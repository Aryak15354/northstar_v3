#!/usr/bin/env python3
"""ALPHA-002 -- Is Delivery the same mechanism as the liquidity-decile gradient?

Executes labs/alpha_engine/protocols/ALPHA-002_DELIVERY_LIQUIDITY_OVERLAP.md. Joint with Portfolio
Engineering (see contract SS5) -- registered under Alpha Engine since it resolves whether a claimed
edge is genuinely distinct, cross-referenced (not duplicated) in Portfolio Engineering's decision log.
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

from research_os.power_precheck import power_precheck  # noqa: E402
from research_os.experiment_registry import close_experiment  # noqa: E402

OUT = ROOT / "labs/alpha_engine/results/ALPHA-002"
OUT.mkdir(parents=True, exist_ok=True)

MIN_PRICE = 20.0
MIN_NAMES = 25
MEANINGFUL_R = 0.03


def nw_mean(x, max_lag=None) -> dict:
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


def zscore(s: pd.Series) -> pd.Series:
    sd = s.std(ddof=0)
    return (s - s.mean()) / sd if sd and np.isfinite(sd) and sd > 0 else s * np.nan


def main() -> int:
    print("=" * 100)
    print("ALPHA-002 -- IS DELIVERY THE SAME MECHANISM AS THE LIQUIDITY-DECILE GRADIENT?")
    print("=" * 100)

    panel = pd.read_parquet(ROOT / "data/kaggle_upload/panel_a_weekly.parquet",
                            columns=["date", "ticker", "close", "adv_13w", "adv_rank_13w", "target_1w"])
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    panel["ticker"] = panel["ticker"].astype(str)
    panel = panel[pd.to_numeric(panel["close"], errors="coerce") >= MIN_PRICE]
    # fno_ok := adv_rank <= 190, exactly run_final_portfolio_matrix.py's own definition (the same
    # definition G9-01 showed the "non-F&O" tier actually was, 77.4% agreement with real membership).
    panel["fno_ok"] = pd.to_numeric(panel["adv_rank_13w"], errors="coerce") <= 190

    sm = pd.read_parquet(ROOT / "data/canonical/microstructure/stock_microstructure_weekly.parquet",
                         columns=["date", "ticker", "delivery_pct_4w_avg"])
    sm["date"] = pd.to_datetime(sm["date"]).dt.normalize()
    sm["ticker"] = sm["ticker"].astype(str)

    df = panel.merge(sm, on=["date", "ticker"], how="inner")
    df = df[(~df["fno_ok"].astype(bool)) & df["delivery_pct_4w_avg"].notna()]
    df = df.dropna(subset=["adv_13w", "target_1w"])
    df["log_adv"] = np.log(pd.to_numeric(df["adv_13w"], errors="coerce").clip(lower=1.0))

    n_weeks = df["date"].nunique()
    print(f"non-F&O, delivery-covered universe: {len(df):,} rows, {n_weeks} weeks "
          f"({df['date'].min().date()}..{df['date'].max().date()})")

    power = power_precheck(
        experiment="ALPHA-002", n=n_weeks, meaningful_effect=MEANINGFUL_R,
        test_design="weekly cross-sectional Spearman IC / OLS partial coefficient, "
                    "NW HAC across independent weekly draws",
        allow_underpowered=True, verbose=True)

    ic_deliv, ic_adv, ic_overlap, beta_deliv, beta_adv = [], [], [], [], []
    for dt, g in df.groupby("date"):
        if len(g) < MIN_NAMES:
            continue
        r_d = stats.spearmanr(g["delivery_pct_4w_avg"], g["target_1w"]).statistic
        r_a = stats.spearmanr(g["log_adv"], g["target_1w"]).statistic
        r_o = stats.spearmanr(g["delivery_pct_4w_avg"], g["log_adv"]).statistic
        if np.isfinite(r_d):
            ic_deliv.append(r_d)
        if np.isfinite(r_a):
            ic_adv.append(r_a)
        if np.isfinite(r_o):
            ic_overlap.append(r_o)

        zD = zscore(g["delivery_pct_4w_avg"]); zL = zscore(g["log_adv"])
        y = pd.to_numeric(g["target_1w"], errors="coerce")
        m = zD.notna() & zL.notna() & y.notna()
        if m.sum() < MIN_NAMES:
            continue
        X = np.column_stack([np.ones(m.sum()), zD[m].to_numpy(), zL[m].to_numpy()])
        yv = y[m].to_numpy()
        try:
            coef, *_ = np.linalg.lstsq(X, yv, rcond=None)
            beta_deliv.append(float(coef[1]))
            beta_adv.append(float(coef[2]))
        except np.linalg.LinAlgError:
            continue

    t_ic_deliv = nw_mean(ic_deliv)
    t_ic_adv = nw_mean(ic_adv)
    t_ic_overlap = nw_mean(ic_overlap)
    t_beta_deliv = nw_mean(beta_deliv)
    t_beta_adv = nw_mean(beta_adv)

    print(f"\nunivariate IC  delivery_pct_4w_avg vs target_1w : mean {t_ic_deliv['mean']:+.5f}  "
          f"NW-t {t_ic_deliv['t']:+.2f}  p {t_ic_deliv['p']:.4f}  n={t_ic_deliv['n']}")
    print(f"univariate IC  log(adv_13w) vs target_1w        : mean {t_ic_adv['mean']:+.5f}  "
          f"NW-t {t_ic_adv['t']:+.2f}  p {t_ic_adv['p']:.4f}  n={t_ic_adv['n']}")
    print(f"raw overlap    delivery vs log(adv_13w)          : mean {t_ic_overlap['mean']:+.5f}  "
          f"NW-t {t_ic_overlap['t']:+.2f}  p {t_ic_overlap['p']:.4f}  n={t_ic_overlap['n']}")
    print(f"\npartial coef   delivery (controlling for liquidity) : mean {t_beta_deliv['mean']:+.5f}  "
          f"NW-t {t_beta_deliv['t']:+.2f}  p {t_beta_deliv['p']:.4f}  n={t_beta_deliv['n']}")
    print(f"partial coef   liquidity (controlling for delivery) : mean {t_beta_adv['mean']:+.5f}  "
          f"NW-t {t_beta_adv['t']:+.2f}  p {t_beta_adv['p']:.4f}  n={t_beta_adv['n']}")

    ratio = abs(t_beta_deliv["mean"]) / abs(t_ic_deliv["mean"]) if t_ic_deliv["mean"] else np.nan
    print(f"\npartial/univariate magnitude ratio for delivery: {ratio:.2f}")

    adequately_powered = power.adequately_powered
    partial_significant = t_beta_deliv["p"] < 0.05 and np.isfinite(t_beta_deliv["p"])
    retains_magnitude = np.isfinite(ratio) and ratio >= 0.5

    if not adequately_powered:
        verdict = "INCONCLUSIVE"
        outcome = "Underpowered at the pre-registered effect size; no claim either way."
    elif partial_significant and retains_magnitude:
        verdict = "VALIDATED"
        outcome = ("Delivery's incremental IC survives controlling for liquidity (partial coefficient "
                   f"{t_beta_deliv['mean']:+.5f}, p={t_beta_deliv['p']:.4f}, retaining "
                   f"{ratio:.0%} of its univariate magnitude). Delivery and the liquidity-decile "
                   "gradient are separable mechanisms, not one edge under two names.")
    else:
        verdict = "REJECTED"
        outcome = ("Delivery's incremental IC does NOT survive controlling for liquidity "
                   f"(partial coefficient {t_beta_deliv['mean']:+.5f}, p={t_beta_deliv['p']:.4f}, "
                   f"retaining only {ratio:.0%} of its univariate magnitude, or losing significance). "
                   "Per the restructuring plan's own framing: Delivery and the liquidity-decile "
                   "gradient collapse into one explanatory variable in this universe -- report as "
                   "one mechanism, not two independent edges.")

    payload = dict(
        experiment="ALPHA-002", n_weeks=int(n_weeks),
        univariate_ic_delivery=t_ic_deliv, univariate_ic_liquidity=t_ic_adv,
        raw_overlap_delivery_vs_liquidity=t_ic_overlap,
        partial_coef_delivery=t_beta_deliv, partial_coef_liquidity=t_beta_adv,
        partial_to_univariate_ratio=float(ratio) if np.isfinite(ratio) else None,
        power=dict(n=power.n, meaningful_effect=power.meaningful_effect,
                  min_detectable_effect=power.min_detectable_effect,
                  power_at_meaningful_effect=power.power_at_meaningful_effect,
                  adequately_powered=power.adequately_powered),
        verdict=verdict, outcome=outcome,
    )
    (OUT / "alpha002_data.json").write_text(json.dumps(payload, indent=2, default=str))

    print("\n" + "=" * 100)
    print(f"VERDICT: {verdict}")
    print(f"OUTCOME: {outcome}")
    print("=" * 100)

    close_experiment("ALPHA-002", verdict, "labs/alpha_engine/results/ALPHA-002/FINDINGS.md")
    print(f"\nwrote {OUT / 'alpha002_data.json'}; ALPHA-002 closed as {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
