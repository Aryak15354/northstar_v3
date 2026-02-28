#!/usr/bin/env python3
"""
🧭 NORTHSTAR V3 - UNIFIED ENTRY POINT
Single entry point for all Northstar V3 operations

This replaces 8 separate entry points with one unified launcher that coordinates
all subsystems through the Master Orchestrator.

Usage:
    python northstar_v3_unified.py --mode dashboard --dashboard unified
    python northstar_v3_unified.py --mode update --quick
    python northstar_v3_unified.py --mode live
    python northstar_v3_unified.py --mode backtest --strategy momentum
    
Modes:
    - dashboard: Launch unified terminal (default)
    - update: Run system update
    - live: Run live trading mode
    - backtest: Run backtesting mode
    
Dashboard Types:
    - unified: New unified terminal (default)
    - trading-desk: Bloomberg-style interface
    - professional: Intelligence-focused interface
    - intelligence: 4-plane command center
    - react: React-based terminal
"""

from src.cohesion.dependency_container import get_dependency_container

import argparse
import sys
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

def main():
    """Main entry point for Northstar V3 unified system"""
    
    parser = argparse.ArgumentParser(
        description='Northstar V3 Unified Investment Operating System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python northstar_v3_unified.py                                    # Launch unified dashboard
  python northstar_v3_unified.py --mode update                      # Full system update
  python northstar_v3_unified.py --mode update --quick              # Quick update
  python northstar_v3_unified.py --mode dashboard --dashboard trading-desk
  python northstar_v3_unified.py --mode live                        # Live trading mode
  python northstar_v3_unified.py --mode backtest --strategy momentum
        """
    )
    
    parser.add_argument('--mode', 
                       choices=['dashboard', 'update', 'live', 'backtest'], 
                       default='dashboard', 
                       help='Operation mode (default: dashboard)')
    
    parser.add_argument('--dashboard', 
                       choices=['unified', 'trading-desk', 'professional', 'intelligence', 'react'],
                       default='unified', 
                       help='Dashboard type (default: unified)')
    
    parser.add_argument('--quick', 
                       action='store_true', 
                       help='Quick update (skip full brain computation)')
    
    parser.add_argument('--strategy', 
                       type=str, 
                       help='Strategy name for backtesting')
    
    parser.add_argument('--verbose', '-v', 
                       action='store_true', 
                       help='Verbose output')
    
    args = parser.parse_args()
    
    # Print startup banner
    print_startup_banner(args)
    
    try:
        # Initialize Master Orchestrator
        from src.orchestrator.master_orchestrator import MasterOrchestrator
        
        orchestrator = MasterOrchestrator(verbose=args.verbose)
        
        # Execute based on mode
        if args.mode == 'dashboard':
            success = orchestrator.run_dashboard(args.dashboard)
        elif args.mode == 'update':
            success = orchestrator.run_system_update(quick=args.quick)
        elif args.mode == 'live':
            success = orchestrator.run_live_trading()
        elif args.mode == 'backtest':
            success = orchestrator.run_backtest(strategy=args.strategy)
        else:
            print(f"❌ Unknown mode: {args.mode}")
            return False
        
        if success:
            print(f"\n🎉 Northstar V3 {args.mode} completed successfully!")
            return True
        else:
            print(f"\n⚠️ Northstar V3 {args.mode} completed with issues")
            return False
            
    except ImportError as e:
        print(f"❌ Failed to import Master Orchestrator: {e}")
        print("🔧 Running in fallback mode...")
        return run_fallback_mode(args)
    except Exception as e:
        print(f"❌ Northstar V3 execution failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return False

def print_startup_banner(args):
    """Print startup banner with system information"""
    
    print("🧭 NORTHSTAR V3 - UNIFIED INVESTMENT OPERATING SYSTEM")
    print("=" * 70)
    print(f"Mode: {args.mode.title()}")
    if args.mode == 'dashboard':
        print(f"Dashboard: {args.dashboard.title()}")
    if args.quick:
        print("Update Type: Quick")
    if args.strategy:
        print(f"Strategy: {args.strategy}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()

def run_fallback_mode(args):
    """Run in fallback mode if Master Orchestrator is not available"""
    
    print("🔄 FALLBACK MODE - Using existing entry points")
    print("-" * 50)
    
    try:
        if args.mode == 'dashboard':
            return run_fallback_dashboard(args.dashboard)
        elif args.mode == 'update':
            return run_fallback_update(args.quick)
        elif args.mode == 'live':
            print("❌ Live trading mode requires Master Orchestrator")
            return False
        elif args.mode == 'backtest':
            print("❌ Backtest mode requires Master Orchestrator")
            return False
        else:
            print(f"❌ Unknown mode: {args.mode}")
            return False
            
    except Exception as e:
        print(f"❌ Fallback mode failed: {e}")
        return False

def run_fallback_dashboard(dashboard_type):
    """Run dashboard in fallback mode"""
    
    print(f"🖥️ Launching {dashboard_type} dashboard...")
    
    try:
        if dashboard_type == 'unified':
            # Try to launch unified terminal
            # Dependency injection - import UnifiedTerminal from src.dashboard.unified_terminal
# print("⚠️ Unified terminal not available, falling back to professional dashboard")
                dashboard_type = 'professional'
        
        if dashboard_type == 'trading-desk':
            import subprocess
            subprocess.run([sys.executable, 'scripts/northstar_trading_desk.py'])
            return True
        elif dashboard_type == 'professional':
            import subprocess
            subprocess.run([sys.executable, 'scripts/northstar_professional.py'])
            return True
        elif dashboard_type == 'intelligence':
            import subprocess
            subprocess.run([sys.executable, 'scripts/northstar_intelligence_organism.py'])
            return True
        elif dashboard_type == 'react':
            import subprocess
            subprocess.run([sys.executable, 'scripts/launchers/launch_northstar_terminal.py'])
            return True
        else:
            print(f"❌ Unknown dashboard type: {dashboard_type}")
            return False
            
    except Exception as e:
        print(f"❌ Dashboard launch failed: {e}")
        return False

def run_fallback_update(quick=False):
    """Run system update in fallback mode"""
    
    print("🔄 Running system update...")
    
    try:
        import subprocess
        
        if quick:
            # Quick update - just run market brain
            result = subprocess.run([sys.executable, 'run_market_brain_production.py'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Quick update completed")
                return True
            else:
                print(f"❌ Quick update failed: {result.stderr}")
                return False
        else:
            # Full update
            result = subprocess.run([sys.executable, 'update_all_systems.py'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Full update completed")
                return True
            else:
                print(f"❌ Full update failed: {result.stderr}")
                return False
                
    except Exception as e:
        print(f"❌ Update failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)