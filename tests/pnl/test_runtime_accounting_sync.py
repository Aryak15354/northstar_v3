from __future__ import annotations

import json

import pandas as pd

from src.pnl import runtime_accounting_sync as sync_mod
from src.pnl.runtime_accounting_sync import (
    _build_cash_seed_rows,
    _build_equity_rows,
    _canonical_total_value,
    _strip_regenerated_rows,
)


def test_strip_regenerated_rows_removes_runtime_fill_rows() -> None:
    df = pd.DataFrame(
        [
            {
                "entry_id": "RUNTIME_EQUITY_FILL_417",
                "entry_type": "EQUITY_BUY",
                "book": "EQUITY",
                "ticker": "ABB.NS",
                "source": "PRS_SYNC",
                "notes": "Canonical core equity rebalance fill from portfolio_events 417: rebalance.core.sync",
            },
            {
                "entry_id": "ACCOUNTING_EQUITY_MTM_20260319",
                "entry_type": "EQUITY_MTM",
                "book": "EQUITY",
                "ticker": "PORTFOLIO",
                "source": "ACCOUNTING_SYNC",
                "notes": "Canonical equity mark from portfolio pnl_on_paper",
            },
            {
                "entry_id": "LIVE_OPTIONS_1",
                "entry_type": "OPTIONS_SELL",
                "book": "OPTIONS",
                "ticker": "NIFTY",
                "source": "LIVE",
                "notes": "Real options close",
            },
        ]
    )

    cleaned = _strip_regenerated_rows(df)

    assert cleaned["entry_id"].tolist() == ["LIVE_OPTIONS_1"]


def test_canonical_total_value_prefers_repaired_current_positions(
    tmp_path,
    monkeypatch,
) -> None:
    current_positions = tmp_path / "current_positions.json"
    unified_state = tmp_path / "unified_state.json"

    current_positions.write_text(json.dumps({"total_value": 9_828_570.11}), encoding="utf-8")
    unified_state.write_text(
        json.dumps(
            {
                "portfolio": {"total_value": 9_700_000.0},
                "governor_state": {"total_capital_inr": 9_784_989.03},
                "pnl_state": {"current_nav_inr": 9_784_989.03},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(sync_mod, "CURRENT_POSITIONS_PATH", current_positions)
    monkeypatch.setattr(sync_mod, "UNIFIED_STATE_PATH", unified_state)

    assert _canonical_total_value(default_capital=10_000_000.0) == 9_828_570.11


def test_build_equity_rows_overrides_latest_mark_from_current_positions(
    tmp_path,
    monkeypatch,
) -> None:
    pnl_path = tmp_path / "pnl_on_paper.parquet"
    current_positions = tmp_path / "current_positions.json"

    pd.DataFrame(
        [
            {"Date": "2026-03-18", "Equity": 1000.0},
            {"Date": "2026-03-19", "Equity": 1000.0},
        ]
    ).to_parquet(pnl_path, index=False)
    current_positions.write_text(
        json.dumps(
            {
                "timestamp": "2026-03-19T21:32:48.439534+00:00",
                "cash": 600.0,
                "invested_value": 420.0,
                "options_market_value": 0.0,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(sync_mod, "EQUITY_PNL_PATH", pnl_path)
    monkeypatch.setattr(sync_mod, "CURRENT_POSITIONS_PATH", current_positions)

    rows = _build_equity_rows(
        {
            "pnl": {
                "nav": {
                    "starting_capital_inr": 1_000.0,
                    "inception_date": "2026-03-18",
                }
            }
        }
    )

    assert rows[-1]["entry_id"] == "ACCOUNTING_EQUITY_MTM_20260319"
    assert rows[-1]["price"] == 1020.0
    assert rows[-1]["notional"] == 1020.0
    assert rows[-1]["unrealized_pnl_change"] == 20.0


def test_build_cash_seed_rows_adds_initial_deposit_when_missing() -> None:
    rows = _build_cash_seed_rows(
        {
            "pnl": {
                "nav": {
                    "starting_capital_inr": 10_000_000.0,
                    "inception_date": "2025-10-01",
                }
            }
        },
        pd.DataFrame(),
    )

    assert len(rows) == 1
    assert rows[0]["entry_type"] == "CASH_IN"
    assert rows[0]["book"] == "CASH"
    assert rows[0]["notional"] == 10_000_000.0


def test_build_cash_seed_rows_skips_when_cash_entry_already_exists() -> None:
    existing = pd.DataFrame(
        [
            {
                "entry_id": "ACCOUNTING_CASH_IN_20251001",
                "entry_type": "CASH_IN",
                "book": "CASH",
            }
        ]
    )

    rows = _build_cash_seed_rows(
        {
            "pnl": {
                "nav": {
                    "starting_capital_inr": 10_000_000.0,
                    "inception_date": "2025-10-01",
                }
            }
        },
        existing,
    )

    assert rows == []
