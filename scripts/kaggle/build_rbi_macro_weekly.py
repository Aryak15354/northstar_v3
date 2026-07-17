#!/usr/bin/env python3
"""Build a publication-lagged weekly RBI macro panel (Phase 0.6).

The alpha export shipped only 17 GST columns + the repo rate as "macro", while
the real treasure — `data/canonical/macro/rbi_macro_long.parquet`, 155 RBI
indicator series (1951 → 2026) across daily/weekly/fortnightly/monthly/quarterly
frequencies — never reached the feature files. This script turns that long-format
store into a leak-safe weekly panel on the SAME Friday cadence as the equity
panel, so macro series can be tested as features / transmission signals.

THE WHOLE GAME IS PUBLICATION LAG. A macro reading dated for period P is not
knowable until RBI publishes it, which lags the period. If you align a macro
series to the Friday it is *dated* rather than the Friday it was *released*, you
inject look-ahead and every downstream IC is inflated. So each series is shifted
to an `available_date = period_date + publication_lag` and then as-of joined
(direction=backward) onto the weekly grid — a Friday only ever sees macro data
that had genuinely been released by then.

Lags here are CONSERVATIVE per-frequency defaults (longer = safer against
look-ahead); refine per-series with the actual RBI release calendar via
SLUG_LAG_OVERRIDES before making any tight-timing claim. Dating conventions
differ and are handled: monthly series are stamped at the month START (CPI for
Jan → 2025-01-01, released ~mid-Feb), quarterly at the quarter END.

Outputs (under data/processed/macro/):
  rbi_macro_weekly.parquet   wide: date(Fri) x [slug, slug_chg4w, slug_yoy,
                             slug_z, slug_trend13w, slug_age_weeks]
  rbi_macro_weekly_manifest.json   per-slug freq, lag, unit, coverage, span

Usage:
  python3 scripts/kaggle/build_rbi_macro_weekly.py
  python3 scripts/kaggle/build_rbi_macro_weekly.py --start 2019-01-04 --json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC = PROJECT_ROOT / "data" / "canonical" / "macro" / "rbi_macro_long.parquet"
OUT_DIR = PROJECT_ROOT / "data" / "processed" / "macro"
GRID_START = "2019-01-04"          # first Friday of the equity panel
MIN_Z_OBS = 52                      # ~1y of weekly history before a z-score is meaningful

# Conservative publication lag (calendar days) from the series' STAMPED date to
# the date the reading is first public. Accounts for the dating convention:
#   monthly is stamped at month-START, quarterly at quarter-END (see module doc).
FREQ_LAG_DAYS = {
    "daily": 1,          # market/policy rates known next session
    "weekly": 7,         # RBI weekly bulletin (e.g. forex reserves) ~1w later
    "fortnightly": 21,   # SCB fortnightly credit/deposits ~3w later
    "monthly": 45,       # month-start stamp + ~2w past month-end (CPI/IIP)
    "quarterly": 75,     # quarter-end stamp + ~2.5m (BoP/GDP/external debt)
}
# Per-series overrides when the true release date is known (tighten or loosen).
# Example placeholders — populate from the RBI release calendar as needed:
SLUG_LAG_OVERRIDES: dict[str, int] = {
    # "consumer_price_index_2012_100": 42,   # CPI ~12 days after month-end
    # "repo_rate": 0,                         # policy rate effective immediately
}


def load_long() -> pd.DataFrame:
    df = pd.read_parquet(SRC, columns=["date", "frequency", "indicator_slug",
                                       "unit", "value"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["date", "indicator_slug", "value"])
    # slug+date is unique in the source; guard anyway (keep last if not).
    df = df.sort_values("date").drop_duplicates(["indicator_slug", "date"], keep="last")
    return df


def lag_days_for(slug: str, freq: str) -> int:
    if slug in SLUG_LAG_OVERRIDES:
        return int(SLUG_LAG_OVERRIDES[slug])
    return int(FREQ_LAG_DAYS.get(freq, 45))


def weekly_grid(start: str, end: pd.Timestamp) -> pd.DatetimeIndex:
    # Fridays inclusive, matching the equity panel cadence.
    return pd.date_range(start=start, end=end, freq="W-FRI")


def _transforms(s: pd.Series) -> pd.DataFrame:
    """Weekly transforms on an as-of aligned level series (indexed by grid date).
    All backward-looking only; no future information."""
    out = pd.DataFrame(index=s.index)
    out["level"] = s
    out["chg4w"] = s - s.shift(4)
    prev_yr = s.shift(52)
    out["yoy"] = np.where(prev_yr.abs() > 1e-9, s / prev_yr - 1.0, np.nan)
    # expanding z-score with a minimum history, so early weeks aren't spurious
    mean = s.expanding(MIN_Z_OBS).mean()
    std = s.expanding(MIN_Z_OBS).std()
    out["z"] = np.where(std > 1e-9, (s - mean) / std, np.nan)
    # 13-week linear slope (per-week), normalized by level scale
    out["trend13w"] = (s - s.shift(13)) / 13.0
    return out


def build(start: str = GRID_START) -> tuple[pd.DataFrame, list[dict]]:
    df = load_long()
    freq_by_slug = df.drop_duplicates("indicator_slug").set_index("indicator_slug")["frequency"]
    unit_by_slug = df.drop_duplicates("indicator_slug").set_index("indicator_slug")["unit"]

    # grid ends at the last Friday for which ANY series is already released
    df["available_date"] = df["date"] + pd.to_timedelta(
        [lag_days_for(sl, freq_by_slug[sl]) for sl in df["indicator_slug"]], unit="D")
    grid = weekly_grid(start, df["available_date"].max())
    base = pd.DataFrame({"date": grid})

    columns = {"date": base["date"].values}   # collect then concat once (no fragmentation)
    manifest = []
    for slug, g in df.groupby("indicator_slug"):
        freq = freq_by_slug[slug]
        lag = lag_days_for(slug, freq)
        g = (g[["available_date", "date", "value"]]
             .rename(columns={"date": "source_date"})
             .sort_values("available_date"))
        merged = pd.merge_asof(base, g, left_on="date", right_on="available_date",
                               direction="backward")
        level = merged["value"]
        level.index = base["date"]
        tf = _transforms(level)
        # staleness: weeks between the grid date and the source period date
        age_weeks = (base["date"].values - merged["source_date"].values) / np.timedelta64(1, "W")
        columns[slug] = tf["level"].values
        columns[f"{slug}_chg4w"] = tf["chg4w"].values
        columns[f"{slug}_yoy"] = tf["yoy"].values
        columns[f"{slug}_z"] = tf["z"].values
        columns[f"{slug}_trend13w"] = tf["trend13w"].values
        columns[f"{slug}_age_weeks"] = np.round(age_weeks, 1)

        cov = float(level.notna().mean())
        manifest.append({
            "slug": slug, "frequency": freq, "publication_lag_days": lag,
            "unit": (str(unit_by_slug[slug]) or "").strip(),
            "n_source_obs": int(len(g)),
            "source_first": str(g["source_date"].min().date()),
            "source_last": str(g["source_date"].max().date()),
            "grid_coverage": round(cov, 3),
        })
    wide = pd.DataFrame(columns)
    return wide, manifest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=GRID_START)
    ap.add_argument("--json", action="store_true", help="print manifest summary as JSON")
    args = ap.parse_args()

    wide, manifest = build(args.start)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    panel_path = OUT_DIR / "rbi_macro_weekly.parquet"
    man_path = OUT_DIR / "rbi_macro_weekly_manifest.json"
    wide.to_parquet(panel_path, index=False)
    summary = {
        "panel": str(panel_path),
        "rows": int(len(wide)),
        "grid_start": str(wide["date"].min().date()),
        "grid_end": str(wide["date"].max().date()),
        "n_series": len(manifest),
        "n_columns": int(wide.shape[1]),
        "by_frequency": pd.Series([m["frequency"] for m in manifest]).value_counts().to_dict(),
        "low_coverage_series": [m["slug"] for m in manifest if m["grid_coverage"] < 0.5],
    }
    man_path.write_text(json.dumps({"summary": summary, "series": manifest},
                                   indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str) if args.json else
          f"✅ {panel_path.name}: {summary['rows']} Fridays x {summary['n_columns']} cols "
          f"({summary['n_series']} series {summary['grid_start']}→{summary['grid_end']}); "
          f"manifest → {man_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
