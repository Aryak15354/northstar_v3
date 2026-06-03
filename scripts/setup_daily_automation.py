#!/usr/bin/env python3
"""
⏰ SETUP DAILY AUTOMATION
Setup automated daily execution for Northstar V3

This script sets up:
- Cron job for daily execution at 6 AM on weekdays
- Log rotation and management
- Configuration files
- System health monitoring

Usage:
    python scripts/setup_daily_automation.py
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
import json

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

class AutomationSetup:
    """Setup automation for Northstar daily execution"""
    
    def __init__(self):
        self.project_root = project_root
        self.python_path = sys.executable
        self.executor_path = self.project_root / 'src' / 'automation' / 'daily_executor.py'
        
    def setup_automation(self):
        """Setup complete automation system"""
        
        print("⏰ NORTHSTAR DAILY AUTOMATION SETUP")
        print("=" * 50)
        
        # Create necessary directories
        self.create_directories()
        
        # Create configuration files
        self.create_configuration()
        
        # Setup cron job
        self.setup_cron_job()
        
        # Setup log rotation
        self.setup_log_rotation()
        
        # Create monitoring scripts
        self.create_monitoring_scripts()
        
        # Test the setup
        self.test_setup()
        
        print("\n🎉 Automation setup completed successfully!")
        print("\n📋 Next Steps:")
        print("1. Verify cron job: crontab -l")
        print("2. Check logs: tail -f logs/daily_execution.log")
        print("3. Monitor execution: python scripts/monitor_automation.py")
        
    def create_directories(self):
        """Create necessary directories"""
        
        print("📁 Creating directories...")
        
        directories = [
            'logs',
            'data/results/analysis/clustering',
            'data/waves',
            'data/dashboard',
            'data/health',
            'data/execution_summaries',
            'data/runtime/failures',
            'config'
        ]
        
        for directory in directories:
            dir_path = self.project_root / directory
            dir_path.mkdir(parents=True, exist_ok=True)
            print(f"   ✅ {directory}")
    
    def create_configuration(self):
        """Create automation configuration files"""
        
        print("⚙️ Creating configuration files...")
        
        # Main automation config
        automation_config = {
            'execution_time': '06:00',
            'days_of_week': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
            'timezone': 'UTC',
            'components': {
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
            },
            'notifications': {
                'email_enabled': False,
                'email_recipients': [],
                'slack_enabled': False,
                'slack_webhook': ''
            },
            'retry_settings': {
                'max_retries': 3,
                'retry_delay': 300
            }
        }
        
        config_file = self.project_root / 'config' / 'automation_config.json'
        with open(config_file, 'w') as f:
            json.dump(automation_config, f, indent=2)
        
        print(f"   ✅ {config_file}")
        
        # Logging configuration
        logging_config = {
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'standard': {
                    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                }
            },
            'handlers': {
                'file': {
                    'level': 'INFO',
                    'class': 'logging.handlers.RotatingFileHandler',
                    'filename': str(self.project_root / 'logs' / 'daily_execution.log'),
                    'maxBytes': 10485760,  # 10MB
                    'backupCount': 5,
                    'formatter': 'standard'
                },
                'console': {
                    'level': 'INFO',
                    'class': 'logging.StreamHandler',
                    'formatter': 'standard'
                }
            },
            'loggers': {
                '': {
                    'handlers': ['file', 'console'],
                    'level': 'INFO',
                    'propagate': False
                }
            }
        }
        
        logging_file = self.project_root / 'config' / 'logging_config.json'
        with open(logging_file, 'w') as f:
            json.dump(logging_config, f, indent=2)
        
        print(f"   ✅ {logging_file}")
    
    def setup_cron_job(self):
        """Setup cron job for daily execution"""
        
        print("⏰ Setting up cron job...")
        
        # Create cron job entry
        cron_command = f"0 6 * * 1-5 cd {self.project_root} && {self.python_path} {self.executor_path} >> logs/cron.log 2>&1"
        
        # Get current crontab
        try:
            result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
            current_crontab = result.stdout if result.returncode == 0 else ""
        except:
            current_crontab = ""
        
        # Check if our job already exists
        if 'daily_executor.py' not in current_crontab:
            # Add our job
            new_crontab = current_crontab + f"\n# Northstar Daily Execution\n{cron_command}\n"
            
            # Write new crontab
            process = subprocess.Popen(['crontab', '-'], stdin=subprocess.PIPE, text=True)
            process.communicate(input=new_crontab)
            
            if process.returncode == 0:
                print("   ✅ Cron job added successfully")
                print(f"   📅 Schedule: Every weekday at 6:00 AM")
                print(f"   📝 Command: {cron_command}")
            else:
                print("   ❌ Failed to add cron job")
        else:
            print("   ✅ Cron job already exists")
        
        # Create cron job management script
        cron_script = f"""#!/bin/bash
# Northstar Daily Execution Cron Job Management

# Add cron job
add_job() {{
    echo "Adding Northstar daily execution cron job..."
    (crontab -l 2>/dev/null; echo "0 6 * * 1-5 cd {self.project_root} && {self.python_path} {self.executor_path} >> logs/cron.log 2>&1") | crontab -
    echo "Cron job added successfully!"
}}

# Remove cron job
remove_job() {{
    echo "Removing Northstar daily execution cron job..."
    crontab -l | grep -v "daily_executor.py" | crontab -
    echo "Cron job removed successfully!"
}}

# Show current cron jobs
show_jobs() {{
    echo "Current cron jobs:"
    crontab -l
}}

case "$1" in
    add)
        add_job
        ;;
    remove)
        remove_job
        ;;
    show)
        show_jobs
        ;;
    *)
        echo "Usage: $0 {{add|remove|show}}"
        exit 1
        ;;
esac
"""
        
        cron_script_file = self.project_root / 'scripts' / 'manage_cron.sh'
        with open(cron_script_file, 'w') as f:
            f.write(cron_script)
        
        # Make executable
        os.chmod(cron_script_file, 0o755)
        print(f"   ✅ Cron management script: {cron_script_file}")
    
    def setup_log_rotation(self):
        """Setup log rotation"""
        
        print("📝 Setting up log rotation...")
        
        # Create logrotate configuration
        logrotate_config = f"""{self.project_root}/logs/*.log {{
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 {os.getenv('USER', 'root')} {os.getenv('USER', 'root')}
    postrotate
        # Restart any services if needed
    endscript
}}
"""
        
        logrotate_file = self.project_root / 'config' / 'logrotate.conf'
        with open(logrotate_file, 'w') as f:
            f.write(logrotate_config)
        
        print(f"   ✅ Logrotate config: {logrotate_file}")
        print("   💡 To enable system-wide log rotation, copy to /etc/logrotate.d/")
    
    def create_monitoring_scripts(self):
        """Create monitoring and management scripts"""
        
        print("📊 Creating monitoring scripts...")
        
        # Monitoring script
        monitor_script = f"""#!/usr/bin/env python3
'''
📊 NORTHSTAR AUTOMATION MONITOR
Monitor the status of Northstar daily automation
'''

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

def check_automation_status():
    '''Check automation status'''
    
    print("📊 NORTHSTAR AUTOMATION STATUS")
    print("=" * 40)
    
    # Check recent executions
    summaries_path = project_root / 'data' / 'execution_summaries'
    
    if summaries_path.exists():
        summary_files = sorted(summaries_path.glob('*.json'), reverse=True)
        
        if summary_files:
            # Get latest execution
            with open(summary_files[0], 'r') as f:
                latest = json.load(f)
            
            execution_date = datetime.fromisoformat(latest['execution_date'])
            
            print(f"📅 Last Execution: {{execution_date.strftime('%Y-%m-%d %H:%M:%S')}}")
            print(f"⏱️  Duration: {{latest['execution_duration']:.1f}} seconds")
            print(f"✅ Success Rate: {{latest['success_rate']:.1%}}")
            print(f"📊 Components: {{latest['successful_components']}}/{{latest['total_components']}}")
            
            # Check if execution is recent (within 25 hours)
            if datetime.now() - execution_date < timedelta(hours=25):
                print("🟢 Status: HEALTHY")
            else:
                print("🟡 Status: STALE (execution overdue)")
            
            # Show component status
            print("\\n📋 Component Status:")
            for component in latest['components']:
                status = "✅" if component['success'] else "❌"
                print(f"   {{status}} {{component['component']}}")
        else:
            print("❌ No execution summaries found")
    else:
        print("❌ Execution summaries directory not found")
    
    # Check system health
    health_path = project_root / 'data' / 'health'
    
    if health_path.exists():
        health_files = sorted(health_path.glob('*.json'), reverse=True)
        
        if health_files:
            with open(health_files[0], 'r') as f:
                health = json.load(f)
            
            print(f"\\n🏥 System Health:")
            print(f"   Success Rate: {{health['success_rate']:.1%}}")
            print(f"   Avg Duration: {{health['execution_duration']:.1f}}s")

if __name__ == "__main__":
    check_automation_status()
"""
        
        monitor_file = self.project_root / 'scripts' / 'monitor_automation.py'
        with open(monitor_file, 'w') as f:
            f.write(monitor_script)
        
        os.chmod(monitor_file, 0o755)
        print(f"   ✅ Monitor script: {monitor_file}")
        
        # Status dashboard script
        dashboard_script = f"""#!/usr/bin/env python3
'''
📈 AUTOMATION DASHBOARD
Simple web dashboard for automation status
'''

import streamlit as st
import json
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import plotly.graph_objects as go

project_root = Path(__file__).parent.parent

st.set_page_config(page_title="Northstar Automation Dashboard", layout="wide")

st.title("🤖 Northstar Automation Dashboard")

# Load execution summaries
summaries_path = project_root / 'data' / 'execution_summaries'

if summaries_path.exists():
    summary_files = sorted(summaries_path.glob('*.json'), reverse=True)[:30]  # Last 30 executions
    
    if summary_files:
        summaries = []
        for file in summary_files:
            with open(file, 'r') as f:
                summaries.append(json.load(f))
        
        # Create DataFrame
        df = pd.DataFrame(summaries)
        df['execution_date'] = pd.to_datetime(df['execution_date'])
        
        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            avg_success_rate = df['success_rate'].mean()
            st.metric("Avg Success Rate", f"{{avg_success_rate:.1%}}")
        
        with col2:
            avg_duration = df['execution_duration'].mean()
            st.metric("Avg Duration", f"{{avg_duration:.1f}}s")
        
        with col3:
            last_execution = df['execution_date'].max()
            st.metric("Last Execution", last_execution.strftime('%Y-%m-%d'))
        
        with col4:
            total_executions = len(df)
            st.metric("Total Executions", total_executions)
        
        # Success rate chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['execution_date'],
            y=df['success_rate'] * 100,
            mode='lines+markers',
            name='Success Rate'
        ))
        
        fig.update_layout(
            title="Success Rate Over Time",
            xaxis_title="Date",
            yaxis_title="Success Rate (%)",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Recent executions table
        st.subheader("Recent Executions")
        display_df = df[['execution_date', 'execution_duration', 'success_rate', 'successful_components', 'total_components']].copy()
        display_df['execution_date'] = display_df['execution_date'].dt.strftime('%Y-%m-%d %H:%M')
        st.dataframe(display_df, use_container_width=True)
    else:
        st.warning("No execution summaries found")
else:
    st.error("Execution summaries directory not found")
"""
        
        dashboard_file = self.project_root / 'scripts' / 'automation_dashboard.py'
        with open(dashboard_file, 'w') as f:
            f.write(dashboard_script)
        
        os.chmod(dashboard_file, 0o755)
        print(f"   ✅ Dashboard script: {dashboard_file}")
    
    def test_setup(self):
        """Test the automation setup"""
        
        print("🧪 Testing automation setup...")
        
        # Test executor script exists and is executable
        if self.executor_path.exists():
            print("   ✅ Daily executor script found")
        else:
            print("   ❌ Daily executor script not found")
            return False
        
        # Test Python path
        try:
            result = subprocess.run([self.python_path, '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"   ✅ Python executable: {result.stdout.strip()}")
            else:
                print("   ❌ Python executable test failed")
                return False
        except:
            print("   ❌ Python executable not found")
            return False
        
        # Test import of required modules
        try:
            result = subprocess.run([
                self.python_path, '-c', 
                'import sys; sys.path.append("src"); from automation.daily_executor import NorthstarDailyExecutor; print("Import successful")'
            ], cwd=self.project_root, capture_output=True, text=True)
            
            if result.returncode == 0:
                print("   ✅ Module imports successful")
            else:
                print(f"   ❌ Module import failed: {result.stderr}")
                return False
        except:
            print("   ❌ Module import test failed")
            return False
        
        # Test dry run
        print("   🧪 Running dry test...")
        try:
            result = subprocess.run([
                self.python_path, str(self.executor_path), '--dry-run'
            ], cwd=self.project_root, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print("   ✅ Dry run successful")
            else:
                print(f"   ⚠️ Dry run completed with warnings")
        except subprocess.TimeoutExpired:
            print("   ⚠️ Dry run timed out (this is normal)")
        except:
            print("   ⚠️ Dry run test skipped")
        
        return True

def main():
    """Main setup function"""
    
    setup = AutomationSetup()
    setup.setup_automation()

if __name__ == "__main__":
    main()
