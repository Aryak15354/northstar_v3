#!/usr/bin/env python3
"""
🛡️ PORTFOLIO KILL SWITCHES - SURVIVAL LAYER
The guardian that prevents portfolio ruin

This is what separates quants from gamblers.
No fund survives without kill switches.

Usage:
from src.cohesion.unified_state_manager import UnifiedStateManager, AuthorityLevel

    from src.risk.portfolio_kill_switches import PortfolioKillSwitches
    
    kill_switches = PortfolioKillSwitches()
    kill_switches.check_portfolio_health()
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from src.cohesion.unified_state_manager import UnifiedStateManager, AuthorityLevel

class PortfolioKillSwitches:
    """
    Portfolio Kill Switches - Survival Protection System
    
    Monitors portfolio for fatal conditions and triggers emergency stops:
    - Maximum drawdown limits
    - Volatility spikes
    - Monthly loss limits
    - Correlation breakdowns
    
    When triggered, forces exposure to zero and freezes allocation.
    """
    
    def __init__(self):
        self.name = "Portfolio Kill Switches"
        self.version = "1.0"
        
        # File paths
        self.paths = {
            'portfolio_weights': 'data/processed/portfolio_weights.parquet',
            'portfolio_analytics': 'data/processed/portfolio_analytics.json',
            'performance_master': 'data/processed/performance/master.parquet',
            'kill_switch_log': 'data/risk/kill_switch_log.parquet',
            'emergency_state': 'data/risk/emergency_state.json'
        }
        
        # Create risk directory
        os.makedirs('data/risk', exist_ok=True)

        # Authoritative state sink for emergency actions (FORCE_ZERO_EXPOSURE,
        # REDUCE_EXPOSURE_50, FREEZE_ALLOCATOR, HALT_TRADING). Must be a real
        # instance, not a bare name, or execute_emergency_action raises
        # NameError and the kill switch never actually de-risks anything.
        self.emergency_state_manager = UnifiedStateManager()

        # Kill switch thresholds (adjusted for risk-controlled portfolio)
        self.thresholds = {
            'max_portfolio_drawdown': 0.20,    # 20% max portfolio drawdown (increased)
            'max_monthly_loss': 0.08,          # 8% max monthly loss (increased)
            'max_portfolio_volatility': 0.30,  # 30% max annualized volatility (increased)
            'max_daily_loss': 0.05,            # 5% max single day loss (increased)
            'min_sharpe_ratio': -1.0,          # Below -1.0 Sharpe = emergency (more lenient)
            'max_correlation_spike': 0.9,      # Strategy correlation > 90%
            'max_consecutive_losses': 7,       # 7 consecutive losing days (increased)
            'min_liquidity_score': 0.3         # Minimum portfolio liquidity
        }
        
        # Emergency actions
        self.emergency_actions = {
            'FORCE_ZERO_EXPOSURE': 'Set portfolio exposure to 0%',
            'FREEZE_ALLOCATOR': 'Stop capital allocation updates',
            'HALT_TRADING': 'Stop all new trades',
            'ALERT_RISK_MANAGER': 'Send emergency alert',
            'REDUCE_EXPOSURE_50': 'Cut exposure by 50%',
            'INCREASE_CASH': 'Move to 80% cash'
        }
    
    def load_portfolio_performance(self):
        """Load recent portfolio performance data"""
        
        print("📊 Loading portfolio performance for kill switch monitoring...")
        
        performance_data = {
            'daily_returns': [],
            'equity_curve': [],
            'drawdowns': [],
            'volatility': 0,
            'sharpe': 0,
            'max_drawdown': 0,
            'current_exposure': 0
        }
        
        try:
            # Load performance master file
            if os.path.exists(self.paths['performance_master']):
                perf_df = pd.read_parquet(self.paths['performance_master'])
                
                # Get portfolio-level performance (aggregate across strategies)
                if not perf_df.empty:
                    # Group by date and calculate portfolio returns
                    daily_perf = perf_df.groupby('date').agg({
                        'daily_return': 'mean',  # Average across strategies
                        'equity': 'mean',
                        'drawdown': 'mean',
                        'exposure': 'mean'
                    }).reset_index()
                    
                    daily_perf = daily_perf.sort_values('date')
                    
                    if len(daily_perf) > 1:
                        performance_data['daily_returns'] = daily_perf['daily_return'].tolist()
                        performance_data['equity_curve'] = daily_perf['equity'].tolist()
                        performance_data['drawdowns'] = daily_perf['drawdown'].tolist()
                        performance_data['current_exposure'] = daily_perf['exposure'].iloc[-1]
                        
                        # Calculate risk metrics
                        returns = daily_perf['daily_return']
                        performance_data['volatility'] = returns.std() * np.sqrt(252)
                        performance_data['sharpe'] = (returns.mean() * 252) / (returns.std() * np.sqrt(252)) if returns.std() > 0 else 0
                        performance_data['max_drawdown'] = daily_perf['drawdown'].min()
            
            # Load current portfolio exposure
            if os.path.exists(self.paths['portfolio_analytics']):
                with open(self.paths['portfolio_analytics'], 'r') as f:
                    analytics = json.load(f)
                    performance_data['current_exposure'] = analytics.get('portfolio_summary', {}).get('total_exposure', 0)
            
            print(f"   ✅ Loaded performance data: {len(performance_data['daily_returns'])} days")
            
        except Exception as e:
            print(f"   ⚠️ Error loading performance: {e}")
        
        return performance_data
    
    def check_drawdown_limits(self, performance_data):
        """Check portfolio drawdown against kill switch limits"""
        
        violations = []
        
        max_dd = performance_data.get('max_drawdown', 0)
        
        if abs(max_dd) > self.thresholds['max_portfolio_drawdown']:
            violations.append({
                'kill_switch': 'MAX_PORTFOLIO_DRAWDOWN',
                'current_value': abs(max_dd),
                'threshold': self.thresholds['max_portfolio_drawdown'],
                'severity': 'CRITICAL',
                'action': 'FORCE_ZERO_EXPOSURE',
                'message': f"Portfolio drawdown {abs(max_dd):.1%} exceeds limit {self.thresholds['max_portfolio_drawdown']:.1%}"
            })
        
        return violations
    
    def check_volatility_limits(self, performance_data):
        """Check portfolio volatility against kill switch limits"""
        
        violations = []
        
        volatility = performance_data.get('volatility', 0)
        
        if volatility > self.thresholds['max_portfolio_volatility']:
            violations.append({
                'kill_switch': 'MAX_PORTFOLIO_VOLATILITY',
                'current_value': volatility,
                'threshold': self.thresholds['max_portfolio_volatility'],
                'severity': 'HIGH',
                'action': 'REDUCE_EXPOSURE_50',
                'message': f"Portfolio volatility {volatility:.1%} exceeds limit {self.thresholds['max_portfolio_volatility']:.1%}"
            })
        
        return violations
    
    def check_loss_limits(self, performance_data):
        """Check daily and monthly loss limits"""
        
        violations = []
        
        daily_returns = performance_data.get('daily_returns', [])
        
        if daily_returns:
            # Check daily loss limit
            worst_daily = min(daily_returns)
            if worst_daily < -self.thresholds['max_daily_loss']:
                violations.append({
                    'kill_switch': 'MAX_DAILY_LOSS',
                    'current_value': abs(worst_daily),
                    'threshold': self.thresholds['max_daily_loss'],
                    'severity': 'HIGH',
                    'action': 'HALT_TRADING',
                    'message': f"Daily loss {abs(worst_daily):.1%} exceeds limit {self.thresholds['max_daily_loss']:.1%}"
                })
            
            # Check monthly loss limit (last 30 days)
            if len(daily_returns) >= 30:
                monthly_return = np.prod([1 + r for r in daily_returns[-30:]]) - 1
                if monthly_return < -self.thresholds['max_monthly_loss']:
                    violations.append({
                        'kill_switch': 'MAX_MONTHLY_LOSS',
                        'current_value': abs(monthly_return),
                        'threshold': self.thresholds['max_monthly_loss'],
                        'severity': 'CRITICAL',
                        'action': 'FORCE_ZERO_EXPOSURE',
                        'message': f"Monthly loss {abs(monthly_return):.1%} exceeds limit {self.thresholds['max_monthly_loss']:.1%}"
                    })
            
            # Check consecutive losses
            consecutive_losses = 0
            for ret in reversed(daily_returns):
                if ret < 0:
                    consecutive_losses += 1
                else:
                    break
            
            if consecutive_losses >= self.thresholds['max_consecutive_losses']:
                violations.append({
                    'kill_switch': 'MAX_CONSECUTIVE_LOSSES',
                    'current_value': consecutive_losses,
                    'threshold': self.thresholds['max_consecutive_losses'],
                    'severity': 'MEDIUM',
                    'action': 'REDUCE_EXPOSURE_50',
                    'message': f"{consecutive_losses} consecutive losing days exceeds limit {self.thresholds['max_consecutive_losses']}"
                })
        
        return violations
    
    def check_sharpe_limits(self, performance_data):
        """Check Sharpe ratio kill switch"""
        
        violations = []
        
        sharpe = performance_data.get('sharpe', 0)
        
        if sharpe < self.thresholds['min_sharpe_ratio']:
            violations.append({
                'kill_switch': 'MIN_SHARPE_RATIO',
                'current_value': sharpe,
                'threshold': self.thresholds['min_sharpe_ratio'],
                'severity': 'HIGH',
                'action': 'FREEZE_ALLOCATOR',
                'message': f"Sharpe ratio {sharpe:.2f} below minimum {self.thresholds['min_sharpe_ratio']:.2f}"
            })
        
        return violations
    
    def check_strategy_correlation(self):
        """Check for strategy correlation spikes (model fraud detection)"""
        
        violations = []
        
        try:
            # Load strategy performance to check correlations
            if os.path.exists(self.paths['performance_master']):
                perf_df = pd.read_parquet(self.paths['performance_master'])
                
                # Create correlation matrix of strategy returns
                strategy_returns = perf_df.pivot(index='date', columns='strategy', values='daily_return')
                
                if len(strategy_returns.columns) > 1:
                    corr_matrix = strategy_returns.corr()
                    
                    # Check for high correlations (excluding diagonal)
                    np.fill_diagonal(corr_matrix.values, 0)
                    max_correlation = corr_matrix.abs().max().max()
                    
                    if max_correlation > self.thresholds['max_correlation_spike']:
                        # Find the correlated pair
                        max_idx = corr_matrix.abs().stack().idxmax()
                        strategy1, strategy2 = max_idx
                        correlation_value = corr_matrix.loc[strategy1, strategy2]
                        
                        violations.append({
                            'kill_switch': 'MAX_CORRELATION_SPIKE',
                            'current_value': abs(correlation_value),
                            'threshold': self.thresholds['max_correlation_spike'],
                            'severity': 'MEDIUM',
                            'action': 'ALERT_RISK_MANAGER',
                            'message': f"High correlation {abs(correlation_value):.1%} between {strategy1} and {strategy2}"
                        })
        
        except Exception as e:
            print(f"   ⚠️ Error checking correlations: {e}")
        
        return violations
    
    def execute_emergency_action(self, action, violation):
        """Execute emergency action when kill switch is triggered"""
        
        print(f"🚨 EXECUTING EMERGENCY ACTION: {action}")
        
        emergency_state = {
            'timestamp': datetime.now().isoformat(),
            'triggered_by': violation['kill_switch'],
            'action': action,
            'severity': violation['severity'],
            'message': violation['message'],
            'portfolio_frozen': False,
            'exposure_override': None
        }
        
        state_update_ok = True
        if action == 'FORCE_ZERO_EXPOSURE':
            state_update_ok = self.emergency_state_manager.update_state(
                "kill_switches", {'exposure_override': 0.0, 'portfolio_frozen': True},
                AuthorityLevel.SYSTEM, f"Kill switch: {violation['kill_switch']}"
            )
            print("   🛑 PORTFOLIO EXPOSURE FORCED TO ZERO")

        elif action == 'REDUCE_EXPOSURE_50':
            state_update_ok = self.emergency_state_manager.update_state(
                "kill_switches", {'exposure_override': 0.5},
                AuthorityLevel.SYSTEM, f"Kill switch: {violation['kill_switch']}"
            )
            print("   ⚠️ PORTFOLIO EXPOSURE REDUCED BY 50%")

        elif action == 'FREEZE_ALLOCATOR':
            state_update_ok = self.emergency_state_manager.update_state(
                "kill_switches", {'portfolio_frozen': True},
                AuthorityLevel.SYSTEM, f"Kill switch: {violation['kill_switch']}"
            )
            print("   🧊 CAPITAL ALLOCATOR FROZEN")

        elif action == 'HALT_TRADING':
            state_update_ok = self.emergency_state_manager.update_state(
                "kill_switches", {'portfolio_frozen': True, 'exposure_override': 0.0},
                AuthorityLevel.SYSTEM, f"Kill switch: {violation['kill_switch']}"
            )
            print("   🛑 ALL TRADING HALTED")

        if not state_update_ok:
            # update_state() returns False (rather than raising) when a
            # higher-authority value already exists for one of these fields
            # (INVARIANT S3). The emergency action did NOT take effect --
            # this must not be silently swallowed.
            emergency_state['portfolio_frozen'] = False
            print(f"   🚨 EMERGENCY STATE UPDATE REJECTED for action={action} -- "
                  f"a higher-authority value already holds these fields. "
                  f"Portfolio was NOT de-risked; manual intervention required.")
        else:
            emergency_state['portfolio_frozen'] = action in (
                'FORCE_ZERO_EXPOSURE', 'FREEZE_ALLOCATOR', 'HALT_TRADING'
            )
            emergency_state['exposure_override'] = {
                'FORCE_ZERO_EXPOSURE': 0.0,
                'REDUCE_EXPOSURE_50': 0.5,
                'HALT_TRADING': 0.0,
            }.get(action)

        # Save emergency state
        with open(self.paths['emergency_state'], 'w') as f:
            json.dump(emergency_state, f, indent=2)

        return emergency_state
    
    def log_violation(self, violation):
        """Log kill switch violation"""
        
        log_entry = {
            'timestamp': datetime.now(),
            'kill_switch': violation['kill_switch'],
            'current_value': violation['current_value'],
            'threshold': violation['threshold'],
            'severity': violation['severity'],
            'action': violation['action'],
            'message': violation['message']
        }
        
        # Append to log
        if os.path.exists(self.paths['kill_switch_log']):
            log_df = pd.read_parquet(self.paths['kill_switch_log'])
            log_df = pd.concat([log_df, pd.DataFrame([log_entry])], ignore_index=True)
        else:
            log_df = pd.DataFrame([log_entry])
        
        log_df.to_parquet(self.paths['kill_switch_log'], index=False)
    
    def check_portfolio_health(self):
        """Run complete portfolio health check with kill switches"""
        
        print("🛡️ PORTFOLIO KILL SWITCHES - SURVIVAL CHECK")
        print("=" * 60)
        
        # Load performance data
        performance_data = self.load_portfolio_performance()
        
        # Run all kill switch checks
        all_violations = []
        
        # Drawdown checks
        dd_violations = self.check_drawdown_limits(performance_data)
        all_violations.extend(dd_violations)
        
        # Volatility checks
        vol_violations = self.check_volatility_limits(performance_data)
        all_violations.extend(vol_violations)
        
        # Loss limit checks
        loss_violations = self.check_loss_limits(performance_data)
        all_violations.extend(loss_violations)
        
        # Sharpe ratio checks
        sharpe_violations = self.check_sharpe_limits(performance_data)
        all_violations.extend(sharpe_violations)
        
        # Strategy correlation checks
        corr_violations = self.check_strategy_correlation()
        all_violations.extend(corr_violations)
        
        # Process violations
        critical_violations = [v for v in all_violations if v['severity'] == 'CRITICAL']
        high_violations = [v for v in all_violations if v['severity'] == 'HIGH']
        
        print(f"\n🔍 KILL SWITCH RESULTS:")
        print(f"   Total violations: {len(all_violations)}")
        print(f"   Critical: {len(critical_violations)}")
        print(f"   High: {len(high_violations)}")
        
        # Execute emergency actions for critical violations
        emergency_actions_taken = []
        
        for violation in critical_violations:
            self.log_violation(violation)
            emergency_state = self.execute_emergency_action(violation['action'], violation)
            emergency_actions_taken.append(emergency_state)
            
            print(f"   🚨 {violation['message']}")
        
        # Log high severity violations
        for violation in high_violations:
            self.log_violation(violation)
            print(f"   ⚠️ {violation['message']}")
        
        # Summary
        if critical_violations:
            print(f"\n🚨 CRITICAL VIOLATIONS DETECTED - EMERGENCY ACTIONS TAKEN")
            print(f"   Portfolio safety systems activated")
            return False, emergency_actions_taken
        elif high_violations:
            print(f"\n⚠️ HIGH RISK CONDITIONS DETECTED - MONITORING REQUIRED")
            return True, []
        else:
            print(f"\n✅ ALL KILL SWITCHES PASSED - PORTFOLIO IS SAFE")
            return True, []

def main():
    """Main execution function"""
    
    kill_switches = PortfolioKillSwitches()
    is_safe, emergency_actions = kill_switches.check_portfolio_health()
    
    return is_safe, emergency_actions

if __name__ == "__main__":
    main()