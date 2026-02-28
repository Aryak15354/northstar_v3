#!/usr/bin/env python3
"""
Macro Backtester - Step 6 of Northstar Macro Engine
Backtests the macro-controlled portfolio system
"""
import pandas as pd
import numpy as np
import os

# Input files
PRICES_FILE = "data/processed/prices.parquet"  # Using existing Northstar prices
WEIGHTS_FILE = "data/portfolio/final_weights.parquet"
OUT_FILE = "data/backtests/macro_portfolio.parquet"

os.makedirs("data/backtests", exist_ok=True)

def load_prices():
    """Load price data for backtesting"""
    
    print("📈 Loading price data...")
    
    if not os.path.exists(PRICES_FILE):
        raise FileNotFoundError(f"Price data not found: {PRICES_FILE}. Run price fetcher first: python src/ingestion/price_fetcher.py")
    
    # Load actual price data
    prices = pd.read_parquet(PRICES_FILE)
    
    # Handle different price data formats
    if 'ticker' in prices.columns and 'Close' in prices.columns:
        # Long format - pivot to wide
        date_col = 'Date' if 'Date' in prices.columns else 'date'
        prices_wide = prices.pivot(index=date_col, columns='ticker', values='Close')
        return prices_wide
    else:
        # Assume already in wide format
        return prices

def calculate_portfolio_returns(prices_df, weights_df):
    """Calculate portfolio returns from prices and weights"""
    
    print("💰 Computing portfolio returns...")
    
    # Align dates
    common_dates = prices_df.index.intersection(weights_df.index)
    
    if len(common_dates) == 0:
        print("❌ No overlapping dates between prices and weights")
        return None
    
    # Sort dates
    common_dates = sorted(common_dates)
    
    prices_aligned = prices_df.loc[common_dates]
    weights_aligned = weights_df.loc[common_dates]
    
    print(f"   Aligned data: {len(common_dates)} dates")
    print(f"   Date range: {common_dates[0]} to {common_dates[-1]}")
    
    # Get common tickers
    price_tickers = set(prices_aligned.columns)
    weight_tickers = set([col for col in weights_aligned.columns 
                         if not col.lower().startswith(('applied_', 'total_', 'max_', 'risk_'))])
    
    common_tickers = list(price_tickers.intersection(weight_tickers))
    
    if not common_tickers:
        print("❌ No common tickers between prices and weights")
        return None
    
    print(f"   Trading {len(common_tickers)} common stocks")
    
    # Calculate returns
    returns = prices_aligned[common_tickers].pct_change().fillna(0)
    weights = weights_aligned[common_tickers].fillna(0)
    
    # Portfolio returns = sum(weight * return) for each date
    portfolio_returns = (weights * returns).sum(axis=1)
    
    # Calculate cumulative equity curve
    equity_curve = (1 + portfolio_returns).cumprod()
    
    # Calculate additional metrics
    results = pd.DataFrame({
        'Return': portfolio_returns,
        'Equity': equity_curve,
        'Drawdown': (equity_curve / equity_curve.cummax()) - 1,
        'Total_Exposure': weights_aligned.get('Total_Exposure', weights.sum(axis=1)),
        'Risk_Budget': weights_aligned.get('Applied_Risk_Budget', 1.0)
    })
    
    return results

def calculate_performance_metrics(results_df):
    """Calculate comprehensive performance metrics"""
    
    print("\n📊 Performance Analysis:")
    print("=" * 40)
    
    returns = results_df['Return'].dropna()
    equity = results_df['Equity'].dropna()
    
    if len(returns) == 0:
        print("❌ No return data available")
        return {}
    
    # Basic metrics
    total_return = equity.iloc[-1] - 1
    annualized_return = (equity.iloc[-1] ** (252 / len(returns))) - 1
    volatility = returns.std() * np.sqrt(252)
    sharpe_ratio = annualized_return / volatility if volatility > 0 else 0
    
    # Drawdown metrics
    drawdowns = results_df['Drawdown']
    max_drawdown = drawdowns.min()
    
    # Win rate
    win_rate = (returns > 0).mean()
    
    # Calmar ratio
    calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown < 0 else np.inf
    
    metrics = {
        'Total Return': total_return,
        'Annualized Return': annualized_return,
        'Volatility': volatility,
        'Sharpe Ratio': sharpe_ratio,
        'Max Drawdown': max_drawdown,
        'Calmar Ratio': calmar_ratio,
        'Win Rate': win_rate,
        'Total Trades': len(returns),
        'Start Date': equity.index[0],
        'End Date': equity.index[-1]
    }
    
    # Print metrics
    print(f"Total Return: {total_return:.2%}")
    print(f"Annualized Return: {annualized_return:.2%}")
    print(f"Volatility: {volatility:.2%}")
    print(f"Sharpe Ratio: {sharpe_ratio:.2f}")
    print(f"Max Drawdown: {max_drawdown:.2%}")
    print(f"Calmar Ratio: {calmar_ratio:.2f}")
    print(f"Win Rate: {win_rate:.2%}")
    
    return metrics

def run():
    """Main backtesting function"""
    print("📈 Macro Backtester - Step 6")
    print("=" * 50)
    
    # Load price data
    prices_df = load_prices()
    print(f"   Loaded prices: {len(prices_df)} dates × {len(prices_df.columns)} assets")
    
    # Load portfolio weights
    print("📊 Loading portfolio weights...")
    
    if not os.path.exists(WEIGHTS_FILE):
        print(f"❌ Portfolio weights not found: {WEIGHTS_FILE}")
        print("   Run apply_macro_overlay.py first!")
        return
    
    weights_df = pd.read_parquet(WEIGHTS_FILE)
    print(f"   Loaded weights: {len(weights_df)} dates")
    
    # Calculate portfolio performance
    results = calculate_portfolio_returns(prices_df, weights_df)
    
    if results is None:
        print("❌ Failed to calculate portfolio returns")
        return
    
    # Calculate performance metrics
    metrics = calculate_performance_metrics(results)
    
    # Save backtest results
    results.to_parquet(OUT_FILE)
    print(f"\n✅ Backtest results saved: {OUT_FILE}")
    
    # Save performance metrics
    metrics_file = OUT_FILE.replace('.parquet', '_metrics.csv')
    metrics_df = pd.DataFrame([metrics]).T
    metrics_df.columns = ['Value']
    metrics_df.to_csv(metrics_file)
    print(f"📊 Performance metrics: {metrics_file}")
    
    # Save equity curve for plotting
    equity_file = OUT_FILE.replace('.parquet', '_equity.csv')
    equity_df = results[['Equity', 'Drawdown', 'Total_Exposure']].reset_index()
    equity_df.to_csv(equity_file, index=False)
    print(f"📈 Equity curve: {equity_file}")
    
    print(f"\n🎯 Backtest Complete!")
    print(f"   Final Portfolio Value: {results['Equity'].iloc[-1]:.2f}")
    print(f"   This represents the macro-controlled system performance")

if __name__ == "__main__":
    run()