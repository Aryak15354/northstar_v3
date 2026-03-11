from __future__ import annotations

from src.portfolio import ConvexPortfolioAllocator, PortfolioMonteCarloSimulator
from src.runtime.adaptive_capital_engine import AdaptiveCapitalEngine


def _covariance() -> dict[str, dict[str, float]]:
    return {
        "a": {"a": 0.020, "b": 0.010, "c": 0.004, "d": 0.003},
        "b": {"a": 0.010, "b": 0.025, "c": 0.005, "d": 0.004},
        "c": {"a": 0.004, "b": 0.005, "c": 0.018, "d": 0.009},
        "d": {"a": 0.003, "b": 0.004, "c": 0.009, "d": 0.022},
    }


def test_phase4_convex_allocator_enforces_cluster_and_leverage_caps():
    allocator = ConvexPortfolioAllocator()
    out = allocator.optimize(
        strategy_ids=["a", "b", "c", "d"],
        expected_edges={"a": 0.12, "b": 0.11, "c": 0.09, "d": 0.08},
        covariance=_covariance(),
        capacity_caps={"a": 0.70, "b": 0.70, "c": 0.70, "d": 0.70},
        cluster_map={"a": "mom", "b": "mom", "c": "mr", "d": "mr"},
        leverage_limit=1.0,
        cluster_cap=0.55,
        correlation_threshold=0.95,
    )
    assert out.constraints_ok
    assert out.leverage <= 1.0 + 1e-6
    assert all(v <= 0.70 + 1e-6 for v in out.weights.values())
    assert all(v <= 0.55 + 1e-6 for v in out.cluster_exposure.values())
    assert float(out.metadata.get("eigen_ratio_base", 0.0)) > 0.0
    assert float(out.metadata.get("eigen_ratio_crisis", 0.0)) > 0.0


def test_phase4_convex_allocator_respects_turnover_budget():
    allocator = ConvexPortfolioAllocator()
    out = allocator.optimize(
        strategy_ids=["a", "b", "c", "d"],
        expected_edges={"a": 0.20, "b": 0.10, "c": 0.05, "d": 0.03},
        covariance=_covariance(),
        capacity_caps={"a": 0.70, "b": 0.70, "c": 0.70, "d": 0.70},
        cluster_map={"a": "mom", "b": "mom", "c": "mr", "d": "mr"},
        current_weights={"a": 0.25, "b": 0.25, "c": 0.25, "d": 0.25},
        max_turnover=0.10,
        leverage_limit=1.0,
        cluster_cap=0.70,
        correlation_threshold=0.99,
    )
    assert float(out.metadata.get("turnover", 0.0)) <= 0.10 + 1e-6


def test_phase4_portfolio_mc_returns_stability_metrics():
    mc = PortfolioMonteCarloSimulator(
        n_paths=200,
        horizon_days=20,
    )
    series = {
        "a": [0.002 + (0.0003 if i % 5 else -0.0015) for i in range(260)],
        "b": [0.0018 + (0.0002 if i % 7 else -0.0012) for i in range(260)],
        "c": [0.0012 + (0.0001 if i % 9 else -0.0010) for i in range(260)],
        "d": [0.0010 + (0.0001 if i % 11 else -0.0009) for i in range(260)],
    }
    out = mc.evaluate(
        strategy_ids=["a", "b", "c", "d"],
        weights={"a": 0.30, "b": 0.30, "c": 0.20, "d": 0.20},
        expected_edges={"a": 0.12, "b": 0.11, "c": 0.09, "d": 0.08},
        return_series_map=series,
        covariance=_covariance(),
        drawdown_breach=0.20,
        max_p_dd_breach=0.40,
        seed_key="test.phase4.mc",
    )
    assert out.n_paths == 200
    assert 0.0 <= out.p_maxdd_breach <= 1.0
    assert 0.0 <= out.p_sharpe_negative <= 1.0
    assert 0.0 < out.stability_multiplier <= 1.0
    assert out.drawdown_cluster_p95 >= 0.0
    assert 0.0 <= out.time_under_water_mean <= 1.0


def test_adaptive_capital_engine_scales_down_under_stress():
    engine = AdaptiveCapitalEngine(
        target_volatility=0.12,
        min_multiplier=0.30,
        max_multiplier=1.20,
    )
    out = engine.scale(
        risk_snapshot={
            "realized_volatility": 0.30,
            "spread_bps": 40.0,
            "estimated_slippage_bps": 35.0,
            "liquidity_factor": 1.8,
        },
        survival_probability=0.35,
        regime_multiplier=0.90,
        estimation_error=1.2,
        live_sharpe=-0.4,
        expected_sharpe=0.2,
        mc_sharpe_std=0.2,
        prior_multiplier=1.1,
        inertia=0.6,
    )
    assert out.final_multiplier < 1.0
    assert out.status == "scaled_down"
    assert out.kelly_estimation_error > 0.0
    assert out.drift_z_score < 0.0
