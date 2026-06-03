"""Synchronize external live books into the canonical PRS event/state surface."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .contracts import DecisionMode, ExecutionEvent, ExecutionEventType, ProposalOrigin


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CURRENT_POSITIONS_PATH = PROJECT_ROOT / "data" / "portfolio" / "current_positions.json"
OPTIONS_RUNTIME_PATH = PROJECT_ROOT / "data" / "options" / "live" / "options_runtime_state.json"

LONG_VOL_STRATEGIES = {
    "long_straddle",
    "long_strangle",
    "bull_call_spread",
    "bear_put_spread",
}
SHORT_VOL_STRATEGIES = {
    "iron_condor",
    "iron_butterfly",
    "short_strangle",
    "calendar_spread",
}
HEDGE_OBJECTIVES = {
    "event_shock_hedge",
    "hedge_convexity",
    "protect_core",
    "defensive_convexity",
}
FINANCIAL_INDEX_UNDERLYINGS = {"BANKNIFTY", "FINNIFTY"}
INDIA_TZ = timezone(timedelta(hours=5, minutes=30))
CORE_EQUITY_META_CONTROL_KEY = "live_book_sync.core_equity.meta"
CORE_EQUITY_BATCH_CONTROL_KEY = "live_book_sync.core_equity.last_batch"
CORE_EQUITY_MIN_HOLD_TRADING_DAYS = 5
CORE_EQUITY_REDUCTION_OVERRIDE_PCT = 0.35


@dataclass
class LiveBookSyncReport:
    timestamp_utc: str
    equity_trade_events: int = 0
    equity_mark_updates: int = 0
    option_trade_events: int = 0
    option_mark_updates: int = 0
    synced_equity_symbols: int = 0
    synced_option_positions: int = 0
    event_ids: List[int] = None

    def __post_init__(self) -> None:
        if self.event_ids is None:
            self.event_ids = []


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return float(default)
    if not math.isfinite(out):
        return float(default)
    return float(out)


def _safe_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalize_symbol(symbol: Any) -> str:
    return str(symbol or "").strip().upper()


def _parse_datetime(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        ts = datetime.fromisoformat(text)
    except Exception:
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _trading_days_elapsed(start: Optional[datetime], end: datetime) -> int:
    if start is None:
        return 10**9
    start_date = start.astimezone(timezone.utc).date()
    end_date = end.astimezone(timezone.utc).date()
    if end_date <= start_date:
        return 0
    days = 0
    current = start_date
    while current < end_date:
        current += timedelta(days=1)
        if current.weekday() < 5:
            days += 1
    return days


def _india_trade_date(ts: datetime) -> str:
    return ts.astimezone(INDIA_TZ).date().isoformat()


def _core_equity_meta(prs: Any) -> Dict[str, Any]:
    payload = prs.store.get_runtime_control_json(
        CORE_EQUITY_META_CONTROL_KEY,
        {"symbols": {}},
    )
    symbols = payload.get("symbols")
    if not isinstance(symbols, dict):
        payload["symbols"] = {}
    return payload


def _should_defer_core_equity_reduction(
    symbol: str,
    current_qty: float,
    target_qty: float,
    meta: Mapping[str, Any],
    now: datetime,
) -> bool:
    if current_qty <= 0.0 or target_qty >= current_qty:
        return False
    symbol_meta = meta.get(symbol)
    if not isinstance(symbol_meta, Mapping):
        return False
    last_trade_at = _parse_datetime(symbol_meta.get("last_trade_at"))
    holding_days = _trading_days_elapsed(last_trade_at, now)
    if holding_days >= CORE_EQUITY_MIN_HOLD_TRADING_DAYS:
        return False
    reduction_fraction = abs(current_qty - target_qty) / max(abs(current_qty), 1e-12)
    return reduction_fraction < CORE_EQUITY_REDUCTION_OVERRIDE_PCT


def _core_equity_fill_price(
    current_holding: Any,
    target: Optional[Mapping[str, Any]],
    current_qty: float,
) -> float:
    if target is not None and abs(current_qty) <= 1e-8:
        fill_price = _safe_float(target.get("avg_price"), 0.0)
    elif target is not None:
        fill_price = _safe_float(target.get("current_price"), 0.0)
    else:
        fill_price = _safe_float(_holding_field(current_holding, "last_price", 0.0), 0.0)
    return float(fill_price)


def _core_equity_batch_fingerprint(planned_trades: List[Mapping[str, Any]]) -> str:
    if not planned_trades:
        return ""
    canonical = [
        {
            "symbol": str(row.get("symbol") or "").strip().upper(),
            "side": str(row.get("side") or "").strip().lower(),
            "filled_qty": round(abs(_safe_float(row.get("delta_qty"), 0.0)), 8),
            "target_qty": round(_safe_float(row.get("target_qty"), 0.0), 8),
        }
        for row in sorted(
            planned_trades,
            key=lambda item: (
                str(item.get("symbol") or "").strip().upper(),
                str(item.get("side") or "").strip().lower(),
            ),
        )
    ]
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _current_holdings_by_symbol(prs: Any) -> Dict[str, Any]:
    return dict((prs.get_portfolio_state().holdings or {}))


def _holding_field(holding: Any, key: str, default: Any = None) -> Any:
    if isinstance(holding, dict):
        return holding.get(key, default)
    return getattr(holding, key, default)


def _current_equity_holdings(prs: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for symbol, holding in _current_holdings_by_symbol(prs).items():
        instrument_type = str(_holding_field(holding, "instrument_type", "") or "").strip().lower()
        sym = _normalize_symbol(symbol)
        if instrument_type in {"option", "options"} or sym.startswith("OPT::"):
            continue
        out[sym] = holding
    return out


def _current_option_holdings(prs: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for symbol, holding in _current_holdings_by_symbol(prs).items():
        instrument_type = str(_holding_field(holding, "instrument_type", "") or "").strip().lower()
        sym = _normalize_symbol(symbol)
        if instrument_type in {"option", "options"} or sym.startswith("OPT::"):
            out[sym] = holding
    return out


def _core_targets(payload: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    targets: Dict[str, Dict[str, Any]] = {}
    raw_positions = payload.get("positions", {}) if isinstance(payload, Mapping) else {}

    if isinstance(raw_positions, dict):
        iterator = raw_positions.items()
    elif isinstance(raw_positions, list):
        iterator = []
        for row in raw_positions:
            if not isinstance(row, dict):
                continue
            sym = _normalize_symbol(row.get("symbol") or row.get("ticker"))
            if sym:
                iterator.append((sym, row))
    else:
        iterator = []

    for symbol, raw in iterator:
        row = dict(raw or {})
        qty = _safe_float(row.get("quantity"), 0.0)
        if abs(qty) <= 1e-12:
            continue
        targets[_normalize_symbol(symbol)] = {
            "symbol": _normalize_symbol(symbol),
            "quantity": qty,
            "avg_price": _safe_float(row.get("avg_price"), 0.0),
            "current_price": _safe_float(row.get("current_price"), 0.0),
            "weight": _safe_float(row.get("weight"), 0.0),
            "market_value": _safe_float(row.get("market_value"), 0.0),
            "sector": str(row.get("sector", "") or ""),
        }
    return targets


def _option_symbol(position_payload: Mapping[str, Any]) -> str:
    metadata = position_payload.get("metadata") if isinstance(position_payload.get("metadata"), dict) else {}
    prs_symbol = _normalize_symbol(metadata.get("prs_symbol") or position_payload.get("prs_symbol"))
    if prs_symbol:
        return prs_symbol
    position_id = str(position_payload.get("position_id") or position_payload.get("position_key") or "").strip()
    return _normalize_symbol(f"OPT::{position_id}") if position_id else ""


def _position_side(position_payload: Mapping[str, Any]) -> str:
    strategy_type = str(position_payload.get("strategy_type", "") or "").strip().lower()
    if strategy_type in LONG_VOL_STRATEGIES:
        return "buy"
    if strategy_type in SHORT_VOL_STRATEGIES:
        return "sell"

    entry_credit_debit = _safe_float(position_payload.get("entry_credit_debit"), 0.0)
    if abs(entry_credit_debit) > 1e-12:
        return "buy" if entry_credit_debit > 0 else "sell"

    buy_premium = 0.0
    sell_premium = 0.0
    for leg in list(position_payload.get("legs") or []):
        if not isinstance(leg, dict):
            continue
        premium = abs(_safe_float(leg.get("entry_premium", leg.get("premium")), 0.0))
        qty = abs(_safe_float(leg.get("quantity"), 0.0))
        action = str(leg.get("action", "") or "").strip().upper()
        if action == "BUY":
            buy_premium += premium * qty
        elif action == "SELL":
            sell_premium += premium * qty
    return "buy" if buy_premium >= sell_premium else "sell"


def _position_contract_quantity(position_payload: Mapping[str, Any]) -> float:
    metadata = position_payload.get("metadata") if isinstance(position_payload.get("metadata"), dict) else {}
    for source in (metadata, position_payload):
        qty = abs(_safe_float(source.get("quantity"), 0.0)) if isinstance(source, Mapping) else 0.0
        if qty > 1e-12:
            return float(qty)

    total_qty = 0.0
    for leg in list(position_payload.get("legs") or []):
        if not isinstance(leg, dict):
            continue
        total_qty += abs(_safe_float(leg.get("quantity"), 0.0))
    if total_qty > 1e-12:
        return float(total_qty)
    return 1.0


def _per_unit_price(total_value: Any, quantity: float, fallback: float = 0.0) -> float:
    total = abs(_safe_float(total_value, 0.0))
    qty = abs(_safe_float(quantity, 0.0))
    if qty > 1e-12 and total > 0.0:
        return float(total / qty)
    return abs(_safe_float(fallback, 0.0))


def _infer_objective(
    underlying: str,
    metadata: Mapping[str, Any],
    overlay: Mapping[str, Any],
) -> str:
    objective = str(metadata.get("objective", "") or "").strip().lower()
    if objective:
        return objective

    stock_objectives = overlay.get("stock_objectives", {}) if isinstance(overlay.get("stock_objectives"), dict) else {}
    index_objectives = overlay.get("index_objectives", {}) if isinstance(overlay.get("index_objectives"), dict) else {}
    stock_meta = stock_objectives.get(underlying)
    if isinstance(stock_meta, dict):
        objective = str(stock_meta.get("objective", "") or "").strip().lower()
        if objective:
            return objective
    if underlying in index_objectives:
        objective = str(index_objectives.get(underlying) or "").strip().lower()
        if objective:
            return objective
    return "balanced_overlay"


def _infer_protected_slice(
    *,
    underlying: str,
    objective: str,
    metadata: Mapping[str, Any],
    core_targets: Mapping[str, Dict[str, Any]],
) -> Dict[str, Any]:
    protected_symbols = [
        _normalize_symbol(sym)
        for sym in list(metadata.get("protected_symbols") or [])
        if _normalize_symbol(sym)
    ]
    if protected_symbols:
        protected_symbols = [sym for sym in protected_symbols if sym in core_targets]

    if not protected_symbols:
        if underlying in core_targets:
            protected_symbols = [underlying]
        else:
            ranked = sorted(
                core_targets.values(),
                key=lambda row: (_safe_float(row.get("weight"), 0.0), _safe_float(row.get("market_value"), 0.0)),
                reverse=True,
            )
            if underlying in FINANCIAL_INDEX_UNDERLYINGS:
                financial = [
                    row for row in ranked
                    if "financial" in str(row.get("sector", "") or "").strip().lower()
                    or "bank" in _normalize_symbol(row.get("symbol"))
                ]
                protected_symbols = [_normalize_symbol(row.get("symbol")) for row in financial[:12]]
            elif objective in HEDGE_OBJECTIVES:
                protected_symbols = [_normalize_symbol(row.get("symbol")) for row in ranked[:12]]

    protected_symbols = list(dict.fromkeys(sym for sym in protected_symbols if sym in core_targets))
    protected_weight = sum(_safe_float(core_targets[sym].get("weight"), 0.0) for sym in protected_symbols)
    protected_market_value = sum(_safe_float(core_targets[sym].get("market_value"), 0.0) for sym in protected_symbols)
    return {
        "protected_symbols": protected_symbols,
        "protected_weight": float(protected_weight),
        "protected_market_value": float(protected_market_value),
    }


def _option_targets(
    runtime_payload: Mapping[str, Any],
    core_payload: Mapping[str, Any],
) -> Dict[str, Dict[str, Any]]:
    core_targets = _core_targets(core_payload)
    overlay = runtime_payload.get("portfolio_overlay", {}) if isinstance(runtime_payload.get("portfolio_overlay"), dict) else {}
    open_positions = list(runtime_payload.get("open_positions") or [])
    targets: Dict[str, Dict[str, Any]] = {}

    for raw in open_positions:
        if not isinstance(raw, dict):
            continue
        symbol = _option_symbol(raw)
        if not symbol:
            continue
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        underlying = _normalize_symbol(raw.get("underlying") or metadata.get("underlying_symbol"))
        strategy_type = str(raw.get("strategy_type", "") or "options_strategy")
        side = _position_side(raw)
        contract_qty = _position_contract_quantity(raw)
        objective = _infer_objective(underlying, metadata, overlay)
        hedging_state = dict(metadata.get("hedging_state") or {}) if isinstance(metadata.get("hedging_state"), dict) else {}
        if not hedging_state:
            hedging_state = _infer_protected_slice(
                underlying=underlying,
                objective=objective,
                metadata=metadata,
                core_targets=core_targets,
            )
        hedging_state.update(
            {
                "objective": objective,
                "underlying_symbol": underlying,
                "portfolio_objective": str(overlay.get("portfolio_objective", "") or ""),
                "hedge_intensity": _safe_float(overlay.get("hedge_intensity"), 0.0),
                "weekly_hedge_targets": list(overlay.get("weekly_hedge_targets") or []),
            }
        )

        greeks = raw.get("greeks") if isinstance(raw.get("greeks"), dict) else {}
        entry_price = _per_unit_price(
            raw.get("entry_credit_debit"),
            contract_qty,
            fallback=_safe_float(raw.get("entry_credit_debit"), 0.0),
        )
        mark_price = _per_unit_price(
            raw.get("current_value"),
            contract_qty,
            fallback=entry_price if entry_price > 0 else _safe_float(raw.get("max_loss"), 0.0),
        )
        if mark_price <= 0.0:
            mark_price = max(
                entry_price,
                _per_unit_price(
                    raw.get("max_loss"),
                    contract_qty,
                    fallback=_safe_float(raw.get("max_loss"), 0.0),
                ),
            )

        targets[symbol] = {
            "symbol": symbol,
            "position_key": str(metadata.get("prs_position_key") or raw.get("position_id") or "").strip(),
            "strategy_type": strategy_type,
            "underlying_symbol": underlying,
            "side": side,
            "target_quantity": float(contract_qty if side == "buy" else -contract_qty),
            "entry_price": float(entry_price),
            "mark_price": float(mark_price),
            "sector": str(metadata.get("sector", "") or ""),
            "greeks": dict(greeks or {}),
            "objective": objective,
            "hedging_state": hedging_state,
        }
    return targets


def _closed_option_map(runtime_payload: Mapping[str, Any], core_payload: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    open_targets = _option_targets(runtime_payload, core_payload)
    closed_positions = list(runtime_payload.get("closed_positions") or [])
    out: Dict[str, Dict[str, Any]] = {}
    for raw in closed_positions:
        if not isinstance(raw, dict):
            continue
        symbol = _option_symbol(raw)
        if not symbol:
            continue
        if symbol in open_targets:
            continue
        row = dict(raw)
        row["symbol"] = symbol
        out[symbol] = row
    return out


def _event(
    *,
    proposal_id: str,
    trigger_reason_code: str,
    strategy_id: str,
    signal_id: str,
    origin: ProposalOrigin,
    payload: Dict[str, Any],
    runtime_scope: str = "live",
) -> ExecutionEvent:
    return ExecutionEvent(
        event_type=ExecutionEventType.ORDER_FILLED,
        proposal_id=proposal_id,
        sequence_no=0,
        timestamp_utc=_now_utc(),
        trigger_reason_code=trigger_reason_code,
        strategy_id=strategy_id,
        signal_id=signal_id,
        certification_snapshot_hash="external_book_sync",
        risk_override_flag=False,
        decision_mode=DecisionMode.AUTO,
        origin=origin,
        allocator_decision_id="external_book_sync",
        budget_decision_id="external_book_sync",
        liquidity_decision_id="external_book_sync",
        operator_id="live_book_sync",
        runtime_scope=runtime_scope,
        payload=dict(payload or {}),
    )


def _ingest_external_fill(prs: Any, event: ExecutionEvent) -> List[int]:
    event_id = int(prs._append_event(event, update_fsm=False))
    breach_eid = prs._post_event_budget_recheck(event)
    prs._persist_snapshot(source_event_id=event_id)
    prs._run_phase3_live_monitor()
    prs._run_phase6_mortality_monitor()
    prs._materialize_all()
    event_ids = [event_id]
    if breach_eid is not None:
        event_ids.append(int(breach_eid))
    return event_ids


def sync_core_equity_book(
    prs: Any,
    current_positions_payload: Optional[Dict[str, Any]] = None,
    *,
    runtime_scope: str = "live",
) -> Dict[str, Any]:
    payload = current_positions_payload or _safe_json(CURRENT_POSITIONS_PATH)
    targets = _core_targets(payload)
    current = _current_equity_holdings(prs)
    now = _now_utc()
    meta_payload = _core_equity_meta(prs)
    meta_symbols = dict(meta_payload.get("symbols") or {})
    event_ids: List[int] = []
    trade_events = 0
    deferred_symbols: List[str] = []
    planned_trades: List[Dict[str, Any]] = []

    for symbol in sorted(set(current.keys()) | set(targets.keys())):
        current_holding = current.get(symbol)
        current_qty = _safe_float(_holding_field(current_holding, "quantity", 0.0), 0.0)
        target = targets.get(symbol)
        target_qty = _safe_float(target.get("quantity"), 0.0) if target else 0.0
        if _should_defer_core_equity_reduction(symbol, current_qty, target_qty, meta_symbols, now):
            deferred_symbols.append(symbol)
            continue
        delta_qty = target_qty - current_qty
        if abs(delta_qty) <= 1e-8:
            continue

        fill_price = _core_equity_fill_price(current_holding, target, current_qty)
        if fill_price <= 0.0:
            continue

        side = "buy" if delta_qty > 0 else "sell"
        planned_trades.append(
            {
                "symbol": symbol,
                "side": side,
                "delta_qty": float(delta_qty),
                "target_qty": float(target_qty),
                "fill_price": float(fill_price),
                "sector": str((target or {}).get("sector", "") or ""),
            }
        )

    trade_date_ist = _india_trade_date(now)
    plan_fingerprint = _core_equity_batch_fingerprint(planned_trades)
    last_batch = prs.store.get_runtime_control_json(CORE_EQUITY_BATCH_CONTROL_KEY, {})
    dedup_skipped = bool(
        planned_trades
        and str(last_batch.get("trade_date_ist") or "") == trade_date_ist
        and str(last_batch.get("fingerprint") or "") == plan_fingerprint
    )
    dedup_reason = ""
    if dedup_skipped:
        dedup_reason = (
            f"duplicate core sync basket suppressed for trade_date={trade_date_ist} "
            f"fingerprint={plan_fingerprint[:12]}"
        )
    else:
        for trade in planned_trades:
            symbol = str(trade.get("symbol") or "")
            side = str(trade.get("side") or "buy")
            delta_qty = _safe_float(trade.get("delta_qty"), 0.0)
            target_qty = _safe_float(trade.get("target_qty"), 0.0)
            fill_price = _safe_float(trade.get("fill_price"), 0.0)
            proposal_id = f"sync_core_{symbol}_{int(now.timestamp() * 1000)}"
            event = _event(
                proposal_id=proposal_id,
                trigger_reason_code="rebalance.core.sync",
                strategy_id="hedge_fund_core_book",
                signal_id=f"core_sync::{symbol}",
                origin=ProposalOrigin.RESEARCH,
                runtime_scope=runtime_scope,
                payload={
                    "symbol": symbol,
                    "side": side,
                    "filled_qty": float(abs(delta_qty)),
                    "fill_price": float(fill_price),
                    "approved_budget_notional": float(abs(delta_qty) * fill_price),
                    "instrument_type": "equity",
                    "sector": str(trade.get("sector") or ""),
                    "position_key": symbol,
                    "lifecycle_action": "adjust",
                    "rebalance_reason": "core_equity_sync",
                    "strategy_id": "hedge_fund_core_book",
                    "origin": ProposalOrigin.RESEARCH.value,
                },
            )
            event_ids.extend(_ingest_external_fill(prs, event))
            trade_events += 1
            meta_symbols[symbol] = {
                "last_trade_at": now.isoformat(),
                "last_trade_side": side,
                "last_fill_quantity": float(abs(delta_qty)),
                "last_target_quantity": float(target_qty),
            }
        if trade_events > 0:
            prs.store.set_runtime_control_json(
                CORE_EQUITY_BATCH_CONTROL_KEY,
                {
                    "trade_date_ist": trade_date_ist,
                    "fingerprint": plan_fingerprint,
                    "timestamp_utc": now.isoformat(),
                    "trade_events": int(trade_events),
                    "symbols": [str(row.get("symbol") or "") for row in planned_trades],
                },
            )

    price_map = {
        symbol: {"mark_price": float(target.get("current_price", 0.0) or 0.0)}
        for symbol, target in targets.items()
        if _safe_float(target.get("current_price"), 0.0) > 0.0
    }
    mark_updates = 0
    if price_map:
        result = prs.mark_to_market(price_map, source="core_equity_sync", runtime_scope=runtime_scope)
        event_ids.extend(int(eid) for eid in list(result.get("event_ids") or []))
        mark_updates = len(price_map)

    prs.store.set_runtime_control_json(
        CORE_EQUITY_META_CONTROL_KEY,
        {
            "timestamp_utc": now.isoformat(),
            "symbols": meta_symbols,
        },
    )
    prs.store.set_runtime_control_json(
        "live_book_sync.core_equity",
        {
            "timestamp_utc": now.isoformat(),
            "symbols": sorted(targets.keys()),
            "total_symbols": int(len(targets)),
            "total_value": _safe_float(payload.get("total_value"), 0.0),
            "invested_value": _safe_float(payload.get("invested_value"), 0.0),
            "deferred_symbols": deferred_symbols,
            "planned_trade_events": int(len(planned_trades)),
            "dedup_skipped": dedup_skipped,
            "dedup_reason": dedup_reason,
            "trade_date_ist": trade_date_ist,
            "batch_fingerprint": plan_fingerprint,
        },
    )
    return {
        "trade_events": int(trade_events),
        "mark_updates": int(mark_updates),
        "synced_symbols": int(len(targets)),
        "event_ids": event_ids,
        "deferred_symbols": deferred_symbols,
        "dedup_skipped": dedup_skipped,
        "dedup_reason": dedup_reason,
    }


def sync_options_runtime_book(
    prs: Any,
    runtime_payload: Optional[Dict[str, Any]] = None,
    *,
    current_positions_payload: Optional[Dict[str, Any]] = None,
    runtime_scope: str = "live",
) -> Dict[str, Any]:
    payload = runtime_payload or _safe_json(OPTIONS_RUNTIME_PATH)
    core_payload = current_positions_payload or _safe_json(CURRENT_POSITIONS_PATH)
    targets = _option_targets(payload, core_payload)
    closed_map = _closed_option_map(payload, core_payload)
    current = _current_option_holdings(prs)
    event_ids: List[int] = []
    trade_events = 0

    for symbol in sorted(set(current.keys()) | set(targets.keys())):
        current_holding = current.get(symbol)
        current_qty = _safe_float(_holding_field(current_holding, "quantity", 0.0), 0.0)
        target = targets.get(symbol)
        target_qty = _safe_float(target.get("target_quantity"), 0.0) if target else 0.0
        delta_qty = target_qty - current_qty
        if abs(delta_qty) <= 1e-8:
            continue

        if target is not None and (abs(target_qty) > abs(current_qty) or abs(current_qty) <= 1e-8):
            side = str(target.get("side", "buy") or "buy").strip().lower()
            fill_price = _safe_float(target.get("entry_price"), 0.0)
            position_key = str(target.get("position_key") or symbol)
            strategy_id = str(target.get("strategy_type") or "options_strategy")
            objective = str(target.get("objective") or "balanced_overlay")
            origin = ProposalOrigin.OPTIONS_HEDGE if objective in HEDGE_OBJECTIVES else ProposalOrigin.OPTIONS_ALPHA
            event = _event(
                proposal_id=f"sync_option_open_{position_key}_{int(_now_utc().timestamp() * 1000)}",
                trigger_reason_code="options.runtime.sync.open",
                strategy_id=strategy_id,
                signal_id=f"options_sync_open::{position_key}",
                origin=origin,
                runtime_scope=runtime_scope,
                payload={
                    "symbol": symbol,
                    "side": side,
                    "filled_qty": float(abs(delta_qty)),
                    "fill_price": float(fill_price),
                    "approved_budget_notional": float(abs(delta_qty) * fill_price),
                    "instrument_type": "option",
                    "underlying_symbol": str(target.get("underlying_symbol", "") or ""),
                    "position_key": position_key,
                    "lifecycle_action": "open",
                    "rebalance_reason": str(objective),
                    "strategy_id": strategy_id,
                    "origin": origin.value,
                    "hedging_state": dict(target.get("hedging_state") or {}),
                    "greek_delta_per_unit": _safe_float((target.get("greeks") or {}).get("delta"), 0.0),
                    "greek_gamma_per_unit": _safe_float((target.get("greeks") or {}).get("gamma"), 0.0),
                    "greek_vega_per_unit": _safe_float((target.get("greeks") or {}).get("vega"), 0.0),
                    "greek_theta_per_unit": _safe_float((target.get("greeks") or {}).get("theta"), 0.0),
                    "greek_rho_per_unit": _safe_float((target.get("greeks") or {}).get("rho"), 0.0),
                },
            )
        else:
            previous_side = "buy" if current_qty > 0 else "sell"
            side = "sell" if previous_side == "buy" else "buy"
            closed_row = closed_map.get(symbol, {})
            close_qty = abs(current_qty) if abs(current_qty) > 1e-12 else _position_contract_quantity(closed_row)
            fill_price = _per_unit_price(
                closed_row.get("current_value"),
                close_qty,
                fallback=_holding_field(current_holding, "last_price", 0.0),
            )
            if fill_price <= 0.0:
                fill_price = _per_unit_price(
                    closed_row.get("entry_credit_debit"),
                    close_qty,
                    fallback=_holding_field(current_holding, "avg_price", 0.0),
                )
            position_key = str(
                closed_row.get("position_id")
                or closed_row.get("position_key")
                or symbol.replace("OPT::", "", 1)
            )
            realized_pnl = _safe_float(closed_row.get("realized_pnl"), 0.0)
            strategy_id = str(closed_row.get("strategy_type") or _holding_field(current_holding, "strategy_id", "") or "options_strategy")
            origin_name = str(_holding_field(current_holding, "origin", "") or "")
            origin = ProposalOrigin.OPTIONS_HEDGE if origin_name == ProposalOrigin.OPTIONS_HEDGE.value else ProposalOrigin.OPTIONS_ALPHA
            event = _event(
                proposal_id=f"sync_option_close_{position_key}_{int(_now_utc().timestamp() * 1000)}",
                trigger_reason_code="options.runtime.sync.close",
                strategy_id=strategy_id,
                signal_id=f"options_sync_close::{position_key}",
                origin=origin,
                runtime_scope=runtime_scope,
                payload={
                    "symbol": symbol,
                    "side": side,
                    "filled_qty": float(abs(delta_qty)),
                    "fill_price": float(fill_price),
                    "approved_budget_notional": float(abs(delta_qty) * fill_price),
                    "instrument_type": "option",
                    "underlying_symbol": str(closed_row.get("underlying", "") or ""),
                    "position_key": position_key,
                    "lifecycle_action": "close",
                    "rebalance_reason": str(closed_row.get("exit_reason", "") or "options_runtime_close_sync"),
                    "strategy_id": strategy_id,
                    "origin": origin.value,
                    "realized_pnl": float(realized_pnl),
                    "max_adverse_excursion": 0.0,
                    "max_favorable_excursion": 0.0,
                },
            )

        event_ids.extend(_ingest_external_fill(prs, event))
        trade_events += 1

    price_map = {}
    for symbol, target in targets.items():
        price_map[symbol] = {
            "mark_price": float(target.get("mark_price", 0.0) or 0.0),
            "greek_delta_per_unit": _safe_float((target.get("greeks") or {}).get("delta"), 0.0),
            "greek_gamma_per_unit": _safe_float((target.get("greeks") or {}).get("gamma"), 0.0),
            "greek_vega_per_unit": _safe_float((target.get("greeks") or {}).get("vega"), 0.0),
            "greek_theta_per_unit": _safe_float((target.get("greeks") or {}).get("theta"), 0.0),
            "greek_rho_per_unit": _safe_float((target.get("greeks") or {}).get("rho"), 0.0),
        }
    mark_updates = 0
    if price_map:
        result = prs.mark_to_market(price_map, source="options_runtime_sync", runtime_scope=runtime_scope)
        event_ids.extend(int(eid) for eid in list(result.get("event_ids") or []))
        mark_updates = len(price_map)

    prs.store.set_runtime_control_json(
        "live_book_sync.options_runtime",
        {
            "timestamp_utc": _now_utc().isoformat(),
            "open_position_ids": sorted(str((row.get("position_key") or "")) for row in targets.values()),
            "total_positions": int(len(targets)),
            "net_equity": _safe_float(payload.get("net_equity"), 0.0),
            "realized_net_pnl": _safe_float(payload.get("realized_net_pnl"), 0.0),
            "unrealized_pnl": _safe_float(payload.get("unrealized_pnl"), 0.0),
        },
    )
    return {
        "trade_events": int(trade_events),
        "mark_updates": int(mark_updates),
        "synced_positions": int(len(targets)),
        "event_ids": event_ids,
    }


def sync_live_books(
    prs: Any,
    *,
    current_positions_payload: Optional[Dict[str, Any]] = None,
    runtime_payload: Optional[Dict[str, Any]] = None,
    runtime_scope: str = "live",
) -> LiveBookSyncReport:
    report = LiveBookSyncReport(timestamp_utc=_now_utc().isoformat())
    equity = sync_core_equity_book(
        prs,
        current_positions_payload=current_positions_payload,
        runtime_scope=runtime_scope,
    )
    options = sync_options_runtime_book(
        prs,
        runtime_payload=runtime_payload,
        current_positions_payload=current_positions_payload,
        runtime_scope=runtime_scope,
    )
    report.equity_trade_events = int(equity.get("trade_events", 0) or 0)
    report.equity_mark_updates = int(equity.get("mark_updates", 0) or 0)
    report.synced_equity_symbols = int(equity.get("synced_symbols", 0) or 0)
    report.option_trade_events = int(options.get("trade_events", 0) or 0)
    report.option_mark_updates = int(options.get("mark_updates", 0) or 0)
    report.synced_option_positions = int(options.get("synced_positions", 0) or 0)
    report.event_ids = list(equity.get("event_ids", []) or []) + list(options.get("event_ids", []) or [])
    return report


def sync_live_books_from_disk(prs: Any, *, runtime_scope: str = "live") -> Dict[str, Any]:
    report = sync_live_books(
        prs,
        current_positions_payload=_safe_json(CURRENT_POSITIONS_PATH),
        runtime_payload=_safe_json(OPTIONS_RUNTIME_PATH),
        runtime_scope=runtime_scope,
    )
    return asdict(report)
