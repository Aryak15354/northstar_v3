#!/usr/bin/env python3
"""
🚨 EMERGENCY BRAKE SYSTEM - ABSOLUTE RISK AUTHORITY
Phase 4: Risk systems have absolute authority over all decisions

This system has ABSOLUTE AUTHORITY over all portfolio decisions.
No engine can override emergency brake signals.
When emergency is active, all other systems must obey.

Key Principle: ABSOLUTE RISK AUTHORITY
- Emergency brake overrides everything
- Risk systems are not advisory - they are law
- Market state must respect emergency caps

Usage:
    from src.risk.emergency_brake import EmergencyBrakeEngine
    
    engine = EmergencyBrakeEngine()
    emergency_state = engine.run()
    
    # All other engines MUST check emergency state
    if emergency_state['emergency_active']:
        allowed_exposure = emergency_state['emergency_cap']
"""
import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime

# Ensure project root is on path so `src.*` imports work when run as a script
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_THIS_DIR))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.state.market_state import load_latest_market_state

# Input files
EQUITY_FILE = "data/backtests/macro_portfolio.parquet"
OUT_FILE = "data/risk/emergency_signal.parquet"
MARKET_STATE_FILE = "data/processed/market_state.parquet"

os.makedirs("data/risk", exist_ok=True)

# === EMERGENCY BRAKE PARAMETERS ===
# These are based on institutional risk management standards

MAX_DRAWDOWN = -0.10        # -10% maximum drawdown trigger
VOL_LOOKBACK = 20           # 20-day volatility window (1 month)
VOL_THRESHOLD = 0.03        # 3% daily volatility threshold
CORRELATION_THRESHOLD = 0.8  # High correlation warning
CONSECUTIVE_LOSSES = 5       # 5 consecutive losing days

class EmergencyBrakeEngine:
    """
    Emergency Brake System - ABSOLUTE RISK AUTHORITY
    
    This system has absolute authority over all portfolio decisions.
    When emergency is active, all other systems must obey.
    """
    
    def __init__(self):
        self.equity_file = EQUITY_FILE
        self.output_file = OUT_FILE
        self.market_state_file = MARKET_STATE_FILE
        
        # Emergency thresholds
        self.max_drawdown = MAX_DRAWDOWN
        self.vol_threshold = VOL_THRESHOLD
        self.consecutive_losses = CONSECUTIVE_LOSSES
    
    def load_portfolio_data(self):
        """Load portfolio performance data"""
        try:
            if os.path.exists(self.equity_file):
                df = pd.read_parquet(self.equity_file)
                print(f"📊 Loaded portfolio data: {len(df)} days")
                return df
        except Exception as e:
            print(f"⚠️ Error loading portfolio data: {e}")

        raise FileNotFoundError(
            f"Real-data-only mode: portfolio data missing at {self.equity_file}. "
            "Synthetic emergency-brake inputs are forbidden."
        )

    def calculate_risk_signals(self, df):
        """Calculate all emergency risk signals"""
        
        print("🚨 Computing emergency risk signals...")
        
        equity = df['Equity']
        returns = df['Return']
        
        # 1. Drawdown Signal
        peak = equity.cummax()
        drawdown = (equity / peak) - 1
        drawdown_breach = drawdown < self.max_drawdown
        
        # 2. Volatility Signal  
        rolling_vol = returns.rolling(VOL_LOOKBACK).std()
        vol_breach = rolling_vol > self.vol_threshold
        
        # 3. Consecutive Losses Signal
        loss_streak = (returns < 0).rolling(self.consecutive_losses).sum()
        consecutive_losses = loss_streak >= self.consecutive_losses
        
        # 4. Extreme Return Signal (single day loss > 5%)
        extreme_loss = returns < -0.05
        
        # 5. Volatility Spike Signal (vol > 2x recent average)
        vol_ma = rolling_vol.rolling(60).mean()  # 3-month average vol
        vol_spike = rolling_vol > (2 * vol_ma)
        
        # 6. Market State Stress Signal
        try:
            market_state = load_latest_market_state()
            stress_level = market_state['stress_level']
            market_stress = pd.Series(stress_level > 0.7, index=df.index)  # High market stress
        except:
            market_stress = pd.Series(False, index=df.index)
        
        # Combine signals
        emergency_signals = pd.DataFrame({
            'Drawdown': drawdown,
            'Drawdown_Breach': drawdown_breach,
            'Volatility': rolling_vol,
            'Vol_Breach': vol_breach,
            'Vol_Spike': vol_spike,
            'Consecutive_Losses': consecutive_losses,
            'Extreme_Loss': extreme_loss,
            'Market_Stress': market_stress,
            'Peak_Equity': peak
        }, index=df.index)
        
        # Master emergency signal (any trigger = emergency)
        emergency_signals['Emergency'] = (
            drawdown_breach | 
            vol_breach | 
            consecutive_losses | 
            extreme_loss | 
            vol_spike |
            market_stress
        )
        
        # Risk level (0 = safe, 1 = maximum risk)
        risk_components = [
            drawdown_breach.astype(int) * 0.3,      # Drawdown
            vol_breach.astype(int) * 0.25,          # Volatility
            consecutive_losses.astype(int) * 0.2,   # Consecutive losses
            extreme_loss.astype(int) * 0.15,        # Extreme loss
            market_stress.astype(int) * 0.1         # Market stress
        ]
        
        emergency_signals['Risk_Level'] = sum(risk_components)
        
        return emergency_signals
    
    def calculate_emergency_caps(self, signals_df):
        """Calculate emergency exposure caps - ABSOLUTE AUTHORITY"""
        
        print("⚙️ Computing emergency exposure caps...")
        
        # Base emergency cap (maximum allowed exposure during emergency)
        emergency_cap = pd.Series(1.0, index=signals_df.index)  # 100% normal
        
        # Drawdown-based cap
        drawdown_cap = 1.0 + signals_df['Drawdown'] * 2  # Reduce as drawdown increases
        drawdown_cap = np.clip(drawdown_cap, 0.1, 1.0)   # Never go below 10%
        
        # Volatility-based cap
        vol_cap = pd.Series(1.0, index=signals_df.index)
        vol_cap[signals_df['Vol_Breach']] = 0.5           # 50% cap during high vol
        vol_cap[signals_df['Vol_Spike']] = 0.2            # 20% cap during vol spikes
        
        # Emergency override - ABSOLUTE AUTHORITY
        emergency_override = pd.Series(1.0, index=signals_df.index)
        emergency_override[signals_df['Emergency']] = 0.1  # 10% cap during emergency
        
        # Combined cap (take minimum = most conservative)
        final_cap = np.minimum.reduce([
            emergency_cap,
            drawdown_cap,
            vol_cap, 
            emergency_override
        ])
        
        signals_df['Emergency_Cap'] = final_cap
        
        return signals_df
    
    def update_market_state_with_emergency(self, signals_df):
        """Update market state with emergency caps - ABSOLUTE AUTHORITY"""
        
        if len(signals_df) == 0:
            return
        
        current_signals = signals_df.iloc[-1]
        
        try:
            # Load current market state
            if os.path.exists(self.market_state_file):
                market_df = pd.read_parquet(self.market_state_file)
                
                if not market_df.empty:
                    # Update latest market state with emergency cap
                    latest_idx = market_df.index[-1]
                    
                    # ABSOLUTE AUTHORITY: Emergency cap overrides market state
                    original_exposure = market_df.loc[latest_idx, 'allowed_exposure']
                    emergency_cap = current_signals['Emergency_Cap'] * 100  # Convert to percentage
                    
                    # Take minimum (most conservative)
                    final_exposure = min(original_exposure, emergency_cap)
                    
                    market_df.loc[latest_idx, 'allowed_exposure'] = final_exposure
                    market_df.loc[latest_idx, 'emergency_active'] = current_signals['Emergency']
                    market_df.loc[latest_idx, 'emergency_cap'] = emergency_cap
                    
                    # Save updated market state
                    market_df.to_parquet(self.market_state_file, index=False)
                    
                    print(f"🚨 EMERGENCY AUTHORITY APPLIED:")
                    print(f"   Original Exposure: {original_exposure:.1f}%")
                    print(f"   Emergency Cap: {emergency_cap:.1f}%")
                    print(f"   Final Exposure: {final_exposure:.1f}%")
                    print(f"   Emergency Active: {current_signals['Emergency']}")
                    
        except Exception as e:
            print(f"⚠️ Could not update market state with emergency: {e}")
    
    def validate_emergency_system(self, signals_df):
        """Validate the emergency brake system"""
        
        print("\n🚨 Emergency System Validation:")
        print("=" * 40)
        
        total_days = len(signals_df)
        emergency_days = signals_df['Emergency'].sum()
        
        print(f"Total Trading Days: {total_days}")
        print(f"Emergency Days: {emergency_days} ({emergency_days/total_days:.1%})")
        
        # Signal breakdown
        print(f"\nSignal Breakdown:")
        print(f"  Drawdown Breaches: {signals_df['Drawdown_Breach'].sum()}")
        print(f"  Volatility Breaches: {signals_df['Vol_Breach'].sum()}")
        print(f"  Volatility Spikes: {signals_df['Vol_Spike'].sum()}")
        print(f"  Consecutive Losses: {signals_df['Consecutive_Losses'].sum()}")
        print(f"  Extreme Losses: {signals_df['Extreme_Loss'].sum()}")
        
        # Risk level distribution
        print(f"\nRisk Level Distribution:")
        risk_dist = signals_df['Risk_Level'].value_counts().sort_index()
        for level, count in risk_dist.items():
            print(f"  Level {level:.1f}: {count} days ({count/total_days:.1%})")
        
        # Emergency cap impact
        avg_cap = signals_df['Emergency_Cap'].mean()
        min_cap = signals_df['Emergency_Cap'].min()
        
        print(f"\nEmergency Caps:")
        print(f"  Average Cap: {avg_cap:.1%}")
        print(f"  Minimum Cap: {min_cap:.1%}")
        print(f"  Days with Reduced Caps: {(signals_df['Emergency_Cap'] < 1.0).sum()}")
        
        # Current status
        if len(signals_df) > 0:
            current = signals_df.iloc[-1]
            print(f"\nCurrent Status:")
            print(f"  Emergency Active: {'YES' if current['Emergency'] else 'NO'}")
            print(f"  Risk Level: {current['Risk_Level']:.1f}")
            print(f"  Emergency Cap: {current['Emergency_Cap']:.1%}")
            print(f"  Current Drawdown: {current['Drawdown']:.2%}")
    
    def run(self):
        """Main execution - compute emergency state with absolute authority"""
        
        print("🚨 EMERGENCY BRAKE SYSTEM - ABSOLUTE RISK AUTHORITY")
        print("=" * 60)
        
        # Load portfolio data
        df = self.load_portfolio_data()
        
        if df.empty:
            print("❌ No portfolio data available")
            return None
        
        # Calculate risk signals
        signals_df = self.calculate_risk_signals(df)
        
        # Calculate emergency caps
        signals_df = self.calculate_emergency_caps(signals_df)
        
        # Update market state with emergency authority
        self.update_market_state_with_emergency(signals_df)
        
        # Validate system
        self.validate_emergency_system(signals_df)
        
        # Save emergency signals
        signals_df.to_parquet(self.output_file)
        print(f"\n✅ Emergency signals saved: {self.output_file}")
        
        # Return current emergency state
        if len(signals_df) > 0:
            current = signals_df.iloc[-1]
            emergency_state = {
                'timestamp': datetime.now(),
                'emergency_active': bool(current['Emergency']),
                'risk_level': float(current['Risk_Level']),
                'emergency_cap': float(current['Emergency_Cap'] * 100),  # Convert to percentage
                'drawdown': float(current['Drawdown']),
                'volatility': float(current['Volatility']) if not pd.isna(current['Volatility']) else 0.02
            }
            
            print(f"\n🚨 CURRENT EMERGENCY STATE:")
            print(f"   Emergency Active: {emergency_state['emergency_active']}")
            print(f"   Risk Level: {emergency_state['risk_level']:.1f}")
            print(f"   Emergency Cap: {emergency_state['emergency_cap']:.1f}%")
            print(f"   Drawdown: {emergency_state['drawdown']:.2%}")
            
            return emergency_state
        
        return None

# =========================== UTILITY FUNCTIONS ===========================

def load_emergency_state():
    """Load current emergency state for other engines"""
    
    try:
        if os.path.exists(OUT_FILE):
            df = pd.read_parquet(OUT_FILE)
            if not df.empty:
                current = df.iloc[-1]
                
                emergency_state = {
                    'emergency_active': bool(current['Emergency']),
                    'risk_level': float(current['Risk_Level']),
                    'emergency_cap': float(current['Emergency_Cap'] * 100),
                    'drawdown': float(current['Drawdown'])
                }
                
                print(f"📖 Loaded emergency state: {'ACTIVE' if emergency_state['emergency_active'] else 'INACTIVE'}")
                return emergency_state
    except Exception as e:
        print(f"⚠️ Error loading emergency state: {e}")
    
    # Return default state
    print("⚠️ Using default emergency state: INACTIVE")
    return {
        'emergency_active': False,
        'risk_level': 0.0,
        'emergency_cap': 100.0,
        'drawdown': 0.0
    }

def check_emergency_authority():
    """Check if emergency brake has authority over system"""
    
    emergency_state = load_emergency_state()
    
    if emergency_state['emergency_active']:
        print(f"🚨 EMERGENCY BRAKE ACTIVE - ABSOLUTE AUTHORITY")
        print(f"   All systems must respect {emergency_state['emergency_cap']:.1f}% exposure cap")
        return True
    else:
        print(f"✅ Emergency brake inactive - normal operations")
        return False

def run():
    """Main function for emergency brake system"""
    print("🚨 Emergency Brake System - ABSOLUTE RISK AUTHORITY")
    print("=" * 60)
    
    engine = EmergencyBrakeEngine()
    emergency_state = engine.run()
    
    return emergency_state

# =========================== MAIN EXECUTION ===========================

def main():
    """Main execution"""
    return run()

if __name__ == "__main__":
    main()
