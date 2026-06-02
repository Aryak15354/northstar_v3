"""
Regime-Adaptive Capital Allocator

Dynamically allocates capital across strategy buckets based on:
- Current volatility regime (low-vol, high-vol, crisis, transition)
- Historical performance by regime
- Kelly criterion with fractional sizing
- Regime-conditional constraints
- Drawdown-based adjustments

Strategy Buckets:
- dispersion: Index vs stock volatility arbitrage
- gamma_scalp: Realized variance harvesting
- short_vol: Premium selling strategies
- long_vol: Volatility buying strategies
- tail_hedge: Crisis protection
- directional_vol: Directional volatility bets
- relative_value: Volatility spread trading
- market_neutral: Delta-neutral strategies

System Laws:
- A1: Allocations must sum to total capital (Property 12)
- A2: Allocations must respect min/max bounds (Property 13)
- A3: Crisis regime blocks short vol strategies (safety first)
- A4: Drawdown reduces allocation proportionally
- A5: Kelly criterion with fractional sizing (0.25 default)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum

import numpy as np
import pandas as pd

from .regime_detector import VolatilityRegime
from .state_engine import VolatilityState

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for a strategy bucket"""
    returns: List[float] = field(default_factory=list)
    timestamps: List[datetime] = field(default_factory=list)
    regime: Optional[str] = None
    
    # Computed metrics
    mean_return: float = 0.0
    variance: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    win_rate: float = 0.0
    
    def compute_metrics(self):
        """Compute performance metrics from returns"""
        if not self.returns:
            return
        
        returns_array = np.array(self.returns)
        
        # Mean and variance
        self.mean_return = float(np.mean(returns_array))
        self.variance = float(np.var(returns_array))
        
        # Sharpe ratio (assuming daily returns, annualized)
        if self.variance > 0:
            self.sharpe_ratio = self.mean_return / np.sqrt(self.variance) * np.sqrt(252)
        
        # Max drawdown
        cumulative = np.cumprod(1 + returns_array)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        self.max_drawdown = float(np.min(drawdown))
        self.current_drawdown = float(drawdown[-1])
        
        # Win rate
        self.win_rate = float(np.sum(returns_array > 0) / len(returns_array))


@dataclass
class PerformanceHistory:
    """Historical performance tracking by strategy and regime"""
    
    # Performance by strategy and regime
    performance: Dict[str, Dict[str, PerformanceMetrics]] = field(default_factory=dict)
    
    def add_return(self, strategy: str, regime: str, return_value: float, timestamp: datetime):
        """Add a return observation"""
        if strategy not in self.performance:
            self.performance[strategy] = {}
        
        if regime not in self.performance[strategy]:
            self.performance[strategy][regime] = PerformanceMetrics(regime=regime)
        
        metrics = self.performance[strategy][regime]
        metrics.returns.append(return_value)
        metrics.timestamps.append(timestamp)
        metrics.compute_metrics()
    
    def get_returns(self, strategy: str, regime: str) -> List[float]:
        """Get returns for a strategy in a specific regime"""
        if strategy not in self.performance:
            return []
        
        if regime not in self.performance[strategy]:
            return []
        
        return self.performance[strategy][regime].returns
    
    def get_metrics(self, strategy: str, regime: str) -> Optional[PerformanceMetrics]:
        """Get performance metrics for a strategy in a specific regime"""
        if strategy not in self.performance:
            return None
        
        return self.performance[strategy].get(regime)
    
    def get_drawdown(self, strategy: str) -> float:
        """Get current drawdown for a strategy (across all regimes)"""
        if strategy not in self.performance:
            return 0.0
        
        # Get most recent drawdown across all regimes
        max_drawdown = 0.0
        for regime_metrics in self.performance[strategy].values():
            if abs(regime_metrics.current_drawdown) > abs(max_drawdown):
                max_drawdown = regime_metrics.current_drawdown
        
        return max_drawdown


@dataclass
class AllocationConstraints:
    """Allocation constraints for capital allocator"""
    
    # Min/max bounds per strategy (as fraction of total capital)
    min_allocations: Dict[str, float] = field(default_factory=dict)
    max_allocations: Dict[str, float] = field(default_factory=dict)
    
    # Regime-conditional constraints
    crisis_blocked_strategies: List[str] = field(default_factory=lambda: ['short_vol', 'dispersion'])
    low_vol_favored: List[str] = field(default_factory=lambda: ['short_vol', 'gamma_scalp'])
    high_vol_favored: List[str] = field(default_factory=lambda: ['gamma_scalp', 'dispersion'])
    transition_defensive: List[str] = field(default_factory=lambda: ['market_neutral', 'relative_value'])
    
    # Drawdown constraints
    drawdown_threshold: float = 0.10  # 10% drawdown triggers reduction
    max_drawdown: float = 0.25  # 25% max drawdown
    drawdown_reduction_factor: float = 0.5  # Reduce allocation by 50% in drawdown
    
    # Diversification
    max_single_strategy: float = 0.40  # Max 40% in any single strategy
    min_active_strategies: int = 3  # At least 3 strategies active


class CapitalAllocator:
    """
    Regime-Adaptive Capital Allocator
    
    Implements:
    - Kelly criterion with fractional sizing
    - Regime-based allocation adjustments
    - Drawdown-based allocation reduction
    - Min/max bounds enforcement
    - Diversification requirements
    
    System Laws:
    - A1: Allocations sum to total capital
    - A2: Allocations respect bounds
    - A3: Crisis blocks short vol
    - A4: Drawdown reduces allocation
    - A5: Fractional Kelly sizing
    """
    
    def __init__(
        self,
        strategy_buckets: Optional[List[str]] = None,
        kelly_fraction: float = 0.25,
        constraints: Optional[AllocationConstraints] = None
    ):
        """
        Initialize capital allocator
        
        Args:
            strategy_buckets: List of strategy bucket names
            kelly_fraction: Fractional Kelly sizing (0.25 = quarter Kelly)
            constraints: Allocation constraints
        """
        if strategy_buckets is None:
            self.strategy_buckets = [
                'dispersion',
                'gamma_scalp',
                'short_vol',
                'long_vol',
                'tail_hedge',
                'directional_vol',
                'relative_value',
                'market_neutral'
            ]
        else:
            self.strategy_buckets = strategy_buckets
        
        self.kelly_fraction = kelly_fraction
        
        if constraints is None:
            # Default constraints
            self.constraints = AllocationConstraints(
                min_allocations={s: 0.0 for s in self.strategy_buckets},
                max_allocations={s: 0.40 for s in self.strategy_buckets}
            )
        else:
            self.constraints = constraints
        
        # Performance tracking
        self.performance_history = PerformanceHistory()
        
        logger.info(
            f"CapitalAllocator initialized: {len(self.strategy_buckets)} strategies, "
            f"kelly_fraction={kelly_fraction}"
        )
    
    def allocate_capital(
        self,
        total_capital: float,
        state: VolatilityState
    ) -> Dict[str, float]:
        """
        Allocate capital across strategy buckets
        
        Implements Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7
        
        Args:
            total_capital: Total available capital
            state: Current volatility state
        
        Returns:
            Dict mapping strategy name to allocated capital
        """
        logger.info(
            f"Allocating {total_capital:,.0f} capital in regime: {state.regime.regime}"
        )
        
        # Check for infeasible constraints and adjust if needed
        self._check_and_adjust_constraints()
        
        # Get regime
        regime = state.regime.regime
        regime_probs = state.regime.regime_probabilities
        
        # Step 1: Compute Kelly fractions for each strategy
        kelly_fractions = self._compute_kelly_fractions(regime)
        
        # Step 2: Apply regime-conditional constraints
        regime_adjusted = self._apply_regime_constraints(
            kelly_fractions,
            regime,
            regime_probs
        )
        
        # Step 3: Apply drawdown-based adjustments
        drawdown_adjusted = self._adjust_for_drawdown(regime_adjusted)
        
        # Step 4: Normalize to total capital (SYSTEM LAW A1)
        normalized = self._normalize_to_capital(drawdown_adjusted, total_capital)
        
        # Step 5: Enforce min/max bounds AFTER normalization (SYSTEM LAW A2)
        bounded = self._enforce_bounds_absolute(normalized, total_capital)
        
        # Step 6: Enforce diversification requirements AFTER bounds
        allocations = self._enforce_diversification_absolute(bounded, total_capital)
        
        # Validate allocations
        self._validate_allocations(allocations, total_capital)
        
        logger.info(f"Capital allocation complete:")
        for strategy, capital in sorted(allocations.items(), key=lambda x: -x[1]):
            if capital > 0:
                pct = capital / total_capital * 100
                logger.info(f"  {strategy}: ${capital:,.0f} ({pct:.1f}%)")
        
        return allocations
    
    def _check_and_adjust_constraints(self):
        """
        Check if constraints are feasible and adjust if needed
        
        If min bounds sum to > 100%, scale them down proportionally
        """
        total_min = sum(self.constraints.min_allocations.values())
        
        if total_min > 1.0:
            logger.warning(
                f"Infeasible min bounds (sum={total_min:.2%} > 100%), "
                f"scaling down proportionally"
            )
            scale_factor = 0.95 / total_min  # Leave 5% slack
            
            self.constraints.min_allocations = {
                s: v * scale_factor
                for s, v in self.constraints.min_allocations.items()
            }
    
    def _compute_kelly_fractions(self, regime: str) -> Dict[str, float]:
        """
        Compute Kelly fractions for each strategy
        
        Kelly criterion: f = mean_return / variance
        With fractional sizing for safety: f_actual = kelly_fraction * f
        
        Implements Requirement 6.3
        """
        kelly_fractions = {}
        
        for strategy in self.strategy_buckets:
            metrics = self.performance_history.get_metrics(strategy, regime)
            
            if metrics is None or len(metrics.returns) < 10:
                # Insufficient data - use neutral allocation
                kelly_fractions[strategy] = 0.0
                continue
            
            # Kelly criterion: f = mean / variance
            if metrics.variance > 0 and metrics.mean_return > 0:
                kelly = metrics.mean_return / metrics.variance
                
                # Apply fractional Kelly (SYSTEM LAW A5)
                kelly_fractions[strategy] = kelly * self.kelly_fraction
            else:
                kelly_fractions[strategy] = 0.0
        
        logger.debug(f"Kelly fractions: {kelly_fractions}")
        return kelly_fractions
    
    def _apply_regime_constraints(
        self,
        allocations: Dict[str, float],
        regime: str,
        regime_probs: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Apply regime-specific allocation constraints
        
        Implements Requirements 6.6, 6.7
        """
        constrained = allocations.copy()
        
        if regime == 'crisis' or regime == VolatilityRegime.CRISIS.value:
            # SYSTEM LAW A3: Crisis blocks short vol strategies (respecting min bounds)
            for strategy in self.constraints.crisis_blocked_strategies:
                if strategy in constrained:
                    # Set to min bound instead of 0 to respect constraints
                    min_bound = self.constraints.min_allocations.get(strategy, 0.0)
                    logger.info(f"Crisis regime: reducing {strategy} to min bound {min_bound}")
                    constrained[strategy] = min_bound
            
            # Increase allocation to protective strategies
            if 'long_vol' in constrained:
                constrained['long_vol'] *= 2.0
            if 'tail_hedge' in constrained:
                constrained['tail_hedge'] *= 3.0
        
        elif regime == 'low_vol' or regime == VolatilityRegime.LOW_VOL.value:
            # Low vol: favor short vol and carry strategies
            for strategy in self.constraints.low_vol_favored:
                if strategy in constrained:
                    constrained[strategy] *= 1.5
            
            # Reduce gamma scalping (less realized vol to harvest)
            if 'gamma_scalp' in constrained:
                constrained['gamma_scalp'] *= 0.5
        
        elif regime == 'high_vol' or regime == VolatilityRegime.HIGH_VOL.value:
            # High vol: favor gamma scalping and dispersion
            for strategy in self.constraints.high_vol_favored:
                if strategy in constrained:
                    constrained[strategy] *= 1.5
            
            # Reduce short vol (higher risk)
            if 'short_vol' in constrained:
                constrained['short_vol'] *= 0.5
        
        elif regime == 'transition' or regime == VolatilityRegime.TRANSITION.value:
            # Uncertain regime: increase market-neutral strategies
            for strategy in self.constraints.transition_defensive:
                if strategy in constrained:
                    constrained[strategy] *= 1.2
            
            # Reduce directional exposure
            if 'directional_vol' in constrained:
                constrained['directional_vol'] *= 0.5
        
        logger.debug(f"Regime-adjusted allocations: {constrained}")
        return constrained
    
    def _adjust_for_drawdown(
        self,
        allocations: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Reduce allocation to strategies in drawdown
        
        Implements Requirement 6.5 (SYSTEM LAW A4)
        """
        adjusted = allocations.copy()
        
        for strategy in allocations.keys():
            # Get current drawdown
            drawdown = self.performance_history.get_drawdown(strategy)
            
            if abs(drawdown) > self.constraints.drawdown_threshold:
                # Reduce allocation proportionally to drawdown
                reduction_factor = 1.0 - (
                    abs(drawdown) / self.constraints.max_drawdown
                ) * self.constraints.drawdown_reduction_factor
                
                # Ensure minimum 10% allocation if strategy was active
                reduction_factor = max(reduction_factor, 0.1)
                
                adjusted[strategy] *= reduction_factor
                
                logger.info(
                    f"Drawdown adjustment for {strategy}: "
                    f"{drawdown:.1%} drawdown -> {reduction_factor:.1%} allocation"
                )
        
        return adjusted
    
    def _enforce_bounds(
        self,
        allocations: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Enforce min/max allocation bounds (on fractions)
        
        Implements Requirement 6.4 (SYSTEM LAW A2)
        """
        bounded = {}
        
        for strategy, allocation in allocations.items():
            min_alloc = self.constraints.min_allocations.get(strategy, 0.0)
            max_alloc = self.constraints.max_allocations.get(strategy, 1.0)
            
            bounded[strategy] = float(np.clip(allocation, min_alloc, max_alloc))
        
        return bounded
    
    def _enforce_bounds_absolute(
        self,
        allocations: Dict[str, float],
        total_capital: float
    ) -> Dict[str, float]:
        """
        Enforce min/max allocation bounds on absolute capital amounts
        
        This is applied AFTER normalization to ensure bounds are respected
        in the final allocation. Uses iterative approach to handle cases
        where capping one strategy requires redistributing to others.
        
        Implements Requirement 6.4 (SYSTEM LAW A2)
        """
        bounded = allocations.copy()
        max_iterations = 10
        
        for iteration in range(max_iterations):
            violations = []
            
            # Check for bound violations
            for strategy, capital in bounded.items():
                fraction = capital / total_capital if total_capital > 0 else 0
                
                min_alloc = self.constraints.min_allocations.get(strategy, 0.0)
                max_alloc = self.constraints.max_allocations.get(strategy, 1.0)
                
                if fraction > max_alloc + 1e-6:
                    violations.append((strategy, 'max', fraction, max_alloc))
                elif fraction < min_alloc - 1e-6 and capital > 0:
                    # Only enforce min if strategy has some allocation
                    violations.append((strategy, 'min', fraction, min_alloc))
            
            if not violations:
                # No violations, we're done
                break
            
            # Fix violations
            for strategy, violation_type, current_fraction, bound in violations:
                if violation_type == 'max':
                    # Cap at max bound
                    excess = bounded[strategy] - (bound * total_capital)
                    bounded[strategy] = bound * total_capital
                    
                    # Redistribute excess to other strategies that aren't at max
                    eligible = {
                        s: c for s, c in bounded.items()
                        if s != strategy and c / total_capital < self.constraints.max_allocations.get(s, 1.0) - 1e-6
                    }
                    
                    if eligible:
                        total_eligible = sum(eligible.values())
                        if total_eligible > 0:
                            for s in eligible.keys():
                                bounded[s] += excess * (eligible[s] / total_eligible)
                        else:
                            # All other strategies at max - distribute equally
                            per_strategy = excess / len(eligible)
                            for s in eligible.keys():
                                bounded[s] += per_strategy
                
                elif violation_type == 'min':
                    # Increase to min bound
                    deficit = (bound * total_capital) - bounded[strategy]
                    bounded[strategy] = bound * total_capital
                    
                    # Take from other strategies proportionally
                    eligible = {
                        s: c for s, c in bounded.items()
                        if s != strategy and c / total_capital > self.constraints.min_allocations.get(s, 0.0) + 1e-6
                    }
                    
                    if eligible:
                        total_eligible = sum(eligible.values())
                        if total_eligible > 0:
                            for s in eligible.keys():
                                reduction = deficit * (eligible[s] / total_eligible)
                                bounded[s] = max(0, bounded[s] - reduction)
        
        # Final normalization to ensure exact sum
        total_bounded = sum(bounded.values())
        if total_bounded > 0 and abs(total_bounded - total_capital) > 0.01:
            scale = total_capital / total_bounded
            bounded = {s: c * scale for s, c in bounded.items()}
        
        return bounded
    
    def _enforce_diversification(
        self,
        allocations: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Enforce diversification requirements
        
        Ensures:
        - No single strategy exceeds max_single_strategy (or its max bound, whichever is lower)
        - At least min_active_strategies are active
        """
        diversified = allocations.copy()
        
        # Enforce max single strategy allocation (respect actual max bounds)
        total = sum(diversified.values())
        if total > 0:
            for strategy in diversified.keys():
                # Use the lower of max_single_strategy and actual max bound
                max_fraction = min(
                    self.constraints.max_single_strategy,
                    self.constraints.max_allocations.get(strategy, 1.0)
                )
                
                if diversified[strategy] / total > max_fraction:
                    logger.info(
                        f"Capping {strategy} at {max_fraction:.1%} of total"
                    )
                    diversified[strategy] = total * max_fraction
        
        # Ensure minimum active strategies
        active_strategies = sum(1 for v in diversified.values() if v > 0)
        if active_strategies < self.constraints.min_active_strategies:
            # Activate strategies with highest Kelly fractions
            sorted_strategies = sorted(
                diversified.items(),
                key=lambda x: -x[1]
            )
            
            for i in range(self.constraints.min_active_strategies):
                if i < len(sorted_strategies):
                    strategy = sorted_strategies[i][0]
                    if diversified[strategy] == 0:
                        # Give minimum allocation
                        diversified[strategy] = 0.05  # 5% minimum
        
        return diversified
    
    def _enforce_diversification_absolute(
        self,
        allocations: Dict[str, float],
        total_capital: float
    ) -> Dict[str, float]:
        """
        Enforce diversification requirements on absolute capital amounts
        
        Ensures:
        - No single strategy exceeds max_single_strategy (or its max bound, whichever is lower)
        - At least min_active_strategies are active
        
        This is called AFTER bounds enforcement to ensure max_single_strategy is respected.
        """
        diversified = allocations.copy()
        
        # Iteratively enforce max single strategy allocation
        max_iterations = 10
        for iteration in range(max_iterations):
            total = sum(diversified.values())
            if total == 0:
                break
            
            violations = []
            for strategy in diversified.keys():
                fraction = diversified[strategy] / total
                
                # Use the lower of max_single_strategy and actual max bound
                max_fraction = min(
                    self.constraints.max_single_strategy,
                    self.constraints.max_allocations.get(strategy, 1.0)
                )
                
                if fraction > max_fraction + 1e-6:
                    violations.append((strategy, fraction, max_fraction))
            
            if not violations:
                # No violations, we're done
                break
            
            # Fix violations by capping and redistributing
            for strategy, current_fraction, max_fraction in violations:
                logger.info(
                    f"Iteration {iteration}: Capping {strategy} at {max_fraction:.1%} of total (was {current_fraction:.1%})"
                )
                excess = diversified[strategy] - (total * max_fraction)
                diversified[strategy] = total * max_fraction
                
                # Redistribute excess to other strategies that aren't at their max
                eligible = {}
                for s, c in diversified.items():
                    if s != strategy and c > 0:
                        s_fraction = c / total
                        s_max_fraction = min(
                            self.constraints.max_single_strategy,
                            self.constraints.max_allocations.get(s, 1.0)
                        )
                        # Only eligible if below max
                        if s_fraction < s_max_fraction - 1e-6:
                            # Weight by how much room they have
                            room = s_max_fraction - s_fraction
                            eligible[s] = (c, room)
                
                if eligible:
                    # Distribute proportionally to room available
                    total_room = sum(room for _, room in eligible.values())
                    if total_room > 0:
                        for s, (c, room) in eligible.items():
                            addition = excess * (room / total_room)
                            diversified[s] += addition
                    else:
                        # All at max - distribute equally
                        per_strategy = excess / len(eligible)
                        for s in eligible.keys():
                            diversified[s] += per_strategy
                else:
                    # No eligible strategies - this shouldn't happen but handle it
                    logger.warning(f"No eligible strategies to redistribute excess from {strategy}")
        
        # Ensure minimum active strategies
        active_strategies = sum(1 for v in diversified.values() if v > total_capital * 0.001)  # >0.1% threshold
        if active_strategies < self.constraints.min_active_strategies:
            # Activate strategies with highest potential
            sorted_strategies = sorted(
                diversified.items(),
                key=lambda x: -x[1]
            )
            
            for i in range(self.constraints.min_active_strategies):
                if i < len(sorted_strategies):
                    strategy = sorted_strategies[i][0]
                    if diversified[strategy] < total_capital * 0.001:
                        # Give minimum allocation (1% of total)
                        min_alloc = max(
                            total_capital * 0.01,
                            self.constraints.min_allocations.get(strategy, 0.0) * total_capital
                        )
                        diversified[strategy] = min_alloc
        
        # Final normalization to ensure exact sum
        total_diversified = sum(diversified.values())
        if total_diversified > 0 and abs(total_diversified - total_capital) > 0.01:
            scale = total_capital / total_diversified
            diversified = {s: c * scale for s, c in diversified.items()}
        
        return diversified
    
    def _normalize_to_capital(
        self,
        allocations: Dict[str, float],
        total_capital: float
    ) -> Dict[str, float]:
        """
        Normalize allocations to sum to total capital
        
        Implements SYSTEM LAW A1
        """
        # Sum of allocation fractions
        total_fraction = sum(allocations.values())
        
        if total_fraction == 0:
            # No allocations - distribute equally
            equal_fraction = 1.0 / len(self.strategy_buckets)
            return {s: total_capital * equal_fraction for s in self.strategy_buckets}
        
        # Normalize to total capital
        normalized = {
            strategy: (fraction / total_fraction) * total_capital
            for strategy, fraction in allocations.items()
        }
        
        return normalized
    
    def _validate_allocations(
        self,
        allocations: Dict[str, float],
        total_capital: float
    ):
        """
        Validate allocations satisfy system laws
        
        SYSTEM LAW A1: Allocations sum to total capital
        SYSTEM LAW A2: Allocations respect bounds
        """
        # Check sum (SYSTEM LAW A1)
        total_allocated = sum(allocations.values())
        tolerance = 0.01  # 1 cent tolerance
        
        if abs(total_allocated - total_capital) > tolerance:
            raise ValueError(
                f"SYSTEM LAW A1 VIOLATION: Allocations sum to {total_allocated:,.2f}, "
                f"expected {total_capital:,.2f}"
            )
        
        # Check bounds (SYSTEM LAW A2)
        for strategy, capital in allocations.items():
            fraction = capital / total_capital if total_capital > 0 else 0
            
            min_alloc = self.constraints.min_allocations.get(strategy, 0.0)
            max_alloc = self.constraints.max_allocations.get(strategy, 1.0)
            
            # Only check min bound if strategy has non-zero allocation
            # (zero allocation is acceptable even if min > 0)
            if capital > 0.01 and fraction < min_alloc - 1e-6:
                raise ValueError(
                    f"SYSTEM LAW A2 VIOLATION: {strategy} allocation {fraction:.2%} "
                    f"outside bounds [{min_alloc:.2%}, {max_alloc:.2%}]"
                )
            
            if fraction > max_alloc + 1e-6:
                raise ValueError(
                    f"SYSTEM LAW A2 VIOLATION: {strategy} allocation {fraction:.2%} "
                    f"outside bounds [{min_alloc:.2%}, {max_alloc:.2%}]"
                )
        
        logger.debug("✅ Allocation validation passed")
    
    def add_performance_observation(
        self,
        strategy: str,
        regime: str,
        return_value: float,
        timestamp: Optional[datetime] = None
    ):
        """
        Add a performance observation for a strategy
        
        Implements Requirement 6.2
        
        Args:
            strategy: Strategy bucket name
            regime: Regime during observation
            return_value: Return value (e.g., 0.05 for 5% return)
            timestamp: Observation timestamp
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        self.performance_history.add_return(strategy, regime, return_value, timestamp)
        
        logger.debug(
            f"Performance observation: {strategy} in {regime}: {return_value:.2%}"
        )
    
    def get_allocation_summary(
        self,
        allocations: Dict[str, float],
        total_capital: float
    ) -> pd.DataFrame:
        """
        Get allocation summary as DataFrame
        
        Args:
            allocations: Capital allocations
            total_capital: Total capital
        
        Returns:
            DataFrame with allocation details
        """
        rows = []
        
        for strategy, capital in sorted(allocations.items(), key=lambda x: -x[1]):
            if capital > 0:
                fraction = capital / total_capital if total_capital > 0 else 0
                
                rows.append({
                    'strategy': strategy,
                    'capital': capital,
                    'fraction': fraction,
                    'min_bound': self.constraints.min_allocations.get(strategy, 0.0),
                    'max_bound': self.constraints.max_allocations.get(strategy, 1.0)
                })
        
        return pd.DataFrame(rows)
