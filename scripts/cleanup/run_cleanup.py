"""
Master Cleanup Script for Northstar V3
Executes the full cleanup workflow safely with backups.
"""
import sys
from pathlib import Path
import logging

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cleanup.file_analyzer import FileAnalyzer
from cleanup.move_planner import MovePlanner
from cleanup.cleanup_executor import CleanupExecutor
from cleanup.import_updater import ImportUpdater


def main(dry_run=True):
    """Run the complete cleanup workflow"""
    workspace = Path.cwd()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("NORTHSTAR V3 CLEANUP")
    logger.info("=" * 60)
    logger.info(f"Workspace: {workspace}")
    logger.info(f"Dry Run: {dry_run}")
    logger.info("=" * 60)
    
    # Step 1: Analyze workspace
    logger.info("\n[1/6] Analyzing workspace...")
    analyzer = FileAnalyzer(workspace)
    categorized = analyzer.scan_workspace()
    report = analyzer.generate_report()
    
    analysis_path = workspace / "reports/workspace_analysis.md"
    analysis_path.write_text(report)
    logger.info(f"Analysis saved: {analysis_path}")
    
    # Step 2: Create cleanup plan
    logger.info("\n[2/6] Creating cleanup plan...")
    planner = MovePlanner(workspace)
    operations = planner.plan_moves(categorized)
    plan_report = planner.generate_plan_report()
    
    plan_path = workspace / "reports/cleanup_plan.md"
    plan_path.write_text(plan_report)
    logger.info(f"Plan saved: {plan_path}")
    logger.info(f"Total operations: {len(operations)}")
    
    # Step 3: Validate plan
    logger.info("\n[3/6] Validating plan...")
    validation = planner.validate_plan(operations)
    
    if not validation.is_valid:
        logger.error("Plan validation failed!")
        for error in validation.errors:
            logger.error(f"  - {error}")
        if not dry_run:
            logger.error("Aborting cleanup due to validation errors")
            return False
    
    if validation.warnings:
        logger.warning(f"Found {len(validation.warnings)} warnings:")
        for warning in validation.warnings[:5]:
            logger.warning(f"  - {warning}")
    
    # Step 4: Create backup
    logger.info("\n[4/6] Creating backup...")
    executor = CleanupExecutor(workspace, dry_run=dry_run)
    backup_path = executor.create_backup()
    logger.info(f"Backup created: {backup_path}")
    
    # Step 5: Execute cleanup
    logger.info("\n[5/6] Executing cleanup operations...")
    results = executor.execute_all(operations)
    
    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful
    
    logger.info(f"\nExecution complete:")
    logger.info(f"  Successful: {successful}/{len(results)}")
    logger.info(f"  Failed: {failed}/{len(results)}")
    
    if failed > 0:
        logger.warning("Some operations failed. Check logs for details.")
    
    # Step 6: Validate imports (if not dry run)
    if not dry_run:
        logger.info("\n[6/6] Validating imports...")
        updater = ImportUpdater(workspace)
        import_errors = updater.validate_imports()
        
        if import_errors:
            logger.warning(f"Found {len(import_errors)} import issues:")
            for error in import_errors[:10]:
                logger.warning(f"  - {error}")
        else:
            logger.info("All imports valid!")
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("CLEANUP SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    logger.info(f"Operations: {len(operations)}")
    logger.info(f"Successful: {successful}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Backup: {backup_path}")
    logger.info("=" * 60)
    
    if dry_run:
        logger.info("\nThis was a DRY RUN. No files were actually moved.")
        logger.info("To execute for real, run: python scripts/cleanup/run_cleanup.py --execute")
    else:
        logger.info("\nCleanup complete!")
        logger.info(f"Backup available at: {backup_path}")
    
    return True


if __name__ == "__main__":
    # Check for --execute flag
    dry_run = "--execute" not in sys.argv
    
    if not dry_run:
        print("\n⚠️  WARNING: This will modify your workspace!")
        print("A backup will be created, but please ensure you have committed your work.")
        response = input("\nProceed with cleanup? (yes/no): ")
        
        if response.lower() != "yes":
            print("Cleanup cancelled.")
            sys.exit(0)
    
    success = main(dry_run=dry_run)
    sys.exit(0 if success else 1)
