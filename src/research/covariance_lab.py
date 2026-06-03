"""Covariance structure diagnostics for research cycles."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

import numpy as np


class CovarianceLab:
    """Computes covariance-health metrics and correlation-break diagnostics."""

    def run_analysis(self, market_data: Dict[str, Any], system_state: Dict[str, Any]) -> Dict[str, Any]:
        returns = market_data.get("strategy_returns")
        if isinstance(returns, dict):
            values = [np.asarray(v, dtype=float) for v in returns.values() if isinstance(v, (list, tuple)) and len(v) > 2]
            if values:
                mat = np.vstack(values)
            else:
                mat = np.empty((0, 0), dtype=float)
        else:
            mat = np.empty((0, 0), dtype=float)

        if mat.size == 0:
            health = {
                "status": "insufficient_data",
                "largest_eigenvalue": 0.0,
                "condition_number": 0.0,
                "eigenvalue_shift": 0.0,
            }
        else:
            cov = np.cov(mat)
            eig = np.linalg.eigvals(cov)
            eig_real = np.real(eig)
            largest = float(np.max(eig_real)) if eig_real.size else 0.0
            smallest = float(np.min(np.clip(eig_real, 1e-12, None))) if eig_real.size else 1e-12
            cond = float(largest / smallest) if smallest > 0 else float("inf")
            prev = float(system_state.get("last_largest_eigenvalue", largest) or largest)
            shift = float(largest - prev)
            health = {
                "status": "ok",
                "largest_eigenvalue": largest,
                "condition_number": cond,
                "eigenvalue_shift": shift,
                "correlation_regime_break": abs(shift) > max(0.15 * abs(prev), 1e-6),
            }

        return {
            "module": "covariance_lab",
            "timestamp": datetime.now().isoformat(),
            "outputs": [
                {
                    "type": "covariance_health",
                    "actionable": False,
                    "generated_at": datetime.now().isoformat(),
                    "data": health,
                }
            ],
        }
