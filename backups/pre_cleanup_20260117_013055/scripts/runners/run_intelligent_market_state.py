#!/usr/bin/env python3
"""
🧠 Intelligent Market State Runner
Wrapper script for running the intelligent market state computation
"""

import sys
import os

def main():
    """Run intelligent market state computation"""
    
    try:
        from src.cohesion.unified_state_manager import UnifiedStateManager
        
        print("🧠 Computing intelligent market state...")
        engine = UnifiedStateManager()
        market_state = engine.run()
        
        print("✅ Intelligent market state computed successfully")
        print(f"   Regime: {market_state['macro_regime']}")
        print(f"   Risk-On Probability: {market_state['risk_on_probability']:.1%}")
        print(f"   Allowed Exposure: {market_state['allowed_exposure']:.1f}%")
        
        return True
        
    except Exception as e:
        print(f"❌ Intelligent market state failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)