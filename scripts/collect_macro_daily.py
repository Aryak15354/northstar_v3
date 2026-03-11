#!/usr/bin/env python3
"""Daily macro collection orchestrator (CEA daily + GST monthly checks)."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

from src.signals.macro.macro_regime import MacroRegimeBuilder
from src.signals.macro.sector_mapper import SectorMapper


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Collect macro data (CEA daily + GST monthly) and rebuild macro features.")
    p.add_argument("--start-year", type=int, default=0, help="CEA backfill start year (0 = auto infer).")
    p.add_argument("--gst-start-year", type=int, default=0, help="GST backfill start year (0 = auto infer).")
    p.add_argument("--resume", action="store_true", default=True)
    p.add_argument("--no-resume", action="store_false", dest="resume")
    p.add_argument("--delay-min", type=float, default=0.2, help="Per-request min delay passed to scrapers.")
    p.add_argument("--delay-max", type=float, default=0.8, help="Per-request max delay passed to scrapers.")
    p.add_argument("--skip-gst", action="store_true", help="Skip GST scrape for this run.")
    p.add_argument(
        "--force-gst",
        action="store_true",
        help="Run GST scrape even before the 15th of month.",
    )
    return p.parse_args()


def _run(cmd: list[str]) -> int:
    print(f"[macro-daily] running: {' '.join(cmd)}")
    return int(subprocess.run(cmd).returncode)


def _latest_power_date(path: Path) -> pd.Timestamp | None:
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
    except Exception:
        return None
    if df.empty or "date" not in df.columns:
        return None
    d = pd.to_datetime(df["date"], errors="coerce")
    return pd.Timestamp(d.max()) if d.notna().any() else None


def _latest_gst_month(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        df = pd.read_parquet(path)
    except Exception:
        return None
    if df.empty:
        return None
    if "year_month" in df.columns:
        return str(df["year_month"].dropna().astype(str).max())
    if "date" in df.columns:
        d = pd.to_datetime(df["date"], errors="coerce")
        if d.notna().any():
            return str(d.max().strftime("%Y-%m"))
    return None


def _normalize_ticker(value: object) -> str:
    s = str(value or "").strip().upper()
    if not s:
        return ""
    if s.endswith(".NS"):
        return s
    if "." in s:
        s = s.split(".", 1)[0]
    return f"{s}.NS"


def _load_macro_metadata() -> pd.DataFrame:
    rows: list[dict] = []

    sm_path = Path("data/processed/sector_mapping.csv")
    if sm_path.exists():
        try:
            sm = pd.read_csv(sm_path)
        except Exception:
            sm = pd.DataFrame()
        if not sm.empty:
            for r in sm.to_dict("records"):
                rows.append(
                    {
                        "ticker": _normalize_ticker(r.get("ticker")),
                        "sector": str(r.get("sector", "") or "").strip(),
                        "industry": str(r.get("industry", "") or "").strip(),
                        "state": str(r.get("state", "") or "").strip(),
                    }
                )

    nf_path = Path("universe/nifty500.csv")
    if nf_path.exists():
        try:
            nf = pd.read_csv(nf_path)
        except Exception:
            nf = pd.DataFrame()
        if not nf.empty:
            for r in nf.to_dict("records"):
                rows.append(
                    {
                        "ticker": _normalize_ticker(r.get("Symbol")),
                        "sector": str(r.get("Industry", "") or "").strip(),
                        "industry": str(r.get("Industry", "") or "").strip(),
                        "state": "",
                    }
                )

    if not rows:
        return pd.DataFrame(columns=["ticker", "sector", "industry", "state"])
    out = pd.DataFrame(rows)
    out = out[out["ticker"] != ""].drop_duplicates(subset=["ticker"], keep="first")
    return out.reset_index(drop=True)


def _rebuild_macro_features(
    power_path: Path,
    gst_path: Path,
    output_path: Path,
) -> pd.DataFrame:
    try:
        power_df = pd.read_parquet(power_path) if power_path.exists() else pd.DataFrame()
    except Exception:
        power_df = pd.DataFrame()
    try:
        gst_df = pd.read_parquet(gst_path) if gst_path.exists() else pd.DataFrame()
    except Exception:
        gst_df = pd.DataFrame()

    metadata_df = _load_macro_metadata()
    mapper = SectorMapper()
    builder = MacroRegimeBuilder(output_path=str(output_path))
    out = builder.build_combined_features(gst_df, power_df, mapper, metadata_df)
    return out


def main() -> int:
    args = parse_args()
    today = pd.Timestamp.today().normalize()
    cea_path = Path("data/processed/macro/cea_power_daily.parquet")
    gst_path = Path("data/processed/macro/gst_ewaybill_monthly.parquet")

    prev_power = _latest_power_date(cea_path)
    prev_gst = _latest_gst_month(gst_path)

    start_year = int(args.start_year) if int(args.start_year) > 0 else (prev_power.year if prev_power is not None else 2018)
    cea_cmd = [
        sys.executable,
        "scripts/scrape_cea_power.py",
        "--start-year",
        str(start_year),
        "--delay-min",
        str(float(args.delay_min)),
        "--delay-max",
        str(float(args.delay_max)),
        "--resume" if bool(args.resume) else "--no-resume",
    ]
    rc = _run(cea_cmd)
    if rc != 0:
        return rc

    # GST new month usually available mid-next month; scrape only after 15th unless forced.
    run_gst = (not bool(args.skip_gst)) and (bool(args.force_gst) or int(today.day) >= 15)
    if run_gst:
        gst_start_year = (
            int(args.gst_start_year)
            if int(args.gst_start_year) > 0
            else int((pd.to_datetime(prev_gst + "-01") if prev_gst else pd.Timestamp("2018-01-01")).year)
        )
        gst_cmd = [
            sys.executable,
            "scripts/scrape_gst_ewaybill.py",
            "--start-year",
            str(gst_start_year),
            "--delay-min",
            str(float(args.delay_min)),
            "--delay-max",
            str(float(args.delay_max)),
            "--resume" if bool(args.resume) else "--no-resume",
        ]
        rc = _run(gst_cmd)
        if rc != 0:
            return rc
    else:
        reason = "explicit --skip-gst" if bool(args.skip_gst) else "day<15 and --force-gst not set"
        print(f"[macro-daily] skipping GST scrape ({reason})")

    now_power = _latest_power_date(cea_path)
    now_gst = _latest_gst_month(gst_path)
    macro_out_path = Path("data/processed/macro/macro_regime_features.parquet")
    macro_df = _rebuild_macro_features(cea_path, gst_path, macro_out_path)

    print(f"=== Macro Daily Collection - {today.date()} ===")
    if prev_power is not None and now_power is not None:
        delta = int((pd.to_datetime(now_power) - pd.to_datetime(prev_power)).days)
        print(f"[CEA Power] Last date in DB: {prev_power.date()} | New records: {max(delta, 0)}")
    else:
        print("[CEA Power] Last date in DB: NA | New records: NA")

    if prev_gst and now_gst:
        print(f"[GST E-Way] Last month in DB: {prev_gst} | Latest now: {now_gst}")
    else:
        print("[GST E-Way] Last month in DB: NA | Latest now: NA")

    if macro_df.empty:
        print("[Macro Features] rebuilt rows=0")
    else:
        market_rows = int((macro_df.get("ticker", pd.Series(dtype=str)).astype(str).str.upper() == "MARKET").sum())
        sector_rows = int(len(macro_df) - market_rows)
        d = pd.to_datetime(macro_df.get("date"), errors="coerce")
        print(
            f"[Macro Features] rebuilt rows={len(macro_df)} market_rows={market_rows} sector_rows={sector_rows} "
            f"date_range={d.min().date() if d.notna().any() else 'NA'} to {d.max().date() if d.notna().any() else 'NA'}"
        )

    if cea_path.exists():
        try:
            cea = pd.read_parquet(cea_path)
            if not cea.empty:
                cea["date"] = pd.to_datetime(cea["date"], errors="coerce")
                latest = cea.sort_values("date", kind="mergesort").tail(1).iloc[0]
                print(
                    f"[CEA Power] Today All-India: {float(pd.to_numeric(latest.get('energy_met_mu'), errors='coerce') or 0.0):,.0f} MU "
                    f"| Peak: {float(pd.to_numeric(latest.get('peak_met_gw'), errors='coerce') or 0.0):,.0f} GW "
                    f"| Deficit: {float(pd.to_numeric(latest.get('deficit_pct'), errors='coerce') or 0.0):.1f}%"
                )
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
