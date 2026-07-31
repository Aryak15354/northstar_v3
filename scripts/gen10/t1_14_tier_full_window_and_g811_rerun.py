#!/usr/bin/env python3
"""T1-14 — the two remaining tier questions.

PART A. T1-13's common index was 712 weeks, bounded by the weakest tier. Drop
NON_FNO_TAIL and the other three tiers each have 1,070 weeks natively — but "same count"
is not "same dates" (Rule 6), so that is verified rather than assumed before comparing.
Question: does SMALL_ADV_Q1's lead hold on the longer window, net of cost, 3 configs?

PART B. G8-11's 17-signal battery is the only remaining path to a properly-measured answer
on where in the size distribution the edge sits, and it has never been evaluated cleanly.
Its `backtest` records `port = 0.0` for weeks a tier cannot form a book — 41.8% of
NON_FNO_TAIL's sample. This re-runs it with those weeks EXCLUDED rather than zero-filled,
which is the fix G8-11's own annotation now prescribes.

Both reuse the original scripts' own constants, signals, directions and cost model, so
these are re-evaluations rather than reimplementations.
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
sys.path.insert(0, str(ROOT / "scripts/gen10"))

from g8_07_capital_scale_sweep import load_panel, CONFIGS  # noqa: E402
from src.pnl.indian_cost_model import IndianEquityCostModel  # noqa: E402
from src.research.gen10.inference import paired_sharpe_diff  # noqa: E402
from t1_13_tier_sweep_common_dates_net import backtest_series  # noqa: E402

OUT = ROOT / "results/gen10/T1-14"
OUT.mkdir(parents=True, exist_ok=True)
SEED = 20260731
ANN_SQ = np.sqrt(52.0)
LOCK = pd.Timestamp("2025-07-11")
TOPQ = 0.80
CM = IndianEquityCostModel()

TIERS_A = ["ALL", "FNO_LARGE", "SMALL_ADV_Q1"]          # the three with native 1,070w
TIER_KEY = {"ALL": None, "FNO_LARGE": "fno", "NON_FNO_TAIL": "nonfno", "SMALL_ADV_Q1": "smallq"}

# G8-11's signal set and FIXED directions, copied verbatim
SIGNALS = {
    "res_mom_52w_ex4w": +1, "ret_52w_ex4w": +1, "ret_26w": +1, "ret_13w": +1,
    "ret_4w": -1, "ret_1w": -1, "sharpe_mom_26w": +1, "consistency_mom_26w": +1,
    "high_52w_prox": +1, "vol_13w": -1, "vol_52w": -1, "idio_vol_13w": -1,
    "beta_104w": -1, "skew_26w": -1, "max5_4w": -1, "amihud_13w": +1,
    "abnormal_volume_4w": -1,
}


def sh(r):
    return float((r.mean() * 52) / (r.std() * ANN_SQ + 1e-12)) if len(r) > 2 else np.nan


def tier_mask(g, tier):
    k = TIER_KEY[tier]
    if k is None:
        return pd.Series(True, index=g.index)
    return {"fno": g["fno_ok"], "nonfno": ~g["fno_ok"], "smallq": g["adv_q"] == 0}[k]


# ---------------------------------------------------------------- PART A -------------
def part_a(df):
    print("=" * 100)
    print("PART A — SMALL_ADV_Q1 on the full 1,070-week window (NON_FNO_TAIL dropped)")
    print("=" * 100)
    series = {}
    for cname, cfg in CONFIGS.items():
        for t in TIERS_A:
            series[(cname, t)] = backtest_series(df, cfg, 10.0 * 1e7, TIER_KEY[t])

    print("\n--- date-set verification (Rule 6: same count is not same dates) ---")
    ok_all = True
    for cname in CONFIGS:
        idx = {t: series[(cname, t)].index for t in TIERS_A}
        same = {t: bool(idx["ALL"].equals(idx[t])) for t in TIERS_A}
        print(f"  {cname:<26} counts={ {t: len(idx[t]) for t in TIERS_A} }  "
              f"identical_to_ALL={same}")
        ok_all &= all(same.values())
    print(f"  -> all three tiers share an identical date index: {ok_all}")

    print("\n--- lead vs ALL, net of cost, Rs10cr, full window ---")
    print(f"{'config':<26}{'FNO_LARGE':>12}{'SMALL_ADV_Q1':>14}")
    rows, sig = [], {}
    for cname in CONFIGS:
        idx = series[(cname, "ALL")].index
        for t in TIERS_A:
            idx = idx.intersection(series[(cname, t)].index)
        a = series[(cname, "ALL")].reindex(idx).dropna()
        line = {}
        for t in ["FNO_LARGE", "SMALL_ADV_Q1"]:
            b = series[(cname, t)].reindex(idx).dropna()
            j = a.index.intersection(b.index)
            lead = sh(b.reindex(j)) - sh(a.reindex(j))
            line[t] = lead
            r = paired_sharpe_diff(a.reindex(j), b.reindex(j), label=f"{cname[:18]} {t}",
                                   seed=SEED)
            sig[f"{cname}|{t}"] = r.to_dict()
            rows.append({"config": cname, "tier": t, "n_weeks": int(len(j)),
                         "lead": float(lead), "t": float(r.t), "p": float(r.p),
                         "fragile": bool(r.fragile)})
        print(f"{cname:<26}{line['FNO_LARGE']:>+12.4f}{line['SMALL_ADV_Q1']:>+14.4f}")

    R = pd.DataFrame(rows)
    mean_lead = R.groupby("tier")["lead"].mean()
    print(f"\n  mean over 3 configs — SMALL_ADV_Q1 {mean_lead['SMALL_ADV_Q1']:+.4f}, "
          f"FNO_LARGE {mean_lead['FNO_LARGE']:+.4f}   (n={rows[0]['n_weeks']} weeks)")
    print("  T1-13 on the 712-week common index: SMALL_ADV_Q1 +0.279")
    print("\n--- significance, per config ---")
    for k, v in sig.items():
        if "SMALL" in k:
            print(f"    {k:<40} t={v['t']:+.2f}  p={v['p']:.4f}  "
                  f"boot=[{v['boot_ci_lo']:+.3f},{v['boot_ci_hi']:+.3f}]"
                  f"{'  FRAGILE' if v['fragile'] else ''}")
    return {"identical_index": bool(ok_all), "rows": rows,
            "mean_lead": {k: float(v) for k, v in mean_lead.items()}, "significance": sig}


# ---------------------------------------------------------------- PART B -------------
def bt_signal(groups, signal, direction, tier, fund_inr, exclude_empty: bool):
    """G8-11's backtest. `exclude_empty=False` reproduces it verbatim (zero-fill);
    `exclude_empty=True` applies the fix — weeks in which the tier holds nothing are
    OMITTED rather than recorded as a 0.0% return."""
    book, net, n_empty = set(), {}, 0
    for i, (d, g) in enumerate(groups):
        sub = g[tier_mask(g, tier)]
        held = g[g["ticker"].isin(book)]
        r = pd.to_numeric(held["target_1w"], errors="coerce").dropna()
        empty = len(r) == 0
        port = float(r.mean()) if len(r) else 0.0
        cost = 0.0
        if i % 4 == 0:
            gg = sub.dropna(subset=[signal])
            if len(gg) >= 40:
                s = direction * pd.to_numeric(gg[signal], errors="coerce")
                thr, exit_thr = s.quantile(TOPQ), s.quantile(0.60)
                new = set(gg["ticker"][s >= thr])
                new |= (set(gg["ticker"][s >= exit_thr]) & book)
                n = max(len(new), 1)
                notional = fund_inr / n
                adv = dict(zip(g["ticker"], pd.to_numeric(g["adv_13w"], errors="coerce")))
                tot = 0.0
                for tk in new.symmetric_difference(book):
                    a = adv.get(tk, np.nan)
                    a = float(a) if np.isfinite(a) else None
                    tot += CM.cost_breakdown("SELL", notional, adv_inr=a).total
                    tot += CM.cost_breakdown("BUY", notional, adv_inr=a).total
                cost = tot / fund_inr / 2.0
                book = new
        if empty:
            n_empty += 1
            if exclude_empty:
                continue
        net[d] = port - cost
    s = pd.Series(net).sort_index()
    return s[s.index < LOCK].dropna(), n_empty


def part_b(df):
    print("\n" + "=" * 100)
    print("PART B — G8-11's 17-signal battery, empty-book weeks EXCLUDED not zero-filled")
    print("=" * 100)
    groups = list(df.groupby("date"))
    tiers = ["ALL", "FNO_LARGE", "NON_FNO_TAIL", "SMALL_ADV_Q1"]
    fund = 10.0 * 1e7
    res = {}
    for sig_name, direction in SIGNALS.items():
        for t in tiers:
            s_fix, n_empty = bt_signal(groups, sig_name, direction, t, fund, True)
            s_orig, _ = bt_signal(groups, sig_name, direction, t, fund, False)
            res[(sig_name, t)] = {"fixed": s_fix, "orig": s_orig, "n_empty": n_empty}
        print(f"  {sig_name:<22} done")

    print("\n--- mean Sharpe by tier: G8-11's method vs empty-weeks-excluded ---")
    print(f"{'tier':<15}{'zero-filled':>13}{'excluded':>11}{'delta':>9}{'mean n_empty':>14}")
    summary = {}
    for t in tiers:
        z = float(np.nanmean([sh(res[(s, t)]["orig"]) for s in SIGNALS]))
        e = float(np.nanmean([sh(res[(s, t)]["fixed"]) for s in SIGNALS]))
        ne = float(np.mean([res[(s, t)]["n_empty"] for s in SIGNALS]))
        summary[t] = {"zero_filled": z, "excluded": e, "mean_n_empty": ne}
        print(f"{t:<15}{z:>13.4f}{e:>11.4f}{e-z:>+9.4f}{ne:>14.0f}")

    print("\n--- tier beats ALL in how many of 17 signals? (each pair on shared dates) ---")
    print(f"{'tier':<15}{'zero-filled':>16}{'excluded':>14}")
    counts = {}
    for t in ["FNO_LARGE", "NON_FNO_TAIL", "SMALL_ADV_Q1"]:
        wz = we = 0
        for s in SIGNALS:
            for key, tag in (("orig", "z"), ("fixed", "e")):
                a, b = res[(s, "ALL")][key], res[(s, t)][key]
                j = a.index.intersection(b.index)
                if len(j) < 52:
                    continue
                d = sh(b.reindex(j)) - sh(a.reindex(j))
                if tag == "z" and d > 0:
                    wz += 1
                elif tag == "e" and d > 0:
                    we += 1
        counts[t] = {"zero_filled_wins": wz, "excluded_wins": we}
        print(f"{t:<15}{str(wz)+' / 17':>16}{str(we)+' / 17':>14}")
    print("\n  G8-11 published: NON_FNO_TAIL 16/17 (sign test p=0.00027), "
          "SMALL_ADV_Q1 5/17, FNO_LARGE 0/17")

    from scipy import stats as st
    print("\n--- sign test on the corrected counts ---")
    for t, c in counts.items():
        c["sign_test_p"] = float(st.binomtest(c["excluded_wins"], 17, 0.5).pvalue)
        print(f"    {t:<15} {c['excluded_wins']}/17  sign-test p = {c['sign_test_p']:.5f}")
    return {"summary": summary, "counts": counts}


def main() -> int:
    print("=" * 100)
    print("T1-14 — TIER: FULL-WINDOW CHECK AND G8-11 RE-RUN")
    print("=" * 100)
    df = load_panel()
    print(f"panel: {len(df):,} rows | {df['date'].nunique()} dates\n")
    a = part_a(df)
    b = part_b(df)

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    print(f"  A. SMALL_ADV_Q1 lead on the full window: "
          f"{a['mean_lead']['SMALL_ADV_Q1']:+.4f}  (712w common index gave +0.279)")
    nf, sm = b["counts"]["NON_FNO_TAIL"], b["counts"]["SMALL_ADV_Q1"]
    print(f"  B. G8-11 with empty weeks excluded: NON_FNO_TAIL {nf['excluded_wins']}/17 "
          f"(reproduced zero-filled: {nf['zero_filled_wins']}/17; published 16/17); "
          f"SMALL_ADV_Q1 {sm['excluded_wins']}/17")

    (OUT / "t1_14_data.json").write_text(json.dumps({"part_a": a, "part_b": b},
                                                    indent=2, default=str))
    print(f"\n-> {OUT/'t1_14_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
