#!/usr/bin/env python3
"""E6 — the IV surface through Gen-11's sign-stability screen, then gate A1.

The surface built from the F&O bhavcopy (112,706 rows, 847 weeks, 427 underlyings) joined to
PANEL-A gives 94,896 stock-weeks across 798 weeks and 308 names -- a real panel, and the
first genuinely new information source this programme has added.

Screened BEFORE any strategy is proposed, per the charter, and specifically because E1->E3
showed a real +0.0266 incremental ceiling can still produce nothing realizable. The screen
costs minutes and would have saved that entire arc.

FEATURES (7 declared; multiplicity counted at m=7):
    iv_atm             level of forward expected vol
    vrp                iv_atm - trailing realised vol   <- strongest external prior
    iv_skew_25d        OTM put IV - OTM call IV         <- second strongest prior
    iv_term_slope      far-expiry ATM IV - near-expiry
    iv_rank_52w        percentile of iv_atm vs own 52w history (rich/cheap)
    pcr_oi             put/call open interest ratio
    oi_concentration   Herfindahl of OI across strikes

Each is screened on:
    share_positive  of the per-date coefficient, controlling for momentum
    NW t            on the momentum-orthogonalised per-date IC
Reference points from E4: delivery 62.2% (real), momentum 60.5% (real), futures OI 50.0%
(dead). A feature near 50% cannot be captured by any fixed linear rule.
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
from src.research.gen10.inference import (  # noqa: E402
    nw_mean_test, per_date_ic, benjamini_yekutieli,
)
from e3_oi_candidates import resid  # noqa: E402

OUT = ROOT / "results/gen11/E6"
OUT.mkdir(parents=True, exist_ok=True)
SEED = 20260731
LOCK = pd.Timestamp("2025-07-11")
DISC_END = pd.Timestamp("2019-12-31")
FEATS = ["iv_atm", "vrp", "iv_skew_25d", "iv_term_slope", "iv_rank_52w",
         "pcr_oi", "oi_concentration"]
MOMC = ["res_mom_52w_ex4w", "ret_52w_ex4w", "sharpe_mom_26w", "consistency_mom_26w"]


def build():
    iv = pd.read_parquet(ROOT / "data/processed/iv_surface_weekly.parquet")
    iv["date"] = pd.to_datetime(iv["date"])
    iv["tk"] = iv["ticker"].astype(str) + ".NS"
    iv["wk"] = iv["date"].dt.to_period("W").dt.start_time

    p = pd.read_parquet(ROOT / "data/kaggle_upload/panel_a_weekly.parquet",
                        columns=["date", "ticker", "close", "vol_13w", "vol_52w",
                                 "target_1w"] + MOMC)
    p["date"] = pd.to_datetime(p["date"])
    p = p[pd.to_numeric(p["close"], errors="coerce") >= 20]
    p["wk"] = p["date"].dt.to_period("W").dt.start_time

    d = p.merge(iv[["wk", "tk", "iv_atm", "iv_skew_25d", "iv_term_slope",
                    "pcr_oi", "oi_concentration"]],
                left_on=["wk", "ticker"], right_on=["wk", "tk"], how="inner")
    d = d.dropna(subset=["target_1w"]).sort_values(["ticker", "date"])

    # realised vol -> annualised, to be unit-comparable with IV
    rv = pd.to_numeric(d["vol_13w"], errors="coerce")
    if rv.median() < 0.15:                       # stored as weekly sigma
        rv = rv * np.sqrt(52.0)
    d["realised_vol_ann"] = rv
    d["vrp"] = d["iv_atm"] - d["realised_vol_ann"]

    d["iv_rank_52w"] = d.groupby("ticker")["iv_atm"].transform(
        lambda s: s.rolling(52, min_periods=26).rank(pct=True))

    d["ret"] = d.groupby("date")["target_1w"].transform(
        lambda s: s.clip(s.quantile(.01), s.quantile(.99)))

    def z(c):
        g = d.groupby("date")[c]
        return (d[c] - g.transform("mean")) / g.transform("std").replace(0, np.nan)
    d["mom_comp"] = pd.concat([z(c) for c in MOMC], axis=1).mean(axis=1)
    return d.dropna(subset=["ret", "mom_comp"])


def main() -> int:
    print("=" * 100)
    print("E6 — IV SURFACE: sign-stability screen, then gate A1")
    print("=" * 100)
    d = build()
    print(f"panel: {len(d):,} stock-weeks | {d['date'].nunique()} weeks "
          f"({d['date'].min().date()} .. {d['date'].max().date()}) | "
          f"{d['ticker'].nunique()} names")
    print(f"realised vol (ann) median {d['realised_vol_ann'].median():.1%}  |  "
          f"iv_atm median {d['iv_atm'].median():.1%}  |  vrp median {d['vrp'].median():+.1%}\n")

    print("--- SCREEN: sign stability of the per-date coefficient (controlling for momentum) ---")
    print(f"{'feature':<20}{'weeks':>7}{'share+':>9}{'|mu|/sd':>9}{'NW t':>8}   verdict")
    print("-" * 84)
    scr = []
    for c in FEATS:
        coefs = {}
        for dt, g in d.groupby("date"):
            s = g[[c, "mom_comp", "ret"]].dropna()
            if len(s) < 40 or s[c].std() == 0:
                continue
            X = np.column_stack([np.ones(len(s)), s["mom_comp"], s[c]])
            try:
                b, *_ = np.linalg.lstsq(X, s["ret"].to_numpy(), rcond=None)
            except np.linalg.LinAlgError:
                continue
            coefs[dt] = float(b[2])
        if len(coefs) < 100:
            print(f"{c:<20}  too few weeks ({len(coefs)})")
            continue
        cs = pd.Series(coefs).sort_index()
        r = nw_mean_test(cs.to_numpy(), overlap=1, n_boot=1500, seed=SEED)
        share = float((cs > 0).mean())
        snr = float(abs(cs.mean()) / cs.std()) if cs.std() > 0 else 0.0
        far = abs(share - 0.5)
        v = ("CAPTURABLE" if far >= 0.04 and abs(r.t) >= 2 else
             "borderline" if far >= 0.03 or abs(r.t) >= 2 else
             "coin flip")
        scr.append({"feature": c, "n_weeks": int(len(cs)), "share_positive": share,
                    "snr": snr, "t": float(r.t), "verdict": v})
        print(f"{c:<20}{len(cs):>7}{share:>8.1%}{snr:>9.3f}{r.t:>+8.2f}   {v}")

    print("\n  reference (E4): delivery 62.2% REAL | momentum 60.5% REAL | futures OI 50.0% DEAD")

    # ---- gate A1 for anything not a coin flip ----
    live = [s for s in scr if s["verdict"] != "coin flip"]
    print(f"\n--- A1: incremental IC over momentum, for the {len(live)} non-coin-flip features ---")
    print(f"{'feature':<20}{'raw IC':>10}{'raw t':>8}{'resid IC':>11}{'resid t':>10}"
          f"   bootstrap CI (resid)")
    a1 = []
    for s in live:
        c = s["feature"]
        dd = d[d[c].notna()].copy()
        raw_ic = per_date_ic(dd[["date", c, "ret"]].dropna(), "date", c, "ret", min_pairs=30)
        raw = nw_mean_test(raw_ic.to_numpy(), overlap=1, n_boot=2500, seed=SEED)
        dd["_r"] = resid(dd, c, "mom_comp")
        r_ic = per_date_ic(dd[["date", "_r", "ret"]].dropna(), "date", "_r", "ret",
                           min_pairs=30)
        res = nw_mean_test(r_ic.to_numpy(), overlap=1, n_boot=2500, seed=SEED)
        a1.append({"feature": c, "raw_ic": float(raw.estimate), "raw_t": float(raw.t),
                   "res_ic": float(res.estimate), "res_t": float(res.t),
                   "res_p": float(res.p), "n": int(res.n),
                   "boot": [res.boot_ci_lo, res.boot_ci_hi],
                   "fragile": bool(res.fragile)})
        print(f"{c:<20}{raw.estimate:>+10.4f}{raw.t:>+8.2f}{res.estimate:>+11.4f}"
              f"{res.t:>+10.2f}   [{res.boot_ci_lo:+.4f},{res.boot_ci_hi:+.4f}]"
              f"{'  FRAGILE' if res.fragile else ''}")

    # multiplicity across ALL 7 declared, not just the survivors
    pv = [next((x["res_p"] for x in a1 if x["feature"] == s["feature"]), 1.0) for s in scr]
    by = benjamini_yekutieli(pv, q=0.05)
    print(f"\n--- A3: BY q=0.05 at m={len(scr)} (all declared features) ---")
    for s, p_, ok in zip(scr, pv, by):
        print(f"  {s['feature']:<20} p={p_:.4f}  BY-clean={bool(ok)}")

    passed = [x for x, ok in zip(a1, [b for s, b in zip(scr, by)
                                      if s["feature"] in [y["feature"] for y in a1]])
              if abs(x["res_t"]) >= 2 and ok and not x["fragile"]]
    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    print(f"  screened {len(scr)} | non-coin-flip {len(live)} | clear A1+A3 {len(passed)}")
    for x in passed:
        print(f"    SURVIVOR  {x['feature']:<18} resid t={x['res_t']:+.2f}  "
              f"IC={x['res_ic']:+.4f}")
    if not passed:
        print("    none — the IV surface carries no capturable cross-sectional signal")
        print("    beyond momentum. Recorded; no strategy proposed.")
    else:
        print("\n  -> next: A2 out-of-sample split, then A4-A7.")

    (OUT / "e6_data.json").write_text(json.dumps(
        {"screen": scr, "a1": a1, "survivors": [x["feature"] for x in passed]},
        indent=2, default=str))
    print(f"\n-> {OUT/'e6_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
