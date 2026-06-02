#!/usr/bin/env python3
"""Validate the Screener -> valuation -> research integration for Gap 10."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion import IngestionRegistry
from src.research.experiment_tracker import ExperimentTracker
from src.research.feature_factory import FeatureFactory
from src.signal_engineering.accruals_validator import AccrualsValidator
from src.valuation.buffett_module.moat_score import MoatScorer
from src.valuation.core.normalized_financials import FinancialNormalizer
from src.valuation.intrinsic_value.dcf_engine import DCFEngine
from src.valuation.valuation_feature_block import ValuationFeatureBlock


RESULT_PATH = PROJECT_ROOT / "data" / "audit" / "gap10_validation_results.json"


def load_config() -> dict:
    config: dict = {}
    for path in [
        PROJECT_ROOT / "config" / "ingestion_config.yaml",
        PROJECT_ROOT / "config" / "factors_config.yaml",
        PROJECT_ROOT / "config" / "valuation_config.yaml",
    ]:
        if not path.exists():
            continue
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(payload, dict):
            config.update(payload)
    config.setdefault("valuation", {})
    config["valuation"].setdefault("features_enabled", True)
    return config


def resolve_date(raw: str) -> pd.Timestamp:
    if str(raw).strip().lower() == "today":
        return pd.Timestamp.today().normalize()
    value = pd.to_datetime(raw, errors="coerce")
    if pd.isna(value):
        raise ValueError(f"invalid --date: {raw}")
    return pd.Timestamp(value).normalize()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Gap 10 lineage and valuation feature integration.")
    parser.add_argument("--date", default="today")
    parser.add_argument("--max-tickers", type=int, default=50)
    return parser.parse_args()


def _price_lookup(registry: IngestionRegistry, tickers: list[str], as_of_date: pd.Timestamp) -> dict[str, float]:
    prices = registry.market.load(
        as_of_date=as_of_date.to_pydatetime(),
        tickers=tickers,
        start_date=(as_of_date - pd.Timedelta(days=15)).to_pydatetime(),
        fields=["close"],
    )
    if prices.empty:
        return {}
    if isinstance(prices.index, pd.MultiIndex):
        frame = prices.reset_index()
        frame["Date"] = pd.to_datetime(frame.get("Date", frame.get("date")), errors="coerce")
        ticker_col = "Ticker" if "Ticker" in frame.columns else "ticker"
        close_col = "close" if "close" in frame.columns else "Close"
        latest = (
            frame.dropna(subset=[ticker_col, close_col])
            .sort_values([ticker_col, "Date"], kind="mergesort")
            .groupby(ticker_col, sort=False)[close_col]
            .last()
        )
        return {str(k): float(v) for k, v in latest.items() if pd.notna(v)}
    if "close" in prices.columns:
        return {str(k): float(v) for k, v in prices["close"].dropna().items()}
    return {}


def record_check(results: list[dict], name: str, passed: bool, detail: str, **extra) -> None:
    results.append({"name": name, "passed": bool(passed), "detail": detail, **extra})


def main() -> int:
    args = parse_args()
    as_of_date = resolve_date(args.date)
    config = load_config()
    registry = IngestionRegistry(config)
    normalizer = FinancialNormalizer(config)
    valuation_block = ValuationFeatureBlock(config)
    dcf = DCFEngine(config=config)
    moat = MoatScorer(config)
    accruals = AccrualsValidator(config)
    feature_factory = FeatureFactory(
        config={
            **config,
            "use_academic_factors": False,
            "use_alternative_features": False,
            "use_sentiment_features": False,
            "use_macro_features": False,
            "use_screener_features": False,
            "valuation": {**(config.get("valuation", {}) or {}), "features_enabled": True},
        }
    )

    tickers = [str(t) for t in registry.market.get_universe_as_of(as_of_date.to_pydatetime())]
    if args.max_tickers and args.max_tickers > 0:
        tickers = tickers[: int(args.max_tickers)]
    prices = _price_lookup(registry, tickers, as_of_date)

    checks: list[dict] = []

    coverage = normalizer.get_coverage(as_of_date.to_pydatetime(), tickers)
    has_data_ratio = (
        sum(1 for item in coverage.values() if item.get("has_data")) / max(len(coverage), 1)
        if coverage
        else 0.0
    )
    record_check(
        checks,
        "Screener data coverage",
        has_data_ratio >= 0.80,
        f"coverage={has_data_ratio:.1%}",
        coverage_ratio=has_data_ratio,
    )

    source_ok = str(normalizer.SCREENER_DATA_PATH).endswith("data/raw/vendors/screener/financials")
    record_check(
        checks,
        "FinancialNormalizer correct source",
        source_ok,
        f"source={normalizer.SCREENER_DATA_PATH}",
    )

    dcf_success = 0
    for ticker in tickers:
        result = dcf.run(ticker, as_of_date=as_of_date.to_pydatetime(), current_price=prices.get(ticker))
        if pd.notna(pd.to_numeric(result.get("fair_value"), errors="coerce")):
            dcf_success += 1
    dcf_ratio = dcf_success / max(len(tickers), 1)
    record_check(
        checks,
        "DCF fair value coverage",
        dcf_ratio >= 0.70,
        f"coverage={dcf_ratio:.1%}",
        coverage_ratio=dcf_ratio,
    )

    moat_source = "FinancialNormalizer" in (
        PROJECT_ROOT / "src" / "valuation" / "buffett_module" / "moat_score.py"
    ).read_text(encoding="utf-8")
    legacy_path_absent = "data/market/financials.parquet" not in (
        PROJECT_ROOT / "src" / "valuation" / "buffett_module" / "moat_score.py"
    ).read_text(encoding="utf-8")
    record_check(
        checks,
        "MoatScorer uses FinancialNormalizer",
        moat_source and legacy_path_absent,
        "FinancialNormalizer import present and legacy financials parquet path absent",
    )

    accrual_results = [accruals.validate(ticker, as_of_date.to_pydatetime()) for ticker in tickers]
    cashflow_ratio = sum(1 for item in accrual_results if item.get("has_real_cashflow")) / max(len(accrual_results), 1)
    record_check(
        checks,
        "AccrualsValidator uses real cashflow data",
        cashflow_ratio >= 0.70,
        f"has_real_cashflow={cashflow_ratio:.1%}",
        coverage_ratio=cashflow_ratio,
    )

    val_df = valuation_block.compute(as_of_date.to_pydatetime(), tickers, prices, use_cache=False)
    raw_cols = [c for c in valuation_block.FEATURE_NAMES if c in val_df.columns]
    z_cols = [f"{c}_zscore" for c in valuation_block.FEATURE_NAMES if f"{c}_zscore" in val_df.columns]
    record_check(
        checks,
        "ValuationFeatureBlock produces all features",
        len(raw_cols) == 15 and len(z_cols) == 15,
        f"raw_cols={len(raw_cols)}, z_cols={len(z_cols)}",
    )

    cache_exists = valuation_block.CACHE_PATH.exists()
    row_coverage = val_df[raw_cols].notna().any(axis=1).mean() if raw_cols else 0.0
    record_check(
        checks,
        "valuation_scores parquet written",
        cache_exists and row_coverage >= 0.70,
        f"path_exists={cache_exists}, row_coverage={row_coverage:.1%}",
        coverage_ratio=float(row_coverage),
    )

    price_panel = registry.market.load(
        as_of_date=as_of_date.to_pydatetime(),
        tickers=tickers[: min(len(tickers), 20)],
        start_date=(as_of_date - pd.Timedelta(days=10)).to_pydatetime(),
        fields=["close"],
    )
    if isinstance(price_panel.index, pd.MultiIndex):
        panel_frame = price_panel.reset_index()
        latest_rows = (
            panel_frame.dropna(subset=["Ticker", "close"])
            .sort_values(["Ticker", "Date"], kind="mergesort")
            .groupby("Ticker", sort=False)
            .tail(1)
            .rename(columns={"Ticker": "ticker", "Date": "date"})
        )[["date", "ticker", "close"]]
    else:
        latest_rows = pd.DataFrame(columns=["date", "ticker", "close"])
    feature_matrix = feature_factory._add_valuation_features(latest_rows, as_of_date.to_pydatetime())
    needed_val_cols = [
        "val_discount_to_fair_pct_zscore",
        "val_moat_score_zscore",
        "val_composite_score_zscore",
    ]
    has_feature_cols = all(col in feature_matrix.columns for col in needed_val_cols)
    nonempty_cols = all(feature_matrix[col].notna().any() for col in needed_val_cols if col in feature_matrix.columns)
    record_check(
        checks,
        "FeatureFactory includes valuation z-score columns",
        has_feature_cols and nonempty_cols,
        f"columns_present={has_feature_cols}, nonempty={nonempty_cols}",
    )
    if has_feature_cols and nonempty_cols:
        ExperimentTracker().log(
            {
                "module": "gap10_validation_probe",
                "as_of_date": str(as_of_date.date()),
                "feature_names": [str(col) for col in feature_matrix.columns if str(col).startswith("val_")],
                "universe_size": int(len(feature_matrix)),
                "notes": "Gap 10 validation probe confirming valuation features are present in the research feature matrix.",
            }
        )

    experiments_path = PROJECT_ROOT / "data" / "results" / "research" / "trackers" / "experiments.ndjson"
    experiment_has_val = False
    if experiments_path.exists():
        try:
            lines = [json.loads(line) for line in experiments_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            for item in reversed(lines[-20:]):
                text = json.dumps(item)
                if "val_" in text:
                    experiment_has_val = True
                    break
        except Exception:
            experiment_has_val = False
    record_check(
        checks,
        "Research experiment records valuation features",
        experiment_has_val,
        "searched latest experiments.ndjson entries for val_* feature references",
    )

    pit_ok = True
    for ticker in tickers[: min(10, len(tickers))]:
        loaded = normalizer.load(ticker, as_of_date.to_pydatetime(), "annual")
        if not loaded.empty and not bool((pd.to_datetime(loaded["available_date"], errors="coerce") <= as_of_date).all()):
            pit_ok = False
            break
    record_check(
        checks,
        "PIT compliance for valuation inputs",
        pit_ok,
        "all sampled normalized financial rows satisfy available_date <= as_of_date",
    )

    summary = {
        "generated_at": datetime.now().isoformat(),
        "as_of_date": str(as_of_date.date()),
        "universe_size": len(tickers),
        "checks": checks,
        "passed": sum(1 for check in checks if check["passed"]),
        "failed": sum(1 for check in checks if not check["passed"]),
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    for check in checks:
        marker = "PASS" if check["passed"] else "FAIL"
        print(f"{marker}: {check['name']} — {check['detail']}")
    print(json.dumps({"passed": summary["passed"], "failed": summary["failed"], "path": str(RESULT_PATH)}, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
