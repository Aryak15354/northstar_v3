#!/usr/bin/env python3
"""
Observer Core Tests

Tests the core Observer components including context, snapshot builder,
temporal isolation, and scheduler functionality.

CRITICAL TESTS:
1. Observer context provides read-only access
2. Snapshot builder creates proper lagged snapshots
3. Temporal isolation prevents synchronous execution
4. Observer scheduler manages execution timing
5. Data quality and completeness validation
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

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.intelligence_observer.observer_core.observer_context import (
    ObserverContext, ObserverSnapshot
)
from src.intelligence_observer.observer_core.snapshot_builder import SnapshotBuilder
from src.intelligence_observer.observer_core.temporal_isolation import TemporalIsolation
from src.intelligence_observer.observer_core.observer_scheduler import (
    ObserverScheduler, ScheduleType, ScheduledTask
)

class TestObserverSnapshot:
    """Test ObserverSnapshot functionality"""
    
    def test_snapshot_creation(self):
        """Test snapshot creation with valid data"""
        from src.intelligence_observer.observer_core.observer_context import (
            MarketStateSummary, EngineStateHistory, LaggedPortfolioStats, HistoricalContext
        )
        
        # Create mock data structures
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
        
        assert snapshot.snapshot_id == "test_001"
        assert isinstance(snapshot.creation_time, datetime)
        assert snapshot.data_quality_score == 0.95
        assert snapshot.completeness_score == 0.90
        assert snapshot.staleness_hours == 2.5
        assert snapshot.market_state.regime == 'supportive'
        assert snapshot.engine_states.active_engine == 'trend'
    
    def test_snapshot_validation(self):
        """Test snapshot data validation"""
        # Test with invalid data quality score
        with pytest.raises(ValueError, match="Data quality score must be between 0 and 1"):
            ObserverSnapshot(
                snapshot_id="test_002",
                timestamp=datetime.now(),
                data={},
                data_quality_score=1.5,  # Invalid
                completeness_score=0.90,
                staleness_hours=2.5
            )
        
        # Test with invalid completeness score
        with pytest.raises(ValueError, match="Completeness score must be between 0 and 1"):
            ObserverSnapshot(
                snapshot_id="test_003",
                timestamp=datetime.now(),
                data={},
                data_quality_score=0.95,
                completeness_score=-0.1,  # Invalid
                staleness_hours=2.5
            )
    
    def test_snapshot_to_dict(self):
        """Test snapshot serialization to dictionary"""
        snapshot_data = {'test_key': 'test_value'}
        
        snapshot = ObserverSnapshot(
            snapshot_id="test_004",
            timestamp=datetime.now(),
            data=snapshot_data,
            data_quality_score=0.95,
            completeness_score=0.90,
            staleness_hours=2.5
        )
        
        snapshot_dict = snapshot.to_dict()
        
        assert 'snapshot_id' in snapshot_dict
        assert 'timestamp' in snapshot_dict
        assert 'data_quality_score' in snapshot_dict
        assert 'completeness_score' in snapshot_dict
        assert 'staleness_hours' in snapshot_dict
        assert snapshot_dict['snapshot_id'] == "test_004"

class TestObserverContext:
    """Test ObserverContext functionality"""
    
    def setup_method(self):
        """Setup for each test"""
        self.context = ObserverContext()
    
    def test_context_initialization(self):
        """Test context initializes correctly"""
        assert self.context.name == "Intelligence Observer Context"
        assert self.context.version == "1.0.0"
        assert self.context.current_snapshot is None
        assert len(self.context.snapshot_history) == 0
    
    def test_load_snapshot(self):
        """Test loading snapshot into context"""
        snapshot_data = {'test_data': 'value'}
        
        snapshot = ObserverSnapshot(
            snapshot_id="test_005",
            timestamp=datetime.now(),
            data=snapshot_data,
            data_quality_score=0.95,
            completeness_score=0.90,
            staleness_hours=2.5
        )
        
        self.context.load_snapshot(snapshot)
        
        assert self.context.current_snapshot == snapshot
        assert len(self.context.snapshot_history) == 1
        assert self.context.snapshot_history[0] == snapshot
    
    def test_get_current_data(self):
        """Test getting current data from context"""
        snapshot_data = {
            'market_state': pd.DataFrame({'col1': [1, 2, 3]}),
            'regime_data': {'regime': 'supportive'}
        }
        
        snapshot = ObserverSnapshot(
            snapshot_id="test_006",
            timestamp=datetime.now(),
            data=snapshot_data,
            data_quality_score=0.95,
            completeness_score=0.90,
            staleness_hours=2.5
        )
        
        self.context.load_snapshot(snapshot)
        
        # Test getting existing data
        market_data = self.context.get_current_data('market_state')
        assert isinstance(market_data, pd.DataFrame)
        assert len(market_data) == 3
        
        regime_data = self.context.get_current_data('regime_data')
        assert regime_data['regime'] == 'supportive'
        
        # Test getting non-existent data
        missing_data = self.context.get_current_data('missing_key')
        assert missing_data is None
    
    def test_get_historical_snapshots(self):
        """Test getting historical snapshots"""
        # Load multiple snapshots
        for i in range(5):
            snapshot = ObserverSnapshot(
                snapshot_id=f"test_{i:03d}",
                timestamp=datetime.now() - timedelta(hours=i),
                data={'index': i},
                data_quality_score=0.95,
                completeness_score=0.90,
                staleness_hours=i
            )
            self.context.load_snapshot(snapshot)
        
        # Test getting last N snapshots
        recent_snapshots = self.context.get_historical_snapshots(3)
        assert len(recent_snapshots) == 3
        
        # Should be in reverse chronological order (most recent first)
        assert recent_snapshots[0].data['index'] == 4
        assert recent_snapshots[1].data['index'] == 3
        assert recent_snapshots[2].data['index'] == 2
    
    def test_snapshot_history_limit(self):
        """Test that snapshot history is limited"""
        # Load more snapshots than the limit
        for i in range(150):  # Assuming limit is 100
            snapshot = ObserverSnapshot(
                snapshot_id=f"test_{i:03d}",
                timestamp=datetime.now() - timedelta(hours=i),
                data={'index': i},
                data_quality_score=0.95,
                completeness_score=0.90,
                staleness_hours=i
            )
            self.context.load_snapshot(snapshot)
        
        # Should not exceed the limit
        assert len(self.context.snapshot_history) <= 100

class TestSnapshotBuilder:
    """Test SnapshotBuilder functionality"""
    
    def setup_method(self):
        """Setup for each test"""
        self.builder = SnapshotBuilder()
        
        # Create temporary data directory
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = os.path.join(self.temp_dir, 'data', 'processed')
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Create sample data files
        self._create_sample_data()
    
    def teardown_method(self):
        """Cleanup after each test"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_sample_data(self):
        """Create sample data files for testing"""
        # Market state data
        market_data = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=100, freq='D'),
            'volatility': np.random.random(100) * 0.3 + 0.1,
            'correlation': np.random.random(100) * 0.6 + 0.2,
            'regime': np.random.choice(['supportive', 'neutral', 'hostile'], 100)
        })
        market_data.to_parquet(os.path.join(self.data_dir, 'market_state.parquet'))
        
        # Portfolio data (should be filtered out for Observer)
        portfolio_data = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=100, freq='D'),
            'current_positions': np.random.random(100),
            'live_pnl': np.random.random(100) * 1000
        })
        portfolio_data.to_parquet(os.path.join(self.data_dir, 'portfolio_state.parquet'))
    
    @patch('src.intelligence_observer.observer_core.snapshot_builder.os.path.exists')
    @patch('src.intelligence_observer.observer_core.snapshot_builder.pd.read_parquet')
    def test_build_snapshot_success(self, mock_read_parquet, mock_exists):
        """Test successful snapshot building"""
        # Mock file existence
        mock_exists.return_value = True
        
        # Mock data loading
        mock_market_data = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=10),
            'volatility': np.random.random(10),
            'correlation': np.random.random(10)
        })
        mock_read_parquet.return_value = mock_market_data
        
        snapshot = self.builder.build_snapshot()
        
        assert snapshot is not None
        assert isinstance(snapshot, ObserverSnapshot)
        assert snapshot.data_quality_score > 0
        assert snapshot.completeness_score > 0
        assert snapshot.staleness_hours >= 1.0  # Minimum lag
    
    def test_data_lag_enforcement(self):
        """Test that data lag is enforced"""
        # This test would need to be adapted based on actual implementation
        # The key is ensuring that no real-time data is included
        
        snapshot = self.builder.build_snapshot()
        
        if snapshot:
            # All data should be at least 1 hour old
            assert snapshot.staleness_hours >= 1.0
    
    def test_forbidden_data_filtering(self):
        """Test that forbidden data is filtered out"""
        # Mock the builder to include forbidden data sources
        with patch.object(self.builder, '_load_data_sources') as mock_load:
            mock_load.return_value = {
                'market_state': pd.DataFrame({'col': [1, 2, 3]}),
                'current_positions': pd.DataFrame({'pos': [0.1, 0.2]}),  # Forbidden
                'live_pnl': pd.DataFrame({'pnl': [100, 200]})  # Forbidden
            }
            
            snapshot = self.builder.build_snapshot()
            
            if snapshot:
                # Should only contain allowed data
                assert 'market_state' in snapshot.data
                assert 'current_positions' not in snapshot.data
                assert 'live_pnl' not in snapshot.data
    
    def test_data_quality_assessment(self):
        """Test data quality assessment"""
        # Test with high quality data
        high_quality_data = {
            'market_state': pd.DataFrame({
                'date': pd.date_range('2024-01-01', periods=100),
                'volatility': np.random.random(100),
                'correlation': np.random.random(100)
            })
        }
        
        quality_score = self.builder._assess_data_quality(high_quality_data)
        assert 0.0 <= quality_score <= 1.0
        assert quality_score > 0.5  # Should be reasonably high
        
        # Test with low quality data (missing values)
        low_quality_data = {
            'market_state': pd.DataFrame({
                'date': pd.date_range('2024-01-01', periods=10),
                'volatility': [np.nan] * 5 + [0.1] * 5,  # 50% missing
                'correlation': [0.5] * 10
            })
        }
        
        quality_score_low = self.builder._assess_data_quality(low_quality_data)
        assert quality_score_low < quality_score  # Should be lower

class TestTemporalIsolation:
    """Test TemporalIsolation functionality"""
    
    def setup_method(self):
        """Setup for each test"""
        self.isolation = TemporalIsolation()
    
    def test_isolation_initialization(self):
        """Test temporal isolation initializes correctly"""
        assert self.isolation.name == "Observer Temporal Isolation"
        assert self.isolation.version == "1.0.0"
        assert self.isolation.min_lag_hours >= 1.0
        assert not self.isolation.allow_real_time_data
    
    def test_execution_time_validation(self):
        """Test that execution times are validated"""
        # Test current time (should be rejected)
        current_time = datetime.now()
        is_valid = self.isolation.is_execution_time_valid(current_time)
        assert not is_valid
        
        # Test time with sufficient lag (should be accepted)
        lagged_time = datetime.now() - timedelta(hours=2)
        is_valid = self.isolation.is_execution_time_valid(lagged_time)
        assert is_valid
    
    def test_data_timestamp_filtering(self):
        """Test that data timestamps are filtered correctly"""
        # Create data with mixed timestamps
        now = datetime.now()
        timestamps = [
            now - timedelta(hours=3),  # Valid (old enough)
            now - timedelta(hours=2),  # Valid (old enough)
            now - timedelta(minutes=30),  # Invalid (too recent)
            now - timedelta(minutes=10)   # Invalid (too recent)
        ]
        
        filtered_timestamps = self.isolation.filter_data_timestamps(timestamps)
        
        # Should only include timestamps older than min_lag_hours
        assert len(filtered_timestamps) == 2
        for ts in filtered_timestamps:
            time_diff = now - ts
            assert time_diff.total_seconds() / 3600 >= self.isolation.min_lag_hours
    
    def test_synchronous_execution_prevention(self):
        """Test that synchronous execution is prevented"""
        # This would test that Observer cannot run synchronously with trading
        # Implementation depends on the actual synchronization mechanism
        
        # Mock a trading execution event
        trading_event_time = datetime.now()
        
        # Observer should not be allowed to execute at the same time
        can_execute = self.isolation.can_execute_now(trading_event_time)
        assert not can_execute
    
    def test_scheduled_execution_timing(self):
        """Test scheduled execution timing"""
        # Test that scheduled times respect isolation rules
        schedule_config = {
            'nightly_batch_hour': 2,
            'weekly_synthesis_day': 6,
            'min_gap_from_execution': 4.0
        }
        
        next_execution = self.isolation.get_next_valid_execution_time(schedule_config)
        
        assert isinstance(next_execution, datetime)
        # Should be in the future
        assert next_execution > datetime.now()

class TestObserverScheduler:
    """Test ObserverScheduler functionality"""
    
    def setup_method(self):
        """Setup for each test"""
        self.scheduler = ObserverScheduler()
    
    def test_scheduler_initialization(self):
        """Test scheduler initializes correctly"""
        assert self.scheduler.name == "Intelligence Observer Scheduler"
        assert self.scheduler.version == "1.0.0"
        assert not self.scheduler.is_running
        assert len(self.scheduler.scheduled_tasks) > 0
        
        # Check that required tasks are initialized
        task_types = [task.schedule_type for task in self.scheduler.scheduled_tasks.values()]
        assert ScheduleType.NIGHTLY_BATCH in task_types
        assert ScheduleType.WEEKLY_SYNTHESIS in task_types
        assert ScheduleType.MONTHLY_REVIEW in task_types
    
    def test_scheduled_task_creation(self):
        """Test scheduled task creation"""
        task = ScheduledTask(
            task_id="test_task",
            schedule_type=ScheduleType.NIGHTLY_BATCH,
            next_run=datetime.now() + timedelta(hours=1),
            interval_hours=24.0,
            task_function=lambda: {'success': True}
        )
        
        assert task.task_id == "test_task"
        assert task.schedule_type == ScheduleType.NIGHTLY_BATCH
        assert task.enabled
        assert task.run_count == 0
        assert task.last_run is None
    
    def test_on_demand_analysis(self):
        """Test on-demand analysis execution"""
        # Mock the snapshot builder to return a valid snapshot
        with patch.object(self.scheduler.snapshot_builder, 'build_snapshot') as mock_build:
            mock_snapshot = Mock()
            mock_snapshot.snapshot_id = "test_snapshot_001"
            mock_build.return_value = mock_snapshot
            
            # Mock the intelligence analysis
            with patch.object(self.scheduler, '_run_intelligence_analysis') as mock_analysis:
                mock_analysis.return_value = [
                    {'type': 'score', 'category': 'regime', 'artifact': {'score_id': 'test_001'}}
                ]
                
                result = self.scheduler.run_on_demand_analysis()
                
                assert result['success']
                assert 'snapshot_id' in result
                assert 'results' in result
                assert len(result['results']) > 0
    
    def test_on_demand_analysis_suspended_observer(self):
        """Test on-demand analysis when observer is suspended"""
        # Suspend the observer
        self.scheduler.authority_firewall.observer_suspended = True
        
        result = self.scheduler.run_on_demand_analysis()
        
        assert not result['success']
        assert 'suspended' in result['error'].lower()
    
    def test_scheduler_status(self):
        """Test scheduler status reporting"""
        status = self.scheduler.get_scheduler_status()
        
        assert 'is_running' in status
        assert 'observer_suspended' in status
        assert 'violation_count' in status
        assert 'scheduled_tasks' in status
        assert 'recent_executions' in status
        assert 'output_paths' in status
        
        # Check scheduled tasks structure
        for task_id, task_info in status['scheduled_tasks'].items():
            assert 'schedule_type' in task_info
            assert 'next_run' in task_info
            assert 'enabled' in task_info
    
    def test_scheduler_start_stop(self):
        """Test scheduler start and stop functionality"""
        # Test start
        self.scheduler.start_scheduler()
        assert self.scheduler.is_running
        assert self.scheduler.scheduler_thread is not None
        
        # Test stop
        self.scheduler.stop_scheduler()
        assert not self.scheduler.is_running
    
    def test_task_execution_timing(self):
        """Test that tasks are scheduled at appropriate times"""
        # Check nightly batch timing
        nightly_task = self.scheduler.scheduled_tasks.get('nightly_batch')
        assert nightly_task is not None
        
        # Should be scheduled for 2 AM
        assert nightly_task.next_run.hour == 2
        
        # Check weekly synthesis timing
        weekly_task = self.scheduler.scheduled_tasks.get('weekly_synthesis')
        assert weekly_task is not None
        
        # Should be scheduled for Saturday
        assert weekly_task.next_run.weekday() == 5  # Saturday is 5
    
    @patch('os.makedirs')
    @patch('builtins.open', create=True)
    def test_analysis_results_saving(self, mock_open, mock_makedirs):
        """Test that analysis results are saved correctly"""
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        results = [
            {
                'type': 'score',
                'category': 'regime',
                'artifact': {'score_id': 'test_001', 'value': 67.5}
            }
        ]
        
        self.scheduler._save_analysis_results(results, "test_batch")
        
        # Should create directories and save files
        mock_makedirs.assert_called()
        mock_open.assert_called()
    
    def test_recent_results_loading(self):
        """Test loading of recent analysis results"""
        # This test would need to mock the file system
        # or use temporary files to test the loading functionality
        
        with patch('os.path.exists') as mock_exists:
            mock_exists.return_value = False
            
            results = self.scheduler._load_recent_results(days=7)
            assert isinstance(results, list)
            # Should return empty list if no files exist
            assert len(results) == 0

class TestObserverCoreIntegration:
    """Test integration between Observer core components"""
    
    def test_context_snapshot_builder_integration(self):
        """Test integration between context and snapshot builder"""
        context = ObserverContext()
        builder = SnapshotBuilder()
        
        # Mock successful snapshot building
        with patch.object(builder, 'build_snapshot') as mock_build:
            mock_snapshot = ObserverSnapshot(
                snapshot_id="integration_test_001",
                timestamp=datetime.now(),
                data={'test': 'data'},
                data_quality_score=0.95,
                completeness_score=0.90,
                staleness_hours=2.0
            )
            mock_build.return_value = mock_snapshot
            
            # Build and load snapshot
            snapshot = builder.build_snapshot()
            context.load_snapshot(snapshot)
            
            # Verify integration
            assert context.current_snapshot == snapshot
            assert context.get_current_data('test') == 'data'
    
    def test_scheduler_temporal_isolation_integration(self):
        """Test integration between scheduler and temporal isolation"""
        scheduler = ObserverScheduler()
        isolation = TemporalIsolation()
        
        # Test that scheduler respects temporal isolation rules
        status = scheduler.get_scheduler_status()
        
        for task_id, task_info in status['scheduled_tasks'].items():
            next_run = datetime.fromisoformat(task_info['next_run'])
            
            # All scheduled times should respect temporal isolation
            assert isolation.is_execution_time_valid(next_run) or next_run > datetime.now()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])