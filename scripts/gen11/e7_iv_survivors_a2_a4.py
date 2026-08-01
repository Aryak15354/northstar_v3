#!/usr/bin/env python3
"""E7 — the two IV-surface survivors through A2 (out-of-sample) and A4 (rediscovery).

E6 left two of seven declared features standing, both BY-clean at m=7 with bootstrap CIs
excluding zero:

    iv_atm   resid t = -3.18, IC = -0.0237   NEGATIVE: low implied vol -> higher returns
    pcr_oi   resid t = +3.76, IC = +0.0151   share-positive 56.4%

Both now face the two gates that have killed everything else in this programme.

A4 IS THE REAL TEST HERE, and each survivor has a specific, named suspect:

  iv_atm  is near-collinear with REALISED vol by construction, and "low vol predicts higher
          returns" is the low-volatility/BAB anomaly the panel already carries as vol_13w,
          vol_52w and beta_104w. Gen-1 tested it: A05 low-vol premium REJECT (regime-
          conditional), A06 low-beta CONDITIONAL (crash hedge only). If iv_atm dies once
          realised vol is removed, it is that anomaly wearing an options label.

  pcr_oi  G8-05 already found a PCR IC of +0.0093, "real but below the materiality bar" --
          at INDEX level. This is per-stock, so it is not the same test, but it is adjacent
          enough that the delivery and futures-OI controls must both be applied.

A2 windows fixed before running: DISC <= 2019-12-31, OOS -> 2025-07-11, LOCKBOX after.
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
from src.research.gen10.inference import nw_mean_test, per_date_ic  # noqa: E402
from e3_oi_candidates import resid  # noqa: E402
from e6_iv_surface_screen import build, DISC_END, LOCK  # noqa: E402

OUT = ROOT / "results/gen11/E7"
OUT.mkdir(parents=True, exist_ok=True)
SEED = 20260731
SURV = ["iv_atm", "pcr_oi"]


def ic_t(frame, col, min_pairs=30):
    s = frame[["date", col, "ret"]].dropna()
    if s["date"].nunique() < 50:
        return None
    ic = per_date_ic(s, "date", col, "ret", min_pairs=min_pairs)
    if len(ic) < 50:
        return None
    return nw_mean_test(ic.to_numpy(), overlap=1, n_boot=2500, seed=SEED)


def chain(frame, col, controls):
    """Sequentially residualise `col` against each control, per date, in rank space."""
    f = frame.copy()
    cur = col
    for i, ctl in enumerate(controls):
        f = f[f[cur].notna() & f[ctl].notna()]
        if len(f) < 500:
            return None, f
        f[f"_c{i}"] = resid(f, cur, ctl)
        cur = f"_c{i}"
    return cur, f


def main() -> int:
    print("=" * 100)
    print("E7 — IV SURVIVORS THROUGH A2 (out-of-sample) AND A4 (rediscovery)")
    print("=" * 100)
    d = build()

    # attach the rediscovery controls
    dl = pd.read_parquet(ROOT / "tmp/kaggle_uploads/panel_enriched/"
                                "northstar_features_enriched.parquet",
                         columns=["date", "ticker", "delivery_pct_z52", "fut_oi_z52",
                                  "fut_oi_chg_4w_pct"])
    dl["date"] = pd.to_datetime(dl["date"]).dt.normalize()
    dl["ticker"] = dl["ticker"].astype(str)
    d = d.merge(dl, on=["date", "ticker"], how="left")
    # beta_104w is not in e6.build()'s column list; pull it for the A4 low-vol control
    bt = pd.read_parquet(ROOT / "data/kaggle_upload/panel_a_weekly.parquet",
                         columns=["date", "ticker", "beta_104w"])
    bt["date"] = pd.to_datetime(bt["date"])
    d = d.merge(bt, on=["date", "ticker"], how="left")
    print(f"panel {len(d):,} stock-weeks | {d['date'].nunique()} weeks | "
          f"{d['ticker'].nunique()} names")
    print(f"corr(iv_atm, realised_vol_ann) = "
          f"{d[['iv_atm','realised_vol_ann']].corr().iloc[0,1]:.3f}   <- the A4 suspect\n")

    # ---------------- A2 ----------------
    disc = d[d["date"] <= DISC_END]
    oos = d[(d["date"] > DISC_END) & (d["date"] <= LOCK)]
    lk = d[d["date"] > LOCK]
    print("--- A2: out-of-sample split (momentum-orthogonalised) ---")
    for nm, x in (("DISCOVERY", disc), ("OOS", oos), ("LOCKBOX", lk)):
        print(f"  {nm:<10} {x['date'].nunique():>4} weeks")
    print(f"\n{'feature':<12}{'DISC t':>9}{'OOS t':>9}{'LOCK t':>9}   A2 verdict")
    rows = []
    for c in SURV:
        ts = {}
        for nm, x in (("disc", disc), ("oos", oos), ("lock", lk)):
            xx = x[x[c].notna()].copy()
            if len(xx) < 500:
                ts[nm] = None
                continue
            xx["_r"] = resid(xx, c, "mom_comp")
            ts[nm] = ic_t(xx, "_r")
        td = ts["disc"].t if ts["disc"] else np.nan
        to = ts["oos"].t if ts["oos"] else np.nan
        tl = ts["lock"].t if ts["lock"] else np.nan
        flip = (ts["disc"] and ts["oos"]
                and np.sign(ts["disc"].estimate) != np.sign(ts["oos"].estimate))
        v = ("KILL (sign flip)" if flip else
             "KILL (OOS |t|<2)" if not np.isfinite(to) or abs(to) < 2 else "SURVIVES A2")
        rows.append({"feature": c, "disc_t": float(td) if np.isfinite(td) else None,
                     "oos_t": float(to) if np.isfinite(to) else None,
                     "lock_t": float(tl) if np.isfinite(tl) else None,
                     "sign_flip": bool(flip), "a2": v})
        f = lambda v: f"{v:+.2f}" if np.isfinite(v) else "  n/a"  # noqa
        print(f"{c:<12}{f(td):>9}{f(to):>9}{f(tl):>9}   {v}")

    # ---------------- A4 ----------------
    print("\n--- A4: rediscovery — strip the named suspect, then re-test ---")
    CONTROLS = {
        "iv_atm": [("+realised vol", ["mom_comp", "realised_vol_ann"]),
                   ("+realised vol +vol_52w", ["mom_comp", "realised_vol_ann", "vol_52w"]),
                   ("+rv +vol_52w +beta", ["mom_comp", "realised_vol_ann", "vol_52w",
                                           "beta_104w"])],
        "pcr_oi": [("+delivery", ["mom_comp", "delivery_pct_z52"]),
                   ("+delivery +futOI", ["mom_comp", "delivery_pct_z52", "fut_oi_z52"]),
                   ("+deliv +futOI +rv", ["mom_comp", "delivery_pct_z52", "fut_oi_z52",
                                          "realised_vol_ann"])],
    }
    for r in rows:
        c = r["feature"]
        base = d[d[c].notna()].copy()
        base["_b"] = resid(base, c, "mom_comp")
        b0 = ic_t(base, "_b")
        print(f"\n  {c}   (momentum only): t = {b0.t:+.2f}, IC = {b0.estimate:+.4f}")
        r["a4"] = []
        for label, ctls in CONTROLS[c]:
            col, f = chain(base, c, ctls)
            if col is None:
                print(f"    {label:<26} not testable")
                continue
            rr = ic_t(f, col)
            if rr is None:
                print(f"    {label:<26} not testable")
                continue
            kept = abs(rr.t) / abs(b0.t) if b0.t else np.nan
            r["a4"].append({"controls": label, "t": float(rr.t),
                            "ic": float(rr.estimate), "n": int(rr.n),
                            "t_retained": float(kept)})
            print(f"    {label:<26} t = {rr.t:+.2f}   IC = {rr.estimate:+.4f}   "
                  f"({kept:.0%} of t retained, {rr.n} weeks)")

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    final = []
    for r in rows:
        worst = min((a["t"] for a in r.get("a4", [])), key=abs, default=np.nan)
        ok = (r["a2"] == "SURVIVES A2" and np.isfinite(worst) and abs(worst) >= 2.0)
        r["a4_worst_t"] = float(worst) if np.isfinite(worst) else None
        r["verdict"] = "PROCEED to A5-A7" if ok else "KILL"
        if ok:
            final.append(r["feature"])
        print(f"  {r['feature']:<12} A2={r['a2']:<18} "
              f"A4 weakest t={r['a4_worst_t']}  -> {r['verdict']}")
    print(f"\n  {len(final)}/{len(rows)} reach the economic gates.")

    (OUT / "e7_data.json").write_text(json.dumps({"rows": rows, "survivors": final},
                                                 indent=2, default=str))
    print(f"\n-> {OUT/'e7_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
