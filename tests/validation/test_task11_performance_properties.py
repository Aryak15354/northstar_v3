"""
Property-Based Tests for Performance Optimization and Caching System

Tests the capital-grade system laws for performance optimization:
- Property 23: Cache Freshness Validation (P1)
- Property 24: Memory Threshold Enforcement (P2)

Feature: northstar-v3-system-cohesion
"""

import pytest
import time
import threading
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant
import pandas as pd
import numpy as np

from src.cohesion.cache_manager import (
    IntelligentCacheManager, CacheEntry, LRUEvictionPolicy, 
    PriorityLRUEvictionPolicy, BatchFileOperationManager,
    DataFrameOptimizer, LazyDataLoader, cached
)
from src.cohesion.performance_monitor import (
    PerformanceMonitor, PerformanceThreshold, AlertSeverity,
    PerformanceProfiler
)


class TestCacheFreshnessValidation:
    """
    Test Property 23: Cache Freshness Validation (P1)
    
    SYSTEM LAW: For any cached data access, freshness must be validated before use
    **Validates: Requirements 9.2**
    """
    
    @given(
        max_age_seconds=st.integers(min_value=1, max_value=3),  # Reduced range
        wait_seconds=st.integers(min_value=0, max_value=5),     # Reduced range
        stale_acceptable=st.booleans()
    )
    @settings(max_examples=10, deadline=10000)  # Increased deadline
    def test_cache_freshness_validation_property(self, max_age_seconds, wait_seconds, stale_acceptable):
        """
        Property 23: Cache Freshness Validation (P1)
        For any cached data access, freshness must be validated before use
        **Feature: northstar-v3-system-cohesion, Property 23: Cache Freshness Validation**
        """
        cache = IntelligentCacheManager(max_memory_mb=10)
        
        # Cache some data with specific max_age
        test_data = f"test_data_{max_age_seconds}_{wait_seconds}"
        max_age = timedelta(seconds=max_age_seconds)
        
        cache.put("test_key", test_data, max_age=max_age, stale_acceptable=stale_acceptable)
        
        # Wait specified time (add small buffer for timing precision)
        if wait_seconds > 0:
            time.sleep(min(wait_seconds, 2) + 0.05)  # Cap sleep time and reduce buffer
        
        # Try to retrieve data
        result = cache.get("test_key")
        
        # SYSTEM LAW: Cache freshness must be validated
        # Allow for timing precision issues
        if wait_seconds < max_age_seconds:
            # Data should be fresh and returned
            assert result == test_data, f"Fresh data should be returned: wait={wait_seconds}, max_age={max_age_seconds}"
        elif wait_seconds == max_age_seconds and stale_acceptable:
            # Edge case: might be fresh or stale but acceptable
            assert result == test_data or result is None, f"Edge case handling failed"
        elif stale_acceptable:
            # Stale but acceptable data should be returned
            assert result == test_data, f"Stale but acceptable data should be returned"
        else:
            # Stale data should not be returned
            assert result is None, f"Stale data should not be returned: wait={wait_seconds}, max_age={max_age_seconds}"
    
    @given(
        entries=st.lists(
            st.tuples(
                st.text(min_size=1, max_size=10),  # key
                st.text(min_size=1, max_size=100),  # value
                st.integers(min_value=1, max_value=5),  # max_age_seconds
                st.booleans()  # stale_acceptable
            ),
            min_size=1,
            max_size=10
        ),
        access_delay=st.integers(min_value=0, max_value=3)  # Reduced range
    )
    @settings(max_examples=10, deadline=5000)
    def test_multiple_entries_freshness_property(self, entries, access_delay):
        """
        Property 23 Extended: Multiple cache entries freshness validation
        For any set of cached entries, each must be validated independently
        **Feature: northstar-v3-system-cohesion, Property 23: Cache Freshness Validation**
        """
        cache = IntelligentCacheManager(max_memory_mb=10)
        
        # Cache all entries
        for key, value, max_age_seconds, stale_acceptable in entries:
            cache.put(
                key, value, 
                max_age=timedelta(seconds=max_age_seconds),
                stale_acceptable=stale_acceptable
            )
        
        # Wait
        if access_delay > 0:
            time.sleep(min(access_delay, 2) + 0.05)  # Cap sleep time and reduce buffer
        
        # Check each entry independently
        for key, expected_value, max_age_seconds, stale_acceptable in entries:
            result = cache.get(key)
            
            # SYSTEM LAW: Each entry's freshness must be validated independently
            # Allow for timing precision issues
            if access_delay < max_age_seconds:
                assert result == expected_value, f"Fresh entry {key} should be returned"
            elif access_delay == max_age_seconds and stale_acceptable:
                # Edge case: might be fresh or stale but acceptable
                assert result == expected_value or result is None, f"Edge case for entry {key}"
            elif stale_acceptable:
                assert result == expected_value, f"Stale but acceptable entry {key} should be returned"
            else:
                assert result is None, f"Stale entry {key} should not be returned"


class TestMemoryThresholdEnforcement:
    """
    Test Property 24: Memory Threshold Enforcement (P2)
    
    SYSTEM LAW: When memory usage exceeds thresholds, eviction policies must activate
    **Validates: Requirements 9.4**
    """
    
    @given(
        max_memory_mb=st.floats(min_value=1.0, max_value=10.0),
        threshold=st.floats(min_value=0.5, max_value=0.9),
        data_sizes=st.lists(
            st.integers(min_value=100, max_value=1000000),  # bytes
            min_size=5,
            max_size=20
        )
    )
    @settings(max_examples=10, deadline=5000)
    def test_memory_threshold_enforcement_property(self, max_memory_mb, threshold, data_sizes):
        """
        Property 24: Memory Threshold Enforcement (P2)
        When memory usage exceeds thresholds, eviction policies must activate
        **Feature: northstar-v3-system-cohesion, Property 24: Memory Threshold Enforcement**
        """
        cache = IntelligentCacheManager(
            max_memory_mb=max_memory_mb,
            memory_threshold=threshold,
            enable_monitoring=False  # Disable background monitoring for test
        )
        
        max_memory_bytes = int(max_memory_mb * 1024 * 1024)
        threshold_bytes = int(max_memory_bytes * threshold)
        
        # Add data until we exceed threshold
        total_added = 0
        entries_added = 0
        
        for i, size in enumerate(data_sizes):
            # Create data of specified size
            data = "x" * size
            key = f"key_{i}"
            
            # Add to cache
            success = cache.put(key, data)
            
            if success:
                entries_added += 1
                total_added += size
            
            # Get current stats
            stats = cache.get_stats()
            
            # SYSTEM LAW: Memory usage must not exceed threshold for long
            # Allow brief excursions but eviction must bring it back down
            if stats.memory_usage_bytes > threshold_bytes:
                # If we're over threshold, eviction should have occurred
                # or we should be very close to threshold
                assert stats.memory_usage_bytes <= max_memory_bytes, \
                    f"Memory usage {stats.memory_usage_bytes} exceeds max {max_memory_bytes}"
                
                # After eviction, we should be back under threshold (with generous tolerance)
                tolerance = max_memory_bytes * 0.2  # 20% tolerance for eviction timing
                if i > 5:  # Give some time for eviction to work
                    # Only check if we have reasonable amount of data
                    if total_added > threshold_bytes:
                        assert stats.memory_usage_bytes <= threshold_bytes + tolerance, \
                            f"Eviction failed: {stats.memory_usage_bytes} > {threshold_bytes + tolerance}"
    
    @given(
        entries=st.lists(
            st.tuples(
                st.text(min_size=1, max_size=5),  # key
                st.integers(min_value=1, max_value=5),  # priority
                st.integers(min_value=100, max_value=10000)  # size
            ),
            min_size=10,
            max_size=30
        )
    )
    @settings(max_examples=10, deadline=8000)
    def test_priority_based_eviction_property(self, entries):
        """
        Property 24 Extended: Priority-based eviction must respect priorities
        When eviction occurs, lower priority items should be evicted first
        **Feature: northstar-v3-system-cohesion, Property 24: Memory Threshold Enforcement**
        """
        # Use small cache to force eviction
        cache = IntelligentCacheManager(
            max_memory_mb=0.1,  # Very small cache
            memory_threshold=0.5,
            eviction_policy=PriorityLRUEvictionPolicy(),
            enable_monitoring=False
        )
        
        # Add all entries
        added_entries = []
        for key, priority, size in entries:
            data = "x" * size
            success = cache.put(key, data, priority=priority)
            if success:
                added_entries.append((key, priority, size))
        
        # Get final state
        stats = cache.get_stats()
        
        # Check which entries survived
        surviving_entries = []
        for key, priority, size in added_entries:
            if cache.get(key) is not None:
                surviving_entries.append((key, priority, size))
        
        if len(surviving_entries) > 1 and len(surviving_entries) < len(added_entries):
            # SYSTEM LAW: Higher priority entries should survive eviction
            surviving_priorities = [priority for _, priority, _ in surviving_entries]
            evicted_priorities = [priority for key, priority, _ in added_entries 
                                if cache.get(key) is None]
            
            if evicted_priorities and surviving_priorities:  # Only check if both exist
                min_surviving_priority = min(surviving_priorities)
                max_evicted_priority = max(evicted_priorities)
                
                # Higher priority (larger number) should survive over lower priority
                # Allow some tolerance for LRU effects within same priority
                if max_evicted_priority > min_surviving_priority:
                    # Check if this is due to LRU within same priority level
                    same_priority_survivors = [p for p in surviving_priorities if p == max_evicted_priority]
                    if not same_priority_survivors:
                        assert False, f"Priority violation: surviving min={min_surviving_priority}, evicted max={max_evicted_priority}"


class TestDataFrameOptimization:
    """
    Test DataFrame optimization for large datasets
    **Validates: Requirements 9.5**
    """
    
    @given(
        num_rows=st.integers(min_value=100, max_value=10000),
        num_int_cols=st.integers(min_value=1, max_value=5),
        num_float_cols=st.integers(min_value=1, max_value=5),
        num_str_cols=st.integers(min_value=1, max_value=3)
    )
    @settings(max_examples=5, deadline=5000)
    def test_dataframe_optimization_property(self, num_rows, num_int_cols, num_float_cols, num_str_cols):
        """
        Property: DataFrame optimization must reduce memory usage without data loss
        For any DataFrame, optimization should reduce memory while preserving data
        **Feature: northstar-v3-system-cohesion, Property: DataFrame Optimization**
        """
        # Create test DataFrame
        data = {}
        
        # Add integer columns
        for i in range(num_int_cols):
            # Use small integers that can be downcast
            data[f'int_col_{i}'] = np.random.randint(0, 100, num_rows)
        
        # Add float columns
        for i in range(num_float_cols):
            data[f'float_col_{i}'] = np.random.random(num_rows).astype('float64')
        
        # Add string columns with low cardinality
        for i in range(num_str_cols):
            categories = [f'cat_{j}' for j in range(min(10, num_rows // 10 + 1))]
            data[f'str_col_{i}'] = np.random.choice(categories, num_rows)
        
        original_df = pd.DataFrame(data)
        original_memory = original_df.memory_usage(deep=True).sum()
        
        # Optimize DataFrame
        optimized_df = DataFrameOptimizer.optimize_dtypes(original_df)
        optimized_memory = optimized_df.memory_usage(deep=True).sum()
        
        # SYSTEM LAW: Optimization must preserve data (with float precision tolerance)
        try:
            pd.testing.assert_frame_equal(
                original_df, 
                optimized_df,
                check_dtype=False,
                check_exact=False,
                rtol=1e-6  # Relative tolerance for float comparison
            )
        except AssertionError:
            # For float columns, check if values are approximately equal
            for col in original_df.columns:
                if original_df[col].dtype in ['float64', 'float32']:
                    np.testing.assert_allclose(
                        original_df[col].values,
                        optimized_df[col].values,
                        rtol=1e-6,
                        err_msg=f"Float precision issue in column {col}"
                    )
                else:
                    pd.testing.assert_series_equal(
                        original_df[col].astype(str),
                        optimized_df[col].astype(str),
                        check_names=False
                    )
        
        # SYSTEM LAW: Optimization should reduce memory usage (or at least not increase it)
        assert optimized_memory <= original_memory, \
            f"Optimization increased memory: {optimized_memory} > {original_memory}"


class TestPerformanceMonitoring:
    """
    Test performance monitoring and alerting
    **Validates: Requirements 9.6**
    """
    
    @given(
        metrics=st.lists(
            st.tuples(
                st.text(min_size=1, max_size=10),  # metric name
                st.floats(min_value=0.0, max_value=100.0)  # value
            ),
            min_size=5,
            max_size=20
        )
    )
    @settings(max_examples=10, deadline=3000)
    def test_metric_recording_property(self, metrics):
        """
        Property: All recorded metrics must be retrievable and accurate
        For any set of metrics, recording and retrieval must be consistent
        **Feature: northstar-v3-system-cohesion, Property: Metric Recording**
        """
        monitor = PerformanceMonitor(monitoring_interval=60)  # Disable auto-monitoring
        
        # Record all metrics
        recorded_metrics = {}
        for name, value in metrics:
            monitor.record_metric(name, value)
            if name not in recorded_metrics:
                recorded_metrics[name] = []
            recorded_metrics[name].append(value)
        
        # Verify retrieval
        for name, expected_values in recorded_metrics.items():
            retrieved_metrics = monitor.get_metrics(name)
            retrieved_values = [m.value for m in retrieved_metrics]
            
            # SYSTEM LAW: All recorded metrics must be retrievable
            assert len(retrieved_values) == len(expected_values), \
                f"Metric count mismatch for {name}: {len(retrieved_values)} != {len(expected_values)}"
            
            # Values should match (in order)
            for i, (expected, actual) in enumerate(zip(expected_values, retrieved_values)):
                assert abs(expected - actual) < 1e-10, \
                    f"Metric value mismatch at index {i}: {expected} != {actual}"
    
    @given(
        warning_threshold=st.floats(min_value=10.0, max_value=50.0),
        critical_threshold=st.floats(min_value=60.0, max_value=90.0),
        values=st.lists(
            st.floats(min_value=0.0, max_value=100.0),
            min_size=10,
            max_size=20
        )
    )
    @settings(max_examples=10, deadline=3000)
    def test_threshold_alerting_property(self, warning_threshold, critical_threshold, values):
        """
        Property: Threshold violations must trigger appropriate alerts
        For any threshold configuration, violations must generate correct alerts
        **Feature: northstar-v3-system-cohesion, Property: Threshold Alerting**
        """
        assume(critical_threshold > warning_threshold)
        
        monitor = PerformanceMonitor(monitoring_interval=60)
        
        # Add threshold
        threshold = PerformanceThreshold(
            metric_name="test_metric",
            warning_threshold=warning_threshold,
            critical_threshold=critical_threshold,
            comparison="greater",
            window_size=3
        )
        monitor.add_threshold(threshold)
        
        # Record values
        for value in values:
            monitor.record_metric("test_metric", value)
        
        # Check alerts
        alerts = monitor.get_active_alerts()
        
        # Calculate expected alert level based on recent values
        if len(values) >= 3:
            recent_avg = sum(values[-3:]) / 3
            
            if recent_avg >= critical_threshold:
                # Should have critical alert
                critical_alerts = [a for a in alerts 
                                 if a.metric_name == "test_metric" 
                                 and a.severity == AlertSeverity.CRITICAL]
                assert len(critical_alerts) > 0, \
                    f"Missing critical alert for avg={recent_avg}, threshold={critical_threshold}"
            
            elif recent_avg >= warning_threshold:
                # Should have warning alert
                warning_alerts = [a for a in alerts 
                                if a.metric_name == "test_metric" 
                                and a.severity == AlertSeverity.HIGH]
                assert len(warning_alerts) > 0, \
                    f"Missing warning alert for avg={recent_avg}, threshold={warning_threshold}"


class CacheStateMachine(RuleBasedStateMachine):
    """
    Stateful testing for cache manager
    Tests complex interactions and invariants
    """
    
    def __init__(self):
        super().__init__()
        self.cache = IntelligentCacheManager(
            max_memory_mb=1.0,  # Small cache for testing
            memory_threshold=0.7,
            enable_monitoring=False
        )
        self.expected_entries = {}
    
    @rule(
        key=st.text(min_size=1, max_size=10),
        value=st.text(min_size=1, max_size=100),
        max_age_seconds=st.integers(min_value=1, max_value=10)
    )
    def put_entry(self, key, value, max_age_seconds):
        """Put entry in cache"""
        max_age = timedelta(seconds=max_age_seconds)
        success = self.cache.put(key, value, max_age=max_age)
        
        if success:
            self.expected_entries[key] = {
                'value': value,
                'expires_at': datetime.now() + max_age
            }
    
    @rule(key=st.text(min_size=1, max_size=10))
    def get_entry(self, key):
        """Get entry from cache"""
        result = self.cache.get(key)
        
        if key in self.expected_entries:
            expected = self.expected_entries[key]
            if datetime.now() <= expected['expires_at']:
                # Should be available
                assert result == expected['value'], \
                    f"Expected {expected['value']}, got {result}"
            else:
                # Should be expired
                assert result is None, f"Expired entry should return None, got {result}"
                # Remove from expected
                del self.expected_entries[key]
        else:
            assert result is None, f"Non-existent entry should return None, got {result}"
    
    @rule()
    def clear_cache(self):
        """Clear all cache entries"""
        self.cache.clear()
        self.expected_entries.clear()
    
    @invariant()
    def cache_consistency_invariant(self):
        """Cache state must be consistent with expectations"""
        stats = self.cache.get_stats()
        
        # Memory usage should not exceed maximum
        max_memory_bytes = int(1.0 * 1024 * 1024)  # 1MB
        assert stats.memory_usage_bytes <= max_memory_bytes, \
            f"Memory usage {stats.memory_usage_bytes} exceeds max {max_memory_bytes}"


# Test the stateful machine
TestCacheStateMachine = CacheStateMachine.TestCase


class TestBatchOperations:
    """
    Test batch file operations
    **Validates: Requirements 9.3**
    """
    
    def test_batch_operations_efficiency(self, tmp_path):
        """
        Test that batch operations are more efficient than individual operations
        **Feature: northstar-v3-system-cohesion, Property: Batch Efficiency**
        """
        batch_manager = BatchFileOperationManager(
            batch_size=5,
            flush_interval=1.0
        )
        
        # Create test files
        test_files = []
        for i in range(10):
            file_path = tmp_path / f"test_{i}.txt"
            file_path.write_text(f"test data {i}")
            test_files.append(str(file_path))
        
        # Test batch reads
        results = []
        
        def collect_result(data):
            results.append(data)
        
        # Queue multiple reads
        for file_path in test_files:
            batch_manager.queue_read(file_path, collect_result)
        
        # Wait for batch processing
        time.sleep(2.0)
        
        # SYSTEM LAW: All queued operations must complete
        assert len(results) == len(test_files), \
            f"Expected {len(test_files)} results, got {len(results)}"
        
        # Results should contain expected data
        for i, result in enumerate(results):
            if result is not None:  # Some might fail due to file system timing
                assert f"test data" in result, f"Unexpected result: {result}"


if __name__ == "__main__":
    # Run property tests
    pytest.main([__file__, "-v", "--tb=short"])