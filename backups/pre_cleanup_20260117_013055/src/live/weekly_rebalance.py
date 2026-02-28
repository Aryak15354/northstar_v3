#!/usr/bin/env python3
"""
Live Weekly Rebalance - Step 8 of Northstar Macro Engine
Production-ready weekly portfolio rebalancing system
"""
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

# Input files
FINAL_WEIGHTS = "data/portfolio/final_weights.parquet"
EMERGENCY = "data/risk/emergency_signal.parquet"
MACRO_REGIME = "data/macro/factors/macro_score.parquet"
OUT_DIR = "data/live"

os.makedirs(OUT_DIR, exist_ok=True)

def load_latest_data():
    """Load the most recent data for live trading"""
    
    print("📊 Loading latest trading data...")
    
    data = {}
    
    # Load portfolio weights
    if os.path.exists(FINAL_WEIGHTS):
        weights = pd.read_parquet(FINAL_WEIGHTS)
        data['weights'] = weights.iloc[-1] if len(weights) > 0 else None
        print(f"   ✅ Portfolio weights: {len(weights)} dates")
    else:
        print(f"   ❌ Portfolio weights not found: {FINAL_WEIGHTS}")
        data['weights'] = None
    
    # Load emergency signals
    if os.path.exists(EMERGENCY):
        emergency = pd.read_parquet(EMERGENCY)
        data['emergency'] = emergency.iloc[-1] if len(emergency) > 0 else None
        print(f"   ✅ Emergency signals: {len(emergency)} dates")
    else:
        print(f"   ❌ Emergency signals not found: {EMERGENCY}")
        data['emergency'] = None
    
    # Load macro regime
    if os.path.exists(MACRO_REGIME):
        regime = pd.read_parquet(MACRO_REGIME)
        data['regime'] = regime.iloc[-1] if len(regime) > 0 else None
        print(f"   ✅ Macro regime: {len(regime)} dates")
    else:
        print(f"   ❌ Macro regime not found: {MACRO_REGIME}")
        data['regime'] = None
    
    return data

def apply_live_adjustments(weights, emergency_data, regime_data):
    """Apply live risk adjustments to portfolio weights"""
    
    print("⚙️  Applying live risk adjustments...")
    
    if weights is None:
        print("   ❌ No weights available")
        return None
    
    # Get stock columns (exclude metadata)
    stock_cols = [col for col in weights.index 
                 if not col.lower().startswith(('applied_', 'total_', 'max_', 'risk_'))]
    
    adjusted_weights = weights[stock_cols].copy()
    adjustments_applied = []
    
    # 1. Emergency brake adjustment
    if emergency_data is not None and 'Emergency' in emergency_data:
        if emergency_data['Emergency']:
            emergency_multiplier = 0.2  # Reduce to 20% during emergency
            adjusted_weights *= emergency_multiplier
            adjustments_applied.append(f"Emergency brake: {emergency_multiplier:.0%}")
            print(f"   🚨 EMERGENCY MODE: Reducing positions to 20%")
        
        elif 'Position_Multiplier' in emergency_data:
            pos_multiplier = emergency_data['Position_Multiplier']
            adjusted_weights *= pos_multiplier
            adjustments_applied.append(f"Risk adjustment: {pos_multiplier:.0%}")
            print(f"   ⚙️  Risk adjustment: {pos_multiplier:.0%}")
    
    # 2. Macro regime adjustment
    if regime_data is not None and 'Regime' in regime_data:
        regime = regime_data['Regime']
        
        # Additional conservative adjustments for extreme regimes
        if regime == 'Crisis':
            crisis_multiplier = 0.5
            adjusted_weights *= crisis_multiplier
            adjustments_applied.append(f"Crisis mode: {crisis_multiplier:.0%}")
            print(f"   💥 CRISIS MODE: Further reducing positions to 50%")
        
        elif regime == 'Boom':
            # Could increase leverage in boom, but keeping conservative
            print(f"   📈 Boom regime detected - maintaining full allocation")
    
    # 3. Normalize weights to sum to target exposure
    total_weight = adjusted_weights.sum()
    if total_weight > 0:
        # Renormalize but maintain the risk-adjusted total exposure
        target_exposure = total_weight  # Keep the risk-adjusted exposure
        adjusted_weights = adjusted_weights / adjusted_weights.sum() * target_exposure
    
    return adjusted_weights, adjustments_applied

def generate_trade_list(current_weights, previous_weights=None, min_trade_size=0.01):
    """Generate actionable trade list"""
    
    print("📋 Generating trade list...")
    
    if previous_weights is None:
        # First time - all positions are new
        trades = current_weights[current_weights > min_trade_size].copy()
        trade_type = 'BUY'
    else:
        # Calculate position changes
        all_tickers = set(current_weights.index) | set(previous_weights.index)
        
        trades = []
        for ticker in all_tickers:
            current = current_weights.get(ticker, 0)
            previous = previous_weights.get(ticker, 0)
            change = current - previous
            
            if abs(change) > min_trade_size:
                trades.append({
                    'Ticker': ticker,
                    'Current_Weight': current,
                    'Previous_Weight': previous,
                    'Change': change,
                    'Action': 'BUY' if change > 0 else 'SELL',
                    'Trade_Size': abs(change)
                })
        
        trades = pd.DataFrame(trades)
    
    return trades

def create_trading_report(weights, emergency_data, regime_data, adjustments, trades):
    """Create comprehensive trading report"""
    
    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append("🧭 NORTHSTAR WEEKLY TRADING REPORT")
    report_lines.append("=" * 60)
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")
    
    # Market regime
    if regime_data is not None:
        report_lines.append("📊 MACRO REGIME STATUS")
        report_lines.append("-" * 30)
        report_lines.append(f"Current Regime: {regime_data.get('Regime', 'Unknown')}")
        report_lines.append(f"MacroScore: {regime_data.get('MacroScore', 'N/A'):.3f}")
        if 'Regime_Momentum' in regime_data:
            report_lines.append(f"Momentum: {regime_data['Regime_Momentum']}")
        report_lines.append("")
    
    # Risk status
    if emergency_data is not None:
        report_lines.append("🚨 RISK STATUS")
        report_lines.append("-" * 30)
        emergency_status = "ACTIVE" if emergency_data.get('Emergency', False) else "NORMAL"
        report_lines.append(f"Emergency Status: {emergency_status}")
        report_lines.append(f"Risk Level: {emergency_data.get('Risk_Level', 'N/A'):.1f}")
        report_lines.append(f"Current Drawdown: {emergency_data.get('Drawdown', 0):.2%}")
        report_lines.append("")
    
    # Adjustments applied
    if adjustments:
        report_lines.append("⚙️  ADJUSTMENTS APPLIED")
        report_lines.append("-" * 30)
        for adj in adjustments:
            report_lines.append(f"• {adj}")
        report_lines.append("")
    
    # Portfolio summary
    report_lines.append("💼 PORTFOLIO SUMMARY")
    report_lines.append("-" * 30)
    total_exposure = weights.sum()
    report_lines.append(f"Total Exposure: {total_exposure:.1%}")
    report_lines.append(f"Number of Positions: {(weights > 0.001).sum()}")
    report_lines.append(f"Largest Position: {weights.max():.2%}")
    report_lines.append("")
    
    # Top positions
    report_lines.append("📈 TOP 10 POSITIONS")
    report_lines.append("-" * 30)
    top_positions = weights.nlargest(10)
    for ticker, weight in top_positions.items():
        if weight > 0:
            report_lines.append(f"{ticker:15} {weight:8.2%}")
    report_lines.append("")
    
    # Trading activity
    if isinstance(trades, pd.DataFrame) and len(trades) > 0:
        report_lines.append("📋 TRADING ACTIVITY")
        report_lines.append("-" * 30)
        buys = trades[trades['Action'] == 'BUY']
        sells = trades[trades['Action'] == 'SELL']
        
        report_lines.append(f"Total Trades: {len(trades)}")
        report_lines.append(f"Buys: {len(buys)}, Sells: {len(sells)}")
        report_lines.append("")
        
        if len(trades) <= 20:  # Show all trades if not too many
            for _, trade in trades.iterrows():
                report_lines.append(f"{trade['Action']:4} {trade['Ticker']:15} {trade['Trade_Size']:8.2%}")
    else:
        report_lines.append("📋 NO TRADING ACTIVITY")
        report_lines.append("-" * 30)
        report_lines.append("No significant position changes required")
    
    report_lines.append("")
    report_lines.append("=" * 60)
    
    return "\n".join(report_lines)

def run():
    """Main live trading function"""
    print("🔴 Live Weekly Rebalance - Step 8")
    print("=" * 50)
    
    # Load latest data
    data = load_latest_data()
    
    if data['weights'] is None:
        print("❌ Cannot proceed without portfolio weights")
        return
    
    # Apply live adjustments
    adjusted_weights, adjustments = apply_live_adjustments(
        data['weights'], data['emergency'], data['regime']
    )
    
    if adjusted_weights is None:
        print("❌ Failed to generate adjusted weights")
        return
    
    # Load previous weights for comparison (if available)
    previous_file = os.path.join(OUT_DIR, "previous_weights.parquet")
    previous_weights = None
    if os.path.exists(previous_file):
        try:
            previous_df = pd.read_parquet(previous_file)
            previous_weights = previous_df.iloc[-1] if len(previous_df) > 0 else None
        except:
            pass
    
    # Generate trade list
    trades = generate_trade_list(adjusted_weights, previous_weights)
    
    # Create trading report
    report = create_trading_report(
        adjusted_weights, data['emergency'], data['regime'], adjustments, trades
    )
    
    # Print report to console
    print("\n" + report)
    
    # Save files for execution
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save current weights
    current_file = os.path.join(OUT_DIR, f"weights_{timestamp}.parquet")
    weights_df = pd.DataFrame([adjusted_weights])
    weights_df.to_parquet(current_file)
    
    # Update previous weights for next run
    weights_df.to_parquet(previous_file)
    
    # Save trade list
    if isinstance(trades, pd.DataFrame) and len(trades) > 0:
        trades_file = os.path.join(OUT_DIR, f"trades_{timestamp}.csv")
        trades.to_csv(trades_file, index=False)
        print(f"\n📋 Trade list saved: {trades_file}")
    
    # Save trading report
    report_file = os.path.join(OUT_DIR, f"report_{timestamp}.txt")
    with open(report_file, 'w') as f:
        f.write(report)
    print(f"📊 Trading report saved: {report_file}")
    
    print(f"\n🎯 LIVE TRADING READY!")
    print(f"   Total Exposure: {adjusted_weights.sum():.1%}")
    print(f"   Execute trades and monitor positions")

if __name__ == "__main__":
    run()