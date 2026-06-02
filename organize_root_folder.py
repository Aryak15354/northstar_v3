#!/usr/bin/env python3
"""
🗂️ ROOT FOLDER ORGANIZATION SCRIPT
Moves files from root to appropriate folders for better organization
"""

import os
import shutil
from pathlib import Path

def organize_root_folder():
    """Organize root folder by moving files to appropriate locations"""
    
    print("🗂️ ORGANIZING ROOT FOLDER")
    print("=" * 50)
    
    # Define organization rules
    organization_rules = {
        # Documentation files
        'docs/': [
            'DASHBOARD_INTEGRATION_COMPLETE.md',
            'NORTHSTAR_V3_CALCULATIONS_AND_FORMULAS.md', 
            'NS_USO_V3_INTEGRATION_COMPLETE.md',
            'SYSTEM_READY.md',
            'USAGE_GUIDE.md',
            'V3_SENTIMENT_INTEGRATION_COMPLETE.md'
        ],
        
        # Test files
        'tests/integration/': [
            'test_v3_sentiment_integration.py',
            'validate_ns_uso_v3_integration.py'
        ],
        
        # System files
        'scripts/': [
            'check_system_status.py',
        ],
        'data/state/': [
            'sealed_results.json',
            'system_freeze_hash.txt',
            'THE_CRITICAL_ANSWER.json'
        ],
        
        # Launch scripts
        'scripts/launchers/': [
            'launch_all_dashboards.py',
            'launch_brain_window.py', 
            'launch_dashboard.py'
        ],
        
        # System runners
        'scripts/runners/': [
            'run_system_with_current_data.py',
            'simple_system_update.py'
        ]
    }
    
    moved_files = 0
    
    for target_dir, files in organization_rules.items():
        # Create target directory if it doesn't exist
        Path(target_dir).mkdir(parents=True, exist_ok=True)
        
        for file_name in files:
            source_path = Path(file_name)
            target_path = Path(target_dir) / file_name
            
            if source_path.exists():
                try:
                    shutil.move(str(source_path), str(target_path))
                    print(f"   ✅ Moved {file_name} → {target_dir}")
                    moved_files += 1
                except Exception as e:
                    print(f"   ❌ Failed to move {file_name}: {e}")
            else:
                print(f"   ⚠️ File not found: {file_name}")
    
    print(f"\n🎯 Organization complete: {moved_files} files moved")
    
    # Clean up empty directories
    cleanup_empty_dirs()

def cleanup_empty_dirs():
    """Remove empty directories"""
    
    print("\n🧹 CLEANING UP EMPTY DIRECTORIES")
    print("-" * 30)
    
    empty_dirs = []
    
    for root, dirs, files in os.walk('.'):
        for dir_name in dirs:
            dir_path = Path(root) / dir_name
            try:
                if dir_path.is_dir() and not any(dir_path.iterdir()):
                    empty_dirs.append(dir_path)
            except PermissionError:
                continue
    
    for empty_dir in empty_dirs:
        try:
            empty_dir.rmdir()
            print(f"   ✅ Removed empty directory: {empty_dir}")
        except Exception as e:
            print(f"   ⚠️ Could not remove {empty_dir}: {e}")

if __name__ == "__main__":
    organize_root_folder()
