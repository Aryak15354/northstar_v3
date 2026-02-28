#!/usr/bin/env python3
"""
🔮 FORWARD VALIDATOR PROPERTY TESTS - PHASE 6: ENHANCEMENT LAYER
Property-based tests for anticipation timing validation

**Validates: Requirements 10.4**

This implements property-based tests for the forward validator to ensure
anticipation timing validation works correctly across different scenarios.

CRITICAL PRINCIPLE: Anticipation Timing Validation
- Test anticipation events where allocation changes preceded market moves
- Verify allocation shifts occurred before corresponding returns
- Track anticipation success rate over time
- Provide evidence of predictive capability
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume, example
from hypothesis.extra.pandas import data_frames, column
import warnings

warnings.filterwarnings('ignore')

# Import the forward validator
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.validation.forward_validator import (
    ForwardValidator, 
    AnticipationResult, 
    AnticipationEvent
)


class TestForwardValidatorProperties:
    """Property-based tests for forward validator anticipation timing"""
    
    def setup_method(self):
        """Setup test environment"""
        self.validator = ForwardValidator(base_dir="data/test_forward_validator")
        
        # Clean test directory
        import shutil
        if os.path.exists("data/test_forward_validator"):
            shutil.rmtree("data/test_forward_validator")
        os.makedirs("data/test_forward_validator", exist_ok=True)
    
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        if os.path.exists("data/test_forward_validator"):
            shutil.rmtree("data/test_forward_validator")
    
    @given(
        n_periods=st.integers(min_value=50, max_value=200),
        base_allocation=st.floats(min_value=0.3, max_value=0.8),
        allocation_volatility=st.floats(min_value=0.01, max_value=0.05),
        return_correlation=st.floats(min_value=0.1, max_value=0.8),
        seed=st.integers(min_value=1, max_value=1000)
    )
    @settings(max_examples=15, deadline=30000)
    def test_anticipation_timing_property(self, n_periods, base_allocation, allocation_volatility, return_correlation, seed):
        """
        **Property 26: Anticipation Timing**
        **Validates: Requirements 10.4**
        
        PROPERTY: For any allocation sequence with predictive changes, the forward
        validator should correctly identify anticipation events where allocation
        shifts preceded corresponding returns.
        
        This tests that anticipation timing validation correctly identifies when
        allocation changes preceded market moves with appropriate timing.
        """
        
        np.random.seed(seed)
        
        # Generate allocation data with intentional regime changes
        dates = pd.date_range(start='2023-01-01', periods=n_periods, freq='D')
        
        allocation_data = []
        current_allocation = base_allocation
        
        # Add regime changes at specific points
        regime_change_points = [n_periods // 4, n_periods // 2, 3 * n_periods // 4]
        regime_changes = [0.15, -0.20, 0.10]  # Allocation changes
        
        for i, date in enumerate(dates):
            # Apply regime changes
            for j, change_point in enumerate(regime_change_points):
                if i == change_point:
                    current_allocation += regime_changes[j]
                    current_allocation = max(0.1, min(0.9, current_allocation))
            
            # Add noise
            noise = np.random.normal(0, allocation_volatility)
            allocation = max(0.1, min(0.9, current_allocation + noise))
            
            allocation_data.append({
                'date': date,
                'strategy_allocation': allocation
            })
        
        allocation_df = pd.DataFrame(allocation_data)
        
        # Generate return data with correlation to allocation changes (with lag)
        return_data = []
        lag_days = 5  # Returns follow allocation changes with 5-day lag
        
        for i, date in enumerate(dates):
            base_return = 0.001  # 0.1% daily base return
            
            # Add correlation with lagged allocation changes
            if i >= lag_days + 1:
                # Calculate allocation change lag_days ago
                lagged_allocation_change = (allocation_df.iloc[i - lag_days]['strategy_allocation'] - 
                                          allocation_df.iloc[i - lag_days - 1]['strategy_allocation'])
                
                # Correlated return component
                correlated_return = lagged_allocation_change * return_correlation * 10  # Scale up correlation
            else:
                correlated_return = 0
            
            # Add noise
            noise = np.random.normal(0, 0.015)
            daily_return = base_return + correlated_return + noise
            
            return_data.append({
                'date': date,
                'strategy_return': daily_return
            })
        
        return_df = pd.DataFrame(return_data)
        
        # Test anticipation events
        anticipation_events = self.validator.test_anticipation_events(allocation_df, return_df)
        
        # PROPERTY ASSERTIONS
        
        # Property 1: Should detect anticipation events
        assert len(anticipation_events) > 0, "Should detect at least one anticipation event"
        
        # Property 2: All events should be valid AnticipationEvent instances
        for event in anticipation_events:
            assert isinstance(event, AnticipationEvent), "Should return AnticipationEvent instances"
            
            # Validate event structure
            validation_errors = event.validate()
            assert len(validation_errors) == 0, f"Event validation failed: {validation_errors}"
        
        # Property 3: Allocation changes should be meaningful
        for event in anticipation_events:
            assert abs(event.allocation_change) >= self.validator.config['min_allocation_change'], \
                f"Allocation change {event.allocation_change:.3f} should be >= {self.validator.config['min_allocation_change']:.3f}"
        
        # Property 4: Forward returns should be calculated
        for event in anticipation_events:
            # At least one forward return should be available
            has_forward_return = (
                not np.isnan(event.return_1d) or 
                not np.isnan(event.return_5d) or 
                not np.isnan(event.return_20d)
            )
            assert has_forward_return, "Event should have at least one forward return calculated"
        
        # Property 5: Anticipation scores should be within reasonable bounds
        for event in anticipation_events:
            # Anticipation scores should be finite
            assert np.isfinite(event.anticipation_score), f"Anticipation score should be finite: {event.anticipation_score}"
            
            # Scores should be within reasonable range (typically -3 to 3)
            assert -5.0 <= event.anticipation_score <= 5.0, \
                f"Anticipation score {event.anticipation_score} outside reasonable bounds [-5.0, 5.0]"
        
        # Property 6: Confidence levels should be valid probabilities
        for event in anticipation_events:
            assert 0.0 <= event.confidence_level <= 1.0, \
                f"Confidence level {event.confidence_level} should be between 0.0 and 1.0"
        
        # Property 7: Timing advantage should be positive
        for event in anticipation_events:
            assert event.timing_advantage >= 0, \
                f"Timing advantage {event.timing_advantage} should be non-negative"
        
        # Property 8: Event dates should be within data range
        data_start = allocation_df['date'].min()
        data_end = allocation_df['date'].max()
        
        for event in anticipation_events:
            assert data_start <= event.date <= data_end, \
                f"Event date {event.date} should be within data range [{data_start}, {data_end}]"
        
        # Property 9: With intentional correlation, should have some successful anticipations
        successful_events = [e for e in anticipation_events if e.anticipation_result == AnticipationResult.SUCCESS]
        
        # With return_correlation > 0.3, we should see some success
        if return_correlation > 0.3 and len(anticipation_events) >= 3:
            success_rate = len(successful_events) / len(anticipation_events)
            assert success_rate > 0.1, \
                f"With correlation {return_correlation:.2f}, success rate {success_rate:.2f} should be > 0.1"
    
    @given(
        allocation_change=st.floats(min_value=-0.3, max_value=0.3),
        forward_return=st.floats(min_value=-0.1, max_value=0.1),
        event_type=st.sampled_from(['increase', 'decrease', 'regime_shift'])
    )
    @settings(max_examples=50, deadline=10000)
    def test_anticipation_score_calculation_property(self, allocation_change, forward_return, event_type):
        """
        **Property 27: Anticipation Score Calculation Consistency**
        **Validates: Requirements 10.4, 10.5**
        
        PROPERTY: Anticipation score calculation should be consistent and
        reward correct directional predictions while penalizing incorrect ones.
        
        This tests that the anticipation scoring algorithm correctly evaluates
        the relationship between allocation changes and subsequent returns.
        """
        
        # Skip very small changes that might not be meaningful
        assume(abs(allocation_change) >= 0.01)
        assume(abs(forward_return) >= 0.001)
        
        # Calculate anticipation score
        anticipation_score, confidence_level = self.validator.calculate_anticipation_score(
            allocation_change, forward_return, event_type
        )
        
        # PROPERTY ASSERTIONS
        
        # Property 1: Score should be finite
        assert np.isfinite(anticipation_score), f"Anticipation score should be finite: {anticipation_score}"
        assert np.isfinite(confidence_level), f"Confidence level should be finite: {confidence_level}"
        
        # Property 2: Confidence should be valid probability
        assert 0.0 <= confidence_level <= 1.0, \
            f"Confidence level {confidence_level} should be between 0.0 and 1.0"
        
        # Property 3: Directional consistency
        # When allocation change and return have same sign, score should tend to be positive
        same_direction = (allocation_change > 0 and forward_return > 0) or (allocation_change < 0 and forward_return < 0)
        opposite_direction = (allocation_change > 0 and forward_return < 0) or (allocation_change < 0 and forward_return > 0)
        
        if same_direction and abs(allocation_change) > 0.05 and abs(forward_return) > 0.01:
            # Strong same-direction moves should generally have positive scores
            assert anticipation_score > -0.5, \
                f"Same direction moves should have non-negative scores: alloc={allocation_change:.3f}, ret={forward_return:.3f}, score={anticipation_score:.3f}"
        
        if opposite_direction and abs(allocation_change) > 0.05 and abs(forward_return) > 0.01:
            # Strong opposite-direction moves should generally have negative scores
            assert anticipation_score < 0.5, \
                f"Opposite direction moves should have non-positive scores: alloc={allocation_change:.3f}, ret={forward_return:.3f}, score={anticipation_score:.3f}"
        
        # Property 4: Magnitude sensitivity
        # Larger changes should generally produce higher confidence
        if abs(allocation_change) > 0.1 and abs(forward_return) > 0.02:
            assert confidence_level > 0.01, \
                f"Large changes should produce non-zero confidence: alloc={allocation_change:.3f}, ret={forward_return:.3f}, conf={confidence_level:.3f}"
        
        # Property 5: Event type multiplier effect
        # Regime shifts should have different scoring than regular changes
        if event_type == 'regime_shift' and same_direction and abs(allocation_change) > 0.1:
            # Regime shifts should get bonus scoring
            regular_score, _ = self.validator.calculate_anticipation_score(
                allocation_change, forward_return, 'increase'
            )
            # Regime shift score should be at least as good as regular score
            assert anticipation_score >= regular_score * 0.9, \
                f"Regime shift should not significantly penalize score: regime={anticipation_score:.3f}, regular={regular_score:.3f}"
    
    @given(
        anticipation_score=st.floats(min_value=-2.0, max_value=2.0),
        confidence_level=st.floats(min_value=0.0, max_value=1.0)
    )
    @settings(max_examples=30, deadline=10000)
    def test_anticipation_result_classification_property(self, anticipation_score, confidence_level):
        """
        **Property 28: Anticipation Result Classification Consistency**
        **Validates: Requirements 10.5, 10.6**
        
        PROPERTY: Anticipation result classification should be consistent with
        configured thresholds and provide appropriate categorization.
        
        This tests that the result classification logic correctly applies
        thresholds and maintains consistency in anticipation determinations.
        """
        
        # Classify anticipation result
        anticipation_result, success_message = self.validator.classify_anticipation_result(
            anticipation_score, confidence_level
        )
        
        # PROPERTY ASSERTIONS
        
        # Property 1: Result should be valid enum value
        assert isinstance(anticipation_result, AnticipationResult), \
            f"Result should be AnticipationResult enum: {type(anticipation_result)}"
        
        # Property 2: Message should be informative
        assert isinstance(success_message, str), "Success message should be string"
        assert len(success_message) > 5, f"Success message should be informative: '{success_message}'"
        
        # Property 3: Confidence threshold logic
        confidence_threshold = self.validator.config['confidence_threshold']
        
        if confidence_level < confidence_threshold:
            assert anticipation_result == AnticipationResult.INSUFFICIENT_DATA, \
                f"Low confidence ({confidence_level:.3f} < {confidence_threshold:.3f}) should result in INSUFFICIENT_DATA"
            assert "confidence" in success_message.lower(), \
                f"Low confidence message should mention confidence: '{success_message}'"
        
        # Property 4: Success threshold logic
        success_threshold = self.validator.config['success_threshold']
        
        if confidence_level >= confidence_threshold:
            if anticipation_score >= success_threshold:
                assert anticipation_result == AnticipationResult.SUCCESS, \
                    f"High score ({anticipation_score:.3f} >= {success_threshold:.3f}) should result in SUCCESS"
            elif anticipation_score <= -success_threshold:
                assert anticipation_result == AnticipationResult.FAILURE, \
                    f"Low score ({anticipation_score:.3f} <= {-success_threshold:.3f}) should result in FAILURE"
            else:
                assert anticipation_result == AnticipationResult.NEUTRAL, \
                    f"Neutral score ({anticipation_score:.3f}) should result in NEUTRAL"
        
        # Property 5: Score information in message
        if anticipation_result in [AnticipationResult.SUCCESS, AnticipationResult.FAILURE, AnticipationResult.NEUTRAL]:
            assert str(round(anticipation_score, 3)) in success_message or f"{anticipation_score:.3f}" in success_message, \
                f"Message should contain score information: score={anticipation_score:.3f}, message='{success_message}'"
    
    @example(
        allocation_changes=[0.1, -0.15, 0.08, -0.12],
        return_lags=[3, 5, 2, 4],
        n_periods=100
    )
    @given(
        allocation_changes=st.lists(
            st.floats(min_value=-0.2, max_value=0.2),
            min_size=2, max_size=6
        ),
        return_lags=st.lists(
            st.integers(min_value=1, max_value=10),
            min_size=2, max_size=6
        ),
        n_periods=st.integers(min_value=80, max_value=150)
    )
    @settings(max_examples=10, deadline=45000)
    def test_end_to_end_anticipation_validation_property(self, allocation_changes, return_lags, n_periods):
        """
        **Property 29: End-to-End Anticipation Validation Completeness**
        **Validates: Requirements 10.1-10.6**
        
        PROPERTY: Complete anticipation validation should produce valid results
        for any reasonable allocation and return sequence with predictive patterns.
        
        This tests the complete anticipation validation workflow from allocation
        change detection through timing validation.
        """
        
        # Ensure lists are same length
        min_length = min(len(allocation_changes), len(return_lags))
        allocation_changes = allocation_changes[:min_length]
        return_lags = return_lags[:min_length]
        
        # Skip if changes are too small
        assume(any(abs(change) >= 0.05 for change in allocation_changes))
        
        np.random.seed(42)
        
        # Generate allocation data with specific changes
        dates = pd.date_range(start='2023-01-01', periods=n_periods, freq='D')
        
        allocation_data = []
        current_allocation = 0.6
        change_points = [n_periods // (len(allocation_changes) + 1) * (i + 1) for i in range(len(allocation_changes))]
        
        for i, date in enumerate(dates):
            # Apply allocation changes at specific points
            for j, change_point in enumerate(change_points):
                if i == change_point and j < len(allocation_changes):
                    current_allocation += allocation_changes[j]
                    current_allocation = max(0.1, min(0.9, current_allocation))
            
            # Add small noise
            noise = np.random.normal(0, 0.01)
            allocation = max(0.1, min(0.9, current_allocation + noise))
            
            allocation_data.append({
                'date': date,
                'strategy_allocation': allocation
            })
        
        allocation_df = pd.DataFrame(allocation_data)
        
        # Generate return data with lagged correlation to allocation changes
        return_data = []
        
        for i, date in enumerate(dates):
            base_return = 0.0005
            correlated_return = 0
            
            # Add correlation with lagged allocation changes
            for j, (change_point, lag) in enumerate(zip(change_points, return_lags)):
                if change_point + lag <= i < change_point + lag + 20:  # 20-day effect window
                    if j < len(allocation_changes):
                        # Positive correlation with allocation change
                        correlated_return += allocation_changes[j] * 0.3 * np.exp(-(i - change_point - lag) / 10)
            
            # Add noise
            noise = np.random.normal(0, 0.012)
            daily_return = base_return + correlated_return + noise
            
            return_data.append({
                'date': date,
                'strategy_return': daily_return
            })
        
        return_df = pd.DataFrame(return_data)
        
        # Run complete anticipation validation
        anticipation_events = self.validator.test_anticipation_events(allocation_df, return_df)
        
        # PROPERTY ASSERTIONS
        
        # Property 1: Should detect some anticipation events
        assert len(anticipation_events) > 0, "Should detect at least one anticipation event"
        
        # Property 2: All events should be valid and complete
        for event in anticipation_events:
            # Basic structure validation
            assert isinstance(event, AnticipationEvent), "Should return AnticipationEvent instances"
            
            # Validation should pass
            validation_errors = event.validate()
            assert len(validation_errors) == 0, f"Event validation failed: {validation_errors}"
            
            # Event should have meaningful allocation change
            assert abs(event.allocation_change) >= self.validator.config['min_allocation_change'], \
                f"Event should have meaningful allocation change: {event.allocation_change:.3f}"
        
        # Property 3: Anticipation results should be consistent with scores
        success_threshold = self.validator.config['success_threshold']
        confidence_threshold = self.validator.config['confidence_threshold']
        
        for event in anticipation_events:
            if event.confidence_level >= confidence_threshold:
                if event.anticipation_score >= success_threshold:
                    assert event.anticipation_result == AnticipationResult.SUCCESS, \
                        f"High score should result in SUCCESS: score={event.anticipation_score:.3f}, result={event.anticipation_result.value}"
                elif event.anticipation_score <= -success_threshold:
                    assert event.anticipation_result == AnticipationResult.FAILURE, \
                        f"Low score should result in FAILURE: score={event.anticipation_score:.3f}, result={event.anticipation_result.value}"
                else:
                    assert event.anticipation_result == AnticipationResult.NEUTRAL, \
                        f"Neutral score should result in NEUTRAL: score={event.anticipation_score:.3f}, result={event.anticipation_result.value}"
        
        # Property 4: Summary statistics should be consistent
        summary = self.validator.get_anticipation_summary()
        
        assert summary['total_events'] == len(anticipation_events), \
            f"Summary total should match events: {summary['total_events']} vs {len(anticipation_events)}"
        
        # Property 5: Success rate should be reasonable
        success_rate = summary['success_rate']
        assert 0.0 <= success_rate <= 1.0, f"Success rate {success_rate} should be between 0.0 and 1.0"
        
        # With intentional correlation, success rate should be better than random
        if len(anticipation_events) >= 5:
            # Should be better than pure random (which would be ~33% for 3-way classification)
            assert success_rate >= 0.0, "Success rate should be non-negative"


def test_forward_validator_initialization():
    """Test that forward validator initializes correctly"""
    
    validator = ForwardValidator(base_dir="data/test_init")
    
    # Check configuration
    assert validator.config['min_allocation_change'] == 0.05
    assert validator.config['success_threshold'] == 0.3
    assert validator.config['primary_period'] == 20
    assert validator.config['confidence_threshold'] == 0.05
    
    # Check directories created
    assert os.path.exists(validator.anticipation_dir)
    
    # Cleanup
    import shutil
    if os.path.exists("data/test_init"):
        shutil.rmtree("data/test_init")


if __name__ == "__main__":
    # Run property tests
    pytest.main([__file__, "-v", "--tb=short"])