#!/usr/bin/env python3
"""
🏛️ INSTITUTIONAL 12-MONTH VALIDATION LAUNCHER
Complete launcher for rigorous institutional validation

This script:
1. Validates system readiness
2. Runs the 12-month walk-forward validation
3. Generates the institutional report
4. Provides final assessment

Usage:
    python scripts/run_institutional_12month_validation.py
"""

import sys
import os
import subprocess
from pathlib import Path
from datetime import datetime
import json

# Add src to path for imports
sys.path.append('src')

def check_system_readiness():
    """Check if the system is ready for institutional validation"""
    
    print("🔍 CHECKING SYSTEM READINESS...")
    
    readiness_checks = {
        'data_availability': False,
        'system_components': False,
        'temporal_protection': False,
        'risk_management': False
    }
    
    # Check data availability
    required_data_files = [
        'data/processed/market_state.parquet',
        'data/processed/prices.parquet',
        'data/macro/factors/macro_score.parquet'
    ]
    
    data_available = all(os.path.exists(f) for f in required_data_files)
    readiness_checks['data_availability'] = data_available
    
    if data_available:
        print("   ✅ Data files: Available")
    else:
        print("   ❌ Data files: Missing required files")
        for f in required_data_files:
            if not os.path.exists(f):
                print(f"      Missing: {f}")
    
    # Check system components
    required_components = [
        'src/orchestrator/master_orchestrator.py',
        'src/validation/enhanced_walk_forward_engine.py',
        'src/intelligence/temporal_guard.py',
        'src/intelligence/institutional_alpha_engine.py',
        'src/risk/portfolio_kill_switches.py'
    ]
    
    components_available = all(os.path.exists(f) for f in required_components)
    readiness_checks['system_components'] = components_available
    
    if components_available:
        print("   ✅ System components: Available")
    else:
        print("   ❌ System components: Missing required components")
        for f in required_components:
            if not os.path.exists(f):
                print(f"      Missing: {f}")
    
    # Check temporal protection
    try:
        from src.intelligence.temporal_guard import TemporalGuard
        guard = TemporalGuard()
        readiness_checks['temporal_protection'] = True
        print("   ✅ Temporal protection: Active")
    except Exception as e:
        print(f"   ❌ Temporal protection: Failed to initialize - {e}")
    
    # Check risk management
    try:
        from src.risk.portfolio_kill_switches import PortfolioKillSwitches
        kill_switches = PortfolioKillSwitches()
        readiness_checks['risk_management'] = True
        print("   ✅ Risk management: Armed")
    except Exception as e:
        print(f"   ❌ Risk management: Failed to initialize - {e}")
    
    all_ready = all(readiness_checks.values())
    
    if all_ready:
        print("   ✅ SYSTEM READY FOR INSTITUTIONAL VALIDATION")
    else:
        print("   ❌ SYSTEM NOT READY - Fix issues before proceeding")
    
    return all_ready, readiness_checks

def run_validation():
    """Run the institutional 12-month validation"""
    
    print("\n🏛️ RUNNING INSTITUTIONAL 12-MONTH VALIDATION...")
    print("⚠️  WARNING: This will take significant time")
    print("⚠️  WARNING: All parameters are FROZEN - no changes allowed")
    
    # Confirm execution
    response = input("\nProceed with validation? (yes/no): ").lower().strip()
    if response != 'yes':
        print("❌ Validation cancelled by user")
        return False, None
    
    try:
        # Import and run the validator
        from scripts.institutional_12month_walk_forward import Institutional12MonthWalkForward
        
        print("\n🔒 Initializing validator with frozen configuration...")
        validator = Institutional12MonthWalkForward()
        
        print("🧪 Running complete validation...")
        results = validator.run_complete_validation()
        
        return True, results
        
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return False, None

def generate_report(results):
    """Generate the institutional report"""
    
    if not results:
        print("❌ No results available for report generation")
        return None
    
    print("\n📊 GENERATING INSTITUTIONAL REPORT...")
    
    try:
        from scripts.generate_institutional_walkforward_report import InstitutionalWalkForwardReporter
        
        # Find the results file
        results_dir = Path("data/validation/institutional_12month")
        results_files = list(results_dir.glob("12month_walkforward_results_*.json"))
        
        if not results_files:
            print("❌ No results files found for report generation")
            return None
        
        # Use most recent file
        latest_file = max(results_files, key=lambda x: x.stat().st_mtime)
        
        # Generate report
        reporter = InstitutionalWalkForwardReporter(str(latest_file))
        report_file = reporter.generate_complete_report()
        
        print(f"✅ Report generated: {report_file}")
        return report_file
        
    except Exception as e:
        print(f"❌ Report generation failed: {e}")
        return None

def provide_final_assessment(results, report_file):
    """Provide final assessment and recommendations"""
    
    print("\n" + "=" * 80)
    print("INSTITUTIONAL VALIDATION ASSESSMENT")
    print("=" * 80)
    
    if not results:
        print("❌ VALIDATION FAILED - No results available")
        return
    
    status = results.get('validation_status', 'UNKNOWN')
    windows = results.get('windows_processed', 0)
    config_hash = results.get('configuration_hash', 'UNKNOWN')
    
    print(f"Status: {status}")
    print(f"Windows Processed: {windows}")
    print(f"Configuration Hash: {config_hash[:16]}...")
    print(f"Execution Time: {results.get('execution_timestamp', 'UNKNOWN')}")
    
    if report_file:
        print(f"Report Location: {report_file}")
    
    print("\n" + "-" * 80)
    
    if status == 'PASS':
        print("✅ SYSTEM PASSES INSTITUTIONAL VALIDATION")
        print("\nRECOMMENDATIONS:")
        print("1. ✅ System is ready for capital deployment")
        print("2. ✅ Proceed with live trading under current parameters")
        print("3. ✅ Monitor performance but DO NOT optimize")
        print("4. ✅ Use this validation as baseline for future assessments")
        
        print("\nNEXT STEPS:")
        print("- Deploy system with current configuration")
        print("- Establish monitoring and reporting procedures")
        print("- Set up regular validation cycles (quarterly)")
        print("- Document operational procedures")
        
    elif status == 'FAIL':
        print("❌ SYSTEM FAILS INSTITUTIONAL VALIDATION")
        print("\nISSUES IDENTIFIED:")
        
        behavior_validation = results.get('behavior_validation', {})
        for check, passed in behavior_validation.items():
            icon = "✅" if passed else "❌"
            print(f"   {icon} {check}")
        
        print("\nRECOMMENDATIONS:")
        print("1. ❌ DO NOT deploy system for live trading")
        print("2. 🔧 Address fundamental issues (not parameter tuning)")
        print("3. 🔍 Review system architecture and risk management")
        print("4. 🧪 Re-run validation after structural improvements")
        
        print("\nNEXT STEPS:")
        print("- Analyze failure modes in detail")
        print("- Improve system architecture (not parameters)")
        print("- Enhance risk management if needed")
        print("- Re-validate after improvements")
        
    else:
        print("⚠️ VALIDATION STATUS UNKNOWN")
        print("Manual review required")
    
    print("\n" + "=" * 80)
    print("CRITICAL REMINDER:")
    print("This validation is the SINGLE SOURCE OF TRUTH")
    print("Do NOT re-run with different parameters")
    print("Do NOT cherry-pick results")
    print("The system either passes or fails - there is no middle ground")
    print("=" * 80)

def main():
    """Main execution function"""
    
    print("🏛️ INSTITUTIONAL 12-MONTH VALIDATION SYSTEM")
    print("=" * 80)
    print("This is the rigorous test that separates toys from funds")
    print("All parameters will be FROZEN - no optimization allowed")
    print("Results will be cryptographically sealed")
    print("=" * 80)
    
    # Step 1: Check system readiness
    ready, checks = check_system_readiness()
    if not ready:
        print("\n❌ System not ready for validation")
        print("Fix the issues above and try again")
        return 1
    
    # Step 2: Run validation
    success, results = run_validation()
    if not success:
        print("\n❌ Validation execution failed")
        return 1
    
    # Step 3: Generate report
    report_file = generate_report(results)
    
    # Step 4: Provide final assessment
    provide_final_assessment(results, report_file)
    
    print(f"\n🏛️ Institutional validation complete")
    print(f"Results sealed and tamper-proof")
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)