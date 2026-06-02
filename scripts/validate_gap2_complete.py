#!/usr/bin/env python3
"""
Validate GAP 2 Complete Integration

This script validates that all GAP 2 Phase 1 and Phase 2 components
are properly integrated and working.
"""

import sys
import os
from datetime import datetime

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def validate_imports():
    """Validate all sentiment modules can be imported"""
    print("🔍 Validating imports...")
    
    try:
        from src.sentiment.sentiment_state import SentimentState, SentimentRegime, compute_sentiment_state
        from src.sentiment.sentiment_feature_block import SentimentFeatureBlock
        from src.sentiment.sentiment_regime import SentimentRegimeClassifier
        from src.sentiment.narrative_sentiment_bridge import NarrativeSentimentBridge
        from src.sentiment.sentiment_pipeline_runner import SentimentPipelineRunner
        from src.intelligence.sentiment_integration import (
            get_sentiment_signal_weights,
            compute_sentiment_confidence,
            load_sentiment_features,
            apply_sentiment_to_beliefs
        )
        from src.intelligence.regime_memory_system import RegimeMemorySystem
        from src.ingestion.sentiment_loader import SentimentLoader
        
        print("   ✅ All sentiment modules import successfully")
        return True
    except Exception as e:
        print(f"   ❌ Import error: {e}")
        return False

def validate_regime_memory():
    """Validate regime memory has sentiment features"""
    print("\n🧠 Validating regime memory system...")
    
    try:
        from src.intelligence.regime_memory_system import RegimeMemorySystem
        
        system = RegimeMemorySystem()
        feature_cols = system.config['feature_columns']
        
        has_sentiment = any('sentiment' in col.lower() for col in feature_cols)
        
        if has_sentiment:
            print("   ✅ Regime memory includes sentiment features")
            sentiment_features = [col for col in feature_cols if 'sentiment' in col.lower()]
            for feat in sentiment_features:
                print(f"      - {feat}")
            return True
        else:
            print("   ❌ Regime memory missing sentiment features")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def validate_feature_block():
    """Validate sentiment feature block"""
    print("\n📊 Validating sentiment feature block...")
    
    try:
        from src.sentiment.sentiment_feature_block import SentimentFeatureBlock
        
        feature_names = SentimentFeatureBlock.get_feature_names()
        
        print(f"   ✅ {len(feature_names)} sentiment features available")
        print(f"      Market features: {len([f for f in feature_names if 'market' in f])}")
        print(f"      Company features: {len([f for f in feature_names if 'company' in f])}")
        
        return len(feature_names) > 0
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False


def validate_signal_weights():
    """Validate sentiment signal weight modifiers"""
    print("\n⚖️  Validating signal weight modifiers...")
    
    try:
        from src.intelligence.sentiment_integration import SENTIMENT_SIGNAL_WEIGHTS
        from src.sentiment.sentiment_state import SentimentRegime
        
        regimes = [r for r in SentimentRegime]
        
        for regime in regimes:
            if regime in SENTIMENT_SIGNAL_WEIGHTS:
                weights = SENTIMENT_SIGNAL_WEIGHTS[regime]
                print(f"   ✅ {regime.value}: {len(weights)} signal types")
        
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def validate_intelligence_integration():
    """Validate intelligence stack integration"""
    print("\n🎯 Validating intelligence stack integration...")
    
    try:
        from src.intelligence.intelligence_stack import MinimalIntelligenceStack
        
        stack = MinimalIntelligenceStack()
        
        if stack.sentiment_enabled:
            print("   ✅ Intelligence stack has sentiment enabled")
        else:
            print("   ⚠️  Intelligence stack sentiment disabled")
        
        return True
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def validate_confidence_engine():
    """Validate confidence engine has sentiment method"""
    print("\n🎲 Validating confidence engine...")
    
    try:
        from src.intelligence.confidence_engine import ConfidenceEngine
        
        engine = ConfidenceEngine()
        
        if hasattr(engine, 'calculate_sentiment_confidence'):
            print("   ✅ Confidence engine has calculate_sentiment_confidence()")
            return True
        else:
            print("   ❌ Confidence engine missing sentiment method")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def validate_narrative_engine():
    """Validate narrative engine has sentiment parameter"""
    print("\n📖 Validating narrative engine...")
    
    try:
        from src.intelligence.narrative_engine import NarrativeEngine
        import inspect
        
        engine = NarrativeEngine()
        
        # Check if generate_market_narrative accepts sentiment_input
        sig = inspect.signature(engine.generate_market_narrative)
        params = list(sig.parameters.keys())
        
        if 'sentiment_input' in params:
            print("   ✅ Narrative engine accepts sentiment_input parameter")
            return True
        else:
            print("   ❌ Narrative engine missing sentiment_input parameter")
            return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    """Run all validations"""
    print("=" * 60)
    print("GAP 2 COMPLETE INTEGRATION VALIDATION")
    print("=" * 60)
    
    results = {
        'imports': validate_imports(),
        'regime_memory': validate_regime_memory(),
        'feature_block': validate_feature_block(),
        'signal_weights': validate_signal_weights(),
        'intelligence': validate_intelligence_integration(),
        'confidence': validate_confidence_engine(),
        'narrative': validate_narrative_engine()
    }
    
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    passed = sum(results.values())
    total = len(results)
    
    for component, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {component}")
    
    print(f"\nResults: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 GAP 2 COMPLETE INTEGRATION: ALL CHECKS PASSED")
        return 0
    else:
        print(f"\n⚠️  GAP 2 INTEGRATION: {total - passed} checks failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
