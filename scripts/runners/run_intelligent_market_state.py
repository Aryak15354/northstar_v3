#!/usr/bin/env python3
"""
🧠 Intelligent Market State Runner
Wrapper script for running the intelligent market state computation
"""

import sys
import os
from pathlib import Path

# Ensure project root is on sys.path when running from scripts/runners
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def main():
    """Run intelligent market state computation"""
    
    try:
        from src.state.market_state import IntelligentMarketStateEngine

        print("🧠 Computing intelligent market state (real artifacts)...")
        engine = IntelligentMarketStateEngine()
        market_state = engine.compute_intelligent_market_state()

        # market_state is a dict; the engine also writes data/processed/intelligent_market_state.parquet
        print("✅ Intelligent market state computed successfully")
        if isinstance(market_state, dict):
            regime = market_state.get("macro_regime") or market_state.get("regime") or market_state.get("market_regime")
            risk_on = market_state.get("risk_on_probability") or market_state.get("risk_on")
            allowed = market_state.get("allowed_exposure")
            if regime is not None:
                print(f"   Regime: {regime}")
            if risk_on is not None:
                try:
                    print(f"   Risk-On Probability: {float(risk_on):.1%}")
                except Exception:
                    print(f"   Risk-On Probability: {risk_on}")
            if allowed is not None:
                try:
                    a = float(allowed)
                    # Some artifacts store percent. Normalize for display.
                    if a > 1.0:
                        a = a / 100.0
                    print(f"   Allowed Exposure: {a:.1%}")
                except Exception:
                    print(f"   Allowed Exposure: {allowed}")
        
        return True
        
    except Exception as e:
        print(f"❌ Intelligent market state failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
