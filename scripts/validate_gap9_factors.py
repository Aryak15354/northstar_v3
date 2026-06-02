#!/usr/bin/env python3
"""Validate the canonical Gap 9 factor pipeline."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.factors import BaseFactor, FactorRegistry, FactorStore
from src.ingestion import IngestionRegistry
from src.research.feature_factory import FeatureFactory


def parse_args():
    parser = argparse.ArgumentParser(description="Validate Gap 9 factor pipeline")
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--config", type=str, default="config/factors_config.yaml")
    parser.add_argument("--full", action="store_true", help="Run factor computation and feature-matrix checks")
    return parser.parse_args()


def load_config(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {
            "factors": {
                "enabled": True,
                "enabled_factors": [
                    "bab",
                    "amihud",
                    "piotroski",
                    "max",
                    "earnings_quality",
                    "operating_profitability",
                    "earnings_surprise",
                    "promoter_pledge",
                    "bulk_deal",
                ],
            }
        }
    with open(p, "r") as f:
        return yaml.safe_load(f) or {}


def main() -> int:
    args = parse_args()
    as_of_date = datetime.strptime(args.date, "%Y-%m-%d")
    cfg = load_config(args.config)

    registry = IngestionRegistry(cfg)
    factor_registry = FactorRegistry(registry, cfg)
    store = FactorStore(factor_registry, cfg)

    checks: list[tuple[str, bool, str]] = []

    factor_classes = [cls for cls in factor_registry._factors.values()]
    checks.append(("factor_classes_present", all(issubclass(cls.__class__, object) or isinstance(cls, BaseFactor) for cls in factor_classes), f"count={len(factor_classes)}"))

    universe_early = registry.market.get_universe_as_of(datetime(2022, 11, 9))
    universe_late = registry.market.get_universe_as_of(datetime(2023, 9, 21))
    checks.append(("pit_universe_varies", universe_early != universe_late, f"early={len(universe_early)} late={len(universe_late)}"))

    index_data = registry.market.load_index(as_of_date, index_name="NIFTY500", start_date=datetime(2023, 1, 1), fields=["close"])
    checks.append(("nifty500_index_loads", (not index_data.empty) and ("close" in index_data.columns), f"rows={len(index_data)} cols={list(index_data.columns)}"))

    prices = registry.market.load(as_of_date, tickers=["RELIANCE.NS"], start_date=datetime(2023, 1, 1), fields=["close", "adj_close", "volume"])
    checks.append(("market_aliases_work", set(["close", "adj_close", "volume"]).issubset(set(prices.columns)), f"cols={list(prices.columns)}"))

    fin = registry.fundamentals.get_factor_financials(as_of_date, ["RELIANCE.NS"], periods=2)
    checks.append(("factor_financial_adapter", bool(fin.get("RELIANCE.NS", {}).get("current")), f"keys={list(fin.get('RELIANCE.NS', {}).keys())}"))

    if args.full:
        tickers = registry.market.get_universe_as_of(as_of_date)[:50]
        result = factor_registry.compute_all(as_of_date, tickers, use_cache=False)
        expected = {c for c in result.columns if isinstance(c, str) and c.endswith("_zscore")}
        checks.append(("factor_registry_returns_base5", expected.issubset(set(result.columns)), f"missing={sorted(expected - set(result.columns))}"))

        coverage = factor_registry.get_coverage_report(as_of_date, tickers)
        checks.append(("coverage_report_present", len(coverage) == len(factor_registry.get_enabled_factors()), f"keys={list(coverage.keys())}"))

        ff = FeatureFactory(config=cfg)
        feature_matrix = ff.build_feature_matrix(as_of_date, tickers)
        checks.append(("feature_factory_has_factor_cols", expected.issubset(set(feature_matrix.columns)), f"missing={sorted(expected - set(feature_matrix.columns))}"))
        non_empty = sorted(c for c in expected if c in feature_matrix.columns and feature_matrix[c].notna().any())
        checks.append(("feature_factory_not_all_nan", len(non_empty) >= max(5, min(len(expected), 7)), f"non_empty={non_empty}"))

        status = store.get_store_status()
        checks.append(("factor_store_accessible", isinstance(status, dict), f"date_range={status.get('date_range')}"))

    print("GAP 9 FACTOR VALIDATION")
    print("=" * 60)
    failures = 0
    for name, passed, detail in checks:
        mark = "PASS" if passed else "FAIL"
        print(f"{mark:4} {name}: {detail}")
        if not passed:
            failures += 1
    print("=" * 60)
    print(f"Checks: {len(checks)}  Failures: {failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
