#!/usr/bin/env python3
"""
🔄 UPDATE ALL SYSTEMS - NORTHSTAR V3
Complete system update pipeline

This script runs all components in the correct order:
1. Market data collection
2. Market state computation
3. Intelligence system
4. Portfolio construction
5. System validation
"""

import sys
import os
import subprocess
from datetime import datetime

def run_command(command, description, timeout=300):
    """Run a command with proper error handling"""
    
    print(f"🔄 {description}...")
    
    try:
        result = subprocess.run(
            [sys.executable] + command.split()[1:] if command.startswith('python') else command.split(),
            capture_output=True, 
            text=True, 
            timeout=timeout
        )
        
        if result.returncode == 0:
            print(f"   ✅ {description} completed")
            return True
        else:
            print(f"   ❌ {description} failed")
            if result.stderr:
                print(f"   Error: {result.stderr[:200]}...")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"   ⏰ {description} timed out")
        return False
    except Exception as e:
        print(f"   ❌ {description} error: {e}")
        return False

def check_file_exists(filepath, description):
    """Check if a file exists and report"""
    
    if os.path.exists(filepath):
        try:
            # Try to get file size and modification time
            stat = os.stat(filepath)
            size_mb = stat.st_size / (1024 * 1024)
            mod_time = datetime.fromtimestamp(stat.st_mtime)
            print(f"   ✅ {description}: {size_mb:.1f}MB, modified {mod_time.strftime('%H:%M:%S')}")
            return True
        except:
            print(f"   ✅ {description}: exists")
            return True
    else:
        print(f"   ❌ {description}: missing")
        return False

def main():
    """Run complete system update"""
    
    print("🔄 NORTHSTAR V3 - COMPLETE SYSTEM UPDATE")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    success_count = 0
    total_steps = 6  # Updated to reflect the enhanced integration
    
    # Step 1: Update market data
    print("📊 STEP 1: MARKET DATA COLLECTION")
    print("-" * 40)
    
    if run_command("python eod_options_pipeline.py", "Market data collection", 300):
        success_count += 1
    
    # Check market data files
    market_files = [
        ('data/options/live/market_data_latest.json', 'Live market data'),
        ('data/processed/scores.parquet', 'Stock scores'),
    ]
    
    for filepath, desc in market_files:
        check_file_exists(filepath, desc)
    
    print()
    
    # Step 2: Update market state
    print("🧠 STEP 2: MARKET STATE COMPUTATION")
    print("-" * 40)
    
    if run_command("python run_intelligent_market_state.py", "Intelligent market state", 180):
        success_count += 1
    
    # Step 2.5: Update market brain (NEW!)
    print("\n🧠 STEP 2.5: MARKET BRAIN INTELLIGENCE")
    print("-" * 40)
    
    # Run market brain production system (quick update)
    if run_command("python run_market_brain_production.py --quick", "Market brain quick update", 120):
        print("   ✅ Market brain updated successfully")
        success_count += 0.5  # Half point for brain update
    else:
        print("   ⚠️ Market brain update failed, continuing...")
    
    # Check market state files
    state_files = [
        ('data/processed/market_state.parquet', 'Market state'),
        ('data/processed/intelligent_market_state.parquet', 'Intelligent market state'),
    ]
    
    for filepath, desc in state_files:
        check_file_exists(filepath, desc)
    
    print()
    
    # Step 3: Complete System Integration (NEW!)
    print("🧬 STEP 3: COMPLETE SYSTEM INTEGRATION")
    print("-" * 40)
    
    try:
        from src.orchestrator.system_orchestrator import SystemOrchestrator
        
        orchestrator = SystemOrchestrator()
        integration_success = orchestrator.run_complete_system()
        
        if integration_success:
            print("   ✅ Complete system integration successful")
            success_count += 1
        else:
            print("   ⚠️ System integration partially successful")
            success_count += 0.5  # Partial credit
            
    except Exception as e:
        print(f"   ❌ System integration error: {e}")
        print("   🔄 Falling back to individual components...")
        
        # Fallback to opportunity surface only
        try:
            from src.processing.opportunity_surface import main as run_opportunity
            run_opportunity()
            print("   ✅ Opportunity surface updated (fallback)")
            success_count += 0.5
        except Exception as e2:
            print(f"   ❌ Opportunity surface fallback error: {e2}")
    
    # Check integration outputs
    integration_files = [
        ('data/processed/opportunity_surface.parquet', 'Opportunity surface'),
        ('data/processed/strategy_portfolios', 'Strategy portfolios directory'),
        ('data/processed/backtests', 'Backtest results directory'),
        ('data/processed/capital_allocations.json', 'Capital allocations'),
        ('data/processed/performance/master.parquet', 'Performance master file'),
    ]
    
    for filepath, desc in integration_files:
        if os.path.isdir(filepath):
            if os.path.exists(filepath):
                file_count = len([f for f in os.listdir(filepath) if f.endswith('.parquet')])
                print(f"   ✅ {desc}: {file_count} files")
            else:
                print(f"   ❌ {desc}: missing")
        else:
            check_file_exists(filepath, desc)
    
    print()
    
    # Step 4: Update portfolio (Enhanced)
    print("🎯 STEP 4: PORTFOLIO CONSTRUCTION")
    print("-" * 40)
    
    if run_command("python run_portfolio_governor.py", "Portfolio construction", 120):
        success_count += 1
    
    # Check portfolio files
    portfolio_files = [
        ('data/processed/portfolio_weights.parquet', 'Portfolio weights'),
        ('data/processed/portfolio_analytics.json', 'Portfolio analytics'),
    ]
    
    for filepath, desc in portfolio_files:
        check_file_exists(filepath, desc)
    
    print()
    
    # Step 5: Validate trading desk data
    print("🧭 STEP 5: TRADING DESK VALIDATION")
    print("-" * 40)
    
    try:
        # Test trading desk data loading
        
        from northstar_trading_desk import load_trading_desk_state
        
        state = load_trading_desk_state()
        
        # Validate key components
        command_bar = state.get('command_bar', {})
        portfolio_brain = state.get('position_plane', {}).get('portfolio_brain', {})
        
        print(f"   ✅ Command bar loaded: {len(command_bar)} metrics")
        print(f"   ✅ Portfolio loaded: {portfolio_brain.get('total_positions', 0)} positions")
        print(f"   ✅ Exposure: {command_bar.get('exposure', 0):.1f}%")
        print(f"   ✅ AI Status: {'Active' if command_bar.get('ai_active') else 'Inactive'}")
        
        success_count += 1
        
    except Exception as e:
        print(f"   ❌ Trading desk validation error: {e}")
    
    print()
    
    # Step 6: System health check
    print("🔍 STEP 6: SYSTEM HEALTH CHECK")
    print("-" * 40)
    
    try:
        # Check data freshness
        import pandas as pd
        
        # Check market state age
        if os.path.exists('data/processed/market_state.parquet'):
            market_df = pd.read_parquet('data/processed/market_state.parquet')
            if not market_df.empty:
                latest_date = pd.to_datetime(market_df['date'].iloc[-1])
                age_hours = (datetime.now() - latest_date).total_seconds() / 3600
                print(f"   📊 Market state age: {age_hours:.1f} hours")
        
        # Check portfolio analytics
        if os.path.exists('data/processed/portfolio_analytics.json'):
            import json
            with open('data/processed/portfolio_analytics.json', 'r') as f:
                analytics = json.load(f)
                
                summary = analytics.get('portfolio_summary', {})
                compliance = analytics.get('compliance_check', {})
                
                print(f"   🎯 Portfolio positions: {summary.get('total_positions', 0)}")
                print(f"   🎯 Portfolio exposure: {summary.get('total_exposure', 0):.1%}")
                print(f"   🎯 Compliance: {'✅' if compliance.get('all_compliant') else '❌'}")
        
        success_count += 1
        
    except Exception as e:
        print(f"   ❌ Health check error: {e}")
    
    print()
    
    # Final summary
    print("📋 SYSTEM UPDATE SUMMARY")
    print("=" * 40)
    print(f"Completed: {success_count}/{total_steps} steps")
    print(f"Success rate: {success_count/total_steps:.1%}")
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if success_count == total_steps:
        print("\n🎉 ALL SYSTEMS OPERATIONAL")
        print("🧭 Ready to launch trading desk!")
        return True
    else:
        print(f"\n⚠️ {total_steps - success_count} SYSTEMS NEED ATTENTION")
        print("🔧 Check errors above and retry")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)