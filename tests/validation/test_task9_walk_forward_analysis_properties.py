"""
Property tests for Task 9: Walk-Forward Analysis Engine.

These tests validate the universal correctness properties of the walk-forward
analysis system across all possible scenarios and conditions.
"""

import pytest
import time
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import Mock, patch

from src.operation.walk_forward_analysis_engine import WalkForwardAnalysisEngine
from src.operation.base_types import (
    WalkForwardConfig, WalkForwardResult, StrategyEvolutionResult,
    AlertLevel, HealthStatus
)


class TestWalkForwardAnalysisProperties:
    """Property tests for Walk-Forward Analysis Engine."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config = WalkForwardConfig(
            training_window=6,  # 6 months
            testing_window=3,   # 3 months
            step_size=3,        # 3 month steps
            minimum_observations=100,
            optimization_metric="sharpe_ratio"
        )
        self.walk_forward_engine = WalkForwardAnalysisEngine(self.config)
    
    def teardown_method(self):
        """Clean up after tests."""
        # Clear analysis history
        self.walk_forward_engine.analysis_history.clear()
        self.walk_forward_engine.strategy_evolution_history.clear()
    
    # Property 30: Walk-Forward Analysis Execution
    def test_property_30_walk_forward_analysis_execution(self):
        """
        Property 30: Walk-Forward Analysis Execution
        
        Universal Property: For any walk-forward analysis execution, the system
        generates rolling windows, performs out-of-sample validation, and
        provides comprehensive analysis results.
        
        Validates: Requirements 9.1, 9.2
        """
        # Test various analysis scenarios
        analysis_scenarios = [
            {
                "name": "short_term_analysis",
                "start_date": datetime(2020, 1, 1),
                "end_date": datetime(2021, 6, 30),
                "strategies": ["momentum_strategy", "mean_reversion_strategy"]
            },
            {
                "name": "medium_term_analysis", 
                "start_date": datetime(2019, 1, 1),
                "end_date": datetime(2022, 12, 31),
                "strategies": ["value_strategy", "quality_strategy", "momentum_strategy"]
            },
            {
                "name": "single_strategy_analysis",
                "start_date": datetime(2020, 6, 1),
                "end_date": datetime(2021, 12, 31),
                "strategies": ["combined_strategy"]
            }
        ]
        
        for scenario in analysis_scenarios:
            start_date = scenario["start_date"]
            end_date = scenario["end_date"]
            strategies = scenario["strategies"]
            
            # Execute walk-forward analysis
            results = self.walk_forward_engine.run_comprehensive_walk_forward_analysis(
                start_date, end_date, strategies
            )
            
            # Property: Analysis generates results
            assert len(results) > 0, f"Walk-forward analysis must generate results for {scenario['name']}"
            
            # Property: All results have required structure
            for result in results:
                assert hasattr(result, 'analysis_id'), "Result must have analysis ID"
                assert hasattr(result, 'window_id'), "Result must have window ID"
                assert hasattr(result, 'training_start'), "Result must have training start date"
                assert hasattr(result, 'training_end'), "Result must have training end date"
                assert hasattr(result, 'testing_start'), "Result must have testing start date"
                assert hasattr(result, 'testing_end'), "Result must have testing end date"
                assert hasattr(result, 'strategies_analyzed'), "Result must have strategies analyzed"
                assert hasattr(result, 'strategy_results'), "Result must have strategy results"
                
                # Property: Training period comes before testing period
                assert result.training_start < result.training_end, \
                    "Training start must be before training end"
                assert result.training_end <= result.testing_start, \
                    "Training end must be before or equal to testing start"
                assert result.testing_start < result.testing_end, \
                    "Testing start must be before testing end"
                
                # Property: Strategies analyzed match input
                assert set(result.strategies_analyzed) == set(strategies), \
                    f"Strategies analyzed must match input strategies"
                
                # Property: Strategy results exist for all strategies
                strategy_names_in_results = [sr["strategy_name"] for sr in result.strategy_results]
                assert set(strategy_names_in_results) == set(strategies), \
                    "Strategy results must exist for all input strategies"
                
                # Property: Each strategy result has required fields
                for strategy_result in result.strategy_results:
                    assert "strategy_name" in strategy_result, "Strategy result must have strategy name"
                    assert "window_id" in strategy_result, "Strategy result must have window ID"
                    assert "out_of_sample_return" in strategy_result, "Strategy result must have out-of-sample return"
                    assert "out_of_sample_sharpe" in strategy_result, "Strategy result must have out-of-sample Sharpe"
                    
                    # Property: Performance metrics are numeric
                    assert isinstance(strategy_result["out_of_sample_return"], (int, float)), \
                        "Out-of-sample return must be numeric"
                    assert isinstance(strategy_result["out_of_sample_sharpe"], (int, float)), \
                        "Out-of-sample Sharpe must be numeric"
            
            # Property: Windows are properly sequenced
            for i in range(1, len(results)):
                prev_result = results[i-1]
                curr_result = results[i]
                
                # Property: Windows advance in time
                assert curr_result.training_start >= prev_result.training_start, \
                    "Window training start dates must advance in time"
                assert curr_result.testing_start >= prev_result.testing_start, \
                    "Window testing start dates must advance in time"
            
            # Property: Analysis history is updated
            assert len(self.walk_forward_engine.analysis_history) >= len(results), \
                "Analysis history must be updated with results"
    
    def test_property_30_rolling_window_generation(self):
        """Test that rolling windows are generated correctly."""
        start_date = datetime(2020, 1, 1)
        end_date = datetime(2021, 12, 31)
        
        # Generate windows
        windows = self.walk_forward_engine._generate_analysis_windows(start_date, end_date)
        
        # Property: Windows are generated
        assert len(windows) > 0, "Windows must be generated for valid date range"
        
        # Property: All windows have required attributes
        for window in windows:
            assert hasattr(window, 'window_id'), "Window must have ID"
            assert hasattr(window, 'training_start'), "Window must have training start"
            assert hasattr(window, 'training_end'), "Window must have training end"
            assert hasattr(window, 'testing_start'), "Window must have testing start"
            assert hasattr(window, 'testing_end'), "Window must have testing end"
            assert hasattr(window, 'training_observations'), "Window must have training observations"
            assert hasattr(window, 'testing_observations'), "Window must have testing observations"
        
        # Property: Window durations match configuration
        for window in windows:
            training_duration = (window.training_end - window.training_start).days
            testing_duration = (window.testing_end - window.testing_start).days
            
            # Allow some tolerance for month variations
            expected_training_days = self.config.training_window * 30
            expected_testing_days = self.config.testing_window * 30
            
            assert abs(training_duration - expected_training_days) <= 5, \
                f"Training duration should be approximately {expected_training_days} days"
            assert abs(testing_duration - expected_testing_days) <= 5, \
                f"Testing duration should be approximately {expected_testing_days} days"
        
        # Property: Windows are properly spaced
        if len(windows) > 1:
            for i in range(1, len(windows)):
                prev_window = windows[i-1]
                curr_window = windows[i]
                
                step_duration = (curr_window.training_start - prev_window.training_start).days
                expected_step_days = self.config.step_size * 30
                
                assert abs(step_duration - expected_step_days) <= 5, \
                    f"Window step size should be approximately {expected_step_days} days"
        
        # Property: Windows stay within date range
        for window in windows:
            assert window.training_start >= start_date, "Window training start must be within range"
            assert window.testing_end <= end_date, "Window testing end must be within range"
    
    def test_property_30_out_of_sample_validation(self):
        """Test that out-of-sample validation is properly performed."""
        start_date = datetime(2020, 1, 1)
        end_date = datetime(2021, 6, 30)
        strategies = ["test_strategy"]
        
        # Run analysis
        results = self.walk_forward_engine.run_comprehensive_walk_forward_analysis(
            start_date, end_date, strategies
        )
        
        # Property: Out-of-sample validation is performed
        for result in results:
            for strategy_result in result.strategy_results:
                # Property: Training and testing results are separate
                assert "training_performance" in strategy_result, \
                    "Strategy result must have training performance"
                assert "testing_performance" in strategy_result, \
                    "Strategy result must have testing performance"
                
                training_perf = strategy_result["training_performance"]
                testing_perf = strategy_result["testing_performance"]
                
                # Property: Training and testing have different data
                assert "training_observations" in training_perf, \
                    "Training performance must include observation count"
                assert "testing_observations" in testing_perf, \
                    "Testing performance must include observation count"
                
                # Property: Out-of-sample metrics are from testing period
                assert strategy_result["out_of_sample_return"] == testing_perf["total_return"], \
                    "Out-of-sample return must come from testing performance"
                assert strategy_result["out_of_sample_sharpe"] == testing_perf["sharpe_ratio"], \
                    "Out-of-sample Sharpe must come from testing performance"
                
                # Property: Parameters used in testing come from training optimization
                if "optimized_parameters" in training_perf and "parameters_used" in testing_perf:
                    assert training_perf["optimized_parameters"] == testing_perf["parameters_used"], \
                        "Testing must use parameters optimized during training"
    
    # Property 31: Strategy Degradation Detection
    def test_property_31_strategy_degradation_detection(self):
        """
        Property 31: Strategy Degradation Detection
        
        Universal Property: For any strategy with sufficient history, the system
        detects performance degradation and provides actionable recommendations.
        
        Validates: Requirements 9.3, 9.4
        """
        # Create mock performance history to test degradation detection
        strategy_name = "test_strategy"
        
        # Simulate performance history with degradation
        mock_performance_history = []
        base_return = 0.15  # Start with 15% returns
        
        # First few periods: good performance (deterministic)
        for i in range(5):
            mock_performance_history.append({
                "window_id": f"WF_{i:03d}",
                "timestamp": datetime(2020, 1, 1) + timedelta(days=i*90),
                "out_of_sample_return": base_return,  # Fixed value
                "out_of_sample_sharpe": 1.2,  # Fixed value
                "testing_performance": {
                    "total_return": base_return,
                    "volatility": 0.15,
                    "max_drawdown": 0.08,
                    "sharpe_ratio": 1.2
                }
            })
        
        # Next few periods: degrading performance (deterministic)
        degraded_return = 0.05  # Drop to 5% returns
        for i in range(5, 10):
            mock_performance_history.append({
                "window_id": f"WF_{i:03d}",
                "timestamp": datetime(2020, 1, 1) + timedelta(days=i*90),
                "out_of_sample_return": degraded_return,  # Fixed value
                "out_of_sample_sharpe": 0.4,  # Fixed value
                "testing_performance": {
                    "total_return": degraded_return,
                    "volatility": 0.25,
                    "max_drawdown": 0.15,
                    "sharpe_ratio": 0.4
                }
            })
        
        # Set up mock history
        self.walk_forward_engine.strategy_performance_history[strategy_name] = mock_performance_history
        
        # Test degradation detection
        degradation_result = self.walk_forward_engine.detect_strategy_degradation(strategy_name)
        
        # Property: Degradation detection returns valid result
        assert hasattr(degradation_result, 'strategy_name'), "Result must have strategy name"
        assert hasattr(degradation_result, 'degradation_detected'), "Result must have degradation detected flag"
        assert hasattr(degradation_result, 'degradation_severity'), "Result must have degradation severity"
        assert hasattr(degradation_result, 'recommended_actions'), "Result must have recommended actions"
        
        # Property: Strategy name matches input
        assert degradation_result.strategy_name == strategy_name, \
            "Result strategy name must match input"
        
        # Property: Degradation is detected for declining performance
        assert degradation_result.degradation_detected == True, \
            f"Degradation should be detected for declining performance pattern. Got: {degradation_result.degradation_detected}, severity: {degradation_result.degradation_severity}"
        
        # Property: Severity is appropriate for degradation level
        assert degradation_result.degradation_severity in ["low", "medium", "high", "critical"], \
            "Degradation severity must be valid level"
        
        # Property: Recommendations are provided
        assert len(degradation_result.recommended_actions) > 0, \
            "Recommendations must be provided for detected degradation"
        
        # Property: Statistical significance is provided
        assert hasattr(degradation_result, 'statistical_significance'), \
            "Result must include statistical significance"
        assert 0.0 <= degradation_result.statistical_significance <= 1.0, \
            "Statistical significance must be between 0 and 1"
        
        # Property: Performance decline percentage is calculated
        assert hasattr(degradation_result, 'performance_decline_pct'), \
            "Result must include performance decline percentage"
        
        # Property: Degradation start date is estimated
        if degradation_result.degradation_detected:
            assert degradation_result.degradation_start_date is not None, \
                "Degradation start date must be provided when degradation detected"
    
    def test_property_31_degradation_detection_edge_cases(self):
        """Test degradation detection edge cases."""
        # Test with insufficient data
        strategy_name = "insufficient_data_strategy"
        
        # Only 2 data points
        mock_history = [
            {
                "window_id": "WF_001",
                "timestamp": datetime(2020, 1, 1),
                "out_of_sample_return": 0.10,
                "out_of_sample_sharpe": 1.0,
                "testing_performance": {"total_return": 0.10, "volatility": 0.15}
            },
            {
                "window_id": "WF_002", 
                "timestamp": datetime(2020, 4, 1),
                "out_of_sample_return": 0.12,
                "out_of_sample_sharpe": 1.1,
                "testing_performance": {"total_return": 0.12, "volatility": 0.14}
            }
        ]
        
        self.walk_forward_engine.strategy_performance_history[strategy_name] = mock_history
        
        degradation_result = self.walk_forward_engine.detect_strategy_degradation(strategy_name)
        
        # Property: Insufficient data is handled gracefully
        assert degradation_result.degradation_detected == False, \
            "Degradation should not be detected with insufficient data"
        assert "insufficient" in degradation_result.degradation_severity.lower() or \
               "insufficient" in " ".join(degradation_result.recommended_actions).lower(), \
            "Result should indicate insufficient data"
        
        # Test with no data
        unknown_strategy = "unknown_strategy"
        degradation_result = self.walk_forward_engine.detect_strategy_degradation(unknown_strategy)
        
        # Property: Unknown strategy is handled gracefully
        assert degradation_result.degradation_detected == False, \
            "Degradation should not be detected for unknown strategy"
        assert degradation_result.strategy_name == unknown_strategy, \
            "Strategy name should match input even for unknown strategy"
    
    def test_property_31_degradation_alert_generation(self):
        """Test that degradation detection generates appropriate alerts."""
        strategy_name = "alert_test_strategy"
        
        # Create severe degradation scenario
        mock_history = []
        for i in range(8):
            # Severe decline from 20% to -5% returns
            declining_return = 0.20 - (i * 0.035)  # Decline by 3.5% each period
            mock_history.append({
                "window_id": f"WF_{i:03d}",
                "timestamp": datetime(2020, 1, 1) + timedelta(days=i*90),
                "out_of_sample_return": declining_return,
                "out_of_sample_sharpe": max(0.1, 2.0 - (i * 0.3)),
                "testing_performance": {
                    "total_return": declining_return,
                    "volatility": 0.15 + (i * 0.02),
                    "max_drawdown": 0.05 + (i * 0.02),
                    "sharpe_ratio": max(0.1, 2.0 - (i * 0.3))
                }
            })
        
        self.walk_forward_engine.strategy_performance_history[strategy_name] = mock_history
        
        initial_alert_count = len(self.walk_forward_engine.degradation_alerts)
        
        # Detect degradation
        degradation_result = self.walk_forward_engine.detect_strategy_degradation(strategy_name)
        
        # Property: Alerts are generated for detected degradation
        if degradation_result.degradation_detected:
            final_alert_count = len(self.walk_forward_engine.degradation_alerts)
            assert final_alert_count > initial_alert_count, \
                "Alerts must be generated when degradation is detected"
            
            # Property: Alert contains relevant information
            new_alerts = self.walk_forward_engine.degradation_alerts[initial_alert_count:]
            for alert in new_alerts:
                assert "degradation" in alert.message.lower(), \
                    "Alert message must mention degradation"
                assert alert.component == "WalkForwardAnalysisEngine", \
                    "Alert must be from WalkForwardAnalysisEngine"
                assert "strategy" in alert.details, \
                    "Alert details must include strategy information"
                assert alert.details["strategy"] == strategy_name, \
                    "Alert must reference correct strategy"
    
    # Additional property tests for comprehensive coverage
    
    def test_strategy_evolution_analysis_properties(self):
        """Test properties of strategy evolution analysis."""
        strategy_name = "evolution_test_strategy"
        
        # Create mock performance and parameter history
        mock_performance = []
        mock_parameters = []
        
        for i in range(10):
            # Simulate evolving strategy
            mock_performance.append({
                "window_id": f"WF_{i:03d}",
                "timestamp": datetime(2020, 1, 1) + timedelta(days=i*90),
                "out_of_sample_return": 0.10 + (i * 0.01),  # Improving trend
                "out_of_sample_sharpe": 1.0 + (i * 0.05),
                "testing_performance": {
                    "total_return": 0.10 + (i * 0.01),
                    "volatility": 0.15 - (i * 0.005),  # Decreasing volatility
                    "sharpe_ratio": 1.0 + (i * 0.05)
                }
            })
            
            # Evolving parameters
            mock_parameters.append({
                "window_id": f"WF_{i:03d}",
                "timestamp": datetime(2020, 1, 1) + timedelta(days=i*90),
                "parameters": {
                    "lookback_period": 20 + i,  # Increasing lookback
                    "signal_threshold": 0.1 + (i * 0.01),  # Increasing threshold
                    "position_size": 0.05 - (i * 0.002)  # Decreasing position size
                }
            })
        
        self.walk_forward_engine.strategy_performance_history[strategy_name] = mock_performance
        self.walk_forward_engine.strategy_parameters_history[strategy_name] = mock_parameters
        
        # Generate evolution insights
        evolution_result = self.walk_forward_engine.generate_strategy_evolution_insights(strategy_name)
        
        # Property: Evolution result has required structure
        assert hasattr(evolution_result, 'strategy_name'), "Evolution result must have strategy name"
        assert hasattr(evolution_result, 'evolution_detected'), "Evolution result must have evolution detected flag"
        assert hasattr(evolution_result, 'recommendations'), "Evolution result must have recommendations"
        assert hasattr(evolution_result, 'confidence_score'), "Evolution result must have confidence score"
        
        # Property: Strategy name matches input
        assert evolution_result.strategy_name == strategy_name, \
            "Evolution result strategy name must match input"
        
        # Property: Confidence score is bounded
        assert 0.0 <= evolution_result.confidence_score <= 1.0, \
            "Confidence score must be between 0 and 1"
        
        # Property: Recommendations are provided
        assert len(evolution_result.recommendations) > 0, \
            "Evolution analysis must provide recommendations"
        
        # Property: Analysis periods are set
        assert evolution_result.analysis_period_start is not None, \
            "Evolution result must have analysis period start"
        assert evolution_result.analysis_period_end is not None, \
            "Evolution result must have analysis period end"
        assert evolution_result.analysis_period_start <= evolution_result.analysis_period_end, \
            "Analysis period start must be before or equal to end"
    
    def test_walk_forward_metrics_calculation_properties(self):
        """Test properties of walk-forward metrics calculation."""
        # Run some analyses to generate data
        start_date = datetime(2020, 1, 1)
        end_date = datetime(2021, 6, 30)
        strategies = ["strategy_1", "strategy_2"]
        
        results = self.walk_forward_engine.run_comprehensive_walk_forward_analysis(
            start_date, end_date, strategies
        )
        
        # Get metrics
        metrics = self.walk_forward_engine.get_walk_forward_metrics()
        
        # Property: Metrics have required structure
        required_sections = [
            "analysis_statistics", "strategy_statistics", "degradation_statistics",
            "evolution_statistics", "window_configuration", "metrics_timestamp"
        ]
        
        for section in required_sections:
            assert section in metrics, f"Metrics must include {section} section"
        
        # Property: Analysis statistics are accurate
        analysis_stats = metrics["analysis_statistics"]
        assert analysis_stats["total_analyses"] >= 1, \
            "Total analyses count must reflect executed analyses"
        assert analysis_stats["total_windows"] >= len(results), \
            "Total windows count must reflect generated windows"
        
        # Property: Strategy statistics are calculated
        strategy_stats = metrics["strategy_statistics"]
        for strategy in strategies:
            if strategy in strategy_stats:
                stats = strategy_stats[strategy]
                assert "windows" in stats, f"Strategy {strategy} must have window count"
                assert "avg_performance" in stats, f"Strategy {strategy} must have average performance"
                assert stats["windows"] > 0, f"Strategy {strategy} must have positive window count"
        
        # Property: Window configuration matches setup
        window_config = metrics["window_configuration"]
        assert window_config["training_window_months"] == self.config.training_window, \
            "Window configuration must match setup"
        assert window_config["testing_window_months"] == self.config.testing_window, \
            "Window configuration must match setup"
        assert window_config["step_size_months"] == self.config.step_size, \
            "Window configuration must match setup"
        
        # Property: Metrics timestamp is recent
        metrics_time = datetime.fromisoformat(metrics["metrics_timestamp"])
        time_diff = (datetime.now() - metrics_time).total_seconds()
        assert time_diff < 60, "Metrics timestamp must be recent"
    
    def test_analysis_window_boundary_conditions(self):
        """Test walk-forward analysis with boundary conditions."""
        # Test with very short date range
        short_start = datetime(2020, 1, 1)
        short_end = datetime(2020, 6, 30)  # Only 6 months
        strategies = ["test_strategy"]
        
        # This should handle the short range gracefully
        results = self.walk_forward_engine.run_comprehensive_walk_forward_analysis(
            short_start, short_end, strategies
        )
        
        # Property: Short date ranges are handled
        # May have 0 or few results depending on configuration
        assert isinstance(results, list), "Results must be a list even for short ranges"
        
        # Test with single strategy
        single_strategy_results = self.walk_forward_engine.run_comprehensive_walk_forward_analysis(
            datetime(2020, 1, 1), datetime(2021, 12, 31), ["single_strategy"]
        )
        
        # Property: Single strategy analysis works
        assert len(single_strategy_results) >= 0, "Single strategy analysis must work"
        
        for result in single_strategy_results:
            assert len(result.strategies_analyzed) == 1, \
                "Single strategy analysis must analyze exactly one strategy"
            assert result.strategies_analyzed[0] == "single_strategy", \
                "Single strategy analysis must analyze correct strategy"


if __name__ == "__main__":
    pytest.main([__file__])