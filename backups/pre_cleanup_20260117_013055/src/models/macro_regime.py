#!/usr/bin/env python3
"""
Macro Regime Engine - Step 3 of Northstar Macro Engine
Turns G, I, L, S factors into MacroScore and regime classification
"""
import pandas as pd
import numpy as np
import os
import json

IN_FILE = "data/macro/factors/macro_factors.parquet"
OUT_FILE = "data/macro/factors/macro_score.parquet"

os.makedirs("data/macro/factors", exist_ok=True)

# === MACRO SCORE FORMULA ===
# Based on economic theory and hedge fund practice
# Positive = Risk-On, Negative = Risk-Off

WEIGHTS = {
    'G': 0.40,   # Growth: Positive = good for risk assets
    'I': -0.30,  # Inflation: Negative = high inflation bad for equities  
    'L': 0.50,   # Liquidity: Positive = ample liquidity good for risk
    'S': -0.60   # Stress: Negative = high stress bad for risk assets
}

def classify_regime(score):
    """Legacy classification by MacroScore only"""
    if score > 1.0:
        return "Boom"
    elif score > 0.3:
        return "Expansion"
    elif score > -0.3:
        return "Neutral"
    elif score > -1.0:
        return "Slowdown"
    else:
        return "Crisis"

def classify_regime_with_stress(score, market_stress_z, breadth=None, participation=None):
    """Stress-aware regime classification.
    - Boom requires strong score and low market stress
    - Expansion for positive but less strong
    - Late-Expansion (Neutral band) renamed to reflect caution
    - Slowdown and Crisis for negatives
    """
    breadth_ok = True if breadth is None else (breadth >= 0.60)
    participation_ok = True if participation is None else (participation >= 0.40)
    # Boom: strong score, very low stress, and stronger internals
    if (score > 1.0) and (market_stress_z is not None and market_stress_z < -0.5) and \
       (breadth is None or breadth >= 0.65) and (participation is None or participation >= 0.45):
        return "Boom"
    # High MacroScore but weak internals = topping / late expansion
    if (score > 1.0) and (not breadth_ok or not participation_ok):
        return "Late-Expansion"
    # Expansion regime guardrails: if stress is elevated or internals weak, downgrade to Late-Expansion
    elif score > 0.3:
        if (market_stress_z is not None and market_stress_z > 1.0) or \
           (breadth is not None and breadth < 0.40) or \
           (participation is not None and participation < 0.30):
            return "Late-Expansion"
        return "Expansion"
    elif score > -0.3:
        return "Late-Expansion"
    elif score > -1.0:
        return "Slowdown"
    else:
        return "Crisis"

def classify_regime_adaptive(score, thresholds):
    t20, t40, t60, t80 = thresholds
    if score > t80:
        return "Boom"
    elif score > t60:
        return "Expansion"
    elif score > t40:
        return "Neutral"
    elif score > t20:
        return "Slowdown"
    else:
        return "Crisis"

def calculate_regime_momentum(df, window=4):
    """Calculate regime momentum (4-week change in MacroScore)"""
    
    df['MacroScore_4w_change'] = df['MacroScore'].diff(window)
    
    def momentum_state(change):
        if pd.isna(change):
            return "Unknown"
        elif change > 0.2:
            return "Improving"
        elif change < -0.2:
            return "Deteriorating"
        else:
            return "Stable"
    
    df['Regime_Momentum'] = df['MacroScore_4w_change'].apply(momentum_state)
    
    return df

def validate_regimes(df):
    """Validate regime classification and provide insights"""
    
    print("\n📊 Regime Analysis:")
    print("=" * 30)
    
    # Regime distribution
    regime_counts = df['Regime'].value_counts()
    print("Regime Distribution:")
    for regime, count in regime_counts.items():
        pct = count / len(df) * 100
        print(f"  {regime}: {count} weeks ({pct:.1f}%)")
    
    # Average MacroScore by regime
    print("\nAverage MacroScore by Regime:")
    regime_scores = df.groupby('Regime')['MacroScore'].agg(['mean', 'std', 'min', 'max'])
    print(regime_scores.round(3))
    
    # Regime transitions
    print("\nRegime Persistence:")
    regime_changes = (df['Regime'] != df['Regime'].shift(1)).sum()
    print(f"  Total regime changes: {regime_changes}")
    print(f"  Average regime duration: {len(df) / regime_changes:.1f} weeks")
    
    # Recent regime
    if len(df) > 0:
        latest = df.iloc[-1]
        print(f"\nCurrent State:")
        print(f"  Regime: {latest['Regime']}")
        print(f"  MacroScore: {latest['MacroScore']:.3f}")
        print(f"  Momentum: {latest.get('Regime_Momentum', 'N/A')}")

def run():
    """Main function to build macro regime engine"""
    print("🧠 Macro Regime Engine - Step 3")
    print("=" * 50)
    
    # Load macro factors
    print("📥 Loading macro factors...")
    
    if not os.path.exists(IN_FILE):
        print(f"❌ Macro factors not found: {IN_FILE}")
        print("   Run macro_blocks.py first!")
        return
    
    df = pd.read_parquet(IN_FILE)
    print(f"   Loaded: {len(df)} weeks of factor data")
    print(f"   Factors: {list(df.columns)}")
    
    # Check for required factors
    required_factors = ['G', 'I', 'L', 'S']
    missing_factors = [f for f in required_factors if f not in df.columns]
    
    if missing_factors:
        print(f"❌ Missing required factors: {missing_factors}")
        return
    
    print(f"   Date range: {df.index.min()} to {df.index.max()}")
    
    # Calculate MacroScore
    print("\n🧮 Computing MacroScore...")
    print("Formula: MacroScore = 0.4×G - 0.3×I + 0.5×L - 0.6×S")
    
    # Optional expanding z-score normalization for each factor to ensure comparability and sign stability
    def expanding_z(series: pd.Series) -> pd.Series:
        m = series.expanding().mean()
        s = series.expanding().std().replace(0, np.nan)
        return (series - m) / (s + 1e-12)

    use_z = os.getenv("MACRO_ZSCORE", "1") != "0"
    if use_z:
        print("   Applying expanding z-score normalization to G, I, L, S (point-in-time safe)")
        for col in ['G','I','L','S']:
            if col in df.columns:
                df[f'{col}_z'] = expanding_z(df[col])
        g = df.get('G_z', df['G'])
        i = df.get('I_z', df['I'])
        l = df.get('L_z', df['L'])
        s = df.get('S_z', df['S'])
    else:
        g, i, l, s = df['G'], df['I'], df['L'], df['S']

    # Blend RBI Stress with equity MarketStress
    ms_path = "data/macro/factors/market_stress.parquet"
    market_stress = None
    market_breadth = None
    market_participation = None
    if os.path.exists(ms_path):
        try:
            ms = pd.read_parquet(ms_path)
            if not isinstance(ms.index, pd.DatetimeIndex) and 'Date' in ms.columns:
                ms['Date'] = pd.to_datetime(ms['Date'], errors='coerce')
                ms = ms.set_index('Date')
            if 'MarketStress' in ms.columns:
                market_stress = ms['MarketStress'].reindex(df.index).ffill()
            if 'breadth' in ms.columns:
                market_breadth = ms['breadth'].reindex(df.index).ffill()
            if 'participation' in ms.columns:
                market_participation = ms['participation'].reindex(df.index).ffill()
        except Exception:
            market_stress = None

    # Build TrueStress ensuring higher = more stress (positive direction)
    def expanding_z(series: pd.Series) -> pd.Series:
        m = series.expanding().mean()
        s_ = series.expanding().std().replace(0, np.nan)
        return (series - m) / (s_ + 1e-12)

    true_stress = s
    if market_stress is not None:
        ms_z = expanding_z(market_stress)
        true_stress = 0.5 * s + 0.5 * ms_z
        df['MarketStress'] = market_stress
        df['MarketStress_z'] = ms_z
        if market_breadth is not None:
            df['MarketBreadth'] = market_breadth
        if market_participation is not None:
            df['MarketParticipation'] = market_participation
        df['TrueStress'] = true_stress
    else:
        df['TrueStress'] = s

    # Calibration: enforce TrueStress positive direction (higher = worse)
    # If average TrueStress is negative, flip sign to align with convention
    if df['TrueStress'].mean(skipna=True) < 0:
        df['TrueStress'] = -df['TrueStress']

    # Per-factor contributions (help detect sign/scale issues)
    df['Contrib_G'] = WEIGHTS['G'] * g
    df['Contrib_I'] = WEIGHTS['I'] * i
    df['Contrib_L'] = WEIGHTS['L'] * l
    df['Contrib_S'] = WEIGHTS['S'] * df['TrueStress']
    df['MacroScore'] = df[['Contrib_G','Contrib_I','Contrib_L','Contrib_S']].sum(axis=1)
    
    # Remove rows with missing MacroScore
    df = df.dropna(subset=['MacroScore'])
    
    print(f"   Computed MacroScore for {len(df)} weeks")
    print(f"   MacroScore range: [{df['MacroScore'].min():.3f}, {df['MacroScore'].max():.3f}]")
    
    # Classify regimes (stress-aware)
    print("\n🏷️  Classifying regimes...")
    adaptive = os.getenv("MACRO_ADAPTIVE_REGIME", "1") != "0"
    gate = df.get('MarketStress_z', pd.Series(index=df.index, data=0.0)).fillna(0.0).tolist()
    gate_breadth = df.get('MarketBreadth', pd.Series(index=df.index, data=np.nan)).tolist()
    gate_participation = df.get('MarketParticipation', pd.Series(index=df.index, data=np.nan)).tolist()
    if adaptive and len(df) >= 20:
        percentiles = df['MacroScore'].quantile([0.2, 0.4, 0.6, 0.8]).values.tolist()
        # Use stress-aware logic; percentiles still logged for reference
        df['Regime'] = [
            classify_regime_with_stress(s, ms, b, p)
            for s, ms, b, p in zip(df['MacroScore'].tolist(), gate, gate_breadth, gate_participation)
        ]
        thresholds_path = OUT_FILE.replace('.parquet', '_thresholds.json')
        with open(thresholds_path, 'w') as f:
            json.dump({"p20": percentiles[0], "p40": percentiles[1], "p60": percentiles[2], "p80": percentiles[3]}, f)
        print(f"   Adaptive thresholds saved (for reference): {thresholds_path}")
    else:
        df['Regime'] = [
            classify_regime_with_stress(s, ms, b, p)
            for s, ms, b, p in zip(df['MacroScore'].tolist(), gate, gate_breadth, gate_participation)
        ]
    
    # Calculate regime momentum
    print("📈 Computing regime momentum...")
    df = calculate_regime_momentum(df)
    
    # Validate results
    validate_regimes(df)
    
    # Save results
    output_cols = ['MacroScore', 'Regime', 'MacroScore_4w_change', 'Regime_Momentum',
                   'Contrib_G','Contrib_I','Contrib_L','Contrib_S', 'TrueStress']
    if 'MarketStress_z' in df.columns:
        output_cols.append('MarketStress_z')
    if 'MarketBreadth' in df.columns:
        output_cols.append('MarketBreadth')
    if 'MarketParticipation' in df.columns:
        output_cols.append('MarketParticipation')
    result_df = df[output_cols]
    
    result_df.to_parquet(OUT_FILE)
    print(f"\n✅ Saved macro regime data: {OUT_FILE}")
    
    # Save regime summary
    summary_file = OUT_FILE.replace('.parquet', '_summary.csv')
    summary = result_df.describe(include='all')
    summary.to_csv(summary_file)
    print(f"📋 Regime summary: {summary_file}")
    
    # Create regime timeline for visualization
    timeline_file = OUT_FILE.replace('.parquet', '_timeline.csv')
    timeline = df[['MacroScore', 'Regime']].reset_index()
    timeline.to_csv(timeline_file, index=False)
    print(f"📅 Regime timeline: {timeline_file}")

    # Diagnostics summary
    diag_summary_file = OUT_FILE.replace('.parquet', '_diagnostics.csv')
    desc = df[['MacroScore','Contrib_G','Contrib_I','Contrib_L','Contrib_S']].describe(percentiles=[0.2, 0.4, 0.6, 0.8])
    desc.to_csv(diag_summary_file)
    print(f"🧪 Diagnostics: {diag_summary_file}")

if __name__ == "__main__":
    run()