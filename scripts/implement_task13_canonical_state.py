#!/usr/bin/env python3
"""
Task 13: Update All Components to Use Canonical State

This script refactors all components to use StateFileManager instead of
direct file reads. This ensures single-source-of-truth pattern is enforced
throughout the system.

Requirements: 1.2, 4.1
"""

import os
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def refactor_file(filepath: Path, replacements: list) -> bool:
    """
    Apply refactoring replacements to a file.
    
    Args:
        filepath: Path to file to refactor
        replacements: List of (old_pattern, new_pattern) tuples
        
    Returns:
        True if file was modified
    """
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        original_content = content
        modified = False
        
        for old_pattern, new_pattern in replacements:
            if old_pattern in content:
                content = content.replace(old_pattern, new_pattern)
                modified = True
                logger.info(f"  ✓ Replaced pattern in {filepath.name}")
        
        if modified:
            # Add StateFileManager import if not present
            if 'from src.cohesion.state_file_manager import StateFileManager' not in content:
                # Find the last import statement
                lines = content.split('\n')
                last_import_idx = 0
                for i, line in enumerate(lines):
                    if line.startswith('import ') or line.startswith('from '):
                        last_import_idx = i
                
                # Insert import after last import
                lines.insert(last_import_idx + 1, 'from src.cohesion.state_file_manager import StateFileManager')
                content = '\n'.join(lines)
                logger.info(f"  ✓ Added StateFileManager import to {filepath.name}")
            
            # Write back
            with open(filepath, 'w') as f:
                f.write(content)
            
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"  ✗ Failed to refactor {filepath}: {e}")
        return False


def main():
    """Main refactoring workflow"""
    
    logger.info("=" * 80)
    logger.info("TASK 13: UPDATE ALL COMPONENTS TO USE CANONICAL STATE")
    logger.info("=" * 80)
    
    # Define files to refactor (core system files only)
    core_files = [
        'src/risk/portfolio_risk_controller.py',
        'src/risk/emergency_brake.py',
        'src/portfolio/tuning.py',
        'src/portfolio/strategies.py',
        'src/state/unified_state_manager.py',
        'src/processing/opportunity_surface.py',
        'src/core/state.py',
        'src/core/memory.py',
        'src/intelligence/strategy_beliefs.py',
        'src/intelligence/strategy_narrative_engine.py',
        'src/intelligence/capital_allocator.py',
        'src/intelligence/narrative_integration.py',
        'src/intelligence/market_brain/enhanced_brain_orchestrator.py',
        'src/intelligence/market_brain/survival_instincts.py',
        'src/backtesting/backtest_engine.py',
        'src/execution/shadow_fund_engine.py',
    ]
    
    # Common replacement patterns
    market_state_replacements = [
        # Pattern 1: Direct read with path check
        (
            "if os.path.exists(self.paths['market_state']):\n                market_df = pd.read_parquet(self.paths['market_state'])",
            "state_manager = StateFileManager()\n            try:\n                market_df = state_manager.read_market_state()"
        ),
        # Pattern 2: Direct read without path check
        (
            "market_df = pd.read_parquet('data/processed/market_state.parquet')",
            "state_manager = StateFileManager()\n        market_df = state_manager.read_market_state()"
        ),
        # Pattern 3: Direct read with variable path
        (
            "market_df = pd.read_parquet(self.paths['market_state'])",
            "state_manager = StateFileManager()\n            market_df = state_manager.read_market_state()"
        ),
        # Pattern 4: Inline read
        (
            "ms = pd.read_parquet('data/processed/market_state.parquet')",
            "state_manager = StateFileManager()\n    ms = state_manager.read_market_state()"
        ),
    ]
    
    portfolio_weights_replacements = [
        # Pattern 1: Direct read
        (
            "portfolio_df = pd.read_parquet(self.paths['portfolio_weights'])",
            "state_manager = StateFileManager()\n        portfolio_df = state_manager.read_portfolio_weights()"
        ),
        # Pattern 2: Direct read with path
        (
            "portfolio_df = pd.read_parquet('data/processed/portfolio_weights.parquet')",
            "state_manager = StateFileManager()\n        portfolio_df = state_manager.read_portfolio_weights()"
        ),
    ]
    
    risk_state_replacements = [
        # Pattern 1: Direct read
        (
            "risk_df = pd.read_parquet(self.paths['risk_state'])",
            "state_manager = StateFileManager()\n        risk_df = state_manager.read_risk_state()"
        ),
    ]
    
    # Refactor each file
    modified_files = []
    failed_files = []
    
    for filepath_str in core_files:
        filepath = project_root / filepath_str
        
        if not filepath.exists():
            logger.warning(f"⚠ File not found: {filepath}")
            continue
        
        logger.info(f"\nRefactoring: {filepath_str}")
        
        # Try all replacement patterns
        all_replacements = (
            market_state_replacements +
            portfolio_weights_replacements +
            risk_state_replacements
        )
        
        if refactor_file(filepath, all_replacements):
            modified_files.append(filepath_str)
        else:
            logger.info(f"  - No changes needed")
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("REFACTORING SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Files modified: {len(modified_files)}")
    logger.info(f"Files failed: {len(failed_files)}")
    
    if modified_files:
        logger.info("\nModified files:")
        for f in modified_files:
            logger.info(f"  ✓ {f}")
    
    if failed_files:
        logger.info("\nFailed files:")
        for f in failed_files:
            logger.info(f"  ✗ {f}")
    
    # Next steps
    logger.info("\n" + "=" * 80)
    logger.info("NEXT STEPS")
    logger.info("=" * 80)
    logger.info("1. Review modified files for correctness")
    logger.info("2. Run property tests: pytest tests/validation/test_task13_canonical_state_properties.py")
    logger.info("3. Run integration tests to verify system still works")
    logger.info("4. Update tasks.md to mark Task 13 complete")
    
    return len(failed_files) == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
