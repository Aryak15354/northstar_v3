#!/usr/bin/env python3
"""
Dispersion Trading Module for Unified Volatility Engine

Implements systematic exploitation of correlation inefficiencies between
index volatility and constituent stock volatilities.

Key Features:
- Implied correlation computation from index options
- Realized correlation computation from constituent stocks
- Dispersion opportunity detection
- Variance-weighted position sizing
- Delta-hedging and rebalancing
- Correlation risk monitoring
- Expected P&L calculation

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
"""

import logging
import numpy as np
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from src.volatility.greeks_aggregator import Greeks, Position

logger = logging.getLogger(__name__)


class DispersionDirection(Enum):
    """Direction of dispersion trade"""
    LONG_DISPERSION = "long_dispersion"    # Long index vol, short stock vol
    SHORT_DISPERSION = "short_dispersion"  # Short index vol, long stock vol


@dataclass
class DispersionOpportunity:
    """Identified dispersion trading opportunity"""
    direction: DispersionDirection
    spread: float  # Implied correlation - realized correlation
    implied_correlation: float
    realized_correlation: float
    confidence: float  # 0.0 to 1.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def is_significant(self, threshold: float = 0.10) -> bool:
        """Check if spread is significant enough to trade"""
        return abs(self.spread) > threshold


@dataclass
class DispersionTrade:
    """Active dispersion trading position"""
    trade_id: str
    direction: DispersionDirection
    entry_spread: float
    entry_timestamp: datetime
    
    # Positions
    index_position: Position
    stock_positions: List[Position]
    
    # Targets
    target_exit_spread: float
    target_delta: float = 0.0  # Delta-neutral target
    
    # Tracking
    last_rebalance: datetime = field(default_factory=datetime.now)
    cumulative_pnl: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0


@dataclass
class CorrelationData:
    """Correlation matrix and statistics"""
    correlation_matrix: np.ndarray
    average_correlation: float
    timestamp: datetime
    lookback_days: int


@dataclass
class VarianceWeights:
    """Variance-weighted position sizes"""
    weights: Dict[str, float]  # Symbol -> weight
    index_variance: float
    stock_variances: Dict[str, float]
    timestamp: datetime


class DispersionModule:
    """
    Dispersion Trading Module
    
    Systematically exploits correlation inefficiencies between index
    volatility and constituent stock volatilities.
    
    Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
    """
    
    def __init__(
        self,
        constituents: List[str],
        index_symbol: str = "SPY",
        entry_threshold: float = 0.10,
        exit_threshold: float = 0.05,
        rebalance_threshold: float = 0.10,
        neutrality_threshold: float = 0.05
    ):
        """
        Initialize dispersion module.
        
        Args:
            constituents: List of constituent stock symbols
            index_symbol: Index symbol (e.g., "SPY")
            entry_threshold: Minimum spread to enter trade
            exit_threshold: Spread level to exit trade
            rebalance_threshold: Delta threshold for rebalancing
            neutrality_threshold: Delta neutrality tolerance
        """
        self.constituents = constituents
        self.index_symbol = index_symbol
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.rebalance_threshold = rebalance_threshold
        self.neutrality_threshold = neutrality_threshold
        
        # Active trades
        self.active_trades: List[DispersionTrade] = []
        
        # Historical tracking
        self.correlation_history: List[CorrelationData] = []
        self.spread_history: List[Tuple[datetime, float]] = []
        
        logger.info(
            f"Dispersion module initialized: {len(constituents)} constituents, "
            f"index={index_symbol}, entry_threshold={entry_threshold:.2%}"
        )
    
    # ========================================================================
    # CORRELATION ANALYSIS (Requirements 4.1, 4.2, 4.3)
    # ========================================================================
    
    def compute_implied_correlation(
        self,
        index_variance: float,
        stock_variances: Dict[str, float],
        index_weights: Dict[str, float]
    ) -> float:
        """
        Compute implied correlation from index options and stock options.
        
        Formula:
        implied_corr = (index_var - weighted_avg_stock_var) / weighted_avg_stock_var
        
        Requirements: 4.1
        
        Args:
            index_variance: Implied variance from index options
            stock_variances: Implied variances from stock options
            index_weights: Constituent weights in index
            
        Returns:
            Implied correlation
        """
        # Compute weighted average of stock variances
        # Formula: index_var = Σ(w_i^2 * σ_i^2) + Σ Σ(w_i * w_j * σ_i * σ_j * ρ_ij)
        # For equal correlation ρ: index_var = Σ(w_i^2 * σ_i^2) + ρ * Σ Σ(w_i * w_j * σ_i * σ_j) for i≠j
        
        # Compute Σ(w_i^2 * σ_i^2)
        sum_weighted_var = 0.0
        for symbol, weight in index_weights.items():
            if symbol in stock_variances:
                sum_weighted_var += (weight ** 2) * stock_variances[symbol]
        
        # Compute Σ Σ(w_i * w_j * σ_i * σ_j) for i≠j
        sum_weighted_covol = 0.0
        symbols = [s for s in index_weights.keys() if s in stock_variances]
        for i, symbol_i in enumerate(symbols):
            for j, symbol_j in enumerate(symbols):
                if i != j:
                    weight_i = index_weights[symbol_i]
                    weight_j = index_weights[symbol_j]
                    vol_i = np.sqrt(stock_variances[symbol_i])
                    vol_j = np.sqrt(stock_variances[symbol_j])
                    sum_weighted_covol += weight_i * weight_j * vol_i * vol_j
        
        if sum_weighted_covol == 0:
            logger.warning("Weighted covariance term is zero")
            # If no cross terms, correlation is undefined
            if sum_weighted_var == 0:
                return 0.0
            # Return clamped value
            implied_corr = (index_variance - sum_weighted_var) / sum_weighted_var
            return np.clip(implied_corr, -1.0, 1.0)
        
        # Solve for implied correlation
        # index_var = sum_weighted_var + ρ * sum_weighted_covol
        # ρ = (index_var - sum_weighted_var) / sum_weighted_covol
        
        implied_corr = (index_variance - sum_weighted_var) / sum_weighted_covol
        
        # Clamp to valid correlation range [-1, 1]
        implied_corr = np.clip(implied_corr, -1.0, 1.0)
        
        logger.debug(
            f"Implied correlation: {implied_corr:.4f} "
            f"(index_var={index_variance:.6f}, sum_weighted_var={sum_weighted_var:.6f})"
        )
        
        return implied_corr
    
    def compute_realized_correlation(
        self,
        returns: np.ndarray,
        lookback_days: int = 60
    ) -> CorrelationData:
        """
        Compute realized correlation from historical returns.
        
        Requirements: 4.1
        
        Args:
            returns: Returns matrix (n_days x n_stocks)
            lookback_days: Number of days for correlation calculation
            
        Returns:
            CorrelationData with correlation matrix and average
        """
        # Use last lookback_days of returns
        recent_returns = returns[-lookback_days:] if len(returns) > lookback_days else returns
        
        if len(recent_returns) < 10:
            logger.warning(f"Insufficient data for correlation: {len(recent_returns)} days")
            return CorrelationData(
                correlation_matrix=np.eye(len(self.constituents)),
                average_correlation=0.0,
                timestamp=datetime.now(),
                lookback_days=len(recent_returns)
            )
        
        # Compute correlation matrix
        corr_matrix = np.corrcoef(recent_returns.T)
        
        # Handle single stock case (corrcoef returns scalar)
        if corr_matrix.ndim == 0:
            corr_matrix = np.array([[1.0]])
        elif corr_matrix.ndim == 1:
            corr_matrix = corr_matrix.reshape(1, 1)
        
        # Compute average correlation (excluding diagonal)
        n = corr_matrix.shape[0]
        if n > 1:
            # Sum all correlations except diagonal, divide by n*(n-1)
            avg_corr = (corr_matrix.sum() - n) / (n * (n - 1))
        else:
            avg_corr = 0.0
        
        correlation_data = CorrelationData(
            correlation_matrix=corr_matrix,
            average_correlation=avg_corr,
            timestamp=datetime.now(),
            lookback_days=len(recent_returns)
        )
        
        # Store in history
        self.correlation_history.append(correlation_data)
        
        logger.debug(
            f"Realized correlation: {avg_corr:.4f} "
            f"(lookback={len(recent_returns)} days)"
        )
        
        return correlation_data
    
    def analyze_dispersion_opportunity(
        self,
        index_variance: float,
        stock_variances: Dict[str, float],
        index_weights: Dict[str, float],
        realized_correlation: float
    ) -> Optional[DispersionOpportunity]:
        """
        Identify dispersion trading opportunities.
        
        Requirements: 4.2, 4.3
        
        Args:
            index_variance: Implied variance from index options
            stock_variances: Implied variances from stock options
            index_weights: Constituent weights in index
            realized_correlation: Realized correlation from historical data
            
        Returns:
            DispersionOpportunity if significant spread exists, None otherwise
        """
        # Compute implied correlation
        implied_corr = self.compute_implied_correlation(
            index_variance,
            stock_variances,
            index_weights
        )
        
        # Compute spread
        spread = implied_corr - realized_correlation
        
        # Store in history
        self.spread_history.append((datetime.now(), spread))
        
        # Determine direction and confidence
        if spread > self.entry_threshold:
            # Implied > Realized: Short dispersion (short index vol, long stock vol)
            direction = DispersionDirection.SHORT_DISPERSION
            confidence = min(abs(spread) / (2 * self.entry_threshold), 1.0)
            
            opportunity = DispersionOpportunity(
                direction=direction,
                spread=spread,
                implied_correlation=implied_corr,
                realized_correlation=realized_correlation,
                confidence=confidence
            )
            
            logger.info(
                f"Dispersion opportunity: SHORT (implied={implied_corr:.4f}, "
                f"realized={realized_correlation:.4f}, spread={spread:.4f})"
            )
            
            return opportunity
        
        elif spread < -self.entry_threshold:
            # Implied < Realized: Long dispersion (long index vol, short stock vol)
            direction = DispersionDirection.LONG_DISPERSION
            confidence = min(abs(spread) / (2 * self.entry_threshold), 1.0)
            
            opportunity = DispersionOpportunity(
                direction=direction,
                spread=spread,
                implied_correlation=implied_corr,
                realized_correlation=realized_correlation,
                confidence=confidence
            )
            
            logger.info(
                f"Dispersion opportunity: LONG (implied={implied_corr:.4f}, "
                f"realized={realized_correlation:.4f}, spread={spread:.4f})"
            )
            
            return opportunity
        
        # No significant opportunity
        logger.debug(f"No dispersion opportunity: spread={spread:.4f}")
        return None
    
    # ========================================================================
    # VARIANCE WEIGHTING (Requirement 4.4)
    # ========================================================================
    
    def compute_variance_weights(
        self,
        stock_volatilities: Dict[str, float],
        index_weights: Dict[str, float],
        correlation_matrix: np.ndarray
    ) -> VarianceWeights:
        """
        Compute variance-weighted position sizes.
        
        Each stock's position size is proportional to its contribution
        to index variance.
        
        Requirements: 4.4
        
        Args:
            stock_volatilities: Volatility for each stock
            index_weights: Index weights for each stock
            correlation_matrix: Correlation matrix between stocks
            
        Returns:
            VarianceWeights with position sizes
        """
        # Compute variance contributions
        variance_contributions = {}
        
        for i, symbol_i in enumerate(self.constituents):
            if symbol_i not in stock_volatilities or symbol_i not in index_weights:
                continue
            
            weight_i = index_weights[symbol_i]
            vol_i = stock_volatilities[symbol_i]
            
            # Variance contribution = w_i^2 * σ_i^2 + 2 * w_i * Σ(w_j * σ_i * σ_j * ρ_ij)
            var_contrib = (weight_i * vol_i) ** 2
            
            # Add covariance terms
            for j, symbol_j in enumerate(self.constituents):
                if i != j and symbol_j in stock_volatilities and symbol_j in index_weights:
                    weight_j = index_weights[symbol_j]
                    vol_j = stock_volatilities[symbol_j]
                    corr_ij = correlation_matrix[i, j] if i < len(correlation_matrix) and j < len(correlation_matrix[0]) else 0.0
                    
                    var_contrib += weight_i * weight_j * vol_i * vol_j * corr_ij
            
            variance_contributions[symbol_i] = var_contrib
        
        # Normalize to get weights
        total_var = sum(variance_contributions.values())
        
        if total_var == 0:
            logger.warning("Total variance contribution is zero")
            # Equal weights as fallback
            weights = {s: 1.0 / len(variance_contributions) for s in variance_contributions}
        else:
            weights = {s: v / total_var for s, v in variance_contributions.items()}
        
        # Compute index variance
        index_variance = total_var
        
        # Store stock variances
        stock_variances = {s: (stock_volatilities[s] ** 2) for s in stock_volatilities}
        
        logger.debug(
            f"Variance weights computed: {len(weights)} stocks, "
            f"index_var={index_variance:.6f}"
        )
        
        return VarianceWeights(
            weights=weights,
            index_variance=index_variance,
            stock_variances=stock_variances,
            timestamp=datetime.now()
        )
    
    # ========================================================================
    # POSITION MANAGEMENT (Requirements 4.5, 4.6, 4.7)
    # ========================================================================
    
    def compute_dispersion_delta(
        self,
        trade: DispersionTrade,
        current_spot_prices: Dict[str, float]
    ) -> float:
        """
        Compute current portfolio delta for dispersion position.
        
        Requirements: 4.5, 4.6
        
        Args:
            trade: Active dispersion trade
            current_spot_prices: Current spot prices for all symbols
            
        Returns:
            Portfolio delta
        """
        total_delta = 0.0
        
        # Index position delta
        # Note: Position.quantity already includes sign (positive for long, negative for short)
        index_delta = trade.index_position.quantity  # Simplified: assume delta ≈ quantity for ATM options
        total_delta += index_delta
        
        # Stock positions delta
        for stock_pos in trade.stock_positions:
            stock_delta = stock_pos.quantity  # Simplified
            total_delta += stock_delta
        
        logger.debug(f"Dispersion delta: {total_delta:.4f}")
        
        return total_delta
    
    def generate_rebalance_orders(
        self,
        trade: DispersionTrade,
        current_delta: float,
        current_spot_prices: Dict[str, float]
    ) -> List[Dict[str, any]]:
        """
        Generate delta-hedging orders for dispersion position.
        
        Requirements: 4.6
        
        Args:
            trade: Active dispersion trade
            current_delta: Current portfolio delta
            current_spot_prices: Current spot prices
            
        Returns:
            List of hedge orders
        """
        orders = []
        
        # Check if rebalancing is needed
        if abs(current_delta - trade.target_delta) < self.rebalance_threshold:
            logger.debug(f"No rebalancing needed: delta={current_delta:.4f}")
            return orders
        
        # Compute required hedge
        delta_imbalance = current_delta - trade.target_delta
        
        # Hedge using index futures/ETF
        index_price = current_spot_prices.get(self.index_symbol, 100.0)
        hedge_quantity = -delta_imbalance  # Opposite sign to neutralize
        
        orders.append({
            'symbol': self.index_symbol,
            'quantity': hedge_quantity,
            'order_type': 'market',
            'reason': 'dispersion_delta_hedge',
            'current_delta': current_delta,
            'target_delta': trade.target_delta
        })
        
        logger.info(
            f"Rebalance order generated: {self.index_symbol} qty={hedge_quantity:.2f} "
            f"(delta={current_delta:.4f} -> {trade.target_delta:.4f})"
        )
        
        return orders
    
    def monitor_correlation_risk(
        self,
        trade: DispersionTrade,
        current_implied_corr: float,
        current_realized_corr: float
    ) -> Dict[str, any]:
        """
        Monitor correlation risk for active dispersion position.
        
        Requirements: 4.5
        
        Args:
            trade: Active dispersion trade
            current_implied_corr: Current implied correlation
            current_realized_corr: Current realized correlation
            
        Returns:
            Risk metrics dictionary
        """
        current_spread = current_implied_corr - current_realized_corr
        spread_change = current_spread - trade.entry_spread
        
        # Determine if position is profitable
        if trade.direction == DispersionDirection.SHORT_DISPERSION:
            # Profitable if spread narrows (implied correlation decreases)
            is_profitable = spread_change < 0
        else:  # LONG_DISPERSION
            # Profitable if spread widens (implied correlation increases)
            is_profitable = spread_change > 0
        
        # Check exit conditions
        should_exit = abs(current_spread) < self.exit_threshold
        
        risk_metrics = {
            'trade_id': trade.trade_id,
            'direction': trade.direction.value,
            'entry_spread': trade.entry_spread,
            'current_spread': current_spread,
            'spread_change': spread_change,
            'is_profitable': is_profitable,
            'should_exit': should_exit,
            'days_held': (datetime.now() - trade.entry_timestamp).days,
            'implied_correlation': current_implied_corr,
            'realized_correlation': current_realized_corr
        }
        
        logger.debug(
            f"Correlation risk: spread={current_spread:.4f} "
            f"(entry={trade.entry_spread:.4f}, change={spread_change:.4f})"
        )
        
        return risk_metrics
    
    def compute_expected_pnl(
        self,
        trade: DispersionTrade,
        target_spread: float,
        vega_per_point: float = 1000.0
    ) -> float:
        """
        Compute expected P&L from dispersion trade.
        
        Assumes correlation mean reversion to target spread.
        
        Requirements: 4.7
        
        Args:
            trade: Active dispersion trade
            target_spread: Expected target spread (e.g., historical mean)
            vega_per_point: Vega per correlation point
            
        Returns:
            Expected P&L
        """
        # Spread change from entry to target
        spread_change = target_spread - trade.entry_spread
        
        # P&L depends on direction
        if trade.direction == DispersionDirection.SHORT_DISPERSION:
            # Profitable if spread narrows (negative spread_change)
            expected_pnl = -spread_change * vega_per_point
        else:  # LONG_DISPERSION
            # Profitable if spread widens (positive spread_change)
            expected_pnl = spread_change * vega_per_point
        
        logger.debug(
            f"Expected P&L: ${expected_pnl:.2f} "
            f"(spread_change={spread_change:.4f}, direction={trade.direction.value})"
        )
        
        return expected_pnl
    
    def is_delta_neutral(
        self,
        trade: DispersionTrade,
        current_spot_prices: Dict[str, float]
    ) -> bool:
        """
        Check if dispersion position is delta-neutral.
        
        Requirements: 4.6 (Property 9)
        
        Args:
            trade: Active dispersion trade
            current_spot_prices: Current spot prices
            
        Returns:
            True if position is delta-neutral within threshold
        """
        current_delta = self.compute_dispersion_delta(trade, current_spot_prices)
        is_neutral = abs(current_delta) <= self.neutrality_threshold
        
        logger.debug(
            f"Delta neutrality check: delta={current_delta:.4f}, "
            f"threshold={self.neutrality_threshold:.4f}, neutral={is_neutral}"
        )
        
        return is_neutral


def main():
    """Test dispersion module"""
    print("📊 Testing Dispersion Trading Module")
    print("=" * 60)
    
    # Create test module
    constituents = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
    module = DispersionModule(
        constituents=constituents,
        index_symbol="SPY",
        entry_threshold=0.10,
        exit_threshold=0.05
    )
    
    # Test correlation computation
    print("\n1. Testing Implied Correlation Computation")
    index_variance = 0.04  # 20% vol squared
    stock_variances = {
        "AAPL": 0.0625,   # 25% vol
        "MSFT": 0.0576,   # 24% vol
        "GOOGL": 0.0729,  # 27% vol
        "AMZN": 0.0900,   # 30% vol
        "META": 0.0841    # 29% vol
    }
    index_weights = {
        "AAPL": 0.25,
        "MSFT": 0.25,
        "GOOGL": 0.20,
        "AMZN": 0.20,
        "META": 0.10
    }
    
    implied_corr = module.compute_implied_correlation(
        index_variance,
        stock_variances,
        index_weights
    )
    print(f"✅ Implied correlation: {implied_corr:.4f}")
    
    # Test realized correlation
    print("\n2. Testing Realized Correlation Computation")
    np.random.seed(42)
    returns = np.random.randn(60, 5) * 0.02  # 60 days, 5 stocks
    corr_data = module.compute_realized_correlation(returns, lookback_days=60)
    print(f"✅ Realized correlation: {corr_data.average_correlation:.4f}")
    
    # Test opportunity detection
    print("\n3. Testing Dispersion Opportunity Detection")
    opportunity = module.analyze_dispersion_opportunity(
        index_variance,
        stock_variances,
        index_weights,
        realized_correlation=0.50
    )
    
    if opportunity:
        print(f"✅ Opportunity found:")
        print(f"   Direction: {opportunity.direction.value}")
        print(f"   Spread: {opportunity.spread:.4f}")
        print(f"   Confidence: {opportunity.confidence:.2%}")
    else:
        print("❌ No opportunity found")
    
    # Test variance weighting
    print("\n4. Testing Variance Weighting")
    stock_vols = {s: np.sqrt(v) for s, v in stock_variances.items()}
    corr_matrix = np.eye(5) * 0.4 + 0.6  # Simple correlation matrix
    
    var_weights = module.compute_variance_weights(
        stock_vols,
        index_weights,
        corr_matrix
    )
    print(f"✅ Variance weights computed:")
    for symbol, weight in var_weights.weights.items():
        print(f"   {symbol}: {weight:.4f}")
    
    print("\n✅ Dispersion module tests complete!")


if __name__ == "__main__":
    main()
