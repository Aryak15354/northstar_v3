#!/usr/bin/env python3
"""
🎯 MASTER ORCHESTRATOR - NORTHSTAR V3 UNIFIED SYSTEM
The Supreme Controller: Coordinates All Northstar V3 Subsystems

This is the master orchestrator that unifies all separate systems into
one coherent investment operating system.

Responsibilities:
- Initialize all subsystems
- Coordinate execution sequencing
- Manage state propagation
- Handle error recovery
- Provide unified interface

Subsystems Coordinated:
1. Data Pipeline Coordinator (Data Collection)
2. System Orchestrator (Strategy + Backtesting)
3. Market Brain Orchestrator (Market Intelligence)
4. Intelligence Coordinator (Unified Beliefs)
5. Portfolio Coordinator (Portfolio Construction)
6. Risk Coordinator (Risk Management)
7. State Manager (Unified State)
"""

from src.cohesion.dependency_container import get_dependency_container

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class MasterOrchestrator:
    """
    Master Orchestrator - Supreme Controller for Northstar V3
    
    Coordinates all subsystems to create a unified investment operating system.
    """
    
    def __init__(self, verbose=False):
        self.name = "Northstar V3 Master Orchestrator"
        self.version = "1.0"
        self.verbose = verbose
        
        # Execution tracking
        self.execution_log = []
        self.subsystem_status = {
            'data_pipeline': False,
            'system_orchestrator': False,
            'market_brain': False,
            'intelligence_coordinator': False,
            'portfolio_coordinator': False,
            'risk_coordinator': False,
            'state_manager': False
        }
        
        # Initialize subsystems (lazy loading)
        self._system_orchestrator = None
        self._market_brain_orchestrator = None
        self._data_pipeline_coordinator = None
        self._intelligence_coordinator = None
        self._portfolio_coordinator = None
        self._risk_coordinator = None
        self._state_manager = None
    
    def log_execution(self, subsystem, status, message="", duration=0):
        """Log subsystem execution"""
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'subsystem': subsystem,
            'status': status,
            'message': message,
            'duration_seconds': duration
        }
        
        self.execution_log.append(entry)
        
        # Update subsystem status
        if subsystem in self.subsystem_status:
            self.subsystem_status[subsystem] = (status == 'success')
        
        # Print status if verbose
        if self.verbose:
            status_icon = "✅" if status == 'success' else "❌" if status == 'failed' else "⚠️"
            print(f"   {status_icon} {subsystem}: {message}")
    
    @property
    def system_orchestrator(self):
        """Lazy load System Orchestrator"""
        if self._system_orchestrator is None:
            try:
                from src.orchestrator.system_orchestrator import SystemOrchestrator
                self._system_orchestrator = SystemOrchestrator()
            except ImportError as e:
                if self.verbose:
                    print(f"⚠️ System Orchestrator not available: {e}")
                self._system_orchestrator = None
        return self._system_orchestrator
    
    @property
    def market_brain_orchestrator(self):
        """Lazy load Market Brain Orchestrator"""
        if self._market_brain_orchestrator is None:
            try:
                from src.intelligence.market_brain.brain_orchestrator import BrainOrchestrator
                self._market_brain_orchestrator = BrainOrchestrator()
            except ImportError as e:
                if self.verbose:
                    print(f"⚠️ Market Brain Orchestrator not available: {e}")
                self._market_brain_orchestrator = None
        return self._market_brain_orchestrator
    
    @property
    def data_pipeline_coordinator(self):
        """Lazy load Data Pipeline Coordinator"""
        if self._data_pipeline_coordinator is None:
            try:
                from src.ingestion.data_pipeline_coordinator import DataPipelineCoordinator
                self._data_pipeline_coordinator = DataPipelineCoordinator()
            except ImportError as e:
                if self.verbose:
                    print(f"⚠️ Data Pipeline Coordinator not available: {e}")
                self._data_pipeline_coordinator = None
        return self._data_pipeline_coordinator
    
    @property
    def intelligence_coordinator(self):
        """Lazy load Intelligence Coordinator"""
        if self._intelligence_coordinator is None:
            try:
                # Try new Unified Intelligence Engine first
                from src.intelligence.unified_intelligence_engine import UnifiedIntelligenceEngine
                self._intelligence_coordinator = UnifiedIntelligenceEngine()
                if self.verbose:
                    print(f"✅ Using Unified Intelligence Engine")
            except ImportError:
                try:
                    # Fallback to old intelligence coordinator
                    from src.intelligence.intelligence_coordinator import IntelligenceCoordinator
                    self._intelligence_coordinator = IntelligenceCoordinator()
                    if self.verbose:
                        print(f"⚠️ Using fallback Intelligence Coordinator")
                except ImportError as e:
                    if self.verbose:
                        print(f"⚠️ Intelligence Coordinator not available: {e}")
                    self._intelligence_coordinator = None
        return self._intelligence_coordinator
    
    @property
    def portfolio_coordinator(self):
        """Lazy load Portfolio Coordinator"""
        if self._portfolio_coordinator is None:
            try:
                # Try new Unified Portfolio Coordinator first
                from src.portfolio.unified_portfolio_coordinator import UnifiedPortfolioCoordinator
                self._portfolio_coordinator = UnifiedPortfolioCoordinator()
                if self.verbose:
                    print(f"✅ Using Unified Portfolio Coordinator")
            except ImportError:
                try:
                    # Fallback to old portfolio coordinator
                    from src.portfolio.portfolio_coordinator import PortfolioCoordinator
                    self._portfolio_coordinator = PortfolioCoordinator()
                    if self.verbose:
                        print(f"⚠️ Using fallback Portfolio Coordinator")
                except ImportError as e:
                    if self.verbose:
                        print(f"⚠️ Portfolio Coordinator not available: {e}")
                    self._portfolio_coordinator = None
        return self._portfolio_coordinator
    
    @property
    def risk_coordinator(self):
        """Lazy load Risk Coordinator"""
        if self._risk_coordinator is None:
            try:
                # Try new Unified Risk Coordinator first
                from src.risk.unified_risk_coordinator import UnifiedRiskCoordinator
                self._risk_coordinator = UnifiedRiskCoordinator()
                if self.verbose:
                    print(f"✅ Using Unified Risk Coordinator")
            except ImportError:
                try:
                    # Fallback to old risk coordinator
                    from src.risk.risk_coordinator import RiskCoordinator
                    self._risk_coordinator = RiskCoordinator()
                    if self.verbose:
                        print(f"⚠️ Using fallback Risk Coordinator")
                except ImportError as e:
                    if self.verbose:
                        print(f"⚠️ Risk Coordinator not available: {e}")
                    self._risk_coordinator = None
        return self._risk_coordinator
    
    @property
    def state_manager(self):
        """Lazy load Unified State Manager"""
        if self._state_manager is None:
            try:
                from src.state.unified_state_manager import UnifiedStateManager
                self._state_manager = UnifiedStateManager()
            except ImportError as e:
                if self.verbose:
                    print(f"⚠️ Unified State Manager not available: {e}")
                self._state_manager = None
        return self._state_manager
    
    def run_system_update(self, quick=False):
        """Run complete system update with unified coordination"""
        
        print("🔄 UNIFIED SYSTEM UPDATE")
        print("=" * 50)
        
        total_start_time = datetime.now()
        
        # Step 1: Data Collection
        success_1 = self.run_data_collection()
        
        # Step 2: Data Processing & Market State
        success_2 = self.run_data_processing()
        
        # Step 3: Intelligence Generation
        if quick:
            success_3 = self.run_quick_intelligence_update()
        else:
            success_3 = self.run_intelligence_generation()
        
        # Step 4: Portfolio Construction
        success_4 = self.run_portfolio_construction()
        
        # Step 5: Risk Management
        success_5 = self.run_risk_management()
        
        # Step 6: State Management
        success_6 = self.run_state_update()
        
        # Calculate results
        total_duration = (datetime.now() - total_start_time).total_seconds()
        successful_steps = sum([success_1, success_2, success_3, success_4, success_5, success_6])
        
        # Save execution log
        self.save_execution_log()
        
        # Print summary
        print(f"\n🎯 UNIFIED UPDATE COMPLETE")
        print("=" * 50)
        print(f"Duration: {total_duration:.1f} seconds")
        print(f"Success: {successful_steps}/6 steps")
        
        return successful_steps >= 4  # At least 4 steps must succeed
    
    def run_data_collection(self):
        """Step 1: Coordinate data collection"""
        
        print("📊 STEP 1: DATA COLLECTION")
        print("-" * 30)
        
        start_time = datetime.now()
        
        try:
            # Try unified data pipeline coordinator first
            if self.data_pipeline_coordinator:
                success = self.data_pipeline_coordinator.collect_all_data()
                duration = (datetime.now() - start_time).total_seconds()
                
                if success:
                    self.log_execution('data_pipeline', 'success', 
                                     "Unified data collection completed", duration)
                    return True
                else:
                    self.log_execution('data_pipeline', 'failed', 
                                     "Unified data collection failed", duration)
            
            # Fallback to individual data collection
            print("   🔄 Using fallback data collection...")
            
            # Run EOD options pipeline
            try:
                import subprocess
                result = subprocess.run([sys.executable, 'eod_options_pipeline.py'], 
                                      capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    print("   ✅ Market data collected")
                    eod_success = True
                else:
                    print("   ❌ Market data collection failed")
                    eod_success = False
            except Exception as e:
                print(f"   ❌ Market data collection error: {e}")
                eod_success = False
            
            # Run integrated data pipeline using subprocess to avoid argument conflicts
            try:
                result = subprocess.run([sys.executable, 'src/ingestion/integrated_data_pipeline.py'], 
                                      capture_output=True, text=True, timeout=180)
                if result.returncode == 0:
                    print("   ✅ Integrated data pipeline completed")
                    integrated_success = True
                else:
                    print("   ❌ Integrated data pipeline failed")
                    integrated_success = False
            except Exception as e:
                print(f"   ❌ Integrated data pipeline error: {e}")
                integrated_success = False
            
            duration = (datetime.now() - start_time).total_seconds()
            
            if eod_success or integrated_success:
                self.log_execution('data_pipeline', 'success', 
                                 "Fallback data collection completed", duration)
                return True
            else:
                self.log_execution('data_pipeline', 'failed', 
                                 "All data collection methods failed", duration)
                return False
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution('data_pipeline', 'failed', str(e), duration)
            return False
    
    def run_data_processing(self):
        """Step 2: Process data and update market state"""
        
        print("\n🧠 STEP 2: DATA PROCESSING & MARKET STATE")
        print("-" * 40)
        
        start_time = datetime.now()
        
        try:
            # Run intelligent market state
            import subprocess
            result = subprocess.run([sys.executable, 'run_intelligent_market_state.py'], 
                                  capture_output=True, text=True, timeout=180)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            if result.returncode == 0:
                self.log_execution('data_processing', 'success', 
                                 "Market state updated", duration)
                print("   ✅ Market state updated")
                return True
            else:
                self.log_execution('data_processing', 'failed', 
                                 "Market state update failed", duration)
                print("   ❌ Market state update failed")
                return False
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution('data_processing', 'failed', str(e), duration)
            print(f"   ❌ Data processing error: {e}")
            return False
    
    def run_intelligence_generation(self):
        """Step 3: Generate unified intelligence"""
        
        print("\n🧬 STEP 3: INTELLIGENCE GENERATION")
        print("-" * 35)
        
        start_time = datetime.now()
        
        try:
            # Try unified intelligence coordinator first
            if self.intelligence_coordinator:
                success = self.intelligence_coordinator.generate_unified_intelligence()
                duration = (datetime.now() - start_time).total_seconds()
                
                if success:
                    self.log_execution('intelligence_coordinator', 'success', 
                                     "Unified intelligence generated", duration)
                    return True
                else:
                    self.log_execution('intelligence_coordinator', 'failed', 
                                     "Unified intelligence generation failed", duration)
            
            # Fallback to individual intelligence systems
            print("   🔄 Using fallback intelligence generation...")
            
            # Run Market Brain
            brain_success = False
            if self.market_brain_orchestrator:
                try:
                    brain_success = self.market_brain_orchestrator.run_complete_market_brain()
                    if brain_success:
                        print("   ✅ Market Brain intelligence generated")
                    else:
                        print("   ⚠️ Market Brain partially successful")
                except Exception as e:
                    print(f"   ❌ Market Brain error: {e}")
            
            # Run System Orchestrator (includes strategy intelligence)
            system_success = False
            if self.system_orchestrator:
                try:
                    system_success = self.system_orchestrator.run_complete_system()
                    if system_success:
                        print("   ✅ System intelligence generated")
                    else:
                        print("   ⚠️ System intelligence partially successful")
                except Exception as e:
                    print(f"   ❌ System intelligence error: {e}")
            
            duration = (datetime.now() - start_time).total_seconds()
            
            if brain_success or system_success:
                self.log_execution('intelligence_coordinator', 'success', 
                                 "Fallback intelligence generation completed", duration)
                return True
            else:
                self.log_execution('intelligence_coordinator', 'failed', 
                                 "All intelligence generation methods failed", duration)
                return False
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution('intelligence_coordinator', 'failed', str(e), duration)
            return False
    
    def run_quick_intelligence_update(self):
        """Step 3 (Quick): Quick intelligence update"""
        
        print("\n⚡ STEP 3: QUICK INTELLIGENCE UPDATE")
        print("-" * 35)
        
        start_time = datetime.now()
        
        try:
            # Quick market brain update
            import subprocess
            result = subprocess.run([sys.executable, 'run_market_brain_production.py'], 
                                  capture_output=True, text=True, timeout=120)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            if result.returncode == 0:
                self.log_execution('intelligence_coordinator', 'success', 
                                 "Quick intelligence update completed", duration)
                print("   ✅ Quick intelligence update completed")
                return True
            else:
                self.log_execution('intelligence_coordinator', 'failed', 
                                 "Quick intelligence update failed", duration)
                print("   ❌ Quick intelligence update failed")
                return False
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution('intelligence_coordinator', 'failed', str(e), duration)
            print(f"   ❌ Quick intelligence update error: {e}")
            return False
    
    def run_portfolio_construction(self):
        """Step 4: Construct portfolio"""
        
        print("\n🎯 STEP 4: PORTFOLIO CONSTRUCTION")
        print("-" * 35)
        
        start_time = datetime.now()
        
        try:
            # Try unified portfolio coordinator first
            if self.portfolio_coordinator:
                success = self.portfolio_coordinator.construct_unified_portfolio()
                duration = (datetime.now() - start_time).total_seconds()
                
                if success:
                    self.log_execution('portfolio_coordinator', 'success', 
                                     "Unified portfolio constructed", duration)
                    return True
                else:
                    self.log_execution('portfolio_coordinator', 'failed', 
                                     "Unified portfolio construction failed", duration)
            
            # Fallback to portfolio governor
            print("   🔄 Using fallback portfolio construction...")
            
            import subprocess
            result = subprocess.run([sys.executable, 'run_portfolio_governor.py'], 
                                  capture_output=True, text=True, timeout=120)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            if result.returncode == 0:
                self.log_execution('portfolio_coordinator', 'success', 
                                 "Fallback portfolio construction completed", duration)
                print("   ✅ Portfolio constructed")
                return True
            else:
                self.log_execution('portfolio_coordinator', 'failed', 
                                 "Portfolio construction failed", duration)
                print("   ❌ Portfolio construction failed")
                return False
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution('portfolio_coordinator', 'failed', str(e), duration)
            print(f"   ❌ Portfolio construction error: {e}")
            return False
    
    def run_risk_management(self):
        """Step 5: Apply risk management"""
        
        print("\n🛡️ STEP 5: RISK MANAGEMENT")
        print("-" * 25)
        
        start_time = datetime.now()
        
        try:
            # Try unified risk coordinator first
            if self.risk_coordinator:
                success = self.risk_coordinator.apply_unified_risk_management()
                duration = (datetime.now() - start_time).total_seconds()
                
                if success:
                    self.log_execution('risk_coordinator', 'success', 
                                     "Unified risk management applied", duration)
                    return True
                else:
                    self.log_execution('risk_coordinator', 'failed', 
                                     "Unified risk management failed", duration)
            
            # Fallback to individual risk checks
            print("   🔄 Using fallback risk management...")
            
            # Check emergency brake
            # Dependency injection - import EmergencyBrakeEngine from src.risk.emergency_brake
# print("⚠️ Unified Dashboard Coordinator not available, using fallback")
            
            # Fallback to direct dashboard launch
            if dashboard_type == 'unified':
                # Try to launch unified terminal V3
                try:
                    import subprocess
                    subprocess.run([sys.executable, '-m', 'streamlit', 'run', 'src/dashboard/unified_terminal_v3.py'])
                    return True
                except Exception:
                    print("⚠️ Unified terminal V3 not available, falling back to original unified terminal")
                    dashboard_type = 'unified-original'
            
            # Launch specific dashboard
            if dashboard_type == 'unified-original':
                import subprocess
                subprocess.run([sys.executable, '-m', 'streamlit', 'run', 'scripts/northstar_unified_terminal.py'])
                return True
            elif dashboard_type == 'trading-desk':
                import subprocess
                subprocess.run([sys.executable, '-m', 'streamlit', 'run', 'scripts/northstar_trading_desk.py'])
                return True
            elif dashboard_type == 'professional':
                import subprocess
                subprocess.run([sys.executable, '-m', 'streamlit', 'run', 'scripts/northstar_professional.py'])
                return True
            elif dashboard_type == 'intelligence':
                import subprocess
                subprocess.run([sys.executable, '-m', 'streamlit', 'run', 'scripts/northstar_intelligence_organism.py'])
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
    
    def run_live_trading(self):
        """Run live trading mode"""
        
        print("🔴 LIVE TRADING MODE")
        print("=" * 30)
        
        print("⚠️ Live trading mode is not yet implemented")
        print("🔧 This will be implemented in future phases")
        
        return False
    
    def run_backtest(self, strategy=None):
        """Run backtesting mode"""
        
        print("📈 BACKTESTING MODE")
        print("=" * 25)
        
        if strategy:
            print(f"Strategy: {strategy}")
        
        print("⚠️ Backtesting mode is not yet implemented")
        print("🔧 This will be implemented in future phases")
        
        return False
    
    def save_execution_log(self):
        """Save execution log for analysis"""
        
        log_file = 'data/processed/master_orchestrator_log.json'
        
        execution_summary = {
            'timestamp': datetime.now().isoformat(),
            'orchestrator_version': self.version,
            'subsystem_status': self.subsystem_status,
            'execution_log': self.execution_log,
            'total_duration': sum(entry['duration_seconds'] for entry in self.execution_log),
            'success_rate': sum(1 for status in self.subsystem_status.values() if status) / len(self.subsystem_status) if self.subsystem_status else 0
        }
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        with open(log_file, 'w') as f:
            json.dump(execution_summary, f, indent=2, default=str)
        
        if self.verbose:
            print(f"\n📋 Execution log saved: {log_file}")
    
    def get_system_status(self):
        """Get current system status"""
        
        return {
            'timestamp': datetime.now().isoformat(),
            'version': self.version,
            'subsystem_status': self.subsystem_status,
            'available_subsystems': {
                'system_orchestrator': self.system_orchestrator is not None,
                'market_brain_orchestrator': self.market_brain_orchestrator is not None,
                'data_pipeline_coordinator': self.data_pipeline_coordinator is not None,
                'intelligence_coordinator': self.intelligence_coordinator is not None,
                'portfolio_coordinator': self.portfolio_coordinator is not None,
                'risk_coordinator': self.risk_coordinator is not None,
                'state_manager': self.state_manager is not None
            }
        }

def main():
    """Test Master Orchestrator"""
    
    orchestrator = MasterOrchestrator(verbose=True)
    
    print("🧪 TESTING MASTER ORCHESTRATOR")
    print("=" * 40)
    
    # Test system status
    status = orchestrator.get_system_status()
    print(f"Available subsystems: {sum(status['available_subsystems'].values())}/7")
    
    # Test quick update
    success = orchestrator.run_system_update(quick=True)
    
    print(f"\n🎯 Test Result: {'✅ SUCCESS' if success else '❌ FAILED'}")
    
    return success

if __name__ == "__main__":
    main()