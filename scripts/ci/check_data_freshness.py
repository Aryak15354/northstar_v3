#!/usr/bin/env python3
"""Fail when any scraped artifact's newest data violates its freshness invariant.

Reads config/data_freshness_invariants.yaml, inspects the newest row date (or file
mtime where no date column exists) of each artifact, and reports STALE datasets.
'error'-severity violations return a non-zero exit code so this can gate CI or a
post-collection hook; 'warn' violations only print. This is the guard that makes a
frozen scraper loud instead of silent.

    python scripts/ci/check_data_freshness.py
    python scripts/ci/check_data_freshness.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG = PROJECT_ROOT / "config" / "data_freshness_invariants.yaml"


def _business_days_between(older: pd.Timestamp, newer: pd.Timestamp) -> int:
    if pd.isna(older) or pd.isna(newer):
        return 10**6
    return int(np.busday_count(older.date(), newer.date()))


def _newest_date(path: Path, date_column) -> pd.Timestamp | None:
    if not path.exists():
        return None
    if date_column in (None, "null", ""):
        return pd.Timestamp(datetime.fromtimestamp(path.stat().st_mtime))
    try:
        if path.suffix == ".parquet":
            df = pd.read_parquet(path, columns=[date_column])
        else:
            df = pd.read_csv(path, usecols=[date_column])
    except Exception:
        # column may not exist; fall back to mtime
        return pd.Timestamp(datetime.fromtimestamp(path.stat().st_mtime))
    dates = pd.to_datetime(df[date_column], errors="coerce")
    if dates.notna().sum() == 0:
        return None
    return dates.max()


def check(config_path: Path = CONFIG) -> tuple[int, list[dict]]:
    spec = yaml.safe_load(config_path.read_text())
    today = pd.Timestamp.now().normalize()
    results: list[dict] = []
    exit_code = 0
    for name, cfg in spec.get("datasets", {}).items():
        path = PROJECT_ROOT / cfg["path"]
        newest = _newest_date(path, cfg.get("date_column"))
        severity = cfg.get("severity", "error")
        max_age = int(cfg["max_age_days"])
        basis = cfg.get("calendar_basis", "calendar")
        if newest is None:
            status = "MISSING"
            age = None
        else:
            newest_n = newest.normalize()
            if basis == "business":
                age = _business_days_between(newest_n, today)
            else:
                age = int((today - newest_n).days)
            status = "FRESH" if age <= max_age else "STALE"
        record = {
            "dataset": name,
            "path": cfg["path"],
            "newest": None if newest is None else str(newest),
            "age_days": age,
            "max_age_days": max_age,
            "basis": basis,
            "severity": severity,
            "status": status,
        }
        results.append(record)
        if status in ("STALE", "MISSING") and severity == "error":
            exit_code = 1
    return exit_code, results


def main() -> int:
    ap = argparse.ArgumentParser(description="Check data freshness invariants.")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    exit_code, results = check()
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            flag = {"FRESH": "ok  ", "STALE": "STALE", "MISSING": "MISS"}[r["status"]]
            sev = "" if r["status"] == "FRESH" else f" [{r['severity']}]"
            print(
                f"[{flag}] {r['dataset']:24s} age={r['age_days']} / max {r['max_age_days']}d "
                f"({r['basis']}) newest={r['newest']}{sev}"
            )
        bad = [r for r in results if r["status"] != "FRESH"]
        print(f"\n{len(results) - len(bad)}/{len(results)} datasets fresh; "
              f"exit={'FAIL' if exit_code else 'PASS'}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
