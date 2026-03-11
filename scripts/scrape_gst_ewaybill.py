#!/usr/bin/env python3
"""Scrape GST e-way bill stats with GSTN dashboard API + portal fallback."""

from __future__ import annotations

import argparse
import os
import random
import re
import time
from io import StringIO
from datetime import date
from pathlib import Path

import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

from scripts.utils.progress_resume import ResumeState, iter_progress


API_URL = "https://ewaybillgst.gov.in/BillGenStats/GetBillGenStats"
GSTN_EWAY_DASHBOARD_URL = "https://www.gstn.org.in/gstnadmin/hr/ewayBillApi.json"
PORTAL_URLS = [
    "https://ewaybillgst.gov.in/Others/EWBMonthStats.aspx",
    "https://ewaybillgst.gov.in/Others/GSTEwayBillStatsStateWise.aspx",
]
PDF_INDEX_URL = "https://ewaybillgst.gov.in/Others/EwbGstStats.aspx"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/javascript, */*",
    "Referer": "https://ewaybillgst.gov.in/",
    "X-Requested-With": "XMLHttpRequest",
}


def _month_iter(start_year: int, end_year: int):
    today = pd.Timestamp.today().normalize().date()
    for y in range(start_year, end_year + 1):
        for m in range(1, 13):
            d = date(y, m, 1)
            if d > today:
                return
            yield d


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    for u in PORTAL_URLS:
        try:
            s.get(u, timeout=30)
        except Exception:
            continue
    return s


def _parse_month_label(label: object) -> pd.Timestamp:
    dt = pd.to_datetime(str(label or "").strip(), format="%b %Y", errors="coerce")
    if pd.isna(dt):
        return pd.NaT
    return pd.Timestamp(dt) + pd.offsets.MonthEnd(0)


def _fetch_gstn_dashboard_series(session: requests.Session) -> pd.DataFrame:
    """
    GSTN dashboard endpoint:
    https://www.gstn.org.in/gstnadmin/hr/ewayBillApi.json

    Provides monthly e-way bill series (Intra / Inter / Total).
    """
    try:
        r = session.get(GSTN_EWAY_DASHBOARD_URL, timeout=45)
        r.raise_for_status()
        payload = r.json()
    except Exception:
        return pd.DataFrame()

    if not isinstance(payload, dict):
        return pd.DataFrame()
    q = payload.get("query", {}) if isinstance(payload.get("query"), dict) else {}
    labels = list(q.get("labels", []) or [])
    datasets = list(q.get("datasets", []) or [])
    if not labels or not datasets:
        return pd.DataFrame()

    month_dates = [_parse_month_label(x) for x in labels]
    rows: list[dict] = []
    for ds in datasets:
        if not isinstance(ds, dict):
            continue
        series_label = str(ds.get("label") or "").strip() or "Total"
        values = list(ds.get("data", []) or [])
        for i, dt in enumerate(month_dates):
            if pd.isna(dt):
                continue
            val = values[i] if i < len(values) else None
            rows.append(
                {
                    "year_month": pd.Timestamp(dt).strftime("%Y-%m"),
                    "state": "All India",
                    "category": series_label,
                    "eway_bills_generated": pd.to_numeric(val, errors="coerce"),
                    "eway_bill_value_crore": pd.NA,
                    "date": pd.Timestamp(dt).normalize(),
                    # PIT safety: conservative +30 days lag.
                    "availability_date": pd.Timestamp(dt).normalize() + pd.Timedelta(days=30),
                    "source": "gstn_dashboard",
                }
            )

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["date", "category"], kind="mergesort").reset_index(drop=True)


def _post_json(session: requests.Session, payload: dict, retries: int = 2):
    backoff = 1.0
    for _ in range(retries):
        try:
            r = session.post(API_URL, json=payload, timeout=60)
            if r.status_code in {403, 429}:
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
                continue
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                for k in ["data", "Data", "Table", "rows", "result"]:
                    if isinstance(data.get(k), list):
                        return data[k]
            return []
        except Exception:
            time.sleep(backoff)
            backoff = min(backoff * 2.0, 60.0)
    return []


def _parse_api_rows(rows: list[dict], ym: str) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    state_col = next((c for c in ["state", "State", "STATE"] if c in df.columns), None)
    sector_col = next((c for c in ["sector", "category", "Commodity", "Category"] if c in df.columns), None)
    bills_col = next((c for c in ["eway_bills_generated", "BillCount", "EwayBill", "Count"] if c in df.columns), None)
    value_col = next((c for c in ["eway_bill_value_crore", "BillValue", "Value"] if c in df.columns), None)

    out = pd.DataFrame()
    out["year_month"] = ym
    out["state"] = df[state_col].astype(str) if state_col else ""
    out["category"] = df[sector_col].astype(str) if sector_col else ""
    out["eway_bills_generated"] = pd.to_numeric(df[bills_col], errors="coerce") if bills_col else pd.NA
    out["eway_bill_value_crore"] = pd.to_numeric(df[value_col], errors="coerce") if value_col else pd.NA
    out["date"] = pd.to_datetime(out["year_month"] + "-01", errors="coerce") + pd.offsets.MonthEnd(0)
    # PIT safety: conservative +30 days lag.
    out["availability_date"] = pd.to_datetime(out["date"], errors="coerce") + pd.Timedelta(days=30)
    out["source"] = "eway_portal_api"
    return out


def _selenium_fallback(ym: str) -> pd.DataFrame:
    """
    Optional JS fallback for unstable GST portal responses.

    This method is best-effort and returns empty output if Selenium is unavailable
    or the page structure changes.
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except Exception:
        return pd.DataFrame()

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    try:
        driver = webdriver.Chrome(options=options)
    except Exception:
        return pd.DataFrame()

    try:
        driver.get(PORTAL_URLS[0])
        time.sleep(4.0)
        tables = pd.read_html(StringIO(driver.page_source))
    except Exception:
        tables = []
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    if not tables:
        return pd.DataFrame()

    cand = tables[0].copy()
    cand.columns = [str(c).strip().lower().replace(" ", "_") for c in cand.columns]
    rows = cand.to_dict("records")
    out = _parse_api_rows(rows, ym=ym)
    if not out.empty:
        out["source"] = "eway_portal_selenium"
    return out


def _pdf_fallback(session: requests.Session, ym: str, pdf_dir: Path) -> pd.DataFrame:
    try:
        idx = session.get(PDF_INDEX_URL, timeout=45).text
    except Exception:
        return pd.DataFrame()

    links = re.findall(r'href=["\']([^"\']+\.pdf)["\']', idx, flags=re.IGNORECASE)
    if not links:
        return pd.DataFrame()

    # Fallback scaffold only; row extraction can be extended later.
    for link in links[:10]:
        url = link if link.startswith("http") else f"https://ewaybillgst.gov.in/{link.lstrip('/')}"
        name = url.split("/")[-1]
        out_pdf = pdf_dir / name
        if out_pdf.exists():
            continue
        try:
            r = session.get(url, timeout=60)
            if r.ok:
                out_pdf.write_bytes(r.content)
        except Exception:
            continue

    return pd.DataFrame()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scrape GST e-way bill monthly stats.")
    p.add_argument("--start-year", type=int, default=2018)
    p.add_argument("--end-year", type=int, default=pd.Timestamp.today().year)
    p.add_argument("--resume", action="store_true", default=True)
    p.add_argument("--no-resume", action="store_false", dest="resume")
    p.add_argument("--delay-min", type=float, default=3.0)
    p.add_argument("--delay-max", type=float, default=6.0)
    p.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Max retries for legacy GST portal API requests per month.",
    )
    p.add_argument(
        "--log-every",
        type=int,
        default=24,
        help="Progress heartbeat in months.",
    )
    p.add_argument(
        "--selenium-fallback",
        action="store_true",
        default=False,
        help="Enable Selenium HTML-table fallback (slow; only use when explicitly needed).",
    )
    p.add_argument(
        "--pdf-fallback",
        action="store_true",
        default=False,
        help="Enable PDF download fallback (downloads files but does not extract tabular rows yet).",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    raw_dir = Path("data/raw/macro/gst_ewaybill")
    pdf_dir = raw_dir / "pdfs"
    raw_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    state = ResumeState(raw_dir / ".resume_state.json")

    session = _session()

    dashboard = _fetch_gstn_dashboard_series(session)
    dashboard_by_ym: dict[str, pd.DataFrame] = {}
    if not dashboard.empty:
        for ym, grp in dashboard.groupby("year_month", sort=False):
            dashboard_by_ym[str(ym)] = grp.copy()
    print(
        f"[gst-ewaybill] dashboard_rows={len(dashboard)} "
        f"dashboard_months={len(dashboard_by_ym)}"
    )

    frames: list[pd.DataFrame] = []
    tasks = list(_month_iter(args.start_year, args.end_year))
    processed = 0
    for d in iter_progress(tasks, desc="gst_ewaybill", unit="month"):
        ym = f"{d.year}-{d.month:02d}"
        key = ym
        out_csv = raw_dir / f"ewaybill_{d.year}_{d.month:02d}.csv"
        if args.resume and (out_csv.exists() or state.has(key)):
            try:
                if out_csv.exists():
                    frames.append(pd.read_csv(out_csv))
                state.mark(key)
            except Exception:
                pass
            continue

        # Primary source: GSTN dashboard monthly time series.
        df = dashboard_by_ym.get(ym, pd.DataFrame()).copy()

        # Legacy/fallback sources only when primary has no row for month.
        if df.empty:
            payload = {"month": int(d.month), "year": int(d.year)}
            rows = _post_json(session, payload, retries=max(1, int(args.max_retries)))
            df = _parse_api_rows(rows, ym=ym)
        if df.empty and bool(args.selenium_fallback):
            df = _selenium_fallback(ym=ym)
        if df.empty and bool(args.pdf_fallback):
            df = _pdf_fallback(session, ym=ym, pdf_dir=pdf_dir)
        if df.empty:
            df = pd.DataFrame(
                columns=[
                    "year_month",
                    "state",
                    "category",
                    "eway_bills_generated",
                    "eway_bill_value_crore",
                    "date",
                    "availability_date",
                    "source",
                ]
            )

        if "source" not in df.columns:
            df["source"] = "unknown"
        df.to_csv(out_csv, index=False)
        state.mark(key)
        frames.append(df)
        processed += 1
        if int(args.log_every) > 0 and (processed % int(args.log_every) == 0):
            src = df["source"].astype(str).iloc[0] if not df.empty else "none"
            print(
                f"[gst-ewaybill] processed={processed}/{len(tasks)} "
                f"latest={ym} rows={len(df)} source={src}"
            )
        time.sleep(random.uniform(args.delay_min, args.delay_max))

    non_empty_frames = [f for f in frames if isinstance(f, pd.DataFrame) and not f.empty]
    all_df = pd.concat(non_empty_frames, ignore_index=True) if non_empty_frames else pd.DataFrame()
    proc = Path("data/processed/macro/gst_ewaybill_monthly.parquet")
    proc.parent.mkdir(parents=True, exist_ok=True)
    if not all_df.empty:
        all_df["date"] = pd.to_datetime(all_df["date"], errors="coerce")
        all_df = all_df.sort_values(["date", "state", "category"], kind="mergesort")
        all_df = all_df.drop_duplicates(subset=["date", "state", "category"], keep="last")
    elif proc.exists():
        try:
            prev = pd.read_parquet(proc)
        except Exception:
            prev = pd.DataFrame()
        if not prev.empty:
            print(
                f"[gst-ewaybill] warning: fetched 0 rows; preserving existing processed dataset ({len(prev)} rows)"
            )
            all_df = prev.copy()
    all_df.to_parquet(proc, index=False)

    sectors = (
        sorted([x for x in all_df.get("category", pd.Series(dtype=str)).dropna().astype(str).unique() if x])
        if not all_df.empty
        else []
    )
    states = (
        sorted([x for x in all_df.get("state", pd.Series(dtype=str)).dropna().astype(str).unique() if x])
        if not all_df.empty
        else []
    )
    src_counts = all_df.get("source", pd.Series(dtype=str)).astype(str).value_counts().to_dict() if not all_df.empty else {}
    print(f"[gst-ewaybill] months scraped: {len(list(raw_dir.glob('ewaybill_*.csv')))}")
    if not all_df.empty and "year_month" in all_df.columns:
        print(f"[gst-ewaybill] date range: {all_df['year_month'].min()} to {all_df['year_month'].max()}")
    else:
        print("[gst-ewaybill] date range: NA to NA")
    print(f"[gst-ewaybill] sectors found: {sectors[:30]}")
    print(f"[gst-ewaybill] states found: {states[:30]}")
    print(f"[gst-ewaybill] source_counts: {src_counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
