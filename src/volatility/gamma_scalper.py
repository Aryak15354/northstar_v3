"""
Gamma Scalping Engine for Northstar V3 Volatility System

Implements systematic delta-hedging of long gamma positions to harvest realized variance:
- Optimal hedging threshold calculation based on transaction costs and gamma exposure
- Hedge trigger detection when spot price moves beyond threshold
- Hedge order generation to maintain delta neutrality
- Realized variance tracking and comparison to implied variance
- Cumulative gamma P&L tracking
- Adaptive hedging frequency based on realized vs implied variance
- Support for continuous and discrete hedging modes
- Expiration-aware hedging adjustments

Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7
"""

import logging
import numpy as np
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from .greeks_aggregator import Position, Greeks

logger = logging.getLogger(__name__)


class HedgingMode(Enum):
    """Hedging frequency modes"""
    HIGH_FREQUENCY = "high_frequency"  # Hedge frequently when realized > implied
    NORMAL = "normal"                   # Standard threshold-based hedging
    LOW_FREQUENCY = "low_frequency"     # Reduce hedging when realized < implied
    CONTINUOUS = "continuous"           # Continuous delta hedging (very frequent)
    DISCRETE = "discrete"               # Discrete threshold-based hedging


@dataclass
class Hedge:
    """Record of a delta hedge execution"""
    timestamp: datetime
    position_id: str
    underlying: str
    price: float  # Spot price at hedge
    delta_before: float  # Delta before hedge
    delta_after: float  # Delta after hedge
    hedge_quantity: float  # Quantity of underlying traded
    transaction_cost: float  # Cost of hedge execution
    pnl: float  # Realized P&L from hedge


@dataclass
class RealizedPnL:
    """Realized P&L tracking for gamma scalping"""
    total_pnl: float  # Total P&L (option + hedges)
    option_pnl: float  # Option mark-to-market P&L
    hedge_pnl: float  # Cumulative hedge P&L
    variance_pnl: float  # P&L from variance difference
    realized_var: float  # Realized variance
    implied_var: float  # Implied variance paid
    num_hedges: int  # Number of hedges executed
    total_transaction_costs: float  # Cumulative transaction costs


@dataclass
class Order:
    """Order to execute"""
    instrument: str  # Underlying symbol
    quantity: float  # Quantity to trade (positive = buy, negative = sell)
    order_type: str  # 'market', 'limit', etc.
    reason: str  # Reason for order
    timestamp: datetime = field(default_factory=datetime.now)


class GammaScalper:
    """
    Gamma Scalping Engine
    
    Harvests realized variance through systematic delta-hedging of long gamma positions.
    
    Key Features:
    - Optimal hedging threshold based on transaction costs
    - Adaptive hedging frequency based on realized vs implied variance
    - Support for continuous and discrete hedging modes
    - Expiration-aware adjustments
    - Comprehensive P&L tracking
    
    Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7
    """
    
    def __init__(
        self,
        transaction_cost_bps: float = 5.0,  # Transaction cost in basis points
        default_mode: HedgingMode = HedgingMode.NORMAL,
        high_freq_threshold_multiplier: float = 0.5,  # Reduce threshold by 50% in high freq mode
        low_freq_threshold_multiplier: float = 2.0,   # Increase threshold by 100% in low freq mode
        expiration_days_threshold: int = 7,  # Days before expiration to adjust hedging
        expiration_threshold_multiplier: float = 0.7  # Reduce threshold near expiration
    ):
        """
        Initialize Gamma Scalper
        
        Args:
            transaction_cost_bps: Transaction cost in basis points
            default_mode: Default hedging mode
            high_freq_threshold_multiplier: Threshold multiplier for high frequency mode
            low_freq_threshold_multiplier: Threshold multiplier for low frequency mode
            expiration_days_threshold: Days before expiration to adjust hedging
            expiration_threshold_multiplier: Threshold multiplier near expiration
        """
        self.transaction_cost_bps = transaction_cost_bps
        self.default_mode = default_mode
        self.high_freq_threshold_multiplier = high_freq_threshold_multiplier
        self.low_freq_threshold_multiplier = low_freq_threshold_multiplier
        self.expiration_days_threshold = expiration_days_threshold
        self.expiration_threshold_multiplier = expiration_threshold_multiplier
        
        # Track hedges by position
        self.hedge_history: Dict[str, List[Hedge]] = {}
        
        # Track last hedge price by position
        self.last_hedge_price: Dict[str, float] = {}
        
        # Track hedging mode by position
        self.hedging_modes: Dict[str, HedgingMode] = {}
        
        logger.info(f"GammaScalper initialized with {transaction_cost_bps} bps transaction cost")
    
    def compute_hedging_threshold(
        self,
        position: Position,
        spot_price: float,
        mode: Optional[HedgingMode] = None
    ) -> float:
        """
        Compute optimal hedging threshold based on gamma and transaction costs.
        
        The optimal threshold minimizes: hedging_cost + gamma_slippage
        Threshold = sqrt(2 * tc / (gamma * S))
        
        Requirements: 5.1, 5.5
        
        Args:
            position: Position to hedge
            spot_price: Current spot price
            mode: Hedging mode (optional, uses default if not specified)
        
        Returns:
            float: Hedging threshold as percentage move
        """
        if mode is None:
            mode = self.hedging_modes.get(position.position_id, self.default_mode)
        
        # Get position gamma (per unit)
        gamma = abs(position.quantity)  # Simplified - should use actual gamma from Greeks
        
        if gamma <= 0:
            return float('inf')  # No gamma, no need to hedge
        
        # Transaction cost per hedge
        tc = self.transaction_cost_bps * spot_price / 10000
        
        # Base optimal threshold: sqrt(2 * tc / (gamma * S))
        base_threshold = np.sqrt(2 * tc / (gamma * spot_price))
        
        # Apply mode-specific multiplier
        if mode == HedgingMode.HIGH_FREQUENCY:
            threshold = base_threshold * self.high_freq_threshold_multiplier
        elif mode == HedgingMode.LOW_FREQUENCY:
            threshold = base_threshold * self.low_freq_threshold_multiplier
        elif mode == HedgingMode.CONTINUOUS:
            threshold = base_threshold * 0.1  # Very small threshold for continuous hedging
        else:  # NORMAL or DISCRETE
            threshold = base_threshold
        
        # Adjust for expiration proximity
        days_to_expiry = (position.expiry - datetime.now().date()).days
        if days_to_expiry <= self.expiration_days_threshold:
            threshold *= self.expiration_threshold_multiplier
            logger.debug(
                f"Position {position.position_id} near expiration ({days_to_expiry} days), "
                f"threshold adjusted to {threshold:.4f}"
            )
        
        return threshold
    
    def should_hedge(
        self,
        position: Position,
        current_price: float,
        mode: Optional[HedgingMode] = None
    ) -> bool:
        """
        Determine if delta hedge should be executed.
        
        Requirements: 5.2
        
        Args:
            position: Position to check
            current_price: Current spot price
            mode: Hedging mode (optional)
        
        Returns:
            bool: True if hedge should be executed
        """
        # Get last hedge price
        last_price = self.last_hedge_price.get(position.position_id)
        
        if last_price is None:
            # First hedge - always execute
            return True
        
        # Compute price move percentage
        price_move = abs(current_price - last_price) / last_price
        
        # Get hedging threshold
        threshold = self.compute_hedging_threshold(position, current_price, mode)
        
        should_hedge = price_move > threshold
        
        if should_hedge:
            logger.info(
                f"Hedge trigger for {position.position_id}: "
                f"price move {price_move:.4f} > threshold {threshold:.4f}"
            )
        
        return should_hedge
    
    def generate_hedge_order(
        self,
        position: Position,
        current_delta: float,
        current_price: float,
        target_delta: float = 0.0
    ) -> Order:
        """
        Generate delta-hedging order.
        
        Requirements: 5.2
        
        Args:
            position: Position to hedge
            current_delta: Current delta exposure
            current_price: Current spot price
            target_delta: Target delta (default 0.0 for delta-neutral)
        
        Returns:
            Order: Hedge order to execute
        """
        # Compute hedge quantity to achieve target delta
        # Delta exposure = position.quantity * position_delta
        # To neutralize: hedge_quantity = -(current_delta - target_delta)
        hedge_quantity = -(current_delta - target_delta)
        
        order = Order(
            instrument=position.underlying,
            quantity=hedge_quantity,
            order_type="market",
            reason=f"gamma_scalp_hedge_{position.position_id}",
            timestamp=datetime.now()
        )
        
        logger.info(
            f"Generated hedge order for {position.position_id}: "
            f"{hedge_quantity:.4f} units of {position.underlying}"
        )
        
        return order
    
    def record_hedge(
        self,
        position: Position,
        current_price: float,
        delta_before: float,
        delta_after: float,
        hedge_quantity: float,
        execution_price: float
    ) -> Hedge:
        """
        Record a hedge execution.
        
        Requirements: 5.3
        
        Args:
            position: Position that was hedged
            current_price: Spot price at hedge
            delta_before: Delta before hedge
            delta_after: Delta after hedge
            hedge_quantity: Quantity of underlying traded
            execution_price: Actual execution price
        
        Returns:
            Hedge: Hedge record
        """
        # Compute transaction cost
        transaction_cost = abs(hedge_quantity) * execution_price * self.transaction_cost_bps / 10000
        
        # Compute realized P&L from this hedge
        # P&L = hedge_quantity * (execution_price - last_price)
        last_price = self.last_hedge_price.get(position.position_id, execution_price)
        pnl = hedge_quantity * (execution_price - last_price) - transaction_cost
        
        hedge = Hedge(
            timestamp=datetime.now(),
            position_id=position.position_id,
            underlying=position.underlying,
            price=current_price,
            delta_before=delta_before,
            delta_after=delta_after,
            hedge_quantity=hedge_quantity,
            transaction_cost=transaction_cost,
            pnl=pnl
        )
        
        # Add to history
        if position.position_id not in self.hedge_history:
            self.hedge_history[position.position_id] = []
        self.hedge_history[position.position_id].append(hedge)
        
        # Update last hedge price
        self.last_hedge_price[position.position_id] = current_price
        
        logger.info(
            f"Recorded hedge for {position.position_id}: "
            f"quantity={hedge_quantity:.4f}, pnl={pnl:.2f}, cost={transaction_cost:.2f}"
        )
        
        return hedge
    
    def compute_realized_variance(
        self,
        position_id: str,
        annualization_factor: int = 252
    ) -> float:
        """
        Compute realized variance from hedge history.
        
        Requirements: 5.3
        
        Args:
            position_id: Position ID
            annualization_factor: Days per year for annualization (default 252)
        
        Returns:
            float: Annualized realized variance
        """
        hedges = self.hedge_history.get(position_id, [])
        
        if len(hedges) < 2:
            return 0.0
        
        # Extract price moves from hedges
        returns = []
        for i in range(1, len(hedges)):
            ret = np.log(hedges[i].price / hedges[i-1].price)
            returns.append(ret)
        
        if not returns:
            return 0.0
        
        # Compute variance
        # Use ddof=0 for population variance when we have only 1 return
        # Use ddof=1 for sample variance when we have 2+ returns
        ddof = 0 if len(returns) == 1 else 1
        variance = np.var(returns, ddof=ddof)
        
        # Handle NaN or negative variance (shouldn't happen, but be safe)
        if np.isnan(variance) or variance < 0:
            return 0.0
        
        # Annualize (assuming hedges are roughly evenly spaced)
        # This is a simplification - more sophisticated methods could be used
        annualized_variance = variance * annualization_factor
        
        return annualized_variance
    
    def track_realized_pnl(
        self,
        position: Position,
        current_value: float,
        entry_value: float,
        entry_iv: float
    ) -> RealizedPnL:
        """
        Track P&L from gamma scalping.
        
        Requirements: 5.3, 5.4
        
        Args:
            position: Position being tracked
            current_value: Current option value
            entry_value: Entry option value
            entry_iv: Entry implied volatility
        
        Returns:
            RealizedPnL: Comprehensive P&L breakdown
        """
        hedges = self.hedge_history.get(position.position_id, [])
        
        # Option P&L (mark-to-market)
        option_pnl = current_value - entry_value
        
        # Hedge P&L (realized)
        hedge_pnl = sum(h.pnl for h in hedges)
        
        # Total transaction costs
        total_transaction_costs = sum(h.transaction_cost for h in hedges)
        
        # Total realized P&L
        total_pnl = option_pnl + hedge_pnl
        
        # Compute realized variance
        realized_var = self.compute_realized_variance(position.position_id)
        
        # Implied variance paid
        implied_var = entry_iv ** 2
        
        # Variance P&L (simplified - actual calculation would use vega)
        # variance_pnl = (realized_var - implied_var) * vega * quantity
        # For now, use a simplified approximation
        variance_pnl = (realized_var - implied_var) * abs(position.quantity) * 100
        
        return RealizedPnL(
            total_pnl=total_pnl,
            option_pnl=option_pnl,
            hedge_pnl=hedge_pnl,
            variance_pnl=variance_pnl,
            realized_var=realized_var,
            implied_var=implied_var,
            num_hedges=len(hedges),
            total_transaction_costs=total_transaction_costs
        )
    
    def adapt_hedging_frequency(
        self,
        position: Position,
        performance: RealizedPnL
    ) -> HedgingMode:
        """
        Adjust hedging frequency based on realized vs implied variance.
        
        Requirements: 5.4, 5.6
        
        Args:
            position: Position to adjust
            performance: Current performance metrics
        
        Returns:
            HedgingMode: Recommended hedging mode
        """
        if performance.implied_var <= 0:
            # No implied variance, use default mode
            return self.default_mode
        
        # Compute variance ratio
        var_ratio = performance.realized_var / performance.implied_var
        
        # Determine appropriate mode
        if var_ratio > 1.5:
            # Realized vol much higher than implied - hedge more frequently
            mode = HedgingMode.HIGH_FREQUENCY
            logger.info(
                f"Position {position.position_id}: Increasing hedging frequency "
                f"(realized/implied = {var_ratio:.2f})"
            )
        elif var_ratio > 1.1:
            # Realized vol slightly higher - normal hedging
            mode = HedgingMode.NORMAL
        else:
            # Realized vol lower than implied - reduce hedging
            mode = HedgingMode.LOW_FREQUENCY
            logger.info(
                f"Position {position.position_id}: Reducing hedging frequency "
                f"(realized/implied = {var_ratio:.2f})"
            )
        
        # Update mode for position
        self.hedging_modes[position.position_id] = mode
        
        return mode
    
    def get_hedging_statistics(self, position_id: str) -> Dict[str, float]:
        """
        Get hedging statistics for a position.
        
        Args:
            position_id: Position ID
        
        Returns:
            dict: Hedging statistics
        """
        hedges = self.hedge_history.get(position_id, [])
        
        if not hedges:
            return {
                'num_hedges': 0,
                'total_pnl': 0.0,
                'total_costs': 0.0,
                'avg_hedge_size': 0.0,
                'realized_variance': 0.0
            }
        
        return {
            'num_hedges': len(hedges),
            'total_pnl': sum(h.pnl for h in hedges),
            'total_costs': sum(h.transaction_cost for h in hedges),
            'avg_hedge_size': np.mean([abs(h.hedge_quantity) for h in hedges]),
            'realized_variance': self.compute_realized_variance(position_id)
        }
    
    def reset_position_history(self, position_id: str):
        """
        Reset hedge history for a position (e.g., when position is closed).
        
        Args:
            position_id: Position ID to reset
        """
        if position_id in self.hedge_history:
            del self.hedge_history[position_id]
        if position_id in self.last_hedge_price:
            del self.last_hedge_price[position_id]
        if position_id in self.hedging_modes:
            del self.hedging_modes[position_id]
        
        logger.info(f"Reset hedge history for position {position_id}")
