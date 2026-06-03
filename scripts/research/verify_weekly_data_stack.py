#!/usr/bin/env python3
"""Verify the weekly research data stack before Kaggle experiments."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _assert(condition: bool, code: str, detail: str, failures: list[dict[str, str]]) -> None:
    if not condition:
        failures.append({"code": code, "detail": detail})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify weekly research inputs and cross-asset coverage.")
    parser.add_argument(
        "--canonical-reference-root",
        type=Path,
        default=PROJECT_ROOT / "data/canonical/reference",
    )
    parser.add_argument(
        "--cross-asset-manifest",
        type=Path,
        default=PROJECT_ROOT / "data/raw/shared/market_data/cross_asset_manifest.json",
    )
    parser.add_argument(
        "--ticker-master",
        type=Path,
        default=PROJECT_ROOT / "data/canonical/reference/ticker_master.parquet",
    )
    parser.add_argument(
        "--legacy-universe",
        type=Path,
        default=PROJECT_ROOT / "universe/nifty500.csv",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=PROJECT_ROOT / "data/results/research/state/weekly_data_stack_verification.json",
    )
    parser.add_argument("--max-stale-days", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    failures: list[dict[str, str]] = []
    reference_root = args.canonical_reference_root.expanduser().resolve()

    major = pd.read_parquet(reference_root / "regimes/nse_regime_events_major.parquet")
    subtle = pd.read_parquet(reference_root / "regimes/nse_regime_periods_subtle.parquet")
    timeline = pd.read_parquet(reference_root / "regimes/nse_regime_timeline.parquet")
    universe = pd.read_parquet(reference_root / "universe/nifty500_universe_enriched.parquet")
    legacy = pd.read_csv(args.legacy_universe.expanduser().resolve())
    ticker_master = pd.read_parquet(args.ticker_master.expanduser().resolve())

    _assert(len(major) >= 20, "major_events_count", f"expected >=20 major events, found {len(major)}", failures)
    _assert(len(subtle) >= 35, "subtle_periods_count", f"expected >=35 subtle periods, found {len(subtle)}", failures)
    _assert(len(timeline) >= len(major) + len(subtle) - 5, "timeline_count", f"timeline rows look short: {len(timeline)}", failures)
    _assert(major["event_id"].astype(str).is_unique, "major_event_ids_unique", "major event ids are not unique", failures)
    _assert(subtle["period_id"].astype(str).is_unique, "subtle_period_ids_unique", "subtle period ids are not unique", failures)
    _assert(universe["symbol"].astype(str).is_unique, "universe_symbols_unique", "universe symbols are not unique", failures)
    _assert(len(universe) >= 500, "universe_row_count", f"expected >=500 universe rows, found {len(universe)}", failures)
    _assert(
        {"Company Name", "Industry", "Symbol", "Series", "ISIN Code"}.issubset(legacy.columns),
        "legacy_universe_schema",
        f"legacy universe missing expected columns: {sorted(set(['Company Name','Industry','Symbol','Series','ISIN Code']) - set(legacy.columns))}",
        failures,
    )
    _assert(
        {"commodity_sensitivities", "sector_macro_sensitivities", "key_interconnections_peers"}.issubset(ticker_master.columns),
        "ticker_master_enriched_columns",
        "ticker_master parquet is missing enriched universe fields",
        failures,
    )

    manifest = json.loads(args.cross_asset_manifest.expanduser().resolve().read_text(encoding="utf-8"))
    assets = pd.DataFrame(manifest.get("assets", []))
    _assert(not assets.empty, "cross_asset_assets_present", "cross asset manifest contains no assets", failures)
    if not assets.empty:
        _assert(
            assets["stale_days"].fillna(args.max_stale_days + 999).astype(int).max() <= args.max_stale_days,
            "cross_asset_staleness",
            f"at least one cross-asset series is older than {args.max_stale_days} days",
            failures,
        )
        _assert(
            assets["rows"].astype(int).min() > 0,
            "cross_asset_nonempty",
            "at least one cross-asset series is empty",
            failures,
        )

    summary = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "status": "pass" if not failures else "fail",
        "failures": failures,
        "checks": {
            "major_events_rows": int(len(major)),
            "subtle_period_rows": int(len(subtle)),
            "timeline_rows": int(len(timeline)),
            "universe_rows": int(len(universe)),
            "legacy_universe_rows": int(len(legacy)),
            "ticker_master_rows": int(len(ticker_master)),
            "cross_asset_series": int(len(assets)),
            "cross_asset_max_stale_days": None if assets.empty else int(assets["stale_days"].fillna(-1).astype(int).max()),
        },
    }
    output_path = args.output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
