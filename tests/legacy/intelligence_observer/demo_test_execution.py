#!/usr/bin/env python3
"""
Intelligence Observer Demo Test Execution

This script demonstrates that the Intelligence Observer system works correctly
by running key functionality tests and validating the core principles.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

def test_authority_firewall():
    """Test that authority firewall works correctly"""
    print("🔒 Testing Authority Firewall...")
    
    from src.intelligence_observer.guardrails.authority_firewall import AuthorityFirewall
    
    firewall = AuthorityFirewall()
    
    # Test forbidden imports
    assert not firewall.check_import_attempt('src.portfolio.portfolio_governor')
    assert not firewall.check_function_call('set_exposure', 'test')
    assert not firewall.check_attribute_access('current_positions', 'read')
    
    # Test valid operations
    assert firewall.check_import_attempt('pandas')
    assert firewall.check_function_call('analyze_data', 'test')
    assert firewall.check_attribute_access('historical_data', 'read')
    
    # Test observer suspension
    for i in range(5):
        firewall.check_import_attempt('src.portfolio.portfolio_governor')
    
    assert firewall.observer_suspended
    assert firewall.violation_count >= 3
    
    print("   ✅ Authority firewall working correctly")
    print(f"   ✅ Violations recorded: {firewall.violation_count}")
    print(f"   ✅ Observer suspended: {firewall.observer_suspended}")
    
    return True

def test_intelligence_engines():
    """Test that intelligence engines work correctly"""
    print("🧠 Testing Intelligence Engines...")
    
    from src.intelligence_observer.question_engines.regime_intelligence import RegimeIntelligenceEngine
    from src.intelligence_observer.question_engines.stress_intelligence import StressIntelligenceEngine
    from src.intelligence_observer.observer_core.observer_context import (
        ObserverSnapshot, MarketStateSummary, EngineStateHistory, 
        LaggedPortfolioStats, HistoricalContext
    )
    
    # Create test engines
    regime_engine = RegimeIntelligenceEngine()
    stress_engine = StressIntelligenceEngine()
    
    # Create mock snapshot
    market_state = MarketStateSummary(
        timestamp=datetime.now() - timedelta(hours=2),
        regime='supportive',
        volatility_regime='normal',
        risk_on_probability=0.75,
        allowed_exposure=0.8,
        market_stress=0.15,
        breadth_pct=65.0,
        correlation=0.35,
        volatility_20d=0.12,
        volatility_60d=0.14,
        drawdown_current=-0.02,
        trend_strength=0.6
    )
    
    engine_states = EngineStateHistory(
        timestamp=datetime.now() - timedelta(hours=2),
        active_engine='trend',
        regime_classification='supportive',
        regime_confidence=0.85,
        trend_allocation=0.8,
        crisis_allocation=0.0,
        trend_engine_active_days=15,
        crisis_engine_active_days=0,
        trend_engine_last_return=0.02,
        crisis_engine_last_return=None,
        regime_changes_30d=1,
        regime_stability_score=0.9,
        last_regime_change=datetime.now() - timedelta(days=20)
    )
    
    portfolio_stats = LaggedPortfolioStats(
        timestamp=datetime.now() - timedelta(hours=2),
        total_return_1d=0.005,
        total_return_7d=0.02,
        total_return_30d=0.08,
        volatility_30d=0.12,
        sharpe_ratio_30d=1.5,
        max_drawdown_30d=-0.03,
        avg_exposure_7d=0.75,
        avg_exposure_30d=0.72,
        turnover_7d=0.15,
        var_95_1d=-0.02,
        concentration_score=0.25,
        sector_concentration_max=0.35
    )
    
    historical_context = HistoricalContext(
        timestamp=datetime.now() - timedelta(hours=2),
        regime_history_1y=['supportive'] * 100,
        volatility_history_1y=[0.12] * 100,
        return_history_1y=[0.001] * 100,
        crisis_periods=[],
        stress_periods=[],
        regime_transition_matrix={'supportive': {'neutral': 0.1, 'hostile': 0.05}},
        avg_regime_duration={'supportive': 45.0, 'neutral': 30.0, 'hostile': 20.0},
        correlation_history_1y=[0.35] * 100,
        breadth_history_1y=[65.0] * 100
    )
    
    snapshot = ObserverSnapshot(
        snapshot_id="test_001",
        creation_time=datetime.now(),
        data_cutoff_time=datetime.now() - timedelta(hours=2),
        market_state=market_state,
        engine_states=engine_states,
        portfolio_stats=portfolio_stats,
        historical_context=historical_context,
        data_quality_score=0.95,
        completeness_score=0.90,
        staleness_hours=2.5
    )
    
    # Test regime intelligence
    regime_score, regime_narrative = regime_engine.analyze_regime_similarity(snapshot)
    
    assert 0 <= regime_score.value <= 100
    assert 0 <= regime_score.confidence <= 1
    assert regime_score.directionality == "neutral"
    assert len(regime_narrative.content) > 0
    
    print(f"   ✅ Regime analysis: {regime_score.value:.1f}/100 (confidence: {regime_score.confidence:.2f})")
    
    # Test stress intelligence
    stress_score, stress_alert = stress_engine.analyze_stress_clustering(snapshot)
    
    assert 0 <= stress_score.value <= 100
    assert 0 <= stress_score.confidence <= 1
    assert stress_score.directionality == "neutral"
    
    print(f"   ✅ Stress analysis: {stress_score.value:.1f}/100 (confidence: {stress_score.confidence:.2f})")
    
    # Test authority compliance
    combined_text = f"{regime_narrative.content} {stress_score.interpretation}".lower()
    forbidden_words = ['should', 'must', 'buy', 'sell', 'trade']
    for word in forbidden_words:
        assert word not in combined_text, f"Forbidden word '{word}' found in output"
    
    print("   ✅ Authority compliance validated")
    
    return True

def test_output_artifacts():
    """Test that output artifacts work correctly"""
    print("📊 Testing Output Artifacts...")
    
    from src.intelligence_observer.output_artifacts.intelligence_score import IntelligenceScore
    from src.intelligence_observer.output_artifacts.intelligence_alert import IntelligenceAlert
    from src.intelligence_observer.output_artifacts.intelligence_narrative import IntelligenceNarrative
    from src.intelligence_observer.output_artifacts.output_sanitizer import OutputSanitizer
    
    # Test intelligence score
    score = IntelligenceScore(
        score_name="Test Regime Score",
        value=67.5,
        confidence=0.82,
        interpretation="Current conditions resemble historically volatile periods"
    )
    
    assert score.value == 67.5
    assert score.confidence == 0.82
    assert score.directionality == "neutral"
    assert len(score.disclaimer) > 0
    
    print(f"   ✅ Intelligence Score: {score.score_name} = {score.value}")
    
    # Test intelligence alert
    alert = IntelligenceAlert(
        alert_type="monitoring",
        severity="medium",
        message="Regime transition probability elevated above baseline",
        confidence=0.75
    )
    
    assert alert.severity == "medium"
    assert alert.confidence == 0.75
    assert len(alert.non_recommended_actions) > 0
    
    print(f"   ✅ Intelligence Alert: {alert.severity} severity")
    
    # Test intelligence narrative
    narrative = IntelligenceNarrative(
        title="Market Regime Analysis",
        content="Current conditions exhibit patterns similar to historical transition periods",
        narrative_type="regime_analysis",
        confidence=0.78
    )
    
    assert narrative.confidence == 0.78
    assert len(narrative.content) > 0
    assert len(narrative.disclaimer) > 0
    
    print(f"   ✅ Intelligence Narrative: {narrative.title}")
    
    # Test output sanitizer
    sanitizer = OutputSanitizer()
    
    # Test forbidden content removal
    forbidden_text = "System should buy more stocks immediately"
    sanitized_text = sanitizer.sanitize_text(forbidden_text)
    
    assert 'should buy' not in sanitized_text.lower()
    print(f"   ✅ Output Sanitizer: Forbidden content removed")
    
    return True

def test_audit_trail():
    """Test that audit trail works correctly"""
    print("📋 Testing Audit Trail...")
    
    from src.intelligence_observer.audit.observer_audit_log import ObserverAuditLog
    
    audit_log = ObserverAuditLog()
    
    # Log some events
    audit_log.log_event('test_event', {'data': 'test'})
    audit_log.log_intelligence_output('test_score', {'value': 75.0})
    audit_log.log_system_interaction('test_read', {'component': 'test'})
    
    # Get audit summary
    summary = audit_log.get_audit_summary(days=1)
    
    assert summary['total_entries'] >= 3
    assert 'event_types' in summary
    
    print(f"   ✅ Audit entries logged: {summary['total_entries']}")
    
    # Verify integrity
    integrity = audit_log.verify_audit_integrity()
    
    assert 'total_entries' in integrity
    print(f"   ✅ Audit integrity verified")
    
    return True

def test_scheduler():
    """Test that scheduler works correctly"""
    print("⏰ Testing Observer Scheduler...")
    
    from src.intelligence_observer.observer_core.observer_scheduler import ObserverScheduler
    
    scheduler = ObserverScheduler()
    
    # Get status
    status = scheduler.get_scheduler_status()
    
    assert 'scheduled_tasks' in status
    assert 'is_running' in status
    assert len(status['scheduled_tasks']) > 0
    
    print(f"   ✅ Scheduled tasks: {len(status['scheduled_tasks'])}")
    
    # Check task timing
    for task_id, task_info in status['scheduled_tasks'].items():
        next_run = datetime.fromisoformat(task_info['next_run'])
        assert next_run > datetime.now()
        print(f"   ✅ {task_id}: {next_run.strftime('%Y-%m-%d %H:%M')}")
    
    return True

def test_northstar_integration():
    """Test Northstar V3 integration"""
    print("🔗 Testing Northstar Integration...")
    
    from src.intelligence_observer.integration.northstar_integration import (
        IntelligenceObserverOrgan, ObserverIntegrationManager
    )
    
    # Create mock Northstar components
    class MockEventBus:
        def __init__(self):
            self.subscriptions = {}
        def subscribe(self, event_type, handler):
            self.subscriptions[event_type] = handler
        def unsubscribe(self, event_type, handler):
            pass
        def emit(self, event):
            pass
    
    class MockUnifiedState:
        def __init__(self):
            self.risk_state = type('obj', (object,), {'status': 'NORMAL'})()
    
    class MockMarketClock:
        def get_current_time(self):
            return datetime.now()
    
    # Test integration
    manager = ObserverIntegrationManager()
    
    success = manager.integrate_with_northstar(
        MockEventBus(),
        MockUnifiedState(),
        MockMarketClock()
    )
    
    assert success
    assert manager.integration_active
    
    print("   ✅ Integration successful")
    
    # Test observer organ
    observer_organ = manager.get_observer_organ()
    assert observer_organ is not None
    
    health = observer_organ.get_health_metrics()
    assert 'status' in health
    assert 'observation_count' in health
    
    print("   ✅ Observer organ functional")
    
    # Test shutdown
    manager.shutdown_integration()
    assert not manager.integration_active
    
    print("   ✅ Graceful shutdown")
    
    return True

def main():
    """Run all Intelligence Observer tests"""
    
    print("🧠 INTELLIGENCE OBSERVER SYSTEM VALIDATION")
    print("=" * 60)
    print("Testing all critical components of the Intelligence Observer Layer")
    print("=" * 60)
    
    tests = [
        ("Authority Firewall", test_authority_firewall),
        ("Intelligence Engines", test_intelligence_engines),
        ("Output Artifacts", test_output_artifacts),
        ("Audit Trail", test_audit_trail),
        ("Observer Scheduler", test_scheduler),
        ("Northstar Integration", test_northstar_integration)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 40)
        
        try:
            success = test_func()
            results[test_name] = success
            
            if success:
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
                
        except Exception as e:
            print(f"💥 {test_name}: ERROR - {e}")
            results[test_name] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 VALIDATION SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    print(f"Tests Passed: {passed}/{total}")
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
    
    # Final verdict
    print(f"\n" + "=" * 60)
    if passed == total:
        print("🎯 INTELLIGENCE OBSERVER LAYER: FULLY VALIDATED")
        print("✅ All authority boundaries maintained")
        print("✅ All components functioning correctly")
        print("✅ Integration with V3 architecture working")
        print("✅ System reliability confirmed")
        print("\n🧠 The Intelligence Observer makes you wiser, not braver.")
        print("⚖️  Bravery is already encoded in your engines.")
    else:
        print("⚠️  INTELLIGENCE OBSERVER LAYER: PARTIAL VALIDATION")
        print(f"❌ {total - passed} components need attention")
        print("🔧 Review failed components before deployment")
    
    print("=" * 60)
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)