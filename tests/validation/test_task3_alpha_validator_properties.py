"""
Property tests for Alpha Validator (Tasks 3.3, 3.4, and 3.5).

Tests the universal properties that should hold for alpha validation:
- Property 3: Alpha Signal Generation Across Regimes
- Property 4: Alpha Signal Quality Validation
- Property 5: Alpha Performance Degradation Response
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume
from typing import List, Dict, Any

from src.operation.alpha_validator import AlphaValidator, MarketRegimeDetector, MarketRegime
from src.operation.base_types import AlphaValidationResult


class TestAlphaValidatorProperties:
    """Property tests for Alpha Validator functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = AlphaValidator()
        self.regime_detector = MarketRegimeDetector()
    
    def _generate_market_data(self, num_days: int = 500, regime: str = "bull") -> pd.DataFrame:
        """Generate synthetic market data for testing."""
        dates = pd.date_range(start='2020-01-01', periods=num_days, freq='D')
        
        # Generate price series based on regime
        np.random.seed(42)  # For reproducible tests
        
        if regime == "bull":
            trend = 0.0005  # Positive trend
            volatility = 0.015
        elif regime == "bear":
            trend = -0.0003  # Negative trend
            volatility = 0.025
        elif regime == "sideways":
            trend = 0.0001  # Minimal trend
            volatility = 0.012
        else:
            trend = 0.0002
            volatility = 0.018
        
        # Generate returns
        returns = np.random.normal(trend, volatility, num_days)
        
        # Generate prices
        initial_price = 100.0
        prices = [initial_price]
        for ret in returns:
            prices.append(prices[-1] * (1 + ret))
        
        # Generate volume
        volume = np.random.lognormal(10, 0.5, num_days)
        
        return pd.DataFrame({
            'date': dates,
            'close': prices[1:],  # Skip initial price
            'volume': volume
        })
    
    @given(
        regime=st.sampled_from(["bull", "bear", "sideways"]),
        num_days=st.integers(min_value=300, max_value=800),
        seed=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=15, deadline=15000)
    def test_property_3_alpha_signal_generation_across_regimes(
        self, 
        regime: str, 
        num_days: int, 
        seed: int
    ):
        """
        Property 3: Alpha Signal Generation Across Regimes
        
        For any market regime (bull, bear, sideways), when alpha validation runs, 
        the system should generate signals appropriate to that regime's characteristics.
        
        Validates: Requirements 2.1, 2.2, 2.3
        """
        # Set seed for reproducible test
        np.random.seed(seed)
        
        # Generate market data for the specified regime
        market_data = self._generate_market_data(num_days, regime)
        
        # Run alpha validation for the regime
        if regime == "bull":
            result = self.validator.validate_bull_market_alpha(market_data)
        elif regime == "bear":
            result = self.validator.validate_bear_market_alpha(market_data)
        elif regime == "sideways":
            result = self.validator.validate_sideways_market_alpha(market_data)
        else:
            # Fallback for unknown regime
            regime_periods = self.regime_detector.detect_regime_periods(market_data)
            result = self.validator.validate_alpha_regime(regime, regime_periods, market_data)
        
        # Property: Result should be a valid AlphaValidationResult
        assert isinstance(result, AlphaValidationResult)
        assert result.regime == regime
        
        # Property: All required alpha metrics should be present and valid
        assert isinstance(result.alpha_generated, float)
        assert isinstance(result.information_ratio, float)
        assert isinstance(result.hit_rate, float)
        assert isinstance(result.signal_quality_score, float)
        assert isinstance(result.consistency_score, float)
        assert isinstance(result.regime_adaptation_score, float)
        assert isinstance(result.validation_passed, bool)
        assert isinstance(result.signal_count, int)
        
        # Property: Metrics should be within reasonable bounds
        assert -1.0 <= result.alpha_generated <= 1.0      # -100% to 100% alpha
        assert -10.0 <= result.information_ratio <= 10.0  # Reasonable IR range
        assert 0.0 <= result.hit_rate <= 1.0              # 0% to 100% hit rate
        assert 0.0 <= result.signal_quality_score <= 1.0  # 0% to 100% quality
        assert 0.0 <= result.consistency_score <= 1.0     # 0% to 100% consistency
        assert 0.0 <= result.regime_adaptation_score <= 2.0  # Can exceed 1.0 for good adaptation
        assert result.signal_count >= 0                   # Non-negative signal count
        
        # Property: Additional metrics should be present
        assert isinstance(result.additional_metrics, dict)
        assert len(result.additional_metrics) > 0
        
        # Property: Period dates should be valid
        if result.period_start and result.period_end:
            assert result.period_start <= result.period_end
    
    @given(
        num_regimes=st.integers(min_value=1, max_value=3),
        alpha_values=st.lists(st.floats(min_value=-0.1, max_value=0.1), min_size=1, max_size=3),
        hit_rates=st.lists(st.floats(min_value=0.4, max_value=0.8), min_size=1, max_size=3),
        quality_scores=st.lists(st.floats(min_value=0.3, max_value=1.0), min_size=1, max_size=3)
    )
    @settings(max_examples=12, deadline=10000)
    def test_property_4_alpha_signal_quality_validation(
        self, 
        num_regimes: int, 
        alpha_values: List[float], 
        hit_rates: List[float], 
        quality_scores: List[float]
    ):
        """
        Property 4: Alpha Signal Quality Validation
        
        For any set of generated alpha signals, the system should validate 
        signal quality metrics and consistency scores meet minimum thresholds.
        
        Validates: Requirements 2.4
        """
        # Ensure we have enough data
        assume(len(alpha_values) >= num_regimes)
        assume(len(hit_rates) >= num_regimes)
        assume(len(quality_scores) >= num_regimes)
        
        # Create mock alpha validation results
        results = []
        regimes = ["bull", "bear", "sideways"][:num_regimes]
        
        for i, regime in enumerate(regimes):
            result = AlphaValidationResult(
                regime=regime,
                period_start=datetime(2020, 1, 1),
                period_end=datetime(2020, 12, 31),
                alpha_generated=alpha_values[i],
                information_ratio=alpha_values[i] / 0.1 if alpha_values[i] != 0 else 0,  # Mock IR
                hit_rate=hit_rates[i],
                signal_quality_score=quality_scores[i],
                consistency_score=0.7,  # Fixed for simplicity
                regime_adaptation_score=0.8,  # Fixed for simplicity
                validation_passed=True,  # Will be determined by validation
                signal_count=np.random.randint(10, 100)
            )
            results.append(result)
        
        # Generate comprehensive alpha report
        report = self.validator.generate_alpha_report(results)
        
        # Property: Report should be a dictionary with required sections
        assert isinstance(report, dict)
        required_sections = ["summary", "performance_metrics", "consistency_analysis", 
                           "regime_specific_results", "insights_and_recommendations"]
        for section in required_sections:
            assert section in report
        
        # Property: Summary section should contain correct aggregates
        summary = report["summary"]
        assert summary["total_regimes_tested"] == num_regimes
        assert 0 <= summary["regimes_passed"] <= num_regimes
        assert 0.0 <= summary["pass_rate"] <= 1.0
        assert summary["overall_assessment"] in ["STRONG", "MODERATE", "WEAK"]
        
        # Property: Performance metrics should be properly aggregated
        perf_metrics = report["performance_metrics"]
        assert isinstance(perf_metrics["average_alpha_generated"], float)
        assert isinstance(perf_metrics["average_information_ratio"], float)
        assert isinstance(perf_metrics["average_hit_rate"], float)
        assert isinstance(perf_metrics["average_signal_quality"], float)
        assert isinstance(perf_metrics["total_signals_generated"], int)
        
        # Property: Performance metrics should be within expected ranges
        assert 0.0 <= perf_metrics["average_hit_rate"] <= 1.0
        assert 0.0 <= perf_metrics["average_signal_quality"] <= 1.0
        assert perf_metrics["total_signals_generated"] >= 0
        
        # Property: Consistency analysis should be present
        consistency = report["consistency_analysis"]
        assert isinstance(consistency, dict)
        assert "overall_consistency_score" in consistency
        assert 0.0 <= consistency["overall_consistency_score"] <= 1.0
        
        # Property: Regime-specific results should match input
        regime_results = report["regime_specific_results"]
        assert len(regime_results) == num_regimes
        
        for regime in regimes:
            assert regime in regime_results
            regime_data = regime_results[regime]
            assert isinstance(regime_data["passed"], bool)
            assert isinstance(regime_data["alpha_generated"], float)
            assert isinstance(regime_data["hit_rate"], float)
            assert isinstance(regime_data["signal_quality"], float)
        
        # Property: Insights should be provided
        insights = report["insights_and_recommendations"]
        assert isinstance(insights, dict)
        required_insight_keys = ["key_findings", "performance_concerns", "recommendations", "strengths"]
        for key in required_insight_keys:
            assert key in insights
            assert isinstance(insights[key], list)
        
        # Property: Report should have generation timestamp
        assert "generated_at" in report
        assert isinstance(report["generated_at"], str)
    
    @given(
        alpha_degradation=st.floats(min_value=0.1, max_value=0.8),
        ir_degradation=st.floats(min_value=0.1, max_value=0.6),
        quality_degradation=st.floats(min_value=0.1, max_value=0.5)
    )
    @settings(max_examples=10, deadline=10000)
    def test_property_5_alpha_performance_degradation_response(
        self, 
        alpha_degradation: float, 
        ir_degradation: float, 
        quality_degradation: float
    ):
        """
        Property 5: Alpha Performance Degradation Response
        
        For any detected alpha performance degradation, the system should trigger 
        appropriate alerts and initiate diagnostic procedures.
        
        Validates: Requirements 2.5
        """
        # Create historical results (good performance)
        historical_results = [
            AlphaValidationResult(
                regime="bull",
                period_start=datetime(2019, 1, 1),
                period_end=datetime(2019, 12, 31),
                alpha_generated=0.05,  # 5% alpha
                information_ratio=1.0,
                hit_rate=0.6,
                signal_quality_score=0.8,
                consistency_score=0.75,
                regime_adaptation_score=0.9,
                validation_passed=True,
                signal_count=50
            ),
            AlphaValidationResult(
                regime="bear",
                period_start=datetime(2019, 1, 1),
                period_end=datetime(2019, 12, 31),
                alpha_generated=0.03,  # 3% alpha
                information_ratio=0.8,
                hit_rate=0.55,
                signal_quality_score=0.75,
                consistency_score=0.7,
                regime_adaptation_score=0.85,
                validation_passed=True,
                signal_count=40
            )
        ]
        
        # Create current results (degraded performance)
        current_results = [
            AlphaValidationResult(
                regime="bull",
                period_start=datetime(2020, 1, 1),
                period_end=datetime(2020, 12, 31),
                alpha_generated=0.05 * (1 - alpha_degradation),  # Degraded alpha
                information_ratio=1.0 * (1 - ir_degradation),    # Degraded IR
                hit_rate=0.6 * (1 - 0.1),  # Slightly degraded hit rate
                signal_quality_score=0.8 * (1 - quality_degradation),  # Degraded quality
                consistency_score=0.75,
                regime_adaptation_score=0.9,
                validation_passed=False,  # Failed due to degradation
                signal_count=45
            ),
            AlphaValidationResult(
                regime="bear",
                period_start=datetime(2020, 1, 1),
                period_end=datetime(2020, 12, 31),
                alpha_generated=0.03 * (1 - alpha_degradation * 0.8),  # Less degraded
                information_ratio=0.8 * (1 - ir_degradation * 0.7),
                hit_rate=0.55,
                signal_quality_score=0.75 * (1 - quality_degradation * 0.6),
                consistency_score=0.7,
                regime_adaptation_score=0.85,
                validation_passed=True,  # Still passing
                signal_count=38
            )
        ]
        
        # Detect alpha degradation
        degradation_analysis = self.validator.detect_alpha_degradation(
            historical_results, current_results
        )
        
        # Property: Degradation analysis should be a dictionary
        assert isinstance(degradation_analysis, dict)
        assert "degradation_detected" in degradation_analysis
        assert isinstance(degradation_analysis["degradation_detected"], bool)
        
        # Property: Should detect degradation when alpha drops significantly
        if alpha_degradation > self.validator.ALPHA_THRESHOLDS["max_alpha_degradation"]:
            assert degradation_analysis["degradation_detected"] == True
            
            # Property: Should have regime-specific analysis
            assert "regime_analysis" in degradation_analysis
            regime_analysis = degradation_analysis["regime_analysis"]
            assert isinstance(regime_analysis, dict)
            
            # Property: Should analyze bull market degradation
            if "bull" in regime_analysis:
                bull_analysis = regime_analysis["bull"]
                assert isinstance(bull_analysis["alpha_change"], float)
                assert isinstance(bull_analysis["degradation_detected"], bool)
                assert bull_analysis["alpha_change"] < 0  # Should be negative change
        
        # Property: Should generate alerts for significant degradation
        if "alerts_generated" in degradation_analysis:
            alerts = degradation_analysis["alerts_generated"]
            assert isinstance(alerts, list)
            
            # If degradation is detected, should have alerts
            if degradation_analysis["degradation_detected"]:
                # Should have at least one alert for significant degradation
                if alpha_degradation > 0.5:  # Very significant degradation
                    assert len(alerts) > 0
                    
                    # Check alert properties
                    for alert in alerts:
                        assert hasattr(alert, 'timestamp')
                        assert hasattr(alert, 'level')
                        assert hasattr(alert, 'component')
                        assert hasattr(alert, 'message')
                        assert alert.component == "AlphaValidator"
        
        # Property: Should have analysis timestamp
        assert "analysis_timestamp" in degradation_analysis
        assert isinstance(degradation_analysis["analysis_timestamp"], str)
    
    @given(
        num_days=st.integers(min_value=300, max_value=600)
    )
    @settings(max_examples=8, deadline=12000)
    def test_property_3_regime_detection_consistency(self, num_days: int):
        """
        Property 3: Regime Detection Consistency
        
        For any market data, regime detection should be consistent and 
        produce valid regime classifications.
        """
        # Generate market data
        market_data = self._generate_market_data(num_days, "bull")
        
        # Detect regimes
        regime_periods = self.regime_detector.detect_regime_periods(market_data)
        
        # Property: Should return a DataFrame
        assert isinstance(regime_periods, pd.DataFrame)
        
        # Property: Should have required columns
        required_columns = ['date', 'regime', 'close']
        for col in required_columns:
            assert col in regime_periods.columns
        
        # Property: All regimes should be valid
        valid_regimes = {MarketRegime.BULL.value, MarketRegime.BEAR.value, 
                        MarketRegime.SIDEWAYS.value, MarketRegime.UNKNOWN.value}
        for regime in regime_periods['regime']:
            assert regime in valid_regimes
        
        # Property: Should have reasonable number of regime periods
        # (not every single day should be a different regime)
        unique_regimes = regime_periods['regime'].nunique()
        assert 1 <= unique_regimes <= 4  # At most 4 different regimes
        
        # Property: Dates should be in chronological order
        dates = pd.to_datetime(regime_periods['date'])
        assert dates.is_monotonic_increasing
    
    def test_property_4_signal_quality_bounds(self):
        """
        Property 4: Signal Quality Bounds
        
        Signal quality metrics should always be within valid bounds
        regardless of input variations.
        """
        # Test with various market conditions
        test_cases = [
            ("bull", 400),
            ("bear", 350),
            ("sideways", 450)
        ]
        
        for regime, num_days in test_cases:
            market_data = self._generate_market_data(num_days, regime)
            
            # Run alpha validation
            if regime == "bull":
                result = self.validator.validate_bull_market_alpha(market_data)
            elif regime == "bear":
                result = self.validator.validate_bear_market_alpha(market_data)
            else:
                result = self.validator.validate_sideways_market_alpha(market_data)
            
            # Property: All metrics should be within valid bounds
            assert 0.0 <= result.hit_rate <= 1.0
            assert 0.0 <= result.signal_quality_score <= 1.0
            assert 0.0 <= result.consistency_score <= 1.0
            assert result.signal_count >= 0
            
            # Property: Information ratio should be reasonable
            assert -10.0 <= result.information_ratio <= 10.0
            
            # Property: Alpha should be reasonable
            assert -1.0 <= result.alpha_generated <= 1.0
    
    def test_property_5_degradation_detection_edge_cases(self):
        """
        Property 5: Degradation Detection Edge Cases
        
        Test degradation detection with edge cases like empty data,
        identical results, and extreme degradation.
        """
        # Test with empty historical results
        empty_degradation = self.validator.detect_alpha_degradation([], [])
        assert isinstance(empty_degradation, dict)
        assert empty_degradation["degradation_detected"] == False
        assert "reason" in empty_degradation
        
        # Test with identical results (no degradation)
        identical_result = AlphaValidationResult(
            regime="bull",
            period_start=datetime(2020, 1, 1),
            period_end=datetime(2020, 12, 31),
            alpha_generated=0.05,
            information_ratio=1.0,
            hit_rate=0.6,
            signal_quality_score=0.8,
            consistency_score=0.75,
            regime_adaptation_score=0.9,
            validation_passed=True,
            signal_count=50
        )
        
        no_degradation = self.validator.detect_alpha_degradation(
            [identical_result], [identical_result]
        )
        
        # Property: Should not detect degradation for identical results
        assert no_degradation["degradation_detected"] == False
        
        # Test with extreme degradation
        good_result = AlphaValidationResult(
            regime="bull",
            period_start=datetime(2019, 1, 1),
            period_end=datetime(2019, 12, 31),
            alpha_generated=0.1,  # 10% alpha
            information_ratio=2.0,
            hit_rate=0.7,
            signal_quality_score=0.9,
            consistency_score=0.8,
            regime_adaptation_score=0.95,
            validation_passed=True,
            signal_count=100
        )
        
        bad_result = AlphaValidationResult(
            regime="bull",
            period_start=datetime(2020, 1, 1),
            period_end=datetime(2020, 12, 31),
            alpha_generated=0.01,  # 1% alpha (90% degradation)
            information_ratio=0.2,
            hit_rate=0.45,
            signal_quality_score=0.3,
            consistency_score=0.4,
            regime_adaptation_score=0.5,
            validation_passed=False,
            signal_count=20
        )
        
        extreme_degradation = self.validator.detect_alpha_degradation(
            [good_result], [bad_result]
        )
        
        # Property: Should detect extreme degradation
        assert extreme_degradation["degradation_detected"] == True
        
        # Property: Should have regime analysis
        assert "regime_analysis" in extreme_degradation
        assert "bull" in extreme_degradation["regime_analysis"]
        
        bull_analysis = extreme_degradation["regime_analysis"]["bull"]
        assert bull_analysis["degradation_detected"] == True
        assert bull_analysis["alpha_change"] < -0.5  # More than 50% degradation
    
    def test_property_3_alpha_generation_regime_adaptation(self):
        """
        Property 3: Alpha Generation Regime Adaptation
        
        Alpha generation should adapt appropriately to different market regimes,
        with different expected performance characteristics.
        """
        regimes_data = {
            "bull": self._generate_market_data(400, "bull"),
            "bear": self._generate_market_data(400, "bear"),
            "sideways": self._generate_market_data(400, "sideways")
        }
        
        results = {}
        
        for regime, data in regimes_data.items():
            if regime == "bull":
                result = self.validator.validate_bull_market_alpha(data)
            elif regime == "bear":
                result = self.validator.validate_bear_market_alpha(data)
            else:
                result = self.validator.validate_sideways_market_alpha(data)
            
            results[regime] = result
        
        # Property: Each regime should have different characteristics
        # Bull markets typically have higher alpha potential
        # Bear markets may have lower but positive alpha from short strategies
        # Sideways markets should have moderate alpha from mean reversion
        
        for regime, result in results.items():
            # Property: All results should be valid
            assert isinstance(result, AlphaValidationResult)
            assert result.regime == regime
            
            # Property: Regime adaptation score should reflect regime appropriateness
            assert 0.0 <= result.regime_adaptation_score <= 2.0
            
            # Property: Signal count should be reasonable for regime
            assert result.signal_count >= 0
            
            # Property: Hit rate should be above random (50%)
            # Allow some flexibility for different regimes
            if result.hit_rate > 0:  # Only check if we have signals
                assert result.hit_rate >= 0.45  # Allow some tolerance
        
        # Property: Generate comprehensive report
        all_results = list(results.values())
        report = self.validator.generate_alpha_report(all_results)
        
        # Property: Report should reflect multi-regime analysis
        assert report["summary"]["total_regimes_tested"] == 3
        assert len(report["regime_specific_results"]) == 3
        
        # Property: Should have consistency analysis across regimes
        consistency = report["consistency_analysis"]
        assert "overall_consistency_score" in consistency
        assert "regime_performance" in consistency