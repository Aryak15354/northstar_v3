#!/usr/bin/env python3
"""
Example: State Authority Hierarchy

This shows how to use authority levels to manage state conflicts
and ensure proper state management hierarchy.
"""

from src.cohesion.unified_state_manager import UnifiedStateManager, AuthorityLevel

class StateAuthorityExample:
    """Example showing state authority hierarchy"""
    
    def __init__(self):
        self.state_manager = UnifiedStateManager()
    
    def demonstrate_authority_hierarchy(self):
        """Demonstrate how authority hierarchy works"""
        
        print("🔐 DEMONSTRATING STATE AUTHORITY HIERARCHY")
        print("-" * 40)
        
        # System-level update (high authority)
        system_success = self.state_manager.update_state(
            component="risk",
            updates={"emergency_active": False},
            authority=AuthorityLevel.SYSTEM,
            reason="System initialization"
        )
        print(f"System update: {'✅ Success' if system_success else '❌ Failed'}")
        
        # Portfolio-level update (lower authority)
        portfolio_success = self.state_manager.update_state(
            component="risk",
            updates={"emergency_active": True},
            authority=AuthorityLevel.PORTFOLIO,
            reason="Portfolio risk assessment"
        )
        print(f"Portfolio update: {'✅ Success' if portfolio_success else '❌ Failed'}")
        
        # Emergency override (highest authority)
        emergency_success = self.state_manager.update_state(
            component="risk",
            updates={"emergency_active": True},
            authority=AuthorityLevel.EMERGENCY,
            reason="Emergency brake activation"
        )
        print(f"Emergency update: {'✅ Success' if emergency_success else '❌ Failed'}")
        
        # Check final state
        risk_state = self.state_manager.get_component_state("risk")
        print(f"Final emergency_active state: {risk_state.get('emergency_active')}")

# Usage example
if __name__ == "__main__":
    example = StateAuthorityExample()
    example.demonstrate_authority_hierarchy()
