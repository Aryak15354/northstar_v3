"""
Tests for SentimentRegimeClassifier.
"""

import pytest
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from src.sentiment.sentiment_regime import SentimentRegimeClassifier
from src.sentiment.sentiment_state import SentimentRegime, SentimentTrend


def test_regime_thresholds():
    """Test regime classification at clear thresholds."""
    classifier = SentimentRegimeClassifier()
    
    # Create synthetic series with clear PANIC signal (z-score = -2.5)
    dates = pd.date_range('2024-01-01', '2024-06-14', freq='D')
    # Create scores that will result in z-score around -2.5
    scores = np.ones(len(dates)) * -2.5
    sentiment_series = pd.Series(scores, index=dates)
    
    as_of_date = datetime(2024, 6, 15)
    regime, confidence = classifier.classify(sentiment_series, as_of_date)
    
    # Should classify as PANIC with high confidence
    assert regime == SentimentRegime.PANIC
    assert confidence > 0.3  # At least moderate confidence


def test_hysteresis():
    """Test hysteresis prevents rapid regime switching."""
    config = {
        'sentiment_regime': {
            'lookback_days': 252,
            'smoothing_days': 5,
            'hysteresis_buffer': 0.25,
            'min_history_days': 60,
            'thresholds': {
                'panic_lower': -2.0,
                'fear_lower': -0.5,
                'neutral_upper': 0.5,
                'euphoria_upper': 2.0
            }
        }
    }
    classifier = SentimentRegimeClassifier(config)
    
    # Create series that starts in FEAR and crosses into NEUTRAL zone by small amount
    dates = pd.date_range('2024-01-01', '2024-06-14', freq='D')
    scores = np.ones(len(dates)) * -0.6  # Clearly in FEAR
    
    # Last 10 days cross into NEUTRAL zone but only by 0.1 (not enough for hysteresis)
    scores[-10:] = -0.4  # Just above FEAR threshold of -0.5
    
    sentiment_series = pd.Series(scores, index=dates)
    
    # First classify to establish FEAR regime
    as_of_date = datetime(2024, 6, 5)
    regime1, _ = classifier.classify(sentiment_series[:len(scores)-10], as_of_date)
    assert regime1 == SentimentRegime.FEAR
    
    # Now classify with the boundary-crossing data
    as_of_date = datetime(2024, 6, 15)
    regime2, _ = classifier.classify(sentiment_series, as_of_date)
    
    # Should stay in FEAR due to hysteresis (0.1 < 0.25 buffer)
    assert regime2 == SentimentRegime.FEAR


def test_unavailable_on_short_history():
    """Test classifier returns UNAVAILABLE with insufficient history."""
    classifier = SentimentRegimeClassifier()
    
    # Create series with only 30 days (below min_history_days=60)
    dates = pd.date_range('2024-05-15', '2024-06-14', freq='D')
    scores = np.random.randn(len(dates))
    sentiment_series = pd.Series(scores, index=dates)
    
    as_of_date = datetime(2024, 6, 15)
    regime, confidence = classifier.classify(sentiment_series, as_of_date)
    
    # Should return UNAVAILABLE
    assert regime == SentimentRegime.UNAVAILABLE
    assert confidence == 0.0


def test_trend_classification():
    """Test trend classification (improving, deteriorating, stable)."""
    classifier = SentimentRegimeClassifier()
    
    # Create series where 7-day EMA is clearly above 30-day EMA (improving)
    dates = pd.date_range('2024-01-01', '2024-06-14', freq='D')
    scores = np.linspace(-1.0, 1.0, len(dates))  # Steadily improving
    sentiment_series = pd.Series(scores, index=dates)
    
    as_of_date = datetime(2024, 6, 15)
    trend = classifier.classify_trend(sentiment_series, as_of_date)
    
    # Should classify as IMPROVING
    assert trend == SentimentTrend.IMPROVING


def test_trend_deteriorating():
    """Test deteriorating trend classification."""
    classifier = SentimentRegimeClassifier()
    
    # Create series where 7-day EMA is clearly below 30-day EMA (deteriorating)
    dates = pd.date_range('2024-01-01', '2024-06-14', freq='D')
    scores = np.linspace(1.0, -1.0, len(dates))  # Steadily deteriorating
    sentiment_series = pd.Series(scores, index=dates)
    
    as_of_date = datetime(2024, 6, 15)
    trend = classifier.classify_trend(sentiment_series, as_of_date)
    
    # Should classify as DETERIORATING
    assert trend == SentimentTrend.DETERIORATING


def test_trend_stable():
    """Test stable trend classification."""
    classifier = SentimentRegimeClassifier()
    
    # Create series with stable sentiment
    dates = pd.date_range('2024-01-01', '2024-06-14', freq='D')
    scores = np.ones(len(dates)) * 0.5  # Constant positive sentiment
    sentiment_series = pd.Series(scores, index=dates)
    
    as_of_date = datetime(2024, 6, 15)
    trend = classifier.classify_trend(sentiment_series, as_of_date)
    
    # Should classify as STABLE
    assert trend == SentimentTrend.STABLE


def test_get_regime_history():
    """Test historical regime classification."""
    classifier = SentimentRegimeClassifier()
    
    # Create series with enough history
    dates = pd.date_range('2024-01-01', '2024-06-14', freq='D')
    scores = np.random.randn(len(dates)) * 0.5
    sentiment_series = pd.Series(scores, index=dates)
    
    # Get regime history for a subset
    start_date = datetime(2024, 5, 1)
    end_date = datetime(2024, 6, 14)
    
    history_df = classifier.get_regime_history(sentiment_series, start_date, end_date)
    
    # Should return DataFrame with expected columns
    assert not history_df.empty
    assert 'regime' in history_df.columns
    assert 'confidence' in history_df.columns
    assert 'zscore' in history_df.columns
    assert 'smoothed_score' in history_df.columns
    
    # Should have entries for the date range
    assert len(history_df) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
