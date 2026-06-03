#!/usr/bin/env python3
"""Scrape rating actions (CRISIL/ICRA/CARE) with robust fallbacks."""

from __future__ import annotations

import argparse
import difflib
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
    try:
        from utils.progress_resume import ResumeState, iter_progress
    except ModuleNotFoundError:
        # Fallback: simple progress without resume
        ResumeState = None
        def iter_progress(items, **kwargs):
            for item in items:
                yield item


CRISIL_URL = "https://www.crisil.com/en/home/our-businesses/ratings/credit-rating-news.html"
ICRA_RATING_URL = "https://www.icra.in/Rating"
ICRA_ALL_URL = "https://www.icra.in/Rating/AllRatingRationales"
BSE_ANN_API = "https://api.bseindia.com/BseIndiaAPI/api/AnnSubCategoryGetData/w"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/javascript, */*",
    "Referer": "https://www.bseindia.com/corporates/ann.html",
    "X-Requested-With": "XMLHttpRequest",
}

STOPWORDS = {
    "LTD",
    "LIMITED",
    "CO",
    "COMPANY",
    "CORP",
    "CORPORATION",
    "INC",
    "PVT",
    "PRIVATE",
    "PUBLIC",
    "PLC",
    "LLP",
    "THE",
    "OF",
    "AND",
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


def _norm_company(value: object) -> str:
    s = str(value or "").upper().replace("&", " AND ")
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    toks = [t for t in s.split() if t and t not in STOPWORDS]
    return " ".join(toks)


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    ta = set(a.split())
    tb = set(b.split())
    inter = len(ta & tb)
    token = (2.0 * inter / (len(ta) + len(tb))) if ta and tb else 0.0
    seq = difflib.SequenceMatcher(None, a, b).ratio()
    return max(token, seq)


def _load_universe_names() -> list[tuple[str, str]]:
    """Load universe of companies with tickers for matching."""
    rows: list[tuple[str, str]] = []
    
    # Try multiple possible paths for the universe file
    universe_paths = [
        Path("universe/nifty500.csv"),
        Path(__file__).parent.parent / "universe" / "nifty500.csv",
        Path("data/universe/nifty500.csv"),
    ]
    
    for p in universe_paths:
        if p.exists():
            try:
                df = pd.read_csv(p)
                for r in df.to_dict("records"):
                    name = str(r.get("Company Name") or "").strip()
                    tk = _normalize_ticker(r.get("Symbol"))
                    if name and tk:
                        rows.append((name, tk))
                if rows:
                    print(f"[universe] Loaded {len(rows)} companies from {p}")
                    break
            except Exception as e:
                print(f"[universe] Error loading {p}: {e}")
    
    if not rows:
        print("[universe] Warning: No universe file found, ticker matching will be disabled")
    
    return rows


def _match_ticker(name: str, universe: list[tuple[str, str]]) -> str:
    """
    Match company name to ticker using fuzzy matching.
    
    Uses multiple strategies:
    1. Exact match on normalized name
    2. Fuzzy match with threshold (lowered to 0.70 for better coverage)
    3. Partial match on key tokens
    """
    n = _norm_company(name)
    
    if not universe:
        return ""
    
    # Strategy 1: Exact match
    for cname, tk in universe:
        if _norm_company(cname) == n:
            return tk
    
    # Strategy 2: Fuzzy match with lowered threshold
    best = (0.0, "")
    for cname, tk in universe:
        s = _similarity(n, _norm_company(cname))
        if s > best[0]:
            best = (s, tk)
    
    if best[0] >= 0.70:  # Lowered from 0.82
        return best[1]
    
    # Strategy 3: Check if company name contains key tokens
    name_tokens = set(n.split())
    for cname, tk in universe:
        cname_tokens = set(_norm_company(cname).split())
        # If 2+ tokens match, consider it a match
        if len(name_tokens & cname_tokens) >= 2:
            return tk
    
    return ""


def _safe_get(session: requests.Session, url: str, params: dict | None = None, retries: int = 5) -> str:
    backoff = 1.0
    for _ in range(retries):
        try:
            r = session.get(url, params=params, timeout=60)
            if r.status_code in {403, 406, 429}:
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
                continue
            if r.status_code >= 500:
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
                continue
            r.raise_for_status()
            return r.text
        except Exception:
            time.sleep(backoff)
            backoff = min(backoff * 2.0, 60.0)
    return ""


def _safe_json(session: requests.Session, url: str, params: dict, retries: int = 5) -> dict:
    backoff = 1.0
    for _ in range(retries):
        try:
            r = session.get(url, params=params, timeout=60)
            if r.status_code in {403, 429}:
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
                continue
            if r.status_code >= 500:
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
                continue
            r.raise_for_status()
            payload = r.json()
            return payload if isinstance(payload, dict) else {}
        except Exception:
            time.sleep(backoff)
            backoff = min(backoff * 2.0, 60.0)
    return {}


def _parse_action_type(text: str) -> str:
    t = str(text or "").upper()
    if "DOWNGRADE" in t:
        return "DOWNGRADE"
    if "UPGRADE" in t:
        return "UPGRADE"
    if "WATCH NEGATIVE" in t or "NEGATIVE WATCH" in t:
        return "WATCH_NEGATIVE"
    if "WATCH POSITIVE" in t or "POSITIVE WATCH" in t:
        return "WATCH_POSITIVE"
    if "AFFIRM" in t or "REAFFIRM" in t:
        return "AFFIRM"
    return "AFFIRM"


def _extract_ratings(text: str) -> tuple[str, str, str]:
    t = str(text or "")
    ratings = re.findall(r"\b(?:AAA|AA\+|AA-|AA|A\+|A-|A|BBB\+|BBB-|BBB|BB\+|BB-|BB|B\+|B-|B)\b", t.upper())
    old = ratings[0] if ratings else ""
    new = ratings[1] if len(ratings) > 1 else (ratings[0] if ratings else "")

    outlook = ""
    u = t.upper()
    if "WATCH NEGATIVE" in u or "NEGATIVE WATCH" in u:
        outlook = "WATCH"
    elif "WATCH POSITIVE" in u or "POSITIVE WATCH" in u:
        outlook = "WATCH"
    elif "NEGATIVE" in u:
        outlook = "NEGATIVE"
    elif "POSITIVE" in u:
        outlook = "POSITIVE"
    elif "STABLE" in u:
        outlook = "STABLE"
    return old, new, outlook


def _extract_company_name(title: str) -> str:
    t = str(title or "").strip()
    if ":" in t:
        return t.split(":", 1)[0].strip()
    if "-" in t:
        return t.split("-", 1)[0].strip()
    return t[:120]


def _infer_agency(text: str) -> str:
    u = str(text or "").upper()
    if "CRISIL" in u:
        return "CRISIL"
    if "ICRA" in u:
        return "ICRA"
    if "CARE" in u:
        return "CARE"
    return ""


def _infer_instrument_type(text: str) -> str:
    u = str(text or "").upper()
    if "NCD" in u:
        return "NCD"
    if "COMMERCIAL PAPER" in u or "CP" in u:
        return "Commercial Paper"
    if "LONG" in u and "TERM" in u:
        return "Long Term"
    if "SHORT" in u and "TERM" in u:
        return "Short Term"
    if "BANK" in u and "FACIL" in u:
        return "Bank Facilities"
    return ""


def _parse_crisil(session: requests.Session) -> pd.DataFrame:
    html = _safe_get(session, CRISIL_URL)
    if not html or "not acceptable" in html.lower() or "blocked" in html.lower():
        return pd.DataFrame()

    # Conservative fallback parser: search for rating-like lines in page text.
    text = re.sub(r"<[^>]+>", " ", html)
    chunks = [re.sub(r"\s+", " ", c).strip() for c in text.split("\n") if "rating" in c.lower()]
    rows: list[dict] = []
    for c in chunks:
        m = re.search(r"(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})", c)
        dt = pd.to_datetime(m.group(1), errors="coerce") if m else pd.NaT
        if pd.isna(dt):
            continue
        old_rating, new_rating, outlook = _extract_ratings(c)
        rows.append(
            {
                "date": dt,
                "company_name": _extract_company_name(c),
                "agency": "CRISIL",
                "instrument_type": _infer_instrument_type(c),
                "old_rating": old_rating,
                "new_rating": new_rating,
                "action_type": _parse_action_type(c),
                "outlook": outlook,
                "raw_text": c,
            }
        )
    return pd.DataFrame(rows)


CARE_RATING_URL = "https://www.careratings.com/credit-rating-news.htm"

def _extract_icra_rational_list(html: str) -> list[dict]:
    if not html:
        return []
    m = re.search(r"var\s+RationalLst\s*=\s*(\[.*?\]);", html, flags=re.S)
    if not m:
        return []
    raw = m.group(1)
    try:
        obj = json.loads(raw)
    except Exception:
        return []
    if not isinstance(obj, list):
        return []
    return [x for x in obj if isinstance(x, dict)]


def _parse_icra(session: requests.Session) -> pd.DataFrame:
    pages = [_safe_get(session, ICRA_RATING_URL), _safe_get(session, ICRA_ALL_URL)]
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for html in pages:
        for item in _extract_icra_rational_list(html):
            title = str(item.get("RationaleTitle") or "").strip()
            if not title:
                continue
            dt = pd.to_datetime(item.get("RationalDate"), errors="coerce")
            if pd.isna(dt):
                dt = pd.Timestamp.today().normalize()
            key = (str(item.get("RationalId") or ""), title)
            if key in seen:
                continue
            seen.add(key)

            old_rating, new_rating, outlook = _extract_ratings(title)
            rows.append(
                {
                    "date": dt,
                    "company_name": _extract_company_name(title),
                    "agency": "ICRA",
                    "instrument_type": _infer_instrument_type(title),
                    "old_rating": old_rating,
                    "new_rating": new_rating,
                    "action_type": _parse_action_type(title),
                    "outlook": outlook,
                    "raw_text": title,
                }
            )

    return pd.DataFrame(rows)


def _parse_care(session: requests.Session) -> pd.DataFrame:
    """Parse CARE ratings from their website."""
    html = _safe_get(session, CARE_RATING_URL)
    if not html or "not acceptable" in html.lower() or "blocked" in html.lower():
        return pd.DataFrame()

    # Search for rating-like patterns in HTML
    text = re.sub(r"<[^>]+>", " ", html)
    chunks = [re.sub(r"\s+", " ", c).strip() for c in text.split("\n") if "rating" in c.lower() or "care" in c.lower()]
    rows: list[dict] = []
    
    for c in chunks:
        # Try to extract date
        m = re.search(r"(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})", c)
        dt = pd.to_datetime(m.group(1), errors="coerce") if m else pd.NaT
        if pd.isna(dt):
            continue
            
        old_rating, new_rating, outlook = _extract_ratings(c)
        rows.append(
            {
                "date": dt,
                "company_name": _extract_company_name(c),
                "agency": "CARE",
                "instrument_type": _infer_instrument_type(c),
                "old_rating": old_rating,
                "new_rating": new_rating,
                "action_type": _parse_action_type(c),
                "outlook": outlook,
                "raw_text": c,
            }
        )
    
    print(f"[care] Parsed {len(rows)} rating actions from CARE website")
    return pd.DataFrame(rows)


def _fetch_bse_rating_announcements(
    session: requests.Session,
    years: list[int],
    max_pages: int = 0,
    page_log_every: int = 25,
) -> pd.DataFrame:
    filters = [
        ("Company Update", "Credit Rating"),
        ("Others", "Reg. 55 - Credit Rating"),
    ]
    rows: list[dict] = []
    seen_ids: set[str] = set()

    for year in sorted({int(y) for y in years}):
        from_dt = f"{year}0101"
        to_dt = f"{year}1231"
        for cat, subcat in filters:
            upper = int(max_pages) if int(max_pages) > 0 else 2500
            for page in range(1, upper + 1):
                payload = _safe_json(
                    session,
                    BSE_ANN_API,
                    {
                        "strScrip": "",
                        "strCat": cat,
                        "strPrevDate": from_dt,
                        "strToDate": to_dt,
                        "strSearch": "P",
                        "strType": "C",
                        "pageno": page,
                        "subcategory": subcat,
                    },
                )
                table = payload.get("Table", []) if isinstance(payload.get("Table", []), list) else []
                meta = payload.get("Table1", []) if isinstance(payload.get("Table1", []), list) else []

                if not table:
                    break

                for r in table:
                    nid = str(r.get("NEWSID") or "").strip()
                    if nid and nid in seen_ids:
                        continue
                    if nid:
                        seen_ids.add(nid)

                    text = " ".join(
                        [
                            str(r.get("NEWSSUB") or ""),
                            str(r.get("HEADLINE") or ""),
                            str(r.get("MORE") or ""),
                            str(r.get("SUBCATNAME") or ""),
                        ]
                    )
                    agency = _infer_agency(text)
                    if agency not in {"CRISIL", "ICRA", "CARE"}:
                        continue

                    old_rating, new_rating, outlook = _extract_ratings(text)
                    rows.append(
                        {
                            "date": pd.to_datetime(r.get("News_submission_dt") or r.get("NEWS_DT") or r.get("DT_TM"), errors="coerce"),
                            "company_name": str(r.get("SLONGNAME") or _extract_company_name(text)),
                            "agency": agency,
                            "instrument_type": _infer_instrument_type(text),
                            "old_rating": old_rating,
                            "new_rating": new_rating,
                            "action_type": _parse_action_type(text),
                            "outlook": outlook,
                            "raw_text": text,
                        }
                    )

                expected_total = None
                if meta:
                    try:
                        expected_total = int(meta[0].get("ROWCNT") or 0)
                    except Exception:
                        expected_total = None
                if expected_total is not None and page * 50 >= expected_total:
                    break
                if page_log_every > 0 and (page % int(page_log_every) == 0):
                    print(
                        f"[ratings][bse_fallback][{year}|{cat}|{subcat}] page={page} "
                        f"kept_rows={len(rows)} expected_total={expected_total if expected_total is not None else 'NA'}"
                    )
                time.sleep(0.05)

    return pd.DataFrame(rows)


def _finalize(df: pd.DataFrame, universe: list[tuple[str, str]]) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(
            columns=[
                "date",
                "company_name",
                "nse_ticker",
                "agency",
                "instrument_type",
                "old_rating",
                "new_rating",
                "action_type",
                "outlook",
            ]
        )
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out.dropna(subset=["date"])
    out["nse_ticker"] = out["company_name"].map(lambda x: _match_ticker(str(x), universe))
    keep = [
        "date",
        "company_name",
        "nse_ticker",
        "agency",
        "instrument_type",
        "old_rating",
        "new_rating",
        "action_type",
        "outlook",
    ]
    for c in keep:
        if c not in out.columns:
            out[c] = ""
    out = out[out["agency"].isin(["CRISIL", "ICRA", "CARE"])].copy()
    return out[keep].reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scrape credit rating actions.")
    p.add_argument("--start-year", type=int, default=2020)  # Changed default to 2020 for recent data
    p.add_argument("--end-year", type=int, default=date.today().year)
    p.add_argument("--resume", action="store_true", default=True)
    p.add_argument("--no-resume", action="store_false", dest="resume")
    p.add_argument("--delay-min", type=float, default=1.0)  # Faster scraping
    p.add_argument("--delay-max", type=float, default=3.0)
    p.add_argument("--max-chunks", type=int, default=0, help="Probe mode: cap agency-year chunks (0 = all).")
    p.add_argument("--max-pages", type=int, default=0, help="Probe mode: cap pages per BSE query (0 = all).")
    p.add_argument("--page-log-every", type=int, default=25, help="Print BSE fallback page heartbeat every N pages.")
    p.add_argument("--log-every", type=int, default=1, help="Print per-chunk ingestion summary every N chunks.")
    p.add_argument(
        "--skip-bse-fallback",
        action="store_true",
        default=False,
        help="Skip BSE announcement fallback source (faster, but fewer historical rows).",
    )
    p.add_argument(
        "--bse-only",
        action="store_true",
        default=False,
        help="Use only BSE announcements (more reliable, captures all agencies)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    raw_dir = Path("data/raw/shared/alternative/credit_ratings")
    raw_dir.mkdir(parents=True, exist_ok=True)
    state = ResumeState(raw_dir / ".resume_state.json")
    universe = _load_universe_names()

    tasks = [(agency, year) for agency in ["CRISIL", "ICRA", "CARE"] for year in range(args.start_year, args.end_year + 1)]
    if int(args.max_chunks) > 0:
        tasks = tasks[: int(args.max_chunks)]

    empty_cols = [
        "date",
        "company_name",
        "nse_ticker",
        "agency",
        "instrument_type",
        "old_rating",
        "new_rating",
        "action_type",
        "outlook",
    ]
    all_frames: list[pd.DataFrame] = []
    pending_tasks: list[tuple[str, int]] = []
    reused = 0
    cumulative_rows = 0

    # Fast resume scan first. If files are already checkpointed, avoid
    # expensive source fetches (especially BSE fallback) entirely.
    for agency, year in tasks:
        key = f"{agency}-{year}"
        out_file = raw_dir / f"ratings_{agency}_{year}.csv"

        if args.resume and out_file.exists():
            try:
                old = pd.read_csv(out_file, parse_dates=["date"])
                if state.has(key) or len(old) > 0:
                    all_frames.append(old)
                    state.mark(key)
                    reused += 1
                    cumulative_rows += int(len(old))
                    continue
            except Exception:
                pass
        pending_tasks.append((agency, year))

    print(
        f"[ratings] resume_scan total_chunks={len(tasks)} reused={reused} "
        f"pending={len(pending_tasks)}"
    )

    if not pending_tasks:
        non_empty_frames = [f for f in all_frames if isinstance(f, pd.DataFrame) and len(f) > 0]
        all_df = pd.concat(non_empty_frames, ignore_index=True) if non_empty_frames else pd.DataFrame(columns=empty_cols)
        proc = Path("data/processed/alternative/credit_ratings_all.csv")
        proc.parent.mkdir(parents=True, exist_ok=True)
        if not all_df.empty:
            all_df["date"] = pd.to_datetime(all_df["date"], errors="coerce")
            all_df = all_df.sort_values(["date", "agency", "company_name"], kind="mergesort")
        all_df.to_csv(proc, index=False)
        print(
            f"[ratings] completed: {int(len(all_df))} actions, "
            f"{int(all_df['nse_ticker'].astype(str).str.len().gt(0).sum()) if not all_df.empty else 0} tickers matched"
        )
        print(
            f"[ratings] ingestion_summary: reused_chunks={reused}, "
            f"processed_chunks={reused}, cumulative_rows={cumulative_rows}"
        )
        return 0

    needed_years = sorted({year for _, year in pending_tasks})

    session = requests.Session()
    session.headers.update(HEADERS)

    # BSE fallback is the MOST RELIABLE source - it captures all 3 agencies
    # Direct agency website scraping is unreliable (blocks, CAPTCHAs, etc.)
    # So we prioritize BSE and use agency websites as supplement
    
    if bool(args.skip_bse_fallback):
        bse_fallback = pd.DataFrame(columns=empty_cols + ["raw_text"])
        print("[ratings] fallback_source BSE skipped (--skip-bse-fallback)")
    else:
        print("[ratings] Fetching from BSE announcements (PRIMARY SOURCE)...")
        bse_fallback = _fetch_bse_rating_announcements(
            session,
            needed_years,
            max_pages=int(args.max_pages),
            page_log_every=int(args.page_log_every),
        )
        print(f"[ratings] fallback_source BSE rows={len(bse_fallback)}")
    
    # Only scrape agency websites if BSE didn't give us enough data
    if len(bse_fallback) < 100 and not args.bse_only:
        print("[ratings] BSE data limited, supplementing with agency websites...")
        direct_crisil = _parse_crisil(session)
        print(f"[ratings] direct_source CRISIL rows={len(direct_crisil)}")
        direct_icra = _parse_icra(session)
        print(f"[ratings] direct_source ICRA rows={len(direct_icra)}")
        direct_care = _parse_care(session)
        print(f"[ratings] direct_source CARE rows={len(direct_care)}")
    else:
        direct_crisil = pd.DataFrame(columns=empty_cols + ["raw_text"])
        direct_icra = pd.DataFrame(columns=empty_cols + ["raw_text"])
        direct_care = pd.DataFrame(columns=empty_cols + ["raw_text"])
        print("[ratings] Using BSE data only (sufficient coverage)")

    source_frames = [f for f in [bse_fallback, direct_crisil, direct_icra, direct_care] if isinstance(f, pd.DataFrame) and len(f) > 0]
    combined = pd.concat(source_frames, ignore_index=True) if source_frames else pd.DataFrame(columns=empty_cols)
    finalized = _finalize(combined, universe)
    print(f"[ratings] finalized rows={len(finalized)}")

    processed = reused
    for agency, year in iter_progress(pending_tasks, desc="credit_ratings", unit="chunk"):
        key = f"{agency}-{year}"
        out_file = raw_dir / f"ratings_{agency}_{year}.csv"

        if finalized.empty:
            sub = pd.DataFrame(columns=empty_cols)
        else:
            sub = finalized[(finalized["agency"] == agency) & (finalized["date"].dt.year == year)].copy()

        sub.to_csv(out_file, index=False)
        state.mark(key)
        all_frames.append(sub)
        processed += 1
        rows = int(len(sub))
        cumulative_rows += rows
        status = "ingested" if rows > 0 else "empty"
        if args.log_every > 0 and (processed % int(args.log_every) == 0):
            print(
                f"[ratings][{agency}|{year}] status={status} rows={rows} "
                f"cumulative_rows={cumulative_rows} processed={processed}/{len(tasks)}"
            )
        time.sleep(random.uniform(args.delay_min, args.delay_max))

    non_empty_frames = [f for f in all_frames if isinstance(f, pd.DataFrame) and len(f) > 0]
    all_df = pd.concat(non_empty_frames, ignore_index=True) if non_empty_frames else pd.DataFrame(columns=empty_cols)
    proc = Path("data/processed/alternative/credit_ratings_all.csv")
    proc.parent.mkdir(parents=True, exist_ok=True)
    if not all_df.empty:
        all_df["date"] = pd.to_datetime(all_df["date"], errors="coerce")
        all_df = all_df.sort_values(["date", "agency", "company_name"], kind="mergesort")
    all_df.to_csv(proc, index=False)

    print(
        f"[ratings] completed: {int(len(all_df))} actions, "
        f"{int(all_df['nse_ticker'].astype(str).str.len().gt(0).sum()) if not all_df.empty else 0} tickers matched"
    )
    print(
        f"[ratings] ingestion_summary: reused_chunks={reused}, "
        f"processed_chunks={processed}, cumulative_rows={cumulative_rows}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
