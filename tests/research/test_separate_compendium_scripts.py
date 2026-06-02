from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.kaggle.plan_2026_04_05.common import load_plan_dataset
from scripts.kaggle.plan_2026_04_08 import run_exp09, run_exp10, run_exp11, run_exp12, run_exp13, run_exp18
from scripts.kaggle.plan_2026_04_08.lib import (
    DEFAULT_CANONICAL_FACTOR_ALIASES,
    DEFAULT_EXP18_FIXED_EVENTS,
    _aligned_canonical_splits,
    _factor_alias_contract,
    _factor_event_table,
    resolve_capital_goods_tickers,
    resolve_financial_services_universes,
    resolve_it_tickers,
)


def _write_export(root: Path, *, features: pd.DataFrame, metadata: pd.DataFrame, regimes: pd.DataFrame, splits: list[dict]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    features.to_parquet(root / "northstar_features.parquet", index=False)
    metadata.to_parquet(root / "northstar_metadata.parquet", index=False)
    regimes.to_parquet(root / "northstar_regime_labels.parquet", index=False)
    (root / "northstar_walk_forward_splits.json").write_text(json.dumps(splits, indent=2), encoding="utf-8")
    (root / "weekly_export_manifest.json").write_text(json.dumps({"source": "synthetic"}, indent=2), encoding="utf-8")
    return root


def _build_dirty_sector_export(root: Path) -> Path:
    dates = pd.to_datetime(["2021-04-02", "2021-04-09", "2021-04-16", "2021-04-23"])
    tickers = [
        "BANK_A",
        "NBFC_A",
        "INS_A",
        "FS_MISC",
        "IT_A",
        "CG_A",
    ]
    features_rows: list[dict[str, object]] = []
    meta_rows: list[dict[str, object]] = []
    for idx, date in enumerate(dates):
        for t_idx, ticker in enumerate(tickers):
            base = float(idx + t_idx + 1)
            features_rows.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "target_weekly_return": 0.01 * base,
                    "eps_sue_decay": base,
                    "rev_sue_decay": base * 0.9,
                    "earnings_quality_ratio_cs_z": base * 0.5,
                    "agreement_score_cs_z": base * 0.4,
                    "piotroski_fscore_cs_z": base * 0.3,
                    "bulk_net_pressure_21d_cs_z": base * 0.2,
                    "rbi_rate_chg": 0.25 if idx % 2 == 0 else 0.0,
                    "inrusd_4w_return": 0.1 * idx,
                    "steel_4w_return": 0.2 * idx,
                }
            )
            if ticker == "BANK_A":
                meta_rows.append({"date": date, "ticker": ticker, "sector": "Other", "subsector": "Private Sector Bank", "broad_sector": "Financial Services"})
            elif ticker == "NBFC_A":
                meta_rows.append({"date": date, "ticker": ticker, "sector": "Other", "subsector": "Gold Loan NBFC", "broad_sector": "Financial Services"})
            elif ticker == "INS_A":
                meta_rows.append({"date": date, "ticker": ticker, "sector": "Other", "subsector": "Life Insurance", "broad_sector": "Financial Services"})
            elif ticker == "FS_MISC":
                meta_rows.append({"date": date, "ticker": ticker, "sector": "Other", "subsector": "See Industry Column", "broad_sector": "Financial Services"})
            elif ticker == "IT_A":
                meta_rows.append({"date": date, "ticker": ticker, "sector": "Consumer Goods", "subsector": "See Industry Column", "broad_sector": "Information Technology"})
            else:
                meta_rows.append({"date": date, "ticker": ticker, "sector": "Information Technology", "subsector": "See Industry Column", "broad_sector": "Capital Goods"})

    regimes = pd.DataFrame(
        {
            "date": dates,
            "plan_regime_id": ["R1", "R1", "R4", "R4"],
            "plan_regime_label": ["Low-Vol Bull", "Low-Vol Bull", "High-Vol Bear", "High-Vol Bear"],
            "major_event_id": ["E016", "E016", "E017", "E017"],
        }
    )
    splits = [
        {
            "window_id": 1,
            "train_start": "2021-04-02",
            "train_end": "2021-04-09",
            "test_start": "2021-04-16",
            "test_end": "2021-04-23",
        }
    ]
    return _write_export(
        root,
        features=pd.DataFrame(features_rows),
        metadata=pd.DataFrame(meta_rows),
        regimes=regimes,
        splits=splits,
    )


def _build_split_export(root: Path) -> Path:
    dates = pd.date_range("2019-01-04", periods=220, freq="W-FRI")
    features_rows: list[dict[str, object]] = []
    meta_rows: list[dict[str, object]] = []
    for date_idx, date in enumerate(dates):
        for ticker_idx in range(12):
            ticker = f"T{ticker_idx:02d}"
            signal = float(date_idx + ticker_idx + 1)
            features_rows.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "target_weekly_return": 0.001 * signal,
                    "eps_sue_decay": signal,
                    "rev_sue_decay": signal * 0.9,
                    "earnings_quality_ratio_cs_z": signal * 0.8,
                    "agreement_score_cs_z": signal * 0.7,
                    "piotroski_fscore_cs_z": signal * 0.6,
                    "bulk_net_pressure_21d_cs_z": signal * 0.5,
                }
            )
            meta_rows.append({"date": date, "ticker": ticker, "sector": "Financial Services", "subsector": "See Industry Column", "broad_sector": "Financial Services"})
    regimes = pd.DataFrame(
        {
            "date": dates,
            "plan_regime_id": ["R1"] * len(dates),
            "plan_regime_label": ["Low-Vol Bull"] * len(dates),
            "major_event_id": ["E016"] * len(dates),
        }
    )
    splits = []
    for idx in range(4):
        splits.append(
            {
                "window_id": idx + 1,
                "train_start": str(dates[idx].date()),
                "train_end": str(dates[idx + 99].date()),
                "test_start": str(dates[idx + 100].date()),
                "test_end": str(dates[idx + 112].date()),
            }
        )
    return _write_export(
        root,
        features=pd.DataFrame(features_rows),
        metadata=pd.DataFrame(meta_rows),
        regimes=regimes,
        splits=splits,
    )


def test_ratio_wrapper_configs_match_compendium_contract() -> None:
    assert len(run_exp09.SCRIPT_CONFIG["candidate_grid"]) == 9
    assert {spec["params"]["depth"] for spec in run_exp09.SCRIPT_CONFIG["candidate_grid"]} == {3, 4, 5}
    assert {spec["params"]["od_wait"] for spec in run_exp09.SCRIPT_CONFIG["candidate_grid"]} == {20, 30, 50}
    assert run_exp10.SCRIPT_CONFIG["l2_grid"] == [3, 5, 8, 10, 15, 20]
    assert [spec["label"] for spec in run_exp11.SCRIPT_CONFIG["boosting_grid"]] == ["ordered", "plain"]
    assert run_exp12.SCRIPT_CONFIG["window_years_grid"] == [2, 3, 4]
    assert run_exp13.SCRIPT_CONFIG["required_fs_features"][4] == "rbi_rate_chg"
    assert run_exp18.SCRIPT_CONFIG["requested_event_ids"] == DEFAULT_EXP18_FIXED_EVENTS


def test_sector_resolvers_prefer_broad_sector(tmp_path: Path) -> None:
    export_dir = _build_dirty_sector_export(tmp_path / "dirty_export")
    dataset = load_plan_dataset(export_dir)

    fs = resolve_financial_services_universes(dataset)
    assert len(fs["full_fs"]) == 4
    assert fs["banks"] == ["BANK_A"]
    assert fs["lenders"] == ["BANK_A", "NBFC_A"]
    assert fs["insurance"] == ["INS_A"]
    assert resolve_it_tickers(dataset) == ["IT_A"]
    assert resolve_capital_goods_tickers(dataset) == ["CG_A"]


def test_aligned_splits_preserve_canonical_test_windows(tmp_path: Path) -> None:
    export_dir = _build_split_export(tmp_path / "split_export")
    dataset = load_plan_dataset(export_dir)

    splits_2y = _aligned_canonical_splits(dataset, 2)
    splits_3y = _aligned_canonical_splits(dataset, 3)

    assert len(splits_2y) == len(dataset.splits) == 4
    assert [row["test_start"] for row in splits_2y] == [row["test_start"] for row in dataset.splits]
    assert [row["test_end"] for row in splits_3y] == [row["test_end"] for row in dataset.splits]
    assert splits_2y[0]["train_start"] >= dataset.splits[0]["train_start"]
    assert splits_3y[0]["train_start"] == dataset.splits[0]["train_start"]


def test_factor_event_table_marks_uncovered_events(tmp_path: Path) -> None:
    export_dir = _build_dirty_sector_export(tmp_path / "event_export")
    dataset = load_plan_dataset(export_dir)
    factor_map = dict(_factor_alias_contract(list(dataset.features.columns), DEFAULT_CANONICAL_FACTOR_ALIASES)["factor_map"])

    table = _factor_event_table(dataset, factor_map)

    assert table["event_id"].nunique() == 22
    assert (table["coverage_status"] == "covered").any()
    assert (table["coverage_status"] == "event_not_in_export").any()
