#!/usr/bin/env python3
"""
📈 P&L CHART DATA GENERATOR
Generate chart-ready P&L data for dashboard visualization
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, Any

import numpy as np
import pandas as pd


def generate_pnl_chart_data() -> Dict[str, Any]:
    """Generate P&L chart data for dashboard."""

    print("📈 Generating P&L chart data...")

    pnl_path = "data/portfolio/pnl_on_paper.parquet"
    if not os.path.exists(pnl_path):
        print("   ⚠️ P&L file missing")
        return {}

    try:
        pnl_df = pd.read_parquet(pnl_path)
    except Exception as e:
        print(f"   ⚠️ Failed to read P&L data: {e}")
        return {}

    if pnl_df.empty or "Date" not in pnl_df.columns:
        print("   ⚠️ P&L data empty or malformed")
        return {}

    pnl_df["Date"] = pd.to_datetime(pnl_df["Date"], errors="coerce")
    pnl_df = pnl_df.dropna(subset=["Date"]).sort_values("Date")
    if pnl_df.empty:
        print("   ⚠️ P&L data has no valid dates")
        return {}

    # Sample every 5th day to reduce size
    chart_df = pnl_df.iloc[::5].copy()

    if "Equity" not in chart_df.columns or "Return" not in chart_df.columns:
        print("   ⚠️ P&L data missing Equity/Return columns")
        return {}

    initial_equity = float(chart_df["Equity"].iloc[0])
    if initial_equity == 0:
        initial_equity = 1.0

    chart_df["cumulative_return"] = (chart_df["Equity"] / initial_equity - 1.0) * 100.0
    chart_df["rolling_vol_30d"] = chart_df["Return"].rolling(30).std() * np.sqrt(252) * 100.0

    rolling_mean = chart_df["Return"].rolling(30).mean() * 252
    rolling_std = chart_df["Return"].rolling(30).std() * np.sqrt(252)
    chart_df["rolling_sharpe_30d"] = rolling_mean / rolling_std.replace(0, np.nan)

    peak = chart_df["Equity"].expanding().max()
    chart_df["drawdown"] = (chart_df["Equity"] / peak - 1.0) * 100.0

    chart_data = {
        "dates": chart_df["Date"].dt.strftime("%Y-%m-%d").tolist(),
        "equity": chart_df["Equity"].round(0).tolist(),
        "cumulative_return": chart_df["cumulative_return"].round(2).tolist(),
        "drawdown": chart_df["drawdown"].round(2).tolist(),
        "rolling_vol": chart_df["rolling_vol_30d"].fillna(0).round(1).tolist(),
        "rolling_sharpe": chart_df["rolling_sharpe_30d"].fillna(0).round(2).tolist(),
        "metadata": {
            "start_date": chart_df["Date"].iloc[0].strftime("%Y-%m-%d"),
            "end_date": chart_df["Date"].iloc[-1].strftime("%Y-%m-%d"),
            "initial_equity": initial_equity,
            "final_equity": float(chart_df["Equity"].iloc[-1]),
            "total_return": float(chart_df["cumulative_return"].iloc[-1]),
            "max_drawdown": float(chart_df["drawdown"].min()),
            "data_points": int(len(chart_df)),
        },
    }

    os.makedirs("data/processed/cache", exist_ok=True)
    chart_file = "data/processed/cache/pnl_chart_data.json"
    with open(chart_file, "w") as f:
        json.dump(chart_data, f, indent=2)

    print(f"   ✅ Generated P&L chart data: {len(chart_df)} points")
    print(f"   📊 Total return: {chart_data['metadata']['total_return']:.1f}%")
    print(f"   📉 Max drawdown: {chart_data['metadata']['max_drawdown']:.1f}%")
    print(f"   💾 Saved to: {chart_file}")

    return chart_data


def main() -> Dict[str, Any]:
    return generate_pnl_chart_data()


if __name__ == "__main__":
    main()
