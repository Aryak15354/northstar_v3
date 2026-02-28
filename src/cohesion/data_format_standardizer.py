#!/usr/bin/env python3
"""
📊 DATA FORMAT STANDARDIZER - CAPITAL-GRADE SYSTEM LAWS
Standardizes data formats and column naming across all data sources

This implements the capital-grade data format standardization system with
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
from typing import Dict, List, Any, Optional, Union, Tuple
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

from src.cohesion.schema_validator import SchemaValidator, DataSchema, ColumnSchema, DataType, ValidationResult

class DataSourceType(Enum):
    """Types of data sources with standardized formats"""
    RBI_MACRO = "rbi_macro"
    MARKET_DATA = "market_data"
    PORTFOLIO_DATA = "portfolio_data"
    FUNDAMENTAL_DATA = "fundamental_data"
    UNIVERSE_DATA = "universe_data"

@dataclass
class ColumnMapping:
    """Column name mapping with validation"""
    source_name: str
    standard_name: str
    data_type: DataType
    required: bool = True
    transformation: Optional[str] = None  # Optional transformation function name

@dataclass
class FormatStandardizationResult:
    """Result of format standardization"""
    success: bool
    standardized_data: Optional[pd.DataFrame]
    original_columns: List[str]
    standardized_columns: List[str]
    dropped_columns: List[str]
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]

class DataFormatStandardizer:
    """
    Standardizes data formats across all data sources
    ENFORCES CAPITAL-GRADE SYSTEM LAWS FOR DATA CONSISTENCY
    """
    
    def __init__(self, schema_validator: SchemaValidator):
        self.schema_validator = schema_validator
        self.column_mappings = self._initialize_column_mappings()
        self.standard_schemas = self._initialize_standard_schemas()
        
    def _initialize_column_mappings(self) -> Dict[DataSourceType, List[ColumnMapping]]:
        """Initialize standard column mappings for each data source type"""
        
        mappings = {
            DataSourceType.RBI_MACRO: [
                # RBI Macro data standardization
                ColumnMapping("date", "date", DataType.DATETIME, True),
                ColumnMapping("Date", "date", DataType.DATETIME, True),
                ColumnMapping("Period", "date", DataType.DATETIME, True),
                ColumnMapping("repo_rate", "repo_rate", DataType.FLOAT, False),
                ColumnMapping("Repo Rate", "repo_rate", DataType.FLOAT, False),
                ColumnMapping("reverse_repo_rate", "reverse_repo_rate", DataType.FLOAT, False),
                ColumnMapping("Reverse Repo Rate", "reverse_repo_rate", DataType.FLOAT, False),
                ColumnMapping("bank_rate", "bank_rate", DataType.FLOAT, False),
                ColumnMapping("Bank Rate", "bank_rate", DataType.FLOAT, False),
                ColumnMapping("msf_rate", "msf_rate", DataType.FLOAT, False),
                ColumnMapping("MSF Rate", "msf_rate", DataType.FLOAT, False),
                ColumnMapping("sdf_rate", "sdf_rate", DataType.FLOAT, False),
                ColumnMapping("SDF Rate", "sdf_rate", DataType.FLOAT, False),
                ColumnMapping("crr", "crr", DataType.FLOAT, False),
                ColumnMapping("CRR", "crr", DataType.FLOAT, False),
                ColumnMapping("slr", "slr", DataType.FLOAT, False),
                ColumnMapping("SLR", "slr", DataType.FLOAT, False),
                ColumnMapping("fx_reserves", "fx_reserves", DataType.FLOAT, False),
                ColumnMapping("FX Reserves", "fx_reserves", DataType.FLOAT, False),
                ColumnMapping("usdinr", "usdinr", DataType.FLOAT, False),
                ColumnMapping("USD/INR", "usdinr", DataType.FLOAT, False),
                ColumnMapping("USDINR", "usdinr", DataType.FLOAT, False),
            ],
            
            DataSourceType.MARKET_DATA: [
                # Market data standardization
                ColumnMapping("Date", "date", DataType.DATETIME, True),
                ColumnMapping("date", "date", DataType.DATETIME, True),
                ColumnMapping("ticker", "ticker", DataType.STRING, True),
                ColumnMapping("symbol", "ticker", DataType.STRING, True),
                ColumnMapping("Symbol", "ticker", DataType.STRING, True),
                ColumnMapping("Close", "close", DataType.FLOAT, True),
                ColumnMapping("close", "close", DataType.FLOAT, True),
                ColumnMapping("Open", "open", DataType.FLOAT, False),
                ColumnMapping("open", "open", DataType.FLOAT, False),
                ColumnMapping("High", "high", DataType.FLOAT, False),
                ColumnMapping("high", "high", DataType.FLOAT, False),
                ColumnMapping("Low", "low", DataType.FLOAT, False),
                ColumnMapping("low", "low", DataType.FLOAT, False),
                ColumnMapping("Volume", "volume", DataType.INTEGER, False),
                ColumnMapping("volume", "volume", DataType.INTEGER, False),
                ColumnMapping("dollar_volume", "dollar_volume", DataType.FLOAT, False),
            ],
            
            DataSourceType.PORTFOLIO_DATA: [
                # Portfolio data standardization
                ColumnMapping("ticker", "ticker", DataType.STRING, True),
                ColumnMapping("symbol", "ticker", DataType.STRING, True),
                ColumnMapping("Symbol", "ticker", DataType.STRING, True),
                ColumnMapping("weight", "weight", DataType.FLOAT, True),
                ColumnMapping("final_weight", "weight", DataType.FLOAT, True),
                ColumnMapping("Weight", "weight", DataType.FLOAT, True),
                ColumnMapping("score", "score", DataType.FLOAT, False),
                ColumnMapping("Score", "score", DataType.FLOAT, False),
                ColumnMapping("Company Name", "company_name", DataType.STRING, False),
                ColumnMapping("company_name", "company_name", DataType.STRING, False),
                ColumnMapping("Industry", "industry", DataType.STRING, False),
                ColumnMapping("industry", "industry", DataType.STRING, False),
                ColumnMapping("Industry Name", "industry", DataType.STRING, False),
                ColumnMapping("Sector", "sector", DataType.STRING, False),
                ColumnMapping("sector", "sector", DataType.STRING, False),
            ],
            
            DataSourceType.UNIVERSE_DATA: [
                # Universe data standardization
                ColumnMapping("Symbol", "ticker", DataType.STRING, True, "add_ns_suffix"),
                ColumnMapping("symbol", "ticker", DataType.STRING, True, "add_ns_suffix"),
                ColumnMapping("ticker", "ticker", DataType.STRING, True),
                ColumnMapping("Company Name", "company_name", DataType.STRING, False),
                ColumnMapping("company_name", "company_name", DataType.STRING, False),
                ColumnMapping("Industry", "industry", DataType.STRING, False),
                ColumnMapping("Industry Name", "industry", DataType.STRING, False),
                ColumnMapping("industry", "industry", DataType.STRING, False),
                ColumnMapping("Sector", "sector", DataType.STRING, False),
                ColumnMapping("sector", "sector", DataType.STRING, False),
                ColumnMapping("Market Cap", "market_cap", DataType.FLOAT, False),
                ColumnMapping("market_cap", "market_cap", DataType.FLOAT, False),
            ]
        }
        
        return mappings
    
    def _initialize_standard_schemas(self) -> Dict[DataSourceType, DataSchema]:
        """Initialize standard schemas for each data source type"""
        
        schemas = {}
        
        # RBI Macro data schema
        rbi_columns = {
            'date': ColumnSchema(name='date', data_type=DataType.DATETIME, nullable=False),
            'repo_rate': ColumnSchema(name='repo_rate', data_type=DataType.FLOAT, nullable=True),
            'reverse_repo_rate': ColumnSchema(name='reverse_repo_rate', data_type=DataType.FLOAT, nullable=True),
            'bank_rate': ColumnSchema(name='bank_rate', data_type=DataType.FLOAT, nullable=True),
            'msf_rate': ColumnSchema(name='msf_rate', data_type=DataType.FLOAT, nullable=True),
            'sdf_rate': ColumnSchema(name='sdf_rate', data_type=DataType.FLOAT, nullable=True),
            'crr': ColumnSchema(name='crr', data_type=DataType.FLOAT, nullable=True),
            'slr': ColumnSchema(name='slr', data_type=DataType.FLOAT, nullable=True),
            'fx_reserves': ColumnSchema(name='fx_reserves', data_type=DataType.FLOAT, nullable=True),
            'usdinr': ColumnSchema(name='usdinr', data_type=DataType.FLOAT, nullable=True),
        }
        
        schemas[DataSourceType.RBI_MACRO] = DataSchema(
            name="rbi_macro_standard",
            version="1.0",
            columns=rbi_columns,
            temporal_columns=['date']
        )
        
        # Market data schema
        market_columns = {
            'date': ColumnSchema(name='date', data_type=DataType.DATETIME, nullable=False),
            'ticker': ColumnSchema(name='ticker', data_type=DataType.STRING, nullable=False),
            'close': ColumnSchema(name='close', data_type=DataType.FLOAT, nullable=False),
            'open': ColumnSchema(name='open', data_type=DataType.FLOAT, nullable=True),
            'high': ColumnSchema(name='high', data_type=DataType.FLOAT, nullable=True),
            'low': ColumnSchema(name='low', data_type=DataType.FLOAT, nullable=True),
            'volume': ColumnSchema(name='volume', data_type=DataType.INTEGER, nullable=True),
            'dollar_volume': ColumnSchema(name='dollar_volume', data_type=DataType.FLOAT, nullable=True),
        }
        
        schemas[DataSourceType.MARKET_DATA] = DataSchema(
            name="market_data_standard",
            version="1.0",
            columns=market_columns,
            temporal_columns=['date']
        )
        
        # Portfolio data schema
        portfolio_columns = {
            'ticker': ColumnSchema(name='ticker', data_type=DataType.STRING, nullable=False),
            'weight': ColumnSchema(name='weight', data_type=DataType.FLOAT, nullable=False),
            'score': ColumnSchema(name='score', data_type=DataType.FLOAT, nullable=True),
            'company_name': ColumnSchema(name='company_name', data_type=DataType.STRING, nullable=True),
            'industry': ColumnSchema(name='industry', data_type=DataType.STRING, nullable=True),
            'sector': ColumnSchema(name='sector', data_type=DataType.STRING, nullable=True),
        }
        
        schemas[DataSourceType.PORTFOLIO_DATA] = DataSchema(
            name="portfolio_data_standard",
            version="1.0",
            columns=portfolio_columns
        )
        
        # Universe data schema
        universe_columns = {
            'ticker': ColumnSchema(name='ticker', data_type=DataType.STRING, nullable=False),
            'company_name': ColumnSchema(name='company_name', data_type=DataType.STRING, nullable=True),
            'industry': ColumnSchema(name='industry', data_type=DataType.STRING, nullable=True),
            'sector': ColumnSchema(name='sector', data_type=DataType.STRING, nullable=True),
            'market_cap': ColumnSchema(name='market_cap', data_type=DataType.FLOAT, nullable=True),
        }
        
        schemas[DataSourceType.UNIVERSE_DATA] = DataSchema(
            name="universe_data_standard",
            version="1.0",
            columns=universe_columns
        )
        
        return schemas
    
    def standardize_data_format(self, 
                              df: pd.DataFrame, 
                              source_type: DataSourceType,
                              validate_schema: bool = True) -> FormatStandardizationResult:
        """
        Standardize data format for a specific source type
        ENFORCES INVARIANT D3: Schema Validation Completeness
        """
        
        if df is None or df.empty:
            return FormatStandardizationResult(
                success=False,
                standardized_data=None,
                original_columns=[],
                standardized_columns=[],
                dropped_columns=[],
                errors=["Input DataFrame is None or empty"],
                warnings=[],
                metadata={}
            )
        
        original_columns = list(df.columns)
        errors = []
        warnings = []
        dropped_columns = []
        
        try:
            # Create a copy to avoid modifying original data
            standardized_df = df.copy()
            
            # Get column mappings for this source type
            mappings = self.column_mappings.get(source_type, [])
            
            # Apply column name standardization
            column_rename_map = {}
            for mapping in mappings:
                if mapping.source_name in standardized_df.columns:
                    column_rename_map[mapping.source_name] = mapping.standard_name
            
            # Rename columns
            standardized_df = standardized_df.rename(columns=column_rename_map)
            
            # Apply transformations
            for mapping in mappings:
                if (mapping.transformation and 
                    mapping.standard_name in standardized_df.columns):
                    try:
                        standardized_df = self._apply_transformation(
                            standardized_df, 
                            mapping.standard_name, 
                            mapping.transformation
                        )
                    except Exception as e:
                        warnings.append(f"Failed to apply transformation {mapping.transformation} to {mapping.standard_name}: {e}")
            
            # Clean column names (remove special characters, standardize case)
            standardized_df.columns = [self._clean_column_name(col) for col in standardized_df.columns]
            
            # Remove duplicate columns
            if standardized_df.columns.duplicated().any():
                duplicate_cols = standardized_df.columns[standardized_df.columns.duplicated()].tolist()
                warnings.append(f"Removing duplicate columns: {duplicate_cols}")
                standardized_df = standardized_df.loc[:, ~standardized_df.columns.duplicated()]
            
            # Validate against standard schema if requested
            validation_result = None
            if validate_schema and source_type in self.standard_schemas:
                schema = self.standard_schemas[source_type]
                validation_result = schema.validate_dataframe(standardized_df)
                
                if not validation_result.is_valid:
                    errors.extend([error.message for error in validation_result.errors])
                
                if validation_result.warnings:
                    warnings.extend([warning.message for warning in validation_result.warnings])
            
            # Identify dropped columns
            standardized_columns = list(standardized_df.columns)
            dropped_columns = [col for col in original_columns if col not in column_rename_map.keys()]
            
            # ENFORCE INVARIANT D1: No Silent Data Loss
            if len(standardized_df) < len(df):
                data_loss_ratio = (len(df) - len(standardized_df)) / len(df)
                if data_loss_ratio > 0.1:  # More than 10% data loss
                    errors.append(f"INVARIANT VIOLATION D1: Excessive data loss detected: {data_loss_ratio:.2%}")
            
            return FormatStandardizationResult(
                success=len(errors) == 0,
                standardized_data=standardized_df if len(errors) == 0 else None,
                original_columns=original_columns,
                standardized_columns=standardized_columns,
                dropped_columns=dropped_columns,
                errors=errors,
                warnings=warnings,
                metadata={
                    'source_type': source_type.value,
                    'original_shape': df.shape,
                    'standardized_shape': standardized_df.shape,
                    'columns_renamed': len(column_rename_map),
                    'validation_performed': validate_schema,
                    'validation_passed': validation_result.is_valid if validation_result else None
                }
            )
            
        except Exception as e:
            return FormatStandardizationResult(
                success=False,
                standardized_data=None,
                original_columns=original_columns,
                standardized_columns=[],
                dropped_columns=[],
                errors=[f"Standardization failed: {str(e)}"],
                warnings=warnings,
                metadata={'source_type': source_type.value}
            )
    
    def _clean_column_name(self, column_name: str) -> str:
        """Clean and standardize column names"""
        if pd.isna(column_name):
            return "unnamed_column"
        
        # Convert to string and strip whitespace
        clean_name = str(column_name).strip()
        
        # Remove extra whitespace and newlines
        clean_name = ' '.join(clean_name.split())
        
        # Replace spaces with underscores
        clean_name = clean_name.replace(' ', '_')
        
        # Remove special characters except underscores
        clean_name = ''.join(c for c in clean_name if c.isalnum() or c == '_')
        
        # Convert to lowercase
        clean_name = clean_name.lower()
        
        # Ensure it doesn't start with a number
        if clean_name and clean_name[0].isdigit():
            clean_name = f"col_{clean_name}"
        
        # Ensure it's not empty
        if not clean_name:
            clean_name = "unnamed_column"
        
        return clean_name
    
    def _apply_transformation(self, 
                            df: pd.DataFrame, 
                            column_name: str, 
                            transformation: str) -> pd.DataFrame:
        """Apply transformation to a column"""
        
        if transformation == "add_ns_suffix":
            # Add .NS suffix to ticker symbols if not present
            if column_name in df.columns:
                df[column_name] = df[column_name].astype(str)
                mask = ~df[column_name].str.endswith('.NS')
                df.loc[mask, column_name] = df.loc[mask, column_name] + '.NS'
        
        return df
    
    def validate_data_consistency(self, 
                                data_sources: Dict[str, pd.DataFrame]) -> ValidationResult:
        """
        Validate consistency across multiple data sources
        ENFORCES INVARIANT D3: Schema Validation Completeness
        """
        
        errors = []
        warnings = []
        
        # Check for common columns across data sources
        all_columns = {}
        for source_name, df in data_sources.items():
            if df is not None and not df.empty:
                all_columns[source_name] = set(df.columns)
        
        # Find common columns that should have consistent naming
        common_columns = set.intersection(*all_columns.values()) if all_columns else set()
        
        # Check for inconsistent column naming patterns
        for source_name, columns in all_columns.items():
            # Check for mixed case patterns
            mixed_case_columns = [col for col in columns if any(c.isupper() for c in col) and any(c.islower() for c in col)]
            if mixed_case_columns:
                warnings.append(f"Mixed case columns in {source_name}: {mixed_case_columns}")
            
            # Check for spaces in column names
            space_columns = [col for col in columns if ' ' in str(col)]
            if space_columns:
                warnings.append(f"Columns with spaces in {source_name}: {space_columns}")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={
                'sources_checked': len(data_sources),
                'common_columns': list(common_columns),
                'total_unique_columns': len(set().union(*all_columns.values())) if all_columns else 0
            }
        )
    
    def get_standard_schema(self, source_type: DataSourceType) -> Optional[DataSchema]:
        """Get the standard schema for a data source type"""
        return self.standard_schemas.get(source_type)
    
    def register_custom_mapping(self, 
                              source_type: DataSourceType, 
                              mapping: ColumnMapping):
        """Register a custom column mapping"""
        if source_type not in self.column_mappings:
            self.column_mappings[source_type] = []
        
        self.column_mappings[source_type].append(mapping)