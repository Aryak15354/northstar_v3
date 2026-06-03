"""
Sentiment Integration for Intelligence Stack

This module provides sentiment integration points for the intelligence stack,
allowing sentiment features and regime information to be consumed by the
intelligence system.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
import pandas as pd

from src.sentiment.sentiment_state import SentimentState, SentimentRegime
from src.sentiment.sentiment_feature_block import SentimentFeatureBlock
from src.sentiment.narrative_sentiment_bridge import NarrativeSentimentBridge, SentimentNarrativeInput

logger = logging.getLogger(__name__)


# Sentiment regime signal weight modifiers
SENTIMENT_SIGNAL_WEIGHTS = {
    SentimentRegime.PANIC: {
        'momentum': 0.3,
        'mean_reversion': 1.5,
        'value': 1.2,
        'quality': 1.3
    },
    SentimentRegime.FEAR: {
        'momentum': 0.7,
        'mean_reversion': 1.2,
        'value': 1.1,
        'quality': 1.1
    },
    SentimentRegime.NEUTRAL: {
        'momentum': 1.0,
        'mean_reversion': 1.0,
        'value': 1.0,
        'quality': 1.0
    },
    SentimentRegime.OPTIMISM: {
        'momentum': 1.2,
        'mean_reversion': 0.9,
        'value': 0.9,
        'quality': 1.0
    },
    SentimentRegime.EUPHORIA: {
        'momentum': 1.3,
        'mean_reversion': 0.7,
        'value': 0.6,
        'quality': 1.1
    },
    SentimentRegime.UNAVAILABLE: {
        'momentum': 1.0,
        'mean_reversion': 1.0,
        'value': 1.0,
        'quality': 1.0
    }
}


def get_sentiment_signal_weights(sentiment_state: SentimentState, config: Optional[Dict] = None) -> Dict[str, float]:
    """
    Get signal weight modifiers based on sentiment regime.
    
    In PANIC or FEAR regime, reduce momentum signals and increase mean-reversion.
    In EUPHORIA, reduce value signals.
    
    Args:
        sentiment_state: Current sentiment state
        config: Optional config to override default weights
        
    Returns:
        Dict of signal type to weight multiplier
    """
    if config and 'sentiment_signal_weights' in config:
        weights_config = config['sentiment_signal_weights']
        regime_key = sentiment_state.market_sentiment_regime.value
        if regime_key in weights_config:
            return weights_config[regime_key]
    
    return SENTIMENT_SIGNAL_WEIGHTS[sentiment_state.market_sentiment_regime]


def compute_sentiment_confidence(sentiment_state: SentimentState) -> float:
    """
    Compute confidence modifier based on sentiment clarity.
    
    High confidence when: sentiment regime is clear (not at a boundary),
    sentiment is fresh, and sentiment aligns with price action.
    
    Low confidence when: sentiment is stale, or sentiment strongly
    contradicts what price action is saying (divergence).
    
    Args:
        sentiment_state: Current sentiment state
        
    Returns:
        Confidence score between 0.1 and 1.0
    """
    if not sentiment_state.is_fresh:
        return 0.5  # Neutral — don't penalize, don't boost
    
    # Base: regime clarity
    base = sentiment_state.regime_confidence
    
    # Penalize if sentiment is diverging from price action
    divergence_penalty = sentiment_state.sentiment_divergence * 0.3
    
    return max(0.1, min(1.0, base - divergence_penalty))


def get_sentiment_narrative_input(sentiment_state: SentimentState, market_state: Any) -> Optional[SentimentNarrativeInput]:
    """
    Build narrative input from sentiment state.
    
    Args:
        sentiment_state: Current sentiment state
        market_state: Current market state
        
    Returns:
        SentimentNarrativeInput or None if sentiment unavailable
    """
    try:
        bridge = NarrativeSentimentBridge()
        return bridge.build_narrative_input(sentiment_state, market_state)
    except Exception as e:
        logger.error(f"Error building sentiment narrative input: {e}")
        return None


def load_sentiment_features(registry, as_of_date: datetime, tickers: list, config: Dict) -> pd.DataFrame:
    """
    Load sentiment features for the intelligence stack.
    
    This is the integration point for feature engineering.
    
    Args:
        registry: IngestionRegistry instance
        as_of_date: Point-in-time date
        tickers: List of tickers to get features for
        config: System configuration
        
    Returns:
        DataFrame with sentiment features (Ticker as index)
    """
    try:
        sentiment_block = SentimentFeatureBlock(registry=registry, config=config)
        
        # Compute company-level features
        company_features = sentiment_block.compute_company_features(
            as_of_date=as_of_date,
            tickers=tickers
        )
        
        return company_features
        
    except Exception as e:
        logger.error(f"Error loading sentiment features: {e}", exc_info=True)
        
        # Return neutral features (all zeros) on error
        neutral_features = pd.DataFrame(index=tickers)
        neutral_features['sent_company_score_7d'] = 0.0
        neutral_features['sent_company_score_30d'] = 0.0
        neutral_features['sent_company_momentum'] = 0.0
        neutral_features['sent_company_vs_market'] = 0.0
        neutral_features['sent_coverage_density'] = 0.0
        neutral_features['sent_has_coverage'] = 0.0
        
        return neutral_features


def apply_sentiment_to_beliefs(beliefs: Dict, sentiment_state: SentimentState) -> Dict:
    """
    Apply sentiment information to intelligence beliefs.
    
    Args:
        beliefs: Current beliefs dict
        sentiment_state: Current sentiment state
        
    Returns:
        Updated beliefs dict with sentiment information
    """
    if not sentiment_state.is_fresh:
        return beliefs
    
    # Add sentiment dimension to beliefs
    beliefs['sentiment'] = {
        'regime': sentiment_state.market_sentiment_regime.value,
        'trend': sentiment_state.sentiment_trend.value,
        'zscore': sentiment_state.market_sentiment_zscore,
        'confidence': sentiment_state.regime_confidence,
        'crisis_signal': sentiment_state.sentiment_crisis_signal
    }
    
    # Adjust overall conviction based on sentiment
    if 'conviction_levels' in beliefs:
        sentiment_conviction = sentiment_state.regime_confidence
        
        # Blend sentiment conviction with existing convictions
        existing_overall = beliefs['conviction_levels'].get('overall', 0.5)
        beliefs['conviction_levels']['sentiment'] = sentiment_conviction
        
        # Recompute overall (simple average for now)
        all_convictions = [v for k, v in beliefs['conviction_levels'].items() if k != 'overall']
        beliefs['conviction_levels']['overall'] = sum(all_convictions) / len(all_convictions) if all_convictions else 0.5
    
    return beliefs
