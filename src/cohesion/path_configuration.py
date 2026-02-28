#!/usr/bin/env python3
"""
📁 PATH CONFIGURATION SYSTEM - TASK 14.1
Configurable File Paths to Replace Hardcoded Path Assumptions

This replaces all hardcoded file paths with configurable parameters
that can be adapted to any deployment environment.

SYSTEM LAWS ENFORCED:
- Invariant P1: Single Source of Truth for Path Configuration
- Invariant P2: Environment Adaptability - paths work in any environment
- Invariant P3: Path Consistency - all path handling is consistent

These are not suggestions - they are LAWS that enable flexible deployment.
"""

import os
import sys
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import warnings
warnings.filterwarnings('ignore')

class PathType(Enum):
    """Types of paths in the system"""
    DATA = "data"
    CONFIG = "config"
    LOGS = "logs"
    REPORTS = "reports"
    CACHE = "cache"
    TEMP = "temp"
    BACKUP = "backup"
    ARCHIVE = "archive"

class Environment(Enum):
    """Deployment environments"""
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"

@dataclass
class PathConfiguration:
    """Complete path configuration for the system"""
    
    # Base directories
    base_dir: str = "."
    data_dir: str = "data"
    config_dir: str = "config"
    logs_dir: str = "logs"
    reports_dir: str = "reports"
    cache_dir: str = "cache"
    temp_dir: str = "temp"
    backup_dir: str = "backup"
    
    # Data subdirectories
    raw_data_dir: str = "data/raw"
    processed_data_dir: str = "data/processed"
    validation_data_dir: str = "data/validation"
    simulation_data_dir: str = "data/simulation"
    audit_data_dir: str = "data/audit_trail"
    integrity_data_dir: str = "data/integrity"
    execution_data_dir: str = "data/execution"
    
    # Config subdirectories
    market_config_dir: str = "config/markets"
    risk_config_dir: str = "config/risk"
    strategy_config_dir: str = "config/strategies"
    system_config_dir: str = "config/system"
    
    # Logs subdirectories
    system_logs_dir: str = "logs/system"
    error_logs_dir: str = "logs/errors"
    audit_logs_dir: str = "logs/audit"
    performance_logs_dir: str = "logs/performance"
    
    # Reports subdirectories
    validation_reports_dir: str = "reports/validation"
    performance_reports_dir: str = "reports/performance"
    risk_reports_dir: str = "reports/risk"
    system_reports_dir: str = "reports/system"
    
    # Environment-specific overrides
    environment: Environment = Environment.DEVELOPMENT
    
    def __post_init__(self):
        """Initialize path configuration"""
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure all configured directories exist"""
        directories = [
            self.data_dir, self.config_dir, self.logs_dir, self.reports_dir,
            self.cache_dir, self.temp_dir, self.backup_dir,
            self.raw_data_dir, self.processed_data_dir, self.validation_data_dir,
            self.simulation_data_dir, self.audit_data_dir, self.integrity_data_dir,
            self.execution_data_dir, self.market_config_dir, self.risk_config_dir,
            self.strategy_config_dir, self.system_config_dir, self.system_logs_dir,
            self.error_logs_dir, self.audit_logs_dir, self.performance_logs_dir,
            self.validation_reports_dir, self.performance_reports_dir,
            self.risk_reports_dir, self.system_reports_dir
        ]
        
        for directory in directories:
            full_path = self.get_absolute_path(directory)
            try:
                os.makedirs(full_path, exist_ok=True)
            except PermissionError:
                # Skip directory creation if no permissions (e.g., production paths in test environment)
                pass
    
    def get_absolute_path(self, relative_path: str) -> str:
        """Get absolute path from relative path"""
        if os.path.isabs(relative_path):
            return relative_path
        return os.path.join(self.base_dir, relative_path)
    
    def get_data_path(self, data_type: str, filename: str = "") -> str:
        """Get path for data files"""
        path_mapping = {
            "raw": self.raw_data_dir,
            "processed": self.processed_data_dir,
            "validation": self.validation_data_dir,
            "simulation": self.simulation_data_dir,
            "audit": self.audit_data_dir,
            "integrity": self.integrity_data_dir,
            "execution": self.execution_data_dir,
            "backtests": os.path.join(self.processed_data_dir, "backtests"),
            "strategy_portfolios": os.path.join(self.processed_data_dir, "strategy_portfolios"),
            "performance": os.path.join(self.processed_data_dir, "performance"),
            "scores": os.path.join(self.processed_data_dir, "scores.parquet"),
            "prices": os.path.join(self.processed_data_dir, "prices.parquet"),
            "market_state": os.path.join(self.processed_data_dir, "market_state.parquet"),
            "strategy_beliefs": os.path.join(self.processed_data_dir, "strategy_beliefs.parquet"),
            "strategy_regret": os.path.join(self.processed_data_dir, "strategy_regret.parquet")
        }
        
        base_path = path_mapping.get(data_type, os.path.join(self.data_dir, data_type))
        full_path = self.get_absolute_path(base_path)
        
        if filename:
            return os.path.join(full_path, filename)
        return full_path
    
    def get_config_path(self, config_type: str, filename: str = "") -> str:
        """Get path for configuration files"""
        path_mapping = {
            "market": self.market_config_dir,
            "risk": self.risk_config_dir,
            "strategy": self.strategy_config_dir,
            "system": self.system_config_dir
        }
        
        base_path = path_mapping.get(config_type, os.path.join(self.config_dir, config_type))
        full_path = self.get_absolute_path(base_path)
        
        if filename:
            return os.path.join(full_path, filename)
        return full_path
    
    def get_log_path(self, log_type: str, filename: str = "") -> str:
        """Get path for log files"""
        path_mapping = {
            "system": self.system_logs_dir,
            "error": self.error_logs_dir,
            "audit": self.audit_logs_dir,
            "performance": self.performance_logs_dir
        }
        
        base_path = path_mapping.get(log_type, os.path.join(self.logs_dir, log_type))
        full_path = self.get_absolute_path(base_path)
        
        if filename:
            return os.path.join(full_path, filename)
        return full_path
    
    def get_report_path(self, report_type: str, filename: str = "") -> str:
        """Get path for report files"""
        path_mapping = {
            "validation": self.validation_reports_dir,
            "performance": self.performance_reports_dir,
            "risk": self.risk_reports_dir,
            "system": self.system_reports_dir
        }
        
        base_path = path_mapping.get(report_type, os.path.join(self.reports_dir, report_type))
        full_path = self.get_absolute_path(base_path)
        
        if filename:
            return os.path.join(full_path, filename)
        return full_path
    
    def get_cache_path(self, cache_type: str, filename: str = "") -> str:
        """Get path for cache files"""
        cache_path = os.path.join(self.cache_dir, cache_type)
        full_path = self.get_absolute_path(cache_path)
        
        if filename:
            return os.path.join(full_path, filename)
        return full_path
    
    def get_temp_path(self, filename: str = "") -> str:
        """Get path for temporary files"""
        full_path = self.get_absolute_path(self.temp_dir)
        
        if filename:
            return os.path.join(full_path, filename)
        return full_path
    
    def get_backup_path(self, backup_type: str, filename: str = "") -> str:
        """Get path for backup files"""
        backup_path = os.path.join(self.backup_dir, backup_type)
        full_path = self.get_absolute_path(backup_path)
        
        if filename:
            return os.path.join(full_path, filename)
        return full_path
    
    def validate_paths(self) -> List[str]:
        """Validate all configured paths"""
        errors = []
        
        # Check if base directory exists or can be created
        try:
            os.makedirs(self.get_absolute_path(self.base_dir), exist_ok=True)
        except Exception as e:
            errors.append(f"Cannot create base directory {self.base_dir}: {e}")
        
        # Check write permissions for key directories
        key_dirs = [self.data_dir, self.logs_dir, self.reports_dir, self.cache_dir, self.temp_dir]
        
        for directory in key_dirs:
            full_path = self.get_absolute_path(directory)
            try:
                os.makedirs(full_path, exist_ok=True)
                # Test write permission
                test_file = os.path.join(full_path, ".write_test")
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
            except Exception as e:
                errors.append(f"Cannot write to directory {directory}: {e}")
        
        return errors

class PathConfigurationManager:
    """
    Manager for path configurations with environment support
    
    Replaces hardcoded file paths with configurable parameters
    """
    
    def __init__(self, config_file: str = "config/paths.yaml", environment: Environment = Environment.DEVELOPMENT):
        self.config_file = config_file
        self.environment = environment
        self.configuration: Optional[PathConfiguration] = None
        
        # Load configuration
        self._load_configuration()
    
    def _load_configuration(self):
        """Load path configuration from file or create default"""
        
        # Ensure config directory exists
        config_dir = os.path.dirname(self.config_file)
        if config_dir:
            os.makedirs(config_dir, exist_ok=True)
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config_data = yaml.safe_load(f)
                
                # Get environment-specific configuration
                env_config = config_data.get(self.environment.value, config_data.get('default', {}))
                
                # Create PathConfiguration object
                self.configuration = PathConfiguration(
                    base_dir=env_config.get('base_dir', '.'),
                    data_dir=env_config.get('data_dir', 'data'),
                    config_dir=env_config.get('config_dir', 'config'),
                    logs_dir=env_config.get('logs_dir', 'logs'),
                    reports_dir=env_config.get('reports_dir', 'reports'),
                    cache_dir=env_config.get('cache_dir', 'cache'),
                    temp_dir=env_config.get('temp_dir', 'temp'),
                    backup_dir=env_config.get('backup_dir', 'backup'),
                    raw_data_dir=env_config.get('raw_data_dir', 'data/raw'),
                    processed_data_dir=env_config.get('processed_data_dir', 'data/processed'),
                    validation_data_dir=env_config.get('validation_data_dir', 'data/validation'),
                    simulation_data_dir=env_config.get('simulation_data_dir', 'data/simulation'),
                    audit_data_dir=env_config.get('audit_data_dir', 'data/audit_trail'),
                    integrity_data_dir=env_config.get('integrity_data_dir', 'data/integrity'),
                    execution_data_dir=env_config.get('execution_data_dir', 'data/execution'),
                    environment=self.environment
                )
                
                print(f"📁 Loaded path configuration for {self.environment.value}")
                
            except Exception as e:
                print(f"⚠️ Error loading path configuration: {e}")
                self._create_default_configuration()
        else:
            self._create_default_configuration()
    
    def _create_default_configuration(self):
        """Create default path configuration"""
        
        # Default configuration for all environments
        default_config = {
            'development': {
                'base_dir': '.',
                'data_dir': 'data',
                'config_dir': 'config',
                'logs_dir': 'logs',
                'reports_dir': 'reports',
                'cache_dir': 'cache',
                'temp_dir': 'temp',
                'backup_dir': 'backup',
                'raw_data_dir': 'data/raw',
                'processed_data_dir': 'data/processed',
                'validation_data_dir': 'data/validation',
                'simulation_data_dir': 'data/simulation',
                'audit_data_dir': 'data/audit_trail',
                'integrity_data_dir': 'data/integrity',
                'execution_data_dir': 'data/execution'
            },
            'testing': {
                'base_dir': './test_env',
                'data_dir': 'test_env/data',
                'config_dir': 'test_env/config',
                'logs_dir': 'test_env/logs',
                'reports_dir': 'test_env/reports',
                'cache_dir': 'test_env/cache',
                'temp_dir': 'test_env/temp',
                'backup_dir': 'test_env/backup',
                'raw_data_dir': 'test_env/data/raw',
                'processed_data_dir': 'test_env/data/processed',
                'validation_data_dir': 'test_env/data/validation',
                'simulation_data_dir': 'test_env/data/simulation',
                'audit_data_dir': 'test_env/data/audit_trail',
                'integrity_data_dir': 'test_env/data/integrity',
                'execution_data_dir': 'test_env/data/execution'
            },
            'production': {
                'base_dir': '/opt/northstar',
                'data_dir': '/opt/northstar/data',
                'config_dir': '/opt/northstar/config',
                'logs_dir': '/var/log/northstar',
                'reports_dir': '/opt/northstar/reports',
                'cache_dir': '/var/cache/northstar',
                'temp_dir': '/tmp/northstar',
                'backup_dir': '/opt/northstar/backup',
                'raw_data_dir': '/opt/northstar/data/raw',
                'processed_data_dir': '/opt/northstar/data/processed',
                'validation_data_dir': '/opt/northstar/data/validation',
                'simulation_data_dir': '/opt/northstar/data/simulation',
                'audit_data_dir': '/opt/northstar/data/audit_trail',
                'integrity_data_dir': '/opt/northstar/data/integrity',
                'execution_data_dir': '/opt/northstar/data/execution'
            }
        }
        
        # Save default configuration
        try:
            with open(self.config_file, 'w') as f:
                yaml.dump(default_config, f, default_flow_style=False)
            print(f"📝 Created default path configuration: {self.config_file}")
        except Exception as e:
            print(f"⚠️ Error creating default configuration: {e}")
        
        # Create PathConfiguration object for current environment
        env_config = default_config.get(self.environment.value, default_config['development'])
        self.configuration = PathConfiguration(
            **env_config,
            environment=self.environment
        )
    
    def get_configuration(self) -> Optional[PathConfiguration]:
        """Get current path configuration"""
        return self.configuration
    
    def validate_configuration(self) -> List[str]:
        """Validate current path configuration"""
        if not self.configuration:
            return ["No configuration loaded"]
        
        return self.configuration.validate_paths()
    
    def get_legacy_path_mapping(self) -> Dict[str, str]:
        """Get mapping of legacy hardcoded paths to new configurable paths"""
        if not self.configuration:
            return {}
        
        return {
            # Legacy hardcoded paths → New configurable paths
            'data/validation/production_hardening_report.json': self.configuration.get_data_path('validation', 'production_hardening_report.json'),
            'data/validation/production_readiness_certificate.json': self.configuration.get_data_path('validation', 'production_readiness_certificate.json'),
            'data/processed/backtests': self.configuration.get_data_path('backtests'),
            'data/processed/strategy_portfolios': self.configuration.get_data_path('strategy_portfolios'),
            'data/validation/strategy_deduplication.json': self.configuration.get_data_path('validation', 'strategy_deduplication.json'),
            'data/processed/performance/master.parquet': self.configuration.get_data_path('performance', 'master.parquet'),
            'data/processed/strategy_beliefs.parquet': self.configuration.get_data_path('strategy_beliefs'),
            'data/processed/strategy_regret.parquet': self.configuration.get_data_path('strategy_regret'),
            'data/validation/walk_forward_results.parquet': self.configuration.get_data_path('validation', 'walk_forward_results.parquet'),
            'data/validation/temporal_splits.json': self.configuration.get_data_path('validation', 'temporal_splits.json'),
            'data/integrity/data_release_calendar.parquet': self.configuration.get_data_path('integrity', 'data_release_calendar.parquet'),
            'data/processed/scores.parquet': self.configuration.get_data_path('scores'),
            'data/processed/prices.parquet': self.configuration.get_data_path('prices'),
            'data/processed/market_state.parquet': self.configuration.get_data_path('market_state'),
            'data/integrity/integrity_violations.parquet': self.configuration.get_data_path('integrity', 'integrity_violations.parquet'),
            'data/validation/enhanced_simulation_results': self.configuration.get_data_path('validation', 'enhanced_simulation_results'),
            'data/validation/simulation_states': self.configuration.get_data_path('validation', 'simulation_states'),
            'data/validation/simulation_logs': self.configuration.get_data_path('validation', 'simulation_logs'),
            'data/validation/benchmark_data': self.configuration.get_data_path('validation', 'benchmark_data'),
            'data/audit_trail': self.configuration.get_data_path('audit'),
            'data/validation/reality_check_results.json': self.configuration.get_data_path('validation', 'reality_check_results.json'),
            'data/validation/constraint_history.parquet': self.configuration.get_data_path('validation', 'constraint_history.parquet'),
            'data/validation/failure_analysis.json': self.configuration.get_data_path('validation', 'failure_analysis.json'),
            'data/validation/crisis_periods.json': self.configuration.get_data_path('validation', 'crisis_periods.json'),
            'data/validation/regime_analysis.parquet': self.configuration.get_data_path('validation', 'regime_analysis.parquet'),
            'data/simulation/daily_portfolio_metrics.parquet': self.configuration.get_data_path('simulation', 'daily_portfolio_metrics.parquet'),
            'data/simulation/regime_performance_tracking.parquet': self.configuration.get_data_path('simulation', 'regime_performance_tracking.parquet'),
            'data/simulation/drawdown_analysis.parquet': self.configuration.get_data_path('simulation', 'drawdown_analysis.parquet'),
            'data/simulation/specialist_attribution.parquet': self.configuration.get_data_path('simulation', 'specialist_attribution.parquet'),
            'data/simulation/risk_events.parquet': self.configuration.get_data_path('simulation', 'risk_events.parquet'),
            'data/simulation/complete_audit_trail.parquet': self.configuration.get_data_path('simulation', 'complete_audit_trail.parquet'),
            'data/simulation/simulation_summary.json': self.configuration.get_data_path('simulation', 'simulation_summary.json'),
            'reports/FINAL_SYSTEM_VALIDATION_CERTIFICATION_REPORT.md': self.configuration.get_report_path('system', 'FINAL_SYSTEM_VALIDATION_CERTIFICATION_REPORT.md')
        }

# Global path configuration manager instance
_path_config_manager = None

def get_path_config_manager(environment: Environment = Environment.DEVELOPMENT) -> PathConfigurationManager:
    """Get global path configuration manager instance"""
    global _path_config_manager
    if _path_config_manager is None:
        _path_config_manager = PathConfigurationManager(environment=environment)
    return _path_config_manager

def get_path_config() -> Optional[PathConfiguration]:
    """Get current path configuration"""
    manager = get_path_config_manager()
    return manager.get_configuration()

def get_data_path(data_type: str, filename: str = "") -> str:
    """Get configurable data path"""
    config = get_path_config()
    if config:
        return config.get_data_path(data_type, filename)
    return os.path.join("data", data_type, filename) if filename else os.path.join("data", data_type)

def get_config_path(config_type: str, filename: str = "") -> str:
    """Get configurable config path"""
    config = get_path_config()
    if config:
        return config.get_config_path(config_type, filename)
    return os.path.join("config", config_type, filename) if filename else os.path.join("config", config_type)

def get_log_path(log_type: str, filename: str = "") -> str:
    """Get configurable log path"""
    config = get_path_config()
    if config:
        return config.get_log_path(log_type, filename)
    return os.path.join("logs", log_type, filename) if filename else os.path.join("logs", log_type)

def get_report_path(report_type: str, filename: str = "") -> str:
    """Get configurable report path"""
    config = get_path_config()
    if config:
        return config.get_report_path(report_type, filename)
    return os.path.join("reports", report_type, filename) if filename else os.path.join("reports", report_type)

def main():
    """Test the path configuration system"""
    
    print("📁 TESTING PATH CONFIGURATION SYSTEM")
    print("=" * 60)
    
    # Test different environments
    environments = [Environment.DEVELOPMENT, Environment.TESTING, Environment.PRODUCTION]
    
    for env in environments:
        print(f"\n🔧 Testing {env.value} environment...")
        
        manager = PathConfigurationManager(environment=env)
        config = manager.get_configuration()
        
        if config:
            print(f"   Base directory: {config.base_dir}")
            print(f"   Data directory: {config.data_dir}")
            print(f"   Logs directory: {config.logs_dir}")
            print(f"   Reports directory: {config.reports_dir}")
            
            # Test path generation
            validation_path = config.get_data_path('validation', 'test_report.json')
            print(f"   Sample validation path: {validation_path}")
            
            system_log_path = config.get_log_path('system', 'northstar.log')
            print(f"   Sample log path: {system_log_path}")
            
            # Validate configuration
            errors = manager.validate_configuration()
            if errors:
                print(f"   ❌ Validation errors: {len(errors)}")
                for error in errors[:3]:  # Show first 3 errors
                    print(f"      - {error}")
            else:
                print(f"   ✅ Configuration valid")
    
    # Test legacy path mapping
    print(f"\n🔄 Testing legacy path mapping...")
    manager = PathConfigurationManager(environment=Environment.DEVELOPMENT)
    legacy_mapping = manager.get_legacy_path_mapping()
    
    print(f"   Legacy paths mapped: {len(legacy_mapping)}")
    for old_path, new_path in list(legacy_mapping.items())[:5]:  # Show first 5 mappings
        print(f"   {old_path} → {new_path}")
    
    print(f"\n✅ Path configuration system test complete!")
    print(f"   Hardcoded file paths can now be replaced with configurable parameters")
    
    return True

if __name__ == "__main__":
    main()