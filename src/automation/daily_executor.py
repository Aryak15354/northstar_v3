#!/usr/bin/env python3
"""
🤖 NORTHSTAR DAILY EXECUTOR
Automated daily execution system for Northstar V3

This system runs every weekday at 6 AM and executes:
- Data ingestion and processing
- Signal generation and portfolio optimization
- Risk assessment and validation
- Clustering and wave analysis updates
- Report generation and dashboard updates
- System health monitoring

Usage:
    python src/automation/daily_executor.py
    
Schedule with cron:
    0 6 * * 1-5 /path/to/python /path/to/daily_executor.py
"""

import sys
import os
import logging
import json
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import traceback
import time

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(project_root / 'logs' / 'daily_execution.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class NorthstarDailyExecutor:
    """Automated daily execution system for Northstar"""
    
    def __init__(self):
        self.project_root = project_root
        self.execution_start = datetime.now()
        self.execution_log = []
        self.success_count = 0
        self.error_count = 0
        
        # Execution components
        self.components = {
            'data_ingestion': True,
            'signal_generation': True,
            'portfolio_optimization': True,
            'risk_assessment': True,
            'clustering_analysis': True,
            'wave_analysis': True,
            'validation': True,
            'reporting': True,
            'dashboard_update': True,
            'system_health': True
        }
        
        # Load configuration if exists
        self.load_configuration()
    
    def load_configuration(self):
        """Load execution configuration"""
        
        config_path = self.project_root / 'config' / 'automation_config.json'
        
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    self.components.update(config.get('components', {}))
                    logger.info("✅ Configuration loaded successfully")
            except Exception as e:
                logger.warning(f"⚠️ Could not load configuration: {e}")
        else:
            logger.info("📝 Using default configuration")
    
    def execute_daily_run(self):
        """Execute the complete daily run"""
        
        logger.info("🚀 Starting Northstar Daily Execution")
        logger.info(f"📅 Execution Date: {self.execution_start.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)
        
        try:
            # Execute each component
            if self.components.get('data_ingestion', True):
                self.execute_data_ingestion()
            
            if self.components.get('signal_generation', True):
                self.execute_signal_generation()
            
            if self.components.get('portfolio_optimization', True):
                self.execute_portfolio_optimization()
            
            if self.components.get('risk_assessment', True):
                self.execute_risk_assessment()
            
            if self.components.get('clustering_analysis', True):
                self.execute_clustering_analysis()
            
            if self.components.get('wave_analysis', True):
                self.execute_wave_analysis()
            
            if self.components.get('validation', True):
                self.execute_validation()
            
            if self.components.get('reporting', True):
                self.execute_reporting()
            
            if self.components.get('dashboard_update', True):
                self.execute_dashboard_update()
            
            if self.components.get('system_health', True):
                self.execute_system_health_check()
            
            # Generate execution summary
            self.generate_execution_summary()
            
            logger.info("🎉 Daily execution completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Daily execution failed: {e}")
            logger.error(traceback.format_exc())
            self.handle_execution_failure(e)
    
    def execute_data_ingestion(self):
        """Execute data ingestion component"""
        
        logger.info("📊 Executing Data Ingestion...")
        
        try:
            # Run data ingestion scripts
            scripts = [
                'ns_uso/scripts/run_v3_sentiment_cycle.py'
            ]
            
            for script in scripts:
                script_path = self.project_root / script
                if script_path.exists():
                    result = subprocess.run([sys.executable, str(script_path)], 
                                          capture_output=True, text=True, timeout=300)
                    
                    if result.returncode == 0:
                        logger.info(f"✅ {script} completed successfully")
                        self.success_count += 1
                    else:
                        logger.error(f"❌ {script} failed: {result.stderr}")
                        self.error_count += 1
                else:
                    logger.warning(f"⚠️ Script not found: {script}")
            
            self.log_component_result('data_ingestion', True, "Data ingestion completed")
            
        except Exception as e:
            logger.error(f"❌ Data ingestion failed: {e}")
            self.log_component_result('data_ingestion', False, str(e))
            self.error_count += 1
    
    def execute_signal_generation(self):
        """Execute signal generation component"""
        
        logger.info("🎯 Executing Signal Generation...")
        
        try:
            # Run signal generation
            script_path = self.project_root / 'scripts' / 'run_complete_northstar_system.py'
            
            if script_path.exists():
                result = subprocess.run([sys.executable, str(script_path), '--signals-only'], 
                                      capture_output=True, text=True, timeout=600)
                
                if result.returncode == 0:
                    logger.info("✅ Signal generation completed successfully")
                    self.success_count += 1
                    self.log_component_result('signal_generation', True, "Signal generation completed")
                else:
                    logger.error(f"❌ Signal generation failed: {result.stderr}")
                    self.error_count += 1
                    self.log_component_result('signal_generation', False, result.stderr)
            else:
                logger.warning("⚠️ Signal generation script not found")
                self.log_component_result('signal_generation', False, "Script not found")
            
        except Exception as e:
            logger.error(f"❌ Signal generation failed: {e}")
            self.log_component_result('signal_generation', False, str(e))
            self.error_count += 1
    
    def execute_portfolio_optimization(self):
        """Execute portfolio optimization component"""
        
        logger.info("⚖️ Executing Portfolio Optimization...")
        
        try:
            # Run portfolio optimization
            script_path = self.project_root / 'scripts' / 'run_complete_northstar_system.py'
            
            if script_path.exists():
                result = subprocess.run([sys.executable, str(script_path), '--portfolio-only'], 
                                      capture_output=True, text=True, timeout=600)
                
                if result.returncode == 0:
                    logger.info("✅ Portfolio optimization completed successfully")
                    self.success_count += 1
                    self.log_component_result('portfolio_optimization', True, "Portfolio optimization completed")
                else:
                    logger.error(f"❌ Portfolio optimization failed: {result.stderr}")
                    self.error_count += 1
                    self.log_component_result('portfolio_optimization', False, result.stderr)
            else:
                logger.warning("⚠️ Portfolio optimization script not found")
                self.log_component_result('portfolio_optimization', False, "Script not found")
            
        except Exception as e:
            logger.error(f"❌ Portfolio optimization failed: {e}")
            self.log_component_result('portfolio_optimization', False, str(e))
            self.error_count += 1
    
    def execute_risk_assessment(self):
        """Execute risk assessment component"""
        
        logger.info("🛡️ Executing Risk Assessment...")
        
        try:
            # Run risk assessment and stress tests
            scripts = [
                'scripts/run_crisis_validation.py',
                'scripts/simple_institutional_validation.py'
            ]
            
            for script in scripts:
                script_path = self.project_root / script
                if script_path.exists():
                    result = subprocess.run([sys.executable, str(script_path)], 
                                          capture_output=True, text=True, timeout=300)
                    
                    if result.returncode == 0:
                        logger.info(f"✅ {script} completed successfully")
                        self.success_count += 1
                    else:
                        logger.error(f"❌ {script} failed: {result.stderr}")
                        self.error_count += 1
            
            self.log_component_result('risk_assessment', True, "Risk assessment completed")
            
        except Exception as e:
            logger.error(f"❌ Risk assessment failed: {e}")
            self.log_component_result('risk_assessment', False, str(e))
            self.error_count += 1
    
    def execute_clustering_analysis(self):
        """Execute clustering analysis component"""
        
        logger.info("🔮 Executing Clustering Analysis...")
        
        try:
            # Update clustering data
            from src.dashboard.enhanced_v3_dashboard import EnhancedV3Dashboard
            
            dashboard = EnhancedV3Dashboard()
            
            # Generate new clustering data
            cluster_data = dashboard.generate_clustering_data(5)
            
            if cluster_data is not None:
                # Save clustering results
                results_path = self.project_root / 'data' / 'clustering'
                results_path.mkdir(exist_ok=True)
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                cluster_file = results_path / f'cluster_analysis_{timestamp}.json'
                
                # Convert numpy arrays to lists for JSON serialization
                cluster_results = {
                    'timestamp': timestamp,
                    'n_clusters': cluster_data['n_clusters'],
                    'cluster_labels': cluster_data['labels'].tolist(),
                    'cluster_centers': cluster_data['centers'].tolist()
                }
                
                with open(cluster_file, 'w') as f:
                    json.dump(cluster_results, f, indent=2)
                
                logger.info("✅ Clustering analysis completed successfully")
                self.success_count += 1
                self.log_component_result('clustering_analysis', True, f"Results saved to {cluster_file}")
            else:
                logger.warning("⚠️ Clustering analysis skipped (sklearn not available)")
                self.log_component_result('clustering_analysis', False, "sklearn not available")
            
        except Exception as e:
            logger.error(f"❌ Clustering analysis failed: {e}")
            self.log_component_result('clustering_analysis', False, str(e))
            self.error_count += 1
    
    def execute_wave_analysis(self):
        """Execute wave analysis component"""
        
        logger.info("🌊 Executing Wave Analysis...")
        
        try:
            # Update wave analysis data
            from src.dashboard.enhanced_v3_dashboard import EnhancedV3Dashboard
            
            dashboard = EnhancedV3Dashboard()
            
            # Generate new wave data
            wave_data = dashboard.generate_wave_data()
            
            # Save wave analysis results
            results_path = self.project_root / 'data' / 'waves'
            results_path.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            wave_file = results_path / f'wave_analysis_{timestamp}.json'
            
            wave_results = {
                'timestamp': timestamp,
                'signal': wave_data['signal'].tolist(),
                'primary_wave': wave_data['primary_wave'].tolist(),
                'secondary_wave': wave_data['secondary_wave'].tolist(),
                'tertiary_wave': wave_data['tertiary_wave'].tolist()
            }
            
            with open(wave_file, 'w') as f:
                json.dump(wave_results, f, indent=2)
            
            logger.info("✅ Wave analysis completed successfully")
            self.success_count += 1
            self.log_component_result('wave_analysis', True, f"Results saved to {wave_file}")
            
        except Exception as e:
            logger.error(f"❌ Wave analysis failed: {e}")
            self.log_component_result('wave_analysis', False, str(e))
            self.error_count += 1
    
    def execute_validation(self):
        """Execute validation component"""
        
        logger.info("✅ Executing Validation...")
        
        try:
            # Run validation scripts
            scripts = [
                'scripts/simple_walk_forward_validation.py',
                'scripts/run_alpha_validation.py'
            ]
            
            for script in scripts:
                script_path = self.project_root / script
                if script_path.exists():
                    result = subprocess.run([sys.executable, str(script_path)], 
                                          capture_output=True, text=True, timeout=300)
                    
                    if result.returncode == 0:
                        logger.info(f"✅ {script} completed successfully")
                        self.success_count += 1
                    else:
                        logger.error(f"❌ {script} failed: {result.stderr}")
                        self.error_count += 1
            
            self.log_component_result('validation', True, "Validation completed")
            
        except Exception as e:
            logger.error(f"❌ Validation failed: {e}")
            self.log_component_result('validation', False, str(e))
            self.error_count += 1
    
    def execute_reporting(self):
        """Execute reporting component"""
        
        logger.info("📊 Executing Reporting...")
        
        try:
            # Generate daily reports
            script_path = self.project_root / 'scripts' / 'generate_12month_performance_report.py'
            
            if script_path.exists():
                result = subprocess.run([sys.executable, str(script_path)], 
                                      capture_output=True, text=True, timeout=300)
                
                if result.returncode == 0:
                    logger.info("✅ Reporting completed successfully")
                    self.success_count += 1
                    self.log_component_result('reporting', True, "Reports generated")
                else:
                    logger.error(f"❌ Reporting failed: {result.stderr}")
                    self.error_count += 1
                    self.log_component_result('reporting', False, result.stderr)
            else:
                logger.warning("⚠️ Reporting script not found")
                self.log_component_result('reporting', False, "Script not found")
            
        except Exception as e:
            logger.error(f"❌ Reporting failed: {e}")
            self.log_component_result('reporting', False, str(e))
            self.error_count += 1
    
    def execute_dashboard_update(self):
        """Execute dashboard update component"""
        
        logger.info("📈 Executing Dashboard Update...")
        
        try:
            # Update dashboard data
            from src.dashboard.real_data_loader import RealDataLoader
            
            loader = RealDataLoader()
            real_data = loader.load_all_data()
            
            # Save updated data for dashboard
            dashboard_data_path = self.project_root / 'data' / 'dashboard'
            dashboard_data_path.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            data_file = dashboard_data_path / f'dashboard_data_{timestamp}.json'
            
            # Serialize data for dashboard
            dashboard_data = {
                'timestamp': timestamp,
                'performance_metrics': real_data.get('performance_metrics', {}),
                'risk_metrics': real_data.get('risk_metrics', {}),
                'last_update': datetime.now().isoformat()
            }
            
            with open(data_file, 'w') as f:
                json.dump(dashboard_data, f, indent=2, default=str)
            
            logger.info("✅ Dashboard update completed successfully")
            self.success_count += 1
            self.log_component_result('dashboard_update', True, f"Data updated: {data_file}")
            
        except Exception as e:
            logger.error(f"❌ Dashboard update failed: {e}")
            self.log_component_result('dashboard_update', False, str(e))
            self.error_count += 1
    
    def execute_system_health_check(self):
        """Execute system health check component"""
        
        logger.info("🏥 Executing System Health Check...")
        
        try:
            # Check system health
            health_status = {
                'timestamp': datetime.now().isoformat(),
                'execution_duration': (datetime.now() - self.execution_start).total_seconds(),
                'success_count': self.success_count,
                'error_count': self.error_count,
                'success_rate': self.success_count / (self.success_count + self.error_count) if (self.success_count + self.error_count) > 0 else 0,
                'components_status': self.execution_log
            }
            
            # Save health status
            health_path = self.project_root / 'data' / 'health'
            health_path.mkdir(exist_ok=True)
            
            health_file = health_path / f'system_health_{datetime.now().strftime("%Y%m%d")}.json'
            
            with open(health_file, 'w') as f:
                json.dump(health_status, f, indent=2)
            
            logger.info("✅ System health check completed successfully")
            self.success_count += 1
            self.log_component_result('system_health', True, f"Health status saved: {health_file}")
            
        except Exception as e:
            logger.error(f"❌ System health check failed: {e}")
            self.log_component_result('system_health', False, str(e))
            self.error_count += 1
    
    def log_component_result(self, component, success, message):
        """Log component execution result"""
        
        self.execution_log.append({
            'component': component,
            'success': success,
            'message': message,
            'timestamp': datetime.now().isoformat()
        })
    
    def generate_execution_summary(self):
        """Generate execution summary"""
        
        execution_duration = datetime.now() - self.execution_start
        
        summary = {
            'execution_date': self.execution_start.isoformat(),
            'execution_duration': execution_duration.total_seconds(),
            'total_components': len(self.execution_log),
            'successful_components': self.success_count,
            'failed_components': self.error_count,
            'success_rate': self.success_count / len(self.execution_log) if self.execution_log else 0,
            'components': self.execution_log
        }
        
        # Save summary
        summary_path = self.project_root / 'data' / 'execution_summaries'
        summary_path.mkdir(exist_ok=True)
        
        summary_file = summary_path / f'execution_summary_{self.execution_start.strftime("%Y%m%d_%H%M%S")}.json'
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        logger.info("📋 Execution Summary:")
        logger.info(f"   Duration: {execution_duration}")
        logger.info(f"   Success Rate: {summary['success_rate']:.1%}")
        logger.info(f"   Successful: {self.success_count}")
        logger.info(f"   Failed: {self.error_count}")
        logger.info(f"   Summary saved: {summary_file}")
    
    def handle_execution_failure(self, error):
        """Handle execution failure"""
        
        logger.error("🚨 EXECUTION FAILURE DETECTED")
        logger.error(f"Error: {error}")
        
        # Save failure report
        failure_report = {
            'timestamp': datetime.now().isoformat(),
            'error': str(error),
            'traceback': traceback.format_exc(),
            'execution_log': self.execution_log,
            'success_count': self.success_count,
            'error_count': self.error_count
        }
        
        failure_path = self.project_root / 'data' / 'failures'
        failure_path.mkdir(exist_ok=True)
        
        failure_file = failure_path / f'execution_failure_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        
        with open(failure_file, 'w') as f:
            json.dump(failure_report, f, indent=2)
        
        logger.error(f"Failure report saved: {failure_file}")

def main():
    """Main execution function"""
    
    executor = NorthstarDailyExecutor()
    executor.execute_daily_run()

if __name__ == "__main__":
    main()
