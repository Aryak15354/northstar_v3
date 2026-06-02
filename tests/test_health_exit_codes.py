from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pandas as pd

import run as run_mod
from scripts import preopen_checks as preopen_mod


def _invoke_health(monkeypatch, checks: list[dict]) -> int:
    monkeypatch.setattr(run_mod, "_collect_health_checks", lambda verbose=False: checks)
    monkeypatch.setattr(run_mod, "_run_subprocess", lambda *args, **kwargs: True)
    monkeypatch.setattr(run_mod, "_ensure_archive_isolation", lambda: (True, ""))
    monkeypatch.setattr(
        run_mod,
        "_load_freeze_state",
        lambda: {"freeze_active": False, "triggers": []},
    )
    monkeypatch.setattr(sys, "argv", ["run.py", "--mode", "health"])
    return run_mod.main()


def _write_runtime_db(db_path: Path, holdings: dict[str, dict[str, object]]) -> None:
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


def _write_current_positions(
    project_root: Path,
    *,
    cash: float,
    positions_count: int,
    total_value: float,
) -> None:
    path = project_root / "data/portfolio/current_positions.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "cash": cash,
                "positions_count": positions_count,
                "total_value": total_value,
                "positions": {"A": {}, "B": {}},
                "performance": {"total_pnl": 0.0},
            }
        ),
        encoding="utf-8",
    )


def _write_empty_ledger(project_root: Path) -> None:
    path = project_root / "data/pnl/master_ledger.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(columns=["entry_type", "notional", "transaction_cost", "trade_date"]).to_parquet(
        path,
        index=False,
    )


def test_health_check_with_missing_broker_token_exits_one(monkeypatch) -> None:
    checks = [
        run_mod._health_check_result(
            "broker_connectivity",
            "fail",
            "critical",
            "Broker token rejected.",
        ),
        run_mod._health_check_result(
            "market_data_freshness",
            "pass",
            "critical",
            "Market data fresh.",
        ),
        run_mod._health_check_result(
            "ledger_integrity",
            "pass",
            "critical",
            "Ledger integrity clean.",
        ),
    ]

    assert _invoke_health(monkeypatch, checks) == 1


def test_health_check_with_code_freeze_only_exits_zero(monkeypatch) -> None:
    checks = [
        run_mod._health_check_result(
            "broker_connectivity",
            "pass",
            "critical",
            "Broker token valid.",
        ),
        run_mod._health_check_result(
            "market_data_freshness",
            "pass",
            "critical",
            "Market data fresh.",
        ),
        run_mod._health_check_result(
            "ledger_integrity",
            "pass",
            "critical",
            "Ledger integrity clean.",
        ),
        run_mod._health_check_result(
            "code_freeze",
            "warn",
            "warning",
            "Code freeze baseline missing.",
        ),
    ]

    assert _invoke_health(monkeypatch, checks) == 0


def test_pre_market_runtime_accounting_skips_missing_same_day_batch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_runtime_db(
        tmp_path / "data/runtime/portfolio_runtime.db",
        {
            "ABB.NS": {"instrument_type": "equity", "quantity": 2.0},
            "VEDL.NS": {"instrument_type": "equity", "quantity": 1.0},
        },
    )
    _write_current_positions(tmp_path, cash=1_000.0, positions_count=2, total_value=1_000.0)
    _write_empty_ledger(tmp_path)
    monkeypatch.setattr(preopen_mod, "_is_pre_market_ist", lambda now=None: True)

    report = preopen_mod.compute_runtime_accounting_sanity(
        tmp_path,
        trade_date_ist=date(2026, 3, 20),
    )

    assert report["status"] == "SKIP"
    assert report["issues"] == []
    assert "same_day_core_sync_not_expected_pre_market" in report["skipped_checks"]
