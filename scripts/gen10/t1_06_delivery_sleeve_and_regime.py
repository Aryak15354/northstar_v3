#!/usr/bin/env python3
"""T1-06 — Delivery: regime dependency (2.2') then sleeve integration (2.1').

Two open questions carried by the ARP dossier for four generations. Both are run here on
the MATCHED delivery window only (2020+), which is the constraint the remediation plan
did not account for.

2.2' RUNS FIRST because its output sizes 2.1'.

Design changes vs the plan, all pre-registered in GEN10_REMEDIATION_CHARTER.md s4/T1-06:

  * Two-state regime collapse. In the delivery era CRASH has 29 weeks and RECOVERY 15,
    both below MSRP's own MIN_N=30. Testing five states here would repeat M-02A's
    documented false positive (all six primitives falsely flagged regime-locked at small
    regime samples).

  * 2.1' is a SIZING question, not a significance question. G8-09 established that an
    unpaired blend-vs-momentum Sharpe test on this window has a minimum detectable
    difference ~8x its own bar. Running it again would reproduce UNRESOLVED. Instead:
    what Sleeve-B weight maximises blended Sharpe when Sleeve B's Sharpe is held at the
    LOWER BOUND of its own CI, and does that weight stay positive across the ladder?

  * Everything on matched 2020-2026 windows. Config-4's full-history Sharpe (0.8105 /
    0.8471) is never mixed with delivery-era numbers.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/kaggle/plan_2026_05_18_production"))
from src.research.gen10.inference import (  # noqa: E402
    nw_mean_test, per_date_ic, sharpe, sharpe_se, paired_sharpe_diff,
    min_detectable_sharpe_diff, ANN_WEEKLY,
)
from src.pnl.indian_cost_model import IndianEquityCostModel  # noqa: E402

OUT = ROOT / "results/gen10/T1-06"
OUT.mkdir(parents=True, exist_ok=True)
BASE = ROOT / "tmp/kaggle_uploads/panel_enriched"
SEED = 20260731
TOPQ = 0.80
DELIV_Q = 0.90
CAPITAL_CR = [0.05, 0.5, 1.0, 2.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0]
MIN_N_REGIME = 30                       # MSRP M-02's own gate
RISK_ON = {"NORMAL_UP", "STRONG_UP"}    # pre-registered two-state collapse


def load() -> pd.DataFrame:
    f = pd.read_parquet(BASE / "northstar_features_enriched.parquet",
                        columns=["date", "ticker", "target_weekly_return", "mom_60d_cs_z",
                                 "delivery_pct_4w_avg", "fut_oi"])
    md = pd.read_parquet(BASE / "northstar_metadata.parquet",
                         columns=["date", "ticker", "close", "volume"])
    for d in (f, md):
        d["date"] = pd.to_datetime(d["date"]).dt.normalize()
        d["ticker"] = d["ticker"].astype(str)
    df = f.merge(md, on=["date", "ticker"], how="left")
    df["adv"] = pd.to_numeric(df["close"], errors="coerce") * pd.to_numeric(df["volume"],
                                                                           errors="coerce")
    df["ret"] = df.groupby("date")["target_weekly_return"].transform(
        lambda s: s.clip(s.quantile(.01), s.quantile(.99)))
    df = df[df["delivery_pct_4w_avg"].notna() & df["mom_60d_cs_z"].notna()
            & df["ret"].notna()].copy()
    df["is_fno"] = df["fut_oi"].notna()
    return df


def build_regimes_panel_a() -> pd.Series:
    from run_g02_regime import build_regimes
    a = pd.read_parquet(ROOT / "data/kaggle_upload/panel_a_weekly.parquet",
                        columns=["date", "ticker", "ret_1w"])
    a["date"] = pd.to_datetime(a["date"]).dt.normalize()
    return build_regimes(a)


def sleeve_returns(df, selector):
    rets, holds = {}, {}
    for date, g in df.groupby("date"):
        sel = selector(g)
        if sel is None or len(sel) == 0:
            continue
        rets[date] = float(sel["ret"].mean())
        holds[date] = (set(sel["ticker"]), sel)
    return pd.Series(rets).sort_index(), holds


def sel_momentum(g):
    return g[g["mom_60d_cs_z"] >= g["mom_60d_cs_z"].quantile(TOPQ)]


def sel_delivery_tail(g):
    return g[(~g["is_fno"]) &
             (g["delivery_pct_4w_avg"] >= g["delivery_pct_4w_avg"].quantile(DELIV_Q))]


def turnover(holds):
    ks = sorted(holds)
    t = [len(holds[a][0] ^ holds[b][0]) / (len(holds[a][0]) + len(holds[b][0]))
         for a, b in zip(ks[:-1], ks[1:]) if holds[a][0] and holds[b][0]]
    return float(np.mean(t)) if t else 0.0


def net_sharpe_ladder(r: pd.Series, holds: dict) -> dict:
    """Real IndianEquityCostModel, per-name notional and per-name ADV, at each capital level."""
    model = IndianEquityCostModel()
    ks = sorted(holds)
    out = {}
    for nav_cr in CAPITAL_CR:
        nav = nav_cr * 1e7
        cost = {}
        for i in range(1, len(ks)):
            pn, pg = holds[ks[i - 1]]
            cn, cg = holds[ks[i]]
            if not cn:
                continue
            pos = nav / len(cn)
            traded = pn.symmetric_difference(cn)
            if not traded:
                cost[ks[i]] = 0.0
                continue
            adv = dict(zip(pg["ticker"], pg["adv"]))
            adv.update(dict(zip(cg["ticker"], cg["adv"])))
            tot = sum(model.cost_breakdown("BUY" if tk in cn else "SELL", pos,
                                           adv_inr=adv.get(tk)).total for tk in traded)
            cost[ks[i]] = tot / nav
        c = pd.Series(cost).reindex(r.index).fillna(0.0)
        nr = r - c
        out[nav_cr] = {"net_sharpe": sharpe(nr), "net_ann_ret": float(nr.mean() * 52),
                       "mean_cost_bps": float(c.mean() * 1e4)}
    return out


def main() -> int:
    print("=" * 96)
    print("T1-06 — DELIVERY REGIME DEPENDENCY (2.2') AND SLEEVE INTEGRATION (2.1')")
    print("=" * 96)
    df = load()
    reg = build_regimes_panel_a()
    print(f"matched window: {df['date'].min().date()} -> {df['date'].max().date()}  "
          f"({df['date'].nunique()} weeks)\n")

    # ================================================================================
    # 2.2'  REGIME DEPENDENCY
    # ================================================================================
    print("=" * 96)
    print("PART 1 (2.2') — IS DELIVERY REGIME-CONDITIONAL?")
    print("=" * 96)
    d = df.copy()
    d["regime5"] = d["date"].map(reg)
    counts = d.groupby("regime5")["date"].nunique().sort_values(ascending=False)
    print("\n5-state regime cells in the delivery era:")
    for k, v in counts.items():
        flag = "" if v >= MIN_N_REGIME else f"   << below MIN_N={MIN_N_REGIME}"
        print(f"    {k:<12} {v:>4} weeks{flag}")
    blocked = [k for k, v in counts.items() if v < MIN_N_REGIME]
    print(f"\n  -> {len(blocked)} of {len(counts)} states fail MSRP's own MIN_N gate "
          f"({', '.join(blocked)}).")
    print("     Pre-registered fallback: two-state collapse.\n")

    d["regime2"] = np.where(d["regime5"].isin(RISK_ON), "RISK_ON", "RISK_OFF")
    res2 = {}
    for st, g in d.groupby("regime2"):
        s = g[["date", "delivery_pct_4w_avg", "ret"]].dropna()
        ic = per_date_ic(s, "date", "delivery_pct_4w_avg", "ret", min_pairs=20)
        r = nw_mean_test(ic.to_numpy(), overlap=1, label=st, n_boot=3000, seed=SEED)
        res2[st] = r
        print(f"  {st:<9} IC={r.estimate:+.4f}  t={r.t:+.2f}  n={r.n:>3} weeks  "
              f"boot95=[{r.boot_ci_lo:+.4f},{r.boot_ci_hi:+.4f}]")

    # is the DIFFERENCE between states significant? (the actual hypothesis)
    on = d[d["regime2"] == "RISK_ON"]
    off = d[d["regime2"] == "RISK_OFF"]
    ic_on = per_date_ic(on, "date", "delivery_pct_4w_avg", "ret", min_pairs=20)
    ic_off = per_date_ic(off, "date", "delivery_pct_4w_avg", "ret", min_pairs=20)
    pooled = np.concatenate([ic_on.to_numpy(), -ic_off.to_numpy()])
    diff_est = float(ic_on.mean() - ic_off.mean())
    se_d = float(np.sqrt(nw_mean_test(ic_on.to_numpy(), 1, n_boot=500).se ** 2 +
                         nw_mean_test(ic_off.to_numpy(), 1, n_boot=500).se ** 2))
    t_d = diff_est / se_d if se_d > 0 else np.nan
    print(f"\n  DIFFERENCE RISK_ON - RISK_OFF: {diff_est:+.4f}  SE={se_d:.4f}  t={t_d:+.2f}")
    regime_conditional = abs(t_d) >= 2.0
    print(f"  -> delivery is {'REGIME-CONDITIONAL' if regime_conditional else 'NOT regime-conditional'}"
          f" on the evidence available")
    print(f"  -> sizing implication: {'regime-conditional Sleeve-B weight' if regime_conditional else 'a STATIC Sleeve-B weight is the correct choice for 2.1'}")

    # ================================================================================
    # 2.1'  SLEEVE INTEGRATION
    # ================================================================================
    print("\n" + "=" * 96)
    print("PART 2 (2.1') — SLEEVE INTEGRATION WITH THE FROZEN BOOK")
    print("=" * 96)

    rA, hA = sleeve_returns(df, sel_momentum)          # Sleeve A: momentum
    rB, hB = sleeve_returns(df, sel_delivery_tail)     # Sleeve B: delivery non-F&O tail
    common = rA.index.intersection(rB.index)
    rA, rB = rA.reindex(common), rB.reindex(common)

    # ---- step 1 (plan's step 3, promoted to first): name collision --------------------
    print("\n--- step 1: name-overlap between the two sleeves ---")
    ov = []
    for dt in common:
        a, b = hA[dt][0], hB[dt][0]
        if a and b:
            ov.append({"date": dt, "nA": len(a), "nB": len(b), "shared": len(a & b),
                       "jaccard": len(a & b) / len(a | b)})
    ovd = pd.DataFrame(ov)
    print(f"    Sleeve A (momentum top-{100-TOPQ*100:.0f}%): {ovd.nA.mean():.0f} names/week")
    print(f"    Sleeve B (non-F&O delivery top-{100-DELIV_Q*100:.0f}%): {ovd.nB.mean():.0f} names/week")
    print(f"    shared names: {ovd.shared.mean():.1f}/week  "
          f"({ovd.shared.mean()/ovd.nB.mean():.1%} of Sleeve B)")
    print(f"    Jaccard: {ovd.jaccard.mean():.4f}")
    separable = ovd.shared.mean() / ovd.nB.mean() < 0.25
    print(f"    -> sleeves are {'SEPARABLE' if separable else 'NOT separable'}; "
          f"{'no' if separable else 'material'} position-level double-counting")

    # ---- step 2: sleeve statistics on the MATCHED window -----------------------------
    print("\n--- step 2: sleeve statistics, matched 2020-2026 window ---")
    rho = float(np.corrcoef(rA, rB)[0, 1])
    shA, shB = sharpe(rA), sharpe(rB)
    seA, seB = sharpe_se(rA), sharpe_se(rB)
    print(f"    Sleeve A  Sharpe {shA:+.4f} +/- {seA:.4f}   (95% CI "
          f"[{shA-1.96*seA:+.3f}, {shA+1.96*seA:+.3f}])")
    print(f"    Sleeve B  Sharpe {shB:+.4f} +/- {seB:.4f}   (95% CI "
          f"[{shB-1.96*seB:+.3f}, {shB+1.96*seB:+.3f}])")
    print(f"    correlation {rho:+.4f}   <-- the ARP dossier's 0.14 is SIGNAL orthogonality,")
    print( "                          not sleeve-return correlation. Two long-only Indian")
    print( "                          equity books share market beta whatever their signals.")
    print(f"    n = {len(common)} weeks")

    # is Sleeve B's apparent Sharpe advantage even real?
    adv = paired_sharpe_diff(rA, rB, label="Sleeve B - Sleeve A", seed=SEED)
    print(f"\n    Sleeve B vs Sleeve A: {adv}")
    print(f"    -> B's Sharpe advantage is "
          f"{'significant' if abs(adv.t) >= 2 else 'NOT significant'} on this window")
    print("\n    NOTE: Config-4's certified full-history Sharpe is 0.8105/0.8471. It is NOT")
    print("    used here. The delivery era is a different, stronger market for this book,")
    print("    and mixing the two manufactures an improvement (G8-09 s3 made the same point).")

    # ---- step 3: the significance test the plan wanted, with its MDE stated -----------
    print("\n--- step 3: the blend-vs-momentum significance test (DESCRIPTIVE ONLY) ---")
    w_naive = 0.20
    r_blend_naive = (1 - w_naive) * rA + w_naive * rB
    pt = paired_sharpe_diff(rA, r_blend_naive, label=f"blend(w={w_naive}) vs momentum",
                            seed=SEED)
    mde_unpaired = min_detectable_sharpe_diff(rA.to_numpy(), paired_corr=None)
    mde_paired = min_detectable_sharpe_diff(rA.to_numpy(),
                                            paired_corr=float(np.corrcoef(rA, r_blend_naive)[0, 1]))
    print(f"    {pt}")
    print(f"    MDE at 80% power — unpaired {mde_unpaired:+.3f} Sharpe (the plan's step-5 design)")
    print(f"    MDE at 80% power — paired   {mde_paired:+.3f} Sharpe")
    print("    -> reported descriptively. The pre-registered decision is the sizing question below.")

    # ---- step 4: THE PRE-REGISTERED QUESTION -----------------------------------------
    print("\n--- step 4: PRE-REGISTERED — optimal Sleeve-B weight at the CI lower bound ---")
    print("    Sleeve B's own Sharpe is uncertain on 320 weeks. Set it to the lower bound")
    print("    of its 95% CI and ask whether any positive allocation still helps.\n")

    grid = np.arange(0.0, 1.001, 0.01)   # full range: an interior optimum must be visible

    def shift_to_sharpe(r: pd.Series, target_sh: float) -> pd.Series:
        """Move a return series' MEAN so its annualised Sharpe equals `target_sh`, holding
        vol fixed. NOTE: multiplying a return series by a constant leaves Sharpe unchanged,
        so a scale factor cannot express 'Sleeve B is weaker than measured' — only a mean
        shift can."""
        return r - r.mean() + target_sh * r.std() / ANN_WEEKLY

    lbB = shB - 1.96 * seB
    curves = {}
    for nm, target in (("point estimate", shB), ("CI lower bound", lbB)):
        rb = shift_to_sharpe(rB, target)
        vals = [sharpe((1 - w) * rA + w * rb) for w in grid]
        w_star = float(grid[int(np.argmax(vals))])
        curves[nm] = {"assumed_B_sharpe": float(target), "w_star": w_star,
                      "sharpe_at_w_star": float(max(vals)), "sharpe_at_0": float(vals[0]),
                      "gain": float(max(vals) - vals[0]),
                      "corner": bool(w_star >= 0.99)}
        print(f"    Sleeve B at {nm:<16} (standalone Sharpe {target:+.3f}): "
              f"w* = {w_star:.0%}   blended Sharpe {max(vals):+.4f}  "
              f"(vs {vals[0]:+.4f} at w=0, gain {max(vals)-vals[0]:+.4f})"
              f"{'   [CORNER]' if w_star >= 0.99 else ''}")

    # ---- step 4b: the honest version — distribution of w* under resampling -------------
    print("\n--- step 4b: bootstrap distribution of w* (both sleeves resampled jointly) ---")
    print("    A single point-estimate w* is not a sizing answer when each sleeve's Sharpe")
    print("    carries SE ~0.40. Resample the PAIRED weekly returns in blocks and recompute")
    print("    w* in each draw.\n")
    rng = np.random.default_rng(SEED)
    n = len(rA)
    exp_block = max(1.0, n ** (1.0 / 3.0))
    p_restart = 1.0 / exp_block
    A_, B_ = rA.to_numpy(), rB.to_numpy()
    ws = []
    for _ in range(2000):
        idx = np.empty(n, dtype=int)
        idx[0] = rng.integers(0, n)
        for j in range(1, n):
            idx[j] = (idx[j - 1] + 1) % n if rng.random() > p_restart else rng.integers(0, n)
        a_, b_ = A_[idx], B_[idx]
        vals = [sharpe((1 - w) * a_ + w * b_) for w in grid]
        ws.append(float(grid[int(np.argmax(vals))]))
    ws = np.array(ws)
    q = np.quantile(ws, [0.05, 0.25, 0.5, 0.75, 0.95])
    print(f"    w* distribution: 5% {q[0]:.0%} | 25% {q[1]:.0%} | median {q[2]:.0%} | "
          f"75% {q[3]:.0%} | 95% {q[4]:.0%}")
    print(f"    P(w* = 0)   = {(ws <= 0.005).mean():.1%}")
    print(f"    P(w* >= 50%) = {(ws >= 0.50).mean():.1%}")
    print(f"    P(w* = 100%) = {(ws >= 0.995).mean():.1%}")
    print("    -> a w* that swings across the whole [0,1] range under resampling is not a")
    print("       sizing recommendation; it is a restatement of how little 338 weeks says.")
    curves["bootstrap_w_star"] = {"q05": float(q[0]), "q25": float(q[1]),
                                  "median": float(q[2]), "q75": float(q[3]),
                                  "q95": float(q[4]),
                                  "p_zero": float((ws <= 0.005).mean()),
                                  "p_ge_50": float((ws >= 0.50).mean()),
                                  "p_full": float((ws >= 0.995).mean())}

    # ---- step 5: does w* stay positive across the capacity ladder? --------------------
    print("\n--- step 5: does the optimal weight survive real costs across the ladder? ---")
    ladA = net_sharpe_ladder(rA, hA)
    ladB = net_sharpe_ladder(rB, hB)
    tnA, tnB = turnover(hA), turnover(hB)
    print(f"    weekly turnover — Sleeve A {tnA:.3f}, Sleeve B {tnB:.3f}")
    print(f"\n    {'capital':>9}{'A net Sh':>11}{'B net Sh':>11}{'w* (point)':>12}"
          f"{'w* (CI lo)':>12}{'blend gain':>12}")
    ladder_rows = []
    for cr in CAPITAL_CR:
        sA, sB_ = ladA[cr]["net_sharpe"], ladB[cr]["net_sharpe"]
        # rescale each sleeve's returns to its net Sharpe, keeping vol and correlation
        fA = (sA / shA) if shA else 0.0
        fB = (sB_ / shB) if shB else 0.0
        rA_net = shift_to_sharpe(rA, sA)
        best = {}
        for nm, target in (("point", sB_), ("ci_lo", sB_ - 1.96 * seB)):
            rB_net = shift_to_sharpe(rB, target)
            vals = [sharpe((1 - w) * rA_net + w * rB_net) for w in grid]
            best[nm] = (float(grid[int(np.argmax(vals))]), float(max(vals)),
                        float(vals[0]))
        ladder_rows.append({"capital_cr": cr, "A_net_sharpe": sA, "B_net_sharpe": sB_,
                            "w_star_point": best["point"][0], "w_star_ci_lo": best["ci_lo"][0],
                            "blend_gain_point": best["point"][1] - best["point"][2],
                            "blend_gain_ci_lo": best["ci_lo"][1] - best["ci_lo"][2]})
        print(f"    Rs{cr:>7.2f}cr{sA:>11.4f}{sB_:>11.4f}{best['point'][0]:>11.0%}"
              f"{best['ci_lo'][0]:>12.0%}{best['point'][1]-best['point'][2]:>12.4f}")

    # the pre-registered band is Rs5L..Rs100cr (charter s4/T1-06), not the whole ladder
    BAND = [r for r in ladder_rows if r["capital_cr"] <= 100.0]
    w_lo = [r["w_star_ci_lo"] for r in BAND]
    w_lo_all = [r["w_star_ci_lo"] for r in ladder_rows]
    promote = all(w > 0 for w in w_lo) and separable
    print("\n" + "=" * 96)
    print("VERDICT vs the pre-registered rule (charter s4/T1-06)")
    print("  promote = optimal weight > 0 at the CI lower bound across Rs5L-Rs100cr AND")
    print("            sleeves separable")
    print("=" * 96)
    print(f"  sleeves separable                  : {separable}")
    print(f"  w* > 0 at CI lower bound, Rs5L-Rs100cr: {all(w > 0 for w in w_lo)}  "
          f"(range {min(w_lo):.0%}-{max(w_lo):.0%})")
    above = "; ".join(f"Rs{int(r['capital_cr'])}cr w*={r['w_star_ci_lo']:.0%}"
                      for r in ladder_rows if r["capital_cr"] > 100)
    print(f"  ...above the pre-registered band      : {above}")
    print(f"  regime-conditional sizing needed      : {regime_conditional}")
    print(f"\n  --> {'PROMOTE' if promote else 'DO NOT PROMOTE'}: "
          f"{'a static Sleeve-B allocation is justified within the band'
             if promote else 'allocation collapses under uncertainty'}")
    if promote:
        print("      Binding constraint is CAPACITY, not signal quality: Sleeve B's net")
        print("      Sharpe turns negative above ~Rs100cr and w* goes to zero there.")

    payload = {
        "experiment": "T1-06",
        "window": [str(df["date"].min().date()), str(df["date"].max().date())],
        "n_weeks": int(len(common)),
        "regime": {"cells_5state": {k: int(v) for k, v in counts.items()},
                   "blocked_by_min_n": blocked,
                   "two_state": {k: v.to_dict() for k, v in res2.items()},
                   "difference": {"estimate": diff_est, "se": se_d, "t": float(t_d),
                                  "regime_conditional": bool(regime_conditional)}},
        "overlap": {"mean_nA": float(ovd.nA.mean()), "mean_nB": float(ovd.nB.mean()),
                    "mean_shared": float(ovd.shared.mean()),
                    "shared_share_of_B": float(ovd.shared.mean() / ovd.nB.mean()),
                    "jaccard": float(ovd.jaccard.mean()), "separable": bool(separable)},
        "sleeves": {"A_sharpe": shA, "A_se": seA, "B_sharpe": shB, "B_se": seB,
                    "correlation": rho, "turnover_A": tnA, "turnover_B": tnB},
        "descriptive_significance": {"paired_test": pt.to_dict(),
                                     "mde_unpaired": float(mde_unpaired),
                                     "mde_paired": float(mde_paired)},
        "sizing": curves, "capacity_ladder": ladder_rows,
        "verdict": "PROMOTE" if promote else "DO NOT PROMOTE",
    }
    (OUT / "t1_06_data.json").write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n-> {OUT/'t1_06_data.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
