#!/usr/bin/env python3
"""Audit local Northstar research dataset inputs and their observed usage."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.week_2026_03_29.build_weekly_feature_export import _dataset_runtime_config  # noqa: E402
from src.signals.signal_loader import AlternativeDataLoader  # noqa: E402

try:
    import pyarrow.parquet as pq
except Exception:  # noqa: BLE001
    pq = None


DATE_COLUMN_CANDIDATES = [
    "date",
    "Date",
    "timestamp",
    "availability_date",
    "announcement_date",
    "delisting_date",
    "period_date",
    "release_date",
    "fiscal_year_end",
    "quarter_end",
    "period_end",
    "period_end_date",
]

TICKER_COLUMN_CANDIDATES = [
    "ticker",
    "Ticker",
    "nse_ticker",
    "nse_symbol",
    "symbol",
    "Symbol",
]

SNAPSHOT_FAMILY_ROOTS: dict[str, list[str]] = {
    "bulk_deals": ["bulk_"],
    "pledge": ["pledge_"],
    "ratings": ["rating_"],
    "announcements": ["order_"],
    "earnings_dates": [
        "days_since_earnings",
        "earnings_frequency_annual",
        "earnings_gap_days",
        "eps_sue",
        "eps_sue_decay",
        "rev_sue",
        "rev_sue_decay",
        "combined_sue",
    ],
    "company_sentiment": ["sent_"],
    "market_sentiment": ["mkt_sent_"],
    "macro_pack": ["macro_"],
    "rbi_dbie": [
        "rbi_repo_rate_level",
        "rbi_repo_rate_ts_z",
        "rbi_repo_rate_change_13w",
        "yield_curve_slope",
        "yield_curve_slope_ts_z",
        "cpi_surprise",
        "cpi_surprise_ts_z",
    ],
    "nifty": ["nifty_"],
    "india_vix": ["india_vix"],
    "valuation": ["posterior_", "agreement_score", "val_"],
}

EXTRA_AUDIT_COLUMNS = [
    "is_delisted",
    "has_delisting_record",
    "record_origin",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit research dataset inputs without rebuilding the dataset.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--universe-scope",
        choices=["current_nifty500", "all_nse"],
        default="current_nifty500",
        help="Expected equity-universe scope for this dataset build.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when critical findings remain.",
    )
    parser.add_argument(
        "--snapshot-path",
        type=Path,
        default=None,
        help="Optional research snapshot parquet. Defaults to latest snapshot under data/results/research/snapshots.",
    )
    parser.add_argument(
        "--plan-signal-audit",
        type=Path,
        default=Path("tmp/northstar_v3_chunk_build/plan_signal_audit.json"),
        help="Optional plan-signal audit JSON produced by build_local_feature_chunks.py.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("tmp/northstar_v3_chunk_build/dataset_input_audit.json"),
        help="Where to write the machine-readable audit output.",
    )
    return parser.parse_args()


def _abs(project_root: Path, raw: str | Path | None) -> Path | None:
    if raw in (None, ""):
        return None
    path = Path(str(raw))
    if path.is_absolute():
        return path
    return project_root / path


def _find_latest_snapshot(project_root: Path) -> Path | None:
    snap_root = project_root / "data/results/research/snapshots"
    if not snap_root.exists():
        return None
    candidates = sorted(snap_root.rglob("research_snapshot_*.parquet"), key=lambda p: p.stat().st_mtime)
    return candidates[-1] if candidates else None


def _schema_names(path: Path) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    if path.suffix.lower() in {".parquet", ".pq"} and pq is not None:
        try:
            return [str(name) for name in pq.ParquetFile(path).schema.names]
        except Exception:  # noqa: BLE001
            return []
    if path.suffix.lower() == ".csv":
        try:
            return list(pd.read_csv(path, nrows=0).columns)
        except Exception:  # noqa: BLE001
            return []
    return []


def _read_minimal_table(path: Path) -> pd.DataFrame:
    if not path.exists() or not path.is_file():
        return pd.DataFrame()
    cols = _schema_names(path)
    wanted = [c for c in DATE_COLUMN_CANDIDATES + TICKER_COLUMN_CANDIDATES + EXTRA_AUDIT_COLUMNS if c in cols]
    try:
        if path.suffix.lower() in {".parquet", ".pq"}:
            if wanted:
                return pd.read_parquet(path, columns=wanted)
            return pd.read_parquet(path)
        if path.suffix.lower() == ".csv":
            if wanted:
                return pd.read_csv(path, usecols=lambda c: c in set(wanted))
            return pd.read_csv(path)
    except Exception:  # noqa: BLE001
        return pd.DataFrame()
    return pd.DataFrame()


def _normalize_ticker(value: Any) -> str:
    s = str(value or "").strip().upper()
    if not s:
        return ""
    if s.endswith(".NS"):
        return s
    if "." in s:
        s = s.split(".", 1)[0]
    return f"{s}.NS"


def _pick_first(columns: list[str], candidates: list[str]) -> str | None:
    available = set(columns)
    for candidate in candidates:
        if candidate in available:
            return candidate
    return None


def _table_stats(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"exists": False}
    if not path.exists():
        return {"exists": False, "path": str(path)}
    if path.is_dir():
        return {
            "exists": True,
            "path": str(path),
            "is_dir": True,
            "file_count": int(sum(1 for p in path.rglob("*") if p.is_file())),
        }

    df = _read_minimal_table(path)
    if isinstance(df.index, pd.DatetimeIndex) and "index" not in df.columns:
        df = df.reset_index()
    elif getattr(df.index, "name", None) and str(df.index.name).lower() in {"date", "datetime", "timestamp"}:
        df = df.reset_index()
    cols = list(df.columns)
    date_col = _pick_first(cols, DATE_COLUMN_CANDIDATES)
    ticker_col = _pick_first(cols, TICKER_COLUMN_CANDIDATES)

    out: dict[str, Any] = {
        "exists": True,
        "path": str(path),
        "rows": int(len(df)),
        "columns": cols[:50],
    }
    if date_col is not None:
        dt = pd.to_datetime(df[date_col], errors="coerce")
        dt = dt.dropna()
        out["date_col"] = date_col
        out["date_min"] = str(dt.min()) if not dt.empty else None
        out["date_max"] = str(dt.max()) if not dt.empty else None
    if ticker_col is not None:
        tickers = df[ticker_col].map(_normalize_ticker)
        tickers = tickers[tickers != ""]
        out["ticker_col"] = ticker_col
        out["tickers"] = int(tickers.nunique())
    if "is_delisted" in cols:
        series = df["is_delisted"]
        if hasattr(series, "astype"):
            norm = series.astype(str).str.strip().str.lower().isin({"true", "1", "yes"})
            out["is_delisted_rows"] = int(norm.sum())
    if "has_delisting_record" in cols:
        series = df["has_delisting_record"]
        if hasattr(series, "astype"):
            norm = series.astype(str).str.strip().str.lower().isin({"true", "1", "yes"})
            out["has_delisting_record_rows"] = int(norm.sum())
    if "record_origin" in cols:
        vals = df["record_origin"].dropna().astype(str).str.strip()
        vals = vals[vals != ""]
        out["record_origins"] = sorted(vals.unique().tolist())[:20]
    return out


def _load_snapshot_usage(snapshot_path: Path | None) -> dict[str, Any]:
    if snapshot_path is None or not snapshot_path.exists():
        return {"exists": False}
    schema = _schema_names(snapshot_path)
    if not schema and snapshot_path.exists():
        try:
            schema = list(pd.read_parquet(snapshot_path, columns=[]).columns)
        except Exception:  # noqa: BLE001
            schema = []

    selected: list[str] = []
    family_to_cols: dict[str, list[str]] = {}
    for family, roots in SNAPSHOT_FAMILY_ROOTS.items():
        matched: list[str] = []
        for col in schema:
            if any(str(col).startswith(root) for root in roots):
                matched.append(str(col))
        family_to_cols[family] = sorted(set(matched))
        selected.extend(matched)
    selected = sorted(set(selected))

    values = pd.read_parquet(snapshot_path, columns=selected) if selected else pd.DataFrame()
    usage: dict[str, Any] = {
        "exists": True,
        "path": str(snapshot_path),
        "rows": int(len(values)),
        "families": {},
    }
    for family, cols in family_to_cols.items():
        if not cols:
            usage["families"][family] = {
                "matched_columns": 0,
                "non_null_columns": 0,
                "sample_non_null_counts": {},
            }
            continue
        frame = values[cols].copy()
        counts = {
            str(col): int(pd.to_numeric(frame[col], errors="coerce").notna().sum())
            for col in cols
        }
        non_zero = {k: v for k, v in counts.items() if v > 0}
        usage["families"][family] = {
            "matched_columns": int(len(cols)),
            "non_null_columns": int(len(non_zero)),
            "sample_non_null_counts": dict(list(sorted(non_zero.items()))[:20]),
        }
    return usage


def _plan_signal_summary(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"exists": False}
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        return {"exists": False, "path": str(path)}
    payload = json.loads(path.read_text())
    signals = payload.get("signals", []) or []
    exact = [sig for sig in signals if str(sig.get("status")) == "exact"]
    return {
        "exists": True,
        "path": str(path),
        "blocking_signals": list(payload.get("blocking_signals", []) or []),
        "warning_signals": list(payload.get("warning_signals", []) or []),
        "low_coverage_signals": list(payload.get("low_coverage_signals", []) or []),
        "exact_signals": exact,
        "dataset_metadata": payload.get("dataset_metadata", {}) or {},
    }


def _runtime_config(project_root: Path) -> dict[str, Any]:
    return _dataset_runtime_config(
        policy_path=project_root / "config/research_policy.yaml",
        start_date=None,
        end_date=None,
        lookback_days=3200,
        max_tickers=0,
        max_rows=0,
        low_resource_mode="false",
        profile="full",
    )


def _build_source_inventory(project_root: Path, config: dict[str, Any]) -> dict[str, Any]:
    alt_root = _abs(project_root, config.get("alternative_data_path"))
    sentiment_path = _abs(project_root, config.get("sentiment_path", "data/canonical/sentiment/company_sentiment_daily.parquet"))
    market_sentiment_path = _abs(
        project_root,
        config.get("market_sentiment_path", "data/canonical/sentiment/market_sentiment_daily.parquet"),
    )
    prices_path = _abs(project_root, config.get("prices_path"))
    annual_path = _abs(project_root, config.get("fundamentals_path"))
    quarterly_path = _abs(project_root, config.get("screener_quarterly_path"))
    shareholding_path = _abs(project_root, config.get("screener_shareholding_path"))
    macro_path = _abs(project_root, config.get("macro_features_path"))
    valuation_path = _abs(project_root, config.get("valuation_posterior_path"))
    announcement_dates_path = _abs(project_root, config.get("announcement_dates_path"))

    sources: dict[str, Any] = {
        "equity_prices": {
            "enabled": True,
            "stats": _table_stats(prices_path),
        },
        "fundamentals_annual": {
            "enabled": True,
            "stats": _table_stats(annual_path),
        },
        "screener_quarterly": {
            "enabled": bool(config.get("use_screener_features", False)),
            "stats": _table_stats(quarterly_path),
        },
        "screener_shareholding": {
            "enabled": bool(config.get("use_screener_features", False)),
            "stats": _table_stats(shareholding_path),
        },
        "macro_regime_features": {
            "enabled": bool(config.get("use_macro_features", False)),
            "stats": _table_stats(macro_path),
        },
        "valuation_posterior": {
            "enabled": True,
            "stats": _table_stats(valuation_path),
        },
        "company_sentiment": {
            "enabled": True,
            "stats": _table_stats(sentiment_path),
        },
        "market_sentiment": {
            "enabled": True,
            "stats": _table_stats(market_sentiment_path),
        },
        "announcement_dates_runtime": {
            "enabled": bool(config.get("use_screener_features", False)),
            "stats": _table_stats(announcement_dates_path),
        },
        "cross_asset_prices": {
            "enabled": True,
            "stats": _table_stats(project_root / "data/canonical/macro/cross_asset_prices_daily.parquet"),
        },
        "coal_benchmark_fallback": {
            "enabled": True,
            "stats": _table_stats(project_root / "data/processed/macro/coal_benchmark_daily.parquet"),
        },
        "india_vix": {
            "enabled": True,
            "stats": _table_stats(project_root / "data/processed/india_vix.parquet"),
        },
        "nifty_prices": {
            "enabled": True,
            "stats": _table_stats(project_root / "data/processed/nifty.parquet"),
        },
        "rbi_macro_raw": {
            "enabled": True,
            "stats": _table_stats(project_root / "data/macro/comprehensive_rbi_data.parquet"),
        },
        "rbi_macro_long": {
            "enabled": True,
            "stats": _table_stats(project_root / "data/canonical/macro/rbi_macro_long.parquet"),
        },
        "rbi_macro_wide": {
            "enabled": True,
            "stats": _table_stats(project_root / "data/canonical/macro/rbi_macro_wide.parquet"),
        },
        "delisting_database": {
            "enabled": True,
            "stats": _table_stats(project_root / "data/universe/delisting_database.parquet"),
        },
        "ticker_master": {
            "enabled": True,
            "stats": _table_stats(project_root / "data/canonical/reference/ticker_master.parquet"),
        },
        "delisted_price_backfill": {
            "enabled": True,
            "stats": _table_stats(project_root / "data/processed/delisted_prices.parquet"),
        },
        "screener_delisted_raw": {
            "enabled": True,
            "stats": _table_stats(project_root / "data/raw/vendors/screener_delisted"),
        },
    }

    for family, candidates in AlternativeDataLoader.FAMILY_PATHS.items():
        resolved = None
        candidate_paths = []
        if alt_root is not None:
            for candidate in candidates:
                path = alt_root / str(candidate)
                candidate_paths.append(str(path))
                if path.exists() and resolved is None:
                    resolved = path
        sources[f"alternative_{family}"] = {
            "enabled": bool(config.get("use_alternative_features", False)),
            "candidate_paths": candidate_paths,
            "stats": _table_stats(resolved if resolved is not None else (alt_root / str(candidates[0]) if alt_root else None)),
        }

    return sources


def _delisting_overlap(project_root: Path) -> dict[str, Any]:
    prices_path = project_root / "data/canonical/prices/equity_prices_daily.parquet"
    delist_path = project_root / "data/universe/delisting_database.parquet"
    if not prices_path.exists() or not delist_path.exists():
        return {"available": False}
    prices = pd.read_parquet(prices_path, columns=["ticker"])
    delist = pd.read_parquet(delist_path)
    sym_col = "symbol" if "symbol" in delist.columns else ("ticker" if "ticker" in delist.columns else None)
    if sym_col is None:
        return {"available": False}
    prices_tickers = {tk for tk in prices["ticker"].map(_normalize_ticker).tolist() if tk}
    delist_tickers = {tk for tk in delist[sym_col].map(_normalize_ticker).tolist() if tk}
    overlap = prices_tickers & delist_tickers
    return {
        "available": True,
        "price_tickers": int(len(prices_tickers)),
        "delisted_tickers": int(len(delist_tickers)),
        "overlap_tickers": int(len(overlap)),
        "sample_overlap": sorted(list(overlap))[:20],
        "sample_missing_from_prices": sorted(list(delist_tickers - prices_tickers))[:20],
    }


def _findings(
    sources: dict[str, Any],
    snapshot_usage: dict[str, Any],
    plan_signal: dict[str, Any],
    delist_overlap: dict[str, Any],
    *,
    universe_scope: str,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    price_tickers = int(sources.get("equity_prices", {}).get("stats", {}).get("tickers", 0) or 0)
    if str(universe_scope) == "all_nse" and price_tickers == 500:
        findings.append(
            {
                "severity": "critical",
                "message": "The canonical equity price panel contains 500 tickers, so the current build is a capped 500-name universe rather than all NSE listings.",
            }
        )
    elif str(universe_scope) == "current_nifty500" and price_tickers == 500:
        findings.append(
            {
                "severity": "info",
                "message": "The canonical equity price panel is aligned to a 500-name current Nifty 500 scope.",
            }
        )

    if delist_overlap.get("available") and int(delist_overlap.get("overlap_tickers", 0)) == 0:
        findings.append(
            {
                "severity": "critical",
                "message": "The delisting database has zero ticker overlap with the canonical equity price panel, so survivorship handling is incomplete for the dataset actually being built.",
            }
        )
    elif delist_overlap.get("available"):
        overlap_tickers = int(delist_overlap.get("overlap_tickers", 0) or 0)
        delisted_tickers = int(delist_overlap.get("delisted_tickers", 0) or 0)
        overlap_pct = (overlap_tickers / max(1, delisted_tickers)) * 100.0
        if overlap_pct < 50.0:
            findings.append(
                {
                    "severity": "warning",
                    "message": (
                        f"Only {overlap_tickers}/{delisted_tickers} delisted tickers currently overlap with the canonical "
                        "equity price panel, so survivorship handling has improved but is still only partially covered."
                    ),
                }
            )
        else:
            findings.append(
                {
                    "severity": "info",
                    "message": (
                        f"{overlap_tickers}/{delisted_tickers} delisted tickers now overlap with the canonical equity "
                        "price panel."
                    ),
                }
            )

    blocking = list(plan_signal.get("blocking_signals", []) or [])
    if blocking:
        findings.append(
            {
                "severity": "critical",
                "message": f"Strict plan-signal validation is still blocked by: {', '.join(blocking)}.",
            }
        )

    for family_key, label in [
        ("fundamentals_annual", "annual fundamentals"),
        ("screener_quarterly", "quarterly fundamentals"),
        ("screener_shareholding", "shareholding"),
    ]:
        stats = sources.get(family_key, {}).get("stats", {}) or {}
        delisted_rows = int(stats.get("is_delisted_rows", 0) or 0)
        if delisted_rows > 0:
            findings.append(
                {
                    "severity": "info",
                    "message": f"Canonical {label} now includes {delisted_rows} rows flagged as delisted.",
                }
            )
        else:
            findings.append(
                {
                    "severity": "warning",
                    "message": f"Canonical {label} does not currently show any rows flagged as delisted.",
                }
            )

    rbi_raw_exists = bool(sources.get("rbi_macro_raw", {}).get("stats", {}).get("exists"))
    rbi_wide_exists = bool(sources.get("rbi_macro_wide", {}).get("stats", {}).get("exists"))
    if rbi_raw_exists or rbi_wide_exists:
        findings.append(
            {
                "severity": "info",
                "message": "RBI-derived features are available through local macro parquet artifacts and are showing up in the latest snapshot as repo/yield/CPI features.",
            }
        )

    snapshot_families = snapshot_usage.get("families", {}) if isinstance(snapshot_usage, dict) else {}
    for family in ["bulk_deals", "pledge", "ratings", "announcements", "earnings_dates", "company_sentiment", "market_sentiment"]:
        non_null = int(snapshot_families.get(family, {}).get("non_null_columns", 0) or 0)
        if non_null == 0:
            findings.append(
                {
                    "severity": "warning",
                    "message": f"The latest snapshot does not show non-null feature columns for {family}.",
                }
            )

    return findings


def _render_human_summary(report: dict[str, Any]) -> str:
    lines: list[str] = []
    builder = report["builder_flags"]
    lines.append("Builder flags:")
    for key in [
        "strict_real_data_only",
        "use_screener_features",
        "use_alternative_features",
        "use_macro_features",
        "use_sentiment_features",
    ]:
        lines.append(f"  - {key}: {builder.get(key)}")

    lines.append("")
    lines.append("Core source status:")
    for key in [
        "equity_prices",
        "fundamentals_annual",
        "screener_quarterly",
        "screener_shareholding",
        "macro_regime_features",
        "rbi_macro_raw",
        "cross_asset_prices",
        "company_sentiment",
        "market_sentiment",
        "delisting_database",
    ]:
        item = report["sources"].get(key, {})
        stats = item.get("stats", {})
        delisted_suffix = f" delisted_rows={stats.get('is_delisted_rows')}" if "is_delisted_rows" in stats else ""
        lines.append(
            "  - "
            + f"{key}: enabled={item.get('enabled')} exists={stats.get('exists')} "
            + f"rows={stats.get('rows')} tickers={stats.get('tickers')} "
            + f"date_max={stats.get('date_max')}{delisted_suffix}"
        )

    lines.append("")
    lines.append("Alternative family usage in latest snapshot:")
    for key in ["bulk_deals", "pledge", "ratings", "announcements", "earnings_dates"]:
        fam = report["snapshot_usage"].get("families", {}).get(key, {})
        lines.append(
            "  - "
            + f"{key}: matched_columns={fam.get('matched_columns')} "
            + f"non_null_columns={fam.get('non_null_columns')}"
        )

    lines.append("")
    lines.append("Sentiment and macro usage in latest snapshot:")
    for key in ["company_sentiment", "market_sentiment", "macro_pack", "rbi_dbie", "nifty", "india_vix", "valuation"]:
        fam = report["snapshot_usage"].get("families", {}).get(key, {})
        lines.append(
            "  - "
            + f"{key}: matched_columns={fam.get('matched_columns')} "
            + f"non_null_columns={fam.get('non_null_columns')}"
        )

    lines.append("")
    lines.append("Plan signal status:")
    if report["plan_signal"].get("exists"):
        lines.append(f"  - blocking_signals: {report['plan_signal'].get('blocking_signals', [])}")
        lines.append(f"  - low_coverage_signals: {report['plan_signal'].get('low_coverage_signals', [])}")
    else:
        lines.append("  - no plan_signal_audit.json found")

    lines.append("")
    lines.append("Delisting overlap:")
    overlap = report["delisting_overlap"]
    if overlap.get("available"):
        lines.append(
            "  - "
            + f"price_tickers={overlap.get('price_tickers')} "
            + f"delisted_tickers={overlap.get('delisted_tickers')} "
            + f"overlap_tickers={overlap.get('overlap_tickers')}"
        )
    else:
        lines.append("  - unavailable")

    lines.append("")
    lines.append("Findings:")
    for item in report["findings"]:
        lines.append(f"  - {item['severity'].upper()}: {item['message']}")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    snapshot_path = args.snapshot_path.resolve() if args.snapshot_path is not None else _find_latest_snapshot(project_root)
    plan_signal_path = args.plan_signal_audit
    if plan_signal_path is not None and not plan_signal_path.is_absolute():
        plan_signal_path = (project_root / plan_signal_path).resolve()

    config = _runtime_config(project_root)
    report: dict[str, Any] = {
        "project_root": str(project_root),
        "builder_flags": {
            "strict_real_data_only": bool(config.get("strict_real_data_only", False)),
            "use_screener_features": bool(config.get("use_screener_features", False)),
            "use_alternative_features": bool(config.get("use_alternative_features", False)),
            "use_macro_features": bool(config.get("use_macro_features", False)),
            "use_sentiment_features": bool(config.get("use_sentiment_features", False)),
            "universe_scope": str(args.universe_scope),
            "alternative_data_path": str(_abs(project_root, config.get("alternative_data_path"))),
            "announcement_dates_path": str(_abs(project_root, config.get("announcement_dates_path"))),
        },
        "snapshot_usage": _load_snapshot_usage(snapshot_path),
        "plan_signal": _plan_signal_summary(plan_signal_path),
        "sources": _build_source_inventory(project_root, config),
        "delisting_overlap": _delisting_overlap(project_root),
    }
    report["findings"] = _findings(
        report["sources"],
        report["snapshot_usage"],
        report["plan_signal"],
        report["delisting_overlap"],
        universe_scope=str(args.universe_scope),
    )

    output_json = args.output_json
    if output_json is not None and not output_json.is_absolute():
        output_json = project_root / output_json
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(report, indent=2))

    print(_render_human_summary(report))
    if output_json is not None:
        print("")
        print(f"JSON report written to: {output_json}")
    if args.strict and any(str(item.get("severity", "")).lower() == "critical" for item in report["findings"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
