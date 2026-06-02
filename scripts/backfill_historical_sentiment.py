#!/usr/bin/env python3
"""
Backfill Historical Sentiment Data

Processes historical news datasets from data/raw/historical_news_datasets/
and merges with existing 106 days of sentiment data to create a comprehensive
historical sentiment database.

Real data sources:
- Company-specific news (2005-2025): ~210K headlines
- RBI news (2005-2025): ~56K headlines  
- Sector news (2005-2025): ~56K headlines
- Total: ~266K historical headlines with pre-calculated sentiment scores
"""

import sys
import logging
from pathlib import Path
from datetime import datetime
import pandas as pd
import glob

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_historical_company_news():
    """Load all company-specific historical news."""
    logger.info("Loading company-specific historical news...")
    
    company_files = glob.glob("data/raw/historical_news_datasets/company_*.csv")
    logger.info(f"Found {len(company_files)} company news files")
    
    dfs = []
    for file_path in company_files:
        try:
            df = pd.read_csv(file_path)
            dfs.append(df)
        except Exception as e:
            logger.warning(f"Failed to load {file_path}: {e}")
    
    if dfs:
        combined = pd.concat(dfs, ignore_index=True)
        logger.info(f"Loaded {len(combined)} company news headlines")
        return combined
    
    return pd.DataFrame()


def load_historical_sector_news():
    """Load all sector-level historical news."""
    logger.info("Loading sector-level historical news...")
    
    sector_files = glob.glob("data/raw/historical_news_datasets/sector_*.csv")
    logger.info(f"Found {len(sector_files)} sector news files")
    
    dfs = []
    for file_path in sector_files:
        try:
            df = pd.read_csv(file_path)
            dfs.append(df)
        except Exception as e:
            logger.warning(f"Failed to load {file_path}: {e}")
    
    if dfs:
        combined = pd.concat(dfs, ignore_index=True)
        logger.info(f"Loaded {len(combined)} sector news headlines")
        return combined
    
    return pd.DataFrame()


def load_historical_rbi_news():
    """Load RBI historical news."""
    logger.info("Loading RBI historical news...")
    
    rbi_path = Path("data/raw/historical_news_datasets/rbi_news_sentiment_2005_2025.csv")
    
    if rbi_path.exists():
        df = pd.read_csv(rbi_path)
        logger.info(f"Loaded {len(df)} RBI news headlines")
        return df
    
    logger.warning("RBI news file not found")
    return pd.DataFrame()


def load_existing_sentiment_data():
    """Load existing 106 days of processed sentiment data."""
    logger.info("Loading existing sentiment data...")
    
    # Check for existing processed sentiment
    sentiment_paths = [
        "data/processed/sentiment/market_sentiment.parquet",
        "data/processed/sentiment/daily_sentiment.parquet",
        "data/raw/news_sentiment"
    ]
    
    for path in sentiment_paths:
        path_obj = Path(path)
        if path_obj.exists():
            if path_obj.is_file() and path.endswith('.parquet'):
                df = pd.read_parquet(path)
                logger.info(f"Loaded {len(df)} existing sentiment records from {path}")
                return df
            elif path_obj.is_dir():
                # Load all parquet files in directory
                parquet_files = list(path_obj.glob("*.parquet"))
                if parquet_files:
                    dfs = [pd.read_parquet(f) for f in parquet_files]
                    combined = pd.concat(dfs, ignore_index=True)
                    logger.info(f"Loaded {len(combined)} existing sentiment records from {path}")
                    return combined
    
    logger.warning("No existing sentiment data found")
    return pd.DataFrame()


def standardize_sentiment_schema(df, source_type):
    """Standardize sentiment data schema across different sources."""
    
    # Ensure date column exists
    if 'date' not in df.columns and 'timestamp' in df.columns:
        df['date'] = pd.to_datetime(df['timestamp']).dt.date
    elif 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date']).dt.date
    
    # Standard columns we want
    standard_cols = {
        'date': 'date',
        'sentiment_polarity': 'sentiment_score',
        'sentiment_conviction': 'conviction',
        'sentiment_bias': 'bias',
        'sentiment_surprise': 'surprise',
        'sentiment_uncertainty': 'uncertainty',
        'company_symbol': 'ticker',
        'sector': 'sector',
        'title': 'headline',
        'content_summary': 'summary',
        'source': 'source'
    }
    
    # Rename columns to standard names
    rename_map = {}
    for old_col, new_col in standard_cols.items():
        if old_col in df.columns:
            rename_map[old_col] = new_col
    
    df = df.rename(columns=rename_map)
    
    # Add source type
    df['data_source'] = source_type
    
    # Add processing timestamp
    df['processed_at'] = datetime.utcnow()
    
    return df


def aggregate_daily_sentiment(df):
    """Aggregate sentiment to daily level."""
    logger.info("Aggregating sentiment to daily level...")
    
    # Group by date and calculate daily metrics
    daily = df.groupby('date').agg({
        'sentiment_score': ['mean', 'std', 'count'],
        'conviction': 'mean',
        'bias': 'mean',
        'surprise': 'mean',
        'uncertainty': 'mean'
    }).reset_index()
    
    # Flatten column names
    daily.columns = [
        'date',
        'sentiment_mean',
        'sentiment_std',
        'headline_count',
        'conviction_mean',
        'bias_mean',
        'surprise_mean',
        'uncertainty_mean'
    ]
    
    # Calculate sentiment regime
    daily['sentiment_regime'] = daily['sentiment_mean'].apply(
        lambda x: 'BULLISH' if x > 0.2 else 'BEARISH' if x < -0.2 else 'NEUTRAL'
    )
    
    logger.info(f"Aggregated to {len(daily)} daily records")
    
    return daily


def main():
    """Execute historical sentiment backfill."""
    logger.info("=" * 80)
    logger.info("HISTORICAL SENTIMENT BACKFILL - REAL DATA ONLY")
    logger.info("=" * 80)
    logger.info(f"Started at: {datetime.now()}")
    logger.info("")
    
    # Load all historical data sources
    company_news = load_historical_company_news()
    sector_news = load_historical_sector_news()
    rbi_news = load_historical_rbi_news()
    existing_sentiment = load_existing_sentiment_data()
    
    # Standardize schemas
    datasets = []
    
    if not company_news.empty:
        company_std = standardize_sentiment_schema(company_news, 'historical_company')
        datasets.append(company_std)
        logger.info(f"✅ Company news: {len(company_std)} records")
    
    if not sector_news.empty:
        sector_std = standardize_sentiment_schema(sector_news, 'historical_sector')
        datasets.append(sector_std)
        logger.info(f"✅ Sector news: {len(sector_std)} records")
    
    if not rbi_news.empty:
        rbi_std = standardize_sentiment_schema(rbi_news, 'historical_rbi')
        datasets.append(rbi_std)
        logger.info(f"✅ RBI news: {len(rbi_std)} records")
    
    if not existing_sentiment.empty:
        existing_std = standardize_sentiment_schema(existing_sentiment, 'existing_processed')
        datasets.append(existing_std)
        logger.info(f"✅ Existing sentiment: {len(existing_std)} records")
    
    if not datasets:
        logger.error("❌ No data sources found!")
        return 1
    
    # Combine all datasets
    logger.info("\nCombining all sentiment data...")
    combined = pd.concat(datasets, ignore_index=True)
    logger.info(f"Combined dataset: {len(combined)} total records")
    
    # Remove duplicates (keep most recent processing)
    if 'date' in combined.columns and 'headline' in combined.columns:
        combined = combined.sort_values('processed_at', ascending=False)
        combined = combined.drop_duplicates(subset=['date', 'headline'], keep='first')
        logger.info(f"After deduplication: {len(combined)} records")
    
    # Save detailed sentiment data
    output_dir = Path("data/processed/sentiment")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    detailed_path = output_dir / "historical_sentiment_detailed.parquet"
    combined.to_parquet(detailed_path, index=False)
    logger.info(f"\n✅ Saved detailed sentiment: {detailed_path}")
    logger.info(f"   Records: {len(combined)}")
    
    # Get date range (handle mixed types)
    try:
        date_col = pd.to_datetime(combined['date'])
        date_min = date_col.min()
        date_max = date_col.max()
        logger.info(f"   Date range: {date_min} to {date_max}")
    except Exception as e:
        logger.warning(f"   Could not determine date range: {e}")
    
    # Aggregate to daily level
    daily_sentiment = aggregate_daily_sentiment(combined)
    
    # Save daily aggregated sentiment
    daily_path = output_dir / "daily_sentiment_aggregated.parquet"
    daily_sentiment.to_parquet(daily_path, index=False)
    logger.info(f"\n✅ Saved daily sentiment: {daily_path}")
    logger.info(f"   Days: {len(daily_sentiment)}")
    
    # Get date range for daily data
    try:
        daily_date_col = pd.to_datetime(daily_sentiment['date'])
        daily_min = daily_date_col.min()
        daily_max = daily_date_col.max()
        logger.info(f"   Date range: {daily_min} to {daily_max}")
    except Exception as e:
        logger.warning(f"   Could not determine date range: {e}")
    
    # Summary statistics
    logger.info("\n" + "=" * 80)
    logger.info("BACKFILL SUMMARY")
    logger.info("=" * 80)
    
    logger.info(f"Total headlines processed: {len(combined):,}")
    logger.info(f"Total days covered: {len(daily_sentiment):,}")
    
    # Get date range safely
    try:
        daily_date_col = pd.to_datetime(daily_sentiment['date'])
        date_min = daily_date_col.min()
        date_max = daily_date_col.max()
        logger.info(f"Date range: {date_min.date()} to {date_max.date()}")
        
        # Calculate days span
        days_span = (date_max - date_min).days
        logger.info(f"Days span: {days_span} days")
    except Exception as e:
        logger.warning(f"Could not calculate date range: {e}")
    
    logger.info(f"Average headlines per day: {len(combined) / len(daily_sentiment):.1f}")
    
    # Sentiment regime distribution
    regime_dist = daily_sentiment['sentiment_regime'].value_counts()
    logger.info(f"\nSentiment Regime Distribution:")
    for regime, count in regime_dist.items():
        pct = count / len(daily_sentiment) * 100
        logger.info(f"  {regime}: {count} days ({pct:.1f}%)")
    
    # Data source distribution
    if 'data_source' in combined.columns:
        source_dist = combined['data_source'].value_counts()
        logger.info(f"\nData Source Distribution:")
        for source, count in source_dist.items():
            pct = count / len(combined) * 100
            logger.info(f"  {source}: {count:,} records ({pct:.1f}%)")
    
    logger.info(f"\n✅ Historical sentiment backfill complete!")
    logger.info(f"Completed at: {datetime.now()}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
