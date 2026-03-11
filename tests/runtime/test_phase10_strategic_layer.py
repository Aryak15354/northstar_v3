from __future__ import annotations

from datetime import datetime, timezone

from src.strategic import (
    ArchitectureOptimizer,
    ObjectiveReweighter,
    ReflexivityModel,
    StrategicRegimeEngine,
    SystemRegretAggregator,
)
from src.strategic.architecture_policy_store import ArchitecturePolicyStore


def _bounds() -> dict[str, tuple[float, float]]:
    return {
        "convex_risk_aversion": (0.8, 5.0),
        "phase8_redundancy_penalty_eta": (0.0, 0.45),
        "phase8_diversity_reward_delta": (0.0, 0.25),
        "phase4_cluster_cap": (0.35, 0.80),
        "phase4_leverage_limit": (0.70, 1.40),
        "kelly_alpha": (0.05, 0.70),
        "phase5_allocation_inertia": (0.05, 0.95),
        "phase10_exploration_rate": (0.03, 0.45),
        "phase10_mortality_sensitivity": (0.25, 3.0),
    }


def test_phase10_regret_reweight_reflexivity_outputs_bounded():
    regret = SystemRegretAggregator().compute(
        alpha_regrets={"a": 0.3, "b": 0.6},
        portfolio_metrics={"p_maxdd_breach": 0.25, "eigen_spike": 1.4, "structural_fragility_index": 1.2},
        research_metrics={"durability_collapse": 0.3, "compute_misallocation": 0.2, "exploration_gap": 0.1},
    )
    rw = ObjectiveReweighter().reweight(
        system_stability_index=regret.system_stability_index,
        regime_entropy=0.6,
        capital_scale=0.3,
    )
    rx = ReflexivityModel().evaluate(
        capital_scale=0.35,
        base_decay=0.02,
        mortality_sensitivity=1.2,
    )

    assert 0.0 <= regret.system_regret <= 1.0
    assert 0.0 <= regret.system_stability_index <= 1.0
    assert 0.4 <= rw.lambda_return <= 1.3
    assert 0.6 <= rw.strategic_multiplier <= 1.25
    assert 0.0 <= rx.decay_lambda
    assert 0.55 <= rx.reflexivity_multiplier <= 1.0


def test_phase10_architecture_optimizer_runs_and_cadence_gate(tmp_path):
    store = ArchitecturePolicyStore(policy_path=str(tmp_path / "architecture_policy.json"))
    opt = ArchitectureOptimizer(
        bounds=_bounds(),
        policy_store=store,
        cadence_days=30,
        min_history_points=1,
        inertia=0.0,
        max_step_fraction=0.10,
    )

    ctx = {
        "expected_return": 0.15,
        "volatility": 0.12,
        "cvar_95": -0.09,
        "structural_fragility_index": 0.8,
        "eigen_spike": 1.2,
        "survival_probability": 0.85,
        "system_regret": 0.25,
        "system_stability_index": 0.75,
        "research_gap": 0.18,
        "capital_scale": 0.40,
    }

    out1 = opt.run_cycle(context=ctx, history_points=10)
    assert set(out1.theta.keys()) == set(ArchitectureOptimizer.PARAM_ORDER)
    diagnostics = dict(out1.diagnostics or {})
    assert "regime_probs" in diagnostics
    assert "strategic_regime" in diagnostics
    assert "gradient_alignment" in diagnostics
    assert "lipschitz_constant" in diagnostics
    assert "eta_bound" in diagnostics
    assert "eta_applied" in diagnostics

    # Force cadence lock and verify no update.
    opt._last_update_date = datetime.now(timezone.utc).isoformat()  # noqa: SLF001
    out2 = opt.run_cycle(context=ctx, history_points=10)
    assert out2.updated is False
    assert out2.cadence_ready is False
    lock_diag = dict(out2.diagnostics or {})
    assert "regime_probs" in lock_diag
    assert "strategic_regime" in lock_diag


def test_strategic_regime_engine_probabilities_and_smoothing():
    engine = StrategicRegimeEngine(smoothing_alpha=0.2)
    growth_state = {
        "system_regret": 0.05,
        "stability_index": 0.95,
        "structural_fragility": 0.05,
        "eigen_spike": 1.02,
        "research_gap": 0.05,
        "capital_scale": 0.40,
    }
    stability_state = {
        "system_regret": 0.80,
        "stability_index": 0.10,
        "structural_fragility": 0.90,
        "eigen_spike": 2.00,
        "research_gap": 0.10,
        "capital_scale": 0.90,
    }

    first = engine.infer(state=growth_state, update_state=True)
    second = engine.infer(state=stability_state, update_state=True)
    third = engine.infer(state=stability_state, update_state=False)

    assert first.dominant_regime == "growth"
    assert second.dominant_regime == "stability"
    assert abs(sum(first.probabilities.values()) - 1.0) < 1e-6
    assert abs(sum(second.probabilities.values()) - 1.0) < 1e-6
    assert second.probabilities["stability"] < second.raw_probabilities["stability"]
    assert third.probabilities == second.probabilities
