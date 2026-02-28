#!/usr/bin/env python3
"""
Alpha Attribution Analysis

This runs the specialist-level PnL analysis to identify:
1. Per-specialist IC (Information Coefficient)
2. Per-regime PnL breakdown
3. Who made money? When?
4. Who destroyed it?

This is how real funds evolve weak alpha into strong alpha.
"""

import sys
import os
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
))

class AlphaAttributionEngine:
    """
    Professional alpha attribution analysis.
    
    This dissects performance to identify exactly where alpha comes from
    and where it gets destroyed.
    """
    
    def __init__(self):
        self.name = "Alpha Attribution Engine"
        self.version = "1.0"
        
        print(f"🔬 {self.name} initialized")
    
    def load_walk_forward_results(self, results_file: str = "sealed_results.json") -> Dict:
        """Load sealed walk-forward results for analysis"""
        
        if not os.path.exists(results_file):
            print(f"❌ Results file not found: {results_file}")
            return None
        
        try:
            with open(results_file, 'r') as f:
                data = json.load(f)
            
            if 'results' in data:
                results = data['results']
            else:
                results = data
            
            print(f"✅ Loaded results: {len(results.get('daily_nav', []))} days")
            return results
            
        except Exception as e:
            print(f"❌ Error loading results: {e}")
            return None
    
    def analyze_specialist_performance(self, results: Dict) -> Dict:
        """
        Analyze performance by specialist (Momentum, Value, Quality, Macro).
        
        This identifies which specialists are generating alpha vs bleeding capital.
        """
        
        print(f"\n🎯 SPECIALIST PERFORMANCE ANALYSIS")
        print("=" * 50)
        
        # Extract data
        daily_nav = results.get('daily_nav', [])
        specialist_allocations = results.get('specialist_allocations', [])
        daily_regime = results.get('daily_regime', [])
        
        if not all([daily_nav, specialist_allocations, daily_regime]):
            print("❌ Insufficient data for specialist analysis")
            return {}
        
        # Calculate daily returns
        daily_returns = []
        for i in range(1, len(daily_nav)):
            ret = (daily_nav[i] - daily_nav[i-1]) / daily_nav[i-1]
            daily_returns.append(ret)
        
        # Initialize specialist tracking
        specialists = ['momentum_specialist', 'value_specialist', 'quality_specialist', 'macro_specialist']
        specialist_pnl = {spec: 0.0 for spec in specialists}
        specialist_returns = {spec: [] for spec in specialists}
        specialist_allocations_history = {spec: [] for spec in specialists}
        
        # Attribution analysis
        for i, (daily_return, allocations) in enumerate(zip(daily_returns, specialist_allocations[1:])):
            for specialist in specialists:
                allocation = allocations.get(specialist, 0.0)
                
                # Attribute return proportionally to allocation
                attributed_return = daily_return * allocation
                specialist_pnl[specialist] += attributed_return
                specialist_returns[specialist].append(attributed_return)
                specialist_allocations_history[specialist].append(allocation)
        
        # Calculate specialist metrics
        specialist_analysis = {}
        
        for specialist in specialists:
            returns = specialist_returns[specialist]
            allocations = specialist_allocations_history[specialist]
            
            if not returns:
                continue
            
            # Performance metrics
            total_return = specialist_pnl[specialist]
            avg_return = np.mean(returns)
            volatility = np.std(returns)
            sharpe = avg_return / volatility * np.sqrt(252) if volatility > 0 else 0
            
            # Hit rate
            positive_days = sum(1 for r in returns if r > 0)
            hit_rate = positive_days / len(returns) if returns else 0
            
            # Average allocation
            avg_allocation = np.mean(allocations) if allocations else 0
            
            # Win/Loss analysis
            wins = [r for r in returns if r > 0]
            losses = [r for r in returns if r < 0]
            
            avg_win = np.mean(wins) if wins else 0
            avg_loss = np.mean(losses) if losses else 0
            win_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
            
            specialist_analysis[specialist] = {
                'total_pnl': total_return,
                'avg_daily_return': avg_return,
                'volatility': volatility,
                'sharpe_ratio': sharpe,
                'hit_rate': hit_rate,
                'avg_allocation': avg_allocation,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'win_loss_ratio': win_loss_ratio,
                'total_days': len(returns)
            }
        
        # Rank specialists by performance
        ranked_specialists = sorted(
            specialist_analysis.items(),
            key=lambda x: x[1]['total_pnl'],
            reverse=True
        )
        
        # Print analysis
        print(f"📊 SPECIALIST RANKINGS (by Total PnL)")
        print("-" * 50)
        
        for rank, (specialist, metrics) in enumerate(ranked_specialists, 1):
            name = specialist.replace('_specialist', '').title()
            pnl = metrics['total_pnl']
            sharpe = metrics['sharpe_ratio']
            hit_rate = metrics['hit_rate']
            avg_alloc = metrics['avg_allocation']
            
            verdict = "🏆 KEEP" if pnl > 0 else "💀 KILL" if pnl < -0.01 else "🔧 FIX"
            
            print(f"{rank}. {name:8} | PnL: {pnl:+.3f} | Sharpe: {sharpe:+.2f} | "
                  f"Hit: {hit_rate:.1%} | Alloc: {avg_alloc:.1%} | {verdict}")
        
        return {
            'specialist_analysis': specialist_analysis,
            'rankings': ranked_specialists,
            'summary': {
                'best_specialist': ranked_specialists[0][0] if ranked_specialists else None,
                'worst_specialist': ranked_specialists[-1][0] if ranked_specialists else None,
                'total_specialists': len(ranked_specialists),
                'profitable_specialists': len([s for s in specialist_analysis.values() if s['total_pnl'] > 0])
            }
        }
    
    def analyze_regime_performance(self, results: Dict) -> Dict:
        """
        Analyze performance by market regime.
        
        This identifies which regimes generate alpha vs destroy capital.
        """
        
        print(f"\n🌊 REGIME PERFORMANCE ANALYSIS")
        print("=" * 50)
        
        # Extract data
        daily_nav = results.get('daily_nav', [])
        daily_regime = results.get('daily_regime', [])
        
        if not all([daily_nav, daily_regime]):
            print("❌ Insufficient data for regime analysis")
            return {}
        
        # Calculate daily returns
        daily_returns = []
        for i in range(1, len(daily_nav)):
            ret = (daily_nav[i] - daily_nav[i-1]) / daily_nav[i-1]
            daily_returns.append(ret)
        
        # Group by regime
        regime_returns = {}
        regime_days = {}
        
        for i, (daily_return, regime) in enumerate(zip(daily_returns, daily_regime[1:])):
            if regime not in regime_returns:
                regime_returns[regime] = []
                regime_days[regime] = 0
            
            regime_returns[regime].append(daily_return)
            regime_days[regime] += 1
        
        # Calculate regime metrics
        regime_analysis = {}
        
        for regime, returns in regime_returns.items():
            if not returns:
                continue
            
            # Performance metrics
            total_return = sum(returns)
            avg_return = np.mean(returns)
            volatility = np.std(returns)
            sharpe = avg_return / volatility * np.sqrt(252) if volatility > 0 else 0
            
            # Hit rate
            positive_days = sum(1 for r in returns if r > 0)
            hit_rate = positive_days / len(returns)
            
            # Drawdown analysis
            cumulative = np.cumprod([1 + r for r in returns])
            running_max = np.maximum.accumulate(cumulative)
            drawdowns = (cumulative - running_max) / running_max
            max_drawdown = np.min(drawdowns) if len(drawdowns) > 0 else 0
            
            regime_analysis[regime] = {
                'total_pnl': total_return,
                'avg_daily_return': avg_return,
                'volatility': volatility,
                'sharpe_ratio': sharpe,
                'hit_rate': hit_rate,
                'max_drawdown': max_drawdown,
                'total_days': len(returns),
                'pct_of_period': len(returns) / len(daily_returns)
            }
        
        # Rank regimes by performance
        ranked_regimes = sorted(
            regime_analysis.items(),
            key=lambda x: x[1]['total_pnl'],
            reverse=True
        )
        
        # Print analysis
        print(f"📊 REGIME RANKINGS (by Total PnL)")
        print("-" * 50)
        
        for rank, (regime, metrics) in enumerate(ranked_regimes, 1):
            pnl = metrics['total_pnl']
            sharpe = metrics['sharpe_ratio']
            hit_rate = metrics['hit_rate']
            days = metrics['total_days']
            pct_period = metrics['pct_of_period']
            
            verdict = "🏆 ALPHA" if pnl > 0 else "💀 TOXIC" if pnl < -0.01 else "🔧 WEAK"
            
            print(f"{rank}. {regime:12} | PnL: {pnl:+.3f} | Sharpe: {sharpe:+.2f} | "
                  f"Hit: {hit_rate:.1%} | Days: {days:3d} ({pct_period:.1%}) | {verdict}")
        
        return {
            'regime_analysis': regime_analysis,
            'rankings': ranked_regimes,
            'summary': {
                'best_regime': ranked_regimes[0][0] if ranked_regimes else None,
                'worst_regime': ranked_regimes[-1][0] if ranked_regimes else None,
                'total_regimes': len(ranked_regimes),
                'profitable_regimes': len([r for r in regime_analysis.values() if r['total_pnl'] > 0])
            }
        }
    
    def analyze_temporal_patterns(self, results: Dict) -> Dict:
        """
        Analyze when alpha is generated vs destroyed.
        
        This identifies temporal patterns in performance.
        """
        
        print(f"\n⏰ TEMPORAL PATTERN ANALYSIS")
        print("=" * 50)
        
        # Extract data
        daily_nav = results.get('daily_nav', [])
        
        if not daily_nav:
            print("❌ Insufficient data for temporal analysis")
            return {}
        
        # Calculate daily returns
        daily_returns = []
        for i in range(1, len(daily_nav)):
            ret = (daily_nav[i] - daily_nav[i-1]) / daily_nav[i-1]
            daily_returns.append(ret)
        
        # Analyze by periods
        n_returns = len(daily_returns)
        
        # Split into periods
        periods = {
            'First Quarter': daily_returns[:n_returns//4],
            'Second Quarter': daily_returns[n_returns//4:n_returns//2],
            'Third Quarter': daily_returns[n_returns//2:3*n_returns//4],
            'Fourth Quarter': daily_returns[3*n_returns//4:]
        }
        
        period_analysis = {}
        
        for period_name, returns in periods.items():
            if not returns:
                continue
            
            total_return = sum(returns)
            avg_return = np.mean(returns)
            volatility = np.std(returns)
            sharpe = avg_return / volatility * np.sqrt(252) if volatility > 0 else 0
            
            period_analysis[period_name] = {
                'total_pnl': total_return,
                'avg_daily_return': avg_return,
                'volatility': volatility,
                'sharpe_ratio': sharpe,
                'total_days': len(returns)
            }
        
        # Print analysis
        print(f"📊 TEMPORAL PERFORMANCE")
        print("-" * 30)
        
        for period, metrics in period_analysis.items():
            pnl = metrics['total_pnl']
            sharpe = metrics['sharpe_ratio']
            days = metrics['total_days']
            
            print(f"{period:15} | PnL: {pnl:+.3f} | Sharpe: {sharpe:+.2f} | Days: {days}")
        
        return period_analysis
    
    def generate_attribution_report(self, results: Dict) -> Dict:
        """Generate comprehensive attribution report"""
        
        print(f"\n🔬 COMPREHENSIVE ALPHA ATTRIBUTION REPORT")
        print("=" * 80)
        
        # Run all analyses
        specialist_analysis = self.analyze_specialist_performance(results)
        regime_analysis = self.analyze_regime_performance(results)
        temporal_analysis = self.analyze_temporal_patterns(results)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            specialist_analysis, regime_analysis, temporal_analysis
        )
        
        # Compile full report
        full_report = {
            'analysis_timestamp': datetime.now().isoformat(),
            'specialist_analysis': specialist_analysis,
            'regime_analysis': regime_analysis,
            'temporal_analysis': temporal_analysis,
            'recommendations': recommendations
        }
        
        # Save report
        report_file = f"alpha_attribution_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(full_report, f, indent=2)
        
        print(f"\n💾 Report saved: {report_file}")
        
        return full_report
    
    def _generate_recommendations(self, specialist_analysis: Dict, regime_analysis: Dict, temporal_analysis: Dict) -> Dict:
        """Generate actionable recommendations based on attribution analysis"""
        
        recommendations = {
            'kill_list': [],
            'fix_list': [],
            'keep_list': [],
            'regime_actions': [],
            'structural_changes': []
        }
        
        # Specialist recommendations
        if specialist_analysis and 'rankings' in specialist_analysis:
            for specialist, metrics in specialist_analysis['rankings']:
                pnl = metrics['total_pnl']
                sharpe = metrics['sharpe_ratio']
                
                if pnl < -0.01:  # Significant loss
                    recommendations['kill_list'].append({
                        'component': specialist,
                        'reason': f"Negative PnL: {pnl:.3f}",
                        'priority': 'HIGH'
                    })
                elif pnl > 0.01:  # Significant gain
                    recommendations['keep_list'].append({
                        'component': specialist,
                        'reason': f"Positive PnL: {pnl:.3f}",
                        'priority': 'HIGH'
                    })
                else:  # Marginal performance
                    recommendations['fix_list'].append({
                        'component': specialist,
                        'reason': f"Weak performance: PnL {pnl:.3f}, Sharpe {sharpe:.2f}",
                        'priority': 'MEDIUM'
                    })
        
        # Regime recommendations
        if regime_analysis and 'rankings' in regime_analysis:
            for regime, metrics in regime_analysis['rankings']:
                pnl = metrics['total_pnl']
                
                if pnl < -0.01:
                    recommendations['regime_actions'].append({
                        'regime': regime,
                        'action': 'Reduce exposure or improve detection',
                        'reason': f"Toxic regime: PnL {pnl:.3f}"
                    })
        
        # Structural recommendations
        if specialist_analysis:
            profitable_count = specialist_analysis.get('summary', {}).get('profitable_specialists', 0)
            total_count = specialist_analysis.get('summary', {}).get('total_specialists', 0)
            
            if profitable_count < total_count / 2:
                recommendations['structural_changes'].append({
                    'change': 'Increase signal quality thresholds',
                    'reason': f'Only {profitable_count}/{total_count} specialists profitable'
                })
        
        return recommendations

def main():
    """Run alpha attribution analysis"""
    
    print("🔬 NORTHSTAR ALPHA ATTRIBUTION ANALYSIS")
    print("=" * 80)
    print("Identifying exactly where alpha comes from and where it gets destroyed.")
    print()
    
    # Initialize engine
    attribution_engine = AlphaAttributionEngine()
    
    # Load results
    results = attribution_engine.load_walk_forward_results()
    
    if not results:
        print("❌ No results to analyze. Run walk-forward validation first.")
        return
    
    # Generate comprehensive report
    report = attribution_engine.generate_attribution_report(results)
    
    # Print key findings
    print(f"\n🎯 KEY FINDINGS")
    print("=" * 40)
    
    if report['recommendations']['kill_list']:
        print(f"💀 KILL LIST:")
        for item in report['recommendations']['kill_list']:
            print(f"   • {item['component']}: {item['reason']}")
    
    if report['recommendations']['fix_list']:
        print(f"\n🔧 FIX LIST:")
        for item in report['recommendations']['fix_list']:
            print(f"   • {item['component']}: {item['reason']}")
    
    if report['recommendations']['keep_list']:
        print(f"\n🏆 KEEP LIST:")
        for item in report['recommendations']['keep_list']:
            print(f"   • {item['component']}: {item['reason']}")
    
    print(f"\n✅ Alpha attribution analysis complete.")
    print(f"This is how real funds evolve weak alpha into strong alpha.")

if __name__ == "__main__":
    main()