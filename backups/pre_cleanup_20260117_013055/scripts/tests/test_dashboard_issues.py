#!/usr/bin/env python3
"""
Test script to identify dashboard issues
"""

import sys
import os
import traceback

# Add project root to path


def test_unified_terminal_v3():
    """Test the unified terminal V3"""
    print("🧪 TESTING UNIFIED TERMINAL V3")
    print("=" * 40)
    
    try:
        # Test imports
        print("1. Testing imports...")
        from src.dashboard.unified_terminal_v3 import (
            load_unified_system_status, 
            load_portfolio_state, 
            load_market_intelligence,
            render_master_status_bar,
            render_coordination_overview,
            render_portfolio_command_center,
            render_risk_authority_center,
            render_intelligence_organism
        )
        print("   ✅ All imports successful")
        
        # Test data loading
        print("2. Testing data loading...")
        
        system_status = load_unified_system_status()
        print(f"   ✅ System status: {system_status['overall']['health_score']:.1%} health")
        
        portfolio_state = load_portfolio_state()
        print(f"   ✅ Portfolio state: {portfolio_state['positions']} positions")
        
        intelligence = load_market_intelligence()
        print(f"   ✅ Market intelligence: {intelligence['regime']} regime")
        
        # Test rendering functions (without Streamlit context)
        print("3. Testing rendering functions...")
        print("   ⚠️ Rendering functions require Streamlit context - skipping")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        traceback.print_exc()
        return False

def test_original_unified_terminal():
    """Test the original unified terminal"""
    print("\n🧪 TESTING ORIGINAL UNIFIED TERMINAL")
    print("=" * 40)
    
    try:
        # Test imports
        print("1. Testing imports...")
        from northstar_unified_terminal import (
            load_unified_snapshot,
            load_war_room_data,
            load_portfolio_data,
            load_intelligence_data,
            check_data_health
        )
        print("   ✅ All imports successful")
        
        # Test data loading
        print("2. Testing data loading...")
        
        health = check_data_health()
        print(f"   ✅ Data health: {health.get('overall_grade', 'unknown')} grade")
        
        snapshot = load_unified_snapshot()
        print(f"   ✅ Unified snapshot: {len(snapshot)} keys")
        
        war_room = load_war_room_data()
        print(f"   ✅ War room data loaded")
        
        portfolio = load_portfolio_data()
        print(f"   ✅ Portfolio data loaded")
        
        intelligence = load_intelligence_data()
        print(f"   ✅ Intelligence data loaded")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        traceback.print_exc()
        return False

def test_dashboard_coordinator():
    """Test the dashboard coordinator"""
    print("\n🧪 TESTING DASHBOARD COORDINATOR")
    print("=" * 40)
    
    try:
        # Test imports
        print("1. Testing imports...")
        from src.dashboard.unified_dashboard_coordinator import UnifiedDashboardCoordinator
        print("   ✅ Import successful")
        
        # Test initialization
        print("2. Testing initialization...")
        coordinator = UnifiedDashboardCoordinator()
        print("   ✅ Coordinator initialized")
        
        # Test data snapshot
        print("3. Testing data snapshot...")
        success = coordinator.ensure_unified_data_snapshot()
        print(f"   {'✅' if success else '❌'} Data snapshot: {success}")
        
        # Test interface detection
        print("4. Testing interface detection...")
        interfaces = coordinator.detect_available_interfaces()
        print(f"   ✅ Detected {len(interfaces)} interfaces")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        traceback.print_exc()
        return False

def test_data_files():
    """Test if required data files exist"""
    print("\n🧪 TESTING DATA FILES")
    print("=" * 40)
    
    required_files = [
        'data/processed/market_state.parquet',
        'data/processed/portfolio_weights.parquet',
        'data/processed/capital_allocations.json',
        'data/risk/unified_risk_state.json',
        'data/processed/master_orchestrator_log.json'
    ]
    
    missing_files = []
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} - MISSING")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\n⚠️ Missing {len(missing_files)} required files:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        return False
    else:
        print(f"\n✅ All {len(required_files)} required files present")
        return True

def main():
    """Main test function"""
    print("🔍 DASHBOARD ISSUE DIAGNOSIS")
    print("=" * 50)
    
    results = []
    
    # Test data files
    results.append(("Data Files", test_data_files()))
    
    # Test dashboard coordinator
    results.append(("Dashboard Coordinator", test_dashboard_coordinator()))
    
    # Test unified terminal V3
    results.append(("Unified Terminal V3", test_unified_terminal_v3()))
    
    # Test original unified terminal
    results.append(("Original Unified Terminal", test_original_unified_terminal()))
    
    # Summary
    print("\n📊 TEST SUMMARY")
    print("=" * 20)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed < len(results):
        print("\n🔧 ISSUES DETECTED - Dashboard problems identified")
        return False
    else:
        print("\n🎉 ALL TESTS PASSED - Dashboard should be working")
        return True

if __name__ == "__main__":
    main()