#!/usr/bin/env python3
"""
Validation diagnostics for valuation artifacts:
- Decile monotonicity vs forward returns
- Information coefficient (Spearman IC)
- Regime-sliced performance diagnostics
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VALUATION_PATH = PROJECT_ROOT / "data/processed/valuation.parquet"
DEFAULT_PRICES_PATH = PROJECT_ROOT / "data/processed/prices.parquet"
DEFAULT_REGIME_PATH = PROJECT_ROOT / "data/processed/market_regime.parquet"
DEFAULT_SUMMARY_PATH = PROJECT_ROOT / "data/processed/valuation_validation_summary.json"
DEFAULT_DECILES_PATH = PROJECT_ROOT / "data/processed/valuation_validation_deciles.parquet"
DEFAULT_IC_PATH = PROJECT_ROOT / "data/processed/valuation_validation_ic.parquet"
DEFAULT_REGIME_OUT_PATH = PROJECT_ROOT / "data/processed/valuation_validation_regime.parquet"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_parquet(path)


def _safe_spearman(x: pd.Series, y: pd.Series) -> float:
    xx = pd.to_numeric(x, errors="coerce")
    yy = pd.to_numeric(y, errors="coerce")
    m = xx.notna() & yy.notna()
    if m.sum() < 8:
        return float("nan")
    return float(xx[m].corr(yy[m], method="spearman"))


def _asof_regime_map(dates: pd.Series, regime_df: pd.DataFrame) -> pd.DataFrame:
    base = pd.DataFrame({"date": pd.to_datetime(dates, errors="coerce")}).dropna().drop_duplicates().sort_values("date")
    if base.empty:
        return base.assign(market_regime=np.nan)
    if regime_df.empty or "Date" not in regime_df.columns:
        return base.assign(market_regime=np.nan)
    reg = regime_df.copy()
    reg["Date"] = pd.to_datetime(reg["Date"], errors="coerce")
    reg = reg.dropna(subset=["Date"]).sort_values("Date")
    if reg.empty:
        return base.assign(market_regime=np.nan)
    col = "market_regime" if "market_regime" in reg.columns else ("regime" if "regime" in reg.columns else None)
    if col is None:
        return base.assign(market_regime=np.nan)
    merged = pd.merge_asof(base, reg[["Date", col]], left_on="date", right_on="Date", direction="backward")
    merged["market_regime"] = merged[col].astype(str).replace({"nan": "Unknown"})
    return merged[["date", "market_regime"]]


def _build_price_index(prices: pd.DataFrame) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    out: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    if prices.empty:
        return out
    p = prices.copy()
    if "Date" not in p.columns:
        return out
    p["Date"] = pd.to_datetime(p["Date"], errors="coerce")
    p["Close"] = pd.to_numeric(p.get("Close"), errors="coerce")
    p = p.dropna(subset=["Date", "ticker", "Close"]).sort_values(["ticker", "Date"])
    for ticker, g in p.groupby("ticker", sort=False):
        dates = g["Date"].astype("datetime64[ns]").to_numpy()
        close = g["Close"].to_numpy(dtype=float)
        out[str(ticker)] = (dates, close)
    return out


def _forward_return(
    date0: pd.Timestamp,
    ticker: str,
    horizon_days: int,
    price_idx: Dict[str, Tuple[np.ndarray, np.ndarray]],
) -> float:
    payload = price_idx.get(str(ticker))
    if payload is None:
        return float("nan")
    dates, close = payload
    if len(dates) == 0:
        return float("nan")
    d0 = np.datetime64(pd.Timestamp(date0).to_datetime64())
    dh = np.datetime64((pd.Timestamp(date0) + pd.Timedelta(days=int(horizon_days))).to_datetime64())
    i0 = int(np.searchsorted(dates, d0, side="left"))
    ih = int(np.searchsorted(dates, dh, side="left"))
    if i0 >= len(dates) or ih >= len(dates):
        return float("nan")
    p0 = float(close[i0])
    ph = float(close[ih])
    if not np.isfinite(p0) or not np.isfinite(ph) or p0 <= 0:
        return float("nan")
    return float(ph / p0 - 1.0)


@dataclass
class ValidationSummary:
    timestamp: str
    status: str
    valuation_rows: int
    usable_rows: int
    horizons: List[int]
    windows_evaluated: int
    ic_mean: float
    ic_std: float
    ic_information_ratio: float
    top_bottom_spread_mean: float
    monotonic_pass_rate: float
    regime_windows: int
    failures: List[str]


def _compute_decile_metrics(
    frame: pd.DataFrame,
    score_col: str,
    ret_col: str,
) -> Tuple[pd.DataFrame, Dict[str, float]]:
    f = frame[[score_col, ret_col]].copy()
    f[score_col] = pd.to_numeric(f[score_col], errors="coerce")
    f[ret_col] = pd.to_numeric(f[ret_col], errors="coerce")
    f = f.dropna(subset=[score_col, ret_col])
    if len(f) < 20:
        return pd.DataFrame(), {"spread": np.nan, "slope": np.nan, "monotonic": 0.0}

    ranks = f[score_col].rank(method="first")
    try:
        dec = pd.qcut(ranks, q=10, labels=False, duplicates="drop")
    except Exception:
        return pd.DataFrame(), {"spread": np.nan, "slope": np.nan, "monotonic": 0.0}
    f = f.assign(decile=dec.astype("float64") + 1.0)
    decile = (
        f.groupby("decile", as_index=False)
        .agg(mean_return=(ret_col, "mean"), n_obs=(ret_col, "count"))
        .sort_values("decile")
    )
    if decile.empty or decile["decile"].nunique() < 4:
        return decile, {"spread": np.nan, "slope": np.nan, "monotonic": 0.0}

    x = decile["decile"].to_numpy(dtype=float)
    y = decile["mean_return"].to_numpy(dtype=float)
    slope = float(np.polyfit(x, y, 1)[0]) if len(x) >= 2 else np.nan
    low = float(decile.iloc[0]["mean_return"])
    high = float(decile.iloc[-1]["mean_return"])
    spread = high - low
    monotonic = 1.0 if (np.isfinite(slope) and slope > 0 and spread > 0) else 0.0
    return decile, {"spread": spread, "slope": slope, "monotonic": monotonic}


def run_validation(
    valuation: pd.DataFrame,
    prices: pd.DataFrame,
    regime: pd.DataFrame,
    score_col: str,
    horizons: Sequence[int],
    min_universe: int,
) -> Tuple[ValidationSummary, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    failures: List[str] = []
    val = valuation.copy()
    if "date" not in val.columns or "ticker" not in val.columns:
        raise ValueError("valuation must contain columns: date, ticker")
    if score_col not in val.columns:
        raise ValueError(f"valuation score column missing: {score_col}")

    val["date"] = pd.to_datetime(val["date"], errors="coerce")
    val[score_col] = pd.to_numeric(val[score_col], errors="coerce")
    val = val.dropna(subset=["date", "ticker", score_col]).copy()
    if val.empty:
        raise ValueError("valuation has no usable rows after date/ticker/score filtering")

    # Keep latest row per ticker/date pair to avoid accidental duplication.
    val = val.sort_values(["ticker", "date"]).drop_duplicates(subset=["ticker", "date"], keep="last")
    valuation_rows = len(val)

    regime_map = _asof_regime_map(val["date"], regime)
    val = val.merge(regime_map, on="date", how="left")

    price_idx = _build_price_index(prices)
    frames: List[pd.DataFrame] = []
    for h in horizons:
        tmp = val[["ticker", "date", score_col, "market_regime"]].copy()
        tmp["horizon_days"] = int(h)
        tmp["forward_return"] = [
            _forward_return(d, t, int(h), price_idx)
            for d, t in zip(tmp["date"], tmp["ticker"])
        ]
        frames.append(tmp)
    full = pd.concat(frames, ignore_index=True)
    full = full.dropna(subset=["forward_return"]).copy()
    usable_rows = len(full)
    if full.empty:
        raise ValueError("no forward returns available for selected horizons")

    ic_rows: List[Dict[str, float]] = []
    decile_rows: List[pd.DataFrame] = []
    for (h, d), g in full.groupby(["horizon_days", "date"], sort=True):
        n_obs = int(g["ticker"].nunique())
        if n_obs < int(min_universe):
            continue
        ic = _safe_spearman(g[score_col], g["forward_return"])
        dec, dec_metrics = _compute_decile_metrics(g, score_col=score_col, ret_col="forward_return")
        if not dec.empty:
            dec = dec.assign(horizon_days=int(h), date=pd.to_datetime(d))
            decile_rows.append(dec)
        ic_rows.append(
            {
                "horizon_days": int(h),
                "date": pd.to_datetime(d),
                "n_obs": n_obs,
                "ic_spearman": ic,
                "top_bottom_spread": dec_metrics["spread"],
                "decile_slope": dec_metrics["slope"],
                "monotonic_pass": dec_metrics["monotonic"],
                "market_regime": str(g["market_regime"].mode().iloc[0]) if g["market_regime"].notna().any() else "Unknown",
            }
        )

    ic_df = pd.DataFrame(ic_rows)
    deciles_df = pd.concat(decile_rows, ignore_index=True) if decile_rows else pd.DataFrame(
        columns=["decile", "mean_return", "n_obs", "horizon_days", "date"]
    )
    if ic_df.empty:
        failures.append("no_windows_with_min_universe")
        regime_df = pd.DataFrame(columns=["market_regime", "horizon_days", "windows", "ic_mean", "spread_mean", "monotonic_rate"])
        summary = ValidationSummary(
            timestamp=_utc_now_iso(),
            status="failed",
            valuation_rows=valuation_rows,
            usable_rows=usable_rows,
            horizons=[int(x) for x in horizons],
            windows_evaluated=0,
            ic_mean=float("nan"),
            ic_std=float("nan"),
            ic_information_ratio=float("nan"),
            top_bottom_spread_mean=float("nan"),
            monotonic_pass_rate=float("nan"),
            regime_windows=0,
            failures=failures,
        )
        return summary, deciles_df, ic_df, regime_df

    regime_df = (
        ic_df.groupby(["market_regime", "horizon_days"], as_index=False)
        .agg(
            windows=("ic_spearman", "count"),
            ic_mean=("ic_spearman", "mean"),
            spread_mean=("top_bottom_spread", "mean"),
            monotonic_rate=("monotonic_pass", "mean"),
        )
        .sort_values(["horizon_days", "market_regime"])
    )

    ic_mean = float(ic_df["ic_spearman"].mean())
    ic_std = float(ic_df["ic_spearman"].std())
    ir = float(ic_mean / (ic_std + 1e-12) * math.sqrt(max(len(ic_df), 1))) if np.isfinite(ic_mean) else float("nan")
    spread_mean = float(ic_df["top_bottom_spread"].mean())
    mono_rate = float(ic_df["monotonic_pass"].mean())

    if not np.isfinite(ic_mean) or ic_mean <= 0:
        failures.append("ic_mean_non_positive")
    if not np.isfinite(spread_mean) or spread_mean <= 0:
        failures.append("top_bottom_spread_non_positive")
    if not np.isfinite(mono_rate) or mono_rate < 0.55:
        failures.append("monotonic_pass_rate_below_55pct")

    status = "ok" if not failures else "warn"
    summary = ValidationSummary(
        timestamp=_utc_now_iso(),
        status=status,
        valuation_rows=valuation_rows,
        usable_rows=usable_rows,
        horizons=[int(x) for x in horizons],
        windows_evaluated=int(len(ic_df)),
        ic_mean=ic_mean,
        ic_std=ic_std,
        ic_information_ratio=ir,
        top_bottom_spread_mean=spread_mean,
        monotonic_pass_rate=mono_rate,
        regime_windows=int(len(regime_df)),
        failures=failures,
    )
    return summary, deciles_df, ic_df, regime_df


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run valuation validation diagnostics")
    p.add_argument("--valuation-path", type=str, default=str(DEFAULT_VALUATION_PATH))
    p.add_argument("--prices-path", type=str, default=str(DEFAULT_PRICES_PATH))
    p.add_argument("--regime-path", type=str, default=str(DEFAULT_REGIME_PATH))
    p.add_argument("--score-col", type=str, default="true_undervaluation")
    p.add_argument("--horizons", type=str, default="21,63")
    p.add_argument("--min-universe", type=int, default=40)
    p.add_argument("--summary-out", type=str, default=str(DEFAULT_SUMMARY_PATH))
    p.add_argument("--deciles-out", type=str, default=str(DEFAULT_DECILES_PATH))
    p.add_argument("--ic-out", type=str, default=str(DEFAULT_IC_PATH))
    p.add_argument("--regime-out", type=str, default=str(DEFAULT_REGIME_OUT_PATH))
    p.add_argument("--strict", action="store_true", help="Exit non-zero when validation status != ok")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    valuation = _read_parquet(Path(args.valuation_path))
    prices = _read_parquet(Path(args.prices_path))
    regime = _read_parquet(Path(args.regime_path)) if Path(args.regime_path).exists() else pd.DataFrame()
    horizons = [int(x.strip()) for x in str(args.horizons).split(",") if x.strip()]
    if not horizons:
        raise ValueError("At least one horizon must be provided")

    summary, deciles, ic_df, regime_df = run_validation(
        valuation=valuation,
        prices=prices,
        regime=regime,
        score_col=str(args.score_col),
        horizons=horizons,
        min_universe=int(args.min_universe),
    )

    summary_path = Path(args.summary_out)
    deciles_path = Path(args.deciles_out)
    ic_path = Path(args.ic_out)
    regime_out_path = Path(args.regime_out)
    for p in [summary_path, deciles_path, ic_path, regime_out_path]:
        p.parent.mkdir(parents=True, exist_ok=True)

    payload = asdict(summary)
    summary_path.write_text(json.dumps(payload, indent=2, default=str))
    deciles.to_parquet(deciles_path, index=False)
    ic_df.to_parquet(ic_path, index=False)
    regime_df.to_parquet(regime_out_path, index=False)

    print(json.dumps(payload, indent=2, default=str))
    if args.strict and summary.status != "ok":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

