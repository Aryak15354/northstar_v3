"""
Tests for StateAuthority - the single write interface for UnifiedState.
"""

import pytest
import tempfile
import json
from datetime import datetime
from pathlib import Path

from src.core.state import UnifiedState
from src.core.state_authority import StateAuthority, StateUpdate, WritePriority


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def unified_state():
    """Create a fresh UnifiedState instance."""
    return UnifiedState()


@pytest.fixture
def state_authority(unified_state, temp_dir):
    """Create a StateAuthority instance with temp paths."""
    unified_state.state_file = str(temp_dir / 'unified_state_default.json')
    unified_state.state_parquet = str(temp_dir / 'unified_state_default.parquet')
    unified_state.state_history_file = str(temp_dir / 'unified_state_history.parquet')
    unified_state.events_file = str(temp_dir / 'state_events.json')
    config = {
        'state_change_log_path': str(temp_dir / 'state_change_log.jsonl'),
        'checkpoint_path': str(temp_dir / 'unified_state.json'),
        'dev_mode': True
    }
    return StateAuthority(unified_state, config)


def test_registered_writer_can_update(state_authority):
    """Test that a registered writer can successfully update state."""
    # Register a writer
    state_authority.register_writer(
        'test_writer',
        ['portfolio_state'],
        WritePriority.LIVE_TRADING
    )
    
    # Create an update
    update = StateUpdate(
        writer_id='test_writer',
        section='portfolio_state',
        field_path='total_positions',
        new_value=10,
        priority=WritePriority.LIVE_TRADING,
        source='LIVE',
        reason='Test update'
    )
    
    # Apply the update
    success = state_authority.update(update)
    
    assert success is True
    assert state_authority.state.portfolio.total_positions == 10


def test_unregistered_writer_emits_warning(state_authority):
    """Test that an unregistered writer emits a warning but still applies update."""
    update = StateUpdate(
        writer_id='unregistered_writer',
        section='portfolio_state',
        field_path='total_positions',
        new_value=5,
        priority=WritePriority.LIVE_TRADING,
        source='LIVE',
        reason='Test update'
    )
    
    # Should emit warning but still apply in dev mode
    with pytest.warns(DeprecationWarning):
        success = state_authority.update(update)
    
    assert success is True
    assert state_authority.state.portfolio.total_positions == 5


def test_wrong_section_rejected(state_authority):
    """Test that writing to a disallowed section is rejected."""
    # Register writer for portfolio_state only
    state_authority.register_writer(
        'portfolio_writer',
        ['portfolio_state'],
        WritePriority.LIVE_TRADING
    )
    
    # Try to write to risk_state
    update = StateUpdate(
        writer_id='portfolio_writer',
        section='risk_state',
        field_path='system_stress',
        new_value=0.5,
        priority=WritePriority.LIVE_TRADING,
        source='LIVE',
        reason='Test update'
    )
    
    success = state_authority.update(update)
    
    assert success is False


def test_batch_update_atomic(state_authority):
    """Test that batch updates are applied atomically."""
    state_authority.register_writer(
        'batch_writer',
        ['portfolio_state'],
        WritePriority.LIVE_TRADING
    )
    
    updates = [
        StateUpdate(
            writer_id='batch_writer',
            section='portfolio_state',
            field_path='total_positions',
            new_value=10,
            priority=WritePriority.LIVE_TRADING,
            source='LIVE',
            reason='Batch test'
        ),
        StateUpdate(
            writer_id='batch_writer',
            section='portfolio_state',
            field_path='total_exposure',
            new_value=0.75,
            priority=WritePriority.LIVE_TRADING,
            source='LIVE',
            reason='Batch test'
        ),
    ]
    
    applied = state_authority.batch_update(updates)
    
    assert applied == 2
    assert state_authority.state.portfolio.total_positions == 10
    assert state_authority.state.portfolio.total_exposure == 0.75


def test_checkpoint_written_after_critical_section(state_authority, temp_dir):
    """Test that checkpoint is written after updating a critical section."""
    state_authority.register_writer(
        'critical_writer',
        ['portfolio_state'],
        WritePriority.LIVE_TRADING
    )
    
    update = StateUpdate(
        writer_id='critical_writer',
        section='portfolio_state',
        field_path='total_value',
        new_value=1000000.0,
        priority=WritePriority.LIVE_TRADING,
        source='LIVE',
        reason='Critical update'
    )
    
    state_authority.update(update)
    
    # Check that checkpoint file was created
    checkpoint_path = temp_dir / 'unified_state.json'
    assert checkpoint_path.exists()
    
    # Verify content
    with open(checkpoint_path, 'r') as f:
        checkpoint_data = json.load(f)

    assert 'timestamp' in checkpoint_data
    history_path = temp_dir / 'unified_state_history.parquet'
    assert history_path.exists()


def test_state_change_log_append_only(state_authority, temp_dir):
    """Test that state change log is append-only."""
    state_authority.register_writer(
        'log_writer',
        ['portfolio_state'],
        WritePriority.LIVE_TRADING
    )
    
    # Apply multiple updates
    for i in range(5):
        update = StateUpdate(
            writer_id='log_writer',
            section='portfolio_state',
            field_path='total_positions',
            new_value=i,
            priority=WritePriority.LIVE_TRADING,
            source='LIVE',
            reason=f'Update {i}'
        )
        state_authority.update(update)
    
    # Read log
    log_path = temp_dir / 'state_change_log.jsonl'
    assert log_path.exists()
    
    entries = []
    with open(log_path, 'r') as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))
    
    assert len(entries) == 5
    
    # Verify chronological order
    timestamps = [datetime.fromisoformat(e['timestamp']) for e in entries]
    assert timestamps == sorted(timestamps)


def test_get_state_history(state_authority):
    """Test retrieving state history for a section."""
    state_authority.register_writer(
        'history_writer',
        ['portfolio_state'],
        WritePriority.LIVE_TRADING
    )
    
    # Apply some updates
    for i in range(3):
        update = StateUpdate(
            writer_id='history_writer',
            section='portfolio_state',
            field_path='total_positions',
            new_value=i * 10,
            priority=WritePriority.LIVE_TRADING,
            source='LIVE',
            reason=f'History test {i}'
        )
        state_authority.update(update)
    
    # Get history
    since = datetime.utcnow()
    history = state_authority.get_state_history('portfolio_state', since)
    
    assert len(history) >= 3


def test_emergency_priority_requires_reason(state_authority):
    """Test that EMERGENCY priority updates require a reason."""
    state_authority.register_writer(
        'emergency_writer',
        ['risk_state'],
        WritePriority.EMERGENCY
    )
    
    # Try without reason
    update = StateUpdate(
        writer_id='emergency_writer',
        section='risk_state',
        field_path='emergency_active',
        new_value=True,
        priority=WritePriority.EMERGENCY,
        source='LIVE',
        reason=None  # Missing reason
    )
    
    success = state_authority.update(update)
    assert success is False
    
    # Try with reason
    update.reason = 'Market crash detected'
    success = state_authority.update(update)
    assert success is True


def test_get_current_writer(state_authority):
    """Test getting the current writer holding a section lock."""
    state_authority.register_writer(
        'writer_a',
        ['portfolio_state'],
        WritePriority.LIVE_TRADING
    )
    
    # Initially no writer
    current = state_authority.get_current_writer('portfolio_state')
    assert current is None
    
    # After update, writer should be cleared (lock released)
    update = StateUpdate(
        writer_id='writer_a',
        section='portfolio_state',
        field_path='total_positions',
        new_value=5,
        priority=WritePriority.LIVE_TRADING,
        source='LIVE',
        reason='Test'
    )
    state_authority.update(update)
    
    # Lock should be released after update
    current = state_authority.get_current_writer('portfolio_state')
    assert current is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
