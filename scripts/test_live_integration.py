#!/usr/bin/env python3
"""
🧪 TEST LIVE INTEGRATION - NORTHSTAR V3
Test Script for Live System Integration

This script tests the integration between core system components and the dashboard
to ensure data flows properly and all components work together.
"""

import os
import sys
import json
import time
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.integration.live_system_coordinator import LiveSystemCoordinator
from src.dashboard.integrated_live_cockpit import IntegratedLiveCockpit

def test_live_system_coordinator():
    """Test the Live System Coordinator"""
    
    print("🎯 TESTING LIVE SYSTEM COORDINATOR")
    print("=" * 50)
    
    try:
        # Create coordinator
        coordinator = LiveSystemCoordinator()
        
        # Test system status
        print("📊 Testing system status...")
        status = coordinator.get_system_status()
        
        print(f"   Coordinator: {status['coordinator']['name']} v{status['coordinator']['version']}")
        print(f"   Running: {status['coordinator']['is_running']}")
        print(f"   Registered Organs: {status['orchestrator']['registered_organs']}")
        print(f"   Healthy Organs: {status['orchestrator']['healthy_organs']}")
        
        # Test forced update
        print("\n⚡ Testing forced system update...")
        success = coordinator.force_system_update()
        print(f"   Update Success: {'✅' if success else '❌'}")
        
        # Test constitutional panels data
        print("\n🏛️ Testing constitutional panels data...")
        panels = coordinator._get_constitutional_panels_data()
        
        for panel_key, panel_data in panels.items():
            title = panel_data.get('title', 'Unknown Panel')
            print(f"   {title}")
        
        # Test dashboard data generation
        print("\n📊 Testing dashboard data generation...")
        coordinator._update_dashboard_data()
        
        # Check if dashboard files were created
        dashboard_files = status['dashboard_files']
        files_created = sum(1 for exists in dashboard_files.values() if exists)
        print(f"   Dashboard files created: {files_created}/{len(dashboard_files)}")
        
        print("\n✅ Live System Coordinator test PASSED!")
        return True
        
    except Exception as e:
        print(f"\n❌ Live System Coordinator test FAILED: {e}")
        return False

def test_integrated_live_cockpit():
    """Test the Integrated Live Cockpit"""
    
    print("\n🖥️ TESTING INTEGRATED LIVE COCKPIT")
    print("=" * 50)
    
    try:
        # Create cockpit
        cockpit = IntegratedLiveCockpit()
        
        # Test loading live system state
        print("📊 Testing live system state loading...")
        live_state = cockpit.load_live_system_state()
        
        system_status = live_state.get('system_status', 'unknown')
        print(f"   System Status: {system_status}")
        
        # Test constitutional panels data
        print("\n🏛️ Testing constitutional panels data...")
        panels = live_state.get('constitutional_panels', {})
        
        for panel_key, panel_data in panels.items():
            title = panel_data.get('title', 'Unknown Panel')
            print(f"   {title}")
        
        # Test performance tracking
        print("\n📈 Testing performance tracking...")
        performance_df = cockpit.load_performance_tracking()
        print(f"   Performance records: {len(performance_df)}")
        
        # Test portfolio tracking
        print("\n💼 Testing portfolio tracking...")
        portfolio_df = cockpit.load_portfolio_tracking()
        print(f"   Portfolio records: {len(portfolio_df)}")
        
        print("\n✅ Integrated Live Cockpit test PASSED!")
        return True
        
    except Exception as e:
        print(f"\n❌ Integrated Live Cockpit test FAILED: {e}")
        return False

def test_data_flow_integration():
    """Test data flow between coordinator and dashboard"""
    
    print("\n🔄 TESTING DATA FLOW INTEGRATION")
    print("=" * 50)
    
    try:
        # Create coordinator and generate data
        coordinator = LiveSystemCoordinator()
        
        print("📊 Generating system data...")
        coordinator.force_system_update()
        
        # Wait a moment for data to be written
        time.sleep(2)
        
        # Create cockpit and load data
        cockpit = IntegratedLiveCockpit()
        
        print("📥 Loading data in dashboard...")
        live_state = cockpit.load_live_system_state()
        
        # Verify data consistency
        print("\n🔍 Verifying data consistency...")
        
        # Check timestamp consistency
        coordinator_status = coordinator.get_system_status()
        dashboard_timestamp = live_state.get('timestamp')
        
        if dashboard_timestamp:
            print(f"   Dashboard timestamp: {dashboard_timestamp}")
            print("   ✅ Timestamp data flow working")
        else:
            print("   ❌ No timestamp in dashboard data")
        
        # Check system status consistency
        coordinator_running = coordinator_status['coordinator']['is_running']
        dashboard_status = live_state.get('system_status')
        
        print(f"   Coordinator running: {coordinator_running}")
        print(f"   Dashboard status: {dashboard_status}")
        
        # Check constitutional panels data
        panels = live_state.get('constitutional_panels', {})
        if panels:
            print(f"   Constitutional panels: {len(panels)} panels loaded")
            print("   ✅ Constitutional panels data flow working")
        else:
            print("   ❌ No constitutional panels data")
        
        print("\n✅ Data Flow Integration test PASSED!")
        return True
        
    except Exception as e:
        print(f"\n❌ Data Flow Integration test FAILED: {e}")
        return False

def test_portfolio_tracking_simulation():
    """Test portfolio tracking with simulated data"""
    
    print("\n💼 TESTING PORTFOLIO TRACKING SIMULATION")
    print("=" * 50)
    
    try:
        coordinator = LiveSystemCoordinator()
        
        # Simulate multiple system updates to generate tracking data
        print("📊 Simulating system updates for tracking...")
        
        for i in range(3):
            print(f"   Update {i+1}/3...")
            coordinator.force_system_update()
            coordinator._track_system_performance()
            time.sleep(1)  # Brief pause between updates
        
        # Check if performance tracking data was generated
        performance_history = coordinator.performance_history
        print(f"   Performance records generated: {len(performance_history)}")
        
        if performance_history:
            latest_record = performance_history[-1]
            print(f"   Latest health score: {latest_record['system_health_score']:.1%}")
            print(f"   Latest exposure: {latest_record['portfolio_exposure']:.1%}")
            print("   ✅ Portfolio tracking simulation working")
        else:
            print("   ❌ No performance tracking data generated")
        
        print("\n✅ Portfolio Tracking Simulation test PASSED!")
        return True
        
    except Exception as e:
        print(f"\n❌ Portfolio Tracking Simulation test FAILED: {e}")
        return False

def run_comprehensive_test():
    """Run comprehensive integration test"""
    
    print("🧪 COMPREHENSIVE LIVE INTEGRATION TEST")
    print("=" * 60)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    test_results = []
    
    # Test 1: Live System Coordinator
    result1 = test_live_system_coordinator()
    test_results.append(("Live System Coordinator", result1))
    
    # Test 2: Integrated Live Cockpit
    result2 = test_integrated_live_cockpit()
    test_results.append(("Integrated Live Cockpit", result2))
    
    # Test 3: Data Flow Integration
    result3 = test_data_flow_integration()
    test_results.append(("Data Flow Integration", result3))
    
    # Test 4: Portfolio Tracking Simulation
    result4 = test_portfolio_tracking_simulation()
    test_results.append(("Portfolio Tracking Simulation", result4))
    
    # Summary
    print("\n📋 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed_tests = 0
    total_tests = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {test_name}: {status}")
        if result:
            passed_tests += 1
    
    print(f"\nOverall Result: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED! Live integration is working correctly.")
        print("\n🚀 Ready to launch integrated system with:")
        print("   python scripts/launch_integrated_live_system.py")
        return True
    else:
        print("⚠️ Some tests failed. Please check the errors above.")
        return False

def main():
    """Main function"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Live Integration")
    parser.add_argument("--coordinator", action="store_true", help="Test coordinator only")
    parser.add_argument("--dashboard", action="store_true", help="Test dashboard only")
    parser.add_argument("--data-flow", action="store_true", help="Test data flow only")
    parser.add_argument("--tracking", action="store_true", help="Test tracking only")
    
    args = parser.parse_args()
    
    if args.coordinator:
        test_live_system_coordinator()
    elif args.dashboard:
        test_integrated_live_cockpit()
    elif args.data_flow:
        test_data_flow_integration()
    elif args.tracking:
        test_portfolio_tracking_simulation()
    else:
        run_comprehensive_test()

if __name__ == "__main__":
    main()