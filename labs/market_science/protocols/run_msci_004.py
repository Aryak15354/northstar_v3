#!/usr/bin/env python3
"""MSCI-004 -- volatility-regime-classification stability vs. forward IC of res_mom_52w_ex4w.

Executes labs/market_science/protocols/MSCI-004_REGIME_STABILITY.md. Reuses build_regimes() from
run_g02_regime.py verbatim (already-verified PIT regime classifier) and the same shared-methodology
validation MSCI-001/002/003 used (NW HAC + circular block permutation + power precheck + rolling-
window artifact check) -- no Sharpe validation anywhere, per this lab's charter.
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
sys.path.insert(0, str(ROOT / "scripts/kaggle/plan_2026_05_18_production"))

from run_g02_regime import build_regimes  # noqa: E402
from research_os.power_precheck import power_precheck  # noqa: E402
from research_os.valid_pvalue import permutation_pvalue  # noqa: E402
from research_os.rolling_window_artifact_check import rolling_window_artifact_check  # noqa: E402
from research_os.experiment_registry import close_experiment  # noqa: E402

OUT = ROOT / "labs/market_science/results/MSCI-004"
OUT.mkdir(parents=True, exist_ok=True)

MIN_PRICE = 20.0
MIN_NAMES = 25
HORIZON = 13
STABILITY_WINDOW = 52
MEANINGFUL_R = 0.15
N_PERM = 4000
SEED = 42


def nw_hac_beta(y: np.ndarray, x: np.ndarray, max_lag: int) -> dict:
    y = np.asarray(y, float); x = np.asarray(x, float)
    m = np.isfinite(y) & np.isfinite(x)
    y, x = y[m], x[m]
    n = len(y)
    if n < 20:
        return dict(n=n, beta=np.nan, t=np.nan, p=np.nan, r=np.nan)
    X = np.column_stack([np.ones(n), x])
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    resid = y - X @ beta
    u = X * resid[:, None]
    S = u.T @ u
    for lag in range(1, max_lag + 1):
        w = 1 - lag / (max_lag + 1)
        Gamma = u[lag:].T @ u[:-lag]
        S += w * (Gamma + Gamma.T)
    V = XtX_inv @ S @ XtX_inv
    se = float(np.sqrt(max(V[1, 1], 0)))
    t = float(beta[1] / se) if se > 0 else 0.0
    p = float(2 * stats.norm.sf(abs(t)))
    r = float(np.corrcoef(x, y)[0, 1])
    return dict(n=n, beta=float(beta[1]), t=t, p=p, r=r)


def circular_block_perm_pvalue(y: np.ndarray, x: np.ndarray, observed_r: float,
                               block: int, n_perm: int = N_PERM, seed: int = SEED) -> dict:
    rng = np.random.default_rng(seed)
    m = np.isfinite(y) & np.isfinite(x)
    y, x = y[m], x[m]
    n = len(x)
    draws = np.empty(n_perm)
    for i in range(n_perm):
        shift = int(rng.integers(block, n - block)) if n > 2 * block else int(rng.integers(1, n))
        draws[i] = np.corrcoef(np.roll(x, shift), y)[0, 1]
    n_ge = int(np.sum(np.abs(draws) >= abs(observed_r)))
    return dict(n_perm=n_perm, block=block, p_value=permutation_pvalue(n_ge, n_perm))


def main() -> int:
    print("=" * 100)
    print("MSCI-004 -- VOLATILITY-REGIME STABILITY vs FORWARD IC (res_mom_52w_ex4w)")
    print("=" * 100)

    cols = ["date", "ticker", "close", "res_mom_52w_ex4w", "target_1w"]
    df = pd.read_parquet(ROOT / "data/kaggle_upload/panel_a_weekly.parquet", columns=cols)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df = df[pd.to_numeric(df["close"], errors="coerce") >= MIN_PRICE].copy()
    dates = sorted(df["date"].unique())
    print(f"panel: {len(df):,} rows, {len(dates)} weeks, "
         f"{df['date'].min().date()}..{df['date'].max().date()}")

    print("\nBuilding regime classification (reused verbatim from run_g02_regime.build_regimes) ...")
    regimes = build_regimes(df).sort_index()
    print(f"regime label counts:\n{regimes.value_counts()}")

    # trailing 52w regime stability = 1 - (fraction of week-over-week label changes in the window)
    changed = (regimes != regimes.shift(1)).astype(float)
    stability_trailing = 1.0 - changed.rolling(STABILITY_WINDOW, min_periods=STABILITY_WINDOW // 2).mean()

    print("Building forward-13w IC of res_mom_52w_ex4w (same construction as MSCI-001) ...")
    per_week_ic = {}
    for dt, g in df.groupby("date"):
        gg = g.dropna(subset=["res_mom_52w_ex4w", "target_1w"])
        if len(gg) < MIN_NAMES:
            continue
        r = stats.spearmanr(gg["res_mom_52w_ex4w"], gg["target_1w"]).statistic
        per_week_ic[dt] = float(r) if np.isfinite(r) else np.nan
    ic = pd.Series(per_week_ic).sort_index()
    idx = list(ic.index)
    fwd = {}
    for i, dt in enumerate(idx):
        window = ic.iloc[i + 1: i + 1 + HORIZON]
        if window.notna().sum() >= HORIZON // 2:
            fwd[dt] = float(window.mean())
    fwd_ic = pd.Series(fwd).sort_index()

    joined = pd.DataFrame({"p": stability_trailing, "f": fwd_ic}).dropna()
    n = len(joined)
    print(f"\njoined series length: {n} weeks ({joined.index.min().date()}..{joined.index.max().date()})")

    n_eff = max(int(n // HORIZON), 8)
    power = power_precheck(
        experiment="MSCI-004", n=n_eff, meaningful_effect=MEANINGFUL_R,
        test_design=f"trailing regime-stability (W={STABILITY_WINDOW}) vs forward-{HORIZON}w IC, "
                    f"NW HAC + circular block permutation; n_eff = non-overlapping {HORIZON}w blocks",
        allow_underpowered=True, verbose=True)

    x = joined["p"].to_numpy(); y = joined["f"].to_numpy()
    hac = nw_hac_beta(y, x, max_lag=max(STABILITY_WINDOW, HORIZON))
    perm = circular_block_perm_pvalue(y, x, hac["r"], block=max(STABILITY_WINDOW, HORIZON))
    artifact = rolling_window_artifact_check(
        joined["p"].to_numpy(), window=STABILITY_WINDOW, name="MSCI-004_regime_stability", verbose=True)

    direction_supported = hac["r"] < 0  # primary hypothesis: higher stability -> LOWER forward IC
    ci_excludes_zero = perm["p_value"] < 0.05
    adequately_powered = power.adequately_powered

    if not adequately_powered:
        verdict = "INCONCLUSIVE"
    elif not direction_supported:
        verdict = "REJECTED"
    elif not ci_excludes_zero:
        verdict = "INCONCLUSIVE"
    else:
        verdict = "VALIDATED"

    print(f"\nPearson r={hac['r']:+.4f}  NW t={hac['t']:+.2f}  NW p={hac['p']:.4f}  "
         f"perm p={perm['p_value']:.4f}")
    print(f"direction (r<0, matching MSCI-001's reversed-sign pattern): {direction_supported}")
    print(f"VERDICT: {verdict}")

    payload = dict(
        experiment="MSCI-004", n_weeks=n, n_eff_blocks=n_eff, predictor_window=STABILITY_WINDOW,
        horizon=HORIZON, pearson_r=hac["r"], nw_t=hac["t"], nw_p=hac["p"], permutation=perm,
        power=dict(n=power.n, meaningful_effect=power.meaningful_effect,
                  min_detectable_effect=power.min_detectable_effect,
                  power_at_meaningful_effect=power.power_at_meaningful_effect,
                  adequately_powered=power.adequately_powered,
                  required_n_for_meaningful_effect=power.required_n_for_meaningful_effect),
        rolling_window_artifact_check=dict(
            verdict=artifact.verdict, n_lags_exceeding_null=artifact.n_lags_exceeding_null,
            max_excess_over_null=artifact.max_excess_over_null,
            survives_differencing=artifact.survives_differencing,
            caveat="Gen-8 correction: differencing is a one-way conservative screen, not a clean "
                  "discriminator -- a highly persistent series can legitimately fail it."),
        direction_supported=direction_supported, ci_excludes_zero=ci_excludes_zero, verdict=verdict,
    )
    (OUT / "msci004_data.json").write_text(json.dumps(payload, indent=2, default=str))
    close_experiment("MSCI-004", verdict, "labs/market_science/results/MSCI-004/FINDINGS.md")
    print(f"\nwrote {OUT / 'msci004_data.json'}; MSCI-004 closed as {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
