#!/usr/bin/env python3
"""PORT-001/002/003 -- First Portfolio Engineering workstreams on the frozen book.

Executes labs/portfolio_engineering/protocols/PORT_001_002_003_FROZEN_BOOK_OVERLAYS.md. All three are
sizing/execution overlays on the already-frozen Config-4+G-05 signal (Sleeve-1, 80% of the book) --
none introduces a new predictive signal, per this lab's charter.
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
from src.pnl.indian_cost_model import IndianEquityCostModel  # noqa: E402
from research_os.experiment_registry import close_experiment  # noqa: E402

OUT = ROOT / "labs/portfolio_engineering/results/PORT-001-002-003"
OUT.mkdir(parents=True, exist_ok=True)

CM = IndianEquityCostModel()
LOCK = pd.Timestamp("2025-07-11")
ANN = 52
SHORT_COST_WK = 0.0008
GEN5_BAR = 0.15
LEV_MIN, LEV_MAX = 0.5, 1.5
DD_TRIGGER, DD_RESTORE, DEGROSS_MULT = -0.15, -0.05, 0.5
LEVERAGE_CHANGE_COST_BPS = 3.0
CAPITAL_TEST_CR = 2500.0
N_TRANCHES = 5


def sharpe(r: pd.Series) -> float:
    r = r.dropna()
    return float(r.mean() * ANN / (r.std() * np.sqrt(ANN) + 1e-12)) if len(r) > 8 else np.nan


def cagr(r: pd.Series) -> float:
    r = r.dropna()
    return float(np.expm1(r.mean() * ANN)) if len(r) > 8 else np.nan


def maxdd(r: pd.Series) -> float:
    r = r.dropna()
    if len(r) < 8:
        return np.nan
    cum = r.cumsum()
    return float(np.expm1((cum - cum.cummax()).min()))


def window_dd(r: pd.Series, a: str, b: str) -> float:
    s = r[(r.index >= a) & (r.index <= b)].dropna()
    if len(s) < 3:
        return np.nan
    c = s.cumsum()
    return float(np.expm1((c - c.cummax()).min()))


def build_config4_g05_with_events(df: pd.DataFrame):
    """Config-4+G-05 backtest, exposing per-rebalance-event traded-name/notional/ADV detail
    (needed for PORT-003) alongside the weekly net return series (needed for PORT-001/002)."""
    dates = sorted(df["date"].unique())
    reg = build_regimes(df)
    d2 = df.copy()
    d2["lowbeta"] = -pd.to_numeric(d2["beta_104w"], errors="coerce")
    lbook, sbook = set(), set()
    net = {}
    events = []  # one dict per rebalance date: {date, traded: [(ticker, adv_inr), ...], n_long, n_short}
    for i, d in enumerate(dates):
        g = d2[d2["date"] == d]
        adv = dict(zip(g["ticker"], pd.to_numeric(g["adv_13w"], errors="coerce")))
        m = float(pd.to_numeric(g["target_1w"], errors="coerce").mean())
        lr = pd.to_numeric(g[g["ticker"].isin(lbook)]["target_1w"], errors="coerce").dropna()
        long_ret = float(lr.mean()) if len(lr) else m
        sr = pd.to_numeric(g[g["ticker"].isin(sbook)]["target_1w"], errors="coerce").dropna()
        short_ret = (-float(sr.mean()) - SHORT_COST_WK) if len(sr) else 0.0
        cost = 0.0
        if i % 4 == 0:
            gg = g.dropna(subset=["composite"])
            if len(gg) >= 50:
                if reg.get(d) == "CRASH":
                    newl = set(gg.sort_values("lowbeta", ascending=False)
                                 .head(int(len(gg) * 0.2))["ticker"])
                else:
                    newl = M.long_secbal(gg)
                ext = gg["composite"].quantile(0.4)
                newl = (set(gg[gg["composite"] >= ext]["ticker"]) & lbook) | newl

                nL = max(len(newl), 1)
                traded_long = newl.symmetric_difference(lbook)
                cost += M.trade_cost_fraction(traded_long, 1e9 / nL, adv) if hasattr(M, "trade_cost_fraction") else 0.0
                lbook = newl
                news = M.short_q1(gg)
                nS = max(len(news), 1)
                traded_short = news.symmetric_difference(sbook)
                sbook = news

                events.append(dict(
                    date=d, n_long=nL, n_short=nS,
                    long_traded=[(tk, adv.get(tk, np.nan)) for tk in traded_long],
                    short_traded=[(tk, adv.get(tk, np.nan)) for tk in traded_short],
                ))
        net[d] = long_ret + 0.5 * short_ret - cost
    return pd.Series(net).sort_index(), events


def apply_leverage_overlay(base: pd.Series, events_dates: set, leverage_series: pd.Series) -> pd.Series:
    """Apply a leverage multiplier (only re-set on rebalance dates, held constant between) to the
    baseline return series, charging the disclosed incremental cost for each leverage change."""
    out = {}
    prev_L = 1.0
    L_hold = 1.0
    for d, r in base.items():
        if d in events_dates and d in leverage_series.index:
            L_new = float(leverage_series.loc[d])
            chg_cost = abs(L_new - L_hold) * (LEVERAGE_CHANGE_COST_BPS / 1e4)
            L_hold = L_new
            out[d] = L_hold * r - chg_cost
        else:
            out[d] = L_hold * r
    return pd.Series(out).sort_index()


def run_port001(base: pd.Series, events_dates: set) -> dict:
    print("\n" + "-" * 100 + "\nPORT-001 -- Volatility-targeting overlay\n" + "-" * 100)
    pre = base[base.index < LOCK]
    target_vol = float(pre.std(ddof=1) * np.sqrt(ANN))
    # shift(1): trailing vol at date d must use only returns through d-1, not r(d) itself
    # (self-caught PIT leak -- rolling().std() on the unshifted series includes today's own return)
    trail_vol = base.shift(1).rolling(13, min_periods=8).std() * np.sqrt(ANN)
    lev = (target_vol / trail_vol).clip(LEV_MIN, LEV_MAX).fillna(1.0)
    overlay = apply_leverage_overlay(base, events_dates, lev)

    m_base_pre = dict(cagr=cagr(base[base.index < LOCK]), sharpe=sharpe(base[base.index < LOCK]),
                      maxdd=maxdd(base[base.index < LOCK]))
    m_over_pre = dict(cagr=cagr(overlay[overlay.index < LOCK]), sharpe=sharpe(overlay[overlay.index < LOCK]),
                      maxdd=maxdd(overlay[overlay.index < LOCK]))
    m_base_lock = dict(cagr=cagr(base[base.index >= LOCK]), sharpe=sharpe(base[base.index >= LOCK]),
                       maxdd=maxdd(base[base.index >= LOCK]))
    m_over_lock = dict(cagr=cagr(overlay[overlay.index >= LOCK]), sharpe=sharpe(overlay[overlay.index >= LOCK]),
                       maxdd=maxdd(overlay[overlay.index >= LOCK]))

    sharpe_delta = m_over_pre["sharpe"] - m_base_pre["sharpe"]
    verdict = ("VALIDATED" if sharpe_delta >= GEN5_BAR else
              "INCONCLUSIVE" if abs(sharpe_delta) < 0.02 else "REJECTED")
    print(f"target vol (pre-lockbox) = {target_vol:.1%}")
    print(f"pre-lockbox : base Sharpe {m_base_pre['sharpe']:+.3f} maxDD {m_base_pre['maxdd']:+.1%}  "
          f"| overlay Sharpe {m_over_pre['sharpe']:+.3f} maxDD {m_over_pre['maxdd']:+.1%}  "
          f"| delta {sharpe_delta:+.3f}")
    print(f"lockbox ctx : base Sharpe {m_base_lock['sharpe']:+.3f}  "
          f"| overlay Sharpe {m_over_lock['sharpe']:+.3f}")
    print(f"VERDICT: {verdict}")
    return dict(target_vol=target_vol, pre_lockbox=dict(base=m_base_pre, overlay=m_over_pre, sharpe_delta=sharpe_delta),
               lockbox_context=dict(base=m_base_lock, overlay=m_over_lock), verdict=verdict)


def run_port002(base: pd.Series, events_dates: set) -> dict:
    print("\n" + "-" * 100 + "\nPORT-002 -- Drawdown-triggered de-gross overlay\n" + "-" * 100)
    # shift(1): drawdown state at date d must reflect cumulative return through d-1, not r(d) itself
    # (same self-caught PIT leak as PORT-001 -- see note there)
    cum = base.shift(1).fillna(0.0).cumsum()
    running_peak = cum.cummax()
    dd = np.expm1(cum - running_peak)

    lev_vals = {}
    state = 1.0  # 1.0 = full gross, DEGROSS_MULT = de-grossed
    for d in base.index:
        if state == 1.0 and dd.loc[d] <= DD_TRIGGER:
            state = DEGROSS_MULT
        elif state == DEGROSS_MULT and dd.loc[d] >= DD_RESTORE:
            state = 1.0
        lev_vals[d] = state
    lev = pd.Series(lev_vals)
    lev_at_events = lev.reindex(sorted(events_dates)).ffill()
    overlay = apply_leverage_overlay(base, events_dates, lev_at_events)

    m_base_pre = dict(cagr=cagr(base[base.index < LOCK]), sharpe=sharpe(base[base.index < LOCK]),
                      maxdd=maxdd(base[base.index < LOCK]),
                      gfc=window_dd(base, "2008-01-01", "2009-06-30"),
                      covid=window_dd(base, "2020-02-01", "2020-06-30"))
    m_over_pre = dict(cagr=cagr(overlay[overlay.index < LOCK]), sharpe=sharpe(overlay[overlay.index < LOCK]),
                      maxdd=maxdd(overlay[overlay.index < LOCK]),
                      gfc=window_dd(overlay, "2008-01-01", "2009-06-30"),
                      covid=window_dd(overlay, "2020-02-01", "2020-06-30"))

    dd_improvement = m_over_pre["maxdd"] - m_base_pre["maxdd"]
    cagr_cost = m_base_pre["cagr"] - m_over_pre["cagr"]
    favorable = dd_improvement > 0.02 and cagr_cost < 0.03
    verdict = "VALIDATED" if favorable else ("REJECTED" if dd_improvement <= 0.005 else "INCONCLUSIVE")
    print(f"pre-lockbox : base maxDD {m_base_pre['maxdd']:+.1%} (GFC {m_base_pre['gfc']:+.1%}, "
          f"COVID {m_base_pre['covid']:+.1%})  CAGR {m_base_pre['cagr']:+.1%}  Sharpe {m_base_pre['sharpe']:+.3f}")
    print(f"            | overlay maxDD {m_over_pre['maxdd']:+.1%} (GFC {m_over_pre['gfc']:+.1%}, "
          f"COVID {m_over_pre['covid']:+.1%})  CAGR {m_over_pre['cagr']:+.1%}  Sharpe {m_over_pre['sharpe']:+.3f}")
    print(f"maxDD improvement: {dd_improvement:+.1%}  |  CAGR cost: {cagr_cost:+.1%}")
    print(f"VERDICT: {verdict}")
    return dict(base=m_base_pre, overlay=m_over_pre, maxdd_improvement=dd_improvement,
               cagr_cost=cagr_cost, verdict=verdict)


def run_port003(events: list) -> dict:
    print("\n" + "-" * 100 + "\nPORT-003 -- Execution-schedule refinement at Rs2500cr\n" + "-" * 100)
    fund_inr = CAPITAL_TEST_CR * 1e7
    single_total, staggered_total, n_names_total = 0.0, 0.0, 0
    for ev in events:
        # short leg is sized at 0.5x the long gross, matching Config-4's own short_ratio -- its
        # per-name notional must be scaled down accordingly, not given the full fund_inr like the
        # long leg (self-caught: first pass gave the short leg 2x its real notional).
        for side_list, n_names, gross_weight in [
            (ev["long_traded"], ev["n_long"], 1.0), (ev["short_traded"], ev["n_short"], 0.5)]:
            notional_full = gross_weight * fund_inr / max(n_names, 1)
            for tk, adv in side_list:
                adv_v = float(adv) if pd.notna(adv) else None
                n_names_total += 1
                # single-shot: one BUY + one SELL at full notional
                single_total += (CM.cost_breakdown("BUY", notional_full, adv_inr=adv_v).total
                                 + CM.cost_breakdown("SELL", notional_full, adv_inr=adv_v).total)
                # 5-day staggered: split notional into N_TRANCHES, each tranche its own BUY+SELL
                tranche = notional_full / N_TRANCHES
                for _ in range(N_TRANCHES):
                    staggered_total += (CM.cost_breakdown("BUY", tranche, adv_inr=adv_v).total
                                        + CM.cost_breakdown("SELL", tranche, adv_inr=adv_v).total)

    n_events = len(events)
    single_bps = single_total / fund_inr * 1e4 if fund_inr else np.nan
    staggered_bps = staggered_total / fund_inr * 1e4 if fund_inr else np.nan
    # actual elapsed span, not an assumed 12/yr cadence -- rebalances are every 4th WEEK (~13/yr)
    span_days = (events[-1]["date"] - events[0]["date"]).days if n_events > 1 else 365
    n_years = span_days / 365.25 if span_days else np.nan
    single_ann_bps = single_bps / n_years if n_years else np.nan
    staggered_ann_bps = staggered_bps / n_years if n_years else np.nan

    print(f"capital = Rs{CAPITAL_TEST_CR:.0f}cr, {n_events} rebalance events, {n_names_total} name-trades")
    print(f"single-shot execution   : {single_ann_bps:.1f} bps/yr total cost")
    print(f"5-day staggered execution: {staggered_ann_bps:.1f} bps/yr total cost")
    diff_bps = staggered_ann_bps - single_ann_bps
    verdict = "VALIDATED" if diff_bps < -5.0 else ("REJECTED" if diff_bps > 5.0 else "INCONCLUSIVE")
    print(f"difference (staggered - single): {diff_bps:+.1f} bps/yr")
    print(f"VERDICT: {verdict}")
    return dict(capital_cr=CAPITAL_TEST_CR, n_events=n_events, n_name_trades=n_names_total,
               single_shot_bps_per_yr=single_ann_bps, staggered_bps_per_yr=staggered_ann_bps,
               difference_bps_per_yr=diff_bps, verdict=verdict)


def main() -> int:
    print("=" * 100)
    print("PORT-001/002/003 -- FIRST PORTFOLIO ENGINEERING WORKSTREAMS ON THE FROZEN BOOK")
    print("=" * 100)

    df = M.load()
    n_weeks = df["date"].nunique()
    print(f"panel: {len(df):,} rows, {n_weeks} weeks, "
          f"{df['date'].min().date()}..{df['date'].max().date()}")
    print("baseline: Config-4 + G-05 (Sleeve-1, 80% of the frozen book) -- reusing "
          "run_final_portfolio_matrix.py's recertified apparatus\n")

    base, events = build_config4_g05_with_events(df)
    events_dates = {ev["date"] for ev in events}
    print(f"baseline pre-lockbox: CAGR {cagr(base[base.index < LOCK]):+.1%}  "
          f"Sharpe {sharpe(base[base.index < LOCK]):+.3f}  maxDD {maxdd(base[base.index < LOCK]):+.1%}")

    r1 = run_port001(base, events_dates)
    r2 = run_port002(base, events_dates)
    r3 = run_port003(events)

    all_results = dict(PORT_001=r1, PORT_002=r2, PORT_003=r3)
    (OUT / "port_001_002_003_data.json").write_text(json.dumps(all_results, indent=2, default=str))

    print("\n" + "=" * 100)
    print("SUMMARY")
    print(f"  PORT-001 (vol-targeting)      -> {r1['verdict']}")
    print(f"  PORT-002 (drawdown de-gross)  -> {r2['verdict']}")
    print(f"  PORT-003 (execution schedule) -> {r3['verdict']}")
    print("=" * 100)

    for exp_id, res in [("PORT-001", r1), ("PORT-002", r2), ("PORT-003", r3)]:
        close_experiment(exp_id, res["verdict"],
                         "labs/portfolio_engineering/results/PORT-001-002-003/FINDINGS.md")
    print(f"\nwrote {OUT / 'port_001_002_003_data.json'}; all three closed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
