from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd

from scripts import preopen_checks as preopen_mod


def _write_runtime_db(
    db_path: Path,
    *,
    event_timestamps: list[str],
    holdings: dict[str, dict[str, object]],
) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    try:
        con.execute(
            """
            CREATE TABLE portfolio_events (
                event_id INTEGER PRIMARY KEY,
                timestamp_utc TEXT NOT NULL,
                trigger_reason_code TEXT NOT NULL
            )
            """
        )
        con.execute(
            """
            CREATE TABLE portfolio_snapshots (
                snapshot_id INTEGER PRIMARY KEY,
                state_json TEXT NOT NULL
            )
            """
        )
        for idx, ts in enumerate(event_timestamps, start=1):
            con.execute(
                """
                INSERT INTO portfolio_events(event_id, timestamp_utc, trigger_reason_code)
                VALUES (?, ?, ?)
                """,
                (idx, ts, "rebalance.core.sync"),
            )
        con.execute(
            """
            INSERT INTO portfolio_snapshots(snapshot_id, state_json)
            VALUES (?, ?)
            """,
            (1, json.dumps({"holdings": holdings})),
        )
        con.commit()
    finally:
        con.close()


def _write_current_positions(project_root: Path, *, cash: float, positions_count: int, total_value: float) -> None:
    path = project_root / "data/portfolio/current_positions.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "cash": cash,
                "positions_count": positions_count,
                "total_value": total_value,
                "positions": {f"POS{i}": {} for i in range(positions_count)},
                "performance": {"total_pnl": total_value - 1_000.0},
            }
        ),
        encoding="utf-8",
    )


def _write_master_ledger(project_root: Path, *, notional_rows: list[float]) -> None:
    path = project_root / "data/pnl/master_ledger.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "entry_type": "EQUITY_BUY",
                "notional": notional,
                "transaction_cost": 0.0,
                "trade_date": "2026-03-20T03:45:00+00:00",
            }
            for notional in notional_rows
        ]
    ).to_parquet(path, index=False)


def test_compute_runtime_accounting_sanity_passes(tmp_path: Path) -> None:
    project_root = tmp_path
    runtime_db_path = project_root / "data/runtime/portfolio_runtime.db"
    _write_runtime_db(
        runtime_db_path,
        event_timestamps=[
            "2026-03-20T03:45:00+00:00",
            "2026-03-20T03:46:00+00:00",
        ],
        holdings={
            "ABB.NS": {"instrument_type": "equity", "quantity": 2.0},
            "VEDL.NS": {"instrument_type": "equity", "quantity": 1.0},
        },
    )
    _write_current_positions(project_root, cash=600.0, positions_count=2, total_value=1_010.0)
    _write_master_ledger(project_root, notional_rows=[200.0, 200.0])

    report = preopen_mod.compute_runtime_accounting_sanity(
        project_root,
        trade_date_ist=date(2026, 3, 20),
    )

    assert report["status"] == "PASS"
    assert report["core_sync_batch_count"] == 1
    assert report["runtime_holdings_count"] == 2
    assert report["current_positions_count"] == 2
    assert report["ledger_cash"] == 600.0
    assert report["issues"] == []


def test_compute_runtime_accounting_sanity_flags_duplicate_batch_and_mismatch(tmp_path: Path) -> None:
    project_root = tmp_path
    runtime_db_path = project_root / "data/runtime/portfolio_runtime.db"
    _write_runtime_db(
        runtime_db_path,
        event_timestamps=[
            "2026-03-20T03:45:00+00:00",
            "2026-03-20T03:46:00+00:00",
            "2026-03-20T03:55:30+00:00",
        ],
        holdings={
            "ABB.NS": {"instrument_type": "equity", "quantity": 2.0},
        },
    )
    _write_current_positions(project_root, cash=650.0, positions_count=2, total_value=1_010.0)
    _write_master_ledger(project_root, notional_rows=[200.0, 200.0])

    report = preopen_mod.compute_runtime_accounting_sanity(
        project_root,
        trade_date_ist=date(2026, 3, 20),
    )

    assert report["status"] == "FAIL"
    assert report["core_sync_batch_count"] == 2
    assert any("batch count 2" in issue for issue in report["issues"])
    assert any("ledger cash mismatch" in issue for issue in report["issues"])
    assert any("runtime holdings count mismatch" in issue for issue in report["issues"])


def test_compute_runtime_accounting_sanity_respects_explicit_cash_seed(tmp_path: Path) -> None:
    project_root = tmp_path
    runtime_db_path = project_root / "data/runtime/portfolio_runtime.db"
    _write_runtime_db(
        runtime_db_path,
        event_timestamps=[
            "2026-03-20T03:45:00+00:00",
            "2026-03-20T03:46:00+00:00",
        ],
        holdings={
            "ABB.NS": {"instrument_type": "equity", "quantity": 2.0},
            "VEDL.NS": {"instrument_type": "equity", "quantity": 1.0},
        },
    )
    _write_current_positions(project_root, cash=600.0, positions_count=2, total_value=1_010.0)

    ledger_path = project_root / "data/pnl/master_ledger.parquet"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "entry_type": "CASH_IN",
                "notional": 1_000.0,
                "transaction_cost": 0.0,
                "trade_date": "2026-03-18T03:45:00+00:00",
            },
            {
                "entry_type": "EQUITY_BUY",
                "notional": 200.0,
                "transaction_cost": 0.0,
                "trade_date": "2026-03-20T03:45:00+00:00",
            },
            {
                "entry_type": "EQUITY_BUY",
                "notional": 200.0,
                "transaction_cost": 0.0,
                "trade_date": "2026-03-20T03:46:00+00:00",
            },
        ]
    ).to_parquet(ledger_path, index=False)

    report = preopen_mod.compute_runtime_accounting_sanity(
        project_root,
        trade_date_ist=date(2026, 3, 20),
    )

    assert report["status"] == "PASS"
    assert report["ledger_cash"] == 600.0
