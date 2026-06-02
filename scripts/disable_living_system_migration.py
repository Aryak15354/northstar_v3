#!/usr/bin/env python3
"""
Northstar Living System Migration Rollback Script

This script disables the living system migration and reverts to the original
Northstar V3 distributed architecture. Use this if you need to rollback
from the living system to the legacy components.

Usage:
    python scripts/disable_living_system_migration.py [--confirm] [--backup]

Options:
    --confirm    Skip confirmation prompt
    --backup     Create backup before rollback
    --verbose    Enable verbose logging
"""

import os
import sys
import json
import shutil
import argparse
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

class LivingSystemRollback:
    """Handles rollback from living system to legacy architecture"""
    
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.root_dir = Path(__file__).parent.parent
        self.migration_status_file = self.root_dir / "data" / "migration" / "living_system_migration_status.json"
        self.rollback_log_file = self.root_dir / "data" / "migration" / "rollback_log.json"
        
    def log(self, message, level="INFO"):
        """Log message with timestamp"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] [{level}] {message}"
        print(log_message)
        
        if self.verbose or level in ["ERROR", "WARNING"]:
            # Also log to file
            self._append_to_rollback_log(log_message)
    
    def _append_to_rollback_log(self, message):
        """Append message to rollback log file"""
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "message": message
            }
            
            # Create directory if it doesn't exist
            self.rollback_log_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Read existing log or create new
            if self.rollback_log_file.exists():
                with open(self.rollback_log_file, 'r') as f:
                    log_data = json.load(f)
            else:
                log_data = {"rollback_history": []}
            
            log_data["rollback_history"].append(log_entry)
            
            # Write back to file
            with open(self.rollback_log_file, 'w') as f:
                json.dump(log_data, f, indent=2)
                
        except Exception as e:
            print(f"Warning: Could not write to rollback log: {e}")
    
    def check_migration_status(self):
        """Check if living system migration is currently enabled"""
        try:
            if not self.migration_status_file.exists():
                self.log("No migration status file found. Living system may not be enabled.", "WARNING")
                return False
            
            with open(self.migration_status_file, 'r') as f:
                status = json.load(f)
            
            is_enabled = status.get("migration_enabled", False)
            self.log(f"Migration status: {'ENABLED' if is_enabled else 'DISABLED'}")
            
            if is_enabled:
                self.log(f"Migration date: {status.get('migration_date', 'Unknown')}")
                self.log(f"Patched components: {len(status.get('patched_components', []))}")
            
            return is_enabled
            
        except Exception as e:
            self.log(f"Error checking migration status: {e}", "ERROR")
            return False
    
    def create_backup(self):
        """Create backup of current system state before rollback"""
        try:
            backup_dir = self.root_dir / "data" / "migration" / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"pre_rollback_backup_{timestamp}"
            
            self.log(f"Creating backup at: {backup_path}")
            
            # Backup key directories and files
            backup_items = [
                "src/core/compatibility.py",
                "src/core/legacy_wrappers.py", 
                "data/migration/",
                "data/state/",
                "data/processed/unified_state.json"
            ]
            
            backup_path.mkdir(exist_ok=True)
            
            for item in backup_items:
                source = self.root_dir / item
                if source.exists():
                    if source.is_file():
                        dest = backup_path / item
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, dest)
                        self.log(f"Backed up file: {item}")
                    elif source.is_dir():
                        dest = backup_path / item
                        shutil.copytree(source, dest, dirs_exist_ok=True)
                        self.log(f"Backed up directory: {item}")
            
            # Create backup manifest
            manifest = {
                "backup_date": datetime.now().isoformat(),
                "backup_type": "pre_rollback",
                "items_backed_up": backup_items,
                "backup_path": str(backup_path)
            }
            
            with open(backup_path / "backup_manifest.json", 'w') as f:
                json.dump(manifest, f, indent=2)
            
            self.log(f"Backup completed successfully: {backup_path}")
            return backup_path
            
        except Exception as e:
            self.log(f"Error creating backup: {e}", "ERROR")
            return None
    
    def disable_compatibility_layer(self):
        """Disable the compatibility layer by renaming/moving files"""
        try:
            compatibility_file = self.root_dir / "src" / "core" / "compatibility.py"
            legacy_wrappers_file = self.root_dir / "src" / "core" / "legacy_wrappers.py"
            
            # Rename compatibility files to disable them
            if compatibility_file.exists():
                disabled_file = compatibility_file.with_suffix('.py.disabled')
                shutil.move(compatibility_file, disabled_file)
                self.log(f"Disabled compatibility layer: {compatibility_file} -> {disabled_file}")
            
            if legacy_wrappers_file.exists():
                disabled_file = legacy_wrappers_file.with_suffix('.py.disabled')
                shutil.move(legacy_wrappers_file, disabled_file)
                self.log(f"Disabled legacy wrappers: {legacy_wrappers_file} -> {disabled_file}")
            
            return True
            
        except Exception as e:
            self.log(f"Error disabling compatibility layer: {e}", "ERROR")
            return False
    
    def update_migration_status(self):
        """Update migration status to disabled"""
        try:
            # Create directory if it doesn't exist
            self.migration_status_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Read current status or create new
            if self.migration_status_file.exists():
                with open(self.migration_status_file, 'r') as f:
                    status = json.load(f)
            else:
                status = {}
            
            # Update status
            status.update({
                "migration_enabled": False,
                "rollback_date": datetime.now().isoformat(),
                "rollback_reason": "Manual rollback via disable script",
                "previous_migration_date": status.get("migration_date"),
                "rollback_version": "1.0"
            })
            
            # Write updated status
            with open(self.migration_status_file, 'w') as f:
                json.dump(status, f, indent=2)
            
            self.log("Migration status updated to DISABLED")
            return True
            
        except Exception as e:
            self.log(f"Error updating migration status: {e}", "ERROR")
            return False
    
    def verify_rollback(self):
        """Verify that rollback was successful"""
        try:
            self.log("Verifying rollback...")
            
            # Check that compatibility files are disabled
            compatibility_file = self.root_dir / "src" / "core" / "compatibility.py"
            legacy_wrappers_file = self.root_dir / "src" / "core" / "legacy_wrappers.py"
            
            if compatibility_file.exists():
                self.log("WARNING: compatibility.py still exists - rollback may be incomplete", "WARNING")
                return False
            
            if legacy_wrappers_file.exists():
                self.log("WARNING: legacy_wrappers.py still exists - rollback may be incomplete", "WARNING")
                return False
            
            # Check migration status
            if not self.check_migration_status():
                self.log("✅ Migration status correctly shows DISABLED")
            else:
                self.log("WARNING: Migration status still shows ENABLED", "WARNING")
                return False
            
            self.log("✅ Rollback verification successful")
            return True
            
        except Exception as e:
            self.log(f"Error verifying rollback: {e}", "ERROR")
            return False
    
    def perform_rollback(self, create_backup=True):
        """Perform complete rollback to legacy system"""
        try:
            self.log("=" * 60)
            self.log("STARTING LIVING SYSTEM ROLLBACK")
            self.log("=" * 60)
            
            # Check current status
            if not self.check_migration_status():
                self.log("Living system migration is not currently enabled.")
                response = input("Continue with rollback anyway? (y/N): ").strip().lower()
                if response != 'y':
                    self.log("Rollback cancelled by user")
                    return False
            
            # Create backup if requested
            backup_path = None
            if create_backup:
                backup_path = self.create_backup()
                if not backup_path:
                    self.log("Backup failed. Continue without backup? (y/N): ")
                    response = input().strip().lower()
                    if response != 'y':
                        self.log("Rollback cancelled due to backup failure")
                        return False
            
            # Disable compatibility layer
            if not self.disable_compatibility_layer():
                self.log("Failed to disable compatibility layer", "ERROR")
                return False
            
            # Update migration status
            if not self.update_migration_status():
                self.log("Failed to update migration status", "ERROR")
                return False
            
            # Verify rollback
            if not self.verify_rollback():
                self.log("Rollback verification failed", "ERROR")
                return False
            
            self.log("=" * 60)
            self.log("✅ ROLLBACK COMPLETED SUCCESSFULLY")
            self.log("=" * 60)
            
            self.log("Your system has been rolled back to the original Northstar V3 architecture.")
            self.log("All scripts will now use the legacy components directly.")
            
            if backup_path:
                self.log(f"Backup created at: {backup_path}")
            
            self.log("\nTo re-enable living system migration:")
            self.log("python scripts/enable_living_system_migration.py")
            
            return True
            
        except Exception as e:
            self.log(f"Rollback failed with error: {e}", "ERROR")
            return False

def main():
    """Main rollback script"""
    parser = argparse.ArgumentParser(description="Disable Northstar Living System Migration")
    parser.add_argument("--confirm", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--backup", action="store_true", default=True, help="Create backup before rollback")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup creation")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Initialize rollback handler
    rollback = LivingSystemRollback(verbose=args.verbose)
    
    print("🔄 Northstar Living System Migration Rollback")
    print("=" * 50)
    
    # Confirmation prompt
    if not args.confirm:
        print("\nThis will rollback your system from the living system architecture")
        print("to the original Northstar V3 distributed components.")
        print("\nEffects:")
        print("- Living system benefits will be disabled")
        print("- Scripts will use original legacy components")
        print("- Enhanced monitoring and coordination will be lost")
        print("- You can re-enable migration later if needed")
        
        response = input("\nAre you sure you want to proceed? (y/N): ").strip().lower()
        if response != 'y':
            print("Rollback cancelled.")
            return 0
    
    # Determine backup setting
    create_backup = args.backup and not args.no_backup
    
    # Perform rollback
    success = rollback.perform_rollback(create_backup=create_backup)
    
    if success:
        print("\n🎯 Rollback completed successfully!")
        print("Your system is now using the original Northstar V3 architecture.")
        return 0
    else:
        print("\n❌ Rollback failed!")
        print("Check the logs for details. Your system may be in an inconsistent state.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
