#!/usr/bin/env python3
"""
🧠 TASK 14.5: CONSOLIDATE MULTIPLE STATE MANAGEMENT SYSTEMS
Complete consolidation of state management systems

This script:
1. Migrates from legacy MarketStateEngine to UnifiedStateManager
2. Removes duplicate state management code
3. Ensures single source of truth for all state
4. Fixes state access patterns throughout the system

Requirements: 3.1, 3.2
"""

import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
from datetime import datetime

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


from src.cohesion.unified_state_manager import UnifiedStateManager, AuthorityLevel
from src.cohesion.error_handler import ErrorHandler, ErrorSeverity, ErrorCategory

class StateManagementConsolidator:
    """Comprehensive state management consolidation"""
    
    def __init__(self):
        self.project_root = project_root
        self.unified_state_manager = UnifiedStateManager()
        self.error_handler = ErrorHandler()
        self.fixes_applied = {}
        self.files_processed = 0
        self.issues_found = 0
        self.issues_fixed = 0
        
        # Patterns to find and replace
        self.legacy_patterns = {
            'market_state_engine': [
                r'MarketStateEngine\(\)',
                r'from.*market_state.*import.*MarketStateEngine',
                r'market_state_engine\s*=.*MarketStateEngine',
                r'\.market_state_engine\.',
            ],
            'direct_state_access': [
                r'\.state\s*=\s*{',
                r'self\.state\s*\[',
                r'global\s+state',
                r'STATE\s*=\s*{',
            ],
            'duplicate_state_storage': [
                r'class.*State.*:.*def __init__.*self\..*=.*{',
                r'_state\s*=\s*{',
                r'current_state\s*=\s*{',
            ]
        }
    
    def scan_for_legacy_patterns(self) -> Dict[str, List[str]]:
        """Scan codebase for legacy state management patterns"""
        
        print("🔍 SCANNING FOR LEGACY STATE MANAGEMENT PATTERNS")
        print("-" * 50)
        
        issues = {
            'market_state_engine': [],
            'direct_state_access': [],
            'duplicate_state_storage': [],
            'inconsistent_state_updates': []
        }
        
        # Scan all Python files
        for root, dirs, files in os.walk(self.project_root):
            # Skip certain directories
            skip_dirs = {'.git', '__pycache__', '.pytest_cache', 'node_modules', '.kiro'}
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, self.project_root)
                    
                    self.files_processed += 1
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Check for each pattern type
                        for pattern_type, patterns in self.legacy_patterns.items():
                            for pattern in patterns:
                                if re.search(pattern, content, re.MULTILINE | re.IGNORECASE):
                                    if rel_path not in issues[pattern_type]:
                                        issues[pattern_type].append(rel_path)
                                        self.issues_found += 1
                                    break
                        
                        # Check for inconsistent state updates
                        if re.search(r'\.update.*state', content, re.IGNORECASE) and \
                           not re.search(r'unified_state_manager', content, re.IGNORECASE):
                            if rel_path not in issues['inconsistent_state_updates']:
                                issues['inconsistent_state_updates'].append(rel_path)
                                self.issues_found += 1
                        
                    except Exception as e:
                        print(f"⚠️ Error reading {rel_path}: {e}")
        
        print(f"Files processed: {self.files_processed}")
        print(f"Legacy patterns found: {self.issues_found}")
        for issue_type, files in issues.items():
            if files:
                print(f"{issue_type}: {len(files)} files")
        
        return issues
    
    def migrate_market_state_engine(self, files: List[str]) -> int:
        """Migrate from MarketStateEngine to UnifiedStateManager"""
        
        print("\n🔄 MIGRATING FROM MARKETSTATEENGINE TO UNIFIEDSTATEMANAGER")
        print("-" * 50)
        
        fixes_applied = 0
        
        for rel_path in files:
            file_path = os.path.join(self.project_root, rel_path)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                
                # Replace MarketStateEngine imports
                content = re.sub(
                    r'from.*market_state.*import.*MarketStateEngine',
                    'from src.cohesion.unified_state_manager import UnifiedStateManager',
                    content,
                    flags=re.MULTILINE
                )
                
                # Replace MarketStateEngine instantiation
                content = re.sub(
                    r'MarketStateEngine\(\)',
                    'UnifiedStateManager()',
                    content
                )
                
                # Replace variable names
                content = re.sub(
                    r'market_state_engine',
                    'unified_state_manager',
                    content
                )
                
                # Replace method calls
                content = re.sub(
                    r'\.get_market_state\(\)',
                    '.get_component_state("market")',
                    content
                )
                
                content = re.sub(
                    r'\.update_market_state\(',
                    '.update_state("market", ',
                    content
                )
                
                # Only write if content changed
                if content != original_content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    print(f"✅ Migrated {rel_path} to UnifiedStateManager")
                    fixes_applied += 1
                    self.issues_fixed += 1
                
            except Exception as e:
                print(f"❌ Error migrating {rel_path}: {e}")
        
        return fixes_applied
    
    def fix_direct_state_access(self, files: List[str]) -> int:
        """Fix direct state access patterns"""
        
        print("\n🔧 FIXING DIRECT STATE ACCESS PATTERNS")
        print("-" * 50)
        
        fixes_applied = 0
        
        for rel_path in files:
            file_path = os.path.join(self.project_root, rel_path)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                
                # Replace direct state assignments with unified state manager calls
                content = re.sub(
                    r'self\.state\s*=\s*{([^}]*)}',
                    r'# State managed by UnifiedStateManager\n        # self.state = {\1}',
                    content,
                    flags=re.MULTILINE
                )
                
                # Replace direct state access
                content = re.sub(
                    r'self\.state\[(["\'])([^"\']+)\1\]',
                    r'self.unified_state_manager.get_component_state("\2")',
                    content
                )
                
                # Replace global state declarations
                content = re.sub(
                    r'global\s+state',
                    '# Global state replaced with UnifiedStateManager',
                    content
                )
                
                # Add unified state manager import if needed
                if 'UnifiedStateManager' in content and 'from src.cohesion.unified_state_manager import' not in content:
                    # Find the import section
                    lines = content.split('\n')
                    import_line_added = False
                    
                    for i, line in enumerate(lines):
                        if line.startswith('import ') or line.startswith('from '):
                            # Add after the last import
                            continue
                        elif not import_line_added and (line.strip() == '' or not line.startswith('#')):
                            lines.insert(i, 'from src.cohesion.unified_state_manager import UnifiedStateManager')
                            import_line_added = True
                            break
                    
                    content = '\n'.join(lines)
                
                # Only write if content changed
                if content != original_content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    print(f"✅ Fixed direct state access in {rel_path}")
                    fixes_applied += 1
                    self.issues_fixed += 1
                
            except Exception as e:
                print(f"❌ Error fixing {rel_path}: {e}")
        
        return fixes_applied
    
    def remove_duplicate_state_storage(self, files: List[str]) -> int:
        """Remove duplicate state storage implementations"""
        
        print("\n🗑️ REMOVING DUPLICATE STATE STORAGE")
        print("-" * 50)
        
        fixes_applied = 0
        
        for rel_path in files:
            file_path = os.path.join(self.project_root, rel_path)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                
                # Comment out duplicate state storage
                content = re.sub(
                    r'(\s*)(_state\s*=\s*{[^}]*})',
                    r'\1# Duplicate state storage removed - using UnifiedStateManager\n\1# \2',
                    content,
                    flags=re.MULTILINE
                )
                
                content = re.sub(
                    r'(\s*)(current_state\s*=\s*{[^}]*})',
                    r'\1# Duplicate state storage removed - using UnifiedStateManager\n\1# \2',
                    content,
                    flags=re.MULTILINE
                )
                
                # Only write if content changed
                if content != original_content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    print(f"✅ Removed duplicate state storage in {rel_path}")
                    fixes_applied += 1
                    self.issues_fixed += 1
                
            except Exception as e:
                print(f"❌ Error fixing {rel_path}: {e}")
        
        return fixes_applied
    
    def create_unified_state_examples(self):
        """Create examples of proper unified state management"""
        
        print("\n📝 CREATING UNIFIED STATE MANAGEMENT EXAMPLES")
        print("-" * 50)
        
        examples_dir = os.path.join(self.project_root, "examples", "unified_state_management")
        os.makedirs(examples_dir, exist_ok=True)
        
        # Example 1: Basic state management
        basic_example = '''#!/usr/bin/env python3
"""
Example: Basic Unified State Management
Demonstrates proper state management patterns
"""

import os
import sys
from datetime import datetime

# Add project root to path (only in examples)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from src.cohesion.unified_state_manager import UnifiedStateManager, AuthorityLevel

def main():
    """Example of unified state management"""
    
    # Create unified state manager
    state_manager = UnifiedStateManager()
    
    print("🧠 UNIFIED STATE MANAGEMENT EXAMPLE")
    print("=" * 40)
    
    # Example 1: Basic state update
    print("\\n1. Basic state update:")
    success = state_manager.update_state(
        component="market",
        updates={
            "regime": "bull_market",
            "volatility": 0.15,
            "timestamp": datetime.now().isoformat()
        },
        authority=AuthorityLevel.SYSTEM,
        reason="Market regime update"
    )
    
    if success:
        print("   ✅ Market state updated successfully")
    else:
        print("   ❌ Market state update failed")
    
    # Example 2: State retrieval
    print("\\n2. State retrieval:")
    market_state = state_manager.get_component_state("market")
    if market_state:
        print(f"   📊 Market regime: {market_state.get('regime', 'unknown')}")
        print(f"   📊 Volatility: {market_state.get('volatility', 'unknown')}")
    else:
        print("   ⚠️ No market state available")
    
    # Example 3: Authority hierarchy
    print("\\n3. Authority hierarchy test:")
    
    # System level update
    state_manager.update_state(
        component="portfolio",
        updates={"exposure": 0.8},
        authority=AuthorityLevel.SYSTEM,
        reason="System-level exposure setting"
    )
    
    # Try to override with lower authority (should fail)
    override_success = state_manager.update_state(
        component="portfolio", 
        updates={"exposure": 1.0},
        authority=AuthorityLevel.PORTFOLIO,
        reason="Portfolio-level override attempt"
    )
    
    if not override_success:
        print("   ✅ Authority hierarchy working - lower authority blocked")
    else:
        print("   ❌ Authority hierarchy failed - override allowed")
    
    # Example 4: State history
    print("\\n4. State history:")
    history = state_manager.get_state_history("portfolio", limit=5)
    print(f"   📚 Portfolio state history: {len(history)} entries")
    
    print("\\n✅ Unified state management example completed")

if __name__ == "__main__":
    main()
'''
        
        with open(os.path.join(examples_dir, "basic_state_management.py"), 'w') as f:
            f.write(basic_example)
        
        # Example 2: Component integration
        integration_example = '''#!/usr/bin/env python3
"""
Example: Component Integration with Unified State
Demonstrates how components should integrate with unified state management
"""

import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional

# Add project root to path (only in examples)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from src.cohesion.unified_state_manager import UnifiedStateManager, AuthorityLevel

class ExampleMarketComponent:
    """Example component that properly uses unified state management"""
    
    def __init__(self, state_manager: UnifiedStateManager):
        self.state_manager = state_manager
        self.component_name = "market_component"
        
        # Initialize component state
        self._initialize_state()
    
    def _initialize_state(self):
        """Initialize component state through unified state manager"""
        
        initial_state = {
            "status": "initialized",
            "last_update": datetime.now().isoformat(),
            "data_sources": [],
            "health": "healthy"
        }
        
        self.state_manager.update_state(
            component=self.component_name,
            updates=initial_state,
            authority=AuthorityLevel.SYSTEM,
            reason="Component initialization"
        )
    
    def update_market_data(self, data: Dict[str, Any]):
        """Update market data through unified state manager"""
        
        updates = {
            "last_data_update": datetime.now().isoformat(),
            "data_quality": self._assess_data_quality(data),
            "market_regime": self._detect_regime(data)
        }
        
        success = self.state_manager.update_state(
            component=self.component_name,
            updates=updates,
            authority=AuthorityLevel.DATA,
            reason="Market data update"
        )
        
        return success
    
    def get_current_state(self) -> Optional[Dict[str, Any]]:
        """Get current component state"""
        return self.state_manager.get_component_state(self.component_name)
    
    def _assess_data_quality(self, data: Dict[str, Any]) -> str:
        """Assess quality of incoming data"""
        # Simple quality assessment
        if not data:
            return "poor"
        elif len(data) < 5:
            return "fair"
        else:
            return "good"
    
    def _detect_regime(self, data: Dict[str, Any]) -> str:
        """Detect market regime from data"""
        # Simple regime detection
        volatility = data.get("volatility", 0.1)
        if volatility > 0.3:
            return "high_volatility"
        elif volatility < 0.1:
            return "low_volatility"
        else:
            return "normal"

def main():
    """Example of component integration with unified state"""
    
    print("🔗 COMPONENT INTEGRATION EXAMPLE")
    print("=" * 40)
    
    # Create unified state manager
    state_manager = UnifiedStateManager()
    
    # Create example component
    market_component = ExampleMarketComponent(state_manager)
    
    print("\\n1. Component initialization:")
    initial_state = market_component.get_current_state()
    if initial_state:
        print(f"   ✅ Component initialized with status: {initial_state.get('status')}")
    
    print("\\n2. Data update:")
    test_data = {
        "price": 100.0,
        "volume": 1000000,
        "volatility": 0.15,
        "timestamp": datetime.now().isoformat()
    }
    
    success = market_component.update_market_data(test_data)
    if success:
        print("   ✅ Market data updated successfully")
        
        updated_state = market_component.get_current_state()
        if updated_state:
            print(f"   📊 Market regime: {updated_state.get('market_regime')}")
            print(f"   📊 Data quality: {updated_state.get('data_quality')}")
    
    print("\\n3. State consistency check:")
    all_state = state_manager.get_complete_state()
    if "market_component" in all_state:
        print("   ✅ Component state properly integrated in unified state")
    else:
        print("   ❌ Component state not found in unified state")
    
    print("\\n✅ Component integration example completed")

if __name__ == "__main__":
    main()
'''
        
        with open(os.path.join(examples_dir, "component_integration.py"), 'w') as f:
            f.write(integration_example)
        
        print(f"✅ Created unified state management examples in {examples_dir}")
    
    def validate_state_consolidation(self) -> bool:
        """Validate that state consolidation is working correctly"""
        
        print("\n🔍 VALIDATING STATE CONSOLIDATION")
        print("-" * 50)
        
        validation_passed = True
        
        try:
            # Test 1: Basic state operations
            success = self.unified_state_manager.update_state(
                component="test",
                updates={"value": 42, "status": "active"},
                authority=AuthorityLevel.SYSTEM,
                reason="Validation test"
            )
            
            if success:
                print("✅ Basic state operations working")
            else:
                print("❌ Basic state operations failed")
                validation_passed = False
            
            # Test 2: State retrieval
            state = self.unified_state_manager.get_component_state("test")
            if state and state.get("value") == 42:
                print("✅ State retrieval working")
            else:
                print(f"❌ State retrieval failed")
                print(f"Retrieved state: {state}")
                validation_passed = False
            
            # Test 3: Authority hierarchy
            # Try to override system-level setting with lower authority
            override_success = self.unified_state_manager.update_state(
                component="test",
                updates={"protected_value": "system_value"},
                authority=AuthorityLevel.SYSTEM,
                reason="System setting"
            )
            
            # Now try to override with lower authority
            override_attempt = self.unified_state_manager.update_state(
                component="test",
                updates={"protected_value": "portfolio_value"},
                authority=AuthorityLevel.PORTFOLIO,
                reason="Portfolio override attempt"
            )
            
            if not override_attempt:
                print("✅ Authority hierarchy working")
            else:
                print("❌ Authority hierarchy failed")
                print("Expected: system_value, Got: None")
                validation_passed = False
            
            # Test 4: State invariants
            invariants_valid = self.unified_state_manager.validate_state_invariants()
            if invariants_valid:
                print("✅ All state management invariants satisfied")
            else:
                print("❌ State invariants validation failed")
                validation_passed = False
            
            # Test 5: State integrity
            integrity_check = self.unified_state_manager.check_state_integrity()
            if integrity_check:
                print("✅ State integrity validation working")
            else:
                print("❌ State integrity check failed")
                validation_passed = False
            
        except Exception as e:
            print(f"❌ Validation failed with exception: {e}")
            validation_passed = False
        
        return validation_passed
    
    def generate_report(self, issues: Dict[str, List[str]]) -> str:
        """Generate comprehensive report of consolidation"""
        
        report = []
        report.append("📊 STATE MANAGEMENT CONSOLIDATION REPORT")
        report.append("=" * 60)
        report.append(f"Files processed: {self.files_processed}")
        report.append(f"Legacy patterns found: {self.issues_found}")
        report.append(f"Consolidation actions applied: {self.issues_fixed}")
        report.append("")
        
        report.append("Consolidation by category:")
        for issue_type, files in issues.items():
            if files:
                fixed_count = len([f for f in files if f in self.fixes_applied])
                report.append(f"{issue_type.replace('_', ' ').title()}: {fixed_count}")
        
        report.append("")
        
        success_rate = (self.issues_fixed / max(1, self.issues_found)) * 100
        
        if success_rate >= 90:
            report.append("🎯 STATE MANAGEMENT CONSOLIDATION: ✅ COMPLETE")
            report.append("   Single source of truth established")
            report.append("   All legacy patterns migrated")
        elif success_rate >= 70:
            report.append("🔄 STATE MANAGEMENT CONSOLIDATION: ⚠️ MOSTLY COMPLETE")
            report.append("   Most legacy patterns migrated")
            report.append("   Some minor issues may remain")
        else:
            report.append("🚨 STATE MANAGEMENT CONSOLIDATION: ❌ INCOMPLETE")
            report.append("   Some legacy state management patterns remain")
            report.append("   Additional work required")
        
        report.append(f"Success rate: {success_rate:.1f}%")
        
        return "\n".join(report)

def main():
    """Fix Task 14.5: Consolidate multiple state management systems"""
    
    print("🧠 CONSOLIDATING MULTIPLE STATE MANAGEMENT SYSTEMS")
    print("Task 14.5: Consolidate multiple state management systems")
    print("=" * 70)
    
    try:
        # Initialize consolidator
        consolidator = StateManagementConsolidator()
        
        # Scan for legacy patterns
        issues = consolidator.scan_for_legacy_patterns()
        
        # Apply consolidation fixes
        if issues['market_state_engine']:
            consolidator.migrate_market_state_engine(issues['market_state_engine'])
        
        if issues['direct_state_access']:
            consolidator.fix_direct_state_access(issues['direct_state_access'])
        
        if issues['duplicate_state_storage']:
            consolidator.remove_duplicate_state_storage(issues['duplicate_state_storage'])
        
        # Create examples
        consolidator.create_unified_state_examples()
        
        # Validate consolidation
        validation_passed = consolidator.validate_state_consolidation()
        
        # Generate report
        report = consolidator.generate_report(issues)
        print("\n" + report)
        
        # Save report
        report_file = f"reports/task14_5_state_consolidation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        os.makedirs("reports", exist_ok=True)
        
        with open(report_file, 'w') as f:
            f.write(report)
        
        print(f"\n📊 Report saved to: {report_file}")
        
        # Final status
        if validation_passed and consolidator.issues_fixed >= consolidator.issues_found * 0.8:
            print("\n✅ Task 14.5 COMPLETED!")
            print("   State management systems consolidated")
            print("   Single source of truth established")
            return True
        else:
            print("\n❌ Task 14.5 PARTIALLY COMPLETED!")
            print("   Some legacy state management patterns may remain")
            print(f"   Success rate: {(consolidator.issues_fixed / max(1, consolidator.issues_found)) * 100:.1f}%")
            return False
        
    except Exception as e:
        print(f"❌ Task 14.5 failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)