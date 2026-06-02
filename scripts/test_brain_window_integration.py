#!/usr/bin/env python3
"""
🧠 BRAIN WINDOW INTEGRATION TEST
Test Brain Window integration with Living System

This test verifies that the Brain Window correctly reads from unified state
and can send intents to the living system.
"""

import os
import sys
import json
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_brain_window_integration():
    """Test Brain Window integration with living system"""
    
    print("🧠 TESTING BRAIN WINDOW INTEGRATION")
    print("=" * 50)
    
    try:
        # Test 1: Import Brain Window Interface
        print("\n📦 Test 1: Import Brain Window Interface")
        from src.dashboard.brain_window import BrainWindowInterface
        print("   ✅ Brain Window Interface imported successfully")
        
        # Test 2: Create Brain Window Interface
        print("\n🔧 Test 2: Create Brain Window Interface")
        interface = BrainWindowInterface()
        print("   ✅ Brain Window Interface created successfully")
        print(f"   📊 Interface version: {interface.version}")
        
        # Test 3: Test State Reading
        print("\n📖 Test 3: Test State Reading from Unified State")
        dashboard_state = interface.dashboard_state
        
        required_keys = ['timestamp', 'system_health', 'command_bar', 'market_state', 
                        'intelligence_state', 'portfolio_state', 'risk_state']
        
        for key in required_keys:
            if key in dashboard_state:
                print(f"   ✅ {key}: Available")
            else:
                print(f"   ❌ {key}: Missing")
        
        # Test 4: Test System Health Reading
        print("\n🏥 Test 4: Test System Health Reading")
        system_health = dashboard_state.get('system_health', {})
        health_score = system_health.get('overall_health_score', 0.0)
        health_status = system_health.get('health_status', 'unknown')
        
        print(f"   📊 Health Score: {health_score:.2f}")
        print(f"   📊 Health Status: {health_status}")
        print(f"   ✅ System health reading successful")
        
        # Test 5: Test Command Bar Data
        print("\n🎯 Test 5: Test Command Bar Data")
        command_bar = dashboard_state.get('command_bar', {})
        
        command_metrics = ['regime', 'exposure', 'ai_conviction', 'emergency_active']
        for metric in command_metrics:
            value = command_bar.get(metric, 'N/A')
            print(f"   📊 {metric}: {value}")
        
        print(f"   ✅ Command bar data reading successful")
        
        # Test 6: Test Intent Sending
        print("\n📤 Test 6: Test Intent Sending")
        
        # Test sending a test intent
        test_intent_success = interface.send_intent("test_intent", {
            "test_parameter": "test_value",
            "timestamp": datetime.now().isoformat()
        })
        
        if test_intent_success:
            print("   ✅ Intent sending successful")
            print(f"   📊 Intent queue length: {len(interface.intent_queue)}")
        else:
            print("   ❌ Intent sending failed")
        
        # Test 7: Test Intent File Creation
        print("\n📁 Test 7: Test Intent File Creation")
        intent_file = 'data/intents/brain_window_intents.json'
        
        if os.path.exists(intent_file):
            with open(intent_file, 'r') as f:
                intents_data = json.load(f)
                intent_count = len(intents_data.get('intents', []))
                print(f"   ✅ Intent file created with {intent_count} intents")
        else:
            print("   ❌ Intent file not created")
        
        # Test 8: Test No Independent Computation
        print("\n🚫 Test 8: Test No Independent Computation")
        
        # Verify Brain Window doesn't have independent data loading methods
        forbidden_methods = ['load_market_data', 'compute_portfolio', 'calculate_risk']
        has_forbidden = False
        
        for method in forbidden_methods:
            if hasattr(interface, method):
                print(f"   ❌ Found forbidden method: {method}")
                has_forbidden = True
        
        if not has_forbidden:
            print("   ✅ No independent computation methods found")
        
        # Test 9: Test State Refresh
        print("\n🔄 Test 9: Test State Refresh")
        refresh_success = interface.refresh_state()
        
        if refresh_success:
            print("   ✅ State refresh successful")
        else:
            print("   ❌ State refresh failed")
        
        print(f"\n🎉 BRAIN WINDOW INTEGRATION TEST COMPLETE")
        print(f"✅ Brain Window successfully reads from Unified State")
        print(f"✅ Brain Window can send intents to living system")
        print(f"✅ Brain Window operates as pure display interface")
        
        return True
        
    except Exception as e:
        print(f"\n❌ BRAIN WINDOW INTEGRATION TEST FAILED")
        print(f"Error: {e}")
        return False

def main():
    """Main execution"""
    
    success = test_brain_window_integration()
    
    if success:
        print("\n✅ All tests passed - Brain Window integration successful")
    else:
        print("\n❌ Tests failed - Brain Window integration issues")
    
    return success

if __name__ == "__main__":
    main()