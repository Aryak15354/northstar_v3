"""
Integration tests for UnifiedVolatilityEngine

Tests complete flow:
- Market data → strategy → execution
- Regime change propagation
- Emergency action triggering

**Validates: Requirements 1.1, 1.2, 1.3, 11.6, 13.5**
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import numpy as np

from src.volatility.unified_engine import (
    UnifiedVolatilityEngine,
    EventType,
    SystemEvent,
    ComponentError,
    TradingCycleResult
)
from src.volatility.state_engine import VolatilityState
from src.volatility.strategy_generator import TargetGreeks
from src.volatility.greeks_aggregator import PortfolioGreeks


@pytest.fixture
def mock_components():
    """Create mock components for testing"""
    return {
        "state_engine": Mock(),
        "strategy_generator": Mock(),
        "greeks_aggregator": Mock(),
        "risk_authority": Mock(),
        "dispersion_module": Mock(),
        "gamma_scalper": Mock(),
        "capital_allocator": Mock(),
        "monte_carlo_engine": Mock(),
        "regime_detector": Mock(),
        "execution_interface": Mock(),
        "performance_monitor": Mock()
    }


@pytest.fixture
def unified_engine(mock_components):
    """Create UnifiedVolatilityEngine with mocked components"""
    return UnifiedVolatilityEngine(**mock_components)


@pytest.fixture
def sample_market_data():
    """Sample market data for testing"""
    return {
        "option_chain": {"SPY": []},
        "spot_prices": {"SPY": 450.0},
        "returns": np.random.randn(100, 5) * 0.01
    }


@pytest.fixture
def sample_state():
    """Sample volatility state"""
    return Mock(
        regime="low_vol",
        vix_level=15.0,
        timestamp=datetime.now(),
        validation_status="valid"
    )


class TestCompleteFlow:
    """Test market data → strategy → execution complete flow"""
    
    def test_successful_trading_cycle(self, unified_engine, mock_components, sample_market_data, sample_state):
        """Test complete trading cycle executes successfully"""
        # Setup mocks
        mock_components["state_engine"].get_state.return_value = sample_state
        mock_components["regime_detector"].detect_regime.return_value = "low_vol"
        
        # Mock strategy generation from all sources
        mock_components["strategy_generator"].generate.return_value = [Mock(type="test_strategy")]
        mock_components["dispersion_module"].analyze_dispersion_opportunity.return_value = Mock(type="dispersion")
        mock_components["gamma_scalper"].identify_opportunities.return_value = [Mock(type="gamma_scalp")]
        
        mock_components["risk_authority"].validate_trade.return_value = Mock(approved=True)
        mock_components["capital_allocator"].allocate_capital.return_value = {"test_strategy": 10000.0}
        mock_components["execution_interface"].submit_order.return_value = Mock(success=True)
        
        portfolio_greeks = Mock(delta=0.0, gamma=10.0, vega=50.0, theta=-5.0)
        mock_components["greeks_aggregator"].compute_portfolio_greeks.return_value = portfolio_greeks
        
        # Mock target Greeks for feedback loop
        target_greeks = Mock(delta=0.0, gamma=10.0, vega=50.0, theta=-5.0)
        mock_components["risk_authority"].get_target_greeks.return_value = target_greeks
        
        # Mock feedback loop methods
        mock_components["capital_allocator"].update_performance_history = Mock()
        mock_components["strategy_generator"].update_from_feedback = Mock()
        
        performance = {"sharpe_ratio": 1.5, "total_pnl": 1000.0}
        mock_components["performance_monitor"].update_performance.return_value = performance
        
        # Execute trading cycle with target Greeks to trigger strategy generation
        target = TargetGreeks(
            delta=0.0, gamma=10.0, vega=50.0, theta=-5.0,
            delta_tolerance=0.1, gamma_tolerance=0.1, vega_tolerance=0.1, theta_tolerance=0.1
        )
        result = unified_engine.run_trading_cycle(sample_market_data, target)
        
        # Verify flow executed
        assert isinstance(result, TradingCycleResult)
        assert result.state == sample_state
        assert len(result.strategies_generated) > 0
        assert len(result.errors) == 0
        
        # Verify components were called in correct order
        mock_components["state_engine"].get_state.assert_called()
        mock_components["regime_detector"].detect_regime.assert_called_once()
        mock_components["strategy_generator"].generate.assert_called()
        mock_components["risk_authority"].validate_trade.assert_called()
        mock_components["capital_allocator"].allocate_capital.assert_called()
        mock_components["greeks_aggregator"].compute_portfolio_greeks.assert_called()
        mock_components["performance_monitor"].update_performance.assert_called()
    
    def test_trading_cycle_with_target_greeks(self, unified_engine, mock_components, sample_market_data, sample_state):
        """Test trading cycle with specific target Greeks"""
        # Setup
        mock_components["state_engine"].get_state.return_value = sample_state
        mock_components["regime_detector"].detect_regime.return_value = "low_vol"
        mock_components["strategy_generator"].generate.return_value = []
        mock_components["dispersion_module"].analyze_dispersion_opportunity.return_value = None
        mock_components["gamma_scalper"].identify_opportunities.return_value = []
        mock_components["greeks_aggregator"].compute_portfolio_greeks.return_value = Mock()
        mock_components["performance_monitor"].update_performance.return_value = {}
        
        target_greeks = TargetGreeks(
            delta=0.0,
            gamma=20.0,
            vega=100.0,
            theta=-10.0,
            delta_tolerance=0.1,
            gamma_tolerance=0.1,
            vega_tolerance=0.1,
            theta_tolerance=0.1
        )
        
        # Execute
        result = unified_engine.run_trading_cycle(sample_market_data, target_greeks)
        
        # Verify target Greeks passed to strategy generator
        mock_components["strategy_generator"].generate.assert_called()
        call_args = mock_components["strategy_generator"].generate.call_args
        assert call_args[1]["target_greeks"] == target_greeks
    
    def test_trading_cycle_handles_component_failure(self, unified_engine, mock_components, sample_market_data):
        """Test trading cycle handles component failures gracefully"""
        # Setup - state engine fails
        mock_components["state_engine"].get_state.side_effect = Exception("State engine failure")
        
        # Execute
        result = unified_engine.run_trading_cycle(sample_market_data)
        
        # Verify error captured
        assert len(result.errors) > 0
        assert "volatility state" in result.errors[0].lower()  # Error message mentions state
        assert result.state is None
    
    def test_strategy_rejection_by_risk_authority(self, unified_engine, mock_components, sample_market_data, sample_state):
        """Test strategies rejected by risk authority are not executed"""
        # Setup
        mock_components["state_engine"].get_state.return_value = sample_state
        mock_components["regime_detector"].detect_regime.return_value = "low_vol"
        
        # Generate one strategy that will be rejected
        mock_components["strategy_generator"].generate.return_value = [Mock(type="risky_strategy")]
        mock_components["dispersion_module"].analyze_dispersion_opportunity.return_value = None
        mock_components["gamma_scalper"].identify_opportunities.return_value = []
        
        mock_components["risk_authority"].validate_trade.return_value = Mock(
            approved=False,
            reason="Exceeds risk limits"
        )
        mock_components["capital_allocator"].allocate_capital.return_value = {}
        
        portfolio_greeks = Mock(delta=0.0, gamma=10.0, vega=50.0, theta=-5.0)
        mock_components["greeks_aggregator"].compute_portfolio_greeks.return_value = portfolio_greeks
        
        # Mock target Greeks for feedback loop
        target_greeks = Mock(delta=0.0, gamma=10.0, vega=50.0, theta=-5.0)
        mock_components["risk_authority"].get_target_greeks.return_value = target_greeks
        
        # Mock feedback loop methods
        mock_components["capital_allocator"].update_performance_history = Mock()
        mock_components["strategy_generator"].update_from_feedback = Mock()
        
        performance = {}
        mock_components["performance_monitor"].update_performance.return_value = performance
        
        # Execute with target Greeks to trigger strategy generation
        target = TargetGreeks(
            delta=0.0, gamma=10.0, vega=50.0, theta=-5.0,
            delta_tolerance=0.1, gamma_tolerance=0.1, vega_tolerance=0.1, theta_tolerance=0.1
        )
        result = unified_engine.run_trading_cycle(sample_market_data, target)
        
        # Verify strategy rejected
        assert len(result.strategies_generated) == 1
        assert len(result.strategies_approved) == 0
        assert len(result.orders_submitted) == 0
        
        # Verify execution interface not called
        mock_components["execution_interface"].submit_order.assert_not_called()


class TestRegimeChangePropagation:
    """Test regime change propagation through all components"""
    
    def test_regime_change_triggers_reallocation(self, unified_engine, mock_components, sample_state):
        """Test regime change triggers capital reallocation"""
        # Setup
        mock_components["capital_allocator"].allocate_capital.return_value = {
            "long_vol": 50000.0,
            "tail_hedge": 30000.0
        }
        mock_components["greeks_aggregator"].compute_portfolio_greeks.return_value = Mock(
            delta=0.0, gamma=5.0, vega=25.0, theta=-2.0
        )
        mock_components["risk_authority"].get_target_greeks.return_value = Mock(
            delta=0.0, gamma=10.0, vega=50.0, theta=-5.0
        )
        
        # Execute regime change
        unified_engine.handle_regime_change("low_vol", "high_vol", sample_state)
        
        # Verify capital allocator called
        mock_components["capital_allocator"].allocate_capital.assert_called_once()
    
    def test_crisis_regime_triggers_emergency_protocols(self, unified_engine, mock_components, sample_state):
        """Test crisis regime triggers emergency actions"""
        # Setup
        mock_components["capital_allocator"].allocate_capital.return_value = {}
        mock_components["greeks_aggregator"].compute_portfolio_greeks.return_value = Mock(
            delta=0.0, gamma=5.0, vega=25.0, theta=-2.0
        )
        mock_components["risk_authority"].get_target_greeks.return_value = Mock(
            delta=0.0, gamma=10.0, vega=50.0, theta=-5.0
        )
        mock_components["risk_authority"].emergency_action.return_value = Mock(
            action="REDUCE_POSITIONS",
            target_reduction=0.5
        )
        
        # Execute regime change to crisis
        unified_engine.handle_regime_change("high_vol", "crisis", sample_state)
        
        # Verify emergency action triggered
        mock_components["risk_authority"].emergency_action.assert_called_once()
    
    def test_regime_change_event_emitted(self, unified_engine, mock_components, sample_state):
        """Test regime change emits event to listeners"""
        # Setup event listener
        events_received = []
        
        def listener(event):
            events_received.append(event)
        
        unified_engine.register_event_listener(EventType.REGIME_CHANGE, listener)
        
        # Setup mocks
        mock_components["capital_allocator"].allocate_capital.return_value = {}
        mock_components["greeks_aggregator"].compute_portfolio_greeks.return_value = Mock(
            delta=0.0, gamma=5.0, vega=25.0, theta=-2.0
        )
        mock_components["risk_authority"].get_target_greeks.return_value = Mock(
            delta=0.0, gamma=10.0, vega=50.0, theta=-5.0
        )
        
        # Execute
        unified_engine.handle_regime_change("low_vol", "crisis", sample_state)
        
        # Verify event received
        assert len(events_received) == 1
        assert events_received[0].event_type == EventType.REGIME_CHANGE
        assert events_received[0].data["old_regime"] == "low_vol"
        assert events_received[0].data["new_regime"] == "crisis"


class TestEmergencyActions:
    """Test emergency action triggering and execution"""
    
    def test_greeks_violation_triggers_adjustment(self, unified_engine, mock_components, sample_state):
        """Test Greeks violation triggers adjustment trades"""
        # Setup - portfolio Greeks deviate significantly from targets
        current_greeks = Mock(delta=50.0, gamma=5.0, vega=25.0, theta=-2.0)
        target_greeks = Mock(delta=0.0, gamma=10.0, vega=50.0, theta=-5.0)
        
        mock_components["risk_authority"].get_target_greeks.return_value = target_greeks
        mock_components["strategy_generator"].generate.return_value = [Mock(type="adjustment")]
        mock_components["risk_authority"].validate_trade.return_value = Mock(approved=True)
        mock_components["execution_interface"].submit_order.return_value = Mock(success=True)
        
        # Execute feedback loop with large deviation
        unified_engine._adjust_for_greeks_deviation(current_greeks, sample_state)
        
        # Verify adjustment strategies generated
        mock_components["strategy_generator"].generate.assert_called()
    
    def test_component_error_triggers_recovery(self, unified_engine, mock_components):
        """Test component errors trigger recovery actions"""
        # Setup - simulate recoverable error
        def failing_func():
            raise ConnectionError("Temporary connection failure")
        
        # Execute with error
        result, error = unified_engine._safe_component_call(
            "execution_interface",
            "submit_order",
            failing_func
        )
        
        # Verify error captured
        assert result is None
        assert error is not None
        assert error.recoverable is True
        assert error.recovery_action == "retry_with_backoff"
    
    def test_critical_error_halts_trading(self, unified_engine, mock_components):
        """Test critical errors halt trading"""
        # Setup - simulate non-recoverable error
        def critical_failure():
            raise RuntimeError("Critical system failure")
        
        # Execute
        result, error = unified_engine._safe_component_call(
            "state_engine",
            "get_state",
            critical_failure
        )
        
        # Verify error captured as non-recoverable
        assert result is None
        assert error is not None
        assert error.recoverable is False


class TestEventDrivenCommunication:
    """Test event-driven updates between components"""
    
    def test_event_listener_registration(self, unified_engine):
        """Test event listeners can be registered"""
        callback = Mock()
        
        unified_engine.register_event_listener(EventType.STATE_UPDATE, callback)
        
        # Verify listener registered
        assert EventType.STATE_UPDATE in unified_engine._event_listeners
        assert callback in unified_engine._event_listeners[EventType.STATE_UPDATE]
    
    def test_event_emission_calls_listeners(self, unified_engine):
        """Test emitted events call registered listeners"""
        callback1 = Mock()
        callback2 = Mock()
        
        unified_engine.register_event_listener(EventType.RISK_ALERT, callback1)
        unified_engine.register_event_listener(EventType.RISK_ALERT, callback2)
        
        # Emit event
        event = SystemEvent(
            event_type=EventType.RISK_ALERT,
            timestamp=datetime.now(),
            component="risk_authority",
            data={"alert": "test"},
            severity="WARNING"
        )
        unified_engine._emit_event(event)
        
        # Verify both listeners called
        callback1.assert_called_once_with(event)
        callback2.assert_called_once_with(event)
    
    def test_listener_failure_does_not_break_system(self, unified_engine):
        """Test failing listener doesn't break event system"""
        def failing_listener(event):
            raise Exception("Listener failure")
        
        working_listener = Mock()
        
        unified_engine.register_event_listener(EventType.STATE_UPDATE, failing_listener)
        unified_engine.register_event_listener(EventType.STATE_UPDATE, working_listener)
        
        # Emit event
        event = SystemEvent(
            event_type=EventType.STATE_UPDATE,
            timestamp=datetime.now(),
            component="state_engine",
            data={},
            severity="INFO"
        )
        unified_engine._emit_event(event)
        
        # Verify working listener still called
        working_listener.assert_called_once()


class TestComponentHealth:
    """Test component health monitoring"""
    
    def test_component_health_tracking(self, unified_engine, mock_components):
        """Test component health is tracked"""
        # Simulate some errors
        def failing_func():
            raise ValueError("Test error")
        
        unified_engine._safe_component_call("strategy_generator", "generate", failing_func)
        unified_engine._safe_component_call("strategy_generator", "generate", failing_func)
        
        # Get health status
        health = unified_engine.get_component_health()
        
        # Verify health tracked
        assert "strategy_generator" in health
        assert health["strategy_generator"]["status"] == "degraded"
        assert health["strategy_generator"]["recent_errors"] == 2
    
    def test_healthy_components_reported(self, unified_engine):
        """Test healthy components reported correctly"""
        health = unified_engine.get_component_health()
        
        # All components should be healthy initially
        for component_health in health.values():
            assert component_health["status"] == "healthy"
            assert component_health["recent_errors"] == 0


class TestFeedbackLoop:
    """Test Greeks monitoring → performance attribution feedback loop"""
    
    def test_feedback_loop_updates_history(self, unified_engine, sample_state, mock_components):
        """Test feedback loop maintains history"""
        strategies = [Mock(type="test")]
        performance = {"sharpe_ratio": 1.5}
        greeks = Mock(delta=0.0, gamma=10.0, vega=50.0, theta=-5.0)
        
        # Mock target Greeks
        target_greeks = Mock(delta=0.0, gamma=10.0, vega=50.0, theta=-5.0)
        mock_components["risk_authority"].get_target_greeks.return_value = target_greeks
        
        # Mock feedback loop methods
        mock_components["capital_allocator"].update_performance_history = Mock()
        mock_components["strategy_generator"].update_from_feedback = Mock()
        
        # Execute feedback update
        unified_engine._update_feedback_loop(sample_state, strategies, performance, greeks)
        
        # Verify history updated
        history = unified_engine.get_feedback_history()
        assert len(history) == 1
        assert history[0]["regime"] == sample_state.regime
        assert history[0]["performance"] == performance
    
    def test_greeks_deviation_detected(self, unified_engine, sample_state, mock_components):
        """Test large Greeks deviation is detected"""
        current_greeks = Mock(delta=100.0, gamma=5.0, vega=25.0, theta=-2.0)
        target_greeks = Mock(delta=0.0, gamma=10.0, vega=50.0, theta=-5.0)
        
        mock_components["risk_authority"].get_target_greeks.return_value = target_greeks
        
        # Compute deviation
        deviation = unified_engine._compute_greeks_deviation(current_greeks, sample_state)
        
        # Verify large deviation detected
        assert deviation > 0.2  # Should exceed 20% threshold


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
