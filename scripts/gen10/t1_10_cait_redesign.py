#!/usr/bin/env python3
"""T1-10 — Gen-7 CAIT redesign, executing the frozen contract.

Contract: docs/gen10_protocols/T1-10_CAIT_REDESIGN_CONTRACT.md (written and frozen BEFORE
this script produced any number). It resolves G8-10 s4's three points:
  1. POOLED, one coefficient per carrier-lag (per-stock testing destroys the power gain).
  2. DATE-CLUSTERED SEs always (Fama-MacBeth + Newey-West + block bootstrap).
  3. Broad market-beta transmission does NOT count as an answer -> receivers are
     beta-residualised, and channel specificity is tested rather than assumed.

Decision rule (frozen): a SURVIVOR needs |t|>=2 on its channel group, a bootstrap CI
excluding zero, BY-clean at m=18, AND channel specificity. Significant on both the channel
group and its complement is scored BETA, not transmission.
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
    nw_mean_test, benjamini_yekutieli,
)

OUT = ROOT / "results/gen10/T1-10"
OUT.mkdir(parents=True, exist_ok=True)
CA = ROOT / "tmp/kaggle_uploads/panel_enriched/cross_asset_prices_daily.parquet"
SEED = 20260731
LAGS = [1, 2, 4]
SHOCK_W = 4
BETA_W = 104
R_FLOOR = 0.11

CARRIERS = {   # symbol -> (label, channel receiver sectors)
    "CL=F":      ("Crude oil",  ["Energy", "Materials"]),
    "HG=F":      ("Copper",     ["Materials", "Industrials"]),
    "GC=F":      ("Gold",       ["Consumer Goods"]),
    "USDINR=X":  ("USD/INR",    ["Information Technology"]),
    "^TNX":      ("US 10Y",     ["Real Estate"]),
    "DX-Y.NYB":  ("DXY",        ["Information Technology", "Materials"]),
}


def load_panel() -> pd.DataFrame:
    d = pd.read_parquet(ROOT / "data/kaggle_upload/panel_a_weekly.parquet",
                        columns=["date", "ticker", "sector", "ret_1w", "target_1w"])
    d["date"] = pd.to_datetime(d["date"]).dt.normalize()
    d = d[d["sector"].notna() & (d["sector"] != "UNKNOWN")].copy()

    # market factor and rolling beta -> residual forward return (contract s1 point 3)
    mkt = d.groupby("date")["ret_1w"].mean().rename("mkt_ret")
    mkt_f = d.groupby("date")["target_1w"].mean().rename("mkt_fwd")
    d = d.merge(mkt, on="date").merge(mkt_f, on="date")
    d = d.sort_values(["ticker", "date"])
    g = d.groupby("ticker")
    cov = g.apply(lambda x: x["ret_1w"].rolling(BETA_W, min_periods=52)
                  .cov(x["mkt_ret"]), include_groups=False).reset_index(level=0, drop=True)
    var = d.groupby("ticker")["mkt_ret"].transform(
        lambda s: s.rolling(BETA_W, min_periods=52).var())
    d["beta"] = (cov / var.replace(0, np.nan)).clip(-3, 3)
    d["resid_fwd"] = d["target_1w"] - d["beta"] * d["mkt_fwd"]
    return d.dropna(subset=["resid_fwd"])


def carrier_shocks(dates: pd.Index) -> pd.DataFrame:
    ca = pd.read_parquet(CA, columns=["date", "symbol", "close"])
    ca["date"] = pd.to_datetime(ca["date"]).dt.normalize()
    out = {}
    for sym in CARRIERS:
        s = ca[ca["symbol"] == sym].set_index("date")["close"].sort_index()
        if s.empty:
            continue
        s = s[~s.index.duplicated(keep="last")]
        s = s.reindex(s.index.union(dates)).ffill().reindex(dates)
        out[sym] = np.log(s / s.shift(SHOCK_W))
    return pd.DataFrame(out, index=dates)


def add_carrier_exposure(d: pd.DataFrame, shock: pd.Series, sym: str) -> pd.DataFrame:
    """Rolling per-stock sensitivity to the carrier. Without this the regressor is constant
    within a date and the stock dimension contributes NOTHING to identification -- the
    design would collapse to a sector-level receiver, which G8-10 measured as 1.49 effective
    series and called a false remedy. Interacting the shock with each stock's own exposure
    is what makes the 132-stock receiver universe do any work."""
    s = shock.rename("shk").to_frame()
    s["shk_now"] = s["shk"]
    d = d.merge(s[["shk_now"]], left_on="date", right_index=True, how="left")
    d = d.sort_values(["ticker", "date"])
    g = d.groupby("ticker")
    cov = g.apply(lambda x: x["ret_1w"].rolling(BETA_W, min_periods=52)
                  .cov(x["shk_now"]), include_groups=False).reset_index(level=0, drop=True)
    var = d.groupby("ticker")["shk_now"].transform(
        lambda x: x.rolling(BETA_W, min_periods=52).var())
    d[f"expo_{sym}"] = (cov / var.replace(0, np.nan)).clip(-5, 5)
    return d


def fm_coefficients(d: pd.DataFrame, shock: pd.Series, lag: int, sym: str) -> tuple:
    """Fama-MacBeth: per date, cross-sectional slope of beta-residualised forward return on
    (stock's carrier exposure x lagged carrier shock). The regressor varies ACROSS STOCKS
    within a date, so the stock-level receiver universe genuinely contributes -- this is the
    estimator G8-10's power argument assumes. Inference is then over the per-date slope
    series (date-clustered by construction), per contract s1 point 2."""
    x = shock.shift(lag)
    d = d.copy()
    d["_shk"] = d["date"].map(x)
    d["_reg"] = d[f"expo_{sym}"] * d["_shk"]
    slopes, rs = {}, []
    for dt, g in d.groupby("date"):
        s = g[["_reg", "resid_fwd"]].dropna()
        if len(s) < 30 or s["_reg"].std() == 0:
            continue
        xc = s["_reg"] - s["_reg"].mean()
        yc = s["resid_fwd"] - s["resid_fwd"].mean()
        denom = float((xc ** 2).sum())
        if denom <= 0:
            continue
        slopes[dt] = float((xc * yc).sum() / denom)
        rs.append(float(np.corrcoef(s["_reg"], s["resid_fwd"])[0, 1]))
    if len(slopes) < 100:
        return pd.Series(dtype=float), np.nan
    return pd.Series(slopes).sort_index(), float(np.nanmean(rs))


def main() -> int:
    print("=" * 100)
    print("T1-10 — GEN-7 CAIT REDESIGN (executing the frozen contract)")
    print("=" * 100)
    d = load_panel()
    dates = pd.Index(sorted(d["date"].unique()))
    sh = carrier_shocks(dates)
    print(f"receivers: {d['ticker'].nunique()} stocks, beta-residualised "
          f"(rolling {BETA_W}w beta vs equal-weight market)")
    print(f"sectors: {sorted(d['sector'].unique())}")
    print(f"carriers: {len(CARRIERS)} x {len(LAGS)} lags = {len(CARRIERS)*len(LAGS)} tests\n")
    for sym, (lbl, _) in CARRIERS.items():
        s = sh[sym].dropna()
        print(f"  {lbl:<12} {sym:<12} {len(s):>5} weeks  "
              f"{s.index.min().date()} .. {s.index.max().date()}")

    print("\n" + "-" * 100)
    print(f"{'carrier':<12}{'lag':>4}{'channel r':>12}{'channel t':>11}"
          f"{'other r':>11}{'other t':>10}   classification")
    print("-" * 100)
    rows = []
    for sym, (lbl, chan) in CARRIERS.items():
        de = add_carrier_exposure(d, sh[sym], sym)
        eff = de[f"expo_{sym}"].notna().sum()
        print(f"  [{lbl}] stock-level exposures estimated on {eff:,} stock-weeks")
        for lag in LAGS:
            ch = de[de["sector"].isin(chan)]
            ot = de[~de["sector"].isin(chan)]
            p_ch, r_ch = fm_coefficients(ch, sh[sym], lag, sym)
            p_ot, r_ot = fm_coefficients(ot, sh[sym], lag, sym)
            if len(p_ch) == 0 or len(p_ot) == 0:
                continue
            t_ch = nw_mean_test(p_ch.to_numpy(), overlap=SHOCK_W, n_boot=2000, seed=SEED)
            t_ot = nw_mean_test(p_ot.to_numpy(), overlap=SHOCK_W, n_boot=2000, seed=SEED)
            sig_ch = abs(t_ch.t) >= 2 and t_ch.boot_ci_lo is not None and \
                (t_ch.boot_ci_lo > 0 or t_ch.boot_ci_hi < 0)
            sig_ot = abs(t_ot.t) >= 2
            if sig_ch and sig_ot:
                cls = "BETA (not channel-specific)"
            elif sig_ch:
                cls = "channel-specific candidate"
            else:
                cls = "null"
            rows.append({"carrier": sym, "label": lbl, "lag": lag, "channel": chan,
                         "r_channel": r_ch, "t_channel": float(t_ch.t),
                         "p_channel": float(t_ch.p), "n_channel": int(t_ch.n),
                         "r_other": r_ot, "t_other": float(t_ot.t),
                         "sig_channel": bool(sig_ch), "sig_other": bool(sig_ot),
                         "classification": cls})
            print(f"{lbl:<12}{lag:>4}{r_ch:>12.4f}{t_ch.t:>11.2f}"
                  f"{r_ot:>11.4f}{t_ot.t:>10.2f}   {cls}")

    pv = [r["p_channel"] for r in rows]
    by = benjamini_yekutieli(pv, q=0.05)
    print(f"\n--- BY q=0.05 across the m={len(rows)} declared tests ---")
    for r, ok in zip(rows, by):
        r["by_clean"] = bool(ok)
    n_by = int(sum(by))
    print(f"  BY-clean: {n_by}/{len(rows)}")
    if n_by:
        for r, ok in zip(rows, by):
            if ok:
                print(f"    {r['label']} lag{r['lag']}  p={r['p_channel']:.4f}")

    survivors = [r for r in rows
                 if r["sig_channel"] and not r["sig_other"] and r["by_clean"]]
    betas = [r for r in rows if r["classification"].startswith("BETA")]

    # observed effect sizes vs the pre-registered floor
    max_r = max(abs(r["r_channel"]) for r in rows) if rows else np.nan
    print(f"\n--- effect sizes vs the pre-registered floor r={R_FLOOR} ---")
    print(f"  largest |r| observed on any channel group: {max_r:.4f}")
    print(f"  number of tests with |r| >= {R_FLOOR}: "
          f"{sum(abs(r['r_channel']) >= R_FLOOR for r in rows)}/{len(rows)}")

    print("\n" + "=" * 100)
    print("VERDICT vs the frozen decision rule")
    print("=" * 100)
    print(f"  survivors (channel-specific, BY-clean, CI excludes 0): {len(survivors)}")
    print(f"  classified BETA rather than transmission             : {len(betas)}")
    if survivors:
        for r in survivors:
            print(f"    SURVIVOR {r['label']} lag{r['lag']} -> {r['channel']}  "
                  f"r={r['r_channel']:+.4f} t={r['t_channel']:+.2f}")
        print("\n  --> H-A1 SUPPORTED. H-A2/A3/A4 become live questions again.")
    else:
        print("\n  --> NULL at adequate power, with the beta confound removed by design.")
        print("      Per the contract s3 and G8-10 s6, this RETIRES the cross-asset")
        print("      transmission question permanently. It does not invite a fourth re-run.")

    payload = {"experiment": "T1-10",
               "contract": "docs/gen10_protocols/T1-10_CAIT_REDESIGN_CONTRACT.md",
               "n_receivers": int(d["ticker"].nunique()), "m_tests": len(rows),
               "results": rows, "n_survivors": len(survivors), "n_beta": len(betas),
               "max_abs_r": float(max_r), "r_floor": R_FLOOR,
               "verdict": ("H-A1 SUPPORTED" if survivors else
                           "NULL — cross-asset transmission retired")}
    (OUT / "t1_10_data.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n-> {OUT/'t1_10_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
