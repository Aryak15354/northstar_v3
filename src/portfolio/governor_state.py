"""
GovernorState — The formal home for Portfolio Governor status in UnifiedState.

Provides the rest of the system visibility into the current capital structure
without needing to query the Governor directly.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class GovernorState:
    """State representation of Portfolio Governor decisions."""

    # Current capital structure
    capital_structure_regime: str = "UNKNOWN"
    equity_fraction: float = 0.75          # Default from config
    options_fraction: float = 0.15
    cash_fraction: float = 0.10

    # INR amounts
    equity_budget_inr: float = 0.0
    options_budget_inr: float = 0.0
    cash_reserve_inr: float = 0.0
    total_capital_inr: float = 0.0

    # Decision quality
    governance_confidence: float = 0.5
    caution_score: float = 0.3
    crisis_probability_at_decision: float = 0.0

    # Key inputs that drove decision
    primary_rationale: str = ""
    modifiers_applied: List[str] = field(default_factory=list)
    overrides_active: List[str] = field(default_factory=list)

    # Temporal
    last_morning_decision: Optional[datetime] = None
    last_intraday_check: Optional[datetime] = None
    intraday_escalations_today: int = 0
    
    # History
    regime_changes_this_week: int = 0
    days_in_current_regime: int = 0

    def update_from_structure(self, structure) -> None:
        """Update state from a CapitalStructure object."""
        self.capital_structure_regime = structure.capital_structure_regime.value
        self.equity_fraction = structure.equity_fraction
        self.options_fraction = structure.options_fraction
        self.cash_fraction = structure.cash_fraction
        self.equity_budget_inr = structure.equity_budget_inr
        self.options_budget_inr = structure.options_budget_inr
        self.cash_reserve_inr = structure.cash_reserve_inr
        self.total_capital_inr = structure.total_capital_inr
        self.governance_confidence = structure.confidence
        self.crisis_probability_at_decision = structure.crisis_probability
        self.primary_rationale = structure.primary_rationale
        self.modifiers_applied = structure.modifiers_applied
        self.overrides_active = structure.overrides_active
        self.last_morning_decision = structure.computed_at

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'capital_structure_regime': self.capital_structure_regime,
            'equity_fraction': self.equity_fraction,
            'options_fraction': self.options_fraction,
            'cash_fraction': self.cash_fraction,
            'equity_budget_inr': self.equity_budget_inr,
            'options_budget_inr': self.options_budget_inr,
            'cash_reserve_inr': self.cash_reserve_inr,
            'total_capital_inr': self.total_capital_inr,
            'governance_confidence': self.governance_confidence,
            'caution_score': self.caution_score,
            'crisis_probability_at_decision': self.crisis_probability_at_decision,
            'primary_rationale': self.primary_rationale,
            'modifiers_applied': self.modifiers_applied,
            'overrides_active': self.overrides_active,
            'last_morning_decision': self.last_morning_decision.isoformat() if self.last_morning_decision else None,
            'last_intraday_check': self.last_intraday_check.isoformat() if self.last_intraday_check else None,
            'intraday_escalations_today': self.intraday_escalations_today,
            'regime_changes_this_week': self.regime_changes_this_week,
            'days_in_current_regime': self.days_in_current_regime,
        }
