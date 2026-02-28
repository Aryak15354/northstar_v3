#!/usr/bin/env python3
"""
Unit Tests for Risk Authority Emergency Actions

Tests emergency triggers, responses, position liquidation selection,
and audit trail completeness.

Validates Requirements 8.3, 8.4, 8.6
"""

import pytest
from datetime import datetime, timedelta
from src.volatility.risk_authority import (
    UnifiedRiskAuthority,
    RiskLimits,
    RiskAction
)


class TestEmergencyTriggers:
    """Test emergency action triggers"""
    
    def test_crisis_volatility_trigger(self):
        """Test emergency actions triggered by high volatility"""
        authority = UnifiedRiskAuthority()
        
        market_conditions = {
            'volatility': 0.40,  # Above crisis threshold (0.35)
            'drawdown': 0.10
        }
        
        portfolio = {
            'positions': {},
            'total_value': 1000000
        }
        
        actions = authority.get_emergency_actions(market_conditions, portfolio)
        
        # Should have emergency actions
        assert len(actions) > 0, "High volatility should trigger emergency actions"
        
        # Should include position reduction
        reduce_actions = [a for a in actions if a['action'] == RiskAction.REDUCE_POSITIONS.value]
        assert len(reduce_actions) > 0, "Should include position reduction action"
    
    def test_crisis_drawdown_trigger(self):
        """Test emergency actions triggered by large drawdown"""
        authority = UnifiedRiskAuthority()
        
        market_conditions = {
            'volatility': 0.20,
            'drawdown': 0.20  # Above crisis threshold (0.15)
        }
        
        portfolio = {
            'positions': {},
            'total_value': 1000000
        }
        
        actions = authority.get_emergency_actions(market_conditions, portfolio)
        
        # Should have emergency actions
        assert len(actions) > 0, "Large drawdown should trigger emergency actions"
        
        # Should include position reduction
        reduce_actions = [a for a in actions if a['action'] == RiskAction.REDUCE_POSITIONS.value]
        assert len(reduce_actions) > 0, "Should include position reduction action"
    
    def test_emergency_stop_loss_trigger(self):
        """Test emergency stop-loss liquidation"""
        authority = UnifiedRiskAuthority()
        
        market_conditions = {
            'volatility': 0.20,
            'drawdown': 0.30  # Above emergency stop-loss (0.25)
        }
        
        portfolio = {
            'positions': {
                'AAPL': {'weight': 0.10, 'return': -0.15, 'volatility': 0.25, 'beta': 1.2,
                        'daily_volume': 1000000, 'bid_ask_spread': 0.01},
                'GOOGL': {'weight': 0.08, 'return': -0.20, 'volatility': 0.30, 'beta': 1.1,
                         'daily_volume': 800000, 'bid_ask_spread': 0.015}
            },
            'total_value': 1000000
        }
        
        actions = authority.get_emergency_actions(market_conditions, portfolio)
        
        # Should have liquidation action
        liquidate_actions = [a for a in actions if a['action'] == RiskAction.LIQUIDATE.value]
        assert len(liquidate_actions) > 0, "Emergency stop-loss should trigger liquidation"
        
        # Should have positions to liquidate
        liquidate_action = liquidate_actions[0]
        assert 'positions_to_liquidate' in liquidate_action, "Should specify positions to liquidate"
        assert len(liquidate_action['positions_to_liquidate']) > 0, "Should select positions for liquidation"
    
    def test_no_emergency_in_normal_conditions(self):
        """Test no emergency actions in normal market conditions"""
        authority = UnifiedRiskAuthority()
        
        market_conditions = {
            'volatility': 0.15,  # Normal volatility
            'drawdown': 0.05     # Small drawdown
        }
        
        portfolio = {
            'positions': {},
            'total_value': 1000000
        }
        
        actions = authority.get_emergency_actions(market_conditions, portfolio)
        
        # Should have no emergency actions
        assert len(actions) == 0, "Normal conditions should not trigger emergency actions"


class TestPositionLiquidationSelection:
    """Test position selection for liquidation"""
    
    def test_liquidation_prioritizes_high_risk(self):
        """Test that high-risk positions are selected first"""
        authority = UnifiedRiskAuthority()
        
        portfolio = {
            'positions': {
                'LOW_RISK': {
                    'weight': 0.05,
                    'return': 0.10,
                    'volatility': 0.15,
                    'beta': 0.8,
                    'daily_volume': 2000000,
                    'bid_ask_spread': 0.005
                },
                'HIGH_RISK': {
                    'weight': 0.10,
                    'return': -0.15,
                    'volatility': 0.40,
                    'beta': 1.5,
                    'daily_volume': 500000,
                    'bid_ask_spread': 0.03
                }
            },
            'total_value': 1000000
        }
        
        positions = authority.select_liquidation_positions(portfolio, target_reduction=0.10)
        
        # Should select at least one position
        assert len(positions) > 0, "Should select positions for liquidation"
        
        # High-risk position should be selected first
        first_position = positions[0]
        assert first_position['symbol'] == 'HIGH_RISK', \
            "High-risk position should be prioritized for liquidation"
    
    def test_liquidation_prioritizes_underperformers(self):
        """Test that underperforming positions are selected"""
        authority = UnifiedRiskAuthority()
        
        portfolio = {
            'positions': {
                'WINNER': {
                    'weight': 0.08,
                    'return': 0.20,
                    'volatility': 0.20,
                    'beta': 1.0,
                    'daily_volume': 1000000,
                    'bid_ask_spread': 0.01
                },
                'LOSER': {
                    'weight': 0.08,
                    'return': -0.25,
                    'volatility': 0.20,
                    'beta': 1.0,
                    'daily_volume': 1000000,
                    'bid_ask_spread': 0.01
                }
            },
            'total_value': 1000000
        }
        
        positions = authority.select_liquidation_positions(portfolio, target_reduction=0.08)
        
        # Should select at least one position
        assert len(positions) > 0, "Should select positions for liquidation"
        
        # Losing position should be selected first
        first_position = positions[0]
        assert first_position['symbol'] == 'LOSER', \
            "Underperforming position should be prioritized"
    
    def test_liquidation_achieves_target_reduction(self):
        """Test that liquidation selection achieves target reduction"""
        authority = UnifiedRiskAuthority()
        
        portfolio = {
            'positions': {
                'POS1': {'weight': 0.10, 'return': 0, 'volatility': 0.20, 'beta': 1.0,
                        'daily_volume': 1000000, 'bid_ask_spread': 0.01},
                'POS2': {'weight': 0.10, 'return': 0, 'volatility': 0.20, 'beta': 1.0,
                        'daily_volume': 1000000, 'bid_ask_spread': 0.01},
                'POS3': {'weight': 0.10, 'return': 0, 'volatility': 0.20, 'beta': 1.0,
                        'daily_volume': 1000000, 'bid_ask_spread': 0.01}
            },
            'total_value': 1000000
        }
        
        target_reduction = 0.20  # 20% reduction
        positions = authority.select_liquidation_positions(portfolio, target_reduction)
        
        # Calculate actual reduction
        total_exposure = sum(abs(p['weight']) for p in portfolio['positions'].values())
        selected_exposure = sum(p['position_size'] for p in positions)
        actual_reduction = selected_exposure / total_exposure if total_exposure > 0 else 0
        
        # Should achieve at least target reduction
        assert actual_reduction >= target_reduction * 0.9, \
            f"Should achieve target reduction. Target: {target_reduction:.2%}, Actual: {actual_reduction:.2%}"
    
    def test_liquidation_empty_portfolio(self):
        """Test liquidation selection with empty portfolio"""
        authority = UnifiedRiskAuthority()
        
        portfolio = {
            'positions': {},
            'total_value': 1000000
        }
        
        positions = authority.select_liquidation_positions(portfolio, target_reduction=0.50)
        
        # Should return empty list
        assert len(positions) == 0, "Empty portfolio should return no positions to liquidate"


class TestEmergencyOverride:
    """Test emergency override functionality"""
    
    def test_emergency_override_activation(self):
        """Test emergency override can be activated"""
        authority = UnifiedRiskAuthority()
        
        result = authority.trigger_emergency_override(
            exposure_cap=0.50,
            triggered_by='test_system',
            reason='testing emergency override'
        )
        
        assert result is True, "Emergency override should activate successfully"
        assert authority.emergency_active is True, "Emergency should be active"
        assert authority.emergency_cap == 0.50, "Emergency cap should be set"
    
    def test_emergency_override_enforcement(self):
        """Test emergency override is enforced in trade validation"""
        authority = UnifiedRiskAuthority()
        
        # Activate emergency override
        authority.trigger_emergency_override(
            exposure_cap=0.40,
            triggered_by='test',
            reason='testing'
        )
        
        # Try to trade above cap
        trade = {
            'symbol': 'TEST',
            'size': 0.50,  # Above 0.40 cap
            'value': 100000,
            'sector': 'Technology',
            'delta': 10,
            'gamma': 1,
            'vega': 5,
            'theta': -0.5,
            'margin_required': 50000,
            'daily_volume': 1000000,
            'quantity': 1000,
            'bid_ask_spread': 0.01
        }
        
        portfolio = {
            'total_value': 1000000,
            'cash': 500000,
            'margin_used': 100000,
            'delta': 0,
            'gamma': 0,
            'vega': 0,
            'theta': 0,
            'positions': {}
        }
        
        result = authority.validate_trade(trade, portfolio)
        
        # Should be rejected
        assert not result.approved, "Trade above emergency cap should be rejected"
    
    def test_emergency_override_clearing(self):
        """Test emergency override can be cleared"""
        authority = UnifiedRiskAuthority()
        
        # Activate override
        authority.trigger_emergency_override(
            exposure_cap=0.50,
            triggered_by='test',
            reason='testing'
        )
        
        assert authority.emergency_active is True
        
        # Clear override
        result = authority.clear_emergency_override(
            cleared_by='operator',
            reason='crisis resolved'
        )
        
        assert result is True, "Emergency override should clear successfully"
        assert authority.emergency_active is False, "Emergency should be inactive"
        assert authority.emergency_cap == 1.0, "Emergency cap should be reset"


class TestAuditTrail:
    """Test audit trail completeness"""
    
    def test_trade_validation_logged(self):
        """Test trade validation is logged to audit trail"""
        authority = UnifiedRiskAuthority()
        
        initial_count = len(authority.audit_trail)
        
        trade = {
            'symbol': 'TEST',
            'size': 0.05,
            'value': 50000,
            'sector': 'Technology',
            'delta': 5,
            'gamma': 1,
            'vega': 3,
            'theta': -0.2,
            'margin_required': 25000,
            'daily_volume': 1000000,
            'quantity': 500,
            'bid_ask_spread': 0.01
        }
        
        portfolio = {
            'total_value': 1000000,
            'cash': 500000,
            'margin_used': 100000,
            'delta': 0,
            'gamma': 0,
            'vega': 0,
            'theta': 0,
            'positions': {}
        }
        
        authority.validate_trade(trade, portfolio)
        
        # Audit trail should have new entry
        assert len(authority.audit_trail) > initial_count, \
            "Trade validation should be logged"
        
        # Last entry should be trade_validation
        last_entry = authority.audit_trail[-1]
        assert last_entry['action'] == 'trade_validation', \
            "Last entry should be trade_validation"
    
    def test_emergency_actions_logged(self):
        """Test emergency actions are logged"""
        authority = UnifiedRiskAuthority()
        
        initial_count = len(authority.audit_trail)
        
        market_conditions = {
            'volatility': 0.40,
            'drawdown': 0.20
        }
        
        portfolio = {
            'positions': {},
            'total_value': 1000000
        }
        
        authority.get_emergency_actions(market_conditions, portfolio)
        
        # Should have audit entry
        assert len(authority.audit_trail) > initial_count, \
            "Emergency actions should be logged"
    
    def test_emergency_override_logged(self):
        """Test emergency override is logged"""
        authority = UnifiedRiskAuthority()
        
        initial_count = len(authority.audit_trail)
        
        authority.trigger_emergency_override(
            exposure_cap=0.50,
            triggered_by='test',
            reason='testing'
        )
        
        # Should have audit entry
        assert len(authority.audit_trail) > initial_count, \
            "Emergency override should be logged"
        
        # Should have emergency_override entry
        override_entries = [e for e in authority.audit_trail 
                          if e['action'] == 'emergency_override']
        assert len(override_entries) > 0, "Should have emergency_override entry"
    
    def test_escalation_logged(self):
        """Test escalations are logged to audit trail"""
        authority = UnifiedRiskAuthority()
        
        initial_count = len(authority.audit_trail)
        
        escalation = authority.escalate_to_human(
            issue_type='test_issue',
            severity='HIGH',
            details={'test': 'data'},
            requires_approval=False
        )
        
        # Should have audit entry
        assert len(authority.audit_trail) > initial_count, \
            "Escalation should be logged"
        
        # Should have escalation entry
        escalation_entries = [e for e in authority.audit_trail 
                            if e['action'] == 'escalation']
        assert len(escalation_entries) > 0, "Should have escalation entry"
    
    def test_audit_trail_retrieval(self):
        """Test audit trail can be retrieved"""
        authority = UnifiedRiskAuthority()
        
        # Generate some audit entries
        for i in range(5):
            authority._audit_log(f'test_action_{i}', {'index': i})
        
        # Retrieve audit trail
        trail = authority.get_audit_trail(last_n=3)
        
        # Should return last 3 entries
        assert len(trail) == 3, "Should return requested number of entries"


class TestEscalation:
    """Test escalation to human oversight"""
    
    def test_escalation_creation(self):
        """Test escalation can be created"""
        authority = UnifiedRiskAuthority()
        
        escalation = authority.escalate_to_human(
            issue_type='systematic_violations',
            severity='HIGH',
            details={'violation_count': 10},
            requires_approval=True
        )
        
        assert 'escalation_id' in escalation, "Should have escalation ID"
        assert escalation['status'] == 'PENDING', "Should be pending"
        assert escalation['severity'] == 'HIGH', "Should have correct severity"
    
    def test_critical_escalation_halts_trading(self):
        """Test critical escalation triggers emergency override"""
        authority = UnifiedRiskAuthority()
        
        assert authority.emergency_active is False
        
        authority.escalate_to_human(
            issue_type='critical_issue',
            severity='CRITICAL',
            details={'test': 'data'},
            requires_approval=True
        )
        
        # Should activate emergency override
        assert authority.emergency_active is True, \
            "Critical escalation should activate emergency override"
    
    def test_escalation_resolution(self):
        """Test escalation can be resolved"""
        authority = UnifiedRiskAuthority()
        
        # Create escalation
        escalation = authority.escalate_to_human(
            issue_type='test_issue',
            severity='MEDIUM',
            details={'test': 'data'},
            requires_approval=False
        )
        
        escalation_id = escalation['escalation_id']
        
        # Resolve escalation
        result = authority.resolve_escalation(
            escalation_id=escalation_id,
            resolved_by='operator',
            resolution='Issue resolved',
            approved=True
        )
        
        assert result is True, "Escalation should be resolved successfully"
    
    def test_systematic_violations_escalation(self):
        """Test systematic violations trigger escalation"""
        authority = UnifiedRiskAuthority()
        
        # Create multiple violations of same parameter
        for i in range(10):
            from src.volatility.risk_authority import RiskViolation
            violation = RiskViolation(
                parameter='max_delta',
                current_value=150,
                limit_value=100,
                severity='HIGH',
                timestamp=datetime.now(),
                description='Test violation'
            )
            authority.violations.append(violation)
        
        # Check for systematic violations
        escalation = authority.check_systematic_violations(lookback_hours=24)
        
        # Should trigger escalation
        assert escalation is not None, "Systematic violations should trigger escalation"
        assert escalation['issue_type'] == 'systematic_violations', \
            "Should be systematic violations escalation"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
