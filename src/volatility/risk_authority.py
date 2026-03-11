#!/usr/bin/env python3
"""
🛡️ UNIFIED RISK AUTHORITY - VOLATILITY ENGINE
Absolute authority over all risk management decisions

This module consolidates all risk management functionality with absolute veto power:
- Trade validation with position/Greeks/concentration limits
- Emergency actions (reduce, liquidate, hedge, halt)
- Regime-conditional risk limits
- Audit trail and escalation
- Risk invariants enforcement (R1-R4)

Key Principles:
- ABSOLUTE AUTHORITY: Risk Authority has final say on all trades
- NO OVERRIDES: Emergency signals cannot be bypassed
- CAPITAL CONSERVATION: All updates preserve capital (R1)
- CRISIS DE-RISKING: Automatic exposure reduction in crisis (R2)
- RISK-OF-RUIN PROTECTION: Drawdown limits enforced (R3)
- POSITION SIZE LIMITS: Individual and sector limits (R4)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import threading
import json
import numpy as np
import pandas as pd
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================================
# ENUMS AND DATA CLASSES
# ============================================================================

class AuthorityLevel(Enum):
    """Risk parameter authority hierarchy"""
    EMERGENCY = 1      # Absolute authority - overrides everything
    OPERATOR = 2       # Manual operator override
    CONFIGURATION = 3  # Configuration file
    SYSTEM = 4         # System defaults

class RiskAction(Enum):
    """Emergency risk actions"""
    REDUCE_POSITIONS = "reduce_positions"
    LIQUIDATE = "liquidate"
    HEDGE = "hedge"
    HALT_TRADING = "halt_trading"
    INCREASE_CASH = "increase_cash"

@dataclass
class RiskLimits:
    """Risk limits configuration"""
    # Position limits
    max_position_size: float = 0.08        # 8% max single position
    max_sector_exposure: float = 0.30      # 30% max sector exposure
    concentration_limit: float = 0.20      # 20% concentration limit

    # Greeks limits
    max_delta: float = 100.0               # Max portfolio delta
    max_gamma: float = 50.0                # Max portfolio gamma
    max_vega: float = 200.0                # Max portfolio vega
    max_theta: float = -10.0               # Max negative theta per day

    # Risk metrics limits
    max_drawdown_threshold: float = 0.40   # 40% max drawdown
    volatility_threshold: float = 0.25     # 25% volatility threshold
    correlation_threshold: float = 0.70    # 70% correlation threshold
    max_leverage: float = 1.0              # 1x leverage (no leverage)

    # Margin requirements
    min_margin_ratio: float = 1.5          # 150% minimum margin ratio
    maintenance_margin_ratio: float = 1.25 # 125% maintenance margin

    # Liquidity requirements
    min_daily_volume: float = 100000       # Minimum daily volume for trading
    max_volume_participation: float = 0.05 # Max 5% of daily volume
    min_bid_ask_spread: float = 0.02       # Max 2% bid-ask spread

    # Crisis parameters
    crisis_volatility_threshold: float = 0.35
    crisis_drawdown_threshold: float = 0.15
    crisis_derisking_target: float = 0.40  # Reduce exposure by 40%
    crisis_derisking_timeframe: int = 10   # Days to achieve derisking

    # Emergency parameters
    emergency_stop_loss: float = 0.25      # 25% emergency stop loss
    emergency_max_exposure: float = 0.50   # 50% max exposure in emergency

@dataclass
class RiskValidationResult:
    """Compatibility validation result used by legacy risk tests."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RiskConfiguration:
    """Compatibility risk configuration object with consistency checks."""
    max_position_size: float = 0.08
    max_sector_exposure: float = 0.30
    max_drawdown_threshold: float = 0.40
    crisis_drawdown_threshold: float = 0.15
    emergency_max_exposure: float = 0.50

    def validate_consistency(self) -> RiskValidationResult:
        errors: List[str] = []

        # Keep position sizing feasible inside sector cap.
        if self.max_position_size * 4 > self.max_sector_exposure:
            errors.append(
                "max_position_size exceeds sector limit feasibility "
                "(max_position_size * 4 > max_sector_exposure)"
            )

        if self.crisis_drawdown_threshold >= self.max_drawdown_threshold:
            errors.append("crisis_drawdown_threshold must be below max_drawdown_threshold")

        return RiskValidationResult(
            is_valid=not errors,
            errors=errors,
            warnings=[],
            metadata={}
        )


@dataclass
class RiskViolation:
    """Risk limit violation record"""
    parameter: str
    current_value: float
    limit_value: float
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    timestamp: datetime
    description: str
    action_taken: Optional[str] = None

@dataclass
class TradeValidationResult:
    """Result of trade validation"""
    approved: bool
    violations: List[RiskViolation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    authority_level: AuthorityLevel = AuthorityLevel.SYSTEM
    reason: str = ""

# ============================================================================
# UNIFIED RISK AUTHORITY
# ============================================================================

class UnifiedRiskAuthority:
    """
    Unified Risk Authority - Absolute veto power over all trading decisions
    
    Consolidates functionality from:
    - UnifiedRiskCoordinator: Emergency actions, regime logic, absolute authority
    - RiskAuthority: Parameter management, authority hierarchy
    - RiskEngine: Invariants validation, comprehensive metrics, crisis de-risking
    
    Implements Risk Invariants:
    - R1: Capital Conservation
    - R2: Crisis De-Risking
    - R3: Risk-of-Ruin Protection
    - R4: Position Size Limits
    """
    
    def __init__(self,
                 config_file: str = "config/risk.yaml",
                 state_manager=None,
                 risk_authority=None,
                 audit_logger=None):
        """
        Initialize unified risk authority.

        Backward compatibility:
        legacy callers sometimes pass configuration/state/logger objects in the
        first positional slots (old RiskAuthority/RiskEngine signatures). Those
        objects are accepted and stored without changing core behavior.
        """
        if isinstance(config_file, str):
            resolved_config_file = config_file
            resolved_state_manager = state_manager
            resolved_audit_logger = audit_logger
            resolved_parent_authority = risk_authority
        else:
            # Legacy signature compatibility:
            #   UnifiedRiskAuthority(config_manager, audit_logger)
            #   UnifiedRiskAuthority(config_manager, state_manager, risk_authority)
            resolved_config_file = "config/risk.yaml"
            resolved_state_manager = state_manager
            resolved_audit_logger = state_manager if risk_authority is None else audit_logger
            resolved_parent_authority = risk_authority

        self.config_file = resolved_config_file
        self.state_manager = resolved_state_manager
        self.audit_logger = resolved_audit_logger
        self.parent_risk_authority = resolved_parent_authority
        self.limits = RiskLimits()
        self._lock = threading.RLock()
        
        # Authority hierarchy (lower number = higher authority)
        self._authority_hierarchy = [
            AuthorityLevel.EMERGENCY,
            AuthorityLevel.OPERATOR,
            AuthorityLevel.CONFIGURATION,
            AuthorityLevel.SYSTEM
        ]
        
        # Tracking
        self.violations: List[RiskViolation] = []
        self.audit_trail: List[Dict[str, Any]] = []
        self.crisis_start_date: Optional[datetime] = None
        self.pre_crisis_exposure: Optional[float] = None
        
        # Emergency state
        self.emergency_active = False
        self.emergency_cap = 1.0  # 100% = no restriction
        
        # Regime-conditional limits
        self.regime_limits = {
            'crisis': {'max_exposure': 0.40, 'max_position': 0.05, 'vol_target': 0.10},
            'high-vol': {'max_exposure': 0.60, 'max_position': 0.06, 'vol_target': 0.15},
            'low-vol': {'max_exposure': 1.00, 'max_position': 0.08, 'vol_target': 0.20},
            'transition': {'max_exposure': 0.70, 'max_position': 0.06, 'vol_target': 0.15}
        }

        # Parameter authority tracking for update arbitration.
        self._parameter_authority: Dict[str, AuthorityLevel] = {}

        # Legacy crisis windows used by validation/property tests.
        self.historical_crises: List[Dict[str, datetime]] = [
            {'name': 'GFC_2008', 'start': datetime(2008, 9, 1), 'end': datetime(2009, 3, 31)},
            {'name': 'COVID_2020', 'start': datetime(2020, 2, 1), 'end': datetime(2020, 5, 31)},
            {'name': 'INFLATION_2022', 'start': datetime(2022, 1, 1), 'end': datetime(2022, 12, 31)},
        ]
        
        logger.info("Unified Risk Authority initialized")
    
    # ========================================================================
    # TRADE VALIDATION (R4: Position Size Limits)
    # ========================================================================
    
    def validate_trade(self, 
                      trade: Dict[str, Any],
                      portfolio: Dict[str, Any],
                      regime: str = 'low-vol') -> TradeValidationResult:
        """
        Validate proposed trade against all risk limits.
        
        Implements R4: Position Size Limits
        
        Args:
            trade: Trade details (symbol, size, direction, greeks)
            portfolio: Current portfolio state
            regime: Current volatility regime
            
        Returns:
            TradeValidationResult with approval status and violations
        """
        with self._lock:
            violations = []
            warnings = []
            
            # Get regime-adjusted limits
            regime_config = self.regime_limits.get(regime, {})
            max_position = regime_config.get('max_position', self.limits.max_position_size)
            max_exposure = regime_config.get('max_exposure', 1.0)
            
            # Check emergency override
            if self.emergency_active:
                max_exposure = min(max_exposure, self.emergency_cap)
                warnings.append(f"Emergency cap active: {self.emergency_cap:.1%}")
            
            # 1. Position size validation
            symbol = trade.get('symbol', '')
            trade_size = abs(trade.get('size', 0))
            
            if trade_size > max_position:
                violations.append(RiskViolation(
                    parameter='max_position_size',
                    current_value=trade_size,
                    limit_value=max_position,
                    severity='HIGH',
                    timestamp=datetime.now(),
                    description=f"Trade size {trade_size:.2%} exceeds limit {max_position:.2%}"
                ))
            
            # 2. Sector exposure validation
            sector = trade.get('sector', 'Unknown')
            current_sector_exposure = self._calculate_sector_exposure(portfolio, sector)
            new_sector_exposure = current_sector_exposure + trade_size
            
            if new_sector_exposure > self.limits.max_sector_exposure:
                violations.append(RiskViolation(
                    parameter='max_sector_exposure',
                    current_value=new_sector_exposure,
                    limit_value=self.limits.max_sector_exposure,
                    severity='HIGH',
                    timestamp=datetime.now(),
                    description=f"Sector {sector} exposure {new_sector_exposure:.2%} exceeds limit"
                ))
            
            # 3. Total exposure validation
            current_exposure = self._calculate_total_exposure(portfolio)
            new_exposure = current_exposure + trade_size
            
            if new_exposure > max_exposure:
                violations.append(RiskViolation(
                    parameter='max_exposure',
                    current_value=new_exposure,
                    limit_value=max_exposure,
                    severity='CRITICAL',
                    timestamp=datetime.now(),
                    description=f"Total exposure {new_exposure:.2%} exceeds limit {max_exposure:.2%}"
                ))
            
            # 4. Greeks limits validation
            greeks_violations = self._validate_greeks(trade, portfolio)
            violations.extend(greeks_violations)
            
            # 5. Concentration validation
            if trade_size > self.limits.concentration_limit:
                warnings.append(
                    f"Trade size {trade_size:.2%} exceeds concentration guideline {self.limits.concentration_limit:.2%}"
                )
            
            # 6. Margin requirement validation
            margin_violations = self._validate_margin_requirements(trade, portfolio)
            violations.extend(margin_violations)
            
            # 7. Liquidity validation
            liquidity_violations = self._validate_liquidity(trade)
            violations.extend(liquidity_violations)
            
            # Store violations
            self.violations.extend(violations)
            
            # Audit log
            self._audit_log('trade_validation', {
                'trade': trade,
                'approved': len(violations) == 0,
                'violations': len(violations),
                'warnings': len(warnings),
                'regime': regime
            })
            
            # Determine approval
            approved = len(violations) == 0
            authority = AuthorityLevel.EMERGENCY if self.emergency_active else AuthorityLevel.SYSTEM
            
            return TradeValidationResult(
                approved=approved,
                violations=violations,
                warnings=warnings,
                authority_level=authority,
                reason=f"{'Approved' if approved else 'Rejected'} with {len(violations)} violations"
            )
    
    def _validate_greeks(self, 
                        trade: Dict[str, Any],
                        portfolio: Dict[str, Any]) -> List[RiskViolation]:
        """Validate Greeks limits"""
        violations = []
        
        # Get current portfolio Greeks
        current_delta = portfolio.get('delta', 0)
        current_gamma = portfolio.get('gamma', 0)
        current_vega = portfolio.get('vega', 0)
        current_theta = portfolio.get('theta', 0)
        
        # Get trade Greeks
        trade_delta = trade.get('delta', 0)
        trade_gamma = trade.get('gamma', 0)
        trade_vega = trade.get('vega', 0)
        trade_theta = trade.get('theta', 0)
        
        # Calculate new Greeks
        new_delta = current_delta + trade_delta
        new_gamma = current_gamma + trade_gamma
        new_vega = current_vega + trade_vega
        new_theta = current_theta + trade_theta
        
        # Check limits
        if abs(new_delta) > self.limits.max_delta:
            violations.append(RiskViolation(
                parameter='max_delta',
                current_value=abs(new_delta),
                limit_value=self.limits.max_delta,
                severity='MEDIUM',
                timestamp=datetime.now(),
                description=f"Portfolio delta {new_delta:.1f} exceeds limit"
            ))
        
        if abs(new_gamma) > self.limits.max_gamma:
            violations.append(RiskViolation(
                parameter='max_gamma',
                current_value=abs(new_gamma),
                limit_value=self.limits.max_gamma,
                severity='MEDIUM',
                timestamp=datetime.now(),
                description=f"Portfolio gamma {new_gamma:.1f} exceeds limit"
            ))
        
        if abs(new_vega) > self.limits.max_vega:
            violations.append(RiskViolation(
                parameter='max_vega',
                current_value=abs(new_vega),
                limit_value=self.limits.max_vega,
                severity='MEDIUM',
                timestamp=datetime.now(),
                description=f"Portfolio vega {new_vega:.1f} exceeds limit"
            ))
        
        if new_theta < self.limits.max_theta:
            violations.append(RiskViolation(
                parameter='max_theta',
                current_value=new_theta,
                limit_value=self.limits.max_theta,
                severity='LOW',
                timestamp=datetime.now(),
                description=f"Portfolio theta {new_theta:.1f} exceeds limit"
            ))
        
        return violations

    def _validate_margin_requirements(self,
                                     trade: Dict[str, Any],
                                     portfolio: Dict[str, Any]) -> List[RiskViolation]:
        """
        Validate margin requirements for the trade.

        Checks:
        - Initial margin ratio meets minimum requirements
        - Maintenance margin ratio is sufficient
        - Portfolio margin after trade is adequate
        """
        violations = []

        # Get trade details
        trade_value = abs(trade.get('value', 0))
        trade_margin = trade.get('margin_required', trade_value * 0.5)  # Default 50% margin

        # Get portfolio details
        portfolio_value = portfolio.get('total_value', 0)
        portfolio_cash = portfolio.get('cash', 0)
        portfolio_margin_used = portfolio.get('margin_used', 0)

        # Calculate new margin requirements
        new_margin_used = portfolio_margin_used + trade_margin
        available_margin = portfolio_cash - new_margin_used

        # Check initial margin ratio
        if portfolio_value > 0:
            margin_ratio = portfolio_value / new_margin_used if new_margin_used > 0 else float('inf')

            if margin_ratio < self.limits.min_margin_ratio:
                violations.append(RiskViolation(
                    parameter='min_margin_ratio',
                    current_value=margin_ratio,
                    limit_value=self.limits.min_margin_ratio,
                    severity='HIGH',
                    timestamp=datetime.now(),
                    description=f"Margin ratio {margin_ratio:.2f} below minimum {self.limits.min_margin_ratio:.2f}"
                ))

        # Check available margin
        if available_margin < 0:
            violations.append(RiskViolation(
                parameter='available_margin',
                current_value=available_margin,
                limit_value=0,
                severity='CRITICAL',
                timestamp=datetime.now(),
                description=f"Insufficient margin: {available_margin:.2f} shortfall"
            ))

        return violations

    def _validate_liquidity(self, trade: Dict[str, Any]) -> List[RiskViolation]:
        """
        Validate liquidity requirements for the trade.

        Checks:
        - Daily volume is sufficient
        - Trade size doesn't exceed volume participation limit
        - Bid-ask spread is within acceptable range
        """
        violations = []

        # Get trade details
        symbol = trade.get('symbol', '')
        trade_size = abs(trade.get('size', 0))
        trade_quantity = abs(trade.get('quantity', 0))

        # Get market data
        daily_volume = trade.get('daily_volume', 0)
        bid_ask_spread = trade.get('bid_ask_spread', 0)

        # Check minimum daily volume
        if daily_volume < self.limits.min_daily_volume:
            violations.append(RiskViolation(
                parameter='min_daily_volume',
                current_value=daily_volume,
                limit_value=self.limits.min_daily_volume,
                severity='MEDIUM',
                timestamp=datetime.now(),
                description=f"Daily volume {daily_volume:.0f} below minimum {self.limits.min_daily_volume:.0f}"
            ))

        # Check volume participation
        if daily_volume > 0:
            volume_participation = trade_quantity / daily_volume

            if volume_participation > self.limits.max_volume_participation:
                violations.append(RiskViolation(
                    parameter='max_volume_participation',
                    current_value=volume_participation,
                    limit_value=self.limits.max_volume_participation,
                    severity='MEDIUM',
                    timestamp=datetime.now(),
                    description=f"Volume participation {volume_participation:.2%} exceeds limit {self.limits.max_volume_participation:.2%}"
                ))

        # Check bid-ask spread
        if bid_ask_spread > self.limits.min_bid_ask_spread:
            violations.append(RiskViolation(
                parameter='min_bid_ask_spread',
                current_value=bid_ask_spread,
                limit_value=self.limits.min_bid_ask_spread,
                severity='LOW',
                timestamp=datetime.now(),
                description=f"Bid-ask spread {bid_ask_spread:.2%} exceeds limit {self.limits.min_bid_ask_spread:.2%}"
            ))

        return violations

    
    # ========================================================================
    # EMERGENCY ACTIONS (R2: Crisis De-Risking)
    # ========================================================================
    
    def get_emergency_actions(self, 
                            market_conditions: Dict[str, Any],
                            portfolio: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Determine emergency actions based on market conditions.
        
        Implements R2: Crisis De-Risking
        
        Args:
            market_conditions: Current market state (volatility, drawdown, etc.)
            portfolio: Current portfolio state
            
        Returns:
            List of emergency actions to take
        """
        with self._lock:
            actions = []
            
            market_volatility = market_conditions.get('volatility', 0.0)
            portfolio_drawdown = abs(market_conditions.get('drawdown', 0.0))
            
            # Check crisis conditions
            is_crisis = (
                market_volatility > self.limits.crisis_volatility_threshold or
                portfolio_drawdown > self.limits.crisis_drawdown_threshold
            )
            
            if is_crisis:
                # Track crisis start
                if self.crisis_start_date is None:
                    self.crisis_start_date = datetime.now()
                    self.pre_crisis_exposure = self._calculate_total_exposure(portfolio)
                    logger.warning(f"CRISIS DETECTED: vol={market_volatility:.2%}, dd={portfolio_drawdown:.2%}")
                
                # Calculate required de-risking
                days_since_crisis = (datetime.now() - self.crisis_start_date).days
                
                if days_since_crisis <= self.limits.crisis_derisking_timeframe:
                    target_reduction = self.limits.crisis_derisking_target
                    
                    actions.append({
                        'action': RiskAction.REDUCE_POSITIONS.value,
                        'target_reduction': target_reduction,
                        'timeframe_days': self.limits.crisis_derisking_timeframe - days_since_crisis,
                        'reason': f'Crisis de-risking: vol={market_volatility:.2%}',
                        'priority': 'HIGH'
                    })
                    
                    actions.append({
                        'action': RiskAction.INCREASE_CASH.value,
                        'target_cash_percentage': 0.30,
                        'reason': 'Crisis liquidity management',
                        'priority': 'MEDIUM'
                    })
            else:
                # Reset crisis tracking
                if self.crisis_start_date is not None:
                    logger.info("Crisis conditions normalized")
                    self.crisis_start_date = None
                    self.pre_crisis_exposure = None
            
            # Check emergency stop-loss (R3: Risk-of-Ruin Protection)
            if portfolio_drawdown > self.limits.emergency_stop_loss:
                # Select positions for liquidation
                liquidation_positions = self.select_liquidation_positions(
                    portfolio,
                    target_reduction=0.50  # Liquidate 50% of portfolio
                )
                
                actions.append({
                    'action': RiskAction.LIQUIDATE.value,
                    'current_drawdown': portfolio_drawdown,
                    'threshold': self.limits.emergency_stop_loss,
                    'positions_to_liquidate': liquidation_positions,
                    'reason': f'Emergency stop-loss: {portfolio_drawdown:.2%} drawdown',
                    'priority': 'CRITICAL'
                })
            
            # Audit log
            if actions:
                self._audit_log('emergency_actions', {
                    'actions_count': len(actions),
                    'market_volatility': market_volatility,
                    'portfolio_drawdown': portfolio_drawdown,
                    'is_crisis': is_crisis
                })
            
            return actions
    
    def trigger_emergency_override(self, 
                                  exposure_cap: float,
                                  triggered_by: str,
                                  reason: str) -> bool:
        """
        Trigger emergency risk override with absolute authority.
        
        Args:
            exposure_cap: Maximum allowed exposure (0.0 to 1.0)
            triggered_by: Who/what triggered the override
            reason: Reason for emergency override
            
        Returns:
            True if override applied successfully
        """
        with self._lock:
            self.emergency_active = True
            self.emergency_cap = max(0.0, min(1.0, exposure_cap))
            
            logger.critical(f"EMERGENCY OVERRIDE: {triggered_by} - {reason}")
            logger.critical(f"Exposure capped at {self.emergency_cap:.1%}")
            
            self._audit_log('emergency_override', {
                'exposure_cap': self.emergency_cap,
                'triggered_by': triggered_by,
                'reason': reason,
                'authority_level': AuthorityLevel.EMERGENCY.name
            })
            
            return True
    
    def clear_emergency_override(self, cleared_by: str, reason: str) -> bool:
        """Clear emergency override"""
        with self._lock:
            self.emergency_active = False
            self.emergency_cap = 1.0
            
            logger.info(f"Emergency override cleared by {cleared_by}: {reason}")
            
            self._audit_log('emergency_cleared', {
                'cleared_by': cleared_by,
                'reason': reason
            })
            
            return True

    def select_liquidation_positions(self,
                                    portfolio: Dict[str, Any],
                                    target_reduction: float) -> List[Dict[str, Any]]:
        """
        Select positions for liquidation to achieve target exposure reduction.

        Selection criteria (in order of priority):
        1. Positions with highest risk contribution
        2. Positions with worst performance
        3. Positions with lowest liquidity
        4. Largest positions (to reduce concentration)

        Args:
            portfolio: Current portfolio state
            target_reduction: Target exposure reduction (0.0 to 1.0)

        Returns:
            List of positions to liquidate with priority scores
        """
        positions = portfolio.get('positions', {})

        if not positions:
            return []

        # Score each position for liquidation priority
        liquidation_candidates = []

        for symbol, position in positions.items():
            # Calculate risk contribution (simplified)
            position_size = abs(position.get('weight', 0))
            position_volatility = position.get('volatility', 0.20)
            position_beta = position.get('beta', 1.0)
            risk_contribution = position_size * position_volatility * abs(position_beta)

            # Calculate performance score (negative = underperforming)
            position_return = position.get('return', 0)

            # Calculate liquidity score (lower = less liquid)
            daily_volume = position.get('daily_volume', 0)
            bid_ask_spread = position.get('bid_ask_spread', 0.01)
            liquidity_score = daily_volume / (1 + bid_ask_spread * 100)

            # Calculate concentration score (higher = more concentrated)
            concentration_score = position_size

            # Composite liquidation priority score (higher = liquidate first)
            priority_score = (
                risk_contribution * 0.4 +           # 40% weight on risk
                (-position_return) * 0.3 +          # 30% weight on performance
                (-liquidity_score / 1000000) * 0.2 + # 20% weight on liquidity
                concentration_score * 0.1           # 10% weight on concentration
            )

            liquidation_candidates.append({
                'symbol': symbol,
                'position_size': position_size,
                'risk_contribution': risk_contribution,
                'return': position_return,
                'liquidity_score': liquidity_score,
                'priority_score': priority_score,
                'position_data': position
            })

        # Sort by priority score (highest first)
        liquidation_candidates.sort(key=lambda x: x['priority_score'], reverse=True)

        # Select positions until target reduction is achieved
        selected_positions = []
        cumulative_reduction = 0.0
        total_exposure = self._calculate_total_exposure(portfolio)

        for candidate in liquidation_candidates:
            if cumulative_reduction >= target_reduction:
                break

            selected_positions.append(candidate)
            cumulative_reduction += candidate['position_size'] / total_exposure if total_exposure > 0 else 0

        # Log liquidation selection
        self._audit_log('liquidation_selection', {
            'target_reduction': target_reduction,
            'positions_selected': len(selected_positions),
            'cumulative_reduction': cumulative_reduction,
            'symbols': [p['symbol'] for p in selected_positions]
        })

        return selected_positions

    def update_regime_limits(self, new_regime: str, previous_regime: Optional[str] = None) -> Dict[str, Any]:
        """
        Update risk limits based on regime change.

        Automatically adjusts limits when regime changes to adapt risk management
        to current market conditions.

        Args:
            new_regime: New volatility regime (crisis, high-vol, low-vol, transition)
            previous_regime: Previous regime (for transition tracking)

        Returns:
            Dictionary with old and new limits
        """
        with self._lock:
            # Get current limits
            old_limits = {
                'max_position_size': self.limits.max_position_size,
                'max_sector_exposure': self.limits.max_sector_exposure,
                'max_delta': self.limits.max_delta,
                'max_vega': self.limits.max_vega
            }

            # Get regime-specific configuration
            regime_config = self.regime_limits.get(new_regime, {})

            # Update position limits based on regime
            if new_regime == 'crisis':
                # Crisis: Tighten all limits significantly
                self.limits.max_position_size = regime_config.get('max_position', 0.05)
                self.limits.max_sector_exposure = 0.20  # Reduce sector concentration
                self.limits.max_delta = 50.0  # Reduce directional exposure
                self.limits.max_vega = 100.0  # Reduce volatility exposure
                self.limits.max_leverage = 0.5  # Reduce leverage

            elif new_regime == 'high-vol':
                # High volatility: Moderate restrictions
                self.limits.max_position_size = regime_config.get('max_position', 0.06)
                self.limits.max_sector_exposure = 0.25
                self.limits.max_delta = 75.0
                self.limits.max_vega = 150.0
                self.limits.max_leverage = 0.75

            elif new_regime == 'low-vol':
                # Low volatility: Normal limits
                self.limits.max_position_size = regime_config.get('max_position', 0.08)
                self.limits.max_sector_exposure = 0.30
                self.limits.max_delta = 100.0
                self.limits.max_vega = 200.0
                self.limits.max_leverage = 1.0

            elif new_regime == 'transition':
                # Transition: Defensive positioning
                self.limits.max_position_size = regime_config.get('max_position', 0.06)
                self.limits.max_sector_exposure = 0.25
                self.limits.max_delta = 60.0  # Reduce directional bets
                self.limits.max_vega = 150.0
                self.limits.max_leverage = 0.75

            # Get new limits
            new_limits = {
                'max_position_size': self.limits.max_position_size,
                'max_sector_exposure': self.limits.max_sector_exposure,
                'max_delta': self.limits.max_delta,
                'max_vega': self.limits.max_vega
            }

            # Log regime change
            logger.info(f"Regime change: {previous_regime} -> {new_regime}")
            logger.info(f"Limits updated: {old_limits} -> {new_limits}")

            self._audit_log('regime_change', {
                'previous_regime': previous_regime,
                'new_regime': new_regime,
                'old_limits': old_limits,
                'new_limits': new_limits
            })

            return {
                'previous_regime': previous_regime,
                'new_regime': new_regime,
                'old_limits': old_limits,
                'new_limits': new_limits
            }

    def get_regime_limits(self, regime: str) -> Dict[str, float]:
        """
        Get risk limits for a specific regime without changing current limits.

        Args:
            regime: Volatility regime to query

        Returns:
            Dictionary of limits for the regime
        """
        return self.regime_limits.get(regime, {})

    def escalate_to_human(self,
                         issue_type: str,
                         severity: str,
                         details: Dict[str, Any],
                         requires_approval: bool = True) -> Dict[str, Any]:
        """
        Escalate risk issue to human oversight.

        Used when:
        - Critical violations occur repeatedly
        - Emergency actions need human approval
        - System detects anomalous behavior
        - Risk limits are systematically breached

        Args:
            issue_type: Type of issue (violation, emergency, anomaly, systematic)
            severity: Severity level (CRITICAL, HIGH, MEDIUM, LOW)
            details: Detailed information about the issue
            requires_approval: Whether human approval is required to proceed

        Returns:
            Escalation record with tracking ID
        """
        with self._lock:
            escalation_id = f"ESC-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

            escalation = {
                'escalation_id': escalation_id,
                'timestamp': datetime.now().isoformat(),
                'issue_type': issue_type,
                'severity': severity,
                'details': details,
                'requires_approval': requires_approval,
                'status': 'PENDING',
                'resolved_at': None,
                'resolved_by': None,
                'resolution': None
            }

            # Log escalation
            logger.critical(f"ESCALATION TO HUMAN: {escalation_id} - {issue_type} ({severity})")
            logger.critical(f"Details: {details}")

            self._audit_log('escalation', escalation)

            # If critical, halt trading until resolved
            if severity == 'CRITICAL' and requires_approval:
                self.trigger_emergency_override(
                    exposure_cap=0.0,
                    triggered_by='ESCALATION_SYSTEM',
                    reason=f"Critical escalation: {issue_type}"
                )

            return escalation

    def resolve_escalation(self,
                          escalation_id: str,
                          resolved_by: str,
                          resolution: str,
                          approved: bool) -> bool:
        """
        Resolve a human escalation.

        Args:
            escalation_id: ID of the escalation to resolve
            resolved_by: Who resolved the escalation
            resolution: Description of the resolution
            approved: Whether the action was approved

        Returns:
            True if escalation was resolved successfully
        """
        with self._lock:
            # Find escalation in audit trail
            for entry in reversed(self.audit_trail):
                if (entry.get('action') == 'escalation' and
                    entry.get('details', {}).get('escalation_id') == escalation_id):

                    # Update escalation status
                    entry['details']['status'] = 'RESOLVED'
                    entry['details']['resolved_at'] = datetime.now().isoformat()
                    entry['details']['resolved_by'] = resolved_by
                    entry['details']['resolution'] = resolution
                    entry['details']['approved'] = approved

                    logger.info(f"Escalation {escalation_id} resolved by {resolved_by}: {resolution}")

                    # If approved and was critical, clear emergency override
                    if approved and entry['details'].get('severity') == 'CRITICAL':
                        self.clear_emergency_override(
                            cleared_by=resolved_by,
                            reason=f"Escalation {escalation_id} resolved"
                        )

                    self._audit_log('escalation_resolved', {
                        'escalation_id': escalation_id,
                        'resolved_by': resolved_by,
                        'resolution': resolution,
                        'approved': approved
                    })

                    return True

            logger.warning(f"Escalation {escalation_id} not found")
            return False

    def check_systematic_violations(self, lookback_hours: int = 24) -> Optional[Dict[str, Any]]:
        """
        Check for systematic risk limit violations that require escalation.

        Escalates if:
        - Same violation occurs more than 5 times in lookback period
        - Multiple critical violations in short timeframe
        - Violation rate is increasing

        Args:
            lookback_hours: Hours to look back for violations

        Returns:
            Escalation details if systematic violations detected, None otherwise
        """
        with self._lock:
            cutoff_time = datetime.now() - timedelta(hours=lookback_hours)
            recent_violations = [v for v in self.violations if v.timestamp >= cutoff_time]

            if not recent_violations:
                return None

            # Count violations by parameter
            violation_counts = {}
            for violation in recent_violations:
                param = violation.parameter
                violation_counts[param] = violation_counts.get(param, 0) + 1

            # Check for systematic violations
            systematic_params = [p for p, count in violation_counts.items() if count > 5]

            if systematic_params:
                # Escalate to human
                escalation = self.escalate_to_human(
                    issue_type='systematic_violations',
                    severity='HIGH',
                    details={
                        'lookback_hours': lookback_hours,
                        'total_violations': len(recent_violations),
                        'systematic_parameters': systematic_params,
                        'violation_counts': violation_counts
                    },
                    requires_approval=True
                )

                return escalation

            # Check for critical violations
            critical_violations = [v for v in recent_violations if v.severity == 'CRITICAL']

            if len(critical_violations) > 3:
                escalation = self.escalate_to_human(
                    issue_type='multiple_critical_violations',
                    severity='CRITICAL',
                    details={
                        'lookback_hours': lookback_hours,
                        'critical_violations': len(critical_violations),
                        'violations': [
                            {
                                'parameter': v.parameter,
                                'value': v.current_value,
                                'limit': v.limit_value,
                                'timestamp': v.timestamp.isoformat()
                            }
                            for v in critical_violations
                        ]
                    },
                    requires_approval=True
                )

                return escalation

            return None



    
    # ========================================================================
    # RISK INVARIANTS VALIDATION
    # ========================================================================

    def _normalize_authority(self, authority_level: Any) -> AuthorityLevel:
        """Normalize external authority enums/strings to local AuthorityLevel."""
        if isinstance(authority_level, AuthorityLevel):
            return authority_level
        if hasattr(authority_level, 'name'):
            name = str(authority_level.name)
            if name in AuthorityLevel.__members__:
                return AuthorityLevel[name]
        if isinstance(authority_level, str) and authority_level in AuthorityLevel.__members__:
            return AuthorityLevel[authority_level]
        return AuthorityLevel.SYSTEM

    def get_risk_parameters(self) -> Dict[str, float]:
        """Return current risk parameters as a plain dictionary."""
        return asdict(self.limits)

    def update_risk_parameters(self,
                               updates: Dict[str, Any],
                               authority_level: Any = AuthorityLevel.SYSTEM,
                               set_by: str = "system",
                               reason: str = "") -> RiskValidationResult:
        """
        Update risk parameters with authority arbitration and consistency checks.
        """
        authority = self._normalize_authority(authority_level)
        errors: List[str] = []

        if not isinstance(updates, dict) or not updates:
            return RiskValidationResult(
                is_valid=False,
                errors=["No parameter updates provided"],
                warnings=[],
                metadata={}
            )

        pending = self.get_risk_parameters()

        for key, value in updates.items():
            if key not in pending:
                errors.append(f"Unknown risk parameter: {key}")
                continue

            current_authority = self._parameter_authority.get(key, AuthorityLevel.SYSTEM)
            if authority.value > current_authority.value:
                errors.append(
                    f"Insufficient authority to update {key}: "
                    f"{authority.name} cannot override {current_authority.name}"
                )
                continue

            pending[key] = value

        # Validate cross-parameter consistency before committing.
        config_check = RiskConfiguration(
            max_position_size=float(pending.get('max_position_size', self.limits.max_position_size)),
            max_sector_exposure=float(pending.get('max_sector_exposure', self.limits.max_sector_exposure)),
            max_drawdown_threshold=float(pending.get('max_drawdown_threshold', self.limits.max_drawdown_threshold)),
            crisis_drawdown_threshold=float(pending.get('crisis_drawdown_threshold', self.limits.crisis_drawdown_threshold)),
            emergency_max_exposure=float(pending.get('emergency_max_exposure', self.limits.emergency_max_exposure)),
        ).validate_consistency()

        if not config_check.is_valid:
            errors.extend(config_check.errors)

        if errors:
            return RiskValidationResult(
                is_valid=False,
                errors=errors,
                warnings=[],
                metadata={'set_by': set_by, 'reason': reason}
            )

        for key, value in updates.items():
            if key in self.get_risk_parameters():
                setattr(self.limits, key, value)
                self._parameter_authority[key] = authority

        self._audit_log('risk_parameter_update', {
            'updates': updates,
            'authority_level': authority.name,
            'set_by': set_by,
            'reason': reason
        })

        return RiskValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            metadata={'set_by': set_by, 'reason': reason}
        )

    def calculate_portfolio_risk(self, portfolio: Dict[str, Any]) -> Dict[str, Any]:
        """Compute basic portfolio risk metrics used by validation tests."""
        positions = portfolio.get('positions', {}) or {}
        nav_history = portfolio.get('nav_history', []) or []

        gross_exposure = sum(abs(pos.get('weight', 0.0)) for pos in positions.values())
        max_position = max((abs(pos.get('weight', 0.0)) for pos in positions.values()), default=0.0)

        sector_exposures: Dict[str, float] = {}
        for pos in positions.values():
            sector = pos.get('sector', 'Unknown')
            sector_exposures[sector] = sector_exposures.get(sector, 0.0) + abs(pos.get('weight', 0.0))

        peak = nav_history[0] if nav_history else portfolio.get('nav', 1.0)
        max_drawdown = 0.0
        for nav in nav_history:
            if nav > peak:
                peak = nav
            drawdown = (peak - nav) / peak if peak > 0 else 0.0
            max_drawdown = max(max_drawdown, drawdown)

        return {
            'gross_exposure': gross_exposure,
            'max_position_size': max_position,
            'sector_exposures': sector_exposures,
            'max_drawdown': max_drawdown
        }

    def check_risk_limits(self, portfolio: Dict[str, Any]) -> RiskValidationResult:
        """Validate portfolio against position and sector exposure constraints."""
        errors: List[str] = []
        metrics = self.calculate_portfolio_risk(portfolio)
        positions = portfolio.get('positions', {}) or {}

        for symbol, pos in positions.items():
            size = abs(pos.get('weight', 0.0))
            if size > self.limits.max_position_size:
                errors.append(
                    f"Position limit breach for {symbol}: {size:.2%} > {self.limits.max_position_size:.2%}"
                )

        for sector, exposure in metrics['sector_exposures'].items():
            if exposure > self.limits.max_sector_exposure:
                errors.append(
                    f"Sector limit breach for {sector}: {exposure:.2%} > {self.limits.max_sector_exposure:.2%}"
                )

        return RiskValidationResult(
            is_valid=not errors,
            errors=errors,
            warnings=[],
            metadata={'metrics': metrics}
        )
    
    def validate_capital_conservation(self,
                                    previous_nav: float,
                                    current_nav: float,
                                    pnl: float,
                                    costs: float,
                                    tolerance: float = 0.0001) -> RiskValidationResult:
        """
        Validate R1: Capital Conservation invariant.
        
        For any portfolio update, capital must be conserved (no magic money).
        
        Args:
            previous_nav: Previous NAV
            current_nav: Current NAV
            pnl: Profit/Loss
            costs: Transaction costs
            tolerance: Tolerance for rounding errors (default 0.01%)
            
        Returns:
            RiskValidationResult
        """
        expected_nav = previous_nav + pnl - costs
        nav_difference = abs(current_nav - expected_nav)
        relative_difference = nav_difference / previous_nav if previous_nav > 0 else 0
        
        is_valid = relative_difference <= tolerance
        
        if not is_valid:
            error_msg = (
                f"Capital conservation violation: "
                f"Expected NAV {expected_nav:.4f}, got {current_nav:.4f}, "
                f"difference {nav_difference:.4f} ({relative_difference:.4%})"
            )
            logger.error(error_msg)
            
            self._audit_log('capital_conservation_violation', {
                'previous_nav': previous_nav,
                'current_nav': current_nav,
                'expected_nav': expected_nav,
                'pnl': pnl,
                'costs': costs,
                'difference': nav_difference,
                'relative_difference': relative_difference
            })
            
            return RiskValidationResult(
                is_valid=False,
                errors=[error_msg],
                warnings=[],
                metadata={
                    'previous_nav': previous_nav,
                    'current_nav': current_nav,
                    'expected_nav': expected_nav,
                    'pnl': pnl,
                    'costs': costs
                }
            )
        
        return RiskValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            metadata={
                'previous_nav': previous_nav,
                'current_nav': current_nav,
                'expected_nav': expected_nav,
                'pnl': pnl,
                'costs': costs
            }
        )
    
    def validate_crisis_derisking(self, *args, **kwargs) -> RiskValidationResult:
        """
        Validate R2: Crisis De-Risking invariant.

        Supports both legacy signatures:
        1) validate_crisis_derisking(crisis_start, pre_crisis_exposure, current_exposure)
        2) validate_crisis_derisking(crisis_period=..., portfolio_history=...)
        """
        if 'crisis_period' in kwargs and 'portfolio_history' in kwargs:
            crisis_period = kwargs['crisis_period']
            portfolio_history = kwargs['portfolio_history'] or []
            if len(portfolio_history) < 2:
                return RiskValidationResult(is_valid=True, errors=[], warnings=["Insufficient history"], metadata={})

            crisis_start = crisis_period.get('start', datetime.now())
            pre_crisis_exposure = self.calculate_portfolio_risk(portfolio_history[0])['gross_exposure']
            required_reduction = self.limits.crisis_derisking_target
            timeframe_days = self.limits.crisis_derisking_timeframe

            for portfolio in portfolio_history[1:]:
                ts = portfolio.get('timestamp', datetime.now())
                days_since_crisis = (ts - crisis_start).days
                if days_since_crisis > timeframe_days:
                    continue
                current_exposure = self.calculate_portfolio_risk(portfolio)['gross_exposure']
                if pre_crisis_exposure > 0:
                    actual_reduction = (pre_crisis_exposure - current_exposure) / pre_crisis_exposure
                    if actual_reduction < required_reduction:
                        msg = (
                            f"Crisis de-risking insufficient: required {required_reduction:.1%}, "
                            f"achieved {actual_reduction:.1%}"
                        )
                        return RiskValidationResult(
                            is_valid=False,
                            errors=[msg],
                            warnings=[],
                            metadata={'required_reduction': required_reduction, 'actual_reduction': actual_reduction}
                        )

            return RiskValidationResult(is_valid=True, errors=[], warnings=[], metadata={})

        if len(args) >= 3:
            crisis_start = args[0]
            pre_crisis_exposure = args[1]
            current_exposure = args[2]
        else:
            crisis_start = kwargs.get('crisis_start', datetime.now())
            pre_crisis_exposure = kwargs.get('pre_crisis_exposure', 0.0)
            current_exposure = kwargs.get('current_exposure', 0.0)

        days_since_crisis = (datetime.now() - crisis_start).days

        if days_since_crisis > self.limits.crisis_derisking_timeframe:
            return RiskValidationResult(is_valid=True, errors=[], warnings=[], metadata={})
        
        required_reduction = self.limits.crisis_derisking_target
        actual_reduction = (
            (pre_crisis_exposure - current_exposure) / pre_crisis_exposure
            if pre_crisis_exposure > 0 else 0.0
        )
        
        is_valid = actual_reduction >= required_reduction
        
        if not is_valid:
            error_msg = (
                f"Crisis de-risking insufficient at day {days_since_crisis}: "
                f"Required {required_reduction:.1%} reduction, "
                f"achieved {actual_reduction:.1%}"
            )
            logger.error(error_msg)
            
            self._audit_log('crisis_derisking_violation', {
                'days_since_crisis': days_since_crisis,
                'required_reduction': required_reduction,
                'actual_reduction': actual_reduction,
                'pre_crisis_exposure': pre_crisis_exposure,
                'current_exposure': current_exposure
            })
            
            return RiskValidationResult(
                is_valid=False,
                errors=[error_msg],
                warnings=[],
                metadata={
                    'days_since_crisis': days_since_crisis,
                    'required_reduction': required_reduction,
                    'actual_reduction': actual_reduction
                }
            )
        
        return RiskValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            metadata={
                'days_since_crisis': days_since_crisis,
                'required_reduction': required_reduction,
                'actual_reduction': actual_reduction
            }
        )

    def validate_risk_of_ruin_protection(self, portfolio_history: List[Dict[str, Any]]) -> RiskValidationResult:
        """Compatibility wrapper for historical crisis drawdown validation."""
        max_crisis_drawdown = 0.0
        for crisis in self.historical_crises:
            crisis_portfolios = [
                p for p in portfolio_history
                if crisis['start'] <= p.get('timestamp', datetime.min) <= crisis['end']
            ]
            if len(crisis_portfolios) < 2:
                continue
            nav_values = [p.get('nav', 1.0) for p in crisis_portfolios]
            peak = nav_values[0]
            crisis_drawdown = 0.0
            for nav in nav_values:
                if nav > peak:
                    peak = nav
                drawdown = (peak - nav) / peak if peak > 0 else 0.0
                crisis_drawdown = max(crisis_drawdown, drawdown)
            max_crisis_drawdown = max(max_crisis_drawdown, crisis_drawdown)

        return self.validate_risk_of_ruin(max_crisis_drawdown)
    
    def validate_risk_of_ruin(self, max_drawdown: float) -> RiskValidationResult:
        """
        Validate R3: Risk-of-Ruin Protection invariant.
        
        For any crisis window, max drawdown must not exceed survival thresholds.
        
        Args:
            max_drawdown: Maximum drawdown observed
            
        Returns:
            RiskValidationResult
        """
        is_valid = max_drawdown <= self.limits.max_drawdown_threshold
        
        if not is_valid:
            error_msg = (
                f"Risk-of-ruin violation: "
                f"Max drawdown {max_drawdown:.1%} exceeds limit {self.limits.max_drawdown_threshold:.1%}"
            )
            logger.error(error_msg)
            
            self._audit_log('risk_of_ruin_violation', {
                'max_drawdown': max_drawdown,
                'threshold': self.limits.max_drawdown_threshold
            })
            
            return RiskValidationResult(
                is_valid=False,
                errors=[error_msg],
                warnings=[],
                metadata={'max_drawdown': max_drawdown}
            )
        
        return RiskValidationResult(
            is_valid=True,
            errors=[],
            warnings=[],
            metadata={'max_drawdown': max_drawdown}
        )
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _calculate_sector_exposure(self, portfolio: Dict[str, Any], sector: str) -> float:
        """Calculate total exposure for a sector"""
        positions = portfolio.get('positions', {})
        sector_exposure = 0.0
        
        for symbol, position in positions.items():
            if position.get('sector') == sector:
                sector_exposure += abs(position.get('weight', 0))
        
        return sector_exposure
    
    def _calculate_total_exposure(self, portfolio: Dict[str, Any]) -> float:
        """Calculate total portfolio exposure"""
        positions = portfolio.get('positions', {})
        return sum(abs(pos.get('weight', 0)) for pos in positions.values())
    
    def _audit_log(self, action: str, details: Dict[str, Any]):
        """Add entry to audit trail"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'action': action,
            'details': details
        }
        self.audit_trail.append(entry)
        
        # Keep only last 1000 entries
        if len(self.audit_trail) > 1000:
            self.audit_trail = self.audit_trail[-1000:]
    
    # ========================================================================
    # STATE MANAGEMENT
    # ========================================================================
    
    def get_risk_state(self) -> Dict[str, Any]:
        """Get current risk authority state"""
        with self._lock:
            return {
                'timestamp': datetime.now().isoformat(),
                'emergency_active': self.emergency_active,
                'emergency_cap': self.emergency_cap,
                'crisis_mode': self.crisis_start_date is not None,
                'crisis_start': self.crisis_start_date.isoformat() if self.crisis_start_date else None,
                'total_violations': len(self.violations),
                'recent_violations': len([v for v in self.violations 
                                        if (datetime.now() - v.timestamp).seconds < 3600]),
                'limits': {
                    'max_position_size': self.limits.max_position_size,
                    'max_sector_exposure': self.limits.max_sector_exposure,
                    'max_drawdown': self.limits.max_drawdown_threshold,
                    'volatility_threshold': self.limits.volatility_threshold
                }
            }
    
    def get_audit_trail(self, last_n: int = 100) -> List[Dict[str, Any]]:
        """Get recent audit trail entries"""
        with self._lock:
            return self.audit_trail[-last_n:]
    
    def get_violations(self, 
                      severity: Optional[str] = None,
                      since: Optional[datetime] = None) -> List[RiskViolation]:
        """Get risk violations with optional filtering"""
        with self._lock:
            violations = self.violations
            
            if severity:
                violations = [v for v in violations if v.severity == severity]
            
            if since:
                violations = [v for v in violations if v.timestamp >= since]
            
            return violations

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def create_risk_authority(config_file: str = "config/risk.yaml") -> UnifiedRiskAuthority:
    """Factory function to create risk authority instance"""
    return UnifiedRiskAuthority(config_file=config_file)

    def get_target_greeks(self, regime: str) -> 'TargetGreeks':
        """
        Get target Greeks for a specific regime.
        
        Args:
            regime: Current volatility regime
            
        Returns:
            TargetGreeks object with regime-appropriate targets
        """
        # Import here to avoid circular dependency
        from .strategy_generator import TargetGreeks
        
        # Define regime-specific target Greeks
        regime_targets = {
            'low_vol': TargetGreeks(
                delta=0.0,
                gamma=20.0,
                vega=100.0,
                theta=-10.0,
                delta_tolerance=0.1,
                gamma_tolerance=0.1,
                vega_tolerance=0.1,
                theta_tolerance=0.1
            ),
            'high_vol': TargetGreeks(
                delta=0.0,
                gamma=15.0,
                vega=75.0,
                theta=-8.0,
                delta_tolerance=0.15,
                gamma_tolerance=0.15,
                vega_tolerance=0.15,
                theta_tolerance=0.15
            ),
            'crisis': TargetGreeks(
                delta=0.0,
                gamma=5.0,
                vega=30.0,
                theta=-3.0,
                delta_tolerance=0.05,
                gamma_tolerance=0.05,
                vega_tolerance=0.05,
                theta_tolerance=0.05
            ),
            'transition': TargetGreeks(
                delta=0.0,
                gamma=10.0,
                vega=50.0,
                theta=-5.0,
                delta_tolerance=0.1,
                gamma_tolerance=0.1,
                vega_tolerance=0.1,
                theta_tolerance=0.1
            )
        }
        
        # Return target for regime, default to low_vol if unknown
        return regime_targets.get(regime, regime_targets['low_vol'])
    
    def get_current_limits(self, regime: str) -> RiskLimits:
        """
        Get current risk limits for a regime.
        
        Args:
            regime: Current volatility regime
            
        Returns:
            RiskLimits object
        """
        return self.limits
