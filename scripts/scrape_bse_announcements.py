#!/usr/bin/env python3
"""Scrape BSE corporate announcements for selected event categories."""

from __future__ import annotations

import argparse
import json
import random
import re
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

try:
    from scripts.utils.progress_resume import ResumeState, iter_progress
except ModuleNotFoundError:  # direct script execution: python3 scripts/...
    from utils.progress_resume import ResumeState, iter_progress


API_URL = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"

# Requested business categories -> live BSE category/subcategory filters.
CATEGORY_FILTERS: dict[str, list[dict[str, str | re.Pattern[str] | None]]] = {
    "Order Win": [
        {"strCat": "Company Update", "subcategory": "Award of Order / Receipt of Order", "text_filter": None},
        {"strCat": "Company Update", "subcategory": "Reg. 30 - Awarding of orders/contracts", "text_filter": None},
    ],
    "Capacity Expansion": [
        {
            "strCat": "Company Update",
            "subcategory": "-1",
            "text_filter": re.compile(r"\b(capacity|capex|expansion|expand|greenfield|brownfield|new\s+plant)\b", flags=re.I),
        },
        {
            "strCat": "Others",
            "subcategory": "-1",
            "text_filter": re.compile(r"\b(capacity|capex|expansion|expand|greenfield|brownfield|new\s+plant)\b", flags=re.I),
        },
    ],
    "Acquisition": [
        {"strCat": "Company Update", "subcategory": "Acquisition", "text_filter": None},
        {"strCat": "Company Update", "subcategory": "Update-Acquisition/Scheme/Sale/Disposal/Reg30", "text_filter": None},
    ],
    "Merger": [
        {"strCat": "Company Update", "subcategory": "Amalgamation/ Merger", "text_filter": None},
        {"strCat": "Company Update", "subcategory": "De-merger", "text_filter": None},
        {"strCat": "Corp. Action", "subcategory": "Amalgamation / Merger / Demerger", "text_filter": None},
    ],
    "Insider Trading": [
        {"strCat": "Insider Trading / SAST", "subcategory": "-1", "text_filter": None},
        {"strCat": "Others", "subcategory": "Reg. 7 (2) - Prohibition of Insider Trading  Regulations, 2015", "text_filter": None},
    ],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/javascript, */*",
    "Referer": "https://www.bseindia.com/corporates/ann.html",
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


def _load_bse_map() -> dict[str, str]:
    out: dict[str, str] = {}
    meta_dir = Path("data/raw/vendors/screener/metadata")
    for p in meta_dir.glob("*_metadata.json"):
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        code = str(d.get("bse_code") or "").strip()
        tk = _normalize_ticker(d.get("ticker"))
        if code and tk:
            out[code] = tk
    return out


def _safe_json(
    session: requests.Session,
    params: dict[str, object],
    *,
    retries: int = 3,
    request_timeout: int = 20,
    context: str = "",
) -> tuple[dict, bool]:
    backoff = 1.0
    for attempt in range(1, retries + 1):
        try:
            r = session.get(API_URL, params=params, timeout=request_timeout)
            if r.status_code in {403, 429}:
                print(
                    f"[announcements]{context} retry={attempt}/{retries} "
                    f"status={r.status_code} backoff={backoff:.1f}s"
                )
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
                continue
            if r.status_code >= 500:
                print(
                    f"[announcements]{context} retry={attempt}/{retries} "
                    f"status={r.status_code} backoff={backoff:.1f}s"
                )
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
                continue
            r.raise_for_status()
            payload = r.json()
            if isinstance(payload, dict):
                return payload, True
            return {}, True
        except Exception as exc:
            print(
                f"[announcements]{context} retry={attempt}/{retries} "
                f"error={type(exc).__name__} backoff={backoff:.1f}s"
            )
            time.sleep(backoff)
            backoff = min(backoff * 2.0, 60.0)
    return {}, False


def _fetch_records(
    session: requests.Session,
    *,
    cat: str,
    subcat: str,
    year: int,
    text_filter: re.Pattern[str] | None,
    max_pages: int = 0,
    page_log_every: int = 25,
    log_prefix: str = "",
    request_timeout: int = 20,
    max_retries: int = 3,
    max_consecutive_page_failures: int = 2,
) -> list[dict]:
    out: list[dict] = []
    seen_ids: set[str] = set()

    from_dt = f"{year}0101"
    to_dt = f"{year}1231"
    expected_total = None
    consecutive_page_failures = 0

    upper = int(max_pages) if int(max_pages) > 0 else 2500
    for page in range(1, upper + 1):
        page_t0 = time.time()
        params = {
            "strScrip": "",
            "strCat": cat,
            "strPrevDate": from_dt,
            "strToDate": to_dt,
            "strSearch": "P",
            "strType": "C",
            "pageno": page,
            "subcategory": subcat,
        }
        payload, ok = _safe_json(
            session,
            params,
            retries=int(max_retries),
            request_timeout=int(request_timeout),
            context=f"[{year}|{cat}|{subcat}|page={page}]",
        )
        if not ok:
            consecutive_page_failures += 1
            print(
                f"[announcements]{log_prefix} page={page} status=request_failed "
                f"elapsed={time.time() - page_t0:.1f}s consecutive_failures={consecutive_page_failures}"
            )
            if consecutive_page_failures >= int(max_consecutive_page_failures):
                print(
                    f"[announcements]{log_prefix} stopping query early due to consecutive "
                    f"request failures (>={max_consecutive_page_failures})."
                )
                break
            continue
        consecutive_page_failures = 0
        table = payload.get("Table", []) if isinstance(payload.get("Table", []), list) else []
        meta = payload.get("Table1", []) if isinstance(payload.get("Table1", []), list) else []

        if expected_total is None and meta:
            try:
                expected_total = int(meta[0].get("ROWCNT") or 0)
            except Exception:
                expected_total = None

        if not table:
            print(
                f"[announcements]{log_prefix} page={page} status=no_records "
                f"elapsed={time.time() - page_t0:.1f}s"
            )
            break

        new_count = 0
        for row in table:
            news_id = str(row.get("NEWSID") or "").strip()
            if news_id and news_id in seen_ids:
                continue

            text_blob = " ".join(
                [
                    str(row.get("NEWSSUB") or ""),
                    str(row.get("HEADLINE") or ""),
                    str(row.get("MORE") or ""),
                    str(row.get("SUBCATNAME") or ""),
                ]
            )
            if text_filter is not None and not text_filter.search(text_blob):
                continue

            if news_id:
                seen_ids.add(news_id)
            out.append(row)
            new_count += 1

        if new_count == 0 and page > 1:
            break
        if expected_total is not None and page * 50 >= expected_total:
            break
        if page_log_every > 0 and (page % int(page_log_every) == 0):
            tag = f"{log_prefix} " if log_prefix else ""
            print(
                f"[announcements]{tag}page={page} kept_rows={len(out)} "
                f"expected_total={expected_total if expected_total is not None else 'NA'} "
                f"elapsed={time.time() - page_t0:.1f}s"
            )

        # Fast pagination. Retries already gate failures.
        time.sleep(0.05)

    return out


def _parse(records: list[dict], category: str, bse_map: dict[str, str]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=["date", "bse_code", "nse_ticker", "company_name", "category", "headline", "announcement_text"])

    df = pd.DataFrame(records)
    dt_col = next((c for c in ["News_submission_dt", "NEWS_DT", "DT_TM", "Date", "date"] if c in df.columns), None)
    code_col = next((c for c in ["SCRIP_CD", "SCRIPCODE", "scrip_code"] if c in df.columns), None)
    name_col = next((c for c in ["SLONGNAME", "SCRIPNAME", "company_name"] if c in df.columns), None)

    out = pd.DataFrame()
    out["date"] = pd.to_datetime(df[dt_col], errors="coerce") if dt_col else pd.NaT
    out["bse_code"] = df[code_col].astype(str).str.strip() if code_col else ""
    out["nse_ticker"] = out["bse_code"].map(bse_map).fillna("")
    out["company_name"] = df[name_col].astype(str) if name_col else ""
    out["category"] = category

    sub = df.get("NEWSSUB", "").astype(str)
    head = df.get("HEADLINE", "").astype(str)
    more = df.get("MORE", "").astype(str)
    out["headline"] = sub.where(sub.str.len() > 0, head)
    out["announcement_text"] = (head + " " + more).str.strip()

    return out[["date", "bse_code", "nse_ticker", "company_name", "category", "headline", "announcement_text"]]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scrape BSE announcements by category.")
    p.add_argument("--start-year", type=int, default=2010)
    p.add_argument("--end-year", type=int, default=date.today().year)
    p.add_argument(
        "--api-min-year",
        type=int,
        default=2023,
        help="Skip historical years before this bound (BSE subcategory history is sparse/unavailable).",
    )
    p.add_argument("--resume", action="store_true", default=True)
    p.add_argument("--no-resume", action="store_false", dest="resume")
    p.add_argument("--delay-min", type=float, default=2.0)
    p.add_argument("--delay-max", type=float, default=5.0)
    p.add_argument("--max-chunks", type=int, default=0, help="Probe mode: cap category-year chunks (0 = all).")
    p.add_argument("--max-pages", type=int, default=0, help="Probe mode: cap pages per query (0 = all).")
    p.add_argument("--request-timeout", type=int, default=60, help="HTTP timeout per page request.")
    p.add_argument("--max-retries", type=int, default=4, help="Maximum retries per page request.")
    p.add_argument(
        "--max-consecutive-page-failures",
        type=int,
        default=2,
        help="Stop a category/year query after this many consecutive request failures.",
    )
    p.add_argument("--page-log-every", type=int, default=25, help="Print per-query page heartbeat every N pages.")
    p.add_argument("--log-every", type=int, default=1, help="Print per-chunk ingestion summary every N chunks.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path("data/raw/exchanges/bse/alternative/order_announcements")
    out_dir.mkdir(parents=True, exist_ok=True)
    state = ResumeState(out_dir / ".resume_state.json")

    bse_map = _load_bse_map()
    session = requests.Session()
    session.headers.update(HEADERS)

    parts: list[pd.DataFrame] = []
    processed = 0
    reused = 0
    cumulative_rows = 0
    tasks: list[tuple[str, str, int]] = []
    for category in CATEGORY_FILTERS:
        slug = category.lower().replace(" ", "_")
        for year in range(args.start_year, args.end_year + 1):
            tasks.append((category, slug, year))

    if int(args.max_chunks) > 0:
        tasks = tasks[: int(args.max_chunks)]

    for category, cat_slug, year in iter_progress(tasks, desc="announcements", unit="chunk"):
        key = f"{cat_slug}-{year}"
        out_file = out_dir / f"announcements_{cat_slug}_{year}.csv"

        if args.resume and out_file.exists():
            try:
                old = pd.read_csv(out_file, parse_dates=["date"])
                if state.has(key) or len(old) > 0:
                    parts.append(old)
                    state.mark(key)
                    reused += 1
                    processed += 1
                    cumulative_rows += int(len(old))
                    reused_status = "reused" if len(old) > 0 else "reused_empty"
                    if args.log_every > 0 and (processed % int(args.log_every) == 0):
                        print(
                            f"[announcements][{category}|{year}] status={reused_status} rows={len(old)} "
                            f"cumulative_rows={cumulative_rows} processed={processed}/{len(tasks)}"
                        )
                    continue
            except Exception:
                pass

        if int(year) < int(args.api_min_year):
            empty = pd.DataFrame(
                columns=[
                    "date",
                    "bse_code",
                    "nse_ticker",
                    "company_name",
                    "category",
                    "headline",
                    "announcement_text",
                ]
            )
            empty.to_csv(out_file, index=False)
            state.mark(key)
            parts.append(empty)
            processed += 1
            if args.log_every > 0 and (processed % int(args.log_every) == 0):
                print(
                    f"[announcements][{category}|{year}] status=skipped_unsupported_history rows=0 "
                    f"api_min_year={args.api_min_year} cumulative_rows={cumulative_rows} "
                    f"processed={processed}/{len(tasks)}"
                )
            continue

        all_records: list[dict] = []
        seen_news: set[str] = set()
        for cfg in CATEGORY_FILTERS.get(category, []):
            str_cat = str(cfg["strCat"])
            subcat = str(cfg["subcategory"])
            print(f"[announcements][{category}|{year}] query_start strCat='{str_cat}' subcategory='{subcat}'")
            recs = _fetch_records(
                session,
                cat=str_cat,
                subcat=subcat,
                year=year,
                text_filter=cfg.get("text_filter") if isinstance(cfg.get("text_filter"), re.Pattern) else None,
                max_pages=int(args.max_pages),
                page_log_every=int(args.page_log_every),
                log_prefix=f"[{category}|{year}|{str_cat}|{subcat}]",
                request_timeout=int(args.request_timeout),
                max_retries=int(args.max_retries),
                max_consecutive_page_failures=int(args.max_consecutive_page_failures),
            )
            print(f"[announcements][{category}|{year}] query_done strCat='{str_cat}' subcategory='{subcat}' rows={len(recs)}")
            for r in recs:
                nid = str(r.get("NEWSID") or "").strip()
                k = nid if nid else f"{r.get('SCRIP_CD')}|{r.get('News_submission_dt')}|{r.get('NEWSSUB')}"
                if k in seen_news:
                    continue
                seen_news.add(k)
                all_records.append(r)

        df = _parse(all_records, category=category, bse_map=bse_map)
        df.to_csv(out_file, index=False)

        state.mark(key)
        parts.append(df)
        processed += 1
        rows = int(len(df))
        cumulative_rows += rows
        status = "ingested" if rows > 0 else "empty"
        if args.log_every > 0 and (processed % int(args.log_every) == 0):
            print(
                f"[announcements][{category}|{year}] status={status} rows={rows} "
                f"cumulative_rows={cumulative_rows} processed={processed}/{len(tasks)}"
            )
        time.sleep(random.uniform(args.delay_min, args.delay_max))

    all_df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    proc = Path("data/processed/alternative/announcements_all.csv")
    proc.parent.mkdir(parents=True, exist_ok=True)
    if not all_df.empty:
        all_df["date"] = pd.to_datetime(all_df["date"], errors="coerce")
        all_df = all_df.sort_values(["date", "nse_ticker", "category"], kind="mergesort")
    all_df.to_csv(proc, index=False)

    print(
        f"[announcements] completed: {int(len(all_df))} announcements, "
        f"{int(all_df['nse_ticker'].astype(str).str.len().gt(0).sum()) if not all_df.empty else 0} tickers"
    )
    print(
        f"[announcements] ingestion_summary: reused_chunks={reused}, "
        f"processed_chunks={processed}, cumulative_rows={cumulative_rows}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
