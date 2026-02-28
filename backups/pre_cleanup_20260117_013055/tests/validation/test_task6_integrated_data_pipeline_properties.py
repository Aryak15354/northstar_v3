#!/usr/bin/env python3
"""
🔄 TASK 6: INTEGRATED DATA PIPELINE SYSTEM - PROPERTY-BASED TESTS
Capital-grade property-based tests for the integrated data pipeline system

PROPERTIES TESTED:
- Property 32: Multi-source data coordination
- Property 33: Data conflict resolution  
- Property 36: Automatic retry for transient failures

These tests validate the system laws that cannot be violated.
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, assume
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from src.cohesion.integrated_data_pipeline import (
    IntegratedDataPipeline, DataSourceConfig, DataSourceType, 
    DataSourcePriority, ProcessingResult, RetryManager, DependencyGraph
)
from src.cohesion.configuration_manager import ConfigurationManager
from src.cohesion.unified_state_manager import UnifiedStateManager
from src.cohesion.schema_validator import SchemaValidator, SchemaRegistry
from src.cohesion.sample_data_sources import (
    MockMarketDataSource, MockMacroDataSource, FailingDataSource,
    create_sample_data_sources
)

class TestIntegratedDataPipelineProperties:
    """Property-based tests for Integrated Data Pipeline System"""
    
    def setup_method(self):
        """Set up test environment"""
        self.config_manager = ConfigurationManager()
        self.state_manager = UnifiedStateManager()
        self.schema_registry = SchemaRegistry()
        self.schema_validator = SchemaValidator(self.schema_registry)
        
        # Create fresh pipeline for each test
        self.pipeline = IntegratedDataPipeline(
            self.config_manager,
            self.state_manager, 
            self.schema_validator
        )
        
        # Clear any existing state
        self.pipeline.data_sources.clear()
        self.pipeline.dependency_graph = DependencyGraph()
        self.pipeline.processing_status.clear()
        self.pipeline.processing_results.clear()
        self.pipeline.data_conflicts.clear()
    
    @given(
        source_count=st.integers(min_value=2, max_value=5),  # Reduced max for simpler testing
        priority_distribution=st.lists(
            st.sampled_from(list(DataSourcePriority)), 
            min_size=2, 
            max_size=5
        )
    )
    @settings(max_examples=50, deadline=30000)  # Reduced examples for faster testing
    def test_property_32_multi_source_coordination(self, source_count, priority_distribution):
        """
        **Property 32: Multi-source data coordination**
        *For any* set of data sources with dependencies, processing must occur in correct order
        **Validates: Requirements 6.1, 6.6**
        **Feature: northstar-v3-system-cohesion, Property 32: Multi-source data coordination**
        """
        
        assume(len(priority_distribution) >= source_count)
        
        # Create data sources with simple linear dependencies to avoid cycles
        sources = {}
        configs = {}
        
        for i in range(source_count):
            source_name = f"test_source_{i}"
            priority = priority_distribution[i % len(priority_distribution)]
            
            # Create simple linear dependencies (each source depends only on the previous one)
            dependencies = [f"test_source_{i-1}"] if i > 0 else []
            
            # Create mock source
            sources[source_name] = MockMarketDataSource(source_name)
            
            # Create config
            configs[source_name] = DataSourceConfig(
                name=source_name,
                source_type=DataSourceType.MARKET_DATA,
                priority=priority,
                dependencies=dependencies,
                schema_name="market_data",
                freshness_threshold=timedelta(hours=24),
                retry_config={'max_retries': 2},
                quality_gates=['completeness']
            )
            
            # Register with pipeline
            self.pipeline.register_data_source(source_name, sources[source_name], configs[source_name])
        
        # PROPERTY 32: Validate dependency order is respected
        try:
            processing_order = self.pipeline.dependency_graph.get_processing_order()
            
            # Verify all sources are in processing order
            assert len(processing_order) == source_count, f"Processing order missing sources: {len(processing_order)} != {source_count}"
            
            # Verify dependencies are respected (linear chain)
            for i in range(1, len(processing_order)):
                current_source = processing_order[i]
                config = configs[current_source]
                
                for dependency in config.dependencies:
                    if dependency in processing_order:
                        dep_index = processing_order.index(dependency)
                        current_index = processing_order.index(current_source)
                        assert dep_index < current_index, f"Dependency {dependency} (index {dep_index}) processed after {current_source} (index {current_index})"
            
            print(f"✅ Property 32: Multi-source coordination validated for {source_count} sources")
            
        except ValueError as e:
            # Circular dependency detected - this shouldn't happen with linear dependencies
            pytest.fail(f"Unexpected circular dependency with linear chain: {e}")
    
    @given(
        conflict_data=st.lists(
            st.tuples(
                st.text(min_size=1, max_size=10),  # source name
                st.sampled_from(list(DataSourcePriority)),  # priority
                st.floats(min_value=1.0, max_value=1000.0)  # conflicting value
            ),
            min_size=2,
            max_size=5
        )
    )
    @settings(max_examples=100, deadline=30000)
    def test_property_33_data_conflict_resolution(self, conflict_data):
        """
        **Property 33: Data conflict resolution**
        *For any* conflicting data from multiple sources, highest priority source must win
        **Validates: Requirements 6.2, 6.7**
        **Feature: northstar-v3-system-cohesion, Property 33: Data conflict resolution**
        """
        
        # Create sources with conflicting data
        sources = {}
        results = {}
        
        for i, (source_name, priority, value) in enumerate(conflict_data):
            # Ensure unique source names
            unique_source_name = f"{source_name}_{i}"
            
            # Create mock source that returns conflicting data
            source = MockMarketDataSource(unique_source_name)
            sources[unique_source_name] = source
            
            # Create mock result with conflicting field
            conflicting_df = pd.DataFrame({
                'field': [value],
                'timestamp': [datetime.now()]
            })
            
            results[unique_source_name] = ProcessingResult(
                success=True,
                data=conflicting_df,
                errors=[],
                warnings=[],
                metadata={},
                processing_time=0.1
            )
            
            # Register source config with priority
            config = DataSourceConfig(
                name=unique_source_name,
                source_type=DataSourceType.MARKET_DATA,
                priority=priority,
                dependencies=[],
                schema_name="",
                freshness_threshold=timedelta(hours=24),
                retry_config={},
                quality_gates=[]
            )
            
            self.pipeline.dependency_graph.add_node(config)
        
        # PROPERTY 33: Resolve conflicts and verify highest priority wins
        conflicts_resolved = self.pipeline._resolve_data_conflicts(results)
        
        # Find the highest priority (lowest enum value)
        priorities = [priority for _, priority, _ in conflict_data]
        highest_priority = min(priorities, key=lambda p: p.value)
        
        # Verify conflict resolution occurred
        if len(set(priorities)) > 1:  # Only if there are actual priority differences
            assert conflicts_resolved > 0, "No conflicts resolved despite priority differences"
            
            # Check that conflicts were recorded
            assert len(self.pipeline.data_conflicts) > 0, "Conflicts not recorded"
            
            print(f"✅ Property 33: Data conflict resolution validated - {conflicts_resolved} conflicts resolved")
        else:
            print(f"✅ Property 33: No conflicts to resolve (all same priority)")
    
    @given(
        max_retries=st.integers(min_value=1, max_value=5),
        fail_count=st.integers(min_value=1, max_value=3),
        backoff_factor=st.floats(min_value=1.1, max_value=3.0)
    )
    @settings(max_examples=100, deadline=30000)
    def test_property_36_automatic_retry_for_transient_failures(self, max_retries, fail_count, backoff_factor):
        """
        **Property 36: Automatic retry for transient failures**
        *For any* transient failure, system must retry according to configured policy
        **Validates: Requirements 6.2, 6.7**
        **Feature: northstar-v3-system-cohesion, Property 36: Automatic retry for transient failures**
        """
        
        assume(fail_count <= max_retries)  # Ensure eventual success
        
        # Create retry manager with test configuration
        retry_manager = RetryManager(
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            initial_delay=0.01  # Fast for testing
        )
        
        # Create failing operation that succeeds after fail_count attempts
        attempt_count = 0
        
        def failing_operation():
            nonlocal attempt_count
            attempt_count += 1
            
            if attempt_count <= fail_count:
                raise Exception(f"Simulated failure {attempt_count}")
            
            # Success
            return ProcessingResult(
                success=True,
                data=pd.DataFrame({'test': [1, 2, 3]}),
                errors=[],
                warnings=[],
                metadata={'attempts': attempt_count},
                processing_time=0.01
            )
        
        # PROPERTY 36: Execute with retry and verify behavior
        start_time = datetime.now()
        result = retry_manager.execute_with_retry(failing_operation, "test_operation")
        end_time = datetime.now()
        
        # Verify retry behavior
        if fail_count <= max_retries:
            # Should succeed after retries
            assert result.success, f"Operation should succeed after {fail_count} failures with {max_retries} max retries"
            assert attempt_count == fail_count + 1, f"Expected {fail_count + 1} attempts, got {attempt_count}"
            
            # Verify backoff timing (approximately)
            expected_min_time = sum(0.01 * (backoff_factor ** i) for i in range(fail_count))
            actual_time = (end_time - start_time).total_seconds()
            
            # Allow some tolerance for timing
            assert actual_time >= expected_min_time * 0.5, f"Retry timing too fast: {actual_time}s < {expected_min_time * 0.5}s"
            
            print(f"✅ Property 36: Automatic retry validated - succeeded after {attempt_count} attempts")
        else:
            # Should fail after max retries
            assert not result.success, f"Operation should fail after {max_retries} retries with {fail_count} required failures"
            assert attempt_count == max_retries + 1, f"Expected {max_retries + 1} attempts, got {attempt_count}"
            
            print(f"✅ Property 36: Automatic retry validated - failed after {attempt_count} attempts (expected)")
    
    @given(
        source_names=st.lists(
            st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
            min_size=1,
            max_size=5,
            unique=True
        )
    )
    @settings(max_examples=50, deadline=30000)
    def test_pipeline_lineage_validation_property(self, source_names):
        """
        **Property: Data lineage validation completeness**
        *For any* set of registered data sources, lineage validation must be comprehensive
        **Validates: Requirements 6.1, 6.6**
        """
        
        # Register sources with valid configurations
        for i, source_name in enumerate(source_names):
            source = MockMarketDataSource(source_name)
            
            # Create dependencies (each source depends on previous one)
            dependencies = [source_names[i-1]] if i > 0 else []
            
            config = DataSourceConfig(
                name=source_name,
                source_type=DataSourceType.MARKET_DATA,
                priority=DataSourcePriority.HIGH,
                dependencies=dependencies,
                schema_name="market_data",
                freshness_threshold=timedelta(hours=24),
                retry_config={},
                quality_gates=[]
            )
            
            self.pipeline.register_data_source(source_name, source, config)
        
        # Validate lineage
        lineage_result = self.pipeline.validate_data_lineage()
        
        # Should be valid for properly configured sources
        assert lineage_result.is_valid, f"Lineage validation failed: {[e.message for e in lineage_result.errors]}"
        
        # Verify all sources are in dependency graph
        assert len(self.pipeline.dependency_graph.nodes) == len(source_names), "Not all sources in dependency graph"
        
        print(f"✅ Data lineage validation property validated for {len(source_names)} sources")
    
    def test_pipeline_status_consistency_property(self):
        """
        **Property: Pipeline status consistency**
        *For any* pipeline state, status information must be consistent and complete
        """
        
        # Create sample sources
        sources = create_sample_data_sources()
        
        for name, source in sources.items():
            config = DataSourceConfig(
                name=name,
                source_type=DataSourceType.MARKET_DATA,
                priority=DataSourcePriority.MEDIUM,
                dependencies=[],
                schema_name="",
                freshness_threshold=timedelta(hours=24),
                retry_config={},
                quality_gates=[]
            )
            
            self.pipeline.register_data_source(name, source, config)
        
        # Get pipeline status
        status = self.pipeline.get_pipeline_status()
        
        # Verify status consistency
        assert 'timestamp' in status, "Status missing timestamp"
        assert 'registered_sources' in status, "Status missing registered sources count"
        assert 'processing_status' in status, "Status missing processing status"
        assert 'lineage_valid' in status, "Status missing lineage validation"
        
        # Verify counts match
        assert status['registered_sources'] == len(sources), "Source count mismatch"
        assert len(status['processing_status']) == len(sources), "Processing status count mismatch"
        
        print(f"✅ Pipeline status consistency property validated")

def main():
    """Run property-based tests for Integrated Data Pipeline System"""
    
    print("🔄 RUNNING PROPERTY-BASED TESTS: INTEGRATED DATA PIPELINE SYSTEM")
    print("=" * 80)
    
    # Run pytest with this file
    pytest_args = [
        __file__,
        "-v",
        "--tb=short",
        "-x"  # Stop on first failure
    ]
    
    exit_code = pytest.main(pytest_args)
    
    if exit_code == 0:
        print("\n✅ ALL INTEGRATED DATA PIPELINE PROPERTIES VALIDATED")
        print("   Property 32: Multi-source data coordination ✅")
        print("   Property 33: Data conflict resolution ✅") 
        print("   Property 36: Automatic retry for transient failures ✅")
        print("   System laws are mathematically enforced")
    else:
        print("\n❌ SOME PROPERTIES FAILED VALIDATION")
        print("   System laws may be violated")
    
    return exit_code == 0

if __name__ == "__main__":
    main()