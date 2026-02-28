"""
Property-Based Tests for Drawdown Calculator

Tests the correctness property:
- Property 7: Drawdown Calculation
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck, assume
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import tempfile
import shutil
from pathlib import Path

from src.cohesion.drawdown_calculator import DrawdownCalculator
from src.cohesion.state_file_manager import StateFileManager


# Strategy for generating equity curves
@st.composite
def equity_curve_strategy(draw):
    """Generate a random equity curve"""
    # Generate 10-100 data points
    n_points = draw(st.integers(min_value=10, max_value=100))
    
    # Start with initial equity of 100
    initial_equity = 100.0
    
    # Generate random returns (daily returns between -5% and +5%)
    returns = draw(st.lists(
        st.floats(min_value=-0.05, max_value=0.05, allow_nan=False, allow_infinity=False),
        min_size=n_points,
        max_size=n_points
    ))
    
    # Calculate equity curve
    equity = [initial_equity]
    for ret in returns:
        equity.append(equity[-1] * (1 + ret))
    
    # Create dates
    start_date = datetime(2020, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(len(equity))]
    
    # Create series
    return pd.Series(equity, index=dates)


class TestDrawdownCalculatorProperties:
    """Property-based tests for DrawdownCalculator"""
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary data directory for testing"""
        temp_dir = tempfile.mkdtemp()
        data_dir = Path(temp_dir) / "data" / "processed"
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # Temporarily override the paths
        original_paths = {
            'market': StateFileManager.MARKET_STATE_PATH,
            'portfolio': StateFileManager.PORTFOLIO_WEIGHTS_PATH,
            'risk': StateFileManager.RISK_STATE_PATH,
            'exposure': StateFileManager.EXPOSURE_HISTORY_PATH,
            'analytics': StateFileManager.PORTFOLIO_ANALYTICS_PATH,
            'backup': StateFileManager.BACKUP_DIR
        }
        
        StateFileManager.MARKET_STATE_PATH = data_dir / "market_state.parquet"
        StateFileManager.PORTFOLIO_WEIGHTS_PATH = data_dir / "portfolio_weights.parquet"
        StateFileManager.RISK_STATE_PATH = data_dir / "risk_state.parquet"
        StateFileManager.EXPOSURE_HISTORY_PATH = data_dir / "exposure_history.parquet"
        StateFileManager.PORTFOLIO_ANALYTICS_PATH = data_dir / "portfolio_analytics.json"
        StateFileManager.BACKUP_DIR = data_dir / "backups"
        StateFileManager.BACKUP_DIR.mkdir(exist_ok=True)
        
        yield temp_dir
        
        # Restore original paths
        StateFileManager.MARKET_STATE_PATH = original_paths['market']
        StateFileManager.PORTFOLIO_WEIGHTS_PATH = original_paths['portfolio']
        StateFileManager.RISK_STATE_PATH = original_paths['risk']
        StateFileManager.EXPOSURE_HISTORY_PATH = original_paths['exposure']
        StateFileManager.PORTFOLIO_ANALYTICS_PATH = original_paths['analytics']
        StateFileManager.BACKUP_DIR = original_paths['backup']
        
        # Clean up
        shutil.rmtree(temp_dir)
    
    @given(equity_curve=equity_curve_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_drawdown_calculation(self, temp_data_dir, equity_curve):
        """
        Property 7: Drawdown Calculation
        
        For any equity time series, the drawdown at time t must equal:
        (equity[t] - max(equity[0:t])) / max(equity[0:t])
        
        Validates: Requirements 8.1
        """
        calculator = DrawdownCalculator()
        
        # Calculate drawdown series
        drawdown_series = calculator.calculate_drawdown_series(equity_curve)
        
        # Verify formula for each point
        for i in range(len(equity_curve)):
            # Calculate expected drawdown using formula
            peak_equity = equity_curve.iloc[:i+1].max()
            current_equity = equity_curve.iloc[i]
            expected_drawdown = (current_equity - peak_equity) / peak_equity
            
            # Get actual drawdown
            actual_drawdown = drawdown_series.iloc[i]
            
            # Verify they match (within floating point tolerance)
            assert abs(actual_drawdown - expected_drawdown) < 1e-10, \
                f"Drawdown formula violated at index {i}: " \
                f"expected {expected_drawdown:.6f}, got {actual_drawdown:.6f}"
    
    @given(equity_curve=equity_curve_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_drawdown_non_positive(self, temp_data_dir, equity_curve):
        """
        Property: Drawdown is always non-positive
        
        Drawdown represents decline from peak, so it should always be <= 0
        """
        calculator = DrawdownCalculator()
        
        # Calculate drawdown series
        drawdown_series = calculator.calculate_drawdown_series(equity_curve)
        
        # Verify all drawdowns are non-positive
        assert (drawdown_series <= 0).all(), \
            f"Found positive drawdown values: {drawdown_series[drawdown_series > 0]}"
    
    @given(equity_curve=equity_curve_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_max_drawdown_is_minimum(self, temp_data_dir, equity_curve):
        """
        Property: Maximum drawdown is the most negative value in drawdown series
        """
        calculator = DrawdownCalculator()
        
        # Calculate drawdown series and max drawdown
        drawdown_series = calculator.calculate_drawdown_series(equity_curve)
        max_dd = calculator.calculate_max_drawdown(equity_curve)
        
        # Max drawdown should equal the minimum (most negative) value
        expected_max_dd = drawdown_series.min()
        
        assert abs(max_dd - expected_max_dd) < 1e-10, \
            f"Max drawdown mismatch: expected {expected_max_dd:.6f}, got {max_dd:.6f}"
    
    @given(equity_curve=equity_curve_strategy())
    @settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_property_current_drawdown_is_last(self, temp_data_dir, equity_curve):
        """
        Property: Current drawdown is the last value in drawdown series
        """
        calculator = DrawdownCalculator()
        
        # Calculate drawdown series and current drawdown
        drawdown_series = calculator.calculate_drawdown_series(equity_curve)
        current_dd = calculator.calculate_current_drawdown(equity_curve)
        
        # Current drawdown should equal the last value
        expected_current_dd = drawdown_series.iloc[-1]
        
        assert abs(current_dd - expected_current_dd) < 1e-10, \
            f"Current drawdown mismatch: expected {expected_current_dd:.6f}, got {current_dd:.6f}"
    
    def test_drawdown_at_peak_is_zero(self, temp_data_dir):
        """
        Test that drawdown is zero when equity is at a new peak
        """
        calculator = DrawdownCalculator()
        
        # Create monotonically increasing equity curve (always at new peaks)
        dates = [datetime(2020, 1, 1) + timedelta(days=i) for i in range(10)]
        equity = pd.Series([100, 105, 110, 115, 120, 125, 130, 135, 140, 145], index=dates)
        
        # Calculate drawdown
        drawdown_series = calculator.calculate_drawdown_series(equity)
        
        # All drawdowns should be zero (always at peak)
        assert (drawdown_series == 0).all(), \
            f"Expected all zeros for monotonic increase, got {drawdown_series.tolist()}"
    
    def test_drawdown_simple_decline(self, temp_data_dir):
        """
        Test drawdown calculation with a simple decline
        """
        calculator = DrawdownCalculator()
        
        # Create equity curve: peak at 100, decline to 80 (20% drawdown)
        dates = [datetime(2020, 1, 1) + timedelta(days=i) for i in range(3)]
        equity = pd.Series([100, 90, 80], index=dates)
        
        # Calculate drawdown
        drawdown_series = calculator.calculate_drawdown_series(equity)
        
        # Expected: [0, -0.1, -0.2]
        expected = [0.0, -0.1, -0.2]
        
        for i, exp in enumerate(expected):
            assert abs(drawdown_series.iloc[i] - exp) < 1e-10, \
                f"At index {i}: expected {exp}, got {drawdown_series.iloc[i]}"
    
    def test_drawdown_with_recovery(self, temp_data_dir):
        """
        Test drawdown calculation with decline and recovery
        """
        calculator = DrawdownCalculator()
        
        # Create equity curve: peak, decline, recovery to new peak
        dates = [datetime(2020, 1, 1) + timedelta(days=i) for i in range(5)]
        equity = pd.Series([100, 90, 80, 90, 110], index=dates)
        
        # Calculate drawdown
        drawdown_series = calculator.calculate_drawdown_series(equity)
        
        # Expected: [0, -0.1, -0.2, -0.1, 0]
        expected = [0.0, -0.1, -0.2, -0.1, 0.0]
        
        for i, exp in enumerate(expected):
            assert abs(drawdown_series.iloc[i] - exp) < 1e-10, \
                f"At index {i}: expected {exp}, got {drawdown_series.iloc[i]}"
    
    def test_calculate_and_store_analytics(self, temp_data_dir):
        """
        Test that analytics are calculated and stored correctly
        """
        state_manager = StateFileManager()
        calculator = DrawdownCalculator(state_manager)
        
        # Create sample equity curves
        dates = [datetime(2020, 1, 1) + timedelta(days=i) for i in range(100)]
        portfolio_equity = pd.Series(
            [100 * (1.001 ** i) for i in range(100)],  # Slight upward trend
            index=dates
        )
        benchmark_equity = pd.Series(
            [100 * (1.0005 ** i) for i in range(100)],  # Slower upward trend
            index=dates
        )
        
        # Calculate and store
        analytics = calculator.calculate_and_store_analytics(
            portfolio_equity,
            benchmark_equity,
            as_of_date=datetime(2020, 4, 9)
        )
        
        # Verify structure
        assert 'as_of_date' in analytics
        assert 'portfolio_metrics' in analytics
        assert 'benchmark_metrics' in analytics
        assert 'relative_performance' in analytics
        
        # Verify portfolio metrics
        assert 'total_return' in analytics['portfolio_metrics']
        assert 'sharpe_ratio' in analytics['portfolio_metrics']
        assert 'max_drawdown' in analytics['portfolio_metrics']
        assert 'current_drawdown' in analytics['portfolio_metrics']
        assert 'volatility' in analytics['portfolio_metrics']
        
        # Verify it was stored
        stored_analytics = calculator.get_latest_analytics()
        assert stored_analytics is not None
        assert stored_analytics['as_of_date'] == '2020-04-09'
    
    def test_empty_equity_curve(self, temp_data_dir):
        """
        Test that empty equity curves are handled gracefully
        """
        calculator = DrawdownCalculator()
        
        # Empty series
        empty_equity = pd.Series(dtype=float)
        
        # Should return empty series
        drawdown_series = calculator.calculate_drawdown_series(empty_equity)
        assert len(drawdown_series) == 0
        
        # Should return 0.0 for metrics
        max_dd = calculator.calculate_max_drawdown(empty_equity)
        assert max_dd == 0.0
        
        current_dd = calculator.calculate_current_drawdown(empty_equity)
        assert current_dd == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
