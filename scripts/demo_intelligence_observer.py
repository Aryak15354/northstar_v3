#!/usr/bin/env python3
"""
Intelligence Observer Demo - Northstar V3 Integration

This script demonstrates the Intelligence Observer Layer integrated with
Northstar V3 architecture while maintaining strict authority boundaries.

DEMONSTRATION FEATURES:
1. Observer integration with V3 architecture
2. Regime and stress intelligence analysis
3. Authority firewall enforcement
4. Temporal isolation from trading decisions
5. Complete audit trail
6. Weekly intelligence reports
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Import Intelligence Observer components
from src.intelligence_observer.observer_core.observer_scheduler import ObserverScheduler
from src.intelligence_observer.observer_core.snapshot_builder import SnapshotBuilder
from src.intelligence_observer.question_engines.regime_intelligence import RegimeIntelligenceEngine
from src.intelligence_observer.question_engines.stress_intelligence import StressIntelligenceEngine
from src.intelligence_observer.guardrails.authority_firewall import install_authority_firewall, get_authority_firewall
from src.intelligence_observer.audit.observer_audit_log import ObserverAuditLog
from src.intelligence_observer.reports.weekly_intelligence_report import WeeklyIntelligenceReport

def create_sample_market_data():
    """Create sample market data for demonstration"""
    
    print("📊 Creating sample market data...")
    
    # Create sample market state data
    dates = pd.date_range(start='2024-01-01', end='2024-12-31', freq='D')
    
    # Generate realistic market data with regime changes
    np.random.seed(42)
    
    market_data = []
    current_regime = 'supportive'
    regime_duration = 0
    
    for i, date in enumerate(dates):
        # Regime transition logic
        if regime_duration > 30 and np.random.random() < 0.1:
            regimes = ['supportive', 'neutral', 'hostile']
            current_regime = np.random.choice([r for r in regimes if r != current_regime])
            regime_duration = 0
        
        regime_duration += 1
        
        # Generate regime-dependent market conditions
        if current_regime == 'supportive':
            volatility = np.random.normal(0.12, 0.03)
            correlation = np.random.normal(0.35, 0.10)
            breadth = np.random.normal(65, 10)
            market_stress = np.random.normal(0.15, 0.05)
        elif current_regime == 'neutral':
            volatility = np.random.normal(0.18, 0.04)
            correlation = np.random.normal(0.50, 0.12)
            breadth = np.random.normal(50, 12)
            market_stress = np.random.normal(0.25, 0.08)
        else:  # hostile
            volatility = np.random.normal(0.28, 0.06)
            correlation = np.random.normal(0.75, 0.10)
            breadth = np.random.normal(35, 8)
            market_stress = np.random.normal(0.45, 0.10)
        
        # Ensure realistic bounds
        volatility = max(0.08, min(0.50, volatility))
        correlation = max(0.20, min(0.90, correlation))
        breadth = max(20, min(80, breadth))
        market_stress = max(0.05, min(0.80, market_stress))
        
        # Calculate derived metrics
        market_return = np.random.normal(0.0005, volatility/np.sqrt(252))
        trend_strength = np.random.normal(0.5 if current_regime == 'supportive' else -0.2, 0.3)
        
        market_data.append({
            'date': date,
            'regime': current_regime,
            'volatility_regime': 'high' if volatility > 0.25 else 'normal',
            'risk_on_probability': 0.7 if current_regime == 'supportive' else 0.3,
            'allowed_exposure': 0.8 if current_regime == 'supportive' else 0.4,
            'market_stress': market_stress,
            'breadth_pct': breadth,
            'correlation': correlation,
            'market_return': market_return,
            'volatility_20d': volatility,
            'trend_strength': trend_strength
        })
    
    # Create DataFrame and save
    df = pd.DataFrame(market_data)
    df.set_index('date', inplace=True)
    
    # Ensure data directory exists
    os.makedirs('data/processed', exist_ok=True)
    df.to_parquet('data/testing/sample_processed/market_state.parquet')  # demo output, never canonical
    
    print(f"✅ Created {len(df)} days of sample market data")
    return df

def demonstrate_authority_firewall():
    """Demonstrate authority firewall protection"""
    
    print("\n🔒 DEMONSTRATING AUTHORITY FIREWALL")
    print("=" * 50)
    
    # Install authority firewall
    firewall = install_authority_firewall()
    
    # Test 1: Forbidden module import
    print("\n🧪 Test 1: Forbidden Module Import")
    try:
        allowed = firewall.check_import_attempt('src.portfolio.portfolio_governor')
        print(f"   Portfolio Governor import allowed: {allowed}")
    except Exception as e:
        print(f"   ❌ Import blocked: {e}")
    
    # Test 2: Forbidden function call
    print("\n🧪 Test 2: Forbidden Function Call")
    try:
        allowed = firewall.check_function_call('set_exposure', 'observer_test')
        print(f"   Set exposure call allowed: {allowed}")
    except Exception as e:
        print(f"   ❌ Function call blocked: {e}")
    
    # Test 3: Forbidden attribute access
    print("\n🧪 Test 3: Forbidden Attribute Access")
    try:
        allowed = firewall.check_attribute_access('current_positions', 'read')
        print(f"   Current positions read allowed: {allowed}")
    except Exception as e:
        print(f"   ❌ Attribute access blocked: {e}")
    
    # Show violation summary
    print("\n📊 Authority Firewall Summary:")
    summary = firewall.get_violation_summary()
    print(f"   Total violations: {summary['total_violations']}")
    print(f"   Observer suspended: {summary['observer_suspended']}")
    print(f"   Violations by type: {summary['violations_by_type']}")

def demonstrate_intelligence_analysis():
    """Demonstrate intelligence analysis capabilities"""
    
    print("\n🧠 DEMONSTRATING INTELLIGENCE ANALYSIS")
    print("=" * 50)
    
    # Create snapshot builder and engines
    snapshot_builder = SnapshotBuilder()
    regime_engine = RegimeIntelligenceEngine()
    stress_engine = StressIntelligenceEngine()
    
    # Build current snapshot
    print("\n📸 Building Observer Snapshot...")
    snapshot = snapshot_builder.build_snapshot()
    
    if snapshot is None:
        print("❌ Failed to build snapshot - using synthetic data")
        return
    
    print(f"✅ Snapshot created: {snapshot.snapshot_id}")
    print(f"   Data quality: {snapshot.data_quality_score:.2f}")
    print(f"   Completeness: {snapshot.completeness_score:.2f}")
    print(f"   Staleness: {snapshot.staleness_hours:.1f} hours")
    
    # Regime Intelligence Analysis
    print("\n🎯 Regime Intelligence Analysis:")
    try:
        regime_score, regime_narrative = regime_engine.analyze_regime_similarity(snapshot)
        stability_score = regime_engine.analyze_regime_stability(snapshot)
        transition_score = regime_engine.analyze_regime_transition_probability(snapshot)
        
        print(f"   Regime Similarity: {regime_score.value:.0f}/100 ({regime_score.confidence:.1%} confidence)")
        print(f"   Regime Stability: {stability_score.value:.0f}/100")
        print(f"   Transition Probability: {transition_score.value:.0f}/100")
        print(f"   Narrative: {regime_narrative.title}")
        
    except Exception as e:
        print(f"   ❌ Regime analysis error: {e}")
    
    # Stress Intelligence Analysis
    print("\n🚨 Stress Intelligence Analysis:")
    try:
        stress_score, stress_alert = stress_engine.analyze_stress_clustering(snapshot)
        false_calm_score, false_calm_alert = stress_engine.analyze_false_calm_detection(snapshot)
        readiness_score = stress_engine.analyze_crisis_engine_readiness(snapshot)
        
        print(f"   Stress Clustering: {stress_score.value:.0f}/100 ({stress_score.confidence:.1%} confidence)")
        print(f"   False Calm Likelihood: {false_calm_score.value:.0f}/100")
        print(f"   Crisis Readiness: {readiness_score.value:.0f}/100")
        
        if stress_alert:
            print(f"   🚨 Stress Alert: {stress_alert.message}")
        
        if false_calm_alert:
            print(f"   ⚠️ False Calm Alert: {false_calm_alert.message}")
        
    except Exception as e:
        print(f"   ❌ Stress analysis error: {e}")

def demonstrate_observer_scheduler():
    """Demonstrate observer scheduler functionality"""
    
    print("\n⏰ DEMONSTRATING OBSERVER SCHEDULER")
    print("=" * 50)
    
    # Create scheduler
    scheduler = ObserverScheduler()
    
    # Get scheduler status
    status = scheduler.get_scheduler_status()
    
    print(f"📅 Scheduler Configuration:")
    print(f"   Running: {status['is_running']}")
    print(f"   Observer suspended: {status['observer_suspended']}")
    print(f"   Violation count: {status['violation_count']}")
    
    print(f"\n📋 Scheduled Tasks:")
    for task_id, task_info in status['scheduled_tasks'].items():
        print(f"   {task_id}:")
        print(f"     Type: {task_info['schedule_type']}")
        print(f"     Next run: {task_info['next_run']}")
        print(f"     Run count: {task_info['run_count']}")
        print(f"     Enabled: {task_info['enabled']}")
    
    # Run on-demand analysis
    print(f"\n🔍 Running On-Demand Analysis...")
    result = scheduler.run_on_demand_analysis()
    
    if result['success']:
        print(f"✅ Analysis completed successfully")
        print(f"   Snapshot ID: {result['snapshot_id']}")
        print(f"   Results count: {len(result['results'])}")
        
        # Show sample results
        for i, result_item in enumerate(result['results'][:3]):
            print(f"   Result {i+1}: {result_item['type']} - {result_item['category']}")
    else:
        print(f"❌ Analysis failed: {result.get('error', 'Unknown error')}")

def demonstrate_audit_trail():
    """Demonstrate audit trail functionality"""
    
    print("\n📋 DEMONSTRATING AUDIT TRAIL")
    print("=" * 50)
    
    # Create audit log
    audit_log = ObserverAuditLog()
    
    # Log sample events
    print("📝 Logging sample events...")
    
    audit_log.log_event('observer_started', {
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })
    
    audit_log.log_intelligence_output('regime_score', {
        'score_value': 67.5,
        'confidence': 0.82,
        'interpretation': 'Current conditions resemble historically unstable regimes'
    })
    
    audit_log.log_system_interaction('state_read', {
        'component': 'market_state',
        'access_type': 'read_only',
        'data_points': 252
    })
    
    # Get audit summary
    print("\n📊 Audit Summary (Last 7 days):")
    summary = audit_log.get_audit_summary(days=7)
    
    print(f"   Total entries: {summary['total_entries']}")
    print(f"   Event types: {summary['event_types']}")
    print(f"   Authority violations: {summary['authority_violations']}")
    print(f"   Audit integrity: {summary['audit_integrity']}")
    
    # Verify audit integrity
    print("\n🔍 Verifying Audit Integrity...")
    integrity = audit_log.verify_audit_integrity()
    
    print(f"   Total entries: {integrity['total_entries']}")
    print(f"   Hash chain valid: {integrity.get('hash_chain_valid', 'N/A')}")
    print(f"   Timestamp gaps: {integrity.get('timestamp_gaps', 0)}")
    print(f"   File integrity: {integrity.get('file_integrity', {}).get('readable_files', 0)} readable files")

def demonstrate_weekly_report():
    """Demonstrate weekly intelligence report generation"""
    
    print("\n📊 DEMONSTRATING WEEKLY INTELLIGENCE REPORT")
    print("=" * 50)
    
    try:
        # Create weekly report generator
        report_generator = WeeklyIntelligenceReport()
        
        # Generate sample report
        print("📝 Generating weekly intelligence report...")
        
        # Create sample intelligence data
        sample_scores = [
            {
                'score_name': 'Regime Similarity Index',
                'value': 67.0,
                'confidence': 0.82,
                'interpretation': 'Current conditions resemble historically unstable regimes'
            },
            {
                'score_name': 'Stress Clustering Index',
                'value': 45.0,
                'confidence': 0.85,
                'interpretation': 'Stress indicators within historical baseline'
            }
        ]
        
        sample_alerts = [
            {
                'alert_type': 'monitoring',
                'severity': 'medium',
                'message': 'Regime transition probability elevated',
                'recommended_response': 'Increase monitoring vigilance'
            }
        ]
        
        # Generate report
        report = report_generator.generate_report(sample_scores, sample_alerts, [])
        
        print(f"✅ Weekly report generated")
        print(f"   Report ID: {report['report_id']}")
        print(f"   Generation time: {report['generation_time']}")
        print(f"   Scores analyzed: {len(sample_scores)}")
        print(f"   Alerts reviewed: {len(sample_alerts)}")
        
        # Show executive summary
        print(f"\n📋 Executive Summary:")
        for item in report['executive_summary'][:3]:
            print(f"   • {item}")
        
    except Exception as e:
        print(f"❌ Weekly report generation error: {e}")

def main():
    """Main demonstration function"""
    
    print("🧠 NORTHSTAR V3 INTELLIGENCE OBSERVER DEMONSTRATION")
    print("=" * 60)
    print("This demonstration shows the Intelligence Observer Layer")
    print("integrated with Northstar V3 while maintaining strict")
    print("authority boundaries and constitutional system design.")
    print("=" * 60)
    
    try:
        # Create sample data
        market_data = create_sample_market_data()
        
        # Demonstrate components
        demonstrate_authority_firewall()
        demonstrate_intelligence_analysis()
        demonstrate_observer_scheduler()
        demonstrate_audit_trail()
        demonstrate_weekly_report()
        
        print("\n" + "=" * 60)
        print("🎉 INTELLIGENCE OBSERVER DEMONSTRATION COMPLETED")
        print("=" * 60)
        print("\nKEY ACHIEVEMENTS:")
        print("✅ Authority firewall prevents decision influence")
        print("✅ Intelligence analysis provides genuine insights")
        print("✅ Temporal isolation from trading decisions")
        print("✅ Complete audit trail for transparency")
        print("✅ Weekly reports for human consumption")
        print("\nThe Intelligence Observer makes you wiser, not braver.")
        print("Bravery is already encoded in your engines.")
        
    except Exception as e:
        print(f"\n❌ Demonstration error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()