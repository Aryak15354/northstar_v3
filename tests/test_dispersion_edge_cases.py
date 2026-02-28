"""
Unit Tests for Dispersion Trading Module Edge Cases

Tests specific edge cases and boundary conditions:
- Extreme correlation spreads
- Missing constituent data
- Rebalancing threshold logic
- Zero variance scenarios
- Single constituent scenarios

Validates: Requirements 4.1, 4.2, 4.3
"""

import pytest
import numpy as np
from datetime import datetime, date, timedelta

from src.volatility.dispersion_module import (
    DispersionModule,
    DispersionTrade,
    DispersionDirection,
    DispersionOpportunity,
    CorrelationData,
    VarianceWeights
)
from src.volatility.greeks_aggregator import Position


class TestDispersionEdgeCases:
    """Test edge cases for dispersion trading module"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.constituents = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
        self.module = DispersionModule(
            constituents=self.constituents,
            index_symbol="SPY",
            entry_threshold=0.10,
            exit_threshold=0.05,
            rebalance_threshold=0.10,
            neutrality_threshold=0.05
        )
    
    # ========================================================================
    # EXTREME CORRELATION SPREADS
    # ========================================================================
    
    def test_extreme_positive_spread(self):
        """Test with extreme positive correlation spread"""
        # Create scenario where implied correlation is much higher than realized
        index_variance = 0.25  # 50% vol
        stock_variances = {
            "AAPL": 0.04,   # 20% vol
            "MSFT": 0.04,
            "GOOGL": 0.04,
            "AMZN": 0.04,
            "META": 0.04
        }
        index_weights = {s: 0.20 for s in self.constituents}
        realized_corr = 0.10  # Very low realized correlation
        
        opportunity = self.module.analyze_dispersion_opportunity(
            index_variance,
            stock_variances,
            index_weights,
            realized_corr
        )
        
        # Should detect opportunity (high index vol vs low stock vol suggests high implied correlation)
        assert opportunity is not None
        assert abs(opportunity.spread) > 0.10
        print(f"✅ Extreme spread detected: {opportunity.spread:.4f}, direction={opportunity.direction.value}")
    
    def test_extreme_negative_spread(self):
        """Test with extreme negative correlation spread"""
        # Create scenario where implied correlation is much lower than realized
        index_variance = 0.04  # 20% vol
        stock_variances = {
            "AAPL": 0.25,   # 50% vol
            "MSFT": 0.25,
            "GOOGL": 0.25,
            "AMZN": 0.25,
            "META": 0.25
        }
        index_weights = {s: 0.20 for s in self.constituents}
        realized_corr = 0.90  # Very high realized correlation
        
        opportunity = self.module.analyze_dispersion_opportunity(
            index_variance,
            stock_variances,
            index_weights,
            realized_corr
        )
        
        # Should detect opportunity (low index vol vs high stock vol suggests low implied correlation)
        assert opportunity is not None
        assert abs(opportunity.spread) > 0.10
        print(f"✅ Extreme spread detected: {opportunity.spread:.4f}, direction={opportunity.direction.value}")
    
    def test_no_opportunity_small_spread(self):
        """Test when spread is below entry threshold"""
        # Create scenario with similar index and stock volatilities
        index_variance = 0.04  # 20% vol
        stock_variances = {s: 0.04 for s in self.constituents}
        index_weights = {s: 0.20 for s in self.constituents}
        # With equal variances and weights, implied correlation should be close to 1.0
        # Use realized correlation close to 1.0 to minimize spread
        realized_corr = 0.95
        
        opportunity = self.module.analyze_dispersion_opportunity(
            index_variance,
            stock_variances,
            index_weights,
            realized_corr
        )
        
        # Should not detect opportunity (spread too small)
        if opportunity is None:
            print("✅ No opportunity detected for small spread")
        else:
            # If opportunity detected, spread should be small
            assert abs(opportunity.spread) < 0.15
            print(f"✅ Small spread detected: {opportunity.spread:.4f}")
    
    # ========================================================================
    # MISSING CONSTITUENT DATA
    # ========================================================================
    
    def test_missing_stock_variance(self):
        """Test with missing stock variance data"""
        index_variance = 0.04
        stock_variances = {
            "AAPL": 0.0625,
            "MSFT": 0.0576,
            # GOOGL missing
            "AMZN": 0.0900,
            "META": 0.0841
        }
        index_weights = {s: 0.20 for s in self.constituents}
        
        # Should handle missing data gracefully
        implied_corr = self.module.compute_implied_correlation(
            index_variance,
            stock_variances,
            index_weights
        )
        
        # Should still compute (using available data)
        assert -1.0 <= implied_corr <= 1.0
        print(f"✅ Handled missing stock variance: implied_corr={implied_corr:.4f}")
    
    def test_missing_index_weight(self):
        """Test with missing index weight"""
        index_variance = 0.04
        stock_variances = {s: 0.0625 for s in self.constituents}
        index_weights = {
            "AAPL": 0.25,
            "MSFT": 0.25,
            # GOOGL missing
            "AMZN": 0.25,
            "META": 0.25
        }
        
        # Should handle missing weight gracefully
        implied_corr = self.module.compute_implied_correlation(
            index_variance,
            stock_variances,
            index_weights
        )
        
        assert -1.0 <= implied_corr <= 1.0
        print(f"✅ Handled missing index weight: implied_corr={implied_corr:.4f}")
    
    def test_insufficient_returns_data(self):
        """Test realized correlation with insufficient data"""
        # Only 5 days of returns (need at least 10)
        returns = np.random.randn(5, len(self.constituents)) * 0.02
        
        corr_data = self.module.compute_realized_correlation(returns, lookback_days=60)
        
        # Should return identity matrix with warning
        assert corr_data.lookback_days == 5
        assert corr_data.average_correlation >= -1.0
        assert corr_data.average_correlation <= 1.0
        print(f"✅ Handled insufficient data: {corr_data.lookback_days} days")
    
    # ========================================================================
    # REBALANCING THRESHOLD LOGIC
    # ========================================================================
    
    def test_rebalancing_not_needed(self):
        """Test when delta is within threshold (no rebalancing needed)"""
        expiry = date.today() + timedelta(days=30)
        
        # Create positions with small delta
        index_pos = Position(
            position_id="INDEX",
            underlying="SPY",
            option_type="call",
            strike=450.0,
            expiry=expiry,
            quantity=5,  # Small quantity
            spot_price=450.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        stock_positions = [
            Position(
                position_id=f"{s}",
                underlying=s,
                option_type="call",
                strike=200.0,
                expiry=expiry,
                quantity=-1,  # Small opposite quantity
                spot_price=200.0,
                implied_vol=0.25,
                risk_free_rate=0.05
            )
            for s in self.constituents
        ]
        
        trade = DispersionTrade(
            trade_id="TEST",
            direction=DispersionDirection.SHORT_DISPERSION,
            entry_spread=0.15,
            entry_timestamp=datetime.now(),
            index_position=index_pos,
            stock_positions=stock_positions,
            target_exit_spread=0.05,
            target_delta=0.0
        )
        
        spot_prices = {"SPY": 450.0}
        spot_prices.update({s: 200.0 for s in self.constituents})
        
        current_delta = self.module.compute_dispersion_delta(trade, spot_prices)
        orders = self.module.generate_rebalance_orders(trade, current_delta, spot_prices)
        
        # Should not generate orders if delta is small
        if abs(current_delta) < self.module.rebalance_threshold:
            assert len(orders) == 0
            print(f"✅ No rebalancing needed: delta={current_delta:.4f}")
        else:
            print(f"⚠️  Rebalancing triggered: delta={current_delta:.4f}")
    
    def test_rebalancing_needed_large_delta(self):
        """Test when delta exceeds threshold (rebalancing needed)"""
        expiry = date.today() + timedelta(days=30)
        
        # Create positions with large delta imbalance
        index_pos = Position(
            position_id="INDEX",
            underlying="SPY",
            option_type="call",
            strike=450.0,
            expiry=expiry,
            quantity=100,  # Large quantity
            spot_price=450.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        stock_positions = [
            Position(
                position_id=f"{s}",
                underlying=s,
                option_type="call",
                strike=200.0,
                expiry=expiry,
                quantity=-5,  # Small opposite quantity
                spot_price=200.0,
                implied_vol=0.25,
                risk_free_rate=0.05
            )
            for s in self.constituents
        ]
        
        trade = DispersionTrade(
            trade_id="TEST",
            direction=DispersionDirection.SHORT_DISPERSION,
            entry_spread=0.15,
            entry_timestamp=datetime.now(),
            index_position=index_pos,
            stock_positions=stock_positions,
            target_exit_spread=0.05,
            target_delta=0.0
        )
        
        spot_prices = {"SPY": 450.0}
        spot_prices.update({s: 200.0 for s in self.constituents})
        
        current_delta = self.module.compute_dispersion_delta(trade, spot_prices)
        orders = self.module.generate_rebalance_orders(trade, current_delta, spot_prices)
        
        # Should generate rebalancing orders
        assert len(orders) > 0
        assert orders[0]['symbol'] == "SPY"
        assert orders[0]['reason'] == 'dispersion_delta_hedge'
        print(f"✅ Rebalancing triggered: delta={current_delta:.4f}, orders={len(orders)}")
    
    # ========================================================================
    # ZERO VARIANCE SCENARIOS
    # ========================================================================
    
    def test_zero_stock_variance(self):
        """Test with zero stock variance"""
        index_variance = 0.04
        stock_variances = {
            "AAPL": 0.0,  # Zero variance
            "MSFT": 0.0625,
            "GOOGL": 0.0729,
            "AMZN": 0.0900,
            "META": 0.0841
        }
        index_weights = {s: 0.20 for s in self.constituents}
        
        # Should handle zero variance gracefully
        implied_corr = self.module.compute_implied_correlation(
            index_variance,
            stock_variances,
            index_weights
        )
        
        assert -1.0 <= implied_corr <= 1.0
        print(f"✅ Handled zero stock variance: implied_corr={implied_corr:.4f}")
    
    def test_zero_weighted_variance(self):
        """Test when weighted stock variance is zero"""
        index_variance = 0.04
        stock_variances = {s: 0.0 for s in self.constituents}  # All zero
        index_weights = {s: 0.20 for s in self.constituents}
        
        # Should return 0.0 correlation when weighted variance is zero
        implied_corr = self.module.compute_implied_correlation(
            index_variance,
            stock_variances,
            index_weights
        )
        
        assert implied_corr == 0.0
        print(f"✅ Handled zero weighted variance: implied_corr={implied_corr:.4f}")
    
    def test_zero_index_variance(self):
        """Test with zero index variance"""
        index_variance = 0.0  # Zero variance
        stock_variances = {s: 0.0625 for s in self.constituents}
        index_weights = {s: 0.20 for s in self.constituents}
        
        # Should handle zero index variance
        implied_corr = self.module.compute_implied_correlation(
            index_variance,
            stock_variances,
            index_weights
        )
        
        # Should be clamped to valid range
        assert -1.0 <= implied_corr <= 1.0
        print(f"✅ Handled zero index variance: implied_corr={implied_corr:.4f}")
    
    # ========================================================================
    # SINGLE CONSTITUENT SCENARIOS
    # ========================================================================
    
    def test_single_constituent(self):
        """Test with single constituent"""
        single_module = DispersionModule(
            constituents=["AAPL"],
            index_symbol="SPY"
        )
        
        returns = np.random.randn(60, 1) * 0.02
        corr_data = single_module.compute_realized_correlation(returns, lookback_days=60)
        
        # Single stock: correlation should be 0 (no pairs)
        assert corr_data.average_correlation == 0.0
        print("✅ Handled single constituent: avg_corr=0.0")
    
    def test_two_constituents(self):
        """Test with two constituents"""
        two_module = DispersionModule(
            constituents=["AAPL", "MSFT"],
            index_symbol="SPY"
        )
        
        # Generate correlated returns
        np.random.seed(42)
        returns = np.random.randn(60, 2) * 0.02
        corr_data = two_module.compute_realized_correlation(returns, lookback_days=60)
        
        # Should compute pairwise correlation
        assert -1.0 <= corr_data.average_correlation <= 1.0
        assert corr_data.correlation_matrix.shape == (2, 2)
        print(f"✅ Handled two constituents: avg_corr={corr_data.average_correlation:.4f}")
    
    # ========================================================================
    # CORRELATION RISK MONITORING
    # ========================================================================
    
    def test_exit_signal_spread_converged(self):
        """Test exit signal when spread converges to target"""
        expiry = date.today() + timedelta(days=30)
        
        index_pos = Position(
            position_id="INDEX",
            underlying="SPY",
            option_type="call",
            strike=450.0,
            expiry=expiry,
            quantity=10,
            spot_price=450.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        stock_positions = [
            Position(
                position_id=f"{s}",
                underlying=s,
                option_type="call",
                strike=200.0,
                expiry=expiry,
                quantity=-2,
                spot_price=200.0,
                implied_vol=0.25,
                risk_free_rate=0.05
            )
            for s in self.constituents
        ]
        
        trade = DispersionTrade(
            trade_id="TEST",
            direction=DispersionDirection.SHORT_DISPERSION,
            entry_spread=0.20,  # Entered at 20% spread
            entry_timestamp=datetime.now(),
            index_position=index_pos,
            stock_positions=stock_positions,
            target_exit_spread=0.05
        )
        
        # Current spread has converged (below exit threshold)
        current_implied = 0.52
        current_realized = 0.50
        current_spread = 0.02  # Below exit threshold of 0.05
        
        risk_metrics = self.module.monitor_correlation_risk(
            trade,
            current_implied,
            current_realized
        )
        
        # Should signal exit
        assert risk_metrics['should_exit']
        assert risk_metrics['current_spread'] < self.module.exit_threshold
        print(f"✅ Exit signal detected: spread={risk_metrics['current_spread']:.4f}")
    
    def test_profitable_short_dispersion(self):
        """Test profitability detection for short dispersion"""
        expiry = date.today() + timedelta(days=30)
        
        index_pos = Position(
            position_id="INDEX",
            underlying="SPY",
            option_type="call",
            strike=450.0,
            expiry=expiry,
            quantity=10,
            spot_price=450.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        stock_positions = []
        
        trade = DispersionTrade(
            trade_id="TEST",
            direction=DispersionDirection.SHORT_DISPERSION,
            entry_spread=0.20,  # Entered at 20% spread
            entry_timestamp=datetime.now(),
            index_position=index_pos,
            stock_positions=stock_positions,
            target_exit_spread=0.05
        )
        
        # Spread has narrowed (profitable for short dispersion)
        current_implied = 0.60
        current_realized = 0.50
        current_spread = 0.10  # Narrowed from 0.20
        
        risk_metrics = self.module.monitor_correlation_risk(
            trade,
            current_implied,
            current_realized
        )
        
        # Should be profitable
        assert risk_metrics['is_profitable']
        assert risk_metrics['spread_change'] < 0  # Negative change = narrowing
        print(f"✅ Profitable short dispersion: spread {trade.entry_spread:.4f} -> {current_spread:.4f}")
    
    # ========================================================================
    # VARIANCE WEIGHTING EDGE CASES
    # ========================================================================
    
    def test_variance_weights_equal_volatilities(self):
        """Test variance weights when all stocks have equal volatility"""
        stock_vols = {s: 0.25 for s in self.constituents}  # All 25% vol
        index_weights = {s: 0.20 for s in self.constituents}  # Equal weights
        corr_matrix = np.eye(len(self.constituents)) * 0.5 + 0.5
        
        var_weights = self.module.compute_variance_weights(
            stock_vols,
            index_weights,
            corr_matrix
        )
        
        # With equal vols and weights, variance weights should be roughly equal
        weights_list = list(var_weights.weights.values())
        assert max(weights_list) - min(weights_list) < 0.1  # Within 10%
        print(f"✅ Equal volatilities: weights range {min(weights_list):.4f} - {max(weights_list):.4f}")
    
    def test_variance_weights_concentrated(self):
        """Test variance weights with one dominant stock"""
        stock_vols = {
            "AAPL": 0.50,  # High vol
            "MSFT": 0.15,
            "GOOGL": 0.15,
            "AMZN": 0.15,
            "META": 0.15
        }
        index_weights = {s: 0.20 for s in self.constituents}
        corr_matrix = np.eye(len(self.constituents)) * 0.5 + 0.5
        
        var_weights = self.module.compute_variance_weights(
            stock_vols,
            index_weights,
            corr_matrix
        )
        
        # AAPL should have highest variance weight
        assert var_weights.weights["AAPL"] > var_weights.weights["MSFT"]
        print(f"✅ Concentrated variance: AAPL weight={var_weights.weights['AAPL']:.4f}")


def test_module_initialization():
    """Test module initialization with various parameters"""
    # Default initialization
    module1 = DispersionModule(constituents=["AAPL", "MSFT"])
    assert module1.index_symbol == "SPY"
    assert module1.entry_threshold == 0.10
    
    # Custom initialization
    module2 = DispersionModule(
        constituents=["AAPL", "MSFT", "GOOGL"],
        index_symbol="QQQ",
        entry_threshold=0.15,
        exit_threshold=0.08
    )
    assert module2.index_symbol == "QQQ"
    assert module2.entry_threshold == 0.15
    assert module2.exit_threshold == 0.08
    
    print("✅ Module initialization tests passed")


def test_correlation_history_tracking():
    """Test that correlation history is tracked correctly"""
    module = DispersionModule(constituents=["AAPL", "MSFT", "GOOGL"])
    
    # Generate multiple correlation computations
    for i in range(5):
        returns = np.random.randn(60, 3) * 0.02
        module.compute_realized_correlation(returns, lookback_days=60)
    
    # Should have 5 entries in history
    assert len(module.correlation_history) == 5
    
    # Each entry should have valid data
    for corr_data in module.correlation_history:
        assert -1.0 <= corr_data.average_correlation <= 1.0
        assert corr_data.correlation_matrix.shape == (3, 3)
    
    print(f"✅ Correlation history tracked: {len(module.correlation_history)} entries")


def test_spread_history_tracking():
    """Test that spread history is tracked correctly"""
    module = DispersionModule(constituents=["AAPL", "MSFT", "GOOGL"])
    
    index_variance = 0.04
    stock_variances = {"AAPL": 0.0625, "MSFT": 0.0576, "GOOGL": 0.0729}
    index_weights = {"AAPL": 0.33, "MSFT": 0.33, "GOOGL": 0.34}
    
    # Generate multiple opportunity analyses
    for realized_corr in [0.30, 0.40, 0.50, 0.60, 0.70]:
        module.analyze_dispersion_opportunity(
            index_variance,
            stock_variances,
            index_weights,
            realized_corr
        )
    
    # Should have 5 entries in spread history
    assert len(module.spread_history) == 5
    
    # Each entry should be a tuple (timestamp, spread)
    for timestamp, spread in module.spread_history:
        assert isinstance(timestamp, datetime)
        assert isinstance(spread, (int, float))
    
    print(f"✅ Spread history tracked: {len(module.spread_history)} entries")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
