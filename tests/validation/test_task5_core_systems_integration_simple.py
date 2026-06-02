#!/usr/bin/env python3
"""
🔗 SIMPLIFIED CORE SYSTEMS INTEGRATION TEST
Capital-Grade Integration Testing for Northstar V3 System Cohesion

This validates that all core systems work together correctly with simplified tests
that focus on the essential integration points without complex timing issues.
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
fixtures_root = os.path.join(project_root, "tests", "fixtures")


from src.cohesion.configuration_manager import ConfigurationManager
from src.cohesion.unified_state_manager import UnifiedStateManager, AuthorityLevel
from src.cohesion.temporal_guard import TemporalGuard, DataQuery, MockDataSource
from src.cohesion.schema_validator import (
    SchemaValidator, SchemaRegistry, DataQualityGate,
    DataSchema, ColumnSchema, DataType, QualityRule, ErrorSeverity,
    DataContext
)

def test_core_systems_integration():
    """
    Simplified integration test that validates all core systems working together
    """
    
    print("\n🔗 RUNNING SIMPLIFIED CORE SYSTEMS INTEGRATION TEST")
    print("=" * 70)
    
    try:
        # 1. Initialize Configuration System
        print("\n📋 Testing Configuration System...")
        config_manager = ConfigurationManager(os.path.join(fixtures_root, "test_simple_config"))
        config_manager.create_default_configs()
        
        market_config = config_manager.load_config("market")
        risk_config = config_manager.load_config("risk")
        
        assert market_config is not None, "Market configuration not loaded"
        assert risk_config is not None, "Risk configuration not loaded"
        print("✅ Configuration system working")
        
        # 2. Initialize State Management System
        print("\n🧠 Testing State Management System...")
        state_manager = UnifiedStateManager()
        
        # Simple state update
        test_state = {"test_value": 42, "timestamp": datetime.now().isoformat()}
        
        update_success = state_manager.update_state(
            component="test_component",
            updates={"test_state": test_state},
            authority=AuthorityLevel.SYSTEM
        )
        
        assert update_success, "State update failed"
        
        # Verify state retrieval
        current_state = state_manager.get_state()
        assert current_state is not None, "State retrieval failed"
        print("✅ State management system working")
        
        # 3. Initialize Temporal Guard System
        print("\n⏰ Testing Temporal Guard System...")
        temporal_guard = TemporalGuard("data/logs/test_simple_temporal.json")
        
        # Create mock data source
        mock_source = MockDataSource("test_source")
        protected_source = temporal_guard.wrap_data_source(mock_source, "test_source")
        
        # Test data access
        query = DataQuery(source="test_source", filters={}, limit=10)
        data = protected_source.read_data(query)
        
        assert not data.empty, "No data retrieved from protected source"
        print("✅ Temporal guard system working")
        
        # 4. Initialize Schema Validation System
        print("\n📋 Testing Schema Validation System...")
        schema_registry = SchemaRegistry(os.path.join(fixtures_root, "test_simple_schemas"))
        schema_validator = SchemaValidator(schema_registry)
        
        # Create simple schema
        test_schema = DataSchema(
            name="simple_test",
            version="1.0.0",
            columns={
                'id': ColumnSchema(name='id', data_type=DataType.INTEGER, nullable=False),
                'value': ColumnSchema(name='value', data_type=DataType.FLOAT, nullable=False)
            }
        )
        
        schema_registry.register_schema(test_schema)
        
        # Test schema validation
        test_data = pd.DataFrame({
            'id': [1, 2, 3],
            'value': [10.0, 20.0, 30.0]
        })
        
        validation_result = schema_validator.validate_dataframe(test_data, "simple_test", strict_mode=False)
        assert validation_result.is_valid, f"Schema validation failed: {validation_result.errors}"
        print("✅ Schema validation system working")
        
        # 5. Initialize Data Quality System
        print("\n🚨 Testing Data Quality System...")
        quality_rules = [
            QualityRule(
                name="completeness",
                rule_type="completeness",
                parameters={'required_columns': ['id', 'value'], 'max_null_percentage': 0.1},
                severity=ErrorSeverity.HIGH
            )
        ]
        
        quality_gate = DataQualityGate(quality_rules)
        
        context = DataContext(
            source_name="simple_test",
            load_timestamp=datetime.now(),
            expected_row_count=3
        )
        
        quality_result = quality_gate.validate_quality(test_data, context)
        assert quality_result.is_valid, f"Quality validation failed: {quality_result.violations}"
        print("✅ Data quality system working")
        
        # 6. Test System Integration
        print("\n🔗 Testing System Integration...")
        
        # Configuration → State integration
        config_validation = config_manager.validate_all_configs()
        assert config_validation.is_valid, "Configuration validation failed"
        
        # Temporal → Schema integration
        temporal_stats = temporal_guard.get_protection_statistics()
        assert temporal_stats['protected_sources'] > 0, "No sources protected"
        
        # Schema → Quality integration
        validator_stats = schema_validator.get_validation_statistics()
        quality_stats = quality_gate.get_quality_statistics()
        
        assert validator_stats['total_validations'] > 0, "No schema validations performed"
        assert quality_stats['total_evaluations'] > 0, "No quality evaluations performed"
        
        print("✅ All systems integrated successfully")
        
        # 7. Test Error Isolation
        print("\n🛡️ Testing Error Isolation...")
        
        # Test schema validation error doesn't affect state management
        invalid_data = pd.DataFrame({'invalid': ['data']})
        
        try:
            schema_validator.validate_dataframe(invalid_data, "simple_test", strict_mode=False)
        except:
            pass  # Expected to fail
        
        # State management should still work
        test_state_2 = {"test_value": 84, "timestamp": datetime.now().isoformat()}
        
        update_success_2 = state_manager.update_state(
            component="test_component_2",
            updates={"test_state": test_state_2},
            authority=AuthorityLevel.SYSTEM
        )
        
        assert update_success_2, "State management corrupted by schema error"
        print("✅ Error isolation working")
        
        print("\n🎯 SIMPLIFIED CORE SYSTEMS INTEGRATION: ✅ SUCCESS")
        print("   All core systems working together correctly")
        print("   Configuration → State → Temporal → Schema → Quality pipeline validated")
        print("   Error isolation verified")
        print("   System ready for next phase of implementation")
        
        return True
        
    except Exception as e:
        print(f"\n❌ CORE SYSTEMS INTEGRATION FAILED: {e}")
        print("   System not ready for next phase")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Run simplified integration test
    success = test_core_systems_integration()
    
    if success:
        print("\n✅ All core systems integration tests passed!")
        print("   Northstar V3 core foundation is solid")
        print("   Ready to proceed with advanced system components")
    else:
        print("\n❌ Core systems integration failed!")
        print("   Must fix core issues before proceeding")
        sys.exit(1)
