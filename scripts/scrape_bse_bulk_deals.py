#!/usr/bin/env python3
"""Scrape BSE bulk deals month-by-month via the live Bulk/Block form flow."""

from __future__ import annotations

import argparse
import json
import random
import difflib
import time
import re
from datetime import date
from pathlib import Path
import sys

import pandas as pd
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.utils.progress_resume import ResumeState, iter_progress
except ModuleNotFoundError:  # direct script execution: python3 scripts/...
    from utils.progress_resume import ResumeState, iter_progress


FORM_URL = "https://www.bseindia.com/markets/equity/eqreports/bulknblockdeals.aspx"
CSV_HEADER = "Deal Date,Security Code,Company,Client Name,Deal Type,Quantity,Price"
MONTH_COLUMNS = ["date", "exchange", "scrip_code", "scrip_name", "client_name", "deal_type", "quantity", "price"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": FORM_URL,
}

BSE_MASTER_URL = "https://www.bseindia.com/corporates/List_Scrips.aspx"


def _normalize_ticker(value: object) -> str:
    s = str(value or "").strip().upper()
    if not s:
        return ""
    if s.endswith(".NS"):
        return s
    if "." in s:
        s = s.split(".", 1)[0]
    return f"{s}.NS"


def _request_with_backoff(
    session: requests.Session,
    method: str,
    url: str,
    *,
    data: dict[str, str] | None = None,
    retries: int = 6,
    timeout: int = 60,
) -> tuple[requests.Response | None, bool]:
    backoff = 1.0
    blocked = False
    for _ in range(retries):
        try:
            if method.upper() == "POST":
                resp = session.post(url, data=data, timeout=timeout)
            else:
                resp = session.get(url, timeout=timeout)
            if resp.status_code in {403, 429}:
                blocked = True
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
                continue
            if resp.status_code >= 500:
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
                continue
            head = (resp.text or "")[:500].lower()
            if "error_bse" in head or "access denied" in head:
                blocked = True
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
                continue
            if resp.status_code >= 400:
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
                continue
            return resp, blocked
        except Exception:
            time.sleep(backoff)
            backoff = min(backoff * 2.0, 60.0)
    return None, blocked


def _month_range(start_year: int, end_year: int):
    today = date.today()
    for y in range(start_year, end_year + 1):
        for m in range(1, 13):
            start = date(y, m, 1)
            if start > today:
                return
            if m == 12:
                end = date(y + 1, 1, 1) - pd.Timedelta(days=1)
            else:
                end = date(y, m + 1, 1) - pd.Timedelta(days=1)
            if end > today:
                end = today
            yield start, end


def _load_bse_master() -> tuple[dict[str, str], dict[str, str]]:
    """
    Returns (code_map, name_map) from BSE master. code_map: scrip_code -> NSE ticker.
    name_map: normalized security name -> NSE ticker.
    """
    path = Path("data/raw/bse_equity_master.csv")
    code_map: dict[str, str] = {}
    name_map: dict[str, str] = {}

    def _normalize_name(s: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", s.upper())

    def _ingest(df: pd.DataFrame) -> None:
        code_col = None
        for cand in ["Scrip Code", "Security Code", "scrip_code", "security_code"]:
            if cand in df.columns:
                code_col = cand
                break
        nse_col = None
        for cand in ["Nse Symbol", "NSE Symbol", "nse_symbol", "nse_ticker", "NSE Ticker"]:
            if cand in df.columns:
                nse_col = cand
                break
        name_col = None
        for cand in ["Security Name", "security_name", "Company Name", "company_name", "Security Id"]:
            if cand in df.columns:
                name_col = cand
                break
        if not code_col or not nse_col:
            return
        df = df[[code_col, nse_col] + ([name_col] if name_col else [])].copy()
        df[code_col] = df[code_col].astype(str).str.strip()
        df[nse_col] = df[nse_col].astype(str).str.strip()
        if name_col:
            df[name_col] = df[name_col].astype(str).str.strip()
        for _, r in df.iterrows():
            code = r.get(code_col)
            sym = _normalize_ticker(r.get(nse_col))
            if code and sym:
                code_map[code] = sym
            if name_col:
                nm = _normalize_name(r.get(name_col, ""))
                if nm and sym:
                    name_map[nm] = sym

    if path.exists():
        try:
            df = pd.read_csv(path)
            _ingest(df)
            return code_map, name_map
        except Exception:
            pass

    try:
        resp = requests.get(BSE_MASTER_URL, timeout=60)
        resp.raise_for_status()
        tables = pd.read_html(resp.text)
        if tables:
            df = max(tables, key=len)
            path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(path, index=False)
            _ingest(df)
    except Exception:
        pass

    return code_map, name_map


def _load_ticker_lookup() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    code_lookup: dict[str, str] = {}
    name_lookup: dict[str, str] = {}

    bse_code_map, bse_name_map = _load_bse_master()
    code_lookup.update(bse_code_map)
    name_lookup.update(bse_name_map)

    meta_dir = Path("data/raw/screener/metadata")
    if meta_dir.exists():
        for p in meta_dir.glob("*_metadata.json"):
            try:
                d = json.loads(p.read_text())
            except Exception:
                continue
            code = str(d.get("bse_code") or "").strip()
            tk = _normalize_ticker(d.get("ticker"))
            nm = str(d.get("name") or "").strip()
            if code and tk:
                code_lookup.setdefault(code, tk)
            if nm and tk:
                name_lookup.setdefault(re.sub(r"[^A-Z0-9]", "", nm.upper()), tk)

    # Screener fundamentals annual sometimes includes names; use if present.
    for meta_path in [
        Path("data/processed/screener_metadata.csv"),
        Path("data/processed/screener_delisted/screener_metadata.csv"),
    ]:
        if meta_path.exists():
            try:
                df = pd.read_csv(meta_path, usecols=["ticker", "company_name", "bse_code"])
                for _, r in df.iterrows():
                    tk = _normalize_ticker(r.get("ticker"))
                    nm = re.sub(r"[^A-Z0-9]", "", str(r.get("company_name") or "").upper())
                    bc = str(r.get("bse_code") or "").strip()
                    if bc and tk:
                        code_lookup.setdefault(bc, tk)
                    if nm and tk:
                        name_lookup.setdefault(nm, tk)
            except Exception:
                pass

    et_map, nifty_map = _name_lookup()
    return code_lookup, name_lookup, {**et_map, **nifty_map}


def _name_lookup() -> tuple[dict[str, str], dict[str, str]]:
    et_map: dict[str, str] = {}
    nifty_map: dict[str, str] = {}

    et_path = Path("data/reference/et500_name_to_ticker.csv")
    if et_path.exists():
        try:
            et = pd.read_csv(et_path)
            for r in et.to_dict("records"):
                name = str(r.get("company_name") or "").strip().upper()
                tk = _normalize_ticker(r.get("nse_ticker"))
                if name and tk and tk != "UNMATCHED.NS":
                    et_map[name] = tk
        except Exception:
            pass

    nf_path = Path("universe/nifty500.csv")
    if nf_path.exists():
        try:
            nf = pd.read_csv(nf_path)
            for r in nf.to_dict("records"):
                name = str(r.get("Company Name") or "").strip().upper()
                sym = _normalize_ticker(r.get("Symbol"))
                if name and sym:
                    nifty_map[name] = sym
        except Exception:
            pass

    return et_map, nifty_map


def _map_ticker(
    row: pd.Series,
    code_map: dict[str, str],
    name_map: dict[str, str],
    et_nifty_map: dict[str, str],
) -> str:
    code = str(row.get("scrip_code") or "").strip()
    if code in code_map:
        return code_map[code]

    name_raw = str(row.get("scrip_name") or "").strip()
    name_norm = re.sub(r"[^A-Z0-9]", "", name_raw.upper())

    if name_norm in name_map:
        return name_map[name_norm]
    if name_norm in et_nifty_map:
        return et_nifty_map[name_norm]

    candidates = difflib.get_close_matches(name_norm, name_map.keys(), n=1, cutoff=0.82)
    if candidates:
        return name_map[candidates[0]]

    return ""


def _assign_tickers(df: pd.DataFrame, code_map: dict[str, str], name_map: dict[str, str], et_nifty_map: dict[str, str]) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    if "nse_ticker" not in df.columns:
        df["nse_ticker"] = ""
    cur = df["nse_ticker"].astype(str).str.upper()
    needs = cur.isna() | (cur == "") | (~cur.str.endswith(".NS"))

    # Exact code match first.
    if needs.any():
        codes = df.loc[needs, "scrip_code"].astype(str).str.strip()
        code_hits = codes.map(code_map).fillna("")
        df.loc[needs, "nse_ticker"] = code_hits.where(code_hits != "", df.loc[needs, "nse_ticker"])

    # Name-based match for remaining.
    cur = df["nse_ticker"].astype(str).str.upper()
    needs = cur.isna() | (cur == "") | (~cur.str.endswith(".NS"))
    if needs.any():
        names = df.loc[needs, "scrip_name"].astype(str).str.strip()
        names_norm = names.str.upper().str.replace(r"[^A-Z0-9]", "", regex=True)
        uniq = names_norm.unique()
        name_hits: dict[str, str] = {}
        for nm in uniq:
            if not nm:
                continue
            if nm in name_map:
                name_hits[nm] = name_map[nm]
            elif nm in et_nifty_map:
                name_hits[nm] = et_nifty_map[nm]
        df.loc[needs, "nse_ticker"] = names_norm.map(name_hits).fillna(df.loc[needs, "nse_ticker"])

    # Optional lightweight fuzzy for still-unmatched (cap to avoid O(N^2)).
    cur = df["nse_ticker"].astype(str).str.upper()
    needs = cur.isna() | (cur == "") | (~cur.str.endswith(".NS"))
    remaining = df.loc[needs]
    if len(remaining) and len(remaining) <= 5000:
        names_norm = remaining["scrip_name"].astype(str).str.upper().str.replace(r"[^A-Z0-9]", "", regex=True)
        name_keys = list(name_map.keys())
        for idx, nm in zip(remaining.index, names_norm):
            if not nm:
                continue
            match = difflib.get_close_matches(nm, name_keys, n=1, cutoff=0.86)
            if match:
                df.at[idx, "nse_ticker"] = name_map[match[0]]

    df["nse_ticker"] = df["nse_ticker"].astype(str).str.upper().apply(_normalize_ticker)
    return df


def _extract_tokens(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    out: dict[str, str] = {}
    for name in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__VIEWSTATEENCRYPTED", "__EVENTVALIDATION"]:
        node = soup.find("input", {"name": name})
        out[name] = str(node.get("value") or "") if node else ""
    return out


def _search_payload(tokens: dict[str, str], from_s: str, to_s: str) -> dict[str, str]:
    return {
        "__EVENTTARGET": "",
        "__EVENTARGUMENT": "",
        "__LASTFOCUS": "",
        "__VIEWSTATE": tokens.get("__VIEWSTATE", ""),
        "__VIEWSTATEGENERATOR": tokens.get("__VIEWSTATEGENERATOR", ""),
        "__VIEWSTATEENCRYPTED": tokens.get("__VIEWSTATEENCRYPTED", ""),
        "__EVENTVALIDATION": tokens.get("__EVENTVALIDATION", ""),
        "ctl00$ContentPlaceHolder1$rblDT": "1",  # bulk deals
        "ctl00$ContentPlaceHolder1$chkAllMarket": "on",
        "ctl00$ContentPlaceHolder1$txtDate": from_s,
        "ctl00$ContentPlaceHolder1$txtToDate": to_s,
        "ctl00$ContentPlaceHolder1$btnSubmit": "Submit",
        "ctl00$ContentPlaceHolder1$Hidden1": "",
        "ctl00$ContentPlaceHolder1$hf_scripcode": "",
        "ctl00$ContentPlaceHolder1$DDate": "",
        "ctl00$ContentPlaceHolder1$SmartSearch$smartSearch": "",
        "ctl00$ContentPlaceHolder1$SmartSearch$hdnCode": "",
    }


def _download_payload(tokens: dict[str, str], from_s: str, to_s: str) -> dict[str, str]:
    # Use the same fields the site posts for download; omitting btnSubmit is
    # important because setting it can suppress the CSV response.
    return {
        "__EVENTTARGET": "ctl00$ContentPlaceHolder1$btnDownload",
        "__EVENTARGUMENT": "",
        "__LASTFOCUS": "",
        "__VIEWSTATE": tokens.get("__VIEWSTATE", ""),
        "__VIEWSTATEGENERATOR": tokens.get("__VIEWSTATEGENERATOR", ""),
        "__VIEWSTATEENCRYPTED": tokens.get("__VIEWSTATEENCRYPTED", ""),
        "__EVENTVALIDATION": tokens.get("__EVENTVALIDATION", ""),
        "ctl00$ContentPlaceHolder1$rblDT": "1",
        "ctl00$ContentPlaceHolder1$chkAllMarket": "on",
        "ctl00$ContentPlaceHolder1$txtDate": from_s,
        "ctl00$ContentPlaceHolder1$txtToDate": to_s,
        "ctl00$ContentPlaceHolder1$Hidden1": "",
        "ctl00$ContentPlaceHolder1$hf_scripcode": "",
        "ctl00$ContentPlaceHolder1$DDate": "",
        "ctl00$ContentPlaceHolder1$SmartSearch$smartSearch": "",
        "ctl00$ContentPlaceHolder1$SmartSearch$hdnCode": "",
    }


def _download_month_csv(session: requests.Session, from_s: str, to_s: str) -> tuple[str, bool]:
    r0, blocked0 = _request_with_backoff(session, "GET", FORM_URL, timeout=45)
    if r0 is None:
        return "", blocked0
    t0 = _extract_tokens(r0.text)

    p1 = _search_payload(t0, from_s, to_s)
    r1, blocked1 = _request_with_backoff(session, "POST", FORM_URL, data=p1, timeout=60)
    if r1 is None:
        return "", bool(blocked0 or blocked1)

    t1 = _extract_tokens(r1.text)
    p2 = _download_payload(t1, from_s, to_s)
    r2, blocked2 = _request_with_backoff(session, "POST", FORM_URL, data=p2, timeout=90)
    if r2 is None:
        return "", bool(blocked0 or blocked1 or blocked2)

    text = str(r2.text or "")
    if CSV_HEADER not in text:
        return "", bool(blocked0 or blocked1 or blocked2)
    return text, bool(blocked0 or blocked1 or blocked2)


def _parse_csv_text(csv_text: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for i, raw_line in enumerate(csv_text.splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        if i == 0 and line.startswith("Deal Date,"):
            continue

        # BSE CSV occasionally includes unquoted commas in client names.
        parts = [p.strip() for p in raw_line.split(",")]
        if len(parts) < 7:
            continue

        rows.append(
            {
                "date": parts[0],
                "exchange": "BSE",
                "scrip_code": parts[1],
                "scrip_name": parts[2],
                "client_name": ",".join(parts[3:-3]).strip(),
                "deal_type": parts[-3],
                "quantity": parts[-2],
                "price": parts[-1],
            }
        )

    if not rows:
        return pd.DataFrame(columns=MONTH_COLUMNS)

    out = pd.DataFrame(rows)
    out["date"] = pd.to_datetime(out["date"], dayfirst=True, errors="coerce")
    out["quantity"] = pd.to_numeric(out["quantity"], errors="coerce")
    out["price"] = pd.to_numeric(out["price"], errors="coerce")
    deal = out["deal_type"].astype(str).str.strip().str.upper()
    out["deal_type"] = deal.replace({"P": "BUY", "B": "BUY", "S": "SELL"}).str.extract(r"(BUY|SELL)", expand=False)
    out["scrip_code"] = out["scrip_code"].astype(str).str.strip()
    out["scrip_name"] = out["scrip_name"].astype(str).str.strip()
    out["client_name"] = out["client_name"].astype(str).str.strip()
    return out[MONTH_COLUMNS]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scrape BSE bulk deals.")
    p.add_argument("--start-year", type=int, default=2004)
    p.add_argument("--end-year", type=int, default=date.today().year)
    p.add_argument("--resume", action="store_true", default=True)
    p.add_argument("--no-resume", action="store_false", dest="resume")
    p.add_argument("--delay-min", type=float, default=2.0)
    p.add_argument("--delay-max", type=float, default=5.0)
    p.add_argument("--max-months", type=int, default=0, help="Probe mode: cap number of months processed (0 = all).")
    p.add_argument("--log-every", type=int, default=1, help="Print ingestion status every N processed months.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path("data/raw/alternative/bulk_deals")
    out_dir.mkdir(parents=True, exist_ok=True)
    state = ResumeState(out_dir / ".resume_state.json")

    code_map, name_map, et_nifty_map = _load_ticker_lookup()

    session = requests.Session()
    session.headers.update(HEADERS)

    parts: list[pd.DataFrame] = []
    blocked_months = 0
    reused_months = 0
    ingested_months = 0
    empty_months = 0
    processed_months = 0
    cumulative_rows = 0
    tasks = list(_month_range(args.start_year, args.end_year))
    if int(args.max_months) > 0:
        tasks = tasks[: int(args.max_months)]

    for start, end in iter_progress(tasks, desc="bulk_deals", unit="month"):
        key = f"{start.year}-{start.month:02d}"
        month_file = out_dir / f"bulk_deals_{start.year}_{start.month:02d}.csv"

        if args.resume and month_file.exists():
            try:
                old = pd.read_csv(month_file, parse_dates=["date"])
                old = _assign_tickers(old, code_map, name_map, et_nifty_map)
                old.to_csv(month_file, index=False)
                if state.has(key) or len(old) > 0:
                    parts.append(old)
                    state.mark(key)
                    reused_months += 1
                    processed_months += 1
                    cumulative_rows += int(len(old))
                    reused_status = "reused" if len(old) > 0 else "reused_empty"
                    if args.log_every > 0 and (processed_months % int(args.log_every) == 0):
                        print(
                            f"[bulk_deals][{key}] status={reused_status} rows={len(old)} "
                            f"cumulative_rows={cumulative_rows} processed={processed_months}/{len(tasks)}"
                        )
                    continue
            except Exception:
                pass

        from_s = start.strftime("%d/%m/%Y")
        to_s = end.strftime("%d/%m/%Y")
        csv_text, blocked = _download_month_csv(session, from_s, to_s)
        if blocked and not csv_text:
            blocked_months += 1
            print(f"[bulk_deals][warn] blocked response for {key}; will retry on next run")
            continue

        df = _parse_csv_text(csv_text)
        if df.empty:
            df = pd.DataFrame(columns=MONTH_COLUMNS)

        df = _assign_tickers(df, code_map, name_map, et_nifty_map)
        df = df[["date", "exchange", "scrip_code", "scrip_name", "client_name", "deal_type", "quantity", "price", "nse_ticker"]]
        df.to_csv(month_file, index=False)

        state.mark(key)
        parts.append(df)
        processed_months += 1
        month_rows = int(len(df))
        cumulative_rows += month_rows
        if month_rows > 0:
            ingested_months += 1
            status = "ingested"
        else:
            empty_months += 1
            status = "empty"
        if args.log_every > 0 and (processed_months % int(args.log_every) == 0):
            print(
                f"[bulk_deals][{key}] status={status} rows={month_rows} "
                f"cumulative_rows={cumulative_rows} processed={processed_months}/{len(tasks)}"
            )
        time.sleep(random.uniform(args.delay_min, args.delay_max))

    all_df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    proc_path = Path("data/processed/alternative/bulk_deals_all.csv")
    proc_path.parent.mkdir(parents=True, exist_ok=True)
    if not all_df.empty:
        all_df["date"] = pd.to_datetime(all_df["date"], errors="coerce")
        all_df = all_df.sort_values(["date", "scrip_code"], kind="mergesort")
    all_df.to_csv(proc_path, index=False)

    if blocked_months > 0 and all_df.empty:
        print(
            f"[bulk_deals] failed: blocked by source for {blocked_months} months; "
            "no rows collected. Retry later or from another network/IP."
        )
        return 2

    mapped_mask = all_df["nse_ticker"].astype(str).str.upper().str.endswith(".NS")
    mapped_rows = int(mapped_mask.sum())
    mapped_tickers = int(all_df.loc[mapped_mask, "nse_ticker"].nunique())
    total_rows = int(len(all_df))

    print(
        f"[bulk_deals] completed: {len(list(out_dir.glob('bulk_deals_*.csv')))} files, "
        f"{int(len(all_df))} rows, date range {args.start_year}-{args.end_year}"
    )
    print(
        f"[bulk_deals] ingestion_summary: ingested_months={ingested_months}, "
        f"reused_months={reused_months}, empty_months={empty_months}, blocked_months={blocked_months}, "
        f"cumulative_rows={cumulative_rows}, mapped_rows={mapped_rows}, mapped_pct={mapped_rows / max(1, total_rows):.4f}, "
        f"mapped_tickers={mapped_tickers}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
