#!/usr/bin/env python3
"""
📊 REAL DATA LOADER
Loads real performance/validation artifacts for optional dashboard panels.
No synthetic or mock data is generated.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List

import json
import pandas as pd


@dataclass
class RealDataLoader:
    project_root: Path | None = None

    def __post_init__(self) -> None:
        if self.project_root is None:
            self.project_root = Path(__file__).resolve().parents[2]

    def _read_json(self, rel: str) -> Dict[str, Any]:
        path = self.project_root / rel
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}

    def _read_csv(self, rel: str) -> pd.DataFrame:
        path = self.project_root / rel
        if not path.exists():
            return pd.DataFrame()
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()

    def _latest_json(self, pattern: str) -> Dict[str, Any]:
        candidates = list((self.project_root / pattern).parent.glob(Path(pattern).name))
        if not candidates:
            return {}
        latest = max(candidates, key=lambda p: p.stat().st_mtime)
        try:
            return json.loads(latest.read_text())
        except Exception:
            return {}

    def load_validation_reports(self) -> Dict[str, Any]:
        reports: Dict[str, Any] = {}
        # Prefer most recent stress + walk-forward
        reports["stress_test"] = self._latest_json("reports/validation/stress_test_report_*.json")
        reports["walk_forward"] = self._latest_json("reports/validation/walk_forward_analysis_report_*.json")
        # Optional: simple institutional validation
        inst = self._read_json("reports/validation/simple_institutional_validation.json")
        if inst:
            reports["institutional"] = inst
        return reports

    def load_backtests(self) -> Dict[str, pd.DataFrame]:
        backtests: Dict[str, pd.DataFrame] = {}
        for rel in [
            "analysis_results/backtests/northstar_3year_backtest_real_data.csv",
            "analysis_results/backtests/northstar_3year_backtest_results.csv",
            "analysis_results/backtests/northstar_all_strategies_3year_backtest.csv",
        ]:
            df = self._read_csv(rel)
            if not df.empty:
                backtests[Path(rel).stem] = df
        return backtests

    def load_performance_reports(self) -> Dict[str, Any]:
        reports: Dict[str, Any] = {}
        # Keep flexible; only include files that exist
        for rel in [
            "reports/performance/TASK6_PERFORMANCE_MONITOR_DEMO_20260105_052741.json",
            "reports/production_deployment/production_deployment_report_20260119_145646.json",
        ]:
            data = self._read_json(rel)
            if data:
                reports[Path(rel).stem] = data
        return reports

    def get_comprehensive_data(self) -> Dict[str, Any]:
        return {
            "validation_reports": self.load_validation_reports(),
            "backtests": self.load_backtests(),
            "performance_reports": self.load_performance_reports(),
        }

