#!/usr/bin/env python3
"""
📊 CHECK V3 SYSTEM STATUS
Comprehensive status check for all Northstar V3 components

This script checks:
1. Data freshness (RBI, market data, portfolios)
2. Intelligence components (beta drift, anticipatory, narratives)
3. Validation systems (shadow trading, stress tests)
4. System health (integrations, dashboards)
5. Performance metrics (recent runs, success rates)

Usage:
    python3 scripts/check_v3_system_status.py
    python3 scripts/check_v3_system_status.py --detailed
"""

import os
import sys
import json
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
from typing import Dict, List, Iterable, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class V3SystemStatusChecker:
    """Comprehensive V3 system status checker"""
    
    def __init__(self, detailed=False):
        self.detailed = detailed
        self.status = {
            'data': {},
            'intelligence': {},
            'validation': {},
            'system': {},
            'performance': {}
        }
        
        print("📊 NORTHSTAR V3 SYSTEM STATUS CHECK")
        print("=" * 50)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)

    @staticmethod
    def _age_hours(path: Path) -> float:
        return (datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)).total_seconds() / 3600

    @staticmethod
    def _status_by_age(age_hours: float, green_hours: float, yellow_hours: float) -> str:
        if age_hours < green_hours:
            return "🟢"
        if age_hours < yellow_hours:
            return "🟡"
        return "🔴"

    def _collect_files(
        self,
        candidates: Iterable[str],
        patterns: Iterable[str] = ("*.json", "*.parquet", "*.md"),
        recursive: bool = True,
    ) -> List[Path]:
        files: List[Path] = []
        for raw in candidates:
            p = Path(raw)
            if not p.exists():
                continue
            if p.is_file():
                files.append(p)
                continue
            if p.is_dir():
                for pat in patterns:
                    files.extend(p.rglob(pat) if recursive else p.glob(pat))
        # Deduplicate while preserving stable sort by mtime later.
        uniq = sorted({str(f): f for f in files}.values(), key=lambda x: x.stat().st_mtime)
        return uniq

    def _print_component_status(
        self,
        label: str,
        candidates: Iterable[str],
        patterns: Iterable[str] = ("*.json", "*.parquet", "*.md"),
        recursive: bool = True,
        green_hours: float = 72.0,
        yellow_hours: float = 168.0,
    ) -> Tuple[str, int, float]:
        files = self._collect_files(candidates, patterns=patterns, recursive=recursive)
        if not files:
            print(f"{label}: 🔴 Not found")
            return "🔴", 0, float("inf")
        latest = files[-1]
        age_hours = self._age_hours(latest)
        status = self._status_by_age(age_hours, green_hours=green_hours, yellow_hours=yellow_hours)
        print(f"{label}: {status} {len(files)} files, latest {age_hours:.1f}h ago")
        return status, len(files), age_hours
    
    def check_data_status(self):
        """Check data freshness and availability"""
        
        print("\n📁 DATA STATUS")
        print("-" * 20)
        
        data_status = {}
        
        # RBI Data
        rbi_dir = Path("data/macro/raw")
        if rbi_dir.exists():
            csv_files = list(rbi_dir.glob("*.csv"))
            if csv_files:
                latest_file = max(csv_files, key=lambda f: f.stat().st_mtime)
                age_hours = (datetime.now() - datetime.fromtimestamp(latest_file.stat().st_mtime)).total_seconds() / 3600
                data_status['rbi'] = {
                    'files': len(csv_files),
                    'latest': latest_file.name,
                    'age_hours': age_hours,
                    'status': '🟢' if age_hours < 48 else '🟡' if age_hours < 168 else '🔴'
                }
                print(f"🏛️ RBI Data: {data_status['rbi']['status']} {len(csv_files)} files, latest {age_hours:.1f}h ago")
            else:
                data_status['rbi'] = {'status': '🔴', 'error': 'No CSV files found'}
                print("🏛️ RBI Data: 🔴 No CSV files found")
        else:
            data_status['rbi'] = {'status': '🔴', 'error': 'Directory not found'}
            print("🏛️ RBI Data: 🔴 Directory not found")
        
        # Market Data (canonical + fallback artifacts)
        market_candidates = [
            ("📈 market_data_latest.json", ["data/options/live/market_data_latest.json"], ("*.json",)),
            ("📈 market_state.parquet", ["data/processed/market_state.parquet", "data/processed/intelligent_market_state.parquet"], ("*.parquet",)),
            ("📈 prices_daily", ["data/raw/prices_daily"], ("*.csv",)),
        ]
        for label, cands, pats in market_candidates:
            if "prices_daily" in label:
                files = self._collect_files(cands, patterns=pats, recursive=False)
                if files:
                    print(f"{label}: 🟢 {len(files)} price files")
                else:
                    print(f"{label}: 🔴 Not found")
                continue
            files = self._collect_files(cands, patterns=pats, recursive=False)
            if files:
                latest = files[-1]
                age_hours = self._age_hours(latest)
                status = self._status_by_age(age_hours, green_hours=24.0, yellow_hours=72.0)
                print(f"{label}: {status} Updated {age_hours:.1f}h ago")
            else:
                print(f"{label}: 🔴 Not found")

        # Portfolio Data (allow runtime state fallback for current positions freshness)
        portfolio_checks = [
            ("💼 portfolio_weights.parquet", ["data/processed/portfolio_weights.parquet"], ("*.parquet",), 48.0, 168.0),
            (
                "💼 current_positions.json",
                ["data/portfolio/current_positions.json", "data/options/live/options_runtime_state.json"],
                ("*.json",),
                48.0,
                168.0,
            ),
        ]
        for label, cands, pats, green_h, yellow_h in portfolio_checks:
            files = self._collect_files(cands, patterns=pats, recursive=False)
            if files:
                latest = files[-1]
                age_hours = self._age_hours(latest)
                status = self._status_by_age(age_hours, green_hours=green_h, yellow_hours=yellow_h)
                print(f"{label}: {status} Updated {age_hours:.1f}h ago")
            else:
                print(f"{label}: 🔴 Not found")
        
        self.status['data'] = data_status
    
    def check_intelligence_status(self):
        """Check intelligence components"""
        
        print("\n🧠 INTELLIGENCE STATUS")
        print("-" * 25)
        
        intelligence_components = [
            ("🤖 Beta Drift Fabric", ["data/intelligence/beta_drift", "data/beta_drift_insights", "data/processed/regime_drift_monitor.json"]),
            ("🤖 Anticipatory Intelligence", ["data/anticipatory", "data/processed/anticipatory_intelligence.json", "data/processed/anticipatory_signals.json", "data/processed/anticipatory_capital_allocations.parquet"]),
            (
                "🤖 Market Brain",
                [
                    "data/intelligence/market_brain",
                    "data/processed/market_brain_state.json",
                    "data/processed/enhanced_market_brain_state.json",
                    "data/processed/market_beliefs.json",
                    # Current production market-brain outputs
                    "data/processed/pulse_state.json",
                    "data/processed/survival_metrics.parquet",
                    "data/processed/system_stress.json",
                ],
            ),
            ("🤖 Narrative Engine", ["data/intelligence/narratives", "data/reports/daily_narrative.json", "data/processed/narrative_state.parquet", "data/processed/narrative_events.parquet"]),
            ("🤖 Regime Memory", ["data/intelligence/regime_memory", "data/processed/regime_fingerprints.parquet", "data/processed/regime_transitions.parquet", "data/processed/regime_metadata.json"]),
        ]
        for label, candidates in intelligence_components:
            self._print_component_status(
                label,
                candidates=candidates,
                patterns=("*.json", "*.parquet"),
                recursive=True,
                green_hours=72.0,
                yellow_hours=168.0,
            )
    
    def check_validation_status(self):
        """Check validation systems"""
        
        print("\n🔍 VALIDATION STATUS")
        print("-" * 22)
        
        validation_components = [
            ("✅ Shadow Trading", ["data/validation/shadow", "data/live/shadow_trading", "data/processed/shadow_trading_snapshot.json", "data/shadow_reality"]),
            ("✅ Stress Tests", ["data/validation/stress", "data/validation/stress_tests", "data/risk/stress_tests.parquet", "data/processed/system_stress.json"]),
            ("✅ Walk Forward", ["data/validation/walk_forward", "data/validation/walk_forward_results.json", "data/validation/walk_forward_results.parquet", "data/validation/interactive/walkforward_results.json"]),
            ("✅ Institutional Reports", ["data/validation/institutional_complete", "data/validation/institutional_real_data", "data/validation/institutional_final"]),
            ("✅ Crisis Validation", ["data/validation/crisis", "data/validation/crisis_periods.json", "data/validation/brutal_periods"]),
        ]
        for label, candidates in validation_components:
            self._print_component_status(
                label,
                candidates=candidates,
                patterns=("*.json", "*.md", "*.parquet", "*.txt"),
                recursive=True,
                green_hours=168.0,
                yellow_hours=336.0,
            )
    
    def check_system_health(self):
        """Check system health and integrations"""
        
        print("\n🔧 SYSTEM HEALTH")
        print("-" * 18)
        
        system_components = [
            ("⚙️ System State", ["data/state/system_state.json", "data/options/live/options_runtime_state.json", "data/state/unified_state.json", "data/processed/system_execution_log.json"]),
            ("⚙️ Market State", ["data/processed/market_state.parquet", "data/processed/intelligent_market_state.parquet"]),
            ("⚙️ Configuration", [str(Path("config") / "operation" / ("operation_" "config.yaml")), "config/northstar_daemon.yaml", "config/options_trading.yaml"]),
            ("⚙️ Deployment State", ["data/deployment_state.json", "data/options/live/northstar_daemon_status.json", "logs/production_deployment.log"]),
        ]
        for label, candidates in system_components:
            files = self._collect_files(candidates, patterns=("*.json", "*.parquet", "*.yaml", "*.log"), recursive=False)
            if files:
                latest = files[-1]
                age_hours = self._age_hours(latest)
                status = self._status_by_age(age_hours, green_hours=168.0, yellow_hours=720.0)
                print(f"{label}: {status} Available ({age_hours:.1f}h ago)")
            else:
                print(f"{label}: 🔴 Not found")

        # Check dashboard availability (current V3 set)
        dashboard_files = [
            "src/dashboard/northstar_v3_ultimate_integrated_dashboard.py",
            "src/dashboard/northstar_v3_production_dashboard.py",
            "src/dashboard/production_grade_dashboard.py",
        ]
        dashboard_count = sum(1 for f in dashboard_files if Path(f).exists())
        status = "🟢" if dashboard_count == len(dashboard_files) else ("🟡" if dashboard_count > 0 else "🔴")
        print(f"📊 Dashboards: {status} {dashboard_count}/{len(dashboard_files)} available")
    
    def check_performance_metrics(self):
        """Check recent performance and runs"""
        
        print("\n📈 PERFORMANCE METRICS")
        print("-" * 25)
        
        # Check log files for recent activity
        log_dirs = [
            "logs/system",
            "logs/operation",
            "logs/performance",
            "logs",
            "logs/daemon_managed",
        ]
        
        recent_activity = False
        for log_dir in log_dirs:
            path = Path(log_dir)
            if path.exists():
                log_files = list(path.glob("*.log"))
                if log_files:
                    latest = max(log_files, key=lambda f: f.stat().st_mtime)
                    age_hours = (datetime.now() - datetime.fromtimestamp(latest.stat().st_mtime)).total_seconds() / 3600
                    if age_hours < 24:
                        recent_activity = True
                        print(f"📝 {log_dir}: 🟢 Recent activity ({age_hours:.1f}h ago)")
                    else:
                        print(f"📝 {log_dir}: 🟡 Last activity {age_hours:.1f}h ago")
        
        if not recent_activity:
            print("📝 System Activity: 🟡 No recent activity detected")
        
        # Check truth mode runs
        truth_candidates = ["truth_mode_runs", "data/truth_reviews"]
        truth_files = self._collect_files(truth_candidates, patterns=("*.json", "*.md"), recursive=True)
        if truth_files:
            latest = truth_files[-1]
            age_hours = self._age_hours(latest)
            status = self._status_by_age(age_hours, green_hours=336.0, yellow_hours=1440.0)
            print(f"🎯 Truth Mode: {status} {len(truth_files)} runs, latest {age_hours:.1f}h ago")
        else:
            print("🎯 Truth Mode: 🔴 Directory not found")
    
    def generate_recommendations(self):
        """Generate recommendations based on status"""
        
        print("\n💡 RECOMMENDATIONS")
        print("-" * 20)
        
        recommendations = []
        
        # Data recommendations
        if 'rbi' in self.status['data']:
            rbi_status = self.status['data']['rbi']
            if rbi_status.get('age_hours', 999) > 48:
                recommendations.append("🔄 Update RBI data: python3 scripts/update_real_data.py --rbi-only")
        
        # Check if portfolio is old
        portfolio_path = Path("data/processed/portfolio_weights.parquet")
        if portfolio_path.exists():
            age_hours = (datetime.now() - datetime.fromtimestamp(portfolio_path.stat().st_mtime)).total_seconds() / 3600
            if age_hours > 168:  # 1 week
                recommendations.append("💼 Regenerate portfolio: python3 scripts/generate_portfolio.py")
        
        beta_drift_path = Path("data/beta_drift_insights")
        if not beta_drift_path.exists():
            recommendations.append("🧠 Build intelligence: python3 scripts/build_beta_drift_fabric.py")

        recommendations.extend([
            "⚡ Quick activation: python3 scripts/quick_activate_v3_essentials.py",
            "🚀 Full activation: python3 scripts/activate_full_northstar_v3_system.py",
            "📊 Launch dashboard: python3 -m streamlit run src/dashboard/northstar_v3_ultimate_integrated_dashboard.py --server.port 8517 --server.address 127.0.0.1 --server.headless true"
        ])
        
        for rec in recommendations[:5]:  # Show top 5
            print(f"   {rec}")
    
    def run_status_check(self):
        """Run complete status check"""
        
        try:
            self.check_data_status()
            self.check_intelligence_status()
            self.check_validation_status()
            self.check_system_health()
            self.check_performance_metrics()
            self.generate_recommendations()
            
            print(f"\n{'='*50}")
            print("📊 STATUS CHECK COMPLETE")
            print(f"{'='*50}")
            
        except Exception as e:
            print(f"\n❌ Status check error: {e}")

def main():
    """Main function"""
    
    import argparse
    parser = argparse.ArgumentParser(description="Check V3 System Status")
    parser.add_argument("--detailed", action="store_true", help="Show detailed status information")
    
    args = parser.parse_args()
    
    checker = V3SystemStatusChecker(detailed=args.detailed)
    checker.run_status_check()

if __name__ == "__main__":
    main()
