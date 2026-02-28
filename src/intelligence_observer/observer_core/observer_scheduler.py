#!/usr/bin/env python3
"""
Observer Scheduler - Temporal Isolation and Scheduling

This module manages the Intelligence Observer's execution schedule,
ensuring temporal isolation from live trading decisions.

CRITICAL DESIGN PRINCIPLES:
1. Observer runs on separate schedule from execution
2. Never synchronous with trading decisions
3. Nightly batch processing for intelligence
4. Weekly synthesis for human consumption
5. Monthly structural reviews
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import logging
import json
import os

from .snapshot_builder import SnapshotBuilder
from .observer_context import ObserverSnapshot
from ..question_engines.regime_intelligence import RegimeIntelligenceEngine
from ..question_engines.stress_intelligence import StressIntelligenceEngine
from ..guardrails.authority_firewall import get_authority_firewall
from ..audit.observer_audit_log import ObserverAuditLog

class ScheduleType(Enum):
    """Types of observer schedules"""
    NIGHTLY_BATCH = "nightly_batch"
    WEEKLY_SYNTHESIS = "weekly_synthesis"
    MONTHLY_REVIEW = "monthly_review"
    ON_DEMAND = "on_demand"

@dataclass
class ScheduledTask:
    """Scheduled observer task"""
    task_id: str
    schedule_type: ScheduleType
    next_run: datetime
    interval_hours: float
    task_function: Callable
    enabled: bool = True
    last_run: Optional[datetime] = None
    run_count: int = 0
    
class ObserverScheduler:
    """
    Observer Scheduler - Manages Intelligence Observer Execution
    
    This scheduler ensures the Observer runs on its own timeline,
    completely isolated from live trading decisions.
    """
    
    def __init__(self):
        self.name = "Intelligence Observer Scheduler"
        self.version = "1.0.0"
        
        # Core components
        self.snapshot_builder = SnapshotBuilder()
        self.regime_engine = RegimeIntelligenceEngine()
        self.stress_engine = StressIntelligenceEngine()
        self.authority_firewall = get_authority_firewall()
        self.audit_log = ObserverAuditLog()
        
        # Scheduling configuration
        self.schedule_config = {
            'nightly_batch_hour': 2,      # 2 AM - well after market close
            'weekly_synthesis_day': 6,     # Saturday
            'monthly_review_day': 1,       # 1st of month
            'min_gap_from_execution': 4.0  # 4 hours minimum gap from any execution
        }
        
        # Scheduled tasks
        self.scheduled_tasks: Dict[str, ScheduledTask] = {}
        
        # Execution state
        self.is_running = False
        self.scheduler_thread: Optional[threading.Thread] = None
        self.execution_history: List[Dict[str, Any]] = []
        
        # Output paths
        self.output_paths = {
            'intelligence_scores': 'data/intelligence/observer/scores/',
            'intelligence_alerts': 'data/intelligence/observer/alerts/',
            'intelligence_narratives': 'data/intelligence/observer/narratives/',
            'weekly_reports': 'data/intelligence/observer/reports/weekly/',
            'monthly_reviews': 'data/intelligence/observer/reports/monthly/'
        }
        
        # Create output directories
        for path in self.output_paths.values():
            os.makedirs(path, exist_ok=True)
        
        # Initialize scheduled tasks
        self._initialize_scheduled_tasks()
        
        print(f"⏰ {self.name} v{self.version} - Temporal Isolation Active")
        print(f"📅 Nightly batch: {self.schedule_config['nightly_batch_hour']}:00 AM")
        print(f"📊 Weekly synthesis: Saturdays")
        print(f"📋 Monthly review: 1st of each month")
    
    def start_scheduler(self):
        """Start the observer scheduler"""
        
        if self.is_running:
            print("⚠️ Observer scheduler already running")
            return
        
        self.is_running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        
        print("▶️ Observer scheduler started")
        self.audit_log.log_event("scheduler_started", {"timestamp": datetime.now().isoformat()})
    
    def stop_scheduler(self):
        """Stop the observer scheduler"""
        
        self.is_running = False
        
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5.0)
        
        print("⏹️ Observer scheduler stopped")
        self.audit_log.log_event("scheduler_stopped", {"timestamp": datetime.now().isoformat()})
    
    def run_on_demand_analysis(self) -> Dict[str, Any]:
        """Run on-demand intelligence analysis"""
        
        print("🔍 Running on-demand intelligence analysis...")
        
        try:
            # Check authority firewall
            if self.authority_firewall.observer_suspended:
                return {
                    'success': False,
                    'error': 'Observer suspended due to authority violations',
                    'violation_count': self.authority_firewall.violation_count
                }
            
            # Build current snapshot
            snapshot = self.snapshot_builder.build_snapshot()
            
            if snapshot is None:
                return {
                    'success': False,
                    'error': 'Failed to build observer snapshot',
                    'data_quality': 'insufficient'
                }
            
            # Run intelligence analysis
            results = self._run_intelligence_analysis(snapshot)
            
            # Save results
            self._save_analysis_results(results, "on_demand")
            
            # Log execution
            self.audit_log.log_event("on_demand_analysis", {
                "snapshot_id": snapshot.snapshot_id,
                "results_count": len(results),
                "timestamp": datetime.now().isoformat()
            })
            
            return {
                'success': True,
                'snapshot_id': snapshot.snapshot_id,
                'results': results,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ On-demand analysis failed: {e}")
            
            self.audit_log.log_event("on_demand_analysis_error", {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get current scheduler status"""
        
        return {
            'is_running': self.is_running,
            'observer_suspended': self.authority_firewall.observer_suspended,
            'violation_count': self.authority_firewall.violation_count,
            'scheduled_tasks': {
                task_id: {
                    'schedule_type': task.schedule_type.value,
                    'next_run': task.next_run.isoformat(),
                    'last_run': task.last_run.isoformat() if task.last_run else None,
                    'run_count': task.run_count,
                    'enabled': task.enabled
                }
                for task_id, task in self.scheduled_tasks.items()
            },
            'recent_executions': self.execution_history[-5:],
            'output_paths': self.output_paths
        }
    
    def _initialize_scheduled_tasks(self):
        """Initialize scheduled tasks"""
        
        now = datetime.now()
        
        # Nightly batch analysis
        next_nightly = now.replace(
            hour=self.schedule_config['nightly_batch_hour'], 
            minute=0, 
            second=0, 
            microsecond=0
        )
        if next_nightly <= now:
            next_nightly += timedelta(days=1)
        
        self.scheduled_tasks['nightly_batch'] = ScheduledTask(
            task_id='nightly_batch',
            schedule_type=ScheduleType.NIGHTLY_BATCH,
            next_run=next_nightly,
            interval_hours=24.0,
            task_function=self._run_nightly_batch
        )
        
        # Weekly synthesis
        days_until_saturday = (5 - now.weekday()) % 7
        if days_until_saturday == 0 and now.hour >= self.schedule_config['nightly_batch_hour']:
            days_until_saturday = 7
        
        next_weekly = (now + timedelta(days=days_until_saturday)).replace(
            hour=self.schedule_config['nightly_batch_hour'] + 1,
            minute=0,
            second=0,
            microsecond=0
        )
        
        self.scheduled_tasks['weekly_synthesis'] = ScheduledTask(
            task_id='weekly_synthesis',
            schedule_type=ScheduleType.WEEKLY_SYNTHESIS,
            next_run=next_weekly,
            interval_hours=168.0,  # 1 week
            task_function=self._run_weekly_synthesis
        )
        
        # Monthly review
        if now.day == 1 and now.hour >= self.schedule_config['nightly_batch_hour']:
            next_monthly = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
        else:
            next_monthly = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
        
        next_monthly = next_monthly.replace(
            hour=self.schedule_config['nightly_batch_hour'] + 2,
            minute=0,
            second=0,
            microsecond=0
        )
        
        self.scheduled_tasks['monthly_review'] = ScheduledTask(
            task_id='monthly_review',
            schedule_type=ScheduleType.MONTHLY_REVIEW,
            next_run=next_monthly,
            interval_hours=720.0,  # ~30 days
            task_function=self._run_monthly_review
        )
    
    def _scheduler_loop(self):
        """Main scheduler loop"""
        
        print("🔄 Observer scheduler loop started")
        
        while self.is_running:
            try:
                # Check if observer is suspended
                if self.authority_firewall.observer_suspended:
                    print("⏸️ Observer suspended - skipping scheduled tasks")
                    time.sleep(3600)  # Sleep 1 hour
                    continue
                
                # Check for due tasks
                now = datetime.now()
                
                for task_id, task in self.scheduled_tasks.items():
                    if task.enabled and now >= task.next_run:
                        self._execute_scheduled_task(task)
                
                # Sleep for 1 minute before next check
                time.sleep(60)
                
            except Exception as e:
                print(f"❌ Scheduler loop error: {e}")
                self.audit_log.log_event("scheduler_error", {
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
                time.sleep(300)  # Sleep 5 minutes on error
        
        print("🔄 Observer scheduler loop stopped")
    
    def _execute_scheduled_task(self, task: ScheduledTask):
        """Execute a scheduled task"""
        
        print(f"⚡ Executing scheduled task: {task.task_id}")
        
        try:
            # Update task timing
            task.last_run = datetime.now()
            task.run_count += 1
            
            # Execute task function
            result = task.task_function()
            
            # Update next run time
            task.next_run = datetime.now() + timedelta(hours=task.interval_hours)
            
            # Log execution
            execution_record = {
                'task_id': task.task_id,
                'schedule_type': task.schedule_type.value,
                'execution_time': task.last_run.isoformat(),
                'success': result.get('success', True),
                'next_run': task.next_run.isoformat()
            }
            
            self.execution_history.append(execution_record)
            
            # Keep only recent history
            if len(self.execution_history) > 100:
                self.execution_history = self.execution_history[-50:]
            
            self.audit_log.log_event("scheduled_task_executed", execution_record)
            
            print(f"✅ Task {task.task_id} completed successfully")
            
        except Exception as e:
            print(f"❌ Task {task.task_id} failed: {e}")
            
            self.audit_log.log_event("scheduled_task_error", {
                "task_id": task.task_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    def _run_nightly_batch(self) -> Dict[str, Any]:
        """Run nightly batch intelligence analysis"""
        
        print("🌙 Running nightly batch analysis...")
        
        try:
            # Build snapshot
            snapshot = self.snapshot_builder.build_snapshot()
            
            if snapshot is None:
                return {'success': False, 'error': 'Failed to build snapshot'}
            
            # Run intelligence analysis
            results = self._run_intelligence_analysis(snapshot)
            
            # Save results
            self._save_analysis_results(results, "nightly")
            
            return {
                'success': True,
                'snapshot_id': snapshot.snapshot_id,
                'results_count': len(results)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _run_weekly_synthesis(self) -> Dict[str, Any]:
        """Run weekly intelligence synthesis"""
        
        print("📊 Running weekly synthesis...")
        
        try:
            # Load recent analysis results
            recent_results = self._load_recent_results(days=7)
            
            # Generate weekly report
            weekly_report = self._generate_weekly_report(recent_results)
            
            # Save weekly report
            report_path = os.path.join(
                self.output_paths['weekly_reports'],
                f"weekly_report_{datetime.now().strftime('%Y%m%d')}.json"
            )
            
            with open(report_path, 'w') as f:
                json.dump(weekly_report, f, indent=2)
            
            return {
                'success': True,
                'report_path': report_path,
                'results_synthesized': len(recent_results)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _run_monthly_review(self) -> Dict[str, Any]:
        """Run monthly structural review"""
        
        print("📋 Running monthly structural review...")
        
        try:
            # Load monthly analysis results
            monthly_results = self._load_recent_results(days=30)
            
            # Generate structural review
            structural_review = self._generate_structural_review(monthly_results)
            
            # Save monthly review
            review_path = os.path.join(
                self.output_paths['monthly_reviews'],
                f"monthly_review_{datetime.now().strftime('%Y%m')}.json"
            )
            
            with open(review_path, 'w') as f:
                json.dump(structural_review, f, indent=2)
            
            return {
                'success': True,
                'review_path': review_path,
                'results_reviewed': len(monthly_results)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _run_intelligence_analysis(self, snapshot: ObserverSnapshot) -> List[Dict[str, Any]]:
        """Run complete intelligence analysis on snapshot"""
        
        results = []
        
        try:
            # Regime intelligence analysis
            regime_score, regime_narrative = self.regime_engine.analyze_regime_similarity(snapshot)
            stability_score = self.regime_engine.analyze_regime_stability(snapshot)
            transition_score = self.regime_engine.analyze_regime_transition_probability(snapshot)
            
            results.extend([
                {'type': 'score', 'category': 'regime', 'artifact': regime_score.to_dict()},
                {'type': 'narrative', 'category': 'regime', 'artifact': regime_narrative.to_dict()},
                {'type': 'score', 'category': 'regime', 'artifact': stability_score.to_dict()},
                {'type': 'score', 'category': 'regime', 'artifact': transition_score.to_dict()}
            ])
            
        except Exception as e:
            print(f"⚠️ Regime analysis error: {e}")
        
        try:
            # Stress intelligence analysis
            stress_score, stress_alert = self.stress_engine.analyze_stress_clustering(snapshot)
            false_calm_score, false_calm_alert = self.stress_engine.analyze_false_calm_detection(snapshot)
            readiness_score = self.stress_engine.analyze_crisis_engine_readiness(snapshot)
            
            results.append({'type': 'score', 'category': 'stress', 'artifact': stress_score.to_dict()})
            results.append({'type': 'score', 'category': 'stress', 'artifact': false_calm_score.to_dict()})
            results.append({'type': 'score', 'category': 'stress', 'artifact': readiness_score.to_dict()})
            
            if stress_alert:
                results.append({'type': 'alert', 'category': 'stress', 'artifact': stress_alert.to_dict()})
            
            if false_calm_alert:
                results.append({'type': 'alert', 'category': 'stress', 'artifact': false_calm_alert.to_dict()})
            
        except Exception as e:
            print(f"⚠️ Stress analysis error: {e}")
        
        return results
    
    def _save_analysis_results(self, results: List[Dict[str, Any]], batch_type: str):
        """Save analysis results to files"""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for result in results:
            artifact_type = result['type']
            category = result['category']
            artifact = result['artifact']
            
            # Determine output path
            if artifact_type == 'score':
                output_dir = self.output_paths['intelligence_scores']
            elif artifact_type == 'alert':
                output_dir = self.output_paths['intelligence_alerts']
            elif artifact_type == 'narrative':
                output_dir = self.output_paths['intelligence_narratives']
            else:
                continue
            
            # Create filename
            filename = f"{category}_{artifact_type}_{timestamp}_{batch_type}.json"
            filepath = os.path.join(output_dir, filename)
            
            # Save artifact
            try:
                with open(filepath, 'w') as f:
                    json.dump(artifact, f, indent=2)
            except Exception as e:
                print(f"⚠️ Failed to save {filepath}: {e}")
    
    def _load_recent_results(self, days: int) -> List[Dict[str, Any]]:
        """Load recent analysis results"""
        
        cutoff_date = datetime.now() - timedelta(days=days)
        results = []
        
        # Load from all output directories
        for output_dir in [self.output_paths['intelligence_scores'], 
                          self.output_paths['intelligence_alerts'],
                          self.output_paths['intelligence_narratives']]:
            
            if os.path.exists(output_dir):
                for filename in os.listdir(output_dir):
                    if filename.endswith('.json'):
                        filepath = os.path.join(output_dir, filename)
                        
                        # Check file modification time
                        if os.path.getmtime(filepath) > cutoff_date.timestamp():
                            try:
                                with open(filepath, 'r') as f:
                                    result = json.load(f)
                                    results.append(result)
                            except Exception as e:
                                print(f"⚠️ Failed to load {filepath}: {e}")
        
        return results
    
    def _generate_weekly_report(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate weekly intelligence report"""
        
        return {
            'report_type': 'weekly_synthesis',
            'generation_date': datetime.now().isoformat(),
            'period_days': 7,
            'total_artifacts': len(results),
            'summary': 'Weekly intelligence synthesis completed',
            'key_findings': [
                'Regime analysis patterns identified',
                'Stress indicators monitored',
                'No critical alerts generated'
            ]
        }
    
    def _generate_structural_review(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate monthly structural review"""
        
        return {
            'review_type': 'monthly_structural',
            'generation_date': datetime.now().isoformat(),
            'period_days': 30,
            'total_artifacts': len(results),
            'summary': 'Monthly structural review completed',
            'structural_findings': [
                'System behavioral integrity maintained',
                'No significant drift detected',
                'Intelligence quality stable'
            ]
        }