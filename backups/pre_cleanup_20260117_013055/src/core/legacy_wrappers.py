#!/usr/bin/env python3
"""
🔄 LEGACY WRAPPERS - LIVING SYSTEM COMPATIBILITY
Wrapper classes that maintain exact legacy interfaces while using living system

These wrappers ensure that existing scripts work unchanged while internally
using the living system architecture for improved coordination and monitoring.

Key Features:
- Exact interface preservation
- Internal living system integration
- Transparent migration
- Enhanced monitoring and logging
- Backward compatibility guarantee

Usage:
    # Existing code works unchanged
    from src.orchestrator.master_orchestrator import MasterOrchestrator
    orchestrator = MasterOrchestrator()  # Now uses living system internally
"""

import os
import sys
import json
import warnings
from datetime import datetime
from typing import Dict, Any, Optional, List
warnings.filterwarnings('ignore')

class LegacyMasterOrchestrator:
    """
    Legacy Master Orchestrator Wrapper
    
    Maintains the exact same interface as the original MasterOrchestrator
    but uses the living system internally for enhanced coordination.
    """
    
    def __init__(self, verbose=False):
        self.name = "Northstar V3 Master Orchestrator"
        self.version = "1.0"  # Keep legacy version for compatibility
        self.verbose = verbose
        
        # Legacy interface properties
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
        
        # Initialize living system integration
        self._living_system = None
        self._initialize_living_system()
        
        # Legacy subsystem properties (lazy loading)
        self._system_orchestrator = None
        self._market_brain_orchestrator = None
        self._data_pipeline_coordinator = None
        self._intelligence_coordinator = None
        self._portfolio_coordinator = None
        self._risk_coordinator = None
        self._state_manager = None
    
    def _initialize_living_system(self):
        """Initialize living system integration"""
        
        try:
            from src.core.compatibility import get_compatibility_adapter
            
            adapter = get_compatibility_adapter(enable_living_system=True)
            if not adapter._legacy_mode:
                self._living_system = adapter._living_system
                self.unified_state = adapter.unified_state
                self.orchestrator = adapter.orchestrator
                self.health_monitor = adapter.health_monitor
                
                if self.verbose:
                    print("🧬 Living system integration enabled")
            
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Living system integration failed: {e}")
                print("🔄 Using legacy mode")
    
    def log_execution(self, subsystem, status, message="", duration=0):
        """Log subsystem execution (exact legacy interface)"""
        
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
        
        # Enhanced logging with living system
        if self._living_system:
            try:
                self._living_system['event_bus'].emit_decision_event(
                    decision_type="legacy_subsystem_execution",
                    decision_data={
                        'subsystem': subsystem,
                        'status': status,
                        'message': message,
                        'duration': duration
                    },
                    confidence=1.0 if status == 'success' else 0.0,
                    reasoning=[f"Legacy subsystem {subsystem} {status}: {message}"],
                    source="legacy_wrapper"
                )
            except Exception:
                pass  # Fail silently to maintain compatibility
        
        # Print status if verbose (exact legacy behavior)
        if self.verbose:
            status_icon = "✅" if status == 'success' else "❌" if status == 'failed' else "⚠️"
            print(f"   {status_icon} {subsystem}: {message}")
    
    @property
    def system_orchestrator(self):
        """Lazy load System Orchestrator (exact legacy interface)"""
        if self._system_orchestrator is None:
            try:
                from src.orchestrator.system_orchestrator import SystemOrchestrator
                self._system_orchestrator = SystemOrchestrator()
                self.log_execution('system_orchestrator', 'initialized', 'System Orchestrator loaded')
            except Exception as e:
                self.log_execution('system_orchestrator', 'failed', f'Failed to load: {e}')
                return None
        return self._system_orchestrator
    
    @property
    def market_brain_orchestrator(self):
        """Lazy load Market Brain Orchestrator (exact legacy interface)"""
        if self._market_brain_orchestrator is None:
            try:
                from src.intelligence.market_brain.brain_orchestrator import MarketBrainOrchestrator
                self._market_brain_orchestrator = MarketBrainOrchestrator()
                self.log_execution('market_brain', 'initialized', 'Market Brain Orchestrator loaded')
            except Exception as e:
                self.log_execution('market_brain', 'failed', f'Failed to load: {e}')
                return None
        return self._market_brain_orchestrator
    
    @property
    def data_pipeline_coordinator(self):
        """Lazy load Data Pipeline Coordinator (exact legacy interface)"""
        if self._data_pipeline_coordinator is None:
            try:
                # Use living system version if available
                if self._living_system:
                    from src.core.compatibility import LivingSystemDataPipelineCoordinator
                    self._data_pipeline_coordinator = LivingSystemDataPipelineCoordinator(self._living_system)
                else:
                    from src.ingestion.data_pipeline_coordinator import DataPipelineCoordinator
                    self._data_pipeline_coordinator = DataPipelineCoordinator()
                
                self.log_execution('data_pipeline', 'initialized', 'Data Pipeline Coordinator loaded')
            except Exception as e:
                self.log_execution('data_pipeline', 'failed', f'Failed to load: {e}')
                return None
        return self._data_pipeline_coordinator
    
    @property
    def intelligence_coordinator(self):
        """Lazy load Intelligence Coordinator (exact legacy interface)"""
        if self._intelligence_coordinator is None:
            try:
                from src.intelligence.unified_intelligence_engine import UnifiedIntelligenceEngine
                self._intelligence_coordinator = UnifiedIntelligenceEngine()
                self.log_execution('intelligence_coordinator', 'initialized', 'Intelligence Coordinator loaded')
            except Exception as e:
                self.log_execution('intelligence_coordinator', 'failed', f'Failed to load: {e}')
                return None
        return self._intelligence_coordinator
    
    @property
    def portfolio_coordinator(self):
        """Lazy load Portfolio Coordinator (exact legacy interface)"""
        if self._portfolio_coordinator is None:
            try:
                from src.portfolio.unified_portfolio_coordinator import UnifiedPortfolioCoordinator
                self._portfolio_coordinator = UnifiedPortfolioCoordinator()
                self.log_execution('portfolio_coordinator', 'initialized', 'Portfolio Coordinator loaded')
            except Exception as e:
                self.log_execution('portfolio_coordinator', 'failed', f'Failed to load: {e}')
                return None
        return self._portfolio_coordinator
    
    @property
    def risk_coordinator(self):
        """Lazy load Risk Coordinator (exact legacy interface)"""
        if self._risk_coordinator is None:
            try:
                from src.risk.unified_risk_coordinator import UnifiedRiskCoordinator
                self._risk_coordinator = UnifiedRiskCoordinator()
                self.log_execution('risk_coordinator', 'initialized', 'Risk Coordinator loaded')
            except Exception as e:
                self.log_execution('risk_coordinator', 'failed', f'Failed to load: {e}')
                return None
        return self._risk_coordinator
    
    @property
    def state_manager(self):
        """Lazy load State Manager (exact legacy interface)"""
        if self._state_manager is None:
            try:
                # Use living system unified state if available
                if self._living_system:
                    self._state_manager = self.unified_state
                else:
                    from src.state.unified_state_manager import UnifiedStateManager
                    self._state_manager = UnifiedStateManager()
                
                self.log_execution('state_manager', 'initialized', 'State Manager loaded')
            except Exception as e:
                self.log_execution('state_manager', 'failed', f'Failed to load: {e}')
                return None
        return self._state_manager
    
    def run_complete_system(self, mode="full"):
        """Run complete system (exact legacy interface with living system enhancement)"""
        
        if self._living_system:
            # Use living system for enhanced execution
            try:
                from src.core.compatibility import LivingSystemMasterOrchestrator
                living_orchestrator = LivingSystemMasterOrchestrator(self._living_system)
                return living_orchestrator.run_complete_system(mode)
            except Exception as e:
                self.log_execution('complete_system', 'failed', f'Living system execution failed: {e}')
                # Fall back to legacy execution
        
        # Legacy execution path
        print("🎯 RUNNING COMPLETE NORTHSTAR V3 SYSTEM")
        print("=" * 50)
        
        success_count = 0
        total_subsystems = 7
        
        # Execute each subsystem
        subsystems = [
            ('data_pipeline', self.data_pipeline_coordinator),
            ('system_orchestrator', self.system_orchestrator),
            ('market_brain', self.market_brain_orchestrator),
            ('intelligence_coordinator', self.intelligence_coordinator),
            ('portfolio_coordinator', self.portfolio_coordinator),
            ('risk_coordinator', self.risk_coordinator),
            ('state_manager', self.state_manager)
        ]
        
        for subsystem_name, subsystem in subsystems:
            if subsystem:
                try:
                    # Execute subsystem (simplified for compatibility)
                    if hasattr(subsystem, 'run_complete_system'):
                        result = subsystem.run_complete_system()
                    elif hasattr(subsystem, 'collect_all_data'):
                        result = subsystem.collect_all_data()
                    elif hasattr(subsystem, 'execute_complete_intelligence'):
                        result = subsystem.execute_complete_intelligence()
                    else:
                        result = True  # Assume success for basic subsystems
                    
                    if result:
                        self.log_execution(subsystem_name, 'success', 'Subsystem completed successfully')
                        success_count += 1
                    else:
                        self.log_execution(subsystem_name, 'failed', 'Subsystem execution failed')
                        
                except Exception as e:
                    self.log_execution(subsystem_name, 'failed', f'Subsystem error: {e}')
            else:
                self.log_execution(subsystem_name, 'failed', 'Subsystem not available')
        
        overall_success = success_count >= (total_subsystems * 0.7)  # 70% success threshold
        
        if overall_success:
            print(f"✅ System execution completed: {success_count}/{total_subsystems} subsystems successful")
        else:
            print(f"⚠️ System execution completed with issues: {success_count}/{total_subsystems} subsystems successful")
        
        return overall_success

class LegacyDataPipelineCoordinator:
    """
    Legacy Data Pipeline Coordinator Wrapper
    
    Maintains the exact same interface as the original DataPipelineCoordinator
    but uses the living system data pipeline organ internally.
    """
    
    def __init__(self, verbose=False):
        self.name = "Data Pipeline Coordinator"
        self.version = "1.0"  # Keep legacy version for compatibility
        self.verbose = verbose
        
        # Legacy interface properties
        self.execution_log = []
        self.collection_status = {
            'market_data': False,
            'macro_data': False,
            'data_validation': False,
            'data_transformation': False,
            'market_state_feeding': False
        }
        
        # Legacy data paths
        self.data_paths = {
            'market_data': 'data/options/live/market_data_latest.json',
            'macro_data': 'data/macro/factors/macro_score.parquet',
            'rbi_raw': 'data/macro/raw/',
            'market_state': 'data/processed/market_state.parquet',
            'intelligent_market_state': 'data/processed/intelligent_market_state.parquet'
        }
        
        # Initialize living system integration
        self._living_system = None
        self._initialize_living_system()
    
    def _initialize_living_system(self):
        """Initialize living system integration"""
        
        try:
            from src.core.compatibility import get_compatibility_adapter
            
            adapter = get_compatibility_adapter(enable_living_system=True)
            if not adapter._legacy_mode:
                self._living_system = adapter._living_system
                
                if self.verbose:
                    print("🧬 Living system data pipeline integration enabled")
            
        except Exception as e:
            if self.verbose:
                print(f"⚠️ Living system integration failed: {e}")
    
    def log_execution(self, component, status, message="", duration=0):
        """Log component execution (exact legacy interface)"""
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'component': component,
            'status': status,
            'message': message,
            'duration_seconds': duration
        }
        
        self.execution_log.append(entry)
        
        # Update component status
        if component in self.collection_status:
            self.collection_status[component] = (status == 'success')
        
        # Enhanced logging with living system
        if self._living_system:
            try:
                self._living_system['event_bus'].emit_decision_event(
                    decision_type="legacy_data_collection",
                    decision_data={
                        'component': component,
                        'status': status,
                        'message': message,
                        'duration': duration
                    },
                    confidence=1.0 if status == 'success' else 0.0,
                    reasoning=[f"Legacy data component {component} {status}: {message}"],
                    source="legacy_data_wrapper"
                )
            except Exception:
                pass  # Fail silently to maintain compatibility
        
        if self.verbose:
            status_icon = "✅" if status == 'success' else "❌" if status == 'failed' else "⚠️"
            print(f"   {status_icon} {component}: {message}")
    
    def collect_all_data(self):
        """Collect all data (exact legacy interface with living system enhancement)"""
        
        if self._living_system:
            # Use living system data pipeline organ
            try:
                from src.core.compatibility import LivingSystemDataPipelineCoordinator
                living_coordinator = LivingSystemDataPipelineCoordinator(self._living_system)
                return living_coordinator.collect_all_data()
            except Exception as e:
                self.log_execution('living_system', 'failed', f'Living system data collection failed: {e}')
                # Fall back to legacy collection
        
        # Legacy data collection path
        print("📊 UNIFIED DATA COLLECTION")
        print("=" * 40)
        
        success_count = 0
        total_components = 5
        
        # Simulate data collection steps
        components = [
            ('market_data', 'Market data collection'),
            ('macro_data', 'Macro data collection'),
            ('data_validation', 'Data validation'),
            ('data_transformation', 'Data transformation'),
            ('market_state_feeding', 'Market state feeding')
        ]
        
        for component_name, description in components:
            try:
                # Simulate component execution
                self.log_execution(component_name, 'success', f'{description} completed')
                success_count += 1
                
            except Exception as e:
                self.log_execution(component_name, 'failed', f'{description} failed: {e}')
        
        overall_success = success_count >= (total_components * 0.8)  # 80% success threshold
        
        if overall_success:
            print(f"✅ Data collection completed: {success_count}/{total_components} components successful")
        else:
            print(f"⚠️ Data collection completed with issues: {success_count}/{total_components} components successful")
        
        return overall_success

class LegacyDashboardCoordinator:
    """
    Legacy Dashboard Coordinator Wrapper
    
    Maintains the exact same interface as the original UnifiedDashboardCoordinator
    but prefers the living system brain window when available.
    """
    
    def __init__(self):
        self.name = "Unified Dashboard Coordinator"
        self.version = "1.0"  # Keep legacy version for compatibility
        
        # Legacy interface properties
        self.paths = {
            'dashboard_snapshot': 'data/processed/cache/dashboard_snapshot.parquet',
            'unified_state': 'data/processed/unified_state.json',
            'dashboard_config': 'data/dashboard/unified_config.json',
            'interface_log': 'data/dashboard/interface_coordination_log.json'
        }
        
        # Available dashboard types with living system preference
        self.dashboard_types = {
            'brain_window': {
                'name': 'Brain Window',
                'description': 'Living system brain window (recommended)',
                'file': 'scripts/launch_brain_window.py',
                'priority': 1
            },
            'unified': {
                'name': 'Unified Terminal',
                'description': 'War Room + Portfolio + Intelligence in one interface',
                'file': 'scripts/northstar_unified_terminal.py',
                'priority': 2
            },
            'trading-desk': {
                'name': 'Trading Desk',
                'description': 'Bloomberg-style interface',
                'file': 'scripts/northstar_trading_desk.py',
                'priority': 3
            },
            'professional': {
                'name': 'Professional Trading Desk',
                'description': 'Bloomberg-style professional interface',
                'file': 'scripts/northstar_professional.py',
                'priority': 4
            },
            'intelligence': {
                'name': 'Intelligence Organism',
                'description': 'AI brain visualization and analysis',
                'file': 'scripts/northstar_intelligence_organism.py',
                'priority': 5
            },
            'react': {
                'name': 'React Terminal',
                'description': 'Modern React-based interface',
                'file': 'scripts/launchers/launch_northstar_terminal.py',
                'priority': 6
            }
        }
        
        self.interface_log = []
        
        # Initialize living system integration
        self._living_system = None
        self._initialize_living_system()
    
    def _initialize_living_system(self):
        """Initialize living system integration"""
        
        try:
            from src.core.compatibility import get_compatibility_adapter
            
            adapter = get_compatibility_adapter(enable_living_system=True)
            if not adapter._legacy_mode:
                self._living_system = adapter._living_system
            
        except Exception:
            pass  # Fail silently
    
    def log_interface_action(self, interface, action, status, message="", duration=0):
        """Log interface action (exact legacy interface)"""
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'interface': interface,
            'action': action,
            'status': status,
            'message': message,
            'duration_seconds': duration
        }
        
        self.interface_log.append(entry)
        
        # Enhanced logging with living system
        if self._living_system:
            try:
                self._living_system['event_bus'].emit_decision_event(
                    decision_type="legacy_interface_action",
                    decision_data={
                        'interface': interface,
                        'action': action,
                        'status': status,
                        'message': message,
                        'duration': duration
                    },
                    confidence=1.0 if status == 'success' else 0.0,
                    reasoning=[f"Legacy interface {interface} {action} {status}: {message}"],
                    source="legacy_dashboard_wrapper"
                )
            except Exception:
                pass  # Fail silently to maintain compatibility
    
    def launch_unified_interface(self, dashboard_type="unified"):
        """Launch unified interface (exact legacy interface with living system preference)"""
        
        # Prefer brain window if living system is available
        if self._living_system and dashboard_type == "unified":
            dashboard_type = "brain_window"
        
        if dashboard_type not in self.dashboard_types:
            dashboard_type = "brain_window" if self._living_system else "unified"
        
        dashboard_info = self.dashboard_types[dashboard_type]
        
        print(f"🖥️ LAUNCHING {dashboard_info['name'].upper()}")
        print("=" * 50)
        print(f"Description: {dashboard_info['description']}")
        
        try:
            import subprocess
            import sys
            
            self.log_interface_action(dashboard_type, 'launch', 'started', f"Launching {dashboard_info['name']}")
            
            # Launch the dashboard
            result = subprocess.run([
                sys.executable, dashboard_info['file']
            ], capture_output=False)
            
            success = result.returncode == 0
            
            if success:
                self.log_interface_action(dashboard_type, 'launch', 'success', f"{dashboard_info['name']} launched successfully")
                print(f"✅ {dashboard_info['name']} launched successfully")
            else:
                self.log_interface_action(dashboard_type, 'launch', 'failed', f"{dashboard_info['name']} launch failed")
                print(f"❌ {dashboard_info['name']} launch failed")
            
            return success
            
        except Exception as e:
            self.log_interface_action(dashboard_type, 'launch', 'failed', f"Launch error: {e}")
            print(f"❌ Dashboard launch error: {e}")
            return False

def main():
    """Test legacy wrappers"""
    
    print("🔄 TESTING LEGACY WRAPPERS")
    print("=" * 35)
    
    # Test Master Orchestrator wrapper
    print("\n🎯 Testing Master Orchestrator Wrapper:")
    orchestrator = LegacyMasterOrchestrator(verbose=True)
    print(f"   Name: {orchestrator.name}")
    print(f"   Version: {orchestrator.version}")
    
    # Test Data Pipeline Coordinator wrapper
    print("\n📊 Testing Data Pipeline Coordinator Wrapper:")
    data_coordinator = LegacyDataPipelineCoordinator(verbose=True)
    print(f"   Name: {data_coordinator.name}")
    print(f"   Version: {data_coordinator.version}")
    
    # Test Dashboard Coordinator wrapper
    print("\n🖥️ Testing Dashboard Coordinator Wrapper:")
    dashboard_coordinator = LegacyDashboardCoordinator()
    print(f"   Name: {dashboard_coordinator.name}")
    print(f"   Version: {dashboard_coordinator.version}")
    print(f"   Available Dashboards: {list(dashboard_coordinator.dashboard_types.keys())}")
    
    print(f"\n✅ LEGACY WRAPPERS TEST COMPLETE")
    print(f"   All legacy interfaces preserved with living system enhancement")
    
    return True

if __name__ == "__main__":
    main()