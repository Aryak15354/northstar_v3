"""Canonical runtime accounting refresh for the live hedge-fund stack."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import yaml

from src.options.trade_ledger import TradeLedger
from src.pnl.ledger import LedgerBook, LedgerEntry, LedgerEntryType, UnifiedPnLLedger
from src.pnl.nav_calculator import NAVCalculator
from src.pnl.reconciliation import PnLReconciler, ReconciliationResult
from src.runtime.storage import RuntimeEventStore


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PNL_CONFIG_PATH = PROJECT_ROOT / "config" / "pnl_config.yaml"
MASTER_LEDGER_PATH = PROJECT_ROOT / "data" / "pnl" / "master_ledger.parquet"
NAV_HISTORY_PATH = PROJECT_ROOT / "data" / "pnl" / "nav_history.parquet"
RECON_PATH = PROJECT_ROOT / "data" / "pnl" / "reconciliation_log.parquet"
ACCOUNTING_SNAPSHOT_PATH = PROJECT_ROOT / "data" / "pnl" / "accounting_snapshot.json"
TRADE_LEDGER_PATH = PROJECT_ROOT / "data" / "options" / "trade_ledger.parquet"
RUNTIME_STATE_PATH = PROJECT_ROOT / "data" / "options" / "live" / "options_runtime_state.json"
EQUITY_PNL_PATH = PROJECT_ROOT / "data" / "portfolio" / "pnl_on_paper.parquet"
CURRENT_POSITIONS_PATH = PROJECT_ROOT / "data" / "portfolio" / "current_positions.json"
SHADOW_PNL_PATH = PROJECT_ROOT / "data" / "execution" / "shadow_pnl.parquet"
RUNTIME_DB_PATH = PROJECT_ROOT / "data" / "runtime" / "portfolio_runtime.db"
UNIFIED_STATE_PATH = PROJECT_ROOT / "data" / "state" / "unified_state.json"


@dataclass
class AccountingRefreshReport:
    status: str
    timestamp: str
    starting_capital_inr: float
    inception_date: str
    equity_rows: int
    options_rows: int
    shadow_rows: int
    ledger_rows: int
    nav_rows: int
    latest_nav_date: Optional[str]
    reconciliation_status: str
    reconciliation_date: Optional[str]
    trade_ledger_rows: int
    trade_ledger_backfilled_open: int
    trade_ledger_backfilled_close: int
    runtime_db_control_updated: bool
    runtime_db_control_error: str


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return float(default)
    return float(out) if np.isfinite(out) else float(default)


def _safe_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _naive_utc(value: Any) -> datetime:
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts.to_pydatetime()


def _load_config() -> Dict[str, Any]:
    if not PNL_CONFIG_PATH.exists():
        return {
            "pnl": {
                "nav": {
                    "starting_capital_inr": 10_000_000.0,
                    "inception_date": "2024-09-01",
                }
            }
        }
    payload = yaml.safe_load(PNL_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _nav_config(config: Dict[str, Any]) -> Dict[str, Any]:
    pnl = config.get("pnl") or {}
    nav = pnl.get("nav") or {}
    return nav if isinstance(nav, dict) else {}


def _canonical_total_value(default_capital: float) -> float:
    current_positions = _safe_json(CURRENT_POSITIONS_PATH)
    if current_positions:
        value = _safe_float(current_positions.get("total_value"), default=np.nan)
        if np.isfinite(value) and value > 0:
            return float(value)

    state = _safe_json(UNIFIED_STATE_PATH)
    if state:
        governor = state.get("governor_state") or {}
        pnl_state = state.get("pnl_state") or {}
        portfolio = state.get("portfolio") or {}
        for candidate in (
            portfolio.get("total_value"),
            governor.get("total_capital_inr"),
            pnl_state.get("current_nav_inr"),
        ):
            value = _safe_float(candidate, default=np.nan)
            if np.isfinite(value) and value > 0:
                return float(value)

    return float(default_capital)


def _ledger_entry(
    *,
    entry_id: str,
    entry_type: LedgerEntryType,
    book: LedgerBook,
    trade_date: datetime,
    ticker: str,
    quantity: float,
    price: float,
    notional: float,
    realized_pnl: float,
    unrealized_pnl_change: float,
    transaction_cost: float,
    net_pnl: float,
    strategy_id: Optional[str],
    source: str,
    notes: str,
    settlement_date: Optional[datetime] = None,
    option_type: Optional[str] = None,
    strike: Optional[float] = None,
    expiry: Optional[datetime] = None,
    greeks_at_entry: Optional[Dict[str, Any]] = None,
    original_entry_id: Optional[str] = None,
) -> Dict[str, Any]:
    ts = _naive_utc(trade_date)
    entry = LedgerEntry(
        entry_id=entry_id,
        entry_type=entry_type,
        book=book,
        trade_date=ts,
        settlement_date=_naive_utc(settlement_date or trade_date),
        recorded_at=_now_utc(),
        ticker=ticker,
        quantity=float(quantity),
        price=float(price),
        notional=float(abs(notional)),
        realized_pnl=float(realized_pnl),
        unrealized_pnl_change=float(unrealized_pnl_change),
        transaction_cost=float(transaction_cost),
        net_pnl=float(net_pnl),
        strategy_id=strategy_id,
        signal_strength=None,
        option_type=option_type,
        strike=strike,
        expiry=_naive_utc(expiry) if expiry is not None else None,
        greeks_at_entry=greeks_at_entry,
        source=source,
        notes=notes,
        original_entry_id=original_entry_id,
    )
    return entry.to_dict()


def _strip_regenerated_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    for col in ("entry_id", "ticker", "book", "source", "notes"):
        if col not in out.columns:
            out[col] = ""
    mask = out["entry_id"].astype(str).str.startswith("ACCOUNTING_")
    # Runtime equity fills are regenerated from the current runtime DB on every
    # refresh. Preserve-only mode must not carry forward stale fills from an
    # earlier event-store incarnation, otherwise a DB reset/reseed duplicates
    # the same executed basket in the canonical ledger.
    mask |= out["entry_id"].astype(str).str.startswith("RUNTIME_EQUITY_FILL_")
    mask |= out["source"].astype(str).eq("PRS_SYNC")
    mask |= (
        out["book"].astype(str).eq("EQUITY")
        & out["ticker"].astype(str).eq("PORTFOLIO")
        & (
            out["source"].astype(str).eq("MIGRATION")
            | out["notes"].astype(str).str.contains("portfolio pnl_on_paper", case=False, na=False)
        )
    )
    mask |= (
        out["book"].astype(str).eq("SHADOW")
        & (
            out["source"].astype(str).eq("MIGRATION")
            | out["notes"].astype(str).str.contains("shadow p&l", case=False, na=False)
        )
    )
    return out.loc[~mask].copy()


def _runtime_equity_book_mark() -> tuple[Optional[pd.Timestamp], Optional[float]]:
    current_positions = _safe_json(CURRENT_POSITIONS_PATH)
    if not current_positions:
        return None, None

    ts = pd.to_datetime(
        current_positions.get("updated_at") or current_positions.get("timestamp"),
        errors="coerce",
        utc=True,
    )
    if pd.isna(ts):
        return None, None

    cash = _safe_float(current_positions.get("cash"), default=np.nan)
    invested_value = _safe_float(current_positions.get("invested_value"), default=np.nan)
    options_market_value = _safe_float(current_positions.get("options_market_value"), default=0.0)

    if np.isfinite(cash) and np.isfinite(invested_value):
        equity_book_value = float(cash + invested_value)
    else:
        total_value = _safe_float(current_positions.get("total_value"), default=np.nan)
        if not np.isfinite(total_value):
            return None, None
        equity_book_value = float(total_value - options_market_value)

    if not np.isfinite(equity_book_value) or equity_book_value <= 0.0:
        return None, None

    return pd.Timestamp(ts).tz_convert("UTC").tz_localize(None).normalize(), equity_book_value


def _build_equity_rows(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    nav_cfg = _nav_config(config)
    starting_capital = _safe_float(nav_cfg.get("starting_capital_inr"), 10_000_000.0)
    inception_date = pd.to_datetime(nav_cfg.get("inception_date", "2024-09-01"), errors="coerce").normalize()

    if EQUITY_PNL_PATH.exists():
        df = pd.read_parquet(EQUITY_PNL_PATH)
    else:
        df = pd.DataFrame(columns=["Date", "Equity"])

    if not df.empty and "Date" in df.columns and "Equity" in df.columns:
        df = df.copy()
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.normalize()
        df["Equity"] = pd.to_numeric(df["Equity"], errors="coerce")
        df = df.dropna(subset=["Date", "Equity"]).sort_values("Date")
        df = df[df["Date"] >= inception_date]
        if not df.empty:
            max_abs_equity = float(df["Equity"].abs().max())
            if max_abs_equity <= 10.0:
                df["equity_value_inr"] = df["Equity"] * starting_capital
            else:
                df["equity_value_inr"] = df["Equity"]
            df = df[["Date", "equity_value_inr"]].copy()
        else:
            df = pd.DataFrame(columns=["Date", "equity_value_inr"])
    else:
        df = pd.DataFrame(columns=["Date", "equity_value_inr"])

    runtime_date, runtime_equity_value = _runtime_equity_book_mark()
    if runtime_date is not None and runtime_equity_value is not None and runtime_date >= inception_date:
        runtime_row = pd.DataFrame([{"Date": runtime_date, "equity_value_inr": float(runtime_equity_value)}])
        if df.empty:
            df = runtime_row
        else:
            df = pd.concat([df[df["Date"] != runtime_date], runtime_row], ignore_index=True)
            df = df.sort_values("Date").reset_index(drop=True)

    if df.empty:
        return []

    df["daily_pnl_inr"] = df["equity_value_inr"].diff()
    df.iloc[0, df.columns.get_loc("daily_pnl_inr")] = float(df["equity_value_inr"].iloc[0] - starting_capital)

    rows: List[Dict[str, Any]] = []
    for row in df.itertuples(index=False):
        trade_date = pd.Timestamp(row.Date).to_pydatetime()
        value_inr = _safe_float(row.equity_value_inr)
        daily_pnl = _safe_float(row.daily_pnl_inr)
        rows.append(
            _ledger_entry(
                entry_id=f"ACCOUNTING_EQUITY_MTM_{pd.Timestamp(row.Date).strftime('%Y%m%d')}",
                entry_type=LedgerEntryType.EQUITY_MTM,
                book=LedgerBook.EQUITY,
                trade_date=trade_date,
                ticker="PORTFOLIO",
                quantity=0.0,
                price=value_inr,
                notional=value_inr,
                realized_pnl=0.0,
                unrealized_pnl_change=daily_pnl,
                transaction_cost=0.0,
                net_pnl=daily_pnl,
                strategy_id="hedge_fund_core_book",
                source="ACCOUNTING_SYNC",
                notes="Canonical equity mark from portfolio pnl_on_paper",
            )
        )
    return rows


def _build_cash_seed_rows(config: Dict[str, Any], existing_rows: pd.DataFrame) -> List[Dict[str, Any]]:
    nav_cfg = _nav_config(config)
    starting_capital = _safe_float(nav_cfg.get("starting_capital_inr"), 10_000_000.0)
    if starting_capital <= 0.0:
        return []

    if isinstance(existing_rows, pd.DataFrame) and not existing_rows.empty and "entry_type" in existing_rows.columns:
        existing_types = existing_rows["entry_type"].astype(str).str.upper()
        if existing_types.isin({"CASH_IN", "CASH_OUT"}).any():
            return []

    inception_value = pd.to_datetime(nav_cfg.get("inception_date", "2024-09-01"), errors="coerce")
    if pd.isna(inception_value):
        inception_value = pd.Timestamp("2024-09-01")
    trade_date = _naive_utc(inception_value)

    return [
        _ledger_entry(
            entry_id=f"ACCOUNTING_CASH_IN_{pd.Timestamp(trade_date).strftime('%Y%m%d')}",
            entry_type=LedgerEntryType.CASH_IN,
            book=LedgerBook.CASH,
            trade_date=trade_date,
            ticker="INR",
            quantity=0.0,
            price=float(starting_capital),
            notional=float(starting_capital),
            realized_pnl=0.0,
            unrealized_pnl_change=0.0,
            transaction_cost=0.0,
            net_pnl=0.0,
            strategy_id="fund_capital_base",
            source="ACCOUNTING_SYNC",
            notes="Canonical starting capital seed deposit",
        )
    ]


def _build_runtime_equity_trade_rows() -> List[Dict[str, Any]]:
    if not RUNTIME_DB_PATH.exists():
        return []

    try:
        store = RuntimeEventStore(str(RUNTIME_DB_PATH), read_only=True)
    except Exception:
        return []

    try:
        events = store.list_events(since_event_id=0)
    finally:
        store.close()

    rows: List[Dict[str, Any]] = []
    for row in events:
        event_type = str(row.get("event_type", "") or "").strip().upper()
        if event_type not in {"ORDER_FILLED", "ORDER_PARTIAL"}:
            continue
        try:
            payload = json.loads(str(row.get("payload_json", "{}") or "{}"))
        except Exception:
            payload = {}
        instrument_type = str(payload.get("instrument_type", "equity") or "equity").strip().lower()
        if instrument_type not in {"equity", "cash_equity"}:
            continue

        symbol = str(payload.get("symbol", "") or "").strip().upper()
        qty = _safe_float(payload.get("filled_qty", payload.get("quantity")), 0.0)
        price = _safe_float(payload.get("fill_price", payload.get("price")), 0.0)
        if not symbol or qty <= 0.0 or price <= 0.0:
            continue

        side = str(payload.get("side", "buy") or "buy").strip().lower()
        entry_type = LedgerEntryType.EQUITY_BUY if side == "buy" else LedgerEntryType.EQUITY_SELL
        signed_qty = float(qty if side == "buy" else -qty)
        trade_date = pd.to_datetime(row.get("timestamp_utc"), errors="coerce", utc=True)
        if pd.isna(trade_date):
            continue

        event_id = int(row.get("event_id", 0) or 0)
        trigger_reason = str(row.get("trigger_reason_code", "") or payload.get("rebalance_reason") or "runtime_equity_fill")
        strategy_id = str(row.get("strategy_id", "") or payload.get("strategy_id") or "hedge_fund_core_book")
        rows.append(
            _ledger_entry(
                entry_id=f"RUNTIME_EQUITY_FILL_{event_id}",
                entry_type=entry_type,
                book=LedgerBook.EQUITY,
                trade_date=pd.Timestamp(trade_date).to_pydatetime(),
                ticker=symbol,
                quantity=signed_qty,
                price=price,
                notional=float(abs(qty * price)),
                realized_pnl=0.0,
                unrealized_pnl_change=0.0,
                transaction_cost=0.0,
                net_pnl=0.0,
                strategy_id=strategy_id,
                source="PRS_SYNC",
                notes=f"Canonical core equity rebalance fill from portfolio_events {event_id}: {trigger_reason}",
                original_entry_id=str(event_id),
            )
        )
    return rows


def _build_shadow_rows(config: Dict[str, Any], latest_reference_date: Optional[datetime]) -> List[Dict[str, Any]]:
    if not SHADOW_PNL_PATH.exists() or latest_reference_date is None:
        return []

    df = pd.read_parquet(SHADOW_PNL_PATH)
    if df.empty or "timestamp" not in df.columns:
        return []

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    df["total_portfolio_value"] = pd.to_numeric(df.get("total_portfolio_value"), errors="coerce")
    df = df.dropna(subset=["timestamp", "total_portfolio_value"]).sort_values("timestamp")
    if df.empty:
        return []

    latest_shadow_ts = df["timestamp"].iloc[-1]
    latest_shadow_dt = pd.Timestamp(latest_shadow_ts).tz_convert("UTC").tz_localize(None).to_pydatetime()
    if latest_reference_date - latest_shadow_dt > timedelta(days=30):
        return []

    nav_cfg = _nav_config(config)
    starting_capital = _safe_float(nav_cfg.get("starting_capital_inr"), 10_000_000.0)
    df["shadow_daily_pnl"] = df["total_portfolio_value"].diff()
    df.iloc[0, df.columns.get_loc("shadow_daily_pnl")] = float(df["total_portfolio_value"].iloc[0] - starting_capital)

    rows: List[Dict[str, Any]] = []
    for row in df.itertuples(index=False):
        trade_date = pd.Timestamp(row.timestamp).to_pydatetime()
        total_value = _safe_float(row.total_portfolio_value)
        daily_pnl = _safe_float(row.shadow_daily_pnl)
        rows.append(
            _ledger_entry(
                entry_id=f"ACCOUNTING_SHADOW_MTM_{pd.Timestamp(row.timestamp).strftime('%Y%m%d_%H%M%S')}",
                entry_type=LedgerEntryType.SHADOW_MTM,
                book=LedgerBook.SHADOW,
                trade_date=trade_date,
                ticker="SHADOW_PORTFOLIO",
                quantity=0.0,
                price=total_value,
                notional=total_value,
                realized_pnl=0.0,
                unrealized_pnl_change=daily_pnl,
                transaction_cost=0.0,
                net_pnl=daily_pnl,
                strategy_id="shadow_book",
                source="ACCOUNTING_SYNC",
                notes="Canonical shadow mark from shadow_pnl",
            )
        )
    return rows


def _load_runtime_timestamp(runtime_payload: Dict[str, Any]) -> Optional[datetime]:
    ts = pd.to_datetime(runtime_payload.get("timestamp"), errors="coerce", utc=True)
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts).tz_convert("UTC").tz_localize(None).to_pydatetime()


def _sync_trade_ledger_from_runtime(runtime_payload: Dict[str, Any]) -> Dict[str, int]:
    ledger = TradeLedger(str(TRADE_LEDGER_PATH))
    return ledger.sync_runtime_state(runtime_payload)


def _build_options_rows(runtime_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if TRADE_LEDGER_PATH.exists():
        trade_df = pd.read_parquet(TRADE_LEDGER_PATH)
    else:
        trade_df = pd.DataFrame()

    if not trade_df.empty:
        trade_df = trade_df.copy()
        trade_df["timestamp"] = pd.to_datetime(trade_df.get("timestamp"), errors="coerce", utc=True)
        trade_df = trade_df.dropna(subset=["trade_id", "action", "timestamp"])
        trade_df = trade_df[trade_df["action"].astype(str).str.lower().isin({"open", "close"})]
        for row in trade_df.itertuples(index=False):
            trade_date = pd.Timestamp(row.timestamp).to_pydatetime()
            trade_id = str(row.trade_id)
            underlying = str(getattr(row, "underlying", "") or "UNKNOWN")
            strategy_type = str(getattr(row, "strategy_type", "") or "options_strategy")
            entry_credit_debit = _safe_float(getattr(row, "entry_credit_debit", 0.0))
            exit_value = _safe_float(getattr(row, "exit_value", 0.0))
            gross_pnl = _safe_float(getattr(row, "gross_pnl", np.nan), np.nan)
            costs = _safe_float(getattr(row, "costs", 0.0))
            tax = _safe_float(getattr(row, "tax", 0.0))
            net_pnl = _safe_float(getattr(row, "net_pnl", 0.0))
            greeks_raw = getattr(row, "greeks_at_entry", None)
            greeks = None
            if isinstance(greeks_raw, str) and greeks_raw.strip():
                try:
                    parsed = json.loads(greeks_raw)
                    greeks = parsed if isinstance(parsed, dict) else None
                except Exception:
                    greeks = None
            expiry = pd.to_datetime(getattr(row, "expiry", None), errors="coerce")
            if str(row.action).lower() == "open":
                rows.append(
                    _ledger_entry(
                        entry_id=f"ACCOUNTING_OPTIONS_OPEN_{trade_id}",
                        entry_type=LedgerEntryType.OPTIONS_BUY if entry_credit_debit >= 0 else LedgerEntryType.OPTIONS_SELL,
                        book=LedgerBook.OPTIONS,
                        trade_date=trade_date,
                        ticker=underlying,
                        quantity=0.0,
                        price=abs(entry_credit_debit),
                        notional=abs(entry_credit_debit),
                        realized_pnl=0.0,
                        unrealized_pnl_change=0.0,
                        transaction_cost=0.0,
                        net_pnl=0.0,
                        strategy_id=strategy_type,
                        source="ACCOUNTING_SYNC",
                        notes="Canonical options entry from immutable trade_ledger open action",
                        option_type="SPREAD",
                        expiry=expiry.to_pydatetime() if not pd.isna(expiry) else None,
                        greeks_at_entry=greeks,
                        original_entry_id=trade_id,
                    )
                )
            else:
                total_cost_drag = float(costs + tax)
                rows.append(
                    _ledger_entry(
                        entry_id=f"ACCOUNTING_OPTIONS_CLOSE_{trade_id}",
                        entry_type=LedgerEntryType.OPTIONS_SELL if entry_credit_debit >= 0 else LedgerEntryType.OPTIONS_BUY,
                        book=LedgerBook.OPTIONS,
                        trade_date=trade_date,
                        ticker=underlying,
                        quantity=0.0,
                        price=abs(exit_value),
                        notional=abs(exit_value),
                        realized_pnl=_safe_float(gross_pnl if np.isfinite(gross_pnl) else net_pnl),
                        unrealized_pnl_change=0.0,
                        transaction_cost=-abs(total_cost_drag),
                        net_pnl=net_pnl,
                        strategy_id=strategy_type,
                        source="ACCOUNTING_SYNC",
                        notes="Canonical options realization from immutable trade_ledger close action",
                        option_type="SPREAD",
                        expiry=expiry.to_pydatetime() if not pd.isna(expiry) else None,
                        greeks_at_entry=greeks,
                        original_entry_id=trade_id,
                    )
                )

    runtime_ts = _load_runtime_timestamp(runtime_payload)
    open_positions = runtime_payload.get("open_positions", [])
    if runtime_ts is not None and isinstance(open_positions, list):
        for pos in open_positions:
            if not isinstance(pos, dict):
                continue
            trade_id = str(pos.get("position_id") or "").strip()
            if not trade_id:
                continue
            current_value = _safe_float(pos.get("current_value"), 0.0)
            unrealized_pnl = _safe_float(pos.get("unrealized_pnl"), 0.0)
            greeks = pos.get("greeks") if isinstance(pos.get("greeks"), dict) else None
            expiry = pd.to_datetime(pos.get("expiry"), errors="coerce")
            rows.append(
                _ledger_entry(
                    entry_id=f"ACCOUNTING_OPTIONS_MTM_{trade_id}_{pd.Timestamp(runtime_ts).strftime('%Y%m%d')}",
                    entry_type=LedgerEntryType.OPTIONS_MTM,
                    book=LedgerBook.OPTIONS,
                    trade_date=runtime_ts,
                    ticker=str(pos.get("underlying") or "UNKNOWN"),
                    quantity=0.0,
                    price=current_value,
                    notional=current_value,
                    realized_pnl=0.0,
                    unrealized_pnl_change=unrealized_pnl,
                    transaction_cost=0.0,
                    net_pnl=unrealized_pnl,
                    strategy_id=str(pos.get("strategy_type") or "options_strategy"),
                    source="ACCOUNTING_SYNC",
                    notes="Canonical live options MTM from runtime snapshot",
                    option_type="SPREAD",
                    expiry=expiry.to_pydatetime() if not pd.isna(expiry) else None,
                    greeks_at_entry=greeks,
                    original_entry_id=trade_id,
                )
            )

    return rows


def _write_master_ledger(existing_rows: pd.DataFrame, generated_rows: List[Dict[str, Any]]) -> pd.DataFrame:
    generated_df = pd.DataFrame(generated_rows)
    if existing_rows.empty:
        combined = generated_df
    elif generated_df.empty:
        combined = existing_rows
    else:
        combined = pd.concat([existing_rows, generated_df], ignore_index=True)

    if combined.empty:
        combined = pd.DataFrame(
            columns=[
                "entry_id",
                "entry_type",
                "book",
                "trade_date",
                "settlement_date",
                "recorded_at",
                "ticker",
                "quantity",
                "price",
                "notional",
                "realized_pnl",
                "unrealized_pnl_change",
                "transaction_cost",
                "net_pnl",
                "strategy_id",
                "signal_strength",
                "option_type",
                "strike",
                "expiry",
                "greeks_at_entry",
                "source",
                "notes",
                "original_entry_id",
            ]
        )

    if "entry_id" in combined.columns:
        combined = combined.drop_duplicates(subset=["entry_id"], keep="last")

    combined = combined.sort_values(
        by=[col for col in ["trade_date", "recorded_at", "entry_id"] if col in combined.columns],
        kind="stable",
    ).reset_index(drop=True)
    for col in ("trade_date", "settlement_date", "recorded_at", "expiry"):
        if col in combined.columns:
            series = pd.to_datetime(combined[col], errors="coerce", utc=True)
            combined[col] = series.dt.tz_convert(None)
    # Compatibility aliases for older operator checks.
    if "trade_date" in combined.columns:
        trade_dates = pd.to_datetime(combined["trade_date"], errors="coerce")
        if "date" not in combined.columns:
            combined["date"] = trade_dates
        else:
            combined["date"] = pd.to_datetime(combined["date"], errors="coerce").fillna(trade_dates)
    if "notional" in combined.columns:
        notionals = pd.to_numeric(combined["notional"], errors="coerce")
        if "amount" not in combined.columns:
            combined["amount"] = notionals
        else:
            combined["amount"] = pd.to_numeric(combined["amount"], errors="coerce").fillna(notionals)
    MASTER_LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(MASTER_LEDGER_PATH, index=False)
    return combined


def _write_nav_history(config: Dict[str, Any]) -> pd.DataFrame:
    ledger = UnifiedPnLLedger(ledger_path=str(MASTER_LEDGER_PATH), config=config)
    nav_cfg = _nav_config(config)
    inception_date = _naive_utc(pd.to_datetime(nav_cfg.get("inception_date", "2024-09-01"), errors="coerce"))
    if ledger.ledger_df.empty:
        end_date = _now_utc()
    else:
        latest = pd.to_datetime(ledger.ledger_df["trade_date"], errors="coerce", utc=True).dropna()
        end_date = _naive_utc(latest.max()) if not latest.empty else _naive_utc(_now_utc())
    nav = NAVCalculator(ledger, config).compute_daily_nav(start_date=inception_date, end_date=end_date)
    nav_export = nav.reset_index()
    if "index" in nav_export.columns and "date" not in nav_export.columns:
        nav_export = nav_export.rename(columns={"index": "date"})
    NAV_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    nav_export.to_parquet(NAV_HISTORY_PATH, index=False)
    return nav_export


def _write_reconciliation(config: Dict[str, Any]) -> ReconciliationResult:
    ledger = UnifiedPnLLedger(ledger_path=str(MASTER_LEDGER_PATH), config=config)
    nav_calc = NAVCalculator(ledger, config)
    reconciler = PnLReconciler(ledger, nav_calc, config)
    if ledger.ledger_df.empty:
        result = ReconciliationResult(
            date=_now_utc(),
            equity_options_balanced=True,
            equity_options_discrepancy_inr=0.0,
            live_shadow_discrepancy_inr=0.0,
            live_shadow_discrepancy_pct=0.0,
            live_shadow_flag=False,
            legacy_migration_discrepancies=[],
            overall_status="CLEAN",
            action_required=[],
        )
    else:
        latest = pd.to_datetime(ledger.ledger_df["trade_date"], errors="coerce", utc=True).dropna()
        recon_date = _naive_utc(latest.max()) if not latest.empty else _naive_utc(_now_utc())
        result = reconciler.run_daily_reconciliation(recon_date)

    row = {
        "date": result.date,
        "equity_options_balanced": result.equity_options_balanced,
        "equity_options_discrepancy_inr": result.equity_options_discrepancy_inr,
        "live_shadow_discrepancy_inr": result.live_shadow_discrepancy_inr,
        "live_shadow_discrepancy_pct": result.live_shadow_discrepancy_pct,
        "live_shadow_flag": result.live_shadow_flag,
        "overall_status": result.overall_status,
        "action_count": len(result.action_required),
        "actions": "; ".join(result.action_required) if result.action_required else "",
    }
    if RECON_PATH.exists():
        recon_df = pd.read_parquet(RECON_PATH)
    else:
        recon_df = pd.DataFrame()
    if not recon_df.empty and "date" in recon_df.columns:
        recon_df["date"] = pd.to_datetime(recon_df["date"], errors="coerce")
        target_date = pd.Timestamp(result.date).normalize()
        recon_df = recon_df[recon_df["date"].dt.normalize() != target_date]
    recon_df = pd.concat([recon_df, pd.DataFrame([row])], ignore_index=True)
    recon_df = recon_df.sort_values("date").reset_index(drop=True)
    RECON_PATH.parent.mkdir(parents=True, exist_ok=True)
    recon_df.to_parquet(RECON_PATH, index=False)
    return result


def _update_runtime_db_controls(report: AccountingRefreshReport, runtime_payload: Dict[str, Any], total_value: float) -> tuple[bool, str]:
    try:
        store = RuntimeEventStore(str(RUNTIME_DB_PATH), writer_name="runtime_accounting_refresh")
    except Exception as exc:
        return False, str(exc)

    try:
        store.set_runtime_control_json(
            "accounting_refresh_status",
            {
                "timestamp": report.timestamp,
                "status": report.status,
                "ledger_rows": report.ledger_rows,
                "nav_rows": report.nav_rows,
                "reconciliation_status": report.reconciliation_status,
            },
        )
        store.set_runtime_control_json(
            "options_runtime_snapshot",
            {
                "timestamp": runtime_payload.get("timestamp"),
                "current_mode": runtime_payload.get("current_mode"),
                "open_position_count": len(runtime_payload.get("open_positions", []) or []),
                "unrealized_pnl": _safe_float(runtime_payload.get("unrealized_pnl"), 0.0),
                "net_equity": _safe_float(runtime_payload.get("net_equity"), 0.0),
            },
        )
        store.set_runtime_control_json(
            "core_equity_snapshot",
            {
                "timestamp": report.timestamp,
                "total_value": float(total_value),
                "position_count": len((_safe_json(CURRENT_POSITIONS_PATH).get("positions") or {})),
            },
        )
    finally:
        store.close()
    return True, ""


def refresh_runtime_accounting() -> AccountingRefreshReport:
    config = _load_config()
    nav_cfg = _nav_config(config)
    starting_capital = _safe_float(nav_cfg.get("starting_capital_inr"), 10_000_000.0)
    inception_date = str(nav_cfg.get("inception_date", "2024-09-01"))

    runtime_payload = _safe_json(RUNTIME_STATE_PATH)
    backfill_report = _sync_trade_ledger_from_runtime(runtime_payload)

    existing = pd.read_parquet(MASTER_LEDGER_PATH) if MASTER_LEDGER_PATH.exists() else pd.DataFrame()
    preserved = _strip_regenerated_rows(existing)

    cash_seed_rows = _build_cash_seed_rows(config, preserved)
    equity_rows = cash_seed_rows + _build_equity_rows(config) + _build_runtime_equity_trade_rows()
    options_rows = _build_options_rows(runtime_payload)
    latest_reference = _load_runtime_timestamp(runtime_payload)
    if latest_reference is None:
        latest_reference = _now_utc()
    shadow_rows = _build_shadow_rows(config, latest_reference)

    combined = _write_master_ledger(preserved, equity_rows + options_rows + shadow_rows)
    nav_df = _write_nav_history(config)
    recon = _write_reconciliation(config)

    total_value = _canonical_total_value(starting_capital)
    report = AccountingRefreshReport(
        status="ok",
        timestamp=_now_utc().isoformat(),
        starting_capital_inr=starting_capital,
        inception_date=inception_date,
        equity_rows=len(equity_rows),
        options_rows=len(options_rows),
        shadow_rows=len(shadow_rows),
        ledger_rows=len(combined),
        nav_rows=len(nav_df),
        latest_nav_date=str(nav_df["date"].iloc[-1]) if not nav_df.empty and "date" in nav_df.columns else None,
        reconciliation_status=recon.overall_status,
        reconciliation_date=recon.date.isoformat() if recon.date is not None else None,
        trade_ledger_rows=len(pd.read_parquet(TRADE_LEDGER_PATH)) if TRADE_LEDGER_PATH.exists() else 0,
        trade_ledger_backfilled_open=int(backfill_report.get("open_entries", 0)),
        trade_ledger_backfilled_close=int(backfill_report.get("close_entries", 0)),
        runtime_db_control_updated=False,
        runtime_db_control_error="",
    )
    updated, error = _update_runtime_db_controls(report, runtime_payload, total_value)
    report.runtime_db_control_updated = bool(updated)
    report.runtime_db_control_error = str(error or "")

    ACCOUNTING_SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACCOUNTING_SNAPSHOT_PATH.write_text(
        json.dumps(
            {
                "timestamp": report.timestamp,
                "status": report.status,
                "equity_book": {
                    "total_value": float(total_value),
                    "positions": len((_safe_json(CURRENT_POSITIONS_PATH).get("positions") or {})),
                },
                "options_book": {
                    "current_mode": runtime_payload.get("current_mode"),
                    "open_positions": len(runtime_payload.get("open_positions", []) or []),
                    "unrealized_pnl": _safe_float(runtime_payload.get("unrealized_pnl"), 0.0),
                    "net_equity": _safe_float(runtime_payload.get("net_equity"), 0.0),
                },
                "shadow_book": {
                    "rows_materialized": int(len(shadow_rows)),
                },
                "artifacts": {
                    "master_ledger": str(MASTER_LEDGER_PATH),
                    "nav_history": str(NAV_HISTORY_PATH),
                    "reconciliation_log": str(RECON_PATH),
                    "trade_ledger": str(TRADE_LEDGER_PATH),
                },
                "report": asdict(report),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    return report
