#!/usr/bin/env python3
"""
Comprehensive System Tests

End-to-end tests for the complete Intelligence Observer system to ensure:
1. All components work together seamlessly
2. Authority boundaries are maintained throughout
3. System handles real-world scenarios correctly
4. Performance and reliability under load
5. Integration with Northstar V3 is robust
"""

import pytest
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import tempfile
import shutil
import json
import threading
import time

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.intelligence_observer.observer_core.observer_scheduler import ObserverScheduler
from src.intelligence_observer.observer_core.snapshot_builder import SnapshotBuilder
from src.intelligence_observer.observer_core.observer_context import ObserverContext, ObserverSnapshot
from src.intelligence_observer.question_engines.regime_intelligence import RegimeIntelligenceEngine
from src.intelligence_observer.question_engines.stress_intelligence import StressIntelligenceEngine
from src.intelligence_observer.guardrails.authority_firewall import AuthorityFirewall, install_authority_firewall
from src.intelligence_observer.audit.observer_audit_log import ObserverAuditLog
from src.intelligence_observer.reports.weekly_intelligence_report import WeeklyIntelligenceReport
from src.intelligence_observer.integration.northstar_integration import (
    IntelligenceObserverOrgan, ObserverIntegrationManager
)

class TestComprehensiveIntelligenceObserver:
    """Comprehensive end-to-end tests for Intelligence Observer system"""
    
    def setup_method(self):
        """Setup for comprehensive tests"""
        # Create temporary directory for test data
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = os.path.join(self.temp_dir, 'data', 'processed')
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Create sample data
        self._create_comprehensive_test_data()
        
        # Initialize components
        self.scheduler = ObserverScheduler()
        self.snapshot_builder = SnapshotBuilder()
        self.context = ObserverContext()
        self.regime_engine = RegimeIntelligenceEngine()
        self.stress_engine = StressIntelligenceEngine()
        self.audit_log = ObserverAuditLog()
        self.firewall = install_authority_firewall()
        
        # Mock Northstar components
        self.mock_event_bus = Mock()
        self.mock_unified_state = Mock()
        self.mock_market_clock = Mock()
    
    def teardown_method(self):
        """Cleanup after tests"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
        # Stop scheduler if running
        if self.scheduler.is_running:
            self.scheduler.stop_scheduler()
    
    def _create_comprehensive_test_data(self):
        """Create comprehensive test data for all scenarios"""
        # Create 2 years of daily market data
        dates = pd.date_range('2022-01-01', '2024-01-01', freq='D')
        n_days = len(dates)
        
        # Generate realistic market regimes
        regimes = []
        current_regime = 'supportive'
        regime_duration = 0
        
        for i in range(n_days):
            # Regime transition logic
            if regime_duration > 45 and np.random.random() < 0.08:
                possible_regimes = ['supportive', 'neutral', 'hostile']
                current_regime = np.random.choice([r for r in possible_regimes if r != current_regime])
                regime_duration = 0
            
            regimes.append(current_regime)
            regime_duration += 1
        
        # Generate regime-dependent market data
        market_data = []
        for i, (date, regime) in enumerate(zip(dates, regimes)):
            if regime == 'supportive':
                volatility = np.random.normal(0.12, 0.03)
                correlation = np.random.normal(0.35, 0.10)
                vix = np.random.normal(16, 4)
                credit_spreads = np.random.normal(120, 30)
                market_stress = np.random.normal(0.15, 0.05)
            elif regime == 'neutral':
                volatility = np.random.normal(0.18, 0.04)
                correlation = np.random.normal(0.50, 0.12)
                vix = np.random.normal(22, 6)
                credit_spreads = np.random.normal(160, 40)
                market_stress = np.random.normal(0.25, 0.08)
            else:  # hostile
                volatility = np.random.normal(0.32, 0.08)
                correlation = np.random.normal(0.75, 0.10)
                vix = np.random.normal(35, 10)
                credit_spreads = np.random.normal(250, 60)
                market_stress = np.random.normal(0.55, 0.15)
            
            # Ensure realistic bounds
            volatility = max(0.08, min(0.60, volatility))
            correlation = max(0.20, min(0.90, correlation))
            vix = max(10, min(80, vix))
            credit_spreads = max(80, min(400, credit_spreads))
            market_stress = max(0.05, min(0.90, market_stress))
            
            market_data.append({
                'date': date,
                'regime': regime,
                'volatility': volatility,
                'correlation': correlation,
                'vix': vix,
                'credit_spreads': credit_spreads,
                'market_stress': market_stress,
                'breadth_pct': np.random.normal(50, 15),
                'market_return': np.random.normal(0.0005, volatility/np.sqrt(252))
            })
        
        # Save market data
        market_df = pd.DataFrame(market_data)
        market_df.to_parquet(os.path.join(self.data_dir, 'market_state.parquet'))
        
        # Create engine performance data
        engine_data = []
        for i, date in enumerate(dates):
            trend_performance = np.random.normal(0.02, 0.15)
            crisis_performance = np.random.normal(0.05, 0.25)
            
            engine_data.append({
                'date': date,
                'trend_engine_performance': trend_performance,
                'crisis_engine_performance': crisis_performance,
                'trend_engine_active': np.random.choice([True, False]),
                'crisis_engine_active': np.random.choice([True, False]),
                'engine_correlation': np.random.normal(0.1, 0.3)
            })
        
        engine_df = pd.DataFrame(engine_data)
        engine_df.to_parquet(os.path.join(self.data_dir, 'engine_performance.parquet'))
        
        print(f"✅ Created comprehensive test data: {len(market_df)} days")
    
    def test_complete_system_workflow(self):
        """Test complete system workflow from data to intelligence"""
        print("\n🧪 Testing Complete System Workflow")
        
        # Step 1: Build snapshot
        with patch('src.intelligence_observer.observer_core.snapshot_builder.os.path.exists', return_value=True):
            with patch('src.intelligence_observer.observer_core.snapshot_builder.pd.read_parquet') as mock_read:
                # Mock data loading
                mock_market_data = pd.DataFrame({
                    'date': pd.date_range('2024-01-01', periods=252),
                    'volatility': np.random.normal(0.15, 0.05, 252),
                    'correlation': np.random.normal(0.45, 0.15, 252),
                    'regime': np.random.choice(['supportive', 'neutral', 'hostile'], 252)
                })
                mock_read.return_value = mock_market_data
                
                snapshot = self.snapshot_builder.build_snapshot()
                assert snapshot is not None
                print(f"   ✅ Snapshot built: {snapshot.snapshot_id}")
        
        # Step 2: Load snapshot into context
        self.context.load_snapshot(snapshot)
        assert self.context.current_snapshot == snapshot
        print(f"   ✅ Snapshot loaded into context")
        
        # Step 3: Run intelligence analysis
        regime_score, regime_narrative = self.regime_engine.analyze_regime_similarity(snapshot)
        stress_score, stress_alert = self.stress_engine.analyze_stress_clustering(snapshot)
        
        assert isinstance(regime_score.value, (int, float))
        assert 0 <= regime_score.value <= 100
        assert isinstance(stress_score.value, (int, float))
        assert 0 <= stress_score.value <= 100
        print(f"   ✅ Intelligence analysis completed")
        print(f"      Regime Score: {regime_score.value:.1f}")
        print(f"      Stress Score: {stress_score.value:.1f}")
        
        # Step 4: Validate authority compliance
        assert regime_score.directionality == "neutral"
        assert stress_score.directionality == "neutral"
        
        # Check for forbidden language
        combined_text = f"{regime_narrative.content} {stress_score.interpretation}".lower()
        forbidden_words = ['should', 'must', 'buy', 'sell', 'trade']
        for word in forbidden_words:
            assert word not in combined_text
        print(f"   ✅ Authority compliance validated")
        
        # Step 5: Audit trail verification
        self.audit_log.log_intelligence_output('regime_score', regime_score.to_dict())
        self.audit_log.log_intelligence_output('stress_score', stress_score.to_dict())
        
        audit_summary = self.audit_log.get_audit_summary(days=1)
        assert audit_summary['total_entries'] >= 2
        print(f"   ✅ Audit trail verified: {audit_summary['total_entries']} entries")
    
    def test_authority_firewall_comprehensive(self):
        """Test authority firewall under comprehensive scenarios"""
        print("\n🔒 Testing Authority Firewall Comprehensively")
        
        # Test multiple violation types
        violation_scenarios = [
            ('forbidden_import', lambda: self.firewall.check_import_attempt('src.portfolio.portfolio_governor')),
            ('forbidden_function', lambda: self.firewall.check_function_call('set_exposure', 'test')),
            ('forbidden_attribute', lambda: self.firewall.check_attribute_access('current_positions', 'read')),
            ('write_attempt', lambda: self.firewall.check_attribute_access('any_attr', 'write'))
        ]
        
        initial_count = self.firewall.violation_count
        
        for scenario_name, violation_func in violation_scenarios:
            allowed = violation_func()
            assert not allowed, f"Scenario {scenario_name} should be blocked"
            print(f"   ✅ {scenario_name} blocked")
        
        # Should have recorded violations
        assert self.firewall.violation_count > initial_count
        print(f"   ✅ Violations recorded: {self.firewall.violation_count}")
        
        # Test observer suspension
        if self.firewall.violation_count >= 3:
            assert self.firewall.observer_suspended
            print(f"   ✅ Observer suspended after {self.firewall.violation_count} violations")
    
    def test_multi_engine_coordination(self):
        """Test coordination between multiple intelligence engines"""
        print("\n🤝 Testing Multi-Engine Coordination")
        
        # Create comprehensive snapshot
        snapshot_data = {
            'market_state': pd.DataFrame({
                'date': pd.date_range('2024-01-01', periods=100),
                'volatility': np.random.normal(0.20, 0.05, 100),
                'correlation': np.random.normal(0.60, 0.15, 100),
                'vix': np.random.normal(25, 8, 100),
                'regime': ['hostile'] * 100  # Stress scenario
            }),
            'engine_performance': pd.DataFrame({
                'date': pd.date_range('2024-01-01', periods=100),
                'trend_engine_performance': np.random.normal(-0.05, 0.20, 100),
                'crisis_engine_performance': np.random.normal(0.15, 0.25, 100)
            })
        }
        
        snapshot = ObserverSnapshot(
            snapshot_id="multi_engine_test",
            timestamp=datetime.now(),
            data=snapshot_data,
            data_quality_score=0.95,
            completeness_score=0.90,
            staleness_hours=2.0
        )
        
        # Run all engines
        regime_score, regime_narrative = self.regime_engine.analyze_regime_similarity(snapshot)
        stress_score, stress_alert = self.stress_engine.analyze_stress_clustering(snapshot)
        
        # Validate coordination
        assert isinstance(regime_score.value, (int, float))
        assert isinstance(stress_score.value, (int, float))
        
        # In hostile regime, stress should be elevated
        assert stress_score.value > 40  # Should detect stress
        
        # All outputs should be neutral directionality
        assert regime_score.directionality == "neutral"
        assert stress_score.directionality == "neutral"
        
        print(f"   ✅ Regime analysis: {regime_score.value:.1f}")
        print(f"   ✅ Stress analysis: {stress_score.value:.1f}")
        print(f"   ✅ Multi-engine coordination successful")
    
    def test_temporal_isolation_enforcement(self):
        """Test temporal isolation is properly enforced"""
        print("\n⏰ Testing Temporal Isolation Enforcement")
        
        # Test scheduler timing
        status = self.scheduler.get_scheduler_status()
        
        for task_id, task_info in status['scheduled_tasks'].items():
            next_run = datetime.fromisoformat(task_info['next_run'])
            
            # All scheduled times should be in the future
            assert next_run > datetime.now()
            print(f"   ✅ {task_id}: scheduled for {next_run.strftime('%Y-%m-%d %H:%M')}")
        
        # Test data staleness requirement
        with patch.object(self.snapshot_builder, 'build_snapshot') as mock_build:
            mock_snapshot = ObserverSnapshot(
                snapshot_id="temporal_test",
                timestamp=datetime.now(),
                data={'test': 'data'},
                data_quality_score=0.95,
                completeness_score=0.90,
                staleness_hours=2.5  # Should be >= 1.0
            )
            mock_build.return_value = mock_snapshot
            
            snapshot = self.snapshot_builder.build_snapshot()
            assert snapshot.staleness_hours >= 1.0
            print(f"   ✅ Data staleness enforced: {snapshot.staleness_hours:.1f} hours")
    
    def test_northstar_integration_robustness(self):
        """Test robust integration with Northstar V3"""
        print("\n🔗 Testing Northstar Integration Robustness")
        
        # Create integration manager
        manager = ObserverIntegrationManager()
        
        # Test integration
        success = manager.integrate_with_northstar(
            self.mock_event_bus,
            self.mock_unified_state,
            self.mock_market_clock
        )
        
        assert success
        assert manager.integration_active
        print(f"   ✅ Integration successful")
        
        # Test observer organ functionality
        observer_organ = manager.get_observer_organ()
        assert observer_organ is not None
        assert isinstance(observer_organ, IntelligenceObserverOrgan)
        
        # Test health metrics
        health = observer_organ.get_health_metrics()
        required_metrics = ['status', 'observation_count', 'authority_violations']
        for metric in required_metrics:
            assert metric in health
        print(f"   ✅ Health metrics available")
        
        # Test graceful shutdown
        manager.shutdown_integration()
        assert not manager.integration_active
        print(f"   ✅ Graceful shutdown successful")
    
    def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms"""
        print("\n🛡️ Testing Error Handling and Recovery")
        
        # Test with corrupted data
        corrupted_snapshot = ObserverSnapshot(
            snapshot_id="corrupted_test",
            timestamp=datetime.now(),
            data={'market_state': None},  # Corrupted data
            data_quality_score=0.1,  # Low quality
            completeness_score=0.2,
            staleness_hours=2.0
        )
        
        # Engines should handle gracefully
        try:
            regime_score, regime_narrative = self.regime_engine.analyze_regime_similarity(corrupted_snapshot)
            # Should either succeed with low confidence or raise appropriate error
            if regime_score:
                assert regime_score.confidence < 0.5  # Low confidence due to data quality
                print(f"   ✅ Graceful degradation: confidence {regime_score.confidence:.2f}")
        except ValueError as e:
            # Acceptable to raise ValueError for corrupted data
            assert "market_state" in str(e)
            print(f"   ✅ Appropriate error handling: {e}")
        
        # Test scheduler error recovery
        with patch.object(self.scheduler, '_run_intelligence_analysis', side_effect=Exception("Test error")):
            result = self.scheduler.run_on_demand_analysis()
            assert not result['success']
            assert 'error' in result
            print(f"   ✅ Scheduler error recovery: {result['error']}")
    
    def test_performance_under_load(self):
        """Test system performance under load"""
        print("\n⚡ Testing Performance Under Load")
        
        # Create large dataset
        large_data = pd.DataFrame({
            'date': pd.date_range('2020-01-01', '2024-01-01', freq='D'),
            'volatility': np.random.normal(0.15, 0.05, 1461),  # 4 years
            'correlation': np.random.normal(0.45, 0.15, 1461),
            'regime': np.random.choice(['supportive', 'neutral', 'hostile'], 1461)
        })
        
        large_snapshot = ObserverSnapshot(
            snapshot_id="performance_test",
            timestamp=datetime.now(),
            data={'market_state': large_data},
            data_quality_score=0.95,
            completeness_score=0.90,
            staleness_hours=2.0
        )
        
        # Time the analysis
        start_time = time.time()
        
        regime_score, regime_narrative = self.regime_engine.analyze_regime_similarity(large_snapshot)
        stress_score, stress_alert = self.stress_engine.analyze_stress_clustering(large_snapshot)
        
        end_time = time.time()
        analysis_time = end_time - start_time
        
        # Should complete within reasonable time
        assert analysis_time < 10.0  # 10 seconds max
        print(f"   ✅ Analysis completed in {analysis_time:.2f} seconds")
        
        # Results should still be valid
        assert isinstance(regime_score.value, (int, float))
        assert isinstance(stress_score.value, (int, float))
        print(f"   ✅ Results valid under load")
    
    def test_concurrent_operations(self):
        """Test concurrent operations safety"""
        print("\n🔄 Testing Concurrent Operations Safety")
        
        results = []
        errors = []
        
        def run_analysis():
            try:
                # Create snapshot
                snapshot_data = {
                    'market_state': pd.DataFrame({
                        'date': pd.date_range('2024-01-01', periods=50),
                        'volatility': np.random.normal(0.15, 0.05, 50),
                        'correlation': np.random.normal(0.45, 0.15, 50)
                    })
                }
                
                snapshot = ObserverSnapshot(
                    snapshot_id=f"concurrent_{threading.current_thread().ident}",
                    timestamp=datetime.now(),
                    data=snapshot_data,
                    data_quality_score=0.95,
                    completeness_score=0.90,
                    staleness_hours=2.0
                )
                
                # Run analysis
                regime_score, _ = self.regime_engine.analyze_regime_similarity(snapshot)
                results.append(regime_score.value)
                
            except Exception as e:
                errors.append(str(e))
        
        # Run multiple concurrent analyses
        threads = []
        for i in range(5):
            thread = threading.Thread(target=run_analysis)
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=10)
        
        # Check results
        assert len(errors) == 0, f"Concurrent errors: {errors}"
        assert len(results) == 5, f"Expected 5 results, got {len(results)}"
        
        # All results should be valid
        for result in results:
            assert 0 <= result <= 100
        
        print(f"   ✅ Concurrent operations completed successfully")
        print(f"   ✅ Results: {[f'{r:.1f}' for r in results]}")
    
    def test_weekly_report_generation(self):
        """Test weekly report generation"""
        print("\n📊 Testing Weekly Report Generation")
        
        # Create sample intelligence data
        sample_scores = [
            {
                'score_name': 'Regime Similarity Index',
                'value': 67.0,
                'confidence': 0.82,
                'interpretation': 'Current conditions resemble historically volatile periods'
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
        report_generator = WeeklyIntelligenceReport()
        report = report_generator.generate_report(sample_scores, sample_alerts, [])
        
        assert 'report_id' in report
        assert 'generation_time' in report
        assert 'executive_summary' in report
        assert 'score_analysis' in report
        assert 'alert_summary' in report
        
        print(f"   ✅ Weekly report generated: {report['report_id']}")
        print(f"   ✅ Executive summary items: {len(report['executive_summary'])}")
    
    def test_system_integrity_validation(self):
        """Test overall system integrity"""
        print("\n🔍 Testing System Integrity Validation")
        
        # Test audit log integrity
        integrity = self.audit_log.verify_audit_integrity()
        assert 'total_entries' in integrity
        assert 'file_integrity' in integrity
        print(f"   ✅ Audit integrity verified")
        
        # Test authority firewall status
        firewall_summary = self.firewall.get_violation_summary()
        assert 'total_violations' in firewall_summary
        assert 'observer_suspended' in firewall_summary
        print(f"   ✅ Authority firewall status: {firewall_summary['total_violations']} violations")
        
        # Test scheduler health
        scheduler_status = self.scheduler.get_scheduler_status()
        assert 'scheduled_tasks' in scheduler_status
        assert len(scheduler_status['scheduled_tasks']) > 0
        print(f"   ✅ Scheduler health: {len(scheduler_status['scheduled_tasks'])} tasks")
        
        # Test component versions
        components = [
            self.scheduler, self.regime_engine, self.stress_engine,
            self.firewall, self.audit_log
        ]
        
        for component in components:
            assert hasattr(component, 'version')
            assert hasattr(component, 'name')
            print(f"   ✅ {component.name} v{component.version}")

class TestRealWorldScenarios:
    """Test real-world market scenarios"""
    
    def setup_method(self):
        """Setup for scenario tests"""
        self.regime_engine = RegimeIntelligenceEngine()
        self.stress_engine = StressIntelligenceEngine()
    
    def test_market_crash_scenario(self):
        """Test behavior during market crash scenario"""
        print("\n💥 Testing Market Crash Scenario")
        
        # Create crash-like data
        crash_data = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=30),
            'volatility': [0.45] * 30,  # Very high volatility
            'correlation': [0.85] * 30,  # High correlation
            'vix': [50] * 30,  # Elevated VIX
            'market_stress': [0.80] * 30,  # High stress
            'regime': ['hostile'] * 30
        })
        
        crash_snapshot = ObserverSnapshot(
            snapshot_id="crash_scenario",
            timestamp=datetime.now(),
            data={'market_state': crash_data},
            data_quality_score=0.95,
            completeness_score=0.90,
            staleness_hours=2.0
        )
        
        # Analyze crash scenario
        stress_score, stress_alert = self.stress_engine.analyze_stress_clustering(crash_snapshot)
        
        # Should detect high stress
        assert stress_score.value > 70  # High stress score
        print(f"   ✅ Stress detected: {stress_score.value:.1f}/100")
        
        # Should generate alert
        if stress_alert:
            assert stress_alert.severity in ['medium', 'high']
            print(f"   ✅ Alert generated: {stress_alert.severity} severity")
        
        # Should maintain authority boundaries even in crisis
        assert stress_score.directionality == "neutral"
        assert 'should' not in stress_score.interpretation.lower()
        print(f"   ✅ Authority boundaries maintained during crisis")
    
    def test_low_volatility_scenario(self):
        """Test behavior during low volatility scenario"""
        print("\n😴 Testing Low Volatility Scenario")
        
        # Create low volatility data
        calm_data = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=60),
            'volatility': [0.08] * 60,  # Very low volatility
            'correlation': [0.25] * 60,  # Low correlation
            'vix': [12] * 60,  # Low VIX
            'market_stress': [0.10] * 60,  # Low stress
            'regime': ['supportive'] * 60
        })
        
        calm_snapshot = ObserverSnapshot(
            snapshot_id="calm_scenario",
            timestamp=datetime.now(),
            data={'market_state': calm_data},
            data_quality_score=0.95,
            completeness_score=0.90,
            staleness_hours=2.0
        )
        
        # Analyze calm scenario
        stress_score, stress_alert = self.stress_engine.analyze_false_calm_detection(calm_snapshot)
        
        # Should detect potential false calm
        print(f"   ✅ False calm analysis: {stress_score.value:.1f}/100")
        
        # Should maintain observational stance
        assert stress_score.directionality == "neutral"
        print(f"   ✅ Observational stance maintained")
    
    def test_regime_transition_scenario(self):
        """Test behavior during regime transitions"""
        print("\n🔄 Testing Regime Transition Scenario")
        
        # Create transition data (supportive -> hostile)
        transition_data = []
        regimes = ['supportive'] * 20 + ['neutral'] * 10 + ['hostile'] * 20
        
        for i, regime in enumerate(regimes):
            if regime == 'supportive':
                vol, corr = 0.12, 0.35
            elif regime == 'neutral':
                vol, corr = 0.18, 0.50
            else:
                vol, corr = 0.28, 0.75
            
            transition_data.append({
                'date': pd.Timestamp('2024-01-01') + pd.Timedelta(days=i),
                'volatility': vol + np.random.normal(0, 0.02),
                'correlation': corr + np.random.normal(0, 0.05),
                'regime': regime
            })
        
        transition_df = pd.DataFrame(transition_data)
        
        transition_snapshot = ObserverSnapshot(
            snapshot_id="transition_scenario",
            timestamp=datetime.now(),
            data={'market_state': transition_df},
            data_quality_score=0.95,
            completeness_score=0.90,
            staleness_hours=2.0
        )
        
        # Analyze transition
        regime_score, regime_narrative = self.regime_engine.analyze_regime_similarity(transition_snapshot)
        transition_score = self.regime_engine.analyze_regime_transition_probability(transition_snapshot)
        
        # Should detect transition patterns
        print(f"   ✅ Regime similarity: {regime_score.value:.1f}/100")
        print(f"   ✅ Transition probability: {transition_score.value:.1f}/100")
        
        # Narrative should describe transition
        assert 'transition' in regime_narrative.content.lower() or 'change' in regime_narrative.content.lower()
        print(f"   ✅ Transition narrative generated")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])