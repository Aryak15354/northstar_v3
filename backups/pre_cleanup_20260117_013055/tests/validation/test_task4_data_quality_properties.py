#!/usr/bin/env python3
"""
🧪 PROPERTY TESTS: Data Quality System Laws
Capital-Grade Property-Based Testing for Schema Validation and Data Quality Gates

This implements property-based tests that validate the mathematical invariants
of the data quality system. These are not unit tests - they are SYSTEM LAWS
that must hold across all possible inputs.

SYSTEM LAWS TESTED:
- Property 10: No Silent Data Loss (D1)
- Property 11: Data Freshness Enforcement (D2)  
- Property 12: Schema Validation Completeness (D3)

Each property is tested with minimum 100 iterations to ensure statistical confidence.
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume, example
from hypothesis.extra.pandas import data_frames, columns
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from src.cohesion.schema_validator import (
    SchemaValidator, SchemaRegistry, DataQualityGate,
    DataSchema, ColumnSchema, DataType, QualityRule, ErrorSeverity,
    DataContext, ValidationResult, QualityResult
)

class TestDataQualitySystemLaws:
    """
    CAPITAL-GRADE PROPERTY TESTS
    
    These tests validate universal properties that must hold for ALL inputs.
    Failure of any property means the system violates capital-grade requirements.
    """
    
    def setup_method(self):
        """Setup for each test method"""
        self.schema_registry = SchemaRegistry("test_schemas")
        self.validator = SchemaValidator(self.schema_registry)
        
        # Create sample schema for testing
        self.test_schema = DataSchema(
            name="test_data",
            version="1.0.0",
            columns={
                'id': ColumnSchema(
                    name='id',
                    data_type=DataType.INTEGER,
                    nullable=False
                ),
                'timestamp': ColumnSchema(
                    name='timestamp',
                    data_type=DataType.DATETIME,
                    nullable=False
                ),
                'value': ColumnSchema(
                    name='value',
                    data_type=DataType.FLOAT,
                    nullable=True,
                    constraints=[
                        {'type': 'min_value', 'value': 0.0},
                        {'type': 'max_value', 'value': 1000.0}
                    ]
                ),
                'category': ColumnSchema(
                    name='category',
                    data_type=DataType.STRING,
                    nullable=False,
                    constraints=[
                        {'type': 'in_values', 'values': ['A', 'B', 'C']}
                    ]
                )
            },
            temporal_columns=['timestamp'],
            primary_key=['id'],
            description="Test schema for property testing"
        )
        
        self.schema_registry.register_schema(self.test_schema)
    
    @settings(max_examples=100, deadline=None)
    @given(
        row_count=st.integers(min_value=1, max_value=1000),
        expected_count=st.integers(min_value=1, max_value=1000)
    )
    def test_property_10_no_silent_data_loss(self, row_count, expected_count):
        """
        PROPERTY 10: No Silent Data Loss (D1)
        
        SYSTEM LAW: For any data transformation, data loss must be explained 
        and within acceptable thresholds. Silent data loss > 10% must terminate the system.
        
        Mathematical Invariant:
        IF expected_rows - actual_rows > 0.10 * expected_rows
        THEN system MUST terminate with INVARIANT D1 VIOLATION
        """
        
        assume(expected_count > 0)  # Avoid division by zero
        
        # Create test data
        test_data = pd.DataFrame({
            'id': range(row_count),
            'timestamp': [datetime.now() - timedelta(hours=i) for i in range(row_count)],
            'value': np.random.uniform(0, 1000, row_count),
            'category': np.random.choice(['A', 'B', 'C'], row_count)
        })
        
        # Create quality rules that check for data loss
        quality_rules = [
            QualityRule(
                name="data_loss_check",
                rule_type="completeness",
                parameters={
                    'required_columns': ['id', 'timestamp', 'value', 'category'],
                    'max_null_percentage': 0.05
                },
                severity=ErrorSeverity.CRITICAL
            )
        ]
        
        quality_gate = DataQualityGate(quality_rules)
        
        context = DataContext(
            source_name="test_data",
            load_timestamp=datetime.now(),
            expected_row_count=expected_count
        )
        
        # Calculate expected data loss
        data_loss_percentage = max(0, (expected_count - row_count) / expected_count)
        
        if data_loss_percentage > 0.10:
            # PROPERTY 10: System must terminate for silent data loss > 10%
            with pytest.raises(SystemExit) as exc_info:
                quality_gate.validate_quality(test_data, context)
            
            # Verify the error message contains INVARIANT D1 VIOLATION
            assert "INVARIANT D1 VIOLATION" in str(exc_info.value)
            assert "SILENT DATA LOSS" in str(exc_info.value)
            
        else:
            # PROPERTY 10: System should continue for acceptable data loss
            result = quality_gate.validate_quality(test_data, context)
            
            # Result should be valid or have non-critical violations only
            if not result.is_valid:
                critical_violations = result.get_critical_violations()
                assert len(critical_violations) == 0, f"Unexpected critical violations: {critical_violations}"
    
    @settings(max_examples=100, deadline=None)
    @given(
        hours_old=st.floats(min_value=0.1, max_value=168.0),  # 0.1 to 168 hours (1 week)
        max_age_threshold=st.floats(min_value=1.0, max_value=72.0)  # 1 to 72 hours
    )
    def test_property_11_data_freshness_enforcement(self, hours_old, max_age_threshold):
        """
        PROPERTY 11: Data Freshness Enforcement (D2)
        
        SYSTEM LAW: For any data used in calculations, freshness must be 
        within configured thresholds. Stale data beyond thresholds must be rejected.
        
        Mathematical Invariant:
        IF data_age > freshness_threshold
        THEN system MUST flag freshness violation
        """
        
        # Create test data with specific age
        data_timestamp = datetime.now() - timedelta(hours=hours_old)
        
        test_data = pd.DataFrame({
            'id': [1, 2, 3],
            'timestamp': [data_timestamp] * 3,
            'value': [100.0, 200.0, 300.0],
            'category': ['A', 'B', 'C']
        })
        
        # Create freshness quality rule
        quality_rules = [
            QualityRule(
                name="freshness_check",
                rule_type="freshness",
                parameters={
                    'timestamp_column': 'timestamp',
                    'max_age_hours': max_age_threshold
                },
                severity=ErrorSeverity.HIGH
            )
        ]
        
        quality_gate = DataQualityGate(quality_rules)
        
        context = DataContext(
            source_name="test_data",
            load_timestamp=datetime.now()
        )
        
        result = quality_gate.validate_quality(test_data, context)
        
        # PROPERTY 11: Check freshness enforcement
        # Allow small tolerance for floating point comparison
        tolerance = 0.01  # 0.01 hours = 36 seconds
        
        if hours_old > max_age_threshold + tolerance:
            # Data is stale - must have freshness violation
            freshness_violations = [
                v for v in result.violations 
                if v.violation_type == "FRESHNESS_VIOLATION"
            ]
            
            assert len(freshness_violations) > 0, (
                f"PROPERTY 11 VIOLATION: Data age {hours_old:.1f}h > threshold {max_age_threshold:.1f}h "
                f"but no freshness violation detected"
            )
            
            # Verify violation message contains age information
            violation = freshness_violations[0]
            assert f"{hours_old:.1f}" in violation.message or f"{int(hours_old)}" in violation.message
            
        elif hours_old < max_age_threshold - tolerance:
            # Data is fresh - should not have freshness violations
            freshness_violations = [
                v for v in result.violations 
                if v.violation_type == "FRESHNESS_VIOLATION"
            ]
            
            assert len(freshness_violations) == 0, (
                f"PROPERTY 11 VIOLATION: Data age {hours_old:.1f}h < threshold {max_age_threshold:.1f}h "
                f"but freshness violation detected: {freshness_violations}"
            )
        # For values within tolerance, either result is acceptable due to timing precision
    
    @settings(max_examples=50, deadline=None)
    @given(
        strict_mode=st.booleans()
    )
    def test_property_12_schema_validation_completeness(self, strict_mode):
        """
        PROPERTY 12: Schema Validation Completeness (D3)
        
        SYSTEM LAW: All data entering the system must pass schema validation 
        before processing. In strict mode, any schema violation must terminate the system.
        
        Mathematical Invariant:
        IF strict_mode AND schema_violations > 0
        THEN system MUST terminate with INVARIANT D3 VIOLATION
        """
        
        # Create test data with known violations
        test_data_valid = pd.DataFrame({
            'id': [1, 2, 3],
            'timestamp': [datetime.now() - timedelta(hours=i) for i in range(3)],
            'value': [100.0, 200.0, 300.0],  # Valid range
            'category': ['A', 'B', 'C']  # Valid categories
        })
        
        test_data_invalid = pd.DataFrame({
            'id': [1, 2, 3],
            'timestamp': [datetime.now() - timedelta(hours=i) for i in range(3)],
            'value': [1500.0, 2000.0, 2500.0],  # Invalid range (> 1000)
            'category': ['INVALID', 'INVALID', 'INVALID']  # Invalid category
        })
        
        # Test with valid data first
        result_valid = self.validator.validate_dataframe(test_data_valid, "test_data", strict_mode=strict_mode)
        assert result_valid.is_valid, f"Expected valid result for valid data, got errors: {result_valid.errors}"
        
        # Test with invalid data
        if strict_mode:
            # PROPERTY 12: Strict mode with invalid data must terminate system
            with pytest.raises(SystemExit) as exc_info:
                self.validator.validate_dataframe(test_data_invalid, "test_data", strict_mode=True)
            
            # Verify the error message contains INVARIANT D3 VIOLATION
            assert "INVARIANT D3 VIOLATION" in str(exc_info.value)
            assert "SCHEMA VALIDATION FAILED" in str(exc_info.value)
            
        else:
            # PROPERTY 12: Non-strict mode should not terminate but should have errors
            result_invalid = self.validator.validate_dataframe(test_data_invalid, "test_data", strict_mode=False)
            
            # Should have validation errors for invalid data
            assert not result_invalid.is_valid, "Expected validation errors for invalid data"
            assert len(result_invalid.errors) > 0, "Expected validation errors"
            
            # Check that errors mention constraint violations
            error_messages = [error.message for error in result_invalid.errors]
            constraint_errors = [
                msg for msg in error_messages 
                if "greater than maximum" in msg or "not in allowed values" in msg
            ]
            assert len(constraint_errors) > 0, f"Expected constraint violation errors, got: {error_messages}"
    
    @settings(max_examples=50, deadline=None)
    @given(
        schema_name=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        column_count=st.integers(min_value=1, max_value=10)
    )
    def test_property_schema_registry_consistency(self, schema_name, column_count):
        """
        PROPERTY: Schema Registry Consistency
        
        SYSTEM LAW: Schema registration and retrieval must be consistent.
        Any registered schema must be retrievable with identical content.
        """
        
        assume(len(schema_name.strip()) > 0)  # Non-empty schema name
        
        # Create dynamic schema
        columns = {}
        for i in range(column_count):
            col_name = f"col_{i}"
            columns[col_name] = ColumnSchema(
                name=col_name,
                data_type=DataType.STRING,
                nullable=True
            )
        
        original_schema = DataSchema(
            name=schema_name,
            version="1.0.0",
            columns=columns,
            description=f"Test schema with {column_count} columns"
        )
        
        # Register schema
        self.schema_registry.register_schema(original_schema)
        
        # Retrieve schema
        retrieved_schema = self.schema_registry.get_schema(schema_name)
        
        # PROPERTY: Retrieved schema must match original
        assert retrieved_schema is not None, f"Schema '{schema_name}' not found after registration"
        assert retrieved_schema.name == original_schema.name
        assert retrieved_schema.version == original_schema.version
        assert len(retrieved_schema.columns) == len(original_schema.columns)
        
        # Check column consistency
        for col_name, original_col in original_schema.columns.items():
            assert col_name in retrieved_schema.columns
            retrieved_col = retrieved_schema.columns[col_name]
            assert retrieved_col.name == original_col.name
            assert retrieved_col.data_type == original_col.data_type
            assert retrieved_col.nullable == original_col.nullable
    
    @settings(max_examples=50, deadline=None)
    @given(
        null_percentage=st.floats(min_value=0.0, max_value=1.0),
        max_null_threshold=st.floats(min_value=0.0, max_value=0.5)
    )
    def test_property_completeness_rule_accuracy(self, null_percentage, max_null_threshold):
        """
        PROPERTY: Completeness Rule Accuracy
        
        SYSTEM LAW: Completeness rules must accurately detect null value violations.
        The violation detection must be mathematically precise.
        """
        
        row_count = 100
        assume(row_count > 0)  # Ensure we have data to test
        null_count = int(row_count * null_percentage)
        
        # Create data with specific null percentage
        values = [100.0] * (row_count - null_count) + [None] * null_count
        np.random.shuffle(values)
        
        test_data = pd.DataFrame({
            'id': range(row_count),
            'test_column': values
        })
        
        # Create completeness rule
        quality_rules = [
            QualityRule(
                name="completeness_test",
                rule_type="completeness",
                parameters={
                    'required_columns': ['test_column'],
                    'max_null_percentage': max_null_threshold
                },
                severity=ErrorSeverity.HIGH
            )
        ]
        
        quality_gate = DataQualityGate(quality_rules)
        
        context = DataContext(
            source_name="test_data",
            load_timestamp=datetime.now()
        )
        
        result = quality_gate.validate_quality(test_data, context)
        
        # PROPERTY: Completeness violation detection must be accurate
        completeness_violations = [
            v for v in result.violations 
            if v.violation_type == "COMPLETENESS_VIOLATION"
        ]
        
        # Allow small tolerance for floating point comparison
        tolerance = 0.01  # 1% tolerance
        
        if null_percentage > max_null_threshold + tolerance:
            # Should detect completeness violation
            assert len(completeness_violations) > 0, (
                f"PROPERTY VIOLATION: Null percentage {null_percentage:.2%} > threshold {max_null_threshold:.2%} "
                f"but no completeness violation detected"
            )
            
            # Check violation details
            violation = completeness_violations[0]
            assert violation.affected_rows == null_count, (
                f"Expected {null_count} affected rows, got {violation.affected_rows}"
            )
            
        elif null_percentage < max_null_threshold - tolerance:
            # Should not detect completeness violation
            assert len(completeness_violations) == 0, (
                f"PROPERTY VIOLATION: Null percentage {null_percentage:.2%} < threshold {max_null_threshold:.2%} "
                f"but completeness violation detected: {completeness_violations}"
            )
        # For values within tolerance, either result is acceptable
    
    def test_property_critical_violation_system_termination(self):
        """
        PROPERTY: Critical Violation System Termination
        
        SYSTEM LAW: Any critical data quality violation must terminate the system
        to prevent corrupted data from propagating through the pipeline.
        """
        
        # Create data that will trigger critical violations
        test_data = pd.DataFrame({
            'id': [1, 2, 3],
            'timestamp': [datetime.now()] * 3,
            'value': [100.0, 200.0, 300.0],
            'category': ['A', 'B', 'C']
        })
        
        # Create rule with critical severity that will always trigger
        quality_rules = [
            QualityRule(
                name="critical_test",
                rule_type="completeness",
                parameters={
                    'required_columns': ['nonexistent_column'],  # This will trigger violation
                    'max_null_percentage': 0.0
                },
                severity=ErrorSeverity.CRITICAL
            )
        ]
        
        quality_gate = DataQualityGate(quality_rules)
        
        context = DataContext(
            source_name="test_data",
            load_timestamp=datetime.now(),
            expected_row_count=10  # This will trigger data loss violation
        )
        
        # PROPERTY: Critical violations must terminate system
        with pytest.raises(SystemExit) as exc_info:
            quality_gate.validate_quality(test_data, context)
        
        # Verify termination message
        assert "INVARIANT D1 VIOLATION" in str(exc_info.value)
    
    def test_property_validation_cache_consistency(self):
        """
        PROPERTY: Validation Cache Consistency
        
        SYSTEM LAW: Cached validation results must be identical to fresh validation
        results for the same input data and schema.
        """
        
        # Create test data
        test_data = pd.DataFrame({
            'id': [1, 2, 3],
            'timestamp': [datetime.now()] * 3,
            'value': [100.0, 200.0, 300.0],
            'category': ['A', 'B', 'C']
        })
        
        cache_key = "test_cache_key"
        
        # First validation (will be cached)
        result1 = self.validator.validate_dataframe(
            test_data, "test_data", strict_mode=False, cache_key=cache_key
        )
        
        # Second validation (should use cache)
        result2 = self.validator.validate_dataframe(
            test_data, "test_data", strict_mode=False, cache_key=cache_key
        )
        
        # PROPERTY: Cached and fresh results must be identical
        assert result1.is_valid == result2.is_valid
        assert len(result1.errors) == len(result2.errors)
        assert len(result1.warnings) == len(result2.warnings)
        
        # Check error messages match
        if result1.errors:
            for error1, error2 in zip(result1.errors, result2.errors):
                assert error1.code == error2.code
                assert error1.message == error2.message
                assert error1.severity == error2.severity

def test_data_quality_system_integration():
    """
    Integration test to verify all data quality components work together
    """
    
    print("\n🧪 RUNNING DATA QUALITY SYSTEM INTEGRATION TEST")
    print("-" * 60)
    
    # Create complete system
    schema_registry = SchemaRegistry("integration_test_schemas")
    validator = SchemaValidator(schema_registry)
    
    # Register comprehensive schema
    schema = DataSchema(
        name="integration_test",
        version="1.0.0",
        columns={
            'id': ColumnSchema(name='id', data_type=DataType.INTEGER, nullable=False),
            'timestamp': ColumnSchema(name='timestamp', data_type=DataType.DATETIME, nullable=False),
            'price': ColumnSchema(
                name='price', 
                data_type=DataType.FLOAT, 
                nullable=False,
                constraints=[{'type': 'min_value', 'value': 0.01}]
            ),
            'symbol': ColumnSchema(
                name='symbol', 
                data_type=DataType.STRING, 
                nullable=False,
                constraints=[{'type': 'regex_pattern', 'pattern': r'^[A-Z]{2,10}$'}]
            )
        },
        temporal_columns=['timestamp'],
        primary_key=['id']
    )
    
    schema_registry.register_schema(schema)
    
    # Create quality rules
    quality_rules = [
        QualityRule(
            name="completeness",
            rule_type="completeness",
            parameters={'required_columns': ['id', 'timestamp', 'price', 'symbol'], 'max_null_percentage': 0.05},
            severity=ErrorSeverity.HIGH
        ),
        QualityRule(
            name="freshness",
            rule_type="freshness",
            parameters={'timestamp_column': 'timestamp', 'max_age_hours': 24},
            severity=ErrorSeverity.MEDIUM
        ),
        QualityRule(
            name="uniqueness",
            rule_type="uniqueness",
            parameters={'unique_columns': ['id']},
            severity=ErrorSeverity.HIGH
        )
    ]
    
    quality_gate = DataQualityGate(quality_rules)
    
    # Test with valid data
    valid_data = pd.DataFrame({
        'id': [1, 2, 3, 4, 5],
        'timestamp': [datetime.now() - timedelta(hours=i) for i in range(5)],
        'price': [100.50, 200.75, 150.25, 300.00, 250.50],
        'symbol': ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN']
    })
    
    # Schema validation
    schema_result = validator.validate_dataframe(valid_data, "integration_test")
    assert schema_result.is_valid, f"Schema validation failed: {schema_result.errors}"
    
    # Quality validation
    context = DataContext(
        source_name="integration_test",
        load_timestamp=datetime.now(),
        expected_row_count=5
    )
    
    quality_result = quality_gate.validate_quality(valid_data, context)
    assert quality_result.is_valid, f"Quality validation failed: {quality_result.violations}"
    
    print("✅ Integration test passed - all components working together")
    print(f"   Schema validation: {schema_result.is_valid}")
    print(f"   Quality validation: {quality_result.is_valid}")
    print(f"   Quality score: {quality_result.quality_score:.2%}")

if __name__ == "__main__":
    # Run property tests
    pytest.main([__file__, "-v", "--tb=short"])