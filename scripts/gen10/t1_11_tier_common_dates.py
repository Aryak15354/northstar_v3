#!/usr/bin/env python3
"""T1-11 — Is G8-07's tier lead confounded by date coverage, and does G8-11's correction survive?

T1-08 found SMALL_ADV_Q1 leading NON_FNO_TAIL on a common date set, the reverse of G8-11's
conclusion that "non-F&O tail is the real source" of the small-cap advantage. Reading
G8-07's own output shows why that is possible:

    universe        n_weeks
    ALL               1070
    FNO_LARGE         1070
    SMALL_ADV_Q1      1070
    NON_FNO_TAIL       712   <-- 358 fewer weeks than everything it is compared against

`g8_07_capital_scale_sweep.backtest` computes `r = s_net[pre].dropna()` per config x tier, so
each tier's Sharpe is measured on whatever dates that tier had a book. **SMALL_ADV_Q1's
+0.222 lead is like-for-like (1070 vs 1070). NON_FNO_TAIL's +0.296 lead is not.**

This quantifies the confound directly: which 712 weeks are they, and what does the ALL tier
score on exactly those weeks?

No new hypothesis. A measurement check on an existing confirmed finding.
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

OUT = ROOT / "results/gen10/T1-11"
OUT.mkdir(parents=True, exist_ok=True)
LOCKBOX = pd.Timestamp("2025-07-10")
MIN_NAMES = 30
TOPQ = 0.80
SEED = 20260731
G8_07 = {"ALL": 0.717385, "FNO_LARGE": 0.564590,
         "NON_FNO_TAIL": 1.013631, "SMALL_ADV_Q1": 0.939453}
G8_07_NWEEKS = {"ALL": 1070, "FNO_LARGE": 1070, "NON_FNO_TAIL": 712, "SMALL_ADV_Q1": 1070}


def load() -> pd.DataFrame:
    d = pd.read_parquet(ROOT / "data/kaggle_upload/panel_a_weekly.parquet",
                        columns=["date", "ticker", "close", "adv_13w", "target_1w",
                                 "res_mom_52w_ex4w", "ret_52w_ex4w", "sharpe_mom_26w",
                                 "consistency_mom_26w"])
    d["date"] = pd.to_datetime(d["date"]).dt.normalize()
    d = d[(d["date"] <= LOCKBOX) & (pd.to_numeric(d["close"], errors="coerce") >= 20)].copy()
    # G8-07's composite: mean of the four validated momentum z-scores
    z = []
    for c in ("res_mom_52w_ex4w", "ret_52w_ex4w", "sharpe_mom_26w", "consistency_mom_26w"):
        g = d.groupby("date")[c]
        z.append((d[c] - g.transform("mean")) / g.transform("std").replace(0, np.nan))
    d["composite"] = pd.concat(z, axis=1).mean(axis=1)
    d = d.dropna(subset=["composite"])
    d["adv_rank"] = d.groupby("date")["adv_13w"].rank(ascending=False)
    d["fno_ok"] = d["adv_rank"] <= 190
    d["adv_q"] = d.groupby("date")["adv_13w"].transform(
        lambda s: pd.qcut(s.rank(method="first"), 5, labels=False, duplicates="drop"))
    return d


def tier_mask(d, tier):
    return {"ALL": pd.Series(True, index=d.index), "FNO_LARGE": d["fno_ok"],
            "NON_FNO_TAIL": ~d["fno_ok"], "SMALL_ADV_Q1": d["adv_q"] == 0}[tier]


def book(d: pd.DataFrame, tier: str) -> pd.Series:
    sub = d[tier_mask(d, tier)]
    out = {}
    for dt, g in sub.groupby("date"):
        s = g[["composite", "target_1w"]].dropna()
        if len(s) < MIN_NAMES:
            continue
        out[dt] = float(s.loc[s["composite"] >= s["composite"].quantile(TOPQ),
                              "target_1w"].mean())
    return pd.Series(out).sort_index()


def main() -> int:
    print("=" * 96)
    print("T1-11 — TIER COMPARISON ON COMMON DATES")
    print("=" * 96)
    d = load()
    TIERS = ["ALL", "FNO_LARGE", "NON_FNO_TAIL", "SMALL_ADV_Q1"]
    books = {t: book(d, t) for t in TIERS}

    print("\n--- 1. date coverage per tier (reproducing G8-07's asymmetry) ---")
    print(f"{'tier':<15}{'this run':>10}{'G8-07':>9}   {'span'}")
    for t in TIERS:
        b = books[t]
        print(f"{t:<15}{len(b):>10}{G8_07_NWEEKS[t]:>9}   "
              f"{b.index.min().date()} .. {b.index.max().date()}")

    common = books["NON_FNO_TAIL"].index
    for t in TIERS:
        common = common.intersection(books[t].index)
    print(f"\n  common date set: {len(common)} weeks "
          f"({common.min().date()} .. {common.max().date()})")

    # ---- 2. WHICH weeks are missing, and are they systematically different? -----------
    print("\n--- 2. are the excluded weeks systematically different? ---")
    all_dates = books["ALL"].index
    missing = all_dates.difference(common)
    print(f"    weeks in ALL but not in the common set: {len(missing)}")
    if len(missing):
        by_year_missing = pd.Series(1, index=missing).groupby(missing.year).sum()
        by_year_common = pd.Series(1, index=common).groupby(common.year).sum()
        yrs = sorted(set(by_year_missing.index) | set(by_year_common.index))
        print(f"    {'year':<7}{'in common':>11}{'excluded':>11}")
        for y in yrs:
            print(f"    {y:<7}{int(by_year_common.get(y,0)):>11}"
                  f"{int(by_year_missing.get(y,0)):>11}")
        rc = books["ALL"].reindex(common).dropna()
        rm = books["ALL"].reindex(missing).dropna()
        print(f"\n    ALL tier on the COMMON weeks   : Sharpe {sharpe(rc):+.4f}  "
              f"mean {rm.mean()*52:+.2%}/yr" if False else
              f"\n    ALL tier on the COMMON weeks   : Sharpe {sharpe(rc):+.4f}  "
              f"ann ret {rc.mean()*52:+.2%}")
        print(f"    ALL tier on the EXCLUDED weeks : Sharpe {sharpe(rm):+.4f}  "
              f"ann ret {rm.mean()*52:+.2%}")
        print("    -> if the excluded weeks are WORSE, every tier measured only on the")
        print("       common set gets a free boost that ALL (measured on all weeks) does not.")

    # ---- 3. the leads, native vs common ------------------------------------------------
    print("\n--- 3. tier lead vs ALL: native date sets vs common date set ---")
    print(f"{'tier':<15}{'native Sh':>11}{'common Sh':>11}{'ALL native':>12}"
          f"{'ALL common':>12}{'lead native':>13}{'lead common':>13}")
    print("-" * 87)
    sh_all_native = sharpe(books["ALL"])
    sh_all_common = sharpe(books["ALL"].reindex(common).dropna())
    rows = []
    for t in TIERS:
        if t == "ALL":
            continue
        n_sh = sharpe(books[t])
        c_sh = sharpe(books[t].reindex(common).dropna())
        rows.append({"tier": t, "native_sharpe": n_sh, "common_sharpe": c_sh,
                     "lead_native": n_sh - sh_all_native,
                     "lead_common": c_sh - sh_all_common,
                     "n_native": len(books[t]), "n_common": len(common)})
        print(f"{t:<15}{n_sh:>11.4f}{c_sh:>11.4f}{sh_all_native:>12.4f}"
              f"{sh_all_common:>12.4f}{n_sh-sh_all_native:>+13.4f}"
              f"{c_sh-sh_all_common:>+13.4f}")

    # ---- 4. significance on the common set --------------------------------------------
    print("\n--- 4. significance of each lead on the common date set ---")
    sig = {}
    a = books["ALL"].reindex(common).dropna()
    for r in rows:
        b = books[r["tier"]].reindex(common).dropna()
        idx = a.index.intersection(b.index)
        res = paired_sharpe_diff(a.reindex(idx), b.reindex(idx),
                                 label=f"{r['tier']} vs ALL", seed=SEED)
        sig[r["tier"]] = res.to_dict()
        r["t"] = float(res.t)
        print(f"    {res}")

    # ---- 5. verdict --------------------------------------------------------------------
    print("\n" + "=" * 96)
    print("VERDICT")
    print("=" * 96)
    nf = next(r for r in rows if r["tier"] == "NON_FNO_TAIL")
    sm = next(r for r in rows if r["tier"] == "SMALL_ADV_Q1")
    print(f"  G8-07 measured NON_FNO_TAIL on {G8_07_NWEEKS['NON_FNO_TAIL']} weeks against "
          f"ALL's {G8_07_NWEEKS['ALL']}.")
    print(f"  SMALL_ADV_Q1 was measured on {G8_07_NWEEKS['SMALL_ADV_Q1']} — like-for-like.\n")
    print(f"  NON_FNO_TAIL lead: {nf['lead_native']:+.4f} native  ->  "
          f"{nf['lead_common']:+.4f} on common dates  (t={nf['t']:+.2f})")
    print(f"  SMALL_ADV_Q1 lead: {sm['lead_native']:+.4f} native  ->  "
          f"{sm['lead_common']:+.4f} on common dates  (t={sm['t']:+.2f})")
    flipped = sm["lead_common"] > nf["lead_common"]
    print(f"\n  ordering on common dates: "
          f"{'SMALL_ADV_Q1 > NON_FNO_TAIL' if flipped else 'NON_FNO_TAIL > SMALL_ADV_Q1'}")
    print(f"  G8-11 concluded: NON_FNO_TAIL is the real source, not the micro-cap tier.")
    print(f"  --> G8-11's correction {'DOES NOT survive' if flipped else 'SURVIVES'} "
          f"the common-date check.")

    payload = {"experiment": "T1-11", "g8_07_reported": G8_07,
               "g8_07_n_weeks": G8_07_NWEEKS, "n_common": int(len(common)),
               "all_sharpe_native": sh_all_native, "all_sharpe_common": sh_all_common,
               "rows": rows, "significance_common": sig,
               "g8_11_survives": bool(not flipped)}
    (OUT / "t1_11_data.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n-> {OUT/'t1_11_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
