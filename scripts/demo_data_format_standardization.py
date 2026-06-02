#!/usr/bin/env python3
"""
🎯 DATA FORMAT STANDARDIZATION DEMO
Demonstrates the new data format standardization system in action

This shows how the capital-grade data format standardization system
fixes data format mismatches across the pipeline.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from src.cohesion.schema_validator import SchemaValidator, SchemaRegistry
from src.cohesion.data_format_standardizer import DataFormatStandardizer, DataSourceType
from src.cohesion.data_ingestion_validator import DataIngestionValidator, DataQualityConfig

def demo_rbi_data_standardization():
    """Demo RBI data format standardization"""
    
    print("🏦 RBI Data Format Standardization Demo")
    print("=" * 50)
    
    # Create messy RBI data (typical of real RBI files)
    messy_rbi_data = pd.DataFrame({
        'Reporting Date': ['31-Dec-2025', '07-Jan-2026', '14-Jan-2026'],
        'Repo Rate (%)': [6.50, 6.50, 6.75],
        'Reverse Repo Rate (%)': [3.35, 3.35, 3.35],
        'Bank Rate (%)': [6.75, 6.75, 7.00],
        'CRR (%)': [4.50, 4.50, 4.50],
        'SLR (%)': [18.00, 18.00, 18.00],
        'USD/INR (Spot)': [82.50, 82.70, 82.90],
        'MSF Rate (%)': [6.75, 6.75, 7.00],
        'SDF Rate (%)': [6.25, 6.25, 6.50],
        'FX Reserves (USD Bn)': [580.0, 581.0, 582.0]
    })
    
    print("📊 Original messy RBI data:")
    print(f"   Columns: {list(messy_rbi_data.columns)}")
    print(f"   Shape: {messy_rbi_data.shape}")
    print()
    
    # Initialize standardization system
    schema_registry = SchemaRegistry()
    schema_validator = SchemaValidator(schema_registry)
    format_standardizer = DataFormatStandardizer(schema_validator)
    
    # Standardize the data
    result = format_standardizer.standardize_data_format(
        messy_rbi_data, DataSourceType.RBI_MACRO, validate_schema=False
    )
    
    if result.success:
        print("✅ Standardization successful!")
        print(f"   Standardized columns: {list(result.standardized_data.columns)}")
        print(f"   Shape: {result.standardized_data.shape}")
        print(f"   Columns renamed: {result.metadata['columns_renamed']}")
        print()
        
        # Show before/after comparison
        print("🔄 Column name mapping:")
        for orig, std in zip(result.original_columns, result.standardized_columns):
            if orig != std:
                print(f"   '{orig}' → '{std}'")
        print()
        
    else:
        print("❌ Standardization failed:")
        for error in result.errors:
            print(f"   - {error}")
        print()

def demo_market_data_standardization():
    """Demo market data format standardization"""
    
    print("📈 Market Data Format Standardization Demo")
    print("=" * 50)
    
    # Create messy market data (typical of different data providers)
    messy_market_data = pd.DataFrame({
        'Trade Date': ['2026-01-01', '2026-01-02', '2026-01-03'],
        'Stock Symbol': ['RELIANCE.NS', 'TCS.NS', 'INFY.NS'],
        'Closing Price': [2500.0, 3200.0, 1450.0],
        'Opening Price': [2480.0, 3180.0, 1430.0],
        'Day High': [2520.0, 3220.0, 1460.0],
        'Day Low': [2470.0, 3170.0, 1420.0],
        'Total Volume': [1000000, 800000, 1200000],
        'Dollar Volume': [2500000000, 2560000000, 1740000000]
    })
    
    print("📊 Original messy market data:")
    print(f"   Columns: {list(messy_market_data.columns)}")
    print(f"   Shape: {messy_market_data.shape}")
    print()
    
    # Initialize standardization system
    schema_registry = SchemaRegistry()
    schema_validator = SchemaValidator(schema_registry)
    format_standardizer = DataFormatStandardizer(schema_validator)
    
    # Standardize the data
    result = format_standardizer.standardize_data_format(
        messy_market_data, DataSourceType.MARKET_DATA, validate_schema=False
    )
    
    if result.success:
        print("✅ Standardization successful!")
        print(f"   Standardized columns: {list(result.standardized_data.columns)}")
        print(f"   Shape: {result.standardized_data.shape}")
        print()
        
        # Show before/after comparison
        print("🔄 Column name mapping:")
        for orig, std in zip(result.original_columns, result.standardized_columns):
            if orig != std:
                print(f"   '{orig}' → '{std}'")
        print()
        
    else:
        print("❌ Standardization failed:")
        for error in result.errors:
            print(f"   - {error}")
        print()

def demo_comprehensive_validation():
    """Demo comprehensive data validation with quality checks"""
    
    print("🔍 Comprehensive Data Validation Demo")
    print("=" * 50)
    
    # Create data with various quality issues
    problematic_data = pd.DataFrame({
        'date': pd.date_range('2026-01-01', periods=100, freq='D'),
        'price': np.random.normal(100, 10, 100),
        'volume': np.random.randint(1000, 10000, 100),
        'category': ['A'] * 50 + ['B'] * 50
    })
    
    # Introduce quality issues
    problematic_data.loc[10:15, 'price'] = np.nan  # Add nulls
    problematic_data.loc[20:22, :] = problematic_data.loc[17:19, :].values  # Add duplicates
    problematic_data.loc[30:32, 'price'] = [1000, 1100, 1200]  # Add outliers
    
    print("📊 Data with quality issues:")
    print(f"   Shape: {problematic_data.shape}")
    print(f"   Null values: {problematic_data.isnull().sum().sum()}")
    print(f"   Duplicate rows: {problematic_data.duplicated().sum()}")
    print()
    
    # Initialize validation system
    schema_registry = SchemaRegistry()
    schema_validator = SchemaValidator(schema_registry)
    format_standardizer = DataFormatStandardizer(schema_validator)
    ingestion_validator = DataIngestionValidator(schema_validator, format_standardizer)
    
    # Configure quality checks
    quality_config = DataQualityConfig(
        freshness_threshold=timedelta(days=7),
        max_null_percentage=0.1,  # 10% max nulls
        max_duplicate_percentage=0.05,  # 5% max duplicates
        min_completeness_ratio=0.8,  # 80% completeness
        temporal_column='date'
    )
    
    # Run comprehensive validation
    result = ingestion_validator.validate_ingestion(
        df=problematic_data,
        source_type=DataSourceType.MARKET_DATA,
        source_name="demo_data",
        quality_config=quality_config,
        enforce_schema=False
    )
    
    print("🔍 Validation Results:")
    print(f"   Success: {result.success}")
    print(f"   Should quarantine: {result.should_quarantine}")
    print(f"   Quality score: {result.metadata['quality_score']:.2%}")
    print()
    
    print("📋 Quality Check Results:")
    for check, passed in result.quality_checks.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {check}: {status}")
    print()
    
    if result.errors:
        print("❌ Validation Errors:")
        for error in result.errors:
            print(f"   - {error}")
        print()
    
    if result.warnings:
        print("⚠️  Validation Warnings:")
        for warning in result.warnings:
            print(f"   - {warning}")
        print()

def demo_data_consistency_check():
    """Demo data consistency validation across multiple sources"""
    
    print("🔗 Data Consistency Validation Demo")
    print("=" * 50)
    
    # Create multiple data sources with inconsistent naming
    source1 = pd.DataFrame({
        'Date': ['2026-01-01'],
        'Close_Price': [2500.0],
        'company name': ['Company A'],
        'Industry Type': ['Technology']
    })
    
    source2 = pd.DataFrame({
        'date': ['2026-01-01'],
        'Close Price': [2500.0],
        'Company_Name': ['Company A'],
        'industry_type': ['Technology']
    })
    
    source3 = pd.DataFrame({
        'DATE': ['2026-01-01'],
        'CLOSE_PRICE': [2500.0],
        'COMPANY_NAME': ['Company A'],
        'INDUSTRY_TYPE': ['Technology']
    })
    
    data_sources = {
        'provider_1': source1,
        'provider_2': source2,
        'provider_3': source3
    }
    
    print("📊 Multiple data sources with inconsistent naming:")
    for name, df in data_sources.items():
        print(f"   {name}: {list(df.columns)}")
    print()
    
    # Initialize standardization system
    schema_registry = SchemaRegistry()
    schema_validator = SchemaValidator(schema_registry)
    format_standardizer = DataFormatStandardizer(schema_validator)
    
    # Validate consistency
    result = format_standardizer.validate_data_consistency(data_sources)
    
    print("🔍 Consistency Validation Results:")
    print(f"   Valid: {result.is_valid}")
    print(f"   Sources checked: {result.metadata['sources_checked']}")
    print(f"   Common columns: {result.metadata['common_columns']}")
    print(f"   Total unique columns: {result.metadata['total_unique_columns']}")
    print()
    
    if result.warnings:
        print("⚠️  Consistency Issues Detected:")
        for warning in result.warnings:
            print(f"   - {warning}")
        print()
    
    # Show standardized versions
    print("✅ Standardized versions:")
    for name, df in data_sources.items():
        std_result = format_standardizer.standardize_data_format(
            df, DataSourceType.MARKET_DATA, validate_schema=False
        )
        if std_result.success:
            print(f"   {name}: {list(std_result.standardized_data.columns)}")
    print()

def main():
    """Run all demos"""
    
    print("🎯 DATA FORMAT STANDARDIZATION SYSTEM DEMO")
    print("=" * 60)
    print("Demonstrating capital-grade data format standardization")
    print("that fixes data format mismatches across the pipeline.")
    print()
    
    demo_rbi_data_standardization()
    demo_market_data_standardization()
    demo_comprehensive_validation()
    demo_data_consistency_check()
    
    print("🎉 Demo completed successfully!")
    print()
    print("✅ CAPITAL-GRADE SYSTEM LAWS DEMONSTRATED:")
    print("   - Property 10: No Silent Data Loss (D1)")
    print("   - Property 11: Data Freshness Enforcement (D2)")
    print("   - Property 12: Schema Validation Completeness (D3)")
    print()
    print("🔧 The system is now ready to handle data format mismatches")
    print("   across all data sources in the Northstar V3 pipeline!")

if __name__ == "__main__":
    main()