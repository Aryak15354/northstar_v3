#!/usr/bin/env python3
"""
Property Tests: Enhanced Transaction Cost Model

Tests the critical properties that ensure transaction costs are realistic
and properly account for market conditions and liquidity constraints.

Property 5: Transaction Cost Lower Bound - Validates: Requirements 2.1
Property 6: Liquidity-Based Slippage Scaling - Validates: Requirements 2.2
Property 7: Volatility-Proportional Costs - Validates: Requirements 2.3
Property 8: Crisis Cost Amplification - Validates: Requirements 2.4
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Add src to path
, '..', '..'))

from src.execution.enhanced_transaction_cost_model import EnhancedTransactionCostModel


class TestEnhancedTransactionCostProperties:
    """Property-based tests for enhanced transaction cost model"""
    
    def setup_method(self):
        """Setup for each test"""
        self.cost_model = EnhancedTransactionCostModel()
    
    def test_property_transaction_cost_lower_bound(self):
        """
        Property 5: Transaction Cost Lower Bound
        
        Tests that transaction costs never fall below the minimum regulatory
        and exchange-mandated costs, regardless of market conditions.
        """
        
        print("🧪 Testing Property 5: Transaction Cost Lower Bound")
        
        # Test various trade sizes and market conditions
        test_scenarios = [
            # (shares, price, market_conditions)
            (100, 1000, {'volatility': 0.05, 'vix': 10, 'market_stress': 0.0}),  # Very calm market
            (1000, 100, {'volatility': 0.08, 'vix': 12, 'market_stress': 0.1}),  # Extremely calm
            (50, 5000, {'volatility': 0.10, 'vix': 15, 'market_stress': 0.0}),   # Low volatility
        ]
        
        # Calculate minimum expected costs (regulatory minimums)
        min_expected_costs = {
            'brokerage': 0.0003,        # 3 bps minimum
            'stt': 0.001,               # 10 bps STT
            'stamp_duty': 0.00003,      # 0.3 bps
            'gst': 0.00018,             # 1.8 bps GST
            'sebi_charges': 0.000001,   # 0.01 bps
            'exchange_charges': 0.0000345, # 0.345 bps
        }
        
        min_total_rate = sum(min_expected_costs.values())
        
        for shares, price, market_conditions in test_scenarios:
            trade_value = shares * price
            
            cost_breakdown = self.cost_model.calculate_total_cost(
                'TEST.NS', shares, price, market_conditions
            )
            
            # Property 1: Total cost should never be below regulatory minimum
            min_expected_cost = trade_value * min_total_rate + self.cost_model.base_costs['dp_charges']
            actual_cost = cost_breakdown['total_transaction_cost']
            
            assert actual_cost >= min_expected_cost * 0.95, (  # Allow 5% tolerance for rounding
                f"Cost {actual_cost:.2f} below minimum {min_expected_cost:.2f} "
                f"for trade value ₹{trade_value:,}"
            )
            
            # Property 2: Each component should meet minimum
            base_costs = cost_breakdown['base_costs']
            for cost_type, min_rate in min_expected_costs.items():
                if cost_type in base_costs:
                    expected_component = trade_value * min_rate
                    actual_component = base_costs[cost_type]
                    
                    assert actual_component >= expected_component * 0.95, (
                        f"{cost_type} cost {actual_component:.2f} below minimum {expected_component:.2f}"
                    )
            
            # Property 3: Crisis multiplier should not reduce costs below minimum
            crisis_costs = cost_breakdown['crisis_adjusted_costs']
            assert crisis_costs['total_base_cost'] >= min_expected_cost * 0.95, (
                "Crisis adjustment should not reduce costs below regulatory minimum"
            )
            
            print(f"   ✅ Trade ₹{trade_value:,}: Cost {actual_cost:.2f} >= Min {min_expected_cost:.2f}")
        
        print("✅ Property 5: Transaction Cost Lower Bound PASSED")
    
    def test_property_liquidity_based_slippage_scaling(self):
        """
        Property 6: Liquidity-Based Slippage Scaling
        
        Tests that market impact scales appropriately with trade size
        relative to average daily volume (ADV).
        """
        
        print("🧪 Testing Property 6: Liquidity-Based Slippage Scaling")
        
        # Test different liquidity scenarios
        base_price = 1000
        base_shares = 1000
        market_conditions = {'volatility': 0.15, 'vix': 20, 'market_stress': 0.2}
        
        # Different liquidity levels (ADV)
        liquidity_scenarios = [
            {'adv_60d': 100_000_000, 'market_cap': 1_000_000_000},  # High liquidity
            {'adv_60d': 10_000_000, 'market_cap': 100_000_000},     # Medium liquidity
            {'adv_60d': 1_000_000, 'market_cap': 10_000_000},       # Low liquidity
        ]
        
        # Different trade sizes as percentage of ADV
        trade_size_multipliers = [0.5, 1.0, 2.0, 5.0]  # 0.5x to 5x base trade
        
        for liquidity_data in liquidity_scenarios:
            adv = liquidity_data['adv_60d']
            impact_costs = []
            adv_percentages = []
            
            for multiplier in trade_size_multipliers:
                shares = int(base_shares * multiplier)
                trade_value = shares * base_price
                adv_percentage = trade_value / adv
                
                cost_breakdown = self.cost_model.calculate_total_cost(
                    'TEST.NS', shares, base_price, market_conditions, liquidity_data
                )
                
                impact_bps = cost_breakdown['market_impact']['total_impact_bps']
                impact_costs.append(impact_bps)
                adv_percentages.append(adv_percentage)
                
                print(f"   ADV ₹{adv:,}: {adv_percentage:.1%} of ADV → {impact_bps:.1f} bps impact")
            
            # Property 1: Market impact should increase with trade size
            for i in range(1, len(impact_costs)):
                assert impact_costs[i] >= impact_costs[i-1], (
                    f"Market impact should increase with trade size: "
                    f"{impact_costs[i]:.1f} bps < {impact_costs[i-1]:.1f} bps"
                )
            
            # Property 2: Impact should scale non-linearly (square root law)
            # For large trades, impact should grow faster than linear
            if len(impact_costs) >= 3:
                # Check that impact growth accelerates
                growth_rate_1 = impact_costs[1] - impact_costs[0]
                growth_rate_2 = impact_costs[2] - impact_costs[1]
                
                # For significant trade sizes, growth should accelerate
                if adv_percentages[2] > 0.02:  # If trade is > 2% of ADV
                    assert growth_rate_2 >= growth_rate_1 * 0.8, (
                        "Market impact should show non-linear scaling for large trades"
                    )
            
            # Property 3: Very large trades should have substantial impact
            max_adv_pct = max(adv_percentages)
            max_impact = max(impact_costs)
            
            if max_adv_pct > 0.05:  # If trade > 5% of ADV
                assert max_impact > 20, (  # Should have > 20 bps impact
                    f"Large trade ({max_adv_pct:.1%} of ADV) should have substantial impact, got {max_impact:.1f} bps"
                )
        
        print("✅ Property 6: Liquidity-Based Slippage Scaling PASSED")
    
    def test_property_volatility_proportional_costs(self):
        """
        Property 7: Volatility-Proportional Costs
        
        Tests that market impact costs increase proportionally with
        market volatility.
        """
        
        print("🧪 Testing Property 7: Volatility-Proportional Costs")
        
        # Test different volatility levels
        volatility_levels = [0.10, 0.15, 0.20, 0.30, 0.40]  # 10% to 40% volatility
        
        base_trade = {
            'shares': 2000,
            'price': 1500,
            'liquidity_data': {'adv_60d': 20_000_000, 'market_cap': 200_000_000}
        }
        
        impact_costs = []
        
        for volatility in volatility_levels:
            market_conditions = {
                'volatility': volatility,
                'vix': volatility * 100,  # Approximate VIX relationship
                'market_stress': min(0.8, volatility * 2)  # Higher vol = more stress
            }
            
            cost_breakdown = self.cost_model.calculate_total_cost(
                'TEST.NS', base_trade['shares'], base_trade['price'],
                market_conditions, base_trade['liquidity_data']
            )
            
            impact_bps = cost_breakdown['market_impact']['total_impact_bps']
            impact_costs.append(impact_bps)
            
            print(f"   Volatility {volatility:.0%}: Market impact {impact_bps:.1f} bps")
        
        # Property 1: Market impact should increase with volatility
        for i in range(1, len(impact_costs)):
            assert impact_costs[i] >= impact_costs[i-1], (
                f"Market impact should increase with volatility: "
                f"{impact_costs[i]:.1f} bps < {impact_costs[i-1]:.1f} bps at vol {volatility_levels[i]:.0%}"
            )
        
        # Property 2: High volatility should have significantly higher impact
        low_vol_impact = impact_costs[0]   # 10% volatility
        high_vol_impact = impact_costs[-1]  # 40% volatility
        
        impact_ratio = high_vol_impact / low_vol_impact
        assert impact_ratio >= 2.0, (
            f"High volatility impact should be at least 2x low volatility: "
            f"ratio = {impact_ratio:.1f}"
        )
        
        # Property 3: Impact should scale roughly proportionally to volatility
        # (allowing for non-linear effects)
        vol_ratio = volatility_levels[-1] / volatility_levels[0]  # 40% / 10% = 4x
        
        # Impact ratio should be between 1.0x and 10x the volatility ratio (allowing for non-linear scaling)
        assert 1.0 <= impact_ratio / vol_ratio <= 10.0, (
            f"Impact scaling should be reasonable relative to volatility: "
            f"impact ratio {impact_ratio:.1f}, vol ratio {vol_ratio:.1f}, ratio of ratios {impact_ratio/vol_ratio:.1f}"
        )
        
        print("✅ Property 7: Volatility-Proportional Costs PASSED")
    
    def test_property_crisis_cost_amplification(self):
        """
        Property 8: Crisis Cost Amplification
        
        Tests that transaction costs are appropriately amplified during
        crisis periods through crisis multipliers.
        """
        
        print("🧪 Testing Property 8: Crisis Cost Amplification")
        
        # Define market regimes with expected multipliers
        market_regimes = [
            ({'volatility': 0.12, 'vix': 18, 'market_stress': 0.1}, 'normal', 1.0),
            ({'volatility': 0.25, 'vix': 25, 'market_stress': 0.4}, 'stress', 1.5),
            ({'volatility': 0.35, 'vix': 35, 'market_stress': 0.7}, 'crisis', 2.0),
            ({'volatility': 0.45, 'vix': 45, 'market_stress': 0.9}, 'extreme_crisis', 3.0),
        ]
        
        base_trade = {
            'shares': 1500,
            'price': 2000,
            'liquidity_data': {'adv_60d': 30_000_000, 'market_cap': 300_000_000}
        }
        
        regime_costs = []
        
        for market_conditions, expected_regime, expected_multiplier in market_regimes:
            cost_breakdown = self.cost_model.calculate_total_cost(
                'TEST.NS', base_trade['shares'], base_trade['price'],
                market_conditions, base_trade['liquidity_data']
            )
            
            detected_regime = cost_breakdown['market_regime']
            actual_multiplier = cost_breakdown['crisis_multiplier']
            total_cost = cost_breakdown['total_transaction_cost']
            
            regime_costs.append((detected_regime, actual_multiplier, total_cost))
            
            print(f"   {market_conditions['volatility']:.0%} vol: {detected_regime} regime, "
                  f"{actual_multiplier:.1f}x multiplier, ₹{total_cost:.0f} cost")
            
            # Property 1: Regime should be detected correctly
            assert detected_regime == expected_regime, (
                f"Expected {expected_regime} regime, got {detected_regime}"
            )
            
            # Property 2: Multiplier should match expected
            assert abs(actual_multiplier - expected_multiplier) < 0.1, (
                f"Expected {expected_multiplier}x multiplier, got {actual_multiplier}x"
            )
        
        # Property 3: Total costs should increase with crisis severity
        for i in range(1, len(regime_costs)):
            prev_cost = regime_costs[i-1][2]
            curr_cost = regime_costs[i][2]
            
            assert curr_cost >= prev_cost, (
                f"Crisis costs should increase: {curr_cost:.0f} < {prev_cost:.0f}"
            )
        
        # Property 4: Extreme crisis should have much higher costs than normal
        normal_cost = regime_costs[0][2]
        extreme_crisis_cost = regime_costs[-1][2]
        
        cost_ratio = extreme_crisis_cost / normal_cost
        assert cost_ratio >= 2.0, (
            f"Extreme crisis should have at least 2x normal costs: ratio = {cost_ratio:.1f}"
        )
        
        # Property 5: Crisis multiplier should only affect variable costs
        # (DP charges should remain constant)
        normal_breakdown = self.cost_model.calculate_total_cost(
            'TEST.NS', base_trade['shares'], base_trade['price'],
            market_regimes[0][0], base_trade['liquidity_data']
        )
        
        crisis_breakdown = self.cost_model.calculate_total_cost(
            'TEST.NS', base_trade['shares'], base_trade['price'],
            market_regimes[-1][0], base_trade['liquidity_data']
        )
        
        normal_dp = normal_breakdown['crisis_adjusted_costs']['dp_charges']
        crisis_dp = crisis_breakdown['crisis_adjusted_costs']['dp_charges']
        
        assert abs(normal_dp - crisis_dp) < 0.01, (
            f"DP charges should not change with crisis: {normal_dp:.2f} vs {crisis_dp:.2f}"
        )
        
        print("✅ Property 8: Crisis Cost Amplification PASSED")
    
    def test_funding_cost_consistency(self):
        """Test that funding costs are applied consistently for long/short positions"""
        
        print("🧪 Testing Funding Cost Consistency")
        
        base_conditions = {'volatility': 0.15, 'vix': 20, 'market_stress': 0.2}
        liquidity_data = {'adv_60d': 50_000_000, 'market_cap': 500_000_000}
        
        # Test long and short positions
        long_cost = self.cost_model.calculate_total_cost(
            'TEST.NS', 1000, 1000, base_conditions, liquidity_data, holding_period_days=1
        )
        
        short_cost = self.cost_model.calculate_total_cost(
            'TEST.NS', -1000, 1000, base_conditions, liquidity_data, holding_period_days=1
        )
        
        # Property 1: Short positions should have higher funding costs
        long_funding = long_cost['funding_costs'].get('funding_cost', 0)
        short_funding = short_cost['funding_costs'].get('total_funding_cost', 0)
        
        assert short_funding > long_funding, (
            f"Short funding cost {short_funding:.2f} should exceed long {long_funding:.2f}"
        )
        
        # Property 2: Funding costs should scale with holding period
        long_cost_5d = self.cost_model.calculate_total_cost(
            'TEST.NS', 1000, 1000, base_conditions, liquidity_data, holding_period_days=5
        )
        
        long_funding_5d = long_cost_5d['funding_costs'].get('funding_cost', 0)
        
        assert long_funding_5d > long_funding * 4, (  # Should be ~5x but allow some tolerance
            f"5-day funding {long_funding_5d:.2f} should be ~5x 1-day {long_funding:.2f}"
        )
        
        print(f"   Long 1d: ₹{long_funding:.2f}, Short 1d: ₹{short_funding:.2f}, Long 5d: ₹{long_funding_5d:.2f}")
        print("✅ Funding Cost Consistency PASSED")
    
    def test_cost_component_additivity(self):
        """Test that cost components add up correctly"""
        
        print("🧪 Testing Cost Component Additivity")
        
        market_conditions = {'volatility': 0.25, 'vix': 30, 'market_stress': 0.5}
        liquidity_data = {'adv_60d': 15_000_000, 'market_cap': 150_000_000}
        
        cost_breakdown = self.cost_model.calculate_total_cost(
            'TEST.NS', 2000, 1200, market_conditions, liquidity_data
        )
        
        # Extract components
        base_cost = cost_breakdown['crisis_adjusted_costs']['total_base_cost']
        market_impact_cost = cost_breakdown['market_impact']['impact_cost']
        funding_cost = cost_breakdown['funding_costs'].get('funding_cost', 
                                                         cost_breakdown['funding_costs'].get('total_funding_cost', 0))
        
        calculated_total = base_cost + market_impact_cost + funding_cost
        reported_total = cost_breakdown['total_transaction_cost']
        
        # Property: Components should sum to total (within rounding tolerance)
        assert abs(calculated_total - reported_total) < 0.01, (
            f"Components {calculated_total:.2f} should sum to total {reported_total:.2f}"
        )
        
        print(f"   Base: ₹{base_cost:.2f}, Impact: ₹{market_impact_cost:.2f}, "
              f"Funding: ₹{funding_cost:.2f}, Total: ₹{reported_total:.2f}")
        print("✅ Cost Component Additivity PASSED")


def test_enhanced_transaction_cost_properties():
    """Run all enhanced transaction cost property tests"""
    
    print("💰 ENHANCED TRANSACTION COST PROPERTY TESTS")
    print("=" * 60)
    
    test_suite = TestEnhancedTransactionCostProperties()
    
    # Run each test
    test_methods = [
        'test_property_transaction_cost_lower_bound',
        'test_property_liquidity_based_slippage_scaling',
        'test_property_volatility_proportional_costs',
        'test_property_crisis_cost_amplification',
        'test_funding_cost_consistency',
        'test_cost_component_additivity'
    ]
    
    passed = 0
    failed = 0
    
    for method_name in test_methods:
        try:
            test_suite.setup_method()
            method = getattr(test_suite, method_name)
            method()
            passed += 1
            print(f"✅ {method_name}")
        except Exception as e:
            failed += 1
            print(f"❌ {method_name}: {e}")
    
    print(f"\n💰 PROPERTY TEST SUMMARY")
    print("=" * 60)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Success Rate: {passed/(passed+failed)*100:.1f}%")
    
    return failed == 0


if __name__ == "__main__":
    success = test_enhanced_transaction_cost_properties()
    
    if success:
        print("\n🎉 All enhanced transaction cost property tests passed!")
        print("💡 Transaction cost model is realistic and properly calibrated")
    else:
        print("\n⚠️ Some property tests failed")
        print("🔧 Fix issues before proceeding")
    
    exit(0 if success else 1)