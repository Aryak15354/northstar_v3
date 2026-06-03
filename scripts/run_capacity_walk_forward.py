#!/usr/bin/env python3
"""
Run capacity-aware walk-forward summary.

Integrates capacity components with the existing portfolio artifacts and emits
constrained vs unconstrained comparison outputs.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.intelligence.adv_database import ADVConfig, ADVDatabase
from src.intelligence.position_governor import GovernorConfig, PositionGovernor
from src.portfolio.liquidity_aware_constructor import LiquidityAwarePortfolioConstructor
from src.validation.capacity_analysis_engine import CapacityAnalysisEngine


def _load_target_weights() -> Dict[str, float]:
    weights_path = PROJECT_ROOT / "data/processed/portfolio_weights.parquet"
    if not weights_path.exists():
        return {}
    df = pd.read_parquet(weights_path)
    if df.empty:
        return {}
    weight_col = "weight" if "weight" in df.columns else "final_weight"
    df[weight_col] = pd.to_numeric(df[weight_col], errors="coerce")
    df = df.dropna(subset=[weight_col, "ticker"])
    out = {}
    for _, row in df.iterrows():
        out[str(row["ticker"])] = float(row[weight_col])
    # normalize long-only to <= 1
    gross = sum(max(0.0, w) for w in out.values())
    if gross > 1.0 and gross > 0:
        scale = 1.0 / gross
        out = {k: max(0.0, v) * scale for k, v in out.items()}
    return out


def _seed_adv_database(symbols: Dict[str, float], adv_db: ADVDatabase) -> None:
    prices_path = PROJECT_ROOT / "data/processed/prices.parquet"
    if not prices_path.exists():
        return
    prices = pd.read_parquet(prices_path)
    if prices.empty or "ticker" not in prices.columns:
        return

    prices["Date"] = pd.to_datetime(prices["Date"], errors="coerce")
    prices = prices.dropna(subset=["Date"])

    for symbol in symbols.keys():
        sdf = prices[prices["ticker"] == symbol].copy()
        if sdf.empty:
            continue
        if "Volume" not in sdf.columns or "Close" not in sdf.columns:
            continue
        volume_data = sdf[["Date", "Volume"]].rename(columns={"Date": "date", "Volume": "volume"})
        price_data = sdf[["Date", "Close"]].rename(columns={"Date": "date", "Close": "close"})
        adv_db.add_volume_data(symbol, volume_data, price_data)


def _load_market_stress() -> bool:
    state_path = PROJECT_ROOT / "data/processed/market_state.parquet"
    if not state_path.exists():
        return False
    df = pd.read_parquet(state_path)
    if df.empty:
        return False
    row = df.iloc[-1]
    risk_on = pd.to_numeric(row.get("risk_on_probability", row.get("risk_on", 0.5)), errors="coerce")
    risk_on_value = float(risk_on) if pd.notna(risk_on) else 0.5
    return bool(risk_on_value < 0.40)


def run(aum: float) -> Dict:
    target_weights = _load_target_weights()
    if not target_weights:
        raise RuntimeError("No target weights found at data/processed/portfolio_weights.parquet")

    adv_db = ADVDatabase(
        ADVConfig(
            # Institutional liquidity floors (INR notional ADV).
            min_adv_threshold=25_000_000,   # ₹2.5 Cr minimum tradable ADV
            mid_cap_threshold=100_000_000,  # ₹10 Cr
            large_cap_threshold=500_000_000,  # ₹50 Cr
        )
    )
    _seed_adv_database(target_weights, adv_db)

    governor = PositionGovernor(
        adv_db,
        GovernorConfig(
            alpha_factors={
                "large_cap": 0.05,
                "mid_cap": 0.03,
                "small_cap": 0.01,
                "default": 0.03,
            }
        ),
    )
    constructor = LiquidityAwarePortfolioConstructor(
        adv_database=adv_db,
        position_governor=governor,
        min_cash_buffer=0.20,
    )

    stress = _load_market_stress()
    constrained = constructor.construct_portfolio(
        target_weights=target_weights,
        portfolio_value=float(aum),
        market_stress=stress,
        as_of_date=datetime.now(),
    )

    unconstrained_gross = float(sum(max(0.0, w) for w in target_weights.values()))
    constrained_gross = float(sum(max(0.0, w) for k, w in constrained.weights.items() if k != "CASH"))

    capacity_engine = CapacityAnalysisEngine()
    capacity_report = capacity_engine.run_capacity_sweep()
    exports = capacity_engine.export_capacity_curves(
        capacity_report,
        output_dir=PROJECT_ROOT / "reports/capacity",
        file_stem="capacity_walk_forward_curves",
    )

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "aum": float(aum),
        "market_stress_detected": stress,
        "unconstrained": {
            "positions": len(target_weights),
            "gross_invested": unconstrained_gross,
        },
        "constrained": {
            "positions": len([k for k, w in constrained.weights.items() if k != "CASH" and w > 0]),
            "gross_invested": constrained_gross,
            "cash_weight": constrained.cash_weight,
            "rejected_positions": constrained.rejected_positions,
            "capped_positions": constrained.capped_positions,
            "redistributed_weight": constrained.redistributed_weight,
        },
        "capacity_recommendation": {
            "capacity_knee_aum": capacity_report.capacity_knee_aum,
            "max_recommended_aum": capacity_report.max_recommended_aum,
        },
        "exports": exports,
    }

    out_dir = PROJECT_ROOT / "reports/capacity"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "capacity_walk_forward_report.json"
    out_file.write_text(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run capacity-aware walk-forward summary.")
    parser.add_argument("--aum", type=float, default=100_000_000, help="AUM level for constrained portfolio construction")
    args = parser.parse_args()

    summary = run(args.aum)
    print("✅ Capacity walk-forward run complete")
    print(f"   AUM: ${summary['aum']:,.0f}")
    print(f"   Constrained positions: {summary['constrained']['positions']}")
    print(f"   Cash weight: {summary['constrained']['cash_weight']:.2%}")
    print(
        "   Capacity knee: "
        f"${summary['capacity_recommendation']['capacity_knee_aum']:,.0f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
