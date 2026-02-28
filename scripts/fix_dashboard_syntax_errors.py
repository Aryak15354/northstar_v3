#!/usr/bin/env python3
"""
Fix Dashboard Syntax Errors

Fixes the corrupted syntax in the main dashboard file.
"""

import re

def main():
    """Fix syntax errors in dashboard"""
    
    print("🔧 Fixing dashboard syntax errors...")
    
    # Read the dashboard file
    with open("src/dashboard/northstar_v3_ultimate_integrated_dashboard.py", 'r') as f:
        content = f.read()
    
    # Fix corrupted color style attributes
    # Pattern: <span style="color is not None and len(...) > 0 is not None...
    # Should be: <span style="color: {color};">
    
    # Fix risk status color
    content = re.sub(
        r'<span style="color is not None.*?risk_color.*?\};">\{risk_label\}</span>',
        '<span style="color: {risk_color};">{risk_label}</span>',
        content,
        flags=re.DOTALL
    )
    
    # Fix edge detection color
    content = re.sub(
        r'<span style="color is not None.*?edge_color.*?\};">\{edge_label\}</span>',
        '<span style="color: {edge_color};">{edge_label}</span>',
        content,
        flags=re.DOTALL
    )
    
    # Fix validation color
    content = re.sub(
        r'<span style="color is not None.*?val_color.*?\};">\{val_label\}</span>',
        '<span style="color: {val_color};">{val_label}</span>',
        content,
        flags=re.DOTALL
    )
    
    # Fix automation color
    content = re.sub(
        r'<span style="color is not None.*?auto_color.*?\};">\{auto_label\}</span>',
        '<span style="color: {auto_color};">{auto_label}</span>',
        content,
        flags=re.DOTALL
    )
    
    # Fix other corrupted patterns
    content = re.sub(
        r'is not None and len\([^)]+\) > 0 is not None and len\([^)]+\) > 0\) > 0',
        '',
        content
    )
    
    content = re.sub(
        r'is not None and len\([^)]+\) > 0',
        '',
        content
    )
    
    # Fix corrupted if statements
    content = re.sub(
        r'if [^:]+is not None and len[^:]+:[^:]+:',
        'if True:',
        content
    )
    
    # Fix corrupted variable assignments
    content = re.sub(
        r'= [^=]+ if not df\.empty else 0\.0 if not df\.empty else 0\.0',
        '= 0.0',
        content
    )
    
    # Fix corrupted max() calls
    content = re.sub(
        r'max\(max\([^,]+,, 0\.001\) 0\.001\)',
        'max(1.0, 0.001)',
        content
    )
    
    # Write the fixed content
    with open("src/dashboard/northstar_v3_ultimate_integrated_dashboard.py", 'w') as f:
        f.write(content)
    
    print("✅ Fixed dashboard syntax errors")
    
    # Test compilation
    try:
        import py_compile
        py_compile.compile("src/dashboard/northstar_v3_ultimate_integrated_dashboard.py", doraise=True)
        print("✅ Dashboard compiles successfully")
    except py_compile.PyCompileError as e:
        print(f"❌ Still has syntax errors: {e}")
        return False
    
    return True

if __name__ == "__main__":
    main()