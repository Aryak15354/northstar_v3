#!/usr/bin/env python3
"""
🏛️ RBI DATA HANDLER - NORTHSTAR V3 UNIFIED RBI DATA ARCHITECTURE
Centralized RBI data handling for all Northstar components

This module provides a unified interface for all RBI data operations:
- Standardized Period column handling (RBI uses "Period" not "Date")
- Consistent header detection and cleaning
- Unified data type conversion and validation
- Standardized resampling and alignment
- Error handling and data quality assurance

Used by:
- Market Brain components
- Macro processing pipeline
- RBI ingestion systems
- Market state calculations
- All other RBI data consumers
"""

# from src.cohesion.dependency_container import get_dependency_container

import pandas as pd
import numpy as np
import os
import sys
import warnings
from datetime import datetime, timedelta
warnings.filterwarnings('ignore')

# Import new standardization system
# Dependency injection - import SchemaValidator from src.cohesion.schema_validator
STANDARDIZATION_AVAILABLE = False
# Silent fallback: legacy processing remains active when standardization is unavailable.

class RBIDataHandler:
    """
    Unified RBI Data Handler
    
    Provides standardized methods for handling RBI data across all Northstar components.
    Ensures consistent data architecture and prevents data processing errors.
    """
    
    def __init__(self):
        self.name = "RBI Data Handler"
        self.version = "1.0"
        
        # RBI data architecture constants
        self.RBI_DATE_COLUMN = "Period"  # RBI uses "Period" not "Date"
        self.RBI_HEADER_INDICATORS = [
            "reporting date", "period", "date", 
            "macro-economic", "indicators"
        ]
        
        # Standard RBI file patterns
        self.RBI_FILE_PATTERNS = {
            'daily_other': 'rbi_daily_other.csv',
            'weekly_core': 'rbi_weekly_core.csv', 
            'weekly_other': 'rbi_weekly_other.csv',
            'fortnightly_core': 'rbi_fortnightly_core.csv',
            'monthly_core': 'rbi_monthly_core.csv',
            'monthly_other': 'rbi_monthly_other.csv',
            'quarterly_core': 'rbi_quarterly_core.csv',
            'quarterly_other': 'rbi_quarterly_other.csv'
        }
        
        # Data quality thresholds
        self.MIN_DATA_COVERAGE = 0.1  # At least 10% non-null values
        self.MAX_HEADER_SEARCH_ROWS = 10  # Search first 10 rows for headers
    
    def detect_rbi_header_row(self, df):
        """
        Detect the header row in RBI CSV files
        
        RBI files have multiple header rows and metadata at the top.
        This finds the actual data header row.
        """
        
        header_row = 0
        date_col_index = None
        
        # Search for header row with date/period column
        for i in range(min(self.MAX_HEADER_SEARCH_ROWS, len(df))):
            row = df.iloc[i]
            for j, cell in enumerate(row):
                if pd.notna(cell):
                    cell_str = str(cell).lower().strip()
                    if any(indicator in cell_str for indicator in self.RBI_DATE_COLUMN.lower().split()):
                        header_row = i
                        date_col_index = j
                        return header_row, date_col_index, self.RBI_DATE_COLUMN
        
        # Fallback: look for other date indicators
        for i in range(min(self.MAX_HEADER_SEARCH_ROWS, len(df))):
            row = df.iloc[i]
            for j, cell in enumerate(row):
                if pd.notna(cell):
                    cell_str = str(cell).lower().strip()
                    for indicator in self.RBI_HEADER_INDICATORS:
                        if indicator in cell_str:
                            header_row = i
                            date_col_index = j
                            # Determine the actual column name
                            actual_col_name = str(df.iloc[i, j]).strip()
                            return header_row, date_col_index, actual_col_name
        
        return None, None, None
    
    def clean_rbi_column_names(self, columns):
        """Clean and standardize RBI column names"""
        
        cleaned_columns = []
        for col in columns:
            if pd.isna(col):
                cleaned_columns.append(f"unnamed_col_{len(cleaned_columns)}")
                continue
                
            # Convert to string and clean
            col_str = str(col).strip()
            
            # Remove extra whitespace and newlines
            col_str = ' '.join(col_str.split())
            
            # Handle special characters
            col_str = col_str.replace('\n', ' ').replace('\r', ' ')
            
            cleaned_columns.append(col_str)
        
        return cleaned_columns
    
    def convert_rbi_period_to_datetime(self, period_series):
        """
        Convert RBI Period column to datetime
        
        RBI uses various date formats in the Period column.
        This handles all common formats.
        """
        
        if period_series.empty:
            return pd.Series(dtype='datetime64[ns]')
        
        # Try different date formats commonly used by RBI
        date_formats = [
            '%d-%m-%Y',      # 31-12-2023
            '%d/%m/%Y',      # 31/12/2023
            '%Y-%m-%d',      # 2023-12-31
            '%d-%b-%Y',      # 31-Dec-2023
            '%d %b %Y',      # 31 Dec 2023
            '%b-%Y',         # Dec-2023
            '%Y-%m',         # 2023-12
            '%Y'             # 2023
        ]
        
        converted_dates = None
        
        for date_format in date_formats:
            try:
                converted_dates = pd.to_datetime(period_series, format=date_format, errors='coerce')
                # If we got some valid dates, use this format
                if converted_dates.notna().sum() > len(converted_dates) * 0.5:
                    break
            except:
                continue
        
        # Fallback: let pandas infer the format
        if converted_dates is None or converted_dates.notna().sum() < len(converted_dates) * 0.5:
            try:
                converted_dates = pd.to_datetime(period_series, errors='coerce', infer_datetime_format=True)
            except:
                # Last resort: return NaT series
                converted_dates = pd.Series([pd.NaT] * len(period_series), dtype='datetime64[ns]')
        
        return converted_dates
    
    def clean_rbi_numeric_data(self, series):
        """
        Clean and convert RBI numeric data
        
        RBI data often has commas, spaces, and other formatting issues.
        """
        
        if series.empty:
            return series
        
        # Ensure we're working with a Series
        if isinstance(series, pd.DataFrame):
            series = series.iloc[:, 0] if not series.empty else pd.Series(dtype=float)
        
        # Convert to string first
        series_str = series.astype(str)
        
        # Clean common formatting issues
        series_str = series_str.str.replace(',', '')  # Remove commas
        series_str = series_str.str.replace(' ', '')  # Remove spaces
        series_str = series_str.str.replace('nan', '')  # Remove 'nan' strings
        series_str = series_str.str.replace('None', '')  # Remove 'None' strings
        series_str = series_str.str.replace('-', '')  # Remove dashes (often used for missing data)
        
        # Convert to numeric
        try:
            numeric_series = pd.to_numeric(series_str, errors='coerce')
            return numeric_series
        except Exception as e:
            print(f"   ⚠️ Could not convert series to numeric: {e}")
            return pd.Series([np.nan] * len(series), dtype=float)
    
    def load_rbi_file(self, file_path, file_key=None):
        """
        Load and process a single RBI CSV file with proper architecture handling
        
        Returns a clean DataFrame with:
        - Proper datetime index
        - Clean column names
        - Numeric data properly converted
        - File source prefix added to column names
        """
        
        if not os.path.exists(file_path):
            print(f"   ❌ RBI file not found: {file_path}")
            return pd.DataFrame()
        
        try:
            # Read raw file
            raw_df = pd.read_csv(file_path)
            
            if raw_df.empty:
                print(f"   ⚠️ Empty RBI file: {file_path}")
                return pd.DataFrame()
            
            # Detect header row and date column
            header_row, date_col_index, date_col_name = self.detect_rbi_header_row(raw_df)
            
            if header_row is None:
                print(f"   ⚠️ Could not detect header in RBI file: {file_path}")
                return pd.DataFrame()
            
            # Extract data starting from header row
            df = raw_df.iloc[header_row:].copy()
            df.columns = self.clean_rbi_column_names(df.iloc[0])  # Use first row as headers
            df = df.iloc[1:].reset_index(drop=True)  # Remove header row from data
            
            # Find the date column in cleaned columns
            date_column = None
            for col in df.columns:
                if any(term in str(col).lower() for term in ['period', 'date', 'reporting']):
                    date_column = col
                    break
            
            if not date_column or date_column not in df.columns:
                print(f"   ⚠️ Date column not found in processed RBI file: {file_path}")
                return pd.DataFrame()
            
            # Convert date column to datetime
            df[date_column] = self.convert_rbi_period_to_datetime(df[date_column])
            df = df.dropna(subset=[date_column])
            
            if df.empty:
                print(f"   ⚠️ No valid dates in RBI file: {file_path}")
                return pd.DataFrame()
            
            # Set datetime index
            df = df.set_index(date_column)
            
            # Process numeric columns
            numeric_columns = []
            for col in df.columns:
                if col != date_column:
                    try:
                        # Clean and convert to numeric
                        cleaned_series = self.clean_rbi_numeric_data(df[col])
                        
                        # Keep if has sufficient data coverage
                        if cleaned_series.notna().sum() >= len(cleaned_series) * self.MIN_DATA_COVERAGE:
                            df[col] = cleaned_series
                            numeric_columns.append(col)
                    except Exception as e:
                        print(f"      ⚠️ Could not process column {col}: {e}")
                        continue
            
            if not numeric_columns:
                print(f"   ⚠️ No numeric data found in RBI file: {file_path}")
                return pd.DataFrame()
            
            # Keep only numeric columns
            df = df[numeric_columns]
            
            # Add file source prefix to avoid column name conflicts
            if file_key:
                df.columns = [f"{file_key}_{col}" for col in df.columns]
            
            # Sort by date
            df = df.sort_index()
            
            return df
            
        except Exception as e:
            print(f"   ❌ Error loading RBI file {file_path}: {e}")
            return pd.DataFrame()
    
    def resample_rbi_data(self, df, target_frequency='W'):
        """
        Resample RBI data to target frequency
        
        Uses appropriate aggregation method based on data type.
        """
        
        if df.empty:
            return df
        
        try:
            # Ensure datetime index
            if not isinstance(df.index, pd.DatetimeIndex):
                print("   ⚠️ Cannot resample: index is not datetime")
                return df
            
            # Resample using last value (appropriate for most economic indicators)
            resampled_df = df.resample(target_frequency).last()
            
            # Forward fill missing values (reasonable for economic data)
            resampled_df = resampled_df.ffill()
            
            return resampled_df
            
        except Exception as e:
            print(f"   ⚠️ Error resampling RBI data: {e}")
            return df
    
    def align_rbi_dataframes(self, dataframes_dict, target_frequency='W'):
        """
        Align multiple RBI DataFrames to common date range and frequency
        
        Returns a single DataFrame with all data aligned and properly formatted.
        """
        
        if not dataframes_dict:
            return pd.DataFrame()
        
        # Filter out empty DataFrames
        valid_dfs = {k: v for k, v in dataframes_dict.items() if not v.empty}
        
        if not valid_dfs:
            return pd.DataFrame()
        
        # Resample all DataFrames to target frequency
        resampled_dfs = {}
        for name, df in valid_dfs.items():
            resampled_df = self.resample_rbi_data(df, target_frequency)
            if not resampled_df.empty:
                # Ensure all columns are proper 1-dimensional Series
                for col in resampled_df.columns:
                    try:
                        # Get the raw column data
                        col_data = resampled_df[col]
                        
                        # Check if column is multi-dimensional
                        if hasattr(col_data, 'values') and col_data.values.ndim > 1:
                            # Extract first column from multi-dimensional data
                            if col_data.values.ndim == 2:
                                flat_values = col_data.values[:, 0]
                            else:
                                flat_values = col_data.values.flatten()[:len(resampled_df.index)]
                            
                            # Create new 1-dimensional Series
                            resampled_df[col] = pd.Series(flat_values, index=resampled_df.index, dtype=float)
                        
                        # Ensure it's a proper Series
                        if not isinstance(resampled_df[col], pd.Series):
                            resampled_df[col] = pd.Series(resampled_df[col], index=resampled_df.index, dtype=float)
                        
                        # Final check: ensure values are 1-dimensional
                        if hasattr(resampled_df[col], 'values') and resampled_df[col].values.ndim > 1:
                            # Force flatten if still multi-dimensional
                            flat_values = resampled_df[col].values.flatten()[:len(resampled_df.index)]
                            resampled_df[col] = pd.Series(flat_values, index=resampled_df.index, dtype=float)
                            
                    except Exception as e:
                        print(f"      ⚠️ Issue fixing column {col} in {name}: {e}")
                        # Remove problematic column
                        try:
                            resampled_df = resampled_df.drop(columns=[col])
                        except:
                            pass
                
                resampled_dfs[name] = resampled_df
        
        if not resampled_dfs:
            return pd.DataFrame()
        
        # Find common date range
        all_dates = set()
        for df in resampled_dfs.values():
            all_dates.update(df.index)
        
        if not all_dates:
            return pd.DataFrame()
        
        # Create full date range
        full_date_range = pd.date_range(min(all_dates), max(all_dates), freq=target_frequency)
        
        # Align all DataFrames
        aligned_dfs = []
        for name, df in resampled_dfs.items():
            try:
                # Reindex to full range
                aligned_df = df.reindex(full_date_range)
                
                # Forward fill missing values
                aligned_df = aligned_df.ffill().bfill()
                
                # Final check: ensure all columns are 1-dimensional Series
                for col in list(aligned_df.columns):
                    try:
                        col_data = aligned_df[col]
                        
                        if hasattr(col_data, 'values') and col_data.values.ndim > 1:
                            # Extract first column from multi-dimensional data
                            if col_data.values.ndim == 2:
                                flat_values = col_data.values[:, 0]
                            else:
                                flat_values = col_data.values.flatten()[:len(aligned_df.index)]
                            
                            # Create new 1-dimensional Series
                            aligned_df[col] = pd.Series(flat_values, index=aligned_df.index, dtype=float)
                        
                        # Ensure proper Series structure
                        if not isinstance(aligned_df[col], pd.Series):
                            aligned_df[col] = pd.Series(aligned_df[col], index=aligned_df.index, dtype=float)
                            
                    except Exception as e:
                        print(f"      ⚠️ Final alignment issue with column {col} in {name}: {e}")
                        # Remove problematic column
                        try:
                            aligned_df = aligned_df.drop(columns=[col])
                        except:
                            pass
                
                aligned_dfs.append(aligned_df)
            except Exception as e:
                print(f"   ⚠️ Error aligning {name}: {e}")
                continue
        
        if not aligned_dfs:
            return pd.DataFrame()
        
        # Concatenate all aligned DataFrames
        try:
            combined_df = pd.concat(aligned_dfs, axis=1, sort=True)
            
            # Final cleanup - ensure all columns are 1-dimensional
            for col in list(combined_df.columns):
                try:
                    col_data = combined_df[col]
                    
                    if hasattr(col_data, 'values') and col_data.values.ndim > 1:
                        # Extract first column from multi-dimensional data
                        if col_data.values.ndim == 2:
                            flat_values = col_data.values[:, 0]
                        else:
                            flat_values = col_data.values.flatten()[:len(combined_df.index)]
                        
                        # Create new 1-dimensional Series
                        combined_df[col] = pd.Series(flat_values, index=combined_df.index, dtype=float)
                    
                    # Ensure proper Series structure
                    if not isinstance(combined_df[col], pd.Series):
                        combined_df[col] = pd.Series(combined_df[col], index=combined_df.index, dtype=float)
                        
                except Exception as e:
                    print(f"      ⚠️ Final cleanup issue with column {col}: {e}")
                    # Remove problematic column
                    try:
                        combined_df = combined_df.drop(columns=[col])
                    except:
                        pass
            
            # Final forward fill
            combined_df = combined_df.ffill().fillna(0)
            
            return combined_df
            
        except Exception as e:
            print(f"   ❌ Error combining aligned DataFrames: {e}")
            return pd.DataFrame()
    
    def get_rbi_data_summary(self, df):
        """Get summary statistics for RBI data"""
        
        if df.empty:
            return {}
        
        return {
            'shape': df.shape,
            'date_range': [str(df.index.min().date()), str(df.index.max().date())],
            'columns': list(df.columns),
            'missing_data_pct': (df.isna().sum().sum() / (df.shape[0] * df.shape[1])) * 100,
            'numeric_columns': len(df.select_dtypes(include=[np.number]).columns)
        }
    
    def process_with_standardization(self, file_path, file_key=None):
        """
        Process RBI file using the new standardization system
        ENFORCES CAPITAL-GRADE DATA FORMAT STANDARDS
        """
        
        if not STANDARDIZATION_AVAILABLE:
            # Silent fallback by design for non-standardized environments.
            return self.load_rbi_file(file_path, file_key)
        
        try:
            # Initialize standardization components
            schema_validator = SchemaValidator()
            format_standardizer = DataFormatStandardizer(schema_validator)
            ingestion_validator = DataIngestionValidator(schema_validator, format_standardizer)
            
            # Load raw data using existing method
            raw_df = self.load_rbi_file(file_path, file_key)
            
            if raw_df.empty:
                return raw_df
            
            # Configure quality checks for RBI data
            quality_config = DataQualityConfig(
                freshness_threshold=timedelta(days=30),  # RBI data can be up to 30 days old
                max_null_percentage=0.3,  # Allow up to 30% nulls in RBI data
                max_duplicate_percentage=0.1,  # Allow up to 10% duplicates
                min_completeness_ratio=0.7,  # Require 70% completeness
                temporal_column='date' if 'date' in raw_df.columns else None
            )
            
            # Reset index to make date a column for validation
            if isinstance(raw_df.index, pd.DatetimeIndex):
                validation_df = raw_df.reset_index()
                validation_df = validation_df.rename(columns={'index': 'date'})
            else:
                validation_df = raw_df.copy()
            
            # Validate and standardize
            validation_result = ingestion_validator.validate_ingestion(
                df=validation_df,
                source_type=DataSourceType.RBI_MACRO,
                source_name=file_key or os.path.basename(file_path),
                quality_config=quality_config,
                enforce_schema=False  # RBI data has variable schemas
            )
            
            if validation_result.success:
                print(f"✅ RBI data validation passed for {file_key or file_path}")
                
                # Convert back to datetime index if needed
                standardized_df = validation_result.validated_data
                if 'date' in standardized_df.columns:
                    standardized_df['date'] = pd.to_datetime(standardized_df['date'])
                    standardized_df = standardized_df.set_index('date')
                
                return standardized_df
            else:
                print(f"❌ RBI data validation failed for {file_key or file_path}")
                print(f"   Errors: {validation_result.errors}")
                
                if validation_result.should_quarantine:
                    quarantine_file = ingestion_validator.quarantine_data(
                        validation_df, 
                        file_key or os.path.basename(file_path),
                        validation_result
                    )
                    print(f"   Data quarantined: {quarantine_file}")
                
                # Return empty DataFrame for failed validation
                return pd.DataFrame()
                
        except Exception:
            # Keep runtime quiet and continue with legacy processing.
            return self.load_rbi_file(file_path, file_key)

# Global instance for use across Northstar
rbi_handler = RBIDataHandler()
