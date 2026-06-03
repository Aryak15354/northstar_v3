"""
SentimentRegimeClassifier — Converts sentiment scores into regime labels.

This classifier does NOT use machine learning. It uses a rolling z-score with
hysteresis to prevent rapid regime switching. The design principle: regime labels
should be stable (not flip every day) but responsive (detect sustained shifts within 3-5 days).

Hysteresis means: once you're in FEAR, you need sentiment to reach the NEUTRAL threshold
PLUS a buffer before you transition to NEUTRAL. This prevents the classifier from
oscillating between two regimes when sentiment is at the boundary.
"""

import logging
from datetime import datetime, timedelta
from typing import Tuple, Dict

import pandas as pd
import numpy as np

from .sentiment_state import SentimentRegime, SentimentTrend

logger = logging.getLogger(__name__)


class SentimentRegimeClassifier:
    """
    Classifies sentiment time series into regime labels with hysteresis.
    
    Uses z-score thresholds with smoothing and hysteresis to prevent
    rapid regime switching at boundaries.
    """
    
    def __init__(self, config: dict = None):
        """
        Initialize classifier with configuration.
        
        Args:
            config: Configuration dict with sentiment_regime section
        """
        if config is None:
            config = {}
        
        regime_config = config.get('sentiment_regime', {})
        
        # Configuration parameters
        self.lookback_days = regime_config.get('lookback_days', 252)
        self.smoothing_days = regime_config.get('smoothing_days', 5)
        self.hysteresis_buffer = regime_config.get('hysteresis_buffer', 0.25)
        self.min_history_days = regime_config.get('min_history_days', 60)
        self.staleness_threshold_days = regime_config.get('staleness_threshold_days', 3)
        
        # Regime thresholds (z-score based)
        thresholds = regime_config.get('thresholds', {})
        self.panic_lower = thresholds.get('panic_lower', -2.0)
        self.fear_lower = thresholds.get('fear_lower', -0.5)
        self.neutral_upper = thresholds.get('neutral_upper', 0.5)
        self.euphoria_upper = thresholds.get('euphoria_upper', 2.0)
        
        # Trend thresholds
        self.trend_threshold = regime_config.get('trend_threshold', 0.1)
        
        # Internal state for hysteresis
        self._current_regime = SentimentRegime.NEUTRAL
        self._last_classification_date = None

    def classify(
        self,
        sentiment_series: pd.Series,
        as_of_date: datetime
    ) -> Tuple[SentimentRegime, float]:
        """
        Classify sentiment regime with hysteresis.
        
        Args:
            sentiment_series: Date-indexed Series of daily market sentiment scores up to T-1
            as_of_date: Point-in-time date for classification
            
        Returns:
            Tuple of (SentimentRegime, confidence_score) where confidence is 0.0 to 1.0
        """
        try:
            as_of_ts = pd.Timestamp(as_of_date)
            if as_of_ts.tzinfo is not None:
                as_of_ts = as_of_ts.tz_localize(None)

            # Check minimum history requirement
            if len(sentiment_series) < self.min_history_days:
                logger.warning(f"Insufficient sentiment history: {len(sentiment_series)} days < {self.min_history_days}")
                return (SentimentRegime.UNAVAILABLE, 0.0)
            
            # Check staleness
            if isinstance(sentiment_series.index[-1], pd.Timestamp):
                latest_date = sentiment_series.index[-1]
            else:
                latest_date = pd.Timestamp(sentiment_series.index[-1])

            if latest_date.tzinfo is not None:
                latest_date = latest_date.tz_localize(None)
            
            days_stale = (as_of_ts - latest_date).days
            if days_stale > self.staleness_threshold_days:
                logger.warning(f"Sentiment data is {days_stale} days stale")
                return (SentimentRegime.UNAVAILABLE, 0.0)
            
            # Apply EMA smoothing
            smoothed = sentiment_series.ewm(span=self.smoothing_days, adjust=False).mean()
            
            # The sentiment pipeline already emits normalized daily scores, so
            # the classifier thresholds the smoothed signal directly rather than
            # re-z-scoring it against its own recent history.
            zscore = pd.to_numeric(smoothed.iloc[-1], errors="coerce")
            zscore = 0.0 if pd.isna(zscore) else float(zscore)
            
            # Classify with hysteresis
            regime = self._classify_with_hysteresis(zscore)
            
            # Compute confidence based on distance from boundaries
            confidence = self._compute_confidence(zscore, regime)
            
            # Update internal state
            self._current_regime = regime
            self._last_classification_date = as_of_ts.to_pydatetime()
            
            return (regime, confidence)
            
        except Exception as e:
            logger.error(f"Error classifying sentiment regime: {e}", exc_info=True)
            return (SentimentRegime.UNAVAILABLE, 0.0)
    
    def _classify_with_hysteresis(self, zscore: float) -> SentimentRegime:
        """
        Classify z-score into regime with hysteresis to prevent oscillation.
        
        Args:
            zscore: Current sentiment z-score
            
        Returns:
            SentimentRegime classification
        """
        # Determine raw regime (without hysteresis)
        if zscore < self.panic_lower:
            raw_regime = SentimentRegime.PANIC
        elif zscore < self.fear_lower:
            raw_regime = SentimentRegime.FEAR
        elif zscore < self.neutral_upper:
            raw_regime = SentimentRegime.NEUTRAL
        elif zscore < self.euphoria_upper:
            raw_regime = SentimentRegime.OPTIMISM
        else:
            raw_regime = SentimentRegime.EUPHORIA

        # Bootstrap the very first classification without hysteresis so the
        # classifier can establish a real starting regime from the data.
        if self._last_classification_date is None:
            return raw_regime
        
        # Apply hysteresis: only transition if we exceed threshold + buffer
        if raw_regime == self._current_regime:
            return raw_regime
        
        # Check if we've exceeded the threshold by enough to transition
        if raw_regime == SentimentRegime.PANIC and zscore < (self.panic_lower - self.hysteresis_buffer):
            return SentimentRegime.PANIC
        elif raw_regime == SentimentRegime.FEAR and self._current_regime == SentimentRegime.PANIC:
            # Transitioning up from PANIC to FEAR
            if zscore > (self.panic_lower + self.hysteresis_buffer):
                return SentimentRegime.FEAR
            return self._current_regime
        elif raw_regime == SentimentRegime.NEUTRAL:
            # Transitioning to NEUTRAL from either side
            if self._current_regime == SentimentRegime.FEAR and zscore > (self.fear_lower + self.hysteresis_buffer):
                return SentimentRegime.NEUTRAL
            elif self._current_regime == SentimentRegime.OPTIMISM and zscore < (self.neutral_upper - self.hysteresis_buffer):
                return SentimentRegime.NEUTRAL
            return self._current_regime
        elif raw_regime == SentimentRegime.OPTIMISM and self._current_regime == SentimentRegime.NEUTRAL:
            # Transitioning up from NEUTRAL to OPTIMISM
            if zscore > (self.neutral_upper + self.hysteresis_buffer):
                return SentimentRegime.OPTIMISM
            return self._current_regime
        elif raw_regime == SentimentRegime.EUPHORIA and zscore > (self.euphoria_upper + self.hysteresis_buffer):
            return SentimentRegime.EUPHORIA
        
        # Default: stay in current regime
        return self._current_regime
    
    def _compute_confidence(self, zscore: float, regime: SentimentRegime) -> float:
        """
        Compute confidence score based on distance from regime boundaries.
        
        Deeper into a regime = higher confidence.
        Right at the boundary = lower confidence.
        
        Args:
            zscore: Current sentiment z-score
            regime: Classified regime
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        if regime == SentimentRegime.UNAVAILABLE:
            return 0.0
        
        # Calculate distance from nearest boundary
        if regime == SentimentRegime.PANIC:
            # Distance below panic threshold
            distance = abs(zscore - self.panic_lower)
            confidence = min(1.0, 0.3 + distance * 0.35)
        elif regime == SentimentRegime.FEAR:
            # Distance from both boundaries
            dist_to_panic = abs(zscore - self.panic_lower)
            dist_to_neutral = abs(zscore - self.fear_lower)
            distance = min(dist_to_panic, dist_to_neutral)
            confidence = min(1.0, 0.3 + distance * 0.7)
        elif regime == SentimentRegime.NEUTRAL:
            # Distance from both boundaries
            dist_to_fear = abs(zscore - self.fear_lower)
            dist_to_optimism = abs(zscore - self.neutral_upper)
            distance = min(dist_to_fear, dist_to_optimism)
            confidence = min(1.0, 0.5 + distance * 0.5)
        elif regime == SentimentRegime.OPTIMISM:
            # Distance from both boundaries
            dist_to_neutral = abs(zscore - self.neutral_upper)
            dist_to_euphoria = abs(zscore - self.euphoria_upper)
            distance = min(dist_to_neutral, dist_to_euphoria)
            confidence = min(1.0, 0.3 + distance * 0.7)
        else:  # EUPHORIA
            # Distance above euphoria threshold
            distance = abs(zscore - self.euphoria_upper)
            confidence = min(1.0, 0.3 + distance * 0.35)
        
        return float(confidence)
    
    def classify_trend(
        self,
        sentiment_series: pd.Series,
        as_of_date: datetime
    ) -> SentimentTrend:
        """
        Classify sentiment trend (improving, deteriorating, stable).
        
        Compares 7-day EMA to 30-day EMA to determine trend direction.
        
        Args:
            sentiment_series: Date-indexed Series of daily market sentiment scores
            as_of_date: Point-in-time date
            
        Returns:
            SentimentTrend classification
        """
        try:
            if len(sentiment_series) < 30:
                return SentimentTrend.UNKNOWN
            
            # Compute EMAs
            ema_7d = sentiment_series.ewm(span=7, adjust=False).mean().iloc[-1]
            ema_30d = sentiment_series.ewm(span=30, adjust=False).mean().iloc[-1]
            
            # Compare
            diff = ema_7d - ema_30d
            
            if diff > self.trend_threshold:
                return SentimentTrend.IMPROVING
            elif diff < -self.trend_threshold:
                return SentimentTrend.DETERIORATING
            else:
                return SentimentTrend.STABLE
                
        except Exception as e:
            logger.error(f"Error classifying sentiment trend: {e}")
            return SentimentTrend.UNKNOWN
    
    def get_regime_history(
        self,
        sentiment_series: pd.Series,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """
        Generate historical regime classifications for a date range.
        
        Used by Research Engine to backfill historical regime labels.
        
        Args:
            sentiment_series: Complete sentiment time series
            start_date: Start of classification period
            end_date: End of classification period
            
        Returns:
            DataFrame with (Date) as index and (regime, confidence, zscore, smoothed_score) columns
        """
        results = []
        
        # Reset internal state for historical classification
        original_regime = self._current_regime
        self._current_regime = SentimentRegime.NEUTRAL
        
        try:
            # Filter series to date range
            mask = (sentiment_series.index >= start_date) & (sentiment_series.index <= end_date)
            date_range = sentiment_series.index[mask]
            
            for date in date_range:
                # Get series up to this date
                series_up_to_date = sentiment_series[sentiment_series.index <= date]
                
                if len(series_up_to_date) < self.min_history_days:
                    results.append({
                        'Date': date,
                        'regime': SentimentRegime.UNAVAILABLE.value,
                        'confidence': 0.0,
                        'zscore': 0.0,
                        'smoothed_score': 0.0
                    })
                    continue
                
                # Classify
                regime, confidence = self.classify(series_up_to_date, date)
                
                # Compute smoothed score and zscore
                smoothed = series_up_to_date.ewm(span=self.smoothing_days, adjust=False).mean()
                current_value = smoothed.iloc[-1]
                zscore = pd.to_numeric(current_value, errors="coerce")
                zscore = 0.0 if pd.isna(zscore) else float(zscore)
                
                results.append({
                    'Date': date,
                    'regime': regime.value,
                    'confidence': confidence,
                    'zscore': zscore,
                    'smoothed_score': current_value
                })
            
            df = pd.DataFrame(results)
            if not df.empty:
                df = df.set_index('Date')
            
            return df
            
        except Exception as e:
            logger.error(f"Error generating regime history: {e}", exc_info=True)
            return pd.DataFrame()
        finally:
            # Restore original state
            self._current_regime = original_regime
