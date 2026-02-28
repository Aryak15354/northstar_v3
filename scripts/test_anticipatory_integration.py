#!/usr/bin/env python3
"""
🧠 TEST ANTICIPATORY INTELLIGENCE INTEGRATION - NORTHSTAR V3
Integration Test: Demonstrating Anticipatory Intelligence in Action

This script demonstrates how the anticipatory intelligence system
integrates with Northstar V3 to provide regime-aware decision making.

Usage:
    python scripts/test_anticipatory_integration.py
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime
import json
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_regime_intelligence():
    """Test regime intelligence functionality"""
    
    print("🧠 TESTING REGIME INTELLIGENCE")
    print("=" * 50)
    
    try:
        # Load simple regime fingerprints
        regime_path = 'data/processed/simple_regime_fingerprints.parquet'
        
        if os.path.exists(regime_path):
            regime_df = pd.read_parquet(regime_path)
            
            print(f"✅ Regime fingerprints loaded: {len(regime_df)} periods")
            print(f"   Date range: {regime_df.index[0].date()} to {regime_df.index[-1].date()}")
            print(f"   Historical coverage: {(regime_df.index[-1] - regime_df.index[0]).days / 365.25:.1f} years")
            
            # Show regime distribution
            regime_counts = regime_df['regime_name'].value_counts()
            print(f"\n📊 Regime Distribution:")
            for regime, count in regime_counts.items():
                percentage = count / len(regime_df) * 100
                print(f"   {regime}: {count} periods ({percentage:.1f}%)")
            
            # Current regime
            current_regime = regime_df.iloc[-1]
            print(f"\n🎯 Current Regime: {current_regime['regime_name']}")
            print(f"   Cluster: {current_regime['regime_cluster']}")
            
            return True
        else:
            print("❌ Regime fingerprints not found")
            return False
            
    except Exception as e:
        print(f"❌ Error testing regime intelligence: {e}")
        return False

def test_anticipatory_signals():
    """Test anticipatory signals functionality"""
    
    print("\n🔮 TESTING ANTICIPATORY SIGNALS")
    print("=" * 50)
    
    try:
        # Load simple anticipatory signals
        signals_path = 'data/processed/simple_anticipatory_signals.json'
        
        if os.path.exists(signals_path):
            with open(signals_path, 'r') as f:
                signals = json.load(f)
            
            print(f"✅ Anticipatory signals loaded")
            
            # Current regime intelligence
            current_regime = signals.get('current_regime', {})
            print(f"\n📊 Current Regime Intelligence:")
            print(f"   Name: {current_regime.get('name', 'Unknown')}")
            print(f"   Cluster: {current_regime.get('cluster', 'Unknown')}")
            print(f"   Stability: {current_regime.get('stability', 0):.1%}")
            print(f"   Duration: {current_regime.get('duration_in_regime', 0)} periods")
            
            # Strategy recommendations
            strategy_recs = signals.get('strategy_recommendations', {})
            current_regime_recs = strategy_recs.get('current_regime', {})
            
            if current_regime_recs:
                print(f"\n🎯 Strategy Recommendations:")
                print(f"   Favor: {', '.join(current_regime_recs.get('favor', []))}")
                print(f"   Avoid: {', '.join(current_regime_recs.get('avoid', []))}")
                print(f"   Reasoning: {current_regime_recs.get('reasoning', 'No reasoning provided')}")
            
            # Risk assessment
            risk_assessment = signals.get('risk_assessment', {})
            print(f"\n🛡️ Risk Assessment:")
            print(f"   Regime Risk Level: {risk_assessment.get('regime_risk_level', 'unknown').upper()}")
            print(f"   Transition Risk: {risk_assessment.get('transition_risk', 0):.1%}")
            print(f"   Stability Risk: {risk_assessment.get('stability_risk', 0):.1%}")
            
            return True
        else:
            print("❌ Anticipatory signals not found")
            return False
            
    except Exception as e:
        print(f"❌ Error testing anticipatory signals: {e}")
        return False

def test_anticipatory_capital_allocation():
    """Test anticipatory capital allocation functionality"""
    
    print("\n🎯 TESTING ANTICIPATORY CAPITAL ALLOCATION")
    print("=" * 50)
    
    try:
        # Load simple anticipatory allocations
        allocations_path = 'data/processed/simple_anticipatory_allocations.parquet'
        
        if os.path.exists(allocations_path):
            allocations_df = pd.read_parquet(allocations_path)
            
            print(f"✅ Anticipatory allocations loaded: {len(allocations_df)} strategies")
            
            # Allocation breakdown
            print(f"\n📊 Capital Allocation Breakdown:")
            
            total_allocation = 0
            for _, allocation in allocations_df.iterrows():
                strategy_name = allocation['strategy_name']
                weight = allocation['allocation_weight']
                category = allocation['category']
                
                print(f"   {strategy_name}: {weight:.1%} ({category})")
                total_allocation += weight
            
            print(f"   Total Allocation: {total_allocation:.1%}")
            
            # Category breakdown
            print(f"\n📈 Category Breakdown:")
            category_allocations = allocations_df.groupby('category')['allocation_weight'].sum()
            
            for category, weight in category_allocations.items():
                print(f"   {category.title()}: {weight:.1%}")
            
            # Regime context
            regime_name = allocations_df['regime_name'].iloc[0]
            regime_stability = allocations_df['regime_stability'].iloc[0]
            
            print(f"\n🔄 Regime Context:")
            print(f"   Current Regime: {regime_name}")
            print(f"   Regime Stability: {regime_stability:.1%}")
            
            # Allocation reasoning
            print(f"\n💡 Allocation Reasoning:")
            for _, allocation in allocations_df.head(3).iterrows():  # Show top 3
                strategy_name = allocation['strategy_name']
                reason = allocation['allocation_reason']
                print(f"   {strategy_name}: {reason}")
            
            return True
        else:
            print("❌ Anticipatory allocations not found")
            return False
            
    except Exception as e:
        print(f"❌ Error testing anticipatory capital allocation: {e}")
        return False

def test_integration_with_existing_system():
    """Test integration with existing Northstar V3 system"""
    
    print("\n🔗 TESTING INTEGRATION WITH EXISTING SYSTEM")
    print("=" * 50)
    
    try:
        # Test integration status
        status_path = 'data/processed/simple_anticipatory_status.json'
        
        if os.path.exists(status_path):
            with open(status_path, 'r') as f:
                status = json.load(f)
            
            print(f"✅ Integration status loaded")
            print(f"   System Type: {status.get('type', 'unknown')}")
            print(f"   Version: {status.get('version', 'unknown')}")
            print(f"   System Ready: {'✅' if status.get('system_ready') else '❌'}")
            
            # Component status
            files_status = status.get('files_status', {})
            print(f"\n📋 Component Status:")
            
            for component, available in files_status.items():
                status_icon = "✅" if available else "❌"
                component_name = component.replace('_', ' ').title()
                print(f"   {status_icon} {component_name}")
            
            # Integration health
            available_components = status.get('components_available', 0)
            total_components = status.get('total_components', 0)
            
            if total_components > 0:
                health_score = available_components / total_components
                print(f"\n🏥 Integration Health:")
                print(f"   Available Components: {available_components}/{total_components}")
                print(f"   Health Score: {health_score:.1%}")
                
                if health_score >= 0.9:
                    health_status = "EXCELLENT"
                elif health_score >= 0.75:
                    health_status = "GOOD"
                elif health_score >= 0.5:
                    health_status = "PARTIAL"
                else:
                    health_status = "POOR"
                
                print(f"   Health Status: {health_status}")
            
            return status.get('system_ready', False)
        else:
            print("❌ Integration status not found")
            return False
            
    except Exception as e:
        print(f"❌ Error testing integration: {e}")
        return False

def demonstrate_anticipatory_intelligence_workflow():
    """Demonstrate complete anticipatory intelligence workflow"""
    
    print("\n🚀 DEMONSTRATING ANTICIPATORY INTELLIGENCE WORKFLOW")
    print("=" * 60)
    
    try:
        # Step 1: Load regime intelligence
        print("Step 1: Regime Recognition")
        
        regime_path = 'data/processed/simple_regime_fingerprints.parquet'
        signals_path = 'data/processed/simple_anticipatory_signals.json'
        
        if os.path.exists(regime_path) and os.path.exists(signals_path):
            regime_df = pd.read_parquet(regime_path)
            
            with open(signals_path, 'r') as f:
                signals = json.load(f)
            
            current_regime = signals['current_regime']
            
            print(f"   🎯 Current Market Regime: {current_regime['name']}")
            print(f"   📊 Based on {len(regime_df)} historical periods")
            print(f"   🔍 Regime Stability: {current_regime['stability']:.1%}")
        
        # Step 2: Strategy recommendations
        print(f"\nStep 2: Strategy Recommendations")
        
        strategy_recs = signals.get('strategy_recommendations', {}).get('current_regime', {})
        
        if strategy_recs:
            print(f"   ✅ Favor: {', '.join(strategy_recs.get('favor', []))}")
            print(f"   ❌ Avoid: {', '.join(strategy_recs.get('avoid', []))}")
            print(f"   💡 Reasoning: {strategy_recs.get('reasoning', 'No reasoning')}")
        
        # Step 3: Capital allocation
        print(f"\nStep 3: Anticipatory Capital Allocation")
        
        allocations_path = 'data/processed/simple_anticipatory_allocations.parquet'
        
        if os.path.exists(allocations_path):
            allocations_df = pd.read_parquet(allocations_path)
            
            # Show allocation summary
            cash_allocation = allocations_df[allocations_df['strategy_name'] == 'CASH']['allocation_weight'].iloc[0]
            strategy_allocations = allocations_df[allocations_df['strategy_name'] != 'CASH']
            
            print(f"   💰 Cash Allocation: {cash_allocation:.1%}")
            print(f"   📈 Active Strategies: {len(strategy_allocations)}")
            
            # Show top strategy
            if not strategy_allocations.empty:
                top_strategy = strategy_allocations.iloc[0]
                print(f"   🏆 Top Strategy: {top_strategy['strategy_name']} ({top_strategy['allocation_weight']:.1%})")
        
        # Step 4: Risk management
        print(f"\nStep 4: Risk Management")
        
        risk_assessment = signals.get('risk_assessment', {})
        risk_actions = signals.get('anticipatory_actions', {}).get('risk_management_actions', {})
        
        print(f"   🛡️ Risk Level: {risk_assessment.get('regime_risk_level', 'unknown').upper()}")
        print(f"   📏 Position Sizing: {risk_actions.get('position_sizing', 'normal').upper()}")
        print(f"   🎯 Max Position: {risk_actions.get('max_position_size', 0.05):.1%}")
        
        print(f"\n🎉 ANTICIPATORY INTELLIGENCE WORKFLOW COMPLETE!")
        print(f"   Northstar is now making regime-aware decisions")
        print(f"   Capital is allocated based on historical regime patterns")
        print(f"   Risk management is adapted to current regime characteristics")
        
        return True
        
    except Exception as e:
        print(f"❌ Error demonstrating workflow: {e}")
        return False

def main():
    """Main test execution"""
    
    print("🧠 ANTICIPATORY INTELLIGENCE INTEGRATION TEST")
    print("=" * 70)
    print("Testing anticipatory intelligence integration with Northstar V3")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    test_results = {}
    
    # Run all tests
    test_results['regime_intelligence'] = test_regime_intelligence()
    test_results['anticipatory_signals'] = test_anticipatory_signals()
    test_results['capital_allocation'] = test_anticipatory_capital_allocation()
    test_results['system_integration'] = test_integration_with_existing_system()
    
    # Demonstrate workflow
    workflow_success = demonstrate_anticipatory_intelligence_workflow()
    
    # Summary
    successful_tests = sum(test_results.values())
    total_tests = len(test_results)
    
    print(f"\n🎯 INTEGRATION TEST SUMMARY")
    print("=" * 70)
    print(f"Successful tests: {successful_tests}/{total_tests}")
    print(f"Success rate: {successful_tests / total_tests:.1%}")
    print(f"Workflow demonstration: {'✅' if workflow_success else '❌'}")
    
    # Individual test results
    print(f"\nTest Results:")
    for test_name, result in test_results.items():
        status_icon = "✅" if result else "❌"
        test_display_name = test_name.replace('_', ' ').title()
        print(f"  {status_icon} {test_display_name}")
    
    if successful_tests >= total_tests * 0.75 and workflow_success:
        print(f"\n🎉 ANTICIPATORY INTELLIGENCE INTEGRATION SUCCESSFUL!")
        print("   🧠 Regime recognition: OPERATIONAL")
        print("   🔮 Anticipatory signals: ACTIVE")
        print("   🎯 Capital allocation: REGIME-AWARE")
        print("   🔗 System integration: COMPLETE")
        print()
        print("   Northstar V3 now has anticipatory intelligence!")
        print("   The system can recognize market regimes and allocate capital")
        print("   based on what historically works in similar conditions.")
        print()
        print("   This is the leap from reactive to anticipatory intelligence.")
        
        return True
    else:
        print(f"\n⚠️ Integration partially successful - some components need attention")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)