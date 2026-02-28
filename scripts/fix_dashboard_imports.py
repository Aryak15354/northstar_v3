#!/usr/bin/env python3
"""
🔧 FIX DASHBOARD IMPORTS
Clean up the dashboard import issues
"""

import os
import re

def fix_dashboard_imports():
    """Fix dashboard import issues"""
    
    dashboard_path = 'src/dashboard/northstar_v3_dashboard.py'
    
    if not os.path.exists(dashboard_path):
        print("❌ Dashboard file not found")
        return False
    
    with open(dashboard_path, 'r') as f:
        content = f.read()
    
    # Find the start of imports (after the docstring)
    docstring_end = content.find('"""', content.find('"""') + 3) + 3
    
    # Find the start of the CSS section
    css_start = content.find('st.markdown("""')
    
    if docstring_end == -1 or css_start == -1:
        print("❌ Could not find docstring or CSS section")
        return False
    
    # Extract the parts
    header = content[:docstring_end]
    css_and_rest = content[css_start:]
    
    # Create clean imports section
    clean_imports = '''

import streamlit as st
import sys
import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import json
import glob
from datetime import datetime, timedelta
import time
import warnings
from scipy import stats
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings('ignore')

# Time-series tracking imports
try:
    sys.path.append('src/dashboard/utils')
    from time_series_manager import time_series_manager
except ImportError:
    # Fallback if time_series_manager is not available
    time_series_manager = None
    st.warning("Time-series manager not available. Historical comparisons will be limited.")

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)

'''
    
    # Combine the parts
    new_content = header + clean_imports + css_and_rest
    
    # Write the fixed content
    with open(dashboard_path, 'w') as f:
        f.write(new_content)
    
    print("✅ Dashboard imports fixed")
    return True

def main():
    """Main execution"""
    
    print("🔧 FIXING DASHBOARD IMPORTS")
    print("=" * 40)
    
    if fix_dashboard_imports():
        print("✅ Dashboard imports fixed successfully!")
        print("   - Removed duplicate imports")
        print("   - Added proper error handling")
        print("   - Fixed sys import issue")
    else:
        print("❌ Failed to fix dashboard imports")

if __name__ == "__main__":
    main()