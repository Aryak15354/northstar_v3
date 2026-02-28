#!/usr/bin/env python3
"""Debug script to isolate the import issue"""

import sys
import traceback

print("=== IMPORT DEBUG TEST ===")

# Test 1: Basic imports
print("\n1. Testing basic imports...")
try:
    import pandas as pd
    import numpy as np
    import os
    import json
    from datetime import datetime, timedelta
    from typing import Dict, List, Tuple, Optional, Any
    print("✓ Basic imports successful")
except Exception as e:
    print("✗ Basic imports failed:", e)
    traceback.print_exc()

# Test 2: V3 component imports
print("\n2. Testing V3 component imports...")
try:
    from src.validation.data_integrity import DataIntegrityEngine
    print("✓ DataIntegrityEngine imported")
except Exception as e:
    print("✗ DataIntegrityEngine import failed:", e)
    traceback.print_exc()

try:
    from src.execution.enhanced_transaction_cost_model import EnhancedTransactionCostModel
    print("✓ EnhancedTransactionCostModel imported")
except Exception as e:
    print("✗ EnhancedTransactionCostModel import failed:", e)
    traceback.print_exc()

try:
    from src.validation.universe_manager import UniverseManager
    print("✓ UniverseManager imported")
except Exception as e:
    print("✗ UniverseManager import failed:", e)
    traceback.print_exc()

# Test 3: Try to define a minimal class
print("\n3. Testing minimal class definition...")
try:
    class TestRealityCheckEngine(DataIntegrityEngine):
        def __init__(self):
            super().__init__()
            self.name = "Test Reality Check Engine"
    
    print("✓ Minimal class definition successful")
    
    # Test instantiation
    test_engine = TestRealityCheckEngine()
    print("✓ Class instantiation successful")
    
except Exception as e:
    print("✗ Class definition/instantiation failed:", e)
    traceback.print_exc()

# Test 4: Try to import the actual file
print("\n4. Testing actual file import...")
try:
    # First, let's see what happens when we exec the file
    with open('src/validation/reality_check_engine.py', 'r') as f:
        file_content = f.read()
    
    # Create a new namespace and add debugging
    namespace = {'__name__': '__main__', '__file__': 'src/validation/reality_check_engine.py'}
    
    # Add some debug prints to the content
    debug_content = """
print("DEBUG: Starting file execution")
try:
""" + file_content + """
    print("DEBUG: File execution completed successfully")
except Exception as e:
    print("DEBUG: Exception during file execution:", e)
    import traceback
    traceback.print_exc()
"""
    
    exec(debug_content, namespace)
    
    print("✓ File executed successfully")
    print("Available names:", [name for name in namespace.keys() if not name.startswith('_')])
    
    if 'RealityCheckEngine' in namespace:
        print("✓ RealityCheckEngine found in namespace")
        RealityCheckEngine = namespace['RealityCheckEngine']
        test_instance = RealityCheckEngine()
        print("✓ RealityCheckEngine instantiated successfully")
    else:
        print("✗ RealityCheckEngine not found in namespace")
        
except Exception as e:
    print("✗ File execution failed:", e)
    traceback.print_exc()

print("\n=== DEBUG TEST COMPLETE ===")