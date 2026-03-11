from __future__ import annotations

from src.diagnostics import (
    CapacityCurveOptimizer,
    MonteCarloStabilitySimulator,
    Phase3DeploymentQualifier,
    StructuralQualificationEngine,
)


def _stable_returns(n: int = 320) -> list[float]:
    return [0.003 + (0.0002 if (i % 2 == 0) else -0.0001) for i in range(n)]


def _fragile_returns(n: int = 320) -> list[float]:
    return [-0.003 + (0.0008 if (i % 3 == 0) else -0.0005) for i in range(n)]


def test_capacity_curve_optimizer_finds_viable_capacity():
    optimizer = CapacityCurveOptimizer()
    out = optimizer.optimize(
        _stable_returns(),
        impact_a=0.0001,
        impact_b=0.00002,
        drawdown_limit=0.50,
    )
    assert out.status == "viable"
    assert out.capacity_limit_estimate > 0.0
    assert out.optimal_capital > 0.0


def test_monte_carlo_stability_rejects_fragile_path():
    mc = MonteCarloStabilitySimulator(
        n_sim=300,
        random_seed=7,
    )
    out = mc.qualify(_fragile_returns())
    assert out.status == "reject"
    assert out.p_sharpe_negative > 0.30


def test_structural_qualification_rejects_fragile_path():
    det = StructuralQualificationEngine()
    out = det.qualify(
        _fragile_returns(),
        portfolio_returns=[0.0] * 320,
    )
    assert out.status == "reject"
    assert (not out.cost_ok) or (not out.capacity_ok) or (not out.stress_ok)


def test_phase3_qualifier_approves_with_relaxed_thresholds():
    det = StructuralQualificationEngine(
        min_cost_ratio=-1.0,
        min_capacity_ratio=-1.0,
        min_marginal_sharpe_delta=-1.0,
        min_decay_slope=-1.0,
        max_stress_drawdown=1.0,
        cost_impact_a=0.0,
        cost_impact_b=0.0,
    )
    mc = MonteCarloStabilitySimulator(
        n_sim=200,
        max_p_sharpe_negative=1.0,
        max_p_dd_gt_40=1.0,
        min_sharpe_p05=-1.0,
        random_seed=3,
    )
    qualifier = Phase3DeploymentQualifier(
        deterministic_engine=det,
        monte_carlo_engine=mc,
    )
    out = qualifier.qualify_alpha(
        alpha_id="alpha_phase3",
        returns=_stable_returns(),
        portfolio_returns=[],
    )
    assert out.phase3_status == "approved"
    assert out.deterministic.status == "deployable"
    assert out.monte_carlo.status == "stable"
