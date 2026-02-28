"""
Parquet Utilities - Safe parquet file loading with error handling
"""

import pandas as pd
import os

def safe_load_parquet(file_path, default=None):
    """
    Safely load parquet file with comprehensive error handling
    """
    if not os.path.exists(file_path):
        print(f"Warning: Parquet file not found: {file_path}")
        return default if default is not None else pd.DataFrame()
    
    try:
        if os.path.getsize(file_path) == 0:
            print(f"Warning: Empty parquet file: {file_path}")
            return default if default is not None else pd.DataFrame()
        
        df = pd.read_parquet(file_path)
        
        if df.empty:
            print(f"Warning: Parquet file contains no data: {file_path}")
            return default if default is not None else pd.DataFrame()
            
        return df
        
    except Exception as e:
        print(f"Warning: Error loading parquet {file_path}: {e}")
        return default if default is not None else pd.DataFrame()

def safe_save_parquet(df, file_path):
    """Safely save parquet file"""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        df.to_parquet(file_path, index=False)
        return True
    except Exception as e:
        print(f"Warning: Error saving parquet {file_path}: {e}")
        return False
