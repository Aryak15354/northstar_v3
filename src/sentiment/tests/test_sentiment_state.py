"""
Tests for SentimentState and compute_sentiment_state function.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock
import pandas as pd
import numpy as np

from src.sentiment.sentiment_state import (
    SentimentState,
    SentimentRegime,
    SentimentTrend,
    compute_sentiment_state
)
from src.core.state import UnifiedState


def test_unified_state_has_sentiment():
    """Test that UnifiedState has sentiment_state attribute."""
    state = UnifiedState()
    
    # Assert sentiment_state exists
    assert hasattr(state, 'sentiment')
    
    # Assert it's of type SentimentState
    assert isinstance(state.sentiment, SentimentState)
    
    # Assert default regime is UNAVAILABLE (safe default before pipeline runs)
    assert state.sentiment.market_sentiment_regime == SentimentRegime.UNAVAILABLE


def test_sentiment_state_defaults():
    """Test SentimentState default values."""
    state = SentimentState()
    
    assert state.market_sentiment_regime == SentimentRegime.UNAVAILABLE
    assert state.sentiment_trend == SentimentTrend.UNKNOWN
    assert state.market_sentiment_zscore == 0.0
    assert state.is_fresh == False
    assert state.data_lag_days == 999
    assert state.company_sentiment_available == False


def test_compute_sentiment_state_stale_data():
    """Test compute_sentiment_state with stale data."""
    # Mock registry
    registry = Mock()
    registry.sentiment.is_sentiment_fresh.return_value = False
    
    # Mock classifier
    classifier = Mock()
    
    # Compute state
    as_of_date = datetime(2024, 6, 15)
    state = compute_sentiment_state(registry, as_of_date, classifier)
    
    # Assert returns UNAVAILABLE regime
    assert state.market_sentiment_regime == SentimentRegime.UNAVAILABLE
    assert state.is_fresh == False
    assert state.data_lag_days == 999


def test_compute_sentiment_state_fresh_data():
    """Test compute_sentiment_state with fresh data."""
    # Mock registry
    registry = Mock()
    registry.sentiment.is_sentiment_fresh.return_value = True
    
    # Mock market sentiment data
    dates = pd.date_range('2024-01-01', '2024-06-14', freq='D')
    sentiment_scores = np.random.randn(len(dates)) * 0.5  # Random sentiment around 0
    market_df = pd.DataFrame({
        'sentiment_score': sentiment_scores
    }, index=dates)
    registry.sentiment.load_market_sentiment.return_value = market_df
    
    # Mock company sentiment data
    company_df = pd.DataFrame({
        'Ticker': ['RELIANCE'] * 10,
        'Date': pd.date_range('2024-06-05', '2024-06-14', freq='D'),
        'sentiment_score': np.random.randn(10)
    }).set_index(['Ticker', 'Date'])
    registry.sentiment.load_company_sentiment.return_value = company_df
    
    # Mock classifier
    classifier = Mock()
    classifier.classify.return_value = (SentimentRegime.NEUTRAL, 0.7)
    classifier.classify_trend.return_value = SentimentTrend.STABLE
    
    # Compute state
    as_of_date = datetime(2024, 6, 15)
    state = compute_sentiment_state(registry, as_of_date, classifier)
    
    # Assert fresh state
    assert state.is_fresh == True
    assert state.market_sentiment_regime == SentimentRegime.NEUTRAL
    assert state.sentiment_trend == SentimentTrend.STABLE
    assert state.regime_confidence == 0.7
    assert state.company_sentiment_available == True
    assert state.companies_with_coverage == 1


def test_compute_sentiment_state_crisis_signal():
    """Test crisis signal detection."""
    # Mock registry
    registry = Mock()
    registry.sentiment.is_sentiment_fresh.return_value = True
    
    # Mock market sentiment data with panic-level scores
    dates = pd.date_range('2024-01-01', '2024-06-14', freq='D')
    sentiment_scores = np.ones(len(dates)) * -3.0  # Extreme negative sentiment
    market_df = pd.DataFrame({
        'sentiment_score': sentiment_scores
    }, index=dates)
    registry.sentiment.load_market_sentiment.return_value = market_df
    
    # Mock company sentiment
    registry.sentiment.load_company_sentiment.return_value = pd.DataFrame()
    
    # Mock classifier returning PANIC
    classifier = Mock()
    classifier.classify.return_value = (SentimentRegime.PANIC, 0.9)
    classifier.classify_trend.return_value = SentimentTrend.DETERIORATING
    
    # Compute state
    as_of_date = datetime(2024, 6, 15)
    state = compute_sentiment_state(registry, as_of_date, classifier)
    
    # Assert crisis signal is True
    assert state.sentiment_crisis_signal == True
    assert state.market_sentiment_regime == SentimentRegime.PANIC


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
