#!/usr/bin/env python3
"""
Property-Based Tests for Confidence System

Tests the correctness properties of the belief confidence and uncertainty
tracking system for institutional validation.

# Feature: institutional-validation-layers, Property 43: Confidence Score Bounds
# Feature: institutional-validation-layers, Property 44: Exposure Reduction Trigger
# Feature: institutional-validation-layers, Property 45: Uncertainty Language Annotation
"""

import pytest
import pandas as pd
import numpy as np
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume
from typing import Dict, List, Any

# Import the system under test
from src.validation.confidence_system import (
    ConfidenceSystem, ConfidenceType, ConfidenceLevel, BeliefConfidence, 
    ConfidenceThresholds
)


class TestConfidenceSystemProperties:
    """Property-based tests for Confidence System"""
    
    def setup_method(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test confidence system with fresh state
        self.confidence = ConfidenceSystem(
            base_dir=os.path.join(self.temp_dir, "confidence")
        )
        
        # Ensure clean state
        self.confidence.current_confidences = {}
        self.confidence.confidence_history = []
    
    def teardown_method(self):
        """Clean up test environment"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    # ========================================================================
    # PROPERTY 43: Confidence Score Bounds
    # ========================================================================
    
    @given(
        regime_similarity=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        similarity_dispersion=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        regime_stability_days=st.integers(min_value=0, max_value=365)
    )
    @settings(max_examples=50, deadline=5000)
    def test_property_43_regime_confidence_bounds(self, regime_similarity: float, similarity_dispersion: float, regime_stability_days: int):
        """
        Property 43: Confidence Score Bounds
        
        For any regime detection inputs, confidence score must be between 0.0 and 1.0.
        
        Validates: Requirements 23.1
        """
        
        # Compute regime confidence
        confidence_score = self.confidence.compute_regime_confidence(
            regime_similarity=regime_similarity,
            similarity_dispersion=similarity_dispersion,
            regime_stability_days=regime_stability_days
        )
        
        # PROPERTY: Confidence score must be bounded
        assert 0.0 <= confidence_score <= 1.0
        assert isinstance(confidence_score, float)
        assert not np.isnan(confidence_score)
        assert not np.isinf(confidence_score)
    
    @given(
        beta_drift_consistency=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        signal_strength=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        data_coverage=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50, deadline=5000)
    def test_property_43_tailwind_confidence_bounds(self, beta_drift_consistency: float, signal_strength: float, data_coverage: float):
        """
        Property 43: Tailwind Confidence Score Bounds
        
        For any tailwind inputs, confidence score must be between 0.0 and 1.0.
        
        Validates: Requirements 23.2
        """
        
        # Compute tailwind confidence
        confidence_score = self.confidence.compute_tailwind_confidence(
            beta_drift_consistency=beta_drift_consistency,
            signal_strength=signal_strength,
            data_coverage=data_coverage
        )
        
        # PROPERTY: Confidence score must be bounded
        assert 0.0 <= confidence_score <= 1.0
        assert isinstance(confidence_score, float)
        assert not np.isnan(confidence_score)
        assert not np.isinf(confidence_score)
    
    @given(
        regime_confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        tailwind_confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        data_freshness_hours=st.floats(min_value=0.0, max_value=168.0, allow_nan=False, allow_infinity=False)  # Up to 1 week
    )
    @settings(max_examples=50, deadline=5000)
    def test_property_43_allocation_confidence_bounds(self, regime_confidence: float, tailwind_confidence: float, data_freshness_hours: float):
        """
        Property 43: Allocation Confidence Score Bounds
        
        For any allocation inputs, confidence score must be between 0.0 and 1.0.
        
        Validates: Requirements 23.3
        """
        
        # Compute allocation confidence
        confidence_score = self.confidence.compute_allocation_confidence(
            regime_confidence=regime_confidence,
            tailwind_confidence=tailwind_confidence,
            data_freshness_hours=data_freshness_hours
        )
        
        # PROPERTY: Confidence score must be bounded
        assert 0.0 <= confidence_score <= 1.0
        assert isinstance(confidence_score, float)
        assert not np.isnan(confidence_score)
        assert not np.isinf(confidence_score)
    
    # ========================================================================
    # PROPERTY 44: Exposure Reduction Trigger
    # ========================================================================
    
    @given(
        confidence_score=st.floats(min_value=0.0, max_value=0.49, allow_nan=False, allow_infinity=False),  # Below threshold
        output_type=st.sampled_from(['regime_detection', 'strategy_tailwinds', 'allocation_decisions'])
    )
    @settings(max_examples=30, deadline=5000)
    def test_property_44_exposure_reduction_trigger(self, confidence_score: float, output_type: str):
        """
        Property 44: Exposure Reduction Trigger
        
        When confidence score falls below threshold (0.5), exposure reduction should be triggered.
        
        Validates: Requirements 23.4
        """
        
        # Mock Risk_Coordinator to capture calls
        class MockRiskCoordinator:
            def __init__(self):
                self.exposure_reduction_called = False
                self.no_edge_called = False
                self.suggested_exposure = None
                
            def suggest_exposure_reduction(self, new_exposure, reason, confidence_factors):
                self.exposure_reduction_called = True
                self.suggested_exposure = new_exposure
                
            def enter_no_edge_state(self, reason, confidence_factors):
                self.no_edge_called = True
        
        mock_risk = MockRiskCoordinator()
        self.confidence.risk_coordinator = mock_risk
        
        # Update belief confidence with low score
        belief_confidence = self.confidence.update_belief_confidence(
            output_type=output_type,
            output_value="test_output",
            confidence_score=confidence_score,
            confidence_sources={"test_source": confidence_score},
            data_freshness_hours=1.0
        )
        
        # PROPERTY: Low confidence must trigger appropriate action
        if confidence_score < self.confidence.thresholds.no_edge_threshold:
            # Should trigger NO_EDGE state
            assert mock_risk.no_edge_called
        elif confidence_score < self.confidence.thresholds.exposure_reduction_threshold:
            # Should trigger exposure reduction
            assert mock_risk.exposure_reduction_called
            assert mock_risk.suggested_exposure is not None
            assert 0.0 <= mock_risk.suggested_exposure <= 0.6  # Capped at 60%
    
    @given(
        confidence_score=st.floats(min_value=0.51, max_value=1.0, allow_nan=False, allow_infinity=False),  # Above threshold
        output_type=st.sampled_from(['regime_detection', 'strategy_tailwinds', 'allocation_decisions'])
    )
    @settings(max_examples=20, deadline=5000)
    def test_property_44_no_exposure_reduction_high_confidence(self, confidence_score: float, output_type: str):
        """
        Property 44: No Exposure Reduction for High Confidence
        
        When confidence score is above threshold, no exposure reduction should be triggered.
        """
        
        # Mock Risk_Coordinator to capture calls
        class MockRiskCoordinator:
            def __init__(self):
                self.exposure_reduction_called = False
                self.no_edge_called = False
                
            def suggest_exposure_reduction(self, new_exposure, reason, confidence_factors):
                self.exposure_reduction_called = True
                
            def enter_no_edge_state(self, reason, confidence_factors):
                self.no_edge_called = True
        
        mock_risk = MockRiskCoordinator()
        self.confidence.risk_coordinator = mock_risk
        
        # Update belief confidence with high score
        belief_confidence = self.confidence.update_belief_confidence(
            output_type=output_type,
            output_value="test_output",
            confidence_score=confidence_score,
            confidence_sources={"test_source": confidence_score},
            data_freshness_hours=1.0
        )
        
        # PROPERTY: High confidence must not trigger exposure reduction
        assert not mock_risk.exposure_reduction_called
        assert not mock_risk.no_edge_called
    
    # ========================================================================
    # PROPERTY 45: Uncertainty Language Annotation
    # ========================================================================
    
    @given(
        confidence_score=st.floats(min_value=0.0, max_value=0.59, allow_nan=False, allow_infinity=False),  # Below narrative threshold
        output_type=st.sampled_from(['regime_detection', 'strategy_tailwinds', 'allocation_decisions'])
    )
    @settings(max_examples=30, deadline=5000)
    def test_property_45_uncertainty_language_annotation(self, confidence_score: float, output_type: str):
        """
        Property 45: Uncertainty Language Annotation
        
        When confidence score is below narrative threshold (0.6), uncertainty language should be added.
        
        Validates: Requirements 23.5
        """
        
        # Update belief confidence with low score
        belief_confidence = self.confidence.update_belief_confidence(
            output_type=output_type,
            output_value="test_output",
            confidence_score=confidence_score,
            confidence_sources={"test_source": confidence_score},
            data_freshness_hours=1.0
        )
        
        # Check uncertainty language
        should_add, description = self.confidence.should_add_uncertainty_language(output_type)
        
        # PROPERTY: Low confidence must trigger uncertainty language
        assert should_add is True
        assert isinstance(description, str)
        assert len(description) > 0
        
        # PROPERTY: Description must match confidence level
        if confidence_score >= 0.5:
            assert "medium confidence" in description.lower() or "moderate uncertainty" in description.lower()
        elif confidence_score >= 0.3:
            assert "low confidence" in description.lower() or "significant uncertainty" in description.lower()
        else:
            assert "very low confidence" in description.lower() or "high uncertainty" in description.lower()
    
    @given(
        confidence_score=st.floats(min_value=0.61, max_value=1.0, allow_nan=False, allow_infinity=False),  # Above narrative threshold
        output_type=st.sampled_from(['regime_detection', 'strategy_tailwinds', 'allocation_decisions'])
    )
    @settings(max_examples=20, deadline=5000)
    def test_property_45_no_uncertainty_language_high_confidence(self, confidence_score: float, output_type: str):
        """
        Property 45: No Uncertainty Language for High Confidence
        
        When confidence score is above narrative threshold, no uncertainty language should be added.
        """
        
        # Update belief confidence with high score
        belief_confidence = self.confidence.update_belief_confidence(
            output_type=output_type,
            output_value="test_output",
            confidence_score=confidence_score,
            confidence_sources={"test_source": confidence_score},
            data_freshness_hours=1.0
        )
        
        # Check uncertainty language
        should_add, description = self.confidence.should_add_uncertainty_language(output_type)
        
        # PROPERTY: High confidence must not trigger uncertainty language
        assert should_add is False
        assert description == ""
    
    # ========================================================================
    # CONFIDENCE LEVEL CLASSIFICATION PROPERTIES
    # ========================================================================
    
    @given(
        confidence_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50, deadline=5000)
    def test_property_confidence_level_classification(self, confidence_score: float):
        """
        Property: Confidence Level Classification
        
        Confidence levels must be correctly classified based on score ranges.
        """
        
        # Classify confidence level
        confidence_level = self.confidence._classify_confidence_level(confidence_score)
        
        # PROPERTY: Classification must match score ranges
        if confidence_score >= 0.9:
            assert confidence_level == ConfidenceLevel.VERY_HIGH
        elif confidence_score >= 0.7:
            assert confidence_level == ConfidenceLevel.HIGH
        elif confidence_score >= 0.5:
            assert confidence_level == ConfidenceLevel.MEDIUM
        elif confidence_score >= 0.3:
            assert confidence_level == ConfidenceLevel.LOW
        else:
            assert confidence_level == ConfidenceLevel.VERY_LOW
    
    # ========================================================================
    # DATA FRESHNESS PROPERTIES
    # ========================================================================
    
    @given(
        base_confidence=st.floats(min_value=0.5, max_value=1.0, allow_nan=False, allow_infinity=False),
        data_freshness_hours=st.floats(min_value=0.0, max_value=48.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=30, deadline=5000)
    def test_property_data_freshness_penalty(self, base_confidence: float, data_freshness_hours: float):
        """
        Property: Data Freshness Penalty
        
        Older data should reduce confidence scores.
        """
        
        # Compute allocation confidence with different freshness
        fresh_confidence = self.confidence.compute_allocation_confidence(
            regime_confidence=base_confidence,
            tailwind_confidence=base_confidence,
            data_freshness_hours=0.0  # Fresh data
        )
        
        stale_confidence = self.confidence.compute_allocation_confidence(
            regime_confidence=base_confidence,
            tailwind_confidence=base_confidence,
            data_freshness_hours=data_freshness_hours
        )
        
        # PROPERTY: Stale data should not increase confidence
        assert stale_confidence <= fresh_confidence
        
        # PROPERTY: Very stale data should significantly reduce confidence
        if data_freshness_hours > self.confidence.thresholds.data_freshness_max_hours:
            assert stale_confidence < fresh_confidence * 0.5  # At least 50% reduction
    
    # ========================================================================
    # CONFIDENCE SOURCES VALIDATION PROPERTIES
    # ========================================================================
    
    @given(
        confidence_sources=st.dictionaries(
            keys=st.text(min_size=1, max_size=20),
            values=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=5
        ),
        output_type=st.sampled_from(['regime_detection', 'strategy_tailwinds', 'allocation_decisions'])
    )
    @settings(max_examples=30, deadline=5000)
    def test_property_confidence_sources_validation(self, confidence_sources: Dict[str, float], output_type: str):
        """
        Property: Confidence Sources Validation
        
        All confidence sources must be valid and within bounds.
        """
        
        # Compute overall confidence as average of sources
        overall_confidence = np.mean(list(confidence_sources.values()))
        
        # Update belief confidence
        belief_confidence = self.confidence.update_belief_confidence(
            output_type=output_type,
            output_value="test_output",
            confidence_score=overall_confidence,
            confidence_sources=confidence_sources,
            data_freshness_hours=1.0
        )
        
        # PROPERTY: All source scores must be valid
        for source, score in belief_confidence.confidence_sources.items():
            assert 0.0 <= score <= 1.0
            assert isinstance(score, float)
            assert not np.isnan(score)
            assert not np.isinf(score)
        
        # PROPERTY: Uncertainty factors should be identified for low sources
        for source, score in confidence_sources.items():
            if score < 0.5:
                # Should appear in uncertainty factors
                uncertainty_text = " ".join(belief_confidence.uncertainty_factors)
                assert source.replace('_', ' ').lower() in uncertainty_text.lower()
    
    # ========================================================================
    # CONFIDENCE SUMMARY PROPERTIES
    # ========================================================================
    
    def test_property_confidence_summary_consistency(self):
        """
        Property: Confidence Summary Consistency
        
        Confidence summary must accurately reflect current state.
        """
        
        # Add multiple confidence records
        confidences = [
            ("regime_detection", 0.8),
            ("strategy_tailwinds", 0.6),
            ("allocation_decisions", 0.4)
        ]
        
        for output_type, score in confidences:
            self.confidence.update_belief_confidence(
                output_type=output_type,
                output_value="test_output",
                confidence_score=score,
                confidence_sources={"test_source": score},
                data_freshness_hours=1.0
            )
        
        # Get summary
        summary = self.confidence.get_confidence_summary()
        
        # PROPERTY: Summary must reflect all confidences
        assert len(summary['current_confidences']) == 3
        
        # PROPERTY: Overall confidence must be average
        expected_overall = np.mean([0.8, 0.6, 0.4])
        assert abs(summary['overall_confidence'] - expected_overall) < 0.001
        
        # PROPERTY: Thresholds must be correctly applied
        assert summary['no_edge_state'] == (expected_overall < self.confidence.thresholds.no_edge_threshold)
        assert summary['exposure_reduction_needed'] == (expected_overall < self.confidence.thresholds.exposure_reduction_threshold)
        assert summary['uncertainty_narrative_needed'] == (expected_overall < self.confidence.thresholds.narrative_uncertainty_threshold)
    
    # ========================================================================
    # SCHEMA ENFORCEMENT PROPERTIES
    # ========================================================================
    
    def test_property_confidence_schema_enforcement(self):
        """
        Property: Confidence Schema Enforcement
        
        Confidence data must conform to required schema.
        """
        
        # Update confidence
        belief_confidence = self.confidence.update_belief_confidence(
            output_type="regime_detection",
            output_value="test_regime",
            confidence_score=0.75,
            confidence_sources={"similarity": 0.8, "stability": 0.7},
            data_freshness_hours=2.0
        )
        
        # Check if parquet file was created
        parquet_file = os.path.join(self.confidence.base_dir, "belief_confidence.parquet")
        assert os.path.exists(parquet_file)
        
        # Load and validate schema
        df = pd.read_parquet(parquet_file)
        
        # PROPERTY: Required columns must exist
        required_columns = [
            'timestamp', 'output_type', 'output_value', 'confidence_score',
            'confidence_sources', 'confidence_level', 'uncertainty_factors', 'data_freshness_hours'
        ]
        
        for col in required_columns:
            assert col in df.columns
        
        # PROPERTY: Data types must be correct
        assert pd.api.types.is_datetime64_any_dtype(df['timestamp'])
        assert pd.api.types.is_string_dtype(df['output_type'])
        assert pd.api.types.is_float_dtype(df['confidence_score'])
        assert pd.api.types.is_float_dtype(df['data_freshness_hours'])
        
        # PROPERTY: Confidence scores must be valid
        assert (df['confidence_score'] >= 0.0).all()
        assert (df['confidence_score'] <= 1.0).all()


def test_belief_confidence_validation():
    """Test BeliefConfidence validation"""
    
    # Valid confidence
    valid_confidence = BeliefConfidence(
        timestamp=datetime.now(),
        output_type=ConfidenceType.REGIME_DETECTION,
        output_value="test_regime",
        confidence_score=0.75,
        confidence_sources={"similarity": 0.8, "stability": 0.7},
        confidence_level=ConfidenceLevel.HIGH,
        uncertainty_factors=["Low data coverage (0.45)"],
        data_freshness_hours=2.0
    )
    
    errors = valid_confidence.validate()
    assert len(errors) == 0
    
    # Invalid confidence - bad score
    invalid_confidence = BeliefConfidence(
        timestamp=datetime.now(),
        output_type=ConfidenceType.REGIME_DETECTION,
        output_value="test_regime",
        confidence_score=1.5,  # Invalid score > 1.0
        confidence_sources={"similarity": 1.2},  # Invalid source score
        confidence_level=ConfidenceLevel.HIGH,
        uncertainty_factors="not_a_list",  # Should be list
        data_freshness_hours=-1.0  # Negative hours
    )
    
    errors = invalid_confidence.validate()
    assert len(errors) > 0
    assert any("Confidence score" in error and "outside bounds" in error for error in errors)
    assert any("Source confidence" in error and "outside bounds" in error for error in errors)
    assert any("Uncertainty factors must be a list" in error for error in errors)
    assert any("Data freshness hours cannot be negative" in error for error in errors)


def test_confidence_thresholds_validation():
    """Test ConfidenceThresholds validation"""
    
    # Valid thresholds
    valid_thresholds = ConfidenceThresholds(
        exposure_reduction_threshold=0.5,
        no_edge_threshold=0.3,
        narrative_uncertainty_threshold=0.6,
        data_freshness_max_hours=24.0
    )
    
    errors = valid_thresholds.validate()
    assert len(errors) == 0
    
    # Invalid thresholds
    invalid_thresholds = ConfidenceThresholds(
        exposure_reduction_threshold=1.5,  # > 1.0
        no_edge_threshold=-0.1,  # < 0.0
        data_freshness_max_hours=-5.0  # Negative
    )
    
    errors = invalid_thresholds.validate()
    assert len(errors) > 0
    assert any("exposure_reduction_threshold" in error and "outside bounds" in error for error in errors)
    assert any("no_edge_threshold" in error and "outside bounds" in error for error in errors)
    assert any("Data freshness max hours must be positive" in error for error in errors)


if __name__ == "__main__":
    pytest.main([__file__])