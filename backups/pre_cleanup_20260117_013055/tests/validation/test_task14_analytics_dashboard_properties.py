"""
Property Tests for Task 14: Reporting and Analytics Dashboard

This module contains property-based tests that validate the universal correctness
properties of the analytics dashboard system, including report generation,
performance attribution, and trend analysis.

Author: Northstar Team
Date: 2026-01-05
"""

import pytest
import hypothesis
from hypothesis import given, strategies as st, assume, settings
import logging
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Any
from pathlib import Path

# Import the modules under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from operation.analytics_dashboard import AnalyticsDashboard, DashboardConfig, TrendAnalysis
from operation.base_types import (
    CrisisValidationResult, AlphaValidationResult, OperationResult, 
    SystemHealthStatus, HealthStatus, AlertLevel, Alert, OperationStatus
)


# Test data strategies
@st.composite
def crisis_validation_result_strategy(draw):
    """Generate valid crisis validation results."""
    return CrisisValidationResult(
        crisis_period=draw(st.sampled_from(["2008_financial_crisis", "2020_covid_crash", "2000_dotcom_bubble"])),
        start_date=datetime(2008, 1, 1),
        end_date=datetime(2009, 12, 31),
        total_return=draw(st.floats(min_value=-0.5, max_value=0.3)),
        max_drawdown=draw(st.floats(min_value=-0.6, max_value=-0.01)),
        volatility=draw(st.floats(min_value=0.1, max_value=0.8)),
        sharpe_ratio=draw(st.floats(min_value=-2.0, max_value=3.0)),
        var_breach_count=draw(st.integers(min_value=0, max_value=20)),
        stress_test_passed=draw(st.booleans())
    )


@st.composite
def alpha_validation_result_strategy(draw):
    """Generate valid alpha validation results."""
    return AlphaValidationResult(
        regime=draw(st.sampled_from(["bull_market", "bear_market", "sideways_market"])),
        period_start=datetime(2020, 1, 1),
        period_end=datetime(2021, 1, 1),
        alpha_generated=draw(st.floats(min_value=-0.1, max_value=0.2)),
        information_ratio=draw(st.floats(min_value=-1.0, max_value=3.0)),
        hit_rate=draw(st.floats(min_value=0.3, max_value=0.8)),
        signal_quality_score=draw(st.floats(min_value=0.0, max_value=1.0)),
        consistency_score=draw(st.floats(min_value=0.0, max_value=1.0)),
        regime_adaptation_score=draw(st.floats(min_value=0.0, max_value=1.0)),
        validation_passed=draw(st.booleans()),
        signal_count=draw(st.integers(min_value=10, max_value=500))
    )


@st.composite
def system_health_status_strategy(draw):
    """Generate valid system health status."""
    return SystemHealthStatus(
        timestamp=datetime.now(),
        overall_health=draw(st.sampled_from(list(HealthStatus))),
        performance_score=draw(st.floats(min_value=0.0, max_value=1.0)),
        data_quality_score=draw(st.floats(min_value=0.0, max_value=1.0)),
        latency_metrics=draw(st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.floats(min_value=1.0, max_value=1000.0),
            min_size=0, max_size=5
        )),
        error_counts=draw(st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.integers(min_value=0, max_value=100),
            min_size=0, max_size=5
        )),
        alert_level=draw(st.sampled_from(list(AlertLevel)))
    )


@st.composite
def operation_result_strategy(draw):
    """Generate valid operation results."""
    start_time = datetime.now() - timedelta(hours=draw(st.integers(min_value=1, max_value=24)))
    end_time = start_time + timedelta(minutes=draw(st.integers(min_value=1, max_value=120)))
    
    return OperationResult(
        operation_id=f"op_{draw(st.integers(min_value=1000, max_value=9999))}",
        operation_type=draw(st.sampled_from(["crisis_validation", "alpha_validation", "system_validation"])),
        start_time=start_time,
        end_time=end_time,
        status=draw(st.sampled_from(list(OperationStatus))),
        performance_metrics=draw(st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.floats(min_value=0.0, max_value=100.0),
            min_size=0, max_size=5
        )),
        alerts_generated=[
            Alert(
                timestamp=datetime.now(),
                level=draw(st.sampled_from(list(AlertLevel))),
                component="test_component",
                message="Test alert message"
            )
            for _ in range(draw(st.integers(min_value=0, max_value=3)))
        ]
    )


class TestAnalyticsDashboardProperties:
    """Property tests for Analytics Dashboard."""
    
    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config = DashboardConfig(output_directory=self.temp_dir)
    
    @given(st.lists(crisis_validation_result_strategy(), min_size=1, max_size=5))
    @settings(max_examples=10, deadline=30000)
    def test_property_crisis_report_generation(self, crisis_results):
        """
        Property: Crisis performance reports should be generated for all valid inputs.
        
        This test validates that crisis performance reports are consistently
        generated and contain expected content.
        """
        dashboard = AnalyticsDashboard(self.config)
        
        # Generate crisis performance report
        report_path = dashboard.create_crisis_performance_report(crisis_results)
        
        # Verify report was created
        assert report_path is not None
        assert isinstance(report_path, str)
        assert len(report_path) > 0
        
        # Verify report file exists
        report_file = Path(report_path)
        assert report_file.exists()
        assert report_file.suffix == ".html"
        
        # Verify report contains expected content
        with open(report_file, 'r') as f:
            content = f.read()
            assert "Crisis Performance Analysis Report" in content
            assert str(len(crisis_results)) in content
            
            # Check that all crisis periods are mentioned
            for result in crisis_results:
                assert result.crisis_period in content
    
    @given(st.lists(alpha_validation_result_strategy(), min_size=1, max_size=5))
    @settings(max_examples=10, deadline=30000)
    def test_property_alpha_report_generation(self, alpha_results):
        """
        Property: Alpha validation reports should be generated for all valid inputs.
        
        This test validates that alpha validation reports are consistently
        generated and contain expected content.
        """
        dashboard = AnalyticsDashboard(self.config)
        
        # Generate alpha validation report
        report_path = dashboard.create_alpha_validation_report(alpha_results)
        
        # Verify report was created
        assert report_path is not None
        assert isinstance(report_path, str)
        assert len(report_path) > 0
        
        # Verify report file exists
        report_file = Path(report_path)
        assert report_file.exists()
        assert report_file.suffix == ".html"
        
        # Verify report contains expected content
        with open(report_file, 'r') as f:
            content = f.read()
            assert "Alpha Validation Analysis Report" in content
            assert str(len(alpha_results)) in content
            
            # Check that all regimes are mentioned
            for result in alpha_results:
                assert result.regime in content
    
    @given(system_health_status_strategy(), st.lists(operation_result_strategy(), min_size=0, max_size=10))
    @settings(max_examples=10, deadline=30000)
    def test_property_system_health_dashboard_generation(self, health_status, recent_operations):
        """
        Property: System health dashboards should be generated for all valid inputs.
        
        This test validates that system health dashboards are consistently
        generated and contain expected content.
        """
        dashboard = AnalyticsDashboard(self.config)
        
        # Generate system health dashboard
        dashboard_path = dashboard.create_system_health_dashboard(health_status, recent_operations)
        
        # Verify dashboard was created
        assert dashboard_path is not None
        assert isinstance(dashboard_path, str)
        assert len(dashboard_path) > 0
        
        # Verify dashboard file exists
        dashboard_file = Path(dashboard_path)
        assert dashboard_file.exists()
        assert dashboard_file.suffix == ".html"
        
        # Verify dashboard contains expected content
        with open(dashboard_file, 'r') as f:
            content = f.read()
            assert "System Health Monitoring Dashboard" in content
            assert health_status.overall_health.value.upper() in content
            assert f"{health_status.performance_score:.1%}" in content
    
    @given(st.lists(operation_result_strategy(), min_size=1, max_size=5),
           st.lists(crisis_validation_result_strategy(), min_size=0, max_size=3),
           st.lists(alpha_validation_result_strategy(), min_size=0, max_size=3))
    @settings(max_examples=8, deadline=30000)
    def test_property_investor_report_generation(self, operation_results, crisis_results, alpha_results):
        """
        Property: Investor reports should be generated for all valid inputs.
        
        This test validates that investor reports are consistently generated
        and contain expected performance metrics.
        """
        dashboard = AnalyticsDashboard(self.config)
        
        # Generate investor report
        report_path = dashboard.generate_investor_report(operation_results, crisis_results, alpha_results)
        
        # Verify report was created
        assert report_path is not None
        assert isinstance(report_path, str)
        assert len(report_path) > 0
        
        # Verify report file exists
        report_file = Path(report_path)
        assert report_file.exists()
        assert report_file.suffix == ".html"
        
        # Verify report contains expected content
        with open(report_file, 'r') as f:
            content = f.read()
            assert "Northstar V3 Trading System - Investor Report" in content
            assert "Executive Summary" in content
            assert "System Performance" in content
            assert str(len(operation_results)) in content
    
    @given(st.lists(st.dictionaries(
        st.sampled_from(["return", "date"]),
        st.one_of(
            st.floats(min_value=-0.1, max_value=0.1),
            st.datetimes(min_value=datetime(2020, 1, 1), max_value=datetime(2023, 12, 31))
        ),
        min_size=1, max_size=2
    ), min_size=0, max_size=50))
    @settings(max_examples=15, deadline=30000)
    def test_property_performance_pattern_detection(self, performance_data):
        """
        Property: Performance pattern detection should handle all valid data inputs.
        
        This test validates that trend analysis consistently produces valid
        results for different performance data inputs.
        """
        dashboard = AnalyticsDashboard(self.config)
        
        # Detect performance patterns
        trend_analysis = dashboard.detect_performance_patterns(performance_data)
        
        # Verify trend analysis structure
        assert isinstance(trend_analysis, TrendAnalysis)
        assert trend_analysis.trend_direction in ["up", "down", "sideways", "unknown"]
        assert 0.0 <= trend_analysis.trend_strength <= 1.0
        assert trend_analysis.trend_duration_days >= 0
        assert isinstance(trend_analysis.pattern_detected, str)
        assert 0.0 <= trend_analysis.confidence_score <= 1.0
        assert isinstance(trend_analysis.support_levels, list)
        assert isinstance(trend_analysis.resistance_levels, list)
        
        # Verify consistency with input data
        if not performance_data:
            assert trend_analysis.trend_direction == "unknown"
            assert trend_analysis.confidence_score == 0.0
        else:
            assert trend_analysis.trend_duration_days == len(performance_data)
    
    @given(st.lists(crisis_validation_result_strategy(), min_size=2, max_size=5))
    @settings(max_examples=8, deadline=30000)
    def test_property_crisis_report_consistency(self, crisis_results):
        """
        Property: Crisis reports should be consistent across multiple generations.
        
        This test validates that generating the same crisis report multiple times
        produces consistent results.
        """
        dashboard = AnalyticsDashboard(self.config)
        
        # Generate report multiple times
        report_path_1 = dashboard.create_crisis_performance_report(crisis_results)
        report_path_2 = dashboard.create_crisis_performance_report(crisis_results)
        
        # Both reports should be generated successfully
        assert report_path_1 is not None
        assert report_path_2 is not None
        
        # Read both reports
        with open(report_path_1, 'r') as f:
            content_1 = f.read()
        with open(report_path_2, 'r') as f:
            content_2 = f.read()
        
        # Key metrics should be consistent (ignoring timestamps)
        for result in crisis_results:
            assert content_1.count(result.crisis_period) == content_2.count(result.crisis_period)
            assert content_1.count(f"{result.total_return:.2%}") == content_2.count(f"{result.total_return:.2%}")
    
    @given(st.lists(alpha_validation_result_strategy(), min_size=1, max_size=3))
    @settings(max_examples=8, deadline=30000)
    def test_property_alpha_report_metrics_accuracy(self, alpha_results):
        """
        Property: Alpha reports should accurately reflect input metrics.
        
        This test validates that alpha validation reports correctly calculate
        and display summary statistics from input data.
        """
        dashboard = AnalyticsDashboard(self.config)
        
        # Calculate expected metrics
        expected_avg_alpha = sum(r.alpha_generated for r in alpha_results) / len(alpha_results)
        expected_best_alpha = max(r.alpha_generated for r in alpha_results)
        expected_success_rate = sum(1 for r in alpha_results if r.validation_passed) / len(alpha_results)
        
        # Generate report
        report_path = dashboard.create_alpha_validation_report(alpha_results)
        
        # Read report content
        with open(report_path, 'r') as f:
            content = f.read()
        
        # Verify key metrics are present in report
        assert f"{expected_avg_alpha:.2%}" in content
        assert f"{expected_best_alpha:.2%}" in content
        assert f"{expected_success_rate:.1%}" in content
    
    def test_property_empty_input_handling(self):
        """
        Property: Dashboard should handle empty inputs gracefully.
        
        This test validates that the dashboard handles empty input lists
        without errors and provides appropriate feedback.
        """
        dashboard = AnalyticsDashboard(self.config)
        
        # Test empty crisis results
        crisis_report = dashboard.create_crisis_performance_report([])
        assert crisis_report == ""  # Should return empty string for no data
        
        # Test empty alpha results
        alpha_report = dashboard.create_alpha_validation_report([])
        assert alpha_report == ""  # Should return empty string for no data
        
        # Test empty performance data
        trend_analysis = dashboard.detect_performance_patterns([])
        assert trend_analysis.trend_direction == "unknown"
        assert trend_analysis.confidence_score == 0.0
    
    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=10, deadline=30000)
    def test_property_output_directory_handling(self, directory_suffix):
        """
        Property: Dashboard should handle different output directories correctly.
        
        This test validates that the dashboard can work with different
        output directory configurations.
        """
        # Create config with custom directory
        safe_suffix = "".join(c for c in directory_suffix if c.isalnum() or c in "._-")[:50]
        custom_dir = Path(self.temp_dir) / safe_suffix
        config = DashboardConfig(output_directory=str(custom_dir))
        
        dashboard = AnalyticsDashboard(config)
        
        # Verify output directory was created
        assert custom_dir.exists()
        assert custom_dir.is_dir()
        
        # Verify dashboard can generate reports in custom directory
        crisis_result = CrisisValidationResult(
            crisis_period="test_crisis",
            start_date=datetime(2008, 1, 1),
            end_date=datetime(2009, 1, 1),
            total_return=-0.1,
            max_drawdown=-0.2,
            volatility=0.3,
            sharpe_ratio=0.5,
            var_breach_count=2,
            stress_test_passed=True
        )
        
        report_path = dashboard.create_crisis_performance_report([crisis_result])
        
        # Verify report was created in custom directory
        if report_path:  # Only check if report was generated
            assert str(custom_dir) in report_path


if __name__ == "__main__":
    # Configure logging for test runs
    logging.basicConfig(level=logging.INFO)
    
    # Run the property tests
    pytest.main([__file__, "-v", "--tb=short"])