#!/usr/bin/env python3
"""
Capacity analysis engine.

Runs systematic AUM sweeps, measures strategy degradation, and identifies
the capacity knee for fund-grade deployment guidance.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import json
import math

import numpy as np
import pandas as pd


DEFAULT_AUM_LEVELS: List[float] = [
    25e6, 50e6, 75e6, 100e6, 150e6, 200e6, 300e6, 400e6, 500e6, 650e6, 800e6, 1e9
]


@dataclass
class CapacityMetrics:
    """Per-AUM capacity metrics."""

    aum: float
    cagr: float
    sharpe: float
    max_drawdown: float
    implementation_shortfall: float
    turnover_penalty: float
    stress_multiplier: float = 1.0


@dataclass
class CapacityReport:
    """Aggregate capacity report with recommendation fields."""

    generated_at: str
    baseline_cagr: float
    baseline_sharpe: float
    metrics: List[CapacityMetrics]
    capacity_knee_aum: float
    max_recommended_aum: float
    stress_adjusted_recommended_aum: float

    def to_dict(self) -> Dict:
        payload = asdict(self)
        payload["metrics"] = [asdict(m) for m in self.metrics]
        return payload


class CapacityAnalysisEngine:
    """
    Systematic AUM scaling engine for deployable-capacity discovery.

    This module intentionally uses conservative degradations so the reported
    AUM guidance remains on the safe side.
    """

    def __init__(self, aum_levels: Optional[Iterable[float]] = None) -> None:
        levels = list(aum_levels) if aum_levels is not None else DEFAULT_AUM_LEVELS
        if not levels:
            raise ValueError("aum_levels must be non-empty")
        self.aum_levels: List[float] = sorted(float(x) for x in levels)

    @staticmethod
    def _degradation_curve(aum: float, stress_multiplier: float = 1.0) -> Dict[str, float]:
        """
        Conservative degradation model vs AUM.

        Returns normalized penalties in [0, +inf).
        """

        scale = max(1.0, float(aum) / 1e8)
        # Liquidity/impact pressure grows super-linearly with size.
        impact_drag = 0.012 * (scale ** 1.20) * stress_multiplier
        crowding_drag = 0.006 * (scale ** 1.10) * stress_multiplier
        turnover_penalty = 0.009 * (max(0.0, scale - 1.0) ** 1.15) * stress_multiplier
        return {
            "impact_drag": float(max(0.0, impact_drag)),
            "crowding_drag": float(max(0.0, crowding_drag)),
            "turnover_penalty": float(max(0.0, turnover_penalty)),
        }

    def evaluate_single_aum(
        self,
        aum: float,
        *,
        baseline_cagr: float = 0.18,
        baseline_sharpe: float = 1.6,
        baseline_max_drawdown: float = 0.12,
        stress_multiplier: float = 1.0,
    ) -> CapacityMetrics:
        """Compute capacity metrics for one AUM point."""

        penalties = self._degradation_curve(aum, stress_multiplier=stress_multiplier)
        cagr = baseline_cagr - penalties["impact_drag"] - penalties["crowding_drag"]
        cagr = float(max(0.0, cagr))

        # Keep Sharpe non-negative and decreasing with stress/scale.
        sharpe = baseline_sharpe - (
            penalties["impact_drag"] * 18.0 + penalties["turnover_penalty"] * 8.0
        )
        sharpe = float(max(0.0, sharpe))

        # Drawdown typically worsens as liquidity gets tighter.
        max_drawdown = baseline_max_drawdown + penalties["impact_drag"] * 2.5
        max_drawdown = float(min(0.95, max(0.0, max_drawdown)))

        implementation_shortfall = float(max(0.0, baseline_cagr - cagr))
        return CapacityMetrics(
            aum=float(aum),
            cagr=cagr,
            sharpe=sharpe,
            max_drawdown=max_drawdown,
            implementation_shortfall=implementation_shortfall,
            turnover_penalty=float(penalties["turnover_penalty"]),
            stress_multiplier=float(stress_multiplier),
        )

    def run_capacity_sweep(
        self,
        *,
        aum_levels: Optional[Iterable[float]] = None,
        baseline_cagr: float = 0.18,
        baseline_sharpe: float = 1.6,
        baseline_max_drawdown: float = 0.12,
        stress_multiplier: float = 1.0,
    ) -> CapacityReport:
        """Run systematic capacity sweep and produce recommendation report."""

        levels = sorted(float(x) for x in (aum_levels or self.aum_levels))
        metrics = [
            self.evaluate_single_aum(
                aum,
                baseline_cagr=baseline_cagr,
                baseline_sharpe=baseline_sharpe,
                baseline_max_drawdown=baseline_max_drawdown,
                stress_multiplier=stress_multiplier,
            )
            for aum in levels
        ]

        cagr_values = [m.cagr for m in metrics]
        peak_cagr = max(cagr_values) if cagr_values else 0.0
        # Knee definition: first point with >20% CAGR drop OR >30% Sharpe drop from peak.
        knee = levels[-1]
        peak_sharpe = max((m.sharpe for m in metrics), default=0.0)
        if peak_cagr > 0:
            cagr_threshold = peak_cagr * 0.80
            sharpe_threshold = peak_sharpe * 0.70 if peak_sharpe > 0 else 0.0
            prev = None
            for m in metrics:
                crossed = (m.cagr < cagr_threshold) or (peak_sharpe > 0 and m.sharpe < sharpe_threshold)
                if crossed:
                    if prev is None:
                        knee = m.aum
                    else:
                        fracs = []
                        if m.cagr < cagr_threshold and m.cagr != prev.cagr:
                            fracs.append((cagr_threshold - prev.cagr) / (m.cagr - prev.cagr))
                        if peak_sharpe > 0 and m.sharpe < sharpe_threshold and m.sharpe != prev.sharpe:
                            fracs.append((sharpe_threshold - prev.sharpe) / (m.sharpe - prev.sharpe))
                        if fracs:
                            frac = float(np.clip(min(fracs), 0.0, 1.0))
                            knee = float(prev.aum + frac * (m.aum - prev.aum))
                        else:
                            knee = m.aum
                    break
                prev = m

        # Recommended AUM is capped at knee, first non-positive Sharpe point,
        # and first drawdown breach >35%.
        max_recommended = knee
        for m in metrics:
            if m.sharpe <= 0:
                max_recommended = min(max_recommended, m.aum)
                break
            if m.max_drawdown > 0.35:
                max_recommended = min(max_recommended, m.aum)
                break

        stress_adjusted = float(max_recommended / max(1.0, stress_multiplier))

        return CapacityReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            baseline_cagr=float(baseline_cagr),
            baseline_sharpe=float(baseline_sharpe),
            metrics=metrics,
            capacity_knee_aum=float(knee),
            max_recommended_aum=float(max_recommended),
            stress_adjusted_recommended_aum=float(stress_adjusted),
        )

    @staticmethod
    def report_to_frame(report: CapacityReport) -> pd.DataFrame:
        """Convert report metrics to a tabular dataframe."""
        return pd.DataFrame([asdict(m) for m in report.metrics]).sort_values("aum")

    def export_capacity_curves(
        self,
        report: CapacityReport,
        output_dir: Path | str = "reports/capacity",
        file_stem: str = "capacity_curves",
    ) -> Dict[str, str]:
        """Export machine-readable capacity curves and report summary."""

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        curve_path = out / f"{file_stem}.csv"
        json_path = out / f"{file_stem}.json"

        frame = self.report_to_frame(report)
        frame.to_csv(curve_path, index=False)
        json_path.write_text(json.dumps(report.to_dict(), indent=2))

        return {"curve_csv": str(curve_path), "report_json": str(json_path)}
