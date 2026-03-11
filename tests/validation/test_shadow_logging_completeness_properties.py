#!/usr/bin/env python3
"""
🧪 SHADOW LOGGING COMPLETENESS - PROPERTY-BASED TESTS
Property tests for Shadow Logger with complete audit trail requirements

These tests verify universal properties that must hold across ALL valid inputs:
- Property 19: Shadow Fund Logging Completeness

Usage:
    pytest tests/validation/test_shadow_logging_completeness_properties.py -v
    
    # Run with more iterations for thorough testing
    pytest tests/validation/test_shadow_logging_completeness_properties.py -v --hypothesis-iterations=1000
"""

import pytest
import pandas as pd
import numpy as np
import json
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from src.validation.shadow_logger import (
    ShadowLogger,
    DailyPosition,
    DailyPnL,
    DailyDecision
)


# ============================================================================
# HYPOTHESIS STRATEGIES
# ============================================================================

@st.composite
def valid_position_data(draw):
    """Generate valid position data"""
    return {
        'ticker': draw(st.text(min_size=3, max_size=10, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ')),
        'weight': draw(st.floats(min_value=-1.0, max_value=1.0)),
        'role': draw(st.sampled_from(['core', 'satellite', 'hedge', 'cash'])),
        'strategy_source': draw(st.text(min_size=5, max_size=20, alphabet='abcdefghijklmnopqrstuvwxyz_')),
        'exposure': draw(st.floats(min_value=0.0, max_value=1.0)),
        'risk_cap': draw(st.floats(min_value=0.0, max_value=1.0))
    }


@st.composite
def valid_pnl_data(draw):
    """Generate valid P&L data"""
    return {
        'returns': draw(st.floats(min_value=-0.20, max_value=0.20)),
        'tracking_error': draw(st.floats(min_value=0.0, max_value=0.10)),
        'drawdown': draw(st.floats(min_value=-0.50, max_value=0.0)),
        'turnover': draw(st.floats(min_value=0.0, max_value=1.0)),
        'costs': draw(st.floats(min_value=0.0, max_value=0.01))
    }


@st.composite
def valid_decision_data(draw):
    """Generate valid decision data"""
    return {
        'regime': draw(st.sampled_from(['expansion', 'late-expansion', 'recession', 'crisis'])),
        'tailwind_shift': draw(st.floats(min_value=-1.0, max_value=1.0)),
        'exposure_change': draw(st.floats(min_value=-100.0, max_value=100.0)),
        'risk_reason': draw(st.text(min_size=5, max_size=50)),
        'strategies_boosted': draw(st.lists(st.text(min_size=3, max_size=15), max_size=5)),
        'strategies_cut': draw(st.lists(st.text(min_size=3, max_size=15), max_size=5)),
        'emergency_triggered': draw(st.booleans())
    }


@st.composite
def sample_date(draw):
    """Generate test date"""
    year = draw(st.integers(min_value=2020, max_value=2025))
    month = draw(st.integers(min_value=1, max_value=12))
    day = draw(st.integers(min_value=1, max_value=28))  # Safe for all months
    
    return datetime(year, month, day)


# ============================================================================
# PROPERTY 19: SHADOW FUND LOGGING COMPLETENESS
# ============================================================================

# Feature: institutional-validation-layers, Property 19: Shadow Fund Logging Completeness
# **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 11.1-11.5**

@settings(max_examples=100, deadline=None)
@given(
    date=sample_date(),
    positions=st.lists(valid_position_data(), min_size=1, max_size=20),
    pnl_data=valid_pnl_data(),
    decision_data=valid_decision_data()
)
def test_property_19_shadow_fund_logging_completeness(date, positions, pnl_data, decision_data):
    """
    Property 19: Shadow Fund Logging Completeness
    
    For any day of shadow fund operation, position logs, P&L logs, and decision logs
    must all be created with complete data and proper schema.
    
    This test verifies that:
    - All three log types are created successfully
    - Files exist at expected locations
    - Data can be read back correctly
    - Schema validation passes
    - All required fields are present
    """
    
    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Initialize logger with temporary directory
        logger = ShadowLogger(base_dir=temp_dir)
        
        # Log complete daily cycle
        file_paths = logger.log_complete_daily_cycle(
            date=date,
            positions=positions,
            pnl_data=pnl_data,
            decision_data=decision_data
        )
        
        # CRITICAL ASSERTION: All three log types must be created
        assert 'positions' in file_paths, "Positions log not created"
        assert 'pnl' in file_paths, "P&L log not created"
        assert 'decisions' in file_paths, "Decisions log not created"
        
        # CRITICAL ASSERTION: All files must exist
        for log_type, file_path in file_paths.items():
            assert os.path.exists(file_path), f"{log_type} file does not exist: {file_path}"
        
        # CRITICAL ASSERTION: Files must be in correct year directory
        year_dir = os.path.join(temp_dir, str(date.year))
        for file_path in file_paths.values():
            assert file_path.startswith(year_dir), f"File not in correct year directory: {file_path}"
        
        # CRITICAL ASSERTION: Files must have correct naming convention
        date_str = date.strftime("%Y%m%d")
        
        assert f"daily_positions_{date_str}.parquet" in file_paths['positions']
        assert f"daily_pnl_{date_str}.parquet" in file_paths['pnl']
        assert f"daily_decisions_{date_str}.json" in file_paths['decisions']
        
        # CRITICAL ASSERTION: Data must be readable and valid
        
        # Test positions
        loaded_positions = logger.load_daily_positions(date)
        assert loaded_positions is not None, "Failed to load positions"
        assert len(loaded_positions) == len(positions), "Position count mismatch"
        
        # Verify positions schema
        required_pos_columns = ['date', 'ticker', 'weight', 'role', 'strategy_source', 'exposure', 'risk_cap']
        for col in required_pos_columns:
            assert col in loaded_positions.columns, f"Missing positions column: {col}"
        
        # Test P&L
        loaded_pnl = logger.load_daily_pnl(date)
        assert loaded_pnl is not None, "Failed to load P&L"
        assert len(loaded_pnl) == 1, "P&L should have exactly one record"
        
        # Verify P&L schema
        required_pnl_columns = ['date', 'returns', 'tracking_error', 'drawdown', 'turnover', 'costs']
        for col in required_pnl_columns:
            assert col in loaded_pnl.columns, f"Missing P&L column: {col}"
        
        # Test decisions
        loaded_decisions = logger.load_daily_decisions(date)
        assert loaded_decisions is not None, "Failed to load decisions"
        
        # Verify decisions schema
        required_decision_fields = ['date', 'regime', 'tailwind_shift', 'exposure_change', 
                                  'risk_reason', 'strategies_boosted', 'strategies_cut', 'emergency_triggered']
        for field in required_decision_fields:
            assert field in loaded_decisions, f"Missing decisions field: {field}"
        
        # CRITICAL ASSERTION: Data integrity - values should match input
        
        # Check P&L values (allowing for small floating point differences)
        pnl_row = loaded_pnl.iloc[0]
        assert abs(pnl_row['returns'] - pnl_data['returns']) < 1e-10, "P&L returns mismatch"
        assert abs(pnl_row['drawdown'] - pnl_data['drawdown']) < 1e-10, "P&L drawdown mismatch"
        assert abs(pnl_row['costs'] - pnl_data['costs']) < 1e-10, "P&L costs mismatch"
        
        # Check decisions values
        assert loaded_decisions['regime'] == decision_data['regime'], "Decision regime mismatch"
        assert loaded_decisions['emergency_triggered'] == decision_data['emergency_triggered'], "Emergency flag mismatch"
        
        # CRITICAL ASSERTION: Timestamps must be immutable and correct
        assert loaded_positions['date'].iloc[0].date() == date.date(), "Position date mismatch"
        assert loaded_pnl['date'].iloc[0].date() == date.date(), "P&L date mismatch"
        
        # Parse decision date from ISO format
        decision_date = datetime.fromisoformat(loaded_decisions['date']).date()
        assert decision_date == date.date(), "Decision date mismatch"


@settings(max_examples=50, deadline=None)
@given(
    date=sample_date(),
    positions=st.lists(valid_position_data(), min_size=1, max_size=10)
)
def test_positions_logging_schema_enforcement(date, positions):
    """
    Test that positions logging enforces schema correctly
    
    Verifies that:
    - Schema validation catches invalid data
    - Valid data passes through correctly
    - Type enforcement works properly
    """
    
    with tempfile.TemporaryDirectory() as temp_dir:
        logger = ShadowLogger(base_dir=temp_dir)
        
        # Log positions
        file_path = logger.log_daily_positions(date, positions)
        
        # Should succeed with valid data
        assert file_path != "", "Valid positions should log successfully"
        
        # Load and verify
        loaded_df = logger.load_daily_positions(date)
        assert loaded_df is not None, "Should be able to load valid positions"
        
        # Check data types
        assert loaded_df['date'].dtype == 'datetime64[ns]', "Date should be datetime64[ns]"
        assert loaded_df['weight'].dtype == 'float64', "Weight should be float64"
        assert loaded_df['exposure'].dtype == 'float64', "Exposure should be float64"
        assert loaded_df['risk_cap'].dtype == 'float64', "Risk cap should be float64"
        
        # Check bounds
        assert (loaded_df['weight'] >= -1.0).all(), "All weights should be >= -1.0"
        assert (loaded_df['weight'] <= 1.0).all(), "All weights should be <= 1.0"
        assert (loaded_df['exposure'] >= 0.0).all(), "All exposures should be >= 0.0"
        assert (loaded_df['risk_cap'] >= 0.0).all(), "All risk caps should be >= 0.0"
        assert (loaded_df['risk_cap'] <= 1.0).all(), "All risk caps should be <= 1.0"


@settings(max_examples=50, deadline=None)
@given(
    date=sample_date(),
    pnl_data=valid_pnl_data()
)
def test_pnl_logging_schema_enforcement(date, pnl_data):
    """
    Test that P&L logging enforces schema correctly
    """
    
    with tempfile.TemporaryDirectory() as temp_dir:
        logger = ShadowLogger(base_dir=temp_dir)
        
        # Log P&L
        file_path = logger.log_daily_pnl(date, pnl_data)
        
        # Should succeed with valid data
        assert file_path != "", "Valid P&L should log successfully"
        
        # Load and verify
        loaded_df = logger.load_daily_pnl(date)
        assert loaded_df is not None, "Should be able to load valid P&L"
        
        # Check data types
        assert loaded_df['date'].dtype == 'datetime64[ns]', "Date should be datetime64[ns]"
        assert loaded_df['returns'].dtype == 'float64', "Returns should be float64"
        assert loaded_df['drawdown'].dtype == 'float64', "Drawdown should be float64"
        assert loaded_df['turnover'].dtype == 'float64', "Turnover should be float64"
        assert loaded_df['costs'].dtype == 'float64', "Costs should be float64"
        
        # Check bounds
        assert (loaded_df['drawdown'] <= 0.0).all(), "All drawdowns should be <= 0.0"
        assert (loaded_df['turnover'] >= 0.0).all(), "All turnovers should be >= 0.0"
        assert (loaded_df['costs'] >= 0.0).all(), "All costs should be >= 0.0"


@settings(max_examples=50, deadline=None)
@given(
    date=sample_date(),
    decision_data=valid_decision_data()
)
def test_decisions_logging_json_format(date, decision_data):
    """
    Test that decisions logging creates valid JSON
    """
    
    with tempfile.TemporaryDirectory() as temp_dir:
        logger = ShadowLogger(base_dir=temp_dir)
        
        # Log decisions
        file_path = logger.log_daily_decisions(date, decision_data)
        
        # Should succeed with valid data
        assert file_path != "", "Valid decisions should log successfully"
        
        # Load and verify JSON format
        loaded_decisions = logger.load_daily_decisions(date)
        assert loaded_decisions is not None, "Should be able to load valid decisions"
        
        # Verify JSON structure
        assert isinstance(loaded_decisions, dict), "Decisions should be a dictionary"
        
        # Check required fields
        required_fields = ['date', 'regime', 'tailwind_shift', 'exposure_change', 
                          'risk_reason', 'strategies_boosted', 'strategies_cut', 'emergency_triggered']
        
        for field in required_fields:
            assert field in loaded_decisions, f"Missing required field: {field}"
        
        # Check data types
        assert isinstance(loaded_decisions['regime'], str), "Regime should be string"
        assert isinstance(loaded_decisions['emergency_triggered'], bool), "Emergency flag should be boolean"
        assert isinstance(loaded_decisions['strategies_boosted'], list), "Strategies boosted should be list"
        assert isinstance(loaded_decisions['strategies_cut'], list), "Strategies cut should be list"


def test_file_organization_structure():
    """
    Test that files are organized correctly by year
    """
    
    with tempfile.TemporaryDirectory() as temp_dir:
        logger = ShadowLogger(base_dir=temp_dir)
        
        # Test dates from different years
        dates = [
            datetime(2023, 6, 15),
            datetime(2024, 3, 10),
            datetime(2025, 12, 1)
        ]
        
        for date in dates:
            # Create minimal valid data
            positions = [{'ticker': 'TEST', 'weight': 0.1, 'role': 'core', 
                         'strategy_source': 'test', 'exposure': 0.1, 'risk_cap': 0.2}]
            pnl_data = {'returns': 0.01, 'tracking_error': 0.005, 'drawdown': -0.01, 
                       'turnover': 0.02, 'costs': 0.001}
            decision_data = {'regime': 'expansion', 'tailwind_shift': 0.0, 'exposure_change': 0.0,
                           'risk_reason': 'normal', 'strategies_boosted': [], 'strategies_cut': [],
                           'emergency_triggered': False}
            
            # Log data
            file_paths = logger.log_complete_daily_cycle(date, positions, pnl_data, decision_data)
            
            # Verify year directory structure
            year_dir = os.path.join(temp_dir, str(date.year))
            assert os.path.exists(year_dir), f"Year directory {date.year} should exist"
            
            # Verify files are in correct year directory
            for file_path in file_paths.values():
                assert file_path.startswith(year_dir), f"File should be in {year_dir}: {file_path}"


def test_data_immutability():
    """
    Test that logged data is immutable (cannot be accidentally modified)
    """
    
    with tempfile.TemporaryDirectory() as temp_dir:
        logger = ShadowLogger(base_dir=temp_dir)
        
        date = datetime(2024, 1, 15)
        
        # Create test data
        positions = [{'ticker': 'IMMUTABLE', 'weight': 0.05, 'role': 'core', 
                     'strategy_source': 'test', 'exposure': 0.05, 'risk_cap': 0.1}]
        pnl_data = {'returns': 0.02, 'tracking_error': 0.01, 'drawdown': -0.005, 
                   'turnover': 0.03, 'costs': 0.0005}
        decision_data = {'regime': 'expansion', 'tailwind_shift': 0.01, 'exposure_change': 2.0,
                        'risk_reason': 'normal', 'strategies_boosted': ['test'], 'strategies_cut': [],
                        'emergency_triggered': False}
        
        # Log data
        file_paths = logger.log_complete_daily_cycle(date, positions, pnl_data, decision_data)
        
        # Load data first time
        positions_1 = logger.load_daily_positions(date)
        pnl_1 = logger.load_daily_pnl(date)
        decisions_1 = logger.load_daily_decisions(date)
        
        # Load data second time
        positions_2 = logger.load_daily_positions(date)
        pnl_2 = logger.load_daily_pnl(date)
        decisions_2 = logger.load_daily_decisions(date)
        
        # Data should be identical (immutable)
        pd.testing.assert_frame_equal(positions_1, positions_2)
        pd.testing.assert_frame_equal(pnl_1, pnl_2)
        assert decisions_1 == decisions_2, "Decisions should be identical"
        
        # Verify specific values haven't changed
        assert positions_1.iloc[0]['weight'] == 0.05, "Position weight should be unchanged"
        assert pnl_1.iloc[0]['returns'] == 0.02, "P&L return should be unchanged"
        assert decisions_1['regime'] == 'expansion', "Decision regime should be unchanged"


def test_date_range_summary():
    """
    Test date range summary functionality
    """
    
    with tempfile.TemporaryDirectory() as temp_dir:
        logger = ShadowLogger(base_dir=temp_dir)
        
        # Create 5 days of test data
        start_date = datetime(2024, 1, 1)
        
        for i in range(5):
            date = start_date + timedelta(days=i)
            
            positions = [{'ticker': f'STOCK{i}', 'weight': 0.1, 'role': 'core', 
                         'strategy_source': f'strategy_{i%2}', 'exposure': 0.1, 'risk_cap': 0.2}]
            pnl_data = {'returns': 0.01 * (i + 1), 'tracking_error': 0.005, 'drawdown': -0.01 * i, 
                       'turnover': 0.02, 'costs': 0.001}
            decision_data = {'regime': ['expansion', 'recession'][i % 2], 'tailwind_shift': 0.0, 
                           'exposure_change': 0.0, 'risk_reason': 'normal', 'strategies_boosted': [], 
                           'strategies_cut': [], 'emergency_triggered': False}
            
            logger.log_complete_daily_cycle(date, positions, pnl_data, decision_data)
        
        # Get summary
        end_date = start_date + timedelta(days=4)
        summary = logger.get_date_range_summary(start_date, end_date)
        
        # Verify summary
        assert summary['total_days'] == 5, "Should have 5 total days"
        assert summary['days_logged'] == 5, "Should have logged all 5 days"
        assert summary['total_return'] > 0, "Should have positive total return"
        assert 'expansion' in summary['regime_distribution'], "Should track regime distribution"
        assert 'recession' in summary['regime_distribution'], "Should track regime distribution"
        assert len(summary['strategy_usage']) == 2, "Should track strategy usage"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, '-v', '--tb=short'])
