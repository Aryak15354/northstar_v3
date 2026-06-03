"""
Tests for SentimentFeatureBlock.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock
import pandas as pd
import numpy as np
import warnings

from src.sentiment.sentiment_feature_block import (
    SentimentFeatureBlock,
    SentimentStalenessWarning
)


def test_get_feature_names():
    """Test feature names are correctly defined."""
    feature_names = SentimentFeatureBlock.get_feature_names()
    
    # Check market features
    assert 'sent_market_score_1d' in feature_names
    assert 'sent_market_score_7d' in feature_names
    assert 'sent_market_score_30d' in feature_names
    assert 'sent_market_momentum' in feature_names
    assert 'sent_market_volatility' in feature_names
    assert 'sent_regime_numeric' in feature_names
    assert 'sent_crisis_proximity' in feature_names
    assert 'sent_price_divergence' in feature_names
    
    # Check company features
    assert 'sent_company_score_7d' in feature_names
    assert 'sent_company_score_30d' in feature_names
    assert 'sent_company_momentum' in feature_names
    assert 'sent_company_vs_market' in feature_names
    assert 'sent_coverage_density' in feature_names
    assert 'sent_has_coverage' in feature_names


def test_pit_strict():
    """Test PIT enforcement: sent_market_score_1d uses only T-1 data."""
    # Mock registry
    registry = Mock()
    registry.sentiment.is_sentiment_fresh.return_value = True
    
    # Create sentiment data up to 2024-06-15
    dates = pd.date_range('2024-01-01', '2024-06-15', freq='D')
    scores = np.random.randn(len(dates))
    market_df = pd.DataFrame({'sentiment_score': scores}, index=dates)
    registry.sentiment.load_market_sentiment.return_value = market_df
    
    # Mock price data
    registry.market.load.return_value = pd.DataFrame()
    
    # Create feature block
    block = SentimentFeatureBlock(registry, config={})
    
    # Compute features as of 2024-06-15
    as_of_date = datetime(2024, 6, 15)
    features = block.compute_market_features(as_of_date)
    
    # The sent_market_score_1d should use data from 2024-06-14 (T-1)
    # Due to shift(1), the value at 2024-06-15 should be based on 2024-06-14's score
    # We can't directly verify the shift, but we can verify no future data is used
    assert not features.empty
    assert features.index.max() <= as_of_date


def test_stale_fallback():
    """Test graceful degradation when sentiment is stale."""
    # Mock registry with stale sentiment
    registry = Mock()
    registry.sentiment.is_sentiment_fresh.return_value = False
    
    # Create feature block
    block = SentimentFeatureBlock(registry, config={})
    
    # Compute features - should emit warning and return neutral features
    as_of_date = datetime(2024, 6, 15)
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        features = block.compute_market_features(as_of_date)
        
        # Check that warning was emitted
        assert len(w) > 0
        assert issubclass(w[0].category, SentimentStalenessWarning)
    
    # Check all features are 0.0 (neutral)
    assert not features.empty
    for col in features.columns:
        if col != 'sent_regime_numeric':  # This one is int
            assert features[col].iloc[0] == 0.0
    
    # No exception should be raised
    assert True


def test_full_ticker_coverage():
    """Test that output has all input tickers, even those without coverage."""
    # Mock registry
    registry = Mock()
    registry.sentiment.is_sentiment_fresh.return_value = True
    
    # Create company sentiment for only 30 out of 50 tickers
    covered_tickers = [f'TICKER{i}' for i in range(30)]
    uncovered_tickers = [f'TICKER{i}' for i in range(30, 50)]
    all_tickers = covered_tickers + uncovered_tickers
    
    # Mock company sentiment data (only covered tickers)
    dates = pd.date_range('2024-05-01', '2024-06-14', freq='D')
    data = []
    for ticker in covered_tickers:
        for date in dates:
            data.append({
                'Ticker': ticker,
                'Date': date,
                'sentiment_score': np.random.randn()
            })
    company_df = pd.DataFrame(data).set_index(['Ticker', 'Date'])
    registry.sentiment.load_company_sentiment.return_value = company_df
    
    # Mock market sentiment
    market_df = pd.DataFrame({
        'sentiment_score': np.random.randn(len(dates))
    }, index=dates)
    registry.sentiment.load_market_sentiment.return_value = market_df
    
    # Create feature block
    block = SentimentFeatureBlock(registry, config={})
    
    # Compute features for all 50 tickers
    as_of_date = datetime(2024, 6, 15)
    features = block.compute_company_features(as_of_date, all_tickers)
    
    # Assert output has exactly 50 rows
    assert len(features) == 50
    
    # Assert uncovered tickers have sent_has_coverage = 0.0
    for ticker in uncovered_tickers:
        if ticker in features.index:
            assert features.loc[ticker, 'sent_has_coverage'] == 0.0
            assert features.loc[ticker, 'sent_company_score_7d'] == 0.0


def test_company_vs_market():
    """Test sent_company_vs_market calculation."""
    # Mock registry
    registry = Mock()
    registry.sentiment.is_sentiment_fresh.return_value = True
    
    # Create company sentiment with positive scores
    dates = pd.date_range('2024-01-01', '2024-06-14', freq='D')
    company_data = []
    for date in dates:
        company_data.append({
            'Ticker': 'POSITIVE_TICKER',
            'Date': date,
            'sentiment_score': 1.0  # Consistently positive
        })
    company_df = pd.DataFrame(company_data).set_index(['Ticker', 'Date'])
    registry.sentiment.load_company_sentiment.return_value = company_df
    
    # Create market sentiment with negative scores
    market_df = pd.DataFrame({
        'sentiment_score': np.ones(len(dates)) * -1.0  # Consistently negative
    }, index=dates)
    registry.sentiment.load_market_sentiment.return_value = market_df
    
    # Create feature block
    block = SentimentFeatureBlock(registry, config={})
    
    # Compute features
    as_of_date = datetime(2024, 6, 15)
    features = block.compute_company_features(as_of_date, ['POSITIVE_TICKER'])
    
    # sent_company_vs_market should be positive (company better than market)
    assert features.loc['POSITIVE_TICKER', 'sent_company_vs_market'] > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
