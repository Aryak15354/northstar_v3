# Northstar V3 Maintenance Guide

## Overview

This document provides guidelines for maintaining the Northstar V3 workspace organization and preventing clutter accumulation.

## Directory Structure

### Essential Root Files
Only these files should remain in the root directory:
- `README.md` - Project overview
- `LICENSE` - License information
- `requirements.txt` - Python dependencies
- `run.py` - Main entry point
- `PROJECT_STRUCTURE.md` - Project structure documentation
- `.gitignore` - Git ignore rules

### Directory Purposes

- **`src/`** - Source code organized by functionality
- **`tests/`** - Test files (unit, integration, property-based)
- **`scripts/`** - Utility scripts organized by purpose
  - `cleanup/` - Workspace cleanup tools
  - `debug/` - Debugging scripts
  - `launchers/` - Application launchers
  - `runners/` - System runners
  - `tests/` - Test runners
  - `utilities/` - General utilities
- **`docs/`** - Documentation
  - `completion_reports/` - Project completion reports
  - `architecture/` - Architecture documentation
- **`config/`** - Configuration files
- **`data/`** - Data files
- **`logs/`** - Log files
- **`backups/`** - Backup files and system state snapshots
- **`reports/`** - Generated reports
- **`.kiro/`** - Kiro IDE configuration
  - `specs/` - Feature specifications
  - `specs/archive/` - Archived completed specs

## Cleanup Procedures

### Daily Maintenance

1. **Remove temporary files**
   ```bash
   find . -name "*.pyc" -delete
   find . -name "__pycache__" -type d -exec rm -rf {} +
   find . -name ".DS_Store" -delete
   ```

2. **Check root directory**
   ```bash
   ls -la | grep -E "\.md$|\.json$|\.txt$|\.py$"
   ```
   Only essential files should be present.

### Weekly Maintenance

1. **Move completion reports**
   - Any new `*_COMPLETE.md` or `*_SUMMARY.md` files should go to `docs/completion_reports/`

2. **Organize logs**
   - Move any `.log` files from root to `logs/`

3. **Clean test artifacts**
   - Remove any `test_*` directories from root
   - Remove temporary JSON files

### Monthly Maintenance

1. **Archive old backups**
   - Keep only the 5 most recent backups in `backups/`
   - Archive older backups to external storage

2. **Review and archive specs**
   - Move completed specs to `.kiro/specs/archive/`
   - Update `.kiro/specs/README.md`

3. **Clean up scripts**
   - Remove obsolete scripts
   - Organize new scripts into appropriate subdirectories

## Automated Cleanup

### Periodic Cleanup Script

Run this script weekly to maintain workspace cleanliness:

```bash
python scripts/cleanup/periodic_cleanup.py
```

This script:
- Removes `__pycache__` directories
- Removes `.pyc` files
- Removes `.DS_Store` files
- Moves misplaced completion reports
- Moves log files to `logs/`
- Reports any files in root that shouldn't be there

### Pre-commit Hooks

Add these pre-commit hooks to prevent clutter:

```bash
# .git/hooks/pre-commit
#!/bin/bash

# Check for files in root that shouldn't be there
ESSENTIAL_FILES="README.md LICENSE requirements.txt run.py PROJECT_STRUCTURE.md .gitignore"

for file in *.md *.json *.txt *.py; do
    if [ -f "$file" ]; then
        if ! echo "$ESSENTIAL_FILES" | grep -q "$file"; then
            echo "Error: $file should not be in root directory"
            echo "Move it to the appropriate directory:"
            echo "  - Completion reports → docs/completion_reports/"
            echo "  - Scripts → scripts/"
            echo "  - Logs → logs/"
            exit 1
        fi
    fi
done

# Check for test artifacts
if ls -d test_* 2>/dev/null; then
    echo "Error: Test artifact directories found in root"
    echo "Remove test_* directories before committing"
    exit 1
fi

echo "✓ Workspace organization check passed"
```

## File Naming Conventions

### Python Files
- **Source code**: `snake_case.py`
- **Test files**: `test_*.py`
- **Scripts**: `descriptive_name.py`

### Configuration Files
- **YAML/JSON**: `kebab-case.yaml`, `kebab-case.json`
- **Environment**: `.env`, `.env.example`

### Documentation
- **Markdown**: `UPPERCASE_TITLE.md` for major docs
- **Completion reports**: `DESCRIPTIVE_NAME_COMPLETE.md`
- **Regular docs**: `Title_Case.md` or `kebab-case.md`

### Directories
- **Source code**: `snake_case/`
- **General**: `kebab-case/` or `lowercase/`

## Code Review Checklist

Before merging code, verify:

- [ ] No new files in root directory (except essential files)
- [ ] All scripts are in appropriate `scripts/` subdirectories
- [ ] All tests are in `tests/` directory
- [ ] Completion reports are in `docs/completion_reports/`
- [ ] No `test_*` directories in root
- [ ] No temporary files (`.pyc`, `__pycache__`, `.DS_Store`)
- [ ] Log files are in `logs/`
- [ ] Backup files are in `backups/`
- [ ] New specs are in `.kiro/specs/`
- [ ] File naming follows conventions

## Preventing Clutter

### Best Practices

1. **Create files in the right place**
   - Don't create files in root unless they're essential
   - Use appropriate subdirectories from the start

2. **Clean up after experiments**
   - Remove test directories after testing
   - Delete temporary files
   - Move useful scripts to proper locations

3. **Use descriptive names**
   - Avoid generic names like `test.py`, `temp.json`
   - Use names that indicate purpose and location

4. **Document as you go**
   - Create completion reports in `docs/completion_reports/`
   - Update relevant documentation
   - Don't leave orphaned files

5. **Regular reviews**
   - Check root directory weekly
   - Archive completed work monthly
   - Remove obsolete files quarterly

## Rollback Procedures

If cleanup causes issues:

1. **Identify the backup**
   ```bash
   ls -la backups/
   ```

2. **Restore from backup**
   ```bash
   python scripts/cleanup/restore_backup.py backups/pre_cleanup_YYYYMMDD_HHMMSS
   ```

3. **Verify restoration**
   ```bash
   python scripts/cleanup/run_cleanup.py  # dry-run mode
   ```

## Troubleshooting

### Import Errors After Cleanup

If you encounter import errors:

1. Check the import updater log: `logs/cleanup_execution.log`
2. Run import validation: `python scripts/cleanup/import_updater.py`
3. Manually fix any broken imports
4. Consider restoring from backup if issues persist

### Missing Files

If files are missing after cleanup:

1. Check the backup: `backups/pre_cleanup_*/`
2. Check the cleanup log: `logs/cleanup_execution.log`
3. Restore specific files from backup if needed

### Duplicate Files

If duplicate files appear:

1. Use the file analyzer: `python scripts/cleanup/file_analyzer.py`
2. Review the workspace analysis report
3. Manually resolve duplicates or use consolidation script

## Contact

For questions or issues with workspace maintenance, refer to:
- Project documentation in `docs/`
- Cleanup scripts in `scripts/cleanup/`
- Spec documentation in `.kiro/specs/`
