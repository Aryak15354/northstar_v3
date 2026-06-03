"""Adaptive structural Monte Carlo stress module."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd

from .structural_monte_carlo import StructuralMonteCarlo


class MonteCarloLab:
    """Runs stress tests only when trigger conditions are met."""

    @staticmethod
    def _latest_snapshot() -> pd.DataFrame:
        root = Path("data/results/research/snapshots")
        snaps = sorted(root.rglob("research_snapshot_*.parquet"))
        if not snaps:
            return pd.DataFrame()
        try:
            return pd.read_parquet(snaps[-1])
        except Exception:
            return pd.DataFrame()

    @staticmethod
    def _validate_snapshot(panel: pd.DataFrame) -> Tuple[bool, str]:
        if panel is None or panel.empty:
            return False, "snapshot_missing_or_empty"
        required_cols = {"date", "ticker", "forward_return_5d"}
        if not required_cols.issubset(set(panel.columns)):
            return False, "snapshot_missing_required_columns"
        if len(panel) < 500:
            return False, "snapshot_too_small"
        if float(pd.to_numeric(panel["forward_return_5d"], errors="coerce").abs().mean()) <= 1e-10:
            return False, "snapshot_target_degenerate"
        return True, "ok"

    def run_analysis(self, market_data: Dict[str, Any], system_state: Dict[str, Any]) -> Dict[str, Any]:
        drawdown = float(system_state.get("current_drawdown", 0.0) or 0.0)
        triggers = {
            "regime_shift_detected": bool(system_state.get("regime_shift_detected", False)),
            "survival_recent": bool(system_state.get("survival_core_recent", False)),
            "drawdown_trigger": drawdown >= 0.10,
        }

        should_run = any(triggers.values())
        if not should_run:
            return {
                "module": "monte_carlo_lab",
                "timestamp": datetime.now().isoformat(),
                "outputs": [
                    {
                        "type": "monte_carlo_report",
                        "actionable": False,
                        "generated_at": datetime.now().isoformat(),
                        "data": {"status": "skipped", "triggers": triggers},
                    }
                ],
            }

        sims = int(system_state.get("monte_carlo_sims", 8000) or 8000)
        horizon = int(system_state.get("monte_carlo_horizon", 20) or 20)
        stress_mult = float(system_state.get("monte_carlo_stress_multiplier", 1.0) or 1.0)

        panel = self._latest_snapshot()
        valid, reason = self._validate_snapshot(panel)
        if not valid:
            report = {
                "status": "failed",
                "triggers": triggers,
                "reason": reason,
                "simulations": 0,
            }
        else:
            try:
                mc = StructuralMonteCarlo(random_state=int(system_state.get("random_state", 42) or 42))
                mc.fit(panel)
                sim = mc.simulate_paths(
                    panel=panel,
                    n_paths=max(1000, sims),
                    horizon=max(5, horizon),
                    stress_multiplier=max(0.5, stress_mult),
                )
                metrics = mc.evaluate(sim.get("paths", np.empty((0, 0))))
                report = {
                    "status": "completed_structural",
                    "triggers": triggers,
                    "simulations": int(max(1000, sims)),
                    "horizon": int(max(5, horizon)),
                    **metrics,
                }
            except Exception as exc:
                report = {
                    "status": "failed",
                    "triggers": triggers,
                    "reason": f"structural_monte_carlo_failed:{exc}",
                    "simulations": 0,
                }

        return {
            "module": "monte_carlo_lab",
            "timestamp": datetime.now().isoformat(),
            "outputs": [
                {
                    "type": "monte_carlo_report",
                    "actionable": bool(report.get("status") == "completed_structural"),
                    "generated_at": datetime.now().isoformat(),
                    "data": report,
                }
            ],
        }
