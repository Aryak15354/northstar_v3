"""
Risk Coordinator Tests

Tests for the hierarchical risk authority system including position-level,
portfolio-level, and system-level risk validation.
"""

import pytest
from datetime import datetime
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from risk.risk_coordinator import (
    RiskCoordinator, RiskLimit, RiskLevel, RiskDecision,
    Trade, Position, Portfolio, RiskMetrics
)


class TestRiskLimits:
    """Test risk limit definitions and validation"""
    
    def test_risk_limit_creation(self):
        """Test risk limit creation"""
        limit = RiskLimit(
            name="max_position_size",
            level=RiskLevel.POSITION,
            limit_type="percentage",
            threshold=0.10,
            warning_threshold=0.08
        )
        
        assert limit.name == "max_position_size"
        assert limit.level == RiskLevel.POSITION
        assert limit.threshold == 0.10
        assert limit.warning_threshold == 0.08
        assert limit.active == True
    
    def test_risk_limit_hierarchy(self):
        """Test risk limit hierarchy levels"""
        position_limit = RiskLimit("pos_limit", RiskLevel.POSITION, "pct", 0.05)
        portfolio_limit = RiskLimit("port_limit", RiskLevel.PORTFOLIO, "abs", 10000)
        system_limit = RiskLimit("sys_limit", RiskLevel.SYSTEM, "pct", 0.15)
        
        assert position_limit.level == RiskLevel.POSITION
        assert portfolio_limit.level == RiskLevel.PORTFOLIO
        assert system_limit.level == RiskLevel.SYSTEM


class TestTradeValidation:
    """Test trade validation through risk hierarchy"""
    
    def create_test_portfolio(self) -> Portfolio:
        """Create test portfolio"""
        positions = [
            Position("STOCK_A", 1000, 100000, 5000, "Tech", "US", "USD"),
            Position("STOCK_B", 500, 50000, -2000, "Finance", "US", "USD"),
            Position("STOCK_C", 800, 80000, 3000, "Healthcare", "US", "USD")
        ]
        return Portfolio(positions, 20000, 250000, datetime.now())
    
    def create_test_limits(self) -> list:
        """Create test risk limits"""
        return [
            RiskLimit("max_position_size", RiskLevel.POSITION, "pct", 0.20),
            RiskLimit("max_sector_concentration", RiskLevel.POSITION, "pct", 0.40),
            RiskLimit("max_portfolio_var", RiskLevel.PORTFOLIO, "abs", 15000),
            RiskLimit("max_leverage", RiskLevel.PORTFOLIO, "ratio", 1.5),
            RiskLimit("max_drawdown", RiskLevel.SYSTEM, "pct", 0.10)
        ]
    
    def test_position_level_validation_pass(self):
        """Test position-level validation that should pass"""
        limits = self.create_test_limits()
        coordinator = RiskCoordinator(limits)
        portfolio = self.create_test_portfolio()
        
        # Small trade that should pass all limits
        trade = Trade("STOCK_D", 100, 50.0, "buy", "market", datetime.now())
        metrics = coordinator.calculate_risk_metrics(portfolio)
        
        decision, violations = coordinator.validate_trade(trade, portfolio, metrics)
        
        assert decision == RiskDecision.APPROVED
        assert len(violations) == 0
    
    def test_position_level_validation_fail(self):
        """Test position-level validation that should fail"""
        limits = self.create_test_limits()
        coordinator = RiskCoordinator(limits)
        portfolio = self.create_test_portfolio()
        
        # Large trade that exceeds position size limit
        trade = Trade("STOCK_A", 2000, 100.0, "buy", "market", datetime.now(),
                     metadata={"sector": "Tech"})
        metrics = coordinator.calculate_risk_metrics(portfolio)
        
        decision, violations = coordinator.validate_trade(trade, portfolio, metrics)
        
        # Should be rejected due to position size
        assert decision == RiskDecision.REJECTED
        assert len(violations) > 0
        assert any("position size" in v.description.lower() for v in violations)
    
    def test_portfolio_level_validation(self):
        """Test portfolio-level risk validation"""
        limits = self.create_test_limits()
        coordinator = RiskCoordinator(limits)
        portfolio = self.create_test_portfolio()
        
        # Create metrics that exceed portfolio VaR limit
        metrics = RiskMetrics(
            timestamp=datetime.now(),
            portfolio_var=20000,  # Exceeds 15000 limit
            portfolio_cvar=25000,
            gross_exposure=1.2,
            net_exposure=0.9,
            leverage=1.2,
            max_drawdown=0.05,
            sector_concentrations={"Tech": 0.4, "Finance": 0.2, "Healthcare": 0.3},
            position_concentrations={"STOCK_A": 0.4, "STOCK_B": 0.2, "STOCK_C": 0.3}
        )
        
        trade = Trade("STOCK_E", 100, 50.0, "buy", "market", datetime.now())
        decision, violations = coordinator.validate_trade(trade, portfolio, metrics)
        
        # Should be rejected due to VaR breach
        assert decision == RiskDecision.REJECTED
        assert any("var" in v.description.lower() for v in violations)
    
    def test_system_level_validation(self):
        """Test system-level risk validation"""
        limits = self.create_test_limits()
        coordinator = RiskCoordinator(limits)
        portfolio = self.create_test_portfolio()
        
        # Create metrics that exceed system drawdown limit
        metrics = RiskMetrics(
            timestamp=datetime.now(),
            portfolio_var=10000,
            portfolio_cvar=12000,
            gross_exposure=1.0,
            net_exposure=0.9,
            leverage=1.0,
            max_drawdown=0.15,  # Exceeds 10% limit
            sector_concentrations={"Tech": 0.4, "Finance": 0.2, "Healthcare": 0.3},
            position_concentrations={"STOCK_A": 0.4, "STOCK_B": 0.2, "STOCK_C": 0.3}
        )
        
        trade = Trade("STOCK_F", 100, 50.0, "buy", "market", datetime.now())
        decision, violations = coordinator.validate_trade(trade, portfolio, metrics)
        
        # Should be rejected due to drawdown breach
        assert decision == RiskDecision.REJECTED
        assert any("drawdown" in v.description.lower() for v in violations)


class TestRiskMetricsCalculation:
    """Test risk metrics calculation"""
    
    def test_risk_metrics_calculation(self):
        """Test basic risk metrics calculation"""
        limits = [RiskLimit("test", RiskLevel.POSITION, "pct", 0.1)]
        coordinator = RiskCoordinator(limits)
        
        positions = [
            Position("STOCK_A", 1000, 100000, 5000, "Tech", "US", "USD"),
            Position("STOCK_B", 500, 50000, -2000, "Finance", "US", "USD")
        ]
        portfolio = Portfolio(positions, 50000, 200000, datetime.now())
        
        metrics = coordinator.calculate_risk_metrics(portfolio)
        
        assert metrics.gross_exposure > 0
        assert metrics.net_exposure >= 0
        assert metrics.leverage > 0
        assert len(metrics.sector_concentrations) > 0
        assert len(metrics.position_concentrations) > 0
    
    def test_sector_concentration_calculation(self):
        """Test sector concentration calculation"""
        limits = [RiskLimit("test", RiskLevel.POSITION, "pct", 0.1)]
        coordinator = RiskCoordinator(limits)
        
        positions = [
            Position("TECH_1", 1000, 80000, 0, "Tech", "US", "USD"),
            Position("TECH_2", 500, 40000, 0, "Tech", "US", "USD"),
            Position("FINANCE_1", 800, 80000, 0, "Finance", "US", "USD")
        ]
        portfolio = Portfolio(positions, 0, 200000, datetime.now())
        
        metrics = coordinator.calculate_risk_metrics(portfolio)
        
        # Tech should be 60% (120k/200k), Finance should be 40% (80k/200k)
        assert abs(metrics.sector_concentrations["Tech"] - 0.6) < 0.01
        assert abs(metrics.sector_concentrations["Finance"] - 0.4) < 0.01


class TestRiskCoordinatorIntegration:
    """Test risk coordinator integration and workflows"""
    
    def test_risk_summary_generation(self):
        """Test comprehensive risk summary generation"""
        limits = [
            RiskLimit("max_position_size", RiskLevel.POSITION, "pct", 0.20),
            RiskLimit("max_leverage", RiskLevel.PORTFOLIO, "ratio", 1.5)
        ]
        coordinator = RiskCoordinator(limits)
        
        positions = [Position("STOCK_A", 1000, 100000, 5000, "Tech", "US", "USD")]
        portfolio = Portfolio(positions, 100000, 200000, datetime.now())
        
        summary = coordinator.get_risk_summary(portfolio)
        
        assert 'timestamp' in summary
        assert 'metrics' in summary
        assert 'violations' in summary
        assert 'risk_score' in summary
        assert 'status' in summary
        assert summary['status'] in ['HEALTHY', 'WARNING', 'CRITICAL']
    
    def test_risk_limit_updates(self):
        """Test dynamic risk limit updates"""
        initial_limits = [RiskLimit("test_limit", RiskLevel.POSITION, "pct", 0.10)]
        coordinator = RiskCoordinator(initial_limits)
        
        # Update limits
        new_limits = [RiskLimit("test_limit", RiskLevel.POSITION, "pct", 0.05)]
        coordinator.update_risk_limits(new_limits)
        
        # Verify limits were updated
        assert coordinator.risk_limits[0].threshold == 0.05
    
    def test_multiple_violation_handling(self):
        """Test handling of multiple simultaneous violations"""
        limits = [
            RiskLimit("max_position_size", RiskLevel.POSITION, "pct", 0.10),
            RiskLimit("max_leverage", RiskLevel.PORTFOLIO, "ratio", 1.2),
            RiskLimit("max_drawdown", RiskLevel.SYSTEM, "pct", 0.05)
        ]
        coordinator = RiskCoordinator(limits)
        
        # Create portfolio that violates multiple limits
        positions = [Position("STOCK_A", 1000, 150000, 0, "Tech", "US", "USD")]
        portfolio = Portfolio(positions, 0, 200000, datetime.now())
        
        # Create metrics that violate system limits
        metrics = RiskMetrics(
            timestamp=datetime.now(),
            portfolio_var=10000,
            portfolio_cvar=12000,
            gross_exposure=0.75,
            net_exposure=0.75,
            leverage=1.5,  # Exceeds 1.2 limit
            max_drawdown=0.08,  # Exceeds 0.05 limit
            sector_concentrations={"Tech": 0.75},
            position_concentrations={"STOCK_A": 0.75}  # Exceeds 0.10 limit
        )
        
        trade = Trade("STOCK_A", 100, 150.0, "buy", "market", datetime.now())
        decision, violations = coordinator.validate_trade(trade, portfolio, metrics)
        
        # Should be rejected with multiple violations
        assert decision == RiskDecision.REJECTED
        assert len(violations) >= 2  # Multiple violations expected


class TestRiskValidatorHierarchy:
    """Test risk validator hierarchy and escalation"""
    
    def test_validator_hierarchy_order(self):
        """Test that validators are called in correct hierarchy order"""
        limits = [
            RiskLimit("pos_limit", RiskLevel.POSITION, "pct", 0.20),
            RiskLimit("port_limit", RiskLevel.PORTFOLIO, "abs", 15000),
            RiskLimit("sys_limit", RiskLevel.SYSTEM, "pct", 0.10)
        ]
        coordinator = RiskCoordinator(limits)
        
        # Verify validators exist for each level
        assert RiskLevel.POSITION in coordinator.validators
        assert RiskLevel.PORTFOLIO in coordinator.validators
        assert RiskLevel.SYSTEM in coordinator.validators
    
    def test_most_restrictive_decision_wins(self):
        """Test that most restrictive decision takes precedence"""
        limits = [
            RiskLimit("lenient_limit", RiskLevel.POSITION, "pct", 0.50),  # Lenient
            RiskLimit("strict_limit", RiskLevel.PORTFOLIO, "abs", 1),     # Very strict
        ]
        coordinator = RiskCoordinator(limits)
        
        positions = [Position("STOCK_A", 1000, 100000, 0, "Tech", "US", "USD")]
        portfolio = Portfolio(positions, 0, 200000, datetime.now())
        
        # Create metrics that pass position level but fail portfolio level
        metrics = RiskMetrics(
            timestamp=datetime.now(),
            portfolio_var=10,  # Exceeds strict limit of 1
            portfolio_cvar=12,
            gross_exposure=0.5,  # Within position limit
            net_exposure=0.5,
            leverage=1.0,
            max_drawdown=0.02,
            sector_concentrations={"Tech": 0.5},
            position_concentrations={"STOCK_A": 0.5}
        )
        
        trade = Trade("STOCK_B", 100, 50.0, "buy", "market", datetime.now())
        decision, violations = coordinator.validate_trade(trade, portfolio, metrics)
        
        # Should be rejected due to strict portfolio limit
        assert decision == RiskDecision.REJECTED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])