"""Phase 3 deployment qualification orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable

from .monte_carlo_stability_simulator import MonteCarloStabilityResult, MonteCarloStabilitySimulator
from .structural_qualification_engine import DeterministicQualificationResult, StructuralQualificationEngine


@dataclass(frozen=True)
class Phase3QualificationResult:
    alpha_id: str
    deterministic: DeterministicQualificationResult
    monte_carlo: MonteCarloStabilityResult
    phase3_status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alpha_id": str(self.alpha_id),
            "deterministic": self.deterministic.to_dict(),
            "monte_carlo": self.monte_carlo.to_dict(),
            "phase3_status": str(self.phase3_status),
        }


class Phase3DeploymentQualifier:
    """Approve only if deterministic deployable AND monte carlo stable."""

    def __init__(
        self,
        *,
        deterministic_engine: StructuralQualificationEngine | None = None,
        monte_carlo_engine: MonteCarloStabilitySimulator | None = None,
    ):
        self.deterministic_engine = deterministic_engine or StructuralQualificationEngine()
        self.monte_carlo_engine = monte_carlo_engine or MonteCarloStabilitySimulator()

    def qualify_alpha(
        self,
        *,
        alpha_id: str,
        returns: Iterable[float],
        portfolio_returns: Iterable[float] | None = None,
    ) -> Phase3QualificationResult:
        det = self.deterministic_engine.qualify(returns=returns, portfolio_returns=portfolio_returns)
        mc = self.monte_carlo_engine.qualify(returns=returns)
        phase3_status = "approved" if (det.status == "deployable" and mc.status == "stable") else "reject"
        return Phase3QualificationResult(
            alpha_id=str(alpha_id),
            deterministic=det,
            monte_carlo=mc,
            phase3_status=str(phase3_status),
        )
