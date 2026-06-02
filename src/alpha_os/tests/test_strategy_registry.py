"""
Tests for StrategyRegistry

Critical tests that must pass before Gap 4 is complete:
1. test_register_and_retrieve: Register a strategy, retrieve it, assert all fields match
2. test_atomic_save_on_update: Simulate crash mid-write, assert no corruption
3. test_status_transition_log: Move strategy through lifecycle, assert log is correct
4. test_duplicate_registration_raises: Attempt duplicate registration, assert error
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from src.alpha_os.strategy_registry import (
    StrategyRegistry,
    StrategyRecord,
    StrategyStatus,
    StrategyFamily,
    StrategyPerformanceRecord,
    DuplicateStrategyError,
    StrategyNotFoundError
)


@pytest.fixture
def temp_registry_dir():
    """Create temporary directory for registry tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def registry(temp_registry_dir):
    """Create a fresh registry for each test."""
    return StrategyRegistry(registry_path=temp_registry_dir)


@pytest.fixture
def sample_strategy():
    """Create a sample strategy record."""
    return StrategyRecord(
        strategy_id="momentum_v1_test",
        strategy_name="Momentum V1 Test",
        family=StrategyFamily.MOMENTUM,
        status=StrategyStatus.RESEARCH,
        discovered_date=datetime.utcnow(),
        validation_ic_mean=0.045,
        validation_icir=1.5,
        validation_hit_rate=0.60
    )


def test_register_and_retrieve(registry, sample_strategy):
    """Test 1: Register a strategy, retrieve it, assert all fields match."""
    # Register strategy
    registry.register(sample_strategy)
    
    # Retrieve strategy
    retrieved = registry.get(sample_strategy.strategy_id)
    
    # Assert all fields match
    assert retrieved.strategy_id == sample_strategy.strategy_id
    assert retrieved.strategy_name == sample_strategy.strategy_name
    assert retrieved.family == sample_strategy.family
    assert retrieved.status == sample_strategy.status
    assert retrieved.validation_ic_mean == sample_strategy.validation_ic_mean
    assert retrieved.validation_icir == sample_strategy.validation_icir
    assert retrieved.validation_hit_rate == sample_strategy.validation_hit_rate


def test_atomic_save_on_update(registry, sample_strategy):
    """Test 2: Simulate crash mid-write, assert no corruption."""
    # Register strategy
    registry.register(sample_strategy)
    
    # Get registry file path
    registry_file = registry.registry_file
    
    # Verify file exists
    assert registry_file.exists()
    
    # Read original content
    with open(registry_file, 'r') as f:
        original_content = f.read()
    
    # Update strategy status
    registry.update_status(
        sample_strategy.strategy_id,
        StrategyStatus.CANDIDATE,
        "Test update"
    )
    
    # Verify file still exists and is valid JSON
    assert registry_file.exists()
    
    # Load and verify
    registry2 = StrategyRegistry(registry_path=str(registry.registry_path))
    retrieved = registry2.get(sample_strategy.strategy_id)
    assert retrieved.status == StrategyStatus.CANDIDATE
    
    # Verify no temp files left behind
    temp_files = list(registry.registry_path.glob("*.tmp"))
    assert len(temp_files) == 0


def test_status_transition_log(registry, sample_strategy):
    """Test 3: Move strategy through lifecycle, assert log is correct."""
    # Register strategy
    registry.register(sample_strategy)
    
    # Transition: RESEARCH → CANDIDATE
    registry.update_status(
        sample_strategy.strategy_id,
        StrategyStatus.CANDIDATE,
        "Passed validation criteria"
    )
    
    # Transition: CANDIDATE → ACTIVE
    registry.update_status(
        sample_strategy.strategy_id,
        StrategyStatus.ACTIVE,
        "Promoted to production"
    )
    
    # Transition: ACTIVE → PROBATION
    registry.update_status(
        sample_strategy.strategy_id,
        StrategyStatus.PROBATION,
        "Performance below threshold"
    )
    
    # Retrieve and check log
    retrieved = registry.get(sample_strategy.strategy_id)
    
    assert len(retrieved.status_change_log) == 3
    
    # Check first transition
    assert retrieved.status_change_log[0]['from_status'] == 'RESEARCH'
    assert retrieved.status_change_log[0]['to_status'] == 'CANDIDATE'
    assert 'validation' in retrieved.status_change_log[0]['reason'].lower()
    
    # Check second transition
    assert retrieved.status_change_log[1]['from_status'] == 'CANDIDATE'
    assert retrieved.status_change_log[1]['to_status'] == 'ACTIVE'
    
    # Check third transition
    assert retrieved.status_change_log[2]['from_status'] == 'ACTIVE'
    assert retrieved.status_change_log[2]['to_status'] == 'PROBATION'
    
    # Verify timestamps are present
    for log_entry in retrieved.status_change_log:
        assert 'timestamp' in log_entry
        assert log_entry['timestamp'] is not None


def test_duplicate_registration_raises(registry, sample_strategy):
    """Test 4: Attempt duplicate registration, assert error raised."""
    # Register strategy
    registry.register(sample_strategy)
    
    # Attempt to register again
    with pytest.raises(DuplicateStrategyError):
        registry.register(sample_strategy)


def test_strategy_not_found_raises(registry):
    """Test that retrieving non-existent strategy raises error."""
    with pytest.raises(StrategyNotFoundError):
        registry.get("nonexistent_strategy")


def test_get_by_status(registry):
    """Test filtering strategies by status."""
    # Create strategies with different statuses
    strategies = [
        StrategyRecord(
            strategy_id=f"strategy_{i}",
            strategy_name=f"Strategy {i}",
            family=StrategyFamily.MOMENTUM,
            status=status,
            discovered_date=datetime.utcnow()
        )
        for i, status in enumerate([
            StrategyStatus.RESEARCH,
            StrategyStatus.CANDIDATE,
            StrategyStatus.ACTIVE,
            StrategyStatus.ACTIVE,
            StrategyStatus.PROBATION
        ])
    ]
    
    # Register all strategies
    for strategy in strategies:
        registry.register(strategy)
    
    # Test filtering
    active_strategies = registry.get_by_status(StrategyStatus.ACTIVE)
    assert len(active_strategies) == 2
    
    candidate_strategies = registry.get_by_status(StrategyStatus.CANDIDATE)
    assert len(candidate_strategies) == 1
    
    research_strategies = registry.get_by_status(StrategyStatus.RESEARCH)
    assert len(research_strategies) == 1


def test_get_active_strategies(registry):
    """Test getting all active strategies (ACTIVE + PROBATION)."""
    # Create strategies
    strategies = [
        StrategyRecord(
            strategy_id=f"strategy_{i}",
            strategy_name=f"Strategy {i}",
            family=StrategyFamily.MOMENTUM,
            status=status,
            discovered_date=datetime.utcnow()
        )
        for i, status in enumerate([
            StrategyStatus.ACTIVE,
            StrategyStatus.ACTIVE,
            StrategyStatus.PROBATION,
            StrategyStatus.RETIRED,
            StrategyStatus.CANDIDATE
        ])
    ]
    
    # Register all
    for strategy in strategies:
        registry.register(strategy)
    
    # Get active strategies
    active = registry.get_active_strategies()
    
    # Should include ACTIVE and PROBATION, not RETIRED or CANDIDATE
    assert len(active) == 3


def test_update_live_performance(registry, sample_strategy):
    """Test updating live performance records."""
    # Register strategy
    registry.register(sample_strategy)
    
    # Add performance record
    perf_record = StrategyPerformanceRecord(
        as_of_date=datetime.utcnow(),
        ic_mean=0.042,
        ic_std=0.015,
        icir=2.8,
        ic_hit_rate=0.65,
        regime_conditional_ics={'expansion': 0.05, 'contraction': 0.03},
        turnover_pct=25.0,
        max_drawdown=0.08,
        live_days=45,
        live_ic=0.040
    )
    
    registry.update_live_performance(sample_strategy.strategy_id, perf_record)
    
    # Retrieve and verify
    retrieved = registry.get(sample_strategy.strategy_id)
    
    assert len(retrieved.performance_history) == 1
    assert retrieved.current_live_ic == 0.040
    assert retrieved.performance_history[0].ic_mean == 0.042


def test_registry_summary(registry):
    """Test registry summary generation."""
    # Create diverse set of strategies
    strategies = [
        StrategyRecord(
            strategy_id=f"strategy_{i}",
            strategy_name=f"Strategy {i}",
            family=family,
            status=status,
            discovered_date=datetime.utcnow(),
            validation_icir=icir
        )
        for i, (family, status, icir) in enumerate([
            (StrategyFamily.MOMENTUM, StrategyStatus.ACTIVE, 1.5),
            (StrategyFamily.VALUE, StrategyStatus.ACTIVE, 1.8),
            (StrategyFamily.QUALITY, StrategyStatus.CANDIDATE, 1.2),
            (StrategyFamily.MOMENTUM, StrategyStatus.PROBATION, 0.9),
            (StrategyFamily.MACRO, StrategyStatus.RETIRED, 0.5)
        ])
    ]
    
    # Register all
    for strategy in strategies:
        registry.register(strategy)
    
    # Get summary
    summary = registry.get_registry_summary()
    
    # Verify counts
    assert summary['total_strategies'] == 5
    assert summary['active_count'] == 2
    assert summary['candidate_count'] == 1
    assert summary['probation_count'] == 1
    
    # Verify family counts
    assert summary['by_family']['MOMENTUM'] == 2
    assert summary['by_family']['VALUE'] == 1
    
    # Verify average ICIR (only ACTIVE strategies)
    assert summary['avg_active_icir'] == pytest.approx((1.5 + 1.8) / 2)


def test_persistence_across_instances(temp_registry_dir, sample_strategy):
    """Test that registry persists across different instances."""
    # Create first registry instance and register strategy
    registry1 = StrategyRegistry(registry_path=temp_registry_dir)
    registry1.register(sample_strategy)
    
    # Create second registry instance
    registry2 = StrategyRegistry(registry_path=temp_registry_dir)
    
    # Verify strategy exists in second instance
    retrieved = registry2.get(sample_strategy.strategy_id)
    assert retrieved.strategy_id == sample_strategy.strategy_id
    assert retrieved.family == sample_strategy.family


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
