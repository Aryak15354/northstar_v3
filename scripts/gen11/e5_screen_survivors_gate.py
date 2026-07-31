#!/usr/bin/env python3
"""E5 — the screen's non-momentum survivors through gates A2-A4.

E4's sign-stability screen validated itself: momentum (positive control) 60.5% share-positive
t=+5.65, and delivery (the one known non-momentum signal) 62.2% t=+4.75 -- the top-ranked
feature of 25. Futures OI came in at 50.0%, confirming E3's kill.

Three CAPTURABLE features are neither momentum nor delivery:

  macro_linkage_score        58.0%  t=+3.33   1071 weeks   full history
  operating_margin_cs_z      57.2%  t=+2.14    929 weeks
  screener_roce_cs_z         56.3%  t=+2.15    854 weeks

Two of them are notable because Gen-1 REJECTED them raw: `screener_roce` scored IC -0.0182
t=-1.65 (FAILED_SIGN) and `operating_margin` IC -0.0072 t=-0.90. Those were unconditional
tests. E4 controls for momentum first, which is a different question -- and the sign flips.

Excluded from this gate, deliberately:
  * mom20_x_liquidity / res_mom20_x_liquidity (43.2%, 41.5%) -- momentum-DERIVED, so they
    fail the "alpha other than momentum" mandate by construction, and Gen-1's A15/A19 already
    killed the momentum x illiquidity interaction on transaction cost ("the edge sits exactly
    where impact cost kills it").
  * india_vix_z (38.9%) -- date-constant. It cannot produce cross-sectional IC; the screen's
    coefficient for it is an artifact of the few names with non-null values.

MULTIPLICITY, honestly counted: E4 screened 25 features and these 3 were CHOSEN from that
screen. So BY runs at m = 25, not m = 3. Selecting after looking is exactly what Rule 4 exists
to price.
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
from e1_ceiling_decomposition import BASE, LOCK  # noqa: E402
from e3_oi_candidates import resid, MOM  # noqa: E402

OUT = ROOT / "results/gen11/E5"
OUT.mkdir(parents=True, exist_ok=True)
SEED = 20260731
DISC_END = pd.Timestamp("2018-12-31")
CANDS = ["macro_linkage_score", "operating_margin_cs_z", "screener_roce_cs_z"]
M_SCREENED = 25


def ic_of(frame, col, label, overlap=1):
    s = frame[["date", col, "ret"]].dropna()
    if s["date"].nunique() < 60:
        return None
    ic = per_date_ic(s, "date", col, "ret", min_pairs=30)
    if len(ic) < 60:
        return None
    return nw_mean_test(ic.to_numpy(), overlap=overlap, label=label, n_boot=2500, seed=SEED)


def main() -> int:
    print("=" * 100)
    print("E5 — SCREEN SURVIVORS THROUGH A2-A4  (multiplicity at m=25, not m=3)")
    print("=" * 100)
    need = sorted(set(CANDS + MOM + ["delivery_pct_z52"]))
    d = pd.read_parquet(BASE / "northstar_features_enriched.parquet",
                        columns=["date", "ticker", "target_weekly_return"] + need)
    d["date"] = pd.to_datetime(d["date"]).dt.normalize()
    d = d[d["date"] <= pd.Timestamp("2026-07-01")]
    d["ret"] = d.groupby("date")["target_weekly_return"].transform(
        lambda s: s.clip(s.quantile(.01), s.quantile(.99)))
    d = d.dropna(subset=["ret"])

    def z(c):
        g = d.groupby("date")[c]
        return (d[c] - g.transform("mean")) / g.transform("std").replace(0, np.nan)
    d["mom_comp"] = pd.concat([z(c) for c in MOM], axis=1).mean(axis=1)

    print(f"\n{'candidate':<26}{'raw t':>8}{'|mom t':>9}{'DISC t':>9}{'OOS t':>9}"
          f"{'LOCK t':>9}   A2")
    print("-" * 100)
    rows = []
    for c in CANDS:
        dd = d[d[c].notna()].copy()
        raw = ic_of(dd, c, c)
        dd["_r"] = resid(dd, c, "mom_comp")
        full = ic_of(dd, "_r", c + "|mom")
        parts = {}
        for nm, x in (("disc", dd[dd["date"] <= DISC_END]),
                      ("oos", dd[(dd["date"] > DISC_END) & (dd["date"] <= LOCK)]),
                      ("lock", dd[dd["date"] > LOCK])):
            xx = x.copy()
            xx["_r"] = resid(xx, c, "mom_comp")
            parts[nm] = ic_of(xx, "_r", f"{c}|{nm}")
        td = parts["disc"].t if parts["disc"] else np.nan
        to = parts["oos"].t if parts["oos"] else np.nan
        tl = parts["lock"].t if parts["lock"] else np.nan
        flip = (parts["disc"] and parts["oos"]
                and np.sign(parts["disc"].estimate) != np.sign(parts["oos"].estimate))
        a2 = ("KILL (sign flip)" if flip else
              "KILL (OOS |t|<2)" if not np.isfinite(to) or abs(to) < 2 else "SURVIVES")
        rows.append({"cand": c, "raw_t": float(raw.t) if raw else None,
                     "mom_t": float(full.t) if full else None,
                     "mom_p": float(full.p) if full else 1.0,
                     "disc_t": float(td) if np.isfinite(td) else None,
                     "oos_t": float(to) if np.isfinite(to) else None,
                     "lock_t": float(tl) if np.isfinite(tl) else None,
                     "n_weeks": int(full.n) if full else 0, "a2": a2,
                     "sign_flip": bool(flip)})
        f = lambda v: f"{v:+.2f}" if v is not None and np.isfinite(v) else "  n/a"  # noqa
        print(f"{c:<26}{f(raw.t if raw else None):>8}{f(full.t if full else None):>9}"
              f"{f(td):>9}{f(to):>9}{f(tl):>9}   {a2}")

    # ---- A3: BY at the honest m ----
    print(f"\n--- A3: BY q=0.05 at m={M_SCREENED} (E4 screened 25; these 3 were chosen) ---")
    pv = [r["mom_p"] for r in rows] + [1.0] * (M_SCREENED - len(rows))
    by = benjamini_yekutieli(pv, q=0.05)[:len(rows)]
    for r, ok in zip(rows, by):
        r["by_clean"] = bool(ok)
        print(f"  {r['cand']:<26} p={r['mom_p']:.4f}  BY-clean at m=25: {bool(ok)}")

    # ---- A4: rediscovery vs delivery ----
    print("\n--- A4: also orthogonalise against DEPLOYED delivery (overlap window) ---")
    ov = d[d["delivery_pct_z52"].notna()].copy()
    for r in rows:
        c = r["cand"]
        t = ov[ov[c].notna()].copy()
        if t["date"].nunique() < 60:
            r["a4_t"] = None
            print(f"  {c:<26} overlap too short")
            continue
        t["_r1"] = resid(t, c, "mom_comp")
        t = t[t["_r1"].notna()]
        t["_r2"] = resid(t, "_r1", "delivery_pct_z52")
        rr = ic_of(t, "_r2", f"{c}|mom,delivery")
        r["a4_t"] = float(rr.t) if rr else None
        print(f"  {c:<26} after mom AND delivery: t={rr.t:+.2f}  ({rr.n} weeks)"
              if rr else f"  {c:<26} not testable")

    print("\n" + "=" * 100)
    print("VERDICT")
    print("=" * 100)
    surv = []
    for r in rows:
        ok = (r["a2"] == "SURVIVES" and r["by_clean"]
              and r["a4_t"] is not None and abs(r["a4_t"]) >= 2.0)
        if ok:
            surv.append(r)
        print(f"  {r['cand']:<26} A2={r['a2']:<18} BY={r['by_clean']}  "
              f"A4 t={r['a4_t']}  -> {'PROCEED' if ok else 'KILL'}")
    print(f"\n  {len(surv)}/{len(rows)} reach the economic gates (A5-A7).")
    if not surv:
        print("  -> Gen-11 has no surviving candidate. The screen's value is the METHOD,")
        print("     not a signal: it is a cheap pre-test that correctly ranks the two")
        print("     signals this programme already knows are real, and correctly kills OI.")

    (OUT / "e5_data.json").write_text(json.dumps(
        {"m_screened": M_SCREENED, "rows": rows,
         "survivors": [r["cand"] for r in surv]}, indent=2, default=str))
    print(f"\n-> {OUT/'e5_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
