#!/usr/bin/env python3
"""
🎯 NORTHSTAR V3 DASHBOARD LAUNCHER
Launch any of the available detailed dashboards

Available Dashboards:
- Ultimate Comprehensive Cockpit (Port 8512) - Most detailed dashboard
- Enhanced Constitutional Cockpit (Port 8505) - Professional styling
- Real Data Cockpit (Port 8506) - Real data integration
- Ultimate Cockpit (Port 8507) - Advanced features
- Simple Constitutional Cockpit (Port 8502) - Clean interface
- Clean Terminal (Port 8503) - Minimal interface
- Brain Window (Port 8501) - Latest living system interface

Usage:
    python launch_all_dashboards.py --list                    # Show all options
    python launch_all_dashboards.py --port 8512              # Launch specific port
    python launch_all_dashboards.py --dashboard ultimate     # Launch by name
"""

import argparse
import subprocess
import sys
import os
from datetime import datetime

class DashboardLauncher:
    """Comprehensive dashboard launcher for all Northstar V3 dashboards"""
    
    def __init__(self):
        self.dashboards = {
            8512: {
                'name': 'Northstar V3 Dashboard (OFFICIAL)',
                'description': 'Official V3 dashboard with comprehensive analytics',
                'script': 'launch_dashboard.py',
                'features': ['Official V3 interface', 'Comprehensive analytics', 'Institutional reporting', 'Professional styling']
            },
            8501: {
                'name': 'Brain Window (Legacy)',
                'description': 'Legacy living system interface',
                'script': 'scripts/launch_brain_window.py',
                'features': ['Living system integration', 'Unified state', 'Real-time intelligence']
            }
        }
        
        # Dashboard aliases
        self.aliases = {
            'v3': 8512,
            'official': 8512,
            'main': 8512,
            'comprehensive': 8512,
            'detailed': 8512,
            'full': 8512,
            'brain': 8501,
            'legacy': 8501
        }
    
    def list_dashboards(self):
        """List all available dashboards"""
        
        print("🎯 NORTHSTAR V3 AVAILABLE DASHBOARDS")
        print("=" * 80)
        print(f"{'Port':<6} {'Name':<30} {'Description'}")
        print("-" * 80)
        
        for port, info in sorted(self.dashboards.items()):
            print(f"{port:<6} {info['name']:<30} {info['description']}")
        
        print("\n🌟 RECOMMENDED DASHBOARDS:")
        print("-" * 40)
        print("🥇 Port 8512 - Ultimate Comprehensive Cockpit (Most detailed)")
        print("🥈 Port 8505 - Enhanced Constitutional Cockpit (Professional)")
        print("🥉 Port 8501 - Brain Window (Latest living system)")
        
        print(f"\n🔗 ACCESS URLs:")
        print("-" * 20)
        for port in sorted(self.dashboards.keys()):
            print(f"   http://localhost:{port} - {self.dashboards[port]['name']}")
        
        print(f"\n📋 LAUNCH COMMANDS:")
        print("-" * 25)
        print("   python launch_dashboard.py                     # V3 Official (RECOMMENDED)")
        print("   python launch_all_dashboards.py --port 8512    # V3 Official")
        print("   python launch_all_dashboards.py --dashboard v3 # V3 Official")
        print("   python launch_all_dashboards.py --port 8501    # Legacy Brain Window")
    
    def launch_dashboard(self, port):
        """Launch dashboard by port"""
        
        if port not in self.dashboards:
            print(f"❌ Port {port} not available")
            self.list_dashboards()
            return False
        
        dashboard = self.dashboards[port]
        script_path = dashboard['script']
        
        print(f"🚀 LAUNCHING {dashboard['name'].upper()}")
        print("=" * 60)
        print(f"Port: {port}")
        print(f"Description: {dashboard['description']}")
        print(f"Features: {', '.join(dashboard['features'])}")
        print(f"URL: http://localhost:{port}")
        print(f"Script: {script_path}")
        print("=" * 60)
        
        if not os.path.exists(script_path):
            print(f"❌ Script not found: {script_path}")
            return False
        
        try:
            print(f"🌐 Opening dashboard in browser...")
            print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"🛑 Press Ctrl+C to stop")
            print()
            
            # Launch the dashboard script
            subprocess.run([sys.executable, script_path])
            
            return True
            
        except KeyboardInterrupt:
            print(f"\n🛑 Dashboard stopped by user")
            return True
        except Exception as e:
            print(f"❌ Error launching dashboard: {e}")
            return False
    
    def launch_by_name(self, name):
        """Launch dashboard by name/alias"""
        
        name_lower = name.lower()
        
        if name_lower in self.aliases:
            port = self.aliases[name_lower]
            return self.launch_dashboard(port)
        else:
            print(f"❌ Dashboard '{name}' not found")
            print(f"Available aliases: {', '.join(self.aliases.keys())}")
            return False

def main():
    """Main function"""
    
    parser = argparse.ArgumentParser(
        description="Launch Northstar V3 Dashboards",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python launch_all_dashboards.py --list                    # Show all options
  python launch_all_dashboards.py --port 8512              # Most detailed dashboard
  python launch_all_dashboards.py --port 8505              # Professional dashboard
  python launch_all_dashboards.py --dashboard comprehensive # By name
  python launch_all_dashboards.py --dashboard enhanced     # By alias

Recommended Dashboards:
  Port 8512 - Ultimate Comprehensive Cockpit (Most detailed)
  Port 8505 - Enhanced Constitutional Cockpit (Professional)
  Port 8501 - Brain Window (Latest living system)
        """
    )
    
    parser.add_argument("--list", action="store_true", help="List all available dashboards")
    parser.add_argument("--port", type=int, help="Launch dashboard by port number")
    parser.add_argument("--dashboard", type=str, help="Launch dashboard by name/alias")
    
    args = parser.parse_args()
    
    launcher = DashboardLauncher()
    
    if args.list:
        launcher.list_dashboards()
        return 0
    
    if args.port:
        success = launcher.launch_dashboard(args.port)
        return 0 if success else 1
    
    if args.dashboard:
        success = launcher.launch_by_name(args.dashboard)
        return 0 if success else 1
    
    # Default: show help and list dashboards
    print("🎯 NORTHSTAR V3 DASHBOARD LAUNCHER")
    print("=" * 50)
    print("No dashboard specified. Here are your options:")
    print()
    launcher.list_dashboards()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())