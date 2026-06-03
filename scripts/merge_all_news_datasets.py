#!/usr/bin/env python3
"""
Comprehensive News Dataset Merger
Merges all news datasets from multiple sources into a unified, deduplicated dataset
"""

import pandas as pd
import numpy as np
from pathlib import Path
import hashlib
from datetime import datetime
import re
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

class NewsDatasetMerger:
    def __init__(self):
        self.unified_schema = {
            'title': str,
            'content': str,
            'summary': str,
            'url': str,
            'published_date': str,
            'source': str,
            'sentiment': str,
            'category': str,
            'author': str,
            'keywords': str,
            'content_hash': str,
            'url_hash': str
        }
        self.all_records = []
        
    def generate_content_hash(self, text):
        """Generate hash for content-based deduplication"""
        if pd.isna(text) or text == '':
            return None
        # Normalize text: lowercase, remove extra spaces, punctuation
        normalized = re.sub(r'[^\w\s]', '', str(text).lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def generate_url_hash(self, url):
        """Generate hash for URL-based deduplication"""
        if pd.isna(url) or url == '':
            return None
        # Normalize URL
        normalized = str(url).lower().strip()
        # Remove trailing slashes and query parameters for better matching
        normalized = re.sub(r'[?#].*$', '', normalized)
        normalized = normalized.rstrip('/')
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def normalize_date(self, date_val):
        """Normalize various date formats to YYYY-MM-DD"""
        if pd.isna(date_val):
            return None
        
        try:
            # Handle numeric dates (like 20010102)
            if isinstance(date_val, (int, float)):
                date_str = str(int(date_val))
                if len(date_str) == 8:
                    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            
            # Try parsing as datetime
            date_obj = pd.to_datetime(date_val, errors='coerce')
            if pd.notna(date_obj):
                return date_obj.strftime('%Y-%m-%d')
        except:
            pass
        
        return str(date_val) if date_val else None
    
    def load_huggingface_datasets(self):
        """Load the 3 downloaded Hugging Face datasets"""
        print("\n" + "="*60)
        print("Loading Hugging Face Datasets")
        print("="*60)
        
        hf_datasets = [
            ('data/raw/news/indian_financial_news_train.csv', 'kdave_indian_financial_news'),
            ('data/raw/news/harixn_indian_news_sentiment_train.csv', 'harixn_sentiment'),
            ('data/raw/news/pranali_indian_financial_news_train.csv', 'pranali_financial_news')
        ]
        
        for path, source_name in hf_datasets:
            print(f"\nLoading: {source_name}")
            try:
                df = pd.read_csv(path)
                print(f"  Rows: {len(df)}")
                
                if 'URL' in df.columns and 'Content' in df.columns:
                    # kdave and pranali format
                    for _, row in tqdm(df.iterrows(), total=len(df), desc=f"  Processing {source_name}"):
                        record = {
                            'title': None,
                            'content': row.get('Content'),
                            'summary': row.get('Summary'),
                            'url': row.get('URL'),
                            'published_date': None,
                            'source': source_name,
                            'sentiment': row.get('Sentiment'),
                            'category': 'financial',
                            'author': None,
                            'keywords': None
                        }
                        self.all_records.append(record)
                
                elif 'text' in df.columns and 'label' in df.columns:
                    # harixn format
                    for _, row in tqdm(df.iterrows(), total=len(df), desc=f"  Processing {source_name}"):
                        record = {
                            'title': None,
                            'content': row.get('text'),
                            'summary': None,
                            'url': None,
                            'published_date': None,
                            'source': source_name,
                            'sentiment': row.get('label'),
                            'category': 'financial',
                            'author': None,
                            'keywords': None
                        }
                        self.all_records.append(record)
                
                print(f"  ✓ Loaded {len(df)} records")
            except Exception as e:
                print(f"  ✗ Error loading {source_name}: {e}")
    
    def load_existing_csv_datasets(self):
        """Load existing CSV datasets from data/raw/news"""
        print("\n" + "="*60)
        print("Loading Existing CSV Datasets")
        print("="*60)
        
        csv_datasets = [
            ('data/raw/news/IN-FINews Dataset.csv', 'in_fi_news'),
            ('data/raw/news/india-news-headlines.csv', 'india_headlines'),
            ('data/raw/news/News_Articles_Indian_Express.csv', 'indian_express')
        ]
        
        for path, source_name in csv_datasets:
            print(f"\nLoading: {source_name}")
            try:
                df = pd.read_csv(path)
                print(f"  Rows: {len(df)}")
                
                if source_name == 'in_fi_news':
                    for _, row in tqdm(df.iterrows(), total=len(df), desc=f"  Processing {source_name}"):
                        record = {
                            'title': row.get('Title'),
                            'content': row.get('Content'),
                            'summary': row.get('Description'),
                            'url': row.get('URL'),
                            'published_date': self.normalize_date(row.get('Date')),
                            'source': source_name,
                            'sentiment': None,
                            'category': 'financial',
                            'author': row.get('Author'),
                            'keywords': row.get('Keywords')
                        }
                        self.all_records.append(record)
                
                elif source_name == 'india_headlines':
                    for _, row in tqdm(df.iterrows(), total=len(df), desc=f"  Processing {source_name}"):
                        record = {
                            'title': row.get('headline_text'),
                            'content': None,
                            'summary': None,
                            'url': None,
                            'published_date': self.normalize_date(row.get('publish_date')),
                            'source': source_name,
                            'sentiment': None,
                            'category': row.get('headline_category', 'general'),
                            'author': None,
                            'keywords': None
                        }
                        self.all_records.append(record)
                
                elif source_name == 'indian_express':
                    for _, row in tqdm(df.iterrows(), total=len(df), desc=f"  Processing {source_name}"):
                        record = {
                            'title': row.get('headline'),
                            'content': row.get('articles'),
                            'summary': row.get('desc'),
                            'url': row.get('url'),
                            'published_date': self.normalize_date(row.get('date')),
                            'source': source_name,
                            'sentiment': None,
                            'category': row.get('article_type', 'general'),
                            'author': None,
                            'keywords': None
                        }
                        self.all_records.append(record)
                
                print(f"  ✓ Loaded {len(df)} records")
            except Exception as e:
                print(f"  ✗ Error loading {source_name}: {e}")
    
    def load_structured_news_folders(self):
        """Load news from data/news structured folders"""
        print("\n" + "="*60)
        print("Loading Structured News Folders (data/news)")
        print("="*60)
        
        news_dir = Path('data/news')
        csv_files = list(news_dir.rglob('*.csv'))
        
        print(f"Found {len(csv_files)} CSV files")
        
        for csv_file in tqdm(csv_files, desc="Processing structured news files"):
            try:
                df = pd.read_csv(csv_file)
                
                # Determine category from path
                parts = csv_file.parts
                category = 'general'
                if 'sectors' in parts:
                    idx = parts.index('sectors')
                    if idx + 1 < len(parts):
                        category = parts[idx + 1]
                elif 'macro_news' in parts:
                    category = 'macro'
                elif 'commodities' in parts:
                    category = 'commodities'
                elif 'forex' in parts:
                    category = 'forex'
                elif 'equities' in parts:
                    category = 'equities'
                
                for _, row in df.iterrows():
                    record = {
                        'title': row.get('title'),
                        'content': row.get('description') or row.get('summary'),
                        'summary': row.get('summary') or row.get('description'),
                        'url': row.get('url'),
                        'published_date': self.normalize_date(row.get('published_date') or row.get('published') or row.get('Date')),
                        'source': f"structured_news_{category}",
                        'sentiment': None,
                        'category': category,
                        'author': None,
                        'keywords': row.get('query')
                    }
                    self.all_records.append(record)
                
            except Exception as e:
                print(f"  Warning: Could not process {csv_file}: {e}")
        
        print(f"  ✓ Loaded records from structured folders")
    
    def load_news_backup(self):
        """Load news from data/archive/news/legacy_backup"""
        print("\n" + "="*60)
        print("Loading News Backup (data/archive/news/legacy_backup)")
        print("="*60)
        
        backup_dir = Path('data/archive/news/legacy_backup')
        if not backup_dir.exists():
            print("  No backup directory found")
            return
        
        csv_files = list(backup_dir.rglob('*.csv'))
        print(f"Found {len(csv_files)} CSV files in backup")
        
        for csv_file in tqdm(csv_files, desc="Processing backup files"):
            try:
                df = pd.read_csv(csv_file)
                
                for _, row in df.iterrows():
                    record = {
                        'title': row.get('title') or row.get('headline') or row.get('Title'),
                        'content': row.get('content') or row.get('description') or row.get('Content'),
                        'summary': row.get('summary') or row.get('Summary'),
                        'url': row.get('url') or row.get('URL'),
                        'published_date': self.normalize_date(row.get('published_date') or row.get('date') or row.get('Date')),
                        'source': 'news_backup',
                        'sentiment': row.get('sentiment') or row.get('Sentiment'),
                        'category': 'backup',
                        'author': row.get('author') or row.get('Author'),
                        'keywords': row.get('keywords') or row.get('Keywords')
                    }
                    self.all_records.append(record)
                
            except Exception as e:
                print(f"  Warning: Could not process {csv_file}: {e}")
        
        print(f"  ✓ Loaded records from backup")
    
    def deduplicate_records(self):
        """Remove duplicate records based on content and URL hashes"""
        print("\n" + "="*60)
        print("Deduplicating Records")
        print("="*60)
        
        print(f"Total records before deduplication: {len(self.all_records)}")
        
        # Convert to DataFrame
        df = pd.DataFrame(self.all_records)
        
        # Generate hashes
        print("Generating content hashes...")
        df['content_hash'] = df.apply(
            lambda row: self.generate_content_hash(
                str(row['content']) if pd.notna(row['content']) else str(row['title'])
            ), axis=1
        )
        
        print("Generating URL hashes...")
        df['url_hash'] = df['url'].apply(self.generate_url_hash)
        
        # Remove duplicates
        initial_count = len(df)
        
        # First pass: Remove exact URL duplicates (keep first occurrence)
        df_dedup = df.drop_duplicates(subset=['url_hash'], keep='first')
        url_removed = initial_count - len(df_dedup)
        print(f"  Removed {url_removed} URL duplicates")
        
        # Second pass: Remove content duplicates (for records without URLs)
        no_url_mask = df_dedup['url_hash'].isna()
        df_with_url = df_dedup[~no_url_mask]
        df_no_url = df_dedup[no_url_mask].drop_duplicates(subset=['content_hash'], keep='first')
        
        df_final = pd.concat([df_with_url, df_no_url], ignore_index=True)
        content_removed = len(df_dedup) - len(df_final)
        print(f"  Removed {content_removed} content duplicates")
        
        print(f"\nFinal record count: {len(df_final)}")
        print(f"Total duplicates removed: {initial_count - len(df_final)}")
        
        return df_final
    
    def save_unified_dataset(self, df, output_dir='data/processed/news'):
        """Save the unified dataset"""
        print("\n" + "="*60)
        print("Saving Unified Dataset")
        print("="*60)
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save as CSV
        csv_path = output_path / f'unified_indian_news_dataset_{timestamp}.csv'
        df.to_csv(csv_path, index=False)
        print(f"  ✓ Saved CSV: {csv_path}")
        
        # Save as Parquet (more efficient)
        parquet_path = output_path / f'unified_indian_news_dataset_{timestamp}.parquet'
        df.to_parquet(parquet_path, index=False)
        print(f"  ✓ Saved Parquet: {parquet_path}")
        
        # Save latest version (without timestamp)
        latest_csv = output_path / 'unified_indian_news_dataset_latest.csv'
        df.to_csv(latest_csv, index=False)
        print(f"  ✓ Saved Latest CSV: {latest_csv}")
        
        latest_parquet = output_path / 'unified_indian_news_dataset_latest.parquet'
        df.to_parquet(latest_parquet, index=False)
        print(f"  ✓ Saved Latest Parquet: {latest_parquet}")
        
        # Generate statistics
        self.generate_statistics(df, output_path / f'dataset_statistics_{timestamp}.txt')
        
        return csv_path, parquet_path
    
    def generate_statistics(self, df, stats_path):
        """Generate dataset statistics"""
        with open(stats_path, 'w') as f:
            f.write("="*60 + "\n")
            f.write("Unified Indian News Dataset Statistics\n")
            f.write("="*60 + "\n\n")
            
            f.write(f"Total Records: {len(df)}\n\n")
            
            f.write("Records by Source:\n")
            f.write(df['source'].value_counts().to_string())
            f.write("\n\n")
            
            f.write("Records by Category:\n")
            f.write(df['category'].value_counts().to_string())
            f.write("\n\n")
            
            f.write("Records with Sentiment:\n")
            f.write(f"  With sentiment: {df['sentiment'].notna().sum()}\n")
            f.write(f"  Without sentiment: {df['sentiment'].isna().sum()}\n\n")
            
            if df['sentiment'].notna().any():
                f.write("Sentiment Distribution:\n")
                f.write(df['sentiment'].value_counts().to_string())
                f.write("\n\n")
            
            f.write("Records with URL: {}\n".format(df['url'].notna().sum()))
            f.write("Records with Content: {}\n".format(df['content'].notna().sum()))
            f.write("Records with Summary: {}\n".format(df['summary'].notna().sum()))
            f.write("Records with Date: {}\n".format(df['published_date'].notna().sum()))
            f.write("Records with Author: {}\n".format(df['author'].notna().sum()))
            f.write("Records with Keywords: {}\n".format(df['keywords'].notna().sum()))
            
            if df['published_date'].notna().any():
                f.write("\nDate Range:\n")
                dates = pd.to_datetime(df['published_date'], errors='coerce')
                f.write(f"  Earliest: {dates.min()}\n")
                f.write(f"  Latest: {dates.max()}\n")
        
        print(f"  ✓ Saved Statistics: {stats_path}")
    
    def run(self):
        """Execute the complete merging pipeline"""
        print("\n" + "="*60)
        print("UNIFIED INDIAN NEWS DATASET MERGER")
        print("="*60)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Load all datasets
        self.load_huggingface_datasets()
        self.load_existing_csv_datasets()
        self.load_structured_news_folders()
        self.load_news_backup()
        
        # Deduplicate
        df_unified = self.deduplicate_records()
        
        # Save
        csv_path, parquet_path = self.save_unified_dataset(df_unified)
        
        print("\n" + "="*60)
        print("MERGE COMPLETE!")
        print("="*60)
        print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\nUnified dataset saved:")
        print(f"  CSV: {csv_path}")
        print(f"  Parquet: {parquet_path}")
        print(f"\nTotal unique records: {len(df_unified)}")

if __name__ == "__main__":
    merger = NewsDatasetMerger()
    merger.run()
