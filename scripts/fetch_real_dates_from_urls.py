#!/usr/bin/env python3
"""
Fetch real publication dates by scraping article URLs
This extracts actual dates from the article pages
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from tqdm import tqdm
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

class ArticleDateScraper:
    def __init__(self, max_workers=10):
        self.max_workers = max_workers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.success_count = 0
        self.fail_count = 0
        
    def extract_date_from_meta(self, soup):
        """Extract date from meta tags"""
        meta_tags = [
            ('property', 'article:published_time'),
            ('property', 'og:published_time'),
            ('name', 'publish-date'),
            ('name', 'publishdate'),
            ('name', 'date'),
            ('name', 'DC.date.issued'),
            ('property', 'article:modified_time'),
            ('name', 'last-modified'),
        ]
        
        for attr_type, attr_value in meta_tags:
            tag = soup.find('meta', {attr_type: attr_value})
            if tag and tag.get('content'):
                date = self.parse_date(tag['content'])
                if date:
                    return date, 'meta_tag'
        return None, None
    
    def extract_date_from_time_tag(self, soup):
        """Extract from time tags"""
        time_tags = soup.find_all('time')
        for tag in time_tags:
            if tag.get('datetime'):
                date = self.parse_date(tag['datetime'])
                if date:
                    return date, 'time_tag'
        return None, None
    
    def extract_date_from_json_ld(self, soup):
        """Extract from JSON-LD structured data"""
        import json
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0] if data else {}
                
                for field in ['datePublished', 'publishDate', 'dateCreated']:
                    if field in data:
                        date = self.parse_date(data[field])
                        if date:
                            return date, 'json_ld'
            except:
                continue
        return None, None
    
    def parse_date(self, date_str):
        """Parse date string to YYYY-MM-DD"""
        if not date_str:
            return None
        
        try:
            # Try pandas first (handles most formats)
            dt = pd.to_datetime(date_str, errors='coerce')
            if pd.notna(dt) and 2000 <= dt.year <= 2026:
                return dt.strftime('%Y-%m-%d')
        except:
            pass
        
        return None
    
    def scrape_article_date(self, url):
        """Scrape a single article for its date"""
        if pd.isna(url) or not url or 'news.google.com' in str(url):
            return None, 'invalid_url'
        
        try:
            response = self.session.get(url, timeout=10, allow_redirects=True)
            if response.status_code != 200:
                return None, 'http_error'
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try meta tags first (most reliable)
            date, method = self.extract_date_from_meta(soup)
            if date:
                return date, method
            
            # Try time tags
            date, method = self.extract_date_from_time_tag(soup)
            if date:
                return date, method
            
            # Try JSON-LD
            date, method = self.extract_date_from_json_ld(soup)
            if date:
                return date, method
            
            return None, 'not_found'
            
        except requests.Timeout:
            return None, 'timeout'
        except Exception as e:
            return None, f'error'
    
    def process_batch(self, df_batch):
        """Process a batch of URLs"""
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_idx = {
                executor.submit(self.scrape_article_date, row['url']): idx 
                for idx, row in df_batch.iterrows()
            }
            
            for future in tqdm(as_completed(future_to_idx), total=len(future_to_idx), desc="Scraping"):
                idx = future_to_idx[future]
                try:
                    date, method = future.result()
                    results.append((idx, date, method))
                    if date:
                        self.success_count += 1
                    else:
                        self.fail_count += 1
                except Exception as e:
                    results.append((idx, None, 'exception'))
                    self.fail_count += 1
                
                # Small delay to be respectful
                time.sleep(0.05)
        
        return results
    
    def process_dataset(self, input_path, output_path, max_records=None):
        """Process the entire dataset"""
        print("="*60)
        print("FETCHING REAL DATES FROM ARTICLE URLS")
        print("="*60)
        
        # Load dataset
        print("\nLoading dataset...")
        df = pd.read_csv(input_path, low_memory=False)
        print(f"Total records: {len(df):,}")
        
        # Filter records that need dates
        # Remove obviously bad dates (2027-2029)
        bad_date_mask = df['published_date'].isna() | (pd.to_datetime(df['published_date'], errors='coerce').dt.year > 2026)
        df_to_process = df[bad_date_mask].copy()
        
        print(f"Records needing date extraction: {len(df_to_process):,}")
        
        if max_records and len(df_to_process) > max_records:
            print(f"Limiting to first {max_records:,} records")
            df_to_process = df_to_process.head(max_records)
        
        # Process in batches
        print(f"\nScraping {len(df_to_process):,} articles...")
        print(f"Using {self.max_workers} parallel workers")
        
        results = self.process_batch(df_to_process)
        
        # Apply results
        print("\nApplying extracted dates...")
        for idx, date, method in results:
            if date:
                df.at[idx, 'published_date'] = date
                df.at[idx, 'date_extraction_method'] = f'scraped_{method}'
        
        # Statistics
        print("\n" + "="*60)
        print("SCRAPING RESULTS")
        print("="*60)
        print(f"Articles processed: {len(df_to_process):,}")
        print(f"Dates extracted: {self.success_count:,}")
        print(f"Failed: {self.fail_count:,}")
        print(f"Success rate: {self.success_count / len(df_to_process) * 100:.1f}%")
        
        # Clean up bad dates
        dates = pd.to_datetime(df['published_date'], errors='coerce')
        bad_dates = (dates.dt.year > 2026) | (dates.dt.year < 2000)
        df.loc[bad_dates, 'published_date'] = None
        
        print(f"\nTotal records with valid dates: {df['published_date'].notna().sum():,}")
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
        print("Updated latest versions")
        
        return df

if __name__ == "__main__":
    import sys
    
    # Get max records from command line or default to 5000
    max_records = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    
    scraper = ArticleDateScraper(max_workers=10)
    
    input_file = 'data/processed/news/unified_indian_news_dataset_latest.csv'
    output_file = 'data/processed/news/unified_indian_news_dataset_scraped_dates.csv'
    
    print(f"Will process up to {max_records:,} articles")
    print("This may take a while depending on network speed...")
    print()
    
    df = scraper.process_dataset(input_file, output_file, max_records=max_records)
    
    print("\n" + "="*60)
    print("DATE SCRAPING COMPLETE!")
    print("="*60)
    print("\nTo process more records, run:")
    print(f"python scripts/fetch_real_dates_from_urls.py 10000")
