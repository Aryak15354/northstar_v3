#!/usr/bin/env python3
"""
Weekly Research Review Script for Northstar V2

Performs comprehensive weekly review of research outputs, model performance,
and system health metrics.
"""

import sys
import os
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List
import pandas as pd
import numpy as np

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.options.accounting_integrity import AccountingIntegrityChecker
from src.options.capital_policy import CapitalPolicyManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WeeklyResearchReviewer:
    """Weekly research and system review"""
    
    def __init__(self):
        self.review_date = datetime.now()
        self.week_start = self.review_date - timedelta(days=7)
        self.integrity_checker = AccountingIntegrityChecker()
        self.capital_policy = CapitalPolicyManager()
        
        # Output directory
        self.output_dir = PROJECT_ROOT / "data/research/weekly_reviews"
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def run_weekly_review(self) -> Dict[str, Any]:
        """Run comprehensive weekly review"""
        logger.info("=" * 60)
        logger.info("NORTHSTAR V2 WEEKLY RESEARCH REVIEW")
        logger.info(f"Review Period: {self.week_start.date()} to {self.review_date.date()}")
        logger.info("=" * 60)
        
        review_report = {
            'timestamp': self.review_date.isoformat(),
            'review_period': {
                'start': self.week_start.isoformat(),
                'end': self.review_date.isoformat()
            },
            'sections': {}
        }
        
        # Run review sections
        review_report['sections']['performance'] = self.review_performance()
        review_report['sections']['research_outputs'] = self.review_research_outputs()
        review_report['sections']['model_performance'] = self.review_model_performance()
        review_report['sections']['system_health'] = self.review_system_health()
        review_report['sections']['governance_events'] = self.review_governance_events()
        review_report['sections']['capital_scaling'] = self.review_capital_scaling()
        review_report['sections']['recommendations'] = self.generate_recommendations(review_report)
        
        # Save report
        self.save_review_report(review_report)
        
        # Print summary
        self.print_review_summary(review_report)
        
        return review_report
    
    def review_performance(self) -> Dict[str, Any]:
        """Review weekly performance metrics"""
        logger.info("1. Reviewing performance metrics...")
        
        performance_review = {
            'weekly_pnl': 0.0,
            'weekly_return_pct': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'win_rate': 0.0,
            'total_trades': 0,
            'strategy_breakdown': {},
            'risk_metrics': {}
        }
        
        try:
            # Load runtime state for current equity
            runtime_file = PROJECT_ROOT / "data/options/live/options_runtime_state.json"
            if runtime_file.exists():
                with open(runtime_file, 'r') as f:
                    runtime_state = json.load(f)
                
                current_equity = runtime_state.get('net_equity', 0.0)
                week_start_equity = runtime_state.get('week_start_equity', current_equity)
                
                if week_start_equity > 0:
                    weekly_pnl = current_equity - week_start_equity
                    weekly_return_pct = (weekly_pnl / week_start_equity) * 100
                    
                    performance_review.update({
                        'weekly_pnl': weekly_pnl,
                        'weekly_return_pct': weekly_return_pct,
                        'current_equity': current_equity,
                        'week_start_equity': week_start_equity
                    })
            
            # Load trade ledger for detailed analysis
            ledger_file = PROJECT_ROOT / "data/options/trade_ledger.parquet"
            if ledger_file.exists():
                df = pd.read_parquet(ledger_file)
                
                # Filter to review period
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce', utc=True)
                week_start_utc = pd.Timestamp(self.week_start, tz='UTC')
                review_date_utc = pd.Timestamp(self.review_date, tz='UTC')
                week_trades = df[
                    (df['timestamp'] >= week_start_utc) &
                    (df['timestamp'] <= review_date_utc)
                ]
                
                if not week_trades.empty:
                    # Calculate metrics
                    closed_trades = week_trades[
                        week_trades.get('action', pd.Series(dtype=str)).astype(str).str.lower() == 'close'
                    ]
                    
                    if not closed_trades.empty:
                        pnl_col = 'net_pnl' if 'net_pnl' in closed_trades.columns else 'realized_pnl'
                        if pnl_col in closed_trades.columns:
                            pnl_series = pd.to_numeric(closed_trades[pnl_col], errors='coerce').fillna(0.0)
                        else:
                            pnl_series = pd.Series(0.0, index=closed_trades.index)
                        total_pnl = float(pnl_series.sum())
                        winning_trades = closed_trades[pnl_series > 0]
                        
                        performance_review.update({
                            'total_trades': len(closed_trades),
                            'win_rate': len(winning_trades) / len(closed_trades) * 100 if len(closed_trades) > 0 else 0,
                            'avg_trade_pnl': total_pnl / len(closed_trades) if len(closed_trades) > 0 else 0
                        })
                        
                        # Strategy breakdown
                        if 'strategy_type' in closed_trades.columns:
                            close_for_group = closed_trades.copy()
                            close_for_group['_pnl'] = pnl_series.values
                            strategy_pnl = close_for_group.groupby('strategy_type')['_pnl'].agg(['sum', 'count', 'mean'])
                            performance_review['strategy_breakdown'] = strategy_pnl.to_dict('index')
            
        except Exception as e:
            logger.error(f"Performance review failed: {e}")
            performance_review['error'] = str(e)
        
        return performance_review
    
    def review_research_outputs(self) -> Dict[str, Any]:
        """Review research outputs from the week"""
        logger.info("2. Reviewing research outputs...")
        
        research_review = {
            'total_outputs': 0,
            'actionable_outputs': 0,
            'non_actionable_outputs': 0,
            'freeze_restricted_outputs': 0,
            'modules_active': [],
            'output_summary': {},
            'freeze_status': False
        }
        
        try:
            research_dir = PROJECT_ROOT / "data/research"
            
            if research_dir.exists():
                # Find research cycle files from the week
                research_files = []
                for file in research_dir.glob("research_cycle_*.json"):
                    file_time = datetime.fromtimestamp(file.stat().st_mtime)
                    if self.week_start <= file_time <= self.review_date:
                        research_files.append(file)
                
                # Analyze research outputs
                all_outputs = []
                modules_used = set()
                
                for file in research_files:
                    try:
                        with open(file, 'r') as f:
                            cycle_data = json.load(f)
                        
                        research_review['freeze_status'] = cycle_data.get('freeze_active', False)
                        modules_used.update(cycle_data.get('modules_run', []))
                        
                        outputs = cycle_data.get('outputs_generated', [])
                        all_outputs.extend(outputs)
                        
                        # Count actionable vs non-actionable
                        actionable = cycle_data.get('actionable_outputs', [])
                        non_actionable = cycle_data.get('non_actionable_outputs', [])
                        
                        research_review['actionable_outputs'] += len(actionable)
                        research_review['non_actionable_outputs'] += len(non_actionable)
                        
                        # Count freeze-restricted outputs
                        freeze_restricted = sum(1 for output in outputs if output.get('freeze_restriction', False))
                        research_review['freeze_restricted_outputs'] += freeze_restricted
                        
                    except Exception as e:
                        logger.warning(f"Failed to process research file {file}: {e}")
                
                research_review['total_outputs'] = len(all_outputs)
                research_review['modules_active'] = list(modules_used)
                
                # Summarize output types
                output_types = {}
                for output in all_outputs:
                    output_type = output.get('type', 'unknown')
                    output_types[output_type] = output_types.get(output_type, 0) + 1
                
                research_review['output_summary'] = output_types
            
        except Exception as e:
            logger.error(f"Research outputs review failed: {e}")
            research_review['error'] = str(e)
        
        return research_review
    
    def review_model_performance(self) -> Dict[str, Any]:
        """Review model performance and registry status"""
        logger.info("3. Reviewing model performance...")
        
        model_review = {
            'models_in_registry': 0,
            'candidate_models': 0,
            'production_models': 0,
            'archived_models': 0,
            'promotion_candidates': [],
            'performance_summary': {}
        }
        
        try:
            registry_dir = PROJECT_ROOT / "data/model_registry"
            
            if registry_dir.exists():
                registry_file = registry_dir / "registry.json"
                if registry_file.exists():
                    with open(registry_file, "r", encoding="utf-8") as f:
                        registry_payload = json.load(f)
                    models = registry_payload.get("models", []) if isinstance(registry_payload, dict) else []
                    model_review["models_in_registry"] = len(models)
                    for m in models:
                        status = str(m.get("status", "")).strip().lower()
                        if status == "candidate":
                            model_review["candidate_models"] += 1
                        elif status == "production":
                            model_review["production_models"] += 1
                        elif status == "archived":
                            model_review["archived_models"] += 1

                    for m in models:
                        if str(m.get("status", "")).strip().lower() != "candidate":
                            continue
                        rel_path = str(m.get("path", "") or "")
                        model_file = registry_dir / rel_path if rel_path else None
                        if not model_file or not model_file.exists():
                            continue
                        try:
                            with open(model_file, "r", encoding="utf-8") as f:
                                model_data = json.load(f)
                            if self._check_promotion_criteria(model_data):
                                model_review["promotion_candidates"].append({
                                    "model_name": m.get("model_id", model_file.stem),
                                    "performance": model_data.get("validation_metrics", {}),
                                    "ready_for_promotion": True,
                                })
                        except Exception as e:
                            logger.warning(f"Failed to process model file {model_file}: {e}")
            
        except Exception as e:
            logger.error(f"Model performance review failed: {e}")
            model_review['error'] = str(e)
        
        return model_review
    
    def review_system_health(self) -> Dict[str, Any]:
        """Review system health metrics"""
        logger.info("4. Reviewing system health...")
        
        health_review = {
            'uptime_pct': 0.0,
            'avg_cpu_usage': 0.0,
            'avg_memory_usage': 0.0,
            'error_rate': 0.0,
            'restart_count': 0,
            'mode_transitions': 0,
            'stability_score': 0.0
        }
        
        try:
            status_file = PROJECT_ROOT / "data/options/live/northstar_daemon_status.json"
            if status_file.exists():
                with open(status_file, "r", encoding="utf-8") as f:
                    status = json.load(f)
                resource_usage = status.get("resource_usage", {}) if isinstance(status.get("resource_usage"), dict) else {}
                health_review["avg_cpu_usage"] = float(resource_usage.get("cpu_percent", 0.0) or 0.0)
                health_review["avg_memory_usage"] = float(resource_usage.get("memory_percent", 0.0) or 0.0)
                health_review["uptime_pct"] = 100.0 if status.get("processes", {}).get("live_engine", {}).get("running", False) else 0.0
            
            # Calculate stability score
            factors = [
                min(100, health_review['avg_cpu_usage']) / 100,  # Lower CPU is better
                min(100, health_review['avg_memory_usage']) / 100,  # Lower memory is better
                health_review['error_rate'],  # Lower error rate is better
                min(10, health_review['restart_count']) / 10  # Fewer restarts is better
            ]
            
            health_review['stability_score'] = max(0, 100 - sum(factors) * 25)
            
        except Exception as e:
            logger.error(f"System health review failed: {e}")
            health_review['error'] = str(e)
        
        return health_review
    
    def review_governance_events(self) -> Dict[str, Any]:
        """Review governance events from the week"""
        logger.info("5. Reviewing governance events...")
        
        governance_review = {
            'total_events': 0,
            'events_by_severity': {},
            'events_by_type': {},
            'unresolved_events': 0,
            'critical_events': [],
            'mode_transitions': []
        }
        
        try:
            events_file = PROJECT_ROOT / "data/options/live/governance_events.parquet"
            
            if events_file.exists():
                df = pd.read_parquet(events_file)
                
                # Filter to review period
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce', utc=True)
                week_start_utc = pd.Timestamp(self.week_start, tz='UTC')
                review_date_utc = pd.Timestamp(self.review_date, tz='UTC')
                week_events = df[
                    (df['timestamp'] >= week_start_utc) &
                    (df['timestamp'] <= review_date_utc)
                ]
                
                if not week_events.empty:
                    governance_review['total_events'] = len(week_events)
                    
                    # Events by severity
                    severity_counts = week_events['severity'].value_counts().to_dict()
                    governance_review['events_by_severity'] = severity_counts
                    
                    # Events by type
                    type_counts = week_events['event_type'].value_counts().to_dict()
                    governance_review['events_by_type'] = type_counts
                    
                    # Unresolved events
                    unresolved = week_events[week_events['resolved_at'].isna()]
                    governance_review['unresolved_events'] = len(unresolved)
                    
                    # Critical events
                    critical = week_events[week_events['severity'] == 'critical']
                    governance_review['critical_events'] = critical[['timestamp', 'event_type', 'details']].to_dict('records')
                    
                    # Mode transitions
                    mode_transitions = week_events[week_events['event_type'] == 'mode_transition']
                    governance_review['mode_transitions'] = mode_transitions[['timestamp', 'mode_before', 'mode_after']].to_dict('records')
            
        except Exception as e:
            logger.error(f"Governance events review failed: {e}")
            governance_review['error'] = str(e)
        
        return governance_review
    
    def review_capital_scaling(self) -> Dict[str, Any]:
        """Review capital scaling and tier management"""
        logger.info("6. Reviewing capital scaling...")
        
        scaling_review = {
            'current_tier': self.capital_policy.current_tier.value,
            'current_capital': self.capital_policy.get_current_capital(),
            'tier_changes_this_week': 0,
            'scaling_recommendation': 'maintain',
            'next_review_date': None,
            'descaling_triggers': {},
            'scaling_requirements': {}
        }
        
        try:
            # Load current runtime state
            runtime_file = PROJECT_ROOT / "data/options/live/options_runtime_state.json"
            if runtime_file.exists():
                with open(runtime_file, 'r') as f:
                    runtime_state = json.load(f)

                # Sync policy manager with current runtime tier when available.
                runtime_tier = int(runtime_state.get("capital_tier", self.capital_policy.current_tier.value) or self.capital_policy.current_tier.value)
                if 1 <= runtime_tier <= 5:
                    self.capital_policy.current_tier = self.capital_policy.current_tier.__class__(runtime_tier)
                
                # Evaluate scaling recommendation
                scaling_recommendation = self.capital_policy.get_scaling_recommendation(runtime_state)
                scaling_review.update({
                    'scaling_recommendation': scaling_recommendation['recommendation'],
                    'next_review_date': scaling_recommendation.get('next_review_date'),
                    'recommendation_reasons': scaling_recommendation.get('reasons', [])
                })
                
                # Check descaling triggers
                descaling_eval = self.capital_policy.evaluate_descaling_triggers(runtime_state)
                scaling_review['descaling_triggers'] = {
                    'should_descale': descaling_eval['should_descale'],
                    'triggers_met': descaling_eval['triggers_met'],
                    'cooldown_active': descaling_eval['cooldown_active']
                }
                
                # Check scaling requirements
                scaling_eval = self.capital_policy.evaluate_scaling_requirements(runtime_state)
                scaling_review['scaling_requirements'] = {
                    'can_scale_up': scaling_eval['can_scale_up'],
                    'requirements_met': len(scaling_eval['requirements_met']),
                    'requirements_failed': len(scaling_eval['requirements_failed'])
                }
            
        except Exception as e:
            logger.error(f"Capital scaling review failed: {e}")
            scaling_review['error'] = str(e)
        
        return scaling_review
    
    def generate_recommendations(self, review_report: Dict[str, Any]) -> Dict[str, Any]:
        """Generate recommendations based on review"""
        logger.info("7. Generating recommendations...")
        
        recommendations = {
            'priority_actions': [],
            'performance_improvements': [],
            'system_optimizations': [],
            'research_priorities': [],
            'risk_management': []
        }
        
        try:
            # Performance-based recommendations
            performance = review_report['sections']['performance']
            if performance.get('weekly_return_pct', 0) < -5:
                recommendations['priority_actions'].append({
                    'action': 'Review poor performance',
                    'reason': f"Weekly return {performance['weekly_return_pct']:.1f}% below acceptable threshold",
                    'urgency': 'high'
                })
            
            # System health recommendations
            health = review_report['sections']['system_health']
            if health.get('stability_score', 100) < 80:
                recommendations['system_optimizations'].append({
                    'action': 'Investigate system stability issues',
                    'reason': f"Stability score {health['stability_score']:.1f}% below target",
                    'urgency': 'medium'
                })
            
            # Governance events recommendations
            governance = review_report['sections']['governance_events']
            if governance.get('unresolved_events', 0) > 0:
                recommendations['priority_actions'].append({
                    'action': 'Resolve outstanding governance events',
                    'reason': f"{governance['unresolved_events']} unresolved events",
                    'urgency': 'high'
                })
            
            # Research recommendations
            research = review_report['sections']['research_outputs']
            if research.get('total_outputs', 0) == 0:
                recommendations['research_priorities'].append({
                    'action': 'Investigate research inactivity',
                    'reason': 'No research outputs generated this week',
                    'urgency': 'medium'
                })
            
            # Capital scaling recommendations
            scaling = review_report['sections']['capital_scaling']
            if scaling.get('scaling_recommendation') == 'down':
                recommendations['risk_management'].append({
                    'action': 'Consider capital tier reduction',
                    'reason': 'Descaling triggers met',
                    'urgency': 'high'
                })
            
        except Exception as e:
            logger.error(f"Recommendations generation failed: {e}")
            recommendations['error'] = str(e)
        
        return recommendations
    
    def _check_promotion_criteria(self, model_data: Dict[str, Any]) -> bool:
        """Check if model meets promotion criteria"""
        performance = model_data.get('validation_metrics', {})
        
        # Simple criteria check (would be more sophisticated in practice)
        sharpe_ratio = performance.get('sharpe_ratio', performance.get('sharpe', 0))
        max_drawdown = performance.get('max_drawdown', 1)
        
        return sharpe_ratio >= 1.2 and max_drawdown <= 0.08
    
    def save_review_report(self, review_report: Dict[str, Any]):
        """Save review report to file"""
        timestamp = self.review_date.strftime('%Y%m%d_%H%M%S')
        report_file = self.output_dir / f"weekly_review_{timestamp}.json"
        
        with open(report_file, 'w') as f:
            json.dump(review_report, f, indent=2, default=str)
        
        logger.info(f"Review report saved: {report_file}")
    
    def print_review_summary(self, review_report: Dict[str, Any]):
        """Print review summary"""
        logger.info("=" * 60)
        logger.info("WEEKLY REVIEW SUMMARY")
        logger.info("=" * 60)
        
        # Performance summary
        performance = review_report['sections']['performance']
        logger.info(f"📊 PERFORMANCE:")
        logger.info(f"   Weekly P&L: ₹{performance.get('weekly_pnl', 0):,.2f}")
        logger.info(f"   Weekly Return: {performance.get('weekly_return_pct', 0):.2f}%")
        logger.info(f"   Total Trades: {performance.get('total_trades', 0)}")
        logger.info(f"   Win Rate: {performance.get('win_rate', 0):.1f}%")
        
        # System health summary
        health = review_report['sections']['system_health']
        logger.info(f"🏥 SYSTEM HEALTH:")
        logger.info(f"   Stability Score: {health.get('stability_score', 0):.1f}%")
        logger.info(f"   Avg CPU Usage: {health.get('avg_cpu_usage', 0):.1f}%")
        logger.info(f"   Avg Memory Usage: {health.get('avg_memory_usage', 0):.1f}%")
        
        # Governance summary
        governance = review_report['sections']['governance_events']
        logger.info(f"⚖️  GOVERNANCE:")
        logger.info(f"   Total Events: {governance.get('total_events', 0)}")
        logger.info(f"   Unresolved: {governance.get('unresolved_events', 0)}")
        logger.info(f"   Critical Events: {len(governance.get('critical_events', []))}")
        
        # Recommendations summary
        recommendations = review_report['sections']['recommendations']
        priority_actions = recommendations.get('priority_actions', [])
        if priority_actions:
            logger.info(f"🚨 PRIORITY ACTIONS:")
            for action in priority_actions[:3]:  # Top 3
                logger.info(f"   - {action['action']}")
        
        logger.info("=" * 60)


def main():
    """Main entry point"""
    reviewer = WeeklyResearchReviewer()
    review_report = reviewer.run_weekly_review()
    
    # Return success/failure based on critical issues
    critical_issues = (
        len(review_report['sections']['governance_events'].get('critical_events', [])) +
        len([r for r in review_report['sections']['recommendations'].get('priority_actions', []) 
             if r.get('urgency') == 'high'])
    )
    
    return 1 if critical_issues > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
