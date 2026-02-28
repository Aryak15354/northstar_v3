"""
Property-Based Tests for State Validator

Tests validation logic for state files on system startup.
"""

import pytest
from hypothesis import given, strategies as st, settings
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import shutil

from src.cohesion.state_validator import StateValidator, validate_state_on_startup


class TestStateValidatorProperties:
    """Property-based tests for state validator"""
    
    def setup_method(self):
        """Create temporary directory for each test"""
        self.temp_dir = tempfile.mkdtemp()
        self.state_dir = Path(self.temp_dir) / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)
    
    def teardown_method(self):
        """Clean up temporary directory"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    @settings(max_examples=100, deadline=None)
    @given(
        num_rows=st.integers(min_value=1, max_value=100),
        allowed_exposure=st.floats(min_value=0.0, max_value=1.0),
        risk_on=st.floats(min_value=0.0, max_value=1.0),
        stress_score=st.floats(min_value=0.0, max_value=1.0)
    )
    def test_property_valid_market_state_passes_validation(
        self, num_rows, allowed_exposure, risk_on, stress_score
    ):
        """
        Property: Valid market state files pass validation
        
        For any valid market state data, validation should succeed.
        """
        # Create valid market state
        dates = pd.date_range(end=datetime.now(), periods=num_rows, freq='D')
        market_df = pd.DataFrame({
            'date': dates,
            'regime': ['early-expansion'] * num_rows,
            'risk_on': [risk_on] * num_rows,
            'allowed_exposure': [allowed_exposure] * num_rows,
            'stress_score': [stress_score] * num_rows
        })
        
        market_df.to_parquet(self.state_dir / 'market_state.parquet', index=False)
        
        # Create valid portfolio weights
        portfolio_df = pd.DataFrame({
            'date': [dates[-1]],
            'symbol': ['TEST'],
            'weight': [0.1],
            'exposure': [0.1]
        })
        portfolio_df.to_parquet(self.state_dir / 'portfolio_weights.parquet', index=False)
        
        # Validate
        validator = StateValidator(str(self.state_dir))
        result = validator.validate_all()
        
        # Should pass
        assert result.is_valid, f"Valid state failed validation: {result.errors}"
        assert len(result.errors) == 0
        assert 'market_state.parquet' in result.validated_files
        assert 'portfolio_weights.parquet' in result.validated_files
    
    @settings(max_examples=100)
    @given(
        invalid_exposure=st.floats(min_value=1.1, max_value=10.0)
    )
    def test_property_invalid_exposure_detected(self, invalid_exposure):
        """
        Property: Invalid exposure values are detected
        
        For any exposure value outside [0, 1], validation should fail.
        """
        # Create market state with invalid exposure
        market_df = pd.DataFrame({
            'date': [datetime.now()],
            'regime': ['early-expansion'],
            'risk_on': [0.5],
            'allowed_exposure': [invalid_exposure],
            'stress_score': [0.3]
        })
        
        market_df.to_parquet(self.state_dir / 'market_state.parquet', index=False)
        
        # Create valid portfolio
        portfolio_df = pd.DataFrame({
            'date': [datetime.now()],
            'symbol': ['TEST'],
            'weight': [0.1],
            'exposure': [0.1]
        })
        portfolio_df.to_parquet(self.state_dir / 'portfolio_weights.parquet', index=False)
        
        # Validate
        validator = StateValidator(str(self.state_dir))
        result = validator.validate_all()
        
        # Should fail
        assert not result.is_valid
        assert any('allowed_exposure' in error for error in result.errors)
    
    def test_missing_required_file_fails_validation(self):
        """
        Integration test: Missing required files fail validation
        """
        # Don't create any files
        validator = StateValidator(str(self.state_dir))
        result = validator.validate_all()
        
        # Should fail
        assert not result.is_valid
        assert any('market_state.parquet' in error for error in result.errors)
    
    def test_missing_required_columns_fails_validation(self):
        """
        Integration test: Missing required columns fail validation
        """
        # Create market state missing 'regime' column
        market_df = pd.DataFrame({
            'date': [datetime.now()],
            'risk_on': [0.5],
            'allowed_exposure': [0.6],
            'stress_score': [0.3]
        })
        
        market_df.to_parquet(self.state_dir / 'market_state.parquet', index=False)
        
        # Create valid portfolio
        portfolio_df = pd.DataFrame({
            'date': [datetime.now()],
            'symbol': ['TEST'],
            'weight': [0.1],
            'exposure': [0.1]
        })
        portfolio_df.to_parquet(self.state_dir / 'portfolio_weights.parquet', index=False)
        
        # Validate
        validator = StateValidator(str(self.state_dir))
        result = validator.validate_all()
        
        # Should fail
        assert not result.is_valid
        assert any('regime' in error for error in result.errors)
    
    def test_date_mismatch_generates_warning(self):
        """
        Integration test: Date mismatches generate warnings
        """
        # Create market state with recent date
        market_df = pd.DataFrame({
            'date': [datetime.now()],
            'regime': ['early-expansion'],
            'risk_on': [0.5],
            'allowed_exposure': [0.6],
            'stress_score': [0.3]
        })
        market_df.to_parquet(self.state_dir / 'market_state.parquet', index=False)
        
        # Create portfolio with old date (30 days ago)
        old_date = datetime.now() - timedelta(days=30)
        portfolio_df = pd.DataFrame({
            'date': [old_date],
            'symbol': ['TEST'],
            'weight': [0.1],
            'exposure': [0.1]
        })
        portfolio_df.to_parquet(self.state_dir / 'portfolio_weights.parquet', index=False)
        
        # Validate
        validator = StateValidator(str(self.state_dir))
        result = validator.validate_all()
        
        # Should pass but with warnings
        assert result.is_valid  # Not a fatal error
        assert len(result.warnings) > 0
        assert any('Date mismatch' in warning for warning in result.warnings)
    
    def test_exposure_mismatch_generates_warning(self):
        """
        Integration test: Exposure mismatches generate warnings
        """
        current_date = datetime.now()
        
        # Create market state with 60% allowed exposure
        market_df = pd.DataFrame({
            'date': [current_date],
            'regime': ['early-expansion'],
            'risk_on': [0.5],
            'allowed_exposure': [0.6],
            'stress_score': [0.3]
        })
        market_df.to_parquet(self.state_dir / 'market_state.parquet', index=False)
        
        # Create portfolio with 90% actual exposure (>10% difference)
        portfolio_df = pd.DataFrame({
            'date': [current_date, current_date],
            'symbol': ['TEST1', 'TEST2'],
            'weight': [0.5, 0.4],
            'exposure': [0.5, 0.4]  # Total = 0.9
        })
        portfolio_df.to_parquet(self.state_dir / 'portfolio_weights.parquet', index=False)
        
        # Validate
        validator = StateValidator(str(self.state_dir))
        result = validator.validate_all()
        
        # Should pass but with warnings
        assert result.is_valid  # Not a fatal error
        assert len(result.warnings) > 0
        assert any('Exposure mismatch' in warning for warning in result.warnings)
    
    def test_repair_creates_missing_directory(self):
        """
        Integration test: Repair utility creates missing directories
        """
        # Remove state directory
        shutil.rmtree(self.state_dir)
        
        # Try repair
        validator = StateValidator(str(self.state_dir))
        repairs = validator.repair_common_issues()
        
        # Should create directory
        assert 'create_state_directory' in repairs['successful']
        assert self.state_dir.exists()
    
    def test_validate_state_on_startup_raises_on_failure(self):
        """
        Integration test: validate_state_on_startup raises RuntimeError on failure
        """
        # Don't create any files
        with pytest.raises(RuntimeError) as exc_info:
            validate_state_on_startup(str(self.state_dir))
        
        assert "State validation failed" in str(exc_info.value)
    
    def test_empty_dataframe_fails_minimum_rows(self):
        """
        Integration test: Empty DataFrames fail minimum row requirement
        """
        # Create empty market state
        market_df = pd.DataFrame({
            'date': pd.Series([], dtype='datetime64[ns]'),
            'regime': pd.Series([], dtype='object'),
            'risk_on': pd.Series([], dtype='float64'),
            'allowed_exposure': pd.Series([], dtype='float64'),
            'stress_score': pd.Series([], dtype='float64')
        })
        market_df.to_parquet(self.state_dir / 'market_state.parquet', index=False)
        
        # Create valid portfolio
        portfolio_df = pd.DataFrame({
            'date': [datetime.now()],
            'symbol': ['TEST'],
            'weight': [0.1],
            'exposure': [0.1]
        })
        portfolio_df.to_parquet(self.state_dir / 'portfolio_weights.parquet', index=False)
        
        # Validate
        validator = StateValidator(str(self.state_dir))
        result = validator.validate_all()
        
        # Should fail
        assert not result.is_valid
        assert any('minimum' in error.lower() for error in result.errors)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
