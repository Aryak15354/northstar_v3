"""
SentimentLoader — Load processed sentiment scores from the sentiment pipeline.

Data sources:
- data/sentiment/v3/ — V3 sentiment scores
- data/processed/sentiment/ — Processed company sentiment
- data/raw/news/ — Raw news data (research/rebuilding mode only)
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

import pandas as pd
import numpy as np

from .base_loader import BaseLoader

logger = logging.getLogger(__name__)


CANONICAL_COMPANY_COLUMNS = [
    'ticker',
    'date',
    'availability_date',
    'sentiment_polarity',
    'sentiment_conviction',
]

CANONICAL_MARKET_COLUMNS = [
    'date',
    'availability_date',
    'india_market_polarity',
    'india_market_conviction',
]

# Backward-compatible aliases for existing imports.
CANONICAL_COMPANY_SENTIMENT_COLUMNS = CANONICAL_COMPANY_COLUMNS
CANONICAL_MARKET_SENTIMENT_COLUMNS = CANONICAL_MARKET_COLUMNS


class SentimentLoader(BaseLoader):
    """Loads sentiment data with proper PIT enforcement."""

    @staticmethod
    def _resolve_parquet_candidate(base_path: Path, filename: str) -> Path:
        if base_path.is_dir():
            return base_path / filename
        return base_path

    def _latest_available_date(
        self,
        df: pd.DataFrame,
        *,
        date_column: str,
        availability_column: str,
        fallback_lag_days: int = 1,
    ) -> Optional[pd.Timestamp]:
        if df.empty:
            return None

        if availability_column in df.columns:
            values = pd.to_datetime(df[availability_column], errors='coerce').dropna()
            if not values.empty:
                return pd.Timestamp(values.max())

        if date_column in df.columns:
            values = pd.to_datetime(df[date_column], errors='coerce').dropna()
            if not values.empty:
                return pd.Timestamp(values.max()) + timedelta(days=fallback_lag_days)

        return None

    @staticmethod
    def _empty_company_sentiment_frame() -> pd.DataFrame:
        empty = pd.DataFrame(
            columns=[
                'Ticker',
                'Date',
                'AvailabilityDate',
                'sentiment_polarity',
                'sentiment_conviction',
                'sentiment_score',
                'sentiment_score_1d',
                'sentiment_score_7d',
                'sentiment_score_30d',
                'sentiment_momentum',
                'sentiment_volatility',
            ]
        )
        return empty.set_index(['Ticker', 'Date'])

    @staticmethod
    def _empty_market_sentiment_frame() -> pd.DataFrame:
        empty = pd.DataFrame(
            columns=[
                'Date',
                'AvailabilityDate',
                'india_market_polarity',
                'india_market_conviction',
                'sentiment_score',
            ]
        )
        return empty.set_index('Date')

    def _validate_company_sentiment_schema(self, df: pd.DataFrame) -> bool:
        missing = [c for c in CANONICAL_COMPANY_COLUMNS if c not in df.columns]
        if missing:
            logger.error(
                "Company sentiment schema mismatch. Missing columns=%s actual_columns=%s",
                missing,
                list(df.columns),
            )
            return False
        return True

    def _validate_market_sentiment_schema(self, df: pd.DataFrame) -> bool:
        missing = [c for c in CANONICAL_MARKET_COLUMNS if c not in df.columns]
        if missing:
            logger.error(
                "Market sentiment schema mismatch. Missing columns=%s actual_columns=%s",
                missing,
                list(df.columns),
            )
            return False
        return True
    
    def load(self, as_of_date: datetime, **kwargs) -> pd.DataFrame:
        """
        Load sentiment data (delegates to load_company_sentiment).
        
        Args:
            as_of_date: Point-in-time date
            **kwargs: Additional parameters for load_company_sentiment
            
        Returns:
            DataFrame with sentiment data
        """
        return self.load_company_sentiment(as_of_date, **kwargs)
    
    def load_company_sentiment(
        self,
        as_of_date: datetime,
        tickers: Optional[List[str]] = None,
        lookback_days: int = 30
    ) -> pd.DataFrame:
        """
        Load company-level sentiment scores.
        
        Uses the canonical daily sentiment dataset with explicit availability dates.

        CRITICAL: Sentiment scores can only use articles published BEFORE as_of_date.
        Today's sentiment cannot use today's news.

        Args:
            as_of_date: Point-in-time date
            tickers: List of tickers (None = all)
            lookback_days: Days of history to include

        Returns:
            DataFrame with (Ticker, Date) as index and sentiment metrics
        """
        start_time = pd.Timestamp.now()
        as_of_ts = pd.Timestamp(as_of_date)
        if as_of_ts.tzinfo is not None:
            as_of_ts = as_of_ts.tz_localize(None)

        # Normalize tickers - add .NS suffix if not present
        if tickers:
            normalized_tickers = []
            for ticker in tickers:
                if not ticker.endswith('.NS') and not ticker.endswith('.BO'):
                    normalized_tickers.append(f"{ticker}.NS")
                else:
                    normalized_tickers.append(ticker)
            tickers = normalized_tickers

        try:
            company_default = 'data/canonical/sentiment/company_sentiment_daily.parquet'
            sentiment_path = Path(
                self.paths_config.get(
                    'company_sentiment_path',
                    self.paths_config.get('company_sentiment', company_default),
                )
            )
            sentiment_path = self._resolve_parquet_candidate(sentiment_path, 'company_sentiment_daily.parquet')

            if not sentiment_path.exists():
                logger.warning("Canonical company sentiment data not found, trying processed sentiment...")
                processed_path = Path('data/processed/sentiment/ticker_sentiment_daily.parquet')
                sentiment_path = self._resolve_parquet_candidate(processed_path, 'ticker_sentiment_daily.parquet')

            if not sentiment_path.exists():
                logger.error("Company sentiment data not found at canonical or processed paths")
                return self._empty_company_sentiment_frame()

            df = pd.read_parquet(sentiment_path)
            logger.info(f"Loaded {len(df):,} sentiment records from {sentiment_path.name}")

            if not self._validate_company_sentiment_schema(df):
                logger.error(
                    "Company sentiment data does not match canonical schema. "
                    "Expected columns: %s",
                    CANONICAL_COMPANY_COLUMNS,
                )
                return self._empty_company_sentiment_frame()

            df = df.rename(
                columns={
                    'ticker': 'Ticker',
                    'date': 'Date',
                    'availability_date': 'AvailabilityDate',
                }
            )
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df['AvailabilityDate'] = pd.to_datetime(df['AvailabilityDate'], errors='coerce')

            # Filter by tickers
            if tickers and 'Ticker' in df.columns:
                df = df[df['Ticker'].isin(tickers)]

            # Remove timezone if present
            if df['Date'].dt.tz is not None:
                df['Date'] = df['Date'].dt.tz_localize(None)
            if df['AvailabilityDate'].dt.tz is not None:
                df['AvailabilityDate'] = df['AvailabilityDate'].dt.tz_localize(None)

            df['sentiment_score'] = pd.to_numeric(df['sentiment_polarity'], errors='coerce').fillna(0.0)
            if 'sentiment_conviction' in df.columns:
                df['sentiment_conviction'] = pd.to_numeric(df['sentiment_conviction'], errors='coerce').fillna(0.0)

            df = df[df['AvailabilityDate'] <= as_of_ts].copy()
            self._validate_pit(df, 'AvailabilityDate', as_of_ts)
            
            # Log if data is stale (but don't fail - degrade gracefully)
            latest_date = df['Date'].max() if not df.empty else None
            if latest_date is not None and pd.notna(latest_date):
                latest_ts = pd.Timestamp(latest_date)
                if latest_ts.tzinfo is not None:
                    latest_ts = latest_ts.tz_localize(None)
                days_stale = (as_of_ts - latest_ts).days
                if days_stale > 7:
                    logger.warning(f"Sentiment data is {days_stale} days stale (latest: {latest_date.date()})")

            # Filter by lookback
            start_date = as_of_ts - timedelta(days=lookback_days)
            df = df[df['Date'] >= start_date]

            # Compute rolling aggregations
            df = self._compute_sentiment_features(df)

            # Set index
            if 'Ticker' in df.columns:
                df = df.set_index(['Ticker', 'Date'])

            elapsed_ms = (pd.Timestamp.now() - start_time).total_seconds() * 1000
            self._log_load(len(df), len(df.columns), str(sentiment_path), elapsed_ms, as_of_ts)

            return df

        except Exception as e:
            logger.error(f"Error loading company sentiment: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self._empty_company_sentiment_frame()
    
    def _compute_sentiment_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute sentiment rolling aggregations."""
        if 'sentiment_score' not in df.columns:
            if 'sentiment_polarity' in df.columns:
                df['sentiment_score'] = pd.to_numeric(df['sentiment_polarity'], errors='coerce').fillna(0.0)
            else:
                logger.warning("Sentiment score column missing and no canonical polarity column available")
                return df
        
        if 'sentiment_score' in df.columns and 'Ticker' in df.columns:
            df = df.sort_values(['Ticker', 'Date'])
            
            # 1-day sentiment (yesterday's average)
            df['sentiment_score_1d'] = df.groupby('Ticker')['sentiment_score'].shift(1)
            
            # 7-day rolling average
            df['sentiment_score_7d'] = df.groupby('Ticker')['sentiment_score'].transform(
                lambda x: x.rolling(7, min_periods=1).mean()
            )
            
            # 30-day rolling average
            df['sentiment_score_30d'] = df.groupby('Ticker')['sentiment_score'].transform(
                lambda x: x.rolling(30, min_periods=7).mean()
            )
            
            # Sentiment momentum (7d - 30d)
            df['sentiment_momentum'] = df['sentiment_score_7d'] - df['sentiment_score_30d']
            
            # Sentiment volatility (30-day std)
            df['sentiment_volatility'] = df.groupby('Ticker')['sentiment_score'].transform(
                lambda x: x.rolling(30, min_periods=7).std()
            )
        
        return df
    
    def load_market_sentiment(self, as_of_date: datetime) -> pd.DataFrame:
        """
        Load aggregate market-level sentiment.
        
        Args:
            as_of_date: Point-in-time date
            
        Returns:
            DataFrame with Date as index and market sentiment metrics
        """
        try:
            as_of_ts = pd.Timestamp(as_of_date)
            if as_of_ts.tzinfo is not None:
                as_of_ts = as_of_ts.tz_localize(None)

            market_path = Path(
                self.paths_config.get(
                    'market_sentiment_path',
                    'data/canonical/sentiment/market_sentiment_daily.parquet',
                )
            )
            market_path = self._resolve_parquet_candidate(market_path, 'market_sentiment_daily.parquet')
            
            if not market_path.exists():
                # Fall back to processed
                market_path = Path('data/processed/sentiment/market_sentiment_daily.parquet')
                market_path = self._resolve_parquet_candidate(market_path, 'market_sentiment_daily.parquet')
            
            if not market_path.exists():
                logger.warning("Market sentiment data not found")
                return self._empty_market_sentiment_frame()
            
            df = pd.read_parquet(market_path)

            if not self._validate_market_sentiment_schema(df):
                logger.error(
                    "Market sentiment data does not match canonical schema. "
                    "Expected columns: %s",
                    CANONICAL_MARKET_COLUMNS,
                )
                return self._empty_market_sentiment_frame()

            df = df.rename(columns={'date': 'Date', 'availability_date': 'AvailabilityDate'})
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df['AvailabilityDate'] = pd.to_datetime(df['AvailabilityDate'], errors='coerce')
            if getattr(df['Date'].dt, 'tz', None) is not None:
                df['Date'] = df['Date'].dt.tz_localize(None)
            if getattr(df['AvailabilityDate'].dt, 'tz', None) is not None:
                df['AvailabilityDate'] = df['AvailabilityDate'].dt.tz_localize(None)

            df = df[df['AvailabilityDate'] <= as_of_ts].copy()
            self._validate_pit(df, 'AvailabilityDate', as_of_ts)
            df['sentiment_score'] = pd.to_numeric(df['india_market_polarity'], errors='coerce').fillna(0.0)
            return df.set_index('Date')
            
        except Exception as e:
            logger.error(f"Error loading market sentiment: {e}")
            return self._empty_market_sentiment_frame()
    
    def is_sentiment_fresh(self, as_of_date: datetime) -> bool:
        """
        Check if sentiment data is fresh enough to use.
        
        Args:
            as_of_date: Point-in-time date
            
        Returns:
            True if sentiment is fresh, False if stale
        """
        try:
            market_path = Path(
                self.paths_config.get(
                    'market_sentiment_path',
                    'data/canonical/sentiment/market_sentiment_daily.parquet',
                )
            )
            market_path = self._resolve_parquet_candidate(market_path, 'market_sentiment_daily.parquet')

            company_path = Path(
                self.paths_config.get(
                    'company_sentiment_path',
                    self.paths_config.get('company_sentiment', 'data/canonical/sentiment/company_sentiment_daily.parquet'),
                )
            )
            company_path = self._resolve_parquet_candidate(company_path, 'company_sentiment_daily.parquet')

            if not market_path.exists() or not company_path.exists():
                logger.warning("Sentiment artifacts missing (market=%s, company=%s)", market_path.exists(), company_path.exists())
                return False

            market_df = pd.read_parquet(market_path)
            company_df = pd.read_parquet(company_path)

            market_available = self._latest_available_date(
                market_df,
                date_column='date',
                availability_column='availability_date',
                fallback_lag_days=1,
            )
            company_available = self._latest_available_date(
                company_df,
                date_column='date',
                availability_column='availability_date',
                fallback_lag_days=1,
            )

            if market_available is None or company_available is None:
                logger.warning("Could not determine sentiment availability dates")
                return False

            as_of_ts = pd.Timestamp(as_of_date)
            if as_of_ts.tzinfo is not None:
                as_of_ts = as_of_ts.tz_localize(None)

            market_available = pd.Timestamp(market_available)
            if market_available.tzinfo is not None:
                market_available = market_available.tz_localize(None)

            company_available = pd.Timestamp(company_available)
            if company_available.tzinfo is not None:
                company_available = company_available.tz_localize(None)

            market_age_days = (as_of_ts.normalize() - market_available.normalize()).days
            company_age_days = (as_of_ts.normalize() - company_available.normalize()).days

            if market_age_days > 3:
                logger.warning("Market sentiment data is %s days old", market_age_days)
                return False

            if company_age_days > 7:
                logger.warning("Company sentiment data is %s days old", company_age_days)
                return False

            return True

        except Exception as e:
            logger.error(f"Error checking sentiment freshness: {e}")
            return False
