#!/usr/bin/env python3
"""
📈 P&L CHART DATA GENERATOR
Generate chart-ready P&L data for dashboard visualization
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime

def generate_pnl_chart_data():
    """Generate P&L chart data for dashboard"""
    
    print("📈 Generating P&L chart data...")
    
    # Load P&L data
    pnl_df = pd.read_parquet('data/portfolio/pnl_on_paper.parquet')
    
    # Ensure Date column is datetime
    pnl_df['Date'] = pd.to_datetime(pnl_df['Date'])
    
    # Sample data for chart (take every 5th day to reduce size)
    chart_df = pnl_df.iloc[::5].copy()
    
    # Calculate cumulative returns
    initial_equity = chart_df['Equity'].iloc[0]
    chart_df['cumulative_return'] = (chart_df['Equity'] / initial_equity - 1) * 100
    
    # Calculate rolling metrics
    chart_df['rolling_vol_30d'] = chart_df['Return'].rolling(30).std() * np.sqrt(252) * 100
    chart_df['rolling_sharpe_30d'] = (chart_df['Return'].rolling(30).mean() * 252) / (chart_df['Return'].rolling(30).std() * np.sqrt(252))
    
    # Calculate drawdowns
    peak = chart_df['Equity'].expanding().max()
    chart_df['drawdown'] = (chart_df['Equity'] / peak - 1) * 100
    
    # Prepare chart data
    chart_data = {
        'dates': chart_df['Date'].dt.strftime('%Y-%m-%d').tolist(),
        'equity': chart_df['Equity'].round(0).tolist(),
        'cumulative_return': chart_df['cumulative_return'].round(2).tolist(),
        'drawdown': chart_df['drawdown'].round(2).tolist(),
        'rolling_vol': chart_df['rolling_vol_30d'].fillna(0).round(1).tolist(),
        'rolling_sharpe': chart_df['rolling_sharpe_30d'].fillna(0).round(2).tolist(),
        'metadata': {
            'start_date': chart_df['Date'].iloc[0].strftime('%Y-%m-%d'),
            'end_date': chart_df['Date'].iloc[-1].strftime('%Y-%m-%d'),
            'initial_equity': float(initial_equity),
            'final_equity': float(chart_df['Equity'].iloc[-1]),
            'total_return': float(chart_df['cumulative_return'].iloc[-1]),
            'max_drawdown': float(chart_df['drawdown'].min()),
            'data_points': len(chart_df)
        }
    }
    
    # Save chart data
    os.makedirs('data/processed/cache', exist_ok=True)
    chart_file = 'data/processed/cache/pnl_chart_data.json'
    
    with open(chart_file, 'w') as f:
        json.dump(chart_data, f, indent=2)
    
    print(f"   ✅ Generated P&L chart data: {len(chart_df)} points")
    print(f"   📊 Total return: {chart_data['metadata']['total_return']:.1f}%")
    print(f"   📉 Max drawdown: {chart_data['metadata']['max_drawdown']:.1f}%")
    print(f"   💾 Saved to: {chart_file}")
    
    return chart_data

def main():
    """Main function"""
    return generate_pnl_chart_data()

if __name__ == "__main__":
    main()