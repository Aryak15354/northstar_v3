#!/usr/bin/env python3
"""
Example: Service Interface Pattern
Demonstrates proper dependency injection with interfaces
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class IDataService(ABC):
    """Interface for data services"""
    
    @abstractmethod
    def get_data(self, query: str) -> Dict[str, Any]:
        """Get data based on query"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if service is available"""
        pass

class MockDataService(IDataService):
    """Mock implementation for testing"""
    
    def get_data(self, query: str) -> Dict[str, Any]:
        return {"mock": True, "query": query}
    
    def is_available(self) -> bool:
        return True

class RealDataService(IDataService):
    """Real implementation"""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self._available = self._check_connection()
    
    def _check_connection(self) -> bool:
        # In real implementation, check actual connection
        return True
    
    def get_data(self, query: str) -> Dict[str, Any]:
        if not self.is_available():
            raise RuntimeError("Service not available")
        # Real data retrieval logic here
        return {"real": True, "query": query}
    
    def is_available(self) -> bool:
        return self._available

class DataServiceFactory:
    """Factory for creating data services with graceful degradation"""
    
    @staticmethod
    def create_service(prefer_real: bool = True) -> IDataService:
        """Create data service with fallback to mock if real service fails"""
        
        if prefer_real:
            try:
                # Try to create real service
                service = RealDataService("connection_string_here")
                if service.is_available():
                    return service
            except Exception as e:
                print(f"⚠️ Real service unavailable, falling back to mock: {e}")
        
        # Fallback to mock service
        return MockDataService()

# Usage example
def main():
    # Dependency injection - service is injected, not imported directly
    data_service = DataServiceFactory.create_service()
    
    try:
        result = data_service.get_data("test_query")
        print(f"✅ Data service working: {result}")
    except Exception as e:
        print(f"❌ Data service failed: {e}")

if __name__ == "__main__":
    main()
