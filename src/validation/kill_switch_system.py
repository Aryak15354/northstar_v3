#!/usr/bin/env python3
"""
🚨 KILL SWITCH SYSTEM - INSTITUTIONAL VALIDATION LAYER 2
Automatic risk brakes with institutional-grade thresholds

This is the enhanced kill switch system for institutional validation.
It provides automatic risk protection with clear, testable rules.

Key Features:
- Drawdown brake: >20% drawdown → 50% exposure
- Daily loss brake: >5% daily loss → 25% exposure  
- Volatility brake: >30% realized vol → 60% cap
- Complete audit trail in risk_state.parquet
- Integration with Risk_Coordinator

Usage:
    from src.validation.kill_switch_system import KillSwitchSystem
    
    kill_switches = KillSwitchSystem()
    risk_state = kill_switches.evaluate_and_apply()
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, asdict
import warnings
warnings.filterwarnings('ignore')


@dataclass
class RiskState:
    """Risk state data model for kill switch system"""
    date: datetime
    portfolio_value: float
    drawdown: float
    daily_return: float
    realized_vol: float
    risk_level: float  # 0.0 to 1.0
    emergency_active: bool
    exposure_cap: float
    kill_switch_triggered: Optional[str] = None
    kill_switch_reason: Optional[str] = None


class KillSwitchSystem:
    """
    Kill Switch System - Institutional Validation Layer 2
    
    Implements three automatic risk brakes:
    1. Drawdown Brake: Reduces exposure when drawdown exceeds threshold
    2. Daily Loss Brake: Reduces exposure after large single-day losses
    3. Volatility Brake: Caps exposure during high volatility periods
    
    All activations are logged to data/risk/risk_state.parquet for audit trail.
    """
    
    def __init__(self, 
                 max_drawdown: float = 0.20,
                 max_daily_loss: float = 0.05,
                 max_volatility: float = 0.30,
                 vol_lookback: int = 30):
        """
        Initialize kill switch system with institutional thresholds
        
        Args:
            max_drawdown: Maximum drawdown before brake activates (default 20%)
            max_daily_loss: Maximum daily loss before brake activates (default 5%)
            max_volatility: Maximum realized volatility before brake activates (default 30%)
            vol_lookback: Days for volatility calculation (default 30)
        """
        self.max_drawdown = max_drawdown
        self.max_daily_loss = max_daily_loss
        self.max_volatility = max_volatility
        self.vol_lookback = vol_lookback
        
        # Exposure reduction rules
        self.drawdown_exposure_reduction = 0.50  # 50% of current exposure
        self.daily_loss_exposure_reduction = 0.25  # 25% of current exposure
        self.volatility_exposure_cap = 0.60  # 60% maximum exposure
        
        # File paths
        self.risk_state_file = 'data/risk/risk_state.parquet'
        self.performance_file = 'data/processed/performance_summary.parquet'
        
        # Ensure directory exists
        os.makedirs('data/risk', exist_ok=True)
    
    def load_performance_data(self) -> Optional[pd.DataFrame]:
        """Load performance data for kill switch evaluation"""
        try:
            if os.path.exists(self.performance_file):
                df = pd.read_parquet(self.performance_file)
                if not df.empty:
                    # Ensure date column is datetime
                    if 'date' in df.columns:
                        df['date'] = pd.to_datetime(df['date'])
                        df = df.sort_values('date')
                    return df
        except Exception as e:
            print(f"⚠️ Error loading performance data: {e}")
        
        return None
    
    def calculate_realized_volatility(self, returns: pd.Series) -> float:
        """
        Calculate realized volatility (annualized)
        
        Args:
            returns: Series of daily returns
            
        Returns:
            Annualized volatility
        """
        if len(returns) < 2:
            return 0.0
        
        # Use last N days for volatility calculation
        recent_returns = returns.tail(self.vol_lookback)
        
        if len(recent_returns) < 2:
            return 0.0
        
        # Annualize daily volatility
        daily_vol = recent_returns.std()
        annual_vol = daily_vol * np.sqrt(252)
        
        return annual_vol
    
    def calculate_drawdown(self, equity_curve: pd.Series) -> float:
        """
        Calculate current drawdown from peak
        
        Args:
            equity_curve: Series of portfolio values
            
        Returns:
            Current drawdown (negative value)
        """
        if len(equity_curve) == 0:
            return 0.0
        
        # Calculate running maximum
        running_max = equity_curve.expanding().max()
        
        # Calculate drawdown
        current_value = equity_curve.iloc[-1]
        peak_value = running_max.iloc[-1]
        
        if peak_value > 0:
            drawdown = (current_value / peak_value) - 1.0
        else:
            drawdown = 0.0
        
        return drawdown
    
    def evaluate_drawdown_brake(self, 
                                 drawdown: float, 
                                 current_exposure: float) -> Tuple[bool, float, str]:
        """
        Evaluate drawdown brake
        
        Rule: If drawdown > 20%, reduce exposure to 50% of current level
        
        Args:
            drawdown: Current drawdown (negative value)
            current_exposure: Current portfolio exposure
            
        Returns:
            (triggered, new_exposure_cap, reason)
        """
        if abs(drawdown) > self.max_drawdown:
            new_cap = current_exposure * self.drawdown_exposure_reduction
            reason = f"Drawdown {abs(drawdown):.1%} exceeds {self.max_drawdown:.1%} threshold"
            return True, new_cap, reason
        
        return False, current_exposure, ""
    
    def evaluate_daily_loss_brake(self, 
                                   daily_return: float, 
                                   current_exposure: float) -> Tuple[bool, float, str]:
        """
        Evaluate daily loss brake
        
        Rule: If daily loss > 5%, reduce exposure to 25% of current level
        
        Args:
            daily_return: Today's return
            current_exposure: Current portfolio exposure
            
        Returns:
            (triggered, new_exposure_cap, reason)
        """
        if daily_return < -self.max_daily_loss:
            new_cap = current_exposure * self.daily_loss_exposure_reduction
            reason = f"Daily loss {abs(daily_return):.1%} exceeds {self.max_daily_loss:.1%} threshold"
            return True, new_cap, reason
        
        return False, current_exposure, ""
    
    def evaluate_volatility_brake(self, 
                                   realized_vol: float, 
                                   current_exposure: float) -> Tuple[bool, float, str]:
        """
        Evaluate volatility brake
        
        Rule: If realized vol > 30%, cap exposure at 60%
        
        Args:
            realized_vol: Realized volatility (annualized)
            current_exposure: Current portfolio exposure
            
        Returns:
            (triggered, new_exposure_cap, reason)
        """
        if realized_vol > self.max_volatility:
            new_cap = min(current_exposure, self.volatility_exposure_cap)
            reason = f"Realized volatility {realized_vol:.1%} exceeds {self.max_volatility:.1%} threshold"
            return True, new_cap, reason
        
        return False, current_exposure, ""
    
    def calculate_risk_level(self, 
                             drawdown: float, 
                             daily_return: float, 
                             realized_vol: float) -> float:
        """
        Calculate overall risk level (0.0 to 1.0)
        
        Risk level is a weighted combination of:
        - Drawdown severity (40%)
        - Daily loss severity (30%)
        - Volatility severity (30%)
        
        Args:
            drawdown: Current drawdown
            daily_return: Today's return
            realized_vol: Realized volatility
            
        Returns:
            Risk level between 0.0 (safe) and 1.0 (maximum risk)
        """
        # Drawdown component (0 to 1)
        dd_component = min(abs(drawdown) / self.max_drawdown, 1.0)
        
        # Daily loss component (0 to 1)
        loss_component = min(abs(min(daily_return, 0)) / self.max_daily_loss, 1.0)
        
        # Volatility component (0 to 1)
        vol_component = min(realized_vol / self.max_volatility, 1.0)
        
        # Weighted combination
        risk_level = (
            0.40 * dd_component +
            0.30 * loss_component +
            0.30 * vol_component
        )
        
        return risk_level
    
    def evaluate_kill_switches(self, 
                                performance_df: pd.DataFrame) -> RiskState:
        """
        Evaluate all kill switches and determine risk state
        
        Args:
            performance_df: Performance data with returns and equity
            
        Returns:
            RiskState object with current risk assessment
        """
        if performance_df.empty:
            # Return safe default state
            return RiskState(
                date=datetime.now(),
                portfolio_value=1.0,
                drawdown=0.0,
                daily_return=0.0,
                realized_vol=0.0,
                risk_level=0.0,
                emergency_active=False,
                exposure_cap=1.0
            )
        
        # Get latest data
        latest = performance_df.iloc[-1]
        date = latest['date'] if 'date' in latest else datetime.now()
        
        # Calculate metrics
        if 'net_return' in performance_df.columns:
            returns = performance_df['net_return']
        elif 'northstar_return' in performance_df.columns:
            returns = performance_df['northstar_return']
        else:
            returns = pd.Series([0.0])
        
        daily_return = returns.iloc[-1] if len(returns) > 0 else 0.0
        
        # Calculate equity curve (cumulative returns)
        equity_curve = (1 + returns).cumprod()
        portfolio_value = equity_curve.iloc[-1] if len(equity_curve) > 0 else 1.0
        
        # Calculate drawdown
        drawdown = self.calculate_drawdown(equity_curve)
        
        # Calculate realized volatility
        realized_vol = self.calculate_realized_volatility(returns)
        
        # Get current exposure (default to 100% if not available)
        current_exposure = latest.get('exposure', 1.0) if 'exposure' in latest else 1.0
        
        # Evaluate each kill switch
        dd_triggered, dd_cap, dd_reason = self.evaluate_drawdown_brake(drawdown, current_exposure)
        loss_triggered, loss_cap, loss_reason = self.evaluate_daily_loss_brake(daily_return, current_exposure)
        vol_triggered, vol_cap, vol_reason = self.evaluate_volatility_brake(realized_vol, current_exposure)
        
        # Determine if any kill switch triggered
        emergency_active = dd_triggered or loss_triggered or vol_triggered
        
        # Take most conservative exposure cap
        if emergency_active:
            exposure_cap = min(dd_cap if dd_triggered else 1.0,
                              loss_cap if loss_triggered else 1.0,
                              vol_cap if vol_triggered else 1.0)
            
            # Determine which kill switch triggered (priority: daily loss > drawdown > volatility)
            if loss_triggered:
                kill_switch = "DAILY_LOSS_BRAKE"
                reason = loss_reason
            elif dd_triggered:
                kill_switch = "DRAWDOWN_BRAKE"
                reason = dd_reason
            else:
                kill_switch = "VOLATILITY_BRAKE"
                reason = vol_reason
        else:
            exposure_cap = current_exposure
            kill_switch = None
            reason = None
        
        # Calculate overall risk level
        risk_level = self.calculate_risk_level(drawdown, daily_return, realized_vol)
        
        # Create risk state
        risk_state = RiskState(
            date=date,
            portfolio_value=portfolio_value,
            drawdown=drawdown,
            daily_return=daily_return,
            realized_vol=realized_vol,
            risk_level=risk_level,
            emergency_active=emergency_active,
            exposure_cap=exposure_cap,
            kill_switch_triggered=kill_switch,
            kill_switch_reason=reason
        )
        
        return risk_state
    
    def log_risk_state(self, risk_state: RiskState) -> None:
        """
        Log risk state to parquet file for audit trail
        
        Args:
            risk_state: RiskState object to log
        """
        # Convert to DataFrame
        risk_df = pd.DataFrame([asdict(risk_state)])
        
        # Append to existing log or create new
        if os.path.exists(self.risk_state_file):
            existing_df = pd.read_parquet(self.risk_state_file)
            risk_df = pd.concat([existing_df, risk_df], ignore_index=True)
        
        # Save to parquet
        risk_df.to_parquet(self.risk_state_file, index=False)
    
    def evaluate_and_apply(self) -> Optional[RiskState]:
        """
        Main method: Evaluate kill switches and apply risk controls
        
        Returns:
            RiskState object with current risk assessment, or None if error
        """
        print("🚨 KILL SWITCH SYSTEM - INSTITUTIONAL VALIDATION")
        print("=" * 60)
        
        # Load performance data
        performance_df = self.load_performance_data()
        
        if performance_df is None:
            print("⚠️ No performance data available")
            return None
        
        print(f"📊 Loaded {len(performance_df)} days of performance data")
        
        # Evaluate kill switches
        risk_state = self.evaluate_kill_switches(performance_df)
        
        # Log risk state
        self.log_risk_state(risk_state)
        
        # Print results
        print(f"\n🔍 RISK STATE ASSESSMENT:")
        print(f"   Date: {risk_state.date.strftime('%Y-%m-%d')}")
        print(f"   Portfolio Value: {risk_state.portfolio_value:.4f}")
        print(f"   Drawdown: {risk_state.drawdown:.2%}")
        print(f"   Daily Return: {risk_state.daily_return:.2%}")
        print(f"   Realized Vol (30d): {risk_state.realized_vol:.2%}")
        print(f"   Risk Level: {risk_state.risk_level:.2f}")
        
        if risk_state.emergency_active:
            print(f"\n🚨 KILL SWITCH ACTIVATED:")
            print(f"   Switch: {risk_state.kill_switch_triggered}")
            print(f"   Reason: {risk_state.kill_switch_reason}")
            print(f"   Exposure Cap: {risk_state.exposure_cap:.1%}")
        else:
            print(f"\n✅ ALL KILL SWITCHES PASSED")
            print(f"   Current Exposure: {risk_state.exposure_cap:.1%}")
        
        print(f"\n💾 Risk state logged to: {self.risk_state_file}")
        
        return risk_state


def main():
    """Main execution function"""
    kill_switches = KillSwitchSystem()
    risk_state = kill_switches.evaluate_and_apply()
    return risk_state


if __name__ == "__main__":
    main()
