"""
Property-based tests for Options Trading System - Tax-Aware P&L Tracker

These tests validate universal correctness properties for P&L calculation
using hypothesis for property-based testing.

Feature: options-trading-system
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from datetime import datetime, date
from dataclasses import dataclass

from src.options.tax_aware_pnl_tracker import TaxAwarePnLTracker, TradeCosts
from src.options.position_manager import PositionLeg
from src.options.strategy_generator import OptionLeg, Greeks


# Mock config for testing
@dataclass
class MockCostsConfig:
    """Mock costs config for testing"""
    brokerage_per_leg: float = 20.0
    exchange_charges_pct: float = 0.0005
    sebi_charges_per_crore: float = 10.0
    stamp_duty_pct: float = 0.00003
    gst_pct: float = 0.18


@dataclass
class MockTaxConfig:
    """Mock tax config for testing"""
    rate: float = 0.30
    min_profitability_multiplier: float = 1.5


class TestPnLCalculationProperties:
    """Property-based tests for P&L calculation"""
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    @given(
        entry_value=st.floats(min_value=-10000, max_value=10000),
        exit_value=st.floats(min_value=-10000, max_value=10000)
    )
    def test_property_36_gross_pnl_formula(self, entry_value, exit_value):
        """
        # Feature: options-trading-system, Property 36: Gross P&L Formula
        
        For any closed position, the gross P&L should equal
        exit_value - entry_credit_debit.
        
        Validates: Requirements US-8.1
        """
        # Create tracker for this test
        costs_config = MockCostsConfig()
        tax_config = MockTaxConfig()
        tracker = TaxAwarePnLTracker(costs_config=costs_config, tax_config=tax_config)
        
        # Calculate gross P&L
        gross_pnl = tracker.calculate_gross_pnl(entry_value, exit_value)
        
        # Property: gross_pnl = exit_value - entry_value
        expected_gross_pnl = exit_value - entry_value
        
        assert abs(gross_pnl - expected_gross_pnl) < 0.01, \
            f"Gross P&L formula incorrect: expected {expected_gross_pnl}, got {gross_pnl}"
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    @given(
        num_legs=st.integers(min_value=1, max_value=4),
        premium_per_leg=st.floats(min_value=50, max_value=500),
        quantity_per_leg=st.integers(min_value=15, max_value=100)
    )
    def test_property_37_cost_completeness(self, num_legs, premium_per_leg, quantity_per_leg):
        """
        # Feature: options-trading-system, Property 37: Cost Completeness
        
        For any trade, the total costs must include all five components:
        brokerage, exchange charges, SEBI charges, stamp duty, and GST.
        
        Validates: Requirements US-8.2
        """
        # Create tracker for this test
        costs_config = MockCostsConfig()
        tax_config = MockTaxConfig()
        tracker = TaxAwarePnLTracker(costs_config=costs_config, tax_config=tax_config)
        
        # Create legs
        legs = []
        for i in range(num_legs):
            legs.append(PositionLeg(
                symbol=f"NIFTY24JAN{21000+i*100}CE",
                strike=21000 + i * 100,
                option_type="call",
                action="buy" if i % 2 == 0 else "sell",
                quantity=quantity_per_leg,
                entry_premium=premium_per_leg,
                current_premium=premium_per_leg,
                entry_iv=0.15,
                current_iv=0.15,
                delta=0.5,
                gamma=0.01,
                theta=-10.0,
                vega=50.0
            ))
        
        # Calculate costs
        costs = tracker.calculate_costs(legs)
        
        # Property: All cost components must be present and non-negative
        assert hasattr(costs, 'brokerage'), "Missing brokerage component"
        assert hasattr(costs, 'exchange_charges'), "Missing exchange_charges component"
        assert hasattr(costs, 'sebi_charges'), "Missing sebi_charges component"
        assert hasattr(costs, 'stamp_duty'), "Missing stamp_duty component"
        assert hasattr(costs, 'gst'), "Missing gst component"
        assert hasattr(costs, 'total'), "Missing total component"
        
        assert costs.brokerage >= 0, "Brokerage should be non-negative"
        assert costs.exchange_charges >= 0, "Exchange charges should be non-negative"
        assert costs.sebi_charges >= 0, "SEBI charges should be non-negative"
        assert costs.stamp_duty >= 0, "Stamp duty should be non-negative"
        assert costs.gst >= 0, "GST should be non-negative"
        
        # Property: Total should equal sum of components
        expected_total = (costs.brokerage + costs.exchange_charges + 
                         costs.sebi_charges + costs.stamp_duty + costs.gst)
        
        assert abs(costs.total - expected_total) < 0.01, \
            f"Total costs should equal sum of components: expected {expected_total}, got {costs.total}"
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    @given(
        gross_pnl=st.floats(min_value=-10000, max_value=10000)
    )
    def test_property_38_tax_calculation(self, gross_pnl):
        """
        # Feature: options-trading-system, Property 38: Tax Calculation
        
        For any closed trade:
        - If gross P&L > 0, tax = 0.30 × gross_pnl
        - If gross P&L ≤ 0, tax = 0
        
        Validates: Requirements US-8.3
        """
        # Create tracker for this test
        costs_config = MockCostsConfig()
        tax_config = MockTaxConfig()
        tracker = TaxAwarePnLTracker(costs_config=costs_config, tax_config=tax_config)
        
        # Calculate tax
        tax = tracker.calculate_tax(gross_pnl)
        
        # Property: Tax calculation based on profit/loss
        if gross_pnl > 0:
            expected_tax = gross_pnl * 0.30
            assert abs(tax - expected_tax) < 0.01, \
                f"Tax on profit incorrect: expected {expected_tax}, got {tax}"
        else:
            assert tax == 0.0, f"Tax on loss should be 0, got {tax}"
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    @given(
        gross_pnl=st.floats(min_value=-10000, max_value=10000),
        total_costs=st.floats(min_value=100, max_value=1000)
    )
    def test_property_39_net_pnl_formula(self, gross_pnl, total_costs):
        """
        # Feature: options-trading-system, Property 39: Net P&L Formula
        
        For any closed trade, the net P&L should equal
        gross_pnl - costs - tax.
        
        Validates: Requirements US-8.4
        """
        # Create tracker for this test
        costs_config = MockCostsConfig()
        tax_config = MockTaxConfig()
        tracker = TaxAwarePnLTracker(costs_config=costs_config, tax_config=tax_config)
        
        # Calculate tax
        tax = tracker.calculate_tax(gross_pnl)
        
        # Create mock costs object
        mock_costs = TradeCosts(
            brokerage=total_costs * 0.4,
            exchange_charges=total_costs * 0.2,
            sebi_charges=total_costs * 0.1,
            stamp_duty=total_costs * 0.1,
            gst=total_costs * 0.2,
            total=total_costs
        )
        
        # Calculate net P&L
        net_pnl = tracker.calculate_net_pnl(gross_pnl, mock_costs, tax)
        
        # Property: net_pnl = gross_pnl - costs - tax
        expected_net_pnl = gross_pnl - total_costs - tax
        
        assert abs(net_pnl - expected_net_pnl) < 0.01, \
            f"Net P&L formula incorrect: expected {expected_net_pnl}, got {net_pnl}"


def test_estimated_trade_economics_include_indian_charges_and_slippage():
    tracker = TaxAwarePnLTracker(costs_config=MockCostsConfig(), tax_config=MockTaxConfig())

    legs = [
        OptionLeg(
            strike=25000,
            option_type="CE",
            expiry=datetime.now(),
            action="BUY",
            quantity=50,
            premium=120.0,
            greeks=Greeks(delta=0.45, gamma=0.01, theta=-8.0, vega=22.0),
            instrument_key="NSE_FO|123",
        ),
        OptionLeg(
            strike=25200,
            option_type="CE",
            expiry=datetime.now(),
            action="SELL",
            quantity=50,
            premium=90.0,
            greeks=Greeks(delta=0.32, gamma=0.01, theta=-6.0, vega=18.0),
            instrument_key="NSE_FO|456",
        ),
    ]

    economics = tracker.estimate_trade_economics(
        legs=legs,
        expected_gross_pnl=4000.0,
        max_loss=12000.0,
        slippage_bps=75.0,
    )

    assert economics["costs"].brokerage > 0.0
    assert economics["costs"].gst > 0.0
    assert economics["slippage_cost"] > 0.0
    assert economics["expected_tax"] > 0.0
    assert economics["expected_net_pnl"] < economics["expected_gross_pnl"]
    assert economics["net_max_loss"] > 12000.0
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    @given(
        expected_gross_pnl=st.floats(min_value=-5000, max_value=10000),
        num_legs=st.integers(min_value=1, max_value=4)
    )
    def test_property_40_minimum_profitability_filter(self, expected_gross_pnl, num_legs):
        """
        # Feature: options-trading-system, Property 40: Minimum Profitability Filter
        
        For any proposed trade, if the expected net P&L is less than
        1.5 times the estimated total costs, the trade should be rejected.
        
        Validates: Requirements US-8.5
        """
        # Create tracker for this test
        costs_config = MockCostsConfig()
        tax_config = MockTaxConfig()
        tracker = TaxAwarePnLTracker(costs_config=costs_config, tax_config=tax_config)
        
        # Create mock legs for cost calculation
        legs = []
        for i in range(num_legs):
            legs.append(PositionLeg(
                symbol=f"NIFTY24JAN{21000+i*100}CE",
                strike=21000 + i * 100,
                option_type="call",
                action="buy" if i % 2 == 0 else "sell",
                quantity=50,
                entry_premium=200.0,
                current_premium=200.0,
                entry_iv=0.15,
                current_iv=0.15,
                delta=0.5,
                gamma=0.01,
                theta=-10.0,
                vega=50.0
            ))
        
        # Check profitability filter
        result = tracker.check_minimum_profitability(expected_gross_pnl, legs)
        
        # Calculate expected values
        costs = tracker.calculate_costs(legs)
        tax = tracker.calculate_tax(expected_gross_pnl)
        expected_net_pnl = expected_gross_pnl - costs.total - tax
        
        # Property: Reject if net P&L < 1.5 × costs
        if expected_net_pnl >= 1.5 * costs.total:
            assert result is True, \
                f"Should accept trade with net P&L {expected_net_pnl} vs costs {costs.total}"
        else:
            assert result is False, \
                f"Should reject trade with net P&L {expected_net_pnl} vs costs {costs.total}"
    
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    @given(
        num_trades=st.integers(min_value=1, max_value=20),
        profit_per_trade=st.floats(min_value=-2000, max_value=5000)
    )
    def test_property_41_ytd_tax_liability_aggregation(self, num_trades, profit_per_trade):
        """
        # Feature: options-trading-system, Property 41: YTD Tax Liability Aggregation
        
        For any set of closed trades, the YTD tax liability should equal
        the sum of taxes on all profitable trades.
        
        Validates: Requirements US-8.6
        """
        # Create tracker for this test
        costs_config = MockCostsConfig()
        tax_config = MockTaxConfig()
        tracker = TaxAwarePnLTracker(costs_config=costs_config, tax_config=tax_config)
        
        # Create trades with varying P&L
        expected_ytd_tax = 0.0
        
        for i in range(num_trades):
            gross_pnl = profit_per_trade + (i * 100)  # Vary profits
            
            if gross_pnl > 0:
                expected_ytd_tax += gross_pnl * 0.30
            
            # Update YTD tracking
            tax = tracker.calculate_tax(gross_pnl)
            tracker.ytd_tax_liability += tax
        
        # Property: YTD tax = sum of taxes on profitable trades
        assert abs(tracker.ytd_tax_liability - expected_ytd_tax) < 0.01, \
            f"YTD tax liability incorrect: expected {expected_ytd_tax}, got {tracker.ytd_tax_liability}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
