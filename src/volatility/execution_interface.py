"""
Execution Interface for Unified Volatility Engine

Implements Requirement 12: Production-Grade Execution Integration
- Order generation from approved strategies (12.1)
- Multi-venue routing (12.2)
- Pre-trade risk checks (12.3)
- Order status tracking (12.4, 12.5)
- Order modification and cancellation (12.6, 12.7)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from decimal import Decimal

from .strategy_ast import OptionLeg
from .strategy_generator import OptionStructure
from .risk_authority import UnifiedRiskAuthority, TradeValidationResult


class OrderType(Enum):
    """Order type enumeration"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class TimeInForce(Enum):
    """Time-in-force parameter"""
    DAY = "day"
    GTC = "good_till_cancel"
    IOC = "immediate_or_cancel"
    FOK = "fill_or_kill"


class OrderStatus(Enum):
    """Order status enumeration"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    FAILED = "failed"


class VenueType(Enum):
    """Execution venue types"""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    DARK_POOL = "dark_pool"
    SMART_ROUTER = "smart_router"


@dataclass
class ExecutionInstruction:
    """Single order execution instruction"""
    order_id: str
    leg: OptionLeg
    order_type: OrderType
    time_in_force: TimeInForce
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    venue: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'order_id': self.order_id,
            'leg': self.leg.to_dict(),
            'order_type': self.order_type.value,
            'time_in_force': self.time_in_force.value,
            'limit_price': self.limit_price,
            'stop_price': self.stop_price,
            'venue': self.venue,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class Order:
    """Order with status tracking"""
    order_id: str
    instruction: ExecutionInstruction
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    average_fill_price: Optional[float] = None
    submission_time: Optional[datetime] = None
    fill_time: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    slippage: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'order_id': self.order_id,
            'instruction': self.instruction.to_dict(),
            'status': self.status.value,
            'filled_quantity': self.filled_quantity,
            'average_fill_price': self.average_fill_price,
            'submission_time': self.submission_time.isoformat() if self.submission_time else None,
            'fill_time': self.fill_time.isoformat() if self.fill_time else None,
            'rejection_reason': self.rejection_reason,
            'slippage': self.slippage
        }


@dataclass
class VenueInfo:
    """Venue information for routing"""
    venue_id: str
    venue_type: VenueType
    liquidity_score: float  # 0-1, higher is better
    avg_spread_bps: float  # Average bid-ask spread in basis points
    fill_rate: float  # Historical fill rate 0-1
    latency_ms: float  # Average latency in milliseconds
    
    def routing_score(self) -> float:
        """Compute routing score (higher is better)"""
        # Weight: 40% liquidity, 30% spread, 20% fill rate, 10% latency
        return (0.4 * self.liquidity_score + 
                0.3 * (1.0 - min(self.avg_spread_bps / 100, 1.0)) +
                0.2 * self.fill_rate +
                0.1 * (1.0 - min(self.latency_ms / 1000, 1.0)))


class ExecutionInterface:
    """
    Execution interface for strategy execution
    
    Implements:
    - Order generation from approved strategies (R12.1)
    - Multi-venue routing (R12.2)
    - Pre-trade risk checks (R12.3)
    - Order status tracking (R12.4, R12.5)
    - Order modification and cancellation (R12.6, R12.7)
    """
    
    def __init__(self, risk_authority: UnifiedRiskAuthority):
        """
        Initialize execution interface
        
        Args:
            risk_authority: Risk authority for pre-trade checks
        """
        self.risk_authority = risk_authority
        self.orders: Dict[str, Order] = {}
        self.order_counter = 0
        
        # Venue configuration (in production, load from config)
        self.venues: Dict[str, VenueInfo] = {
            'CBOE': VenueInfo('CBOE', VenueType.PRIMARY, 0.9, 5.0, 0.95, 10.0),
            'ISE': VenueInfo('ISE', VenueType.PRIMARY, 0.85, 6.0, 0.93, 12.0),
            'PHLX': VenueInfo('PHLX', VenueType.SECONDARY, 0.75, 8.0, 0.90, 15.0),
            'SMART': VenueInfo('SMART', VenueType.SMART_ROUTER, 0.95, 4.0, 0.97, 8.0)
        }
    
    def generate_execution_instructions(
        self,
        strategy: OptionStructure,
        order_type: OrderType = OrderType.LIMIT,
        time_in_force: TimeInForce = TimeInForce.DAY,
        limit_prices: Optional[Dict[str, float]] = None
    ) -> List[ExecutionInstruction]:
        """
        Generate execution instructions from approved strategy
        
        Implements R12.1: Order generation from approved strategies
        
        Args:
            strategy: Approved option structure
            order_type: Order type (market, limit, stop)
            time_in_force: Time-in-force parameter
            limit_prices: Optional limit prices per leg (keyed by leg identifier)
            
        Returns:
            List of execution instructions
        """
        instructions = []
        
        # Extract legs from strategy AST
        legs = strategy.legs
        
        for idx, leg in enumerate(legs):
            # Generate unique order ID
            order_id = self._generate_order_id()
            
            # Determine limit price if needed
            limit_price = None
            if order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
                if limit_prices and f"leg_{idx}" in limit_prices:
                    limit_price = limit_prices[f"leg_{idx}"]
                else:
                    # Use mid-market price as default limit
                    limit_price = self._estimate_mid_price(leg)
            
            # Select venue based on liquidity and pricing
            venue = self._select_venue(leg)
            
            instruction = ExecutionInstruction(
                order_id=order_id,
                leg=leg,
                order_type=order_type,
                time_in_force=time_in_force,
                limit_price=limit_price,
                venue=venue,
                timestamp=datetime.now()
            )
            
            instructions.append(instruction)
        
        return instructions
    
    def select_order_type(
        self,
        leg: OptionLeg,
        urgency: str = "normal",
        market_conditions: Optional[Dict[str, Any]] = None
    ) -> OrderType:
        """
        Select appropriate order type based on conditions
        
        Args:
            leg: Option leg to execute
            urgency: Execution urgency (low, normal, high)
            market_conditions: Current market conditions
            
        Returns:
            Recommended order type
        """
        # High urgency or illiquid options -> market order
        if urgency == "high":
            return OrderType.MARKET
        
        # Check liquidity
        if market_conditions:
            spread_bps = market_conditions.get('spread_bps', 10.0)
            volume = market_conditions.get('volume', 0)
            
            # Wide spread or low volume -> limit order
            if spread_bps > 20.0 or volume < 100:
                return OrderType.LIMIT
        
        # Default to limit order for better price
        return OrderType.LIMIT
    
    def _select_venue(self, leg: OptionLeg) -> str:
        """
        Select best execution venue based on liquidity and pricing
        
        Implements R12.2: Multi-venue routing
        
        Args:
            leg: Option leg to route
            
        Returns:
            Selected venue ID
        """
        # Compute routing scores for all venues
        scores = {venue_id: venue.routing_score() 
                 for venue_id, venue in self.venues.items()}
        
        # Select venue with highest score
        best_venue = max(scores.items(), key=lambda x: x[1])[0]
        
        return best_venue
    
    def pre_trade_risk_check(
        self,
        instructions: List[ExecutionInstruction],
        portfolio: Dict[str, Any],
        regime: str = 'low-vol'
    ) -> TradeValidationResult:
        """
        Perform pre-trade risk checks before order submission
        
        Implements R12.3: Pre-trade risk checks
        
        Args:
            instructions: Execution instructions to validate
            portfolio: Current portfolio state
            regime: Current volatility regime
            
        Returns:
            Validation result from Risk Authority
        """
        # Convert instructions to trade format for risk authority
        trade = self._instructions_to_trade(instructions)
        
        # Validate with risk authority
        result = self.risk_authority.validate_trade(trade, portfolio, regime)
        
        return result
    
    def submit_orders(
        self,
        instructions: List[ExecutionInstruction],
        portfolio: Dict[str, Any],
        regime: str = 'low-vol'
    ) -> Dict[str, Any]:
        """
        Submit orders after pre-trade risk checks
        
        Args:
            instructions: Execution instructions
            portfolio: Current portfolio state
            regime: Current volatility regime
            
        Returns:
            Submission result with order IDs and status
        """
        # Pre-trade risk check
        validation = self.pre_trade_risk_check(instructions, portfolio, regime)
        
        if not validation.approved:
            return {
                'success': False,
                'reason': 'Pre-trade risk check failed',
                'violations': [v.__dict__ for v in validation.violations],
                'orders': []
            }
        
        # Submit orders
        submitted_orders = []
        for instruction in instructions:
            order = Order(
                order_id=instruction.order_id,
                instruction=instruction,
                status=OrderStatus.SUBMITTED,
                submission_time=datetime.now()
            )
            
            self.orders[order.order_id] = order
            submitted_orders.append(order.order_id)
        
        return {
            'success': True,
            'orders': submitted_orders,
            'submission_time': datetime.now().isoformat()
        }
    
    def update_order_status(
        self,
        order_id: str,
        status: OrderStatus,
        filled_quantity: Optional[int] = None,
        fill_price: Optional[float] = None,
        rejection_reason: Optional[str] = None
    ) -> bool:
        """
        Update order status and track fills
        
        Implements R12.4: Order status tracking
        
        Args:
            order_id: Order identifier
            status: New order status
            filled_quantity: Quantity filled (for partial/full fills)
            fill_price: Execution price
            rejection_reason: Reason for rejection
            
        Returns:
            True if update successful
        """
        if order_id not in self.orders:
            return False
        
        order = self.orders[order_id]
        order.status = status
        
        if filled_quantity is not None:
            order.filled_quantity = filled_quantity
        
        if fill_price is not None:
            # Update average fill price
            if order.average_fill_price is None:
                order.average_fill_price = fill_price
            else:
                # Weighted average
                total_filled = order.filled_quantity
                prev_filled = total_filled - (filled_quantity or 0)
                order.average_fill_price = (
                    (order.average_fill_price * prev_filled + fill_price * (filled_quantity or 0)) 
                    / total_filled
                )
        
        if status in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
            order.fill_time = datetime.now()
            
            # Compute slippage if limit price was set
            if order.instruction.limit_price and order.average_fill_price:
                order.slippage = order.average_fill_price - order.instruction.limit_price
        
        if status == OrderStatus.REJECTED and rejection_reason:
            order.rejection_reason = rejection_reason
        
        return True
    
    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current order status
        
        Args:
            order_id: Order identifier
            
        Returns:
            Order status dictionary or None if not found
        """
        if order_id not in self.orders:
            return None
        
        return self.orders[order_id].to_dict()
    
    def modify_order(
        self,
        order_id: str,
        new_limit_price: Optional[float] = None,
        new_quantity: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Modify existing order
        
        Implements R12.6: Order modification
        
        Args:
            order_id: Order to modify
            new_limit_price: New limit price
            new_quantity: New quantity
            
        Returns:
            Modification result
        """
        if order_id not in self.orders:
            return {
                'success': False,
                'reason': f'Order {order_id} not found'
            }
        
        order = self.orders[order_id]
        
        # Can only modify pending or submitted orders
        if order.status not in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
            return {
                'success': False,
                'reason': f'Cannot modify order in status {order.status.value}'
            }
        
        # Update order parameters
        if new_limit_price is not None:
            order.instruction.limit_price = new_limit_price
        
        if new_quantity is not None:
            order.instruction.leg.quantity = new_quantity
        
        return {
            'success': True,
            'order_id': order_id,
            'modification_time': datetime.now().isoformat()
        }
    
    def cancel_order(self, order_id: str, reason: str = "User requested") -> Dict[str, Any]:
        """
        Cancel existing order
        
        Implements R12.7: Order cancellation
        
        Args:
            order_id: Order to cancel
            reason: Cancellation reason
            
        Returns:
            Cancellation result
        """
        if order_id not in self.orders:
            return {
                'success': False,
                'reason': f'Order {order_id} not found',
                'logged': False
            }
        
        order = self.orders[order_id]
        
        # Can only cancel pending or submitted orders
        if order.status not in [OrderStatus.PENDING, OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]:
            return {
                'success': False,
                'reason': f'Cannot cancel order in status {order.status.value}',
                'logged': True
            }
        
        # Update status
        order.status = OrderStatus.CANCELLED
        order.rejection_reason = reason
        
        # Log cancellation
        self._log_cancellation(order_id, reason)
        
        return {
            'success': True,
            'order_id': order_id,
            'cancellation_time': datetime.now().isoformat(),
            'logged': True
        }
    
    def get_portfolio_state_update(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get portfolio state update from filled order
        
        Implements R12.4: Portfolio state updates on fills
        
        Args:
            order_id: Filled order ID
            
        Returns:
            Portfolio update or None if order not filled
        """
        if order_id not in self.orders:
            return None
        
        order = self.orders[order_id]
        
        if order.status not in [OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED]:
            return None
        
        leg = order.instruction.leg
        
        return {
            'underlying': leg.underlying,
            'option_type': leg.option_type.value,
            'strike': leg.strike,
            'expiry': leg.expiry.isoformat(),
            'quantity': order.filled_quantity,
            'average_price': order.average_fill_price,
            'fill_time': order.fill_time.isoformat() if order.fill_time else None
        }
    
    def compute_execution_slippage(
        self,
        order_id: str,
        theoretical_price: float
    ) -> Optional[float]:
        """
        Compute execution slippage vs theoretical price
        
        Implements R12.5: Execution price and slippage tracking
        
        Args:
            order_id: Order ID
            theoretical_price: Theoretical/expected price
            
        Returns:
            Slippage amount or None if not filled
        """
        if order_id not in self.orders:
            return None
        
        order = self.orders[order_id]
        
        if order.average_fill_price is None:
            return None
        
        # Slippage = actual - theoretical (positive means worse execution)
        slippage = order.average_fill_price - theoretical_price
        
        return slippage
    
    def _generate_order_id(self) -> str:
        """Generate unique order ID"""
        self.order_counter += 1
        return f"ORD{datetime.now().strftime('%Y%m%d')}{self.order_counter:06d}"
    
    def _estimate_mid_price(self, leg: OptionLeg) -> float:
        """
        Estimate mid-market price for option leg
        
        In production, this would query real market data.
        For now, return a placeholder.
        """
        # Placeholder: use simple heuristic based on moneyness
        # In production, query actual bid/ask and compute mid
        return 5.0  # Placeholder
    
    def _instructions_to_trade(self, instructions: List[ExecutionInstruction]) -> Dict[str, Any]:
        """Convert execution instructions to trade format for risk authority"""
        # Aggregate position size and Greeks
        total_size = sum(abs(inst.leg.quantity) for inst in instructions)
        
        # Extract underlying (assume all legs same underlying)
        underlying = instructions[0].leg.underlying if instructions else "SPY"
        
        return {
            'symbol': underlying,
            'size': total_size / 100.0,  # Normalize to percentage
            'direction': 'long',  # Simplified
            'sector': 'options',
            'greeks': {
                'delta': 0.0,  # Would compute from legs
                'gamma': 0.0,
                'vega': 0.0,
                'theta': 0.0
            }
        }
    
    def _log_cancellation(self, order_id: str, reason: str):
        """Log order cancellation"""
        # In production, write to audit log
        print(f"[CANCEL] Order {order_id} cancelled: {reason}")
    
    def get_all_orders(self, status_filter: Optional[OrderStatus] = None) -> List[Dict[str, Any]]:
        """
        Get all orders, optionally filtered by status
        
        Args:
            status_filter: Optional status to filter by
            
        Returns:
            List of order dictionaries
        """
        orders = self.orders.values()
        
        if status_filter:
            orders = [o for o in orders if o.status == status_filter]
        
        return [o.to_dict() for o in orders]
