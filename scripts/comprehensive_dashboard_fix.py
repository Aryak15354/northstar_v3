#!/usr/bin/env python3
"""
Comprehensive Dashboard Fix

Fixes all major syntax issues in the dashboard file.
"""

import re
import ast

def main():
    """Fix all dashboard issues"""
    
    print("🔧 Comprehensive dashboard fix...")
    
    # Read the dashboard file
    with open("src/dashboard/northstar_v3_ultimate_integrated_dashboard.py", 'r') as f:
        lines = f.readlines()
    
    fixed_lines = []
    in_multiline_string = False
    string_delimiter = None
    
    for i, line in enumerate(lines):
        line_num = i + 1
        original_line = line
        
        # Skip lines that are clearly corrupted with the pattern
        if "is not None and len(" in line and "color" in line:
            # This is a corrupted HTML line, try to fix it
            if "risk_color" in line:
                line = '                        <span style="color: {risk_color};">{risk_label}</span>\n'
            elif "edge_color" in line:
                line = '                        <span style="color: {edge_color};">{edge_label}</span>\n'
            elif "val_color" in line:
                line = '                        <span style="color: {val_color};">{val_label}</span>\n'
            elif "auto_color" in line:
                line = '                        <span style="color: {auto_color};">{auto_label}</span>\n'
            else:
                # Skip this corrupted line
                continue
        
        # Fix other common corruption patterns
        line = re.sub(r'is not None and len\([^)]+\) > 0 is not None and len\([^)]+\) > 0\) > 0', '', line)
        line = re.sub(r'is not None and len\([^)]+\) > 0', '', line)
        line = re.sub(r'if not df\.empty else 0\.0 if not df\.empty else 0\.0', '0.0', line)
        line = re.sub(r'max\(max\([^,]+,, 0\.001\) 0\.001\)', 'max(1.0, 0.001)', line)
        
        # Fix empty if statements
        if line.strip().startswith('if ') and line.strip().endswith(':'):
            # Check if the next line is properly indented
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                if not next_line.strip() or not next_line.startswith('    '):
                    # Add a pass statement
                    fixed_lines.append(line)
                    fixed_lines.append('            pass\n')
                    continue
        
        fixed_lines.append(line)
    
    # Write the fixed content
    with open("src/dashboard/northstar_v3_ultimate_integrated_dashboard.py", 'w') as f:
        f.writelines(fixed_lines)
    
    print("✅ Applied comprehensive fixes")
    
    # Test compilation
    try:
        with open("src/dashboard/northstar_v3_ultimate_integrated_dashboard.py", 'r') as f:
            content = f.read()
        ast.parse(content)
        print("✅ Dashboard compiles successfully")
        return True
    except SyntaxError as e:
        print(f"❌ Still has syntax errors: {e}")
        print(f"   Line {e.lineno}: {e.text}")
        return False

if __name__ == "__main__":
    main()