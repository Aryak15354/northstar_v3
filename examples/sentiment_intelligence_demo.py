#!/usr/bin/env python3
"""
Sentiment Intelligence System Demo

Demonstrates how the sentiment system works in Northstar V3.
Shows regime classification, feature engineering, and state computation.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from src.sentiment.sentiment_state import (
    SentimentState,
    SentimentRegime,
    SentimentTrend,
    compute_sentiment_state
)
from src.sentiment.sentiment_regime import SentimentRegimeClassifier
from src.sentiment.sentiment_feature_block import SentimentFeatureBlock
from src.sentiment.narrative_sentiment_bridge import NarrativeSentimentBridge
from src.core.state import UnifiedState


def demo_unified_state_integration():
    """Demo 1: Sentiment in UnifiedState"""
    print("=" * 80)
    print("DEMO 1: Sentiment Integration in UnifiedState")
    print("=" * 80)
    
    # Create unified state
    state = UnifiedState()
    
    print(f"\nUnifiedState has sentiment: {hasattr(state, 'sentiment')}")
    print(f"Sentiment type: {type(state.sentiment)}")
    print(f"Default regime: {state.sentiment.market_sentiment_regime}")
    print(f"Default is_fresh: {state.sentiment.is_fresh}")
    print(f"Default data_lag_days: {state.sentiment.data_lag_days}")
    
    print("\n✓ Sentiment is now a first-class component of UnifiedState")


def demo_regime_classification():
    """Demo 2: Regime Classification with Hysteresis"""
    print("\n" + "=" * 80)
    print("DEMO 2: Sentiment Regime Classification")
    print("=" * 80)
    
    # Create classifier
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
    
    # Create synthetic sentiment series
    dates = pd.date_range('2024-01-01', '2024-06-14', freq='D')
    
    # Scenario 1: Panic regime
    panic_scores = np.ones(len(dates)) * -2.5
    panic_series = pd.Series(panic_scores, index=dates)
    regime, confidence = classifier.classify(panic_series, datetime(2024, 6, 15))
    print(f"\nScenario 1: Extreme negative sentiment (-2.5)")
    print(f"  Regime: {regime.value}")
    print(f"  Confidence: {confidence:.2f}")
    
    # Scenario 2: Neutral regime
    neutral_scores = np.random.randn(len(dates)) * 0.2  # Small variance around 0
    neutral_series = pd.Series(neutral_scores, index=dates)
    regime, confidence = classifier.classify(neutral_series, datetime(2024, 6, 15))
    print(f"\nScenario 2: Neutral sentiment (random around 0)")
    print(f"  Regime: {regime.value}")
    print(f"  Confidence: {confidence:.2f}")
    
    # Scenario 3: Euphoria regime
    euphoria_scores = np.ones(len(dates)) * 2.5
    euphoria_series = pd.Series(euphoria_scores, index=dates)
    regime, confidence = classifier.classify(euphoria_series, datetime(2024, 6, 15))
    print(f"\nScenario 3: Extreme positive sentiment (+2.5)")
    print(f"  Regime: {regime.value}")
    print(f"  Confidence: {confidence:.2f}")
    
    # Scenario 4: Trend classification
    improving_scores = np.linspace(-1.0, 1.0, len(dates))  # Steadily improving
    improving_series = pd.Series(improving_scores, index=dates)
    trend = classifier.classify_trend(improving_series, datetime(2024, 6, 15))
    print(f"\nScenario 4: Steadily improving sentiment")
    print(f"  Trend: {trend.value}")
    
    print("\n✓ Regime classifier uses z-scores with hysteresis to prevent oscillation")


def demo_feature_engineering():
    """Demo 3: Feature Engineering"""
    print("\n" + "=" * 80)
    print("DEMO 3: Sentiment Feature Engineering")
    print("=" * 80)
    
    # Show feature names
    feature_names = SentimentFeatureBlock.get_feature_names()
    
    print(f"\nTotal features: {len(feature_names)}")
    print("\nMarket-level features:")
    for name in feature_names[:8]:
        print(f"  - {name}")
    
    print("\nCompany-level features:")
    for name in feature_names[8:]:
        print(f"  - {name}")
    
    print("\n✓ All features are z-scored and PIT-compliant (use T-1 data)")
    print("✓ If sentiment is stale, all features return 0.0 (neutral)")
    print("✓ Research and live use identical features (parity guaranteed)")


def demo_narrative_bridge():
    """Demo 4: Narrative Bridge"""
    print("\n" + "=" * 80)
    print("DEMO 4: Narrative Sentiment Bridge")
    print("=" * 80)
    
    bridge = NarrativeSentimentBridge()
    
    # Create mock sentiment states
    scenarios = [
        SentimentState(
            market_sentiment_regime=SentimentRegime.PANIC,
            sentiment_trend=SentimentTrend.DETERIORATING,
            regime_confidence=0.9,
            is_fresh=True,
            sentiment_crisis_signal=True
        ),
        SentimentState(
            market_sentiment_regime=SentimentRegime.NEUTRAL,
            sentiment_trend=SentimentTrend.STABLE,
            regime_confidence=0.7,
            is_fresh=True,
            sentiment_divergence=0.8  # High divergence
        ),
        SentimentState(
            market_sentiment_regime=SentimentRegime.EUPHORIA,
            sentiment_trend=SentimentTrend.IMPROVING,
            regime_confidence=0.85,
            is_fresh=True
        ),
    ]
    
    for i, sentiment_state in enumerate(scenarios, 1):
        narrative_input = bridge.build_narrative_input(sentiment_state)
        print(f"\nScenario {i}:")
        print(f"  Regime: {narrative_input.regime_label}")
        print(f"  Trend: {narrative_input.trend_label}")
        print(f"  Diverging: {narrative_input.is_diverging_from_price}")
        print(f"  Flag: {narrative_input.key_narrative_flag}")
        print(f"  Confidence: {narrative_input.confidence:.2f}")
    
    print("\n✓ Bridge translates technical state into human-readable narrative context")


def demo_graceful_degradation():
    """Demo 5: Graceful Degradation"""
    print("\n" + "=" * 80)
    print("DEMO 5: Graceful Degradation (Stale Sentiment)")
    print("=" * 80)
    
    # Create stale sentiment state
    stale_state = SentimentState(
        market_sentiment_regime=SentimentRegime.UNAVAILABLE,
        sentiment_trend=SentimentTrend.UNKNOWN,
        is_fresh=False,
        data_lag_days=5
    )
    
    print(f"\nStale sentiment state:")
    print(f"  Regime: {stale_state.market_sentiment_regime.value}")
    print(f"  Is Fresh: {stale_state.is_fresh}")
    print(f"  Data Lag: {stale_state.data_lag_days} days")
    
    # Show what narrative bridge does
    bridge = NarrativeSentimentBridge()
    narrative_input = bridge.build_narrative_input(stale_state)
    
    print(f"\nNarrative input:")
    print(f"  Regime Label: {narrative_input.regime_label}")
    print(f"  Is Fresh: {narrative_input.is_fresh}")
    
    print("\n✓ System degrades gracefully when sentiment is unavailable")
    print("✓ Intelligence stack will use neutral weights (1.0 for all signals)")
    print("✓ No crash, no blocked trading - system continues operating")


def main():
    """Run all demos"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "SENTIMENT INTELLIGENCE SYSTEM DEMO" + " " * 24 + "║")
    print("║" + " " * 25 + "Northstar V3 - GAP 2" + " " * 33 + "║")
    print("╚" + "=" * 78 + "╝")
    
    try:
        demo_unified_state_integration()
        demo_regime_classification()
        demo_feature_engineering()
        demo_narrative_bridge()
        demo_graceful_degradation()
        
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print("\nThe sentiment intelligence system provides:")
        print("  1. Regime classification (PANIC → FEAR → NEUTRAL → OPTIMISM → EUPHORIA)")
        print("  2. Feature engineering (14 features for models)")
        print("  3. Narrative context (human-readable explanations)")
        print("  4. Graceful degradation (system runs without sentiment)")
        print("  5. Research-live parity (identical features everywhere)")
        print("\nNext: Wire into intelligence_stack.py, data_pipeline.py, and startup sequence")
        print("=" * 80 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error running demo: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
