"""Unified news-sentiment ingestion and feature build pipeline for Northstar v3."""

from __future__ import annotations

import json
import random
import re
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import date
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd
import requests
from pandas.tseries.offsets import BDay

try:
    from scripts.utils.progress_resume import Progress, ResumeState
except ModuleNotFoundError:  # pragma: no cover
    from utils.progress_resume import Progress, ResumeState


GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

GDELT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/javascript, */*",
}

RSS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
}

DEFAULT_KEYWORDS = {
    "earnings": ["earnings", "quarterly", "q1", "q2", "q3", "q4", "results", "guidance"],
    "mna": ["acquisition", "merger", "demerger", "takeover", "buyout"],
    "capex": ["capex", "capacity expansion", "plant", "manufacturing", "greenfield"],
    "orders": ["order win", "contract", "deal won", "order received", "tender"],
    "governance": ["pledge", "resign", "appointment", "independent director", "audit"],
    "distress": ["default", "downgrade", "bankruptcy", "insolvency", "nclt", "watch negative"],
    "regulatory": ["sebi", "rbi", "gst", "penalty", "compliance", "investigation"],
}

POSITIVE_WORDS = {
    "beat",
    "growth",
    "upgrade",
    "strong",
    "surge",
    "profit",
    "record",
    "win",
    "order",
    "expansion",
    "approval",
    "positive",
    "awarded",
    "received",
    "rise",
    "higher",
    "improved",
    "outperform",
    "buyback",
    "dividend",
    "contract",
    "guidance",
}
NEGATIVE_WORDS = {
    "miss",
    "fall",
    "downgrade",
    "weak",
    "loss",
    "default",
    "fraud",
    "penalty",
    "warning",
    "negative",
    "decline",
    "cut",
    "defaulted",
    "insolvency",
    "nclt",
    "resign",
    "resignation",
    "investigation",
    "watch",
    "delay",
    "lower",
    "weaker",
    "fraudulent",
    "suspend",
}


@dataclass(frozen=True)
class GdeltTask:
    ticker: str
    company: str
    year: int
    month: int

    @property
    def key(self) -> str:
        return f"{self.ticker}|{self.year:04d}-{self.month:02d}"

    @property
    def month_file(self) -> str:
        return f"gdelt_{self.year:04d}_{self.month:02d}.jsonl"

    @property
    def start_dt(self) -> pd.Timestamp:
        return pd.Timestamp(year=self.year, month=self.month, day=1)

    @property
    def end_dt(self) -> pd.Timestamp:
        return self.start_dt + pd.offsets.MonthEnd(0)


class NewsSentimentBuilder:
    """
    Build a consolidated news dataset and derived sentiment features.

    Outputs:
    - data/processed/news/news_dataset.parquet
    - data/processed/sentiment/ticker_sentiment_daily.parquet
    - data/processed/sentiment/market_sentiment_daily.parquet
    - data/processed/sentiment/top_bottom_weekly.parquet
    """

    NEWS_KEY_COLUMNS = ["date", "ticker", "headline", "url", "source_type"]

    def __init__(
        self,
        *,
        universe_path: str = "universe/nifty500.csv",
        raw_dir: str = "data/raw/news_sentiment",
        processed_news_dir: str = "data/processed/news",
        processed_sentiment_dir: str = "data/processed/sentiment",
        legacy_news_path: str = "data/processed/news/legacy_news_clean.parquet",
        random_seed: int = 7,
    ):
        self.universe_path = Path(universe_path)
        self.raw_dir = Path(raw_dir)
        self.processed_news_dir = Path(processed_news_dir)
        self.processed_sentiment_dir = Path(processed_sentiment_dir)
        self.legacy_news_path = Path(legacy_news_path)
        self.rng = random.Random(int(random_seed))

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.processed_news_dir.mkdir(parents=True, exist_ok=True)
        self.processed_sentiment_dir.mkdir(parents=True, exist_ok=True)

        self.gdelt_dir = self.raw_dir / "gdelt"
        self.rss_dir = self.raw_dir / "rss"
        self.exchange_dir = self.raw_dir / "nse"
        # Backward-compatible alias for older code paths that still reference bse_dir.
        self.bse_dir = self.exchange_dir
        self.gdelt_dir.mkdir(parents=True, exist_ok=True)
        self.rss_dir.mkdir(parents=True, exist_ok=True)
        self.exchange_dir.mkdir(parents=True, exist_ok=True)

        # GDELT public endpoint enforces low request frequency.
        self._gdelt_rate_lock = threading.Lock()
        self._gdelt_next_request_ts = 0.0

        self._universe = self._load_universe()

    @staticmethod
    def _normalize_ticker(value: object) -> str:
        s = str(value or "").strip().upper()
        if not s:
            return ""
        if s.endswith(".NS"):
            return s
        if "." in s:
            s = s.split(".", 1)[0]
        return f"{s}.NS"

    @staticmethod
    def _normalize_text(value: object) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip())

    @staticmethod
    def _canonicalize_source_type(value: object) -> str:
        normalized = re.sub(r"\s+", "_", str(value or "").strip().lower())
        if normalized == "bse_announcements":
            return "nse_announcements"
        return normalized

    def _load_universe(self) -> pd.DataFrame:
        if not self.universe_path.exists():
            return pd.DataFrame(columns=["ticker", "company"])
        try:
            df = pd.read_csv(self.universe_path)
        except Exception:
            return pd.DataFrame(columns=["ticker", "company"])

        company_col = "Company Name" if "Company Name" in df.columns else "company"
        symbol_col = "Symbol" if "Symbol" in df.columns else "ticker"
        if company_col not in df.columns or symbol_col not in df.columns:
            return pd.DataFrame(columns=["ticker", "company"])

        out = pd.DataFrame(
            {
                "ticker": df[symbol_col].map(self._normalize_ticker),
                "company": df[company_col].map(self._normalize_text),
            }
        )
        out = out[(out["ticker"] != "") & (out["company"] != "")]
        out = out.drop_duplicates(subset=["ticker"], keep="first").reset_index(drop=True)
        return out

    @staticmethod
    def _month_range(start_year: int, end_year: int) -> list[tuple[int, int]]:
        months: list[tuple[int, int]] = []
        today = pd.Timestamp.today().normalize()
        for y in range(int(start_year), int(end_year) + 1):
            for m in range(1, 13):
                dt = pd.Timestamp(year=y, month=m, day=1)
                if dt > today:
                    break
                months.append((y, m))
        return months

    @staticmethod
    def _append_jsonl(path: Path, rows: list[dict]) -> None:
        if not rows:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=True) + "\n")

    @staticmethod
    def _read_jsonl(path: Path) -> pd.DataFrame:
        if not path.exists() or path.stat().st_size == 0:
            return pd.DataFrame()
        rows: list[dict] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
        return pd.DataFrame(rows)

    def _load_all_jsonl(self, folder: Path, pattern: str = "*.jsonl") -> pd.DataFrame:
        parts: list[pd.DataFrame] = []
        for p in sorted(folder.glob(pattern)):
            df = self._read_jsonl(p)
            if not df.empty:
                parts.append(df)
        return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

    @staticmethod
    def _gdelt_datetime(ts: pd.Timestamp, end_of_day: bool = False) -> str:
        base = pd.Timestamp(ts)
        if end_of_day:
            base = base.replace(hour=23, minute=59, second=59)
        else:
            base = base.replace(hour=0, minute=0, second=0)
        return base.strftime("%Y%m%d%H%M%S")

    def _gdelt_wait_for_slot(self, min_interval_sec: float) -> None:
        """Global request pacing across workers to avoid 429 floods."""
        wait = 0.0
        with self._gdelt_rate_lock:
            now = time.monotonic()
            wait = max(0.0, float(self._gdelt_next_request_ts) - now)
            self._gdelt_next_request_ts = max(now, self._gdelt_next_request_ts) + float(min_interval_sec)
        if wait > 0.0:
            time.sleep(wait)

    def _fetch_gdelt_task(
        self,
        task: GdeltTask,
        *,
        max_records: int,
        retries: int,
        timeout: int,
        delay_min: float,
        delay_max: float,
        min_interval_sec: float,
    ) -> dict:
        query = f"\"{task.company}\""
        params = {
            "query": query,
            "mode": "ArtList",
            "maxrecords": str(int(max_records)),
            "format": "json",
            "sort": "DateAsc",
            "startdatetime": self._gdelt_datetime(task.start_dt, end_of_day=False),
            "enddatetime": self._gdelt_datetime(task.end_dt, end_of_day=True),
        }

        backoff = 1.0
        last_error = ""
        last_status = 0
        for _ in range(max(1, int(retries))):
            try:
                self._gdelt_wait_for_slot(min_interval_sec=float(min_interval_sec))
                r = requests.get(GDELT_URL, params=params, headers=GDELT_HEADERS, timeout=int(timeout))
                last_status = int(r.status_code)
                if r.status_code in {403, 429}:
                    last_error = f"http_{r.status_code}"
                    # Respect public endpoint throttle guidance.
                    throttle_sleep = max(float(min_interval_sec), backoff)
                    time.sleep(throttle_sleep)
                    backoff = min(backoff * 2.0, 20.0)
                    continue
                r.raise_for_status()
                payload = r.json()
                articles = payload.get("articles", []) if isinstance(payload, dict) else []
                rows: list[dict] = []
                for a in articles:
                    if not isinstance(a, dict):
                        continue
                    seendate = str(a.get("seendate") or "").strip()
                    dt = pd.to_datetime(seendate, errors="coerce")
                    if pd.isna(dt):
                        dt = pd.to_datetime(a.get("socialimage", ""), errors="coerce")
                    if pd.isna(dt):
                        dt = task.start_dt
                    title = self._normalize_text(a.get("title"))
                    if not title:
                        continue
                    rows.append(
                        {
                            "date": pd.Timestamp(dt).normalize().strftime("%Y-%m-%d"),
                            "company": task.company,
                            "ticker": task.ticker,
                            "headline": title,
                            "summary": self._normalize_text(a.get("snippet", "")),
                            "url": self._normalize_text(a.get("url", "")),
                            "source": self._normalize_text(a.get("domain", "gdelt")),
                            "source_type": "gdelt",
                        }
                    )
                time.sleep(self.rng.uniform(float(delay_min), float(delay_max)))
                return {
                    "rows": rows,
                    "status": ("ok" if rows else "empty"),
                    "http_status": int(last_status),
                    "error": "",
                }
            except Exception as exc:
                last_error = type(exc).__name__
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 20.0)
        return {
            "rows": [],
            "status": "failed",
            "http_status": int(last_status),
            "error": last_error or "unknown",
        }

    def collect_gdelt(
        self,
        *,
        start_year: int,
        end_year: int,
        resume: bool = True,
        workers: int = 4,
        max_records: int = 250,
        retries: int = 3,
        timeout: int = 30,
        delay_min: float = 0.2,
        delay_max: float = 0.8,
        log_every: int = 100,
        max_tickers: int = 0,
        max_months: int = 0,
        min_interval_sec: float = 5.2,
    ) -> pd.DataFrame:
        state = ResumeState(self.gdelt_dir / ".resume_state.json")
        universe = self._universe.copy()
        if int(max_tickers) > 0:
            universe = universe.head(int(max_tickers)).copy()

        months = self._month_range(start_year, end_year)
        if int(max_months) > 0:
            months = months[: int(max_months)]

        tasks: list[GdeltTask] = []
        for _, row in universe.iterrows():
            for y, m in months:
                tasks.append(GdeltTask(ticker=str(row["ticker"]), company=str(row["company"]), year=y, month=m))

        pending = [t for t in tasks if not (resume and state.has(t.key))]
        print(f"[news][gdelt] resume_scan total={len(tasks)} reused={len(tasks)-len(pending)} pending={len(pending)}")
        if pending:
            est_secs = float(len(pending)) * float(max(min_interval_sec, 0.1))
            est_hours = est_secs / 3600.0
            print(
                f"[news][gdelt] pacing min_interval={float(min_interval_sec):.2f}s "
                f"workers={max(1, int(workers))} est_min_runtime={est_hours:.1f}h "
                "(public GDELT throttle-safe mode)"
            )
        if not pending:
            return self._load_all_jsonl(self.gdelt_dir, pattern="gdelt_*.jsonl")

        done = 0
        non_empty = 0
        total_rows = 0
        empty = 0
        failed = 0
        rate_limited = 0
        status_counts: dict[str, int] = {"ok": 0, "empty": 0, "failed": 0}
        http_counts: dict[int, int] = {}
        started = time.monotonic()

        def _submit_task(executor: ThreadPoolExecutor, t: GdeltTask) -> Future:
            return executor.submit(
                self._fetch_gdelt_task,
                t,
                max_records=max_records,
                retries=retries,
                timeout=timeout,
                delay_min=delay_min,
                delay_max=delay_max,
                min_interval_sec=min_interval_sec,
            )

        max_workers = max(1, int(workers))
        inflight_cap = max(4, max_workers * 4)
        pending_iter = iter(pending)

        with Progress(total=len(pending), desc="news_gdelt", unit="task") as p:
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                fut_to_task: dict[Future, GdeltTask] = {}
                for _ in range(min(inflight_cap, len(pending))):
                    try:
                        t = next(pending_iter)
                    except StopIteration:
                        break
                    fut_to_task[_submit_task(ex, t)] = t

                while fut_to_task:
                    done_futs, _ = wait(fut_to_task.keys(), return_when=FIRST_COMPLETED)
                    for fut in done_futs:
                        task = fut_to_task.pop(fut)
                        try:
                            payload = fut.result()
                        except Exception:
                            payload = {"rows": [], "status": "failed", "http_status": 0, "error": "future_error"}

                        rows = payload.get("rows", []) if isinstance(payload, dict) else []
                        status = str(payload.get("status", "failed")) if isinstance(payload, dict) else "failed"
                        http_status = int(payload.get("http_status", 0)) if isinstance(payload, dict) else 0
                        status_counts[status] = int(status_counts.get(status, 0)) + 1
                        if http_status > 0:
                            http_counts[http_status] = int(http_counts.get(http_status, 0)) + 1
                            if http_status == 429:
                                rate_limited += 1

                        out_file = self.gdelt_dir / task.month_file
                        self._append_jsonl(out_file, rows)
                        state.mark(task.key)
                        done += 1
                        total_rows += int(len(rows))
                        if status == "failed":
                            failed += 1
                        elif rows:
                            non_empty += 1
                        else:
                            empty += 1
                        if int(log_every) > 0 and (done % int(log_every) == 0):
                            elapsed = max(1e-6, time.monotonic() - started)
                            tps = float(done) / elapsed
                            eta_secs = float(len(pending) - done) / max(tps, 1e-9)
                            eta_min = eta_secs / 60.0
                            http_top = sorted(http_counts.items(), key=lambda kv: kv[1], reverse=True)[:3]
                            print(
                                f"[news][gdelt] processed={done}/{len(pending)} rows={total_rows} "
                                f"non_empty={non_empty} empty={empty} failed={failed} "
                                f"rate_limited={rate_limited} tps={tps:.2f} eta_min={eta_min:.1f} "
                                f"status={status_counts} http_top={http_top} "
                                f"last_rows={len(rows)} task={task.ticker}|{task.year:04d}-{task.month:02d}"
                            )
                        p.update(1)

                        try:
                            next_task = next(pending_iter)
                        except StopIteration:
                            next_task = None
                        if next_task is not None:
                            fut_to_task[_submit_task(ex, next_task)] = next_task

        df = self._load_all_jsonl(self.gdelt_dir, pattern="gdelt_*.jsonl")
        elapsed = max(1e-6, time.monotonic() - started)
        rate = float(done) / elapsed
        print(
            f"[news][gdelt] completed files={len(list(self.gdelt_dir.glob('gdelt_*.jsonl')))} "
            f"rows={len(df)} tickers={df['ticker'].nunique() if not df.empty and 'ticker' in df.columns else 0} "
            f"done={done} non_empty={non_empty} empty={empty} failed={failed} "
            f"rate_limited={rate_limited} avg_tps={rate:.2f} status={status_counts}"
        )
        if len(df) == 0 and rate_limited > 0:
            print(
                "[news][gdelt] warning: high rate-limit pressure and zero rows so far. "
                "Use --sources nse,rss for immediate completion, or run gdelt alone overnight."
            )
        return df

    def collect_rss(
        self,
        *,
        resume: bool = True,
        lookback_days: int = 30,
        timeout: int = 30,
        retries: int = 3,
        delay_min: float = 0.2,
        delay_max: float = 0.6,
        log_every: int = 50,
        max_tickers: int = 0,
    ) -> pd.DataFrame:
        state = ResumeState(self.rss_dir / ".resume_state.json")
        universe = self._universe.copy()
        if int(max_tickers) > 0:
            universe = universe.head(int(max_tickers)).copy()
        run_tag = pd.Timestamp.today().strftime("%Y%m%d")
        out_file = self.rss_dir / f"rss_{run_tag}.jsonl"

        pending = []
        for _, row in universe.iterrows():
            key = f"{run_tag}|{row['ticker']}"
            if resume and state.has(key):
                continue
            pending.append((key, str(row["ticker"]), str(row["company"])))
        print(f"[news][rss] resume_scan total={len(universe)} pending={len(pending)}")

        cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=max(1, int(lookback_days)))
        done = 0
        total_rows = 0
        non_empty = 0
        with Progress(total=len(pending), desc="news_rss", unit="ticker") as p:
            for key, ticker, company in pending:
                rows: list[dict] = []
                q = quote_plus(f"{company} {ticker.replace('.NS', '')} NSE")
                url = f"https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
                backoff = 1.0
                payload_text = ""
                for _ in range(max(1, int(retries))):
                    try:
                        r = requests.get(url, headers=RSS_HEADERS, timeout=int(timeout))
                        if r.status_code in {403, 429}:
                            time.sleep(backoff)
                            backoff = min(backoff * 2.0, 20.0)
                            continue
                        r.raise_for_status()
                        payload_text = r.text
                        break
                    except Exception:
                        time.sleep(backoff)
                        backoff = min(backoff * 2.0, 20.0)

                if payload_text:
                    try:
                        root = ET.fromstring(payload_text)
                        for item in root.findall(".//item"):
                            title = self._normalize_text(item.findtext("title", default=""))
                            link = self._normalize_text(item.findtext("link", default=""))
                            pub = self._normalize_text(item.findtext("pubDate", default=""))
                            src = self._normalize_text(item.findtext("source", default="google_news"))
                            desc = self._normalize_text(item.findtext("description", default=""))
                            try:
                                dt = pd.Timestamp(parsedate_to_datetime(pub)).tz_localize(None).normalize()
                            except Exception:
                                dt = pd.NaT
                            if pd.isna(dt) or dt < cutoff:
                                continue
                            if not title:
                                continue
                            rows.append(
                                {
                                    "date": dt.strftime("%Y-%m-%d"),
                                    "company": company,
                                    "ticker": ticker,
                                    "headline": title,
                                    "summary": desc,
                                    "url": link,
                                    "source": src or "google_news",
                                    "source_type": "rss",
                                }
                            )
                    except Exception:
                        rows = []

                self._append_jsonl(out_file, rows)
                state.mark(key)
                done += 1
                total_rows += int(len(rows))
                if rows:
                    non_empty += 1
                if int(log_every) > 0 and (done % int(log_every) == 0):
                    print(
                        f"[news][rss] processed={done}/{len(pending)} non_empty={non_empty} "
                        f"rows={total_rows} last={len(rows)} ticker={ticker}"
                    )
                p.update(1)
                time.sleep(self.rng.uniform(float(delay_min), float(delay_max)))

        df = self._load_all_jsonl(self.rss_dir, pattern="rss_*.jsonl")
        print(
            f"[news][rss] completed files={len(list(self.rss_dir.glob('rss_*.jsonl')))} "
            f"rows={len(df)} tickers={df['ticker'].nunique() if not df.empty and 'ticker' in df.columns else 0}"
        )
        return df

    def collect_bse_events(
        self,
        *,
        include_bulk_deals: bool = False,
    ) -> pd.DataFrame:
        parts: list[pd.DataFrame] = []

        def _read_alt_frame(*candidates: str) -> pd.DataFrame:
            for candidate in candidates:
                path = Path(candidate)
                if not path.exists():
                    continue
                try:
                    if path.suffix.lower() == ".parquet":
                        return pd.read_parquet(path)
                    return pd.read_csv(path)
                except Exception:
                    continue
            return pd.DataFrame()

        ann = _read_alt_frame(
            "data/processed/alternative/announcements_all.parquet",
            "data/processed/alternative/announcements_all.csv",
        )
        if not ann.empty:
            a = pd.DataFrame()
            a["date"] = pd.to_datetime(ann.get("date"), errors="coerce").dt.normalize()
            a["company"] = ann.get("company_name", "").astype(str)
            a["ticker"] = ann.get("nse_ticker", "").map(self._normalize_ticker)
            a["headline"] = ann.get("headline", "").astype(str)
            a["summary"] = ann.get("announcement_text", "").astype(str)
            a["url"] = ""
            a["source"] = "nse"
            a["source_type"] = "nse_announcements"
            a = a.dropna(subset=["date"])
            parts.append(a)

        earn_path = Path("data/processed/alternative/earnings_dates_all.csv")
        if earn_path.exists():
            try:
                earn = pd.read_csv(earn_path)
            except Exception:
                earn = pd.DataFrame()
            if not earn.empty:
                e = pd.DataFrame()
                e["date"] = pd.to_datetime(earn.get("announcement_date"), errors="coerce").dt.normalize()
                e["company"] = earn.get("company_name", "").astype(str)
                e["ticker"] = earn.get("nse_ticker", "").map(self._normalize_ticker)
                period = earn.get("purpose", "").astype(str)
                e["headline"] = ("Financial Results: " + period).str.strip()
                e["summary"] = period
                e["url"] = ""
                e["source"] = "nse"
                e["source_type"] = "nse_financial_results"
                e = e.dropna(subset=["date"])
                parts.append(e)

        rat = _read_alt_frame(
            "data/processed/alternative/credit_ratings_nse_all.parquet",
            "data/processed/alternative/credit_ratings_nse_all.csv",
            "data/processed/alternative/credit_ratings_all.csv",
        )
        if not rat.empty:
            r = pd.DataFrame()
            r["date"] = pd.to_datetime(
                rat.get("date", rat.get("DATE OF CREDIT RATING")), errors="coerce"
            ).dt.normalize()
            r["company"] = rat.get("company_name", "").astype(str)
            r["ticker"] = rat.get("nse_ticker", rat.get("ticker", "")).map(self._normalize_ticker)
            r["headline"] = (
                rat.get("agency", "").astype(str)
                + " "
                + rat.get("action_type", rat.get("rating_action", "")).astype(str)
                + " "
                + rat.get("new_rating", rat.get("rating", "")).astype(str)
            ).str.strip()
            r["summary"] = rat.get("instrument_type", "").astype(str)
            r["url"] = ""
            r["source"] = rat.get("agency", "ratings").astype(str).str.lower()
            r["source_type"] = "credit_ratings"
            r = r.dropna(subset=["date"])
            parts.append(r)

        if include_bulk_deals:
            bulk = _read_alt_frame(
                "data/processed/alternative/bulk_deals_nse_all.parquet",
                "data/processed/alternative/bulk_deals_nse_all.csv",
                "data/processed/alternative/bulk_deals_all.csv",
            )
            if not bulk.empty:
                b = pd.DataFrame()
                b["date"] = pd.to_datetime(bulk.get("date"), errors="coerce").dt.normalize()
                b["company"] = bulk.get("company_name", bulk.get("scrip_name", "")).astype(str)
                b["ticker"] = bulk.get("nse_ticker", "").map(self._normalize_ticker)
                b["headline"] = (
                    "Bulk "
                    + bulk.get("deal_type", "").astype(str)
                    + " by "
                    + bulk.get("client_name", "").astype(str)
                ).str.strip()
                b["summary"] = (
                    "Qty="
                    + bulk.get("quantity", "").astype(str)
                    + " Price="
                    + bulk.get("price", "").astype(str)
                )
                b["url"] = ""
                b["source"] = "nse"
                b["source_type"] = "bulk_deals"
                b = b.dropna(subset=["date"])
                parts.append(b)

        out = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
        if out.empty:
            out = pd.DataFrame(
                columns=[
                    "date",
                    "company",
                    "ticker",
                    "headline",
                    "summary",
                    "url",
                    "source",
                    "source_type",
                ]
            )
        else:
            out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
            out["company"] = out["company"].map(self._normalize_text)
            out["ticker"] = out["ticker"].map(self._normalize_ticker)
            out["headline"] = out["headline"].map(self._normalize_text)
            out["summary"] = out["summary"].map(self._normalize_text)
            out["url"] = out["url"].map(self._normalize_text)
            out["source"] = out["source"].map(self._normalize_text).str.lower()
            out["source_type"] = out["source_type"].map(self._normalize_text).map(self._canonicalize_source_type)
            out = out.dropna(subset=["date"])
            out = out[out["headline"] != ""].copy()
            out = out.drop_duplicates(subset=["date", "ticker", "headline", "source_type"], keep="last")
            out = out.sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)

        out_path = self.exchange_dir / "nse_events.csv"
        out.to_csv(out_path, index=False)
        print(
            f"[news][nse] completed rows={len(out)} tickers={out['ticker'].nunique() if not out.empty else 0} "
            f"path={out_path}"
        )
        return out

    def collect_legacy_news(self) -> pd.DataFrame:
        """Load cleaned legacy news if available."""
        path = self.legacy_news_path
        if not path.exists():
            return pd.DataFrame()
        try:
            df = pd.read_parquet(path) if path.suffix.lower() == ".parquet" else pd.read_csv(path)
        except Exception:
            return pd.DataFrame()
        if df.empty:
            return pd.DataFrame()

        out = pd.DataFrame()
        out["date"] = pd.to_datetime(df.get("date"), errors="coerce").dt.normalize()
        out["company"] = df.get("company", "").astype(str)
        out["ticker"] = df.get("ticker", "").map(self._normalize_ticker)
        out["headline"] = df.get("headline", "").astype(str)
        out["summary"] = df.get("summary", "").astype(str)
        out["url"] = df.get("url", "").astype(str)
        out["source"] = df.get("source", "legacy").astype(str)
        out["source_type"] = "legacy_csv"
        out = out.dropna(subset=["date"])
        out = out[out["headline"].astype(str).str.len() > 0]
        out = out.drop_duplicates(subset=["date", "ticker", "headline", "url", "source_type"], keep="last")
        out = out.sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)
        print(
            f"[news][legacy] completed rows={len(out)} tickers={out['ticker'].nunique() if not out.empty else 0} "
            f"path={path}"
        )
        return out

    @staticmethod
    def _extract_keywords(text: str) -> str:
        s = str(text or "").lower()
        found: list[str] = []
        for label, words in DEFAULT_KEYWORDS.items():
            for w in words:
                if w in s:
                    found.append(label)
                    break
        return ",".join(sorted(set(found)))

    @staticmethod
    def _score_lexicon(headlines: pd.Series) -> tuple[pd.Series, pd.Series]:
        polarity = []
        conviction = []
        for h in headlines.fillna("").astype(str):
            tokens = re.findall(r"[a-zA-Z]+", h.lower())
            if not tokens:
                polarity.append(0.0)
                conviction.append(0.0)
                continue
            pos = sum(1 for t in tokens if t in POSITIVE_WORDS)
            neg = sum(1 for t in tokens if t in NEGATIVE_WORDS)
            score = float(pos - neg) / float(max(1, len(tokens) ** 0.5))
            score = float(np.clip(score, -1.0, 1.0))
            polarity.append(score)
            conviction.append(float(np.clip(abs(score), 0.0, 1.0)))
        return pd.Series(polarity, dtype=float), pd.Series(conviction, dtype=float)

    @staticmethod
    def _event_prior(source_type: object, text: object) -> float:
        s_type = str(source_type or "").strip().lower()
        txt = str(text or "").strip().lower()
        score = 0.0

        if "bulk_deals" in s_type:
            if "bulk buy" in txt or " deal_type=buy" in txt or " buy " in f" {txt} ":
                score += 0.30
            if "bulk sell" in txt or " deal_type=sell" in txt or " sell " in f" {txt} ":
                score -= 0.30

        if "credit_ratings" in s_type:
            if "downgrade" in txt or "default" in txt or "watch negative" in txt:
                score -= 0.70
            if "upgrade" in txt or "watch positive" in txt:
                score += 0.55

        if "nse_financial_results" in s_type:
            # Keep earnings structured events near-neutral unless explicit guidance words are present.
            if "beat" in txt or "record profit" in txt:
                score += 0.25
            if "miss" in txt or "loss" in txt:
                score -= 0.25

        # Generic event priors for BSE/NSE corp events.
        if any(k in txt for k in ["order", "contract", "capacity expansion", "plant", "acquisition", "merger"]):
            score += 0.20
        if any(k in txt for k in ["pledge", "penalty", "default", "fraud", "investigation", "insolvency", "nclt"]):
            score -= 0.35

        return float(np.clip(score, -1.0, 1.0))

    def _score_finbert(
        self,
        headlines: pd.Series,
        *,
        batch_size: int = 32,
    ) -> tuple[pd.Series, pd.Series]:
        try:
            from transformers import pipeline  # type: ignore
        except Exception:
            return self._score_lexicon(headlines)

        texts = headlines.fillna("").astype(str).tolist()
        if not texts:
            return pd.Series(dtype=float), pd.Series(dtype=float)

        model = pipeline("sentiment-analysis", model="ProsusAI/finbert", tokenizer="ProsusAI/finbert")
        pol: list[float] = []
        conv: list[float] = []
        with Progress(total=len(texts), desc="sentiment_score", unit="headline") as p:
            for i in range(0, len(texts), max(1, int(batch_size))):
                chunk = texts[i : i + max(1, int(batch_size))]
                try:
                    out = model(chunk, truncation=True)
                except Exception:
                    out = [{"label": "neutral", "score": 0.0} for _ in chunk]
                for row in out:
                    label = str(row.get("label", "neutral")).strip().lower()
                    score = float(row.get("score", 0.0) or 0.0)
                    if "positive" in label:
                        signed = score
                    elif "negative" in label:
                        signed = -score
                    else:
                        signed = 0.0
                    pol.append(float(np.clip(signed, -1.0, 1.0)))
                    conv.append(float(np.clip(abs(signed), 0.0, 1.0)))
                p.update(len(chunk))
        return pd.Series(pol, dtype=float), pd.Series(conv, dtype=float)

    def score_sentiment(
        self,
        df: pd.DataFrame,
        *,
        model: str = "auto",
        finbert_batch_size: int = 32,
    ) -> pd.DataFrame:
        if df.empty:
            return df.copy()
        # Scoring helpers return fresh RangeIndex series; keep the working frame on the
        # same index so boolean masks and aligned assignments remain valid in resume mode.
        out = df.copy().reset_index(drop=True)
        out["headline"] = out["headline"].map(self._normalize_text)
        out["summary"] = out.get("summary", "").map(self._normalize_text)
        out["keywords"] = (out["headline"].fillna("") + " " + out["summary"].fillna("")).map(self._extract_keywords)
        text_for_score = (out["headline"].fillna("") + " " + out["summary"].fillna("")).str.strip()

        use_finbert = str(model).strip().lower() in {"finbert", "auto"}
        if use_finbert:
            pol, conv = self._score_finbert(out["headline"], batch_size=finbert_batch_size)
        else:
            pol, conv = self._score_lexicon(text_for_score)

        event_prior = [
            self._event_prior(st, txt)
            for st, txt in zip(out.get("source_type", pd.Series(index=out.index, dtype=object)), text_for_score)
        ]
        event_prior_s = pd.Series(event_prior, index=out.index, dtype=float)
        event_prior_arr = event_prior_s.to_numpy(dtype=float, copy=False)

        # Rebuild scored outputs explicitly on the working frame index so incremental/resume
        # runs cannot hit pandas alignment errors when the scorer returns fresh RangeIndex series.
        base_pol = pd.Series(
            pd.to_numeric(pol, errors="coerce").to_numpy(),
            index=out.index,
            dtype=float,
        ).fillna(0.0).clip(-1.0, 1.0)
        combined_arr = base_pol.to_numpy(dtype=float, copy=True)
        neutral_mask = np.abs(combined_arr) < 1e-9
        combined_arr[neutral_mask] = event_prior_arr[neutral_mask]
        combined_arr[~neutral_mask] = (
            0.7 * combined_arr[~neutral_mask] + 0.3 * event_prior_arr[~neutral_mask]
        )

        out["sentiment"] = pd.Series(combined_arr, index=out.index, dtype=float).clip(-1.0, 1.0)
        base_conv = pd.Series(
            pd.to_numeric(conv, errors="coerce").to_numpy(),
            index=out.index,
            dtype=float,
        ).fillna(0.0).clip(0.0, 1.0)
        out["sentiment_conviction"] = np.maximum(base_conv.to_numpy(), np.abs(event_prior_arr) * 0.8)
        out["sentiment_conviction"] = pd.to_numeric(out["sentiment_conviction"], errors="coerce").fillna(0.0).clip(0.0, 1.0)
        out["sentiment_label"] = np.where(
            out["sentiment"] > 0.05,
            "positive",
            np.where(out["sentiment"] < -0.05, "negative", "neutral"),
        )
        out["ingested_at"] = pd.Timestamp.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        return out

    def combine_sources(self, frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
        valid = [f.copy() for f in frames if isinstance(f, pd.DataFrame) and not f.empty]
        if not valid:
            return pd.DataFrame(
                columns=["date", "company", "ticker", "headline", "summary", "url", "source", "source_type"]
            )
        out = pd.concat(valid, ignore_index=True, sort=False)
        out["date"] = pd.to_datetime(out.get("date"), errors="coerce").dt.normalize()
        out["company"] = out.get("company", "").map(self._normalize_text)
        out["ticker"] = out.get("ticker", "").map(self._normalize_ticker)
        out["headline"] = out.get("headline", "").map(self._normalize_text)
        out["summary"] = out.get("summary", "").map(self._normalize_text)
        out["url"] = out.get("url", "").map(self._normalize_text)
        out["source"] = out.get("source", "").map(self._normalize_text).str.lower()
        out["source_type"] = (
            out.get("source_type", "news")
            .map(self._normalize_text)
            .str.lower()
            .map(self._canonicalize_source_type)
        )
        source_fix_mask = out["source"].eq("bse") & out["source_type"].isin(["nse_announcements", "bulk_deals"])
        out.loc[source_fix_mask, "source"] = "nse"
        out = out.dropna(subset=["date"])
        out = out[out["headline"] != ""].copy()
        out = out.drop_duplicates(subset=["date", "ticker", "headline", "url", "source_type"], keep="last")
        out = out.sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)
        return out

    def _load_existing_scored_dataset(self) -> pd.DataFrame:
        news_parquet = self.processed_news_dir / "news_dataset.parquet"
        news_csv = self.processed_news_dir / "news_dataset.csv"
        existing = pd.DataFrame()

        if news_parquet.exists():
            try:
                existing = pd.read_parquet(news_parquet)
            except Exception:
                existing = pd.DataFrame()
        elif news_csv.exists():
            try:
                existing = pd.read_csv(news_csv)
            except Exception:
                existing = pd.DataFrame()

        if existing.empty:
            return existing

        for col in ["headline", "summary", "ticker", "url", "source_type", "source"]:
            if col not in existing.columns:
                existing[col] = ""

        existing["date"] = pd.to_datetime(existing.get("date"), errors="coerce").dt.normalize()
        existing["headline"] = existing["headline"].map(self._normalize_text)
        existing["summary"] = existing["summary"].map(self._normalize_text)
        existing["ticker"] = existing["ticker"].map(self._normalize_ticker)
        existing["url"] = existing["url"].map(self._normalize_text)
        existing["source_type"] = (
            existing["source_type"]
            .map(self._normalize_text)
            .str.lower()
            .map(self._canonicalize_source_type)
        )
        existing["source"] = existing["source"].map(self._normalize_text).str.lower()
        source_fix_mask = existing["source"].eq("bse") & existing["source_type"].isin(["nse_announcements", "bulk_deals"])
        existing.loc[source_fix_mask, "source"] = "nse"
        existing = existing.dropna(subset=["date"])
        existing = existing[existing["headline"] != ""].copy()
        existing = existing.drop_duplicates(subset=self.NEWS_KEY_COLUMNS, keep="last")
        existing = existing.sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)
        return existing

    def _build_processed_sentiment(self, scored: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        if scored.empty:
            empty_ticker = pd.DataFrame(
                columns=[
                    "ticker",
                    "date",
                    "availability_date",
                    "sentiment_polarity",
                    "sentiment_conviction",
                    "sentiment_surprise",
                    "sentiment_uncertainty",
                    "news_volume",
                    "source",
                ]
            )
            empty_market = pd.DataFrame(
                columns=[
                    "date",
                    "availability_date",
                    "india_market_polarity",
                    "india_market_conviction",
                    "india_market_uncertainty",
                    "global_risk_sentiment",
                    "news_volume_total",
                ]
            )
            empty_rank = pd.DataFrame(columns=["week", "rank_type", "rank", "ticker", "score"])
            return empty_ticker, empty_market, empty_rank

        work = scored.copy()
        work["date"] = pd.to_datetime(work["date"], errors="coerce").dt.normalize()
        work["ticker"] = work["ticker"].map(self._normalize_ticker)
        work["sentiment"] = pd.to_numeric(work.get("sentiment"), errors="coerce")
        work["sentiment_conviction"] = pd.to_numeric(work.get("sentiment_conviction"), errors="coerce")
        work = work.dropna(subset=["date", "ticker"])
        work = work[work["ticker"] != ""].copy()
        if work.empty:
            return self._build_processed_sentiment(pd.DataFrame())

        ticker_daily = (
            work.groupby(["ticker", "date"], as_index=False)
            .agg(
                sentiment_polarity=("sentiment", "mean"),
                sentiment_conviction=("sentiment_conviction", "mean"),
                news_volume=("headline", "count"),
                source=("source", "last"),
            )
            .sort_values(["ticker", "date"], kind="mergesort")
        )
        ticker_daily["sentiment_surprise"] = (
            ticker_daily.groupby("ticker", sort=False)["sentiment_polarity"]
            .transform(lambda x: (x - x.rolling(20, min_periods=5).mean()).abs())
            .fillna(0.0)
            .clip(0.0, 1.0)
        )
        ticker_daily["sentiment_uncertainty"] = (1.0 - ticker_daily["sentiment_conviction"]).clip(0.0, 1.0)
        ticker_daily["availability_date"] = ticker_daily["date"] + BDay(1)

        market_daily = (
            ticker_daily.groupby("date", as_index=False)
            .agg(
                india_market_polarity=("sentiment_polarity", "mean"),
                india_market_conviction=("sentiment_conviction", "mean"),
                india_market_uncertainty=("sentiment_uncertainty", "mean"),
                global_risk_sentiment=("sentiment_polarity", "mean"),
                news_volume_total=("news_volume", "sum"),
            )
            .sort_values("date", kind="mergesort")
        )
        market_daily["availability_date"] = market_daily["date"] + BDay(1)

        rank_base = ticker_daily.copy()
        rank_base["week"] = rank_base["date"] + pd.offsets.Week(weekday=4)
        rank_base["score"] = (
            pd.to_numeric(rank_base["sentiment_polarity"], errors="coerce").fillna(0.0)
            * pd.to_numeric(rank_base["sentiment_conviction"], errors="coerce").fillna(0.0)
            * np.log1p(pd.to_numeric(rank_base["news_volume"], errors="coerce").fillna(0.0))
        )
        rows_rank: list[dict] = []
        for wk, grp in rank_base.groupby("week", sort=True):
            g = grp.sort_values("score", ascending=False, kind="mergesort")
            top = g.head(30).copy()
            bot = g.tail(30).sort_values("score", ascending=True, kind="mergesort").copy()
            for i, (_, r) in enumerate(top.iterrows(), start=1):
                rows_rank.append(
                    {
                        "week": pd.Timestamp(wk).strftime("%Y-%m-%d"),
                        "rank_type": "top",
                        "rank": i,
                        "ticker": str(r["ticker"]),
                        "score": float(r["score"]),
                    }
                )
            for i, (_, r) in enumerate(bot.iterrows(), start=1):
                rows_rank.append(
                    {
                        "week": pd.Timestamp(wk).strftime("%Y-%m-%d"),
                        "rank_type": "bottom",
                        "rank": i,
                        "ticker": str(r["ticker"]),
                        "score": float(r["score"]),
                    }
                )
        weekly_rank = pd.DataFrame(rows_rank)
        return ticker_daily, market_daily, weekly_rank

    def run(
        self,
        *,
        start_year: int = 2010,
        end_year: int = date.today().year,
        resume: bool = True,
        sources: tuple[str, ...] = ("nse", "gdelt", "rss"),
        workers: int = 4,
        gdelt_max_records: int = 250,
        delay_min: float = 0.2,
        delay_max: float = 0.8,
        log_every: int = 100,
        max_tickers: int = 0,
        max_months: int = 0,
        rss_lookback_days: int = 30,
        sentiment_model: str = "auto",
        include_bulk_deals: bool = False,
        include_legacy: bool = True,
        gdelt_min_interval: float = 5.2,
    ) -> dict[str, int]:
        source_set = {s.strip().lower() for s in sources if str(s).strip()}
        frames: list[pd.DataFrame] = []
        source_stats: dict[str, dict[str, float]] = {}

        def _record_source(name: str, started: float, df: pd.DataFrame) -> None:
            elapsed = max(0.0, time.monotonic() - started)
            rows = int(len(df)) if isinstance(df, pd.DataFrame) else 0
            tickers = int(df["ticker"].nunique()) if isinstance(df, pd.DataFrame) and not df.empty and "ticker" in df.columns else 0
            source_stats[name] = {"rows": float(rows), "tickers": float(tickers), "seconds": float(elapsed)}
            print(
                f"[news][{name}] ingest_done rows={rows} tickers={tickers} "
                f"elapsed_s={elapsed:.1f}"
            )

        if "nse" in source_set or "bse" in source_set:
            t0 = time.monotonic()
            bse_df = self.collect_bse_events(include_bulk_deals=include_bulk_deals)
            frames.append(bse_df)
            _record_source("nse" if "nse" in source_set else "bse", t0, bse_df)
        if "gdelt" in source_set:
            t0 = time.monotonic()
            gdelt_df = self.collect_gdelt(
                start_year=start_year,
                end_year=end_year,
                resume=resume,
                workers=workers,
                max_records=gdelt_max_records,
                delay_min=delay_min,
                delay_max=delay_max,
                log_every=log_every,
                max_tickers=max_tickers,
                max_months=max_months,
                min_interval_sec=gdelt_min_interval,
            )
            frames.append(gdelt_df)
            _record_source("gdelt", t0, gdelt_df)
        if "rss" in source_set:
            t0 = time.monotonic()
            rss_df = self.collect_rss(
                resume=resume,
                lookback_days=rss_lookback_days,
                delay_min=delay_min,
                delay_max=delay_max,
                log_every=max(20, int(log_every)),
                max_tickers=max_tickers,
            )
            frames.append(rss_df)
            _record_source("rss", t0, rss_df)

        if include_legacy:
            t0 = time.monotonic()
            legacy_df = self.collect_legacy_news()
            if not legacy_df.empty:
                frames.append(legacy_df)
            _record_source("legacy", t0, legacy_df)

        combined = self.combine_sources(frames)
        print(
            f"[news] combine rows={len(combined)} tickers={combined['ticker'].nunique() if not combined.empty else 0} "
            f"sources={sorted(combined['source_type'].dropna().unique().tolist()) if not combined.empty else []}"
        )
        if source_stats:
            summary = {
                k: {
                    "rows": int(v.get("rows", 0)),
                    "tickers": int(v.get("tickers", 0)),
                    "seconds": round(float(v.get("seconds", 0.0)), 1),
                }
                for k, v in source_stats.items()
            }
            print(f"[news] source_summary={summary}")

        existing_scored = self._load_existing_scored_dataset() if resume else pd.DataFrame()
        to_score = combined
        if resume and not existing_scored.empty and not combined.empty:
            existing_keys = existing_scored[self.NEWS_KEY_COLUMNS].drop_duplicates().assign(_existing=1)
            merged = combined.merge(existing_keys, on=self.NEWS_KEY_COLUMNS, how="left")
            to_score = merged[merged["_existing"].isna()].drop(columns=["_existing"])

        print(
            f"[news] resume scored_existing_rows={len(existing_scored)} "
            f"new_rows_to_score={len(to_score)}"
        )

        new_scored = self.score_sentiment(to_score, model=sentiment_model) if not to_score.empty else pd.DataFrame()
        if resume and not existing_scored.empty:
            scored = pd.concat([existing_scored, new_scored], ignore_index=True, sort=False)
            scored = scored.drop_duplicates(subset=self.NEWS_KEY_COLUMNS, keep="last")
            scored = scored.sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)
        else:
            scored = new_scored

        print(
            f"[news] scored_rows_total={len(scored)} newly_scored_rows={len(new_scored)}"
        )
        ticker_daily, market_daily, weekly_rank = self._build_processed_sentiment(scored)

        news_parquet = self.processed_news_dir / "news_dataset.parquet"
        news_csv = self.processed_news_dir / "news_dataset.csv"
        scored.to_parquet(news_parquet, index=False)
        scored.to_csv(news_csv, index=False)

        ticker_path = self.processed_sentiment_dir / "ticker_sentiment_daily.parquet"
        market_path = self.processed_sentiment_dir / "market_sentiment_daily.parquet"
        weekly_path = self.processed_sentiment_dir / "top_bottom_weekly.parquet"
        ticker_daily.to_parquet(ticker_path, index=False)
        market_daily.to_parquet(market_path, index=False)
        weekly_rank.to_parquet(weekly_path, index=False)

        print(
            f"[news] outputs dataset_rows={len(scored)} ticker_daily_rows={len(ticker_daily)} "
            f"market_daily_rows={len(market_daily)} weekly_rows={len(weekly_rank)}"
        )
        if not ticker_daily.empty:
            print(
                f"[news] ticker_sentiment date_range={ticker_daily['date'].min().date()} to "
                f"{ticker_daily['date'].max().date()} tickers={ticker_daily['ticker'].nunique()}"
            )
        if not market_daily.empty:
            print(
                f"[news] market_sentiment date_range={market_daily['date'].min().date()} to "
                f"{market_daily['date'].max().date()}"
            )

        return {
            "news_rows": int(len(scored)),
            "ticker_daily_rows": int(len(ticker_daily)),
            "market_daily_rows": int(len(market_daily)),
            "weekly_rows": int(len(weekly_rank)),
        }
