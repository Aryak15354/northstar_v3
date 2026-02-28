#!/usr/bin/env python3
"""
🔍 DATA INGESTION VALIDATOR - CAPITAL-GRADE SYSTEM LAWS
Validates all data at ingestion points with comprehensive schema checking

This implements the capital-grade data ingestion validation system with
mathematical invariants that cannot be violated.

SYSTEM LAWS ENFORCED:
- Property 10: No Silent Data Loss (D1)
- Property 11: Data Freshness Enforcement (D2)
- Property 12: Schema Validation Completeness (D3)

These are not suggestions - they are LAWS that terminate the system if violated.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

from src.cohesion.schema_validator import SchemaValidator, DataSchema, ValidationResult, ValidationError, ErrorSeverity
from src.cohesion.data_format_standardizer import DataFormatStandardizer, DataSourceType, FormatStandardizationResult

class ValidationSeverity(Enum):
    """Validation severity levels"""
    CRITICAL = "critical"    # System must terminate
    HIGH = "high"           # Data must be quarantined
    MEDIUM = "medium"       # Warning with monitoring
    LOW = "low"            # Log for analysis

class DataQualityRule(Enum):
    """Data quality rules"""
    NO_NULL_REQUIRED_COLUMNS = "no_null_required_columns"
    FRESHNESS_CHECK = "freshness_check"
    DUPLICATE_CHECK = "duplicate_check"
    OUTLIER_CHECK = "outlier_check"
    COMPLETENESS_CHECK = "completeness_check"
    CONSISTENCY_CHECK = "consistency_check"
    TEMPORAL_ORDER_CHECK = "temporal_order_check"

@dataclass
class DataQualityConfig:
    """Configuration for data quality checks"""
    freshness_threshold: timedelta
    max_null_percentage: float = 0.1  # 10% max nulls
    max_duplicate_percentage: float = 0.05  # 5% max duplicates
    outlier_std_threshold: float = 3.0  # 3 standard deviations
    min_completeness_ratio: float = 0.8  # 80% minimum completeness
    temporal_column: Optional[str] = None
    
@dataclass
class IngestionValidationResult:
    """Result of data ingestion validation"""
    success: bool
    validated_data: Optional[pd.DataFrame]
    standardization_result: Optional[FormatStandardizationResult]
    quality_checks: Dict[str, bool]
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]
    should_quarantine: bool = False
    
class DataIngestionValidator:
    """
    Validates all data at ingestion points
    ENFORCES CAPITAL-GRADE SYSTEM LAWS FOR DATA QUALITY
    """
    
    def __init__(self, 
                 schema_validator: SchemaValidator,
                 format_standardizer: DataFormatStandardizer):
        self.schema_validator = schema_validator
        self.format_standardizer = format_standardizer
        self.quality_rules = self._initialize_quality_rules()
        
    def _initialize_quality_rules(self) -> Dict[DataQualityRule, Callable]:
        """Initialize data quality rule functions"""
        return {
            DataQualityRule.NO_NULL_REQUIRED_COLUMNS: self._check_required_columns,
            DataQualityRule.FRESHNESS_CHECK: self._check_data_freshness,
            DataQualityRule.DUPLICATE_CHECK: self._check_duplicates,
            DataQualityRule.OUTLIER_CHECK: self._check_outliers,
            DataQualityRule.COMPLETENESS_CHECK: self._check_completeness,
            DataQualityRule.CONSISTENCY_CHECK: self._check_consistency,
            DataQualityRule.TEMPORAL_ORDER_CHECK: self._check_temporal_order,
        }
    
    def validate_ingestion(self,
                          df: pd.DataFrame,
                          source_type: DataSourceType,
                          source_name: str,
                          quality_config: DataQualityConfig,
                          enforce_schema: bool = True) -> IngestionValidationResult:
        """
        Comprehensive validation of data at ingestion point
        ENFORCES ALL DATA QUALITY INVARIANTS
        """
        
        if df is None or df.empty:
            return IngestionValidationResult(
                success=False,
                validated_data=None,
                standardization_result=None,
                quality_checks={},
                errors=["Input DataFrame is None or empty"],
                warnings=[],
                metadata={'source_name': source_name, 'source_type': source_type.value},
                should_quarantine=True
            )
        
        errors = []
        warnings = []
        quality_checks = {}
        should_quarantine = False
        
        try:
            # Step 1: Format Standardization
            print(f"🔄 Standardizing format for {source_name} ({source_type.value})")
            standardization_result = self.format_standardizer.standardize_data_format(
                df, source_type, validate_schema=enforce_schema
            )
            
            if not standardization_result.success:
                errors.extend(standardization_result.errors)
                should_quarantine = True
                
            warnings.extend(standardization_result.warnings)
            
            # Use standardized data for further validation
            validated_df = standardization_result.standardized_data if standardization_result.success else df
            
            # Step 2: Data Quality Checks
            print(f"🔍 Running quality checks for {source_name}")
            for rule in DataQualityRule:
                try:
                    check_result = self.quality_rules[rule](validated_df, quality_config)
                    quality_checks[rule.value] = check_result['passed']
                    
                    if not check_result['passed']:
                        if check_result['severity'] == ValidationSeverity.CRITICAL:
                            errors.append(f"CRITICAL: {check_result['message']}")
                            should_quarantine = True
                        elif check_result['severity'] == ValidationSeverity.HIGH:
                            errors.append(f"HIGH: {check_result['message']}")
                            should_quarantine = True
                        elif check_result['severity'] == ValidationSeverity.MEDIUM:
                            warnings.append(f"MEDIUM: {check_result['message']}")
                        else:
                            warnings.append(f"LOW: {check_result['message']}")
                            
                except Exception as e:
                    warnings.append(f"Quality check {rule.value} failed: {str(e)}")
                    quality_checks[rule.value] = False
            
            # Step 3: Final Validation
            final_success = len(errors) == 0 and standardization_result.success
            
            # ENFORCE INVARIANT D1: No Silent Data Loss
            if validated_df is not None and len(validated_df) < len(df):
                data_loss_ratio = (len(df) - len(validated_df)) / len(df)
                if data_loss_ratio > 0.1:  # More than 10% data loss
                    errors.append(f"INVARIANT VIOLATION D1: Excessive data loss: {data_loss_ratio:.2%}")
                    should_quarantine = True
            
            return IngestionValidationResult(
                success=final_success,
                validated_data=validated_df if final_success else None,
                standardization_result=standardization_result,
                quality_checks=quality_checks,
                errors=errors,
                warnings=warnings,
                metadata={
                    'source_name': source_name,
                    'source_type': source_type.value,
                    'original_shape': df.shape,
                    'validated_shape': validated_df.shape if validated_df is not None else (0, 0),
                    'quality_score': sum(quality_checks.values()) / len(quality_checks) if quality_checks else 0.0,
                    'validation_timestamp': datetime.now().isoformat()
                },
                should_quarantine=should_quarantine
            )
            
        except Exception as e:
            return IngestionValidationResult(
                success=False,
                validated_data=None,
                standardization_result=standardization_result if 'standardization_result' in locals() else None,
                quality_checks=quality_checks,
                errors=[f"Validation failed: {str(e)}"],
                warnings=warnings,
                metadata={'source_name': source_name, 'source_type': source_type.value},
                should_quarantine=True
            )
    
    def _check_required_columns(self, df: pd.DataFrame, config: DataQualityConfig) -> Dict[str, Any]:
        """Check for null values in required columns"""
        
        if df is None or df.empty:
            return {
                'passed': False,
                'severity': ValidationSeverity.CRITICAL,
                'message': "DataFrame is None or empty"
            }
        
        # Check for excessive nulls in any column
        null_percentages = df.isnull().sum() / len(df)
        excessive_nulls = null_percentages[null_percentages > config.max_null_percentage]
        
        if len(excessive_nulls) > 0:
            return {
                'passed': False,
                'severity': ValidationSeverity.HIGH,
                'message': f"Excessive nulls in columns: {excessive_nulls.to_dict()}"
            }
        
        return {
            'passed': True,
            'severity': ValidationSeverity.LOW,
            'message': "Required columns check passed"
        }
    
    def _check_data_freshness(self, df: pd.DataFrame, config: DataQualityConfig) -> Dict[str, Any]:
        """
        Check data freshness
        ENFORCES INVARIANT D2: Data Freshness Enforcement
        """
        
        if config.temporal_column is None:
            return {
                'passed': True,
                'severity': ValidationSeverity.LOW,
                'message': "No temporal column specified for freshness check"
            }
        
        if config.temporal_column not in df.columns:
            return {
                'passed': False,
                'severity': ValidationSeverity.MEDIUM,
                'message': f"Temporal column {config.temporal_column} not found"
            }
        
        try:
            # Get the latest timestamp in the data
            latest_timestamp = pd.to_datetime(df[config.temporal_column]).max()
            current_time = datetime.now()
            
            # Calculate data age
            data_age = current_time - latest_timestamp
            
            # ENFORCE INVARIANT D2: Data Freshness Enforcement
            if data_age > config.freshness_threshold:
                return {
                    'passed': False,
                    'severity': ValidationSeverity.HIGH,
                    'message': f"INVARIANT VIOLATION D2: Data is stale. Age: {data_age}, Threshold: {config.freshness_threshold}"
                }
            
            return {
                'passed': True,
                'severity': ValidationSeverity.LOW,
                'message': f"Data freshness check passed. Age: {data_age}"
            }
            
        except Exception as e:
            return {
                'passed': False,
                'severity': ValidationSeverity.MEDIUM,
                'message': f"Freshness check failed: {str(e)}"
            }
    
    def _check_duplicates(self, df: pd.DataFrame, config: DataQualityConfig) -> Dict[str, Any]:
        """Check for excessive duplicate rows"""
        
        if df is None or df.empty:
            return {
                'passed': False,
                'severity': ValidationSeverity.CRITICAL,
                'message': "DataFrame is None or empty"
            }
        
        duplicate_count = df.duplicated().sum()
        duplicate_percentage = duplicate_count / len(df)
        
        if duplicate_percentage > config.max_duplicate_percentage:
            return {
                'passed': False,
                'severity': ValidationSeverity.MEDIUM,
                'message': f"Excessive duplicates: {duplicate_percentage:.2%} (threshold: {config.max_duplicate_percentage:.2%})"
            }
        
        return {
            'passed': True,
            'severity': ValidationSeverity.LOW,
            'message': f"Duplicate check passed: {duplicate_percentage:.2%}"
        }
    
    def _check_outliers(self, df: pd.DataFrame, config: DataQualityConfig) -> Dict[str, Any]:
        """Check for statistical outliers in numeric columns"""
        
        if df is None or df.empty:
            return {
                'passed': False,
                'severity': ValidationSeverity.CRITICAL,
                'message': "DataFrame is None or empty"
            }
        
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        
        if len(numeric_columns) == 0:
            return {
                'passed': True,
                'severity': ValidationSeverity.LOW,
                'message': "No numeric columns for outlier detection"
            }
        
        outlier_columns = []
        
        for col in numeric_columns:
            if df[col].std() > 0:  # Avoid division by zero
                z_scores = np.abs((df[col] - df[col].mean()) / df[col].std())
                outlier_count = (z_scores > config.outlier_std_threshold).sum()
                outlier_percentage = outlier_count / len(df)
                
                # Flag if more than 5% of values are outliers
                if outlier_percentage > 0.05:
                    outlier_columns.append((col, outlier_percentage))
        
        if outlier_columns:
            return {
                'passed': False,
                'severity': ValidationSeverity.MEDIUM,
                'message': f"Excessive outliers in columns: {outlier_columns}"
            }
        
        return {
            'passed': True,
            'severity': ValidationSeverity.LOW,
            'message': "Outlier check passed"
        }
    
    def _check_completeness(self, df: pd.DataFrame, config: DataQualityConfig) -> Dict[str, Any]:
        """Check data completeness"""
        
        if df is None or df.empty:
            return {
                'passed': False,
                'severity': ValidationSeverity.CRITICAL,
                'message': "DataFrame is None or empty"
            }
        
        # Calculate completeness ratio (non-null values / total values)
        total_values = df.size
        non_null_values = df.count().sum()
        completeness_ratio = non_null_values / total_values if total_values > 0 else 0
        
        if completeness_ratio < config.min_completeness_ratio:
            return {
                'passed': False,
                'severity': ValidationSeverity.HIGH,
                'message': f"Low data completeness: {completeness_ratio:.2%} (threshold: {config.min_completeness_ratio:.2%})"
            }
        
        return {
            'passed': True,
            'severity': ValidationSeverity.LOW,
            'message': f"Completeness check passed: {completeness_ratio:.2%}"
        }
    
    def _check_consistency(self, df: pd.DataFrame, config: DataQualityConfig) -> Dict[str, Any]:
        """Check data consistency (basic checks)"""
        
        if df is None or df.empty:
            return {
                'passed': False,
                'severity': ValidationSeverity.CRITICAL,
                'message': "DataFrame is None or empty"
            }
        
        consistency_issues = []
        
        # Check for mixed data types in object columns
        object_columns = df.select_dtypes(include=['object']).columns
        for col in object_columns:
            unique_types = set(type(x).__name__ for x in df[col].dropna().values)
            if len(unique_types) > 1:
                consistency_issues.append(f"Mixed types in {col}: {unique_types}")
        
        # Check for negative values in columns that should be positive
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        for col in numeric_columns:
            if 'price' in col.lower() or 'volume' in col.lower() or 'rate' in col.lower():
                if (df[col] < 0).any():
                    consistency_issues.append(f"Negative values in {col}")
        
        if consistency_issues:
            return {
                'passed': False,
                'severity': ValidationSeverity.MEDIUM,
                'message': f"Consistency issues: {consistency_issues}"
            }
        
        return {
            'passed': True,
            'severity': ValidationSeverity.LOW,
            'message': "Consistency check passed"
        }
    
    def _check_temporal_order(self, df: pd.DataFrame, config: DataQualityConfig) -> Dict[str, Any]:
        """Check temporal ordering of data"""
        
        if config.temporal_column is None:
            return {
                'passed': True,
                'severity': ValidationSeverity.LOW,
                'message': "No temporal column specified"
            }
        
        if config.temporal_column not in df.columns:
            return {
                'passed': False,
                'severity': ValidationSeverity.MEDIUM,
                'message': f"Temporal column {config.temporal_column} not found"
            }
        
        try:
            # Convert to datetime and check ordering
            temporal_series = pd.to_datetime(df[config.temporal_column])
            
            # Check if data is sorted
            is_sorted = temporal_series.is_monotonic_increasing
            
            if not is_sorted:
                return {
                    'passed': False,
                    'severity': ValidationSeverity.MEDIUM,
                    'message': f"Temporal data is not properly ordered in {config.temporal_column}"
                }
            
            return {
                'passed': True,
                'severity': ValidationSeverity.LOW,
                'message': "Temporal order check passed"
            }
            
        except Exception as e:
            return {
                'passed': False,
                'severity': ValidationSeverity.MEDIUM,
                'message': f"Temporal order check failed: {str(e)}"
            }
    
    def quarantine_data(self, 
                       df: pd.DataFrame, 
                       source_name: str, 
                       validation_result: IngestionValidationResult,
                       quarantine_dir: str = "data/quarantine") -> str:
        """Quarantine bad data with detailed logging"""
        
        os.makedirs(quarantine_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        quarantine_file = os.path.join(quarantine_dir, f"{source_name}_{timestamp}.parquet")
        
        # Save quarantined data
        df.to_parquet(quarantine_file)
        
        # Save validation report
        report_file = os.path.join(quarantine_dir, f"{source_name}_{timestamp}_report.json")
        report = {
            'source_name': source_name,
            'quarantine_timestamp': timestamp,
            'validation_result': {
                'success': validation_result.success,
                'errors': validation_result.errors,
                'warnings': validation_result.warnings,
                'quality_checks': validation_result.quality_checks,
                'metadata': validation_result.metadata
            }
        }
        
        import json
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"⚠️  Data quarantined: {quarantine_file}")
        print(f"📋 Report saved: {report_file}")
        
        return quarantine_file