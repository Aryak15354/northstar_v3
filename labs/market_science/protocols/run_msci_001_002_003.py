#!/usr/bin/env python3
"""MSCI-001/002/003 -- MSRP descriptive-to-predictive escalation.

Executes labs/market_science/protocols/MSCI_001_002_003_PREDICTIVE_ESCALATION.md. Three
independent, pre-registered forecasting tests, all walk-forward/PIT-safe, all validated by
Newey-West HAC + permutation-null + power precheck -- NEVER by Sharpe, per this lab's charter.
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
from research_os.valid_pvalue import permutation_pvalue  # noqa: E402
from research_os.rolling_window_artifact_check import rolling_window_artifact_check  # noqa: E402
from research_os.experiment_registry import register_experiment, close_experiment  # noqa: E402

OUT = ROOT / "labs/market_science/results/MSCI-001-002-003"
OUT.mkdir(parents=True, exist_ok=True)

MIN_PRICE = 20.0
MIN_NAMES = 25
HORIZON = 13
STABILITY_WINDOW = 52
INTERACTION_WINDOW = 104
REDUNDANCY_WINDOW = 52
MEANINGFUL_R = 0.15
N_PERM = 4000
SEED = 42

MOM_FAMILY = ["res_mom_52w_ex4w", "ret_52w_ex4w", "sharpe_mom_26w", "consistency_mom_26w"]
VOL_FAMILY = ["vol_13w", "vol_52w", "beta_104w", "idio_vol_13w"]


def zscore(s: pd.Series) -> pd.Series:
    sd = s.std(ddof=0)
    return (s - s.mean()) / sd if sd and np.isfinite(sd) and sd > 0 else s * np.nan


def weekly_ic(g: pd.DataFrame, x: str, y: str = "target_1w") -> float:
    gg = g.dropna(subset=[x, y])
    if len(gg) < MIN_NAMES:
        return np.nan
    r = stats.spearmanr(gg[x], gg[y]).statistic
    return float(r) if np.isfinite(r) else np.nan


def nw_hac_beta(y: np.ndarray, x: np.ndarray, max_lag: int):
    """Simple OLS of y on x with a Newey-West HAC t-stat on the slope."""
    y = np.asarray(y, float); x = np.asarray(x, float)
    m = np.isfinite(y) & np.isfinite(x)
    y, x = y[m], x[m]
    n = len(y)
    if n < 20:
        return dict(n=n, beta=np.nan, se=np.nan, t=np.nan, p=np.nan, r=np.nan)
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
    return dict(n=n, beta=float(beta[1]), se=se, t=t, p=p, r=r)


def circular_block_perm_pvalue(y: np.ndarray, x: np.ndarray, observed_r: float,
                                block: int, n_perm: int = N_PERM, seed: int = SEED) -> dict:
    """Circular block-shift permutation null for the Pearson correlation. Blocks preserve x's own
    autocorrelation structure while breaking any true alignment with y."""
    rng = np.random.default_rng(seed)
    m = np.isfinite(y) & np.isfinite(x)
    y, x = y[m], x[m]
    n = len(x)
    draws = np.empty(n_perm)
    for i in range(n_perm):
        shift = int(rng.integers(block, n - block)) if n > 2 * block else int(rng.integers(1, n))
        xs = np.roll(x, shift)
        draws[i] = np.corrcoef(xs, y)[0, 1]
    n_ge = int(np.sum(np.abs(draws) >= abs(observed_r)))
    p = permutation_pvalue(n_ge, n_perm)
    return dict(n_perm=n_perm, block=block, null_mean=float(np.nanmean(draws)),
                null_sd=float(np.nanstd(draws)), n_ge=n_ge, p_value=p)


def build_forward_ic(df: pd.DataFrame, dates: list, signal_cols) -> dict:
    """forward-13w mean IC of a single signal, or of the equal-weight z-score composite of several,
    keyed by date -- computed once and reused across hypotheses that share an outcome."""
    if isinstance(signal_cols, str):
        signal_cols = [signal_cols]
    per_week = {}
    for dt, g in df.groupby("date"):
        if len(signal_cols) == 1:
            per_week[dt] = weekly_ic(g, signal_cols[0])
        else:
            gg = g.dropna(subset=signal_cols + ["target_1w"])
            if len(gg) < MIN_NAMES:
                per_week[dt] = np.nan
                continue
            comp = sum(zscore(gg[c]) for c in signal_cols) / len(signal_cols)
            r = stats.spearmanr(comp, gg["target_1w"]).statistic
            per_week[dt] = float(r) if np.isfinite(r) else np.nan
    ic = pd.Series(per_week).sort_index()
    fwd = {}
    idx = list(ic.index)
    for i, dt in enumerate(idx):
        window = ic.iloc[i + 1: i + 1 + HORIZON]
        if window.notna().sum() >= HORIZON // 2:
            fwd[dt] = float(window.mean())
    return ic, pd.Series(fwd).sort_index()


def run_hypothesis(exp_id: str, name: str, predictor: pd.Series, outcome: pd.Series,
                    predictor_window: int, primary_direction: str) -> dict:
    joined = pd.DataFrame({"p": predictor, "f": outcome}).dropna()
    n = len(joined)
    print(f"\n{'-'*100}\n{exp_id} -- {name}\n{'-'*100}")
    print(f"joined series length: {n} weeks "
          f"({joined.index.min().date()}..{joined.index.max().date()})")

    n_eff = max(int(n // HORIZON), 8)
    power = power_precheck(
        experiment=exp_id, n=n_eff, meaningful_effect=MEANINGFUL_R,
        test_design=f"trailing predictor (W={predictor_window}) vs forward-{HORIZON}w IC, "
                    f"NW HAC + circular block permutation; n_eff = non-overlapping {HORIZON}w blocks",
        allow_underpowered=True, verbose=True)

    x = joined["p"].to_numpy(); y = joined["f"].to_numpy()
    hac = nw_hac_beta(y, x, max_lag=max(predictor_window, HORIZON))
    perm = circular_block_perm_pvalue(y, x, hac["r"], block=max(predictor_window, HORIZON))

    artifact = rolling_window_artifact_check(
        joined["p"].to_numpy(), window=predictor_window, name=f"{exp_id}_predictor", verbose=True)

    if primary_direction == "positive":
        direction_supported = hac["r"] > 0
    else:
        direction_supported = hac["r"] < 0
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

    result = dict(
        experiment=exp_id, name=name, n_weeks=n, n_eff_blocks=n_eff,
        predictor_window=predictor_window, horizon=HORIZON,
        pearson_r=hac["r"], nw_beta=hac["beta"], nw_t=hac["t"], nw_p=hac["p"],
        permutation=perm, power=dict(
            n=power.n, meaningful_effect=power.meaningful_effect,
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
        direction_supported=direction_supported, ci_excludes_zero=ci_excludes_zero,
        verdict=verdict,
    )
    print(f"\nPearson r={hac['r']:+.4f}  NW t={hac['t']:+.2f}  NW p={hac['p']:.4f}  "
          f"perm p={perm['p_value']:.4f}")
    print(f"VERDICT: {verdict}")
    return result


def main() -> int:
    print("=" * 100)
    print("MSCI-001/002/003 -- MSRP DESCRIPTIVE-TO-PREDICTIVE ESCALATION")
    print("=" * 100)

    cols = ["date", "ticker", "close"] + MOM_FAMILY + VOL_FAMILY + ["target_1w"]
    df = pd.read_parquet(ROOT / "data/kaggle_upload/panel_a_weekly.parquet", columns=cols)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df = df[pd.to_numeric(df["close"], errors="coerce") >= MIN_PRICE].copy()
    dates = sorted(df["date"].unique())
    print(f"panel: {len(df):,} rows, {len(dates)} weeks, "
          f"{df['date'].min().date()}..{df['date'].max().date()}")

    all_results = {}

    # ================================================================================
    # MSCI-001: trailing rank-stability of res_mom_52w_ex4w -> forward IC of the same signal
    # ================================================================================
    print("\nBuilding rank-stability predictor for MSCI-001 ...")
    df_sorted = df.sort_values("date")
    weekly_stability = {}
    prev = None
    for dt, g in df_sorted.groupby("date"):
        cur = g.set_index("ticker")["res_mom_52w_ex4w"].dropna()
        if prev is not None:
            common = cur.index.intersection(prev.index)
            if len(common) >= MIN_NAMES:
                r = stats.spearmanr(cur.loc[common], prev.loc[common]).statistic
                weekly_stability[dt] = float(r) if np.isfinite(r) else np.nan
        prev = cur
    stability_raw = pd.Series(weekly_stability).sort_index()
    stability_trailing = stability_raw.rolling(STABILITY_WINDOW, min_periods=STABILITY_WINDOW // 2).mean()

    ic_mom, fwd_ic_mom = build_forward_ic(df, dates, "res_mom_52w_ex4w")
    r1 = run_hypothesis("MSCI-001", "Primitive stability predicts future IC",
                        stability_trailing, fwd_ic_mom, STABILITY_WINDOW, primary_direction="positive")
    all_results["MSCI-001"] = r1

    # ================================================================================
    # MSCI-002: trailing interaction complexity (consistency_mom_26w x res_mom_52w_ex4w)
    #           -> forward IC decay of res_mom_52w_ex4w
    # ================================================================================
    print("\nBuilding interaction-complexity predictor for MSCI-002 ...")
    weekly_incremental = {}
    for dt, g in df.groupby("date"):
        gg = g.dropna(subset=["res_mom_52w_ex4w", "consistency_mom_26w", "target_1w"])
        if len(gg) < MIN_NAMES:
            continue
        ic_alone = weekly_ic(gg, "res_mom_52w_ex4w")
        interact = zscore(gg["res_mom_52w_ex4w"]) * zscore(gg["consistency_mom_26w"])
        r = stats.spearmanr(interact, gg["target_1w"]).statistic
        ic_interact = float(r) if np.isfinite(r) else np.nan
        if np.isfinite(ic_alone) and np.isfinite(ic_interact):
            weekly_incremental[dt] = ic_interact - ic_alone
    incremental_raw = pd.Series(weekly_incremental).sort_index()
    incremental_trailing = incremental_raw.rolling(
        INTERACTION_WINDOW, min_periods=INTERACTION_WINDOW // 2).mean()

    r2 = run_hypothesis("MSCI-002", "Interaction complexity predicts factor decay",
                        incremental_trailing, fwd_ic_mom, INTERACTION_WINDOW,
                        primary_direction="negative")
    all_results["MSCI-002"] = r2

    # ================================================================================
    # MSCI-003: trailing cross-family redundancy (momentum <-> volatility) -> forward IC
    #           of the momentum composite
    # ================================================================================
    print("\nBuilding cross-family redundancy predictor for MSCI-003 ...")
    weekly_redundancy = {}
    for dt, g in df.groupby("date"):
        gg = g.dropna(subset=MOM_FAMILY + VOL_FAMILY)
        if len(gg) < MIN_NAMES:
            continue
        zmom = {c: zscore(gg[c]) for c in MOM_FAMILY}
        zvol = {c: zscore(gg[c]) for c in VOL_FAMILY}
        corrs = []
        for cm in MOM_FAMILY:
            for cv in VOL_FAMILY:
                c = np.corrcoef(zmom[cm], zvol[cv])[0, 1]
                if np.isfinite(c):
                    corrs.append(abs(c))
        if corrs:
            weekly_redundancy[dt] = float(np.mean(corrs))
    redundancy_raw = pd.Series(weekly_redundancy).sort_index()
    redundancy_trailing = redundancy_raw.rolling(
        REDUNDANCY_WINDOW, min_periods=REDUNDANCY_WINDOW // 2).mean()

    ic_composite, fwd_ic_composite = build_forward_ic(df, dates, MOM_FAMILY)
    r3 = run_hypothesis("MSCI-003", "Structural redundancy forecasts crowding",
                        redundancy_trailing, fwd_ic_composite, REDUNDANCY_WINDOW,
                        primary_direction="negative")
    all_results["MSCI-003"] = r3

    # ================================================================================
    (OUT / "msci_001_002_003_data.json").write_text(json.dumps(all_results, indent=2, default=str))
    print("\n" + "=" * 100)
    print("SUMMARY")
    for k, v in all_results.items():
        print(f"  {k}: r={v['pearson_r']:+.4f}  NW p={v['nw_p']:.4f}  perm p={v['permutation']['p_value']:.4f}  "
              f"power={v['power']['power_at_meaningful_effect']:.1%}  -> {v['verdict']}")
    print("=" * 100)

    for exp_id in ["MSCI-001", "MSCI-002", "MSCI-003"]:
        close_experiment(exp_id, all_results[exp_id]["verdict"],
                         "labs/market_science/results/MSCI-001-002-003/FINDINGS.md")
    print(f"\nwrote {OUT / 'msci_001_002_003_data.json'}; all three closed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
