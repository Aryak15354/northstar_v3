#!/usr/bin/env python3
"""
Multi-Timeline Walk-Forward Engine - real-data-only implementation.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class MultiTimelineWalkForwardConfig:
    """Configuration for multi-timeline walk-forward validation."""

    validation_periods: List[str] = field(
        default_factory=lambda: ["crisis_2008", "recovery_2009", "covid_crash_2020", "inflation_shock_2022"]
    )
    walk_forward_window_months: int = 6
    rebalance_frequency_days: int = 7
    min_period_success_rate: float = 0.6
    min_observations_per_period: int = 20
    output_base_path: str = "data/validation/multi_timeline"
    results_filename: str = "multi_timeline_walk_forward_results.json"
    pnl_source_path: str = "data/portfolio/pnl_on_paper.parquet"


class MultiTimelineWalkForwardEngine:
    """Multi-Timeline Walk-Forward Validation Engine."""

    PERIODS: Dict[str, Dict[str, str]] = {
        "crisis_2008": {"name": "Financial Crisis 2008", "start": "2008-01-01", "end": "2009-03-31"},
        "recovery_2009": {"name": "Recovery 2009-2010", "start": "2009-04-01", "end": "2010-12-31"},
        "covid_crash_2020": {"name": "COVID Crisis 2020", "start": "2020-02-01", "end": "2020-06-30"},
        "inflation_shock_2022": {"name": "Inflation Shock 2022", "start": "2022-01-01", "end": "2022-12-31"},
    }

    def __init__(self, config: Optional[MultiTimelineWalkForwardConfig] = None):
        self.name = "Multi-Timeline Walk-Forward Validation Engine"
        self.version = "4.4.0"
        self.config = config or MultiTimelineWalkForwardConfig()
        os.makedirs(self.config.output_base_path, exist_ok=True)
        print(f"🔄 {self.name} v{self.version} initialized")

    def _load_real_returns(self) -> pd.Series:
        path = self.config.pnl_source_path
        if not os.path.exists(path):
            raise FileNotFoundError(f"PnL source not found for multi-timeline validation: {path}")

        df = pd.read_parquet(path)
        if df.empty:
            raise ValueError(f"PnL source is empty: {path}")

        dcol = "Date" if "Date" in df.columns else ("date" if "date" in df.columns else None)
        if dcol is None:
            raise ValueError("PnL source missing date column (Date/date)")

        df[dcol] = pd.to_datetime(df[dcol], errors="coerce")
        df = df.dropna(subset=[dcol]).sort_values(dcol)
        if df.empty:
            raise ValueError("PnL source has no valid dates")

        if "Return" in df.columns:
            r = pd.to_numeric(df["Return"], errors="coerce")
        elif "daily_return" in df.columns:
            r = pd.to_numeric(df["daily_return"], errors="coerce")
        else:
            nav_col = None
            for c in ["Equity", "equity", "portfolio_value", "nav", "NAV"]:
                if c in df.columns:
                    nav_col = c
                    break
            if nav_col is None:
                raise ValueError("PnL source missing Return/daily_return and NAV columns")
            nav = pd.to_numeric(df[nav_col], errors="coerce")
            r = nav.pct_change()

        out = pd.Series(r.values, index=df[dcol]).dropna()
        out = out.replace([np.inf, -np.inf], np.nan).dropna().sort_index()
        if out.empty:
            raise ValueError("PnL source has no valid returns")
        return out

    @staticmethod
    def _max_drawdown(returns: pd.Series) -> float:
        nav = (1.0 + returns).cumprod()
        peak = nav.cummax()
        dd = (nav / peak) - 1.0
        return float(dd.min()) if not dd.empty else 0.0

    @staticmethod
    def _score_period(total_return: float, sharpe: float, max_drawdown: float) -> float:
        sharpe_score = float(np.clip((sharpe + 1.0) / 2.0, 0.0, 1.0))
        drawdown_score = float(np.clip(1.0 - abs(max_drawdown) / 0.35, 0.0, 1.0))
        return_score = float(np.clip((total_return + 0.20) / 0.40, 0.0, 1.0))
        return float(0.45 * sharpe_score + 0.35 * drawdown_score + 0.20 * return_score)

    def run_multi_timeline_validation(self) -> Dict[str, Any]:
        """Run comprehensive multi-timeline walk-forward validation."""
        print("🔄 MULTI-TIMELINE WALK-FORWARD VALIDATION ENGINE")
        print("=" * 70)

        selected_periods = {
            k: v for k, v in self.PERIODS.items() if k in self.config.validation_periods
        }
        print(f"🎯 Validating {len(selected_periods)} periods")
        if not selected_periods:
            raise ValueError("No validation periods selected")

        returns = self._load_real_returns()
        periods_passed = 0
        period_results: Dict[str, Dict[str, Any]] = {}

        for period_name, period_config in selected_periods.items():
            start = pd.Timestamp(period_config["start"])
            end = pd.Timestamp(period_config["end"])
            period_ret = returns[(returns.index >= start) & (returns.index <= end)]

            if len(period_ret) < int(self.config.min_observations_per_period):
                period_results[period_name] = {
                    "period_name": period_name,
                    "validation_score": 0.0,
                    "validation_passed": False,
                    "status": "insufficient_data",
                    "observations": int(len(period_ret)),
                    "required_observations": int(self.config.min_observations_per_period),
                }
                print(
                    f"   ❌ FAILED {period_config['name']}: insufficient data "
                    f"({len(period_ret)}/{self.config.min_observations_per_period})"
                )
                continue

            total_return = float((1.0 + period_ret).prod() - 1.0)
            vol = float(period_ret.std() * np.sqrt(252))
            ann_return = float((1.0 + total_return) ** (252.0 / max(1.0, len(period_ret))) - 1.0)
            sharpe = float(ann_return / vol) if vol > 0 else 0.0
            max_dd = self._max_drawdown(period_ret)
            score = self._score_period(total_return=total_return, sharpe=sharpe, max_drawdown=max_dd)
            passed = bool(score >= self.config.min_period_success_rate)

            period_results[period_name] = {
                "period_name": period_name,
                "validation_score": score,
                "validation_passed": passed,
                "status": "evaluated",
                "observations": int(len(period_ret)),
                "total_return": total_return,
                "annualized_return": ann_return,
                "sharpe_ratio": sharpe,
                "max_drawdown": max_dd,
            }

            if passed:
                periods_passed += 1
            status_icon = "✅ PASSED" if passed else "❌ FAILED"
            print(f"   {status_icon} {period_config['name']}: {score:.3f}")

        total_periods = len(selected_periods)
        success_rate = periods_passed / total_periods if total_periods > 0 else 0.0
        result = {
            "validation_id": f"multi_timeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "periods_tested": total_periods,
            "periods_passed": periods_passed,
            "success_rate": success_rate,
            "overall_validation_status": "passed"
            if success_rate >= self.config.min_period_success_rate
            else "failed",
            "overall_consistency_score": success_rate,
            "period_results": period_results,
            "data_source": self.config.pnl_source_path,
        }

        out_path = os.path.join(self.config.output_base_path, self.config.results_filename)
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2, default=str)

        print(f"\n🎯 Overall Status: {result['overall_validation_status'].upper()}")
        print(f"📊 Success Rate: {success_rate:.1%} ({periods_passed}/{total_periods} periods)")
        return result

    def run_consistency_analysis(self, validation_result: Dict[str, Any]) -> Dict[str, Any]:
        """Run cross-timeline consistency analysis from real validation outputs."""
        print("\n🔄 Running cross-timeline consistency analysis...")
        scores = [
            float(v.get("validation_score", 0.0))
            for v in validation_result.get("period_results", {}).values()
            if v.get("status") == "evaluated"
        ]
        avg_score = float(np.mean(scores)) if scores else 0.0
        level = "high" if avg_score >= 0.75 else ("medium" if avg_score >= 0.60 else "low")
        results = {
            "overall_consistency_level": level,
            "overall_consistency_score": avg_score,
            "evaluated_periods": int(len(scores)),
        }
        print("   ✅ Consistency analysis completed")
        return results

    def run_complete_validation(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Run complete multi-timeline walk-forward validation."""
        print("🚀 COMPLETE MULTI-TIMELINE WALK-FORWARD VALIDATION")
        print("=" * 70)
        validation_result = self.run_multi_timeline_validation()
        consistency_results = self.run_consistency_analysis(validation_result)
        print(f"\n✅ Multi-timeline validation: {validation_result['overall_validation_status']}")
        print(f"🔄 Overall consistency: {consistency_results['overall_consistency_level']}")
        return validation_result, consistency_results


def create_default_config() -> MultiTimelineWalkForwardConfig:
    return MultiTimelineWalkForwardConfig()


def main() -> bool:
    config = create_default_config()
    engine = MultiTimelineWalkForwardEngine(config)
    validation_result, _ = engine.run_complete_validation()
    return validation_result["overall_validation_status"] == "passed"


if __name__ == "__main__":
    main()
