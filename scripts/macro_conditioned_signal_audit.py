#!/usr/bin/env python3
"""
Macro-conditioned signal IC audit.

Purpose:
1) Quantify unconditional IC for existing cross-sectional signals.
2) Quantify conditional IC by macro state terciles (G/I/L/S + MacroScore/TrueStress).
3) Test whether a regime-conditioned rolling composite improves IC over equal-weight composite.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd


PRICE_DIR = Path("data/raw/prices_daily")
BASE_MACRO_FACTORS_PATH = Path("data/macro/factors/macro_factors.parquet")
BASE_MACRO_SCORE_PATH = Path("data/macro/factors/macro_score.parquet")
MACRO_FACTORS_V2_PATH = Path("data/macro/factors/macro_factors_v2.parquet")
MACRO_SCORE_V2_PATH = Path("data/macro/factors/macro_score_v2.parquet")
DEFAULT_OUTPUT_DIR = Path("reports/signal_audit/macro_conditioned")

SIGNAL_COLS = [
    "signal_momentum_1m",
    "signal_momentum_3m",
    "signal_low_volatility",
    "signal_liquidity",
    "signal_reversal_5d",
]

CRASH_REGIMES = {"Crisis", "Slowdown"}
CRASH_PRIOR_WEIGHTS = {
    "signal_momentum_1m": -0.10,
    "signal_momentum_3m": -0.20,
    "signal_low_volatility": 0.45,
    "signal_liquidity": 0.05,
    "signal_reversal_5d": 0.35,
}
MACRO_FACTORS_PATH, MACRO_SCORE_PATH = BASE_MACRO_FACTORS_PATH, BASE_MACRO_SCORE_PATH


def _safe_corr(x: pd.Series, y: pd.Series) -> float:
    x_vals = x.to_numpy(dtype=float)
    y_vals = y.to_numpy(dtype=float)
    if len(x_vals) < 3:
        return np.nan
    x_centered = x_vals - np.nanmean(x_vals)
    y_centered = y_vals - np.nanmean(y_vals)
    denom = np.sqrt(np.nansum(x_centered ** 2) * np.nansum(y_centered ** 2))
    if not np.isfinite(denom) or denom <= 1e-12:
        return np.nan
    corr = np.nansum(x_centered * y_centered) / denom
    if not np.isfinite(corr):
        return np.nan
    return float(corr)


def _cross_sectional_zscore(df: pd.DataFrame, col: str, out_col: str) -> pd.DataFrame:
    df[out_col] = df.groupby("date")[col].transform(
        lambda x: (x - x.mean()) / (x.std() + 1e-12)
    )
    return df


def load_prices(price_dir: Path) -> pd.DataFrame:
    if not price_dir.exists():
        raise FileNotFoundError(f"Price directory not found: {price_dir}")

    parts: List[pd.DataFrame] = []
    files = sorted(price_dir.glob("*.csv"))
    if not files:
        raise RuntimeError(f"No CSV files found in {price_dir}")

    for csv_path in files:
        try:
            ticker = csv_path.stem
            df = pd.read_csv(csv_path, parse_dates=["Date"])
            df = df.rename(
                columns={
                    "Date": "date",
                    "Close": "price",
                    "Volume": "volume",
                }
            )
            if {"date", "price", "volume"} - set(df.columns):
                continue
            df = df[["date", "price", "volume"]].copy()
            df["asset_id"] = ticker
            df = df.dropna(subset=["date", "price"])
            parts.append(df)
        except Exception:
            continue

    if not parts:
        raise RuntimeError("Failed to load any price files")

    out = pd.concat(parts, ignore_index=True)
    out = out.sort_values(["asset_id", "date"]).reset_index(drop=True)
    return out


def compute_signals(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["asset_id", "date"]).copy()
    df["return"] = df.groupby("asset_id")["price"].transform(lambda x: np.log(x / x.shift(1)))

    df["signal_momentum_1m"] = df.groupby("asset_id")["return"].transform(
        lambda x: x.rolling(21, min_periods=10).sum()
    )
    df["signal_momentum_3m"] = df.groupby("asset_id")["return"].transform(
        lambda x: x.rolling(63, min_periods=30).sum()
    )
    df["signal_low_volatility"] = df.groupby("asset_id")["return"].transform(
        lambda x: -x.rolling(20, min_periods=10).std()
    )
    df["signal_liquidity"] = df.groupby("asset_id")["volume"].transform(
        lambda x: np.log(x.rolling(20, min_periods=10).mean() + 1.0)
    )
    df["signal_reversal_5d"] = df.groupby("asset_id")["return"].transform(
        lambda x: -x.rolling(5, min_periods=3).sum()
    )

    return df


def compute_target(df: pd.DataFrame, horizon: int) -> pd.DataFrame:
    df = df.sort_values(["asset_id", "date"]).copy()
    df["market_return_1d"] = df.groupby("date")["return"].transform("mean")
    df["cross_sectional_vol_1d"] = df.groupby("date")["return"].transform("std")
    df[f"forward_return_{horizon}d"] = df.groupby("asset_id")["return"].transform(
        lambda x: x.rolling(horizon).sum().shift(-horizon)
    )
    df["universe_mean_return"] = df.groupby("date")[f"forward_return_{horizon}d"].transform("mean")
    df["excess_return"] = df[f"forward_return_{horizon}d"] - df["universe_mean_return"]

    for signal in SIGNAL_COLS:
        df = _cross_sectional_zscore(df, signal, f"{signal}_z")

    keep = [
        "date",
        "asset_id",
        "excess_return",
        "market_return_1d",
        "cross_sectional_vol_1d",
    ] + [f"{s}_z" for s in SIGNAL_COLS]
    out = df[keep].dropna(subset=["excess_return"] + [f"{s}_z" for s in SIGNAL_COLS]).copy()
    return out


def _build_tercile_labels(series: pd.Series) -> pd.Series:
    valid = series.dropna()
    out = pd.Series(index=series.index, dtype="object")
    if len(valid) < 30:
        out.loc[valid.index] = "unknown"
        return out
    ranked = valid.rank(method="first")
    bins = pd.qcut(ranked, q=3, labels=["low", "mid", "high"])
    out.loc[valid.index] = bins.astype(str)
    return out


def load_macro_state(macro_factors_path: Path, macro_score_path: Path) -> pd.DataFrame:
    if not macro_factors_path.exists():
        raise FileNotFoundError(f"Missing macro factors: {macro_factors_path}")
    if not macro_score_path.exists():
        raise FileNotFoundError(f"Missing macro score: {macro_score_path}")

    mf = pd.read_parquet(macro_factors_path).copy()
    ms = pd.read_parquet(macro_score_path).copy()

    if not isinstance(mf.index, pd.DatetimeIndex):
        raise ValueError("macro_factors index must be DatetimeIndex")
    if not isinstance(ms.index, pd.DatetimeIndex):
        raise ValueError("macro_score index must be DatetimeIndex")

    mf = mf.rename_axis("date").reset_index()
    ms = ms.rename_axis("date").reset_index()
    macro = pd.merge(mf, ms[["date", "MacroScore", "Regime", "TrueStress"]], on="date", how="left")

    for col in ["G", "I", "L", "S", "MacroScore", "TrueStress"]:
        if col in macro.columns:
            macro[f"{col}_tercile"] = _build_tercile_labels(macro[col])

    macro = macro.sort_values("date").reset_index(drop=True)
    return macro


def merge_panel_with_macro(panel: pd.DataFrame, macro: pd.DataFrame) -> pd.DataFrame:
    left = panel.sort_values("date").reset_index(drop=True)
    right = macro.sort_values("date").reset_index(drop=True)
    merged = pd.merge_asof(left, right, on="date", direction="backward")
    merged = merged.dropna(subset=["Regime"]).copy()
    return merged


def daily_ic_series(panel: pd.DataFrame, signal_col: str) -> pd.Series:
    valid = panel[["date", signal_col, "excess_return"]].dropna()
    ic = valid.groupby("date")[[signal_col, "excess_return"]].apply(
        lambda g: _safe_corr(g[signal_col], g["excess_return"])
    )
    return ic.dropna()


def unconditional_signal_ic(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for signal in SIGNAL_COLS:
        s_col = f"{signal}_z"
        ic = daily_ic_series(panel, s_col)
        rows.append(
            {
                "signal": signal,
                "mean_ic": float(ic.mean()) if len(ic) else np.nan,
                "std_ic": float(ic.std()) if len(ic) else np.nan,
                "stability_ratio": float(ic.mean() / ic.std()) if len(ic) and ic.std() > 0 else np.nan,
                "pct_positive": float((ic > 0).mean()) if len(ic) else np.nan,
                "n_days": int(len(ic)),
            }
        )
    return pd.DataFrame(rows).sort_values("mean_ic", ascending=False)


def conditional_ic_by_tercile(panel: pd.DataFrame) -> pd.DataFrame:
    tercile_cols = [c for c in panel.columns if c.endswith("_tercile")]
    rows = []
    for signal in SIGNAL_COLS:
        s_col = f"{signal}_z"
        for t_col in tercile_cols:
            for bucket in ["low", "mid", "high"]:
                sub = panel[panel[t_col] == bucket]
                ic = daily_ic_series(sub, s_col)
                rows.append(
                    {
                        "signal": signal,
                        "macro_bucket_col": t_col,
                        "bucket": bucket,
                        "mean_ic": float(ic.mean()) if len(ic) else np.nan,
                        "std_ic": float(ic.std()) if len(ic) else np.nan,
                        "stability_ratio": float(ic.mean() / ic.std()) if len(ic) and ic.std() > 0 else np.nan,
                        "n_days": int(len(ic)),
                    }
                )
    out = pd.DataFrame(rows)
    return out


def _rolling_regime_weights(
    ic_table: pd.DataFrame,
    signals: List[str],
    lookback_days: int,
    min_obs: int,
    crash_blend: float = 0.65,
) -> pd.DataFrame:
    """
    Build regime-conditioned rolling signal weights.
    Uses only prior IC observations for each date.
    """
    ic_table = ic_table.sort_values("date").reset_index(drop=True).copy()
    dates = ic_table["date"].tolist()
    weights_rows = []

    def _is_crash_state(
        current_regime: object,
        current_stress: float,
        current_score: float,
        current_market_return: float,
        current_cross_vol: float,
        hist_frame: pd.DataFrame,
    ) -> bool:
        regime_hit = str(current_regime) in CRASH_REGIMES
        if hist_frame.empty:
            return bool(regime_hit or (np.isfinite(current_market_return) and current_market_return <= -0.02))
        stress_hist = (
            pd.to_numeric(hist_frame["TrueStress"], errors="coerce").dropna()
            if "TrueStress" in hist_frame.columns
            else pd.Series(dtype=float)
        )
        score_hist = (
            pd.to_numeric(hist_frame["MacroScore"], errors="coerce").dropna()
            if "MacroScore" in hist_frame.columns
            else pd.Series(dtype=float)
        )
        market_ret_hist = (
            pd.to_numeric(hist_frame["market_return_1d"], errors="coerce").dropna()
            if "market_return_1d" in hist_frame.columns
            else pd.Series(dtype=float)
        )
        cross_vol_hist = (
            pd.to_numeric(hist_frame["cross_sectional_vol_1d"], errors="coerce").dropna()
            if "cross_sectional_vol_1d" in hist_frame.columns
            else pd.Series(dtype=float)
        )
        stress_threshold = float(stress_hist.quantile(0.80)) if len(stress_hist) >= 30 else np.nan
        score_threshold = float(score_hist.quantile(0.20)) if len(score_hist) >= 30 else np.nan
        market_return_threshold = float(market_ret_hist.quantile(0.05)) if len(market_ret_hist) >= 30 else np.nan
        cross_vol_threshold = float(cross_vol_hist.quantile(0.90)) if len(cross_vol_hist) >= 30 else np.nan
        stress_hit = np.isfinite(current_stress) and np.isfinite(stress_threshold) and current_stress >= stress_threshold
        score_hit = np.isfinite(current_score) and np.isfinite(score_threshold) and current_score <= score_threshold
        market_hit = (
            np.isfinite(current_market_return)
            and ((current_market_return <= -0.015) or (np.isfinite(market_return_threshold) and current_market_return <= market_return_threshold))
        )
        vol_hit = np.isfinite(current_cross_vol) and np.isfinite(cross_vol_threshold) and current_cross_vol >= cross_vol_threshold
        return bool(regime_hit or stress_hit or score_hit or market_hit or vol_hit)

    for d in dates:
        d_start = d - pd.Timedelta(days=lookback_days)
        hist = ic_table[(ic_table["date"] < d) & (ic_table["date"] >= d_start)]
        date_rows = ic_table[ic_table["date"] == d]
        current_row = date_rows.iloc[0] if not date_rows.empty else pd.Series(dtype=object)
        current_regime = current_row.get("Regime", "")
        current_stress = float(pd.to_numeric(current_row.get("TrueStress", np.nan), errors="coerce"))
        current_score = float(pd.to_numeric(current_row.get("MacroScore", np.nan), errors="coerce"))
        current_market_return = float(pd.to_numeric(current_row.get("market_return_1d", np.nan), errors="coerce"))
        current_cross_vol = float(pd.to_numeric(current_row.get("cross_sectional_vol_1d", np.nan), errors="coerce"))
        if hist.empty:
            raw = {s: 1.0 for s in signals}
        else:
            regime = current_regime
            reg_hist = hist[hist["Regime"] == regime]
            raw = {}
            for s in signals:
                reg_vals = reg_hist[s].dropna()
                if len(reg_vals) >= min_obs:
                    raw[s] = float(reg_vals.mean())
                else:
                    all_vals = hist[s].dropna()
                    raw[s] = float(all_vals.mean()) if len(all_vals) else 0.0

        crash_state = _is_crash_state(
            current_regime=current_regime,
            current_stress=current_stress,
            current_score=current_score,
            current_market_return=current_market_return,
            current_cross_vol=current_cross_vol,
            hist_frame=hist,
        )
        if crash_state:
            blend = float(np.clip(crash_blend, 0.0, 1.0))
            for s in signals:
                prior = float(CRASH_PRIOR_WEIGHTS.get(s, 0.0))
                raw[s] = (1.0 - blend) * float(raw.get(s, 0.0)) + blend * prior

        norm = sum(abs(v) for v in raw.values())
        if norm <= 1e-12:
            w = {s: 1.0 / len(signals) for s in signals}
        else:
            w = {s: raw[s] / norm for s in signals}
        w["is_crash_state"] = bool(crash_state)
        w["date"] = d
        weights_rows.append(w)

    return pd.DataFrame(weights_rows).sort_values("date").reset_index(drop=True)


def evaluate_composites(
    panel: pd.DataFrame,
    lookback_days: int,
    min_obs: int,
    crash_blend: float = 0.65,
) -> Dict[str, object]:
    signals_z = [f"{s}_z" for s in SIGNAL_COLS]

    # Equal-weight composite
    panel = panel.copy()
    panel["signal_composite_equal"] = panel[signals_z].mean(axis=1)
    ic_equal = daily_ic_series(panel, "signal_composite_equal")

    # Regime-conditioned rolling weights from daily IC history
    daily_rows = []
    for signal in SIGNAL_COLS:
        ic_s = daily_ic_series(panel, f"{signal}_z").rename(signal)
        daily_rows.append(ic_s)
    ic_table = pd.concat(daily_rows, axis=1).reset_index().rename(columns={"index": "date"})
    macro_state_cols = [
        c
        for c in [
            "date",
            "Regime",
            "TrueStress",
            "MacroScore",
            "market_return_1d",
            "cross_sectional_vol_1d",
        ]
        if c in panel.columns
    ]
    regimes = panel[macro_state_cols].drop_duplicates().sort_values("date")
    ic_table = pd.merge(ic_table, regimes, on="date", how="left").dropna(subset=["Regime"])

    w_df = _rolling_regime_weights(
        ic_table=ic_table,
        signals=SIGNAL_COLS,
        lookback_days=lookback_days,
        min_obs=min_obs,
        crash_blend=crash_blend,
    )
    panel = pd.merge(panel, w_df, on="date", how="left")

    weighted_cols = []
    for signal in SIGNAL_COLS:
        out_col = f"weighted_{signal}"
        panel[out_col] = panel[f"{signal}_z"] * panel[signal]
        weighted_cols.append(out_col)
    panel["signal_composite_regime"] = panel[weighted_cols].sum(axis=1)
    ic_regime = daily_ic_series(panel, "signal_composite_regime")

    latest_date = panel["date"].max()
    latest_snapshot = panel.loc[
        panel["date"] == latest_date,
        ["date", "asset_id", "signal_composite_equal", "signal_composite_regime", "Regime"] + signals_z,
    ].copy()
    latest_snapshot = latest_snapshot.sort_values("signal_composite_regime", ascending=False)

    latest_weight_row = pd.DataFrame()
    if not w_df.empty:
        latest_weight_row = w_df[w_df["date"] == latest_date].copy()

    summary = pd.DataFrame(
        [
            {
                "composite": "equal_weight",
                "mean_ic": float(ic_equal.mean()) if len(ic_equal) else np.nan,
                "std_ic": float(ic_equal.std()) if len(ic_equal) else np.nan,
                "stability_ratio": float(ic_equal.mean() / ic_equal.std())
                if len(ic_equal) and ic_equal.std() > 0
                else np.nan,
                "pct_positive": float((ic_equal > 0).mean()) if len(ic_equal) else np.nan,
                "n_days": int(len(ic_equal)),
            },
            {
                "composite": "regime_conditioned_rolling",
                "mean_ic": float(ic_regime.mean()) if len(ic_regime) else np.nan,
                "std_ic": float(ic_regime.std()) if len(ic_regime) else np.nan,
                "stability_ratio": float(ic_regime.mean() / ic_regime.std())
                if len(ic_regime) and ic_regime.std() > 0
                else np.nan,
                "pct_positive": float((ic_regime > 0).mean()) if len(ic_regime) else np.nan,
                "n_days": int(len(ic_regime)),
            },
        ]
    )

    return {
        "summary": summary,
        "weights_by_date": w_df,
        "ic_equal": ic_equal,
        "ic_regime": ic_regime,
        "latest_snapshot": latest_snapshot,
        "latest_weight_row": latest_weight_row,
    }


def _to_json_safe(obj):
    if isinstance(obj, dict):
        return {str(k): _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_json_safe(v) for v in obj]
    if isinstance(obj, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(obj).isoformat()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        if not np.isfinite(v):
            return None
        return v
    if pd.isna(obj):
        return None
    return obj


def run(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading prices...")
    prices = load_prices(PRICE_DIR)
    print(f"Price rows={len(prices):,}, assets={prices['asset_id'].nunique()}, "
          f"date_range={prices['date'].min().date()}->{prices['date'].max().date()}")

    print("Computing baseline signals...")
    with_signals = compute_signals(prices)
    panel = compute_target(with_signals, horizon=args.horizon)
    print(f"Signal panel rows={len(panel):,}, date_range={panel['date'].min().date()}->{panel['date'].max().date()}")

    print("Loading macro state...")
    macro = load_macro_state(Path(args.macro_factors_path), Path(args.macro_score_path))
    print(f"Macro rows={len(macro):,}, date_range={macro['date'].min().date()}->{macro['date'].max().date()}")

    print("Joining daily panel with macro state...")
    panel_macro = merge_panel_with_macro(panel, macro)
    print(
        f"Joined rows={len(panel_macro):,}, date_range={panel_macro['date'].min().date()}->{panel_macro['date'].max().date()}"
    )

    print("Computing unconditional IC...")
    signal_ic = unconditional_signal_ic(panel_macro)
    signal_ic.to_csv(out_dir / "signal_ic_unconditional.csv", index=False)

    print("Computing macro-conditional IC by terciles...")
    cond_ic = conditional_ic_by_tercile(panel_macro)
    cond_ic.to_csv(out_dir / "signal_ic_macro_terciles.csv", index=False)

    print("Evaluating equal-weight vs regime-conditioned rolling composite...")
    composites = evaluate_composites(
        panel_macro,
        lookback_days=args.lookback_days,
        min_obs=args.min_obs,
        crash_blend=args.crash_blend,
    )
    composite_summary = composites["summary"]
    composite_summary.to_csv(out_dir / "composite_ic_summary.csv", index=False)
    composites["weights_by_date"].to_csv(out_dir / "regime_conditioned_weights_by_date.csv", index=False)
    composites["ic_equal"].to_frame("ic_equal").reset_index().to_csv(
        out_dir / "ic_time_series_equal_weight.csv", index=False
    )
    composites["ic_regime"].to_frame("ic_regime").reset_index().to_csv(
        out_dir / "ic_time_series_regime_conditioned.csv", index=False
    )
    latest_snapshot = composites.get("latest_snapshot")
    if isinstance(latest_snapshot, pd.DataFrame) and not latest_snapshot.empty:
        latest_snapshot.to_parquet(out_dir / "latest_macro_conditioned_signal_snapshot.parquet", index=False)
        latest_snapshot.to_csv(out_dir / "latest_macro_conditioned_signal_snapshot.csv", index=False)
    latest_weight_row = composites.get("latest_weight_row")
    if isinstance(latest_weight_row, pd.DataFrame) and not latest_weight_row.empty:
        latest_weight_row.to_csv(out_dir / "latest_regime_conditioned_weights.csv", index=False)

    # Lift summary for quick decisioning
    eq_ic = composite_summary.loc[composite_summary["composite"] == "equal_weight", "mean_ic"].iloc[0]
    rg_ic = composite_summary.loc[
        composite_summary["composite"] == "regime_conditioned_rolling", "mean_ic"
    ].iloc[0]
    rel_uplift = (rg_ic - eq_ic) / abs(eq_ic) if eq_ic and np.isfinite(eq_ic) and abs(eq_ic) > 1e-12 else np.nan

    report = {
        "horizon_days": args.horizon,
        "lookback_days": args.lookback_days,
        "min_obs": args.min_obs,
        "macro_factors_path": str(Path(args.macro_factors_path)),
        "macro_score_path": str(Path(args.macro_score_path)),
        "crash_blend": float(args.crash_blend),
        "sample": {
            "assets": int(panel_macro["asset_id"].nunique()),
            "rows": int(len(panel_macro)),
            "start_date": panel_macro["date"].min(),
            "end_date": panel_macro["date"].max(),
        },
        "unconditional_signal_ic": signal_ic.to_dict(orient="records"),
        "composite_ic_summary": composite_summary.to_dict(orient="records"),
        "composite_uplift": {
            "equal_weight_mean_ic": eq_ic,
            "regime_conditioned_mean_ic": rg_ic,
            "absolute_uplift": rg_ic - eq_ic if np.isfinite(rg_ic) and np.isfinite(eq_ic) else np.nan,
            "relative_uplift_vs_equal": rel_uplift,
        },
    }

    with open(out_dir / "macro_conditioned_audit_report.json", "w") as f:
        json.dump(_to_json_safe(report), f, indent=2)

    print("\nSaved:")
    print(f"- {out_dir / 'signal_ic_unconditional.csv'}")
    print(f"- {out_dir / 'signal_ic_macro_terciles.csv'}")
    print(f"- {out_dir / 'composite_ic_summary.csv'}")
    print(f"- {out_dir / 'regime_conditioned_weights_by_date.csv'}")
    print(f"- {out_dir / 'ic_time_series_equal_weight.csv'}")
    print(f"- {out_dir / 'ic_time_series_regime_conditioned.csv'}")
    print(f"- {out_dir / 'macro_conditioned_audit_report.json'}")

    print("\nComposite IC:")
    print(composite_summary.to_string(index=False))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Macro-conditioned signal IC audit")
    parser.add_argument("--horizon", type=int, default=20, help="Forward return horizon in trading days")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=504,
        help="History window (calendar days) for rolling regime-conditioned weights",
    )
    parser.add_argument(
        "--min-obs",
        type=int,
        default=20,
        help="Minimum IC observations in matching regime before fallback to all-regime history",
    )
    parser.add_argument(
        "--macro-factors-path",
        type=str,
        default=str(MACRO_FACTORS_PATH),
        help="Macro factors parquet path",
    )
    parser.add_argument(
        "--macro-score-path",
        type=str,
        default=str(MACRO_SCORE_PATH),
        help="Macro score parquet path",
    )
    parser.add_argument(
        "--crash-blend",
        type=float,
        default=0.65,
        help="Blend toward explicit crash priors when crash-state gating is active (0..1)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for reports",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
