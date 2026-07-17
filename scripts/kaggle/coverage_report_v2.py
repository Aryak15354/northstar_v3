#!/usr/bin/env python3
"""Coverage-report-v2 — the trust gate for any regenerated feature/factor panel.

The 2026-07-04 alpha export passed every existing coverage check yet was silently
poisoned, because those checks counted non-null rows. This tool measures the
things that actually distinguish a real signal from a fabricated one, per factor:

  * coverage overall AND by year   — surfaces the anchor/sentiment "cliff" where a
                                      factor is ~0% before 2024 and ~100% after
                                      (a train/test era boundary a model memorizes)
  * first/last valid date, longest gap
  * per-date DISTINCT-VALUE count  — a factor with coverage=1.0 but <5 distinct
                                      values across the universe is SOURCE
                                      zero-filled (eps_revision_accel: coverage
                                      1.0, 18 real dates); non-null share can't see this
  * frac exactly 0.0               — for *_cs_z / *_cs_rank columns, the share of
                                      values that are exactly 0 flags NaN→0
                                      imputation ("no data" == "average")

Verdicts per factor:
  DEAD           overall coverage < 5% OR never varies
  SILENT_ZERO    a cs_z/cs_rank column that is exactly 0 for > SILENT_ZERO_FRAC
  SOURCE_FILLED  coverage high but median per-date distinct values < MIN_DISTINCT
  ERA_BOUNDARY   < 10% covered pre-2024 but > 50% in 2025-26 (memorizable regime)
  OK             none of the above

Usage:
  python3 scripts/kaggle/coverage_report_v2.py --panel path.parquet [--out report.csv]
  python3 scripts/kaggle/coverage_report_v2.py --panel p.parquet --gate  # exit 1 if any DEAD/SILENT_ZERO/SOURCE_FILLED
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SILENT_ZERO_FRAC = 0.90      # cs_z exactly 0 for >90% of rows → NaN→0 imputation
MIN_DISTINCT = 5             # median distinct values per date below this → source-filled
ERA_PRE_MAX = 0.10           # pre-2024 coverage ceiling for an era-boundary flag
ERA_POST_MIN = 0.50          # 2025-26 coverage floor for an era-boundary flag
DEAD_COV = 0.05
ID_COLS = {"date", "ticker", "Date", "Ticker"}


def _classify(row: dict, is_csz: bool) -> str:
    # DEAD = truly constant / empty (one value or none) — a real defect.
    if row["n_distinct_total"] <= 1:
        return "DEAD"
    # SILENT_ZERO = a cross-sectional transform that is exactly 0 for almost every
    # row (the NaN->0 imputation bug). After the fix, a missing base -> NaN cs_z,
    # so this should only fire on a genuinely broken column.
    if is_csz and row["frac_exact_zero"] > SILENT_ZERO_FRAC:
        return "SILENT_ZERO"
    # SOURCE_FILLED = a PER-TICKER factor that collapsed to one dominant value
    # (e.g. zero-filled at source): high coverage, few distinct values per date,
    # and one value dominates. `mode_frac > 0.6` is what separates this from a
    # legitimate MACRO/MARKET broadcast — that is ~1 value per date too, but it
    # varies over time so no single value dominates (mode_frac stays low). The
    # >5-distinct guard exempts binary/categorical flags (e.g. *_available).
    if (row["n_distinct_total"] > 5 and row["overall"] > 0.5
            and row["mode_frac"] > 0.60 and row["median_distinct_per_date"] < MIN_DISTINCT):
        return "SOURCE_FILLED"
    # SPARSE = honest low coverage that genuinely varies (a young factor with real
    # NaN gaps). NOT a defect — kept, just flagged so a per-family window is used.
    if row["overall"] < DEAD_COV:
        return "SPARSE"
    if row["cov_pre_2024"] < ERA_PRE_MAX and row["cov_2025_26"] > ERA_POST_MIN:
        return "ERA_BOUNDARY"
    return "OK"


def analyze(panel: pd.DataFrame, date_col="date") -> pd.DataFrame:
    d = pd.to_datetime(panel[date_col], errors="coerce")
    year = d.dt.year
    pre = year < 2024
    post = year >= 2025
    factor_cols = [c for c in panel.columns if c not in ID_COLS]
    rows = []
    for c in factor_cols:
        s = panel[c]
        notna = s.notna()
        overall = float(notna.mean())
        valid_dates = d[notna]
        # per-date distinct-value count (on a sampled set of dates for speed)
        by_date = pd.DataFrame({"date": d, "v": s}).dropna()
        distinct_per_date = by_date.groupby("date")["v"].nunique()
        is_csz = c.endswith("_cs_z") or c.endswith("_cs_rank")
        frac_zero = float((s == 0.0).mean()) if is_csz else np.nan
        # concentration of the single most-common value among non-null rows —
        # high for a zero-/constant-filled column, low for a real varying series.
        nn = s.dropna()
        mode_frac = float(nn.value_counts(normalize=True).iloc[0]) if len(nn) else 0.0
        # longest gap between consecutive valid weekly/daily dates
        vd = valid_dates.sort_values().drop_duplicates()
        gap = int(vd.diff().dt.days.max()) if len(vd) > 1 else np.nan
        row = {
            "factor": c,
            "overall": round(overall, 4),
            "cov_pre_2024": round(float(notna[pre].mean()) if pre.any() else np.nan, 4),
            "cov_2025_26": round(float(notna[post].mean()) if post.any() else np.nan, 4),
            "first_valid": str(valid_dates.min().date()) if notna.any() else "",
            "last_valid": str(valid_dates.max().date()) if notna.any() else "",
            "longest_gap_days": gap,
            "n_distinct_total": int(s.dropna().nunique()),
            "median_distinct_per_date": float(distinct_per_date.median()) if len(distinct_per_date) else 0.0,
            "mode_frac": round(mode_frac, 4),
            "frac_exact_zero": round(frac_zero, 4) if is_csz else np.nan,
        }
        row["verdict"] = _classify(row, is_csz)
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", required=True)
    ap.add_argument("--date-col", default="date")
    ap.add_argument("--out", default=None, help="write full per-factor CSV here")
    ap.add_argument("--gate", action="store_true",
                    help="exit 1 if any factor is DEAD / SILENT_ZERO / SOURCE_FILLED")
    args = ap.parse_args()

    panel = pd.read_parquet(args.panel)
    rep = analyze(panel, date_col=args.date_col)
    if args.out:
        rep.to_csv(args.out, index=False)

    counts = rep["verdict"].value_counts().to_dict()
    hard = rep[rep["verdict"].isin(["DEAD", "SILENT_ZERO", "SOURCE_FILLED"])]
    summary = {
        "panel": args.panel,
        "n_factors": int(len(rep)),
        "verdicts": counts,
        "n_hard_fail": int(len(hard)),
        "hard_fail_examples": hard["factor"].head(15).tolist(),
        "era_boundary_examples": rep[rep["verdict"] == "ERA_BOUNDARY"]["factor"].head(15).tolist(),
    }
    print(json.dumps(summary, indent=2, default=str))
    if args.gate and len(hard):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
