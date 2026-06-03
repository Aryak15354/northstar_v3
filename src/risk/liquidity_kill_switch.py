#!/usr/bin/env python3
"""
💧 LIQUIDITY KILL SWITCH
Real-data-only liquidity risk assessment for portfolio exits.

Outputs:
- data/processed/liquidity_risk.parquet
- data/processed/liquidity_risk.json
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import numpy as np
import pandas as pd


@dataclass
class LiquidityConfig:
    adv_window: int = 20
    impact_k: float = 0.005
    impact_beta: float = 0.6
    default_spread: float = 0.002
    min_expected_edge: float = 0.001
    freeze_threshold: float = 1.0
    dangerous_threshold: float = 0.8


class LiquidityRiskAssessor:
    def __init__(self, config: Optional[LiquidityConfig] = None) -> None:
        self.config = config or LiquidityConfig()
        self.paths = {
            "prices": Path("data/processed/prices.parquet"),
            "portfolio": Path("data/processed/portfolio_weights.parquet"),
            "pnl": Path("data/portfolio/pnl_on_paper.parquet"),
            "output_json": Path("data/processed/liquidity_risk.json"),
            "output_parquet": Path("data/processed/liquidity_risk.parquet"),
        }

    def _load_prices(self) -> Optional[pd.DataFrame]:
        if not self.paths["prices"].exists():
            return None
        try:
            df = pd.read_parquet(self.paths["prices"])
        except Exception:
            return None
        if df.empty:
            return None
        # Normalize columns
        if "Date" not in df.columns and "date" in df.columns:
            df = df.rename(columns={"date": "Date"})
        if "ticker" not in df.columns and "Symbol" in df.columns:
            df = df.rename(columns={"Symbol": "ticker"})
        if "ticker" not in df.columns and "Ticker" in df.columns:
            df = df.rename(columns={"Ticker": "ticker"})
        if "ticker" in df.columns:
            # Many portfolio artifacts store symbols without `.NS` while prices use `.NS`.
            df["symbol_base"] = df["ticker"].astype(str).str.strip().str.replace(".NS", "", regex=False)
        return df

    def _load_portfolio(self) -> Optional[pd.DataFrame]:
        if not self.paths["portfolio"].exists():
            return None
        try:
            df = pd.read_parquet(self.paths["portfolio"])
        except Exception:
            return None
        if df.empty:
            return None
        if "ticker" not in df.columns and "symbol" in df.columns:
            df = df.rename(columns={"symbol": "ticker"})
        weight_col = None
        for c in ["final_weight", "weight", "allocation", "w"]:
            if c in df.columns:
                weight_col = c
                break
        if weight_col is None:
            return None
        df["weight"] = pd.to_numeric(df[weight_col], errors="coerce")
        df = df.dropna(subset=["weight"])
        return df[["ticker", "weight"]]

    def _load_equity(self) -> float:
        if not self.paths["pnl"].exists():
            return 1.0
        try:
            df = pd.read_parquet(self.paths["pnl"])
        except Exception:
            return 1.0
        if df.empty or "Equity" not in df.columns:
            return 1.0
        return float(df["Equity"].iloc[-1])

    def _expected_edge(self, price_series: pd.Series) -> float:
        returns = price_series.pct_change().dropna()
        if returns.empty:
            return self.config.min_expected_edge
        expected = float(np.abs(returns.tail(self.config.adv_window).mean()))
        return max(expected, self.config.min_expected_edge)

    def compute(self) -> Optional[pd.DataFrame]:
        prices = self._load_prices()
        portfolio = self._load_portfolio()
        if prices is None or portfolio is None:
            return None

        prices["Date"] = pd.to_datetime(prices["Date"], errors="coerce")
        prices = prices.dropna(subset=["Date", "ticker"]).sort_values("Date")

        equity = self._load_equity()
        results = []

        for _, row in portfolio.iterrows():
            ticker = str(row["ticker"]).strip()
            symbol_base = ticker.replace(".NS", "").strip()
            weight = float(row["weight"])
            if weight <= 0:
                continue
            if "symbol_base" in prices.columns:
                px = prices[prices["symbol_base"] == symbol_base]
            else:
                px = prices[prices["ticker"] == ticker]
            if px.empty:
                continue
            px = px.tail(self.config.adv_window)
            if px.empty:
                continue

            latest = px.iloc[-1]
            price = float(latest.get("Close", np.nan))
            volume = float(latest.get("Volume", np.nan))
            if not np.isfinite(price) or price <= 0:
                continue

            adv_shares = float(px["Volume"].mean()) if "Volume" in px.columns else np.nan
            if not np.isfinite(adv_shares) or adv_shares <= 0:
                continue

            position_value = equity * weight
            shares = position_value / price
            participation = shares / adv_shares

            impact_cost = self.config.impact_k * (participation ** self.config.impact_beta)
            spread = self.config.default_spread

            exp_edge = self._expected_edge(px["Close"])
            exit_risk = (impact_cost + spread) / exp_edge

            status = "NORMAL"
            if exit_risk >= self.config.freeze_threshold:
                status = "FROZEN"
            elif exit_risk >= self.config.dangerous_threshold:
                status = "DANGEROUS"

            results.append(
                {
                    "ticker": ticker,
                    "weight": weight,
                    "price": price,
                    "adv_shares": adv_shares,
                    "participation": participation,
                    "impact_cost": impact_cost,
                    "spread": spread,
                    "expected_edge": exp_edge,
                    "exit_risk": exit_risk,
                    "status": status,
                    "timestamp": datetime.now().isoformat(),
                }
            )

        if not results:
            return None

        return pd.DataFrame(results)

    def save(self, df: pd.DataFrame) -> None:
        out_json = self.paths["output_json"]
        out_parquet = self.paths["output_parquet"]
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_parquet.parent.mkdir(parents=True, exist_ok=True)

        summary = {
            "timestamp": datetime.now().isoformat(),
            "positions": len(df),
            "frozen": int((df["status"] == "FROZEN").sum()),
            "dangerous": int((df["status"] == "DANGEROUS").sum()),
            "avg_exit_risk": float(df["exit_risk"].mean()),
        }

        out_json.write_text(json.dumps({"summary": summary, "rows": df.to_dict("records")}, indent=2))
        df.to_parquet(out_parquet, index=False)

    def run(self) -> Optional[pd.DataFrame]:
        df = self.compute()
        if df is None or df.empty:
            return None
        self.save(df)
        return df


def main() -> None:
    assessor = LiquidityRiskAssessor()
    assessor.run()


if __name__ == "__main__":
    main()
