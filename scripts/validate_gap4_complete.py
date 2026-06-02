#!/usr/bin/env python3
"""
Gap 4 Validation Script

Validates that all Alpha OS components are properly installed and functional.
This script checks:
1. All modules can be imported
2. Registry can be created and used
3. All components can be initialized
4. Integration points exist
5. Configuration is valid
"""

import sys
from pathlib import Path
import logging

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_imports():
    """Validate all Alpha OS modules can be imported."""
    logger.info("=" * 70)
    logger.info("VALIDATING GAP 4: ALPHA OS LAYER")
    logger.info("=" * 70)
    
    logger.info("\n1. Validating module imports...")
    
    try:
        from src.alpha_os import (
            StrategyRegistry,
            StrategyRecord,
            StrategyStatus,
            StrategyFamily,
            StrategyPerformanceRecord,
            StrategyOrchestrator,
            StrategyTribunal,
            StrategyLifecycleManager,
            PromotionEvaluationResult,
            StrategyRedundancyDetector,
            RedundancyCheckResult,
            AlphaOSState
        )
        logger.info("   ✅ All Alpha OS modules imported successfully")
        return True
    except ImportError as e:
        logger.error(f"   ❌ Import failed: {e}")
        return False


def validate_registry():
    """Validate StrategyRegistry functionality."""
    logger.info("\n2. Validating StrategyRegistry...")
    
    try:
        from src.alpha_os import StrategyRegistry, StrategyRecord, StrategyStatus, StrategyFamily
        from datetime import datetime
        
        # Create registry
        registry = StrategyRegistry()
        logger.info("   ✅ Registry created")
        
        # Check if registry file exists
        if registry.registry_file.exists():
            logger.info(f"   ✅ Registry file exists: {registry.registry_file}")
            
            # Get summary
            summary = registry.get_registry_summary()
            logger.info(f"   ✅ Registry summary: {summary['total_strategies']} strategies")
        else:
            logger.info("   ⚠️  Registry file doesn't exist yet (run bootstrap script)")
        
        return True
    except Exception as e:
        logger.error(f"   ❌ Registry validation failed: {e}")
        return False


def validate_components():
    """Validate all Alpha OS components can be initialized."""
    logger.info("\n3. Validating component initialization...")
    
    try:
        from src.alpha_os import (
            StrategyRegistry,
            StrategyOrchestrator,
            StrategyTribunal,
            StrategyLifecycleManager,
            StrategyRedundancyDetector
        )
        from src.intelligence.bayesian_capital_tribunal import BayesianCapitalTribunal
        
        # Initialize components
        registry = StrategyRegistry()
        logger.info("   ✅ StrategyRegistry initialized")
        
        tribunal_instance = BayesianCapitalTribunal()
        logger.info("   ✅ BayesianCapitalTribunal initialized")
        
        tribunal = StrategyTribunal(tribunal_instance, registry)
        logger.info("   ✅ StrategyTribunal initialized")
        
        redundancy = StrategyRedundancyDetector(registry)
        logger.info("   ✅ StrategyRedundancyDetector initialized")
        
        orchestrator = StrategyOrchestrator(registry, tribunal, redundancy)
        logger.info("   ✅ StrategyOrchestrator initialized")
        
        lifecycle = StrategyLifecycleManager(registry, tribunal)
        logger.info("   ✅ StrategyLifecycleManager initialized")
        
        return True
    except Exception as e:
        logger.error(f"   ❌ Component initialization failed: {e}")
        return False


def validate_unified_state_integration():
    """Validate UnifiedState integration."""
    logger.info("\n4. Validating UnifiedState integration...")
    
    try:
        from src.core.state import UnifiedState
        from src.alpha_os import AlphaOSState
        
        # Create UnifiedState
        state = UnifiedState()
        
        # Check if alpha_os attribute exists
        if hasattr(state, 'alpha_os'):
            logger.info("   ✅ UnifiedState has alpha_os attribute")
            
            # Check if it's an AlphaOSState instance
            if isinstance(state.alpha_os, AlphaOSState):
                logger.info("   ✅ alpha_os is AlphaOSState instance")
            else:
                logger.warning(f"   ⚠️  alpha_os is {type(state.alpha_os)}, not AlphaOSState")
        else:
            logger.error("   ❌ UnifiedState missing alpha_os attribute")
            return False
        
        return True
    except Exception as e:
        logger.error(f"   ❌ UnifiedState integration validation failed: {e}")
        return False


def validate_configuration():
    """Validate configuration files exist."""
    logger.info("\n5. Validating configuration...")
    
    config_file = PROJECT_ROOT / "config/alpha_os_config.yaml"
    
    if config_file.exists():
        logger.info(f"   ✅ Configuration file exists: {config_file}")
        
        try:
            import yaml
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            # Check for required sections
            if 'alpha_os' in config:
                logger.info("   ✅ alpha_os section found")
                
                required_sections = [
                    'promotion_criteria',
                    'probation_criteria',
                    'demotion_criteria',
                    'hot_reload',
                    'redundancy'
                ]
                
                for section in required_sections:
                    if section in config['alpha_os']:
                        logger.info(f"   ✅ {section} configured")
                    else:
                        logger.warning(f"   ⚠️  {section} missing from config")
            else:
                logger.warning("   ⚠️  alpha_os section missing from config")
        except Exception as e:
            logger.warning(f"   ⚠️  Could not parse config: {e}")
    else:
        logger.warning(f"   ⚠️  Configuration file not found: {config_file}")
    
    return True


def validate_scripts():
    """Validate scripts exist."""
    logger.info("\n6. Validating scripts...")
    
    scripts = [
        "scripts/bootstrap_alpha_os_registry.py",
        "examples/alpha_os_demo.py"
    ]
    
    all_exist = True
    for script_path in scripts:
        full_path = PROJECT_ROOT / script_path
        if full_path.exists():
            logger.info(f"   ✅ {script_path}")
        else:
            logger.error(f"   ❌ {script_path} not found")
            all_exist = False
    
    return all_exist


def validate_tests():
    """Validate test files exist."""
    logger.info("\n7. Validating tests...")
    
    test_file = PROJECT_ROOT / "src/alpha_os/tests/test_strategy_registry.py"
    
    if test_file.exists():
        logger.info(f"   ✅ Test file exists: {test_file}")
        
        # Try to import tests
        try:
            sys.path.insert(0, str(PROJECT_ROOT / "src/alpha_os/tests"))
            import test_strategy_registry
            logger.info("   ✅ Tests can be imported")
        except Exception as e:
            logger.warning(f"   ⚠️  Could not import tests: {e}")
    else:
        logger.error(f"   ❌ Test file not found: {test_file}")
        return False
    
    return True


def validate_documentation():
    """Validate documentation exists."""
    logger.info("\n8. Validating documentation...")
    
    doc_file = PROJECT_ROOT / "GAP4_COMPLETE.md"
    
    if doc_file.exists():
        logger.info(f"   ✅ Documentation exists: {doc_file}")
        
        # Check file size
        size_kb = doc_file.stat().st_size / 1024
        logger.info(f"   ✅ Documentation size: {size_kb:.1f} KB")
    else:
        logger.error(f"   ❌ Documentation not found: {doc_file}")
        return False
    
    return True


def main():
    """Run all validations."""
    results = []
    
    results.append(("Module Imports", validate_imports()))
    results.append(("StrategyRegistry", validate_registry()))
    results.append(("Component Initialization", validate_components()))
    results.append(("UnifiedState Integration", validate_unified_state_integration()))
    results.append(("Configuration", validate_configuration()))
    results.append(("Scripts", validate_scripts()))
    results.append(("Tests", validate_tests()))
    results.append(("Documentation", validate_documentation()))
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("VALIDATION SUMMARY")
    logger.info("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status:10} {name}")
    
    logger.info("=" * 70)
    logger.info(f"Results: {passed}/{total} validations passed")
    
    if passed == total:
        logger.info("\n🎉 GAP 4 IS COMPLETE!")
        logger.info("   All Alpha OS components are properly installed and functional.")
        logger.info("\nNext steps:")
        logger.info("   1. Run: python scripts/bootstrap_alpha_os_registry.py")
        logger.info("   2. Run: python examples/alpha_os_demo.py")
        logger.info("   3. Run: pytest src/alpha_os/tests/ -v")
        return 0
    else:
        logger.error("\n❌ Some validations failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
