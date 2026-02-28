#!/usr/bin/env python3
"""
🚀 RUN NORTHSTAR V3 SYSTEM WITH CURRENT DATA
Run the complete system using already updated and merged data

Since data is already updated and merged, this script:
1. Runs the complete Northstar V3 system
2. Generates performance reports
3. Launches dashboard

Usage:
    python run_system_with_current_data.py                # Full system run
    python run_system_with_current_data.py --quick        # Quick run
    python run_system_with_current_data.py --dashboard    # Launch dashboard only
"""

import argparse
import subprocess
import sys
import os
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

class NorthstarSystemRunner:
    """Run Northstar V3 system with current data"""
    
    def __init__(self, verbose=True):
        self.verbose = verbose
        self.start_time = datetime.now()
        self.execution_log = []
        
        # Execution phases
        self.phases = {
            'system_execution': {'duration': 0, 'status': 'pending', 'details': []},
            'performance_analysis': {'duration': 0, 'status': 'pending', 'details': []},
            'dashboard_launch': {'duration': 0, 'status': 'pending', 'details': []}
        }
    
    def log_phase(self, phase, status, message="", duration=0):
        """Log phase execution"""
        
        self.phases[phase]['status'] = status
        self.phases[phase]['duration'] = duration
        if message:
            self.phases[phase]['details'].append(message)
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'phase': phase,
            'status': status,
            'message': message,
            'duration_seconds': duration
        }
        self.execution_log.append(entry)
        
        if self.verbose:
            status_icon = "✅" if status == 'success' else "❌" if status == 'failed' else "⚠️" if status == 'warning' else "🔄"
            print(f"   {status_icon} {phase}: {message}")
    
    def run_command(self, command, phase, description, timeout=1800, cwd=None):
        """Run a command and log results"""
        
        if self.verbose:
            print(f"\n🔄 {description}")
            print(f"   Command: {' '.join(command) if isinstance(command, list) else command}")
        
        start_time = time.time()
        
        try:
            if isinstance(command, str):
                command = command.split()
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd
            )
            
            duration = time.time() - start_time
            
            if result.returncode == 0:
                self.log_phase(phase, 'success', f"{description} completed", duration)
                if self.verbose and result.stdout:
                    print(f"   Output: {result.stdout[:300]}...")
                return True
            else:
                self.log_phase(phase, 'failed', f"{description} failed: {result.stderr[:100]}", duration)
                if self.verbose:
                    print(f"   Error: {result.stderr[:300]}...")
                return False
                
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            self.log_phase(phase, 'failed', f"{description} timed out after {timeout}s", duration)
            if self.verbose:
                print(f"   ❌ Timeout after {timeout} seconds")
            return False
        except Exception as e:
            duration = time.time() - start_time
            self.log_phase(phase, 'failed', f"{description} error: {str(e)}", duration)
            if self.verbose:
                print(f"   ❌ Error: {e}")
            return False
    
    def run_system(self, quick=False):
        """Run the complete Northstar V3 system"""
        
        print("\n🚀 PHASE 1: RUNNING COMPLETE NORTHSTAR V3 SYSTEM")
        print("=" * 60)
        
        # Choose system runner based on quick flag
        if quick:
            # Quick system run
            quick_scripts = [
                "scripts/quick_activate_v3_essentials.py",
                "scripts/activate_system.py",
                "scripts/run_complete_northstar_system.py"
            ]
            
            success = False
            for script in quick_scripts:
                if os.path.exists(script):
                    print(f"🎯 Running quick system: {script}")
                    success = self.run_command(
                        [sys.executa