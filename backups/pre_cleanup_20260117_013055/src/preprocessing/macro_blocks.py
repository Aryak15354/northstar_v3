#!/usr/bin/env python3
"""
Macro Blocks Engine - Step 2 of Northstar Macro Engine
Builds Growth, Inflation, Liquidity, Stress latent factors using PCA
"""
import pandas as pd
import numpy as np
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import os

IN_FILE = "data/macro/cleaned/macro_cleaned.parquet"
OUT_FILE = "data/macro/factors/macro_factors.parquet"

os.makedirs("data/macro/factors", exist_ok=True)

# === MACRO FACTOR DEFINITIONS ===
# These map to economic theory and hedge fund practice
# Updated based on actual RBI data available

GROWTH = [
    "tbill_91d", "tbill_182d", "tbill_364d", "gsec_10y", 
    "nifty", "bankex", "gdp_current", "gdp_constant", "iip"
]

INFLATION = [
    "repo_rate", "reverse_repo_rate", "bank_rate", "msf_rate", "sdf_rate",
    "cpi_2012", "wpi"
]

LIQUIDITY = [
    "crr", "slr", "call_rate_high", "call_rate_low", "fx_reserves", 
    "m1_money_supply", "m2_money_supply", "m3_money_supply",
    "bank_credit", "aggregate_deposits"
]

STRESS = [
    "usd_1m_forward", "usd_3m_forward", "usd_6m_forward", "usdinr",
    "current_account_balance", "bop_overall", "trade_balance"
]

def make_factor(df, cols, factor_name):
    """Create a single factor from multiple indicators using PCA"""
    
    # Filter to available columns
    available_cols = [c for c in cols if c in df.columns]
    
    if not available_cols:
        print(f"   ⚠️  No data available for {factor_name} factor")
        return pd.Series(index=df.index, dtype=float)
    
    print(f"   📊 {factor_name}: Using {len(available_cols)}/{len(cols)} indicators")
    print(f"      Available: {available_cols}")
    
    # Get data and drop rows with any missing values
    X = df[available_cols].dropna()
    
    if len(X) < 10:
        print(f"   ⚠️  Insufficient data for {factor_name} ({len(X)} observations)")
        return pd.Series(index=df.index, dtype=float)
    
    # Standardize (Z-score)
    scaler = StandardScaler()
    Z = scaler.fit_transform(X)
    
    # Run PCA and extract first component
    pca = PCA(n_components=1)
    factor_values = pca.fit_transform(Z).flatten()
    
    # Create series with original index
    factor_series = pd.Series(index=X.index, data=factor_values)
    
    # Reindex to match full dataframe
    factor_series = factor_series.reindex(df.index)
    
    # Report explained variance
    explained_var = pca.explained_variance_ratio_[0]
    print(f"      Explained variance: {explained_var:.1%}")
    
    return factor_series

def validate_factors(factors_df):
    """Validate the factor construction"""
    
    print("\n📊 Factor Validation:")
    print("=" * 30)
    
    for factor in factors_df.columns:
        series = factors_df[factor].dropna()
        if len(series) > 0:
            print(f"{factor}:")
            print(f"  Observations: {len(series)}")
            print(f"  Mean: {series.mean():.3f}")
            print(f"  Std: {series.std():.3f}")
            print(f"  Range: [{series.min():.3f}, {series.max():.3f}]")
        else:
            print(f"{factor}: No valid data")
        print()

def run():
    """Main function to build macro factors"""
    print("🧠 Macro Blocks Engine - Step 2")
    print("=" * 50)
    
    # Load cleaned macro data
    print("📥 Loading cleaned macro data...")
    
    if not os.path.exists(IN_FILE):
        print(f"❌ Cleaned macro data not found: {IN_FILE}")
        print("   Run macro_cleaner.py first!")
        return
    
    macro = pd.read_parquet(IN_FILE)
    print(f"   Loaded: {len(macro)} weeks × {len(macro.columns)} indicators")
    print(f"   Date range: {macro.index.min()} to {macro.index.max()}")
    
    # Initialize factors dataframe
    factors = pd.DataFrame(index=macro.index)
    
    print("\n🏗️  Building macro factors...")
    
    # Build each factor block
    print("\n1️⃣  GROWTH Factor (G)")
    print("   Theory: Economic growth expectations from yield curve + equity markets")
    factors["G"] = make_factor(macro, GROWTH, "Growth")
    
    print("\n2️⃣  INFLATION Factor (I)")  
    print("   Theory: Monetary policy stance and inflation expectations")
    factors["I"] = make_factor(macro, INFLATION, "Inflation")
    
    print("\n3️⃣  LIQUIDITY Factor (L)")
    print("   Theory: System liquidity and money market conditions")
    factors["L"] = make_factor(macro, LIQUIDITY, "Liquidity")
    
    print("\n4️⃣  STRESS Factor (S)")
    print("   Theory: Financial stress and currency/volatility pressures")
    factors["S"] = make_factor(macro, STRESS, "Stress")
    
    # Remove rows where all factors are NaN
    factors = factors.dropna(how='all')
    
    print(f"\n📊 Final factor dataset: {len(factors)} observations")
    
    # Validate factors
    validate_factors(factors)
    
    # Check factor correlations
    print("🔗 Factor Correlations:")
    corr_matrix = factors.corr()
    print(corr_matrix.round(3))
    
    # Enforce deterministic factor orientation using anchor correlations
    # Growth: positive vs 'nifty' or GDP or yield-curve slope; Inflation: positive vs CPI/WPI; Liquidity: positive vs M3; Stress: positive vs USDINR
    # Prepare yield-curve slope if available
    if all(c in macro.columns for c in ['gsec_10y', 'tbill_364d']):
        macro['_yc_slope'] = macro['gsec_10y'] - macro['tbill_364d']
    else:
        macro['_yc_slope'] = np.nan

    def orient(series, anchor_cols, default_sign=1.0):
        anchors = [c for c in anchor_cols if c in macro.columns]
        if not anchors or series.dropna().empty:
            return series * default_sign
        # Build anchor composite on overlapping index
        tmp = pd.concat([macro[anchors], series.rename('factor')], axis=1).dropna()
        if tmp.empty:
            return series * default_sign
        anchor_comp = tmp[anchors].mean(axis=1)
        corr = anchor_comp.corr(tmp['factor'])
        # If correlation is weak, try rolling confirmation (52w)
        if pd.isna(corr) or abs(corr) < 0.1:
            try:
                z = tmp['factor'].rolling(52, min_periods=26).corr(anchor_comp)
                med = z.median()
                if pd.notna(med) and med < 0:
                    return -series
            except Exception:
                pass
            # Fall back to default sign
            return series * default_sign
        if corr < 0:
            return -series
        return series

    factors['G'] = orient(factors['G'], ['nifty', 'gdp_current', 'gdp_constant', '_yc_slope'])
    factors['I'] = orient(factors['I'], ['cpi_2012', 'wpi'])
    factors['L'] = orient(factors['L'], ['m3_money_supply', 'm2_money_supply', 'm1_money_supply'])
    factors['S'] = orient(factors['S'], ['usdinr', 'usd_3m_forward', 'usd_6m_forward'])

    # Save factors
    factors.to_parquet(OUT_FILE)
    print(f"\n✅ Saved macro factors: {OUT_FILE}")
    
    # Save factor summary
    summary_file = OUT_FILE.replace('.parquet', '_summary.csv')
    summary = factors.describe()
    summary.to_csv(summary_file)
    print(f"📋 Factor summary: {summary_file}")
    
    # Save correlation matrix
    corr_file = OUT_FILE.replace('.parquet', '_correlations.csv')
    corr_matrix.to_csv(corr_file)
    print(f"🔗 Correlations: {corr_file}")

if __name__ == "__main__":
    run()