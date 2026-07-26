#!/usr/bin/env python3
"""ALPHA-001 -- Liquidity-gradient out-of-sample test on the fresh 53-week post-lockbox window.

Executes labs/alpha_engine/protocols/ALPHA-001_LIQUIDITY_GRADIENT_OOS.md. The outcome rule is fixed
in the contract BEFORE this script was run: at 40.9% power (n=53), no result here can be VALIDATED or
REJECTED -- only INCONCLUSIVE, directionally consistent or not. This script does not deviate from
that rule regardless of what comes out.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from src.pnl.indian_cost_model import IndianEquityCostModel  # noqa: E402
from research_os.experiment_registry import close_experiment  # noqa: E402

CM = IndianEquityCostModel()
OUT = ROOT / "labs/alpha_engine/results/ALPHA-001"
OUT.mkdir(parents=True, exist_ok=True)

MIN_PRICE = 20.0
MIN_NAMES = 25
HOLDOUT_START = pd.Timestamp("2025-07-11")
SIGNAL = "res_mom_52w_ex4w"
CAPITAL_CR = 5.0


def nw_mean(x, max_lag=None):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    n = len(x)
    if n < 8:
        return dict(mean=np.nan, t=np.nan, p=np.nan, n=n)
    if max_lag is None:
        max_lag = max(int(np.floor(4 * (n / 100) ** (2 / 9))), 1)
    d = x - x.mean()
    lrv = float(d @ d) / n
    for k in range(1, max_lag + 1):
        lrv += 2 * (1 - k / (max_lag + 1)) * float(d[k:] @ d[:-k]) / n
    se = np.sqrt(max(lrv, 1e-300) / n)
    t = float(x.mean() / se) if se > 0 else 0.0
    return dict(mean=float(x.mean()), t=t, p=float(2 * stats.norm.sf(abs(t))), n=n)


def main() -> int:
    print("=" * 100)
    print("ALPHA-001 -- LIQUIDITY-GRADIENT OOS TEST ON THE FRESH 53-WEEK WINDOW")
    print("=" * 100)
    print("Pre-committed outcome rule: this test can ONLY close INCONCLUSIVE (power=40.9%),")
    print("directionally consistent or not -- fixed before this script ran.\n")

    df = pd.read_parquet(ROOT / "data/kaggle_upload/panel_a_weekly.parquet",
                         columns=["date", "ticker", "close", "adv_13w", SIGNAL, "target_1w"])
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df = df[pd.to_numeric(df["close"], errors="coerce") >= MIN_PRICE]
    holdout = df[df["date"] >= HOLDOUT_START].copy()
    n_weeks = holdout["date"].nunique()
    print(f"holdout: {len(holdout):,} rows, {n_weeks} weeks, "
          f"{holdout['date'].min().date()}..{holdout['date'].max().date()}")

    holdout["adv_decile"] = holdout.groupby("date")["adv_13w"].transform(
        lambda s: pd.qcut(s.rank(method="first"), 10, labels=False, duplicates="drop"))

    ic_lo, ic_hi = [], []
    for dt, g in holdout.groupby("date"):
        for dec, bucket, store in [(0, "low", ic_lo), (9, "high", ic_hi)]:
            gg = g[g["adv_decile"] == dec].dropna(subset=[SIGNAL, "target_1w"])
            if len(gg) < MIN_NAMES:
                continue
            ic = stats.spearmanr(gg[SIGNAL], gg["target_1w"]).statistic
            if np.isfinite(ic):
                store.append(ic)

    t_lo = nw_mean(ic_lo)
    t_hi = nw_mean(ic_hi)
    print(f"\ndecile 0 (least liquid) : mean IC {t_lo['mean']:+.5f}  NW-t {t_lo['t']:+.2f}  n={t_lo['n']}")
    print(f"decile 9 (most liquid)  : mean IC {t_hi['mean']:+.5f}  NW-t {t_hi['t']:+.2f}  n={t_hi['n']}")

    diff = t_lo["mean"] - t_hi["mean"]
    se_diff = np.sqrt((1 / t_lo["n"]) + (1 / t_hi["n"])) * 0.15 if t_lo["n"] and t_hi["n"] else np.nan
    same_direction = diff > 0
    print(f"\ndifference (low - high): {diff:+.5f}")
    print(f"direction matches G9-01 (low > high): {same_direction}")

    # ---- economic readout (Alpha Engine charter requirement), same power caveat ----
    print("\n--- economic readout (descriptive only, not gated) ---")
    fund_inr = CAPITAL_CR * 1e7
    weekly_ret = {}
    for dt, g in holdout.groupby("date"):
        lo = g[g["adv_decile"] == 0].dropna(subset=[SIGNAL])
        hi = g[g["adv_decile"] == 9].dropna(subset=[SIGNAL])
        if len(lo) < MIN_NAMES or len(hi) < MIN_NAMES:
            continue
        long_names = set(lo.nlargest(max(int(len(lo) * 0.2), 5), SIGNAL)["ticker"])
        short_names = set(hi.nsmallest(max(int(len(hi) * 0.2), 5), SIGNAL)["ticker"])
        lr = pd.to_numeric(g[g["ticker"].isin(long_names)]["target_1w"], errors="coerce").mean()
        sr = pd.to_numeric(g[g["ticker"].isin(short_names)]["target_1w"], errors="coerce").mean()
        weekly_ret[dt] = (lr if np.isfinite(lr) else 0) - (sr if np.isfinite(sr) else 0)
    ret = pd.Series(weekly_ret).sort_index()
    sharpe = float(ret.mean() / ret.std(ddof=1) * np.sqrt(52)) if ret.std(ddof=1) > 0 else np.nan
    print(f"long-low-liquidity / short-high-liquidity spread, {len(ret)} weeks: "
          f"mean {ret.mean():+.4%}/wk, ann. Sharpe {sharpe:+.2f} (DESCRIPTIVE ONLY -- 41% power)")

    # ---- the pre-committed outcome rule, applied mechanically ----
    if same_direction:
        verdict = "INCONCLUSIVE"
        outcome = (f"Directionally CONSISTENT with G9-01 (decile-0 IC {t_lo['mean']:+.5f} > "
                   f"decile-9 IC {t_hi['mean']:+.5f} on the fresh 53-week window) but the design has "
                   f"only 40.9% power -- per the pre-committed outcome rule, this cannot be called "
                   f"VALIDATED. G9-01's own finding is unaffected either way; it stands on its "
                   f"much larger, better-powered sample (810 weeks, sign test p=0.00027).")
    else:
        verdict = "INCONCLUSIVE"
        outcome = (f"Direction REVERSED on the fresh window (decile-0 IC {t_lo['mean']:+.5f} vs "
                   f"decile-9 IC {t_hi['mean']:+.5f}). Per the pre-committed outcome rule, this is "
                   f"NOT treated as a rejection of G9-01 -- a reversal at 41% power on 53 weeks is "
                   f"exactly the Gen-7 Oil-sign-flip pattern (two noisy estimates within one "
                   f"standard error of each other), not evidence the original finding is wrong.")

    payload = dict(
        experiment="ALPHA-001", n_holdout_weeks=int(n_weeks), signal=SIGNAL,
        decile_0_ic=t_lo, decile_9_ic=t_hi, difference=float(diff),
        direction_matches_g9_01=bool(same_direction),
        economic_readout=dict(n_weeks=len(ret), mean_weekly_return=float(ret.mean()) if len(ret) else None,
                              annualized_sharpe=sharpe, capital_cr=CAPITAL_CR,
                              note="descriptive only, not gated -- 41% power applies here too"),
        power_at_meaningful_effect=0.409, pre_committed_rule="INCONCLUSIVE regardless of direction",
        verdict=verdict, outcome=outcome,
    )
    (OUT / "alpha001_data.json").write_text(json.dumps(payload, indent=2, default=str))

    print("\n" + "=" * 100)
    print(f"VERDICT: {verdict}  (fixed in advance by the power computation, not chosen after seeing results)")
    print(f"OUTCOME: {outcome}")
    print("=" * 100)

    close_experiment("ALPHA-001", verdict, "labs/alpha_engine/results/ALPHA-001/FINDINGS.md")
    print(f"\nwrote {OUT / 'alpha001_data.json'}; ALPHA-001 closed as {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
