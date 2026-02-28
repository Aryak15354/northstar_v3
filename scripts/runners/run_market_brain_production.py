#!/usr/bin/env python3
"""
Production Market Brain runner.

Focused on stable, currently used components:
- market tensor
- market pulse
- survival instincts
- unified state integration
"""

from __future__ import annotations

import argparse
import sys


def run_production_brain() -> bool:
    """Run end-to-end production brain update."""
    print("🧠 NORTHSTAR PRODUCTION MARKET BRAIN")
    print("=" * 60)

    success_count = 0

    try:
        print("🧠 STEP 1: MARKET TENSOR")
        print("-" * 40)
        from src.intelligence.market_brain.market_tensor import MarketTensorEngine

        tensor_engine = MarketTensorEngine()
        tensor = tensor_engine.build_market_tensor()
        if tensor is not None and not tensor.empty:
            print(f"✅ Market Tensor: {tensor.shape}")
            success_count += 1
        else:
            print("❌ Market Tensor failed")

        print("\n💓 STEP 2: MARKET PULSE")
        print("-" * 40)
        from src.intelligence.market_brain.market_pulse import MarketPulseEngine

        pulse_engine = MarketPulseEngine()
        pulse_success = pulse_engine.compute_market_pulse()
        if pulse_success:
            pulse_state = pulse_engine.load_pulse_state() or {}
            print(
                "✅ Market Pulse: "
                f"{pulse_state.get('pulse_intensity', 0):.2f} intensity, "
                f"{pulse_state.get('market_phase', 'unknown')} phase, "
                f"{pulse_state.get('risk_level', 'unknown')} risk"
            )
            success_count += 1
        else:
            print("❌ Market Pulse failed")

        print("\n🛡️ STEP 3: SURVIVAL INSTINCTS")
        print("-" * 40)
        from src.intelligence.market_brain.survival_instincts import SurvivalInstinctEngine

        survival_engine = SurvivalInstinctEngine()
        survival_state = survival_engine.assess_survival_instincts()
        if survival_state:
            mode = survival_state.get("survival_mode", "unknown")
            emergency = survival_state.get("emergency_triggered", False)
            exposure_mult = survival_state.get("action_parameters", {}).get("exposure_multiplier", 1.0)
            emergency_text = " 🚨 EMERGENCY" if emergency else ""
            print(f"✅ Survival: {mode} mode{emergency_text} (exposure: {exposure_mult:.1%})")
            success_count += 1
        else:
            print("❌ Survival assessment failed")

        print("\n🔗 STEP 4: V3 INTEGRATION")
        print("-" * 40)
        from src.cohesion.unified_state_manager import UnifiedStateManager

        manager = UnifiedStateManager()
        market_state = manager.compute_market_state()
        brain_fields = ["pulse_intensity", "market_phase", "survival_mode", "brain_active"]
        integrated = [f for f in brain_fields if f in market_state]
        if len(integrated) >= 3:
            print(f"✅ V3 Integration: {len(integrated)}/4 brain fields integrated")
            print(f"   Market Phase: {market_state.get('market_phase', 'unknown')}")
            print(f"   Survival Mode: {market_state.get('survival_mode', 'unknown')}")
            print(f"   Allowed Exposure: {market_state.get('allowed_exposure', 0):.1f}%")
            success_count += 1
        else:
            print(f"❌ V3 Integration: Only {len(integrated)}/4 fields integrated")

        print("\n🎯 PRODUCTION BRAIN SUMMARY")
        print("=" * 60)
        print(f"Components successful: {success_count}/4")
        print(
            "Status: "
            f"{'✅ OPERATIONAL' if success_count >= 3 else '⚠️ PARTIAL' if success_count >= 2 else '❌ FAILED'}"
        )
        return success_count >= 3
    except Exception as e:
        print(f"❌ Production brain error: {e}")
        return False


def run_quick_pulse() -> bool:
    """Run only pulse update."""
    print("💓 QUICK PULSE UPDATE")
    print("=" * 40)
    try:
        from src.intelligence.market_brain.market_pulse import MarketPulseEngine

        pulse_engine = MarketPulseEngine()
        success = pulse_engine.compute_market_pulse()
        if success:
            print("✅ Pulse updated successfully")
            print(pulse_engine.get_pulse_summary())
            return True
        print("❌ Pulse update failed")
        return False
    except Exception as e:
        print(f"❌ Quick pulse error: {e}")
        return False


def run_brain_monitoring() -> bool:
    """Run monitor health checks."""
    print("🔍 MARKET BRAIN MONITORING")
    print("=" * 60)
    try:
        from src.intelligence.market_brain.brain_monitor import MarketBrainMonitor

        monitor = MarketBrainMonitor()
        results = monitor.run_complete_monitoring()
        overall = results.get("health_status", {}).get("overall_health", "unknown")
        alerts = len(results.get("health_status", {}).get("alerts", [])) + len(results.get("anomalies", []))
        print("\n🎯 MONITORING SUMMARY")
        print("-" * 40)
        print(f"Overall Health: {str(overall).upper()}")
        print(f"Active Alerts: {alerts}")
        return overall in {"excellent", "good"}
    except Exception as e:
        print(f"❌ Monitoring error: {e}")
        return False


def show_brain_dashboard() -> bool:
    """Show dashboard summary in terminal."""
    print("📊 MARKET BRAIN DASHBOARD")
    print("=" * 60)
    try:
        from src.intelligence.market_brain.market_pulse import MarketPulseEngine
        from src.intelligence.market_brain.survival_instincts import SurvivalInstinctEngine

        pulse_state = MarketPulseEngine().load_pulse_state() or {}
        survival_state = SurvivalInstinctEngine().load_survival_state() or {}

        print("💓 MARKET PULSE")
        print("-" * 20)
        print(f"  Intensity: {pulse_state.get('pulse_intensity', 0):.2f}")
        print(f"  Phase: {str(pulse_state.get('market_phase', 'unknown')).title()}")
        print(f"  Risk Level: {str(pulse_state.get('risk_level', 'unknown')).title()}")
        print(f"  Active Forces: {len(pulse_state.get('dominant_forces', {}))}")

        print("\n🛡️ SURVIVAL STATUS")
        print("-" * 20)
        mode = survival_state.get("survival_mode", "unknown")
        emergency = survival_state.get("emergency_triggered", False)
        status_icon = "🚨" if emergency else "✅" if mode == "normal" else "⚠️"
        print(f"  Status: {status_icon} {str(mode).upper()}")
        print(f"  Emergency: {'YES' if emergency else 'No'}")
        print(f"  Exposure Multiplier: {survival_state.get('action_parameters', {}).get('exposure_multiplier', 1.0):.1%}")
        return True
    except Exception as e:
        print(f"❌ Dashboard error: {e}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Northstar Production Market Brain")
    parser.add_argument("--quick", action="store_true", help="Quick pulse update only")
    parser.add_argument("--monitor", action="store_true", help="Run monitoring/health checks")
    parser.add_argument("--dashboard", action="store_true", help="Show terminal dashboard")
    args = parser.parse_args()

    if args.dashboard:
        ok = show_brain_dashboard()
    elif args.monitor:
        ok = run_brain_monitoring()
    elif args.quick:
        ok = run_quick_pulse()
    else:
        ok = run_production_brain()

    print("\n🎯 Production brain execution completed successfully!" if ok else "\n❌ Production brain execution failed!")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
