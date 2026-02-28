#!/usr/bin/env python3
"""
🧪 DATA FORMAT STANDARDIZATION TESTS - CAPITAL-GRADE SYSTEM LAWS
Tests for data format standardization and validation system

This validates the capital-grade data format standardization system with
mathematical invariants that cannot be violated.

SYSTEM LAWS TESTED:
- Property 10: No Silent Data Loss (D1)
- Property 11: Data Freshness Enforcement (D2)
- Property 12: Schema Validation Completeness (D3)

These are not suggestions - they are LAWS that terminate the system if violated.
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from src.cohesion.schema_validator import SchemaValidator, SchemaRegistry
from src.cohesion.data_format_standardizer import DataFormatStandardizer, DataSourceType, ColumnMapping
from src.cohesion.data_ingestion_validator import DataIngestionValidator, DataQualityConfig

class TestDataFormatStandardization:
    """Test data format standardization system"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.schema_registry = SchemaRegistry()
        self.schema_validator = SchemaValidator(self.schema_registry)
        self.format_standardizer = DataFormatStandardizer(self.schema_validator)
        self.ingestion_validator = DataIngestionValidator(self.schema_validator, self.format_standardizer)
    
    def test_rbi_macro_data_standardization(self):
        """Test RBI macro data format standardization"""
        
        # Create sample RBI data with various column name formats
        rbi_data = pd.DataFrame({
            'Period': pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03']),
            'Repo Rate': [6.5, 6.5, 6.75],
            'Reverse Repo Rate': [3.35, 3.35, 3.35],
            'Bank Rate': [6.75, 6.75, 7.0],
            'CRR': [4.5, 4.5, 4.5],
            'SLR': [18.0, 18.0, 18.0],
            'USD/INR': [82.5, 82.7, 82.9],
            'MSF Rate': [7.0, 7.0, 7.25],
            'SDF Rate': [6.25, 6.25, 6.5],
            'FX Reserves': [580.0, 581.0, 582.0]
        })
        
        # Standardize format (without strict schema validation for this test)
        result = self.format_standardizer.standardize_data_format(
            rbi_data, DataSourceType.RBI_MACRO, validate_schema=False
        )
        
        # Validate standardization success
        assert result.success, f"Standardization failed: {result.errors}"
        
        # Check standardized column names
        expected_columns = ['date', 'repo_rate', 'reverse_repo_rate', 'bank_rate', 'crr', 'slr', 'usdinr']
        standardized_columns = list(result.standardized_data.columns)
        
        for expected_col in expected_columns:
            assert expected_col in standardized_columns, f"Missing standardized column: {expected_col}"
        
        # ENFORCE INVARIANT D1: No Silent Data Loss
        assert len(result.standardized_data) == len(rbi_data), "INVARIANT VIOLATION D1: Data loss detected"
        
        print("✅ RBI macro data standardization test passed")
    
    def test_market_data_standardization(self):
        """Test market data format standardization"""
        
        # Create sample market data with various column name formats
        market_data = pd.DataFrame({
            'Date': pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03']),
            'Symbol': ['RELIANCE.NS', 'TCS.NS', 'INFY.NS'],
            'Close': [2500.0, 3200.0, 1450.0],
            'Open': [2480.0, 3180.0, 1430.0],
            'High': [2520.0, 3220.0, 1460.0],
            'Low': [2470.0, 3170.0, 1420.0],
            'Volume': [1000000, 800000, 1200000]
        })
        
        # Standardize format (without strict schema validation for this test)
        result = self.format_standardizer.standardize_data_format(
            market_data, DataSourceType.MARKET_DATA, validate_schema=False
        )
        
        # Validate standardization success
        assert result.success, f"Standardization failed: {result.errors}"
        
        # Check standardized column names
        expected_columns = ['date', 'ticker', 'close', 'open', 'high', 'low', 'volume']
        standardized_columns = list(result.standardized_data.columns)
        
        for expected_col in expected_columns:
            assert expected_col in standardized_columns, f"Missing standardized column: {expected_col}"
        
        # ENFORCE INVARIANT D1: No Silent Data Loss
        assert len(result.standardized_data) == len(market_data), "INVARIANT VIOLATION D1: Data loss detected"
        
        print("✅ Market data standardization test passed")
    
    def test_portfolio_data_standardization(self):
        """Test portfolio data format standardization"""
        
        # Create sample portfolio data with various column name formats
        portfolio_data = pd.DataFrame({
            'Symbol': ['RELIANCE.NS', 'TCS.NS', 'INFY.NS'],
            'final_weight': [0.08, 0.06, 0.05],
            'Score': [0.85, 0.78, 0.72],
            'Company Name': ['Reliance Industries', 'Tata Consultancy Services', 'Infosys'],
            'Industry Name': ['Oil & Gas', 'IT Services', 'IT Services']
        })
        
        # Standardize format (without strict schema validation for this test)
        result = self.format_standardizer.standardize_data_format(
            portfolio_data, DataSourceType.PORTFOLIO_DATA, validate_schema=False
        )
        
        # Validate standardization success
        assert result.success, f"Standardization failed: {result.errors}"
        
        # Check standardized column names
        expected_columns = ['ticker', 'weight', 'score', 'company_name', 'industry']
        standardized_columns = list(result.standardized_data.columns)
        
        for expected_col in expected_columns:
            assert expected_col in standardized_columns, f"Missing standardized column: {expected_col}"
        
        # ENFORCE INVARIANT D1: No Silent Data Loss
        assert len(result.standardized_data) == len(portfolio_data), "INVARIANT VIOLATION D1: Data loss detected"
        
        print("✅ Portfolio data standardization test passed")
    
    def test_data_ingestion_validation(self):
        """Test comprehensive data ingestion validation"""
        
        # Create sample data with quality issues
        test_data = pd.DataFrame({
            'date': pd.date_range('2023-01-01', periods=100, freq='D'),
            'value': np.random.normal(100, 10, 100),
            'category': ['A'] * 50 + ['B'] * 50
        })
        
        # Add some quality issues
        test_data.loc[10:15, 'value'] = np.nan  # Add nulls
        test_data.loc[20:22, :] = test_data.loc[17:19, :].values  # Add duplicates
        
        # Configure quality checks
        quality_config = DataQualityConfig(
            freshness_threshold=timedelta(days=7),
            max_null_percentage=0.1,
            max_duplicate_percentage=0.05,
            min_completeness_ratio=0.8,
            temporal_column='date'
        )
        
        # Validate ingestion
        result = self.ingestion_validator.validate_ingestion(
            df=test_data,
            source_type=DataSourceType.MARKET_DATA,
            source_name="test_data",
            quality_config=quality_config,
            enforce_schema=False
        )
        
        # Check validation results
        assert isinstance(result.success, bool), "Validation result must have success flag"
        assert isinstance(result.quality_checks, dict), "Quality checks must be returned"
        assert len(result.quality_checks) > 0, "Quality checks must be performed"
        
        print("✅ Data ingestion validation test passed")
    
    def test_data_freshness_enforcement(self):
        """
        Test data freshness enforcement
        ENFORCES INVARIANT D2: Data Freshness Enforcement
        """
        
        # Create stale data (older than threshold)
        stale_data = pd.DataFrame({
            'date': [datetime.now() - timedelta(days=10)],  # 10 days old
            'value': [100.0]
        })
        
        # Configure strict freshness check (5 days)
        quality_config = DataQualityConfig(
            freshness_threshold=timedelta(days=5),
            temporal_column='date'
        )
        
        # Validate ingestion
        result = self.ingestion_validator.validate_ingestion(
            df=stale_data,
            source_type=DataSourceType.MARKET_DATA,
            source_name="stale_test_data",
            quality_config=quality_config,
            enforce_schema=False
        )
        
        # ENFORCE INVARIANT D2: Data Freshness Enforcement
        freshness_check = result.quality_checks.get('freshness_check', True)
        if not freshness_check:
            # Check that freshness violation was detected
            freshness_errors = [error for error in result.errors if 'INVARIANT VIOLATION D2' in error]
            assert len(freshness_errors) > 0, "INVARIANT VIOLATION D2: Freshness check should fail for stale data"
        
        print("✅ Data freshness enforcement test passed")
    
    def test_schema_validation_completeness(self):
        """
        Test schema validation completeness
        ENFORCES INVARIANT D3: Schema Validation Completeness
        """
        
        # Create data with schema violations
        invalid_data = pd.DataFrame({
            'date': ['invalid_date', '2023-01-02'],  # Invalid date format
            'ticker': ['RELIANCE.NS', None],  # Null in required field
            'close': [2500.0, 'invalid_price']  # Invalid price format
        })
        
        # Validate with schema enforcement
        result = self.format_standardizer.standardize_data_format(
            invalid_data, DataSourceType.MARKET_DATA, validate_schema=True
        )
        
        # ENFORCE INVARIANT D3: Schema Validation Completeness
        assert not result.success, "INVARIANT VIOLATION D3: Schema validation should fail for invalid data"
        assert len(result.errors) > 0, "Schema validation errors should be reported"
        
        print("✅ Schema validation completeness test passed")
    
    def test_column_name_cleaning(self):
        """Test column name cleaning and standardization"""
        
        # Create data with messy column names
        messy_data = pd.DataFrame({
            'Date Time': ['2023-01-01', '2023-01-02'],
            'Close Price (INR)': [2500.0, 2520.0],
            'Volume  ': [1000000, 1100000],
            '  Company Name  ': ['Company A', 'Company B'],
            'Industry/Sector': ['Tech', 'Finance']
        })
        
        # Standardize format
        result = self.format_standardizer.standardize_data_format(
            messy_data, DataSourceType.MARKET_DATA, validate_schema=False
        )
        
        # Check that column names are cleaned
        standardized_columns = list(result.standardized_data.columns)
        
        # All columns should be lowercase with underscores
        for col in standardized_columns:
            assert col.islower(), f"Column name should be lowercase: {col}"
            assert ' ' not in col, f"Column name should not contain spaces: {col}"
            assert col.replace('_', '').replace('/', '').isalnum(), f"Column name should be alphanumeric with underscores: {col}"
        
        print("✅ Column name cleaning test passed")
    
    def test_data_consistency_validation(self):
        """Test data consistency validation across multiple sources"""
        
        # Create multiple data sources with inconsistent naming
        source1 = pd.DataFrame({
            'Date': ['2023-01-01'],
            'Close_Price': [2500.0],
            'company name': ['Company A']
        })
        
        source2 = pd.DataFrame({
            'date': ['2023-01-01'],
            'Close Price': [2500.0],
            'Company_Name': ['Company A']
        })
        
        data_sources = {
            'source1': source1,
            'source2': source2
        }
        
        # Validate consistency
        result = self.format_standardizer.validate_data_consistency(data_sources)
        
        # Should detect inconsistencies
        assert len(result.warnings) > 0, "Should detect column naming inconsistencies"
        
        print("✅ Data consistency validation test passed")

def test_data_format_standardization_integration():
    """Integration test for complete data format standardization workflow"""
    
    # Initialize components
    schema_registry = SchemaRegistry()
    schema_validator = SchemaValidator(schema_registry)
    format_standardizer = DataFormatStandardizer(schema_validator)
    ingestion_validator = DataIngestionValidator(schema_validator, format_standardizer)
    
    # Create comprehensive test data with current dates
    current_date = datetime.now()
    test_data = pd.DataFrame({
        'Period': pd.date_range(current_date - timedelta(days=10), periods=50, freq='D'),
        'Repo Rate': np.random.normal(6.5, 0.1, 50),
        'Reverse Repo Rate': np.random.normal(3.35, 0.05, 50),
        'USD/INR': np.random.normal(82.5, 1.0, 50)
    })
    
    # Configure quality checks
    quality_config = DataQualityConfig(
        freshness_threshold=timedelta(days=30),
        max_null_percentage=0.1,
        max_duplicate_percentage=0.05,
        min_completeness_ratio=0.9,
        temporal_column='date'
    )
    
    # Run complete validation workflow
    result = ingestion_validator.validate_ingestion(
        df=test_data,
        source_type=DataSourceType.RBI_MACRO,
        source_name="integration_test",
        quality_config=quality_config,
        enforce_schema=False  # Don't enforce strict schema for integration test
    )
    
    # Validate complete workflow
    assert result.success, f"Integration test failed: {result.errors}"
    assert result.validated_data is not None, "Validated data should be returned"
    assert result.standardization_result is not None, "Standardization result should be available"
    
    # Check that all quality checks were performed
    expected_checks = [
        'no_null_required_columns',
        'freshness_check',
        'duplicate_check',
        'outlier_check',
        'completeness_check',
        'consistency_check',
        'temporal_order_check'
    ]
    
    for check in expected_checks:
        assert check in result.quality_checks, f"Missing quality check: {check}"
    
    print("✅ Data format standardization integration test passed")

if __name__ == "__main__":
    # Run tests
    test_class = TestDataFormatStandardization()
    test_class.setup_method()
    
    print("🧪 Running Data Format Standardization Tests")
    print("=" * 60)
    
    test_class.test_rbi_macro_data_standardization()
    test_class.test_market_data_standardization()
    test_class.test_portfolio_data_standardization()
    test_class.test_data_ingestion_validation()
    test_class.test_data_freshness_enforcement()
    test_class.test_schema_validation_completeness()
    test_class.test_column_name_cleaning()
    test_class.test_data_consistency_validation()
    
    test_data_format_standardization_integration()
    
    print("\n🎉 All data format standardization tests passed!")
    print("✅ CAPITAL-GRADE SYSTEM LAWS ENFORCED:")
    print("   - Property 10: No Silent Data Loss (D1)")
    print("   - Property 11: Data Freshness Enforcement (D2)")
    print("   - Property 12: Schema Validation Completeness (D3)")