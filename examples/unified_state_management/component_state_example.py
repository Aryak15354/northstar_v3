#!/usr/bin/env python3
"""
Example: Proper Component State Management

This shows how to use UnifiedStateManager for component state
instead of direct state manipulation.
"""

from src.cohesion.unified_state_manager import UnifiedStateManager, AuthorityLevel

class ExampleComponent:
    """Example component using unified state management"""
    
    def __init__(self):
        self.state_manager = UnifiedStateManager()
        self.component_name = "example_component"
    
    def initialize_state(self):
        """Initialize component state"""
        initial_state = {
            "status": "initialized",
            "last_update": "2024-01-01T00:00:00",
            "configuration": {
                "enabled": True,
                "threshold": 0.5
            }
        }
        
        # Use unified state manager for state updates
        success = self.state_manager.update_state(
            component=self.component_name,
            updates=initial_state,
            authority=AuthorityLevel.SYSTEM,
            reason="Component initialization"
        )
        
        if success:
            print(f"✅ {self.component_name} state initialized")
        else:
            print(f"❌ Failed to initialize {self.component_name} state")
    
    def update_configuration(self, new_config):
        """Update component configuration through state manager"""
        
        # Get current state
        current_state = self.state_manager.get_component_state(self.component_name)
        
        # Update configuration
        success = self.state_manager.update_state(
            component=self.component_name,
            updates={"configuration": new_config},
            authority=AuthorityLevel.SYSTEM,
            reason="Configuration update"
        )
        
        return success
    
    def get_status(self):
        """Get component status from unified state"""
        state = self.state_manager.get_component_state(self.component_name)
        return state.get("status", "unknown")

# Usage example
if __name__ == "__main__":
    component = ExampleComponent()
    component.initialize_state()
    
    # Update configuration
    new_config = {"enabled": True, "threshold": 0.7}
    success = component.update_configuration(new_config)
    print(f"Configuration update: {'✅ Success' if success else '❌ Failed'}")
    
    # Get status
    status = component.get_status()
    print(f"Component status: {status}")
