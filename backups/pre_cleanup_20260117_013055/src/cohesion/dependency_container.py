"""
Dependency Injection Container for Northstar V3 System Cohesion

This module implements a comprehensive dependency injection system that eliminates
circular dependencies and provides clean interface-based service registration.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, get_type_hints
from dataclasses import dataclass
from enum import Enum
import inspect
import threading
from contextlib import contextmanager

logger = logging.getLogger(__name__)

T = TypeVar('T')

class DependencyScope(Enum):
    """Dependency scope enumeration"""
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"

@dataclass
class ValidationResult:
    """Dependency validation result"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    
    def raise_if_invalid(self):
        """Raise exception if validation failed"""
        if not self.is_valid:
            error_msg = "Dependency validation failed:\n" + "\n".join(self.errors)
            raise DependencyValidationError(error_msg)

class DependencyValidationError(Exception):
    """Raised when dependency validation fails"""
    pass

class CircularDependencyError(Exception):
    """Raised when circular dependencies are detected"""
    pass

class DependencyResolutionError(Exception):
    """Raised when dependency cannot be resolved"""
    pass

@dataclass
class ServiceRegistration:
    """Service registration information"""
    interface_type: Type
    implementation_type: Optional[Type] = None
    factory: Optional[Callable] = None
    instance: Optional[Any] = None
    scope: DependencyScope = DependencyScope.TRANSIENT
    dependencies: List[Type] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []

class DependencyContainer:
    """
    Dependency injection container with interface registration and validation.
    
    Provides clean dependency management with:
    - Interface-based service registration
    - Circular dependency detection
    - Automatic dependency resolution
    - Singleton and transient scopes
    - Comprehensive validation
    """
    
    def __init__(self):
        self._registrations: Dict[Type, ServiceRegistration] = {}
        self._singletons: Dict[Type, Any] = {}
        self._resolution_stack: List[Type] = []
        self._lock = threading.RLock()
        self._validated = False
        
    def register_interface(self, 
                          interface_type: Type[T], 
                          implementation_type: Type[T],
                          scope: DependencyScope = DependencyScope.TRANSIENT) -> 'DependencyContainer':
        """
        Register interface implementation.
        
        Args:
            interface_type: The interface/abstract class
            implementation_type: The concrete implementation
            scope: Dependency scope (singleton, transient, scoped)
            
        Returns:
            Self for method chaining
        """
        with self._lock:
            # Validate that implementation implements interface
            if not issubclass(implementation_type, interface_type):
                raise DependencyValidationError(
                    f"{implementation_type} does not implement {interface_type}"
                )
            
            # Extract dependencies from constructor
            dependencies = self._extract_dependencies(implementation_type)
            
            registration = ServiceRegistration(
                interface_type=interface_type,
                implementation_type=implementation_type,
                scope=scope,
                dependencies=dependencies
            )
            
            self._registrations[interface_type] = registration
            self._validated = False
            
            logger.debug(f"Registered {interface_type.__name__} -> {implementation_type.__name__}")
            return self
    
    def register_singleton(self, interface_type: Type[T], instance: T) -> 'DependencyContainer':
        """
        Register singleton instance.
        
        Args:
            interface_type: The interface type
            instance: The singleton instance
            
        Returns:
            Self for method chaining
        """
        with self._lock:
            if not isinstance(instance, interface_type):
                raise DependencyValidationError(
                    f"Instance {type(instance)} is not of type {interface_type}"
                )
            
            registration = ServiceRegistration(
                interface_type=interface_type,
                instance=instance,
                scope=DependencyScope.SINGLETON
            )
            
            self._registrations[interface_type] = registration
            self._singletons[interface_type] = instance
            self._validated = False
            
            logger.debug(f"Registered singleton {interface_type.__name__}")
            return self
    
    def register_factory(self, 
                        interface_type: Type[T], 
                        factory: Callable[..., T],
                        scope: DependencyScope = DependencyScope.TRANSIENT) -> 'DependencyContainer':
        """
        Register factory function for interface.
        
        Args:
            interface_type: The interface type
            factory: Factory function that creates instances
            scope: Dependency scope
            
        Returns:
            Self for method chaining
        """
        with self._lock:
            # Extract dependencies from factory signature
            dependencies = self._extract_factory_dependencies(factory)
            
            registration = ServiceRegistration(
                interface_type=interface_type,
                factory=factory,
                scope=scope,
                dependencies=dependencies
            )
            
            self._registrations[interface_type] = registration
            self._validated = False
            
            logger.debug(f"Registered factory for {interface_type.__name__}")
            return self
    
    def resolve(self, interface_type: Type[T]) -> T:
        """
        Resolve interface to implementation.
        
        Args:
            interface_type: The interface to resolve
            
        Returns:
            Instance of the implementation
            
        Raises:
            DependencyResolutionError: If dependency cannot be resolved
            CircularDependencyError: If circular dependency detected
        """
        with self._lock:
            # Validate dependencies if not already done
            if not self._validated:
                validation_result = self.validate_dependencies()
                validation_result.raise_if_invalid()
                self._validated = True
            
            return self._resolve_internal(interface_type)
    
    def _resolve_internal(self, interface_type: Type[T]) -> T:
        """Internal resolution with circular dependency detection"""
        # Check for circular dependencies
        if interface_type in self._resolution_stack:
            cycle = " -> ".join([t.__name__ for t in self._resolution_stack])
            cycle += f" -> {interface_type.__name__}"
            raise CircularDependencyError(f"Circular dependency detected: {cycle}")
        
        # Check if already registered
        if interface_type not in self._registrations:
            raise DependencyResolutionError(f"No registration found for {interface_type}")
        
        registration = self._registrations[interface_type]
        
        # Return singleton if already created
        if registration.scope == DependencyScope.SINGLETON:
            if interface_type in self._singletons:
                return self._singletons[interface_type]
        
        # Add to resolution stack for circular dependency detection
        self._resolution_stack.append(interface_type)
        
        try:
            # Create instance
            if registration.instance is not None:
                instance = registration.instance
            elif registration.factory is not None:
                # Resolve factory dependencies
                factory_args = []
                for dep_type in registration.dependencies:
                    dep_instance = self._resolve_internal(dep_type)
                    factory_args.append(dep_instance)
                instance = registration.factory(*factory_args)
            elif registration.implementation_type is not None:
                # Resolve constructor dependencies
                constructor_args = []
                for dep_type in registration.dependencies:
                    dep_instance = self._resolve_internal(dep_type)
                    constructor_args.append(dep_instance)
                instance = registration.implementation_type(*constructor_args)
            else:
                raise DependencyResolutionError(
                    f"No implementation, factory, or instance for {interface_type}"
                )
            
            # Store singleton
            if registration.scope == DependencyScope.SINGLETON:
                self._singletons[interface_type] = instance
            
            return instance
            
        finally:
            # Remove from resolution stack
            self._resolution_stack.pop()
    
    def validate_dependencies(self) -> ValidationResult:
        """
        Validate all dependencies can be resolved.
        
        Returns:
            ValidationResult with any errors or warnings
        """
        errors = []
        warnings = []
        
        # Check all registrations have valid dependencies
        for interface_type, registration in self._registrations.items():
            for dep_type in registration.dependencies:
                if dep_type not in self._registrations:
                    errors.append(
                        f"{interface_type.__name__} depends on unregistered {dep_type.__name__}"
                    )
        
        # Check for circular dependencies
        try:
            visited = set()
            for interface_type in self._registrations:
                if interface_type not in visited:
                    self._check_circular_dependencies(interface_type, set(), visited)
        except CircularDependencyError as e:
            errors.append(str(e))
        
        # Check for missing abstract method implementations
        for interface_type, registration in self._registrations.items():
            if registration.implementation_type:
                missing_methods = self._check_interface_implementation(
                    interface_type, registration.implementation_type
                )
                if missing_methods:
                    errors.append(
                        f"{registration.implementation_type.__name__} missing methods: "
                        f"{', '.join(missing_methods)}"
                    )
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def _check_circular_dependencies(self, 
                                   interface_type: Type, 
                                   path: set, 
                                   visited: set):
        """Check for circular dependencies using DFS"""
        if interface_type in path:
            cycle_path = list(path) + [interface_type]
            cycle_names = [t.__name__ for t in cycle_path]
            raise CircularDependencyError(f"Circular dependency: {' -> '.join(cycle_names)}")
        
        if interface_type in visited:
            return
        
        visited.add(interface_type)
        
        if interface_type in self._registrations:
            registration = self._registrations[interface_type]
            path.add(interface_type)
            
            for dep_type in registration.dependencies:
                self._check_circular_dependencies(dep_type, path, visited)
            
            path.remove(interface_type)
    
    def _extract_dependencies(self, implementation_type: Type) -> List[Type]:
        """Extract dependencies from constructor type hints"""
        try:
            init_method = implementation_type.__init__
            type_hints = get_type_hints(init_method)
            
            # Skip 'self' parameter
            dependencies = []
            sig = inspect.signature(init_method)
            for param_name, param in sig.parameters.items():
                if param_name != 'self' and param_name in type_hints:
                    dependencies.append(type_hints[param_name])
            
            return dependencies
        except Exception as e:
            logger.warning(f"Could not extract dependencies for {implementation_type}: {e}")
            return []
    
    def _extract_factory_dependencies(self, factory: Callable) -> List[Type]:
        """Extract dependencies from factory function signature"""
        try:
            type_hints = get_type_hints(factory)
            sig = inspect.signature(factory)
            
            dependencies = []
            for param_name, param in sig.parameters.items():
                if param_name in type_hints:
                    dependencies.append(type_hints[param_name])
            
            return dependencies
        except Exception as e:
            logger.warning(f"Could not extract factory dependencies: {e}")
            return []
    
    def _check_interface_implementation(self, 
                                     interface_type: Type, 
                                     implementation_type: Type) -> List[str]:
        """Check if implementation provides all abstract methods"""
        missing_methods = []
        
        if hasattr(interface_type, '__abstractmethods__'):
            abstract_methods = interface_type.__abstractmethods__
            for method_name in abstract_methods:
                if not hasattr(implementation_type, method_name):
                    missing_methods.append(method_name)
                else:
                    impl_method = getattr(implementation_type, method_name)
                    if getattr(impl_method, '__isabstractmethod__', False):
                        missing_methods.append(method_name)
        
        return missing_methods
    
    def get_registration_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all registrations for debugging"""
        info = {}
        for interface_type, registration in self._registrations.items():
            info[interface_type.__name__] = {
                'implementation': registration.implementation_type.__name__ if registration.implementation_type else None,
                'scope': registration.scope.value,
                'has_factory': registration.factory is not None,
                'has_instance': registration.instance is not None,
                'dependencies': [dep.__name__ for dep in registration.dependencies]
            }
        return info
    
    @contextmanager
    def scope(self):
        """Context manager for scoped dependencies"""
        scoped_instances = {}
        original_singletons = self._singletons.copy()
        
        try:
            # Add scoped instances to singletons temporarily
            self._singletons.update(scoped_instances)
            yield self
        finally:
            # Restore original singletons
            self._singletons = original_singletons

class ServiceLocator:
    """
    Service locator pattern for dependency resolution with caching.
    
    Provides a simplified interface for service resolution with
    performance optimizations through caching.
    """
    
    def __init__(self, container: DependencyContainer):
        self.container = container
        self._resolution_cache: Dict[Type, Any] = {}
        self._cache_lock = threading.RLock()
    
    def get_service(self, service_type: Type[T]) -> T:
        """
        Get service instance with caching for singletons.
        
        Args:
            service_type: The service type to resolve
            
        Returns:
            Service instance
        """
        with self._cache_lock:
            # Check cache for singletons
            if service_type in self._resolution_cache:
                registration = self.container._registrations.get(service_type)
                if registration and registration.scope == DependencyScope.SINGLETON:
                    return self._resolution_cache[service_type]
            
            # Resolve from container
            instance = self.container.resolve(service_type)
            
            # Cache singletons
            registration = self.container._registrations.get(service_type)
            if registration and registration.scope == DependencyScope.SINGLETON:
                self._resolution_cache[service_type] = instance
            
            return instance
    
    def clear_cache(self):
        """Clear resolution cache"""
        with self._cache_lock:
            self._resolution_cache.clear()
    
    def get_cached_services(self) -> Dict[str, Any]:
        """Get all cached services for debugging"""
        with self._cache_lock:
            return {
                service_type.__name__: instance 
                for service_type, instance in self._resolution_cache.items()
            }

# Global container instance for application-wide use
_global_container: Optional[DependencyContainer] = None
_container_lock = threading.RLock()

def get_container() -> DependencyContainer:
    """Get the global dependency container"""
    global _global_container
    with _container_lock:
        if _global_container is None:
            _global_container = DependencyContainer()
        return _global_container

def set_container(container: DependencyContainer):
    """Set the global dependency container"""
    global _global_container
    with _container_lock:
        _global_container = container

def reset_container():
    """Reset the global dependency container"""
    global _global_container
    with _container_lock:
        _global_container = None


# Alias for backward compatibility
def get_dependency_container() -> DependencyContainer:
    """Alias for get_container() - for backward compatibility"""
    return get_container()
