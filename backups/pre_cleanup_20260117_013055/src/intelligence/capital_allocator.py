#!/usr/bin/env python3
"""
🧠 CAPITAL ALLOCATOR - BAYESIAN MODEL ALLOCATION ENGINE
Institutional-Grade Capital Allocation with Regret Minimization

This is the brain that decides which strategies get money today.
Uses Thompson Sampling and Bayesian updating to allocate capital
across competing strategies based on their skill and regime fit.

This is how Bridgewater, Citadel, and Two Sigma actually operate:
They don't pick stocks. They allocate capital to models.

Usage:
    from src.intelligence.capital_allocator import CapitalAllocator
    
    allocator = CapitalAllocator()
    allocations = allocator.allocate_capital()
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from scipy.stats import beta
import warnings
warnings.filterwarnings('ignore')

class CapitalAllocator:
    """
    Bayesian Capital Allocation Engine with Regret Minimization
    
    This system decides how to split capital across strategies using:
    1. Bayesian skill estimation (Thompson Sampling)
    2. Regime awareness
    3. Regret tracking
    4. Risk management overlays
    """
    
    def __init__(self):
        self.name = "Northstar Capital Allocator"
        self.version = "3.0"
        
        # File paths
        self.paths = {
            'strategy_performance': 'data/processed/strategy_performance',
            'backtests': 'data/processed/backtests',
            'market_state': 'data/processed/market_state.parquet',
            'strategy_beliefs': 'data/processed/strategy_beliefs.parquet',
            'strategy_regret': 'data/processed/strategy_regret.parquet',
            'capital_allocations': 'data/processed/capital_allocations.json',
            'allocation_history': 'data/processed/allocation_history.parquet'
        }
        
        # Allocation parameters
        self.params = {
            'min_allocation': 0.05,    # 5% minimum per strategy
            'max_allocation': 0.50,    # 50% maximum per strategy
            'temperature': 0.75,       # Softmax temperature (lower = more concentrated)
            'confidence_threshold': 0.4,  # Minimum skill probability
            'regret_penalty': 0.3,     # Regret penalty weight
            'lookback_days': 90,       # Days to consider for allocation
            'min_trades': 10,          # Minimum trades for skill estimation
            'kill_switch_dd': 0.20,    # 20% drawdown kills strategy
            'kill_switch_regret': 0.70  # Top 70% regret kills strategy
        }
        
        # Regime boosts
        self.regime_boosts = {
            'crisis': {
                'low_vol': 1.5, 'quality_tilt': 1.3, 'value_tilt': 1.2,
                'mom_6m': 0.7, 'mom_12m': 0.7, 'dual_momentum': 0.8
            },
            'boom': {
                'mom_6m': 1.4, 'mom_12m': 1.3, 'dual_momentum': 1.2,
                'low_vol': 0.8, 'quality_tilt': 0.9
            },
            'expansion': {
                'mom_6m': 1.2, 'quality_tilt': 1.1, 'northstar': 1.1,
                'value_tilt': 0.9
            },
            'late-expansion': {
                'quality_tilt': 1.2, 'low_vol': 1.1, 'northstar': 1.0,
                'mom_6m': 0.9, 'value_tilt': 1.1
            },
            'slowdown': {
                'value_tilt': 1.3, 'quality_tilt': 1.2, 'low_vol': 1.1,
                'mom_6m': 0.8, 'mom_12m': 0.8
            },
            'tightening': {
                'low_vol': 1.4, 'value_tilt': 1.3, 'quality_tilt': 1.2,
                'mom_6m': 0.7, 'dual_momentum': 0.8
            }
        }
    
    def load_strategy_performance(self):
        """Load recent strategy performance data"""
        
        print("📊 Loading strategy performance data...")
        
        strategy_data = {}
        
        # Load backtest results
        if os.path.exists(self.paths['backtests']):
            for file in os.listdir(self.paths['backtests']):
                if file.endswith('.parquet'):
                    strategy_name = file.replace('.parquet', '')
                    try:
                        df = pd.read_parquet(os.path.join(self.paths['backtests'], file))
                        if not df.empty:
                            # Get recent performance
                            recent_df = df.tail(self.params['lookback_days'])
                            
                            if len(recent_df) > 1:
                                returns = recent_df['daily_return']
                                equity = recent_df['equity']
                                
                                # Calculate metrics
                                total_return = equity.iloc[-1] / equity.iloc[0] - 1
                                ann_return = (equity.iloc[-1] / equity.iloc[0]) ** (252 / len(recent_df)) - 1
                                volatility = returns.std() * np.sqrt(252)
                                sharpe = ann_return / volatility if volatility > 0 else 0
                                max_dd = recent_df['drawdown'].min()
                                
                                # Win rate and other metrics
                                win_rate = (returns > 0).mean()
                                avg_exposure = recent_df['exposure'].mean()
                                avg_turnover = recent_df['turnover'].mean()
                                
                                strategy_data[strategy_name] = {
                                    'total_return': total_return,
                                    'ann_return': ann_return,
                                    'volatility': volatility,
                                    'sharpe': sharpe,
                                    'max_drawdown': max_dd,
                                    'win_rate': win_rate,
                                    'avg_exposure': avg_exposure,
                                    'avg_turnover': avg_turnover,
                                    'n_observations': len(recent_df),
                                    'last_equity': equity.iloc[-1],
                                    'recent_returns': returns.tolist()
                                }
                    except Exception as e:
                        print(f"   ⚠️ Error loading {strategy_name}: {e}")
        
        print(f"   ✅ Loaded performance for {len(strategy_data)} strategies")
        return strategy_data
    
    def load_market_regime(self):
        """Load current market regime"""
        
        try:
            if os.path.exists(self.paths['market_state']):
                market_df = pd.read_parquet(self.paths['market_state'])
                if not market_df.empty:
                    latest = market_df.iloc[-1]
                    regime = latest.get('macro_regime', 'neutral')
                    vol_regime = latest.get('vol_regime', 'mid')
                    liquidity_regime = latest.get('liquidity_regime', 'neutral')
                    risk_on_prob = latest.get('risk_on_probability', 0.5)
                    
                    print(f"   📊 Current regime: {regime} (risk-on: {risk_on_prob:.1%})")
                    
                    return {
                        'macro_regime': regime,
                        'vol_regime': vol_regime,
                        'liquidity_regime': liquidity_regime,
                        'risk_on_prob': risk_on_prob
                    }
        except Exception as e:
            print(f"   ⚠️ Could not load market regime: {e}")
        
        return {
            'macro_regime': 'neutral',
            'vol_regime': 'mid',
            'liquidity_regime': 'neutral',
            'risk_on_prob': 0.5
        }
    
    def load_strategy_beliefs(self):
        """Load strategy beliefs from the beliefs engine"""
        
        print("🧠 Loading strategy beliefs...")
        
        beliefs = {}
        beliefs_file = 'data/processed/strategy_beliefs.parquet'
        
        if os.path.exists(beliefs_file):
            try:
                beliefs_df = pd.read_parquet(beliefs_file)
                # Get latest beliefs for each strategy
                latest_beliefs = beliefs_df.sort_values('date').groupby('strategy').tail(1)
                
                for _, row in latest_beliefs.iterrows():
                    beliefs[row['strategy']] = {
                        'skill_prob': row['skill_prob'],
                        'confidence': row['confidence'],
                        'effective_skill': row['effective_skill'],
                        'regime_fit': row['regime_fit'],
                        'status': row['status'],
                        'sharpe': row['sharpe'],
                        'alpha': row['alpha'],
                        'beta': row['beta']
                    }
                
                print(f"   ✅ Loaded beliefs for {len(beliefs)} strategies")
                
            except Exception as e:
                print(f"   ⚠️ Error loading beliefs: {e}")
        
        return beliefs
    
    def load_strategy_regret(self):
        """Load strategy regret from the regret engine"""
        
        print("😈 Loading strategy regret...")
        
        regret = {}
        regret_file = 'data/processed/strategy_regret.parquet'
        
        if os.path.exists(regret_file):
            try:
                regret_df = pd.read_parquet(regret_file)
                # Get latest regret for each strategy
                latest_regret = regret_df.sort_values('date').groupby('strategy').tail(1)
                
                for _, row in latest_regret.iterrows():
                    regret[row['strategy']] = {
                        'cum_regret': row['cum_regret'],
                        'regret_30d': row['regret_30d'],
                        'regret_90d': row['regret_90d'],
                        'normalized_regret': row['normalized_regret'],
                        'penalty_score': row['penalty_score'],
                        'drawdown': row['drawdown']
                    }
                
                print(f"   ✅ Loaded regret for {len(regret)} strategies")
                
            except Exception as e:
                print(f"   ⚠️ Error loading regret: {e}")
        
        return regret
    
    def calculate_regret(self, strategy_data):
        """Calculate and update regret for each strategy"""
        
        print("😈 Calculating strategy regret...")
        
        # Load existing regret or initialize
        if os.path.exists(self.paths['strategy_regret']):
            regret_df = pd.read_parquet(self.paths['strategy_regret'])
            regret = regret_df.set_index('strategy')['cumulative_regret'].to_dict()
        else:
            regret = {}
        
        # Find best performer each day
        all_returns = {}
        max_length = 0
        
        for strategy, data in strategy_data.items():
            returns = data.get('recent_returns', [])
            if returns:
                all_returns[strategy] = returns
                max_length = max(max_length, len(returns))
        
        if not all_returns:
            return regret
        
        # Calculate daily regret
        for i in range(max_length):
            daily_returns = {}
            for strategy, returns in all_returns.items():
                if i < len(returns):
                    daily_returns[strategy] = returns[i]
            
            if daily_returns:
                best_return = max(daily_returns.values())
                
                for strategy, return_val in daily_returns.items():
                    if strategy not in regret:
                        regret[strategy] = 0.0
                    regret[strategy] += max(0, best_return - return_val)
        
        # Save regret
        regret_df = pd.DataFrame(list(regret.items()), columns=['strategy', 'cumulative_regret'])
        regret_df.to_parquet(self.paths['strategy_regret'], index=False)
        
        print(f"   ✅ Updated regret for {len(regret)} strategies")
        return regret
    
    def calculate_health_scores(self, strategy_data, beliefs, regret, regime):
        """Calculate comprehensive health scores using beliefs and regret"""
        
        print("⚖️ Calculating strategy health scores with beliefs and regret...")
        
        health_scores = {}
        
        for strategy, data in strategy_data.items():
            # Get beliefs data
            belief_data = beliefs.get(strategy, {})
            regret_data = regret.get(strategy, {})
            
            # Skip if strategy is not ACTIVE or FADING
            if belief_data.get('status') not in ['ACTIVE', 'FADING']:
                # But don't completely kill strategies with good Sharpe ratios
                sharpe = data.get('sharpe', 0)
                if sharpe > 1.0:  # Give high-Sharpe strategies a chance
                    print(f"   🔄 Rescuing high-Sharpe strategy: {strategy} (Sharpe: {sharpe:.2f})")
                    # Override status for allocation - continue processing this strategy
                    belief_data = dict(belief_data)
                    belief_data['status'] = 'FADING'
                    # Don't skip - let it continue to health calculation
                else:
                    health_scores[strategy] = {
                        'health_score': -999,  # Kill non-active strategies
                        'effective_skill': 0,
                        'regret_penalty': 1.0,
                        'status': belief_data.get('status', 'UNKNOWN'),
                        'alive': False
                    }
                    continue
            
            # Core belief metrics
            effective_skill = belief_data.get('effective_skill', 0.1)
            skill_prob = belief_data.get('skill_prob', 0.5)
            confidence = belief_data.get('confidence', 0.1)
            regime_fit = belief_data.get('regime_fit', 1.0)
            
            # Regret penalties
            normalized_regret = regret_data.get('normalized_regret', 0.5)
            penalty_score = regret_data.get('penalty_score', 0.5)
            drawdown = abs(regret_data.get('drawdown', 0))
            
            # Performance metrics
            sharpe = data.get('sharpe', 0)
            ann_return = data.get('ann_return', 0)
            
            # Calculate final score using beliefs + regret
            final_score = (
                effective_skill -
                0.3 * normalized_regret -
                0.2 * drawdown
            )
            
            # Apply regime boost
            current_regime = regime.get('macro_regime', 'neutral')
            regime_boost = self.regime_boosts.get(current_regime, {}).get(strategy, 1.0)
            final_score *= regime_boost
            
            # Determine if strategy is alive (more lenient criteria)
            is_alive = (
                final_score > -5.0 or  # Not completely terrible
                sharpe > 1.0 or        # Good Sharpe ratio
                effective_skill > 0.1   # Some skill detected
            )

            health_scores[strategy] = {
                'health_score': final_score,
                'effective_skill': effective_skill,
                'skill_prob': skill_prob,
                'confidence': confidence,
                'regime_fit': regime_fit,
                'normalized_regret': normalized_regret,
                'penalty_score': penalty_score,
                'regime_boost': regime_boost,
                'sharpe': sharpe,
                'ann_return': ann_return,
                'drawdown': drawdown,
                'status': belief_data.get('status', 'ACTIVE'),
                'alive': is_alive  # Use the calculated alive status
            }
        
        print(f"   ✅ Calculated health scores for {len(health_scores)} strategies")
        
        # Show belief-based filtering
        active_count = sum(1 for h in health_scores.values() if h['status'] == 'ACTIVE')
        alive_count = sum(1 for h in health_scores.values() if h['alive'])
        
        print(f"   📊 Active strategies: {active_count}")
        print(f"   📊 Alive strategies: {alive_count}")
        
        return health_scores
    
    def allocate_capital(self, health_scores):
        """Allocate capital using Thompson Sampling and softmax"""
        
        print("🎯 Allocating capital across strategies...")
        
        # Filter alive strategies
        alive_strategies = {k: v for k, v in health_scores.items() if v['alive']}
        
        if not alive_strategies:
            print("   ⚠️ No strategies alive! Using fallback allocation...")
            
            # Fallback: allocate to strategies with best raw performance
            fallback_strategies = {}
            for strategy, data in health_scores.items():
                if data.get('sharpe', 0) > 0.5:  # Positive Sharpe strategies
                    fallback_strategies[strategy] = data
            
            if fallback_strategies:
                print(f"   🔄 Using {len(fallback_strategies)} fallback strategies")
                alive_strategies = fallback_strategies
            else:
                # Ultimate fallback: equal weight top 3 by Sharpe
                sorted_by_sharpe = sorted(health_scores.items(), 
                                        key=lambda x: x[1].get('sharpe', -999), reverse=True)
                top_3 = dict(sorted_by_sharpe[:3])
                
                equal_weight = 1.0 / len(top_3)
                allocations = {k: equal_weight for k in top_3.keys()}
                
                print(f"   🆘 Emergency allocation: equal weight to top 3 strategies")
                return allocations
        
        # Thompson Sampling: sample from Beta distributions
        sampled_scores = {}
        for strategy, data in alive_strategies.items():
            # Sample skill probability with fallback
            skill_prob = data.get('skill_prob', 0.5)
            alpha = max(1, skill_prob * 100)
            beta_param = max(1, (1 - skill_prob) * 100)
            sampled_skill = np.random.beta(alpha, beta_param)
            
            # Combine with health score
            health_score = data.get('health_score', 0)
            sampled_scores[strategy] = max(0.01, health_score * sampled_skill)  # Ensure positive
        
        # Softmax allocation
        scores = np.array(list(sampled_scores.values()))
        exp_scores = np.exp(scores / self.params['temperature'])
        raw_allocations = exp_scores / exp_scores.sum()
        
        # Apply constraints
        allocations = {}
        for i, strategy in enumerate(sampled_scores.keys()):
            alloc = raw_allocations[i]
            
            # Apply min/max constraints
            alloc = max(self.params['min_allocation'], alloc)
            alloc = min(self.params['max_allocation'], alloc)
            
            allocations[strategy] = alloc
        
        # Renormalize
        total_alloc = sum(allocations.values())
        if total_alloc > 0:
            allocations = {k: v / total_alloc for k, v in allocations.items()}
        
        print(f"   ✅ Allocated capital across {len(allocations)} strategies")
        return allocations
    
    def save_allocations(self, allocations, regime, health_scores):
        """Save capital allocations and history"""
        
        timestamp = datetime.now()
        
        # Current allocation
        allocation_data = {
            'timestamp': timestamp.isoformat(),
            'date': timestamp.date().isoformat(),
            'regime': regime,
            'allocations': allocations,
            'strategy_health': {k: v['health_score'] for k, v in health_scores.items()},
            'total_strategies': len(allocations),
            'alive_strategies': sum(1 for v in health_scores.values() if v['alive'])
        }
        
        # Save current allocations
        with open(self.paths['capital_allocations'], 'w') as f:
            json.dump(allocation_data, f, indent=2, default=str)
        
        # Update allocation history
        history_row = {
            'date': timestamp.date(),
            'regime': regime.get('macro_regime', 'neutral'),
            **allocations
        }
        
        if os.path.exists(self.paths['allocation_history']):
            history_df = pd.read_parquet(self.paths['allocation_history'])
            history_df = pd.concat([history_df, pd.DataFrame([history_row])], ignore_index=True)
        else:
            history_df = pd.DataFrame([history_row])
        
        history_df.to_parquet(self.paths['allocation_history'], index=False)
        
        print(f"   ✅ Saved allocations: {self.paths['capital_allocations']}")
    
    def run_allocation(self):
        """Main allocation process with beliefs and regret integration"""
        
        print("🧠 CAPITAL ALLOCATOR - BAYESIAN MODEL ALLOCATION")
        print("=" * 60)
        
        # Load data
        strategy_data = self.load_strategy_performance()
        regime = self.load_market_regime()
        
        if not strategy_data:
            print("❌ No strategy performance data available")
            return {}
        
        # Load beliefs and regret (NEW!)
        beliefs = self.load_strategy_beliefs()
        regret = self.load_strategy_regret()
        
        # Calculate health scores using beliefs and regret
        health_scores = self.calculate_health_scores(strategy_data, beliefs, regret, regime)
        
        # Allocate capital
        allocations = self.allocate_capital(health_scores)
        
        # Save results
        if allocations:
            self.save_allocations(allocations, regime, health_scores)
            
            # Print enhanced summary
            print(f"\n📊 ENHANCED CAPITAL ALLOCATION SUMMARY")
            print(f"   Regime: {regime.get('macro_regime', 'neutral')}")
            print(f"   Active Strategies: {len(allocations)}")
            print(f"\n   Top Allocations (with beliefs):")
            
            sorted_allocs = sorted(allocations.items(), key=lambda x: x[1], reverse=True)
            for strategy, allocation in sorted_allocs[:5]:
                health = health_scores.get(strategy, {})
                skill = health.get('skill_prob', 0)
                regret = health.get('normalized_regret', 0)
                status = health.get('status', 'UNKNOWN')
                
                print(f"     {strategy}: {allocation:.1%} "
                      f"(skill: {skill:.1%}, regret: {regret:.1%}, {status})")
        
        return allocations

def main():
    """Main execution function"""
    
    allocator = CapitalAllocator()
    allocations = allocator.run_allocation()
    
    return allocations

if __name__ == "__main__":
    main()