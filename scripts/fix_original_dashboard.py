#!/usr/bin/env python3
"""
Fix Original Dashboard

Fixes the syntax errors in the original dashboard while preserving all features.
"""

import re

def main():
    """Fix the original dashboard"""
    
    print("🔧 Fixing original dashboard syntax errors...")
    
    # Read the original dashboard
    with open("src/dashboard/northstar_v3_ultimate_integrated_dashboard.py", 'r') as f:
        content = f.read()
    
    # Fix the corrupted HTML color attributes
    # These got corrupted with "is not None and len(...)" patterns
    
    # Fix risk status color
    content = re.sub(
        r'<span style="color[^>]*?risk_color[^>]*?>\{risk_label\}</span>',
        '<span style="color: {risk_color};">{risk_label}</span>',
        content,
        flags=re.DOTALL
    )
    
    # Fix edge detection color
    content = re.sub(
        r'<span style="color[^>]*?edge_color[^>]*?>\{edge_label\}</span>',
        '<span style="color: {edge_color};">{edge_label}</span>',
        content,
        flags=re.DOTALL
    )
    
    # Fix validation color
    content = re.sub(
        r'<span style="color[^>]*?val_color[^>]*?>\{val_label\}</span>',
        '<span style="color: {val_color};">{val_label}</span>',
        content,
        flags=re.DOTALL
    )
    
    # Fix automation color
    content = re.sub(
        r'<span style="color[^>]*?auto_color[^>]*?>\{auto_label\}</span>',
        '<span style="color: {auto_color};">{auto_label}</span>',
        content,
        flags=re.DOTALL
    )
    
    # Remove all the corrupted "is not None and len(...)" patterns
    content = re.sub(r'is not None and len\([^)]+\) > 0 is not None and len\([^)]+\) > 0\) > 0', '', content)
    content = re.sub(r'is not None and len\([^)]+\) > 0', '', content)
    
    # Fix corrupted variable assignments
    content = re.sub(r'if not df\.empty else 0\.0 if not df\.empty else 0\.0', '0.0', content)
    content = re.sub(r'max\(max\([^,]+,, 0\.001\) 0\.001\)', 'max(1.0, 0.001)', content)
    
    # Fix corrupted try/except blocks
    content = re.sub(r'try:\s+try:\s+st\.plotly_chart\([^)]+\)\s+except[^:]+:\s+st\.error\([^)]+\)\s+except[^:]+:\s+st\.error\([^)]+\)', 
                     'try:\n            st.plotly_chart(fig, use_container_width=True)\n        except Exception as e:\n            st.error(f"Error creating chart: {e}")', 
                     content, flags=re.DOTALL)
    
    # Fix the specific indentation error around line 367
    content = re.sub(r'if value is None :\s+return "No data yet"\s+try:\s+if True:\s+pass', 
                     'if value is None:\n            return "No data yet"\n        try:\n            if pd.isna(value):\n                return "No data yet"\n        except Exception:\n            pass', 
                     content)
    
    # Write the fixed content
    with open("src/dashboard/northstar_v3_ultimate_integrated_dashboard.py", 'w') as f:
        f.write(content)
    
    print("✅ Fixed original dashboard")
    
    # Test compilation
    try:
        import py_compile
        py_compile.compile("src/dashboard/northstar_v3_ultimate_integrated_dashboard.py", doraise=True)
        print("✅ Original dashboard compiles successfully")
        return True
    except py_compile.PyCompileError as e:
        print(f"❌ Still has syntax errors: {e}")
        return False

if __name__ == "__main__":
    main()