#!/usr/bin/env python3
"""T0-01 — AEP Paper B Sub-study 2, standard-error correction.

Re-runs all four candidate roles for consistency_mom_26w with date-clustered / Newey-West
inference instead of the pooled stock-week two-sample t the original used.

The original script (scripts/aep/paper_b_substudy2_conditional_activation.py) computed
    se = sqrt(var(hi)/n_hi + var(lo)/n_lo)
over ~62,000 stock-weeks. Those observations are not independent: forward returns over h
weeks overlap, and stocks within a week share a market factor. This script reproduces that
number exactly (as a control) and reports the corrected one beside it.

Pre-registered in GEN10_REMEDIATION_CHARTER.md s4/T0-01 before running.
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
    date_clustered_group_diff, nw_mean_test, benjamini_yekutieli, benjamini_hochberg,
)

OUT = ROOT / "results/gen10/T0-01"
OUT.mkdir(parents=True, exist_ok=True)

LOCK = pd.Timestamp("2025-07-11")          # identical to the original
TREND_COL = "res_mom_52w_ex4w"
CONS_COL = "consistency_mom_26w"
FWD_HORIZONS = [1, 4, 8, 13]
SEED = 20260731


def load(window: str = "discovery") -> pd.DataFrame:
    """`discovery` reproduces the original's pre-lockbox window exactly.
    `lockbox` is the 53 weeks after 2025-07-11 that Paper B truncated away and never saw."""
    df = pd.read_parquet(ROOT / "data/kaggle_upload/panel_a_weekly.parquet",
                         columns=["date", "ticker", "ret_1w", TREND_COL, CONS_COL])
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    if window == "discovery":
        return df[df["date"] < LOCK].copy()
    if window == "lockbox":
        return df[df["date"] >= LOCK].copy()
    return df.copy()


def stock_level_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Identical construction to the original, so any difference is inference, not data."""
    df = df.sort_values(["ticker", "date"]).copy()
    for h in FWD_HORIZONS:
        df[f"fwd_ret_{h}w"] = df.groupby("ticker")["ret_1w"].transform(
            lambda s: s.shift(-1).rolling(h, min_periods=h).sum().shift(-(h - 1)))
    df = df[df[TREND_COL].notna() & df[CONS_COL].notna()].copy()
    df["trend_tercile"] = df.groupby("date")[TREND_COL].transform(
        lambda s: pd.qcut(s.rank(method="first"), 3, labels=["Low", "Mid", "High"]))
    df["cons_tercile"] = df.groupby("date")[CONS_COL].transform(
        lambda s: pd.qcut(s.rank(method="first"), 3, labels=["Low", "Mid", "High"]))
    return df


def role_test(sdf: pd.DataFrame, trend_state: str, label: str) -> dict:
    """2a Confirms  = High-Trend  x [High-Cons vs Low-Cons]
       2b Warns     = Low-Trend   x [High-Cons vs Low-Cons]"""
    out = {}
    for h in FWD_HORIZONS:
        col = f"fwd_ret_{h}w"
        hi = (sdf["trend_tercile"] == trend_state) & (sdf["cons_tercile"] == "High")
        lo = (sdf["trend_tercile"] == trend_state) & (sdf["cons_tercile"] == "Low")
        r = date_clustered_group_diff(sdf, "date", col, hi, lo, overlap=h,
                                      label=f"{label} {h}w", seed=SEED)
        out[f"{h}w"] = r
        print("   " + str(r))
    return out


def test_c_delays(sdf: pd.DataFrame) -> dict:
    """2c Delays: lead/lag cross-correlation of the two weekly cross-sectional means.
    Reported descriptively, exactly as the original did — a correlation profile, not a
    significance test. Kept so the record covers all four roles."""
    trend_w = sdf.groupby("date")[TREND_COL].mean()
    cons_w = sdf.groupby("date")[CONS_COL].mean()
    both = pd.DataFrame({"trend": trend_w, "cons": cons_w}).dropna()
    out = {}
    for lag in range(-4, 5):
        x = both["trend"].shift(lag) if lag < 0 else both["trend"]
        y = both["cons"].shift(-lag) if lag > 0 else both["cons"]
        j = pd.DataFrame({"x": x, "y": y}).dropna()
        out[str(lag)] = float(j["x"].corr(j["y"])) if len(j) >= 30 else None
    return out


def test_d_exits(sdf: pd.DataFrame) -> dict:
    """2d Accelerates-exits: within High-Trend, does a High->not-High consistency drop
    predict a worse forward 4w return than a stable-High state?"""
    d = sdf.sort_values(["ticker", "date"]).copy()
    d["cons_prev"] = d.groupby("ticker")["cons_tercile"].shift(1)
    base = (d["trend_tercile"] == "High") & (d["cons_prev"] == "High")
    dropped = base & (d["cons_tercile"] != "High")
    stable = base & (d["cons_tercile"] == "High")
    r = date_clustered_group_diff(d, "date", "fwd_ret_4w", dropped, stable, overlap=4,
                                 label="2d exits 4w", seed=SEED)
    print("   " + str(r))
    return {"4w": r}


def main() -> int:
    print("=" * 88)
    print("T0-01  AEP PAPER B SUB-STUDY 2 — DATE-CLUSTERED RE-INFERENCE")
    print("=" * 88)
    df = load()
    sdf = stock_level_frame(df)
    print(f"stock-level panel: {len(sdf):,} rows | {sdf['date'].nunique():,} dates | "
          f"{sdf['ticker'].nunique()} tickers | window {sdf['date'].min().date()} -> "
          f"{sdf['date'].max().date()}\n")

    print("(2a) CONFIRMS   High-Trend x [High-Cons vs Low-Cons]")
    a = role_test(sdf, "High", "2a confirms")
    print("\n(2b) WARNS      Low-Trend  x [High-Cons vs Low-Cons]")
    b = role_test(sdf, "Low", "2b warns")
    print("\n(2c) DELAYS     lead/lag cross-correlation (descriptive)")
    c = test_c_delays(sdf)
    print("   " + json.dumps({k: (round(v, 4) if v is not None else None)
                             for k, v in c.items()}))
    print("\n(2d) ACCELERATES-EXITS")
    d = test_d_exits(sdf)

    # ---- multiplicity across the 2 role x 4 horizon significance tests actually run ----
    keys, pvals = [], []
    for role, res in (("2a", a), ("2b", b)):
        for h, r in res.items():
            keys.append(f"{role}_{h}")
            pvals.append(r.p if np.isfinite(r.p) else 1.0)
    keys.append("2d_4w")
    pvals.append(d["4w"].p if np.isfinite(d["4w"].p) else 1.0)
    bh = benjamini_hochberg(pvals, q=0.05)
    by = benjamini_yekutieli(pvals, q=0.05)

    print("\n" + "-" * 88)
    print("MULTIPLICITY  (m = 9 tests: 2 roles x 4 horizons + 1 exit test)")
    print("-" * 88)
    print(f"{'test':<12}{'p':>10}{'BH q=.05':>12}{'BY q=.05':>12}")
    for k, p, x, y in zip(keys, pvals, bh, by):
        print(f"{k:<12}{p:>10.4f}{str(bool(x)):>12}{str(bool(y)):>12}")

    # ---- true out-of-sample: the 53 weeks Paper B truncated away and never saw ----
    print("\n" + "=" * 88)
    print("LOCKBOX — 2025-07-11 onward, never seen by AEP Paper B")
    print("=" * 88)
    lb_raw = load("lockbox")
    lb = stock_level_frame(lb_raw)
    print(f"lockbox panel: {len(lb):,} rows | {lb['date'].nunique()} dates | "
          f"{lb['date'].min().date()} -> {lb['date'].max().date()}\n")
    lockbox = {}
    for role, state in (("2a confirms", "High"), ("2b warns", "Low")):
        print(f"({role})")
        lockbox[role] = {}
        for h in FWD_HORIZONS:
            col = f"fwd_ret_{h}w"
            hi = (lb["trend_tercile"] == state) & (lb["cons_tercile"] == "High")
            lo = (lb["trend_tercile"] == state) & (lb["cons_tercile"] == "Low")
            r = date_clustered_group_diff(lb, "date", col, hi, lo, overlap=h,
                                          label=f"LB {role} {h}w", seed=SEED)
            lockbox[role][f"{h}w"] = r
            print("   " + str(r))

    # power of the lockbox to adjudicate the discovery-window effect (G10-L04)
    print("\nLockbox power check — can 53 weeks resolve the discovery effect?")
    power_rows = []
    for h in FWD_HORIZONS:
        d_est = a[f"{h}w"].estimate
        n_lb = lockbox["2a confirms"][f"{h}w"].n
        se_lb = lockbox["2a confirms"][f"{h}w"].se
        mde = 1.96 * se_lb if np.isfinite(se_lb) else np.nan
        power_rows.append({"horizon": f"{h}w", "discovery_effect_pct": round(d_est * 100, 4),
                           "lockbox_n_dates": int(n_lb),
                           "lockbox_mde_pct": round(mde * 100, 4) if np.isfinite(mde) else None,
                           "adequately_powered": bool(np.isfinite(mde) and mde <= abs(d_est))})
        print(f"   {h:2d}w  discovery effect {d_est*100:+.4f}%   lockbox n={n_lb:3d}   "
              f"MDE {mde*100:+.4f}%   powered={power_rows[-1]['adequately_powered']}")

    # ---- verdicts against the pre-registered rule (charter s4/T0-01) ----
    print("\n" + "=" * 88)
    print("VERDICTS vs the PRE-REGISTERED rule (charter s4/T0-01):")
    print("  promote  = |t|>=2 under NW  AND  bootstrap CI excludes 0  AND  effect monotone")
    print("             in horizon  AND  survives the declared BY multiplicity correction")
    print("  kill     = |t|<2 at every horizon")
    print("=" * 88)
    by_map = dict(zip(keys, by))
    verdicts = {}
    for role, res, archived, tag in (
            ("2a Confirms", a, "NOT CONFIRMED (near-miss, t=1.97-1.91)", "2a"),
            ("2b Warns", b, "CONFIRMED (t=2.25/2.03/2.07)", "2b")):
        eff = [res[f"{h}w"].estimate for h in FWD_HORIZONS]
        monotone = all(eff[i] <= eff[i + 1] for i in range(len(eff) - 1)) or \
                   all(eff[i] >= eff[i + 1] for i in range(len(eff) - 1))
        best = max(res.values(), key=lambda r: abs(r.t) if np.isfinite(r.t) else 0)
        ci_ok = best.boot_ci_lo is not None and (best.boot_ci_lo > 0 or best.boot_ci_hi < 0)
        signs_stable = len({np.sign(e) for e in eff}) == 1
        by_ok = any(by_map.get(f"{tag}_{h}w", False) for h in FWD_HORIZONS)
        raw_ok = abs(best.t) >= 2.0 and ci_ok and monotone and signs_stable
        killed = all(abs(res[f"{h}w"].t) < 2.0 for h in FWD_HORIZONS
                     if np.isfinite(res[f"{h}w"].t))
        if raw_ok and by_ok:
            v = "PROMOTE to economic gate"
        elif killed:
            v = "RETIRE"
        else:
            v = "UNRESOLVED — coherent effect, fails declared multiplicity correction"
        lb_best = max(lockbox[role.split()[0] + (" confirms" if tag == "2a" else " warns")].values(),
                      key=lambda r: abs(r.t) if np.isfinite(r.t) else 0)
        verdicts[role] = {
            "archived_verdict": archived,
            "corrected_best_t": float(best.t), "corrected_best_horizon": best.label,
            "effects_by_horizon_pct": [round(e * 100, 4) for e in eff],
            "monotone_in_horizon": bool(monotone), "sign_stable": bool(signs_stable),
            "bootstrap_ci_excludes_zero": bool(ci_ok),
            "survives_declared_BY": bool(by_ok),
            "lockbox_best_t": float(lb_best.t) if np.isfinite(lb_best.t) else None,
            "verdict": v,
        }
        print(f"\n{role}")
        print(f"  archived           : {archived}")
        print(f"  corrected best     : t={best.t:+.2f} at {best.label}")
        print(f"  effects (1/4/8/13w): {[round(e*100,4) for e in eff]} %")
        print(f"  sign stable={signs_stable}  monotone={monotone}  boot CI excl 0={ci_ok}  "
              f"BY-clean={by_ok}")
        print(f"  lockbox best t     : {lb_best.t:+.2f} (53w, see power check above)")
        print(f"  --> {v}")

    # ---- what would actually settle 2a? (G10-L04: state the requirement, don't hand-wave) ----
    print("\n" + "-" * 88)
    print("WHAT WOULD SETTLE 2a")
    print("-" * 88)
    settle = {}
    best_a = max(a.values(), key=lambda r: abs(r.t) if np.isfinite(r.t) else 0)
    p_needed_by = 0.05 / np.sum(1.0 / np.arange(1, len(keys) + 1)) / len(keys)  # BY rank-1
    from scipy import stats as _st
    t_needed = float(_st.norm.ppf(1 - p_needed_by / 2))
    n_needed = int(np.ceil(best_a.n * (t_needed / abs(best_a.t)) ** 2))
    extra_weeks = max(0, n_needed - best_a.n)
    settle = {"current_t": float(best_a.t), "current_n_dates": int(best_a.n),
              "by_rank1_p_threshold": float(p_needed_by), "t_required": t_needed,
              "n_dates_required": n_needed, "extra_weeks_required": extra_weeks,
              "extra_years_required": round(extra_weeks / 52.0, 1)}
    print(f"   current   : t={best_a.t:+.2f} on n={best_a.n} dates (4w horizon)")
    print(f"   BY rank-1 : p<={p_needed_by:.5f}  =>  |t|>={t_needed:.2f}")
    print(f"   requires  : n={n_needed} dates  =>  {extra_weeks} more weeks "
          f"({extra_weeks/52.0:.1f} more years) at the observed effect size")
    print("   => waiting is not a viable route. A more efficient estimator (full "
          "cross-section\n      rather than discarding the middle tercile) is the only "
          "way to resolve this on\n      existing data, and must itself be pre-registered.")

    payload = {
        "experiment": "T0-01",
        "what_would_settle_2a": settle,
        "question": "Do consistency_mom_26w's four candidate roles survive date-clustered inference?",
        "window": [str(sdf["date"].min().date()), str(sdf["date"].max().date())],
        "n_dates": int(sdf["date"].nunique()), "n_rows": int(len(sdf)),
        "lockbox_boundary": str(LOCK.date()),
        "defect": ("original used pooled stock-week two-sample SE; forward returns overlap and "
                   "stocks within a week share a market factor"),
        "results": {
            "2a_confirms": {h: r.to_dict() for h, r in a.items()},
            "2b_warns": {h: r.to_dict() for h, r in b.items()},
            "2c_delays_crosscorr": c,
            "2d_exits": {h: r.to_dict() for h, r in d.items()},
        },
        "multiplicity": {"m": len(keys), "tests": keys, "p": pvals,
                         "bh_pass": [bool(x) for x in bh], "by_pass": [bool(x) for x in by]},
        "lockbox": {role: {h: r.to_dict() for h, r in res.items()}
                    for role, res in lockbox.items()},
        "lockbox_power": power_rows,
        "verdicts": verdicts,
    }
    (OUT / "t0_01_data.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n-> {OUT/'t0_01_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
