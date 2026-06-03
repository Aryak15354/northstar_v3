"""Canonical mutable portfolio state owned exclusively by PRS."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from numbers import Integral, Real
from typing import Any, Dict, List

from .contracts import ExecutionEvent, ExecutionEventType, PortfolioStateSnapshot
from .hash_utils import canonical_hash


_MUTATING_EVENT_TYPES = {
    ExecutionEventType.ORDER_PARTIAL,
    ExecutionEventType.ORDER_FILLED,
    ExecutionEventType.RECONCILIATION_APPLIED,
    ExecutionEventType.POSITION_ADJUSTED,
    ExecutionEventType.CORPORATE_ACTION_APPLIED,
    ExecutionEventType.MARK_TO_MARKET,
}

_BROAD_INDEX_UNDERLYINGS = {"NIFTY", "MIDCPNIFTY"}

_STATE_HASH_FIELDS = (
    "cash",
    "net_liquidation_value",
    "gross_exposure",
    "net_exposure",
    "beta",
    "sector_allocation",
    "regime_context",
    "hedging_state",
    "transaction_history",
    "unrealized_pnl",
    "realized_pnl",
    "net_delta",
    "net_gamma",
    "net_vega",
    "net_theta",
    "net_rho",
    "holdings",
    "last_rebalance_reason",
    "source_event_id",
)


def _holding_underlying_symbol(symbol: str) -> str:
    text = str(symbol or "").strip().upper()
    if text.startswith("OPT::"):
        parts = text.split("::")
        if len(parts) >= 2:
            return str(parts[1] or "").strip().upper()
    return text


def _counts_toward_sector_caps(holding: "Holding") -> bool:
    sector = str(getattr(holding, "sector", "") or "").strip()
    if not sector:
        return False
    instrument_type = str(getattr(holding, "instrument_type", "") or "").strip().lower()
    origin = str(getattr(holding, "origin", "") or "").strip().lower()
    underlying = _holding_underlying_symbol(getattr(holding, "symbol", ""))
    if origin == "options_hedge":
        return False
    if instrument_type in {"option", "options"} and underlying in _BROAD_INDEX_UNDERLYINGS:
        return False
    return True


def state_hash_payload(snapshot_like: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build the deterministic payload used for runtime state hashing.

    `timestamp_utc` is intentionally excluded so replaying the same event
    stream later yields the same state hash.
    """
    payload = {key: snapshot_like.get(key) for key in _STATE_HASH_FIELDS}
    payload["sector_allocation"] = dict(payload.get("sector_allocation", {}) or {})
    payload["regime_context"] = dict(payload.get("regime_context", {}) or {})
    payload["hedging_state"] = dict(payload.get("hedging_state", {}) or {})
    payload["transaction_history"] = list(payload.get("transaction_history", []) or [])
    payload["holdings"] = dict(payload.get("holdings", {}) or {})
    payload["last_rebalance_reason"] = str(payload.get("last_rebalance_reason", "") or "")
    payload["source_event_id"] = int(payload.get("source_event_id", 0) or 0)
    return _normalize_hash_value(payload)


def compute_state_hash(snapshot_like: Dict[str, Any]) -> str:
    return canonical_hash(state_hash_payload(snapshot_like))


def _normalize_hash_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _normalize_hash_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_hash_value(v) for v in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        return f"{float(value):.8f}"
    return value


@dataclass
class Holding:
    symbol: str
    instrument_type: str = "equity"
    quantity: float = 0.0
    avg_price: float = 0.0
    last_price: float = 0.0
    sector: str = ""
    strategy_id: str = ""
    origin: str = ""
    greek_delta_per_unit: float = 0.0
    greek_gamma_per_unit: float = 0.0
    greek_vega_per_unit: float = 0.0
    greek_theta_per_unit: float = 0.0
    greek_rho_per_unit: float = 0.0

    def notional(self) -> float:
        return float(self.quantity * self.last_price)


@dataclass
class PortfolioState:
    cash: float
    holdings: Dict[str, Holding] = field(default_factory=dict)
    regime_context: Dict[str, Any] = field(default_factory=dict)
    hedging_state: Dict[str, Any] = field(default_factory=dict)
    transaction_history: List[int] = field(default_factory=list)
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    beta: float = 0.0
    net_delta: float = 0.0
    net_gamma: float = 0.0
    net_vega: float = 0.0
    net_theta: float = 0.0
    net_rho: float = 0.0
    last_rebalance_reason: str = ""
    last_event_id: int = 0

    @classmethod
    def initialize(cls, starting_cash: float) -> "PortfolioState":
        return cls(cash=float(starting_cash))

    @staticmethod
    def _read_float(payload: Dict[str, Any], key: str, default: float) -> float:
        if key not in payload:
            return float(default)
        val = payload.get(key)
        if val is None:
            return float(default)
        try:
            return float(val)
        except Exception:
            return float(default)

    def _apply_trade(self, payload: Dict[str, Any]) -> None:
        symbol = str(payload.get("symbol", "") or "").strip().upper()
        if not symbol:
            return
        side = str(payload.get("side", "buy") or "buy").strip().lower()
        filled_qty = float(payload.get("filled_qty", payload.get("quantity", 0.0)) or 0.0)
        fill_price = float(payload.get("fill_price", payload.get("price", 0.0)) or 0.0)
        if filled_qty <= 0.0 or fill_price <= 0.0:
            return

        sign = -1.0 if side == "sell" else 1.0
        delta_qty = sign * filled_qty

        h = self.holdings.get(symbol) or Holding(symbol=symbol)
        old_qty = float(h.quantity)
        old_avg = float(h.avg_price)

        realized = 0.0
        if old_qty != 0.0 and (old_qty * delta_qty) < 0:
            closing_qty = min(abs(old_qty), abs(delta_qty))
            if old_qty > 0:
                realized += closing_qty * (fill_price - old_avg)
            else:
                realized += closing_qty * (old_avg - fill_price)

        new_qty = old_qty + delta_qty
        if abs(new_qty) < 1e-12:
            h.quantity = 0.0
            h.avg_price = 0.0
        elif old_qty == 0.0 or (old_qty * delta_qty) > 0:
            weighted_notional = (old_avg * abs(old_qty)) + (fill_price * abs(delta_qty))
            h.avg_price = weighted_notional / abs(new_qty)
            h.quantity = new_qty
        else:
            h.quantity = new_qty
            if old_qty * new_qty < 0:
                h.avg_price = fill_price

        mark_price = payload.get("mark_price")
        h.last_price = float(fill_price if mark_price is None else mark_price)
        h.instrument_type = str(payload.get("instrument_type", h.instrument_type) or h.instrument_type).lower()
        h.sector = str(payload.get("sector", h.sector) or h.sector)
        h.strategy_id = str(payload.get("strategy_id", h.strategy_id) or h.strategy_id)
        h.origin = str(payload.get("origin", h.origin) or h.origin)
        h.greek_delta_per_unit = self._read_float(payload, "greek_delta_per_unit", h.greek_delta_per_unit)
        h.greek_gamma_per_unit = self._read_float(payload, "greek_gamma_per_unit", h.greek_gamma_per_unit)
        h.greek_vega_per_unit = self._read_float(payload, "greek_vega_per_unit", h.greek_vega_per_unit)
        h.greek_theta_per_unit = self._read_float(payload, "greek_theta_per_unit", h.greek_theta_per_unit)
        h.greek_rho_per_unit = self._read_float(payload, "greek_rho_per_unit", h.greek_rho_per_unit)
        self.holdings[symbol] = h

        notional = filled_qty * fill_price
        if side == "buy":
            self.cash -= notional
        else:
            self.cash += notional

        self.realized_pnl += realized

    def _apply_reconciliation(self, payload: Dict[str, Any]) -> None:
        cash_adj = float(payload.get("cash_adjustment", 0.0) or 0.0)
        realized_adj = float(payload.get("realized_pnl_adjustment", 0.0) or 0.0)
        self.cash += cash_adj
        self.realized_pnl += realized_adj

    def _apply_corporate_action(self, payload: Dict[str, Any]) -> None:
        action_type = str(payload.get("action_type", "") or "").strip().lower()
        symbol = str(payload.get("symbol", "") or "").strip().upper()
        if not symbol:
            return
        h = self.holdings.get(symbol)
        if h is None:
            return

        if action_type == "split":
            ratio = float(payload.get("split_ratio", 1.0) or 1.0)
            if ratio > 0:
                h.quantity *= ratio
                h.avg_price /= ratio
                h.last_price = float(payload.get("mark_price", h.last_price) or h.last_price)
        elif action_type == "dividend":
            dividend_per_share = float(payload.get("dividend_per_share", 0.0) or 0.0)
            self.cash += h.quantity * dividend_per_share
        elif action_type == "symbol_change":
            new_symbol = str(payload.get("new_symbol", "") or "").strip().upper()
            if new_symbol:
                self.holdings[new_symbol] = Holding(
                    symbol=new_symbol,
                    instrument_type=h.instrument_type,
                    quantity=h.quantity,
                    avg_price=h.avg_price,
                    last_price=h.last_price,
                    sector=h.sector,
                    strategy_id=h.strategy_id,
                    origin=h.origin,
                )
                self.holdings.pop(symbol, None)

    def _apply_mark_to_market(self, payload: Dict[str, Any]) -> None:
        price_map = dict(payload.get("price_map", {}) or {})
        for symbol, mark in price_map.items():
            sym = str(symbol or "").strip().upper()
            if not sym:
                continue
            h = self.holdings.get(sym)
            if h is None:
                continue
            if isinstance(mark, dict):
                if "mark_price" in mark:
                    h.last_price = self._read_float(mark, "mark_price", h.last_price)
                for field in (
                    "greek_delta_per_unit",
                    "greek_gamma_per_unit",
                    "greek_vega_per_unit",
                    "greek_theta_per_unit",
                    "greek_rho_per_unit",
                ):
                    if field in mark:
                        setattr(h, field, self._read_float(mark, field, getattr(h, field)))
            else:
                try:
                    h.last_price = float(mark)
                except Exception:
                    continue

    def _refresh_derived(self) -> None:
        gross = 0.0
        net = 0.0
        sector_notional: Dict[str, float] = {}
        unreal = 0.0

        for symbol, h in list(self.holdings.items()):
            if abs(h.quantity) < 1e-12:
                self.holdings.pop(symbol, None)
                continue
            pos_notional = h.notional()
            gross += abs(pos_notional)
            net += pos_notional
            if _counts_toward_sector_caps(h):
                sector_notional[h.sector] = sector_notional.get(h.sector, 0.0) + abs(pos_notional)
            unreal += h.quantity * (h.last_price - h.avg_price)

        self.unrealized_pnl = unreal

        greeks = {"delta": 0.0, "gamma": 0.0, "vega": 0.0, "theta": 0.0, "rho": 0.0}
        for h in self.holdings.values():
            has_explicit_greeks = any(
                abs(v) > 0.0
                for v in (
                    h.greek_delta_per_unit,
                    h.greek_gamma_per_unit,
                    h.greek_vega_per_unit,
                    h.greek_theta_per_unit,
                    h.greek_rho_per_unit,
                )
            )
            if has_explicit_greeks:
                greeks["delta"] += h.quantity * h.greek_delta_per_unit
                greeks["gamma"] += h.quantity * h.greek_gamma_per_unit
                greeks["vega"] += h.quantity * h.greek_vega_per_unit
                greeks["theta"] += h.quantity * h.greek_theta_per_unit
                greeks["rho"] += h.quantity * h.greek_rho_per_unit
            else:
                instrument_type = str(h.instrument_type or "equity").lower()
                if instrument_type not in {"option", "options"}:
                    # Equity-only fallback where explicit option Greeks are unavailable.
                    greeks["delta"] += h.notional()

        self.net_delta = greeks["delta"]
        self.net_gamma = greeks["gamma"]
        self.net_vega = greeks["vega"]
        self.net_theta = greeks["theta"]
        self.net_rho = greeks["rho"]

    def apply(self, event: ExecutionEvent, event_id: int) -> None:
        self.last_event_id = int(event_id)
        if event.event_type not in _MUTATING_EVENT_TYPES:
            return

        payload = dict(event.payload or {})
        self.regime_context = dict(payload.get("regime_context", self.regime_context) or self.regime_context)
        self.last_rebalance_reason = str(payload.get("rebalance_reason", self.last_rebalance_reason) or self.last_rebalance_reason)
        if "hedging_state" in payload and isinstance(payload["hedging_state"], dict):
            self.hedging_state = dict(payload["hedging_state"])

        if event.event_type in {ExecutionEventType.ORDER_PARTIAL, ExecutionEventType.ORDER_FILLED, ExecutionEventType.POSITION_ADJUSTED}:
            self._apply_trade(payload)
        elif event.event_type == ExecutionEventType.RECONCILIATION_APPLIED:
            self._apply_reconciliation(payload)
        elif event.event_type == ExecutionEventType.CORPORATE_ACTION_APPLIED:
            self._apply_corporate_action(payload)
        elif event.event_type == ExecutionEventType.MARK_TO_MARKET:
            self._apply_mark_to_market(payload)

        self.transaction_history.append(int(event_id))
        self.transaction_history = self.transaction_history[-10000:]
        self._refresh_derived()

    def to_snapshot(self, timestamp: datetime | None = None) -> PortfolioStateSnapshot:
        ts = timestamp or datetime.now(timezone.utc)

        gross = 0.0
        net = 0.0
        sector_notional: Dict[str, float] = {}
        holdings_dict: Dict[str, Dict[str, Any]] = {}
        for symbol, h in sorted(self.holdings.items()):
            notional = h.notional()
            gross += abs(notional)
            net += notional
            if _counts_toward_sector_caps(h):
                sector_notional[h.sector] = sector_notional.get(h.sector, 0.0) + abs(notional)
            holdings_dict[symbol] = {
                "instrument_type": h.instrument_type,
                "quantity": float(h.quantity),
                "avg_price": float(h.avg_price),
                "last_price": float(h.last_price),
                "sector": h.sector,
                "strategy_id": h.strategy_id,
                "origin": h.origin,
                "notional": float(notional),
                "greek_delta_per_unit": float(h.greek_delta_per_unit),
                "greek_gamma_per_unit": float(h.greek_gamma_per_unit),
                "greek_vega_per_unit": float(h.greek_vega_per_unit),
                "greek_theta_per_unit": float(h.greek_theta_per_unit),
                "greek_rho_per_unit": float(h.greek_rho_per_unit),
            }

        net_liq = float(self.cash + net)
        sector_alloc = {}
        if gross > 0:
            sector_alloc = {k: float(v / gross) for k, v in sorted(sector_notional.items())}

        snap_core = {
            "cash": float(self.cash),
            "net_liquidation_value": float(net_liq),
            "gross_exposure": float(gross),
            "net_exposure": float(net),
            "beta": float(self.beta),
            "sector_allocation": sector_alloc,
            "regime_context": dict(self.regime_context),
            "hedging_state": dict(self.hedging_state),
            "transaction_history": list(self.transaction_history),
            "unrealized_pnl": float(self.unrealized_pnl),
            "realized_pnl": float(self.realized_pnl),
            "net_delta": float(self.net_delta),
            "net_gamma": float(self.net_gamma),
            "net_vega": float(self.net_vega),
            "net_theta": float(self.net_theta),
            "net_rho": float(self.net_rho),
            "holdings": holdings_dict,
            "last_rebalance_reason": self.last_rebalance_reason,
            "source_event_id": int(self.last_event_id),
        }
        state_hash = compute_state_hash(snap_core)

        return PortfolioStateSnapshot(
            timestamp_utc=ts,
            cash=float(self.cash),
            net_liquidation_value=float(net_liq),
            gross_exposure=float(gross),
            net_exposure=float(net),
            beta=float(self.beta),
            sector_allocation=sector_alloc,
            regime_context=dict(self.regime_context),
            hedging_state=dict(self.hedging_state),
            transaction_history=list(self.transaction_history),
            unrealized_pnl=float(self.unrealized_pnl),
            realized_pnl=float(self.realized_pnl),
            net_delta=float(self.net_delta),
            net_gamma=float(self.net_gamma),
            net_vega=float(self.net_vega),
            net_theta=float(self.net_theta),
            net_rho=float(self.net_rho),
            holdings=holdings_dict,
            last_rebalance_reason=self.last_rebalance_reason,
            state_hash=state_hash,
            source_event_id=int(self.last_event_id),
        )

    @classmethod
    def from_snapshot(cls, snapshot: Dict[str, Any]) -> "PortfolioState":
        holdings: Dict[str, Holding] = {}
        for symbol, payload in dict(snapshot.get("holdings", {}) or {}).items():
            holdings[str(symbol)] = Holding(
                symbol=str(symbol),
                instrument_type=str(payload.get("instrument_type", "equity") or "equity"),
                quantity=float(payload.get("quantity", 0.0) or 0.0),
                avg_price=float(payload.get("avg_price", 0.0) or 0.0),
                last_price=float(payload.get("last_price", 0.0) or 0.0),
                sector=str(payload.get("sector", "") or ""),
                strategy_id=str(payload.get("strategy_id", "") or ""),
                origin=str(payload.get("origin", "") or ""),
                greek_delta_per_unit=float(payload.get("greek_delta_per_unit", 0.0) or 0.0),
                greek_gamma_per_unit=float(payload.get("greek_gamma_per_unit", 0.0) or 0.0),
                greek_vega_per_unit=float(payload.get("greek_vega_per_unit", 0.0) or 0.0),
                greek_theta_per_unit=float(payload.get("greek_theta_per_unit", 0.0) or 0.0),
                greek_rho_per_unit=float(payload.get("greek_rho_per_unit", 0.0) or 0.0),
            )

        state = cls(
            cash=float(snapshot.get("cash", 0.0) or 0.0),
            holdings=holdings,
            regime_context=dict(snapshot.get("regime_context", {}) or {}),
            hedging_state=dict(snapshot.get("hedging_state", {}) or {}),
            transaction_history=list(snapshot.get("transaction_history", []) or []),
            realized_pnl=float(snapshot.get("realized_pnl", 0.0) or 0.0),
            unrealized_pnl=float(snapshot.get("unrealized_pnl", 0.0) or 0.0),
            beta=float(snapshot.get("beta", 0.0) or 0.0),
            net_delta=float(snapshot.get("net_delta", 0.0) or 0.0),
            net_gamma=float(snapshot.get("net_gamma", 0.0) or 0.0),
            net_vega=float(snapshot.get("net_vega", 0.0) or 0.0),
            net_theta=float(snapshot.get("net_theta", 0.0) or 0.0),
            net_rho=float(snapshot.get("net_rho", 0.0) or 0.0),
            last_rebalance_reason=str(snapshot.get("last_rebalance_reason", "") or ""),
            last_event_id=int(snapshot.get("source_event_id", 0) or 0),
        )
        state._refresh_derived()
        return state
