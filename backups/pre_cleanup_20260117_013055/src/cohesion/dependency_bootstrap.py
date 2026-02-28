"""
Dependency Injection Bootstrap for Northstar V3 System Cohesion

This module provides bootstrap functionality to configure the dependency
injection container with all system services and their implementations.
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path

from src.dependency_container import DependencyContainer, DependencyScope, get_container
from src.service_interfaces import (
    IConfigurationManager, IMarketConfiguration, IStateManager,
    ITemporalGuard, IDataPipeline, ISchemaValidator, IRiskEngine,
    IIntelligenceEngine, IErrorHandler, IHealthMonitor, ICacheManager,
    IAuditLogger, IDataSourceFactory
)

logger = logging.getLogger(__name__)

class DependencyBootstrap:
    """
    Bootstrap class for configuring dependency injection container.
    
    Provides methods to register all system services and their implementations
    with proper dependency relationships and scoping.
    """
    
    def __init__(self, container: Optional[DependencyContainer] = None):
        self.container = container or get_container()
        self._registered_services = set()
    
    def bootstrap_system(self, config_dir: str = "config") -> DependencyContainer:
        """
        Bootstrap the complete system with all dependencies.
        
        Args:
            config_dir: Configuration directory path
            
        Returns:
            Configured dependency container
        """
        logger.info("Starting system dependency bootstrap")
        
        try:
            # Register core services first (no dependencies)
            self._register_core_services(config_dir)
            
            # Register data services (depend on core)
            self._register_data_services()
            
            # Register intelligence services (depend on data)
            self._register_intelligence_services()
            
            # Register monitoring services (depend on all others)
            self._register_monitoring_services()
            
            # Validate all dependencies
            validation_result = self.container.validate_dependencies()
            if not validation_result.is_valid:
                logger.error("Dependency validation failed:")
                for error in validation_result.errors:
                    logger.error(f"  - {error}")
                raise RuntimeError("Dependency bootstrap failed validation")
            
            logger.info("System dependency bootstrap completed successfully")
            logger.info(f"Registered services: {', '.join(sorted(self._registered_services))}")
            
            return self.container
            
        except Exception as e:
            logger.error(f"Dependency bootstrap failed: {e}")
            raise
    
    def _register_core_services(self, config_dir: str):
        """Register core services with no external dependencies"""
        logger.debug("Registering core services")
        
        # Configuration Manager (singleton - single source of truth)
        from src.configuration_manager import ConfigurationManager
        self.container.register_interface(
            IConfigurationManager,
            ConfigurationManager,
            DependencyScope.SINGLETON
        )
        self._registered_services.add("ConfigurationManager")
        
        # Market Configuration (singleton - loaded once)
        from src.configuration_manager import MarketConfiguration
        self.container.register_interface(
            IMarketConfiguration,
            MarketConfiguration,
            DependencyScope.SINGLETON
        )
        self._registered_services.add("MarketConfiguration")
        
        # Error Handler (singleton - centralized error handling)
        from src.error_handler import ErrorHandler
        self.container.register_interface(
            IErrorHandler,
            ErrorHandler,
            DependencyScope.SINGLETON
        )
        self._registered_services.add("ErrorHandler")
        
        # Audit Logger (singleton - centralized audit trail)
        from src.audit_logger import AuditLogger
        self.container.register_interface(
            IAuditLogger,
            AuditLogger,
            DependencyScope.SINGLETON
        )
        self._registered_services.add("AuditLogger")
    
    def _register_data_services(self):
        """Register data services that depend on core services"""
        logger.debug("Registering data services")
        
        # State Manager (singleton - single source of truth)
        from src.unified_state_manager import UnifiedStateManager
        self.container.register_interface(
            IStateManager,
            UnifiedStateManager,
            DependencyScope.SINGLETON
        )
        self._registered_services.add("StateManager")
        
        # Temporal Guard (singleton - consistent temporal context)
        from src.temporal_guard import TemporalGuard
        self.container.register_interface(
            ITemporalGuard,
            TemporalGuard,
            DependencyScope.SINGLETON
        )
        self._registered_services.add("TemporalGuard")
        
        # Schema Validator (singleton - consistent validation rules)
        from src.schema_validator import SchemaValidator
        self.container.register_interface(
            ISchemaValidator,
            SchemaValidator,
            DependencyScope.SINGLETON
        )
        self._registered_services.add("SchemaValidator")
        
        # Cache Manager (singleton - centralized caching)
        from src.cache_manager import CacheManager
        self.container.register_interface(
            ICacheManager,
            CacheManager,
            DependencyScope.SINGLETON
        )
        self._registered_services.add("CacheManager")
        
        # Data Pipeline (singleton - coordinated data processing)
        from src.integrated_data_pipeline import IntegratedDataPipeline
        self.container.register_interface(
            IDataPipeline,
            IntegratedDataPipeline,
            DependencyScope.SINGLETON
        )
        self._registered_services.add("DataPipeline")
        
        # Data Source Factory (singleton - consistent data source creation)
        from src.data_source_factory import DataSourceFactory
        self.container.register_interface(
            IDataSourceFactory,
            DataSourceFactory,
            DependencyScope.SINGLETON
        )
        self._registered_services.add("DataSourceFactory")
    
    def _register_intelligence_services(self):
        """Register intelligence services that depend on data services"""
        logger.debug("Registering intelligence services")
        
        # Risk Authority (singleton - single source of truth for risk parameters)
        from src.risk_authority import RiskAuthority
        self.container.register_interface(
            RiskAuthority,
            RiskAuthority,
            DependencyScope.SINGLETON
        )
        self._registered_services.add("RiskAuthority")
        
        # Risk Engine (singleton - consistent risk management)
        from src.risk_engine import RiskEngine
        self.container.register_interface(
            IRiskEngine,
            RiskEngine,
            DependencyScope.SINGLETON
        )
        self._registered_services.add("RiskEngine")
        
        # Intelligence Engine (singleton - consistent intelligence state)
        from src.intelligence_engine import IntelligenceEngine
        self.container.register_interface(
            IIntelligenceEngine,
            IntelligenceEngine,
            DependencyScope.SINGLETON
        )
        self._registered_services.add("IntelligenceEngine")
    
    def _register_monitoring_services(self):
        """Register monitoring services that depend on all other services"""
        logger.debug("Registering monitoring services")
        
        # Health Monitor (singleton - centralized health monitoring)
        from src.health_monitor import HealthMonitor
        self.container.register_interface(
            IHealthMonitor,
            HealthMonitor,
            DependencyScope.SINGLETON
        )
        self._registered_services.add("HealthMonitor")
    
    def register_custom_service(self, 
                              interface_type: type, 
                              implementation_type: type,
                              scope: DependencyScope = DependencyScope.TRANSIENT,
                              service_name: str = None):
        """
        Register a custom service implementation.
        
        Args:
            interface_type: The service interface
            implementation_type: The concrete implementation
            scope: Dependency scope
            service_name: Optional service name for tracking
        """
        self.container.register_interface(interface_type, implementation_type, scope)
        
        service_name = service_name or implementation_type.__name__
        self._registered_services.add(service_name)
        logger.debug(f"Registered custom service: {service_name}")
    
    def register_service_factory(self, 
                               interface_type: type, 
                               factory_func: callable,
                               scope: DependencyScope = DependencyScope.TRANSIENT,
                               service_name: str = None):
        """
        Register a service factory function.
        
        Args:
            interface_type: The service interface
            factory_func: Factory function that creates instances
            scope: Dependency scope
            service_name: Optional service name for tracking
        """
        self.container.register_factory(interface_type, factory_func, scope)
        
        service_name = service_name or f"{interface_type.__name__}Factory"
        self._registered_services.add(service_name)
        logger.debug(f"Registered service factory: {service_name}")
    
    def get_registered_services(self) -> set:
        """Get set of registered service names"""
        return self._registered_services.copy()
    
    def validate_bootstrap(self) -> Dict[str, Any]:
        """
        Validate the bootstrap configuration.
        
        Returns:
            Validation report with status and details
        """
        validation_result = self.container.validate_dependencies()
        
        report = {
            'is_valid': validation_result.is_valid,
            'errors': validation_result.errors,
            'warnings': validation_result.warnings,
            'registered_services': list(self._registered_services),
            'service_count': len(self._registered_services),
            'registration_info': self.container.get_registration_info()
        }
        
        return report

class ServiceRegistry:
    """
    Service registry for managing service lifecycle and discovery.
    
    Provides centralized service management with initialization,
    shutdown, and health monitoring capabilities.
    """
    
    def __init__(self, container: DependencyContainer):
        self.container = container
        self._initialized_services = {}
        self._service_health = {}
    
    def initialize_all_services(self) -> Dict[str, bool]:
        """
        Initialize all registered services.
        
        Returns:
            Dictionary of service initialization results
        """
        results = {}
        
        for interface_type in self.container._registrations:
            try:
                service = self.container.resolve(interface_type)
                
                # Initialize if service supports it
                if hasattr(service, 'initialize'):
                    success = service.initialize()
                    results[interface_type.__name__] = success
                    if success:
                        self._initialized_services[interface_type] = service
                        logger.debug(f"Initialized service: {interface_type.__name__}")
                    else:
                        logger.error(f"Failed to initialize service: {interface_type.__name__}")
                else:
                    # Service doesn't need initialization
                    results[interface_type.__name__] = True
                    self._initialized_services[interface_type] = service
                    
            except Exception as e:
                logger.error(f"Error initializing {interface_type.__name__}: {e}")
                results[interface_type.__name__] = False
        
        logger.info(f"Initialized {len(self._initialized_services)} services")
        return results
    
    def shutdown_all_services(self) -> Dict[str, bool]:
        """
        Shutdown all initialized services.
        
        Returns:
            Dictionary of service shutdown results
        """
        results = {}
        
        # Shutdown in reverse order of initialization
        for interface_type, service in reversed(list(self._initialized_services.items())):
            try:
                if hasattr(service, 'shutdown'):
                    success = service.shutdown()
                    results[interface_type.__name__] = success
                    if success:
                        logger.debug(f"Shutdown service: {interface_type.__name__}")
                    else:
                        logger.error(f"Failed to shutdown service: {interface_type.__name__}")
                else:
                    # Service doesn't need shutdown
                    results[interface_type.__name__] = True
                    
            except Exception as e:
                logger.error(f"Error shutting down {interface_type.__name__}: {e}")
                results[interface_type.__name__] = False
        
        self._initialized_services.clear()
        logger.info("All services shutdown")
        return results
    
    def check_service_health(self) -> Dict[str, Dict[str, Any]]:
        """
        Check health of all initialized services.
        
        Returns:
            Dictionary of service health status
        """
        health_status = {}
        
        for interface_type, service in self._initialized_services.items():
            try:
                if hasattr(service, 'get_health_status'):
                    status = service.get_health_status()
                else:
                    # Default healthy status
                    status = {'healthy': True, 'message': 'Service running'}
                
                health_status[interface_type.__name__] = status
                self._service_health[interface_type] = status
                
            except Exception as e:
                error_status = {'healthy': False, 'error': str(e)}
                health_status[interface_type.__name__] = error_status
                self._service_health[interface_type] = error_status
        
        return health_status
    
    def get_service_status(self) -> Dict[str, Any]:
        """
        Get overall service registry status.
        
        Returns:
            Service registry status report
        """
        total_services = len(self.container._registrations)
        initialized_services = len(self._initialized_services)
        healthy_services = sum(
            1 for status in self._service_health.values() 
            if status.get('healthy', False)
        )
        
        return {
            'total_services': total_services,
            'initialized_services': initialized_services,
            'healthy_services': healthy_services,
            'initialization_rate': initialized_services / total_services if total_services > 0 else 0,
            'health_rate': healthy_services / initialized_services if initialized_services > 0 else 0,
            'service_health': self._service_health.copy()
        }

# Global bootstrap instance
_bootstrap_instance: Optional[DependencyBootstrap] = None

def get_bootstrap() -> DependencyBootstrap:
    """Get the global bootstrap instance"""
    global _bootstrap_instance
    if _bootstrap_instance is None:
        _bootstrap_instance = DependencyBootstrap()
    return _bootstrap_instance

def bootstrap_system(config_dir: str = "config") -> DependencyContainer:
    """Bootstrap the complete system with dependencies"""
    bootstrap = get_bootstrap()
    return bootstrap.bootstrap_system(config_dir)

def create_service_registry(container: DependencyContainer = None) -> ServiceRegistry:
    """Create a service registry for the container"""
    if container is None:
        container = get_container()
    return ServiceRegistry(container)