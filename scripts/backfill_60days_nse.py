#!/usr/bin/env python3
"""Simple 60-day NSE news backfill for Gap 2"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add repo to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.signals.sentiment_bridge import SentimentBridge

def main():
    print("=" * 60)
    print("60-DAY NSE NEWS BACKFILL")
    print("=" * 60)
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)
    
    print(f"\nDate range: {start_date.date()} to {end_date.date()}")
    print("Source: NSE announcements only")
    print("\nStarting backfill...")
    
    # Initialize bridge
    bridge = SentimentBridge(
        duckdb_path="data/sentiment.duckdb",
        output_dir="data/processed/sentiment"
    )
    
    # Export with incremental mode
    exports = bridge.export_all(start_date=str(start_date.date()))
    
    ticker_df = exports.get('ticker')
    market_df = exports.get('market')
    
    print("\n" + "=" * 60)
    print("BACKFILL COMPLETE")
    print("=" * 60)
    
    if ticker_df is not None and not ticker_df.empty:
        print(f"\nTicker sentiment: {len(ticker_df)} rows")
        print(f"  Unique tickers: {ticker_df['ticker'].nunique()}")
        print(f"  Date range: {ticker_df['date'].min()} to {ticker_df['date'].max()}")
    else:
        print("\n⚠️  No ticker sentiment data")
    
    if market_df is not None and not market_df.empty:
        print(f"\nMarket sentiment: {len(market_df)} rows")
        print(f"  Date range: {market_df['date'].min()} to {market_df['date'].max()}")
    else:
        print("\n⚠️  No market sentiment data")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
