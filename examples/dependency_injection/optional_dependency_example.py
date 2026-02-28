#!/usr/bin/env python3
"""
Example: Optional Dependency Handling

This shows how to handle optional dependencies properly
without try/except ImportError blocks.
"""

from src.cohesion.dependency_container import get_container

class IOptionalService:
    """Optional service interface"""
    def enhanced_processing(self, data):
        pass

class OptionalDependencyHandler:
    """Handles optional dependencies through dependency injection"""
    
    def __init__(self):
        self.container = get_container()
    
    def use_optional_feature(self, data):
        """Use optional feature if available"""
        
        try:
            # Try to get optional service
            optional_service = self.container.resolve(IOptionalService)
            return optional_service.enhanced_processing(data)
        except:
            # Graceful degradation with clear messaging
            print("⚠️ Optional service not available - using basic processing")
            return self.basic_processing(data)
    
    def basic_processing(self, data):
        """Basic processing when optional service unavailable"""
        return f"Basic processing: {data}"

# Usage example
if __name__ == "__main__":
    handler = OptionalDependencyHandler()
    result = handler.use_optional_feature("test data")
    print(result)
