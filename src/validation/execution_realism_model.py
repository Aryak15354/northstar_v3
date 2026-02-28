#!/usr/bin/env python3
"""
⚙️ EXECUTION REALISM MODEL - PHASE 5: INFRASTRUCTURE LAYER
Realistic execution friction simulation for institutional validation

This implements the execution realism requirements for Phase 5 (Infrastructure)
of the institutional validation framework. It simulates real trading friction
beyond simple transaction costs to ensure backtest results match live trading.

CRITICAL PRINCIPLE: Realistic Execution Simulation
- Simulate partial fills based on liquidity constraints
- Apply market impact scaling with trade volume
- Model T+1 rebalancing delay instead of T+0
- Track execution quality metrics
- Ensure backtest matches live trading expectations

Usage:
    from src.validation.execution_realism_model import ExecutionRealismModel
    
    model = ExecutionRealismModel()
    execution_result = model.simulate_execution(trades, market_data)
    quality_metrics = model.get_execution_quality()
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import warnings

warnings.filterwarnings('ignore')


@dataclass
class Trade:
    """
    Trade record for execution simulation
    
    Complete trade information for realistic execution modeling.
    """
    ticker: str
    target_weight: float  # Target portfolio weight
    current_weight: float  # Current portfolio weight
    trade_size: float  # Trade size as % of portfolio
    direction: str  # 'buy' or 'sell'
    urgency: str  # 'normal', 'high', 'low'
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return asdict(self)
    
    def validate(self) -> List[str]:
        """Validate trade data"""
        errors = []
        
        if not (-1.0 <= self.target_weight <= 1.0):
            errors.append(f"Target weight {self.target_weight} outside bounds [-1.0, 1.0]")
        
        if not (-1.0 <= self.current_weight <= 1.0):
            errors.append(f"Current weight {self.current_weight} outside bounds [-1.0, 1.0]")
        
        if self.trade_size < 0.0:
            errors.append(f"Trade size {self.trade_size} is negative")
        
        if self.direction not in ['buy', 'sell']:
            errors.append(f"Invalid direction: {self.direction}")
        
        if self.urgency not in ['normal', 'high', 'low']:
            errors.append(f"Invalid urgency: {self.urgency}")
        
        return errors


@dataclass
class ExecutionResult:
    """
    Execution result record
    
    Complete execution outcome with friction and quality metrics.
    """
    ticker: str
    target_weight: float
    achieved_weight: float  # Actually achieved weight after friction
    fill_rate: float  # Percentage of trade filled (0.0 to 1.0)
    slippage: float  # Slippage as % of trade value
    market_impact: float  # Market impact as % of trade value
    delay_days: int  # Execution delay in days
    total_cost: float  # Total execution cost
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return asdict(self)
    
    def validate(self) -> List[str]:
        """Validate execution result"""
        errors = []
        
        if not (0.0 <= self.fill_rate <= 1.0):
            errors.append(f"Fill rate {self.fill_rate} outside bounds [0.0, 1.0]")
        
        if self.slippage < 0.0:
            errors.append(f"Slippage {self.slippage} is negative")
        
        if self.market_impact < 0.0:
            errors.append(f"Market impact {self.market_impact} is negative")
        
        if self.delay_days < 0:
            errors.append(f"Delay days {self.delay_days} is negative")
        
        if self.total_cost < 0.0:
            errors.append(f"Total cost {self.total_cost} is negative")
        
        return errors


@dataclass
class ExecutionQuality:
    """
    Execution quality metrics
    
    Aggregate metrics for execution quality assessment.
    """
    date: datetime
    avg_slippage: float  # Average slippage across all trades
    fill_rate: float  # Average fill rate
    rebalance_delay: float  # Average rebalancing delay
    realized_cost: float  # Total realized execution cost
    trade_count: int  # Number of trades executed
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        result = asdict(self)
        result['date'] = result['date'].isoformat()
        return result
    
    def validate(self) -> List[str]:
        """Validate execution quality metrics"""
        errors = []
        
        if not (0.0 <= self.fill_rate <= 1.0):
            errors.append(f"Fill rate {self.fill_rate} outside bounds [0.0, 1.0]")
        
        if self.avg_slippage < 0.0:
            errors.append(f"Average slippage {self.avg_slippage} is negative")
        
        if self.rebalance_delay < 0.0:
            errors.append(f"Rebalance delay {self.rebalance_delay} is negative")
        
        if self.realized_cost < 0.0:
            errors.append(f"Realized cost {self.realized_cost} is negative")
        
        if self.trade_count < 0:
            errors.append(f"Trade count {self.trade_count} is negative")
        
        return errors


class ExecutionRealismModel:
    """
    Execution Realism Model - Phase 5: Infrastructure Layer
    
    Simulates realistic trading friction including partial fills, slippage,
    market impact, and execution delays to ensure backtest results match
    live trading expectations.
    
    ENFORCES REQUIREMENTS:
    - 17.1-17.8: Execution realism modeling
    
    V3 INTEGRATION:
    - Uses UnifiedState for state storage (Requirement 14.1)
    - Emits events through EventBus (Requirement 14.2)
    - Integrates with Market_Clock for time-driven updates (Requirement 14.4)
    """
    
    def __init__(self, 
                 base_dir: str = "data/execution",
                 unified_state=None,
                 event_bus=None,
                 market_clock=None):
        """
        Initialize Execution Realism Model
        
        Args:
            base_dir: Base directory for execution quality data
            unified_state: Optional UnifiedState instance for V3 integration
            event_bus: Optional EventBus instance for V3 integration
            market_clock: Optional Market_Clock instance for V3 integration
        """
        self.base_dir = base_dir
        
        # Create base directory
        os.makedirs(base_dir, exist_ok=True)
        
        # V3 Integration (optional)
        self.unified_state = unified_state
        self.event_bus = event_bus
        self.market_clock = market_clock
        
        # Execution parameters
        self.base_slippage = 0.0005  # 5 bps base slippage
        self.market_impact_factor = 0.5  # Market impact scaling
        self.liquidity_threshold = 0.15  # 15% of ADV threshold
        self.delay_probability = 0.1  # 10% chance of T+1 delay
        
        # Historical execution data
        self.execution_history: List[ExecutionQuality] = []
        
        print("⚙️ Execution Realism Model initialized")
        print(f"   Output: {self.base_dir}/")
        print(f"   Base slippage: {self.base_slippage:.1%}")
        print(f"   Market impact factor: {self.market_impact_factor}")
        print(f"   Liquidity threshold: {self.liquidity_threshold:.1%}")
        if unified_state:
            print("   ✅ V3 Integration: UnifiedState connected")
        if event_bus:
            print("   ✅ V3 Integration: EventBus connected")
        if market_clock:
            print("   ✅ V3 Integration: Market_Clock connected")
    
    def _calculate_liquidity_constraint(self, 
                                      ticker: str, 
                                      trade_size: float,
                                      market_data: Optional[Dict] = None) -> float:
        """
        Calculate liquidity constraint for trade
        
        Args:
            ticker: Stock ticker
            trade_size: Trade size as % of portfolio
            market_data: Optional market data with ADV information
            
        Returns:
            Liquidity constraint factor (0.0 to 1.0)
        """
        
        # Default ADV if not provided
        default_adv = 1000000  # $1M default ADV
        
        if market_data and ticker in market_data:
            adv = market_data[ticker].get('adv', default_adv)
        else:
            # Estimate ADV based on ticker (rough heuristic)
            if ticker in ['RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK']:
                adv = 5000000  # Large cap - $5M ADV
            elif ticker.endswith('.NS') or len(ticker) <= 6:
                adv = 2000000  # Mid cap - $2M ADV
            else:
                adv = default_adv  # Small cap - $1M ADV
        
        # Assume portfolio size for calculation
        portfolio_size = 10000000  # $10M portfolio assumption
        trade_value = abs(trade_size) * portfolio_size
        
        # Calculate trade as % of ADV
        adv_percentage = trade_value / adv
        
        # Apply liquidity constraint
        if adv_percentage <= self.liquidity_threshold:
            return 1.0  # No constraint
        elif adv_percentage <= 0.30:
            return 0.8  # Moderate constraint
        elif adv_percentage <= 0.50:
            return 0.6  # High constraint
        else:
            return 0.4  # Severe constraint
    
    def _calculate_market_impact(self, 
                               trade_size: float,
                               liquidity_factor: float,
                               urgency: str) -> float:
        """
        Calculate market impact for trade
        
        Args:
            trade_size: Trade size as % of portfolio
            liquidity_factor: Liquidity constraint factor
            urgency: Trade urgency level
            
        Returns:
            Market impact as % of trade value
        """
        
        # Base market impact (square root of trade size)
        base_impact = self.market_impact_factor * np.sqrt(abs(trade_size))
        
        # Adjust for liquidity
        liquidity_adjustment = (2.0 - liquidity_factor)  # Higher impact for lower liquidity
        
        # Adjust for urgency
        urgency_multiplier = {
            'low': 0.5,     # Patient execution
            'normal': 1.0,  # Normal execution
            'high': 2.0     # Urgent execution
        }.get(urgency, 1.0)
        
        market_impact = base_impact * liquidity_adjustment * urgency_multiplier
        
        # Cap at reasonable level
        return min(market_impact, 0.02)  # Max 2% market impact
    
    def _calculate_slippage(self, 
                          trade_size: float,
                          market_impact: float,
                          volatility: float = 0.02) -> float:
        """
        Calculate slippage for trade
        
        Args:
            trade_size: Trade size as % of portfolio
            market_impact: Market impact
            volatility: Stock volatility (default 2% daily)
            
        Returns:
            Slippage as % of trade value
        """
        
        # Base slippage
        base_slippage = self.base_slippage
        
        # Volatility component
        volatility_slippage = volatility * 0.1  # 10% of daily volatility
        
        # Size component
        size_slippage = abs(trade_size) * 0.01  # 1% per 1% of portfolio
        
        # Total slippage
        total_slippage = base_slippage + volatility_slippage + size_slippage + market_impact
        
        # Add random component (bid-ask spread variation)
        random_component = np.random.normal(0, base_slippage * 0.5)
        
        return max(0, total_slippage + random_component)
    
    def _determine_execution_delay(self, 
                                 liquidity_factor: float,
                                 urgency: str) -> int:
        """
        Determine execution delay in days
        
        Args:
            liquidity_factor: Liquidity constraint factor
            urgency: Trade urgency level
            
        Returns:
            Delay in days (0 for T+0, 1 for T+1, etc.)
        """
        
        # Base delay probability
        delay_prob = self.delay_probability
        
        # Adjust for liquidity (lower liquidity = higher delay probability)
        delay_prob *= (2.0 - liquidity_factor)
        
        # Adjust for urgency
        urgency_adjustment = {
            'low': 2.0,     # Higher delay probability for patient trades
            'normal': 1.0,  # Normal delay probability
            'high': 0.3     # Lower delay probability for urgent trades
        }.get(urgency, 1.0)
        
        delay_prob *= urgency_adjustment
        
        # Determine delay
        if np.random.random() < delay_prob:
            # Weighted random delay (most delays are T+1)
            delay_weights = [0.7, 0.2, 0.1]  # T+1, T+2, T+3
            return np.random.choice([1, 2, 3], p=delay_weights)
        else:
            return 0  # T+0 execution
    
    def simulate_trade_execution(self, 
                               trade: Trade,
                               market_data: Optional[Dict] = None) -> ExecutionResult:
        """
        Simulate execution of a single trade
        
        ENFORCES PROPERTY 36: Execution Friction Application
        VALIDATES REQUIREMENTS 17.1, 17.2, 17.3
        
        Args:
            trade: Trade to execute
            market_data: Optional market data
            
        Returns:
            ExecutionResult with friction applied
        """
        
        # Validate trade
        validation_errors = trade.validate()
        if validation_errors:
            print(f"⚠️ Trade validation warnings for {trade.ticker}:")
            for error in validation_errors:
                print(f"   {error}")
        
        # Calculate liquidity constraint
        liquidity_factor = self._calculate_liquidity_constraint(
            trade.ticker, trade.trade_size, market_data
        )
        
        # Calculate market impact
        market_impact = self._calculate_market_impact(
            trade.trade_size, liquidity_factor, trade.urgency
        )
        
        # Calculate slippage
        volatility = 0.02  # Default 2% daily volatility
        if market_data and trade.ticker in market_data:
            volatility = market_data[trade.ticker].get('volatility', 0.02)
        
        slippage = self._calculate_slippage(trade.trade_size, market_impact, volatility)
        
        # Determine execution delay
        delay_days = self._determine_execution_delay(liquidity_factor, trade.urgency)
        
        # Calculate fill rate (partial fills)
        fill_rate = liquidity_factor
        
        # If delayed execution, reduce fill rate further
        if delay_days > 0:
            fill_rate *= 0.9  # 10% reduction for delayed execution
        
        # Calculate achieved weight
        weight_change = trade.target_weight - trade.current_weight
        achieved_change = weight_change * fill_rate
        achieved_weight = trade.current_weight + achieved_change
        
        # Calculate total cost
        total_cost = slippage + market_impact
        
        # Create execution result
        result = ExecutionResult(
            ticker=trade.ticker,
            target_weight=trade.target_weight,
            achieved_weight=achieved_weight,
            fill_rate=fill_rate,
            slippage=slippage,
            market_impact=market_impact,
            delay_days=delay_days,
            total_cost=total_cost
        )
        
        # Validate result
        result_errors = result.validate()
        if result_errors:
            print(f"⚠️ Execution result validation warnings for {trade.ticker}:")
            for error in result_errors:
                print(f"   {error}")
        
        return result
    
    def simulate_portfolio_rebalance(self, 
                                   trades: List[Trade],
                                   market_data: Optional[Dict] = None) -> List[ExecutionResult]:
        """
        Simulate execution of portfolio rebalance
        
        ENFORCES PROPERTY 36: Execution Friction Application
        VALIDATES REQUIREMENTS 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 17.7, 17.8
        
        Args:
            trades: List of trades to execute
            market_data: Optional market data
            
        Returns:
            List of ExecutionResult objects
        """
        
        print(f"⚙️ Simulating portfolio rebalance: {len(trades)} trades")
        
        results = []
        
        for trade in trades:
            result = self.simulate_trade_execution(trade, market_data)
            results.append(result)
        
        # Calculate aggregate metrics
        if results:
            avg_slippage = np.mean([r.slippage for r in results])
            avg_fill_rate = np.mean([r.fill_rate for r in results])
            avg_delay = np.mean([r.delay_days for r in results])
            total_cost = sum([r.total_cost * abs(r.target_weight - r.achieved_weight) for r in results])
            
            print(f"   Average slippage: {avg_slippage:.2%}")
            print(f"   Average fill rate: {avg_fill_rate:.1%}")
            print(f"   Average delay: {avg_delay:.1f} days")
            print(f"   Total cost: {total_cost:.2%}")
        
        return results
    
    def record_execution_quality(self, 
                               date: datetime,
                               execution_results: List[ExecutionResult]) -> ExecutionQuality:
        """
        Record execution quality metrics
        
        VALIDATES REQUIREMENTS 17.7, 17.8
        
        Args:
            date: Date of execution
            execution_results: List of execution results
            
        Returns:
            ExecutionQuality metrics
        """
        
        if not execution_results:
            # Empty execution
            quality = ExecutionQuality(
                date=date,
                avg_slippage=0.0,
                fill_rate=1.0,
                rebalance_delay=0.0,
                realized_cost=0.0,
                trade_count=0
            )
        else:
            # Calculate metrics
            avg_slippage = np.mean([r.slippage for r in execution_results])
            avg_fill_rate = np.mean([r.fill_rate for r in execution_results])
            avg_delay = np.mean([r.delay_days for r in execution_results])
            
            # Weight costs by trade size
            total_cost = sum([
                r.total_cost * abs(r.target_weight - r.achieved_weight) 
                for r in execution_results
            ])
            
            quality = ExecutionQuality(
                date=date,
                avg_slippage=avg_slippage,
                fill_rate=avg_fill_rate,
                rebalance_delay=avg_delay,
                realized_cost=total_cost,
                trade_count=len(execution_results)
            )
        
        # Validate quality metrics
        validation_errors = quality.validate()
        if validation_errors:
            print(f"⚠️ Execution quality validation warnings for {date.date()}:")
            for error in validation_errors:
                print(f"   {error}")
        
        # Store in history
        self.execution_history.append(quality)
        
        # Persist to file
        self._save_execution_quality(quality)
        
        # V3 Integration: Store in UnifiedState
        self._store_quality_in_unified_state(quality)
        
        # V3 Integration: Emit event
        self._emit_quality_event(quality)
        
        return quality
    
    def _save_execution_quality(self, quality: ExecutionQuality):
        """
        Save execution quality to parquet file
        
        Args:
            quality: ExecutionQuality to save
        """
        
        try:
            # Convert to DataFrame
            quality_df = pd.DataFrame([quality.to_dict()])
            
            # Enforce schema
            quality_df = self._enforce_quality_schema(quality_df)
            
            # Append to existing file or create new
            file_path = os.path.join(self.base_dir, "execution_quality.parquet")
            
            if os.path.exists(file_path):
                # Append to existing file
                existing_df = pd.read_parquet(file_path)
                combined_df = pd.concat([existing_df, quality_df], ignore_index=True)
                combined_df.to_parquet(file_path, index=False)
            else:
                # Create new file
                quality_df.to_parquet(file_path, index=False)
            
            print(f"✅ Execution quality saved for {quality.date.date()}")
            
        except Exception as e:
            print(f"❌ Failed to save execution quality: {e}")
    
    def _enforce_quality_schema(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Enforce execution quality schema
        
        Args:
            df: DataFrame to validate
            
        Returns:
            DataFrame with enforced schema
        """
        
        # Required columns with types
        required_schema = {
            'date': 'datetime64[ns]',
            'avg_slippage': 'float64',
            'fill_rate': 'float64',
            'rebalance_delay': 'float64',
            'realized_cost': 'float64',
            'trade_count': 'int64'
        }
        
        # Ensure all required columns exist
        for col in required_schema.keys():
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        # Enforce types
        for col, dtype in required_schema.items():
            if col == 'date':
                df[col] = pd.to_datetime(df[col])
            else:
                df[col] = df[col].astype(dtype)
        
        # Validate bounds
        if not ((df['fill_rate'] >= 0.0) & (df['fill_rate'] <= 1.0)).all():
            raise ValueError("Fill rate must be between 0.0 and 1.0")
        
        if not (df['avg_slippage'] >= 0.0).all():
            raise ValueError("Average slippage must be non-negative")
        
        if not (df['rebalance_delay'] >= 0.0).all():
            raise ValueError("Rebalance delay must be non-negative")
        
        if not (df['realized_cost'] >= 0.0).all():
            raise ValueError("Realized cost must be non-negative")
        
        if not (df['trade_count'] >= 0).all():
            raise ValueError("Trade count must be non-negative")
        
        return df
    
    def get_execution_quality_summary(self, 
                                    start_date: Optional[datetime] = None,
                                    end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Get execution quality summary for date range
        
        Args:
            start_date: Start date (optional)
            end_date: End date (optional)
            
        Returns:
            Dictionary with execution quality summary
        """
        
        # Filter history by date range
        filtered_history = []
        for quality in self.execution_history:
            if start_date and quality.date < start_date:
                continue
            if end_date and quality.date > end_date:
                continue
            filtered_history.append(quality)
        
        if not filtered_history:
            return {
                'period': {
                    'start': start_date.isoformat() if start_date else None,
                    'end': end_date.isoformat() if end_date else None
                },
                'days': 0,
                'avg_slippage': 0.0,
                'avg_fill_rate': 1.0,
                'avg_delay': 0.0,
                'total_cost': 0.0,
                'total_trades': 0
            }
        
        # Calculate summary statistics
        avg_slippage = np.mean([q.avg_slippage for q in filtered_history])
        avg_fill_rate = np.mean([q.fill_rate for q in filtered_history])
        avg_delay = np.mean([q.rebalance_delay for q in filtered_history])
        total_cost = sum([q.realized_cost for q in filtered_history])
        total_trades = sum([q.trade_count for q in filtered_history])
        
        return {
            'period': {
                'start': start_date.isoformat() if start_date else filtered_history[0].date.isoformat(),
                'end': end_date.isoformat() if end_date else filtered_history[-1].date.isoformat()
            },
            'days': len(filtered_history),
            'avg_slippage': avg_slippage,
            'avg_fill_rate': avg_fill_rate,
            'avg_delay': avg_delay,
            'total_cost': total_cost,
            'total_trades': total_trades
        }
    
    def load_execution_quality_history(self) -> bool:
        """
        Load execution quality history from file
        
        Returns:
            True if successful, False otherwise
        """
        
        file_path = os.path.join(self.base_dir, "execution_quality.parquet")
        
        if not os.path.exists(file_path):
            return False
        
        try:
            df = pd.read_parquet(file_path)
            df = self._enforce_quality_schema(df)
            
            # Convert to ExecutionQuality objects
            self.execution_history = []
            for _, row in df.iterrows():
                quality = ExecutionQuality(
                    date=row['date'],
                    avg_slippage=row['avg_slippage'],
                    fill_rate=row['fill_rate'],
                    rebalance_delay=row['rebalance_delay'],
                    realized_cost=row['realized_cost'],
                    trade_count=row['trade_count']
                )
                self.execution_history.append(quality)
            
            print(f"✅ Loaded {len(self.execution_history)} execution quality records")
            return True
            
        except Exception as e:
            print(f"❌ Failed to load execution quality history: {e}")
            return False
    
    # ========================================================================
    # V3 INTEGRATION METHODS
    # ========================================================================
    
    def _store_quality_in_unified_state(self, quality: ExecutionQuality):
        """Store execution quality in UnifiedState"""
        
        if self.unified_state is None:
            return
        
        try:
            component_name = "execution_realism_model"
            
            # Store latest quality metrics
            self.unified_state.set(
                component=component_name,
                key="latest_quality",
                value={
                    "date": quality.date.isoformat(),
                    "avg_slippage": quality.avg_slippage,
                    "fill_rate": quality.fill_rate,
                    "rebalance_delay": quality.rebalance_delay,
                    "realized_cost": quality.realized_cost,
                    "trade_count": quality.trade_count
                }
            )
            
        except Exception as e:
            print(f"⚠️ Failed to store quality in UnifiedState: {e}")
    
    def _emit_quality_event(self, quality: ExecutionQuality):
        """Emit execution quality event through EventBus"""
        
        if self.event_bus is None:
            return
        
        try:
            self.event_bus.emit(
                event_type="EXECUTION_QUALITY_RECORDED",
                source="execution_realism_model",
                data={
                    "date": quality.date.isoformat(),
                    "avg_slippage": quality.avg_slippage,
                    "fill_rate": quality.fill_rate,
                    "rebalance_delay": quality.rebalance_delay,
                    "realized_cost": quality.realized_cost,
                    "trade_count": quality.trade_count
                },
                tags=["execution", "quality", "realism"]
            )
            
            # Emit alert if execution quality is poor
            if quality.fill_rate < 0.8 or quality.avg_slippage > 0.01:
                self.event_bus.emit(
                    event_type="EXECUTION_QUALITY_ALERT",
                    source="execution_realism_model",
                    data={
                        "date": quality.date.isoformat(),
                        "fill_rate": quality.fill_rate,
                        "avg_slippage": quality.avg_slippage,
                        "threshold_fill_rate": 0.8,
                        "threshold_slippage": 0.01
                    },
                    tags=["execution", "quality", "alert"],
                    priority="HIGH"
                )
            
        except Exception as e:
            print(f"⚠️ Failed to emit quality event: {e}")


def main():
    """Demonstrate Execution Realism Model"""
    
    print("⚙️ EXECUTION REALISM MODEL - DEMONSTRATION")
    print("=" * 60)
    
    # Initialize model
    model = ExecutionRealismModel(base_dir="data/test_execution")
    
    # Create sample trades
    trades = [
        Trade(
            ticker="RELIANCE",
            target_weight=0.08,
            current_weight=0.05,
            trade_size=0.03,
            direction="buy",
            urgency="normal"
        ),
        Trade(
            ticker="TCS",
            target_weight=0.06,
            current_weight=0.08,
            trade_size=0.02,
            direction="sell",
            urgency="low"
        ),
        Trade(
            ticker="SMALLCAP",
            target_weight=0.02,
            current_weight=0.00,
            trade_size=0.02,
            direction="buy",
            urgency="high"
        )
    ]
    
    # Sample market data
    market_data = {
        "RELIANCE": {"adv": 5000000, "volatility": 0.015},
        "TCS": {"adv": 4000000, "volatility": 0.018},
        "SMALLCAP": {"adv": 500000, "volatility": 0.035}
    }
    
    # Simulate execution
    results = model.simulate_portfolio_rebalance(trades, market_data)
    
    print(f"\n📊 EXECUTION RESULTS")
    print("=" * 60)
    
    for i, (trade, result) in enumerate(zip(trades, results)):
        print(f"\n{i+1}. {trade.ticker}")
        print(f"   Target: {trade.target_weight:.1%} → Achieved: {result.achieved_weight:.1%}")
        print(f"   Fill rate: {result.fill_rate:.1%}")
        print(f"   Slippage: {result.slippage:.2%}")
        print(f"   Market impact: {result.market_impact:.2%}")
        print(f"   Delay: {result.delay_days} days")
        print(f"   Total cost: {result.total_cost:.2%}")
    
    # Record quality
    quality = model.record_execution_quality(datetime.now(), results)
    
    print(f"\n📈 EXECUTION QUALITY")
    print("=" * 60)
    print(f"   Average slippage: {quality.avg_slippage:.2%}")
    print(f"   Average fill rate: {quality.fill_rate:.1%}")
    print(f"   Average delay: {quality.rebalance_delay:.1f} days")
    print(f"   Total cost: {quality.realized_cost:.2%}")
    print(f"   Trade count: {quality.trade_count}")
    
    # Get summary
    summary = model.get_execution_quality_summary()
    print(f"\n📋 SUMMARY")
    print(f"   Days tracked: {summary['days']}")
    print(f"   Total trades: {summary['total_trades']}")
    print(f"   Average slippage: {summary['avg_slippage']:.2%}")
    print(f"   Average fill rate: {summary['avg_fill_rate']:.1%}")
    
    print("\n✅ Execution Realism Model demonstration complete")


if __name__ == "__main__":
    main()