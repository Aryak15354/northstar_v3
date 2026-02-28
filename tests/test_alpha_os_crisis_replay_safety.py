from __future__ import annotations

from src.intelligence.bayesian_kelly_allocator import BayesianKellyAllocator
from src.risk.stress_scenario_engine import StressScenarioEngine


def test_crisis_stress_path_keeps_cycle_feasible_and_respects_veto() -> None:
    stress = StressScenarioEngine()
    stress_out = stress.evaluate(
        delta=10000.0,
        gamma=5000.0,
        vega=8000.0,
        theta=-200.0,
        portfolio_value=100000.0,
        spot_sigma=0.25,
    )
    assert stress_out["gap_risk_score"] >= 0.0
    assert isinstance(stress_out["scenarios"], list)

    allocator = BayesianKellyAllocator()
    result = allocator.allocate(
        regime_probs={"LOW_VOL": 0.0, "HIGH_VOL": 0.1, "CRISIS": 0.8, "TRANSITION": 0.1},
        strategy_posteriors={
            "short_vol": {
                "posterior_mean": 0.05,
                "posterior_variance": 0.15,
                "volatility": 0.50,
                "credibility": 0.6,
            }
        },
        risk_veto_active=True,
        veto_reasons=["crisis_replay_veto"],
    )
    assert all(abs(v) <= 1e-12 for v in result["weights"].values())
    assert "hard_risk_veto_active" in result["reason_codes"]
