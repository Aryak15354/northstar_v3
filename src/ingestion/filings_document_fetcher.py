#!/usr/bin/env python3
"""Discover, classify, and download filing-attachment documents (Phase 4).

The announcements pipeline already indexes every corporate filing with its
attachment PDF URL. This module classifies those attachments against
``config/document_patterns.yaml`` (results / investor_presentation / transcript /
basel_pillar3 / embedded_value / press_release), filters to a target universe and
document classes, downloads the PDFs into an immutable raw store, and writes an
index the extractor consumes.

    python -m src.ingestion.filings_document_fetcher \
        --universe financials --classes investor_presentation press_release \
        --since 2025-01-01 --limit 200

The raw store is ``data/raw/vendors/nse_filings/{SYMBOL}/{date}_{class}.pdf`` and
the index is ``data/processed/sector_financials/filings_index.parquet``.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.nse_csv_scraper_common import create_nse_session, nse_request  # noqa: E402

ANNOUNCEMENTS = PROJECT_ROOT / "data" / "processed" / "alternative" / "announcements_all.parquet"
PATTERNS_FILE = PROJECT_ROOT / "config" / "document_patterns.yaml"
REGISTRY_FILE = PROJECT_ROOT / "config" / "sector_data_sources.yaml"
UNIVERSE_FILE = PROJECT_ROOT / "universe" / "nifty500.csv"
RAW_FILINGS_DIR = PROJECT_ROOT / "data" / "raw" / "vendors" / "nse_filings"
INDEX_OUT = PROJECT_ROOT / "data" / "processed" / "sector_financials" / "filings_index.parquet"

NSE_REFERER = "https://www.nseindia.com/companies-listing/corporate-filings-announcements"


def load_patterns() -> dict:
    return yaml.safe_load(PATTERNS_FILE.read_text())


def classify_document(subject: str, attachment_url: str, patterns: dict) -> Optional[str]:
    """Return the document class whose subject/filename regexes match, else None."""
    subject_l = str(subject or "").lower()
    fname_l = str(attachment_url or "").rsplit("/", 1)[-1].lower()
    for doc_class, spec in patterns.items():
        for rx in spec.get("subject", []):
            if re.search(rx, subject_l):
                return doc_class
        for rx in spec.get("filename", []):
            if re.search(rx, fname_l):
                return doc_class
    return None


def _target_symbols(universe: str) -> set[str]:
    df = pd.read_csv(UNIVERSE_FILE)
    if universe == "financials":
        sel = df[df["Industry"] == "Financial Services"]
    elif universe in ("it", "information_technology"):
        sel = df[df["Industry"] == "Information Technology"]
    elif universe == "all":
        sel = df
    else:  # comma-separated symbols
        return {s.strip().upper() for s in universe.split(",") if s.strip()}
    return {str(s).strip().upper() for s in sel["Symbol"].dropna()}


def build_document_index(
    universe: str,
    classes: Optional[list[str]] = None,
    since: Optional[str] = None,
) -> pd.DataFrame:
    """Classify announcement attachments into a candidate download index."""
    if not ANNOUNCEMENTS.exists():
        raise FileNotFoundError(f"{ANNOUNCEMENTS} not found — run the announcements pipeline first")
    ann = pd.read_parquet(ANNOUNCEMENTS)
    ann["date"] = pd.to_datetime(ann["date"], errors="coerce")
    ann = ann.dropna(subset=["date"])
    if since:
        ann = ann[ann["date"] >= pd.Timestamp(since)]

    symbols = _target_symbols(universe)
    ann["symbol_u"] = (
        ann.get("nse_ticker", pd.Series("", index=ann.index))
        .astype(str).str.replace(".NS", "", regex=False).str.upper()
    )
    ann = ann[ann["symbol_u"].isin(symbols)]
    ann = ann[ann["attachment"].astype(str).str.len() > 5]

    patterns = load_patterns()
    ann["doc_class"] = [
        classify_document(subj, att, patterns)
        for subj, att in zip(ann.get("headline", ""), ann["attachment"])
    ]
    ann = ann.dropna(subset=["doc_class"])
    if classes:
        ann = ann[ann["doc_class"].isin(classes)]
    cols = ["date", "symbol_u", "company_name", "doc_class", "headline", "attachment"]
    out = ann[[c for c in cols if c in ann.columns]].rename(columns={"symbol_u": "symbol"})
    return out.sort_values("date").reset_index(drop=True)


def _dest_path(symbol: str, dt: pd.Timestamp, doc_class: str, url: str) -> Path:
    h = hashlib.sha1(url.encode()).hexdigest()[:8]
    fname = f"{dt:%Y%m%d}_{doc_class}_{h}.pdf"
    return RAW_FILINGS_DIR / symbol / fname


def download_documents(
    index: pd.DataFrame,
    limit: int = 0,
    session=None,
    sleep_seconds: float = 0.8,
) -> pd.DataFrame:
    """Download PDFs referenced by the index; return the index with local paths."""
    session = session or create_nse_session(referer=NSE_REFERER)
    rows = []
    n = 0
    total = len(index)
    for i, (_, r) in enumerate(index.iterrows(), 1):
        if limit and n >= limit:
            break
        url = str(r["attachment"])
        dest = _dest_path(r["symbol"], r["date"], r["doc_class"], url)
        status = "cached"
        if not (dest.exists() and dest.stat().st_size > 0):
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                resp = nse_request(session, url, referer=NSE_REFERER, max_attempts=3)
                body = resp.content
                if not body[:5] == b"%PDF-":
                    status = "not_pdf"
                else:
                    dest.write_bytes(body)
                    status = "downloaded"
                    n += 1
                    time.sleep(sleep_seconds)
            except Exception as exc:  # noqa: BLE001
                status = f"error:{type(exc).__name__}"
        if status != "cached" or i == 1 or i % 10 == 0 or i == total:
            print(
                f"[filings] {i}/{total} {r['symbol']} {r['doc_class']} {status}",
                flush=True,
            )
        rows.append({**r.to_dict(), "local_path": str(dest) if status in ("cached", "downloaded") else "", "download_status": status})
    result = pd.DataFrame(rows)
    INDEX_OUT.parent.mkdir(parents=True, exist_ok=True)
    if INDEX_OUT.exists():
        prev = pd.read_parquet(INDEX_OUT)
        result = pd.concat([prev, result], ignore_index=True).drop_duplicates(
            subset=["symbol", "date", "doc_class", "attachment"], keep="last"
        )
    result.to_parquet(INDEX_OUT, index=False)
    return result


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download & classify filing attachments (Phase 4).")
    p.add_argument("--universe", default="financials",
                   help="'financials' | 'it' | 'all' | comma-separated symbols")
    p.add_argument("--classes", nargs="*", default=None,
                   help="Restrict to these document classes (default: all classified).")
    p.add_argument("--since", default=None, help="ISO date lower bound.")
    p.add_argument("--limit", type=int, default=0, help="Max downloads this run (0 = all).")
    p.add_argument("--index-only", action="store_true", help="Build/print index, no downloads.")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    index = build_document_index(args.universe, args.classes, args.since)
    print(f"[filings] {len(index)} classified attachments "
          f"(universe={args.universe}, classes={args.classes or 'all'}, since={args.since})")
    if not index.empty:
        print(index["doc_class"].value_counts().to_string())
    if args.index_only:
        return 0
    result = download_documents(index, limit=args.limit)
    dl = result[result["download_status"] == "downloaded"]
    print(f"[filings] downloaded {len(dl)} new PDFs -> {RAW_FILINGS_DIR}")
    print(f"[filings] index -> {INDEX_OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
