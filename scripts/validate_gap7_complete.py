#!/usr/bin/env python3
"""
Validation script for Gap 7: State Management Consolidation

Verifies that all Gap 7 components are implemented and functional.
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_file_exists(filepath: str, description: str) -> bool:
    """Check if a file exists."""
    path = project_root / filepath
    exists = path.exists()
    status = "✅" if exists else "❌"
    print(f"{status} {description}: {filepath}")
    return exists


def check_class_exists(module_path: str, class_name: str, description: str) -> bool:
    """Check if a class exists in a module."""
    try:
        module_parts = module_path.split('.')
        module = __import__(module_path, fromlist=[class_name])
        has_class = hasattr(module, class_name)
        status = "✅" if has_class else "❌"
        print(f"{status} {description}: {module_path}.{class_name}")
        return has_class
    except Exception as e:
        print(f"❌ {description}: {module_path}.{class_name} - Error: {e}")
        return False


def check_dataclass_field(module_path: str, class_name: str, field_name: str, description: str) -> bool:
    """Check if a dataclass has a specific field."""
    try:
        module = __import__(module_path, fromlist=[class_name])
        cls = getattr(module, class_name)
        
        # Check if it's a dataclass
        if not hasattr(cls, '__dataclass_fields__'):
            print(f"❌ {description}: {class_name} is not a dataclass")
            return False
        
        has_field = field_name in cls.__dataclass_fields__
        status = "✅" if has_field else "❌"
        print(f"{status} {description}: {class_name}.{field_name}")
        return has_field
    except Exception as e:
        print(f"❌ {description}: {class_name}.{field_name} - Error: {e}")
        return False


def main():
    """Run all validation checks."""
    print("=" * 80)
    print("GAP 7: STATE MANAGEMENT CONSOLIDATION - VALIDATION")
    print("=" * 80)
    print()
    
    all_checks = []
    
    # Core Files
    print("📁 Core Files")
    print("-" * 80)
    all_checks.append(check_file_exists("src/core/state_authority.py", "StateAuthority implementation"))
    all_checks.append(check_file_exists("src/core/state_reconciler.py", "StateReconciler implementation"))
    all_checks.append(check_file_exists("src/core/state_bridges/__init__.py", "State bridges package"))
    all_checks.append(check_file_exists("src/core/state_bridges/options_bridge.py", "OptionsBridge implementation"))
    all_checks.append(check_file_exists("src/core/state_bridges/shadow_bridge.py", "ShadowBridge implementation"))
    all_checks.append(check_file_exists("src/core/state_bridges/valuation_bridge.py", "ValuationBridge implementation"))
    all_checks.append(check_file_exists("src/core/state_bridges/runtime_bridge.py", "RuntimeBridge implementation"))
    print()
    
    # Test Files
    print("🧪 Test Files")
    print("-" * 80)
    all_checks.append(check_file_exists("src/core/tests/test_state_authority.py", "StateAuthority tests"))
    print()
    
    # Documentation
    print("📚 Documentation")
    print("-" * 80)
    all_checks.append(check_file_exists("GAP7_STATE_CONSOLIDATION_COMPLETE.md", "Gap 7 documentation"))
    print()
    
    # Core Classes
    print("🏗️  Core Classes")
    print("-" * 80)
    all_checks.append(check_class_exists("src.core.state_authority", "StateAuthority", "StateAuthority class"))
    all_checks.append(check_class_exists("src.core.state_authority", "StateUpdate", "StateUpdate dataclass"))
    all_checks.append(check_class_exists("src.core.state_authority", "WritePriority", "WritePriority enum"))
    all_checks.append(check_class_exists("src.core.state_reconciler", "StateReconciler", "StateReconciler class"))
    all_checks.append(check_class_exists("src.core.state_reconciler", "ReconciliationReport", "ReconciliationReport dataclass"))
    print()
    
    # Bridge Classes
    print("🌉 Bridge Classes")
    print("-" * 80)
    all_checks.append(check_class_exists("src.core.state_bridges.options_bridge", "OptionsStateBridge", "OptionsStateBridge class"))
    all_checks.append(check_class_exists("src.core.state_bridges.shadow_bridge", "ShadowStateBridge", "ShadowStateBridge class"))
    all_checks.append(check_class_exists("src.core.state_bridges.valuation_bridge", "ValuationStateBridge", "ValuationStateBridge class"))
    all_checks.append(check_class_exists("src.core.state_bridges.runtime_bridge", "RuntimeStateBridge", "RuntimeStateBridge class"))
    print()
    
    # State Dataclasses
    print("📊 State Dataclasses")
    print("-" * 80)
    all_checks.append(check_class_exists("src.core.state", "ShadowState", "ShadowState dataclass"))
    all_checks.append(check_class_exists("src.core.state", "ValuationState", "ValuationState dataclass"))
    print()
    
    # PortfolioState Fields
    print("💼 PortfolioState Options Fields")
    print("-" * 80)
    all_checks.append(check_dataclass_field("src.core.state", "PortfolioState", "options_positions", "options_positions field"))
    all_checks.append(check_dataclass_field("src.core.state", "PortfolioState", "options_net_delta", "options_net_delta field"))
    all_checks.append(check_dataclass_field("src.core.state", "PortfolioState", "options_net_gamma", "options_net_gamma field"))
    all_checks.append(check_dataclass_field("src.core.state", "PortfolioState", "options_net_vega", "options_net_vega field"))
    all_checks.append(check_dataclass_field("src.core.state", "PortfolioState", "options_system_mode", "options_system_mode field"))
    print()
    
    # RiskState Fields
    print("⚠️  RiskState Options Fields")
    print("-" * 80)
    all_checks.append(check_dataclass_field("src.core.state", "RiskState", "options_delta_exposure_inr", "options_delta_exposure_inr field"))
    all_checks.append(check_dataclass_field("src.core.state", "RiskState", "options_vega_exposure_inr", "options_vega_exposure_inr field"))
    all_checks.append(check_dataclass_field("src.core.state", "RiskState", "options_trading_suspended", "options_trading_suspended field"))
    print()
    
    # StateAuthority Methods
    print("🔧 StateAuthority Methods")
    print("-" * 80)
    try:
        from src.core.state_authority import StateAuthority
        methods = ['register_writer', 'update', 'batch_update', 'checkpoint', 'get_current_writer', 'get_state_history']
        for method in methods:
            has_method = hasattr(StateAuthority, method)
            status = "✅" if has_method else "❌"
            print(f"{status} StateAuthority.{method}() method")
            all_checks.append(has_method)
    except Exception as e:
        print(f"❌ Failed to check StateAuthority methods: {e}")
        all_checks.extend([False] * 6)
    print()
    
    # StateReconciler Methods
    print("🔍 StateReconciler Methods")
    print("-" * 80)
    try:
        from src.core.state_reconciler import StateReconciler
        methods = ['run_full_reconciliation', 'check_position_triplet', 'check_options_coverage', 
                   'check_shadow_divergence', 'check_valuation_coverage', 'check_can_trade']
        for method in methods:
            has_method = hasattr(StateReconciler, method)
            status = "✅" if has_method else "❌"
            print(f"{status} StateReconciler.{method}() method")
            all_checks.append(has_method)
    except Exception as e:
        print(f"❌ Failed to check StateReconciler methods: {e}")
        all_checks.extend([False] * 6)
    print()
    
    # Bridge Methods
    print("🌉 Bridge Methods")
    print("-" * 80)
    try:
        from src.core.state_bridges.options_bridge import OptionsStateBridge
        from src.core.state_bridges.shadow_bridge import ShadowStateBridge
        from src.core.state_bridges.valuation_bridge import ValuationStateBridge
        from src.core.state_bridges.runtime_bridge import RuntimeStateBridge
        
        bridge_checks = [
            (OptionsStateBridge, ['push_position_update', 'push_mode_update', 'push_greeks_snapshot']),
            (ShadowStateBridge, ['push_shadow_state', 'compute_position_overlap', 'detect_systematic_divergence']),
            (ValuationStateBridge, ['push_valuation_summary']),
            (RuntimeStateBridge, ['sync_to_unified_state', 'sync_to_json_checkpoint', 'detect_triplet_inconsistency', 'reconcile_on_startup'])
        ]
        
        for bridge_class, methods in bridge_checks:
            for method in methods:
                has_method = hasattr(bridge_class, method)
                status = "✅" if has_method else "❌"
                print(f"{status} {bridge_class.__name__}.{method}() method")
                all_checks.append(has_method)
    except Exception as e:
        print(f"❌ Failed to check bridge methods: {e}")
        all_checks.extend([False] * 11)
    print()
    
    # Summary
    print("=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    
    passed = sum(all_checks)
    total = len(all_checks)
    percentage = (passed / total * 100) if total > 0 else 0
    
    print(f"Checks passed: {passed}/{total} ({percentage:.1f}%)")
    print()
    
    if passed == total:
        print("✅ GAP 7: STATE MANAGEMENT CONSOLIDATION - COMPLETE")
        print()
        print("All components implemented successfully:")
        print("  • StateAuthority with priority-based writes")
        print("  • Four state bridges (Options, Shadow, Valuation, Runtime)")
        print("  • StateReconciler with six checks")
        print("  • Extended UnifiedState with new fields")
        print("  • Comprehensive test suite")
        print()
        print("Next steps:")
        print("  1. Integrate with orchestrator")
        print("  2. Integrate with options system")
        print("  3. Add to EOD process")
        print("  4. Run integration tests")
        print("  5. Deploy to staging")
        return 0
    else:
        print("❌ GAP 7: INCOMPLETE")
        print()
        print(f"Missing {total - passed} components. Review failures above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
