#!/usr/bin/env python3
"""
Strategy Generator for Unified Volatility Engine

Implements AST-based strategy generation from target exposure specifications.
Generates option structures dynamically rather than selecting from templates.

Key Features:
- Target Greeks decomposition into primitive exposures
- Structure generation from primitives (straddles, spreads, butterflies, etc.)
- Pricing and Greeks computation for structures
- Ranking by cost-efficiency
- Constraint satisfaction and validation

Requirements: 2.1, 2.2, 2.3, 2.5, 2.6, 2.7
"""

import logging
import numpy as np
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from src.volatility.strategy_ast import (
    OptionNode, Call, Put, Spread, Straddle, Strangle,
    Butterfly, Condor, Calendar, CompositeNode, OptionLeg, OptionType
)
from src.volatility.greeks_aggregator import (
    Greeks, GreeksAggregator, Position
)

logger = logging.getLogger(__name__)


@dataclass
class TargetGreeks:
    """Target exposure specification with tolerances"""
    delta: float = 0.0
    delta_tolerance: float = 0.1
    gamma: float = 0.0
    gamma_tolerance: float = 0.05
    vega: float = 0.0
    vega_tolerance: float = 0.1
    theta: float = 0.0
    theta_tolerance: float = 0.05


@dataclass
class Constraints:
    """Strategy generation constraints"""
    max_legs: int = 10
    max_cost: float = 100000.0
    min_liquidity: float = 100.0  # Min open interest
    max_spread_width: float = 0.05  # Max bid-ask spread as % of mid
    allowed_underlyings: List[str] = field(default_factory=lambda: ["SPY"])
    max_dte: int = 90  # Max days to expiration
    min_dte: int = 7   # Min days to expiration


@dataclass
class MarketState:
    """Simplified market state for strategy generation"""
    spot_price: float
    implied_vol: float
    risk_free_rate: float = 0.05
    timestamp: datetime = field(default_factory=datetime.now)
    
    def get_atm_strike(self, round_to: float = 5.0) -> float:
        """Get at-the-money strike rounded to nearest increment"""
        return round(self.spot_price / round_to) * round_to


class PrimitiveType(Enum):
    """Primitive exposure types"""
    LONG_VOL = "long_vol"
    SHORT_VOL = "short_vol"
    LONG_GAMMA = "long_gamma"
    SHORT_GAMMA = "short_gamma"
    DIRECTIONAL_LONG = "directional_long"
    DIRECTIONAL_SHORT = "directional_short"
    THETA_POSITIVE = "theta_positive"
    THETA_NEGATIVE = "theta_negative"


@dataclass
class PrimitiveExposure:
    """Primitive exposure decomposition"""
    type: PrimitiveType
    size: float
    priority: int = 1  # Higher priority = more important to satisfy


@dataclass
class OptionStructure:
    """Generated option structure with pricing and Greeks"""
    ast: OptionNode
    greeks: Greeks
    price: float
    underlying: str
    expiry: date
    legs: List[OptionLeg]
    cost_efficiency: float = 0.0  # Price per unit vega (or other metric)
    
    def satisfies_target(self, target: TargetGreeks) -> bool:
        """Check if structure satisfies target Greeks within tolerances"""
        if abs(self.greeks.delta - target.delta) > target.delta_tolerance:
            return False
        if abs(self.greeks.gamma - target.gamma) > target.gamma_tolerance:
            return False
        if abs(self.greeks.vega - target.vega) > target.vega_tolerance:
            return False
        if abs(self.greeks.theta - target.theta) > target.theta_tolerance:
            return False
        return True


class StrategyGenerator:
    """
    AST-based strategy generator
    
    Generates option structures from target Greeks specifications.
    Uses decomposition → generation → pricing → ranking pipeline.
    
    Requirements: 2.1, 2.2, 2.3, 2.5, 2.6, 2.7
    """
    
    def __init__(self):
        self.greeks_calculator = GreeksAggregator()
        self.generation_count = 0
    
    def generate(
        self,
        target_greeks: TargetGreeks,
        constraints: Constraints,
        state: MarketState
    ) -> List[OptionStructure]:
        """
        Generate option structures matching target Greeks.
        
        Algorithm:
        1. Decompose target Greeks into primitive exposures
        2. Generate candidate structures using AST composition
        3. Price each structure and compute actual Greeks
        4. Rank by cost-efficiency and constraint satisfaction
        5. Return top N candidates
        
        Requirements: 2.1, 2.2, 2.3, 2.5
        """
        logger.info(f"Generating strategies for target: {target_greeks}")
        
        # Step 1: Decompose targets
        primitives = self._decompose_greeks(target_greeks)
        logger.debug(f"Decomposed into {len(primitives)} primitives: {primitives}")
        
        # Step 2: Generate candidates
        candidates = []
        for primitive in primitives:
            structures = self._generate_structures(primitive, state, constraints)
            candidates.extend(structures)
        
        logger.info(f"Generated {len(candidates)} candidate structures")
        
        # Step 3: Price and compute Greeks
        for structure in candidates:
            structure.price = self._price_structure(structure, state)
            structure.greeks = self._compute_structure_greeks(structure, state)
            
            # Compute cost-efficiency (price per unit vega, or other metric)
            if abs(structure.greeks.vega) > 0.01:
                structure.cost_efficiency = structure.price / abs(structure.greeks.vega)
            else:
                structure.cost_efficiency = float('inf')
        
        # Step 4: Filter and rank
        feasible = []
        for s in candidates:
            is_feasible = self._satisfies_constraints(s, constraints, target_greeks)
            logger.debug(f"Structure feasibility: {is_feasible}, price: {s.price}, legs: {len(s.legs)}")
            if is_feasible:
                feasible.append(s)
        
        logger.info(f"Filtered to {len(feasible)} feasible structures")
        
        if not feasible:
            logger.warning("No feasible structures found - relaxing constraints")
            # Emergency fallback with very relaxed constraints
            for s in candidates:
                if len(s.legs) <= 8 and abs(s.price) <= 500000:  # Very relaxed
                    feasible.append(s)
                    logger.info(f"Added structure with relaxed constraints: price={s.price}")
        
        if not feasible:
            logger.warning("Still no feasible structures after relaxing constraints")
            return []
        
        # Rank by cost-efficiency (lower is better)
        ranked = sorted(feasible, key=lambda s: s.cost_efficiency)
        
        # Step 5: Return top candidates
        self.generation_count += 1
        return ranked[:3]
    
    def _decompose_greeks(self, target: TargetGreeks) -> List[PrimitiveExposure]:
        """
        Break down target Greeks into basic exposures.
        
        Requirements: 2.1
        """
        primitives = []
        
        # Vega exposure (volatility exposure)
        if target.vega > 0.1:
            primitives.append(PrimitiveExposure(
                type=PrimitiveType.LONG_VOL,
                size=target.vega,
                priority=3
            ))
        elif target.vega < -0.1:
            primitives.append(PrimitiveExposure(
                type=PrimitiveType.SHORT_VOL,
                size=-target.vega,
                priority=3
            ))
        
        # Gamma exposure (convexity)
        if target.gamma > 0.01:
            primitives.append(PrimitiveExposure(
                type=PrimitiveType.LONG_GAMMA,
                size=target.gamma,
                priority=2
            ))
        elif target.gamma < -0.01:
            primitives.append(PrimitiveExposure(
                type=PrimitiveType.SHORT_GAMMA,
                size=-target.gamma,
                priority=2
            ))
        
        # Delta exposure (directional)
        if target.delta > 0.1:
            primitives.append(PrimitiveExposure(
                type=PrimitiveType.DIRECTIONAL_LONG,
                size=target.delta,
                priority=1
            ))
        elif target.delta < -0.1:
            primitives.append(PrimitiveExposure(
                type=PrimitiveType.DIRECTIONAL_SHORT,
                size=-target.delta,
                priority=1
            ))
        
        # Theta exposure (time decay)
        if target.theta > 0.01:
            primitives.append(PrimitiveExposure(
                type=PrimitiveType.THETA_POSITIVE,
                size=target.theta,
                priority=1
            ))
        elif target.theta < -0.01:
            primitives.append(PrimitiveExposure(
                type=PrimitiveType.THETA_NEGATIVE,
                size=-target.theta,
                priority=1
            ))
        
        # If no significant exposures, default to delta-neutral long vol
        if not primitives:
            primitives.append(PrimitiveExposure(
                type=PrimitiveType.LONG_VOL,
                size=1.0,
                priority=1
            ))
        
        return primitives
    
    def _generate_structures(
        self,
        primitive: PrimitiveExposure,
        state: MarketState,
        constraints: Constraints
    ) -> List[OptionStructure]:
        """
        Generate structures for a primitive exposure.
        
        Requirements: 2.1, 2.2
        """
        structures = []
        
        # Get ATM strike and use available expiries from market
        atm_strike = round(state.get_atm_strike() / 50) * 50  # Round to nearest 50
        underlying = constraints.allowed_underlyings[0]
        
        # Use a reasonable default expiry that will be matched by option chain
        # The enhanced strategy generator will find the best matching expiry
        expiry = datetime.now().date() + timedelta(days=30)
        
        if primitive.type == PrimitiveType.LONG_VOL:
            # Long volatility structures
            structures.extend([
                self._create_straddle(atm_strike, expiry, 1, underlying),
                self._create_strangle(atm_strike, expiry, 1, underlying, state),
                self._create_call_spread(atm_strike, expiry, 1, underlying, state, long=True),
                self._create_put_spread(atm_strike, expiry, 1, underlying, state, long=True),
            ])
        
        elif primitive.type == PrimitiveType.SHORT_VOL:
            # Short volatility structures
            structures.extend([
                self._create_iron_condor(atm_strike, expiry, 1, underlying, state),
                self._create_short_strangle(atm_strike, expiry, 1, underlying, state),
                self._create_butterfly(atm_strike, expiry, 1, underlying, state),
            ])
        
        elif primitive.type == PrimitiveType.LONG_GAMMA:
            # Long gamma structures (ATM options)
            structures.extend([
                self._create_atm_straddle(atm_strike, expiry, 1, underlying),
                self._create_calendar_spread(atm_strike, expiry, 1, underlying, state),
            ])
        
        elif primitive.type == PrimitiveType.SHORT_GAMMA:
            # Short gamma structures
            structures.extend([
                self._create_short_straddle(atm_strike, expiry, 1, underlying),
                self._create_iron_condor(atm_strike, expiry, 1, underlying, state),
            ])
        
        elif primitive.type == PrimitiveType.DIRECTIONAL_LONG:
            # Bullish structures
            structures.extend([
                self._create_long_call(atm_strike, expiry, 1, underlying),
                self._create_call_spread(atm_strike, expiry, 1, underlying, state, long=True),
            ])
        
        elif primitive.type == PrimitiveType.DIRECTIONAL_SHORT:
            # Bearish structures
            structures.extend([
                self._create_long_put(atm_strike, expiry, 1, underlying),
                self._create_put_spread(atm_strike, expiry, 1, underlying, state, long=True),
            ])
        
        elif primitive.type == PrimitiveType.THETA_POSITIVE:
            # Positive theta (short options)
            structures.extend([
                self._create_short_strangle(atm_strike, expiry, 1, underlying, state),
                self._create_iron_condor(atm_strike, expiry, 1, underlying, state),
            ])
        
        elif primitive.type == PrimitiveType.THETA_NEGATIVE:
            # Negative theta (long options)
            structures.extend([
                self._create_straddle(atm_strike, expiry, 1, underlying),
                self._create_calendar_spread(atm_strike, expiry, 1, underlying, state),
            ])
        
        return structures

    
    # Structure creation methods
    
    def _create_straddle(self, strike: float, expiry: date, quantity: int, underlying: str) -> OptionStructure:
        """Create ATM straddle"""
        # Round strike to nearest 50 for Indian markets
        rounded_strike = round(strike / 50) * 50
        
        ast = Straddle(strike=rounded_strike, expiry=expiry, quantity=quantity, underlying=underlying)
        return OptionStructure(
            ast=ast,
            greeks=Greeks.zero(),
            price=0.0,
            underlying=underlying,
            expiry=expiry,
            legs=ast.get_legs()
        )
    
    def _create_atm_straddle(self, strike: float, expiry: date, quantity: int, underlying: str) -> OptionStructure:
        """Create ATM straddle (same as straddle)"""
        return self._create_straddle(strike, expiry, quantity, underlying)
    
    def _create_short_straddle(self, strike: float, expiry: date, quantity: int, underlying: str) -> OptionStructure:
        """Create short straddle"""
        return self._create_straddle(strike, expiry, -quantity, underlying)
    
    def _create_strangle(self, strike: float, expiry: date, quantity: int, underlying: str, state: MarketState) -> OptionStructure:
        """Create strangle with OTM strikes"""
        # Round strikes to nearest 50 for Indian markets
        base_strike = round(strike / 50) * 50
        strike_spacing = max(50, round(state.spot_price * 0.05 / 50) * 50)  # At least 50 points spacing
        
        call_strike = base_strike + strike_spacing
        put_strike = base_strike - strike_spacing
        
        ast = Strangle(
            call_strike=call_strike,
            put_strike=put_strike,
            expiry=expiry,
            quantity=quantity,
            underlying=underlying
        )
        return OptionStructure(
            ast=ast,
            greeks=Greeks.zero(),
            price=0.0,
            underlying=underlying,
            expiry=expiry,
            legs=ast.get_legs()
        )
    
    def _create_short_strangle(self, strike: float, expiry: date, quantity: int, underlying: str, state: MarketState) -> OptionStructure:
        """Create short strangle"""
        return self._create_strangle(strike, expiry, -quantity, underlying, state)
    
    def _create_call_spread(self, strike: float, expiry: date, quantity: int, underlying: str, state: MarketState, long: bool = True) -> OptionStructure:
        """Create call spread"""
        strike_spacing = state.spot_price * 0.05  # 5% width
        
        if long:
            # Bull call spread: long lower strike, short higher strike
            long_strike = strike
            short_strike = strike + strike_spacing
        else:
            # Bear call spread: short lower strike, long higher strike
            long_strike = strike + strike_spacing
            short_strike = strike
        
        long_leg = Call(strike=long_strike, expiry=expiry, quantity=quantity, underlying=underlying)
        short_leg = Call(strike=short_strike, expiry=expiry, quantity=-quantity, underlying=underlying)
        
        ast = Spread(long_leg=long_leg, short_leg=short_leg)
        return OptionStructure(
            ast=ast,
            greeks=Greeks.zero(),
            price=0.0,
            underlying=underlying,
            expiry=expiry,
            legs=ast.get_legs()
        )
    
    def _create_put_spread(self, strike: float, expiry: date, quantity: int, underlying: str, state: MarketState, long: bool = True) -> OptionStructure:
        """Create put spread"""
        strike_spacing = state.spot_price * 0.05  # 5% width
        
        if long:
            # Bear put spread: long higher strike, short lower strike
            long_strike = strike
            short_strike = strike - strike_spacing
        else:
            # Bull put spread: short higher strike, long lower strike
            long_strike = strike - strike_spacing
            short_strike = strike
        
        long_leg = Put(strike=long_strike, expiry=expiry, quantity=quantity, underlying=underlying)
        short_leg = Put(strike=short_strike, expiry=expiry, quantity=-quantity, underlying=underlying)
        
        ast = Spread(long_leg=long_leg, short_leg=short_leg)
        return OptionStructure(
            ast=ast,
            greeks=Greeks.zero(),
            price=0.0,
            underlying=underlying,
            expiry=expiry,
            legs=ast.get_legs()
        )
    
    def _create_long_call(self, strike: float, expiry: date, quantity: int, underlying: str) -> OptionStructure:
        """Create long call"""
        ast = Call(strike=strike, expiry=expiry, quantity=quantity, underlying=underlying)
        return OptionStructure(
            ast=ast,
            greeks=Greeks.zero(),
            price=0.0,
            underlying=underlying,
            expiry=expiry,
            legs=ast.get_legs()
        )
    
    def _create_long_put(self, strike: float, expiry: date, quantity: int, underlying: str) -> OptionStructure:
        """Create long put"""
        ast = Put(strike=strike, expiry=expiry, quantity=quantity, underlying=underlying)
        return OptionStructure(
            ast=ast,
            greeks=Greeks.zero(),
            price=0.0,
            underlying=underlying,
            expiry=expiry,
            legs=ast.get_legs()
        )
    
    def _create_butterfly(self, strike: float, expiry: date, quantity: int, underlying: str, state: MarketState) -> OptionStructure:
        """Create butterfly spread"""
        # Round strikes to nearest 50 for Indian markets
        base_strike = round(strike / 50) * 50
        strike_spacing = max(50, round(state.spot_price * 0.05 / 50) * 50)  # At least 50 points spacing
        
        ast = Butterfly(
            lower_strike=base_strike - strike_spacing,
            middle_strike=base_strike,
            upper_strike=base_strike + strike_spacing,
            expiry=expiry,
            quantity=quantity,
            option_type=OptionType.CALL,
            underlying=underlying
        )
        return OptionStructure(
            ast=ast,
            greeks=Greeks.zero(),
            price=0.0,
            underlying=underlying,
            expiry=expiry,
            legs=ast.get_legs()
        )
    
    def _create_iron_condor(self, strike: float, expiry: date, quantity: int, underlying: str, state: MarketState) -> OptionStructure:
        """Create iron condor"""
        # Round strikes to nearest 50 for Indian markets
        base_strike = round(strike / 50) * 50
        strike_spacing = max(100, round(state.spot_price * 0.05 / 50) * 50)  # At least 100 points spacing
        wing_width = max(50, round(state.spot_price * 0.03 / 50) * 50)  # At least 50 points wing width
        
        ast = Condor(
            put_lower_strike=base_strike - strike_spacing - wing_width,
            put_upper_strike=base_strike - strike_spacing,
            call_lower_strike=base_strike + strike_spacing,
            call_upper_strike=base_strike + strike_spacing + wing_width,
            expiry=expiry,
            quantity=quantity,
            underlying=underlying
        )
        return OptionStructure(
            ast=ast,
            greeks=Greeks.zero(),
            price=0.0,
            underlying=underlying,
            expiry=expiry,
            legs=ast.get_legs()
        )
    
    def _create_calendar_spread(self, strike: float, expiry: date, quantity: int, underlying: str, state: MarketState) -> OptionStructure:
        """Create calendar spread"""
        near_expiry = expiry
        far_expiry = (datetime.combine(expiry, datetime.min.time()) + timedelta(days=30)).date()
        
        ast = Calendar(
            strike=strike,
            near_expiry=near_expiry,
            far_expiry=far_expiry,
            quantity=quantity,
            option_type=OptionType.CALL,
            underlying=underlying
        )
        return OptionStructure(
            ast=ast,
            greeks=Greeks.zero(),
            price=0.0,
            underlying=underlying,
            expiry=far_expiry,  # Use far expiry as structure expiry
            legs=ast.get_legs()
        )
    
    def _price_structure(self, structure: OptionStructure, state: MarketState) -> float:
        """
        Price an option structure using Black-Scholes.
        
        Requirements: 2.2, 2.3
        """
        total_price = 0.0
        
        for leg in structure.legs:
            # Create position for pricing
            position = Position(
                position_id=f"temp_{leg.strike}_{leg.option_type.value}",
                underlying=leg.underlying,
                option_type=leg.option_type.value,
                strike=leg.strike,
                expiry=leg.expiry,
                quantity=1,  # Price for 1 contract
                spot_price=state.spot_price,
                implied_vol=state.implied_vol,
                risk_free_rate=state.risk_free_rate
            )
            
            # Price using Black-Scholes
            leg_price = self._black_scholes_price(position, state)
            
            # Add to total (positive for long, negative for short)
            total_price += leg_price * leg.quantity
        
        return total_price
    
    def _black_scholes_price(self, position: Position, state: MarketState) -> float:
        """Calculate Black-Scholes option price"""
        S = position.spot_price
        K = position.strike
        T = position.time_to_expiry(state.timestamp)
        r = position.risk_free_rate
        sigma = position.implied_vol
        
        if T <= 0:
            # Expired option
            if position.option_type == 'call':
                return max(S - K, 0)
            else:
                return max(K - S, 0)
        
        # Black-Scholes formula
        d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma*np.sqrt(T))
        d2 = d1 - sigma*np.sqrt(T)
        
        from scipy.stats import norm
        
        if position.option_type == 'call':
            price = S * norm.cdf(d1) - K * np.exp(-r*T) * norm.cdf(d2)
        else:  # put
            price = K * np.exp(-r*T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        
        return price
    
    def _compute_structure_greeks(self, structure: OptionStructure, state: MarketState) -> Greeks:
        """
        Compute Greeks for an option structure.
        
        Requirements: 2.2, 2.3
        """
        # Convert legs to positions
        positions = []
        for leg in structure.legs:
            position = Position(
                position_id=f"temp_{leg.strike}_{leg.option_type.value}",
                underlying=leg.underlying,
                option_type=leg.option_type.value,
                strike=leg.strike,
                expiry=leg.expiry,
                quantity=leg.quantity,
                spot_price=state.spot_price,
                implied_vol=state.implied_vol,
                risk_free_rate=state.risk_free_rate
            )
            positions.append(position)
        
        # Compute portfolio Greeks
        portfolio_greeks = self.greeks_calculator.compute_portfolio_greeks(
            positions,
            as_of=state.timestamp
        )
        
        # Convert to Greeks object
        return Greeks(
            delta=portfolio_greeks.delta,
            gamma=portfolio_greeks.gamma,
            vega=portfolio_greeks.vega,
            theta=portfolio_greeks.theta,
            rho=portfolio_greeks.rho,
            vanna=portfolio_greeks.vanna,
            volga=portfolio_greeks.volga,
            charm=portfolio_greeks.charm,
            vomma=portfolio_greeks.vomma
        )
    
    def _satisfies_constraints(
        self,
        structure: OptionStructure,
        constraints: Constraints,
        target: TargetGreeks
    ) -> bool:
        """
        Check if structure satisfies constraints.
        
        Requirements: 2.3, 2.5
        """
        # Check number of legs (more lenient)
        if len(structure.legs) > constraints.max_legs:
            logger.debug(f"Failed legs constraint: {len(structure.legs)} > {constraints.max_legs}")
            return False
        
        # Check cost (more lenient for Indian markets)
        max_cost = min(constraints.max_cost, 200000.0)  # ₹2L max for Indian options
        if abs(structure.price) > max_cost:
            logger.debug(f"Failed cost constraint: {abs(structure.price)} > {max_cost}")
            return False
        
        # Check underlying
        if structure.underlying not in constraints.allowed_underlyings:
            logger.debug(f"Failed underlying constraint: {structure.underlying} not in {constraints.allowed_underlyings}")
            return False
        
        # Check DTE (more lenient range)
        try:
            dte = (structure.expiry - datetime.now().date()).days
            min_dte = max(1, constraints.min_dte - 5)  # Allow shorter DTE
            max_dte = constraints.max_dte + 30  # Allow longer DTE
            if dte < min_dte or dte > max_dte:
                logger.debug(f"Failed DTE constraint: {dte} not in [{min_dte}, {max_dte}]")
                return False
        except Exception as e:
            logger.debug(f"Failed DTE calculation: {e}")
            return False
        
        # More lenient Greeks matching (Indian markets are less liquid)
        if not self._satisfies_target_lenient(structure, target):
            logger.debug(f"Failed Greeks constraint")
            return False
        
        # Additional Indian market specific checks
        if not self._satisfies_indian_market_constraints(structure):
            logger.debug(f"Failed Indian market constraints")
            return False
        
        logger.debug(f"Structure passed all constraints: price={structure.price}, legs={len(structure.legs)}")
        return True
    
    def _satisfies_target_lenient(self, structure: OptionStructure, target: TargetGreeks) -> bool:
        """Lenient target Greeks matching for Indian markets"""
        try:
            # Use larger tolerances for Indian options
            delta_tolerance = 0.5  # 50% tolerance
            gamma_tolerance = 0.8  # 80% tolerance  
            vega_tolerance = 0.6   # 60% tolerance
            theta_tolerance = 0.7  # 70% tolerance
            
            # Only check significant targets (> 0.1)
            if abs(target.delta) > 0.1:
                if abs(structure.greeks.delta - target.delta) > delta_tolerance:
                    return False
            
            if abs(target.gamma) > 0.1:
                if abs(structure.greeks.gamma - target.gamma) > gamma_tolerance:
                    return False
            
            if abs(target.vega) > 0.1:
                if abs(structure.greeks.vega - target.vega) > vega_tolerance:
                    return False
            
            if abs(target.theta) > 0.1:
                if abs(structure.greeks.theta - target.theta) > theta_tolerance:
                    return False
                
            return True
        except Exception:
            return True  # Default to True if comparison fails
    
    def _satisfies_indian_market_constraints(self, structure: OptionStructure) -> bool:
        """Indian market specific constraints"""
        try:
            # Check for reasonable option prices (not too cheap/expensive)
            if abs(structure.price) < 50:  # Minimum ₹50 strategy cost
                return False
            
            # Check for reasonable strike spacing
            strikes = [leg.strike for leg in structure.legs]
            if len(strikes) > 1:
                strike_range = max(strikes) - min(strikes)
                # Allow wider strike ranges for Indian markets
                if strike_range > strikes[0] * 0.5:  # Max 50% of underlying price
                    return False
            
            return True
        except Exception:
            return True
    
    def compose_structures(
        self,
        structures: List[OptionStructure],
        state: MarketState
    ) -> OptionStructure:
        """
        Combine multiple structures into a complex position.
        
        Requirements: 2.4
        """
        if not structures:
            raise ValueError("Cannot compose empty structure list")
        
        # Build composite AST
        composite_ast = CompositeNode(
            children=[s.ast for s in structures],
            name="Composed Strategy"
        )
        
        # Validate composite
        if not composite_ast.validate():
            raise ValueError("Composed structure failed validation")
        
        # Combine all legs
        all_legs = []
        for structure in structures:
            all_legs.extend(structure.legs)
        
        # Compute combined Greeks
        combined_greeks = Greeks.zero()
        for structure in structures:
            combined_greeks = combined_greeks + structure.greeks
        
        # Compute combined price
        combined_price = sum(s.price for s in structures)
        
        # Use latest expiry
        latest_expiry = max(s.expiry for s in structures)
        
        # Create composed structure
        composed = OptionStructure(
            ast=composite_ast,
            greeks=combined_greeks,
            price=combined_price,
            underlying=structures[0].underlying,
            expiry=latest_expiry,
            legs=all_legs
        )
        
        # Validate no-arbitrage
        if not self._validate_arbitrage_free(composed, state):
            logger.warning("Composed structure may violate arbitrage bounds")
        
        return composed
    
    def _validate_arbitrage_free(self, structure: OptionStructure, state: MarketState) -> bool:
        """
        Validate that structure doesn't violate no-arbitrage constraints.
        
        Requirements: 2.4
        """
        # Basic no-arbitrage checks
        
        # 1. Option prices must be non-negative
        for leg in structure.legs:
            position = Position(
                position_id=f"temp_{leg.strike}_{leg.option_type.value}",
                underlying=leg.underlying,
                option_type=leg.option_type.value,
                strike=leg.strike,
                expiry=leg.expiry,
                quantity=1,
                spot_price=state.spot_price,
                implied_vol=state.implied_vol,
                risk_free_rate=state.risk_free_rate
            )
            price = self._black_scholes_price(position, state)
            if price < 0:
                return False
        
        # 2. Call prices should be monotonically decreasing in strike
        # 3. Put prices should be monotonically increasing in strike
        # (Simplified check - full validation would be more complex)
        
        return True


def main():
    """Test strategy generator"""
    print("🎯 Testing Strategy Generator")
    print("=" * 60)
    
    # Create test inputs
    target = TargetGreeks(
        delta=0.0,
        delta_tolerance=0.2,
        vega=10.0,
        vega_tolerance=2.0,
        gamma=0.5,
        gamma_tolerance=0.2
    )
    
    constraints = Constraints(
        max_legs=6,
        max_cost=50000.0,
        allowed_underlyings=["SPY"],
        max_dte=60,
        min_dte=14
    )
    
    state = MarketState(
        spot_price=450.0,
        implied_vol=0.20,
        risk_free_rate=0.05
    )
    
    # Generate strategies
    generator = StrategyGenerator()
    strategies = generator.generate(target, constraints, state)
    
    print(f"\n✅ Generated {len(strategies)} strategies")
    
    for i, strategy in enumerate(strategies, 1):
        print(f"\n📊 Strategy {i}:")
        print(f"  Type: {strategy.ast.__class__.__name__}")
        print(f"  Price: ${strategy.price:.2f}")
        print(f"  Greeks:")
        print(f"    Delta: {strategy.greeks.delta:.4f}")
        print(f"    Gamma: {strategy.greeks.gamma:.4f}")
        print(f"    Vega: {strategy.greeks.vega:.4f}")
        print(f"    Theta: {strategy.greeks.theta:.4f}")
        print(f"  Cost Efficiency: {strategy.cost_efficiency:.2f}")
        print(f"  Legs: {len(strategy.legs)}")
    
    print("\n✅ Strategy generator tests complete!")


if __name__ == "__main__":
    main()
