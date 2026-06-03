"""
Enhanced Strategy Generator V2 for Options Paper Engine

Simplified version that focuses on working basic strategies with proper OptionLeg format.
Falls back to basic strategies when unified engine fails.
"""

import logging
import warnings
from typing import List, Dict, Any, Optional, Tuple
from datetime import date, datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import pandas as pd

# Import from current options engine
from src.options.strategy_generator import (
    StrategyType as BasicStrategyType,
    Greeks,
    OptionLeg,
    OptionStrategy
)

logger = logging.getLogger(__name__)

warnings.warn(
    "src.options.enhanced_strategy_generator_v2 is deprecated for Northstar V3; "
    "use src.options.enhanced_strategy_generator_v3.EnhancedStrategyGeneratorV3.",
    DeprecationWarning,
    stacklevel=2,
)


class EnhancedStrategyGeneratorV2:
    """
    Simplified enhanced strategy generator that focuses on working basic strategies.
    """
    
    def __init__(self, config: Any):
        self.config = config
        logger.info("Enhanced strategy generator V2 initialized")
    
    def generate_strategy(
        self,
        regime: Any,
        underlying: str,
        option_chain: pd.DataFrame,
        spot_price: float,
        implied_vol: float = 0.20,
        risk_free_rate: float = 0.05
    ) -> Optional[OptionStrategy]:
        """
        Generate strategy using reliable basic approaches.
        """
        try:
            # Normalize regime
            regime_str = self._normalize_regime(regime)
            
            # Find a suitable expiry
            current_expiry = self._find_nearest_expiry(option_chain, 7, 60)
            if current_expiry is None:
                logger.warning(f"No suitable expiry found for {underlying}")
                return None
            
            # Generate strategy based on regime
            if regime_str in ["low_vol_sell", "high_vol_sell"]:
                # Try iron condor first
                strategy = self._generate_iron_condor(underlying, option_chain, spot_price, current_expiry)
                if strategy:
                    return strategy
                
                # Fall back to short straddle
                strategy = self._generate_short_straddle(underlying, option_chain, spot_price, current_expiry)
                if strategy:
                    return strategy
            
            elif regime_str in ["rising_vol_buy", "falling_vol_buy"]:
                # Try long straddle first
                strategy = self._generate_long_straddle(underlying, option_chain, spot_price, current_expiry)
                if strategy:
                    return strategy
                
                # Fall back to calendar spread
                strategy = self._generate_calendar_spread(underlying, option_chain, spot_price, current_expiry)
                if strategy:
                    return strategy
            
            # Ultimate fallback - simple long call
            return self._generate_long_call(underlying, option_chain, spot_price, current_expiry)
            
        except Exception as e:
            logger.error(f"Strategy generation failed: {e}")
            return None
    
    def _normalize_regime(self, regime: Any) -> str:
        """Normalize regime to string"""
        if hasattr(regime, 'value'):
            return regime.value
        return str(regime).lower()
    
    def _find_nearest_expiry(
        self,
        option_chain: pd.DataFrame,
        min_days: int,
        max_days: int
    ) -> Optional[date]:
        """Find expiry within date range"""
        try:
            today = datetime.now().date()
            expiries = option_chain['expiry'].unique()
            
            valid_expiries = []
            for expiry in expiries:
                # Handle different expiry formats
                if isinstance(expiry, str):
                    expiry_date = datetime.strptime(expiry, '%Y-%m-%d').date()
                elif hasattr(expiry, 'date'):  # Timestamp
                    expiry_date = expiry.date()
                elif isinstance(expiry, date):
                    expiry_date = expiry
                else:
                    continue
                
                days_to_expiry = (expiry_date - today).days
                if min_days <= days_to_expiry <= max_days:
                    valid_expiries.append((expiry_date, days_to_expiry))
            
            if not valid_expiries:
                return None
            
            # Return closest to middle of range
            target_days = (min_days + max_days) / 2
            closest = min(valid_expiries, key=lambda x: abs(x[1] - target_days))
            return closest[0]
            
        except Exception as e:
            logger.warning(f"Error finding expiry: {e}")
            return None
    
    def _find_closest_option(
        self,
        option_chain: pd.DataFrame,
        option_type: str,
        target_strike: float,
        expiry: date
    ) -> Optional[pd.Series]:
        """Find closest option to target strike"""
        try:
            if option_chain.empty:
                return None
            
            # Filter by type and expiry
            filtered = option_chain[
                (option_chain['option_type'].str.lower() == option_type.lower()) &
                (option_chain['expiry'] == expiry.strftime('%Y-%m-%d'))
            ]
            
            if filtered.empty:
                # Try any expiry for this type
                filtered = option_chain[
                    option_chain['option_type'].str.lower() == option_type.lower()
                ]
                
                if filtered.empty:
                    return None
            
            # Find closest strike
            strike_diffs = abs(filtered['strike'] - target_strike)
            closest_idx = strike_diffs.idxmin()
            return filtered.loc[closest_idx]
            
        except Exception as e:
            logger.warning(f"Error finding closest option: {e}")
            return None
    
    def _create_option_leg(
        self,
        option_row: pd.Series,
        option_type: str,
        expiry: date,
        action: str,
        quantity: int = 1
    ) -> OptionLeg:
        """Create OptionLeg with proper format"""
        return OptionLeg(
            option_type='CE' if option_type.lower() == 'call' else 'PE',
            strike=float(option_row['strike']),
            expiry=datetime.combine(expiry, datetime.min.time()),
            action=action,
            quantity=quantity,
            premium=float(option_row.get('ltp', 0)),
            greeks=Greeks(
                delta=float(option_row.get('delta', 0)),
                gamma=float(option_row.get('gamma', 0)),
                theta=float(option_row.get('theta', 0)),
                vega=float(option_row.get('vega', 0))
            ),
            instrument_key=str(option_row.get('instrument_key', ''))
        )
    
    def _calculate_portfolio_greeks(self, legs: List[OptionLeg]) -> Greeks:
        """Calculate portfolio Greeks by summing leg Greeks"""
        portfolio_greeks = Greeks(delta=0, gamma=0, theta=0, vega=0)
        for leg in legs:
            portfolio_greeks = portfolio_greeks + leg.total_greeks
        return portfolio_greeks
    
    def _generate_long_straddle(
        self,
        underlying: str,
        option_chain: pd.DataFrame,
        spot_price: float,
        expiry: date
    ) -> Optional[OptionStrategy]:
        """Generate long straddle strategy"""
        try:
            # Find ATM call and put
            call_row = self._find_closest_option(option_chain, 'call', spot_price, expiry)
            put_row = self._find_closest_option(option_chain, 'put', spot_price, expiry)
            
            if call_row is None or put_row is None:
                return None
            
            legs = [
                self._create_option_leg(call_row, 'call', expiry, 'BUY'),
                self._create_option_leg(put_row, 'put', expiry, 'BUY')
            ]
            
            net_premium = sum(leg.total_premium for leg in legs)
            
            strategy = OptionStrategy(
                strategy_type=BasicStrategyType.LONG_STRADDLE,
                legs=legs,
                underlying=underlying,
                underlying_price=spot_price,
                regime=None,  # Will be set by caller
                max_profit=float('inf'),
                max_loss=abs(net_premium),
                net_credit_debit=net_premium,
                portfolio_greeks=self._calculate_portfolio_greeks(legs),
                created_at=datetime.now(),
                expiry_date=datetime.combine(expiry, datetime.min.time()),
                days_to_expiry=(expiry - datetime.now().date()).days
            )
            
            return strategy
            
        except Exception as e:
            logger.error(f"Failed to generate long straddle: {e}")
            return None
    
    def _generate_short_straddle(
        self,
        underlying: str,
        option_chain: pd.DataFrame,
        spot_price: float,
        expiry: date
    ) -> Optional[OptionStrategy]:
        """Generate short straddle strategy"""
        try:
            # Find ATM call and put
            call_row = self._find_closest_option(option_chain, 'call', spot_price, expiry)
            put_row = self._find_closest_option(option_chain, 'put', spot_price, expiry)
            
            if call_row is None or put_row is None:
                return None
            
            legs = [
                self._create_option_leg(call_row, 'call', expiry, 'SELL'),
                self._create_option_leg(put_row, 'put', expiry, 'SELL')
            ]
            
            net_premium = sum(leg.total_premium for leg in legs)
            
            strategy = OptionStrategy(
                strategy_type=BasicStrategyType.LONG_STRADDLE,  # Use existing enum
                underlying=underlying,
                legs=legs,
                max_profit=abs(net_premium),
                max_loss=float('inf'),
                breakeven_points=[legs[0].strike - abs(net_premium), legs[0].strike + abs(net_premium)],
                net_premium=net_premium,
                description=f"Short Straddle on {underlying}"
            )
            
            return strategy
            
        except Exception as e:
            logger.error(f"Failed to generate short straddle: {e}")
            return None
    
    def _generate_iron_condor(
        self,
        underlying: str,
        option_chain: pd.DataFrame,
        spot_price: float,
        expiry: date
    ) -> Optional[OptionStrategy]:
        """Generate iron condor strategy"""
        try:
            # Define strikes (5% OTM on each side)
            otm_distance = spot_price * 0.05
            put_long_strike = spot_price - otm_distance * 2
            put_short_strike = spot_price - otm_distance
            call_short_strike = spot_price + otm_distance
            call_long_strike = spot_price + otm_distance * 2
            
            # Find options
            put_long_row = self._find_closest_option(option_chain, 'put', put_long_strike, expiry)
            put_short_row = self._find_closest_option(option_chain, 'put', put_short_strike, expiry)
            call_short_row = self._find_closest_option(option_chain, 'call', call_short_strike, expiry)
            call_long_row = self._find_closest_option(option_chain, 'call', call_long_strike, expiry)
            
            if not all([put_long_row is not None, put_short_row is not None, 
                       call_short_row is not None, call_long_row is not None]):
                return None
            
            legs = [
                self._create_option_leg(put_long_row, 'put', expiry, 'BUY'),
                self._create_option_leg(put_short_row, 'put', expiry, 'SELL'),
                self._create_option_leg(call_short_row, 'call', expiry, 'SELL'),
                self._create_option_leg(call_long_row, 'call', expiry, 'BUY')
            ]
            
            net_premium = sum(leg.total_premium for leg in legs)
            
            strategy = OptionStrategy(
                strategy_type=BasicStrategyType.IRON_CONDOR,
                underlying=underlying,
                legs=legs,
                max_profit=abs(net_premium) if net_premium < 0 else 0,
                max_loss=abs(net_premium) if net_premium > 0 else 0,
                breakeven_points=[put_short_row['strike'] - abs(net_premium), 
                                call_short_row['strike'] + abs(net_premium)],
                net_premium=net_premium,
                description=f"Iron Condor on {underlying}"
            )
            
            return strategy
            
        except Exception as e:
            logger.error(f"Failed to generate iron condor: {e}")
            return None
    
    def _generate_calendar_spread(
        self,
        underlying: str,
        option_chain: pd.DataFrame,
        spot_price: float,
        expiry: date
    ) -> Optional[OptionStrategy]:
        """Generate calendar spread strategy"""
        try:
            # Find near and far expiries
            near_expiry = expiry
            
            # Find a far expiry (try to find one 30 days later)
            far_expiry = self._find_nearest_expiry(option_chain, 
                                                 (expiry - datetime.now().date()).days + 20,
                                                 (expiry - datetime.now().date()).days + 50)
            
            if far_expiry is None:
                return None
            
            # Find ATM calls for both expiries
            near_call = self._find_closest_option(option_chain, 'call', spot_price, near_expiry)
            far_call = self._find_closest_option(option_chain, 'call', spot_price, far_expiry)
            
            if near_call is None or far_call is None:
                return None
            
            legs = [
                self._create_option_leg(near_call, 'call', near_expiry, 'SELL'),
                self._create_option_leg(far_call, 'call', far_expiry, 'BUY')
            ]
            
            net_premium = sum(leg.total_premium for leg in legs)
            
            strategy = OptionStrategy(
                strategy_type=BasicStrategyType.CALENDAR_SPREAD,
                underlying=underlying,
                legs=legs,
                max_profit=abs(net_premium) * 2,  # Simplified calculation
                max_loss=abs(net_premium) if net_premium > 0 else 0,
                breakeven_points=[spot_price],
                net_premium=net_premium,
                description=f"Calendar Spread on {underlying}"
            )
            
            return strategy
            
        except Exception as e:
            logger.error(f"Failed to generate calendar spread: {e}")
            return None
    
    def _generate_long_call(
        self,
        underlying: str,
        option_chain: pd.DataFrame,
        spot_price: float,
        expiry: date
    ) -> Optional[OptionStrategy]:
        """Generate simple long call as ultimate fallback"""
        try:
            # Find ATM or slightly OTM call
            target_strike = spot_price * 1.02  # 2% OTM
            call_row = self._find_closest_option(option_chain, 'call', target_strike, expiry)
            
            if call_row is None:
                return None
            
            leg = self._create_option_leg(call_row, 'call', expiry, 'BUY')
            
            strategy = OptionStrategy(
                strategy_type=BasicStrategyType.LONG_STRADDLE,  # Use existing enum
                underlying=underlying,
                legs=[leg],
                max_profit=float('inf'),
                max_loss=leg.total_premium,
                breakeven_points=[leg.strike + leg.premium],
                net_premium=leg.total_premium,
                description=f"Long Call on {underlying}"
            )
            
            return strategy
            
        except Exception as e:
            logger.error(f"Failed to generate long call: {e}")
            return None
