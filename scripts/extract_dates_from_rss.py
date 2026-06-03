#!/usr/bin/env python3
"""
Extract dates from RSS feed URLs by fetching actual article content
This script handles Google News RSS URLs and extracts publication dates
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from tqdm import tqdm
import time
from urllib.parse import urlparse, parse_qs, unquote
import warnings
warnings.filterwarnings('ignore')

class RSSDateExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.success_count = 0
        self.fail_count = 0
        self.cache = {}
        
    def decode_google_news_url(self, url):
        """Decode Google News RSS URL to get actual article URL"""
        try:
            # Google News RSS URLs often contain the actual URL encoded
            if 'news.google.com' in url:
                # Try to extract from URL parameters
                parsed = urlparse(url)
                
                # Check if it's a redirect URL
                if '/articles/' in url:
                    # These are encoded article IDs, we need to fetch to get real URL
                    return None
                
                # Check query parameters
                params = parse_qs(parsed.query)
                if 'url' in params:
                    return unquote(params['url'][0])
            
            return url
        except:
            return url
    
    def fetch_article_date(self, url, timeout=10):
        """Fetch article and extract publication date"""
        if pd.isna(url) or url == '':
            return None, 'no_url'
        
        # Check cache
        if url in self.cache:
            return self.cache[url]
        
        try:
            # Decode Google News URL if needed
            actual_url = self.decode_google_news_url(url)
            if not actual_url:
                actual_url = url
            
            # Fetch the page
            response = self.session.get(actual_url, timeout=timeout, allow_redirects=True)
            
            if response.status_code != 200:
                self.cache[url] = (None, 'http_error')
                return None, 'http_error'
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Strategy 1: Look for meta tags (most reliable)
            date = self.extract_from_meta_tags(soup)
            if date:
                self.cache[url] = (date, 'meta_tag')
                return date, 'meta_tag'
            
            # Strategy 2: Look for time tags
            date = self.extract_from_time_tags(soup)
            if date:
                self.cache[url] = (date, 'time_tag')
                return date, 'time_tag'
            
            # Strategy 3: Look for JSON-LD structured data
            date = self.extract_from_json_ld(soup)
            if date:
                self.cache[url] = (date, 'json_ld')
                return date, 'json_ld'
            
            # Strategy 4: Look for common date patterns in text
            date = self.extract_from_text_patterns(soup)
            if date:
                self.cache[url] = (date, 'text_pattern')
                return date, 'text_pattern'
            
            self.cache[url] = (None, 'not_found')
            return None, 'not_found'
            
        except requests.Timeout:
            self.cache[url] = (None, 'timeout')
            return None, 'timeout'
        except Exception as e:
            self.cache[url] = (None, f'error_{type(e).__name__}')
            return None, f'error_{type(e).__name__}'
    
    def extract_from_meta_tags(self, soup):
        """Extract date from meta tags"""
        meta_properties = [
            'article:published_time',
            'article:published',
            'datePublished',
            'publishdate',
            'DC.date.issued',
            'date',
            'pubdate',
            'publish-date',
            'publication-date',
            'og:published_time',
            'article:modified_time'
        ]
        
        for prop in meta_properties:
            # Try property attribute
            tag = soup.find('meta', property=prop)
            if tag and tag.get('content'):
                date = self.parse_date_string(tag['content'])
                if date:
                    return date
            
            # Try name attribute
            tag = soup.find('meta', attrs={'name': prop})
            if tag and tag.get('content'):
                date = self.parse_date_string(tag['content'])
                if date:
                    return date
        
        return None
    
    def extract_from_time_tags(self, soup):
        """Extract date from time tags"""
        time_tags = soup.find_all('time')
        for tag in time_tags:
            # Check datetime attribute
            if tag.get('datetime'):
                date = self.parse_date_string(tag['datetime'])
                if date:
                    return date
            
            # Check text content
            if tag.text:
                date = self.parse_date_string(tag.text)
                if date:
                    return date
        
        return None
    
    def extract_from_json_ld(self, soup):
        """Extract date from JSON-LD structured data"""
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                import json
                data = json.loads(script.string)
                
                # Handle both single objects and arrays
                if isinstance(data, list):
                    for item in data:
                        date = self.extract_date_from_json_obj(item)
                        if date:
                            return date
                else:
                    date = self.extract_date_from_json_obj(data)
                    if date:
                        return date
            except:
                continue
        
        return None
    
    def extract_date_from_json_obj(self, obj):
        """Extract date from JSON object"""
        if not isinstance(obj, dict):
            return None
        
        date_fields = ['datePublished', 'publishDate', 'dateCreated', 'uploadDate', 'dateModified']
        for field in date_fields:
            if field in obj:
                date = self.parse_date_string(obj[field])
                if date:
                    return date
        
        return None
    
    def extract_from_text_patterns(self, soup):
        """Extract date from common text patterns"""
        # Look in common date containers
        date_classes = ['date', 'published', 'timestamp', 'post-date', 'article-date', 'byline']
        
        for class_name in date_classes:
            elements = soup.find_all(class_=re.compile(class_name, re.I))
            for elem in elements:
                date = self.parse_date_string(elem.get_text())
                if date:
                    return date
        
        return None
    
    def parse_date_string(self, date_str):
        """Parse various date string formats to YYYY-MM-DD"""
        if not date_str:
            return None
        
        date_str = str(date_str).strip()
        
        # Common formats to try
        formats = [
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%dT%H:%M:%S.%f%z',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
            '%d/%m/%Y',
            '%m/%d/%Y',
            '%d-%m-%Y',
            '%B %d, %Y',
            '%b %d, %Y',
            '%d %B %Y',
            '%d %b %Y',
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str[:25], fmt)  # Limit length for timezone issues
                if 2000 <= dt.year <= 2026:
                    return dt.strftime('%Y-%m-%d')
            except:
                continue
        
        # Try pandas to_datetime as fallback
        try:
            dt = pd.to_datetime(date_str, errors='coerce')
            if pd.notna(dt) and 2000 <= dt.year <= 2026:
                return dt.strftime('%Y-%m-%d')
        except:
            pass
        
        return None
    
    def process_dataset(self, input_path, output_path, max_records=None, batch_size=100):
        """Process dataset and extract dates from RSS URLs"""
        print("Loading dataset...")
        df = pd.read_csv(input_path, low_memory=False)
        
        print(f"Total records: {len(df)}")
        
        # Focus on records without dates
        no_date_mask = df['published_date'].isna()
        no_date_df = df[no_date_mask].copy()
        
        print(f"Records without dates: {len(no_date_df)}")
        
        if max_records:
            no_date_df = no_date_df.head(max_records)
            print(f"Processing first {max_records} records")
        
        # Extract dates
        extracted_dates = []
        extraction_methods = []
        
        print("\nExtracting dates from URLs...")
        for idx, row in tqdm(no_date_df.iterrows(), total=len(no_date_df)):
            date, method = self.fetch_article_date(row['url'])
            extracted_dates.append(date)
            extraction_methods.append(method)
            
            if date:
                self.success_count += 1
            else:
                self.fail_count += 1
            
            # Rate limiting
            time.sleep(0.1)
            
            # Progress update every batch
            if (self.success_count + self.fail_count) % batch_size == 0:
                success_rate = self.success_count / (self.success_count + self.fail_count) * 100
                print(f"\n  Progress: {self.success_count} success, {self.fail_count} failed ({success_rate:.1f}% success rate)")
        
        # Update dataframe
        no_date_df['published_date'] = extracted_dates
        no_date_df['date_extraction_method'] = extraction_methods
        
        # Merge back
        df.update(no_date_df)
        
        # Add extraction method column if not exists
        if 'date_extraction_method' not in df.columns:
            df['date_extraction_method'] = None
        
        # Statistics
        print("\n" + "="*60)
        print("RSS Date Extraction Results")
        print("="*60)
        print(f"Total processed: {len(no_date_df)}")
        print(f"Successfully extracted: {self.success_count}")
        print(f"Failed: {self.fail_count}")
        print(f"Success rate: {self.success_count / len(no_date_df) * 100:.1f}%")
        
        print(f"\nTotal records with dates now: {df['published_date'].notna().sum()}")
        print(f"Coverage: {df['published_date'].notna().sum() / len(df) * 100:.1f}%")
        
        # Save
        print(f"\nSaving to: {output_path}")
        df.to_csv(output_path, index=False)
        
        parquet_path = output_path.replace('.csv', '.parquet')
        df.to_parquet(parquet_path, index=False)
        print(f"Saved Parquet: {parquet_path}")
        
        return df

if __name__ == "__main__":
    import sys
    
    extractor = RSSDateExtractor()
    
    input_file = 'data/processed/news/unified_indian_news_dataset_enhanced.csv'
    output_file = 'data/processed/news/unified_indian_news_dataset_with_rss_dates.csv'
    
    # Process first 10000 records as a test (you can increase this)
    max_records = 10000 if len(sys.argv) == 1 else int(sys.argv[1])
    
    print("="*60)
    print("RSS DATE EXTRACTION")
    print("="*60)
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")
    print(f"Max records to process: {max_records}")
    print()
    
    df = extractor.process_dataset(input_file, output_file, max_records=max_records)
    
    print("\n" + "="*60)
    print("EXTRACTION COMPLETE!")
    print("="*60)
