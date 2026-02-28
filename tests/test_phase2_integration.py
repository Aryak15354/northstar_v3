#!/usr/bin/env python3
"""
Phase 2 Integration Test - Core Infrastructure Checkpoint

This test verifies that all Phase 2 components work together:
- IV Surface modeling
- Portfolio Greeks Aggregator
- Configuration Management
- State Persistence

Validates: Task 13 - Core infrastructure complete
"""

import pytest
import numpy as np
import tempfile
from datetime import datetime, timedelta

from src.volatility.iv_surface import IVSurface
from src.volatility.greeks_aggregator import GreeksAggregator, Position
from src.volatility.config import ConfigurationManager
from src.volatility.state_engine import (
    VolatilityStateEngine,
    RegimeState,
    PortfolioGreeks
)


def test_phase2_integration():
    """
    Integration test for Phase 2 core infrastructure
    
    Tests the complete flow:
    1. Verify IV surface can be created
    2. Compute Greeks for portfolio
    3. Update state engine with Greeks
    4. Persist and restore state
    5. Verify configuration management
    """
    
    # 1. Verify IV surface can be created
    print("\n📊 Testing IV Surface...")
    surface = IVSurface(underlying='SPY', spot_price=100.0, risk_free_rate=0.05)
    assert surface.underlying == 'SPY'
    assert surface.spot_price == 100.0
    print(f"✅ IV Surface created")
    
    # 2. Compute Greeks for portfolio
    print("\n📈 Testing Greeks Aggregator...")
    aggregator = GreeksAggregator()
    
    # Create sample portfolio
    positions = [
        Position(
            position_id='CALL_1',
            underlying='SPY',
            option_type='call',
            strike=100.0,
            expiry=datetime.now().date() + timedelta(days=30),
            quantity=10,
            spot_price=100.0,
            implied_vol=0.18,
            risk_free_rate=0.05
        ),
        Position(
            position_id='PUT_1',
            underlying='SPY',
            option_type='put',
            strike=95.0,
            expiry=datetime.now().date() + timedelta(days=30),
            quantity=-5,
            spot_price=100.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        ),
    ]
    
    portfolio_greeks = aggregator.compute_portfolio_greeks(positions)
    
    # Verify Greeks are computed
    assert portfolio_greeks.delta != 0, "Portfolio should have delta"
    assert portfolio_greeks.gamma > 0, "Portfolio should have positive gamma"
    assert portfolio_greeks.vega > 0, "Portfolio should have positive vega"
    print(f"✅ Portfolio Greeks computed (delta: {portfolio_greeks.delta:.2f}, gamma: {portfolio_greeks.gamma:.2f})")
    
    # 3. Update state engine with Greeks
    print("\n🧠 Testing State Engine...")
    with tempfile.TemporaryDirectory() as temp_dir:
        engine = VolatilityStateEngine(persistence_dir=temp_dir)
        
        # Update portfolio Greeks
        success = engine.update_portfolio_greeks(portfolio_greeks)
        assert success, "Portfolio Greeks update should succeed"
        
        # Update regime
        regime = RegimeState(
            regime='low_vol',
            confidence=0.85,
            duration=timedelta(days=5),
            regime_probabilities={'low_vol': 0.85, 'high_vol': 0.10, 'crisis': 0.05}
        )
        success = engine.update_regime(regime)
        assert success, "Regime update should succeed"
        
        # Update volatility metrics
        success = engine.update_volatility_metrics(
            vix_level=18.5,
            realized_vol_20d=0.15,
            realized_vol_60d=0.18,
            vol_of_vol=1.2
        )
        assert success, "Volatility metrics update should succeed"
        
        print(f"✅ State engine updated (version: {engine.current_state.version})")
        
        # 4. Persist and restore state
        print("\n💾 Testing State Persistence...")
        success = engine.persist_state()
        assert success, "State persistence should succeed"
        
        # Modify state
        new_regime = RegimeState(
            regime='high_vol',
            confidence=0.90,
            duration=timedelta(days=1),
            regime_probabilities={'low_vol': 0.05, 'high_vol': 0.90, 'crisis': 0.05}
        )
        engine.update_regime(new_regime)
        
        # Restore original state
        success = engine.restore_state()
        assert success, "State restoration should succeed"
        
        # Verify restored state
        restored_state = engine.get_state()
        assert restored_state.regime.regime == 'low_vol', "Should restore low_vol regime"
        assert restored_state.vix_level == 18.5, "Should restore VIX level"
        print(f"✅ State persisted and restored successfully")
    
    # 5. Verify configuration management
    print("\n⚙️  Testing Configuration Management...")
    config_manager = ConfigurationManager()
    config = config_manager.config
    
    # Verify config has all required sections
    assert config.risk is not None, "Config should have risk section"
    assert config.volatility is not None, "Config should have volatility section"
    
    # Test parameter update
    success = config_manager.update_parameter('risk.max_position_size', 200000)
    assert success, "Parameter update should succeed"
    assert config_manager.config.risk.max_position_size == 200000
    
    print(f"✅ Configuration management working")
    
    print("\n✅ Phase 2 Integration Test PASSED - Core infrastructure complete!")


def test_greeks_computation_performance():
    """Test that Greeks computation meets <50ms target"""
    import time
    
    aggregator = GreeksAggregator()
    
    # Create portfolio with 20 positions
    positions = []
    for i in range(20):
        positions.append(Position(
            position_id=f'POS_{i}',
            underlying='SPY',
            option_type='call' if i % 2 == 0 else 'put',
            strike=95.0 + i * 2,
            expiry=datetime.now().date() + timedelta(days=30),
            quantity=10,
            spot_price=100.0,
            implied_vol=0.20,
            risk_free_rate=0.05
        ))
    
    # Measure computation time
    start = time.time()
    portfolio_greeks = aggregator.compute_portfolio_greeks(positions)
    elapsed = (time.time() - start) * 1000  # Convert to ms
    
    print(f"\n⏱️  Greeks computation time: {elapsed:.2f}ms for {len(positions)} positions")
    assert elapsed < 50, f"Greeks computation should be <50ms, got {elapsed:.2f}ms"
    print(f"✅ Performance target met (<50ms)")


def test_state_update_propagation_performance():
    """Test that state update propagation meets <100ms target"""
    import time
    
    with tempfile.TemporaryDirectory() as temp_dir:
        engine = VolatilityStateEngine(persistence_dir=temp_dir)
        
        # Measure state update time
        regime = RegimeState(
            regime='low_vol',
            confidence=0.85,
            duration=timedelta(days=5)
        )
        
        start = time.time()
        success = engine.update_regime(regime)
        elapsed = (time.time() - start) * 1000  # Convert to ms
        
        assert success, "State update should succeed"
        print(f"\n⏱️  State update propagation time: {elapsed:.2f}ms")
        assert elapsed < 100, f"State update should be <100ms, got {elapsed:.2f}ms"
        print(f"✅ Performance target met (<100ms)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
