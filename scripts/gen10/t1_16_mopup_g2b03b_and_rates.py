#!/usr/bin/env python3
"""T1-16 — the two mop-up items.

PART A — G2-B03b: "order-win announcements -> revenue visibility". The one row in ARP's
"research-incomplete" bucket that the remediation plan missed. Archived INCONCLUSIVE with
NO t-stat recorded at all. Columns exist (`order_win_flag_30d`, `order_win_count_90d_cs_z`),
so it is testable.

PART B — T1-10's rates channel. US 10Y (`^TNX`) was UNTESTABLE there: 440 weeks of history
against a 104-week rolling exposure with a 52-week minimum, plus the lag, left fewer than
the 100-date floor. The design question is whether a SHORTER exposure window makes it
testable without giving away the identification. Run at 52w/26w and report the power
honestly rather than leaving the channel formally uncovered.

Both route through the Gen-10 inference layer (per-date collapse, NW, bootstrap) and both
report the composition share (Rule 5), since neither signal's coverage was known in advance.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.research.gen10.inference import nw_mean_test, per_date_ic, benjamini_yekutieli  # noqa: E402

OUT = ROOT / "results/gen10/T1-16"
OUT.mkdir(parents=True, exist_ok=True)
BASE = ROOT / "tmp/kaggle_uploads/panel_enriched"
SEED = 20260731
LOCK = pd.Timestamp("2025-07-11")

ORDER_WIN_COLS = ["order_win_flag_30d", "order_win_flag_30d_cs_z",
                  "order_win_count_90d_cs_z"]


# ---------------------------------------------------------------- PART A -------------
def part_a():
    print("=" * 96)
    print("PART A — G2-B03b: order-win announcements -> revenue visibility")
    print("=" * 96)
    cols = ["date", "ticker", "target_weekly_return"] + ORDER_WIN_COLS
    f = pd.read_parquet(BASE / "northstar_features_enriched.parquet", columns=cols)
    f["date"] = pd.to_datetime(f["date"]).dt.normalize()
    f["ticker"] = f["ticker"].astype(str)
    f["ret"] = f.groupby("date")["target_weekly_return"].transform(
        lambda s: s.clip(s.quantile(.01), s.quantile(.99)))

    a = pd.read_parquet(ROOT / "data/kaggle_upload/panel_a_weekly.parquet",
                        columns=["date", "ticker"])
    a["date"] = pd.to_datetime(a["date"]).dt.normalize()
    a["ticker"] = a["ticker"].astype(str)
    keys = set(map(tuple, a.to_numpy()))
    f["in_a"] = [tuple(x) in keys for x in f[["date", "ticker"]].to_numpy()]

    print("\ncoverage:")
    for c in ORDER_WIN_COLS:
        s = f[c].dropna()
        nz = (f[c].fillna(0) != 0).sum()
        print(f"  {c:<30} non-null {len(s):>7,}  non-zero {nz:>7,}  "
              f"weeks {f.loc[f[c].notna(),'date'].nunique():>5}")

    rows = []
    for c in ORDER_WIN_COLS:
        s = f[["date", c, "ret", "in_a"]].dropna()
        if s["date"].nunique() < 60 or s[c].nunique() < 3:
            print(f"\n  {c}: not testable (n_dates={s['date'].nunique()}, "
                  f"n_unique={s[c].nunique()})")
            rows.append({"col": c, "testable": False,
                         "n_dates": int(s["date"].nunique())})
            continue
        ic = per_date_ic(s, "date", c, "ret", min_pairs=20)
        r = nw_mean_test(ic.to_numpy(), overlap=1, label=c, n_boot=3000, seed=SEED)
        w = s.copy()
        for cc in (c, "ret"):
            w[cc + "_w"] = w[cc] - w.groupby(["date", "in_a"])[cc].transform("mean")
        icw = per_date_ic(w, "date", c + "_w", "ret_w", min_pairs=20)
        rw = nw_mean_test(icw.to_numpy(), overlap=1, n_boot=3000, seed=SEED)
        share = (r.estimate - rw.estimate) / r.estimate if r.estimate else np.nan
        rows.append({"col": c, "testable": True, "ic": float(r.estimate),
                     "t": float(r.t), "p": float(r.p), "n_dates": int(r.n),
                     "ic_corrected": float(rw.estimate), "t_corrected": float(rw.t),
                     "composition_share": float(share), "fragile": bool(r.fragile)})
        print(f"\n  {c}")
        print(f"    pooled     IC={r.estimate:+.5f}  t={r.t:+.2f}  p={r.p:.4f}  n={r.n}")
        print(f"    corrected  IC={rw.estimate:+.5f}  t={rw.t:+.2f}   "
              f"(composition share {share:+.0%})")
        print(f"    bootstrap 95% CI [{r.boot_ci_lo:+.5f}, {r.boot_ci_hi:+.5f}]"
              f"{'  FRAGILE' if r.fragile else ''}")

    tested = [r for r in rows if r.get("testable")]
    if tested:
        by = benjamini_yekutieli([r["p"] for r in tested], q=0.05)
        for r, ok in zip(tested, by):
            r["by_clean"] = bool(ok)
        best = max(tested, key=lambda r: abs(r["t_corrected"]))
        verdict = ("PROMOTE" if abs(best["t_corrected"]) >= 2 and any(by) else "REJECTED")
        print(f"\n  BY q=0.05 across {len(tested)} specs: {int(sum(by))} clean")
        print(f"  --> G2-B03b: {verdict}  (best corrected |t| = {abs(best['t_corrected']):.2f})")
    else:
        verdict = "NOT TESTABLE"
        print(f"\n  --> G2-B03b: {verdict}")
    return {"rows": rows, "verdict": verdict}


# ---------------------------------------------------------------- PART B -------------
def part_b():
    print("\n" + "=" * 96)
    print("PART B — T1-10's rates channel, at a shorter exposure window")
    print("=" * 96)
    d = pd.read_parquet(ROOT / "data/kaggle_upload/panel_a_weekly.parquet",
                        columns=["date", "ticker", "sector", "ret_1w", "target_1w"])
    d["date"] = pd.to_datetime(d["date"]).dt.normalize()
    d = d[d["sector"].notna() & (d["sector"] != "UNKNOWN")].copy()
    mkt = d.groupby("date")["ret_1w"].mean().rename("mkt_ret")
    mktf = d.groupby("date")["target_1w"].mean().rename("mkt_fwd")
    d = d.merge(mkt, on="date").merge(mktf, on="date").sort_values(["ticker", "date"])

    ca = pd.read_parquet(BASE / "cross_asset_prices_daily.parquet",
                         columns=["date", "symbol", "close"])
    ca["date"] = pd.to_datetime(ca["date"]).dt.normalize()
    dates = pd.Index(sorted(d["date"].unique()))
    out = {}
    for BETA_W, MINP in ((104, 52), (52, 26), (26, 13)):
        res = {}
        for sym, chan in (("^TNX", ["Real Estate"]), ("DX-Y.NYB", ["Information Technology",
                                                                   "Materials"])):
            s = ca[ca["symbol"] == sym].set_index("date")["close"].sort_index()
            s = s[~s.index.duplicated(keep="last")]
            s = s.reindex(s.index.union(dates)).ffill().reindex(dates)
            shock = np.log(s / s.shift(4))
            dd = d.copy()
            dd["shk_now"] = dd["date"].map(shock)
            g = dd.groupby("ticker")
            cov = g.apply(lambda x: x["ret_1w"].rolling(BETA_W, min_periods=MINP)
                          .cov(x["shk_now"]), include_groups=False
                          ).reset_index(level=0, drop=True)
            var = dd.groupby("ticker")["shk_now"].transform(
                lambda x: x.rolling(BETA_W, min_periods=MINP).var())
            dd["expo"] = (cov / var.replace(0, np.nan)).clip(-5, 5)
            # beta-residualised forward return (contract s1 point 3)
            cov2 = g.apply(lambda x: x["ret_1w"].rolling(104, min_periods=52)
                           .cov(x["mkt_ret"]), include_groups=False
                           ).reset_index(level=0, drop=True)
            var2 = dd.groupby("ticker")["mkt_ret"].transform(
                lambda x: x.rolling(104, min_periods=52).var())
            dd["beta"] = (cov2 / var2.replace(0, np.nan)).clip(-3, 3)
            dd["resid_fwd"] = dd["target_1w"] - dd["beta"] * dd["mkt_fwd"]
            for lag in (1, 2, 4):
                dd["_reg"] = dd["expo"] * dd["date"].map(shock.shift(lag))
                ch = dd[dd["sector"].isin(chan)]
                slopes = {}
                for dt, gg in ch.groupby("date"):
                    ss = gg[["_reg", "resid_fwd"]].dropna()
                    if len(ss) < 30 or ss["_reg"].std() == 0:
                        continue
                    xc = ss["_reg"] - ss["_reg"].mean()
                    den = float((xc ** 2).sum())
                    if den <= 0:
                        continue
                    slopes[dt] = float((xc * (ss["resid_fwd"] - ss["resid_fwd"].mean())).sum() / den)
                n = len(slopes)
                if n < 100:
                    res[f"{sym}|lag{lag}"] = {"n_dates": n, "testable": False}
                    continue
                r = nw_mean_test(pd.Series(slopes).sort_index().to_numpy(), overlap=4,
                                 n_boot=1500, seed=SEED)
                res[f"{sym}|lag{lag}"] = {"n_dates": n, "testable": True,
                                          "t": float(r.t), "p": float(r.p)}
        out[f"{BETA_W}w/{MINP}w"] = res
        n_test = sum(1 for v in res.values() if v["testable"])
        print(f"\n  exposure window {BETA_W}w (min {MINP}w): "
              f"{n_test}/{len(res)} carrier-lags testable")
        for k, v in res.items():
            if v["testable"]:
                print(f"    {k:<20} n={v['n_dates']:>4}  t={v['t']:+.2f}  p={v['p']:.4f}")
            else:
                print(f"    {k:<20} n={v['n_dates']:>4}  NOT TESTABLE (<100 dates)")
    return out


def main() -> int:
    a = part_a()
    b = part_b()
    (OUT / "t1_16_data.json").write_text(json.dumps({"g2_b03b": a, "rates_channel": b},
                                                    indent=2, default=str))
    print(f"\n-> {OUT/'t1_16_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
