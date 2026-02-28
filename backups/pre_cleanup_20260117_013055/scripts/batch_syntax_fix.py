#!/usr/bin/env python3
"""
Batch fix all remaining syntax errors in Northstar V3
"""

import re
import os

def fix_corrupted_imports(file_path):
    """Fix corrupted import blocks with ))) or similar patterns"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Pattern 1: Fix ))) standalone
    content = re.sub(r'^import sys\n\)\)\)\n', 
                     'import sys\nimport os\nsys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\n',
                     content, flags=re.MULTILINE)
    
    # Pattern 2: Fix ))) with following imports
    content = re.sub(r'\)\)\)\nfrom ', 
                     'import os\nsys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\n\nfrom ',
                     content)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    return True

def fix_empty_class_blocks(file_path):
    """Fix empty class definitions"""
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    fixed_lines = []
    i = 0
    while i < len(lines):
        fixed_lines.append(lines[i])
        
        # Check if this is a class definition followed by empty line
        if lines[i].strip().startswith('class ') and lines[i].strip().endswith(':'):
            # Check next line
            if i + 1 < len(lines) and lines[i + 1].strip() == '':
                # Add a pass statement
                indent = len(lines[i]) - len(lines[i].lstrip())
                fixed_lines.append(' ' * (indent + 4) + 'pass\n')
        
        i += 1
    
    with open(file_path, 'w') as f:
        f.writelines(fixed_lines)
    
    return True

def fix_empty_if_blocks(file_path):
    """Fix empty if statements"""
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    fixed_lines = []
    i = 0
    while i < len(lines):
        fixed_lines.append(lines[i])
        
        # Check if this is an if statement followed by empty/unindented line
        if 'if ' in lines[i] and lines[i].strip().endswith(':'):
            if i + 1 < len(lines):
                current_indent = len(lines[i]) - len(lines[i].lstrip())
                next_indent = len(lines[i + 1]) - len(lines[i + 1].lstrip()) if lines[i + 1].strip() else 0
                
                # If next line is not properly indented, add pass
                if next_indent <= current_indent:
                    fixed_lines.append(' ' * (current_indent + 4) + 'pass\n')
        
        i += 1
    
    with open(file_path, 'w') as f:
        f.writelines(fixed_lines)
    
    return True

# Files to fix
fixes = {
    'src/intelligence/strategy_narrative_engine.py': [fix_corrupted_imports],
    'src/intelligence/capacity_integration.py': [fix_corrupted_imports],
    'src/intelligence/market_brain/beta_drift_fabric.py': [fix_corrupted_imports],
    'src/intelligence/market_brain/weekly_fabric_builder.py': [fix_corrupted_imports],
    'src/intelligence/market_brain/market_tensor.py': [fix_corrupted_imports],
    'src/intelligence/market_brain/weekly_fabric_reader.py': [fix_corrupted_imports],
    'src/intelligence/market_brain/fabric_narrative_integration.py': [fix_corrupted_imports],
    'src/intelligence/market_brain/fabric_capital_integration.py': [fix_corrupted_imports],
    'src/dashboard/brain_window.py': [fix_empty_if_blocks],
    'src/dashboard/unified_terminal_v3.py': [fix_empty_if_blocks],
    'src/dashboard/unified_dashboard_coordinator.py': [fix_empty_class_blocks],
    'src/portfolio/unified_portfolio_coordinator.py': [fix_empty_class_blocks],
    'src/risk/unified_risk_coordinator.py': [fix_empty_class_blocks],
    'src/intelligence/unified_intelligence_engine.py': [fix_empty_if_blocks],
    'src/intelligence/market_brain/brain_dashboard.py': [fix_corrupted_imports],
}

print("🔧 BATCH SYNTAX FIX")
print("=" * 70)

for file_path, fix_functions in fixes.items():
    if os.path.exists(file_path):
        print(f"\n📝 Fixing {file_path}...")
        for fix_func in fix_functions:
            try:
                fix_func(file_path)
                print(f"   ✅ Applied {fix_func.__name__}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
    else:
        print(f"\n⚠️  {file_path} not found")

print("\n" + "=" * 70)
print("✅ Batch fix complete!")
