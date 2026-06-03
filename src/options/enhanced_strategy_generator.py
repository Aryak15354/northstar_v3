"""
Enhanced Strategy Generator for Options Paper Engine

Integrates the unified volatility engine's advanced strategies into the options paper engine.
Provides backward compatibility while adding butterfly, condor, strangle, ratio spreads, etc.
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

# Import from unified volatility engine
from src.volatility.strategy_generator import StrategyGenerator as UnifiedGenerator
from src.volatility.strategy_ast import (
    OptionType, OptionLeg as UnifiedLeg, OptionStructure,
    Straddle, Strangle, Butterfly, Condor, Calendar, Spread, Call, Put
)
from src.volatility.greeks_aggregator import GreeksAggregator
from src.volatility.config import (
    TargetGreeks, Constraints, MarketState, PrimitiveExposure, PrimitiveType
)

logger = logging.getLogger(__name__)

warnings.warn(
    "src.options.enhanced_strategy_generator is deprecated for Northstar V3; "
    "use src.options.enhanced_strategy_generator_v3.EnhancedStrategyGeneratorV3.",
    DeprecationWarning,
    stacklevel=2,
)


class EnhancedStrategyType(Enum):
    """Extended strategy types including advanced strategies"""
    # Basic strategies (backward compatibility)
    IRON_CONDOR = "iron_condor"
    CALENDAR_SPREAD = "calendar_spread"
    LONG_STRADDLE = "long_straddle"
    
    # Advanced strategies from unified engine
    BUTTERFLY = "butterfly"
    STRANGLE = "strangle"
    SHORT_STRADDLE = "short_straddle"
    SHORT_STRANGLE = "short_strangle"
    CALL_SPREAD = "call_spread"
    PUT_SPREAD = "put_spread"
    RATIO_CALL_SPREAD = "ratio_call_spread"
    RATIO_PUT_SPREAD = "ratio_put_spread"
    DIAGONAL_SPREAD = "diagonal_spread"
    JADE_LIZARD = "jade_lizard"
    IRON_BUTTERFLY = "iron_butterfly"


@dataclass
class RegimeMapping:
    """Maps volatility regimes to target Greeks"""
    regime: str
    target_delta: float = 0.0
    target_gamma: float = 0.0
    target_vega: float = 0.0
    target_theta: float = 0.0
    preferred_strategies: List[EnhancedStrategyType] = None


class EnhancedStrategyGenerator:
    """
    Enhanced strategy generator that combines basic and advanced strategies.
    
    Provides backward compatibility with existing options paper engine while
    adding advanced strategies from the unified volatility engine.
    """
    
    def __init__(self, config: Any):
        self.config = config
        self.unified_generator = UnifiedGenerator()
        self.greeks_calculator = GreeksAggregator()
        
        # Regime to strategy mapping
        self.regime_mappings = {
            "low_vol_sell": RegimeMapping(
                regime="low_vol_sell",
                target_vega=-1.0,  # Short volatility
                target_theta=0.5,  # Positive theta
                preferred_strategies=[
                    EnhancedStrategyType.IRON_CONDOR,
                    EnhancedStrategyType.BUTTERFLY,
                    EnhancedStrategyType.SHORT_STRANGLE
                ]
            ),
            "high_vol_sell": RegimeMapping(
                regime="high_vol_sell",
                target_vega=-0.5,  # Moderate short vol
                target_gamma=-0.3,  # Short gamma
                preferred_strategies=[
                    EnhancedStrategyType.SHORT_STRADDLE,
                    EnhancedStrategyType.IRON_CONDOR,
                    EnhancedStrategyType.IRON_BUTTERFLY
                ]
            ),
            "rising_vol_buy": RegimeMapping(
                regime="rising_vol_buy",
                target_vega=1.0,   # Long volatility
                target_gamma=0.5,  # Long gamma
                preferred_strategies=[
                    EnhancedStrategyType.LONG_STRADDLE,
                    EnhancedStrategyType.STRANGLE,
                    EnhancedStrategyType.CALENDAR_SPREAD
                ]
            ),
            "falling_vol_buy": RegimeMapping(
                regime="falling_vol_buy",
                target_vega=0.3,   # Moderate long vol
                target_theta=-0.2,  # Accept some theta decay
                preferred_strategies=[
                    EnhancedStrategyType.CALENDAR_SPREAD,
                    EnhancedStrategyType.DIAGONAL_SPREAD,
                    EnhancedStrategyType.CALL_SPREAD
                ]
            )
        }
        
        logger.info("Enhanced strategy generator initialized with unified engine")
    
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
        Generate strategies using both basic and advanced approaches.
        
        Args:
            regime: Volatility regime
            underlying: Underlying symbol
            option_chain: Available options
            spot_price: Current spot price
            implied_vol: Implied volatility
            risk_free_rate: Risk-free rate
            
        Returns:
            List of option strategies
        """
        try:
            # Normalize regime
            regime_str = self._normalize_regime(regime)
            mapping = self.regime_mappings.get(regime_str)
            
            if not mapping:
                logger.warning(f"Unknown regime {regime_str}, using default")
                mapping = self.regime_mappings["rising_vol_buy"]
            
            # Get available expiries from option chain
            available_expiries = []
            if not option_chain.empty:
                unique_expiries = option_chain['expiry'].unique()
                for exp in unique_expiries:
                    if isinstance(exp, str):
                        exp_date = datetime.strptime(exp, '%Y-%m-%d').date()
                    elif hasattr(exp, 'date'):
                        exp_date = exp.date()
                    else:
                        exp_date = exp
                    
                    days_to_exp = (exp_date - datetime.now().date()).days
                    if 7 <= days_to_exp <= 60:  # Only use expiries 1-8 weeks out
                        available_expiries.append(exp_date)
            
            if not available_expiries:
                logger.warning(f"No suitable expiries found for {underlying}")
                # Fall back to basic strategy generation immediately
                return self._generate_single_basic_strategy(regime_str, underlying, option_chain, spot_price)
            
            # Use the closest expiry to 30 days
            target_expiry = min(available_expiries, key=lambda x: abs((x - datetime.now().date()).days - 30))
            
            # Try unified engine approach first
            try:
                # Create market state for unified engine with actual expiry
                market_state = MarketState(
                    spot_price=spot_price,
                    implied_vol=implied_vol,
                    risk_free_rate=risk_free_rate,
                    timestamp=datetime.combine(target_expiry, datetime.min.time())  # Use target expiry
                )
                
                # Create target Greeks from regime
                target_greeks = TargetGreeks(
                    delta=mapping.target_delta,
                    gamma=mapping.target_gamma,
                    vega=mapping.target_vega,
                    theta=mapping.target_theta
                )
                
                # Create constraints with available expiries
                constraints = Constraints(
                    max_legs=6,
                    max_cost=200000.0,  # ₹2L max for Indian markets
                    allowed_underlyings=[underlying],
                    max_dte=90,
                    min_dte=1  # More lenient for Indian markets
                )
                
                # Generate strategies using unified engine
                unified_strategies = self.unified_generator.generate(
                    target_greeks=target_greeks,
                    constraints=constraints,
                    state=market_state
                )
                
                # Convert unified strategies to options paper engine format
                converted_strategies = []
                for unified_strategy in unified_strategies:
                    try:
                        # Create a new strategy with corrected expiries
                        corrected_strategy = self._create_strategy_with_available_expiry(
                            unified_strategy, target_expiry, underlying, option_chain
                        )
                        if corrected_strategy:
                            converted_strategies.append(corrected_strategy)
                    except Exception as e:
                        logger.warning(f"Failed to convert strategy: {e}")
                        continue
                
                # If unified engine produced valid strategies, return the best one
                if converted_strategies:
                    return converted_strategies[0]
                    
            except Exception as e:
                logger.warning(f"Unified engine failed: {e}")
            
            # If unified engine didn't work, fall back to basic strategy generation
            logger.info("Falling back to basic strategy generation")
            return self._generate_single_basic_strategy(regime_str, underlying, option_chain, spot_price)
            
        except Exception as e:
            logger.error(f"Strategy generation failed: {e}")
            # Emergency fallback to basic straddle
            return self._generate_single_basic_strategy("rising_vol_buy", underlying, option_chain, spot_price)
    
    def _create_strategy_with_available_expiry(
        self,
        unified_strategy: OptionStructure,
        target_expiry: date,
        underlying: str,
        option_chain: pd.DataFrame
    ) -> Optional[OptionStrategy]:
        """Create strategy using available expiry instead of unified engine expiry"""
        try:
            # Determine strategy type from AST
            strategy_type = self._determine_strategy_type(unified_strategy.ast)
            
            # Create new legs with available expiry and matching options
            converted_legs = []
            total_premium = 0.0
            
            for unified_leg in unified_strategy.legs:
                # Find matching option in chain using available expiry
                option_row = self._find_option_in_chain(
                    option_chain,
                    unified_leg.option_type.value,
                    unified_leg.strike,
                    target_expiry  # Use available expiry instead of unified leg expiry
                )
                
                if option_row is None:
                    logger.warning(f"Could not find option for {unified_leg.option_type.value} {unified_leg.strike} {target_expiry}")
                    return None
                
                # Enhanced pricing validation
                premium = float(option_row.get('ltp', 0))
                bid = float(option_row.get('bid', 0))
                ask = float(option_row.get('ask', 0))
                
                # Validate option pricing
                if not self._validate_option_pricing(premium, bid, ask, unified_leg.strike, underlying):
                    logger.warning(f"Invalid pricing for {unified_leg}: premium={premium}, bid={bid}, ask={ask}")
                    return None
                
                # Use mid price if available and reasonable
                if bid > 0 and ask > 0 and ask > bid:
                    mid_price = (bid + ask) / 2
                    # Use mid if it's close to LTP, otherwise use LTP
                    if abs(mid_price - premium) / max(premium, 1) < 0.20:  # Within 20%
                        premium = mid_price
                
                # Create option leg with available expiry
                leg = OptionLeg(
                    option_type=unified_leg.option_type.value.upper(),  # Convert to CE/PE format
                    strike=unified_leg.strike,
                    expiry=datetime.combine(target_expiry, datetime.min.time()),
                    action='BUY' if unified_leg.quantity > 0 else 'SELL',
                    quantity=abs(unified_leg.quantity),
                    premium=premium,
                    greeks=Greeks(
                        delta=float(option_row.get('delta', 0)),
                        gamma=float(option_row.get('gamma', 0)),
                        theta=float(option_row.get('theta', 0)),
                        vega=float(option_row.get('vega', 0)),
                        rho=0.0
                    ),
                    instrument_key=str(option_row.get('instrument_key', ''))
                )
                converted_legs.append(leg)
                total_premium += leg.total_premium()
            
            # Validate overall strategy
            if not self._validate_strategy_structure(converted_legs, underlying):
                return None
            
            # Calculate risk metrics
            max_profit = self._calculate_max_profit_enhanced(converted_legs)
            max_loss = self._calculate_max_loss_enhanced(converted_legs)
            breakevens = self._calculate_breakevens_enhanced(converted_legs)
            
            # Final validation of risk metrics
            if not self._validate_risk_metrics(max_profit, max_loss, total_premium):
                return None
            
            # Create option strategy
            strategy = OptionStrategy(
                strategy_type=strategy_type,
                underlying=underlying,
                legs=converted_legs,
                max_profit=max_profit,
                max_loss=max_loss,
                breakeven_points=breakevens,
                net_premium=total_premium,
                description=f"{strategy_type.value} on {underlying}"
            )
            
            return strategy
            
        except Exception as e:
            logger.error(f"Failed to create strategy with available expiry: {e}")
            return None
    
    def _convert_unified_strategy(
        self,
        unified_strategy: OptionStructure,
        underlying: str,
        option_chain: pd.DataFrame
    ) -> Optional[OptionStrategy]:
        """Convert unified engine strategy to options paper engine format"""
        try:
            # Convert legs with improved validation
            converted_legs = []
            total_premium = 0.0
            
            for unified_leg in unified_strategy.legs:
                # Find matching option in chain
                option_row = self._find_option_in_chain(
                    option_chain,
                    unified_leg.option_type.value,
                    unified_leg.strike,
                    unified_leg.expiry
                )
                
                if option_row is None:
                    logger.warning(f"Could not find option for {unified_leg}")
                    return None
                
                # Enhanced pricing validation
                premium = float(option_row.get('ltp', 0))
                bid = float(option_row.get('bid', 0))
                ask = float(option_row.get('ask', 0))
                
                # Validate option pricing
                if not self._validate_option_pricing(premium, bid, ask, unified_leg.strike, underlying):
                    logger.warning(f"Invalid pricing for {unified_leg}: premium={premium}, bid={bid}, ask={ask}")
                    return None
                
                # Use mid price if available and reasonable
                if bid > 0 and ask > 0 and ask > bid:
                    mid_price = (bid + ask) / 2
                    # Use mid if it's close to LTP, otherwise use LTP
                    if abs(mid_price - premium) / max(premium, 1) < 0.20:  # Within 20%
                        premium = mid_price
                
                # Create option leg
                leg = OptionLeg(
                    option_type=unified_leg.option_type.value.upper(),  # Convert to CE/PE format
                    strike=unified_leg.strike,
                    expiry=datetime.combine(unified_leg.expiry, datetime.min.time()),
                    action='BUY' if unified_leg.quantity > 0 else 'SELL',
                    quantity=abs(unified_leg.quantity),
                    premium=premium,
                    greeks=Greeks(
                        delta=float(option_row.get('delta', 0)),
                        gamma=float(option_row.get('gamma', 0)),
                        theta=float(option_row.get('theta', 0)),
                        vega=float(option_row.get('vega', 0)),
                        rho=0.0
                    ),
                    instrument_key=str(option_row.get('instrument_key', ''))
                )
                converted_legs.append(leg)
                total_premium += leg.total_premium()
            
            # Validate overall strategy
            if not self._validate_strategy_structure(converted_legs, underlying):
                return None
            
            # Determine strategy type from AST
            strategy_type = self._determine_strategy_type(unified_strategy.ast)
            
            # Calculate risk metrics
            max_profit = self._calculate_max_profit_enhanced(converted_legs)
            max_loss = self._calculate_max_loss_enhanced(converted_legs)
            breakevens = self._calculate_breakevens_enhanced(converted_legs)
            
            # Final validation of risk metrics
            if not self._validate_risk_metrics(max_profit, max_loss, total_premium):
                return None
            
            # Create option strategy
            strategy = OptionStrategy(
                strategy_type=strategy_type,
                underlying=underlying,
                legs=converted_legs,
                max_profit=max_profit,
                max_loss=max_loss,
                breakeven_points=breakevens,
                net_premium=total_premium,
                description=f"{strategy_type.value} on {underlying}"
            )
            
            return strategy
            
        except Exception as e:
            logger.error(f"Failed to convert unified strategy: {e}")
            return None
    
    def _validate_option_pricing(self, premium: float, bid: float, ask: float, strike: float, underlying: str) -> bool:
        """Validate option pricing for reasonableness"""
        try:
            # Basic sanity checks
            if premium <= 0:
                return False
            
            # Premium should be reasonable relative to strike
            if premium > strike * 0.5:  # Premium shouldn't exceed 50% of strike
                return False
            
            # Bid-ask spread validation
            if bid > 0 and ask > 0:
                if ask <= bid:  # Ask should be higher than bid
                    return False
                
                spread_pct = (ask - bid) / max(premium, 1)
                if spread_pct > 0.50:  # Spread shouldn't exceed 50% of premium
                    return False
            
            # Premium should be within reasonable bounds
            if premium < 1.0:  # Minimum ₹1 premium
                return False
            
            if premium > 50000.0:  # Maximum ₹50k premium (sanity check)
                return False
            
            return True
            
        except Exception:
            return False
    
    def _validate_strategy_structure(self, legs: List[OptionLeg], underlying: str) -> bool:
        """Validate overall strategy structure"""
        try:
            if not legs:
                return False
            
            # Check for reasonable number of legs
            if len(legs) > 8:
                return False
            
            # Check for reasonable strike distribution
            strikes = [leg.strike for leg in legs]
            if len(set(strikes)) > 1:
                strike_range = max(strikes) - min(strikes)
                avg_strike = sum(strikes) / len(strikes)
                
                # Strike range shouldn't be too wide
                if strike_range > avg_strike * 0.6:  # Max 60% of average strike
                    return False
            
            # Check for reasonable expiry distribution
            expiries = [leg.expiry for leg in legs]
            if len(set(expiries)) > 2:  # Max 2 different expiries
                return False
            
            # Check total premium is reasonable
            total_premium = sum(leg.total_premium() for leg in legs)
            if abs(total_premium) > 100000:  # Max ₹1L total premium
                return False
            
            return True
            
        except Exception:
            return False
    
    def _validate_risk_metrics(self, max_profit: float, max_loss: float, net_premium: float) -> bool:
        """Validate calculated risk metrics"""
        try:
            # Max loss should be reasonable
            if max_loss > 200000:  # Max ₹2L loss
                return False
            
            # Risk-reward should be reasonable
            if max_profit != float('inf') and max_loss > 0:
                risk_reward = max_profit / max_loss
                if risk_reward < 0.1:  # Minimum 1:10 risk-reward
                    return False
            
            # Net premium should be reasonable
            if abs(net_premium) > 150000:  # Max ₹1.5L net premium
                return False
            
            return True
            
        except Exception:
            return True  # Default to True if validation fails
    
    def _find_option_in_chain(
        self,
        option_chain: pd.DataFrame,
        option_type: str,
        strike: float,
        expiry: date
    ) -> Optional[pd.Series]:
        """Find matching option in the option chain with improved logic"""
        try:
            if option_chain.empty:
                return None
            
            # Step 1: Try exact match
            exact_matches = option_chain[
                (option_chain['option_type'].str.upper() == option_type.upper()) &
                (abs(option_chain['strike'] - strike) < 0.01) &
                (option_chain['expiry'] == expiry)
            ]
            
            if not exact_matches.empty:
                # Return the one with best liquidity (highest volume/OI)
                if 'volume' in exact_matches.columns:
                    best_idx = exact_matches['volume'].idxmax()
                    return exact_matches.loc[best_idx]
                return exact_matches.iloc[0]
            
            # Step 2: Try same expiry, closest strike
            expiry_matches = option_chain[
                (option_chain['option_type'].str.upper() == option_type.upper()) &
                (option_chain['expiry'] == expiry)
            ]
            
            if not expiry_matches.empty:
                # Find closest strike within reasonable range (±10%)
                strike_diff = abs(expiry_matches['strike'] - strike)
                reasonable_range = strike * 0.10  # 10% of target strike
                
                close_strikes = expiry_matches[strike_diff <= reasonable_range]
                if not close_strikes.empty:
                    closest_idx = strike_diff[close_strikes.index].idxmin()
                    return expiry_matches.loc[closest_idx]
            
            # Step 3: Try closest expiry, exact strike
            strike_matches = option_chain[
                (option_chain['option_type'].str.upper() == option_type.upper()) &
                (abs(option_chain['strike'] - strike) < 0.01)
            ]
            
            if not strike_matches.empty:
                # Find closest expiry within ±30 days
                target_timestamp = pd.Timestamp(expiry)
                expiry_diff = abs(pd.to_datetime(strike_matches['expiry']) - target_timestamp).dt.days
                
                close_expiries = strike_matches[expiry_diff <= 30]
                if not close_expiries.empty:
                    closest_idx = expiry_diff[close_expiries.index].idxmin()
                    return strike_matches.loc[closest_idx]
            
            # Step 4: Best effort - closest strike and expiry
            type_matches = option_chain[
                option_chain['option_type'].str.upper() == option_type.upper()
            ]
            
            if not type_matches.empty:
                # Combined distance metric
                strike_diff_pct = abs(type_matches['strike'] - strike) / strike
                target_timestamp = pd.Timestamp(expiry)
                expiry_diff_days = abs(pd.to_datetime(type_matches['expiry']) - target_timestamp).dt.days
                
                # Weighted distance (strike weight = 0.7, expiry weight = 0.3)
                combined_distance = (strike_diff_pct * 0.7) + (expiry_diff_days / 30.0 * 0.3)
                
                # Only consider options within reasonable bounds
                reasonable_options = type_matches[
                    (strike_diff_pct <= 0.15) &  # Within 15% of target strike
                    (expiry_diff_days <= 45)     # Within 45 days of target expiry
                ]
                
                if not reasonable_options.empty:
                    best_idx = combined_distance[reasonable_options.index].idxmin()
                    return type_matches.loc[best_idx]
            
            return None
            
        except Exception as e:
            logger.warning(f"Error finding option in chain: {e}")
            return None
    
    def _determine_strategy_type(self, ast) -> EnhancedStrategyType:
        """Determine strategy type from AST"""
        ast_type = type(ast).__name__
        
        mapping = {
            'Straddle': EnhancedStrategyType.LONG_STRADDLE,
            'Strangle': EnhancedStrategyType.STRANGLE,
            'Butterfly': EnhancedStrategyType.BUTTERFLY,
            'Condor': EnhancedStrategyType.IRON_CONDOR,
            'Calendar': EnhancedStrategyType.CALENDAR_SPREAD,
            'Spread': EnhancedStrategyType.CALL_SPREAD,  # Default to call spread
        }
        
        return mapping.get(ast_type, EnhancedStrategyType.LONG_STRADDLE)
    
    def _generate_single_basic_strategy(
        self,
        regime: str,
        underlying: str,
        option_chain: pd.DataFrame,
        spot_price: float
    ) -> Optional[OptionStrategy]:
        """Generate a single basic strategy that works reliably"""
        try:
            # Find a suitable expiry
            current_expiry = self._find_nearest_expiry(option_chain, 7, 60)
            if current_expiry is None:
                logger.warning(f"No suitable expiry found for {underlying}")
                return None
            
            # Try different strategies based on regime
            if regime in ["low_vol_sell", "high_vol_sell"]:
                # Try iron condor first
                strategy = self._generate_basic_iron_condor(underlying, option_chain, spot_price)
                if strategy:
                    return strategy
                
                # Fall back to short straddle
                strategy = self._generate_basic_short_straddle(underlying, option_chain, spot_price)
                if strategy:
                    return strategy
            
            elif regime in ["rising_vol_buy", "falling_vol_buy"]:
                # Try long straddle first
                strategy = self._generate_basic_straddle(underlying, option_chain, spot_price)
                if strategy:
                    return strategy
                
                # Fall back to calendar spread
                strategy = self._generate_basic_calendar(underlying, option_chain, spot_price)
                if strategy:
                    return strategy
            
            # Ultimate fallback - simple long call
            return self._generate_simple_long_call(underlying, option_chain, spot_price)
            
        except Exception as e:
            logger.error(f"Single basic strategy generation failed: {e}")
            return None
    
    def _generate_basic_short_straddle(
        self,
        underlying: str,
        option_chain: pd.DataFrame,
        spot_price: float
    ) -> Optional[OptionStrategy]:
        """Generate basic short straddle strategy"""
        try:
            # Find ATM options
            current_expiry = self._find_nearest_expiry(option_chain, 15, 45)
            if current_expiry is None:
                return None
            
            # Find ATM call and put
            call_row = self._find_closest_option(
                option_chain, 'call', spot_price, current_expiry
            )
            put_row = self._find_closest_option(
                option_chain, 'put', spot_price, current_expiry
            )
            
            if call_row is None or put_row is None:
                return None
            
            legs = []
            for option_row, option_type in [(call_row, 'call'), (put_row, 'put')]:
                leg = OptionLeg(
                    option_type=option_type,
                    strike=float(option_row['strike']),
                    expiry=current_expiry,
                    quantity=-1,  # Short position
                    premium=float(option_row.get('ltp', 0)),
                    bid=float(option_row.get('bid', 0)),
                    ask=float(option_row.get('ask', 0)),
                    delta=float(option_row.get('delta', 0)),
                    gamma=float(option_row.get('gamma', 0)),
                    theta=float(option_row.get('theta', 0)),
                    vega=float(option_row.get('vega', 0)),
                    instrument_key=str(option_row.get('instrument_key', ''))
                )
                legs.append(leg)
            
            strategy = OptionStrategy(
                strategy_type=BasicStrategyType.LONG_STRADDLE,  # Use existing enum
                underlying=underlying,
                legs=legs,
                max_profit=sum(leg.premium for leg in legs),  # Max profit is premium received
                max_loss=float('inf'),  # Unlimited loss potential
                breakeven_points=self._calculate_breakevens(legs),
                net_premium=sum(leg.total_premium() for leg in legs),
                description=f"Short Straddle on {underlying}"
            )
            
            return strategy
            
        except Exception as e:
            logger.error(f"Failed to generate short straddle: {e}")
            return None
    
    def _generate_simple_long_call(
        self,
        underlying: str,
        option_chain: pd.DataFrame,
        spot_price: float
    ) -> Optional[OptionStrategy]:
        """Generate simple long call as ultimate fallback"""
        try:
            current_expiry = self._find_nearest_expiry(option_chain, 7, 60)
            if current_expiry is None:
                return None
            
            # Find ATM or slightly OTM call
            target_strike = spot_price * 1.02  # 2% OTM
            call_row = self._find_closest_option(
                option_chain, 'call', target_strike, current_expiry
            )
            
            if call_row is None:
                return None
            
            leg = OptionLeg(
                option_type='call',
                strike=float(call_row['strike']),
                expiry=current_expiry,
                quantity=1,
                premium=float(call_row.get('ltp', 0)),
                bid=float(call_row.get('bid', 0)),
                ask=float(call_row.get('ask', 0)),
                delta=float(call_row.get('delta', 0)),
                gamma=float(call_row.get('gamma', 0)),
                theta=float(call_row.get('theta', 0)),
                vega=float(call_row.get('vega', 0)),
                instrument_key=str(call_row.get('instrument_key', ''))
            )
            
            strategy = OptionStrategy(
                strategy_type=BasicStrategyType.LONG_STRADDLE,  # Use existing enum
                underlying=underlying,
                legs=[leg],
                max_profit=float('inf'),
                max_loss=leg.total_premium(),
                breakeven_points=[leg.strike + leg.premium],
                net_premium=leg.total_premium(),
                description=f"Long Call on {underlying}"
            )
            
            return strategy
            
        except Exception as e:
            logger.error(f"Failed to generate simple long call: {e}")
            return None
    
    def _generate_basic_strategies(
        self,
        regime: str,
        underlying: str,
        option_chain: pd.DataFrame,
        spot_price: float
    ) -> List[OptionStrategy]:
        """Fallback to basic strategy generation"""
        strategies = []
        
        try:
            # Generate basic iron condor
            if regime in ["low_vol_sell", "high_vol_sell"]:
                iron_condor = self._generate_basic_iron_condor(
                    underlying, option_chain, spot_price
                )
                if iron_condor:
                    strategies.append(iron_condor)
            
            # Generate basic straddle
            if regime in ["rising_vol_buy", "falling_vol_buy"]:
                straddle = self._generate_basic_straddle(
                    underlying, option_chain, spot_price
                )
                if straddle:
                    strategies.append(straddle)
            
            # Generate basic calendar spread
            calendar = self._generate_basic_calendar(
                underlying, option_chain, spot_price
            )
            if calendar:
                strategies.append(calendar)
                
        except Exception as e:
            logger.error(f"Basic strategy generation failed: {e}")
        
        return strategies
    
    def _generate_basic_iron_condor(
        self,
        underlying: str,
        option_chain: pd.DataFrame,
        spot_price: float
    ) -> Optional[OptionStrategy]:
        """Generate basic iron condor strategy"""
        try:
            # Find ATM options for current expiry
            current_expiry = self._find_nearest_expiry(option_chain, 15, 45)
            if current_expiry is None:
                return None
            
            # Define strikes (5% OTM on each side)
            otm_distance = spot_price * 0.05
            put_long_strike = spot_price - otm_distance * 2
            put_short_strike = spot_price - otm_distance
            call_short_strike = spot_price + otm_distance
            call_long_strike = spot_price + otm_distance * 2
            
            # Find options
            legs = []
            strikes_types = [
                (put_long_strike, 'put', 1),    # Long put
                (put_short_strike, 'put', -1),  # Short put
                (call_short_strike, 'call', -1), # Short call
                (call_long_strike, 'call', 1),   # Long call
            ]
            
            for strike, option_type, quantity in strikes_types:
                option_row = self._find_closest_option(
                    option_chain, option_type, strike, current_expiry
                )
                if option_row is None:
                    return None
                
                leg = OptionLeg(
                    option_type=option_type,
                    strike=float(option_row['strike']),
                    expiry=current_expiry,
                    quantity=quantity,
                    premium=float(option_row.get('ltp', 0)),
                    bid=float(option_row.get('bid', 0)),
                    ask=float(option_row.get('ask', 0)),
                    delta=float(option_row.get('delta', 0)),
                    gamma=float(option_row.get('gamma', 0)),
                    theta=float(option_row.get('theta', 0)),
                    vega=float(option_row.get('vega', 0)),
                    instrument_key=str(option_row.get('instrument_key', ''))
                )
                legs.append(leg)
            
            if len(legs) != 4:
                return None
            
            strategy = OptionStrategy(
                strategy_type=BasicStrategyType.IRON_CONDOR,
                underlying=underlying,
                legs=legs,
                max_profit=self._calculate_max_profit(legs),
                max_loss=self._calculate_max_loss(legs),
                breakeven_points=self._calculate_breakevens(legs),
                net_premium=sum(leg.total_premium() for leg in legs),
                description=f"Iron Condor on {underlying}"
            )
            
            return strategy
            
        except Exception as e:
            logger.error(f"Failed to generate iron condor: {e}")
            return None
    
    def _generate_basic_straddle(
        self,
        underlying: str,
        option_chain: pd.DataFrame,
        spot_price: float
    ) -> Optional[OptionStrategy]:
        """Generate basic long straddle strategy"""
        try:
            # Find ATM options
            current_expiry = self._find_nearest_expiry(option_chain, 15, 45)
            if current_expiry is None:
                return None
            
            # Find ATM call and put
            call_row = self._find_closest_option(
                option_chain, 'call', spot_price, current_expiry
            )
            put_row = self._find_closest_option(
                option_chain, 'put', spot_price, current_expiry
            )
            
            if call_row is None or put_row is None:
                return None
            
            legs = []
            for option_row, option_type in [(call_row, 'call'), (put_row, 'put')]:
                leg = OptionLeg(
                    option_type='CE' if option_type == 'call' else 'PE',
                    strike=float(option_row['strike']),
                    expiry=datetime.combine(current_expiry, datetime.min.time()),
                    action='BUY',
                    quantity=1,
                    premium=float(option_row.get('ltp', 0)),
                    greeks=Greeks(
                        delta=float(option_row.get('delta', 0)),
                        gamma=float(option_row.get('gamma', 0)),
                        theta=float(option_row.get('theta', 0)),
                        vega=float(option_row.get('vega', 0)),
                        rho=0.0
                    ),
                    instrument_key=str(option_row.get('instrument_key', ''))
                )
                legs.append(leg)
            
            strategy = OptionStrategy(
                strategy_type=BasicStrategyType.LONG_STRADDLE,
                underlying=underlying,
                legs=legs,
                max_profit=float('inf'),  # Unlimited upside
                max_loss=sum(leg.total_premium() for leg in legs),
                breakeven_points=self._calculate_breakevens(legs),
                net_premium=sum(leg.total_premium() for leg in legs),
                description=f"Long Straddle on {underlying}"
            )
            
            return strategy
            
        except Exception as e:
            logger.error(f"Failed to generate straddle: {e}")
            return None
    
    def _generate_basic_calendar(
        self,
        underlying: str,
        option_chain: pd.DataFrame,
        spot_price: float
    ) -> Optional[OptionStrategy]:
        """Generate basic calendar spread strategy"""
        try:
            # Find near and far expiries
            near_expiry = self._find_nearest_expiry(option_chain, 15, 30)
            far_expiry = self._find_nearest_expiry(option_chain, 45, 60)
            
            if near_expiry is None or far_expiry is None:
                return None
            
            # Find ATM calls for both expiries
            near_call = self._find_closest_option(
                option_chain, 'call', spot_price, near_expiry
            )
            far_call = self._find_closest_option(
                option_chain, 'call', spot_price, far_expiry
            )
            
            if near_call is None or far_call is None:
                return None
            
            legs = [
                OptionLeg(  # Short near-term call
                    option_type='call',
                    strike=float(near_call['strike']),
                    expiry=near_expiry,
                    quantity=-1,
                    premium=float(near_call.get('ltp', 0)),
                    bid=float(near_call.get('bid', 0)),
                    ask=float(near_call.get('ask', 0)),
                    delta=float(near_call.get('delta', 0)),
                    gamma=float(near_call.get('gamma', 0)),
                    theta=float(near_call.get('theta', 0)),
                    vega=float(near_call.get('vega', 0)),
                    instrument_key=str(near_call.get('instrument_key', ''))
                ),
                OptionLeg(  # Long far-term call
                    option_type='call',
                    strike=float(far_call['strike']),
                    expiry=far_expiry,
                    quantity=1,
                    premium=float(far_call.get('ltp', 0)),
                    bid=float(far_call.get('bid', 0)),
                    ask=float(far_call.get('ask', 0)),
                    delta=float(far_call.get('delta', 0)),
                    gamma=float(far_call.get('gamma', 0)),
                    theta=float(far_call.get('theta', 0)),
                    vega=float(far_call.get('vega', 0)),
                    instrument_key=str(far_call.get('instrument_key', ''))
                )
            ]
            
            strategy = OptionStrategy(
                strategy_type=BasicStrategyType.CALENDAR_SPREAD,
                underlying=underlying,
                legs=legs,
                max_profit=self._calculate_max_profit(legs),
                max_loss=self._calculate_max_loss(legs),
                breakeven_points=self._calculate_breakevens(legs),
                net_premium=sum(leg.total_premium() for leg in legs),
                description=f"Calendar Spread on {underlying}"
            )
            
            return strategy
            
        except Exception as e:
            logger.error(f"Failed to generate calendar spread: {e}")
            return None
    
    def _generate_emergency_fallback(
        self,
        underlying: str,
        option_chain: pd.DataFrame,
        spot_price: float
    ) -> List[OptionStrategy]:
        """Emergency fallback to simple long call"""
        try:
            current_expiry = self._find_nearest_expiry(option_chain, 15, 45)
            if current_expiry is None:
                return []
            
            call_row = self._find_closest_option(
                option_chain, 'call', spot_price, current_expiry
            )
            
            if call_row is None:
                return []
            
            leg = OptionLeg(
                option_type='call',
                strike=float(call_row['strike']),
                expiry=current_expiry,
                quantity=1,
                premium=float(call_row.get('ltp', 0)),
                bid=float(call_row.get('bid', 0)),
                ask=float(call_row.get('ask', 0)),
                delta=float(call_row.get('delta', 0)),
                gamma=float(call_row.get('gamma', 0)),
                theta=float(call_row.get('theta', 0)),
                vega=float(call_row.get('vega', 0)),
                instrument_key=str(call_row.get('instrument_key', ''))
            )
            
            strategy = OptionStrategy(
                strategy_type=BasicStrategyType.LONG_STRADDLE,  # Use existing enum
                underlying=underlying,
                legs=[leg],
                max_profit=float('inf'),
                max_loss=leg.total_premium(),
                breakeven_points=[leg.strike + leg.premium],
                net_premium=leg.total_premium(),
                description=f"Emergency Long Call on {underlying}"
            )
            
            return [strategy]
            
        except Exception as e:
            logger.error(f"Emergency fallback failed: {e}")
            return []
    
    # Helper methods
    
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
        """Find closest option to target strike with improved matching"""
        try:
            if option_chain.empty:
                return None
            
            # Handle different expiry formats consistently
            def normalize_expiry(exp):
                if isinstance(exp, str):
                    return datetime.strptime(exp, '%Y-%m-%d').date()
                elif hasattr(exp, 'date'):
                    return exp.date()
                elif isinstance(exp, date):
                    return exp
                return None
            
            # Normalize expiries in the chain
            option_chain = option_chain.copy()
            option_chain['normalized_expiry'] = option_chain['expiry'].apply(normalize_expiry)
            
            # Filter by type and expiry
            filtered = option_chain[
                (option_chain['option_type'].str.lower() == option_type.lower()) &
                (option_chain['normalized_expiry'] == expiry)
            ]
            
            if filtered.empty:
                # Try to find closest expiry within ±15 days
                expiry_diffs = []
                for idx, row_expiry in option_chain['normalized_expiry'].items():
                    if row_expiry is not None:
                        diff = abs((row_expiry - expiry).days)
                        expiry_diffs.append((idx, diff))
                
                if expiry_diffs:
                    # Get indices where expiry diff <= 15 days
                    close_indices = [idx for idx, diff in expiry_diffs if diff <= 15]
                    
                    filtered = option_chain[
                        (option_chain['option_type'].str.lower() == option_type.lower()) &
                        (option_chain.index.isin(close_indices))
                    ]
                
                if filtered.empty:
                    return None
            
            # Find closest strike with liquidity preference
            strike_diffs = abs(filtered['strike'] - target_strike)
            
            # Prefer liquid options (with volume > 0 or OI > 0)
            liquid_options = filtered[
                ((filtered.get('volume', 0) > 0) | (filtered.get('oi', 0) > 0))
            ]
            
            if not liquid_options.empty:
                closest_idx = strike_diffs[liquid_options.index].idxmin()
                return filtered.loc[closest_idx]
            else:
                # Fall back to closest strike regardless of liquidity
                closest_idx = strike_diffs.idxmin()
                return filtered.loc[closest_idx]
            
        except Exception as e:
            logger.warning(f"Error finding closest option: {e}")
            return None
    
    def _calculate_max_profit(self, legs: List[OptionLeg]) -> float:
        """Calculate maximum profit (simplified)"""
        try:
            net_premium = sum(leg.total_premium() for leg in legs)
            
            # For credit spreads, max profit is net credit
            if net_premium < 0:  # Net credit
                return abs(net_premium)
            
            # For debit spreads, calculate based on spread width
            # This is a simplified calculation
            return float('inf')  # Unlimited for long volatility strategies
            
        except Exception:
            return 0.0
    
    def _calculate_max_loss(self, legs: List[OptionLeg]) -> float:
        """Calculate maximum loss (simplified)"""
        try:
            net_premium = sum(leg.total_premium() for leg in legs)
            
            # For debit spreads, max loss is net debit
            if net_premium > 0:  # Net debit
                return net_premium
            
            # For credit spreads, calculate based on spread width
            # This is a simplified calculation
            strikes = [leg.strike for leg in legs]
            if len(strikes) >= 2:
                spread_width = max(strikes) - min(strikes)
                return spread_width - abs(net_premium)
            
            return abs(net_premium)
            
        except Exception:
            return 0.0
    
    def _calculate_max_profit_enhanced(self, legs: List[OptionLeg]) -> float:
        """Enhanced maximum profit calculation"""
        try:
            net_premium = sum(leg.total_premium() for leg in legs)
            
            # For single leg strategies
            if len(legs) == 1:
                leg = legs[0]
                if leg.option_type.lower() == 'call' and leg.quantity > 0:
                    return float('inf')  # Long call has unlimited upside
                elif leg.option_type.lower() == 'put' and leg.quantity > 0:
                    return leg.strike - leg.premium  # Long put max profit
                else:
                    return leg.premium  # Short option max profit
            
            # For multi-leg strategies, use simplified calculation
            if net_premium < 0:  # Net credit received
                # For credit spreads, max profit is net credit
                return abs(net_premium)
            else:
                # For debit spreads, calculate based on spread width
                strikes = [leg.strike for leg in legs]
                if len(set(strikes)) > 1:
                    spread_width = max(strikes) - min(strikes)
                    return max(0, spread_width - net_premium)
                else:
                    # Straddle/strangle - unlimited profit potential
                    return float('inf')
                    
        except Exception:
            return float('inf')  # Default to unlimited if calculation fails
    
    def _calculate_max_loss_enhanced(self, legs: List[OptionLeg]) -> float:
        """Enhanced maximum loss calculation"""
        try:
            net_premium = sum(leg.total_premium() for leg in legs)
            
            # For single leg strategies
            if len(legs) == 1:
                leg = legs[0]
                if leg.quantity > 0:  # Long option
                    return leg.premium  # Max loss is premium paid
                else:  # Short option
                    if leg.option_type.lower() == 'call':
                        return float('inf')  # Short call has unlimited loss
                    else:
                        return leg.strike - leg.premium  # Short put max loss
            
            # For multi-leg strategies
            if net_premium > 0:  # Net debit paid
                # For debit spreads, max loss is net debit
                return net_premium
            else:
                # For credit spreads, calculate based on spread width
                strikes = [leg.strike for leg in legs]
                if len(set(strikes)) > 1:
                    spread_width = max(strikes) - min(strikes)
                    return max(0, spread_width - abs(net_premium))
                else:
                    # Short straddle/strangle - unlimited loss potential
                    return float('inf')
                    
        except Exception:
            return abs(sum(leg.total_premium() for leg in legs))  # Fallback to net premium
    
    def _calculate_breakevens_enhanced(self, legs: List[OptionLeg]) -> List[float]:
        """Enhanced breakeven calculation"""
        try:
            if not legs:
                return [0.0]
            
            net_premium = sum(leg.total_premium() for leg in legs)
            strikes = sorted([leg.strike for leg in legs])
            
            # Single leg
            if len(legs) == 1:
                leg = legs[0]
                if leg.option_type.lower() == 'call':
                    return [leg.strike + abs(leg.premium)]
                else:
                    return [leg.strike - abs(leg.premium)]
            
            # Two legs with same strike (straddle)
            elif len(legs) == 2 and len(set(strikes)) == 1:
                strike = strikes[0]
                return [strike - abs(net_premium), strike + abs(net_premium)]
            
            # Two legs with different strikes (strangle, spread)
            elif len(legs) == 2 and len(set(strikes)) == 2:
                lower_strike, upper_strike = strikes[0], strikes[-1]
                
                # Check if it's a strangle (different strikes, same expiry, opposite types)
                call_legs = [leg for leg in legs if leg.option_type.lower() == 'call']
                put_legs = [leg for leg in legs if leg.option_type.lower() == 'put']
                
                if len(call_legs) == 1 and len(put_legs) == 1:
                    # Strangle breakevens
                    return [lower_strike - abs(net_premium), upper_strike + abs(net_premium)]
                else:
                    # Spread breakevens
                    if net_premium > 0:  # Debit spread
                        return [lower_strike + net_premium]
                    else:  # Credit spread
                        return [lower_strike + abs(net_premium)]
            
            # Multi-leg strategies - simplified
            else:
                return [min(strikes) - abs(net_premium), max(strikes) + abs(net_premium)]
                
        except Exception:
            return [0.0]
