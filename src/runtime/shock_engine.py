"""Options/equity shock engine for stress matrix generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .contracts import StressScenarioResult


@dataclass(frozen=True)
class ShockEngineConfig:
    vol_spike_sigma: float = 2.0
    underlying_gap_down_pct: float = -0.05
    correlation_spike_factor: float = 1.35
    vol_crush_pct: float = -0.20


class OptionsShockEngine:
    """Computes deterministic portfolio stress scenarios per event."""

    def __init__(self, config: ShockEngineConfig | None = None):
        self.config = config or ShockEngineConfig()

    def compute_stress_matrix(
        self,
        portfolio_snapshot: Dict[str, float],
        risk_snapshot: Dict[str, float] | None = None,
    ) -> List[StressScenarioResult]:
        rs = dict(risk_snapshot or {})

        equity = float(portfolio_snapshot.get("net_liquidation_value", 0.0) or 0.0)
        delta = float(portfolio_snapshot.get("net_delta", 0.0) or 0.0)
        gamma = float(portfolio_snapshot.get("net_gamma", 0.0) or 0.0)
        vega = float(portfolio_snapshot.get("net_vega", 0.0) or 0.0)
        theta = float(portfolio_snapshot.get("net_theta", 0.0) or 0.0)
        gross = float(portfolio_snapshot.get("gross_exposure", 0.0) or 0.0)
        corr = float(rs.get("correlation", 0.5) or 0.5)

        vol_sigma = float(rs.get("vol_sigma", 0.20) or 0.20)
        vol_shock = float(self.config.vol_spike_sigma) * vol_sigma
        gap = float(self.config.underlying_gap_down_pct)
        corr_jump = max(0.0, float(self.config.correlation_spike_factor) - 1.0)
        vol_crush = float(self.config.vol_crush_pct)

        s1 = (vega * vol_shock) + (0.5 * theta)
        s2 = (delta * gap) + (0.5 * gamma * (gap ** 2))
        s3 = -(gross * corr_jump * max(0.0, corr))
        s4 = (vega * vol_crush) + theta

        def _risk_metric(pnl: float) -> float:
            if equity <= 0.0:
                return 0.0
            return abs(float(pnl)) / equity

        return [
            StressScenarioResult(
                scenario_id="VOL_SPIKE_2SIGMA",
                pnl_impact=float(s1),
                risk_metric=_risk_metric(s1),
                payload={"vol_sigma": vol_sigma, "vol_shock": vol_shock},
            ),
            StressScenarioResult(
                scenario_id="UNDERLYING_GAP_DOWN_5PCT",
                pnl_impact=float(s2),
                risk_metric=_risk_metric(s2),
                payload={"underlying_gap_pct": gap},
            ),
            StressScenarioResult(
                scenario_id="CORRELATION_SPIKE",
                pnl_impact=float(s3),
                risk_metric=_risk_metric(s3),
                payload={"correlation": corr, "correlation_spike_factor": self.config.correlation_spike_factor},
            ),
            StressScenarioResult(
                scenario_id="POST_EVENT_VOL_CRUSH",
                pnl_impact=float(s4),
                risk_metric=_risk_metric(s4),
                payload={"vol_crush_pct": vol_crush},
            ),
        ]
