from __future__ import annotations

from src.manifold import AlphaManifoldBuilder
from src.portfolio import ConvexPortfolioAllocator


def _covariance() -> dict[str, dict[str, float]]:
    return {
        "a": {"a": 0.020, "b": 0.010, "c": 0.004},
        "b": {"a": 0.010, "b": 0.024, "c": 0.006},
        "c": {"a": 0.004, "b": 0.006, "c": 0.018},
    }


def _returns() -> dict[str, list[float]]:
    return {
        "a": [0.002 + (0.0002 if i % 7 else -0.0011) for i in range(220)],
        "b": [0.0018 + (0.0002 if i % 9 else -0.0010) for i in range(220)],
        "c": [0.0011 + (0.0001 if i % 8 else -0.0008) for i in range(220)],
    }


def test_phase8_manifold_builder_emits_structural_snapshot():
    builder = AlphaManifoldBuilder()
    snap = builder.build(
        alpha_ids=["a", "b", "c"],
        expected_edges={"a": 0.11, "b": 0.10, "c": 0.08},
        strategy_points={},
        return_series_map=_returns(),
        capacity_caps={"a": 0.7, "b": 0.7, "c": 0.7},
        factor_exposures={"a": {"beta": 0.4}, "b": {"beta": 0.3}, "c": {"beta": 0.1}},
        weights={"a": 0.4, "b": 0.3, "c": 0.3},
    )

    payload = snap.to_dict()
    assert set(payload.keys()) >= {
        "alpha_ids",
        "distance_matrix",
        "cluster_map",
        "redundancy_scores",
        "diversity_score",
    }
    assert len(payload["alpha_ids"]) == 3
    assert payload["diversity_score"] >= 0.0


def test_phase8_manifold_penalty_reduces_overcrowded_weight():
    allocator = ConvexPortfolioAllocator(iters=120)
    base = allocator.optimize(
        strategy_ids=["a", "b", "c"],
        expected_edges={"a": 0.15, "b": 0.10, "c": 0.09},
        covariance=_covariance(),
        capacity_caps={"a": 0.8, "b": 0.8, "c": 0.8},
        cluster_map={"a": "mom", "b": "mom", "c": "mr"},
        leverage_limit=1.0,
        cluster_cap=0.9,
        correlation_threshold=0.99,
    )
    penalized = allocator.optimize(
        strategy_ids=["a", "b", "c"],
        expected_edges={"a": 0.15, "b": 0.10, "c": 0.09},
        covariance=_covariance(),
        capacity_caps={"a": 0.8, "b": 0.8, "c": 0.8},
        cluster_map={"a": "mom", "b": "mom", "c": "mr"},
        leverage_limit=1.0,
        cluster_cap=0.9,
        correlation_threshold=0.99,
        manifold_redundancy={"a": 3.0, "b": 0.5, "c": 0.5},
        manifold_distance={
            "a": {"a": 0.0, "b": 0.1, "c": 1.2},
            "b": {"a": 0.1, "b": 0.0, "c": 1.0},
            "c": {"a": 1.2, "b": 1.0, "c": 0.0},
        },
        manifold_penalty_eta=0.15,
        manifold_diversity_delta=0.08,
    )

    assert penalized.weights["a"] <= base.weights["a"] + 1e-6
    assert float(penalized.metadata.get("manifold_penalty_eta", 0.0)) > 0.0


def test_phase9_multi_horizon_allocator_returns_aggregate_and_horizon_weights():
    allocator = ConvexPortfolioAllocator(iters=120)
    out = allocator.optimize_multi_horizon(
        strategy_ids=["a", "b", "c"],
        horizons=["1d", "5d", "20d"],
        expected_edges_by_horizon={
            "1d": {"a": 0.12, "b": 0.08, "c": 0.07},
            "5d": {"a": 0.10, "b": 0.09, "c": 0.08},
            "20d": {"a": 0.09, "b": 0.10, "c": 0.09},
        },
        covariance=_covariance(),
        capacity_caps={"a": 0.8, "b": 0.8, "c": 0.8},
        cluster_map={"a": "mom", "b": "mom", "c": "mr"},
        leverage_limit=1.0,
        cluster_cap=0.75,
        cross_horizon_corr=0.4,
        horizon_mix={"1d": 0.3, "5d": 0.4, "20d": 0.3},
    )

    assert out.constraints_ok
    assert set(out.horizon_weights.keys()) == {"1d", "5d", "20d"}
    assert set(out.aggregated_weights.keys()) == {"a", "b", "c"}
    assert out.leverage <= 1.0 + 1e-6
