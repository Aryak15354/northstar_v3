from __future__ import annotations

import json
import sqlite3

from src.runtime import PortfolioRuntimeService
from src.runtime.live_book_sync import sync_core_equity_book, sync_options_runtime_book


def _make_prs(tmp_path):
    db = tmp_path / "portfolio_runtime.db"
    out = tmp_path / "derived"
    return PortfolioRuntimeService(
        db_path=str(db),
        materialized_output_dir=str(out),
        starting_cash=1_000.0,
    )


def _overwrite_latest_snapshot_holdings(db_path, holdings):
    with sqlite3.connect(str(db_path)) as con:
        state_json = json.dumps({"holdings": holdings})
        con.execute(
            """
            UPDATE portfolio_snapshots
            SET state_hash = ?, state_json = ?
            WHERE snapshot_id = (SELECT MAX(snapshot_id) FROM portfolio_snapshots)
            """,
            ("forced_snapshot", state_json),
        )
        con.commit()


def test_core_equity_sync_bootstraps_and_is_idempotent(tmp_path):
    prs = _make_prs(tmp_path)
    try:
        payload = {
            "total_value": 1_000.0,
            "positions": {
                "ABC.NS": {
                    "quantity": 5.0,
                    "avg_price": 100.0,
                    "current_price": 100.0,
                    "weight": 0.50,
                    "market_value": 500.0,
                    "sector": "Industrials",
                },
                "XYZ.NS": {
                    "quantity": 2.0,
                    "avg_price": 200.0,
                    "current_price": 200.0,
                    "weight": 0.40,
                    "market_value": 400.0,
                    "sector": "Financial Services",
                },
            },
        }

        report = sync_core_equity_book(prs, payload)
        state = prs.get_portfolio_state()

        assert report["trade_events"] == 2
        assert "ABC.NS" in state.holdings
        assert "XYZ.NS" in state.holdings
        assert state.holdings["ABC.NS"]["quantity"] == 5.0
        assert state.holdings["XYZ.NS"]["quantity"] == 2.0

        with sqlite3.connect(str(tmp_path / "portfolio_runtime.db")) as con:
            origins = {
                row[0]
                for row in con.execute(
                    "select origin from portfolio_events where trigger_reason_code = 'rebalance.core.sync'"
                ).fetchall()
            }
        assert origins == {"research"}

        rerun = sync_core_equity_book(prs, payload)
        assert rerun["trade_events"] == 0
    finally:
        prs.close()


def test_core_equity_sync_defers_small_reductions_inside_hold_window(tmp_path):
    prs = _make_prs(tmp_path)
    try:
        initial_payload = {
            "total_value": 1_000.0,
            "positions": {
                "ABC.NS": {
                    "quantity": 5.0,
                    "avg_price": 100.0,
                    "current_price": 100.0,
                    "weight": 0.50,
                    "market_value": 500.0,
                    "sector": "Industrials",
                },
            },
        }
        sync_core_equity_book(prs, initial_payload)

        deferred_payload = {
            "total_value": 1_000.0,
            "positions": {
                "ABC.NS": {
                    "quantity": 4.5,
                    "avg_price": 100.0,
                    "current_price": 100.0,
                    "weight": 0.45,
                    "market_value": 450.0,
                    "sector": "Industrials",
                },
            },
        }
        report = sync_core_equity_book(prs, deferred_payload)
        state = prs.get_portfolio_state()

        assert report["trade_events"] == 0
        assert state.holdings["ABC.NS"]["quantity"] == 5.0

        override_payload = {
            "total_value": 1_000.0,
            "positions": {},
        }
        override_report = sync_core_equity_book(prs, override_payload)
        final_state = prs.get_portfolio_state()

        assert override_report["trade_events"] == 1
        assert "ABC.NS" not in final_state.holdings
    finally:
        prs.close()


def test_core_equity_sync_dedup_skips_duplicate_basket_after_runtime_state_reset(tmp_path):
    db_path = tmp_path / "portfolio_runtime.db"
    payload = {
        "total_value": 1_000.0,
        "positions": {
            "ABC.NS": {
                "quantity": 5.0,
                "avg_price": 100.0,
                "current_price": 100.0,
                "weight": 0.50,
                "market_value": 500.0,
                "sector": "Industrials",
            },
            "XYZ.NS": {
                "quantity": 2.0,
                "avg_price": 200.0,
                "current_price": 200.0,
                "weight": 0.40,
                "market_value": 400.0,
                "sector": "Financial Services",
            },
        },
    }

    prs = _make_prs(tmp_path)
    try:
        report = sync_core_equity_book(prs, payload)
        assert report["trade_events"] == 2
    finally:
        prs.close()

    _overwrite_latest_snapshot_holdings(db_path, {})

    prs = _make_prs(tmp_path)
    try:
        rerun = sync_core_equity_book(prs, payload)
        assert rerun["trade_events"] == 0
        assert rerun["dedup_skipped"] is True
        assert "duplicate core sync basket suppressed" in rerun["dedup_reason"]

        with sqlite3.connect(str(db_path)) as con:
            count = con.execute(
                "select count(*) from portfolio_events where trigger_reason_code = 'rebalance.core.sync'"
            ).fetchone()[0]
        assert count == 2
    finally:
        prs.close()


def test_core_equity_sync_dedup_allows_changed_basket_same_day(tmp_path):
    db_path = tmp_path / "portfolio_runtime.db"
    initial_payload = {
        "total_value": 1_000.0,
        "positions": {
            "ABC.NS": {
                "quantity": 5.0,
                "avg_price": 100.0,
                "current_price": 100.0,
                "weight": 0.50,
                "market_value": 500.0,
                "sector": "Industrials",
            },
        },
    }
    changed_payload = {
        "total_value": 1_000.0,
        "positions": {
            "ABC.NS": {
                "quantity": 6.0,
                "avg_price": 100.0,
                "current_price": 100.0,
                "weight": 0.60,
                "market_value": 600.0,
                "sector": "Industrials",
            },
        },
    }

    prs = _make_prs(tmp_path)
    try:
        report = sync_core_equity_book(prs, initial_payload)
        assert report["trade_events"] == 1
    finally:
        prs.close()

    _overwrite_latest_snapshot_holdings(db_path, {})

    prs = _make_prs(tmp_path)
    try:
        rerun = sync_core_equity_book(prs, changed_payload)
        assert rerun["trade_events"] == 1
        assert rerun["dedup_skipped"] is False

        with sqlite3.connect(str(db_path)) as con:
            count = con.execute(
                "select count(*) from portfolio_events where trigger_reason_code = 'rebalance.core.sync'"
            ).fetchone()[0]
        assert count == 2
    finally:
        prs.close()


def test_options_runtime_sync_bootstraps_and_closes_position(tmp_path):
    prs = _make_prs(tmp_path)
    try:
        core_payload = {
            "positions": {
                "HDFCBANK.NS": {
                    "quantity": 3.0,
                    "avg_price": 100.0,
                    "current_price": 100.0,
                    "weight": 0.30,
                    "market_value": 300.0,
                    "sector": "Financial Services",
                },
                "ICICIBANK.NS": {
                    "quantity": 2.0,
                    "avg_price": 150.0,
                    "current_price": 150.0,
                    "weight": 0.30,
                    "market_value": 300.0,
                    "sector": "Financial Services",
                },
            }
        }
        open_runtime = {
            "portfolio_overlay": {
                "portfolio_objective": "defensive_convexity",
                "hedge_intensity": 0.9,
                "weekly_hedge_targets": ["NIFTY", "BANKNIFTY"],
            },
            "open_positions": [
                {
                    "position_id": "POS1",
                    "strategy_type": "bear_put_spread",
                    "underlying": "NIFTY",
                    "entry_credit_debit": 120.0,
                    "current_value": 135.0,
                    "max_loss": 120.0,
                    "greeks": {"delta": -0.25, "gamma": 0.02, "vega": 0.30, "theta": -0.05},
                    "metadata": {
                        "objective": "protect_core",
                        "prs_symbol": "OPT::NIFTY::POS1",
                        "prs_position_key": "POS1",
                    },
                }
            ],
            "closed_positions": [],
        }

        open_report = sync_options_runtime_book(
            prs,
            runtime_payload=open_runtime,
            current_positions_payload=core_payload,
        )
        state = prs.get_portfolio_state()

        assert open_report["trade_events"] == 1
        assert "OPT::NIFTY::POS1" in state.holdings
        assert state.holdings["OPT::NIFTY::POS1"]["instrument_type"] == "option"
        assert state.holdings["OPT::NIFTY::POS1"]["quantity"] == 1.0
        assert state.hedging_state["objective"] == "protect_core"
        assert "HDFCBANK.NS" in state.hedging_state["protected_symbols"]

        close_runtime = {
            "portfolio_overlay": open_runtime["portfolio_overlay"],
            "open_positions": [],
            "closed_positions": [
                {
                    "position_id": "POS1",
                    "strategy_type": "bear_put_spread",
                    "underlying": "NIFTY",
                    "current_value": 150.0,
                    "realized_pnl": 30.0,
                    "exit_reason": "profit_target",
                    "metadata": {
                        "prs_symbol": "OPT::NIFTY::POS1",
                        "prs_position_key": "POS1",
                    },
                }
            ],
        }
        close_report = sync_options_runtime_book(
            prs,
            runtime_payload=close_runtime,
            current_positions_payload=core_payload,
        )
        final_state = prs.get_portfolio_state()

        assert close_report["trade_events"] == 1
        assert "OPT::NIFTY::POS1" not in final_state.holdings
    finally:
        prs.close()


def test_options_runtime_sync_keeps_lifecycle_open_rows_idempotent(tmp_path):
    db_path = tmp_path / "portfolio_runtime.db"
    core_payload = {
        "positions": {
            "HDFCBANK.NS": {
                "quantity": 3.0,
                "avg_price": 100.0,
                "current_price": 100.0,
                "weight": 0.30,
                "market_value": 300.0,
                "sector": "Financial Services",
            },
        }
    }
    open_runtime = {
        "portfolio_overlay": {
            "portfolio_objective": "defensive_convexity",
            "hedge_intensity": 0.9,
            "weekly_hedge_targets": ["NIFTY"],
        },
        "open_positions": [
            {
                "position_id": "POS1",
                "strategy_type": "bear_put_spread",
                "underlying": "NIFTY",
                "entry_credit_debit": 120.0,
                "current_value": 135.0,
                "max_loss": 120.0,
                "greeks": {"delta": -0.25, "gamma": 0.02, "vega": 0.30, "theta": -0.05},
                "metadata": {
                    "objective": "protect_core",
                    "prs_symbol": "OPT::NIFTY::POS1",
                    "prs_position_key": "POS1",
                },
            }
        ],
        "closed_positions": [],
    }

    prs = _make_prs(tmp_path)
    try:
        first = sync_options_runtime_book(
            prs,
            runtime_payload=open_runtime,
            current_positions_payload=core_payload,
        )
        assert first["trade_events"] == 1
    finally:
        prs.close()

    _overwrite_latest_snapshot_holdings(db_path, {})

    prs = _make_prs(tmp_path)
    try:
        rerun = sync_options_runtime_book(
            prs,
            runtime_payload=open_runtime,
            current_positions_payload=core_payload,
        )
        assert rerun["trade_events"] == 1
    finally:
        prs.close()

    with sqlite3.connect(str(db_path)) as con:
        lifecycle_open = con.execute(
            "select count(*) from position_lifecycle_table where close_event_id is null"
        ).fetchone()[0]
        distinct_keys = con.execute(
            "select count(distinct position_key) from position_lifecycle_table where close_event_id is null"
        ).fetchone()[0]

    assert lifecycle_open == 1
    assert distinct_keys == 1
