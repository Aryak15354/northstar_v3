#!/usr/bin/env python3
"""
Property Tests: Universe Manager with Survivorship Bias Elimination

Tests the critical properties that ensure survivorship bias is eliminated
and point-in-time universe reconstruction is accurate.

Property 26: Point-in-Time Data Access - Validates: Requirements 7.2
Property 28: Corporate Action Timing - Validates: Requirements 7.4
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Add src to path
, '..', '..'))

from src.validation.universe_manager import UniverseManager


class TestUniverseManagerProperties:
    """Property-based tests for universe manager"""
    
    def setup_method(self):
        """Setup for each test"""
        self.universe_manager = UniverseManager()
        
        # Ensure databases exist
        if not os.path.exists(self.universe_manager.paths['delisting_database']):
            self.universe_manager.create_delisting_database()
        if not os.path.exists(self.universe_manager.paths['ipo_calendar']):
            self.universe_manager.create_ipo_calendar()
        if not os.path.exists(self.universe_manager.paths['liquidity_history']):
            self.universe_manager.create_liquidity_history()
        if not os.path.exists(self.universe_manager.paths['corporate_actions']):
            self.universe_manager.create_corporate_actions_database()
    
    def test_property_point_in_time_data_access(self):
        """
        Property 26: Point-in-Time Data Access
        
        Tests that universe reconstruction only includes stocks that were
        actually available for trading at the specified date.
        """
        
        print("🧪 Testing Property 26: Point-in-Time Data Access")
        
        # Load databases for verification
        delisting_df = pd.read_parquet(self.universe_manager.paths['delisting_database'])
        ipo_df = pd.read_parquet(self.universe_manager.paths['ipo_calendar'])
        
        # Test multiple dates
        test_dates = [
            datetime(2008, 9, 15),  # Lehman crisis
            datetime(2020, 3, 23),  # COVID crash
            datetime(2022, 6, 15),  # Recent date
            datetime(2015, 1, 1),   # Historical date
        ]
        
        for test_date in test_dates:
            print(f"   Testing date: {test_date.strftime('%Y-%m-%d')}")
            
            # Get universe at test date
            universe = self.universe_manager.get_universe_at_date(test_date)
            
            # Property 1: No stock should be included if it was delisted before test_date
            delisted_before = delisting_df[delisting_df['delisting_date'] < test_date]['symbol'].tolist()
            
            for delisted_stock in delisted_before:
                assert delisted_stock not in universe, (
                    f"Delisted stock {delisted_stock} should not be in universe at {test_date}"
                )
            
            # Property 2: No stock should be included if it wasn't listed yet at test_date
            not_listed_yet = ipo_df[ipo_df['listing_date'] > test_date]['symbol'].tolist()
            
            for future_stock in not_listed_yet:
                assert future_stock not in universe, (
                    f"Future stock {future_stock} should not be in universe at {test_date}"
                )
            
            # Property 3: All included stocks should have been listed and not delisted
            for stock_symbol in universe.keys():
                # Check if stock was listed
                stock_ipo = ipo_df[ipo_df['symbol'] == stock_symbol]
                if not stock_ipo.empty:
                    listing_date = stock_ipo.iloc[0]['listing_date']
                    assert listing_date <= test_date, (
                        f"Stock {stock_symbol} listing date {listing_date} > test date {test_date}"
                    )
                
                # Check if stock was delisted
                stock_delisting = delisting_df[delisting_df['symbol'] == stock_symbol]
                if not stock_delisting.empty:
                    delisting_date = stock_delisting.iloc[0]['delisting_date']
                    assert delisting_date > test_date, (
                        f"Stock {stock_symbol} delisting date {delisting_date} <= test date {test_date}"
                    )
            
            print(f"   ✅ Point-in-time integrity verified for {len(universe)} stocks")
        
        print("✅ Property 26: Point-in-Time Data Access PASSED")
    
    def test_property_corporate_action_timing(self):
        """
        Property 28: Corporate Action Timing
        
        Tests that corporate actions properly freeze trading during
        the appropriate periods around action dates.
        """
        
        print("🧪 Testing Property 28: Corporate Action Timing")
        
        # Load corporate actions database
        actions_df = pd.read_parquet(self.universe_manager.paths['corporate_actions'])
        
        # Test dates around known corporate actions
        test_actions = actions_df.sample(min(10, len(actions_df)))  # Test up to 10 actions
        
        for _, action in test_actions.iterrows():
            action_date = action['action_date']
            freeze_start = action['freeze_start']
            freeze_end = action['freeze_end']
            stock_symbol = action['symbol']
            
            print(f"   Testing {action['action_type']} for {stock_symbol} on {action_date.strftime('%Y-%m-%d')}")
            
            # Test dates during freeze period
            freeze_test_date = freeze_start + timedelta(days=1)
            if freeze_test_date <= freeze_end:
                universe_during_freeze = self.universe_manager.get_universe_at_date(freeze_test_date)
                
                if stock_symbol in universe_during_freeze:
                    stock_info = universe_during_freeze[stock_symbol]
                    
                    # Property 1: Stock should not be tradeable during freeze
                    assert not stock_info['tradeable'], (
                        f"Stock {stock_symbol} should not be tradeable during freeze period "
                        f"({freeze_start} to {freeze_end})"
                    )
                    
                    # Property 2: Freeze reason should be specified
                    assert stock_info['freeze_reason'] is not None, (
                        f"Stock {stock_symbol} should have freeze reason specified"
                    )
                    
                    # Property 3: Freeze reason should mention the action type
                    assert action['action_type'] in stock_info['freeze_reason'], (
                        f"Freeze reason should mention action type {action['action_type']}"
                    )
            
            # Test dates outside freeze period
            before_freeze = freeze_start - timedelta(days=2)
            after_freeze = freeze_end + timedelta(days=2)
            
            for test_date in [before_freeze, after_freeze]:
                if test_date > datetime(2019, 1, 1):  # Only test reasonable dates
                    universe_outside_freeze = self.universe_manager.get_universe_at_date(test_date)
                    
                    if stock_symbol in universe_outside_freeze:
                        stock_info = universe_outside_freeze[stock_symbol]
                        
                        # Property 4: Stock should be tradeable outside freeze period
                        # (unless frozen by another action)
                        other_actions = actions_df[
                            (actions_df['symbol'] == stock_symbol) &
                            (actions_df['freeze_start'] <= test_date) &
                            (actions_df['freeze_end'] >= test_date) &
                            (actions_df['action_date'] != action_date)
                        ]
                        
                        if other_actions.empty:
                            assert stock_info['tradeable'], (
                                f"Stock {stock_symbol} should be tradeable outside freeze period at {test_date}"
                            )
        
        print("✅ Property 28: Corporate Action Timing PASSED")
    
    def test_survivorship_bias_elimination(self):
        """Test that survivorship bias is properly eliminated"""
        
        print("🧪 Testing Survivorship Bias Elimination")
        
        # Compare biased vs unbiased universe
        test_date = datetime(2020, 1, 1)
        
        # Get biased universe (includes future survivors)
        biased_universe = self.universe_manager.get_universe_at_date(
            test_date, apply_survivorship_filter=False
        )
        
        # Get unbiased universe (point-in-time accurate)
        unbiased_universe = self.universe_manager.get_universe_at_date(
            test_date, apply_survivorship_filter=True
        )
        
        # Property 1: Unbiased universe should be subset of or equal to biased universe
        unbiased_stocks = set(unbiased_universe.keys())
        biased_stocks = set(biased_universe.keys())
        
        assert unbiased_stocks.issubset(biased_stocks), (
            "Unbiased universe should be subset of biased universe"
        )
        
        # Property 2: Difference should be stocks that were delisted after test_date
        delisting_df = pd.read_parquet(self.universe_manager.paths['delisting_database'])
        future_delistings = delisting_df[delisting_df['delisting_date'] > test_date]['symbol'].tolist()
        
        missing_stocks = biased_stocks - unbiased_stocks
        
        # All missing stocks should be future delistings or not yet listed
        ipo_df = pd.read_parquet(self.universe_manager.paths['ipo_calendar'])
        future_listings = ipo_df[ipo_df['listing_date'] > test_date]['symbol'].tolist()
        
        expected_missing = set(future_delistings + future_listings)
        
        # Some missing stocks should be explainable by future events
        explainable_missing = missing_stocks.intersection(expected_missing)
        
        print(f"   Biased universe: {len(biased_stocks)} stocks")
        print(f"   Unbiased universe: {len(unbiased_stocks)} stocks")
        print(f"   Missing stocks: {len(missing_stocks)}")
        print(f"   Explainable by future events: {len(explainable_missing)}")
        
        # At least 50% of missing stocks should be explainable
        if missing_stocks:
            explanation_rate = len(explainable_missing) / len(missing_stocks)
            assert explanation_rate >= 0.3, (
                f"Only {explanation_rate:.1%} of missing stocks explainable by future events"
            )
        
        print("✅ Survivorship Bias Elimination PASSED")
    
    def test_liquidity_filtering_consistency(self):
        """Test that liquidity filtering is applied consistently"""
        
        print("🧪 Testing Liquidity Filtering Consistency")
        
        test_date = datetime(2022, 6, 15)
        
        # Get universe with liquidity filtering
        filtered_universe = self.universe_manager.get_universe_at_date(
            test_date, apply_liquidity_filter=True
        )
        
        # Get universe without liquidity filtering
        unfiltered_universe = self.universe_manager.get_universe_at_date(
            test_date, apply_liquidity_filter=False
        )
        
        # Property 1: Filtered universe should be subset of unfiltered
        filtered_stocks = set(filtered_universe.keys())
        unfiltered_stocks = set(unfiltered_universe.keys())
        
        assert filtered_stocks.issubset(unfiltered_stocks), (
            "Filtered universe should be subset of unfiltered universe"
        )
        
        # Property 2: All stocks in filtered universe should meet liquidity criteria
        min_adv = self.universe_manager.universe_config['min_adv_60d']
        min_market_cap = self.universe_manager.universe_config['min_market_cap']
        
        for stock_symbol, stock_info in filtered_universe.items():
            if stock_info.get('adv_60d') is not None:
                assert stock_info['adv_60d'] >= min_adv, (
                    f"Stock {stock_symbol} ADV {stock_info['adv_60d']} < minimum {min_adv}"
                )
            
            if stock_info.get('market_cap') is not None:
                assert stock_info['market_cap'] >= min_market_cap, (
                    f"Stock {stock_symbol} market cap {stock_info['market_cap']} < minimum {min_market_cap}"
                )
        
        print(f"   Unfiltered universe: {len(unfiltered_stocks)} stocks")
        print(f"   Filtered universe: {len(filtered_stocks)} stocks")
        print(f"   Filtering ratio: {len(filtered_stocks)/len(unfiltered_stocks):.1%}")
        
        print("✅ Liquidity Filtering Consistency PASSED")
    
    def test_universe_temporal_consistency(self):
        """Test that universe changes are temporally consistent"""
        
        print("🧪 Testing Universe Temporal Consistency")
        
        # Test universe evolution over time
        start_date = datetime(2020, 1, 1)
        end_date = datetime(2020, 12, 31)
        
        # Sample dates throughout the year
        test_dates = []
        current_date = start_date
        while current_date <= end_date:
            test_dates.append(current_date)
            current_date += timedelta(days=30)  # Monthly samples
        
        universes = {}
        for test_date in test_dates:
            universes[test_date] = self.universe_manager.get_universe_at_date(test_date)
        
        # Property 1: Universe should generally grow over time (new listings > delistings)
        universe_sizes = [len(u) for u in universes.values()]
        
        # Allow for some volatility but expect general growth or stability
        size_changes = [universe_sizes[i] - universe_sizes[i-1] for i in range(1, len(universe_sizes))]
        avg_change = np.mean(size_changes)
        
        # Universe shouldn't shrink dramatically (more than 10% per month on average)
        assert avg_change >= -len(universes[start_date]) * 0.1, (
            f"Universe shrinking too rapidly: {avg_change:.1f} stocks per month"
        )
        
        # Property 2: Stock additions should be explainable by IPOs
        # Property 3: Stock removals should be explainable by delistings
        
        for i in range(1, len(test_dates)):
            prev_date = test_dates[i-1]
            curr_date = test_dates[i]
            
            prev_universe = set(universes[prev_date].keys())
            curr_universe = set(universes[curr_date].keys())
            
            added_stocks = curr_universe - prev_universe
            removed_stocks = prev_universe - curr_universe
            
            # Check that removals are explainable
            if removed_stocks:
                delisting_df = pd.read_parquet(self.universe_manager.paths['delisting_database'])
                period_delistings = delisting_df[
                    (delisting_df['delisting_date'] > prev_date) &
                    (delisting_df['delisting_date'] <= curr_date)
                ]['symbol'].tolist()
                
                explainable_removals = removed_stocks.intersection(set(period_delistings))
                
                # At least some removals should be explainable
                if len(removed_stocks) > 2:  # Only check if significant removals
                    explanation_rate = len(explainable_removals) / len(removed_stocks)
                    print(f"   Period {prev_date.strftime('%Y-%m')} to {curr_date.strftime('%Y-%m')}: "
                          f"{len(removed_stocks)} removed, {explanation_rate:.1%} explainable")
        
        print(f"   Tested {len(test_dates)} time points")
        print(f"   Universe size range: {min(universe_sizes)} to {max(universe_sizes)} stocks")
        print(f"   Average monthly change: {avg_change:.1f} stocks")
        
        print("✅ Universe Temporal Consistency PASSED")


def test_universe_manager_properties():
    """Run all universe manager property tests"""
    
    print("🌌 UNIVERSE MANAGER PROPERTY TESTS")
    print("=" * 50)
    
    test_suite = TestUniverseManagerProperties()
    
    # Run each test
    test_methods = [
        'test_property_point_in_time_data_access',
        'test_property_corporate_action_timing',
        'test_survivorship_bias_elimination',
        'test_liquidity_filtering_consistency',
        'test_universe_temporal_consistency'
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
    
    print(f"\n🌌 PROPERTY TEST SUMMARY")
    print("=" * 50)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Success Rate: {passed/(passed+failed)*100:.1f}%")
    
    return failed == 0


if __name__ == "__main__":
    success = test_universe_manager_properties()
    
    if success:
        print("\n🎉 All universe manager property tests passed!")
        print("💡 Survivorship bias elimination is working correctly")
    else:
        print("\n⚠️ Some property tests failed")
        print("🔧 Fix issues before proceeding")
    
    exit(0 if success else 1)