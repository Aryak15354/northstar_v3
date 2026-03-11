"""
Operation Configuration Manager

This module provides comprehensive configuration management for the Northstar V3
operation system, including parameter validation, configuration templates, and
scenario-specific configurations.

Author: Northstar Team
Date: 2026-01-05
"""

import json
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime
import copy

from .base_types import (
    OperationConfig, CrisisPeriod, ValidationScenario, AlertConfig, 
    ReportConfig, BacktestConfig, WalkForwardConfig, StressTestConfig
)


@dataclass
class ConfigTemplate:
    """Configuration template definition."""
    name: str
    description: str
    scenario_type: str
    template_config: Dict[str, Any]
    required_parameters: List[str] = field(default_factory=list)
    optional_parameters: List[str] = field(default_factory=list)
    validation_rules: Dict[str, Any] = field(default_factory=dict)


class OperationConfigManager:
    """
    Comprehensive configuration manager for operation system.
    
    Provides configuration loading, validation, templating, and management
    for all operation scenarios and components.
    """
    
    def __init__(self, config_dir: str = "config/operation"):
        """Initialize the configuration manager."""
        self.logger = logging.getLogger("northstar_operation.config")
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Configuration storage
        self.base_config = None
        self.scenario_configs = {}
        self.config_templates = {}
        
        # Initialize default templates
        self._initialize_config_templates()
        
        self.logger.info(f"Configuration Manager initialized - config dir: {self.config_dir}")
    
    def load_base_config(self, config_path: Optional[str] = None) -> OperationConfig:
        """
        Load base operation configuration.
        
        Args:
            config_path: Path to configuration file (optional)
            
        Returns:
            OperationConfig: Loaded configuration
        """
        if config_path:
            config_file = Path(config_path)
        else:
            config_file = self.config_dir / "operation_config.yaml"
        
        if config_file.exists():
            self.logger.info(f"Loading configuration from: {config_file}")
            config_data = self._load_config_file(config_file)
            self.base_config = self._create_config_from_dict(config_data)
        else:
            self.logger.info("Using default configuration")
            self.base_config = OperationConfig()
            # Save default config for future reference
            self.save_config(self.base_config, str(config_file))
        
        return self.base_config
    
    def get_scenario_config(self, scenario_name: str, 
                          parameters: Optional[Dict[str, Any]] = None) -> OperationConfig:
        """
        Get configuration for a specific scenario.
        
        Args:
            scenario_name: Name of the scenario
            parameters: Additional parameters to override
            
        Returns:
            OperationConfig: Scenario-specific configuration
        """
        # Start with base config
        if not self.base_config:
            self.load_base_config()
        
        scenario_config = copy.deepcopy(self.base_config)
        
        # Apply scenario-specific overrides
        scenario_overrides = self._get_scenario_overrides(scenario_name)
        if scenario_overrides:
            scenario_config = self._merge_config(scenario_config, scenario_overrides)
        
        # Apply parameter overrides
        if parameters:
            scenario_config = self._apply_parameter_overrides(scenario_config, parameters)
        
        # Validate configuration
        self._validate_config(scenario_config, scenario_name)
        
        return scenario_config
    
    def create_config_from_template(self, template_name: str, 
                                  parameters: Dict[str, Any]) -> OperationConfig:
        """
        Create configuration from template.
        
        Args:
            template_name: Name of the configuration template
            parameters: Parameters to populate template
            
        Returns:
            OperationConfig: Configuration created from template
        """
        if template_name not in self.config_templates:
            raise ValueError(f"Unknown configuration template: {template_name}")
        
        template = self.config_templates[template_name]
        
        # Validate required parameters
        missing_params = [p for p in template.required_parameters if p not in parameters]
        if missing_params:
            raise ValueError(f"Missing required parameters for template {template_name}: {missing_params}")
        
        # Create config from template
        config_data = copy.deepcopy(template.template_config)
        config_data = self._substitute_template_parameters(config_data, parameters)
        
        config = self._create_config_from_dict(config_data)
        
        # Validate configuration
        self._validate_config(config, template.scenario_type)
        
        return config
    
    def save_config(self, config: OperationConfig, file_path: str):
        """
        Save configuration to file.
        
        Args:
            config: Configuration to save
            file_path: Path to save configuration
        """
        config_dict = self._config_to_dict(config)
        
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Sanitize filename to avoid illegal characters
        safe_filename = "".join(c for c in file_path.name if c.isalnum() or c in "._-")
        if not safe_filename:
            safe_filename = "config.yaml"
        
        safe_file_path = file_path.parent / safe_filename
        
        try:
            if safe_file_path.suffix.lower() == '.json':
                with open(safe_file_path, 'w', encoding='utf-8') as f:
                    json.dump(config_dict, f, indent=2, default=str, ensure_ascii=False)
            else:
                with open(safe_file_path, 'w', encoding='utf-8') as f:
                    yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
            
            self.logger.info(f"Configuration saved to: {safe_file_path}")
        except (OSError, UnicodeError) as e:
            # Fallback to a simple filename
            fallback_path = file_path.parent / "config.yaml"
            with open(fallback_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
            self.logger.info(f"Configuration saved to: {fallback_path} (fallback due to: {str(e)})")
    
    def validate_parameters(self, scenario_name: str, parameters: Dict[str, Any]) -> List[str]:
        """
        Validate parameters for a scenario.
        
        Args:
            scenario_name: Name of the scenario
            parameters: Parameters to validate
            
        Returns:
            List[str]: List of validation errors (empty if valid)
        """
        errors = []
        
        # Get validation rules for scenario
        validation_rules = self._get_scenario_validation_rules(scenario_name)
        
        for param_name, rules in validation_rules.items():
            if param_name in parameters:
                value = parameters[param_name]
                param_errors = self._validate_parameter(param_name, value, rules)
                errors.extend(param_errors)
        
        return errors
    
    def get_available_templates(self) -> List[str]:
        """Get list of available configuration templates."""
        return list(self.config_templates.keys())
    
    def get_template_info(self, template_name: str) -> Optional[ConfigTemplate]:
        """Get information about a configuration template."""
        return self.config_templates.get(template_name)
    
    def _initialize_config_templates(self):
        """Initialize default configuration templates."""
        # Crisis Validation Template
        self.config_templates["crisis_validation"] = ConfigTemplate(
            name="crisis_validation",
            description="Configuration template for crisis validation scenarios",
            scenario_type="crisis_validation",
            template_config={
                "max_concurrent_operations": 2,
                "operation_timeout_hours": 12,
                "min_sharpe_ratio": 0.3,
                "max_drawdown_threshold": 0.25,
                "max_var_breaches": 10,
                "crisis_periods": [
                    {
                        "name": "2008_financial_crisis",
                        "start_date": "2007-10-01",
                        "end_date": "2009-03-31",
                        "severity": "extreme"
                    }
                ]
            },
            required_parameters=["crisis_periods"],
            optional_parameters=["max_drawdown_threshold", "min_sharpe_ratio"]
        )
        
        # Alpha Validation Template
        self.config_templates["alpha_validation"] = ConfigTemplate(
            name="alpha_validation",
            description="Configuration template for alpha validation scenarios",
            scenario_type="alpha_validation",
            template_config={
                "max_concurrent_operations": 3,
                "operation_timeout_hours": 8,
                "min_information_ratio": 0.5,
                "min_hit_rate": 0.55,
                "min_signal_quality": 0.7,
                "market_regimes": ["bull_market", "bear_market", "sideways_market"]
            },
            required_parameters=["market_regimes"],
            optional_parameters=["min_information_ratio", "min_hit_rate"]
        )
        
        # Live Operation Template
        self.config_templates["live_operation"] = ConfigTemplate(
            name="live_operation",
            description="Configuration template for live operation scenarios",
            scenario_type="live_operation",
            template_config={
                "max_concurrent_operations": 1,
                "max_processing_latency_ms": 50.0,
                "max_execution_latency_ms": 200.0,
                "monitoring_interval_seconds": 10,
                "max_position_size": 5000,
                "enable_real_time_monitoring": True
            },
            required_parameters=["max_position_size"],
            optional_parameters=["max_processing_latency_ms", "monitoring_interval_seconds"]
        )
        
        # System Validation Template
        self.config_templates["system_validation"] = ConfigTemplate(
            name="system_validation",
            description="Configuration template for comprehensive system validation",
            scenario_type="system_validation",
            template_config={
                "max_concurrent_operations": 5,
                "operation_timeout_hours": 6,
                "min_data_quality": 0.98,
                "max_latency_ms": 100.0,
                "certification_threshold": 0.90
            },
            required_parameters=["certification_threshold"],
            optional_parameters=["min_data_quality", "max_latency_ms"]
        )
    
    def _load_config_file(self, file_path: Path) -> Dict[str, Any]:
        """Load configuration from file."""
        try:
            with open(file_path, 'r') as f:
                if file_path.suffix.lower() == '.json':
                    return json.load(f)
                else:
                    return yaml.safe_load(f)
        except Exception as e:
            self.logger.error(f"Failed to load config file {file_path}: {str(e)}")
            raise
    
    def _create_config_from_dict(self, config_data: Dict[str, Any]) -> OperationConfig:
        """Create OperationConfig from dictionary."""
        # Handle nested objects
        if 'crisis_periods' in config_data:
            crisis_periods = []
            for cp_data in config_data['crisis_periods']:
                if isinstance(cp_data, dict):
                    # Handle datetime conversion
                    start_date = cp_data['start_date']
                    if isinstance(start_date, str):
                        start_date = datetime.fromisoformat(start_date)
                    
                    end_date = cp_data['end_date']
                    if isinstance(end_date, str):
                        end_date = datetime.fromisoformat(end_date)
                    
                    crisis_periods.append(CrisisPeriod(
                        name=cp_data['name'],
                        start_date=start_date,
                        end_date=end_date,
                        severity=cp_data.get('severity', 'medium'),
                        characteristics=cp_data.get('characteristics', []),
                        description=cp_data.get('description', '')
                    ))
                elif isinstance(cp_data, CrisisPeriod):
                    crisis_periods.append(cp_data)
            config_data['crisis_periods'] = crisis_periods
        
        if 'alert_settings' in config_data:
            alert_data = config_data['alert_settings']
            if isinstance(alert_data, dict):
                config_data['alert_settings'] = AlertConfig(**alert_data)
        
        if 'reporting_config' in config_data:
            report_data = config_data['reporting_config']
            if isinstance(report_data, dict):
                config_data['reporting_config'] = ReportConfig(**report_data)
        
        # Filter out unknown parameters
        valid_params = {}
        for key, value in config_data.items():
            if hasattr(OperationConfig, key) or key in ['crisis_periods', 'alert_settings', 'reporting_config']:
                valid_params[key] = value
        
        return OperationConfig(**valid_params)
    
    def _config_to_dict(self, config: OperationConfig) -> Dict[str, Any]:
        """Convert OperationConfig to dictionary."""
        config_dict = asdict(config)
        
        # Convert datetime objects to strings
        if 'crisis_periods' in config_dict:
            for cp in config_dict['crisis_periods']:
                if 'start_date' in cp:
                    cp['start_date'] = cp['start_date'].isoformat()
                if 'end_date' in cp:
                    cp['end_date'] = cp['end_date'].isoformat()
        
        return config_dict
    
    def _get_scenario_overrides(self, scenario_name: str) -> Optional[Dict[str, Any]]:
        """Get scenario-specific configuration overrides."""
        scenario_overrides = {
            "crisis_validation": {
                "max_concurrent_operations": 2,
                "operation_timeout_hours": 12,
                "min_sharpe_ratio": 0.3,
                "max_drawdown_threshold": 0.25
            },
            "alpha_validation": {
                "max_concurrent_operations": 3,
                "operation_timeout_hours": 8,
                "min_information_ratio": 0.5
            },
            "live_operation": {
                "max_concurrent_operations": 1,
                "max_processing_latency_ms": 50.0,
                "enable_real_time_monitoring": True
            },
            "system_validation": {
                "max_concurrent_operations": 5,
                "operation_timeout_hours": 6
            },
            "stress_testing": {
                "max_concurrent_operations": 3,
                "operation_timeout_hours": 4
            }
        }
        
        return scenario_overrides.get(scenario_name)
    
    def _merge_config(self, base_config: OperationConfig, overrides: Dict[str, Any]) -> OperationConfig:
        """Merge configuration overrides into base configuration."""
        config_dict = asdict(base_config)
        
        for key, value in overrides.items():
            if hasattr(base_config, key):
                config_dict[key] = value
        
        return self._create_config_from_dict(config_dict)
    
    def _apply_parameter_overrides(self, config: OperationConfig, parameters: Dict[str, Any]) -> OperationConfig:
        """Apply parameter overrides to configuration."""
        config_dict = asdict(config)
        
        # Map parameters to configuration attributes
        parameter_mapping = {
            "max_position_size": "max_position_size",
            "risk_limit": "max_drawdown_threshold",
            "monitoring_interval": "monitoring_interval_seconds",
            "certification_threshold": "min_data_quality",
            "timeout_hours": "operation_timeout_hours"
        }
        
        for param_name, config_attr in parameter_mapping.items():
            if param_name in parameters and hasattr(config, config_attr):
                config_dict[config_attr] = parameters[param_name]
        
        return self._create_config_from_dict(config_dict)
    
    def _substitute_template_parameters(self, config_data: Dict[str, Any], 
                                      parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Substitute template parameters in configuration data."""
        def substitute_value(value):
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                param_name = value[2:-1]
                return parameters.get(param_name, value)
            elif isinstance(value, dict):
                return {k: substitute_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [substitute_value(item) for item in value]
            else:
                return value
        
        return substitute_value(config_data)
    
    def _validate_config(self, config: OperationConfig, scenario_name: str):
        """Validate configuration for scenario."""
        errors = []
        
        # Basic validation
        if config.max_concurrent_operations <= 0:
            errors.append("max_concurrent_operations must be positive")
        
        if config.operation_timeout_hours <= 0:
            errors.append("operation_timeout_hours must be positive")
        
        # Scenario-specific validation
        if scenario_name == "crisis_validation":
            if not config.crisis_periods:
                errors.append("crisis_periods cannot be empty for crisis validation")
            
            if config.max_drawdown_threshold <= 0:
                errors.append("max_drawdown_threshold must be positive")
        
        elif scenario_name == "live_operation":
            if config.max_position_size <= 0:
                errors.append("max_position_size must be positive for live operation")
            
            if config.max_processing_latency_ms <= 0:
                errors.append("max_processing_latency_ms must be positive")
        
        if errors:
            raise ValueError(f"Configuration validation failed: {'; '.join(errors)}")
    
    def _get_scenario_validation_rules(self, scenario_name: str) -> Dict[str, Dict[str, Any]]:
        """Get validation rules for scenario parameters."""
        validation_rules = {
            "crisis_validation": {
                "max_drawdown_threshold": {"type": float, "min": 0.0, "max": 1.0},
                "min_sharpe_ratio": {"type": float, "min": -2.0, "max": 5.0},
                "crisis_periods": {"type": list, "min_length": 1}
            },
            "alpha_validation": {
                "min_information_ratio": {"type": float, "min": 0.0, "max": 3.0},
                "min_hit_rate": {"type": float, "min": 0.0, "max": 1.0},
                "market_regimes": {"type": list, "min_length": 1}
            },
            "live_operation": {
                "max_position_size": {"type": int, "min": 1, "max": 100000},
                "max_processing_latency_ms": {"type": float, "min": 1.0, "max": 1000.0},
                "monitoring_interval": {"type": int, "min": 1, "max": 300}
            },
            "system_validation": {
                "certification_threshold": {"type": float, "min": 0.0, "max": 1.0},
                "min_data_quality": {"type": float, "min": 0.0, "max": 1.0}
            }
        }
        
        return validation_rules.get(scenario_name, {})
    
    def _validate_parameter(self, param_name: str, value: Any, rules: Dict[str, Any]) -> List[str]:
        """Validate a single parameter against rules."""
        errors = []
        
        # Type validation
        if "type" in rules:
            expected_type = rules["type"]
            if not isinstance(value, expected_type):
                errors.append(f"{param_name} must be of type {expected_type.__name__}")
                return errors  # Skip further validation if type is wrong
        
        # Numeric range validation
        if "min" in rules and value < rules["min"]:
            errors.append(f"{param_name} must be >= {rules['min']}")
        
        if "max" in rules and value > rules["max"]:
            errors.append(f"{param_name} must be <= {rules['max']}")
        
        # List length validation
        if "min_length" in rules and isinstance(value, list) and len(value) < rules["min_length"]:
            errors.append(f"{param_name} must have at least {rules['min_length']} items")
        
        if "max_length" in rules and isinstance(value, list) and len(value) > rules["max_length"]:
            errors.append(f"{param_name} must have at most {rules['max_length']} items")
        
        return errors
