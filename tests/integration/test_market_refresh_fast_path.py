from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pandas as pd


def _load_integrated_pipeline_module():
    module_path = Path("src/ingestion/integrated_data_pipeline.py")
    spec = importlib.util.spec_from_file_location("integrated_data_pipeline_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_run_complete_module():
    module_path = Path("scripts/run_complete_v3_system.py")
    spec = importlib.util.spec_from_file_location("run_complete_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_force_market_update_module():
    module_path = Path("scripts/force_market_update.py")
    spec = importlib.util.spec_from_file_location("force_market_update_module", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_integrated_pipeline_fast_market_refresh_skips_price_fetch(monkeypatch):
    module = _load_integrated_pipeline_module()
    pipeline = module.IntegratedDataPipeline()

    subprocess_called = {"value": False}
    fetch_called = {"value": False}

    def fake_run(*args, **kwargs):
        subprocess_called["value"] = True
        raise AssertionError("price_fetcher should not run in fast market refresh mode")

    def fake_fetch_market_indices():
        fetch_called["value"] = True
        return True

    monkeypatch.setenv("NORTHSTAR_FAST_MARKET_REFRESH", "1")
    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(pipeline, "fetch_market_indices", fake_fetch_market_indices)

    assert pipeline.update_yfinance_market_data() is True
    assert fetch_called["value"] is True
    assert subprocess_called["value"] is False


def test_run_command_stage_forces_unbuffered_env(monkeypatch, tmp_path):
    module = _load_run_complete_module()

    captured = {}

    class Completed:
        returncode = 0

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["env"] = kwargs.get("env")
        return Completed()

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    result = module.run_command_stage(
        name="Example",
        description="example",
        command=["python3", "-c", "print('ok')"],
        required=True,
        run_dir=tmp_path,
        dry_run=False,
        timeout_seconds=5,
    )

    assert result.status == "PASS"
    assert captured["env"]["PYTHONUNBUFFERED"] == "1"


def test_force_market_update_ci_fast_path_materializes_artifacts(tmp_path, monkeypatch):
    module = _load_force_market_update_module()

    module.PROJECT_ROOT = tmp_path
    module.STATUS_PATH = tmp_path / "data/processed/market_refresh_status.json"
    module.MARKET_DATA_PATH = tmp_path / "data/options/live/market_data_latest.json"
    module.MARKET_STATE_PATH = tmp_path / "data/processed/market_state.parquet"

    monkeypatch.setenv("NORTHSTAR_CI_GATE", "1")
    monkeypatch.delenv("NORTHSTAR_FAST_MARKET_REFRESH", raising=False)

    assert module.main() == 0

    assert module.STATUS_PATH.exists()
    assert module.MARKET_DATA_PATH.exists()
    assert module.MARKET_STATE_PATH.exists()

    status_payload = json.loads(module.STATUS_PATH.read_text(encoding="utf-8"))
    market_payload = json.loads(module.MARKET_DATA_PATH.read_text(encoding="utf-8"))
    market_state = pd.read_parquet(module.MARKET_STATE_PATH)

    assert status_payload["pipeline_status"] == "SUCCESS"
    assert status_payload["mode"] == "ci_fast_path"
    assert market_payload["refresh_mode"] == "ci_fast_path"
    assert len(market_state) == 1


def test_stage_plan_ci_gate_quick_skips_research_branch(monkeypatch):
    module = _load_run_complete_module()
    monkeypatch.setenv("NORTHSTAR_CI_GATE", "1")

    args = SimpleNamespace(
        dashboard_only=False,
        data_only=False,
        quick=True,
        force_gst=False,
        include_announcements=False,
        alt_start_year=2024,
        alt_end_year=2026,
        screener_max_tickers=0,
        news_sources="bse,rss",
        news_max_tickers=0,
        news_max_months=0,
        proof_level="standard",
        date="today",
    )

    names = [stage["name"] for stage in module.stage_plan(args)]

    assert "Research Surface" not in names
    assert "Strategy Backtests" not in names
    assert "Strategy Beliefs" not in names
    assert "Strategy Regret" not in names
    assert "Strategy Tailwinds" not in names
    assert "Capital Allocator" not in names
    assert "Live Scores" not in names
    assert "Canonical Datasets" not in names
    assert names[-1] == "Market Data Freshness"
