#!/usr/bin/env python3
"""
📁 ENHANCED FILE ORGANIZATION SCRIPT

This script organizes files into proper folder structure based on their content and naming patterns.
It handles completion reports, validation documents, and other misplaced files.

Usage:
    python scripts/enhanced_file_organization.py
"""

import os
import shutil
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

class EnhancedFileOrganizer:
    """Enhanced file organizer for proper folder structure"""
    
    def __init__(self):
        self.name = "Enhanced File Organizer"
        self.version = "1.0.0"
        self.execution_time = datetime.now()
        
        # Define comprehensive folder mappings
        self.folder_mappings = {
            # Completion reports (should be in reports/completion/)
            '_COMPLETE.md': 'reports/completion/',
            'COMPLETE.md': 'reports/completion/',
            '_IMPLEMENTATION_COMPLETE.md': 'reports/completion/',
            '_VALIDATION_COMPLETE.md': 'reports/completion/',
            '_INTEGRATION_COMPLETE.md': 'reports/completion/',
            '_CHECKPOINT_COMPLETE.md': 'reports/completion/',
            
            # Task reports (should be in reports/tasks/)
            'TASK_': 'reports/tasks/',
            'TASKS_': 'reports/tasks/',
            
            # Phase reports (should be in reports/phases/)
            'PHASE_': 'reports/phases/',
            
            # System reports (should be in reports/system/)
            'SYSTEM_': 'reports/system/',
            
            # Institutional reports (should be in reports/institutional/)
            'INSTITUTIONAL_': 'reports/institutional/',
            
            # Validation reports (should be in reports/validation/)
            'VALIDATION_': 'reports/validation/',
            
            # Architecture docs (should be in docs/architecture/)
            'ARCHITECTURE': 'docs/architecture/',
            
            # Integration docs (should be in docs/integration/)
            'INTEGRATION_': 'docs/integration/',
            
            # Migration docs (should be in docs/migration/)
            'MIGRATION_': 'docs/migration/',
            
            # Maintenance docs (should stay in docs/)
            'MAINTENANCE': 'docs/',
            
            # README files (should stay where they are)
            'README': None,  # Don't move README files
        }
        
        print(f"📁 {self.name} v{self.version}")
        print(f"📅 Execution: {self.execution_time}")
    
    def find_misplaced_files(self) -> List[Tuple[Path, str]]:
        """Find files that are in the wrong location"""
        
        misplaced_files = []
        
        # Check docs directory for completion reports
        docs_path = Path("docs")
        if docs_path.exists():
            for file_path in docs_path.glob("*.md"):
                if file_path.name == "README.md":
                    continue  # Skip README files
                
                target_dir = self._determine_target_directory(file_path.name)
                if target_dir and not str(file_path).startswith(target_dir):
                    misplaced_files.append((file_path, target_dir))
        
        # Check root directory for any reports
        root_path = Path(".")
        for file_path in root_path.glob("*.md"):
            if file_path.name in ["README.md", "PROJECT_STRUCTURE.md"]:
                continue  # Skip essential root files
            
            target_dir = self._determine_target_directory(file_path.name)
            if target_dir:
                misplaced_files.append((file_path, target_dir))
        
        # Check other directories for misplaced files
        for check_dir in ["scripts", "src", "config"]:
            check_path = Path(check_dir)
            if check_path.exists():
                for file_path in check_path.glob("*.md"):
                    if file_path.name == "README.md":
                        continue
                    
                    target_dir = self._determine_target_directory(file_path.name)
                    if target_dir and not str(file_path).startswith(target_dir):
                        misplaced_files.append((file_path, target_dir))
        
        return misplaced_files
    
    def _determine_target_directory(self, filename: str) -> str:
        """Determine target directory for a file based on its name"""
        
        # Check each mapping pattern
        for pattern, target_dir in self.folder_mappings.items():
            if target_dir is None:  # Don't move these files
                continue
                
            if pattern in filename:
                return target_dir
        
        # Special cases for specific file types
        if filename.endswith('_COMPLETE.md') or filename.endswith('COMPLETE.md'):
            return 'reports/completion/'
        elif 'VALIDATION' in filename and 'COMPLETE' in filename:
            return 'reports/validation/'
        elif 'IMPLEMENTATION' in filename and 'COMPLETE' in filename:
            return 'reports/completion/'
        elif 'INTEGRATION' in filename and 'COMPLETE' in filename:
            return 'docs/integration/'
        elif 'ARCHITECTURE' in filename:
            return 'docs/architecture/'
        elif 'MIGRATION' in filename:
            return 'docs/migration/'
        
        return None
    
    def organize_files(self):
        """Organize misplaced files into proper folders"""
        
        print("\n📁 FINDING MISPLACED FILES")
        print("=" * 60)
        
        misplaced_files = self.find_misplaced_files()
        
        if not misplaced_files:
            print("✅ All files are already in proper locations!")
            return
        
        print(f"📄 Found {len(misplaced_files)} files to organize")
        
        moved_count = 0
        error_count = 0
        
        for file_path, target_dir in misplaced_files:
            try:
                # Create target directory if it doesn't exist
                target_path = Path(target_dir)
                target_path.mkdir(parents=True, exist_ok=True)
                
                # Move file
                new_file_path = target_path / file_path.name
                
                # Check if file already exists in target
                if new_file_path.exists():
                    print(f"   ⚠️  File already exists: {file_path.name} → {target_dir}")
                    continue
                
                shutil.move(str(file_path), str(new_file_path))
                moved_count += 1
                print(f"   📁 Moved: {file_path} → {target_dir}")
                
            except Exception as e:
                error_count += 1
                print(f"   ❌ Error moving {file_path}: {e}")
        
        print(f"\n📁 ORGANIZATION SUMMARY:")
        print(f"   ✅ Moved: {moved_count}")
        print(f"   ❌ Errors: {error_count}")
    
    def create_migration_directory(self):
        """Create migration directory for migration-related docs"""
        
        migration_dir = Path("docs/migration")
        migration_dir.mkdir(parents=True, exist_ok=True)
        
        # Move migration-related files
        docs_path = Path("docs")
        if docs_path.exists():
            for file_path in docs_path.glob("MIGRATION_*.md"):
                target_path = migration_dir / file_path.name
                if not target_path.exists():
                    shutil.move(str(file_path), str(target_path))
                    print(f"   📁 Moved migration doc: {file_path.name}")
    
    def generate_organization_report(self):
        """Generate a report of the organization changes"""
        
        report = {
            'execution_time': self.execution_time.isoformat(),
            'organizer': {
                'name': self.name,
                'version': self.version
            },
            'folder_structure': {
                'reports': {
                    'completion': 'Completion reports and status updates',
                    'tasks': 'Task-specific reports',
                    'phases': 'Phase completion reports',
                    'system': 'System-level reports',
                    'institutional': 'Institutional validation reports',
                    'validation': 'Validation and testing reports'
                },
                'docs': {
                    'architecture': 'Architecture documentation',
                    'integration': 'Integration documentation',
                    'migration': 'Migration documentation',
                    'completion_reports': 'Legacy completion reports'
                }
            },
            'organization_rules': self.folder_mappings
        }
        
        report_file = Path("reports/system/enhanced_organization_report.json")
        report_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📊 Enhanced organization report saved: {report_file}")
    
    def run_complete_organization(self):
        """Run the complete enhanced file organization process"""
        
        print(f"\n📁 {self.name.upper()}")
        print("=" * 80)
        print("Organizing files into proper folder structure")
        print("=" * 80)
        
        # Step 1: Create migration directory
        self.create_migration_directory()
        
        # Step 2: Organize misplaced files
        self.organize_files()
        
        # Step 3: Generate report
        self.generate_organization_report()
        
        print("\n" + "=" * 80)
        print("ENHANCED FILE ORGANIZATION COMPLETE")
        print("=" * 80)
        print("✅ Files organized into proper folder structure")
        print("✅ Migration directory created")
        print("✅ Organization report generated")
        print("=" * 80)

def main():
    """Main execution"""
    
    organizer = EnhancedFileOrganizer()
    organizer.run_complete_organization()

if __name__ == "__main__":
    main()