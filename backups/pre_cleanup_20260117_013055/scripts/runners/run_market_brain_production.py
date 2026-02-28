#!/usr/bin/env python3
"""
🧠 PRODUCTION MARKET BRAIN - NORTHSTAR V3
Production-ready Market Brain focusing on working components

This version focuses on the core working components:
- Market Tensor: Unified market representation ✅
- Market Pulse: Real-time force detection ✅  
- Survival Instincts: System health monitoring ✅
- V3 Integration: Enhanced market state ✅

Usage:
    python run_market_brain_production.py           # Full production brain
    python run_market_brain_production.py --quick   # Quick pulse update only
"""

import sys
import os
import argparse
from datetime import datetime

def run_production_brain():
    """Run production-ready market brain"""
    
    print("🧠 NORTHSTAR PRODUCTION MARKET BRAIN")
    print("=" * 60)
    
    success_count = 0
    
    try:
        # Step 1: Build/Update Market Tensor
        print("🧠 STEP 1: MARKET TENSOR")
        print("-" * 40)
        
        from src.intelligence.market_brain.market_tensor import MarketTensorEngine
        
        tensor_engine = MarketTensorEngine()
        tensor = tensor_engine.build_market_tensor()
        
        if not tensor.empty:
            print(f"✅ Market Tensor: {tensor.shape}")
            success_count += 1
        else:
            print("❌ Market Tensor failed")
        
        # Step 2: Compute Market Pulse
        print("\n💓 STEP 2: MARKET PULSE")
        print("-" * 40)
        
        from src.intelligence.market_brain.market_pulse import MarketPulseEngine
        
        pulse_engine = MarketPulseEngine()
        pulse_success = pulse_engine.compute_market_pulse()
        
        if pulse_success:
            pulse_state = pulse_engine.load_pulse_state()
            intensity = pulse_state.get('pulse_intensity', 0)
            phase = pulse_state.get('market_phase', 'unknown')
            risk = pulse_state.get('risk_level', 'unknown')
            
            print(f"✅ Market Pulse: {intensity:.2f} intensity, {phase} phase, {risk} risk")
            success_count += 1
        else:
            print("❌ Market Pulse failed")
        
        # Step 3: Assess Survival Instincts
        print("\n🛡️ STEP 3: SURVIVAL INSTINCTS")
        print("-" * 40)
        
        from src.intelligence.market_brain.survival_instincts import SurvivalInstinctEngine
        
        survival_engine = SurvivalInstinctEngine()
        survival_state = survival_engine.assess_survival_instincts()
        
        if survival_state:
            mode = survival_state.get('survival_mode', 'unknown')
            emergency = survival_state.get('emergency_triggered', False)
            exposure_mult = survival_state.get('action_parameters', {}).get('exposure_multiplier', 1.0)
            
            emergency_text = " 🚨 EMERGENCY" if emergency else ""
            print(f"✅ Survival: {mode} mode{emergency_text} (exposure: {exposure_mult:.1%})")
            success_count += 1
        else:
            print("❌ Survival assessment failed")
        
        # Step 4: Integrate with V3 Market State
        print("\n🔗 STEP 4: V3 INTEGRATION")
        print("-" * 40)
        
        from src.cohesion.unified_state_manager import UnifiedStateManager
        
        market_engine = UnifiedStateManager()
        market_state = market_engine.compute_market_state()
        
        # Check brain integration
        brain_fields = ['pulse_intensity', 'market_phase', 'survival_mode', 'brain_active']
        integrated_fields = [field for field in brain_fields if field in market_state]
        
        if len(integrated_fields) >= 3:
            print(f"✅ V3 Integration: {len(integrated_fields)}/4 brain fields integrated")
            print(f"   Market Phase: {market_state.get('market_phase', 'unknown')}")
            print(f"   Survival Mode: {market_state.get('survival_mode', 'unknown')}")
            print(f"   Allowed Exposure: {market_state.get('allowed_exposure', 0):.1f}%")
            success_count += 1
        else:
            print(f"❌ V3 Integration: Only {len(integrated_fields)}/4 fields integrated")
        
        # Summary
        print(f"\n🎯 PRODUCTION BRAIN SUMMARY")
        print("=" * 60)
        print(f"Components successful: {success_count}/4")
        print(f"Status: {'✅ OPERATIONAL' if success_count >= 3 else '⚠️ PARTIAL' if success_count >= 2 else '❌ FAILED'}")
        
        if success_count >= 3:
            print("\n🎉 Production Market Brain is operational!")
            print("   Northstar now has:")
            print("   🧠 Market sensing (tensor)")
            print("   💓 Real-time pulse detection")
            print("   🛡️ Survival instinct monitoring")
            print("   🔗 V3 spine integration")
        
        return success_count >= 3
        
    except Exception as e:
        print(f"❌ Production brain error: {e}")
        return False

def run_quick_pulse():
    """Run quick pulse update only"""
    
    print("💓 QUICK PULSE UPDATE")
    print("=" * 40)
    
    try:
        from src.intelligence.market_brain.market_pulse import MarketPulseEngine
        
        pulse_engine = MarketPulseEngine()
        success = pulse_engine.compute_market_pulse()
        
        if success:
            summary = pulse_engine.get_pulse_summary()
            print("✅ Pulse updated successfully")
            print(f"\n{summary}")
            return True
        else:
            print("❌ Pulse update failed")
            return False
            
    except Exception as e:
        print(f"❌ Quick pulse error: {e}")
        return False

def show_brain_dashboard():
    """Run Market Brain monitoring and health checks"""
    
    print("🔍 MARKET BRAIN MONITORING")
    print("=" * 60)
    
    try:
        import sys
                from src.intelligence.market_brain.brain_monitor import MarketBrainMonitor
        
        monitor = MarketBrainMonitor()
        results = monitor.run_complete_monitoring()
        
        # Summary
        overall_health = results['health_status']['overall_health']
        alert_count = len(results['health_status']['alerts'] + results['anomalies'])
        
        print(f"\n🎯 MONITORING SUMMARY")
        print("-" * 40)
        print(f"Overall Health: {overall_health.upper()}")
        print(f"Active Alerts: {alert_count}")
        
        return overall_health in ['excellent', 'good']
        
    except Exception as e:
        print(f"❌ Monitoring error: {e}")
        return False
    """Show production brain dashboard"""
    
    print("📊 MARKET BRAIN DASHBOARD")
    print("=" * 60)
    
    try:
        # Use the enhanced dashboard
        import sys
                from src.intelligence.market_brain.brain_dashboard import MarketBrainDashboard
        
        dashboard = MarketBrainDashboard()
        dashboard.run_complete_dashboard()
        
        return True
        
    except Exception as e:
        print(f"❌ Dashboard error: {e}")
        
        # Fallback to basic dashboard
        try:
            # Load current state
            from src.intelligence.market_brain.market_pulse import MarketPulseEngine
            from src.intelligence.market_brain.survival_instincts import SurvivalInstinctEngine
            
            pulse_engine = MarketPulseEngine()
            survival_engine = SurvivalInstinctEngine()
            
            pulse_state = pulse_engine.load_pulse_state()
            survival_state = survival_engine.load_survival_state()
            
            # Market Pulse Section
            print("💓 MARKET PULSE")
            print("-" * 20)
            if pulse_state:
                print(f"  Intensity: {pulse_state.get('pulse_intensity', 0):.2f}")
                print(f"  Phase: {pulse_state.get('market_phase', 'unknown').title()}")
                print(f"  Risk Level: {pulse_state.get('risk_level', 'unknown').title()}")
                print(f"  Active Forces: {len(pulse_state.get('dominant_forces', {}))}")
                
                # Show top forces
                forces = pulse_state.get('dominant_forces', {})
                if forces:
                    print("  Top Forces:")
                    for i, (force, data) in enumerate(list(forces.items())[:3]):
                        direction = "↑" if data.get('direction') == 'up' else "↓"
                        print(f"    {i+1}. {force}: {data.get('strength', 0):.2f} {direction}")
            else:
                print("  ⚠️ No pulse data available")
            
            # Survival Status Section
            print(f"\n🛡️ SURVIVAL STATUS")
            print("-" * 20)
            if survival_state:
                mode = survival_state.get('survival_mode', 'unknown')
                emergency = survival_state.get('emergency_triggered', False)
                exposure_mult = survival_state.get('action_parameters', {}).get('exposure_multiplier', 1.0)
                
                status_icon = "🚨" if emergency else "✅" if mode == 'normal' else "⚠️"
                print(f"  Status: {status_icon} {mode.upper()}")
                print(f"  Emergency: {'YES' if emergency else 'No'}")
                print(f"  Exposure Multiplier: {exposure_mult:.1%}")
                
                # Show assessments
                assessments = survival_state.get('assessments', {})
                if assessments:
                    print("  Health Metrics:")
                    for metric, data in assessments.items():
                        if isinstance(data, dict) and 'stress_level' in data:
                            level = data.get('stress_level', 'unknown')
                            print(f"    {metric.replace('_', ' ').title()}: {level}")
            else:
                print("  ⚠️ No survival data available")
            
            # Market State Integration
            print(f"\n🔗 V3 INTEGRATION")
            print("-" * 20)
            
            from src.cohesion.unified_state_manager import UnifiedStateManager
            market_engine = UnifiedStateManager()
            
            try:
                market_state = market_engine.compute_market_state()
                
                print(f"  Brain Active: {'✅ Yes' if market_state.get('brain_active', False) else '❌ No'}")
                print(f"  Allowed Exposure: {market_state.get('allowed_exposure', 0):.1f}%")
                print(f"  Risk-On Probability: {market_state.get('risk_on_probability', 0):.1%}")
                print(f"  Market Regime: {market_state.get('macro_regime', 'unknown')}")
                
            except Exception as e:
                print(f"  ❌ Integration error: {e}")
            
            return True
            
        except Exception as e2:
            print(f"❌ Fallback dashboard error: {e2}")
            return False

def run_brain_monitoring():
    """Run Market Brain monitoring and health checks"""
    
    print("🔍 MARKET BRAIN MONITORING")
    print("=" * 60)
    
    try:
        import sys
                from src.intelligence.market_brain.brain_monitor import MarketBrainMonitor
        
        monitor = MarketBrainMonitor()
        results = monitor.run_complete_monitoring()
        
        # Summary
        overall_health = results['health_status']['overall_health']
        alert_count = len(results['health_status']['alerts'] + results['anomalies'])
        
        print(f"\n🎯 MONITORING SUMMARY")
        print("-" * 40)
        print(f"Overall Health: {overall_health.upper()}")
        print(f"Active Alerts: {alert_count}")
        
        return overall_health in ['excellent', 'good']
        
    except Exception as e:
        print(f"❌ Monitoring error: {e}")
        return False

def main():
    """Main execution function"""
    
    parser = argparse.ArgumentParser(description='Northstar Production Market Brain')
    parser.add_argument('--quick', action='store_true', 
                       help='Quick pulse update only')
    parser.add_argument('--monitor', action='store_true', 
                       help='Run brain monitoring and health checks')
    parser.add_argument('--dashboard', action='store_true', 
                       help='Show brain dashboard')
    
    args = parser.parse_args()
    
    # Execute based on arguments
    if args.dashboard:
        success = show_brain_dashboard()
    elif args.monitor:
        success = run_brain_monitoring()
    elif args.quick:
        success = run_quick_pulse()
    else:
        success = run_production_brain()
    
    # Exit with appropriate code
    if success:
        print(f"\n🎯 Production brain execution completed successfully!")
        sys.exit(0)
    else:
        print(f"\n❌ Production brain execution failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()