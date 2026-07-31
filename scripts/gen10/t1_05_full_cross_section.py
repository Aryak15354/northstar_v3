#!/usr/bin/env python3
"""T1-05'' — Paper B Sub-study 2a with a full-cross-section estimator.

T0-01 left 2a UNRESOLVED: corrected t=+2.52 at 4w with a coherent monotone effect, but it
fails the pre-registered BY correction, and settling it by waiting needs 9.7 more years.
The remaining route is a MORE EFFICIENT ESTIMATOR on the same data.

The original design is wasteful by construction. It compares the top and bottom terciles
of consistency WITHIN the top tercile of trend - so it discards a third of names on the
consistency axis and two thirds on the trend axis, using roughly 22% of each week's
cross-section.

Two estimators that use all of it:
  E1  conditional IC : per-date Spearman IC of consistency vs forward return, within the
                       High-Trend tercile. Uses every High-Trend name.
  E2  Fama-MacBeth   : per-date OLS of forward return on [trend_rank, cons_rank,
                       trend x cons], full cross-section. The INTERACTION coefficient is
                       the "Confirms" hypothesis stated as a continuous effect.

MULTIPLICITY, STATED HONESTLY. This is a second look at data already tested in T0-01.
The family is T0-01's 9 tests plus these 8 (2 estimators x 4 horizons) = 17. A claim to
have ESTABLISHED 2a must clear BY at m=17, not at m=8. Both are reported.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.research.gen10.inference import (  # noqa: E402
    nw_mean_test, per_date_ic, benjamini_yekutieli,
)

OUT = ROOT / "results/gen10/T1-05"
OUT.mkdir(parents=True, exist_ok=True)
LOCK = pd.Timestamp("2025-07-11")
TREND, CONS = "res_mom_52w_ex4w", "consistency_mom_26w"
HORIZONS = [1, 4, 8, 13]
SEED = 20260731
T0_01_M = 9          # tests already spent on this question in T0-01


def frame(window: str = "discovery") -> pd.DataFrame:
    df = pd.read_parquet(ROOT / "data/kaggle_upload/panel_a_weekly.parquet",
                         columns=["date", "ticker", "ret_1w", TREND, CONS])
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df = df[df["date"] < LOCK] if window == "discovery" else df[df["date"] >= LOCK]
    df = df.sort_values(["ticker", "date"]).copy()
    for h in HORIZONS:
        df[f"fwd_{h}"] = df.groupby("ticker")["ret_1w"].transform(
            lambda s: s.shift(-1).rolling(h, min_periods=h).sum().shift(-(h - 1)))
    df = df[df[TREND].notna() & df[CONS].notna()].copy()
    df["trend_tercile"] = df.groupby("date")[TREND].transform(
        lambda s: pd.qcut(s.rank(method="first"), 3, labels=["Low", "Mid", "High"]))
    for c, nm in ((TREND, "trend_r"), (CONS, "cons_r")):
        df[nm] = df.groupby("date")[c].transform(
            lambda s: (s.rank(method="first") - 0.5) / len(s) - 0.5)   # centred [-0.5,0.5]
    return df


def e1_conditional_ic(df, h) -> tuple:
    sub = df[df["trend_tercile"] == "High"]
    s = sub[["date", CONS, f"fwd_{h}"]].dropna()
    ic = per_date_ic(s, "date", CONS, f"fwd_{h}", min_pairs=20)
    return nw_mean_test(ic.to_numpy(), overlap=h, label=f"E1 cond-IC {h}w",
                        n_boot=3000, seed=SEED), len(ic)


def e2_fama_macbeth(df, h) -> tuple:
    """Per-date OLS: fwd ~ a + b1*trend + b2*cons + b3*(trend*cons). Report b3."""
    betas = {}
    for dt, g in df.groupby("date"):
        s = g[["trend_r", "cons_r", f"fwd_{h}"]].dropna()
        if len(s) < 40:
            continue
        X = np.column_stack([np.ones(len(s)), s["trend_r"], s["cons_r"],
                             s["trend_r"] * s["cons_r"]])
        y = s[f"fwd_{h}"].to_numpy()
        try:
            b, *_ = np.linalg.lstsq(X, y, rcond=None)
        except np.linalg.LinAlgError:
            continue
        betas[dt] = float(b[3])
    bs = pd.Series(betas).sort_index()
    return nw_mean_test(bs.to_numpy(), overlap=h, label=f"E2 FM-interaction {h}w",
                        n_boot=3000, seed=SEED), len(bs)


def main() -> int:
    print("=" * 96)
    print("T1-05'' — PAPER B 2a WITH A FULL-CROSS-SECTION ESTIMATOR")
    print("=" * 96)
    df = frame("discovery")
    print(f"discovery panel: {len(df):,} rows | {df['date'].nunique():,} dates\n")

    # how much of the cross-section does the original design actually use?
    hi = df[df["trend_tercile"] == "High"]
    used = len(hi) * (2 / 3) / len(df)
    print(f"original design uses ~{used:.0%} of each week's cross-section "
          f"(top trend tercile x extreme consistency terciles)")
    print(f"E1 uses {len(hi)/len(df):.0%} (all High-Trend names); E2 uses 100%.\n")

    print(f"{'estimator':<24}{'horizon':>9}{'estimate':>13}{'t':>8}{'p':>9}"
          f"{'n_dates':>9}   bootstrap 95% CI")
    print("-" * 96)
    rows = []
    for name, fn in (("E1 conditional IC", e1_conditional_ic),
                     ("E2 Fama-MacBeth", e2_fama_macbeth)):
        for h in HORIZONS:
            r, n = fn(df, h)
            rows.append({"estimator": name, "horizon": h, "estimate": float(r.estimate),
                         "t": float(r.t), "p": float(r.p), "n_dates": int(r.n),
                         "boot_lo": r.boot_ci_lo, "boot_hi": r.boot_ci_hi,
                         "fragile": r.fragile})
            print(f"{name:<24}{h:>8}w{r.estimate:>13.6f}{r.t:>8.2f}{r.p:>9.4f}"
                  f"{r.n:>9}   [{r.boot_ci_lo:+.6f}, {r.boot_ci_hi:+.6f}]"
                  f"{'  FRAGILE' if r.fragile else ''}")

    # ---- multiplicity, both accountings -----------------------------------------------
    pv = [r["p"] for r in rows]
    by_local = benjamini_yekutieli(pv, q=0.05)
    # honest family: T0-01's 9 tests are already spent on this same question
    pv_family = pv + [1.0] * T0_01_M
    by_family = benjamini_yekutieli(pv_family, q=0.05)[:len(pv)]
    print(f"\n--- multiplicity ---")
    print(f"{'test':<30}{'p':>10}{'BY m=8':>10}{'BY m=17':>10}")
    print("(m=8 counts only this experiment; m=17 also counts T0-01's 9 tests on the")
    print(" same question, which is the honest denominator for an ESTABLISHED claim)")
    for r, p, a, b in zip(rows, pv, by_local, by_family):
        r["by_m8"] = bool(a); r["by_m17"] = bool(b)
        print(f"{r['estimator']+' '+str(r['horizon'])+'w':<30}{p:>10.4f}"
              f"{str(bool(a)):>10}{str(bool(b)):>10}")

    # ---- lockbox --------------------------------------------------------------------
    print("\n--- lockbox (53 weeks, never seen by Paper B) ---")
    lb = frame("lockbox")
    lock_rows = []
    for name, fn in (("E1 conditional IC", e1_conditional_ic),
                     ("E2 Fama-MacBeth", e2_fama_macbeth)):
        for h in (4, 8):
            r, n = fn(lb, h)
            lock_rows.append({"estimator": name, "horizon": h,
                              "estimate": float(r.estimate), "t": float(r.t),
                              "n_dates": int(r.n)})
            print(f"    {name:<24}{h:>3}w  est={r.estimate:+.6f}  t={r.t:+.2f}  n={r.n}")

    # ---- verdict ----------------------------------------------------------------------
    best = max(rows, key=lambda r: abs(r["t"]))
    signs = {np.sign(r["estimate"]) for r in rows}
    consistent = len(signs) == 1
    established = any(r["by_m17"] for r in rows) and consistent
    print("\n" + "=" * 96)
    print("VERDICT")
    print("=" * 96)
    print(f"  best: {best['estimator']} at {best['horizon']}w, t={best['t']:+.2f}, "
          f"p={best['p']:.4f}")
    print(f"  sign consistent across all 8 tests: {consistent}")
    print(f"  any test BY-clean at m=8 : {bool(any(r['by_m8'] for r in rows))}")
    print(f"  any test BY-clean at m=17: {bool(any(r['by_m17'] for r in rows))}")
    if established:
        print("\n  --> 2a ESTABLISHED. Proceed to the Gen-5 economic gate.")
    else:
        print("\n  --> 2a REMAINS UNRESOLVED.")
        print("      The more efficient estimator does not rescue it. Two independent")
        print("      designs (extreme-tercile contrast in T0-01, full cross-section here)")
        print("      both find a consistently-signed effect that will not clear a correction")
        print("      for the number of looks taken at it.")
        print("      RECOMMENDATION: close 2a as a documented near-effect and stop looking.")
        print("      Further estimators on the same 985 weeks would be a search, not a test.")

    payload = {"experiment": "T1-05''",
               "cross_section_used": {"original_design": float(used),
                                      "E1": float(len(hi) / len(df)), "E2": 1.0},
               "discovery": rows, "lockbox": lock_rows,
               "multiplicity": {"m_local": len(pv), "m_family": len(pv) + T0_01_M},
               "sign_consistent": bool(consistent), "established": bool(established),
               "verdict": "ESTABLISHED" if established else "UNRESOLVED — close and stop"}
    (OUT / "t1_05_data.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n-> {OUT/'t1_05_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
