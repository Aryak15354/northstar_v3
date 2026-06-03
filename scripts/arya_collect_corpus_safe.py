#!/usr/bin/env python3
"""Mac-safe Arya corpus collection runner.

This runner is deliberately sequential. It batches NSE dates, limits article
fetches by default, writes provenance manifests, and never holds the whole
corpus in memory.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from arya.data import NorthstarCorpusExporter
from arya.data.corpus_builder import build_clean_corpus, split_corpus
from arya.data.scrapers import NSEFilingScraper, NewsScraper, RBIScraper, SEBIScraper, WikipediaScraper


@dataclass
class CollectionSummary:
    raw_root: str
    clean_root: str | None
    split_root: str | None
    nse_docs: int = 0
    rbi_docs: int = 0
    sebi_docs: int = 0
    news_docs: int = 0
    wikipedia_docs: int = 0
    northstar_docs: int = 0
    clean_written_docs: int | None = None
    clean_skipped_docs: int | None = None
    split_counts: dict[str, int] | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Arya corpus collection safely on an 8GB Mac.")
    parser.add_argument("--raw-root", type=Path, default=Path("data/arya/raw"))
    parser.add_argument("--clean-root", type=Path, default=Path("data/arya/clean"))
    parser.add_argument("--split-root", type=Path, default=Path("data/arya/splits"))
    parser.add_argument("--northstar-root", type=Path, default=Path.cwd())

    parser.add_argument("--nse-from", default="2024-01-01")
    parser.add_argument("--nse-to", default=date.today().isoformat())
    parser.add_argument("--nse-batch-days", type=int, default=7)
    parser.add_argument("--nse-delay-sec", type=float, default=1.5)
    parser.add_argument("--download-nse-attachments", action="store_true")
    parser.add_argument("--max-nse-attachments-per-batch", type=int, default=25)
    parser.add_argument("--nse-progress-every", type=int, default=250)

    parser.add_argument("--rbi-limit", type=int, default=100)
    parser.add_argument("--sebi-limit", type=int, default=100)
    parser.add_argument("--news-per-feed-limit", type=int, default=100)
    parser.add_argument("--fetch-sebi-articles", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--fetch-news-articles", action="store_true")

    parser.add_argument("--skip-nse", action="store_true")
    parser.add_argument("--skip-rbi", action="store_true")
    parser.add_argument("--skip-sebi", action="store_true")
    parser.add_argument("--skip-news", action="store_true")
    parser.add_argument("--skip-wikipedia", action="store_true")
    parser.add_argument("--skip-northstar", action="store_true")
    parser.add_argument("--skip-clean", action="store_true")
    parser.add_argument("--skip-split", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = CollectionSummary(
        raw_root=str(args.raw_root),
        clean_root=None if args.skip_clean else str(args.clean_root),
        split_root=None if args.skip_split else str(args.split_root),
    )

    args.raw_root.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        print(json.dumps({"dry_run": True, "plan": _plan(args)}, indent=2, sort_keys=True))
        return 0

    if not args.skip_nse:
        summary.nse_docs = collect_nse(args)
    if not args.skip_rbi:
        rbi = RBIScraper(args.raw_root)
        summary.rbi_docs = rbi.collect_press_releases(limit=args.rbi_limit)
        summary.rbi_docs += rbi.collect_notifications(limit=args.rbi_limit)
    if not args.skip_sebi:
        summary.sebi_docs = SEBIScraper(args.raw_root, fetch_articles=args.fetch_sebi_articles).collect_rss(
            limit=args.sebi_limit
        )
    if not args.skip_news:
        summary.news_docs = NewsScraper(args.raw_root, fetch_articles=args.fetch_news_articles).collect(
            per_feed_limit=args.news_per_feed_limit
        )
    if not args.skip_wikipedia:
        summary.wikipedia_docs = WikipediaScraper(args.raw_root).collect()
    if not args.skip_northstar:
        summary.northstar_docs = NorthstarCorpusExporter(args.northstar_root, args.raw_root).export_all()

    if not args.skip_clean:
        clean_result = build_clean_corpus(args.raw_root, args.clean_root, min_words=50)
        summary.clean_written_docs = clean_result.written_docs
        summary.clean_skipped_docs = clean_result.skipped_docs
    if not args.skip_split:
        summary.split_counts = split_corpus(args.clean_root, args.split_root, val_fraction=0.01)

    print(json.dumps(asdict(summary), indent=2, sort_keys=True))
    return 0


def collect_nse(args: argparse.Namespace) -> int:
    total = 0
    scraper = NSEFilingScraper(args.raw_root, delay_sec=args.nse_delay_sec)
    for start, end in date_batches(args.nse_from, args.nse_to, args.nse_batch_days):
        print(f"[arya] NSE {start} -> {end}", flush=True)
        total += scraper.collect_range(
            start,
            end,
            download_attachments=args.download_nse_attachments,
            max_attachments=args.max_nse_attachments_per_batch,
            progress_every=args.nse_progress_every,
        )
    return total


def date_batches(from_date: str, to_date: str, batch_days: int) -> list[tuple[str, str]]:
    start = datetime.strptime(from_date, "%Y-%m-%d").date()
    final = datetime.strptime(to_date, "%Y-%m-%d").date()
    if batch_days < 1:
        raise ValueError("--nse-batch-days must be >= 1")
    batches: list[tuple[str, str]] = []
    current = start
    while current <= final:
        end = min(current + timedelta(days=batch_days - 1), final)
        batches.append((current.isoformat(), end.isoformat()))
        current = end + timedelta(days=1)
    return batches


def _plan(args: argparse.Namespace) -> dict:
    return {
        "raw_root": str(args.raw_root),
        "clean_root": None if args.skip_clean else str(args.clean_root),
        "split_root": None if args.skip_split else str(args.split_root),
        "nse_batches": [] if args.skip_nse else date_batches(args.nse_from, args.nse_to, args.nse_batch_days),
        "download_nse_attachments": args.download_nse_attachments,
        "rbi_limit": None if args.skip_rbi else args.rbi_limit,
        "sebi_limit": None if args.skip_sebi else args.sebi_limit,
        "news_per_feed_limit": None if args.skip_news else args.news_per_feed_limit,
        "wikipedia": not args.skip_wikipedia,
        "northstar": not args.skip_northstar,
    }


if __name__ == "__main__":
    raise SystemExit(main())
