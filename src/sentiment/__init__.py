"""
Sentiment & News Intelligence System for Northstar V3

This module provides sentiment analysis integration for the Intelligence Stack,
converting raw news sentiment scores into actionable regime classifications,
features, and confidence signals.

Key components:
- SentimentState: Formal state representation in UnifiedState
- SentimentRegimeClassifier: Converts scores to regime labels (PANIC, FEAR, etc.)
- SentimentFeatureBlock: Feature engineering for models
- SentimentPipelineRunner: Daily pipeline orchestration
- NarrativeSentimentBridge: Integration with narrative engine
"""

from .sentiment_state import (
    SentimentState,
    SentimentRegime,
    SentimentTrend,
    compute_sentiment_state
)

__all__ = [
    'SentimentState',
    'SentimentRegime',
    'SentimentTrend',
    'compute_sentiment_state',
]
