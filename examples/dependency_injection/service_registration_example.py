#!/usr/bin/env python3
"""
Example: Proper Service Registration with Dependency Injection

This shows how to register and use services through dependency injection
instead of try/except ImportError blocks.
"""

from src.cohesion.dependency_container import get_container

class IExampleService:
    """Example service interface"""
    def process_data(self, data):
        pass

class ExampleService(IExampleService):
    """Example service implementation"""
    
    def __init__(self):
        self.name = "ExampleService"
    
    def process_data(self, data):
        """Process data with service"""
        return f"Processed by {self.name}: {data}"

class ExampleConsumer:
    """Example consumer that uses dependency injection"""
    
    def __init__(self):
        self.container = get_container()
        
        # Register service if not already registered
        try:
            self.container.resolve(IExampleService)
        except:
            self.container.register_interface(IExampleService, ExampleService)
    
    def do_work(self, data):
        """Do work using injected service"""
        
        try:
            # Get service through dependency injection
            service = self.container.resolve(IExampleService)
            return service.process_data(data)
        except:
            # Graceful degradation
            return f"Fallback processing: {data}"

# Usage example
if __name__ == "__main__":
    consumer = ExampleConsumer()
    result = consumer.do_work("test data")
    print(result)
