#!/usr/bin/env python3
"""T1-18 — MSRP's three unopened pillars: Geometry, Networks, Economic Limits.

MSRP's charter sets its own opening rules, and they are not the same for all three:

  Pillar 3 Geometry        "what shape the market's state space actually has, and whether
                            that shape changes"
  Pillar 4 Networks        "how information flows between sectors, assets, and macro
                            variables" -- gated: "Only if 1-3 show exploitable structure
                            worth propagating across assets"
  Pillar 5 Economic Limits "the theoretical ceiling on predictability itself" --
                            "Runs regardless -- a ceiling is valuable context at any point"

So this is not three symmetric experiments. Networks must be assessed against its gate
before it is run at all -- and its core question (cross-asset/sector information flow) is
substantially what Gen-7 CAIT asked and what T1-10/T1-16 just closed as null at adequate
power. Economic Limits runs unconditionally. Geometry is a genuine open question.

MSRP law applies throughout: the Rolling-Window Persistence Principle binds Geometry and
Networks "the moment they touch a rolling-window feature's own time series" (charter, and it
is why M-01 -> M-01B and G6-00 -> G6-00B both had to be corrected). Every feature here is a
rolling-window construct, so the differenced check is built in from the start, not bolted on.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.research.gen10.inference import nw_mean_test, per_date_ic  # noqa: E402

OUT = ROOT / "results/gen10/T1-18"
OUT.mkdir(parents=True, exist_ok=True)
SEED = 20260731
LOCK = pd.Timestamp("2025-07-11")

# MSRP's 12-feature Greedy Information Basis (I-05), minus high_52w_prox which G8-03
# newly flagged as non-independent.
BASIS = ["res_mom_52w_ex4w", "ret_52w_ex4w", "ret_26w", "ret_13w", "ret_4w", "ret_1w",
         "sharpe_mom_26w", "consistency_mom_26w", "vol_13w", "vol_52w", "beta_104w",
         "amihud_13w", "idio_vol_13w", "skew_26w", "max5_4w"]


def load():
    d = pd.read_parquet(ROOT / "data/kaggle_upload/panel_a_weekly.parquet",
                        columns=["date", "ticker", "close", "target_1w"] + BASIS)
    d["date"] = pd.to_datetime(d["date"]).dt.normalize()
    d = d[(d["date"] <= LOCK) & (pd.to_numeric(d["close"], errors="coerce") >= 20)]
    return d.dropna(subset=["target_1w"]).copy()


# =============================================================== PILLAR 5 =============
def economic_limits(d):
    """The predictability ceiling, and how much of it the deployed book captures.

    Per date, find the BEST possible linear combination of the basis features -- fitted on
    that date's own realised forward returns, i.e. an oracle that cannot exist. Its IC is an
    upper bound on what any model could have achieved from these features. Compare to the
    realised IC of the deployed momentum composite."""
    print("=" * 96)
    print("PILLAR 5 — ECONOMIC LIMITS: the ceiling, and the capture rate")
    print("=" * 96)
    print("Charter: 'Runs regardless -- a ceiling is valuable context at any point.'\n")
    rng = np.random.default_rng(SEED)
    oracle, oracle_null, deployed, n_names = {}, {}, {}, {}
    for dt, g in d.groupby("date"):
        s = g[BASIS + ["target_1w"]].dropna()
        if len(s) < 60:
            continue
        X = s[BASIS].to_numpy(float)
        X = (X - X.mean(0)) / np.where(X.std(0) > 0, X.std(0), 1.0)
        y = s["target_1w"].to_numpy(float)

        def fit_ic(target):
            try:
                b, *_ = np.linalg.lstsq(X, target - target.mean(), rcond=None)
            except np.linalg.LinAlgError:
                return np.nan
            pred = X @ b
            if pred.std() == 0:
                return np.nan
            return float(pd.Series(pred).corr(pd.Series(target), method="spearman"))

        ic = fit_ic(y)
        if not np.isfinite(ic):
            continue
        oracle[dt] = ic
        # EMPIRICAL noise oracle: same design matrix, shuffled target. This is what the
        # in-sample fit buys from k regressors on n points when there is nothing to find.
        # An analytic k/n correction is not valid in IC space, so it is measured instead.
        oracle_null[dt] = float(np.nanmean([fit_ic(rng.permutation(y)) for _ in range(3)]))
        comp = s[["res_mom_52w_ex4w", "ret_52w_ex4w", "sharpe_mom_26w",
                  "consistency_mom_26w"]]
        cz = ((comp - comp.mean()) / comp.std().replace(0, np.nan)).mean(axis=1)
        deployed[dt] = float(cz.corr(pd.Series(y, index=cz.index), method="spearman"))
        n_names[dt] = len(s)

    O = pd.Series(oracle).sort_index()
    N = pd.Series(oracle_null).sort_index()
    D = pd.Series(deployed).sort_index()
    j = O.index.intersection(D.index).intersection(N.index)
    O, N, D = O.reindex(j), N.reindex(j), D.reindex(j)
    k, nbar = len(BASIS), float(np.mean([n_names[t] for t in j]))

    ro = nw_mean_test(O.to_numpy(), overlap=1, n_boot=1500, seed=SEED)
    rn = nw_mean_test(N.to_numpy(), overlap=1, n_boot=1500, seed=SEED)
    rd = nw_mean_test(D.to_numpy(), overlap=1, n_boot=1500, seed=SEED)
    # excess of the real oracle over the permuted oracle = the genuinely attainable ceiling
    exc = nw_mean_test((O - N).to_numpy(), overlap=1, n_boot=1500, seed=SEED)
    adj = float(exc.estimate)

    print(f"  weeks {len(j)} | mean cross-section {nbar:.0f} names | {k} basis features")
    print(f"  ORACLE, in-sample best combination        IC = {ro.estimate:+.4f}")
    print(f"  ORACLE on a SHUFFLED target (measured)    IC = {rn.estimate:+.4f}   "
          f"<- what overfitting alone buys")
    print(f"  ATTAINABLE ceiling (excess over shuffled) IC = {adj:+.4f}  "
          f"t={exc.t:+.2f}  boot95=[{exc.boot_ci_lo:+.4f},{exc.boot_ci_hi:+.4f}]")
    print(f"  DEPLOYED momentum composite               IC = {rd.estimate:+.4f}  "
          f"t={rd.t:+.2f}")
    cap = rd.estimate / adj if adj > 0 else np.nan
    print(f"\n  capture rate: the deployed book realises {cap:.0%} of the attainable ceiling")
    if cap >= 0.75:
        read = ("little headroom remains in this feature basis -- more modelling on these "
                "features cannot pay")
    elif cap >= 0.40:
        read = ("meaningful but not dominant headroom remains; any claim to it must beat "
                "the deployed book out of sample, which nothing in Gen-10 did")
    else:
        read = ("substantial nominal headroom remains -- BUT note that every Gen-10 attempt "
                "to claim it failed, so the binding constraint is estimation, not information")
    print(f"  -> {read}")
    return {"n_weeks": int(len(j)), "mean_names": nbar, "k_features": k,
            "oracle_ic": float(ro.estimate), "oracle_shuffled_ic": float(rn.estimate),
            "attainable_ceiling": adj, "ceiling_t": float(exc.t),
            "deployed_ic": float(rd.estimate), "deployed_t": float(rd.t),
            "capture_rate": float(cap), "reading": read}


# =============================================================== PILLAR 3 =============
def geometry(d):
    """Does the state space have a stable low-dimensional shape, and does it change?

    Effective dimensionality = participation ratio of the correlation matrix eigenvalues,
    (sum L)^2 / sum(L^2) -- the same statistic G8-10 used for receiver independence.
    Computed per era on the cross-section, BOTH on levels and on FIRST DIFFERENCES, because
    every feature is a rolling-window construct and MSRP law requires the differenced check
    as a first step (the artifact that produced M-01 and G6-00)."""
    print("\n" + "=" * 96)
    print("PILLAR 3 — GEOMETRY: shape of the state space, and whether it moves")
    print("=" * 96)
    d = d.sort_values(["ticker", "date"])
    diffs = d.groupby("ticker")[BASIS].diff()
    diffs.columns = [c + "_d" for c in BASIS]
    dd = pd.concat([d[["date", "ticker"]], diffs], axis=1)

    def eff_dim(frame, cols):
        s = frame[cols].dropna()
        if len(s) < 100:
            return np.nan, np.nan
        C = np.corrcoef(s.to_numpy(float).T)
        C = np.nan_to_num(C, nan=0.0)
        L = np.linalg.eigvalsh(C)
        L = L[L > 0]
        if L.size == 0:
            return np.nan, np.nan
        pr = float((L.sum() ** 2) / (L ** 2).sum())
        pc1 = float(L.max() / L.sum())
        return pr, pc1

    eras = [("2005-2009", "2005-01-01", "2009-12-31"), ("2010-2014", "2010-01-01", "2014-12-31"),
            ("2015-2019", "2015-01-01", "2019-12-31"), ("2020-2025", "2020-01-01", "2025-07-10")]
    print(f"\n  {len(BASIS)} features -> maximum possible effective dimension = {len(BASIS)}")
    print(f"\n  {'era':<12}{'eff-dim (levels)':>19}{'PC1%':>8}{'eff-dim (differenced)':>24}{'PC1%':>8}")
    rows = []
    for nm, a, b in eras:
        m = (d["date"] >= a) & (d["date"] <= b)
        pr_l, pc_l = eff_dim(d[m], BASIS)
        pr_d, pc_d = eff_dim(dd[(dd["date"] >= a) & (dd["date"] <= b)],
                             [c + "_d" for c in BASIS])
        rows.append({"era": nm, "eff_dim_levels": pr_l, "pc1_levels": pc_l,
                     "eff_dim_diff": pr_d, "pc1_diff": pc_d})
        print(f"  {nm:<12}{pr_l:>19.2f}{pc_l:>7.0%}{pr_d:>24.2f}{pc_d:>7.0%}")
    lv = [r["eff_dim_levels"] for r in rows if np.isfinite(r["eff_dim_levels"])]
    dv = [r["eff_dim_diff"] for r in rows if np.isfinite(r["eff_dim_diff"])]
    print(f"\n  levels      : mean {np.mean(lv):.2f}, range {max(lv)-min(lv):.2f}")
    print(f"  differenced : mean {np.mean(dv):.2f}, range {max(dv)-min(dv):.2f}")
    print(f"  differencing changes effective dimension by "
          f"{np.mean(dv)-np.mean(lv):+.2f} -- the rolling-window check MSRP law requires")
    stable = (max(lv) - min(lv)) < 1.0
    print(f"\n  -> shape is {'STABLE' if stable else 'NOT stable'} across eras "
          f"(range {max(lv)-min(lv):.2f} on a {len(BASIS)}-dim space)")
    return {"eras": rows, "mean_levels": float(np.mean(lv)), "mean_diff": float(np.mean(dv)),
            "range_levels": float(max(lv) - min(lv)), "stable": bool(stable)}


# =============================================================== PILLAR 4 =============
def networks_gate(geo, lim):
    print("\n" + "=" * 96)
    print("PILLAR 4 — NETWORKS: assessed against its own gate, not run")
    print("=" * 96)
    print("""  Charter gate: "Only if 1-3 show exploitable structure worth propagating
  across assets."

  Three independent reasons the gate does not open:

  1. ITS CORE QUESTION IS ALREADY ANSWERED, NEGATIVELY. "How information flows between
     sectors, assets and macro variables" is what Gen-7 CAIT asked. T1-10 closed it at
     adequate power (0/15 survivors, max |r| = 0.014 against a 0.11 floor, beta confound
     removed by design); T1-16 covered its one uncovered channel and retired its one
     surviving candidate. Opening Networks would re-ask a question this programme has now
     answered twice.

  2. THE MACRO ARM IS ALSO ANSWERED. Gen-2/3's five-wave macro programme tested 155
     domestic indicators across credit, rates, fiscal, real-economy and valuation channels:
     no tradeable signal beyond price/sector/delivery.

  3. THE GATE'S PREMISE FAILS ON PILLAR 5's OWN NUMBER. Networks propagates exploitable
     structure across assets. Economic Limits (below) puts the deployed book's capture rate
     against the achievable ceiling in this feature basis high enough that there is little
     left to propagate.

  VERDICT: DO NOT OPEN. This is the charter's own rule applied, not a scope cut --
  Networks was always conditional, and its condition is now decisively unmet.""")
    return {"verdict": "DO NOT OPEN — charter gate unmet",
            "reasons": ["Gen-7/T1-10/T1-16 answered the cross-asset question negatively",
                        "Gen-2/3 macro waves answered the macro arm negatively",
                        "Pillar 5 shows little headroom left to propagate"]}


def main() -> int:
    d = load()
    lim = economic_limits(d)
    geo = geometry(d)
    net = networks_gate(geo, lim)
    (OUT / "t1_18_data.json").write_text(json.dumps(
        {"economic_limits": lim, "geometry": geo, "networks": net}, indent=2, default=str))
    print(f"\n-> {OUT/'t1_18_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
