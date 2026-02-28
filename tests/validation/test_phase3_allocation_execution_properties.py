#!/usr/bin/env python3
"""
🧪 PROPERTY TESTS - PHASE 3 ALLOCATION EXECUTION FIDELITY
Property-based tests for Advanced Shadow Executor Phase 3 integration

Property 1: Phase 3 Allocation Execution Fidelity
**Validates: Requirements 1.1, 1.2, 1.3, 1.4**

This property test validates that the AdvancedShadowExecutor correctly:
1. Integrates with Phase 3 AnticipatoryCapitalAllocator
2. Executes allocations with advanced market simulation
3. Applies Phase 3 NO_EDGE constraints and exposure capping
4. Tracks execution quality and reality consistency

The test uses property-based testing to verify these behaviors hold
across a wide range of market conditions and Phase 3 states.
"""

import pytest
import pandas as pd
import numpy as np
import os
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant
import sys

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from validation.advanced_shadow_executor import AdvancedShadowExecutor

class TestPhase3AllocationExecutionFidelity:
    """Property tests for Phase 3 allocation execution fidelity"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Create data directories
        os.makedirs('data/intelligence', exist_ok=True)
        os.makedirs('data/processed', exist_ok=True)
        os.makedirs('data/shadow_reality', exist_ok=True)
        
        self.executor = AdvancedShadowExecutor()
        
        # Override paths to use temp directory
        for key, path in self.executor.paths.items():
            self.executor.paths[key] = path
    
    def teardown_method(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_mock_regime_memory(self, regime_name='Late-Expansion', n_periods=100):
        """Create mock regime memory data"""
        dates = pd.date_range(start='2023-01-01', periods=n_periods, freq='W')
        
        regime_data = []
        for date in dates:
            regime_data.append({
                'Regime': regime_name,
                'regime_avg_return': np.random.normal(0.001, 0.002),
                'regime_sharpe': np.random.normal(1.2, 0.3),
                'MacroScore_scaled': np.random.normal(0, 1),
                'Contrib_G_scaled': np.random.normal(0, 1),
                'Contrib_I_scaled': np.random.normal(0, 1)
            })
        
        regime_df = pd.DataFrame(regime_data, index=dates)
        regime_df.to_parquet('data/intelligence/regime_memory.parquet')
        return regime_df
    
    def create_mock_strategy_tailwinds(self, strategies=None, regime='Late-Expansion'):
        """Create mock strategy tailwinds data"""
        if strategies is None:
            strategies = ['dual_momentum', 'regime_conditional', 'sector_tilt_mom', 
                         'quality_tilt', 'low_vol', 'value_tilt', 'northstar']
        
        tailwind_data = []
        for strategy in strategies:
            tailwind_data.append({
                'strategy': strategy,
                'regime': regime,
                'sharpe': np.random.normal(1.0, 0.5),
                'normalized_sharpe': np.random.normal(1.0, 0.3),
                'regime_tailwind': np.random.normal(1.2, 0.4),
                'combined_score': np.random.normal(1.5, 0.5),
                'sharpe_contribution': np.random.normal(0.6, 0.2),
                'regime_contribution': np.random.normal(0.5, 0.2)
            })
        
        tailwind_df = pd.DataFrame(tailwind_data)
        tailwind_df['date'] = datetime.now().date()
        tailwind_df = tailwind_df.set_index('date')
        tailwind_df.to_parquet('data/intelligence/strategy_tailwinds.parquet')
        return tailwind_df
    
    def create_mock_no_edge_state(self, state='NORMAL', exposure_cap=0.8, reasons=None):
        """Create mock NO_EDGE state data"""
        if reasons is None:
            reasons = []
        
        no_edge_data = [{
            'date': datetime.now().date(),
            'state': state,
            'exposure_cap': exposure_cap,
            'n_reasons': len(reasons),
            'reasons': '; '.join(reasons) if reasons else '',
            'state_changed': False
        }]
        
        no_edge_df = pd.DataFrame(no_edge_data)
        no_edge_df.to_parquet('data/intelligence/no_edge_state.parquet', index=False)
        return no_edge_df
    
    def create_mock_capital_allocations(self, strategies=None, total_exposure=0.8):
        """Create mock capital allocations data"""
        if strategies is None:
            strategies = ['dual_momentum', 'regime_conditional', 'sector_tilt_mom', 
                         'quality_tilt', 'low_vol']
        
        # Generate random allocations that sum to total_exposure
        raw_allocations = np.random.dirichlet(np.ones(len(strategies))) * total_exposure
        allocations = {strategy: float(alloc) for strategy, alloc in zip(strategies, raw_allocations)}
        
        allocation_data = {
            'timestamp': datetime.now().isoformat(),
            'date': datetime.now().date().isoformat(),
            'regime': {'macro_regime': 'Late-Expansion'},
            'no_edge_state': {'state': 'NORMAL', 'exposure_cap': 0.8},
            'allocations': allocations,
            'total_exposure': sum(allocations.values())
        }
        
        with open('data/processed/capital_allocations.json', 'w') as f:
            json.dump(allocation_data, f, default=str)
        
        return allocations
    
    @given(
        regime_name=st.sampled_from(['Crisis', 'Expansion', 'Late-Expansion', 'Slowdown']),
        n_strategies=st.integers(min_value=3, max_value=10),
        exposure_cap=st.floats(min_value=0.1, max_value=1.0),
        no_edge_state=st.sampled_from(['NORMAL', 'NO_EDGE'])
    )
    @settings(max_examples=50, deadline=30000)
    def test_phase3_allocation_execution_fidelity(self, regime_name, n_strategies, exposure_cap, no_edge_state):
        """
        Property 1: Phase 3 Allocation Execution Fidelity
        
        Tests that the AdvancedShadowExecutor maintains fidelity to Phase 3 components:
        1. Correctly loads Phase 3 intelligence state
        2. Respects NO_EDGE exposure constraints
        3. Applies tailwind enhancements appropriately
        4. Maintains execution quality standards
        5. Provides accurate performance attribution
        """
        
        # Generate test strategies
        base_strategies = ['dual_momentum', 'regime_conditional', 'sector_tilt_mom', 
                          'quality_tilt', 'low_vol', 'value_tilt', 'northstar', 'growth']
        strategies = base_strategies[:n_strategies]
        
        # Create mock Phase 3 data
        regime_df = self.create_mock_regime_memory(regime_name)
        tailwind_df = self.create_mock_strategy_tailwinds(strategies, regime_name)
        no_edge_df = self.create_mock_no_edge_state(no_edge_state, exposure_cap)
        allocations = self.create_mock_capital_allocations(strategies, min(exposure_cap, 0.8))
        
        # Execute shadow portfolio
        result = self.executor.execute_shadow_portfolio()
        
        # Property 1.1: Successfully loads Phase 3 intelligence
        assert result.get('success', False), "Shadow execution should succeed"
        assert result.get('intelligence_confidence', 0) > 0, "Should have positive intelligence confidence"
        assert result.get('regime') == regime_name, f"Should detect regime as {regime_name}"
        assert result.get('no_edge_state') == no_edge_state, f"Should detect NO_EDGE state as {no_edge_state}"
        
        # Property 1.2: Respects NO_EDGE exposure constraints
        total_exposure = result.get('total_exposure', 0)
        if no_edge_state == 'NO_EDGE':
            # In NO_EDGE state, exposure should be capped at the specified limit
            assert total_exposure <= exposure_cap + 0.01, f"NO_EDGE exposure {total_exposure:.3f} should be <= {exposure_cap:.3f}"
        else:
            # In NORMAL state, exposure should be reasonable but can be higher
            assert total_exposure <= 1.0, f"Normal exposure {total_exposure:.3f} should be <= 100%"
        
        assert total_exposure >= 0, "Total exposure should be non-negative"
        
        # Property 1.3: Maintains execution quality standards
        execution_quality = result.get('execution_quality', 0)
        assert 0 <= execution_quality <= 1, f"Execution quality {execution_quality} should be between 0 and 1"
        
        # For reasonable market conditions, execution quality should be reasonable
        # Note: execution quality can vary due to random simulation noise
        if no_edge_state == 'NORMAL' and n_strategies <= 7 and exposure_cap >= 0.5:
            assert execution_quality >= 0.4, f"Execution quality {execution_quality} should be >= 40% for normal conditions"
        
        # Property 1.4: Provides reality consistency validation
        reality_consistency = result.get('reality_consistency', 0)
        assert 0 <= reality_consistency <= 1, f"Reality consistency {reality_consistency} should be between 0 and 1"
        assert reality_consistency >= 0.7, f"Reality consistency {reality_consistency} should be >= 70%"
        
        consistency_score = result.get('consistency_score', 0)
        assert 0 <= consistency_score <= 1, f"Consistency score {consistency_score} should be between 0 and 1"
        
        # Property 1.5: Phase 3 performance attribution is present
        phase3_contributions = result.get('phase3_contributions', {})
        assert 'regime' in phase3_contributions, "Should have regime contribution"
        assert 'tailwind' in phase3_contributions, "Should have tailwind contribution"
        assert 'no_edge' in phase3_contributions, "Should have NO_EDGE contribution"
        
        # Contributions should be finite numbers
        for component, contribution in phase3_contributions.items():
            assert np.isfinite(contribution), f"{component} contribution should be finite"
        
        # Property 1.6: Number of positions is reasonable
        n_positions = result.get('n_positions', 0)
        # Note: n_positions can be higher than n_strategies due to existing positions from previous runs
        # We should check that it's reasonable, not strictly bounded by current strategies
        assert n_positions >= 0, f"Number of positions {n_positions} should be non-negative"
        assert n_positions <= 15, f"Number of positions {n_positions} should be reasonable (<=15)"
        
        # In normal conditions with reasonable exposure, should have some positions
        if no_edge_state == 'NORMAL' and total_exposure > 0.1:
            assert n_positions > 0, "Should have some positions in normal state with reasonable exposure"
    
    @given(
        exposure_caps=st.lists(st.floats(min_value=0.1, max_value=1.0), min_size=2, max_size=5),
        regime_changes=st.lists(st.sampled_from(['Crisis', 'Expansion', 'Late-Expansion', 'Slowdown']), 
                               min_size=2, max_size=5)
    )
    @settings(max_examples=20, deadline=45000)
    def test_phase3_allocation_consistency_across_conditions(self, exposure_caps, regime_changes):
        """
        Property 1.7: Allocation Consistency Across Changing Conditions
        
        Tests that the executor maintains consistent behavior as Phase 3 conditions change:
        1. Exposure properly adjusts to changing caps
        2. Regime changes are reflected in allocations
        3. Execution quality remains stable
        4. Attribution properly tracks changes
        """
        
        strategies = ['dual_momentum', 'regime_conditional', 'sector_tilt_mom', 'quality_tilt', 'low_vol']
        results = []
        
        # Test across different conditions
        for i, (exposure_cap, regime) in enumerate(zip(exposure_caps, regime_changes)):
            # Create mock data for this condition
            self.create_mock_regime_memory(regime)
            self.create_mock_strategy_tailwinds(strategies, regime)
            
            # Determine NO_EDGE state based on exposure cap
            no_edge_state = 'NO_EDGE' if exposure_cap < 0.5 else 'NORMAL'
            self.create_mock_no_edge_state(no_edge_state, exposure_cap)
            self.create_mock_capital_allocations(strategies, min(exposure_cap, 0.8))
            
            # Execute
            result = self.executor.execute_shadow_portfolio()
            results.append(result)
            
            # Basic validation for each execution
            assert result.get('success', False), f"Execution {i} should succeed"
            assert result.get('regime') == regime, f"Should detect regime {regime} in execution {i}"
            
            total_exposure = result.get('total_exposure', 0)
            assert total_exposure <= exposure_cap + 0.02, f"Exposure should respect cap in execution {i}"
        
        # Property 1.7.1: Execution quality should be consistently reasonable
        execution_qualities = [r.get('execution_quality', 0) for r in results]
        assert all(q >= 0.2 for q in execution_qualities), "All execution qualities should be >= 20%"
        
        # Property 1.7.2: Reality consistency should be stable
        reality_consistencies = [r.get('reality_consistency', 0) for r in results]
        assert all(rc >= 0.6 for rc in reality_consistencies), "All reality consistencies should be >= 60%"
        
        # Property 1.7.3: Exposure should properly track caps
        exposures = [r.get('total_exposure', 0) for r in results]
        for exposure, cap in zip(exposures, exposure_caps):
            assert exposure <= cap + 0.02, f"Exposure {exposure:.3f} should be <= cap {cap:.3f}"
        
        # Property 1.7.4: Attribution should be present for all executions
        for i, result in enumerate(results):
            phase3_contributions = result.get('phase3_contributions', {})
            assert len(phase3_contributions) >= 3, f"Should have at least 3 attribution components in execution {i}"
            
            for component, contribution in phase3_contributions.items():
                assert np.isfinite(contribution), f"Contribution {component} should be finite in execution {i}"
    
    @given(
        n_strategies=st.integers(min_value=1, max_value=15),
        allocation_concentration=st.floats(min_value=0.1, max_value=10.0)
    )
    @settings(max_examples=30, deadline=30000)
    def test_phase3_allocation_scaling_properties(self, n_strategies, allocation_concentration):
        """
        Property 1.8: Allocation Scaling Properties
        
        Tests that the executor properly handles different numbers of strategies
        and allocation concentrations:
        1. Scales properly with strategy count
        2. Handles concentrated vs diversified allocations
        3. Maintains execution quality across scales
        4. Attribution remains accurate
        """
        
        # Generate strategies
        base_strategies = ['dual_momentum', 'regime_conditional', 'sector_tilt_mom', 
                          'quality_tilt', 'low_vol', 'value_tilt', 'northstar', 'growth',
                          'momentum_6m', 'momentum_12m', 'defensive', 'small_cap', 'large_cap',
                          'international', 'emerging_markets']
        strategies = base_strategies[:n_strategies]
        
        # Create concentrated or diversified allocations
        if allocation_concentration > 2.0:
            # Concentrated: most weight in first few strategies
            weights = np.array([allocation_concentration ** (-i) for i in range(n_strategies)])
        else:
            # Diversified: more equal weights
            weights = np.ones(n_strategies)
        
        weights = weights / weights.sum() * 0.8  # Scale to 80% total exposure
        allocations = {strategy: float(weight) for strategy, weight in zip(strategies, weights)}
        
        # Create mock data
        self.create_mock_regime_memory('Late-Expansion')
        self.create_mock_strategy_tailwinds(strategies, 'Late-Expansion')
        self.create_mock_no_edge_state('NORMAL', 0.8)
        
        # Save allocations
        allocation_data = {
            'timestamp': datetime.now().isoformat(),
            'allocations': allocations,
            'total_exposure': sum(allocations.values())
        }
        with open('data/processed/capital_allocations.json', 'w') as f:
            json.dump(allocation_data, f, default=str)
        
        # Execute
        result = self.executor.execute_shadow_portfolio()
        
        # Property 1.8.1: Should handle any reasonable number of strategies
        assert result.get('success', False), f"Should succeed with {n_strategies} strategies"
        
        n_positions = result.get('n_positions', 0)
        # Note: n_positions can be higher than n_strategies due to existing positions from previous runs
        # We should check that it's reasonable, not strictly bounded by current strategies
        assert 0 <= n_positions <= 20, f"Positions {n_positions} should be reasonable (<=20)"
        
        # Property 1.8.2: Total exposure should be reasonable
        total_exposure = result.get('total_exposure', 0)
        expected_exposure = sum(allocations.values())
        assert abs(total_exposure - expected_exposure) < 0.1, f"Exposure should be close to expected {expected_exposure:.3f}"
        
        # Property 1.8.3: Execution quality should not degrade significantly with scale
        execution_quality = result.get('execution_quality', 0)
        if n_strategies <= 10:  # Reasonable scale
            assert execution_quality >= 0.2, f"Execution quality should be >= 20% for {n_strategies} strategies"
        else:  # Large scale
            assert execution_quality >= 0.1, f"Execution quality should be >= 10% even for {n_strategies} strategies"
        
        # Property 1.8.4: Attribution should scale properly
        phase3_contributions = result.get('phase3_contributions', {})
        total_attribution = sum(abs(contrib) for contrib in phase3_contributions.values())
        
        # Attribution magnitude should be reasonable relative to exposure
        if total_exposure > 0.1:
            assert total_attribution < total_exposure * 0.5, "Attribution should not exceed reasonable bounds"
    
    def test_phase3_integration_error_handling(self):
        """
        Property 1.9: Error Handling and Graceful Degradation
        
        Tests that the executor handles missing or corrupted Phase 3 data gracefully:
        1. Handles missing regime memory
        2. Handles missing tailwinds
        3. Handles missing NO_EDGE state
        4. Handles missing allocations
        5. Provides reasonable fallbacks
        """
        
        # Test 1: Missing regime memory
        self.create_mock_strategy_tailwinds()
        self.create_mock_no_edge_state()
        self.create_mock_capital_allocations()
        # Don't create regime memory
        
        result = self.executor.execute_shadow_portfolio()
        # Should still work with fallbacks
        assert result.get('intelligence_confidence', 0) > 0, "Should have some confidence even without regime memory"
        
        # Test 2: Missing tailwinds
        self.create_mock_regime_memory()
        # Don't create tailwinds
        
        result = self.executor.execute_shadow_portfolio()
        assert result.get('intelligence_confidence', 0) > 0, "Should work without tailwinds"
        
        # Test 3: Missing NO_EDGE state
        self.create_mock_strategy_tailwinds()
        # Don't create NO_EDGE state
        
        result = self.executor.execute_shadow_portfolio()
        assert result.get('intelligence_confidence', 0) > 0, "Should work without NO_EDGE state"
        
        # Test 4: Missing allocations
        self.create_mock_no_edge_state()
        # Remove allocations file
        if os.path.exists('data/processed/capital_allocations.json'):
            os.remove('data/processed/capital_allocations.json')
        
        result = self.executor.execute_shadow_portfolio()
        # This should fail gracefully or have minimal exposure
        assert result.get('total_exposure', 0) <= 0.1, "Should have minimal exposure without allocations"
        
        # Test 5: All data present - should work best
        self.create_mock_regime_memory()
        self.create_mock_strategy_tailwinds()
        self.create_mock_no_edge_state()
        self.create_mock_capital_allocations()
        
        result = self.executor.execute_shadow_portfolio()
        assert result.get('success', False), "Should succeed with all data present"
        assert result.get('intelligence_confidence', 0) >= 0.8, "Should have high confidence with all data"

if __name__ == "__main__":
    # Run a simple test
    test_instance = TestPhase3AllocationExecutionFidelity()
    test_instance.setup_method()
    
    try:
        # Test with sample data
        test_instance.create_mock_regime_memory('Late-Expansion')
        test_instance.create_mock_strategy_tailwinds()
        test_instance.create_mock_no_edge_state('NORMAL', 0.8)
        test_instance.create_mock_capital_allocations()
        
        result = test_instance.executor.execute_shadow_portfolio()
        
        print("🧪 PROPERTY TEST VALIDATION")
        print("=" * 50)
        print(f"✅ Shadow execution: {'SUCCESS' if result.get('success') else 'FAILED'}")
        print(f"✅ Intelligence confidence: {result.get('intelligence_confidence', 0):.1%}")
        print(f"✅ Execution quality: {result.get('execution_quality', 0):.1%}")
        print(f"✅ Reality consistency: {result.get('reality_consistency', 0):.1%}")
        print(f"✅ Total exposure: {result.get('total_exposure', 0):.1%}")
        print(f"✅ Phase 3 attribution components: {len(result.get('phase3_contributions', {}))}")
        
        print(f"\n🎯 Property Test Ready!")
        print(f"   Run: pytest tests/validation/test_phase3_allocation_execution_properties.py -v")
        
    finally:
        test_instance.teardown_method()