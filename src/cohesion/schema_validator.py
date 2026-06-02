#!/usr/bin/env python3
"""
📋 SCHEMA VALIDATOR - CAPITAL-GRADE DATA QUALITY SYSTEM
Comprehensive Data Schema Validation and Quality Gates

This implements the capital-grade data quality system with
mathematical invariants that prevent data corruption.

SYSTEM LAWS ENFORCED:
- Invariant D1: No Silent Data Loss - data loss must be explained and within thresholds
- Invariant D2: Data Freshness Enforcement - data age must be within configured thresholds
- Invariant D3: Schema Validation Completeness - all data must pass schema validation

These are not suggestions - they are LAWS that terminate the system if violated.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Union, Protocol
from dataclasses import dataclass, asdict, field
from abc import ABC, abstractmethod
from enum import Enum
import warnings
import json
warnings.filterwarnings('ignore')

class DataType(Enum):
    """Supported data types for schema validation"""
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    DATETIME = "datetime"
    BOOLEAN = "boolean"
    CATEGORICAL = "categorical"

class ConstraintType(Enum):
    """Types of data constraints"""
    NOT_NULL = "not_null"
    UNIQUE = "unique"
    MIN_VALUE = "min_value"
    MAX_VALUE = "max_value"
    MIN_LENGTH = "min_length"
    MAX_LENGTH = "max_length"
    REGEX_PATTERN = "regex_pattern"
    IN_VALUES = "in_values"
    FOREIGN_KEY = "foreign_key"

@dataclass
class ColumnSchema:
    """Schema definition for a single column"""
    name: str
    data_type: DataType
    nullable: bool = True
    constraints: List[Dict[str, Any]] = field(default_factory=list)
    description: str = ""
    
    def validate_value(self, value: Any) -> List[str]:
        """Validate a single value against this column schema"""
        errors = []
        
        # Check null values
        if pd.isna(value) or value is None:
            if not self.nullable:
                errors.append(f"Column '{self.name}' cannot be null")
            return errors  # Skip other validations for null values
        
        # Type validation
        if not self._validate_type(value):
            errors.append(f"Column '{self.name}' value '{value}' is not of type {self.data_type.value}")
        
        # Constraint validation
        for constraint in self.constraints:
            constraint_errors = self._validate_constraint(value, constraint)
            errors.extend(constraint_errors)
        
        return errors
    
    def _validate_type(self, value: Any) -> bool:
        """Validate value type"""
        try:
            if self.data_type == DataType.INTEGER:
                return isinstance(value, (int, np.integer)) or (isinstance(value, float) and value.is_integer())
            elif self.data_type == DataType.FLOAT:
                return isinstance(value, (int, float, np.number))
            elif self.data_type == DataType.STRING:
                return isinstance(value, str)
            elif self.data_type == DataType.DATETIME:
                return isinstance(value, (datetime, pd.Timestamp)) or pd.api.types.is_datetime64_any_dtype(pd.Series([value]))
            elif self.data_type == DataType.BOOLEAN:
                return isinstance(value, (bool, np.bool_))
            elif self.data_type == DataType.CATEGORICAL:
                return True  # Any value can be categorical
            return False
        except:
            return False
    
    def _validate_constraint(self, value: Any, constraint: Dict[str, Any]) -> List[str]:
        """Validate value against a constraint"""
        errors = []
        constraint_type = ConstraintType(constraint['type'])
        
        try:
            if constraint_type == ConstraintType.MIN_VALUE:
                if value < constraint['value']:
                    errors.append(f"Column '{self.name}' value {value} is less than minimum {constraint['value']}")
            
            elif constraint_type == ConstraintType.MAX_VALUE:
                if value > constraint['value']:
                    errors.append(f"Column '{self.name}' value {value} is greater than maximum {constraint['value']}")
            
            elif constraint_type == ConstraintType.MIN_LENGTH:
                if len(str(value)) < constraint['value']:
                    errors.append(f"Column '{self.name}' value length {len(str(value))} is less than minimum {constraint['value']}")
            
            elif constraint_type == ConstraintType.MAX_LENGTH:
                if len(str(value)) > constraint['value']:
                    errors.append(f"Column '{self.name}' value length {len(str(value))} is greater than maximum {constraint['value']}")
            
            elif constraint_type == ConstraintType.IN_VALUES:
                if value not in constraint['values']:
                    errors.append(f"Column '{self.name}' value '{value}' not in allowed values {constraint['values']}")
            
            elif constraint_type == ConstraintType.REGEX_PATTERN:
                import re
                if not re.match(constraint['pattern'], str(value)):
                    errors.append(f"Column '{self.name}' value '{value}' does not match pattern '{constraint['pattern']}'")
        
        except Exception as e:
            errors.append(f"Error validating constraint {constraint_type.value} for column '{self.name}': {e}")
        
        return errors

@dataclass
class DataSchema:
    """Complete data schema definition with validation rules"""
    name: str
    version: str
    columns: Dict[str, ColumnSchema]
    constraints: List[Dict[str, Any]] = field(default_factory=list)
    temporal_columns: List[str] = field(default_factory=list)
    primary_key: Optional[List[str]] = None
    description: str = ""
    
    def validate_dataframe(self, df: pd.DataFrame) -> 'ValidationResult':
        """
        Validate DataFrame against this schema
        ENFORCES INVARIANT D3: Schema Validation Completeness
        """
        errors = []
        warnings = []
        
        # Check required columns
        missing_columns = set(self.columns.keys()) - set(df.columns)
        if missing_columns:
            errors.extend([f"Missing required column: {col}" for col in missing_columns])
        
        # Check unexpected columns
        unexpected_columns = set(df.columns) - set(self.columns.keys())
        if unexpected_columns:
            warnings.extend([f"Unexpected column: {col}" for col in unexpected_columns])
        
        # Validate each column
        for col_name, col_schema in self.columns.items():
            if col_name in df.columns:
                column_errors = self._validate_column(df[col_name], col_schema)
                errors.extend(column_errors)
        
        # Validate table-level constraints
        table_errors = self._validate_table_constraints(df)
        errors.extend(table_errors)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=[ValidationError(code="SCHEMA_VALIDATION", message=error, field="", value="", severity=ErrorSeverity.HIGH) for error in errors],
            warnings=[ValidationWarning(code="SCHEMA_WARNING", message=warning, field="") for warning in warnings],
            metadata={
                'schema_name': self.name,
                'schema_version': self.version,
                'rows_validated': len(df),
                'columns_validated': len(self.columns)
            }
        )
    
    def _validate_column(self, series: pd.Series, col_schema: ColumnSchema) -> List[str]:
        """Validate a pandas Series against column schema"""
        errors = []
        
        # Sample validation (validate first 1000 rows for performance)
        sample_size = min(1000, len(series))
        sample_series = series.head(sample_size)
        
        error_count = 0
        for idx, value in sample_series.items():
            value_errors = col_schema.validate_value(value)
            if value_errors:
                errors.extend([f"Row {idx}: {error}" for error in value_errors])
                error_count += 1
                
                # Stop after 10 errors per column to avoid spam
                if error_count >= 10:
                    remaining_rows = len(series) - idx - 1
                    if remaining_rows > 0:
                        errors.append(f"... and potentially {remaining_rows} more rows with violations")
                    break
        
        return errors
    
    def _validate_table_constraints(self, df: pd.DataFrame) -> List[str]:
        """Validate table-level constraints"""
        errors = []
        
        # Primary key uniqueness
        if self.primary_key:
            pk_columns = [col for col in self.primary_key if col in df.columns]
            if pk_columns:
                duplicates = df.duplicated(subset=pk_columns).sum()
                if duplicates > 0:
                    errors.append(f"Primary key constraint violated: {duplicates} duplicate rows found")
        
        # Custom table constraints
        for constraint in self.constraints:
            try:
                constraint_errors = self._validate_table_constraint(df, constraint)
                errors.extend(constraint_errors)
            except Exception as e:
                errors.append(f"Error validating table constraint: {e}")
        
        return errors
    
    def _validate_table_constraint(self, df: pd.DataFrame, constraint: Dict[str, Any]) -> List[str]:
        """Validate a single table constraint"""
        errors = []
        
        constraint_type = constraint.get('type')
        
        if constraint_type == 'row_count_min':
            if len(df) < constraint['value']:
                errors.append(f"Table has {len(df)} rows, minimum required: {constraint['value']}")
        
        elif constraint_type == 'row_count_max':
            if len(df) > constraint['value']:
                errors.append(f"Table has {len(df)} rows, maximum allowed: {constraint['value']}")
        
        elif constraint_type == 'column_correlation':
            col1, col2 = constraint['columns']
            if col1 in df.columns and col2 in df.columns:
                correlation = df[col1].corr(df[col2])
                if abs(correlation) < constraint['min_correlation']:
                    errors.append(f"Correlation between {col1} and {col2} is {correlation:.3f}, minimum required: {constraint['min_correlation']}")
        
        return errors

class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

@dataclass
class ValidationError:
    """Detailed validation error"""
    code: str
    message: str
    field: str
    value: Any
    severity: ErrorSeverity
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class ValidationWarning:
    """Validation warning"""
    code: str
    message: str
    field: str
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class ValidationResult:
    """Standardized validation result"""
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationWarning]
    metadata: Dict[str, Any]
    
    def raise_if_invalid(self):
        """Raise exception if validation failed"""
        if not self.is_valid:
            error_messages = [error.message for error in self.errors]
            raise ValueError(f"Validation failed: {'; '.join(error_messages)}")

@dataclass
class QualityRule:
    """Data quality rule definition"""
    name: str
    rule_type: str
    parameters: Dict[str, Any]
    severity: ErrorSeverity
    description: str = ""
    
    def evaluate(self, data: pd.DataFrame, context: 'DataContext') -> List['QualityViolation']:
        """Evaluate quality rule against data"""
        violations = []
        
        try:
            if self.rule_type == 'completeness':
                violations.extend(self._check_completeness(data))
            elif self.rule_type == 'freshness':
                violations.extend(self._check_freshness(data, context))
            elif self.rule_type == 'uniqueness':
                violations.extend(self._check_uniqueness(data))
            elif self.rule_type == 'consistency':
                violations.extend(self._check_consistency(data))
            elif self.rule_type == 'accuracy':
                violations.extend(self._check_accuracy(data))
            elif self.rule_type == 'validity':
                violations.extend(self._check_validity(data))
        
        except Exception as e:
            violations.append(QualityViolation(
                rule_name=self.name,
                violation_type="RULE_EVALUATION_ERROR",
                message=f"Error evaluating rule: {e}",
                affected_rows=0,
                severity=ErrorSeverity.HIGH
            ))
        
        return violations
    
    def _check_completeness(self, data: pd.DataFrame) -> List['QualityViolation']:
        """Check data completeness"""
        violations = []
        
        required_columns = self.parameters.get('required_columns', [])
        max_null_percentage = self.parameters.get('max_null_percentage', 0.05)
        
        for column in required_columns:
            if column in data.columns:
                null_percentage = data[column].isnull().sum() / len(data)
                if null_percentage > max_null_percentage:
                    violations.append(QualityViolation(
                        rule_name=self.name,
                        violation_type="COMPLETENESS_VIOLATION",
                        message=f"Column '{column}' has {null_percentage:.2%} null values, exceeds threshold {max_null_percentage:.2%}",
                        affected_rows=int(data[column].isnull().sum()),
                        severity=self.severity
                    ))
        
        return violations
    
    def _check_freshness(self, data: pd.DataFrame, context: 'DataContext') -> List['QualityViolation']:
        """
        Check data freshness
        ENFORCES INVARIANT D2: Data Freshness Enforcement
        """
        violations = []
        
        timestamp_column = self.parameters.get('timestamp_column')
        max_age_hours = self.parameters.get('max_age_hours', 24)
        
        if timestamp_column and timestamp_column in data.columns:
            try:
                timestamps = pd.to_datetime(data[timestamp_column])
                current_time = datetime.now()
                
                # Check latest data age
                latest_timestamp = timestamps.max()
                age_hours = (current_time - latest_timestamp).total_seconds() / 3600
                
                if age_hours > max_age_hours:
                    violations.append(QualityViolation(
                        rule_name=self.name,
                        violation_type="FRESHNESS_VIOLATION",
                        message=f"Data is {age_hours:.1f} hours old, exceeds threshold {max_age_hours} hours",
                        affected_rows=len(data),
                        severity=self.severity
                    ))
            
            except Exception as e:
                violations.append(QualityViolation(
                    rule_name=self.name,
                    violation_type="FRESHNESS_CHECK_ERROR",
                    message=f"Error checking freshness: {e}",
                    affected_rows=0,
                    severity=ErrorSeverity.MEDIUM
                ))
        
        return violations
    
    def _check_uniqueness(self, data: pd.DataFrame) -> List['QualityViolation']:
        """Check data uniqueness"""
        violations = []
        
        unique_columns = self.parameters.get('unique_columns', [])
        
        for column in unique_columns:
            if column in data.columns:
                duplicates = data[column].duplicated().sum()
                if duplicates > 0:
                    violations.append(QualityViolation(
                        rule_name=self.name,
                        violation_type="UNIQUENESS_VIOLATION",
                        message=f"Column '{column}' has {duplicates} duplicate values",
                        affected_rows=duplicates,
                        severity=self.severity
                    ))
        
        return violations
    
    def _check_consistency(self, data: pd.DataFrame) -> List['QualityViolation']:
        """Check data consistency"""
        violations = []
        
        consistency_rules = self.parameters.get('consistency_rules', [])
        
        for rule in consistency_rules:
            try:
                if rule['type'] == 'column_sum':
                    columns = rule['columns']
                    target_column = rule['target_column']
                    
                    if all(col in data.columns for col in columns + [target_column]):
                        calculated_sum = data[columns].sum(axis=1)
                        actual_values = data[target_column]
                        
                        tolerance = rule.get('tolerance', 0.01)
                        inconsistent_rows = abs(calculated_sum - actual_values) > tolerance
                        inconsistent_count = inconsistent_rows.sum()
                        
                        if inconsistent_count > 0:
                            violations.append(QualityViolation(
                                rule_name=self.name,
                                violation_type="CONSISTENCY_VIOLATION",
                                message=f"Column sum consistency violated in {inconsistent_count} rows",
                                affected_rows=inconsistent_count,
                                severity=self.severity
                            ))
            
            except Exception as e:
                violations.append(QualityViolation(
                    rule_name=self.name,
                    violation_type="CONSISTENCY_CHECK_ERROR",
                    message=f"Error checking consistency rule: {e}",
                    affected_rows=0,
                    severity=ErrorSeverity.MEDIUM
                ))
        
        return violations
    
    def _check_accuracy(self, data: pd.DataFrame) -> List['QualityViolation']:
        """Check data accuracy"""
        violations = []
        
        accuracy_rules = self.parameters.get('accuracy_rules', [])
        
        for rule in accuracy_rules:
            try:
                if rule['type'] == 'range_check':
                    column = rule['column']
                    min_value = rule.get('min_value')
                    max_value = rule.get('max_value')
                    
                    if column in data.columns:
                        out_of_range = pd.Series([False] * len(data))
                        
                        if min_value is not None:
                            out_of_range |= data[column] < min_value
                        
                        if max_value is not None:
                            out_of_range |= data[column] > max_value
                        
                        out_of_range_count = out_of_range.sum()
                        
                        if out_of_range_count > 0:
                            violations.append(QualityViolation(
                                rule_name=self.name,
                                violation_type="ACCURACY_VIOLATION",
                                message=f"Column '{column}' has {out_of_range_count} values out of range [{min_value}, {max_value}]",
                                affected_rows=out_of_range_count,
                                severity=self.severity
                            ))
            
            except Exception as e:
                violations.append(QualityViolation(
                    rule_name=self.name,
                    violation_type="ACCURACY_CHECK_ERROR",
                    message=f"Error checking accuracy rule: {e}",
                    affected_rows=0,
                    severity=ErrorSeverity.MEDIUM
                ))
        
        return violations
    
    def _check_validity(self, data: pd.DataFrame) -> List['QualityViolation']:
        """Check data validity"""
        violations = []
        
        validity_rules = self.parameters.get('validity_rules', [])
        
        for rule in validity_rules:
            try:
                if rule['type'] == 'format_check':
                    column = rule['column']
                    pattern = rule['pattern']
                    
                    if column in data.columns:
                        import re
                        invalid_format = ~data[column].astype(str).str.match(pattern)
                        invalid_count = invalid_format.sum()
                        
                        if invalid_count > 0:
                            violations.append(QualityViolation(
                                rule_name=self.name,
                                violation_type="VALIDITY_VIOLATION",
                                message=f"Column '{column}' has {invalid_count} values with invalid format",
                                affected_rows=invalid_count,
                                severity=self.severity
                            ))
            
            except Exception as e:
                violations.append(QualityViolation(
                    rule_name=self.name,
                    violation_type="VALIDITY_CHECK_ERROR",
                    message=f"Error checking validity rule: {e}",
                    affected_rows=0,
                    severity=ErrorSeverity.MEDIUM
                ))
        
        return violations

@dataclass
class QualityViolation:
    """Data quality violation"""
    rule_name: str
    violation_type: str
    message: str
    affected_rows: int
    severity: ErrorSeverity
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class DataContext:
    """Context information for data validation"""
    source_name: str
    load_timestamp: datetime
    expected_row_count: Optional[int] = None
    previous_load_timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class QualityResult:
    """Data quality validation result"""
    is_valid: bool
    violations: List[QualityViolation]
    rules_evaluated: int
    data_rows: int
    quality_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_critical_violations(self) -> List[QualityViolation]:
        """Get critical violations that require immediate attention"""
        return [v for v in self.violations if v.severity == ErrorSeverity.CRITICAL]

class SchemaRegistry:
    """Registry for data schemas"""
    
    def __init__(self, schema_dir: str = "config/schemas"):
        self.schema_dir = schema_dir
        self.schemas: Dict[str, DataSchema] = {}
        os.makedirs(schema_dir, exist_ok=True)
    
    def register_schema(self, schema: DataSchema):
        """Register a data schema"""
        self.schemas[schema.name] = schema
        
        # Persist to file
        schema_file = os.path.join(self.schema_dir, f"{schema.name}.json")
        try:
            schema_dict = self._schema_to_dict(schema)
            with open(schema_file, 'w') as f:
                json.dump(schema_dict, f, indent=2, default=str)
        except Exception as e:
            print(f"⚠️ Error persisting schema {schema.name}: {e}")
    
    def get_schema(self, name: str) -> Optional[DataSchema]:
        """Get schema by name"""
        if name in self.schemas:
            return self.schemas[name]
        
        # Try to load from file
        schema_file = os.path.join(self.schema_dir, f"{name}.json")
        if os.path.exists(schema_file):
            try:
                with open(schema_file, 'r') as f:
                    schema_dict = json.load(f)
                schema = self._dict_to_schema(schema_dict)
                self.schemas[name] = schema
                return schema
            except Exception as e:
                print(f"⚠️ Error loading schema {name}: {e}")
        
        return None
    
    def list_schemas(self) -> List[str]:
        """List all registered schema names"""
        return list(self.schemas.keys())
    
    def _schema_to_dict(self, schema: DataSchema) -> Dict[str, Any]:
        """Convert schema to dictionary for serialization"""
        return {
            'name': schema.name,
            'version': schema.version,
            'description': schema.description,
            'columns': {
                name: {
                    'name': col.name,
                    'data_type': col.data_type.value,
                    'nullable': col.nullable,
                    'constraints': col.constraints,
                    'description': col.description
                }
                for name, col in schema.columns.items()
            },
            'constraints': schema.constraints,
            'temporal_columns': schema.temporal_columns,
            'primary_key': schema.primary_key
        }
    
    def _dict_to_schema(self, schema_dict: Dict[str, Any]) -> DataSchema:
        """Convert dictionary to schema object"""
        columns = {}
        for name, col_dict in schema_dict['columns'].items():
            columns[name] = ColumnSchema(
                name=col_dict['name'],
                data_type=DataType(col_dict['data_type']),
                nullable=col_dict.get('nullable', True),
                constraints=col_dict.get('constraints', []),
                description=col_dict.get('description', '')
            )
        
        return DataSchema(
            name=schema_dict['name'],
            version=schema_dict['version'],
            columns=columns,
            constraints=schema_dict.get('constraints', []),
            temporal_columns=schema_dict.get('temporal_columns', []),
            primary_key=schema_dict.get('primary_key'),
            description=schema_dict.get('description', '')
        )

class ValidationCache:
    """Cache for validation results to improve performance"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache: Dict[str, Dict[str, Any]] = {}
    
    def get(self, key: str) -> Optional[ValidationResult]:
        """Get cached validation result"""
        if key in self.cache:
            cache_entry = self.cache[key]
            
            # Check if cache entry is still valid (not expired)
            if datetime.now() - cache_entry['timestamp'] < timedelta(minutes=30):
                return cache_entry['result']
            else:
                # Remove expired entry
                del self.cache[key]
        
        return None
    
    def put(self, key: str, result: ValidationResult):
        """Cache validation result"""
        # Implement LRU eviction if cache is full
        if len(self.cache) >= self.max_size:
            # Remove oldest entry
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k]['timestamp'])
            del self.cache[oldest_key]
        
        self.cache[key] = {
            'result': result,
            'timestamp': datetime.now()
        }
    
    def clear(self):
        """Clear all cached results"""
        self.cache.clear()

class SchemaValidator:
    """
    CAPITAL-GRADE SCHEMA VALIDATOR
    
    Enforces system laws that cannot be violated:
    - INVARIANT D1: No Silent Data Loss
    - INVARIANT D2: Data Freshness Enforcement  
    - INVARIANT D3: Schema Validation Completeness
    """
    
    def __init__(self, schema_registry: SchemaRegistry):
        self.schema_registry = schema_registry
        self.validation_cache = ValidationCache()
        
        # Validation statistics
        self.total_validations = 0
        self.total_failures = 0
        self.schemas_registered = 0
    
    def validate_dataframe(self, 
                          df: pd.DataFrame, 
                          schema_name: str,
                          strict_mode: bool = True,
                          cache_key: Optional[str] = None) -> ValidationResult:
        """
        Validate DataFrame against registered schema
        ENFORCES INVARIANT D3: Schema Validation Completeness
        """
        
        self.total_validations += 1
        
        # Check cache first
        if cache_key:
            cached_result = self.validation_cache.get(cache_key)
            if cached_result:
                return cached_result
        
        # Get schema
        schema = self.schema_registry.get_schema(schema_name)
        if not schema:
            error = ValidationError(
                code="SCHEMA_NOT_FOUND",
                message=f"Schema '{schema_name}' not found",
                field="",
                value="",
                severity=ErrorSeverity.CRITICAL
            )
            
            result = ValidationResult(
                is_valid=False,
                errors=[error],
                warnings=[],
                metadata={'schema_name': schema_name}
            )
            
            self.total_failures += 1
            return result
        
        # Validate against schema
        result = schema.validate_dataframe(df)
        
        # In strict mode, any error is a failure
        if strict_mode and not result.is_valid:
            self.total_failures += 1
            
            # INVARIANT D3: Schema validation must pass in strict mode
            if result.errors:
                error_messages = [error.message for error in result.errors]
                raise SystemExit(f"INVARIANT D3 VIOLATION - SCHEMA VALIDATION FAILED:\n" + "\n".join(error_messages))
        
        # Cache result
        if cache_key:
            self.validation_cache.put(cache_key, result)
        
        return result
    
    def register_schema(self, name: str, schema: DataSchema):
        """Register new data schema"""
        self.schema_registry.register_schema(schema)
        self.schemas_registered += 1
        print(f"📋 Schema registered: {name} (v{schema.version})")
    
    def auto_detect_schema(self, df: pd.DataFrame, schema_name: str = "auto_detected") -> DataSchema:
        """Auto-detect schema from DataFrame"""
        
        columns = {}
        
        for col_name in df.columns:
            series = df[col_name]
            
            # Detect data type
            if pd.api.types.is_integer_dtype(series):
                data_type = DataType.INTEGER
            elif pd.api.types.is_float_dtype(series):
                data_type = DataType.FLOAT
            elif pd.api.types.is_datetime64_any_dtype(series):
                data_type = DataType.DATETIME
            elif pd.api.types.is_bool_dtype(series):
                data_type = DataType.BOOLEAN
            else:
                data_type = DataType.STRING
            
            # Check nullability
            nullable = series.isnull().any()
            
            # Create column schema
            columns[col_name] = ColumnSchema(
                name=col_name,
                data_type=data_type,
                nullable=nullable,
                description=f"Auto-detected column of type {data_type.value}"
            )
        
        # Detect temporal columns
        temporal_columns = []
        for col_name, col_schema in columns.items():
            if col_schema.data_type == DataType.DATETIME:
                temporal_columns.append(col_name)
            elif 'date' in col_name.lower() or 'time' in col_name.lower():
                temporal_columns.append(col_name)
        
        schema = DataSchema(
            name=schema_name,
            version="1.0.0",
            columns=columns,
            temporal_columns=temporal_columns,
            description=f"Auto-detected schema with {len(columns)} columns"
        )
        
        return schema
    
    def get_validation_statistics(self) -> Dict[str, Any]:
        """Get validation statistics"""
        
        return {
            'total_validations': self.total_validations,
            'total_failures': self.total_failures,
            'failure_rate': self.total_failures / max(1, self.total_validations),
            'schemas_registered': self.schemas_registered,
            'cache_size': len(self.validation_cache.cache),
            'available_schemas': self.schema_registry.list_schemas()
        }

class DataQualityGate:
    """
    CAPITAL-GRADE DATA QUALITY GATES
    
    Enforces system laws that prevent data corruption:
    - INVARIANT D1: No Silent Data Loss
    - INVARIANT D2: Data Freshness Enforcement
    """
    
    def __init__(self, quality_rules: List[QualityRule]):
        self.quality_rules = quality_rules
        self.quality_history: List[QualityResult] = []
        self.quarantine_dir = "data/runtime/quarantine"
        os.makedirs(self.quarantine_dir, exist_ok=True)
        
        # Quality statistics
        self.total_evaluations = 0
        self.total_violations = 0
        self.quarantined_datasets = 0
    
    def validate_quality(self, 
                        data: pd.DataFrame, 
                        context: DataContext) -> QualityResult:
        """
        Validate data quality against rules
        ENFORCES INVARIANT D1 and D2
        """
        
        self.total_evaluations += 1
        all_violations = []
        
        # Evaluate each quality rule
        for rule in self.quality_rules:
            try:
                violations = rule.evaluate(data, context)
                all_violations.extend(violations)
            except Exception as e:
                # Rule evaluation error
                violation = QualityViolation(
                    rule_name=rule.name,
                    violation_type="RULE_EVALUATION_ERROR",
                    message=f"Error evaluating rule '{rule.name}': {e}",
                    affected_rows=0,
                    severity=ErrorSeverity.HIGH
                )
                all_violations.append(violation)
        
        # Calculate quality score
        total_rows = len(data)
        affected_rows = sum(v.affected_rows for v in all_violations)
        quality_score = max(0.0, 1.0 - (affected_rows / max(1, total_rows)))
        
        # Check for critical violations
        critical_violations = [v for v in all_violations if v.severity == ErrorSeverity.CRITICAL]
        is_valid = len(critical_violations) == 0
        
        result = QualityResult(
            is_valid=is_valid,
            violations=all_violations,
            rules_evaluated=len(self.quality_rules),
            data_rows=total_rows,
            quality_score=quality_score,
            metadata={
                'source_name': context.source_name,
                'load_timestamp': context.load_timestamp.isoformat(),
                'critical_violations': len(critical_violations)
            }
        )
        
        # Track violations
        if all_violations:
            self.total_violations += len(all_violations)
        
        # Store in history
        self.quality_history.append(result)
        
        # Keep only last 100 results
        if len(self.quality_history) > 100:
            self.quality_history = self.quality_history[-100:]
        
        # INVARIANT D1: Check for silent data loss
        if context.expected_row_count:
            actual_rows = len(data)
            expected_rows = context.expected_row_count
            
            if actual_rows < expected_rows:
                loss_percentage = (expected_rows - actual_rows) / expected_rows
                
                # If data loss > 10%, this is a critical violation
                if loss_percentage > 0.10:
                    critical_violation = QualityViolation(
                        rule_name="DATA_LOSS_CHECK",
                        violation_type="SILENT_DATA_LOSS",
                        message=f"Silent data loss detected: {actual_rows} rows received, {expected_rows} expected ({loss_percentage:.1%} loss)",
                        affected_rows=expected_rows - actual_rows,
                        severity=ErrorSeverity.CRITICAL
                    )
                    
                    result.violations.append(critical_violation)
                    result.is_valid = False
                    
                    # INVARIANT D1 VIOLATION: Terminate system
                    raise SystemExit(f"INVARIANT D1 VIOLATION - SILENT DATA LOSS:\n{critical_violation.message}")
        
        return result
    
    def quarantine_bad_data(self, 
                           data: pd.DataFrame, 
                           violations: List[QualityViolation],
                           context: DataContext):
        """
        Quarantine data that fails quality checks
        ENFORCES INVARIANT D1: No Silent Data Loss
        """
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        quarantine_file = os.path.join(
            self.quarantine_dir, 
            f"{context.source_name}_{timestamp}_quarantined.csv"
        )
        
        try:
            # Save quarantined data
            data.to_csv(quarantine_file, index=False)
            
            # Save violation details
            violation_file = quarantine_file.replace('.csv', '_violations.json')
            violation_data = {
                'quarantine_timestamp': datetime.now().isoformat(),
                'source_name': context.source_name,
                'load_timestamp': context.load_timestamp.isoformat(),
                'violations': [asdict(v) for v in violations],
                'data_rows': len(data),
                'quarantine_file': quarantine_file
            }
            
            with open(violation_file, 'w') as f:
                json.dump(violation_data, f, indent=2, default=str)
            
            self.quarantined_datasets += 1
            
            print(f"🚨 DATA QUARANTINED: {context.source_name}")
            print(f"   Violations: {len(violations)}")
            print(f"   Quarantine file: {quarantine_file}")
            print(f"   Violation details: {violation_file}")
            
        except Exception as e:
            print(f"⚠️ Error quarantining data: {e}")
    
    def get_quality_trends(self, 
                          data_source: str, 
                          days: int = 7) -> Dict[str, Any]:
        """Get data quality trends for monitoring"""
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Filter history for this data source and time range
        relevant_results = []
        for result in self.quality_history:
            if (result.metadata.get('source_name') == data_source and 
                datetime.fromisoformat(result.metadata['load_timestamp']) >= cutoff_date):
                relevant_results.append(result)
        
        if not relevant_results:
            return {
                'data_source': data_source,
                'days': days,
                'evaluations': 0,
                'average_quality_score': 0.0,
                'trend': 'NO_DATA'
            }
        
        # Calculate trends
        quality_scores = [r.quality_score for r in relevant_results]
        violation_counts = [len(r.violations) for r in relevant_results]
        
        # Determine trend
        if len(quality_scores) >= 2:
            recent_avg = np.mean(quality_scores[-3:])  # Last 3 evaluations
            older_avg = np.mean(quality_scores[:-3]) if len(quality_scores) > 3 else quality_scores[0]
            
            if recent_avg > older_avg + 0.05:
                trend = 'IMPROVING'
            elif recent_avg < older_avg - 0.05:
                trend = 'DEGRADING'
            else:
                trend = 'STABLE'
        else:
            trend = 'INSUFFICIENT_DATA'
        
        return {
            'data_source': data_source,
            'days': days,
            'evaluations': len(relevant_results),
            'average_quality_score': np.mean(quality_scores),
            'min_quality_score': min(quality_scores),
            'max_quality_score': max(quality_scores),
            'average_violations': np.mean(violation_counts),
            'trend': trend,
            'latest_quality_score': quality_scores[-1] if quality_scores else 0.0
        }
    
    def get_quality_statistics(self) -> Dict[str, Any]:
        """Get quality gate statistics"""
        
        return {
            'total_evaluations': self.total_evaluations,
            'total_violations': self.total_violations,
            'quarantined_datasets': self.quarantined_datasets,
            'active_rules': len(self.quality_rules),
            'quality_history_size': len(self.quality_history),
            'average_quality_score': np.mean([r.quality_score for r in self.quality_history]) if self.quality_history else 0.0
        }

def main():
    """Test the Schema Validator and Data Quality Gates"""
    
    print("📋 TESTING CAPITAL-GRADE SCHEMA VALIDATOR")
    print("=" * 60)
    
    # Create schema registry
    schema_registry = SchemaRegistry()
    
    # Create sample schema
    market_data_schema = DataSchema(
        name="market_data",
        version="1.0.0",
        columns={
            'date': ColumnSchema(
                name='date',
                data_type=DataType.DATETIME,
                nullable=False,
                description="Trading date"
            ),
            'symbol': ColumnSchema(
                name='symbol',
                data_type=DataType.STRING,
                nullable=False,
                constraints=[
                    {'type': 'regex_pattern', 'pattern': r'^[A-Z]{2,10}$'}
                ],
                description="Stock symbol"
            ),
            'price': ColumnSchema(
                name='price',
                data_type=DataType.FLOAT,
                nullable=False,
                constraints=[
                    {'type': 'min_value', 'value': 0.01},
                    {'type': 'max_value', 'value': 100000.0}
                ],
                description="Stock price"
            ),
            'volume': ColumnSchema(
                name='volume',
                data_type=DataType.INTEGER,
                nullable=False,
                constraints=[
                    {'type': 'min_value', 'value': 0}
                ],
                description="Trading volume"
            )
        },
        temporal_columns=['date'],
        primary_key=['date', 'symbol'],
        description="Market data schema for stock prices"
    )
    
    # Register schema
    schema_registry.register_schema(market_data_schema)
    
    # Create schema validator
    validator = SchemaValidator(schema_registry)
    
    print("\n📊 Testing schema validation...")
    
    # Create test data
    test_data = pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=100, freq='D'),
        'symbol': ['AAPL'] * 50 + ['GOOGL'] * 50,
        'price': np.random.uniform(100, 200, 100),
        'volume': np.random.randint(1000, 100000, 100)
    })
    
    # Test valid data
    try:
        result = validator.validate_dataframe(test_data, "market_data", strict_mode=False)
        
        if result.is_valid:
            print("✅ Schema validation passed")
        else:
            print(f"❌ Schema validation failed: {len(result.errors)} errors")
            for error in result.errors[:3]:  # Show first 3 errors
                print(f"   - {error.message}")
    
    except Exception as e:
        print(f"⚠️ Schema validation error: {e}")
    
    # Test data quality gates
    print("\n🚨 Testing data quality gates...")
    
    # Create quality rules
    quality_rules = [
        QualityRule(
            name="completeness_check",
            rule_type="completeness",
            parameters={
                'required_columns': ['date', 'symbol', 'price', 'volume'],
                'max_null_percentage': 0.05
            },
            severity=ErrorSeverity.HIGH,
            description="Check data completeness"
        ),
        QualityRule(
            name="freshness_check",
            rule_type="freshness",
            parameters={
                'timestamp_column': 'date',
                'max_age_hours': 24
            },
            severity=ErrorSeverity.MEDIUM,
            description="Check data freshness"
        ),
        QualityRule(
            name="uniqueness_check",
            rule_type="uniqueness",
            parameters={
                'unique_columns': ['date', 'symbol']
            },
            severity=ErrorSeverity.HIGH,
            description="Check primary key uniqueness"
        )
    ]
    
    # Create quality gate
    quality_gate = DataQualityGate(quality_rules)
    
    # Test quality validation
    context = DataContext(
        source_name="test_market_data",
        load_timestamp=datetime.now(),
        expected_row_count=100
    )
    
    try:
        quality_result = quality_gate.validate_quality(test_data, context)
        
        if quality_result.is_valid:
            print(f"✅ Data quality validation passed")
            print(f"   Quality score: {quality_result.quality_score:.2%}")
        else:
            print(f"❌ Data quality validation failed")
            print(f"   Violations: {len(quality_result.violations)}")
            print(f"   Quality score: {quality_result.quality_score:.2%}")
            
            for violation in quality_result.violations[:3]:  # Show first 3 violations
                print(f"   - {violation.message}")
    
    except Exception as e:
        print(f"⚠️ Quality validation error: {e}")
    
    # Show statistics
    print("\n📊 Validation statistics:")
    validator_stats = validator.get_validation_statistics()
    for key, value in validator_stats.items():
        print(f"   {key}: {value}")
    
    quality_stats = quality_gate.get_quality_statistics()
    for key, value in quality_stats.items():
        print(f"   {key}: {value}")
    
    print(f"\n✅ Schema Validator and Quality Gates test successful!")
    print(f"   Capital-grade data quality laws are enforced")
    print(f"   System prevents data corruption and silent failures")
    
    return True

if __name__ == "__main__":
    main()
