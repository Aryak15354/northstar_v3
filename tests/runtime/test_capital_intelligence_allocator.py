from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from src.runtime.capital_allocator import CapitalAllocatorConfig, CapitalAllocatorPolicy
from src.runtime.contracts import DecisionMode, ProposalOrigin, TradeProposal


def _seed_diagnostics_db(path: str, *, negative_alpha_a: bool = False) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE strategy_diagnostics (
                strategy_id TEXT PRIMARY KEY,
                trade_count INTEGER NOT NULL,
                avg_err REAL,
                avg_cer REAL,
                avg_sdr REAL,
                starvation_ratio REAL,
                rebalance_efficiency REAL,
                sharpe REAL,
                max_drawdown REAL,
                stability_score REAL,
                edge_decay REAL,
                regime_sensitivity REAL,
                certification_survival_ratio REAL,
                last_updated TEXT NOT NULL
            );
            CREATE TABLE trade_diagnostics (
                trade_id TEXT PRIMARY KEY,
                strategy_id TEXT NOT NULL,
                close_event_id INTEGER NOT NULL,
                realized_pnl REAL,
                capital_reserved REAL
            );
            CREATE TABLE policy_recommendations (
                recommendation_ts TEXT PRIMARY KEY,
                recommendation_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.executemany(
            """
            INSERT INTO strategy_diagnostics(
                strategy_id, trade_count, avg_err, avg_cer, avg_sdr, starvation_ratio,
                rebalance_efficiency, sharpe, max_drawdown, stability_score, edge_decay,
                regime_sensitivity, certification_survival_ratio, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("alpha_a", 45, 1.20, 0.80, 0.20, 0.15, 1.10, 1.0, 0.12, 0.82, -0.01, 0.30, 0.88, now),
                ("alpha_b", 42, 0.95, 0.65, 0.22, 0.18, 1.05, 0.9, 0.14, 0.79, -0.02, 0.35, 0.84, now),
                ("alpha_c", 39, 0.85, 0.55, 0.25, 0.22, 0.98, 0.8, 0.16, 0.74, -0.03, 0.42, 0.81, now),
            ],
        )
        pnl_rows = []
        for i in range(1, 31):
            a_base = -10.0 if negative_alpha_a else 10.0
            pnl_rows.append((f"a_{i}", "alpha_a", i, a_base + (i % 4), 100.0))
            pnl_rows.append((f"b_{i}", "alpha_b", i, 8.0 + (i % 3), 100.0))
            pnl_rows.append((f"c_{i}", "alpha_c", i, 6.0 + (i % 2), 100.0))
        conn.executemany(
            "INSERT INTO trade_diagnostics(trade_id, strategy_id, close_event_id, realized_pnl, capital_reserved) VALUES (?, ?, ?, ?, ?)",
            pnl_rows,
        )
        recommendation = {
            "advisory_only": True,
            "strategy_cap_adjustment": {"alpha_a": -0.20, "alpha_b": 0.05},
        }
        conn.execute(
            """
            INSERT INTO policy_recommendations(recommendation_ts, recommendation_json, created_at)
            VALUES (?, ?, ?)
            """,
            (now, json.dumps(recommendation, sort_keys=True), now),
        )
        conn.commit()
    finally:
        conn.close()


def _proposal() -> TradeProposal:
    return TradeProposal(
        proposal_id="prop_adv_alloc_1",
        origin=ProposalOrigin.RESEARCH,
        strategy_id="alpha_a",
        signal_id="sig_adv_alloc_1",
        alpha_type="directional",
        expected_edge=0.12,
        risk_score=0.25,
        regime_context={"regime": "neutral"},
        instrument_plan={"symbol": "NIFTY", "side": "buy", "price": 100.0, "quantity": 10.0},
        requested_notional=1000.0,
        certification_snapshot_hash="cert_x",
        decision_mode=DecisionMode.AUTO,
    )


def test_capital_allocator_advanced_models_emit_rationale(tmp_path):
    diag_db = tmp_path / "diag.db"
    _seed_diagnostics_db(str(diag_db))
    policy = CapitalAllocatorPolicy(
        CapitalAllocatorConfig(
            diagnostics_db_path=str(diag_db),
            enable_advanced_models=True,
            apply_advisory_feedback=False,
        )
    )

    decision = policy.evaluate(
        _proposal(),
        portfolio_snapshot={
            "net_liquidation_value": 10000.0,
            "regime_context": {"latent_risk_level": 0.45, "latent_risk_var": 0.10},
        },
        budget_snapshot={
            "reserve_usage": {"equity_alpha": 500.0},
            "strategy_usage": {"alpha_a": 0.45, "alpha_b": 0.30, "alpha_c": 0.25},
        },
        risk_snapshot={"vol_percentile": 0.70, "correlation": 0.80, "drawdown_ratio": 0.15},
    )

    assert decision.is_approved
    assert decision.approved_notional > 0.0
    advanced = dict(decision.sizing_rationale.get("advanced_models", {}) or {})
    assert advanced.get("enabled") is True
    for key in (
        "bayesian_posterior_edge",
        "kelly_fraction",
        "convex_target_share",
        "regime_multiplier",
        "monte_carlo_breach_prob",
        "size_factor",
        "phase4",
        "phase4_status",
        "phase6_adaptive",
        "phase6_multiplier",
    ):
        assert key in advanced
    assert float(advanced.get("kelly_variance_used", 0.0)) >= float(advanced.get("kelly_variance_base", 0.0))
    assert float(advanced.get("kelly_estimation_error", 0.0)) >= 0.0
    assert isinstance(dict(advanced.get("phase4", {}) or {}).get("regime_allocations", []), list)


def test_capital_allocator_advisory_cap_adjustment_changes_convex_share(tmp_path):
    diag_db = tmp_path / "diag.db"
    _seed_diagnostics_db(str(diag_db))
    base = CapitalAllocatorPolicy(
        CapitalAllocatorConfig(
            diagnostics_db_path=str(diag_db),
            enable_advanced_models=True,
            apply_advisory_feedback=False,
        )
    )
    with_advisory = CapitalAllocatorPolicy(
        CapitalAllocatorConfig(
            diagnostics_db_path=str(diag_db),
            enable_advanced_models=True,
            apply_advisory_feedback=True,
        )
    )
    portfolio_snapshot = {
        "net_liquidation_value": 10000.0,
        "regime_context": {"latent_risk_level": 0.40, "latent_risk_var": 0.10},
    }
    budget_snapshot = {
        "reserve_usage": {"equity_alpha": 0.0},
        "strategy_usage": {"alpha_a": 0.40, "alpha_b": 0.35, "alpha_c": 0.25},
    }
    risk_snapshot = {"vol_percentile": 0.50, "correlation": 0.65, "drawdown_ratio": 0.05}

    a = base.evaluate(
        _proposal(),
        portfolio_snapshot=portfolio_snapshot,
        budget_snapshot=budget_snapshot,
        risk_snapshot=risk_snapshot,
    )
    b = with_advisory.evaluate(
        _proposal(),
        portfolio_snapshot=portfolio_snapshot,
        budget_snapshot=budget_snapshot,
        risk_snapshot=risk_snapshot,
    )
    share_a = float(a.sizing_rationale["advanced_models"]["convex_target_share"])
    share_b = float(b.sizing_rationale["advanced_models"]["convex_target_share"])
    assert share_b <= share_a


def test_capital_allocator_phase4_regime_conditioned_and_eigen_penalty(tmp_path):
    diag_db = tmp_path / "diag_regime.db"
    _seed_diagnostics_db(str(diag_db))
    policy = CapitalAllocatorPolicy(
        CapitalAllocatorConfig(
            diagnostics_db_path=str(diag_db),
            enable_advanced_models=True,
            apply_advisory_feedback=False,
            phase4_enabled=True,
            phase5_enabled=True,
            phase5_regime_conditioned=True,
            phase4_eigen_risk_threshold=0.10,
        )
    )

    decision = policy.evaluate(
        _proposal(),
        portfolio_snapshot={
            "net_liquidation_value": 10000.0,
            "regime_context": {"latent_risk_level": 0.45, "latent_risk_var": 0.10},
        },
        budget_snapshot={
            "reserve_usage": {"equity_alpha": 500.0},
            "strategy_usage": {"alpha_a": 0.45, "alpha_b": 0.30, "alpha_c": 0.25},
        },
        risk_snapshot={
            "vol_percentile": 0.70,
            "correlation": 0.80,
            "drawdown_ratio": 0.10,
            "regime_probabilities": {"state_0": 0.20, "state_1": 0.50, "state_2": 0.30},
        },
    )
    assert decision.is_approved
    advanced = dict(decision.sizing_rationale.get("advanced_models", {}) or {})
    p4 = dict(advanced.get("phase4", {}) or {})
    assert p4.get("regime_conditioned") is True
    assert len(list(p4.get("regime_allocations", []) or [])) >= 2
    assert float(p4.get("eigen_multiplier", 1.0)) <= 1.0


def test_capital_allocator_enforces_phase3_reject(tmp_path):
    diag_db = tmp_path / "diag_phase3_fail.db"
    _seed_diagnostics_db(str(diag_db), negative_alpha_a=True)
    policy = CapitalAllocatorPolicy(
        CapitalAllocatorConfig(
            diagnostics_db_path=str(diag_db),
            enable_advanced_models=True,
            apply_advisory_feedback=False,
            phase3_enabled=True,
            phase3_enforce=True,
            phase3_min_history=10,
            phase3_n_sim=200,
        )
    )

    decision = policy.evaluate(
        _proposal(),
        portfolio_snapshot={
            "net_liquidation_value": 10000.0,
            "regime_context": {"latent_risk_level": 0.45, "latent_risk_var": 0.10},
        },
        budget_snapshot={
            "reserve_usage": {"equity_alpha": 500.0},
            "strategy_usage": {"alpha_a": 0.45, "alpha_b": 0.30, "alpha_c": 0.25},
        },
        risk_snapshot={"vol_percentile": 0.70, "correlation": 0.80, "drawdown_ratio": 0.15},
    )

    assert not decision.is_approved
    assert decision.denial_reason in {
        "capital.phase3_deterministic_fail",
        "capital.phase3_monte_carlo_fail",
        "capital.phase3_reject",
    }
    advanced = dict(decision.sizing_rationale.get("advanced_models", {}) or {})
    assert str(advanced.get("phase3_status", "")) == "reject"


def test_capital_allocator_emits_phase8_phase9_payload(tmp_path):
    diag_db = tmp_path / "diag_phase89.db"
    _seed_diagnostics_db(str(diag_db))
    policy = CapitalAllocatorPolicy(
        CapitalAllocatorConfig(
            diagnostics_db_path=str(diag_db),
            enable_advanced_models=True,
            phase4_enabled=True,
            phase5_enabled=True,
            phase8_enabled=True,
            phase9_enabled=True,
            phase10_enabled=True,
            phase10_min_history_points=5,
        )
    )

    decision = policy.evaluate(
        _proposal(),
        portfolio_snapshot={
            "net_liquidation_value": 10000.0,
            "regime_context": {"latent_risk_level": 0.42, "latent_risk_var": 0.08},
        },
        budget_snapshot={
            "reserve_usage": {"equity_alpha": 300.0},
            "strategy_usage": {"alpha_a": 0.40, "alpha_b": 0.35, "alpha_c": 0.25},
        },
        risk_snapshot={"vol_percentile": 0.60, "correlation": 0.70, "drawdown_ratio": 0.08},
    )

    assert decision.is_approved
    advanced = dict(decision.sizing_rationale.get("advanced_models", {}) or {})
    p4 = dict(advanced.get("phase4", {}) or {})
    assert "manifold" in p4
    assert "phase9" in p4
    assert bool(dict(p4.get("phase9", {}) or {}).get("enabled", False)) is True
    alloc = dict(p4.get("allocation", {}) or {})
    assert "weights" in alloc
    assert str(advanced.get("phase10_status", "")) == "active"
    assert float(advanced.get("phase10_multiplier", 1.0)) > 0.0
    assert "phase10" in advanced
    phase10 = dict(advanced.get("phase10", {}) or {})
    arch_update = dict(phase10.get("architecture_update", {}) or {})
    arch_diag = dict(arch_update.get("diagnostics", {}) or {})
    assert "system_stability_index" in dict(phase10.get("system_regret", {}) or {})
    assert "regime_probs" in arch_diag
    assert "strategic_regime" in arch_diag
