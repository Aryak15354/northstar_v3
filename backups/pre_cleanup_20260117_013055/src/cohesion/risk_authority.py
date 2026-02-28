"""
Risk Authority Implementation for Northstar V3 System Cohesion

This module implements the unified risk parameter authority that serves as the
single source of truth for all risk management parameters across the system.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import threading
import json
from pathlib import Path

from src.service_interfaces import ValidationResult, IConfigurationManager, IAuditLogger

logger = logging.getLogger(__name__)

class AuthorityLevel(Enum):
    """Risk parameter authority levels"""
    SYSTEM = "system"           # System defaults
    CONFIGURATION = "config"    # Configuration file
    OPERATOR = "operator"       # Manual operator override
    EMERGENCY = "emergency"     # Emergency override (highest priority)

class RiskParameterType(Enum):
    """Types of risk parameters"""
    POSITION_LIMIT = "position_limit"
    EXPOSURE_LIMIT = "exposure_limit"
    DRAWDOWN_LIMIT = "drawdown_limit"
    VOLATILITY_LIMIT = "volatility_limit"
    CORRELATION_LIMIT = "correlation_limit"
    LEVERAGE_LIMIT = "leverage_limit"
    CONCENTRATION_LIMIT = "concentration_limit"

@dataclass
class RiskParameter:
    """Risk parameter with metadata"""
    name: str
    value: float
    parameter_type: RiskParameterType
    authority_level: AuthorityLevel
    set_by: str
    timestamp: datetime
    description: str = ""
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    emergency_override: bool = False
    
    def validate_value(self) -> ValidationResult:
        """Validate parameter value against constraints"""
        errors = []
        warnings = []
        
        if self.min_value is not None and self.value < self.min_value:
            errors.append(f"Value {self.value} below minimum {self.min_value}")
        
        if self.max_value is not None and self.value > self.max_value:
            errors.append(f"Value {self.value} above maximum {self.max_value}")
        
        # Type-specific validations
        if self.parameter_type in [RiskParameterType.POSITION_LIMIT, 
                                  RiskParameterType.EXPOSURE_LIMIT]:
            if self.value <= 0 or self.value > 1:
                errors.append(f"Limit {self.value} must be between 0 and 1")
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

@dataclass
class RiskConfiguration:
    """Complete risk configuration with consistency validation"""
    max_position_size: float = 0.08        # 8% max single position
    max_sector_exposure: float = 0.30       # 30% max sector exposure
    max_drawdown_threshold: float = 0.40    # 40% max drawdown
    volatility_threshold: float = 0.25      # 25% volatility threshold
    correlation_threshold: float = 0.70     # 70% correlation threshold
    max_leverage: float = 1.0               # 1x leverage (no leverage)
    concentration_limit: float = 0.20       # 20% concentration limit
    
    # Crisis management parameters
    crisis_volatility_threshold: float = 0.35
    crisis_drawdown_threshold: float = 0.15
    crisis_derisking_target: float = 0.40   # Reduce exposure by 40% in crisis
    crisis_derisking_timeframe: int = 10    # Days to achieve derisking
    
    # Emergency parameters
    emergency_stop_loss: float = 0.25       # 25% emergency stop loss
    emergency_max_exposure: float = 0.50    # 50% max exposure in emergency
    
    def validate_consistency(self) -> ValidationResult:
        """Validate mathematical consistency of risk parameters"""
        errors = []
        warnings = []
        
        # Mathematical consistency checks
        
        # 1. Position size vs sector exposure consistency
        min_positions_per_sector = 4  # Assume minimum 4 positions per sector
        if self.max_position_size * min_positions_per_sector > self.max_sector_exposure:
            errors.append(
                f"Position size {self.max_position_size:.2%} × {min_positions_per_sector} "
                f"= {self.max_position_size * min_positions_per_sector:.2%} "
                f"exceeds sector limit {self.max_sector_exposure:.2%}"
            )
        
        # 2. Crisis thresholds should be more restrictive than normal
        if self.crisis_volatility_threshold <= self.volatility_threshold:
            warnings.append(
                f"Crisis volatility threshold {self.crisis_volatility_threshold:.2%} "
                f"should be higher than normal threshold {self.volatility_threshold:.2%}"
            )
        
        # 3. Emergency limits should be more restrictive
        if self.emergency_max_exposure >= self.max_sector_exposure:
            warnings.append(
                f"Emergency exposure limit {self.emergency_max_exposure:.2%} "
                f"should be lower than normal sector limit {self.max_sector_exposure:.2%}"
            )
        
        # 4. Drawdown thresholds should be ordered
        if self.crisis_drawdown_threshold >= self.max_drawdown_threshold:
            errors.append(
                f"Crisis drawdown threshold {self.crisis_drawdown_threshold:.2%} "
                f"should be lower than max drawdown {self.max_drawdown_threshold:.2%}"
            )
        
        # 5. Concentration limit should be reasonable relative to position size
        if self.concentration_limit < self.max_position_size:
            warnings.append(
                f"Concentration limit {self.concentration_limit:.2%} "
                f"is lower than max position size {self.max_position_size:.2%}"
            )
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

class RiskAuthority:
    """
    Unified risk parameter authority - single source of truth for all risk parameters.
    
    Implements the Risk Authority system invariant that ensures all risk parameters
    are centralized, consistent, and properly validated before use.
    """
    
    def __init__(self, 
                 config_manager: IConfigurationManager,
                 audit_logger: IAuditLogger,
                 config_file: str = "config/risk.yaml"):
        self.config_manager = config_manager
        self.audit_logger = audit_logger
        self.config_file = config_file
        
        self._parameters: Dict[str, RiskParameter] = {}
        self._configuration = RiskConfiguration()
        self._lock = threading.RLock()
        self._authority_hierarchy = [
            AuthorityLevel.EMERGENCY,
            AuthorityLevel.OPERATOR,
            AuthorityLevel.CONFIGURATION,
            AuthorityLevel.SYSTEM
        ]
        
        # Load initial configuration
        self._load_configuration()
    
    def get_risk_parameters(self) -> Dict[str, float]:
        """Get current risk parameters as simple dict"""
        with self._lock:
            return {
                'max_position_size': self._configuration.max_position_size,
                'max_sector_exposure': self._configuration.max_sector_exposure,
                'max_drawdown_threshold': self._configuration.max_drawdown_threshold,
                'volatility_threshold': self._configuration.volatility_threshold,
                'correlation_threshold': self._configuration.correlation_threshold,
                'max_leverage': self._configuration.max_leverage,
                'concentration_limit': self._configuration.concentration_limit,
                'crisis_volatility_threshold': self._configuration.crisis_volatility_threshold,
                'crisis_drawdown_threshold': self._configuration.crisis_drawdown_threshold,
                'crisis_derisking_target': self._configuration.crisis_derisking_target,
                'emergency_stop_loss': self._configuration.emergency_stop_loss,
                'emergency_max_exposure': self._configuration.emergency_max_exposure
            }
    
    def get_risk_configuration(self) -> RiskConfiguration:
        """Get complete risk configuration object"""
        with self._lock:
            return self._configuration
    
    def update_risk_parameters(self, 
                             updates: Dict[str, float], 
                             authority_level: AuthorityLevel,
                             set_by: str,
                             reason: str = "") -> ValidationResult:
        """
        Update risk parameters with authority validation.
        
        Args:
            updates: Dictionary of parameter name -> new value
            authority_level: Authority level of the update
            set_by: Who is making the update
            reason: Reason for the update
            
        Returns:
            ValidationResult indicating success/failure
        """
        with self._lock:
            errors = []
            warnings = []
            
            # Validate authority for each parameter
            for param_name, new_value in updates.items():
                if not hasattr(self._configuration, param_name):
                    errors.append(f"Unknown risk parameter: {param_name}")
                    continue
                
                # Check if we have authority to update this parameter
                current_param = self._parameters.get(param_name)
                if current_param and not self._has_authority(authority_level, current_param.authority_level):
                    errors.append(
                        f"Insufficient authority to update {param_name}. "
                        f"Required: {current_param.authority_level.value}, "
                        f"Provided: {authority_level.value}"
                    )
            
            if errors:
                return ValidationResult(is_valid=False, errors=errors, warnings=warnings)
            
            # Create new configuration with updates
            new_config = RiskConfiguration(**{
                **self._configuration.__dict__,
                **updates
            })
            
            # Validate consistency of new configuration
            consistency_result = new_config.validate_consistency()
            if not consistency_result.is_valid:
                return consistency_result
            
            # Apply updates
            old_config = self._configuration.__dict__.copy()
            self._configuration = new_config
            
            # Update parameter metadata
            timestamp = datetime.now()
            for param_name, new_value in updates.items():
                param_type = self._get_parameter_type(param_name)
                
                self._parameters[param_name] = RiskParameter(
                    name=param_name,
                    value=new_value,
                    parameter_type=param_type,
                    authority_level=authority_level,
                    set_by=set_by,
                    timestamp=timestamp,
                    description=reason,
                    emergency_override=(authority_level == AuthorityLevel.EMERGENCY)
                )
            
            # Audit log the changes
            self.audit_logger.log_risk_action(
                action="update_parameters",
                parameters={
                    'updates': updates,
                    'authority_level': authority_level.value,
                    'set_by': set_by,
                    'reason': reason,
                    'old_config': old_config,
                    'new_config': self._configuration.__dict__
                },
                timestamp=timestamp
            )
            
            logger.info(f"Risk parameters updated by {set_by} with {authority_level.value} authority: {updates}")
            
            return ValidationResult(
                is_valid=True,
                errors=[],
                warnings=consistency_result.warnings
            )
    
    def validate_risk_consistency(self) -> ValidationResult:
        """Validate risk parameter consistency across all components"""
        with self._lock:
            return self._configuration.validate_consistency()
    
    def get_emergency_parameters(self) -> Dict[str, float]:
        """Get emergency risk parameters for crisis situations"""
        with self._lock:
            return {
                'max_position_size': min(self._configuration.max_position_size, 0.05),  # 5% max in emergency
                'max_sector_exposure': self._configuration.emergency_max_exposure,
                'max_drawdown_threshold': self._configuration.emergency_stop_loss,
                'volatility_threshold': self._configuration.crisis_volatility_threshold,
                'max_leverage': 0.5,  # Reduce leverage in emergency
                'concentration_limit': min(self._configuration.concentration_limit, 0.10)  # 10% max concentration
            }
    
    def trigger_emergency_override(self, 
                                 parameters: Dict[str, float], 
                                 triggered_by: str,
                                 reason: str) -> ValidationResult:
        """
        Trigger emergency risk parameter override.
        
        This bypasses normal authority checks and immediately applies
        emergency risk parameters.
        """
        logger.critical(f"EMERGENCY RISK OVERRIDE triggered by {triggered_by}: {reason}")
        
        return self.update_risk_parameters(
            updates=parameters,
            authority_level=AuthorityLevel.EMERGENCY,
            set_by=triggered_by,
            reason=f"EMERGENCY: {reason}"
        )
    
    def get_parameter_history(self, parameter_name: str) -> List[RiskParameter]:
        """Get history of changes for a specific parameter"""
        # This would typically query a database or audit log
        # For now, return current parameter if it exists
        with self._lock:
            if parameter_name in self._parameters:
                return [self._parameters[parameter_name]]
            return []
    
    def _load_configuration(self):
        """Load risk configuration from config manager"""
        try:
            risk_config = self.config_manager.get_config("risk")
            if risk_config:
                # Update configuration with loaded values
                for key, value in risk_config.items():
                    if hasattr(self._configuration, key):
                        setattr(self._configuration, key, value)
                        
                        # Create parameter metadata
                        param_type = self._get_parameter_type(key)
                        self._parameters[key] = RiskParameter(
                            name=key,
                            value=value,
                            parameter_type=param_type,
                            authority_level=AuthorityLevel.CONFIGURATION,
                            set_by="configuration_file",
                            timestamp=datetime.now(),
                            description="Loaded from configuration"
                        )
                
                logger.info("Risk configuration loaded from config manager")
            else:
                logger.warning("No risk configuration found, using defaults")
                
        except Exception as e:
            logger.error(f"Failed to load risk configuration: {e}")
            # Continue with defaults
    
    def _has_authority(self, 
                      requested_level: AuthorityLevel, 
                      current_level: AuthorityLevel) -> bool:
        """Check if requested authority level can override current level"""
        requested_priority = self._authority_hierarchy.index(requested_level)
        current_priority = self._authority_hierarchy.index(current_level)
        return requested_priority <= current_priority
    
    def _get_parameter_type(self, parameter_name: str) -> RiskParameterType:
        """Get parameter type from parameter name"""
        type_mapping = {
            'max_position_size': RiskParameterType.POSITION_LIMIT,
            'max_sector_exposure': RiskParameterType.EXPOSURE_LIMIT,
            'max_drawdown_threshold': RiskParameterType.DRAWDOWN_LIMIT,
            'volatility_threshold': RiskParameterType.VOLATILITY_LIMIT,
            'correlation_threshold': RiskParameterType.CORRELATION_LIMIT,
            'max_leverage': RiskParameterType.LEVERAGE_LIMIT,
            'concentration_limit': RiskParameterType.CONCENTRATION_LIMIT,
            'crisis_volatility_threshold': RiskParameterType.VOLATILITY_LIMIT,
            'crisis_drawdown_threshold': RiskParameterType.DRAWDOWN_LIMIT,
            'emergency_stop_loss': RiskParameterType.DRAWDOWN_LIMIT,
            'emergency_max_exposure': RiskParameterType.EXPOSURE_LIMIT
        }
        return type_mapping.get(parameter_name, RiskParameterType.POSITION_LIMIT)
    
    def get_authority_info(self) -> Dict[str, Any]:
        """Get information about current authority levels"""
        with self._lock:
            return {
                'parameters': {
                    name: {
                        'value': param.value,
                        'authority_level': param.authority_level.value,
                        'set_by': param.set_by,
                        'timestamp': param.timestamp.isoformat(),
                        'emergency_override': param.emergency_override
                    }
                    for name, param in self._parameters.items()
                },
                'authority_hierarchy': [level.value for level in self._authority_hierarchy]
            }
    
    def initialize(self) -> bool:
        """Initialize the risk authority"""
        try:
            # Validate initial configuration
            validation_result = self.validate_risk_consistency()
            if not validation_result.is_valid:
                logger.error(f"Risk configuration validation failed: {validation_result.errors}")
                return False
            
            if validation_result.warnings:
                for warning in validation_result.warnings:
                    logger.warning(f"Risk configuration warning: {warning}")
            
            logger.info("Risk authority initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize risk authority: {e}")
            return False
    
    def shutdown(self) -> bool:
        """Shutdown the risk authority"""
        logger.info("Risk authority shutdown")
        return True
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get risk authority health status"""
        with self._lock:
            validation_result = self.validate_risk_consistency()
            
            emergency_overrides = sum(
                1 for param in self._parameters.values() 
                if param.emergency_override
            )
            
            return {
                'healthy': validation_result.is_valid,
                'total_parameters': len(self._parameters),
                'emergency_overrides': emergency_overrides,
                'consistency_errors': len(validation_result.errors),
                'consistency_warnings': len(validation_result.warnings),
                'message': f"Managing {len(self._parameters)} risk parameters"
            }