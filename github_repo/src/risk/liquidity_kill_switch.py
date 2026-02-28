"""
Liquidity-Aware Kill Switch System

This module enhances the kill switch system with liquidity-aware risk controls,
preventing forced liquidation when exit costs exceed remaining edge value.

Key Features:
- Liquidity risk assessment per position
- Exit cost vs edge value analysis
- Staged liquidation during liquidity crises
- Liquidity-aware emergency brake logic
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging


class LiquidityStatus(Enum):
    """Position liquidity status levels"""
    NORMAL = "normal"        # ExitRisk < 0.5
    CAUTIOUS = "cautious"    # ExitRisk 0.5-0.8
    DANGEROUS = "dangerous"  # ExitRisk 0.8-1.0
    FROZEN = "frozen"        # ExitRisk > 1.0
    CRISIS = "crisis"        # Systemic liquidity crisis


class LiquidationUrgency(Enum):
    """Liquidation urgency levels"""
    ROUTINE = "routine"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class LiquidityMetrics:
    """Position-level liquidity metrics"""
    symbol: str
    timestamp: datetime
    position_size: float
    market_value: float
    adv_20d: float              # 20-day average daily volume
    participation_rate: float   # Position size / ADV
    bid_ask_spread: float      # Current spread
    impact_cost: float         # Estimated market impact
    exit_risk: float           # Impact cost / remaining edge
    liquidity_status: LiquidityStatus
    days_to_liquidate: float   # Estimated liquidation time
    remaining_edge: float      # Expected remaining edge value


@dataclass
class PortfolioLiquidityState:
    """Portfolio-level liquidity state"""
    timestamp: datetime
    total_positions: int
    normal_positions: int
    dangerous_positions: int
    frozen_positions: int
    portfolio_liquidity_score: float  # 0-1, higher is more liquid
    systemic_risk_level: float       # 0-1, higher is more risky
    max_safe_liquidation_pct: float  # Max % that can be liquidated safely


class LiquidityRiskAssessor:
    """
    Assesses liquidity risk for individual positions and portfolio
    
    This system:
    1. Calculates participation rates and market impact costs
    2. Compares exit costs to remaining edge value
    3. Determines optimal liquidation strategies
    4. Provides liquidity-aware risk controls
    """
    
    def __init__(self,
                 impact_model_k: float = 0.005,  # Base impact coefficient
                 impact_model_beta: float = 0.6,  # Impact power law exponent
                 max_participation_rate: float = 0.20,  # Max 20% of ADV
                 liquidity_lookback: int = 20):  # Days for ADV calculation
        
        self.impact_model_k = impact_model_k
        self.impact_model_beta = impact_model_beta
        self.max_participation_rate = max_participation_rate
        self.liquidity_lookback = liquidity_lookback
        
        # Storage
        self.volume_history: Dict[str, pd.DataFrame] = {}
        self.liquidity_metrics: Dict[str, LiquidityMetrics] = {}
        self.portfolio_state: Optional[PortfolioLiquidityState] = None
        
        self.logger = logging.getLogger(__name__)
    
    def update_market_data(self,
                          symbol: str,
                          timestamp: datetime,
                          volume: float,
                          bid_price: float,
                          ask_price: float,
                          last_price: float) -> None:
        """Update market data for liquidity calculations"""
        
        # Calculate bid-ask spread
        spread = (ask_price - bid_price) / last_price if last_price > 0 else 0.0
        
        # Store volume data
        if symbol not in self.volume_history:
            self.volume_history[symbol] = pd.DataFrame()
        
        new_data = pd.DataFrame([{
            'timestamp': timestamp,
            'volume': volume,
            'bid_price': bid_price,
            'ask_price': ask_price,
            'last_price': last_price,
            'spread': spread
        }])
        
        self.volume_history[symbol] = pd.concat([
            self.volume_history[symbol],
            new_data
        ], ignore_index=True)
        
        # Keep only recent history
        cutoff_date = timestamp - timedelta(days=self.liquidity_lookback * 2)
        self.volume_history[symbol] = self.volume_history[symbol][
            self.volume_history[symbol]['timestamp'] >= cutoff_date
        ]
    
    def calculate_position_liquidity(self,
                                   symbol: str,
                                   position_size: float,
                                   market_value: float,
                                   remaining_edge: float,
                                   timestamp: datetime) -> LiquidityMetrics:
        """Calculate liquidity metrics for a position"""
        
        if symbol not in self.volume_history or self.volume_history[symbol].empty:
            # No data available - assume illiquid
            return self._create_default_metrics(symbol, position_size, market_value, 
                                              remaining_edge, timestamp)
        
        df = self.volume_history[symbol]
        recent_data = df[df['timestamp'] >= timestamp - timedelta(days=self.liquidity_lookback)]
        
        if recent_data.empty:
            return self._create_default_metrics(symbol, position_size, market_value,
                                              remaining_edge, timestamp)
        
        # Calculate 20-day ADV
        adv_20d = recent_data['volume'].mean()
        
        # Calculate participation rate
        participation_rate = abs(position_size) / max(adv_20d, 1.0)
        
        # Calculate market impact cost using power law model
        # Impact = k * (participation_rate)^beta
        impact_cost = self.impact_model_k * (participation_rate ** self.impact_model_beta)
        
        # Add spread cost
        current_spread = recent_data['spread'].iloc[-1] if not recent_data.empty else 0.01
        total_impact = impact_cost + current_spread / 2  # Half spread for market orders
        
        # Calculate exit risk ratio
        exit_risk = total_impact / max(abs(remaining_edge), 0.001) if remaining_edge != 0 else float('inf')
        
        # Estimate days to liquidate (assuming max participation rate)
        days_to_liquidate = participation_rate / self.max_participation_rate
        
        # Determine liquidity status
        if exit_risk < 0.5:
            status = LiquidityStatus.NORMAL
        elif exit_risk < 0.8:
            status = LiquidityStatus.CAUTIOUS
        elif exit_risk < 1.0:
            status = LiquidityStatus.DANGEROUS
        else:
            status = LiquidityStatus.FROZEN
        
        metrics = LiquidityMetrics(
            symbol=symbol,
            timestamp=timestamp,
            position_size=position_size,
            market_value=market_value,
            adv_20d=adv_20d,
            participation_rate=participation_rate,
            bid_ask_spread=current_spread,
            impact_cost=total_impact,
            exit_risk=exit_risk,
            liquidity_status=status,
            days_to_liquidate=days_to_liquidate,
            remaining_edge=remaining_edge
        )
        
        self.liquidity_metrics[symbol] = metrics
        return metrics
    
    def _create_default_metrics(self, symbol: str, position_size: float,
                               market_value: float, remaining_edge: float,
                               timestamp: datetime) -> LiquidityMetrics:
        """Create default metrics when no data available"""
        return LiquidityMetrics(
            symbol=symbol,
            timestamp=timestamp,
            position_size=position_size,
            market_value=market_value,
            adv_20d=0.0,
            participation_rate=1.0,  # Assume high participation
            bid_ask_spread=0.02,     # Assume 2% spread
            impact_cost=0.05,        # Assume 5% impact
            exit_risk=float('inf'),  # Assume very risky
            liquidity_status=LiquidityStatus.FROZEN,
            days_to_liquidate=float('inf'),
            remaining_edge=remaining_edge
        )
    
    def calculate_portfolio_liquidity_state(self,
                                          positions: Dict[str, Dict],
                                          timestamp: datetime) -> PortfolioLiquidityState:
        """Calculate portfolio-level liquidity state"""
        
        if not positions:
            return PortfolioLiquidityState(
                timestamp=timestamp,
                total_positions=0,
                normal_positions=0,
                dangerous_positions=0,
                frozen_positions=0,
                portfolio_liquidity_score=1.0,
                systemic_risk_level=0.0,
                max_safe_liquidation_pct=1.0
            )
        
        # Count positions by liquidity status
        status_counts = {status: 0 for status in LiquidityStatus}
        total_value = 0.0
        liquid_value = 0.0
        
        for symbol, pos_data in positions.items():
            if symbol in self.liquidity_metrics:
                metrics = self.liquidity_metrics[symbol]
                status_counts[metrics.liquidity_status] += 1
                
                total_value += abs(pos_data.get('market_value', 0.0))
                
                # Consider normal and cautious positions as liquid
                if metrics.liquidity_status in [LiquidityStatus.NORMAL, LiquidityStatus.CAUTIOUS]:
                    liquid_value += abs(pos_data.get('market_value', 0.0))
        
        total_positions = len(positions)
        normal_positions = status_counts[LiquidityStatus.NORMAL]
        dangerous_positions = status_counts[LiquidityStatus.DANGEROUS]
        frozen_positions = status_counts[LiquidityStatus.FROZEN]
        
        # Calculate portfolio liquidity score
        portfolio_liquidity_score = liquid_value / max(total_value, 1.0)
        
        # Calculate systemic risk level
        illiquid_positions = dangerous_positions + frozen_positions
        systemic_risk_level = illiquid_positions / max(total_positions, 1)
        
        # Calculate max safe liquidation percentage
        max_safe_liquidation_pct = min(1.0, portfolio_liquidity_score * 0.8)  # Conservative buffer
        
        self.portfolio_state = PortfolioLiquidityState(
            timestamp=timestamp,
            total_positions=total_positions,
            normal_positions=normal_positions,
            dangerous_positions=dangerous_positions,
            frozen_positions=frozen_positions,
            portfolio_liquidity_score=portfolio_liquidity_score,
            systemic_risk_level=systemic_risk_level,
            max_safe_liquidation_pct=max_safe_liquidation_pct
        )
        
        return self.portfolio_state
    
    def get_liquidation_strategy(self,
                               positions: Dict[str, Dict],
                               urgency: LiquidationUrgency) -> Dict[str, Any]:
        """
        Determine optimal liquidation strategy based on liquidity constraints
        
        Returns:
            Dict containing liquidation plan with timing and sequencing
        """
        
        if not positions:
            return {'strategy': 'no_positions', 'orders': []}
        
        # Categorize positions by liquidity
        liquid_positions = []
        illiquid_positions = []
        frozen_positions = []
        
        for symbol, pos_data in positions.items():
            if symbol in self.liquidity_metrics:
                metrics = self.liquidity_metrics[symbol]
                
                if metrics.liquidity_status in [LiquidityStatus.NORMAL, LiquidityStatus.CAUTIOUS]:
                    liquid_positions.append((symbol, pos_data, metrics))
                elif metrics.liquidity_status == LiquidityStatus.DANGEROUS:
                    illiquid_positions.append((symbol, pos_data, metrics))
                else:
                    frozen_positions.append((symbol, pos_data, metrics))
        
        # Determine strategy based on urgency
        if urgency in [LiquidationUrgency.ROUTINE, LiquidationUrgency.ELEVATED]:
            return self._create_gradual_liquidation_plan(liquid_positions, illiquid_positions)
        
        elif urgency == LiquidationUrgency.HIGH:
            return self._create_urgent_liquidation_plan(liquid_positions, illiquid_positions)
        
        else:  # CRITICAL or EMERGENCY
            return self._create_emergency_liquidation_plan(liquid_positions, illiquid_positions, frozen_positions)
    
    def _create_gradual_liquidation_plan(self, liquid_positions, illiquid_positions) -> Dict[str, Any]:
        """Create gradual liquidation plan for routine situations"""
        orders = []
        
        # Liquidate liquid positions first, respecting participation limits
        for symbol, pos_data, metrics in liquid_positions:
            daily_volume_limit = metrics.adv_20d * self.max_participation_rate
            position_size = abs(pos_data.get('position_size', 0.0))
            
            if position_size <= daily_volume_limit:
                # Can liquidate in one day
                orders.append({
                    'symbol': symbol,
                    'quantity': -pos_data.get('position_size', 0.0),
                    'urgency': 'normal',
                    'max_participation': self.max_participation_rate,
                    'estimated_days': 1
                })
            else:
                # Multi-day liquidation
                days_needed = np.ceil(position_size / daily_volume_limit)
                orders.append({
                    'symbol': symbol,
                    'quantity': -pos_data.get('position_size', 0.0),
                    'urgency': 'gradual',
                    'max_participation': self.max_participation_rate,
                    'estimated_days': days_needed
                })
        
        return {
            'strategy': 'gradual_liquidation',
            'orders': orders,
            'estimated_completion_days': max([o.get('estimated_days', 1) for o in orders], default=1),
            'illiquid_positions_held': len(illiquid_positions)
        }
    
    def _create_urgent_liquidation_plan(self, liquid_positions, illiquid_positions) -> Dict[str, Any]:
        """Create urgent liquidation plan with higher participation rates"""
        orders = []
        
        # Liquidate liquid positions with higher participation
        for symbol, pos_data, metrics in liquid_positions:
            orders.append({
                'symbol': symbol,
                'quantity': -pos_data.get('position_size', 0.0),
                'urgency': 'high',
                'max_participation': min(0.4, self.max_participation_rate * 2),  # Double normal rate
                'estimated_impact': metrics.impact_cost * 1.5  # Higher impact expected
            })
        
        # Attempt to liquidate some illiquid positions
        for symbol, pos_data, metrics in illiquid_positions[:3]:  # Only top 3 by size
            if metrics.exit_risk < 2.0:  # Only if not too expensive
                orders.append({
                    'symbol': symbol,
                    'quantity': -pos_data.get('position_size', 0.0) * 0.5,  # Partial liquidation
                    'urgency': 'high',
                    'max_participation': 0.3,
                    'estimated_impact': metrics.impact_cost * 2.0
                })
        
        return {
            'strategy': 'urgent_liquidation',
            'orders': orders,
            'estimated_completion_days': 2,
            'partial_liquidation': True
        }
    
    def _create_emergency_liquidation_plan(self, liquid_positions, illiquid_positions, frozen_positions) -> Dict[str, Any]:
        """Create emergency liquidation plan ignoring normal constraints"""
        orders = []
        
        # Liquidate everything possible, regardless of impact
        all_positions = liquid_positions + illiquid_positions
        
        for symbol, pos_data, metrics in all_positions:
            orders.append({
                'symbol': symbol,
                'quantity': -pos_data.get('position_size', 0.0),
                'urgency': 'emergency',
                'max_participation': 1.0,  # No participation limits
                'estimated_impact': metrics.impact_cost * 3.0,  # Very high impact expected
                'accept_high_impact': True
            })
        
        # For frozen positions, create hedge orders if possible
        hedge_orders = []
        for symbol, pos_data, metrics in frozen_positions:
            hedge_orders.append({
                'symbol': f"{symbol}_HEDGE",
                'quantity': pos_data.get('position_size', 0.0),  # Opposite position
                'urgency': 'emergency',
                'order_type': 'hedge',
                'note': f"Hedge for frozen position {symbol}"
            })
        
        return {
            'strategy': 'emergency_liquidation',
            'orders': orders,
            'hedge_orders': hedge_orders,
            'estimated_completion_days': 1,
            'high_impact_expected': True,
            'frozen_positions': len(frozen_positions)
        }


class LiquidityAwareKillSwitch:
    """
    Enhanced kill switch with liquidity awareness
    
    This system modifies kill switch behavior based on liquidity conditions:
    - Prevents forced liquidation when exit costs exceed edge value
    - Implements staged liquidation during liquidity crises
    - Provides liquidity-aware emergency brake logic
    """
    
    def __init__(self, 
                 base_kill_switch,
                 liquidity_assessor: LiquidityRiskAssessor,
                 max_acceptable_exit_risk: float = 1.0):
        
        self.base_kill_switch = base_kill_switch
        self.liquidity_assessor = liquidity_assessor
        self.max_acceptable_exit_risk = max_acceptable_exit_risk
        
        self.logger = logging.getLogger(__name__)
    
    def should_trigger_kill_switch(self,
                                 trigger_type,
                                 current_metrics: Dict[str, float],
                                 positions: Dict[str, Dict]) -> Tuple[bool, str]:
        """
        Determine if kill switch should trigger considering liquidity constraints
        
        Returns:
            Tuple of (should_trigger, reason)
        """
        
        # First check if base kill switch would trigger
        try:
            base_trigger = self.base_kill_switch._check_trigger_condition(
                trigger_type, current_metrics, self.base_kill_switch.triggers[trigger_type]
            )
        except (KeyError, TypeError):
            # Handle mock objects or missing triggers
            base_trigger = self.base_kill_switch._check_trigger_condition(
                trigger_type, current_metrics, {}
            )
        
        if not base_trigger:
            return False, "base_conditions_not_met"
        
        # Calculate portfolio liquidity state
        portfolio_liquidity = self.liquidity_assessor.calculate_portfolio_liquidity_state(
            positions, datetime.now()
        )
        
        # Check if liquidation would be counterproductive
        if portfolio_liquidity.systemic_risk_level > 0.7:  # 70% of positions illiquid
            
            # For drawdown triggers, check if holding is better than selling
            if trigger_type.value in ['drawdown_limit', 'var_breach']:
                avg_exit_risk = np.mean([
                    metrics.exit_risk for metrics in self.liquidity_assessor.liquidity_metrics.values()
                    if metrics.exit_risk != float('inf')
                ])
                
                if avg_exit_risk > self.max_acceptable_exit_risk:
                    return False, f"exit_risk_too_high_{avg_exit_risk:.2f}"
        
        # For concentration risk, only trigger if the concentrated position is liquid
        if trigger_type.value == 'concentration_risk':
            # Find most concentrated position
            max_concentration = 0.0
            max_symbol = None
            
            for symbol, pos_data in positions.items():
                concentration = abs(pos_data.get('market_value', 0.0)) / sum(
                    abs(p.get('market_value', 0.0)) for p in positions.values()
                )
                if concentration > max_concentration:
                    max_concentration = concentration
                    max_symbol = symbol
            
            if max_symbol and max_symbol in self.liquidity_assessor.liquidity_metrics:
                metrics = self.liquidity_assessor.liquidity_metrics[max_symbol]
                if metrics.liquidity_status == LiquidityStatus.FROZEN:
                    return False, f"concentrated_position_frozen_{max_symbol}"
        
        return True, "liquidity_conditions_acceptable"
    
    def execute_liquidity_aware_liquidation(self,
                                          positions: Dict[str, Dict],
                                          urgency: LiquidationUrgency) -> Dict[str, Any]:
        """
        Execute liquidation with liquidity awareness
        
        Returns:
            Dict containing execution results and liquidity impact
        """
        
        # Get liquidation strategy
        strategy = self.liquidity_assessor.get_liquidation_strategy(positions, urgency)
        
        # Execute based on strategy type
        if strategy['strategy'] == 'emergency_liquidation':
            return self._execute_emergency_liquidation(strategy)
        elif strategy['strategy'] == 'urgent_liquidation':
            return self._execute_urgent_liquidation(strategy)
        else:
            return self._execute_gradual_liquidation(strategy)
    
    def _execute_emergency_liquidation(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Execute emergency liquidation accepting high impact"""
        
        self.logger.critical("Executing emergency liquidation with high impact acceptance")
        
        # Execute main orders
        executed_orders = []
        total_impact = 0.0
        
        for order in strategy['orders']:
            # Simulate execution with high impact
            impact = order.get('estimated_impact', 0.05)
            total_impact += impact
            
            executed_orders.append({
                'symbol': order['symbol'],
                'quantity_requested': order['quantity'],
                'quantity_executed': order['quantity'] * 0.9,  # 90% fill rate in emergency
                'market_impact': impact,
                'execution_time': 0.5,  # Very fast execution
                'status': 'EXECUTED'
            })
        
        # Execute hedge orders for frozen positions
        hedge_results = []
        for hedge_order in strategy.get('hedge_orders', []):
            hedge_results.append({
                'symbol': hedge_order['symbol'],
                'quantity': hedge_order['quantity'],
                'status': 'HEDGE_PLACED',
                'note': hedge_order.get('note', '')
            })
        
        return {
            'strategy_type': 'emergency_liquidation',
            'executed_orders': executed_orders,
            'hedge_orders': hedge_results,
            'total_market_impact': total_impact,
            'execution_time_minutes': 30,
            'frozen_positions_hedged': len(hedge_results),
            'success': True
        }
    
    def _execute_urgent_liquidation(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Execute urgent liquidation with elevated participation"""
        
        self.logger.warning("Executing urgent liquidation with elevated market participation")
        
        executed_orders = []
        total_impact = 0.0
        
        for order in strategy['orders']:
            impact = order.get('estimated_impact', 0.02)
            total_impact += impact
            
            executed_orders.append({
                'symbol': order['symbol'],
                'quantity_requested': order['quantity'],
                'quantity_executed': order['quantity'] * 0.95,  # 95% fill rate
                'market_impact': impact,
                'execution_time': 2.0,
                'status': 'EXECUTED'
            })
        
        return {
            'strategy_type': 'urgent_liquidation',
            'executed_orders': executed_orders,
            'total_market_impact': total_impact,
            'execution_time_minutes': 120,
            'partial_liquidation': strategy.get('partial_liquidation', False),
            'success': True
        }
    
    def _execute_gradual_liquidation(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """Execute gradual liquidation respecting participation limits"""
        
        self.logger.info("Executing gradual liquidation with participation limits")
        
        # For gradual liquidation, we only execute day 1 orders
        executed_orders = []
        scheduled_orders = []
        total_impact = 0.0
        
        for order in strategy['orders']:
            if order.get('estimated_days', 1) == 1:
                # Execute immediately
                impact = 0.01  # Low impact for gradual execution
                total_impact += impact
                
                executed_orders.append({
                    'symbol': order['symbol'],
                    'quantity_requested': order['quantity'],
                    'quantity_executed': order['quantity'],
                    'market_impact': impact,
                    'execution_time': 5.0,
                    'status': 'EXECUTED'
                })
            else:
                # Schedule for future execution
                daily_quantity = order['quantity'] / order['estimated_days']
                scheduled_orders.append({
                    'symbol': order['symbol'],
                    'daily_quantity': daily_quantity,
                    'remaining_days': order['estimated_days'] - 1,
                    'status': 'SCHEDULED'
                })
        
        return {
            'strategy_type': 'gradual_liquidation',
            'executed_orders': executed_orders,
            'scheduled_orders': scheduled_orders,
            'total_market_impact': total_impact,
            'execution_time_minutes': 300,
            'estimated_completion_days': strategy.get('estimated_completion_days', 1),
            'success': True
        }
    
    def get_liquidity_status_summary(self) -> Dict[str, Any]:
        """Get comprehensive liquidity status summary"""
        
        if not self.liquidity_assessor.portfolio_state:
            return {'status': 'no_data'}
        
        state = self.liquidity_assessor.portfolio_state
        
        return {
            'timestamp': state.timestamp,
            'portfolio_liquidity_score': state.portfolio_liquidity_score,
            'systemic_risk_level': state.systemic_risk_level,
            'max_safe_liquidation_pct': state.max_safe_liquidation_pct,
            'position_breakdown': {
                'total': state.total_positions,
                'normal': state.normal_positions,
                'dangerous': state.dangerous_positions,
                'frozen': state.frozen_positions
            },
            'kill_switch_recommendation': self._get_kill_switch_recommendation(state)
        }
    
    def _get_kill_switch_recommendation(self, state: PortfolioLiquidityState) -> str:
        """Get kill switch recommendation based on liquidity state"""
        
        if state.systemic_risk_level > 0.8:
            return "DISABLE_KILL_SWITCH_HIGH_ILLIQUIDITY"
        elif state.systemic_risk_level > 0.5:
            return "USE_GRADUAL_LIQUIDATION_ONLY"
        elif state.portfolio_liquidity_score < 0.3:
            return "EMERGENCY_LIQUIDATION_HIGH_IMPACT"
        else:
            return "NORMAL_KILL_SWITCH_OPERATION"