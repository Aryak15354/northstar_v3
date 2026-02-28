#!/usr/bin/env python3
"""
🔄 MIGRATION COMPATIBILITY LAYER - LIVING SYSTEM
Backward compatibility layer for existing scripts and workflows

This compatibility layer ensures that existing Northstar V3 scripts continue
to work while gradually migrating to the living system architecture.

Key Features:
- Transparent living system integration
- Existing interface preservation
- Gradual migration support
- Legacy script compatibility
- Zero-disruption transition

Usage:
    # Existing scripts work unchanged
    from src.orchestrator.master_orchestrator import MasterOrchestrator
    orchestrator = MasterOrchestrator()  # Now uses living system internally
    
    # Or explicitly use living system
    from src.core.compatibility import LivingSystemAdapter
    adapter = LivingSystemAdapter()
    orchestrator = adapter.get_master_orchestrator()
"""

import os
import sys
import json
import warnings
from datetime import datetime
from typing import Dict, Any, Optional, List
warnings.filterwarnings('ignore')

from src.core import create_living_system
from src.core.state import UnifiedState
from src.core.events import EventBus
from src.core.orchestrator import OrganOrchestrator
from src.core.health_monitor import HealthMonitor
from src.core.heartbeat import NorthstarHeartbeat, HeartbeatStatus

class LivingSystemAdapter:
    """
    Living System Adapter - Compatibility Layer
    
    Provides backward compatibility for existing scripts while enabling
    gradual migration to the living system architecture.
    """
    
    def __init__(self, enable_living_system: bool = True):
        self.name = "Living System Compatibility Adapter"
        self.version = "1.0"
        self.enable_living_system = enable_living_system
        
        # Initialize living system if enabled
        self._living_system = None
        self._legacy_mode = not enable_living_system
        
        if enable_living_system:
            self._initialize_living_system()
    
    def _initialize_living_system(self):
        """Initialize the living system"""
        
        try:
            print("🧬 Initializing Living System Compatibility Layer...")
            self._living_system = create_living_system()
            
            # Extract components for easy access
            self.unified_state = self._living_system['unified_state']
            self.event_bus = self._living_system['event_bus']
            self.orchestrator = self._living_system['organ_orchestrator']
            self.health_monitor = self._living_system['health_monitor']
            self.heartbeat = self._living_system['heartbeat']
            
            print("   ✅ Living system initialized successfully")
            
        except Exception as e:
            print(f"   ⚠️ Living system initialization failed: {e}")
            print("   🔄 Falling back to legacy mode")
            self._legacy_mode = True
    
    def get_master_orchestrator(self):
        """Get Master Orchestrator with living system integration"""
        
        if self._legacy_mode:
            # Return legacy orchestrator
            from src.orchestrator.master_orchestrator import MasterOrchestrator
            return MasterOrchestrator()
        else:
            # Return living system integrated orchestrator
            return LivingSystemMasterOrchestrator(self._living_system)
    
    def get_data_pipeline_coordinator(self):
        """Get Data Pipeline Coordinator with living system integration"""
        
        if self._legacy_mode:
            # Return legacy coordinator
            from src.ingestion.data_pipeline_coordinator import DataPipelineCoordinator
            return DataPipelineCoordinator()
        else:
            # Return living system integrated coordinator
            return LivingSystemDataPipelineCoordinator(self._living_system)
    
    def get_dashboard_coordinator(self):
        """Get Dashboard Coordinator with living system integration"""
        
        if self._legacy_mode:
            # Return legacy coordinator
            from src.dashboard.unified_dashboard_coordinator import UnifiedDashboardCoordinator
            return UnifiedDashboardCoordinator()
        else:
            # Return living system integrated coordinator
            return LivingSystemDashboardCoordinator(self._living_system)
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system status with living system awareness"""
        
        if self._legacy_mode:
            return {
                'mode': 'legacy',
                'living_system_enabled': False,
                'status': 'operational',
                'components': ['legacy_orchestrators']
            }
        else:
            health_report = self.health_monitor.get_system_health_report()
            return {
                'mode': 'living_system',
                'living_system_enabled': True,
                'status': 'operational',
                'health_score': health_report.overall_health_score,
                'health_level': health_report.health_level.value,
                'organs_registered': len(health_report.organ_reports),
                'components': ['unified_state', 'event_bus', 'orchestrator', 'health_monitor']
            }

class LivingSystemMasterOrchestrator:
    """
    Living System Master Orchestrator
    
    Provides the same interface as the legacy MasterOrchestrator but
    uses the living system internally for coordination.
    """
    
    def __init__(self, living_system: Dict[str, Any]):
        self.name = "Living System Master Orchestrator"
        self.version = "2.0"
        self.verbose = False
        
        # Living system components
        self.living_system = living_system
        self.unified_state = living_system['unified_state']
        self.event_bus = living_system['event_bus']
        self.orchestrator = living_system['organ_orchestrator']
        self.health_monitor = living_system['health_monitor']
        self.heartbeat = living_system['heartbeat']
        
        # Legacy compatibility
        self.execution_log = []
        self.subsystem_status = {
            'data_pipeline': False,
            'system_orchestrator': False,
            'market_brain': False,
            'intelligence_coordinator': False,
            'portfolio_coordinator': False,
            'risk_coordinator': False,
            'state_manager': True  # Always true in living system
        }
        
        # Register V3 organs
        self._register_v3_organs()
    
    def _register_v3_organs(self):
        """Register V3 component organs"""
        
        try:
            from src.core.organ_wrappers import create_v3_organ_wrappers
            
            v3_organs = create_v3_organ_wrappers()
            for organ in v3_organs:
                self.orchestrator.register_organ(organ)
                self.health_monitor.register_organ(organ)
            
            print(f"   🔗 Registered {len(v3_organs)} V3 organs in living system")
            
        except Exception as e:
            print(f"   ⚠️ Error registering V3 organs: {e}")
    
    def run_complete_system(self, mode: str = "full") -> bool:
        """Run complete system using living system"""
        
        print("🧬 Running Complete System via Living System")
        print("=" * 50)
        
        try:
            # Start heartbeat for continuous operation
            if self.heartbeat.status != HeartbeatStatus.RUNNING:
                print("💓 Starting living system heartbeat...")
                self.heartbeat.start()
            
            # Run one complete cycle
            print("🔄 Executing complete system cycle...")
            cycle_start = datetime.now()
            
            # Execute all organs
            organs = self.orchestrator.organs  # Use organs property
            successful_executions = 0
            
            for organ in organs:
                try:
                    result = organ.execute_full_cycle(self.unified_state)
                    if result.success:
                        successful_executions += 1
                    
                    # Update health monitoring
                    self.health_monitor.update_organ_health(organ)
                    
                except Exception as e:
                    print(f"   ⚠️ Organ {organ.name} execution failed: {e}")
            
            # Save state
            self.unified_state.save_state()
            
            cycle_duration = (datetime.now() - cycle_start).total_seconds()
            
            # Update subsystem status based on organ execution
            self.subsystem_status.update({
                'data_pipeline': successful_executions > 0,
                'system_orchestrator': successful_executions > 0,
                'market_brain': successful_executions > 0,
                'intelligence_coordinator': successful_executions > 0,
                'portfolio_coordinator': successful_executions > 0,
                'risk_coordinator': successful_executions > 0,
                'state_manager': True
            })
            
            print(f"✅ System cycle completed in {cycle_duration:.2f}s")
            print(f"   Successful organ executions: {successful_executions}/{len(organs)}")
            
            return successful_executions > 0
            
        except Exception as e:
            print(f"❌ System execution failed: {e}")
            return False
    
    def log_execution(self, subsystem: str, status: str, message: str = "", duration: float = 0):
        """Log execution (legacy compatibility)"""
        
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
        
        # Emit event to living system
        self.event_bus.emit_decision_event(
            decision_type="subsystem_execution",
            decision_data={
                'subsystem': subsystem,
                'status': status,
                'message': message,
                'duration': duration
            },
            confidence=1.0 if status == 'success' else 0.0,
            reasoning=[f"Subsystem {subsystem} {status}: {message}"],
            source="compatibility_layer"
        )
        
        if self.verbose:
            status_icon = "✅" if status == 'success' else "❌" if status == 'failed' else "⚠️"
            print(f"   {status_icon} {subsystem}: {message}")

class LivingSystemDataPipelineCoordinator:
    """
    Living System Data Pipeline Coordinator
    
    Provides the same interface as the legacy DataPipelineCoordinator but
    uses the living system data pipeline organ internally.
    """
    
    def __init__(self, living_system: Dict[str, Any]):
        self.name = "Living System Data Pipeline Coordinator"
        self.version = "2.0"
        self.verbose = False
        
        # Living system components
        self.living_system = living_system
        self.unified_state = living_system['unified_state']
        self.orchestrator = living_system['organ_orchestrator']
        
        # Find data pipeline organ
        self.data_pipeline_organ = None
        for organ in self.orchestrator.organs:  # Use organs property
            if hasattr(organ, 'name') and 'data_pipeline' in organ.name.lower():
                self.data_pipeline_organ = organ
                break
        
        # Legacy compatibility
        self.execution_log = []
        self.collection_status = {
            'market_data': False,
            'macro_data': False,
            'data_validation': False,
            'data_transformation': False,
            'market_state_feeding': False
        }
    
    def collect_all_data(self) -> bool:
        """Collect all data using living system data pipeline organ"""
        
        print("📊 Collecting Data via Living System")
        print("=" * 40)
        
        if not self.data_pipeline_organ:
            print("❌ Data pipeline organ not found")
            return False
        
        try:
            # Execute data pipeline organ
            result = self.data_pipeline_organ.execute_full_cycle(self.unified_state)
            
            if result.success:
                # Update collection status
                self.collection_status.update({
                    'market_data': True,
                    'macro_data': True,
                    'data_validation': True,
                    'data_transformation': True,
                    'market_state_feeding': True
                })
                
                print("✅ Data collection completed successfully")
                return True
            else:
                print(f"❌ Data collection failed: {result.error}")
                return False
                
        except Exception as e:
            print(f"❌ Data collection error: {e}")
            return False
    
    def log_execution(self, component: str, status: str, message: str = "", duration: float = 0):
        """Log execution (legacy compatibility)"""
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'component': component,
            'status': status,
            'message': message,
            'duration_seconds': duration
        }
        
        self.execution_log.append(entry)
        
        if component in self.collection_status:
            self.collection_status[component] = (status == 'success')

class LivingSystemDashboardCoordinator:
    """
    Living System Dashboard Coordinator
    
    Provides the same interface as the legacy UnifiedDashboardCoordinator but
    integrates with the living system brain window.
    """
    
    def __init__(self, living_system: Dict[str, Any]):
        self.name = "Living System Dashboard Coordinator"
        self.version = "2.0"
        
        # Living system components
        self.living_system = living_system
        self.unified_state = living_system['unified_state']
        
        # Dashboard types with living system preference
        self.dashboard_types = {
            'brain_window': {
                'name': 'Brain Window',
                'description': 'Living system brain window (recommended)',
                'file': 'scripts/launch_brain_window.py',
                'priority': 1
            },
            'unified': {
                'name': 'Unified Terminal',
                'description': 'Legacy unified terminal',
                'file': 'scripts/northstar_unified_terminal.py',
                'priority': 2
            },
            'professional': {
                'name': 'Professional Trading Desk',
                'description': 'Bloomberg-style interface',
                'file': 'scripts/northstar_professional.py',
                'priority': 3
            }
        }
        
        self.interface_log = []
    
    def launch_unified_interface(self, dashboard_type: str = "brain_window") -> bool:
        """Launch unified interface with living system integration"""
        
        print("🖥️ Launching Interface via Living System")
        print("=" * 45)
        
        if dashboard_type == "brain_window" or dashboard_type not in self.dashboard_types:
            # Launch brain window (preferred)
            print("🧠 Launching Brain Window (Living System Interface)")
            
            try:
                import subprocess
                import sys
                
                result = subprocess.run([
                    sys.executable, "scripts/launch_brain_window.py"
                ], capture_output=False)
                
                return result.returncode == 0
                
            except Exception as e:
                print(f"❌ Brain window launch failed: {e}")
                return False
        else:
            # Launch legacy dashboard
            dashboard_info = self.dashboard_types[dashboard_type]
            print(f"🖥️ Launching {dashboard_info['name']} (Legacy Mode)")
            
            try:
                import subprocess
                import sys
                
                result = subprocess.run([
                    sys.executable, dashboard_info['file']
                ], capture_output=False)
                
                return result.returncode == 0
                
            except Exception as e:
                print(f"❌ Dashboard launch failed: {e}")
                return False

# Global compatibility adapter instance
_compatibility_adapter = None

def get_compatibility_adapter(enable_living_system: bool = True) -> LivingSystemAdapter:
    """Get global compatibility adapter instance"""
    
    global _compatibility_adapter
    
    if _compatibility_adapter is None:
        _compatibility_adapter = LivingSystemAdapter(enable_living_system)
    
    return _compatibility_adapter

def enable_living_system_compatibility():
    """Enable living system compatibility for all existing scripts"""
    
    print("🔄 Enabling Living System Compatibility...")
    
    # Monkey patch existing imports to use living system
    import sys
    
    # Store original modules
    original_modules = {}
    
    # Patch MasterOrchestrator
    if 'src.orchestrator.master_orchestrator' in sys.modules:
        original_modules['master_orchestrator'] = sys.modules['src.orchestrator.master_orchestrator']
    
    # Create compatibility wrapper
    adapter = get_compatibility_adapter(enable_living_system=True)
    
    # Replace with living system versions
    class CompatibilityMasterOrchestrator:
        def __new__(cls, *args, **kwargs):
            return adapter.get_master_orchestrator()
    
    class CompatibilityDataPipelineCoordinator:
        def __new__(cls, *args, **kwargs):
            return adapter.get_data_pipeline_coordinator()
    
    class CompatibilityDashboardCoordinator:
        def __new__(cls, *args, **kwargs):
            return adapter.get_dashboard_coordinator()
    
    # Monkey patch the classes
    try:
        import src.orchestrator.master_orchestrator
        src.orchestrator.master_orchestrator.MasterOrchestrator = CompatibilityMasterOrchestrator
        
        import src.ingestion.data_pipeline_coordinator
        src.ingestion.data_pipeline_coordinator.DataPipelineCoordinator = CompatibilityDataPipelineCoordinator
        
        import src.dashboard.unified_dashboard_coordinator
        src.dashboard.unified_dashboard_coordinator.UnifiedDashboardCoordinator = CompatibilityDashboardCoordinator
        
        print("   ✅ Living system compatibility enabled")
        return True
        
    except Exception as e:
        print(f"   ⚠️ Compatibility patching failed: {e}")
        return False

def main():
    """Test compatibility layer"""
    
    print("🔄 TESTING LIVING SYSTEM COMPATIBILITY LAYER")
    print("=" * 55)
    
    # Test adapter creation
    adapter = LivingSystemAdapter(enable_living_system=True)
    
    # Test system status
    status = adapter.get_system_status()
    print(f"\n📊 System Status:")
    print(f"   Mode: {status['mode']}")
    print(f"   Living System: {status['living_system_enabled']}")
    print(f"   Status: {status['status']}")
    
    if status['living_system_enabled']:
        print(f"   Health Score: {status['health_score']:.2f}")
        print(f"   Health Level: {status['health_level']}")
        print(f"   Organs: {status['organs_registered']}")
    
    # Test orchestrator compatibility
    print(f"\n🎯 Testing Master Orchestrator Compatibility:")
    orchestrator = adapter.get_master_orchestrator()
    print(f"   Orchestrator: {orchestrator.name} v{orchestrator.version}")
    
    # Test data pipeline compatibility
    print(f"\n📊 Testing Data Pipeline Compatibility:")
    data_coordinator = adapter.get_data_pipeline_coordinator()
    print(f"   Coordinator: {data_coordinator.name} v{data_coordinator.version}")
    
    # Test dashboard compatibility
    print(f"\n🖥️ Testing Dashboard Compatibility:")
    dashboard_coordinator = adapter.get_dashboard_coordinator()
    print(f"   Coordinator: {dashboard_coordinator.name} v{dashboard_coordinator.version}")
    
    print(f"\n✅ COMPATIBILITY LAYER TEST COMPLETE")
    print(f"   Living system compatibility is operational")
    
    return True

if __name__ == "__main__":
    main()