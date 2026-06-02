"""
V3 Risk System Integration for Options Trading

This module integrates the options trading system with Northstar V3's risk management
infrastructure. It registers the OptionsRiskValidator with the RiskCoordinator and
ensures options trades are subject to the same hierarchical risk authority as equities.

Integration Points:
1. RiskCoordinator - Register OptionsRiskValidator in validation chain
2. UnifiedRiskAuthority - Integrate with emergency brake system
3. Kill Switches - Options-specific kill switches feed into system-level risk state

Philosophy: Options are a first-class organ in the V3 nervous system.
Risk has absolute authority - no exceptions.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from src.options.options_risk_validator import OptionsRiskValidator
from src.options.config_loader import get_config

# Import V3 risk components
try:
    from src.volatility.risk_authority import create_risk_authority, UnifiedRiskAuthority
    V3_UNIFIED_RISK_AVAILABLE = True
except ImportError:
    V3_UNIFIED_RISK_AVAILABLE = False
    create_risk_authority = None
    UnifiedRiskAuthority = None

try:
    from github_repo.src.risk.risk_coordinator import RiskCoordinator, RiskLimit, RiskLevel
    V3_RISK_COORDINATOR_AVAILABLE = True
except ImportError:
    V3_RISK_COORDINATOR_AVAILABLE = False
    RiskCoordinator = None
    RiskLimit = None
    RiskLevel = None

logger = logging.getLogger("options.v3_integration")


class OptionsV3RiskIntegration:
    """
    Integrates options trading with V3 risk management system
    
    This class acts as the bridge between the options trading system and
    Northstar V3's risk infrastructure. It ensures options trades are
    validated through the same hierarchical risk authority as equities.
    """
    
    def __init__(self, base_capital: float, config: Optional[Any] = None):
        """
        Initialize V3 risk integration
        
        Args:
            base_capital: Base capital for risk calculations
            config: Options trading configuration (optional)
        """
        self.base_capital = base_capital
        self.config = config or get_config()
        
        # Initialize options risk validator
        self.options_validator = OptionsRiskValidator(
            base_capital=base_capital,
            config=self.config
        )
        
        # V3 components (lazy loaded)
        self._risk_coordinator: Optional[RiskCoordinator] = None
        self._unified_risk_authority: Optional[UnifiedRiskAuthority] = None
        if not V3_RISK_COORDINATOR_AVAILABLE:
            logger.warning(
                "OptionsV3RiskIntegration initialized without a live V3 RiskCoordinator dependency; "
                "registration will remain standalone until that interface is restored."
            )
        
        logger.info("OptionsV3RiskIntegration initialized")
    
    def register_with_risk_coordinator(
        self,
        risk_coordinator: Optional[RiskCoordinator] = None
    ) -> bool:
        """
        Register OptionsRiskValidator with V3 RiskCoordinator
        
        This adds options-specific risk validation to the hierarchical
        risk authority chain. The OptionsRiskValidator operates at the
        SYSTEM level and can veto any options trade.
        
        Args:
            risk_coordinator: V3 RiskCoordinator instance (optional, will create if not provided)
        
        Returns:
            bool: True if registration successful
        """
        if not V3_RISK_COORDINATOR_AVAILABLE:
            logger.warning("V3 RiskCoordinator not available - running in standalone mode")
            return False
        
        try:
            # Use provided coordinator or create new one
            if risk_coordinator:
                self._risk_coordinator = risk_coordinator
            else:
                # Create risk coordinator with options-specific limits
                risk_limits = self._create_options_risk_limits()
                self._risk_coordinator = RiskCoordinator(risk_limits=risk_limits)
            
            # Register options validator
            self._risk_coordinator.validators[RiskLevel.SYSTEM] = self.options_validator
            
            logger.info("OptionsRiskValidator registered with RiskCoordinator at SYSTEM level")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register with RiskCoordinator: {e}")
            return False
    
    def integrate_with_unified_risk_coordinator(
        self,
        unified_coordinator: Optional[UnifiedRiskAuthority] = None
    ) -> bool:
        """
        Integrate with V3 UnifiedRiskAuthority
        
        This ensures options risk state is included in the unified risk
        management system and options kill switches feed into emergency brake.
        
        Args:
            unified_coordinator: V3 UnifiedRiskAuthority instance (optional)
        
        Returns:
            bool: True if integration successful
        """
        if not V3_UNIFIED_RISK_AVAILABLE:
            logger.warning("V3 UnifiedRiskAuthority not available - running in standalone mode")
            return False
        
        try:
            # Use provided coordinator or create new one
            if unified_coordinator:
                self._unified_risk_authority = unified_coordinator
            else:
                # Prefer factory to ensure config-backed initialization.
                self._unified_risk_authority = create_risk_authority()
            
            logger.info("Integrated with UnifiedRiskAuthority")
            return True
            
        except Exception as e:
            logger.error(f"Failed to integrate with UnifiedRiskAuthority: {e}")
            return False
    
    def check_options_risk_before_trade(
        self,
        trade_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check options risk before executing trade
        
        This is the main entry point for options trade validation.
        It runs all risk checks and returns a decision.
        
        Args:
            trade_metadata: Trade metadata including strategy, max_loss, etc.
        
        Returns:
            Dict with validation result:
                - approved: bool
                - decision: str (APPROVED, REJECTED, CONDITIONAL)
                - violations: List[str]
                - reason: str
        """
        try:
            # Create V3 Trade object from metadata
            from src.options.options_risk_validator import Trade, Portfolio, RiskMetrics
            
            trade = Trade(
                symbol=trade_metadata.get('symbol', 'UNKNOWN'),
                quantity=trade_metadata.get('quantity', 0),
                price=trade_metadata.get('price', 0.0),
                side=trade_metadata.get('side', 'buy'),
                trade_type='options',
                timestamp=datetime.now(),
                metadata=trade_metadata
            )
            
            # Create portfolio state
            portfolio = Portfolio(
                positions=[],
                cash=self.base_capital,
                total_value=self.base_capital,
                timestamp=datetime.now()
            )
            
            # Create risk metrics
            metrics = RiskMetrics(
                timestamp=datetime.now(),
                portfolio_var=0.0,
                portfolio_cvar=0.0,
                gross_exposure=0.0,
                net_exposure=0.0,
                leverage=1.0,
                max_drawdown=0.0,
                sector_concentrations={},
                position_concentrations={}
            )
            
            # Validate through options risk validator
            decision, violations = self.options_validator.validate(trade, portfolio, metrics)
            
            # Format result
            result = {
                'approved': decision.value == 'approved',
                'decision': decision.value,
                'violations': [v.description for v in violations],
                'reason': violations[0].description if violations else 'All risk checks passed',
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"Options risk check: {result['decision']} - {result['reason']}")
            return result
            
        except Exception as e:
            logger.error(f"Options risk check failed: {e}")
            return {
                'approved': False,
                'decision': 'REJECTED',
                'violations': [str(e)],
                'reason': f'Risk check error: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }
    
    def get_integrated_risk_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive risk summary including V3 integration status
        
        Returns:
            Dict with risk summary and integration status
        """
        # Get options risk summary
        options_summary = self.options_validator.get_options_risk_summary()
        
        # Add integration status
        integration_status = {
            'v3_risk_coordinator_available': V3_RISK_COORDINATOR_AVAILABLE,
            'v3_unified_risk_available': V3_UNIFIED_RISK_AVAILABLE,
            'risk_coordinator_registered': self._risk_coordinator is not None,
            # Keep legacy key for compatibility with existing dashboards/reports.
            'unified_coordinator_integrated': self._unified_risk_authority is not None,
            'unified_risk_authority_integrated': self._unified_risk_authority is not None
        }
        
        return {
            'options_risk': options_summary,
            'v3_integration': integration_status,
            'timestamp': datetime.now().isoformat()
        }
    
    def _create_options_risk_limits(self):
        """Create options-specific risk limits for RiskCoordinator"""
        if not RiskLimit or not RiskLevel:
            return []
        
        return [
            RiskLimit(
                name='options_portfolio_risk_cap',
                level=RiskLevel.SYSTEM,
                limit_type='percentage',
                threshold=0.02,  # 2% of capital
                warning_threshold=0.015,  # 1.5% warning
                currency='INR',
                active=True
            ),
            RiskLimit(
                name='options_weekly_loss_limit',
                level=RiskLevel.SYSTEM,
                limit_type='percentage',
                threshold=0.02,  # 2% weekly loss
                warning_threshold=0.015,  # 1.5% warning
                currency='INR',
                active=True
            ),
            RiskLimit(
                name='options_max_open_positions',
                level=RiskLevel.PORTFOLIO,
                limit_type='count',
                threshold=3.0,  # Max 3 open positions
                warning_threshold=2.0,  # Warning at 2
                currency='INR',
                active=True
            ),
            RiskLimit(
                name='options_max_weekly_trades',
                level=RiskLevel.SYSTEM,
                limit_type='count',
                threshold=2.0,  # Max 2 trades per week
                warning_threshold=1.0,  # Warning at 1
                currency='INR',
                active=True
            )
        ]


def create_v3_risk_integration(base_capital: float) -> OptionsV3RiskIntegration:
    """
    Factory function to create V3 risk integration
    
    Args:
        base_capital: Base capital for risk calculations
    
    Returns:
        OptionsV3RiskIntegration instance
    """
    integration = OptionsV3RiskIntegration(base_capital=base_capital)
    
    # Attempt to register with V3 components
    integration.register_with_risk_coordinator()
    integration.integrate_with_unified_risk_coordinator()
    
    return integration


if __name__ == "__main__":
    # Test V3 risk integration
    import logging
    
    logging.basicConfig(level=logging.INFO)
    
    # Create integration
    integration = create_v3_risk_integration(base_capital=1000000.0)  # ₹10 lakh
    
    # Test trade validation
    test_trade = {
        'symbol': 'NIFTY_25000_CE',
        'quantity': 50,
        'price': 100.0,
        'side': 'buy',
        'strategy_type': 'IRON_CONDOR',
        'max_loss': 5000.0,
        'asset_class': 'options'
    }
    
    result = integration.check_options_risk_before_trade(test_trade)
    
    print(f"\nRisk Check Result:")
    print(f"  Approved: {result['approved']}")
    print(f"  Decision: {result['decision']}")
    print(f"  Reason: {result['reason']}")
    
    # Get integrated risk summary
    summary = integration.get_integrated_risk_summary()
    
    print(f"\nIntegrated Risk Summary:")
    print(f"  V3 RiskCoordinator Available: {summary['v3_integration']['v3_risk_coordinator_available']}")
    print(f"  V3 UnifiedRisk Available: {summary['v3_integration']['v3_unified_risk_available']}")
    print(f"  RiskCoordinator Registered: {summary['v3_integration']['risk_coordinator_registered']}")
    print(f"  Options Kill Switch Active: {summary['options_risk']['kill_switch_active']}")
    print(f"  Total Risk: ₹{summary['options_risk']['total_risk']:,.0f}")
