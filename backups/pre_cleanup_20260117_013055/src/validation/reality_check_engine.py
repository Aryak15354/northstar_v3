#!/usr/bin/env python3
"""
🔍 REALITY CHECK ENGINE - THE 12 CRITICAL CONSTRAINTS
The difference between research and production-ready trading systems

These are the constraints that separate academic backtests from real money management.
Every constraint must pass before a strategy can trade live capital.

Usage:
    from src.validation.reality_check_engine import RealityCheckEngine
    
    reality_check = RealityCheckEngine()
    results = reality_check.run_full_validation(backtest_results, market_data)
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import warnings
warnings.filterwarnings('ignore')

# Import existing V3 components for integration
from src.validation.data_integrity import DataIntegrityEngine
from src.execution.enhanced_transaction_cost_model import EnhancedTransactionCostModel
from src.validation.universe_manager import UniverseManager

class RealityCheckEngine(DataIntegrityEngine):
    """
    Reality Check Engine - The 12 Critical Constraints
    
    Implements the brutal reality checks that every strategy must pass:
    
    1. Survivorship Bias Elimination
    2. Transaction Cost Reality
    3. Liquidity Constraint Enforcement
    4. Market Impact Modeling
    5. Regime Change Robustness
    6. Crisis Period Performance
    7. Capacity Constraint Analysis
    8. Correlation Breakdown Detection
    9. Data Snooping Prevention
    10. Out-of-Sample Validation
    11. Walk-Forward Stability
    12. Economic Intuition Alignment
    """
    
    def __init__(self):
        super().__init__()
        self.name = "Reality Check Engine"
        self.version = "1.0"
        
        # Initialize integrated V3 components
        self.transaction_cost_model = EnhancedTransactionCostModel()
        self.universe_manager = UniverseManager()
        
        # Critical constraint thresholds (fund-grade standards)
        self.constraints = {
            'survivorship_bias_max': 0.02,      # Max 2% performance bias from survivorship
            'transaction_cost_max': 0.005,      # Max 50 bps per trade
            'liquidity_min_adv': 0.05,          # Max 5% of ADV per position
            'market_impact_max': 0.01,          # Max 100 bps market impact
            'regime_drawdown_max': 0.15,        # Max 15% drawdown in any regime
            'crisis_performance_min': -0.25,    # Max 25% loss during crisis
            'capacity_utilization_max': 0.80,   # Max 80% capacity utilization
            'correlation_breakdown_max': 0.30,  # Max 30% correlation breakdown
            'data_snooping_trials_max': 100,    # Max 100 parameter combinations tested
            'out_of_sample_min': 0.30,          # Min 30% out-of-sample data
            'walk_forward_stability_min': 0.70, # Min 70% of periods must be profitable
            'economic_intuition_score_min': 0.60 # Min 60% economic intuition score
        }
        
        # Enhanced file paths
        self.paths.update({
            'validation_results': 'data/validation/reality_check_results.json',
            'constraint_history': 'data/validation/constraint_history.parquet',
            'failure_analysis': 'data/validation/failure_analysis.json',
            'crisis_periods': 'data/validation/crisis_periods.json',
            'regime_analysis': 'data/validation/regime_analysis.parquet'
        })
        
        # Create validation directory
        os.makedirs('data/validation', exist_ok=True)
        
        print(f"🔍 {self.name} v{self.version} initialized")
        print(f"💡 Integrated with V3 components: Transaction Cost Model, Universe Manager")
    
    def run_full_validation(self, backtest_results: Dict, validation_data: Dict) -> Dict[str, any]:
        """
        Run complete reality check validation with all 12 constraints
        
        This is the main entry point that validates a strategy against all
        12 critical constraints that separate research from production.
        """
        
        print(f"🔍 {self.name} - Running Full Validation")
        print("=" * 60)
        
        validation_timestamp = datetime.now()
        constraint_results = []
        
        # Run all 12 constraints
        constraints = [
            ('Survivorship Bias Elimination', self.constraint_1_survivorship_bias_elimination),
            ('Transaction Cost Reality', self.constraint_2_transaction_cost_reality),
            ('Liquidity Constraint Enforcement', self.constraint_3_liquidity_constraint_enforcement),
            ('Market Impact Modeling', self.constraint_4_market_impact_modeling),
            ('Regime Change Robustness', self.constraint_5_regime_change_robustness),
            ('Crisis Period Performance', self.constraint_6_crisis_period_performance),
            ('Capacity Constraint Analysis', self.constraint_7_capacity_constraint_analysis),
            ('Correlation Breakdown Detection', self.constraint_8_correlation_breakdown_detection),
            ('Data Snooping Prevention', self.constraint_9_data_snooping_prevention),
            ('Out-of-Sample Validation', self.constraint_10_out_of_sample_validation),
            ('Walk-Forward Stability', self.constraint_11_walk_forward_stability),
            ('Economic Intuition Alignment', self.constraint_12_economic_intuition_alignment)
        ]
        
        for constraint_name, constraint_method in constraints:
            print(f"\n🧪 Testing: {constraint_name}")
            
            try:
                result = constraint_method(backtest_results, validation_data)
                result['constraint_name'] = constraint_name
                constraint_results.append(result)
                
                status = "✅ PASS" if result['passed'] else "❌ FAIL"
                print(f"   {status} - {result['message']}")
                
            except Exception as e:
                print(f"   ❌ ERROR - {constraint_name}: {e}")
                constraint_results.append({
                    'constraint_name': constraint_name,
                    'passed': False,
                    'severity': 'CRITICAL',
                    'message': f"Constraint execution failed: {e}",
                    'value': None,
                    'threshold': None
                })
        
        # Calculate overall results
        passed_constraints = [r for r in constraint_results if r['passed']]
        failed_constraints = [r for r in constraint_results if not r['passed']]
        overall_pass_rate = len(passed_constraints) / len(constraint_results)
        
        # Determine validation status
        critical_failures = [r for r in failed_constraints if r['severity'] == 'CRITICAL']
        if critical_failures:
            validation_status = 'FAILED'
        elif len(failed_constraints) > 6:  # More than half failed
            validation_status = 'FAILED'
        elif len(failed_constraints) > 3:  # Some failures
            validation_status = 'WARNING'
        else:
            validation_status = 'PASSED'
        
        # Generate recommendations
        recommendations = self._generate_recommendations(failed_constraints)
        
        # Compile final results
        validation_results = {
            'validation_timestamp': validation_timestamp,
            'validation_status': validation_status,
            'overall_pass_rate': overall_pass_rate,
            'total_constraints': len(constraint_results),
            'passed_constraints': len(passed_constraints),
            'failed_constraints': len(failed_constraints),
            'critical_failures': len(critical_failures),
            'constraint_results': constraint_results,
            'recommendations': recommendations,
            'backtest_summary': backtest_results,
            'validation_config': self.constraints
        }
        
        # Save results
        self._save_validation_results(validation_results)
        
        # Print summary
        print(f"\n📊 VALIDATION SUMMARY:")
        print(f"   Status: {validation_status}")
        print(f"   Pass Rate: {overall_pass_rate:.1%}")
        print(f"   Passed: {len(passed_constraints)}/12")
        print(f"   Failed: {len(failed_constraints)}/12")
        print(f"   Critical: {len(critical_failures)}/12")
        
        if recommendations:
            print(f"\n💡 RECOMMENDATIONS:")
            for i, rec in enumerate(recommendations[:5], 1):
                print(f"   {i}. {rec}")
        
        return validation_results
    
    def constraint_1_survivorship_bias_elimination(self, backtest_results: Dict, validation_data: Dict) -> Dict[str, any]:
        """
        Constraint 1: Survivorship Bias Elimination
        
        Validates that the backtest includes delisted stocks and properly
        accounts for the performance impact of companies that failed.
        """
        
        universe_data = validation_data.get('universe_data', {})
        delisted_stocks = universe_data.get('delisted_stocks', [])
        total_stocks = universe_data.get('total_stocks', 100)
        
        # Calculate survivorship bias using UniverseManager
        if hasattr(self, 'universe_manager'):
            bias_analysis = self.universe_manager.calculate_survivorship_bias_impact(
                '2020-01-01', '2023-12-31', total_stocks
            )
            bias_percentage = bias_analysis['bias_percentage']
        else:
            # Fallback calculation
            delisting_rate = len(delisted_stocks) / total_stocks
            bias_percentage = delisting_rate * 0.5  # Assume 50% average loss on delisting
        
        # Check against threshold
        threshold = self.constraints['survivorship_bias_max']
        passed = bool(bias_percentage <= threshold)
        
        severity = 'CRITICAL' if bias_percentage > threshold * 2 else 'HIGH' if not passed else 'PASS'
        
        return {
            'passed': passed,
            'severity': severity,
            'value': bias_percentage,
            'threshold': threshold,
            'message': f"Survivorship bias: {bias_percentage:.2%} (threshold: {threshold:.2%})",
            'details': {
                'delisted_stocks_count': len(delisted_stocks),
                'total_universe_size': total_stocks,
                'delisting_rate': len(delisted_stocks) / total_stocks,
                'estimated_performance_impact': bias_percentage
            }
        }
    
    def constraint_2_transaction_cost_reality(self, backtest_results: Dict, validation_data: Dict) -> Dict[str, any]:
        """
        Constraint 2: Transaction Cost Reality
        
        Validates that realistic transaction costs are applied, including
        brokerage, taxes, slippage, and market impact.
        """
        
        trading_data = validation_data.get('trading_data', {})
        total_trades = trading_data.get('total_trades', 0)
        total_volume = trading_data.get('total_volume', 0)
        turnover_rate = trading_data.get('turnover_rate', 1.0)
        
        # Calculate transaction cost using EnhancedTransactionCostModel
        if total_volume > 0 and total_trades > 0:
            avg_trade_size = total_volume / total_trades
            
            # Use integrated transaction cost model
            sample_cost = self.transaction_cost_model.calculate_total_cost(
                'SAMPLE.NS', 1000, avg_trade_size / 1000,
                {'volatility': 0.20, 'vix': 25, 'market_stress': 0.3}
            )
            
            estimated_cost_bps = sample_cost['total_cost_bps']
            annual_cost_impact = estimated_cost_bps * turnover_rate / 10000
        else:
            # Fallback estimation
            estimated_cost_bps = 25  # 25 bps default
            annual_cost_impact = 0.0025 * turnover_rate
        
        # Check against threshold
        threshold = self.constraints['transaction_cost_max']
        passed = bool(annual_cost_impact <= threshold)
        
        severity = 'CRITICAL' if annual_cost_impact > threshold * 2 else 'HIGH' if not passed else 'PASS'
        
        return {
            'passed': passed,
            'severity': severity,
            'value': annual_cost_impact,
            'threshold': threshold,
            'message': f"Transaction cost impact: {annual_cost_impact:.3f} (threshold: {threshold:.3f})",
            'details': {
                'estimated_cost_bps': estimated_cost_bps,
                'turnover_rate': turnover_rate,
                'total_trades': total_trades,
                'avg_trade_size': total_volume / max(1, total_trades)
            }
        }
    
    def constraint_3_liquidity_constraint_enforcement(self, backtest_results: Dict, validation_data: Dict) -> Dict[str, any]:
        """
        Constraint 3: Liquidity Constraint Enforcement
        
        Validates that position sizes respect liquidity constraints and
        don't exceed reasonable percentages of average daily volume.
        """
        
        position_data = validation_data.get('position_data', {})
        positions = position_data.get('positions', {})
        adv_data = position_data.get('adv_data', {})
        
        liquidity_violations = []
        max_adv_percentage = 0.0
        
        for symbol, position_size in positions.items():
            if symbol in adv_data:
                adv = adv_data[symbol]
                adv_percentage = abs(position_size) / adv
                
                max_adv_percentage = max(max_adv_percentage, adv_percentage)
                
                if adv_percentage > self.constraints['liquidity_min_adv']:
                    liquidity_violations.append({
                        'symbol': symbol,
                        'position_size': position_size,
                        'adv': adv,
                        'adv_percentage': adv_percentage
                    })
        
        # Check against threshold
        threshold = self.constraints['liquidity_min_adv']
        passed = bool(max_adv_percentage <= threshold)
        
        severity = 'CRITICAL' if max_adv_percentage > threshold * 2 else 'HIGH' if not passed else 'PASS'
        
        return {
            'passed': passed,
            'severity': severity,
            'value': max_adv_percentage,
            'threshold': threshold,
            'message': f"Max ADV usage: {max_adv_percentage:.2%} (threshold: {threshold:.2%})",
            'details': {
                'liquidity_violations': liquidity_violations,
                'positions_checked': len(positions),
                'violations_count': len(liquidity_violations)
            }
        }
    
    def constraint_4_market_impact_modeling(self, backtest_results: Dict, validation_data: Dict) -> Dict[str, any]:
        """
        Constraint 4: Market Impact Modeling
        
        Validates that market impact costs are properly modeled for large trades
        and that the strategy accounts for price movement due to trading.
        """
        
        execution_data = validation_data.get('execution_data', {})
        large_trades = execution_data.get('large_trades', [])
        execution_shortfall = execution_data.get('execution_shortfall', 0.0)
        
        max_market_impact = 0.0
        impact_violations = []
        
        for trade in large_trades:
            trade_size = trade.get('size', 0)
            market_cap = trade.get('market_cap', 1_000_000_000)
            
            # Calculate market impact as percentage of market cap
            market_impact = trade_size / market_cap
            max_market_impact = max(max_market_impact, market_impact)
            
            if market_impact > self.constraints['market_impact_max']:
                impact_violations.append({
                    'trade_size': trade_size,
                    'market_cap': market_cap,
                    'market_impact': market_impact,
                    'symbol': trade.get('symbol', 'UNKNOWN')
                })
        
        # Also consider execution shortfall as proxy for market impact
        total_impact = max(max_market_impact, execution_shortfall)
        
        # Check against threshold
        threshold = self.constraints['market_impact_max']
        passed = bool(total_impact <= threshold)
        
        severity = 'CRITICAL' if total_impact > threshold * 2 else 'HIGH' if not passed else 'PASS'
        
        return {
            'passed': passed,
            'severity': severity,
            'value': total_impact,
            'threshold': threshold,
            'message': f"Max market impact: {total_impact:.3f} (threshold: {threshold:.3f})",
            'details': {
                'max_trade_impact': max_market_impact,
                'execution_shortfall': execution_shortfall,
                'large_trades_count': len(large_trades),
                'impact_violations': impact_violations
            }
        }
    
    def constraint_5_regime_change_robustness(self, backtest_results: Dict, validation_data: Dict) -> Dict[str, any]:
        """
        Constraint 5: Regime Change Robustness
        
        Validates that the strategy performs reasonably across different
        market regimes and adapts to changing conditions.
        """
        
        regime_data = validation_data.get('regime_data', {})
        regime_returns = regime_data.get('regime_returns', {})
        
        regime_performance = {}
        worst_regime_drawdown = 0.0
        
        for regime, returns in regime_returns.items():
            if returns:
                regime_return = np.mean(returns)
                regime_volatility = np.std(returns)
                regime_sharpe = regime_return / max(regime_volatility, 0.01)
                
                # Calculate maximum drawdown in regime
                cumulative = np.cumprod(1 + np.array(returns))
                running_max = np.maximum.accumulate(cumulative)
                drawdown = (cumulative - running_max) / running_max
                max_drawdown = abs(np.min(drawdown))
                
                worst_regime_drawdown = max(worst_regime_drawdown, max_drawdown)
                
                regime_performance[regime] = {
                    'return': regime_return,
                    'volatility': regime_volatility,
                    'sharpe': regime_sharpe,
                    'max_drawdown': max_drawdown
                }
        
        # Check against threshold
        threshold = self.constraints['regime_drawdown_max']
        passed = bool(worst_regime_drawdown <= threshold)
        
        severity = 'CRITICAL' if worst_regime_drawdown > threshold * 1.5 else 'HIGH' if not passed else 'PASS'
        
        return {
            'passed': passed,
            'severity': severity,
            'value': worst_regime_drawdown,
            'threshold': threshold,
            'message': f"Worst regime drawdown: {worst_regime_drawdown:.2%} (threshold: {threshold:.2%})",
            'details': {
                'regime_performance': regime_performance,
                'regimes_tested': len(regime_returns),
                'regime_transitions': regime_data.get('regime_transitions', 0)
            }
        }
    
    def constraint_6_crisis_period_performance(self, backtest_results: Dict, validation_data: Dict) -> Dict[str, any]:
        """
        Constraint 6: Crisis Period Performance
        
        Validates that the strategy survives major market crises without
        catastrophic losses that would force fund closure.
        """
        
        crisis_data = validation_data.get('crisis_data', {})
        crisis_periods = crisis_data.get('crisis_periods', [])
        
        worst_crisis_performance = 0.0
        crisis_performance = []
        
        for crisis in crisis_periods:
            crisis_return = crisis.get('return', 0.0)
            crisis_duration = crisis.get('duration', 30)
            crisis_name = crisis.get('name', 'Unknown Crisis')
            
            worst_crisis_performance = min(worst_crisis_performance, crisis_return)
            
            crisis_performance.append({
                'name': crisis_name,
                'return': crisis_return,
                'duration': crisis_duration,
                'annualized_return': crisis_return * (365 / crisis_duration)
            })
        
        # Check against threshold
        threshold = self.constraints['crisis_performance_min']
        passed = bool(worst_crisis_performance >= threshold)
        
        severity = 'CRITICAL' if worst_crisis_performance < threshold * 2 else 'HIGH' if not passed else 'PASS'
        
        return {
            'passed': passed,
            'severity': severity,
            'value': worst_crisis_performance,
            'threshold': threshold,
            'message': f"Worst crisis performance: {worst_crisis_performance:.2%} (threshold: {threshold:.2%})",
            'details': {
                'crisis_performance': crisis_performance,
                'crisis_periods_tested': len(crisis_periods),
                'recovery_times': crisis_data.get('recovery_times', [])
            }
        }
    
    def constraint_7_capacity_constraint_analysis(self, backtest_results: Dict, validation_data: Dict) -> Dict[str, any]:
        """
        Constraint 7: Capacity Constraint Analysis
        
        Validates that the strategy can scale to target AUM without
        significantly degrading performance due to capacity constraints.
        """
        
        capacity_data = validation_data.get('capacity_data', {})
        target_aum = capacity_data.get('target_aum', 100_000_000)
        market_capacity = capacity_data.get('market_capacity', 500_000_000)
        capacity_utilization_history = capacity_data.get('capacity_utilization_history', [0.5])
        
        # Calculate current capacity utilization
        current_utilization = target_aum / market_capacity
        max_historical_utilization = max(capacity_utilization_history) if capacity_utilization_history else current_utilization
        
        # Check against threshold
        threshold = self.constraints['capacity_utilization_max']
        passed = bool(max_historical_utilization <= threshold)
        
        severity = 'CRITICAL' if max_historical_utilization > threshold * 1.2 else 'HIGH' if not passed else 'PASS'
        
        return {
            'passed': passed,
            'severity': severity,
            'value': max_historical_utilization,
            'threshold': threshold,
            'message': f"Max capacity utilization: {max_historical_utilization:.2%} (threshold: {threshold:.2%})",
            'details': {
                'target_aum': target_aum,
                'market_capacity': market_capacity,
                'current_utilization': current_utilization,
                'utilization_history': capacity_utilization_history,
                'liquidity_buffer': capacity_data.get('liquidity_buffer', 0.2)
            }
        }
    
    def constraint_8_correlation_breakdown_detection(self, backtest_results: Dict, validation_data: Dict) -> Dict[str, any]:
        """
        Constraint 8: Correlation Breakdown Detection
        
        Validates that the strategy detects and adapts to correlation breakdowns
        that can cause diversification to fail during stress periods.
        """
        
        correlation_data = validation_data.get('correlation_data', {})
        historical_correlations = correlation_data.get('historical_correlations', [0.7])
        correlation_breakdown_events = correlation_data.get('correlation_breakdown_events', 0)
        max_correlation_change = correlation_data.get('max_correlation_change', 0.1)
        
        # Calculate correlation stability
        if len(historical_correlations) > 1:
            correlation_volatility = np.std(historical_correlations)
            correlation_range = max(historical_correlations) - min(historical_correlations)
        else:
            correlation_volatility = 0.0
            correlation_range = 0.0
        
        # Use maximum correlation change as primary metric
        breakdown_severity = max(max_correlation_change, correlation_range)
        
        # Check against threshold
        threshold = self.constraints['correlation_breakdown_max']
        passed = bool(breakdown_severity <= threshold)
        
        severity = 'CRITICAL' if breakdown_severity > threshold * 1.5 else 'HIGH' if not passed else 'PASS'
        
        return {
            'passed': passed,
            'severity': severity,
            'value': breakdown_severity,
            'threshold': threshold,
            'message': f"Max correlation breakdown: {breakdown_severity:.2%} (threshold: {threshold:.2%})",
            'details': {
                'correlation_volatility': correlation_volatility,
                'correlation_range': correlation_range,
                'breakdown_events': correlation_breakdown_events,
                'stability_score': correlation_data.get('correlation_stability_score', 0.8),
                'historical_correlations': historical_correlations
            }
        }
    
    def constraint_9_data_snooping_prevention(self, backtest_results: Dict, validation_data: Dict) -> Dict[str, any]:
        """
        Constraint 9: Data Snooping Prevention
        
        Validates that the strategy hasn't been over-optimized through
        excessive parameter testing that would lead to false discoveries.
        """
        
        optimization_data = validation_data.get('optimization_data', {})
        parameter_trials = optimization_data.get('parameter_trials', 10)
        optimization_periods = optimization_data.get('optimization_periods', 1)
        overfitting_score = optimization_data.get('overfitting_score', 0.1)
        
        # Calculate effective number of trials (Bonferroni-style adjustment)
        effective_trials = parameter_trials * optimization_periods
        
        # Check against threshold
        threshold = self.constraints['data_snooping_trials_max']
        passed = bool(effective_trials <= threshold)
        
        # Also check overfitting score if available
        if overfitting_score > 0.3:  # High overfitting risk
            passed = False
        
        severity = 'CRITICAL' if effective_trials > threshold * 2 else 'HIGH' if not passed else 'PASS'
        
        return {
            'passed': passed,
            'severity': severity,
            'value': effective_trials,
            'threshold': threshold,
            'message': f"Effective parameter trials: {effective_trials} (threshold: {threshold})",
            'details': {
                'parameter_trials': parameter_trials,
                'optimization_periods': optimization_periods,
                'overfitting_score': overfitting_score,
                'parameters_tested': optimization_data.get('parameters_tested', []),
                'parameter_stability': optimization_data.get('parameter_stability', 0.8)
            }
        }
    
    def constraint_10_out_of_sample_validation(self, backtest_results: Dict, validation_data: Dict) -> Dict[str, any]:
        """
        Constraint 10: Out-of-Sample Validation
        
        Validates that sufficient data is reserved for out-of-sample testing
        and that performance doesn't degrade significantly out-of-sample.
        """
        
        sample_data = validation_data.get('sample_data', {})
        total_periods = sample_data.get('total_periods', 100)
        out_of_sample_periods = sample_data.get('out_of_sample_periods', 20)
        in_sample_return = sample_data.get('in_sample_return', 0.15)
        out_of_sample_return = sample_data.get('out_of_sample_return', 0.12)
        
        # Calculate out-of-sample percentage
        oos_percentage = out_of_sample_periods / total_periods
        
        # Calculate performance decay
        if in_sample_return > 0:
            performance_decay = (in_sample_return - out_of_sample_return) / in_sample_return
        else:
            performance_decay = 0.0
        
        # Check against threshold
        threshold = self.constraints['out_of_sample_min']
        passed = bool(oos_percentage >= threshold and performance_decay <= 0.5  )# Max 50% decay allowed
        
        severity = 'CRITICAL' if oos_percentage < threshold * 0.5 else 'HIGH' if not passed else 'PASS'
        
        return {
            'passed': passed,
            'severity': severity,
            'value': oos_percentage,
            'threshold': threshold,
            'message': f"Out-of-sample ratio: {oos_percentage:.2%} (threshold: {threshold:.2%})",
            'details': {
                'total_periods': total_periods,
                'out_of_sample_periods': out_of_sample_periods,
                'in_sample_return': in_sample_return,
                'out_of_sample_return': out_of_sample_return,
                'performance_decay': performance_decay,
                'consistency_score': sample_data.get('consistency_score', 0.8)
            }
        }
    
    def constraint_11_walk_forward_stability(self, backtest_results: Dict, validation_data: Dict) -> Dict[str, any]:
        """
        Constraint 11: Walk-Forward Stability
        
        Validates that the strategy performs consistently across multiple
        walk-forward periods without excessive performance variation.
        """
        
        walk_forward_data = validation_data.get('walk_forward_data', {})
        period_returns = walk_forward_data.get('period_returns', [0.1])
        period_sharpe_ratios = walk_forward_data.get('period_sharpe_ratios', [1.0])
        
        # Calculate stability metrics
        if len(period_returns) > 1:
            positive_periods = len([r for r in period_returns if r > 0])
            stability_ratio = positive_periods / len(period_returns)
            
            return_volatility = np.std(period_returns)
            sharpe_consistency = np.std(period_sharpe_ratios) if len(period_sharpe_ratios) > 1 else 0.0
        else:
            stability_ratio = 1.0 if period_returns[0] > 0 else 0.0
            return_volatility = 0.0
            sharpe_consistency = 0.0
        
        # Check against threshold
        threshold = self.constraints['walk_forward_stability_min']
        passed = bool(stability_ratio >= threshold)
        
        severity = 'CRITICAL' if stability_ratio < threshold * 0.7 else 'HIGH' if not passed else 'PASS'
        
        return {
            'passed': passed,
            'severity': severity,
            'value': stability_ratio,
            'threshold': threshold,
            'message': f"Walk-forward stability: {stability_ratio:.2%} (threshold: {threshold:.2%})",
            'details': {
                'period_returns': period_returns,
                'positive_periods': len([r for r in period_returns if r > 0]),
                'total_periods': len(period_returns),
                'return_volatility': return_volatility,
                'sharpe_consistency': sharpe_consistency,
                'stability_metrics': walk_forward_data.get('stability_metrics', {})
            }
        }
    
    def constraint_12_economic_intuition_alignment(self, backtest_results: Dict, validation_data: Dict) -> Dict[str, any]:
        """
        Constraint 12: Economic Intuition Alignment
        
        Validates that the strategy's behavior aligns with economic intuition
        and fundamental market principles rather than pure data mining.
        """
        
        intuition_data = validation_data.get('intuition_data', {})
        intuition_checks = intuition_data.get('intuition_checks', [])
        overall_intuition_score = intuition_data.get('overall_intuition_score', 0.5)
        
        # Calculate intuition score from individual checks
        if intuition_checks:
            passed_checks = [check for check in intuition_checks if check.get('passed', False)]
            calculated_score = len(passed_checks) / len(intuition_checks)
            
            # Use provided score if available, otherwise use calculated
            final_score = overall_intuition_score if overall_intuition_score > 0 else calculated_score
        else:
            final_score = overall_intuition_score
        
        # Check against threshold
        threshold = self.constraints['economic_intuition_score_min']
        passed = bool(final_score >= threshold)
        
        severity = 'CRITICAL' if final_score < threshold * 0.7 else 'HIGH' if not passed else 'PASS'
        
        return {
            'passed': passed,
            'severity': severity,
            'value': final_score,
            'threshold': threshold,
            'message': f"Economic intuition score: {final_score:.2%} (threshold: {threshold:.2%})",
            'details': {
                'intuition_checks': intuition_checks,
                'passed_checks': len([c for c in intuition_checks if c.get('passed', False)]),
                'total_checks': len(intuition_checks),
                'failed_checks': intuition_data.get('failed_checks', 0),
                'overall_score': overall_intuition_score
            }
        }
    
    def _generate_recommendations(self, failed_constraints: List[Dict]) -> List[str]:
        """Generate actionable recommendations based on failed constraints"""
        
        recommendations = []
        
        for constraint in failed_constraints:
            constraint_name = constraint['constraint_name']
            severity = constraint['severity']
            
            if 'Survivorship Bias' in constraint_name:
                recommendations.append("Add delisted stocks in backtest universe with proper delisting dates and PnL impact")
            
            elif 'Transaction Cost' in constraint_name:
                recommendations.append("Implement realistic transaction cost model with crisis multipliers and market impact")
            
            elif 'Liquidity Constraint' in constraint_name:
                recommendations.append("Reduce position sizes to respect ADV limits and add liquidity-based position sizing")
            
            elif 'Market Impact' in constraint_name:
                recommendations.append("Add market impact modeling for large trades and implement smart order routing")
            
            elif 'Regime Change' in constraint_name:
                recommendations.append("Improve regime detection and add adaptive position sizing during regime transitions")
            
            elif 'Crisis Period' in constraint_name:
                recommendations.append("Add crisis detection and implement defensive positioning during market stress")
            
            elif 'Capacity Constraint' in constraint_name:
                recommendations.append("Reduce target AUM or expand investment universe to increase market capacity")
            
            elif 'Correlation Breakdown' in constraint_name:
                recommendations.append("Add correlation monitoring and implement dynamic hedging during breakdown events")
            
            elif 'Data Snooping' in constraint_name:
                recommendations.append("Reduce parameter optimization trials and implement proper multiple testing corrections")
            
            elif 'Out-of-Sample' in constraint_name:
                recommendations.append("Increase out-of-sample data allocation and validate performance decay is acceptable")
            
            elif 'Walk-Forward' in constraint_name:
                recommendations.append("Improve strategy robustness to reduce performance variation across time periods")
            
            elif 'Economic Intuition' in constraint_name:
                recommendations.append("Review strategy logic for economic sensibility and add fundamental validation checks")
        
        return recommendations
    
    def _save_validation_results(self, validation_results: Dict):
        """Save validation results to file"""
        
        try:
            # Convert datetime objects to strings for JSON serialization
            serializable_results = self._make_json_serializable(validation_results)
            
            with open(self.paths['validation_results'], 'w') as f:
                json.dump(serializable_results, f, indent=2)
            
            print(f"💾 Validation results saved to {self.paths['validation_results']}")
            
        except Exception as e:
            print(f"⚠️ Error saving validation results: {e}")
    
    def _make_json_serializable(self, obj):
        """Convert objects to JSON-serializable format"""
        
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {key: self._make_json_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        else:
            return obj


def main():
    """Demonstrate Reality Check Engine"""
    
    print("🔍 REALITY CHECK ENGINE - THE 12 CRITICAL CONSTRAINTS")
    print("=" * 70)
    
    reality_check = RealityCheckEngine()
    
    # Sample backtest results
    sample_backtest = {
        'total_return': 0.22,
        'sharpe_ratio': 1.6,
        'max_drawdown': 0.12,
        'trading_days': 252,
        'volatility': 0.15,
        'win_rate': 0.58
    }
    
    # Sample validation data
    sample_validation_data = {
        'universe_data': {
            'delisted_stocks': ['BHARTIARTL.NS', 'IDEA.NS'],
            'total_stocks': 100,
            'universe_changes': [
                {'date': '2023-01-01', 'added': 5, 'removed': 3},
                {'date': '2023-06-01', 'added': 2, 'removed': 4}
            ]
        },
        'trading_data': {
            'total_trades': 450,
            'total_volume': 750000000,
            'avg_trade_size': 1666667,
            'turnover_rate': 2.5
        },
        'position_data': {
            'positions': {
                'RELIANCE.NS': 40000000,
                'TCS.NS': 35000000,
                'INFY.NS': 30000000,
                'HDFCBANK.NS': 25000000
            },
            'adv_data': {
                'RELIANCE.NS': 1200000000,
                'TCS.NS': 900000000,
                'INFY.NS': 800000000,
                'HDFCBANK.NS': 1000000000
            }
        },
        'execution_data': {
            'large_trades': [
                {'size': 15000000, 'market_cap': 2000000000, 'symbol': 'RELIANCE.NS'},
                {'size': 12000000, 'market_cap': 1500000000, 'symbol': 'TCS.NS'},
                {'size': 8000000, 'market_cap': 1200000000, 'symbol': 'INFY.NS'}
            ],
            'execution_shortfall': 0.0025,
            'fill_rate': 0.98
        },
        'regime_data': {
            'regime_returns': {
                'bull_market': [0.025, 0.032, 0.018, 0.041, 0.028],
                'bear_market': [-0.015, -0.022, 0.008, -0.035, -0.012],
                'sideways_market': [0.005, -0.008, 0.012, -0.003, 0.015],
                'crisis_period': [-0.045, -0.062, -0.028, 0.035, -0.018]
            },
            'regime_transitions': 12,
            'avg_regime_duration': 21
        },
        'crisis_data': {
            'crisis_periods': [
                {'name': 'COVID-19 March 2020', 'return': -0.18, 'duration': 30},
                {'name': 'Banking Crisis 2018', 'return': -0.12, 'duration': 45},
                {'name': 'Demonetization 2016', 'return': -0.08, 'duration': 20}
            ],
            'recovery_times': [60, 90, 45],
            'max_consecutive_losses': 8
        },
        'capacity_data': {
            'target_aum': 500000000,
            'market_capacity': 2000000000,
            'liquidity_buffer': 0.20,
            'capacity_utilization_history': [0.15, 0.18, 0.22, 0.25, 0.25]
        },
        'correlation_data': {
            'historical_correlations': [0.65, 0.68, 0.72, 0.69, 0.71, 0.66, 0.74],
            'correlation_breakdown_events': 2,
            'max_correlation_change': 0.15,
            'correlation_stability_score': 0.82
        },
        'optimization_data': {
            'parameter_trials': 75,
            'optimization_periods': 3,
            'parameters_tested': ['lookback', 'threshold', 'rebalance_freq'],
            'overfitting_score': 0.15,
            'parameter_stability': 0.78
        },
        'sample_data': {
            'total_periods': 120,
            'out_of_sample_periods': 40,
            'in_sample_return': 0.24,
            'out_of_sample_return': 0.20,
            'performance_decay': 0.167,
            'consistency_score': 0.85
        },
        'walk_forward_data': {
            'period_returns': [
                0.022, 0.031, 0.015, 0.028, 0.019, 0.025, 0.012, 0.033,
                0.008, 0.021, -0.005, 0.018, 0.026, 0.014, 0.029, 0.007
            ],
            'period_sharpe_ratios': [1.8, 2.1, 1.2, 1.9, 1.5, 1.7, 0.9, 2.2, 0.6, 1.4, -0.3, 1.3, 1.8, 1.1, 2.0, 0.5],
            'stability_metrics': {
                'return_consistency': 0.75,
                'sharpe_consistency': 0.68,
                'drawdown_consistency': 0.82
            }
        },
        'intuition_data': {
            'intuition_checks': [
                {'name': 'Market regime alignment', 'passed': True, 'score': 0.85},
                {'name': 'Factor exposure consistency', 'passed': True, 'score': 0.78},
                {'name': 'Fundamental driver correlation', 'passed': False, 'score': 0.45},
                {'name': 'Economic cycle alignment', 'passed': True, 'score': 0.72},
                {'name': 'Risk factor attribution', 'passed': True, 'score': 0.88},
                {'name': 'Sector rotation logic', 'passed': True, 'score': 0.65},
                {'name': 'Momentum persistence', 'passed': False, 'score': 0.52}
            ],
            'overall_intuition_score': 0.69,
            'failed_checks': 2
        }
    }
    
    # Run validation
    results = reality_check.run_full_validation(sample_backtest, sample_validation_data)
    
    print(f"\n✅ Reality Check Engine demonstration complete")
    print(f"💡 All 12 constraints validated with real V3 integration")


if __name__ == "__main__":
    main()