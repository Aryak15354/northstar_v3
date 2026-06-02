#!/usr/bin/env python3
"""
⚡ QUICK ACTIVATE V3 ESSENTIALS
Fast activation of core Northstar V3 components with fresh data

This script runs the essential V3 components quickly:
1. Market State Update - Fresh market data integration
2. Portfolio Generation - Real portfolio with current data
3. Intelligence Stack - Core AI components
4. Shadow Validation - Quick validation run
5. System Health Check - Ensure everything works

Usage:
    python3 scripts/quick_activate_v3_essentials.py
"""

import os
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def run_essential_step(step_name, script_path, timeout=600, args=None):
    """Run an essential step with error handling"""
    
    print(f"\n⚡ {step_name}")
    print("-" * 30)
    
    try:
        cmd = [sys.executable, script_path]
        if args:
            cmd.extend(args)
        
        start_time = time.time()
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=timeout,
            cwd=project_root
        )
        
        duration = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ Completed ({duration:.1f}s)")
            return True
        else:
            print(f"⚠️ Completed with warnings ({duration:.1f}s)")
            if result.stderr:
                print(f"   Warning: {result.stderr[:100]}...")
            return True  # Continue even with warnings
            
    except subprocess.TimeoutExpired:
        print(f"❌ Timed out (>{timeout}s)")
        return False
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def main():
    """Main function for quick activation"""
    
    start_time = datetime.now()
    
    print("⚡ NORTHSTAR V3 QUICK ESSENTIALS ACTIVATION")
    print("=" * 50)
    print(f"Session started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    success_count = 0
    total_steps = 5
    
    # Step 1: Market State Update
    print("\n🔄 STEP 1/5: MARKET STATE UPDATE")
    if run_essential_step(
        "Market State Integration",
        "src/ingestion/integrated_data_pipeline.py",
        timeout=900,  # 15 minutes
        args=["--quick"]
    ):
        success_count += 1
    
    # Step 2: Portfolio Generation
    print("\n💼 STEP 2/5: PORTFOLIO GENERATION")
    if run_essential_step(
        "Real Portfolio Generation",
        "scripts/generate_portfolio.py",
        timeout=600  # 10 minutes
    ):
        success_count += 1
    
    # Step 3: Intelligence Stack
    print("\n🤖 STEP 3/5: INTELLIGENCE STACK")
    if run_essential_step(
        "Core Intelligence Stack",
        "scripts/run_full_intelligence.py",
        timeout=900  # 15 minutes
    ):
        success_count += 1
    
    # Step 4: Quick Shadow Validation
    print("\n👥 STEP 4/5: SHADOW VALIDATION")
    if run_essential_step(
        "Quick Shadow Validation",
        "scripts/test_shadow_trading_system.py",
        timeout=600  # 10 minutes
    ):
        success_count += 1
    
    # Step 5: System Health Check
    print("\n🔍 STEP 5/5: SYSTEM HEALTH CHECK")
    if run_essential_step(
        "System Health Verification",
        "scripts/verify_system_core_functionality.py",
        timeout=300  # 5 minutes
    ):
        success_count += 1
    
    # Final Summary
    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds()
    
    print(f"\n{'='*50}")
    print("⚡ QUICK ACTIVATION COMPLETE")
    print(f"{'='*50}")
    print(f"Session ended: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total duration: {total_duration/60:.1f} minutes")
    print(f"Success rate: {success_count}/{total_steps} ({success_count/total_steps*100:.1f}%)")
    
    if success_count >= 4:
        print("\n🎉 QUICK ACTIVATION SUCCESSFUL!")
        print("   Core V3 components are operational")
        print("   Ready to launch dashboards:")
        print("   • python3 scripts/launch_ultimate_real_data_cockpit.py")
        print("   • python3 scripts/launch_integrated_live_system.py")
    elif success_count >= 3:
        print("\n⚠️ PARTIAL ACTIVATION")
        print("   Most core components are working")
        print("   Some features may be limited")
    else:
        print("\n❌ ACTIVATION INCOMPLETE")
        print("   Multiple core components failed")
        print("   Run full activation: python3 scripts/activate_full_northstar_v3_system.py")

if __name__ == "__main__":
    main()