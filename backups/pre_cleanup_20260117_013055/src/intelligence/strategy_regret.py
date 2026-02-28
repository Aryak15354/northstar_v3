#!/usr/bin/env python3
"""
😈 STRATEGY REGRET ENGINE - OPPORTUNITY COST TRACKING
"How much money did this strategy fail to make when it mattered?"

This tracks regret - the difference between what a strategy made
and what the best strategy made on each day. This catches:
"It made money but missed the real opportunity."

Usage:
    from src.intelligence.strategy_regret import StrategyRegret
    
    regret = StrategyRegret()
    regret.calculate_regret()
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class StrategyRegret:
    """
    Strategy Regret Tracking Engine
    
    Calculates and tracks regret (opportunity cost) for each strategy:
    - Daily regret vs best performer
    - Cumulative regret over time
    - Rolling regret windows
    - Normalized regret percentiles
    - Penalty scores combining regret and drawdown
    """
    
    def __init__(self):
        self.name = "Strategy Regret Engine"
        self.version = "3.0"
        
        # File paths
        self.paths = {
            'regret': 'data/processed/strategy_regret.parquet',
            'backtests': 'data/processed/backtests',
            'beliefs': 'data/processed/strategy_beliefs.parquet'
        }
        
        # Regret parameters
        self.params = {
            'lookback_days': 252,     # 1 year of regret tracking
            'regret_30d_window': 30,  # 30-day rolling regret
            'regret_90d_window': 90,  # 90-day rolling regret
            'min_observations': 20,   # Minimum days for regret calculation
            'regret_penalty_weight': 0.3,  # Weight for regret in penalty score
            'drawdown_penalty_weight': 0.7  # Weight for drawdown in penalty score
        }
    
    def load_strategy_returns(self):
        """Load daily returns for all strategies"""
        
        print("📊 Loading strategy returns for regret calculation...")
        
        strategy_returns = {}
        
        if os.path.exists(self.paths['backtests']):
            for file in os.listdir(self.paths['backtests']):
                if file.endswith('.parquet'):
                    strategy_name = file.replace('.parquet', '')
                    try:
                        df = pd.read_parquet(os.path.join(self.paths['backtests'], file))
                        if not df.empty and 'daily_return' in df.columns and 'date' in df.columns:
                            # Get recent returns
                            recent_df = df.tail(self.params['lookback_days'])
                            
                            if len(recent_df) >= self.params['min_observations']:
                                returns_series = recent_df.set_index('date')['daily_return']
                                strategy_returns[strategy_name] = returns_series
                                
                    except Exception as e:
                        print(f"   ⚠️ Error loading {strategy_name}: {e}")
        
        print(f"   ✅ Loaded returns for {len(strategy_returns)} strategies")
        return strategy_returns
    
    def calculate_daily_regret(self, strategy_returns):
        """Calculate daily regret for each strategy vs best performer"""
        
        print("😈 Calculating daily regret...")
        
        # Align all strategy returns to common dates
        if not strategy_returns:
            return pd.DataFrame()
        
        # Create returns matrix
        returns_df = pd.DataFrame(strategy_returns)
        returns_df = returns_df.fillna(0)  # Fill missing returns with 0
        
        if returns_df.empty:
            return pd.DataFrame()
        
        # Calculate daily best return
        daily_best = returns_df.max(axis=1)
        
        # Calculate regret for each strategy each day
        regret_data = []
        
        for date in returns_df.index:
            best_return = daily_best.loc[date]
            
            for strategy in returns_df.columns:
                strategy_return = returns_df.loc[date, strategy]
                daily_regret = max(0, best_return - strategy_return)  # Only positive regret
                
                regret_data.append({
                    'date': date,
                    'strategy': strategy,
                    'daily_return': strategy_return,
                    'best_return': best_return,
                    'regret': daily_regret
                })
        
        regret_df = pd.DataFrame(regret_data)
        print(f"   ✅ Calculated regret for {len(regret_df)} strategy-days")
        
        return regret_df
    
    def calculate_cumulative_metrics(self, regret_df):
        """Calculate cumulative and rolling regret metrics"""
        
        print("📈 Calculating cumulative regret metrics...")
        
        if regret_df.empty:
            return regret_df
        
        # Sort by date for proper cumulative calculation
        regret_df = regret_df.sort_values(['strategy', 'date'])
        
        # Calculate metrics for each strategy
        enhanced_data = []
        
        for strategy in regret_df['strategy'].unique():
            strategy_data = regret_df[regret_df['strategy'] == strategy].copy()
            
            # Cumulative regret
            strategy_data['cum_regret'] = strategy_data['regret'].cumsum()
            
            # Rolling regret windows
            strategy_data['regret_30d'] = strategy_data['regret'].rolling(
                window=self.params['regret_30d_window'], min_periods=1
            ).sum()
            
            strategy_data['regret_90d'] = strategy_data['regret'].rolling(
                window=self.params['regret_90d_window'], min_periods=1
            ).sum()
            
            # Calculate drawdown from equity curve
            if len(strategy_data) > 1:
                equity = (1 + strategy_data['daily_return']).cumprod()
                running_max = equity.expanding().max()
                strategy_data['drawdown'] = (equity / running_max) - 1
            else:
                strategy_data['drawdown'] = 0.0
            
            enhanced_data.append(strategy_data)
        
        # Combine all strategies
        enhanced_df = pd.concat(enhanced_data, ignore_index=True)
        
        # Calculate normalized regret (percentile across strategies for each date)
        print("📊 Calculating normalized regret percentiles...")
        
        normalized_regret = []
        for date in enhanced_df['date'].unique():
            date_data = enhanced_df[enhanced_df['date'] == date]
            
            if len(date_data) > 1:
                # Calculate percentile rank for regret on this date
                date_data['normalized_regret'] = date_data['regret'].rank(pct=True)
            else:
                date_data['normalized_regret'] = 0.5
            
            normalized_regret.append(date_data)
        
        final_df = pd.concat(normalized_regret, ignore_index=True)
        
        # Calculate penalty score (combines regret and drawdown)
        final_df['penalty_score'] = (
            self.params['regret_penalty_weight'] * final_df['normalized_regret'] +
            self.params['drawdown_penalty_weight'] * abs(final_df['drawdown'])
        )
        
        print(f"   ✅ Enhanced regret data with {len(final_df)} records")
        return final_df
    
    def calculate_regret(self):
        """Main regret calculation process"""
        
        print("😈 STRATEGY REGRET ENGINE")
        print("=" * 50)
        
        # Load strategy returns
        strategy_returns = self.load_strategy_returns()
        
        if not strategy_returns:
            print("❌ No strategy returns available for regret calculation")
            return pd.DataFrame()
        
        # Calculate daily regret
        regret_df = self.calculate_daily_regret(strategy_returns)
        
        if regret_df.empty:
            print("❌ No regret data calculated")
            return pd.DataFrame()
        
        # Calculate cumulative and rolling metrics
        enhanced_regret_df = self.calculate_cumulative_metrics(regret_df)
        
        # Save regret data
        enhanced_regret_df.to_parquet(self.paths['regret'], index=False)
        print(f"   ✅ Saved regret data: {self.paths['regret']}")
        
        # Print regret summary
        self.print_regret_summary(enhanced_regret_df)
        
        return enhanced_regret_df
    
    def print_regret_summary(self, regret_df):
        """Print summary of regret analysis"""
        
        if regret_df.empty:
            return
        
        print(f"\n😈 REGRET SUMMARY:")
        
        # Get latest regret for each strategy
        latest_regret = regret_df.sort_values('date').groupby('strategy').tail(1)
        
        # Sort by cumulative regret (worst first)
        regret_ranking = latest_regret.sort_values('cum_regret', ascending=False)
        
        print(f"   📊 Regret Leaderboard (Worst First):")
        for _, row in regret_ranking.head(10).iterrows():
            print(f"     {row['strategy']:20} Cum: {row['cum_regret']:6.2%} "
                  f"90d: {row['regret_90d']:6.2%} DD: {row['drawdown']:6.1%} "
                  f"Penalty: {row['penalty_score']:.2f}")
        
        # Overall statistics
        total_strategies = len(latest_regret)
        avg_regret = latest_regret['cum_regret'].mean()
        max_regret = latest_regret['cum_regret'].max()
        
        print(f"\n   📈 Overall Statistics:")
        print(f"     Strategies tracked: {total_strategies}")
        print(f"     Average cumulative regret: {avg_regret:.2%}")
        print(f"     Maximum cumulative regret: {max_regret:.2%}")
        
        # High regret strategies (top 20%)
        high_regret_threshold = latest_regret['cum_regret'].quantile(0.8)
        high_regret_strategies = latest_regret[
            latest_regret['cum_regret'] >= high_regret_threshold
        ]['strategy'].tolist()
        
        if high_regret_strategies:
            print(f"   ⚠️ High regret strategies (top 20%): {', '.join(high_regret_strategies)}")
    
    def get_strategy_regret(self, strategy=None, days=None):
        """Get regret data for specific strategy or all strategies"""
        
        if not os.path.exists(self.paths['regret']):
            return pd.DataFrame()
        
        regret_df = pd.read_parquet(self.paths['regret'])
        
        if strategy:
            regret_df = regret_df[regret_df['strategy'] == strategy]
        
        if days:
            cutoff_date = datetime.now().date() - timedelta(days=days)
            regret_df = regret_df[regret_df['date'] >= cutoff_date]
        
        return regret_df
    
    def get_regret_rankings(self, metric='cum_regret', ascending=False):
        """Get strategies ranked by regret metric"""
        
        regret_df = self.get_strategy_regret()
        
        if regret_df.empty:
            return pd.DataFrame()
        
        # Get latest values for each strategy
        latest_regret = regret_df.sort_values('date').groupby('strategy').tail(1)
        
        # Rank by specified metric
        rankings = latest_regret.sort_values(metric, ascending=ascending)
        
        return rankings[['strategy', metric, 'regret_30d', 'regret_90d', 'drawdown', 'penalty_score']]

def main():
    """Main execution function"""
    
    regret_engine = StrategyRegret()
    regret_data = regret_engine.calculate_regret()
    
    return regret_data

if __name__ == "__main__":
    main()