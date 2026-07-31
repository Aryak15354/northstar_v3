#!/usr/bin/env python3
"""E4 — Sign-stability screen: the cheap pre-test E3 should have run first.

E3 killed all five futures-OI candidates at gate A1 despite E2 measuring a +0.0266
incremental attainable ceiling for that family. The diagnostic that explains it:

    per-date OI coefficient (controlling for momentum), 856 weeks
      mean +0.000142, t = 1.17          -- not significant
      share positive              51.1% -- a coin flip
      |mean| / std                0.037 -- 27x more noise than signal
      lag-1 autocorrelation      -0.082 -- no week-to-week persistence
      weekly refit buys           20.8x the fixed-rule coefficient

The oracle earns its incremental ceiling by refitting a SIGN-UNSTABLE coefficient every week,
with foresight. A deployable signal must commit to one sign for all weeks, and that sign is
right 51% of the time.

So: **a positive incremental ceiling is necessary but nowhere near sufficient.** What decides
realizability is whether the per-date relationship holds its SIGN. That is far cheaper to
measure than a ceiling, and it should be run BEFORE constructing candidates, not after.

This screens every family's features on that statistic. For each feature, per date, regress
forward return on [momentum composite, feature] and record the feature's coefficient. Then:

    share_positive   -- 50% means no stable direction; a real signal is far from 50%
    |mean|/std       -- signal-to-noise of the weekly coefficient
    NW t             -- whether the mean coefficient differs from zero at all

A feature whose share_positive is within a few points of 50% cannot be captured by any fixed
linear rule, whatever its ceiling contribution.
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
from src.research.gen10.inference import nw_mean_test, benjamini_yekutieli  # noqa: E402
from e1_ceiling_decomposition import BASE, LOCK, PRICE_BASIS  # noqa: E402

OUT = ROOT / "results/gen11/E4"
OUT.mkdir(parents=True, exist_ok=True)
SEED = 20260731
MOM = ["mom_60d_cs_z", "mom_63d_1m_lag_cs_z", "res_mom_60d", "res_mom_20d_cs_z"]

# the features E1 selected, by family, plus delivery as a positive control (it is a KNOWN
# real signal, so it must score well or the screen is broken)
TARGETS = {
    "microstructure": ["fut_oi_chg_4w_pct", "fut_oi_z52", "delivery_pct_4w_avg",
                       "delivery_pct_z52"],
    "liquidity_exposure": ["mom20_x_liquidity_cs_z", "res_mom20_x_liquidity_cs_z",
                           "fii_proxy", "international_revenue_proxy",
                           "oil_sensitivity_score", "fx_sensitivity_score",
                           "rate_sensitivity_score", "macro_linkage_score"],
    "fundamentals": ["accruals_ratio_cs_z", "operating_margin_cs_z", "roe_cs_z",
                     "debt_to_equity_cs_z", "screener_roce_cs_z",
                     "val_composite_score_zscore"],
    "earnings": ["eps_sue_cs_z", "rev_sue_cs_z", "combined_revision_score_cs_z",
                 "days_since_earnings_cs_z"],
    "events_flows": ["bulk_net_pressure_21d_cs_z", "insider_buy_flag_30d_cs_z",
                     "event_positive_flag_cs_z", "order_win_count_90d_cs_z"],
    "macro_market": ["crude_shock", "inrusd_vol_4w", "india_vix_z", "stock_x_crude",
                     "stock_x_inrusd"],
    "price (POSITIVE CONTROL)": ["mom_60d_cs_z", "res_mom_60d"],
}


def main() -> int:
    print("=" * 104)
    print("E4 — SIGN-STABILITY SCREEN: can a fixed rule capture this feature at all?")
    print("=" * 104)
    feats = sorted({c for v in TARGETS.values() for c in v})
    d = pd.read_parquet(BASE / "northstar_features_enriched.parquet",
                        columns=["date", "ticker", "target_weekly_return"]
                        + sorted(set(feats + MOM)))
    d["date"] = pd.to_datetime(d["date"]).dt.normalize()
    d = d[d["date"] <= LOCK]
    d["ret"] = d.groupby("date")["target_weekly_return"].transform(
        lambda s: s.clip(s.quantile(.01), s.quantile(.99)))
    d = d.dropna(subset=["ret"])

    def z(c):
        g = d.groupby("date")[c]
        return (d[c] - g.transform("mean")) / g.transform("std").replace(0, np.nan)
    d["mom_comp"] = pd.concat([z(c) for c in MOM], axis=1).mean(axis=1)

    print(f"\n{'family':<26}{'feature':<32}{'weeks':>6}{'share+':>8}{'|mu|/sd':>9}"
          f"{'NW t':>7}   verdict")
    print("-" * 104)
    rows = []
    for fam, cols in TARGETS.items():
        for c in cols:
            if c not in d.columns:
                continue
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
                continue
            cs = pd.Series(coefs).sort_index()
            r = nw_mean_test(cs.to_numpy(), overlap=1, n_boot=1200, seed=SEED)
            share = float((cs > 0).mean())
            snr = float(abs(cs.mean()) / cs.std()) if cs.std() > 0 else 0.0
            far = abs(share - 0.5)
            v = ("CAPTURABLE" if far >= 0.04 and abs(r.t) >= 2 else
                 "borderline" if far >= 0.03 or abs(r.t) >= 2 else
                 "coin flip — no fixed rule can capture it")
            rows.append({"family": fam, "feature": c, "n_weeks": int(len(cs)),
                         "share_positive": share, "snr": snr, "t": float(r.t),
                         "verdict": v})
            print(f"{fam:<26}{c:<32}{len(cs):>6}{share:>7.1%}{snr:>9.3f}"
                  f"{r.t:>+7.2f}   {v}")

    print("\n" + "=" * 104)
    print("RANKING by distance from a coin flip")
    print("=" * 104)
    rows.sort(key=lambda r: -abs(r["share_positive"] - 0.5))
    by = benjamini_yekutieli([abs(r["t"]) and 2 * (1 - min(0.999999,
                             abs(r["t"]) / 10)) or 1.0 for r in rows], q=0.05)
    for i, r in enumerate(rows[:12], 1):
        print(f"  {i:>2}. {r['feature']:<32} share+ {r['share_positive']:>6.1%}  "
              f"(|dev| {abs(r['share_positive']-0.5):.3f})  t={r['t']:+.2f}   {r['family']}")

    ctrl = [r for r in rows if "CONTROL" in r["family"]]
    print(f"\n  positive control (momentum, a KNOWN real signal):")
    for r in ctrl:
        print(f"    {r['feature']:<32} share+ {r['share_positive']:.1%}  t={r['t']:+.2f}")
    best_non_ctrl = [r for r in rows if "CONTROL" not in r["family"]][:1]
    print(f"\n  best non-momentum feature: {best_non_ctrl[0]['feature']} at "
          f"share+ {best_non_ctrl[0]['share_positive']:.1%}, t={best_non_ctrl[0]['t']:+.2f}"
          if best_non_ctrl else "")

    (OUT / "e4_data.json").write_text(json.dumps({"rows": rows}, indent=2, default=str))
    print(f"\n-> {OUT/'e4_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
