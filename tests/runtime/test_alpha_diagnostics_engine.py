from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pandas as pd

from src.diagnostics import AlphaDiagnosticsEngine, DiagnosticsPaths


def _seed_runtime_db(db_path: str) -> None:
    now = datetime.now(timezone.utc)
    future = now + timedelta(days=20)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE proposal_inbox (
                proposal_id TEXT PRIMARY KEY,
                proposal_json TEXT
            );
            CREATE TABLE portfolio_events (
                event_id INTEGER PRIMARY KEY,
                sequence_no INTEGER,
                timestamp_utc TEXT,
                event_type TEXT,
                proposal_id TEXT,
                trigger_reason_code TEXT,
                strategy_id TEXT,
                signal_id TEXT,
                origin TEXT,
                payload_json TEXT
            );
            CREATE TABLE execution_fills (
                event_id INTEGER,
                fill_notional REAL
            );
            CREATE TABLE position_lifecycle_table (
                id INTEGER PRIMARY KEY,
                position_key TEXT,
                open_event_id INTEGER,
                close_event_id INTEGER,
                open_reason TEXT,
                close_reason TEXT,
                hold_days REAL,
                realized_pnl REAL,
                strategy_id TEXT,
                signal_id TEXT
            );
            CREATE TABLE portfolio_stress_matrix (
                event_id INTEGER,
                risk_metric REAL
            );
            CREATE TABLE certification_snapshots (
                snapshot_hash TEXT PRIMARY KEY,
                valid_until TEXT
            );
            CREATE TABLE portfolio_snapshots (
                snapshot_id INTEGER PRIMARY KEY,
                state_json TEXT
            );
            """
        )

        conn.execute(
            "INSERT INTO certification_snapshots(snapshot_hash, valid_until) VALUES (?, ?)",
            ("cert_1", future.isoformat()),
        )

        proposals = [
            (
                "prop_eq",
                {
                    "proposal_id": "prop_eq",
                    "origin": "equity_alpha",
                    "strategy_id": "alpha_eq",
                    "signal_id": "sig_eq",
                    "expected_edge": 0.02,
                    "requested_notional": 1000.0,
                    "certification_snapshot_hash": "cert_1",
                    "regime_context": {"regime": "bull"},
                },
            ),
            (
                "prop_opt",
                {
                    "proposal_id": "prop_opt",
                    "origin": "options_alpha",
                    "strategy_id": "options_strat",
                    "signal_id": "sig_opt",
                    "expected_edge": 0.03,
                    "requested_notional": 1000.0,
                    "certification_snapshot_hash": "cert_1",
                    "regime_context": {"regime": "neutral"},
                },
            ),
        ]
        for proposal_id, payload in proposals:
            conn.execute(
                "INSERT INTO proposal_inbox(proposal_id, proposal_json) VALUES (?, ?)",
                (proposal_id, json.dumps(payload, sort_keys=True)),
            )

        events = [
            (
                1,
                1,
                now.isoformat(),
                "ORDER_FILLED",
                "prop_eq",
                "proposal.runtime.default",
                "alpha_eq",
                "sig_eq",
                "equity_alpha",
                {"regime_context": {"regime": "bull"}},
            ),
            (
                2,
                2,
                (now + timedelta(hours=2)).isoformat(),
                "ORDER_FILLED",
                "prop_eq",
                "rebalance.volatility",
                "alpha_eq",
                "sig_eq",
                "equity_alpha",
                {"regime_context": {"regime": "bear"}},
            ),
            (
                3,
                1,
                now.isoformat(),
                "ORDER_FILLED",
                "prop_opt",
                "proposal.runtime.default",
                "options_strat",
                "sig_opt",
                "options_alpha",
                {"regime_context": {"regime": "neutral"}},
            ),
            (
                4,
                2,
                (now + timedelta(hours=3)).isoformat(),
                "ORDER_FILLED",
                "prop_opt",
                "close.signal",
                "options_strat",
                "sig_opt",
                "options_alpha",
                {"regime_context": {"regime": "neutral"}},
            ),
            (
                5,
                0,
                now.isoformat(),
                "INTENT_APPROVED",
                "prop_eq",
                "proposal.runtime.default",
                "alpha_eq",
                "sig_eq",
                "equity_alpha",
                {"approved_notional": 1000.0},
            ),
            (
                6,
                0,
                now.isoformat(),
                "INTENT_APPROVED",
                "prop_opt",
                "proposal.runtime.default",
                "options_strat",
                "sig_opt",
                "options_alpha",
                {"approved_notional": 200.0},
            ),
        ]
        conn.executemany(
            """
            INSERT INTO portfolio_events(
                event_id, sequence_no, timestamp_utc, event_type, proposal_id,
                trigger_reason_code, strategy_id, signal_id, origin, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [(e[0], e[1], e[2], e[3], e[4], e[5], e[6], e[7], e[8], json.dumps(e[9], sort_keys=True)) for e in events],
        )

        conn.executemany(
            """
            INSERT INTO position_lifecycle_table(
                id, position_key, open_event_id, close_event_id, open_reason, close_reason,
                hold_days, realized_pnl, strategy_id, signal_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    1,
                    "pos_eq_1",
                    1,
                    2,
                    "entry.signal",
                    "rebalance.volatility",
                    5.0,
                    30.0,
                    "alpha_eq",
                    "sig_eq",
                ),
                (
                    2,
                    "pos_opt_1",
                    3,
                    4,
                    "entry.signal",
                    "close.signal",
                    4.0,
                    10.0,
                    "options_strat",
                    "sig_opt",
                ),
            ],
        )

        conn.executemany(
            "INSERT INTO portfolio_stress_matrix(event_id, risk_metric) VALUES (?, ?)",
            [(1, 0.25), (2, 0.10), (3, 0.40), (4, 0.20)],
        )
        conn.execute(
            "INSERT INTO execution_fills(event_id, fill_notional) VALUES (?, ?)",
            (2, 1000.0),
        )
        conn.execute(
            "INSERT INTO portfolio_snapshots(snapshot_id, state_json) VALUES (?, ?)",
            (1, json.dumps({"gross_exposure": 1500.0, "net_exposure": 900.0}, sort_keys=True)),
        )
        conn.commit()
    finally:
        conn.close()


def test_ade_metrics_and_artifacts(tmp_path):
    runtime_db = tmp_path / "runtime.db"
    diagnostics_db = tmp_path / "diagnostics.db"
    alpha_parquet = tmp_path / "alpha_metrics.parquet"
    strategy_parquet = tmp_path / "strategy_metrics.parquet"
    policy_json = tmp_path / "policy_recommendations.json"
    _seed_runtime_db(str(runtime_db))

    engine = AlphaDiagnosticsEngine(
        DiagnosticsPaths(
            runtime_db=str(runtime_db),
            diagnostics_db=str(diagnostics_db),
            alpha_metrics_parquet=str(alpha_parquet),
            strategy_metrics_parquet=str(strategy_parquet),
            policy_recommendations_json=str(policy_json),
        )
    )
    try:
        trade_df = engine.compute_trade_diagnostics()
        strategy_df = engine.compute_strategy_diagnostics()
        portfolio_df = engine.compute_portfolio_diagnostics()
    finally:
        engine.close()

    assert len(trade_df) == 2
    eq_trade = trade_df[trade_df["strategy_id"] == "alpha_eq"].iloc[0]
    assert abs(float(eq_trade["edge_realization_ratio"]) - 1.5) < 1e-9
    assert abs(float(eq_trade["capital_efficiency_ratio"]) - 0.006) < 1e-9
    assert abs(float(eq_trade["stress_drag_ratio"]) - 0.25) < 1e-9

    assert len(strategy_df) == 2
    opt_row = strategy_df[strategy_df["strategy_id"] == "options_strat"].iloc[0]
    assert abs(float(opt_row["starvation_ratio"]) - 0.8) < 1e-9

    assert len(portfolio_df) == 1
    assert 0.0 <= float(portfolio_df.iloc[0]["eqs"]) <= 1.0
    assert float(portfolio_df.iloc[0]["gross_exposure"]) == 1500.0

    assert alpha_parquet.exists()
    assert strategy_parquet.exists()
    assert policy_json.exists()
    payload = json.loads(policy_json.read_text(encoding="utf-8"))
    assert payload.get("advisory_only") is True


def test_ade_handles_sparse_runtime_db(tmp_path):
    runtime_db = tmp_path / "empty_runtime.db"
    sqlite3.connect(str(runtime_db)).close()
    diagnostics_db = tmp_path / "diag.db"
    alpha_parquet = tmp_path / "alpha.parquet"
    strategy_parquet = tmp_path / "strategy.parquet"
    policy_json = tmp_path / "policy.json"

    engine = AlphaDiagnosticsEngine(
        DiagnosticsPaths(
            runtime_db=str(runtime_db),
            diagnostics_db=str(diagnostics_db),
            alpha_metrics_parquet=str(alpha_parquet),
            strategy_metrics_parquet=str(strategy_parquet),
            policy_recommendations_json=str(policy_json),
        )
    )
    try:
        trade_df = engine.compute_trade_diagnostics()
        strategy_df = engine.compute_strategy_diagnostics()
        portfolio_df = engine.compute_portfolio_diagnostics()
    finally:
        engine.close()

    assert isinstance(trade_df, pd.DataFrame)
    assert isinstance(strategy_df, pd.DataFrame)
    assert len(portfolio_df) == 1


def test_ade_bootstraps_missing_runtime_db_parent(tmp_path):
    runtime_db = tmp_path / "data/runtime/portfolio_runtime.db"
    diagnostics_db = tmp_path / "data/diagnostics/alpha_diagnostics.db"
    alpha_parquet = tmp_path / "data/diagnostics/alpha_metrics.parquet"
    strategy_parquet = tmp_path / "data/diagnostics/strategy_metrics.parquet"
    policy_json = tmp_path / "data/diagnostics/policy_recommendations.json"

    engine = AlphaDiagnosticsEngine(
        DiagnosticsPaths(
            runtime_db=str(runtime_db),
            diagnostics_db=str(diagnostics_db),
            alpha_metrics_parquet=str(alpha_parquet),
            strategy_metrics_parquet=str(strategy_parquet),
            policy_recommendations_json=str(policy_json),
        )
    )
    try:
        trade_df = engine.compute_trade_diagnostics()
        strategy_df = engine.compute_strategy_diagnostics()
        portfolio_df = engine.compute_portfolio_diagnostics()
    finally:
        engine.close()

    assert runtime_db.exists()
    assert diagnostics_db.exists()
    assert isinstance(trade_df, pd.DataFrame)
    assert isinstance(strategy_df, pd.DataFrame)
    assert len(portfolio_df) == 1
