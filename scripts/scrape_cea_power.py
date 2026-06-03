#!/usr/bin/env python3
"""Scrape CEA/NPP power activity data (Excel-first, NPP DGR fallback)."""

from __future__ import annotations

import argparse
import io
import os
import random
import re
import time
from datetime import date
from pathlib import Path
import warnings

import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

from scripts.utils.progress_resume import ResumeState, iter_progress


LEGACY_EXCEL_URLS = [
    "https://cea.nic.in/reports/others/demand/rna/energy_date-wise.xlsx",
]
CEA_POWER_PAGE = "https://cea.nic.in/power-supply/?lang=en"
NPP_PUBLISHED_REPORTS_URL = "https://npp.gov.in/publishedReports"
NPP_DGR17_URL_TMPL = "https://npp.gov.in/public-reports/cea/daily/dgr/{ddmmyyyy}/dgr17-{yyyy}-{mm}-{dd}.xls"
PDF_BASE = "https://cea.nic.in/wp-content/uploads/power_supply/"
_XLRD_MISSING_WARNED = False

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/javascript, */*",
}


def _to_float(value: object) -> float | None:
    s = str(value or "").strip()
    if not s:
        return None
    s = s.replace(",", "").replace("%", "").strip()
    if s in {"-", "NA", "N/A", "nan", "None"}:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _get_with_backoff(
    session: requests.Session,
    url: str,
    *,
    request_timeout: int,
    max_retries: int,
    verify: bool,
) -> requests.Response | None:
    backoff = 1.0
    for _ in range(max(1, int(max_retries))):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", category=Warning)
                r = session.get(url, timeout=int(request_timeout), verify=bool(verify))
            if r.status_code in {403, 429}:
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 20.0)
                continue
            return r
        except Exception:
            time.sleep(backoff)
            backoff = min(backoff * 2.0, 20.0)
    return None


def _discover_excel_urls(session: requests.Session, request_timeout: int, max_retries: int) -> list[str]:
    urls: list[str] = []
    for page in [CEA_POWER_PAGE]:
        r = _get_with_backoff(
            session,
            page,
            request_timeout=request_timeout,
            max_retries=max_retries,
            verify=False,
        )
        if r is None or r.status_code != 200:
            continue
        found = re.findall(r'href=["\']([^"\']+\.(?:xlsx|xls))["\']', r.text, flags=re.IGNORECASE)
        for link in found:
            if link.startswith("http"):
                urls.append(link)
            else:
                base = page.rsplit("/", 1)[0]
                urls.append(f"{base}/{link.lstrip('/')}")
    # Keep legacy URL first, then discovered unique URLs.
    out: list[str] = []
    for u in LEGACY_EXCEL_URLS + urls:
        if u not in out:
            out.append(u)
    return out


def _fetch_excel(session: requests.Session, request_timeout: int, max_retries: int) -> pd.DataFrame:
    for url in _discover_excel_urls(session, request_timeout, max_retries):
        r = _get_with_backoff(
            session,
            url,
            request_timeout=request_timeout,
            max_retries=max_retries,
            verify=False,
        )
        if r is None or r.status_code != 200 or len(r.content) < 1024:
            continue
        content_type = str(r.headers.get("content-type", "")).lower()
        if "text/html" in content_type:
            continue
        try:
            return pd.read_excel(io.BytesIO(r.content))
        except Exception:
            continue
    return pd.DataFrame()


def _norm_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().lower().replace(" ", "_") for c in out.columns]
    return out


def _parse_excel(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    d = _norm_columns(df)

    date_col = next((c for c in d.columns if "date" in c), None)
    met_col = next((c for c in d.columns if "energy" in c and ("met" in c or "actual" in c)), None)
    req_col = next((c for c in d.columns if "requirement" in c or "scheduled" in c), None)
    peak_col = next((c for c in d.columns if "peak" in c and ("met" in c or "demand" in c)), None)
    region_col = next((c for c in d.columns if "region" in c), None)

    if date_col is None:
        return pd.DataFrame()

    out = pd.DataFrame()
    out["date"] = pd.to_datetime(d[date_col], errors="coerce")
    out["region"] = d[region_col].astype(str) if region_col else "All India"
    out["energy_met_mu"] = pd.to_numeric(d[met_col], errors="coerce") if met_col else pd.NA
    out["peak_met_gw"] = pd.to_numeric(d[peak_col], errors="coerce") if peak_col else pd.NA
    out["energy_requirement_mu"] = pd.to_numeric(d[req_col], errors="coerce") if req_col else pd.NA

    out = out.dropna(subset=["date"]).copy()
    out["deficit_pct"] = (
        (pd.to_numeric(out["energy_requirement_mu"], errors="coerce") - pd.to_numeric(out["energy_met_mu"], errors="coerce"))
        / pd.to_numeric(out["energy_requirement_mu"], errors="coerce").replace(0.0, pd.NA)
    ) * 100.0
    # PIT safety: CEA daily publication assumed available next day.
    out["availability_date"] = pd.to_datetime(out["date"], errors="coerce") + pd.Timedelta(days=1)
    return out


def _pdf_fallback(session: requests.Session, raw_dir: Path, year: int, month: int) -> None:
    # Scaffold fallback downloader for unstable portals.
    folder_url = f"{PDF_BASE}{year}/{month:02d}/"
    try:
        html = session.get(folder_url, timeout=30).text
    except Exception:
        return
    links = re.findall(r'href=["\']([^"\']+\.pdf)["\']', html, flags=re.IGNORECASE)
    if not links:
        return
    month_dir = raw_dir / "pdfs" / f"{year}_{month:02d}"
    month_dir.mkdir(parents=True, exist_ok=True)
    for link in links:
        url = link if link.startswith("http") else f"{folder_url}{link.lstrip('/')}"
        name = url.split("/")[-1]
        out_file = month_dir / name
        if out_file.exists():
            continue
        try:
            r = session.get(url, timeout=60, verify=False)
            if r.ok:
                out_file.write_bytes(r.content)
        except Exception:
            continue


def _parse_dgr17_blob(blob: bytes, for_date: pd.Timestamp) -> dict | None:
    """
    Parse NPP DGR-17 xls (Category-wise fuel generation) and extract all-India totals.

    Expected row pattern includes "Total" with numeric sequence:
      [monitored_capacity_mw, today_program_mu, today_actual_mu, ...]
    """
    if not blob:
        return None
    global _XLRD_MISSING_WARNED
    try:
        df = pd.read_excel(io.BytesIO(blob), engine="xlrd", header=None)
    except ImportError:
        if not _XLRD_MISSING_WARNED:
            print(
                "[cea-power] xlrd_missing: install xlrd>=2.0.1 to parse NPP .xls daily files "
                "(pip install 'xlrd>=2.0.1')."
            )
            _XLRD_MISSING_WARNED = True
        return None
    except Exception:
        return None
    if df.empty:
        return None

    text_col = None
    for c in [1, 0, 2, 3]:
        if c in df.columns:
            text_col = c
            break
    if text_col is None:
        return None

    candidates = []
    for _, row in df.iterrows():
        label = str(row.get(text_col, "") or "").strip().lower()
        if label != "total":
            continue
        nums: list[float] = []
        for c in df.columns:
            if c == text_col:
                continue
            v = _to_float(row.get(c))
            if v is not None:
                nums.append(float(v))
        if len(nums) >= 2:
            candidates.append(nums)
    if not candidates:
        return None

    nums = max(candidates, key=len)
    # Heuristic: first value is often monitored capacity MW (very large),
    # followed by today's program MU and today's actual MU.
    if len(nums) >= 3 and nums[0] > 50000 and nums[1] < 30000 and nums[2] < 30000:
        nums = nums[1:]
    if len(nums) < 2:
        return None

    energy_requirement_mu = float(nums[0])
    energy_met_mu = float(nums[1])
    peak_met_gw = float(nums[2]) / 24.0 if len(nums) >= 3 else None
    deficit_pct = (
        ((energy_requirement_mu - energy_met_mu) / energy_requirement_mu) * 100.0
        if energy_requirement_mu
        else None
    )

    return {
        "date": pd.Timestamp(for_date).normalize(),
        "region": "All India",
        "energy_met_mu": energy_met_mu,
        "peak_met_gw": peak_met_gw,
        "energy_requirement_mu": energy_requirement_mu,
        "deficit_pct": deficit_pct,
        "availability_date": pd.Timestamp(for_date).normalize() + pd.Timedelta(days=1),
        "source": "npp_dgr17",
    }


def _fetch_npp_dgr17_day(
    session: requests.Session,
    day: pd.Timestamp,
    *,
    request_timeout: int,
    max_retries: int,
) -> dict | None:
    ddmmyyyy = day.strftime("%d-%m-%Y")
    yyyy = day.strftime("%Y")
    mm = day.strftime("%m")
    dd = day.strftime("%d")
    url = NPP_DGR17_URL_TMPL.format(ddmmyyyy=ddmmyyyy, yyyy=yyyy, mm=mm, dd=dd)

    r = _get_with_backoff(
        session,
        url,
        request_timeout=request_timeout,
        max_retries=max_retries,
        verify=True,
    )
    if r is None:
        return None
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        return None
    content_type = str(r.headers.get("content-type", "")).lower()
    if "text/html" in content_type:
        return None
    return _parse_dgr17_blob(r.content, day)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scrape CEA daily power data.")
    p.add_argument("--start-year", type=int, default=2019)
    p.add_argument("--end-year", type=int, default=pd.Timestamp.today().year)
    p.add_argument("--resume", action="store_true", default=True)
    p.add_argument("--no-resume", action="store_false", dest="resume")
    p.add_argument("--delay-min", type=float, default=2.0)
    p.add_argument("--delay-max", type=float, default=5.0)
    p.add_argument("--request-timeout", type=int, default=35)
    p.add_argument("--max-retries", type=int, default=4)
    p.add_argument("--log-every", type=int, default=200)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    raw_dir = Path("data/raw/macro/cea_power")
    raw_dir.mkdir(parents=True, exist_ok=True)
    state = ResumeState(raw_dir / ".resume_state.json")

    session = requests.Session()
    session.headers.update(HEADERS)

    legacy_df = _parse_excel(_fetch_excel(session, int(args.request_timeout), int(args.max_retries)))
    if not legacy_df.empty:
        legacy_df["source"] = "cea_excel"

    # Fallback hooks (downloads only; parsing optional for later extension).
    pdf_tasks = []
    for y in range(args.start_year, args.end_year + 1):
        for m in range(1, 13):
            if date(y, m, 1) > pd.Timestamp.today().date():
                break
            pdf_tasks.append((y, m))
    for y, m in iter_progress(pdf_tasks, desc="cea_pdf_scan", unit="month"):
        key = f"pdf-{y}-{m:02d}"
        if args.resume and state.has(key):
            continue
        _pdf_fallback(session, raw_dir, y, m)
        state.mark(key)
        time.sleep(random.uniform(args.delay_min, args.delay_max) / 10.0)

    # NPP DGR17 daily fallback (reliable and structured; available from 2019+).
    start_dt = pd.Timestamp(year=int(args.start_year), month=1, day=1)
    end_dt = pd.Timestamp(year=int(args.end_year), month=12, day=31).normalize()
    today = pd.Timestamp.today().normalize()
    if end_dt > today:
        end_dt = today
    daily_tasks = pd.date_range(start_dt, end_dt, freq="D")

    npp_rows: list[dict] = []
    processed_daily = 0
    found_daily = 0
    for d in iter_progress(daily_tasks, desc="cea_npp_dgr17", unit="day"):
        key = f"dgr17-{pd.Timestamp(d).strftime('%Y-%m-%d')}"
        if args.resume and state.has(key):
            processed_daily += 1
            continue
        row = _fetch_npp_dgr17_day(
            session,
            pd.Timestamp(d),
            request_timeout=int(args.request_timeout),
            max_retries=int(args.max_retries),
        )
        if row is not None:
            npp_rows.append(row)
            found_daily += 1
        state.mark(key)
        processed_daily += 1
        if int(args.log_every) > 0 and (processed_daily % int(args.log_every) == 0):
            print(
                f"[cea-power][npp] processed_days={processed_daily}/{len(daily_tasks)} "
                f"rows_found={found_daily} latest={pd.Timestamp(d).date()}"
            )
        time.sleep(random.uniform(args.delay_min, args.delay_max) / 25.0)

    npp_df = pd.DataFrame(npp_rows) if npp_rows else pd.DataFrame()

    # Rehydrate existing monthly raw partitions so resume runs are additive.
    existing_parts: list[pd.DataFrame] = []
    for old in sorted(raw_dir.glob("power_*.csv")):
        try:
            x = pd.read_csv(old)
        except Exception:
            continue
        if not x.empty:
            existing_parts.append(x)

    frames = []
    if existing_parts:
        frames.append(pd.concat(existing_parts, ignore_index=True))
    if not legacy_df.empty:
        frames.append(legacy_df)
    if not npp_df.empty:
        frames.append(npp_df)

    if frames:
        all_df = pd.concat(frames, ignore_index=True)
    else:
        all_df = pd.DataFrame(
            columns=[
                "date",
                "region",
                "energy_met_mu",
                "peak_met_gw",
                "energy_requirement_mu",
                "deficit_pct",
                "availability_date",
                "source",
            ]
        )

    all_df["date"] = pd.to_datetime(all_df.get("date"), errors="coerce").dt.normalize()
    all_df["availability_date"] = pd.to_datetime(all_df.get("availability_date"), errors="coerce")
    miss = all_df["availability_date"].isna()
    all_df.loc[miss, "availability_date"] = all_df.loc[miss, "date"] + pd.Timedelta(days=1)
    all_df = all_df.dropna(subset=["date"]).copy()
    # Keep previously ingested history intact on incremental runs.
    all_df = all_df[(all_df["date"].dt.year <= int(args.end_year))].copy()
    if "source" not in all_df.columns:
        all_df["source"] = "unknown"
    all_df = all_df.sort_values(["date", "source"], kind="mergesort")
    all_df = all_df.drop_duplicates(subset=["date", "region"], keep="last").reset_index(drop=True)

    # Write monthly raw CSV partitions.
    if not all_df.empty:
        all_df["_ym"] = all_df["date"].dt.strftime("%Y_%m")
        month_groups = list(all_df.groupby("_ym", sort=True))
        for ym, grp in iter_progress(month_groups, desc="cea_monthly_write", unit="file"):
            key = f"csv-{ym}"
            out_csv = raw_dir / f"power_{ym}.csv"
            # Always rewrite monthly partitions from the deduplicated canonical frame.
            grp.drop(columns=["_ym"], errors="ignore").to_csv(out_csv, index=False)
            state.mark(key)

    proc = Path("data/processed/macro/cea_power_daily.parquet")
    proc.parent.mkdir(parents=True, exist_ok=True)
    all_df = all_df.drop(columns=["_ym"], errors="ignore")
    if all_df.empty and proc.exists():
        try:
            prev = pd.read_parquet(proc)
        except Exception:
            prev = pd.DataFrame()
        if not prev.empty:
            print(
                f"[cea-power] warning: fetched 0 rows; preserving existing processed dataset ({len(prev)} rows)"
            )
            all_df = prev.copy()
    all_df.to_parquet(proc, index=False)

    if not all_df.empty:
        src_counts = (
            all_df.get("source", pd.Series(dtype=str))
            .astype(str)
            .value_counts(dropna=False)
            .to_dict()
        )
        print(
            f"[cea-power] date_range={all_df['date'].min().date()} to {all_df['date'].max().date()} "
            f"sources={src_counts}"
        )
    print(
        f"[cea-power] completed: {len(list(raw_dir.glob('power_*.csv')))} files, {len(all_df)} rows"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
