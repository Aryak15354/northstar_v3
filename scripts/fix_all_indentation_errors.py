#!/usr/bin/env python3
"""
Fix All Indentation Errors

Fixes the systematic indentation errors in the dashboard file.
"""

import re

def main():
    """Fix all indentation errors"""
    
    print("🔧 Fixing all indentation errors...")
    
    # Read the dashboard file
    with open("src/dashboard/northstar_v3_ultimate_integrated_dashboard.py", 'r') as f:
        content = f.read()
    
    # Fix the systematic pattern of broken try/except blocks
    # Pattern: try:\n            st.plotly_chart(fig, use_container_width=True)\n        except Exception as e:\n            st.error(f"Error creating chart: {e}")
    
    # Fix broken try blocks with wrong indentation
    content = re.sub(
        r'try:\s+st\.plotly_chart\(fig[^,]*,\s*use_container_width=True\)\s+except Exception as e:\s+st\.error\(f"Error creating chart: \{e\}"\)',
        'try:\n                        st.plotly_chart(fig, use_container_width=True)\n                    except Exception as e:\n                        st.error(f"Error creating chart: {e}")',
        content,
        flags=re.MULTILINE | re.DOTALL
    )
    
    # Fix specific variable names in plotly charts
    content = re.sub(
        r'st\.plotly_chart\(fig,\s*use_container_width=True\)',
        'st.plotly_chart(fig, use_container_width=True)',
        content
    )
    
    # Fix broken if statements with extra spaces
    content = re.sub(r'if ([^:]+) :', r'if \1:', content)
    
    # Write the fixed content
    with open("src/dashboard/northstar_v3_ultimate_integrated_dashboard.py", 'w') as f:
        f.write(content)
    
    print("✅ Fixed all indentation errors")
    
    # Test compilation
    try:
        import py_compile
        py_compile.compile("src/dashboard/northstar_v3_ultimate_integrated_dashboard.py", doraise=True)
        print("✅ Dashboard compiles successfully")
        return True
    except py_compile.PyCompileError as e:
        print(f"❌ Still has syntax errors: {e}")
        return False

if __name__ == "__main__":
    main()