"""
Periodic Cleanup Script
Run weekly to maintain workspace cleanliness.
"""
from pathlib import Path
import logging
import shutil

workspace = Path.cwd()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def remove_pycache():
    """Remove all __pycache__ directories"""
    removed = 0
    for pycache in workspace.rglob("__pycache__"):
        if pycache.is_dir():
            shutil.rmtree(pycache)
            removed += 1
    return removed

def remove_pyc_files():
    """Remove all .pyc files"""
    removed = 0
    for pyc in workspace.rglob("*.pyc"):
        if pyc.is_file():
            pyc.unlink()
            removed += 1
    return removed

def remove_ds_store():
    """Remove all .DS_Store files"""
    removed = 0
    for ds in workspace.rglob(".DS_Store"):
        if ds.is_file():
            ds.unlink()
            removed += 1
    return removed

def move_completion_reports():
    """Move any completion reports from root to docs/completion_reports/"""
    dest_dir = workspace / "docs/completion_reports"
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    moved = []
    for file in workspace.glob("*COMPLETE*.md"):
        if file.is_file() and file.parent == workspace:
            dest = dest_dir / file.name
            if not dest.exists():
                shutil.move(str(file), str(dest))
                moved.append(file.name)
    
    for file in workspace.glob("*SUMMARY*.md"):
        if file.is_file() and file.parent == workspace:
            dest = dest_dir / file.name
            if not dest.exists():
                shutil.move(str(file), str(dest))
                moved.append(file.name)
    
    return moved

def move_log_files():
    """Move any log files from root to logs/"""
    logs_dir = workspace / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    moved = []
    for file in workspace.glob("*.log"):
        if file.is_file() and file.parent == workspace:
            dest = logs_dir / file.name
            if not dest.exists():
                shutil.move(str(file), str(dest))
                moved.append(file.name)
    
    return moved

def check_root_files():
    """Check for unexpected files in root"""
    essential = {
        'README.md', 'LICENSE', 'requirements.txt', 'run.py',
        'PROJECT_STRUCTURE.md', '.gitignore', '.DS_Store'
    }
    
    unexpected = []
    for file in workspace.iterdir():
        if file.is_file() and file.name not in essential:
            if file.suffix in ['.md', '.json', '.txt', '.py', '.log']:
                unexpected.append(file.name)
    
    return unexpected

def main():
    logger.info("=" * 60)
    logger.info("PERIODIC WORKSPACE CLEANUP")
    logger.info("=" * 60)
    
    # Remove Python cache
    logger.info("\n[1/6] Removing __pycache__ directories...")
    pycache_count = remove_pycache()
    logger.info(f"  ✓ Removed {pycache_count} __pycache__ directories")
    
    # Remove .pyc files
    logger.info("\n[2/6] Removing .pyc files...")
    pyc_count = remove_pyc_files()
    logger.info(f"  ✓ Removed {pyc_count} .pyc files")
    
    # Remove .DS_Store files
    logger.info("\n[3/6] Removing .DS_Store files...")
    ds_count = remove_ds_store()
    logger.info(f"  ✓ Removed {ds_count} .DS_Store files")
    
    # Move completion reports
    logger.info("\n[4/6] Moving completion reports...")
    reports = move_completion_reports()
    if reports:
        for report in reports:
            logger.info(f"  ✓ Moved: {report}")
    else:
        logger.info("  ✓ No completion reports to move")
    
    # Move log files
    logger.info("\n[5/6] Moving log files...")
    logs = move_log_files()
    if logs:
        for log in logs:
            logger.info(f"  ✓ Moved: {log}")
    else:
        logger.info("  ✓ No log files to move")
    
    # Check root directory
    logger.info("\n[6/6] Checking root directory...")
    unexpected = check_root_files()
    if unexpected:
        logger.warning("  ⚠ Unexpected files in root:")
        for file in unexpected:
            logger.warning(f"    - {file}")
        logger.warning("  Please move these files to appropriate directories")
    else:
        logger.info("  ✓ Root directory is clean")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("CLEANUP COMPLETE")
    logger.info("=" * 60)
    logger.info(f"__pycache__ removed: {pycache_count}")
    logger.info(f".pyc files removed: {pyc_count}")
    logger.info(f".DS_Store removed: {ds_count}")
    logger.info(f"Reports moved: {len(reports)}")
    logger.info(f"Logs moved: {len(logs)}")
    logger.info(f"Unexpected root files: {len(unexpected)}")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
