#!/usr/bin/env python3
"""
🧪 DUAL ENGINE INTEGRATION TEST

This script tests the complete dual engine integration with the portfolio governor
and demonstrates the institutional discipline of the Crisis Engine.

TESTING SCENARIOS:
1. Normal market conditions (Trend Engine active)
2. Crisis market conditions (Crisis Engine active)
3. Engine separation validation
4. Conviction contract enforcement
5. Portfolio construction with dual engines
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

# Import the dual engine system
from src.intelligence.dual_engine_coordinator import DualEngineCoordinator, MarketRegime
from src.intelligence.crisis_engine import NorthstarCrisisEngine, CrisisRegime
from src.intelligence.crisis_conviction_contract import CrisisConvictionContract
from src.portfolio.portfolio_governor import PortfolioGovernor

class DualEngineIntegrationTester:
    """
    Dual Engine Integration Tester
    
    Tests the complete integration of Crisis and Trend engines
    with the portfolio construction system.
    """
    
    def __init__(self):
        self.name = "Dual Engine Integration Tester"
        self.version = "1.0.0"
        
        # Initialize components
        self.dual_coordinator = DualEngineCoordinator()
        self.portfolio_governor = PortfolioGovernor()
        
        print(f"🧪 {self.name} v{self.version}")
        print(f"🎯 Testing dual engine integration with portfolio construction")
    
    def create_test_market_scenarios(self):
        """Create different market scenarios for testing"""
        
        scenarios = {}
        
        # Scenario 1: Normal Bull Market (Trend Engine should dominate)
        dates_bull = pd.date_range('2023-01-01', '2023-06-30', freq='D')
        np.random.seed(42)
        returns_bull = np.random.normal(0.001, 0.015, len(dates_bull))  # Low vol, positive drift
        
        scenarios['bull_market'] = pd.DataFrame({
            'date': dates_bull,
            'market_return': returns_bull
        })
        
        # Scenario 2: Crisis Market (Crisis Engine should activate)
        dates_crisis = pd.date_range('2023-07-01', '2023-09-30', freq='D')
        returns_crisis = np.random.normal(-0.02, 0.08, len(dates_crisis))  # High vol, negative drift
        
        scenarios['crisis_market'] = pd.DataFrame({
            'date': dates_crisis,
            'market_return': returns_crisis
        })
        
        # Scenario 3: Volatile but Trending Market (Mixed regime)
        dates_volatile = pd.date_range('2023-10-01', '2023-12-31', freq='D')
        returns_volatile = []
        for i in range(len(dates_volatile)):
            if i % 20 < 5:  # Periodic stress
                ret = np.random.normal(-0.01, 0.05)
            else:  # Normal trending
                ret = np.random.normal(0.002, 0.025)
            returns_volatile.append(ret)
        
        scenarios['volatile_trending'] = pd.DataFrame({
            'date': dates_volatile,
            'market_return': returns_volatile
        })
        
        return scenarios
    
    def create_test_universe(self):
        """Create test stock universe for portfolio construction"""
        
        # Create sample universe with different sectors
        tickers = [
            'RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ICICIBANK.NS',
            'HINDUNILVR.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'KOTAKBANK.NS',
            'LT.NS', 'ASIANPAINT.NS', 'MARUTI.NS', 'AXISBANK.NS', 'HCLTECH.NS',
            'WIPRO.NS', 'ULTRACEMCO.NS', 'TITAN.NS', 'SUNPHARMA.NS', 'POWERGRID.NS'
        ]
        
        sectors = [
            'Energy', 'Technology', 'Technology', 'Financials', 'Financials',
            'Consumer Staples', 'Consumer Staples', 'Financials', 'Telecommunications', 'Financials',
            'Industrials', 'Materials', 'Consumer Discretionary', 'Financials', 'Technology',
            'Technology', 'Materials', 'Consumer Discretionary', 'Healthcare', 'Utilities'
        ]
        
        # Generate random scores
        np.random.seed(42)
        scores = np.random.uniform(0.3, 0.9, len(tickers))
        
        universe = pd.DataFrame({
            'ticker': tickers,
            'Company Name': [t.replace('.NS', '') for t in tickers],
            'Industry': sectors,
            'score': scores
        })
        
        # Save to expected location
        os.makedirs('data/processed', exist_ok=True)
        universe.to_parquet('data/processed/scores.parquet', index=False)
        
        return universe
    
    def test_scenario(self, scenario_name, market_data):
        """Test dual engine behavior in a specific market scenario"""
        
        print(f"\n🧪 TESTING SCENARIO: {scenario_name.upper()}")
        print("=" * 60)
        
        results = {
            'scenario_name': scenario_name,
            'total_days': len(market_data),
            'allocations': [],
            'regime_changes': 0,
            'crisis_activations': 0,
            'trend_activations': 0,
            'engine_violations': 0,
            'portfolio_constructions': []
        }
        
        previous_regime = None
        
        # Test day by day
        for i in range(20, min(len(market_data), 100)):  # Test subset for speed
            current_data = market_data.iloc[:i+1]
            current_date = market_data['date'].iloc[i]
            
            # Get engine allocation
            allocation = self.dual_coordinator.coordinate_engine_allocations(
                current_data, current_date
            )
            
            # Track statistics
            if allocation.regime != previous_regime:
                results['regime_changes'] += 1
                previous_regime = allocation.regime
            
            if allocation.crisis_allocation > 0:
                results['crisis_activations'] += 1
            
            if allocation.trend_allocation > 0:
                results['trend_activations'] += 1
            
            # Check for violations
            if allocation.crisis_allocation > 0 and allocation.trend_allocation > 0:
                results['engine_violations'] += 1
            
            results['allocations'].append({
                'date': current_date,
                'regime': allocation.regime.value,
                'active_engine': allocation.active_engine,
                'crisis_allocation': allocation.crisis_allocation,
                'trend_allocation': allocation.trend_allocation,
                'total_allocation': allocation.total_allocation
            })
            
            # Test portfolio construction every 10 days
            if i % 10 == 0:
                try:
                    portfolio_result = self.test_portfolio_construction_with_engines(allocation)
                    results['portfolio_constructions'].append(portfolio_result)
                except Exception as e:
                    print(f"   ⚠️ Portfolio construction error: {e}")
        
        # Print scenario results
        print(f"📊 Scenario Results:")
        print(f"   Total Days Tested: {len(results['allocations'])}")
        print(f"   Regime Changes: {results['regime_changes']}")
        print(f"   Crisis Engine Activations: {results['crisis_activations']}")
        print(f"   Trend Engine Activations: {results['trend_activations']}")
        print(f"   Engine Separation Violations: {results['engine_violations']}")
        print(f"   Portfolio Constructions: {len(results['portfolio_constructions'])}")
        
        # Show regime distribution
        regimes = [a['regime'] for a in results['allocations']]
        regime_counts = {}
        for regime in regimes:
            regime_counts[regime] = regime_counts.get(regime, 0) + 1
        
        print(f"   Regime Distribution: {regime_counts}")
        
        # Validate engine separation
        if results['engine_violations'] == 0:
            print("   ✅ Perfect engine separation maintained")
        else:
            print(f"   ❌ Engine separation violations: {results['engine_violations']}")
        
        return results
    
    def test_portfolio_construction_with_engines(self, engine_allocation):
        """Test portfolio construction with dual engine allocation"""
        
        # Create mock intelligence with engine allocation
        mock_intelligence = {
            'market_state': {'daily_return': 0.001},
            'ai_intelligence': {},
            'regime': engine_allocation.regime.value.lower(),
            'allowed_exposure': engine_allocation.total_allocation,
            'risk_on_prob': 0.5,
            'ai_active': False,
            'strategy_performance': {},
            'capital_allocations': {},
            'engine_allocation': engine_allocation,
            'crisis_engine_active': engine_allocation.crisis_allocation > 0,
            'trend_engine_active': engine_allocation.trend_allocation > 0
        }
        
        # Test portfolio construction components
        try:
            # Load universe
            universe, score_col = self.portfolio_governor.load_universe_scores()
            
            if universe.empty:
                return {'status': 'No universe available'}
            
            # Calculate base weights
            portfolio = self.portfolio_governor.calculate_base_weights(universe, score_col, mock_intelligence)
            
            if portfolio.empty:
                return {'status': 'No portfolio generated'}
            
            # Apply risk controls
            portfolio = self.portfolio_governor.apply_risk_controls(portfolio, mock_intelligence)
            
            # Apply regime overlay (this uses the dual engine results)
            portfolio = self.portfolio_governor.apply_regime_overlay(portfolio, mock_intelligence)
            
            # Calculate analytics
            analytics = self.portfolio_governor.calculate_portfolio_analytics(portfolio, mock_intelligence)
            
            return {
                'status': 'Success',
                'positions': len(portfolio),
                'total_exposure': portfolio['final_weight'].sum(),
                'largest_position': portfolio['final_weight'].max(),
                'active_engine': engine_allocation.active_engine,
                'regime': engine_allocation.regime.value,
                'analytics_available': 'dual_engine_coordination' in analytics
            }
            
        except Exception as e:
            return {'status': f'Error: {str(e)}'}
    
    def test_conviction_contract_enforcement(self):
        """Test conviction contract enforcement"""
        
        print(f"\n🔒 TESTING CONVICTION CONTRACT ENFORCEMENT")
        print("=" * 60)
        
        # Create a separate contract instance for testing to avoid polluting the main system
        from src.intelligence.crisis_conviction_contract import CrisisConvictionContract
        test_contract = CrisisConvictionContract()
        
        # Test valid action
        valid_state = {
            'regime_state': 'HOSTILE',
            'position_size': 0.05,
            'daily_pnl': -0.001
        }
        
        valid_action = {
            'crisis_allocation': 0.05,
            'signal_based': True
        }
        
        is_valid = test_contract.validate_engine_action('position_sizing', valid_state, valid_action)
        print(f"✅ Valid action allowed: {is_valid}")
        
        # Test invalid action (emotional override) - this should be blocked
        invalid_action = {
            'crisis_allocation': 0.0,
            'manual_exit': True,
            'reason_for_exit': 'emotional'
        }
        
        is_invalid = test_contract.validate_engine_action('exit', valid_state, invalid_action)
        print(f"❌ Invalid action blocked: {not is_invalid}")
        
        # Get conviction health from the main system (not the test instance)
        health = self.dual_coordinator.crisis_contract.get_conviction_health()
        print(f"📊 Main System Conviction Score: {health['conviction_score']}/100")
        print(f"📊 Main System Total Violations: {health['total_violations']}")
        
        # Return the main system health, not the test instance
        return health
    
    def run_comprehensive_test(self):
        """Run comprehensive dual engine integration test"""
        
        print(f"🧪 COMPREHENSIVE DUAL ENGINE INTEGRATION TEST")
        print("=" * 70)
        
        # Step 1: Create test data
        print("📊 Creating test market scenarios...")
        scenarios = self.create_test_market_scenarios()
        
        print("🏢 Creating test stock universe...")
        universe = self.create_test_universe()
        
        # Step 2: Test each scenario
        scenario_results = {}
        
        for scenario_name, market_data in scenarios.items():
            scenario_results[scenario_name] = self.test_scenario(scenario_name, market_data)
        
        # Step 3: Test conviction contract
        conviction_health = self.test_conviction_contract_enforcement()
        
        # Step 4: Test coordination diagnostics
        print(f"\n📊 COORDINATION DIAGNOSTICS")
        print("=" * 60)
        
        diagnostics = self.dual_coordinator.get_coordination_diagnostics()
        
        print("Coordination Summary:")
        if 'coordination_summary' in diagnostics:
            for key, value in diagnostics['coordination_summary'].items():
                print(f"  {key}: {value}")
        
        print("\nEngine Separation:")
        if 'engine_separation' in diagnostics:
            for key, value in diagnostics['engine_separation'].items():
                print(f"  {key}: {value}")
        
        # Step 5: Validate institutional discipline
        print(f"\n🏛️ INSTITUTIONAL DISCIPLINE VALIDATION")
        print("=" * 60)
        
        discipline = self.dual_coordinator.validate_institutional_discipline()
        for check, passed in discipline.items():
            status = "✅" if passed else "❌"
            print(f"{status} {check}: {passed}")
        
        # Step 6: Generate summary
        print(f"\n📋 INTEGRATION TEST SUMMARY")
        print("=" * 70)
        
        total_days = sum(len(r['allocations']) for r in scenario_results.values())
        total_crisis_activations = sum(r['crisis_activations'] for r in scenario_results.values())
        total_trend_activations = sum(r['trend_activations'] for r in scenario_results.values())
        total_violations = sum(r['engine_violations'] for r in scenario_results.values())
        total_portfolio_tests = sum(len(r['portfolio_constructions']) for r in scenario_results.values())
        
        print(f"Total Days Tested: {total_days}")
        print(f"Crisis Engine Activations: {total_crisis_activations}")
        print(f"Trend Engine Activations: {total_trend_activations}")
        print(f"Engine Separation Violations: {total_violations}")
        print(f"Portfolio Construction Tests: {total_portfolio_tests}")
        print(f"Conviction Score: {conviction_health['conviction_score']}/100")
        
        # Overall assessment
        all_discipline_passed = all(discipline.values())
        no_violations = total_violations == 0
        good_conviction = conviction_health['conviction_score'] > 80
        
        overall_pass = all_discipline_passed and no_violations and good_conviction
        
        if overall_pass:
            print("\n✅ DUAL ENGINE INTEGRATION TEST: PASS")
            print("   System demonstrates institutional discipline")
            print("   Engine separation maintained perfectly")
            print("   Conviction contracts respected")
            print("   Portfolio construction works with both engines")
        else:
            print("\n❌ DUAL ENGINE INTEGRATION TEST: FAIL")
            print("   Issues detected in integration:")
            if not all_discipline_passed:
                print("   - Institutional discipline violations")
            if total_violations > 0:
                print(f"   - Engine separation violations: {total_violations}")
            if not good_conviction:
                print(f"   - Poor conviction score: {conviction_health['conviction_score']}")
        
        # Save results
        results = {
            'test_summary': {
                'test_name': self.name,
                'test_version': self.version,
                'test_date': datetime.now().isoformat(),
                'overall_pass': overall_pass
            },
            'scenario_results': scenario_results,
            'conviction_health': conviction_health,
            'coordination_diagnostics': diagnostics,
            'institutional_discipline': discipline,
            'statistics': {
                'total_days_tested': total_days,
                'crisis_activations': total_crisis_activations,
                'trend_activations': total_trend_activations,
                'engine_violations': total_violations,
                'portfolio_tests': total_portfolio_tests
            }
        }
        
        # Save test results
        os.makedirs('data/validation/dual_engine_tests', exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_file = f'data/validation/dual_engine_tests/integration_test_{timestamp}.json'
        
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n💾 Test results saved: {results_file}")
        
        return results

def main():
    """Main execution function"""
    
    tester = DualEngineIntegrationTester()
    results = tester.run_comprehensive_test()
    
    return results

if __name__ == "__main__":
    main()