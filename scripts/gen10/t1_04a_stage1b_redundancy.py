#!/usr/bin/env python3
"""T1-04a Stage 1b — are the three Stage-1 survivors three signals or one?

All three are built from `delivery_pct_4w_avg`:
    DS-U-02   delivery_pct_4w_avg                      (= G2-E03b, already promoted)
    DS-F5-01  delivery_pct_4w_avg - sector mean
    DS-F1-05  z(delivery_pct_4w_avg) - z(ret_20d)

Before spending Stages 2-4 on three candidates, establish how many distinct ones there are.
The operative question for promotion is not "is each significant" but "does each add
anything to the one already in the book". Gen-5 F01 is the precedent: the momentum
composite's four members were individually significant and jointly redundant (Shapley
19-31% each, leave-one-out ~0).

Two tests, both on the OOS window that Stage 1 used:
  1. pairwise per-date rank correlation of the signals themselves;
  2. incremental IC — orthogonalise each candidate against DS-U-02 cross-sectionally,
     per date, and re-test. A candidate that is genuinely new keeps its t.
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

sys.path.insert(0, str(ROOT / "scripts/gen10"))
from t1_04a_ds_delivery_stage1 import load, DISC_END, OOS_END  # noqa: E402

OUT = ROOT / "results/gen10/T1-04a"
SEED = 20260731
SURVIVORS = {"DS-U-02": "delivery_pct_4w_avg",
             "DS-F5-01": "rel_deliv_sector",
             "DS-F1-05": "dv_deliv_price"}
BASE_ID = "DS-U-02"


def ic_of(d, col, label, tgt="ret"):
    s = d[["date", col, tgt]].dropna()
    ic = per_date_ic(s, "date", col, tgt, min_pairs=20)
    return nw_mean_test(ic.to_numpy(), overlap=1, label=label, n_boot=3000, seed=SEED)


def orthogonalise(d: pd.DataFrame, col: str, against: str) -> pd.Series:
    """Per-date cross-sectional residual of `col` on `against` (rank space, so the result
    is invariant to monotone rescaling of either — matching the Spearman IC we test with)."""
    def _resid(g):
        x = g[against].rank()
        y = g[col].rank()
        if len(g) < 20 or x.nunique() < 3:
            return pd.Series(np.nan, index=g.index)
        x = (x - x.mean())
        b = float((x * (y - y.mean())).sum() / max((x * x).sum(), 1e-12))
        return (y - y.mean()) - b * x
    return d.groupby("date", group_keys=False).apply(_resid)


def main() -> int:
    print("=" * 96)
    print("T1-04a STAGE 1b — REDUNDANCY AMONG THE THREE STAGE-1 SURVIVORS")
    print("=" * 96)
    d = load()
    oos = d[(d["date"] > DISC_END) & (d["date"] <= OOS_END)].copy()
    full = d[d["delivery_pct"].notna()].copy()

    # ---- 1. pairwise signal correlation --------------------------------------------------
    print("\n--- 1. pairwise per-date Spearman between the survivors (OOS window) ---")
    ids = list(SURVIVORS)
    corr = {}
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            ca, cb = SURVIVORS[a], SURVIVORS[b]
            s = oos[["date", ca, cb]].dropna()
            r = s.groupby("date").apply(
                lambda g: g[ca].corr(g[cb], method="spearman") if len(g) > 20 else np.nan,
                include_groups=False).dropna()
            corr[f"{a}~{b}"] = float(r.mean())
            print(f"    {a:<10} ~ {b:<10}  mean per-date rho = {r.mean():+.4f}")

    # ---- 2. incremental IC over the already-promoted signal -------------------------------
    print(f"\n--- 2. incremental IC after orthogonalising against {BASE_ID} "
          f"({SURVIVORS[BASE_ID]}) ---")
    print("    Question: does the candidate still predict once the deployed signal's")
    print("    cross-sectional ranking is removed?\n")
    base = ic_of(oos, SURVIVORS[BASE_ID], BASE_ID)
    print(f"    {BASE_ID:<10} (the incumbent)            IC={base.estimate:+.4f}  "
          f"t={base.t:+.2f}")
    rows = []
    for eid, col in SURVIVORS.items():
        if eid == BASE_ID:
            continue
        raw = ic_of(oos, col, eid)
        oos2 = oos.copy()
        oos2["_res"] = orthogonalise(oos2, col, SURVIVORS[BASE_ID])
        res = ic_of(oos2, "_res", f"{eid}|{BASE_ID}")
        keep = abs(res.t) / abs(raw.t) if raw.t else np.nan
        verdict = ("DISTINCT" if abs(res.t) >= 2.0 else "REDUNDANT with " + BASE_ID)
        rows.append({"id": eid, "col": col, "raw_ic": float(raw.estimate),
                     "raw_t": float(raw.t), "resid_ic": float(res.estimate),
                     "resid_t": float(res.t), "t_retained": float(keep),
                     "verdict": verdict})
        print(f"    {eid:<10} raw t={raw.t:+.2f}  ->  residual t={res.t:+.2f}   "
              f"({keep:.0%} of t retained)   {verdict}")

    # ---- 3. the reverse direction: does the incumbent survive the challenger? -------------
    print(f"\n--- 3. reverse check — is {BASE_ID} itself redundant to the strongest "
          f"challenger? ---")
    strongest = max(rows, key=lambda r: abs(r["raw_t"]))["id"]
    oos3 = oos.copy()
    oos3["_res"] = orthogonalise(oos3, SURVIVORS[BASE_ID], SURVIVORS[strongest])
    rev = ic_of(oos3, "_res", f"{BASE_ID}|{strongest}")
    print(f"    {BASE_ID} raw t={base.t:+.2f}  ->  residual t={rev.t:+.2f} after removing "
          f"{strongest}")
    if abs(rev.t) < 2.0 <= abs(rows[[r['id'] for r in rows].index(strongest)]["resid_t"]):
        print(f"    -> {strongest} SUBSUMES {BASE_ID}: the sector-relative form is the")
        print(f"       better carrier of the same information.")
    elif abs(rev.t) >= 2.0:
        print(f"    -> both survive mutual orthogonalisation: genuinely two dimensions.")
    else:
        print(f"    -> neither survives the other cleanly: one underlying signal.")

    # ---- 4. full-window replication of the redundancy call --------------------------------
    print("\n--- 4. same test on the full delivery window (339w), as a stability check ---")
    for eid, col in SURVIVORS.items():
        if eid == BASE_ID:
            continue
        f2 = full.copy()
        f2["_res"] = orthogonalise(f2, col, SURVIVORS[BASE_ID])
        r = ic_of(f2, "_res", f"{eid}|{BASE_ID} full")
        print(f"    {eid:<10} residual t (full window) = {r.t:+.2f}")

    payload = {"experiment": "T1-04a-stage1b", "pairwise_signal_corr": corr,
               "incremental": rows, "incumbent": {"id": BASE_ID, "t": float(base.t)},
               "reverse_check": {"challenger": strongest, "incumbent_residual_t": float(rev.t)}}
    (OUT / "t1_04a_stage1b_data.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n-> {OUT/'t1_04a_stage1b_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
