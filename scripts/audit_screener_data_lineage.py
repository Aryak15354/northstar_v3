#!/usr/bin/env python3
"""Audit the Screener -> valuation -> research lineage for Gap 10."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.feature_factory import FeatureFactory
from src.signal_engineering.accruals_validator import AccrualsValidator
from src.valuation.buffett_module.moat_score import MoatScorer
from src.valuation.core.normalized_financials import FinancialNormalizer
from src.valuation.forensic.earnings_quality import EarningsQualityAnalyzer
from src.valuation.intrinsic_value.dcf_engine import DCFEngine
from src.valuation.valuation_feature_block import ValuationFeatureBlock


RAW_DIR = PROJECT_ROOT / "data" / "raw" / "screener" / "financials"
PIPELINE_SCRIPT = PROJECT_ROOT / "scripts" / "load_screener_to_pipeline.py"
SCRAPER_SCRIPT = PROJECT_ROOT / "scripts" / "scrape_screener_financials.py"
AUDIT_PATH = PROJECT_ROOT / "data" / "audit" / "gap10_lineage_audit.json"


CRITICAL_FIELDS = {
    "sales",
    "net_profit",
    "operating_profit",
    "other_income",
    "interest",
    "depreciation",
    "eps",
    "equity_capital",
    "reserves",
    "borrowings",
    "other_liabilities",
    "fixed_assets",
    "cwip",
    "investments",
    "other_assets",
    "cash_from_operations",
    "cash_from_investing",
    "cash_from_financing",
    "total_assets",
}


def _clean_metric(value: object) -> str:
    return (
        str(value or "")
        .strip()
        .lower()
        .replace("%", "pct")
        .replace("&", "and")
        .replace("  ", " ")
    )


def _metric_key(value: object) -> str:
    text = _clean_metric(value)
    return (
        text.replace("cash from operating activity", "cash_from_operations")
        .replace("cash from investing activity", "cash_from_investing")
        .replace("cash from financing activity", "cash_from_financing")
        .replace("cash from operations", "cash_from_operations")
        .replace("cash from investing", "cash_from_investing")
        .replace("cash from financing", "cash_from_financing")
        .replace(" ", "_")
    )


def _find_test_ticker() -> str:
    preferred = RAW_DIR / "RELIANCE_annual_pl.csv"
    if preferred.exists():
        return "RELIANCE.NS"
    for path in sorted(RAW_DIR.glob("*_annual_pl.csv")):
        return f"{path.stem.split('_', 1)[0]}.NS"
    return "RELIANCE.NS"


def _read_sample_raw() -> pd.DataFrame:
    sample = _find_test_ticker().replace(".NS", "")
    frames = []
    for suffix in ["annual_pl", "annual_bs", "annual_cf", "annual_ratios"]:
        path = RAW_DIR / f"{sample}_{suffix}.csv"
        if not path.exists():
            continue
        try:
            frames.append(pd.read_csv(path))
        except Exception:
            continue
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _search_refs(pattern: str) -> list[str]:
    cmd = ["rg", "-n", pattern, "scripts", "src"]
    proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), text=True, capture_output=True)
    if proc.returncode not in (0, 1):
        return []
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _search_file_lines(path: Path, needles: tuple[str, ...]) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    matches = []
    for idx, line in enumerate(text, start=1):
        lowered = line.lower()
        if any(needle.lower() in lowered for needle in needles):
            matches.append(f"{path}:{idx}:{line.strip()}")
    return matches


def main() -> int:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    test_ticker = _find_test_ticker()
    sample_raw = _read_sample_raw()
    normalizer = FinancialNormalizer()
    moat = MoatScorer()
    eq = EarningsQualityAnalyzer()
    accruals = AccrualsValidator()
    dcf = DCFEngine(config={})
    valuation_block = ValuationFeatureBlock({})
    as_of_date = datetime.now()

    raw_files = sorted(RAW_DIR.glob("*.csv"))
    sample_columns = sample_raw.columns.tolist() if not sample_raw.empty else []
    metrics_present = sorted({_metric_key(v) for v in sample_raw.get("metric", pd.Series(dtype=object)).dropna().tolist()})
    missing_critical = sorted(field for field in CRITICAL_FIELDS if field not in metrics_present)
    unique_tickers = sorted({path.stem.split("_", 1)[0] for path in raw_files})
    latest_mtime = max((datetime.fromtimestamp(p.stat().st_mtime) for p in raw_files), default=None)

    node2_refs = _search_refs("load_screener_to_pipeline\\.py")
    processed_outputs = [
        PROJECT_ROOT / "data" / "processed" / "screener_fundamentals_annual.csv",
        PROJECT_ROOT / "data" / "processed" / "screener_fundamentals_quarterly.csv",
        PROJECT_ROOT / "data" / "processed" / "screener_shareholding.csv",
    ]

    normalized_latest = normalizer.load_latest(test_ticker, as_of_date, "annual")
    normalized_history = normalizer.load_history(test_ticker, as_of_date, n_periods=3, frequency="annual")
    normalized_result = {
        "source_path": str(normalizer.SCREENER_DATA_PATH),
        "resolved_paths": [str(p) for p in normalizer.get_source_paths(test_ticker, "annual")],
        "success": bool(normalized_latest),
        "columns": sorted(normalized_latest.keys())[:80] if normalized_latest else [],
        "history_rows": len(normalized_history),
    }

    dcf_result = dcf.run(test_ticker, as_of_date=as_of_date)
    moat_result = moat.score(test_ticker, as_of_date=as_of_date)
    eq_result = eq.analyze(test_ticker, as_of_date=as_of_date)
    accruals_result = accruals.validate(test_ticker, as_of_date)

    feature_factory_path = PROJECT_ROOT / "src" / "research" / "feature_factory.py"
    feature_factory_matches = _search_file_lines(
        feature_factory_path,
        ("valuation", "fair_value", "dcf", "moat", "intrinsic", "margin_of_safety", "discount_to_fair", "val_"),
    )
    valuation_scores_path = valuation_block.CACHE_PATH
    valuation_scores = pd.read_parquet(valuation_scores_path) if valuation_scores_path.exists() else pd.DataFrame()

    audit = {
        "generated_at": datetime.now().isoformat(),
        "test_ticker": test_ticker,
        "node_1_scraper_output": {
            "raw_dir_exists": RAW_DIR.exists(),
            "scraper_script": str(SCRAPER_SCRIPT),
            "ticker_count": len(unique_tickers),
            "sample_columns": sample_columns,
            "latest_scrape_mtime": latest_mtime.isoformat() if latest_mtime else None,
            "sample_metrics_present": metrics_present,
            "critical_fields_missing": missing_critical,
        },
        "node_2_pipeline_loader": {
            "loader_script_exists": PIPELINE_SCRIPT.exists(),
            "loader_script": str(PIPELINE_SCRIPT),
            "called_from": node2_refs,
            "is_orphaned": len([line for line in node2_refs if "load_screener_to_pipeline.py" in line and "scripts/load_screener_to_pipeline.py:" not in line]) == 0,
            "outputs": [
                {"path": str(path), "exists": path.exists()} for path in processed_outputs
            ],
        },
        "node_3_normalized_financials": normalized_result,
        "node_4_dcf_engine": {
            "success": bool(pd.notna(pd.to_numeric(dcf_result.get("fair_value"), errors="coerce"))),
            "fair_value": pd.to_numeric(dcf_result.get("fair_value"), errors="coerce"),
            "result": {k: (float(v) if isinstance(v, (int, float)) and pd.notna(v) else v) for k, v in dcf_result.items()},
            "hardcoded_refs": _search_file_lines(
                PROJECT_ROOT / "src" / "valuation" / "intrinsic_value" / "dcf_engine.py",
                ("test_data", "mock", "hardcoded"),
            ),
        },
        "node_5_moat_scorer": {
            "success": bool(moat_result),
            "result": moat_result,
            "source_paths": [str(p) for p in normalizer.get_source_paths(test_ticker, "annual")],
        },
        "node_6_forensic_accruals": {
            "earnings_quality_uses_cashflow": "cash_from_operations" in Path(
                PROJECT_ROOT / "src" / "valuation" / "forensic" / "earnings_quality.py"
            ).read_text(encoding="utf-8"),
            "earnings_quality_result": eq_result,
            "earnings_quality_source_paths": [str(p) for p in normalizer.get_source_paths(test_ticker, "annual")],
            "accruals_validator_result": accruals_result,
            "accruals_validator_source_paths": accruals_result.get("data_source_paths", []),
        },
        "node_7_feature_factory": {
            "matches": feature_factory_matches,
            "valuation_feature_block_present": "ValuationFeatureBlock" in feature_factory_path.read_text(encoding="utf-8"),
            "valuation_columns": [c for c in FeatureFactory(config={"valuation": {"features_enabled": True}})._valuation_block.FEATURE_NAMES],
        },
        "node_8_valuation_scores_parquet": {
            "exists": valuation_scores_path.exists(),
            "path": str(valuation_scores_path),
            "columns": valuation_scores.columns.tolist() if not valuation_scores.empty else [],
            "date_min": str(pd.to_datetime(valuation_scores["date"], errors="coerce").min()) if "date" in valuation_scores.columns and not valuation_scores.empty else None,
            "date_max": str(pd.to_datetime(valuation_scores["date"], errors="coerce").max()) if "date" in valuation_scores.columns and not valuation_scores.empty else None,
            "ticker_count": int(valuation_scores["ticker"].nunique()) if "ticker" in valuation_scores.columns and not valuation_scores.empty else 0,
        },
    }

    AUDIT_PATH.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    print(json.dumps(audit, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
