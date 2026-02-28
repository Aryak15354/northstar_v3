"""
Unit Tests for Gamma Scalping Edge Cases

Tests specific edge cases and boundary conditions:
- Hedging near expiration
- Extreme volatility scenarios
- Transaction cost impact

Validates: Requirements 5.5, 5.7
"""

import pytest
import numpy as np
from datetime import datetime, date, timedelta

from src.volatility.gamma_scalper import (
    GammaScalper,
    HedgingMode,
    Hedge,
    RealizedPnL
)
from src.volatility.greeks_aggregator import Position


class TestGammaScalpingEdgeCases:
    """Test edge cases for gamma scalping"""
    
    def test_hedging_near_expiration_reduces_threshold(self):
        """
        Test that hedging threshold is reduced near expiration
        
        Requirements: 5.7
        """
        scalper = GammaScalper(
            transaction_cost_bps=5.0,
            expiration_days_threshold=7,
            expiration_threshold_multiplier=0.7
        )
        
        # Position far from expiration (30 days)
        far_position = Position(
            position_id="FAR_POS",
            underlying="TEST",
            option_type="call",
            strike=100.0,
            expiry=date.today() + timedelta(days=30),
            quantity=10,
            spot_price=100.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        # Position near expiration (5 days)
        near_position = Position(
            position_id="NEAR_POS",
            underlying="TEST",
            option_type="call",
            strike=100.0,
            expiry=date.today() + timedelta(days=5),
            quantity=10,
            spot_price=100.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        threshold_far = scalper.compute_hedging_threshold(far_position, 100.0)
        threshold_near = scalper.compute_hedging_threshold(near_position, 100.0)
        
        # Near expiration threshold should be lower
        assert threshold_near < threshold_far
        
        # Should be reduced by the multiplier
        expected_near = threshold_far * 0.7
        assert abs(threshold_near - expected_near) < 0.0001
    
    def test_hedging_at_expiration_day(self):
        """
        Test hedging behavior on expiration day
        
        Requirements: 5.7
        """
        scalper = GammaScalper(
            transaction_cost_bps=5.0,
            expiration_days_threshold=7,
            expiration_threshold_multiplier=0.7
        )
        
        # Position expiring today
        expiring_position = Position(
            position_id="EXPIRING_POS",
            underlying="TEST",
            option_type="call",
            strike=100.0,
            expiry=date.today(),
            quantity=10,
            spot_price=100.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        # Should still compute a threshold (even if very small)
        threshold = scalper.compute_hedging_threshold(expiring_position, 100.0)
        assert threshold > 0
        assert threshold < 0.01  # Should be very small
    
    def test_extreme_high_volatility(self):
        """
        Test gamma scalping with extreme high volatility (100%+)
        
        Requirements: 5.5
        """
        scalper = GammaScalper(transaction_cost_bps=5.0)
        
        position = Position(
            position_id="HIGH_VOL_POS",
            underlying="TEST",
            option_type="call",
            strike=100.0,
            expiry=date.today() + timedelta(days=30),
            quantity=10,
            spot_price=100.0,
            implied_vol=1.50,  # 150% volatility
            risk_free_rate=0.05
        )
        
        # Should still compute valid threshold
        threshold = scalper.compute_hedging_threshold(position, 100.0)
        assert threshold > 0
        assert not np.isnan(threshold)
        assert not np.isinf(threshold)
        
        # Should trigger hedge with large price moves
        assert scalper.should_hedge(position, 120.0)  # 20% move
    
    def test_extreme_low_volatility(self):
        """
        Test gamma scalping with extreme low volatility (5%)
        
        Requirements: 5.5
        """
        scalper = GammaScalper(transaction_cost_bps=5.0)
        
        position = Position(
            position_id="LOW_VOL_POS",
            underlying="TEST",
            option_type="call",
            strike=100.0,
            expiry=date.today() + timedelta(days=30),
            quantity=10,
            spot_price=100.0,
            implied_vol=0.05,  # 5% volatility
            risk_free_rate=0.05
        )
        
        # Should still compute valid threshold
        threshold = scalper.compute_hedging_threshold(position, 100.0)
        assert threshold > 0
        assert not np.isnan(threshold)
        assert not np.isinf(threshold)
    
    def test_high_transaction_costs_increase_threshold(self):
        """
        Test that high transaction costs increase hedging threshold
        
        Requirements: 5.5
        """
        low_cost_scalper = GammaScalper(transaction_cost_bps=1.0)
        high_cost_scalper = GammaScalper(transaction_cost_bps=20.0)
        
        position = Position(
            position_id="TEST_POS",
            underlying="TEST",
            option_type="call",
            strike=100.0,
            expiry=date.today() + timedelta(days=30),
            quantity=10,
            spot_price=100.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        threshold_low = low_cost_scalper.compute_hedging_threshold(position, 100.0)
        threshold_high = high_cost_scalper.compute_hedging_threshold(position, 100.0)
        
        # Higher transaction costs should lead to higher threshold (less frequent hedging)
        assert threshold_high > threshold_low
        
        # Relationship should be roughly sqrt(cost_ratio)
        cost_ratio = 20.0 / 1.0
        expected_ratio = np.sqrt(cost_ratio)
        actual_ratio = threshold_high / threshold_low
        
        # Allow some tolerance
        assert abs(actual_ratio - expected_ratio) < 0.5
    
    def test_zero_gamma_position(self):
        """
        Test handling of position with zero gamma
        
        Requirements: 5.1
        """
        scalper = GammaScalper(transaction_cost_bps=5.0)
        
        # Position with zero quantity (effectively zero gamma)
        zero_position = Position(
            position_id="ZERO_POS",
            underlying="TEST",
            option_type="call",
            strike=100.0,
            expiry=date.today() + timedelta(days=30),
            quantity=0,  # Zero quantity
            spot_price=100.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        # Should return infinite threshold (never hedge)
        threshold = scalper.compute_hedging_threshold(zero_position, 100.0)
        assert np.isinf(threshold)
    
    def test_first_hedge_always_triggers(self):
        """
        Test that first hedge always triggers (no last price)
        
        Requirements: 5.2
        """
        scalper = GammaScalper(transaction_cost_bps=5.0)
        
        position = Position(
            position_id="NEW_POS",
            underlying="TEST",
            option_type="call",
            strike=100.0,
            expiry=date.today() + timedelta(days=30),
            quantity=10,
            spot_price=100.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        # First hedge should always trigger
        assert scalper.should_hedge(position, 100.0)
    
    def test_hedge_with_large_price_gap(self):
        """
        Test hedging with large price gap (e.g., overnight gap)
        
        Requirements: 5.2
        """
        scalper = GammaScalper(transaction_cost_bps=5.0)
        
        position = Position(
            position_id="GAP_POS",
            underlying="TEST",
            option_type="call",
            strike=100.0,
            expiry=date.today() + timedelta(days=30),
            quantity=10,
            spot_price=100.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        # Record first hedge
        scalper.last_hedge_price[position.position_id] = 100.0
        
        # Large price gap (20% move)
        assert scalper.should_hedge(position, 120.0)
        
        # Very large price gap (50% move)
        assert scalper.should_hedge(position, 150.0)
    
    def test_realized_variance_with_no_price_movement(self):
        """
        Test realized variance computation when prices don't move
        
        Requirements: 5.3
        """
        scalper = GammaScalper(transaction_cost_bps=5.0)
        
        position_id = "FLAT_POS"
        
        # Record hedges with no price movement
        for i in range(5):
            hedge = Hedge(
                timestamp=datetime.now() + timedelta(days=i),
                position_id=position_id,
                underlying="TEST",
                price=100.0,  # Same price
                delta_before=0.5,
                delta_after=0.0,
                hedge_quantity=10.0,
                transaction_cost=5.0,
                pnl=0.0
            )
            
            if position_id not in scalper.hedge_history:
                scalper.hedge_history[position_id] = []
            scalper.hedge_history[position_id].append(hedge)
        
        # Realized variance should be zero (no movement)
        realized_var = scalper.compute_realized_variance(position_id)
        assert realized_var == 0.0
    
    def test_realized_variance_with_single_hedge(self):
        """
        Test realized variance computation with only one hedge
        
        Requirements: 5.3
        """
        scalper = GammaScalper(transaction_cost_bps=5.0)
        
        position_id = "SINGLE_HEDGE"
        
        # Record single hedge
        hedge = Hedge(
            timestamp=datetime.now(),
            position_id=position_id,
            underlying="TEST",
            price=100.0,
            delta_before=0.5,
            delta_after=0.0,
            hedge_quantity=10.0,
            transaction_cost=5.0,
            pnl=0.0
        )
        
        scalper.hedge_history[position_id] = [hedge]
        
        # Should return 0 (need at least 2 hedges)
        realized_var = scalper.compute_realized_variance(position_id)
        assert realized_var == 0.0
    
    def test_continuous_hedging_mode_very_low_threshold(self):
        """
        Test that continuous hedging mode has very low threshold
        
        Requirements: 5.6
        """
        scalper = GammaScalper(transaction_cost_bps=5.0)
        
        position = Position(
            position_id="CONTINUOUS_POS",
            underlying="TEST",
            option_type="call",
            strike=100.0,
            expiry=date.today() + timedelta(days=30),
            quantity=10,
            spot_price=100.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        threshold_normal = scalper.compute_hedging_threshold(position, 100.0, HedgingMode.NORMAL)
        threshold_continuous = scalper.compute_hedging_threshold(position, 100.0, HedgingMode.CONTINUOUS)
        
        # Continuous should be much lower (10% of normal)
        assert threshold_continuous < threshold_normal * 0.2
        assert threshold_continuous > 0
    
    def test_hedge_order_for_call_with_positive_delta(self):
        """
        Test hedge order generation for call with positive delta
        
        Requirements: 5.2
        """
        scalper = GammaScalper(transaction_cost_bps=5.0)
        
        position = Position(
            position_id="CALL_POS",
            underlying="TEST",
            option_type="call",
            strike=100.0,
            expiry=date.today() + timedelta(days=30),
            quantity=10,
            spot_price=100.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        # Positive delta (long call)
        current_delta = 5.0
        
        order = scalper.generate_hedge_order(position, current_delta, 100.0, target_delta=0.0)
        
        # Should sell to neutralize positive delta
        assert order.quantity < 0
        assert abs(order.quantity) == pytest.approx(5.0)
        assert order.instrument == "TEST"
        assert order.order_type == "market"
    
    def test_hedge_order_for_put_with_negative_delta(self):
        """
        Test hedge order generation for put with negative delta
        
        Requirements: 5.2
        """
        scalper = GammaScalper(transaction_cost_bps=5.0)
        
        position = Position(
            position_id="PUT_POS",
            underlying="TEST",
            option_type="put",
            strike=100.0,
            expiry=date.today() + timedelta(days=30),
            quantity=10,
            spot_price=100.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        # Negative delta (long put)
        current_delta = -5.0
        
        order = scalper.generate_hedge_order(position, current_delta, 100.0, target_delta=0.0)
        
        # Should buy to neutralize negative delta
        assert order.quantity > 0
        assert order.quantity == pytest.approx(5.0)
        assert order.instrument == "TEST"
    
    def test_transaction_cost_accumulation(self):
        """
        Test that transaction costs accumulate correctly over multiple hedges
        
        Requirements: 5.5
        """
        scalper = GammaScalper(transaction_cost_bps=10.0)  # 10 bps
        
        position = Position(
            position_id="COST_POS",
            underlying="TEST",
            option_type="call",
            strike=100.0,
            expiry=date.today() + timedelta(days=30),
            quantity=10,
            spot_price=100.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        # Record multiple hedges
        total_expected_cost = 0.0
        for i in range(5):
            price = 100.0 + i
            hedge_qty = 10.0
            
            hedge = scalper.record_hedge(
                position=position,
                current_price=price,
                delta_before=0.5,
                delta_after=0.0,
                hedge_quantity=hedge_qty,
                execution_price=price
            )
            
            # Expected cost: quantity * price * bps / 10000
            expected_cost = abs(hedge_qty) * price * 10.0 / 10000
            assert hedge.transaction_cost == pytest.approx(expected_cost)
            
            total_expected_cost += expected_cost
        
        # Check total costs
        stats = scalper.get_hedging_statistics(position.position_id)
        assert stats['total_costs'] == pytest.approx(total_expected_cost)
    
    def test_adaptive_hedging_with_zero_implied_variance(self):
        """
        Test adaptive hedging when implied variance is zero
        
        Requirements: 5.4
        """
        scalper = GammaScalper(transaction_cost_bps=5.0)
        
        position = Position(
            position_id="ZERO_IV_POS",
            underlying="TEST",
            option_type="call",
            strike=100.0,
            expiry=date.today() + timedelta(days=30),
            quantity=10,
            spot_price=100.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        )
        
        # Performance with zero implied variance
        performance = RealizedPnL(
            total_pnl=0.0,
            option_pnl=0.0,
            hedge_pnl=0.0,
            variance_pnl=0.0,
            realized_var=0.04,
            implied_var=0.0,  # Zero implied variance
            num_hedges=10,
            total_transaction_costs=0.0
        )
        
        # Should return default mode (not crash)
        mode = scalper.adapt_hedging_frequency(position, performance)
        assert mode == scalper.default_mode
    
    def test_reset_position_history(self):
        """
        Test resetting position history when position is closed
        
        Requirements: 5.3
        """
        scalper = GammaScalper(transaction_cost_bps=5.0)
        
        position_id = "RESET_POS"
        
        # Add some hedges
        for i in range(3):
            hedge = Hedge(
                timestamp=datetime.now() + timedelta(days=i),
                position_id=position_id,
                underlying="TEST",
                price=100.0 + i,
                delta_before=0.5,
                delta_after=0.0,
                hedge_quantity=10.0,
                transaction_cost=5.0,
                pnl=0.0
            )
            
            if position_id not in scalper.hedge_history:
                scalper.hedge_history[position_id] = []
            scalper.hedge_history[position_id].append(hedge)
        
        scalper.last_hedge_price[position_id] = 102.0
        scalper.hedging_modes[position_id] = HedgingMode.HIGH_FREQUENCY
        
        # Verify data exists
        assert position_id in scalper.hedge_history
        assert position_id in scalper.last_hedge_price
        assert position_id in scalper.hedging_modes
        
        # Reset
        scalper.reset_position_history(position_id)
        
        # Verify data is cleared
        assert position_id not in scalper.hedge_history
        assert position_id not in scalper.last_hedge_price
        assert position_id not in scalper.hedging_modes
    
    def test_hedging_statistics_empty_position(self):
        """
        Test getting statistics for position with no hedges
        
        Requirements: 5.3
        """
        scalper = GammaScalper(transaction_cost_bps=5.0)
        
        stats = scalper.get_hedging_statistics("NONEXISTENT_POS")
        
        assert stats['num_hedges'] == 0
        assert stats['total_pnl'] == 0.0
        assert stats['total_costs'] == 0.0
        assert stats['avg_hedge_size'] == 0.0
        assert stats['realized_variance'] == 0.0
