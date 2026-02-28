#!/usr/bin/env python3
"""
Production Deployment Script
Automated deployment pipeline for Northstar V3
"""

import os
import sys
import json
import shutil
import subprocess
from datetime import datetime
from typing import Dict, Any, List, Optional

class ProductionDeployer:
    """Production deployment manager"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_deployment_config(config_path)
        self.deployment_log = []
        
    def _load_deployment_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load deployment configuration"""
        
        default_config = {
            "deployment": {
                "environment": "production",
                "backup_enabled": True,
                "health_check_enabled": True,
                "rollback_enabled": True,
                "pre_deployment_checks": True,
                "post_deployment_validation": True
            },
            "paths": {
                "source_dir": ".",
                "backup_dir": "backups",
                "logs_dir": "logs",
                "config_dir": "config"
            },
            "services": [
                "northstar_engine",
                "data_pipeline",
                "health_monitor"
            ]
        }
        
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
            return {**default_config, **config}
        
        return default_config
    
    def log_step(self, message: str, success: bool = True):
        """Log deployment step"""
        
        timestamp = datetime.now().isoformat()
        status = "✅" if success else "❌"
        log_entry = f"{timestamp} {status} {message}"
        
        print(log_entry)
        self.deployment_log.append({
            "timestamp": timestamp,
            "message": message,
            "success": success
        })
    
    def pre_deployment_checks(self) -> bool:
        """Run pre-deployment checks"""
        
        self.log_step("Starting pre-deployment checks")
        
        checks_passed = True
        
        # Check if configuration is valid
        config_validator = os.path.join("deployment", "scripts", "validate_config.py")
        if os.path.exists(config_validator):
            try:
                result = subprocess.run([
                    sys.executable, config_validator,
                    "--config", "deployment/config/production.yaml"
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    self.log_step("Configuration validation passed")
                else:
                    self.log_step("Configuration validation failed", False)
                    checks_passed = False
            except Exception as e:
                self.log_step(f"Configuration validation error: {e}", False)
                checks_passed = False
        
        # Check if required files exist
        required_files = [
            "src/intelligence/institutional_alpha_engine.py",
            "src/cohesion/unified_state_manager.py",
            "src/cohesion/temporal_guard.py",
            "requirements.txt"
        ]
        
        for file_path in required_files:
            if os.path.exists(file_path):
                self.log_step(f"Required file exists: {file_path}")
            else:
                self.log_step(f"Missing required file: {file_path}", False)
                checks_passed = False
        
        # Check Python dependencies
        try:
            import pandas, numpy, yaml
            self.log_step("Core dependencies available")
        except ImportError as e:
            self.log_step(f"Missing dependencies: {e}", False)
            checks_passed = False
        
        return checks_passed
    
    def create_backup(self) -> bool:
        """Create deployment backup"""
        
        self.log_step("Creating deployment backup")
        
        try:
            backup_dir = self.config["paths"]["backup_dir"]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"backup_{timestamp}")
            
            os.makedirs(backup_path, exist_ok=True)
            
            # Backup key directories
            backup_items = [
                ("src", "source_code"),
                ("config", "configuration"),
                ("scripts", "scripts"),
                ("reports", "reports")
            ]
            
            for source, dest in backup_items:
                if os.path.exists(source):
                    dest_path = os.path.join(backup_path, dest)
                    if os.path.isdir(source):
                        shutil.copytree(source, dest_path, ignore_errors=True)
                    else:
                        shutil.copy2(source, dest_path)
                    
                    self.log_step(f"Backed up {source} to {dest}")
            
            # Save backup metadata
            backup_metadata = {
                "timestamp": timestamp,
                "environment": self.config["deployment"]["environment"],
                "backup_path": backup_path,
                "items_backed_up": [item[0] for item in backup_items if os.path.exists(item[0])]
            }
            
            metadata_path = os.path.join(backup_path, "backup_metadata.json")
            with open(metadata_path, 'w') as f:
                json.dump(backup_metadata, f, indent=2)
            
            self.log_step(f"Backup created successfully: {backup_path}")
            return True
            
        except Exception as e:
            self.log_step(f"Backup creation failed: {e}", False)
            return False
    
    def deploy_application(self) -> bool:
        """Deploy application"""
        
        self.log_step("Starting application deployment")
        
        try:
            # Install/update dependencies
            if os.path.exists("requirements.txt"):
                result = subprocess.run([
                    sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    self.log_step("Dependencies installed successfully")
                else:
                    self.log_step("Dependency installation failed", False)
                    return False
            
            # Copy configuration files
            config_source = "deployment/config/production.yaml"
            config_dest = "config/production.yaml"
            
            if os.path.exists(config_source):
                os.makedirs(os.path.dirname(config_dest), exist_ok=True)
                shutil.copy2(config_source, config_dest)
                self.log_step("Production configuration deployed")
            
            # Set up logging directory
            logs_dir = self.config["paths"]["logs_dir"]
            os.makedirs(logs_dir, exist_ok=True)
            self.log_step("Logging directory prepared")
            
            self.log_step("Application deployment completed")
            return True
            
        except Exception as e:
            self.log_step(f"Application deployment failed: {e}", False)
            return False
    
    def post_deployment_validation(self) -> bool:
        """Run post-deployment validation"""
        
        self.log_step("Starting post-deployment validation")
        
        try:
            # Test basic imports
            sys.path.insert(0, ".")
            
            try:
                from src.cohesion.unified_state_manager import UnifiedStateManager
                self.log_step("Core imports working")
            except ImportError as e:
                self.log_step(f"Import validation failed: {e}", False)
                return False
            
            # Run health check
            health_monitor = os.path.join("deployment", "scripts", "production_health_monitor.py")
            if os.path.exists(health_monitor):
                result = subprocess.run([
                    sys.executable, health_monitor, "--single-check"
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    self.log_step("Health check passed")
                else:
                    self.log_step("Health check failed", False)
                    return False
            
            self.log_step("Post-deployment validation completed")
            return True
            
        except Exception as e:
            self.log_step(f"Post-deployment validation failed: {e}", False)
            return False
    
    def deploy(self) -> bool:
        """Execute full deployment pipeline"""
        
        print("🚀 NORTHSTAR V3 PRODUCTION DEPLOYMENT")
        print("=" * 50)
        print(f"Environment: {self.config['deployment']['environment']}")
        print(f"Timestamp: {datetime.now().isoformat()}")
        print()
        
        deployment_success = True
        
        # Pre-deployment checks
        if self.config["deployment"]["pre_deployment_checks"]:
            if not self.pre_deployment_checks():
                self.log_step("Pre-deployment checks failed - aborting deployment", False)
                return False
        
        # Create backup
        if self.config["deployment"]["backup_enabled"]:
            if not self.create_backup():
                self.log_step("Backup creation failed - aborting deployment", False)
                return False
        
        # Deploy application
        if not self.deploy_application():
            self.log_step("Application deployment failed", False)
            deployment_success = False
        
        # Post-deployment validation
        if self.config["deployment"]["post_deployment_validation"] and deployment_success:
            if not self.post_deployment_validation():
                self.log_step("Post-deployment validation failed", False)
                deployment_success = False
        
        # Generate deployment report
        self._generate_deployment_report(deployment_success)
        
        if deployment_success:
            self.log_step("🎉 DEPLOYMENT COMPLETED SUCCESSFULLY!")
        else:
            self.log_step("💥 DEPLOYMENT FAILED!", False)
        
        return deployment_success
    
    def _generate_deployment_report(self, success: bool):
        """Generate deployment report"""
        
        report = {
            "deployment_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "environment": self.config["deployment"]["environment"],
            "timestamp": datetime.now().isoformat(),
            "success": success,
            "steps": self.deployment_log,
            "summary": {
                "total_steps": len(self.deployment_log),
                "successful_steps": len([s for s in self.deployment_log if s["success"]]),
                "failed_steps": len([s for s in self.deployment_log if not s["success"]])
            }
        }
        
        report_file = f"deployment_report_{report['deployment_id']}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.log_step(f"Deployment report saved: {report_file}")

def main():
    """Deployment script main function"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Northstar V3 Production Deployment")
    parser.add_argument("--config", help="Deployment configuration file")
    parser.add_argument("--dry-run", action="store_true", help="Perform dry run without actual deployment")
    
    args = parser.parse_args()
    
    deployer = ProductionDeployer(args.config)
    
    if args.dry_run:
        print("🧪 DRY RUN MODE - No actual deployment will be performed")
        # Run only pre-deployment checks
        success = deployer.pre_deployment_checks()
        print(f"\nDry run result: {'✅ PASSED' if success else '❌ FAILED'}")
    else:
        success = deployer.deploy()
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
