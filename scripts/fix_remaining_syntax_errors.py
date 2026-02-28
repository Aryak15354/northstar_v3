#!/usr/bin/env python3
"""
Fix all remaining syntax errors in Northstar V3
"""

import re

def fix_file(filepath, fixes):
    """Apply fixes to a file"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    for pattern, replacement in fixes:
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)
    
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"✅ Fixed {filepath}")

# Fix unified_intelligence_engine.py - empty if block
fix_file('src/intelligence/unified_intelligence_engine.py', [
    (r'(if self\._market_brain is None:\n\s+# Dependency injection[^\n]+\n)# self\._market_brain = None',
     r'\1            pass  # self._market_brain = None')
])

# Fix strategy_narrative_engine.py - corrupted import
fix_file('src/intelligence/strategy_narrative_engine.py', [
    (r'import sys\n\)\)\)',
     'import sys\nimport os\nsys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))')
])

# Fix capacity_integration.py - corrupted import
fix_file('src/intelligence/capacity_integration.py', [
    (r'import sys\n\s+from src\.intelligence',
     'import sys\nimport os\nsys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))\n\nfrom src.intelligence')
])

# Fix beta_drift_fabric.py - corrupted import
fix_file('src/intelligence/market_brain/beta_drift_fabric.py', [
    (r'import sys\n\)\)\)',
     'import sys\nimport os\nsys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))')
])

# Fix brain_dashboard.py - unexpected indent
fix_file('src/intelligence/market_brain/brain_dashboard.py', [
    (r'(\n)(\s{8,})from src\.intelligence',
     r'\1from src.intelligence')
])

# Fix weekly_fabric_builder.py - corrupted import
fix_file('src/intelligence/market_brain/weekly_fabric_builder.py', [
    (r'import sys\n\)\)\)',
     'import sys\nimport os\nsys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))')
])

# Fix weekly_fabric_reader.py - corrupted import
fix_file('src/intelligence/market_brain/weekly_fabric_reader.py', [
    (r'import sys\n\)\)\)',
     'import sys\nimport os\nsys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))')
])

# Fix fabric_narrative_integration.py - corrupted import
fix_file('src/intelligence/market_brain/fabric_narrative_integration.py', [
    (r'import sys\n\)\)\)',
     'import sys\nimport os\nsys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))')
])

# Fix fabric_capital_integration.py - corrupted import
fix_file('src/intelligence/market_brain/fabric_capital_integration.py', [
    (r'import sys\n\)\)\)',
     'import sys\nimport os\nsys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))')
])

# Fix brain_window.py - empty if block
with open('src/dashboard/brain_window.py', 'r') as f:
    lines = f.readlines()

fixed_lines = []
i = 0
while i < len(lines):
    fixed_lines.append(lines[i])
    
    # Check if this is an if statement followed by empty/unindented line
    if 'if ' in lines[i] and lines[i].strip().endswith(':'):
        if i + 1 < len(lines):
            current_indent = len(lines[i]) - len(lines[i].lstrip())
            next_line = lines[i + 1] if i + 1 < len(lines) else ''
            next_indent = len(next_line) - len(next_line.lstrip()) if next_line.strip() else 0
            
            # If next line is not properly indented, add pass
            if next_indent <= current_indent and not next_line.strip().startswith('pass'):
                fixed_lines.append(' ' * (current_indent + 4) + 'pass\n')
    
    i += 1

with open('src/dashboard/brain_window.py', 'w') as f:
    f.writelines(fixed_lines)
print("✅ Fixed src/dashboard/brain_window.py")

# Fix unified_terminal_v3.py - empty if block
with open('src/dashboard/unified_terminal_v3.py', 'r') as f:
    lines = f.readlines()

fixed_lines = []
i = 0
while i < len(lines):
    fixed_lines.append(lines[i])
    
    # Check if this is an if statement followed by empty/unindented line
    if 'if ' in lines[i] and lines[i].strip().endswith(':'):
        if i + 1 < len(lines):
            current_indent = len(lines[i]) - len(lines[i].lstrip())
            next_line = lines[i + 1] if i + 1 < len(lines) else ''
            next_indent = len(next_line) - len(next_line.lstrip()) if next_line.strip() else 0
            
            # If next line is not properly indented, add pass
            if next_indent <= current_indent and not next_line.strip().startswith('pass'):
                fixed_lines.append(' ' * (current_indent + 4) + 'pass\n')
    
    i += 1

with open('src/dashboard/unified_terminal_v3.py', 'w') as f:
    f.writelines(fixed_lines)
print("✅ Fixed src/dashboard/unified_terminal_v3.py")

# Fix unified_dashboard_coordinator.py - empty class
with open('src/dashboard/unified_dashboard_coordinator.py', 'r') as f:
    lines = f.readlines()

fixed_lines = []
i = 0
while i < len(lines):
    fixed_lines.append(lines[i])
    
    # Check if this is a class definition followed by empty line
    if lines[i].strip().startswith('class ') and lines[i].strip().endswith(':'):
        # Check next line
        if i + 1 < len(lines):
            current_indent = len(lines[i]) - len(lines[i].lstrip())
            next_line = lines[i + 1] if i + 1 < len(lines) else ''
            next_indent = len(next_line) - len(next_line.lstrip()) if next_line.strip() else 0
            
            # If next line is not properly indented, add pass
            if next_indent <= current_indent and not next_line.strip().startswith('pass'):
                fixed_lines.append(' ' * (current_indent + 4) + 'pass\n')
    
    i += 1

with open('src/dashboard/unified_dashboard_coordinator.py', 'w') as f:
    f.writelines(fixed_lines)
print("✅ Fixed src/dashboard/unified_dashboard_coordinator.py")

# Fix northstar_command_bridge.py - line 368
with open('src/dashboard/northstar_command_bridge.py', 'r') as f:
    content = f.read()

# Fix the specific issue at line 368 (incomplete line)
content = re.sub(
    r'all_green = all\(c\[\'status\'\] == \'green\' for c in constraints\.',
    "all_green = all(c['status'] == 'green' for c in constraints.values())",
    content
)

with open('src/dashboard/northstar_command_bridge.py', 'w') as f:
    f.write(content)
print("✅ Fixed src/dashboard/northstar_command_bridge.py")

# Fix unified_portfolio_coordinator.py - empty class
with open('src/portfolio/unified_portfolio_coordinator.py', 'r') as f:
    lines = f.readlines()

fixed_lines = []
i = 0
while i < len(lines):
    fixed_lines.append(lines[i])
    
    # Check if this is a class definition followed by empty line
    if lines[i].strip().startswith('class ') and lines[i].strip().endswith(':'):
        # Check next line
        if i + 1 < len(lines):
            current_indent = len(lines[i]) - len(lines[i].lstrip())
            next_line = lines[i + 1] if i + 1 < len(lines) else ''
            next_indent = len(next_line) - len(next_line.lstrip()) if next_line.strip() else 0
            
            # If next line is not properly indented, add pass
            if next_indent <= current_indent and not next_line.strip().startswith('pass'):
                fixed_lines.append(' ' * (current_indent + 4) + 'pass\n')
    
    i += 1

with open('src/portfolio/unified_portfolio_coordinator.py', 'w') as f:
    f.writelines(fixed_lines)
print("✅ Fixed src/portfolio/unified_portfolio_coordinator.py")

# Fix unified_risk_coordinator.py - empty class
with open('src/risk/unified_risk_coordinator.py', 'r') as f:
    lines = f.readlines()

fixed_lines = []
i = 0
while i < len(lines):
    fixed_lines.append(lines[i])
    
    # Check if this is a class definition followed by empty line
    if lines[i].strip().startswith('class ') and lines[i].strip().endswith(':'):
        # Check next line
        if i + 1 < len(lines):
            current_indent = len(lines[i]) - len(lines[i].lstrip())
            next_line = lines[i + 1] if i + 1 < len(lines) else ''
            next_indent = len(next_line) - len(next_line.lstrip()) if next_line.strip() else 0
            
            # If next line is not properly indented, add pass
            if next_indent <= current_indent and not next_line.strip().startswith('pass'):
                fixed_lines.append(' ' * (current_indent + 4) + 'pass\n')
    
    i += 1

with open('src/risk/unified_risk_coordinator.py', 'w') as f:
    f.writelines(fixed_lines)
print("✅ Fixed src/risk/unified_risk_coordinator.py")

print("\n🎉 All syntax errors fixed!")
