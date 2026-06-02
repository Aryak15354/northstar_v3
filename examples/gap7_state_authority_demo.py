#!/usr/bin/env python3
"""
Gap 7 State Authority Demo

Demonstrates the state consolidation layer in action:
- StateAuthority with priority-based writes
- State bridges synchronizing domain state
- StateReconciler detecting divergences
"""

import sys
from pathlib import Path
from datetime import datetime
import tempfile

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.state import UnifiedState
from src.core.state_authority import StateAuthority, StateUpdate, WritePriority


def demo_state_authority():
    """Demonstrate StateAuthority basic functionality."""
    print("=" * 80)
    print("GAP 7 DEMO: StateAuthority - Single Write Interface")
    print("=" * 80)
    print()
    
    # Create UnifiedState and StateAuthority
    print("1️⃣  Creating UnifiedState and StateAuthority...")
    state = UnifiedState()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            'state_change_log_path': f'{tmpdir}/state_change_log.jsonl',
            'checkpoint_path': f'{tmpdir}/unified_state.json',
            'dev_mode': True
        }
        authority = StateAuthority(state, config)
        print("   ✅ StateAuthority initialized")
        print()
        
        # Register writers
        print("2️⃣  Registering writers with different priorities...")
        authority.register_writer(
            'risk_controller',
            ['risk_state'],
            WritePriority.LIVE_RISK
        )
        authority.register_writer(
            'portfolio_manager',
            ['portfolio_state'],
            WritePriority.LIVE_TRADING
        )
        authority.register_writer(
            'options_bridge',
            ['portfolio_state', 'risk_state'],
            WritePriority.BRIDGE_SYNC
        )
        print("   ✅ Registered 3 writers")
        print()
        
        # Apply updates
        print("3️⃣  Applying state updates...")
        
        # Risk controller update (high priority)
        update1 = StateUpdate(
            writer_id='risk_controller',
            section='risk_state',
            field_path='system_stress',
            new_value=0.35,
            priority=WritePriority.LIVE_RISK,
            source='LIVE',
            reason='Market volatility increased'
        )
        success1 = authority.update(update1)
        print(f"   {'✅' if success1 else '❌'} Risk controller: system_stress = 0.35")
        
        # Portfolio manager update
        update2 = StateUpdate(
            writer_id='portfolio_manager',
            section='portfolio_state',
            field_path='total_positions',
            new_value=25,
            priority=WritePriority.LIVE_TRADING,
            source='LIVE',
            reason='New positions opened'
        )
        success2 = authority.update(update2)
        print(f"   {'✅' if success2 else '❌'} Portfolio manager: total_positions = 25")
        
        # Options bridge update (lower priority)
        update3 = StateUpdate(
            writer_id='options_bridge',
            section='portfolio_state',
            field_path='options_net_delta',
            new_value=150.5,
            priority=WritePriority.BRIDGE_SYNC,
            source='BRIDGE',
            reason='Options position sync'
        )
        success3 = authority.update(update3)
        print(f"   {'✅' if success3 else '❌'} Options bridge: options_net_delta = 150.5")
        print()
        
        # Batch update
        print("4️⃣  Applying batch update (atomic)...")
        batch_updates = [
            StateUpdate(
                writer_id='portfolio_manager',
                section='portfolio_state',
                field_path='total_exposure',
                new_value=0.65,
                priority=WritePriority.LIVE_TRADING,
                source='LIVE',
                reason='Batch update'
            ),
            StateUpdate(
                writer_id='portfolio_manager',
                section='portfolio_state',
                field_path='cash',
                new_value=350000.0,
                priority=WritePriority.LIVE_TRADING,
                source='LIVE',
                reason='Batch update'
            ),
        ]
        applied = authority.batch_update(batch_updates)
        print(f"   ✅ Applied {applied}/{len(batch_updates)} updates atomically")
        print()
        
        # Verify state
        print("5️⃣  Verifying state changes...")
        print(f"   Risk state:")
        print(f"     • system_stress: {state.risk.system_stress}")
        print(f"   Portfolio state:")
        print(f"     • total_positions: {state.portfolio.total_positions}")
        print(f"     • total_exposure: {state.portfolio.total_exposure}")
        print(f"     • cash: {state.portfolio.cash}")
        print(f"     • options_net_delta: {state.portfolio.options_net_delta}")
        print()
        
        # Check state history
        print("6️⃣  Checking state change log...")
        history = authority.get_state_history(
            'portfolio_state',
            datetime.utcnow()
        )
        print(f"   ✅ Found {len(history)} portfolio state changes")
        if history:
            latest = history[-1]
            print(f"   Latest: {latest['writer_id']} → {latest['field_path']} = {latest['new_value']}")
        print()
        
        # Checkpoint
        print("7️⃣  Creating checkpoint...")
        authority.checkpoint(force=True)
        checkpoint_path = Path(config['checkpoint_path'])
        if checkpoint_path.exists():
            print(f"   ✅ Checkpoint written to {checkpoint_path}")
            print(f"   Size: {checkpoint_path.stat().st_size} bytes")
        print()


def demo_priority_conflict():
    """Demonstrate priority-based conflict resolution."""
    print("=" * 80)
    print("GAP 7 DEMO: Priority-Based Conflict Resolution")
    print("=" * 80)
    print()
    
    state = UnifiedState()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            'state_change_log_path': f'{tmpdir}/state_change_log.jsonl',
            'checkpoint_path': f'{tmpdir}/unified_state.json',
            'dev_mode': True
        }
        authority = StateAuthority(state, config)
        
        # Register writers with different priorities
        print("1️⃣  Registering writers with different priorities...")
        authority.register_writer(
            'emergency_system',
            ['risk_state'],
            WritePriority.EMERGENCY
        )
        authority.register_writer(
            'risk_controller',
            ['risk_state'],
            WritePriority.LIVE_RISK
        )
        authority.register_writer(
            'research_system',
            ['risk_state'],
            WritePriority.RESEARCH
        )
        print("   ✅ Registered 3 writers with EMERGENCY, LIVE_RISK, RESEARCH priorities")
        print()
        
        # Emergency update (highest priority)
        print("2️⃣  Emergency system sets emergency_active = True...")
        emergency_update = StateUpdate(
            writer_id='emergency_system',
            section='risk_state',
            field_path='emergency_active',
            new_value=True,
            priority=WritePriority.EMERGENCY,
            source='LIVE',
            reason='Circuit breaker triggered'
        )
        success = authority.update(emergency_update)
        print(f"   {'✅' if success else '❌'} Emergency update applied")
        print(f"   Current value: emergency_active = {state.risk.emergency_active}")
        print()
        
        # Risk controller update (lower priority)
        print("3️⃣  Risk controller tries to update same field...")
        risk_update = StateUpdate(
            writer_id='risk_controller',
            section='risk_state',
            field_path='emergency_active',
            new_value=False,
            priority=WritePriority.LIVE_RISK,
            source='LIVE',
            reason='Risk assessment complete'
        )
        success = authority.update(risk_update)
        print(f"   {'✅' if success else '❌'} Risk controller update applied")
        print(f"   Current value: emergency_active = {state.risk.emergency_active}")
        print()
        
        print("💡 Note: In production, lower-priority writes would be queued")
        print("   when a higher-priority writer holds the lock.")
        print()


def demo_emergency_priority():
    """Demonstrate emergency priority requiring reason."""
    print("=" * 80)
    print("GAP 7 DEMO: Emergency Priority Validation")
    print("=" * 80)
    print()
    
    state = UnifiedState()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            'state_change_log_path': f'{tmpdir}/state_change_log.jsonl',
            'checkpoint_path': f'{tmpdir}/unified_state.json',
            'dev_mode': True
        }
        authority = StateAuthority(state, config)
        
        authority.register_writer(
            'emergency_system',
            ['risk_state'],
            WritePriority.EMERGENCY
        )
        
        # Try emergency update without reason
        print("1️⃣  Attempting emergency update WITHOUT reason...")
        update_no_reason = StateUpdate(
            writer_id='emergency_system',
            section='risk_state',
            field_path='emergency_active',
            new_value=True,
            priority=WritePriority.EMERGENCY,
            source='LIVE',
            reason=None  # Missing reason
        )
        success = authority.update(update_no_reason)
        print(f"   {'✅' if success else '❌'} Update {'succeeded' if success else 'rejected'}")
        print()
        
        # Try with reason
        print("2️⃣  Attempting emergency update WITH reason...")
        update_with_reason = StateUpdate(
            writer_id='emergency_system',
            section='risk_state',
            field_path='emergency_active',
            new_value=True,
            priority=WritePriority.EMERGENCY,
            source='LIVE',
            reason='Market crash: NIFTY down 5% in 10 minutes'
        )
        success = authority.update(update_with_reason)
        print(f"   {'✅' if success else '❌'} Update {'succeeded' if success else 'rejected'}")
        print(f"   Current value: emergency_active = {state.risk.emergency_active}")
        print()
        
        print("💡 Emergency priority updates MUST include a reason for audit trail.")
        print()


def main():
    """Run all demos."""
    print()
    print("🧠 GAP 7: STATE MANAGEMENT CONSOLIDATION - DEMO")
    print()
    
    try:
        demo_state_authority()
        demo_priority_conflict()
        demo_emergency_priority()
        
        print("=" * 80)
        print("✅ GAP 7 DEMO COMPLETE")
        print("=" * 80)
        print()
        print("Key Takeaways:")
        print("  • StateAuthority provides single write interface for UnifiedState")
        print("  • Priority-based conflict resolution (EMERGENCY > LIVE_RISK > LIVE_TRADING > BRIDGE_SYNC > RESEARCH)")
        print("  • All state changes are logged for audit trail")
        print("  • Batch updates are atomic")
        print("  • Emergency updates require explicit reason")
        print("  • Checkpoints are written after critical section updates")
        print()
        print("Next: See examples/gap7_bridges_demo.py for bridge synchronization demo")
        print()
        
        return 0
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
