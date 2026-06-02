from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from scripts.runners import sync_current_positions as sync_mod


def _write_runtime_snapshot(db_path: Path) -> None:
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            """
            CREATE TABLE portfolio_snapshots (
                snapshot_id INTEGER PRIMARY KEY,
                event_id INTEGER NOT NULL,
                state_hash TEXT NOT NULL,
                state_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        state = {
            "holdings": {
                "ABB.NS": {
                    "quantity": 2.0,
                    "avg_price": 100.0,
                    "last_price": 100.0,
                    "instrument_type": "equity",
                    "sector": "Capital Goods",
                    "strategy_id": "hedge_fund_core_book",
                },
                "VEDL.NS": {
                    "quantity": 1.0,
                    "avg_price": 200.0,
                    "last_price": 200.0,
                    "instrument_type": "equity",
                    "sector": "Metals",
                    "strategy_id": "hedge_fund_core_book",
                },
            }
        }
        con.execute(
            """
            INSERT INTO portfolio_snapshots(event_id, state_hash, state_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (12, "abc123", json.dumps(state), "2026-03-19T14:18:41.755400+00:00"),
        )
        con.commit()
    finally:
        con.close()


def _write_options_only_runtime_snapshot(db_path: Path) -> None:
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            """
            CREATE TABLE portfolio_snapshots (
                snapshot_id INTEGER PRIMARY KEY,
                event_id INTEGER NOT NULL,
                state_hash TEXT NOT NULL,
                state_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        state = {
            "holdings": {
                "OPT::NIFTY::POS1": {
                    "quantity": 2.0,
                    "avg_price": 100.0,
                    "last_price": 110.0,
                    "instrument_type": "option",
                    "sector": "",
                    "strategy_id": "hedge_fund_core_book",
                }
            }
        }
        con.execute(
            """
            INSERT INTO portfolio_snapshots(event_id, state_hash, state_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (12, "opt123", json.dumps(state), "2026-03-19T14:18:41.755400+00:00"),
        )
        con.commit()
    finally:
        con.close()


def test_build_current_positions_prefers_runtime_holdings_and_ledger_cash(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_db = tmp_path / "portfolio_runtime.db"
    prices_path = tmp_path / "prices.parquet"
    ledger_path = tmp_path / "master_ledger.parquet"
    runtime_json = tmp_path / "options_runtime_state.json"
    state_path = tmp_path / "unified_state.json"
    analytics_path = tmp_path / "portfolio_analytics.json"
    nav_history_path = tmp_path / "nav_history.parquet"
    missing_weights = tmp_path / "missing_weights.parquet"

    _write_runtime_snapshot(runtime_db)

    pd.DataFrame(
        [
            {"ticker": "ABB.NS", "Date": "2026-03-19", "Close": 110.0},
            {"ticker": "VEDL.NS", "Date": "2026-03-19", "Close": 190.0},
        ]
    ).to_parquet(prices_path, index=False)

    pd.DataFrame(
        [
            {
                "entry_type": "EQUITY_BUY",
                "notional": 200.0,
                "transaction_cost": 0.0,
                "trade_date": "2026-03-19T14:18:41+00:00",
            },
            {
                "entry_type": "EQUITY_BUY",
                "notional": 200.0,
                "transaction_cost": 0.0,
                "trade_date": "2026-03-19T14:18:42+00:00",
            },
        ]
    ).to_parquet(ledger_path, index=False)

    runtime_json.write_text(json.dumps({"open_positions": [], "closed_positions": []}), encoding="utf-8")
    state_path.write_text(json.dumps({"portfolio": {"total_value": 800.0}}), encoding="utf-8")
    analytics_path.write_text(json.dumps({}), encoding="utf-8")
    pd.DataFrame([{"date": "2026-03-19", "nav_combined": 700.0}]).to_parquet(nav_history_path, index=False)

    monkeypatch.setattr(sync_mod, "RUNTIME_DB_PATH", runtime_db)
    monkeypatch.setattr(sync_mod, "PRICES_PATH", prices_path)
    monkeypatch.setattr(sync_mod, "MASTER_LEDGER_PATH", ledger_path)
    monkeypatch.setattr(sync_mod, "RUNTIME_PATH", runtime_json)
    monkeypatch.setattr(sync_mod, "STATE_PATH", state_path)
    monkeypatch.setattr(sync_mod, "PORTFOLIO_ANALYTICS_PATH", analytics_path)
    monkeypatch.setattr(sync_mod, "NAV_HISTORY_PATH", nav_history_path)
    monkeypatch.setattr(sync_mod, "WEIGHTS_PATH", missing_weights)

    payload, holdings_df = sync_mod.build_current_positions(default_capital=1_000.0)

    assert payload["position_source"] == "runtime_snapshot"
    assert payload["positions_count"] == 2
    assert holdings_df["ticker"].tolist() == ["ABB.NS", "VEDL.NS"]
    assert payload["invested_value"] == 410.0
    assert payload["cash"] == 600.0
    assert payload["total_value"] == 1_010.0
    assert payload["positions"]["ABB.NS"]["market_value"] == 220.0
    assert payload["positions"]["VEDL.NS"]["market_value"] == 190.0


def test_build_current_positions_fails_closed_without_runtime_holdings(
    tmp_path: Path,
    monkeypatch,
) -> None:
    missing_runtime_db = tmp_path / "missing_runtime.db"
    runtime_json = tmp_path / "options_runtime_state.json"
    runtime_json.write_text(json.dumps({"open_positions": [], "closed_positions": []}), encoding="utf-8")

    monkeypatch.setattr(sync_mod, "RUNTIME_DB_PATH", missing_runtime_db)
    monkeypatch.setattr(sync_mod, "RUNTIME_PATH", runtime_json)

    with pytest.raises(RuntimeError, match="refusing weights fallback"):
        sync_mod.build_current_positions(default_capital=1_000.0)


def test_build_current_positions_uses_explicit_cash_seed_without_double_counting(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_db = tmp_path / "portfolio_runtime.db"
    prices_path = tmp_path / "prices.parquet"
    ledger_path = tmp_path / "master_ledger.parquet"
    runtime_json = tmp_path / "options_runtime_state.json"
    state_path = tmp_path / "unified_state.json"
    analytics_path = tmp_path / "portfolio_analytics.json"
    nav_history_path = tmp_path / "nav_history.parquet"
    missing_weights = tmp_path / "missing_weights.parquet"

    _write_runtime_snapshot(runtime_db)

    pd.DataFrame(
        [
            {"ticker": "ABB.NS", "Date": "2026-03-19", "Close": 110.0},
            {"ticker": "VEDL.NS", "Date": "2026-03-19", "Close": 190.0},
        ]
    ).to_parquet(prices_path, index=False)

    pd.DataFrame(
        [
            {
                "entry_type": "CASH_IN",
                "notional": 1_000.0,
                "transaction_cost": 0.0,
                "trade_date": "2026-03-18T14:18:40+00:00",
            },
            {
                "entry_type": "EQUITY_BUY",
                "notional": 200.0,
                "transaction_cost": 0.0,
                "trade_date": "2026-03-19T14:18:41+00:00",
            },
            {
                "entry_type": "EQUITY_BUY",
                "notional": 200.0,
                "transaction_cost": 0.0,
                "trade_date": "2026-03-19T14:18:42+00:00",
            },
        ]
    ).to_parquet(ledger_path, index=False)

    runtime_json.write_text(json.dumps({"open_positions": [], "closed_positions": []}), encoding="utf-8")
    state_path.write_text(json.dumps({"portfolio": {"total_value": 800.0}}), encoding="utf-8")
    analytics_path.write_text(json.dumps({}), encoding="utf-8")
    pd.DataFrame([{"date": "2026-03-19", "nav_combined": 700.0}]).to_parquet(nav_history_path, index=False)

    monkeypatch.setattr(sync_mod, "RUNTIME_DB_PATH", runtime_db)
    monkeypatch.setattr(sync_mod, "PRICES_PATH", prices_path)
    monkeypatch.setattr(sync_mod, "MASTER_LEDGER_PATH", ledger_path)
    monkeypatch.setattr(sync_mod, "RUNTIME_PATH", runtime_json)
    monkeypatch.setattr(sync_mod, "STATE_PATH", state_path)
    monkeypatch.setattr(sync_mod, "PORTFOLIO_ANALYTICS_PATH", analytics_path)
    monkeypatch.setattr(sync_mod, "NAV_HISTORY_PATH", nav_history_path)
    monkeypatch.setattr(sync_mod, "WEIGHTS_PATH", missing_weights)

    payload, _ = sync_mod.build_current_positions(default_capital=1_000.0)

    assert payload["cash"] == 600.0
    assert payload["total_value"] == 1_010.0


def test_build_current_positions_allows_options_only_runtime_snapshot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_db = tmp_path / "portfolio_runtime.db"
    runtime_json = tmp_path / "options_runtime_state.json"
    state_path = tmp_path / "unified_state.json"
    analytics_path = tmp_path / "portfolio_analytics.json"
    nav_history_path = tmp_path / "nav_history.parquet"
    missing_weights = tmp_path / "missing_weights.parquet"

    _write_options_only_runtime_snapshot(runtime_db)

    runtime_json.write_text(
        json.dumps(
            {
                "open_positions": [
                    {
                        "position_id": "POS1",
                        "current_value": 220.0,
                        "entry_credit_debit": 200.0,
                    }
                ],
                "closed_positions": [],
            }
        ),
        encoding="utf-8",
    )
    state_path.write_text(json.dumps({"portfolio": {"total_value": 1_000.0}}), encoding="utf-8")
    analytics_path.write_text(json.dumps({}), encoding="utf-8")
    pd.DataFrame([{"date": "2026-03-19", "nav_combined": 1_000.0}]).to_parquet(nav_history_path, index=False)

    monkeypatch.setattr(sync_mod, "RUNTIME_DB_PATH", runtime_db)
    monkeypatch.setattr(sync_mod, "RUNTIME_PATH", runtime_json)
    monkeypatch.setattr(sync_mod, "STATE_PATH", state_path)
    monkeypatch.setattr(sync_mod, "PORTFOLIO_ANALYTICS_PATH", analytics_path)
    monkeypatch.setattr(sync_mod, "NAV_HISTORY_PATH", nav_history_path)
    monkeypatch.setattr(sync_mod, "WEIGHTS_PATH", missing_weights)

    payload, holdings_df = sync_mod.build_current_positions(default_capital=1_000.0)

    assert holdings_df.empty
    assert payload["position_source"] == "runtime_snapshot_options_only"
    assert payload["positions_count"] == 0
    assert payload["invested_value"] == 0.0
    assert payload["options_market_value"] == 220.0


def test_options_runtime_audit_deduplicates_duplicate_open_lifecycle_rows(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_db = tmp_path / "portfolio_runtime.db"
    con = sqlite3.connect(runtime_db)
    try:
        con.execute(
            """
            CREATE TABLE position_lifecycle_table (
                id INTEGER PRIMARY KEY,
                position_key TEXT NOT NULL,
                open_event_id INTEGER,
                close_event_id INTEGER,
                open_reason TEXT,
                close_reason TEXT,
                hold_days REAL,
                max_adverse_excursion REAL,
                max_favorable_excursion REAL,
                realized_pnl REAL,
                strategy_id TEXT,
                signal_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE portfolio_events (
                event_id INTEGER PRIMARY KEY,
                event_type TEXT,
                proposal_id TEXT,
                trigger_reason_code TEXT,
                timestamp_utc TEXT,
                payload_json TEXT
            )
            """
        )
        payload_json = json.dumps({"underlying_symbol": "NIFTY"})
        con.execute(
            """
            INSERT INTO portfolio_events(event_id, event_type, proposal_id, trigger_reason_code, timestamp_utc, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (1, "ORDER_FILLED", "prop_sig_NIFTY_1", "proposal.runtime.default", "2026-03-26T03:46:04+00:00", payload_json),
        )
        con.execute(
            """
            INSERT INTO portfolio_events(event_id, event_type, proposal_id, trigger_reason_code, timestamp_utc, payload_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (2, "ORDER_FILLED", "sync_option_open_POS1", "options.runtime.sync.open", "2026-03-26T03:47:04+00:00", payload_json),
        )
        con.execute(
            """
            INSERT INTO position_lifecycle_table(
                id, position_key, open_event_id, close_event_id, open_reason, close_reason,
                hold_days, max_adverse_excursion, max_favorable_excursion, realized_pnl,
                strategy_id, signal_id, created_at, updated_at
            ) VALUES (?, ?, ?, NULL, ?, NULL, NULL, NULL, NULL, NULL, ?, ?, ?, ?)
            """,
            (1, "POS1", 1, "proposal.runtime.default", "bear_put_spread", "sig1", "2026-03-26T03:46:04+00:00", "2026-03-26T03:46:04+00:00"),
        )
        con.execute(
            """
            INSERT INTO position_lifecycle_table(
                id, position_key, open_event_id, close_event_id, open_reason, close_reason,
                hold_days, max_adverse_excursion, max_favorable_excursion, realized_pnl,
                strategy_id, signal_id, created_at, updated_at
            ) VALUES (?, ?, ?, NULL, ?, NULL, NULL, NULL, NULL, NULL, ?, ?, ?, ?)
            """,
            (2, "POS1", 2, "options.runtime.sync.open", "bear_put_spread", "sig2", "2026-03-26T03:47:04+00:00", "2026-03-26T03:47:04+00:00"),
        )
        con.commit()
    finally:
        con.close()

    monkeypatch.setattr(sync_mod, "RUNTIME_DB_PATH", runtime_db)

    ledger_df = pd.DataFrame(
        [
            {
                "trade_id": "POS1",
                "action": "open",
                "strategy_type": "bear_put_spread",
                "underlying": "NIFTY",
                "timestamp": "2026-03-26T03:46:04+00:00",
            }
        ]
    )
    runtime_payload = {"open_positions": [{"position_id": "POS1"}], "closed_positions": []}

    audit = sync_mod._repair_stale_option_lifecycle_from_ledger(ledger_df, runtime_payload)

    assert audit["deduplicated_open_lifecycle_rows"] == 1
    assert audit["remaining_open_lifecycle_rows"] == 1
    assert audit["status"] == "ok"
