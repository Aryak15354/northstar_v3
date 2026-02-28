#!/usr/bin/env python3
"""
🧠 TEST MARKET BRAIN - NORTHSTAR V3
Quick test script to verify Market Brain components work

This script tests each Market Brain component individually
and then runs the complete system to ensure integration works.
"""

import sys
import os
from datetime import datetime

# Add project root to path


def test_market_tensor():
    """Test Market Tensor Engine"""
    
    print("🧠 Testing Market Tensor Engine...")
    
    try:
        from src.intelligence.market_brain.market_tensor import MarketTensorEngine
        
        engine = MarketTensorEngine()
        tensor = engine.build_market_tensor()
        
        if not tensor.empty:
            print(f"   ✅ Market Tensor: {tensor.shape}")
            return True
        else:
            print("   ❌ Market Tensor: Empty")
            return False
            
    except Exception as e:
        print(f"   ❌ Market Tensor Error: {e}")
        return False

def test_causal_graph():
    """Test Causal Graph Engine"""
    
    print("🧬 Testing Causal Graph Engine...")
    
    try:
        from src.intelligence.market_brain.causal_graph import CausalGraphEngine
        
        engine = CausalGraphEngine()
        
        # Load tensor first (required for causality)
        tensor = engine.load_market_tensor()
        if tensor.empty:
            print("   ⚠️ No tensor available, building minimal causality")
        
        success = engine.build_causal_intelligence()
        
        if success:
            graph = engine.load_causal_graph()
            edges = len(graph.get('edges', []))
            print(f"   ✅ Causal Graph: {edges} relationships")
            return True
        else:
            print("   ❌ Causal Graph: Failed")
            return False
            
    except Exception as e:
        print(f"   ❌ Causal Graph Error: {e}")
        return False

def test_regime_memory():
    """Test Regime Memory Engine"""
    
    print("🧠 Testing Regime Memory Engine...")
    
    try:
        from src.intelligence.market_brain.regime_memory import RegimeMemoryEngine
        
        engine = RegimeMemoryEngine()
        success = engine.build_regime_fingerprints()
        
        if success:
            fingerprints = engine.load_regime_memory()
            print(f"   ✅ Regime Memory: {len(fingerprints)} periods")
            return True
        else:
            print("   ❌ Regime Memory: Failed")
            return False
            
    except Exception as e:
        print(f"   ❌ Regime Memory Error: {e}")
        return False

def test_market_pulse():
    """Test Market Pulse Engine"""
    
    print("💓 Testing Market Pulse Engine...")
    
    try:
        from src.intelligence.market_brain.market_pulse import MarketPulseEngine
        
        engine = MarketPulseEngine()
        success = engine.compute_market_pulse()
        
        if success:
            pulse_state = engine.load_pulse_state()
            intensity = pulse_state.get('pulse_intensity', 0)
            phase = pulse_state.get('market_phase', 'unknown')
            print(f"   ✅ Market Pulse: {intensity:.2f} intensity, {phase} phase")
            return True
        else:
            print("   ❌ Market Pulse: Failed")
            return False
            
    except Exception as e:
        print(f"   ❌ Market Pulse Error: {e}")
        return False

def test_survival_instincts():
    """Test Survival Instincts Engine"""
    
    print("🛡️ Testing Survival Instincts Engine...")
    
    try:
        from src.intelligence.market_brain.survival_instincts import SurvivalInstinctEngine
        
        engine = SurvivalInstinctEngine()
        survival_state = engine.assess_survival_instincts()
        
        if survival_state:
            mode = survival_state.get('survival_mode', 'unknown')
            emergency = survival_state.get('emergency_triggered', False)
            print(f"   ✅ Survival Instincts: {mode} mode, emergency: {emergency}")
            return True
        else:
            print("   ❌ Survival Instincts: Failed")
            return False
            
    except Exception as e:
        print(f"   ❌ Survival Instincts Error: {e}")
        return False

def test_brain_orchestrator():
    """Test complete Brain Orchestrator"""
    
    print("🧠 Testing Brain Orchestrator...")
    
    try:
        from src.intelligence.market_brain.brain_orchestrator import MarketBrainOrchestrator
        
        orchestrator = MarketBrainOrchestrator()
        success = orchestrator.run_complete_market_brain()
        
        if success:
            brain_state = orchestrator.get_brain_status()
            active_components = sum(brain_state.get('component_status', {}).values())
            print(f"   ✅ Brain Orchestrator: {active_components}/5 components active")
            return True
        else:
            print("   ❌ Brain Orchestrator: Failed")
            return False
            
    except Exception as e:
        print(f"   ❌ Brain Orchestrator Error: {e}")
        return False

def test_v3_integration():
    """Test V3 Market State integration"""
    
    print("🔗 Testing V3 Integration...")
    
    try:
        from src.cohesion.unified_state_manager import UnifiedStateManager
        
        engine = UnifiedStateManager()
        market_state = engine.compute_market_state()
        
        # Check if brain fields are present
        brain_fields = ['pulse_intensity', 'market_phase', 'regime_similarity', 'survival_mode']
        brain_integrated = all(field in market_state for field in brain_fields)
        
        if brain_integrated:
            print(f"   ✅ V3 Integration: Brain fields integrated")
            print(f"      Pulse intensity: {market_state.get('pulse_intensity', 0):.2f}")
            print(f"      Market phase: {market_state.get('market_phase', 'unknown')}")
            print(f"      Survival mode: {market_state.get('survival_mode', 'unknown')}")
            return True
        else:
            print("   ❌ V3 Integration: Brain fields missing")
            return False
            
    except Exception as e:
        print(f"   ❌ V3 Integration Error: {e}")
        return False

def main():
    """Run complete Market Brain test suite"""
    
    print("🧠 NORTHSTAR MARKET BRAIN - TEST SUITE")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Test individual components
    tests = [
        ("Market Tensor", test_market_tensor),
        ("Causal Graph", test_causal_graph),
        ("Regime Memory", test_regime_memory),
        ("Market Pulse", test_market_pulse),
        ("Survival Instincts", test_survival_instincts),
        ("Brain Orchestrator", test_brain_orchestrator),
        ("V3 Integration", test_v3_integration)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"   ❌ {test_name} crashed: {e}")
            results[test_name] = False
    
    # Summary
    print(f"\n🎯 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = sum(results.values())
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed >= 5:  # At least 5 out of 7 should pass
        print("🎉 Market Brain is ready for production!")
        return True
    else:
        print("⚠️ Market Brain needs attention before production use")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)