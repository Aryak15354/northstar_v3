#!/usr/bin/env python3
"""Scrape earnings announcement dates using NSE corporate filings APIs.

Primary source:
  /api/corporates-corporateActions (purpose=Financial Results)
Fallback source:
  /api/corporates-financial-results
"""

from __future__ import annotations

import argparse
import os
import random
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

from scripts.utils.progress_resume import ResumeState, iter_progress


NSE_HOME_URL = "https://www.nseindia.com"
NSE_FILINGS_URL = "https://www.nseindia.com/companies-listing/corporate-filings-actions"
NSE_CORP_ACTIONS_URL = "https://www.nseindia.com/api/corporates-corporateActions"
NSE_FIN_RESULTS_URL = "https://www.nseindia.com/api/corporates-financial-results"
NSE_MIN_HISTORY_YEAR = 2010

NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Referer": "https://www.nseindia.com/",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "Connection": "keep-alive",
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


def _quarter_windows(year: int) -> list[tuple[int, pd.Timestamp, pd.Timestamp]]:
    return [
        (1, pd.Timestamp(f"{year}-01-01"), pd.Timestamp(f"{year}-03-31")),
        (2, pd.Timestamp(f"{year}-04-01"), pd.Timestamp(f"{year}-06-30")),
        (3, pd.Timestamp(f"{year}-07-01"), pd.Timestamp(f"{year}-09-30")),
        (4, pd.Timestamp(f"{year}-10-01"), pd.Timestamp(f"{year}-12-31")),
    ]


def _fmt_nse_date(dt: pd.Timestamp) -> str:
    return pd.Timestamp(dt).strftime("%d-%m-%Y")


def _prime_nse_session(session: requests.Session, request_timeout: int, quiet: bool = False) -> None:
    targets = [NSE_HOME_URL, NSE_FILINGS_URL]
    for idx, target in enumerate(targets, start=1):
        try:
            r = session.get(target, timeout=request_timeout)
            if not quiet:
                print(f"[earnings][nse-session] prime_step={idx}/{len(targets)} status={r.status_code} url={target}")
        except Exception as exc:  # noqa: BLE001
            if not quiet:
                print(
                    f"[earnings][nse-session] prime_step={idx}/{len(targets)} "
                    f"error={type(exc).__name__} url={target}"
                )
        time.sleep(1.5)


def _safe_get_json(
    session: requests.Session,
    url: str,
    params: dict[str, str],
    *,
    retries: int,
    request_timeout: int,
    context: str,
) -> tuple[list[dict], bool]:
    backoff = 1.0
    for attempt in range(1, retries + 1):
        try:
            r = session.get(url, params=params, timeout=request_timeout)
            if r.status_code in {401, 403, 429}:
                print(
                    f"[earnings]{context} retry={attempt}/{retries} "
                    f"status={r.status_code} backoff={backoff:.1f}s"
                )
                _prime_nse_session(session, request_timeout, quiet=True)
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)
                continue
            if r.status_code >= 500:
                print(
                    f"[earnings]{context} retry={attempt}/{retries} "
                    f"status={r.status_code} backoff={backoff:.1f}s"
                )
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)
                continue
            r.raise_for_status()
            payload = r.json()
            if isinstance(payload, list):
                return payload, True
            if isinstance(payload, dict):
                for k in ["data", "Table", "Table1"]:
                    if isinstance(payload.get(k), list):
                        return payload[k], True
            return [], True
        except Exception as exc:  # noqa: BLE001
            print(
                f"[earnings]{context} retry={attempt}/{retries} "
                f"error={type(exc).__name__} backoff={backoff:.1f}s"
            )
            _prime_nse_session(session, request_timeout, quiet=True)
            time.sleep(backoff)
            backoff = min(backoff * 2.0, 30.0)
    return [], False


def _parse_dates_for_record(rec: dict, keys: list[str]) -> pd.Timestamp:
    for k in keys:
        v = rec.get(k)
        if v in (None, "", "-", "NA"):
            continue
        dt = pd.to_datetime(v, errors="coerce", dayfirst=True)
        if pd.notna(dt):
            return pd.Timestamp(dt)
    return pd.NaT


def _from_corporate_action_record(rec: dict) -> dict | None:
    subject = str(rec.get("subject") or "").strip()
    if not subject:
        return None
    # Defensive local filter in case server-side purpose filter changes.
    low = subject.lower()
    if ("result" not in low) and ("financial" not in low):
        return None

    ann = _parse_dates_for_record(rec, ["caBroadcastDate", "bcStartDate", "recDate", "exDate"])
    exd = _parse_dates_for_record(rec, ["exDate"])
    symbol = str(rec.get("symbol") or "").strip().upper()
    if not symbol:
        return None

    return {
        "announcement_date": ann,
        "nse_symbol": symbol,
        "nse_ticker": _normalize_ticker(symbol),
        "company_name": str(rec.get("comp") or "").strip(),
        "ex_date": exd,
        "purpose": subject,
    }


def _from_financial_result_record(rec: dict) -> dict | None:
    ann = _parse_dates_for_record(rec, ["broadCastDate", "filingDate", "exchdisstime"])
    symbol = str(rec.get("symbol") or "").strip().upper()
    if not symbol:
        return None

    rel = str(rec.get("relatingTo") or "").strip()
    desc = str(rec.get("resultDescription") or "").strip()
    purpose = desc if desc else (f"Financial Results - {rel}" if rel else "Financial Results")
    exd = _parse_dates_for_record(rec, ["toDate"])

    return {
        "announcement_date": ann,
        "nse_symbol": symbol,
        "nse_ticker": _normalize_ticker(symbol),
        "company_name": str(rec.get("companyName") or "").strip(),
        "ex_date": exd,
        "purpose": purpose,
    }


def _to_frame(records: list[dict]) -> pd.DataFrame:
    cols = ["announcement_date", "nse_symbol", "nse_ticker", "company_name", "ex_date", "purpose"]
    if not records:
        return pd.DataFrame(columns=cols)

    rows: list[dict] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if any(k in rec for k in ["subject", "exDate", "caBroadcastDate", "comp"]):
            row = _from_corporate_action_record(rec)
        else:
            row = _from_financial_result_record(rec)
        if row is not None:
            rows.append(row)

    if not rows:
        return pd.DataFrame(columns=cols)

    out = pd.DataFrame(rows)
    out["announcement_date"] = pd.to_datetime(out["announcement_date"], errors="coerce")
    out["ex_date"] = pd.to_datetime(out["ex_date"], errors="coerce")
    out = out.dropna(subset=["announcement_date"]).copy()
    out = out[out["nse_ticker"].astype(str).str.len() > 0].copy()
    out = out.drop_duplicates(subset=["announcement_date", "nse_ticker", "purpose"], keep="last")
    return out[cols].sort_values(["announcement_date", "nse_ticker"], kind="mergesort").reset_index(drop=True)


def _is_year_file_valid(df: pd.DataFrame, year: int, min_history_year: int) -> bool:
    """
    Guard resume reuse against stale/corrupt year files.

    Reuse is allowed when:
    - pre-history years (< NSE min history) are empty, or
    - announcement_date is present and dates predominantly match the target year.
    """
    if not isinstance(df, pd.DataFrame):
        return False
    if df.empty:
        return int(year) < int(min_history_year)
    if "announcement_date" not in df.columns:
        return False

    d = pd.to_datetime(df["announcement_date"], errors="coerce")
    if int(d.notna().sum()) == 0:
        return False
    years = d.dropna().dt.year.astype(int)
    if years.empty:
        return False
    target_share = float((years == int(year)).mean())
    # Require majority year match; catches stale reused files (e.g., 2025 file containing 2020 rows).
    return bool(target_share >= 0.80)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Scrape NSE earnings announcement dates (financial results).")
    p.add_argument("--start-year", type=int, default=2005)
    p.add_argument("--end-year", type=int, default=date.today().year)
    p.add_argument("--resume", action="store_true", default=True)
    p.add_argument("--no-resume", action="store_false", dest="resume")
    p.add_argument("--delay-min", type=float, default=2.0)
    p.add_argument("--delay-max", type=float, default=5.0)
    p.add_argument("--max-years", type=int, default=0, help="Probe mode: cap number of years (0 = all).")
    p.add_argument("--max-quarters", type=int, default=0, help="Probe mode: cap quarter windows queried globally (0 = all).")
    p.add_argument("--log-every", type=int, default=1, help="Print per-year ingestion summary every N years.")
    p.add_argument("--page-log-every", type=int, default=1, help="Compatibility alias; now controls quarter heartbeat every N windows.")
    p.add_argument("--request-timeout", type=int, default=25, help="HTTP timeout in seconds.")
    p.add_argument("--max-retries", type=int, default=4, help="Max retries per API request.")
    p.add_argument(
        "--max-consecutive-page-failures",
        type=int,
        default=2,
        help="Compatibility alias; now max consecutive quarter request failures per year.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out_dir = Path("data/raw/shared/alternative/earnings_dates")
    out_dir.mkdir(parents=True, exist_ok=True)
    state = ResumeState(out_dir / ".resume_state.json")

    session = requests.Session()
    session.headers.update(NSE_HEADERS)
    _prime_nse_session(session, int(args.request_timeout))

    parts: list[pd.DataFrame] = []
    processed = 0
    reused = 0
    cumulative_rows = 0
    queried_quarters = 0

    years = list(range(int(args.start_year), int(args.end_year) + 1))
    if int(args.max_years) > 0:
        years = years[: int(args.max_years)]

    for year in iter_progress(years, desc="earnings_dates", unit="year"):
        key = str(year)
        out_file = out_dir / f"earnings_{year}.csv"

        if args.resume and out_file.exists():
            try:
                old = pd.read_csv(out_file, parse_dates=["announcement_date", "ex_date"])
                if _is_year_file_valid(old, year, NSE_MIN_HISTORY_YEAR) and (state.has(key) or len(old) > 0):
                    parts.append(old)
                    state.mark(key)
                    reused += 1
                    processed += 1
                    cumulative_rows += int(len(old))
                    reused_status = "reused" if len(old) > 0 else "reused_empty"
                    if args.log_every > 0 and (processed % int(args.log_every) == 0):
                        print(
                            f"[earnings][{year}] status={reused_status} rows={len(old)} "
                            f"cumulative_rows={cumulative_rows} processed={processed}/{len(years)}"
                        )
                    continue
                print(
                    f"[earnings][{year}] stale_or_invalid_existing_file rows={len(old)} "
                    f"-> reingesting"
                )
            except Exception:
                pass

        if year < NSE_MIN_HISTORY_YEAR:
            empty = pd.DataFrame(
                columns=["announcement_date", "nse_symbol", "nse_ticker", "company_name", "ex_date", "purpose"]
            )
            empty.to_csv(out_file, index=False)
            state.mark(key)
            parts.append(empty)
            processed += 1
            if args.log_every > 0 and (processed % int(args.log_every) == 0):
                print(
                    f"[earnings][{year}] status=pre_nse_history rows=0 "
                    f"cumulative_rows={cumulative_rows} processed={processed}/{len(years)}"
                )
            continue

        records_all: list[dict] = []
        seen_keys: set[str] = set()
        consecutive_failures = 0

        windows = _quarter_windows(year)
        if int(args.max_quarters) > 0:
            remaining = int(args.max_quarters) - queried_quarters
            if remaining <= 0:
                print(f"[earnings][{year}] status=probe_limit_reached max_quarters={args.max_quarters}")
                break
            windows = windows[:remaining]

        for qnum, qstart, qend in windows:
            if int(args.max_quarters) > 0 and queried_quarters >= int(args.max_quarters):
                break

            queried_quarters += 1
            if args.page_log_every > 0 and (
                queried_quarters % int(args.page_log_every) == 0 or qnum == 1
            ):
                print(
                    f"[earnings][{year}Q{qnum}] query_start "
                    f"from={_fmt_nse_date(qstart)} to={_fmt_nse_date(qend)}"
                )

            rows_this_quarter = 0

            # Primary endpoint requested by strategy design:
            # /api/corporates-corporateActions with purpose=Financial Results
            actions_params = {
                "index": "equities",
                "from_date": _fmt_nse_date(qstart),
                "to_date": _fmt_nse_date(qend),
                "industryType": "allIndustries",
                "purpose": "Financial Results",
            }
            payload_actions, ok_actions = _safe_get_json(
                session,
                NSE_CORP_ACTIONS_URL,
                actions_params,
                retries=int(args.max_retries),
                request_timeout=int(args.request_timeout),
                context=f"[{year}Q{qnum}|corporateActions]",
            )
            if not ok_actions:
                consecutive_failures += 1
                print(
                    f"[earnings][{year}Q{qnum}|corporateActions] status=request_failed "
                    f"consecutive_failures={consecutive_failures}"
                )
            else:
                consecutive_failures = 0
                for rec in payload_actions:
                    key_rec = "|".join(
                        [
                            str(rec.get("symbol") or ""),
                            str(rec.get("caBroadcastDate") or rec.get("bcStartDate") or ""),
                            str(rec.get("subject") or ""),
                            str(rec.get("exDate") or ""),
                        ]
                    )
                    if key_rec in seen_keys:
                        continue
                    seen_keys.add(key_rec)
                    records_all.append(rec)
                    rows_this_quarter += 1
                if args.page_log_every > 0 and (
                    queried_quarters % int(args.page_log_every) == 0 or qnum == 1
                ):
                    print(
                        f"[earnings][{year}Q{qnum}|corporateActions] status=ok rows={len(payload_actions)} "
                        f"kept={rows_this_quarter} cumulative_rows={len(records_all)}"
                    )

            # NSE corporateActions currently returns sparse/empty rows for financial results
            # on some windows; fallback to corporates-financial-results to avoid history gaps.
            if rows_this_quarter == 0:
                periods = ["Quarterly", "Half-Yearly", "Annual"]
                for period in periods:
                    params = {
                        "index": "equities",
                        "period": period,
                        "from_date": _fmt_nse_date(qstart),
                        "to_date": _fmt_nse_date(qend),
                    }
                    payload, ok = _safe_get_json(
                        session,
                        NSE_FIN_RESULTS_URL,
                        params,
                        retries=int(args.max_retries),
                        request_timeout=int(args.request_timeout),
                        context=f"[{year}Q{qnum}|{period}]",
                    )
                    if not ok:
                        consecutive_failures += 1
                        print(
                            f"[earnings][{year}Q{qnum}|{period}] status=request_failed "
                            f"consecutive_failures={consecutive_failures}"
                        )
                        if consecutive_failures >= int(args.max_consecutive_page_failures):
                            print(
                                f"[earnings][{year}] stopping early due to consecutive failures "
                                f"(>={args.max_consecutive_page_failures})"
                            )
                            break
                        continue

                    consecutive_failures = 0
                    for rec in payload:
                        key_rec = str(rec.get("seqNumber") or "")
                        if not key_rec:
                            key_rec = "|".join(
                                [
                                    str(rec.get("symbol") or ""),
                                    str(rec.get("broadCastDate") or rec.get("filingDate") or ""),
                                    str(rec.get("relatingTo") or ""),
                                    str(rec.get("consolidated") or ""),
                                ]
                            )
                        if key_rec in seen_keys:
                            continue
                        seen_keys.add(key_rec)
                        records_all.append(rec)
                        rows_this_quarter += 1

                    if args.page_log_every > 0 and (
                        queried_quarters % int(args.page_log_every) == 0 or qnum == 1
                    ):
                        print(
                            f"[earnings][{year}Q{qnum}|{period}] status=ok rows={len(payload)} "
                            f"kept={rows_this_quarter} cumulative_rows={len(records_all)}"
                        )
                    time.sleep(0.1)

            if consecutive_failures >= int(args.max_consecutive_page_failures):
                break

            time.sleep(random.uniform(args.delay_min, args.delay_max))

        df = _to_frame(records_all)
        df.to_csv(out_file, index=False)

        state.mark(key)
        parts.append(df)
        processed += 1
        yr_rows = int(len(df))
        cumulative_rows += yr_rows
        status = "ingested" if yr_rows > 0 else "empty"
        if args.log_every > 0 and (processed % int(args.log_every) == 0):
            print(
                f"[earnings][{year}] status={status} rows={yr_rows} "
                f"cumulative_rows={cumulative_rows} processed={processed}/{len(years)}"
            )

        if int(args.max_quarters) > 0 and queried_quarters >= int(args.max_quarters):
            break

    all_df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    proc = Path("data/processed/alternative/earnings_dates_all.csv")
    proc.parent.mkdir(parents=True, exist_ok=True)
    if not all_df.empty:
        all_df["announcement_date"] = pd.to_datetime(all_df["announcement_date"], errors="coerce")
        all_df["ex_date"] = pd.to_datetime(all_df.get("ex_date"), errors="coerce")
        all_df = all_df.sort_values(["announcement_date", "nse_ticker"], kind="mergesort")
    all_df.to_csv(proc, index=False)

    print(
        f"[earnings] completed: {int(len(all_df))} announcements, "
        f"{int(all_df['nse_ticker'].nunique()) if not all_df.empty and 'nse_ticker' in all_df.columns else 0} tickers covered"
    )
    print(
        f"[earnings] ingestion_summary: reused_years={reused}, processed_years={processed}, "
        f"queried_quarters={queried_quarters}, cumulative_rows={cumulative_rows}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
