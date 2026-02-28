"""
Property-Based Tests for State File Manager

Tests universal properties that must hold for all state file operations.
Uses Hypothesis for property-based testing with 100+ iterations per property.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, HealthCheck
from pathlib import Path
import tempfile
import shutil
from contextlib import contextmanager

from src.cohesion.state_file_manager import StateFileManager, ValidationResult


# Test fixtures

@pytest.fixture
def temp_state_manager(tmp_path, monkeypatch):
    """Create a StateFileManager with temporary paths"""
    # Monkey patch the class paths to use temp directory
    monkeypatch.setattr(
        StateFileManager,
        'MARKET_STATE_PATH',
        tmp_path / 'market_state.parquet'
    )
    monkeypatch.setattr(
        StateFileManager,
        'PORTFOLIO_WEIGHTS_PATH',
        tmp_path / 'portfolio_weights.parquet'
    )
    monkeypatch.setattr(
        StateFileManager,
        'RISK_STATE_PATH',
        tmp_path / 'risk_state.parquet'
    )
    monkeypatch.setattr(
        StateFileManager,
        'EXPOSURE_HISTORY_PATH',
        tmp_path / 'exposure_history.parquet'
    )
    monkeypatch.setattr(
        StateFileManager,
        'PORTFOLIO_ANALYTICS_PATH',
        tmp_path / 'portfolio_analytics.json'
    )
    monkeypatch.setattr(
        StateFileManager,
        'BACKUP_DIR',
        tmp_path / 'backups'
    )
    
    manager = StateFileManager()
    return manager


@contextmanager
def create_temp_state_manager():
    """Context manager to create a temporary StateFileManager"""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create a custom manager with temp paths
        manager = StateFileManager()
        manager.MARKET_STATE_PATH = tmp_path / 'market_state.parquet'
        manager.PORTFOLIO_WEIGHTS_PATH = tmp_path / 'portfolio_weights.parquet'
        manager.RISK_STATE_PATH = tmp_path / 'risk_state.parquet'
        manager.EXPOSURE_HISTORY_PATH = tmp_path / 'exposure_history.parquet'
        manager.PORTFOLIO_ANALYTICS_PATH = tmp_path / 'portfolio_analytics.json'
        manager.BACKUP_DIR = tmp_path / 'backups'
        manager.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        
        yield manager


# Hypothesis strategies for generating test data

@st.composite
def market_state_dataframe(draw, min_rows=1, max_rows=100):
    """Generate valid market state DataFrame"""
    n_rows = draw(st.integers(min_value=min_rows, max_value=max_rows))
    
    base_date = datetime(2024, 1, 1)
    dates = [base_date + timedelta(days=i) for i in range(n_rows)]
    
    regimes = draw(st.lists(
        st.sampled_from(['early-expansion', 'late-expansion', 'early-contraction', 'late-contraction']),
        min_size=n_rows,
        max_size=n_rows
    ))
    
    risk_on = draw(st.lists(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=n_rows,
        max_size=n_rows
    ))
    
    allowed_exposure = draw(st.lists(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=n_rows,
        max_size=n_rows
    ))
    
    stress_score = draw(st.lists(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=n_rows,
        max_size=n_rows
    ))
    
    return pd.DataFrame({
        'date': dates,
        'regime': regimes,
        'risk_on': risk_on,
        'allowed_exposure': allowed_exposure,
        'stress_score': stress_score
    })


@st.composite
def portfolio_weights_dataframe(draw, min_rows=1, max_rows=50):
    """Generate valid portfolio weights DataFrame"""
    n_rows = draw(st.integers(min_value=min_rows, max_value=max_rows))
    
    base_date = datetime(2024, 1, 1)
    date = base_date
    
    symbols = [f"STOCK{i}" for i in range(n_rows)]
    
    weights = draw(st.lists(
        st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=n_rows,
        max_size=n_rows
    ))
    
    exposures = draw(st.lists(
        st.floats(min_value=0.0, max_value=0.2, allow_nan=False, allow_infinity=False),
        min_size=n_rows,
        max_size=n_rows
    ))
    
    return pd.DataFrame({
        'date': [date] * n_rows,
        'symbol': symbols,
        'weight': weights,
        'exposure': exposures
    })


@st.composite
def risk_state_dataframe(draw, min_rows=1, max_rows=100):
    """Generate valid risk state DataFrame"""
    n_rows = draw(st.integers(min_value=min_rows, max_value=max_rows))
    
    base_date = datetime(2024, 1, 1)
    dates = [base_date + timedelta(days=i) for i in range(n_rows)]
    
    volatility = draw(st.lists(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=n_rows,
        max_size=n_rows
    ))
    
    correlation = draw(st.lists(
        st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=n_rows,
        max_size=n_rows
    ))
    
    var = draw(st.lists(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_size=n_rows,
        max_size=n_rows
    ))
    
    return pd.DataFrame({
        'date': dates,
        'volatility': volatility,
        'correlation': correlation,
        'var': var
    })


# Property Tests

@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(state_df=market_state_dataframe())
def test_property_atomic_write_roundtrip_market_state(state_df):
    """
    Property 8: Atomic Write Round-Trip
    
    For any state data written to market_state.parquet,
    immediately reading that file must return data equal to what was written.
    
    Validates: Requirements 10.1, 10.2, 10.5
    Feature: system-integrity-repair, Property 8: Atomic Write Round-Trip
    """
    with create_temp_state_manager() as manager:
        # Write the data
        manager.write_market_state(state_df)
        
        # Immediately read it back
        read_df = manager.read_market_state()
        
        # Verify exact equality
        pd.testing.assert_frame_equal(state_df, read_df, check_dtype=True)
        
        # Verify file exists at canonical location
        assert manager.MARKET_STATE_PATH.exists()
        
        # Verify no temp files left behind
        temp_files = list(manager.MARKET_STATE_PATH.parent.glob('*.tmp'))
        assert len(temp_files) == 0, f"Temp files left behind: {temp_files}"


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(weights_df=portfolio_weights_dataframe())
def test_property_atomic_write_roundtrip_portfolio_weights(weights_df):
    """
    Property 8: Atomic Write Round-Trip (Portfolio Weights)
    
    For any portfolio weights written to portfolio_weights.parquet,
    immediately reading that file must return data equal to what was written.
    
    Validates: Requirements 10.1, 10.2, 10.5
    Feature: system-integrity-repair, Property 8: Atomic Write Round-Trip
    """
    with create_temp_state_manager() as manager:
        # Write the data
        manager.write_portfolio_weights(weights_df)
        
        # Immediately read it back
        read_df = manager.read_portfolio_weights()
        
        # Verify exact equality
        pd.testing.assert_frame_equal(weights_df, read_df, check_dtype=True)
        
        # Verify file exists at canonical location
        assert manager.PORTFOLIO_WEIGHTS_PATH.exists()
        
        # Verify no temp files left behind
        temp_files = list(manager.PORTFOLIO_WEIGHTS_PATH.parent.glob('*.tmp'))
        assert len(temp_files) == 0


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(risk_df=risk_state_dataframe())
def test_property_atomic_write_roundtrip_risk_state(risk_df):
    """
    Property 8: Atomic Write Round-Trip (Risk State)
    
    For any risk state written to risk_state.parquet,
    immediately reading that file must return data equal to what was written.
    
    Validates: Requirements 10.1, 10.2, 10.5
    Feature: system-integrity-repair, Property 8: Atomic Write Round-Trip
    """
    with create_temp_state_manager() as manager:
        # Write the data
        manager.write_risk_state(risk_df)
        
        # Immediately read it back
        read_df = manager.read_risk_state()
        
        # Verify exact equality
        pd.testing.assert_frame_equal(risk_df, read_df, check_dtype=True)
        
        # Verify file exists at canonical location
        assert manager.RISK_STATE_PATH.exists()
        
        # Verify no temp files left behind
        temp_files = list(manager.RISK_STATE_PATH.parent.glob('*.tmp'))
        assert len(temp_files) == 0


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    analytics=st.fixed_dictionaries({
        'as_of_date': st.just('2024-01-01'),
        'portfolio_metrics': st.fixed_dictionaries({
            'total_return': st.floats(min_value=-1.0, max_value=5.0, allow_nan=False),
            'sharpe_ratio': st.floats(min_value=-3.0, max_value=5.0, allow_nan=False),
            'max_drawdown': st.floats(min_value=-1.0, max_value=0.0, allow_nan=False),
        })
    })
)
def test_property_atomic_write_roundtrip_portfolio_analytics(analytics):
    """
    Property 8: Atomic Write Round-Trip (Portfolio Analytics)
    
    For any portfolio analytics written to portfolio_analytics.json,
    immediately reading that file must return data equal to what was written.
    
    Validates: Requirements 10.1, 10.2, 10.5
    Feature: system-integrity-repair, Property 8: Atomic Write Round-Trip
    """
    with create_temp_state_manager() as manager:
        # Write the data
        manager.write_portfolio_analytics(analytics)
        
        # Immediately read it back
        read_analytics = manager.read_portfolio_analytics()
        
        # Verify exact equality
        assert analytics == read_analytics
        
        # Verify file exists at canonical location
        assert manager.PORTFOLIO_ANALYTICS_PATH.exists()
        
        # Verify no temp files left behind
        temp_files = list(manager.PORTFOLIO_ANALYTICS_PATH.parent.glob('*.tmp'))
        assert len(temp_files) == 0


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    state_df1=market_state_dataframe(min_rows=5, max_rows=10),
    state_df2=market_state_dataframe(min_rows=5, max_rows=10)
)
def test_property_atomic_write_preserves_previous_on_failure(state_df1, state_df2):
    """
    Property: Write Failure Preservation
    
    If a write fails, the previous state must remain intact.
    
    Validates: Requirements 10.3
    Feature: system-integrity-repair, Property 8 Extension
    """
    with create_temp_state_manager() as manager:
        # Write initial state
        manager.write_market_state(state_df1)
        
        # Verify initial state
        read_df1 = manager.read_market_state()
        pd.testing.assert_frame_equal(state_df1, read_df1)
        
        # Attempt to write invalid state (wrong schema)
        invalid_df = pd.DataFrame({'wrong_column': [1, 2, 3]})
        
        with pytest.raises(ValueError):
            manager.write_market_state(invalid_df)
        
        # Verify original state is still intact
        read_df_after_failure = manager.read_market_state()
        pd.testing.assert_frame_equal(state_df1, read_df_after_failure)


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(state_df=market_state_dataframe())
def test_property_backup_created_on_overwrite(state_df):
    """
    Property: Backup Creation
    
    When overwriting an existing file, a backup must be created.
    
    Validates: Requirements 10.1
    Feature: system-integrity-repair, Property 8 Extension
    """
    with create_temp_state_manager() as manager:
        # Write initial state
        manager.write_market_state(state_df)
        
        # Write again (should create backup)
        manager.write_market_state(state_df)
        
        # Verify backup was created
        backups = list(manager.BACKUP_DIR.glob('market_state_*'))
        assert len(backups) >= 1, "Backup should have been created"


# Unit tests for edge cases

def test_read_nonexistent_file_raises_error(temp_state_manager):
    """Test that reading nonexistent file raises FileNotFoundError"""
    manager = temp_state_manager
    
    with pytest.raises(FileNotFoundError):
        manager.read_market_state()


def test_schema_validation_detects_missing_columns(temp_state_manager):
    """Test that schema validation detects missing columns"""
    manager = temp_state_manager
    
    # Create DataFrame with missing columns
    invalid_df = pd.DataFrame({
        'date': [datetime.now()],
        'regime': ['expansion']
        # Missing: risk_on, allowed_exposure, stress_score
    })
    
    with pytest.raises(ValueError, match="Missing columns"):
        manager.write_market_state(invalid_df)


def test_schema_validation_detects_wrong_types(temp_state_manager):
    """Test that schema validation detects wrong column types"""
    manager = temp_state_manager
    
    # Create DataFrame with wrong types
    invalid_df = pd.DataFrame({
        'date': [datetime.now()],
        'regime': ['expansion'],
        'risk_on': ['not_a_float'],  # Should be float
        'allowed_exposure': [0.5],
        'stress_score': [0.3]
    })
    
    with pytest.raises(ValueError, match="has type"):
        manager.write_market_state(invalid_df)


def test_exposure_history_append_creates_file_if_missing(temp_state_manager):
    """Test that appending to exposure history creates file if it doesn't exist"""
    manager = temp_state_manager
    
    # Create a single row to append
    history_row = pd.DataFrame({
        'date': [datetime.now()],
        'allowed_exposure': [0.5],
        'actual_exposure': [0.45],
        'risk_scaled_exposure': [0.6],
        'regime': ['expansion'],
        'stress_score': [0.3]
    })
    
    # Append (should create file)
    manager.append_exposure_history(history_row)
    
    # Verify file was created and contains the row
    history = manager.read_exposure_history()
    assert len(history) == 1
    pd.testing.assert_frame_equal(history, history_row)


def test_validate_state_consistency_detects_date_mismatch(temp_state_manager):
    """Test that consistency validation detects date mismatches"""
    manager = temp_state_manager
    
    # Write market state with one date
    market_df = pd.DataFrame({
        'date': [datetime(2024, 1, 1)],
        'regime': ['expansion'],
        'risk_on': [0.7],
        'allowed_exposure': [0.5],
        'stress_score': [0.3]
    })
    manager.write_market_state(market_df)
    
    # Write portfolio with different date
    portfolio_df = pd.DataFrame({
        'date': [datetime(2024, 1, 2)],  # Different date
        'symbol': ['STOCK1'],
        'weight': [0.5],
        'exposure': [0.5]
    })
    manager.write_portfolio_weights(portfolio_df)
    
    # Write risk state with matching date
    risk_df = pd.DataFrame({
        'date': [datetime(2024, 1, 1)],
        'volatility': [0.15],
        'correlation': [0.5],
        'var': [0.02]
    })
    manager.write_risk_state(risk_df)
    
    # Validate consistency
    result = manager.validate_state_consistency()
    
    # Should detect date mismatch
    assert not result.is_valid
    assert any('Date mismatch' in error for error in result.errors)


def test_validate_state_consistency_detects_exposure_mismatch(temp_state_manager):
    """Test that consistency validation detects exposure mismatches"""
    manager = temp_state_manager
    
    date = datetime(2024, 1, 1)
    
    # Write market state with allowed_exposure = 0.5
    market_df = pd.DataFrame({
        'date': [date],
        'regime': ['expansion'],
        'risk_on': [0.7],
        'allowed_exposure': [0.5],
        'stress_score': [0.3]
    })
    manager.write_market_state(market_df)
    
    # Write portfolio with actual_exposure = 0.9 (significant mismatch)
    portfolio_df = pd.DataFrame({
        'date': [date, date],
        'symbol': ['STOCK1', 'STOCK2'],
        'weight': [0.5, 0.4],
        'exposure': [0.5, 0.4]  # Sum = 0.9
    })
    manager.write_portfolio_weights(portfolio_df)
    
    # Write risk state
    risk_df = pd.DataFrame({
        'date': [date],
        'volatility': [0.15],
        'correlation': [0.5],
        'var': [0.02]
    })
    manager.write_risk_state(risk_df)
    
    # Validate consistency
    result = manager.validate_state_consistency()
    
    # Should detect exposure mismatch as warning
    assert any('Exposure mismatch' in warning for warning in result.warnings)
