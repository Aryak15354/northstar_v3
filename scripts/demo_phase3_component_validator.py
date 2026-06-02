#!/usr/bin/env python3
"""
🔍 DEMO: Phase 3 Component Validator - Shadow Reality Phase 4.3
Demonstrates individual Phase 3 component validation across multiple timelines

This script demonstrates the Phase3ComponentValidator functionality
by creating mock data and running component validation across multiple periods.
"""

import pandas as pd
import numpy as np
import os
import tempfile
import shutil
from datetime import datetime
import sys

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def create_demo_data():
    """Create demo historical data for component validation"""
    
    print("📊 Creating demo historical data for component validation...")
    
    # Create comprehensive time series covering all validation periods
    all_dates = pd.date_range(start='2008-01-01', end='2023-12-31', freq='W')
    n_periods = len(all_dates)
    
    print(f"   📅 Date range: {all_dates[0].date()} to {all_dates[-1].date()}")
    print(f"   📈 Total periods: {n_periods}")
    
    # Create realistic regime patterns for different periods
    regimes = []
    macro_scores = []
    stress_levels = []
    
    for date in all_dates:
        year = date.year
        month = date.month
        
        if 2008 <= year <= 2009:
            # Crisis period - mostly Crisis and Slowdown
            regime = np.random.choice(['Crisis', 'Slowdown'], p=[0.7, 0.3])
            macro_score = np.random.normal(-1.5, 0.8)
            stress = np.random.uniform(0.7, 1.0)
        elif 2010 <= year <= 2013:
            # Recovery period - mostly Expansion
            regime = np.random.choice(['Expansion', 'Late-Expansion'], p=[0.8, 0.2])
            macro_score = np.random.normal(1.0, 0.5)
            stress = np.random.uniform(0.1, 0.4)
        elif 2014 <= year <= 2019:
            # Stable expansion - mixed but stable
            regime = np.random.choice(['Expansion', 'Late-Expansion'], p=[0.6, 0.4])
            macro_score = np.random.normal(0.8, 0.4)
            stress = np.random.uniform(0.1, 0.3)
        elif year == 2020 and month <= 6:
            # COVID crisis - Crisis and volatility
            regime = np.random.choice(['Crisis', 'Slowdown'], p=[0.8, 0.2])
            macro_score = np.random.normal(-2.0, 1.0)
            stress = np.random.uniform(0.8, 1.0)
        elif 2021 <= year <= 2022:
            # Inflation period - Late-Expansion and transitions
            regime = np.random.choice(['Late-Expansion', 'Slowdown'], p=[0.6, 0.4])
            macro_score = np.random.normal(0.3, 0.7)
            stress = np.random.uniform(0.3, 0.6)
        else:
            # Current period - mixed conditions
            regime = np.random.choice(['Late-Expansion', 'Expansion', 'Slowdown'], p=[0.5, 0.3, 0.2])
            macro_score = np.random.normal(0.5, 0.6)
            stress = np.random.uniform(0.2, 0.5)
        
        regimes.append(regime)
        macro_scores.append(macro_score)
        stress_levels.append(stress)
    
    # Create macro DataFrame with additional factors
    macro_data = pd.DataFrame({
        'Regime': regimes,
        'MacroScore': macro_scores,
        'Contrib_G': np.random.normal(0, 0.5, n_periods),
        'Contrib_I': np.random.normal(0, 0.5, n_periods),
        'Contrib_L': np.random.normal(0, 0.5, n_periods),
        'Contrib_S': np.random.normal(0, 0.5, n_periods),
        'TrueStress': stress_levels,
        'Volatility': np.random.uniform(0.1, 0.5, n_periods),
        'Liquidity': np.random.uniform(0.3, 1.0, n_periods)
    }, index=all_dates)
    
    # Create performance data with regime-appropriate returns
    returns = []
    for regime, macro_score, stress in zip(regimes, macro_scores, stress_levels):
        if regime == 'Crisis':
            ret = np.random.normal(-0.008, 0.05)  # Negative returns, high vol
        elif regime == 'Slowdown':
            ret = np.random.normal(-0.002, 0.03)  # Slightly negative, medium vol
        elif regime == 'Expansion':
            ret = np.random.normal(0.005, 0.02)   # Positive returns, low vol
        else:  # Late-Expansion
            ret = np.random.normal(0.003, 0.025)  # Modest positive, medium vol
        
        # Add some macro influence
        ret += macro_score * 0.001
        
        returns.append(ret)
    
    # Create performance DataFrame with additional metrics
    cumulative_returns = np.cumsum(returns)
    running_max = np.maximum.accumulate(cumulative_returns)
    drawdowns = cumulative_returns - running_max
    
    perf_data = pd.DataFrame({
        'net_return': returns,
        'northstar_return': [r * 1.1 + np.random.normal(0, 0.001) for r in returns],
        'gross_return': [r * 1.05 for r in returns],
        'drawdown': drawdowns,
        'volatility': pd.Series(returns).rolling(4).std().fillna(0.02),
        'turnover': np.random.uniform(0.05, 0.15, n_periods),
        'transaction_costs': np.random.uniform(0.0005, 0.002, n_periods),
        'active_share': np.random.uniform(0.3, 0.8, n_periods)
    }, index=all_dates)
    
    print(f"   ✅ Created macro data with {len(set(regimes))} unique regimes")
    print(f"   ✅ Created performance data with {len(returns)} return periods")
    print(f"   📊 Regime distribution: {pd.Series(regimes).value_counts().to_dict()}")
    
    return macro_data, perf_data

def save_demo_data(macro_data, perf_data, data_dir):
    """Save demo data to specified directory"""
    
    print(f"💾 Saving demo data to {data_dir}...")
    
    # Create directory structure
    os.makedirs(os.path.join(data_dir, 'macro', 'factors'), exist_ok=True)
    os.makedirs(os.path.join(data_dir, 'processed'), exist_ok=True)
    os.makedirs(os.path.join(data_dir, 'validation'), exist_ok=True)
    
    # Save data files
    macro_path = os.path.join(data_dir, 'macro', 'factors', 'macro_score.parquet')
    perf_path = os.path.join(data_dir, 'processed', 'performance_summary.parquet')
    
    macro_data.to_parquet(macro_path)
    perf_data.to_parquet(perf_path)
    
    print(f"   ✅ Saved macro data: {macro_path}")
    print(f"   ✅ Saved performance data: {perf_path}")

def run_component_validation_demo():
    """Run Phase 3 component validation demo"""
    
    print("🔍 PHASE 3 COMPONENT VALIDATOR DEMO")
    print("Shadow Reality Phase 4.3 - Individual Component Validation")
    print("=" * 70)
    
    # Create temporary directory for demo
    temp_dir = tempfile.mkdtemp()
    print(f"📁 Using temporary directory: {temp_dir}")
    
    try:
        # Create and save demo data
        macro_data, perf_data = create_demo_data()
        save_demo_data(macro_data, perf_data, temp_dir)
        
        # Import and configure validator
        from src.validation.phase3_component_validator import Phase3ComponentValidator
        
        validator = Phase3ComponentValidator()
        
        # Override paths to use demo data
        validator.paths = {
            'macro_score': os.path.join(temp_dir, 'macro', 'factors', 'macro_score.parquet'),
            'performance_summary': os.path.join(temp_dir, 'processed', 'performance_summary.parquet'),
            'market_state': os.path.join(temp_dir, 'processed', 'market_state.parquet'),
            'component_validation_output': os.path.join(temp_dir, 'validation', 'phase3_component_validation.parquet'),
            'component_metadata': os.path.join(temp_dir, 'validation', 'phase3_component_metadata.json'),
            'component_reports': os.path.join(temp_dir, 'validation', 'component_reports')
        }
        
        print(f"\n🔧 Configured validator with demo data paths")
        
        # Run validation on a subset of periods for demo
        demo_periods = ['crisis_2008', 'recovery_2009', 'covid_crash_2020', 'inflation_shock_2022']
        
        print(f"\n🎯 Running component validation on {len(demo_periods)} demo periods:")
        for period in demo_periods:
            period_config = validator.validation_periods[period]
            print(f"   • {period_config['name']}: {period_config['description']}")
        
        # Run comprehensive component validation
        results = validator.validate_all_components_across_periods(demo_periods)
        
        # Print detailed insights
        print(f"\n" + "="*70)
        print("🔍 DETAILED COMPONENT ANALYSIS")
        print("="*70)
        
        # Component-specific insights
        component_names = {
            'regime_memory': 'Regime Memory System',
            'tailwind_engine': 'Simple Tailwind Engine',
            'no_edge_detector': 'NO_EDGE Detector',
            'capital_allocator': 'Anticipatory Capital Allocator'
        }
        
        for component, stats in results['component_statistics'].items():
            print(f"\n📊 {component_names[component]}:")
            print(f"   Success Rate: {stats['success_rate']:.1%}")
            print(f"   Periods Passed: {stats['periods_passed']}/{stats['total_periods']}")
            
            # Find best and worst performing periods for this component
            period_scores = []
            for period_name, period_result in results['period_results'].items():
                component_result = period_result['component_results'][component]
                if component == 'regime_memory':
                    score = component_result['accuracy_score']
                elif component == 'tailwind_engine':
                    score = (component_result['correlation_score'] + 
                           component_result['stability_score'] + 
                           component_result['predictive_score']) / 3
                elif component == 'no_edge_detector':
                    score = component_result['appropriateness_score']
                elif component == 'capital_allocator':
                    score = (component_result['performance_score'] + 
                           component_result['risk_adjusted_score'] + 
                           component_result['consistency_score']) / 3
                
                period_scores.append((period_name, score, component_result['validation_passed']))
            
            # Sort by score
            period_scores.sort(key=lambda x: x[1], reverse=True)
            
            if period_scores:
                best_period, best_score, best_passed = period_scores[0]
                worst_period, worst_score, worst_passed = period_scores[-1]
                
                print(f"   Best Period: {validator.validation_periods[best_period]['name']} ({best_score:.3f})")
                print(f"   Worst Period: {validator.validation_periods[worst_period]['name']} ({worst_score:.3f})")
        
        # Period-specific insights
        print(f"\n📋 PERIOD-SPECIFIC INSIGHTS:")
        for period_name, period_result in results['period_results'].items():
            period_config = validator.validation_periods[period_name]
            status = "✅" if period_result['validation_passed'] else "❌"
            
            print(f"\n{status} {period_config['name']}:")
            print(f"   Overall Score: {period_result['overall_score']:.3f}")
            print(f"   Components Passed: {period_result['components_passed']}/{period_result['total_components']}")
            
            # Show component breakdown
            for component, result in period_result['component_results'].items():
                comp_status = "✅" if result['validation_passed'] else "❌"
                print(f"     {comp_status} {component_names[component]}")
        
        print(f"\n🎯 DEMO INSIGHTS:")
        print("   • Phase 3 Component Validator provides detailed component-level analysis")
        print("   • Each component tested individually across multiple market conditions")
        print("   • Identifies component strengths and weaknesses across different regimes")
        print("   • Enables targeted improvements for specific components")
        print("   • Validates robustness of Phase 3 anticipatory intelligence foundation")
        
        print(f"\n📁 Demo results saved to: {temp_dir}")
        print("   (Temporary directory will be cleaned up)")
        
        return True
        
    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup temporary directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            print(f"\n🧹 Cleaned up temporary directory")

if __name__ == "__main__":
    success = run_component_validation_demo()
    
    if success:
        print(f"\n✅ Phase 3 Component Validator demo completed successfully!")
        print("🎯 Ready for Task 3.4: Implement CrossTimelineConsistencyChecker")
    else:
        print(f"\n❌ Demo failed - check implementation")
    
    exit(0 if success else 1)