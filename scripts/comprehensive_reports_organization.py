#!/usr/bin/env python3
"""
📊 COMPREHENSIVE REPORTS ORGANIZATION SCRIPT

This script organizes all reports in the reports directory into proper subdirectories
based on their content and naming patterns.

Usage:
    python scripts/comprehensive_reports_organization.py
"""

import os
import shutil
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

class ComprehensiveReportsOrganizer:
    """Comprehensive organizer for reports directory"""
    
    def __init__(self):
        self.name = "Comprehensive Reports Organizer"
        self.version = "1.0.0"
        self.execution_time = datetime.now()
        
        # Define comprehensive folder mappings for reports
        self.report_mappings = {
            # Task reports
            'TASK_': 'tasks/',
            'TASKS_': 'tasks/',
            'task': 'tasks/',
            
            # Phase reports
            'PHASE_': 'phases/',
            
            # System reports
            'SYSTEM_': 'system/',
            
            # Institutional reports
            'INSTITUTIONAL_': 'institutional/',
            
            # Validation reports
            'VALIDATION_': 'validation/',
            'walk_forward_analysis': 'validation/',
            'WALK_FORWARD_': 'validation/',
            
            # Completion reports
            '_COMPLETE.md': 'completion/',
            'COMPLETE.md': 'completion/',
            
            # Capital reports
            'CAPITAL_': 'capital/',
            'capital_grade': 'capital/',
            
            # Shadow reports
            'SHADOW_': 'shadow/',
            
            # Northstar reports
            'NORTHSTAR_': 'northstar/',
            'northstar_': 'northstar/',
            
            # Performance reports
            'PERFORMANCE_': 'performance/',
            'performance_': 'performance/',
            
            # Technical reports
            'TENSORFLOW_': 'technical/',
            'TEMPORAL_': 'technical/',
            'temporal_': 'technical/',
            
            # Cleanup reports
            'V3_CLEANUP': 'cleanup/',
            'cleanup_': 'cleanup/',
            'coherence_audit': 'cleanup/',
            
            # Final reports
            'FINAL_': 'final/',
            
            # Crisis validation
            'crisis_validation': 'crisis_validation/',
            
            # Alpha validation
            'alpha_validation': 'alpha_validation/',
            
            # Daily operations
            'daily_operations': 'operation/',
            
            # Stress test reports
            'stress_test': 'validation/',
            
            # Robustness reports
            'robustness_fixes': 'technical/',
            
            # Integration reports
            'integration_': 'system/',
            
            # Migration reports
            'MIGRATION_': 'system/',
            
            # Foundation reports
            'FOUNDATION_': 'system/',
        }
        
        print(f"📊 {self.name} v{self.version}")
        print(f"📅 Execution: {self.execution_time}")
    
    def find_reports_to_organize(self) -> List[Tuple[Path, str]]:
        """Find reports that need to be organized"""
        
        reports_to_move = []
        reports_path = Path("reports")
        
        if not reports_path.exists():
            return reports_to_move
        
        # Get all files in reports root directory
        for file_path in reports_path.glob("*"):
            if file_path.is_file():
                target_subdir = self._determine_target_subdirectory(file_path.name)
                if target_subdir:
                    target_path = f"reports/{target_subdir}"
                    # Only move if not already in the correct subdirectory
                    if not str(file_path).startswith(target_path):
                        reports_to_move.append((file_path, target_path))
        
        return reports_to_move
    
    def _determine_target_subdirectory(self, filename: str) -> str:
        """Determine target subdirectory for a report file"""
        
        # Check each mapping pattern
        for pattern, target_subdir in self.report_mappings.items():
            if pattern in filename:
                return target_subdir
        
        # Special cases based on file extensions and patterns
        if filename.endswith('.json'):
            if 'validation' in filename.lower():
                return 'validation/'
            elif 'performance' in filename.lower():
                return 'performance/'
            elif 'operation' in filename.lower():
                return 'operation/'
            elif 'system' in filename.lower():
                return 'system/'
            else:
                return 'data/'  # Generic JSON reports
        
        # HTML files
        if filename.endswith('.html'):
            return 'dashboard/'
        
        # Default for unmatched files
        return None
    
    def organize_reports(self):
        """Organize reports into proper subdirectories"""
        
        print("\n📊 ORGANIZING REPORTS DIRECTORY")
        print("=" * 60)
        
        reports_to_move = self.find_reports_to_organize()
        
        if not reports_to_move:
            print("✅ All reports are already organized!")
            return
        
        print(f"📄 Found {len(reports_to_move)} reports to organize")
        
        moved_count = 0
        error_count = 0
        skipped_count = 0
        
        for file_path, target_dir in reports_to_move:
            try:
                # Create target directory if it doesn't exist
                target_path = Path(target_dir)
                target_path.mkdir(parents=True, exist_ok=True)
                
                # Move file
                new_file_path = target_path / file_path.name
                
                # Check if file already exists in target
                if new_file_path.exists():
                    print(f"   ⚠️  Already exists: {file_path.name} → {target_dir}")
                    skipped_count += 1
                    continue
                
                shutil.move(str(file_path), str(new_file_path))
                moved_count += 1
                print(f"   📊 Moved: {file_path.name} → {target_dir}")
                
            except Exception as e:
                error_count += 1
                print(f"   ❌ Error moving {file_path.name}: {e}")
        
        print(f"\n📊 ORGANIZATION SUMMARY:")
        print(f"   ✅ Moved: {moved_count}")
        print(f"   ⏭️  Skipped: {skipped_count}")
        print(f"   ❌ Errors: {error_count}")
    
    def create_reports_index(self):
        """Create an index of all organized reports"""
        
        reports_path = Path("reports")
        if not reports_path.exists():
            return
        
        index = {
            'generated': self.execution_time.isoformat(),
            'structure': {},
            'total_files': 0
        }
        
        # Scan all subdirectories
        for subdir in reports_path.iterdir():
            if subdir.is_dir():
                files = list(subdir.glob("*"))
                index['structure'][subdir.name] = {
                    'count': len(files),
                    'files': [f.name for f in files if f.is_file()]
                }
                index['total_files'] += len([f for f in files if f.is_file()])
        
        # Add root files
        root_files = [f.name for f in reports_path.glob("*") if f.is_file()]
        if root_files:
            index['structure']['root'] = {
                'count': len(root_files),
                'files': root_files
            }
            index['total_files'] += len(root_files)
        
        # Save index
        index_file = Path("reports/system/reports_index.json")
        index_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(index_file, 'w') as f:
            json.dump(index, f, indent=2)
        
        print(f"\n📊 Reports index saved: {index_file}")
        print(f"   📄 Total files indexed: {index['total_files']}")
        print(f"   📁 Subdirectories: {len(index['structure'])}")
    
    def generate_organization_report(self):
        """Generate a report of the organization changes"""
        
        report = {
            'execution_time': self.execution_time.isoformat(),
            'organizer': {
                'name': self.name,
                'version': self.version
            },
            'organization_rules': self.report_mappings,
            'directory_structure': {
                'tasks': 'Task-specific completion reports',
                'phases': 'Phase completion reports',
                'system': 'System-level reports and diagnostics',
                'institutional': 'Institutional validation reports',
                'validation': 'Validation and testing reports',
                'completion': 'General completion reports',
                'capital': 'Capital allocation and grading reports',
                'shadow': 'Shadow trading reports',
                'northstar': 'Northstar system reports',
                'performance': 'Performance analysis reports',
                'technical': 'Technical implementation reports',
                'cleanup': 'Cleanup and maintenance reports',
                'final': 'Final validation and certification reports',
                'crisis_validation': 'Crisis validation reports',
                'alpha_validation': 'Alpha validation reports',
                'operation': 'Operational reports',
                'dashboard': 'Dashboard and visualization reports',
                'data': 'Raw data and JSON reports'
            }
        }
        
        report_file = Path("reports/system/comprehensive_organization_report.json")
        report_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📊 Comprehensive organization report saved: {report_file}")
    
    def run_complete_organization(self):
        """Run the complete reports organization process"""
        
        print(f"\n📊 {self.name.upper()}")
        print("=" * 80)
        print("Organizing reports directory into proper structure")
        print("=" * 80)
        
        # Step 1: Organize reports
        self.organize_reports()
        
        # Step 2: Create reports index
        self.create_reports_index()
        
        # Step 3: Generate organization report
        self.generate_organization_report()
        
        print("\n" + "=" * 80)
        print("COMPREHENSIVE REPORTS ORGANIZATION COMPLETE")
        print("=" * 80)
        print("✅ Reports organized into proper subdirectories")
        print("✅ Reports index created")
        print("✅ Organization report generated")
        print("=" * 80)

def main():
    """Main execution"""
    
    organizer = ComprehensiveReportsOrganizer()
    organizer.run_complete_organization()

if __name__ == "__main__":
    main()