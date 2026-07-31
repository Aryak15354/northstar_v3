#!/usr/bin/env python3
"""T1-17 — G5-08A/B/C/D and G5-09: the construction branch Gen-5 never opened.

WHY THESE WERE NEVER RUN, stated before any result. Gen-5 did not skip them for lack of
data or time. Its own frozen sequencing rule closed them (decision log, 2026-07-24):

    "Per the frozen sequencing rule, Paper 2's construction branch (G5-08A-D) does NOT
     open -- it required a cleared B1 gate, which none produced."

All three B1 levers (G5-05A/05B/04C) were TERMINATED_BY_GATE, so the branch stayed shut.
Running it now overrides Gen-5's sequencing discipline. That is a deliberate choice made on
explicit instruction, and it is recorded rather than glossed: the prior is low, and Gen-10's
own T1-06 (any long-only sleeve added to a long-only book hits a ~0.84 correlation wall) and
T1-15 (the small-cap tiers are one nested signal, not two) both point the same way.

A low prior is a reason to pre-register a hard kill criterion, not a reason to skip. So:

PRE-REGISTERED (frozen before results):
  benchmark  = equal-weight Config-4 proxy long book, identical holdings, net of cost.
  promote    = paired Sharpe improvement with a bootstrap CI excluding zero AND the
               improvement >= Gen-5's own +0.15 bar AND BY-clean at m = 5.
  kill       = anything less. "Directionally positive" is not a result.
  Everything on the same holdings and the same dates (Rule 6); only WEIGHTS differ,
  except G5-08D which also changes turnover, and G5-09 which changes exposure.
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

from g8_07_capital_scale_sweep import load_panel  # noqa: E402
from src.pnl.indian_cost_model import IndianEquityCostModel  # noqa: E402
from src.research.gen10.inference import (  # noqa: E402
    paired_sharpe_diff, benjamini_yekutieli, sharpe,
)

OUT = ROOT / "results/gen10/T1-17"
OUT.mkdir(parents=True, exist_ok=True)
SEED = 20260731
LOCK = pd.Timestamp("2025-07-11")
TOPQ = 0.80
FUND = 10.0 * 1e7
GEN5_BAR = 0.15
CM = IndianEquityCostModel()


def build_books(df):
    """Top-quintile composite long book, monthly rebalance — the same selection every arm
    trades. Returns per-date (tickers, per-name fwd return, vol, composite)."""
    dates = sorted(df["date"].unique())
    book, hist = set(), {}
    for i, d in enumerate(dates):
        g = df[df["date"] == d]
        if i % 4 == 0:
            gg = g.dropna(subset=["composite"])
            if len(gg) >= 50:
                book = set(gg.loc[gg["composite"] >= gg["composite"].quantile(TOPQ), "ticker"])
        if not book:
            continue
        h = g[g["ticker"].isin(book)].dropna(subset=["target_1w"])
        if len(h) < 20:
            continue
        hist[d] = h[["ticker", "target_1w", "vol_13w", "composite", "adv_13w", "close"]].copy()
    return hist


def weights_for(arm, h, prev_w):
    """Per-arm weight vector on the SAME holdings."""
    n = len(h)
    tick = h["ticker"].to_numpy()
    if arm == "EW":
        w = np.ones(n) / n
    elif arm == "G5-08A_confidence":
        c = pd.to_numeric(h["composite"], errors="coerce").to_numpy()
        c = np.nan_to_num(c - np.nanmin(c) + 1e-6)
        w = c / c.sum() if c.sum() > 0 else np.ones(n) / n
    elif arm == "G5-08B_riskparity":
        v = pd.to_numeric(h["vol_13w"], errors="coerce").to_numpy()
        v = np.where(np.isfinite(v) & (v > 0), v, np.nanmedian(v[np.isfinite(v)]) if np.isfinite(v).any() else 1.0)
        iv = 1.0 / v
        w = iv / iv.sum()
    elif arm == "G5-08C_shrinkage":
        # Ledoit-Wolf-style shrinkage toward the identity, then minimum-variance weights.
        # With only per-name vol available cross-sectionally, shrink the vol vector toward
        # its cross-sectional mean and take inverse-variance weights -- the diagonal case
        # of a shrunk covariance, which is what a shrinkage optimizer collapses to here.
        v = pd.to_numeric(h["vol_13w"], errors="coerce").to_numpy()
        v = np.where(np.isfinite(v) & (v > 0), v, np.nan)
        m = np.nanmean(v) if np.isfinite(v).any() else 1.0
        v = np.where(np.isfinite(v), v, m)
        lam = 0.5
        vs = lam * m + (1 - lam) * v
        iv = 1.0 / (vs ** 2)
        w = iv / iv.sum()
    elif arm == "G5-08D_notrade":
        w = np.ones(n) / n                      # target is EW; the band is applied outside
    else:
        raise ValueError(arm)
    return dict(zip(tick, w))


def run_arm(hist, arm, band=0.0):
    dates = sorted(hist)
    prev_w, rets, costs = {}, {}, {}
    for d in dates:
        h = hist[d]
        tgt = weights_for(arm if arm != "G5-08D_notrade" else "EW", h, prev_w)
        if band > 0.0 and prev_w:
            # no-trade region: keep the old weight unless it has drifted beyond `band`
            new = {}
            for tk, wt in tgt.items():
                pw = prev_w.get(tk)
                new[tk] = pw if (pw is not None and abs(pw - wt) <= band * wt) else wt
            ssum = sum(new.values())
            tgt = {k: v / ssum for k, v in new.items()} if ssum > 0 else tgt
        r = pd.to_numeric(h["target_1w"], errors="coerce").to_numpy()
        wv = np.array([tgt[t] for t in h["ticker"]])
        ok = np.isfinite(r)
        rets[d] = float((wv[ok] * r[ok]).sum() / max(wv[ok].sum(), 1e-12))
        # cost: turnover of the weight vector, priced per-name against ADV
        adv = dict(zip(h["ticker"], pd.to_numeric(h["adv_13w"], errors="coerce")
                       * pd.to_numeric(h["close"], errors="coerce")))
        c = 0.0
        allt = set(tgt) | set(prev_w)
        for tk in allt:
            dw = abs(tgt.get(tk, 0.0) - prev_w.get(tk, 0.0))
            if dw <= 0:
                continue
            a = adv.get(tk, np.nan)
            a = float(a) if np.isfinite(a) else None
            c += CM.cost_breakdown("BUY", dw * FUND, adv_inr=a).total
        costs[d] = c / FUND
        prev_w = tgt
    s = pd.Series(rets).sort_index() - pd.Series(costs).reindex(sorted(rets)).fillna(0.0)
    s = s[s.index < LOCK].dropna()
    return s, float(np.mean(list(costs.values())) * 1e4)


def g5_09_temporal(df, hist):
    """G5-09 — does a TEMPORAL model of state add value over the contemporaneous state?
    Gen-5 F17 found weekly state carries near-zero information about the correct action.
    G5-09 asks whether the state's recent TRAJECTORY (its 4-week change) does better.
    Exposure is scaled by whether trailing market vol is rising or falling."""
    from run_g02_regime import build_regimes
    reg = build_regimes(df)
    mret = df.groupby("date")["ret_1w"].mean().sort_index()
    vol13 = mret.rolling(13, min_periods=8).std()
    rising = (vol13 - vol13.shift(4)) > 0
    base, _ = run_arm(hist, "EW")
    scale = base.index.map(lambda d: 0.5 if bool(rising.get(d, False)) else 1.0)
    return base, base * np.array(scale)


def main() -> int:
    print("=" * 96)
    print("T1-17 — G5-08A/B/C/D + G5-09: the construction branch Gen-5 never opened")
    print("=" * 96)
    print("NOTE: Gen-5's frozen sequencing rule kept this branch shut because no B1 lever")
    print("      cleared its gate. Running it overrides that discipline, on instruction.\n")
    df = load_panel()
    hist = build_books(df)
    print(f"panel {len(df):,} rows | book history {len(hist)} weeks "
          f"| mean names {np.mean([len(h) for h in hist.values()]):.0f}\n")

    arms = {
        "EW": dict(arm="EW", band=0.0),
        "G5-08A_confidence": dict(arm="G5-08A_confidence", band=0.0),
        "G5-08B_riskparity": dict(arm="G5-08B_riskparity", band=0.0),
        "G5-08C_shrinkage": dict(arm="G5-08C_shrinkage", band=0.0),
        "G5-08D_notrade": dict(arm="G5-08D_notrade", band=0.25),
    }
    series, costs = {}, {}
    for name, kw in arms.items():
        series[name], costs[name] = run_arm(hist, **kw)
        print(f"  {name:<22} Sharpe {sharpe(series[name]):+.4f}  "
              f"n={len(series[name])}  mean cost {costs[name]:.2f}bps")

    base = series["EW"]
    print(f"\n--- paired vs equal-weight (Rule 6: identical holdings, identical dates) ---")
    rows = []
    for name in arms:
        if name == "EW":
            continue
        b = series[name]
        j = base.index.intersection(b.index)
        r = paired_sharpe_diff(base.reindex(j), b.reindex(j), label=name, seed=SEED)
        rows.append({"arm": name, "sharpe": sharpe(b), "delta": float(r.estimate),
                     "t": float(r.t), "p": float(r.p), "boot_lo": r.boot_ci_lo,
                     "boot_hi": r.boot_ci_hi, "cost_bps": costs[name],
                     "fragile": bool(r.fragile)})
        print(f"  {r}")

    # G5-09
    print("\n--- G5-09: temporal model of state (vol trajectory) vs static exposure ---")
    b0, b1 = g5_09_temporal(df, hist)
    j = b0.index.intersection(b1.index)
    r9 = paired_sharpe_diff(b0.reindex(j), b1.reindex(j), label="G5-09_temporal", seed=SEED)
    rows.append({"arm": "G5-09_temporal", "sharpe": sharpe(b1), "delta": float(r9.estimate),
                 "t": float(r9.t), "p": float(r9.p), "boot_lo": r9.boot_ci_lo,
                 "boot_hi": r9.boot_ci_hi, "cost_bps": None, "fragile": bool(r9.fragile)})
    print(f"  {r9}")

    by = benjamini_yekutieli([x["p"] for x in rows], q=0.05)
    print(f"\n--- verdict vs the pre-registered rule (delta >= {GEN5_BAR}, CI excludes 0, BY-clean) ---")
    for x, ok in zip(rows, by):
        x["by_clean"] = bool(ok)
        ci_ok = x["boot_lo"] is not None and (x["boot_lo"] > 0 or x["boot_hi"] < 0)
        x["promote"] = bool(x["delta"] >= GEN5_BAR and ci_ok and ok)
        print(f"  {x['arm']:<22} delta={x['delta']:+.4f}  t={x['t']:+.2f}  "
              f"CI_excl_0={ci_ok}  BY={bool(ok)}  -> "
              f"{'PROMOTE' if x['promote'] else 'KILL'}")
    n_p = sum(x["promote"] for x in rows)
    print(f"\n  {n_p}/{len(rows)} promote.  Gen-5's sequencing rule is "
          f"{'overturned' if n_p else 'VINDICATED'}.")

    (OUT / "t1_17_data.json").write_text(json.dumps(
        {"rows": rows, "bar": GEN5_BAR, "n_promote": int(n_p)}, indent=2, default=str))
    print(f"\n-> {OUT/'t1_17_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
