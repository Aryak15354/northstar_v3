#!/usr/bin/env python3
"""Build the company news history from the NSE announcements backfill (PIT-safe).

The canonical sentiment (`company_sentiment_daily.parquet`) was historically THIN
pre-2024 (~6 news-days per ticker per year in 2019) because live RSS collection
only started mid-2024 — which is exactly why the export's `sent_*` factors were
~0% before 2024. The 2026-07-11 backfill produced 1M+ NSE corporate announcements
dense every year 2019-2026, with TRUE exchange PIT timestamps. This script turns
that corpus into the news input the existing FinBERT batch scorer consumes, then
you run the scorer (heavy/GPU — see the printed command) to regenerate sentiment.

Pipeline position:
  announcements_all.parquet  --[this script]-->  company_news_history.parquet
  company_news_history.parquet  --[BatchHistoricalScorer, GPU]-->  company_sentiment_daily.parquet

PIT rule: availability_date = max(broadcast, receipt, dissemination) datetimes —
the true "known at" moment, never the nominal announcement date. This is stronger
PIT than any news vendor. Merges with (does not clobber) the existing news history;
`source` column preserves provenance.

Usage:
  python3 scripts/build_company_news_from_announcements.py            # full build
  python3 scripts/build_company_news_from_announcements.py --sample 5000   # quick test
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANNOUNCEMENTS = PROJECT_ROOT / "data/processed/alternative/announcements_all.parquet"
EXISTING_NEWS = PROJECT_ROOT / "data/canonical/news/company_news_history.parquet"
OUTPUT = PROJECT_ROOT / "data/canonical/news/company_news_history.parquet"
UNIVERSE = PROJECT_ROOT / "universe/nifty500.csv"

# Boilerplate/administrative categories that carry no company-sentiment signal.
# (Drop-list, not keep-list: keep everything not explicitly administrative, so a
# new informative category is never silently dropped.)
DROP_CATEGORIES = {
    "copy of newspaper publication", "loss of share certificates",
    "shareholders meeting", "duplicate certificate",
    "certificate under sebi (depositories and participants) regulations, 2018",
    "trading window", "compliances-reg", "compliance certificate",
    "record date", "book closure", "spurt in volume", "price movement",
}


def _norm_ticker(s: pd.Series) -> pd.Series:
    t = s.astype(str).str.strip().str.upper()
    return t.where(t.str.endswith(".NS") | (t == ""), t + ".NS")


def build(sample: int | None = None) -> pd.DataFrame:
    ann = pd.read_parquet(ANNOUNCEMENTS)
    if sample:
        ann = ann.head(sample).copy()

    ann["ticker"] = _norm_ticker(ann["nse_ticker"])
    # PIT: latest of the three real exchange timestamps, fallback to nominal date
    ts_cols = [c for c in ("broadcast_datetime", "receipt_datetime", "dissemination_datetime")
               if c in ann.columns]
    avail = pd.concat([pd.to_datetime(ann[c], errors="coerce") for c in ts_cols], axis=1).max(axis=1)
    ann["date"] = pd.to_datetime(ann["date"], errors="coerce")
    ann["availability_date"] = avail.fillna(ann["date"])

    # headline text: prefer headline, fall back to subject/announcement_text
    head = ann["headline"].astype(str)
    for alt in ("subject", "announcement_text"):
        if alt in ann.columns:
            head = head.where(head.str.len() >= 10, ann[alt].astype(str))
    ann["headline"] = head

    # filter: universe tickers, informative categories, real text
    uni = set(_norm_ticker(pd.read_csv(UNIVERSE)["Symbol"])) if UNIVERSE.exists() else None
    cat = ann.get("category", pd.Series("", index=ann.index)).astype(str).str.strip().str.lower()
    keep = (ann["headline"].str.len() >= 10) & (~cat.isin(DROP_CATEGORIES)) & ann["date"].notna()
    if uni:
        keep &= ann["ticker"].isin(uni)
    out = ann.loc[keep, ["date", "availability_date", "ticker", "headline", "category"]].copy()
    out["source"] = "nse_announcement"
    out = out.drop_duplicates(["ticker", "date", "headline"])

    # merge with existing news history (keep both sources; provenance in `source`)
    if EXISTING_NEWS.exists():
        prev = pd.read_parquet(EXISTING_NEWS)
        prev["date"] = pd.to_datetime(prev["date"], errors="coerce")
        common = ["date", "availability_date", "ticker", "headline", "source"]
        prev = prev[[c for c in common if c in prev.columns]].copy()
        merged = pd.concat([prev, out[[c for c in common if c in out.columns]]], ignore_index=True)
        merged = merged.drop_duplicates(["ticker", "date", "headline"])
    else:
        merged = out
    merged = merged.dropna(subset=["date", "headline", "ticker"]).sort_values(["date", "ticker"])
    return merged.reset_index(drop=True)


def _report(df: pd.DataFrame) -> None:
    d = pd.to_datetime(df["date"])
    av = pd.to_datetime(df["availability_date"], errors="coerce")
    pit_ok = float((av >= d).mean())
    print(f"rows={len(df):,}  tickers={df['ticker'].nunique()}  "
          f"range={d.min().date()}->{d.max().date()}")
    print("  rows/yr:", {int(k): int(v) for k, v in d.dt.year.value_counts().sort_index().items() if k >= 2019})
    print(f"  PIT (availability>=date): {pit_ok:.3f}  (must be ~1.0)")
    # Synthetic detection: real exchange filings repeat legitimately ("Outcome of
    # Board Meeting"), so a low distinct ratio is NOT itself a red flag. The real
    # tell is a rigid generated TEMPLATE pattern ("Analyst Upgrade: TICKER").
    import re
    tmpl = df["headline"].astype(str).str.match(
        r"^(Analyst Upgrade|Regulatory Update|.* Complies with|.* Reports Q\d)").mean()
    print(f"  distinct headlines: {df['headline'].nunique():,} / {len(df):,}  "
          f"| synthetic-template rate: {tmpl:.3f} (must be ~0; the fake file was ~1.0)")
    print("  top sources:", dict(list(df["source"].value_counts().head(4).items())))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=None, help="only process first N announcements (test)")
    ap.add_argument("--out", default=str(OUTPUT))
    ap.add_argument("--dry-run", action="store_true", help="report only, do not write")
    args = ap.parse_args()

    df = build(sample=args.sample)
    _report(df)
    if args.dry_run or args.sample:
        print("\n(dry-run/sample — not written)")
        return 0
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    print(f"\nwrote {args.out}")
    print("\nNEXT (heavy, GPU — run manually):")
    print("  python3 -c \"from src.nlp.pipeline.batch_scorer import BatchHistoricalScorer;"
          " BatchHistoricalScorer().score_company_news_history(resume_from_checkpoint=True)\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
