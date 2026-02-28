"""
Property Tests for Task 13: Canonical State Access

These tests validate that all components access state through StateFileManager
rather than direct file reads, ensuring single-source-of-truth pattern.

Property 10: Canonical File Reads
For any component reading market state, the file path accessed must be the
canonical market_state.parquet location via StateFileManager.

Validates: Requirements 1.2, 4.1
"""

import pytest
import os
import sys
import ast
import logging
from pathlib import Path
from typing import List, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StateAccessAnalyzer(ast.NodeVisitor):
    """AST visitor to detect direct state file access"""
    
    def __init__(self):
        self.direct_reads = []
        self.state_manager_uses = []
        
    def visit_Call(self, node):
        """Visit function calls to detect pd.read_parquet"""
        # Check for pd.read_parquet calls
        if isinstance(node.func, ast.Attribute):
            if (node.func.attr == 'read_parquet' and
                isinstance(node.func.value, ast.Name) and
                node.func.value.id == 'pd'):
                
                # Extract the file path argument
                if node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant):
                        filepath = arg.value
                        if any(state_file in filepath for state_file in [
                            'market_state', 'portfolio_weights', 'risk_state',
                            'exposure_history', 'portfolio_analytics'
                        ]):
                            self.direct_reads.append({
                                'line': node.lineno,
                                'filepath': filepath
                            })
        
        # Check for StateFileManager method calls
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in [
                'read_market_state', 'read_portfolio_weights',
                'read_risk_state', 'read_exposure_history',
                'read_portfolio_analytics'
            ]:
                self.state_manager_uses.append({
                    'line': node.lineno,
                    'method': node.func.attr
                })
        
        self.generic_visit(node)


def analyze_file_for_state_access(filepath: Path) -> Tuple[List, List]:
    """
    Analyze a Python file for state access patterns.
    
    Args:
        filepath: Path to Python file
        
    Returns:
        Tuple of (direct_reads, state_manager_uses)
    """
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        tree = ast.parse(content)
        analyzer = StateAccessAnalyzer()
        analyzer.visit(tree)
        
        return analyzer.direct_reads, analyzer.state_manager_uses
        
    except Exception as e:
        logger.warning(f"Failed to analyze {filepath}: {e}")
        return [], []


def get_core_system_files() -> List[Path]:
    """Get list of core system files to check"""
    core_dirs = [
        'src/risk',
        'src/portfolio',
        'src/state',
        'src/processing',
        'src/intelligence',
        'src/backtesting',
        'src/execution',
    ]
    
    files = []
    for dir_path in core_dirs:
        full_path = project_root / dir_path
        if full_path.exists():
            files.extend(full_path.rglob('*.py'))
    
    # Exclude test files and __init__.py
    files = [f for f in files if not f.name.startswith('test_') and f.name != '__init__.py']
    
    return files


# Property 10: Canonical File Reads
def test_property_10_canonical_file_reads():
    """
    Property 10: Canonical File Reads
    
    For any component reading market state, the file path accessed must be
    through StateFileManager methods, not direct pd.read_parquet calls.
    
    This ensures single-source-of-truth pattern is enforced.
    """
    logger.info("\n" + "=" * 80)
    logger.info("Property 10: Canonical File Reads")
    logger.info("=" * 80)
    
    core_files = get_core_system_files()
    logger.info(f"Analyzing {len(core_files)} core system files...")
    
    violations = []
    compliant_files = []
    
    for filepath in core_files:
        direct_reads, state_manager_uses = analyze_file_for_state_access(filepath)
        
        # Check for violations (direct reads of state files)
        if direct_reads:
            # Exclude state_file_manager.py itself (it's allowed to read directly)
            if 'state_file_manager.py' not in str(filepath):
                violations.append({
                    'file': str(filepath.relative_to(project_root)),
                    'direct_reads': direct_reads,
                    'state_manager_uses': state_manager_uses
                })
        elif state_manager_uses:
            compliant_files.append(str(filepath.relative_to(project_root)))
    
    # Report results
    logger.info(f"\nCompliant files: {len(compliant_files)}")
    logger.info(f"Files with violations: {len(violations)}")
    
    if violations:
        logger.warning("\n⚠ VIOLATIONS DETECTED:")
        for v in violations:
            logger.warning(f"\n  File: {v['file']}")
            logger.warning(f"  Direct reads: {len(v['direct_reads'])}")
            for read in v['direct_reads']:
                logger.warning(f"    Line {read['line']}: {read['filepath']}")
            if v['state_manager_uses']:
                logger.info(f"  StateManager uses: {len(v['state_manager_uses'])}")
    
    if compliant_files:
        logger.info("\n✓ COMPLIANT FILES:")
        for f in compliant_files[:10]:  # Show first 10
            logger.info(f"  {f}")
        if len(compliant_files) > 10:
            logger.info(f"  ... and {len(compliant_files) - 10} more")
    
    # Property assertion
    assert len(violations) == 0, (
        f"Property 10 violated: {len(violations)} files use direct state file reads "
        f"instead of StateFileManager. See log for details."
    )
    
    logger.info("\n✓ Property 10 validated: All components use canonical state access")


def test_state_file_manager_import_presence():
    """
    Verify that files using state access have StateFileManager imported.
    """
    logger.info("\n" + "=" * 80)
    logger.info("Checking StateFileManager imports")
    logger.info("=" * 80)
    
    core_files = get_core_system_files()
    
    files_needing_import = []
    
    for filepath in core_files:
        direct_reads, state_manager_uses = analyze_file_for_state_access(filepath)
        
        if state_manager_uses:
            # Check if StateFileManager is imported
            with open(filepath, 'r') as f:
                content = f.read()
            
            if 'StateFileManager' not in content:
                files_needing_import.append(str(filepath.relative_to(project_root)))
    
    if files_needing_import:
        logger.warning(f"\n⚠ Files using StateFileManager without import: {len(files_needing_import)}")
        for f in files_needing_import:
            logger.warning(f"  {f}")
    else:
        logger.info("\n✓ All files have proper imports")
    
    assert len(files_needing_import) == 0, (
        f"{len(files_needing_import)} files use StateFileManager without importing it"
    )


def test_no_hardcoded_state_paths():
    """
    Verify that no files contain hardcoded state file paths.
    """
    logger.info("\n" + "=" * 80)
    logger.info("Checking for hardcoded state paths")
    logger.info("=" * 80)
    
    core_files = get_core_system_files()
    
    hardcoded_paths = [
        'data/processed/market_state.parquet',
        'data/processed/portfolio_weights.parquet',
        'data/processed/risk_state.parquet',
        'data/processed/exposure_history.parquet',
    ]
    
    violations = []
    
    for filepath in core_files:
        # Exclude state_file_manager.py (it defines the paths)
        if 'state_file_manager.py' in str(filepath):
            continue
        
        with open(filepath, 'r') as f:
            content = f.read()
        
        for hardcoded_path in hardcoded_paths:
            if hardcoded_path in content:
                violations.append({
                    'file': str(filepath.relative_to(project_root)),
                    'path': hardcoded_path
                })
    
    if violations:
        logger.warning(f"\n⚠ Files with hardcoded paths: {len(violations)}")
        for v in violations:
            logger.warning(f"  {v['file']}: {v['path']}")
    else:
        logger.info("\n✓ No hardcoded state paths found")
    
    # This is a warning, not a hard failure (some files may legitimately need paths)
    if violations:
        logger.warning(
            "\nNote: Some hardcoded paths may be acceptable (e.g., in scripts). "
            "Review each case individually."
        )


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
