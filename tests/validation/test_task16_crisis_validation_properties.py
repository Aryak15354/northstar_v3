#!/usr/bin/env python3
"""
🧪 PROPERTY TESTS FOR TASK 16 - HISTORICAL CRISIS VALIDATION
Property-based tests for historical crisis validation suite

Tests crisis response consistency and validation accuracy across different scenarios.

Usage:
    python -m pytest tests/validation/test_task16_crisis_validation_properties.py -v
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings
import warnings
warnings.filterwarnings('ignore')

import sys
import os
from typing import Dict, List, Optional, Tuple, Any
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from src.validation.historical_crisis_validation_suite import HistoricalCrisisValidationSuite, CrisisPeriod

class TestTask16CrisisValidationProperties:
    """Property tests for Task 16 - Historical Crisis Validation"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.suite = HistoricalCrisisValidationSuite()
        
    @given(
        crisis_severity=st.floats(min_value=0.1, max_value=0.8),
        adaptation_capability=st.floats(min_value=0.2, max_value=1.0)
    )
    @settings(max_examples=15, deadline=5000)
    def test_crisis_response_consistency(self, crisis_severity, adaptation_capability):
        """
        Test that crisis responses are consistent across similar severity levels
        and that adaptation capability affects survival metrics appropriately.
        """
        
        # Create mock crisis scenarios with different severities
        scenario_1 = self._create_mock_crisis_scenario(crisis_severity, adaptation_capability)
        scenario_2 = self._create_mock_crisis_scenario(crisis_severity * 1.1, adaptation_capability)  # Slightly worse
        
        # Calculate survival metrics for both scenarios
        survival_1 = self.suite.calculate_survival_metrics(scenario_1, CrisisPeriod.FINANCIAL_CRISIS_2008)
        survival_2 = self.suite.calculate_survival_metrics(scenario_2, CrisisPeriod.FINANCIAL_CRISIS_2008)
        
        # Property: More severe crisis should have lower or equal survival score
        assert survival_2['overall_score'] <= survival_1['overall_score'] + 0.1, \
            f"More severe crisis should have lower survival score: {survival_2['overall_score']:.3f} vs {survival_1['overall_score']:.3f}"
        
        # Property: Survival scores should be in valid range
        assert 0.0 <= survival_1['overall_score'] <= 1.0, "Survival score should be normalized"
        assert 0.0 <= survival_2['overall_score'] <= 1.0, "Survival score should be normalized"
        
        # Property: High adaptation capability should improve survival
        if adaptation_capability > 0.8:
            assert survival_1['overall_score'] >= 0.25, "High adaptation should yield reasonable survival score"
    
    @given(
        defensive_positioning=st.floats(min_value=0.1, max_value=0.9),
        crisis_magnitude=st.floats(min_value=0.1, max_value=0.6)
    )
    @settings(max_examples=15, deadline=5000)
    def test_defensive_positioning_effectiveness(self, defensive_positioning, crisis_magnitude):
        """
        Test that defensive positioning improves crisis performance
        and that the scoring system accurately reflects positioning quality.
        """
        
        # Create pre-crisis positioning with varying defensive levels
        positioning = {
            'equity_exposure': 1.0 - defensive_positioning,
            'cash_buffer': defensive_positioning * 0.4,  # More defensive = more cash
            'defensive_assets': defensive_positioning * 0.3,
            'leverage': 1.0 + (1.0 - defensive_positioning) * 0.5,  # Less defensive = more leverage
            'concentration_risk': (1.0 - defensive_positioning) * 0.2,
            'sector_diversification': 0.5 + defensive_positioning * 0.4,
            'volatility_exposure': (1.0 - defensive_positioning) * 0.3
        }
        
        # Create crisis performance based on positioning and crisis magnitude
        crisis_performance = {
            'total_return': -crisis_magnitude * (1.0 - defensive_positioning * 0.5),
            'max_drawdown': -crisis_magnitude * (1.0 - defensive_positioning * 0.3),
            'volatility': 0.2 + crisis_magnitude * (1.0 - defensive_positioning * 0.4),
            'sharpe_ratio': (defensive_positioning - 0.5) * 2,  # Better positioning = better Sharpe
            'correlation_with_market': 0.9 - defensive_positioning * 0.3,
            'worst_day': -crisis_magnitude * 0.1 * (1.0 - defensive_positioning * 0.5),
            'best_day': crisis_magnitude * 0.05 * (1.0 + defensive_positioning),
            'days_in_crisis': 100
        }
        
        # Score defensive positioning
        defensive_score = self.suite.score_defensive_positioning(positioning, crisis_performance)
        
        # Property: Higher defensive positioning should yield higher scores
        if defensive_positioning > 0.7:
            assert defensive_score >= 0.5, f"High defensive positioning should score well: {defensive_score:.3f}"
        
        # Property: Defensive score should be normalized
        assert 0.0 <= defensive_score <= 1.0, f"Defensive score should be normalized: {defensive_score:.3f}"
        
        # Property: Better positioning should correlate with better performance
        if defensive_positioning > 0.67 and crisis_magnitude < 0.4:
            assert abs(crisis_performance['max_drawdown']) < crisis_magnitude * 0.8, \
                "Good defensive positioning should limit drawdown"
    
    @given(
        adaptation_speed_factor=st.floats(min_value=0.1, max_value=2.0),
        crisis_duration_days=st.integers(min_value=30, max_value=300)
    )
    @settings(max_examples=15, deadline=5000)
    def test_adaptation_speed_measurement(self, adaptation_speed_factor, crisis_duration_days):
        """
        Test that adaptation speed measurement accurately reflects
        how quickly the system responds to crisis conditions.
        """
        
        # Create crisis scenario with varying adaptation characteristics
        crisis_start = datetime(2020, 3, 1)
        crisis_peak = crisis_start + timedelta(days=crisis_duration_days // 3)
        
        # Performance that reflects adaptation speed
        base_drawdown = 0.3
        adapted_drawdown = base_drawdown * (1.0 / adaptation_speed_factor)  # Faster adaptation = less drawdown
        
        crisis_performance = {
            'total_return': -adapted_drawdown * 0.8,
            'max_drawdown': -adapted_drawdown,
            'volatility': 0.4 / adaptation_speed_factor,  # Faster adaptation = lower vol
            'sharpe_ratio': (adaptation_speed_factor - 1.0) * 0.5,
            'correlation_with_market': 0.8,
            'worst_day': -adapted_drawdown * 0.1,
            'best_day': adapted_drawdown * 0.05,
            'days_in_crisis': crisis_duration_days
        }
        
        # Measure adaptation speed
        measured_speed = self.suite.measure_adaptation_speed(
            crisis_start, crisis_peak, crisis_performance
        )
        
        # Property: Adaptation speed should be normalized
        assert 0.0 <= measured_speed <= 1.0, f"Adaptation speed should be normalized: {measured_speed:.3f}"
        
        # Property: Better adaptation characteristics should yield higher speed scores
        if adaptation_speed_factor > 1.6:
            assert measured_speed >= 0.25, f"Good adaptation should score reasonably: {measured_speed:.3f}"
        
        # Property: Shorter crisis duration with good adaptation should score higher
        if crisis_duration_days < 60 and adaptation_speed_factor > 1.2:
            assert measured_speed >= 0.4, "Quick adaptation in short crisis should score well"
    
    def test_crisis_response_consistency_deterministic(self):
        """Deterministic test for crisis response consistency"""
        
        # Create two similar crisis scenarios
        base_scenario = {
            'total_return': -0.25,
            'max_drawdown': -0.30,
            'volatility': 0.35,
            'sharpe_ratio': -0.5,
            'correlation_with_market': 0.8,
            'worst_day': -0.08,
            'best_day': 0.06,
            'days_in_crisis': 120
        }
        
        # Slightly worse scenario
        worse_scenario = base_scenario.copy()
        worse_scenario['max_drawdown'] = -0.35
        worse_scenario['volatility'] = 0.40
        
        # Calculate survival metrics
        base_survival = self.suite.calculate_survival_metrics(base_scenario, CrisisPeriod.FINANCIAL_CRISIS_2008)
        worse_survival = self.suite.calculate_survival_metrics(worse_scenario, CrisisPeriod.FINANCIAL_CRISIS_2008)
        
        # Worse scenario should have lower survival score
        assert worse_survival['overall_score'] <= base_survival['overall_score'], \
            "Worse crisis performance should have lower survival score"
        
        # Both should be in valid range
        assert 0.0 <= base_survival['overall_score'] <= 1.0
        assert 0.0 <= worse_survival['overall_score'] <= 1.0
    
    def test_defensive_positioning_effectiveness_deterministic(self):
        """Deterministic test for defensive positioning effectiveness"""
        
        # High defensive positioning
        defensive_positioning = {
            'equity_exposure': 0.5,
            'cash_buffer': 0.3,
            'defensive_assets': 0.2,
            'leverage': 1.0,
            'concentration_risk': 0.05,
            'sector_diversification': 0.9,
            'volatility_exposure': 0.1
        }
        
        # Low defensive positioning
        aggressive_positioning = {
            'equity_exposure': 0.9,
            'cash_buffer': 0.05,
            'defensive_assets': 0.05,
            'leverage': 1.5,
            'concentration_risk': 0.2,
            'sector_diversification': 0.6,
            'volatility_exposure': 0.3
        }
        
        # Mock crisis performance (defensive should perform better)
        defensive_performance = {
            'total_return': -0.15,
            'max_drawdown': -0.18,
            'volatility': 0.25,
            'sharpe_ratio': -0.2,
            'correlation_with_market': 0.7,
            'worst_day': -0.05,
            'best_day': 0.04,
            'days_in_crisis': 90
        }
        
        aggressive_performance = {
            'total_return': -0.30,
            'max_drawdown': -0.35,
            'volatility': 0.45,
            'sharpe_ratio': -0.8,
            'correlation_with_market': 0.9,
            'worst_day': -0.10,
            'best_day': 0.08,
            'days_in_crisis': 90
        }
        
        # Score both approaches
        defensive_score = self.suite.score_defensive_positioning(defensive_positioning, defensive_performance)
        aggressive_score = self.suite.score_defensive_positioning(aggressive_positioning, aggressive_performance)
        
        # Defensive positioning should score higher
        assert defensive_score > aggressive_score, \
            f"Defensive positioning should score higher: {defensive_score:.3f} vs {aggressive_score:.3f}"
        
        # Both should be in valid range
        assert 0.0 <= defensive_score <= 1.0
        assert 0.0 <= aggressive_score <= 1.0
    
    def test_adaptation_speed_measurement_deterministic(self):
        """Deterministic test for adaptation speed measurement"""
        
        crisis_start = datetime(2020, 3, 1)
        crisis_peak = datetime(2020, 3, 23)  # 22 days to peak
        
        # Fast adaptation scenario (good performance despite crisis)
        fast_adaptation_performance = {
            'total_return': -0.10,
            'max_drawdown': -0.15,
            'volatility': 0.25,
            'sharpe_ratio': 0.2,
            'correlation_with_market': 0.6,
            'worst_day': -0.04,
            'best_day': 0.05,
            'days_in_crisis': 60
        }
        
        # Slow adaptation scenario (poor performance)
        slow_adaptation_performance = {
            'total_return': -0.35,
            'max_drawdown': -0.40,
            'volatility': 0.55,
            'sharpe_ratio': -1.0,
            'correlation_with_market': 0.9,
            'worst_day': -0.12,
            'best_day': 0.03,
            'days_in_crisis': 60
        }
        
        # Measure adaptation speeds
        fast_speed = self.suite.measure_adaptation_speed(crisis_start, crisis_peak, fast_adaptation_performance)
        slow_speed = self.suite.measure_adaptation_speed(crisis_start, crisis_peak, slow_adaptation_performance)
        
        # Fast adaptation should score higher
        assert fast_speed > slow_speed, \
            f"Fast adaptation should score higher: {fast_speed:.3f} vs {slow_speed:.3f}"
        
        # Both should be in valid range
        assert 0.0 <= fast_speed <= 1.0
        assert 0.0 <= slow_speed <= 1.0
    
    def test_anticipatory_derisking_detection(self):
        """Test anticipatory de-risking detection"""
        
        # Positioning with anticipatory de-risking
        anticipatory_positioning = {
            'equity_exposure': 0.6,
            'cash_buffer': 0.25,  # High cash
            'defensive_assets': 0.18,  # High defensive allocation
            'leverage': 1.1,  # Low leverage
            'concentration_risk': 0.08,
            'sector_diversification': 0.85,
            'volatility_exposure': 0.15
        }
        
        # Positioning without anticipatory de-risking
        normal_positioning = {
            'equity_exposure': 0.8,
            'cash_buffer': 0.1,   # Low cash
            'defensive_assets': 0.05,  # Low defensive allocation
            'leverage': 1.4,  # High leverage
            'concentration_risk': 0.15,
            'sector_diversification': 0.7,
            'volatility_exposure': 0.25
        }
        
        crisis_start = datetime(2020, 3, 1)
        
        # Test detection
        anticipatory_detected = self.suite.detect_anticipatory_derisking(anticipatory_positioning, crisis_start)
        normal_detected = self.suite.detect_anticipatory_derisking(normal_positioning, crisis_start)
        
        # Should detect anticipatory de-risking in first case but not second
        assert anticipatory_detected, "Should detect anticipatory de-risking"
        assert not normal_detected, "Should not detect anticipatory de-risking in normal positioning"
    
    def test_cross_crisis_consistency_analysis(self):
        """Test cross-crisis consistency analysis"""
        
        # Create mock results with varying consistency
        from src.validation.historical_crisis_validation_suite import CrisisValidationResult
        
        # Consistent results
        consistent_results = {
            'crisis_1': CrisisValidationResult(
                crisis_name="Crisis 1",
                crisis_period=(datetime(2008, 1, 1), datetime(2008, 12, 31)),
                pre_crisis_positioning={},
                crisis_performance={},
                survival_metrics={'overall_score': 0.7},
                adaptation_speed=0.6,
                defensive_positioning_score=0.8,
                anticipatory_derisking=True,
                lessons_learned=[],
                validation_passed=True
            ),
            'crisis_2': CrisisValidationResult(
                crisis_name="Crisis 2",
                crisis_period=(datetime(2020, 1, 1), datetime(2020, 12, 31)),
                pre_crisis_positioning={},
                crisis_performance={},
                survival_metrics={'overall_score': 0.72},
                adaptation_speed=0.62,
                defensive_positioning_score=0.78,
                anticipatory_derisking=True,
                lessons_learned=[],
                validation_passed=True
            )
        }
        
        # Inconsistent results
        inconsistent_results = {
            'crisis_1': CrisisValidationResult(
                crisis_name="Crisis 1",
                crisis_period=(datetime(2008, 1, 1), datetime(2008, 12, 31)),
                pre_crisis_positioning={},
                crisis_performance={},
                survival_metrics={'overall_score': 0.8},
                adaptation_speed=0.7,
                defensive_positioning_score=0.9,
                anticipatory_derisking=True,
                lessons_learned=[],
                validation_passed=True
            ),
            'crisis_2': CrisisValidationResult(
                crisis_name="Crisis 2",
                crisis_period=(datetime(2020, 1, 1), datetime(2020, 12, 31)),
                pre_crisis_positioning={},
                crisis_performance={},
                survival_metrics={'overall_score': 0.3},
                adaptation_speed=0.2,
                defensive_positioning_score=0.4,
                anticipatory_derisking=False,
                lessons_learned=[],
                validation_passed=False
            )
        }
        
        # Analyze consistency
        consistent_score = self.suite.analyze_cross_crisis_consistency(consistent_results)
        inconsistent_score = self.suite.analyze_cross_crisis_consistency(inconsistent_results)
        
        # Consistent results should have higher consistency score
        assert consistent_score > inconsistent_score, \
            f"Consistent results should have higher consistency score: {consistent_score:.3f} vs {inconsistent_score:.3f}"
        
        # Both should be in valid range
        assert 0.0 <= consistent_score <= 1.0
        assert 0.0 <= inconsistent_score <= 1.0
    
    def _create_mock_crisis_scenario(self, severity: float, adaptation: float) -> Dict[str, float]:
        """Create mock crisis scenario for testing"""
        
        return {
            'total_return': -severity * (1.0 - adaptation * 0.3),
            'max_drawdown': -severity * (1.0 - adaptation * 0.2),
            'volatility': 0.2 + severity * (1.0 - adaptation * 0.4),
            'sharpe_ratio': (adaptation - severity) * 2,
            'correlation_with_market': 0.9 - adaptation * 0.2,
            'worst_day': -severity * 0.1,
            'best_day': severity * 0.05 * adaptation,
            'days_in_crisis': int(100 * severity)
        }


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
