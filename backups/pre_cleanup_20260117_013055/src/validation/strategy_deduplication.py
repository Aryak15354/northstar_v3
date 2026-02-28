#!/usr/bin/env python3
"""
🔍 STRATEGY DEDUPLICATION ENGINE
Removes redundant strategies with high correlations

This prevents model fraud by identifying and removing strategies
that are essentially duplicates of each other.

Usage:
    from src.validation.strategy_deduplication import StrategyDeduplication
    
    dedup = StrategyDeduplication()
    dedup.remove_redundant_strategies()
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class StrategyDeduplication:
    """
    Strategy Deduplication Engine
    
    Identifies and removes strategies with high correlations
    to prevent model fraud and improve portfolio diversification.
    """
    
    def __init__(self):
        self.name = "Strategy Deduplication Engine"
        self.version = "1.0"
        
        # File paths
        self.paths = {
            'backtests': 'data/processed/backtests',
            'strategy_portfolios': 'data/processed/strategy_portfolios',
            'deduplication_log': 'data/validation/strategy_deduplication.json'
        }
        
        # Create validation directory
        os.makedirs('data/validation', exist_ok=True)
        
        # Deduplication thresholds
        self.thresholds = {
            'correlation_threshold': 0.80,  # Above this = redundant (lowered from 0.85)
            'min_strategies': 6,            # Keep at least this many (lowered from 8)
            'performance_weight': 0.7,      # Weight for performance in ranking
            'diversification_weight': 0.3   # Weight for diversification
        }
    
    def load_strategy_returns(self):
        """Load returns for all strategies"""
        
        print("📊 Loading strategy returns for correlation analysis...")
        
        strategy_returns = {}
        strategy_metrics = {}
        
        if os.path.exists(self.paths['backtests']):
            for file in os.listdir(self.paths['backtests']):
                if file.endswith('.parquet'):
                    strategy_name = file.replace('.parquet', '')
                    try:
                        df = pd.read_parquet(os.path.join(self.paths['backtests'], file))
                        if not df.empty and 'daily_return' in df.columns:
                            returns = df['daily_return']
                            
                            # Store returns
                            strategy_returns[strategy_name] = returns
                            
                            # Calculate performance metrics
                            total_return = (1 + returns).prod() - 1
                            volatility = returns.std() * np.sqrt(252)
                            sharpe = (returns.mean() * 252) / volatility if volatility > 0 else 0
                            max_dd = self.calculate_max_drawdown(returns)
                            
                            strategy_metrics[strategy_name] = {
                                'total_return': total_return,
                                'volatility': volatility,
                                'sharpe': sharpe,
                                'max_drawdown': max_dd,
                                'n_observations': len(returns)
                            }
                            
                    except Exception as e:
                        print(f"   ⚠️ Error loading {strategy_name}: {e}")
        
        print(f"   ✅ Loaded {len(strategy_returns)} strategies")
        return strategy_returns, strategy_metrics
    
    def calculate_max_drawdown(self, returns):
        """Calculate maximum drawdown"""
        equity = (1 + returns).cumprod()
        running_max = equity.expanding().max()
        drawdown = (equity / running_max) - 1
        return drawdown.min()
    
    def calculate_correlation_matrix(self, strategy_returns):
        """Calculate correlation matrix between strategies"""
        
        print("🔍 Calculating strategy correlation matrix...")
        
        # Align returns to common dates
        returns_df = pd.DataFrame(strategy_returns)
        returns_df = returns_df.fillna(0)
        
        # Calculate correlation matrix
        corr_matrix = returns_df.corr()
        
        print(f"   ✅ Correlation matrix: {len(corr_matrix)} x {len(corr_matrix)} strategies")
        
        return corr_matrix
    
    def identify_redundant_strategies(self, corr_matrix, strategy_metrics):
        """Identify redundant strategies based on correlations"""
        
        print("🎯 Identifying redundant strategies...")
        
        redundant_pairs = []
        
        # Find high correlation pairs
        for i in range(len(corr_matrix.columns)):
            for j in range(i+1, len(corr_matrix.columns)):
                strategy1 = corr_matrix.columns[i]
                strategy2 = corr_matrix.columns[j]
                correlation = abs(corr_matrix.iloc[i, j])
                
                if correlation > self.thresholds['correlation_threshold']:
                    redundant_pairs.append({
                        'strategy1': strategy1,
                        'strategy2': strategy2,
                        'correlation': correlation,
                        'sharpe1': strategy_metrics[strategy1]['sharpe'],
                        'sharpe2': strategy_metrics[strategy2]['sharpe'],
                        'return1': strategy_metrics[strategy1]['total_return'],
                        'return2': strategy_metrics[strategy2]['total_return']
                    })
        
        print(f"   🚨 Found {len(redundant_pairs)} highly correlated pairs")
        
        # Determine which strategies to remove
        strategies_to_remove = set()
        
        for pair in redundant_pairs:
            strategy1 = pair['strategy1']
            strategy2 = pair['strategy2']
            
            # Keep the better performing strategy
            if pair['sharpe1'] > pair['sharpe2']:
                strategies_to_remove.add(strategy2)
                print(f"   🗑️ Removing {strategy2} (corr: {pair['correlation']:.1%}, "
                      f"Sharpe: {pair['sharpe2']:.2f} vs {pair['sharpe1']:.2f})")
            else:
                strategies_to_remove.add(strategy1)
                print(f"   🗑️ Removing {strategy1} (corr: {pair['correlation']:.1%}, "
                      f"Sharpe: {pair['sharpe1']:.2f} vs {pair['sharpe2']:.2f})")
        
        # Ensure we keep minimum number of strategies
        remaining_strategies = len(corr_matrix.columns) - len(strategies_to_remove)
        
        if remaining_strategies < self.thresholds['min_strategies']:
            # Keep the best performing strategies
            all_strategies = list(corr_matrix.columns)
            strategy_scores = [(s, strategy_metrics[s]['sharpe']) for s in all_strategies]
            strategy_scores.sort(key=lambda x: x[1], reverse=True)
            
            # Keep top strategies
            keep_strategies = [s[0] for s in strategy_scores[:self.thresholds['min_strategies']]]
            strategies_to_remove = set(all_strategies) - set(keep_strategies)
            
            print(f"   ⚖️ Adjusted removal to keep {len(keep_strategies)} strategies")
        
        return list(strategies_to_remove), redundant_pairs
    
    def remove_strategy_files(self, strategies_to_remove):
        """Remove files for redundant strategies"""
        
        print("🗑️ Removing redundant strategy files...")
        
        removed_files = []
        
        for strategy in strategies_to_remove:
            # Remove backtest file
            backtest_file = os.path.join(self.paths['backtests'], f"{strategy}.parquet")
            if os.path.exists(backtest_file):
                os.remove(backtest_file)
                removed_files.append(backtest_file)
                print(f"   🗑️ Removed backtest: {strategy}")
            
            # Remove strategy portfolio file
            portfolio_file = os.path.join(self.paths['strategy_portfolios'], f"{strategy}.parquet")
            if os.path.exists(portfolio_file):
                os.remove(portfolio_file)
                removed_files.append(portfolio_file)
                print(f"   🗑️ Removed portfolio: {strategy}")
        
        return removed_files
    
    def update_beliefs_and_regret(self, strategies_to_remove):
        """Update beliefs and regret files to remove redundant strategies"""
        
        print("🧠 Updating beliefs and regret data...")
        
        # Update beliefs
        beliefs_file = 'data/processed/strategy_beliefs.parquet'
        if os.path.exists(beliefs_file):
            beliefs_df = pd.read_parquet(beliefs_file)
            original_count = len(beliefs_df)
            beliefs_df = beliefs_df[~beliefs_df['strategy'].isin(strategies_to_remove)]
            beliefs_df.to_parquet(beliefs_file, index=False)
            print(f"   🧠 Updated beliefs: {original_count} → {len(beliefs_df)} records")
        
        # Update regret
        regret_file = 'data/processed/strategy_regret.parquet'
        if os.path.exists(regret_file):
            regret_df = pd.read_parquet(regret_file)
            original_count = len(regret_df)
            regret_df = regret_df[~regret_df['strategy'].isin(strategies_to_remove)]
            regret_df.to_parquet(regret_file, index=False)
            print(f"   😈 Updated regret: {original_count} → {len(regret_df)} records")
    
    def remove_redundant_strategies(self):
        """Main deduplication process"""
        
        print("🔍 STRATEGY DEDUPLICATION ENGINE")
        print("=" * 60)
        
        # Load strategy data
        strategy_returns, strategy_metrics = self.load_strategy_returns()
        
        if len(strategy_returns) < 2:
            print("❌ Not enough strategies for deduplication")
            return False
        
        # Calculate correlations
        corr_matrix = self.calculate_correlation_matrix(strategy_returns)
        
        # Identify redundant strategies
        strategies_to_remove, redundant_pairs = self.identify_redundant_strategies(
            corr_matrix, strategy_metrics
        )
        
        if not strategies_to_remove:
            print("✅ No redundant strategies found - all strategies are sufficiently diverse")
            return True
        
        # Remove redundant strategy files
        removed_files = self.remove_strategy_files(strategies_to_remove)
        
        # Update beliefs and regret data
        self.update_beliefs_and_regret(strategies_to_remove)
        
        # Log deduplication results
        dedup_log = {
            'timestamp': datetime.now().isoformat(),
            'original_strategies': len(strategy_returns),
            'removed_strategies': len(strategies_to_remove),
            'remaining_strategies': len(strategy_returns) - len(strategies_to_remove),
            'strategies_removed': strategies_to_remove,
            'redundant_pairs': redundant_pairs,
            'removed_files': removed_files,
            'correlation_threshold': self.thresholds['correlation_threshold']
        }
        
        with open(self.paths['deduplication_log'], 'w') as f:
            json.dump(dedup_log, f, indent=2, default=str)
        
        # Summary
        print(f"\n🎯 DEDUPLICATION SUMMARY:")
        print(f"   📊 Original strategies: {len(strategy_returns)}")
        print(f"   🗑️ Removed strategies: {len(strategies_to_remove)}")
        print(f"   ✅ Remaining strategies: {len(strategy_returns) - len(strategies_to_remove)}")
        print(f"   📋 Removed: {', '.join(strategies_to_remove)}")
        
        return True

def main():
    """Main execution function"""
    
    dedup = StrategyDeduplication()
    success = dedup.remove_redundant_strategies()
    
    return success

if __name__ == "__main__":
    main()