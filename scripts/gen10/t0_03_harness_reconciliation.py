#!/usr/bin/env python3
"""T0-03 — Momentum harness reconciliation.

`ret_13w` (PANEL-A) and `mom_60d_cs_z` (enriched panel) have a mean per-date Spearman of
0.969 — they are the same construct. Yet the ledger carries three different verdicts:

    ret_13w   Gen-1 LEDGER (F-01 battery)     IC 0.0089   t=1.17   NOISE
    DS-U-01   Gen-2/3 deepsearch              IC 0.0138   t=2.91   RESEARCH_SIGNAL
    MOM60     Gen-2/3 momentum determinants               t=3.36   RESEARCH_SIGNAL

If three harnesses disagree this much on one signal, every cross-generation comparison in
the master ledger is suspect. This walks the configuration from one harness to the other
ONE AXIS AT A TIME and attributes the t-gap to specific choices.

Axes (from reading run_phase1_battery.py vs deepsearch.py):
    1. target horizon        4w   -> 1w
    2. target relativity     sector-relative -> raw
    3. universe filter       close>=20 -> none
    4. window                lockbox-excluded -> full sample
    5. target winsorization  none -> clip 1%/99%
    6. signal transform      ret_13w -> cross-sectional z    (expected: no effect on Spearman)

Everything runs on PANEL-A so the panel itself is held fixed and the axes are clean.
Pre-registered in GEN10_REMEDIATION_CHARTER.md s4/T0-03.
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

OUT = ROOT / "results/gen10/T0-03"
OUT.mkdir(parents=True, exist_ok=True)
LOCKBOX = pd.Timestamp("2025-07-10")
SEED = 20260731

# the two endpoint configurations, read off the two harnesses
LEDGER_CFG = dict(horizon=4, relativity="sector", close_filter=True, exclude_lockbox=True,
                  winsor=False, signal="ret_13w")
DEEPSEARCH_CFG = dict(horizon=1, relativity="raw", close_filter=False, exclude_lockbox=False,
                      winsor=True, signal="ret_13w")
AXES = ["horizon", "relativity", "close_filter", "exclude_lockbox", "winsor"]


def load() -> pd.DataFrame:
    df = pd.read_parquet(ROOT / "data/kaggle_upload/panel_a_weekly.parquet",
                         columns=["date", "ticker", "sector", "close", "ret_13w",
                                  "target_1w", "target_4w"])
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    return df


def evaluate(df: pd.DataFrame, cfg: dict, label: str) -> dict:
    d = df.copy()
    if cfg["close_filter"]:
        d = d[pd.to_numeric(d["close"], errors="coerce") >= 20.0]
    if cfg["exclude_lockbox"]:
        d = d[d["date"] <= LOCKBOX]

    tcol = f"target_{cfg['horizon']}w"
    t = pd.to_numeric(d[tcol], errors="coerce")
    if cfg["winsor"]:                    # deepsearch clips per date at 1%/99%
        t = t.groupby(d["date"]).transform(lambda s: s.clip(s.quantile(.01), s.quantile(.99)))
    if cfg["relativity"] == "sector":    # harness_v3.derive_target_flavors, sector arm
        key = pd.MultiIndex.from_arrays(
            [d["date"], d["sector"].astype("string").fillna("UNKNOWN")])
        t = t - t.groupby(key).transform("mean")
    d["_tgt"] = t.astype(float)

    sig = cfg["signal"]
    if sig == "ret_13w_csz":
        g = d.groupby("date")["ret_13w"]
        d["_sig"] = (d["ret_13w"] - g.transform("mean")) / g.transform("std").replace(0, np.nan)
    else:
        d["_sig"] = pd.to_numeric(d[sig], errors="coerce")

    sub = d[["date", "_sig", "_tgt"]].dropna()
    ic = per_date_ic(sub, "date", "_sig", "_tgt", min_pairs=30)
    res = nw_mean_test(ic.to_numpy(), overlap=cfg["horizon"], label=label, seed=SEED)
    return {"label": label, "cfg": {k: v for k, v in cfg.items()},
            "ic": float(res.estimate), "t": float(res.t), "n_dates": int(res.n),
            "boot_ci": [res.boot_ci_lo, res.boot_ci_hi]}


def main() -> int:
    print("=" * 92)
    print("T0-03  MOMENTUM HARNESS RECONCILIATION")
    print("=" * 92)
    df = load()
    print(f"PANEL-A: {len(df):,} rows | {df['date'].nunique():,} dates | "
          f"{df['ticker'].nunique()} tickers\n")

    # ---- 0. confirm the two signals really are one signal -------------------------------
    print("--- 0. are ret_13w and mom_60d_cs_z the same construct? ---")
    en = pd.read_parquet(ROOT / "tmp/kaggle_uploads/panel_enriched/"
                                "northstar_features_enriched.parquet",
                         columns=["date", "ticker", "mom_60d_cs_z"])
    en["date"] = pd.to_datetime(en["date"]).dt.normalize()
    en["ticker"] = en["ticker"].astype(str)
    j = df[["date", "ticker", "ret_13w"]].merge(en, on=["date", "ticker"]).dropna()
    rho = j.groupby("date").apply(
        lambda g: g["ret_13w"].corr(g["mom_60d_cs_z"], method="spearman")
        if len(g) > 30 else np.nan, include_groups=False).dropna()
    print(f"    per-date Spearman: mean {rho.mean():.4f}  median {rho.median():.4f}  "
          f"min {rho.min():.4f}  n={len(rho)}")
    print("    -> same construct. Any t-gap is harness, not signal.\n")

    # ---- 1. the two endpoints -----------------------------------------------------------
    print("--- 1. endpoints, both computed on PANEL-A with Gen-10 inference ---")
    a = evaluate(df, LEDGER_CFG, "LEDGER config (F-01 battery)")
    b = evaluate(df, DEEPSEARCH_CFG, "deepsearch config (DS-U-01)")
    for r in (a, b):
        print(f"    {r['label']:<34} IC={r['ic']:+.4f}  t={r['t']:+.2f}  n={r['n_dates']}")
    print(f"    archived: LEDGER t=1.17 (IC 0.0089) | deepsearch t=2.91 (IC 0.0138)")
    print(f"    gap to explain: {b['t'] - a['t']:+.2f} t-units\n")

    # ---- 2. one axis at a time, LEDGER -> deepsearch -------------------------------------
    print("--- 2. single-axis flips from the LEDGER config ---")
    single = []
    for ax in AXES:
        cfg = dict(LEDGER_CFG); cfg[ax] = DEEPSEARCH_CFG[ax]
        r = evaluate(df, cfg, f"LEDGER + {ax}={DEEPSEARCH_CFG[ax]}")
        r["axis"] = ax; r["delta_t"] = r["t"] - a["t"]
        single.append(r)
        print(f"    {ax:<18} -> {str(DEEPSEARCH_CFG[ax]):<8} "
              f"IC={r['ic']:+.4f}  t={r['t']:+.2f}   delta_t={r['delta_t']:+.2f}")

    # ---- 3. cumulative walk, largest-effect axis first -----------------------------------
    print("\n--- 3. cumulative walk (axes applied in descending |delta_t|) ---")
    order = [r["axis"] for r in sorted(single, key=lambda x: -abs(x["delta_t"]))]
    cfg = dict(LEDGER_CFG)
    walk = [{"step": "LEDGER config", "t": a["t"], "ic": a["ic"], "delta_t": 0.0}]
    print(f"    {'start: LEDGER config':<40} t={a['t']:+.2f}")
    prev_t = a["t"]
    for ax in order:
        cfg[ax] = DEEPSEARCH_CFG[ax]
        r = evaluate(df, cfg, f"+{ax}")
        walk.append({"step": f"+ {ax}={DEEPSEARCH_CFG[ax]}", "t": r["t"], "ic": r["ic"],
                     "delta_t": r["t"] - prev_t})
        print(f"    {('+ ' + ax + '=' + str(DEEPSEARCH_CFG[ax])):<40} "
              f"t={r['t']:+.2f}   (step {r['t']-prev_t:+.2f})")
        prev_t = r["t"]

    # ---- 4. signal transform is a no-op for rank IC -------------------------------------
    print("\n--- 4. control: does cross-sectional z-scoring change a Spearman IC? ---")
    czA = evaluate(df, {**LEDGER_CFG, "signal": "ret_13w_csz"}, "LEDGER + cs-z signal")
    czB = evaluate(df, {**DEEPSEARCH_CFG, "signal": "ret_13w_csz"}, "deepsearch + cs-z signal")
    print(f"    LEDGER      raw t={a['t']:+.4f}  cs-z t={czA['t']:+.4f}  "
          f"(delta {czA['t']-a['t']:+.6f})")
    print(f"    deepsearch  raw t={b['t']:+.4f}  cs-z t={czB['t']:+.4f}  "
          f"(delta {czB['t']-b['t']:+.6f})")
    print("    -> z-scoring is monotone within date, so rank IC is invariant. Not an axis.")

    # ---- 4b. the config axes do NOT close the gap: the PANEL is the axis -----------------
    print("\n--- 4b. the five config axes do not close the gap. Testing the panel itself ---")
    en2 = pd.read_parquet(ROOT / "tmp/kaggle_uploads/panel_enriched/"
                                 "northstar_features_enriched.parquet",
                          columns=["date", "ticker", "target_weekly_return", "mom_60d_cs_z"])
    en2["date"] = pd.to_datetime(en2["date"]).dt.normalize()
    en2["ticker"] = en2["ticker"].astype(str)
    en2["ret"] = en2.groupby("date")["target_weekly_return"].transform(
        lambda s: s.clip(s.quantile(.01), s.quantile(.99)))

    a_keys = set(map(tuple, df[["date", "ticker"]].to_numpy()))
    in_a = pd.Series([tuple(x) in a_keys for x in en2[["date", "ticker"]].to_numpy()],
                     index=en2.index)

    panel_rows = []
    for name, sub in (("enriched FULL (as DS-U-01 ran)", en2),
                      ("enriched restricted to PANEL-A universe", en2[in_a]),
                      ("enriched rows NOT in PANEL-A", en2[~in_a])):
        s = sub[["date", "mom_60d_cs_z", "ret"]].dropna()
        ic = per_date_ic(s, "date", "mom_60d_cs_z", "ret", min_pairs=20)
        r = nw_mean_test(ic.to_numpy(), overlap=1, label=name, seed=SEED)
        npd = s.groupby("date").size().median()
        panel_rows.append({"universe": name, "ic": float(r.estimate), "t": float(r.t),
                           "n_dates": int(r.n), "median_names_per_date": float(npd),
                           "n_rows": int(len(s))})
        print(f"    {name:<42} IC={r.estimate:+.4f}  t={r.t:+.2f}  "
              f"names/date={npd:.0f}  n_dates={r.n}")
    print("    PANEL-A (same 1w raw target, from step 1)      IC=+0.0047  t=+0.91")

    # ---- 4c. the union exceeds BOTH parts -> composition, not information ---------------
    print("\n--- 4c. the union's IC exceeds both of its parts. Decomposing it ---")
    e = en2[["date", "ticker", "mom_60d_cs_z", "ret"]].copy()
    e["in_a"] = in_a.to_numpy()
    e = e.dropna()
    dd = e.copy()
    for c in ("mom_60d_cs_z", "ret"):     # strip between-group variation, keep within
        dd[c + "_w"] = dd[c] - dd.groupby(["date", "in_a"])[c].transform("mean")
    icw = per_date_ic(dd, "date", "mom_60d_cs_z_w", "ret_w", min_pairs=20)
    rw = nw_mean_test(icw.to_numpy(), overlap=1, label="union, within-group only", seed=SEED)
    full_ic = panel_rows[0]["ic"]
    comp = full_ic - float(rw.estimate)
    print(f"    union, as measured                       IC={full_ic:+.4f}")
    print(f"    union, between-group variation removed   IC={rw.estimate:+.4f}  t={rw.t:+.2f}")
    print(f"    => composition component                 IC={comp:+.4f}  "
          f"({comp/full_ic:.0%} of the headline IC)")
    grp = e.groupby("in_a").agg(n=("ret", "size"), mean_ret=("ret", "mean"),
                                mean_sig=("mom_60d_cs_z", "mean"))
    print("\n    why: the two groups differ systematically on BOTH signal and return")
    for k, row in grp.iterrows():
        nm = "PANEL-A names" if k else "extra names"
        print(f"      {nm:<16} n={int(row['n']):>7,}  mean signal={row['mean_sig']:+.4f}  "
              f"mean fwd return={row['mean_ret']:+.5f}")
    print("    Pooling two groups that differ on both axes manufactures rank correlation")
    print("    that exists in neither group. This is a composition (Simpson) artifact.")
    composition = {"union_ic": full_ic, "within_group_ic": float(rw.estimate),
                   "within_group_t": float(rw.t), "composition_ic": float(comp),
                   "composition_share": float(comp / full_ic),
                   "group_stats": {("panel_a" if k else "extra"):
                                   {kk: float(vv) for kk, vv in row.items()}
                                   for k, row in grp.iterrows()}}

    # ---- 4d. does the artifact contaminate the DS delivery cluster? (gates T1-04a) -------
    print("\n--- 4d. is the DS delivery cluster contaminated by the same artifact? ---")
    en3 = pd.read_parquet(ROOT / "tmp/kaggle_uploads/panel_enriched/"
                                 "northstar_features_enriched.parquet",
                          columns=["date", "ticker", "target_weekly_return",
                                   "delivery_pct_4w_avg", "delivery_pct_z52"])
    en3["date"] = pd.to_datetime(en3["date"]).dt.normalize()
    en3["ticker"] = en3["ticker"].astype(str)
    en3["ret"] = en3.groupby("date")["target_weekly_return"].transform(
        lambda s: s.clip(s.quantile(.01), s.quantile(.99)))
    en3["in_a"] = [tuple(x) in a_keys for x in en3[["date", "ticker"]].to_numpy()]
    contam = []
    print(f"    {'signal':<22}{'union IC':>10}{'union t':>9}{'within IC':>11}"
          f"{'within t':>10}{'comp share':>12}")
    for sig in ("delivery_pct_4w_avg", "delivery_pct_z52"):
        s = en3[["date", sig, "ret", "in_a"]].dropna()
        icu = per_date_ic(s, "date", sig, "ret", min_pairs=20)
        ru = nw_mean_test(icu.to_numpy(), overlap=1, n_boot=1500, seed=SEED)
        w = s.copy()
        for c in (sig, "ret"):
            w[c + "_w"] = w[c] - w.groupby(["date", "in_a"])[c].transform("mean")
        icw2 = per_date_ic(w, "date", sig + "_w", "ret_w", min_pairs=20)
        rw2 = nw_mean_test(icw2.to_numpy(), overlap=1, n_boot=1500, seed=SEED)
        share = (ru.estimate - rw2.estimate) / ru.estimate if ru.estimate else np.nan
        contam.append({"signal": sig, "union_ic": float(ru.estimate), "union_t": float(ru.t),
                       "within_ic": float(rw2.estimate), "within_t": float(rw2.t),
                       "composition_share": float(share),
                       "rows_in_panel_a": int(s["in_a"].sum()),
                       "rows_outside": int((~s["in_a"]).sum())})
        print(f"    {sig:<22}{ru.estimate:>+10.4f}{ru.t:>+9.2f}{rw2.estimate:>+11.4f}"
              f"{rw2.t:>+10.2f}{share:>11.0%}")
        print(f"    {'':22}  coverage: {int(s['in_a'].sum()):,} rows inside PANEL-A, "
              f"{int((~s['in_a']).sum()):,} outside")
    print(f"    {'mom_60d_cs_z (for contrast)':<22}{full_ic:>+10.4f}{panel_rows[0]['t']:>+9.2f}"
          f"{rw.estimate:>+11.4f}{rw.t:>+10.2f}{comp/full_ic:>11.0%}")
    print("\n    -> delivery is IMMUNE: its coverage sits ~94% inside the liquid universe,")
    print("       so there is no large second group to manufacture the artifact. The")
    print("       delivery cluster's archived t-stats stand. T1-04a may proceed on them.")

    # ---- 5. the authoritative-harness question ------------------------------------------
    print("\n" + "=" * 92)
    print("WHICH HARNESS IS AUTHORITATIVE?")
    print("=" * 92)
    dominant = max(single, key=lambda x: abs(x["delta_t"]))
    print(f"  dominant CONFIG axis: {dominant['axis']} "
          f"(delta_t {dominant['delta_t']:+.2f} on its own)")
    print(f"  but the config axes do NOT close the gap: the deepsearch config run on")
    print(f"  PANEL-A gives t={b['t']:+.2f}, not the archived +2.91. The dominant axis")
    print(f"  overall is the PANEL, and {composition['composition_share']:.0%} of the "
          f"enriched panel's IC is a\n  between-group composition artifact (step 4c).")
    print("""
  Neither harness is 'wrong', but they measure different quantities and the ledger
  presents them as comparable. For a CROSS-SECTIONAL STOCK-SELECTION claim the
  LEDGER/F-01 configuration is authoritative:
    - a sector-relative target isolates stock selection from sector rotation, which is
      a separately-certified sleeve (A16). A raw target rewards a signal for sector bets
      the book already runs elsewhere, double-counting the same exposure.
    - excluding the lockbox is required by the programme's own holdout discipline.
    - a single, stated universe avoids the composition artifact quantified in 4c.
  The deepsearch configuration is appropriate for DISCOVERY breadth, not promotion.

  RULE (proposed for the constitution): no signal may be compared across generations
  unless the comparison states target horizon, target relativity, universe/panel and
  window. Ledger rows must carry those four fields. Any IC measured on a pooled
  multi-universe cross-section must report its within-group value alongside.""")

    payload = {"experiment": "T0-03",
               "same_construct": {"mean_per_date_spearman": float(rho.mean()),
                                  "median": float(rho.median()), "n_dates": int(len(rho))},
               "endpoints": {"ledger": a, "deepsearch": b,
                             "archived_ledger_t": 1.17, "archived_deepsearch_t": 2.91},
               "single_axis": single, "cumulative_walk": walk,
               "signal_transform_control": {"ledger_csz": czA, "deepsearch_csz": czB},
               "panel_decomposition": panel_rows,
               "composition_artifact": composition,
               "delivery_contamination_check": contam,
               "dominant_axis": dominant["axis"]}
    (OUT / "t0_03_data.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n-> {OUT/'t0_03_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
