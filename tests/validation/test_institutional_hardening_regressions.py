from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from src.intelligence.market_brain.market_tensor import MarketTensorEngine
from src.validation.institutional_hardening import (
    _latest_weekly_summary,
    audit_survivorship_bias,
    evaluate_freeze_state,
    reconcile_nav_ledgers,
    validate_allocator_universe_alignment,
    validate_exposure_cash_contract,
)
from src.validation.universe_manager import UniverseManager


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def test_market_tensor_save_emits_canonical_date_column(tmp_path: Path) -> None:
    engine = MarketTensorEngine()
    engine.paths["output"] = str(tmp_path / "data/processed/market_tensor.parquet")
    engine.paths["metadata"] = str(tmp_path / "data/processed/market_tensor_metadata.json")

    idx = pd.date_range("2026-01-04", periods=4, freq="W")
    tensor = pd.DataFrame({"macro_signal": [0.1, 0.2, -0.1, 0.0]}, index=idx)
    components = {"monetary": tensor.copy()}

    engine.save_market_tensor(tensor, components)

    raw = pd.read_parquet(engine.paths["output"])
    assert "date" in raw.columns
    assert pd.api.types.is_datetime64_any_dtype(raw["date"])

    loaded = engine.load_market_tensor()
    assert "date" not in loaded.columns
    assert isinstance(loaded.index, pd.DatetimeIndex)
    assert loaded.index.name == "date"


def test_nav_reconciliation_flags_material_mismatch(tmp_path: Path) -> None:
    prices_path = tmp_path / "data/processed/prices.parquet"
    weekly_dir = tmp_path / "data/portfolio/weekly"
    paper_nav_path = tmp_path / "data/portfolio/pnl_on_paper.parquet"
    weekly_dir.mkdir(parents=True, exist_ok=True)
    paper_nav_path.parent.mkdir(parents=True, exist_ok=True)
    prices_path.parent.mkdir(parents=True, exist_ok=True)

    prices = pd.DataFrame(
        {
            "Date": pd.date_range("2026-01-01", periods=5, freq="D"),
            "ticker": ["AAA"] * 5,
            "Close": [100.0, 101.0, 102.0, 103.0, 104.0],
        }
    )
    prices.to_parquet(prices_path, index=False)

    weekly = pd.DataFrame({"ticker": ["AAA"], "weight": [1.0]})
    weekly.to_parquet(weekly_dir / "2026-01-01.parquet", index=False)

    # Deliberately inconsistent with recomputed NAV to force a reconciliation fail.
    paper_nav = pd.DataFrame(
        {
            "Date": pd.date_range("2026-01-01", periods=5, freq="D"),
            "Equity": [100.0, 135.0, 150.0, 170.0, 185.0],
        }
    )
    paper_nav.to_parquet(paper_nav_path, index=False)

    result = reconcile_nav_ledgers(tmp_path)
    assert result["status"] == "fail"
    assert float(result["mismatch_bps"]) > 100.0


def test_freeze_state_is_deterministic_for_same_inputs(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "data/processed/portfolio_analytics.json",
        {"max_drawdown": -0.08, "sharpe_ratio": 1.25},
    )
    drift = {"severity": "normal", "flags": []}
    nav_recon = {"status": "fail", "mismatch_bps": 250.0}

    state_a = evaluate_freeze_state(tmp_path, drift=drift, nav_recon=nav_recon)
    state_b = evaluate_freeze_state(tmp_path, drift=drift, nav_recon=nav_recon)

    comp_a = {k: v for k, v in state_a.items() if k != "timestamp"}
    comp_b = {k: v for k, v in state_b.items() if k != "timestamp"}
    assert comp_a == comp_b
    assert state_a["freeze_active"] is True
    assert "nav_mismatch_gt_100bps" in state_a["triggers"]
    assert state_a["actions"]["lock_new_risk"] is True
    assert state_a["actions"]["require_human_override"] is True


def test_exposure_cash_contract_detects_break_and_passes_when_aligned(tmp_path: Path) -> None:
    aligned = {
        "portfolio_summary": {
            "total_exposure": 0.0938123880,
            "cash": 0.9061876120,
        }
    }
    _write_json(tmp_path / "data/processed/portfolio_analytics.json", aligned)
    pass_result = validate_exposure_cash_contract(tmp_path)
    assert pass_result["status"] == "pass"

    broken = {
        "portfolio_summary": {
            "total_exposure": 0.0938123880,
            "cash": 0.50,
        }
    }
    _write_json(tmp_path / "data/processed/portfolio_analytics.json", broken)
    fail_result = validate_exposure_cash_contract(tmp_path)
    assert fail_result["status"] == "fail"
    assert float(fail_result["residual_bps"]) > 25.0


def test_latest_weekly_summary_uses_latest_embedded_date_not_mtime(tmp_path: Path) -> None:
    old_summary = tmp_path / "data/weekly_insights/2006/summary.parquet"
    new_summary = tmp_path / "data/weekly_insights/2025/summary.parquet"
    old_summary.parent.mkdir(parents=True, exist_ok=True)
    new_summary.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame({"date": [pd.Timestamp("2006-12-31")] * 3}).to_parquet(old_summary, index=False)
    pd.DataFrame({"date": [pd.Timestamp("2025-12-28")] * 3}).to_parquet(new_summary, index=False)

    # Force older-data file to have newer mtime to verify date-based selection.
    old_stat = old_summary.stat()
    new_stat = new_summary.stat()
    os.utime(old_summary, (max(new_stat.st_atime, old_stat.st_atime) + 1000, max(new_stat.st_mtime, old_stat.st_mtime) + 1000))

    selected = _latest_weekly_summary(tmp_path)
    assert selected == new_summary


def test_survivorship_bias_audit_warns_when_no_inactive_tickers(tmp_path: Path) -> None:
    prices_path = tmp_path / "data/processed/prices.parquet"
    prices_path.parent.mkdir(parents=True, exist_ok=True)

    dates = pd.date_range("2015-01-31", "2025-12-31", freq="ME")
    df = pd.DataFrame(
        {
            "Date": list(dates) + list(dates),
            "ticker": ["AAA"] * len(dates) + ["BBB"] * len(dates),
        }
    )
    df.to_parquet(prices_path, index=False)

    audit = audit_survivorship_bias(tmp_path)
    assert audit["status"] in {"warn", "fail"}
    assert "no_inactive_tickers_detected" in set(audit.get("issues", []))
    assert int(audit.get("official_delistings", {}).get("rows", -1)) == 0


def test_allocator_universe_alignment_fails_for_off_universe_symbols(tmp_path: Path) -> None:
    prices_path = tmp_path / "data/processed/prices.parquet"
    weights_path = tmp_path / "data/processed/portfolio_weights.parquet"
    prices_path.parent.mkdir(parents=True, exist_ok=True)

    prices = pd.DataFrame(
        {
            "Date": pd.date_range("2025-01-01", periods=5, freq="D"),
            "ticker": ["AAA.NS"] * 5,
            "Close": [100.0, 101.0, 99.0, 102.0, 103.0],
            "Volume": [1_000_000] * 5,
        }
    )
    prices.to_parquet(prices_path, index=False)

    weights = pd.DataFrame(
        {
            "date": [pd.Timestamp("2025-01-05")] * 3,
            "ticker": ["AAA.NS", "FAKE1.NS", "FAKE2.NS"],
            "weight": [0.5, 0.25, 0.25],
        }
    )
    weights.to_parquet(weights_path, index=False)

    alignment = validate_allocator_universe_alignment(tmp_path)
    assert alignment["status"] == "fail"
    assert int(alignment["off_universe_count"]) >= 2
    assert "FAKE1.NS" in set(alignment.get("off_universe_symbols", []))
    assert "FAKE2.NS" in set(alignment.get("off_universe_symbols", []))


def test_historical_universe_snapshots_respect_delisting_dates(tmp_path: Path) -> None:
    prices_path = tmp_path / "data/processed/prices.parquet"
    workbook_path = tmp_path / "universe/List of delisted Companies.xlsx"
    prices_path.parent.mkdir(parents=True, exist_ok=True)
    workbook_path.parent.mkdir(parents=True, exist_ok=True)

    dates = pd.date_range("2025-01-01", periods=5, freq="D")
    price_rows = []
    for ticker, base in [("AAA.NS", 100.0), ("DEL.NS", 50.0)]:
        for i, d in enumerate(dates):
            price_rows.append(
                {
                    "Date": d,
                    "ticker": ticker,
                    "Close": base + i,
                    "Volume": 1_000_000,
                }
            )
    pd.DataFrame(price_rows).to_parquet(prices_path, index=False)

    delisted_sheet = pd.DataFrame(
        {
            "Company Name": ["Delisted Co"],
            "Symbol": ["DEL"],
            "Delisted Date": [pd.Timestamp("2025-01-03")],
            "Type of Delisting": ["Compulsory Delisting"],
            "ISIN": [""],
            "Board": ["Main"],
            "Exit Price (Fair Value)": [0.0],
        }
    )
    with pd.ExcelWriter(workbook_path) as xls:
        delisted_sheet.to_excel(xls, sheet_name="delisted", index=False)

    um = UniverseManager(project_root=tmp_path)
    um.create_delisting_database(force_refresh=True)
    snapshots = um.build_historical_universe_snapshots(
        start_date=pd.Timestamp("2025-01-01"),
        end_date=pd.Timestamp("2025-01-05"),
        apply_liquidity_filter=False,
        apply_survivorship_filter=True,
    )

    snapshots["date"] = pd.to_datetime(snapshots["date"], errors="coerce")
    pre = snapshots[(snapshots["date"] == pd.Timestamp("2025-01-02")) & (snapshots["ticker"] == "DEL.NS")]
    post = snapshots[(snapshots["date"] == pd.Timestamp("2025-01-04")) & (snapshots["ticker"] == "DEL.NS")]

    assert not pre.empty
    assert post.empty
