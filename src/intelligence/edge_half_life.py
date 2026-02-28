#!/usr/bin/env python3
"""
🧬 EDGE HALF-LIFE TRACKER
Real-data-only edge decay estimation for strategies.

Outputs:
- data/processed/edge_half_life.json
- data/processed/edge_half_life.parquet
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

import numpy as np
import pandas as pd


@dataclass
class EdgeHalfLifeResult:
    strategy: str
    edge_peak: float
    decay_rate: float
    half_life_days: float
    remaining_half_life: float
    edge_health: float
    status: str
    last_updated: str


class EdgeHalfLifeTracker:
    def __init__(self) -> None:
        self.backtests_dir = Path("data/processed/backtests")
        self.benchmark_paths = [
            Path("data/processed/nifty.parquet"),
            Path("data/processed/index_data/nifty_50.parquet"),
        ]
        self.output_json = Path("data/processed/edge_half_life.json")
        self.output_parquet = Path("data/processed/edge_half_life.parquet")

        self.params = {
            "lookback_days": 120,
            "edge_window": 30,
            "min_points": 30,
            "expected_horizon": 30,
            "min_edge": 1e-6,
        }

    def _load_benchmark(self) -> Optional[pd.Series]:
        for path in self.benchmark_paths:
            if not path.exists():
                continue
            try:
                df = pd.read_parquet(path)
            except Exception:
                continue
            if df.empty:
                continue
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
                df = df.dropna(subset=["Date"]).sort_values("Date").set_index("Date")
            else:
                df.index = pd.to_datetime(df.index, errors="coerce")
            for col in ["Close", "close", "Adj Close", "adj_close"]:
                if col in df.columns:
                    series = df[col].dropna()
                    return series
        return None

    def _edge_series(self, strat_df: pd.DataFrame, bench_series: Optional[pd.Series]) -> Optional[pd.Series]:
        if strat_df.empty:
            return None
        if "date" in strat_df.columns:
            strat_df["date"] = pd.to_datetime(strat_df["date"], errors="coerce")
            strat_df = strat_df.dropna(subset=["date"]).sort_values("date")
            strat_df = strat_df.set_index("date")
        elif "Date" in strat_df.columns:
            strat_df["Date"] = pd.to_datetime(strat_df["Date"], errors="coerce")
            strat_df = strat_df.dropna(subset=["Date"]).sort_values("Date")
            strat_df = strat_df.set_index("Date")
        else:
            return None

        if "daily_return" not in strat_df.columns:
            return None

        strat_returns = pd.to_numeric(strat_df["daily_return"], errors="coerce").dropna()
        if strat_returns.empty:
            return None

        if bench_series is None or bench_series.empty:
            bench_returns = pd.Series(0.0, index=strat_returns.index)
        else:
            bench_returns = bench_series.pct_change().reindex(strat_returns.index).fillna(0.0)

        excess = strat_returns - bench_returns
        vol = strat_returns.rolling(self.params["edge_window"]).std().replace(0, np.nan)
        edge = (excess.rolling(self.params["edge_window"]).mean() / vol).dropna()
        return edge

    def _fit_decay(self, edge: pd.Series) -> Dict[str, float]:
        if edge.empty or len(edge) < self.params["min_points"]:
            return {"decay_rate": np.nan, "half_life": np.nan, "remaining": np.nan, "edge_peak": np.nan}

        edge = edge[edge > self.params["min_edge"]]
        if edge.empty:
            return {"decay_rate": np.nan, "half_life": np.nan, "remaining": np.nan, "edge_peak": np.nan}

        peak_idx = edge.idxmax()
        peak_val = float(edge.loc[peak_idx])
        tail = edge.loc[peak_idx:]
        if len(tail) < max(10, self.params["min_points"] // 2):
            return {"decay_rate": np.nan, "half_life": np.nan, "remaining": np.nan, "edge_peak": peak_val}

        t = np.arange(len(tail))
        y = np.log(np.maximum(tail.values, self.params["min_edge"]))
        try:
            slope, intercept = np.polyfit(t, y, 1)
        except Exception:
            return {"decay_rate": np.nan, "half_life": np.nan, "remaining": np.nan, "edge_peak": peak_val}

        decay_rate = float(max(0.0, -slope))
        half_life = float(np.log(2) / decay_rate) if decay_rate > 0 else np.nan
        age = float(len(edge.loc[peak_idx:]) - 1)
        remaining = float(max(0.0, half_life - age)) if half_life == half_life else np.nan
        return {
            "decay_rate": decay_rate,
            "half_life": half_life,
            "remaining": remaining,
            "edge_peak": peak_val,
        }

    def compute(self) -> Dict[str, EdgeHalfLifeResult]:
        bench = self._load_benchmark()
        results: Dict[str, EdgeHalfLifeResult] = {}

        if not self.backtests_dir.exists():
            return results

        for path in self.backtests_dir.glob("*.parquet"):
            strategy = path.stem
            try:
                df = pd.read_parquet(path)
            except Exception:
                continue

            if df.empty:
                continue

            # Reduce to lookback window
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                df = df.dropna(subset=["date"]).sort_values("date")
                df = df.tail(self.params["lookback_days"])

            edge = self._edge_series(df, bench)
            if edge is None or edge.empty:
                results[strategy] = EdgeHalfLifeResult(
                    strategy=strategy,
                    edge_peak=0.0,
                    decay_rate=0.0,
                    half_life_days=0.0,
                    remaining_half_life=0.0,
                    edge_health=0.35,
                    status="insufficient_data",
                    last_updated=datetime.now().isoformat(),
                )
                continue

            decay = self._fit_decay(edge)
            half_life = decay.get("half_life")
            remaining = decay.get("remaining")
            edge_peak = decay.get("edge_peak", 0.0)
            if half_life != half_life or remaining != remaining:  # NaN check
                edge_health = 0.35
                status = "insufficient_data"
                half_life = 0.0
                remaining = 0.0
            else:
                horizon = self.params["expected_horizon"]
                edge_health = float(min(1.0, max(0.0, remaining / max(1.0, horizon))))
                status = "ok"

            results[strategy] = EdgeHalfLifeResult(
                strategy=strategy,
                edge_peak=float(edge_peak),
                decay_rate=float(decay.get("decay_rate", 0.0)),
                half_life_days=float(half_life),
                remaining_half_life=float(remaining),
                edge_health=edge_health,
                status=status,
                last_updated=datetime.now().isoformat(),
            )

        return results

    def save(self, results: Dict[str, EdgeHalfLifeResult]) -> None:
        payload = {
            "timestamp": datetime.now().isoformat(),
            "strategies": {
                k: {
                    "edge_peak": v.edge_peak,
                    "decay_rate": v.decay_rate,
                    "half_life_days": v.half_life_days,
                    "remaining_half_life": v.remaining_half_life,
                    "edge_health": v.edge_health,
                    "status": v.status,
                    "last_updated": v.last_updated,
                }
                for k, v in results.items()
            },
        }
        self.output_json.parent.mkdir(parents=True, exist_ok=True)
        self.output_json.write_text(json.dumps(payload, indent=2))

        if results:
            df = pd.DataFrame(
                [
                    {
                        "strategy": k,
                        "edge_peak": v.edge_peak,
                        "decay_rate": v.decay_rate,
                        "half_life_days": v.half_life_days,
                        "remaining_half_life": v.remaining_half_life,
                        "edge_health": v.edge_health,
                        "status": v.status,
                        "last_updated": v.last_updated,
                    }
                    for k, v in results.items()
                ]
            )
            df.to_parquet(self.output_parquet, index=False)

    def run(self) -> Dict[str, EdgeHalfLifeResult]:
        results = self.compute()
        self.save(results)
        return results


def main() -> None:
    tracker = EdgeHalfLifeTracker()
    tracker.run()


if __name__ == "__main__":
    main()
