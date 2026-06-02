"""
AlphaOSState — The formal representation of Alpha OS in UnifiedState.

This state object gives the rest of the system visibility into the current state
of the strategy portfolio without needing to query the registry directly.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict


@dataclass
class AlphaOSState:
    """Alpha OS state for UnifiedState integration."""
    
    # Active strategy portfolio
    active_strategy_count: int = 0
    probation_strategy_count: int = 0
    candidate_strategy_count: int = 0
    
    # Current weights
    strategy_weights: Dict[str, float] = field(default_factory=dict)  # {strategy_id: weight}
    
    # Recent lifecycle events
    last_promotion_date: Optional[datetime] = None
    last_retirement_date: Optional[datetime] = None
    last_probation_date: Optional[datetime] = None
    
    # Portfolio health
    avg_active_icir: float = 0.0
    weakest_strategy_id: Optional[str] = None
    weakest_strategy_live_ic: Optional[float] = None
    
    # Redundancy
    redundancy_issues: int = 0  # Count of redundancy flags among active strategies
    
    # Tribunal
    tribunal_entropy: float = 0.0  # Shannon entropy of capital weight distribution
                                    # Low = concentrated, High = diversified
    
    # Last update
    last_updated: Optional[datetime] = None
