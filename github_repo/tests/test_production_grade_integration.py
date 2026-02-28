"""
Tests for Production Grade Enhancements Integration

These tests verify the integration of Edge Half-Life and Liquidity Kill Switch
into the existing Northstar V3 system.
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.integration.production_grade_enhancements import ProductionGradeRiskManager
from src.intelligence.edge_half_life import EdgeStatus, EdgeMetrics
from src.risk.liquidity_kill_switch import LiquidityStatus, LiquidationUrgency


class TestProductionGradeRiskManager:
    """Test suite for ProductionGradeRiskManager"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.mock_unified_state = Mock()
        self.mock_risk_coordinator = Mock()
        self.mock_kill_switch = Mock()
        
        self.risk_manager = ProductionGradeRiskManager(
            unified_state=self.mock_unified_state,
            base_risk_coordinator=self.mock_risk_coordinator,
            base_kill_switch=self.mock_kill_switch
        )
    
    def test_initialization(self):
        """Test risk manager initialization"""
        assert self.risk_manager.unified_state == self.mock_unified_state
        assert self.risk_manager.base_risk_coordinator == self.mock_risk_coordinator
        assert self.risk_manager.base_kill_switch == self.mock_kill_switch
        
        # Check that enhanced components are initialized
        assert self.risk_manager.edge_tracker is not None
        assert self.risk_manager.liquidity_assessor is not None
        assert self.risk_manager.liquidity_kill_switch is not None
        assert self.risk_manager.edge_state_manager is not None
        
        # Check integration flags
        assert self.risk_manager.edge_integration_enabled is True
        assert self.risk_manager.liquidity_integration_enabled is True
    
    def test_update_strategy_performance(self):
        """Test strategy performance update"""
        strategy_id = "test_strategy"
        timestamp = datetime.now()
        
        self.risk_manager.update_strategy_performance(
            strategy_id=strategy_id,
            timestamp=timestamp,
            returns=0.05,
            benchmark_returns=0.02,
            volatility=0.15,
            confidence=0.8,
            regime="bull"
        )
        
        # Verify edge tracker was updated
        assert strategy_id in self.risk_manager.edge_tracker.performance_history
        
        # Verify state manager was called to update state
        # (This would be verified through mock calls in a real implementation)
    
    def test_update_market_liquidity(self):
        """Test market liquidity data update"""
        symbol = "TEST_STOCK"
        timestamp = datetime.now()
        
        self.risk_manager.update_market_liquidity(
            symbol=symbol,
            timestamp=timestamp,
            volume=100000,
            bid_price=99.5,
            ask_price=100.5,
            last_price=100.0
        )
        
        # Verify liquidity assessor was updated
        assert symbol in self.risk_manager.liquidity_assessor.volume_history
    
    def test_get_enhanced_capital_allocation_with_edge_decay(self):
        """Test capital allocation with edge decay"""
        # Setup edge metrics for strategies
        strategy_metrics = {
            "healthy_strategy": EdgeMetrics(
                strategy_id="healthy_strategy",
                timestamp=datetime.now(),
                edge_value=0.2,
                decay_rate=0.01,
                half_life_days=69.3,
                edge_health=0.8,
                status=EdgeStatus.HEALTHY,
                confidence=0.9,
                observations=30,
                regime_context="bull"
            ),
            "decaying_strategy": EdgeMetrics(
                strategy_id="decaying_strategy",
                timestamp=datetime.now(),
                edge_value=0.1,
                decay_rate=0.1,
                half_life_days=6.93,
                edge_health=0.2,
                status=EdgeStatus.STALE,
                confidence=0.8,
                observations=25,
                regime_context="bear"
            )
        }
        
        # Mock edge tracker metrics
        self.risk_manager.edge_tracker.edge_metrics = strategy_metrics
        
        # Mock state manager responses
        def mock_get_multiplier(strategy_id):
            if strategy_id == "healthy_strategy":
                return 0.9  # High multiplier for healthy strategy
            elif strategy_id == "decaying_strategy":
                return 0.1  # Low multiplier for decaying strategy
            return 0.5
        
        self.risk_manager.edge_state_manager.get_strategy_capital_multiplier = mock_get_multiplier
        
        # Test allocation adjustment
        proposed_allocations = {
            "healthy_strategy": 0.4,
            "decaying_strategy": 0.4,
            "other_strategy": 0.2
        }
        
        strategy_edges = {
            "healthy_strategy": 0.05,
            "decaying_strategy": 0.01,
            "other_strategy": 0.03
        }
        
        enhanced_allocations = self.risk_manager.get_enhanced_capital_allocation(
            proposed_allocations, strategy_edges
        )
        
        # Healthy strategy should maintain most of its allocation
        assert enhanced_allocations["healthy_strategy"] > 0.35
        
        # Decaying strategy should have reduced allocation
        assert enhanced_allocations["decaying_strategy"] < 0.1
        
        # Total allocation should still sum to approximately 1.0
        total_allocation = sum(enhanced_allocations.values())
        assert abs(total_allocation - 1.0) < 0.01
    
    def test_validate_trade_with_liquidity_constraints(self):
        """Test trade validation with liquidity constraints"""
        # Mock trade object
        mock_trade = Mock()
        mock_trade.symbol = "TEST_STOCK"
        mock_trade.quantity = 10000
        mock_trade.price = 100.0
        mock_trade.timestamp = datetime.now()
        
        # Mock portfolio and metrics
        mock_portfolio = Mock()
        mock_metrics = Mock()
        
        # Mock base risk coordinator response
        from src.risk.risk_coordinator import RiskDecision
        self.mock_risk_coordinator.validate_trade.return_value = (
            RiskDecision.APPROVED, []
        )
        
        # Test with normal liquidity
        with patch.object(self.risk_manager.liquidity_assessor, 'calculate_position_liquidity') as mock_calc:
            mock_calc.return_value = Mock(
                exit_risk=0.5,
                participation_rate=0.1,
                liquidity_status=LiquidityStatus.NORMAL
            )
            
            approved, violations = self.risk_manager.validate_trade_with_liquidity(
                mock_trade, mock_portfolio, mock_metrics
            )
            
            assert approved is True
            assert len(violations) == 0
        
        # Test with high liquidity risk
        with patch.object(self.risk_manager.liquidity_assessor, 'calculate_position_liquidity') as mock_calc:
            mock_calc.return_value = Mock(
                exit_risk=3.0,  # High exit risk
                participation_rate=0.4,  # High participation
                liquidity_status=LiquidityStatus.FROZEN
            )
            
            approved, violations = self.risk_manager.validate_trade_with_liquidity(
                mock_trade, mock_portfolio, mock_metrics
            )
            
            assert approved is False
            assert len(violations) > 0
            assert any("exit risk" in v.lower() for v in violations)
    
    def test_should_trigger_enhanced_kill_switch_liquidity_aware(self):
        """Test enhanced kill switch trigger logic"""
        mock_trigger_type = Mock(value='drawdown_limit')
        current_metrics = {'current_drawdown': 0.12}
        positions = {
            "STOCK_1": {"position_size": 10000, "market_value": 1000000},
            "STOCK_2": {"position_size": 50000, "market_value": 500000}
        }
        
        # Mock liquidity kill switch response
        self.risk_manager.liquidity_kill_switch.should_trigger_kill_switch = Mock(
            return_value=(False, "exit_risk_too_high_2.5")
        )
        
        should_trigger, reason = self.risk_manager.should_trigger_enhanced_kill_switch(
            mock_trigger_type, current_metrics, positions
        )
        
        assert should_trigger is False
        assert "exit_risk_too_high" in reason
    
    def test_execute_enhanced_liquidation_different_urgencies(self):
        """Test enhanced liquidation with different urgency levels"""
        positions = {
            "STOCK_1": {"position_size": 10000, "market_value": 1000000}
        }
        
        # Mock liquidation results for different urgencies
        mock_results = {
            'routine': {
                'strategy_type': 'gradual_liquidation',
                'executed_orders': [{'symbol': 'STOCK_1', 'status': 'EXECUTED'}],
                'success': True,
                'total_market_impact': 0.01
            },
            'emergency': {
                'strategy_type': 'emergency_liquidation',
                'executed_orders': [{'symbol': 'STOCK_1', 'status': 'EXECUTED'}],
                'success': True,
                'total_market_impact': 0.05,
                'high_impact_expected': True
            }
        }
        
        for urgency, expected_result in mock_results.items():
            with patch.object(self.risk_manager.liquidity_kill_switch, 
                             'execute_liquidity_aware_liquidation',
                             return_value=expected_result):
                
                result = self.risk_manager.execute_enhanced_liquidation(
                    positions, urgency
                )
                
                assert result['strategy_type'] == expected_result['strategy_type']
                assert result['success'] is True
                
                if urgency == 'emergency':
                    assert result['total_market_impact'] > 0.03
                else:
                    assert result['total_market_impact'] < 0.02
    
    def test_get_production_risk_summary(self):
        """Test comprehensive production risk summary"""
        # Mock base risk summary
        mock_base_summary = {
            'status': 'HEALTHY',
            'risk_score': 25.0,
            'violations': []
        }
        self.mock_risk_coordinator.get_risk_summary.return_value = mock_base_summary
        
        # Mock edge summary
        mock_edge_summary = {
            'portfolio_edge_score': 0.7,
            'healthy_strategies': 3,
            'total_strategies': 4
        }
        
        # Mock liquidity summary
        mock_liquidity_summary = {
            'portfolio_liquidity_score': 0.8,
            'systemic_risk_level': 0.2,
            'kill_switch_recommendation': 'NORMAL_KILL_SWITCH_OPERATION'
        }
        
        with patch.object(self.risk_manager.edge_tracker, 'get_portfolio_edge_summary',
                         return_value=mock_edge_summary):
            with patch.object(self.risk_manager.liquidity_kill_switch, 'get_liquidity_status_summary',
                             return_value=mock_liquidity_summary):
                
                summary = self.risk_manager.get_production_risk_summary()
        
        assert 'base_risk' in summary
        assert 'edge_health' in summary
        assert 'liquidity_risk' in summary
        assert 'overall_status' in summary
        
        assert summary['base_risk']['status'] == 'HEALTHY'
        assert summary['edge_health']['portfolio_edge_score'] == 0.7
        assert summary['liquidity_risk']['portfolio_liquidity_score'] == 0.8
        assert summary['overall_status'] == 'HEALTHY'
    
    def test_integration_flags_control(self):
        """Test integration enable/disable functionality"""
        # Test edge integration control
        assert self.risk_manager.edge_integration_enabled is True
        
        self.risk_manager.disable_edge_integration()
        assert self.risk_manager.edge_integration_enabled is False
        
        self.risk_manager.enable_edge_integration()
        assert self.risk_manager.edge_integration_enabled is True
        
        # Test liquidity integration control
        assert self.risk_manager.liquidity_integration_enabled is True
        
        self.risk_manager.disable_liquidity_integration()
        assert self.risk_manager.liquidity_integration_enabled is False
        
        self.risk_manager.enable_liquidity_integration()
        assert self.risk_manager.liquidity_integration_enabled is True
    
    def test_disabled_integrations_fallback(self):
        """Test fallback behavior when integrations are disabled"""
        # Disable both integrations
        self.risk_manager.disable_edge_integration()
        self.risk_manager.disable_liquidity_integration()
        
        # Test capital allocation fallback
        proposed_allocations = {"strategy_1": 0.5, "strategy_2": 0.5}
        strategy_edges = {"strategy_1": 0.03, "strategy_2": 0.02}
        
        enhanced_allocations = self.risk_manager.get_enhanced_capital_allocation(
            proposed_allocations, strategy_edges
        )
        
        # Should return unchanged allocations
        assert enhanced_allocations == proposed_allocations
        
        # Test kill switch fallback
        mock_trigger_type = Mock()
        self.mock_kill_switch._check_trigger_condition.return_value = True
        
        should_trigger, reason = self.risk_manager.should_trigger_enhanced_kill_switch(
            mock_trigger_type, {}, {}
        )
        
        assert should_trigger is True
        assert reason == "base_kill_switch"
    
    def test_error_handling_and_logging(self):
        """Test error handling and logging in production manager"""
        # Test error in strategy performance update
        with patch.object(self.risk_manager.edge_tracker, 'update_performance',
                         side_effect=Exception("Test error")):
            
            # Should not raise exception, but log error
            self.risk_manager.update_strategy_performance(
                strategy_id="test",
                timestamp=datetime.now(),
                returns=0.05,
                benchmark_returns=0.02,
                volatility=0.15,
                confidence=0.8,
                regime="bull"
            )
            
            # Verify it handled the error gracefully
            # (In a real implementation, we'd check log messages)
        
        # Test error in liquidity validation
        mock_trade = Mock()
        mock_trade.symbol = "ERROR_STOCK"
        
        with patch.object(self.risk_manager.liquidity_assessor, 'calculate_position_liquidity',
                         side_effect=Exception("Liquidity error")):
            
            # Should fall back to base validation
            from src.risk.risk_coordinator import RiskDecision
            self.mock_risk_coordinator.validate_trade.return_value = (
                RiskDecision.APPROVED, []
            )
            
            approved, violations = self.risk_manager.validate_trade_with_liquidity(
                mock_trade, Mock(), Mock()
            )
            
            # Should still work with base validation
            assert approved is True
    
    def test_get_integration_status(self):
        """Test integration status reporting"""
        # Add some mock data
        self.risk_manager.edge_tracker.edge_metrics = {
            "strategy_1": Mock(),
            "strategy_2": Mock()
        }
        
        self.risk_manager.liquidity_assessor.liquidity_metrics = {
            "STOCK_1": Mock(),
            "STOCK_2": Mock(),
            "STOCK_3": Mock()
        }
        
        status = self.risk_manager.get_integration_status()
        
        assert status['edge_integration_enabled'] is True
        assert status['liquidity_integration_enabled'] is True
        assert status['edge_strategies_tracked'] == 2
        assert status['liquidity_symbols_tracked'] == 3
        assert 'last_update' in status


class TestProductionGradeIntegrationScenarios:
    """Integration scenario tests"""
    
    def test_full_production_workflow(self):
        """Test complete production workflow"""
        # This would be a comprehensive integration test
        # that exercises the full system workflow
        
        mock_unified_state = Mock()
        mock_risk_coordinator = Mock()
        mock_kill_switch = Mock()
        
        risk_manager = ProductionGradeRiskManager(
            unified_state=mock_unified_state,
            base_risk_coordinator=mock_risk_coordinator,
            base_kill_switch=mock_kill_switch
        )
        
        # Simulate a day of trading
        base_timestamp = datetime(2024, 1, 1, 9, 30)  # Market open
        
        # 1. Update market data
        symbols = ["AAPL", "GOOGL", "MSFT"]
        for i, symbol in enumerate(symbols):
            risk_manager.update_market_liquidity(
                symbol=symbol,
                timestamp=base_timestamp + timedelta(minutes=i),
                volume=1000000 - (i * 200000),  # Decreasing liquidity
                bid_price=100.0 - 0.05,
                ask_price=100.0 + 0.05,
                last_price=100.0
            )
        
        # 2. Update strategy performance
        strategies = ["momentum", "mean_reversion", "arbitrage"]
        for i, strategy in enumerate(strategies):
            risk_manager.update_strategy_performance(
                strategy_id=strategy,
                timestamp=base_timestamp + timedelta(minutes=30 + i),
                returns=0.05 - (i * 0.01),  # Decreasing performance
                benchmark_returns=0.02,
                volatility=0.15,
                confidence=0.9 - (i * 0.1),
                regime="bull"
            )
        
        # 3. Test capital allocation
        proposed_allocations = {
            "momentum": 0.4,
            "mean_reversion": 0.3,
            "arbitrage": 0.3
        }
        
        strategy_edges = {
            "momentum": 0.04,
            "mean_reversion": 0.03,
            "arbitrage": 0.02
        }
        
        # This should work without errors
        enhanced_allocations = risk_manager.get_enhanced_capital_allocation(
            proposed_allocations, strategy_edges
        )
        
        assert isinstance(enhanced_allocations, dict)
        assert len(enhanced_allocations) >= len(proposed_allocations)
        
        # 4. Test risk summary
        summary = risk_manager.get_production_risk_summary()
        
        assert 'timestamp' in summary
        assert 'overall_status' in summary
        
        # 5. Test integration status
        status = risk_manager.get_integration_status()
        
        assert status['edge_strategies_tracked'] >= 0
        assert status['liquidity_symbols_tracked'] >= 0
    
    def test_crisis_scenario_handling(self):
        """Test system behavior during crisis scenarios"""
        mock_unified_state = Mock()
        mock_risk_coordinator = Mock()
        mock_kill_switch = Mock()
        
        risk_manager = ProductionGradeRiskManager(
            unified_state=mock_unified_state,
            base_risk_coordinator=mock_risk_coordinator,
            base_kill_switch=mock_kill_switch
        )
        
        # Simulate crisis conditions
        crisis_positions = {
            "ILLIQUID_STOCK_1": {"position_size": 100000, "market_value": 10000000},
            "ILLIQUID_STOCK_2": {"position_size": 50000, "market_value": 5000000}
        }
        
        # Mock high liquidity risk
        with patch.object(risk_manager.liquidity_kill_switch, 'should_trigger_kill_switch',
                         return_value=(False, "exit_risk_too_high_5.0")):
            
            should_trigger, reason = risk_manager.should_trigger_enhanced_kill_switch(
                Mock(value='drawdown_limit'),
                {'current_drawdown': 0.15},  # High drawdown
                crisis_positions
            )
            
            # Should not trigger due to liquidity constraints
            assert should_trigger is False
            assert "exit_risk_too_high" in reason
        
        # Test emergency liquidation in crisis
        with patch.object(risk_manager.liquidity_kill_switch, 'execute_liquidity_aware_liquidation',
                         return_value={
                             'strategy_type': 'emergency_liquidation',
                             'executed_orders': [],
                             'hedge_orders': [{'symbol': 'HEDGE_1', 'status': 'PLACED'}],
                             'success': True,
                             'frozen_positions_hedged': 2
                         }):
            
            result = risk_manager.execute_enhanced_liquidation(
                crisis_positions, 'emergency'
            )
            
            # Should handle crisis with hedging
            assert result['success'] is True
            assert 'hedge_orders' in result


if __name__ == "__main__":
    pytest.main([__file__])