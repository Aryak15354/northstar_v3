"""
SentimentState — The formal representation of sentiment in Northstar V3's UnifiedState.

This module defines what "sentiment" means to the system at the state level:
not raw scores, but a set of structured signals that other components can consume
without knowing anything about how sentiment is calculated.

Design rule: SentimentState contains interpretations, not raw scores.
Other components should not do math on sentiment — they consume regime labels
and normalized scores from here.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class SentimentRegime(str, Enum):
    """Sentiment regime classifications."""
    PANIC       = "PANIC"        # Extreme fear, sentiment < -2 std dev
    FEAR        = "FEAR"         # Negative sentiment, -2 to -0.5 std dev
    NEUTRAL     = "NEUTRAL"      # Flat sentiment, -0.5 to +0.5 std dev
    OPTIMISM    = "OPTIMISM"     # Positive sentiment, +0.5 to +2 std dev
    EUPHORIA    = "EUPHORIA"     # Extreme optimism, > +2 std dev
    UNAVAILABLE = "UNAVAILABLE"  # Sentiment pipeline has not run recently enough


class SentimentTrend(str, Enum):
    """Sentiment trend classifications."""
    DETERIORATING = "DETERIORATING"   # Sentiment is getting worse
    STABLE        = "STABLE"          # Sentiment is roughly flat
    IMPROVING     = "IMPROVING"       # Sentiment is getting better
    UNKNOWN       = "UNKNOWN"


@dataclass
class SentimentState:
    """
    Formal sentiment state representation for UnifiedState.
    
    Contains interpreted sentiment signals, not raw scores.
    All consumers read from this state without doing sentiment math.
    """
    # Regime classification
    market_sentiment_regime: SentimentRegime = SentimentRegime.UNAVAILABLE
    sentiment_trend: SentimentTrend = SentimentTrend.UNKNOWN
    
    # Normalized scores (z-scored, so all consumers interpret consistently)
    market_sentiment_zscore: float = 0.0       # z-score of aggregate market sentiment
    sentiment_momentum_1w: float = 0.0         # 1-week sentiment momentum
    sentiment_momentum_1m: float = 0.0         # 1-month sentiment momentum
    sentiment_volatility: float = 0.0          # How much sentiment is swinging
    
    # Regime confidence (how clearly are we in this regime vs borderline?)
    regime_confidence: float = 0.5             # 0.0 to 1.0
    
    # Freshness tracking
    last_updated: Optional[datetime] = None
    pipeline_last_run: Optional[datetime] = None
    is_fresh: bool = False                     # False if pipeline hasn't run today
    data_lag_days: int = 999                   # How many days stale the sentiment is
    
    # Per-company sentiment availability flag
    company_sentiment_available: bool = False  # True if company-level scores exist
    companies_with_coverage: int = 0           # How many tickers have sentiment data
    
    # Crisis detection flag from sentiment
    sentiment_crisis_signal: bool = False      # True if sentiment is in extreme territory
    sentiment_divergence: float = 0.0          # How much market sentiment diverges from price action


def _latest_company_date(company_sentiment_df: pd.DataFrame) -> Optional[datetime]:
    """Extract the latest company sentiment date from either columns or MultiIndex."""
    if company_sentiment_df.empty:
        return None

    if 'Date' in company_sentiment_df.columns:
        values = pd.to_datetime(company_sentiment_df['Date'], errors='coerce').dropna()
        if not values.empty:
            return pd.Timestamp(values.max()).to_pydatetime()

    if isinstance(company_sentiment_df.index, pd.MultiIndex):
        for level_name in company_sentiment_df.index.names:
            if level_name and str(level_name).lower() == 'date':
                values = pd.to_datetime(
                    company_sentiment_df.index.get_level_values(level_name),
                    errors='coerce',
                ).dropna()
                if len(values) > 0:
                    return pd.Timestamp(values.max()).to_pydatetime()

        values = pd.to_datetime(company_sentiment_df.index.get_level_values(-1), errors='coerce').dropna()
        if len(values) > 0:
            return pd.Timestamp(values.max()).to_pydatetime()

    if isinstance(company_sentiment_df.index, pd.DatetimeIndex) and len(company_sentiment_df.index) > 0:
        return pd.Timestamp(company_sentiment_df.index.max()).to_pydatetime()

    return None


def compute_sentiment_state(
    registry,           # IngestionRegistry instance
    as_of_date: datetime,
    sentiment_regime_classifier,  # SentimentRegimeClassifier instance
    market_state=None,  # Optional MarketState for divergence calculation
) -> SentimentState:
    """
    Computes a fresh SentimentState from the sentiment loader and classifier.
    
    Called by the orchestrator at system startup and periodically throughout the day.
    Returns a SentimentState with is_fresh=False if the sentiment pipeline
    hasn't run recently — it does NOT raise an exception. Other components
    must check is_fresh before trusting the sentiment content.
    
    Args:
        registry: IngestionRegistry instance
        as_of_date: Point-in-time date
        sentiment_regime_classifier: SentimentRegimeClassifier instance
        market_state: Optional MarketState for divergence calculation
        
    Returns:
        SentimentState with all fields populated
    """
    try:
        as_of_ts = pd.Timestamp(as_of_date)
        if as_of_ts.tzinfo is not None:
            as_of_ts = as_of_ts.tz_localize(None)

        # Check freshness first
        is_fresh = registry.sentiment.is_sentiment_fresh(as_of_ts.to_pydatetime())
        
        if not is_fresh:
            logger.warning(f"Sentiment data is stale as of {as_of_date}")
            return SentimentState(
                market_sentiment_regime=SentimentRegime.UNAVAILABLE,
                sentiment_trend=SentimentTrend.UNKNOWN,
                is_fresh=False,
                data_lag_days=999,
                last_updated=datetime.now()
            )
        
        # Load market sentiment
        market_sentiment_df = registry.sentiment.load_market_sentiment(as_of_ts.to_pydatetime())
        
        if market_sentiment_df.empty:
            logger.warning("No market sentiment data available")
            return SentimentState(
                market_sentiment_regime=SentimentRegime.UNAVAILABLE,
                is_fresh=False,
                last_updated=datetime.now()
            )
        
        # Extract sentiment series for classification
        if 'sentiment_score' in market_sentiment_df.columns:
            sentiment_series = market_sentiment_df['sentiment_score']
        elif 'raw_score' in market_sentiment_df.columns:
            sentiment_series = market_sentiment_df['raw_score']
        else:
            # Try to find any score column
            score_cols = [c for c in market_sentiment_df.columns if 'score' in c.lower()]
            if score_cols:
                sentiment_series = market_sentiment_df[score_cols[0]]
            else:
                logger.error("No sentiment score column found")
                return SentimentState(
                    market_sentiment_regime=SentimentRegime.UNAVAILABLE,
                    is_fresh=False,
                    last_updated=datetime.now()
                )
        
        # Classify regime and trend
        regime, confidence = sentiment_regime_classifier.classify(sentiment_series, as_of_ts.to_pydatetime())
        trend = sentiment_regime_classifier.classify_trend(sentiment_series, as_of_ts.to_pydatetime())
        
        # Compute z-score (most recent value)
        if len(sentiment_series) >= 30:
            mean = sentiment_series.rolling(252, min_periods=30).mean().iloc[-1]
            std = sentiment_series.rolling(252, min_periods=30).std().iloc[-1]
            if std > 0:
                zscore = (sentiment_series.iloc[-1] - mean) / std
            else:
                zscore = 0.0
        else:
            zscore = 0.0
        
        # Compute momentum
        if len(sentiment_series) >= 7:
            momentum_1w = sentiment_series.rolling(7).mean().iloc[-1] - sentiment_series.rolling(30, min_periods=7).mean().iloc[-1]
        else:
            momentum_1w = 0.0
        
        if len(sentiment_series) >= 30:
            momentum_1m = sentiment_series.rolling(30).mean().iloc[-1] - sentiment_series.rolling(90, min_periods=30).mean().iloc[-1]
        else:
            momentum_1m = 0.0
        
        # Compute volatility
        if len(sentiment_series) >= 30:
            volatility = sentiment_series.rolling(30).std().iloc[-1]
        else:
            volatility = 0.0
        
        # Check for crisis signal
        crisis_signal = regime in [SentimentRegime.PANIC, SentimentRegime.EUPHORIA]
        
        # Compute divergence from price action if market_state provided
        divergence = 0.0
        if market_state is not None and hasattr(market_state, 'nifty_return_5d'):
            # Divergence: sentiment and price moving in opposite directions
            price_direction = 1 if market_state.nifty_return_5d > 0 else -1
            sentiment_direction = 1 if momentum_1w > 0 else -1
            if price_direction != sentiment_direction:
                divergence = abs(zscore) * 0.5  # Scale by sentiment strength
        
        # Check company sentiment availability
        company_sentiment_df = registry.sentiment.load_company_sentiment(as_of_ts.to_pydatetime(), lookback_days=14)
        company_available = not company_sentiment_df.empty
        companies_covered = 0
        if company_available:
            if isinstance(company_sentiment_df.index, pd.MultiIndex):
                ticker_level = next(
                    (name for name in company_sentiment_df.index.names if str(name).lower() == 'ticker'),
                    company_sentiment_df.index.names[0],
                )
                companies_covered = int(company_sentiment_df.index.get_level_values(ticker_level).astype(str).nunique())
            elif 'Ticker' in company_sentiment_df.columns:
                companies_covered = int(company_sentiment_df['Ticker'].astype(str).nunique())

        latest_company_date = _latest_company_date(company_sentiment_df)
        if latest_company_date is not None:
            company_ts = pd.Timestamp(latest_company_date)
            if company_ts.tzinfo is not None:
                company_ts = company_ts.tz_localize(None)
            company_lag = (as_of_ts - company_ts).days
        else:
            company_lag = 999
        
        # Calculate data lag
        if not market_sentiment_df.empty:
            latest_date = market_sentiment_df.index.max()
            latest_ts = pd.Timestamp(latest_date)
            if latest_ts.tzinfo is not None:
                latest_ts = latest_ts.tz_localize(None)
            data_lag = (as_of_ts - latest_ts).days
        else:
            data_lag = 999

        market_fresh = bool(is_fresh and data_lag <= 3)
        company_fresh = bool(company_available and companies_covered > 0 and company_lag <= 7)

        if not market_fresh or not company_fresh:
            logger.warning(
                "Sentiment state degraded: market_lag_days=%s company_lag_days=%s companies_covered=%s",
                data_lag,
                company_lag,
                companies_covered,
            )
        
        return SentimentState(
            market_sentiment_regime=regime if market_fresh else SentimentRegime.UNAVAILABLE,
            sentiment_trend=trend if market_fresh else SentimentTrend.UNKNOWN,
            market_sentiment_zscore=float(zscore),
            sentiment_momentum_1w=float(momentum_1w),
            sentiment_momentum_1m=float(momentum_1m),
            sentiment_volatility=float(volatility),
            regime_confidence=float(confidence),
            last_updated=datetime.now(),
            pipeline_last_run=latest_date if 'latest_date' in locals() else as_of_date,
            is_fresh=market_fresh,
            data_lag_days=data_lag,
            company_sentiment_available=company_available,
            companies_with_coverage=companies_covered,
            sentiment_crisis_signal=bool(crisis_signal and market_fresh),
            sentiment_divergence=float(divergence)
        )
        
    except Exception as e:
        logger.error(f"Error computing sentiment state: {e}", exc_info=True)
        return SentimentState(
            market_sentiment_regime=SentimentRegime.UNAVAILABLE,
            sentiment_trend=SentimentTrend.UNKNOWN,
            is_fresh=False,
            last_updated=datetime.now()
        )
