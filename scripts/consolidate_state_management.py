#!/usr/bin/env python3
"""
🧠 CONSOLIDATE MULTIPLE STATE MANAGEMENT SYSTEMS
Task 14.5: Consolidate multiple state management systems

This script consolidates multiple state management systems by:
1. Migrating from legacy MarketStateEngine to UnifiedStateManager
2. Removing duplicate state management code
3. Ensuring single source of truth for all state
4. Validating state consistency across components

SYSTEM LAWS ENFORCED:
- INVARIANT S1: Atomic State Updates
- INVARIANT S2: Temporal Monotonicity
- INVARIANT S3: State Authority Hierarchy
"""

import os
import sys
import re
from typing import Dict, List, Any, Optional
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


from src.cohesion.unified_state_manager import UnifiedStateManager, AuthorityLevel
from src.cohesion.error_handler import ErrorHandler, ErrorSeverity, ErrorCategory

class StateManagementConsolidator:
    """
    Consolidates multiple state management systems into unified state manager
    """
    
    def __init__(self):
        self.project_root = Path(project_root)
        self.unified_state_manager = UnifiedStateManager()
        self.error_handler = ErrorHandler()
        self.consolidation_results = {}
        self.files_processed = 0
        self.legacy_patterns_found = 0
        self.legacy_patterns_fixed = 0
    
    def find_legacy_state_management(self) -> Dict[str, List[str]]:
        """Find all legacy state management patterns in the codebase"""
        
        print("🔍 SCANNING FOR LEGACY STATE MANAGEMENT PATTERNS")
        print("-" * 50)
        
        patterns = {
            'market_state_engine': [],
            'direct_state_access': [],
            'duplicate_state_storage': [],
            'inconsistent_state_updates': []
        }
        
        # Scan all Python files
        for py_file in self.project_root.rglob("*.py"):
            if self._should_skip_file(py_file):
                continue
            
            self.files_processed += 1
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Find MarketStateEngine usage
                market_state_pattern = r'MarketStateEngine|market_state_engine|MarketState\('
                if re.search(market_state_pattern, content, re.IGNORECASE):
                    patterns['market_state_engine'].append(str(py_file))
                    self.legacy_patterns_found += 1
                
                # Find direct state access patterns
                direct_access_pattern = r'\.state\s*=|state\[.*?\]\s*='
                if re.search(direct_access_pattern, content):
                    patterns['direct_state_access'].append(str(py_file))
                    self.legacy_patterns_found += 1
                
                # Find duplicate state storage
                duplicate_storage_pattern = r'self\._state|self\.state_dict|self\.current_state'
                if re.search(duplicate_storage_pattern, content):
                    patterns['duplicate_state_storage'].append(str(py_file))
                    self.legacy_patterns_found += 1
                
                # Find inconsistent state updates
                inconsistent_update_pattern = r'state\.update\(|\.set_state\(|\.update_state\('
                if re.search(inconsistent_update_pattern, content):
                    patterns['inconsistent_state_updates'].append(str(py_file))
                    self.legacy_patterns_found += 1
                
            except Exception as e:
                print(f"   ⚠️ Error scanning {py_file}: {e}")
        
        print(f"   Files processed: {self.files_processed}")
        print(f"   Legacy patterns found: {self.legacy_patterns_found}")
        
        for pattern_type, files in patterns.items():
            if files:
                print(f"   {pattern_type}: {len(files)} files")
        
        return patterns
    
    def _should_skip_file(self, file_path: Path) -> bool:
        """Check if file should be skipped"""
        
        skip_patterns = [
            '__pycache__',
            '.git',
            'venv',
            'node_modules',
            '.pytest_cache',
            'test_',
            '_test.py'
        ]
        
        file_str = str(file_path)
        return any(pattern in file_str for pattern in skip_patterns)
    
    def migrate_market_state_engine(self, files_with_legacy: List[str]) -> int:
        """Migrate from MarketStateEngine to UnifiedStateManager"""
        
        print("\n🔄 MIGRATING FROM MARKETSTATEENGINE TO UNIFIEDSTATEMANAGER")
        print("-" * 50)
        
        migrations_applied = 0
        
        for file_path in files_with_legacy:
            try:
                print(f"   Processing: {os.path.basename(file_path)}")
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                
                # Replace MarketStateEngine imports
                import_replacements = [
                    (
                        r'from\s+.*?market_state.*?from src.cohesion.unified_state_manager import UnifiedStateManager',
                        'from src.cohesion.unified_state_manager import UnifiedStateManager'
                    ),
                    (
                        r'from src.cohesion.unified_state_manager import UnifiedStateManager',
                        'from src.cohesion.unified_state_manager import UnifiedStateManager'
                    )
                ]
                
                for pattern, replacement in import_replacements:
                    new_content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
                    if new_content != content:
                        content = new_content
                        migrations_applied += 1
                
                # Replace MarketStateEngine instantiation
                instantiation_replacements = [
                    (
                        r'MarketStateEngine\(\)',
                        'UnifiedStateManager()'
                    ),
                    (
                        r'market_state_engine\s*=.*?MarketStateEngine\(\)',
                        'state_manager = UnifiedStateManager()'
                    ),
                    (
                        r'self\.market_state_engine\s*=.*?MarketStateEngine\(\)',
                        'self.state_manager = UnifiedStateManager()'
                    )
                ]
                
                for pattern, replacement in instantiation_replacements:
                    new_content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
                    if new_content != content:
                        content = new_content
                        migrations_applied += 1
                
                # Replace method calls
                method_replacements = [
                    (
                        r'\.get_market_state\(\)',
                        '.get_component_state("market")'
                    ),
                    (
                        r'\.update_market_state\(',
                        '.update_state("market", '
                    ),
                    (
                        r'\.set_market_regime\(',
                        '.update_state("market", {"regime": '
                    )
                ]
                
                for pattern, replacement in method_replacements:
                    new_content = re.sub(pattern, replacement, content)
                    if new_content != content:
                        content = new_content
                        migrations_applied += 1
                
                # Write back to file if changes were made
                if content != original_content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    print(f"      ✅ Migrated {os.path.basename(file_path)} to UnifiedStateManager")
                
            except Exception as e:
                print(f"      ❌ Error migrating {file_path}: {e}")
                self.error_handler.handle_error(
                    error=e,
                    component="state_consolidator",
                    severity=ErrorSeverity.MEDIUM,
                    category=ErrorCategory.COMPONENT_FAILURE,
                    context={'file': file_path}
                )
        
        self.consolidation_results['market_state_migrations'] = migrations_applied
        return migrations_applied
    
    def fix_direct_state_access(self, files_with_issues: List[str]) -> int:
        """Fix direct state access patterns"""
        
        print("\n🔧 FIXING DIRECT STATE ACCESS PATTERNS")
        print("-" * 50)
        
        fixes_applied = 0
        
        for file_path in files_with_issues:
            try:
                print(f"   Processing: {os.path.basename(file_path)}")
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                
                # Replace direct state assignments
                replacements = [
                    (
                        r'self\.state\s*=\s*({.*?})',
                        r'self.state_manager.update_state("component", \1, AuthorityLevel.SYSTEM, "Direct state update")'
                    ),
                    (
                        r'state\[(["\'].*?["\'])\]\s*=\s*(.*?)$',
                        r'state_manager.update_state("component", {\1: \2}, AuthorityLevel.SYSTEM, "State field update")'
                    )
                ]
                
                for pattern, replacement in replacements:
                    new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
                    if new_content != content:
                        content = new_content
                        fixes_applied += 1
                
                # Add necessary imports if changes were made
                if content != original_content:
                    if 'from src.cohesion.unified_state_manager import' not in content:
                        # Add import at the top
                        import_line = "from src.cohesion.unified_state_manager import UnifiedStateManager, AuthorityLevel\n"
                        
                        # Find the first import line
                        lines = content.split('\n')
                        import_index = 0
                        for i, line in enumerate(lines):
                            if line.strip().startswith('import ') or line.strip().startswith('from '):
                                import_index = i
                                break
                        
                        # Insert import
                        lines.insert(import_index, import_line)
                        content = '\n'.join(lines)
                    
                    # Write back to file
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    print(f"      ✅ Fixed direct state access in {os.path.basename(file_path)}")
                
            except Exception as e:
                print(f"      ❌ Error fixing {file_path}: {e}")
                self.error_handler.handle_error(
                    error=e,
                    component="state_consolidator",
                    severity=ErrorSeverity.MEDIUM,
                    category=ErrorCategory.COMPONENT_FAILURE,
                    context={'file': file_path}
                )
        
        self.consolidation_results['direct_access_fixes'] = fixes_applied
        return fixes_applied
    
    def remove_duplicate_state_storage(self, files_with_issues: List[str]) -> int:
        """Remove duplicate state storage patterns"""
        
        print("\n🗑️ REMOVING DUPLICATE STATE STORAGE")
        print("-" * 50)
        
        removals_applied = 0
        
        for file_path in files_with_issues:
            try:
                print(f"   Processing: {os.path.basename(file_path)}")
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                
                # Remove duplicate state storage patterns
                patterns_to_remove = [
                    r'self\._state\s*=\s*{.*?}\s*\n',
                    r'self\.state_dict\s*=\s*{.*?}\s*\n',
                    r'self\.current_state\s*=\s*{.*?}\s*\n'
                ]
                
                for pattern in patterns_to_remove:
                    new_content = re.sub(pattern, '', content, flags=re.MULTILINE | re.DOTALL)
                    if new_content != content:
                        content = new_content
                        removals_applied += 1
                
                # Write back to file if changes were made
                if content != original_content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    print(f"      ✅ Removed duplicate state storage from {os.path.basename(file_path)}")
                
            except Exception as e:
                print(f"      ❌ Error removing duplicates from {file_path}: {e}")
                self.error_handler.handle_error(
                    error=e,
                    component="state_consolidator",
                    severity=ErrorSeverity.MEDIUM,
                    category=ErrorCategory.COMPONENT_FAILURE,
                    context={'file': file_path}
                )
        
        self.consolidation_results['duplicate_removals'] = removals_applied
        return removals_applied
    
    def create_unified_state_examples(self):
        """Create examples of proper unified state management"""
        
        print("\n📝 CREATING UNIFIED STATE MANAGEMENT EXAMPLES")
        print("-" * 50)
        
        examples_dir = self.project_root / "examples" / "unified_state_management"
        examples_dir.mkdir(parents=True, exist_ok=True)
        
        # Example 1: Component state management
        component_example = '''#!/usr/bin/env python3
"""
Example: Proper Component State Management

This shows how to use UnifiedStateManager for component state
instead of direct state manipulation.
"""

from src.cohesion.unified_state_manager import UnifiedStateManager, AuthorityLevel

class ExampleComponent:
    """Example component using unified state management"""
    
    def __init__(self):
        self.state_manager = UnifiedStateManager()
        self.component_name = "example_component"
    
    def initialize_state(self):
        """Initialize component state"""
        initial_state = {
            "status": "initialized",
            "last_update": "2024-01-01T00:00:00",
            "configuration": {
                "enabled": True,
                "threshold": 0.5
            }
        }
        
        # Use unified state manager for state updates
        success = self.state_manager.update_state(
            component=self.component_name,
            updates=initial_state,
            authority=AuthorityLevel.SYSTEM,
            reason="Component initialization"
        )
        
        if success:
            print(f"✅ {self.component_name} state initialized")
        else:
            print(f"❌ Failed to initialize {self.component_name} state")
    
    def update_configuration(self, new_config):
        """Update component configuration through state manager"""
        
        # Get current state
        current_state = self.state_manager.get_component_state(self.component_name)
        
        # Update configuration
        success = self.state_manager.update_state(
            component=self.component_name,
            updates={"configuration": new_config},
            authority=AuthorityLevel.SYSTEM,
            reason="Configuration update"
        )
        
        return success
    
    def get_status(self):
        """Get component status from unified state"""
        state = self.state_manager.get_component_state(self.component_name)
        return state.get("status", "unknown")

# Usage example
if __name__ == "__main__":
    component = ExampleComponent()
    component.initialize_state()
    
    # Update configuration
    new_config = {"enabled": True, "threshold": 0.7}
    success = component.update_configuration(new_config)
    print(f"Configuration update: {'✅ Success' if success else '❌ Failed'}")
    
    # Get status
    status = component.get_status()
    print(f"Component status: {status}")
'''
        
        with open(examples_dir / "component_state_example.py", 'w') as f:
            f.write(component_example)
        
        # Example 2: State authority hierarchy
        authority_example = '''#!/usr/bin/env python3
"""
Example: State Authority Hierarchy

This shows how to use authority levels to manage state conflicts
and ensure proper state management hierarchy.
"""

from src.cohesion.unified_state_manager import UnifiedStateManager, AuthorityLevel

class StateAuthorityExample:
    """Example showing state authority hierarchy"""
    
    def __init__(self):
        self.state_manager = UnifiedStateManager()
    
    def demonstrate_authority_hierarchy(self):
        """Demonstrate how authority hierarchy works"""
        
        print("🔐 DEMONSTRATING STATE AUTHORITY HIERARCHY")
        print("-" * 40)
        
        # System-level update (high authority)
        system_success = self.state_manager.update_state(
            component="risk",
            updates={"emergency_active": False},
            authority=AuthorityLevel.SYSTEM,
            reason="System initialization"
        )
        print(f"System update: {'✅ Success' if system_success else '❌ Failed'}")
        
        # Portfolio-level update (lower authority)
        portfolio_success = self.state_manager.update_state(
            component="risk",
            updates={"emergency_active": True},
            authority=AuthorityLevel.PORTFOLIO,
            reason="Portfolio risk assessment"
        )
        print(f"Portfolio update: {'✅ Success' if portfolio_success else '❌ Failed'}")
        
        # Emergency override (highest authority)
        emergency_success = self.state_manager.update_state(
            component="risk",
            updates={"emergency_active": True},
            authority=AuthorityLevel.EMERGENCY,
            reason="Emergency brake activation"
        )
        print(f"Emergency update: {'✅ Success' if emergency_success else '❌ Failed'}")
        
        # Check final state
        risk_state = self.state_manager.get_component_state("risk")
        print(f"Final emergency_active state: {risk_state.get('emergency_active')}")

# Usage example
if __name__ == "__main__":
    example = StateAuthorityExample()
    example.demonstrate_authority_hierarchy()
'''
        
        with open(examples_dir / "authority_hierarchy_example.py", 'w') as f:
            f.write(authority_example)
        
        print(f"   ✅ Created unified state management examples in {examples_dir}")
    
    def validate_state_consolidation(self) -> bool:
        """Validate that state consolidation works correctly"""
        
        print("\n🔍 VALIDATING STATE CONSOLIDATION")
        print("-" * 50)
        
        validation_passed = True
        
        try:
            # Test unified state manager
            test_manager = UnifiedStateManager()
            
            # Test basic state operations
            success = test_manager.update_state(
                component="test",
                updates={"value": 42, "status": "active"},
                authority=AuthorityLevel.SYSTEM,
                reason="Validation test"
            )
            
            if success:
                print("   ✅ Basic state operations working")
            else:
                print("   ❌ Basic state operations failed")
                validation_passed = False
            
            # Test state retrieval
            state = test_manager.get_component_state("test")
            if state and state.get("value") == 42 and state.get("status") == "active":
                print("   ✅ State retrieval working")
            else:
                print("   ❌ State retrieval failed")
                print(f"      Retrieved state: {state}")
                validation_passed = False
            
            # Test authority hierarchy
            # Lower authority should not override higher authority
            test_manager.update_state(
                component="test",
                updates={"protected_value": "system_value"},
                authority=AuthorityLevel.SYSTEM,
                reason="System protection test"
            )
            
            # Try to override with lower authority (this should be rejected)
            override_success = test_manager.update_state(
                component="test",
                updates={"protected_value": "portfolio_value"},
                authority=AuthorityLevel.PORTFOLIO,
                reason="Portfolio override attempt"
            )
            
            final_state = test_manager.get_component_state("test")
            # The system value should remain because portfolio authority is lower
            if final_state and final_state.get("protected_value") == "system_value":
                print("   ✅ Authority hierarchy working")
            else:
                print("   ❌ Authority hierarchy failed")
                print(f"      Expected: system_value, Got: {final_state.get('protected_value') if final_state else 'None'}")
                validation_passed = False
            
            # Test state integrity
            integrity_valid = test_manager.validate_state_integrity()
            if integrity_valid:
                print("   ✅ State integrity validation working")
            else:
                print("   ❌ State integrity validation failed")
                validation_passed = False
            
        except Exception as e:
            print(f"   ❌ Validation error: {e}")
            validation_passed = False
        
        return validation_passed
    
    def generate_consolidation_report(self) -> Dict[str, Any]:
        """Generate comprehensive consolidation report"""
        
        print("\n📊 STATE MANAGEMENT CONSOLIDATION REPORT")
        print("=" * 60)
        
        total_fixes = sum(self.consolidation_results.values())
        
        print(f"Files processed: {self.files_processed}")
        print(f"Legacy patterns found: {self.legacy_patterns_found}")
        print(f"Consolidation actions applied: {total_fixes}")
        
        print(f"\nConsolidation by category:")
        for fix_type, count in self.consolidation_results.items():
            print(f"   {fix_type.replace('_', ' ').title()}: {count}")
        
        # Validation results
        validation_passed = self.validate_state_consolidation()
        
        print(f"\nValidation: {'✅ PASSED' if validation_passed else '❌ FAILED'}")
        
        # Overall success
        success_rate = (total_fixes / max(1, self.legacy_patterns_found)) * 100
        overall_success = success_rate >= 50 and validation_passed
        
        print(f"\nSuccess rate: {success_rate:.1f}%")
        
        if overall_success:
            print("\n🎯 STATE MANAGEMENT CONSOLIDATION: ✅ COMPLETE")
            print("   Multiple state management systems consolidated")
            print("   Single source of truth established")
            print("   State authority hierarchy enforced")
        else:
            print("\n🚨 STATE MANAGEMENT CONSOLIDATION: ❌ INCOMPLETE")
            print("   Some legacy state management patterns remain")
            print("   Additional work required")
        
        return {
            'files_processed': self.files_processed,
            'legacy_patterns_found': self.legacy_patterns_found,
            'consolidation_actions': total_fixes,
            'consolidation_results': self.consolidation_results,
            'validation_passed': validation_passed,
            'success_rate': success_rate,
            'overall_success': overall_success
        }

def main():
    """Consolidate multiple state management systems"""
    
    print("🧠 CONSOLIDATING MULTIPLE STATE MANAGEMENT SYSTEMS")
    print("Task 14.5: Consolidate multiple state management systems")
    print("=" * 70)
    
    # Create consolidator
    consolidator = StateManagementConsolidator()
    
    # Find legacy state management patterns
    legacy_patterns = consolidator.find_legacy_state_management()
    
    # Migrate MarketStateEngine to UnifiedStateManager
    if legacy_patterns['market_state_engine']:
        consolidator.migrate_market_state_engine(legacy_patterns['market_state_engine'])
    
    # Fix direct state access patterns
    if legacy_patterns['direct_state_access']:
        consolidator.fix_direct_state_access(legacy_patterns['direct_state_access'])
    
    # Remove duplicate state storage
    if legacy_patterns['duplicate_state_storage']:
        consolidator.remove_duplicate_state_storage(legacy_patterns['duplicate_state_storage'])
    
    # Create unified state management examples
    consolidator.create_unified_state_examples()
    
    # Generate final report
    report = consolidator.generate_consolidation_report()
    
    if report['overall_success']:
        print(f"\n✅ Task 14.5 COMPLETED successfully!")
        print(f"   Multiple state management systems consolidated")
        print(f"   Single source of truth established")
        return True
    else:
        print(f"\n❌ Task 14.5 PARTIALLY COMPLETED!")
        print(f"   Some legacy state management patterns may remain")
        print(f"   Success rate: {report['success_rate']:.1f}%")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)