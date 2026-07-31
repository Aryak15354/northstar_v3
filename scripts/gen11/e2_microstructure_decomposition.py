#!/usr/bin/env python3
"""E2 — What inside 'microstructure' carries the incremental ceiling?

E1 ranked microstructure first: +0.0340 incremental attainable ceiling over the price basis
(0.117 -> 0.151, a 29% lift) on 270 dates. Before constructing anything, charter gate A4
requires establishing whether that is a REDISCOVERY.

The family has three structurally different kinds of column, and they cannot all be
contributing:

  DELIVERY      delivery_pct, delivery_pct_4w_avg, delivery_pct_z52
                -- stock-level, and ALREADY DEPLOYED (G2-E03/E03b). If the ceiling is here,
                   E1 found nothing new and Gen-11 must say so.
  FUTURES OI    fut_oi, fut_oi_chg_1w_pct, fut_oi_chg_4w_pct, fut_oi_z52
                -- stock-level, and REJECTED individually by G2-E01 (t=-0.27) and
                   G2-E02 (t=-0.03). A joint contribution here would be genuinely new.
  MARKET-LEVEL  partoi_* (participant-category net long ratios), nifty50_*
                -- DATE-CONSTANT. In a per-date cross-sectional regression these are
                   collinear with the intercept and contribute EXACTLY NOTHING. Included
                   as a control: if they appear to contribute, the method is broken.

So this decomposes the +0.0340 by sub-block, on matched dates (Rule 6), each against its own
permutation null.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/gen11"))
from src.research.gen10.inference import nw_mean_test  # noqa: E402
from e1_ceiling_decomposition import PRICE_BASIS, oracle_excess, BASE, LOCK  # noqa: E402

OUT = ROOT / "results/gen11/E2"
OUT.mkdir(parents=True, exist_ok=True)
SEED = 20260731

BLOCKS = {
    "delivery (DEPLOYED)": ["delivery_pct", "delivery_pct_4w_avg", "delivery_pct_z52"],
    "futures OI (rejected individually)": ["fut_oi", "fut_oi_chg_1w_pct",
                                           "fut_oi_chg_4w_pct", "fut_oi_z52"],
    "market-level (CONTROL, must be ~0)": ["partoi_client_net_long_ratio",
                                           "partoi_dii_net_long_ratio",
                                           "partoi_fii_net_long_ratio",
                                           "partoi_pro_net_long_ratio",
                                           "partoi_fii_net_long_ratio_chg_1w",
                                           "nifty50_pe", "nifty50_pb",
                                           "nifty50_div_yield", "nifty50_pe_z52"],
}


def main() -> int:
    print("=" * 100)
    print("E2 — DECOMPOSING THE MICROSTRUCTURE CEILING (charter gate A4: rediscovery check)")
    print("=" * 100)
    need = sorted(set(PRICE_BASIS + sum(BLOCKS.values(), [])))
    d = pd.read_parquet(BASE / "northstar_features_enriched.parquet",
                        columns=["date", "ticker", "target_weekly_return"] + need)
    d["date"] = pd.to_datetime(d["date"]).dt.normalize()
    d = d[d["date"] <= LOCK]
    d["ret"] = d.groupby("date")["target_weekly_return"].transform(
        lambda s: s.clip(s.quantile(.01), s.quantile(.99)))
    d = d.dropna(subset=["ret"])

    # the full-family arm defines the matched date set for every sub-block (Rule 6)
    full = oracle_excess(d, PRICE_BASIS + sum(BLOCKS.values(), []), "price+all micro")
    if full is None:
        print("full arm not computable"); return 1
    dates = full["dates"]
    sub = d[d["date"].isin(dates)]
    base = oracle_excess(sub, PRICE_BASIS, "price-only")
    print(f"\nmatched date set: {len(dates)} weeks "
          f"({pd.Timestamp(min(dates)).date()} .. {pd.Timestamp(max(dates)).date()})")
    print(f"price-only ceiling        {base['ceiling']:+.4f}")
    print(f"price + ALL microstructure {full['ceiling']:+.4f}   "
          f"incremental {full['ceiling']-base['ceiling']:+.4f}\n")

    print(f"{'block':<38}{'k':>3}{'ceiling':>11}{'incremental':>13}   bootstrap CI")
    print("-" * 92)
    rows = []
    for name, cols in BLOCKS.items():
        r = oracle_excess(sub, PRICE_BASIS + cols, name)
        if r is None:
            print(f"{name:<38}{len(cols):>3}   not computable")
            continue
        inc = r["ceiling"] - base["ceiling"]
        rows.append({"block": name, "k": len(cols), "ceiling": r["ceiling"],
                     "incremental": float(inc), "t": r["t"],
                     "boot": [r["boot_lo"], r["boot_hi"]], "cols": cols})
        print(f"{name:<38}{len(cols):>3}{r['ceiling']:>11.4f}{inc:>+13.4f}   "
              f"[{r['boot_lo']:+.4f},{r['boot_hi']:+.4f}]")

    # --- the decisive test: does futures OI add anything OVER delivery? ---
    print("\n--- decisive: does futures OI add anything OVER the deployed delivery block? ---")
    dl = oracle_excess(sub, PRICE_BASIS + BLOCKS["delivery (DEPLOYED)"], "price+delivery")
    dloi = oracle_excess(sub, PRICE_BASIS + BLOCKS["delivery (DEPLOYED)"]
                         + BLOCKS["futures OI (rejected individually)"], "price+delivery+OI")
    over = dloi["ceiling"] - dl["ceiling"]
    print(f"  price + delivery              {dl['ceiling']:+.4f}")
    print(f"  price + delivery + futures OI {dloi['ceiling']:+.4f}")
    print(f"  incremental of OI over delivery: {over:+.4f}")

    verdict = ("REDISCOVERY — the ceiling is delivery, already deployed"
               if over < 0.010 else
               "NEW — futures OI adds beyond the deployed delivery signal")
    print(f"\n{'=' * 100}\nVERDICT (charter A4)\n{'=' * 100}")
    print(f"  {verdict}")
    if over >= 0.010:
        print("  -> E3 constructs a futures-OI candidate and runs it through gates A1-A7.")
    else:
        print("  -> microstructure is exhausted. Gen-11 moves to liquidity_exposure (E1 rank 2).")

    (OUT / "e2_data.json").write_text(json.dumps(
        {"matched_dates": len(dates), "price_only": base["ceiling"],
         "price_all_micro": full["ceiling"], "blocks": rows,
         "oi_over_delivery": float(over), "verdict": verdict}, indent=2, default=str))
    print(f"\n-> {OUT/'e2_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
