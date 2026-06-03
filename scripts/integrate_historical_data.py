#!/usr/bin/env python3
"""
Historical Data Integration Script

This script integrates historical equity data with current daily prices.
It handles:
1. Different date ranges (some companies started later, some have gaps)
2. Different column formats between historical and current data
3. Deduplication of overlapping periods
4. Missing data for companies not in historical period
"""

import pandas as pd
import os
import glob
from pathlib import Path
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HistoricalDataIntegrator:
    def __init__(self, historical_path, current_path, output_path):
        self.historical_path = Path(historical_path)
        self.current_path = Path(current_path)
        self.output_path = Path(output_path)
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        # Statistics
        self.stats = {
            'total_files_processed': 0,
            'files_with_historical_data': 0,
            'files_current_only': 0,
            'files_with_overlaps': 0,
            'total_records_added': 0
        }
    
    def normalize_symbol(self, symbol):
        """Convert between different symbol formats"""
        # Remove .NS suffix if present
        if symbol.endswith('.NS'):
            return symbol[:-3]
        return symbol
    
    def load_historical_data(self, symbol):
        """Load historical data for a symbol"""
        base_symbol = self.normalize_symbol(symbol)
        historical_file = self.historical_path / f"{base_symbol}.csv"
        
        if not historical_file.exists():
            return None
            
        try:
            # Read historical data with proper column handling
            df = pd.read_csv(historical_file)
            
            # Handle malformed CSV (seems to have formatting issues)
            if len(df.columns) == 1:
                # Try to parse the malformed data
                lines = []
                with open(historical_file, 'r') as f:
                    for line in f:
                        # Clean up the line and split properly
                        clean_line = line.strip().replace(' ', '').replace('\n', '')
                        if ',' in clean_line and len(clean_line.split(',')) >= 7:
                            parts = clean_line.split(',')
                            if len(parts) >= 8:  # Date,Adj Close,Close,High,Low,Open,Volume,Symbol
                                lines.append(parts[:8])
                
                if lines:
                    df = pd.DataFrame(lines[1:], columns=['Date', 'Adj_Close', 'Close', 'High', 'Low', 'Open', 'Volume', 'Symbol'])
                else:
                    return None
            
            # Standardize column names
            df.columns = df.columns.str.strip()
            if 'Adj Close' in df.columns:
                df = df.rename(columns={'Adj Close': 'Adj_Close'})
            
            # Convert Date column
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df = df.dropna(subset=['Date'])
            
            # Convert numeric columns
            numeric_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            if 'Adj_Close' in df.columns:
                numeric_cols.append('Adj_Close')
                
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Sort by date
            df = df.sort_values('Date')
            
            # Select relevant columns in standard order
            standard_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            df = df[standard_cols].copy()
            
            logger.info(f"Loaded historical data for {base_symbol}: {len(df)} records from {df['Date'].min()} to {df['Date'].max()}")
            return df
            
        except Exception as e:
            logger.error(f"Error loading historical data for {base_symbol}: {e}")
            return None
    
    def load_current_data(self, symbol):
        """Load current daily data for a symbol"""
        current_file = self.current_path / f"{symbol}.csv"
        
        if not current_file.exists():
            return None
            
        try:
            df = pd.read_csv(current_file)
            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date')
            
            # Ensure standard columns
            standard_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
            df = df[standard_cols].copy()
            
            logger.info(f"Loaded current data for {symbol}: {len(df)} records from {df['Date'].min()} to {df['Date'].max()}")
            return df
            
        except Exception as e:
            logger.error(f"Error loading current data for {symbol}: {e}")
            return None
    
    def merge_data(self, historical_df, current_df):
        """Merge historical and current data, handling overlaps"""
        if historical_df is None:
            return current_df
        if current_df is None:
            return historical_df
            
        # Find overlap period
        hist_max = historical_df['Date'].max()
        curr_min = current_df['Date'].min()
        
        overlap_exists = hist_max >= curr_min
        
        if overlap_exists:
            self.stats['files_with_overlaps'] += 1
            # Keep historical data up to current start, then use current data
            historical_filtered = historical_df[historical_df['Date'] < curr_min].copy()
            merged_df = pd.concat([historical_filtered, current_df], ignore_index=True)
            logger.info(f"Overlap detected. Historical: up to {hist_max}, Current: from {curr_min}. Using historical up to {curr_min}")
        else:
            # No overlap, concatenate all data
            merged_df = pd.concat([historical_df, current_df], ignore_index=True)
            logger.info(f"No overlap. Historical: up to {hist_max}, Current: from {curr_min}")
        
        # Sort by date and remove any duplicates
        merged_df = merged_df.sort_values('Date').drop_duplicates(subset=['Date'], keep='last')
        
        return merged_df
    
    def process_symbol(self, symbol):
        """Process a single symbol"""
        logger.info(f"Processing {symbol}")
        
        # Load data
        historical_df = self.load_historical_data(symbol)
        current_df = self.load_current_data(symbol)
        
        # Track statistics
        if historical_df is not None:
            self.stats['files_with_historical_data'] += 1
        if historical_df is None and current_df is not None:
            self.stats['files_current_only'] += 1
        
        # Merge data
        merged_df = self.merge_data(historical_df, current_df)
        
        if merged_df is None or len(merged_df) == 0:
            logger.warning(f"No data available for {symbol}")
            return False
        
        # Calculate additional records from historical data
        if historical_df is not None and current_df is not None:
            additional_records = len(merged_df) - len(current_df)
            self.stats['total_records_added'] += additional_records
            logger.info(f"Added {additional_records} historical records for {symbol}")
        elif historical_df is not None:
            self.stats['total_records_added'] += len(merged_df)
        
        # Save merged data
        output_file = self.output_path / f"{symbol}.csv"
        merged_df.to_csv(output_file, index=False)
        
        logger.info(f"Saved {len(merged_df)} records for {symbol} to {output_file}")
        return True
    
    def process_all_symbols(self):
        """Process all symbols from current data directory"""
        current_files = list(self.current_path.glob("*.csv"))
        
        logger.info(f"Found {len(current_files)} current data files to process")
        
        for file_path in current_files:
            symbol = file_path.stem  # filename without extension
            self.stats['total_files_processed'] += 1
            
            try:
                self.process_symbol(symbol)
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                continue
        
        self.print_statistics()
    
    def print_statistics(self):
        """Print processing statistics"""
        logger.info("=== PROCESSING STATISTICS ===")
        logger.info(f"Total files processed: {self.stats['total_files_processed']}")
        logger.info(f"Files with historical data: {self.stats['files_with_historical_data']}")
        logger.info(f"Files with current data only: {self.stats['files_current_only']}")
        logger.info(f"Files with overlapping periods: {self.stats['files_with_overlaps']}")
        logger.info(f"Total historical records added: {self.stats['total_records_added']}")
        
        if self.stats['total_files_processed'] > 0:
            historical_coverage = (self.stats['files_with_historical_data'] / self.stats['total_files_processed']) * 100
            logger.info(f"Historical data coverage: {historical_coverage:.1f}%")


def main():
    # Paths
    historical_path = os.getenv("NORTHSTAR_HISTORICAL_PRICE_PATH", "data/historical/equities/daily")
    current_path = "data/raw/prices_daily"
    output_path = "data/raw/prices_daily_extended"
    
    # Create integrator and process
    integrator = HistoricalDataIntegrator(historical_path, current_path, output_path)
    integrator.process_all_symbols()
    
    logger.info("Historical data integration completed!")


if __name__ == "__main__":
    main()
