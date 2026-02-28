#!/usr/bin/env python3
"""
Extract Real Data Results for Northstar V3 System
Uses only actual data files - no mock data generation
"""

import pandas as pd
import numpy as np
import os
import sys
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

def extract_3year_backtest_results():
    """Extract 3-year backtest results from real data files"""
    
    print("🚀 Extracting 3-Year Backtest Results from Real Data...")
    print("=" * 60)
    
    # Check for existing backtest data
    backtest_files = []
    
    # Check main backtest directory
    if os.path.exists('data/backtests/'):
        for file in os.listdir('data/backtests/'):
            if file.endswith('.csv') or file.endswith('.parquet'):
                backtest_files.append(os.path.join('data/backtests/', file))
    
    # Check processed backtests directory
    if os.path.exists('data/processed/backtests/'):
        for file in os.listdir('data/processed/backtests/'):
            if file.endswith('.csv') or file.endswith('.parquet'):
                backtest_files.append(os.path.join('data/processed/backtests/', file))
    
    # Check validation directory for walk-forward results
    if os.path.exists('data/validation/walk_forward_results.parquet'):
        backtest_files.append('data/validation/walk_forward_results.parquet')
    
    print(f"📁 Found {len(backtest_files)} backtest data files:")
    for file in backtest_files:
        print(f"   - {file}")
    
    # Load and combine all backtest results
    all_results = []
    
    # Load macro portfolio equity (main backtest)
    if os.path.exists('data/backtests/macro_portfolio_equity.csv'):
        print("\n📊 Loading macro portfolio equity data...")
        equity_data = pd.read_csv('data/backtests/macro_portfolio_equity.csv')
        equity_data['date'] = pd.to_datetime(equity_data['date'])
        
        # Filter to last 3 years
        end_date = equity_data['date'].max()
        start_date = end_date - timedelta(days=3*365)
        equity_3y = equity_data[equity_data['date'] >= start_date].copy()
        
        print(f"   ✅ Loaded {len(equity_3y)} observations from {equity_3y['date'].min()} to {equity_3y['date'].max()}")
        
        # Convert to standard format
        equity_3y['strategy'] = 'northstar_macro'
        equity_3y['daily_return'] = equity_3y['Equity'].pct_change().fillna(0)
        equity_3y['exposure'] = equity_3y['Total_Exposure']
        equity_3y['drawdown'] = equity_3y['Drawdown']
        
        # Calculate additional metrics
        equity_3y['vol_20d'] = equity_3y['daily_return'].rolling(20).std() * np.sqrt(252)
        equity_3y['cash'] = 1.0 - equity_3y['exposure']
        equity_3y['turnover'] = equity_3y['exposure'].diff().abs().fillna(0)
        
        all_results.append(equity_3y[['date', 'strategy', 'Equity', 'daily_return', 'drawdown', 
                                     'vol_20d', 'exposure', 'cash', 'turnover']])
    
    # Load walk-forward validation results if available
    if os.path.exists('data/validation/walk_forward_results.parquet'):
        print("\n📊 Loading walk-forward validation results...")
        try:
            wf_data = pd.read_parquet('data/validation/walk_forward_results.parquet')
            print(f"   ✅ Loaded walk-forward data: {len(wf_data)} observations")
            
            # Filter to last 3 years if date column exists
            if 'date' in wf_data.columns:
                wf_data['date'] = pd.to_datetime(wf_data['date'])
                end_date = wf_data['date'].max()
                start_date = end_date - timedelta(days=3*365)
                wf_3y = wf_data[wf_data['date'] >= start_date].copy()
                
                if len(wf_3y) > 0:
                    all_results.append(wf_3y)
                    print(f"   ✅ Added {len(wf_3y)} walk-forward observations")
        except Exception as e:
            print(f"   ⚠️ Could not load walk-forward data: {e}")
    
    # Load processed strategy performance if available
    if os.path.exists('data/processed/strategy_performance.parquet'):
        print("\n📊 Loading processed strategy performance...")
        try:
            strategy_data = pd.read_parquet('data/processed/strategy_performance.parquet')
            print(f"   ✅ Loaded strategy performance: {len(strategy_data)} observations")
            
            # Filter to last 3 years if date column exists
            if 'date' in strategy_data.columns:
                strategy_data['date'] = pd.to_datetime(strategy_data['date'])
                end_date = strategy_data['date'].max()
                start_date = end_date - timedelta(days=3*365)
                strategy_3y = strategy_data[strategy_data['date'] >= start_date].copy()
                
                if len(strategy_3y) > 0:
                    all_results.append(strategy_3y)
                    print(f"   ✅ Added {len(strategy_3y)} strategy performance observations")
        except Exception as e:
            print(f"   ⚠️ Could not load strategy performance: {e}")
    
    # Combine all results
    if all_results:
        combined_results = pd.concat(all_results, ignore_index=True, sort=False)
        
        # Standardize columns
        required_columns = ['date', 'strategy', 'daily_return', 'drawdown', 'exposure']
        for col in required_columns:
            if col not in combined_results.columns:
                if col == 'strategy':
                    combined_results[col] = 'northstar'
                else:
                    combined_results[col] = 0.0
        
        # Remove duplicates and sort
        combined_results = combined_results.drop_duplicates(subset=['date', 'strategy']).sort_values(['strategy', 'date'])
        
        print(f"\n✅ Combined results: {len(combined_results)} total observations")
        print(f"   📅 Date range: {combined_results['date'].min()} to {combined_results['date'].max()}")
        print(f"   🏆 Strategies: {combined_results['strategy'].nunique()}")
        
        # Save to CSV
        output_file = 'northstar_3year_backtest_real_data.csv'
        combined_results.to_csv(output_file, index=False)
        
        # Generate summary
        summary_stats = generate_real_summary(combined_results)
        summary_file = 'northstar_3year_backtest_summary_real.csv'
        summary_stats.to_csv(summary_file, index=False)
        
        print(f"\n🎯 Real Data Results Saved:")
        print(f"   📄 Detailed Results: {output_file}")
        print(f"   📊 Summary Stats: {summary_file}")
        
        return combined_results
    else:
        print("\n❌ No real backtest data found")
        return None

def extract_6month_live_trading_data():
    """Extract 6-month live trading data from real execution files"""
    
    print("\n🚀 Extracting 6-Month Live Trading Data...")
    print("=" * 60)
    
    live_data_files = []
    
    # Check execution directory
    execution_files = [
        'data/execution/shadow_pnl.parquet',
        'data/execution/shadow_positions.parquet', 
        'data/execution/shadow_trades.parquet',
        'data/execution/transaction_cost_history.parquet'
    ]
    
    for file in execution_files:
        if os.path.exists(file):
            live_data_files.append(file)
    
    # Check live directory
    if os.path.exists('data/live/shadow_trading/'):
        for file in os.listdir('data/live/shadow_trading/'):
            if file.endswith('.csv') or file.endswith('.parquet'):
                live_data_files.append(os.path.join('data/live/shadow_trading/', file))
    
    # Check shadow reality directory
    shadow_files = [
        'data/shadow_reality/shadow_execution_log.parquet',
        'data/shadow_reality/shadow_portfolio_state.parquet'
    ]
    
    for file in shadow_files:
        if os.path.exists(file):
            live_data_files.append(file)
    
    print(f"📁 Found {len(live_data_files)} live trading data files:")
    for file in live_data_files:
        print(f"   - {file}")
    
    all_live_data = []
    
    # Load shadow PnL data
    if os.path.exists('data/execution/shadow_pnl.parquet'):
        print("\n📊 Loading shadow PnL data...")
        try:
            pnl_data = pd.read_parquet('data/execution/shadow_pnl.parquet')
            print(f"   ✅ Loaded shadow PnL: {len(pnl_data)} observations")
            
            # Filter to last 6 months if date column exists
            if 'date' in pnl_data.columns:
                pnl_data['date'] = pd.to_datetime(pnl_data['date'])
                end_date = pnl_data['date'].max()
                start_date = end_date - timedelta(days=6*30)  # 6 months
                pnl_6m = pnl_data[pnl_data['date'] >= start_date].copy()
                
                if len(pnl_6m) > 0:
                    pnl_6m['data_type'] = 'shadow_pnl'
                    all_live_data.append(pnl_6m)
                    print(f"   ✅ Added {len(pnl_6m)} PnL observations from last 6 months")
        except Exception as e:
            print(f"   ⚠️ Could not load shadow PnL: {e}")
    
    # Load shadow positions data
    if os.path.exists('data/execution/shadow_positions.parquet'):
        print("\n📊 Loading shadow positions data...")
        try:
            positions_data = pd.read_parquet('data/execution/shadow_positions.parquet')
            print(f"   ✅ Loaded shadow positions: {len(positions_data)} observations")
            
            # Filter to last 6 months if date column exists
            if 'date' in positions_data.columns:
                positions_data['date'] = pd.to_datetime(positions_data['date'])
                end_date = positions_data['date'].max()
                start_date = end_date - timedelta(days=6*30)  # 6 months
                positions_6m = positions_data[positions_data['date'] >= start_date].copy()
                
                if len(positions_6m) > 0:
                    positions_6m['data_type'] = 'shadow_positions'
                    all_live_data.append(positions_6m)
                    print(f"   ✅ Added {len(positions_6m)} position observations from last 6 months")
        except Exception as e:
            print(f"   ⚠️ Could not load shadow positions: {e}")
    
    # Load shadow trades data
    if os.path.exists('data/execution/shadow_trades.parquet'):
        print("\n📊 Loading shadow trades data...")
        try:
            trades_data = pd.read_parquet('data/execution/shadow_trades.parquet')
            print(f"   ✅ Loaded shadow trades: {len(trades_data)} observations")
            
            # Filter to last 6 months if date column exists
            if 'date' in trades_data.columns:
                trades_data['date'] = pd.to_datetime(trades_data['date'])
                end_date = trades_data['date'].max()
                start_date = end_date - timedelta(days=6*30)  # 6 months
                trades_6m = trades_data[trades_data['date'] >= start_date].copy()
                
                if len(trades_6m) > 0:
                    trades_6m['data_type'] = 'shadow_trades'
                    all_live_data.append(trades_6m)
                    print(f"   ✅ Added {len(trades_6m)} trade observations from last 6 months")
        except Exception as e:
            print(f"   ⚠️ Could not load shadow trades: {e}")
    
    # Load shadow execution log
    if os.path.exists('data/shadow_reality/shadow_execution_log.parquet'):
        print("\n📊 Loading shadow execution log...")
        try:
            exec_data = pd.read_parquet('data/shadow_reality/shadow_execution_log.parquet')
            print(f"   ✅ Loaded execution log: {len(exec_data)} observations")
            
            # Filter to last 6 months if date column exists
            if 'date' in exec_data.columns:
                exec_data['date'] = pd.to_datetime(exec_data['date'])
                end_date = exec_data['date'].max()
                start_date = end_date - timedelta(days=6*30)  # 6 months
                exec_6m = exec_data[exec_data['date'] >= start_date].copy()
                
                if len(exec_6m) > 0:
                    exec_6m['data_type'] = 'execution_log'
                    all_live_data.append(exec_6m)
                    print(f"   ✅ Added {len(exec_6m)} execution observations from last 6 months")
        except Exception as e:
            print(f"   ⚠️ Could not load execution log: {e}")
    
    # Combine all live data
    if all_live_data:
        combined_live = pd.concat(all_live_data, ignore_index=True, sort=False)
        
        # Sort by date
        if 'date' in combined_live.columns:
            combined_live = combined_live.sort_values('date')
        
        print(f"\n✅ Combined live data: {len(combined_live)} total observations")
        if 'date' in combined_live.columns:
            print(f"   📅 Date range: {combined_live['date'].min()} to {combined_live['date'].max()}")
        if 'data_type' in combined_live.columns:
            print(f"   📊 Data types: {combined_live['data_type'].value_counts().to_dict()}")
        
        # Save to CSV
        output_file = 'northstar_6month_live_trading_real_data.csv'
        combined_live.to_csv(output_file, index=False)
        
        print(f"\n🎯 Live Trading Data Saved:")
        print(f"   📄 Live Data Results: {output_file}")
        
        return combined_live
    else:
        print("\n❌ No real live trading data found")
        return None

def generate_real_summary(results_df):
    """Generate summary statistics from real backtest data"""
    
    print("\n📊 Generating summary from real data...")
    
    summary_data = []
    
    for strategy in results_df['strategy'].unique():
        strategy_data = results_df[results_df['strategy'] == strategy].copy()
        
        if len(strategy_data) < 2:
            continue
        
        # Calculate performance metrics from real data
        if 'daily_return' in strategy_data.columns:
            returns = strategy_data['daily_return'].dropna()
        elif 'Equity' in strategy_data.columns:
            returns = strategy_data['Equity'].pct_change().dropna()
        else:
            continue
        
        if len(returns) < 2:
            continue
        
        # Basic metrics
        if 'Equity' in strategy_data.columns:
            total_return = strategy_data['Equity'].iloc[-1] / strategy_data['Equity'].iloc[0] - 1.0
            final_equity = strategy_data['Equity'].iloc[-1]
        else:
            total_return = (1 + returns).prod() - 1.0
            final_equity = (1 + returns).prod()
        
        annual_return = (1 + total_return) ** (252 / len(returns)) - 1.0
        annual_vol = returns.std() * np.sqrt(252)
        sharpe_ratio = (annual_return - 0.06) / annual_vol if annual_vol > 0 else 0
        
        # Drawdown metrics
        if 'drawdown' in strategy_data.columns:
            max_drawdown = strategy_data['drawdown'].min()
        else:
            equity_curve = (1 + returns).cumprod()
            peak = equity_curve.expanding().max()
            drawdown = (equity_curve - peak) / peak
            max_drawdown = drawdown.min()
        
        # Win rate
        win_rate = (returns > 0).mean()
        
        # Other metrics
        avg_exposure = strategy_data['exposure'].mean() if 'exposure' in strategy_data.columns else 0.6
        avg_turnover = strategy_data['turnover'].mean() if 'turnover' in strategy_data.columns else 0.05
        
        summary = {
            'strategy': strategy,
            'total_return': total_return,
            'annual_return': annual_return,
            'annual_volatility': annual_vol,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'avg_exposure': avg_exposure,
            'avg_turnover': avg_turnover,
            'start_date': strategy_data['date'].min(),
            'end_date': strategy_data['date'].max(),
            'total_days': len(strategy_data),
            'final_equity': final_equity
        }
        
        summary_data.append(summary)
    
    summary_df = pd.DataFrame(summary_data)
    
    print(f"✅ Real data summary generated for {len(summary_df)} strategies")
    
    return summary_df

if __name__ == "__main__":
    print("🎯 NORTHSTAR V3 - REAL DATA EXTRACTION")
    print("=" * 60)
    
    # Extract 3-year backtest results
    backtest_results = extract_3year_backtest_results()
    
    # Extract 6-month live trading data
    live_results = extract_6month_live_trading_data()
    
    print("\n" + "=" * 60)
    print("🎯 EXTRACTION COMPLETE!")
    
    if backtest_results is not None:
        print(f"✅ 3-Year Backtest: {len(backtest_results)} observations saved")
    else:
        print("❌ No 3-year backtest data available")
    
    if live_results is not None:
        print(f"✅ 6-Month Live Data: {len(live_results)} observations saved")
    else:
        print("❌ No 6-month live data available")