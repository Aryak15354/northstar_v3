"""Runtime adapter for option Greeks enrichment prior to PRS execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from src.volatility.greeks_aggregator import GreeksAggregator, Position


@dataclass(frozen=True)
class GreeksEnrichmentResult:
    instrument_plan: Dict[str, Any]
    has_required_greeks: bool
    source: str
    details: Dict[str, Any]


class RuntimeGreeksAdapter:
    """Enrich option instrument plans with explicit per-unit Greeks."""

    REQUIRED_GREEK_FIELDS = (
        "greek_delta_per_unit",
        "greek_gamma_per_unit",
        "greek_vega_per_unit",
        "greek_theta_per_unit",
        "greek_rho_per_unit",
    )

    def __init__(self) -> None:
        self._agg = GreeksAggregator()

    @staticmethod
    def _is_option(plan: Dict[str, Any]) -> bool:
        return str(plan.get("instrument_type", "equity") or "equity").strip().lower() in {"option", "options"}

    @classmethod
    def _has_required_greeks(cls, plan: Dict[str, Any]) -> bool:
        for field in cls.REQUIRED_GREEK_FIELDS:
            try:
                val = float(plan.get(field, 0.0) or 0.0)
            except Exception:
                val = 0.0
            if abs(val) <= 0.0:
                return False
        return True

    @staticmethod
    def _symbol_greeks(
        symbol: str,
        market_snapshot: Dict[str, Any] | None,
        risk_snapshot: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        symbol_u = str(symbol or "").strip().upper()
        for source in (market_snapshot or {}, risk_snapshot or {}):
            if not isinstance(source, dict):
                continue
            for key in ("symbol_greeks", "option_greeks", "greeks_by_symbol"):
                lookup = source.get(key)
                if isinstance(lookup, dict):
                    payload = lookup.get(symbol_u) or lookup.get(symbol_u.lower())
                    if isinstance(payload, dict):
                        return dict(payload)
        return {}

    def _compute_from_contract_context(
        self,
        plan: Dict[str, Any],
        *,
        as_of: datetime,
    ) -> Tuple[Dict[str, float], Dict[str, Any]]:
        required = ("symbol", "option_type", "strike", "expiry", "spot_price", "implied_vol")
        if not all(k in plan for k in required):
            return {}, {"missing_contract_context": [k for k in required if k not in plan]}

        try:
            position = Position(
                position_id=str(plan.get("position_key", "runtime_greeks_context")),
                underlying=str(plan.get("underlying", plan.get("symbol", ""))),
                option_type=str(plan.get("option_type", "call")),
                strike=float(plan.get("strike", 0.0)),
                expiry=datetime.fromisoformat(str(plan.get("expiry"))).date(),
                quantity=1,
                spot_price=float(plan.get("spot_price", 0.0)),
                implied_vol=float(plan.get("implied_vol", 0.0)),
                risk_free_rate=float(plan.get("risk_free_rate", 0.05)),
            )
            greeks = self._agg.compute_position_greeks(position, as_of=as_of)
            return {
                "greek_delta_per_unit": float(greeks.delta),
                "greek_gamma_per_unit": float(greeks.gamma),
                "greek_vega_per_unit": float(greeks.vega),
                "greek_theta_per_unit": float(greeks.theta),
                "greek_rho_per_unit": float(greeks.rho),
            }, {"computed_from_contract_context": True}
        except Exception as exc:
            return {}, {"compute_error": str(exc)}

    def enrich(
        self,
        instrument_plan: Dict[str, Any],
        *,
        market_snapshot: Dict[str, Any] | None = None,
        risk_snapshot: Dict[str, Any] | None = None,
        as_of: datetime | None = None,
    ) -> GreeksEnrichmentResult:
        plan = dict(instrument_plan or {})
        if not self._is_option(plan):
            return GreeksEnrichmentResult(plan, True, "not_option", {})

        if self._has_required_greeks(plan):
            return GreeksEnrichmentResult(plan, True, "already_present", {})

        as_of_ts = as_of or datetime.now(timezone.utc)
        symbol = str(plan.get("symbol", "") or "")
        from_symbol = self._symbol_greeks(symbol, market_snapshot, risk_snapshot)
        if from_symbol:
            for src, dst in (
                ("delta", "greek_delta_per_unit"),
                ("gamma", "greek_gamma_per_unit"),
                ("vega", "greek_vega_per_unit"),
                ("theta", "greek_theta_per_unit"),
                ("rho", "greek_rho_per_unit"),
                ("greek_delta_per_unit", "greek_delta_per_unit"),
                ("greek_gamma_per_unit", "greek_gamma_per_unit"),
                ("greek_vega_per_unit", "greek_vega_per_unit"),
                ("greek_theta_per_unit", "greek_theta_per_unit"),
                ("greek_rho_per_unit", "greek_rho_per_unit"),
            ):
                if src in from_symbol:
                    plan[dst] = float(from_symbol.get(src, 0.0) or 0.0)
            if self._has_required_greeks(plan):
                return GreeksEnrichmentResult(plan, True, "symbol_greeks", {"symbol": symbol})

        computed, details = self._compute_from_contract_context(plan, as_of=as_of_ts)
        if computed:
            plan.update(computed)
            if self._has_required_greeks(plan):
                return GreeksEnrichmentResult(plan, True, "computed", details)

        return GreeksEnrichmentResult(plan, False, "missing", details)
