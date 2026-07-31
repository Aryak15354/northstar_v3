#!/usr/bin/env python3
"""T1-04a Stage 1 — DS delivery cluster: the first out-of-sample split it has ever had.

Every one of the 28 deep-search items was evaluated on the FULL sample. Their manifests
carry `"lockbox_used": false` and `deepsearch.fast_ic` runs over all dates. The single
case where a genuine split was later applied — DS-F3-04 — collapsed from t=-4.4 to
t=-0.06. This runs that split for the delivery cluster.

Signal specs are lifted verbatim from scripts/gen23/deepsearch.py so the only thing that
changes is the evaluation window.

Pre-registered in GEN10_REMEDIATION_CHARTER.md s4/T1-04a:
  Stage 1 kill = OOS |t| < 2 OR sign flip vs discovery.
  Multiplicity = BY across the deduped cluster.

Windows (fixed before any result was read; delivery data begins 2020-01-03):
  DISCOVERY 2020-01-03 .. 2023-12-31
  OOS       2024-01-01 .. 2025-07-10
  LOCKBOX   2025-07-11 .. 2026-06-26     (never touched by any prior experiment)
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
    nw_mean_test, per_date_ic, benjamini_yekutieli,
)

OUT = ROOT / "results/gen10/T1-04a"
OUT.mkdir(parents=True, exist_ok=True)
BASE = ROOT / "tmp/kaggle_uploads/panel_enriched"
SEED = 20260731

DISC_END = pd.Timestamp("2023-12-31")
OOS_END = pd.Timestamp("2025-07-10")

# deduped delivery cluster. DS-U-04 is dropped: identical spec to DS-F5-01 (verified in
# T0-02, IC identical to 7dp). DS-U-02 is the already-promoted G2-E03b, kept as a control.
CLUSTER = [
    ("DS-F1-01", "signal",  "ix_deliv_mom",        -1.88, "delivery x momentum"),
    ("DS-F1-04", "signal",  "ix_deliv_breakout",   -2.95, "delivery confirms breakout"),
    ("DS-F1-05", "signal",  "dv_deliv_price",      +4.21, "delivery-price divergence"),
    ("DS-F1-06", "signal",  "pa_deliv_jump",       +3.46, "delivery jump above own trend"),
    ("DS-F3-01", "failure", "delivery_pct_4w_avg", +2.34, "delivery picks momentum winners"),
    ("DS-F3-02", "failure", "delivery_pct_z52",    +3.02, "delivery-vs-history picks winners"),
    ("DS-F5-01", "signal",  "rel_deliv_sector",    +4.93, "sector-relative delivery"),
    ("DS-U-02",  "signal",  "delivery_pct_4w_avg", +4.06, "unconditional delivery (=G2-E03b)"),
]
DROPPED = [("DS-U-04", "DS-F5-01", "identical spec `rel_deliv_sector`; verified in T0-02")]


def load() -> pd.DataFrame:
    cols = ["date", "ticker", "target_weekly_return", "mom_60d_cs_z", "delivery_pct",
            "delivery_pct_4w_avg", "delivery_pct_z52", "ret_20d", "fut_oi"]
    f = pd.read_parquet(BASE / "northstar_features_enriched.parquet", columns=cols)
    md = pd.read_parquet(BASE / "northstar_metadata.parquet",
                         columns=["date", "ticker", "sector"])
    for d in (f, md):
        d["date"] = pd.to_datetime(d["date"]).dt.normalize()
        d["ticker"] = d["ticker"].astype(str)
    d = f.merge(md, on=["date", "ticker"], how="left")
    d["ret"] = d.groupby("date")["target_weekly_return"].transform(
        lambda s: s.clip(s.quantile(.01), s.quantile(.99)))

    def zc(col):
        g = d.groupby("date")[col]
        return (d[col] - g.transform("mean")) / g.transform("std").replace(0, np.nan)

    d["z_delivery_pct_4w_avg"] = zc("delivery_pct_4w_avg")
    d["z_delivery_pct"] = zc("delivery_pct")
    d["z_ret_20d"] = zc("ret_20d")
    # verbatim from deepsearch.py
    d["ix_deliv_mom"] = d["z_delivery_pct_4w_avg"] * d["mom_60d_cs_z"]
    d["ix_deliv_breakout"] = d["z_delivery_pct_4w_avg"] * d["z_ret_20d"]
    d["dv_deliv_price"] = d["z_delivery_pct_4w_avg"] - d["z_ret_20d"]
    d["pa_deliv_jump"] = d["z_delivery_pct"] - d["z_delivery_pct_4w_avg"]
    sm = d.groupby(["date", "sector"])["delivery_pct_4w_avg"].transform("mean")
    d["rel_deliv_sector"] = d["delivery_pct_4w_avg"] - sm
    return d


def eval_signal(d: pd.DataFrame, kind: str, spec: str, label: str) -> dict:
    """`signal`  = plain cross-sectional IC.
       `failure` = IC within the top-quintile momentum longs (deepsearch.failure_ic)."""
    if kind == "failure":
        q = d.groupby("date")["mom_60d_cs_z"].transform(lambda s: s.quantile(0.8))
        sub = d[d["mom_60d_cs_z"] >= q]
        min_pairs = 15
    else:
        sub = d
        min_pairs = 20
    s = sub[["date", spec, "ret"]].dropna()
    if s["date"].nunique() < 20:
        return {"ic": None, "t": None, "n": int(s["date"].nunique()), "label": label}
    ic = per_date_ic(s, "date", spec, "ret", min_pairs=min_pairs)
    r = nw_mean_test(ic.to_numpy(), overlap=1, label=label, n_boot=3000, seed=SEED)
    return {"ic": float(r.estimate), "t": float(r.t), "p": float(r.p), "n": int(r.n),
            "boot_lo": r.boot_ci_lo, "boot_hi": r.boot_ci_hi, "label": label}


def main() -> int:
    print("=" * 100)
    print("T1-04a STAGE 1 — DS DELIVERY CLUSTER: FIRST-EVER OUT-OF-SAMPLE SPLIT")
    print("=" * 100)
    d = load()
    dd = d[d["delivery_pct"].notna()]
    print(f"delivery coverage: {dd['date'].min().date()} -> {dd['date'].max().date()}  "
          f"({dd['date'].nunique()} weeks)")
    print(f"deduped cluster: {len(CLUSTER)} items "
          f"(dropped {len(DROPPED)}: {DROPPED[0][0]} == {DROPPED[0][1]})\n")

    disc = d[d["date"] <= DISC_END]
    oos = d[(d["date"] > DISC_END) & (d["date"] <= OOS_END)]
    lock = d[d["date"] > OOS_END]
    for nm, x in (("DISCOVERY", disc), ("OOS", oos), ("LOCKBOX", lock)):
        xx = x[x["delivery_pct"].notna()]
        print(f"  {nm:<10} {xx['date'].min().date()} .. {xx['date'].max().date()}  "
              f"{xx['date'].nunique():>3} weeks")

    print("\n" + "-" * 100)
    print(f"{'ID':<11}{'spec':<22}{'arch t':>8}{'FULL t':>9}"
          f"{'DISC t':>9}{'OOS t':>9}{'LOCK t':>9}   verdict")
    print("-" * 100)

    rows = []
    for eid, kind, spec, t_arch, mech in CLUSTER:
        full = eval_signal(d, kind, spec, f"{eid} full")
        de = eval_signal(disc, kind, spec, f"{eid} disc")
        oo = eval_signal(oos, kind, spec, f"{eid} oos")
        lo = eval_signal(lock, kind, spec, f"{eid} lock")

        t_o = oo["t"]
        sign_flip = (de["ic"] is not None and oo["ic"] is not None
                     and np.sign(de["ic"]) != np.sign(oo["ic"]))
        if t_o is None:
            verdict = "NOT TESTABLE"
        elif sign_flip:
            verdict = "KILL (sign flip)"
        elif abs(t_o) < 2.0:
            verdict = "KILL (OOS |t|<2)"
        else:
            verdict = "SURVIVES stage 1"
        rows.append({"id": eid, "kind": kind, "spec": spec, "mechanism": mech,
                     "archived_t": t_arch, "full": full, "discovery": de, "oos": oo,
                     "lockbox": lo, "sign_flip": bool(sign_flip), "verdict": verdict})
        f_ = lambda v: f"{v:+.2f}" if v is not None else "  n/a"   # noqa: E731
        print(f"{eid:<11}{spec:<22}{t_arch:>+8.2f}{f_(full['t']):>9}"
              f"{f_(de['t']):>9}{f_(oo['t']):>9}{f_(lo['t']):>9}   {verdict}")

    # multiplicity across the deduped cluster, on the OOS stage
    surv = [r for r in rows if r["verdict"] == "SURVIVES stage 1"]
    pv = [r["oos"]["p"] if r["oos"].get("p") is not None else 1.0 for r in rows]
    by = benjamini_yekutieli(pv, q=0.05)
    print("\n" + "-" * 100)
    print(f"MULTIPLICITY — BY q=0.05 across the deduped cluster (m={len(rows)}), OOS stage")
    print("-" * 100)
    for r, ok in zip(rows, by):
        r["by_pass_oos"] = bool(ok)
        print(f"  {r['id']:<11} OOS p={pv[rows.index(r)]:.4f}   BY-clean={bool(ok)}")

    print("\n" + "=" * 100)
    print(f"STAGE 1 RESULT: {len(surv)}/{len(rows)} survive the sign+|t| rule; "
          f"{sum(by)}/{len(rows)} are BY-clean on OOS")
    print("=" * 100)
    for r in rows:
        if r["verdict"] == "SURVIVES stage 1":
            print(f"  SURVIVOR  {r['id']:<11} {r['mechanism']:<36} "
                  f"OOS t={r['oos']['t']:+.2f}  BY-clean={r['by_pass_oos']}")
    if not surv:
        print("  none")

    payload = {"experiment": "T1-04a-stage1",
               "windows": {"discovery": ["2020-01-03", str(DISC_END.date())],
                           "oos": [str((DISC_END + pd.Timedelta(days=1)).date()),
                                   str(OOS_END.date())],
                           "lockbox": [str((OOS_END + pd.Timedelta(days=1)).date()),
                                       "2026-06-26"]},
               "dropped_duplicates": DROPPED, "results": rows,
               "n_survivors": len(surv)}
    (OUT / "t1_04a_stage1_data.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n-> {OUT/'t1_04a_stage1_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
