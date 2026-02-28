"""
Service Interfaces for Northstar V3 System Cohesion

This module defines the core service interfaces that enable clean dependency
injection and eliminate circular dependencies throughout the system.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable
from datetime import datetime
import pandas as pd
from dataclasses import dataclass
from enum import Enum

# Core data types
DataFrame = pd.DataFrame

class SystemState(Enum):
    """System state enumeration"""
    INITIALIZING = "initializing"
    RUNNING = "running"
    DEGRADED = "degraded"
    TERMINATED = "terminated"

class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class ValidationResult:
    """Standardized validation result"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class ProcessingResult:
    """Result of data processing operation"""
    success: bool
    data: Optional[DataFrame]
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

# Configuration Management Interfaces

class IConfigurationManager(ABC):
    """Interface for centralized configuration management"""
    
    @abstractmethod
    def load_config(self, config_name: str) -> Dict[str, Any]:
        """Load and validate configuration"""
        pass
    
    @abstractmethod
    def get_config(self, config_name: str, key: str = None) -> Any:
        """Get configuration value"""
        pass
    
    @abstractmethod
    def validate_all_configs(self) -> ValidationResult:
        """Validate all loaded configurations"""
        pass
    
    @abstractmethod
    def reload_config(self, config_name: str) -> bool:
        """Reload configuration from file"""
        pass

class IMarketConfiguration(ABC):
    """Interface for market-specific configuration"""
    
    @abstractmethod
    def get_market_name(self) -> str:
        """Get market name"""
        pass
    
    @abstractmethod
    def get_currency(self) -> str:
        """Get market currency"""
        pass
    
    @abstractmethod
    def get_trading_hours(self) -> Dict[str, str]:
        """Get trading hours"""
        pass
    
    @abstractmethod
    def get_sectors(self) -> List[str]:
        """Get sector classifications"""
        pass
    
    @abstractmethod
    def validate(self) -> ValidationResult:
        """Validate market configuration"""
        pass

# State Management Interfaces

class IStateManager(ABC):
    """Interface for unified state management"""
    
    @abstractmethod
    def update_state(self, 
                    component: str, 
                    updates: Dict[str, Any], 
                    timestamp: datetime = None) -> bool:
        """Update system state atomically"""
        pass
    
    @abstractmethod
    def get_state(self, component: str = None, as_of: datetime = None) -> Dict[str, Any]:
        """Get current or historical state"""
        pass
    
    @abstractmethod
    def subscribe_to_changes(self, 
                           component: str, 
                           callback: callable,
                           filter_func: callable = None):
        """Subscribe to state changes"""
        pass
    
    @abstractmethod
    def get_state_history(self, 
                         component: str, 
                         start_time: datetime, 
                         end_time: datetime) -> List[Dict[str, Any]]:
        """Get state history for time range"""
        pass

# Temporal Protection Interfaces

class ITemporalGuard(ABC):
    """Interface for temporal data protection"""
    
    @abstractmethod
    def set_time_context(self, as_of_date: datetime):
        """Set temporal context for data access"""
        pass
    
    @abstractmethod
    def validate_data_access(self, 
                           data_timestamp: datetime, 
                           request_timestamp: datetime) -> ValidationResult:
        """Validate temporal data access"""
        pass
    
    @abstractmethod
    def get_violations(self) -> List[Dict[str, Any]]:
        """Get temporal violations for audit"""
        pass
    
    @abstractmethod
    def clear_violations(self):
        """Clear violation history"""
        pass

# Data Pipeline Interfaces

class IDataSource(ABC):
    """Interface for data sources"""
    
    @abstractmethod
    def read_data(self, query: Dict[str, Any] = None) -> DataFrame:
        """Read data from source"""
        pass
    
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Get data schema"""
        pass
    
    @abstractmethod
    def get_last_update(self) -> datetime:
        """Get last update timestamp"""
        pass
    
    @abstractmethod
    def validate_connection(self) -> ValidationResult:
        """Validate data source connection"""
        pass

class IDataPipeline(ABC):
    """Interface for integrated data pipeline"""
    
    @abstractmethod
    def register_data_source(self, 
                           name: str, 
                           source: IDataSource,
                           dependencies: List[str] = None):
        """Register data source with dependencies"""
        pass
    
    @abstractmethod
    def process_pipeline(self, force_refresh: bool = False) -> ProcessingResult:
        """Process entire data pipeline"""
        pass
    
    @abstractmethod
    def get_data(self, source_name: str, as_of: datetime = None) -> DataFrame:
        """Get processed data from pipeline"""
        pass
    
    @abstractmethod
    def validate_pipeline(self) -> ValidationResult:
        """Validate pipeline configuration and dependencies"""
        pass

class ISchemaValidator(ABC):
    """Interface for schema validation"""
    
    @abstractmethod
    def validate_dataframe(self, 
                          df: DataFrame, 
                          schema_name: str) -> ValidationResult:
        """Validate DataFrame against schema"""
        pass
    
    @abstractmethod
    def register_schema(self, name: str, schema: Dict[str, Any]):
        """Register data schema"""
        pass
    
    @abstractmethod
    def get_schema(self, name: str) -> Dict[str, Any]:
        """Get registered schema"""
        pass

# Risk Management Interfaces

class IRiskEngine(ABC):
    """Interface for risk management engine"""
    
    @abstractmethod
    def validate_position_size(self, 
                             symbol: str, 
                             size: float, 
                             portfolio: Dict[str, Any]) -> ValidationResult:
        """Validate position size against limits"""
        pass
    
    @abstractmethod
    def calculate_portfolio_risk(self, portfolio: Dict[str, Any]) -> Dict[str, float]:
        """Calculate portfolio risk metrics"""
        pass
    
    @abstractmethod
    def check_risk_limits(self, portfolio: Dict[str, Any]) -> ValidationResult:
        """Check portfolio against risk limits"""
        pass
    
    @abstractmethod
    def get_emergency_actions(self, 
                            market_conditions: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get emergency risk actions for market conditions"""
        pass

class IRiskAuthority(ABC):
    """Interface for centralized risk parameter authority"""
    
    @abstractmethod
    def get_risk_parameters(self) -> Dict[str, float]:
        """Get current risk parameters"""
        pass
    
    @abstractmethod
    def update_risk_parameters(self, 
                             updates: Dict[str, float], 
                             authority_level: str) -> bool:
        """Update risk parameters with authority validation"""
        pass
    
    @abstractmethod
    def validate_risk_consistency(self) -> ValidationResult:
        """Validate risk parameter consistency"""
        pass

# Intelligence Engine Interfaces

class IIntelligenceEngine(ABC):
    """Interface for intelligence engine"""
    
    @abstractmethod
    def update_market_regime(self, 
                           market_data: DataFrame, 
                           as_of: datetime) -> Dict[str, Any]:
        """Update market regime assessment"""
        pass
    
    @abstractmethod
    def get_strategy_allocations(self, 
                               market_state: Dict[str, Any]) -> Dict[str, float]:
        """Get strategy allocations for market state"""
        pass
    
    @abstractmethod
    def validate_signal_consistency(self) -> ValidationResult:
        """Validate signal consistency across time"""
        pass
    
    @abstractmethod
    def detect_overfitting(self, 
                         signal_history: DataFrame) -> ValidationResult:
        """Detect potential overfitting in signals"""
        pass

# Error Handling Interfaces

class IErrorHandler(ABC):
    """Interface for comprehensive error handling"""
    
    @abstractmethod
    def handle_error(self, 
                    error: Exception, 
                    context: Dict[str, Any], 
                    severity: ErrorSeverity) -> bool:
        """Handle error with context and severity"""
        pass
    
    @abstractmethod
    def escalate_error(self, 
                      error: Exception, 
                      escalation_level: str) -> bool:
        """Escalate error to appropriate level"""
        pass
    
    @abstractmethod
    def get_error_history(self, 
                         start_time: datetime = None, 
                         end_time: datetime = None) -> List[Dict[str, Any]]:
        """Get error history for analysis"""
        pass
    
    @abstractmethod
    def should_fail_fast(self, error: Exception) -> bool:
        """Determine if error should trigger fail-fast"""
        pass

# Health Monitoring Interfaces

class IHealthMonitor(ABC):
    """Interface for system health monitoring"""
    
    @abstractmethod
    def register_component(self, 
                         component_name: str, 
                         health_check: callable):
        """Register component for health monitoring"""
        pass
    
    @abstractmethod
    def check_component_health(self, component_name: str) -> Dict[str, Any]:
        """Check health of specific component"""
        pass
    
    @abstractmethod
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health"""
        pass
    
    @abstractmethod
    def trigger_alert(self, 
                     component: str, 
                     severity: str, 
                     message: str):
        """Trigger health alert"""
        pass

# Performance and Caching Interfaces

class ICacheManager(ABC):
    """Interface for intelligent caching"""
    
    @abstractmethod
    def get(self, key: str, max_age: Optional[int] = None) -> Any:
        """Get cached value with freshness validation"""
        pass
    
    @abstractmethod
    def set(self, 
           key: str, 
           value: Any, 
           ttl: Optional[int] = None):
        """Set cached value with TTL"""
        pass
    
    @abstractmethod
    def invalidate(self, pattern: str = None):
        """Invalidate cache entries"""
        pass
    
    @abstractmethod
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        pass

# Logging and Audit Interfaces

class IAuditLogger(ABC):
    """Interface for audit logging"""
    
    @abstractmethod
    def log_state_change(self, 
                        component: str, 
                        old_state: Dict[str, Any], 
                        new_state: Dict[str, Any], 
                        timestamp: datetime):
        """Log state change for audit"""
        pass
    
    @abstractmethod
    def log_data_access(self, 
                       source: str, 
                       query: Dict[str, Any], 
                       timestamp: datetime):
        """Log data access for audit"""
        pass
    
    @abstractmethod
    def log_risk_action(self, 
                       action: str, 
                       parameters: Dict[str, Any], 
                       timestamp: datetime):
        """Log risk management action"""
        pass
    
    @abstractmethod
    def get_audit_trail(self, 
                       start_time: datetime, 
                       end_time: datetime, 
                       component: str = None) -> List[Dict[str, Any]]:
        """Get audit trail for time range"""
        pass

# Protocol for dependency injection compatibility
@runtime_checkable
class Injectable(Protocol):
    """Protocol for injectable services"""
    
    def initialize(self) -> bool:
        """Initialize the service"""
        ...
    
    def shutdown(self) -> bool:
        """Shutdown the service gracefully"""
        ...
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get service health status"""
        ...

# Factory interfaces for complex object creation

class IServiceFactory(ABC):
    """Interface for service factories"""
    
    @abstractmethod
    def create_service(self, 
                      service_type: str, 
                      config: Dict[str, Any]) -> Any:
        """Create service instance from configuration"""
        pass
    
    @abstractmethod
    def get_supported_services(self) -> List[str]:
        """Get list of supported service types"""
        pass

class IDataSourceFactory(ABC):
    """Interface for data source factories"""
    
    @abstractmethod
    def create_data_source(self, 
                          source_type: str, 
                          config: Dict[str, Any]) -> IDataSource:
        """Create data source from configuration"""
        pass
    
    @abstractmethod
    def validate_config(self, 
                       source_type: str, 
                       config: Dict[str, Any]) -> ValidationResult:
        """Validate data source configuration"""
        pass