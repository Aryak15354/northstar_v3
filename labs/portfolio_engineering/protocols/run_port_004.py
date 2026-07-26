#!/usr/bin/env python3
"""PORT-004 -- vol-targeting + drawdown de-gross overlays, extended to Sleeve-2 and the combined book.

Executes labs/portfolio_engineering/protocols/PORT-004_SLEEVE2_AND_COMBINED_BOOK.md. Reuses the exact
overlay mechanisms from PORT-001/PORT-002 (leverage clip, drawdown thresholds, PIT-safe shift(1) fix)
unchanged, applied to two new bases: Sleeve-2 alone and the 80/20 combined book.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts/kaggle/plan_2026_05_18_production"))

import run_final_portfolio_matrix as M  # noqa: E402
from run_g02_regime import build_regimes  # noqa: E402
from run_sector_cert_signal import load_piv, rot  # noqa: E402
from research_os.experiment_registry import close_experiment  # noqa: E402

# reuse the exact PORT-001/002 build routine (Sleeve-1 baseline) from the sibling script
sys.path.insert(0, str(ROOT / "labs/portfolio_engineering/protocols"))
from run_port_001_002_003 import (  # noqa: E402
    build_config4_g05_with_events, apply_leverage_overlay, sharpe, cagr, maxdd, window_dd,
    LOCK, GEN5_BAR, LEV_MIN, LEV_MAX, DD_TRIGGER, DD_RESTORE, DEGROSS_MULT,
)

OUT = ROOT / "labs/portfolio_engineering/results/PORT-004"
OUT.mkdir(parents=True, exist_ok=True)

SLEEVE2_WEIGHT = 0.20
SLEEVE1_WEIGHT = 0.80


def vol_target_overlay(base: pd.Series, events_dates: set) -> pd.Series:
    pre = base[base.index < LOCK]
    target_vol = float(pre.std(ddof=1) * np.sqrt(52))
    trail_vol = base.shift(1).rolling(13, min_periods=8).std() * np.sqrt(52)
    lev = (target_vol / trail_vol).clip(LEV_MIN, LEV_MAX).fillna(1.0)
    return apply_leverage_overlay(base, events_dates, lev), target_vol


def degross_overlay(base: pd.Series, events_dates: set) -> pd.Series:
    cum = base.shift(1).fillna(0.0).cumsum()
    running_peak = cum.cummax()
    dd = np.expm1(cum - running_peak)
    lev_vals, state = {}, 1.0
    for d in base.index:
        if state == 1.0 and dd.loc[d] <= DD_TRIGGER:
            state = DEGROSS_MULT
        elif state == DEGROSS_MULT and dd.loc[d] >= DD_RESTORE:
            state = 1.0
        lev_vals[d] = state
    lev = pd.Series(lev_vals)
    lev_at_events = lev.reindex(sorted(events_dates)).ffill()
    return apply_leverage_overlay(base, events_dates, lev_at_events)


def evaluate_base(name: str, base: pd.Series, events_dates: set) -> dict:
    print(f"\n{'-'*100}\n{name}\n{'-'*100}")
    m_base = dict(cagr=cagr(base[base.index < LOCK]), sharpe=sharpe(base[base.index < LOCK]),
                 maxdd=maxdd(base[base.index < LOCK]),
                 gfc=window_dd(base, "2008-01-01", "2009-06-30"),
                 covid=window_dd(base, "2020-02-01", "2020-06-30"))
    print(f"baseline pre-lockbox: CAGR {m_base['cagr']:+.1%} Sharpe {m_base['sharpe']:+.3f} "
         f"maxDD {m_base['maxdd']:+.1%}")

    vol_overlay, target_vol = vol_target_overlay(base, events_dates)
    m_vol = dict(cagr=cagr(vol_overlay[vol_overlay.index < LOCK]),
                sharpe=sharpe(vol_overlay[vol_overlay.index < LOCK]),
                maxdd=maxdd(vol_overlay[vol_overlay.index < LOCK]))
    sharpe_delta = m_vol["sharpe"] - m_base["sharpe"]
    vol_verdict = ("VALIDATED" if sharpe_delta >= GEN5_BAR else
                  "INCONCLUSIVE" if abs(sharpe_delta) < 0.02 else "REJECTED")
    print(f"  vol-targeting (target_vol={target_vol:.1%}): overlay Sharpe {m_vol['sharpe']:+.3f} "
         f"maxDD {m_vol['maxdd']:+.1%}  delta {sharpe_delta:+.3f}  -> {vol_verdict}")

    dg_overlay = degross_overlay(base, events_dates)
    m_dg = dict(cagr=cagr(dg_overlay[dg_overlay.index < LOCK]),
               sharpe=sharpe(dg_overlay[dg_overlay.index < LOCK]),
               maxdd=maxdd(dg_overlay[dg_overlay.index < LOCK]),
               gfc=window_dd(dg_overlay, "2008-01-01", "2009-06-30"),
               covid=window_dd(dg_overlay, "2020-02-01", "2020-06-30"))
    dd_improve = m_dg["maxdd"] - m_base["maxdd"]
    cagr_cost = m_base["cagr"] - m_dg["cagr"]
    favorable = dd_improve > 0.02 and cagr_cost < 0.03
    dg_verdict = "VALIDATED" if favorable else ("REJECTED" if dd_improve <= 0.005 else "INCONCLUSIVE")
    print(f"  drawdown de-gross: overlay maxDD {m_dg['maxdd']:+.1%} (GFC {m_dg['gfc']:+.1%}) "
         f"CAGR {m_dg['cagr']:+.1%}  dd_improve {dd_improve:+.1%}  cagr_cost {cagr_cost:+.1%}  "
         f"-> {dg_verdict}")

    return dict(base=m_base, vol_targeting=dict(target_vol=target_vol, overlay=m_vol,
                sharpe_delta=sharpe_delta, verdict=vol_verdict),
               drawdown_degross=dict(overlay=m_dg, maxdd_improvement=dd_improve,
                                    cagr_cost=cagr_cost, verdict=dg_verdict))


def main() -> int:
    print("=" * 100)
    print("PORT-004 -- OVERLAY EXTENSION TO SLEEVE-2 AND THE COMBINED 80/20 BOOK")
    print("=" * 100)

    df = M.load()
    print(f"panel: {len(df):,} rows, {df['date'].nunique()} weeks")

    print("\nBuilding Sleeve-1 (Config-4+G-05) baseline, reused from PORT-001/002 ...")
    sleeve1, events = build_config4_g05_with_events(df)
    events_dates = {ev["date"] for ev in events}

    print("Building Sleeve-2 (sector rotation, rot(piv,13,2,4) -- exact FROZEN_SPEC parameters) ...")
    piv = load_piv()
    sleeve2 = rot(piv, lookback=13, k=2, rebal=4)
    print(f"sleeve-2: {len(sleeve2)} weeks, {sleeve2.index.min().date()}..{sleeve2.index.max().date()}")

    common = sleeve1.index.intersection(sleeve2.index)
    print(f"sleeve-1/sleeve-2 common weeks: {len(common)}")
    combined = (SLEEVE1_WEIGHT * sleeve1.reindex(common) + SLEEVE2_WEIGHT * sleeve2.reindex(common)).dropna()

    # sleeve-2 doesn't share sleeve-1's exact rebalance-event calendar, but rot() rebalances every
    # 4th week of its own index too -- approximate its rebalance dates the same way (every 4th week).
    sleeve2_dates = sorted(sleeve2.index)
    sleeve2_events = set(sleeve2_dates[i] for i in range(0, len(sleeve2_dates), 4))
    combined_events = events_dates | sleeve2_events

    r_sleeve2 = evaluate_base("Sleeve-2 (sector rotation) alone", sleeve2, sleeve2_events)
    r_combined = evaluate_base("Combined 80/20 book", combined, combined_events)

    all_results = dict(sleeve2=r_sleeve2, combined=r_combined)
    (OUT / "port004_data.json").write_text(json.dumps(all_results, indent=2, default=str))

    verdicts = [r_sleeve2["vol_targeting"]["verdict"], r_sleeve2["drawdown_degross"]["verdict"],
               r_combined["vol_targeting"]["verdict"], r_combined["drawdown_degross"]["verdict"]]
    print("\n" + "=" * 100)
    print("SUMMARY")
    print(f"  Sleeve-2  vol-targeting -> {r_sleeve2['vol_targeting']['verdict']}")
    print(f"  Sleeve-2  drawdown de-gross -> {r_sleeve2['drawdown_degross']['verdict']}")
    print(f"  Combined  vol-targeting -> {r_combined['vol_targeting']['verdict']}")
    print(f"  Combined  drawdown de-gross -> {r_combined['drawdown_degross']['verdict']}")
    print("=" * 100)

    # one overall verdict for the registry: VALIDATED only if every sub-test validated, REJECTED
    # only if every sub-test rejected, else INCONCLUSIVE -- an honest summary of a mixed result.
    if all(v == "VALIDATED" for v in verdicts):
        overall = "VALIDATED"
    elif all(v == "REJECTED" for v in verdicts):
        overall = "REJECTED"
    else:
        overall = "INCONCLUSIVE"
    print(f"\nOVERALL (registry) verdict: {overall} -- see FINDINGS.md for the four sub-results")

    close_experiment("PORT-004", overall, "labs/portfolio_engineering/results/PORT-004/FINDINGS.md")
    print(f"\nwrote {OUT / 'port004_data.json'}; PORT-004 closed as {overall}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
