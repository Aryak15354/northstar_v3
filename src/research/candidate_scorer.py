"""Candidate scoring contract for promotion gating."""

from __future__ import annotations

from typing import Dict


class CandidateScorer:
    """Unified score for comparing candidate models under governance."""

    def __init__(self):
        self.weights = {
            "sharpe": 0.25,
            "stability": 0.20,
            "ic": 0.15,
            "survival": 0.20,
            "drawdown_penalty": 0.20,
        }

    def score(
        self,
        walk_forward_metrics: Dict[str, float],
        mc_metrics: Dict[str, float],
        regime_metrics: Dict[str, float],
    ) -> Dict[str, float]:
        sharpe = float(walk_forward_metrics.get("avg_sharpe", 0.0))
        stability = float(walk_forward_metrics.get("stability_score", 0.0))
        ic = float(walk_forward_metrics.get("ic_mean", 0.0))
        survival = float(mc_metrics.get("survival_probability", 0.0))
        max_dd = float(walk_forward_metrics.get("avg_max_drawdown", 1.0))

        # Regime dispersion penalty: lower is better.
        regime_dispersion = float(regime_metrics.get("dispersion", 0.0))

        drawdown_penalty = max(0.0, 1.0 - max_dd)

        raw = (
            self.weights["sharpe"] * sharpe
            + self.weights["stability"] * stability
            + self.weights["ic"] * ic
            + self.weights["survival"] * survival
            + self.weights["drawdown_penalty"] * drawdown_penalty
            - 0.10 * regime_dispersion
        )

        normalized = max(0.0, min(1.0, 0.5 + 0.5 * raw))
        return {
            "candidate_score": float(normalized),
            "raw_score": float(raw),
            "sharpe": sharpe,
            "stability": stability,
            "ic": ic,
            "survival_probability": survival,
            "avg_max_drawdown": max_dd,
            "regime_dispersion": regime_dispersion,
        }
