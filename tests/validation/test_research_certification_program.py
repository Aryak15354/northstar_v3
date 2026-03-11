from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from src.research.certification import CertificationContext, CertificationEvaluator
from src.research.research_controller import ResearchController


def _mk_evaluator(tmp_path) -> CertificationEvaluator:
    cfg = {
        "random_state": 7,
        "training": {"max_windows": 8},
        "certification": {
            "state_path": str(tmp_path / "cert_state.json"),
            "max_pairwise_corr": 0.99,
            "max_holdings_overlap": 0.95,
            "overlap_persistence_threshold": 0.70,
            "turnover_zero_streak_limit": 3,
            "turnover_min_rebalances": 10,
            "min_trials_weekday": 12,
            "min_trials_weekend": 20,
            "max_family_weight_hard": 0.45,
            "max_family_weight_soft": 0.35,
            "corr_drift_hard": 0.10,
            "min_family_entropy": 0.55,
            "regime_multipliers": {"LOW_VOL": 1.05, "NORMAL": 1.0, "CRISIS": 0.70},
        },
    }
    return CertificationEvaluator(project_root=tmp_path, config=cfg)


def _mk_base_context(tmp_path) -> CertificationContext:
    rng = np.random.RandomState(7)
    dates = pd.date_range("2024-01-01", periods=180, freq="B")
    rets = rng.normal(loc=0.0015, scale=0.01, size=len(dates))
    series_rows = [{"date": d.isoformat(), "return": float(r)} for d, r in zip(dates, rets)]
    snaps = []
    for i, d in enumerate(dates[::5]):
        tickers = [f"T{j}" for j in range(20)]
        w = {tk: float((j + 1) / 210.0) for j, tk in enumerate(tickers)}
        snaps.append(
            {
                "date": d.isoformat(),
                "tickers": tickers,
                "weights": w,
                "gross_exposure": 1.0 + (0.01 if i % 2 else 0.0),
                "turnover": 0.15 + (0.01 * (i % 3)),
                "transaction_cost": 0.0005,
            }
        )
    best_payload = {
        "aggregate_metrics": {
            "windows": 8,
            "avg_turnover": 0.16,
            "avg_rebalance_count": 20,
            "avg_txn_cost_per_rebalance": 0.0005,
        },
        "windows": [
            {
                "train_end": "2024-06-01",
                "test_start": "2024-06-02",
            },
            {
                "train_end": "2024-09-01",
                "test_start": "2024-09-02",
            },
        ],
        "regime_metrics": {
            "LOW_VOL": {"avg_sharpe": 1.4},
            "NORMAL": {"avg_sharpe": 1.1},
            "CRISIS": {"avg_sharpe": 0.6},
        },
        "portfolio_return_series": series_rows,
        "rebalance_snapshots": snaps,
    }
    model_results = {"lightgbm": dict(best_payload)}
    dataset_frame = pd.DataFrame(
        {
            "date": np.repeat(dates, 2),
            "ticker": ["AAA", "BBB"] * len(dates),
            "regime": np.where(np.arange(len(dates) * 2) % 3 == 0, "LOW_VOL", np.where(np.arange(len(dates) * 2) % 3 == 1, "NORMAL", "CRISIS")),
        }
    )
    outputs = [
        {
            "type": "alpha_factory",
            "data": {
                "blend_weights": {"momentum": 0.34, "quality": 0.33, "volatility": 0.33},
                "monitoring": {"correlation_drift": {"mean_abs_corr_shift": 0.03}},
            },
        },
        {
            "type": "regime_transition_analysis",
            "data": {"latest_regime_probabilities": {"LOW_VOL": 0.5, "NORMAL": 0.3, "CRISIS": 0.2}},
        },
    ]
    param_payload = {
        "mode": "bayesian_hyperopt",
        "optimization": {
            "history": [
                {"objective": float(1.0 + i * 0.1), "params": {"lr": 0.01 + (i * 0.001), "depth": 4 + (i % 2)}}
                for i in range(12)
            ]
        },
    }
    meta = {
        "universe_hash": "u",
        "price_hash": "p",
        "feature_hash": "f",
        "label_hash": "l",
        "membership_drift_rate": 0.10,
        "delisted_assets_handled": 1.0,
        "forward_inclusion_check": True,
    }
    now = datetime.now(timezone.utc)
    return CertificationContext(
        outputs=outputs,
        model_results=model_results,
        best_model="lightgbm",
        best_payload=best_payload,
        param_payload=param_payload,
        cap_metrics={},
        dataset_metadata=meta,
        dataset_frame=dataset_frame,
        portfolio_cfg={"transaction_cost_bps_per_side": 5.0},
        freeze_active=False,
        weekend_run=False,
        started_at=now - timedelta(minutes=2),
        completed_at=now,
        system_state={"cycle_id": "cycle_001"},
    )


def test_certification_emits_required_blocks(tmp_path):
    evaluator = _mk_evaluator(tmp_path)
    ctx = _mk_base_context(tmp_path)
    out = evaluator.evaluate(ctx)
    required = {
        "integrity_summary",
        "data_provenance",
        "replay_certification",
        "universe_integrity",
        "strategy_correlation_check",
        "portfolio_integrity",
        "blend_integrity",
        "regime_effectiveness",
        "objective_surface_sanity",
        "statistical_robustness",
        "capital_scaling_gate",
        "time_aggregation_check",
        "confidence_score",
        "model_risk_tier",
        "dependency_lock",
        "resource_guard",
        "formula_lineage",
        "macro_unit_integrity",
        "belief_layer_diagnostics",
        "gate_overfitting_audit",
        "certification_timing",
    }
    assert required.issubset(set(out.keys()))
    assert isinstance(out["integrity_summary"]["critical_failures"], list)
    timing = out.get("certification_timing", {})
    assert "certification_runtime_share" in timing
    assert "max_certification_runtime_share" in timing


def test_strategy_duplication_gate_detects_clones(tmp_path):
    evaluator = _mk_evaluator(tmp_path)
    dates = pd.date_range("2025-01-01", periods=80, freq="B")
    rows = [{"date": d.isoformat(), "return": 0.001 + (i % 5) * 0.0001} for i, d in enumerate(dates)]
    snaps = [
        {
            "date": d.isoformat(),
            "tickers": [f"T{k}" for k in range(10)],
            "weights": {f"T{k}": 0.1 for k in range(10)},
            "gross_exposure": 1.0,
            "turnover": 0.2,
            "transaction_cost": 0.0002,
        }
        for d in dates[::5]
    ]
    model_results = {
        "mom_6m": {"portfolio_return_series": rows, "rebalance_snapshots": snaps},
        "mom_12m": {"portfolio_return_series": rows, "rebalance_snapshots": snaps},
    }
    gate = evaluator._strategy_correlation_check(model_results)
    assert gate["passed"] is False
    assert gate["max_pairwise_corr"] >= 0.99
    assert len(gate["duplicated_strategies"]) >= 1


def test_turnover_zero_streak_fails_after_three_cycles(tmp_path):
    evaluator = _mk_evaluator(tmp_path)
    payload = {
        "aggregate_metrics": {
            "avg_turnover": 0.0,
            "avg_rebalance_count": 12,
            "avg_txn_cost_per_rebalance": 0.0,
        },
        "rebalance_snapshots": [
            {"gross_exposure": 1.0, "turnover": 0.0, "transaction_cost": 0.0}
            for _ in range(12)
        ],
    }
    cfg = {"transaction_cost_bps_per_side": 5.0}
    for _ in range(2):
        gate = evaluator._portfolio_integrity(payload, cfg)
        assert gate["passed"] is False or gate["turnover_zero_streak"] < 3
    gate = evaluator._portfolio_integrity(payload, cfg)
    assert gate["turnover_zero_streak"] >= 3
    assert gate["passed"] is False


def test_certification_compute_is_pure_state_isolation(tmp_path):
    evaluator = _mk_evaluator(tmp_path)
    ctx = _mk_base_context(tmp_path)
    state_before = copy.deepcopy(evaluator.state)
    out, next_state = evaluator.compute(ctx, prior_state=evaluator.state)
    assert evaluator.state == state_before
    assert isinstance(out, dict)
    assert isinstance(next_state, dict)
    assert next_state != {}


def test_integrity_summary_contains_rule_level_threshold_trace(tmp_path):
    evaluator = _mk_evaluator(tmp_path)
    ctx = _mk_base_context(tmp_path)
    ctx.dataset_metadata = {
        # purposefully missing feature_hash + label_hash
        "universe_hash": "u",
        "price_hash": "p",
        "membership_drift_rate": 0.10,
        "delisted_assets_handled": 1.0,
        "forward_inclusion_check": True,
    }
    out = evaluator.evaluate(ctx)
    summary = out.get("integrity_summary", {})
    details = summary.get("critical_failure_details", [])
    assert isinstance(details, list)
    assert any(str(d.get("rule_id", "")).startswith("data_provenance.") for d in details)
    for d in details:
        assert "observed" in d
        assert "threshold" in d


def test_macro_unit_integrity_detects_currency_percent_conversion(tmp_path):
    evaluator = _mk_evaluator(tmp_path)
    ctx = _mk_base_context(tmp_path)

    out_dir = tmp_path / "data" / "processed" / "macro_transmission"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "run_metadata.json").write_text(
        """
{
  "unit_handling": {
    "percent_conversions": 1,
    "conversion_log_sample": {
      "Exchange Rate INR per USD": "percent_to_decimal"
    },
    "unit_family_counts": {
      "money": 1
    }
  }
}
        """.strip()
    )
    pd.DataFrame(
        [
            {"macro_variable": "Exchange Rate INR per USD", "expected_change": 0.01, "horizon": 1, "as_of": "2026-03-01"}
        ]
    ).to_parquet(out_dir / "macro_expected_change.parquet", index=False)

    out = evaluator.evaluate(ctx)
    gate = out.get("macro_unit_integrity", {})
    assert gate.get("passed") is False
    assert len(gate.get("suspicious_unit_usage", [])) >= 1


def test_shadow_mode_computes_but_does_not_block_actionables(tmp_path):
    controller = ResearchController(
        config={"certification": {"enabled": True, "mode": "shadow"}},
        project_root=tmp_path,
    )
    outputs = [
        {"type": "parameter_search", "actionable": True, "data": {}},
        {"type": "model_promotion", "actionable": True, "data": {}},
    ]
    payload = {
        "integrity_summary": {
            "hard_fail_triggered": True,
            "critical_failures": ["strategy_correlation_check"],
            "certification_passed": False,
        },
        "model_risk_tier": {"tier": 4, "promotion_allowed": False},
    }
    errors: list[str] = []
    summary: dict[str, object] = {}
    controller._apply_certification_policy(outputs=outputs, cert_payload=payload, errors=errors, summary=summary)
    assert outputs[0]["actionable"] is True
    assert outputs[0].get("integrity_shadow_violation") is True
    assert outputs[1]["actionable"] is True
    assert errors == []
    assert summary.get("certification_mode") == "shadow"


def test_certification_disabled_keeps_outputs_unchanged_regression_guard(tmp_path):
    controller = ResearchController(
        config={"certification": {"enabled": False}},
        project_root=tmp_path,
    )
    outputs_before = [
        {"type": "parameter_search", "actionable": True, "data": {"x": 1}},
        {"type": "candidate_model", "actionable": False, "data": {"y": 2}},
    ]
    outputs_after = copy.deepcopy(outputs_before)
    if controller._certification_enabled():
        controller._apply_certification_policy(
            outputs=outputs_after,
            cert_payload={"integrity_summary": {"hard_fail_triggered": True, "certification_passed": False}},
            errors=[],
            summary={},
        )
    assert outputs_after == outputs_before
