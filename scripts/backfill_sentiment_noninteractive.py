#!/usr/bin/env python3
"""
Non-interactive sentiment backfill using real 3.9M news headlines.
Processes existing news data and generates sentiment scores.
"""
import pandas as pd
from pathlib import Path
from datetime import datetime
import sys
import os

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.sentiment.sentiment_pipeline_runner import SentimentPipelineRunner

def main():
    print("=" * 80)
    print("SENTIMENT BACKFILL - NON-INTERACTIVE")
    print("=" * 80)
    
    # Check if news data exists
    news_files = [
        "data/raw/news/india-news-headlines.csv",
        "data/raw/news/IN-FINews Dataset.csv",
        "data/raw/news/News_Articles_Indian_Express.csv"
    ]
    
    total_rows = 0
    for nf in news_files:
        if Path(nf).exists():
            try:
                df = pd.read_csv(nf, nrows=1)
                row_count = sum(1 for _ in open(nf)) - 1  # Subtract header
                total_rows += row_count
                print(f"✓ Found {nf}: {row_count:,} rows")
            except Exception as e:
                print(f"✗ Error reading {nf}: {e}")
    
    print(f"\nTotal news headlines available: {total_rows:,}")
    
    if total_rows == 0:
        print("ERROR: No news data found")
        return 1
    
    print("\nProcessing sentiment from real news data...")
    print("This will take 15-30 minutes depending on system speed.")
    
    try:
        # Initialize pipeline runner
        runner = SentimentPipelineRunner()
        
        # Run backfill
        print("\nStep 1: Processing historical news...")
        result = runner.run_backfill(
            start_date=datetime(2020, 1, 1),
            end_date=datetime.now(),
            batch_size=10000
        )
        
        print(f"\n✅ Backfill complete!")
        print(f"   Processed: {result.get('rows_processed', 0):,} headlines")
        print(f"   Generated: {result.get('sentiment_rows', 0):,} sentiment records")
        
        # Verify output
        output_file = Path("data/processed/sentiment/market_sentiment_daily.parquet")
        if output_file.exists():
            df = pd.read_parquet(output_file)
            print(f"\n✅ Output file created: {len(df)} days of sentiment data")
            print(f"   Date range: {df.index.min()} to {df.index.max()}")
        else:
            print(f"\n⚠️  Output file not found at {output_file}")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error during backfill: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())
