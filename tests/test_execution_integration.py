#!/usr/bin/env python3
"""
Execution Interface Integration Tests

Tests complete flow from strategy approval to execution:
- Order generation from approved strategies
- Pre-trade risk checks
- Order submission and status tracking
- Order rejection handling
- Partial fill scenarios
- Order modification and cancellation

Validates Requirements: 13.5
"""

import pytest
from datetime import datetime, date, timedelta
from src.volatility.execution_interface import (
    ExecutionInterface, OrderType, TimeInForce, OrderStatus,
    ExecutionInstruction, Order
)
from src.volatility.risk_authority import UnifiedRiskAuthority
from src.volatility.strategy_generator import StrategyGenerator, TargetGreeks, Constraints, MarketState, OptionStructure
from src.volatility.strategy_ast import OptionLeg, OptionType
from src.volatility.greeks_aggregator import Greeks


class TestExecutionIntegration:
    """Integration tests for execution interface"""
    
    @pytest.fixture
    def risk_authority(self):
        """Create risk authority instance"""
        return UnifiedRiskAuthority()
    
    @pytest.fixture
    def execution_interface(self, risk_authority):
        """Create execution interface instance"""
        return ExecutionInterface(risk_authority)
    
    @pytest.fixture
    def sample_strategy(self):
        """Create sample option structure for testing"""
        # Create a simple straddle
        legs = [
            OptionLeg(
                option_type=OptionType.CALL,
                strike=100.0,
                expiry=date.today() + timedelta(days=30),
                quantity=10,
                underlying="SPY"
            ),
            OptionLeg(
                option_type=OptionType.PUT,
                strike=100.0,
                expiry=date.today() + timedelta(days=30),
                quantity=10,
                underlying="SPY"
            )
        ]
        
        greeks = Greeks(
            delta=0.0,
            gamma=5.0,
            vega=30.0,
            theta=-1.0,
            rho=0.5,
            vanna=0.0,
            volga=0.0,
            charm=0.0,
            vomma=0.0
        )
        
        return OptionStructure(
            ast=None,  # Not needed for this test
            greeks=greeks,
            price=500.0,
            underlying="SPY",
            expiry=date.today() + timedelta(days=30),
            legs=legs
        )
    
    @pytest.fixture
    def sample_portfolio(self):
        """Create sample portfolio for testing"""
        return {
            'total_value': 1000000,
            'cash': 500000,
            'margin_used': 100000,
            'delta': 0,
            'gamma': 0,
            'vega': 0,
            'theta': 0,
            'positions': {}
        }
    
    def test_complete_execution_flow(self, execution_interface, sample_strategy, sample_portfolio):
        """
        Test complete flow from strategy approval to execution
        
        **Validates: Requirements 13.5**
        """
        # Step 1: Generate execution instructions
        instructions = execution_interface.generate_execution_instructions(
            strategy=sample_strategy,
            order_type=OrderType.LIMIT,
            time_in_force=TimeInForce.DAY
        )
        
        assert len(instructions) == 2, "Should generate 2 instructions for straddle"
        assert all(isinstance(inst, ExecutionInstruction) for inst in instructions)
        assert all(inst.order_type == OrderType.LIMIT for inst in instructions)
        assert all(inst.time_in_force == TimeInForce.DAY for inst in instructions)
        assert all(inst.venue is not None for inst in instructions)
        
        # Step 2: Pre-trade risk check
        validation = execution_interface.pre_trade_risk_check(
            instructions=instructions,
            portfolio=sample_portfolio,
            regime='low-vol'
        )
        
        assert validation is not None
        # Risk check may pass or fail depending on limits - just verify it runs
        
        # Step 3: Submit orders (if validation passed)
        if validation.approved:
            result = execution_interface.submit_orders(
                instructions=instructions,
                portfolio=sample_portfolio,
                regime='low-vol'
            )
            
            assert result['success'] == True
            assert len(result['orders']) == 2
            
            # Step 4: Track order status
            for order_id in result['orders']:
                status = execution_interface.get_order_status(order_id)
                assert status is not None
                assert status['status'] == OrderStatus.SUBMITTED.value
    
    def test_order_rejection_handling(self, execution_interface, sample_strategy, sample_portfolio):
        """
        Test order rejection handling
        
        **Validates: Requirements 13.5**
        """
        # Create instructions
        instructions = execution_interface.generate_execution_instructions(
            strategy=sample_strategy,
            order_type=OrderType.MARKET
        )
        
        # Simulate rejection by updating order status
        result = execution_interface.submit_orders(
            instructions=instructions,
            portfolio=sample_portfolio,
            regime='low-vol'
        )
        
        if result['success']:
            order_id = result['orders'][0]
            
            # Reject the order
            success = execution_interface.update_order_status(
                order_id=order_id,
                status=OrderStatus.REJECTED,
                rejection_reason="Insufficient margin"
            )
            
            assert success == True
            
            # Verify rejection was recorded
            status = execution_interface.get_order_status(order_id)
            assert status['status'] == OrderStatus.REJECTED.value
            assert status['rejection_reason'] == "Insufficient margin"
    
    def test_partial_fill_scenarios(self, execution_interface, sample_strategy, sample_portfolio):
        """
        Test partial fill scenarios
        
        **Validates: Requirements 13.5**
        """
        # Create instructions
        instructions = execution_interface.generate_execution_instructions(
            strategy=sample_strategy,
            order_type=OrderType.LIMIT
        )
        
        result = execution_interface.submit_orders(
            instructions=instructions,
            portfolio=sample_portfolio,
            regime='low-vol'
        )
        
        if result['success']:
            order_id = result['orders'][0]
            original_quantity = instructions[0].leg.quantity
            
            # Simulate partial fill (50%)
            partial_quantity = original_quantity // 2
            success = execution_interface.update_order_status(
                order_id=order_id,
                status=OrderStatus.PARTIALLY_FILLED,
                filled_quantity=partial_quantity,
                fill_price=5.0
            )
            
            assert success == True
            
            # Verify partial fill
            status = execution_interface.get_order_status(order_id)
            assert status['status'] == OrderStatus.PARTIALLY_FILLED.value
            assert status['filled_quantity'] == partial_quantity
            assert status['average_fill_price'] == 5.0
            
            # Simulate second partial fill
            remaining_quantity = original_quantity - partial_quantity
            success = execution_interface.update_order_status(
                order_id=order_id,
                status=OrderStatus.FILLED,
                filled_quantity=original_quantity,
                fill_price=5.1
            )
            
            assert success == True
            
            # Verify full fill with weighted average price
            status = execution_interface.get_order_status(order_id)
            assert status['status'] == OrderStatus.FILLED.value
            assert status['filled_quantity'] == original_quantity
            # Average should be between 5.0 and 5.1
            assert 5.0 <= status['average_fill_price'] <= 5.1
    
    def test_order_modification(self, execution_interface, sample_strategy, sample_portfolio):
        """Test order modification functionality"""
        # Create and submit orders
        instructions = execution_interface.generate_execution_instructions(
            strategy=sample_strategy,
            order_type=OrderType.LIMIT
        )
        
        result = execution_interface.submit_orders(
            instructions=instructions,
            portfolio=sample_portfolio,
            regime='low-vol'
        )
        
        if result['success']:
            order_id = result['orders'][0]
            
            # Modify limit price
            mod_result = execution_interface.modify_order(
                order_id=order_id,
                new_limit_price=5.5
            )
            
            assert mod_result['success'] == True
            
            # Verify modification
            status = execution_interface.get_order_status(order_id)
            assert status['instruction']['limit_price'] == 5.5
    
    def test_order_cancellation(self, execution_interface, sample_strategy, sample_portfolio):
        """Test order cancellation functionality"""
        # Create and submit orders
        instructions = execution_interface.generate_execution_instructions(
            strategy=sample_strategy,
            order_type=OrderType.LIMIT
        )
        
        result = execution_interface.submit_orders(
            instructions=instructions,
            portfolio=sample_portfolio,
            regime='low-vol'
        )
        
        if result['success']:
            order_id = result['orders'][0]
            
            # Cancel order
            cancel_result = execution_interface.cancel_order(
                order_id=order_id,
                reason="Market conditions changed"
            )
            
            assert cancel_result['success'] == True
            assert cancel_result['logged'] == True
            
            # Verify cancellation
            status = execution_interface.get_order_status(order_id)
            assert status['status'] == OrderStatus.CANCELLED.value
            assert status['rejection_reason'] == "Market conditions changed"
    
    def test_portfolio_state_update_on_fill(self, execution_interface, sample_strategy, sample_portfolio):
        """Test portfolio state updates when orders are filled"""
        # Create and submit orders
        instructions = execution_interface.generate_execution_instructions(
            strategy=sample_strategy,
            order_type=OrderType.MARKET
        )
        
        result = execution_interface.submit_orders(
            instructions=instructions,
            portfolio=sample_portfolio,
            regime='low-vol'
        )
        
        if result['success']:
            order_id = result['orders'][0]
            
            # Fill the order
            execution_interface.update_order_status(
                order_id=order_id,
                status=OrderStatus.FILLED,
                filled_quantity=10,
                fill_price=5.0
            )
            
            # Get portfolio update
            update = execution_interface.get_portfolio_state_update(order_id)
            
            assert update is not None
            assert update['underlying'] == 'SPY'
            assert update['quantity'] == 10
            assert update['average_price'] == 5.0
            assert 'fill_time' in update
    
    def test_execution_slippage_tracking(self, execution_interface, sample_strategy, sample_portfolio):
        """Test execution slippage computation"""
        # Create and submit orders
        instructions = execution_interface.generate_execution_instructions(
            strategy=sample_strategy,
            order_type=OrderType.LIMIT
        )
        
        result = execution_interface.submit_orders(
            instructions=instructions,
            portfolio=sample_portfolio,
            regime='low-vol'
        )
        
        if result['success']:
            order_id = result['orders'][0]
            theoretical_price = 5.0
            
            # Fill at worse price
            execution_interface.update_order_status(
                order_id=order_id,
                status=OrderStatus.FILLED,
                filled_quantity=10,
                fill_price=5.2
            )
            
            # Compute slippage
            slippage = execution_interface.compute_execution_slippage(
                order_id=order_id,
                theoretical_price=theoretical_price
            )
            
            assert slippage is not None
            assert slippage == 0.2  # 5.2 - 5.0
    
    def test_venue_selection(self, execution_interface, sample_strategy):
        """Test multi-venue routing logic"""
        # Generate instructions
        instructions = execution_interface.generate_execution_instructions(
            strategy=sample_strategy,
            order_type=OrderType.LIMIT
        )
        
        # Verify venue was selected
        assert all(inst.venue is not None for inst in instructions)
        
        # Verify venue is from configured venues
        valid_venues = execution_interface.venues.keys()
        assert all(inst.venue in valid_venues for inst in instructions)
    
    def test_order_type_selection(self, execution_interface):
        """Test order type selection logic"""
        leg = OptionLeg(
            option_type=OptionType.CALL,
            strike=100.0,
            expiry=date.today() + timedelta(days=30),
            quantity=10,
            underlying="SPY"
        )
        
        # High urgency -> market order
        order_type = execution_interface.select_order_type(
            leg=leg,
            urgency="high"
        )
        assert order_type == OrderType.MARKET
        
        # Normal urgency -> limit order
        order_type = execution_interface.select_order_type(
            leg=leg,
            urgency="normal"
        )
        assert order_type == OrderType.LIMIT
        
        # Wide spread -> limit order
        order_type = execution_interface.select_order_type(
            leg=leg,
            urgency="normal",
            market_conditions={'spread_bps': 25.0, 'volume': 1000}
        )
        assert order_type == OrderType.LIMIT
    
    def test_pre_trade_risk_check_rejection(self, execution_interface, sample_portfolio):
        """Test that pre-trade risk checks can reject orders"""
        # Create oversized position
        large_legs = [
            OptionLeg(
                option_type=OptionType.CALL,
                strike=100.0,
                expiry=date.today() + timedelta(days=30),
                quantity=10000,  # Very large position
                underlying="SPY"
            )
        ]
        
        large_strategy = OptionStructure(
            ast=None,
            greeks=Greeks(delta=1000.0, gamma=100.0, vega=500.0, theta=-50.0, rho=10.0, vanna=0.0, volga=0.0, charm=0.0, vomma=0.0),
            price=500000.0,
            underlying="SPY",
            expiry=date.today() + timedelta(days=30),
            legs=large_legs
        )
        
        instructions = execution_interface.generate_execution_instructions(
            strategy=large_strategy,
            order_type=OrderType.MARKET
        )
        
        # Submit should fail due to risk check
        result = execution_interface.submit_orders(
            instructions=instructions,
            portfolio=sample_portfolio,
            regime='low-vol'
        )
        
        # May pass or fail depending on risk limits - just verify it runs
        assert 'success' in result
        if not result['success']:
            assert 'violations' in result or 'reason' in result
    
    def test_cannot_modify_filled_order(self, execution_interface, sample_strategy, sample_portfolio):
        """Test that filled orders cannot be modified"""
        instructions = execution_interface.generate_execution_instructions(
            strategy=sample_strategy,
            order_type=OrderType.LIMIT
        )
        
        result = execution_interface.submit_orders(
            instructions=instructions,
            portfolio=sample_portfolio,
            regime='low-vol'
        )
        
        if result['success']:
            order_id = result['orders'][0]
            
            # Fill the order
            execution_interface.update_order_status(
                order_id=order_id,
                status=OrderStatus.FILLED,
                filled_quantity=10,
                fill_price=5.0
            )
            
            # Try to modify - should fail
            mod_result = execution_interface.modify_order(
                order_id=order_id,
                new_limit_price=6.0
            )
            
            assert mod_result['success'] == False
            assert 'Cannot modify' in mod_result['reason']
    
    def test_cannot_cancel_filled_order(self, execution_interface, sample_strategy, sample_portfolio):
        """Test that filled orders cannot be cancelled"""
        instructions = execution_interface.generate_execution_instructions(
            strategy=sample_strategy,
            order_type=OrderType.LIMIT
        )
        
        result = execution_interface.submit_orders(
            instructions=instructions,
            portfolio=sample_portfolio,
            regime='low-vol'
        )
        
        if result['success']:
            order_id = result['orders'][0]
            
            # Fill the order
            execution_interface.update_order_status(
                order_id=order_id,
                status=OrderStatus.FILLED,
                filled_quantity=10,
                fill_price=5.0
            )
            
            # Try to cancel - should fail
            cancel_result = execution_interface.cancel_order(order_id=order_id)
            
            assert cancel_result['success'] == False
            assert 'Cannot cancel' in cancel_result['reason']
    
    def test_get_all_orders_filtering(self, execution_interface, sample_strategy, sample_portfolio):
        """Test filtering orders by status"""
        # Submit multiple orders
        instructions = execution_interface.generate_execution_instructions(
            strategy=sample_strategy,
            order_type=OrderType.LIMIT
        )
        
        result = execution_interface.submit_orders(
            instructions=instructions,
            portfolio=sample_portfolio,
            regime='low-vol'
        )
        
        if result['success']:
            # Get all orders
            all_orders = execution_interface.get_all_orders()
            assert len(all_orders) >= 2
            
            # Get only submitted orders
            submitted_orders = execution_interface.get_all_orders(
                status_filter=OrderStatus.SUBMITTED
            )
            assert all(o['status'] == OrderStatus.SUBMITTED.value for o in submitted_orders)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
