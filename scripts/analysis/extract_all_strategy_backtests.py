#!/usr/bin/env python3
"""
Extract All Strategy Backtests from Real Data Files
Loads individual strategy backtest files from data/processed/backtests/
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

OUTPUT_DIR = Path("data/results/analysis/backtests")

def extract_all_strategy_backtests():
    """Extract all individual strategy backtests from real data"""
    
    print("🚀 Extracting All Strategy Backtests from Real Data...")
    print("=" * 60)
    
    backtest_dir = 'data/processed/backtests/'
    
    if not os.path.exists(backtest_dir):
        print(f"❌ Backtest directory not found: {backtest_dir}")
        return None
    
    # Get all strategy backtest files
    strategy_files = []
    for file in os.listdir(backtest_dir):
        if file.endswith('.parquet'):
            strategy_files.append(file)
    
    print(f"📁 Found {len(strategy_files)} strategy backtest files:")
    for file in strategy_files:
        print(f"   - {file}")
    
    all_strategy_data = []
    
    # Load each strategy backtest
    for file in strategy_files:
        strategy_name = file.replace('.parquet', '')
        file_path = os.path.join(backtest_dir, file)
        
        print(f"\n📊 Loading {strategy_name}...")
        
        try:
            strategy_data = pd.read_parquet(file_path)
            print(f"   ✅ Loaded {len(strategy_data)} observations")
            
            # Add strategy name
            strategy_data['strategy'] = strategy_name
            
            # Ensure date column exists and is datetime
            if 'date' in strategy_data.columns:
                strategy_data['date'] = pd.to_datetime(strategy_data['date'])
            elif strategy_data.index.name == 'date' or 'date' in str(strategy_data.index.name).lower():
                strategy_data = strategy_data.reset_index()
                strategy_data['date'] = pd.to_datetime(strategy_data['date'])
            else:
                # Try to find a date-like column
                date_cols = [col for col in strategy_data.columns if 'date' in col.lower() or 'time' in col.lower()]
                if date_cols:
                    strategy_data['date'] = pd.to_datetime(strategy_data[date_cols[0]])
                else:
                    print(f"   ⚠️ No date column found for {strategy_name}")
                    continue
            
            # Filter to last 3 years
            end_date = strategy_data['date'].max()
            start_date = end_date - timedelta(days=3*365)
            strategy_3y = strategy_data[strategy_data['date'] >= start_date].copy()
            
            if len(strategy_3y) > 0:
                print(f"   ✅ 3-year data: {len(strategy_3y)} observations from {strategy_3y['date'].min()} to {strategy_3y['date'].max()}")
                all_strategy_data.append(strategy_3y)
            else:
                print(f"   ⚠️ No 3-year data available for {strategy_name}")
                
        except Exception as e:
            print(f"   ❌ Error loading {strategy_name}: {e}")
            continue
    
    # Combine all strategy data
    if all_strategy_data:
        combined_data = pd.concat(all_strategy_data, ignore_index=True, sort=False)
        
        # Sort by strategy and date
        combined_data = combined_data.sort_values(['strategy', 'date'])
        
        print(f"\n✅ Combined all strategies: {len(combined_data)} total observations")
        print(f"   📅 Date range: {combined_data['date'].min()} to {combined_data['date'].max()}")
        print(f"   🏆 Strategies: {combined_data['strategy'].nunique()}")
        print(f"   📊 Strategy breakdown:")
        for strategy, count in combined_data['strategy'].value_counts().items():
            print(f"      - {strategy}: {count} observations")
        
        # Save to CSV
        output_file = OUTPUT_DIR / 'northstar_all_strategies_3year_backtest.csv'
        combined_data.to_csv(output_file, index=False)
        
        # Generate comprehensive summary
        summary_stats = generate_strategy_summary(combined_data)
        summary_file = OUTPUT_DIR / 'northstar_all_strategies_summary.csv'
        summary_stats.to_csv(summary_file, index=False)
        
        print(f"\n🎯 All Strategy Results Saved:")
        print(f"   📄 Detailed Results: {output_file}")
        print(f"   📊 Summary Stats: {summary_file}")
        
        return combined_data
    else:
        print("\n❌ No strategy backtest data could be loaded")
        return None

def generate_strategy_summary(results_df):
    """Generate comprehensive summary for all strategies"""
    
    print("\n📊 Generating comprehensive strategy summary...")
    
    summary_data = []
    
    for strategy in results_df['strategy'].unique():
        strategy_data = results_df[results_df['strategy'] == strategy].copy()
        
        if len(strategy_data) < 2:
            continue
        
        print(f"   📈 Analyzing {strategy}...")
        
        # Try to find return/equity columns
        returns = None
        equity_col = None
        
        # Look for common column names
        for col in ['daily_return', 'returns', 'return', 'pnl', 'equity', 'nav', 'value']:
            if col in strategy_data.columns:
                if col in ['equity', 'nav', 'value']:
                    equity_col = col
                    returns = strategy_data[col].pct_change().dropna()
                else:
                    returns = strategy_data[col].dropna()
                break
        
        if returns is None or len(returns) < 2:
            print(f"   ⚠️ No return data found for {strategy}")
            continue
        
        # Calculate metrics
        try:
            # Basic performance metrics
            total_return = (1 + returns).prod() - 1.0
            annual_return = (1 + returns).mean() ** 252 - 1.0
            annual_vol = returns.std() * np.sqrt(252)
            sharpe_ratio = (annual_return - 0.06) / annual_vol if annual_vol > 0 else 0
            
            # Drawdown calculation
            if equity_col:
                equity_curve = strategy_data[equity_col]
                peak = equity_curve.expanding().max()
                drawdown = (equity_curve - peak) / peak
                max_drawdown = drawdown.min()
            else:
                equity_curve = (1 + returns).cumprod()
                peak = equity_curve.expanding().max()
                drawdown = (equity_curve - peak) / peak
                max_drawdown = drawdown.min()
            
            # Win rate and other metrics
            win_rate = (returns > 0).mean()
            avg_return = returns.mean()
            median_return = returns.median()
            skewness = returns.skew()
            kurtosis = returns.kurtosis()
            
            # VaR and CVaR (95% confidence)
            var_95 = returns.quantile(0.05)
            cvar_95 = returns[returns <= var_95].mean()
            
            # Calmar ratio
            calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
            
            # Additional metrics from data if available
            avg_exposure = strategy_data['exposure'].mean() if 'exposure' in strategy_data.columns else np.nan
            avg_turnover = strategy_data['turnover'].mean() if 'turnover' in strategy_data.columns else np.nan
            avg_positions = strategy_data['n_positions'].mean() if 'n_positions' in strategy_data.columns else np.nan
            
            summary = {
                'strategy': strategy,
                'total_return': total_return,
                'annual_return': annual_return,
                'annual_volatility': annual_vol,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'calmar_ratio': calmar_ratio,
                'win_rate': win_rate,
                'avg_daily_return': avg_return,
                'median_daily_return': median_return,
                'skewness': skewness,
                'kurtosis': kurtosis,
                'var_95': var_95,
                'cvar_95': cvar_95,
                'avg_exposure': avg_exposure,
                'avg_turnover': avg_turnover,
                'avg_positions': avg_positions,
                'start_date': strategy_data['date'].min(),
                'end_date': strategy_data['date'].max(),
                'total_observations': len(strategy_data),
                'trading_days': len(returns)
            }
            
            summary_data.append(summary)
            print(f"      ✅ {strategy}: {annual_return:.1%} return, {sharpe_ratio:.2f} Sharpe, {max_drawdown:.1%} max DD")
            
        except Exception as e:
            print(f"   ❌ Error calculating metrics for {strategy}: {e}")
            continue
    
    summary_df = pd.DataFrame(summary_data)
    
    # Sort by Sharpe ratio descending
    summary_df = summary_df.sort_values('sharpe_ratio', ascending=False)
    
    print(f"\n✅ Strategy summary generated for {len(summary_df)} strategies")
    print("\n🏆 Top 5 Strategies by Sharpe Ratio:")
    for i, row in summary_df.head().iterrows():
        print(f"   {row['strategy']}: {row['sharpe_ratio']:.2f} Sharpe, {row['annual_return']:.1%} return")
    
    return summary_df

if __name__ == "__main__":
    results = extract_all_strategy_backtests()
    if results is not None:
        print(f"\n🎯 All Strategy Extraction Complete! {len(results)} total observations")
    else:
        print("\n❌ Strategy extraction failed")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
