"""Stateless deterministic rebalance trigger engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .contracts import RebalanceTriggerDecision
from .hash_utils import canonical_hash


@dataclass(frozen=True)
class RebalanceTriggerConfig:
    rules_version: str = "v1"
    regime_delta_threshold: float = 0.20
    vol_percentile_jump_threshold: float = 0.25
    drawdown_threshold: float = 0.08
    correlation_spike_threshold: float = 0.15
    entropy_collapse_threshold: float = 0.40
    risk_budget_breach_threshold: float = 1.0


class RebalanceTriggerEngine:
    """Pure function engine: snapshot + market/risk -> deterministic triggers."""

    def __init__(self, config: RebalanceTriggerConfig | None = None):
        self.config = config or RebalanceTriggerConfig()

    def evaluate(
        self,
        portfolio_snapshot: Dict[str, Any],
        market_snapshot: Dict[str, Any],
        risk_snapshot: Dict[str, Any],
    ) -> List[RebalanceTriggerDecision]:
        payload = {
            "rules_version": self.config.rules_version,
            "portfolio": portfolio_snapshot,
            "market": market_snapshot,
            "risk": risk_snapshot,
        }
        input_hash = canonical_hash(payload)

        regime_delta = abs(
            float(market_snapshot.get("regime_transition_probability", 0.0) or 0.0)
            - float(portfolio_snapshot.get("regime_transition_probability", 0.0) or 0.0)
        )
        vol_jump = abs(float(market_snapshot.get("vol_percentile_jump", 0.0) or 0.0))
        drawdown = abs(float(portfolio_snapshot.get("drawdown_ratio", 0.0) or 0.0))
        corr_spike = abs(float(market_snapshot.get("correlation_spike", 0.0) or 0.0))
        entropy = float(risk_snapshot.get("signal_entropy", 1.0) or 1.0)
        risk_budget_ratio = float(risk_snapshot.get("risk_budget_ratio", 0.0) or 0.0)

        ordered = [
            (
                "rule.regime_shift",
                "rebalance.regime_shift",
                {"regime_delta_threshold": float(self.config.regime_delta_threshold), "regime_delta": regime_delta},
                regime_delta >= float(self.config.regime_delta_threshold),
            ),
            (
                "rule.volatility_shock",
                "rebalance.volatility_shock",
                {"vol_percentile_jump_threshold": float(self.config.vol_percentile_jump_threshold), "vol_jump": vol_jump},
                vol_jump >= float(self.config.vol_percentile_jump_threshold),
            ),
            (
                "rule.drawdown_breach",
                "rebalance.drawdown_breach",
                {"drawdown_threshold": float(self.config.drawdown_threshold), "drawdown": drawdown},
                drawdown >= float(self.config.drawdown_threshold),
            ),
            (
                "rule.correlation_spike",
                "rebalance.correlation_spike",
                {"correlation_spike_threshold": float(self.config.correlation_spike_threshold), "correlation_spike": corr_spike},
                corr_spike >= float(self.config.correlation_spike_threshold),
            ),
            (
                "rule.signal_entropy_collapse",
                "rebalance.signal_entropy_collapse",
                {"entropy_collapse_threshold": float(self.config.entropy_collapse_threshold), "signal_entropy": entropy},
                entropy <= float(self.config.entropy_collapse_threshold),
            ),
            (
                "rule.risk_budget_breach",
                "rebalance.risk_budget_breach",
                {"risk_budget_breach_threshold": float(self.config.risk_budget_breach_threshold), "risk_budget_ratio": risk_budget_ratio},
                risk_budget_ratio >= float(self.config.risk_budget_breach_threshold),
            ),
        ]

        return [
            RebalanceTriggerDecision(
                rule_id=rule_id,
                trigger_reason_code=reason,
                input_hash=input_hash,
                threshold_values=thresholds,
                decision=bool(decision),
            )
            for rule_id, reason, thresholds, decision in ordered
        ]
