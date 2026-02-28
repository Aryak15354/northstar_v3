"""
Options Strategy Generator

Generates options trading strategies based on detected regime.
Supports Iron Condor, Calendar Spread, and Long Straddle strategies.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Dict, Any

import pandas as pd
import numpy as np

from src.volatility.regime_detector import VolatilityRegime

logger = logging.getLogger(__name__)


class StrategyType(Enum):
    """Options strategy types"""
    IRON_CONDOR = "iron_condor"
    IRON_BUTTERFLY = "iron_butterfly"
    CALENDAR_SPREAD = "calendar_spread"
    LONG_STRADDLE = "long_straddle"
    LONG_STRANGLE = "long_strangle"
    SHORT_STRANGLE = "short_strangle"
    BULL_CALL_SPREAD = "bull_call_spread"
    BEAR_PUT_SPREAD = "bear_put_spread"


@dataclass
class Greeks:
    """Option Greeks"""
    delta: float
    gamma: float
    theta: float
    vega: float
    
    def __add__(self, other: 'Greeks') -> 'Greeks':
        """Add Greeks together for portfolio aggregation"""
        return Greeks(
            delta=self.delta + other.delta,
            gamma=self.gamma + other.gamma,
            theta=self.theta + other.theta,
            vega=self.vega + other.vega
        )
    
    def __mul__(self, scalar: float) -> 'Greeks':
        """Multiply Greeks by scalar (for position sizing)"""
        return Greeks(
            delta=self.delta * scalar,
            gamma=self.gamma * scalar,
            theta=self.theta * scalar,
            vega=self.vega * scalar
        )


@dataclass
class OptionLeg:
    """Single option leg in a strategy"""
    strike: float
    option_type: str  # 'CE' or 'PE'
    expiry: datetime
    action: str  # 'BUY' or 'SELL'
    quantity: int  # Number of contracts
    premium: float  # Premium per contract
    greeks: Greeks
    instrument_key: str  # Upstox instrument key
    
    @property
    def total_premium(self) -> float:
        """Total premium for this leg"""
        multiplier = 1 if self.action == 'BUY' else -1
        return self.premium * self.quantity * multiplier
    
    @property
    def total_greeks(self) -> Greeks:
        """Total Greeks for this leg"""
        multiplier = 1 if self.action == 'BUY' else -1
        return self.greeks * (self.quantity * multiplier)


@dataclass
class OptionStrategy:
    """Complete options strategy"""
    strategy_type: StrategyType
    legs: List[OptionLeg]
    underlying: str  # 'NIFTY' or 'BANKNIFTY'
    underlying_price: float
    regime: VolatilityRegime
    
    # Risk metrics
    max_loss: float
    max_profit: float
    net_credit_debit: float  # Positive = credit, negative = debit
    
    # Greeks
    portfolio_greeks: Greeks
    
    # Metadata
    created_at: datetime
    expiry_date: datetime
    days_to_expiry: int
    
    # Validation flags
    is_valid: bool = True
    validation_errors: List[str] = None
    
    def __post_init__(self):
        if self.validation_errors is None:
            self.validation_errors = []
    
    @property
    def total_quantity(self) -> int:
        """Total number of contracts across all legs"""
        return sum(leg.quantity for leg in self.legs)
    
    @property
    def risk_reward_ratio(self) -> float:
        """Risk-reward ratio (max_loss / max_profit)"""
        if self.max_profit <= 0:
            return float('inf')
        return abs(self.max_loss) / self.max_profit
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert strategy to dictionary for serialization"""
        return {
            'strategy_type': self.strategy_type.value,
            'underlying': self.underlying,
            'underlying_price': self.underlying_price,
            'regime': self.regime.value,
            'max_loss': self.max_loss,
            'max_profit': self.max_profit,
            'net_credit_debit': self.net_credit_debit,
            'portfolio_greeks': {
                'delta': self.portfolio_greeks.delta,
                'gamma': self.portfolio_greeks.gamma,
                'theta': self.portfolio_greeks.theta,
                'vega': self.portfolio_greeks.vega
            },
            'created_at': self.created_at.isoformat(),
            'expiry_date': self.expiry_date.isoformat(),
            'days_to_expiry': self.days_to_expiry,
            'is_valid': self.is_valid,
            'validation_errors': self.validation_errors,
            'legs': [
                {
                    'strike': leg.strike,
                    'option_type': leg.option_type,
                    'expiry': leg.expiry.isoformat(),
                    'action': leg.action,
                    'quantity': leg.quantity,
                    'premium': leg.premium,
                    'instrument_key': leg.instrument_key
                }
                for leg in self.legs
            ]
        }


class StrategyGenerator:
    """
    Generates options trading strategies based on regime
    
    Regime-Strategy Mapping:
    - LOW_VOL_SELL / HIGH_VOL_SELL → Iron Condor (sell premium)
    - RISING_VOL_BUY → Calendar Spread or Long Straddle (buy vol)
    - CRASH_HEDGE → Long Straddle (tail hedge)
    - NEUTRAL → No trade
    """
    
    # Lot sizes
    LOT_SIZES = {
        'NIFTY': 65,
        'BANKNIFTY': 30,
        'FINNIFTY': 60,
        'MIDCPNIFTY': 120
    }
    
    def __init__(self, config: Any):
        """
        Initialize strategy generator
        
        Args:
            config: Strategy generation configuration
        """
        self.config = config
        logger.info("StrategyGenerator initialized")

    def _get_expiry_window(self, section: str, default_min: int, default_max: int) -> tuple[int, int]:
        """
        Resolve expiry window from strategy config with safe defaults.
        Expected schema: config.<section>.expiry_days = [min_days, max_days]
        """
        try:
            block = getattr(self.config, section, None)
            if block is None and isinstance(self.config, dict):
                block = self.config.get(section)
            expiry_days = block.get("expiry_days") if isinstance(block, dict) else getattr(block, "expiry_days", None)
            if isinstance(expiry_days, (list, tuple)) and len(expiry_days) >= 2:
                lo, hi = int(expiry_days[0]), int(expiry_days[1])
                if lo > 0 and hi >= lo:
                    return lo, hi
        except Exception:
            pass
        return default_min, default_max

    def _normalize_regime(
        self, regime: Any
    ) -> tuple[str, Optional[VolatilityRegime]]:
        """
        Normalize regime inputs across legacy options enum and unified enum.

        Returns:
            (routing_token, normalized VolatilityRegime or None)
        """
        raw = str(getattr(regime, "value", regime)).strip().lower()
        mapping = {
            "low_vol": ("low_vol", VolatilityRegime.LOW_VOL),
            "high_vol": ("high_vol", VolatilityRegime.HIGH_VOL),
            "transition": ("transition", VolatilityRegime.TRANSITION),
            "crisis": ("crisis", VolatilityRegime.CRISIS),
            "low_vol_sell": ("low_vol_sell", VolatilityRegime.LOW_VOL),
            "high_vol_sell": ("high_vol_sell", VolatilityRegime.HIGH_VOL),
            "rising_vol_buy": ("rising_vol_buy", VolatilityRegime.TRANSITION),
            "crash_hedge": ("crash_hedge", VolatilityRegime.CRISIS),
            "neutral": ("neutral", VolatilityRegime.TRANSITION),
        }
        return mapping.get(raw, (raw, None))
    
    def generate_strategy(
        self,
        regime: Any,
        option_chain: pd.DataFrame,
        underlying: str = 'NIFTY'
    ) -> Optional[OptionStrategy]:
        """
        Generate strategy for given regime
        
        Args:
            regime: Detected market regime (legacy or unified enum)
            option_chain: Current option chain data
            underlying: Underlying instrument ('NIFTY' or 'BANKNIFTY')
        
        Returns:
            OptionStrategy if valid strategy found, None otherwise
        """
        regime_token, normalized_regime = self._normalize_regime(regime)
        logger.info(f"Generating strategy for regime: {regime_token}, underlying: {underlying}")

        if regime_token in {"neutral", "transition"}:
            logger.info("TRANSITION regime - no trade signal")
            return None

        # Route to appropriate strategy generator
        if regime_token in {"low_vol", "high_vol", "low_vol_sell", "high_vol_sell"}:
            return self._generate_iron_condor(
                normalized_regime or VolatilityRegime.LOW_VOL,
                option_chain,
                underlying
            )
        if regime_token == "rising_vol_buy":
            # Legacy options path: buy-vol regime uses calendar spread.
            return self._generate_calendar_spread(
                normalized_regime or VolatilityRegime.TRANSITION,
                option_chain,
                underlying
            )
        if regime_token in {"crisis", "crash_hedge"}:
            return self._generate_long_straddle(
                normalized_regime or VolatilityRegime.CRISIS,
                option_chain,
                underlying
            )
        
        return None
    
    def _generate_iron_condor(
        self,
        regime: VolatilityRegime,
        option_chain: pd.DataFrame,
        underlying: str
    ) -> Optional[OptionStrategy]:
        """
        Generate Iron Condor strategy
        
        Structure:
        - Sell OTM call (16-20 delta)
        - Buy further OTM call (5-10 delta)
        - Sell OTM put (16-20 delta)
        - Buy further OTM put (5-10 delta)
        
        Requirements:
        - Net credit ≥ 0.25 × max loss
        - Lot size validation
        """
        logger.info("Generating Iron Condor strategy")
        
        if option_chain.empty:
            logger.warning("Empty option chain")
            return None
        
        spot = option_chain['underlying_price'].iloc[0]
        lot_size = self._get_lot_size(underlying)
        
        # Use configured expiry window (fallback to legacy-safe defaults).
        min_days, max_days = self._get_expiry_window("iron_condor", 15, 45)
        expiry = self._find_expiry(option_chain, min_days=min_days, max_days=max_days)
        if expiry is None:
            # Live chains can be short-dated; relax window but keep >= 5 DTE.
            expiry = self._find_expiry(
                option_chain,
                min_days=max(5, min_days // 2),
                max_days=max_days + 30
            )
        if expiry is None:
            logger.warning("No suitable expiry found")
            return None
        
        # Filter to selected expiry
        chain = option_chain[option_chain['expiry'] == expiry].copy()
        
        # Find strikes by delta
        # Short call: 16-20 delta OTM
        short_call = self._find_strike_by_delta(
            chain, 'CE', target_delta=0.18, delta_range=(0.16, 0.20)
        )
        
        # Long call: 5-10 delta OTM (further out)
        long_call = self._find_strike_by_delta(
            chain, 'CE', target_delta=0.08, delta_range=(0.05, 0.10),
            min_strike=short_call['strike'] if short_call else spot
        )
        
        # Short put: 16-20 delta OTM
        short_put = self._find_strike_by_delta(
            chain, 'PE', target_delta=-0.18, delta_range=(-0.20, -0.16)
        )
        
        # Long put: 5-10 delta OTM (further out)
        long_put = self._find_strike_by_delta(
            chain, 'PE', target_delta=-0.08, delta_range=(-0.10, -0.05),
            max_strike=short_put['strike'] if short_put else spot
        )
        
        # Validate all legs found
        if not all([short_call, long_call, short_put, long_put]):
            logger.warning("Could not find all required strikes for Iron Condor")
            return None
        
        # Create legs
        legs = [
            self._create_leg(short_call, 'SELL', lot_size),
            self._create_leg(long_call, 'BUY', lot_size),
            self._create_leg(short_put, 'SELL', lot_size),
            self._create_leg(long_put, 'BUY', lot_size)
        ]
        
        # Calculate risk metrics
        call_spread_width = long_call['strike'] - short_call['strike']
        put_spread_width = short_put['strike'] - long_put['strike']
        max_loss = max(call_spread_width, put_spread_width) * lot_size
        
        net_credit = sum(leg.total_premium for leg in legs)
        max_profit = net_credit
        
        # Calculate portfolio Greeks
        portfolio_greeks = self._calculate_portfolio_greeks(legs)
        
        # Calculate days to expiry
        days_to_expiry = (expiry - datetime.now()).days
        
        # Create strategy
        strategy = OptionStrategy(
            strategy_type=StrategyType.IRON_CONDOR,
            legs=legs,
            underlying=underlying,
            underlying_price=spot,
            regime=regime,
            max_loss=max_loss,
            max_profit=max_profit,
            net_credit_debit=net_credit,
            portfolio_greeks=portfolio_greeks,
            created_at=datetime.now(),
            expiry_date=expiry,
            days_to_expiry=days_to_expiry
        )
        
        # Validate strategy
        self._validate_strategy(strategy)
        
        if strategy.is_valid:
            logger.info(
                f"Generated Iron Condor: credit={net_credit:.2f}, "
                f"max_loss={max_loss:.2f}, RR={strategy.risk_reward_ratio:.2f}"
            )
        
        return strategy
    
    def _generate_calendar_spread(
        self,
        regime: VolatilityRegime,
        option_chain: pd.DataFrame,
        underlying: str
    ) -> Optional[OptionStrategy]:
        """
        Generate Calendar Spread strategy
        
        Structure:
        - Sell near-term ATM option (7-14 days)
        - Buy far-term ATM option (30-45 days)
        
        Can be call or put calendar spread
        """
        logger.info("Generating Calendar Spread strategy")
        
        if option_chain.empty:
            logger.warning("Empty option chain")
            return None
        
        spot = option_chain['underlying_price'].iloc[0]
        lot_size = self._get_lot_size(underlying)
        
        near_min, near_max = 7, 14
        far_min, far_max = 30, 45
        try:
            block = getattr(self.config, "calendar_spread", None)
            if block is None and isinstance(self.config, dict):
                block = self.config.get("calendar_spread")
            if isinstance(block, dict):
                near = block.get("near_term_days")
                far = block.get("far_term_days")
            else:
                near = getattr(block, "near_term_days", None)
                far = getattr(block, "far_term_days", None)
            if isinstance(near, (list, tuple)) and len(near) >= 2:
                near_min, near_max = int(near[0]), int(near[1])
            if isinstance(far, (list, tuple)) and len(far) >= 2:
                far_min, far_max = int(far[0]), int(far[1])
        except Exception:
            pass

        # Find near-term expiry
        near_expiry = self._find_expiry(option_chain, min_days=near_min, max_days=near_max)
        if near_expiry is None:
            near_expiry = self._find_expiry(option_chain, min_days=max(5, near_min - 2), max_days=near_max + 7)
        if near_expiry is None:
            logger.warning("No suitable near-term expiry found")
            return None
        
        # Find far-term expiry
        far_expiry = self._find_expiry(option_chain, min_days=far_min, max_days=far_max)
        if far_expiry is None:
            far_expiry = self._find_expiry(option_chain, min_days=max(near_max + 1, 15), max_days=far_max + 30)
        if far_expiry is None:
            logger.warning("No suitable far-term expiry found")
            return None
        
        # Use call calendar spread (can also do put calendar)
        option_type = 'CE'
        
        # Find ATM strike for near-term
        near_chain = option_chain[
            (option_chain['expiry'] == near_expiry) &
            (option_chain['option_type'] == option_type)
        ].copy()
        
        if near_chain.empty:
            logger.warning("No near-term options found")
            return None
        
        # Find ATM strike
        near_chain['distance_to_atm'] = abs(near_chain['strike'] - spot)
        near_atm = near_chain.loc[near_chain['distance_to_atm'].idxmin()]
        atm_strike = near_atm['strike']
        
        # Find same strike in far-term
        far_chain = option_chain[
            (option_chain['expiry'] == far_expiry) &
            (option_chain['option_type'] == option_type) &
            (option_chain['strike'] == atm_strike)
        ]
        
        if far_chain.empty:
            logger.warning(f"No far-term option found at strike {atm_strike}")
            return None
        
        far_atm = far_chain.iloc[0]
        
        # Create legs
        legs = [
            self._create_leg(near_atm.to_dict(), 'SELL', lot_size),
            self._create_leg(far_atm.to_dict(), 'BUY', lot_size)
        ]
        
        # Calculate risk metrics
        # Max loss = net debit (cost to enter)
        net_debit = sum(leg.total_premium for leg in legs)
        max_loss = abs(net_debit)
        
        # Max profit is theoretical (depends on vol expansion)
        # Conservative estimate: 50% of far-term premium
        max_profit = far_atm['ltp'] * lot_size * 0.5 if 'ltp' in far_atm else max_loss * 2
        
        # Calculate portfolio Greeks
        portfolio_greeks = self._calculate_portfolio_greeks(legs)
        
        # Use near-term expiry for days to expiry
        days_to_expiry = (near_expiry - datetime.now()).days
        
        # Create strategy
        strategy = OptionStrategy(
            strategy_type=StrategyType.CALENDAR_SPREAD,
            legs=legs,
            underlying=underlying,
            underlying_price=spot,
            regime=regime,
            max_loss=max_loss,
            max_profit=max_profit,
            net_credit_debit=net_debit,
            portfolio_greeks=portfolio_greeks,
            created_at=datetime.now(),
            expiry_date=near_expiry,
            days_to_expiry=days_to_expiry
        )
        
        # Validate strategy
        self._validate_strategy(strategy)
        
        if strategy.is_valid:
            logger.info(
                f"Generated Calendar Spread: debit={abs(net_debit):.2f}, "
                f"max_loss={max_loss:.2f}, RR={strategy.risk_reward_ratio:.2f}"
            )
        
        return strategy
    
    def _generate_long_straddle(
        self,
        regime: VolatilityRegime,
        option_chain: pd.DataFrame,
        underlying: str
    ) -> Optional[OptionStrategy]:
        """
        Generate Long Straddle strategy
        
        Structure:
        - Buy ATM call
        - Buy ATM put
        
        Same strike, same expiry (30-60 days)
        """
        logger.info("Generating Long Straddle strategy")
        
        if option_chain.empty:
            logger.warning("Empty option chain")
            return None
        
        spot = option_chain['underlying_price'].iloc[0]
        lot_size = self._get_lot_size(underlying)
        
        min_days, max_days = self._get_expiry_window("long_straddle", 30, 60)
        expiry = self._find_expiry(option_chain, min_days=min_days, max_days=max_days)
        if expiry is None:
            expiry = self._find_expiry(option_chain, min_days=max(7, min_days // 2), max_days=max_days + 30)
        if expiry is None:
            logger.warning("No suitable expiry found")
            return None
        
        # Filter to selected expiry
        chain = option_chain[option_chain['expiry'] == expiry].copy()
        
        # Find ATM strike
        chain['distance_to_atm'] = abs(chain['strike'] - spot)
        atm_strike = chain.loc[chain['distance_to_atm'].idxmin(), 'strike']
        
        # Get ATM call
        atm_call = chain[
            (chain['strike'] == atm_strike) &
            (chain['option_type'] == 'CE')
        ]
        
        if atm_call.empty:
            logger.warning("No ATM call found")
            return None
        
        atm_call = atm_call.iloc[0]
        
        # Get ATM put
        atm_put = chain[
            (chain['strike'] == atm_strike) &
            (chain['option_type'] == 'PE')
        ]
        
        if atm_put.empty:
            logger.warning("No ATM put found")
            return None
        
        atm_put = atm_put.iloc[0]
        
        # Create legs
        legs = [
            self._create_leg(atm_call.to_dict(), 'BUY', lot_size),
            self._create_leg(atm_put.to_dict(), 'BUY', lot_size)
        ]
        
        # Calculate risk metrics
        # Max loss = total premium paid
        total_premium = sum(leg.total_premium for leg in legs)
        max_loss = abs(total_premium)
        
        # Max profit is unlimited (theoretically)
        # Use conservative estimate: 2x premium
        max_profit = max_loss * 2
        
        # Calculate portfolio Greeks
        portfolio_greeks = self._calculate_portfolio_greeks(legs)
        
        # Calculate days to expiry
        days_to_expiry = (expiry - datetime.now()).days
        
        # Create strategy
        strategy = OptionStrategy(
            strategy_type=StrategyType.LONG_STRADDLE,
            legs=legs,
            underlying=underlying,
            underlying_price=spot,
            regime=regime,
            max_loss=max_loss,
            max_profit=max_profit,
            net_credit_debit=total_premium,
            portfolio_greeks=portfolio_greeks,
            created_at=datetime.now(),
            expiry_date=expiry,
            days_to_expiry=days_to_expiry
        )
        
        # Validate strategy
        self._validate_strategy(strategy)
        
        if strategy.is_valid:
            logger.info(
                f"Generated Long Straddle: cost={max_loss:.2f}, "
                f"max_profit={max_profit:.2f}, RR={strategy.risk_reward_ratio:.2f}"
            )
        
        return strategy
    
    def _get_lot_size(self, underlying: str) -> int:
        """Get lot size for underlying"""
        return self.LOT_SIZES.get(underlying, 50)
    
    def _calculate_portfolio_greeks(self, legs: List[OptionLeg]) -> Greeks:
        """Calculate portfolio Greeks by summing leg Greeks"""
        portfolio_greeks = Greeks(delta=0, gamma=0, theta=0, vega=0)
        for leg in legs:
            portfolio_greeks = portfolio_greeks + leg.total_greeks
        return portfolio_greeks
    
    def _validate_strategy(self, strategy: OptionStrategy) -> None:
        """
        Validate strategy meets all requirements
        
        Modifies strategy.is_valid and strategy.validation_errors in place
        """
        errors = []
        
        # Check lot size
        lot_size = self._get_lot_size(strategy.underlying)
        for leg in strategy.legs:
            if leg.quantity % lot_size != 0:
                errors.append(f"Leg quantity {leg.quantity} not multiple of lot size {lot_size}")
        
        # Check premium adequacy for credit spreads
        if strategy.net_credit_debit > 0:  # Credit spread
            min_credit = 0.25 * abs(strategy.max_loss)
            if strategy.net_credit_debit < min_credit:
                errors.append(
                    f"Net credit {strategy.net_credit_debit:.2f} < "
                    f"minimum {min_credit:.2f} (0.25 × max loss)"
                )
        
        # Update strategy
        strategy.is_valid = len(errors) == 0
        strategy.validation_errors = errors
        
        if not strategy.is_valid:
            logger.warning(f"Strategy validation failed: {errors}")
    
    def _find_expiry(
        self,
        option_chain: pd.DataFrame,
        min_days: int,
        max_days: int
    ) -> Optional[datetime]:
        """
        Find suitable expiry date
        
        Args:
            option_chain: Option chain data
            min_days: Minimum days to expiry
            max_days: Maximum days to expiry
        
        Returns:
            Expiry datetime or None
        """
        if 'expiry' not in option_chain.columns:
            logger.warning("No expiry column in option chain")
            return None
        
        # Get unique expiries
        expiries = option_chain['expiry'].unique()
        
        # Convert to datetime if needed
        if not isinstance(expiries[0], datetime):
            expiries = pd.to_datetime(expiries)
        
        now = datetime.now()
        
        # Filter by days to expiry
        valid_expiries = []
        for expiry in expiries:
            days = (expiry - now).days
            if min_days <= days <= max_days:
                valid_expiries.append(expiry)
        
        if not valid_expiries:
            logger.warning(f"No expiry found between {min_days} and {max_days} days")
            return None
        
        # Return closest to middle of range
        target_days = (min_days + max_days) / 2
        best_expiry = min(valid_expiries, key=lambda e: abs((e - now).days - target_days))
        
        logger.debug(f"Selected expiry: {best_expiry} ({(best_expiry - now).days} days)")
        return best_expiry
    
    def _find_strike_by_delta(
        self,
        option_chain: pd.DataFrame,
        option_type: str,
        target_delta: float,
        delta_range: tuple,
        min_strike: float = None,
        max_strike: float = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find strike with delta in target range
        
        Args:
            option_chain: Option chain data
            option_type: 'CE' or 'PE'
            target_delta: Target delta value
            delta_range: (min_delta, max_delta) acceptable range
            min_strike: Minimum strike (for calls)
            max_strike: Maximum strike (for puts)
        
        Returns:
            Option data dict or None
        """
        # Filter by option type
        chain = option_chain[option_chain['option_type'] == option_type].copy()
        
        if chain.empty:
            return None
        
        # Apply strike filters
        if min_strike is not None:
            chain = chain[chain['strike'] > min_strike]
        if max_strike is not None:
            chain = chain[chain['strike'] < max_strike]
        
        if chain.empty:
            return None
        
        # If delta column exists, use it
        if 'delta' in chain.columns:
            # Filter by delta range
            min_delta, max_delta = delta_range
            chain = chain[
                (chain['delta'] >= min_delta) &
                (chain['delta'] <= max_delta)
            ]
            
            if chain.empty:
                return None
            
            # Find closest to target
            chain['delta_diff'] = abs(chain['delta'] - target_delta)
            best = chain.loc[chain['delta_diff'].idxmin()]
        else:
            # Fallback: estimate by moneyness
            # For calls: delta ≈ 0.5 + (strike - spot) / (2 * spot * sqrt(T))
            # Simplified: use moneyness as proxy
            spot = chain['underlying_price'].iloc[0]
            
            if option_type == 'CE':
                # For calls, higher strike = lower delta
                # Target delta 0.18 ≈ 10% OTM
                target_moneyness = 1 + (0.5 - abs(target_delta)) * 0.2
                chain['moneyness'] = chain['strike'] / spot
                chain['moneyness_diff'] = abs(chain['moneyness'] - target_moneyness)
                best = chain.loc[chain['moneyness_diff'].idxmin()]
            else:
                # For puts, lower strike = lower delta (more negative)
                target_moneyness = 1 - (0.5 - abs(target_delta)) * 0.2
                chain['moneyness'] = chain['strike'] / spot
                chain['moneyness_diff'] = abs(chain['moneyness'] - target_moneyness)
                best = chain.loc[chain['moneyness_diff'].idxmin()]
        
        return best.to_dict()
    
    def _create_leg(
        self,
        option_data: Dict[str, Any],
        action: str,
        quantity: int
    ) -> OptionLeg:
        """
        Create option leg from option data
        
        Args:
            option_data: Option data dict
            action: 'BUY' or 'SELL'
            quantity: Number of contracts
        
        Returns:
            OptionLeg
        """
        # Extract Greeks if available
        greeks = Greeks(
            delta=option_data.get('delta', 0.0),
            gamma=option_data.get('gamma', 0.0),
            theta=option_data.get('theta', 0.0),
            vega=option_data.get('vega', 0.0)
        )
        
        # Calculate premium (use mid price)
        bid = option_data.get('bid', 0)
        ask = option_data.get('ask', 0)
        premium = (bid + ask) / 2 if bid and ask else option_data.get('ltp', 0)
        
        return OptionLeg(
            strike=option_data['strike'],
            option_type=option_data['option_type'],
            expiry=option_data['expiry'],
            action=action,
            quantity=quantity,
            premium=premium,
            greeks=greeks,
            instrument_key=option_data.get('instrument_key', '')
        )
