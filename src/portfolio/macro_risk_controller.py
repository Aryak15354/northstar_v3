#!/usr/bin/env python3
"""
Macro Risk Controller - Step 4 of Northstar Macro Engine
Converts macro regimes into portfolio risk budgets
"""
import pandas as pd
import numpy as np
import os

IN_FILE = "data/macro/factors/macro_score.parquet"
OUT_FILE = "data/macro/factors/risk_budget.parquet"

os.makedirs("data/macro/factors", exist_ok=True)

# === RISK BUDGET MAPPING ===
# Based on hedge fund risk management practices
# These are maximum allowed equity exposures by regime

RISK_MAP = {
    "Boom": 1.0,        # Full risk-on: 100% equity exposure allowed
    "Expansion": 0.8,   # High risk: 80% equity exposure  
    "Late-Expansion": 0.6,  # Topping / fragile: moderate risk
    "Neutral": 0.6,     # Moderate risk: 60% equity exposure
    "Slowdown": 0.4,    # Low risk: 40% equity exposure
    "Crisis": 0.2       # Defensive: 20% equity exposure maximum
}

# === DYNAMIC ADJUSTMENTS ===
# Additional risk adjustments based on regime momentum

MOMENTUM_ADJUSTMENTS = {
    "Improving": 1.1,      # 10% boost if regime improving
    "Stable": 1.0,         # No adjustment if stable
    "Deteriorating": 0.9,  # 10% reduction if deteriorating
    "Unknown": 1.0         # No adjustment if unknown
}

def calculate_volatility_adjustment(macro_score_series, window=12):
    """Adjust risk budget based on MacroScore volatility"""
    
    # Calculate rolling volatility of MacroScore
    vol = macro_score_series.rolling(window=window).std()
    
    # High volatility = reduce risk, Low volatility = increase risk
    # Normalize to 0.8 - 1.2 range
    vol_adj = 1.0 - (vol - vol.median()) / vol.std() * 0.1
    vol_adj = np.clip(vol_adj, 0.8, 1.2)
    
    return vol_adj

def calculate_trend_adjustment(macro_score_series, window=8):
    """Adjust risk budget based on MacroScore trend"""
    
    # Calculate trend (8-week moving average slope)
    trend = macro_score_series.rolling(window=window).apply(
        lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) == window else np.nan
    )
    
    # Positive trend = increase risk, Negative trend = decrease risk
    trend_adj = 1.0 + np.clip(trend * 2, -0.2, 0.2)
    
    return trend_adj

def validate_risk_budgets(df):
    """Validate risk budget calculations"""
    
    print("\n📊 Risk Budget Analysis:")
    print("=" * 30)
    
    # Risk budget distribution
    print("Risk Budget Distribution:")
    for regime in RISK_MAP.keys():
        regime_data = df[df['Regime'] == regime]['Max_Equity_Exposure']
        if len(regime_data) > 0:
            print(f"  {regime}: {regime_data.mean():.2f} ± {regime_data.std():.2f}")
    
    # Average risk budget over time
    avg_risk = df['Max_Equity_Exposure'].mean()
    print(f"\nAverage Risk Budget: {avg_risk:.2f}")
    
    # Risk budget volatility
    risk_vol = df['Max_Equity_Exposure'].std()
    print(f"Risk Budget Volatility: {risk_vol:.3f}")
    
    # Current risk budget
    if len(df) > 0:
        current = df.iloc[-1]
        print(f"\nCurrent Risk Budget: {current['Max_Equity_Exposure']:.2f}")
        print(f"Current Regime: {current['Regime']}")
    
    # Risk budget changes
    risk_changes = (df['Max_Equity_Exposure'].diff().abs() > 0.05).sum()
    print(f"\nSignificant Risk Changes (>5%): {risk_changes}")

def run():
    """Main function to build macro risk controller"""
    print("🎚️  Macro Risk Controller - Step 4")
    print("=" * 50)
    
    # Load macro regime data
    print("📥 Loading macro regime data...")
    
    if not os.path.exists(IN_FILE):
        print(f"❌ Macro regime data not found: {IN_FILE}")
        print("   Run macro_regime.py first!")
        return
    
    df = pd.read_parquet(IN_FILE)
    print(f"   Loaded: {len(df)} weeks of regime data")
    print(f"   Date range: {df.index.min()} to {df.index.max()}")
    
    # Check required columns
    required_cols = ['Regime', 'MacroScore']
    missing_cols = [c for c in required_cols if c not in df.columns]
    
    if missing_cols:
        print(f"❌ Missing required columns: {missing_cols}")
        return
    
    print(f"   Available regimes: {df['Regime'].unique()}")
    
    # Calculate base risk budget from regime
    print("\n💰 Calculating base risk budgets...")
    df['Base_Risk_Budget'] = df['Regime'].map(RISK_MAP)
    # Fallback for any unknown/new regimes
    df['Base_Risk_Budget'] = df['Base_Risk_Budget'].fillna(0.6)
    
    # Apply momentum adjustments
    print("📈 Applying momentum adjustments...")
    if 'Regime_Momentum' in df.columns:
        momentum_adj = df['Regime_Momentum'].map(MOMENTUM_ADJUSTMENTS)
        df['Momentum_Adjustment'] = momentum_adj
    else:
        df['Momentum_Adjustment'] = 1.0
        print("   ⚠️  No momentum data available, using 1.0")
    
    # Apply volatility adjustments
    print("📊 Applying volatility adjustments...")
    df['Volatility_Adjustment'] = calculate_volatility_adjustment(df['MacroScore'])
    
    # Apply trend adjustments  
    print("📈 Applying trend adjustments...")
    df['Trend_Adjustment'] = calculate_trend_adjustment(df['MacroScore'])
    
    # Calculate final risk budget
    print("🎯 Computing final risk budgets...")
    df['Max_Equity_Exposure'] = (
        df['Base_Risk_Budget'] * 
        df['Momentum_Adjustment'] * 
        df['Volatility_Adjustment'] * 
        df['Trend_Adjustment']
    )

    # CIO-grade Late-Expansion haircut based on weak internals if available
    # Expect MarketBreadth / MarketParticipation from macro_score.parquet
    topping_haircut = pd.Series(index=df.index, data=1.0, dtype=float)
    if 'MarketBreadth' in df.columns or 'MarketParticipation' in df.columns:
        b = df.get('MarketBreadth', pd.Series(index=df.index, data=pd.NA)).astype(float)
        p = df.get('MarketParticipation', pd.Series(index=df.index, data=pd.NA)).astype(float)
        cond = (df['Regime'] == 'Late-Expansion')
        # Haircut logic: if breadth < 0.60 and/or participation < 0.40
        weak_b = cond & (b < 0.60)
        weak_p = cond & (p < 0.40)
        both = weak_b & weak_p
        # Apply multiplicative haircuts
        topping_haircut[both] = 0.70
        topping_haircut[weak_b ^ weak_p] = 0.80
        df['Max_Equity_Exposure'] = df['Max_Equity_Exposure'] * topping_haircut
        # Notes for diagnostics
        note = pd.Series(index=df.index, data='', dtype=object)
        note[both] = 'Breadth & Participation weak'
        note[weak_b & ~weak_p] = 'Breadth weak'
        note[weak_p & ~weak_b] = 'Participation weak'
        df['Topping_Haircut'] = topping_haircut
        df['Topping_Note'] = note
    else:
        df['Topping_Haircut'] = 1.0
        df['Topping_Note'] = ''
    
    # Ensure risk budget stays within reasonable bounds
    df['Max_Equity_Exposure'] = np.clip(df['Max_Equity_Exposure'], 0.1, 1.0)
    
    # Calculate risk budget changes
    df['Risk_Budget_Change'] = df['Max_Equity_Exposure'].diff()
    df['Risk_Budget_Change_Pct'] = df['Max_Equity_Exposure'].pct_change(fill_method=None)
    
    # Validate results
    validate_risk_budgets(df)
    
    # Save risk budget data
    output_cols = [
        'Max_Equity_Exposure', 'Base_Risk_Budget', 
        'Momentum_Adjustment', 'Volatility_Adjustment', 'Trend_Adjustment',
        'Risk_Budget_Change', 'Risk_Budget_Change_Pct', 'Topping_Haircut', 'Topping_Note'
    ]
    
    result_df = df[output_cols]
    result_df.to_parquet(OUT_FILE)
    print(f"\n✅ Saved risk budget data: {OUT_FILE}")
    
    # Save risk budget summary
    summary_file = OUT_FILE.replace('.parquet', '_summary.csv')
    summary = result_df.describe()
    summary.to_csv(summary_file)
    print(f"📋 Risk budget summary: {summary_file}")
    
    # Create risk timeline for visualization
    timeline_file = OUT_FILE.replace('.parquet', '_timeline.csv')
    timeline = df[['Max_Equity_Exposure', 'Regime', 'MacroScore']].reset_index()
    timeline.to_csv(timeline_file, index=False)
    print(f"📅 Risk timeline: {timeline_file}")
    
    print(f"\n🎯 Risk Controller Ready!")
    if len(df) > 0:
        print(f"   Current max equity exposure: {df['Max_Equity_Exposure'].iloc[-1]:.1%}")
        print(f"   This should be used to scale all ODIN/LOKI/HEL position sizes")
    else:
        print(f"   No data available - using default 60% exposure")
        print(f"   This should be used to scale all ODIN/LOKI/HEL position sizes")

if __name__ == "__main__":
    run()