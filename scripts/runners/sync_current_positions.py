#!/usr/bin/env python3
"""
Sync dashboard-friendly `data/portfolio/current_positions.json` from canonical
portfolio artifacts.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEIGHTS_PATH = PROJECT_ROOT / "data/processed/portfolio_weights.parquet"
PRICES_PATH = PROJECT_ROOT / "data/processed/prices.parquet"
RUNTIME_PATH = PROJECT_ROOT / "data/options/live/options_runtime_state.json"
PNL_PATH = PROJECT_ROOT / "data/portfolio/pnl_on_paper.parquet"
OUTPUT_PATH = PROJECT_ROOT / "data/portfolio/current_positions.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        out = float(v)
    except Exception:
        return default
    return out if np.isfinite(out) else default


def _load_total_value(default_capital: float) -> float:
    if RUNTIME_PATH.exists():
        try:
            runtime = json.loads(RUNTIME_PATH.read_text())
            net_equity = _safe_float(runtime.get("net_equity"), default=np.nan)
            if np.isfinite(net_equity) and net_equity > 0:
                return float(net_equity)
        except Exception:
            pass
    if PNL_PATH.exists():
        try:
            pnl_df = pd.read_parquet(PNL_PATH)
            if not pnl_df.empty and "Equity" in pnl_df.columns:
                eq = pd.to_numeric(pnl_df["Equity"], errors="coerce").dropna()
                if not eq.empty and float(eq.iloc[-1]) > 0:
                    return float(eq.iloc[-1])
        except Exception:
            pass
    return float(default_capital)


def _load_latest_prices() -> pd.DataFrame:
    if not PRICES_PATH.exists():
        return pd.DataFrame(columns=["ticker", "Close"])
    p = pd.read_parquet(PRICES_PATH)
    if p.empty or "ticker" not in p.columns:
        return pd.DataFrame(columns=["ticker", "Close"])
    date_col = "Date" if "Date" in p.columns else ("date" if "date" in p.columns else None)
    if date_col is None:
        return pd.DataFrame(columns=["ticker", "Close"])
    p[date_col] = pd.to_datetime(p[date_col], errors="coerce")
    p["Close"] = pd.to_numeric(p.get("Close"), errors="coerce")
    p = p.dropna(subset=["ticker", date_col, "Close"]).sort_values(date_col)
    if p.empty:
        return pd.DataFrame(columns=["ticker", "Close"])
    return p.groupby("ticker", as_index=False).tail(1)[["ticker", "Close"]]


def _load_daily_return_pct() -> float:
    if not PNL_PATH.exists():
        return 0.0
    try:
        pnl_df = pd.read_parquet(PNL_PATH)
        if pnl_df.empty:
            return 0.0
        if "Return" in pnl_df.columns:
            series = pd.to_numeric(pnl_df["Return"], errors="coerce").dropna()
            if not series.empty:
                return float(series.iloc[-1] * 100.0)
    except Exception:
        return 0.0
    return 0.0


def build_current_positions(default_capital: float = 10_000_000.0) -> Dict[str, Any]:
    if not WEIGHTS_PATH.exists():
        raise FileNotFoundError(f"Missing portfolio weights: {WEIGHTS_PATH}")

    wdf = pd.read_parquet(WEIGHTS_PATH)
    if wdf.empty:
        raise RuntimeError("portfolio_weights.parquet is empty")

    if "ticker" not in wdf.columns:
        if "symbol" in wdf.columns:
            wdf["ticker"] = wdf["symbol"].astype(str)
        else:
            raise RuntimeError("portfolio_weights missing ticker/symbol columns")

    if "weight" not in wdf.columns:
        if "final_weight" in wdf.columns:
            wdf["weight"] = pd.to_numeric(wdf["final_weight"], errors="coerce")
        elif "exposure" in wdf.columns:
            wdf["weight"] = pd.to_numeric(wdf["exposure"], errors="coerce")
        else:
            raise RuntimeError("portfolio_weights missing weight/final_weight/exposure columns")

    wdf["weight"] = pd.to_numeric(wdf["weight"], errors="coerce").fillna(0.0)
    wdf = wdf[wdf["weight"].abs() > 1e-9].copy()

    if wdf.empty:
        raise RuntimeError("No non-zero positions found in portfolio_weights")

    prices = _load_latest_prices()
    if not prices.empty:
        wdf = wdf.merge(prices, on="ticker", how="left")
    else:
        wdf["Close"] = np.nan

    total_value = _load_total_value(default_capital=default_capital)
    invested_value = float((wdf["weight"].clip(lower=0.0).sum()) * total_value)
    cash = float(max(0.0, total_value - invested_value))

    positions: Dict[str, Dict[str, Any]] = {}
    sector_allocation: Dict[str, float] = {}

    for _, row in wdf.iterrows():
        ticker = str(row.get("ticker"))
        weight = _safe_float(row.get("weight"))
        sector = str(row.get("Industry") or row.get("sector") or "Unknown")
        current_price = _safe_float(row.get("Close"), default=0.0)
        market_value = float(max(0.0, weight) * total_value)
        quantity = float(market_value / current_price) if current_price > 0 else 0.0

        positions[ticker] = {
            "symbol": ticker,
            "quantity": quantity,
            "avg_price": current_price,
            "current_price": current_price,
            "market_value": market_value,
            "unrealized_pnl": 0.0,
            "weight": weight,
            "sector": sector,
        }
        sector_allocation[sector] = sector_allocation.get(sector, 0.0) + max(0.0, weight)

    daily_return_pct = _load_daily_return_pct()
    total_return_pct = 0.0
    if PNL_PATH.exists():
        try:
            pnl_df = pd.read_parquet(PNL_PATH)
            eq = pd.to_numeric(pnl_df.get("Equity"), errors="coerce").dropna()
            if len(eq) >= 2 and float(eq.iloc[0]) > 0:
                total_return_pct = float((eq.iloc[-1] / eq.iloc[0] - 1.0) * 100.0)
        except Exception:
            total_return_pct = 0.0

    payload = {
        "timestamp": _utc_now_iso(),
        "total_value": total_value,
        "cash": cash,
        "invested_value": invested_value,
        "positions": positions,
        "sector_allocation": sector_allocation,
        "performance": {
            "total_pnl": float(total_value - default_capital),
            "total_return_pct": total_return_pct,
            "daily_return_pct": daily_return_pct,
            "volatility_30d": 0.0,
            "sharpe_ratio": 0.0,
        },
    }
    return payload


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Sync current_positions.json from portfolio weights")
    p.add_argument("--default-capital", type=float, default=10_000_000.0)
    p.add_argument("--output", type=str, default=str(OUTPUT_PATH))
    return p.parse_args()


def main() -> int:
    args = parse_args()
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_current_positions(default_capital=float(args.default_capital))

    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str))
    tmp.replace(out_path)

    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(out_path),
                "positions": len(payload.get("positions", {})),
                "total_value": payload.get("total_value"),
                "timestamp": payload.get("timestamp"),
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
