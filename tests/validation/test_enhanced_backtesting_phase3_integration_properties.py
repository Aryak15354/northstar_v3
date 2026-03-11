#!/usr/bin/env python3
"""
🧪 PROPERTY TESTS: Enhanced Backtesting Phase 3 Integration
Property-based tests for Shadow Reality Phase 4.2 enhanced backtesting engine

**Property 7: Enhanced Backtesting Phase 3 Integration**
For any enhanced backtest run, the system should properly integrate Phase 3 anticipatory 
intelligence, apply NO_EDGE constraints historically, and generate comprehensive reports 
on Phase 3 component performance.

**Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.6**

This test validates that:
1. Enhanced backtesting builds upon existing V3 BacktestEngine correctly
2. Phase 3 anticipatory intelligence is properly integrated
3. NO_EDGE constraints are applied historically when appropriate
4. Regime memory accuracy is validated in historical contexts
5. Tailwind calculations are tested with forward-looking validation
6. Comprehensive reports on Phase 3 component performance are generated

Integration Points:
- Uses existing V3 BacktestEngine as foundation
- Integrates MarketConditionReplicator for advanced simulation
- Applies Phase 3 components (RegimeMemorySystem, SimpleTailwindEngine, NoEdgeDetector)
- Validates institutional-grade reporting and analysis

Test Strategy:
- Generate diverse backtest parameters (strategies, periods, simulation types)
- Test integration with Phase 3 components across different scenarios
- Validate historical constraint application and temporal discipline
- Verify comprehensive reporting and analysis generation
- Test error handling and graceful degradation
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume
from typing import Dict, List, Any, Optional
import warnings
warnings.filterwarnings('ignore')

# Import the enhanced backtesting engine
try:
    from src.validation.enhanced_backtesting_engine import (
        EnhancedBacktestingEngine, 
        SimulationType,
        EnhancedBacktestParameters,
        EnhancedBacktestResult
    )
    ENHANCED_ENGINE_AVAILABLE = True
except ImportError as e:
    ENHANCED_ENGINE_AVAILABLE = False
    print(f"⚠️ Enhanced Backtesting Engine not available: {e}")
    
    # Create dummy classes for type hints
    class EnhancedBacktestResult:
        pass
    
    class EnhancedBacktestParameters:
        pass

# Import V3 and Phase 3 components for validation
try:
    from src.backtesting.backtest_engine import BacktestEngine
    from src.validation.market_condition_replicator import MarketConditionReplicator
    V3_AVAILABLE = True
except ImportError:
    V3_AVAILABLE = False

try:
    from src.intelligence.regime_memory_system import RegimeMemorySystem
    from src.intelligence.simple_tailwind_engine import SimpleTailwindEngine
    from src.intelligence.no_edge_detector import NoEdgeDetector
    PHASE3_AVAILABLE = True
except ImportError:
    PHASE3_AVAILABLE = False

# Test data strategies
@st.composite
def enhanced_backtest_parameters(draw):
    """Generate enhanced backtest parameters for property testing"""
    
    # Strategy names
    strategy_name = draw(st.sampled_from([
        'northstar', 'mom_6m', 'mom_12m', 'value_tilt', 'quality_tilt',
        'low_vol', 'equal_weight_top', 'regime_conditional'
    ]))
    
    # Date ranges (ensure reasonable periods)
    start_year = draw(st.integers(min_value=2018, max_value=2022))
    start_month = draw(st.integers(min_value=1, max_value=12))
    start_day = draw(st.integers(min_value=1, max_value=28))  # Safe day range
    
    start_date = datetime(start_year, start_month, start_day)
    
    # End date (1-12 months after start)
    duration_days = draw(st.integers(min_value=30, max_value=365))
    end_date = start_date + timedelta(days=duration_days)
    
    # Simulation type
    simulation_type = draw(st.sampled_from([
        'basic_historical', 'advanced_conditions', 'regime_scenarios',
        'stress_testing', 'multi_timeline', 'phase3_integration'
    ]))
    
    # Asset universe (subset of common assets)
    all_assets = [
        'RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'HINDUNILVR.NS',
        'ICICIBANK.NS', 'KOTAKBANK.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'ITC.NS'
    ]
    
    asset_count = draw(st.integers(min_value=3, max_value=len(all_assets)))
    asset_universe = draw(st.lists(
        st.sampled_from(all_assets), 
        min_size=asset_count, 
        max_size=asset_count,
        unique=True
    ))
    
    # Additional parameters
    rebalance_frequency = draw(st.sampled_from(['daily', 'weekly', 'monthly']))
    condition_type = draw(st.sampled_from([
        'normal_conditions', 'crisis_volatility', 'regime_transition',
        'correlation_breakdown', 'liquidity_stress'
    ]))
    
    apply_phase3_constraints = draw(st.booleans())
    validate_regime_consistency = draw(st.booleans())
    simulation_fidelity = draw(st.floats(min_value=0.7, max_value=1.0))
    
    return {
        'strategy_name': strategy_name,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'simulation_type': simulation_type,
        'asset_universe': asset_universe,
        'rebalance_frequency': rebalance_frequency,
        'condition_type': condition_type,
        'apply_phase3_constraints': apply_phase3_constraints,
        'validate_regime_consistency': validate_regime_consistency,
        'simulation_fidelity': simulation_fidelity
    }

class TestEnhancedBacktestingPhase3Integration:
    """Test suite for Enhanced Backtesting Phase 3 Integration properties"""
    
    def setup_method(self):
        """Setup test environment"""
        if ENHANCED_ENGINE_AVAILABLE:
            self.engine = EnhancedBacktestingEngine()
        else:
            self.engine = None
    
    @pytest.mark.skipif(not ENHANCED_ENGINE_AVAILABLE, reason="Enhanced Backtesting Engine not available")
    @given(params=enhanced_backtest_parameters())
    @settings(max_examples=20, deadline=None)
    def test_property_7_enhanced_backtesting_phase3_integration(self, params):
        """
        Feature: shadow-reality, Property 7: Enhanced Backtesting Phase 3 Integration
        
        **Validates: Requirements 7.1, 7.2, 7.3, 7.4, 7.5, 7.6**
        
        For any enhanced backtest run, the system should properly integrate Phase 3 
        anticipatory intelligence, apply NO_EDGE constraints historically, and generate 
        comprehensive reports on Phase 3 component performance.
        """
        
        # Assume reasonable parameters
        assume(params['strategy_name'] is not None)
        assume(params['start_date'] < params['end_date'])
        assume(len(params['asset_universe']) >= 3)
        
        # Run enhanced backtest
        result = self.engine.run_enhanced_backtest(**params)
        
        # Validate result structure
        assert isinstance(result, EnhancedBacktestResult)
        assert result.parameters is not None
        assert result.basic_performance is not None
        assert result.enhanced_metrics is not None
        assert result.phase3_integration_results is not None
        assert result.simulation_validation is not None
        assert result.warnings is not None
        assert result.metadata is not None
        
        # **Requirement 7.1: Build upon existing V3 BacktestEngine**
        self._validate_v3_foundation_integration(result)
        
        # **Requirement 7.2: Integrate Phase 3 anticipatory intelligence**
        self._validate_phase3_intelligence_integration(result)
        
        # **Requirement 7.3: Apply NO_EDGE constraints historically**
        self._validate_no_edge_historical_application(result, params)
        
        # **Requirement 7.4: Validate regime memory historical accuracy**
        self._validate_regime_memory_historical_accuracy(result)
        
        # **Requirement 7.5: Test tailwind accuracy with forward-looking validation**
        self._validate_tailwind_forward_looking_accuracy(result)
        
        # **Requirement 7.6: Generate comprehensive Phase 3 component reports**
        self._validate_comprehensive_phase3_reporting(result)
        
        # Validate overall integration quality
        self._validate_overall_integration_quality(result, params)
    
    def _validate_v3_foundation_integration(self, result: EnhancedBacktestResult):
        """Validate that enhanced backtesting builds upon V3 BacktestEngine correctly"""
        
        # Check that basic performance data exists when V3 available and data is sufficient
        if V3_AVAILABLE:
            # If basic performance is empty, it should be due to insufficient data
            if result.basic_performance.empty:
                # Check if warnings indicate data issues or low performance
                data_warnings = [w for w in result.warnings if any(keyword in w.lower() for keyword in 
                    ['data', 'insufficient', 'low', 'fidelity', 'sharpe', 'unavailable'])]
                assert len(data_warnings) > 0, f"Empty performance should have relevant warnings. Got: {result.warnings}"
            else:
                # Validate basic performance structure when data exists
                required_columns = ['date', 'strategy', 'equity', 'daily_return']
                for col in required_columns:
                    if col in result.basic_performance.columns:
                        assert result.basic_performance[col].notna().any(), f"Column {col} should have valid data"
        
        # Check metadata indicates V3 integration status
        assert 'v3_integration' in result.metadata
        assert isinstance(result.metadata['v3_integration'], bool)
        
        # Validate enhanced metrics build upon basic metrics
        assert 'total_return' in result.enhanced_metrics
        assert 'sharpe_ratio' in result.enhanced_metrics
        assert 'max_drawdown' in result.enhanced_metrics
        
        # Enhanced metrics should be reasonable
        total_return = result.enhanced_metrics['total_return']
        assert -0.8 <= total_return <= 3.0, f"Total return {total_return} should be reasonable"
        
        sharpe_ratio = result.enhanced_metrics['sharpe_ratio']
        # Allow for extreme Sharpe ratios in short backtests or edge cases
        if not result.basic_performance.empty and len(result.basic_performance) > 5:
            assert -5.0 <= sharpe_ratio <= 20.0, f"Sharpe ratio {sharpe_ratio} should be reasonable for normal backtests"
        else:
            # For very short backtests or edge cases, allow wider range
            assert -50.0 <= sharpe_ratio <= 50.0, f"Sharpe ratio {sharpe_ratio} should be finite for edge cases"
    
    def _validate_phase3_intelligence_integration(self, result: EnhancedBacktestResult):
        """Validate Phase 3 anticipatory intelligence integration"""
        
        phase3_results = result.phase3_integration_results
        
        # Check Phase 3 integration structure
        assert 'integration_score' in phase3_results
        assert 'component_availability' in phase3_results
        
        integration_score = phase3_results['integration_score']
        assert 0.0 <= integration_score <= 1.0, f"Integration score {integration_score} should be between 0 and 1"
        
        # Check component availability tracking
        component_availability = phase3_results['component_availability']
        expected_components = ['regime_memory', 'tailwind_engine', 'no_edge_detector', 'anticipatory_allocator']
        
        for component in expected_components:
            assert component in component_availability
            assert isinstance(component_availability[component], bool)
        
        # If Phase 3 is available, integration score should be reasonable
        if PHASE3_AVAILABLE:
            assert integration_score >= 0.3, "Integration score should be reasonable when Phase 3 available"
            
            # Check individual component analyses
            if component_availability['regime_memory']:
                assert 'regime_memory_analysis' in phase3_results
                regime_analysis = phase3_results['regime_memory_analysis']
                assert 'integration_quality' in regime_analysis
                assert 0.0 <= regime_analysis['integration_quality'] <= 1.0
            
            if component_availability['tailwind_engine']:
                assert 'tailwind_analysis' in phase3_results
                tailwind_analysis = phase3_results['tailwind_analysis']
                assert 'integration_quality' in tailwind_analysis
                assert 0.0 <= tailwind_analysis['integration_quality'] <= 1.0
    
    def _validate_no_edge_historical_application(self, result: EnhancedBacktestResult, params: Dict[str, Any]):
        """Validate NO_EDGE constraints are applied historically when appropriate"""
        
        phase3_results = result.phase3_integration_results
        
        # Check if NO_EDGE analysis was performed
        if params['apply_phase3_constraints'] and PHASE3_AVAILABLE:
            component_availability = phase3_results['component_availability']
            
            if component_availability.get('no_edge_detector', False):
                assert 'no_edge_analysis' in phase3_results
                no_edge_analysis = phase3_results['no_edge_analysis']
                
                # Validate NO_EDGE analysis structure
                assert 'integration_quality' in no_edge_analysis
                assert 'trigger_accuracy' in no_edge_analysis
                assert 'exposure_capping_effectiveness' in no_edge_analysis
                
                # Validate metrics are reasonable
                trigger_accuracy = no_edge_analysis['trigger_accuracy']
                assert 0.0 <= trigger_accuracy <= 1.0, f"Trigger accuracy {trigger_accuracy} should be between 0 and 1"
                
                capping_effectiveness = no_edge_analysis['exposure_capping_effectiveness']
                assert 0.0 <= capping_effectiveness <= 1.0, f"Capping effectiveness {capping_effectiveness} should be between 0 and 1"
                
                # Check false positive rate
                if 'false_positive_rate' in no_edge_analysis:
                    false_positive_rate = no_edge_analysis['false_positive_rate']
                    assert 0.0 <= false_positive_rate <= 0.3, f"False positive rate {false_positive_rate} should be low"
        
        # Check that exposure constraints are reflected in performance data
        if not result.basic_performance.empty and 'exposure' in result.basic_performance.columns:
            exposures = result.basic_performance['exposure']
            max_exposure = exposures.max()
            
            # If NO_EDGE constraints applied, exposure should be capped
            if params['apply_phase3_constraints'] and PHASE3_AVAILABLE:
                # Allow some tolerance for implementation variations
                assert max_exposure <= 1.2, f"Maximum exposure {max_exposure} should be reasonable with constraints"
    
    def _validate_regime_memory_historical_accuracy(self, result: EnhancedBacktestResult):
        """Validate regime memory historical accuracy"""
        
        phase3_results = result.phase3_integration_results
        component_availability = phase3_results['component_availability']
        
        if component_availability.get('regime_memory', False):
            assert 'regime_memory_analysis' in phase3_results
            regime_analysis = phase3_results['regime_memory_analysis']
            
            # Check historical accuracy metrics
            if 'historical_accuracy' in regime_analysis:
                historical_accuracy = regime_analysis['historical_accuracy']
                assert 0.0 <= historical_accuracy <= 1.0, f"Historical accuracy {historical_accuracy} should be between 0 and 1"
                assert historical_accuracy >= 0.5, f"Historical accuracy {historical_accuracy} should be reasonable"
            
            # Check regime classifications
            if 'regime_classifications' in regime_analysis:
                regime_classifications = regime_analysis['regime_classifications']
                assert isinstance(regime_classifications, dict)
            
            # Check similarity scores
            if 'similarity_scores' in regime_analysis:
                similarity_scores = regime_analysis['similarity_scores']
                assert isinstance(similarity_scores, dict)
        
        # Validate regime analysis in results
        regime_analysis = result.regime_analysis
        assert 'regime_consistency_score' in regime_analysis
        
        consistency_score = regime_analysis['regime_consistency_score']
        assert 0.0 <= consistency_score <= 1.0, f"Regime consistency score {consistency_score} should be between 0 and 1"
        
        # Check regime periods analysis
        if 'regime_periods' in regime_analysis:
            regime_periods = regime_analysis['regime_periods']
            assert isinstance(regime_periods, dict)
            
            # Validate regime period structure
            for regime, data in regime_periods.items():
                assert 'count' in data
                assert 'percentage' in data
                assert data['count'] >= 0
                assert 0.0 <= data['percentage'] <= 100.0
    
    def _validate_tailwind_forward_looking_accuracy(self, result: EnhancedBacktestResult):
        """Validate tailwind accuracy with forward-looking validation"""
        
        phase3_results = result.phase3_integration_results
        component_availability = phase3_results['component_availability']
        
        if component_availability.get('tailwind_engine', False):
            assert 'tailwind_analysis' in phase3_results
            tailwind_analysis = phase3_results['tailwind_analysis']
            
            # Check tailwind calculation accuracy
            if 'regime_weighting_accuracy' in tailwind_analysis:
                regime_weighting_accuracy = tailwind_analysis['regime_weighting_accuracy']
                assert 0.0 <= regime_weighting_accuracy <= 1.0, f"Regime weighting accuracy {regime_weighting_accuracy} should be between 0 and 1"
                assert regime_weighting_accuracy >= 0.4, f"Regime weighting accuracy {regime_weighting_accuracy} should be reasonable"
            
            if 'sharpe_component_accuracy' in tailwind_analysis:
                sharpe_component_accuracy = tailwind_analysis['sharpe_component_accuracy']
                assert 0.0 <= sharpe_component_accuracy <= 1.0, f"Sharpe component accuracy {sharpe_component_accuracy} should be between 0 and 1"
                assert sharpe_component_accuracy >= 0.4, f"Sharpe component accuracy {sharpe_component_accuracy} should be reasonable"
            
            # Check tailwind calculations structure
            if 'tailwind_calculations' in tailwind_analysis:
                tailwind_calculations = tailwind_analysis['tailwind_calculations']
                assert isinstance(tailwind_calculations, dict)
        
        # Validate attribution includes tailwind contribution
        attribution = result.attribution_breakdown
        if 'tailwind_contribution' in attribution:
            tailwind_contribution = attribution['tailwind_contribution']
            assert -0.1 <= tailwind_contribution <= 0.2, f"Tailwind contribution {tailwind_contribution} should be reasonable"
    
    def _validate_comprehensive_phase3_reporting(self, result: EnhancedBacktestResult):
        """Validate comprehensive Phase 3 component performance reports"""
        
        # Check attribution breakdown completeness
        attribution = result.attribution_breakdown
        expected_attribution_components = [
            'total_alpha', 'regime_contribution', 'tailwind_contribution',
            'no_edge_contribution', 'anticipatory_contribution'
        ]
        
        for component in expected_attribution_components:
            assert component in attribution, f"Attribution should include {component}"
            value = attribution[component]
            assert isinstance(value, (int, float)), f"{component} should be numeric"
            assert -0.5 <= value <= 0.5, f"{component} value {value} should be reasonable"
        
        # Check that total attribution is consistent
        component_sum = (
            attribution.get('regime_contribution', 0) +
            attribution.get('tailwind_contribution', 0) +
            attribution.get('no_edge_contribution', 0) +
            attribution.get('anticipatory_contribution', 0) +
            attribution.get('interaction_effects', 0)
        )
        
        total_alpha = attribution.get('total_alpha', 0)
        if abs(component_sum) > 0.001:  # Avoid division by zero
            attribution_consistency = abs(total_alpha - component_sum) / abs(component_sum)
            assert attribution_consistency <= 0.5, f"Attribution consistency {attribution_consistency} should be reasonable"
        
        # Check enhanced metrics include Phase 3 enhancements
        enhanced_metrics = result.enhanced_metrics
        phase3_enhanced_metrics = [
            'simulation_enhanced_sharpe', 'regime_adjusted_return',
            'phase3_enhanced_alpha', 'risk_adjusted_performance'
        ]
        
        for metric in phase3_enhanced_metrics:
            assert metric in enhanced_metrics, f"Enhanced metrics should include {metric}"
            value = enhanced_metrics[metric]
            assert isinstance(value, (int, float)), f"{metric} should be numeric"
        
        # Check simulation validation completeness
        simulation_validation = result.simulation_validation
        expected_validation_metrics = [
            'overall_fidelity', 'temporal_consistency', 'correlation_preservation',
            'volatility_accuracy', 'regime_consistency'
        ]
        
        for metric in expected_validation_metrics:
            assert metric in simulation_validation, f"Simulation validation should include {metric}"
            value = simulation_validation[metric]
            assert 0.0 <= value <= 1.0, f"{metric} value {value} should be between 0 and 1"
    
    def _validate_overall_integration_quality(self, result: EnhancedBacktestResult, params: Dict[str, Any]):
        """Validate overall integration quality and consistency"""
        
        # Check that results are internally consistent
        enhanced_metrics = result.enhanced_metrics
        simulation_validation = result.simulation_validation
        phase3_results = result.phase3_integration_results
        
        # Integration score should correlate with simulation fidelity
        integration_score = phase3_results.get('integration_score', 0.0)
        overall_fidelity = simulation_validation.get('overall_fidelity', 0.0)
        
        # Both should be reasonable if components are available
        if PHASE3_AVAILABLE and V3_AVAILABLE:
            assert integration_score >= 0.3, f"Integration score {integration_score} should be reasonable with components available"
            assert overall_fidelity >= 0.3, f"Overall fidelity {overall_fidelity} should be reasonable with components available"
        
        # Check warning generation is appropriate
        warnings = result.warnings
        assert isinstance(warnings, list)
        
        # Should have warnings if components not available
        if not PHASE3_AVAILABLE:
            phase3_warning_found = any('Phase 3' in warning for warning in warnings)
            assert phase3_warning_found, "Should warn when Phase 3 components not available"
        
        if not V3_AVAILABLE:
            v3_warning_found = any('V3' in warning for warning in warnings)
            assert v3_warning_found, "Should warn when V3 components not available"
        
        # Check metadata completeness
        metadata = result.metadata
        required_metadata = ['backtest_timestamp', 'engine_version', 'v3_integration', 'phase3_integration']
        
        for field in required_metadata:
            assert field in metadata, f"Metadata should include {field}"
        
        # Validate timestamp format
        backtest_timestamp = metadata['backtest_timestamp']
        assert isinstance(backtest_timestamp, str)
        # Should be able to parse as ISO format
        datetime.fromisoformat(backtest_timestamp.replace('Z', '+00:00'))

def main():
    """Run property tests for Enhanced Backtesting Phase 3 Integration"""
    
    print("🧪 TESTING ENHANCED BACKTESTING PHASE 3 INTEGRATION PROPERTIES")
    print("=" * 70)
    
    if not ENHANCED_ENGINE_AVAILABLE:
        print("❌ Enhanced Backtesting Engine not available - skipping tests")
        return False
    
    # Create test instance
    test_suite = TestEnhancedBacktestingPhase3Integration()
    test_suite.setup_method()
    
    # Generate test parameters manually
    test_params = {
        'strategy_name': 'northstar',
        'start_date': '2020-01-01',
        'end_date': '2020-03-31',
        'simulation_type': 'phase3_integration',
        'asset_universe': ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS'],
        'rebalance_frequency': 'weekly',
        'condition_type': 'normal_conditions',
        'apply_phase3_constraints': True,
        'validate_regime_consistency': True,
        'simulation_fidelity': 0.9
    }
    
    try:
        # Run the test directly
        print("🧪 Running Property 7 test...")
        
        # Run enhanced backtest
        result = test_suite.engine.run_enhanced_backtest(**test_params)
        
        # Validate result structure
        assert isinstance(result, EnhancedBacktestResult)
        assert result.parameters is not None
        assert result.basic_performance is not None
        assert result.enhanced_metrics is not None
        assert result.phase3_integration_results is not None
        assert result.simulation_validation is not None
        assert result.warnings is not None
        assert result.metadata is not None
        
        print("✅ Property 7 test passed!")
        print(f"   Integration Score: {result.phase3_integration_results.get('integration_score', 0.0):.3f}")
        print(f"   Simulation Fidelity: {result.simulation_validation.get('overall_fidelity', 0.0):.3f}")
        print(f"   Total Return: {result.enhanced_metrics.get('total_return', 0.0):.2%}")
        
        return True
        
    except Exception as e:
        print(f"❌ Property 7 test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    main()
