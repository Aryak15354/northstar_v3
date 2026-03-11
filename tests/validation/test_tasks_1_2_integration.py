#!/usr/bin/env python3
"""
Integration Test: Tasks 1-2 Validation

Tests that the core temporal infrastructure (Task 1) and stateful brain (Task 2)
work together properly to maintain temporal integrity.
"""

import sys
import os
from datetime import datetime, timedelta
import numpy as np

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from src.intelligence.temporal_guard import TemporalGuard
from src.validation.northstar_brain_state import NorthstarBrain


def test_temporal_guard_brain_integration():
    """Test that temporal guard and brain work together"""
    
    print("🧪 Testing Temporal Guard + Brain Integration...")
    
    # Initialize components
    temporal_guard = TemporalGuard()
    start_date = datetime(2023, 1, 1)
    
    # Create brain with temporal guard
    brain = NorthstarBrain.from_historical_state(
        historical_data={},
        start_date=start_date,
        temporal_guard=temporal_guard
    )
    
    print(f"✅ Brain initialized with temporal guard at {start_date}")
    
    # Test forward progression
    current_date = start_date
    states = []
    
    for i in range(5):
        current_date += timedelta(days=1)
        
        # Create daily market data
        daily_data = {
            'market_return': np.random.normal(0, 0.02),
            'market_volatility': 0.15 + np.random.normal(0, 0.05),
            'market_momentum': np.random.normal(0, 0.01)
        }
        
        # Step brain forward
        portfolio_weights = brain.step_forward(daily_data, current_date)
        state = brain.get_current_state()
        
        # Verify temporal integrity
        assert state.timestamp == current_date, f"State timestamp mismatch: {state.timestamp} != {current_date}"
        assert state.verify_integrity(), "State integrity verification failed"
        
        states.append((current_date, state, portfolio_weights))
        
        print(f"✅ Day {i+1}: Brain stepped to {current_date}, generated {len(portfolio_weights)} weights")
    
    # Verify temporal progression
    for i in range(1, len(states)):
        prev_date, prev_state, _ = states[i-1]
        curr_date, curr_state, _ = states[i]
        
        assert curr_date > prev_date, "Time should advance"
        assert curr_state.timestamp > prev_state.timestamp, "State timestamp should advance"
    
    print("✅ Temporal progression verified")
    
    # Test that brain cannot step backwards
    try:
        past_date = start_date
        brain.step_forward({'market_return': 0}, past_date)
        assert False, "Should not allow stepping backwards"
    except ValueError as e:
        assert "cannot step backwards" in str(e)
        print("✅ Backwards stepping properly prevented")
    
    return True


def test_state_preservation_across_steps():
    """Test that state is properly preserved across multiple steps"""
    
    print("\n🧪 Testing State Preservation...")
    
    temporal_guard = TemporalGuard()
    start_date = datetime(2023, 1, 1)
    brain = NorthstarBrain.from_historical_state({}, start_date, temporal_guard)
    
    # Step forward with regime change conditions
    current_date = start_date + timedelta(days=1)
    
    # Start with crisis conditions
    crisis_data = {
        'market_return': -0.05,
        'market_volatility': 0.35,  # High volatility = crisis
        'market_momentum': -0.03
    }
    
    brain.step_forward(crisis_data, current_date)
    crisis_state = brain.get_current_state()
    
    assert crisis_state.regime_state.current_regime == "crisis"
    print(f"✅ Crisis regime detected: {crisis_state.regime_state.current_regime}")
    
    # Continue crisis for 3 more days
    for i in range(3):
        current_date += timedelta(days=1)
        brain.step_forward(crisis_data, current_date)
    
    extended_crisis_state = brain.get_current_state()
    
    # Regime should persist with increasing duration and confidence
    assert extended_crisis_state.regime_state.current_regime == "crisis"
    assert extended_crisis_state.regime_state.regime_duration == 4
    assert extended_crisis_state.regime_state.confidence > crisis_state.regime_state.confidence
    
    print(f"✅ Crisis regime persisted: duration={extended_crisis_state.regime_state.regime_duration}, confidence={extended_crisis_state.regime_state.confidence:.3f}")
    
    # Switch to bull market conditions
    current_date += timedelta(days=1)
    bull_data = {
        'market_return': 0.03,
        'market_volatility': 0.12,  # Low volatility
        'market_momentum': 0.025    # Strong momentum = bull
    }
    
    brain.step_forward(bull_data, current_date)
    bull_state = brain.get_current_state()
    
    # Should detect regime change
    assert bull_state.regime_state.current_regime == "bull"
    assert bull_state.regime_state.regime_duration == 1  # Reset duration
    assert bull_state.regime_state.last_transition_date == current_date
    
    print(f"✅ Regime transition detected: {extended_crisis_state.regime_state.current_regime} -> {bull_state.regime_state.current_regime}")
    
    return True


def test_bayesian_learning_integration():
    """Test that Bayesian learning works with temporal constraints"""
    
    print("\n🧪 Testing Bayesian Learning Integration...")
    
    temporal_guard = TemporalGuard()
    start_date = datetime(2023, 1, 1)
    brain = NorthstarBrain.from_historical_state({}, start_date, temporal_guard)
    
    initial_state = brain.get_current_state()
    initial_alphas = initial_state.bayesian_priors.specialist_alphas.copy()
    
    print(f"✅ Initial specialist alphas: {initial_alphas}")
    
    # Simulate consistent momentum performance
    current_date = start_date
    for i in range(10):
        current_date += timedelta(days=1)
        
        # Conditions favorable to momentum
        daily_data = {
            'market_return': 0.015,  # Consistent positive returns
            'market_volatility': 0.12,
            'market_momentum': 0.015,
            'momentum_return': 0.02  # Momentum outperforms
        }
        
        brain.step_forward(daily_data, current_date)
    
    final_state = brain.get_current_state()
    final_alphas = final_state.bayesian_priors.specialist_alphas
    
    print(f"✅ Final specialist alphas: {final_alphas}")
    
    # Verify learning occurred
    assert final_state.bayesian_priors.update_counts['momentum'] > 0
    print(f"✅ Momentum specialist received {final_state.bayesian_priors.update_counts['momentum']} updates")
    
    # Verify performance history is tracked
    assert len(final_state.performance_history) == 10
    assert len(final_state.attribution_history) == 10
    
    print("✅ Performance and attribution history properly tracked")
    
    return True


def test_signal_decay_temporal_consistency():
    """Test that signal decay maintains temporal consistency"""
    
    print("\n🧪 Testing Signal Decay Temporal Consistency...")
    
    temporal_guard = TemporalGuard()
    start_date = datetime(2023, 1, 1)
    brain = NorthstarBrain.from_historical_state({}, start_date, temporal_guard)
    
    # Generate strong signal
    current_date = start_date + timedelta(days=1)
    strong_signal_data = {
        'market_return': 0.03,
        'market_volatility': 0.15,
        'market_momentum': 0.025
    }
    
    brain.step_forward(strong_signal_data, current_date)
    signal_state = brain.get_current_state()
    
    # All decay factors should be 1.0 (just updated)
    # Note: decay is applied first, then signals are updated, so we need to check the next step
    for specialist, decay_factor in signal_state.signal_decay_factors.items():
        assert decay_factor >= 0.95, f"Fresh signal should have high decay factor, got {decay_factor}"
    
    print("✅ Fresh signals have high strength (decay factor >= 0.95)")
    
    # Let signals decay over time
    decay_factors_over_time = []
    
    for i in range(5):
        current_date += timedelta(days=1)
        
        # No new signals
        no_signal_data = {
            'market_return': 0.0,
            'market_volatility': 0.15,
            'market_momentum': 0.0
        }
        
        brain.step_forward(no_signal_data, current_date)
        state = brain.get_current_state()
        
        avg_decay = np.mean(list(state.signal_decay_factors.values()))
        decay_factors_over_time.append(avg_decay)
        
        print(f"✅ Day {i+1}: Average decay factor = {avg_decay:.4f}")
    
    # Verify decay is monotonic and bounded
    for i in range(1, len(decay_factors_over_time)):
        assert decay_factors_over_time[i] <= decay_factors_over_time[i-1], "Decay should be monotonic"
        assert decay_factors_over_time[i] >= 0.01, "Decay should be bounded above 0.01"
    
    print("✅ Signal decay is monotonic and properly bounded")
    
    return True


def run_all_integration_tests():
    """Run all integration tests for Tasks 1-2"""
    
    print("🧬 TASKS 1-2 INTEGRATION TESTING")
    print("=" * 50)
    
    tests = [
        ("Temporal Guard + Brain Integration", test_temporal_guard_brain_integration),
        ("State Preservation Across Steps", test_state_preservation_across_steps),
        ("Bayesian Learning Integration", test_bayesian_learning_integration),
        ("Signal Decay Temporal Consistency", test_signal_decay_temporal_consistency)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
                print(f"\n✅ {test_name} PASSED")
            else:
                failed += 1
                print(f"\n❌ {test_name} FAILED")
        except Exception as e:
            failed += 1
            print(f"\n❌ {test_name} FAILED: {e}")
    
    print(f"\n🧬 INTEGRATION TEST SUMMARY")
    print("=" * 50)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"📊 Success Rate: {passed/(passed+failed)*100:.1f}%")
    
    if failed == 0:
        print(f"\n🎉 ALL INTEGRATION TESTS PASSED!")
        print("💡 Tasks 1-2 are working together correctly")
        print("🚀 Ready to proceed with Phase 1 implementation")
        return True
    else:
        print(f"\n⚠️ Some integration tests failed")
        print("🔧 Fix issues before proceeding to Phase 1")
        return False


if __name__ == "__main__":
    success = run_all_integration_tests()
    exit(0 if success else 1)
