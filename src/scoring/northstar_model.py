#!/usr/bin/env python3
"""
Northstar Scoring Model - Institutional Grade
Multi-factor model with proper risk adjustment and sector neutrality
"""
from src.cohesion.dependency_container import get_dependency_container

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
import os
import sys

# Add src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
if src_dir not in sys.path:
    # Dependency injection - import load_standard_data, save_standard_data, standardize_dataframe from utils.data_standards
# print("⚠️  Data standards module not available - using fallback methods")
    
    def load_standard_data(data_type, validate=True):
        """Fallback data loader"""
        file_map = {
            'prices': 'data/processed/prices.parquet',
            'fundamentals': 'data/processed/fundamentals.parquet'
        }
        if data_type in file_map:
            return pd.read_parquet(file_map[data_type])
        raise FileNotFoundError(f"No fallback for data type: {data_type}")
    
    def save_standard_data(df, data_type, validate=True):
        """Fallback data saver"""
        file_map = {
            'scores': 'data/processed/scores.parquet'
        }
        if data_type in file_map:
            os.makedirs(os.path.dirname(file_map[data_type]), exist_ok=True)
            df.to_parquet(file_map[data_type])
            print(f"✅ Saved {data_type} data: {file_map[data_type]}")
        else:
            raise ValueError(f"No fallback for data type: {data_type}")
    
    def standardize_dataframe(df, schema_name):
        """Fallback standardizer"""
        return df

# Input files
FUND_FILE = "data/processed/fundamentals.parquet"
VAL_FILE = "data/processed/valuation.parquet"
TECH_FILE = "data/processed/technicals.parquet"
PRICE_FILE = "data/processed/prices.parquet"
UNIVERSE_FILE = "universe/nifty500.csv"
OUTPUT_FILE = "data/processed/scores.parquet"

# Scoring model parameters
FACTOR_WEIGHTS = {
    'quality': 0.30,      # Business quality
    'value': 0.25,        # Valuation attractiveness
    'momentum': 0.20,     # Price momentum
    'growth': 0.15,       # Earnings growth
    'profitability': 0.10 # Profitability metrics
}

RISK_PENALTY_WEIGHT = 0.15  # Risk penalty applied to final score

def load_and_validate_data():
    """Load and validate all required data sources"""
    
    print("📊 Loading and validating data sources...")
    
    data = {}
    
    # Load fundamentals
    try:
        data['fundamentals'] = load_standard_data('fundamentals', validate=False)
        print(f"   ✅ Fundamentals: {len(data['fundamentals'])} records")
    except FileNotFoundError:
        print(f"   ❌ Fundamentals not found: {FUND_FILE}")
        raise
    
    # Load valuation
    try:
        data['valuation'] = pd.read_parquet(VAL_FILE)
        print(f"   ✅ Valuation: {len(data['valuation'])} records")
    except FileNotFoundError:
        print(f"   ❌ Valuation not found: {VAL_FILE}")
        raise
    
    # Load technicals
    try:
        data['technicals'] = pd.read_parquet(TECH_FILE)
        print(f"   ✅ Technicals: {len(data['technicals'])} records")
    except FileNotFoundError:
        print(f"   ❌ Technicals not found: {TECH_FILE}")
        raise
    
    # Load prices
    try:
        data['prices'] = load_standard_data('prices', validate=False)
        print(f"   ✅ Prices: {len(data['prices'])} records")
    except FileNotFoundError:
        print(f"   ❌ Prices not found: {PRICE_FILE}")
        raise
    
    # Load universe for industry mapping
    try:
        universe = pd.read_csv(UNIVERSE_FILE)
        universe['ticker'] = universe['Symbol'] + '.NS'
        data['universe'] = universe[['ticker', 'Industry', 'Company Name']]
        print(f"   ✅ Universe: {len(data['universe'])} stocks")
    except FileNotFoundError:
        print(f"   ❌ Universe not found: {UNIVERSE_FILE}")
        raise
    
    return data

def prepare_latest_data(data):
    """Prepare latest data for each ticker"""
    
    print("🔄 Preparing latest data for scoring...")
    
    # Get latest fundamentals (most recent date per ticker)
    fundamentals = data['fundamentals'].sort_values('date').groupby('ticker').tail(1)
    
    # Get latest valuation
    valuation = data['valuation'].sort_values('date').groupby('ticker').tail(1)
    
    # Get latest technicals
    date_col = 'Date' if 'Date' in data['technicals'].columns else 'date'
    technicals = data['technicals'].sort_values(date_col).groupby('ticker').tail(1)
    
    # Get latest prices
    prices = data['prices'].sort_values('Date').groupby('ticker').tail(1)
    
    # Merge all data
    df = fundamentals.merge(valuation, on='ticker', suffixes=('', '_val'), how='outer')
    df = df.merge(technicals, on='ticker', how='outer')
    df = df.merge(prices[['ticker', 'Close', 'Volume']], on='ticker', how='outer')
    df = df.merge(data['universe'], on='ticker', how='left')

    # Normalize common merged columns that can appear with suffixes.
    # This keeps downstream sector-neutralization and reporting stable.
    industry_candidates = [c for c in ['Industry', 'Industry_x', 'Industry_y', 'industry'] if c in df.columns]
    if industry_candidates:
        df['Industry'] = pd.NA
        for c in industry_candidates:
            df['Industry'] = df['Industry'].fillna(df[c])
    else:
        df['Industry'] = pd.NA

    company_candidates = [c for c in ['Company Name', 'Company Name_x', 'Company Name_y', 'company_name'] if c in df.columns]
    if company_candidates:
        df['Company Name'] = pd.NA
        for c in company_candidates:
            df['Company Name'] = df['Company Name'].fillna(df[c])
    else:
        df['Company Name'] = df['ticker']
    
    print(f"   📊 Combined dataset: {len(df)} stocks")
    
    return df

def calculate_quality_score(df):
    """Calculate business quality score"""
    
    print("🏆 Computing quality scores...")
    
    # Return on Equity (ROE)
    df['roe'] = df['net_income'] / df['equity'].replace(0, np.nan)
    
    # Return on Assets (ROA)
    df['roa'] = df['net_income'] / df['total_assets'].replace(0, np.nan)
    
    # Free Cash Flow Margin
    df['fcf_margin'] = df['free_cash_flow'] / df['revenue'].replace(0, np.nan)
    
    # Debt to Equity
    df['debt_to_equity'] = df['total_debt'] / df['equity'].replace(0, np.nan)
    
    # EBITDA Margin (using available ebitda instead of ebit)
    df['ebitda_margin'] = df['ebitda'] / df['revenue'].replace(0, np.nan)
    
    # Revenue Growth (calculate if not available)
    if 'revenue_growth' not in df.columns:
        df = df.sort_values(['ticker', 'date'])
        df['revenue_growth'] = df.groupby('ticker')['revenue'].pct_change()
    
    # Clean and cap extreme values
    quality_metrics = ['roe', 'roa', 'fcf_margin', 'revenue_growth', 'ebitda_margin']
    for metric in quality_metrics:
        if metric in df.columns:
            df[metric] = df[metric].fillna(0)
            # Cap at 99th percentile to handle outliers
            upper_cap = df[metric].quantile(0.99)
            lower_cap = df[metric].quantile(0.01)
            df[metric] = df[metric].clip(lower_cap, upper_cap)
    
    # Debt metrics (lower is better, so invert)
    debt_metrics = ['debt_to_equity']
    for metric in debt_metrics:
        if metric in df.columns:
            df[metric] = df[metric].fillna(df[metric].median())
            # Invert so lower debt = higher score
            df[f'{metric}_inv'] = 1 / (1 + df[metric])
    
    # Combine quality factors using PCA if we have enough data
    quality_cols = [col for col in ['roe', 'roa', 'fcf_margin', 'revenue_growth', 'debt_to_equity_inv', 'ebitda_margin'] 
                   if col in df.columns and df[col].notna().sum() > 10]
    
    if len(quality_cols) >= 3:
        quality_data = df[quality_cols].fillna(0)
        scaler = StandardScaler()
        quality_scaled = scaler.fit_transform(quality_data)
        
        # Use first principal component
        pca = PCA(n_components=1)
        quality_pca = pca.fit_transform(quality_scaled)
        df['quality_score'] = quality_pca.flatten()
        
        # Convert to 0-100 scale
        df['quality_score'] = ((df['quality_score'] - df['quality_score'].min()) / 
                              (df['quality_score'].max() - df['quality_score'].min()) * 100)
        
        print(f"   📊 Quality PCA explained variance: {pca.explained_variance_ratio_[0]:.2%}")
    else:
        # Fallback to simple average
        df['quality_score'] = df[quality_cols].fillna(0).mean(axis=1) * 100
    
    return df

def calculate_value_score(df):
    """Calculate valuation attractiveness score"""
    
    print("💰 Computing value scores...")
    
    # Use existing valuation metrics
    value_metrics = []
    
    if 'true_undervaluation' in df.columns:
        df['value_base'] = df['true_undervaluation'].fillna(0)
        value_metrics.append('value_base')
    
    # P/E ratio (lower is better for value)
    if 'pe_ratio' in df.columns:
        df['pe_ratio'] = df['pe_ratio'].fillna(df['pe_ratio'].median())
        # Invert P/E so lower P/E = higher score
        df['pe_inv'] = 1 / (1 + df['pe_ratio'] / 20)  # Normalize around 20 P/E
        value_metrics.append('pe_inv')
    
    # P/B ratio (lower is better for value)
    if 'pb_ratio' in df.columns:
        df['pb_ratio'] = df['pb_ratio'].fillna(df['pb_ratio'].median())
        df['pb_inv'] = 1 / (1 + df['pb_ratio'] / 3)  # Normalize around 3 P/B
        value_metrics.append('pb_inv')
    
    # EV/EBITDA (lower is better)
    if 'ev_ebitda' in df.columns:
        df['ev_ebitda'] = df['ev_ebitda'].fillna(df['ev_ebitda'].median())
        df['ev_ebitda_inv'] = 1 / (1 + df['ev_ebitda'] / 15)  # Normalize around 15x
        value_metrics.append('ev_ebitda_inv')
    
    # Combine value metrics
    if value_metrics:
        df['value_score'] = df[value_metrics].fillna(0).mean(axis=1) * 100
    else:
        df['value_score'] = 50  # Neutral score if no value metrics
    
    return df

def calculate_momentum_score(df):
    """Calculate price momentum score"""
    
    print("📈 Computing momentum scores...")
    
    momentum_metrics = []
    
    # RSI (50 is neutral, higher is better momentum)
    if 'rsi' in df.columns:
        df['rsi'] = df['rsi'].fillna(50)
        df['rsi_norm'] = df['rsi']
        momentum_metrics.append('rsi_norm')
    
    # MACD (higher is better)
    if 'macd' in df.columns:
        df['macd'] = df['macd'].fillna(0)
        # Normalize MACD to 0-100 scale
        df['macd_norm'] = ((df['macd'] - df['macd'].min()) / 
                          (df['macd'].max() - df['macd'].min()) * 100).fillna(50)
        momentum_metrics.append('macd_norm')
    
    # Trend regime (convert to 0-100 scale)
    if 'trend_regime' in df.columns:
        df['trend_regime'] = df['trend_regime'].fillna(0.5)
        df['trend_norm'] = df['trend_regime'] * 100
        momentum_metrics.append('trend_norm')
    
    # Breakout strength
    if 'breakout_strength' in df.columns:
        df['breakout_strength'] = df['breakout_strength'].fillna(0.5)
        df['breakout_norm'] = df['breakout_strength'] * 100
        momentum_metrics.append('breakout_norm')
    
    # Price performance (if available)
    if 'price_performance_1m' in df.columns:
        df['price_perf_norm'] = ((df['price_performance_1m'] + 0.2) / 0.4 * 100).clip(0, 100)
        momentum_metrics.append('price_perf_norm')
    
    # Combine momentum metrics
    if momentum_metrics:
        df['momentum_score'] = df[momentum_metrics].fillna(50).mean(axis=1)
    else:
        df['momentum_score'] = 50  # Neutral score
    
    return df

def calculate_growth_score(df):
    """Calculate earnings growth score"""
    
    print("🌱 Computing growth scores...")
    
    growth_metrics = []
    
    # Revenue growth (already calculated)
    if 'revenue_growth' in df.columns:
        df['revenue_growth'] = df['revenue_growth'].fillna(0)
        # Convert to 0-100 scale (0% growth = 50, 20% growth = 100)
        df['revenue_growth_norm'] = ((df['revenue_growth'] + 0.1) / 0.3 * 100).clip(0, 100)
        growth_metrics.append('revenue_growth_norm')
    
    # Earnings growth
    if 'earnings_growth' in df.columns:
        df['earnings_growth'] = df['earnings_growth'].fillna(0)
        df['earnings_growth_norm'] = ((df['earnings_growth'] + 0.1) / 0.3 * 100).clip(0, 100)
        growth_metrics.append('earnings_growth_norm')
    
    # Book value growth
    if 'book_value_growth' in df.columns:
        df['book_value_growth'] = df['book_value_growth'].fillna(0)
        df['bv_growth_norm'] = ((df['book_value_growth'] + 0.05) / 0.25 * 100).clip(0, 100)
        growth_metrics.append('bv_growth_norm')
    
    # Combine growth metrics
    if growth_metrics:
        df['growth_score'] = df[growth_metrics].fillna(50).mean(axis=1)
    else:
        df['growth_score'] = 50  # Neutral score
    
    return df

def calculate_profitability_score(df):
    """Calculate profitability score"""
    
    print("💵 Computing profitability scores...")
    
    prof_metrics = []
    
    # Gross margin
    if 'gross_margin' in df.columns:
        df['gross_margin'] = df['gross_margin'].fillna(df['gross_margin'].median())
        df['gross_margin_norm'] = (df['gross_margin'] * 100).clip(0, 100)
        prof_metrics.append('gross_margin_norm')
    
    # Operating margin
    if 'operating_margin' in df.columns:
        df['operating_margin'] = df['operating_margin'].fillna(df['operating_margin'].median())
        df['op_margin_norm'] = (df['operating_margin'] * 100).clip(0, 100)
        prof_metrics.append('op_margin_norm')
    
    # Net margin
    if 'net_margin' in df.columns:
        df['net_margin'] = df['net_margin'].fillna(df['net_margin'].median())
        df['net_margin_norm'] = (df['net_margin'] * 100).clip(0, 100)
        prof_metrics.append('net_margin_norm')
    
    # ROE (already calculated in quality)
    if 'roe' in df.columns:
        df['roe_norm'] = ((df['roe'] + 0.05) / 0.3 * 100).clip(0, 100)
        prof_metrics.append('roe_norm')
    
    # Combine profitability metrics
    if prof_metrics:
        df['profitability_score'] = df[prof_metrics].fillna(50).mean(axis=1)
    else:
        df['profitability_score'] = 50  # Neutral score
    
    return df

def calculate_risk_penalty(df):
    """Calculate risk penalty"""
    
    print("⚠️  Computing risk penalties...")
    
    risk_factors = []
    
    # Volatility penalty (higher volatility = higher penalty)
    if 'atr' in df.columns:
        df['atr'] = df['atr'].fillna(df['atr'].median())
        df['vol_penalty'] = (df['atr'] / df['Close'] * 100).clip(0, 10)  # ATR as % of price
        risk_factors.append('vol_penalty')
    
    # Debt penalty
    if 'debt_to_equity' in df.columns:
        df['debt_penalty'] = (df['debt_to_equity'] / 2).clip(0, 5)  # Cap at 5 points
        risk_factors.append('debt_penalty')
    
    # Liquidity penalty (low volume = higher penalty)
    if 'Volume' in df.columns and 'Close' in df.columns:
        df['dollar_volume'] = df['Volume'] * df['Close']
        df['liquidity_penalty'] = np.where(
            df['dollar_volume'] < df['dollar_volume'].quantile(0.1),
            2,  # 2 point penalty for bottom 10% liquidity
            0
        )
        risk_factors.append('liquidity_penalty')
    
    # Size penalty (very small stocks get penalty)
    if 'market_cap' in df.columns:
        df['size_penalty'] = np.where(
            df['market_cap'] < df['market_cap'].quantile(0.05),
            3,  # 3 point penalty for bottom 5% by market cap
            0
        )
        risk_factors.append('size_penalty')
    
    # Combine risk factors
    if risk_factors:
        df['risk_penalty'] = df[risk_factors].fillna(0).sum(axis=1)
    else:
        df['risk_penalty'] = 0
    
    return df

def apply_sector_neutralization(df):
    """Apply sector neutralization to prevent sector concentration"""
    
    print("🏭 Applying sector neutralization...")
    
    if 'Industry' not in df.columns:
        print("   ⚠️  No Industry column found, skipping sector neutralization")
        return df
    
    # Calculate sector-neutral scores
    for score_col in ['quality_score', 'value_score', 'momentum_score', 'growth_score', 'profitability_score']:
        if score_col in df.columns:
            # Calculate sector means
            sector_means = df.groupby('Industry')[score_col].transform('mean')
            sector_stds = df.groupby('Industry')[score_col].transform('std')
            
            # Z-score within sector
            df[f'{score_col}_sector_neutral'] = (df[score_col] - sector_means) / (sector_stds + 1e-8)
            
            # Convert back to 0-100 scale
            col_name = f'{score_col}_sector_neutral'
            df[col_name] = ((df[col_name] - df[col_name].min()) / 
                           (df[col_name].max() - df[col_name].min()) * 100).fillna(50)
    
    return df

def calculate_final_score(df):
    """Calculate final Northstar score - FIXED VERSION"""
    
    print("🎯 Computing final Northstar scores...")
    
    # FIXED: Ensure all component scores are properly normalized to 0-100 scale
    score_components = {}
    
    missing_factors = []
    for factor, weight in FACTOR_WEIGHTS.items():
        regular_col = f'{factor}_score'
        neutral_col = f'{factor}_score_sector_neutral'
        
        if neutral_col in df.columns and df[neutral_col].std() > 0:
            # Use sector-neutral scores if they vary
            score_components[factor] = df[neutral_col] * weight
            print(f"   ✅ Using {neutral_col} (std: {df[neutral_col].std():.2f})")
        elif regular_col in df.columns and df[regular_col].std() > 0:
            # Use regular scores if they vary
            score_components[factor] = df[regular_col] * weight
            print(f"   ✅ Using {regular_col} (std: {df[regular_col].std():.2f})")
        elif neutral_col in df.columns:
            # Constant but real sector-neutral signal: keep it as-is.
            score_components[factor] = pd.to_numeric(df[neutral_col], errors="coerce").fillna(50.0) * weight
            print(f"   ⚠️  {neutral_col} is constant; using constant real signal")
        elif regular_col in df.columns:
            # Constant but real signal: keep it as-is.
            score_components[factor] = pd.to_numeric(df[regular_col], errors="coerce").fillna(50.0) * weight
            print(f"   ⚠️  {regular_col} is constant; using constant real signal")
        else:
            # No synthetic proxy allowed; missing factors are explicitly tracked.
            missing_factors.append(factor)
            score_components[factor] = pd.Series(0.0, index=df.index)
            print(f"   ❌ Missing real input for factor: {factor}")
    
    # Calculate weighted raw score
    df['raw_score'] = sum(score_components.values())
    
    if len(missing_factors) == len(FACTOR_WEIGHTS):
        raise ValueError("No real factor inputs available to compute northstar_score")

    print(f"   📊 Raw score range: {df['raw_score'].min():.1f} - {df['raw_score'].max():.1f}")
    print(f"   📊 Raw score std: {df['raw_score'].std():.2f}")
    
    # FIXED: Make risk penalty more meaningful
    # Ensure risk penalty has proper variation and impact
    if 'risk_penalty' not in df.columns or df['risk_penalty'].std() == 0:
        print("   ⚠️  Risk penalty missing or constant, calculating from volatility")
        
        # Create risk penalty from available risk metrics
        risk_factors = []
        
        # Volatility penalty
        if 'realized_vol' in df.columns:
            vol_penalty = (df['realized_vol'] - df['realized_vol'].median()) * 20  # Scale to meaningful range
            risk_factors.append(vol_penalty)
        
        # Size penalty (smaller stocks = higher risk)
        if 'market_cap' in df.columns:
            size_penalty = (df['market_cap'].median() - df['market_cap']) / df['market_cap'].std() * 5
            risk_factors.append(size_penalty)
        
        # Debt penalty
        if 'debt_to_equity' in df.columns:
            debt_penalty = (df['debt_to_equity'] - df['debt_to_equity'].median()) * 3
            risk_factors.append(debt_penalty)
        
        if risk_factors:
            df['risk_penalty'] = np.mean(risk_factors, axis=0)
        else:
            # Real-data-only fallback: use neutral penalty instead of synthetic proxy.
            df['risk_penalty'] = 0.0
    
    # Ensure risk penalty has reasonable range
    df['risk_penalty'] = df['risk_penalty'].clip(-10, 20)  # -10 to +20 range
    
    print(f"   📊 Risk penalty range: {df['risk_penalty'].min():.1f} - {df['risk_penalty'].max():.1f}")
    print(f"   📊 Risk penalty std: {df['risk_penalty'].std():.2f}")
    
    # FIXED: Apply meaningful risk penalty
    # Increase risk penalty weight to make it more impactful
    EFFECTIVE_RISK_WEIGHT = 0.5  # Increased from 0.15
    df['northstar_score'] = df['raw_score'] - (df['risk_penalty'] * EFFECTIVE_RISK_WEIGHT)

    # Ensure scores are in reasonable range but allow for full distribution
    df['northstar_score'] = df['northstar_score'].clip(0, 100)

    # FINAL CHECK: If scores are still too clustered, force distribution using RAW distribution
    if df['northstar_score'].std() < 5:
        print("   ⚠️  Scores still too clustered, applying distribution normalization from raw_score")
        rank_key = pd.DataFrame({"raw_score": pd.to_numeric(df["raw_score"], errors="coerce").fillna(0.0)})
        if "ticker" in df.columns:
            rank_key["ticker"] = df["ticker"].astype(str)
        else:
            rank_key["ticker"] = df.index.astype(str)
        rank_key = rank_key.sort_values(["raw_score", "ticker"], ascending=[True, True], kind="mergesort")
        rank_key["score_rank"] = rank_key["raw_score"].rank(pct=True, method="average")
        df["score_rank"] = rank_key.loc[df.index, "score_rank"]
        df['northstar_score'] = (df['score_rank'] * 100).clip(0, 100)
    
    print(f"   📊 Final score range: {df['northstar_score'].min():.1f} - {df['northstar_score'].max():.1f}")
    print(f"   📊 Final score std: {df['northstar_score'].std():.2f}")
    print(f"   📊 Final score mean: {df['northstar_score'].mean():.1f}")
    
    # Add component scores for analysis
    for factor, score in score_components.items():
        df[f'{factor}_contribution'] = score
    
    return df

def main():
    """Main scoring function"""
    print("🎯 Northstar Institutional Scoring Model")
    print("=" * 60)
    
    # Load and validate data
    data = load_and_validate_data()
    
    # Prepare latest data
    df = prepare_latest_data(data)
    
    if len(df) == 0:
        raise ValueError("No data available for scoring")
    
    # Calculate factor scores
    df = calculate_quality_score(df)
    df = calculate_value_score(df)
    df = calculate_momentum_score(df)
    df = calculate_growth_score(df)
    df = calculate_profitability_score(df)
    
    # Calculate risk penalty
    df = calculate_risk_penalty(df)
    
    # Apply sector neutralization
    df = apply_sector_neutralization(df)
    
    # Calculate final score
    df = calculate_final_score(df)
    
    # Prepare output
    output_columns = [
        'ticker', 'Industry', 'Company Name', 'Date',
        'northstar_score', 'raw_score', 'risk_penalty',
        'quality_score', 'value_score', 'momentum_score', 
        'growth_score', 'profitability_score'
    ]
    
    # Add date column
    df['Date'] = pd.Timestamp.now().strftime('%Y-%m-%d')
    
    # Filter to available columns
    available_columns = [col for col in output_columns if col in df.columns]
    result_df = df[available_columns].copy()
    
    # Remove rows with missing scores
    result_df = result_df.dropna(subset=['northstar_score'])
    
    # Sort by score
    result_df = result_df.sort_values('northstar_score', ascending=False)
    
    print(f"\n📊 Scoring Results:")
    print(f"   Total stocks scored: {len(result_df)}")
    print(f"   Score range: {result_df['northstar_score'].min():.1f} - {result_df['northstar_score'].max():.1f}")
    print(f"   Mean score: {result_df['northstar_score'].mean():.1f}")
    
    # Show top 10
    print(f"\n🏆 Top 10 Stocks:")
    top_10 = result_df.head(10)
    for _, row in top_10.iterrows():
        print(f"   {row['ticker']:12} {row.get('Industry', 'Unknown'):20} {row['northstar_score']:6.1f}")
    
    # Save results
    save_standard_data(result_df, 'scores', validate=False)
    
    print(f"\n✅ Institutional Northstar scoring complete!")
    print(f"   Results saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
