#!/usr/bin/env python3
"""
🚀 NORTHSTAR TERMINAL LAUNCHER
Launch the complete Northstar Terminal system with all components

This script:
1. Builds the unified dashboard snapshot
2. Starts the FastAPI backend server
3. Launches the Streamlit terminal (optional)
4. Provides instructions for the React terminal
"""

import subprocess
import sys
import os
import time
import signal
from datetime import datetime
import threading

def print_banner():
    """Print the Northstar Terminal banner"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                    🌟 NORTHSTAR TERMINAL 🌟                   ║
║                                                              ║
║              Professional Hedge Fund Intelligence            ║
║                        Terminal v3.0                        ║
║                                                              ║
║  • Bloomberg-grade UI                                        ║
║  • Real-time intelligence                                    ║
║  • Strategy evolution tracking                               ║
║  • Bayesian belief systems                                   ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")

def check_dependencies():
    """Check if required dependencies are installed"""
    print("🔍 Checking dependencies...")
    
    required_packages = [
        'streamlit', 'fastapi', 'uvicorn', 'pandas', 'plotly', 'numpy'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"   ✅ {package}")
        except ImportError:
            missing.append(package)
            print(f"   ❌ {package}")
    
    if missing:
        print(f"\n❌ Missing packages: {', '.join(missing)}")
        print("Install with: pip install " + " ".join(missing))
        return False
    
    print("✅ All Python dependencies found")
    return True

def build_snapshot():
    """Build the unified dashboard snapshot"""
    print("\n🧠 Building unified dashboard snapshot...")
    
    try:
        # Import and run the snapshot builder
        
        from build_dashboard_snapshot import build_unified_snapshot
        
        snapshot = build_unified_snapshot()
        print("✅ Dashboard snapshot built successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error building snapshot: {e}")
        return False

def start_api_server():
    """Start the FastAPI backend server"""
    print("\n🔌 Starting FastAPI backend server...")
    
    try:
        # Change to the correct directory
        api_dir = os.path.join(os.getcwd(), 'src', 'api')
        
        # Start the server
        process = subprocess.Popen([
            sys.executable, '-m', 'uvicorn', 'server:app',
            '--host', '0.0.0.0',
            '--port', '8000',
            '--reload'
        ], cwd=api_dir)
        
        print("✅ FastAPI server starting on http://localhost:8000")
        print("   API endpoints:")
        print("   • GET /snapshot - Unified dashboard data")
        print("   • GET /timeseries/{name} - Time series data")
        print("   • GET /strategies - Strategy intelligence")
        print("   • GET /health - System health check")
        
        return process
        
    except Exception as e:
        print(f"❌ Error starting API server: {e}")
        return None

def start_streamlit_terminal():
    """Start the Streamlit terminal (optional)"""
    print("\n📊 Starting Streamlit terminal...")
    
    try:
        process = subprocess.Popen([
            sys.executable, '-m', 'streamlit', 'run', 'northstar_terminal.py',
            '--server.port', '8501',
            '--server.headless', 'true'
        ])
        
        print("✅ Streamlit terminal starting on http://localhost:8501")
        return process
        
    except Exception as e:
        print(f"❌ Error starting Streamlit terminal: {e}")
        return None

def check_react_terminal():
    """Check if React terminal is set up"""
    print("\n⚛️ Checking React terminal setup...")
    
    react_dir = 'northstar-terminal'
    package_json = os.path.join(react_dir, 'package.json')
    
    if os.path.exists(package_json):
        print("✅ React terminal found")
        print(f"   Directory: {react_dir}")
        print("   To start React terminal:")
        print(f"   1. cd {react_dir}")
        print("   2. npm install")
        print("   3. npm start")
        print("   4. Open http://localhost:3000")
        return True
    else:
        print("❌ React terminal not found")
        print("   The React terminal provides the Bloomberg-grade UI")
        return False

def generate_narratives():
    """Generate strategy narratives"""
    print("\n🗣️ Generating strategy narratives...")
    
    try:
        
        from strategy_narrative_engine import StrategyNarrativeEngine
        
        engine = StrategyNarrativeEngine()
        narratives = engine.analyze_strategy_events()
        
        if not narratives.empty:
            print(f"✅ Generated {len(narratives)} strategy narratives")
        else:
            print("⚠️ No narratives generated (using mock data)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error generating narratives: {e}")
        return False

def main():
    """Main launcher function"""
    print_banner()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Build snapshot
    if not build_snapshot():
        print("⚠️ Continuing without fresh snapshot...")
    
    # Generate narratives
    generate_narratives()
    
    # Start API server
    api_process = start_api_server()
    if not api_process:
        print("❌ Cannot continue without API server")
        sys.exit(1)
    
    # Wait for API server to start
    print("⏳ Waiting for API server to initialize...")
    time.sleep(3)
    
    # Check React terminal
    react_available = check_react_terminal()
    
    # Start Streamlit terminal
    streamlit_process = start_streamlit_terminal()
    
    # Wait for Streamlit to start
    if streamlit_process:
        print("⏳ Waiting for Streamlit to initialize...")
        time.sleep(3)
    
    # Print final status
    print("\n" + "="*60)
    print("🎯 NORTHSTAR TERMINAL STATUS")
    print("="*60)
    print(f"✅ API Server: http://localhost:8000")
    if streamlit_process:
        print(f"✅ Streamlit Terminal: http://localhost:8501")
    if react_available:
        print(f"⚛️ React Terminal: Run 'cd northstar-terminal && npm start'")
    print("="*60)
    
    print("\n🎮 TERMINAL MODES:")
    print("• WAR ROOM - Real-time risk and performance monitoring")
    print("• PORTFOLIO - Holdings and strategy allocation analysis") 
    print("• INTELLIGENCE - Bayesian beliefs and strategy evolution")
    
    print("\n📊 DATA SOURCES:")
    print("• Unified snapshot: data/processed/cache/dashboard_snapshot.parquet")
    print("• Strategy beliefs: data/processed/strategy_beliefs.parquet")
    print("• Portfolio weights: data/processed/portfolio_weights.parquet")
    print("• Market state: data/processed/market_state.parquet")
    
    print(f"\n🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nPress Ctrl+C to stop all services")
    
    # Set up signal handler for graceful shutdown
    def signal_handler(sig, frame):
        print("\n\n🛑 Shutting down Northstar Terminal...")
        if api_process:
            api_process.terminate()
        if streamlit_process:
            streamlit_process.terminate()
        print("✅ All services stopped")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Keep the launcher running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    main()