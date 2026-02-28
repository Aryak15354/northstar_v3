#!/usr/bin/env python3
"""
Test Intelligence Stack specifically to see what's failing
"""

import os
import sys

# Add src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(os.path.dirname(current_dir), 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

def test_intelligence_stack():
    """Test intelligence stack with detailed error reporting"""
    
    print("🧪 Testing Intelligence Stack with detailed errors...")
    
    try:
        print("   Importing intelligence stack...")
        from intelligence.intelligence_stack import IntelligenceStack
        print("   ✅ Import successful")
        
        print("   Creating intelligence stack instance...")
        intelligence = IntelligenceStack()
        print("   ✅ Instance creation successful")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_intelligence_stack()