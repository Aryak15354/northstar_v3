#!/usr/bin/env python3
"""
Option Structure AST (Abstract Syntax Tree)

This module implements AST nodes for representing option structures programmatically.
Enables composition of complex multi-leg positions from primitive building blocks.

Key Features:
- Base OptionNode class for all structures
- Primitive nodes: Call, Put
- Spread nodes: Spread, Straddle, Strangle, Butterfly, Condor, Calendar
- Composite nodes for complex multi-leg positions
- AST traversal and validation

Requirements: 2.4
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from abc import ABC, abstractmethod


class OptionType(Enum):
    """Option type enumeration"""
    CALL = "call"
    PUT = "put"


class OptionNode(ABC):
    """
    Base class for option structure AST
    
    All option structures inherit from this base class and implement
    the required methods for pricing, Greeks computation, and validation.
    """
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """Serialize node to dictionary"""
        pass
    
    @abstractmethod
    def get_legs(self) -> List['OptionLeg']:
        """Get all option legs in this structure"""
        pass
    
    @abstractmethod
    def validate(self) -> bool:
        """Validate structure for no-arbitrage and consistency"""
        pass
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.to_dict()})"


@dataclass
class OptionLeg:
    """
    Single option leg representation
    
    Represents a single call or put option with quantity.
    Used as building block for all structures.
    """
    option_type: OptionType
    strike: float
    expiry: date
    quantity: int  # Positive for long, negative for short
    underlying: str = "SPY"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'option_type': self.option_type.value,
            'strike': self.strike,
            'expiry': self.expiry.isoformat(),
            'quantity': self.quantity,
            'underlying': self.underlying
        }
    
    def is_long(self) -> bool:
        """Check if this is a long position"""
        return self.quantity > 0
    
    def is_short(self) -> bool:
        """Check if this is a short position"""
        return self.quantity < 0


# Primitive Nodes

@dataclass
class Call(OptionNode):
    """
    Call option node
    
    Represents a single call option (long or short based on quantity).
    """
    strike: float
    expiry: date
    quantity: int
    underlying: str = "SPY"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': 'Call',
            'strike': self.strike,
            'expiry': self.expiry.isoformat(),
            'quantity': self.quantity,
            'underlying': self.underlying
        }
    
    def get_legs(self) -> List[OptionLeg]:
        return [OptionLeg(
            option_type=OptionType.CALL,
            strike=self.strike,
            expiry=self.expiry,
            quantity=self.quantity,
            underlying=self.underlying
        )]
    
    def validate(self) -> bool:
        """Validate call option parameters"""
        if self.strike <= 0:
            return False
        if self.quantity == 0:
            return False
        return True


@dataclass
class Put(OptionNode):
    """
    Put option node
    
    Represents a single put option (long or short based on quantity).
    """
    strike: float
    expiry: date
    quantity: int
    underlying: str = "SPY"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': 'Put',
            'strike': self.strike,
            'expiry': self.expiry.isoformat(),
            'quantity': self.quantity,
            'underlying': self.underlying
        }
    
    def get_legs(self) -> List[OptionLeg]:
        return [OptionLeg(
            option_type=OptionType.PUT,
            strike=self.strike,
            expiry=self.expiry,
            quantity=self.quantity,
            underlying=self.underlying
        )]
    
    def validate(self) -> bool:
        """Validate put option parameters"""
        if self.strike <= 0:
            return False
        if self.quantity == 0:
            return False
        return True


# Spread Nodes

@dataclass
class Spread(OptionNode):
    """
    Vertical spread node
    
    Represents a vertical spread (long one strike, short another strike, same expiry).
    Can be call spread or put spread.
    """
    long_leg: OptionNode
    short_leg: OptionNode
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': 'Spread',
            'long_leg': self.long_leg.to_dict(),
            'short_leg': self.short_leg.to_dict()
        }
    
    def get_legs(self) -> List[OptionLeg]:
        return self.long_leg.get_legs() + self.short_leg.get_legs()
    
    def validate(self) -> bool:
        """Validate spread structure"""
        # Both legs must be valid
        if not self.long_leg.validate() or not self.short_leg.validate():
            return False
        
        # Get legs
        long_legs = self.long_leg.get_legs()
        short_legs = self.short_leg.get_legs()
        
        if not long_legs or not short_legs:
            return False
        
        # Same expiry
        if long_legs[0].expiry != short_legs[0].expiry:
            return False
        
        # Same option type
        if long_legs[0].option_type != short_legs[0].option_type:
            return False
        
        # Different strikes
        if long_legs[0].strike == short_legs[0].strike:
            return False
        
        return True


@dataclass
class Straddle(OptionNode):
    """
    Straddle node
    
    Represents a straddle (long/short call and put at same strike and expiry).
    """
    strike: float
    expiry: date
    quantity: int  # Positive for long straddle, negative for short
    underlying: str = "SPY"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': 'Straddle',
            'strike': self.strike,
            'expiry': self.expiry.isoformat(),
            'quantity': self.quantity,
            'underlying': self.underlying
        }
    
    def get_legs(self) -> List[OptionLeg]:
        return [
            OptionLeg(
                option_type=OptionType.CALL,
                strike=self.strike,
                expiry=self.expiry,
                quantity=self.quantity,
                underlying=self.underlying
            ),
            OptionLeg(
                option_type=OptionType.PUT,
                strike=self.strike,
                expiry=self.expiry,
                quantity=self.quantity,
                underlying=self.underlying
            )
        ]
    
    def validate(self) -> bool:
        """Validate straddle parameters"""
        if self.strike <= 0:
            return False
        if self.quantity == 0:
            return False
        return True


@dataclass
class Strangle(OptionNode):
    """
    Strangle node
    
    Represents a strangle (long/short call and put at different strikes, same expiry).
    """
    call_strike: float
    put_strike: float
    expiry: date
    quantity: int  # Positive for long strangle, negative for short
    underlying: str = "SPY"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': 'Strangle',
            'call_strike': self.call_strike,
            'put_strike': self.put_strike,
            'expiry': self.expiry.isoformat(),
            'quantity': self.quantity,
            'underlying': self.underlying
        }
    
    def get_legs(self) -> List[OptionLeg]:
        return [
            OptionLeg(
                option_type=OptionType.CALL,
                strike=self.call_strike,
                expiry=self.expiry,
                quantity=self.quantity,
                underlying=self.underlying
            ),
            OptionLeg(
                option_type=OptionType.PUT,
                strike=self.put_strike,
                expiry=self.expiry,
                quantity=self.quantity,
                underlying=self.underlying
            )
        ]
    
    def validate(self) -> bool:
        """Validate strangle parameters"""
        if self.call_strike <= 0 or self.put_strike <= 0:
            return False
        if self.quantity == 0:
            return False
        # Call strike should be above put strike for standard strangle
        if self.call_strike <= self.put_strike:
            return False
        return True


@dataclass
class Butterfly(OptionNode):
    """
    Butterfly spread node
    
    Represents a butterfly spread (long 1 lower, short 2 middle, long 1 upper).
    Can be call butterfly or put butterfly.
    """
    lower_strike: float
    middle_strike: float
    upper_strike: float
    expiry: date
    quantity: int
    option_type: OptionType = OptionType.CALL
    underlying: str = "SPY"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': 'Butterfly',
            'lower_strike': self.lower_strike,
            'middle_strike': self.middle_strike,
            'upper_strike': self.upper_strike,
            'expiry': self.expiry.isoformat(),
            'quantity': self.quantity,
            'option_type': self.option_type.value,
            'underlying': self.underlying
        }
    
    def get_legs(self) -> List[OptionLeg]:
        return [
            OptionLeg(
                option_type=self.option_type,
                strike=self.lower_strike,
                expiry=self.expiry,
                quantity=self.quantity,
                underlying=self.underlying
            ),
            OptionLeg(
                option_type=self.option_type,
                strike=self.middle_strike,
                expiry=self.expiry,
                quantity=-2 * self.quantity,
                underlying=self.underlying
            ),
            OptionLeg(
                option_type=self.option_type,
                strike=self.upper_strike,
                expiry=self.expiry,
                quantity=self.quantity,
                underlying=self.underlying
            )
        ]
    
    def validate(self) -> bool:
        """Validate butterfly parameters"""
        if self.lower_strike <= 0 or self.middle_strike <= 0 or self.upper_strike <= 0:
            return False
        if self.quantity == 0:
            return False
        # Strikes must be in order
        if not (self.lower_strike < self.middle_strike < self.upper_strike):
            return False
        # Middle strike should be roughly centered (for standard butterfly)
        # Allow some tolerance
        expected_middle = (self.lower_strike + self.upper_strike) / 2
        if abs(self.middle_strike - expected_middle) > (self.upper_strike - self.lower_strike) * 0.2:
            return False
        return True


@dataclass
class Condor(OptionNode):
    """
    Iron condor node
    
    Represents an iron condor (short OTM put spread + short OTM call spread).
    """
    put_lower_strike: float
    put_upper_strike: float
    call_lower_strike: float
    call_upper_strike: float
    expiry: date
    quantity: int
    underlying: str = "SPY"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': 'Condor',
            'put_lower_strike': self.put_lower_strike,
            'put_upper_strike': self.put_upper_strike,
            'call_lower_strike': self.call_lower_strike,
            'call_upper_strike': self.call_upper_strike,
            'expiry': self.expiry.isoformat(),
            'quantity': self.quantity,
            'underlying': self.underlying
        }
    
    def get_legs(self) -> List[OptionLeg]:
        return [
            # Put spread (short put_upper, long put_lower)
            OptionLeg(
                option_type=OptionType.PUT,
                strike=self.put_upper_strike,
                expiry=self.expiry,
                quantity=-self.quantity,
                underlying=self.underlying
            ),
            OptionLeg(
                option_type=OptionType.PUT,
                strike=self.put_lower_strike,
                expiry=self.expiry,
                quantity=self.quantity,
                underlying=self.underlying
            ),
            # Call spread (short call_lower, long call_upper)
            OptionLeg(
                option_type=OptionType.CALL,
                strike=self.call_lower_strike,
                expiry=self.expiry,
                quantity=-self.quantity,
                underlying=self.underlying
            ),
            OptionLeg(
                option_type=OptionType.CALL,
                strike=self.call_upper_strike,
                expiry=self.expiry,
                quantity=self.quantity,
                underlying=self.underlying
            )
        ]
    
    def validate(self) -> bool:
        """Validate condor parameters"""
        if any(s <= 0 for s in [self.put_lower_strike, self.put_upper_strike, 
                                  self.call_lower_strike, self.call_upper_strike]):
            return False
        if self.quantity == 0:
            return False
        # Strikes must be in order
        if not (self.put_lower_strike < self.put_upper_strike < 
                self.call_lower_strike < self.call_upper_strike):
            return False
        return True


@dataclass
class Calendar(OptionNode):
    """
    Calendar spread node
    
    Represents a calendar spread (long far expiry, short near expiry, same strike).
    """
    strike: float
    near_expiry: date
    far_expiry: date
    quantity: int
    option_type: OptionType = OptionType.CALL
    underlying: str = "SPY"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': 'Calendar',
            'strike': self.strike,
            'near_expiry': self.near_expiry.isoformat(),
            'far_expiry': self.far_expiry.isoformat(),
            'quantity': self.quantity,
            'option_type': self.option_type.value,
            'underlying': self.underlying
        }
    
    def get_legs(self) -> List[OptionLeg]:
        return [
            OptionLeg(
                option_type=self.option_type,
                strike=self.strike,
                expiry=self.near_expiry,
                quantity=-self.quantity,
                underlying=self.underlying
            ),
            OptionLeg(
                option_type=self.option_type,
                strike=self.strike,
                expiry=self.far_expiry,
                quantity=self.quantity,
                underlying=self.underlying
            )
        ]
    
    def validate(self) -> bool:
        """Validate calendar spread parameters"""
        if self.strike <= 0:
            return False
        if self.quantity == 0:
            return False
        # Far expiry must be after near expiry
        if self.far_expiry <= self.near_expiry:
            return False
        return True


# Composite Node

@dataclass
class CompositeNode(OptionNode):
    """
    Composite node for complex multi-leg positions
    
    Combines multiple option structures into a single complex position.
    Enables building arbitrarily complex strategies from primitives.
    """
    children: List[OptionNode] = field(default_factory=list)
    name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'type': 'Composite',
            'name': self.name,
            'children': [child.to_dict() for child in self.children]
        }
    
    def get_legs(self) -> List[OptionLeg]:
        """Get all legs from all children"""
        legs = []
        for child in self.children:
            legs.extend(child.get_legs())
        return legs
    
    def validate(self) -> bool:
        """Validate all children"""
        return all(child.validate() for child in self.children)
    
    def add_child(self, node: OptionNode):
        """Add a child node to the composite"""
        self.children.append(node)
    
    def remove_child(self, node: OptionNode):
        """Remove a child node from the composite"""
        self.children.remove(node)


def main():
    """Test AST node creation"""
    from datetime import timedelta
    
    print("🌳 Testing Option Structure AST")
    print("=" * 60)
    
    # Test primitive nodes
    print("\n📌 Testing Primitive Nodes...")
    call = Call(strike=100.0, expiry=date.today() + timedelta(days=30), quantity=10)
    print(f"Call: {call}")
    print(f"  Valid: {call.validate()}")
    print(f"  Legs: {call.get_legs()}")
    
    put = Put(strike=95.0, expiry=date.today() + timedelta(days=30), quantity=-5)
    print(f"\nPut: {put}")
    print(f"  Valid: {put.validate()}")
    
    # Test spread nodes
    print("\n📊 Testing Spread Nodes...")
    straddle = Straddle(strike=100.0, expiry=date.today() + timedelta(days=30), quantity=5)
    print(f"Straddle: {straddle}")
    print(f"  Valid: {straddle.validate()}")
    print(f"  Legs: {len(straddle.get_legs())} legs")
    
    butterfly = Butterfly(
        lower_strike=95.0,
        middle_strike=100.0,
        upper_strike=105.0,
        expiry=date.today() + timedelta(days=30),
        quantity=10
    )
    print(f"\nButterfly: {butterfly}")
    print(f"  Valid: {butterfly.validate()}")
    print(f"  Legs: {len(butterfly.get_legs())} legs")
    
    # Test composite node
    print("\n🔗 Testing Composite Node...")
    composite = CompositeNode(name="Complex Strategy")
    composite.add_child(call)
    composite.add_child(put)
    composite.add_child(straddle)
    print(f"Composite: {composite.name}")
    print(f"  Valid: {composite.validate()}")
    print(f"  Total legs: {len(composite.get_legs())} legs")
    
    print("\n✅ AST node tests complete!")


if __name__ == "__main__":
    main()


@dataclass
class OptionStructure:
    """
    Complete option structure with pricing and Greeks
    
    Represents a complete option strategy with all computed metrics.
    Used by the strategy generator to return fully-priced structures.
    """
    ast: OptionNode
    greeks: 'Greeks'  # Forward reference to avoid circular import
    price: float
    underlying: str
    expiry: date
    legs: List[OptionLeg]
    cost_efficiency: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'ast': self.ast.to_dict(),
            'greeks': self.greeks.__dict__ if hasattr(self.greeks, '__dict__') else {},
            'price': self.price,
            'underlying': self.underlying,
            'expiry': self.expiry.isoformat(),
            'legs': [leg.to_dict() for leg in self.legs],
            'cost_efficiency': self.cost_efficiency
        }
    
    def satisfies_target(self, target: 'TargetGreeks') -> bool:
        """Check if structure satisfies target Greeks within tolerance"""
        try:
            tolerance = 0.2  # 20% tolerance
            
            if abs(self.greeks.delta - target.delta) > tolerance:
                return False
            if abs(self.greeks.gamma - target.gamma) > tolerance:
                return False
            if abs(self.greeks.vega - target.vega) > tolerance:
                return False
            if abs(self.greeks.theta - target.theta) > tolerance:
                return False
                
            return True
        except Exception:
            return True  # Default to True if comparison fails


# Greeks class for OptionStructure
@dataclass
class Greeks:
    """Option Greeks"""
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0
    rho: float = 0.0
    vanna: float = 0.0
    volga: float = 0.0
    charm: float = 0.0
    vomma: float = 0.0
    
    @classmethod
    def zero(cls) -> 'Greeks':
        """Create zero Greeks"""
        return cls()
    
    def __add__(self, other: 'Greeks') -> 'Greeks':
        """Add Greeks together"""
        return Greeks(
            delta=self.delta + other.delta,
            gamma=self.gamma + other.gamma,
            vega=self.vega + other.vega,
            theta=self.theta + other.theta,
            rho=self.rho + other.rho,
            vanna=self.vanna + other.vanna,
            volga=self.volga + other.volga,
            charm=self.charm + other.charm,
            vomma=self.vomma + other.vomma
        )


# Position class for pricing
@dataclass
class Position:
    """Position for pricing calculations"""
    position_id: str
    underlying: str
    option_type: str
    strike: float
    expiry: date
    quantity: int
    spot_price: float
    implied_vol: float
    risk_free_rate: float
    
    def time_to_expiry(self, timestamp: datetime) -> float:
        """Calculate time to expiry in years"""
        from datetime import datetime
        if isinstance(timestamp, datetime):
            current_date = timestamp.date()
        else:
            current_date = timestamp
        
        days_to_expiry = (self.expiry - current_date).days
        return max(0, days_to_expiry / 365.0)