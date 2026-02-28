"""
Canonical AlphaOS interfaces for Northstar V4 dual-track migration.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RegimeProbabilitySnapshot:
    timestamp: str
    probabilities: Dict[str, float]
    confidence: float
    source: str = "frozen_hmm"
    model_path: str = ""
    model_version: str = ""
    stale: bool = False
    reason_codes: List[str] = field(default_factory=list)


@dataclass
class StrategyPosterior:
    strategy_name: str
    posterior_mean: float
    posterior_variance: float
    volatility: float
    adjusted_sharpe: float
    credibility: float
    regime_means: Dict[str, float] = field(default_factory=dict)
    regime_variances: Dict[str, float] = field(default_factory=dict)
    crowding_penalty: float = 1.0
    convexity_penalty: float = 1.0
    information_ratio: float = 0.0


@dataclass
class RiskBudgetSnapshot:
    gross_cap: float
    net_cap: float
    gross_used: float
    net_used: float
    convexity_score: float
    gap_risk_score: float
    crowding_score: float
    liquidity_adjusted_vega: float
    veto_active: bool = False
    veto_reasons: List[str] = field(default_factory=list)
    hard_limits: Dict[str, float] = field(default_factory=dict)
    soft_limits: Dict[str, float] = field(default_factory=dict)


@dataclass
class MetaFeedback:
    regret_ewma: float
    confidence_ewma: float
    credibility_relative_change: float
    adjustment_multiplier: float
    hysteresis_active: bool
    max_delta_applied: bool
    exposure_floor_applied: bool
    reason_codes: List[str] = field(default_factory=list)


@dataclass
class AllocationIntent:
    timestamp: str
    mode: str
    strategy_weights: Dict[str, float]
    gross_target: float
    net_target: float
    used_fallback: bool = False
    fallback_level: Optional[str] = None
    reason_codes: List[str] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    regime_snapshot: Optional[RegimeProbabilitySnapshot] = None
    strategy_posteriors: List[StrategyPosterior] = field(default_factory=list)
    risk_budget: Optional[RiskBudgetSnapshot] = None
    meta_feedback: Optional[MetaFeedback] = None
    legacy_allocation: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AlphaOSContext:
    timestamp: str
    cycle_id: str
    canonical_state: Dict[str, Any]
    canonical_sources: Dict[str, Dict[str, Any]]
    current_positions: List[Dict[str, Any]]
    current_weights: Dict[str, float]
    current_gross_exposure: float
    current_net_exposure: float
    current_drawdown: float
    max_gross_cap: float
    max_net_cap: float
    risk_veto_active: bool
    risk_veto_reasons: List[str]
    market_snapshot: Dict[str, Any] = field(default_factory=dict)
    portfolio_overlay: Dict[str, Any] = field(default_factory=dict)
    additional_inputs: Dict[str, Any] = field(default_factory=dict)
