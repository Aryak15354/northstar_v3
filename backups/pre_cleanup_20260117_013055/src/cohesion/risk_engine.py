"""
Risk Engine Implementation for Northstar V3 System Cohesion

This module implements the comprehensive risk management system with invariants
that enforce capital conservation, crisis de-risking, and risk-of-ruin protection.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np
from dataclasses import dataclass

from src.service_interfaces import IRiskEngine, ValidationResult, IConfigurationManager, IStateManager
from src.risk_authority import RiskAuthority, AuthorityLevel

logger = logging.getLogger(__name__)

@dataclass
class PortfolioMetrics:
    """Portfolio risk metrics"""
    total_exposure: float
    gross_exposure: float
    net_exposure: float
    sector_exposures: Dict[str, float]
    position_sizes: Dict[str, float]
    volatility: float
    var_95: float
    max_drawdown: float
    sharpe_ratio: float
    correlation_matrix: Optional[pd.DataFrame] = None

@dataclass
class RiskViolation:
    """Risk limit violation"""
    parameter: str
    current_value: float
    limit_value: float
    severity: str
    timestamp: datetime
    description: str

class RiskEngine(IRiskEngine):
    """
    Comprehensive risk management system with invariants.
    
    Implements the capital-grade risk management laws:
    - Capital Conservation (R1)
    - Crisis De-Risking (R2) 
    - Risk-of-Ruin Protection (R3)
    - Position Size Limits (R4)
    """
    
    def __init__(self, 
                 config_manager: IConfigurationManager,
                 state_manager: IStateManager,
                 risk_authority: RiskAuthority):
        self.config_manager = config_manager
        self.state_manager = state_manager
        self.risk_authority = risk_authority
        
        self.risk_violations: List[RiskViolation] = []
        self.crisis_start_date: Optional[datetime] = None
        self.pre_crisis_exposure: Optional[float] = None
        
        # Historical crisis periods for validation
        self.historical_crises = [
            {'start': datetime(2008, 9, 15), 'end': datetime(2009, 3, 9), 'name': '2008 Financial Crisis'},
            {'start': datetime(2020, 2, 20), 'end': datetime(2020, 4, 7), 'name': 'COVID-19 Crash'},
            {'start': datetime(2000, 3, 10), 'end': datetime(2002, 10, 9), 'name': 'Dot-com Crash'}
        ]
    
    def validate_position_size(self, 
                             symbol: str, 
                             size: float, 
                             portfolio: Dict[str, Any]) -> ValidationResult:
        """
        Validate position size against limits.
        
        Implements Property 16: Position Size Limits (R4)
        """
        errors = []
        warnings = []
        
        risk_params = self.risk_authority.get_risk_parameters()
        max_position_size = risk_params['max_position_size']
        
        # Check individual position size limit
        if size > max_position_size:
            errors.append(
                f"Position size {size:.2%} for {symbol} exceeds limit {max_position_size:.2%}"
            )
        
        # Check sector exposure if sector information available
        if 'sector' in portfolio.get(symbol, {}):
            sector = portfolio[symbol]['sector']
            sector_exposure = self._calculate_sector_exposure(portfolio, sector, symbol, size)
            max_sector_exposure = risk_params['max_sector_exposure']
            
            if sector_exposure > max_sector_exposure:
                errors.append(
                    f"Adding position would create sector exposure {sector_exposure:.2%} "
                    f"exceeding limit {max_sector_exposure:.2%} for sector {sector}"
                )
        
        # Check concentration risk
        concentration_limit = risk_params['concentration_limit']
        if size > concentration_limit:
            warnings.append(
                f"Position size {size:.2%} exceeds concentration guideline {concentration_limit:.2%}"
            )
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def calculate_portfolio_risk(self, portfolio: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate comprehensive portfolio risk metrics.
        
        Returns all metrics needed for risk invariant validation.
        """
        try:
            # Extract position data
            positions = portfolio.get('positions', {})
            if not positions:
                return self._empty_risk_metrics()
            
            # Calculate exposures
            total_exposure = sum(abs(pos.get('weight', 0)) for pos in positions.values())
            gross_exposure = sum(abs(pos.get('weight', 0)) for pos in positions.values())
            net_exposure = sum(pos.get('weight', 0) for pos in positions.values())
            
            # Calculate sector exposures
            sector_exposures = self._calculate_all_sector_exposures(positions)
            
            # Calculate position sizes
            position_sizes = {
                symbol: abs(pos.get('weight', 0)) 
                for symbol, pos in positions.items()
            }
            
            # Calculate volatility metrics (simplified for now)
            volatility = self._calculate_portfolio_volatility(positions)
            var_95 = volatility * 1.645  # Approximate 95% VaR
            
            # Calculate drawdown
            max_drawdown = self._calculate_max_drawdown(portfolio)
            
            # Calculate Sharpe ratio (simplified)
            returns = portfolio.get('returns', [])
            sharpe_ratio = self._calculate_sharpe_ratio(returns) if returns else 0.0
            
            return {
                'total_exposure': total_exposure,
                'gross_exposure': gross_exposure,
                'net_exposure': net_exposure,
                'sector_exposures': sector_exposures,
                'position_sizes': position_sizes,
                'volatility': volatility,
                'var_95': var_95,
                'max_drawdown': max_drawdown,
                'sharpe_ratio': sharpe_ratio,
                'largest_position': max(position_sizes.values()) if position_sizes else 0.0,
                'largest_sector': max(sector_exposures.values()) if sector_exposures else 0.0
            }
            
        except Exception as e:
            logger.error(f"Error calculating portfolio risk: {e}")
            return self._empty_risk_metrics()
    
    def check_risk_limits(self, portfolio: Dict[str, Any]) -> ValidationResult:
        """
        Check portfolio against all risk limits.
        
        Implements comprehensive risk limit validation across all invariants.
        """
        errors = []
        warnings = []
        violations = []
        
        risk_metrics = self.calculate_portfolio_risk(portfolio)
        risk_params = self.risk_authority.get_risk_parameters()
        
        # Check position size limits (Property 16: R4)
        for symbol, size in risk_metrics['position_sizes'].items():
            if size > risk_params['max_position_size']:
                violation = RiskViolation(
                    parameter='max_position_size',
                    current_value=size,
                    limit_value=risk_params['max_position_size'],
                    severity='HIGH',
                    timestamp=datetime.now(),
                    description=f"Position {symbol} size {size:.2%} exceeds limit"
                )
                violations.append(violation)
                errors.append(violation.description)
        
        # Check sector exposure limits (Property 16: R4)
        for sector, exposure in risk_metrics['sector_exposures'].items():
            if exposure > risk_params['max_sector_exposure']:
                violation = RiskViolation(
                    parameter='max_sector_exposure',
                    current_value=exposure,
                    limit_value=risk_params['max_sector_exposure'],
                    severity='HIGH',
                    timestamp=datetime.now(),
                    description=f"Sector {sector} exposure {exposure:.2%} exceeds limit"
                )
                violations.append(violation)
                errors.append(violation.description)
        
        # Check drawdown limits (Property 15: R3)
        if risk_metrics['max_drawdown'] > risk_params['max_drawdown_threshold']:
            violation = RiskViolation(
                parameter='max_drawdown_threshold',
                current_value=risk_metrics['max_drawdown'],
                limit_value=risk_params['max_drawdown_threshold'],
                severity='CRITICAL',
                timestamp=datetime.now(),
                description=f"Drawdown {risk_metrics['max_drawdown']:.2%} exceeds limit"
            )
            violations.append(violation)
            errors.append(violation.description)
        
        # Check volatility limits
        if risk_metrics['volatility'] > risk_params['volatility_threshold']:
            violation = RiskViolation(
                parameter='volatility_threshold',
                current_value=risk_metrics['volatility'],
                limit_value=risk_params['volatility_threshold'],
                severity='MEDIUM',
                timestamp=datetime.now(),
                description=f"Volatility {risk_metrics['volatility']:.2%} exceeds threshold"
            )
            violations.append(violation)
            warnings.append(violation.description)
        
        # Store violations for audit
        self.risk_violations.extend(violations)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={'violations': violations, 'risk_metrics': risk_metrics}
        )
    
    def get_emergency_actions(self, 
                            market_conditions: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get emergency risk actions for market conditions.
        
        Implements Property 14: Crisis De-Risking (R2)
        """
        actions = []
        
        market_volatility = market_conditions.get('volatility', 0.0)
        risk_params = self.risk_authority.get_risk_parameters()
        
        # Check if we're in crisis conditions
        is_crisis = market_volatility > risk_params['crisis_volatility_threshold']
        
        if is_crisis:
            # Track crisis start if not already tracking
            if self.crisis_start_date is None:
                self.crisis_start_date = datetime.now()
                current_state = self.state_manager.get_state('portfolio')
                if current_state:
                    portfolio_metrics = self.calculate_portfolio_risk(current_state)
                    self.pre_crisis_exposure = portfolio_metrics['gross_exposure']
                
                logger.warning(f"CRISIS CONDITIONS DETECTED: volatility {market_volatility:.2%}")
            
            # Calculate required de-risking
            days_since_crisis = (datetime.now() - self.crisis_start_date).days
            derisking_timeframe = risk_params.get('crisis_derisking_timeframe', 10)
            
            if days_since_crisis <= derisking_timeframe:
                target_reduction = risk_params['crisis_derisking_target']  # 40% reduction
                
                actions.append({
                    'action': 'reduce_exposure',
                    'target_reduction': target_reduction,
                    'timeframe_days': derisking_timeframe - days_since_crisis,
                    'reason': f'Crisis de-risking: volatility {market_volatility:.2%}',
                    'priority': 'HIGH'
                })
                
                actions.append({
                    'action': 'reduce_position_sizes',
                    'max_position_size': min(risk_params['max_position_size'], 0.05),  # 5% max
                    'reason': 'Crisis position size limits',
                    'priority': 'HIGH'
                })
                
                actions.append({
                    'action': 'increase_cash',
                    'target_cash_percentage': 0.30,  # 30% cash
                    'reason': 'Crisis liquidity management',
                    'priority': 'MEDIUM'
                })
        
        else:
            # Reset crisis tracking if conditions normalize
            if self.crisis_start_date is not None:
                logger.info("Crisis conditions normalized, resetting crisis tracking")
                self.crisis_start_date = None
                self.pre_crisis_exposure = None
        
        # Check for emergency stop-loss conditions
        current_state = self.state_manager.get_state('portfolio')
        if current_state:
            portfolio_metrics = self.calculate_portfolio_risk(current_state)
            emergency_threshold = risk_params['emergency_stop_loss']
            
            if portfolio_metrics['max_drawdown'] > emergency_threshold:
                actions.append({
                    'action': 'emergency_stop_loss',
                    'current_drawdown': portfolio_metrics['max_drawdown'],
                    'threshold': emergency_threshold,
                    'reason': f'Emergency stop-loss triggered: {portfolio_metrics["max_drawdown"]:.2%} drawdown',
                    'priority': 'CRITICAL'
                })
        
        return actions
    
    def validate_capital_conservation(self, 
                                   previous_nav: float, 
                                   current_nav: float,
                                   pnl: float, 
                                   costs: float) -> ValidationResult:
        """
        Validate capital conservation invariant.
        
        Implements Property 13: Capital Conservation (R1)
        For any portfolio update, capital must be conserved (no magic money)
        """
        errors = []
        warnings = []
        
        # Calculate expected NAV
        expected_nav = previous_nav + pnl - costs
        tolerance = 0.0001  # 0.01% tolerance for rounding
        
        nav_difference = abs(current_nav - expected_nav)
        relative_difference = nav_difference / previous_nav if previous_nav > 0 else 0
        
        if relative_difference > tolerance:
            errors.append(
                f"Capital conservation violation: "
                f"Expected NAV {expected_nav:.4f}, got {current_nav:.4f}, "
                f"difference {nav_difference:.4f} ({relative_difference:.4%})"
            )
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={
                'previous_nav': previous_nav,
                'current_nav': current_nav,
                'expected_nav': expected_nav,
                'pnl': pnl,
                'costs': costs,
                'difference': nav_difference,
                'relative_difference': relative_difference
            }
        )
    
    def validate_crisis_derisking(self, 
                                crisis_period: Dict[str, datetime],
                                portfolio_history: List[Dict[str, Any]]) -> ValidationResult:
        """
        Validate crisis de-risking invariant.
        
        Implements Property 14: Crisis De-Risking (R2)
        For any crisis condition, exposure must be reduced within timeframes
        """
        errors = []
        warnings = []
        
        crisis_start = crisis_period['start']
        crisis_end = crisis_period.get('end', datetime.now())
        
        # Find portfolio states during crisis
        crisis_portfolios = [
            p for p in portfolio_history 
            if crisis_start <= p.get('timestamp', datetime.min) <= crisis_end
        ]
        
        if len(crisis_portfolios) < 2:
            warnings.append("Insufficient portfolio history for crisis validation")
            return ValidationResult(is_valid=True, errors=[], warnings=warnings)
        
        # Get pre-crisis and crisis portfolios
        pre_crisis = crisis_portfolios[0]
        crisis_portfolios_sorted = sorted(crisis_portfolios, key=lambda x: x.get('timestamp', datetime.min))
        
        risk_params = self.risk_authority.get_risk_parameters()
        required_reduction = risk_params['crisis_derisking_target']  # 40%
        timeframe_days = risk_params.get('crisis_derisking_timeframe', 10)
        
        pre_crisis_metrics = self.calculate_portfolio_risk(pre_crisis)
        pre_crisis_exposure = pre_crisis_metrics['gross_exposure']
        
        # Check de-risking within timeframe
        for i, portfolio in enumerate(crisis_portfolios_sorted[1:], 1):
            days_since_crisis = (portfolio['timestamp'] - crisis_start).days
            
            if days_since_crisis <= timeframe_days:
                current_metrics = self.calculate_portfolio_risk(portfolio)
                current_exposure = current_metrics['gross_exposure']
                
                actual_reduction = (pre_crisis_exposure - current_exposure) / pre_crisis_exposure
                
                if actual_reduction < required_reduction:
                    errors.append(
                        f"Crisis de-risking insufficient at day {days_since_crisis}: "
                        f"Required {required_reduction:.1%} reduction, "
                        f"achieved {actual_reduction:.1%}"
                    )
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={
                'crisis_period': crisis_period,
                'pre_crisis_exposure': pre_crisis_exposure,
                'required_reduction': required_reduction,
                'timeframe_days': timeframe_days
            }
        )
    
    def validate_risk_of_ruin_protection(self, 
                                       portfolio_history: List[Dict[str, Any]]) -> ValidationResult:
        """
        Validate risk-of-ruin protection invariant.
        
        Implements Property 15: Risk-of-Ruin Protection (R3)
        For any crisis window, max drawdown must not exceed survival thresholds
        """
        errors = []
        warnings = []
        
        risk_params = self.risk_authority.get_risk_parameters()
        max_allowed_drawdown = risk_params['max_drawdown_threshold']  # 40%
        
        # Check drawdown during each historical crisis
        for crisis in self.historical_crises:
            crisis_portfolios = [
                p for p in portfolio_history 
                if crisis['start'] <= p.get('timestamp', datetime.min) <= crisis['end']
            ]
            
            if not crisis_portfolios:
                continue
            
            # Calculate maximum drawdown during crisis
            nav_values = [p.get('nav', 1.0) for p in crisis_portfolios]
            if len(nav_values) < 2:
                continue
            
            peak = nav_values[0]
            max_drawdown = 0.0
            
            for nav in nav_values:
                if nav > peak:
                    peak = nav
                drawdown = (peak - nav) / peak
                max_drawdown = max(max_drawdown, drawdown)
            
            if max_drawdown > max_allowed_drawdown:
                errors.append(
                    f"Risk-of-ruin violation during {crisis['name']}: "
                    f"Max drawdown {max_drawdown:.1%} exceeds limit {max_allowed_drawdown:.1%}"
                )
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            metadata={
                'max_allowed_drawdown': max_allowed_drawdown,
                'historical_crises': self.historical_crises
            }
        )
    
    def _calculate_sector_exposure(self, 
                                 portfolio: Dict[str, Any], 
                                 sector: str, 
                                 new_symbol: str = None, 
                                 new_size: float = 0.0) -> float:
        """Calculate total exposure for a sector"""
        positions = portfolio.get('positions', {})
        sector_exposure = 0.0
        
        for symbol, position in positions.items():
            if position.get('sector') == sector:
                sector_exposure += abs(position.get('weight', 0))
        
        # Add new position if specified
        if new_symbol and new_size > 0:
            sector_exposure += new_size
        
        return sector_exposure
    
    def _calculate_all_sector_exposures(self, positions: Dict[str, Any]) -> Dict[str, float]:
        """Calculate exposures for all sectors"""
        sector_exposures = {}
        
        for symbol, position in positions.items():
            sector = position.get('sector', 'Unknown')
            weight = abs(position.get('weight', 0))
            
            if sector not in sector_exposures:
                sector_exposures[sector] = 0.0
            sector_exposures[sector] += weight
        
        return sector_exposures
    
    def _calculate_portfolio_volatility(self, positions: Dict[str, Any]) -> float:
        """Calculate portfolio volatility (simplified)"""
        # This is a simplified calculation
        # In practice, would use covariance matrix and position weights
        weights = [abs(pos.get('weight', 0)) for pos in positions.values()]
        volatilities = [pos.get('volatility', 0.20) for pos in positions.values()]
        
        if not weights:
            return 0.0
        
        # Weighted average volatility (simplified)
        total_weight = sum(weights)
        if total_weight == 0:
            return 0.0
        
        weighted_vol = sum(w * v for w, v in zip(weights, volatilities)) / total_weight
        return weighted_vol
    
    def _calculate_max_drawdown(self, portfolio: Dict[str, Any]) -> float:
        """Calculate maximum drawdown from portfolio history"""
        nav_history = portfolio.get('nav_history', [])
        if len(nav_history) < 2:
            return 0.0
        
        peak = nav_history[0]
        max_drawdown = 0.0
        
        for nav in nav_history:
            if nav > peak:
                peak = nav
            drawdown = (peak - nav) / peak if peak > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)
        
        return max_drawdown
    
    def _calculate_sharpe_ratio(self, returns: List[float]) -> float:
        """Calculate Sharpe ratio"""
        if len(returns) < 2:
            return 0.0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # Assume risk-free rate of 2%
        risk_free_rate = 0.02 / 252  # Daily risk-free rate
        return (mean_return - risk_free_rate) / std_return
    
    def _empty_risk_metrics(self) -> Dict[str, float]:
        """Return empty risk metrics"""
        return {
            'total_exposure': 0.0,
            'gross_exposure': 0.0,
            'net_exposure': 0.0,
            'sector_exposures': {},
            'position_sizes': {},
            'volatility': 0.0,
            'var_95': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0,
            'largest_position': 0.0,
            'largest_sector': 0.0
        }
    
    def initialize(self) -> bool:
        """Initialize the risk engine"""
        try:
            # Validate risk authority is working
            validation_result = self.risk_authority.validate_risk_consistency()
            if not validation_result.is_valid:
                logger.error(f"Risk authority validation failed: {validation_result.errors}")
                return False
            
            logger.info("Risk engine initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize risk engine: {e}")
            return False
    
    def shutdown(self) -> bool:
        """Shutdown the risk engine"""
        logger.info("Risk engine shutdown")
        return True
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get risk engine health status"""
        recent_violations = len([
            v for v in self.risk_violations 
            if (datetime.now() - v.timestamp).seconds < 3600  # Last hour
        ])
        
        return {
            'healthy': recent_violations < 5,
            'total_violations': len(self.risk_violations),
            'recent_violations': recent_violations,
            'crisis_mode': self.crisis_start_date is not None,
            'message': f"Risk engine monitoring with {len(self.risk_violations)} total violations"
        }