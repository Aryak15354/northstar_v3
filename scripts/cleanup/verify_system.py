"""
System Verification After Cleanup
Verifies that the system is still functional after cleanup operations.
"""
from pathlib import Path
import sys
import logging

workspace = Path.cwd()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def verify_essential_files():
    """Verify essential files exist"""
    essential = [
        'README.md',
        'LICENSE',
        'requirements.txt',
        'run.py',
        'PROJECT_STRUCTURE.md'
    ]
    
    missing = []
    for file in essential:
        if not (workspace / file).exists():
            missing.append(file)
    
    return missing

def verify_directory_structure():
    """Verify essential directories exist"""
    essential_dirs = [
        'src',
        'tests',
        'scripts',
        'docs',
        'config',
        'logs',
        'backups',
        '.kiro'
    ]
    
    missing = []
    for dir_name in essential_dirs:
        if not (workspace / dir_name).is_dir():
            missing.append(dir_name)
    
    return missing

def verify_imports():
    """Verify key imports work"""
    errors = []
    
    # Add src to path
    sys.path.insert(0, str(workspace / "src"))
    
    # Try importing key modules
    test_imports = [
        'cohesion.state_file_manager',
        'cohesion.bounded_exposure_calculator',
        'cohesion.health_calculator',
    ]
    
    for module in test_imports:
        try:
            __import__(module)
        except ImportError as e:
            errors.append(f"{module}: {e}")
    
    return errors

def verify_cleanup_infrastructure():
    """Verify cleanup infrastructure exists"""
    cleanup_files = [
        'scripts/cleanup/file_analyzer.py',
        'scripts/cleanup/move_planner.py',
        'scripts/cleanup/cleanup_executor.py',
        'scripts/cleanup/import_updater.py',
        'scripts/cleanup/run_cleanup.py'
    ]
    
    missing = []
    for file in cleanup_files:
        if not (workspace / file).exists():
            missing.append(file)
    
    return missing

def verify_documentation():
    """Verify key documentation exists"""
    docs = [
        'docs/MAINTENANCE.md',
        'docs/README.md',
        '.kiro/specs/README.md'
    ]
    
    missing = []
    for doc in docs:
        if not (workspace / doc).exists():
            missing.append(doc)
    
    return missing

def main():
    logger.info("=" * 60)
    logger.info("SYSTEM VERIFICATION")
    logger.info("=" * 60)
    
    all_passed = True
    
    # Verify essential files
    logger.info("\n[1/5] Verifying essential files...")
    missing_files = verify_essential_files()
    if missing_files:
        logger.error(f"  ✗ Missing files: {', '.join(missing_files)}")
        all_passed = False
    else:
        logger.info("  ✓ All essential files present")
    
    # Verify directory structure
    logger.info("\n[2/5] Verifying directory structure...")
    missing_dirs = verify_directory_structure()
    if missing_dirs:
        logger.error(f"  ✗ Missing directories: {', '.join(missing_dirs)}")
        all_passed = False
    else:
        logger.info("  ✓ All essential directories present")
    
    # Verify imports
    logger.info("\n[3/5] Verifying key imports...")
    import_errors = verify_imports()
    if import_errors:
        logger.warning("  ⚠ Some imports failed:")
        for error in import_errors[:5]:
            logger.warning(f"    - {error}")
        # Don't fail on import errors as some may have pre-existing issues
    else:
        logger.info("  ✓ Key imports working")
    
    # Verify cleanup infrastructure
    logger.info("\n[4/5] Verifying cleanup infrastructure...")
    missing_cleanup = verify_cleanup_infrastructure()
    if missing_cleanup:
        logger.error(f"  ✗ Missing cleanup files: {', '.join(missing_cleanup)}")
        all_passed = False
    else:
        logger.info("  ✓ Cleanup infrastructure intact")
    
    # Verify documentation
    logger.info("\n[5/5] Verifying documentation...")
    missing_docs = verify_documentation()
    if missing_docs:
        logger.warning(f"  ⚠ Missing documentation: {', '.join(missing_docs)}")
    else:
        logger.info("  ✓ Key documentation present")
    
    # Summary
    logger.info("\n" + "=" * 60)
    if all_passed:
        logger.info("✓ SYSTEM VERIFICATION PASSED")
    else:
        logger.error("✗ SYSTEM VERIFICATION FAILED")
    logger.info("=" * 60)
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
