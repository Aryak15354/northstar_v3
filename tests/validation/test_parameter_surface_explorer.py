from __future__ import annotations

from typing import Any, Dict, List

from src.research.alpha_lab import ParameterSurfaceExplorer


def _row(
    parameter_hash: str,
    params: Dict[str, Any],
    train_sharpe: float,
    test_sharpe: float,
    regime_bull: float,
    regime_bear: float,
) -> Dict[str, Any]:
    fold_rows: List[Dict[str, Any]] = [
        {"fold_id": 0, "test_sharpe": test_sharpe - 0.05, "train_sharpe": train_sharpe - 0.03},
        {"fold_id": 1, "test_sharpe": test_sharpe + 0.02, "train_sharpe": train_sharpe + 0.01},
        {"fold_id": 2, "test_sharpe": test_sharpe + 0.01, "train_sharpe": train_sharpe + 0.02},
    ]
    return {
        "parameter_hash": parameter_hash,
        "params": dict(params),
        "aggregate_metrics": {
            "avg_sharpe": train_sharpe,
            "regime_sharpes": {"bull": regime_bull, "bear": regime_bear},
            "regime_probabilities": {"bull": 0.6, "bear": 0.4},
        },
        "fold_rows": fold_rows,
    }


def test_parameter_surface_explorer_rejects_spiky_point_and_keeps_plateau():
    explorer = ParameterSurfaceExplorer()

    rows = [
        _row("a00", {"lookback": 20, "holding": 5}, 0.95, 0.90, 0.90, 0.86),
        _row("a01", {"lookback": 20, "holding": 10}, 0.98, 0.93, 0.94, 0.90),
        _row("a02", {"lookback": 20, "holding": 20}, 0.96, 0.91, 0.91, 0.89),
        _row("a10", {"lookback": 40, "holding": 5}, 0.99, 0.94, 0.95, 0.90),
        _row("a11", {"lookback": 40, "holding": 10}, 1.04, 0.97, 0.99, 0.95),
        _row("a12", {"lookback": 40, "holding": 20}, 1.00, 0.95, 0.95, 0.92),
        _row("a20", {"lookback": 60, "holding": 5}, 0.98, 0.92, 0.92, 0.88),
        _row("a21", {"lookback": 60, "holding": 10}, 1.02, 0.96, 0.98, 0.92),
        _row("a22", {"lookback": 60, "holding": 20}, 2.10, 1.95, 2.60, 0.20),
    ]

    out = explorer.evaluate(
        rows,
        parameter_grid={
            "lookback": [20, 40, 60],
            "holding": [5, 10, 20],
        },
    )
    by_hash = {r.parameter_hash: r for r in out}

    assert by_hash["a11"].status == "candidate"
    assert by_hash["a11"].plateau_width >= 3
    assert by_hash["a11"].regime_tag in {"core", "conditional"}
    assert by_hash["a22"].status == "reject"
    assert by_hash["a22"].reject_reason != "candidate"


def test_parameter_surface_explorer_bayesian_shrink_and_noise_metrics_present():
    explorer = ParameterSurfaceExplorer()
    rows = [
        _row("p1", {"lookback": 20}, 1.2, 1.0, 1.1, 0.9),
        _row("p2", {"lookback": 40}, 0.9, 0.85, 0.88, 0.82),
    ]
    out = explorer.evaluate(rows, parameter_grid={"lookback": [20, 40]})
    assert len(out) == 2
    for point in out:
        assert point.shrunk_train_sharpe <= 1.2
        assert point.noise_robustness_score >= 0.0
        assert point.perturbation_drop >= 0.0
