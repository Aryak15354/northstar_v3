"""
Consolidate Duplicate Directories for V3 Cleanup
Merges backup into backups, removes empty directories.
"""
from pathlib import Path
import shutil
import logging

workspace = Path.cwd()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def consolidate_backup_dirs():
    """Merge backup/ into backups/"""
    backup_dir = workspace / "backup"
    backups_dir = workspace / "backups"
    
    if not backup_dir.exists():
        logger.info("✓ backup/ directory doesn't exist, nothing to consolidate")
        return
    
    # Ensure backups exists
    backups_dir.mkdir(exist_ok=True)
    
    # Move all contents from backup/ to backups/
    moved = 0
    for item in backup_dir.iterdir():
        dest = backups_dir / item.name
        if dest.exists():
            logger.warning(f"  ⚠ {item.name} already exists in backups/, skipping")
        else:
            shutil.move(str(item), str(dest))
            logger.info(f"  ✓ Moved: {item.name} → backups/")
            moved += 1
    
    # Remove empty backup directory
    if not any(backup_dir.iterdir()):
        backup_dir.rmdir()
        logger.info(f"✓ Removed empty backup/ directory")
    
    return moved

def remove_empty_directories():
    """Remove empty directories in workspace"""
    removed = []
    
    # Check common directories that might be empty
    check_dirs = [
        "temp",
        "cache",
        "__pycache__"
    ]
    
    for dir_name in check_dirs:
        dir_path = workspace / dir_name
        if dir_path.exists() and dir_path.is_dir():
            try:
                # Check if empty
                if not any(dir_path.iterdir()):
                    dir_path.rmdir()
                    removed.append(dir_name)
                    logger.info(f"✓ Removed empty directory: {dir_name}/")
            except Exception as e:
                logger.warning(f"  ⚠ Could not remove {dir_name}/: {e}")
    
    return removed

def main():
    logger.info("=" * 60)
    logger.info("CONSOLIDATE DUPLICATE DIRECTORIES")
    logger.info("=" * 60)
    
    # Task 1: Consolidate backup directories
    logger.info("\n[1/2] Consolidating backup directories...")
    moved = consolidate_backup_dirs()
    
    # Task 2: Remove empty directories
    logger.info("\n[2/2] Removing empty directories...")
    removed = remove_empty_directories()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("CONSOLIDATION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Files moved: {moved if moved else 0}")
    logger.info(f"Empty directories removed: {len(removed)}")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
