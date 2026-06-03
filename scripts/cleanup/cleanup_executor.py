"""
Cleanup Executor for Northstar V3
Safely executes file operations with backup and rollback.
"""
import shutil
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from dataclasses import dataclass

from .move_planner import MoveOperation, OperationType


@dataclass
class ExecutionResult:
    """Result of an operation execution"""
    success: bool
    operation: MoveOperation
    error: Optional[str] = None


class CleanupExecutor:
    """Executes cleanup operations safely"""
    
    def __init__(self, workspace_root: Path, dry_run: bool = False):
        self.workspace_root = Path(workspace_root)
        self.dry_run = dry_run
        self.backup_dir: Optional[Path] = None
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/cleanup_execution.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def create_backup(self) -> Path:
        """Create full workspace backup"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.workspace_root / "backups" / f"pre_cleanup_{timestamp}"
        
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would create backup at: {backup_path}")
            return backup_path
        
        self.logger.info(f"Creating backup at: {backup_path}")
        backup_path.mkdir(parents=True, exist_ok=True)
        
        # Backup entire workspace (excluding the backup container itself).
        for source in self.workspace_root.iterdir():
            if source.name == "backups":
                continue

            dest = backup_path / source.name
            try:
                if source.is_dir():
                    shutil.copytree(source, dest, dirs_exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, dest)
                self.logger.info(f"Backed up: {source.name}")
            except Exception as e:
                self.logger.error(f"Failed to backup {source.name}: {e}")
        
        self.backup_dir = backup_path
        self.logger.info(f"Backup complete: {backup_path}")
        return backup_path
    
    def execute_operation(self, op: MoveOperation) -> ExecutionResult:
        """Execute a single operation"""
        try:
            source_full = self.workspace_root / op.source_path
            
            if op.operation_type == OperationType.DELETE:
                return self._execute_delete(op, source_full)
            elif op.operation_type == OperationType.MOVE:
                return self._execute_move(op, source_full)
            elif op.operation_type == OperationType.MERGE:
                return self._execute_merge(op, source_full)
            else:
                return ExecutionResult(
                    success=False,
                    operation=op,
                    error=f"Unknown operation type: {op.operation_type}"
                )
        
        except Exception as e:
            self.logger.error(f"Error executing {op.operation_type.value} {op.source_path}: {e}")
            return ExecutionResult(success=False, operation=op, error=str(e))
    
    def _execute_delete(self, op: MoveOperation, source: Path) -> ExecutionResult:
        """Execute delete operation"""
        if not source.exists():
            return ExecutionResult(
                success=True,
                operation=op,
                error="Source does not exist (already deleted?)"
            )
        
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would delete: {op.source_path}")
            return ExecutionResult(success=True, operation=op)
        
        try:
            if source.is_dir():
                shutil.rmtree(source)
            else:
                source.unlink()
            self.logger.info(f"Deleted: {op.source_path}")
            return ExecutionResult(success=True, operation=op)
        except Exception as e:
            return ExecutionResult(success=False, operation=op, error=str(e))
    
    def _execute_move(self, op: MoveOperation, source: Path) -> ExecutionResult:
        """Execute move operation"""
        if not source.exists():
            return ExecutionResult(
                success=False,
                operation=op,
                error="Source does not exist"
            )
        
        dest_full = self.workspace_root / op.dest_path
        
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would move: {op.source_path} → {op.dest_path}")
            return ExecutionResult(success=True, operation=op)
        
        try:
            # Create destination directory
            dest_full.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if destination exists
            if dest_full.exists():
                # If identical, skip
                if source.is_file() and dest_full.is_file():
                    if source.read_bytes() == dest_full.read_bytes():
                        self.logger.info(f"Skipped (identical): {op.source_path}")
                        source.unlink()  # Remove source
                        return ExecutionResult(success=True, operation=op)
                
                # Otherwise, create unique name
                counter = 1
                new_dest = dest_full
                while new_dest.exists():
                    new_dest = dest_full.parent / f"{dest_full.stem}_{counter}{dest_full.suffix}"
                    counter += 1
                dest_full = new_dest
                self.logger.warning(f"Destination exists, using: {dest_full}")
            
            # Move file/directory
            shutil.move(str(source), str(dest_full))
            self.logger.info(f"Moved: {op.source_path} → {dest_full.relative_to(self.workspace_root)}")
            return ExecutionResult(success=True, operation=op)
        
        except Exception as e:
            return ExecutionResult(success=False, operation=op, error=str(e))
    
    def _execute_merge(self, op: MoveOperation, source: Path) -> ExecutionResult:
        """Execute merge operation"""
        # For now, treat merge as move
        return self._execute_move(op, source)
    
    def execute_all(self, operations: List[MoveOperation]) -> List[ExecutionResult]:
        """Execute all operations"""
        results = []
        
        self.logger.info(f"Executing {len(operations)} operations (dry_run={self.dry_run})")
        
        for i, op in enumerate(operations, 1):
            self.logger.info(f"[{i}/{len(operations)}] {op.operation_type.value}: {op.source_path}")
            result = self.execute_operation(op)
            results.append(result)
            
            if not result.success:
                self.logger.error(f"Operation failed: {result.error}")
        
        # Summary
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        
        self.logger.info(f"\nExecution complete:")
        self.logger.info(f"  Successful: {successful}")
        self.logger.info(f"  Failed: {failed}")
        
        return results
    
    def rollback(self, backup_path: Path):
        """Rollback changes from backup"""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Would rollback from: {backup_path}")
            return
        
        if not backup_path.exists():
            self.logger.error(f"Backup not found: {backup_path}")
            return
        
        self.logger.info(f"Rolling back from: {backup_path}")
        
        # Restore backed up items
        for item in backup_path.iterdir():
            dest = self.workspace_root / item.name
            try:
                if dest.exists():
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()
                
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
                
                self.logger.info(f"Restored: {item.name}")
            except Exception as e:
                self.logger.error(f"Failed to restore {item.name}: {e}")
        
        self.logger.info("Rollback complete")
    
    def verify_operation(self, op: MoveOperation) -> bool:
        """Verify an operation was successful"""
        if op.operation_type == OperationType.DELETE:
            source_full = self.workspace_root / op.source_path
            return not source_full.exists()
        
        elif op.operation_type == OperationType.MOVE:
            source_full = self.workspace_root / op.source_path
            dest_full = self.workspace_root / op.dest_path
            return not source_full.exists() and dest_full.exists()
        
        return True


if __name__ == "__main__":
    import sys
    
    dry_run = "--dry-run" in sys.argv
    
    executor = CleanupExecutor(Path.cwd(), dry_run=dry_run)
    
    # Create backup
    backup = executor.create_backup()
    
    print(f"\nBackup created at: {backup}")
    print(f"Dry run mode: {dry_run}")
    
    if not dry_run:
        print("\nTo execute cleanup, run the full cleanup script.")
