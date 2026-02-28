#!/usr/bin/env python3
"""
🖥️ UNIFIED DASHBOARD COORDINATOR - NORTHSTAR V3 PHASE 5
Master Dashboard System with Unified Interface

This is the unified coordinator that orchestrates all dashboard and interface
components into a single, coherent user experience.

Coordinates:
- Professional Trading Desk (Bloomberg-style interface)
- Intelligence Organism (AI brain visualization)
- Unified Terminal (War room + Portfolio + Intelligence)
- Real-time data synchronization across all interfaces
- Unified state management for all dashboards

Usage:
from src.cohesion.dependency_container import get_dependency_container

    from src.dashboard.unified_dashboard_coordinator import UnifiedDashboardCoordinator
    
    coordinator = UnifiedDashboardCoordinator()
    success = coordinator.launch_unified_interface()
"""

import pandas as pd
import numpy as np
import os
import sys
import json
import subprocess
import streamlit as st
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Add project root to path for imports
if project_root not in sys.path:
    class UnifiedDashboardCoordinator:
        pass
    """
    Unified Dashboard Coordinator - Master Interface System
    
    Orchestrates all dashboard components to create a unified user experience
    with real-time data synchronization and coordinated interface management.
    """
    
    def __init__(self):
        self.name = "Unified Dashboard Coordinator"
        self.version = "1.0"
        
        # File paths
        self.paths = {
            'dashboard_snapshot': 'data/processed/cache/dashboard_snapshot.parquet',
            'unified_state': 'data/processed/unified_state.json',
            'dashboard_config': 'data/dashboard/unified_config.json',
            'interface_log': 'data/dashboard/interface_coordination_log.json'
        }
        
        # Ensure directories exist
        os.makedirs('data/dashboard', exist_ok=True)
        os.makedirs('data/processed/cache', exist_ok=True)
        
        # Available dashboard types
        self.dashboard_types = {
            'unified': {
                'name': 'Unified Terminal',
                'description': 'War Room + Portfolio + Intelligence in one interface',
                'file': 'scripts/northstar_unified_terminal.py',
                'priority': 1
            },
            'professional': {
                'name': 'Professional Trading Desk',
                'description': 'Bloomberg-style professional interface',
                'file': 'scripts/northstar_professional.py',
                'priority': 2
            },
            'trading-desk': {
                'name': 'Trading Desk',
                'description': 'Institutional trading desk interface',
                'file': 'scripts/northstar_trading_desk.py',
                'priority': 3
            },
            'intelligence': {
                'name': 'Intelligence Organism',
                'description': 'AI brain visualization and analysis',
                'file': 'scripts/northstar_intelligence_organism.py',
                'priority': 4
            },
            'react': {
                'name': 'React Terminal',
                'description': 'Modern React-based interface',
                'file': 'scripts/launchers/launch_northstar_terminal.py',
                'priority': 5
            }
        }
        
        # Interface coordination tracking
        self.interface_log = []
    
    def log_interface_action(self, interface, action, status, message="", duration=0):
        """Log interface coordination activities"""
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'interface': interface,
            'action': action,
            'status': status,
            'message': message,
            'duration_seconds': duration
        }
        
        self.interface_log.append(entry)
        
        # Print status
        status_icon = "✅" if status == 'success' else "❌" if status == 'failed' else "⚠️"
        print(f"   {status_icon} {interface}: {message}")
    
    def ensure_unified_data_snapshot(self):
        """Step 1: Ensure unified data snapshot is available"""
        
        print("📊 STEP 1: UNIFIED DATA SNAPSHOT")
        print("-" * 35)
        
        start_time = datetime.now()
        
        try:
            # Check if snapshot exists and is recent
            snapshot_exists = os.path.exists(self.paths['dashboard_snapshot'])
            snapshot_fresh = False
            
            if snapshot_exists:
                snapshot_age = (datetime.now() - datetime.fromtimestamp(
                    os.path.getmtime(self.paths['dashboard_snapshot'])
                )).total_seconds()
                snapshot_fresh = snapshot_age < 300  # 5 minutes
            
            if not snapshot_exists or not snapshot_fresh:
                # Build new snapshot
                self.build_unified_snapshot()
            
            duration = (datetime.now() - start_time).total_seconds()
            
            if os.path.exists(self.paths['dashboard_snapshot']):
                self.log_interface_action('data_snapshot', 'ensure', 'success', 
                                        "Unified data snapshot ready", duration)
                return True
            else:
                self.log_interface_action('data_snapshot', 'ensure', 'failed', 
                                        "Failed to create unified snapshot", duration)
                return False
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_interface_action('data_snapshot', 'ensure', 'failed', str(e), duration)
            return False
    
    def build_unified_snapshot(self):
        """Build unified dashboard snapshot from all system components"""
        
        print("   🔄 Building unified dashboard snapshot...")
        
        snapshot = {
            'timestamp': datetime.now().isoformat(),
            'coordinator_version': self.version,
            'market': {},
            'portfolio': {},
            'intelligence': {},
            'risk': {},
            'strategies': {},
            'execution': {}
        }
        
        # Load market state
        try:
            if os.path.exists('data/processed/market_state.parquet'):
                market_df = pd.read_parquet('data/processed/market_state.parquet')
                if not market_df.empty:
                    latest = market_df.iloc[-1]
                    snapshot['market'] = {
                        'regime': latest.get('macro_regime', 'neutral'),
                        'allowed_exposure': latest.get('allowed_exposure', 60),
                        'risk_on_prob': latest.get('risk_on_probability', 0.5),
                        'liquidity_index': latest.get('liquidity_index', 50),
                        'market_stability': latest.get('market_stability', 50),
                        'coherence_score': latest.get('coherence_mean_60', 0.7)
                    }
        except Exception as e:
            print(f"   ⚠️ Market state load error: {e}")
        
        # Load portfolio state
        try:
            if os.path.exists('data/processed/portfolio_weights.parquet'):
                portfolio_df = pd.read_parquet('data/processed/portfolio_weights.parquet')
                if not portfolio_df.empty:
                    total_exposure = portfolio_df['final_weight'].sum()
                    positions = len(portfolio_df)
                    snapshot['portfolio'] = {
                        'total_exposure': float(total_exposure),
                        'positions': int(positions),
                        'largest_position': float(portfolio_df['final_weight'].max()),
                        'top_positions': portfolio_df.nlargest(5, 'final_weight')[['ticker', 'final_weight']].to_dict('records')
                    }
        except Exception as e:
            print(f"   ⚠️ Portfolio state load error: {e}")
        
        # Load intelligence state
        try:
            if os.path.exists('data/processed/capital_allocations.json'):
                with open('data/processed/capital_allocations.json', 'r') as f:
                    allocations = json.load(f)
                    snapshot['intelligence'] = {
                        'strategy_count': len(allocations.get('allocations', {})),
                        'top_strategy': max(allocations.get('allocations', {}).items(), 
                                          key=lambda x: x[1], default=('none', 0))[0],
                        'allocation_entropy': self.calculate_allocation_entropy(allocations.get('allocations', {}))
                    }
        except Exception as e:
            print(f"   ⚠️ Intelligence state load error: {e}")
        
        # Load risk state
        try:
            if os.path.exists('data/risk/unified_risk_state.json'):
                with open('data/risk/unified_risk_state.json', 'r') as f:
                    risk_state = json.load(f)
                    snapshot['risk'] = {
                        'emergency_active': risk_state.get('emergency_state', {}).get('emergency_active', False),
                        'risk_level': risk_state.get('emergency_state', {}).get('risk_level', 0.0),
                        'final_exposure_cap': risk_state.get('risk_authority', {}).get('final_exposure_cap', 1.0),
                        'authority_level': risk_state.get('risk_authority', {}).get('active_authority', 'SYSTEM')
                    }
        except Exception as e:
            print(f"   ⚠️ Risk state load error: {e}")
        
        # Save snapshot
        try:
            snapshot_df = pd.DataFrame([snapshot])
            snapshot_df.to_parquet(self.paths['dashboard_snapshot'], index=False)
            print(f"   ✅ Unified snapshot built with {len(snapshot)} components")
        except Exception as e:
            # Fallback to JSON if Parquet fails with complex nested data
            print(f"   ⚠️ Parquet save failed, using JSON fallback: {e}")
            json_path = self.paths['dashboard_snapshot'].replace('.parquet', '.json')
            with open(json_path, 'w') as f:
                json.dump(snapshot, f, indent=2, default=str)
            print(f"   ✅ Unified snapshot built as JSON with {len(snapshot)} components")
    
    def calculate_allocation_entropy(self, allocations):
        """Calculate entropy of allocations for diversification measure"""
        
        if not allocations:
            return 0
        
        values = np.array(list(allocations.values()))
        values = values[values > 0]
        
        if len(values) == 0:
            return 0
        
        probs = values / values.sum()
        entropy = -np.sum(probs * np.log(probs + 1e-10))
        
        return float(entropy)
    
    def detect_available_interfaces(self):
        """Step 2: Detect available dashboard interfaces"""
        
        print("\n🔍 STEP 2: INTERFACE DETECTION")
        print("-" * 35)
        
        start_time = datetime.now()
        available_interfaces = {}
        
        try:
            for interface_id, config in self.dashboard_types.items():
                interface_file = config['file']
                
                # Check if interface file exists
                if os.path.exists(interface_file):
                    # Check if interface has required dependencies
                    interface_available = self.check_interface_dependencies(interface_id, interface_file)
                    
                    if interface_available:
                        available_interfaces[interface_id] = config
                        self.log_interface_action(interface_id, 'detect', 'success', 
                                                f"{config['name']} available")
                    else:
                        self.log_interface_action(interface_id, 'detect', 'warning', 
                                                f"{config['name']} has missing dependencies")
                else:
                    self.log_interface_action(interface_id, 'detect', 'failed', 
                                            f"{config['name']} file not found: {interface_file}")
            
            duration = (datetime.now() - start_time).total_seconds()
            
            if available_interfaces:
                print(f"   ✅ Detected {len(available_interfaces)} available interfaces")
                return available_interfaces
            else:
                print(f"   ❌ No interfaces available")
                return {}
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_interface_action('interface_detection', 'detect', 'failed', str(e), duration)
            return {}
    
    def check_interface_dependencies(self, interface_id, interface_file):
        """Check if interface has required dependencies"""
        
        try:
            # Basic checks for different interface types
            if interface_id == 'react':
                # Check if Node.js and React dependencies are available
                return os.path.exists('northstar-terminal/package.json')
            elif interface_id in ['unified', 'professional', 'trading-desk']:
                # Check if Streamlit is available
                # Dependency injection - import streamlit
                pass  # Fallback: # Fallback to legacy interfaces if Brain Window not available
            if preferred_interface and preferred_interface in available_interfaces:
                selected_interface = preferred_interface
            else:
                # Select highest priority available interface
                sorted_interfaces = sorted(available_interfaces.items(), 
                                         key=lambda x: x[1]['priority'])
                selected_interface = sorted_interfaces[0][0] if sorted_interfaces else None
            
            if not selected_interface:
                self.log_interface_action('interface_launch', 'launch', 'failed', 
                                        "No interfaces available to launch", 0)
                return False
            
            interface_config = available_interfaces[selected_interface]
            interface_file = interface_config['file']
            
            print(f"   🎯 Launching {interface_config['name']} (Legacy)...")
            
            # Launch the interface
            if selected_interface == 'react':
                # Launch React interface
                success = self.launch_react_interface()
            else:
                # Launch Python interface
                success = self.launch_python_interface(interface_file)
            
            duration = (datetime.now() - start_time).total_seconds()
            
            if success:
                self.log_interface_action(selected_interface, 'launch', 'success', 
                                        f"{interface_config['name']} launched successfully", duration)
                return True
            else:
                self.log_interface_action(selected_interface, 'launch', 'failed', 
                                        f"{interface_config['name']} launch failed", duration)
                return False
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_interface_action('interface_launch', 'launch', 'failed', str(e), duration)
            return False
    
    def launch_brain_window(self):
        """Launch Brain Window (Living System Interface)"""
        
        try:
            brain_window_path = 'src/dashboard/brain_window.py'
            
            # Use subprocess to launch Streamlit interface
            cmd = [sys.executable, '-m', 'streamlit', 'run', brain_window_path, 
                   '--server.headless', 'true', '--server.port', '8501']
            
            # Start the process
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            print(f"   ✅ Brain Window launched: {brain_window_path}")
            print(f"   🌐 Access at: http://localhost:8501")
            print(f"   🧠 Living System Interface - Reads from Unified State only")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Failed to launch Brain Window: {e}")
            return False
    
    def launch_python_interface(self, interface_file):
        """Launch Python-based interface (Streamlit)"""
        
        try:
            # Use subprocess to launch Streamlit interface
            cmd = [sys.executable, '-m', 'streamlit', 'run', interface_file, '--server.headless', 'true']
            
            # Start the process
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            print(f"   ✅ Interface launched: {interface_file}")
            print(f"   🌐 Access at: http://localhost:8501")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Failed to launch {interface_file}: {e}")
            return False
    
    def launch_react_interface(self):
        """Launch React-based interface"""
        
        try:
            # Change to React directory and start development server
            react_dir = 'northstar-terminal'
            
            if not os.path.exists(react_dir):
                print(f"   ❌ React directory not found: {react_dir}")
                return False
            
            # Start React development server
            cmd = ['npm', 'start']
            process = subprocess.Popen(cmd, cwd=react_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            print(f"   ✅ React interface launched")
            print(f"   🌐 Access at: http://localhost:3000")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Failed to launch React interface: {e}")
            return False
    
    def save_coordination_state(self):
        """Step 4: Save coordination state and logs"""
        
        print("\n💾 STEP 4: SAVE COORDINATION STATE")
        print("-" * 35)
        
        start_time = datetime.now()
        
        try:
            # Save interface coordination log
            coordination_summary = {
                'timestamp': datetime.now().isoformat(),
                'coordinator_version': self.version,
                'interface_log': self.interface_log,
                'available_interfaces': len([entry for entry in self.interface_log if entry['status'] == 'success' and entry['action'] == 'detect']),
                'launched_interfaces': len([entry for entry in self.interface_log if entry['status'] == 'success' and entry['action'] == 'launch']),
                'success_rate': sum(1 for entry in self.interface_log if entry['status'] == 'success') / len(self.interface_log) if self.interface_log else 0,
                'total_duration': sum(entry['duration_seconds'] for entry in self.interface_log)
            }
            
            with open(self.paths['interface_log'], 'w') as f:
                json.dump(coordination_summary, f, indent=2, default=str)
            
            # Save dashboard configuration
            dashboard_config = {
                'timestamp': datetime.now().isoformat(),
                'coordinator_version': self.version,
                'dashboard_types': self.dashboard_types,
                'data_paths': self.paths
            }
            
            with open(self.paths['dashboard_config'], 'w') as f:
                json.dump(dashboard_config, f, indent=2, default=str)
            
            duration = (datetime.now() - start_time).total_seconds()
            self.log_interface_action('coordination_state', 'save', 'success', 
                                    "Coordination state saved", duration)
            
            return True
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_interface_action('coordination_state', 'save', 'failed', str(e), duration)
            return False
    
    def launch_unified_interface(self, preferred_interface=None):
        """Main unified interface launch process"""
        
        print("🖥️ UNIFIED DASHBOARD COORDINATOR")
        print("=" * 60)
        
        total_start_time = datetime.now()
        
        # Step 1: Ensure unified data snapshot
        snapshot_success = self.ensure_unified_data_snapshot()
        
        # Step 2: Detect available interfaces
        available_interfaces = self.detect_available_interfaces()
        
        # Step 3: Launch primary interface
        launch_success = self.launch_primary_interface(available_interfaces, preferred_interface)
        
        # Step 4: Save coordination state
        save_success = self.save_coordination_state()
        
        # Calculate results
        total_duration = (datetime.now() - total_start_time).total_seconds()
        successful_steps = sum([snapshot_success, bool(available_interfaces), launch_success, save_success])
        
        # Print summary
        print(f"\n🖥️ UNIFIED DASHBOARD COORDINATION COMPLETE")
        print("=" * 60)
        print(f"Duration: {total_duration:.1f} seconds")
        print(f"Success: {successful_steps}/4 steps")
        print(f"Available Interfaces: {len(available_interfaces)}")
        
        if launch_success:
            print(f"🎉 Dashboard interface launched successfully!")
            print(f"🌐 Access your unified Northstar interface in your browser")
        
        return successful_steps >= 3  # At least 3 steps must succeed

def main():
    """Main execution function"""
    
    coordinator = UnifiedDashboardCoordinator()
    success = coordinator.launch_unified_interface()
    
    return success

if __name__ == "__main__":
    main()