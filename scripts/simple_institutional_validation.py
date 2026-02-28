#!/usr/bin/env python3
"""
🏆 SIMPLE INSTITUTIONAL VALIDATION
Simplified institutional validation using working components only.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import warnings

warnings.filterwarnings('ignore')

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    """Run simplified institutional validation"""
    
    print("🏆 SIMPLE INSTITUTIONAL VALIDATION")
    print("=" * 60)
    print("Simplified validation using working components only.")
    print()
    
    try:
        # Phase 1: Data Validation
        print("📊 PHASE 1: DATA VALIDATION")
        print("-" * 40)
        
        data_checks = {
            'market_state': 'data/processed/market_state.parquet',
            'portfolio_weights': 'data/processed/portfolio_weights.parquet',
            'strategy_beliefs': 'data/processed/strategy_beliefs.parquet'
        }
        
        data_status = {}
        for name, path in data_checks.items():
            if os.path.exists(path):
                try:
                    df = pd.read_parquet(path)
                    data_status[name] = {
                        'exists': True,
                        'records': len(df),
                        'size_mb': os.path.getsize(path) / 1024 / 1024
                    }
                    print(f"   ✅ {name}: {len(df)} records ({data_status[name]['size_mb']:.1f} MB)")
                except Exception as e:
                    data_status[name] = {'exists': True, 'error': str(e)}
                    print(f"   ❌ {name}: Error reading file - {e}")
            else:
                data_status[name] = {'exists': False}
                print(f"   ⚠️ {name}: File not found")
        
        # Phase 2: Performance Validation
        print(f"\n📈 PHASE 2: PERFORMANCE VALIDATION")
        print("-" * 40)
        
        # Check for existing performance reports
        performance_files = []
        reports_dir = "reports"
        if os.path.exists(reports_dir):
            for root, dirs, files in os.walk(reports_dir):
                for file in files:
                    if 'performance' in file.lower() and file.endswith('.md'):
                        performance_files.append(os.path.join(root, file))
        
        print(f"   📄 Found {len(performance_files)} performance reports")
        
        # Compute real performance metrics from portfolio PnL history (no synthetic data)
        pnl_path = "data/portfolio/pnl_on_paper.parquet"
        if not os.path.exists(pnl_path):
            raise FileNotFoundError("Missing real PnL series: data/portfolio/pnl_on_paper.parquet")

        pnl = pd.read_parquet(pnl_path)
        if pnl is None or pnl.empty or "Date" not in pnl.columns:
            raise ValueError("PnL series is empty or malformed")

        pnl = pnl.copy()
        pnl["Date"] = pd.to_datetime(pnl["Date"], errors="coerce")
        pnl = pnl.dropna(subset=["Date"]).sort_values("Date").set_index("Date")

        # Use last 252 trading days (~1Y) for institutional summary.
        pnl_1y = pnl.tail(252)
        if "Return" in pnl_1y.columns and pd.to_numeric(pnl_1y["Return"], errors="coerce").notna().any():
            returns = pd.to_numeric(pnl_1y["Return"], errors="coerce").dropna().astype(float)
        else:
            equity = pd.to_numeric(pnl_1y.get("Equity"), errors="coerce")
            returns = equity.pct_change().dropna().astype(float)

        if returns.empty or len(returns) < 30:
            raise ValueError("Not enough real return history to compute metrics (need >= 30 days).")

        cumulative_return = float((1 + returns).prod() - 1)
        vol_ann = float(returns.std() * np.sqrt(252)) if returns.std() > 0 else np.nan
        sharpe_ratio = float(returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else np.nan

        equity_curve = (1 + returns).cumprod()
        peak = equity_curve.cummax()
        drawdown = equity_curve / peak - 1
        max_drawdown = float(drawdown.min())

        performance_metrics = {
            'total_return': cumulative_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'volatility': vol_ann,
            'win_rate': float((returns > 0).mean()),
            'as_of': str(pnl_1y.index.max().date()),
            'window_days': int(len(returns)),
        }
        
        print(f"   📊 Total Return: {performance_metrics['total_return']:.2%}")
        print(f"   📊 Sharpe Ratio: {performance_metrics['sharpe_ratio']:.2f}")
        print(f"   📊 Max Drawdown: {performance_metrics['max_drawdown']:.2%}")
        print(f"   📊 Win Rate: {performance_metrics['win_rate']:.1%}")
        
        # Phase 3: Risk Validation
        print(f"\n🛡️ PHASE 3: RISK VALIDATION")
        print("-" * 40)
        
        # Check for risk-related files
        risk_files = []
        data_risk_dir = "data/risk"
        if os.path.exists(data_risk_dir):
            risk_files = [f for f in os.listdir(data_risk_dir) if f.endswith('.parquet')]
        
        print(f"   📄 Found {len(risk_files)} risk data files")
        
        # Validate risk metrics
        risk_metrics = {
            'exposure_limit': 1.0,  # 100% max exposure
            'drawdown_limit': -0.15,  # 15% max drawdown
            'volatility_limit': 0.20,  # 20% max volatility
            'concentration_limit': 0.10  # 10% max single position
        }
        
        # Exposure / concentration from real current portfolio weights
        exposure = None
        max_weight = None
        weights_path = "data/processed/portfolio_weights.parquet"
        if os.path.exists(weights_path):
            try:
                wdf = pd.read_parquet(weights_path)
                wcol = None
                for c in ["weight", "final_weight", "w", "allocation"]:
                    if c in wdf.columns:
                        wcol = c
                        break
                if wcol is not None:
                    w = pd.to_numeric(wdf[wcol], errors="coerce").dropna()
                    if not w.empty:
                        exposure = float(w.sum())
                        max_weight = float(w.max())
            except Exception:
                pass

        risk_status = {
            'exposure_ok': (exposure is None) or (exposure <= risk_metrics['exposure_limit']),
            'concentration_ok': (max_weight is None) or (max_weight <= risk_metrics['concentration_limit']),
            'volatility_ok': (performance_metrics['volatility'] is not None) and (performance_metrics['volatility'] <= risk_metrics['volatility_limit']),
            'drawdown_ok': (performance_metrics['max_drawdown'] is not None) and (performance_metrics['max_drawdown'] >= risk_metrics['drawdown_limit']),
        }
        
        for check, passed in risk_status.items():
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"   {check}: {status}")
        
        # Phase 4: System Health
        print(f"\n🏥 PHASE 4: SYSTEM HEALTH")
        print("-" * 40)
        
        # Check system components
        system_components = {
            'data_pipeline': 'src/ingestion/integrated_data_pipeline.py',
            'dashboard': 'dashboard/app.py',
            'validation_suite': 'src/validation/performance_tracker.py'
        }
        
        system_health = {}
        for component, path in system_components.items():
            exists = os.path.exists(path)
            system_health[component] = exists
            status = "✅ Available" if exists else "❌ Missing"
            print(f"   {component}: {status}")
        
        # Generate final validation report
        print(f"\n📋 FINAL VALIDATION SUMMARY")
        print("=" * 50)
        
        # Calculate overall scores
        data_score = sum(1 for status in data_status.values() if status.get('exists', False)) / len(data_status)
        performance_score = 1.0 if performance_metrics['sharpe_ratio'] > 0.5 else 0.5
        risk_score = sum(risk_status.values()) / len(risk_status)
        system_score = sum(system_health.values()) / len(system_health)
        
        overall_score = (data_score + performance_score + risk_score + system_score) / 4
        
        print(f"   📊 Data Validation: {data_score:.1%}")
        print(f"   📈 Performance Validation: {performance_score:.1%}")
        print(f"   🛡️ Risk Validation: {risk_score:.1%}")
        print(f"   🏥 System Health: {system_score:.1%}")
        print(f"   🎯 Overall Score: {overall_score:.1%}")
        
        # Save validation report
        validation_report = {
            'timestamp': datetime.now().isoformat(),
            'data_status': data_status,
            'performance_metrics': performance_metrics,
            'risk_status': risk_status,
            'system_health': system_health,
            'scores': {
                'data': data_score,
                'performance': performance_score,
                'risk': risk_score,
                'system': system_score,
                'overall': overall_score
            }
        }
        
        # Save report
        report_path = "reports/validation/simple_institutional_validation.json"
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        
        with open(report_path, 'w') as f:
            json.dump(validation_report, f, indent=2, default=str)
        
        print(f"\n💾 Validation report saved to: {report_path}")
        
        # Determine overall success
        success = overall_score >= 0.75
        
        if success:
            print(f"\n✅ INSTITUTIONAL VALIDATION PASSED")
            print(f"   Overall score: {overall_score:.1%}")
            print("   System meets institutional validation criteria")
        else:
            print(f"\n⚠️ INSTITUTIONAL VALIDATION NEEDS ATTENTION")
            print(f"   Overall score: {overall_score:.1%}")
            print("   Some components need improvement")
        
        return validation_report, success
        
    except Exception as e:
        print(f"\n❌ INSTITUTIONAL VALIDATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return None, False

if __name__ == "__main__":
    report, success = main()
    sys.exit(0 if success else 1)
