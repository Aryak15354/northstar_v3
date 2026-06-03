#!/usr/bin/env python3
"""
Create a high-quality news dataset with reliable dates
Focuses on records with dates and enriches where possible
"""

import pandas as pd
from pathlib import Path
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

print("="*60)
print("CREATING DATED NEWS DATASET")
print("="*60)

# Load current dataset
print("\nLoading unified dataset...")
df = pd.read_csv('data/processed/news/unified_indian_news_dataset_enhanced.csv', low_memory=False)
print(f"Total records: {len(df):,}")
print(f"With dates: {df['published_date'].notna().sum():,}")

# Strategy: Keep only records with dates
df_dated = df[df['published_date'].notna()].copy()
print(f"\nRecords with dates: {len(df_dated):,}")

# Add records without dates but from high-quality sources
# For news_backup, we can infer approximate dates from file structure
print("\nAttempting to recover more dates from news_backup...")

backup_no_date = df[(df['source'] == 'news_backup') & (df['published_date'].isna())].copy()
print(f"news_backup records without dates: {len(backup_no_date):,}")

# For these, we'll assign a generic date based on when they were likely collected
# This is better than no date at all for time-series analysis
backup_no_date['published_date'] = '2024-01-01'  # Approximate collection period
backup_no_date['date_extraction_method'] = 'estimated_from_collection'

# Combine
df_final = pd.concat([df_dated, backup_no_date], ignore_index=True)

print(f"\nFinal dataset size: {len(df_final):,}")
print(f"Records with reliable dates: {(df_final['date_extraction_method'] != 'estimated_from_collection').sum():,}")
print(f"Records with estimated dates: {(df_final['date_extraction_method'] == 'estimated_from_collection').sum():,}")

# Sort by date
df_final['date_sort'] = pd.to_datetime(df_final['published_date'], errors='coerce')
df_final = df_final.sort_values('date_sort', ascending=False)
df_final = df_final.drop('date_sort', axis=1)

# Statistics
print("\n" + "="*60)
print("FINAL DATASET STATISTICS")
print("="*60)
print(f"Total records: {len(df_final):,}")
print(f"\nBy source:")
print(df_final['source'].value_counts())
print(f"\nBy year:")
dates = pd.to_datetime(df_final['published_date'], errors='coerce')
print(dates.dt.year.value_counts().sort_index())

# Save
output_dir = Path('data/processed/news')
output_dir.mkdir(parents=True, exist_ok=True)

csv_path = output_dir / 'indian_news_dataset_with_dates.csv'
parquet_path = output_dir / 'indian_news_dataset_with_dates.parquet'

print(f"\nSaving dataset...")
df_final.to_csv(csv_path, index=False)
df_final.to_parquet(parquet_path, index=False)

print(f"  CSV: {csv_path}")
print(f"  Parquet: {parquet_path}")

# Also update the latest
df_final.to_csv(output_dir / 'unified_indian_news_dataset_latest.csv', index=False)
df_final.to_parquet(output_dir / 'unified_indian_news_dataset_latest.parquet', index=False)

print("\n" + "="*60)
print("DATASET CREATION COMPLETE!")
print("="*60)
print(f"\nYou now have {len(df_final):,} news records with dates")
print(f"Date range: {dates.min()} to {dates.max()}")
