#!/usr/bin/env python3
"""
🧠 RUN MARKET BRAIN - NORTHSTAR V3 MARKET INTELLIGENCE
Complete Market Brain Execution for Northstar V3

This script runs the complete market brain system and integrates it
with the existing Northstar V3 intelligence stack.

The Market Brain adds:
- Market Tensor: Unified sensory system
- Causal Graph: What moves what relationships  
- Regime Memory: Historical pattern recognition
- Market Pulse: Real-time force detection
- Survival Instincts: System health monitoring

Usage:
    python run_market_brain.py                    # Full brain execution
    python run_market_brain.py --pulse-only       # Update pulse only
    python run_market_brain.py --survival-only    # Check survival only
    python run_market_brain.py --status           # Check brain status
"""

import sys
import os
import argparse
from datetime import datetime

def run_full_market_brain():
    """Run complete market brain system"""
    
    print("🧠 NORTHSTAR MARKET BRAIN - FULL EXECUTION")
    print("=" * 70)
    
    try:
        from src.intelligence.market_brain.brain_orchestrator import MarketBrainOrchestrator

        orchestrator = MarketBrainOrchestrator()
        success = orchestrator.run_complete_market_brain()

        if success:
            print("\n✅ Full market brain execution completed")
            try:
                status = orchestrator.get_brain_status()
                if isinstance(status, dict):
                    print(f"   Status: {status.get('status', 'unknown')}")
            except Exception:
                pass
        else:
            print("\n❌ Full market brain execution failed")
        return bool(success)
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure all market brain components are available")
        return False
    except Exception as e:
        print(f"❌ Execution error: {e}")
        return False

def run_pulse_only():
    """Run market pulse update only"""
    
    print("💓 MARKET PULSE UPDATE")
    print("=" * 40)
    
    try:
        from src.intelligence.market_brain.market_pulse import MarketPulseEngine
        
        pulse_engine = MarketPulseEngine()
        success = pulse_engine.compute_market_pulse()
        
        if success:
            print("✅ Market pulse updated successfully")
            
            # Show pulse summary
            summary = pulse_engine.get_pulse_summary()
            print(f"\n{summary}")
        
        return success
        
    except Exception as e:
        print(f"❌ Pulse update error: {e}")
        return False

def run_survival_only():
    """Run survival instincts check only"""
    
    print("🛡️ SURVIVAL INSTINCTS CHECK")
    print("=" * 40)
    
    try:
        from src.intelligence.market_brain.survival_instincts import SurvivalInstinctEngine
        
        survival_engine = SurvivalInstinctEngine()
        survival_state = survival_engine.assess_survival_instincts()
        
        if survival_state:
            print("✅ Survival instincts assessed successfully")
            
            # Show survival status
            mode = survival_state.get('survival_mode', 'unknown')
            emergency = survival_state.get('emergency_triggered', False)
            
            print(f"\nSurvival Status:")
            print(f"  Mode: {mode.upper()}")
            print(f"  Emergency: {'🚨 YES' if emergency else 'No'}")
            
            if emergency:
                recommendations = survival_state.get('recommendations', [])
                print(f"  Recommendations:")
                for rec in recommendations[:3]:
                    print(f"    - {rec}")
        
        return bool(survival_state)
        
    except Exception as e:
        print(f"❌ Survival check error: {e}")
        return False

def check_brain_status():
    """Check current brain system status"""
    
    print("📊 MARKET BRAIN STATUS")
    print("=" * 40)
    
    try:
        from src.intelligence.market_brain.brain_orchestrator import MarketBrainOrchestrator
        
        orchestrator = MarketBrainOrchestrator()
        brain_state = orchestrator.get_brain_status()
        
        if brain_state and brain_state.get('status') != 'not_available':
            print("✅ Market Brain is active")
            
            # Show component status
            component_status = brain_state.get('component_status', {})
            print(f"\nComponent Status:")
            for component, status in component_status.items():
                status_icon = "✅" if status else "❌"
                print(f"  {status_icon} {component.title()}")
            
            # Show intelligence summary
            intelligence = brain_state.get('intelligence_summary', {})
            
            if 'market_pulse' in intelligence:
                pulse = intelligence['market_pulse']
                print(f"\nMarket Pulse:")
                print(f"  Intensity: {pulse.get('intensity', 0):.2f}")
                print(f"  Phase: {pulse.get('phase', 'unknown')}")
                print(f"  Risk: {pulse.get('risk_level', 'unknown')}")
            
            if 'survival_status' in intelligence:
                survival = intelligence['survival_status']
                emergency_text = " 🚨" if survival.get('emergency', False) else ""
                print(f"\nSurvival Status:")
                print(f"  Mode: {survival.get('mode', 'unknown')}{emergency_text}")
                print(f"  Exposure: {survival.get('exposure_multiplier', 1.0):.1%}")
            
            # Show last update
            timestamp = brain_state.get('timestamp', '')
            if timestamp:
                print(f"\nLast Update: {timestamp}")
            
            return True
        else:
            print("❌ Market Brain is not active")
            print("   Run 'python run_market_brain.py' to initialize")
            return False
            
    except Exception as e:
        print(f"❌ Status check error: {e}")
        return False

def build_tensor_only():
    """Build market tensor only"""
    
    print("🧠 MARKET TENSOR BUILD")
    print("=" * 40)
    
    try:
        from src.intelligence.market_brain.market_tensor import MarketTensorEngine
        
        tensor_engine = MarketTensorEngine()
        tensor = tensor_engine.build_market_tensor()
        
        if not tensor.empty:
            print("✅ Market tensor built successfully")
            print(f"   Shape: {tensor.shape}")
            print(f"   Variables: {len(tensor.columns)}")
            print(f"   Date range: {tensor.index[0].date()} to {tensor.index[-1].date()}")
            return True
        else:
            print("❌ Failed to build market tensor")
            return False
            
    except Exception as e:
        print(f"❌ Tensor build error: {e}")
        return False

def build_causality_only():
    """Build causal graph only"""
    
    print("🧬 CAUSAL GRAPH BUILD")
    print("=" * 40)
    
    try:
        from src.intelligence.market_brain.causal_graph import CausalGraphEngine
        
        causal_engine = CausalGraphEngine()
        success = causal_engine.build_causal_intelligence()
        
        if success:
            print("✅ Causal graph built successfully")
            
            # Load and show graph stats
            graph = causal_engine.load_causal_graph()
            if graph:
                print(f"   Nodes: {len(graph.get('nodes', []))}")
                print(f"   Edges: {len(graph.get('edges', []))}")
            
            return True
        else:
            print("❌ Failed to build causal graph")
            return False
            
    except Exception as e:
        print(f"❌ Causal graph error: {e}")
        return False

def main():
    """Main execution function"""
    
    parser = argparse.ArgumentParser(description='Northstar Market Brain Execution')
    parser.add_argument('--pulse-only', action='store_true', 
                       help='Update market pulse only')
    parser.add_argument('--survival-only', action='store_true', 
                       help='Check survival instincts only')
    parser.add_argument('--status', action='store_true', 
                       help='Check brain system status')
    parser.add_argument('--tensor-only', action='store_true', 
                       help='Build market tensor only')
    parser.add_argument('--causality-only', action='store_true', 
                       help='Build causal graph only')
    
    args = parser.parse_args()
    
    # Execute based on arguments
    if args.status:
        success = check_brain_status()
    elif args.pulse_only:
        success = run_pulse_only()
    elif args.survival_only:
        success = run_survival_only()
    elif args.tensor_only:
        success = build_tensor_only()
    elif args.causality_only:
        success = build_causality_only()
    else:
        success = run_full_market_brain()
    
    # Exit with appropriate code
    if success:
        print(f"\n🎯 Execution completed successfully!")
        sys.exit(0)
    else:
        print(f"\n❌ Execution failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
