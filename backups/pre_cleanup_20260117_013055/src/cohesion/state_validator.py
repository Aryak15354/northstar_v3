"""
State Validator for System Integrity Repair

This module implements comprehensive state validation on system startup to detect
corruption, missing files, schema violations, and cross-file inconsistencies before
trading begins.

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd
import json

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of state validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    validated_files: List[str]
    timestamp: datetime


@dataclass
class StateFileSchema:
    """Expected schema for a state file"""
    required_columns: List[str]
    column_types: Dict[str, str]
    min_rows: int = 1


class StateValidator:
    """
    Validates system state files on startup
    
    Checks:
    - File existence
    - Schema compliance
    - Cross-file consistency
    - Data freshness
    - Value ranges
    """
    
    # Expected schemas for canonical state files
    SCHEMAS = {
        'market_state.parquet': StateFileSchema(
            required_columns=['date', 'regime', 'risk_on', 'allowed_exposure', 'stress_score'],
            column_types={
                'date': 'datetime64[ns]',
                'regime': 'object',
                'risk_on': 'float64',
                'allowed_exposure': 'float64',
                'stress_score': 'float64'
            }
        ),
        'portfolio_weights.parquet': StateFileSchema(
            required_columns=['date', 'symbol', 'weight', 'exposure'],
            column_types={
                'date': 'datetime64[ns]',
                'symbol': 'object',
                'weight': 'float64',
                'exposure': 'float64'
            }
        ),
        'risk_state.parquet': StateFileSchema(
            required_columns=['date', 'volatility', 'correlation', 'var'],
            column_types={
                'date': 'datetime64[ns]',
                'volatility': 'float64',
                'correlation': 'float64',
                'var': 'float64'
            },
            min_rows=0  # Optional file
        ),
        'exposure_history.parquet': StateFileSchema(
            required_columns=['date', 'allowed_exposure', 'actual_exposure', 
                            'risk_scaled_exposure', 'regime', 'stress_score'],
            column_types={
                'date': 'datetime64[ns]',
                'allowed_exposure': 'float64',
                'actual_exposure': 'float64',
                'risk_scaled_exposure': 'float64',
                'regime': 'object',
                'stress_score': 'float64'
            },
            min_rows=0  # Optional file
        )
    }
    
    def __init__(self, state_dir: str = "data/state"):
        """
        Initialize state validator
        
        Args:
            state_dir: Directory containing canonical state files
        """
        self.state_dir = Path(state_dir)
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.validated_files: List[str] = []
    
    def validate_all(self) -> ValidationResult:
        """
        Validate all canonical state files
        
        Returns:
            ValidationResult with overall status and details
        """
        self.errors = []
        self.warnings = []
        self.validated_files = []
        
        logger.info("Starting state validation...")
        
        # Validate each file
        for filename, schema in self.SCHEMAS.items():
            self._validate_file(filename, schema)
        
        # Validate cross-file consistency
        if not self.errors:  # Only if individual files are valid
            self._validate_cross_file_consistency()
        
        # Determine overall validity
        is_valid = len(self.errors) == 0
        
        result = ValidationResult(
            is_valid=is_valid,
            errors=self.errors.copy(),
            warnings=self.warnings.copy(),
            validated_files=self.validated_files.copy(),
            timestamp=datetime.now()
        )
        
        if is_valid:
            logger.info(f"✅ State validation passed. Validated {len(self.validated_files)} files.")
        else:
            logger.error(f"❌ State validation failed with {len(self.errors)} errors.")
            for error in self.errors:
                logger.error(f"  - {error}")
        
        if self.warnings:
            logger.warning(f"⚠️  {len(self.warnings)} warnings:")
            for warning in self.warnings:
                logger.warning(f"  - {warning}")
        
        return result
    
    def _validate_file(self, filename: str, schema: StateFileSchema) -> None:
        """
        Validate a single state file
        
        Args:
            filename: Name of file to validate
            schema: Expected schema
        """
        filepath = self.state_dir / filename
        
        # Check file existence
        if not filepath.exists():
            if schema.min_rows > 0:
                self.errors.append(f"Required file missing: {filename}")
            else:
                self.warnings.append(f"Optional file missing: {filename}")
            return
        
        try:
            # Load file
            if filename.endswith('.parquet'):
                df = pd.read_parquet(filepath)
            elif filename.endswith('.json'):
                with open(filepath, 'r') as f:
                    data = json.load(f)
                # For JSON files, just check it's valid JSON
                self.validated_files.append(filename)
                return
            else:
                self.errors.append(f"Unknown file type: {filename}")
                return
            
            # Validate schema
            self._validate_schema(filename, df, schema)
            
            # Validate data quality
            self._validate_data_quality(filename, df, schema)
            
            self.validated_files.append(filename)
            
        except Exception as e:
            self.errors.append(f"Failed to load {filename}: {str(e)}")
    
    def _validate_schema(self, filename: str, df: pd.DataFrame, schema: StateFileSchema) -> None:
        """
        Validate DataFrame schema matches expected schema
        
        Args:
            filename: Name of file being validated
            df: DataFrame to validate
            schema: Expected schema
        """
        # Check required columns
        missing_cols = set(schema.required_columns) - set(df.columns)
        if missing_cols:
            self.errors.append(
                f"{filename}: Missing required columns: {sorted(missing_cols)}"
            )
            return
        
        # Check column types
        for col, expected_type in schema.column_types.items():
            if col not in df.columns:
                continue
            
            actual_type = str(df[col].dtype)
            
            # Allow some type flexibility
            if expected_type == 'object' and actual_type in ['object', 'string']:
                continue
            if expected_type == 'float64' and actual_type in ['float64', 'float32', 'int64', 'int32']:
                continue
            if expected_type == 'datetime64[ns]' and 'datetime' in actual_type:
                continue
            
            if actual_type != expected_type:
                self.warnings.append(
                    f"{filename}: Column '{col}' has type {actual_type}, expected {expected_type}"
                )
        
        # Check minimum rows
        if len(df) < schema.min_rows:
            self.errors.append(
                f"{filename}: Has {len(df)} rows, minimum {schema.min_rows} required"
            )
    
    def _validate_data_quality(self, filename: str, df: pd.DataFrame, schema: StateFileSchema) -> None:
        """
        Validate data quality (ranges, NaN, etc.)
        
        Args:
            filename: Name of file being validated
            df: DataFrame to validate
            schema: Expected schema
        """
        if len(df) == 0:
            return
        
        # Check for NaN in critical columns
        for col in schema.required_columns:
            if col not in df.columns:
                continue
            
            nan_count = df[col].isna().sum()
            if nan_count > 0:
                self.warnings.append(
                    f"{filename}: Column '{col}' has {nan_count} NaN values"
                )
        
        # Validate specific column ranges
        if 'allowed_exposure' in df.columns:
            invalid = (df['allowed_exposure'] < 0) | (df['allowed_exposure'] > 1)
            if invalid.any():
                self.errors.append(
                    f"{filename}: allowed_exposure has {invalid.sum()} values outside [0, 1]"
                )
        
        if 'actual_exposure' in df.columns:
            invalid = (df['actual_exposure'] < 0) | (df['actual_exposure'] > 1)
            if invalid.any():
                self.errors.append(
                    f"{filename}: actual_exposure has {invalid.sum()} values outside [0, 1]"
                )
        
        if 'risk_on' in df.columns:
            invalid = (df['risk_on'] < 0) | (df['risk_on'] > 1)
            if invalid.any():
                self.errors.append(
                    f"{filename}: risk_on has {invalid.sum()} values outside [0, 1]"
                )
        
        if 'stress_score' in df.columns:
            invalid = (df['stress_score'] < 0) | (df['stress_score'] > 1)
            if invalid.any():
                self.errors.append(
                    f"{filename}: stress_score has {invalid.sum()} values outside [0, 1]"
                )
        
        if 'weight' in df.columns:
            invalid = (df['weight'] < -1) | (df['weight'] > 1)
            if invalid.any():
                self.errors.append(
                    f"{filename}: weight has {invalid.sum()} values outside [-1, 1]"
                )
    
    def _validate_cross_file_consistency(self) -> None:
        """
        Validate consistency between related state files
        """
        try:
            # Load files
            market_path = self.state_dir / 'market_state.parquet'
            portfolio_path = self.state_dir / 'portfolio_weights.parquet'
            
            if not market_path.exists() or not portfolio_path.exists():
                return  # Already reported as errors
            
            market_df = pd.read_parquet(market_path)
            portfolio_df = pd.read_parquet(portfolio_path)
            
            if len(market_df) == 0 or len(portfolio_df) == 0:
                return
            
            # Check date alignment
            market_date = market_df['date'].iloc[-1]
            portfolio_date = portfolio_df['date'].iloc[-1]
            
            date_diff = abs((market_date - portfolio_date).total_seconds() / 3600)
            if date_diff > 24:  # More than 24 hours apart
                self.warnings.append(
                    f"Date mismatch: market_state={market_date}, "
                    f"portfolio_weights={portfolio_date} ({date_diff:.1f} hours apart)"
                )
            
            # Check exposure alignment
            allowed_exposure = market_df['allowed_exposure'].iloc[-1]
            actual_exposure = portfolio_df['exposure'].sum()
            
            exposure_diff = abs(allowed_exposure - actual_exposure)
            if exposure_diff > 0.10:  # More than 10% difference
                self.warnings.append(
                    f"Exposure mismatch: allowed={allowed_exposure:.1%}, "
                    f"actual={actual_exposure:.1%} (diff={exposure_diff:.1%})"
                )
            
            # Check regime consistency
            if 'regime' in market_df.columns:
                regime = market_df['regime'].iloc[-1]
                valid_regimes = ['early-expansion', 'late-expansion', 
                               'early-contraction', 'late-contraction', 'unknown']
                if regime not in valid_regimes:
                    self.warnings.append(
                        f"Invalid regime: '{regime}' not in {valid_regimes}"
                    )
        
        except Exception as e:
            self.warnings.append(f"Cross-file validation failed: {str(e)}")
    
    def repair_common_issues(self) -> Dict[str, Any]:
        """
        Attempt to repair common state corruption patterns
        
        Returns:
            Dictionary with repair results
        """
        repairs = {
            'attempted': [],
            'successful': [],
            'failed': []
        }
        
        logger.info("Attempting to repair common state issues...")
        
        # Repair 1: Create missing directories
        if not self.state_dir.exists():
            try:
                self.state_dir.mkdir(parents=True, exist_ok=True)
                repairs['attempted'].append('create_state_directory')
                repairs['successful'].append('create_state_directory')
                logger.info(f"✅ Created state directory: {self.state_dir}")
            except Exception as e:
                repairs['failed'].append(f'create_state_directory: {str(e)}')
                logger.error(f"❌ Failed to create state directory: {e}")
        
        # Repair 2: Remove corrupt parquet files (will be regenerated)
        for filename in self.SCHEMAS.keys():
            if not filename.endswith('.parquet'):
                continue
            
            filepath = self.state_dir / filename
            if not filepath.exists():
                continue
            
            try:
                # Try to load
                pd.read_parquet(filepath)
            except Exception as e:
                # File is corrupt, try to remove
                repairs['attempted'].append(f'remove_corrupt_{filename}')
                try:
                    backup_path = filepath.with_suffix('.parquet.corrupt')
                    filepath.rename(backup_path)
                    repairs['successful'].append(f'remove_corrupt_{filename}')
                    logger.info(f"✅ Moved corrupt file to {backup_path}")
                except Exception as e2:
                    repairs['failed'].append(f'remove_corrupt_{filename}: {str(e2)}')
                    logger.error(f"❌ Failed to remove corrupt file: {e2}")
        
        logger.info(
            f"Repair complete: {len(repairs['successful'])} successful, "
            f"{len(repairs['failed'])} failed"
        )
        
        return repairs


def validate_state_on_startup(state_dir: str = "data/state") -> ValidationResult:
    """
    Convenience function to validate state on system startup
    
    Args:
        state_dir: Directory containing canonical state files
    
    Returns:
        ValidationResult
    
    Raises:
        RuntimeError: If validation fails
    """
    validator = StateValidator(state_dir)
    result = validator.validate_all()
    
    if not result.is_valid:
        error_msg = f"State validation failed with {len(result.errors)} errors:\n"
        for error in result.errors:
            error_msg += f"  - {error}\n"
        error_msg += "\nSystem cannot start with invalid state. "
        error_msg += "Run repair utility or fix issues manually."
        raise RuntimeError(error_msg)
    
    return result


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)
    
    try:
        result = validate_state_on_startup()
        print(f"\n✅ State validation passed!")
        print(f"Validated files: {result.validated_files}")
        if result.warnings:
            print(f"\n⚠️  Warnings:")
            for warning in result.warnings:
                print(f"  - {warning}")
    except RuntimeError as e:
        print(f"\n❌ State validation failed:")
        print(str(e))
        
        # Try repair
        print("\nAttempting automatic repair...")
        validator = StateValidator()
        repairs = validator.repair_common_issues()
        print(f"Repairs: {repairs}")
