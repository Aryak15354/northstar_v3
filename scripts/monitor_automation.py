#!/usr/bin/env python3
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
            
            print(f"📅 Last Execution: {execution_date.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"⏱️  Duration: {latest['execution_duration']:.1f} seconds")
            print(f"✅ Success Rate: {latest['success_rate']:.1%}")
            print(f"📊 Components: {latest['successful_components']}/{latest['total_components']}")
            
            # Check if execution is recent (within 25 hours)
            if datetime.now() - execution_date < timedelta(hours=25):
                print("🟢 Status: HEALTHY")
            else:
                print("🟡 Status: STALE (execution overdue)")
            
            # Show component status
            print("\n📋 Component Status:")
            for component in latest['components']:
                status = "✅" if component['success'] else "❌"
                print(f"   {status} {component['component']}")
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
            
            print(f"\n🏥 System Health:")
            print(f"   Success Rate: {health['success_rate']:.1%}")
            print(f"   Avg Duration: {health['execution_duration']:.1f}s")

if __name__ == "__main__":
    check_automation_status()
