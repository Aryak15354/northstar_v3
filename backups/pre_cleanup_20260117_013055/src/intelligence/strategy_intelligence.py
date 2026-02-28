#!/usr/bin/env python3
"""
🧬 STRATEGY INTELLIGENCE ORCHESTRATOR
The master brain that coordinates beliefs, regret, and capital allocation

This orchestrates the complete strategy intelligence pipeline:
1. Update strategy beliefs (Bayesian learning)
2. Calculate strategy regret (opportunity cost)
3. Allocate capital based on beliefs + regret
4. Track strategy lifecycle and status changes

Usage:
    from src.intelligence.strategy_intelligence import StrategyIntelligence
    
    intelligence = StrategyIntelligence()
    intelligence.run_complete_intelligence()
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class StrategyIntelligence:
    """
    Complete Strategy Intelligence System
    
    Orchestrates the full intelligence pipeline that transforms
    Northstar from a static system into a learning organism.
    """
    
    def __init__(self):
        self.name = "Strategy Intelligence Orchestrator"
        self.version = "3.0"
        
        # Component status tracking
        self.component_status = {
            'beliefs_update': False,
            'regret_calculation': False,
            'capital_allocation': False,
            'intelligence_summary': False
        }
        
        # Execution log
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
    
    def run_beliefs_update(self):
        """Step 1: Update strategy beliefs"""
        
        print("🧠 STEP 1: STRATEGY BELIEFS UPDATE")
        print("=" * 50)
        
        start_time = datetime.now()
        
        try:
            from src.intelligence.strategy_beliefs import StrategyBeliefs
            
            beliefs_engine = StrategyBeliefs()
            updated_beliefs = beliefs_engine.update_all_beliefs()
            
            if updated_beliefs:
                duration = (datetime.now() - start_time).total_seconds()
                self.log_execution('beliefs_update', 'success', 
                                 f"Updated beliefs for {len(updated_beliefs)} strategies", duration)
                print(f"✅ Beliefs update completed: {len(updated_beliefs)} strategies")
                return True
            else:
                self.log_execution('beliefs_update', 'failed', "No beliefs updated")
                print("❌ Beliefs update failed: No beliefs updated")
                return False
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution('beliefs_update', 'failed', str(e), duration)
            print(f"❌ Beliefs update failed: {e}")
            return False
    
    def run_regret_calculation(self):
        """Step 2: Calculate strategy regret"""
        
        print("\n😈 STEP 2: STRATEGY REGRET CALCULATION")
        print("=" * 50)
        
        start_time = datetime.now()
        
        try:
            from src.intelligence.strategy_regret import StrategyRegret
            
            regret_engine = StrategyRegret()
            regret_data = regret_engine.calculate_regret()
            
            if not regret_data.empty:
                duration = (datetime.now() - start_time).total_seconds()
                strategies_count = regret_data['strategy'].nunique()
                self.log_execution('regret_calculation', 'success', 
                                 f"Calculated regret for {strategies_count} strategies", duration)
                print(f"✅ Regret calculation completed: {strategies_count} strategies")
                return True
            else:
                self.log_execution('regret_calculation', 'failed', "No regret data calculated")
                print("❌ Regret calculation failed: No data generated")
                return False
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution('regret_calculation', 'failed', str(e), duration)
            print(f"❌ Regret calculation failed: {e}")
            return False
    
    def run_capital_allocation(self):
        """Step 3: Enhanced capital allocation with beliefs and regret"""
        
        print("\n⚖️ STEP 3: ENHANCED CAPITAL ALLOCATION")
        print("=" * 50)
        
        start_time = datetime.now()
        
        try:
            from src.intelligence.capital_allocator import CapitalAllocator
            
            allocator = CapitalAllocator()
            allocations = allocator.run_allocation()
            
            if allocations:
                duration = (datetime.now() - start_time).total_seconds()
                total_allocated = sum(allocations.values())
                self.log_execution('capital_allocation', 'success', 
                                 f"Allocated {total_allocated:.1%} across {len(allocations)} strategies", 
                                 duration)
                print(f"✅ Capital allocation completed: {len(allocations)} strategies")
                return True
            else:
                self.log_execution('capital_allocation', 'failed', "No allocations generated")
                print("❌ Capital allocation failed: No allocations generated")
                return False
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution('capital_allocation', 'failed', str(e), duration)
            print(f"❌ Capital allocation failed: {e}")
            return False
    
    def generate_intelligence_summary(self):
        """Step 4: Generate intelligence summary"""
        
        print("\n📊 STEP 4: INTELLIGENCE SUMMARY")
        print("=" * 50)
        
        start_time = datetime.now()
        
        try:
            summary = {
                'timestamp': datetime.now().isoformat(),
                'intelligence_status': 'active',
                'component_status': self.component_status,
                'execution_log': self.execution_log,
                'strategy_insights': {},
                'system_health': {}
            }
            
            # Load latest beliefs
            beliefs_file = 'data/processed/strategy_beliefs.parquet'
            if os.path.exists(beliefs_file):
                beliefs_df = pd.read_parquet(beliefs_file)
                latest_beliefs = beliefs_df.sort_values('date').groupby('strategy').tail(1)
                
                # Strategy status distribution
                status_counts = latest_beliefs['status'].value_counts().to_dict()
                
                # Top strategies by effective skill
                top_strategies = latest_beliefs.nlargest(5, 'effective_skill')[
                    ['strategy', 'effective_skill', 'skill_prob', 'status']
                ].to_dict('records')
                
                summary['strategy_insights'] = {
                    'total_strategies': len(latest_beliefs),
                    'status_distribution': status_counts,
                    'top_strategies': top_strategies,
                    'avg_skill_prob': float(latest_beliefs['skill_prob'].mean()),
                    'avg_confidence': float(latest_beliefs['confidence'].mean())
                }
            
            # Load latest regret
            regret_file = 'data/processed/strategy_regret.parquet'
            if os.path.exists(regret_file):
                regret_df = pd.read_parquet(regret_file)
                latest_regret = regret_df.sort_values('date').groupby('strategy').tail(1)
                
                # High regret strategies
                high_regret = latest_regret.nlargest(3, 'cum_regret')[
                    ['strategy', 'cum_regret', 'penalty_score']
                ].to_dict('records')
                
                summary['strategy_insights']['high_regret_strategies'] = high_regret
                summary['strategy_insights']['avg_regret'] = float(latest_regret['cum_regret'].mean())
            
            # System health metrics
            success_rate = sum(1 for status in self.component_status.values() if status) / len(self.component_status)
            total_duration = sum(entry['duration_seconds'] for entry in self.execution_log)
            
            summary['system_health'] = {
                'success_rate': success_rate,
                'total_duration': total_duration,
                'intelligence_active': success_rate >= 0.75,
                'last_update': datetime.now().isoformat()
            }
            
            # Save summary
            summary_file = 'data/processed/strategy_intelligence_summary.json'
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution('intelligence_summary', 'success', 
                             f"Generated intelligence summary", duration)
            
            # Print summary
            print(f"✅ Intelligence summary generated")
            print(f"   📊 Success rate: {success_rate:.1%}")
            print(f"   📊 Total strategies: {summary['strategy_insights'].get('total_strategies', 0)}")
            print(f"   📊 Intelligence status: {'ACTIVE' if summary['system_health']['intelligence_active'] else 'DEGRADED'}")
            
            return True
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution('intelligence_summary', 'failed', str(e), duration)
            print(f"❌ Intelligence summary failed: {e}")
            return False
    
    def run_complete_intelligence(self):
        """Run the complete strategy intelligence pipeline"""
        
        print("🧬 STRATEGY INTELLIGENCE ORCHESTRATOR")
        print("=" * 70)
        print("Transforming Northstar into a learning financial organism")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Track overall execution
        system_start = datetime.now()
        
        # Run all intelligence components
        steps = [
            ('Strategy Beliefs Update', self.run_beliefs_update),
            ('Strategy Regret Calculation', self.run_regret_calculation),
            ('Enhanced Capital Allocation', self.run_capital_allocation),
            ('Intelligence Summary', self.generate_intelligence_summary)
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
        
        # Print final summary
        print(f"\n🧬 STRATEGY INTELLIGENCE COMPLETE")
        print("=" * 70)
        print(f"⏱️  Total Duration: {total_duration:.1f} seconds")
        print(f"✅ Success Rate: {success_rate:.1%} ({successful_steps}/{len(steps)} steps)")
        print(f"🧬 Component Status:")
        
        for component, status in self.component_status.items():
            status_icon = "✅" if status else "❌"
            print(f"   {status_icon} {component.replace('_', ' ').title()}")
        
        if success_rate >= 0.75:
            print(f"\n🎉 NORTHSTAR IS NOW A LEARNING FINANCIAL ORGANISM!")
            print("   Strategies compete based on Bayesian beliefs and regret tracking.")
            print("   The system learns, adapts, and evolves its capital allocation.")
        else:
            print(f"\n⚠️ Intelligence system partially operational - some components need attention")
        
        return success_rate >= 0.75

def main():
    """Main execution function"""
    
    intelligence = StrategyIntelligence()
    success = intelligence.run_complete_intelligence()
    
    return success

if __name__ == "__main__":
    main()