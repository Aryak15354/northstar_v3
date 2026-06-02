from __future__ import annotations

import logging
from datetime import date
from types import SimpleNamespace

from scripts import run_trading_day_orchestrator as orch


def test_runtime_sync_bundle_includes_no_edge_and_canonical_sync(monkeypatch, tmp_path) -> None:
    steps = []
    statuses = []

    def fake_run_step(logger, step_name, cmd, log_path, timeout_seconds):
        steps.append((step_name, cmd))
        return True

    def fake_update_runtime_status(status_path, timezone_name, session_date, stage, processes, details=None):
        statuses.append((stage, details or {}))

    monkeypatch.setattr(orch, "_run_step", fake_run_step)
    monkeypatch.setattr(orch, "_update_runtime_status", fake_update_runtime_status)

    args = SimpleNamespace(
        python_bin="python",
        timezone="Asia/Kolkata",
        runtime_sync_timeout_seconds=900,
    )

    orch._run_runtime_sync_bundle(
        logging.getLogger("test"),
        args,
        date(2026, 3, 21),
        tmp_path / "status.json",
    )

    step_names = [name for name, _ in steps]
    assert "no_edge_refresh" in step_names
    assert "canonical_state_sync" in step_names
    assert statuses[-1][1]["no_edge_refresh_ok"] is True
    assert statuses[-1][1]["canonical_state_sync_ok"] is True


def test_market_once_command_uses_fast_recovery_flags() -> None:
    args = SimpleNamespace(python_bin="python")
    cmd = orch._build_market_once_command(args)

    assert "--once" in cmd
    assert "--allow-outside-market-hours" in cmd
