#!/usr/bin/env python3
"""
🧪 LAYER 2 RISK PROTECTION - PROPERTY-BASED TESTS
Property tests for Kill Switch System and Risk Protection

These tests verify universal properties that must hold across ALL valid inputs:
- Property 13: Kill Switch Activation (Drawdown Brake)
- Property 14: Daily Loss Brake
- Property 15: Volatility Brake
- Property 16: Kill Switch Logging
- Property 17: Risk Budget Enforcement

Usage:
    pytest tests/validation/test_layer2_risk_properties.py -v
    
    # Run with more iterations for thorough testing
    pytest tests/validation/test_layer2_risk_properties.py -v --hypothesis-iterations=1000
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume
import sys
import os
import tempfile
import shutil

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.validation.kill_switch_system import KillSwitchSystem, RiskState
from src.validation.risk_budget_enforcer import RiskBudgetEnforcer, SectorRiskState


# ============================================================================
# HYPOTHESIS STRATEGIES
# ============================================================================

@st.composite
def performance_data_with_drawdown(draw, min_days=30, max_days=100):
    """
    Generate performance data with controlled drawdown
    
    Returns DataFrame with columns: date, net_return, exposure
    """
    n_days = draw(st.integers(min_value=min_days, max_value=max_days))
    
    # Generate dates
    start_date = datetime(2024, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(n_days)]
    
    # Generate returns with potential drawdown
    returns = []
    for i in range(n_days):
        # Occasionally inject large losses to create drawdowns
        if draw(st.booleans()) and i > 10:  # Occasional drawdown
            ret = draw(st.floats(min_value=-0.15, max_value=-0.05))  # -15% to -5%
        else:
            ret = draw(st.floats(min_value=-0.03, max_value=0.03))  # Normal returns
        returns.append(ret)
    
    # Generate exposure (typically high)
    exposure = draw(st.floats(min_value=0.5, max_value=1.0))
    
    df = pd.DataFrame({
        'date': dates,
        'net_return': returns,
        'exposure': [exposure] * n_days
    })
    
    return df


@st.composite
def performance_data_with_daily_loss(draw, min_days=30, max_days=100):
    """
    Generate performance data with potential large daily losses
    
    Returns DataFrame with columns: date, net_return, exposure
    """
    n_days = draw(st.integers(min_value=min_days, max_value=max_days))
    
    # Generate dates
    start_date = datetime(2024, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(n_days)]
    
    # Generate returns with occasional large losses
    returns = []
    for i in range(n_days):
        if i == n_days - 1:  # Last day - potential large loss
            ret = draw(st.floats(min_value=-0.10, max_value=0.03))
        else:
            ret = draw(st.floats(min_value=-0.02, max_value=0.02))
        returns.append(ret)
    
    # Generate exposure
    exposure = draw(st.floats(min_value=0.5, max_value=1.0))
    
    df = pd.DataFrame({
        'date': dates,
        'net_return': returns,
        'exposure': [exposure] * n_days
    })
    
    return df


@st.composite
def performance_data_with_volatility(draw, min_days=30, max_days=100):
    """
    Generate performance data with controlled volatility
    
    Returns DataFrame with columns: date, net_return, exposure
    """
    n_days = draw(st.integers(min_value=min_days, max_value=max_days))
    
    # Generate dates
    start_date = datetime(2024, 1, 1)
    dates = [start_date + timedelta(days=i) for i in range(n_days)]
    
    # Generate returns with controlled volatility
    # Draw target daily volatility
    daily_vol = draw(st.floats(min_value=0.005, max_value=0.05))  # 0.5% to 5% daily
    
    returns = []
    for i in range(n_days):
        ret = draw(st.floats(min_value=-3*daily_vol, max_value=3*daily_vol))
        returns.append(ret)
    
    # Generate exposure
    exposure = draw(st.floats(min_value=0.5, max_value=1.0))
    
    df = pd.DataFrame({
        'date': dates,
        'net_return': returns,
        'exposure': [exposure] * n_days
    })
    
    return df


# ============================================================================
# PROPERTY TESTS
# ============================================================================

# Feature: institutional-validation-layers, Property 13: Kill Switch Activation
@settings(max_examples=100, deadline=None)
@given(perf_data=performance_data_with_drawdown())
def test_property_13_kill_switch_activation_drawdown(perf_data):
    """
    Property 13: Kill Switch Activation (Drawdown Brake)
    
    For any portfolio state where drawdown exceeds 20%, the kill switch
    should activate and reduce exposure to 50% of current level.
    
    Validates: Requirements 3.1
    """
    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup test environment
        perf_file = os.path.join(tmpdir, 'performance_summary.parquet')
        risk_file = os.path.join(tmpdir, 'risk_state.parquet')
        
        # Save performance data
        perf_data.to_parquet(perf_file, index=False)
        
        # Create kill switch system with test paths
        kill_switches = KillSwitchSystem(
            max_drawdown=0.20,
            max_daily_loss=0.05,
            max_volatility=0.30
        )
        kill_switches.performance_file = perf_file
        kill_switches.risk_state_file = risk_file
        
        # Evaluate kill switches
        risk_state = kill_switches.evaluate_kill_switches(perf_data)
        
        # Calculate actual drawdown
        equity_curve = (1 + perf_data['net_return']).cumprod()
        running_max = equity_curve.expanding().max()
        current_drawdown = (equity_curve.iloc[-1] / running_max.iloc[-1]) - 1.0
        
        # Property: If drawdown > 20%, kill switch must activate
        if abs(current_drawdown) > 0.20:
            assert risk_state.emergency_active, \
                f"Kill switch should activate for drawdown {current_drawdown:.2%}"
            
            # Check exposure reduction
            current_exposure = perf_data['exposure'].iloc[-1]
            
            # Check if daily loss brake also triggered (takes priority)
            daily_return = perf_data['net_return'].iloc[-1]
            if daily_return < -0.05:
                # Daily loss brake takes priority - expect 25% exposure
                expected_cap = current_exposure * 0.25
                assert risk_state.kill_switch_triggered == "DAILY_LOSS_BRAKE"
            else:
                # Only drawdown brake - expect 50% exposure
                expected_cap = current_exposure * 0.50
                assert risk_state.kill_switch_triggered == "DRAWDOWN_BRAKE"
            
            # Allow small tolerance for floating point
            assert abs(risk_state.exposure_cap - expected_cap) < 0.01, \
                f"Exposure should be reduced to {expected_cap:.2%}: got {risk_state.exposure_cap:.2%}"
        
        # Property: Drawdown should match calculated value
        assert abs(risk_state.drawdown - current_drawdown) < 0.001, \
            f"Drawdown mismatch: expected {current_drawdown:.4f}, got {risk_state.drawdown:.4f}"


# Feature: institutional-validation-layers, Property 14: Daily Loss Brake
@settings(max_examples=100, deadline=None)
@given(perf_data=performance_data_with_daily_loss())
def test_property_14_daily_loss_brake(perf_data):
    """
    Property 14: Daily Loss Brake
    
    For any day where portfolio loss exceeds 5%, the kill switch should
    reduce exposure to 25% of current level.
    
    Validates: Requirements 3.2
    """
    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup test environment
        perf_file = os.path.join(tmpdir, 'performance_summary.parquet')
        risk_file = os.path.join(tmpdir, 'risk_state.parquet')
        
        # Save performance data
        perf_data.to_parquet(perf_file, index=False)
        
        # Create kill switch system with test paths
        kill_switches = KillSwitchSystem(
            max_drawdown=0.20,
            max_daily_loss=0.05,
            max_volatility=0.30
        )
        kill_switches.performance_file = perf_file
        kill_switches.risk_state_file = risk_file
        
        # Evaluate kill switches
        risk_state = kill_switches.evaluate_kill_switches(perf_data)
        
        # Get last day's return
        daily_return = perf_data['net_return'].iloc[-1]
        
        # Property: If daily loss > 5%, kill switch must activate
        if daily_return < -0.05:
            assert risk_state.emergency_active, \
                f"Kill switch should activate for daily loss {daily_return:.2%}"
            
            # Check exposure reduction
            current_exposure = perf_data['exposure'].iloc[-1]
            expected_cap = current_exposure * 0.25
            
            # Allow small tolerance for floating point
            assert abs(risk_state.exposure_cap - expected_cap) < 0.01, \
                f"Exposure should be reduced to 25%: expected {expected_cap:.2%}, got {risk_state.exposure_cap:.2%}"
            
            # Check kill switch type (daily loss has priority)
            assert risk_state.kill_switch_triggered == "DAILY_LOSS_BRAKE", \
                f"Expected daily loss brake, got {risk_state.kill_switch_triggered}"
        
        # Property: Daily return should match
        assert abs(risk_state.daily_return - daily_return) < 0.0001, \
            f"Daily return mismatch: expected {daily_return:.4f}, got {risk_state.daily_return:.4f}"


# Feature: institutional-validation-layers, Property 15: Volatility Brake
@settings(max_examples=100, deadline=None)
@given(perf_data=performance_data_with_volatility(min_days=30, max_days=100))
def test_property_15_volatility_brake(perf_data):
    """
    Property 15: Volatility Brake
    
    For any period where 30-day realized volatility exceeds 30%, exposure
    should be capped at 60%.
    
    Validates: Requirements 3.3
    """
    # Need at least 30 days for volatility calculation
    assume(len(perf_data) >= 30)
    
    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup test environment
        perf_file = os.path.join(tmpdir, 'performance_summary.parquet')
        risk_file = os.path.join(tmpdir, 'risk_state.parquet')
        
        # Save performance data
        perf_data.to_parquet(perf_file, index=False)
        
        # Create kill switch system with test paths
        kill_switches = KillSwitchSystem(
            max_drawdown=0.20,
            max_daily_loss=0.05,
            max_volatility=0.30,
            vol_lookback=30
        )
        kill_switches.performance_file = perf_file
        kill_switches.risk_state_file = risk_file
        
        # Evaluate kill switches
        risk_state = kill_switches.evaluate_kill_switches(perf_data)
        
        # Calculate realized volatility
        returns = perf_data['net_return'].tail(30)
        realized_vol = returns.std() * np.sqrt(252)
        
        # Property: If volatility > 30%, kill switch must activate
        if realized_vol > 0.30:
            assert risk_state.emergency_active, \
                f"Kill switch should activate for volatility {realized_vol:.2%}"
            
            # Check exposure cap
            assert risk_state.exposure_cap <= 0.60, \
                f"Exposure should be capped at 60%: got {risk_state.exposure_cap:.2%}"
        
        # Property: Realized volatility should match (within tolerance)
        assert abs(risk_state.realized_vol - realized_vol) < 0.05, \
            f"Volatility mismatch: expected {realized_vol:.4f}, got {risk_state.realized_vol:.4f}"


# Feature: institutional-validation-layers, Property 16: Kill Switch Logging
@settings(max_examples=50, deadline=None)
@given(perf_data=performance_data_with_drawdown())
def test_property_16_kill_switch_logging(perf_data):
    """
    Property 16: Kill Switch Logging
    
    For any kill switch activation, a log entry must be created in
    risk_state.parquet with all required fields.
    
    Validates: Requirements 3.4
    """
    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup test environment
        perf_file = os.path.join(tmpdir, 'performance_summary.parquet')
        risk_file = os.path.join(tmpdir, 'risk_state.parquet')
        
        # Save performance data
        perf_data.to_parquet(perf_file, index=False)
        
        # Create kill switch system with test paths
        kill_switches = KillSwitchSystem()
        kill_switches.performance_file = perf_file
        kill_switches.risk_state_file = risk_file
        
        # Evaluate and log
        risk_state = kill_switches.evaluate_kill_switches(perf_data)
        kill_switches.log_risk_state(risk_state)
        
        # Property: Log file must exist
        assert os.path.exists(risk_file), "Risk state log file should be created"
        
        # Property: Log must contain required fields
        log_df = pd.read_parquet(risk_file)
        
        required_fields = [
            'date', 'portfolio_value', 'drawdown', 'daily_return',
            'realized_vol', 'risk_level', 'emergency_active', 'exposure_cap'
        ]
        
        for field in required_fields:
            assert field in log_df.columns, f"Required field '{field}' missing from log"
        
        # Property: Log should have at least one entry
        assert len(log_df) > 0, "Log should contain at least one entry"
        
        # Property: Latest entry should match risk state
        latest = log_df.iloc[-1]
        assert abs(latest['drawdown'] - risk_state.drawdown) < 0.001
        assert abs(latest['daily_return'] - risk_state.daily_return) < 0.001
        assert latest['emergency_active'] == risk_state.emergency_active


# Feature: institutional-validation-layers, Property 0.2: Monotonic Risk Response
@settings(max_examples=100, deadline=None)
@given(perf_data=performance_data_with_drawdown(min_days=50, max_days=100))
def test_property_0_2_monotonic_risk_response(perf_data):
    """
    Property 0.2: Monotonic Risk Response
    
    As measured risk increases, allowed exposure SHALL not increase.
    
    Validates: Requirements 3.1, 3.2, 3.3
    """
    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup test environment
        perf_file = os.path.join(tmpdir, 'performance_summary.parquet')
        risk_file = os.path.join(tmpdir, 'risk_state.parquet')
        
        # Create kill switch system
        kill_switches = KillSwitchSystem()
        kill_switches.performance_file = perf_file
        kill_switches.risk_state_file = risk_file
        
        # Evaluate risk at different points in time
        risk_levels = []
        exposure_caps = []
        
        # Sample at multiple points
        for i in range(30, len(perf_data), 10):
            subset = perf_data.iloc[:i]
            subset.to_parquet(perf_file, index=False)
            
            risk_state = kill_switches.evaluate_kill_switches(subset)
            risk_levels.append(risk_state.risk_level)
            exposure_caps.append(risk_state.exposure_cap)
        
        # Property: When risk increases, exposure should not increase
        for i in range(1, len(risk_levels)):
            if risk_levels[i] > risk_levels[i-1]:
                # Risk increased - exposure should not increase
                assert exposure_caps[i] <= exposure_caps[i-1] + 0.01, \
                    f"Exposure increased when risk increased: " \
                    f"risk {risk_levels[i-1]:.2f} → {risk_levels[i]:.2f}, " \
                    f"exposure {exposure_caps[i-1]:.2%} → {exposure_caps[i]:.2%}"


# Feature: institutional-validation-layers, Property 0.3: Bounded Exposure
@settings(max_examples=100, deadline=None)
@given(perf_data=performance_data_with_drawdown())
def test_property_0_3_bounded_exposure(perf_data):
    """
    Property 0.3: Bounded Exposure
    
    For all times t, exposure must satisfy: 0 ≤ Exposure_t ≤ 1.0
    
    Validates: Requirements 3.1, 3.2, 3.3
    """
    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup test environment
        perf_file = os.path.join(tmpdir, 'performance_summary.parquet')
        risk_file = os.path.join(tmpdir, 'risk_state.parquet')
        
        # Save performance data
        perf_data.to_parquet(perf_file, index=False)
        
        # Create kill switch system
        kill_switches = KillSwitchSystem()
        kill_switches.performance_file = perf_file
        kill_switches.risk_state_file = risk_file
        
        # Evaluate kill switches
        risk_state = kill_switches.evaluate_kill_switches(perf_data)
        
        # Property: Exposure must be bounded [0, 1]
        assert 0.0 <= risk_state.exposure_cap <= 1.0, \
            f"Exposure cap {risk_state.exposure_cap:.2%} is outside valid range [0%, 100%]"
        
        # Property: Risk level must be bounded [0, 1]
        assert 0.0 <= risk_state.risk_level <= 1.0, \
            f"Risk level {risk_state.risk_level:.2f} is outside valid range [0.0, 1.0]"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--hypothesis-show-statistics"])

@st.composite
def portfolio_with_sector_violations(draw, min_positions=5, max_positions=20):
    """
    Generate portfolio with potential sector limit violations
    
    Returns Dict[str, Dict] with ticker -> {'weight': float, 'sector': str}
    """
    n_positions = draw(st.integers(min_value=min_positions, max_value=max_positions))
    
    # Define sectors with their limits
    sectors = ['Banks', 'IT', 'Metals', 'Pharma', 'Auto', 'FMCG', 'Energy']
    sector_limits = {
        'Banks': 0.10, 'IT': 0.08, 'Metals': 0.06, 'Pharma': 0.07,
        'Auto': 0.05, 'FMCG': 0.05, 'Energy': 0.05
    }
    
    portfolio = {}
    
    for i in range(n_positions):
        ticker = f"STOCK_{i:03d}"
        sector = draw(st.sampled_from(sectors))
        
        # Generate weight - sometimes exceed sector limits
        if draw(st.booleans()):  # 50% chance of normal weight
            weight = draw(st.floats(min_value=0.001, max_value=0.05))
        else:  # 50% chance of larger weight that might cause violations
            weight = draw(st.floats(min_value=0.02, max_value=0.08))
        
        portfolio[ticker] = {
            'weight': weight,
            'sector': sector
        }
    
    return portfolio


@st.composite
def portfolio_with_known_violations(draw):
    """
    Generate portfolio with guaranteed sector violations for testing
    
    Returns Dict[str, Dict] with ticker -> {'weight': float, 'sector': str}
    """
    # Create portfolio that definitely violates Banks limit (10%)
    portfolio = {
        'BANK_1': {'weight': 0.06, 'sector': 'Banks'},
        'BANK_2': {'weight': 0.05, 'sector': 'Banks'},
        'BANK_3': {'weight': 0.04, 'sector': 'Banks'},  # Total: 15% > 10%
        'IT_1': {'weight': 0.05, 'sector': 'IT'},
        'IT_2': {'weight': 0.04, 'sector': 'IT'},       # Total: 9% > 8%
        'METAL_1': {'weight': 0.04, 'sector': 'Metals'},
        'METAL_2': {'weight': 0.03, 'sector': 'Metals'}, # Total: 7% > 6%
        'PHARMA_1': {'weight': 0.03, 'sector': 'Pharma'}, # Total: 3% < 7% (OK)
    }
    
    # Add some randomness to weights
    for ticker in portfolio:
        noise = draw(st.floats(min_value=-0.01, max_value=0.01))
        portfolio[ticker]['weight'] = max(0.001, portfolio[ticker]['weight'] + noise)
    
    return portfolio


# ============================================================================
# RISK BUDGET ENFORCEMENT PROPERTY TESTS
# ============================================================================

# Feature: institutional-validation-layers, Property 17: Risk Budget Enforcement
@settings(max_examples=100, deadline=None)
@given(portfolio=portfolio_with_sector_violations())
def test_property_17_risk_budget_enforcement(portfolio):
    """
    Property 17: Risk Budget Enforcement
    
    For any portfolio where a sector exceeds its risk limit, all positions
    in that sector should be scaled down proportionally to meet the limit.
    
    Validates: Requirements 4.1, 4.2
    """
    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup test environment
        risk_budget_file = os.path.join(tmpdir, 'risk_budget.parquet')
        risk_budget_state_file = os.path.join(tmpdir, 'risk_budget_state.parquet')
        
        # Create risk budget enforcer with test paths
        enforcer = RiskBudgetEnforcer()
        enforcer.risk_budget_file = risk_budget_file
        enforcer.risk_budget_state_file = risk_budget_state_file
        
        # Calculate original sector risks
        original_sector_risks = enforcer.calculate_sector_risks(portfolio)
        
        # Enforce risk budget
        adjusted_portfolio, budget_state = enforcer.enforce_risk_budget(portfolio)
        
        # Calculate adjusted sector risks
        adjusted_sector_risks = enforcer.calculate_sector_risks(adjusted_portfolio)
        
        # Property: No sector should exceed its limit after enforcement
        for sector, adjusted_risk in adjusted_sector_risks.items():
            limit = enforcer.get_sector_limit(sector)
            assert adjusted_risk <= limit + 0.001, \
                f"Sector {sector} still exceeds limit: {adjusted_risk:.3f} > {limit:.3f}"
        
        # Property: If original sector was within limit, it should remain unchanged
        for sector in original_sector_risks:
            original_risk = original_sector_risks[sector]
            limit = enforcer.get_sector_limit(sector)
            
            if original_risk <= limit:
                adjusted_risk = adjusted_sector_risks.get(sector, 0.0)
                # Allow small tolerance for floating point arithmetic
                assert abs(adjusted_risk - original_risk) < 0.001, \
                    f"Sector {sector} was within limit but was changed: " \
                    f"{original_risk:.3f} -> {adjusted_risk:.3f}"
        
        # Property: Proportional scaling within sectors
        for sector in original_sector_risks:
            original_risk = original_sector_risks[sector]
            limit = enforcer.get_sector_limit(sector)
            
            if original_risk > limit:
                # Check that all positions in this sector were scaled by same factor
                expected_scale = limit / original_risk
                
                sector_positions = [
                    (ticker, pos) for ticker, pos in adjusted_portfolio.items()
                    if pos.get('sector') == sector and pos.get('weight', 0) != 0
                ]
                
                for ticker, pos in sector_positions:
                    if 'original_weight' in pos:
                        actual_scale = pos['weight'] / pos['original_weight']
                        assert abs(actual_scale - expected_scale) < 0.01, \
                            f"Position {ticker} not scaled correctly: " \
                            f"expected {expected_scale:.3f}, got {actual_scale:.3f}"


# Feature: institutional-validation-layers, Property 18: Sector Risk Bounds
@settings(max_examples=100, deadline=None)
@given(portfolio=portfolio_with_known_violations())
def test_property_18_sector_risk_bounds(portfolio):
    """
    Property 18: Sector Risk Bounds
    
    For any sector in the portfolio, current risk must not exceed the
    defined maximum risk after enforcement.
    
    Validates: Requirements 4.1
    """
    # Create risk budget enforcer
    enforcer = RiskBudgetEnforcer()
    
    # Enforce risk budget
    adjusted_portfolio, budget_state = enforcer.enforce_risk_budget(portfolio)
    
    # Calculate sector risks after enforcement
    sector_risks = enforcer.calculate_sector_risks(adjusted_portfolio)
    
    # Property: All sectors must be within their limits
    for sector, current_risk in sector_risks.items():
        limit = enforcer.get_sector_limit(sector)
        
        assert current_risk <= limit + 0.001, \
            f"Sector {sector} exceeds limit after enforcement: " \
            f"{current_risk:.3f} > {limit:.3f}"
    
    # Property: Budget state should reflect enforcement correctly
    violations_detected = any(
        sector_risks[sector] > enforcer.get_sector_limit(sector) - 0.001
        for sector in sector_risks
    )
    
    # If no violations, enforcement should not be active
    if not violations_detected:
        assert not budget_state.enforcement_active, \
            "Enforcement should not be active when no violations exist"


# Feature: institutional-validation-layers, Property 19: Risk Budget Logging
@settings(max_examples=50, deadline=None)
@given(portfolio=portfolio_with_sector_violations())
def test_property_19_risk_budget_logging(portfolio):
    """
    Property 19: Risk Budget Logging
    
    For any risk budget enforcement, log entries must be created in
    risk_budget.parquet with all required fields.
    
    Validates: Requirements 4.3, 4.4, 4.5
    """
    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup test environment
        risk_budget_file = os.path.join(tmpdir, 'risk_budget.parquet')
        risk_budget_state_file = os.path.join(tmpdir, 'risk_budget_state.parquet')
        
        # Create risk budget enforcer with test paths
        enforcer = RiskBudgetEnforcer()
        enforcer.risk_budget_file = risk_budget_file
        enforcer.risk_budget_state_file = risk_budget_state_file
        
        # Enforce risk budget
        adjusted_portfolio, budget_state = enforcer.enforce_risk_budget(portfolio)
        
        # Property: Log files must exist
        assert os.path.exists(risk_budget_file), "Risk budget log file should be created"
        assert os.path.exists(risk_budget_state_file), "Risk budget state file should be created"
        
        # Property: Sector log must contain required fields
        sector_log = pd.read_parquet(risk_budget_file)
        
        required_sector_fields = [
            'date', 'sector', 'max_risk', 'current_risk', 'utilization',
            'positions_count', 'total_weight', 'scale_factor', 'enforcement_triggered'
        ]
        
        for field in required_sector_fields:
            assert field in sector_log.columns, f"Required field '{field}' missing from sector log"
        
        # Property: State log must contain required fields
        state_log = pd.read_parquet(risk_budget_state_file)
        
        required_state_fields = [
            'date', 'total_sectors', 'sectors_over_limit', 'max_utilization',
            'avg_utilization', 'enforcement_active', 'total_scaling_applied'
        ]
        
        for field in required_state_fields:
            assert field in state_log.columns, f"Required field '{field}' missing from state log"
        
        # Property: Logs should have at least one entry
        assert len(sector_log) > 0, "Sector log should contain at least one entry"
        assert len(state_log) > 0, "State log should contain at least one entry"
        
        # Property: Utilization should be calculated correctly
        for _, row in sector_log.iterrows():
            if row['max_risk'] > 0:
                expected_util = row['current_risk'] / row['max_risk']
                assert abs(row['utilization'] - expected_util) < 0.001, \
                    f"Utilization calculation error: expected {expected_util:.3f}, got {row['utilization']:.3f}"


# Feature: institutional-validation-layers, Property 20: Proportional Scaling
@settings(max_examples=100, deadline=None)
@given(portfolio=portfolio_with_known_violations())
def test_property_20_proportional_scaling(portfolio):
    """
    Property 20: Proportional Scaling
    
    When a sector exceeds its limit, all positions in that sector should
    be scaled by the same factor: scale_factor = limit / current_risk
    
    Validates: Requirements 4.2
    """
    # Create risk budget enforcer
    enforcer = RiskBudgetEnforcer()
    
    # Calculate original sector risks
    original_sector_risks = enforcer.calculate_sector_risks(portfolio)
    
    # Enforce risk budget
    adjusted_portfolio, budget_state = enforcer.enforce_risk_budget(portfolio)
    
    # Check proportional scaling for each violating sector
    for sector, original_risk in original_sector_risks.items():
        limit = enforcer.get_sector_limit(sector)
        
        if original_risk > limit:
            expected_scale_factor = limit / original_risk
            
            # Get all positions in this sector
            sector_positions = [
                (ticker, pos) for ticker, pos in adjusted_portfolio.items()
                if pos.get('sector') == sector and pos.get('weight', 0) != 0
            ]
            
            # Property: All positions should have same scale factor
            for ticker, pos in sector_positions:
                if 'scale_factor' in pos:
                    actual_scale = pos['scale_factor']
                    assert abs(actual_scale - expected_scale_factor) < 0.001, \
                        f"Position {ticker} has wrong scale factor: " \
                        f"expected {expected_scale_factor:.3f}, got {actual_scale:.3f}"
                
                # Property: Weight should be scaled correctly
                if 'original_weight' in pos:
                    expected_weight = pos['original_weight'] * expected_scale_factor
                    actual_weight = pos['weight']
                    assert abs(actual_weight - expected_weight) < 0.001, \
                        f"Position {ticker} weight not scaled correctly: " \
                        f"expected {expected_weight:.3f}, got {actual_weight:.3f}"

# Import stress test engine
from src.validation.stress_test_engine import StressTestEngine, StressTestResult


@st.composite
def crisis_performance_data(draw, crisis_severity='moderate'):
    """
    Generate performance data for crisis testing
    
    Args:
        crisis_severity: 'mild', 'moderate', 'severe'
    
    Returns DataFrame with crisis-like returns
    """
    n_days = draw(st.integers(min_value=20, max_value=60))  # 20-60 day crisis
    
    # Generate dates
    start_date = datetime(2020, 2, 20)
    dates = [start_date + timedelta(days=i) for i in range(n_days)]
    
    # Crisis severity parameters
    severity_params = {
        'mild': {'nifty_decline': -0.15, 'northstar_decline': -0.10, 'volatility': 0.02},
        'moderate': {'nifty_decline': -0.25, 'northstar_decline': -0.18, 'volatility': 0.03},
        'severe': {'nifty_decline': -0.40, 'northstar_decline': -0.30, 'volatility': 0.04}
    }
    
    params = severity_params.get(crisis_severity, severity_params['moderate'])
    
    # Generate declining returns
    nifty_daily_decline = (1 + params['nifty_decline']) ** (1/n_days) - 1
    northstar_daily_decline = (1 + params['northstar_decline']) ** (1/n_days) - 1
    
    nifty_returns = []
    northstar_returns = []
    
    for i in range(n_days):
        # Add volatility
        nifty_vol = draw(st.floats(min_value=-params['volatility'], max_value=params['volatility']))
        northstar_vol = draw(st.floats(min_value=-params['volatility']*0.8, max_value=params['volatility']*0.8))
        
        nifty_ret = nifty_daily_decline + nifty_vol
        northstar_ret = northstar_daily_decline + northstar_vol
        
        nifty_returns.append(nifty_ret)
        northstar_returns.append(northstar_ret)
    
    df = pd.DataFrame({
        'date': dates,
        'northstar_return': northstar_returns,
        'nifty_return': nifty_returns,
        'net_return': northstar_returns,
        'exposure': [0.75] * n_days  # Reduced exposure during crisis
    })
    
    return df


# ============================================================================
# STRESS TEST ENGINE PROPERTY TESTS
# ============================================================================

# Feature: institutional-validation-layers, Property 21: Stress Test Execution
@settings(max_examples=50, deadline=None)
@given(crisis_data=crisis_performance_data())
def test_property_21_stress_test_execution(crisis_data):
    """
    Property 21: Stress Test Execution
    
    For any crisis period, the stress test should execute successfully
    and produce valid results with all required metrics.
    
    Validates: Requirements 5.1, 5.4, 5.5, 5.6
    """
    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup test environment
        stress_tests_file = os.path.join(tmpdir, 'stress_tests.parquet')
        
        # Create stress test engine with test paths
        stress_tester = StressTestEngine()
        stress_tester.stress_tests_file = stress_tests_file
        
        # Run COVID stress test with mock data
        result = stress_tester.run_covid_stress_test(crisis_data)
        
        # Property: Result should be valid StressTestResult
        assert isinstance(result, StressTestResult), "Result should be StressTestResult object"
        
        # Property: All required fields should be present
        required_fields = [
            'scenario', 'start_date', 'end_date', 'duration_days',
            'northstar_return', 'nifty_return', 'northstar_max_drawdown',
            'nifty_max_drawdown', 'northstar_advantage', 'drawdown_protection',
            'success', 'test_date'
        ]
        
        for field in required_fields:
            assert hasattr(result, field), f"Required field '{field}' missing from result"
        
        # Property: Duration should be reasonable (stress test uses fixed COVID period)
        assert 20 <= result.duration_days <= 40, \
            f"Duration should be reasonable for crisis period: got {result.duration_days}"
        
        # Property: Returns should be negative (crisis scenario)
        assert result.northstar_return < 0, \
            f"Northstar return should be negative in crisis: {result.northstar_return:.4f}"
        
        assert result.nifty_return < 0, \
            f"NIFTY return should be negative in crisis: {result.nifty_return:.4f}"
        
        # Property: Advantage should be difference
        expected_advantage = result.northstar_return - result.nifty_return
        assert abs(result.northstar_advantage - expected_advantage) < 0.001, \
            f"Advantage calculation error: expected {expected_advantage:.4f}, got {result.northstar_advantage:.4f}"


# Feature: institutional-validation-layers, Property 22: Drawdown Protection Validation
@settings(max_examples=50, deadline=None)
@given(crisis_data=crisis_performance_data(crisis_severity='severe'))
def test_property_22_drawdown_protection_validation(crisis_data):
    """
    Property 22: Drawdown Protection Validation
    
    For any severe crisis, Northstar should provide measurable drawdown
    protection compared to NIFTY (success = Northstar drawdown < NIFTY drawdown).
    
    Validates: Requirements 5.1, 5.4
    """
    # Create stress test engine
    stress_tester = StressTestEngine()
    
    # Run stress test
    result = stress_tester.run_covid_stress_test(crisis_data)
    
    # Property: Drawdowns should be negative (losses)
    assert result.northstar_max_drawdown <= 0, \
        f"Northstar drawdown should be negative: {result.northstar_max_drawdown:.4f}"
    
    assert result.nifty_max_drawdown <= 0, \
        f"NIFTY drawdown should be negative: {result.nifty_max_drawdown:.4f}"
    
    # Property: Drawdown protection ratio should be calculated correctly
    if result.nifty_max_drawdown != 0:
        expected_protection = result.northstar_max_drawdown / result.nifty_max_drawdown
        assert abs(result.drawdown_protection - expected_protection) < 0.001, \
            f"Drawdown protection calculation error: expected {expected_protection:.4f}, got {result.drawdown_protection:.4f}"
    
    # Property: Success should be determined correctly
    expected_success = result.northstar_max_drawdown > result.nifty_max_drawdown  # Less negative = better
    assert result.success == expected_success, \
        f"Success determination error: expected {expected_success}, got {result.success}"
    
    # Property: If Northstar provides protection, drawdown protection should be < 1.0
    if result.success:
        assert result.drawdown_protection < 1.0, \
            f"Successful protection should have ratio < 1.0: {result.drawdown_protection:.4f}"


# Feature: institutional-validation-layers, Property 23: Stress Test Logging
@settings(max_examples=30, deadline=None)
@given(crisis_data=crisis_performance_data())
def test_property_23_stress_test_logging(crisis_data):
    """
    Property 23: Stress Test Logging
    
    For any stress test execution, results must be logged to
    stress_tests.parquet with all required fields.
    
    Validates: Requirements 5.6
    """
    # Create temporary directory for test
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup test environment
        stress_tests_file = os.path.join(tmpdir, 'stress_tests.parquet')
        
        # Create stress test engine with test paths
        stress_tester = StressTestEngine()
        stress_tester.stress_tests_file = stress_tests_file
        
        # Run stress test
        result = stress_tester.run_covid_stress_test(crisis_data)
        
        # Log results
        stress_tester.log_stress_test_results([result])
        
        # Property: Log file must exist
        assert os.path.exists(stress_tests_file), "Stress test log file should be created"
        
        # Property: Log must contain required fields
        log_df = pd.read_parquet(stress_tests_file)
        
        required_fields = [
            'scenario', 'start_date', 'end_date', 'duration_days',
            'northstar_return', 'nifty_return', 'northstar_max_drawdown',
            'nifty_max_drawdown', 'northstar_advantage', 'drawdown_protection',
            'success', 'test_date'
        ]
        
        for field in required_fields:
            assert field in log_df.columns, f"Required field '{field}' missing from log"
        
        # Property: Log should have at least one entry
        assert len(log_df) > 0, "Log should contain at least one entry"
        
        # Property: Latest entry should match result
        latest = log_df.iloc[-1]
        assert latest['scenario'] == result.scenario
        assert abs(latest['northstar_return'] - result.northstar_return) < 0.001
        assert abs(latest['nifty_return'] - result.nifty_return) < 0.001
        assert latest['success'] == result.success


# Feature: institutional-validation-layers, Property 24: Crisis Scenario Consistency
@settings(max_examples=50, deadline=None)
@given(crisis_data=crisis_performance_data())
def test_property_24_crisis_scenario_consistency(crisis_data):
    """
    Property 24: Crisis Scenario Consistency
    
    For any crisis data, the stress test should produce consistent
    results when run multiple times with the same input.
    
    Validates: Requirements 5.5
    """
    # Create stress test engine
    stress_tester = StressTestEngine()
    
    # Run stress test twice with same data
    result1 = stress_tester.run_covid_stress_test(crisis_data)
    result2 = stress_tester.run_covid_stress_test(crisis_data)
    
    # Property: Results should be identical (except test_date)
    assert result1.scenario == result2.scenario
    assert result1.start_date == result2.start_date
    assert result1.end_date == result2.end_date
    assert result1.duration_days == result2.duration_days
    
    # Property: Calculated metrics should be identical
    assert abs(result1.northstar_return - result2.northstar_return) < 0.0001
    assert abs(result1.nifty_return - result2.nifty_return) < 0.0001
    assert abs(result1.northstar_max_drawdown - result2.northstar_max_drawdown) < 0.0001
    assert abs(result1.nifty_max_drawdown - result2.nifty_max_drawdown) < 0.0001
    assert abs(result1.northstar_advantage - result2.northstar_advantage) < 0.0001
    assert abs(result1.drawdown_protection - result2.drawdown_protection) < 0.0001
    assert result1.success == result2.success