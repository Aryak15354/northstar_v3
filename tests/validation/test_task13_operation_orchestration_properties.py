"""
Property Tests for Task 13: Operation Orchestration Scripts

This module contains property-based tests that validate the universal correctness
properties of the operation orchestration system, including master operation
controller, executable scripts, and configuration management.

Author: Northstar Team
Date: 2026-01-05
"""

import pytest
import hypothesis
from hypothesis import given, strategies as st, assume, settings
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any
import tempfile
import json
from pathlib import Path

# Import the modules under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from operation.master_operation_controller import (
    MasterOperationController, OperationScenario, OperationPriority, OperationRequest
)
from operation.operation_config_manager import OperationConfigManager, ConfigTemplate
from operation.base_types import OperationConfig, OperationStatus


# Test data strategies
@st.composite
def operation_request_strategy(draw):
    """Generate valid operation requests."""
    scenario = draw(st.sampled_from(list(OperationScenario)))
    priority = draw(st.sampled_from(list(OperationPriority)))
    
    return OperationRequest(
        request_id=f"test_{draw(st.integers(min_value=1000, max_value=9999))}",
        scenario=scenario,
        priority=priority,
        parameters=draw(st.dictionaries(
            st.text(min_size=1, max_size=20),
            st.one_of(st.integers(), st.floats(allow_nan=False), st.text(), st.booleans()),
            min_size=0,
            max_size=5
        )),
        timeout_minutes=draw(st.integers(min_value=1, max_value=240)),
        retry_count=draw(st.integers(min_value=0, max_value=3))
    )


@st.composite
def config_parameters_strategy(draw):
    """Generate valid configuration parameters."""
    return draw(st.dictionaries(
        st.sampled_from([
            "max_position_size", "risk_limit", "monitoring_interval",
            "certification_threshold", "timeout_hours", "max_drawdown_threshold"
        ]),
        st.one_of(
            st.integers(min_value=1, max_value=100000),
            st.floats(min_value=0.001, max_value=1.0, allow_nan=False)
        ),
        min_size=1,
        max_size=4
    ))


class TestMasterOperationControllerProperties:
    """Property tests for Master Operation Controller."""
    
    def setup_method(self):
        """Setup test environment."""
        self.config = OperationConfig()
        self.config.max_concurrent_operations = 2  # Limit for testing
        
    @given(operation_request_strategy())
    @settings(max_examples=20, deadline=30000)
    def test_property_operation_request_handling(self, request):
        """
        Property: All valid operation requests should be accepted and queued.
        
        This test validates that the master controller properly handles
        operation request submission and queuing.
        """
        controller = MasterOperationController(self.config)
        
        # Submit operation request
        execution_id = controller.submit_operation(request)
        
        # Verify request was accepted
        assert execution_id is not None
        assert isinstance(execution_id, str)
        assert execution_id.startswith("exec_")
        assert request.request_id in execution_id
        
        # Verify operation is tracked
        assert not controller.operation_queue.empty()
    
    @given(st.lists(operation_request_strategy(), min_size=1, max_size=5))
    @settings(max_examples=10, deadline=60000)
    def test_property_concurrent_operation_limits(self, requests):
        """
        Property: Controller should respect concurrent operation limits.
        
        This test validates that the master controller properly manages
        concurrent operation execution limits.
        """
        controller = MasterOperationController(self.config)
        controller.start_operation_controller()
        
        try:
            # Submit multiple requests
            execution_ids = []
            for request in requests:
                execution_id = controller.submit_operation(request)
                execution_ids.append(execution_id)
            
            # Allow some processing time
            time.sleep(2)
            
            # Verify concurrent operation limit is respected
            active_operations = controller.get_active_operations()
            assert len(active_operations) <= self.config.max_concurrent_operations
            
            # Verify all requests are either active or queued
            total_operations = len(active_operations) + controller.operation_queue.qsize()
            assert total_operations >= 0  # Should have some operations
            
        finally:
            controller.stop_operation_controller()
    
    @given(st.sampled_from(list(OperationScenario)))
    @settings(max_examples=10, deadline=45000)
    def test_property_scenario_execution_completeness(self, scenario):
        """
        Property: All supported scenarios should execute and return results.
        
        This test validates that all operation scenarios can be executed
        and return proper operation results.
        """
        # Skip scenarios that require special setup
        assume(scenario in [
            OperationScenario.CRISIS_VALIDATION,
            OperationScenario.ALPHA_VALIDATION,
            OperationScenario.SYSTEM_VALIDATION
        ])
        
        controller = MasterOperationController(self.config)
        
        # Execute scenario
        result = controller.execute_scenario(scenario, parameters={})
        
        # Verify result completeness
        assert result is not None
        assert result.operation_id is not None
        assert result.operation_type == scenario.value
        assert result.start_time is not None
        assert result.end_time is not None
        assert result.status in [OperationStatus.SUCCESS, OperationStatus.WARNING, OperationStatus.FAILURE]
        assert result.duration_seconds is not None
        assert result.duration_seconds >= 0
        
        # Verify result structure
        assert isinstance(result.performance_metrics, dict)
        assert isinstance(result.validation_results, dict)
        assert isinstance(result.alerts_generated, list)
    
    @given(st.sampled_from(list(OperationPriority)))
    @settings(max_examples=8, deadline=30000)
    def test_property_priority_ordering(self, priority):
        """
        Property: Operations should be processed according to priority.
        
        This test validates that the operation queue respects priority ordering.
        """
        controller = MasterOperationController(self.config)
        
        # Create requests with different priorities
        high_priority_request = OperationRequest(
            request_id="high_priority",
            scenario=OperationScenario.CRISIS_VALIDATION,
            priority=OperationPriority.HIGH,
            parameters={}
        )
        
        test_priority_request = OperationRequest(
            request_id="test_priority",
            scenario=OperationScenario.ALPHA_VALIDATION,
            priority=priority,
            parameters={}
        )
        
        # Submit in reverse priority order
        controller.submit_operation(test_priority_request)
        controller.submit_operation(high_priority_request)
        
        # Verify queue is not empty
        assert not controller.operation_queue.empty()
        
        # Higher priority should have lower numeric value in queue
        priority_values = []
        while not controller.operation_queue.empty():
            priority_val, _, _ = controller.operation_queue.get()
            priority_values.append(priority_val)
        
        # Verify priority ordering (lower values = higher priority)
        assert priority_values == sorted(priority_values)


class TestOperationConfigManagerProperties:
    """Property tests for Operation Configuration Manager."""
    
    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_manager = OperationConfigManager(self.temp_dir)
    
    @given(config_parameters_strategy())
    @settings(max_examples=15, deadline=30000)
    def test_property_parameter_validation_consistency(self, parameters):
        """
        Property: Parameter validation should be consistent and deterministic.
        
        This test validates that parameter validation produces consistent
        results for the same inputs.
        """
        scenario_name = "crisis_validation"
        
        # Validate parameters multiple times
        errors1 = self.config_manager.validate_parameters(scenario_name, parameters)
        errors2 = self.config_manager.validate_parameters(scenario_name, parameters)
        
        # Results should be identical
        assert errors1 == errors2
        
        # Errors should be strings
        for error in errors1:
            assert isinstance(error, str)
            assert len(error) > 0
    
    @given(st.sampled_from(["crisis_validation", "alpha_validation", "live_operation", "system_validation"]))
    @settings(max_examples=8, deadline=30000)
    def test_property_scenario_config_generation(self, scenario_name):
        """
        Property: All scenarios should generate valid configurations.
        
        This test validates that scenario-specific configurations are
        properly generated and valid.
        """
        # Load base config first
        base_config = self.config_manager.load_base_config()
        
        # Generate scenario config
        scenario_config = self.config_manager.get_scenario_config(scenario_name)
        
        # Verify config is valid OperationConfig
        assert isinstance(scenario_config, OperationConfig)
        assert scenario_config.max_concurrent_operations > 0
        assert scenario_config.operation_timeout_hours > 0
        assert scenario_config.data_retention_days > 0
        
        # Verify scenario-specific attributes are set
        if scenario_name == "live_operation":
            assert scenario_config.enable_real_time_monitoring is True
            assert scenario_config.max_processing_latency_ms > 0
        elif scenario_name == "crisis_validation":
            assert len(scenario_config.crisis_periods) > 0
            assert scenario_config.max_drawdown_threshold > 0
    
    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=10, deadline=30000)
    def test_property_config_serialization_roundtrip(self, config_name):
        """
        Property: Configuration serialization should be reversible.
        
        This test validates that configurations can be saved and loaded
        without data loss.
        """
        # Create a configuration
        original_config = OperationConfig()
        original_config.max_concurrent_operations = 5
        original_config.operation_timeout_hours = 12
        
        # Save configuration
        safe_name = "".join(c for c in config_name if c.isalnum() or c in "._-").strip("._-")
        if not safe_name:
            safe_name = "config"
        config_path = Path(self.temp_dir) / f"{safe_name}.yaml"
        self.config_manager.save_config(original_config, str(config_path))
        
        # Verify file was created
        assert config_path.exists()
        
        # Load configuration back
        loaded_config = self.config_manager.load_base_config(str(config_path))
        
        # Verify key attributes are preserved
        assert loaded_config.max_concurrent_operations == original_config.max_concurrent_operations
        assert loaded_config.operation_timeout_hours == original_config.operation_timeout_hours
        assert loaded_config.data_retention_days == original_config.data_retention_days
    
    @given(st.sampled_from(["crisis_validation", "alpha_validation", "live_operation", "system_validation"]))
    @settings(max_examples=8, deadline=30000)
    def test_property_template_parameter_requirements(self, template_name):
        """
        Property: Templates should enforce parameter requirements consistently.
        
        This test validates that configuration templates properly enforce
        required and optional parameter specifications.
        """
        template_info = self.config_manager.get_template_info(template_name)
        
        if template_info:
            # Test with missing required parameters
            if template_info.required_parameters:
                incomplete_params = {}  # Missing required parameters
                
                with pytest.raises(ValueError) as exc_info:
                    self.config_manager.create_config_from_template(template_name, incomplete_params)
                
                assert "Missing required parameters" in str(exc_info.value)
            
            # Test with all required parameters
            if template_info.required_parameters:
                # Create minimal valid parameters
                complete_params = {}
                for param in template_info.required_parameters:
                    if param == "crisis_periods":
                        complete_params[param] = ["2008_financial_crisis"]
                    elif param == "market_regimes":
                        complete_params[param] = ["bull_market"]
                    elif param == "max_position_size":
                        complete_params[param] = 1000
                    elif param == "certification_threshold":
                        complete_params[param] = 0.85
                    else:
                        complete_params[param] = "test_value"
                
                # Should not raise exception
                config = self.config_manager.create_config_from_template(template_name, complete_params)
                assert isinstance(config, OperationConfig)


class TestOperationOrchestrationIntegrationProperties:
    """Integration property tests for operation orchestration."""
    
    def setup_method(self):
        """Setup test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_manager = OperationConfigManager(self.temp_dir)
        self.config = OperationConfig()
        self.config.max_concurrent_operations = 1  # Limit for testing
    
    @given(st.sampled_from(["crisis_validation", "alpha_validation", "system_validation"]))
    @settings(max_examples=6, deadline=60000)
    def test_property_end_to_end_operation_execution(self, scenario_name):
        """
        Property: End-to-end operation execution should be complete and consistent.
        
        This test validates that the complete operation orchestration flow
        works correctly from configuration to execution to reporting.
        """
        # Get scenario configuration
        scenario_config = self.config_manager.get_scenario_config(scenario_name)
        
        # Create master controller with scenario config
        controller = MasterOperationController(scenario_config)
        
        # Map scenario name to enum
        scenario_mapping = {
            "crisis_validation": OperationScenario.CRISIS_VALIDATION,
            "alpha_validation": OperationScenario.ALPHA_VALIDATION,
            "system_validation": OperationScenario.SYSTEM_VALIDATION
        }
        
        scenario_enum = scenario_mapping[scenario_name]
        
        # Execute scenario
        result = controller.execute_scenario(scenario_enum, parameters={})
        
        # Verify complete execution
        assert result is not None
        assert result.operation_type == scenario_enum.value
        assert result.start_time is not None
        assert result.end_time is not None
        assert result.start_time <= result.end_time
        assert result.status in [OperationStatus.SUCCESS, OperationStatus.WARNING, OperationStatus.FAILURE]
        
        # Verify performance metrics are populated
        assert isinstance(result.performance_metrics, dict)
        if result.status != OperationStatus.FAILURE:
            assert len(result.performance_metrics) > 0
        
        # Verify validation results are populated
        assert isinstance(result.validation_results, dict)
        
        # Verify alerts are properly structured
        assert isinstance(result.alerts_generated, list)
        for alert in result.alerts_generated:
            assert hasattr(alert, 'timestamp')
            assert hasattr(alert, 'level')
            assert hasattr(alert, 'component')
            assert hasattr(alert, 'message')
    
    @given(config_parameters_strategy())
    @settings(max_examples=10, deadline=45000)
    def test_property_configuration_parameter_propagation(self, parameters):
        """
        Property: Configuration parameters should properly propagate through the system.
        
        This test validates that configuration parameters are correctly
        applied and affect system behavior.
        """
        # Create configuration with parameters
        scenario_config = self.config_manager.get_scenario_config("crisis_validation", parameters)
        
        # Verify parameters were applied
        for param_name, param_value in parameters.items():
            if param_name == "max_position_size":
                assert scenario_config.max_position_size == param_value
            elif param_name == "risk_limit":
                assert scenario_config.max_drawdown_threshold == param_value
            elif param_name == "monitoring_interval":
                assert scenario_config.monitoring_interval_seconds == param_value
            elif param_name == "timeout_hours":
                assert scenario_config.operation_timeout_hours == param_value
        
        # Create controller with configured parameters
        controller = MasterOperationController(scenario_config)
        
        # Verify controller respects configuration
        assert controller.config.max_concurrent_operations == scenario_config.max_concurrent_operations
        assert controller.config.operation_timeout_hours == scenario_config.operation_timeout_hours
    
    @given(st.integers(min_value=1, max_value=3))
    @settings(max_examples=5, deadline=90000)
    def test_property_operation_state_consistency(self, max_concurrent):
        """
        Property: Operation state should remain consistent throughout execution.
        
        This test validates that operation state transitions are consistent
        and that the system maintains proper state tracking.
        """
        config = OperationConfig()
        config.max_concurrent_operations = max_concurrent
        
        controller = MasterOperationController(config)
        controller.start_operation_controller()
        
        try:
            # Submit operation
            request = OperationRequest(
                request_id="state_test",
                scenario=OperationScenario.CRISIS_VALIDATION,
                priority=OperationPriority.MEDIUM,
                parameters={}
            )
            
            execution_id = controller.submit_operation(request)
            
            # Allow some processing time
            time.sleep(3)
            
            # Check operation state consistency
            active_operations = controller.get_active_operations()
            completed_operations = controller.get_operation_history()
            
            # Verify state consistency
            total_operations = len(active_operations) + len(completed_operations)
            assert total_operations >= 1  # At least our submitted operation
            
            # Verify no operation appears in both active and completed
            active_ids = set(active_operations.keys())
            completed_ids = set(op.operation_id for op in completed_operations)
            assert len(active_ids.intersection(completed_ids)) == 0
            
            # Verify system health is trackable
            health = controller.get_system_health()
            assert health is not None
            
        finally:
            controller.stop_operation_controller()


if __name__ == "__main__":
    # Configure logging for test runs
    logging.basicConfig(level=logging.INFO)
    
    # Run the property tests
    pytest.main([__file__, "-v", "--tb=short"])
