#!/usr/bin/env python3
"""
🔍 NORTHSTAR V3 SYSTEM STATUS CHECKER
Comprehensive system health and data availability checker

Checks all system components, data freshness, and readiness status.
"""

import os
import sys
import pandas as pd
import json
from datetime import datetime, timedelta
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

class SystemStatusChecker:
    """Comprehensive system status checker"""
    
    def __init__(self):
        self.status = {
            'data_availability': {},
            'system_health': {},
            'component_status': {},
            'data_freshness': {},
            'recommendations': []
        }
    
    def check_data_availability(self):
        """Check availability of key data files"""
        
        print("📊 CHECKING DATA AVAILABILITY")
        print("-" * 40)
        
        # Critical data files
        critical_files = {
            'Market State': 'data/processed/market_state.parquet',
            'Strategy Beliefs': 'data/processed/strategy_beliefs.parquet',
            'Portfolio Weights': 'data/processed/portfolio_weights.parquet',
            'Price Data': 'data/raw/prices_daily/',
            'RBI Macro Data': 'data/macro/raw/',
            'Universe Definition': 'universe/nifty500.csv'
        }
        
        # Optional data files
        optional_files = {
            'PnL Data': 'data/portfolio/pnl_on_paper.parquet',
            'Backtest Results': 'data/backtests/',
            'Shadow Trading': 'data/live/shadow_trading/',
            'Performance Reports': 'reports/performance/',
            'Validation Results': 'data/validation/'
        }
        
        all_files = {**critical_files, **optional_files}
        
        for name, path in all_files.items():
            exists = os.path.exists(path)
            is_critical = name in [k for k in critical_files.keys()]
            
            if exists:
                if os.path.isdir(path):
                    file_count = len([f for f in os.listdir(path) if not f.startswith('.')])
                    size_info = f"({file_count} files)"
                else:
                    size_mb = os.path.getsize(path) / (1024 * 1024)
                    size_info = f"({size_mb:.1f} MB)"
                
                status_icon = "✅"
                status_text = f"Available {size_info}"
            else:
                status_icon = "❌" if is_critical else "⚠️"
                status_text = "Missing"
            
            print(f"   {status_icon} {name:<20} {status_text}")
            
            self.status['data_availability'][name] = {
                'exists': exists,
                'path': path,
                'critical': is_critical,
                'status': 'available' if exists else 'missing'
            }
    
    def check_data_freshness(self):
        """Check freshness of time-sensitive data"""
        
        print(f"\n🕒 CHECKING DATA FRESHNESS")
        print("-" * 40)
        
        freshness_checks = {
            'Market State': 'data/processed/market_state.parquet',
            'Price Data': 'data/raw/prices_daily/',
            'RBI Data': 'data/macro/raw/',
            'Portfolio Weights': 'data/processed/portfolio_weights.parquet'
        }
        
        for name, path in freshness_checks.items():
            if os.path.exists(path):
                try:
                    if os.path.isdir(path):
                        # Get newest file in directory
                        files = [os.path.join(path, f) for f in os.listdir(path) if not f.startswith('.')]
                        if files:
                            newest_file = max(files, key=os.path.getmtime)
                            mod_time = datetime.fromtimestamp(os.path.getmtime(newest_file))
                        else:
                            mod_time = None
                    else:
                        mod_time = datetime.fromtimestamp(os.path.getmtime(path))
                    
                    if mod_time:
                        age_hours = (datetime.now() - mod_time).total_seconds() / 3600
                        
                        if age_hours < 4:
                            status_icon = "✅"
                            freshness = "Fresh"
                        elif age_hours < 24:
                            status_icon = "⚠️"
                            freshness = "Stale"
                        else:
                            status_icon = "❌"
                            freshness = "Old"
                        
                        age_str = f"{age_hours:.1f}h ago"
                        print(f"   {status_icon} {name:<20} {freshness} ({age_str})")
                        
                        self.status['data_freshness'][name] = {
                            'age_hours': age_hours,
                            'freshness': freshness.lower(),
                            'last_updated': mod_time.isoformat()
                        }
                    else:
                        print(f"   ⚠️ {name:<20} No files found")
                        self.status['data_freshness'][name] = {'status': 'no_files'}
                        
                except Exception as e:
                    print(f"   ❌ {name:<20} Error checking: {e}")
                    self.status['data_freshness'][name] = {'status': 'error', 'error': str(e)}
            else:
                print(f"   ❌ {name:<20} Not found")
                self.status['data_freshness'][name] = {'status': 'missing'}
    
    def check_system_components(self):
        """Check system component availability"""
        
        print(f"\n🧩 CHECKING SYSTEM COMPONENTS")
        print("-" * 40)
        
        components = {
            'Data Pipeline': 'src/ingestion/integrated_data_pipeline.py',
            'Backtest Engine': 'src/backtesting/backtest_engine.py',
            'Brain Window': 'src/dashboard/brain_window.py',
            'Master Orchestrator': 'src/orchestrator/master_orchestrator.py',
            'Risk Coordinator': 'src/risk/unified_risk_coordinator.py',
            'Portfolio Coordinator': 'src/portfolio/unified_portfolio_coordinator.py',
            'Intelligence Engine': 'src/intelligence/unified_intelligence_engine.py',
            'Market Brain': 'src/intelligence/market_brain/',
            'Validation Suite': 'src/validation/',
            'Main Entry Point': 'run.py'
        }
        
        for name, path in components.items():
            exists = os.path.exists(path)
            status_icon = "✅" if exists else "❌"
            status_text = "Available" if exists else "Missing"
            
            print(f"   {status_icon} {name:<20} {status_text}")
            
            self.status['component_status'][name] = {
                'exists': exists,
                'path': path
            }
    
    def check_system_health(self):
        """Check overall system health"""
        
        print(f"\n🏥 CHECKING SYSTEM HEALTH")
        print("-" * 40)
        
        health_checks = []
        
        # Check Python environment
        try:
            import pandas, numpy, streamlit, plotly
            health_checks.append(("Python Dependencies", True, "All key packages available"))
        except ImportError as e:
            health_checks.append(("Python Dependencies", False, f"Missing packages: {e}"))
        
        # Check disk space
        try:
            import shutil
            total, used, free = shutil.disk_usage(".")
            free_gb = free / (1024**3)
            
            if free_gb > 5:
                health_checks.append(("Disk Space", True, f"{free_gb:.1f} GB free"))
            else:
                health_checks.append(("Disk Space", False, f"Low space: {free_gb:.1f} GB"))
        except Exception as e:
            health_checks.append(("Disk Space", False, f"Error checking: {e}"))
        
        # Check data directories
        data_dirs = ['data', 'logs', 'reports', 'backups']
        missing_dirs = [d for d in data_dirs if not os.path.exists(d)]
        
        if not missing_dirs:
            health_checks.append(("Directory Structure", True, "All directories present"))
        else:
            health_checks.append(("Directory Structure", False, f"Missing: {missing_dirs}"))
        
        # Check configuration
        config_files = ['config/paths.yaml', 'requirements.txt']
        missing_configs = [c for c in config_files if not os.path.exists(c)]
        
        if not missing_configs:
            health_checks.append(("Configuration", True, "All config files present"))
        else:
            health_checks.append(("Configuration", False, f"Missing: {missing_configs}"))
        
        # Display health check results
        for name, status, message in health_checks:
            status_icon = "✅" if status else "❌"
            print(f"   {status_icon} {name:<20} {message}")
            
            self.status['system_health'][name] = {
                'status': 'healthy' if status else 'unhealthy',
                'message': message
            }
    
    def generate_recommendations(self):
        """Generate system recommendations"""
        
        recommendations = []
        
        # Data availability recommendations
        missing_critical = [
            name for name, info in self.status['data_availability'].items()
            if info['critical'] and not info['exists']
        ]
        
        if missing_critical:
            recommendations.append({
                'priority': 'high',
                'category': 'data',
                'issue': f"Missing critical data: {', '.join(missing_critical)}",
                'action': "Run: python run_complete_v3_system.py --data-only"
            })
        
        # Data freshness recommendations
        stale_data = [
            name for name, info in self.status['data_freshness'].items()
            if isinstance(info, dict) and info.get('freshness') in ['stale', 'old']
        ]
        
        if stale_data:
            recommendations.append({
                'priority': 'medium',
                'category': 'freshness',
                'issue': f"Stale data: {', '.join(stale_data)}",
                'action': "Run: python run.py --mode update"
            })
        
        # System health recommendations
        unhealthy_components = [
            name for name, info in self.status['system_health'].items()
            if info['status'] == 'unhealthy'
        ]
        
        if unhealthy_components:
            recommendations.append({
                'priority': 'high',
                'category': 'health',
                'issue': f"Unhealthy components: {', '.join(unhealthy_components)}",
                'action': "Check system requirements and dependencies"
            })
        
        # Missing components recommendations
        missing_components = [
            name for name, info in self.status['component_status'].items()
            if not info['exists']
        ]
        
        if missing_components:
            recommendations.append({
                'priority': 'high',
                'category': 'components',
                'issue': f"Missing components: {', '.join(missing_components)}",
                'action': "Verify system installation and file integrity"
            })
        
        self.status['recommendations'] = recommendations
        
        return recommendations
    
    def print_recommendations(self, recommendations):
        """Print system recommendations"""
        
        if not recommendations:
            print(f"\n✅ SYSTEM STATUS: EXCELLENT")
            print("   No issues found. System is ready for operation.")
            return
        
        print(f"\n📋 RECOMMENDATIONS")
        print("-" * 40)
        
        for i, rec in enumerate(recommendations, 1):
            priority_icon = "🔴" if rec['priority'] == 'high' else "🟡" if rec['priority'] == 'medium' else "🟢"
            print(f"{i}. {priority_icon} {rec['issue']}")
            print(f"   Action: {rec['action']}")
            print()
    
    def save_status_report(self):
        """Save detailed status report"""
        
        # Add summary
        self.status['summary'] = {
            'timestamp': datetime.now().isoformat(),
            'critical_data_missing': len([
                name for name, info in self.status['data_availability'].items()
                if info['critical'] and not info['exists']
            ]),
            'components_missing': len([
                name for name, info in self.status['component_status'].items()
                if not info['exists']
            ]),
            'health_issues': len([
                name for name, info in self.status['system_health'].items()
                if info['status'] == 'unhealthy'
            ]),
            'recommendations_count': len(self.status['recommendations'])
        }
        
        # Save report
        report_dir = Path("reports/system")
        report_dir.mkdir(parents=True, exist_ok=True)
        
        report_file = report_dir / f"system_status_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_file, 'w') as f:
            json.dump(self.status, f, indent=2)
        
        return report_file
    
    def run_complete_check(self):
        """Run complete system status check"""
        
        print("🔍 NORTHSTAR V3 SYSTEM STATUS CHECK")
        print("=" * 50)
        print(f"   Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Run all checks
        self.check_data_availability()
        self.check_data_freshness()
        self.check_system_components()
        self.check_system_health()
        
        # Generate and display recommendations
        recommendations = self.generate_recommendations()
        self.print_recommendations(recommendations)
        
        # Save report
        report_file = self.save_status_report()
        
        print(f"📄 Detailed report saved to: {report_file}")
        
        return len(recommendations) == 0

def main():
    """Main function"""
    
    checker = SystemStatusChecker()
    system_healthy = checker.run_complete_check()
    
    if system_healthy:
        print(f"\n🚀 READY TO LAUNCH")
        print("   System is healthy and ready for operation")
        print("   Recommended next steps:")
        print("     python launch_dashboard.py              # Launch V3 dashboard")
        print("     python run_complete_v3_system.py        # Full pipeline")
        print("     python run.py --mode update             # Quick update")
    else:
        print(f"\n⚠️ SYSTEM NEEDS ATTENTION")
        print("   Please address the recommendations above before proceeding")
    
    return 0 if system_healthy else 1

if __name__ == "__main__":
    sys.exit(main())