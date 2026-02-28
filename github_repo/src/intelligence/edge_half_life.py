"""
Edge Half-Life Model - Capital Decay Controller

This module implements edge persistence tracking and capital decay based on
signal half-life, enabling early exit before Sharpe degradation occurs.

Key Features:
- Exponential edge decay modeling
- Robust half-life estimation
- Capital allocation decay curves
- Regime-aware edge persistence
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging
from scipy import stats
from sklearn.linear_model import HuberRegressor


class EdgeStatus(Enum):
    """Edge health status levels"""
    FRESH = "fresh"          # EdgeHealth > 0.8
    HEALTHY = "healthy"      # EdgeHealth > 0.5
    DECAYING = "decaying"    # EdgeHealth > 0.3
    STALE = "stale"          # EdgeHealth > 0.1
    DEAD = "dead"            # EdgeHealth <= 0.1


@dataclass
class EdgeMetrics:
    """Edge performance metrics"""
    strategy_id: str
    timestamp: datetime
    edge_value: float           # Risk-adjusted excess return
    decay_rate: float          # Lambda parameter
    half_life_days: float      # T_1/2 in days
    edge_health: float         # 0-1 health score
    status: EdgeStatus
    confidence: float          # Estimation confidence
    observations: int          # Sample size used
    regime_context: str        # Current regime


@dataclass
class EdgeDecayModel:
    """Edge decay model parameters"""
    strategy_id: str
    peak_edge: float
    decay_rate: float
    model_r_squared: float
    estimation_date: datetime
    regime: str
    observations_used: int


class EdgeHalfLifeTracker:
    """
    Tracks edge persistence and calculates capital decay multipliers
    
    This system:
    1. Monitors strategy performance in real-time
    2. Estimates edge decay rates using robust regression
    3. Calculates remaining edge half-life
    4. Provides capital allocation multipliers
    5. Triggers early exit signals before Sharpe degradation
    """
    
    def __init__(self, 
                 lookback_window: int = 90,
                 min_observations: int = 20,
                 decay_power: float = 2.0,
                 confidence_threshold: float = 0.7):
        
        self.lookback_window = lookback_window
        self.min_observations = min_observations
        self.decay_power = decay_power  # Alpha in capital decay formula
        self.confidence_threshold = confidence_threshold
        
        # Storage
        self.performance_history: Dict[str, pd.DataFrame] = {}
        self.edge_models: Dict[str, EdgeDecayModel] = {}
        self.edge_metrics: Dict[str, EdgeMetrics] = {}
        
        self.logger = logging.getLogger(__name__)
    
    def update_performance(self, 
                          strategy_id: str,
                          timestamp: datetime,
                          returns: float,
                          benchmark_returns: float,
                          volatility: float,
                          confidence: float,
                          regime: str) -> None:
        """Update strategy performance data"""
        
        # Calculate risk-adjusted edge
        excess_return = returns - benchmark_returns
        edge_value = excess_return / max(volatility, 0.001)  # Avoid division by zero
        
        # Create performance record
        record = {
            'timestamp': timestamp,
            'returns': returns,
            'benchmark_returns': benchmark_returns,
            'excess_return': excess_return,
            'volatility': volatility,
            'edge_value': edge_value,
            'confidence': confidence,
            'regime': regime
        }
        
        # Initialize or update history
        if strategy_id not in self.performance_history:
            self.performance_history[strategy_id] = pd.DataFrame()
        
        # Add new record
        new_row = pd.DataFrame([record])
        self.performance_history[strategy_id] = pd.concat([
            self.performance_history[strategy_id], 
            new_row
        ], ignore_index=True)
        
        # Keep only recent history
        cutoff_date = timestamp - timedelta(days=self.lookback_window)
        self.performance_history[strategy_id] = self.performance_history[strategy_id][
            self.performance_history[strategy_id]['timestamp'] >= cutoff_date
        ]
        
        # Update edge model if we have enough data
        if len(self.performance_history[strategy_id]) >= self.min_observations:
            self._update_edge_model(strategy_id, timestamp, regime)
    
    def _update_edge_model(self, strategy_id: str, timestamp: datetime, regime: str) -> None:
        """Update edge decay model for strategy"""
        try:
            df = self.performance_history[strategy_id].copy()
            
            # Find local peak in edge values
            peak_idx = df['edge_value'].idxmax()
            peak_edge = df.loc[peak_idx, 'edge_value']
            peak_date = df.loc[peak_idx, 'timestamp']
            
            # Only use data after peak for decay estimation
            post_peak_data = df[df['timestamp'] >= peak_date].copy()
            
            if len(post_peak_data) < self.min_observations // 2:
                # Not enough post-peak data
                return
            
            # Calculate days since peak
            post_peak_data['days_since_peak'] = (
                post_peak_data['timestamp'] - peak_date
            ).dt.total_seconds() / 86400
            
            # Filter out zero/negative edge values for log regression
            valid_data = post_peak_data[post_peak_data['edge_value'] > 0].copy()
            
            if len(valid_data) < self.min_observations // 3:
                return
            
            # Robust log-linear regression: ln(edge) = a - lambda * t
            X = valid_data['days_since_peak'].values.reshape(-1, 1)
            y = np.log(valid_data['edge_value'].values)
            
            # Use Huber regression for robustness
            model = HuberRegressor(epsilon=1.35, max_iter=100)
            model.fit(X, y)
            
            # Extract decay rate (lambda)
            decay_rate = -model.coef_[0]  # Negative because we want positive decay rate
            decay_rate = max(decay_rate, 0.001)  # Ensure positive
            
            # Calculate R-squared
            y_pred = model.predict(X)
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
            r_squared = max(r_squared, 0.0)
            
            # Store model
            self.edge_models[strategy_id] = EdgeDecayModel(
                strategy_id=strategy_id,
                peak_edge=peak_edge,
                decay_rate=decay_rate,
                model_r_squared=r_squared,
                estimation_date=timestamp,
                regime=regime,
                observations_used=len(valid_data)
            )
            
            # Update current edge metrics
            self._calculate_edge_metrics(strategy_id, timestamp)
            
        except Exception as e:
            self.logger.error(f"Error updating edge model for {strategy_id}: {e}")
    
    def _calculate_edge_metrics(self, strategy_id: str, timestamp: datetime) -> None:
        """Calculate current edge health metrics"""
        if strategy_id not in self.edge_models:
            return
        
        model = self.edge_models[strategy_id]
        df = self.performance_history[strategy_id]
        
        # Get current edge value
        current_edge = df['edge_value'].iloc[-1] if not df.empty else 0.0
        
        # Calculate days since model estimation
        days_since_estimation = (timestamp - model.estimation_date).total_seconds() / 86400
        
        # Calculate half-life
        half_life_days = np.log(2) / model.decay_rate if model.decay_rate > 0 else float('inf')
        
        # Calculate edge health score
        if half_life_days == float('inf'):
            edge_health = 1.0
        else:
            # Remaining half-life as fraction of expected holding horizon (default 30 days)
            expected_horizon = 30.0
            edge_health = min(1.0, half_life_days / expected_horizon)
        
        # Determine status
        if edge_health > 0.8:
            status = EdgeStatus.FRESH
        elif edge_health > 0.5:
            status = EdgeStatus.HEALTHY
        elif edge_health > 0.3:
            status = EdgeStatus.DECAYING
        elif edge_health > 0.1:
            status = EdgeStatus.STALE
        else:
            status = EdgeStatus.DEAD
        
        # Estimation confidence based on R-squared and sample size
        confidence = model.model_r_squared * min(1.0, model.observations_used / 30.0)
        
        # Store metrics
        self.edge_metrics[strategy_id] = EdgeMetrics(
            strategy_id=strategy_id,
            timestamp=timestamp,
            edge_value=current_edge,
            decay_rate=model.decay_rate,
            half_life_days=half_life_days,
            edge_health=edge_health,
            status=status,
            confidence=confidence,
            observations=model.observations_used,
            regime_context=df['regime'].iloc[-1] if not df.empty else 'unknown'
        )
    
    def get_capital_multiplier(self, strategy_id: str) -> float:
        """
        Get capital allocation multiplier based on edge health
        
        Returns:
            float: Multiplier between 0 and 1 to apply to proposed allocation
        """
        if strategy_id not in self.edge_metrics:
            return 0.5  # Conservative default
        
        metrics = self.edge_metrics[strategy_id]
        
        # Apply power law decay: multiplier = edge_health^alpha
        multiplier = metrics.edge_health ** self.decay_power
        
        # Apply confidence adjustment
        confidence_adjusted = multiplier * metrics.confidence
        
        # Minimum threshold for very low confidence
        if metrics.confidence < self.confidence_threshold:
            confidence_adjusted *= 0.5
        
        return max(0.0, min(1.0, confidence_adjusted))
    
    def should_exit_strategy(self, strategy_id: str, threshold: float = 0.3) -> bool:
        """
        Determine if strategy should be exited based on edge health
        
        Args:
            strategy_id: Strategy identifier
            threshold: Edge health threshold for exit signal
            
        Returns:
            bool: True if strategy should be exited
        """
        if strategy_id not in self.edge_metrics:
            return False
        
        metrics = self.edge_metrics[strategy_id]
        return metrics.edge_health < threshold and metrics.confidence > self.confidence_threshold
    
    def get_edge_metrics(self, strategy_id: str) -> Optional[EdgeMetrics]:
        """Get current edge metrics for strategy"""
        return self.edge_metrics.get(strategy_id)
    
    def get_all_edge_metrics(self) -> Dict[str, EdgeMetrics]:
        """Get edge metrics for all strategies"""
        return self.edge_metrics.copy()
    
    def reset_strategy_model(self, strategy_id: str) -> None:
        """Reset edge model for strategy (e.g., after regime change)"""
        if strategy_id in self.edge_models:
            del self.edge_models[strategy_id]
        if strategy_id in self.edge_metrics:
            del self.edge_metrics[strategy_id]
        
        self.logger.info(f"Reset edge model for strategy {strategy_id}")
    
    def get_strategy_summary(self, strategy_id: str) -> Dict[str, Any]:
        """Get comprehensive summary for strategy"""
        if strategy_id not in self.edge_metrics:
            return {'status': 'no_data'}
        
        metrics = self.edge_metrics[strategy_id]
        model = self.edge_models.get(strategy_id)
        
        return {
            'strategy_id': strategy_id,
            'edge_health': metrics.edge_health,
            'status': metrics.status.value,
            'half_life_days': metrics.half_life_days,
            'capital_multiplier': self.get_capital_multiplier(strategy_id),
            'should_exit': self.should_exit_strategy(strategy_id),
            'confidence': metrics.confidence,
            'current_edge': metrics.edge_value,
            'decay_rate': metrics.decay_rate,
            'regime': metrics.regime_context,
            'model_r_squared': model.model_r_squared if model else None,
            'observations': metrics.observations,
            'last_update': metrics.timestamp
        }
    
    def get_portfolio_edge_summary(self) -> Dict[str, Any]:
        """Get portfolio-level edge summary"""
        if not self.edge_metrics:
            return {'status': 'no_strategies'}
        
        # Calculate portfolio-level metrics
        total_strategies = len(self.edge_metrics)
        healthy_strategies = sum(1 for m in self.edge_metrics.values() 
                               if m.status in [EdgeStatus.FRESH, EdgeStatus.HEALTHY])
        
        avg_edge_health = np.mean([m.edge_health for m in self.edge_metrics.values()])
        avg_confidence = np.mean([m.confidence for m in self.edge_metrics.values()])
        
        # Status distribution
        status_counts = {}
        for status in EdgeStatus:
            status_counts[status.value] = sum(1 for m in self.edge_metrics.values() 
                                            if m.status == status)
        
        return {
            'total_strategies': total_strategies,
            'healthy_strategies': healthy_strategies,
            'healthy_percentage': healthy_strategies / total_strategies,
            'avg_edge_health': avg_edge_health,
            'avg_confidence': avg_confidence,
            'status_distribution': status_counts,
            'portfolio_edge_score': avg_edge_health * avg_confidence,
            'timestamp': datetime.now()
        }


class EdgeStateManager:
    """
    State manager for edge half-life integration with UnifiedState
    """
    
    def __init__(self, unified_state, edge_tracker: EdgeHalfLifeTracker):
        self.unified_state = unified_state
        self.edge_tracker = edge_tracker
        self.logger = logging.getLogger(__name__)
    
    def update_edge_state(self) -> None:
        """Update edge state in unified state system"""
        try:
            # Get all current edge metrics
            all_metrics = self.edge_tracker.get_all_edge_metrics()
            portfolio_summary = self.edge_tracker.get_portfolio_edge_summary()
            
            # Update individual strategy edge states
            edge_state = {}
            for strategy_id, metrics in all_metrics.items():
                edge_state[strategy_id] = {
                    'edge_health': metrics.edge_health,
                    'status': metrics.status.value,
                    'half_life_days': metrics.half_life_days,
                    'capital_multiplier': self.edge_tracker.get_capital_multiplier(strategy_id),
                    'should_exit': self.edge_tracker.should_exit_strategy(strategy_id),
                    'confidence': metrics.confidence,
                    'last_update': metrics.timestamp
                }
            
            # Update unified state
            self.unified_state.update_state('edge_metrics', edge_state, 'edge_tracker')
            self.unified_state.update_state('portfolio_edge_summary', portfolio_summary, 'edge_tracker')
            
            self.logger.debug(f"Updated edge state for {len(all_metrics)} strategies")
            
        except Exception as e:
            self.logger.error(f"Error updating edge state: {e}")
    
    def get_strategy_capital_multiplier(self, strategy_id: str) -> float:
        """Get capital multiplier for strategy from state"""
        edge_state = self.unified_state.get_state('edge_metrics', {})
        try:
            if strategy_id in edge_state:
                return edge_state[strategy_id].get('capital_multiplier', 0.5)
        except TypeError:
            # Handle mock objects
            pass
        return 0.5  # Conservative default
    
    def should_exit_strategy(self, strategy_id: str) -> bool:
        """Check if strategy should be exited from state"""
        edge_state = self.unified_state.get_state('edge_metrics', {})
        try:
            if strategy_id in edge_state:
                return edge_state[strategy_id].get('should_exit', False)
        except TypeError:
            # Handle mock objects
            pass
        return False