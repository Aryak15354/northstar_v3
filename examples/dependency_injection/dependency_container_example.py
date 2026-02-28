#!/usr/bin/env python3
"""
Example: Dependency Container Usage
Demonstrates how to use the dependency container for clean imports
"""

import os
import sys

# Add project root to path (only in examples and scripts)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from src.cohesion.dependency_container import DependencyContainer
from src.cohesion.service_interfaces import IDataPipeline, IStateManager

def main():
    """Example of using dependency container instead of direct imports"""
    
    # Create dependency container
    container = DependencyContainer()
    
    try:
        # Resolve services through container instead of direct imports
        data_pipeline = container.resolve(IDataPipeline)
        state_manager = container.resolve(IStateManager)
        
        print("✅ Services resolved successfully through dependency injection")
        print(f"   Data pipeline: {type(data_pipeline).__name__}")
        print(f"   State manager: {type(state_manager).__name__}")
        
        # Use services
        if hasattr(data_pipeline, 'get_status'):
            status = data_pipeline.get_status()
            print(f"   Pipeline status: {status}")
        
    except Exception as e:
        print(f"⚠️ Service resolution failed (graceful degradation): {e}")
        print("   System continues with reduced functionality")

if __name__ == "__main__":
    main()
