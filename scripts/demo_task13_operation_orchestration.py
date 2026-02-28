#!/usr/bin/env python3
"""
Demo Script for Task 13: Operation Orchestration Scripts

This script demonstrates the comprehensive operation orchestration capabilities
of the Northstar V3 system, including master operation controller, executable
scripts, and configuration management.

Author: Northstar Team
Date: 2026-01-05
"""

import sys
import logging
import time
import asyncio
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from operation.master_operation_controller import (
    MasterOperationController, OperationScenario, OperationPriority, OperationRequest
)
from operation.operation_config_manager import OperationConfigManager
from operation.base_types import OperationConfig
from operation.logging_config import setup_operation_logging


def demonstrate_master_operation_controller():
    """Demonstrate master operation controller capabilities."""
    print("\n" + "="*80)
    print("MASTER OPERATION CONTROLLER DEMONSTRATION")
    print("="*80)
    
    # Initialize configuration
    config = OperationConfig()
    config.max_concurrent_operations = 2
    
    # Create master controller
    controller = MasterOperationController(config)
    
    print(f"✅ Master Operation Controller initialized")
    print(f"   Max concurrent operations: {config.max_concurrent_operations}")
    print(f"   Operation timeout: {config.operation_timeout_hours} hours")
    
    # Start the controller
    controller.start_operation_controller()
    print("✅ Operation controller started")
    
    try:
        # Demonstrate scenario execution
        print("\n📋 Executing Crisis Validation Scenario...")
        crisis_result = controller.execute_scenario(
            scenario=OperationScenario.CRISIS_VALIDATION,
            parameters={"crisis_periods": ["2008_financial_crisis"]},
            priority=OperationPriority.HIGH
        )
        
        print(f"   Status: {crisis_result.status.value}")
        print(f"   Duration: {crisis_result.duration_seconds:.2f} seconds")
        print(f"   Performance metrics: {len(crisis_result.performance_metrics)} metrics")
        print(f"   Alerts generated: {len(crisis_result.alerts_generated)}")
        
        # Demonstrate alpha validation
        print("\n📊 Executing Alpha Validation Scenario...")
        alpha_result = controller.execute_scenario(
            scenario=OperationScenario.ALPHA_VALIDATION,
            parameters={"market_regimes": ["bull_market", "bear_market"]},
            priority=OperationPriority.HIGH
        )
        
        print(f"   Status: {alpha_result.status.value}")
        print(f"   Duration: {alpha_result.duration_seconds:.2f} seconds")
        print(f"   Performance metrics: {len(alpha_result.performance_metrics)} metrics")
        
        # Demonstrate system validation
        print("\n🔍 Executing System Validation Scenario...")
        system_result = controller.execute_scenario(
            scenario=OperationScenario.SYSTEM_VALIDATION,
            parameters={"certification_threshold": 0.85},
            priority=OperationPriority.CRITICAL
        )
        
        print(f"   Status: {system_result.status.value}")
        print(f"   Duration: {system_result.duration_seconds:.2f} seconds")
        print(f"   Certification ready: {system_result.performance_metrics.get('certification_ready', False)}")
        
        # Demonstrate operation queue management
        print("\n⚡ Demonstrating Operation Queue Management...")
        
        # Submit multiple operations with different priorities
        requests = [
            OperationRequest(
                request_id="low_priority_test",
                scenario=OperationScenario.CRISIS_VALIDATION,
                priority=OperationPriority.LOW,
                parameters={}
            ),
            OperationRequest(
                request_id="high_priority_test",
                scenario=OperationScenario.ALPHA_VALIDATION,
                priority=OperationPriority.HIGH,
                parameters={}
            ),
            OperationRequest(
                request_id="critical_priority_test",
                scenario=OperationScenario.SYSTEM_VALIDATION,
                priority=OperationPriority.CRITICAL,
                parameters={}
            )
        ]
        
        execution_ids = []
        for request in requests:
            execution_id = controller.submit_operation(request)
            execution_ids.append(execution_id)
            print(f"   Submitted {request.priority.value} priority operation: {execution_id}")
        
        # Monitor active operations
        time.sleep(2)
        active_operations = controller.get_active_operations()
        print(f"   Active operations: {len(active_operations)}")
        
        # Get operation history
        operation_history = controller.get_operation_history()
        print(f"   Completed operations: {len(operation_history)}")
        
        # Check system health
        system_health = controller.get_system_health()
        print(f"   System health: {system_health.value}")
        
    finally:
        # Stop the controller
        controller.stop_operation_controller()
        print("\n✅ Operation controller stopped gracefully")
    
    return True


def demonstrate_configuration_management():
    """Demonstrate configuration management capabilities."""
    print("\n" + "="*80)
    print("CONFIGURATION MANAGEMENT DEMONSTRATION")
    print("="*80)
    
    # Create configuration manager
    config_manager = OperationConfigManager("temp/demo_config")
    
    print("✅ Configuration Manager initialized")
    
    # Load base configuration
    base_config = config_manager.load_base_config()
    print(f"✅ Base configuration loaded")
    print(f"   Max concurrent operations: {base_config.max_concurrent_operations}")
    print(f"   Operation timeout: {base_config.operation_timeout_hours} hours")
    print(f"   Crisis periods configured: {len(base_config.crisis_periods)}")
    
    # Demonstrate scenario-specific configurations
    print("\n📋 Generating Scenario-Specific Configurations...")
    
    scenarios = ["crisis_validation", "alpha_validation", "live_operation", "system_validation"]
    
    for scenario_name in scenarios:
        scenario_config = config_manager.get_scenario_config(scenario_name)
        print(f"   {scenario_name}:")
        print(f"     Max concurrent ops: {scenario_config.max_concurrent_operations}")
        print(f"     Timeout hours: {scenario_config.operation_timeout_hours}")
        
        if scenario_name == "live_operation":
            print(f"     Real-time monitoring: {scenario_config.enable_real_time_monitoring}")
            print(f"     Max processing latency: {scenario_config.max_processing_latency_ms}ms")
    
    # Demonstrate configuration templates
    print("\n📝 Available Configuration Templates:")
    available_templates = config_manager.get_available_templates()
    
    for template_name in available_templates:
        template_info = config_manager.get_template_info(template_name)
        if template_info:
            print(f"   {template_name}:")
            print(f"     Description: {template_info.description}")
            print(f"     Required parameters: {template_info.required_parameters}")
            print(f"     Optional parameters: {template_info.optional_parameters}")
    
    # Demonstrate template usage
    print("\n🔧 Creating Configuration from Template...")
    
    try:
        # Create crisis validation config from template
        crisis_params = {
            "crisis_periods": ["2008_financial_crisis", "2020_covid_crash"]
        }
        
        crisis_config = config_manager.create_config_from_template(
            "crisis_validation", 
            crisis_params
        )
        
        print("   ✅ Crisis validation config created from template")
        print(f"     Crisis periods: {len(crisis_config.crisis_periods)}")
        print(f"     Max drawdown threshold: {crisis_config.max_drawdown_threshold}")
        
        # Create live operation config from template
        live_params = {
            "max_position_size": 5000
        }
        
        live_config = config_manager.create_config_from_template(
            "live_operation",
            live_params
        )
        
        print("   ✅ Live operation config created from template")
        print(f"     Max position size: {live_config.max_position_size}")
        print(f"     Max processing latency: {live_config.max_processing_latency_ms}ms")
        
    except Exception as e:
        print(f"   ❌ Template creation failed: {str(e)}")
    
    # Demonstrate parameter validation
    print("\n✅ Parameter Validation:")
    
    test_parameters = {
        "max_drawdown_threshold": 0.15,
        "min_sharpe_ratio": 0.5,
        "crisis_periods": ["2008_financial_crisis"]
    }
    
    validation_errors = config_manager.validate_parameters("crisis_validation", test_parameters)
    
    if validation_errors:
        print(f"   ❌ Validation errors found: {len(validation_errors)}")
        for error in validation_errors:
            print(f"     - {error}")
    else:
        print("   ✅ All parameters valid")
    
    # Test invalid parameters
    invalid_parameters = {
        "max_drawdown_threshold": 1.5,  # Invalid: > 1.0
        "min_sharpe_ratio": -5.0,       # Invalid: < -2.0
    }
    
    validation_errors = config_manager.validate_parameters("crisis_validation", invalid_parameters)
    print(f"   Invalid parameters test: {len(validation_errors)} errors found (expected)")
    
    return True


def demonstrate_executable_scripts():
    """Demonstrate executable operation scripts."""
    print("\n" + "="*80)
    print("EXECUTABLE OPERATION SCRIPTS DEMONSTRATION")
    print("="*80)
    
    scripts_dir = Path(__file__).parent
    
    # List available executable scripts
    executable_scripts = [
        "run_crisis_validation.py",
        "run_alpha_validation.py", 
        "run_comprehensive_system_validation.py",
        "launch_live_operation.py"
    ]
    
    print("📜 Available Executable Scripts:")
    
    for script_name in executable_scripts:
        script_path = scripts_dir / script_name
        if script_path.exists():
            print(f"   ✅ {script_name}")
            print(f"      Path: {script_path}")
            
            # Show script help (first few lines of docstring)
            try:
                with open(script_path, 'r') as f:
                    lines = f.readlines()
                    in_docstring = False
                    docstring_lines = []
                    
                    for line in lines:
                        if '"""' in line and not in_docstring:
                            in_docstring = True
                            continue
                        elif '"""' in line and in_docstring:
                            break
                        elif in_docstring:
                            docstring_lines.append(line.strip())
                    
                    if docstring_lines:
                        print(f"      Description: {docstring_lines[0]}")
                        if len(docstring_lines) > 2:
                            print(f"      Usage: {docstring_lines[2]}")
            except Exception:
                pass
        else:
            print(f"   ❌ {script_name} (not found)")
    
    # Demonstrate script parameter handling
    print("\n⚙️  Script Parameter Examples:")
    
    script_examples = {
        "run_crisis_validation.py": [
            "--crisis-periods 2008_financial_crisis 2020_covid_crash",
            "--output reports/crisis --verbose",
            "--config config/crisis_config.yaml"
        ],
        "run_alpha_validation.py": [
            "--regimes bull_market bear_market",
            "--min-alpha 0.02 --output reports/alpha",
            "--verbose --config config/alpha_config.yaml"
        ],
        "run_comprehensive_system_validation.py": [
            "--certification-threshold 0.90",
            "--skip-integration --verbose",
            "--components data_pipeline intelligence_engine"
        ],
        "launch_live_operation.py": [
            "--dry-run --max-position-size 5000",
            "--risk-limit 0.02 --monitoring-interval 30",
            "--config config/live_config.yaml --verbose"
        ]
    }
    
    for script_name, examples in script_examples.items():
        print(f"\n   {script_name}:")
        for example in examples:
            print(f"     python scripts/{script_name} {example}")
    
    return True


def demonstrate_integration_workflow():
    """Demonstrate complete integration workflow."""
    print("\n" + "="*80)
    print("COMPLETE INTEGRATION WORKFLOW DEMONSTRATION")
    print("="*80)
    
    print("🔄 Demonstrating End-to-End Operation Orchestration Workflow...")
    
    # Step 1: Configuration Management
    print("\n1️⃣  Configuration Setup")
    config_manager = OperationConfigManager("temp/workflow_config")
    
    # Create custom configuration for workflow
    workflow_params = {
        "max_position_size": 10000,
        "certification_threshold": 0.85,
        "timeout_hours": 2
    }
    
    workflow_config = config_manager.get_scenario_config("system_validation", workflow_params)
    print("   ✅ Workflow configuration created")
    
    # Step 2: Master Controller Initialization
    print("\n2️⃣  Master Controller Initialization")
    controller = MasterOperationController(workflow_config)
    controller.start_operation_controller()
    print("   ✅ Master controller started")
    
    try:
        # Step 3: Sequential Operation Execution
        print("\n3️⃣  Sequential Operation Execution")
        
        operations = [
            ("System Validation", OperationScenario.SYSTEM_VALIDATION),
            ("Crisis Validation", OperationScenario.CRISIS_VALIDATION),
            ("Alpha Validation", OperationScenario.ALPHA_VALIDATION)
        ]
        
        results = []
        
        for operation_name, scenario in operations:
            print(f"\n   Executing {operation_name}...")
            start_time = time.time()
            
            result = controller.execute_scenario(
                scenario=scenario,
                parameters={},
                priority=OperationPriority.HIGH
            )
            
            execution_time = time.time() - start_time
            results.append((operation_name, result, execution_time))
            
            print(f"   ✅ {operation_name} completed")
            print(f"      Status: {result.status.value}")
            print(f"      Duration: {execution_time:.2f} seconds")
            print(f"      Alerts: {len(result.alerts_generated)}")
        
        # Step 4: Results Analysis
        print("\n4️⃣  Results Analysis")
        
        total_operations = len(results)
        successful_operations = sum(1 for _, result, _ in results if result.status.value == "success")
        total_execution_time = sum(exec_time for _, _, exec_time in results)
        total_alerts = sum(len(result.alerts_generated) for _, result, _ in results)
        
        print(f"   📊 Workflow Summary:")
        print(f"      Total operations: {total_operations}")
        print(f"      Successful operations: {successful_operations}")
        print(f"      Success rate: {successful_operations/total_operations:.1%}")
        print(f"      Total execution time: {total_execution_time:.2f} seconds")
        print(f"      Average execution time: {total_execution_time/total_operations:.2f} seconds")
        print(f"      Total alerts generated: {total_alerts}")
        
        # Step 5: System Health Assessment
        print("\n5️⃣  System Health Assessment")
        
        system_health = controller.get_system_health()
        operation_history = controller.get_operation_history()
        
        print(f"   🏥 System Health: {system_health.value}")
        print(f"   📈 Operation History: {len(operation_history)} completed operations")
        
        # Determine overall workflow status
        if successful_operations == total_operations:
            workflow_status = "✅ WORKFLOW COMPLETED SUCCESSFULLY"
        elif successful_operations > 0:
            workflow_status = "⚠️  WORKFLOW COMPLETED WITH ISSUES"
        else:
            workflow_status = "❌ WORKFLOW FAILED"
        
        print(f"\n🎯 {workflow_status}")
        
    finally:
        # Step 6: Cleanup
        print("\n6️⃣  Cleanup")
        controller.stop_operation_controller()
        print("   ✅ Master controller stopped")
        print("   ✅ Workflow cleanup completed")
    
    return True


def main():
    """Main demonstration function."""
    # Setup logging
    logger = setup_operation_logging(log_level="INFO")
    
    print("🚀 NORTHSTAR V3 OPERATION ORCHESTRATION DEMONSTRATION")
    print("=" * 80)
    print(f"Started at: {datetime.now()}")
    print("This demonstration showcases the comprehensive operation orchestration")
    print("capabilities of the Northstar V3 trading system.")
    
    try:
        # Run demonstrations
        demonstrations = [
            ("Master Operation Controller", demonstrate_master_operation_controller),
            ("Configuration Management", demonstrate_configuration_management),
            ("Executable Scripts", demonstrate_executable_scripts),
            ("Integration Workflow", demonstrate_integration_workflow)
        ]
        
        results = []
        
        for demo_name, demo_func in demonstrations:
            print(f"\n🎯 Running {demo_name} demonstration...")
            try:
                success = demo_func()
                results.append((demo_name, success))
                if success:
                    print(f"✅ {demo_name} demonstration completed successfully")
                else:
                    print(f"⚠️  {demo_name} demonstration completed with issues")
            except Exception as e:
                print(f"❌ {demo_name} demonstration failed: {str(e)}")
                results.append((demo_name, False))
        
        # Final summary
        print("\n" + "="*80)
        print("DEMONSTRATION SUMMARY")
        print("="*80)
        
        successful_demos = sum(1 for _, success in results if success)
        total_demos = len(results)
        
        for demo_name, success in results:
            status = "✅ PASSED" if success else "❌ FAILED"
            print(f"{demo_name}: {status}")
        
        print(f"\nOverall Success Rate: {successful_demos}/{total_demos} ({successful_demos/total_demos:.1%})")
        
        if successful_demos == total_demos:
            print("🎉 ALL DEMONSTRATIONS COMPLETED SUCCESSFULLY!")
            print("   The Operation Orchestration System is working correctly.")
        else:
            print("⚠️  SOME DEMONSTRATIONS HAD ISSUES")
            print("   Please review the output above for details.")
        
        print(f"\nCompleted at: {datetime.now()}")
        print("="*80)
        
        return successful_demos == total_demos
        
    except Exception as e:
        logger.error(f"Demonstration failed: {str(e)}")
        print(f"\n❌ DEMONSTRATION FAILED: {str(e)}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)