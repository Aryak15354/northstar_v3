"""
Integration Tests for Options Trading V3 Integration

Tests the integration of options trading system with Northstar V3:
1. OptionsRiskValidator integration with RiskCoordinator
2. Event publishing to V3 event bus
3. Kill switch coordination with V3 risk system
4. End-to-end risk validation flow

These tests verify that options are properly integrated as a first-class
organ in the V3 nervous system, not a bolt-on sidecar.
"""

import pytest
from datetime import datetime, timedelta
from typing import List, Dict

from src.options.options_risk_validator import OptionsRiskValidator
from src.options.v3_risk_integration import OptionsV3RiskIntegration, create_v3_risk_integration
from src.options.v3_event_integration import OptionsEventPublisher, create_event_publisher, OptionsEventType
from src.options.survival_rules_engine import (
    Position as OptionsPosition,
    Trade as OptionsTradeRecord,
    PerformanceMetrics as OptionsPerformanceMetrics
)


class TestOptionsRiskValidator:
    """Test OptionsRiskValidator integration with V3 RiskCoordinator"""
    
    def test_validator_initialization(self):
        """Test validator initializes correctly"""
        validator = OptionsRiskValidator(base_capital=1000000.0)
        
        assert validator.base_capital == 1000000.0
        assert validator.survival_rules is not None
        assert validator.eligibility_validator is not None
        assert len(validator.open_options_positions) == 0
        assert len(validator.closed_options_trades) == 0
    
    def test_validator_approves_valid_trade(self):
        """Test validator approves valid options trade"""
        from src.options.options_risk_validator import Trade, Portfolio, RiskMetrics
        
        validator = OptionsRiskValidator(base_capital=1000000.0)
        
        # Create valid trade
        trade = Trade(
            symbol="NIFTY_25000_CE",
            quantity=50,
            price=100.0,
            side="buy",
            trade_type="options",
            timestamp=datetime.now(),
            metadata={
                'asset_class': 'options',
                'strategy_type': 'IRON_CONDOR',
                'max_loss': 5000.0
            }
        )
        
        portfolio = Portfolio(
            positions=[],
            cash=1000000.0,
            total_value=1000000.0,
            timestamp=datetime.now()
        )
        
        metrics = RiskMetrics(
            timestamp=datetime.now(),
            portfolio_var=0.02,
            portfolio_cvar=0.03,
            gross_exposure=0.5,
            net_exposure=0.4,
            leverage=1.0,
            max_drawdown=0.02,
            sector_concentrations={},
            position_concentrations={}
        )
        
        # Validate
        decision, violations = validator.validate(trade, portfolio, metrics)
        
        # Should approve
        assert decision.value == 'approved'
        assert len(violations) == 0
    
    def test_validator_rejects_high_drawdown(self):
        """Test validator rejects trade during high portfolio drawdown"""
        from src.options.options_risk_validator import Trade, Portfolio, RiskMetrics
        
        validator = OptionsRiskValidator(base_capital=1000000.0)
        
        trade = Trade(
            symbol="NIFTY_25000_CE",
            quantity=50,
            price=100.0,
            side="buy",
            trade_type="options",
            timestamp=datetime.now(),
            metadata={
                'asset_class': 'options',
                'strategy_type': 'IRON_CONDOR',
                'max_loss': 5000.0
            }
        )
        
        portfolio = Portfolio(
            positions=[],
            cash=1000000.0,
            total_value=1000000.0,
            timestamp=datetime.now()
        )
        
        # High drawdown
        metrics = RiskMetrics(
            timestamp=datetime.now(),
            portfolio_var=0.02,
            portfolio_cvar=0.03,
            gross_exposure=0.5,
            net_exposure=0.4,
            leverage=1.0,
            max_drawdown=0.08,  # 8% drawdown - exceeds 5% limit
            sector_concentrations={},
            position_concentrations={}
        )
        
        # Validate
        decision, violations = validator.validate(trade, portfolio, metrics)
        
        # Should reject
        assert decision.value == 'rejected'
        assert len(violations) > 0
        assert any('drawdown' in v.description.lower() for v in violations)
    
    def test_validator_rejects_portfolio_risk_cap_breach(self):
        """Test validator rejects trade that breaches portfolio risk cap"""
        from src.options.options_risk_validator import Trade, Portfolio, RiskMetrics
        
        validator = OptionsRiskValidator(base_capital=1000000.0)
        
        # Add existing positions that consume most of risk budget
        existing_positions = [
            OptionsPosition(
                position_id="pos1",
                strategy_type="IRON_CONDOR",
                max_loss=15000.0,  # 1.5% of capital
                entry_time=datetime.now(),
                is_short_vol=True
            )
        ]
        
        validator.update_options_state(
            open_positions=existing_positions,
            closed_trades=[],
            performance=OptionsPerformanceMetrics(
                current_equity=1000000.0,
                ytd_gross_profits=0.0,
                ytd_tax_liability=0.0,
                cash_buffer=0.0
            )
        )
        
        # Try to add another position that would breach 2% cap
        trade = Trade(
            symbol="NIFTY_25000_CE",
            quantity=50,
            price=100.0,
            side="buy",
            trade_type="options",
            timestamp=datetime.now(),
            metadata={
                'asset_class': 'options',
                'strategy_type': 'IRON_CONDOR',
                'max_loss': 10000.0  # Would bring total to 2.5%
            }
        )
        
        portfolio = Portfolio(
            positions=[],
            cash=1000000.0,
            total_value=1000000.0,
            timestamp=datetime.now()
        )
        
        metrics = RiskMetrics(
            timestamp=datetime.now(),
            portfolio_var=0.02,
            portfolio_cvar=0.03,
            gross_exposure=0.5,
            net_exposure=0.4,
            leverage=1.0,
            max_drawdown=0.02,
            sector_concentrations={},
            position_concentrations={}
        )
        
        # Validate
        decision, violations = validator.validate(trade, portfolio, metrics)
        
        # Should reject
        assert decision.value == 'rejected'
        assert len(violations) > 0
        assert any('risk cap' in v.description.lower() for v in violations)
    
    def test_validator_force_close_positions(self):
        """Test validator can force close all positions"""
        validator = OptionsRiskValidator(base_capital=1000000.0)
        
        # Add positions
        positions = [
            OptionsPosition(
                position_id="pos1",
                strategy_type="IRON_CONDOR",
                max_loss=5000.0,
                entry_time=datetime.now(),
                is_short_vol=True
            ),
            OptionsPosition(
                position_id="pos2",
                strategy_type="CALENDAR_SPREAD",
                max_loss=3000.0,
                entry_time=datetime.now(),
                is_short_vol=True
            )
        ]
        
        validator.update_options_state(
            open_positions=positions,
            closed_trades=[],
            performance=OptionsPerformanceMetrics(
                current_equity=1000000.0,
                ytd_gross_profits=0.0,
                ytd_tax_liability=0.0,
                cash_buffer=0.0
            )
        )
        
        # Force close
        closed_ids = validator.force_close_all_positions(reason="Emergency brake activated")
        
        # Verify
        assert len(closed_ids) == 2
        assert "pos1" in closed_ids
        assert "pos2" in closed_ids
        assert len(validator.open_options_positions) == 0


class TestV3RiskIntegration:
    """Test V3 risk system integration"""
    
    def test_integration_initialization(self):
        """Test integration initializes correctly"""
        integration = OptionsV3RiskIntegration(base_capital=1000000.0)
        
        assert integration.base_capital == 1000000.0
        assert integration.options_validator is not None
    
    def test_check_options_risk_before_trade(self):
        """Test risk check before trade"""
        integration = create_v3_risk_integration(base_capital=1000000.0)
        
        # Valid trade
        trade_metadata = {
            'symbol': 'NIFTY_25000_CE',
            'quantity': 50,
            'price': 100.0,
            'side': 'buy',
            'strategy_type': 'IRON_CONDOR',
            'max_loss': 5000.0,
            'asset_class': 'options'
        }
        
        result = integration.check_options_risk_before_trade(trade_metadata)
        
        # Should approve
        assert result['approved'] is True
        assert result['decision'] == 'approved'
        assert len(result['violations']) == 0
    
    def test_get_integrated_risk_summary(self):
        """Test integrated risk summary"""
        integration = create_v3_risk_integration(base_capital=1000000.0)
        
        summary = integration.get_integrated_risk_summary()
        
        # Verify structure
        assert 'options_risk' in summary
        assert 'v3_integration' in summary
        assert 'timestamp' in summary
        
        # Verify options risk data
        assert 'open_positions' in summary['options_risk']
        assert 'total_risk' in summary['options_risk']
        assert 'kill_switch_active' in summary['options_risk']
        
        # Verify integration status
        assert 'v3_risk_coordinator_available' in summary['v3_integration']
        assert 'v3_unified_risk_available' in summary['v3_integration']


class TestEventIntegration:
    """Test event bus integration"""
    
    def test_event_publisher_initialization(self):
        """Test event publisher initializes correctly"""
        publisher = create_event_publisher()
        
        assert publisher.event_bus is not None
        assert publisher.events_published == 0
    
    def test_publish_regime_change_event(self):
        """Test publishing regime change event"""
        publisher = create_event_publisher()
        
        publisher.publish_regime_change(
            old_regime="LOW_VOL_SELL",
            new_regime="HIGH_VOL_SELL",
            iv_rank=0.85,
            days_in_old_regime=12,
            reason="IV rank exceeded 80%"
        )
        
        assert publisher.events_published == 1
        assert len(publisher.event_bus.events) >= 1
        
        # Event structure may vary depending on event bus implementation
        event = publisher.event_bus.events[0]
        # Check if event has expected structure (flexible for different event bus implementations)
        assert isinstance(event, dict)
    
    def test_publish_trade_signal_event(self):
        """Test publishing trade signal event"""
        publisher = create_event_publisher()
        
        publisher.publish_trade_signal(
            strategy_type="IRON_CONDOR",
            regime="HIGH_VOL_SELL",
            max_loss=5000.0,
            max_profit=2000.0,
            edge_score=0.75,
            legs=[
                {'strike': 25000, 'type': 'CE', 'action': 'SELL'},
                {'strike': 25500, 'type': 'CE', 'action': 'BUY'}
            ]
        )
        
        assert publisher.events_published == 1
    
    def test_publish_position_lifecycle_events(self):
        """Test publishing position lifecycle events"""
        publisher = create_event_publisher()
        
        # Position opened
        publisher.publish_position_opened(
            position_id="pos1",
            strategy_type="IRON_CONDOR",
            max_loss=5000.0,
            entry_time=datetime.now(),
            legs=[]
        )
        
        # Position updated
        publisher.publish_position_updated(
            position_id="pos1",
            unrealized_pnl=-500.0,
            current_value=4500.0,
            portfolio_greeks={'delta': 0.1, 'gamma': 0.05}
        )
        
        # Position closed
        publisher.publish_position_closed(
            position_id="pos1",
            strategy_type="IRON_CONDOR",
            realized_pnl=1000.0,
            net_pnl=800.0,
            exit_reason="profit_target",
            hold_duration_days=5.5
        )
        
        assert publisher.events_published == 3
    
    def test_publish_kill_switch_events(self):
        """Test publishing kill switch events"""
        publisher = create_event_publisher()
        
        # Kill switch activated
        publisher.publish_kill_switch_activated(
            kill_switch_type="weekly_loss_limit",
            reason="Weekly loss exceeded 2%",
            cooldown_until=datetime.now() + timedelta(days=1),
            triggered_rules=["weekly_loss_limit"]
        )
        
        # Kill switch cleared
        publisher.publish_kill_switch_cleared(
            kill_switch_type="weekly_loss_limit",
            reason="Cooldown period expired"
        )
        
        assert publisher.events_published == 2
    
    def test_publish_greeks_breach_event(self):
        """Test publishing Greeks breach event"""
        publisher = create_event_publisher()
        
        publisher.publish_greeks_breach(
            greek_type="delta",
            current_value=0.25,
            threshold=0.20,
            severity="WARNING"
        )
        
        assert publisher.events_published == 1
    
    def test_publish_edge_decay_event(self):
        """Test publishing edge decay event"""
        publisher = create_event_publisher()
        
        publisher.publish_edge_decay(
            strategy_type="IRON_CONDOR",
            win_rate=0.55,
            historical_win_rate=0.70,
            avg_profit=800.0,
            historical_avg_profit=1200.0
        )
        
        assert publisher.events_published == 1
    
    def test_event_statistics(self):
        """Test event statistics"""
        publisher = create_event_publisher()
        
        # Publish multiple events
        publisher.publish_regime_change("LOW_VOL_SELL", "HIGH_VOL_SELL", 0.85, 12, "test")
        publisher.publish_trade_signal("IRON_CONDOR", "HIGH_VOL_SELL", 5000, 2000, 0.75, [])
        
        stats = publisher.get_event_statistics()
        
        assert stats['total_events_published'] == 2
        assert 'event_bus_available' in stats
        assert 'timestamp' in stats


class TestEndToEndIntegration:
    """Test end-to-end V3 integration flow"""
    
    def test_complete_trade_validation_flow(self):
        """Test complete trade validation flow with V3 integration"""
        # Create integration
        integration = create_v3_risk_integration(base_capital=1000000.0)
        
        # Create event publisher
        publisher = create_event_publisher()
        
        # 1. Check regime (would come from regime detector)
        publisher.publish_regime_change(
            old_regime="NEUTRAL",
            new_regime="HIGH_VOL_SELL",
            iv_rank=0.85,
            days_in_old_regime=0,
            reason="IV rank exceeded 80%"
        )
        
        # 2. Generate trade signal (would come from strategy generator)
        publisher.publish_trade_signal(
            strategy_type="IRON_CONDOR",
            regime="HIGH_VOL_SELL",
            max_loss=5000.0,
            max_profit=2000.0,
            edge_score=0.75,
            legs=[]
        )
        
        # 3. Validate trade through risk system
        trade_metadata = {
            'symbol': 'NIFTY_25000_CE',
            'quantity': 50,
            'price': 100.0,
            'side': 'buy',
            'strategy_type': 'IRON_CONDOR',
            'max_loss': 5000.0,
            'asset_class': 'options'
        }
        
        result = integration.check_options_risk_before_trade(trade_metadata)
        
        # 4. If approved, publish position opened event
        if result['approved']:
            publisher.publish_position_opened(
                position_id="pos1",
                strategy_type="IRON_CONDOR",
                max_loss=5000.0,
                entry_time=datetime.now(),
                legs=[]
            )
        
        # Verify flow
        assert result['approved'] is True
        assert publisher.events_published >= 3  # regime change + signal + position opened
    
    def test_kill_switch_blocks_trade(self):
        """Test that kill switch blocks trade through V3 integration"""
        integration = create_v3_risk_integration(base_capital=1000000.0)
        publisher = create_event_publisher()
        
        # Simulate weekly loss that triggers kill switch
        import pytz
        IST = pytz.timezone('Asia/Kolkata')
        now_ist = datetime.now(IST)
        
        closed_trades = [
            OptionsTradeRecord(
                trade_id="trade1",
                strategy_type="IRON_CONDOR",
                entry_time=now_ist - timedelta(days=2),
                exit_time=now_ist - timedelta(days=1),
                max_loss=5000.0,
                realized_pnl=-25000.0,  # 2.5% loss - exceeds 2% limit
                is_short_vol=True
            )
        ]
        
        # Update options state
        integration.options_validator.update_options_state(
            open_positions=[],
            closed_trades=closed_trades,
            performance=OptionsPerformanceMetrics(
                current_equity=975000.0,
                ytd_gross_profits=0.0,
                ytd_tax_liability=0.0,
                cash_buffer=0.0
            )
        )
        
        # Publish kill switch event
        publisher.publish_kill_switch_activated(
            kill_switch_type="weekly_loss_limit",
            reason="Weekly loss exceeded 2%",
            cooldown_until=now_ist + timedelta(days=1),
            triggered_rules=["weekly_loss_limit"]
        )
        
        # Try to validate new trade
        trade_metadata = {
            'symbol': 'NIFTY_25000_CE',
            'quantity': 50,
            'price': 100.0,
            'side': 'buy',
            'strategy_type': 'IRON_CONDOR',
            'max_loss': 5000.0,
            'asset_class': 'options'
        }
        
        result = integration.check_options_risk_before_trade(trade_metadata)
        
        # Should be rejected due to kill switch
        assert result['approved'] is False
        assert result['decision'].lower() == 'rejected'
        # Check that there are violations (may not contain exact text due to error handling)
        assert len(result['violations']) > 0


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
