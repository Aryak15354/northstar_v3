#!/usr/bin/env python3
"""
Position Inertia System - Turnover Reduction Engine

This system reduces turnover from 225% to <50% by adding intelligent friction
to position changes. The goal is to stop paying the market for micro-noise.

Key mechanisms:
1. Hysteresis entry/exit bands
2. Signal decay smoothing  
3. Minimum holding periods
4. Capital flow limiters
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

@dataclass
class PositionState:
    """Current position state with inertia tracking"""
    symbol: str
    current_weight: float
    target_weight: float
    entry_date: datetime
    last_trade_date: datetime
    holding_period: int  # days
    entry_threshold_crossed: bool
    exit_threshold_crossed: bool
    locked_until: Optional[datetime] = None

@dataclass
class InertiaConfig:
    """Configuration for position inertia system"""
    # Hysteresis bands
    entry_threshold: float = 0.07      # Enter position at 7% signal
    exit_threshold: float = 0.03       # Exit position at 3% signal
    
    # Signal smoothing
    signal_decay_factor: float = 0.9   # Exponential smoothing
    
    # Holding constraints
    min_holding_days: int = 20         # Minimum 20 trading days
    
    # Flow limits
    max_daily_weight_change: float = 0.03  # Max 3% weight change per day
    
    # Position sizing
    min_position_size: float = 0.01    # Minimum 1% position
    max_position_size: float = 0.05    # Maximum 5% position

class PositionInertiaSystem:
    """
    Intelligent position management with inertia to reduce turnover.
    
    This system prevents the strategy from churning on noise while
    still allowing meaningful position changes when signals are strong.
    """
    
    def __init__(self, config: InertiaConfig = None):
        self.config = config or InertiaConfig()
        self.positions: Dict[str, PositionState] = {}
        self.smoothed_signals: Dict[str, float] = {}
        self.signal_history: Dict[str, List[Tuple[datetime, float]]] = {}
        
        # Tracking metrics
        self.daily_turnover: List[float] = []
        self.trades_blocked: int = 0
        self.trades_executed: int = 0
        
        print(f"🔄 Position Inertia System initialized")
        print(f"   Entry threshold: {self.config.entry_threshold:.1%}")
        print(f"   Exit threshold: {self.config.exit_threshold:.1%}")
        print(f"   Min holding: {self.config.min_holding_days} days")
        print(f"   Max daily change: {self.config.max_daily_weight_change:.1%}")
    
    def update_signals(self, raw_signals: Dict[str, float], current_date: datetime) -> Dict[str, float]:
        """
        Update signals with smoothing and return processed signals.
        
        This applies exponential smoothing to reduce micro-noise.
        """
        
        smoothed_signals = {}
        
        for symbol, raw_signal in raw_signals.items():
            # Initialize if new signal
            if symbol not in self.smoothed_signals:
                self.smoothed_signals[symbol] = raw_signal
                self.signal_history[symbol] = []
            
            # Apply exponential smoothing
            prev_smoothed = self.smoothed_signals[symbol]
            smoothed = (self.config.signal_decay_factor * prev_smoothed + 
                       (1 - self.config.signal_decay_factor) * raw_signal)
            
            self.smoothed_signals[symbol] = smoothed
            smoothed_signals[symbol] = smoothed
            
            # Track signal history
            self.signal_history[symbol].append((current_date, smoothed))
            
            # Keep only recent history (for analysis)
            if len(self.signal_history[symbol]) > 252:  # 1 year
                self.signal_history[symbol] = self.signal_history[symbol][-252:]
        
        return smoothed_signals
    
    def calculate_target_weights(self, 
                               smoothed_signals: Dict[str, float],
                               current_date: datetime) -> Dict[str, float]:
        """
        Calculate target weights with hysteresis bands.
        
        This prevents entering/exiting positions on weak signals.
        """
        
        target_weights = {}
        
        for symbol, signal in smoothed_signals.items():
            current_position = self.positions.get(symbol)
            current_weight = current_position.current_weight if current_position else 0.0
            
            # Apply hysteresis logic
            if current_weight == 0.0:
                # Not in position - check entry threshold
                if abs(signal) >= self.config.entry_threshold:
                    # Strong enough signal to enter
                    target_weight = np.sign(signal) * min(
                        abs(signal), 
                        self.config.max_position_size
                    )
                    target_weight = max(abs(target_weight), self.config.min_position_size) * np.sign(target_weight)
                else:
                    # Signal too weak to enter
                    target_weight = 0.0
            else:
                # In position - check exit threshold
                if abs(signal) <= self.config.exit_threshold:
                    # Signal too weak to maintain position
                    target_weight = 0.0
                elif np.sign(signal) != np.sign(current_weight):
                    # Signal flipped - exit if below entry threshold
                    if abs(signal) >= self.config.entry_threshold:
                        # Strong enough to flip
                        target_weight = np.sign(signal) * min(
                            abs(signal), 
                            self.config.max_position_size
                        )
                        target_weight = max(abs(target_weight), self.config.min_position_size) * np.sign(target_weight)
                    else:
                        # Not strong enough to flip - exit
                        target_weight = 0.0
                else:
                    # Same direction - adjust size
                    target_weight = np.sign(signal) * min(
                        abs(signal), 
                        self.config.max_position_size
                    )
                    target_weight = max(abs(target_weight), self.config.min_position_size) * np.sign(target_weight)
            
            target_weights[symbol] = target_weight
        
        return target_weights
    
    def apply_holding_constraints(self, 
                                target_weights: Dict[str, float],
                                current_date: datetime) -> Dict[str, float]:
        """
        Apply minimum holding period constraints.
        
        This prevents churning by enforcing minimum holding periods.
        """
        
        constrained_weights = target_weights.copy()
        
        for symbol, target_weight in target_weights.items():
            current_position = self.positions.get(symbol)
            
            if current_position is None:
                continue
            
            # Check if position is locked due to minimum holding period
            if current_position.locked_until and current_date < current_position.locked_until:
                # Position is locked - maintain current weight
                constrained_weights[symbol] = current_position.current_weight
                self.trades_blocked += 1
                continue
            
            # Check minimum holding period for exits
            if (current_position.current_weight != 0.0 and 
                target_weight == 0.0 and 
                current_position.holding_period < self.config.min_holding_days):
                
                # Too early to exit - maintain position
                constrained_weights[symbol] = current_position.current_weight
                self.trades_blocked += 1
        
        return constrained_weights
    
    def apply_flow_limits(self, 
                         constrained_weights: Dict[str, float],
                         current_date: datetime) -> Dict[str, float]:
        """
        Apply daily capital flow limits.
        
        This prevents excessive daily turnover.
        """
        
        flow_limited_weights = {}
        
        for symbol, target_weight in constrained_weights.items():
            current_position = self.positions.get(symbol)
            current_weight = current_position.current_weight if current_position else 0.0
            
            # Calculate desired change
            weight_change = target_weight - current_weight
            
            # Apply flow limit
            max_change = self.config.max_daily_weight_change
            
            if abs(weight_change) > max_change:
                # Limit the change
                limited_change = np.sign(weight_change) * max_change
                final_weight = current_weight + limited_change
                
                self.trades_blocked += 1
            else:
                final_weight = target_weight
                
                if abs(weight_change) > 0.001:  # Meaningful change
                    self.trades_executed += 1
            
            flow_limited_weights[symbol] = final_weight
        
        return flow_limited_weights
    
    def update_positions(self, 
                        final_weights: Dict[str, float],
                        current_date: datetime) -> Dict[str, float]:
        """
        Update position states and return actual weights for execution.
        """
        
        actual_weights = {}
        daily_turnover = 0.0
        
        for symbol, final_weight in final_weights.items():
            current_position = self.positions.get(symbol)
            current_weight = current_position.current_weight if current_position else 0.0
            
            # Calculate turnover
            weight_change = abs(final_weight - current_weight)
            daily_turnover += weight_change
            
            # Update or create position
            if symbol in self.positions:
                # Update existing position
                position = self.positions[symbol]
                position.target_weight = final_weight
                
                # If weight changed significantly, update trade date
                if weight_change > 0.001:
                    position.last_trade_date = current_date
                
                # Update holding period
                position.holding_period = (current_date - position.entry_date).days
                
                # Update current weight
                position.current_weight = final_weight
                
                # If exiting position, remove from tracking
                if final_weight == 0.0:
                    del self.positions[symbol]
                
            else:
                # New position
                if final_weight != 0.0:
                    self.positions[symbol] = PositionState(
                        symbol=symbol,
                        current_weight=final_weight,
                        target_weight=final_weight,
                        entry_date=current_date,
                        last_trade_date=current_date,
                        holding_period=0,
                        entry_threshold_crossed=True,
                        exit_threshold_crossed=False,
                        locked_until=current_date + timedelta(days=self.config.min_holding_days)
                    )
            
            actual_weights[symbol] = final_weight
        
        # Track daily turnover
        self.daily_turnover.append(daily_turnover)
        
        return actual_weights
    
    def process_signals(self, 
                       raw_signals: Dict[str, float],
                       current_date: datetime) -> Dict[str, float]:
        """
        Complete signal processing pipeline with inertia.
        
        This is the main entry point that applies all inertia mechanisms.
        """
        
        # Step 1: Smooth signals
        smoothed_signals = self.update_signals(raw_signals, current_date)
        
        # Step 2: Calculate target weights with hysteresis
        target_weights = self.calculate_target_weights(smoothed_signals, current_date)
        
        # Step 3: Apply holding constraints
        constrained_weights = self.apply_holding_constraints(target_weights, current_date)
        
        # Step 4: Apply flow limits
        flow_limited_weights = self.apply_flow_limits(constrained_weights, current_date)
        
        # Step 5: Update positions and return actual weights
        actual_weights = self.update_positions(flow_limited_weights, current_date)
        
        return actual_weights
    
    def get_turnover_metrics(self) -> Dict:
        """Get turnover and efficiency metrics"""
        
        if not self.daily_turnover:
            return {}
        
        # Calculate metrics
        avg_daily_turnover = np.mean(self.daily_turnover)
        annual_turnover = avg_daily_turnover * 252
        
        total_trades = self.trades_executed + self.trades_blocked
        trade_efficiency = self.trades_executed / total_trades if total_trades > 0 else 0
        
        # Recent turnover trend
        recent_turnover = np.mean(self.daily_turnover[-21:]) if len(self.daily_turnover) >= 21 else avg_daily_turnover
        
        return {
            'avg_daily_turnover': avg_daily_turnover,
            'annual_turnover': annual_turnover,
            'recent_daily_turnover': recent_turnover,
            'trades_executed': self.trades_executed,
            'trades_blocked': self.trades_blocked,
            'trade_efficiency': trade_efficiency,
            'active_positions': len(self.positions),
            'avg_holding_period': np.mean([p.holding_period for p in self.positions.values()]) if self.positions else 0
        }
    
    def get_position_report(self) -> Dict:
        """Get detailed position report"""
        
        if not self.positions:
            return {'active_positions': 0}
        
        position_data = []
        for symbol, position in self.positions.items():
            position_data.append({
                'symbol': symbol,
                'weight': position.current_weight,
                'holding_days': position.holding_period,
                'entry_date': position.entry_date.strftime('%Y-%m-%d'),
                'locked_until': position.locked_until.strftime('%Y-%m-%d') if position.locked_until else None
            })
        
        return {
            'active_positions': len(self.positions),
            'total_gross_exposure': sum(abs(p.current_weight) for p in self.positions.values()),
            'total_net_exposure': sum(p.current_weight for p in self.positions.values()),
            'positions': position_data
        }

def main():
    """Test the Position Inertia System"""
    
    print("🧪 TESTING POSITION INERTIA SYSTEM")
    print("=" * 60)
    
    # Initialize system
    config = InertiaConfig(
        entry_threshold=0.05,
        exit_threshold=0.02,
        min_holding_days=10,
        max_daily_weight_change=0.02
    )
    
    inertia_system = PositionInertiaSystem(config)
    
    # Simulate trading over time
    np.random.seed(42)
    n_days = 100
    symbols = ['AAPL', 'GOOGL', 'MSFT', 'TSLA']
    
    print(f"\n📊 Simulating {n_days} days of trading...")
    
    for day in range(n_days):
        current_date = datetime(2024, 1, 1) + timedelta(days=day)
        
        # Generate noisy signals
        raw_signals = {}
        for symbol in symbols:
            # Base signal with noise
            base_signal = 0.03 * np.sin(day / 20) + np.random.normal(0, 0.02)
            raw_signals[symbol] = base_signal
        
        # Process through inertia system
        actual_weights = inertia_system.process_signals(raw_signals, current_date)
        
        # Print progress every 20 days
        if day % 20 == 0:
            print(f"   Day {day}: {len(actual_weights)} positions, "
                  f"turnover: {inertia_system.daily_turnover[-1]:.3f}")
    
    # Generate reports
    print(f"\n📈 TURNOVER METRICS")
    print("=" * 40)
    
    turnover_metrics = inertia_system.get_turnover_metrics()
    for metric, value in turnover_metrics.items():
        if isinstance(value, float):
            if 'turnover' in metric:
                print(f"{metric}: {value:.1%}")
            else:
                print(f"{metric}: {value:.2f}")
        else:
            print(f"{metric}: {value}")
    
    print(f"\n📋 POSITION REPORT")
    print("=" * 40)
    
    position_report = inertia_system.get_position_report()
    print(f"Active positions: {position_report['active_positions']}")
    if 'total_gross_exposure' in position_report:
        print(f"Total gross exposure: {position_report['total_gross_exposure']:.1%}")
        print(f"Total net exposure: {position_report['total_net_exposure']:.1%}")

if __name__ == "__main__":
    main()