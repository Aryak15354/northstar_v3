#!/usr/bin/env python3
"""
Enhanced Date Extraction for News Dataset
Extracts dates from URLs, filenames, and content where possible
"""

import pandas as pd
import re
from datetime import datetime
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

class DateEnhancer:
    def __init__(self):
        # Common date patterns in URLs
        self.url_patterns = [
            # YYYY/MM/DD or YYYY-MM-DD
            r'/(\d{4})[/-](\d{1,2})[/-](\d{1,2})/',
            r'/(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b',
            # YYYYMMDD
            r'/(\d{4})(\d{2})(\d{2})/',
            # news/2020/05/article-name
            r'/news/(\d{4})/(\d{1,2})/',
            # article-2020-05-15
            r'-(\d{4})-(\d{1,2})-(\d{1,2})',
            # /2020/article-name
            r'/(\d{4})/',
        ]
        
        # Month name patterns
        self.month_patterns = {
            'january': '01', 'jan': '01',
            'february': '02', 'feb': '02',
            'march': '03', 'mar': '03',
            'april': '04', 'apr': '04',
            'may': '05',
            'june': '06', 'jun': '06',
            'july': '07', 'jul': '07',
            'august': '08', 'aug': '08',
            'september': '09', 'sep': '09', 'sept': '09',
            'october': '10', 'oct': '10',
            'november': '11', 'nov': '11',
            'december': '12', 'dec': '12'
        }
    
    def extract_date_from_url(self, url):
        """Extract date from URL patterns"""
        if pd.isna(url) or url == '':
            return None
        
        url_lower = str(url).lower()
        
        # Try each pattern
        for pattern in self.url_patterns:
            match = re.search(pattern, url_lower)
            if match:
                groups = match.groups()
                try:
                    if len(groups) == 3:
                        year, month, day = groups
                        year = int(year)
                        month = int(month)
                        day = int(day)
                        
                        # Validate date
                        if 2000 <= year <= 2026 and 1 <= month <= 12 and 1 <= day <= 31:
                            return f"{year:04d}-{month:02d}-{day:02d}"
                    elif len(groups) == 2:
                        year, month = groups
                        year = int(year)
                        month = int(month)
                        
                        if 2000 <= year <= 2026 and 1 <= month <= 12:
                            return f"{year:04d}-{month:02d}-01"
                    elif len(groups) == 1:
                        year = int(groups[0])
                        if 2000 <= year <= 2026:
                            return f"{year:04d}-01-01"
                except (ValueError, IndexError):
                    continue
        
        # Try month name patterns (e.g., /2020/may/article)
        for month_name, month_num in self.month_patterns.items():
            pattern = rf'/(\d{{4}})/{month_name}/'
            match = re.search(pattern, url_lower)
            if match:
                year = int(match.group(1))
                if 2000 <= year <= 2026:
                    return f"{year:04d}-{month_num}-01"
        
        return None
    
    def extract_date_from_content(self, content, title):
        """Extract date from content or title"""
        text = ''
        if pd.notna(content):
            text += str(content)[:500]  # First 500 chars
        if pd.notna(title):
            text += ' ' + str(title)
        
        if not text:
            return None
        
        # Look for date patterns in text
        # Pattern: Month DD, YYYY or DD Month YYYY
        patterns = [
            r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2}),?\s+(\d{4})',
            r'(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december),?\s+(\d{4})',
            r'(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\s+(\d{1,2}),?\s+(\d{4})',
        ]
        
        text_lower = text.lower()
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                groups = match.groups()
                try:
                    if groups[0].isdigit():
                        day, month_name, year = groups
                    else:
                        month_name, day, year = groups
                    
                    month_num = self.month_patterns.get(month_name.lower())
                    if month_num:
                        year = int(year)
                        day = int(day)
                        if 2000 <= year <= 2026 and 1 <= day <= 31:
                            return f"{year:04d}-{month_num}-{day:02d}"
                except (ValueError, AttributeError):
                    continue
        
        return None
    
    def enhance_dataset(self, input_path, output_path):
        """Enhance the dataset with extracted dates"""
        print("Loading dataset...")
        df = pd.read_csv(input_path)
        
        print(f"Total records: {len(df)}")
        print(f"Records with dates: {df['published_date'].notna().sum()}")
        
        # Find records without dates
        no_date_mask = df['published_date'].isna()
        no_date_count = no_date_mask.sum()
        print(f"Records without dates: {no_date_count}")
        
        if no_date_count == 0:
            print("All records already have dates!")
            return df
        
        print("\nExtracting dates from URLs and content...")
        
        extracted_dates = []
        extraction_methods = []
        
        for idx, row in tqdm(df[no_date_mask].iterrows(), total=no_date_count):
            extracted_date = None
            method = None
            
            # Try URL first
            if pd.notna(row['url']):
                extracted_date = self.extract_date_from_url(row['url'])
                if extracted_date:
                    method = 'url'
            
            # Try content/title if URL didn't work
            if not extracted_date:
                extracted_date = self.extract_date_from_content(row['content'], row['title'])
                if extracted_date:
                    method = 'content'
            
            extracted_dates.append(extracted_date)
            extraction_methods.append(method)
        
        # Update the dataframe
        df.loc[no_date_mask, 'published_date'] = extracted_dates
        df.loc[no_date_mask, 'date_extraction_method'] = extraction_methods
        
        # Add extraction method column for all records
        if 'date_extraction_method' not in df.columns:
            df['date_extraction_method'] = None
        df.loc[~no_date_mask, 'date_extraction_method'] = 'original'
        
        # Statistics
        print("\n" + "="*60)
        print("Date Enhancement Results")
        print("="*60)
        print(f"Original records with dates: {(~no_date_mask).sum()}")
        print(f"Dates extracted from URLs: {(df['date_extraction_method'] == 'url').sum()}")
        print(f"Dates extracted from content: {(df['date_extraction_method'] == 'content').sum()}")
        print(f"Total records with dates now: {df['published_date'].notna().sum()}")
        print(f"Records still without dates: {df['published_date'].isna().sum()}")
        print(f"Coverage: {df['published_date'].notna().sum() / len(df) * 100:.1f}%")
        
        # Save enhanced dataset
        print(f"\nSaving enhanced dataset to: {output_path}")
        df.to_csv(output_path, index=False)
        
        # Also save as parquet
        parquet_path = output_path.replace('.csv', '.parquet')
        df.to_parquet(parquet_path, index=False)
        print(f"Saved Parquet: {parquet_path}")
        
        # Generate updated statistics
        self.generate_statistics(df, output_path.replace('.csv', '_statistics.txt'))
        
        return df
    
    def generate_statistics(self, df, stats_path):
        """Generate updated statistics"""
        with open(stats_path, 'w') as f:
            f.write("="*60 + "\n")
            f.write("Enhanced News Dataset Statistics\n")
            f.write("="*60 + "\n\n")
            
            f.write(f"Total Records: {len(df)}\n\n")
            
            f.write("Date Coverage:\n")
            f.write(f"  With dates: {df['published_date'].notna().sum()} ({df['published_date'].notna().sum()/len(df)*100:.1f}%)\n")
            f.write(f"  Without dates: {df['published_date'].isna().sum()} ({df['published_date'].isna().sum()/len(df)*100:.1f}%)\n\n")
            
            if 'date_extraction_method' in df.columns:
                f.write("Date Extraction Methods:\n")
                f.write(df['date_extraction_method'].value_counts().to_string())
                f.write("\n\n")
            
            if df['published_date'].notna().any():
                f.write("Date Range:\n")
                dates = pd.to_datetime(df['published_date'], errors='coerce')
                f.write(f"  Earliest: {dates.min()}\n")
                f.write(f"  Latest: {dates.max()}\n\n")
                
                # Year distribution
                f.write("Records by Year:\n")
                years = dates.dt.year.value_counts().sort_index()
                f.write(years.to_string())
                f.write("\n\n")
            
            f.write("Records by Source:\n")
            f.write(df['source'].value_counts().head(20).to_string())
            f.write("\n\n")
            
            f.write("Records by Category:\n")
            f.write(df['category'].value_counts().head(20).to_string())
            f.write("\n")
        
        print(f"Statistics saved to: {stats_path}")

if __name__ == "__main__":
    enhancer = DateEnhancer()
    
    input_file = 'data/processed/news/unified_indian_news_dataset_latest.csv'
    output_file = 'data/processed/news/unified_indian_news_dataset_enhanced.csv'
    
    print("="*60)
    print("NEWS DATASET DATE ENHANCEMENT")
    print("="*60)
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")
    print()
    
    df_enhanced = enhancer.enhance_dataset(input_file, output_file)
    
    print("\n" + "="*60)
    print("ENHANCEMENT COMPLETE!")
    print("="*60)
