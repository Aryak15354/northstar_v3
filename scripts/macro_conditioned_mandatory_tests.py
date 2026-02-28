#!/usr/bin/env python3
"""
Run the 4 mandatory robustness tests for macro-conditioned alpha:
1) Subperiod stability
2) Crisis-window IC
3) Universe sensitivity (Top 150/200/300)
4) Horizon sensitivity (10/20/40/60)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd

from macro_conditioned_signal_audit import (
    MACRO_FACTORS_PATH,
    MACRO_SCORE_PATH,
    PRICE_DIR,
    compute_signals,
    compute_target,
    evaluate_composites,
    load_macro_state,
    load_prices,
    merge_panel_with_macro,
)


DEFAULT_OUTPUT_DIR = Path("reports/signal_audit/macro_conditioned_mandatory")
VALUATION_PATH = Path("data/processed/valuation.parquet")
FUNDAMENTALS_PATH = Path("data/processed/fundamentals.parquet")
PRICES_PARQUET_PATH = Path("data/processed/prices.parquet")

SUBPERIODS: List[Tuple[str, str, str]] = [
    ("2017-2019", "2017-01-01", "2019-12-31"),
    ("2020-2021", "2020-01-01", "2021-12-31"),
    ("2022-2024", "2022-01-01", "2024-12-31"),
    ("2024-2026", "2024-01-01", "2026-12-31"),
]

CRISIS_WINDOWS: List[Tuple[str, str, str]] = [
    ("covid_crash", "2020-02-20", "2020-04-07"),
    ("2022_tightening", "2022-05-01", "2022-12-30"),
]

HORIZONS = [10, 20, 40, 60]
UNIVERSE_NS = [150, 200, 300, 500]


def _to_json_safe(obj):
    if isinstance(obj, dict):
        return {str(k): _to_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_json_safe(v) for v in obj]
    if isinstance(obj, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(obj).isoformat()
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        v = float(obj)
        return v if np.isfinite(v) else None
    if pd.isna(obj):
        return None
    return obj


def summarize_ic(ic_series: pd.Series, label: str) -> Dict[str, object]:
    ic = ic_series.dropna()
    if len(ic) == 0:
        return {
            "label": label,
            "mean_ic": np.nan,
            "std_ic": np.nan,
            "stability_ratio": np.nan,
            "pct_positive": np.nan,
            "n_days": 0,
            "start_date": None,
            "end_date": None,
        }
    std = float(ic.std())
    mean = float(ic.mean())
    return {
        "label": label,
        "mean_ic": mean,
        "std_ic": std,
        "stability_ratio": mean / std if std > 1e-12 else np.nan,
        "pct_positive": float((ic > 0).mean()),
        "n_days": int(len(ic)),
        "start_date": ic.index.min(),
        "end_date": ic.index.max(),
    }


def slice_ic(ic_series: pd.Series, start: str, end: str) -> pd.Series:
    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    mask = (ic_series.index >= s) & (ic_series.index <= e)
    return ic_series.loc[mask]


def load_market_cap_ranked_tickers(valuation_path: Path) -> List[str]:
    """
    Build robust top-N ranking for all 500 names.
    Priority:
    1) valuation.market_cap
    2) fundamentals.shares_outstanding * latest close
    3) latest 60d average traded value (price*volume) as liquidity proxy
    """
    if not valuation_path.exists():
        raise FileNotFoundError(
            f"Missing valuation parquet for market-cap ranking: {valuation_path}"
        )
    if not FUNDAMENTALS_PATH.exists():
        raise FileNotFoundError(f"Missing fundamentals parquet: {FUNDAMENTALS_PATH}")
    if not PRICES_PARQUET_PATH.exists():
        raise FileNotFoundError(f"Missing prices parquet: {PRICES_PARQUET_PATH}")

    val = pd.read_parquet(valuation_path)
    req = {"ticker", "market_cap"}
    if req - set(val.columns):
        raise ValueError(f"{valuation_path} must have columns: {sorted(req)}")
    if "date" in val.columns:
        val = val.sort_values(["ticker", "date"]).groupby("ticker", as_index=False).tail(1)
    val = val[["ticker", "market_cap"]].copy()

    fund = pd.read_parquet(FUNDAMENTALS_PATH)
    if {"ticker", "shares_outstanding"} - set(fund.columns):
        raise ValueError("fundamentals.parquet must contain ticker and shares_outstanding")
    if "date" in fund.columns:
        fund = fund.sort_values(["ticker", "date"]).groupby("ticker", as_index=False).tail(1)
    fund = fund[["ticker", "shares_outstanding"]].copy()

    prices = pd.read_parquet(PRICES_PARQUET_PATH)
    if {"ticker", "Close", "Volume", "Date"} - set(prices.columns):
        raise ValueError("prices.parquet must contain ticker, Close, Volume, Date")
    prices = prices.sort_values(["ticker", "Date"]).copy()

    latest_px = prices.groupby("ticker", as_index=False).tail(1)[["ticker", "Close"]].rename(
        columns={"Close": "latest_close"}
    )
    prices["traded_value"] = prices["Close"] * prices["Volume"]
    adv60 = (
        prices.groupby("ticker")["traded_value"]
        .tail(60)
        .groupby(prices.groupby("ticker").tail(60)["ticker"])
        .mean()
        .reset_index(name="adv60_value")
    )

    universe = prices[["ticker"]].drop_duplicates().copy()
    rank_df = (
        universe.merge(val, on="ticker", how="left")
        .merge(fund, on="ticker", how="left")
        .merge(latest_px, on="ticker", how="left")
        .merge(adv60, on="ticker", how="left")
    )
    rank_df["mcap_from_shares"] = rank_df["shares_outstanding"] * rank_df["latest_close"]
    rank_df["rank_metric"] = rank_df["market_cap"]
    rank_df["rank_metric"] = rank_df["rank_metric"].fillna(rank_df["mcap_from_shares"])
    rank_df["rank_metric"] = rank_df["rank_metric"].fillna(rank_df["adv60_value"])
    rank_df = rank_df.dropna(subset=["rank_metric"]).sort_values("rank_metric", ascending=False)
    return rank_df["ticker"].astype(str).tolist()


def run(args: argparse.Namespace) -> int:
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Loading shared inputs...")
    prices = load_prices(PRICE_DIR)
    with_signals = compute_signals(prices)
    macro = load_macro_state(Path(args.macro_factors_path), Path(args.macro_score_path))
    ranked_tickers = load_market_cap_ranked_tickers(VALUATION_PATH)

    print(
        f"Universe source assets={with_signals['asset_id'].nunique()}, "
        f"macro_rows={len(macro)}, ranked_tickers={len(ranked_tickers)}"
    )

    # 4) Horizon sensitivity on full universe
    print("\n[1/4] Horizon sensitivity...")
    horizon_rows = []
    composites_by_horizon = {}
    panel_by_horizon = {}

    for h in HORIZONS:
        print(f"  Horizon {h}d...")
        panel = compute_target(with_signals, horizon=h)
        panel_macro = merge_panel_with_macro(panel, macro)
        panel_by_horizon[h] = panel_macro
        comp = evaluate_composites(
            panel_macro,
            lookback_days=args.lookback_days,
            min_obs=args.min_obs,
            crash_blend=args.crash_blend,
        )
        composites_by_horizon[h] = comp
        summ = comp["summary"].copy()
        summ["horizon_days"] = h
        summ["universe"] = "all500"
        horizon_rows.append(summ)

    horizon_df = pd.concat(horizon_rows, ignore_index=True)
    horizon_df.to_csv(out_dir / "mandatory_horizon_sensitivity.csv", index=False)

    # Reference run for subperiod + crisis + default universe checks
    ref_h = 20
    ref_comp = composites_by_horizon[ref_h]
    ref_ic_equal = ref_comp["ic_equal"]
    ref_ic_regime = ref_comp["ic_regime"]

    # 1) Subperiod stability (on 20d composite)
    print("\n[2/4] Subperiod stability...")
    sub_rows = []
    for name, start, end in SUBPERIODS:
        sub_rows.append(
            {
                **summarize_ic(slice_ic(ref_ic_equal, start, end), f"{name}|equal_weight"),
                "period": name,
                "composite": "equal_weight",
                "start": start,
                "end": end,
                "horizon_days": ref_h,
            }
        )
        sub_rows.append(
            {
                **summarize_ic(
                    slice_ic(ref_ic_regime, start, end),
                    f"{name}|regime_conditioned_rolling",
                ),
                "period": name,
                "composite": "regime_conditioned_rolling",
                "start": start,
                "end": end,
                "horizon_days": ref_h,
            }
        )
    subperiod_df = pd.DataFrame(sub_rows)
    subperiod_df.to_csv(out_dir / "mandatory_subperiod_stability.csv", index=False)

    # 2) Crisis window IC (on 20d composite)
    print("\n[3/4] Crisis windows...")
    crisis_rows = []
    for name, start, end in CRISIS_WINDOWS:
        crisis_rows.append(
            {
                **summarize_ic(slice_ic(ref_ic_equal, start, end), f"{name}|equal_weight"),
                "window": name,
                "composite": "equal_weight",
                "start": start,
                "end": end,
                "horizon_days": ref_h,
            }
        )
        crisis_rows.append(
            {
                **summarize_ic(
                    slice_ic(ref_ic_regime, start, end),
                    f"{name}|regime_conditioned_rolling",
                ),
                "window": name,
                "composite": "regime_conditioned_rolling",
                "start": start,
                "end": end,
                "horizon_days": ref_h,
            }
        )
    crisis_df = pd.DataFrame(crisis_rows)
    crisis_df.to_csv(out_dir / "mandatory_crisis_windows.csv", index=False)

    # 3) Universe sensitivity (Top N by market cap) at 20d horizon
    print("\n[4/4] Universe sensitivity...")
    universe_rows = []
    for n in UNIVERSE_NS:
        if n == 500:
            keep = set(with_signals["asset_id"].unique())
            label = "all500"
        else:
            keep = set(ranked_tickers[:n])
            label = f"top{n}_mcap"

        subset = with_signals[with_signals["asset_id"].isin(keep)].copy()
        panel_u = compute_target(subset, horizon=ref_h)
        panel_u_macro = merge_panel_with_macro(panel_u, macro)
        comp_u = evaluate_composites(
            panel_u_macro,
            lookback_days=args.lookback_days,
            min_obs=args.min_obs,
            crash_blend=args.crash_blend,
        )
        summ_u = comp_u["summary"].copy()
        summ_u["horizon_days"] = ref_h
        summ_u["universe"] = label
        summ_u["assets"] = panel_u_macro["asset_id"].nunique()
        summ_u["rows"] = len(panel_u_macro)
        universe_rows.append(summ_u)

    universe_df = pd.concat(universe_rows, ignore_index=True)
    universe_df.to_csv(out_dir / "mandatory_universe_sensitivity.csv", index=False)

    # Decision flags
    u_regime = universe_df[universe_df["composite"] == "regime_conditioned_rolling"].copy()
    u_regime = u_regime[u_regime["universe"].isin(["top150_mcap", "top200_mcap", "top300_mcap"])]
    universe_robust = bool((u_regime["mean_ic"] > 0.05).all()) if len(u_regime) == 3 else False

    h_regime = horizon_df[horizon_df["composite"] == "regime_conditioned_rolling"].copy()
    h_lookup = {int(r["horizon_days"]): float(r["mean_ic"]) for _, r in h_regime.iterrows()}
    horizon_strengthens_40_60 = (
        h_lookup.get(40, np.nan) > h_lookup.get(20, np.nan)
        and h_lookup.get(60, np.nan) > h_lookup.get(20, np.nan)
    )

    s_regime = subperiod_df[subperiod_df["composite"] == "regime_conditioned_rolling"].copy()
    subperiod_nonnegative = bool((s_regime["mean_ic"] > 0).all()) if len(s_regime) else False

    c_regime = crisis_df[crisis_df["composite"] == "regime_conditioned_rolling"].copy()
    crisis_survives = bool((c_regime["mean_ic"] > 0).all()) if len(c_regime) == 2 else False

    summary = {
        "config": {
            "lookback_days": args.lookback_days,
            "min_obs": args.min_obs,
            "ref_horizon_days": ref_h,
            "macro_factors_path": str(Path(args.macro_factors_path)),
            "macro_score_path": str(Path(args.macro_score_path)),
            "crash_blend": float(args.crash_blend),
        },
        "flags": {
            "subperiod_nonnegative_ic": subperiod_nonnegative,
            "crisis_windows_positive_ic": crisis_survives,
            "universe_robust_ic_gt_0p05_top150_200_300": universe_robust,
            "horizon_strengthens_at_40_60_vs_20": bool(horizon_strengthens_40_60),
        },
        "files": {
            "subperiod": str(out_dir / "mandatory_subperiod_stability.csv"),
            "crisis": str(out_dir / "mandatory_crisis_windows.csv"),
            "universe": str(out_dir / "mandatory_universe_sensitivity.csv"),
            "horizon": str(out_dir / "mandatory_horizon_sensitivity.csv"),
        },
    }
    with open(out_dir / "mandatory_tests_report.json", "w") as f:
        json.dump(_to_json_safe(summary), f, indent=2)

    print("\nSaved mandatory-test artifacts:")
    print(f"- {out_dir / 'mandatory_subperiod_stability.csv'}")
    print(f"- {out_dir / 'mandatory_crisis_windows.csv'}")
    print(f"- {out_dir / 'mandatory_universe_sensitivity.csv'}")
    print(f"- {out_dir / 'mandatory_horizon_sensitivity.csv'}")
    print(f"- {out_dir / 'mandatory_tests_report.json'}")

    print("\nDecision flags:")
    for k, v in summary["flags"].items():
        print(f"- {k}: {v}")

    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run mandatory macro-conditioned robustness tests")
    p.add_argument("--lookback-days", type=int, default=504)
    p.add_argument("--min-obs", type=int, default=20)
    p.add_argument("--crash-blend", type=float, default=0.65)
    p.add_argument("--macro-factors-path", type=str, default=str(MACRO_FACTORS_PATH))
    p.add_argument("--macro-score-path", type=str, default=str(MACRO_SCORE_PATH))
    p.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR))
    return p.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
