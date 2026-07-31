#!/usr/bin/env python3
"""T1-09 — DS momentum-quality and cross-factor clusters.

Two changes to the plan's design, both forced by earlier Gen-10 results:

  1. These signals are BROAD-COVERAGE (built from mom_60d_cs_z, vol_60d, amihud), unlike
     delivery. T0-03 showed broad-coverage signals on the enriched panel carry a
     universe-composition artifact worth ~36% of the headline IC. So every signal here is
     evaluated BOTH pooled and with between-group variation removed, and Stage 1 is
     decided on the corrected number.

  2. DS-F2-03 runs its COST check first (charter s4/T1-09). It is a reversal x illiquidity
     interaction and Gen-1 killed that family twice: A04 (1-week reversal, real IC
     t=-6.82, dead at 4187%/yr turnover) and A15/A19 (momentum x illiquidity, "edge sits
     exactly where impact cost kills it"). Pre-registered: if its turnover profile matches
     A04's, it is retired without running the remaining stages.

Windows (fixed before any result was read; these signals have full 2005-2026 history):
  DISCOVERY 2005-01-07 .. 2017-12-29
  OOS       2018-01-05 .. 2025-07-10
  LOCKBOX   2025-07-11 .. 2026-06-26
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
    nw_mean_test, per_date_ic, benjamini_yekutieli, sharpe, ANN_WEEKLY,
)

OUT = ROOT / "results/gen10/T1-09"
OUT.mkdir(parents=True, exist_ok=True)
BASE = ROOT / "tmp/kaggle_uploads/panel_enriched"
SEED = 20260731
DISC_END = pd.Timestamp("2017-12-31")
OOS_END = pd.Timestamp("2025-07-10")

# deduped. DS-U-03 dropped: identical spec `pa_mom_smooth` to DS-F4-01.
CLUSTER = [
    ("DS-F4-01", "signal",      "pa_mom_smooth",   +3.06, "momentum-quality", "smooth vs jumpy momentum"),
    ("DS-F4-02", "signal",      "pa_mom_declpart", +6.33, "momentum-quality", "momentum w/ declining participation"),
    ("DS-U-01",  "signal",      "mom_60d_cs_z",    +2.91, "momentum-quality", "unconditional 3m momentum"),
    ("DS-F2-06", "conditional", "mom_60d_cs_z|vol_60d|lo", +3.38, "momentum-quality", "momentum in low-vol names"),
    ("DS-F2-03", "conditional", "res_mom_20d_cs_z|amihud_illiquidity_cs_z|hi", -8.91, "cross-factor", "reversal after liquidity shocks"),
    ("DS-F2-04", "conditional", "val_composite_score_zscore|z_ret_20d|lo", +2.20, "cross-factor", "value when price weak"),
]
DROPPED = [("DS-U-03", "DS-F4-01", "identical spec `pa_mom_smooth`")]


def load() -> pd.DataFrame:
    cols = ["date", "ticker", "target_weekly_return", "mom_60d_cs_z", "res_mom_20d_cs_z",
            "amihud_illiquidity_cs_z", "vol_60d", "vol_surge_5d", "ret_20d",
            "val_composite_score_zscore", "close", "volume"]
    have = set(pd.read_parquet(BASE / "northstar_features_enriched.parquet",
                               columns=["date"]).columns)  # cheap open
    f = pd.read_parquet(BASE / "northstar_features_enriched.parquet",
                        columns=[c for c in cols if c not in ("close", "volume")])
    md = pd.read_parquet(BASE / "northstar_metadata.parquet",
                         columns=["date", "ticker", "close", "volume"])
    for d in (f, md):
        d["date"] = pd.to_datetime(d["date"]).dt.normalize()
        d["ticker"] = d["ticker"].astype(str)
    d = f.merge(md, on=["date", "ticker"], how="left")
    d["adv"] = pd.to_numeric(d["close"], errors="coerce") * pd.to_numeric(d["volume"],
                                                                         errors="coerce")
    d["ret"] = d.groupby("date")["target_weekly_return"].transform(
        lambda s: s.clip(s.quantile(.01), s.quantile(.99)))

    def zc(c):
        g = d.groupby("date")[c]
        return (d[c] - g.transform("mean")) / g.transform("std").replace(0, np.nan)

    d["z_vol_60d"] = zc("vol_60d")
    d["z_vol_surge_5d"] = zc("vol_surge_5d")
    d["z_ret_20d"] = zc("ret_20d")
    d["pa_mom_smooth"] = pd.to_numeric(d["mom_60d_cs_z"]) / (d["z_vol_60d"].abs() + 1.0)
    d["pa_mom_declpart"] = d["mom_60d_cs_z"] * (-d["z_vol_surge_5d"])

    # PANEL-A membership, for the composition correction (T0-03)
    a = pd.read_parquet(ROOT / "data/kaggle_upload/panel_a_weekly.parquet",
                        columns=["date", "ticker"])
    a["date"] = pd.to_datetime(a["date"]).dt.normalize()
    a["ticker"] = a["ticker"].astype(str)
    keys = set(map(tuple, a.to_numpy()))
    d["in_a"] = [tuple(x) in keys for x in d[["date", "ticker"]].to_numpy()]
    return d


def slice_for(d: pd.DataFrame, kind: str, spec: str) -> tuple[pd.DataFrame, str]:
    """Return (frame, signal_column) for either a plain signal or a conditional test,
    reproducing deepsearch.conditional_ic's tercile gating."""
    if kind == "signal":
        return d, spec
    sig, state, side = spec.split("|")
    hi = side == "hi"
    thr = d.groupby("date")[state].transform(lambda s: s.quantile(0.66 if hi else 0.34))
    sub = d[d[state] >= thr] if hi else d[d[state] <= thr]
    return sub, sig


def ic_pair(d: pd.DataFrame, col: str, label: str, min_pairs: int = 20) -> tuple:
    """(pooled, composition-corrected) IC tests."""
    s = d[["date", col, "ret", "in_a"]].dropna()
    if s["date"].nunique() < 20:
        return None, None
    ic = per_date_ic(s, "date", col, "ret", min_pairs=min_pairs)
    pooled = nw_mean_test(ic.to_numpy(), overlap=1, label=label, n_boot=2000, seed=SEED)
    w = s.copy()
    for c in (col, "ret"):
        w[c + "_w"] = w[c] - w.groupby(["date", "in_a"])[c].transform("mean")
    icw = per_date_ic(w, "date", col + "_w", "ret_w", min_pairs=min_pairs)
    corrected = nw_mean_test(icw.to_numpy(), overlap=1, label=label + " (corr)",
                             n_boot=2000, seed=SEED)
    return pooled, corrected


def signal_turnover(d: pd.DataFrame, col: str, q: float = 0.8) -> dict:
    """Weekly name turnover of a top-quintile long book on `col`, and the annualised
    two-way turnover that Gen-1 A04 reported as 4187%/yr for 1-week reversal."""
    holds = {}
    for dt, g in d.groupby("date"):
        s = g[[col, "ticker"]].dropna()
        if len(s) < 30:
            continue
        thr = s[col].quantile(q)
        holds[dt] = set(s.loc[s[col] >= thr, "ticker"])
    ks = sorted(holds)
    t = [len(holds[a] ^ holds[b]) / (len(holds[a]) + len(holds[b]))
         for a, b in zip(ks[:-1], ks[1:]) if holds[a] and holds[b]]
    wk = float(np.mean(t)) if t else np.nan
    return {"weekly_turnover": wk, "annual_two_way_pct": float(wk * 52 * 2 * 100)}


def main() -> int:
    print("=" * 104)
    print("T1-09 — DS MOMENTUM-QUALITY AND CROSS-FACTOR CLUSTERS")
    print("=" * 104)
    d = load()
    print(f"panel: {len(d):,} rows | {d['date'].nunique():,} dates")
    print(f"deduped: {len(CLUSTER)} tests (dropped {DROPPED[0][0]} == {DROPPED[0][1]})\n")

    # ---------------------------------------------------------------- Stage 4 FIRST -----
    print("=" * 104)
    print("PRE-STAGE — DS-F2-03 COST CHECK (charter s4/T1-09: run Stage 4 first)")
    print("=" * 104)
    print("DS-F2-03 is reversal x illiquidity. Gen-1 killed this family twice:")
    print("  A04     1-week reversal: real IC (t=-6.82) dead at 4187%/yr turnover")
    print("  A15/A19 momentum x illiquidity: 'edge sits exactly where impact cost kills it'")
    sub, sig = slice_for(d, "conditional", CLUSTER[4][2])
    tn = signal_turnover(sub, sig)
    a04_annual = 4187.0
    matches_a04 = tn["annual_two_way_pct"] >= 0.5 * a04_annual
    print(f"\n  DS-F2-03 top-quintile book turnover: {tn['weekly_turnover']:.3f}/week "
          f"= {tn['annual_two_way_pct']:.0f}%/yr two-way")
    print(f"  A04 reference: {a04_annual:.0f}%/yr")
    # a slow-moving control, to show the measurement is discriminating
    tn_mom = signal_turnover(d, "mom_60d_cs_z")
    print(f"  control (mom_60d_cs_z): {tn_mom['annual_two_way_pct']:.0f}%/yr")
    print(f"\n  -> turnover profile {'MATCHES' if matches_a04 else 'does NOT match'} "
          f"the A04 reversal family")
    if matches_a04:
        print("  -> RETIRED without running the remaining stages, per pre-registration.")

    # ---------------------------------------------------------------- Stage 1 -----------
    print("\n" + "=" * 104)
    print("STAGE 1 — COMPOSITION CORRECTION, THEN FIRST-EVER OUT-OF-SAMPLE SPLIT")
    print("=" * 104)
    disc = d[d["date"] <= DISC_END]
    oos = d[(d["date"] > DISC_END) & (d["date"] <= OOS_END)]
    lock = d[d["date"] > OOS_END]
    for nm, x in (("DISCOVERY", disc), ("OOS", oos), ("LOCKBOX", lock)):
        print(f"  {nm:<10} {x['date'].min().date()} .. {x['date'].max().date()}  "
              f"{x['date'].nunique():>4} weeks")

    print("\n" + "-" * 104)
    print(f"{'ID':<11}{'cluster':<18}{'arch t':>8}{'full t':>9}{'full t*':>9}"
          f"{'DISC t*':>9}{'OOS t*':>9}{'LOCK t*':>9}   verdict")
    print(f"{'':<11}{'':<18}{'':>8}{'(pooled)':>9}{'(corr)':>9}"
          f"{'(corr)':>9}{'(corr)':>9}{'(corr)':>9}")
    print("-" * 104)

    rows = []
    for eid, kind, spec, t_arch, cluster, mech in CLUSTER:
        if eid == "DS-F2-03" and matches_a04:
            rows.append({"id": eid, "cluster": cluster, "mechanism": mech,
                         "archived_t": t_arch, "turnover": tn,
                         "verdict": "RETIRED (cost, pre-stage)"})
            print(f"{eid:<11}{cluster:<18}{t_arch:>+8.2f}{'--':>9}{'--':>9}{'--':>9}"
                  f"{'--':>9}{'--':>9}   RETIRED (cost)")
            continue
        out = {}
        for nm, frame in (("full", d), ("disc", disc), ("oos", oos), ("lock", lock)):
            sub_, sig_ = slice_for(frame, kind, spec)
            p, c = ic_pair(sub_, sig_, f"{eid} {nm}", min_pairs=15 if kind != "signal" else 20)
            out[nm] = {"pooled": p.to_dict() if p else None,
                       "corrected": c.to_dict() if c else None}
        t_o = out["oos"]["corrected"]["t"] if out["oos"]["corrected"] else None
        ic_d = out["disc"]["corrected"]["estimate"] if out["disc"]["corrected"] else None
        ic_o = out["oos"]["corrected"]["estimate"] if out["oos"]["corrected"] else None
        flip = ic_d is not None and ic_o is not None and np.sign(ic_d) != np.sign(ic_o)
        if t_o is None:
            v = "NOT TESTABLE"
        elif flip:
            v = "KILL (sign flip)"
        elif abs(t_o) < 2.0:
            v = "KILL (OOS |t|<2)"
        else:
            v = "SURVIVES stage 1"
        comp_share = None
        if out["full"]["pooled"] and out["full"]["corrected"]:
            pe = out["full"]["pooled"]["estimate"]
            comp_share = (pe - out["full"]["corrected"]["estimate"]) / pe if pe else None
        rows.append({"id": eid, "cluster": cluster, "mechanism": mech,
                     "archived_t": t_arch, "windows": out, "sign_flip": bool(flip),
                     "composition_share": comp_share, "verdict": v})
        g = lambda k: (f"{out[k]['corrected']['t']:+.2f}" if out[k]["corrected"] else "  n/a")  # noqa
        fp = f"{out['full']['pooled']['t']:+.2f}" if out["full"]["pooled"] else "n/a"
        print(f"{eid:<11}{cluster:<18}{t_arch:>+8.2f}{fp:>9}{g('full'):>9}"
              f"{g('disc'):>9}{g('oos'):>9}{g('lock'):>9}   {v}")

    print("\n--- composition artifact per signal (pooled vs corrected, full window) ---")
    for r in rows:
        if r.get("composition_share") is not None:
            print(f"    {r['id']:<11} {r['composition_share']:+.0%} of the pooled IC is "
                  f"between-group composition")

    surv = [r for r in rows if r["verdict"] == "SURVIVES stage 1"]
    tested = [r for r in rows if "windows" in r]
    pv = [r["windows"]["oos"]["corrected"]["p"] for r in tested]
    by = benjamini_yekutieli(pv, q=0.05)
    print(f"\n--- multiplicity: BY q=0.05 across the {len(tested)} tested items (OOS) ---")
    for r, p, ok in zip(tested, pv, by):
        r["by_pass_oos"] = bool(ok)
        print(f"    {r['id']:<11} OOS p={p:.4f}  BY-clean={bool(ok)}")

    print("\n" + "=" * 104)
    print(f"RESULT: {len(surv)}/{len(CLUSTER)} survive Stage 1 "
          f"({sum(by)}/{len(tested)} BY-clean); 1 retired on cost before Stage 1")
    print("=" * 104)
    for r in surv:
        print(f"  SURVIVOR  {r['id']:<11} {r['mechanism']:<38} "
              f"OOS t*={r['windows']['oos']['corrected']['t']:+.2f}  "
              f"BY-clean={r.get('by_pass_oos')}")
    if not surv:
        print("  none")

    payload = {"experiment": "T1-09",
               "windows": {"discovery": ["2005-01-07", str(DISC_END.date())],
                           "oos": ["2018-01-05", str(OOS_END.date())],
                           "lockbox": ["2025-07-11", "2026-06-26"]},
               "dropped_duplicates": DROPPED,
               "ds_f2_03_cost_prestage": {"turnover": tn, "a04_reference_pct": a04_annual,
                                          "control_mom_turnover": tn_mom,
                                          "matches_a04": bool(matches_a04)},
               "results": rows, "n_survivors": len(surv)}
    (OUT / "t1_09_data.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n-> {OUT/'t1_09_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
