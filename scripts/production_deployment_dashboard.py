#!/usr/bin/env python3
"""
Production Deployment Dashboard

Real-time dashboard for monitoring production deployment phases:
1. Shadow Trading Validation Status
2. 90-Day Discipline Period Progress
3. Psychological Safeguards Status
4. Production Readiness Assessment
5. Live Trading Monitoring

Provides comprehensive visibility into deployment progress and system health.
"""

import sys
import os
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "northstar_c" / "src"))

# Import deployment components
from scripts.execute_shadow_trading_validation import ProductionDeploymentOrchestrator, DeploymentPhase, ValidationStatus
from scripts.launch_comprehensive_shadow_trading import ComprehensiveShadowTradingSystem

# Import safeguard systems
from northstar_c.src.tier2.anti_override_system import AntiOverrideSystem
from northstar_c.src.tier2.truth_review_system import TruthReviewSystem
from northstar_c.src.tier2.decision_logger import DecisionLogger


class ProductionDeploymentDashboard:
    """Real-time production deployment monitoring dashboard"""
    
    def __init__(self):
        self.deployment_orchestrator = ProductionDeploymentOrchestrator()
        self.shadow_system = ComprehensiveShadowTradingSystem()
        
        # Initialize safeguard systems for monitoring
        self.decision_logger = DecisionLogger()
        self.anti_override_system = AntiOverrideSystem(self.decision_logger)
        self.truth_review_system = TruthReviewSystem(self.decision_logger)
        
        # Dashboard state
        self.last_update = None
        self.dashboard_data = {}
        
    def collect_dashboard_data(self) -> Dict[str, Any]:
        """Collect all dashboard data"""
        dashboard_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'shadow_trading_status': self._get_shadow_trading_status(),
            'deployment_phase_status': self._get_deployment_phase_status(),
            'safeguards_status': self._get_safeguards_status(),
            'performance_metrics': self._get_performance_metrics(),
            'validation_criteria': self._get_validation_criteria(),
            'system_health': self._get_system_health(),
            'next_actions': self._get_next_actions()
        }
        
        self.dashboard_data = dashboard_data
        self.last_update = datetime.now(timezone.utc)
        
        return dashboard_data
    
    def _get_shadow_trading_status(self) -> Dict[str, Any]:
        """Get shadow trading system status"""
        try:
            # Initialize shadow system if needed
            if not hasattr(self.shadow_system, 'trading_state'):
                self.shadow_system.initialize_system()
            
            status = self.shadow_system.get_system_status()
            
            # Get recent performance data
            validation_report = self.shadow_system.generate_validation_report()
            
            return {
                'system_active': status.get('system_active', False),
                'last_trading_date': status.get('last_trading_date'),
                'total_trading_days': status.get('total_trading_days', 0),
                'cumulative_return': status.get('cumulative_return', 0.0),
                'validation_score': status.get('validation_score', 0.0),
                'production_ready': status.get('production_ready', False),
                'performance_metrics': validation_report.get('performance_metrics', {}),
                'criteria_assessment': validation_report.get('validation_assessment', {})
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'system_active': False,
                'status': 'error'
            }
    
    def _get_deployment_phase_status(self) -> Dict[str, Any]:
        """Get deployment phase status"""
        try:
            deployment_state = self.deployment_orchestrator.deployment_state
            
            phases_status = {}
            
            for phase in DeploymentPhase:
                phase_key = phase.value
                
                if phase_key in deployment_state.get('phase_results', {}):
                    phase_result = deployment_state['phase_results'][phase_key]
                    phases_status[phase_key] = {
                        'status': phase_result.get('status', 'not_started'),
                        'validation_score': phase_result.get('validation_score', 0.0),
                        'next_phase_approved': phase_result.get('next_phase_approved', False),
                        'start_date': phase_result.get('start_date'),
                        'end_date': phase_result.get('end_date'),
                        'criteria_met': phase_result.get('criteria_met', {}),
                        'recommendations': phase_result.get('recommendations', [])
                    }
                else:
                    phases_status[phase_key] = {
                        'status': 'not_started',
                        'validation_score': 0.0,
                        'next_phase_approved': False
                    }
            
            return {
                'current_phase': deployment_state.get('current_phase', 'shadow_validation'),
                'production_approved': deployment_state.get('production_approved', False),
                'phases': phases_status,
                'overall_progress': self._calculate_overall_progress(phases_status)
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'current_phase': 'unknown',
                'production_approved': False
            }
    
    def _get_safeguards_status(self) -> Dict[str, Any]:
        """Get psychological safeguards status"""
        try:
            # Anti-override system status
            override_stats = self.anti_override_system.get_override_statistics(days=30)
            
            # Truth review system status
            recent_reviews = self.truth_review_system.get_recent_reviews(count=3)
            
            # Decision logging status
            decision_stats = {
                'total_decisions': len(self.decision_logger.decisions),
                'recent_decisions': len([
                    d for d in self.decision_logger.decisions
                    if d.timestamp > datetime.now(timezone.utc) - timedelta(days=7)
                ])
            }
            
            return {
                'anti_override_system': {
                    'active': True,
                    'override_attempts_30d': override_stats.get('total_attempts', 0),
                    'block_rate': override_stats.get('block_rate', 0.0),
                    'current_stress_level': override_stats.get('current_stress_level', 1)
                },
                'truth_review_system': {
                    'active': True,
                    'recent_reviews_count': len(recent_reviews),
                    'last_review_date': recent_reviews[0].generation_timestamp.isoformat() if recent_reviews else None
                },
                'decision_logging': {
                    'active': True,
                    'total_decisions': decision_stats['total_decisions'],
                    'recent_decisions_7d': decision_stats['recent_decisions']
                }
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'systems_active': False
            }
    
    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics"""
        try:
            shadow_status = self._get_shadow_trading_status()
            performance = shadow_status.get('performance_metrics', {})
            
            # Calculate additional metrics
            metrics = {
                'returns': {
                    'total_return': performance.get('total_return', 0.0),
                    'average_daily_return': performance.get('average_daily_return', 0.0),
                    'annualized_return': performance.get('average_daily_return', 0.0) * 252
                },
                'risk': {
                    'volatility': performance.get('volatility', 0.0),
                    'max_drawdown': performance.get('max_drawdown', 0.0),
                    'current_drawdown': performance.get('current_drawdown', 0.0),
                    'sharpe_ratio': performance.get('sharpe_ratio', 0.0)
                },
                'consistency': {
                    'win_rate': performance.get('win_rate', 0.0),
                    'win_days': performance.get('win_days', 0),
                    'loss_days': performance.get('loss_days', 0),
                    'trading_days': performance.get('trading_days', 0)
                }
            }
            
            return metrics
            
        except Exception as e:
            return {
                'error': str(e),
                'metrics_available': False
            }
    
    def _get_validation_criteria(self) -> Dict[str, Any]:
        """Get validation criteria status for each phase"""
        criteria = {
            'shadow_validation': {
                'min_trading_days': {'target': 20, 'current': 0, 'met': False},
                'min_sharpe_ratio': {'target': 1.0, 'current': 0.0, 'met': False},
                'max_drawdown': {'target': 0.05, 'current': 0.0, 'met': False},
                'min_win_rate': {'target': 0.6, 'current': 0.0, 'met': False}
            },
            'discipline_period': {
                'min_trading_days': {'target': 60, 'current': 0, 'met': False},
                'min_sharpe_ratio': {'target': 1.2, 'current': 0.0, 'met': False},
                'max_drawdown': {'target': 0.05, 'current': 0.0, 'met': False},
                'min_win_rate': {'target': 0.65, 'current': 0.0, 'met': False}
            },
            'production_deployment': {
                'production_certificate': {'target': 0.8, 'current': 0.0, 'met': False},
                'safeguards_active': {'target': True, 'current': False, 'met': False},
                'monitoring_systems': {'target': True, 'current': False, 'met': False}
            }
        }
        
        # Update with actual data
        try:
            shadow_status = self._get_shadow_trading_status()
            performance = shadow_status.get('performance_metrics', {})
            
            # Update shadow validation criteria
            criteria['shadow_validation']['min_trading_days']['current'] = performance.get('trading_days', 0)
            criteria['shadow_validation']['min_trading_days']['met'] = performance.get('trading_days', 0) >= 20
            
            criteria['shadow_validation']['min_sharpe_ratio']['current'] = performance.get('sharpe_ratio', 0.0)
            criteria['shadow_validation']['min_sharpe_ratio']['met'] = performance.get('sharpe_ratio', 0.0) >= 1.0
            
            criteria['shadow_validation']['max_drawdown']['current'] = abs(performance.get('max_drawdown', 0.0))
            criteria['shadow_validation']['max_drawdown']['met'] = abs(performance.get('max_drawdown', 0.0)) <= 0.05
            
            criteria['shadow_validation']['min_win_rate']['current'] = performance.get('win_rate', 0.0)
            criteria['shadow_validation']['min_win_rate']['met'] = performance.get('win_rate', 0.0) >= 0.6
            
        except Exception:
            pass
        
        return criteria
    
    def _get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status"""
        try:
            health_checks = {
                'shadow_trading_active': False,
                'data_pipeline_healthy': False,
                'safeguards_operational': False,
                'monitoring_active': False,
                'validation_passing': False
            }
            
            # Check shadow trading
            shadow_status = self._get_shadow_trading_status()
            health_checks['shadow_trading_active'] = shadow_status.get('system_active', False)
            
            # Check validation
            health_checks['validation_passing'] = shadow_status.get('production_ready', False)
            
            # Check safeguards
            safeguards_status = self._get_safeguards_status()
            health_checks['safeguards_operational'] = not ('error' in safeguards_status)
            
            # Overall health score
            health_score = sum(health_checks.values()) / len(health_checks)
            
            return {
                'overall_health_score': health_score,
                'health_checks': health_checks,
                'status': 'healthy' if health_score >= 0.8 else 'warning' if health_score >= 0.6 else 'critical'
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'overall_health_score': 0.0,
                'status': 'critical'
            }
    
    def _get_next_actions(self) -> List[str]:
        """Get recommended next actions"""
        actions = []
        
        try:
            deployment_status = self._get_deployment_phase_status()
            shadow_status = self._get_shadow_trading_status()
            
            current_phase = deployment_status.get('current_phase', 'shadow_validation')
            
            if current_phase == 'shadow_validation':
                if not shadow_status.get('system_active', False):
                    actions.append("🚀 Start shadow trading system")
                elif shadow_status.get('total_trading_days', 0) < 20:
                    actions.append(f"📈 Continue shadow trading ({shadow_status.get('total_trading_days', 0)}/20 days)")
                elif not shadow_status.get('production_ready', False):
                    actions.append("📊 Improve performance metrics to meet validation criteria")
                else:
                    actions.append("✅ Shadow validation complete - proceed to discipline period")
            
            elif current_phase == 'discipline_period':
                actions.append("⏳ Execute 90-day discipline period with real capital constraints")
            
            elif current_phase == 'safeguards_implementation':
                actions.append("🛡️ Implement and test additional psychological safeguards")
            
            elif current_phase == 'production_deployment':
                actions.append("🎯 Deploy to production with full capital allocation")
            
            else:
                actions.append("📋 Review deployment status and continue current phase")
            
        except Exception:
            actions.append("🔧 Check system configuration and restart dashboard")
        
        return actions
    
    def _calculate_overall_progress(self, phases_status: Dict[str, Any]) -> float:
        """Calculate overall deployment progress"""
        total_phases = len(phases_status)
        completed_phases = sum(
            1 for phase in phases_status.values()
            if phase.get('status') == 'completed'
        )
        
        return completed_phases / total_phases if total_phases > 0 else 0.0
    
    def display_dashboard(self) -> None:
        """Display formatted dashboard"""
        data = self.collect_dashboard_data()
        
        # Clear screen
        os.system('clear' if os.name == 'posix' else 'cls')
        
        print("🚀 NORTHSTAR PRODUCTION DEPLOYMENT DASHBOARD 🚀")
        print("=" * 80)
        print(f"Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # System Health Overview
        health = data['system_health']
        health_emoji = "🟢" if health['status'] == 'healthy' else "🟡" if health['status'] == 'warning' else "🔴"
        print(f"{health_emoji} SYSTEM HEALTH: {health['status'].upper()} ({health['overall_health_score']:.1%})")
        print()
        
        # Deployment Phase Status
        deployment = data['deployment_phase_status']
        print(f"📋 DEPLOYMENT PROGRESS: {deployment['overall_progress']:.1%}")
        print(f"Current Phase: {deployment['current_phase'].replace('_', ' ').title()}")
        print(f"Production Approved: {'✅ YES' if deployment['production_approved'] else '❌ NO'}")
        print()
        
        # Phase Details
        print("📊 PHASE STATUS:")
        for phase_name, phase_data in deployment['phases'].items():
            status_emoji = {
                'completed': '✅',
                'in_progress': '🔄',
                'failed': '❌',
                'not_started': '⏸️'
            }.get(phase_data['status'], '❓')
            
            phase_title = phase_name.replace('_', ' ').title()
            score = phase_data['validation_score']
            print(f"  {status_emoji} {phase_title}: {score:.1%}")
        print()
        
        # Shadow Trading Status
        shadow = data['shadow_trading_status']
        if 'error' not in shadow:
            print("📈 SHADOW TRADING STATUS:")
            print(f"  System Active: {'✅ YES' if shadow['system_active'] else '❌ NO'}")
            print(f"  Trading Days: {shadow['total_trading_days']}")
            print(f"  Cumulative Return: {shadow['cumulative_return']:.2%}")
            print(f"  Validation Score: {shadow['validation_score']:.1%}")
            print(f"  Production Ready: {'✅ YES' if shadow['production_ready'] else '❌ NO'}")
        else:
            print(f"❌ SHADOW TRADING ERROR: {shadow['error']}")
        print()
        
        # Performance Metrics
        performance = data['performance_metrics']
        if 'error' not in performance:
            print("📊 PERFORMANCE METRICS:")
            print(f"  Total Return: {performance['returns']['total_return']:.2%}")
            print(f"  Sharpe Ratio: {performance['risk']['sharpe_ratio']:.2f}")
            print(f"  Max Drawdown: {performance['risk']['max_drawdown']:.2%}")
            print(f"  Win Rate: {performance['consistency']['win_rate']:.1%}")
        print()
        
        # Validation Criteria
        criteria = data['validation_criteria']
        print("✅ VALIDATION CRITERIA (Shadow Trading):")
        for criterion, details in criteria['shadow_validation'].items():
            status = "✅" if details['met'] else "❌"
            criterion_name = criterion.replace('_', ' ').title()
            if isinstance(details['target'], float):
                if 'rate' in criterion or 'return' in criterion:
                    print(f"  {status} {criterion_name}: {details['current']:.1%} (target: {details['target']:.1%})")
                else:
                    print(f"  {status} {criterion_name}: {details['current']:.3f} (target: {details['target']:.3f})")
            else:
                print(f"  {status} {criterion_name}: {details['current']} (target: {details['target']})")
        print()
        
        # Safeguards Status
        safeguards = data['safeguards_status']
        if 'error' not in safeguards:
            print("🛡️ PSYCHOLOGICAL SAFEGUARDS:")
            anti_override = safeguards['anti_override_system']
            print(f"  Anti-Override System: {'✅ ACTIVE' if anti_override['active'] else '❌ INACTIVE'}")
            print(f"  Override Attempts (30d): {anti_override['override_attempts_30d']}")
            print(f"  Block Rate: {anti_override['block_rate']:.1%}")
            
            truth_review = safeguards['truth_review_system']
            print(f"  Truth Review System: {'✅ ACTIVE' if truth_review['active'] else '❌ INACTIVE'}")
            print(f"  Recent Reviews: {truth_review['recent_reviews_count']}")
        print()
        
        # Next Actions
        actions = data['next_actions']
        print("🎯 NEXT ACTIONS:")
        for action in actions:
            print(f"  {action}")
        print()
        
        print("=" * 80)
        print("Press Ctrl+C to exit | Refreshes every 30 seconds")
    
    def run_dashboard(self, refresh_interval: int = 30) -> None:
        """Run dashboard with automatic refresh"""
        try:
            while True:
                self.display_dashboard()
                time.sleep(refresh_interval)
        except KeyboardInterrupt:
            print("\n\n👋 Dashboard stopped by user")


def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Production Deployment Dashboard")
    parser.add_argument('--refresh', type=int, default=30,
                       help='Dashboard refresh interval in seconds (default: 30)')
    parser.add_argument('--once', action='store_true',
                       help='Display dashboard once and exit')
    
    args = parser.parse_args()
    
    try:
        dashboard = ProductionDeploymentDashboard()
        
        if args.once:
            dashboard.display_dashboard()
        else:
            dashboard.run_dashboard(refresh_interval=args.refresh)
            
    except Exception as e:
        print(f"❌ Dashboard error: {e}")
        raise


if __name__ == "__main__":
    main()