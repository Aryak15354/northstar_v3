#!/usr/bin/env python3
"""
🚀 LAUNCH INTEGRATED LIVE SYSTEM - NORTHSTAR V3
Comprehensive System Launcher

This script launches the complete integrated Northstar V3 system:
1. Live System Coordinator (background process)
2. Integrated Live Cockpit Dashboard (Streamlit)
3. System monitoring and health checks
4. Automatic data recording and portfolio tracking

Usage:
    python scripts/launch_integrated_live_system.py
    python scripts/launch_integrated_live_system.py --dashboard-only
    python scripts/launch_integrated_live_system.py --coordinator-only
"""

import os
import sys
import subprocess
import threading
import time
import argparse
from datetime import datetime
import signal
import atexit

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.integration.live_system_coordinator import LiveSystemCoordinator

class IntegratedSystemLauncher:
    """Launcher for the complete integrated Northstar V3 system"""
    
    def __init__(self):
        self.coordinator = None
        self.dashboard_process = None
        self.coordinator_thread = None
        self.is_running = False
        
        # Register cleanup handlers
        atexit.register(self.cleanup)
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n🛑 Received signal {signum}, shutting down...")
        self.cleanup()
        sys.exit(0)
    
    def cleanup(self):
        """Clean up processes on shutdown"""
        
        if self.is_running:
            print("🧹 Cleaning up system processes...")
            
            # Stop orchestrator
            if self.coordinator:
                try:
                    self.coordinator.stop_live_system()
                except Exception as e:
                    print(f"⚠️ Error stopping coordinator: {e}")
            
            # Stop dashboard
            if self.dashboard_process:
                try:
                    self.dashboard_process.terminate()
                    self.dashboard_process.wait(timeout=5)
                except Exception as e:
                    print(f"⚠️ Error stopping dashboard: {e}")
                    try:
                        self.dashboard_process.kill()
                    except:
                        pass
            
            self.is_running = False
            print("✅ System cleanup completed")
    
    def start_coordinator(self):
        """Start the live system coordinator"""
        
        print("🎯 Starting Live System Coordinator...")
        
        try:
            self.coordinator = LiveSystemCoordinator()
            self.coordinator.start_live_system()
            
            print("✅ Live System Coordinator started successfully")
            return True
            
        except Exception as e:
            print(f"❌ Failed to start Live System Coordinator: {e}")
            return False
    
    def start_dashboard(self, port=8507):
        """Start the integrated live cockpit dashboard"""
        
        print(f"🖥️ Starting Integrated Live Cockpit on port {port}...")
        
        try:
            dashboard_script = os.path.join(project_root, "src/dashboard/integrated_live_cockpit.py")
            
            # Start Streamlit dashboard
            cmd = [
                sys.executable, "-m", "streamlit", "run",
                dashboard_script,
                "--server.port", str(port),
                "--server.headless", "true",
                "--browser.gatherUsageStats", "false",
                "--server.address", "0.0.0.0"
            ]
            
            self.dashboard_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=project_root
            )
            
            # Wait a moment to check if it started successfully
            time.sleep(3)
            
            if self.dashboard_process.poll() is None:
                print(f"✅ Integrated Live Cockpit started successfully")
                print(f"🌐 Dashboard URL: http://localhost:{port}")
                return True
            else:
                stdout, stderr = self.dashboard_process.communicate()
                print(f"❌ Dashboard failed to start")
                print(f"STDOUT: {stdout.decode()}")
                print(f"STDERR: {stderr.decode()}")
                return False
                
        except Exception as e:
            print(f"❌ Failed to start dashboard: {e}")
            return False
    
    def monitor_system_health(self):
        """Monitor system health and report status"""
        
        print("🏥 Starting system health monitoring...")
        
        while self.is_running:
            try:
                if self.coordinator:
                    status = self.coordinator.get_system_status()
                    
                    # Log health summary every 5 minutes
                    coordinator_status = status['coordinator']
                    unified_state = status['unified_state']
                    
                    health_score = unified_state['system_health']['overall_health_score']
                    orchestrator_running = status['orchestrator']['is_running']
                    
                    print(f"🏥 Health Check - {datetime.now().strftime('%H:%M:%S')}")
                    print(f"   System Health: {health_score:.1%}")
                    print(f"   Coordinator: {'✅' if coordinator_status['is_running'] else '❌'}")
                    print(f"   Orchestrator: {'✅' if orchestrator_running else '❌'}")
                    print(f"   Dashboard: {'✅' if self.dashboard_process and self.dashboard_process.poll() is None else '❌'}")
                
                # Sleep for 5 minutes
                time.sleep(300)
                
            except Exception as e:
                print(f"⚠️ Health monitoring error: {e}")
                time.sleep(60)  # Shorter sleep on error
    
    def launch_full_system(self, dashboard_port=8507):
        """Launch the complete integrated system"""
        
        print("🚀 LAUNCHING INTEGRATED NORTHSTAR V3 SYSTEM")
        print("=" * 60)
        
        self.is_running = True
        
        # Step 1: Start Live System Coordinator
        if not self.start_coordinator():
            print("❌ Failed to start coordinator, aborting launch")
            return False
        
        # Step 2: Wait for coordinator to initialize
        print("⏳ Waiting for coordinator to initialize...")
        time.sleep(5)
        
        # Step 3: Start Dashboard
        if not self.start_dashboard(dashboard_port):
            print("❌ Failed to start dashboard, stopping coordinator")
            self.cleanup()
            return False
        
        # Step 4: Start health monitoring
        health_thread = threading.Thread(target=self.monitor_system_health)
        health_thread.daemon = True
        health_thread.start()
        
        print("\n✅ INTEGRATED SYSTEM LAUNCHED SUCCESSFULLY!")
        print("=" * 60)
        print(f"🎯 Live System Coordinator: Running")
        print(f"🖥️ Integrated Live Cockpit: http://localhost:{dashboard_port}")
        print(f"🏥 Health Monitoring: Active")
        print(f"📊 Data Recording: Active")
        print(f"💼 Portfolio Tracking: Active")
        print("\n🔄 System will run continuously and update every 5 minutes")
        print("📈 Dashboard refreshes automatically every 30 seconds")
        print("🛑 Press Ctrl+C to stop the system")
        
        return True
    
    def launch_coordinator_only(self):
        """Launch only the coordinator (no dashboard)"""
        
        print("🎯 LAUNCHING LIVE SYSTEM COORDINATOR ONLY")
        print("=" * 50)
        
        self.is_running = True
        
        if not self.start_coordinator():
            return False
        
        # Start health monitoring
        health_thread = threading.Thread(target=self.monitor_system_health)
        health_thread.daemon = True
        health_thread.start()
        
        print("\n✅ LIVE SYSTEM COORDINATOR LAUNCHED!")
        print("🔄 System running in background")
        print("🛑 Press Ctrl+C to stop")
        
        return True
    
    def launch_dashboard_only(self, dashboard_port=8507):
        """Launch only the dashboard (assumes coordinator is running)"""
        
        print("🖥️ LAUNCHING INTEGRATED LIVE COCKPIT ONLY")
        print("=" * 50)
        
        self.is_running = True
        
        if not self.start_dashboard(dashboard_port):
            return False
        
        print(f"\n✅ INTEGRATED LIVE COCKPIT LAUNCHED!")
        print(f"🌐 Dashboard URL: http://localhost:{dashboard_port}")
        print("🛑 Press Ctrl+C to stop")
        
        return True
    
    def wait_for_shutdown(self):
        """Wait for shutdown signal"""
        
        try:
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Shutdown requested by user")
            self.cleanup()

def main():
    """Main function"""
    
    parser = argparse.ArgumentParser(description="Launch Integrated Northstar V3 System")
    parser.add_argument("--coordinator-only", action="store_true", 
                       help="Launch only the Live System Coordinator")
    parser.add_argument("--dashboard-only", action="store_true", 
                       help="Launch only the Integrated Live Cockpit")
    parser.add_argument("--port", type=int, default=8507, 
                       help="Dashboard port (default: 8507)")
    parser.add_argument("--test", action="store_true", 
                       help="Run system test and exit")
    
    args = parser.parse_args()
    
    launcher = IntegratedSystemLauncher()
    
    if args.test:
        print("🧪 TESTING INTEGRATED SYSTEM COMPONENTS")
        print("=" * 50)
        
        # Test coordinator
        print("Testing Live System Coordinator...")
        coordinator = LiveSystemCoordinator()
        status = coordinator.get_system_status()
        print(f"✅ Coordinator test passed - {status['coordinator']['name']}")
        
        # Test dashboard components
        print("Testing Dashboard Components...")
        from src.dashboard.integrated_live_cockpit import IntegratedLiveCockpit
        cockpit = IntegratedLiveCockpit()
        live_state = cockpit.load_live_system_state()
        print(f"✅ Dashboard test passed - Status: {live_state['system_status']}")
        
        print("\n✅ All system components tested successfully!")
        return
    
    success = False
    
    if args.coordinator_only:
        success = launcher.launch_coordinator_only()
    elif args.dashboard_only:
        success = launcher.launch_dashboard_only(args.port)
    else:
        success = launcher.launch_full_system(args.port)
    
    if success:
        launcher.wait_for_shutdown()
    else:
        print("❌ System launch failed")
        sys.exit(1)

if __name__ == "__main__":
    main()