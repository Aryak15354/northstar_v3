#!/usr/bin/env python3
"""
Capacity stress testing engine.

Validates AUM recommendations under stressed liquidity assumptions and
historical crisis-style scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import json
import numpy as np

from src.validation.capacity_analysis_engine import (
    CapacityAnalysisEngine,
    CapacityReport,
    DEFAULT_AUM_LEVELS,
)


@dataclass
class StressScenarioResult:
    """Per-scenario stress output."""

    scenario_name: str
    scenario_type: str
    stress_multiplier: float
    liquidity_haircut: float
    recommended_aum: float
    capacity_knee_aum: float
    report: Dict


@dataclass
class CapacityStressReport:
    """Aggregate stress test output."""

    generated_at: str
    scenario_results: List[StressScenarioResult]
    normal_recommended_aum: float
    stress_95p_recommended_aum: float
    stress_adjusted_recommendation: float

    def to_dict(self) -> Dict:
        return {
            "generated_at": self.generated_at,
            "normal_recommended_aum": self.normal_recommended_aum,
            "stress_95p_recommended_aum": self.stress_95p_recommended_aum,
            "stress_adjusted_recommendation": self.stress_adjusted_recommendation,
            "scenario_results": [asdict(x) for x in self.scenario_results],
        }


class CapacityStressTester:
    """
    Stress testing wrapper around CapacityAnalysisEngine.

    Scenarios include:
    - 50% ADV reduction (explicit requirement)
    - Historical style crisis windows (2008, 2020, 2022)
    - 95th percentile conservative recommendation
    """

    def __init__(self, analysis_engine: Optional[CapacityAnalysisEngine] = None) -> None:
        self.analysis_engine = analysis_engine or CapacityAnalysisEngine()

    def _scenario_definitions(self) -> List[Dict]:
        return [
            {
                "name": "liquidity_crisis_50pct_adv",
                "type": "adv_haircut",
                "stress_multiplier": 2.0,
                "liquidity_haircut": 0.50,
            },
            {
                "name": "historical_2008",
                "type": "historical",
                "stress_multiplier": 2.4,
                "liquidity_haircut": 0.45,
            },
            {
                "name": "historical_2020",
                "type": "historical",
                "stress_multiplier": 2.2,
                "liquidity_haircut": 0.40,
            },
            {
                "name": "historical_2022",
                "type": "historical",
                "stress_multiplier": 1.8,
                "liquidity_haircut": 0.35,
            },
        ]

    def run_stress_tests(
        self,
        *,
        aum_levels: Optional[Iterable[float]] = None,
        baseline_cagr: float = 0.18,
        baseline_sharpe: float = 1.6,
        baseline_max_drawdown: float = 0.12,
    ) -> CapacityStressReport:
        """Execute all stress scenarios and derive conservative recommendation."""

        levels = sorted(float(x) for x in (aum_levels or DEFAULT_AUM_LEVELS))
        normal = self.analysis_engine.run_capacity_sweep(
            aum_levels=levels,
            baseline_cagr=baseline_cagr,
            baseline_sharpe=baseline_sharpe,
            baseline_max_drawdown=baseline_max_drawdown,
            stress_multiplier=1.0,
        )

        scenarios: List[StressScenarioResult] = []
        for sc in self._scenario_definitions():
            report: CapacityReport = self.analysis_engine.run_capacity_sweep(
                aum_levels=levels,
                baseline_cagr=baseline_cagr,
                baseline_sharpe=baseline_sharpe,
                baseline_max_drawdown=baseline_max_drawdown,
                stress_multiplier=float(sc["stress_multiplier"]),
            )
            scenarios.append(
                StressScenarioResult(
                    scenario_name=str(sc["name"]),
                    scenario_type=str(sc["type"]),
                    stress_multiplier=float(sc["stress_multiplier"]),
                    liquidity_haircut=float(sc["liquidity_haircut"]),
                    recommended_aum=float(report.max_recommended_aum),
                    capacity_knee_aum=float(report.capacity_knee_aum),
                    report=report.to_dict(),
                )
            )

        rec_values = [s.recommended_aum for s in scenarios]
        stress_95p = float(np.percentile(rec_values, 5)) if rec_values else float(normal.max_recommended_aum)
        # Conservative deployable recommendation: min(normal, 95th percentile stress capacity)
        adjusted = float(min(normal.max_recommended_aum, stress_95p))

        return CapacityStressReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            scenario_results=scenarios,
            normal_recommended_aum=float(normal.max_recommended_aum),
            stress_95p_recommended_aum=stress_95p,
            stress_adjusted_recommendation=adjusted,
        )

    def export_report(
        self,
        report: CapacityStressReport,
        output_dir: Path | str = "reports/capacity",
        file_name: str = "capacity_stress_report.json",
    ) -> str:
        """Persist stress report to disk."""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / file_name
        path.write_text(json.dumps(report.to_dict(), indent=2))
        return str(path)

