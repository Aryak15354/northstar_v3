#!/usr/bin/env python3
"""
Comprehensive Date Recovery for News Dataset
Recovers dates from original source files by re-reading them with proper date extraction
"""

import pandas as pd
import numpy as np
from pathlib import Path
from tqdm import tqdm
import re
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class ComprehensiveDateRecovery:
    def __init__(self):
        self.recovered_dates = {}
        
    def normalize_date(self, date_val):
        """Normalize various date formats"""
        if pd.isna(date_val):
            return None
        
        try:
            # Handle numeric dates
            if isinstance(date_val, (int, float)):
                date_str = str(int(date_val))
                if len(date_str) == 8:
                    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            
            # Parse as datetime
            date_obj = pd.to_datetime(date_val, errors='coerce')
            if pd.notna(date_obj) and 2000 <= date_obj.year <= 2026:
                return date_obj.strftime('%Y-%m-%d')
        except:
            pass
        
        return None
    
    def recover_from_structured_news(self):
        """Recover dates from data/news structured folders"""
        print("\nRecovering dates from structured news folders...")
        news_dir = Path('data/news')
        csv_files = list(news_dir.rglob('*.csv'))
        
        for csv_file in tqdm(csv_files, desc="Processing structured files"):
            try:
                df = pd.read_csv(csv_file)
                
                # Try different date column names
                date_cols = ['published_date', 'published', 'Date', 'date', 'publish_date']
                date_col = None
                for col in date_cols:
                    if col in df.columns:
                        date_col = col
                        break
                
                if not date_col:
                    continue
                
                # Try to find URL or title to match
                if 'url' in df.columns:
                    for _, row in df.iterrows():
                        url = row.get('url')
                        date = self.normalize_date(row.get(date_col))
                        if pd.notna(url) and date:
                            self.recovered_dates[str(url)] = date
                
                if 'title' in df.columns:
                    for _, row in df.iterrows():
                        title = row.get('title')
                        date = self.normalize_date(row.get(date_col))
                        if pd.notna(title) and date:
                            title_key = str(title)[:100]  # Use first 100 chars as key
                            self.recovered_dates[title_key] = date
                            
            except Exception as e:
                continue
        
        print(f"  Recovered {len(self.recovered_dates)} date mappings from structured news")

    
    def recover_from_news_backup(self):
        """Recover dates from archived legacy news backup files by checking file metadata"""
        print("\nRecovering dates from news_backup...")
        backup_dir = Path('data/archive/news/legacy_backup')
        if not backup_dir.exists():
            return
        
        csv_files = list(backup_dir.rglob('*.csv'))
        
        for csv_file in tqdm(csv_files, desc="Processing backup files"):
            try:
                # Extract date from filename if possible
                filename = csv_file.stem
                date_match = re.search(r'(\d{4})[_-](\d{2})[_-](\d{2})', filename)
                file_date = None
                if date_match:
                    year, month, day = date_match.groups()
                    file_date = f"{year}-{month}-{day}"
                
                df = pd.read_csv(csv_file)
                
                # Check for date columns
                date_cols = ['published_date', 'published', 'Date', 'date', 'publish_date', 'timestamp']
                date_col = None
                for col in date_cols:
                    if col in df.columns:
                        date_col = col
                        break
                
                for _, row in df.iterrows():
                    # Try to get date from row
                    row_date = None
                    if date_col:
                        row_date = self.normalize_date(row.get(date_col))
                    
                    # Fallback to file date
                    if not row_date:
                        row_date = file_date
                    
                    if row_date:
                        # Store by URL
                        if 'url' in df.columns and pd.notna(row.get('url')):
                            self.recovered_dates[str(row['url'])] = row_date
                        
                        # Store by title
                        if 'title' in df.columns and pd.notna(row.get('title')):
                            title_key = str(row['title'])[:100]
                            self.recovered_dates[title_key] = row_date
                            
            except Exception as e:
                continue
        
        print(f"  Total date mappings: {len(self.recovered_dates)}")
    
    def apply_recovered_dates(self, df):
        """Apply recovered dates to the dataset"""
        print("\nApplying recovered dates...")
        
        updated_count = 0
        no_date_mask = df['published_date'].isna()
        
        for idx in tqdm(df[no_date_mask].index, desc="Matching records"):
            row = df.loc[idx]
            
            # Try URL match
            if pd.notna(row['url']):
                url_key = str(row['url'])
                if url_key in self.recovered_dates:
                    df.at[idx, 'published_date'] = self.recovered_dates[url_key]
                    df.at[idx, 'date_extraction_method'] = 'recovered_from_source'
                    updated_count += 1
                    continue
            
            # Try title match
            if pd.notna(row['title']):
                title_key = str(row['title'])[:100]
                if title_key in self.recovered_dates:
                    df.at[idx, 'published_date'] = self.recovered_dates[title_key]
                    df.at[idx, 'date_extraction_method'] = 'recovered_from_source'
                    updated_count += 1
        
        print(f"  Updated {updated_count} records with recovered dates")
        return df, updated_count
    
    def process(self, input_path, output_path):
        """Main processing function"""
        print("="*60)
        print("COMPREHENSIVE DATE RECOVERY")
        print("="*60)
        
        # Load dataset
        print("\nLoading dataset...")
        df = pd.read_csv(input_path, low_memory=False)
        print(f"Total records: {len(df)}")
        print(f"Records with dates: {df['published_date'].notna().sum()}")
        print(f"Records without dates: {df['published_date'].isna().sum()}")
        
        # Recover dates from sources
        self.recover_from_structured_news()
        self.recover_from_news_backup()
        
        # Apply recovered dates
        df, updated_count = self.apply_recovered_dates(df)
        
        # Statistics
        print("\n" + "="*60)
        print("RECOVERY RESULTS")
        print("="*60)
        print(f"Records updated: {updated_count}")
        print(f"Total with dates now: {df['published_date'].notna().sum()}")
        print(f"Coverage: {df['published_date'].notna().sum() / len(df) * 100:.1f}%")
        
        # Save
        print(f"\nSaving to: {output_path}")
        df.to_csv(output_path, index=False)
        
        parquet_path = output_path.replace('.csv', '.parquet')
        df.to_parquet(parquet_path, index=False)
        print(f"Saved Parquet: {parquet_path}")
        
        # Update latest
        latest_csv = 'data/processed/news/unified_indian_news_dataset_latest.csv'
        latest_parquet = 'data/processed/news/unified_indian_news_dataset_latest.parquet'
        df.to_csv(latest_csv, index=False)
        df.to_parquet(latest_parquet, index=False)
        print(f"Updated latest versions")
        
        return df

if __name__ == "__main__":
    recovery = ComprehensiveDateRecovery()
    
    input_file = 'data/processed/news/unified_indian_news_dataset_enhanced.csv'
    output_file = 'data/processed/news/unified_indian_news_dataset_final.csv'
    
    df = recovery.process(input_file, output_file)
    
    print("\n" + "="*60)
    print("DATE RECOVERY COMPLETE!")
    print("="*60)
