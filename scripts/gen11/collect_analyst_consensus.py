#!/usr/bin/env python3
"""Weekly analyst-consensus snapshot collector (Yahoo via yfinance).

CORRECTS docs/DATA_ACQUISITION_ASSESSMENT_2026_07_31.md s3, which said PIT analyst
consensus was "not obtainable free -- do not attempt". That was asserted from priors and is
wrong. Measured coverage on a stratified 36-name sample of the live universe: 27/36 (75%)
-- 11/12 large, 10/12 mid, 6/12 small.

WHAT IS AND IS NOT POINT-IN-TIME. This matters more than the coverage number.

  NOT PIT, and must never be treated as history:
    numberOfAnalystOpinions, targetMedianPrice, recommendationKey, revenue/earnings estimate
    levels. These are TODAY's values. Writing them backwards across history is exactly the
    look-ahead bug that poisoned the val_* family (current-day Screener metadata broadcast
    into the past). This collector never does that -- every row is stamped with the date it
    was COLLECTED, and snapshots are never overwritten.

  GENUINELY PIT-USABLE, as of the collection date:
    eps_revisions   -- counts of analysts revising up/down over the trailing 7 and 30 days.
                       A change measure. "How many revised up in the last 30 days, as of
                       today" is a legitimate as-of-today feature. This is precisely the
                       analyst-revision-breadth construct Gen-1's R01-R08 family wanted and
                       was blocked on ("0/448 relevant columns").
    eps_trend       -- the consensus EPS estimate as it stood 7/30/60/90 days ago. A real,
                       if short, backward window. Differences across those columns give
                       revision MAGNITUDE to complement the breadth counts above.

  NOT AVAILABLE for Indian names at all:
    upgrades_downgrades returns an empty frame -- there is no dated broker-action history.

CONSEQUENCE: history cannot be backfilled. Each weekly run appends one dated snapshot, and
each snapshot carries a 90-day internal lookback. A usable PIT panel accrues from the first
run forward; the 90-day window gives a small head start, not a substitute for waiting.

Resumable and rate-limited. One snapshot per ISO week; re-running in the same week is a no-op.
"""
from __future__ import annotations
import argparse
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/processed/analyst_consensus"
OUT.mkdir(parents=True, exist_ok=True)
SLEEP = 0.35            # deliberate pacing; this is a public endpoint, not a scrape target


def universe():
    p = pd.read_parquet(ROOT / "data/kaggle_upload/panel_a_weekly.parquet",
                        columns=["date", "ticker"])
    p["date"] = pd.to_datetime(p["date"])
    return sorted(p[p["date"] == p["date"].max()]["ticker"].unique())


def one(tk, yf):
    r = {"ticker": tk}
    t = yf.Ticker(tk)
    try:
        info = t.info or {}
    except Exception:
        info = {}
    # --- SNAPSHOT fields: today's values. Valid only at the collection date. ---
    for k, c in (("numberOfAnalystOpinions", "n_analysts"),
                 ("targetMedianPrice", "target_median"),
                 ("targetLowPrice", "target_low"),
                 ("targetHighPrice", "target_high"),
                 ("recommendationMean", "rec_mean"),
                 ("recommendationKey", "rec_key"),
                 ("currentPrice", "price_at_collection")):
        r[c] = info.get(k)
    if r.get("target_median") and r.get("price_at_collection"):
        try:
            r["target_upside"] = float(r["target_median"]) / float(r["price_at_collection"]) - 1
        except Exception:
            r["target_upside"] = np.nan

    # --- PIT-USABLE: revision BREADTH over trailing windows ---
    try:
        er = t.eps_revisions
        if isinstance(er, pd.DataFrame) and len(er):
            row = er.iloc[0]                       # nearest fiscal period
            for k, c in (("upLast7days", "eps_rev_up_7d"),
                         ("downLast7Days", "eps_rev_dn_7d"),
                         ("upLast30days", "eps_rev_up_30d"),
                         ("downLast30days", "eps_rev_dn_30d")):
                r[c] = row.get(k)
            u30, d30 = r.get("eps_rev_up_30d"), r.get("eps_rev_dn_30d")
            if u30 is not None and d30 is not None:
                # NOTE on construction. The obvious ratio (up-dn)/(up+dn) is DEGENERATE for
                # thinly-covered names: most Indian stocks get at most one revision in a
                # month, so the ratio collapses to exactly +1 or -1. Measured on the first
                # snapshot: of 146 names with any revision, 90 were -1.0 and 49 were +1.0 --
                # bimodal, carrying almost no cross-sectional gradation.
                # The NET COUNT scaled by analyst coverage is the usable version: it
                # separates "1 of 2 analysts cut" from "1 of 30 analysts cut".
                r["eps_rev_net_30d"] = u30 - d30
                na = r.get("n_analysts")
                if na:
                    r["eps_rev_net_scaled_30d"] = (u30 - d30) / float(na)
                if (u30 + d30):
                    r["eps_rev_breadth_30d"] = (u30 - d30) / (u30 + d30)   # kept, secondary
    except Exception:
        pass

    # --- PIT-USABLE: revision MAGNITUDE from the 90-day estimate trail ---
    try:
        et = t.eps_trend
        if isinstance(et, pd.DataFrame) and len(et):
            row = et.iloc[0]
            cur, d30, d90 = row.get("current"), row.get("30daysAgo"), row.get("90daysAgo")
            r["eps_est_current"] = cur
            for c, v in (("eps_est_30d_ago", d30), ("eps_est_90d_ago", d90)):
                r[c] = v
            if cur is not None and d30 not in (None, 0) and np.isfinite(float(d30 or np.nan)):
                r["eps_rev_mag_30d"] = float(cur) / float(d30) - 1
            if cur is not None and d90 not in (None, 0) and np.isfinite(float(d90 or np.nan)):
                r["eps_rev_mag_90d"] = float(cur) / float(d90) - 1
    except Exception:
        pass

    # --- rating distribution, current + 3 monthly lags Yahoo carries ---
    try:
        rc = t.recommendations
        if isinstance(rc, pd.DataFrame) and len(rc):
            cur = rc.iloc[0]
            tot = sum(float(cur.get(k) or 0) for k in
                      ("strongBuy", "buy", "hold", "sell", "strongSell"))
            if tot > 0:
                r["rec_bull_share"] = (float(cur.get("strongBuy") or 0)
                                       + float(cur.get("buy") or 0)) / tot
                r["rec_bear_share"] = (float(cur.get("sell") or 0)
                                       + float(cur.get("strongSell") or 0)) / tot
                r["rec_n_total"] = tot
            if len(rc) >= 4:                      # 0m vs -3m: rating drift
                old = rc.iloc[3]
                to = sum(float(old.get(k) or 0) for k in
                         ("strongBuy", "buy", "hold", "sell", "strongSell"))
                if to > 0 and tot > 0:
                    ob = (float(old.get("strongBuy") or 0) + float(old.get("buy") or 0)) / to
                    r["rec_bull_share_chg_3m"] = r["rec_bull_share"] - ob
    except Exception:
        pass
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    import yfinance as yf

    today = pd.Timestamp.today().normalize()
    key = f"{today.isocalendar().year}W{today.isocalendar().week:02d}"
    path = OUT / f"consensus_{key}.parquet"
    if path.exists() and not a.force:
        print(f"snapshot for {key} already exists -> {path}  (use --force to overwrite)")
        return

    tks = universe()
    if a.limit:
        tks = tks[:a.limit]
    print(f"collecting {len(tks)} names for ISO week {key} ...")
    rows = []
    for i, tk in enumerate(tks, 1):
        rows.append(one(tk, yf))
        if i % 50 == 0:
            got = sum(1 for r in rows if r.get("n_analysts") is not None)
            print(f"  [{i}/{len(tks)}] {got} with coverage", flush=True)
        time.sleep(SLEEP)

    d = pd.DataFrame(rows)
    d.insert(0, "collected_at", today)            # PIT stamp: never overwrite, never backfill
    d.to_parquet(path, index=False)
    cov = d["n_analysts"].notna().mean()
    print(f"\nwrote {len(d)} rows -> {path}")
    print(f"  coverage: {d['n_analysts'].notna().sum()}/{len(d)} ({cov:.0%}) have analyst data")
    for c in ("eps_rev_breadth_30d", "eps_rev_mag_30d", "target_upside", "rec_bull_share"):
        if c in d:
            print(f"  {c:<22} {d[c].notna().sum():>4} non-null   "
                  f"median {d[c].median():+.4f}" if d[c].notna().any() else f"  {c}: none")


if __name__ == "__main__":
    main()
