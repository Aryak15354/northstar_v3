#!/usr/bin/env python3
"""
🛡️ PORTFOLIO RISK CONTROLLER
Advanced risk management with dynamic exposure scaling

This prevents portfolio ruin by dynamically adjusting exposure
based on realized risk metrics and market conditions.

Usage:
    from src.risk.portfolio_risk_controller import PortfolioRiskController
    
    risk_controller = PortfolioRiskController()
    risk_controller.apply_risk_controls()
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class PortfolioRiskController:
    """
    Portfolio Risk Controller
    
    Dynamically adjusts portfolio exposure based on:
    - Realized volatility vs target
    - Drawdown levels
    - Recent performance
    - Market regime
    """
    
    def __init__(self):
        self.name = "Portfolio Risk Controller"
        self.version = "1.0"
        
        # File paths
        self.paths = {
            'portfolio_weights': 'data/processed/portfolio_weights.parquet',
            'portfolio_analytics': 'data/processed/portfolio_analytics.json',
            'performance_master': 'data/processed/performance/master.parquet',
            'market_state': 'data/processed/market_state.parquet',
            'risk_controls': 'data/risk/portfolio_risk_controls.json'
        }
        
        # Create risk directory
        os.makedirs('data/risk', exist_ok=True)
        
        # Risk control parameters
        self.risk_params = {
            'target_volatility': 0.15,      # 15% target annual volatility
            'max_volatility': 0.20,         # 20% maximum volatility
            'target_drawdown': 0.08,        # 8% target max drawdown
            'max_drawdown': 0.12,           # 12% absolute max drawdown
            'lookback_days': 60,            # Days for risk calculation
            'min_exposure': 0.20,           # 20% minimum exposure
            'max_exposure': 1.00,           # 100% maximum exposure
            'volatility_halflife': 30,      # Days for volatility decay
            'stress_multiplier': 1.5        # Stress test multiplier
        }
        
        # Regime-based risk adjustments
        self.regime_adjustments = {
            'crisis': {'vol_target': 0.10, 'max_exposure': 0.60},
            'tightening': {'vol_target': 0.12, 'max_exposure': 0.80},
            'slowdown': {'vol_target': 0.13, 'max_exposure': 0.85},
            'expansion': {'vol_target': 0.15, 'max_exposure': 1.00},
            'boom': {'vol_target': 0.18, 'max_exposure': 1.00},
            'late-expansion': {'vol_target': 0.14, 'max_exposure': 0.90}
        }
    
    def load_portfolio_performance(self):
        """Load recent portfolio performance for risk assessment"""
        
        print("📊 Loading portfolio performance for risk assessment...")
        
        performance_data = {
            'daily_returns': [],
            'dates': [],
            'equity_curve': [],
            'current_drawdown': 0,
            'realized_volatility': 0
        }
        
        try:
            if os.path.exists(self.paths['performance_master']):
                perf_df = pd.read_parquet(self.paths['performance_master'])
                
                if not perf_df.empty:
                    # Aggregate portfolio performance
                    daily_perf = perf_df.groupby('date').agg({
                        'daily_return': 'mean',
                        'equity': 'mean'
                    }).reset_index()
                    
                    daily_perf = daily_perf.sort_values('date')
                    
                    # Get recent performance
                    recent_perf = daily_perf.tail(self.risk_params['lookback_days'])
                    
                    if len(recent_perf) > 10:
                        returns = recent_perf['daily_return']
                        equity = recent_perf['equity']
                        
                        performance_data['daily_returns'] = returns.tolist()
                        performance_data['dates'] = recent_perf['date'].tolist()
                        performance_data['equity_curve'] = equity.tolist()
                        
                        # Calculate current drawdown
                        running_max = equity.expanding().max()
                        current_dd = (equity.iloc[-1] / running_max.iloc[-1]) - 1
                        performance_data['current_drawdown'] = current_dd
                        
                        # Calculate realized volatility (EWMA)
                        performance_data['realized_volatility'] = self.calculate_ewma_volatility(returns)
            
            print(f"   ✅ Loaded {len(performance_data['daily_returns'])} days of performance")
            
        except Exception as e:
            print(f"   ⚠️ Error loading performance: {e}")
        
        return performance_data
    
    def calculate_ewma_volatility(self, returns):
        """Calculate exponentially weighted moving average volatility"""
        
        if len(returns) < 10:
            return returns.std() * np.sqrt(252)
        
        # EWMA with half-life
        alpha = 1 - np.exp(-np.log(2) / self.risk_params['volatility_halflife'])
        
        ewma_var = 0
        for ret in returns:
            ewma_var = alpha * (ret ** 2) + (1 - alpha) * ewma_var
        
        return np.sqrt(ewma_var * 252)
    
    def get_current_regime(self):
        """Get current market regime for risk adjustment"""
        
        try:
            if os.path.exists(self.paths['market_state']):
                market_df = pd.read_parquet(self.paths['market_state'])
                if not market_df.empty:
                    latest = market_df.iloc[-1]
                    return latest.get('macro_regime', 'expansion')
        except Exception as e:
            print(f"   ⚠️ Could not load regime: {e}")
        
        return 'expansion'
    
    def calculate_risk_adjusted_exposure(self, performance_data, current_regime):
        """Calculate risk-adjusted portfolio exposure"""
        
        print("⚖️ Calculating risk-adjusted exposure...")
        
        # Get regime-adjusted targets
        regime_config = self.regime_adjustments.get(current_regime, {})
        vol_target = regime_config.get('vol_target', self.risk_params['target_volatility'])
        max_exposure_regime = regime_config.get('max_exposure', self.risk_params['max_exposure'])
        
        # Base exposure calculation
        realized_vol = performance_data['realized_volatility']
        current_dd = abs(performance_data['current_drawdown'])
        
        # Volatility-based scaling
        if realized_vol > 0:
            vol_scalar = min(vol_target / realized_vol, 2.0)  # Cap at 2x
        else:
            vol_scalar = 1.0
        
        # Drawdown-based scaling
        if current_dd > self.risk_params['target_drawdown']:
            dd_scalar = max(
                (self.risk_params['max_drawdown'] - current_dd) / 
                (self.risk_params['max_drawdown'] - self.risk_params['target_drawdown']),
                0.1
            )
        else:
            dd_scalar = 1.0
        
        # Recent performance scaling
        if len(performance_data['daily_returns']) >= 20:
            recent_returns = performance_data['daily_returns'][-20:]
            recent_sharpe = (np.mean(recent_returns) * 252) / (np.std(recent_returns) * np.sqrt(252))
            
            if recent_sharpe > 1.0:
                perf_scalar = 1.1  # Slight boost for good performance
            elif recent_sharpe < -0.5:
                perf_scalar = 0.7  # Reduce for poor performance
            else:
                perf_scalar = 1.0
        else:
            perf_scalar = 1.0
        
        # Combined exposure
        base_exposure = 0.8  # Start with 80% base exposure
        risk_adjusted_exposure = base_exposure * vol_scalar * dd_scalar * perf_scalar
        
        # Apply bounds
        final_exposure = np.clip(
            risk_adjusted_exposure,
            self.risk_params['min_exposure'],
            min(max_exposure_regime, self.risk_params['max_exposure'])
        )
        
        print(f"   📊 Volatility scalar: {vol_scalar:.2f} (realized: {realized_vol:.1%}, target: {vol_target:.1%})")
        print(f"   📊 Drawdown scalar: {dd_scalar:.2f} (current: {current_dd:.1%})")
        print(f"   📊 Performance scalar: {perf_scalar:.2f}")
        print(f"   📊 Final exposure: {final_exposure:.1%}")
        
        return final_exposure, {
            'vol_scalar': vol_scalar,
            'dd_scalar': dd_scalar,
            'perf_scalar': perf_scalar,
            'realized_volatility': realized_vol,
            'current_drawdown': current_dd,
            'regime': current_regime,
            'vol_target': vol_target
        }
    
    def apply_exposure_scaling(self, target_exposure):
        """Apply exposure scaling to portfolio weights"""
        
        print(f"🎯 Applying {target_exposure:.1%} exposure scaling...")
        
        if not os.path.exists(self.paths['portfolio_weights']):
            print("   ⚠️ No portfolio weights file found")
            return False
        
        # Load current portfolio
        portfolio_df = pd.read_parquet(self.paths['portfolio_weights'])
        
        if portfolio_df.empty:
            print("   ⚠️ Empty portfolio")
            return False
        
        # Scale weights
        original_exposure = portfolio_df['final_weight'].abs().sum()
        scaling_factor = target_exposure / original_exposure if original_exposure > 0 else 0
        
        portfolio_df['final_weight'] = portfolio_df['final_weight'] * scaling_factor
        portfolio_df['risk_adjusted'] = True
        portfolio_df['scaling_factor'] = scaling_factor
        portfolio_df['target_exposure'] = target_exposure
        
        # Save scaled portfolio
        portfolio_df.to_parquet(self.paths['portfolio_weights'], index=False)
        
        print(f"   ✅ Scaled portfolio: {original_exposure:.1%} → {target_exposure:.1%}")
        print(f"   📊 Scaling factor: {scaling_factor:.2f}")
        print(f"   📊 Positions: {len(portfolio_df)}")
        
        return True
    
    def update_portfolio_analytics(self, risk_metrics):
        """Update portfolio analytics with risk control information"""
        
        analytics = {}
        
        # Load existing analytics
        if os.path.exists(self.paths['portfolio_analytics']):
            with open(self.paths['portfolio_analytics'], 'r') as f:
                analytics = json.load(f)
        
        # Add risk control metrics
        analytics['risk_controls'] = {
            'timestamp': datetime.now().isoformat(),
            'risk_adjusted_exposure': risk_metrics.get('final_exposure', 0),
            'volatility_scalar': risk_metrics.get('vol_scalar', 1),
            'drawdown_scalar': risk_metrics.get('dd_scalar', 1),
            'performance_scalar': risk_metrics.get('perf_scalar', 1),
            'realized_volatility': risk_metrics.get('realized_volatility', 0),
            'current_drawdown': risk_metrics.get('current_drawdown', 0),
            'regime': risk_metrics.get('regime', 'expansion'),
            'volatility_target': risk_metrics.get('vol_target', 0.15)
        }
        
        # Save updated analytics
        with open(self.paths['portfolio_analytics'], 'w') as f:
            json.dump(analytics, f, indent=2, default=str)
        
        return analytics
    
    def apply_risk_controls(self):
        """Apply complete risk control system"""
        
        print("🛡️ PORTFOLIO RISK CONTROLLER")
        print("=" * 60)
        
        # Load performance data
        performance_data = self.load_portfolio_performance()
        
        if not performance_data['daily_returns']:
            print("❌ No performance data available for risk control")
            return False
        
        # Get current regime
        current_regime = self.get_current_regime()
        print(f"📊 Current regime: {current_regime}")
        
        # Calculate risk-adjusted exposure
        target_exposure, risk_metrics = self.calculate_risk_adjusted_exposure(
            performance_data, current_regime
        )
        
        # Apply exposure scaling
        success = self.apply_exposure_scaling(target_exposure)
        
        if not success:
            print("❌ Failed to apply exposure scaling")
            return False
        
        # Update analytics
        risk_metrics['final_exposure'] = target_exposure
        analytics = self.update_portfolio_analytics(risk_metrics)
        
        # Save risk control log
        risk_log = {
            'timestamp': datetime.now().isoformat(),
            'target_exposure': target_exposure,
            'risk_metrics': risk_metrics,
            'regime': current_regime,
            'performance_days': len(performance_data['daily_returns'])
        }
        
        with open(self.paths['risk_controls'], 'w') as f:
            json.dump(risk_log, f, indent=2, default=str)
        
        # Summary
        print(f"\n🛡️ RISK CONTROL SUMMARY:")
        print(f"   🎯 Target exposure: {target_exposure:.1%}")
        print(f"   📊 Realized volatility: {risk_metrics['realized_volatility']:.1%}")
        print(f"   📊 Current drawdown: {abs(risk_metrics['current_drawdown']):.1%}")
        print(f"   📊 Regime: {current_regime}")
        print(f"   ✅ Risk controls applied successfully")
        
        return True

def main():
    """Main execution function"""
    
    risk_controller = PortfolioRiskController()
    success = risk_controller.apply_risk_controls()
    
    return success

if __name__ == "__main__":
    main()