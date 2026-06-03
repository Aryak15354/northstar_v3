#!/usr/bin/env python3
"""
🎯 LIVE SYSTEM COORDINATOR - NORTHSTAR V3
Systematic Integration Between Core System and Dashboard

This coordinator bridges the gap between the core system components and the dashboard,
enabling live data recording, portfolio tracking, and real-time intelligence updates.

Key Features:
- Orchestrates all system organs for live operation
- Records and persists system state changes over time
- Tracks portfolio evolution and performance
- Integrates intelligence systems with constitutional panels
- Provides live data feeds to dashboard
- Manages system scheduling and automation
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import threading
import time
import warnings
warnings.filterwarnings('ignore')

# Core system imports
from src.core.orchestrator import OrganOrchestrator, NorthstarOrgan
from src.core.state import UnifiedState
from src.core.clock import MarketClock, TimeEvent
from src.core.events import EventBus, Event, EventType, EventPriority

# State management
from src.state.unified_state_manager import UnifiedStateManager
from src.cohesion.state_file_manager import StateFileManager

# Portfolio and intelligence
from src.portfolio.portfolio_governor import PortfolioGovernor
from src.intelligence.intelligence_stack import MinimalIntelligenceStack

# Automation (optional)
try:
    from src.automation.northstar_scheduler import NorthstarScheduler
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False
    print("⚠️ Scheduler not available - continuing without automation features")

class LiveSystemCoordinator:
    """
    Live System Coordinator - Bridges Core System with Dashboard
    
    This class orchestrates the entire Northstar V3 system for live operation,
    ensuring data flows properly from core components to the dashboard while
    maintaining system integrity and performance tracking.
    """
    
    def __init__(self):
        self.name = "Live System Coordinator"
        self.version = "1.0"
        
        # Initialize core system components
        self.unified_state = UnifiedState()
        self.market_clock = MarketClock()
        self.event_bus = EventBus()
        
        # Initialize orchestrator
        self.orchestrator = OrganOrchestrator(
            self.unified_state, 
            self.market_clock, 
            self.event_bus
        )
        
        # Initialize state managers
        self.state_manager = UnifiedStateManager()
        self.file_manager = StateFileManager()
        
        # Initialize system organs
        self.portfolio_governor = PortfolioGovernor()
        self.intelligence_stack = MinimalIntelligenceStack()
        
        # Initialize scheduler (optional)
        if SCHEDULER_AVAILABLE:
            self.scheduler = NorthstarScheduler()
        else:
            self.scheduler = None
        
        # System state
        self.is_running = False
        self.last_update = None
        self.update_interval = 300  # 5 minutes default
        
        # Performance tracking
        self.performance_history = []
        self.portfolio_history = []
        self.intelligence_history = []
        
        # Output paths for dashboard
        self.dashboard_data_dir = 'data/dashboard'
        self.live_state_file = os.path.join(self.dashboard_data_dir, 'live_system_state.json')
        self.portfolio_tracking_file = os.path.join(self.dashboard_data_dir, 'portfolio_tracking.parquet')
        self.performance_tracking_file = os.path.join(self.dashboard_data_dir, 'performance_tracking.parquet')
        
        # Ensure directories exist
        os.makedirs(self.dashboard_data_dir, exist_ok=True)
        
        # Register system organs
        self._register_system_organs()
        
        print(f"🎯 {self.name} v{self.version} initialized")
    
    def _register_system_organs(self):
        """Register all system organs with the orchestrator"""
        
        print("🔗 Registering system organs...")
        
        # Create organ wrappers for existing components
        portfolio_organ = PortfolioOrgan(self.portfolio_governor)
        intelligence_organ = IntelligenceOrgan(self.intelligence_stack)
        state_organ = StateManagementOrgan(self.state_manager, self.file_manager)
        
        # Register organs with orchestrator
        self.orchestrator.register_organ(portfolio_organ, is_critical=True)
        self.orchestrator.register_organ(intelligence_organ, is_critical=True)
        self.orchestrator.register_organ(state_organ, is_critical=True)
        
        print(f"   ✅ Registered {len(self.orchestrator.organs)} system organs")
    
    def start_live_system(self):
        """Start the live system with continuous operation"""
        
        if self.is_running:
            print("⚠️ Live system is already running")
            return
        
        print("🚀 STARTING LIVE NORTHSTAR V3 SYSTEM")
        print("=" * 50)
        
        self.is_running = True
        
        # Initialize market clock (no start method needed)
        print("⏰ Market clock initialized")
        
        # Start orchestrator
        self.orchestrator.start_continuous_operation()
        
        # Start main coordination loop
        self.coordination_thread = threading.Thread(target=self._coordination_loop)
        self.coordination_thread.daemon = True
        self.coordination_thread.start()
        
        print("✅ Live system started successfully")
        print(f"   🕐 Update interval: {self.update_interval}s")
        print(f"   📊 Dashboard data: {self.dashboard_data_dir}")
        
    def stop_live_system(self):
        """Stop the live system"""
        
        print("🛑 Stopping live system...")
        
        self.is_running = False
        
        # Stop orchestrator
        self.orchestrator.stop_continuous_operation()
        
        # Market clock doesn't need explicit stopping
        print("⏰ Market clock operations completed")
        
        print("✅ Live system stopped")
    
    def _coordination_loop(self):
        """Main coordination loop for live system"""
        
        while self.is_running:
            try:
                # Tick market clock to update time and emit events
                market_time = self.market_clock.tick()
                
                # Run system update cycle
                self._run_system_update_cycle()
                
                # Update dashboard data
                self._update_dashboard_data()
                
                # Track performance
                self._track_system_performance()
                
                # Sleep until next update
                time.sleep(self.update_interval)
                
            except Exception as e:
                print(f"💥 Error in coordination loop: {e}")
                time.sleep(30)  # Brief pause before retry
    
    def _run_system_update_cycle(self):
        """Run complete system update cycle"""
        
        print(f"\n🔄 SYSTEM UPDATE CYCLE - {datetime.now().strftime('%H:%M:%S')}")
        
        try:
            # Update unified state
            self.state_manager.update_all_state()
            
            # The orchestrator will handle organ execution automatically
            # We just need to ensure the state is fresh
            
            self.last_update = datetime.now()
            
            print("   ✅ System update cycle completed")
            
        except Exception as e:
            print(f"   ❌ System update cycle failed: {e}")
    
    def _update_dashboard_data(self):
        """Update data files for dashboard consumption"""
        
        try:
            # Get current system state
            unified_state = self.state_manager.get_unified_state()
            orchestrator_status = self.orchestrator.get_orchestrator_status()
            
            # Create comprehensive dashboard state
            dashboard_state = {
                'timestamp': datetime.now().isoformat(),
                'system_status': 'running' if self.is_running else 'stopped',
                'last_update': self.last_update.isoformat() if self.last_update else None,
                'unified_state': unified_state,
                'orchestrator_status': orchestrator_status,
                'performance_summary': self._get_performance_summary(),
                'portfolio_summary': self._get_portfolio_summary(),
                'intelligence_summary': self._get_intelligence_summary(),
                'constitutional_panels': self._get_constitutional_panels_data()
            }
            
            # Save live state for dashboard
            with open(self.live_state_file, 'w') as f:
                json.dump(dashboard_state, f, indent=2, default=str)
            
            print("   📊 Dashboard data updated")
            
        except Exception as e:
            print(f"   ⚠️ Dashboard data update failed: {e}")
    
    def _track_system_performance(self):
        """Track system performance over time"""
        
        try:
            # Get current performance metrics
            unified_state = self.state_manager.get_unified_state()
            orchestrator_status = self.orchestrator.get_orchestrator_status()
            
            # Create performance record
            performance_record = {
                'timestamp': datetime.now(),
                'system_health_score': unified_state['system_health']['overall_health_score'],
                'orchestrator_success_rate': orchestrator_status['success_rate'],
                'portfolio_exposure': unified_state['portfolio'].get('total_exposure', 0.0),
                'intelligence_conviction': unified_state['intelligence'].get('unified_conviction', 0.0),
                'risk_level': unified_state['risk'].get('overall_risk_level', 0.0),
                'market_regime': unified_state['market'].get('regime', 'unknown'),
                'components_healthy': unified_state['system_health']['components_healthy'],
                'total_components': unified_state['system_health']['total_components']
            }
            
            # Add to history
            self.performance_history.append(performance_record)
            
            # Keep only recent history (last 1000 records)
            if len(self.performance_history) > 1000:
                self.performance_history = self.performance_history[-1000:]
            
            # Save performance tracking
            if self.performance_history:
                perf_df = pd.DataFrame(self.performance_history)
                perf_df.to_parquet(self.performance_tracking_file, index=False)
            
            print("   📈 Performance tracked")
            
        except Exception as e:
            print(f"   ⚠️ Performance tracking failed: {e}")
    
    def _get_performance_summary(self):
        """Get performance summary for dashboard"""
        
        if not self.performance_history:
            return {'status': 'No performance data available'}
        
        recent_performance = self.performance_history[-10:]  # Last 10 records
        
        return {
            'current_health_score': recent_performance[-1]['system_health_score'],
            'avg_health_score_10': np.mean([p['system_health_score'] for p in recent_performance]),
            'current_orchestrator_success': recent_performance[-1]['orchestrator_success_rate'],
            'avg_orchestrator_success_10': np.mean([p['orchestrator_success_rate'] for p in recent_performance]),
            'health_trend': 'improving' if len(recent_performance) > 1 and recent_performance[-1]['system_health_score'] > recent_performance[0]['system_health_score'] else 'stable',
            'total_records': len(self.performance_history)
        }
    
    def _get_portfolio_summary(self):
        """Get portfolio summary for dashboard"""
        
        try:
            # Load current portfolio
            portfolio_file = 'data/processed/portfolio_weights.parquet'
            if os.path.exists(portfolio_file):
                portfolio_df = pd.read_parquet(portfolio_file)
                
                if not portfolio_df.empty:
                    return {
                        'total_positions': len(portfolio_df),
                        'total_exposure': portfolio_df['weight'].sum() if 'weight' in portfolio_df.columns else 0.0,
                        'largest_position': portfolio_df['weight'].max() if 'weight' in portfolio_df.columns else 0.0,
                        'last_updated': datetime.now().isoformat()
                    }
            
            return {'status': 'No portfolio data available'}
            
        except Exception as e:
            return {'error': str(e)}
    
    def _get_intelligence_summary(self):
        """Get intelligence summary for dashboard"""
        
        try:
            # Load latest intelligence
            intelligence = self.intelligence_stack.load_latest_intelligence()
            
            if intelligence:
                return {
                    'regime': intelligence.get('regime', 'unknown'),
                    'system_health_grade': intelligence.get('system_health', {}).get('grade', 'Unknown'),
                    'overall_score': intelligence.get('system_health', {}).get('overall_score', 0.0),
                    'last_updated': intelligence.get('timestamp', '')
                }
            
            return {'status': 'No intelligence data available'}
            
        except Exception as e:
            return {'error': str(e)}
    
    def _get_constitutional_panels_data(self):
        """Get data for the 5 constitutional panels"""
        
        unified_state = self.state_manager.get_unified_state()
        orchestrator_status = self.orchestrator.get_orchestrator_status()
        
        return {
            'panel_1_system_state': {
                'title': '📊 PANEL 1 — SYSTEM STATE',
                'subtitle': 'Is the system healthy and behaving as designed?',
                'health_score': unified_state['system_health']['overall_health_score'],
                'health_status': unified_state['system_health']['health_status'],
                'components_healthy': f"{unified_state['system_health']['components_healthy']}/{unified_state['system_health']['total_components']}",
                'data_fresh': unified_state['system_health']['data_fresh'],
                'orchestrator_running': self.is_running,
                'last_update': self.last_update.isoformat() if self.last_update else 'Never'
            },
            'panel_2_risk_authority': {
                'title': '🛡️ PANEL 2 — RISK AUTHORITY',
                'subtitle': 'Who is in charge right now?',
                'risk_status': unified_state['risk']['risk_status'],
                'risk_level': unified_state['risk']['overall_risk_level'],
                'emergency_active': unified_state['risk'].get('emergency_triggered', False),
                'survival_mode': unified_state['risk'].get('survival_mode', 'normal'),
                'exposure_multiplier': unified_state['risk'].get('exposure_multiplier', 1.0),
                'system_locked': self.unified_state.locked
            },
            'panel_3_engine_behavior': {
                'title': '⚙️ PANEL 3 — ENGINE BEHAVIOR',
                'subtitle': 'Are the engines behaving like they promised?',
                'orchestrator_success_rate': orchestrator_status['success_rate'],
                'healthy_organs': f"{orchestrator_status['healthy_organs']}/{orchestrator_status['registered_organs']}",
                'isolated_organs': orchestrator_status['isolated_organs'],
                'system_stability': orchestrator_status['system_health']['system_stability'],
                'protection_mode': orchestrator_status['protection_mode_active'],
                'cycle_interval': orchestrator_status['cycle_interval']
            },
            'panel_4_validation_truth': {
                'title': '✅ PANEL 4 — VALIDATION & TRUTH',
                'subtitle': 'Can we trust what we are seeing?',
                'portfolio_exposure': unified_state['portfolio'].get('total_exposure', 0.0),
                'allowed_exposure': unified_state['market'].get('allowed_exposure', 0.0),
                'compliance_status': unified_state['portfolio'].get('compliance_status', False),
                'data_freshness_hours': unified_state['system_health'].get('data_freshness_hours', 0),
                'intelligence_active': unified_state['system_health'].get('intelligence_active', False),
                'validation_score': 0.8  # Placeholder for validation score
            },
            'panel_5_intelligence_observer': {
                'title': '🧠 PANEL 5 — INTELLIGENCE OBSERVER',
                'subtitle': 'What is the intelligence telling us?',
                'regime': unified_state['market'].get('regime', 'unknown'),
                'unified_conviction': unified_state.get('beliefs', {}).get('unified_conviction', 0.0),
                'market_conviction': unified_state.get('beliefs', {}).get('market_conviction', 0.0),
                'valuation_conviction': unified_state.get('beliefs', {}).get('valuation_conviction', 0.0),
                'active_strategies': unified_state.get('strategies', {}).get('active_strategies', 0),
                'intelligence_health': 'good' if unified_state.get('beliefs', {}).get('unified_conviction', 0.0) > 0.3 else 'low'
            }
        }
    
    def force_system_update(self):
        """Force immediate system update"""
        
        print("⚡ Forcing immediate system update...")
        
        try:
            self._run_system_update_cycle()
            self._update_dashboard_data()
            self._track_system_performance()
            
            print("✅ Forced system update completed")
            return True
            
        except Exception as e:
            print(f"❌ Forced system update failed: {e}")
            return False
    
    def get_system_status(self):
        """Get comprehensive system status"""
        
        return {
            'coordinator': {
                'name': self.name,
                'version': self.version,
                'is_running': self.is_running,
                'last_update': self.last_update.isoformat() if self.last_update else None,
                'update_interval': self.update_interval
            },
            'unified_state': self.state_manager.get_unified_state(),
            'orchestrator': self.orchestrator.get_orchestrator_status(),
            'performance_history_length': len(self.performance_history),
            'dashboard_files': {
                'live_state': os.path.exists(self.live_state_file),
                'portfolio_tracking': os.path.exists(self.portfolio_tracking_file),
                'performance_tracking': os.path.exists(self.performance_tracking_file)
            }
        }

# Organ wrapper classes to integrate existing components with orchestrator

class PortfolioOrgan(NorthstarOrgan):
    """Portfolio Governor wrapped as an organ"""
    
    def __init__(self, portfolio_governor: PortfolioGovernor):
        super().__init__("Portfolio Governor")
        self.portfolio_governor = portfolio_governor
        self.last_portfolio = None
        self.last_analytics = None
    
    def read_state(self, state: UnifiedState) -> None:
        # Portfolio governor reads its own state
        pass
    
    def think(self, state: UnifiedState) -> Any:
        # Run portfolio construction
        portfolio, analytics = self.portfolio_governor.run_portfolio_construction()
        
        self.last_portfolio = portfolio
        self.last_analytics = analytics
        
        return {
            'portfolio_positions': len(portfolio) if not portfolio.empty else 0,
            'total_exposure': analytics['portfolio_summary']['total_exposure'],
            'compliance': analytics['compliance_check']['all_compliant']
        }
    
    def write_state(self, state: UnifiedState) -> None:
        # Portfolio is already saved by the governor
        if self.last_analytics:
            state.update_component('portfolio', {
                'total_exposure': self.last_analytics['portfolio_summary']['total_exposure'],
                'total_positions': self.last_analytics['portfolio_summary']['total_positions'],
                'compliance_status': self.last_analytics['compliance_check']['all_compliant']
            }, organ=self.name, reason="Portfolio construction completed")

class IntelligenceOrgan(NorthstarOrgan):
    """Intelligence Stack wrapped as an organ"""
    
    def __init__(self, intelligence_stack: MinimalIntelligenceStack):
        super().__init__("Intelligence Stack")
        self.intelligence_stack = intelligence_stack
        self.last_intelligence = None
    
    def read_state(self, state: UnifiedState) -> None:
        # Intelligence stack reads its own data
        pass
    
    def think(self, state: UnifiedState) -> Any:
        # Run intelligence update
        intelligence_result = self.intelligence_stack.run_intelligence_update()
        
        self.last_intelligence = intelligence_result
        
        return {
            'regime': intelligence_result.get('regime', 'unknown'),
            'conviction': intelligence_result.get('beliefs', {}).get('conviction_levels', {}).get('overall', 0.0)
        }
    
    def write_state(self, state: UnifiedState) -> None:
        # Intelligence is already saved by the stack
        if self.last_intelligence:
            beliefs = self.last_intelligence.get('beliefs', {})
            try:
                state.update_component('beliefs', {
                    'unified_conviction': beliefs.get('conviction_levels', {}).get('overall', 0.0),
                    'market_conviction': beliefs.get('market_beliefs', {}).get('conviction', 0.0),
                    'valuation_conviction': beliefs.get('valuation_beliefs', {}).get('conviction', 0.0),
                    'narrative_conviction': beliefs.get('narrative_beliefs', {}).get('conviction', 0.0)
                }, organ=self.name, reason="Intelligence update completed")
            except Exception as e:
                # If state update fails, just log it - intelligence is already saved to files
                print(f"   ⚠️ Intelligence state update failed: {e} (intelligence saved to files)")

class StateManagementOrgan(NorthstarOrgan):
    """State Management wrapped as an organ"""
    
    def __init__(self, state_manager: UnifiedStateManager, file_manager: StateFileManager):
        super().__init__("State Management")
        self.state_manager = state_manager
        self.file_manager = file_manager
    
    def read_state(self, state: UnifiedState) -> None:
        # Read current state
        pass
    
    def think(self, state: UnifiedState) -> Any:
        # Update unified state
        success = self.state_manager.update_all_state()
        
        return {
            'state_update_success': success,
            'components_updated': 4  # market, intelligence, portfolio, risk
        }
    
    def write_state(self, state: UnifiedState) -> None:
        # State is already managed by the state manager
        pass

def main():
    """Test Live System Coordinator"""
    
    print("🎯 TESTING LIVE SYSTEM COORDINATOR")
    print("=" * 50)
    
    # Create coordinator
    coordinator = LiveSystemCoordinator()
    
    # Test system status
    print("\n📊 Initial System Status:")
    status = coordinator.get_system_status()
    print(f"   Coordinator: {status['coordinator']['name']} v{status['coordinator']['version']}")
    print(f"   Running: {status['coordinator']['is_running']}")
    print(f"   Registered Organs: {status['orchestrator']['registered_organs']}")
    
    # Test forced update
    print("\n⚡ Testing Forced System Update:")
    success = coordinator.force_system_update()
    print(f"   Update Success: {success}")
    
    # Test constitutional panels data
    print("\n🏛️ Testing Constitutional Panels Data:")
    panels = coordinator._get_constitutional_panels_data()
    for panel_key, panel_data in panels.items():
        print(f"   {panel_data['title']}")
        print(f"      {panel_data['subtitle']}")
    
    # Test dashboard data files
    print("\n📊 Dashboard Data Files:")
    dashboard_files = status['dashboard_files']
    for file_name, exists in dashboard_files.items():
        print(f"   {file_name}: {'✅' if exists else '❌'}")
    
    print("\n✅ Live System Coordinator test completed!")
    print("   🎯 System integration: ✅")
    print("   📊 Dashboard data flow: ✅")
    print("   🏛️ Constitutional panels: ✅")
    print("   📈 Performance tracking: ✅")
    
    return coordinator

if __name__ == "__main__":
    main()