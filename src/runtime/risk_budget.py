"""Risk budget manager enforcing hard portfolio constraints."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict
from uuid import uuid4

from .contracts import BudgetDecision, CapitalDecision, TradeProposal


@dataclass(frozen=True)
class RiskBudgetConfig:
    gross_cap_ratio: float = 1.20
    net_cap_ratio: float = 0.75
    vol_adjusted_cap_ratio: float = 1.00
    per_strategy_cap_ratio: float = 0.35
    per_origin_cap_ratio: float = 0.60
    sector_caps: Dict[str, float] = field(default_factory=dict)
    stress_loss_cap_ratio: float = 0.25


class RiskBudgetManager:
    """Independent hard-cap checker after capital allocation."""

    def __init__(self, config: RiskBudgetConfig | None = None):
        self.config = config or RiskBudgetConfig(
            sector_caps={
                "financial services": 0.30,
                "information technology": 0.25,
                "healthcare": 0.20,
                "energy": 0.20,
            }
        )

    @staticmethod
    def _trade_sign(proposal: TradeProposal) -> float:
        direction = float(proposal.instrument_plan.get("direction", 1.0) or 1.0)
        side = str(proposal.instrument_plan.get("side", "buy") or "buy").strip().lower()
        if side == "sell":
            return -1.0
        if direction < 0:
            return -1.0
        return 1.0

    def check(
        self,
        capital_decision: CapitalDecision,
        proposal: TradeProposal,
        portfolio_snapshot: Dict[str, Any],
        risk_snapshot: Dict[str, Any] | None = None,
    ) -> BudgetDecision:
        decision_id = f"bud_{uuid4().hex[:16]}"
        if not capital_decision.is_approved:
            return BudgetDecision(
                decision_id=decision_id,
                is_approved=False,
                approved_notional=0.0,
                denial_reason=capital_decision.denial_reason or "capital.reserve_unavailable",
                post_fill_guard_required=True,
            )

        rs = dict(risk_snapshot or {})
        equity = float(portfolio_snapshot.get("net_liquidation_value", 0.0) or 0.0)
        if equity <= 0.0:
            return BudgetDecision(
                decision_id=decision_id,
                is_approved=False,
                approved_notional=0.0,
                denial_reason="risk.net_cap_breach",
                post_fill_guard_required=True,
            )

        approved = float(capital_decision.approved_notional)
        gross = float(portfolio_snapshot.get("gross_exposure", 0.0) or 0.0)
        net = float(portfolio_snapshot.get("net_exposure", 0.0) or 0.0)
        sign = self._trade_sign(proposal)

        projected_gross_ratio = (gross + approved) / equity
        projected_net_ratio = abs(net + sign * approved) / equity
        vol_multiplier = float(rs.get("vol_multiplier", 1.0) or 1.0)
        projected_vol_adj_ratio = projected_gross_ratio * max(1.0, vol_multiplier)

        strategy_usage = dict(rs.get("strategy_exposure", {}) or {})
        origin_usage = dict(rs.get("origin_exposure", {}) or {})
        strategy_ratio = float(strategy_usage.get(proposal.strategy_id, 0.0) or 0.0) + (approved / equity)
        origin_ratio = float(origin_usage.get(proposal.origin.value, 0.0) or 0.0) + (approved / equity)

        sector = str(proposal.instrument_plan.get("sector", "") or "").strip().lower()
        sector_allocation = dict(portfolio_snapshot.get("sector_allocation", {}) or {})
        sector_ratio = float(sector_allocation.get(sector, 0.0) or 0.0) + (approved / equity)
        sector_cap = float(self.config.sector_caps.get(sector, 1.0))

        worst_stress = float(rs.get("worst_case_loss_ratio", 0.0) or 0.0)

        cap_obs = {
            "projected_gross_ratio": projected_gross_ratio,
            "projected_net_ratio": projected_net_ratio,
            "projected_vol_adjusted_ratio": projected_vol_adj_ratio,
            "projected_strategy_ratio": strategy_ratio,
            "projected_origin_ratio": origin_ratio,
            "projected_sector_ratio": sector_ratio,
            "projected_worst_case_loss_ratio": worst_stress,
        }

        if projected_gross_ratio > float(self.config.gross_cap_ratio):
            return BudgetDecision(decision_id, False, 0.0, "risk.gross_cap_breach", cap_obs, True)
        if projected_net_ratio > float(self.config.net_cap_ratio):
            return BudgetDecision(decision_id, False, 0.0, "risk.net_cap_breach", cap_obs, True)
        if projected_vol_adj_ratio > float(self.config.vol_adjusted_cap_ratio):
            return BudgetDecision(decision_id, False, 0.0, "risk.vol_adjusted_cap_breach", cap_obs, True)
        if strategy_ratio > float(self.config.per_strategy_cap_ratio):
            return BudgetDecision(decision_id, False, 0.0, "risk.strategy_cap_breach", cap_obs, True)
        if origin_ratio > float(self.config.per_origin_cap_ratio):
            return BudgetDecision(decision_id, False, 0.0, "risk.origin_cap_breach", cap_obs, True)
        if sector and sector_ratio > sector_cap:
            return BudgetDecision(decision_id, False, 0.0, "risk.sector_cap_breach", cap_obs, True)
        if worst_stress > float(self.config.stress_loss_cap_ratio):
            return BudgetDecision(decision_id, False, 0.0, "risk.stress_cap_breach", cap_obs, True)

        return BudgetDecision(
            decision_id=decision_id,
            is_approved=True,
            approved_notional=approved,
            denial_reason="",
            cap_observations=cap_obs,
            post_fill_guard_required=True,
        )
