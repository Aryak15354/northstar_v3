#!/usr/bin/env python3
"""Validate the feature-system update on a recent research slice."""

from __future__ import annotations

import argparse
import copy
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.factors.gap9_academic_factors import Gap9AcademicFactors
from src.research.dataset_manager import DatasetManager


LOGGER = logging.getLogger("northstar.validate_feature_update")
MACRO_NEW_COLUMNS = [
    "rbi_repo_rate_level",
    "rbi_repo_rate_ts_z",
    "rbi_repo_rate_change_13w",
    "yield_curve_slope",
    "yield_curve_slope_ts_z",
    "cpi_surprise",
    "cpi_surprise_ts_z",
]
ALL_NEW_COLUMNS = Gap9AcademicFactors.OUTPUT_COLUMNS + MACRO_NEW_COLUMNS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the Gap 9, sentiment-mode, and RBI macro feature update.")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config/research_policy.yaml")
    parser.add_argument("--sentiment-mode", choices=["full", "reduced"], default=None)
    parser.add_argument("--lookback-days", type=int, default=420)
    parser.add_argument("--validation-days", type=int, default=5)
    parser.add_argument("--max-tickers", type=int, default=0)
    parser.add_argument("--max-rows", type=int, default=80000)
    parser.add_argument("--min-coverage", type=float, default=0.80)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def _load_dataset_config(config_path: Path) -> dict:
    with config_path.open("r", encoding="utf-8") as handle:
        root_cfg = yaml.safe_load(handle) or {}
    dataset_cfg = copy.deepcopy(root_cfg.get("historical_research", {}).get("dataset", {}))
    if not isinstance(dataset_cfg, dict):
        raise ValueError("historical_research.dataset config missing or invalid")
    dataset_cfg["policy_config_path"] = str(config_path)
    return dataset_cfg


def _sentiment_feature_counts(feature_names: list[str]) -> tuple[int, int]:
    company_prefixes = ("sent_", "sentiment_", "event_", "narrative_", "topic_")
    market_prefixes = ("macro_sentiment_", "mkt_sent_")
    company_count = 0
    market_count = 0
    for name in feature_names:
        if name == "agreement_score" or name.startswith(company_prefixes):
            company_count += 1
        elif name.startswith(market_prefixes):
            market_count += 1
    return company_count, market_count


def _format_pct(value: float) -> str:
    if not np.isfinite(value):
        return "nan"
    return f"{value * 100.0:.1f}%"


def _latest_snapshot_path() -> Path | None:
    snapshot_root = PROJECT_ROOT / "data/results/research/snapshots"
    if not snapshot_root.exists():
        return None
    candidates = sorted(snapshot_root.glob("**/research_snapshot_*.parquet"))
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    dataset_cfg = _load_dataset_config(args.config.resolve())
    dataset_cfg["lookback_days"] = int(max(252, args.lookback_days))
    dataset_cfg["max_rows"] = int(max(5000, args.max_rows))
    if int(args.max_tickers) > 0:
        dataset_cfg["max_tickers"] = int(args.max_tickers)
    if args.sentiment_mode is not None:
        dataset_cfg["sentiment_feature_mode"] = str(args.sentiment_mode)
    dataset_cfg["use_gap9_academic_factors"] = True
    dataset_cfg["use_macro_features"] = True

    manager = DatasetManager(project_root=PROJECT_ROOT, config=dataset_cfg)
    lookback_days = int(manager.config.get("lookback_days", 3650))
    max_tickers = int(manager.config.get("max_tickers", 250))
    cfg_start = manager._config_date("start_date")
    cfg_end = manager._config_date("end_date")
    snapshot_path = _latest_snapshot_path()
    if snapshot_path is not None:
        frame = pd.read_parquet(snapshot_path)
        frame = frame.drop(columns=ALL_NEW_COLUMNS, errors="ignore")
        if "date" not in frame.columns and "Date" in frame.columns:
            frame = frame.rename(columns={"Date": "date"})
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame.dropna(subset=["date", "ticker"]).sort_values(["date", "ticker"], kind="mergesort")
        if lookback_days > 0 and not frame.empty:
            cutoff = frame["date"].max() - pd.Timedelta(days=lookback_days)
            frame = frame.loc[frame["date"] >= cutoff].copy()
        if cfg_start is not None:
            frame = frame.loc[frame["date"] >= cfg_start].copy()
        if cfg_end is not None:
            frame = frame.loc[frame["date"] <= cfg_end].copy()
        if max_tickers > 0 and frame["ticker"].nunique() > max_tickers:
            top = (
                frame.groupby("ticker")["date"]
                .count()
                .sort_values(ascending=False)
                .head(max_tickers)
                .index
            )
            frame = frame.loc[frame["ticker"].astype(str).isin(set(top.astype(str)))].copy()
        frame = manager.factory._merge_rbi_dbie_macro_features(frame)
        frame = manager.factory._gap9_academic_block.transform(frame)
        frame = manager.factory.apply_sentiment_feature_mode(frame)
        source_label = str(snapshot_path.relative_to(PROJECT_ROOT))
    else:
        prices = manager.load_prices()
        fundamentals = manager.load_fundamentals()
        screener_annual = manager.load_screener_extended_annual() if bool(manager.use_screener_features) else pd.DataFrame()
        screener_quarterly = manager.load_screener_extended_quarterly() if bool(manager.use_screener_features) else pd.DataFrame()
        screener_shareholding = (
            manager.load_screener_extended_shareholding() if bool(manager.use_screener_features) else pd.DataFrame()
        )
        macro_enabled = bool(manager.config.get("enable_macro_features", True))
        macro = manager.load_macro() if macro_enabled else pd.DataFrame()
        valuation = manager.load_valuation_posterior()
        sentiment_company = manager.load_sentiment_company()
        sentiment_market = manager.load_sentiment_market()
        sentiment_features_df = (
            manager.load_sentiment_features() if bool(manager.config.get("use_sentiment_features", False)) else pd.DataFrame()
        )
        et500_membership = (
            manager._load_et500_membership()
            if bool(manager.use_et500_features or manager.use_et500_universe_filter)
            else pd.DataFrame()
        )
        sector_lookup = manager._load_sector_lookup()
        fundamentals = manager._apply_sector_lookup_to_frame(fundamentals, sector_lookup)

        if not prices.empty:
            p = prices.copy()
            date_col = "Date" if "Date" in p.columns else ("date" if "date" in p.columns else None)
            if date_col is not None:
                p["__date"] = pd.to_datetime(p[date_col], errors="coerce")
                p = p.dropna(subset=["__date"])
                if cfg_start is not None:
                    p = p.loc[p["__date"] >= cfg_start].copy()
                if cfg_end is not None:
                    p = p.loc[p["__date"] <= cfg_end].copy()
                if lookback_days > 0 and not p.empty:
                    cutoff = p["__date"].max() - pd.Timedelta(days=lookback_days + 180)
                    p = p.loc[p["__date"] >= cutoff].copy()
                if max_tickers > 0 and "ticker" in p.columns and p["ticker"].nunique() > max_tickers:
                    top = (
                        p.groupby("ticker")["__date"]
                        .count()
                        .sort_values(ascending=False)
                        .head(max_tickers)
                        .index
                    )
                    top_set = set(top.astype(str))
                    p = p.loc[p["ticker"].astype(str).isin(top_set)].copy()
                    if not fundamentals.empty and "ticker" in fundamentals.columns:
                        fundamentals = fundamentals[fundamentals["ticker"].astype(str).isin(top_set)].copy()
                    if not valuation.empty and "ticker" in valuation.columns:
                        valuation = valuation[valuation["ticker"].astype(str).isin(top_set)].copy()
                    if not sentiment_company.empty and "ticker" in sentiment_company.columns:
                        sentiment_company = sentiment_company[sentiment_company["ticker"].astype(str).isin(top_set)].copy()
                    if not screener_annual.empty and "ticker" in screener_annual.columns:
                        screener_annual = screener_annual[screener_annual["ticker"].astype(str).isin(top_set)].copy()
                    if not screener_quarterly.empty and "ticker" in screener_quarterly.columns:
                        screener_quarterly = screener_quarterly[screener_quarterly["ticker"].astype(str).isin(top_set)].copy()
                    if not screener_shareholding.empty and "ticker" in screener_shareholding.columns:
                        screener_shareholding = screener_shareholding[
                            screener_shareholding["ticker"].astype(str).isin(top_set)
                        ].copy()
                prices = p.drop(columns=["__date"], errors="ignore")

        frame = manager.factory.build_features(
            prices=prices,
            fundamentals=fundamentals,
            screener_annual=screener_annual if bool(manager.use_screener_features) else None,
            screener_quarterly=screener_quarterly if bool(manager.use_screener_features) else None,
            screener_shareholding=screener_shareholding if bool(manager.use_screener_features) else None,
            macro=macro,
            valuation_posterior=valuation,
            sentiment_company=sentiment_company,
            sentiment_market=sentiment_market,
            sector_lookup=sector_lookup,
            et500_membership=et500_membership if bool(manager.use_et500_features) else None,
        )
        if not sentiment_features_df.empty:
            frame = frame.merge(sentiment_features_df, on=["date", "ticker"], how="left")
        if bool(manager.use_et500_universe_filter):
            frame = manager._apply_et500_universe_filter(frame, et500_membership)
        frame = manager._apply_liquidity_filter(frame, prices)
        delist_df = manager._load_delisting_database()
        if not delist_df.empty:
            frame = manager._apply_delisting_adjustments(frame, delist_df)
        frame = manager._add_sector_dummies(frame)
        frame = manager.factory.apply_sentiment_feature_mode(frame)
        source_label = "raw_feature_build"
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame.dropna(subset=["date", "ticker"]).sort_values(["date", "ticker"], kind="mergesort")
    if lookback_days > 0 and not frame.empty:
        cutoff = frame["date"].max() - pd.Timedelta(days=lookback_days)
        frame = frame.loc[frame["date"] >= cutoff].copy()
    if cfg_start is not None:
        frame = frame.loc[frame["date"] >= cfg_start].copy()
    if cfg_end is not None:
        frame = frame.loc[frame["date"] <= cfg_end].copy()
    if frame.empty:
        raise ValueError("validation_frame_empty")

    unique_dates = sorted(pd.Timestamp(d) for d in frame["date"].dropna().unique())
    recent_dates = unique_dates[-max(1, min(int(args.validation_days), len(unique_dates))):]
    recent_frame = frame[frame["date"].isin(recent_dates)].copy()
    anchor_date = recent_dates[-1]
    anchor_frame = recent_frame[recent_frame["date"] == anchor_date].copy()
    n_tickers = int(anchor_frame["ticker"].nunique())
    if n_tickers == 0:
        raise ValueError("validation_anchor_empty")

    target_col = str(manager.config.get("target_col", "forward_return_5d"))
    exclude = {
        "date",
        "ticker",
        "regime",
        "macro_regime",
        "regime_name",
        "valuation_regime",
        "volume",
        target_col,
        f"{target_col}__realized",
    }
    leakage_prefixes = ("forward_return_", "target_")
    feature_names = [
        c
        for c in frame.columns
        if c not in exclude
        and pd.api.types.is_numeric_dtype(frame[c])
        and not str(c).endswith("__realized")
        and not str(c).startswith(leakage_prefixes)
    ]
    present_new_columns = [column for column in ALL_NEW_COLUMNS if column in feature_names]
    before_count = int(len(feature_names) - len(present_new_columns))
    company_sentiment_count, market_sentiment_count = _sentiment_feature_counts(feature_names)

    print("FEATURE UPDATE VALIDATION")
    print("=" * 72)
    print(f"anchor_date: {anchor_date.date()}")
    print(f"validation_dates: {recent_dates[0].date()} -> {recent_dates[-1].date()} ({len(recent_dates)} trading days)")
    print(f"tickers_on_anchor_date: {n_tickers}")
    print(f"source: {source_label}")
    print(f"sentiment_mode: {getattr(manager.factory, 'sentiment_feature_mode', dataset_cfg.get('sentiment_feature_mode', 'full'))}")
    print(f"feature_count_before_update: {before_count}")
    print(f"feature_count_after_update: {len(feature_names)}")
    print(f"new_feature_columns_present: {len(present_new_columns)}/{len(ALL_NEW_COLUMNS)}")
    print(f"company_sentiment_feature_count: {company_sentiment_count}")
    print(f"market_sentiment_feature_count: {market_sentiment_count}")
    print("-" * 72)

    failures: list[str] = []

    missing_columns = [column for column in ALL_NEW_COLUMNS if column not in anchor_frame.columns or column not in feature_names]
    if missing_columns:
        failures.append(f"missing_new_columns={missing_columns}")

    print("Coverage on anchor date")
    for column in ALL_NEW_COLUMNS:
        if column not in anchor_frame.columns:
            print(f"  FAIL {column}: missing")
            continue
        coverage = float(pd.to_numeric(anchor_frame[column], errors="coerce").notna().mean())
        status = "PASS" if coverage >= float(args.min_coverage) else "FAIL"
        print(f"  {status} {column}: {_format_pct(coverage)} non-null")
        if coverage < float(args.min_coverage):
            failures.append(f"low_coverage:{column}:{coverage:.3f}")

    print("-" * 72)
    print("Gap 9 cross-sectional variance on anchor date")
    for column in Gap9AcademicFactors.RAW_COLUMNS:
        if column not in anchor_frame.columns:
            print(f"  FAIL {column}: missing")
            failures.append(f"missing_gap9:{column}")
            continue
        std = float(pd.to_numeric(anchor_frame[column], errors="coerce").std())
        status = "PASS" if np.isfinite(std) and std > 0.0 else "FAIL"
        print(f"  {status} {column}: std={std:.6f}" if np.isfinite(std) else f"  {status} {column}: std=nan")
        if not np.isfinite(std) or std <= 0.0:
            failures.append(f"zero_variance:{column}:{std}")

    corr_sample = recent_frame[["piotroski_fscore", "roe_qoq_change"]].copy()
    corr_sample["piotroski_fscore"] = pd.to_numeric(corr_sample["piotroski_fscore"], errors="coerce")
    corr_sample["roe_qoq_change"] = pd.to_numeric(corr_sample["roe_qoq_change"], errors="coerce")
    corr_sample = corr_sample.dropna()
    corr_reason = "insufficient overlap"
    corr = float("nan")
    if len(corr_sample) >= 2:
        piot_unique = int(corr_sample["piotroski_fscore"].nunique(dropna=True))
        roe_unique = int(corr_sample["roe_qoq_change"].nunique(dropna=True))
        if piot_unique >= 2 and roe_unique >= 2:
            corr = float(corr_sample["piotroski_fscore"].corr(corr_sample["roe_qoq_change"]))
            corr_reason = "expected positive and below 0.7"
        else:
            corr_reason = f"insufficient variation (piotroski_unique={piot_unique}, roe_qoq_change_unique={roe_unique})"
    corr_status = "PASS" if np.isfinite(corr) and 0.0 < corr < 0.7 else "WARN"

    print("-" * 72)
    print(
        "Piotroski vs ROE QoQ change correlation: "
        f"{corr:.4f} ({corr_status}; {corr_reason})"
        if np.isfinite(corr)
        else f"Piotroski vs ROE QoQ change correlation: nan (WARN; {corr_reason})"
    )
    print("=" * 72)

    if failures:
        print("VALIDATION RESULT: FAIL")
        for item in failures:
            print(f"  - {item}")
        return 1

    print("VALIDATION RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
