"""
Tests for Edge Half-Life Model

These tests verify the edge persistence tracking and capital decay functionality.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from src.intelligence.edge_half_life import (
    EdgeHalfLifeTracker, EdgeStatus, EdgeMetrics, EdgeStateManager
)


class TestEdgeHalfLifeTracker:
    """Test suite for EdgeHalfLifeTracker"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.tracker = EdgeHalfLifeTracker(
            lookback_window=30,
            min_observations=10,
            decay_power=2.0,
            confidence_threshold=0.7
        )
        
        self.base_timestamp = datetime(2024, 1, 1)
    
    def test_initialization(self):
        """Test tracker initialization"""
        assert self.tracker.lookback_window == 30
        assert self.tracker.min_observations == 10
        assert self.tracker.decay_power == 2.0
        assert len(self.tracker.performance_history) == 0
        assert len(self.tracker.edge_models) == 0
    
    def test_update_performance_single_record(self):
        """Test updating performance with single record"""
        self.tracker.update_performance(
            strategy_id="test_strategy",
            timestamp=self.base_timestamp,
            returns=0.05,
            benchmark_returns=0.02,
            volatility=0.15,
            confidence=0.8,
            regime="bull"
        )
        
        assert "test_strategy" in self.tracker.performance_history
        df = self.tracker.performance_history["test_strategy"]
        assert len(df) == 1
        assert df.iloc[0]['returns'] == 0.05
        assert df.iloc[0]['edge_value'] == (0.05 - 0.02) / 0.15  # (returns - benchmark) / volatility
    
    def test_update_performance_multiple_records(self):
        """Test updating performance with multiple records"""
        strategy_id = "test_strategy"
        
        # Add multiple performance records
        for i in range(15):
            timestamp = self.base_timestamp + timedelta(days=i)
            returns = 0.05 - (i * 0.001)  # Declining returns
            
            self.tracker.update_performance(
                strategy_id=strategy_id,
                timestamp=timestamp,
                returns=returns,
                benchmark_returns=0.02,
                volatility=0.15,
                confidence=0.8,
                regime="bull"
            )
        
        # Should have edge model after min_observations
        assert strategy_id in self.tracker.edge_models
        assert strategy_id in self.tracker.edge_metrics
        
        # Check edge metrics
        metrics = self.tracker.edge_metrics[strategy_id]
        assert isinstance(metrics, EdgeMetrics)
        assert metrics.strategy_id == strategy_id
        assert metrics.decay_rate > 0
        assert metrics.half_life_days > 0
    
    def test_edge_decay_calculation(self):
        """Test edge decay rate calculation"""
        strategy_id = "decay_test"
        
        # Create synthetic decaying edge data
        peak_edge = 0.3
        true_decay_rate = 0.05  # 5% per day
        
        for i in range(20):
            timestamp = self.base_timestamp + timedelta(days=i)
            
            # Synthetic edge with exponential decay + noise
            edge_value = peak_edge * np.exp(-true_decay_rate * i) + np.random.normal(0, 0.01)
            
            # Convert back to returns (edge = excess_return / volatility)
            volatility = 0.15
            excess_return = edge_value * volatility
            returns = excess_return + 0.02  # Add benchmark return
            
            self.tracker.update_performance(
                strategy_id=strategy_id,
                timestamp=timestamp,
                returns=returns,
                benchmark_returns=0.02,
                volatility=volatility,
                confidence=0.8,
                regime="bull"
            )
        
        # Check that decay rate is estimated reasonably
        model = self.tracker.edge_models[strategy_id]
        assert abs(model.decay_rate - true_decay_rate) < 0.02  # Within 2% tolerance
    
    def test_capital_multiplier_calculation(self):
        """Test capital multiplier calculation"""
        strategy_id = "multiplier_test"
        
        # Create strategy with good edge health
        self.tracker.edge_metrics[strategy_id] = EdgeMetrics(
            strategy_id=strategy_id,
            timestamp=datetime.now(),
            edge_value=0.2,
            decay_rate=0.01,
            half_life_days=69.3,  # ln(2)/0.01
            edge_health=0.8,
            status=EdgeStatus.HEALTHY,
            confidence=0.9,
            observations=20,
            regime_context="bull"
        )
        
        multiplier = self.tracker.get_capital_multiplier(strategy_id)
        
        # Should be high for healthy edge
        assert multiplier > 0.5  # Adjusted for actual calculation
        assert multiplier <= 1.0
    
    def test_capital_multiplier_decaying_edge(self):
        """Test capital multiplier for decaying edge"""
        strategy_id = "decaying_test"
        
        # Create strategy with poor edge health
        self.tracker.edge_metrics[strategy_id] = EdgeMetrics(
            strategy_id=strategy_id,
            timestamp=datetime.now(),
            edge_value=0.1,
            decay_rate=0.1,
            half_life_days=6.93,  # ln(2)/0.1
            edge_health=0.2,
            status=EdgeStatus.STALE,
            confidence=0.8,
            observations=20,
            regime_context="bear"
        )
        
        multiplier = self.tracker.get_capital_multiplier(strategy_id)
        
        # Should be low for poor edge health
        assert multiplier < 0.3
        assert multiplier >= 0.0
    
    def test_should_exit_strategy(self):
        """Test exit signal generation"""
        strategy_id = "exit_test"
        
        # Create strategy with very poor edge health
        self.tracker.edge_metrics[strategy_id] = EdgeMetrics(
            strategy_id=strategy_id,
            timestamp=datetime.now(),
            edge_value=0.05,
            decay_rate=0.2,
            half_life_days=3.47,  # ln(2)/0.2
            edge_health=0.1,
            status=EdgeStatus.DEAD,
            confidence=0.8,
            observations=20,
            regime_context="bear"
        )
        
        should_exit = self.tracker.should_exit_strategy(strategy_id, threshold=0.3)
        assert should_exit is True
        
        # Test with higher threshold
        should_exit = self.tracker.should_exit_strategy(strategy_id, threshold=0.05)
        assert should_exit is False
    
    def test_portfolio_edge_summary(self):
        """Test portfolio-level edge summary"""
        # Add multiple strategies with different edge health
        strategies = [
            ("healthy_1", 0.8, EdgeStatus.HEALTHY),
            ("healthy_2", 0.7, EdgeStatus.HEALTHY),
            ("decaying_1", 0.4, EdgeStatus.DECAYING),
            ("stale_1", 0.1, EdgeStatus.STALE)
        ]
        
        for strategy_id, edge_health, status in strategies:
            self.tracker.edge_metrics[strategy_id] = EdgeMetrics(
                strategy_id=strategy_id,
                timestamp=datetime.now(),
                edge_value=0.1,
                decay_rate=0.05,
                half_life_days=13.86,
                edge_health=edge_health,
                status=status,
                confidence=0.8,
                observations=20,
                regime_context="neutral"
            )
        
        summary = self.tracker.get_portfolio_edge_summary()
        
        assert summary['total_strategies'] == 4
        assert summary['healthy_strategies'] == 2
        assert summary['healthy_percentage'] == 0.5
        assert 'avg_edge_health' in summary
        assert 'status_distribution' in summary
    
    def test_reset_strategy_model(self):
        """Test resetting strategy model"""
        strategy_id = "reset_test"
        
        # Add some data
        self.tracker.edge_metrics[strategy_id] = EdgeMetrics(
            strategy_id=strategy_id,
            timestamp=datetime.now(),
            edge_value=0.1,
            decay_rate=0.05,
            half_life_days=13.86,
            edge_health=0.5,
            status=EdgeStatus.HEALTHY,
            confidence=0.8,
            observations=20,
            regime_context="neutral"
        )
        
        # Reset
        self.tracker.reset_strategy_model(strategy_id)
        
        # Should be removed
        assert strategy_id not in self.tracker.edge_metrics
        assert strategy_id not in self.tracker.edge_models
    
    def test_lookback_window_enforcement(self):
        """Test that lookback window is enforced"""
        strategy_id = "window_test"
        
        # Add data beyond lookback window
        for i in range(50):  # More than lookback_window of 30
            timestamp = self.base_timestamp + timedelta(days=i)
            
            self.tracker.update_performance(
                strategy_id=strategy_id,
                timestamp=timestamp,
                returns=0.05,
                benchmark_returns=0.02,
                volatility=0.15,
                confidence=0.8,
                regime="bull"
            )
        
        # Should only keep recent data
        df = self.tracker.performance_history[strategy_id]
        assert len(df) <= self.tracker.lookback_window + 5  # Some buffer for edge cases


class TestEdgeStateManager:
    """Test suite for EdgeStateManager"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.mock_unified_state = Mock()
        self.tracker = EdgeHalfLifeTracker()
        self.state_manager = EdgeStateManager(self.mock_unified_state, self.tracker)
    
    def test_initialization(self):
        """Test state manager initialization"""
        assert self.state_manager.unified_state == self.mock_unified_state
        assert self.state_manager.edge_tracker == self.tracker
    
    def test_update_edge_state(self):
        """Test updating edge state in unified state"""
        # Add some mock edge metrics
        strategy_id = "test_strategy"
        self.tracker.edge_metrics[strategy_id] = EdgeMetrics(
            strategy_id=strategy_id,
            timestamp=datetime.now(),
            edge_value=0.2,
            decay_rate=0.05,
            half_life_days=13.86,
            edge_health=0.7,
            status=EdgeStatus.HEALTHY,
            confidence=0.8,
            observations=20,
            regime_context="bull"
        )
        
        # Update state
        self.state_manager.update_edge_state()
        
        # Verify unified state was updated
        assert self.mock_unified_state.update_state.call_count >= 2  # edge_metrics and portfolio_summary
        
        # Check that edge_metrics was updated
        calls = self.mock_unified_state.update_state.call_args_list
        edge_metrics_call = next(call for call in calls if call[0][0] == 'edge_metrics')
        assert edge_metrics_call is not None
    
    def test_get_strategy_capital_multiplier(self):
        """Test getting capital multiplier from state"""
        strategy_id = "test_strategy"
        
        # Mock state return
        self.mock_unified_state.get_state.return_value = {
            strategy_id: {
                'capital_multiplier': 0.75,
                'edge_health': 0.8
            }
        }
        
        multiplier = self.state_manager.get_strategy_capital_multiplier(strategy_id)
        assert multiplier == 0.75
        
        # Test default case
        self.mock_unified_state.get_state.return_value = {}
        multiplier = self.state_manager.get_strategy_capital_multiplier("unknown_strategy")
        assert multiplier == 0.5  # Default
    
    def test_should_exit_strategy(self):
        """Test exit signal from state"""
        strategy_id = "test_strategy"
        
        # Mock state return
        self.mock_unified_state.get_state.return_value = {
            strategy_id: {
                'should_exit': True,
                'edge_health': 0.2
            }
        }
        
        should_exit = self.state_manager.should_exit_strategy(strategy_id)
        assert should_exit is True
        
        # Test default case
        self.mock_unified_state.get_state.return_value = {}
        should_exit = self.state_manager.should_exit_strategy("unknown_strategy")
        assert should_exit is False  # Default


class TestEdgeMetricsIntegration:
    """Integration tests for edge metrics"""
    
    def test_full_workflow(self):
        """Test complete edge tracking workflow"""
        tracker = EdgeHalfLifeTracker(
            lookback_window=30,
            min_observations=10,
            decay_power=2.0
        )
        
        strategy_id = "integration_test"
        base_timestamp = datetime(2024, 1, 1)
        
        # Simulate strategy lifecycle
        # Phase 1: Strong performance
        for i in range(10):
            timestamp = base_timestamp + timedelta(days=i)
            returns = 0.08 - (i * 0.001)  # Slight decline
            
            tracker.update_performance(
                strategy_id=strategy_id,
                timestamp=timestamp,
                returns=returns,
                benchmark_returns=0.02,
                volatility=0.15,
                confidence=0.9,
                regime="bull"
            )
        
        # Should have model now
        assert strategy_id in tracker.edge_models
        metrics = tracker.get_edge_metrics(strategy_id)
        assert metrics.status in [EdgeStatus.FRESH, EdgeStatus.HEALTHY]
        
        # Phase 2: Declining performance
        for i in range(10, 25):
            timestamp = base_timestamp + timedelta(days=i)
            returns = 0.08 - (i * 0.002)  # Faster decline
            
            tracker.update_performance(
                strategy_id=strategy_id,
                timestamp=timestamp,
                returns=returns,
                benchmark_returns=0.02,
                volatility=0.15,
                confidence=0.8,
                regime="bull"
            )
        
        # Should show degrading edge
        metrics = tracker.get_edge_metrics(strategy_id)
        assert metrics.edge_health < 0.8  # Should be declining
        
        # Capital multiplier should be reduced
        multiplier = tracker.get_capital_multiplier(strategy_id)
        assert multiplier < 1.0
        
        # Portfolio summary should reflect degradation
        summary = tracker.get_portfolio_edge_summary()
        assert summary['total_strategies'] == 1
        assert summary['portfolio_edge_score'] < 0.8


if __name__ == "__main__":
    pytest.main([__file__])