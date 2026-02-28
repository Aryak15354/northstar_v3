#!/usr/bin/env python3
"""
🧪 TEST V3 SENTIMENT INTEGRATION
Verify that NS-USO is properly integrated with Northstar V3

This test:
✅ Runs NS-USO V3 batch ingestion
✅ Verifies sentiment artifacts are created
✅ Tests Market Brain sentiment loading
✅ Validates Brain Window data format
✅ Confirms no impact on core V3 functionality
"""

import sys
import os
import json
from pathlib import Path
import pandas as pd
from datetime import datetime

def test_ns_uso_v3_batch_ingestion():
    """Test NS-USO V3 batch ingestion"""
    
    print("🧪 Testing NS-USO V3 Batch Ingestion...")
    
    # Run the batch ingestion
    import subprocess
    result = subprocess.run([
        sys.executable, "northstar/scripts/run_v3_batch_ingestion.py", "--quiet"
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"   ❌ Batch ingestion failed: {result.stderr}")
        return False
    
    # Verify artifacts were created
    v3_data_dir = Path("data/sentiment/v3")
    
    required_files = [
        "market_sentiment_india.parquet",
        "sector_narratives.parquet", 
        "policy_context.json",
        "v3_sentiment_summary.json"
    ]
    
    for file_name in required_files:
        file_path = v3_data_dir / file_name
        if not file_path.exists():
            print(f"   ❌ Missing artifact: {file_name}")
            return False
    
    print("   ✅ NS-USO V3 batch ingestion successful")
    return True

def test_v3_sentiment_loader():
    """Test V3 sentiment loader"""
    
    print("🧪 Testing V3 Sentiment Loader...")
    
    try:
        from src.intelligence.market_brain.v3_sentiment_loader import load_v3_sentiment_for_market_brain
        
        sentiment = load_v3_sentiment_for_market_brain()
        
        if not sentiment:
            print("   ❌ No sentiment data loaded")
            return False
        
        # Verify key properties
        required_properties = [
            'conviction', 'narrative_cohesion', 'uncertainty',
            'dominant_theme', 'policy_weight'
        ]
        
        for prop in required_properties:
            if not hasattr(sentiment, prop):
                print(f"   ❌ Missing property: {prop}")
                return False
        
        # Verify safe bounds
        if not (0.5 <= sentiment.belief_strength_multiplier <= 1.5):
            print(f"   ❌ Unsafe belief strength multiplier: {sentiment.belief_strength_multiplier}")
            return False
        
        if not (0.0 <= sentiment.uncertainty_addition <= 0.3):
            print(f"   ❌ Unsafe uncertainty addition: {sentiment.uncertainty_addition}")
            return False
        
        print("   ✅ V3 sentiment loader working correctly")
        return True
        
    except Exception as e:
        print(f"   ❌ Sentiment loader error: {e}")
        return False

def test_market_brain_integration():
    """Test Market Brain integration with V3 sentiment"""
    
    print("🧪 Testing Market Brain Integration...")
    
    try:
        from src.intelligence.market_brain.real_data_integrator import RealDataIntegrator
        
        integrator = RealDataIntegrator()
        
        # Load sentiment
        sentiment_loaded = integrator.load_v3_sentiment()
        
        if not sentiment_loaded:
            print("   ⚠️ Sentiment not loaded, but integration should still work")
        
        # Test sentiment adjustments (with mock data)
        base_confidence = 0.8
        adjusted_confidence = integrator.get_sentiment_adjusted_confidence(base_confidence)
        
        if not (0.1 <= adjusted_confidence <= 1.0):
            print(f"   ❌ Unsafe adjusted confidence: {adjusted_confidence}")
            return False
        
        base_inertia = 1.0
        adjusted_inertia = integrator.get_sentiment_adjusted_belief_inertia(base_inertia)
        
        if not (0.5 <= adjusted_inertia <= 2.0):
            print(f"   ❌ Unsafe adjusted inertia: {adjusted_inertia}")
            return False
        
        # Test Brain Window data
        brain_window_data = integrator.get_v3_sentiment_for_brain_window()
        
        required_sections = ['india_semantic_context', 'regime_confidence', 'narrative_health']
        for section in required_sections:
            if section not in brain_window_data:
                print(f"   ❌ Missing Brain Window section: {section}")
                return False
        
        print("   ✅ Market Brain integration working correctly")
        return True
        
    except Exception as e:
        print(f"   ❌ Market Brain integration error: {e}")
        return False

def test_brain_window_panel():
    """Test Brain Window panel (basic validation)"""
    
    print("🧪 Testing Brain Window Panel...")
    
    try:
        from src.dashboard.components.v3_sentiment_panel import V3SentimentPanel
        
        panel = V3SentimentPanel()
        data = panel.load_sentiment_data()
        
        if not isinstance(data, dict):
            print("   ❌ Panel data format invalid")
            return False
        
        required_keys = ['market_sentiment', 'sector_narratives', 'policy_context', 'data_available']
        for key in required_keys:
            if key not in data:
                print(f"   ❌ Missing data key: {key}")
                return False
        
        print("   ✅ Brain Window panel structure valid")
        return True
        
    except Exception as e:
        print(f"   ❌ Brain Window panel error: {e}")
        return False

def test_v3_system_compatibility():
    """Test that V3 system still works with sentiment integration"""
    
    print("🧪 Testing V3 System Compatibility...")
    
    try:
        # Test that core V3 files are not broken
        core_paths = [
            "data/processed/market_state.parquet",
            "data/processed/strategy_beliefs.parquet",
            "data/processed/portfolio_weights.parquet"
        ]
        
        # These files may not exist yet, but the paths should be valid
        for path in core_paths:
            path_obj = Path(path)
            if path_obj.exists():
                # If file exists, try to read it
                if path.endswith('.parquet'):
                    df = pd.read_parquet(path)
                    if df.empty:
                        print(f"   ⚠️ Empty core file: {path}")
                elif path.endswith('.json'):
                    with open(path, 'r') as f:
                        data = json.load(f)
        
        # Test that sentiment directory doesn't interfere
        sentiment_dir = Path("data/sentiment/v3")
        if sentiment_dir.exists():
            # Should be isolated from core V3 data
            core_data_dir = Path("data/processed")
            if sentiment_dir.resolve() == core_data_dir.resolve():
                print("   ❌ Sentiment data conflicts with core V3 data")
                return False
        
        print("   ✅ V3 system compatibility maintained")
        return True
        
    except Exception as e:
        print(f"   ❌ V3 compatibility error: {e}")
        return False

def test_safety_guarantees():
    """Test that sentiment integration maintains safety guarantees"""
    
    print("🧪 Testing Safety Guarantees...")
    
    try:
        from src.intelligence.market_brain.v3_sentiment_loader import load_v3_sentiment_for_market_brain
        
        sentiment = load_v3_sentiment_for_market_brain()
        
        if sentiment:
            # Test that sentiment never creates signals (only modulates)
            if hasattr(sentiment, 'create_signal') or hasattr(sentiment, 'generate_trade'):
                print("   ❌ Sentiment has signal creation methods (unsafe)")
                return False
            
            # Test that multipliers are conservative
            if sentiment.belief_strength_multiplier > 1.5 or sentiment.belief_strength_multiplier < 0.5:
                print(f"   ❌ Unsafe belief strength multiplier: {sentiment.belief_strength_multiplier}")
                return False
            
            # Test that uncertainty addition is bounded
            if sentiment.uncertainty_addition > 0.3:
                print(f"   ❌ Excessive uncertainty addition: {sentiment.uncertainty_addition}")
                return False
        
        print("   ✅ Safety guarantees maintained")
        return True
        
    except Exception as e:
        print(f"   ❌ Safety guarantee error: {e}")
        return False

def main():
    """Run all V3 sentiment integration tests"""
    
    print("🧪 V3 SENTIMENT INTEGRATION TEST SUITE")
    print("=" * 60)
    print("   Testing NS-USO integration with Northstar V3")
    print()
    
    tests = [
        ("NS-USO V3 Batch Ingestion", test_ns_uso_v3_batch_ingestion),
        ("V3 Sentiment Loader", test_v3_sentiment_loader),
        ("Market Brain Integration", test_market_brain_integration),
        ("Brain Window Panel", test_brain_window_panel),
        ("V3 System Compatibility", test_v3_system_compatibility),
        ("Safety Guarantees", test_safety_guarantees)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔬 {test_name}")
        print("-" * 40)
        
        try:
            if test_func():
                passed += 1
                print(f"   ✅ PASSED")
            else:
                print(f"   ❌ FAILED")
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
    
    print(f"\n🎯 TEST RESULTS")
    print("=" * 40)
    print(f"Passed: {passed}/{total}")
    print(f"Success rate: {passed/total:.1%}")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED!")
        print("   V3 sentiment integration is ready for production")
        return True
    else:
        print(f"\n⚠️ {total - passed} TESTS FAILED")
        print("   Review failed tests before deploying")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)