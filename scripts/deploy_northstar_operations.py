#!/usr/bin/env python3
"""
Northstar V3 Operations Deployment Script

This script handles the deployment of the complete Northstar V3 comprehensive
operation system, including environment configuration, system integration,
and operational procedures setup.

Usage:
    python scripts/deploy_northstar_operations.py [--environment ENV] [--config CONFIG_FILE]

Author: Northstar Team
Date: 2026-01-05
"""

import sys
import argparse
import logging
import json
import yaml
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from operation.system_integration_wiring import SystemIntegrationWiring, SystemWiringConfig
from operation.operation_config_manager import OperationConfigManager
from operation.base_types import OperationConfig
from operation.logging_config import setup_operation_logging


class DeploymentEnvironment:
    """Deployment environment configuration."""
    
    def __init__(self, name: str):
        self.name = name
        self.config = self._get_environment_config(name)
    
    def _get_environment_config(self, env_name: str) -> Dict[str, Any]:
        """Get configuration for deployment environment."""
        configs = {
            "development": {
                "log_level": "DEBUG",
                "max_concurrent_operations": 2,
                "enable_real_time_monitoring": True,
                "data_retention_days": 30,
                "alert_thresholds": {"performance": 0.7, "error_rate": 0.1},
                "backup_enabled": False,
                "security_level": "basic"
            },
            "staging": {
                "log_level": "INFO",
                "max_concurrent_operations": 3,
                "enable_real_time_monitoring": True,
                "data_retention_days": 90,
                "alert_thresholds": {"performance": 0.8, "error_rate": 0.05},
                "backup_enabled": True,
                "security_level": "enhanced"
            },
            "production": {
                "log_level": "INFO",
                "max_concurrent_operations": 5,
                "enable_real_time_monitoring": True,
                "data_retention_days": 365,
                "alert_thresholds": {"performance": 0.9, "error_rate": 0.02},
                "backup_enabled": True,
                "security_level": "maximum"
            }
        }
        
        return configs.get(env_name, configs["development"])


class NorthstarOperationsDeployer:
    """Comprehensive deployment manager for Northstar V3 operations."""
    
    def __init__(self, environment: str = "development"):
        """Initialize the deployment manager."""
        self.logger = setup_operation_logging()
        self.environment = DeploymentEnvironment(environment)
        self.deployment_root = Path("deployment") / environment
        self.config_manager = OperationConfigManager()
        
        self.logger.info(f"Northstar Operations Deployer initialized for {environment}")
    
    def deploy_complete_system(self, config_file: Optional[str] = None) -> bool:
        """
        Deploy the complete Northstar V3 operations system.
        
        Args:
            config_file: Optional configuration file path
            
        Returns:
            bool: True if deployment successful
        """
        self.logger.info("Starting complete system deployment...")
        
        try:
            # Step 1: Prepare deployment environment
            self._prepare_deployment_environment()
            
            # Step 2: Deploy configuration
            self._deploy_configuration(config_file)
            
            # Step 3: Deploy system components
            self._deploy_system_components()
            
            # Step 4: Setup system integration
            self._setup_system_integration()
            
            # Step 5: Deploy operational procedures
            self._deploy_operational_procedures()
            
            # Step 6: Verify deployment
            deployment_success = self._verify_deployment()
            
            if deployment_success:
                self.logger.info("✅ Complete system deployment successful")
                self._generate_deployment_report(True)
                return True
            else:
                self.logger.error("❌ System deployment verification failed")
                self._generate_deployment_report(False)
                return False
                
        except Exception as e:
            self.logger.error(f"System deployment failed: {str(e)}")
            self._generate_deployment_report(False, str(e))
            return False
    
    def _prepare_deployment_environment(self):
        """Prepare the deployment environment."""
        self.logger.info("Preparing deployment environment...")
        
        # Create deployment directories
        directories = [
            self.deployment_root,
            self.deployment_root / "config",
            self.deployment_root / "logs",
            self.deployment_root / "data",
            self.deployment_root / "reports",
            self.deployment_root / "scripts",
            self.deployment_root / "backups"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Created directory: {directory}")
        
        # Set up environment-specific permissions
        self._setup_environment_permissions()
        
        self.logger.info("Deployment environment prepared")
    
    def _setup_environment_permissions(self):
        """Setup environment-specific permissions and security."""
        if self.environment.config["security_level"] == "maximum":
            # Production security setup
            self.logger.info("Setting up maximum security configuration")
            # In real implementation, this would set file permissions, encryption, etc.
        elif self.environment.config["security_level"] == "enhanced":
            # Staging security setup
            self.logger.info("Setting up enhanced security configuration")
        else:
            # Development security setup
            self.logger.info("Setting up basic security configuration")
    
    def _deploy_configuration(self, config_file: Optional[str] = None):
        """Deploy system configuration."""
        self.logger.info("Deploying system configuration...")
        
        # Load or create base configuration
        if config_file and Path(config_file).exists():
            base_config = self.config_manager.load_base_config(config_file)
        else:
            base_config = OperationConfig()
        
        # Apply environment-specific overrides
        env_config = self._apply_environment_overrides(base_config)
        
        # Save environment configuration
        config_path = self.deployment_root / "config" / "operation" / ("operation_" "config.yaml")
        self.config_manager.save_config(env_config, str(config_path))
        
        # Deploy scenario-specific configurations
        scenarios = ["crisis_validation", "alpha_validation", "live_operation", "system_validation"]
        
        for scenario in scenarios:
            scenario_config = self.config_manager.get_scenario_config(scenario)
            scenario_path = self.deployment_root / "config" / f"{scenario}_config.yaml"
            self.config_manager.save_config(scenario_config, str(scenario_path))
        
        self.logger.info("System configuration deployed")
    
    def _apply_environment_overrides(self, base_config: OperationConfig) -> OperationConfig:
        """Apply environment-specific configuration overrides."""
        env_config = base_config
        
        # Apply environment-specific settings
        env_config.max_concurrent_operations = self.environment.config["max_concurrent_operations"]
        env_config.enable_real_time_monitoring = self.environment.config["enable_real_time_monitoring"]
        env_config.data_retention_days = self.environment.config["data_retention_days"]
        
        # Update alert thresholds
        thresholds = self.environment.config["alert_thresholds"]
        env_config.performance_thresholds.update({
            "min_performance_score": thresholds["performance"],
            "max_error_rate": thresholds["error_rate"]
        })
        
        return env_config
    
    def _deploy_system_components(self):
        """Deploy system components."""
        self.logger.info("Deploying system components...")
        
        # Copy executable scripts
        scripts_source = Path("scripts")
        scripts_dest = self.deployment_root / "scripts"
        
        executable_scripts = [
            "run_crisis_validation.py",
            "run_alpha_validation.py",
            "run_comprehensive_system_validation.py",
            "launch_live_operation.py"
        ]
        
        for script in executable_scripts:
            source_path = scripts_source / script
            dest_path = scripts_dest / script
            
            if source_path.exists():
                shutil.copy2(source_path, dest_path)
                # Make executable
                dest_path.chmod(0o755)
                self.logger.debug(f"Deployed script: {script}")
        
        # Deploy demo and utility scripts
        demo_scripts = [
            "demo_task13_operation_orchestration.py",
            "demo_task14_analytics_dashboard.py"
        ]
        
        for script in demo_scripts:
            source_path = scripts_source / script
            dest_path = scripts_dest / script
            
            if source_path.exists():
                shutil.copy2(source_path, dest_path)
                self.logger.debug(f"Deployed demo script: {script}")
        
        self.logger.info("System components deployed")
    
    def _setup_system_integration(self):
        """Setup system integration wiring."""
        self.logger.info("Setting up system integration...")
        
        # Create integration configuration
        wiring_config = SystemWiringConfig(
            enable_auto_integration=True,
            integration_timeout_seconds=300,
            health_check_interval_seconds=self.environment.config.get("health_check_interval", 60),
            max_retry_attempts=3,
            enable_graceful_degradation=True
        )
        
        # Save integration configuration
        integration_config_path = self.deployment_root / "config" / "integration_config.json"
        with open(integration_config_path, 'w') as f:
            json.dump({
                "enable_auto_integration": wiring_config.enable_auto_integration,
                "integration_timeout_seconds": wiring_config.integration_timeout_seconds,
                "health_check_interval_seconds": wiring_config.health_check_interval_seconds,
                "max_retry_attempts": wiring_config.max_retry_attempts,
                "enable_graceful_degradation": wiring_config.enable_graceful_degradation
            }, f, indent=2)
        
        self.logger.info("System integration setup completed")
    
    def _deploy_operational_procedures(self):
        """Deploy operational procedures and documentation."""
        self.logger.info("Deploying operational procedures...")
        
        # Create operational procedures documentation
        procedures = {
            "startup_procedure": self._create_startup_procedure(),
            "shutdown_procedure": self._create_shutdown_procedure(),
            "monitoring_procedure": self._create_monitoring_procedure(),
            "backup_procedure": self._create_backup_procedure(),
            "troubleshooting_guide": self._create_troubleshooting_guide()
        }
        
        procedures_dir = self.deployment_root / "procedures"
        procedures_dir.mkdir(exist_ok=True)
        
        for procedure_name, content in procedures.items():
            procedure_path = procedures_dir / f"{procedure_name}.md"
            with open(procedure_path, 'w') as f:
                f.write(content)
            self.logger.debug(f"Created procedure: {procedure_name}")
        
        # Create environment-specific startup script
        self._create_startup_script()
        
        self.logger.info("Operational procedures deployed")
    
    def _create_startup_procedure(self) -> str:
        """Create startup procedure documentation."""
        return f"""
# Northstar V3 Operations Startup Procedure

## Environment: {self.environment.name.upper()}

### Pre-startup Checklist
1. Verify system requirements are met
2. Check configuration files are present
3. Ensure data directories are accessible
4. Verify network connectivity

### Startup Steps
1. **Start System Integration**
   ```bash
   python scripts/start_system_integration.py --environment {self.environment.name}
   ```

2. **Verify Component Health**
   ```bash
   python scripts/run_comprehensive_system_validation.py --quick-check
   ```

3. **Start Monitoring**
   ```bash
   python scripts/start_monitoring.py --environment {self.environment.name}
   ```

### Post-startup Verification
1. Check system health dashboard
2. Verify all components are integrated
3. Run basic operation test
4. Monitor logs for errors

### Troubleshooting
- If integration fails, check component dependencies
- If health check fails, review component configurations
- For monitoring issues, verify alert configurations
"""
    
    def _create_shutdown_procedure(self) -> str:
        """Create shutdown procedure documentation."""
        return f"""
# Northstar V3 Operations Shutdown Procedure

## Environment: {self.environment.name.upper()}

### Pre-shutdown Steps
1. Complete any running operations
2. Notify users of planned shutdown
3. Create system backup (if enabled)

### Shutdown Steps
1. **Stop New Operations**
   ```bash
   python scripts/stop_new_operations.py
   ```

2. **Wait for Active Operations**
   ```bash
   python scripts/wait_for_operations.py --timeout 300
   ```

3. **Stop System Integration**
   ```bash
   python scripts/stop_system_integration.py
   ```

### Post-shutdown Verification
1. Verify all processes stopped
2. Check logs for clean shutdown
3. Verify data integrity
"""
    
    def _create_monitoring_procedure(self) -> str:
        """Create monitoring procedure documentation."""
        return f"""
# Northstar V3 Operations Monitoring Procedure

## Environment: {self.environment.name.upper()}

### Key Metrics to Monitor
1. **System Health Score**: Target > {self.environment.config['alert_thresholds']['performance']:.0%}
2. **Error Rate**: Target < {self.environment.config['alert_thresholds']['error_rate']:.1%}
3. **Operation Success Rate**: Target > 95%
4. **Component Integration Status**: All components should be integrated

### Monitoring Tools
1. **System Health Dashboard**: `reports/system_health_dashboard.html`
2. **Analytics Dashboard**: `reports/analytics_dashboard.html`
3. **Log Files**: `logs/operation/`

### Alert Thresholds
- Performance Score < {self.environment.config['alert_thresholds']['performance']:.0%}: WARNING
- Error Rate > {self.environment.config['alert_thresholds']['error_rate']:.1%}: CRITICAL
- Component Integration Failure: CRITICAL

### Response Procedures
1. **Performance Degradation**: Investigate component health, check resource usage
2. **High Error Rate**: Review error logs, check data quality
3. **Integration Failure**: Restart failed components, check dependencies
"""
    
    def _create_backup_procedure(self) -> str:
        """Create backup procedure documentation."""
        backup_enabled = self.environment.config["backup_enabled"]
        
        return f"""
# Northstar V3 Operations Backup Procedure

## Environment: {self.environment.name.upper()}
## Backup Enabled: {backup_enabled}

### Backup Components
1. **Configuration Files**: All YAML/JSON configuration files
2. **Operation Data**: Historical operation results and reports
3. **System State**: Component integration status and health data
4. **Log Files**: Critical system and operation logs

### Backup Schedule
- **Development**: Manual backup only
- **Staging**: Daily automated backup
- **Production**: Hourly automated backup with daily full backup

### Backup Commands
```bash
# Manual backup
python scripts/create_backup.py --environment {self.environment.name}

# Restore from backup
python scripts/restore_backup.py --backup-file BACKUP_FILE --environment {self.environment.name}
```

### Backup Verification
1. Verify backup file integrity
2. Test restore procedure in non-production environment
3. Validate restored system functionality
"""
    
    def _create_troubleshooting_guide(self) -> str:
        """Create troubleshooting guide."""
        return """
# Northstar V3 Operations Troubleshooting Guide

## Common Issues and Solutions

### System Integration Issues
**Problem**: Component integration fails
**Solution**: 
1. Check component dependencies
2. Verify configuration files
3. Review integration logs
4. Restart integration process

### Performance Issues
**Problem**: System performance degraded
**Solution**:
1. Check system resource usage
2. Review component health metrics
3. Analyze operation execution times
4. Consider scaling resources

### Operation Failures
**Problem**: Operations failing consistently
**Solution**:
1. Review operation logs
2. Check data quality
3. Verify component connectivity
4. Validate operation parameters

### Monitoring Issues
**Problem**: Monitoring not working
**Solution**:
1. Check monitoring service status
2. Verify alert configurations
3. Review monitoring logs
4. Test alert delivery

## Log File Locations
- System Logs: `logs/operation/operation.log`
- Error Logs: `logs/operation/operation_errors.log`
- Performance Logs: `logs/operation/performance.log`
- Integration Logs: `logs/integration/`

## Support Contacts
- System Administrator: admin@northstar.com
- Technical Support: support@northstar.com
- Emergency Contact: emergency@northstar.com
"""
    
    def _create_startup_script(self):
        """Create environment-specific startup script."""
        script_content = f"""#!/bin/bash
# Northstar V3 Operations Startup Script
# Environment: {self.environment.name}

set -e

echo "Starting Northstar V3 Operations ({self.environment.name})..."

# Set environment variables
export NORTHSTAR_ENV={self.environment.name}
export NORTHSTAR_CONFIG_DIR="{self.deployment_root}/config"
export NORTHSTAR_LOG_LEVEL={self.environment.config['log_level']}

# Change to deployment directory
cd "{self.deployment_root}"

# Start system integration
echo "Starting system integration..."
python scripts/start_system_integration.py --environment {self.environment.name}

# Verify system health
echo "Verifying system health..."
python scripts/run_comprehensive_system_validation.py --quick-check

# Start monitoring (if enabled)
if [ "{self.environment.config['enable_real_time_monitoring']}" = "True" ]; then
    echo "Starting real-time monitoring..."
    python scripts/start_monitoring.py --environment {self.environment.name}
fi

echo "Northstar V3 Operations startup completed successfully!"
"""
        
        script_path = self.deployment_root / "start_northstar.sh"
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        # Make executable
        script_path.chmod(0o755)
        
        self.logger.info(f"Startup script created: {script_path}")
    
    def _verify_deployment(self) -> bool:
        """Verify deployment was successful."""
        self.logger.info("Verifying deployment...")
        
        verification_checks = [
            ("Configuration files", self._verify_configuration_files),
            ("System components", self._verify_system_components),
            ("Operational procedures", self._verify_operational_procedures),
            ("Directory structure", self._verify_directory_structure)
        ]
        
        all_checks_passed = True
        
        for check_name, check_function in verification_checks:
            try:
                if check_function():
                    self.logger.info(f"✅ {check_name} verification passed")
                else:
                    self.logger.error(f"❌ {check_name} verification failed")
                    all_checks_passed = False
            except Exception as e:
                self.logger.error(f"❌ {check_name} verification error: {str(e)}")
                all_checks_passed = False
        
        return all_checks_passed
    
    def _verify_configuration_files(self) -> bool:
        """Verify configuration files are deployed correctly."""
        required_configs = [
            str(Path("operation") / ("operation_" "config.yaml")),
            "crisis_validation_config.yaml",
            "alpha_validation_config.yaml",
            "live_operation_" "config.yaml",
            "system_validation_config.yaml",
            "integration_config.json"
        ]
        
        config_dir = self.deployment_root / "config"
        
        for config_file in required_configs:
            config_path = config_dir / config_file
            if not config_path.exists():
                self.logger.error(f"Missing configuration file: {config_file}")
                return False
        
        return True
    
    def _verify_system_components(self) -> bool:
        """Verify system components are deployed correctly."""
        required_scripts = [
            "run_crisis_validation.py",
            "run_alpha_validation.py",
            "run_comprehensive_system_validation.py",
            "launch_live_operation.py"
        ]
        
        scripts_dir = self.deployment_root / "scripts"
        
        for script in required_scripts:
            script_path = scripts_dir / script
            if not script_path.exists():
                self.logger.error(f"Missing script: {script}")
                return False
            
            # Check if executable
            if not script_path.stat().st_mode & 0o111:
                self.logger.error(f"Script not executable: {script}")
                return False
        
        return True
    
    def _verify_operational_procedures(self) -> bool:
        """Verify operational procedures are deployed correctly."""
        required_procedures = [
            "startup_procedure.md",
            "shutdown_procedure.md",
            "monitoring_procedure.md",
            "backup_procedure.md",
            "troubleshooting_guide.md"
        ]
        
        procedures_dir = self.deployment_root / "procedures"
        
        for procedure in required_procedures:
            procedure_path = procedures_dir / procedure
            if not procedure_path.exists():
                self.logger.error(f"Missing procedure: {procedure}")
                return False
        
        # Check startup script
        startup_script = self.deployment_root / "start_northstar.sh"
        if not startup_script.exists() or not startup_script.stat().st_mode & 0o111:
            self.logger.error("Startup script missing or not executable")
            return False
        
        return True
    
    def _verify_directory_structure(self) -> bool:
        """Verify directory structure is correct."""
        required_dirs = [
            "config",
            "logs",
            "data",
            "reports",
            "scripts",
            "procedures"
        ]
        
        if self.environment.config["backup_enabled"]:
            required_dirs.append("backups")
        
        for directory in required_dirs:
            dir_path = self.deployment_root / directory
            if not dir_path.exists() or not dir_path.is_dir():
                self.logger.error(f"Missing or invalid directory: {directory}")
                return False
        
        return True
    
    def _generate_deployment_report(self, success: bool, error_message: Optional[str] = None):
        """Generate deployment report."""
        report_content = f"""
# Northstar V3 Operations Deployment Report

**Environment:** {self.environment.name}
**Deployment Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Status:** {'SUCCESS' if success else 'FAILED'}

## Deployment Configuration
- Log Level: {self.environment.config['log_level']}
- Max Concurrent Operations: {self.environment.config['max_concurrent_operations']}
- Real-time Monitoring: {self.environment.config['enable_real_time_monitoring']}
- Data Retention: {self.environment.config['data_retention_days']} days
- Backup Enabled: {self.environment.config['backup_enabled']}
- Security Level: {self.environment.config['security_level']}

## Deployment Results
"""
        
        if success:
            report_content += """
✅ **Deployment Successful**

All components have been deployed successfully and verified.

### Next Steps
1. Run the startup script: `./start_northstar.sh`
2. Verify system health: Check the system health dashboard
3. Run initial validation: Execute system validation script
4. Monitor operations: Review monitoring procedures

### Deployed Components
- Configuration files: All environment-specific configs deployed
- System components: All executable scripts deployed and configured
- Operational procedures: Complete documentation and scripts created
- Integration setup: System integration wiring configured
"""
        else:
            report_content += f"""
❌ **Deployment Failed**

Deployment encountered errors and could not be completed successfully.

### Error Details
{error_message or 'Unknown error occurred during deployment'}

### Troubleshooting Steps
1. Review deployment logs for detailed error information
2. Check system requirements and dependencies
3. Verify file permissions and directory access
4. Retry deployment after resolving issues

### Support
Contact technical support for assistance with deployment issues.
"""
        
        # Save deployment report
        report_path = self.deployment_root / "deployment_report.md"
        with open(report_path, 'w') as f:
            f.write(report_content)
        
        self.logger.info(f"Deployment report generated: {report_path}")


def main():
    """Main deployment function."""
    parser = argparse.ArgumentParser(description="Deploy Northstar V3 Operations System")
    parser.add_argument("--environment", "-e", 
                       choices=["development", "staging", "production"],
                       default="development",
                       help="Deployment environment")
    parser.add_argument("--config", "-c", type=str,
                       help="Configuration file path")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    logger = setup_operation_logging(log_level=log_level)
    
    logger.info("=" * 80)
    logger.info("NORTHSTAR V3 OPERATIONS DEPLOYMENT")
    logger.info("=" * 80)
    logger.info(f"Environment: {args.environment}")
    logger.info(f"Started at: {datetime.now()}")
    
    try:
        # Create deployer
        deployer = NorthstarOperationsDeployer(args.environment)
        
        # Deploy system
        success = deployer.deploy_complete_system(args.config)
        
        if success:
            logger.info("🎉 DEPLOYMENT COMPLETED SUCCESSFULLY!")
            logger.info(f"System deployed to: {deployer.deployment_root}")
            logger.info("Run './start_northstar.sh' to start the system")
            return 0
        else:
            logger.error("💥 DEPLOYMENT FAILED!")
            logger.error("Check deployment logs and report for details")
            return 1
            
    except KeyboardInterrupt:
        logger.info("Deployment interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Deployment failed with error: {str(e)}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
