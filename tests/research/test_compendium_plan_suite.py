from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.kaggle.plan_2026_04_05.catalog import load_experiment_catalog, load_plan_info
from scripts.kaggle.plan_2026_04_05.run_plan_suite import run_suite
from scripts.kaggle.plan_2026_04_08.lib import _select_exp09_best


def _build_synthetic_export(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range("2022-01-07", periods=20, freq="W-FRI")
    tickers = [f"TICKER_{idx:03d}" for idx in range(24)]
    sectors = [
        "Financial Services",
        "Information Technology",
        "Capital Goods",
        "Healthcare",
        "Oil Gas & Consumable Fuels",
        "Fast Moving Consumer Goods",
    ]
    groups = ["Group A", "Group B", "Group C", "Group D"]

    rows: list[dict[str, object]] = []
    meta_rows: list[dict[str, object]] = []
    for date_idx, date in enumerate(dates):
        macro = np.sin(date_idx / 3.0)
        for ticker_idx, ticker in enumerate(tickers):
            sector = sectors[ticker_idx % len(sectors)]
            group = groups[ticker_idx % len(groups)]
            cyc = np.cos(ticker_idx / 4.0) + macro
            quality = 0.3 * cyc + 0.02 * ticker_idx
            revision = 0.2 * np.sin((date_idx + ticker_idx) / 5.0)
            target = 0.35 * quality + 0.20 * revision - 0.03 * (ticker_idx % 5)
            rows.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "target_weekly_return": target,
                    "eps_sue_decay": quality + revision,
                    "rev_sue_decay": quality - revision,
                    "earnings_quality_ratio_cs_z": quality,
                    "agreement_score_cs_z": quality * 0.8,
                    "piotroski_fscore_cs_z": quality * 0.6,
                    "bulk_net_pressure_21d_cs_z": revision,
                    "ret_20d": cyc,
                    "inrusd_4w_return": 0.02 * macro,
                    "inrusd_vol_4w": 0.01 + abs(macro) * 0.02,
                    "crude_4w_return": 0.03 * cyc,
                    "crude_shock": 1.0 if abs(0.03 * cyc) > 0.015 else 0.0,
                    "gold_4w_return": -0.01 * macro,
                    "steel_4w_return": 0.02 * (ticker_idx % 3),
                    "copper_4w_return": 0.025 * macro,
                    "coal_4w_return": 0.015 * cyc,
                    "stock_x_crude": 0.03 * cyc * (1 if "Oil" in sector else 0.5),
                    "stock_x_inrusd": 0.02 * macro * (1 if sector in {"Information Technology", "Healthcare"} else 0.3),
                    "dxy_4w_return": -0.015 * macro,
                    "fii_proxy": 0.01 * cyc,
                    "vix_india_4w": abs(macro) * 0.4,
                    "rbi_rate_chg": 0.1 if date_idx % 6 == 0 else 0.0,
                    "us_10y_4w": 0.02 * macro,
                    "commodity_basket": 0.01 * cyc + 0.01 * macro,
                }
            )
            meta_rows.append(
                {
                    "date": date,
                    "ticker": ticker,
                    "broad_sector": sector,
                    "sector": sector,
                    "subsector": f"{sector} Subsector",
                    "conglomerate_group": group,
                    "market_cap": 1_000_000_000 + ticker_idx * 50_000_000,
                    "market_cap_rank": ticker_idx / len(tickers),
                }
            )

    features_df = pd.DataFrame(rows)
    metadata_df = pd.DataFrame(meta_rows)
    regimes_df = pd.DataFrame(
        {
            "date": dates,
            "plan_regime_id": ["R1"] * 8 + ["R4"] * 6 + ["R5"] * 6,
            "plan_regime_label": ["Low-Vol Bull"] * 8 + ["High-Vol Bear"] * 6 + ["Recovery"] * 6,
            "regime": ["R1|Low-Vol Bull"] * 8 + ["R4|High-Vol Bear"] * 6 + ["R5|Recovery"] * 6,
        }
    )
    splits = []
    for idx in range(4):
        splits.append(
            {
                "window_id": idx + 1,
                "train_start": str(dates[idx].date()),
                "train_end": str(dates[idx + 9].date()),
                "test_start": str(dates[idx + 10].date()),
                "test_end": str(dates[idx + 12].date()),
            }
        )

    features_df.to_parquet(root / "northstar_features.parquet", index=False)
    metadata_df.to_parquet(root / "northstar_metadata.parquet", index=False)
    regimes_df.to_parquet(root / "northstar_regime_labels.parquet", index=False)
    (root / "northstar_walk_forward_splits.json").write_text(json.dumps(splits, indent=2), encoding="utf-8")
    (root / "weekly_export_manifest.json").write_text(json.dumps({"source": "synthetic"}, indent=2), encoding="utf-8")
    return root


def test_catalog_covers_exp_09_through_exp_27() -> None:
    catalog = load_experiment_catalog()
    expected = {f"EXP-{idx:02d}" for idx in range(9, 28)}

    assert set(catalog.keys()) == expected
    assert catalog["EXP-09"].family == "ratio"
    assert catalog["EXP-16"].family == "sector"
    assert catalog["EXP-19"].dependencies == ("EXP-18",)
    assert catalog["EXP-21"].family == "redemption"
    assert catalog["EXP-27"].family == "verification"


def test_plan_info_points_to_single_master_notebook() -> None:
    plan = load_plan_info()

    assert plan.master_notebook.endswith("master_experiment_suite_v1.ipynb")
    assert len(plan.anchor_factors) == 6
    assert "earnings_quality_ratio" in plan.anchor_factors
    assert "commodity_basket" in plan.cross_asset_signals


def test_run_suite_dispatches_signal_and_verification_experiments(tmp_path: Path) -> None:
    export_dir = _build_synthetic_export(tmp_path / "export")
    output_root = tmp_path / "runs"

    payload = run_suite(
        export_dir=export_dir,
        output_root=output_root,
        exp_ids=["EXP-24", "EXP-25", "EXP-26", "EXP-27"],
        profile="smoke",
        max_splits=2,
        version="v1",
    )

    assert "EXP-24" in payload["experiments"]
    assert "EXP-26" in payload["experiments"]
    assert (output_root / "suite_summary.json").exists()
    assert (output_root / "exp_24_v1" / "signal_ic_battery.csv").exists()
    assert (output_root / "exp_25_v1" / "ccms_feature_frame.parquet").exists()
    assert (output_root / "exp_26_v1" / "five_test_battery.csv").exists()
    assert (output_root / "exp_27_v1" / "earnings_quality_validation.csv").exists()


def test_select_exp09_best_no_longer_crashes_on_ratio_tier_unpack() -> None:
    rows = [
        {
            "config_label": "depth_3_es_20",
            "mean_test_ic": 0.0165,
            "mean_train_test_ratio": 5.97,
            "ic_ir": 0.61,
        },
        {
            "config_label": "depth_5_es_30",
            "mean_test_ic": 0.0192,
            "mean_train_test_ratio": 12.16,
            "ic_ir": 0.65,
        },
    ]

    best = _select_exp09_best(rows, ic_floor=0.020)

    assert best["config_label"] == "depth_3_es_20"
