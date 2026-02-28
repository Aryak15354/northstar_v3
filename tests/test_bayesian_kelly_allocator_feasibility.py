from __future__ import annotations

from src.intelligence.bayesian_kelly_allocator import BayesianKellyAllocator


def _posteriors():
    return {
        "short_vol": {
            "posterior_mean": 0.12,
            "posterior_variance": 0.20,
            "volatility": 0.40,
            "adjusted_sharpe": 0.5,
            "credibility": 0.6,
            "crowding_penalty": 0.4,
            "convexity_penalty": 0.5,
            "liquidity_score": 0.8,
            "convexity_score": 0.9,
        },
        "long_vol": {
            "posterior_mean": 0.04,
            "posterior_variance": 0.10,
            "volatility": 0.35,
            "adjusted_sharpe": 0.2,
            "credibility": 0.5,
            "crowding_penalty": 0.8,
            "convexity_penalty": 0.9,
            "liquidity_score": 0.6,
            "convexity_score": 0.4,
        },
    }


def test_allocator_returns_valid_output_under_stressed_constraints() -> None:
    allocator = BayesianKellyAllocator()
    result = allocator.allocate(
        regime_probs={"LOW_VOL": 0.2, "HIGH_VOL": 0.2, "CRISIS": 0.5, "TRANSITION": 0.1},
        strategy_posteriors=_posteriors(),
        current_drawdown=0.12,
        model_confidence=0.30,
        hard_limits={"gross_cap": 0.4, "net_cap": 0.15},
        soft_limits={
            "cvar_target": 0.0001,
            "vol_target": 0.0001,
            "drawdown_probability_max": 0.01,
            "liquidity_penalty_max": 0.01,
            "convexity_preference_max": 0.01,
        },
    )
    weights = result["weights"]
    assert isinstance(weights, dict)
    assert set(weights.keys()) == {"short_vol", "long_vol"}
    gross = sum(abs(v) for v in weights.values())
    assert gross <= 0.4 + 1e-8
    assert "reason_codes" in result


def test_allocator_respects_hard_veto() -> None:
    allocator = BayesianKellyAllocator()
    result = allocator.allocate(
        regime_probs={"LOW_VOL": 0.5, "HIGH_VOL": 0.2, "CRISIS": 0.1, "TRANSITION": 0.2},
        strategy_posteriors=_posteriors(),
        risk_veto_active=True,
        veto_reasons=["test_veto"],
    )
    assert all(abs(v) <= 1e-12 for v in result["weights"].values())
    assert "hard_risk_veto_active" in result["reason_codes"]
