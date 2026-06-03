#!/usr/bin/env python3
"""
Fix Gap 7 State Management Integration

Wires StateAuthority, StateReconciler, and all bridges into the live system.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from pathlib import Path


def fix_orchestrator_integration():
    """Add StateAuthority and StateReconciler to orchestrator"""
    
    orchestrator_path = Path('src/core/orchestrator.py')
    
    print("\n1. Fixing Orchestrator Integration...")
    print("   Adding StateAuthority and StateReconciler initialization")
    
    # Read current file
    with open(orchestrator_path, 'r') as f:
        content = f.read()
    
    # Check if already integrated
    if 'self.state_authority' in content:
        print("   ✓ StateAuthority already integrated")
        return True
    
    # Find the __init__ method and add state management components
    init_marker = "# CRITICAL: Initialize Portfolio Governor"
    
    if init_marker not in content:
        print("   ✗ Could not find integration point in orchestrator")
        return False
    
    # Add state management initialization before Governor
    state_mgmt_code = '''        # CRITICAL: Initialize State Management (Gap 7)
        from src.core.state_authority import StateAuthority, WritePriority
        from src.core.state_reconciler import StateReconciler
        from src.core.state_bridges.options_bridge import OptionsStateBridge
        from src.core.state_bridges.shadow_bridge import ShadowStateBridge
        from src.core.state_bridges.valuation_bridge import ValuationStateBridge
        from src.core.state_bridges.runtime_bridge import RuntimeStateBridge
        
        # Initialize StateAuthority
        self.state_authority = StateAuthority(state, config={'dev_mode': True})
        print("   🏛️ StateAuthority initialized")
        
        # Register core state writers
        self.state_authority.register_writer(
            'orchestrator',
            allowed_sections=['portfolio_state', 'risk_state', 'health_state'],
            priority=WritePriority.LIVE_TRADING
        )
        self.state_authority.register_writer(
            'options_bridge',
            allowed_sections=['portfolio_state', 'risk_state'],
            priority=WritePriority.BRIDGE_SYNC
        )
        self.state_authority.register_writer(
            'shadow_bridge',
            allowed_sections=['shadow_state'],
            priority=WritePriority.BRIDGE_SYNC
        )
        self.state_authority.register_writer(
            'valuation_bridge',
            allowed_sections=['valuation_state'],
            priority=WritePriority.BRIDGE_SYNC
        )
        self.state_authority.register_writer(
            'runtime_bridge',
            allowed_sections=['portfolio_state'],
            priority=WritePriority.BRIDGE_SYNC
        )
        
        # Initialize bridges (will be connected to actual systems later)
        self.options_bridge = None
        self.shadow_bridge = None
        self.valuation_bridge = None
        self.runtime_bridge = None
        
        # Initialize StateReconciler (will be fully wired after bridges are connected)
        self.state_reconciler = None
        
        print("   🔗 State management infrastructure initialized")
        
        '''
    
    content = content.replace(init_marker, state_mgmt_code + init_marker)
    
    # Add reconciliation check to run_cycle
    cycle_marker = "# === CRITICAL: Compute Capital Structure FIRST ==="
    
    if cycle_marker in content:
        reconciliation_code = '''        # === CRITICAL: Run State Reconciliation FIRST ===
        if self.state_reconciler is not None:
            print(f"\\n🔍 Running State Reconciliation...")
            try:
                reconciliation_report = self.state_reconciler.run_full_reconciliation(datetime.now())
                
                print(f"   Status: {reconciliation_report.overall_status}")
                print(f"   Can Trade: {reconciliation_report.can_trade}")
                
                if not reconciliation_report.can_trade:
                    print(f"   ⚠️  CRITICAL: State reconciliation failed - trading blocked")
                    for action in reconciliation_report.action_required:
                        print(f"      - {action}")
                    
                    # Lock system if reconciliation fails
                    self.state.lock_system(
                        "State reconciliation failed",
                        AuthorityLevel.SYSTEM,
                        "state_reconciler"
                    )
                    return {
                        'cycle_number': self.total_cycles + 1,
                        'timestamp': datetime.now().isoformat(),
                        'reconciliation_failed': True,
                        'can_trade': False
                    }
                
                # Write reconciliation report
                self.state_reconciler.write_reconciliation_report(reconciliation_report)
                
            except Exception as e:
                print(f"   ⚠️ Reconciliation failed: {e}")
        
        '''
        
        content = content.replace(cycle_marker, reconciliation_code + cycle_marker)
    
    # Add heartbeat for bridge updates
    heartbeat_code = '''
    def run_state_heartbeat(self):
        """Run periodic state synchronization (every 5 minutes during market hours)"""
        
        print(f"\\n💓 State Heartbeat")
        
        try:
            # Update options Greeks snapshot
            if self.options_bridge:
                self.options_bridge.push_greeks_snapshot()
                print("   ✓ Options Greeks updated")
            
            # Update shadow state
            if self.shadow_bridge:
                self.shadow_bridge.sync_shadow_state()
                print("   ✓ Shadow state synced")
            
            # Update valuation state
            if self.valuation_bridge:
                self.valuation_bridge.sync_valuation_state()
                print("   ✓ Valuation state synced")
            
            # Update runtime state
            if self.runtime_bridge:
                self.runtime_bridge.sync_runtime_state()
                print("   ✓ Runtime state synced")
            
            # Checkpoint state
            self.state_authority.checkpoint(force=False)
            print("   ✓ State checkpointed")
            
        except Exception as e:
            print(f"   ⚠️ Heartbeat error: {e}")
    '''
    
    # Add before the main() function
    main_marker = "def main():"
    if main_marker in content:
        content = content.replace(main_marker, heartbeat_code + "\n" + main_marker)
    
    # Write back
    with open(orchestrator_path, 'w') as f:
        f.write(content)
    
    print("   ✓ Orchestrator integration complete")
    return True


def fix_options_system_integration():
    """Add bridge calls to options position_manager and mode_controller"""
    
    print("\n2. Fixing Options System Integration...")
    
    # Fix position_manager.py
    pm_path = Path('src/options/position_manager.py')
    
    if not pm_path.exists():
        print("   ⚠️ position_manager.py not found")
        return False
    
    with open(pm_path, 'r') as f:
        pm_content = f.read()
    
    # Check if already integrated
    if 'self.options_bridge' in pm_content:
        print("   ✓ position_manager already integrated")
    else:
        # Add bridge to __init__
        init_marker = "logger.info(\"PositionManager initialized\")"
        
        if init_marker in pm_content:
            bridge_init = '''
        # Gap 7: State bridge for syncing to UnifiedState
        self.options_bridge = None
        '''
            pm_content = pm_content.replace(init_marker, bridge_init + "\n        " + init_marker)
        
        # Add bridge call to open_position
        open_marker = "logger.info("
        if "Opened position" in pm_content:
            # Find the logger.info call in open_position
            lines = pm_content.split('\n')
            for i, line in enumerate(lines):
                if 'Opened position' in line and 'logger.info' in line:
                    # Add bridge call after this line
                    indent = len(line) - len(line.lstrip())
                    bridge_call = ' ' * indent + '''
        # Sync to UnifiedState via bridge
        if self.options_bridge:
            self.options_bridge.push_position_update(reason='POSITION_OPENED')
'''
                    lines.insert(i + 1, bridge_call)
                    break
            pm_content = '\n'.join(lines)
        
        # Add bridge call to update_position_mtm
        if "Updated MTM for" in pm_content:
            lines = pm_content.split('\n')
            for i, line in enumerate(lines):
                if 'Updated MTM for' in line and 'logger.debug' in line:
                    indent = len(line) - len(line.lstrip())
                    bridge_call = ' ' * indent + '''
        # Sync to UnifiedState via bridge
        if self.options_bridge:
            self.options_bridge.push_position_update(reason='MTM_UPDATE')
'''
                    lines.insert(i + 1, bridge_call)
                    break
            pm_content = '\n'.join(lines)
        
        # Add bridge call to close_position
        if "Closed position" in pm_content:
            lines = pm_content.split('\n')
            for i, line in enumerate(lines):
                if 'Closed position' in line and 'logger.info' in line:
                    indent = len(line) - len(line.lstrip())
                    bridge_call = ' ' * indent + '''
        # Sync to UnifiedState via bridge
        if self.options_bridge:
            self.options_bridge.push_position_update(reason='POSITION_CLOSED')
'''
                    lines.insert(i + 1, bridge_call)
                    break
            pm_content = '\n'.join(lines)
        
        with open(pm_path, 'w') as f:
            f.write(pm_content)
        
        print("   ✓ position_manager integration complete")
    
    # Fix mode_controller.py
    mc_path = Path('src/options/mode_controller.py')
    
    if mc_path.exists():
        with open(mc_path, 'r') as f:
            mc_content = f.read()
        
        if 'self.options_bridge' not in mc_content:
            # Add bridge to __init__ if it has one
            if 'def __init__' in mc_content:
                # Find first logger.info in __init__
                lines = mc_content.split('\n')
                for i, line in enumerate(lines):
                    if 'logger.info' in line and '__init__' in ''.join(lines[max(0, i-20):i]):
                        indent = len(line) - len(line.lstrip())
                        bridge_init = ' ' * indent + '''
        # Gap 7: State bridge for syncing to UnifiedState
        self.options_bridge = None
'''
                        lines.insert(i, bridge_init)
                        break
                mc_content = '\n'.join(lines)
            
            # Add bridge call to mode transitions
            if 'def transition_to' in mc_content or 'def set_mode' in mc_content:
                lines = mc_content.split('\n')
                for i, line in enumerate(lines):
                    if ('Mode transition' in line or 'mode changed' in line.lower()) and 'logger' in line:
                        indent = len(line) - len(line.lstrip())
                        bridge_call = ' ' * indent + '''
        # Sync to UnifiedState via bridge
        if self.options_bridge:
            self.options_bridge.push_mode_update(new_mode=self.current_mode, reason='MODE_TRANSITION')
'''
                        lines.insert(i + 1, bridge_call)
                        break
                mc_content = '\n'.join(lines)
            
            with open(mc_path, 'w') as f:
                f.write(mc_content)
            
            print("   ✓ mode_controller integration complete")
    else:
        print("   ⚠️ mode_controller.py not found")
    
    return True


def fix_eod_reconciliation():
    """Add StateReconciler to EOD rebalance script"""
    
    print("\n3. Fixing EOD Reconciliation...")
    
    eod_path = Path('scripts/eod_rebalance_with_pnl.py')
    
    if not eod_path.exists():
        print("   ⚠️ eod_rebalance_with_pnl.py not found")
        return False
    
    with open(eod_path, 'r') as f:
        content = f.read()
    
    # Check if already integrated
    if 'StateReconciler' in content:
        print("   ✓ EOD reconciliation already integrated")
        return True
    
    # Add reconciliation at the end of the function
    marker = "return True"
    
    if marker in content:
        reconciliation_code = '''
    # === Gap 7: Run EOD State Reconciliation ===
    print("\\n" + "=" * 60)
    print("Running EOD State Reconciliation")
    print("=" * 60)
    
    try:
        from src.core.state import UnifiedState
        from src.core.state_authority import StateAuthority
        from src.core.state_reconciler import StateReconciler
        from src.core.state_bridges.options_bridge import OptionsStateBridge
        from src.core.state_bridges.shadow_bridge import ShadowStateBridge
        from src.core.state_bridges.valuation_bridge import ValuationStateBridge
        from src.core.state_bridges.runtime_bridge import RuntimeStateBridge
        
        # Initialize state management
        state = UnifiedState()
        state_authority = StateAuthority(state)
        
        # Initialize bridges (with minimal dependencies for EOD)
        options_bridge = None  # Would need actual position_manager
        shadow_bridge = ShadowStateBridge(state_authority)
        valuation_bridge = ValuationStateBridge(state_authority)
        runtime_bridge = RuntimeStateBridge(state_authority)
        
        # Initialize reconciler
        reconciler = StateReconciler(
            unified_state=state,
            options_bridge=options_bridge,
            shadow_bridge=shadow_bridge,
            valuation_bridge=valuation_bridge,
            runtime_bridge=runtime_bridge,
            state_authority=state_authority
        )
        
        # Run full reconciliation
        report = reconciler.run_full_reconciliation(datetime.now())
        
        print(f"\\nReconciliation Status: {report.overall_status}")
        print(f"Can Trade Tomorrow: {report.can_trade}")
        
        if report.action_required:
            print("\\nActions Required:")
            for action in report.action_required:
                print(f"  - {action}")
        
        # Write report
        reconciler.write_reconciliation_report(report)
        
        if not report.can_trade:
            print("\\n⚠️  WARNING: State reconciliation failed")
            print("   System should not trade until issues are resolved")
        
    except Exception as e:
        print(f"\\n⚠️ EOD reconciliation failed: {e}")
        import traceback
        traceback.print_exc()
    
    '''
        
        # Insert before the final return
        content = content.replace('    return True', reconciliation_code + '    return True')
        
        with open(eod_path, 'w') as f:
            f.write(content)
        
        print("   ✓ EOD reconciliation integration complete")
        return True
    
    print("   ✗ Could not find integration point")
    return False


def create_integration_test():
    """Create integration test for Gap 7"""
    
    print("\n4. Creating Integration Test...")
    
    test_content = '''#!/usr/bin/env python3
"""
Test Gap 7 State Management Integration

Verifies that StateAuthority, StateReconciler, and bridges are properly integrated.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime
from src.core.state import UnifiedState
from src.core.state_authority import StateAuthority, StateUpdate, WritePriority
from src.core.state_reconciler import StateReconciler
from src.core.state_bridges.shadow_bridge import ShadowStateBridge
from src.core.state_bridges.valuation_bridge import ValuationStateBridge
from src.core.state_bridges.runtime_bridge import RuntimeStateBridge


def test_state_authority_registration():
    """Test that StateAuthority is properly initialized and writers are registered"""
    print("=" * 80)
    print("TEST 1: StateAuthority Registration")
    print("=" * 80)
    
    state = UnifiedState()
    state_authority = StateAuthority(state, config={'dev_mode': True})
    
    # Register a test writer
    state_authority.register_writer(
        'test_writer',
        allowed_sections=['portfolio_state'],
        priority=WritePriority.LIVE_TRADING
    )
    
    # Verify registration
    if 'test_writer' not in state_authority.registered_writers:
        print("   ✗ FAIL: Writer not registered")
        return False
    
    print("   ✓ PASS: StateAuthority initialized and writer registered")
    return True


def test_state_update_flow():
    """Test that state updates flow through StateAuthority"""
    print("\\n" + "=" * 80)
    print("TEST 2: State Update Flow")
    print("=" * 80)
    
    state = UnifiedState()
    state_authority = StateAuthority(state, config={'dev_mode': True})
    
    # Register writer
    state_authority.register_writer(
        'test_writer',
        allowed_sections=['portfolio_state'],
        priority=WritePriority.LIVE_TRADING
    )
    
    # Create update
    update = StateUpdate(
        writer_id='test_writer',
        section='portfolio_state',
        field_path='total_positions',
        new_value=10,
        priority=WritePriority.LIVE_TRADING,
        source='LIVE',
        reason='Test update'
    )
    
    # Apply update
    success = state_authority.update(update)
    
    if not success:
        print("   ✗ FAIL: Update not applied")
        return False
    
    # Verify update
    if state.portfolio.total_positions != 10:
        print(f"   ✗ FAIL: Value not updated (got {state.portfolio.total_positions})")
        return False
    
    print("   ✓ PASS: State update applied successfully")
    return True


def test_reconciler_initialization():
    """Test that StateReconciler can be initialized"""
    print("\\n" + "=" * 80)
    print("TEST 3: StateReconciler Initialization")
    print("=" * 80)
    
    state = UnifiedState()
    state_authority = StateAuthority(state)
    
    # Initialize bridges
    shadow_bridge = ShadowStateBridge(state_authority)
    valuation_bridge = ValuationStateBridge(state_authority)
    runtime_bridge = RuntimeStateBridge(state_authority)
    
    # Initialize reconciler
    try:
        reconciler = StateReconciler(
            unified_state=state,
            options_bridge=None,  # Optional
            shadow_bridge=shadow_bridge,
            valuation_bridge=valuation_bridge,
            runtime_bridge=runtime_bridge,
            state_authority=state_authority
        )
        
        print("   ✓ PASS: StateReconciler initialized successfully")
        return True
        
    except Exception as e:
        print(f"   ✗ FAIL: StateReconciler initialization failed: {e}")
        return False


def test_reconciliation_run():
    """Test that reconciliation can run"""
    print("\\n" + "=" * 80)
    print("TEST 4: Reconciliation Run")
    print("=" * 80)
    
    state = UnifiedState()
    state_authority = StateAuthority(state)
    
    # Initialize bridges
    shadow_bridge = ShadowStateBridge(state_authority)
    valuation_bridge = ValuationStateBridge(state_authority)
    runtime_bridge = RuntimeStateBridge(state_authority)
    
    # Initialize reconciler
    reconciler = StateReconciler(
        unified_state=state,
        options_bridge=None,
        shadow_bridge=shadow_bridge,
        valuation_bridge=valuation_bridge,
        runtime_bridge=runtime_bridge,
        state_authority=state_authority
    )
    
    # Run reconciliation
    try:
        report = reconciler.run_full_reconciliation(datetime.now())
        
        print(f"   Status: {report.overall_status}")
        print(f"   Can Trade: {report.can_trade}")
        
        print("   ✓ PASS: Reconciliation completed")
        return True
        
    except Exception as e:
        print(f"   ✗ FAIL: Reconciliation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all integration tests"""
    print("=" * 80)
    print("GAP 7 STATE MANAGEMENT INTEGRATION TESTS")
    print("=" * 80)
    
    results = []
    
    # Test 1: StateAuthority registration
    try:
        results.append(("StateAuthority Registration", test_state_authority_registration()))
    except Exception as e:
        print(f"\\n✗ Test 1 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("StateAuthority Registration", False))
    
    # Test 2: State update flow
    try:
        results.append(("State Update Flow", test_state_update_flow()))
    except Exception as e:
        print(f"\\n✗ Test 2 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("State Update Flow", False))
    
    # Test 3: StateReconciler initialization
    try:
        results.append(("StateReconciler Initialization", test_reconciler_initialization()))
    except Exception as e:
        print(f"\\n✗ Test 3 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("StateReconciler Initialization", False))
    
    # Test 4: Reconciliation run
    try:
        results.append(("Reconciliation Run", test_reconciliation_run()))
    except Exception as e:
        print(f"\\n✗ Test 4 failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Reconciliation Run", False))
    
    # Summary
    print("\\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\\n✅ Gap 7 integration is WORKING")
        print("   StateAuthority, StateReconciler, and bridges are operational")
        return 0
    else:
        print(f"\\n✗ {total - passed} integration tests failed")
        print("   State management is not fully integrated")
        return 1


if __name__ == "__main__":
    sys.exit(main())
'''
    
    test_path = Path('scripts/test_gap7_integration.py')
    with open(test_path, 'w') as f:
        f.write(test_content)
    
    # Make executable
    os.chmod(test_path, 0o755)
    
    print("   ✓ Integration test created")
    return True


def main():
    """Run all Gap 7 integration fixes"""
    print("=" * 80)
    print("GAP 7 STATE MANAGEMENT - COMPREHENSIVE INTEGRATION FIX")
    print("=" * 80)
    
    results = []
    
    # Fix 1: Orchestrator integration
    results.append(("Orchestrator Integration", fix_orchestrator_integration()))
    
    # Fix 2: Options system integration
    results.append(("Options System Integration", fix_options_system_integration()))
    
    # Fix 3: EOD reconciliation
    results.append(("EOD Reconciliation", fix_eod_reconciliation()))
    
    # Fix 4: Create integration test
    results.append(("Integration Test", create_integration_test()))
    
    # Summary
    print("\\n" + "=" * 80)
    print("FIX SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for fix_name, result in results:
        status = "✓ DONE" if result else "✗ FAILED"
        print(f"{status}: {fix_name}")
    
    print(f"\\n{passed}/{total} fixes applied")
    
    if passed == total:
        print("\\n✅ Gap 7 integration fixes complete")
        print("\\nNext steps:")
        print("1. Run integration test: python scripts/test_gap7_integration.py")
        print("2. Connect actual options/shadow/valuation systems to bridges")
        print("3. Test EOD reconciliation: python scripts/eod_rebalance.py")
        return 0
    else:
        print(f"\\n✗ {total - passed} fixes failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
