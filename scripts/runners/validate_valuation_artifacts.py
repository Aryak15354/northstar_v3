#!/usr/bin/env python3
"""
Strict schema and sanity validation for valuation artifacts:
- data/processed/valuation.parquet
- data/processed/valuation_families.parquet
- data/processed/valuation_posterior.parquet
- data/processed/portfolio_valuation_state.parquet
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INTEGRITY_DIR = PROJECT_ROOT / "data/processed/integrity"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _range_check(df: pd.DataFrame, col: str, low: float, high: float, allow_na: bool = True) -> Tuple[bool, str]:
    if col not in df.columns:
        return False, f"missing_column:{col}"
    s = _to_numeric(df[col])
    if not allow_na and s.isna().any():
        return False, f"nulls_not_allowed:{col}:{int(s.isna().sum())}"
    s = s.dropna()
    if s.empty:
        return False, f"all_nan:{col}"
    bad = (~s.between(low, high)).sum()
    if int(bad) > 0:
        return False, f"out_of_range:{col}:{int(bad)}"
    return True, "ok"


def _required_columns(df: pd.DataFrame, cols: List[str]) -> Tuple[bool, List[str]]:
    missing = [c for c in cols if c not in df.columns]
    return len(missing) == 0, missing


def _validate_valuation(df: pd.DataFrame) -> Tuple[List[str], List[str]]:
    errs: List[str] = []
    warns: List[str] = []
    required = [
        "ticker",
        "date",
        "final_value_index",
        "true_undervaluation",
        "final_value_index_core",
        "posterior_gap",
        "posterior_confidence",
        "macro_adjustment_factor",
        "family_status",
    ]
    ok, missing = _required_columns(df, required)
    if not ok:
        errs.append(f"valuation_missing_columns:{missing}")
        return errs, warns

    if len(df) == 0:
        errs.append("valuation_empty")
        return errs, warns

    dups = int(df["ticker"].astype(str).duplicated().sum())
    if dups > 0:
        warns.append(f"valuation_duplicate_tickers:{dups}")

    for col, lo, hi in [
        ("final_value_index", 0.0, 100.0),
        ("true_undervaluation", 0.0, 100.0),
        ("final_value_index_core", 0.0, 100.0),
        ("posterior_gap", -2.0, 2.0),
        ("posterior_confidence", 0.0, 1.0),
        ("macro_adjustment_factor", 0.5, 1.5),
    ]:
        good, msg = _range_check(df, col, lo, hi, allow_na=False)
        if not good:
            errs.append(f"valuation_{msg}")
    return errs, warns


def _validate_families(df: pd.DataFrame) -> Tuple[List[str], List[str]]:
    errs: List[str] = []
    warns: List[str] = []
    required = [
        "ticker",
        "date",
        "reference_value",
        "core_value",
        "core_gap",
        "core_confidence",
        "fcff_value",
        "fcff_gap",
        "residual_value",
        "transaction_value",
        "credit_value",
        "real_option_value",
        "macro_percentile",
        "macro_adjustment_factor",
        "family_status",
    ]
    ok, missing = _required_columns(df, required)
    if not ok:
        errs.append(f"families_missing_columns:{missing}")
        return errs, warns
    if len(df) == 0:
        errs.append("families_empty")
        return errs, warns
    dups = int(df["ticker"].astype(str).duplicated().sum())
    if dups > 0:
        errs.append(f"families_duplicate_tickers:{dups}")

    for col, lo, hi in [
        ("core_confidence", 0.0, 1.0),
        ("fcff_confidence", 0.0, 1.0),
        ("fcfe_confidence", 0.0, 1.0),
        ("ddm_confidence", 0.0, 1.0),
        ("apv_confidence", 0.0, 1.0),
        ("residual_confidence", 0.0, 1.0),
        ("transaction_confidence", 0.0, 1.0),
        ("lbo_confidence", 0.0, 1.0),
        ("credit_confidence", 0.0, 1.0),
        ("real_option_confidence", 0.0, 1.0),
        ("macro_percentile", 0.0, 1.0),
        ("macro_adjustment_factor", 0.5, 1.5),
        ("default_probability", 0.0, 1.0),
    ]:
        if col in df.columns:
            good, msg = _range_check(df, col, lo, hi, allow_na=True)
            if not good:
                errs.append(f"families_{msg}")
    return errs, warns


def _validate_posterior(df: pd.DataFrame) -> Tuple[List[str], List[str]]:
    errs: List[str] = []
    warns: List[str] = []
    required = [
        "ticker",
        "date",
        "posterior_gap",
        "posterior_value",
        "posterior_variance",
        "model_dispersion",
        "agreement_score",
        "regime_modifier",
        "macro_compression",
        "posterior_confidence",
        "regime_low_vol_prob",
        "regime_normal_prob",
        "regime_crisis_prob",
    ]
    ok, missing = _required_columns(df, required)
    if not ok:
        errs.append(f"posterior_missing_columns:{missing}")
        return errs, warns
    if len(df) == 0:
        errs.append("posterior_empty")
        return errs, warns

    dups = int(df["ticker"].astype(str).duplicated().sum())
    if dups > 0:
        errs.append(f"posterior_duplicate_tickers:{dups}")

    for col, lo, hi in [
        ("posterior_gap", -2.0, 2.0),
        ("posterior_variance", 0.0, 100.0),
        ("agreement_score", 0.0, 1.0),
        ("posterior_confidence", 0.0, 1.0),
        ("macro_compression", 0.5, 1.5),
        ("regime_low_vol_prob", 0.0, 1.0),
        ("regime_normal_prob", 0.0, 1.0),
        ("regime_crisis_prob", 0.0, 1.0),
    ]:
        good, msg = _range_check(df, col, lo, hi, allow_na=False)
        if not good:
            errs.append(f"posterior_{msg}")
    probs = (
        _to_numeric(df["regime_low_vol_prob"]).fillna(0.0)
        + _to_numeric(df["regime_normal_prob"]).fillna(0.0)
        + _to_numeric(df["regime_crisis_prob"]).fillna(0.0)
    )
    dev = float((probs - 1.0).abs().max())
    if dev > 0.02:
        errs.append(f"posterior_regime_probs_not_normalized:max_dev={dev:.6f}")
    return errs, warns


def _validate_state(df: pd.DataFrame) -> Tuple[List[str], List[str]]:
    errs: List[str] = []
    warns: List[str] = []
    required = [
        "date",
        "market_percentile",
        "sector_dispersion",
        "aggregate_gap_mean",
        "aggregate_gap_std",
        "bubble_probability",
        "valuation_regime",
    ]
    ok, missing = _required_columns(df, required)
    if not ok:
        errs.append(f"state_missing_columns:{missing}")
        return errs, warns
    if len(df) == 0:
        errs.append("state_empty")
        return errs, warns

    for col, lo, hi in [
        ("market_percentile", 0.0, 1.0),
        ("bubble_probability", 0.0, 1.0),
    ]:
        good, msg = _range_check(df, col, lo, hi, allow_na=False)
        if not good:
            errs.append(f"state_{msg}")
    return errs, warns


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate valuation artifacts schema")
    p.add_argument("--valuation-path", type=str, default="data/processed/valuation.parquet")
    p.add_argument("--families-path", type=str, default="data/processed/valuation_families.parquet")
    p.add_argument("--posterior-path", type=str, default="data/processed/valuation_posterior.parquet")
    p.add_argument("--state-path", type=str, default="data/processed/portfolio_valuation_state.parquet")
    p.add_argument("--strict", action="store_true", help="Exit non-zero on warnings as well as errors")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    paths = {
        "valuation": PROJECT_ROOT / args.valuation_path,
        "families": PROJECT_ROOT / args.families_path,
        "posterior": PROJECT_ROOT / args.posterior_path,
        "state": PROJECT_ROOT / args.state_path,
    }
    errors: List[str] = []
    warnings: List[str] = []
    tables: Dict[str, pd.DataFrame] = {}

    for name, path in paths.items():
        if not path.exists():
            errors.append(f"missing_artifact:{name}:{path}")
            continue
        try:
            tables[name] = pd.read_parquet(path)
        except Exception as e:
            errors.append(f"read_failed:{name}:{e}")

    if "valuation" in tables:
        e, w = _validate_valuation(tables["valuation"])
        errors.extend(e)
        warnings.extend(w)
    if "families" in tables:
        e, w = _validate_families(tables["families"])
        errors.extend(e)
        warnings.extend(w)
    if "posterior" in tables:
        e, w = _validate_posterior(tables["posterior"])
        errors.extend(e)
        warnings.extend(w)
    if "state" in tables:
        e, w = _validate_state(tables["state"])
        errors.extend(e)
        warnings.extend(w)

    if {"valuation", "families", "posterior"}.issubset(tables.keys()):
        tick_val = set(tables["valuation"]["ticker"].astype(str))
        tick_fam = set(tables["families"]["ticker"].astype(str))
        tick_pos = set(tables["posterior"]["ticker"].astype(str))
        if tick_val != tick_fam:
            errors.append(f"ticker_set_mismatch:valuation_vs_families:diff={len(tick_val.symmetric_difference(tick_fam))}")
        if tick_val != tick_pos:
            errors.append(f"ticker_set_mismatch:valuation_vs_posterior:diff={len(tick_val.symmetric_difference(tick_pos))}")

    status = "ok" if not errors and not warnings else ("warn" if not errors else "failed")
    report = {
        "timestamp": _utc_now_iso(),
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "row_counts": {k: int(len(v)) for k, v in tables.items()},
        "paths": {k: str(v) for k, v in paths.items()},
    }

    INTEGRITY_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    latest = INTEGRITY_DIR / "valuation_schema_validation_latest.json"
    stamped = INTEGRITY_DIR / f"valuation_schema_validation_{ts}.json"
    latest.write_text(json.dumps(report, indent=2, default=str))
    stamped.write_text(json.dumps(report, indent=2, default=str))

    print(json.dumps(report, indent=2, default=str))
    if errors:
        return 1
    if args.strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

