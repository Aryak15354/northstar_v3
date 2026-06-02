#!/usr/bin/env python3
"""Quick validation that sentiment is ready for startup integration."""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from src.ingestion import IngestionRegistry
from src.sentiment.sentiment_state import compute_sentiment_state
from src.sentiment.sentiment_regime import SentimentRegimeClassifier

def main():
    print("\n" + "="*60)
    print("SENTIMENT STARTUP VALIDATION")
    print("="*60)
    
    # Test 1: Registry has sentiment
    print("\n1. Testing IngestionRegistry...")
    try:
        registry = IngestionRegistry()
        assert hasattr(registry, 'sentiment'), "Registry missing sentiment loader"
        print("   ✅ Sentiment loader registered")
    except Exception as e:
        print(f"   ✗ FAIL: {e}")
        return 1
    
    # Test 2: Health check includes sentiment
    print("\n2. Testing health check...")
    try:
        health = registry.health_check(datetime.now())
        assert 'sentiment' in health, "Health check missing sentiment"
        status = health['sentiment']
        print(f"   ✅ Sentiment in health check: {status['status']}")
        if not status['is_fresh']:
            print(f"   ⚠️  Warning: {status.get('warning', 'Data not fresh')}")
    except Exception as e:
        print(f"   ✗ FAIL: {e}")
        return 1
    
    # Test 3: Can load sentiment data
    print("\n3. Testing sentiment data loading...")
    try:
        market_df = registry.sentiment.load_market_sentiment(datetime.now())
        if not market_df.empty:
            print(f"   ✅ Market sentiment loaded: {len(market_df)} rows")
            print(f"      Latest: {market_df.index.max()}")
        else:
            print("   ⚠️  Market sentiment is empty")
    except Exception as e:
        print(f"   ✗ FAIL: {e}")
        return 1
    
    # Test 4: Can compute sentiment state
    print("\n4. Testing sentiment state computation...")
    try:
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
        sentiment_state = compute_sentiment_state(registry, datetime.now(), classifier)
        
        print(f"   ✅ Sentiment state computed")
        print(f"      Regime: {sentiment_state.market_sentiment_regime.value}")
        print(f"      Fresh: {sentiment_state.is_fresh}")
        print(f"      Lag: {sentiment_state.data_lag_days} days")
    except Exception as e:
        print(f"   ✗ FAIL: {e}")
        return 1
    
    print("\n" + "="*60)
    print("✅ ALL VALIDATIONS PASSED")
    print("="*60)
    print("\nSentiment is ready for startup integration!")
    print("It will be loaded automatically when the live engine starts.")
    return 0

if __name__ == '__main__':
    sys.exit(main())
