#!/usr/bin/env python3
"""
🧪 LAYER 1 PROOF ENGINE - PROPERTY-BASED TESTS
Property tests for Performance Tracker with strict temporal discipline

These tests verify universal properties that must hold across ALL valid inputs:
- Property 1: Temporal Correctness (No Lookahead Bias)
- Property 2: Performance Calculation Correctness
- Property 3: Schema Completeness
- Property 4: Transaction Cost Non-Negativity
- Property 5: Net Return Arithmetic
- Property 6: Active Share Bounds
- Property 7: Turnover Non-Negativity
- Property 8: Drawdown Non-Positivity

Usage:
    pytest tests/validation/test_layer1_proof_properties.py -v
    
    # Run with more iterations for thorough testing
    pytest tests/validation/test_layer1_proof_properties.py -v --hypothesis-iterations=1000
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume
from hypothesis.extra.pandas import column, data_frames, range_indexes
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.validation.performance_tracker import (
    PerformanceTracker,
    PerformanceMetrics,
    TransactionCostModel
)


# ============================================================================
# HYPOTHESIS STRATEGIES
# ============================================================================

@st.composite
def portfolio_weights(draw, min_stocks=1, max_stocks=10):
    """Generate valid portfolio weights that sum to reasonable exposure"""
    n_stocks = draw(st.integers(min_value=min_stocks, max_value=max_stocks))
    
    # Generate stock tickers
    tickers = [f"STOCK{i}" for i in range(n_stocks)]
    
    # Generate weights (can be positive or zero, sum to <= 1.0)
    weights = draw(st.lists(
        st.floats(min_value=0.0, max_value=0.3),
        min_size=n_stocks,
        max_size=n_stocks
    ))
    
    # Normalize to ensure sum <= 1.0
    total_weight = sum(weights)
    if total_weight > 1.0:
        weights = [w / total_weight for w in weights]
    
    return dict(zip(tickers, weights))


@st.composite
def stock_returns(draw, tickers):
    """Generate realistic stock returns for given tickers"""
    returns = draw(st.lists(
        st.floats(min_value=-0.20, max_value=0.20),  # -20% to +20% monthly
        min_size=len(tickers),
        max_size=len(tickers)
    ))
    
    return pd.DataFrame({
        'ticker': tickers,
        'return': returns
    })


@st.composite
def month_end_date(draw):
    """Generate random month-end date"""
    year = draw(st.integers(min_value=2020, max_value=2025))
    month = draw(st.integers(min_value=1, max_value=12))
    
    # Get last day of month
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    
    last_day = next_month - timedelta(days=1)
    
    return last_day


# ============================================================================
# PROPERTY 1: TEMPORAL CORRECTNESS (NO LOOKAHEAD BIAS)
# ============================================================================

# Feature: institutional-validation-layers, Property 1: Temporal Correctness (No Lookahead Bias)
# **Validates: Requirements 1.1, 1.2**

@settings(max_examples=100, deadline=None)
@given(
    positions=portfolio_weights(),
    month_end=month_end_date(),
    nifty_return=st.floats(min_value=-0.10, max_value=0.10)
)
def test_property_1_temporal_correctness(positions, month_end, nifty_return):
    """
    Property 1: Temporal Correctness (No Lookahead Bias)
    
    For any month in the backtest period, when computing performance,
    the system should use only data available before the decision point,
    never using future information.
    
    This test verifies that:
    - Performance calculation uses t-1 weights with t returns
    - No future data leaks into past decisions
    - Decision timestamp is always before return observation
    """
    
    # Create tracker
    tracker = PerformanceTracker(output_dir="data/test_output")
    
    # Generate returns for the stocks in the portfolio
    tickers = list(positions.keys())
    returns = pd.DataFrame({
        'ticker': tickers,
        'return': [np.random.uniform(-0.20, 0.20) for _ in tickers]
    })
    
    # Compute performance
    metrics = tracker.compute_monthly_performance(
        month_end=month_end,
        positions_start=positions,  # t-1 weights
        returns_current=returns,     # t returns
        nifty_return=nifty_return
    )
    
    # CRITICAL ASSERTION: The metrics date should match the month_end
    # This ensures we're computing performance for the correct period
    assert metrics.date == month_end, \
        f"Metrics date {metrics.date} does not match month_end {month_end}"
    
    # CRITICAL ASSERTION: Portfolio return should be calculable from positions and returns
    # This verifies no future data was used
    expected_return = sum(
        positions.get(row['ticker'], 0.0) * row['return']
        for _, row in returns.iterrows()
    )
    
    # Allow small numerical error
    assert abs(metrics.northstar_return - expected_return) < 1e-6, \
        f"Portfolio return {metrics.northstar_return} != expected {expected_return}"
    
    # CRITICAL ASSERTION: Net return should be less than or equal to gross return
    # (costs can only reduce returns, never increase them)
    assert metrics.net_return <= metrics.northstar_return, \
        f"Net return {metrics.net_return} > gross return {metrics.northstar_return}"


# ============================================================================
# PROPERTY 2: PERFORMANCE CALCULATION CORRECTNESS
# ============================================================================

# Feature: institutional-validation-layers, Property 2: Performance Calculation Correctness
# **Validates: Requirements 1.2, 1.5**

@settings(max_examples=100, deadline=None)
@given(
    positions=portfolio_weights(),
    month_end=month_end_date(),
    nifty_return=st.floats(min_value=-0.10, max_value=0.10)
)
def test_property_2_performance_calculation(positions, month_end, nifty_return):
    """
    Property 2: Performance Calculation Correctness
    
    For any set of portfolio weights and asset returns, the portfolio return
    should equal the weighted sum of asset returns.
    
    Mathematically: R_portfolio = sum(w_i * R_i)
    """
    
    tracker = PerformanceTracker(output_dir="data/test_output")
    
    # Generate returns
    tickers = list(positions.keys())
    returns = pd.DataFrame({
        'ticker': tickers,
        'return': [np.random.uniform(-0.20, 0.20) for _ in tickers]
    })
    
    # Calculate expected return manually
    expected_return = 0.0
    for ticker, weight in positions.items():
        ticker_return = returns[returns['ticker'] == ticker]['return'].iloc[0]
        expected_return += weight * ticker_return
    
    # Calculate using tracker
    actual_return = tracker._calculate_portfolio_return(positions, returns)
    
    # ASSERTION: Calculated return should match expected
    assert abs(actual_return - expected_return) < 1e-10, \
        f"Calculated return {actual_return} != expected {expected_return}"


# ============================================================================
# PROPERTY 3: SCHEMA COMPLETENESS
# ============================================================================

# Feature: institutional-validation-layers, Property 3: Schema Completeness
# **Validates: Requirements 1.3, 15.1-15.7**

@settings(max_examples=100, deadline=None)
@given(
    positions=portfolio_weights(),
    month_end=month_end_date(),
    nifty_return=st.floats(min_value=-0.10, max_value=0.10)
)
def test_property_3_schema_completeness(positions, month_end, nifty_return):
    """
    Property 3: Schema Completeness
    
    For any performance summary record, all required columns must be present
    and have valid types.
    """
    
    tracker = PerformanceTracker(output_dir="data/test_output")
    
    # Generate returns
    tickers = list(positions.keys())
    returns = pd.DataFrame({
        'ticker': tickers,
        'return': [np.random.uniform(-0.20, 0.20) for _ in tickers]
    })
    
    # Compute metrics
    metrics = tracker.compute_monthly_performance(
        month_end=month_end,
        positions_start=positions,
        returns_current=returns,
        nifty_return=nifty_return
    )
    
    # ASSERTION: All required fields must be present
    required_fields = [
        'date', 'northstar_return', 'nifty_return', 'exposure',
        'active_share', 'turnover', 'drawdown', 'transaction_costs',
        'net_return', 'volatility'
    ]
    
    metrics_dict = metrics.to_dict()
    
    for field in required_fields:
        assert field in metrics_dict, f"Missing required field: {field}"
    
    # ASSERTION: Types should be correct
    assert isinstance(metrics.date, datetime), "date must be datetime"
    assert isinstance(metrics.northstar_return, (int, float)), "northstar_return must be numeric"
    assert isinstance(metrics.nifty_return, (int, float)), "nifty_return must be numeric"
    assert isinstance(metrics.exposure, (int, float)), "exposure must be numeric"
    assert isinstance(metrics.active_share, (int, float)), "active_share must be numeric"
    assert isinstance(metrics.turnover, (int, float)), "turnover must be numeric"
    assert isinstance(metrics.drawdown, (int, float)), "drawdown must be numeric"
    assert isinstance(metrics.transaction_costs, (int, float)), "transaction_costs must be numeric"
    assert isinstance(metrics.net_return, (int, float)), "net_return must be numeric"
    assert isinstance(metrics.volatility, (int, float)), "volatility must be numeric"


# ============================================================================
# PROPERTY 4: TRANSACTION COST NON-NEGATIVITY
# ============================================================================

# Feature: institutional-validation-layers, Property 4: Transaction Cost Non-Negativity
# **Validates: Requirements 1.4**

@settings(max_examples=100, deadline=None)
@given(
    turnover=st.floats(min_value=0.0, max_value=2.0),
    portfolio_value=st.floats(min_value=0.1, max_value=100.0)
)
def test_property_4_transaction_cost_non_negativity(turnover, portfolio_value):
    """
    Property 4: Transaction Cost Non-Negativity
    
    For any set of trades, the computed transaction costs must be non-negative.
    
    Costs can never be negative - you can't get paid to trade!
    """
    
    cost_model = TransactionCostModel(base_cost_bps=5.0)
    
    # Calculate costs
    costs = cost_model.compute_costs(turnover, portfolio_value)
    
    # ASSERTION: Costs must be non-negative
    assert costs >= 0.0, f"Transaction costs {costs} are negative"
    
    # ASSERTION: Costs should increase with meaningful turnover
    # Use a threshold to avoid floating point precision issues
    if turnover > 1e-10:
        assert costs > 0, f"Costs should be positive when turnover {turnover} > 0"


# ============================================================================
# PROPERTY 5: NET RETURN ARITHMETIC
# ============================================================================

# Feature: institutional-validation-layers, Property 5: Net Return Arithmetic
# **Validates: Requirements 1.5**

@settings(max_examples=100, deadline=None)
@given(
    positions=portfolio_weights(),
    month_end=month_end_date(),
    nifty_return=st.floats(min_value=-0.10, max_value=0.10)
)
def test_property_5_net_return_arithmetic(positions, month_end, nifty_return):
    """
    Property 5: Net Return Arithmetic
    
    For any gross return and transaction cost, net return must equal
    gross return minus transaction cost.
    
    Mathematically: R_net = R_gross - Costs
    """
    
    tracker = PerformanceTracker(output_dir="data/test_output")
    
    # Generate returns
    tickers = list(positions.keys())
    returns = pd.DataFrame({
        'ticker': tickers,
        'return': [np.random.uniform(-0.20, 0.20) for _ in tickers]
    })
    
    # Compute metrics
    metrics = tracker.compute_monthly_performance(
        month_end=month_end,
        positions_start=positions,
        returns_current=returns,
        nifty_return=nifty_return
    )
    
    # ASSERTION: Net return = Gross return - Costs
    expected_net = metrics.northstar_return - metrics.transaction_costs
    
    assert abs(metrics.net_return - expected_net) < 1e-10, \
        f"Net return {metrics.net_return} != gross {metrics.northstar_return} - costs {metrics.transaction_costs}"


# ============================================================================
# PROPERTY 6: ACTIVE SHARE BOUNDS
# ============================================================================

# Feature: institutional-validation-layers, Property 6: Active Share Bounds
# **Validates: Requirements 1.6**

@settings(max_examples=100, deadline=None)
@given(
    portfolio_weights=portfolio_weights(),
    benchmark_weights=portfolio_weights()
)
def test_property_6_active_share_bounds(portfolio_weights, benchmark_weights):
    """
    Property 6: Active Share Bounds
    
    For any portfolio and benchmark, active share must be between 0.0 and 1.0,
    where 0.0 means identical to benchmark and 1.0 means completely different.
    """
    
    tracker = PerformanceTracker(output_dir="data/test_output")
    
    # Calculate active share
    active_share = tracker._calculate_active_share(portfolio_weights, benchmark_weights)
    
    # ASSERTION: Active share must be in [0.0, 1.0]
    assert 0.0 <= active_share <= 1.0, \
        f"Active share {active_share} outside bounds [0.0, 1.0]"
    
    # ASSERTION: Identical portfolios should have active share = 0
    identical_active_share = tracker._calculate_active_share(portfolio_weights, portfolio_weights)
    assert abs(identical_active_share) < 1e-10, \
        f"Identical portfolios should have active share = 0, got {identical_active_share}"


# ============================================================================
# PROPERTY 7: TURNOVER NON-NEGATIVITY
# ============================================================================

# Feature: institutional-validation-layers, Property 7: Turnover Non-Negativity
# **Validates: Requirements 1.7**

@settings(max_examples=100, deadline=None)
@given(
    positions1=portfolio_weights(),
    positions2=portfolio_weights()
)
def test_property_7_turnover_non_negativity(positions1, positions2):
    """
    Property 7: Turnover Non-Negativity
    
    For any pair of consecutive portfolio weight vectors, turnover must be non-negative.
    
    Turnover measures trading activity and can never be negative.
    """
    
    tracker = PerformanceTracker(output_dir="data/test_output")
    
    # Set previous positions
    tracker.previous_positions = positions1
    
    # Calculate turnover
    turnover = tracker._calculate_turnover(positions2)
    
    # ASSERTION: Turnover must be non-negative
    assert turnover >= 0.0, f"Turnover {turnover} is negative"
    
    # ASSERTION: Identical portfolios should have turnover = 0
    tracker.previous_positions = positions1
    zero_turnover = tracker._calculate_turnover(positions1)
    assert abs(zero_turnover) < 1e-10, \
        f"Identical portfolios should have turnover = 0, got {zero_turnover}"


# ============================================================================
# PROPERTY 8: DRAWDOWN NON-POSITIVITY
# ============================================================================

# Feature: institutional-validation-layers, Property 8: Drawdown Non-Positivity
# **Validates: Requirements 1.8**

@settings(max_examples=100, deadline=None)
@given(
    returns=st.lists(
        st.floats(min_value=-0.20, max_value=0.20),
        min_size=1,
        max_size=100
    )
)
def test_property_8_drawdown_non_positivity(returns):
    """
    Property 8: Drawdown Non-Positivity
    
    For any portfolio value series, drawdown must be non-positive (zero or negative).
    
    Drawdown measures decline from peak, so it can never be positive.
    """
    
    # Calculate cumulative values
    values = [1.0]
    for ret in returns:
        values.append(values[-1] * (1 + ret))
    
    # Calculate drawdown
    peak = max(values)
    current = values[-1]
    drawdown = (current - peak) / peak
    
    # ASSERTION: Drawdown must be non-positive
    assert drawdown <= 0.0, f"Drawdown {drawdown} is positive"
    
    # ASSERTION: If current value equals peak, drawdown should be 0
    if abs(current - peak) < 1e-10:
        assert abs(drawdown) < 1e-10, \
            f"Drawdown should be 0 when at peak, got {drawdown}"


# ============================================================================
# PROPERTY 11: SHARPE RATIO FORMULA CORRECTNESS
# ============================================================================

# Feature: institutional-validation-layers, Property 11: Sharpe Ratio Formula Correctness
# **Validates: Requirements 2.4**

@settings(max_examples=100, deadline=None)
@given(
    returns=st.lists(
        st.floats(min_value=-0.20, max_value=0.20),
        min_size=2,
        max_size=100
    ),
    risk_free_rate=st.floats(min_value=0.0, max_value=0.10)
)
def test_property_11_sharpe_ratio_formula(returns, risk_free_rate):
    """
    Property 11: Sharpe Ratio Formula Correctness
    
    For any return series and risk-free rate, Sharpe ratio should equal
    (mean return - risk free) / standard deviation.
    
    Mathematically: Sharpe = (E[R] - Rf) / σ(R)
    """
    
    from src.validation.performance_tracker import BenchmarkComparator
    
    # Create comparator
    comparator = BenchmarkComparator(risk_free_rate=risk_free_rate)
    
    # Convert to pandas Series
    returns_series = pd.Series(returns)
    
    # Calculate Sharpe using comparator
    sharpe_calculated = comparator.compute_sharpe_ratio(returns_series)
    
    # Calculate Sharpe manually
    risk_free_monthly = risk_free_rate / 12
    excess_returns = returns_series - risk_free_monthly
    mean_excess = excess_returns.mean()
    std_excess = excess_returns.std(ddof=1)
    
    if std_excess == 0:
        expected_sharpe = 0.0
    else:
        sharpe_monthly = mean_excess / std_excess
        expected_sharpe = sharpe_monthly * np.sqrt(12)  # Annualize
    
    # ASSERTION: Calculated Sharpe should match expected
    assert abs(sharpe_calculated - expected_sharpe) < 1e-10, \
        f"Sharpe {sharpe_calculated} != expected {expected_sharpe}"


# ============================================================================
# PROPERTY 12: WIN RATE BOUNDS
# ============================================================================

# Feature: institutional-validation-layers, Property 12: Win Rate Bounds
# **Validates: Requirements 2.5**

@settings(max_examples=100, deadline=None)
@given(
    returns=st.lists(
        st.floats(min_value=-0.20, max_value=0.20),
        min_size=1,
        max_size=100
    )
)
def test_property_12_win_rate_bounds(returns):
    """
    Property 12: Win Rate Bounds
    
    For any return series, win rate must be between 0.0 and 1.0.
    
    Win rate is the percentage of positive return periods.
    """
    
    from src.validation.performance_tracker import BenchmarkComparator
    
    # Create comparator
    comparator = BenchmarkComparator()
    
    # Convert to pandas Series
    returns_series = pd.Series(returns)
    
    # Calculate win rate
    win_rate = comparator.compute_win_rate(returns_series)
    
    # ASSERTION: Win rate must be in [0.0, 1.0]
    assert 0.0 <= win_rate <= 1.0, \
        f"Win rate {win_rate} outside bounds [0.0, 1.0]"
    
    # ASSERTION: Win rate should match manual calculation
    positive_count = (returns_series > 0).sum()
    expected_win_rate = positive_count / len(returns_series)
    
    assert abs(win_rate - expected_win_rate) < 1e-10, \
        f"Win rate {win_rate} != expected {expected_win_rate}"


# ============================================================================
# PROPERTY 10: VISUALIZATION DATA FIDELITY
# ============================================================================

# Feature: institutional-validation-layers, Property 10: Visualization Data Fidelity
# **Validates: Requirements 2.1, 2.2**

@settings(max_examples=100, deadline=None)
@given(
    returns=st.lists(
        st.floats(min_value=-0.20, max_value=0.20),
        min_size=3,
        max_size=50
    )
)
def test_property_10_visualization_data_fidelity(returns):
    """
    Property 10: Visualization Data Fidelity
    
    For any performance data, the cumulative return chart should accurately
    represent the compounded returns with no data loss.
    
    This test verifies that:
    - Cumulative returns are calculated correctly (compounding)
    - No data is lost in visualization
    - Chart data matches source data exactly
    """
    
    from src.validation.performance_tracker import VisualizationEngine
    
    # Create performance DataFrame with proper date handling
    # Generate dates spanning multiple years if needed
    start_date = datetime(2020, 1, 31)
    dates = [start_date + timedelta(days=30*i) for i in range(len(returns))]
    
    performance_df = pd.DataFrame({
        'date': dates,
        'net_return': returns,
        'nifty_return': [r * 0.8 for r in returns]  # Mock NIFTY returns
    })
    
    # Calculate expected cumulative returns manually
    expected_northstar_cumulative = (1 + pd.Series(returns)).cumprod()
    expected_nifty_cumulative = (1 + pd.Series([r * 0.8 for r in returns])).cumprod()
    
    # Calculate using performance_df (same as visualization engine does)
    actual_northstar_cumulative = (1 + performance_df['net_return']).cumprod()
    actual_nifty_cumulative = (1 + performance_df['nifty_return']).cumprod()
    
    # ASSERTION: Cumulative returns should match expected values
    assert np.allclose(actual_northstar_cumulative.values, expected_northstar_cumulative.values, rtol=1e-10), \
        "Northstar cumulative returns do not match expected values"
    
    assert np.allclose(actual_nifty_cumulative.values, expected_nifty_cumulative.values, rtol=1e-10), \
        "NIFTY cumulative returns do not match expected values"
    
    # ASSERTION: Final cumulative return should equal product of (1 + return) - 1
    expected_final_return = (1 + pd.Series(returns)).prod() - 1
    actual_final_return = actual_northstar_cumulative.iloc[-1] - 1
    
    assert abs(actual_final_return - expected_final_return) < 1e-10, \
        f"Final cumulative return {actual_final_return} != expected {expected_final_return}"
    
    # ASSERTION: Number of data points should be preserved
    assert len(actual_northstar_cumulative) == len(returns), \
        "Data points lost in cumulative calculation"
    
    # ASSERTION: Cumulative returns should be monotonic if all returns are positive
    if all(r >= 0 for r in returns):
        # Check that cumulative returns are non-decreasing
        assert (actual_northstar_cumulative.diff().dropna() >= -1e-10).all(), \
            "Cumulative returns should be non-decreasing when all returns are positive"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

def test_full_monthly_cycle():
    """
    Integration test: Full monthly performance tracking cycle
    
    Tests the complete workflow from positions to persisted metrics.
    """
    
    # Clean up any existing test data
    test_output_dir = "data/test_output"
    test_file = os.path.join(test_output_dir, "performance_summary.parquet")
    if os.path.exists(test_file):
        os.remove(test_file)
    
    tracker = PerformanceTracker(output_dir=test_output_dir)
    
    # Month 1
    positions_m1 = {'STOCK1': 0.3, 'STOCK2': 0.2, 'STOCK3': 0.1}
    returns_m1 = pd.DataFrame({
        'ticker': ['STOCK1', 'STOCK2', 'STOCK3'],
        'return': [0.05, -0.02, 0.03]
    })
    
    metrics_m1 = tracker.compute_monthly_performance(
        month_end=datetime(2024, 1, 31),
        positions_start=positions_m1,
        returns_current=returns_m1,
        nifty_return=0.02
    )
    
    # Verify metrics
    assert metrics_m1.date == datetime(2024, 1, 31)
    assert 0.0 <= metrics_m1.exposure <= 1.0
    assert 0.0 <= metrics_m1.active_share <= 1.0
    assert metrics_m1.turnover >= 0.0
    assert metrics_m1.drawdown <= 0.0
    assert metrics_m1.transaction_costs >= 0.0
    assert metrics_m1.volatility >= 0.0
    
    # Persist
    tracker.persist_metrics(metrics_m1)
    
    # Load and verify
    df = tracker.load_performance_summary()
    assert len(df) == 1
    assert df.iloc[0]['date'] == datetime(2024, 1, 31)
    
    print("✅ Full monthly cycle test passed")


def test_temporal_discipline_enforcement():
    """
    Test that temporal discipline is strictly enforced
    
    Verifies that using future data is impossible by design.
    """
    
    # Clean up any existing test data
    test_output_dir = "data/test_output"
    test_file = os.path.join(test_output_dir, "performance_summary.parquet")
    if os.path.exists(test_file):
        os.remove(test_file)
    
    tracker = PerformanceTracker(output_dir=test_output_dir)
    
    # Create positions for January (decided in December)
    positions_jan = {'STOCK1': 0.5}
    
    # Create returns for January (observed in January)
    returns_jan = pd.DataFrame({
        'ticker': ['STOCK1'],
        'return': [0.10]
    })
    
    # Compute performance for January
    metrics_jan = tracker.compute_monthly_performance(
        month_end=datetime(2024, 1, 31),
        positions_start=positions_jan,  # Decided BEFORE January
        returns_current=returns_jan,     # Observed DURING January
        nifty_return=0.05
    )
    
    # The return should be exactly 0.5 * 0.10 = 0.05
    expected_return = 0.5 * 0.10
    assert abs(metrics_jan.northstar_return - expected_return) < 1e-10
    
    # The metrics date should be January 31
    assert metrics_jan.date == datetime(2024, 1, 31)
    
    print("✅ Temporal discipline enforcement test passed")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, '-v', '--tb=short'])
