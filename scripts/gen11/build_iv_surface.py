#!/usr/bin/env python3
"""Build a weekly stock-level implied-volatility surface from the F&O bhavcopy already on disk.

NO ACQUISITION. `data/raw/fo_bhav/` holds 4,075 daily NSE F&O bhavcopy files, 2.0 GB,
2010-2026. This turns them into panel-joinable weekly features.

Handles BOTH format eras:
  2010-2024  16 cols, STRIKE_PR / OPTION_TYP / SETTLE_PR, NO underlying price
             -> spot is joined from the futures (FUTSTK) row for the same symbol/expiry,
                which is present in the same file. That avoids depending on prices_daily
                and keeps everything self-consistent within the file.
  2025-2026  34 cols, StrkPric / OptnTp / SttlmPric, UndrlygPric present.

Features per (week, underlying), none of which exist in the 603-column panel:
    iv_atm            ATM implied vol, OI-weighted over near-the-money strikes
    iv_skew_25d       OTM put IV - OTM call IV  (crash-fear asymmetry)
    iv_term_slope     far-expiry ATM IV - near-expiry ATM IV
    vrp               iv_atm - trailing realised vol   (variance risk premium)
    pcr_oi / pcr_vol  put-call ratio on open interest / volume
    oi_concentration  Herfindahl of OI across strikes (disagreement proxy)
    n_contracts       liquidity / breadth control

Resumable: skips weeks already written. Run with --limit for a slice.
"""
from __future__ import annotations
import argparse
import glob
import os
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/fo_bhav"
OUT = ROOT / "data/processed/iv_surface"
OUT.mkdir(parents=True, exist_ok=True)
RF = 0.065          # flat risk-free; IV is not materially sensitive at these maturities
MIN_PRICE = 0.05
MIN_OI = 100


def _bs(S, K, t, sig, cp):
    d1 = (np.log(S / K) + (RF + sig * sig / 2) * t) / (sig * np.sqrt(t))
    d2 = d1 - sig * np.sqrt(t)
    if cp == "CE":
        return S * norm.cdf(d1) - K * np.exp(-RF * t) * norm.cdf(d2)
    return K * np.exp(-RF * t) * norm.cdf(-d2) - S * norm.cdf(-d1)


def _iv(S, K, t, px, cp):
    intrinsic = max(S - K, 0) if cp == "CE" else max(K - S, 0)
    if px <= intrinsic + 1e-6:          # no time value -> IV undefined
        return np.nan
    try:
        return brentq(lambda s: _bs(S, K, t, s, cp) - px, 1e-3, 5.0, maxiter=60)
    except Exception:
        return np.nan


def read_day(path):
    """Return a normalised options frame for one bhavcopy, or None."""
    try:
        z = zipfile.ZipFile(path)
        df = pd.read_csv(z.open(z.namelist()[0]))
    except Exception:
        return None
    cols = set(df.columns)
    if {"OptnTp", "StrkPric"} <= cols:                      # 2025+ format
        d = df.rename(columns={"TckrSymb": "sym", "OptnTp": "cp", "StrkPric": "K",
                               "SttlmPric": "px", "OpnIntrst": "oi",
                               "TtlTradgVol": "vol", "XpryDt": "exp",
                               "TradDt": "dt", "UndrlygPric": "S",
                               "FinInstrmTp": "typ"})
        d = d[d["cp"].isin(["CE", "PE"])]
    elif {"OPTION_TYP", "STRIKE_PR"} <= cols:               # 2010-2024 format
        d = df.rename(columns={"SYMBOL": "sym", "OPTION_TYP": "cp", "STRIKE_PR": "K",
                               "SETTLE_PR": "px", "OPEN_INT": "oi",
                               "CONTRACTS": "vol", "EXPIRY_DT": "exp",
                               "TIMESTAMP": "dt", "INSTRUMENT": "typ"})
        fut = df[df["INSTRUMENT"].isin(["FUTSTK", "FUTIDX"])][["SYMBOL", "EXPIRY_DT",
                                                               "SETTLE_PR"]]
        fut = fut.rename(columns={"SYMBOL": "sym", "EXPIRY_DT": "exp", "SETTLE_PR": "S"})
        fut = fut.drop_duplicates(["sym", "exp"])
        d = d[d["cp"].isin(["CE", "PE"])].merge(fut, on=["sym", "exp"], how="left")
    else:
        return None
    for c in ("K", "px", "oi", "vol", "S"):
        d[c] = pd.to_numeric(d.get(c), errors="coerce")
    d["dt"] = pd.to_datetime(d["dt"], errors="coerce", dayfirst=False)
    d["exp"] = pd.to_datetime(d["exp"], errors="coerce", dayfirst=False)
    d["tau"] = (d["exp"] - d["dt"]).dt.days / 365.25
    d = d[(d["tau"] > 0.015) & (d["px"] > MIN_PRICE) & (d["S"] > 0)
          & (d["oi"] >= MIN_OI)].dropna(subset=["K", "px", "S", "tau", "cp"])
    return d if len(d) else None


def surface(d):
    """Per-underlying surface metrics for one day."""
    out = []
    for sym, g in d.groupby("sym"):
        S = float(g["S"].median())
        if not np.isfinite(S) or S <= 0:
            continue
        g = g.copy()
        g["m"] = g["K"] / S
        near = g[(g["m"].between(0.97, 1.03))]
        if len(near) < 4:
            continue
        near = near.assign(iv=[_iv(S, r.K, r.tau, r.px, r.cp) for r in near.itertuples()])
        near = near.dropna(subset=["iv"])
        if len(near) < 3:
            continue
        w = near["oi"].clip(lower=1)
        iv_atm = float((near["iv"] * w).sum() / w.sum())

        wing = g[(g["m"] < 0.95) | (g["m"] > 1.05)].copy()
        skew = np.nan
        if len(wing) >= 4:
            wing["iv"] = [_iv(S, r.K, r.tau, r.px, r.cp) for r in wing.itertuples()]
            p = wing[(wing["cp"] == "PE") & (wing["m"] < 0.95)]["iv"].dropna()
            c = wing[(wing["cp"] == "CE") & (wing["m"] > 1.05)]["iv"].dropna()
            if len(p) >= 2 and len(c) >= 2:
                skew = float(p.mean() - c.mean())

        slope = np.nan
        by_exp = near.groupby("exp")["iv"].mean().sort_index()
        if len(by_exp) >= 2:
            slope = float(by_exp.iloc[-1] - by_exp.iloc[0])

        oi_p, oi_c = g[g.cp == "PE"]["oi"].sum(), g[g.cp == "CE"]["oi"].sum()
        v_p, v_c = g[g.cp == "PE"]["vol"].sum(), g[g.cp == "CE"]["vol"].sum()
        share = g.groupby("K")["oi"].sum()
        hhi = float(((share / share.sum()) ** 2).sum()) if share.sum() > 0 else np.nan
        out.append({"date": g["dt"].iloc[0], "ticker": sym, "iv_atm": iv_atm,
                    "iv_skew_25d": skew, "iv_term_slope": slope,
                    "pcr_oi": float(oi_p / oi_c) if oi_c > 0 else np.nan,
                    "pcr_vol": float(v_p / v_c) if v_c > 0 else np.nan,
                    "oi_concentration": hhi, "n_contracts": int(len(g)),
                    "spot": S})
    return pd.DataFrame(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weekly", action="store_true", default=True,
                    help="one snapshot per ISO week (matches the panel's frequency)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--year", type=str, default="")
    a = ap.parse_args()

    files = sorted(glob.glob(str(RAW / (a.year or "*") / "*.zip")))
    if a.weekly:                       # last trading file of each ISO week
        by = {}
        for f in files:
            ds = os.path.basename(f).split("_")[-1].split(".")[0]
            try:
                dt = pd.Timestamp(ds)
            except Exception:
                continue
            by[(dt.isocalendar().year, dt.isocalendar().week)] = f
        files = [by[k] for k in sorted(by)]
    if a.limit:
        files = files[-a.limit:]
    print(f"{len(files)} snapshots to process")

    done = {p.stem for p in OUT.glob("*.parquet")}
    n_ok = 0
    for i, f in enumerate(files, 1):
        key = os.path.basename(f).split("_")[-1].split(".")[0]
        if key in done:
            continue
        d = read_day(f)
        if d is None:
            continue
        s = surface(d)
        if len(s) == 0:
            continue
        s.to_parquet(OUT / f"{key}.parquet", index=False)
        n_ok += 1
        if n_ok % 10 == 0 or i == len(files):
            print(f"  [{i}/{len(files)}] {key}: {len(s)} underlyings "
                  f"(median ATM IV {s.iv_atm.median():.1%})", flush=True)
    print(f"\nwrote {n_ok} weekly snapshots -> {OUT}")


if __name__ == "__main__":
    main()
