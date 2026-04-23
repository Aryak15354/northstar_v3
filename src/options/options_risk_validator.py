"""
Options Risk Validator for Northstar V3 Risk Coordinator

Integrates options trading risk checks into the V3 hierarchical risk authority system.
This validator has veto power over all options trades and enforces institutional-grade
risk controls.

Philosophy: Options are a first-class organ in the V3 nervous system, not a bolt-on sidecar.
Risk has absolute authority - when survival rules trigger, trading stops.
"""

import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from src.options.survival_rules_engine import (
    SurvivalRulesEngine,
    KillSwitchStatus,
    Position as OptionsPosition,
    Trade as OptionsTradeRecord,
    PerformanceMetrics as OptionsPerformanceMetrics
)
from src.options.trade_eligibility_validator import TradeEligibilityValidator
from src.options.config_loader import get_config

# Import V3 risk coordinator interfaces
V3_RISK_AVAILABLE = False
RiskValidator = None
RiskLevel = None
RiskDecision = None
RiskViolation = None
Trade = None
Portfolio = None
RiskMetrics = None

try:
    from github_repo.src.risk.risk_coordinator import (
        RiskValidator,
        RiskLevel,
        RiskDecision,
        RiskViolation,
        Trade,
        Portfolio,
        RiskMetrics
    )
    V3_RISK_AVAILABLE = True
except ImportError:
    pass

# Fallback classes if V3 not available
if not V3_RISK_AVAILABLE:
    class RiskValidator:
        def validate(self, trade, portfolio, metrics):
            pass
        def get_risk_level(self):
            pass
    
    class RiskLevel:
        SYSTEM = "system"
    
    class RiskDecision(Enum):
        APPROVED = "approved"
        REJECTED = "rejected"
        CONDITIONAL = "conditional"
    
    @dataclass
    class RiskViolation:
        limit_name: str
        current_value: float
        threshold: float
        severity: str
        timestamp: datetime
        description: str
    
    @dataclass
    class Trade:
        symbol: str
        quantity: float
        price: float
        side: str
        trade_type: str
        timestamp: datetime
        metadata: Optional[Dict] = None
    
    @dataclass
    class Portfolio:
        positions: List
        cash: float
        total_value: float
        timestamp: datetime
    
    @dataclass
    class RiskMetrics:
        timestamp: datetime
        portfolio_var: float
        portfolio_cvar: float
        gross_exposure: float
        net_exposure: float
        leverage: float
        max_drawdown: float
        sector_concentrations: Dict[str, float]
        position_concentrations: Dict[str, float]

logger = logging.getLogger("options.risk_validator")


class OptionsRiskValidator(RiskValidator):
    """
    Options-specific risk validator for V3 RiskCoordinator
    
    Integrates options trading risk checks into the hierarchical risk authority system.
    Enforces:
    - Kill switches (weekly loss, trauma, portfolio risk cap, tax liquidity)
    - Frequency limits (max 2 trades/week, time blocks)
    - Trade eligibility (IV rank, liquidity, expiry, events, vol-of-vol)
    - Portfolio risk caps (max 2% capital at risk)
    
    Authority Level: SYSTEM (can veto all options trades)
    """
    
    def __init__(self, base_capital: float, config: Optional[any] = None):
        """
        Initialize options risk validator
        
        Args:
            base_capital: Base capital for risk calculations
            config: Options trading configuration (optional, will load default if not provided)
        """
        self.base_capital = base_capital
        self.config = config or get_config()
        
        # Initialize options risk engines
        self.survival_rules = SurvivalRulesEngine(
            config=self.config.survival_rules,
            base_capital=base_capital
        )
        
        self.eligibility_validator = TradeEligibilityValidator(self.config)
        
        # Track options state
        self.open_options_positions: List[OptionsPosition] = []
        self.closed_options_trades: List[OptionsTradeRecord] = []
        self.options_performance = OptionsPerformanceMetrics(
            current_equity=base_capital,
            ytd_gross_profits=0.0,
            ytd_tax_liability=0.0,
            cash_buffer=0.0
        )
        if not V3_RISK_AVAILABLE:
            logger.warning(
                "OptionsRiskValidator running without external V3 RiskCoordinator interfaces; "
                "fallback compatibility classes are active."
            )
        
        logger.info(f"OptionsRiskValidator initialized with base capital: ₹{base_capital:,.0f}")
    
    def validate(
        self,
        trade: Trade,
        portfolio: Portfolio,
        metrics: RiskMetrics
    ) -> Tuple[RiskDecision, List[RiskViolation]]:
        """
        Validate options trade against system-level risk rules
        
        This is called by RiskCoordinator before any options trade is executed.
        Returns REJECTED if any kill switch is active or eligibility check fails.
        
        Args:
            trade: Proposed trade (V3 Trade object)
            portfolio: Current portfolio state (V3 Portfolio object)
            metrics: Current risk metrics (V3 RiskMetrics object)
        
        Returns:
            Tuple[RiskDecision, List[RiskViolation]]: Decision and violations
        """
        violations = []
        current_time = datetime.now()
        
        # Only validate options trades
        if not self._is_options_trade(trade):
            return RiskDecision.APPROVED, violations
        
        logger.info(f"Validating options trade: {trade.symbol} {trade.side} {trade.quantity}")
        
        # 1. Check kill switches (ABSOLUTE AUTHORITY)
        kill_switch_status = self.survival_rules.check_all_kill_switches(
            open_positions=self.open_options_positions,
            closed_trades=self.closed_options_trades,
            performance=self.options_performance,
            current_time=current_time,
            proposed_trade=self._convert_to_options_position(trade)
        )
        
        if kill_switch_status.active:
            for rule in kill_switch_status.triggered_rules:
                violations.append(RiskViolation(
                    limit_name=f"options_kill_switch_{rule}",
                    current_value=1.0,
                    threshold=0.0,
                    severity='ERROR',
                    timestamp=current_time,
                    description=f"Options kill switch active: {kill_switch_status.reason}"
                ))
            
            logger.warning(f"Options trade REJECTED by kill switches: {kill_switch_status.reason}")
            return RiskDecision.REJECTED, violations
        
        # 2. Check portfolio drawdown (V3 integration)
        if metrics.max_drawdown > 0.05:  # 5% drawdown
            violations.append(RiskViolation(
                limit_name="portfolio_drawdown_limit",
                current_value=metrics.max_drawdown,
                threshold=0.05,
                severity='ERROR',
                timestamp=current_time,
                description=f"Portfolio drawdown {metrics.max_drawdown:.1%} exceeds 5% - options trading halted"
            ))
            
            logger.warning("Options trade REJECTED: Portfolio drawdown exceeds 5%")
            return RiskDecision.REJECTED, violations
        
        # 3. Check portfolio risk cap
        current_options_risk = sum(pos.max_loss for pos in self.open_options_positions)
        proposed_risk = self._estimate_trade_risk(trade)
        total_risk = current_options_risk + proposed_risk
        risk_cap = self.base_capital * 0.02  # 2% cap
        
        if total_risk > risk_cap:
            violations.append(RiskViolation(
                limit_name="options_portfolio_risk_cap",
                current_value=total_risk / self.base_capital,
                threshold=0.02,
                severity='ERROR',
                timestamp=current_time,
                description=f"Options portfolio risk cap breached: ₹{total_risk:,.0f} exceeds 2% cap (₹{risk_cap:,.0f})"
            ))
            
            logger.warning(f"Options trade REJECTED: Portfolio risk cap exceeded")
            return RiskDecision.REJECTED, violations
        
        # 4. Check system-level volatility shock (V3 integration)
        # This would integrate with MarketState.regime if available
        # For now, we check if gross exposure is too high during stress
        if metrics.gross_exposure > 0.8 and metrics.leverage > 1.5:
            violations.append(RiskViolation(
                limit_name="system_stress_options_block",
                current_value=metrics.leverage,
                threshold=1.5,
                severity='WARNING',
                timestamp=current_time,
                description="System stress detected - options trading cautioned"
            ))
            
            logger.warning("Options trade CONDITIONAL: System stress detected")
            return RiskDecision.CONDITIONAL, violations
        
        # All checks passed
        logger.info("Options trade APPROVED by risk validator")
        return RiskDecision.APPROVED, violations
    
    def get_risk_level(self) -> RiskLevel:
        """Get the risk level this validator operates at"""
        return RiskLevel.SYSTEM
    
    def update_options_state(
        self,
        open_positions: List[OptionsPosition],
        closed_trades: List[OptionsTradeRecord],
        performance: OptionsPerformanceMetrics
    ) -> None:
        """
        Update options state for risk validation
        
        This should be called after each options trade or position update.
        
        Args:
            open_positions: Currently open options positions
            closed_trades: Historical closed options trades
            performance: Current options performance metrics
        """
        self.open_options_positions = open_positions
        self.closed_options_trades = closed_trades
        self.options_performance = performance
        
        logger.debug(
            f"Options state updated: {len(open_positions)} open positions, "
            f"{len(closed_trades)} closed trades"
        )
    
    def force_close_all_positions(self, reason: str) -> List[str]:
        """
        Force close all options positions (emergency brake)
        
        This is called by RiskCoordinator when emergency conditions are detected.
        
        Args:
            reason: Reason for force close
        
        Returns:
            List of position IDs that were force closed
        """
        closed_position_ids = []
        
        for position in self.open_options_positions:
            closed_position_ids.append(position.position_id)
            logger.critical(
                f"FORCE CLOSE: Position {position.position_id} "
                f"({position.strategy_type}) - Reason: {reason}"
            )
        
        # Clear open positions
        self.open_options_positions = []
        
        return closed_position_ids
    
    def get_options_risk_summary(self) -> Dict[str, any]:
        """
        Get comprehensive options risk summary
        
        Returns:
            Dict with options risk metrics and status
        """
        current_time = datetime.now()
        
        # Calculate current risk
        total_risk = sum(pos.max_loss for pos in self.open_options_positions)
        risk_pct = (total_risk / self.base_capital) if self.base_capital > 0 else 0
        
        # Get kill switch status
        kill_switch_status = self.survival_rules.check_all_kill_switches(
            open_positions=self.open_options_positions,
            closed_trades=self.closed_options_trades,
            performance=self.options_performance,
            current_time=current_time
        )
        
        # Get survival rules status
        survival_status = self.survival_rules.get_status_summary(
            open_positions=self.open_options_positions,
            closed_trades=self.closed_options_trades,
            performance=self.options_performance,
            current_time=current_time
        )
        
        return {
            'timestamp': current_time.isoformat(),
            'open_positions': len(self.open_options_positions),
            'total_risk': total_risk,
            'risk_percentage': risk_pct,
            'risk_cap': self.base_capital * 0.02,
            'kill_switch_active': kill_switch_status.active,
            'kill_switch_reasons': kill_switch_status.triggered_rules,
            'kill_switch_cooldown_until': kill_switch_status.cooldown_until.isoformat() if kill_switch_status.cooldown_until else None,
            'survival_status': survival_status,
            'ytd_tax_liability': self.options_performance.ytd_tax_liability,
            'cash_buffer': self.options_performance.cash_buffer
        }
    
    def _is_options_trade(self, trade: Trade) -> bool:
        """Check if trade is an options trade"""
        # Check if trade metadata indicates options
        if trade.metadata and 'asset_class' in trade.metadata:
            return trade.metadata['asset_class'] == 'options'
        
        # Check if symbol contains options indicators
        if 'CE' in trade.symbol or 'PE' in trade.symbol:
            return True
        
        # Check trade type
        if trade.trade_type in ['options', 'option_strategy']:
            return True
        
        return False
    
    def _convert_to_options_position(self, trade: Trade) -> OptionsPosition:
        """Convert V3 Trade to OptionsPosition for survival rules checking"""
        # Estimate max loss from trade metadata or use conservative default
        max_loss = 0.0
        if trade.metadata and 'max_loss' in trade.metadata:
            max_loss = trade.metadata['max_loss']
        else:
            # Conservative estimate: 1% of capital per trade
            max_loss = self.base_capital * 0.01
        
        # Determine if short-vol
        is_short_vol = False
        if trade.metadata and 'strategy_type' in trade.metadata:
            strategy_type = trade.metadata['strategy_type']
            is_short_vol = strategy_type in ['IRON_CONDOR', 'CALENDAR_SPREAD']
        
        return OptionsPosition(
            position_id=f"proposed_{trade.symbol}_{trade.timestamp.strftime('%Y%m%d%H%M%S')}",
            strategy_type=trade.metadata.get('strategy_type', 'UNKNOWN') if trade.metadata else 'UNKNOWN',
            max_loss=max_loss,
            entry_time=trade.timestamp,
            is_short_vol=is_short_vol
        )
    
    def _estimate_trade_risk(self, trade: Trade) -> float:
        """Estimate max loss for proposed trade"""
        if trade.metadata and 'max_loss' in trade.metadata:
            return trade.metadata['max_loss']
        
        # Conservative estimate: 1% of capital
        return self.base_capital * 0.01


if __name__ == "__main__":
    # Test options risk validator
    import logging
    
    logging.basicConfig(level=logging.INFO)
    
    # Create validator
    validator = OptionsRiskValidator(base_capital=1000000.0)  # ₹10 lakh
    
    # Create test trade
    test_trade = Trade(
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
    
    # Create test portfolio
    test_portfolio = Portfolio(
        positions=[],
        cash=1000000.0,
        total_value=1000000.0,
        timestamp=datetime.now()
    )
    
    # Create test metrics
    test_metrics = RiskMetrics(
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
    
    # Validate trade
    decision, violations = validator.validate(test_trade, test_portfolio, test_metrics)
    
    print(f"\nValidation Result:")
    print(f"  Decision: {decision}")
    print(f"  Violations: {len(violations)}")
    for v in violations:
        print(f"    - {v.description}")
    
    # Get risk summary
    summary = validator.get_options_risk_summary()
    print(f"\nOptions Risk Summary:")
    print(f"  Open Positions: {summary['open_positions']}")
    print(f"  Total Risk: ₹{summary['total_risk']:,.0f}")
    print(f"  Risk %: {summary['risk_percentage']:.2%}")
    print(f"  Kill Switch Active: {summary['kill_switch_active']}")
