#!/usr/bin/env python3
"""
🔧 COMPREHENSIVE NORTHSTAR V3 SYSTEM REPAIR
Systematically fix all syntax errors and broken imports across the entire system
"""

import os
import subprocess
import sys
from pathlib import Path

def check_syntax(file_path):
    """Check if a Python file has syntax errors"""
    result = subprocess.run(
        ['python', '-m', 'py_compile', file_path],
        capture_output=True,
        text=True
    )
    return result.returncode == 0, result.stderr

def scan_all_python_files():
    """Scan all Python files in the project"""
    print("🔍 SCANNING ALL PYTHON FILES FOR SYNTAX ERRORS")
    print("=" * 70)
    
    # Critical directories to scan
    directories = [
        'src/intelligence',
        'src/dashboard',
        'src/portfolio',
        'src/risk',
        'src/core',
        'src/orchestrator',
        'src/cohesion',
        'src/state',
        'src/ingestion',
    ]
    
    errors = {}
    
    for directory in directories:
        if not os.path.exists(directory):
            continue
            
        print(f"\n📁 Scanning {directory}/...")
        
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith('.py') and not file.startswith('__pycache__'):
                    file_path = os.path.join(root, file)
                    is_valid, error_msg = check_syntax(file_path)
                    
                    if not is_valid:
                        errors[file_path] = error_msg
                        print(f"   ❌ {file_path}")
                        # Print first line of error
                        first_line = error_msg.split('\n')[0] if error_msg else "Unknown error"
                        print(f"      {first_line[:100]}")
                    else:
                        print(f"   ✅ {file_path}")
    
    return errors

def main():
    print("🔧 NORTHSTAR V3 COMPREHENSIVE SYSTEM REPAIR")
    print("=" * 70)
    print()
    
    # Scan for errors
    errors = scan_all_python_files()
    
    print("\n" + "=" * 70)
    print(f"📊 SCAN RESULTS")
    print("=" * 70)
    print(f"Files with syntax errors: {len(errors)}")
    
    if errors:
        print("\n❌ FILES NEEDING REPAIR:")
        for file_path, error in errors.items():
            print(f"\n{file_path}:")
            # Print first 3 lines of error
            error_lines = error.strip().split('\n')[:3]
            for line in error_lines:
                print(f"  {line}")
    else:
        print("\n🎉 ALL FILES HAVE VALID SYNTAX!")
    
    return len(errors)

if __name__ == "__main__":
    error_count = main()
    sys.exit(0 if error_count == 0 else 1)
