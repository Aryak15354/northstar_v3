#!/usr/bin/env python3
"""T1-13 — G8-07's tier sweep on a common date index, all 3 configs, NET of cost.

T1-11's own prescribed next step, and the thing that settles whether its reversal is
decision-grade. T1-11 was one config on gross returns; cost specifically penalises the
least-liquid tier, i.e. works against SMALL_ADV_Q1 — the tier T1-11 elevated.

METHOD NOTE (this is the part that matters):
`g8_07_capital_scale_sweep.backtest` is STATEFUL — `lbook`/`sbook` evolve across dates and
the rebalance fires on `i % 4 == 0`. Filtering the input dates would therefore change the
STRATEGY, not just the evaluation window. So each (config, tier) is run over the FULL panel
exactly as G8-07 runs it, and only the resulting net-return SERIES is restricted to the
common index. Strategy unchanged; comparison made like-for-like.

The tier's date set is set by `if len(g) < 20: continue` — NON_FNO_TAIL simply does not have
20 names in the early panel, which is where its 712-vs-1070 asymmetry comes from.

Reuses G8-07's own CONFIGS, apply_tier, cost model and book rules verbatim so this is a
re-evaluation of that experiment, not a reimplementation of it.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/kaggle/plan_2026_05_18_production"))
sys.path.insert(0, str(ROOT / "scripts/gen8"))

from g8_07_capital_scale_sweep import (  # noqa: E402
    load_panel, apply_tier, short_q1, trade_cost_fraction, long_secbal,
    CONFIGS, UNIVERSE_TIERS, LOCK, ANN, SHORT_COST_WK,
)
from src.research.gen10.inference import paired_sharpe_diff, sharpe  # noqa: E402

OUT = ROOT / "results/gen10/T1-13"
OUT.mkdir(parents=True, exist_ok=True)
SEED = 20260731
CAPITALS_CR = [1.0, 10.0, 100.0]        # small / mid / institutional
ANN_SQ = np.sqrt(52.0)


def backtest_series(df, cfg, fund_inr, tier):
    """G8-07's backtest, verbatim, except it RETURNS THE WEEKLY NET SERIES instead of a
    summary. Every rule below is copied from `g8_07_capital_scale_sweep.backtest`."""
    dates = sorted(df["date"].unique())
    lbook, sbook = set(), set()
    net = {}
    for i, d in enumerate(dates):
        g_all = df[df["date"] == d]
        g = apply_tier(g_all, tier)
        if len(g) < 20:                                   # <-- the truncation mechanism
            continue
        adv = dict(zip(g_all["ticker"], pd.to_numeric(g_all["adv_13w"], errors="coerce")))
        m = float(pd.to_numeric(g_all["target_1w"], errors="coerce").mean())
        lr = pd.to_numeric(g_all[g_all["ticker"].isin(lbook)]["target_1w"],
                           errors="coerce").dropna()
        long_ret = float(lr.mean()) if len(lr) else m
        sr = pd.to_numeric(g_all[g_all["ticker"].isin(sbook)]["target_1w"],
                           errors="coerce").dropna()
        short_ret = (-float(sr.mean()) - SHORT_COST_WK) if len(sr) else 0.0
        cost = 0.0
        if i % 4 == 0:
            gg = g.dropna(subset=["composite"])
            if len(gg) >= 50:
                newl = cfg["long"](gg)
                if cfg.get("band"):
                    ext = gg["composite"].quantile(0.4 if cfg["long"] is long_secbal else 0.6)
                    newl = (set(gg[gg["composite"] >= ext]["ticker"]) & lbook) | newl
                nL = max(len(newl), 1)
                notional = fund_inr / nL
                cost += trade_cost_fraction(newl.symmetric_difference(lbook), notional,
                                            adv, fund_inr)
                lbook = newl
                if cfg.get("short_q1"):
                    news = short_q1(gg)
                    nS = max(len(news), 1)
                    cost += cfg["short_ratio"] * trade_cost_fraction(
                        news.symmetric_difference(sbook), fund_inr / nS, adv, fund_inr)
                    sbook = news
        net[d] = (long_ret + cfg.get("short_ratio", 0.0) * short_ret) - cost
    s = pd.Series(net).sort_index()
    return s[s.index < LOCK].dropna()


def sh(r):
    return float((r.mean() * 52) / (r.std() * ANN_SQ + 1e-12)) if len(r) > 2 else np.nan


def main() -> int:
    print("=" * 104)
    print("T1-13 — TIER SWEEP: COMMON DATES x 3 CONFIGS x NET OF COST")
    print("=" * 104)
    df = load_panel()
    print(f"panel: {len(df):,} rows | {df['date'].nunique()} dates | "
          f"{df['ticker'].nunique()} tickers\n")

    series = {}
    for cname, cfg in CONFIGS.items():
        for tname, tier in UNIVERSE_TIERS.items():
            for cap in CAPITALS_CR:
                series[(cname, tname, cap)] = backtest_series(df, cfg, cap * 1e7, tier)
        print(f"  ran {cname}: " + ", ".join(
            f"{t}={len(series[(cname,t,CAPITALS_CR[0])])}w" for t in UNIVERSE_TIERS))

    # ---- the common index, per (config, capital) ------------------------------------
    print("\n" + "=" * 104)
    print("COMMON-DATE RESTRICTION (Rule 6)")
    print("=" * 104)
    commons = {}
    for cname in CONFIGS:
        for cap in CAPITALS_CR:
            idx = None
            for tname in UNIVERSE_TIERS:
                s = series[(cname, tname, cap)].index
                idx = s if idx is None else idx.intersection(s)
            commons[(cname, cap)] = idx
    c0 = commons[(list(CONFIGS)[0], CAPITALS_CR[0])]
    print(f"  native weeks by tier (config-invariant): " + ", ".join(
        f"{t}={len(series[(list(CONFIGS)[0], t, CAPITALS_CR[0])])}" for t in UNIVERSE_TIERS))
    print(f"  common index: {len(c0)} weeks ({c0.min().date()} .. {c0.max().date()})")

    # ---- results ---------------------------------------------------------------------
    rows = []
    for cap in CAPITALS_CR:
        print("\n" + "=" * 104)
        print(f"CAPITAL Rs{cap:g}cr — NET of cost")
        print("=" * 104)
        print(f"{'config':<26}{'tier':<15}{'native Sh':>11}{'common Sh':>11}"
              f"{'lead native':>13}{'lead common':>13}")
        print("-" * 89)
        for cname in CONFIGS:
            idx = commons[(cname, cap)]
            base_n = sh(series[(cname, "ALL", cap)])
            base_c = sh(series[(cname, "ALL", cap)].reindex(idx).dropna())
            for tname in UNIVERSE_TIERS:
                s = series[(cname, tname, cap)]
                n_sh, c_sh = sh(s), sh(s.reindex(idx).dropna())
                rows.append({"config": cname, "tier": tname, "capital_cr": cap,
                             "n_native": len(s), "n_common": len(idx),
                             "sharpe_native": n_sh, "sharpe_common": c_sh,
                             "lead_native": n_sh - base_n, "lead_common": c_sh - base_c})
                mark = "" if tname == "ALL" else f"{n_sh-base_n:>+13.4f}{c_sh-base_c:>+13.4f}"
                print(f"{cname:<26}{tname:<15}{n_sh:>11.4f}{c_sh:>11.4f}{mark}")

    # ---- the headline: mean lead across configs, native vs common --------------------
    print("\n" + "=" * 104)
    print("HEADLINE — mean tier lead vs ALL, averaged across the 3 configs")
    print("=" * 104)
    R = pd.DataFrame(rows)
    for cap in CAPITALS_CR:
        sub = R[(R.capital_cr == cap) & (R.tier != "ALL")]
        agg = sub.groupby("tier")[["lead_native", "lead_common"]].mean()
        print(f"\n  Rs{cap:g}cr")
        print(f"    {'tier':<15}{'lead native':>13}{'lead common':>13}   configs won (common)")
        for t in ["FNO_LARGE", "NON_FNO_TAIL", "SMALL_ADV_Q1"]:
            won = int((sub[sub.tier == t]["lead_common"] > 0).sum())
            print(f"    {t:<15}{agg.loc[t,'lead_native']:>+13.4f}"
                  f"{agg.loc[t,'lead_common']:>+13.4f}   {won}/3")
    print(f"\n  G8-07 reported (native, gross-ish, mean over configs): "
          f"NON_FNO_TAIL +0.296, SMALL_ADV_Q1 +0.222, FNO_LARGE -0.153")

    # ---- significance on the common index, at Rs10cr ---------------------------------
    print("\n" + "=" * 104)
    print("SIGNIFICANCE on the common index (Rs10cr, paired vs ALL, per config)")
    print("=" * 104)
    sig = {}
    for cname in CONFIGS:
        idx = commons[(cname, 10.0)]
        a = series[(cname, "ALL", 10.0)].reindex(idx).dropna()
        for t in ["NON_FNO_TAIL", "SMALL_ADV_Q1"]:
            b = series[(cname, t, 10.0)].reindex(idx).dropna()
            j = a.index.intersection(b.index)
            r = paired_sharpe_diff(a.reindex(j), b.reindex(j), label=f"{cname[:18]} {t}",
                                   seed=SEED)
            sig[f"{cname}|{t}"] = r.to_dict()
            print(f"    {r}")

    # ---- verdict ----------------------------------------------------------------------
    print("\n" + "=" * 104)
    print("VERDICT")
    print("=" * 104)
    mid = R[(R.capital_cr == 10.0) & (R.tier != "ALL")].groupby("tier")["lead_common"].mean()
    nf, sm = mid["NON_FNO_TAIL"], mid["SMALL_ADV_Q1"]
    print(f"  At Rs10cr, net of cost, on a common date index, averaged over 3 configs:")
    print(f"    NON_FNO_TAIL vs ALL : {nf:+.4f}")
    print(f"    SMALL_ADV_Q1 vs ALL : {sm:+.4f}")
    flipped = sm > nf
    print(f"\n  ordering: {'SMALL_ADV_Q1 > NON_FNO_TAIL' if flipped else 'NON_FNO_TAIL > SMALL_ADV_Q1'}")
    print(f"  T1-11 (1 config, gross) found SMALL_ADV_Q1 > NON_FNO_TAIL.")
    print(f"  --> T1-11's reversal {'HOLDS' if flipped else 'DOES NOT HOLD'} net of cost.")

    payload = {"experiment": "T1-13", "capitals_cr": CAPITALS_CR,
               "common_weeks": int(len(c0)), "rows": rows, "significance_10cr": sig,
               "t1_11_reversal_holds_net": bool(flipped)}
    (OUT / "t1_13_data.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n-> {OUT/'t1_13_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
