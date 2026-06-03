"""
CapitalStructure — The top-level capital allocation decision for one trading day.

This is what the Portfolio Governor produces. Every other allocation decision
in the system is subordinate to this structure.

The capital structure specifies:
- What fraction of total capital is deployed to equities
- What fraction is deployed to options (notional exposure, not premium only)
- What fraction is held as cash (uninvested)
- The reasoning behind the decision (for audit and narrative engine)

All fractions must sum to 1.0. The Governor is the only entity that
sets these fractions. Neither the ConvexAllocator nor the options
capital_policy.py may override them.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum


class CapitalStructureRegime(str, Enum):
    """
    The Governor's own regime classification for capital structure purposes.
    This is DERIVED from the multi-dimensional regime state — it is not the
    same as the market_regime, macro_regime, or any individual regime signal.
    It is the Governor's synthesis of all regime signals into a single
    capital deployment posture.
    """
    FULL_DEPLOYMENT = "FULL_DEPLOYMENT"      # All signals favorable, max equity
    STANDARD = "STANDARD"                     # Normal conditions, standard split
    CAUTIOUS = "CAUTIOUS"                     # Mixed signals, moderate equity reduction
    DEFENSIVE = "DEFENSIVE"                   # Adverse regime, significant equity reduction
    CAPITAL_PRESERVATION = "CAPITAL_PRESERVATION"  # Crisis or extreme regime, minimal equity


class RegimeCapitalTable:
    """Authoritative base capital structures and hard limits for the Governor."""

    REGIME_TABLE = {
        CapitalStructureRegime.FULL_DEPLOYMENT: {
            'equity_fraction': 0.90,
            'options_fraction': 0.08,
            'cash_fraction': 0.02,
        },
        CapitalStructureRegime.STANDARD: {
            'equity_fraction': 0.75,
            'options_fraction': 0.15,
            'cash_fraction': 0.10,
        },
        CapitalStructureRegime.CAUTIOUS: {
            'equity_fraction': 0.60,
            'options_fraction': 0.20,
            'cash_fraction': 0.20,
        },
        CapitalStructureRegime.DEFENSIVE: {
            'equity_fraction': 0.40,
            'options_fraction': 0.20,
            'cash_fraction': 0.40,
        },
        CapitalStructureRegime.CAPITAL_PRESERVATION: {
            'equity_fraction': 0.15,
            'options_fraction': 0.10,
            'cash_fraction': 0.75,
        },
    }

    HARD_LIMITS = {
        'min_equity_fraction': 0.10,
        'max_equity_fraction': 0.95,
        'min_cash_fraction': 0.02,
        'max_options_fraction': 0.25,
        'min_options_fraction': 0.00,
        'emergency_cash_minimum': 0.20,
    }

    @classmethod
    def validate_table(cls) -> None:
        for regime, structure in cls.REGIME_TABLE.items():
            total = (
                structure['equity_fraction']
                + structure['options_fraction']
                + structure['cash_fraction']
            )
            if abs(total - 1.0) > 1e-6:
                raise ValueError(f"{regime.value} fractions sum to {total}, not 1.0")
            if any(value < 0 for value in structure.values()):
                raise ValueError(f"{regime.value} contains a negative fraction")

    @classmethod
    def get_regime_structure(cls, regime: CapitalStructureRegime) -> dict:
        return dict(cls.REGIME_TABLE[regime])


@dataclass
class CapitalStructure:
    """The Governor's capital allocation decision for one trading day."""

    # The three fractions (must sum to 1.0)
    equity_fraction: float           # Fraction of total capital to equity book
    options_fraction: float          # Fraction of total capital to options book
    cash_fraction: float             # Fraction held as cash / undeployed

    # Derived capital amounts (computed from fractions * total_capital_inr)
    total_capital_inr: float         # Total capital under management
    equity_budget_inr: float         # equity_fraction * total_capital_inr
    options_budget_inr: float        # options_fraction * total_capital_inr
    cash_reserve_inr: float          # cash_fraction * total_capital_inr

    # Classification
    capital_structure_regime: CapitalStructureRegime
    confidence: float                # 0.0 to 1.0 — how confident is the Governor in this decision

    # Inputs that drove the decision (for audit trail)
    market_regime: str               # From UnifiedState.market_state.regime
    volatility_regime: str           # From UnifiedState.market_state.volatility_regime
    macro_regime: str                # From MacroState
    sentiment_regime: str            # From SentimentState (Gap 2)
    economic_activity_regime: str    # From AlternativeDataState (Gap 3)
    crisis_probability: float        # From crisis_engine.py
    current_drawdown_pct: float      # From PnLState (Gap 5)
    current_nav_inr: float           # From PnLState (Gap 5)

    # Validity
    primary_rationale: str           # Primary reason for this structure
    valid_for_date: datetime         # This structure is valid for this trading date only
    expires_at: datetime             # Expires at end of trading day (15:30 IST)
    computed_at: datetime            # When the Governor computed this

    # Reasoning audit trail
    modifiers_applied: List[str] = field(default_factory=list)
    overrides_active: List[str] = field(default_factory=list)

    def validate(self) -> None:
        """Raises ValueError if fractions don't sum to 1.0 or any fraction is negative."""
        total = self.equity_fraction + self.options_fraction + self.cash_fraction
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Capital fractions sum to {total}, not 1.0")
        for name, val in [('equity', self.equity_fraction),
                          ('options', self.options_fraction),
                          ('cash', self.cash_fraction)]:
            if val < 0:
                raise ValueError(f"{name}_fraction is negative: {val}")

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'equity_fraction': self.equity_fraction,
            'options_fraction': self.options_fraction,
            'cash_fraction': self.cash_fraction,
            'total_capital_inr': self.total_capital_inr,
            'equity_budget_inr': self.equity_budget_inr,
            'options_budget_inr': self.options_budget_inr,
            'cash_reserve_inr': self.cash_reserve_inr,
            'capital_structure_regime': self.capital_structure_regime.value,
            'confidence': self.confidence,
            'market_regime': self.market_regime,
            'volatility_regime': self.volatility_regime,
            'macro_regime': self.macro_regime,
            'sentiment_regime': self.sentiment_regime,
            'economic_activity_regime': self.economic_activity_regime,
            'crisis_probability': self.crisis_probability,
            'current_drawdown_pct': self.current_drawdown_pct,
            'current_nav_inr': self.current_nav_inr,
            'primary_rationale': self.primary_rationale,
            'modifiers_applied': self.modifiers_applied,
            'overrides_active': self.overrides_active,
            'valid_for_date': self.valid_for_date.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'computed_at': self.computed_at.isoformat(),
        }
