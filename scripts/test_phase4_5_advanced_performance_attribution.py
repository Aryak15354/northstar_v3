#!/usr/bin/env python3
"""
Test Phase 4.5 Advanced Performance Attribution System

Tests all components built for Phase 4.5:
- RegimeBasedAttributionEngine
- Phase3ComponentAttribution
- MultiDimensionalDecomposer
- InstitutionalReportGenerator
- EnhancedPerformanceTracker

This comprehensive test validates the integration and functionality
of all Phase 4.5 components.
"""

import sys
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging
from pathlib import Path

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.validation.regime_based_attribution_engine import RegimeBasedAttributionEngine
from src.validation.phase3_component_attribution import Phase3ComponentAttribution
from src.validation.multi_dimensional_decomposer import MultiDimensionalDecomposer
from src.validation.institutional_report_generator import (
    InstitutionalReportGenerator, InstitutionalReportConfig
)
from src.validation.enhanced_performance_tracker import (
    EnhancedPerformanceTracker, PerformanceTrackingConfig
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_test_data():
    """Create comprehensive test data for Phase 4.5 validation"""
    
    # Create date range
    dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')
    n_periods = len(dates)
    
    # Create portfolio returns with some realistic patterns
    np.random.seed(42)  # For reproducible results
    
    # Base returns with trend and volatility clustering
    base_returns = np.random.normal(0.0008, 0.015, n_periods)  # ~20% annual vol, positive drift
    volatility_regime = np.random.choice([0.8, 1.0, 1.2], n_periods, p=[0.3, 0.4, 0.3])
    portfolio_returns = pd.Series(base_returns * volatility_regime, index=dates)
    
    # Create benchmark returns (slightly lower performance)
    benchmark_returns = pd.Series(
        np.random.normal(0.0006, 0.012, n_periods), index=dates
    )
    
    # Create Phase 3 signals
    phase3_signals = {}
    
    # Regime classification
    regimes = np.random.choice(['expansion', 'contraction', 'recovery'], n_periods, p=[0.5, 0.2, 0.3])
    phase3_signals['regime_classification'] = pd.Series(regimes, index=dates)
    
    # Regime similarity scores
    phase3_signals['regime_similarity_score'] = pd.Series(
        np.random.uniform(0.6, 0.95, n_periods), index=dates
    )
    
    # Tailwind scores
    phase3_signals['tailwind_scores'] = pd.Series(
        np.random.uniform(0.3, 0.9, n_periods), index=dates
    )
    
    # Strategy tailwinds (multiple strategies)
    phase3_signals['strategy_tailwinds'] = pd.Series(
        np.random.uniform(0.4, 0.8, n_periods), index=dates
    )
    
    # NO_EDGE state
    phase3_signals['no_edge_state'] = pd.Series(
        np.random.choice([True, False], n_periods, p=[0.15, 0.85]), index=dates
    )
    
    # NO_EDGE confidence
    phase3_signals['no_edge_confidence'] = pd.Series(
        np.random.uniform(0.5, 0.9, n_periods), index=dates
    )
    
    # Anticipatory allocation
    phase3_signals['anticipatory_allocation'] = pd.Series(
        np.random.uniform(0.2, 0.8, n_periods), index=dates
    )
    
    # Anticipatory signals
    phase3_signals['anticipatory_signals'] = pd.Series(
        np.random.uniform(-0.1, 0.1, n_periods), index=dates
    )
    
    return portfolio_returns, benchmark_returns, phase3_signals

def test_regime_based_attribution_engine():
    """Test RegimeBasedAttributionEngine"""
    
    print("\n🎯 Testing RegimeBasedAttributionEngine...")
    print("=" * 50)
    
    try:
        engine = RegimeBasedAttributionEngine()
        portfolio_returns, benchmark_returns, phase3_signals = create_test_data()
        
        # Test regime attribution
        result = engine.calculate_regime_attribution(
            portfolio_returns,
            phase3_signals['regime_classification'],
            benchmark_returns,
            phase3_signals['regime_similarity_score']
        )
        
        print(f"✅ RegimeBasedAttributionEngine test PASSED")
        print(f"   Total Portfolio Return: {result.total_portfolio_return:.3f}")
        print(f"   Benchmark Return: {result.benchmark_return:.3f}")
        print(f"   Regime Timing Alpha: {result.regime_timing_alpha:.3f}")
        print(f"   Unexplained Alpha: {result.unexplained_alpha:.3f}")
        print(f"   Regimes Analyzed: {len(result.regime_performance)}")
        print(f"   Transitions Analyzed: {len(result.transition_performance)}")
        
        # Test report generation
        report = engine.generate_regime_attribution_report(result)
        print(f"   Report Generated: {len(report)} characters")
        
        return True, result
        
    except Exception as e:
        print(f"❌ RegimeBasedAttributionEngine test FAILED: {str(e)}")
        return False, None

def test_phase3_component_attribution():
    """Test Phase3ComponentAttribution"""
    
    print("\n🧩 Testing Phase3ComponentAttribution...")
    print("=" * 50)
    
    try:
        engine = Phase3ComponentAttribution()
        portfolio_returns, benchmark_returns, phase3_signals = create_test_data()
        
        # Test component attribution
        result = engine.calculate_phase3_component_attribution(
            portfolio_returns, phase3_signals, benchmark_returns
        )
        
        print(f"✅ Phase3ComponentAttribution test PASSED")
        print(f"   Total Portfolio Return: {result.total_portfolio_return:.3f}")
        print(f"   Benchmark Return: {result.benchmark_return:.3f}")
        print(f"   Component Timing Alpha: {result.component_timing_alpha:.3f}")
        print(f"   Attribution R²: {result.attribution_r_squared:.3f}")
        print(f"   Components Analyzed: {len(result.component_contributions)}")
        print(f"   Interaction Effects: {len(result.interaction_effects)}")
        print(f"   Unexplained Alpha: {result.unexplained_alpha:.3f}")
        
        # Test report generation
        report = engine.generate_component_attribution_report(result)
        print(f"   Report Generated: {len(report)} characters")
        
        return True, result
        
    except Exception as e:
        print(f"❌ Phase3ComponentAttribution test FAILED: {str(e)}")
        return False, None

def test_multi_dimensional_decomposer():
    """Test MultiDimensionalDecomposer"""
    
    print("\n🔀 Testing MultiDimensionalDecomposer...")
    print("=" * 50)
    
    try:
        decomposer = MultiDimensionalDecomposer()
        portfolio_returns, benchmark_returns, phase3_signals = create_test_data()
        
        # Prepare dimensions
        dimensions = {
            'regime': phase3_signals['regime_classification'],
            'tailwinds': phase3_signals['tailwind_scores'],
            'no_edge': phase3_signals['no_edge_state'],
            'anticipatory': phase3_signals['anticipatory_allocation']
        }
        
        # Test multi-dimensional decomposition
        result = decomposer.decompose_performance_multi_dimensional(
            portfolio_returns, dimensions, benchmark_returns
        )
        
        print(f"✅ MultiDimensionalDecomposer test PASSED")
        print(f"   Total Return: {result.total_return:.3f}")
        print(f"   Benchmark Return: {result.benchmark_return:.3f}")
        print(f"   Model R²: {result.model_r_squared:.3f}")
        print(f"   Adjusted R²: {result.model_adjusted_r_squared:.3f}")
        print(f"   Dimensions Analyzed: {len(result.dimensions)}")
        print(f"   Main Effects: {len(result.main_effects)}")
        print(f"   Interaction Effects: {len(result.interaction_effects)}")
        print(f"   Unexplained Alpha: {result.unexplained_alpha:.3f}")
        
        # Test report generation
        report = decomposer.generate_multi_dimensional_report(result)
        print(f"   Report Generated: {len(report)} characters")
        
        return True, result
        
    except Exception as e:
        print(f"❌ MultiDimensionalDecomposer test FAILED: {str(e)}")
        return False, None

def test_institutional_report_generator():
    """Test InstitutionalReportGenerator"""
    
    print("\n📊 Testing InstitutionalReportGenerator...")
    print("=" * 50)
    
    try:
        # Create output directory for test
        test_output_dir = "data/testing/institutional_reports"
        Path(test_output_dir).mkdir(parents=True, exist_ok=True)
        
        generator = InstitutionalReportGenerator(test_output_dir)
        portfolio_returns, benchmark_returns, phase3_signals = create_test_data()
        
        # Create report configuration
        config = InstitutionalReportConfig(
            report_type="tearsheet",
            report_period=(portfolio_returns.index[0], portfolio_returns.index[-1]),
            include_phase3_analysis=True,
            include_risk_analysis=True,
            include_compliance_section=True
        )
        
        # Test institutional tearsheet generation
        report = generator.generate_institutional_tearsheet(
            portfolio_returns, benchmark_returns, phase3_signals, config
        )
        
        print(f"✅ InstitutionalReportGenerator test PASSED")
        print(f"   Report ID: {report.report_id}")
        print(f"   Report Type: {report.report_type}")
        print(f"   Total Return: {report.performance_metrics.total_return:.3f}")
        print(f"   Sharpe Ratio: {report.performance_metrics.sharpe_ratio:.3f}")
        print(f"   Max Drawdown: {report.performance_metrics.max_drawdown:.3f}")
        print(f"   Institutional Grade: {report.phase3_intelligence_analysis.get('intelligence_integration_score', 0):.3f}")
        print(f"   HTML Report Length: {len(report.report_html)} characters")
        print(f"   Compliance Certified: {report.compliance_certification['performance_standards_compliance']}")
        
        return True, report
        
    except Exception as e:
        print(f"❌ InstitutionalReportGenerator test FAILED: {str(e)}")
        return False, None

def test_enhanced_performance_tracker():
    """Test EnhancedPerformanceTracker"""
    
    print("\n📈 Testing EnhancedPerformanceTracker...")
    print("=" * 50)
    
    try:
        # Create configuration
        config = PerformanceTrackingConfig(
            enable_regime_attribution=True,
            enable_component_attribution=True,
            enable_multi_dimensional_attribution=True,
            enable_institutional_reporting=True
        )
        
        tracker = EnhancedPerformanceTracker(config)
        portfolio_returns, benchmark_returns, phase3_signals = create_test_data()
        
        # Test enhanced performance tracking
        enhanced_metrics = tracker.track_enhanced_performance(
            portfolio_returns, benchmark_returns, phase3_signals
        )
        
        print(f"✅ EnhancedPerformanceTracker test PASSED")
        print(f"   Basic Metrics Available: {len(enhanced_metrics.basic_metrics)}")
        print(f"   Phase 3 Intelligence Score: {enhanced_metrics.phase3_intelligence_score:.3f}")
        print(f"   Attribution Quality Score: {enhanced_metrics.attribution_quality_score:.3f}")
        print(f"   Institutional Grade: {enhanced_metrics.institutional_grade_rating}")
        print(f"   Regime Attribution: {'✓' if enhanced_metrics.regime_attribution else '✗'}")
        print(f"   Component Attribution: {'✓' if enhanced_metrics.component_attribution else '✗'}")
        print(f"   Multi-Dimensional Attribution: {'✓' if enhanced_metrics.multi_dimensional_attribution else '✗'}")
        
        # Test institutional report generation
        institutional_report = tracker.generate_institutional_report(
            portfolio_returns, benchmark_returns, phase3_signals
        )
        
        if institutional_report:
            print(f"   Institutional Report Generated: {institutional_report.report_id}")
        
        # Test performance summary
        summary = tracker.get_performance_summary()
        print(f"   Performance Summary Available: {len(summary)} fields")
        
        return True, enhanced_metrics
        
    except Exception as e:
        print(f"❌ EnhancedPerformanceTracker test FAILED: {str(e)}")
        return False, None

def run_integration_test():
    """Run integration test of all Phase 4.5 components"""
    
    print("\n🔗 Running Phase 4.5 Integration Test...")
    print("=" * 50)
    
    try:
        # Test all components in sequence
        regime_success, regime_result = test_regime_based_attribution_engine()
        component_success, component_result = test_phase3_component_attribution()
        decomposer_success, decomposer_result = test_multi_dimensional_decomposer()
        report_success, report_result = test_institutional_report_generator()
        tracker_success, tracker_result = test_enhanced_performance_tracker()
        
        # Check overall success
        all_tests = [regime_success, component_success, decomposer_success, report_success, tracker_success]
        overall_success = all(all_tests)
        
        print(f"\n🎯 PHASE 4.5 INTEGRATION TEST SUMMARY:")
        print("=" * 50)
        print(f"   RegimeBasedAttributionEngine: {'✅ PASS' if regime_success else '❌ FAIL'}")
        print(f"   Phase3ComponentAttribution: {'✅ PASS' if component_success else '❌ FAIL'}")
        print(f"   MultiDimensionalDecomposer: {'✅ PASS' if decomposer_success else '❌ FAIL'}")
        print(f"   InstitutionalReportGenerator: {'✅ PASS' if report_success else '❌ FAIL'}")
        print(f"   EnhancedPerformanceTracker: {'✅ PASS' if tracker_success else '❌ FAIL'}")
        print(f"\n   OVERALL INTEGRATION: {'✅ PASS' if overall_success else '❌ FAIL'}")
        
        return overall_success
        
    except Exception as e:
        print(f"❌ Integration test FAILED: {str(e)}")
        return False

def test_end_to_end_workflow():
    """Test end-to-end Phase 4.5 workflow"""
    
    print("\n🔄 Testing End-to-End Phase 4.5 Workflow...")
    print("=" * 50)
    
    try:
        # Create test data
        portfolio_returns, benchmark_returns, phase3_signals = create_test_data()
        
        # Initialize enhanced tracker
        config = PerformanceTrackingConfig(
            enable_regime_attribution=True,
            enable_component_attribution=True,
            enable_multi_dimensional_attribution=True,
            enable_institutional_reporting=True
        )
        
        tracker = EnhancedPerformanceTracker(config)
        
        # Step 1: Track enhanced performance
        enhanced_metrics = tracker.track_enhanced_performance(
            portfolio_returns, benchmark_returns, phase3_signals
        )
        
        # Step 2: Generate institutional report
        institutional_report = tracker.generate_institutional_report(
            portfolio_returns, benchmark_returns, phase3_signals, "tearsheet"
        )
        
        # Step 3: Get performance summary
        summary = tracker.get_performance_summary()
        
        print(f"✅ End-to-End Workflow test PASSED")
        print(f"   Enhanced Metrics Generated: ✓")
        print(f"   Institutional Report Generated: {'✓' if institutional_report else '✗'}")
        print(f"   Performance Summary Available: ✓")
        print(f"   Final Institutional Grade: {enhanced_metrics.institutional_grade_rating}")
        
        return True
        
    except Exception as e:
        print(f"❌ End-to-End Workflow test FAILED: {str(e)}")
        return False

def main():
    """Main test execution"""
    
    print("🎯 PHASE 4.5 ADVANCED PERFORMANCE ATTRIBUTION SYSTEM TEST")
    print("=" * 80)
    print("Testing all components built for Phase 4.5:")
    print("- RegimeBasedAttributionEngine")
    print("- Phase3ComponentAttribution")
    print("- MultiDimensionalDecomposer")
    print("- InstitutionalReportGenerator")
    print("- EnhancedPerformanceTracker")
    print("=" * 80)
    
    # Create test directories
    Path("data/testing/institutional_reports").mkdir(parents=True, exist_ok=True)
    Path("data/performance/enhanced").mkdir(parents=True, exist_ok=True)
    
    # Run all tests
    integration_success = run_integration_test()
    workflow_success = test_end_to_end_workflow()
    
    # Final summary
    print(f"\n🏁 FINAL TEST SUMMARY:")
    print("=" * 80)
    
    if integration_success and workflow_success:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Phase 4.5 Advanced Performance Attribution System is working correctly")
        print("✅ All components integrate properly")
        print("✅ End-to-end workflow functions correctly")
        print("✅ Ready to proceed to Phase 4.6: Sophisticated Stress Testing Framework")
        return 0
    else:
        print("❌ SOME TESTS FAILED!")
        print("⚠️ Please review the failed components before proceeding")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
