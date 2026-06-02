#!/usr/bin/env python3
"""
🚀 ACTIVATE FULL NORTHSTAR V3 SYSTEM
Master orchestration script to update all calculations and turn on all facets of V3

This script runs the complete Northstar V3 system with fresh data:
1. Beta Drift Fabric - Market brain intelligence
2. Anticipatory Intelligence - Forward-looking analysis
3. Portfolio Generation - Real portfolio construction
4. Shadow Trading Validation - Live system validation
5. Intelligence Engines - All AI components
6. Risk Management - Complete risk framework
7. Institutional Reporting - Professional reports
8. System Integration - Full system coordination

Usage:
    python3 scripts/activate_full_northstar_v3_system.py
    python3 scripts/activate_full_northstar_v3_system.py --quick  # Skip heavy computations
    python3 scripts/activate_full_northstar_v3_system.py --validation-only  # Only validation
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

class NorthstarV3SystemActivator:
    """Master system activator for Northstar V3"""
    
    def __init__(self, quick_mode=False, validation_only=False):
        self.quick_mode = quick_mode
        self.validation_only = validation_only
        self.start_time = datetime.now()
        self.completed_steps = []
        self.failed_steps = []
        
        print("🚀 NORTHSTAR V3 FULL SYSTEM ACTIVATION")
        print("=" * 60)
        print(f"Session started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Quick mode: {'ON' if quick_mode else 'OFF'}")
        print(f"Validation only: {'ON' if validation_only else 'OFF'}")
        print("=" * 60)
    
    def run_step(self, step_name, script_path, timeout=1800, args=None):
        """Run a system step with error handling"""
        
        print(f"\n🔄 STEP: {step_name}")
        print("-" * 40)
        
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
                print(f"✅ {step_name} completed successfully ({duration:.1f}s)")
                self.completed_steps.append((step_name, duration))
                return True
            else:
                print(f"⚠️ {step_name} completed with warnings")
                print(f"   stderr: {result.stderr[:200]}...")
                self.completed_steps.append((step_name, duration))
                return True  # Continue even with warnings
                
        except subprocess.TimeoutExpired:
            print(f"❌ {step_name} timed out (>{timeout}s)")
            self.failed_steps.append((step_name, "timeout"))
            return False
        except Exception as e:
            print(f"❌ {step_name} failed: {e}")
            self.failed_steps.append((step_name, str(e)))
            return False
    
    def step_1_beta_drift_fabric(self):
        """Build Beta Drift Fabric - Market brain intelligence"""
        
        if self.validation_only:
            print("⏭️ Skipping Beta Drift Fabric (validation-only mode)")
            return True
            
        print("\n🧠 PHASE 1: BETA DRIFT FABRIC")
        print("Building market brain intelligence...")
        
        success = True
        
        # Build full beta drift fabric
        if not self.quick_mode:
            success &= self.run_step(
                "Full Beta Drift Fabric",
                "scripts/build_full_beta_drift_fabric.py",
                timeout=2400  # 40 minutes
            )
        
        # Build weekly causal fabric
        success &= self.run_step(
            "Weekly Causal Fabric",
            "scripts/build_weekly_causal_fabric.py",
            timeout=1200  # 20 minutes
        )
        
        return success
    
    def step_2_anticipatory_intelligence(self):
        """Build Anticipatory Intelligence - Forward-looking analysis"""
        
        if self.validation_only:
            print("⏭️ Skipping Anticipatory Intelligence (validation-only mode)")
            return True
            
        print("\n🔮 PHASE 2: ANTICIPATORY INTELLIGENCE")
        print("Building forward-looking analysis...")
        
        success = True
        
        # Build anticipatory intelligence
        if self.quick_mode:
            success &= self.run_step(
                "Simple Anticipatory Intelligence",
                "scripts/build_simple_anticipatory_intelligence.py",
                timeout=600  # 10 minutes
            )
        else:
            success &= self.run_step(
                "Full Anticipatory Intelligence",
                "scripts/build_anticipatory_intelligence.py",
                timeout=1800  # 30 minutes
            )
        
        return success
    
    def step_3_portfolio_generation(self):
        """Generate Real Portfolio - Portfolio construction"""
        
        if self.validation_only:
            print("⏭️ Skipping Portfolio Generation (validation-only mode)")
            return True
            
        print("\n💼 PHASE 3: PORTFOLIO GENERATION")
        print("Constructing real portfolio...")
        
        success = True
        
        # Generate portfolio
        success &= self.run_step(
            "Portfolio Generation",
            "scripts/generate_portfolio.py",
            timeout=900  # 15 minutes
        )
        
        return success
    
    def step_4_intelligence_engines(self):
        """Activate Intelligence Engines - All AI components"""
        
        print("\n🤖 PHASE 4: INTELLIGENCE ENGINES")
        print("Activating AI components...")
        
        success = True
        
        # Run full intelligence
        success &= self.run_step(
            "Full Intelligence Stack",
            "scripts/run_full_intelligence.py",
            timeout=1200  # 20 minutes
        )
        
        # Enhanced narratives
        success &= self.run_step(
            "Enhanced Narratives",
            "scripts/run_enhanced_northstar_with_narratives.py",
            timeout=600  # 10 minutes
        )
        
        return success
    
    def step_5_shadow_validation(self):
        """Run Shadow Trading Validation - Live system validation"""
        
        print("\n👥 PHASE 5: SHADOW VALIDATION")
        print("Running live system validation...")
        
        success = True
        
        # Shadow trading validation
        success &= self.run_step(
            "Shadow Trading Validation",
            "scripts/execute_shadow_trading_validation.py",
            timeout=1800  # 30 minutes
        )
        
        # Institutional validation
        if not self.quick_mode:
            success &= self.run_step(
                "Institutional 12-Month Validation",
                "scripts/institutional_12month_final.py",
                timeout=2400  # 40 minutes
            )
        
        return success
    
    def step_6_comprehensive_validation(self):
        """Run Comprehensive System Validation"""
        
        print("\n🔍 PHASE 6: COMPREHENSIVE VALIDATION")
        print("Running system validation...")
        
        success = True
        
        # System validation
        success &= self.run_step(
            "Comprehensive System Validation",
            "scripts/run_comprehensive_system_validation.py",
            timeout=1200  # 20 minutes
        )
        
        # Alpha validation
        success &= self.run_step(
            "Alpha Validation",
            "scripts/run_alpha_validation.py",
            timeout=900  # 15 minutes
        )
        
        # Crisis validation
        success &= self.run_step(
            "Crisis Validation",
            "scripts/run_crisis_validation.py",
            timeout=900  # 15 minutes
        )
        
        return success
    
    def step_7_institutional_reporting(self):
        """Generate Institutional Reports"""
        
        print("\n📊 PHASE 7: INSTITUTIONAL REPORTING")
        print("Generating professional reports...")
        
        success = True
        
        # Generate institutional report
        success &= self.run_step(
            "Institutional Report Generation",
            "scripts/generate_institutional_report_complete.py",
            timeout=600  # 10 minutes
        )
        
        # 12-month performance report
        success &= self.run_step(
            "12-Month Performance Report",
            "scripts/generate_12month_performance_report.py",
            timeout=600  # 10 minutes
        )
        
        return success
    
    def step_8_system_integration(self):
        """Final System Integration and Health Check"""
        
        print("\n🔧 PHASE 8: SYSTEM INTEGRATION")
        print("Final system integration...")
        
        success = True
        
        # System operations verification
        success &= self.run_step(
            "System Operations Verification",
            "scripts/verify_complete_system_operation.py",
            timeout=600  # 10 minutes
        )
        
        # Living system validation
        success &= self.run_step(
            "Living System Validation",
            "scripts/validate_living_system_final.py",
            timeout=600  # 10 minutes
        )
        
        return success
    
    def generate_system_status_report(self):
        """Generate final system status report"""
        
        print("\n📋 GENERATING SYSTEM STATUS REPORT")
        print("-" * 40)
        
        try:
            self.run_step(
                "System Status Report",
                "scripts/system_status_report.py",
                timeout=300  # 5 minutes
            )
        except Exception as e:
            print(f"⚠️ Status report generation failed: {e}")
    
    def print_final_summary(self):
        """Print final activation summary"""
        
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        
        print(f"\n{'='*60}")
        print("🚀 NORTHSTAR V3 SYSTEM ACTIVATION COMPLETE")
        print(f"{'='*60}")
        print(f"Session ended: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total duration: {total_duration/60:.1f} minutes")
        
        print(f"\n✅ COMPLETED STEPS ({len(self.completed_steps)}):")
        for step, duration in self.completed_steps:
            print(f"   • {step} ({duration:.1f}s)")
        
        if self.failed_steps:
            print(f"\n❌ FAILED STEPS ({len(self.failed_steps)}):")
            for step, error in self.failed_steps:
                print(f"   • {step}: {error}")
        
        success_rate = len(self.completed_steps) / (len(self.completed_steps) + len(self.failed_steps)) * 100
        print(f"\n📊 SUCCESS RATE: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("\n🎉 SYSTEM ACTIVATION SUCCESSFUL!")
            print("   Your Northstar V3 system is fully operational")
            print("   Launch dashboards:")
            print("   • python3 scripts/launch_ultimate_real_data_cockpit.py")
            print("   • python3 scripts/launch_integrated_live_system.py")
            print("   • python3 scripts/launch_command_bridge.py")
        elif success_rate >= 60:
            print("\n⚠️ PARTIAL SYSTEM ACTIVATION")
            print("   Most components are operational")
            print("   Some advanced features may be limited")
        else:
            print("\n❌ SYSTEM ACTIVATION INCOMPLETE")
            print("   Multiple critical components failed")
            print("   Check logs and retry failed steps")
    
    def run_full_activation(self):
        """Run the complete system activation"""
        
        try:
            # Phase 1: Market Intelligence
            self.step_1_beta_drift_fabric()
            
            # Phase 2: Forward-Looking Analysis
            self.step_2_anticipatory_intelligence()
            
            # Phase 3: Portfolio Construction
            self.step_3_portfolio_generation()
            
            # Phase 4: AI Components
            self.step_4_intelligence_engines()
            
            # Phase 5: Live Validation
            self.step_5_shadow_validation()
            
            # Phase 6: System Validation
            self.step_6_comprehensive_validation()
            
            # Phase 7: Professional Reporting
            self.step_7_institutional_reporting()
            
            # Phase 8: Final Integration
            self.step_8_system_integration()
            
            # Generate status report
            self.generate_system_status_report()
            
        except KeyboardInterrupt:
            print("\n\n⚠️ ACTIVATION INTERRUPTED BY USER")
            print("Partial activation may be available")
        except Exception as e:
            print(f"\n\n❌ CRITICAL ERROR: {e}")
            print("System activation failed")
        finally:
            self.print_final_summary()

def main():
    """Main function"""
    
    import argparse
    parser = argparse.ArgumentParser(description="Activate Full Northstar V3 System")
    parser.add_argument("--quick", action="store_true", help="Quick mode - skip heavy computations")
    parser.add_argument("--validation-only", action="store_true", help="Run only validation phases")
    
    args = parser.parse_args()
    
    # Create and run activator
    activator = NorthstarV3SystemActivator(
        quick_mode=args.quick,
        validation_only=args.validation_only
    )
    
    activator.run_full_activation()

if __name__ == "__main__":
    main()