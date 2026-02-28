"""
Risk Coordinator - Hierarchical Risk Authority System

This module implements the central risk authority system with absolute veto power
over all investment decisions, providing multi-layered risk validation and control.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Union, Tuple
from dataclasses import dataclass
from enum import Enum
import logging


class RiskLevel(Enum):
    """Risk authority levels"""
    POSITION = "position"
    PORTFOLIO = "portfolio"
    SYSTEM = "system"
    REGULATORY = "regulatory"


class RiskDecision(Enum):
    """Risk decision outcomes"""
    APPROVED = "approved"
    REJECTED = "rejected"
    CONDITIONAL = "conditional"
    ESCALATED = "escalated"


@dataclass
class RiskLimit:
    """Risk limit definition"""
    name: str
    level: RiskLevel
    limit_type: str
    threshold: float
    warning_threshold: Optional[float] = None
    currency: str = "USD"
    active: bool = True


@dataclass
class RiskMetrics:
    """Current risk metrics"""
    timestamp: datetime
    portfolio_var: float
    portfolio_cvar: float
    gross_exposure: float
    net_exposure: float
    leverage: float
    max_drawdown: float
    sector_concentrations: Dict[str, float]
    position_concentrations: Dict[str, float]


@dataclass
class RiskViolation:
    """Risk limit violation"""
    limit_name: str
    current_value: float
    threshold: float
    severity: str
    timestamp: datetime
    description: str


@dataclass
class Trade:
    """Trade representation for risk validation"""
    symbol: str
    quantity: float
    price: float
    side: str  # 'buy' or 'sell'
    trade_type: str
    timestamp: datetime
    metadata: Optional[Dict] = None


@dataclass
class Position:
    """Position representation"""
    symbol: str
    quantity: float
    market_value: float
    unrealized_pnl: float
    sector: str
    country: str
    currency: str


@dataclass
class Portfolio:
    """Portfolio representation"""
    positions: List[Position]
    cash: float
    total_value: float
    timestamp: datetime


class RiskValidator(ABC):
    """Abstract base class for risk validators"""
    
    @abstractmethod
    def validate(self, trade: Trade, portfolio: Portfolio, metrics: RiskMetrics) -> Tuple[RiskDecision, List[RiskViolation]]:
        """Validate trade against risk criteria"""
        pass
    
    @abstractmethod
    def get_risk_level(self) -> RiskLevel:
        """Get the risk level this validator operates at"""
        pass


class PositionRiskValidator(RiskValidator):
    """Position-level risk validation"""
    
    def __init__(self, limits: List[RiskLimit]):
        self.limits = {limit.name: limit for limit in limits if limit.level == RiskLevel.POSITION}
        self.logger = logging.getLogger(__name__)
    
    def validate(self, trade: Trade, portfolio: Portfolio, metrics: RiskMetrics) -> Tuple[RiskDecision, List[RiskViolation]]:
        """Validate position-level risk constraints"""
        violations = []
        
        # Calculate new position after trade
        current_position = self._get_current_position(trade.symbol, portfolio)
        new_quantity = current_position.quantity + (trade.quantity if trade.side == 'buy' else -trade.quantity)
        new_market_value = new_quantity * trade.price
        
        # Check position size limits
        if 'max_position_size' in self.limits:
            limit = self.limits['max_position_size']
            position_pct = abs(new_market_value) / portfolio.total_value
            
            if position_pct > limit.threshold:
                violations.append(RiskViolation(
                    limit_name=limit.name,
                    current_value=position_pct,
                    threshold=limit.threshold,
                    severity='ERROR',
                    timestamp=datetime.now(),
                    description=f"Position size {position_pct:.2%} exceeds limit {limit.threshold:.2%}"
                ))
        
        # Check concentration limits
        if 'max_sector_concentration' in self.limits:
            limit = self.limits['max_sector_concentration']
            sector_exposure = self._calculate_sector_exposure_after_trade(trade, portfolio)
            
            if trade.metadata and 'sector' in trade.metadata:
                sector = trade.metadata['sector']
                if sector in sector_exposure and sector_exposure[sector] > limit.threshold:
                    violations.append(RiskViolation(
                        limit_name=limit.name,
                        current_value=sector_exposure[sector],
                        threshold=limit.threshold,
                        severity='WARNING',
                        timestamp=datetime.now(),
                        description=f"Sector concentration {sector_exposure[sector]:.2%} exceeds limit"
                    ))
        
        # Determine decision
        if any(v.severity == 'ERROR' for v in violations):
            return RiskDecision.REJECTED, violations
        elif violations:
            return RiskDecision.CONDITIONAL, violations
        else:
            return RiskDecision.APPROVED, violations
    
    def get_risk_level(self) -> RiskLevel:
        return RiskLevel.POSITION
    
    def _get_current_position(self, symbol: str, portfolio: Portfolio) -> Position:
        """Get current position for symbol"""
        for position in portfolio.positions:
            if position.symbol == symbol:
                return position
        
        # Return empty position if not found
        return Position(
            symbol=symbol,
            quantity=0.0,
            market_value=0.0,
            unrealized_pnl=0.0,
            sector='Unknown',
            country='Unknown',
            currency='USD'
        )
    
    def _calculate_sector_exposure_after_trade(self, trade: Trade, portfolio: Portfolio) -> Dict[str, float]:
        """Calculate sector exposures after trade execution"""
        # Simplified implementation - would be more complex in practice
        sector_exposures = {}
        
        for position in portfolio.positions:
            sector = position.sector
            if sector not in sector_exposures:
                sector_exposures[sector] = 0.0
            sector_exposures[sector] += abs(position.market_value) / portfolio.total_value
        
        return sector_exposures


class PortfolioRiskValidator(RiskValidator):
    """Portfolio-level risk validation"""
    
    def __init__(self, limits: List[RiskLimit]):
        self.limits = {limit.name: limit for limit in limits if limit.level == RiskLevel.PORTFOLIO}
        self.logger = logging.getLogger(__name__)
    
    def validate(self, trade: Trade, portfolio: Portfolio, metrics: RiskMetrics) -> Tuple[RiskDecision, List[RiskViolation]]:
        """Validate portfolio-level risk constraints"""
        violations = []
        
        # Check VaR limits
        if 'max_portfolio_var' in self.limits:
            limit = self.limits['max_portfolio_var']
            if metrics.portfolio_var > limit.threshold:
                violations.append(RiskViolation(
                    limit_name=limit.name,
                    current_value=metrics.portfolio_var,
                    threshold=limit.threshold,
                    severity='ERROR',
                    timestamp=datetime.now(),
                    description=f"Portfolio VaR {metrics.portfolio_var:.2f} exceeds limit {limit.threshold:.2f}"
                ))
        
        # Check leverage limits
        if 'max_leverage' in self.limits:
            limit = self.limits['max_leverage']
            if metrics.leverage > limit.threshold:
                violations.append(RiskViolation(
                    limit_name=limit.name,
                    current_value=metrics.leverage,
                    threshold=limit.threshold,
                    severity='ERROR',
                    timestamp=datetime.now(),
                    description=f"Leverage {metrics.leverage:.2f} exceeds limit {limit.threshold:.2f}"
                ))
        
        # Check gross exposure limits
        if 'max_gross_exposure' in self.limits:
            limit = self.limits['max_gross_exposure']
            if metrics.gross_exposure > limit.threshold:
                violations.append(RiskViolation(
                    limit_name=limit.name,
                    current_value=metrics.gross_exposure,
                    threshold=limit.threshold,
                    severity='WARNING',
                    timestamp=datetime.now(),
                    description=f"Gross exposure {metrics.gross_exposure:.2%} exceeds limit"
                ))
        
        # Determine decision
        if any(v.severity == 'ERROR' for v in violations):
            return RiskDecision.REJECTED, violations
        elif violations:
            return RiskDecision.CONDITIONAL, violations
        else:
            return RiskDecision.APPROVED, violations
    
    def get_risk_level(self) -> RiskLevel:
        return RiskLevel.PORTFOLIO


class SystemRiskValidator(RiskValidator):
    """System-level risk validation"""
    
    def __init__(self, limits: List[RiskLimit]):
        self.limits = {limit.name: limit for limit in limits if limit.level == RiskLevel.SYSTEM}
        self.logger = logging.getLogger(__name__)
    
    def validate(self, trade: Trade, portfolio: Portfolio, metrics: RiskMetrics) -> Tuple[RiskDecision, List[RiskViolation]]:
        """Validate system-level risk constraints"""
        violations = []
        
        # Check maximum drawdown limits
        if 'max_drawdown' in self.limits:
            limit = self.limits['max_drawdown']
            if metrics.max_drawdown > limit.threshold:
                violations.append(RiskViolation(
                    limit_name=limit.name,
                    current_value=metrics.max_drawdown,
                    threshold=limit.threshold,
                    severity='ERROR',
                    timestamp=datetime.now(),
                    description=f"Max drawdown {metrics.max_drawdown:.2%} exceeds limit {limit.threshold:.2%}"
                ))
        
        # System health checks would go here
        # - Market connectivity
        # - Data quality
        # - System performance
        
        # Determine decision
        if any(v.severity == 'ERROR' for v in violations):
            return RiskDecision.REJECTED, violations
        elif violations:
            return RiskDecision.CONDITIONAL, violations
        else:
            return RiskDecision.APPROVED, violations
    
    def get_risk_level(self) -> RiskLevel:
        return RiskLevel.SYSTEM


class RiskCoordinator:
    """
    Central risk authority with hierarchical validation
    
    The RiskCoordinator implements a hierarchical risk management system where
    each level has the authority to reject trades. Risk validation proceeds
    from position level through portfolio, system, and regulatory levels.
    """
    
    def __init__(self, risk_limits: List[RiskLimit]):
        self.validators: Dict[RiskLevel, RiskValidator] = {}
        self.risk_limits = risk_limits
        self.logger = logging.getLogger(__name__)
        
        # Initialize validators
        self._initialize_validators()
    
    def _initialize_validators(self) -> None:
        """Initialize risk validators for each level"""
        self.validators[RiskLevel.POSITION] = PositionRiskValidator(self.risk_limits)
        self.validators[RiskLevel.PORTFOLIO] = PortfolioRiskValidator(self.risk_limits)
        self.validators[RiskLevel.SYSTEM] = SystemRiskValidator(self.risk_limits)
        # Regulatory validator would be added here
    
    def validate_trade(self, trade: Trade, portfolio: Portfolio, metrics: RiskMetrics) -> Tuple[RiskDecision, List[RiskViolation]]:
        """
        Validate trade through hierarchical risk authority
        
        Returns the most restrictive decision from all risk levels
        """
        all_violations = []
        final_decision = RiskDecision.APPROVED
        
        # Validate through each risk level
        for level in [RiskLevel.POSITION, RiskLevel.PORTFOLIO, RiskLevel.SYSTEM]:
            if level in self.validators:
                decision, violations = self.validators[level].validate(trade, portfolio, metrics)
                all_violations.extend(violations)
                
                # Most restrictive decision wins
                if decision == RiskDecision.REJECTED:
                    final_decision = RiskDecision.REJECTED
                elif decision == RiskDecision.CONDITIONAL and final_decision == RiskDecision.APPROVED:
                    final_decision = RiskDecision.CONDITIONAL
                elif decision == RiskDecision.ESCALATED:
                    final_decision = RiskDecision.ESCALATED
        
        self.logger.info(f"Trade validation result: {final_decision.value} with {len(all_violations)} violations")
        
        return final_decision, all_violations
    
    def check_portfolio_limits(self, portfolio: Portfolio, metrics: RiskMetrics) -> List[RiskViolation]:
        """Check current portfolio against all risk limits"""
        all_violations = []
        
        # Create dummy trade for validation
        dummy_trade = Trade(
            symbol="DUMMY",
            quantity=0.0,
            price=0.0,
            side="buy",
            trade_type="validation",
            timestamp=datetime.now()
        )
        
        for validator in self.validators.values():
            _, violations = validator.validate(dummy_trade, portfolio, metrics)
            all_violations.extend(violations)
        
        return all_violations
    
    def calculate_risk_metrics(self, portfolio: Portfolio) -> RiskMetrics:
        """Calculate current portfolio risk metrics"""
        # Simplified implementation - would be much more complex in practice
        total_value = portfolio.total_value
        gross_exposure = sum(abs(pos.market_value) for pos in portfolio.positions) / total_value
        net_exposure = sum(pos.market_value for pos in portfolio.positions) / total_value
        leverage = gross_exposure
        
        # Sector concentrations
        sector_concentrations = {}
        for position in portfolio.positions:
            sector = position.sector
            if sector not in sector_concentrations:
                sector_concentrations[sector] = 0.0
            sector_concentrations[sector] += abs(position.market_value) / total_value
        
        # Position concentrations
        position_concentrations = {}
        for position in portfolio.positions:
            position_concentrations[position.symbol] = abs(position.market_value) / total_value
        
        return RiskMetrics(
            timestamp=datetime.now(),
            portfolio_var=0.0,  # Would be calculated using risk model
            portfolio_cvar=0.0,  # Would be calculated using risk model
            gross_exposure=gross_exposure,
            net_exposure=net_exposure,
            leverage=leverage,
            max_drawdown=0.0,  # Would be calculated from performance history
            sector_concentrations=sector_concentrations,
            position_concentrations=position_concentrations
        )
    
    def update_risk_limits(self, new_limits: List[RiskLimit]) -> None:
        """Update risk limits and reinitialize validators"""
        self.risk_limits = new_limits
        self._initialize_validators()
        self.logger.info(f"Updated risk limits: {len(new_limits)} limits active")
    
    def get_risk_summary(self, portfolio: Portfolio) -> Dict[str, any]:
        """Get comprehensive risk summary"""
        metrics = self.calculate_risk_metrics(portfolio)
        violations = self.check_portfolio_limits(portfolio, metrics)
        
        return {
            'timestamp': datetime.now(),
            'metrics': metrics,
            'violations': violations,
            'risk_score': self._calculate_risk_score(metrics, violations),
            'status': 'HEALTHY' if not violations else 'WARNING' if all(v.severity != 'ERROR' for v in violations) else 'CRITICAL'
        }
    
    def _calculate_risk_score(self, metrics: RiskMetrics, violations: List[RiskViolation]) -> float:
        """Calculate overall risk score (0-100, higher is riskier)"""
        base_score = 0.0
        
        # Add score based on leverage
        base_score += min(metrics.leverage * 10, 30)
        
        # Add score based on concentration
        max_concentration = max(metrics.position_concentrations.values()) if metrics.position_concentrations else 0
        base_score += max_concentration * 50
        
        # Add score based on violations
        violation_score = len([v for v in violations if v.severity == 'ERROR']) * 20
        violation_score += len([v for v in violations if v.severity == 'WARNING']) * 5
        
        return min(base_score + violation_score, 100.0)