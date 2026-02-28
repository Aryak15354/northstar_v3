#!/usr/bin/env python3
"""
Property-Based Tests for Risk Authority Validation

Tests Property 8: Risk authority rejects limit violations
Validates Requirements 8.1, 8.2
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime
from src.volatility.risk_authority import (
    UnifiedRiskAuthority,
    RiskLimits,
    TradeValidationResult
)


# ============================================================================
# TEST STRATEGIES
# ============================================================================

@st.composite
def trade_strategy(draw):
    """Generate random trade proposals"""
    return {
        'symbol': draw(st.text(min_size=1, max_size=10, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ')),
        'size': draw(st.floats(min_value=0.0, max_value=1.0)),
        'value': draw(st.floats(min_value=1000, max_value=1000000)),
        'sector': draw(st.sampled_from(['Technology', 'Finance', 'Healthcare', 'Energy', 'Consumer'])),
        'delta': draw(st.floats(min_value=-200, max_value=200)),
        'gamma': draw(st.floats(min_value=-100, max_value=100)),
        'vega': draw(st.floats(min_value=-300, max_value=300)),
        'theta': draw(st.floats(min_value=-50, max_value=50)),
        'margin_required': draw(st.floats(min_value=0, max_value=500000)),
        'daily_volume': draw(st.floats(min_value=0, max_value=10000000)),
        'quantity': draw(st.floats(min_value=1, max_value=10000)),
        'bid_ask_spread': draw(st.floats(min_value=0.001, max_value=0.10))
    }


@st.composite
def portfolio_strategy(draw):
    """Generate random portfolio states"""
    return {
        'total_value': draw(st.floats(min_value=100000, max_value=10000000)),
        'cash': draw(st.floats(min_value=10000, max_value=5000000)),
        'margin_used': draw(st.floats(min_value=0, max_value=2000000)),
        'delta': draw(st.floats(min_value=-100, max_value=100)),
        'gamma': draw(st.floats(min_value=-50, max_value=50)),
        'vega': draw(st.floats(min_value=-200, max_value=200)),
        'theta': draw(st.floats(min_value=-20, max_value=20)),
        'positions': {}
    }


# ============================================================================
# PROPERTY 8: RISK AUTHORITY REJECTS LIMIT VIOLATIONS
# ============================================================================

class TestProperty8RiskAuthorityRejectsViolations:
    """
    Property 8: Risk authority rejects limit violations
    
    For any proposed trade that would breach risk limits,
    the Risk Authority should reject it.
    
    Validates: Requirements 8.1, 8.2
    """
    
    @given(
        trade=trade_strategy(),
        portfolio=portfolio_strategy()
    )
    @settings(max_examples=50, deadline=None)
    def test_position_size_limit_rejection(self, trade, portfolio):
        """Property: Trades exceeding position size limits are rejected"""
        authority = UnifiedRiskAuthority()
        
        # Force trade to violate position size limit
        trade['size'] = authority.limits.max_position_size + 0.01
        
        result = authority.validate_trade(trade, portfolio)
        
        # Should be rejected
        assert not result.approved, "Trade exceeding position size limit should be rejected"
        
        # Should have position size violation
        position_violations = [v for v in result.violations if v.parameter == 'max_position_size']
        assert len(position_violations) > 0, "Should have position size violation"
    
    @given(
        trade=trade_strategy(),
        portfolio=portfolio_strategy()
    )
    @settings(max_examples=50, deadline=None)
    def test_greeks_limit_rejection(self, trade, portfolio):
        """Property: Trades exceeding Greeks limits are rejected"""
        authority = UnifiedRiskAuthority()
        
        # Force trade to violate delta limit
        portfolio['delta'] = 0
        trade['delta'] = authority.limits.max_delta + 10
        
        result = authority.validate_trade(trade, portfolio)
        
        # Should be rejected
        assert not result.approved, "Trade exceeding delta limit should be rejected"
        
        # Should have delta violation
        delta_violations = [v for v in result.violations if v.parameter == 'max_delta']
        assert len(delta_violations) > 0, "Should have delta violation"
    
    @given(
        trade=trade_strategy(),
        portfolio=portfolio_strategy()
    )
    @settings(max_examples=50, deadline=None)
    def test_margin_requirement_rejection(self, trade, portfolio):
        """Property: Trades with insufficient margin are rejected"""
        authority = UnifiedRiskAuthority()
        
        # Force insufficient margin
        portfolio['cash'] = 10000
        portfolio['margin_used'] = 5000
        trade['margin_required'] = 10000  # Requires more than available
        
        result = authority.validate_trade(trade, portfolio)
        
        # Should be rejected
        assert not result.approved, "Trade with insufficient margin should be rejected"
        
        # Should have margin violation
        margin_violations = [v for v in result.violations 
                           if 'margin' in v.parameter.lower()]
        assert len(margin_violations) > 0, "Should have margin violation"
    
    @given(
        trade=trade_strategy(),
        portfolio=portfolio_strategy()
    )
    @settings(max_examples=50, deadline=None)
    def test_valid_trade_approval(self, trade, portfolio):
        """Property: Trades within all limits are approved"""
        authority = UnifiedRiskAuthority()
        
        # Ensure trade is within all limits
        trade['size'] = 0.05  # Well below max_position_size
        trade['delta'] = 10
        trade['gamma'] = 5
        trade['vega'] = 20
        trade['theta'] = -1
        trade['margin_required'] = 1000
        trade['daily_volume'] = 500000
        trade['bid_ask_spread'] = 0.01
        
        portfolio['delta'] = 0
        portfolio['gamma'] = 0
        portfolio['vega'] = 0
        portfolio['theta'] = 0
        portfolio['cash'] = 100000
        portfolio['margin_used'] = 10000
        
        result = authority.validate_trade(trade, portfolio)
        
        # Should be approved
        assert result.approved, f"Valid trade should be approved. Violations: {result.violations}"
    
    @given(
        trade=trade_strategy(),
        portfolio=portfolio_strategy(),
        regime=st.sampled_from(['crisis', 'high-vol', 'low-vol', 'transition'])
    )
    @settings(max_examples=50, deadline=None)
    def test_regime_conditional_limits(self, trade, portfolio, regime):
        """Property: Risk limits adapt to regime"""
        authority = UnifiedRiskAuthority()
        
        # Update regime limits
        authority.update_regime_limits(regime)
        
        # Get regime-specific max position
        regime_config = authority.regime_limits.get(regime, {})
        max_position = regime_config.get('max_position', authority.limits.max_position_size)
        
        # Force trade to violate regime-specific limit
        trade['size'] = max_position + 0.01
        
        result = authority.validate_trade(trade, portfolio, regime=regime)
        
        # Should be rejected
        assert not result.approved, f"Trade exceeding {regime} regime limit should be rejected"
    
    @given(
        trade=trade_strategy(),
        portfolio=portfolio_strategy()
    )
    @settings(max_examples=30, deadline=None)
    def test_emergency_override_enforcement(self, trade, portfolio):
        """Property: Emergency override caps are enforced"""
        authority = UnifiedRiskAuthority()
        
        # Trigger emergency override with 50% cap
        authority.trigger_emergency_override(
            exposure_cap=0.50,
            triggered_by='test',
            reason='testing'
        )
        
        # Try to trade above emergency cap
        trade['size'] = 0.60
        
        result = authority.validate_trade(trade, portfolio)
        
        # Should be rejected
        assert not result.approved, "Trade exceeding emergency cap should be rejected"
        
        # Should have exposure violation
        exposure_violations = [v for v in result.violations 
                             if 'exposure' in v.parameter.lower()]
        assert len(exposure_violations) > 0, "Should have exposure violation"
    
    @given(
        trade=trade_strategy(),
        portfolio=portfolio_strategy()
    )
    @settings(max_examples=30, deadline=None)
    def test_liquidity_validation(self, trade, portfolio):
        """Property: Illiquid trades are rejected or warned"""
        authority = UnifiedRiskAuthority()
        
        # Force low liquidity
        trade['daily_volume'] = 50000  # Below min_daily_volume
        trade['size'] = 0.05
        
        result = authority.validate_trade(trade, portfolio)
        
        # Should have liquidity violation or warning
        liquidity_violations = [v for v in result.violations 
                              if 'volume' in v.parameter.lower()]
        
        # Either rejected or has warnings
        assert (not result.approved or len(result.warnings) > 0), \
            "Illiquid trade should be rejected or warned"


# ============================================================================
# ADDITIONAL PROPERTY TESTS
# ============================================================================

class TestRiskAuthorityInvariants:
    """Test invariants that should always hold"""
    
    @given(
        trade=trade_strategy(),
        portfolio=portfolio_strategy()
    )
    @settings(max_examples=50, deadline=None)
    def test_rejection_has_violations(self, trade, portfolio):
        """Property: Rejected trades always have violations"""
        authority = UnifiedRiskAuthority()
        
        result = authority.validate_trade(trade, portfolio)
        
        if not result.approved:
            assert len(result.violations) > 0, \
                "Rejected trade must have at least one violation"
    
    @given(
        trade=trade_strategy(),
        portfolio=portfolio_strategy()
    )
    @settings(max_examples=50, deadline=None)
    def test_approval_has_no_violations(self, trade, portfolio):
        """Property: Approved trades have no violations"""
        authority = UnifiedRiskAuthority()
        
        result = authority.validate_trade(trade, portfolio)
        
        if result.approved:
            assert len(result.violations) == 0, \
                "Approved trade must have zero violations"
    
    @given(
        trade=trade_strategy(),
        portfolio=portfolio_strategy()
    )
    @settings(max_examples=30, deadline=None)
    def test_audit_trail_completeness(self, trade, portfolio):
        """Property: All validations are logged to audit trail"""
        authority = UnifiedRiskAuthority()
        
        initial_audit_count = len(authority.audit_trail)
        
        authority.validate_trade(trade, portfolio)
        
        # Audit trail should have new entry
        assert len(authority.audit_trail) > initial_audit_count, \
            "Trade validation should be logged to audit trail"
        
        # Last entry should be trade_validation
        last_entry = authority.audit_trail[-1]
        assert last_entry['action'] == 'trade_validation', \
            "Last audit entry should be trade_validation"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
