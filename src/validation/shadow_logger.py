#!/usr/bin/env python3
"""
📋 SHADOW LOGGER - LAYER 4: LIVE REALITY
Complete daily audit trail of shadow portfolio for institutional validation

This implements the core logging requirements for Layer 4 (Live Reality) of the
institutional validation framework. It provides complete transparency and
auditability for shadow fund operations.

CRITICAL PRINCIPLE: Complete Audit Trail
- Log daily positions with full attribution
- Log daily P&L with complete breakdown
- Log daily decisions with human-readable explanations
- All logs timestamped and immutable for compliance

Usage:
    from src.validation.shadow_logger import ShadowLogger
    
    logger = ShadowLogger()
    logger.log_daily_positions(positions_data)
    logger.log_daily_pnl(pnl_data)
    logger.log_daily_decisions(decisions_data)
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import warnings

warnings.filterwarnings('ignore')


@dataclass
class DailyPosition:
    """
    Daily position record for shadow portfolio
    
    Complete position information with attribution and risk metrics.
    """
    date: datetime
    ticker: str
    weight: float  # Portfolio weight (0.0 to 1.0)
    role: str  # Position role (core, satellite, hedge, cash)
    strategy_source: str  # Strategy that generated this position
    exposure: float  # Absolute exposure (>= 0.0)
    risk_cap: float  # Risk limit for this position
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return asdict(self)
    
    def validate(self) -> List[str]:
        """Validate position data"""
        errors = []
        
        if not (-1.0 <= self.weight <= 1.0):
            errors.append(f"Weight {self.weight} outside bounds [-1.0, 1.0]")
        
        if self.exposure < 0.0:
            errors.append(f"Exposure {self.exposure} is negative")
        
        if not (0.0 <= self.risk_cap <= 1.0):
            errors.append(f"Risk cap {self.risk_cap} outside bounds [0.0, 1.0]")
        
        if self.role not in ['core', 'satellite', 'hedge', 'cash']:
            errors.append(f"Invalid role: {self.role}")
        
        return errors


@dataclass
class DailyPnL:
    """
    Daily P&L record for shadow portfolio
    
    Complete performance breakdown with costs and attribution.
    """
    date: datetime
    returns: float  # Daily return
    tracking_error: float  # Tracking error vs benchmark
    drawdown: float  # Current drawdown from peak
    turnover: float  # Daily turnover
    costs: float  # Transaction costs
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return asdict(self)
    
    def validate(self) -> List[str]:
        """Validate P&L data"""
        errors = []
        
        if self.drawdown > 0.0:
            errors.append(f"Drawdown {self.drawdown} is positive (should be <= 0.0)")
        
        if self.turnover < 0.0:
            errors.append(f"Turnover {self.turnover} is negative")
        
        if self.costs < 0.0:
            errors.append(f"Costs {self.costs} are negative")
        
        return errors


@dataclass
class DailyDecision:
    """
    Daily decision record for shadow portfolio
    
    Human-readable explanation of allocation decisions and reasoning.
    """
    date: datetime
    regime: str  # Current market regime
    tailwind_shift: float  # Change in strategy tailwinds
    exposure_change: float  # Change in total exposure (%)
    risk_reason: str  # Primary risk consideration
    strategies_boosted: List[str]  # Strategies that increased allocation
    strategies_cut: List[str]  # Strategies that decreased allocation
    emergency_triggered: bool  # Whether emergency controls activated
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return asdict(self)
    
    def validate(self) -> List[str]:
        """Validate decision data"""
        errors = []
        
        if not (-100.0 <= self.exposure_change <= 100.0):
            errors.append(f"Exposure change {self.exposure_change} outside reasonable bounds")
        
        if not (-1.0 <= self.tailwind_shift <= 1.0):
            errors.append(f"Tailwind shift {self.tailwind_shift} outside reasonable bounds")
        
        if not isinstance(self.strategies_boosted, list):
            errors.append("Strategies boosted must be a list")
        
        if not isinstance(self.strategies_cut, list):
            errors.append("Strategies cut must be a list")
        
        return errors


class ShadowLogger:
    """
    Shadow Logger - Layer 4: Live Reality
    
    Provides complete daily audit trail of shadow portfolio operations
    for institutional validation and compliance.
    
    ENFORCES REQUIREMENTS:
    - 11.1-11.6: Daily shadow portfolio logging
    - 6.1-6.4: Shadow fund operation tracking
    
    V3 INTEGRATION:
    - Uses UnifiedState for state storage (Requirement 14.1)
    - Emits events through EventBus (Requirement 14.2)
    - Integrates with Market_Clock for daily updates (Requirement 14.4)
    """
    
    def __init__(self, 
                 base_dir: str = "data/live_shadow",
                 unified_state=None,
                 event_bus=None,
                 market_clock=None):
        """
        Initialize Shadow Logger
        
        Args:
            base_dir: Base directory for shadow logs
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
        
        # Current year directory
        current_year = datetime.now().year
        self.year_dir = os.path.join(base_dir, str(current_year))
        os.makedirs(self.year_dir, exist_ok=True)
        
        print("📋 Shadow Logger initialized")
        print(f"   Output: {self.year_dir}/")
        if unified_state:
            print("   ✅ V3 Integration: UnifiedState connected")
        if event_bus:
            print("   ✅ V3 Integration: EventBus connected")
        if market_clock:
            print("   ✅ V3 Integration: Market_Clock connected")
    
    def _get_daily_file_path(self, date: datetime, file_type: str) -> str:
        """
        Get file path for daily log file
        
        Args:
            date: Date for the log
            file_type: Type of log (positions, pnl, decisions)
            
        Returns:
            Full file path
        """
        date_str = date.strftime("%Y%m%d")
        
        if file_type == "positions":
            filename = f"daily_positions_{date_str}.parquet"
        elif file_type == "pnl":
            filename = f"daily_pnl_{date_str}.parquet"
        elif file_type == "decisions":
            filename = f"daily_decisions_{date_str}.json"
        else:
            raise ValueError(f"Invalid file type: {file_type}")
        
        # Ensure year directory exists
        year = date.year
        year_dir = os.path.join(self.base_dir, str(year))
        os.makedirs(year_dir, exist_ok=True)
        
        return os.path.join(year_dir, filename)
    
    def log_daily_positions(self, 
                           date: datetime,
                           positions: List[Dict[str, Any]]) -> str:
        """
        Log daily positions to parquet file
        
        ENFORCES PROPERTY 19: Shadow Fund Logging Completeness
        VALIDATES REQUIREMENTS 11.1, 11.2
        
        Args:
            date: Date for the positions
            positions: List of position dictionaries
            
        Returns:
            Path to saved file
        """
        
        # Convert to DailyPosition objects and validate
        position_objects = []
        validation_errors = []
        
        for pos_data in positions:
            try:
                # Ensure date is set
                pos_data['date'] = date
                
                # Create DailyPosition object
                position = DailyPosition(**pos_data)
                
                # Validate
                errors = position.validate()
                if errors:
                    validation_errors.extend([f"{position.ticker}: {error}" for error in errors])
                else:
                    position_objects.append(position)
                    
            except Exception as e:
                validation_errors.append(f"Position validation error: {e}")
        
        if validation_errors:
            print(f"⚠️ Position validation warnings for {date.date()}:")
            for error in validation_errors[:5]:  # Show first 5 errors
                print(f"   {error}")
            if len(validation_errors) > 5:
                print(f"   ... and {len(validation_errors) - 5} more")
        
        # Convert to DataFrame
        if position_objects:
            positions_data = [pos.to_dict() for pos in position_objects]
            positions_df = pd.DataFrame(positions_data)
            
            # Enforce schema
            positions_df = self._enforce_positions_schema(positions_df)
            
            # Save to parquet
            file_path = self._get_daily_file_path(date, "positions")
            positions_df.to_parquet(file_path, index=False)
            
            print(f"✅ Logged {len(positions_df)} positions for {date.date()}")
            
            # V3 Integration: Store in UnifiedState
            self._store_positions_in_unified_state(date, positions_df)
            
            # V3 Integration: Emit event
            self._emit_positions_event(date, positions_df)
            
            return file_path
        else:
            print(f"⚠️ No valid positions to log for {date.date()}")
            return ""
    
    def log_daily_pnl(self, 
                     date: datetime,
                     pnl_data: Dict[str, Any]) -> str:
        """
        Log daily P&L to parquet file
        
        ENFORCES PROPERTY 19: Shadow Fund Logging Completeness
        VALIDATES REQUIREMENTS 11.3
        
        Args:
            date: Date for the P&L
            pnl_data: P&L data dictionary
            
        Returns:
            Path to saved file
        """
        
        try:
            # Ensure date is set
            pnl_data['date'] = date
            
            # Create DailyPnL object
            pnl = DailyPnL(**pnl_data)
            
            # Validate
            validation_errors = pnl.validate()
            if validation_errors:
                print(f"⚠️ P&L validation warnings for {date.date()}:")
                for error in validation_errors:
                    print(f"   {error}")
            
            # Convert to DataFrame
            pnl_df = pd.DataFrame([pnl.to_dict()])
            
            # Enforce schema
            pnl_df = self._enforce_pnl_schema(pnl_df)
            
            # Save to parquet
            file_path = self._get_daily_file_path(date, "pnl")
            pnl_df.to_parquet(file_path, index=False)
            
            print(f"✅ Logged P&L for {date.date()}: {pnl.returns:+.2%} return")
            
            # V3 Integration: Store in UnifiedState
            self._store_pnl_in_unified_state(date, pnl)
            
            # V3 Integration: Emit event
            self._emit_pnl_event(date, pnl)
            
            return file_path
            
        except Exception as e:
            print(f"❌ Failed to log P&L for {date.date()}: {e}")
            return ""
    
    def log_daily_decisions(self, 
                           date: datetime,
                           decision_data: Dict[str, Any]) -> str:
        """
        Log daily decisions to JSON file
        
        ENFORCES PROPERTY 19: Shadow Fund Logging Completeness
        VALIDATES REQUIREMENTS 11.4, 11.5
        
        Args:
            date: Date for the decisions
            decision_data: Decision data dictionary
            
        Returns:
            Path to saved file
        """
        
        try:
            # Ensure date is set
            decision_data['date'] = date
            
            # Create DailyDecision object
            decision = DailyDecision(**decision_data)
            
            # Validate
            validation_errors = decision.validate()
            if validation_errors:
                print(f"⚠️ Decision validation warnings for {date.date()}:")
                for error in validation_errors:
                    print(f"   {error}")
            
            # Convert to dictionary with proper serialization
            decision_dict = decision.to_dict()
            decision_dict['date'] = decision_dict['date'].isoformat()
            
            # Save to JSON
            file_path = self._get_daily_file_path(date, "decisions")
            with open(file_path, 'w') as f:
                json.dump(decision_dict, f, indent=2, default=str)
            
            print(f"✅ Logged decisions for {date.date()}: {decision.regime} regime")
            
            # V3 Integration: Store in UnifiedState
            self._store_decisions_in_unified_state(date, decision)
            
            # V3 Integration: Emit event
            self._emit_decisions_event(date, decision)
            
            return file_path
            
        except Exception as e:
            print(f"❌ Failed to log decisions for {date.date()}: {e}")
            return ""
    
    def log_complete_daily_cycle(self,
                                date: datetime,
                                positions: List[Dict[str, Any]],
                                pnl_data: Dict[str, Any],
                                decision_data: Dict[str, Any]) -> Dict[str, str]:
        """
        Log complete daily cycle (positions + P&L + decisions)
        
        ENFORCES PROPERTY 19: Shadow Fund Logging Completeness
        VALIDATES REQUIREMENTS 11.1-11.6
        
        Args:
            date: Date for the logs
            positions: List of position dictionaries
            pnl_data: P&L data dictionary
            decision_data: Decision data dictionary
            
        Returns:
            Dictionary mapping log types to file paths
        """
        
        print(f"📋 Logging complete daily cycle for {date.date()}")
        
        file_paths = {}
        
        # Log positions
        positions_path = self.log_daily_positions(date, positions)
        if positions_path:
            file_paths['positions'] = positions_path
        
        # Log P&L
        pnl_path = self.log_daily_pnl(date, pnl_data)
        if pnl_path:
            file_paths['pnl'] = pnl_path
        
        # Log decisions
        decisions_path = self.log_daily_decisions(date, decision_data)
        if decisions_path:
            file_paths['decisions'] = decisions_path
        
        # Emit completion event
        if self.event_bus:
            self.event_bus.emit(
                event_type="DAILY_LOGGING_COMPLETE",
                source="shadow_logger",
                data={
                    "date": date.isoformat(),
                    "files_created": len(file_paths),
                    "positions_count": len(positions),
                    "daily_return": pnl_data.get('returns', 0.0),
                    "regime": decision_data.get('regime', 'unknown')
                },
                tags=["shadow", "logging", "daily"],
                priority="INFO"
            )
        
        print(f"✅ Daily logging complete: {len(file_paths)} files created")
        
        return file_paths
    
    def _enforce_positions_schema(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Enforce positions schema
        
        ENFORCES PROPERTY 3: Schema Completeness
        
        Args:
            df: DataFrame to validate
            
        Returns:
            DataFrame with enforced schema
        """
        
        # Required columns with types
        required_schema = {
            'date': 'datetime64[ns]',
            'ticker': 'string',
            'weight': 'float64',
            'role': 'string',
            'strategy_source': 'string',
            'exposure': 'float64',
            'risk_cap': 'float64'
        }
        
        # Ensure all required columns exist
        for col in required_schema.keys():
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        # Enforce types
        for col, dtype in required_schema.items():
            if col == 'date':
                df[col] = pd.to_datetime(df[col])
            elif dtype == 'string':
                df[col] = df[col].astype(str)
            else:
                df[col] = df[col].astype(dtype)
        
        # Validate bounds
        if not ((df['weight'] >= -1.0) & (df['weight'] <= 1.0)).all():
            raise ValueError("Weight must be between -1.0 and 1.0")
        
        if not (df['exposure'] >= 0.0).all():
            raise ValueError("Exposure must be non-negative")
        
        if not ((df['risk_cap'] >= 0.0) & (df['risk_cap'] <= 1.0)).all():
            raise ValueError("Risk cap must be between 0.0 and 1.0")
        
        return df
    
    def _enforce_pnl_schema(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Enforce P&L schema
        
        Args:
            df: DataFrame to validate
            
        Returns:
            DataFrame with enforced schema
        """
        
        # Required columns with types
        required_schema = {
            'date': 'datetime64[ns]',
            'returns': 'float64',
            'tracking_error': 'float64',
            'drawdown': 'float64',
            'turnover': 'float64',
            'costs': 'float64'
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
        if not (df['drawdown'] <= 0.0).all():
            raise ValueError("Drawdown must be non-positive")
        
        if not (df['turnover'] >= 0.0).all():
            raise ValueError("Turnover must be non-negative")
        
        if not (df['costs'] >= 0.0).all():
            raise ValueError("Costs must be non-negative")
        
        return df
    
    def load_daily_positions(self, date: datetime) -> Optional[pd.DataFrame]:
        """
        Load daily positions from file
        
        Args:
            date: Date to load
            
        Returns:
            DataFrame with positions or None if not found
        """
        
        file_path = self._get_daily_file_path(date, "positions")
        
        if not os.path.exists(file_path):
            return None
        
        try:
            df = pd.read_parquet(file_path)
            return self._enforce_positions_schema(df)
        except Exception as e:
            print(f"❌ Failed to load positions for {date.date()}: {e}")
            return None
    
    def load_daily_pnl(self, date: datetime) -> Optional[pd.DataFrame]:
        """
        Load daily P&L from file
        
        Args:
            date: Date to load
            
        Returns:
            DataFrame with P&L or None if not found
        """
        
        file_path = self._get_daily_file_path(date, "pnl")
        
        if not os.path.exists(file_path):
            return None
        
        try:
            df = pd.read_parquet(file_path)
            return self._enforce_pnl_schema(df)
        except Exception as e:
            print(f"❌ Failed to load P&L for {date.date()}: {e}")
            return None
    
    def load_daily_decisions(self, date: datetime) -> Optional[Dict]:
        """
        Load daily decisions from file
        
        Args:
            date: Date to load
            
        Returns:
            Dictionary with decisions or None if not found
        """
        
        file_path = self._get_daily_file_path(date, "decisions")
        
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Failed to load decisions for {date.date()}: {e}")
            return None
    
    def get_date_range_summary(self, 
                              start_date: datetime, 
                              end_date: datetime) -> Dict[str, Any]:
        """
        Get summary statistics for a date range
        
        Args:
            start_date: Start date
            end_date: End date
            
        Returns:
            Dictionary with summary statistics
        """
        
        summary = {
            'start_date': start_date.date(),
            'end_date': end_date.date(),
            'total_days': (end_date - start_date).days + 1,
            'days_logged': 0,
            'total_positions': 0,
            'avg_daily_return': 0.0,
            'total_return': 1.0,
            'max_drawdown': 0.0,
            'avg_turnover': 0.0,
            'total_costs': 0.0,
            'regime_distribution': {},
            'strategy_usage': {}
        }
        
        current_date = start_date
        daily_returns = []
        daily_turnovers = []
        daily_costs = []
        peak_value = 1.0
        
        while current_date <= end_date:
            # Load P&L
            pnl_df = self.load_daily_pnl(current_date)
            if pnl_df is not None and not pnl_df.empty:
                summary['days_logged'] += 1
                
                daily_return = pnl_df['returns'].iloc[0]
                daily_returns.append(daily_return)
                
                # Update cumulative return
                summary['total_return'] *= (1 + daily_return)
                
                # Update drawdown
                peak_value = max(peak_value, summary['total_return'])
                current_drawdown = (summary['total_return'] - peak_value) / peak_value
                summary['max_drawdown'] = min(summary['max_drawdown'], current_drawdown)
                
                # Track turnover and costs
                daily_turnovers.append(pnl_df['turnover'].iloc[0])
                daily_costs.append(pnl_df['costs'].iloc[0])
            
            # Load positions
            positions_df = self.load_daily_positions(current_date)
            if positions_df is not None and not positions_df.empty:
                summary['total_positions'] += len(positions_df)
                
                # Track strategy usage
                for strategy in positions_df['strategy_source'].unique():
                    summary['strategy_usage'][strategy] = summary['strategy_usage'].get(strategy, 0) + 1
            
            # Load decisions
            decisions = self.load_daily_decisions(current_date)
            if decisions:
                regime = decisions.get('regime', 'unknown')
                summary['regime_distribution'][regime] = summary['regime_distribution'].get(regime, 0) + 1
            
            current_date += timedelta(days=1)
        
        # Calculate averages
        if daily_returns:
            summary['avg_daily_return'] = np.mean(daily_returns)
        
        if daily_turnovers:
            summary['avg_turnover'] = np.mean(daily_turnovers)
        
        if daily_costs:
            summary['total_costs'] = np.sum(daily_costs)
        
        # Convert total return to percentage
        summary['total_return'] = summary['total_return'] - 1.0
        
        return summary
    
    # ========================================================================
    # V3 INTEGRATION METHODS
    # ========================================================================
    
    def _store_positions_in_unified_state(self, date: datetime, positions_df: pd.DataFrame):
        """Store positions in UnifiedState"""
        
        if self.unified_state is None:
            return
        
        try:
            component_name = "shadow_logger"
            
            # Store latest positions
            self.unified_state.set(
                component=component_name,
                key="latest_positions",
                value={
                    "date": date.isoformat(),
                    "count": len(positions_df),
                    "total_exposure": positions_df['exposure'].sum(),
                    "strategies": positions_df['strategy_source'].unique().tolist()
                }
            )
            
        except Exception as e:
            print(f"⚠️ Failed to store positions in UnifiedState: {e}")
    
    def _store_pnl_in_unified_state(self, date: datetime, pnl: DailyPnL):
        """Store P&L in UnifiedState"""
        
        if self.unified_state is None:
            return
        
        try:
            component_name = "shadow_logger"
            
            # Store latest P&L
            self.unified_state.set(
                component=component_name,
                key="latest_pnl",
                value={
                    "date": date.isoformat(),
                    "returns": pnl.returns,
                    "drawdown": pnl.drawdown,
                    "costs": pnl.costs
                }
            )
            
        except Exception as e:
            print(f"⚠️ Failed to store P&L in UnifiedState: {e}")
    
    def _store_decisions_in_unified_state(self, date: datetime, decision: DailyDecision):
        """Store decisions in UnifiedState"""
        
        if self.unified_state is None:
            return
        
        try:
            component_name = "shadow_logger"
            
            # Store latest decisions
            self.unified_state.set(
                component=component_name,
                key="latest_decisions",
                value={
                    "date": date.isoformat(),
                    "regime": decision.regime,
                    "exposure_change": decision.exposure_change,
                    "emergency_triggered": decision.emergency_triggered
                }
            )
            
        except Exception as e:
            print(f"⚠️ Failed to store decisions in UnifiedState: {e}")
    
    def _emit_positions_event(self, date: datetime, positions_df: pd.DataFrame):
        """Emit positions event through EventBus"""
        
        if self.event_bus is None:
            return
        
        try:
            self.event_bus.emit(
                event_type="SHADOW_POSITIONS_LOGGED",
                source="shadow_logger",
                data={
                    "date": date.isoformat(),
                    "position_count": len(positions_df),
                    "total_exposure": positions_df['exposure'].sum(),
                    "strategies": positions_df['strategy_source'].unique().tolist()
                },
                tags=["shadow", "positions", "logging"]
            )
            
        except Exception as e:
            print(f"⚠️ Failed to emit positions event: {e}")
    
    def _emit_pnl_event(self, date: datetime, pnl: DailyPnL):
        """Emit P&L event through EventBus"""
        
        if self.event_bus is None:
            return
        
        try:
            self.event_bus.emit(
                event_type="SHADOW_PNL_LOGGED",
                source="shadow_logger",
                data={
                    "date": date.isoformat(),
                    "returns": pnl.returns,
                    "drawdown": pnl.drawdown,
                    "costs": pnl.costs,
                    "turnover": pnl.turnover
                },
                tags=["shadow", "pnl", "logging"]
            )
            
            # Emit alert if significant drawdown
            if pnl.drawdown < -0.05:  # More than 5% drawdown
                self.event_bus.emit(
                    event_type="SHADOW_DRAWDOWN_ALERT",
                    source="shadow_logger",
                    data={
                        "date": date.isoformat(),
                        "drawdown": pnl.drawdown,
                        "threshold": -0.05
                    },
                    tags=["shadow", "drawdown", "alert"],
                    priority="HIGH"
                )
            
        except Exception as e:
            print(f"⚠️ Failed to emit P&L event: {e}")
    
    def _emit_decisions_event(self, date: datetime, decision: DailyDecision):
        """Emit decisions event through EventBus"""
        
        if self.event_bus is None:
            return
        
        try:
            self.event_bus.emit(
                event_type="SHADOW_DECISIONS_LOGGED",
                source="shadow_logger",
                data={
                    "date": date.isoformat(),
                    "regime": decision.regime,
                    "exposure_change": decision.exposure_change,
                    "emergency_triggered": decision.emergency_triggered,
                    "strategies_boosted": decision.strategies_boosted,
                    "strategies_cut": decision.strategies_cut
                },
                tags=["shadow", "decisions", "logging"]
            )
            
            # Emit alert if emergency triggered
            if decision.emergency_triggered:
                self.event_bus.emit(
                    event_type="SHADOW_EMERGENCY_ALERT",
                    source="shadow_logger",
                    data={
                        "date": date.isoformat(),
                        "regime": decision.regime,
                        "risk_reason": decision.risk_reason
                    },
                    tags=["shadow", "emergency", "alert"],
                    priority="CRITICAL"
                )
            
        except Exception as e:
            print(f"⚠️ Failed to emit decisions event: {e}")


def main():
    """Demonstrate Shadow Logger"""
    
    print("📋 SHADOW LOGGER - DEMONSTRATION")
    print("=" * 60)
    
    # Initialize logger
    logger = ShadowLogger(base_dir="data/test_shadow")
    
    # Simulate 5 days of shadow fund operation
    np.random.seed(42)
    
    for day in range(5):
        date = datetime(2024, 1, 1) + timedelta(days=day)
        
        # Mock positions
        positions = [
            {
                'ticker': 'RELIANCE',
                'weight': 0.05,
                'role': 'core',
                'strategy_source': 'value_momentum',
                'exposure': 0.05,
                'risk_cap': 0.10
            },
            {
                'ticker': 'TCS',
                'weight': 0.04,
                'role': 'core',
                'strategy_source': 'quality_growth',
                'exposure': 0.04,
                'risk_cap': 0.08
            },
            {
                'ticker': 'HDFCBANK',
                'weight': 0.06,
                'role': 'satellite',
                'strategy_source': 'banking_momentum',
                'exposure': 0.06,
                'risk_cap': 0.12
            }
        ]
        
        # Mock P&L
        pnl_data = {
            'returns': np.random.normal(0.001, 0.02),  # 0.1% mean, 2% std
            'tracking_error': np.random.uniform(0.005, 0.015),
            'drawdown': min(0.0, np.random.normal(-0.01, 0.02)),
            'turnover': np.random.uniform(0.01, 0.05),
            'costs': np.random.uniform(0.0001, 0.001)
        }
        
        # Mock decisions
        decision_data = {
            'regime': np.random.choice(['expansion', 'late-expansion', 'recession']),
            'tailwind_shift': np.random.normal(0.0, 0.05),
            'exposure_change': np.random.normal(0.0, 5.0),
            'risk_reason': np.random.choice(['normal', 'volatility rising', 'liquidity stress']),
            'strategies_boosted': ['value_momentum'] if np.random.random() > 0.5 else [],
            'strategies_cut': ['banking_momentum'] if np.random.random() > 0.7 else [],
            'emergency_triggered': np.random.random() < 0.1
        }
        
        # Log complete daily cycle
        file_paths = logger.log_complete_daily_cycle(
            date=date,
            positions=positions,
            pnl_data=pnl_data,
            decision_data=decision_data
        )
        
        print(f"\n📅 {date.date()}")
        print(f"   Return: {pnl_data['returns']:+.2%}")
        print(f"   Regime: {decision_data['regime']}")
        print(f"   Files: {len(file_paths)}")
    
    # Get summary
    print("\n📊 SUMMARY STATISTICS")
    print("=" * 60)
    
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 1, 5)
    
    summary = logger.get_date_range_summary(start_date, end_date)
    
    print(f"   Days logged: {summary['days_logged']}/{summary['total_days']}")
    print(f"   Total return: {summary['total_return']:+.2%}")
    print(f"   Max drawdown: {summary['max_drawdown']:+.2%}")
    print(f"   Avg turnover: {summary['avg_turnover']:.2%}")
    print(f"   Total costs: {summary['total_costs']:.4%}")
    print(f"   Regime distribution: {summary['regime_distribution']}")
    
    print("\n✅ Shadow Logger demonstration complete")


if __name__ == "__main__":
    main()