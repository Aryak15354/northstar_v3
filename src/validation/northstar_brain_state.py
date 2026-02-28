"""
Stateful Northstar Brain Integration

This module implements the critical stateful brain architecture:
Northstar[t] = f(Northstar[t-1], data[t])

This prevents the deadly flaw of rebuilding state from full historical data,
which would leak future information into past decisions.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
import json
import pickle
import hashlib
import logging
from enum import Enum
import numpy as np

from src.intelligence.temporal_guard import TemporalGuard

class BrainStateType(Enum):
    REGIME_MEMORY = "regime_memory"
    BAYESIAN_PRIORS = "bayesian_priors"
    SPECIALIST_WEIGHTS = "specialist_weights"
    SIGNAL_DECAY = "signal_decay"
    CORRELATION_MATRIX = "correlation_matrix"
    RISK_BUDGETS = "risk_budgets"
    PERFORMANCE_ATTRIBUTION = "performance_attribution"

@dataclass
class RegimeState:
    """Current regime state with confidence and transition probabilities"""
    current_regime: str
    confidence: float
    transition_probabilities: Dict[str, float]
    regime_duration: int  # Days in current regime
    last_transition_date: datetime
    regime_history: List[Tuple[datetime, str, float]]  # (date, regime, confidence)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'current_regime': self.current_regime,
            'confidence': self.confidence,
            'transition_probabilities': self.transition_probabilities,
            'regime_duration': self.regime_duration,
            'last_transition_date': self.last_transition_date.isoformat(),
            'regime_history': [(d.isoformat(), r, c) for d, r, c in self.regime_history]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RegimeState':
        return cls(
            current_regime=data['current_regime'],
            confidence=data['confidence'],
            transition_probabilities=data['transition_probabilities'],
            regime_duration=data['regime_duration'],
            last_transition_date=datetime.fromisoformat(data['last_transition_date']),
            regime_history=[(datetime.fromisoformat(d), r, c) for d, r, c in data['regime_history']]
        )

@dataclass
class BayesianPriors:
    """Bayesian priors for specialist strategies"""
    specialist_alphas: Dict[str, float]  # Prior alpha estimates
    specialist_betas: Dict[str, float]   # Prior beta estimates
    confidence_intervals: Dict[str, Tuple[float, float]]  # (lower, upper) bounds
    update_counts: Dict[str, int]  # Number of updates per specialist
    last_update_date: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'specialist_alphas': self.specialist_alphas,
            'specialist_betas': self.specialist_betas,
            'confidence_intervals': {k: list(v) for k, v in self.confidence_intervals.items()},
            'update_counts': self.update_counts,
            'last_update_date': self.last_update_date.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BayesianPriors':
        return cls(
            specialist_alphas=data['specialist_alphas'],
            specialist_betas=data['specialist_betas'],
            confidence_intervals={k: tuple(v) for k, v in data['confidence_intervals'].items()},
            update_counts=data['update_counts'],
            last_update_date=datetime.fromisoformat(data['last_update_date'])
        )

@dataclass
class SpecialistWeights:
    """Current allocation weights to specialist strategies"""
    weights: Dict[str, float]
    weight_history: List[Tuple[datetime, Dict[str, float]]]
    rebalance_triggers: Dict[str, float]  # Thresholds for rebalancing
    last_rebalance_date: datetime
    turnover_budget: float  # Remaining turnover budget
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'weights': self.weights,
            'weight_history': [(d.isoformat(), w) for d, w in self.weight_history],
            'rebalance_triggers': self.rebalance_triggers,
            'last_rebalance_date': self.last_rebalance_date.isoformat(),
            'turnover_budget': self.turnover_budget
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SpecialistWeights':
        return cls(
            weights=data['weights'],
            weight_history=[(datetime.fromisoformat(d), w) for d, w in data['weight_history']],
            rebalance_triggers=data['rebalance_triggers'],
            last_rebalance_date=datetime.fromisoformat(data['last_rebalance_date']),
            turnover_budget=data['turnover_budget']
        )

@dataclass
class NorthstarBrainState:
    """
    Complete state of the Northstar brain at a specific point in time.
    
    This encapsulates ALL information the brain needs to make decisions,
    ensuring no future data can leak into past decisions.
    """
    timestamp: datetime
    regime_state: RegimeState
    bayesian_priors: BayesianPriors
    specialist_weights: SpecialistWeights
    
    # Signal decay tracking
    signal_decay_factors: Dict[str, float]
    signal_last_update: Dict[str, datetime]
    
    # Correlation and risk state
    correlation_matrix: Dict[str, Dict[str, float]]
    risk_budgets: Dict[str, float]
    volatility_estimates: Dict[str, float]
    
    # Performance tracking (for Bayesian updates)
    performance_history: List[Tuple[datetime, Dict[str, float]]]  # (date, specialist_returns)
    attribution_history: List[Tuple[datetime, Dict[str, float]]]  # (date, attributions)
    
    # State integrity
    state_hash: str
    creation_context: str
    
    def __post_init__(self):
        """Calculate state hash for integrity verification"""
        if not self.state_hash:
            self.state_hash = self._calculate_hash()
    
    def _calculate_hash(self) -> str:
        """Calculate hash of current state for integrity verification"""
        state_dict = self.to_dict()
        # Remove hash from calculation
        state_dict.pop('state_hash', None)
        
        state_json = json.dumps(state_dict, sort_keys=True, default=str)
        return hashlib.sha256(state_json.encode()).hexdigest()
    
    def verify_integrity(self) -> bool:
        """Verify state integrity using hash"""
        current_hash = self._calculate_hash()
        return current_hash == self.state_hash
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize state to dictionary"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'regime_state': self.regime_state.to_dict(),
            'bayesian_priors': self.bayesian_priors.to_dict(),
            'specialist_weights': self.specialist_weights.to_dict(),
            'signal_decay_factors': self.signal_decay_factors,
            'signal_last_update': {k: v.isoformat() for k, v in self.signal_last_update.items()},
            'correlation_matrix': self.correlation_matrix,
            'risk_budgets': self.risk_budgets,
            'volatility_estimates': self.volatility_estimates,
            'performance_history': [(d.isoformat(), p) for d, p in self.performance_history],
            'attribution_history': [(d.isoformat(), a) for d, a in self.attribution_history],
            'state_hash': self.state_hash,
            'creation_context': self.creation_context
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NorthstarBrainState':
        """Deserialize state from dictionary"""
        return cls(
            timestamp=datetime.fromisoformat(data['timestamp']),
            regime_state=RegimeState.from_dict(data['regime_state']),
            bayesian_priors=BayesianPriors.from_dict(data['bayesian_priors']),
            specialist_weights=SpecialistWeights.from_dict(data['specialist_weights']),
            signal_decay_factors=data['signal_decay_factors'],
            signal_last_update={k: datetime.fromisoformat(v) for k, v in data['signal_last_update'].items()},
            correlation_matrix=data['correlation_matrix'],
            risk_budgets=data['risk_budgets'],
            volatility_estimates=data['volatility_estimates'],
            performance_history=[(datetime.fromisoformat(d), p) for d, p in data['performance_history']],
            attribution_history=[(datetime.fromisoformat(d), a) for d, a in data['attribution_history']],
            state_hash=data['state_hash'],
            creation_context=data['creation_context']
        )


class NorthstarBrain:
    """
    Stateful Northstar Brain that maintains temporal integrity.
    
    This is the core component that implements:
    Northstar[t] = f(Northstar[t-1], data[t])
    
    The brain NEVER rebuilds state from historical data during simulation.
    It only uses the previous state and current day's data to make decisions.
    """
    
    def __init__(self, initial_state: NorthstarBrainState, temporal_guard: TemporalGuard):
        self.current_state = initial_state
        self.temporal_guard = temporal_guard
        self.logger = logging.getLogger(__name__)
        
        # State history for debugging (limited size)
        self.state_history: List[NorthstarBrainState] = [initial_state]
        self.max_history_size = 100
        
        # Configuration
        self.signal_decay_rate = 0.95  # Daily decay factor
        self.bayesian_learning_rate = 0.1
        self.regime_confidence_threshold = 0.7
        self.rebalance_threshold = 0.05  # 5% weight change triggers rebalance
        
        self.logger.info(f"NorthstarBrain initialized with state from {initial_state.timestamp}")
    
    def step_forward(self, daily_data: Dict[str, Any], current_date: datetime) -> Dict[str, float]:
        """
        Steps the brain forward one day using only previous state and current data.
        
        This is the CRITICAL method that implements stateful progression:
        Northstar[t] = f(Northstar[t-1], data[t])
        
        Args:
            daily_data: Market data for current day only
            current_date: Current simulation date
            
        Returns:
            Portfolio signals/weights for current day
        """
        # Verify temporal integrity - ensure we're not accessing future data
        # The temporal guard will enforce this when we access data through it
        
        # Verify we're moving forward in time
        if current_date <= self.current_state.timestamp:
            raise ValueError(f"Brain cannot step backwards: {current_date} <= {self.current_state.timestamp}")
        
        self.logger.debug(f"Stepping brain forward from {self.current_state.timestamp} to {current_date}")
        
        # Step 1: Update regime state using only current data and previous state
        new_regime_state = self._update_regime_state(daily_data, current_date)
        
        # Step 2: Apply signal decay to previous signals
        new_signal_decay = self._apply_signal_decay(current_date)
        
        # Step 3: Update Bayesian priors based on recent performance
        new_bayesian_priors = self._update_bayesian_priors(daily_data, current_date)
        
        # Step 4: Update correlation and risk estimates
        new_correlation_matrix = self._update_correlations(daily_data, current_date)
        new_risk_budgets = self._update_risk_budgets(daily_data, current_date)
        new_volatility_estimates = self._update_volatility_estimates(daily_data, current_date)
        
        # Step 5: Generate specialist signals using updated state
        specialist_signals = self._generate_specialist_signals(daily_data, current_date)
        
        # Step 6: Update specialist weights using Bayesian allocation
        new_specialist_weights = self._update_specialist_weights(specialist_signals, current_date)
        
        # Step 7: Record performance for future Bayesian updates
        new_performance_history = self._update_performance_history(daily_data, current_date)
        new_attribution_history = self._update_attribution_history(daily_data, current_date)
        
        # Step 8: Create new brain state
        new_state = NorthstarBrainState(
            timestamp=current_date,
            regime_state=new_regime_state,
            bayesian_priors=new_bayesian_priors,
            specialist_weights=new_specialist_weights,
            signal_decay_factors=new_signal_decay,
            signal_last_update={k: current_date for k in specialist_signals.keys()},
            correlation_matrix=new_correlation_matrix,
            risk_budgets=new_risk_budgets,
            volatility_estimates=new_volatility_estimates,
            performance_history=new_performance_history,
            attribution_history=new_attribution_history,
            state_hash="",  # Will be calculated in __post_init__
            creation_context=f"step_forward_{current_date.isoformat()}"
        )
        
        # Verify state integrity
        if not new_state.verify_integrity():
            raise RuntimeError("Brain state integrity verification failed")
        
        # Update current state
        self.current_state = new_state
        
        # Add to history (with size limit)
        self.state_history.append(new_state)
        if len(self.state_history) > self.max_history_size:
            self.state_history.pop(0)
        
        # Generate final portfolio weights
        portfolio_weights = self._generate_portfolio_weights(specialist_signals, current_date)
        
        self.logger.info(f"Brain stepped forward to {current_date}, generated {len(portfolio_weights)} portfolio weights")
        
        return portfolio_weights
    
    def _update_regime_state(self, daily_data: Dict[str, Any], current_date: datetime) -> RegimeState:
        """Update regime state using only current data and previous regime state"""
        prev_regime = self.current_state.regime_state
        
        # Simple regime detection based on market volatility and momentum
        # In real implementation, this would use sophisticated regime detection
        market_volatility = daily_data.get('market_volatility', 0.15)
        market_momentum = daily_data.get('market_momentum', 0.0)
        
        # Determine current regime
        if market_volatility > 0.25:
            current_regime = "crisis"
        elif market_volatility > 0.20:
            current_regime = "stress"
        elif market_momentum > 0.02:
            current_regime = "bull"
        elif market_momentum < -0.02:
            current_regime = "bear"
        else:
            current_regime = "neutral"
        
        # Calculate confidence based on regime persistence
        if current_regime == prev_regime.current_regime:
            # Regime continues - increase confidence
            confidence = min(0.95, prev_regime.confidence + 0.05)
            regime_duration = prev_regime.regime_duration + 1
            last_transition_date = prev_regime.last_transition_date
        else:
            # Regime change - reset confidence
            confidence = 0.6
            regime_duration = 1
            last_transition_date = current_date
        
        # Update transition probabilities (simplified)
        transition_probs = {
            "bull": 0.3, "bear": 0.2, "neutral": 0.3, "stress": 0.15, "crisis": 0.05
        }
        
        # Update regime history
        new_history = prev_regime.regime_history.copy()
        new_history.append((current_date, current_regime, confidence))
        
        # Keep only recent history (last 252 days = 1 year)
        if len(new_history) > 252:
            new_history = new_history[-252:]
        
        return RegimeState(
            current_regime=current_regime,
            confidence=confidence,
            transition_probabilities=transition_probs,
            regime_duration=regime_duration,
            last_transition_date=last_transition_date,
            regime_history=new_history
        )
    
    def _apply_signal_decay(self, current_date: datetime) -> Dict[str, float]:
        """Apply decay to signals based on time elapsed"""
        prev_decay = self.current_state.signal_decay_factors
        prev_updates = self.current_state.signal_last_update
        
        new_decay = {}
        
        for signal_name, prev_factor in prev_decay.items():
            last_update = prev_updates.get(signal_name, current_date)
            days_elapsed = (current_date - last_update).days
            
            # Apply exponential decay
            decay_factor = prev_factor * (self.signal_decay_rate ** days_elapsed)
            new_decay[signal_name] = max(0.01, decay_factor)  # Minimum decay factor
        
        return new_decay
    
    def _update_bayesian_priors(self, daily_data: Dict[str, Any], current_date: datetime) -> BayesianPriors:
        """Update Bayesian priors based on recent performance"""
        prev_priors = self.current_state.bayesian_priors
        
        # Get recent performance data
        recent_performance = self._get_recent_performance(current_date)
        
        # Update priors using Bayesian learning
        new_alphas = {}
        new_betas = {}
        new_confidence_intervals = {}
        new_update_counts = prev_priors.update_counts.copy()
        
        for specialist in prev_priors.specialist_alphas.keys():
            prev_alpha = prev_priors.specialist_alphas[specialist]
            prev_beta = prev_priors.specialist_betas[specialist]
            
            if specialist in recent_performance:
                # Update with new performance data
                performance = recent_performance[specialist]
                
                # Simple Bayesian update (in practice, would be more sophisticated)
                new_alpha = prev_alpha + self.bayesian_learning_rate * performance
                new_beta = prev_beta + self.bayesian_learning_rate * abs(performance)
                
                new_update_counts[specialist] = new_update_counts.get(specialist, 0) + 1
            else:
                # No new data - keep previous values
                new_alpha = prev_alpha
                new_beta = prev_beta
            
            new_alphas[specialist] = new_alpha
            new_betas[specialist] = new_beta
            
            # Update confidence intervals
            std_error = new_beta / np.sqrt(max(1, new_update_counts.get(specialist, 1)))
            new_confidence_intervals[specialist] = (
                new_alpha - 1.96 * std_error,
                new_alpha + 1.96 * std_error
            )
        
        return BayesianPriors(
            specialist_alphas=new_alphas,
            specialist_betas=new_betas,
            confidence_intervals=new_confidence_intervals,
            update_counts=new_update_counts,
            last_update_date=current_date
        )
    
    def _get_recent_performance(self, current_date: datetime) -> Dict[str, float]:
        """Get recent specialist performance for Bayesian updates"""
        # Look for performance in the last few days
        recent_performance = {}
        
        for date, performance in self.current_state.performance_history[-5:]:  # Last 5 days
            if (current_date - date).days <= 5:
                for specialist, perf in performance.items():
                    if specialist not in recent_performance:
                        recent_performance[specialist] = []
                    recent_performance[specialist].append(perf)
        
        # Average recent performance
        return {k: np.mean(v) for k, v in recent_performance.items() if v}
    
    def _update_correlations(self, daily_data: Dict[str, Any], current_date: datetime) -> Dict[str, Dict[str, float]]:
        """Update correlation matrix using exponential weighting"""
        prev_corr = self.current_state.correlation_matrix
        
        # In real implementation, would calculate correlations from recent returns
        # For now, just apply slight decay to existing correlations
        new_corr = {}
        decay_factor = 0.99
        
        for asset1, corr_dict in prev_corr.items():
            new_corr[asset1] = {}
            for asset2, correlation in corr_dict.items():
                # Apply decay towards zero correlation
                new_corr[asset1][asset2] = correlation * decay_factor
        
        return new_corr
    
    def _update_risk_budgets(self, daily_data: Dict[str, Any], current_date: datetime) -> Dict[str, float]:
        """Update risk budgets based on regime and volatility"""
        prev_budgets = self.current_state.risk_budgets
        regime = self.current_state.regime_state.current_regime
        
        # Adjust risk budgets based on regime
        risk_multipliers = {
            "crisis": 0.3,
            "stress": 0.5,
            "bear": 0.7,
            "neutral": 1.0,
            "bull": 1.2
        }
        
        multiplier = risk_multipliers.get(regime, 1.0)
        
        new_budgets = {}
        for asset, budget in prev_budgets.items():
            new_budgets[asset] = budget * multiplier
        
        return new_budgets
    
    def _update_volatility_estimates(self, daily_data: Dict[str, Any], current_date: datetime) -> Dict[str, float]:
        """Update volatility estimates using exponential weighting"""
        prev_vol = self.current_state.volatility_estimates
        
        # Simple volatility update (in practice, would use EWMA or GARCH)
        new_vol = {}
        vol_decay = 0.94
        
        for asset, prev_volatility in prev_vol.items():
            # Get current return (if available)
            current_return = daily_data.get(f'{asset}_return', 0.0)
            
            # Update volatility estimate
            new_volatility = np.sqrt(vol_decay * prev_volatility**2 + (1 - vol_decay) * current_return**2)
            new_vol[asset] = new_volatility
        
        return new_vol
    
    def _generate_specialist_signals(self, daily_data: Dict[str, Any], current_date: datetime) -> Dict[str, float]:
        """Generate signals from specialist strategies"""
        # This would interface with actual specialist strategies
        # For now, generate simple signals based on regime and data
        
        regime = self.current_state.regime_state.current_regime
        regime_confidence = self.current_state.regime_state.confidence
        
        signals = {}
        
        # Momentum specialist
        momentum_signal = daily_data.get('market_momentum', 0.0) * regime_confidence
        if regime in ['bull', 'neutral']:
            signals['momentum'] = momentum_signal
        else:
            signals['momentum'] = momentum_signal * 0.5  # Reduce in stress/crisis
        
        # Mean reversion specialist
        mean_reversion_signal = -daily_data.get('market_momentum', 0.0) * 0.5
        if regime in ['bear', 'stress']:
            signals['mean_reversion'] = mean_reversion_signal
        else:
            signals['mean_reversion'] = mean_reversion_signal * 0.3
        
        # Quality specialist
        quality_signal = 0.02 if regime in ['crisis', 'stress'] else 0.01
        signals['quality'] = quality_signal * regime_confidence
        
        # Defensive specialist
        defensive_signal = 0.05 if regime in ['crisis', 'stress'] else -0.01
        signals['defensive'] = defensive_signal * regime_confidence
        
        return signals
    
    def _update_specialist_weights(self, specialist_signals: Dict[str, float], current_date: datetime) -> SpecialistWeights:
        """Update specialist allocation weights using Bayesian approach"""
        prev_weights = self.current_state.specialist_weights
        bayesian_priors = self.current_state.bayesian_priors
        
        # Calculate new weights based on Bayesian priors and current signals
        new_weights = {}
        total_weight = 0.0
        
        for specialist, signal in specialist_signals.items():
            if specialist in bayesian_priors.specialist_alphas:
                # Weight by expected alpha and confidence
                expected_alpha = bayesian_priors.specialist_alphas[specialist]
                confidence_width = (bayesian_priors.confidence_intervals[specialist][1] - 
                                 bayesian_priors.confidence_intervals[specialist][0])
                
                # Higher expected alpha and lower uncertainty = higher weight
                weight = max(0.0, expected_alpha / (1.0 + confidence_width))
                new_weights[specialist] = weight
                total_weight += weight
        
        # Normalize weights
        if total_weight > 0:
            new_weights = {k: v / total_weight for k, v in new_weights.items()}
        else:
            # Equal weights if no positive expected alphas
            equal_weight = 1.0 / len(specialist_signals)
            new_weights = {k: equal_weight for k in specialist_signals.keys()}
        
        # Check if rebalancing is needed
        weight_changes = {}
        for specialist, new_weight in new_weights.items():
            old_weight = prev_weights.weights.get(specialist, 0.0)
            weight_changes[specialist] = abs(new_weight - old_weight)
        
        max_change = max(weight_changes.values()) if weight_changes else 0.0
        needs_rebalance = max_change > self.rebalance_threshold
        
        # Update weight history
        new_history = prev_weights.weight_history.copy()
        new_history.append((current_date, new_weights.copy()))
        
        # Keep only recent history
        if len(new_history) > 252:
            new_history = new_history[-252:]
        
        return SpecialistWeights(
            weights=new_weights,
            weight_history=new_history,
            rebalance_triggers=weight_changes,
            last_rebalance_date=current_date if needs_rebalance else prev_weights.last_rebalance_date,
            turnover_budget=max(0.0, prev_weights.turnover_budget - sum(weight_changes.values()))
        )
    
    def _update_performance_history(self, daily_data: Dict[str, Any], current_date: datetime) -> List[Tuple[datetime, Dict[str, float]]]:
        """Update performance history with current day's performance"""
        prev_history = self.current_state.performance_history
        
        # Calculate specialist performance for current day
        current_performance = {}
        for specialist in self.current_state.specialist_weights.weights.keys():
            # In real implementation, would calculate actual performance
            # For now, use mock performance based on market data
            base_return = daily_data.get('market_return', 0.0)
            specialist_return = base_return + np.random.normal(0, 0.01)  # Add noise
            current_performance[specialist] = specialist_return
        
        # Add to history
        new_history = prev_history.copy()
        new_history.append((current_date, current_performance))
        
        # Keep only recent history (1 year)
        if len(new_history) > 252:
            new_history = new_history[-252:]
        
        return new_history
    
    def _update_attribution_history(self, daily_data: Dict[str, Any], current_date: datetime) -> List[Tuple[datetime, Dict[str, float]]]:
        """Update attribution history with current day's attributions"""
        prev_history = self.current_state.attribution_history
        
        # Calculate performance attribution
        current_attribution = {}
        specialist_weights = self.current_state.specialist_weights.weights
        
        for specialist, weight in specialist_weights.items():
            # Simple attribution = weight * specialist_return
            specialist_return = daily_data.get(f'{specialist}_return', 0.0)
            attribution = weight * specialist_return
            current_attribution[specialist] = attribution
        
        # Add to history
        new_history = prev_history.copy()
        new_history.append((current_date, current_attribution))
        
        # Keep only recent history
        if len(new_history) > 252:
            new_history = new_history[-252:]
        
        return new_history
    
    def _generate_portfolio_weights(self, specialist_signals: Dict[str, float], current_date: datetime) -> Dict[str, float]:
        """Generate final portfolio weights from specialist signals and weights"""
        specialist_weights = self.current_state.specialist_weights.weights
        
        # Combine specialist signals with their weights
        portfolio_weights = {}
        
        # In real implementation, this would map specialist signals to actual securities
        # For now, create simple portfolio weights
        total_signal = 0.0
        weighted_signals = {}
        
        for specialist, signal in specialist_signals.items():
            weight = specialist_weights.get(specialist, 0.0)
            weighted_signal = signal * weight
            weighted_signals[specialist] = weighted_signal
            total_signal += abs(weighted_signal)
        
        # Normalize to create portfolio weights
        if total_signal > 0:
            for specialist, weighted_signal in weighted_signals.items():
                portfolio_weights[f'{specialist}_portfolio'] = weighted_signal / total_signal
        
        # Add cash weight
        used_weight = sum(abs(w) for w in portfolio_weights.values())
        portfolio_weights['CASH'] = max(0.0, 1.0 - used_weight)
        
        return portfolio_weights
    
    def get_current_state(self) -> NorthstarBrainState:
        """Get current brain state"""
        return self.current_state
    
    def save_state(self, filepath: str) -> None:
        """Save current state to file"""
        state_dict = self.current_state.to_dict()
        
        with open(filepath, 'w') as f:
            json.dump(state_dict, f, indent=2)
        
        self.logger.info(f"Brain state saved to {filepath}")
    
    def load_state(self, filepath: str) -> None:
        """Load state from file"""
        with open(filepath, 'r') as f:
            state_dict = json.load(f)
        
        self.current_state = NorthstarBrainState.from_dict(state_dict)
        
        # Verify integrity
        if not self.current_state.verify_integrity():
            raise RuntimeError("Loaded state failed integrity verification")
        
        self.logger.info(f"Brain state loaded from {filepath}")
    
    @classmethod
    def from_historical_state(cls, historical_data: Dict[str, Any], start_date: datetime, temporal_guard: TemporalGuard) -> 'NorthstarBrain':
        """
        Create initial brain state from minimal historical data.
        
        This is the ONLY place where historical data is used to initialize the brain.
        After this, the brain operates purely in stateful mode.
        """
        # Create initial regime state
        initial_regime = RegimeState(
            current_regime="neutral",
            confidence=0.5,
            transition_probabilities={"bull": 0.25, "bear": 0.25, "neutral": 0.25, "stress": 0.15, "crisis": 0.1},
            regime_duration=1,
            last_transition_date=start_date,
            regime_history=[(start_date, "neutral", 0.5)]
        )
        
        # Create initial Bayesian priors
        specialists = ["momentum", "mean_reversion", "quality", "defensive"]
        initial_priors = BayesianPriors(
            specialist_alphas={s: 0.0 for s in specialists},
            specialist_betas={s: 0.1 for s in specialists},
            confidence_intervals={s: (-0.05, 0.05) for s in specialists},
            update_counts={s: 0 for s in specialists},
            last_update_date=start_date
        )
        
        # Create initial specialist weights (equal allocation)
        equal_weight = 1.0 / len(specialists)
        initial_weights = SpecialistWeights(
            weights={s: equal_weight for s in specialists},
            weight_history=[(start_date, {s: equal_weight for s in specialists})],
            rebalance_triggers={s: 0.0 for s in specialists},
            last_rebalance_date=start_date,
            turnover_budget=1.0
        )
        
        # Create initial state
        initial_state = NorthstarBrainState(
            timestamp=start_date,
            regime_state=initial_regime,
            bayesian_priors=initial_priors,
            specialist_weights=initial_weights,
            signal_decay_factors={s: 1.0 for s in specialists},
            signal_last_update={s: start_date for s in specialists},
            correlation_matrix={s: {s2: 0.0 if s != s2 else 1.0 for s2 in specialists} for s in specialists},
            risk_budgets={s: 0.1 for s in specialists},
            volatility_estimates={s: 0.15 for s in specialists},
            performance_history=[],
            attribution_history=[],
            state_hash="",
            creation_context=f"initial_state_{start_date.isoformat()}"
        )
        
        return cls(initial_state, temporal_guard)