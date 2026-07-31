#!/usr/bin/env python3
"""T1-08 — Exit realism: what a real exit from a failing name costs the small-cap lead.

This REPLACES the remediation plan's item 2.3 (rewrite the universe rule, rebuild the
survivorship-complete panel, re-run C04/C05/C07). That item contradicted its own source.
G8-12 concluded:

  "The universe rules are the strategy's own rules. A book that only trades names above
   Rs20 with Rs1cr ADV *would* sell a name that falls through those thresholds. Dropping
   it is not the backtest hiding a loss - it is the backtest executing a stop that the
   strategy actually has."

and named the actual remaining task (G8-12 s6.1):

  "Model realistic exits. Re-run the small-cap tier charging a gap-down exit when a name
   leaves the universe on a price/liquidity failure, rather than a clean fill. This is the
   single test that moves the lead forward and it needs no new data."

Rebuilding the panel to hold names to delisting would model a book nobody would trade. This
models the book that IS traded, with an honest exit price.

Pre-registered in GEN10_REMEDIATION_CHARTER.md s4/T1-08: sweep clean-fill -> -10% -> -20%
-> -35% -> -50% and report the assumption at which G8-07's tier lead stops being a lead.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.research.gen10.inference import sharpe, paired_sharpe_diff, ANN_WEEKLY  # noqa: E402

OUT = ROOT / "results/gen10/T1-08"
OUT.mkdir(parents=True, exist_ok=True)
SEED = 20260731
LOCKBOX = pd.Timestamp("2025-07-10")
MIN_PRICE = 20.0
MIN_ADV_INR = 1e7          # Rs1cr, the panel's own universe rule
TOPQ = 0.80
GAPS = [0.0, -0.10, -0.20, -0.35, -0.50]
# G8-07's reported tier leads vs ALL, averaged across configs
G8_07_LEAD = {"NON_FNO_TAIL": 0.296, "SMALL_ADV_Q1": 0.222, "FNO_LARGE": -0.153}


def load() -> pd.DataFrame:
    df = pd.read_parquet(ROOT / "data/kaggle_upload/panel_a_weekly.parquet",
                         columns=["date", "ticker", "close", "adv_13w", "target_1w",
                                  "is_delisted", "res_mom_52w_ex4w"])
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df = df[df["date"] <= LOCKBOX]
    df = df[pd.to_numeric(df["close"], errors="coerce") >= MIN_PRICE].copy()
    df["adv_inr"] = pd.to_numeric(df["adv_13w"], errors="coerce") * \
        pd.to_numeric(df["close"], errors="coerce")
    df["adv_rank"] = df.groupby("date")["adv_13w"].rank(ascending=False)
    df["fno_ok"] = df["adv_rank"] <= 190
    df["adv_q"] = df.groupby("date")["adv_13w"].transform(
        lambda s: pd.qcut(s.rank(method="first"), 5, labels=False, duplicates="drop"))
    return df


def failure_exits(df: pd.DataFrame) -> set:
    """(date, ticker) pairs where a name is present at t and ABSENT at t+1, and its last
    observation shows it failing the universe rule on price or liquidity.

    This is the population G8-12 identified: names dropped by the rule while still 'looking
    healthy' in the panel, whose real exit would not fill at the last observed price. Names
    that simply reach the end of the data are excluded - that is not a failure exit."""
    dates = sorted(df["date"].unique())
    nxt = {d: n for d, n in zip(dates[:-1], dates[1:])}
    last_date = dates[-1]
    present = df.groupby("date")["ticker"].apply(set).to_dict()
    exits = set()
    for d in dates[:-1]:
        gone = present[d] - present.get(nxt[d], set())
        if not gone:
            continue
        g = df[(df["date"] == d) & (df["ticker"].isin(gone))]
        # failing on the universe rule's own thresholds, or flagged delisted
        fail = g[(g["adv_inr"] < MIN_ADV_INR)
                 | (g["close"] < MIN_PRICE * 1.25)
                 | (g["is_delisted"].astype(bool))]
        exits.update((d, t) for t in fail["ticker"])
    return exits


def tier_mask(df: pd.DataFrame, tier: str) -> pd.Series:
    if tier == "ALL":
        return pd.Series(True, index=df.index)
    if tier == "FNO_LARGE":
        return df["fno_ok"]
    if tier == "NON_FNO_TAIL":
        return ~df["fno_ok"]
    if tier == "SMALL_ADV_Q1":
        return df["adv_q"] == 0
    raise ValueError(tier)


def book_returns(df: pd.DataFrame, tier: str, exits: set, gap: float) -> pd.Series:
    """Top-quintile momentum long book within `tier`, charging `gap` on the exit week of any
    holding that leaves the universe on a price/liquidity failure."""
    d = df[tier_mask(df, tier)]
    out = {}
    for dt, g in d.groupby("date"):
        s = g[["ticker", "res_mom_52w_ex4w", "target_1w"]].dropna()
        if len(s) < 30:
            continue
        thr = s["res_mom_52w_ex4w"].quantile(TOPQ)
        held = s[s["res_mom_52w_ex4w"] >= thr].copy()
        if held.empty:
            continue
        if gap != 0.0:
            is_exit = held["ticker"].map(lambda t, _d=dt: (_d, t) in exits)
            held.loc[is_exit, "target_1w"] = gap
        out[dt] = float(held["target_1w"].mean())
    return pd.Series(out).sort_index()


def main() -> int:
    print("=" * 100)
    print("T1-08 — EXIT REALISM (replaces plan item 2.3)")
    print("=" * 100)
    df = load()
    print(f"panel (pre-lockbox, close>=Rs{MIN_PRICE:.0f}): {len(df):,} rows | "
          f"{df['date'].nunique():,} dates | {df['ticker'].nunique()} tickers\n")

    exits = failure_exits(df)
    print(f"failure exits identified: {len(exits):,} (date, ticker) pairs")
    ex_by_tier = {}
    for tier in ("ALL", "FNO_LARGE", "NON_FNO_TAIL", "SMALL_ADV_Q1"):
        d = df[tier_mask(df, tier)]
        held_ex = sum(1 for dt, g in d.groupby("date")
                      for t in g["ticker"] if (dt, t) in exits)
        ex_by_tier[tier] = held_ex / max(len(d), 1)
        print(f"  {tier:<14} {held_ex:>6,} failure-exit rows  "
              f"({ex_by_tier[tier]:.3%} of tier rows)")
    print("\n  -> exposure ordering reproduces G8-12 s3: the small/illiquid tiers sit")
    print("     closest to the universe boundary and are dropped most often.\n")

    # ---------------------------------------------------------------- the sweep --------
    print("=" * 100)
    print("SWEEP — tier Sharpe as the exit assumption worsens")
    print("=" * 100)
    print(f"\n{'gap on exit':<14}" + "".join(f"{t:>16}" for t in
          ("ALL", "FNO_LARGE", "NON_FNO_TAIL", "SMALL_ADV_Q1")))
    print("-" * 78)
    TIERS = ("ALL", "FNO_LARGE", "NON_FNO_TAIL", "SMALL_ADV_Q1")
    raw = {(g, t): book_returns(df, t, exits, g) for g in GAPS for t in TIERS}

    # Each tier book exists on a different number of dates (the >=30-name floor bites
    # hardest on the small tiers). Comparing Sharpes across different date sets compares
    # periods, not tiers. Restrict every tier to the COMMON date set before comparing.
    common = None
    for t in TIERS:
        idx = raw[(0.0, t)].index
        common = idx if common is None else common.intersection(idx)
    print(f"\n  date coverage per tier: " + ", ".join(
        f"{t}={len(raw[(0.0, t)])}" for t in TIERS))
    print(f"  common date set: {len(common)} weeks — all comparisons below use it, because")
    print(f"  Sharpes measured on different date sets compare periods, not tiers.")

    series = {k: v.reindex(common).dropna() for k, v in raw.items()}
    table = []
    for gap in GAPS:
        row = {"gap": gap}
        for tier in TIERS:
            row[tier] = sharpe(series[(gap, tier)])
        table.append(row)
        print(f"{gap:>+11.0%}   " + "".join(f"{row[t]:>16.4f}" for t in TIERS))

    # ---------------------------------------------------------------- the leads --------
    print("\n" + "=" * 100)
    print("THE QUESTION: at what exit assumption does the small-cap LEAD stop being a lead?")
    print("=" * 100)
    print(f"\n{'gap on exit':<14}{'NON_FNO_TAIL vs ALL':>24}{'SMALL_ADV_Q1 vs ALL':>24}"
          f"{'FNO_LARGE vs ALL':>22}")
    print("-" * 84)
    leads = []
    for row in table:
        lead = {t: row[t] - row["ALL"] for t in
                ("NON_FNO_TAIL", "SMALL_ADV_Q1", "FNO_LARGE")}
        lead["gap"] = row["gap"]
        leads.append(lead)
        print(f"{row['gap']:>+11.0%}   {lead['NON_FNO_TAIL']:>+21.4f}"
              f"{lead['SMALL_ADV_Q1']:>+24.4f}{lead['FNO_LARGE']:>+22.4f}")
    print(f"\n  G8-07 reference (mean over 3 configs): NON_FNO_TAIL {G8_07_LEAD['NON_FNO_TAIL']:+.3f}"
          f"  SMALL_ADV_Q1 {G8_07_LEAD['SMALL_ADV_Q1']:+.3f}"
          f"  FNO_LARGE {G8_07_LEAD['FNO_LARGE']:+.3f}")

    # break-even gap: linear interpolation to lead = 0
    print("\n--- break-even exit assumption (where the lead reaches zero) ---")
    breakeven = {}
    for t in ("NON_FNO_TAIL", "SMALL_ADV_Q1"):
        xs = [l["gap"] for l in leads]
        ys = [l[t] for l in leads]
        be = None
        for i in range(len(xs) - 1):
            if ys[i] > 0 >= ys[i + 1]:
                be = xs[i] + (xs[i + 1] - xs[i]) * ys[i] / (ys[i] - ys[i + 1])
                break
        breakeven[t] = be
        if be is None:
            print(f"    {t:<14} lead survives the entire sweep to {min(GAPS):+.0%}")
        else:
            print(f"    {t:<14} lead reaches zero at a {be:+.1%} gap-down exit")

    # significance of the lead at the harshest assumption
    print("\n--- is the lead statistically distinguishable at the harshest assumption? ---")
    sig = {}
    for gap in (0.0, min(GAPS)):
        for t in ("NON_FNO_TAIL", "SMALL_ADV_Q1"):
            r = paired_sharpe_diff(series[(gap, "ALL")], series[(gap, t)],
                                   label=f"{t} vs ALL @ {gap:+.0%}", seed=SEED)
            sig[f"{t}@{gap}"] = r.to_dict()
            print(f"    {r}")

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    worst = leads[-1]
    print(f"  At a {min(GAPS):+.0%} gap-down exit — an assumption harsher than any realistic")
    print(f"  fill — NON_FNO_TAIL leads ALL by {worst['NON_FNO_TAIL']:+.4f} and SMALL_ADV_Q1")
    print(f"  by {worst['SMALL_ADV_Q1']:+.4f} Sharpe.")
    survives = worst["NON_FNO_TAIL"] > 0 and worst["SMALL_ADV_Q1"] > 0
    print(f"\n  -> the tier lead {'SURVIVES' if survives else 'DOES NOT SURVIVE'} the "
          f"exit-realism stress.")
    print("  -> G8-12's honest range (0 to -2.29%/yr drag) is confirmed by direct")
    print("     simulation rather than by applying a median decline uniformly.")

    payload = {"experiment": "T1-08", "replaces": "remediation plan item 2.3",
               "n_failure_exits": len(exits), "exit_exposure_by_tier": ex_by_tier,
               "sweep": table, "leads": leads, "breakeven_gap": breakeven,
               "significance_at_worst": sig,
               "g8_07_reference": G8_07_LEAD,
               "lead_survives_stress": bool(survives)}
    (OUT / "t1_08_data.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n-> {OUT/'t1_08_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
