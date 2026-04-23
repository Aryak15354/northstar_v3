from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import pandas as pd


def _load_module(module_path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_bootstrap_module():
    return _load_module(Path("scripts/ci/bootstrap_runtime_gate_state.py"), "runtime_gate_bootstrap")


def test_bootstrap_runtime_gate_state_write_and_verify(tmp_path):
    module = _load_bootstrap_module()

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    sample = scripts_dir / "sample.py"
    sample.write_text("print('ok')\n", encoding="utf-8")

    live_dir = tmp_path / "data" / "options" / "live"
    baseline_path = live_dir / "gate_code_freeze_baseline.json"

    module.PROJECT_ROOT = tmp_path
    module.LIVE_DIR = live_dir
    module.BASELINE_PATH = baseline_path
    module.BOOTSTRAP_MANIFEST_PATH = live_dir / "runtime_gate_ci_bootstrap.json"
    module.RUNTIME_STATE_PATH = live_dir / "options_runtime_state.json"
    module.DASHBOARD_STATE_PATH = live_dir / "options_dashboard_state.json"
    module.GOVERNANCE_EVENTS_PATH = live_dir / "governance_events.parquet"
    module.RUNNER_STATUS_PATH = live_dir / "full_gate_runner_status.json"
    module.DAEMON_STATUS_PATH = live_dir / "northstar_daemon_status.json"
    module.WAL_PATH = live_dir / "write_journal.log"
    module.MARKET_DATA_PATH = live_dir / "market_data_latest.json"
    module.TRADE_LEDGER_PATH = tmp_path / "data/options/trade_ledger.parquet"
    module.RUNTIME_DB_PATH = tmp_path / "data/runtime/portfolio_runtime.db"
    module.TEST_COUNT_BASELINE_PATH = tmp_path / "data/processed/test_count_baseline.json"
    module.CODE_FREEZE_DIRS = [scripts_dir]

    written = module.write_baseline()
    assert baseline_path.exists()
    assert written["file_count"] == 1
    assert (live_dir / "runtime_gate_ci_bootstrap.json").exists()
    assert (live_dir / "options_runtime_state.json").exists()
    assert (live_dir / "options_dashboard_state.json").exists()
    assert (live_dir / "governance_events.parquet").exists()
    assert (tmp_path / "data/options/trade_ledger.parquet").exists()
    assert (tmp_path / "data/runtime/portfolio_runtime.db").exists()
    assert (tmp_path / "data/processed/test_count_baseline.json").exists()

    verified = module.verify_baseline()
    assert verified["status"] == "pass"
    assert verified["changed_files_count"] == 0

    sample.write_text("print('changed')\n", encoding="utf-8")

    verified_changed = module.verify_baseline()
    assert verified_changed["status"] == "fail"
    assert verified_changed["changed_files_count"] == 1
    assert verified_changed["changed_files_sample"] == ["scripts/sample.py"]


def test_bootstrap_runtime_gate_state_satisfies_gate_triage_contract(tmp_path):
    bootstrap = _load_bootstrap_module()
    gate_triage = _load_module(Path("scripts/gate_triage.py"), "runtime_gate_triage")

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "sample.py").write_text("print('ok')\n", encoding="utf-8")

    bootstrap.PROJECT_ROOT = tmp_path
    bootstrap.LIVE_DIR = tmp_path / "data" / "options" / "live"
    bootstrap.BASELINE_PATH = bootstrap.LIVE_DIR / "gate_code_freeze_baseline.json"
    bootstrap.BOOTSTRAP_MANIFEST_PATH = bootstrap.LIVE_DIR / "runtime_gate_ci_bootstrap.json"
    bootstrap.RUNTIME_STATE_PATH = bootstrap.LIVE_DIR / "options_runtime_state.json"
    bootstrap.DASHBOARD_STATE_PATH = bootstrap.LIVE_DIR / "options_dashboard_state.json"
    bootstrap.GOVERNANCE_EVENTS_PATH = bootstrap.LIVE_DIR / "governance_events.parquet"
    bootstrap.RUNNER_STATUS_PATH = bootstrap.LIVE_DIR / "full_gate_runner_status.json"
    bootstrap.DAEMON_STATUS_PATH = bootstrap.LIVE_DIR / "northstar_daemon_status.json"
    bootstrap.WAL_PATH = bootstrap.LIVE_DIR / "write_journal.log"
    bootstrap.MARKET_DATA_PATH = bootstrap.LIVE_DIR / "market_data_latest.json"
    bootstrap.TRADE_LEDGER_PATH = tmp_path / "data/options/trade_ledger.parquet"
    bootstrap.RUNTIME_DB_PATH = tmp_path / "data/runtime/portfolio_runtime.db"
    bootstrap.TEST_COUNT_BASELINE_PATH = tmp_path / "data/processed/test_count_baseline.json"
    bootstrap.CODE_FREEZE_DIRS = [scripts_dir]
    bootstrap.write_baseline()

    gate_triage.PROJECT_ROOT = tmp_path
    gate_triage.LIVE_DIR = bootstrap.LIVE_DIR
    gate_triage.RUNTIME_PATH = bootstrap.RUNTIME_STATE_PATH
    gate_triage.WAL_PATH = bootstrap.WAL_PATH
    gate_triage.DAEMON_STATUS_PATH = bootstrap.DAEMON_STATUS_PATH
    gate_triage.RUNNER_STATUS_PATH = bootstrap.RUNNER_STATUS_PATH
    gate_triage.GOV_EVENTS_PATH = bootstrap.GOVERNANCE_EVENTS_PATH
    gate_triage.DAEMON_LOCK_PATH = bootstrap.LIVE_DIR / "northstar_daemon.lock"
    gate_triage.ENGINE_LOCK_PATH = bootstrap.LIVE_DIR / "options_engine.lock"
    gate_triage.CODE_FREEZE_BASELINE_PATH = bootstrap.BASELINE_PATH
    gate_triage.CODE_FREEZE_DIRS = [scripts_dir]

    report = gate_triage.run_triage()
    statuses = {item["check"]: item["status"] for item in report["checks"]}

    assert statuses["runtime_schema"] == "pass"
    assert statuses["wal"] == "pass"
    assert statuses["lock_acquisition"] == "pass"
    assert statuses["mode_transitions"] == "pass"
    assert "runtime_schema" not in report["fail_reasons"]
    assert "mode_transitions" not in report["fail_reasons"]


def test_ci_health_checks_accept_bootstrap_without_live_broker_secret(tmp_path, monkeypatch):
    bootstrap = _load_bootstrap_module()
    run_module = _load_module(Path("run.py"), "northstar_run")

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "sample.py").write_text("print('ok')\n", encoding="utf-8")

    bootstrap.PROJECT_ROOT = tmp_path
    bootstrap.LIVE_DIR = tmp_path / "data" / "options" / "live"
    bootstrap.BASELINE_PATH = bootstrap.LIVE_DIR / "gate_code_freeze_baseline.json"
    bootstrap.BOOTSTRAP_MANIFEST_PATH = bootstrap.LIVE_DIR / "runtime_gate_ci_bootstrap.json"
    bootstrap.RUNTIME_STATE_PATH = bootstrap.LIVE_DIR / "options_runtime_state.json"
    bootstrap.DASHBOARD_STATE_PATH = bootstrap.LIVE_DIR / "options_dashboard_state.json"
    bootstrap.GOVERNANCE_EVENTS_PATH = bootstrap.LIVE_DIR / "governance_events.parquet"
    bootstrap.RUNNER_STATUS_PATH = bootstrap.LIVE_DIR / "full_gate_runner_status.json"
    bootstrap.DAEMON_STATUS_PATH = bootstrap.LIVE_DIR / "northstar_daemon_status.json"
    bootstrap.WAL_PATH = bootstrap.LIVE_DIR / "write_journal.log"
    bootstrap.MARKET_DATA_PATH = bootstrap.LIVE_DIR / "market_data_latest.json"
    bootstrap.TRADE_LEDGER_PATH = tmp_path / "data/options/trade_ledger.parquet"
    bootstrap.RUNTIME_DB_PATH = tmp_path / "data/runtime/portfolio_runtime.db"
    bootstrap.TEST_COUNT_BASELINE_PATH = tmp_path / "data/processed/test_count_baseline.json"
    bootstrap.CODE_FREEZE_DIRS = [scripts_dir]
    bootstrap.write_baseline()

    ledger_path = tmp_path / "data/pnl/master_ledger.parquet"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "entry_type": "CASH_IN",
                "amount": 1_000_000.0,
            }
        ]
    ).to_parquet(ledger_path, index=False)

    guide_path = tmp_path / "docs/operations/WORKSPACE_GUIDE.md"
    guide_path.parent.mkdir(parents=True, exist_ok=True)
    guide_path.write_text("CI runtime gate guide\n", encoding="utf-8")

    run_module.PROJECT_ROOT = tmp_path
    run_module.MASTER_LEDGER_FILE = ledger_path
    run_module.WORKSPACE_GUIDE_FILE = guide_path
    run_module.TEST_COUNT_BASELINE_FILE = bootstrap.TEST_COUNT_BASELINE_PATH
    run_module.CI_BOOTSTRAP_MANIFEST_FILE = bootstrap.BOOTSTRAP_MANIFEST_PATH
    run_module.MARKET_DATA_CANDIDATES = [bootstrap.MARKET_DATA_PATH]

    monkeypatch.delenv("UPSTOX_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("NORTHSTAR_CI_GATE", "1")

    report = run_module._summarize_health_checks(run_module._collect_health_checks())
    checks = {item["check"]: item for item in report["checks"]}

    assert report["hard_failures"] == []
    assert checks["broker_connectivity"]["status"] == "pass"
    assert checks["market_data_freshness"]["status"] == "pass"
    assert checks["test_count_drift"]["status"] == "pass"


def test_ci_gate_quick_stage_plan_is_deterministic(monkeypatch):
    run_complete = _load_module(Path("scripts/run_complete_v3_system.py"), "complete_v3_runner")

    args = argparse.Namespace(
        dashboard_only=False,
        quick=True,
        force_gst=False,
        alt_start_year=2024,
        alt_end_year=2026,
        include_announcements=False,
        screener_max_tickers=0,
        date="today",
        news_sources="nse,rss",
        news_max_tickers=0,
        news_max_months=0,
        data_only=False,
        proof_level="standard",
    )

    monkeypatch.setenv("NORTHSTAR_CI_GATE", "1")

    stages = run_complete.stage_plan(args)
    stage_names = [stage["name"] for stage in stages]

    assert stage_names == ["Market Refresh", "Market Data Freshness"]


def test_bootstrap_runtime_db_supports_alpha_diagnostics_smoke(tmp_path):
    bootstrap = _load_bootstrap_module()
    diagnostics = _load_module(Path("src/diagnostics/alpha_diagnostics_engine.py"), "alpha_diagnostics_engine")
    from src.runtime import PortfolioRuntimeService, RuntimeEventStore

    assert RuntimeEventStore is not None

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "sample.py").write_text("print('ok')\n", encoding="utf-8")

    bootstrap.PROJECT_ROOT = tmp_path
    bootstrap.LIVE_DIR = tmp_path / "data" / "options" / "live"
    bootstrap.BASELINE_PATH = bootstrap.LIVE_DIR / "gate_code_freeze_baseline.json"
    bootstrap.BOOTSTRAP_MANIFEST_PATH = bootstrap.LIVE_DIR / "runtime_gate_ci_bootstrap.json"
    bootstrap.RUNTIME_STATE_PATH = bootstrap.LIVE_DIR / "options_runtime_state.json"
    bootstrap.DASHBOARD_STATE_PATH = bootstrap.LIVE_DIR / "options_dashboard_state.json"
    bootstrap.GOVERNANCE_EVENTS_PATH = bootstrap.LIVE_DIR / "governance_events.parquet"
    bootstrap.RUNNER_STATUS_PATH = bootstrap.LIVE_DIR / "full_gate_runner_status.json"
    bootstrap.DAEMON_STATUS_PATH = bootstrap.LIVE_DIR / "northstar_daemon_status.json"
    bootstrap.WAL_PATH = bootstrap.LIVE_DIR / "write_journal.log"
    bootstrap.MARKET_DATA_PATH = bootstrap.LIVE_DIR / "market_data_latest.json"
    bootstrap.TRADE_LEDGER_PATH = tmp_path / "data/options/trade_ledger.parquet"
    bootstrap.RUNTIME_DB_PATH = tmp_path / "data/runtime/portfolio_runtime.db"
    bootstrap.TEST_COUNT_BASELINE_PATH = tmp_path / "data/processed/test_count_baseline.json"
    bootstrap.CODE_FREEZE_DIRS = [scripts_dir]
    bootstrap.write_baseline()

    paths = diagnostics.DiagnosticsPaths(
        runtime_db=str(bootstrap.RUNTIME_DB_PATH),
        diagnostics_db=str(tmp_path / "data/diagnostics/alpha_diagnostics.db"),
        alpha_metrics_parquet=str(tmp_path / "data/diagnostics/alpha_metrics.parquet"),
        strategy_metrics_parquet=str(tmp_path / "data/diagnostics/strategy_metrics.parquet"),
        policy_recommendations_json=str(tmp_path / "data/diagnostics/policy_recommendations.json"),
    )
    engine = diagnostics.AlphaDiagnosticsEngine(paths)
    try:
        trades = engine.compute_trade_diagnostics()
        strategies = engine.compute_strategy_diagnostics()
        portfolio = engine.compute_portfolio_diagnostics()
    finally:
        engine.close()

    prs = PortfolioRuntimeService(
        db_path=str(bootstrap.RUNTIME_DB_PATH),
        materialized_output_dir=str(tmp_path / "data/processed/runtime"),
    )
    try:
        replay = prs.replay()
    finally:
        prs.close()

    assert trades.empty
    assert strategies.empty
    assert len(portfolio) == 1
    assert replay["deterministic_match"] is True
