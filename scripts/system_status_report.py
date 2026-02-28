#!/usr/bin/env python3
"""
📊 SYSTEM STATUS REPORT - NORTHSTAR V3
Comprehensive System Health and Operational Status Report

This script provides a complete overview of system health after recovery
"""

import os
import sys
import json
import pandas as pd
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def check_component_status():
    """Check status of all critical components"""
    
    print("🔍 NORTHSTAR V3 - SYSTEM STATUS REPORT")
    print("=" * 60)
    print(f"Report generated: {datetime.now()}")
    print()
    
    components = {}
    
    # 1. Data Pipeline Status
    print("📊 DATA PIPELINE STATUS")
    print("-" * 30)
    
    market_data_file = 'data/options/live/market_data_latest.json'
    market_state_file = 'data/processed/market_state.parquet'
    
    if os.path.exists(market_data_file):
        age_hours = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(market_data_file))).total_seconds() / 3600
        print(f"✅ Market Data: Fresh ({age_hours:.1f} hours old)")
        components['market_data'] = 'operational'
    else:
        print("❌ Market Data: Missing")
        components['market_data'] = 'failed'
    
    if os.path.exists(market_state_file):
        df = pd.read_parquet(market_state_file)
        print(f"✅ Market State: Available ({len(df)} records)")
        components['market_state'] = 'operational'
    else:
        print("❌ Market State: Missing")
        components['market_state'] = 'failed'
    
    # 2. Intelligence Stack Status
    print("\n🧠 INTELLIGENCE STACK STATUS")
    print("-" * 30)
    
    intelligence_file = 'data/intelligence/intelligence_state.json'
    if os.path.exists(intelligence_file):
        with open(intelligence_file, 'r') as f:
            intel_data = json.load(f)
        print(f"✅ Intelligence State: Available")
        print(f"   Regime: {intel_data.get('regime', 'unknown')}")
        print(f"   Beliefs: {len(intel_data.get('beliefs', {}))}")
        components['intelligence'] = 'operational'
    else:
        print("❌ Intelligence State: Missing")
        components['intelligence'] = 'failed'
    
    # Test intelligence stack import
    try:
        from src.intelligence.intelligence_stack import IntelligenceStack
        print("✅ Intelligence Stack: Importable")
        components['intelligence_stack'] = 'operational'
    except Exception as e:
        print(f"❌ Intelligence Stack: Import failed - {str(e)}")
        components['intelligence_stack'] = 'failed'
    
    # 3. Capital Allocation Status
    print("\n💰 CAPITAL ALLOCATION STATUS")
    print("-" * 30)
    
    allocation_file = 'data/processed/capital_allocations.json'
    if os.path.exists(allocation_file):
        with open(allocation_file, 'r') as f:
            alloc_data = json.load(f)
        allocations = alloc_data.get('allocations', {})
        total_exposure = alloc_data.get('total_exposure', 0)
        print(f"✅ Capital Allocations: Available")
        print(f"   Strategies: {len(allocations)}")
        print(f"   Total Exposure: {total_exposure:.1%}")
        components['capital_allocation'] = 'operational'
    else:
        print("❌ Capital Allocations: Missing")
        components['capital_allocation'] = 'failed'
    
    # Test capital allocator import
    try:
        from src.intelligence.capital_allocator import CapitalAllocator
        print("✅ Capital Allocator: Importable")
        components['capital_allocator'] = 'operational'
    except Exception as e:
        print(f"❌ Capital Allocator: Import failed - {str(e)}")
        components['capital_allocator'] = 'failed'
    
    # 4. Portfolio Management Status
    print("\n🎯 PORTFOLIO MANAGEMENT STATUS")
    print("-" * 30)
    
    portfolio_file = 'data/processed/portfolio_weights.parquet'
    analytics_file = 'data/processed/portfolio_analytics.json'
    
    if os.path.exists(portfolio_file):
        df = pd.read_parquet(portfolio_file)
        total_exposure = df['final_weight'].sum() if 'final_weight' in df.columns else 0
        print(f"✅ Portfolio Weights: Available")
        print(f"   Positions: {len(df)}")
        print(f"   Total Exposure: {total_exposure:.1%}")
        components['portfolio_weights'] = 'operational'
    else:
        print("❌ Portfolio Weights: Missing")
        components['portfolio_weights'] = 'failed'
    
    if os.path.exists(analytics_file):
        with open(analytics_file, 'r') as f:
            analytics = json.load(f)
        print(f"✅ Portfolio Analytics: Available")
        components['portfolio_analytics'] = 'operational'
    else:
        print("❌ Portfolio Analytics: Missing")
        components['portfolio_analytics'] = 'failed'
    
    # Test portfolio governor import
    try:
        from src.portfolio.portfolio_governor import PortfolioGovernor
        print("✅ Portfolio Governor: Importable")
        components['portfolio_governor'] = 'operational'
    except Exception as e:
        print(f"❌ Portfolio Governor: Import failed - {str(e)}")
        components['portfolio_governor'] = 'failed'
    
    # 5. System Orchestration Status
    print("\n🎭 SYSTEM ORCHESTRATION STATUS")
    print("-" * 30)
    
    try:
        from src.core.orchestrator import OrganOrchestrator
        from src.core.state import UnifiedState
        from src.core.clock import MarketClock
        from src.core.events import EventBus
        
        state = UnifiedState()
        clock = MarketClock()
        event_bus = EventBus()
        orchestrator = OrganOrchestrator(state, clock, event_bus)
        
        status = orchestrator.get_orchestrator_status()
        print("✅ Orchestrator: Operational")
        print(f"   Registered Organs: {status['registered_organs']}")
        print(f"   System Health: {status['system_health']['overall_score']:.1%}")
        components['orchestrator'] = 'operational'
        
    except Exception as e:
        print(f"❌ Orchestrator: Failed - {str(e)}")
        components['orchestrator'] = 'failed'
    
    # 6. Emergency Protocols Status
    print("\n🚨 EMERGENCY PROTOCOLS STATUS")
    print("-" * 30)
    
    emergency_file = 'data/state/emergency_config.json'
    if os.path.exists(emergency_file):
        with open(emergency_file, 'r') as f:
            emergency_config = json.load(f)
        print("✅ Emergency Protocols: Configured")
        print(f"   Emergency Mode: {emergency_config.get('emergency_mode', False)}")
        print(f"   Max Exposure: {emergency_config.get('max_exposure', 0):.1%}")
        components['emergency_protocols'] = 'operational'
    else:
        print("❌ Emergency Protocols: Not configured")
        components['emergency_protocols'] = 'failed'
    
    return components

def generate_system_summary(components):
    """Generate overall system summary"""
    
    print("\n📊 SYSTEM HEALTH SUMMARY")
    print("=" * 60)
    
    total_components = len(components)
    operational_components = len([c for c in components.values() if c == 'operational'])
    failed_components = len([c for c in components.values() if c == 'failed'])
    
    system_health = operational_components / total_components * 100
    
    print(f"Total Components: {total_components}")
    print(f"Operational: {operational_components}")
    print(f"Failed: {failed_components}")
    print(f"System Health: {system_health:.1f}%")
    
    # Determine system status
    if system_health >= 90:
        status = "🟢 FULLY OPERATIONAL"
        description = "All critical systems are functioning normally"
    elif system_health >= 75:
        status = "🟡 MOSTLY OPERATIONAL"
        description = "Most systems operational, minor issues present"
    elif system_health >= 50:
        status = "🟠 PARTIALLY OPERATIONAL"
        description = "Core systems working, some components degraded"
    else:
        status = "🔴 CRITICAL ISSUES"
        description = "Multiple system failures, immediate attention required"
    
    print(f"\nSystem Status: {status}")
    print(f"Description: {description}")
    
    # List failed components
    if failed_components > 0:
        print(f"\n❌ FAILED COMPONENTS:")
        for component, status in components.items():
            if status == 'failed':
                print(f"   • {component}")
    
    # List operational components
    print(f"\n✅ OPERATIONAL COMPONENTS:")
    for component, status in components.items():
        if status == 'operational':
            print(f"   • {component}")
    
    return system_health, status

def check_recent_activity():
    """Check recent system activity"""
    
    print("\n📈 RECENT SYSTEM ACTIVITY")
    print("-" * 30)
    
    # Check recent files
    recent_files = []
    
    data_dirs = ['data/processed', 'data/intelligence', 'data/reports']
    for data_dir in data_dirs:
        if os.path.exists(data_dir):
            for file in os.listdir(data_dir):
                file_path = os.path.join(data_dir, file)
                if os.path.isfile(file_path):
                    mtime = os.path.getmtime(file_path)
                    age_hours = (datetime.now().timestamp() - mtime) / 3600
                    if age_hours < 24:  # Files modified in last 24 hours
                        recent_files.append({
                            'file': file,
                            'path': data_dir,
                            'age_hours': age_hours
                        })
    
    recent_files.sort(key=lambda x: x['age_hours'])
    
    print(f"Recent Activity (last 24 hours): {len(recent_files)} files")
    for file_info in recent_files[:10]:  # Show top 10 most recent
        print(f"   • {file_info['file']} ({file_info['age_hours']:.1f}h ago)")
    
    return recent_files

def generate_recommendations(components, system_health):
    """Generate operational recommendations"""
    
    print("\n💡 OPERATIONAL RECOMMENDATIONS")
    print("-" * 30)
    
    recommendations = []
    
    # Critical component failures
    failed_components = [comp for comp, status in components.items() if status == 'failed']
    if failed_components:
        recommendations.append({
            'priority': 'HIGH',
            'category': 'Component Failure',
            'message': f'Repair failed components: {", ".join(failed_components)}',
            'action': 'Run diagnostic scripts and check logs'
        })
    
    # System health recommendations
    if system_health < 75:
        recommendations.append({
            'priority': 'HIGH',
            'category': 'System Health',
            'message': f'System health is {system_health:.1f}% - below optimal',
            'action': 'Run critical system recovery script'
        })
    
    # Data freshness
    market_data_file = 'data/options/live/market_data_latest.json'
    if os.path.exists(market_data_file):
        age_hours = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(market_data_file))).total_seconds() / 3600
        if age_hours > 6:
            recommendations.append({
                'priority': 'MEDIUM',
                'category': 'Data Freshness',
                'message': f'Market data is {age_hours:.1f} hours old',
                'action': 'Update market data pipeline'
            })
    
    # Portfolio exposure check
    portfolio_file = 'data/processed/portfolio_weights.parquet'
    if os.path.exists(portfolio_file):
        df = pd.read_parquet(portfolio_file)
        if 'final_weight' in df.columns:
            total_exposure = df['final_weight'].sum()
            if total_exposure < 0.3:
                recommendations.append({
                    'priority': 'MEDIUM',
                    'category': 'Portfolio Exposure',
                    'message': f'Portfolio exposure is low: {total_exposure:.1%}',
                    'action': 'Review risk management settings'
                })
    
    # Emergency mode check
    emergency_file = 'data/state/emergency_config.json'
    if os.path.exists(emergency_file):
        with open(emergency_file, 'r') as f:
            emergency_config = json.load(f)
        if emergency_config.get('emergency_mode', False):
            recommendations.append({
                'priority': 'HIGH',
                'category': 'Emergency Mode',
                'message': 'System is in emergency mode',
                'action': 'Validate system stability and disable emergency mode'
            })
    
    # Display recommendations
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            priority_icon = {'HIGH': '🔴', 'MEDIUM': '🟡', 'LOW': '🟢'}.get(rec['priority'], '📋')
            print(f"{priority_icon} {rec['priority']} - {rec['category']}")
            print(f"   Issue: {rec['message']}")
            print(f"   Action: {rec['action']}")
            print()
    else:
        print("✅ No immediate recommendations - system is operating well")
    
    return recommendations

def main():
    """Main status report execution"""
    
    # Check component status
    components = check_component_status()
    
    # Generate system summary
    system_health, status = generate_system_summary(components)
    
    # Check recent activity
    recent_files = check_recent_activity()
    
    # Generate recommendations
    recommendations = generate_recommendations(components, system_health)
    
    # Save status report
    status_report = {
        'timestamp': datetime.now().isoformat(),
        'system_health': system_health,
        'system_status': status,
        'components': components,
        'recent_activity': len(recent_files),
        'recommendations': recommendations
    }
    
    os.makedirs('data/reports', exist_ok=True)
    report_file = f'data/reports/system_status_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    
    with open(report_file, 'w') as f:
        json.dump(status_report, f, indent=2, default=str)
    
    print(f"\n📊 Status report saved: {report_file}")
    
    # Final summary
    print(f"\n🎯 SYSTEM STATUS REPORT COMPLETE")
    print("=" * 60)
    print(f"System Health: {system_health:.1f}%")
    print(f"Status: {status}")
    print(f"Recommendations: {len(recommendations)}")
    
    return system_health >= 75

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)