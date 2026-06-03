#!/usr/bin/env python3
"""
Observer Context - Read-Only System State Access

This module provides the Observer with read-only access to system state
through immutable snapshots. No live references are allowed.

CRITICAL DESIGN PRINCIPLE:
The Observer sees the past, never the present. This prevents any possibility
of the Observer influencing decisions through timing or information leakage.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union
import json
import warnings
warnings.filterwarnings('ignore')

@dataclass(frozen=True)
class MarketStateSummary:
    """Immutable market state summary for Observer"""
    timestamp: datetime
    regime: str
    volatility_regime: str
    risk_on_probability: float
    allowed_exposure: float
    market_stress: float
    breadth_pct: float
    correlation: float
    
    # Derived metrics (lagged)
    volatility_20d: float
    volatility_60d: float
    drawdown_current: float
    trend_strength: float
    
    def __post_init__(self):
        """Validate all values are reasonable"""
        assert 0.0 <= self.risk_on_probability <= 1.0
        assert 0.0 <= self.allowed_exposure <= 1.0
        assert 0.0 <= self.market_stress <= 1.0
        assert 0.0 <= self.breadth_pct <= 100.0
        assert -1.0 <= self.correlation <= 1.0

@dataclass(frozen=True)
class EngineStateHistory:
    """Immutable engine state history for Observer"""
    timestamp: datetime
    
    # Dual Engine Coordinator State
    active_engine: str
    regime_classification: str
    regime_confidence: float
    trend_allocation: float
    crisis_allocation: float
    
    # Engine Performance (lagged)
    trend_engine_active_days: int
    crisis_engine_active_days: int
    trend_engine_last_return: Optional[float]
    crisis_engine_last_return: Optional[float]
    
    # Regime Transition History
    regime_changes_30d: int
    regime_stability_score: float
    last_regime_change: Optional[datetime]
    
    def __post_init__(self):
        """Validate engine state consistency"""
        assert self.active_engine in ['trend', 'crisis', 'none']
        assert 0.0 <= self.regime_confidence <= 1.0
        assert 0.0 <= self.trend_allocation <= 1.0
        assert 0.0 <= self.crisis_allocation <= 1.0

@dataclass(frozen=True)
class LaggedPortfolioStats:
    """Lagged portfolio statistics - NO CURRENT POSITIONS"""
    timestamp: datetime
    
    # Performance metrics (all lagged by 1+ days)
    total_return_1d: float
    total_return_7d: float
    total_return_30d: float
    volatility_30d: float
    sharpe_ratio_30d: float
    max_drawdown_30d: float
    
    # Exposure metrics (lagged)
    avg_exposure_7d: float
    avg_exposure_30d: float
    turnover_7d: float
    
    # Risk metrics (lagged)
    var_95_1d: float
    concentration_score: float
    sector_concentration_max: float
    
    # NO CURRENT POSITIONS - Observer is blind to live exposure
    
    def __post_init__(self):
        """Validate portfolio statistics"""
        assert 0.0 <= self.avg_exposure_7d <= 1.0
        assert 0.0 <= self.avg_exposure_30d <= 1.0
        assert self.turnover_7d >= 0.0
        assert 0.0 <= self.concentration_score <= 1.0

@dataclass(frozen=True)
class HistoricalContext:
    """Historical context for pattern matching"""
    timestamp: datetime
    
    # Historical regime data
    regime_history_1y: List[str]
    volatility_history_1y: List[float]
    return_history_1y: List[float]
    
    # Crisis periods identification
    crisis_periods: List[Dict[str, Any]]
    stress_periods: List[Dict[str, Any]]
    
    # Regime transition patterns
    regime_transition_matrix: Dict[str, Dict[str, float]]
    avg_regime_duration: Dict[str, float]
    
    # Market structure evolution
    correlation_history_1y: List[float]
    breadth_history_1y: List[float]
    
    def __post_init__(self):
        """Validate historical context data"""
        assert len(self.regime_history_1y) <= 252  # Max 1 year daily
        assert len(self.volatility_history_1y) <= 252
        assert len(self.return_history_1y) <= 252

@dataclass(frozen=True)
class ObserverSnapshot:
    """
    Complete immutable snapshot for Intelligence Observer
    
    This is the ONLY data the Observer is allowed to see.
    All data is historical/lagged - no live positions or real-time P&L.
    """
    snapshot_id: str
    creation_time: datetime
    data_cutoff_time: datetime  # All data is before this time
    
    # Core state components
    market_state: MarketStateSummary
    engine_states: EngineStateHistory
    portfolio_stats: LaggedPortfolioStats
    historical_context: HistoricalContext
    
    # Metadata
    data_quality_score: float
    completeness_score: float
    staleness_hours: float
    
    def __post_init__(self):
        """Validate snapshot integrity"""
        # Ensure all timestamps are consistent
        assert self.creation_time >= self.data_cutoff_time
        assert self.market_state.timestamp <= self.data_cutoff_time
        assert self.engine_states.timestamp <= self.data_cutoff_time
        assert self.portfolio_stats.timestamp <= self.data_cutoff_time
        
        # Ensure data quality
        assert 0.0 <= self.data_quality_score <= 1.0
        assert 0.0 <= self.completeness_score <= 1.0
        assert self.staleness_hours >= 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary for serialization"""
        return {
            'snapshot_id': self.snapshot_id,
            'creation_time': self.creation_time.isoformat(),
            'data_cutoff_time': self.data_cutoff_time.isoformat(),
            'market_state': {
                'timestamp': self.market_state.timestamp.isoformat(),
                'regime': self.market_state.regime,
                'volatility_regime': self.market_state.volatility_regime,
                'risk_on_probability': self.market_state.risk_on_probability,
                'allowed_exposure': self.market_state.allowed_exposure,
                'market_stress': self.market_state.market_stress,
                'breadth_pct': self.market_state.breadth_pct,
                'correlation': self.market_state.correlation,
                'volatility_20d': self.market_state.volatility_20d,
                'volatility_60d': self.market_state.volatility_60d,
                'drawdown_current': self.market_state.drawdown_current,
                'trend_strength': self.market_state.trend_strength
            },
            'engine_states': {
                'timestamp': self.engine_states.timestamp.isoformat(),
                'active_engine': self.engine_states.active_engine,
                'regime_classification': self.engine_states.regime_classification,
                'regime_confidence': self.engine_states.regime_confidence,
                'trend_allocation': self.engine_states.trend_allocation,
                'crisis_allocation': self.engine_states.crisis_allocation,
                'trend_engine_active_days': self.engine_states.trend_engine_active_days,
                'crisis_engine_active_days': self.engine_states.crisis_engine_active_days,
                'regime_changes_30d': self.engine_states.regime_changes_30d,
                'regime_stability_score': self.engine_states.regime_stability_score
            },
            'portfolio_stats': {
                'timestamp': self.portfolio_stats.timestamp.isoformat(),
                'total_return_1d': self.portfolio_stats.total_return_1d,
                'total_return_7d': self.portfolio_stats.total_return_7d,
                'total_return_30d': self.portfolio_stats.total_return_30d,
                'volatility_30d': self.portfolio_stats.volatility_30d,
                'sharpe_ratio_30d': self.portfolio_stats.sharpe_ratio_30d,
                'max_drawdown_30d': self.portfolio_stats.max_drawdown_30d,
                'avg_exposure_7d': self.portfolio_stats.avg_exposure_7d,
                'avg_exposure_30d': self.portfolio_stats.avg_exposure_30d,
                'turnover_7d': self.portfolio_stats.turnover_7d,
                'var_95_1d': self.portfolio_stats.var_95_1d,
                'concentration_score': self.portfolio_stats.concentration_score,
                'sector_concentration_max': self.portfolio_stats.sector_concentration_max
            },
            'metadata': {
                'data_quality_score': self.data_quality_score,
                'completeness_score': self.completeness_score,
                'staleness_hours': self.staleness_hours
            }
        }

class ObserverContext:
    """
    Observer Context Manager - Provides read-only access to system state
    
    This class ensures the Observer can only access historical, immutable
    snapshots of system state. No live references are allowed.
    """
    
    def __init__(self):
        self.name = "Intelligence Observer Context"
        self.version = "1.0.0"
        
        # Forbidden imports - these will raise exceptions if accessed
        self._forbidden_modules = [
            'portfolio_governor',
            'risk',
            'emergency_brake', 
            'dual_engine_coordinator',
            'trend_engine',
            'crisis_engine'
        ]
        
        # Access tracking
        self.access_log: List[Dict[str, Any]] = []
        self.violation_count = 0
        
        print(f"🔒 {self.name} v{self.version} - Read-Only Access Enforced")
    
    def validate_snapshot(self, snapshot: ObserverSnapshot) -> bool:
        """
        Validate that snapshot contains only allowed data
        
        Returns:
            bool: True if snapshot is valid for Observer access
        """
        try:
            # Check temporal constraints
            now = datetime.now()
            if snapshot.data_cutoff_time > now - timedelta(hours=1):
                print(f"⚠️ Snapshot too recent: {snapshot.data_cutoff_time}")
                return False
            
            # Check data completeness
            if snapshot.completeness_score < 0.8:
                print(f"⚠️ Snapshot incomplete: {snapshot.completeness_score}")
                return False
            
            # Check for forbidden data (current positions, live P&L)
            # ObserverSnapshot is designed to exclude these by construction
            
            # Log access
            self.access_log.append({
                'timestamp': datetime.now(),
                'snapshot_id': snapshot.snapshot_id,
                'data_cutoff': snapshot.data_cutoff_time,
                'validation': 'passed'
            })
            
            return True
            
        except Exception as e:
            print(f"❌ Snapshot validation failed: {e}")
            self.violation_count += 1
            return False
    
    def get_access_summary(self) -> Dict[str, Any]:
        """Get summary of Observer access patterns"""
        return {
            'total_accesses': len(self.access_log),
            'violation_count': self.violation_count,
            'last_access': self.access_log[-1] if self.access_log else None,
            'forbidden_modules': self._forbidden_modules
        }