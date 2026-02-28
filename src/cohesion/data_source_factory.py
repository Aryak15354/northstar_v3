"""
Data Source Factory Stub Implementation for Dependency Injection System

This is a stub implementation to support the dependency injection system.
"""

import logging
from typing import Dict, Any
from src.service_interfaces import IDataSourceFactory, IDataSource, ValidationResult

logger = logging.getLogger(__name__)

class StubDataSource(IDataSource):
    """Stub data source for testing"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
    
    def read_data(self, query: Dict[str, Any] = None):
        """Read data from source"""
        import pandas as pd
        # Return empty DataFrame for stub
        return pd.DataFrame()
    
    def get_schema(self) -> Dict[str, Any]:
        """Get data schema"""
        return {'columns': [], 'types': {}}
    
    def get_last_update(self):
        """Get last update timestamp"""
        from datetime import datetime
        return datetime.now()
    
    def validate_connection(self) -> ValidationResult:
        """Validate data source connection"""
        return ValidationResult(is_valid=True, errors=[], warnings=[])

class DataSourceFactory(IDataSourceFactory):
    """Stub data source factory implementation for dependency injection"""
    
    def __init__(self):
        self.supported_types = ['csv', 'parquet', 'database', 'api']
    
    def create_data_source(self, 
                          source_type: str, 
                          config: Dict[str, Any]) -> IDataSource:
        """Create data source from configuration"""
        if source_type not in self.supported_types:
            raise ValueError(f"Unsupported source type: {source_type}")
        
        # Return stub data source
        return StubDataSource(f"{source_type}_source", config)
    
    def validate_config(self, 
                       source_type: str, 
                       config: Dict[str, Any]) -> ValidationResult:
        """Validate data source configuration"""
        errors = []
        warnings = []
        
        if source_type not in self.supported_types:
            errors.append(f"Unsupported source type: {source_type}")
        
        if 'name' not in config:
            errors.append("Missing required 'name' field in config")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def initialize(self) -> bool:
        """Initialize the data source factory"""
        logger.debug("Data source factory initialized (stub)")
        return True
    
    def shutdown(self) -> bool:
        """Shutdown the data source factory"""
        logger.debug("Data source factory shutdown (stub)")
        return True
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get data source factory health status"""
        return {
            'healthy': True,
            'supported_types': self.supported_types,
            'message': f"Factory supports {len(self.supported_types)} source types"
        }