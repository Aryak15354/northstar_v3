"""
Trade Eligibility Validator for Options Trading System

Validates whether a trade should be executed based on:
- IV rank thresholds
- Liquidity checks (bid-ask spread, depth)
- Expiry hygiene
- Event calendar
- Late-cycle protection
- Vol-of-vol conditions

This is the gatekeeper - no trade executes without passing all checks.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from enum import Enum

import pandas as pd

from src.options.strategy_generator import OptionStrategy, StrategyType

logger = logging.getLogger(__name__)

SHORT_VOL_STRATEGY_TYPES = {
    "iron_condor",
    "iron_butterfly",
    "short_strangle",
    "calendar_spread",
}
LONG_VOL_STRATEGY_TYPES = {
    "long_straddle",
    "long_strangle",
    "bear_put_spread",
    "bull_call_spread",
}


class ValidationRule(Enum):
    """Validation rule types"""
    IV_RANK_THRESHOLD = "iv_rank_threshold"
    LIQUIDITY_SPREAD = "liquidity_spread"
    LIQUIDITY_DEPTH = "liquidity_depth"
    EXPIRY_HYGIENE = "expiry_hygiene"
    EVENT_CALENDAR = "event_calendar"
    LATE_CYCLE_PROTECTION = "late_cycle_protection"
    VOL_OF_VOL = "vol_of_vol"


@dataclass
class ValidationResult:
    """Result of trade eligibility validation"""
    is_eligible: bool
    violations: List[str]
    warnings: List[str]
    size_adjustment: float  # 1.0 = full size, 0.5 = half size, 0.0 = reject
    validation_timestamp: datetime
    
    # Detailed rule results
    rule_results: Dict[ValidationRule, bool]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'is_eligible': self.is_eligible,
            'violations': self.violations,
            'warnings': self.warnings,
            'size_adjustment': self.size_adjustment,
            'validation_timestamp': self.validation_timestamp.isoformat(),
            'rule_results': {rule.value: result for rule, result in self.rule_results.items()}
        }


class TradeEligibilityValidator:
    """
    Validates trade eligibility based on multiple criteria
    
    All checks must pass for trade to be eligible.
    Some checks may reduce position size instead of rejecting.
    """
    
    def __init__(self, config: Any):
        """
        Initialize trade eligibility validator
        
        Args:
            config: Eligibility validation configuration
        """
        self.config = config
        self.event_calendar = self._load_event_calendar()
        logger.info("TradeEligibilityValidator initialized")

    def _extract_threshold(self, key: str, default: float) -> float:
        """
        Fetch threshold across config variants.

        Supported layouts:
        - full options config: config.regime_detection.thresholds[key]
        - flat regime config:  config.<key>
        - dict-like threshold blocks
        """
        regime_cfg = getattr(self.config, "regime_detection", None)
        if regime_cfg is not None:
            thresholds = getattr(regime_cfg, "thresholds", None)
            if isinstance(thresholds, dict) and key in thresholds:
                return float(thresholds[key])
            if hasattr(regime_cfg, key):
                return float(getattr(regime_cfg, key))

        if hasattr(self.config, key):
            return float(getattr(self.config, key))

        thresholds = getattr(self.config, "thresholds", None)
        if isinstance(thresholds, dict) and key in thresholds:
            return float(thresholds[key])

        return float(default)

    def _eligibility_cfg(self) -> Any:
        """Support both full options config and eligibility-only config."""
        return getattr(self.config, "eligibility", self.config)

    @staticmethod
    def _regime_key(regime: Any) -> str:
        """Normalize regime objects/strings to a single uppercase key."""
        if hasattr(regime, "value"):
            raw = getattr(regime, "value")
        else:
            raw = regime
        text = str(raw or "").strip().upper()
        return text

    @staticmethod
    def _get_days_in_regime(regime_state: Any) -> int:
        """Handle both `days_in_regime` on state and nested metrics."""
        if hasattr(regime_state, "days_in_regime"):
            try:
                return int(getattr(regime_state, "days_in_regime"))
            except (TypeError, ValueError):
                pass
        metrics = getattr(regime_state, "metrics", None)
        if metrics is not None and hasattr(metrics, "days_in_regime"):
            try:
                return int(getattr(metrics, "days_in_regime"))
            except (TypeError, ValueError):
                pass
        return 0
    
    def validate_trade(
        self,
        strategy: OptionStrategy,
        regime_state: Any,
        option_chain: pd.DataFrame
    ) -> ValidationResult:
        """
        Validate if trade should be executed
        
        Args:
            strategy: Generated strategy to validate
            regime_state: Current regime state
            option_chain: Current option chain data
        
        Returns:
            ValidationResult with eligibility decision
        """
        logger.info(f"Validating trade eligibility for {strategy.strategy_type.value}")
        
        violations = []
        warnings = []
        size_adjustment = 1.0
        rule_results = {}
        
        # 1. IV rank threshold check
        iv_rank_ok, iv_rank_msg = self._check_iv_rank_threshold(
            regime_state.regime,
            regime_state.metrics.iv_rank
        )
        rule_results[ValidationRule.IV_RANK_THRESHOLD] = iv_rank_ok
        if not iv_rank_ok:
            violations.append(iv_rank_msg)
        
        # 2. Liquidity spread check
        spread_ok, spread_msg = self._check_liquidity_spread(strategy, option_chain)
        rule_results[ValidationRule.LIQUIDITY_SPREAD] = spread_ok
        if not spread_ok:
            violations.append(spread_msg)
        
        # 3. Liquidity depth check
        depth_ok, depth_msg = self._check_liquidity_depth(strategy, option_chain)
        rule_results[ValidationRule.LIQUIDITY_DEPTH] = depth_ok
        if not depth_ok:
            violations.append(depth_msg)
        
        # 4. Expiry hygiene check
        expiry_ok, expiry_msg = self._check_expiry_hygiene(strategy)
        rule_results[ValidationRule.EXPIRY_HYGIENE] = expiry_ok
        if not expiry_ok:
            violations.append(expiry_msg)
        
        # 5. Event calendar check
        event_ok, event_msg = self._check_event_calendar(strategy)
        rule_results[ValidationRule.EVENT_CALENDAR] = event_ok
        if not event_ok:
            violations.append(event_msg)
        
        # 6. Vol-of-vol check (blocks short-vol)
        vol_of_vol_ok, vol_of_vol_msg = self._check_vol_of_vol(
            strategy,
            regime_state.metrics.vol_of_vol_elevated
        )
        rule_results[ValidationRule.VOL_OF_VOL] = vol_of_vol_ok
        if not vol_of_vol_ok:
            violations.append(vol_of_vol_msg)
        
        # 7. Late-cycle protection (reduces size, doesn't reject)
        late_cycle_adjustment, late_cycle_msg = self._check_late_cycle_protection(
            regime_state.regime,
            self._get_days_in_regime(regime_state)
        )
        rule_results[ValidationRule.LATE_CYCLE_PROTECTION] = late_cycle_adjustment == 1.0
        if late_cycle_adjustment < 1.0:
            warnings.append(late_cycle_msg)
            size_adjustment = min(size_adjustment, late_cycle_adjustment)
        
        # Determine eligibility
        is_eligible = len(violations) == 0
        
        result = ValidationResult(
            is_eligible=is_eligible,
            violations=violations,
            warnings=warnings,
            size_adjustment=size_adjustment,
            validation_timestamp=datetime.now(timezone.utc),
            rule_results=rule_results
        )
        
        if is_eligible:
            logger.info(
                f"Trade ELIGIBLE (size adjustment: {size_adjustment:.0%}, "
                f"warnings: {len(warnings)})"
            )
        else:
            logger.warning(
                f"Trade REJECTED: {len(violations)} violations - {', '.join(violations)}"
            )
        
        return result
    
    def _check_iv_rank_threshold(
        self,
        regime: Any,
        iv_rank: float
    ) -> tuple[bool, str]:
        """
        Check if IV rank meets threshold for regime
        
        Requirements:
        - HIGH_VOL: IV rank >= configured high-vol threshold
        - LOW_VOL: IV rank <= configured low-vol ceiling
        
        Args:
            regime: Current regime
            iv_rank: Current IV rank (0-1)
        
        Returns:
            (is_valid, message)
        """
        low_sell = self._extract_threshold("low_vol_sell_iv_rank", 0.70)
        high_sell = self._extract_threshold("high_vol_sell_iv_rank", 0.80)
        rising_buy = self._extract_threshold("rising_vol_buy_iv_rank", 0.30)

        key = self._regime_key(regime)

        # Legacy options enums: LOW_VOL_SELL/HIGH_VOL_SELL/RISING_VOL_BUY
        # Unified enum aliases are mapped to the same behavioral rules.
        if key in {"HIGH_VOL_SELL", "HIGH_VOL"}:
            if iv_rank < high_sell:
                return False, f"IV rank {iv_rank:.1%} < required {high_sell:.1%} for HIGH_VOL_SELL"

        elif key in {"LOW_VOL_SELL", "LOW_VOL"}:
            if iv_rank < low_sell:
                return False, f"IV rank {iv_rank:.1%} < required {low_sell:.1%} for LOW_VOL_SELL"

        elif key in {"RISING_VOL_BUY"}:
            if iv_rank > rising_buy:
                return False, f"IV rank {iv_rank:.1%} > allowed {rising_buy:.1%} for RISING_VOL_BUY"
        
        return True, ""
    
    def _check_liquidity_spread(
        self,
        strategy: OptionStrategy,
        option_chain: pd.DataFrame
    ) -> tuple[bool, str]:
        """
        Check bid-ask spread for all legs
        
        Requirement: Spread ≤ 8% of mid premium
        
        Args:
            strategy: Strategy to validate
            option_chain: Current option chain data
        
        Returns:
            (is_valid, message)
        """
        eligibility = self._eligibility_cfg()
        max_spread_pct = float(getattr(eligibility, "max_bid_ask_spread_pct", 0.08))
        
        for leg in strategy.legs:
            # Find leg in option chain - normalize expiry to date for comparison
            leg_expiry = leg.expiry if isinstance(leg.expiry, datetime) else pd.to_datetime(leg.expiry)
            leg_expiry_date = leg_expiry.date()
            
            # Filter by strike and option type first
            leg_data = option_chain[
                (option_chain['strike'] == leg.strike) &
                (option_chain['option_type'] == leg.option_type)
            ].copy()
            
            # Then filter by expiry (compare dates only, not times)
            if not leg_data.empty:
                leg_data['expiry_dt'] = pd.to_datetime(leg_data['expiry'])
                leg_data['expiry_date'] = leg_data['expiry_dt'].dt.date
                leg_data = leg_data[leg_data['expiry_date'] == leg_expiry_date]
            
            if leg_data.empty:
                return False, f"Leg {leg.strike} {leg.option_type} not found in option chain"
            
            leg_data = leg_data.iloc[0]
            
            # Check if bid/ask available
            if 'bid' not in leg_data or 'ask' not in leg_data:
                logger.warning("Bid/ask not available in option chain")
                continue
            
            bid = leg_data['bid']
            ask = leg_data['ask']
            
            if bid <= 0 or ask <= 0:
                return False, f"Invalid bid/ask for {leg.strike} {leg.option_type}"
            
            # Calculate spread
            mid = (bid + ask) / 2
            spread_pct = (ask - bid) / mid if mid > 0 else 1.0
            
            if spread_pct > max_spread_pct:
                return False, (
                    f"Spread {spread_pct:.1%} > max {max_spread_pct:.1%} "
                    f"for {leg.strike} {leg.option_type}"
                )
        
        return True, ""
    
    def _check_liquidity_depth(
        self,
        strategy: OptionStrategy,
        option_chain: pd.DataFrame
    ) -> tuple[bool, str]:
        """
        Check liquidity depth for all legs
        
        Requirement: available side depth ≥ configured multiplier × order quantity
        
        Args:
            strategy: Strategy to validate
            option_chain: Current option chain data
        
        Returns:
            (is_valid, message)
        """
        eligibility = self._eligibility_cfg()
        min_depth_multiplier = float(getattr(eligibility, "min_liquidity_depth_multiplier", 2.0))
        
        for leg in strategy.legs:
            # Find leg in option chain - normalize expiry to date for comparison
            leg_expiry = leg.expiry if isinstance(leg.expiry, datetime) else pd.to_datetime(leg.expiry)
            leg_expiry_date = leg_expiry.date()
            
            # Filter by strike and option type first
            leg_data = option_chain[
                (option_chain['strike'] == leg.strike) &
                (option_chain['option_type'] == leg.option_type)
            ].copy()
            
            # Then filter by expiry (compare dates only, not times)
            if not leg_data.empty:
                leg_data['expiry_dt'] = pd.to_datetime(leg_data['expiry'])
                leg_data['expiry_date'] = leg_data['expiry_dt'].dt.date
                leg_data = leg_data[leg_data['expiry_date'] == leg_expiry_date]
            
            if leg_data.empty:
                return False, f"Leg {leg.strike} {leg.option_type} not found in option chain"
            
            leg_data = leg_data.iloc[0]
            
            # Check if bid_qty available
            if 'bid_qty' not in leg_data:
                logger.warning("Bid quantity not available in option chain")
                continue

            action = str(getattr(leg, 'action', 'SELL')).upper()
            depth_col = 'ask_qty' if action == 'BUY' and 'ask_qty' in leg_data else 'bid_qty'
            if depth_col not in leg_data:
                depth_col = 'bid_qty' if 'bid_qty' in leg_data else ('ask_qty' if 'ask_qty' in leg_data else None)
            if depth_col is None:
                logger.warning("No depth columns available in option chain")
                continue

            available_qty = float(leg_data[depth_col] or 0.0)
            required_qty = leg.quantity * min_depth_multiplier
            
            if available_qty < required_qty:
                return False, (
                    f"Insufficient liquidity for {leg.strike} {leg.option_type}: "
                    f"{depth_col} {available_qty:.0f} < required {required_qty:.0f}"
                )
        
        return True, ""
    
    def _check_expiry_hygiene(self, strategy: OptionStrategy) -> tuple[bool, str]:
        """
        Check expiry hygiene
        
        Requirement: No trades with < 5 days to expiry
        
        Args:
            strategy: Strategy to validate
        
        Returns:
            (is_valid, message)
        """
        eligibility = self._eligibility_cfg()
        min_days = int(getattr(eligibility, "min_days_to_expiry", 5))
        
        if strategy.days_to_expiry < min_days:
            return False, (
                f"Days to expiry {strategy.days_to_expiry} < minimum {min_days}"
            )
        
        return True, ""
    
    def _check_event_calendar(self, strategy: OptionStrategy) -> tuple[bool, str]:
        """
        Check event calendar
        
        Requirement: Block short-vol within 2 days of macro events
        
        Args:
            strategy: Strategy to validate
        
        Returns:
            (is_valid, message)
        """
        # Only check for short-vol strategies
        if not self._is_short_vol_strategy(strategy):
            return True, ""
        
        eligibility = self._eligibility_cfg()
        buffer_days = int(getattr(eligibility, "event_buffer_days", 2))
        now = datetime.now()
        
        # Check all events
        for event in self.event_calendar:
            event_date = event['date']
            days_to_event = (event_date - now).days
            
            if 0 <= days_to_event <= buffer_days:
                return False, (
                    f"Short-vol blocked: {event['type']} event in {days_to_event} days "
                    f"(buffer: {buffer_days} days)"
                )
        
        return True, ""
    
    def _check_vol_of_vol(
        self,
        strategy: OptionStrategy,
        vol_of_vol_elevated: bool
    ) -> tuple[bool, str]:
        """
        Check vol-of-vol condition
        
        Requirement: Block short-vol if vol-of-vol elevated
        
        Args:
            strategy: Strategy to validate
            vol_of_vol_elevated: Whether vol-of-vol is elevated
        
        Returns:
            (is_valid, message)
        """
        if not vol_of_vol_elevated:
            return True, ""
        
        # Block short-vol strategies
        if self._is_short_vol_strategy(strategy):
            return False, "Short-vol blocked: vol-of-vol elevated (unstable volatility regime)"
        
        return True, ""
    
    def _check_late_cycle_protection(
        self,
        regime: Any,
        days_in_regime: int
    ) -> tuple[float, str]:
        """
        Check late-cycle protection
        
        Requirement: Reduce size by 50% if LOW_VOL persists too long
        
        Args:
            regime: Current regime
            days_in_regime: Days in current regime
        
        Returns:
            (size_adjustment, message)
        """
        key = self._regime_key(regime)
        if key not in {"LOW_VOL_SELL", "LOW_VOL"}:
            return 1.0, ""
        
        eligibility = self._eligibility_cfg()
        threshold_days = int(getattr(eligibility, "late_cycle_days", 10))
        
        if days_in_regime > threshold_days:
            reduction = float(getattr(eligibility, "late_cycle_size_reduction", 0.5))
            return reduction, (
                f"Late-cycle protection: {days_in_regime} days in LOW_VOL "
                f"(threshold: {threshold_days}) - size reduced to {reduction:.0%}"
            )
        
        return 1.0, ""
    
    def _is_short_vol_strategy(self, strategy: OptionStrategy) -> bool:
        """
        Check if strategy is short-vol
        
        Args:
            strategy: Strategy to check
        
        Returns:
            True if short-vol
        """
        if strategy is None:
            return False

        if hasattr(strategy.strategy_type, "value"):
            token = str(strategy.strategy_type.value or "").strip().lower()
        else:
            token = str(strategy.strategy_type or "").strip().lower()

        if token in SHORT_VOL_STRATEGY_TYPES:
            return True
        if token in LONG_VOL_STRATEGY_TYPES:
            return False

        # Conservative fallback:
        # strategy types not explicitly mapped are treated by premium sign.
        # Negative net_credit_debit means net premium received => short-vol leaning.
        try:
            net = float(strategy.net_credit_debit or 0.0)
            return net < 0
        except Exception:
            return token != StrategyType.LONG_STRADDLE.value
    
    def _load_event_calendar(self) -> List[Dict[str, Any]]:
        """
        Load event calendar from config
        
        Returns:
            List of events with dates
        """
        events = []
        
        if not hasattr(self.config, 'event_calendar'):
            logger.warning("No event calendar in config")
            return events
        
        for event_group in self.config.event_calendar:
            # Handle both dict and MacroEvent object
            if isinstance(event_group, dict):
                event_type = event_group['event_type']
                buffer_days = event_group.get('buffer_days', 2)
                dates = event_group['dates']
            else:
                # MacroEvent object
                event_type = event_group.event_type
                buffer_days = event_group.buffer_days
                dates = event_group.dates
            
            for date_str in dates:
                try:
                    event_date = datetime.strptime(date_str, '%Y-%m-%d')
                    events.append({
                        'type': event_type,
                        'date': event_date,
                        'buffer_days': buffer_days
                    })
                except ValueError:
                    logger.warning(f"Invalid date format: {date_str}")
        
        logger.info(f"Loaded {len(events)} events from calendar")
        return events


if __name__ == "__main__":
    # Test trade eligibility validator
    import logging
    from src.options.config_loader import get_config
    from src.volatility.regime_detector import RegimeMetrics, RegimeState, VolatilityRegime
    from src.options.strategy_generator import StrategyGenerator
    import numpy as np
    
    logging.basicConfig(level=logging.INFO)
    
    config = get_config()
    validator = TradeEligibilityValidator(config)
    
    # Create sample regime state
    regime_state = RegimeState(
        regime=VolatilityRegime.LOW_VOL,
        metrics=RegimeMetrics(
            breadth=0.55,
            participation=0.52,
            market_correlation=0.45,
            market_volatility=0.013,
            iv_rank=0.25,
            iv_trend="stable",
            skew=0.05,
            vol_of_vol_elevated=False,
            risk_on_score=0.58,
            regime_confidence=0.85
        ),
        timestamp=datetime.now(),
        confidence=0.85,
        days_in_regime=5,
        transition_probability={},
        reason="Test regime"
    )
    
    # Create sample option chain
    strikes = np.arange(25000, 26500, 50)
    spot = 25867
    
    option_data = []
    for strike in strikes:
        moneyness = strike / spot
        base_iv = 0.15
        iv = base_iv + 0.05 * (1 - moneyness)**2
        
        # Add bid/ask
        mid = max(10, 100 * (1 - abs(moneyness - 1)))
        spread = mid * 0.05  # 5% spread
        
        option_data.append({
            'strike': strike,
            'option_type': 'CE',
            'expiry': datetime.now() + timedelta(days=30),
            'iv': iv,
            'underlying_price': spot,
            'bid': mid - spread/2,
            'ask': mid + spread/2,
            'bid_qty': 100,
            'ltp': mid,
            'delta': 0.5 - (strike - spot) / (2 * spot)
        })
        option_data.append({
            'strike': strike,
            'option_type': 'PE',
            'expiry': datetime.now() + timedelta(days=30),
            'iv': iv * 1.1,
            'underlying_price': spot,
            'bid': mid - spread/2,
            'ask': mid + spread/2,
            'bid_qty': 100,
            'ltp': mid,
            'delta': -0.5 + (strike - spot) / (2 * spot)
        })
    
    option_chain = pd.DataFrame(option_data)
    
    # Generate strategy
    generator = StrategyGenerator(config.strategies)
    strategy = generator.generate_strategy(VolatilityRegime.LOW_VOL, option_chain, 'NIFTY')
    
    if strategy:
        # Validate trade
        result = validator.validate_trade(strategy, regime_state, option_chain)
        
        print(f"\nValidation Result:")
        print(f"  Eligible: {result.is_eligible}")
        print(f"  Size Adjustment: {result.size_adjustment:.0%}")
        print(f"  Violations: {len(result.violations)}")
        for v in result.violations:
            print(f"    - {v}")
        print(f"  Warnings: {len(result.warnings)}")
        for w in result.warnings:
            print(f"    - {w}")
    else:
        print("No strategy generated")
