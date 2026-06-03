#!/usr/bin/env python3
"""
🧬 SYSTEM ORCHESTRATOR - COMPLETE NORTHSTAR V3 SPINE
The Master Controller that makes all components talk to each other

This is the spine that transforms Northstar from "many good scripts" 
into "one coherent hedge fund operating system."

The orchestrator runs:
1. Strategy generation and persistence
2. Backtesting of all strategies
3. Capital allocation across strategies
4. Portfolio construction with strategy blending
5. System validation and health checks

Usage:
    from src.orchestrator.system_orchestrator import SystemOrchestrator
    
    orchestrator = SystemOrchestrator()
    orchestrator.run_complete_system()
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class SystemOrchestrator:
    """
    Complete System Orchestrator for Northstar V3
    
    This is the master controller that coordinates all components
    to create a self-learning, adaptive hedge fund system.
    """
    
    def __init__(self):
        self.name = "Northstar System Orchestrator"
        self.version = "3.0"
        
        # Component status tracking
        self.component_status = {
            'strategies': False,
            'backtests': False,
            'strategy_intelligence': False,  # NEW!
            'portfolio_construction': False,
            'system_validation': False
        }
        
        # Performance tracking
        self.execution_log = []
        
    def log_execution(self, component, status, message="", duration=0):
        """Log component execution"""
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'component': component,
            'status': status,
            'message': message,
            'duration_seconds': duration
        }
        
        self.execution_log.append(entry)
        
        # Update component status
        if component in self.component_status:
            self.component_status[component] = (status == 'success')
    
    def run_strategy_generation(self):
        """Step 1: Generate and save all strategy portfolios"""
        
        print("🧪 STEP 1: STRATEGY GENERATION")
        print("=" * 50)
        
        start_time = datetime.now()
        
        try:
            # Import and run strategy generation
            from src.portfolio.strategies import generate_all_strategies
            
            results = generate_all_strategies()
            
            # Validate results
            successful_strategies = len([k for k, v in results.items() if not v.empty])
            
            if successful_strategies > 0:
                duration = (datetime.now() - start_time).total_seconds()
                self.log_execution('strategies', 'success', 
                                 f"Generated {successful_strategies} strategies", duration)
                print(f"✅ Strategy generation completed: {successful_strategies} strategies")
                return True
            else:
                self.log_execution('strategies', 'failed', "No strategies generated")
                print("❌ Strategy generation failed: No strategies generated")
                return False
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution('strategies', 'failed', str(e), duration)
            print(f"❌ Strategy generation failed: {e}")
            return False
    
    def run_backtesting(self):
        """Step 2: Run comprehensive backtests for all strategies"""
        
        print("\n🧪 STEP 2: STRATEGY BACKTESTING")
        print("=" * 50)
        
        start_time = datetime.now()
        
        try:
            # Import and run backtest engine
            from src.backtesting.backtest_engine import BacktestEngine
            
            engine = BacktestEngine()
            summaries = engine.run_all_strategies()
            
            if summaries:
                duration = (datetime.now() - start_time).total_seconds()
                self.log_execution('backtests', 'success', 
                                 f"Backtested {len(summaries)} strategies", duration)
                print(f"✅ Backtesting completed: {len(summaries)} strategies")
                return True
            else:
                self.log_execution('backtests', 'failed', "No backtest results")
                print("❌ Backtesting failed: No results generated")
                return False
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution('backtests', 'failed', str(e), duration)
            print(f"❌ Backtesting failed: {e}")
            return False
    
    def run_portfolio_construction(self):
        """Step 4: Construct final portfolio using strategy blending"""
        
        print("\n🎯 STEP 4: PORTFOLIO CONSTRUCTION")
        print("=" * 50)
        
        start_time = datetime.now()
        
        try:
            # Import and run portfolio governor
            from src.portfolio.portfolio_governor import PortfolioGovernor
            
            governor = PortfolioGovernor()
            portfolio, analytics = governor.run_portfolio_construction()
            
            if not portfolio.empty:
                duration = (datetime.now() - start_time).total_seconds()
                n_positions = len(portfolio)
                total_exposure = analytics.get('portfolio_summary', {}).get('total_exposure', 0)
                
                self.log_execution('portfolio_construction', 'success', 
                                 f"Constructed portfolio: {n_positions} positions, {total_exposure:.1%} exposure", 
                                 duration)
                print(f"✅ Portfolio construction completed: {n_positions} positions")
                return True
            else:
                self.log_execution('portfolio_construction', 'failed', "Empty portfolio generated")
                print("❌ Portfolio construction failed: Empty portfolio")
                return False
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution('portfolio_construction', 'failed', str(e), duration)
            print(f"❌ Portfolio construction failed: {e}")
            return False
    
    def run_system_validation(self):
        """Step 5: Validate complete system health"""
        
        print("\n🔍 STEP 5: SYSTEM VALIDATION")
        print("=" * 50)
        
        start_time = datetime.now()
        
        try:
            validation_results = {}
            
            # Check strategy portfolios
            strategy_dir = 'data/processed/strategy_portfolios'
            if os.path.exists(strategy_dir):
                strategy_files = [f for f in os.listdir(strategy_dir) if f.endswith('.parquet')]
                validation_results['strategy_portfolios'] = len(strategy_files)
            else:
                validation_results['strategy_portfolios'] = 0
            
            # Check backtest results
            backtest_dir = 'data/processed/backtests'
            if os.path.exists(backtest_dir):
                backtest_files = [f for f in os.listdir(backtest_dir) if f.endswith('.parquet')]
                validation_results['backtest_results'] = len(backtest_files)
            else:
                validation_results['backtest_results'] = 0
            
            # Check capital allocations
            alloc_file = 'data/processed/capital_allocations.json'
            if os.path.exists(alloc_file):
                with open(alloc_file, 'r') as f:
                    alloc_data = json.load(f)
                    validation_results['capital_allocations'] = len(alloc_data.get('allocations', {}))
            else:
                validation_results['capital_allocations'] = 0
            
            # Check final portfolio
            portfolio_file = 'data/processed/portfolio_weights.parquet'
            if os.path.exists(portfolio_file):
                portfolio_df = pd.read_parquet(portfolio_file)
                validation_results['portfolio_positions'] = len(portfolio_df)
            else:
                validation_results['portfolio_positions'] = 0
            
            # Check performance master file
            perf_file = 'data/processed/performance/master.parquet'
            if os.path.exists(perf_file):
                perf_df = pd.read_parquet(perf_file)
                validation_results['performance_records'] = len(perf_df)
            else:
                validation_results['performance_records'] = 0
            
            # Validate system coherence
            all_valid = all([
                validation_results['strategy_portfolios'] > 0,
                validation_results['backtest_results'] > 0,
                validation_results['capital_allocations'] > 0,
                validation_results['portfolio_positions'] > 0
            ])
            
            duration = (datetime.now() - start_time).total_seconds()
            
            if all_valid:
                self.log_execution('system_validation', 'success', 
                                 f"System coherent: {validation_results}", duration)
                print("✅ System validation passed: All components coherent")
                
                # Print validation summary
                print(f"   📊 Strategy portfolios: {validation_results['strategy_portfolios']}")
                print(f"   📊 Backtest results: {validation_results['backtest_results']}")
                print(f"   📊 Capital allocations: {validation_results['capital_allocations']}")
                print(f"   📊 Portfolio positions: {validation_results['portfolio_positions']}")
                print(f"   📊 Performance records: {validation_results['performance_records']}")
                
                return True
            else:
                self.log_execution('system_validation', 'failed', 
                                 f"System incomplete: {validation_results}", duration)
                print("❌ System validation failed: Missing components")
                return False
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution('system_validation', 'failed', str(e), duration)
            print(f"❌ System validation failed: {e}")
            return False
    
    def save_execution_log(self):
        """Save execution log for analysis"""
        
        log_file = 'data/processed/system_execution_log.json'
        
        execution_summary = {
            'timestamp': datetime.now().isoformat(),
            'system_version': self.version,
            'component_status': self.component_status,
            'execution_log': self.execution_log,
            'total_duration': sum(entry['duration_seconds'] for entry in self.execution_log),
            'success_rate': sum(1 for status in self.component_status.values() if status) / len(self.component_status)
        }
        
        with open(log_file, 'w') as f:
            json.dump(execution_summary, f, indent=2, default=str)
        
        print(f"\n📋 Execution log saved: {log_file}")
    
    def run_complete_system(self):
        """Run the complete integrated system with strategy intelligence"""
        
        print("🧬 NORTHSTAR V3 COMPLETE SYSTEM ORCHESTRATOR")
        print("=" * 70)
        print("Transforming from 'many good scripts' to 'one coherent hedge fund'")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Track overall execution
        system_start = datetime.now()
        
        # Run all components in sequence (ENHANCED WITH INTELLIGENCE)
        steps = [
            ('Strategy Generation', self.run_strategy_generation),
            ('Backtesting', self.run_backtesting),
            ('Strategy Intelligence', self.run_strategy_intelligence),  # NEW!
            ('Portfolio Construction', self.run_portfolio_construction),
            ('System Validation', self.run_system_validation)
        ]
        
        successful_steps = 0
        
        for step_name, step_function in steps:
            success = step_function()
            if success:
                successful_steps += 1
            else:
                print(f"\n⚠️ {step_name} failed - continuing with remaining steps...")
        
        # Calculate overall results
        total_duration = (datetime.now() - system_start).total_seconds()
        success_rate = successful_steps / len(steps)
        
        # Save execution log
        self.save_execution_log()
        
        # Print final summary
        print(f"\n🎯 SYSTEM ORCHESTRATION COMPLETE")
        print("=" * 70)
        print(f"⏱️  Total Duration: {total_duration:.1f} seconds")
        print(f"✅ Success Rate: {success_rate:.1%} ({successful_steps}/{len(steps)} steps)")
        print(f"🧬 Component Status:")
        
        for component, status in self.component_status.items():
            status_icon = "✅" if status else "❌"
            print(f"   {status_icon} {component.replace('_', ' ').title()}")
        
        if success_rate >= 0.8:
            print(f"\n🎉 NORTHSTAR V3 IS NOW A LEARNING FINANCIAL ORGANISM!")
            print("   The spine is complete - strategies compete for capital,")
            print("   beliefs drive allocation, regret punishes failure,")
            print("   and the system learns and evolves.")
        else:
            print(f"\n⚠️ System partially operational - some components need attention")
        
        return success_rate >= 0.8
    
    def run_strategy_intelligence(self):
        """Step 3: Run complete strategy intelligence pipeline (NEW!)"""
        
        print("\n🧬 STEP 3: STRATEGY INTELLIGENCE PIPELINE")
        print("=" * 50)
        
        start_time = datetime.now()
        
        try:
            from src.intelligence.strategy_intelligence import StrategyIntelligence
            
            intelligence = StrategyIntelligence()
            success = intelligence.run_complete_intelligence()
            
            if success:
                duration = (datetime.now() - start_time).total_seconds()
                self.log_execution('strategy_intelligence', 'success', 
                                 "Complete intelligence pipeline operational", duration)
                print("✅ Strategy intelligence completed successfully")
                return True
            else:
                self.log_execution('strategy_intelligence', 'failed', "Intelligence pipeline degraded")
                print("⚠️ Strategy intelligence partially successful")
                return False
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution('strategy_intelligence', 'failed', str(e), duration)
            print(f"❌ Strategy intelligence failed: {e}")
            return False

def main():
    """Main execution function"""
    
    orchestrator = SystemOrchestrator()
    success = orchestrator.run_complete_system()
    
    return success

if __name__ == "__main__":
    main()