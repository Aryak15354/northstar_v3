#!/usr/bin/env python3
"""
🔄 TASK 6: INTEGRATED DATA PIPELINE SYSTEM - SIMPLE VALIDATION TESTS
Simple validation tests for the integrated data pipeline system

PROPERTIES TESTED:
- Property 32: Multi-source data coordination
- Property 33: Data conflict resolution  
- Property 36: Automatic retry for transient failures

These tests validate the system laws in a simpler, more deterministic way.
"""

import os
import sys
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
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

class TestIntegratedDataPipelineSimple:
    """Simple validation tests for Integrated Data Pipeline System"""
    
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
    
    def test_property_32_multi_source_coordination_simple(self):
        """
        **Property 32: Multi-source data coordination**
        Simple test for dependency-based processing order
        **Validates: Requirements 6.1, 6.6**
        **Feature: northstar-v3-system-cohesion, Property 32: Multi-source data coordination**
        """
        
        # Create 3 sources with linear dependencies: A -> B -> C
        sources = {
            'source_a': MockMarketDataSource('source_a'),
            'source_b': MockMacroDataSource('source_b'),
            'source_c': MockMarketDataSource('source_c')
        }
        
        configs = {
            'source_a': DataSourceConfig(
                name='source_a',
                source_type=DataSourceType.MARKET_DATA,
                priority=DataSourcePriority.HIGH,
                dependencies=[],  # No dependencies
                schema_name="",
                freshness_threshold=timedelta(hours=24),
                retry_config={},
                quality_gates=[]
            ),
            'source_b': DataSourceConfig(
                name='source_b',
                source_type=DataSourceType.MACRO_DATA,
                priority=DataSourcePriority.MEDIUM,
                dependencies=['source_a'],  # Depends on A
                schema_name="",
                freshness_threshold=timedelta(hours=24),
                retry_config={},
                quality_gates=[]
            ),
            'source_c': DataSourceConfig(
                name='source_c',
                source_type=DataSourceType.MARKET_DATA,
                priority=DataSourcePriority.LOW,
                dependencies=['source_b'],  # Depends on B
                schema_name="",
                freshness_threshold=timedelta(hours=24),
                retry_config={},
                quality_gates=[]
            )
        }
        
        # Register sources
        for name, source in sources.items():
            self.pipeline.register_data_source(name, source, configs[name])
        
        # PROPERTY 32: Validate dependency order is respected
        processing_order = self.pipeline.dependency_graph.get_processing_order()
        
        # Verify all sources are in processing order
        assert len(processing_order) == 3, f"Expected 3 sources, got {len(processing_order)}"
        assert set(processing_order) == {'source_a', 'source_b', 'source_c'}, "Missing sources in processing order"
        
        # Verify dependency order: A before B before C
        a_index = processing_order.index('source_a')
        b_index = processing_order.index('source_b')
        c_index = processing_order.index('source_c')
        
        assert a_index < b_index, f"source_a (index {a_index}) should come before source_b (index {b_index})"
        assert b_index < c_index, f"source_b (index {b_index}) should come before source_c (index {c_index})"
        
        print(f"✅ Property 32: Multi-source coordination validated - order: {processing_order}")
    
    def test_property_33_data_conflict_resolution_simple(self):
        """
        **Property 33: Data conflict resolution**
        Simple test for priority-based conflict resolution
        **Validates: Requirements 6.2, 6.7**
        **Feature: northstar-v3-system-cohesion, Property 33: Data conflict resolution**
        """
        
        # Create mock results with conflicting data
        results = {
            'high_priority_source': ProcessingResult(
                success=True,
                data=pd.DataFrame({'price': [100.0], 'timestamp': [datetime.now()]}),
                errors=[],
                warnings=[],
                metadata={},
                processing_time=0.1
            ),
            'low_priority_source': ProcessingResult(
                success=True,
                data=pd.DataFrame({'price': [95.0], 'timestamp': [datetime.now()]}),
                errors=[],
                warnings=[],
                metadata={},
                processing_time=0.1
            )
        }
        
        # Register source configs with different priorities
        high_priority_config = DataSourceConfig(
            name='high_priority_source',
            source_type=DataSourceType.MARKET_DATA,
            priority=DataSourcePriority.CRITICAL,  # Higher priority
            dependencies=[],
            schema_name="",
            freshness_threshold=timedelta(hours=24),
            retry_config={},
            quality_gates=[]
        )
        
        low_priority_config = DataSourceConfig(
            name='low_priority_source',
            source_type=DataSourceType.MARKET_DATA,
            priority=DataSourcePriority.LOW,  # Lower priority
            dependencies=[],
            schema_name="",
            freshness_threshold=timedelta(hours=24),
            retry_config={},
            quality_gates=[]
        )
        
        self.pipeline.dependency_graph.add_node(high_priority_config)
        self.pipeline.dependency_graph.add_node(low_priority_config)
        
        # PROPERTY 33: Resolve conflicts and verify highest priority wins
        conflicts_resolved = self.pipeline._resolve_data_conflicts(results)
        
        # Should have resolved at least one conflict
        assert conflicts_resolved > 0, "No conflicts resolved despite different priorities"
        
        # Check that conflicts were recorded
        assert len(self.pipeline.data_conflicts) > 0, "Conflicts not recorded"
        
        # Verify the winning source is the high priority one
        conflict = self.pipeline.data_conflicts[0]
        assert conflict.resolution == 'high_priority_source', f"Expected high priority source to win, got {conflict.resolution}"
        
        print(f"✅ Property 33: Data conflict resolution validated - {conflicts_resolved} conflicts resolved")
    
    def test_property_36_automatic_retry_simple(self):
        """
        **Property 36: Automatic retry for transient failures**
        Simple test for retry logic with transient failures
        **Validates: Requirements 6.2, 6.7**
        **Feature: northstar-v3-system-cohesion, Property 36: Automatic retry for transient failures**
        """
        
        # Create retry manager
        retry_manager = RetryManager(
            max_retries=3,
            backoff_factor=1.5,
            initial_delay=0.01  # Fast for testing
        )
        
        # Create failing operation that succeeds on 3rd attempt
        attempt_count = 0
        
        def failing_operation():
            nonlocal attempt_count
            attempt_count += 1
            
            if attempt_count <= 2:  # Fail first 2 attempts
                raise Exception(f"Simulated failure {attempt_count}")
            
            # Success on 3rd attempt
            return ProcessingResult(
                success=True,
                data=pd.DataFrame({'test': [1, 2, 3]}),
                errors=[],
                warnings=[],
                metadata={'attempts': attempt_count},
                processing_time=0.01
            )
        
        # PROPERTY 36: Execute with retry and verify behavior
        result = retry_manager.execute_with_retry(failing_operation, "test_operation")
        
        # Should succeed after retries
        assert result.success, "Operation should succeed after retries"
        assert attempt_count == 3, f"Expected 3 attempts, got {attempt_count}"
        assert result.data is not None, "Result should contain data"
        assert len(result.data) == 3, "Result data should have 3 rows"
        
        print(f"✅ Property 36: Automatic retry validated - succeeded after {attempt_count} attempts")
    
    def test_property_36_retry_exhaustion(self):
        """
        **Property 36: Automatic retry for transient failures**
        Test that retry exhaustion is handled correctly
        """
        
        # Create retry manager with limited retries
        retry_manager = RetryManager(
            max_retries=2,
            backoff_factor=1.5,
            initial_delay=0.01
        )
        
        # Create operation that always fails
        attempt_count = 0
        
        def always_failing_operation():
            nonlocal attempt_count
            attempt_count += 1
            raise Exception(f"Always fails - attempt {attempt_count}")
        
        # Execute with retry
        result = retry_manager.execute_with_retry(always_failing_operation, "failing_operation")
        
        # Should fail after max retries
        assert not result.success, "Operation should fail after max retries"
        assert attempt_count == 3, f"Expected 3 attempts (1 + 2 retries), got {attempt_count}"
        assert len(result.errors) > 0, "Result should contain error messages"
        
        print(f"✅ Property 36: Retry exhaustion validated - failed after {attempt_count} attempts")
    
    def test_pipeline_lineage_validation(self):
        """
        Test data lineage validation completeness
        **Validates: Requirements 6.1, 6.6**
        """
        
        # Register sources with valid configurations
        sources = create_sample_data_sources()
        
        for i, (name, source) in enumerate(sources.items()):
            config = DataSourceConfig(
                name=name,
                source_type=DataSourceType.MARKET_DATA,
                priority=DataSourcePriority.MEDIUM,
                dependencies=[],  # No dependencies for simplicity
                schema_name="",
                freshness_threshold=timedelta(hours=24),
                retry_config={},
                quality_gates=[]
            )
            
            self.pipeline.register_data_source(name, source, config)
        
        # Validate lineage
        lineage_result = self.pipeline.validate_data_lineage()
        
        # Should be valid for properly configured sources
        assert lineage_result.is_valid, f"Lineage validation failed: {[e.message for e in lineage_result.errors]}"
        
        # Verify all sources are in dependency graph
        assert len(self.pipeline.dependency_graph.nodes) == len(sources), "Not all sources in dependency graph"
        
        print(f"✅ Data lineage validation validated for {len(sources)} sources")
    
    def test_pipeline_status_consistency(self):
        """
        Test pipeline status consistency and completeness
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
        
        print(f"✅ Pipeline status consistency validated")
    
    def test_full_pipeline_processing(self):
        """
        Test complete pipeline processing with multiple sources
        """
        
        # Create sources with dependencies
        market_source = MockMarketDataSource('market_data')
        macro_source = MockMacroDataSource('macro_data')
        
        market_config = DataSourceConfig(
            name='market_data',
            source_type=DataSourceType.MARKET_DATA,
            priority=DataSourcePriority.HIGH,
            dependencies=[],
            schema_name="",
            freshness_threshold=timedelta(hours=1),  # Force refresh
            retry_config={'max_retries': 2},
            quality_gates=['completeness']
        )
        
        macro_config = DataSourceConfig(
            name='macro_data',
            source_type=DataSourceType.MACRO_DATA,
            priority=DataSourcePriority.MEDIUM,
            dependencies=['market_data'],
            schema_name="",
            freshness_threshold=timedelta(hours=1),  # Force refresh
            retry_config={'max_retries': 2},
            quality_gates=['completeness']
        )
        
        # Register sources
        self.pipeline.register_data_source('market_data', market_source, market_config)
        self.pipeline.register_data_source('macro_data', macro_source, macro_config)
        
        # Process pipeline
        result = self.pipeline.process_data_pipeline(force_refresh=True)
        
        # Verify processing completed
        assert result.success, f"Pipeline processing failed: {result.errors}"
        assert result.metadata['successful_sources'] >= 1, "No sources processed successfully"
        
        # Verify state was updated
        intelligence_state = self.state_manager.get_component_state('intelligence')
        assert 'data_pipeline_last_run' in intelligence_state, "Pipeline state not updated"
        
        print(f"✅ Full pipeline processing validated - {result.metadata['successful_sources']} sources processed")

def main():
    """Run simple validation tests for Integrated Data Pipeline System"""
    
    print("🔄 RUNNING SIMPLE VALIDATION TESTS: INTEGRATED DATA PIPELINE SYSTEM")
    print("=" * 80)
    
    # Run pytest with this file
    pytest_args = [
        __file__,
        "-v",
        "--tb=short"
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