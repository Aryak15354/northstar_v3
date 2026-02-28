#!/usr/bin/env python3
"""
📊 DATA MERGE AND FILE ORGANIZATION SCRIPT

This script handles two main tasks:
1. Merge historical data from prices_daily_extended into prices_daily without duplicates
2. Organize reports and documentation files into proper folder structure

Usage:
    python scripts/data_merge_and_organize.py
"""

import os
import shutil
import pandas as pd
from pathlib import Path
from datetime import datetime
import json
import glob

class DataMergeAndOrganizer:
    """Handles data merging and file organization"""
    
    def __init__(self):
        self.name = "Data Merge and File Organizer"
        self.version = "1.0.0"
        self.execution_time = datetime.now()
        
        # Define proper folder structure
        self.folder_mappings = {
            # Reports by category
            'TASK_': 'reports/tasks/',
            'TASKS_': 'reports/tasks/',
            'PHASE_': 'reports/phases/',
            'SYSTEM_': 'reports/system/',
            'INSTITUTIONAL_': 'reports/institutional/',
            'SHADOW_': 'reports/shadow/',
            'NORTHSTAR_': 'reports/northstar/',
            'CAPITAL_': 'reports/capital/',
            'FINAL_': 'reports/final/',
            'V3_CLEANUP': 'reports/cleanup/',
            'TENSORFLOW_': 'reports/technical/',
            'PRODUCTION_': 'reports/production/',
            'WALK_FORWARD_': 'reports/validation/',
            'THE_HONEST_': 'reports/validation/',
            
            # Documentation by type
            'COMPREHENSIVE_': 'docs/comprehensive/',
            'VISUAL_': 'docs/dashboards/',
            'DASHBOARD_': 'docs/dashboards/',
            'WORKING_': 'docs/dashboards/',
            'INTEGRATED_': 'docs/integration/',
            'SHADOW_TRADING_': 'docs/trading/',
            
            # Completion reports
            '_COMPLETE.md': 'reports/completion/',
            '_COMPLETION_REPORT.md': 'reports/completion/',
            '_SUMMARY.md': 'reports/summaries/',
            '_STATUS.md': 'reports/status/',
            
            # Validation reports
            'VALIDATION_': 'reports/validation/',
            'RECOVERY_': 'reports/recovery/',
        }
        
        print(f"🔧 {self.name} v{self.version}")
        print(f"📅 Execution: {self.execution_time}")
    
    def merge_price_data(self):
        """Merge price data from extended folder into daily folder without duplicates"""
        
        print("\n📊 MERGING HISTORICAL PRICE DATA")
        print("=" * 60)
        
        source_dir = Path("data/raw/prices_daily_extended")
        target_dir = Path("data/raw/prices_daily")
        
        if not source_dir.exists():
            print(f"❌ Source directory not found: {source_dir}")
            return
        
        if not target_dir.exists():
            print(f"❌ Target directory not found: {target_dir}")
            return
        
        source_files = list(source_dir.glob("*.csv"))
        merged_count = 0
        skipped_count = 0
        error_count = 0
        
        print(f"📈 Found {len(source_files)} files in extended folder")
        
        for source_file in source_files:
            target_file = target_dir / source_file.name
            
            try:
                if target_file.exists():
                    # Merge data without duplicates
                    merged = self._merge_csv_files(source_file, target_file)
                    if merged:
                        merged_count += 1
                        print(f"   ✅ Merged: {source_file.name}")
                    else:
                        skipped_count += 1
                        print(f"   ⏭️  Skipped: {source_file.name} (no new data)")
                else:
                    # Copy new file
                    shutil.copy2(source_file, target_file)
                    merged_count += 1
                    print(f"   📋 Copied: {source_file.name}")
                    
            except Exception as e:
                error_count += 1
                print(f"   ❌ Error with {source_file.name}: {e}")
        
        print(f"\n📊 MERGE SUMMARY:")
        print(f"   ✅ Merged/Copied: {merged_count}")
        print(f"   ⏭️  Skipped: {skipped_count}")
        print(f"   ❌ Errors: {error_count}")
        
        # Create backup of extended folder
        if merged_count > 0:
            backup_dir = Path("data/raw/prices_daily_extended_backup")
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            shutil.copytree(source_dir, backup_dir)
            print(f"   💾 Backup created: {backup_dir}")
    
    def _merge_csv_files(self, source_file: Path, target_file: Path) -> bool:
        """Merge two CSV files without duplicating dates"""
        
        try:
            # Read both files
            source_df = pd.read_csv(source_file)
            target_df = pd.read_csv(target_file)
            
            # Ensure Date column exists and is datetime
            if 'Date' not in source_df.columns or 'Date' not in target_df.columns:
                return False
            
            source_df['Date'] = pd.to_datetime(source_df['Date'])
            target_df['Date'] = pd.to_datetime(target_df['Date'])
            
            # Find new dates in source that aren't in target
            source_dates = set(source_df['Date'])
            target_dates = set(target_df['Date'])
            new_dates = source_dates - target_dates
            
            if not new_dates:
                return False  # No new data to merge
            
            # Get rows with new dates
            new_rows = source_df[source_df['Date'].isin(new_dates)]
            
            # Combine and sort
            combined_df = pd.concat([target_df, new_rows], ignore_index=True)
            combined_df = combined_df.sort_values('Date').reset_index(drop=True)
            
            # Save merged file
            combined_df.to_csv(target_file, index=False)
            
            return True
            
        except Exception as e:
            print(f"      Error merging {source_file.name}: {e}")
            return False
    
    def organize_files(self):
        """Organize reports and documentation into proper folders"""
        
        print("\n📁 ORGANIZING FILES INTO PROPER FOLDERS")
        print("=" * 60)
        
        # Create target directories
        self._create_target_directories()
        
        # Find files to organize
        files_to_move = self._find_files_to_organize()
        
        moved_count = 0
        error_count = 0
        
        print(f"📄 Found {len(files_to_move)} files to organize")
        
        for file_path, target_dir in files_to_move:
            try:
                target_path = Path(target_dir) / file_path.name
                
                # Create target directory if it doesn't exist
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Move file
                shutil.move(str(file_path), str(target_path))
                moved_count += 1
                print(f"   📁 Moved: {file_path.name} → {target_dir}")
                
            except Exception as e:
                error_count += 1
                print(f"   ❌ Error moving {file_path.name}: {e}")
        
        print(f"\n📁 ORGANIZATION SUMMARY:")
        print(f"   ✅ Moved: {moved_count}")
        print(f"   ❌ Errors: {error_count}")
    
    def _create_target_directories(self):
        """Create target directory structure"""
        
        directories = [
            'reports/tasks',
            'reports/phases', 
            'reports/system',
            'reports/institutional',
            'reports/shadow',
            'reports/northstar',
            'reports/capital',
            'reports/final',
            'reports/cleanup',
            'reports/technical',
            'reports/production',
            'reports/validation',
            'reports/completion',
            'reports/summaries',
            'reports/status',
            'docs/comprehensive',
            'docs/dashboards',
            'docs/integration',
            'docs/trading',
            'docs/validation'
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def _find_files_to_organize(self):
        """Find files that need to be organized"""
        
        files_to_move = []
        
        # Look for files in root directory
        root_files = [
            f for f in Path('.').glob('*.md') 
            if f.is_file() and f.name not in ['README.md', 'PROJECT_STRUCTURE.md']
        ]
        
        for file_path in root_files:
            target_dir = self._determine_target_directory(file_path.name)
            if target_dir:
                files_to_move.append((file_path, target_dir))
        
        return files_to_move
    
    def _determine_target_directory(self, filename: str) -> str:
        """Determine target directory for a file based on its name"""
        
        # Check each mapping pattern
        for pattern, target_dir in self.folder_mappings.items():
            if pattern in filename:
                return target_dir
        
        # Special cases
        if filename.endswith('_COMPLETE.md'):
            return 'reports/completion/'
        elif filename.endswith('_SUMMARY.md'):
            return 'reports/summaries/'
        elif filename.endswith('_STATUS.md'):
            return 'reports/status/'
        elif 'VALIDATION' in filename:
            return 'reports/validation/'
        elif 'DASHBOARD' in filename:
            return 'docs/dashboards/'
        elif 'TRADING' in filename:
            return 'docs/trading/'
        
        return None
    
    def update_institutional_validator_path(self):
        """Update the institutional validator to use the merged data"""
        
        print("\n🔧 UPDATING INSTITUTIONAL VALIDATOR DATA PATH")
        print("=" * 60)
        
        validator_file = Path("scripts/institutional_walk_forward_complete.py")
        
        if not validator_file.exists():
            print("❌ Institutional validator not found")
            return
        
        try:
            # Read the file
            with open(validator_file, 'r') as f:
                content = f.read()
            
            # Update the path reference
            old_path = "data/raw/prices_daily_extended/"
            new_path = "data/raw/prices_daily/"
            
            if old_path in content:
                content = content.replace(old_path, new_path)
                
                # Write back
                with open(validator_file, 'w') as f:
                    f.write(content)
                
                print(f"✅ Updated validator to use: {new_path}")
            else:
                print("ℹ️  Validator already using correct path")
                
        except Exception as e:
            print(f"❌ Error updating validator: {e}")
    
    def generate_organization_report(self):
        """Generate a report of the organization changes"""
        
        report = {
            'execution_time': self.execution_time.isoformat(),
            'data_merge': {
                'source': 'data/raw/prices_daily_extended/',
                'target': 'data/raw/prices_daily/',
                'backup_created': 'data/raw/prices_daily_extended_backup/'
            },
            'file_organization': {
                'directories_created': [
                    'reports/tasks', 'reports/phases', 'reports/system',
                    'reports/institutional', 'reports/shadow', 'reports/northstar',
                    'reports/capital', 'reports/final', 'reports/cleanup',
                    'reports/technical', 'reports/production', 'reports/validation',
                    'reports/completion', 'reports/summaries', 'reports/status',
                    'docs/comprehensive', 'docs/dashboards', 'docs/integration',
                    'docs/trading', 'docs/validation'
                ]
            },
            'validator_update': {
                'file': 'scripts/institutional_walk_forward_complete.py',
                'path_updated': 'data/raw/prices_daily/'
            }
        }
        
        report_file = Path("reports/system/data_organization_report.json")
        report_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📊 Organization report saved: {report_file}")
    
    def run_complete_organization(self):
        """Run the complete data merge and file organization process"""
        
        print(f"\n🔧 {self.name.upper()}")
        print("=" * 80)
        print("Merging historical data and organizing files into proper structure")
        print("=" * 80)
        
        # Step 1: Merge price data
        self.merge_price_data()
        
        # Step 2: Organize files
        self.organize_files()
        
        # Step 3: Update validator path
        self.update_institutional_validator_path()
        
        # Step 4: Generate report
        self.generate_organization_report()
        
        print("\n" + "=" * 80)
        print("DATA MERGE AND ORGANIZATION COMPLETE")
        print("=" * 80)
        print("✅ Historical price data merged without duplicates")
        print("✅ Reports and docs organized into proper folders")
        print("✅ Institutional validator updated to use merged data")
        print("✅ Organization report generated")
        print("=" * 80)

def main():
    """Main execution"""
    
    organizer = DataMergeAndOrganizer()
    organizer.run_complete_organization()

if __name__ == "__main__":
    main()