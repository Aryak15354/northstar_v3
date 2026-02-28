#!/usr/bin/env python3
"""
Simple Intelligence Observer Validation Test

This script validates the core functionality of the Intelligence Observer
system with the actual implementation APIs.
"""

import os
import sys
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

def test_authority_firewall():
    """Test authority firewall functionality"""
    print("🔒 Testing Authority Firewall...")
    
    from src.intelligence_observer.guardrails.authority_firewall import AuthorityFirewall
    
    firewall = AuthorityFirewall()
    
    # Test forbidden operations
    assert not firewall.check_import_attempt('src.portfolio.portfolio_governor')
    assert not firewall.check_function_call('set_exposure', 'test')
    assert not firewall.check_attribute_access('current_positions', 'read')
    
    # Test allowed operations
    assert firewall.check_import_attempt('pandas')
    assert firewall.check_function_call('analyze_data', 'test')
    
    print("   ✅ Authority boundaries enforced")
    return True

def test_output_artifacts():
    """Test output artifacts with correct API"""
    print("📊 Testing Output Artifacts...")
    
    from src.intelligence_observer.output_artifacts.intelligence_score import (
        IntelligenceScore, ScoreType, HistoricalContext
    )
    from src.intelligence_observer.output_artifacts.intelligence_alert import (
        IntelligenceAlert, AlertType, AlertSeverity
    )
    from src.intelligence_observer.output_artifacts.intelligence_narrative import (
        IntelligenceNarrative, NarrativeType
    )
    
    # Create historical context
    historical_context = HistoricalContext(
        median=50.0,
        p25=25.0,
        p75=75.0,
        p90=90.0,
        p95=95.0,
        similar_periods=["2018-Q4", "2020-Q1"]
    )
    
    # Test intelligence score
    score = IntelligenceScore(
        score_id="test_001",
        score_name="Test Regime Score",
        score_type=ScoreType.REGIME_SIMILARITY,
        value=67.5,
        confidence=0.82,
        timestamp=datetime.now(),
        time_horizon="4-12 weeks",
        historical_context=historical_context,
        interpretation="Current conditions resemble historically volatile periods"
    )
    
    assert score.value == 67.5
    assert score.confidence == 0.82
    assert len(score.forbidden_actions) > 0
    
    print(f"   ✅ Intelligence Score: {score.score_name} = {score.value}")
    
    # Test intelligence alert
    alert = IntelligenceAlert(
        alert_id="alert_001",
        alert_type=AlertType.MONITORING,
        severity=AlertSeverity.MEDIUM,
        message="Regime transition probability elevated above baseline",
        timestamp=datetime.now(),
        confidence=0.75
    )
    
    assert alert.severity == AlertSeverity.MEDIUM
    assert alert.confidence == 0.75
    
    print(f"   ✅ Intelligence Alert: {alert.severity} severity")
    
    # Test intelligence narrative
    narrative = IntelligenceNarrative(
        narrative_id="narrative_001",
        narrative_type=NarrativeType.REGIME_ANALOG,
        title="Market Regime Analysis",
        summary="Current conditions exhibit patterns similar to historical transition periods",
        timestamp=datetime.now(),
        key_similarities=["High volatility", "Elevated correlation"],
        key_differences=["Different credit conditions", "Lower breadth"],
        confidence=0.78
    )
    
    assert narrative.confidence == 0.78
    assert len(narrative.summary) > 0
    
    print(f"   ✅ Intelligence Narrative: {narrative.title}")
    
    return True

def test_audit_trail():
    """Test audit trail functionality"""
    print("📋 Testing Audit Trail...")
    
    from src.intelligence_observer.audit.observer_audit_log import ObserverAuditLog
    
    audit_log = ObserverAuditLog()
    
    # Log events
    audit_log.log_event('test_event', {'data': 'test'})
    audit_log.log_intelligence_output('test_score', {'value': 75.0})
    
    # Get summary
    summary = audit_log.get_audit_summary(days=1)
    assert summary['total_entries'] >= 2
    
    print(f"   ✅ Audit entries: {summary['total_entries']}")
    return True

def test_scheduler():
    """Test scheduler functionality"""
    print("⏰ Testing Scheduler...")
    
    from src.intelligence_observer.observer_core.observer_scheduler import ObserverScheduler
    
    scheduler = ObserverScheduler()
    status = scheduler.get_scheduler_status()
    
    assert 'scheduled_tasks' in status
    assert len(status['scheduled_tasks']) > 0
    
    print(f"   ✅ Scheduled tasks: {len(status['scheduled_tasks'])}")
    return True

def test_integration():
    """Test Northstar integration"""
    print("🔗 Testing Integration...")
    
    from src.intelligence_observer.integration.northstar_integration import ObserverIntegrationManager
    
    # Mock components
    class MockEventBus:
        def subscribe(self, event_type, handler): pass
        def unsubscribe(self, event_type, handler): pass
        def emit(self, event): pass
    
    class MockUnifiedState:
        def __init__(self):
            self.risk_state = type('obj', (object,), {'status': 'NORMAL'})()
    
    class MockMarketClock:
        def get_current_time(self): return datetime.now()
    
    manager = ObserverIntegrationManager()
    success = manager.integrate_with_northstar(
        MockEventBus(), MockUnifiedState(), MockMarketClock()
    )
    
    assert success
    print("   ✅ Integration successful")
    
    manager.shutdown_integration()
    return True

def main():
    """Run validation tests"""
    
    print("🧠 INTELLIGENCE OBSERVER VALIDATION")
    print("=" * 50)
    
    tests = [
        ("Authority Firewall", test_authority_firewall),
        ("Output Artifacts", test_output_artifacts),
        ("Audit Trail", test_audit_trail),
        ("Scheduler", test_scheduler),
        ("Integration", test_integration)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results[test_name] = success
            print(f"✅ {test_name}: {'PASSED' if success else 'FAILED'}")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
            results[test_name] = False
    
    # Summary
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    print(f"\n📊 RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎯 INTELLIGENCE OBSERVER: VALIDATED")
        print("✅ All core components working")
        print("✅ Authority boundaries maintained")
        print("✅ Ready for integration")
        print("\n🧠 The Intelligence Observer makes you wiser, not braver.")
    else:
        print("⚠️  Some components need attention")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)