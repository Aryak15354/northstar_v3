#!/usr/bin/env python3
"""E1 — Ceiling decomposition: where does information actually live?

Gen-10 measured the attainable predictability ceiling at IC +0.141 on the 15-feature PRICE
basis, with the deployed book capturing 20%, and named the one exception to its closing
statement: the ceiling is basis-specific.

This asks the question that has never been asked in this programme: does any OTHER feature
family raise the joint ceiling above the price basis alone?

That is not the same question as "does this family contain a signal". Gen-1/2/3 tested most
of these families individually and rejected them. A family can carry no standalone signal and
still raise the joint ceiling -- through interaction, conditioning, or by spanning a direction
the price features do not.

METHOD, and the part that decides whether the answer means anything:
  * per date, fit an in-sample OLS oracle -- the best possible linear combination of the
    feature set, knowing that week's realised returns. That bounds any model.
  * adding features RAISES the raw oracle mechanically. So every arm is measured against its
    OWN permutation null (same design matrix, shuffled target), and the reported ceiling is
    the EXCESS over that null. Gen-10 showed 60% of a raw oracle can be overfitting, and that
    an analytic k/n correction is invalid in IC space.
  * price-alone and price+family are computed on the SAME DATES (Rule 6). Family coverage
    varies enormously -- delivery is 2020+, sentiment 2024+ -- so an unmatched comparison
    would compare eras, not feature sets.
  * each family is capped at the 12 best-covered features so k is comparable across arms.

Pre-registered in GEN11_ALPHA_DISCOVERY_CHARTER.md s5. Descriptive: proposes no strategy.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.research.gen10.inference import nw_mean_test  # noqa: E402

OUT = ROOT / "results/gen11/E1"
OUT.mkdir(parents=True, exist_ok=True)
BASE = ROOT / "tmp/kaggle_uploads/panel_enriched"
SEED = 20260731
LOCK = pd.Timestamp("2025-07-11")
MAX_PER_FAMILY = 12
MIN_NAMES = 80
MIN_DATES = 150
N_PERM = 3

# The enriched panel carries its OWN price columns (PANEL-A's names do not exist here).
# This is the enriched-panel equivalent of Gen-10's 15-feature price basis: momentum at
# several horizons, residual momentum, volatility, liquidity, lottery and beta.
PRICE_BASIS = ["mom_60d_cs_z", "mom_20d_cs_z", "mom_63d_1m_lag_cs_z",
               "res_mom_60d", "res_mom_20d_cs_z",
               "ret_20d_cs_z", "ret_5d_cs_z",
               "vol_60d", "vol_20d", "vol_z20",
               "amihud_illiquidity_cs_z", "max_ret_20d_cs_z",
               "price_to_sma20_cs_z"]
# NOTE: `bab_signal_cs_z` was in this basis on the first run and was REMOVED. It exists only
# from 2021-02-05 (232 weeks) and silently collapsed EVERY family arm to that window --
# i.e. every family was being judged inside the microstructure era. The other 13 columns
# each cover all 1,071 weeks, so each family is now limited by its OWN coverage, which is
# the correct behaviour.


def classify(c):
    if re.match(r'^(mom_|ret_|res_mom|price_to|max_ret|high_52|vol_\d|skew|beta_)', c):
        return "price"
    if c.startswith("rbi_"):
        return "macro_rbi"
    if c.startswith(("macro_", "crude_", "copper_", "gold_", "dxy_", "inrusd_",
                     "commodity_", "vix_")):
        return "macro_market"
    if c.startswith(("sent_", "mkt_sent", "narrative_")):
        return "sentiment"
    if c.startswith(("screener_", "val_", "roe", "debt_to", "piotroski", "cash_conv",
                     "operating_margin", "accruals", "pledge", "rating_")):
        return "fundamentals"
    if c.startswith(("credit_", "bank_")):
        return "credit"
    if c.startswith(("eps_", "rev_", "combined_revision", "days_since_earn")):
        return "earnings"
    if c.startswith(("bulk_", "insider_", "institutional_", "order_win", "event_")):
        return "events_flows"
    if c.startswith(("fut_oi", "delivery_", "partoi_", "nifty50_")):
        return "microstructure"
    if c.startswith(("amihud", "mom20_x_liq", "res_mom20_x_liq", "fii_proxy",
                     "international_rev", "oil_sens", "fx_sens", "rate_sens",
                     "gold_sens", "copper_sens", "macro_link")):
        return "liquidity_exposure"
    return None


def pick_features(pf, fams):
    """Up to MAX_PER_FAMILY best-covered numeric features per family."""
    names = [c for c in pf.schema_arrow.names if not c.startswith("__")]
    by = {}
    for c in names:
        f = classify(c)
        if f in fams:
            by.setdefault(f, []).append(c)
    # coverage from the row-group statistics is unavailable; sample a slice instead
    samp = pd.read_parquet(BASE / "northstar_features_enriched.parquet",
                           columns=["date"] + sum(by.values(), []))
    samp["date"] = pd.to_datetime(samp["date"])
    samp = samp[samp["date"] <= LOCK]
    out = {}
    for f, cs in by.items():
        cov = {}
        for c in cs:
            s = pd.to_numeric(samp[c], errors="coerce")
            if s.notna().sum() < 20000 or s.nunique() < 20:
                continue
            cov[c] = s.notna().sum()
        top = sorted(cov, key=cov.get, reverse=True)[:MAX_PER_FAMILY]
        if top:
            out[f] = top
    return out


def oracle_excess(d, cols, label):
    """Per-date in-sample oracle IC minus its own measured permutation null."""
    rng = np.random.default_rng(SEED)
    real, null = {}, {}
    for dt, g in d.groupby("date"):
        s = g[cols + ["ret"]].dropna()
        if len(s) < max(MIN_NAMES, 4 * len(cols)):
            continue
        X = s[cols].to_numpy(float)
        sd = X.std(0)
        X = (X - X.mean(0)) / np.where(sd > 0, sd, 1.0)
        y = s["ret"].to_numpy(float)

        def ic_of(t):
            try:
                b, *_ = np.linalg.lstsq(X, t - t.mean(), rcond=None)
            except np.linalg.LinAlgError:
                return np.nan
            p = X @ b
            return float(pd.Series(p).corr(pd.Series(t), method="spearman")) if p.std() > 0 else np.nan

        v = ic_of(y)
        if not np.isfinite(v):
            continue
        real[dt] = v
        null[dt] = float(np.nanmean([ic_of(rng.permutation(y)) for _ in range(N_PERM)]))
    if len(real) < MIN_DATES:
        return None
    R = pd.Series(real).sort_index()
    N = pd.Series(null).sort_index()
    j = R.index.intersection(N.index)
    ex = nw_mean_test((R - N).reindex(j).to_numpy(), overlap=1, n_boot=1200, seed=SEED)
    return {"label": label, "k": len(cols), "n_dates": int(len(j)),
            "oracle_raw": float(R.reindex(j).mean()), "oracle_null": float(N.reindex(j).mean()),
            "ceiling": float(ex.estimate), "t": float(ex.t),
            "boot_lo": ex.boot_ci_lo, "boot_hi": ex.boot_ci_hi, "dates": j}


def main() -> int:
    print("=" * 100)
    print("E1 — CEILING DECOMPOSITION: where does information live?")
    print("=" * 100)
    pf = pq.ParquetFile(BASE / "northstar_features_enriched.parquet")
    fams = ["macro_rbi", "macro_market", "sentiment", "fundamentals", "credit",
            "earnings", "events_flows", "microstructure", "liquidity_exposure"]
    picked = pick_features(pf, fams)
    print("\nfeatures selected per family (best-covered, capped at "
          f"{MAX_PER_FAMILY}):")
    for f, cs in picked.items():
        print(f"  {f:<20} {len(cs):>2}  e.g. {', '.join(cs[:3])}")

    need = sorted(set(PRICE_BASIS + sum(picked.values(), [])))
    d = pd.read_parquet(BASE / "northstar_features_enriched.parquet",
                        columns=["date", "ticker", "target_weekly_return"] + need)
    d["date"] = pd.to_datetime(d["date"]).dt.normalize()
    d = d[d["date"] <= LOCK]
    d["ret"] = d.groupby("date")["target_weekly_return"].transform(
        lambda s: s.clip(s.quantile(.01), s.quantile(.99)))
    d = d.dropna(subset=["ret"])
    print(f"\npanel: {len(d):,} rows | {d['date'].nunique()} dates")

    print("\n" + "-" * 100)
    print(f"{'family':<20}{'k':>4}{'dates':>7}{'price-only':>13}{'price+family':>14}"
          f"{'INCREMENTAL':>13}{'t':>8}   bootstrap CI")
    print("-" * 100)
    rows = []
    for f, cs in picked.items():
        aug = oracle_excess(d, PRICE_BASIS + cs, f"price+{f}")
        if aug is None:
            print(f"{f:<20}{len(cs):>4}   -- insufficient dates")
            continue
        sub = d[d["date"].isin(aug["dates"])]          # Rule 6: matched dates
        basep = oracle_excess(sub, PRICE_BASIS, "price-only")
        if basep is None:
            print(f"{f:<20}{len(cs):>4}   -- baseline not computable")
            continue
        inc = aug["ceiling"] - basep["ceiling"]
        rows.append({"family": f, "k_family": len(cs), "n_dates": aug["n_dates"],
                     "ceiling_price": basep["ceiling"], "ceiling_aug": aug["ceiling"],
                     "incremental": float(inc), "t_aug": aug["t"],
                     "boot": [aug["boot_lo"], aug["boot_hi"]],
                     "features": cs})
        print(f"{f:<20}{len(cs):>4}{aug['n_dates']:>7}{basep['ceiling']:>13.4f}"
              f"{aug['ceiling']:>14.4f}{inc:>+13.4f}{aug['t']:>8.1f}   "
              f"[{aug['boot_lo']:+.4f},{aug['boot_hi']:+.4f}]")

    rows.sort(key=lambda r: -r["incremental"])
    print("\n" + "=" * 100)
    print("RANKING — incremental attainable ceiling over the price basis")
    print("=" * 100)
    for i, r in enumerate(rows, 1):
        flag = "  <-- worth opening" if r["incremental"] > 0.02 else ""
        print(f"  {i}. {r['family']:<20} {r['incremental']:+.4f}   "
              f"({r['n_dates']} dates, k={r['k_family']}){flag}")
    best = rows[0] if rows else None
    if best and best["incremental"] > 0.02:
        print(f"\n  -> E2 opens on '{best['family']}'.")
    else:
        print("\n  -> NO family clears +0.02 incremental. Per charter s6, Gen-11 CLOSES here")
        print("     and Gen-10's closing statement stands unamended.")

    payload = {"experiment": "E1", "max_per_family": MAX_PER_FAMILY,
               "price_basis": PRICE_BASIS,
               "rows": [{k: v for k, v in r.items()} for r in rows]}
    (OUT / "e1_data.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n-> {OUT/'e1_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
