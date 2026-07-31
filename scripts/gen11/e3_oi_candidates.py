#!/usr/bin/env python3
"""E3 — Futures-OI candidates through charter gates A0-A4.

E2 localised the incremental ceiling: futures OI adds +0.0266 over the price basis and
+0.0121 OVER the already-deployed delivery block. The market-level control returned exactly
+0.0000, which validates the method.

Futures OI was REJECTED individually by G2-E01 (abnormal OI vs own history, t = -0.27) and
G2-E02 (4-week OI build -> continuation, t = -0.03), and OI interactions were rejected by
DS-F1-02 (t = 1.47) and DS-F3-03 (t = -1.21). Those are close cousins of what follows, and
they are the reason the bar here is the full adversarial gate rather than a t-statistic.

The ceiling result says something those tests could not: OI adds JOINTLY with price even
though it carries nothing alone. That points at an interaction, not a standalone factor.

ECONOMIC STORY (gate A6, stated BEFORE the test). Open interest tells you whether a price
move is backed by new positioning or by positions closing. Price up + OI up = new longs
being opened, i.e. conviction. Price up + OI down = short covering, i.e. a move without
fresh commitment behind it. The two look identical in the price series and different in the
OI series. That is a real, well-understood microstructure distinction, and it is why an
interaction is the natural construction and a standalone OI level is not.

PRE-REGISTERED, m = 5 constructions, declared before results:
  C1 oi_chg_z      4-week OI change, cross-sectionally z-scored      (direct)
  C2 oi_z52        OI vs its own 52-week history                     (direct, = G2-E01)
  C3 oi_x_mom      momentum x OI change                              (conviction interaction)
  C4 oi_confirm    sign(20d return) x sign(4w OI change)             (pure confirmation)
  C5 oi_divergence z(OI change) - z(20d return)                      (positioning w/o price)

GATES APPLIED HERE (A5-A7 only if something survives):
  A0 coverage      >= 150 dates
  A1 incremental   |t| >= 2 AFTER orthogonalising against momentum, per date, in rank space
  A2 OOS           OOS |t| >= 2 and no sign flip
  A3 multiplicity  BY-clean at m = 5
  A4 rediscovery   also orthogonalised against DELIVERY on the overlap window
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

OUT = ROOT / "results/gen11/E3"
OUT.mkdir(parents=True, exist_ok=True)
BASE = ROOT / "tmp/kaggle_uploads/panel_enriched"
SEED = 20260731
LOCK = pd.Timestamp("2025-07-11")
DISC_END = pd.Timestamp("2018-12-31")
OOS_END = LOCK
MOM = ["mom_60d_cs_z", "mom_63d_1m_lag_cs_z", "res_mom_60d", "res_mom_20d_cs_z"]
CANDS = ["C1_oi_chg_z", "C2_oi_z52", "C3_oi_x_mom", "C4_oi_confirm", "C5_oi_divergence"]


def load():
    cols = ["date", "ticker", "target_weekly_return", "fut_oi", "fut_oi_chg_4w_pct",
            "fut_oi_z52", "ret_20d_cs_z", "delivery_pct_z52"] + MOM
    d = pd.read_parquet(BASE / "northstar_features_enriched.parquet", columns=cols)
    d["date"] = pd.to_datetime(d["date"]).dt.normalize()
    d = d[d["date"] <= pd.Timestamp("2026-07-01")]
    d["ret"] = d.groupby("date")["target_weekly_return"].transform(
        lambda s: s.clip(s.quantile(.01), s.quantile(.99)))
    d = d[d["fut_oi"].notna() & d["ret"].notna()].copy()

    def z(c):
        g = d.groupby("date")[c]
        return (d[c] - g.transform("mean")) / g.transform("std").replace(0, np.nan)

    d["mom_comp"] = pd.concat([z(c) for c in MOM], axis=1).mean(axis=1)
    d["oi_chg_z"] = z("fut_oi_chg_4w_pct")
    d["C1_oi_chg_z"] = d["oi_chg_z"]
    d["C2_oi_z52"] = d["fut_oi_z52"]
    d["C3_oi_x_mom"] = d["oi_chg_z"] * d["mom_comp"]
    d["C4_oi_confirm"] = np.sign(d["ret_20d_cs_z"].fillna(0)) * np.sign(
        d["fut_oi_chg_4w_pct"].fillna(0))
    d["C5_oi_divergence"] = d["oi_chg_z"] - d["ret_20d_cs_z"]
    return d


def resid(frame, col, against):
    """Per-date cross-sectional residual of `col` on `against`, in rank space."""
    def _r(g):
        s = g[[col, against]].dropna()
        if len(s) < 25 or s[against].nunique() < 3 or s[col].nunique() < 3:
            return pd.Series(np.nan, index=g.index)
        x = s[against].rank(); y = s[col].rank()
        xc = x - x.mean()
        b = float((xc * (y - y.mean())).sum() / max((xc * xc).sum(), 1e-12))
        return ((y - y.mean()) - b * xc).reindex(g.index)
    return frame.groupby("date", group_keys=False).apply(_r, include_groups=False)


def ic_test(frame, col, label, min_pairs=25):
    s = frame[["date", col, "ret"]].dropna()
    if s["date"].nunique() < 60:
        return None
    ic = per_date_ic(s, "date", col, "ret", min_pairs=min_pairs)
    if len(ic) < 60:
        return None
    return nw_mean_test(ic.to_numpy(), overlap=1, label=label, n_boot=2500, seed=SEED)


def main() -> int:
    print("=" * 100)
    print("E3 — FUTURES-OI CANDIDATES THROUGH GATES A0-A4")
    print("=" * 100)
    d = load()
    print(f"universe: {len(d):,} rows | {d['date'].nunique()} weeks "
          f"({d['date'].min().date()} .. {d['date'].max().date()}) | "
          f"median {d.groupby('date').size().median():.0f} names/wk  (F&O-eligible only)\n")

    # ---- A1: raw and momentum-orthogonalised ----
    print("--- A1: incremental over momentum (per-date rank-space residual) ---")
    print(f"{'candidate':<18}{'raw IC':>10}{'raw t':>8}{'resid IC':>11}{'resid t':>10}"
          f"{'kept':>7}   bootstrap CI (resid)")
    rows = []
    for c in CANDS:
        raw = ic_test(d, c, c)
        dd = d.copy()
        dd["_r"] = resid(dd, c, "mom_comp")
        res = ic_test(dd, "_r", c + "|mom")
        if raw is None or res is None:
            print(f"{c:<18}  not testable"); continue
        kept = abs(res.t) / abs(raw.t) if raw.t else np.nan
        rows.append({"cand": c, "raw_ic": float(raw.estimate), "raw_t": float(raw.t),
                     "res_ic": float(res.estimate), "res_t": float(res.t),
                     "res_p": float(res.p), "kept": float(kept),
                     "boot": [res.boot_ci_lo, res.boot_ci_hi], "n": int(res.n)})
        print(f"{c:<18}{raw.estimate:>+10.4f}{raw.t:>+8.2f}{res.estimate:>+11.4f}"
              f"{res.t:>+10.2f}{kept:>6.0%}   [{res.boot_ci_lo:+.4f},{res.boot_ci_hi:+.4f}]")

    a1 = [r for r in rows if abs(r["res_t"]) >= 2.0]
    print(f"\n  A1: {len(a1)}/{len(rows)} clear |t| >= 2 after removing momentum")
    if not a1:
        print("  -> ALL DIE AT A1. No OI construction carries information beyond momentum.")
        (OUT / "e3_data.json").write_text(json.dumps({"rows": rows, "verdict": "ALL DIE AT A1"},
                                                     indent=2, default=str))
        return 0

    # ---- A2: out-of-sample split ----
    print(f"\n--- A2: OOS split (DISC <= {DISC_END.date()}, OOS -> {OOS_END.date()}, "
          f"LOCKBOX after) ---")
    disc, oos, lk = (d[d["date"] <= DISC_END],
                     d[(d["date"] > DISC_END) & (d["date"] <= OOS_END)],
                     d[d["date"] > OOS_END])
    for nm, x in (("DISCOVERY", disc), ("OOS", oos), ("LOCKBOX", lk)):
        print(f"  {nm:<10} {x['date'].nunique():>4} weeks")
    print(f"\n{'candidate':<18}{'DISC t':>9}{'OOS t':>9}{'LOCK t':>9}   verdict")
    for r in a1:
        c = r["cand"]
        out = {}
        for nm, x in (("disc", disc), ("oos", oos), ("lock", lk)):
            xx = x.copy()
            xx["_r"] = resid(xx, c, "mom_comp")
            out[nm] = ic_test(xx, "_r", f"{c}|{nm}")
        td = out["disc"].t if out["disc"] else np.nan
        to = out["oos"].t if out["oos"] else np.nan
        tl = out["lock"].t if out["lock"] else np.nan
        flip = (out["disc"] and out["oos"] and
                np.sign(out["disc"].estimate) != np.sign(out["oos"].estimate))
        v = ("KILL (sign flip)" if flip else
             "KILL (OOS |t|<2)" if not np.isfinite(to) or abs(to) < 2 else "SURVIVES A2")
        r.update(disc_t=float(td), oos_t=float(to) if np.isfinite(to) else None,
                 lock_t=float(tl) if np.isfinite(tl) else None, a2=v)
        f = lambda v: f"{v:+.2f}" if np.isfinite(v) else "  n/a"  # noqa
        print(f"{c:<18}{f(td):>9}{f(to):>9}{f(tl):>9}   {v}")

    # ---- A3 multiplicity, A4 rediscovery ----
    surv = [r for r in a1 if r["a2"] == "SURVIVES A2"]
    by = benjamini_yekutieli([r["res_p"] for r in rows], q=0.05)
    bymap = {r["cand"]: bool(b) for r, b in zip(rows, by)}
    print(f"\n--- A3: BY q=0.05 across all m={len(rows)} declared constructions ---")
    for r in rows:
        print(f"  {r['cand']:<18} p={r['res_p']:.4f}  BY-clean={bymap[r['cand']]}")

    print("\n--- A4: rediscovery check — also orthogonalise against DEPLOYED delivery ---")
    ov = d[d["delivery_pct_z52"].notna()].copy()
    print(f"  delivery-overlap window: {ov['date'].nunique()} weeks")
    for r in surv:
        c = r["cand"]
        t = ov.copy()
        t["_r1"] = resid(t, c, "mom_comp")
        t = t[t["_r1"].notna()]
        t["_r2"] = resid(t, "_r1", "delivery_pct_z52")
        rr = ic_test(t, "_r2", f"{c}|mom,delivery")
        r["a4_t"] = float(rr.t) if rr else None
        print(f"  {c:<18} after mom AND delivery: t = "
              f"{rr.t:+.2f}" if rr else f"  {c}: not testable")

    print("\n" + "=" * 100)
    print("VERDICT after A0-A4")
    print("=" * 100)
    final = [r for r in surv if bymap[r["cand"]]
             and r.get("a4_t") is not None and abs(r["a4_t"]) >= 2.0]
    for r in surv:
        ok = (bymap[r["cand"]] and r.get("a4_t") is not None and abs(r["a4_t"]) >= 2.0)
        print(f"  {r['cand']:<18} A2 pass, BY={bymap[r['cand']]}, "
              f"A4 t={r.get('a4_t')} -> {'PROCEED to A5-A7' if ok else 'KILL'}")
    if not surv:
        print("  none survived A2")
    print(f"\n  {len(final)} candidate(s) reach the economic gates.")

    (OUT / "e3_data.json").write_text(json.dumps(
        {"rows": rows, "survivors": [r["cand"] for r in final]}, indent=2, default=str))
    print(f"\n-> {OUT/'e3_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
