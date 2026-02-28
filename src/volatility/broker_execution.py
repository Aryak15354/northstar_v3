#!/usr/bin/env python3
"""
Broker Execution Interface for Unified Volatility Engine

Implements real order execution through Upstox API with proper order management,
risk checks, and execution quality tracking.
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import requests

logger = logging.getLogger(__name__)


class OrderType(Enum):
    """Order types"""
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "SL"
    STOP_LOSS_MARKET = "SL-M"


class OrderSide(Enum):
    """Order side"""
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    """Order status"""
    PENDING = "pending"
    OPEN = "open"
    COMPLETE = "complete"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    PARTIALLY_FILLED = "partially_filled"


class ProductType(Enum):
    """Product type"""
    INTRADAY = "I"  # MIS
    DELIVERY = "D"  # CNC
    CARRYFORWARD = "C"  # NRML


@dataclass
class Order:
    """Order representation"""
    instrument_key: str
    quantity: int
    side: OrderSide
    order_type: OrderType
    product_type: ProductType
    price: Optional[float] = None
    trigger_price: Optional[float] = None
    disclosed_quantity: int = 0
    validity: str = "DAY"
    
    # Order tracking
    order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: int = 0
    average_price: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    exchange_timestamp: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    
    # Execution quality
    slippage: float = 0.0
    execution_time_ms: float = 0.0


@dataclass
class Position:
    """Position representation"""
    instrument_key: str
    quantity: int
    average_price: float
    last_price: float
    pnl: float
    day_pnl: float
    product_type: ProductType


class BrokerExecutionInterface:
    """
    Real broker execution interface using Upstox API
    
    Features:
    - Order placement and management
    - Position tracking
    - Execution quality monitoring
    - Pre-trade risk checks
    - Order book management
    """
    
    def __init__(self, api_key: str, api_secret: str, access_token: str):
        """
        Initialize broker execution interface
        
        Args:
            api_key: Upstox API key
            api_secret: Upstox API secret
            access_token: Upstox access token
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
        
        # API endpoints
        self.base_url = "https://api.upstox.com"
        self.endpoints = {
            'place_order': f"{self.base_url}/v2/order/place",
            'modify_order': f"{self.base_url}/v2/order/modify",
            'cancel_order': f"{self.base_url}/v2/order/cancel",
            'order_book': f"{self.base_url}/v2/order/retrieve-all",
            'order_details': f"{self.base_url}/v2/order/history",
            'positions': f"{self.base_url}/v2/portfolio/short-term-positions",
            'holdings': f"{self.base_url}/v2/portfolio/long-term-holdings"
        }
        
        # Session
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        })
        
        # Order tracking
        self.orders: Dict[str, Order] = {}
        self.positions: Dict[str, Position] = {}
        
        # Execution metrics
        self.total_orders = 0
        self.filled_orders = 0
        self.rejected_orders = 0
        self.total_slippage = 0.0
        
        logger.info("BrokerExecutionInterface initialized")
    
    def _make_request(
        self,
        method: str,
        url: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict:
        """Make HTTP request to Upstox API"""
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        
        except requests.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            if e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise
        
        except Exception as e:
            logger.error(f"Request error: {e}")
            raise
    
    def place_order(
        self,
        instrument_key: str,
        quantity: int,
        side: OrderSide,
        order_type: OrderType = OrderType.LIMIT,
        price: Optional[float] = None,
        product_type: ProductType = ProductType.CARRYFORWARD,
        trigger_price: Optional[float] = None
    ) -> Order:
        """
        Place order with broker
        
        Args:
            instrument_key: Upstox instrument key (e.g., "NSE_FO|12345")
            quantity: Order quantity
            side: BUY or SELL
            order_type: Order type (MARKET, LIMIT, etc.)
            price: Limit price (required for LIMIT orders)
            product_type: Product type (INTRADAY, DELIVERY, CARRYFORWARD)
            trigger_price: Trigger price (for stop loss orders)
        
        Returns:
            Order object with order_id
        """
        # Validate order
        if order_type == OrderType.LIMIT and price is None:
            raise ValueError("Price required for LIMIT orders")
        
        if order_type in [OrderType.STOP_LOSS, OrderType.STOP_LOSS_MARKET] and trigger_price is None:
            raise ValueError("Trigger price required for stop loss orders")
        
        # Create order object
        order = Order(
            instrument_key=instrument_key,
            quantity=quantity,
            side=side,
            order_type=order_type,
            product_type=product_type,
            price=price,
            trigger_price=trigger_price
        )
        
        # Prepare API request
        order_data = {
            'instrument_token': instrument_key,
            'quantity': quantity,
            'transaction_type': side.value,
            'order_type': order_type.value,
            'product': product_type.value,
            'validity': 'DAY'
        }
        
        if price is not None:
            order_data['price'] = price
        
        if trigger_price is not None:
            order_data['trigger_price'] = trigger_price
        
        # Place order
        start_time = time.time()
        
        try:
            response = self._make_request(
                'POST',
                self.endpoints['place_order'],
                data=order_data
            )
            
            execution_time = (time.time() - start_time) * 1000  # ms
            
            # Extract order ID
            if response.get('status') == 'success':
                order_id = response.get('data', {}).get('order_id')
                
                if order_id:
                    order.order_id = order_id
                    order.status = OrderStatus.OPEN
                    order.execution_time_ms = execution_time
                    
                    # Track order
                    self.orders[order_id] = order
                    self.total_orders += 1
                    
                    logger.info(f"Order placed: {order_id} - {side.value} {quantity} {instrument_key} @ {price}")
                    return order
                else:
                    raise ValueError("No order ID in response")
            else:
                raise ValueError(f"Order placement failed: {response}")
        
        except Exception as e:
            order.status = OrderStatus.REJECTED
            order.rejection_reason = str(e)
            self.rejected_orders += 1
            
            logger.error(f"Order rejected: {e}")
            raise
    
    def modify_order(
        self,
        order_id: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        trigger_price: Optional[float] = None
    ) -> Order:
        """
        Modify existing order
        
        Args:
            order_id: Order ID to modify
            quantity: New quantity (optional)
            price: New price (optional)
            trigger_price: New trigger price (optional)
        
        Returns:
            Updated Order object
        """
        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")
        
        order = self.orders[order_id]
        
        # Prepare modification data
        modify_data = {'order_id': order_id}
        
        if quantity is not None:
            modify_data['quantity'] = quantity
        if price is not None:
            modify_data['price'] = price
        if trigger_price is not None:
            modify_data['trigger_price'] = trigger_price
        
        try:
            response = self._make_request(
                'PUT',
                self.endpoints['modify_order'],
                data=modify_data
            )
            
            if response.get('status') == 'success':
                # Update order
                if quantity is not None:
                    order.quantity = quantity
                if price is not None:
                    order.price = price
                if trigger_price is not None:
                    order.trigger_price = trigger_price
                
                logger.info(f"Order modified: {order_id}")
                return order
            else:
                raise ValueError(f"Order modification failed: {response}")
        
        except Exception as e:
            logger.error(f"Failed to modify order {order_id}: {e}")
            raise
    
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel order
        
        Args:
            order_id: Order ID to cancel
        
        Returns:
            True if cancelled successfully
        """
        if order_id not in self.orders:
            raise ValueError(f"Order {order_id} not found")
        
        try:
            response = self._make_request(
                'DELETE',
                self.endpoints['cancel_order'],
                params={'order_id': order_id}
            )
            
            if response.get('status') == 'success':
                order = self.orders[order_id]
                order.status = OrderStatus.CANCELLED
                
                logger.info(f"Order cancelled: {order_id}")
                return True
            else:
                raise ValueError(f"Order cancellation failed: {response}")
        
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            raise
    
    def get_order_status(self, order_id: str) -> Order:
        """
        Get current order status
        
        Args:
            order_id: Order ID
        
        Returns:
            Updated Order object
        """
        try:
            response = self._make_request(
                'GET',
                self.endpoints['order_details'],
                params={'order_id': order_id}
            )
            
            if response.get('status') == 'success':
                order_data = response.get('data', [])
                
                if order_data:
                    # Get latest status
                    latest = order_data[-1]
                    
                    order = self.orders.get(order_id)
                    if order:
                        # Update order status
                        status_map = {
                            'complete': OrderStatus.COMPLETE,
                            'rejected': OrderStatus.REJECTED,
                            'cancelled': OrderStatus.CANCELLED,
                            'open': OrderStatus.OPEN
                        }
                        
                        order.status = status_map.get(
                            latest.get('status', '').lower(),
                            OrderStatus.PENDING
                        )
                        
                        order.filled_quantity = latest.get('filled_quantity', 0)
                        order.average_price = latest.get('average_price', 0.0)
                        
                        # Calculate slippage
                        if order.price and order.average_price > 0:
                            if order.side == OrderSide.BUY:
                                order.slippage = (order.average_price - order.price) / order.price
                            else:
                                order.slippage = (order.price - order.average_price) / order.price
                            
                            self.total_slippage += abs(order.slippage)
                        
                        if order.status == OrderStatus.COMPLETE:
                            self.filled_orders += 1
                        
                        return order
            
            raise ValueError(f"Could not get status for order {order_id}")
        
        except Exception as e:
            logger.error(f"Failed to get order status for {order_id}: {e}")
            raise
    
    def get_positions(self) -> List[Position]:
        """
        Get current positions
        
        Returns:
            List of Position objects
        """
        try:
            response = self._make_request(
                'GET',
                self.endpoints['positions']
            )
            
            if response.get('status') == 'success':
                positions_data = response.get('data', [])
                
                positions = []
                for pos_data in positions_data:
                    position = Position(
                        instrument_key=pos_data.get('instrument_token', ''),
                        quantity=pos_data.get('quantity', 0),
                        average_price=pos_data.get('average_price', 0.0),
                        last_price=pos_data.get('last_price', 0.0),
                        pnl=pos_data.get('pnl', 0.0),
                        day_pnl=pos_data.get('day_pnl', 0.0),
                        product_type=ProductType.CARRYFORWARD
                    )
                    positions.append(position)
                    
                    # Update position cache
                    self.positions[position.instrument_key] = position
                
                logger.info(f"Retrieved {len(positions)} positions")
                return positions
            
            return []
        
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            raise
    
    def get_execution_metrics(self) -> Dict:
        """
        Get execution quality metrics
        
        Returns:
            Dict with execution metrics
        """
        fill_rate = self.filled_orders / self.total_orders if self.total_orders > 0 else 0
        rejection_rate = self.rejected_orders / self.total_orders if self.total_orders > 0 else 0
        avg_slippage = self.total_slippage / self.filled_orders if self.filled_orders > 0 else 0
        
        return {
            'total_orders': self.total_orders,
            'filled_orders': self.filled_orders,
            'rejected_orders': self.rejected_orders,
            'fill_rate': fill_rate,
            'rejection_rate': rejection_rate,
            'avg_slippage': avg_slippage
        }
    
    def cancel_all_orders(self) -> int:
        """
        Cancel all open orders
        
        Returns:
            Number of orders cancelled
        """
        cancelled = 0
        
        for order_id, order in self.orders.items():
            if order.status == OrderStatus.OPEN:
                try:
                    self.cancel_order(order_id)
                    cancelled += 1
                except Exception as e:
                    logger.error(f"Failed to cancel order {order_id}: {e}")
        
        logger.info(f"Cancelled {cancelled} orders")
        return cancelled


if __name__ == "__main__":
    # Test broker execution interface
    import logging
    import os
    
    logging.basicConfig(level=logging.INFO)
    
    # Get credentials from environment
    api_key = os.getenv('UPSTOX_API_KEY', '')
    api_secret = os.getenv('UPSTOX_API_SECRET', '')
    access_token = os.getenv('UPSTOX_ACCESS_TOKEN', '')
    
    if not all([api_key, api_secret, access_token]):
        print("Error: Upstox credentials not found in environment")
        exit(1)
    
    broker = BrokerExecutionInterface(api_key, api_secret, access_token)
    
    # Test get positions
    try:
        positions = broker.get_positions()
        print(f"\nCurrent Positions: {len(positions)}")
        for pos in positions:
            print(f"  {pos.instrument_key}: {pos.quantity} @ {pos.average_price}, P&L: {pos.pnl}")
    except Exception as e:
        print(f"Error getting positions: {e}")
    
    # Test execution metrics
    metrics = broker.get_execution_metrics()
    print(f"\nExecution Metrics:")
    print(f"  Total Orders: {metrics['total_orders']}")
    print(f"  Fill Rate: {metrics['fill_rate']:.2%}")
    print(f"  Avg Slippage: {metrics['avg_slippage']:.4f}")
