#!/usr/bin/env python3
"""
Data Standardization Module
Ensures consistent data formats across all Northstar modules
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Union
import os

# ====================== STANDARD SCHEMAS ======================

# Standard column names mapping
STANDARD_COLUMNS = {
    # Price data
    'price_data': {
        'required': ['Date', 'ticker', 'Open', 'High', 'Low', 'Close', 'Volume'],
        'date_cols': ['Date'],
        'numeric_cols': ['Open', 'High', 'Low', 'Close', 'Volume']
    },
    
    # Scores data
    'scores_data': {
        'required': ['Date', 'ticker', 'northstar_score'],
        'optional': ['Industry', 'market_score', 'value_score', 'quality_score', 'risk_penalty'],
        'date_cols': ['Date'],
        'numeric_cols': ['northstar_score', 'market_score', 'value_score', 'quality_score', 'risk_penalty']
    },
    
    # Macro data
    'macro_data': {
        'required': ['date'],  # Index
        'date_cols': ['date'],
        'numeric_cols': []  # All other columns should be numeric
    },
    
    # Portfolio weights
    'weights_data': {
        'required': ['date'],  # Index, stock columns are dynamic
        'date_cols': ['date'],
        'numeric_cols': []  # All stock columns should be numeric
    },
    
    # Sector rotation
    'sector_data': {
        'required': ['Date', 'Industry', 'capital_flow'],
        'optional': ['relative_performance', 'volume_growth', 'trend_strength', 'northstar_score', 'volatility'],
        'date_cols': ['Date'],
        'numeric_cols': ['capital_flow', 'relative_performance', 'volume_growth', 'trend_strength', 'northstar_score', 'volatility']
    }
}

# Standard file paths
STANDARD_PATHS = {
    'prices': 'data/processed/prices.parquet',
    'fundamentals': 'data/processed/fundamentals.parquet',
    'valuation': 'data/processed/valuation.parquet',
    'technicals': 'data/processed/technicals.parquet',
    'scores': 'data/processed/scores.parquet',
    'macro_factors': 'data/macro/factors/macro_factors.parquet',
    'macro_score': 'data/macro/factors/macro_score.parquet',
    'risk_budget': 'data/macro/factors/risk_budget.parquet',
    'portfolio_weights': 'data/processed/portfolio_weights.parquet',
    'sector_rotation': 'data/processed/sector_rotation.parquet',
    'opportunity_surface': 'data/processed/opportunity_surface.parquet',
    'market_regime': 'data/processed/market_regime.parquet',
    'emergency_signals': 'data/risk/emergency_signal.parquet'
}

# ====================== VALIDATION FUNCTIONS ======================

def validate_schema(df: pd.DataFrame, schema_name: str) -> Dict[str, Union[bool, List[str]]]:
    """Validate dataframe against standard schema"""
    
    if schema_name not in STANDARD_COLUMNS:
        return {'valid': False, 'errors': [f"Unknown schema: {schema_name}"]}
    
    schema = STANDARD_COLUMNS[schema_name]
    errors = []
    
    # Check required columns
    required_cols = schema['required']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        errors.append(f"Missing required columns: {missing_cols}")
    
    # Check date columns
    if 'date_cols' in schema:
        for date_col in schema['date_cols']:
            if date_col in df.columns:
                if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
                    errors.append(f"Column {date_col} is not datetime type")
    
    # Check numeric columns
    if 'numeric_cols' in schema:
        for num_col in schema['numeric_cols']:
            if num_col in df.columns:
                if not pd.api.types.is_numeric_dtype(df[num_col]):
                    errors.append(f"Column {num_col} is not numeric type")
    
    return {'valid': len(errors) == 0, 'errors': errors}

def standardize_dataframe(df: pd.DataFrame, schema_name: str) -> pd.DataFrame:
    """Standardize dataframe to match schema"""
    
    if schema_name not in STANDARD_COLUMNS:
        raise ValueError(f"Unknown schema: {schema_name}")
    
    df_clean = df.copy()
    schema = STANDARD_COLUMNS[schema_name]
    
    # Standardize date columns
    if 'date_cols' in schema:
        for date_col in schema['date_cols']:
            if date_col in df_clean.columns:
                df_clean[date_col] = pd.to_datetime(df_clean[date_col], errors='coerce')
    
    # Standardize numeric columns
    if 'numeric_cols' in schema:
        for num_col in schema['numeric_cols']:
            if num_col in df_clean.columns:
                df_clean[num_col] = pd.to_numeric(df_clean[num_col], errors='coerce')
    
    # Remove completely empty rows and columns
    df_clean = df_clean.dropna(how='all').dropna(axis=1, how='all')
    
    return df_clean

# ====================== STANDARD LOADERS ======================

def load_standard_data(data_type: str, validate: bool = True) -> Optional[pd.DataFrame]:
    """Load data with standard format validation"""
    
    if data_type not in STANDARD_PATHS:
        raise ValueError(f"Unknown data type: {data_type}. Available: {list(STANDARD_PATHS.keys())}")
    
    file_path = STANDARD_PATHS[data_type]
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Data file not found: {file_path}")
    
    # Load data
    df = pd.read_parquet(file_path)
    
    # Validate if requested
    if validate and data_type in STANDARD_COLUMNS:
        validation = validate_schema(df, f"{data_type}_data")
        if not validation['valid']:
            print(f"⚠️  Data validation warnings for {data_type}:")
            for error in validation['errors']:
                print(f"   - {error}")
    
    return df

def save_standard_data(df: pd.DataFrame, data_type: str, validate: bool = True) -> None:
    """Save data with standard format validation"""
    
    if data_type not in STANDARD_PATHS:
        raise ValueError(f"Unknown data type: {data_type}. Available: {list(STANDARD_PATHS.keys())}")
    
    # Validate before saving
    if validate and data_type in STANDARD_COLUMNS:
        validation = validate_schema(df, f"{data_type}_data")
        if not validation['valid']:
            print(f"⚠️  Data validation warnings for {data_type}:")
            for error in validation['errors']:
                print(f"   - {error}")
    
    file_path = STANDARD_PATHS[data_type]
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Save data
    df.to_parquet(file_path)
    print(f"✅ Saved standardized {data_type} data: {file_path}")

# ====================== COLUMN STANDARDIZATION ======================

def standardize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names across the system"""
    
    df_clean = df.copy()
    
    # Common column name mappings
    column_mappings = {
        # Date columns
        'date': 'Date',
        'DATE': 'Date',
        'timestamp': 'Date',
        'time': 'Date',
        
        # Ticker columns
        'symbol': 'ticker',
        'Symbol': 'ticker',
        'SYMBOL': 'ticker',
        'Ticker': 'ticker',
        'TICKER': 'ticker',
        
        # Industry columns
        'industry': 'Industry',
        'INDUSTRY': 'Industry',
        'sector': 'Industry',
        'Sector': 'Industry',
        'SECTOR': 'Industry',
        
        # Price columns
        'close': 'Close',
        'CLOSE': 'Close',
        'open': 'Open',
        'OPEN': 'Open',
        'high': 'High',
        'HIGH': 'High',
        'low': 'Low',
        'LOW': 'Low',
        'volume': 'Volume',
        'VOLUME': 'Volume'
    }
    
    # Apply mappings
    df_clean = df_clean.rename(columns=column_mappings)
    
    return df_clean

# ====================== DATA QUALITY CHECKS ======================

def check_data_quality(df: pd.DataFrame, data_type: str) -> Dict[str, Union[int, float, List[str]]]:
    """Comprehensive data quality check"""
    
    quality_report = {
        'total_rows': len(df),
        'total_columns': len(df.columns),
        'missing_data_pct': (df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100,
        'duplicate_rows': df.duplicated().sum(),
        'issues': []
    }
    
    # Check for completely empty columns
    empty_cols = df.columns[df.isnull().all()].tolist()
    if empty_cols:
        quality_report['issues'].append(f"Empty columns: {empty_cols}")
    
    # Check for columns with >90% missing data
    high_missing_cols = df.columns[df.isnull().mean() > 0.9].tolist()
    if high_missing_cols:
        quality_report['issues'].append(f"High missing data (>90%): {high_missing_cols}")
    
    # Data type specific checks
    if data_type == 'prices':
        # Check for negative prices
        price_cols = ['Open', 'High', 'Low', 'Close']
        for col in price_cols:
            if col in df.columns:
                negative_count = (df[col] < 0).sum()
                if negative_count > 0:
                    quality_report['issues'].append(f"Negative {col} prices: {negative_count} rows")
    
    elif data_type == 'scores':
        # Check for extreme scores
        if 'northstar_score' in df.columns:
            extreme_scores = ((df['northstar_score'] < -100) | (df['northstar_score'] > 200)).sum()
            if extreme_scores > 0:
                quality_report['issues'].append(f"Extreme northstar_scores: {extreme_scores} rows")
    
    return quality_report

# ====================== UTILITY FUNCTIONS ======================

def get_date_range(df: pd.DataFrame, date_col: str = 'Date') -> Dict[str, pd.Timestamp]:
    """Get date range from dataframe"""
    
    if date_col not in df.columns:
        return {'start': None, 'end': None, 'error': f"Date column '{date_col}' not found"}
    
    date_series = pd.to_datetime(df[date_col], errors='coerce')
    
    return {
        'start': date_series.min(),
        'end': date_series.max(),
        'total_days': (date_series.max() - date_series.min()).days if date_series.notna().any() else 0
    }

def align_dataframes_by_date(*dfs: pd.DataFrame, date_col: str = 'Date', method: str = 'inner') -> List[pd.DataFrame]:
    """Align multiple dataframes by date"""
    
    if not dfs:
        return []
    
    # Convert all date columns to datetime
    aligned_dfs = []
    for df in dfs:
        df_copy = df.copy()
        if date_col in df_copy.columns:
            df_copy[date_col] = pd.to_datetime(df_copy[date_col], errors='coerce')
        aligned_dfs.append(df_copy)
    
    # Find common date range
    if method == 'inner':
        # Use intersection of all date ranges
        date_ranges = []
        for df in aligned_dfs:
            if date_col in df.columns:
                date_ranges.append(set(df[date_col].dropna()))
        
        if date_ranges:
            common_dates = set.intersection(*date_ranges)
            
            # Filter each dataframe to common dates
            result_dfs = []
            for df in aligned_dfs:
                if date_col in df.columns:
                    filtered_df = df[df[date_col].isin(common_dates)]
                    result_dfs.append(filtered_df)
                else:
                    result_dfs.append(df)
            
            return result_dfs
    
    return aligned_dfs

def print_data_summary(df: pd.DataFrame, name: str = "DataFrame") -> None:
    """Print comprehensive data summary"""
    
    print(f"\n📊 {name} Summary:")
    print("=" * 50)
    print(f"Shape: {df.shape[0]:,} rows × {df.shape[1]} columns")
    
    # Date range if available
    date_cols = [col for col in df.columns if 'date' in col.lower() or col in ['Date', 'timestamp']]
    if date_cols:
        date_range = get_date_range(df, date_cols[0])
        if date_range['start']:
            print(f"Date range: {date_range['start'].strftime('%Y-%m-%d')} to {date_range['end'].strftime('%Y-%m-%d')}")
            print(f"Total days: {date_range['total_days']:,}")
    
    # Missing data
    missing_pct = (df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100
    print(f"Missing data: {missing_pct:.1f}%")
    
    # Duplicates
    duplicates = df.duplicated().sum()
    if duplicates > 0:
        print(f"Duplicate rows: {duplicates:,}")
    
    # Column types
    print(f"\nColumn types:")
    type_counts = df.dtypes.value_counts()
    for dtype, count in type_counts.items():
        print(f"  {dtype}: {count} columns")
    
    print()