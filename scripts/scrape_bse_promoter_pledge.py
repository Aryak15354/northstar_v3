#!/usr/bin/env python3
"""Scrape promoter pledge data from BSE consolidated pledge endpoint."""

from __future__ import annotations

import argparse
import json
import random
import time
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

try:
    from scripts.utils.progress_resume import ResumeState, iter_progress
except ModuleNotFoundError:  # direct script execution: python3 scripts/...
    from utils.progress_resume import ResumeState, iter_progress


API_URL = "https://api.bseindia.com/BseIndiaAPI/api/ConsolidatePledge/w?scripcode={}"
CSV_URL = "https://api.bseindia.com/BseIndiaAPI/api/DwnldExcel_ConPldge/w?scripcode={}&flag=ConPldge"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/javascript, */*",
    "Referer": "https://www.bseindia.com/",
    "X-Requested-With": "XMLHttpRequest",
}


def _normalize_ticker(value: object) -> str:
    s = str(value or "").strip().upper()
    if not s:
        return ""
    if s.endswith(".NS"):
        return s
    if "." in s:
        s = s.split(".", 1)[0]
    return f"{s}.NS"


def _load_universe() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    meta_dir = Path("data/raw/screener/metadata")
    for p in sorted(meta_dir.glob("*_metadata.json")):
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        bse_code = str(d.get("bse_code") or "").strip()
        ticker = _normalize_ticker(d.get("ticker"))
        if bse_code and ticker:
            rows.append((bse_code, ticker))
    return rows


def _safe_get(session: requests.Session, url: str, retries: int = 6) -> tuple[requests.Response | None, bool]:
    backoff = 1.0
    blocked = False
    for _ in range(retries):
        try:
            r = session.get(url, timeout=45)
            if r.status_code in {403, 429}:
                blocked = True
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
                continue
            if r.status_code >= 500:
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
                continue
            if "access denied" in (r.text or "")[:300].lower():
                blocked = True
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
                continue
            return r, blocked
        except Exception:
            time.sleep(backoff)
            backoff = min(backoff * 2.0, 60.0)
    return None, blocked


def _safe_json(session: requests.Session, url: str) -> tuple[list[dict], bool]:
    r, blocked = _safe_get(session, url)
    if r is None:
        return [], blocked
    try:
        payload = r.json()
    except Exception:
        return [], blocked
    if isinstance(payload, list):
        return payload, blocked
    if isinstance(payload, dict):
        for k in ["Table", "Data", "data", "Table1"]:
            if isinstance(payload.get(k), list):
                return payload[k], blocked
    return [], blocked


def _parse_download_csv(session: requests.Session, bse_code: str) -> pd.DataFrame:
    # Fallback endpoint used on BSE quote page download button.
    r, _ = _safe_get(session, CSV_URL.format(bse_code), retries=4)
    if r is None or not r.text:
        return pd.DataFrame()

    txt = r.text
    if "Name of the Company" not in txt or "Promoter" not in txt:
        return pd.DataFrame()

    try:
        df = pd.read_csv(StringIO(txt))
    except Exception:
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    # This CSV is generally latest-quarter snapshot only.
    out = pd.DataFrame()
    out["date"] = pd.NaT
    out["shares_pledged"] = pd.to_numeric(
        df.filter(regex=r"No of Shares|No\. of Shares|No of share", axis=1).iloc[:, -1], errors="coerce"
    )
    total_col = next((c for c in df.columns if "Total Promoter Holding" in str(c)), None)
    out["total_promoter_shares"] = pd.to_numeric(df[total_col], errors="coerce") if total_col else pd.NA
    pct_col = next((c for c in df.columns if "% of promoter" in str(c) or "Encumbered" in str(c)), None)
    out["pledge_pct"] = pd.to_numeric(df[pct_col], errors="coerce") if pct_col else pd.NA
    return out


def _to_frame(records: list[dict], bse_code: str, ticker: str) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=["date", "bse_code", "nse_ticker", "shares_pledged", "total_promoter_shares", "pledge_pct"])

    df = pd.DataFrame(records)
    out = pd.DataFrame()

    date_col = next((c for c in ["new_EndDate", "dDateEnd", "Fld_EndDate", "date", "Date"] if c in df.columns), None)
    if date_col == "Fld_EndDate":
        out["date"] = pd.to_datetime(df[date_col].astype(str), format="%Y%m%d", errors="coerce")
    else:
        out["date"] = pd.to_datetime(df[date_col], errors="coerce") if date_col else pd.NaT

    out["bse_code"] = str(bse_code)
    out["nse_ticker"] = ticker

    shares_col = next((c for c in ["Noofsharespledged", "PROMOTEREncum_NoOfshares", "shares_pledged"] if c in df.columns), None)
    total_col = next((c for c in ["NoofShares_TOTAL_PROMOTER_HOLDING", "TotalNoofShares", "total_promoter_shares"] if c in df.columns), None)
    pct_col = next(
        (c for c in ["PROMOTEREncum_Percof_PromoterShares", "F_NewCol", "pledge_pct", "PROMOTEREncum_Percof_TotalShares"] if c in df.columns),
        None,
    )

    out["shares_pledged"] = pd.to_numeric(df[shares_col], errors="coerce") if shares_col else pd.NA
    out["total_promoter_shares"] = pd.to_numeric(df[total_col], errors="coerce") if total_col else pd.NA
    out["pledge_pct"] = pd.to_numeric(df[pct_col], errors="coerce") if pct_col else pd.NA

    mask = out["pledge_pct"].isna() & out["shares_pledged"].notna() & out["total_promoter_shares"].notna()
    out.loc[mask, "pledge_pct"] = (
        100.0 * out.loc[mask, "shares_pledged"] / out.loc[mask, "total_promoter_shares"].replace(0.0, pd.NA)
    )

    return out[["date", "bse_code", "nse_ticker", "shares_pledged", "total_promoter_shares", "pledge_pct"]]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scrape BSE promoter pledge history.")
    p.add_argument("--resume", action="store_true", default=True)
    p.add_argument("--no-resume", action="store_false", dest="resume")
    p.add_argument("--delay-min", type=float, default=2.0)
    p.add_argument("--delay-max", type=float, default=4.0)
    p.add_argument("--max-companies", type=int, default=0, help="Probe mode: cap number of companies (0 = all).")
    p.add_argument("--log-every", type=int, default=1, help="Print ingestion status every N processed companies.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path("data/raw/alternative/promoter_pledge")
    out_dir.mkdir(parents=True, exist_ok=True)
    state = ResumeState(out_dir / ".resume_state.json")

    universe = _load_universe()
    if int(args.max_companies) > 0:
        universe = universe[: int(args.max_companies)]

    session = requests.Session()
    session.headers.update(HEADERS)

    frames: list[pd.DataFrame] = []
    blocked = 0
    reused = 0
    processed = 0
    cumulative_rows = 0
    fallback_used = 0
    for bse_code, ticker in iter_progress(universe, desc="promoter_pledge", unit="company"):
        key = str(bse_code)
        out_file = out_dir / f"{bse_code}_pledge.csv"

        if args.resume and out_file.exists():
            try:
                old = pd.read_csv(out_file, parse_dates=["date"])
                if state.has(key) or len(old) > 0:
                    frames.append(old)
                    state.mark(key)
                    reused += 1
                    processed += 1
                    cumulative_rows += int(len(old))
                    reused_status = "reused" if len(old) > 0 else "reused_empty"
                    if args.log_every > 0 and (processed % int(args.log_every) == 0):
                        print(
                            f"[pledge][{bse_code}] status={reused_status} rows={len(old)} "
                            f"cumulative_rows={cumulative_rows} processed={processed}/{len(universe)}"
                        )
                    continue
            except Exception:
                pass

        records, was_blocked = _safe_json(session, API_URL.format(bse_code))
        if was_blocked and not records:
            blocked += 1

        df = _to_frame(records, bse_code=bse_code, ticker=ticker)
        if df.empty:
            fb = _parse_download_csv(session, bse_code)
            if not fb.empty:
                fallback_used += 1
                fb["bse_code"] = str(bse_code)
                fb["nse_ticker"] = ticker
                df = fb[["date", "bse_code", "nse_ticker", "shares_pledged", "total_promoter_shares", "pledge_pct"]]

        df.to_csv(out_file, index=False)
        state.mark(key)
        frames.append(df)
        processed += 1
        rows = int(len(df))
        cumulative_rows += rows
        status = "ingested" if rows > 0 else "empty"
        if args.log_every > 0 and (processed % int(args.log_every) == 0):
            print(
                f"[pledge][{bse_code}] status={status} rows={rows} "
                f"cumulative_rows={cumulative_rows} processed={processed}/{len(universe)}"
            )
        time.sleep(random.uniform(args.delay_min, args.delay_max))

    all_df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    proc_path = Path("data/processed/alternative/promoter_pledge_all.csv")
    proc_path.parent.mkdir(parents=True, exist_ok=True)
    if not all_df.empty:
        all_df["date"] = pd.to_datetime(all_df["date"], errors="coerce")
        all_df = all_df.sort_values(["date", "nse_ticker"], kind="mergesort")
    all_df.to_csv(proc_path, index=False)

    if blocked > 0 and all_df.empty:
        print(f"[pledge] failed: blocked for {blocked} companies and no rows collected")
        return 2

    print(f"[pledge] completed: {len(universe)} companies, {int(len(all_df))} rows")
    print(
        f"[pledge] ingestion_summary: reused={reused}, blocked={blocked}, "
        f"fallback_used={fallback_used}, cumulative_rows={cumulative_rows}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
