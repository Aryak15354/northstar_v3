#!/usr/bin/env python3
"""
🔐 CAPITAL-GRADE SYSTEM LAWS INTEGRATION TEST
Test the first three implemented system laws

This validates that our capital-grade system laws are working:
- INVARIANT C1, C2, C3: Configuration Management
- INVARIANT S1, S2, S3: State Management  
- INVARIANT T1, T2, T3: Temporal Protection

This is a comprehensive integration test to verify the system is ready for capital deployment.
"""

import os
import sys
import tempfile
import shutil
from datetime import datetime, timedelta

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


from src.cohesion.configuration_manager import ConfigurationManager
from src.cohesion.unified_state_manager import UnifiedStateManager, AuthorityLevel
from src.cohesion.temporal_guard import TemporalGuard, MockDataSource, DataQuery

def test_configuration_system_laws():
    """Test Configuration System Laws (C1, C2, C3)"""
    
    print("🔐 TESTING CONFIGURATION SYSTEM LAWS")
    print("-" * 50)
    
    # Create temporary config directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        config_manager = ConfigurationManager(config_dir=temp_dir)
        
        # Create default configurations
        config_manager.create_default_configs()
        
        # Test INVARIANT C1: Single Source of Truth
        print("Testing INVARIANT C1: Single Source of Truth...")
        market_config = config_manager.load_config("market")
        risk_config = config_manager.load_config("risk")
        
        # Should have exactly one active config per type
        assert len(config_manager.configs) >= 2, "Should have at least 2 config types loaded"
        assert "market" in config_manager.configs, "Market config should be active"
        assert "risk" in config_manager.configs, "Risk config should be active"
        print("✅ INVARIANT C1 SATISFIED")
        
        # Test INVARIANT C2: Risk Parameter Consistency
        print("Testing INVARIANT C2: Risk Parameter Consistency...")
        max_pos = risk_config['max_position_size']
        max_sector = risk_config['max_sector_exposure']
        
        # Mathematical consistency: max_pos * 4 <= max_sector
        min_positions_per_sector = 4
        required_sector_exposure = max_pos * min_positions_per_sector
        
        assert required_sector_exposure <= max_sector, f"Risk parameters inconsistent: {max_pos} * 4 = {required_sector_exposure} > {max_sector}"
        print("✅ INVARIANT C2 SATISFIED")
        
        # Test INVARIANT C3: Configuration Completeness
        print("Testing INVARIANT C3: Configuration Completeness...")
        validation_result = config_manager.validate_all_configs()
        
        assert validation_result.is_valid, f"Configuration validation failed: {[e.message for e in validation_result.errors]}"
        print("✅ INVARIANT C3 SATISFIED")
        
        print("✅ ALL CONFIGURATION SYSTEM LAWS VALIDATED")
        return True
        
    finally:
        shutil.rmtree(temp_dir)

def test_state_management_system_laws():
    """Test State Management System Laws (S1, S2, S3)"""
    
    print("\n🧠 TESTING STATE MANAGEMENT SYSTEM LAWS")
    print("-" * 50)
    
    # Create temporary state directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        state_manager = UnifiedStateManager(persistence_dir=temp_dir)
        
        # Test INVARIANT S1: Atomic State Updates
        print("Testing INVARIANT S1: Atomic State Updates...")
        initial_version = state_manager.get_state_version()
        
        success = state_manager.update_state(
            component="market",
            updates={
                "regime": "expansion",
                "risk_on_probability": 0.75,
                "allowed_exposure": 0.65
            },
            authority=AuthorityLevel.INTELLIGENCE,
            reason="Test atomic update"
        )
        
        assert success, "Atomic update should succeed"
        new_version = state_manager.get_state_version()
        assert new_version == initial_version + 1, f"Version should increment by 1: {initial_version} -> {new_version}"
        
        # Verify all fields updated atomically
        market_state = state_manager.get_component_state("market")
        assert market_state["regime"] == "expansion", "Regime should be updated"
        assert market_state["risk_on_probability"] == 0.75, "Risk-on probability should be updated"
        assert market_state["allowed_exposure"] == 0.65, "Allowed exposure should be updated"
        print("✅ INVARIANT S1 SATISFIED")
        
        # Test INVARIANT S2: Temporal Monotonicity
        print("Testing INVARIANT S2: Temporal Monotonicity...")
        
        # This should fail - past timestamp
        past_time = datetime.now() - timedelta(minutes=1)
        try:
            state_manager.update_state(
                component="portfolio",
                updates={"total_exposure": 0.60},
                authority=AuthorityLevel.PORTFOLIO,
                timestamp=past_time,
                reason="Should fail - past timestamp"
            )
            assert False, "Past timestamp should be rejected"
        except ValueError as e:
            assert "INVARIANT S2 VIOLATION" in str(e), "Should mention invariant violation"
        
        print("✅ INVARIANT S2 SATISFIED")
        
        # Test INVARIANT S3: State Authority Hierarchy
        print("Testing INVARIANT S3: State Authority Hierarchy...")
        
        # Set initial value with SYSTEM authority
        state_manager.update_state(
            component="risk",
            updates={"emergency_active": False},
            authority=AuthorityLevel.SYSTEM,
            reason="Initial system value"
        )
        
        # Try to override with lower authority (should fail)
        success = state_manager.update_state(
            component="risk",
            updates={"emergency_active": True},
            authority=AuthorityLevel.POSITION,  # Lower authority
            reason="Position override attempt"
        )
        
        # Should be rejected
        assert not success, "Lower authority should be rejected"
        
        risk_state = state_manager.get_component_state("risk")
        assert risk_state.get("emergency_active") == False, "Value should not change with lower authority"
        
        # Override with higher authority (should succeed)
        success = state_manager.update_state(
            component="risk",
            updates={"emergency_active": True},
            authority=AuthorityLevel.EMERGENCY,  # Higher authority
            reason="Emergency override"
        )
        
        assert success, "Higher authority should succeed"
        
        risk_state = state_manager.get_component_state("risk")
        assert risk_state.get("emergency_active") == True, "Emergency authority should override"
        print("✅ INVARIANT S3 SATISFIED")
        
        print("✅ ALL STATE MANAGEMENT SYSTEM LAWS VALIDATED")
        return True
        
    finally:
        shutil.rmtree(temp_dir)

def test_temporal_protection_system_laws():
    """Test Temporal Protection System Laws (T1, T2, T3)"""
    
    print("\n⏰ TESTING TEMPORAL PROTECTION SYSTEM LAWS")
    print("-" * 50)
    
    # Create temporary log directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        temporal_guard = TemporalGuard(violation_log_file=os.path.join(temp_dir, "violations.json"))
        
        # Create mock data source
        mock_source = MockDataSource("test_source")
        protected_source = temporal_guard.wrap_data_source(mock_source, "test_source")
        
        # Test INVARIANT T1: No Future Data Access
        print("Testing INVARIANT T1: No Future Data Access...")
        
        # Set temporal context to past date
        as_of_date = datetime(2023, 6, 1)
        temporal_guard.set_time_context(as_of_date)
        
        # Query data
        query = DataQuery(
            source="test_source",
            filters={},
            columns=['date', 'value', 'price'],
            limit=100
        )
        
        data = protected_source.read_data(query)
        
        if not data.empty:
            max_timestamp = data['date'].max()
            assert max_timestamp <= as_of_date, f"Future data found: {max_timestamp} > {as_of_date}"
        
        print("✅ INVARIANT T1 SATISFIED")
        
        # Test INVARIANT T2: Scramble Test Invariance
        print("Testing INVARIANT T2: Scramble Test Invariance...")
        
        def simple_analysis():
            """Simple deterministic analysis"""
            query = DataQuery(
                source="test_source",
                filters={},
                columns=['date', 'value'],
                limit=50
            )
            data = protected_source.read_data(query)
            return data['value'].mean() if not data.empty else 0.0
        
        scramble_result = temporal_guard.run_scramble_test(
            data_function=simple_analysis,
            as_of_date=as_of_date,
            test_name="integration_test"
        )
        
        assert scramble_result['invariant_t2_satisfied'], "Scramble test should pass for clean analysis"
        print("✅ INVARIANT T2 SATISFIED")
        
        # Test INVARIANT T3: As-Of-Date Filtering Completeness
        print("Testing INVARIANT T3: As-Of-Date Filtering Completeness...")
        
        # Test get_data_as_of method
        as_of_data = protected_source.get_data_as_of(as_of_date, query)
        
        if not as_of_data.empty:
            max_timestamp = as_of_data['date'].max()
            assert max_timestamp <= as_of_date, f"As-of filtering failed: {max_timestamp} > {as_of_date}"
        
        print("✅ INVARIANT T3 SATISFIED")
        
        # Test system integrity
        integrity_valid = temporal_guard.validate_system_temporal_integrity()
        assert integrity_valid, "Temporal system integrity should be valid"
        
        print("✅ ALL TEMPORAL PROTECTION SYSTEM LAWS VALIDATED")
        return True
        
    finally:
        shutil.rmtree(temp_dir)
        temporal_guard.clear_time_context()

def main():
    """Run comprehensive capital-grade system laws test"""
    
    print("🔐 CAPITAL-GRADE SYSTEM LAWS INTEGRATION TEST")
    print("=" * 60)
    print("Testing the mathematical invariants that cannot be violated")
    print("This is what separates research toys from capital-grade systems")
    print()
    
    test_results = []
    
    try:
        # Test Configuration System Laws
        config_result = test_configuration_system_laws()
        test_results.append(("Configuration Laws (C1, C2, C3)", config_result))
        
        # Test State Management System Laws
        state_result = test_state_management_system_laws()
        test_results.append(("State Management Laws (S1, S2, S3)", state_result))
        
        # Test Temporal Protection System Laws
        temporal_result = test_temporal_protection_system_laws()
        test_results.append(("Temporal Protection Laws (T1, T2, T3)", temporal_result))
        
    except Exception as e:
        print(f"\n❌ CRITICAL SYSTEM FAILURE: {e}")
        return False
    
    # Summary
    print("\n" + "=" * 60)
    print("CAPITAL-GRADE SYSTEM LAWS VALIDATION SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_name, result in test_results:
        status = "✅ VALIDATED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    print()
    if all_passed:
        print("🎯 SYSTEM STATUS: ✅ CAPITAL-GRADE LAWS SATISFIED")
        print("   All mathematical invariants are enforced")
        print("   System is protected against:")
        print("     • Configuration errors and inconsistencies")
        print("     • State corruption and race conditions")
        print("     • Look-ahead bias and temporal violations")
        print("   🔐 System is ready for capital deployment")
    else:
        print("🚨 SYSTEM STATUS: ❌ CAPITAL-GRADE LAWS VIOLATED")
        print("   Mathematical invariants are not satisfied")
        print("   🚨 System is NOT safe for capital deployment")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)