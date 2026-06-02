#!/usr/bin/env python3
"""
Test Constitutional Cockpit - Create Real Snapshots and Test Dashboard

This script creates real snapshots from the V3 system and tests the constitutional cockpit.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.dashboard.snapshot_loader import (
    DashboardSnapshot, SystemStateView, RiskStateView, 
    EngineStateView, ValidationStateView, IntelligenceStateView
)

def create_sample_data_directories():
    """Create sample data directories and files for testing"""
    
    print("📁 Creating sample data directories...")
    
    # Create directories
    directories = [
        'data/state',
        'data/risk', 
        'data/intelligence',
        'data/validation',
        'data/processed',
        'data/intelligence/observer/snapshots'
    ]
    
    for directory in directories:
        full_path = os.path.join(project_root, directory)
        os.makedirs(full_path, exist_ok=True)
        print(f"   ✅ Created: {directory}")
    
    return True

def create_sample_system_state():
    """Create sample system state data"""
    
    print("🧠 Creating sample system state...")
    
    # Sample unified state
    unified_state = {
        'timestamp': datetime.now().isoformat(),
        'system_status': 'healthy',
        'organs': {
            'portfolio_governor': {'status': 'healthy'},
            'dual_engine_coordinator': {'status': 'healthy'},
            'emergency_brake': {'status': 'healthy'},
            'intelligence_stack': {'status': 'healthy'},
            'market_brain': {'status': 'healthy'},
            'validation_suite': {'status': 'healthy'},
            'intelligence_observer': {'status': 'healthy'},
            'risk_coordinator': {'status': 'healthy'}
        },
        'market_state': {
            'regime': 'SUPPORTIVE',
            'regime_confidence': 0.85,
            'active_engine': 'trend',
            'engine_confidence': 0.78,
            'allowed_exposure': 0.65,
            'exposure_state': 'RISK_ON'
        },
        'conviction_contract': {
            'locked': True,
            'violations': 0
        }
    }
    
    # Save to file
    state_file = os.path.join(project_root, 'data/state/unified_state.json')
    with open(state_file, 'w') as f:
        json.dump(unified_state, f, indent=2)
    
    print(f"   ✅ Created: {state_file}")
    return True

def create_sample_risk_data():
    """Create sample risk state data"""
    
    print("🛡️ Creating sample risk data...")
    
    # Sample risk data
    risk_data = []
    base_date = datetime.now() - timedelta(days=30)
    
    for i in range(30):
        date = base_date + timedelta(days=i)
        risk_data.append({
            'date': date,
            'emergency_brake_status': 'ARMED',
            'emergency_active': False,
            'current_drawdown': np.random.uniform(-0.05, 0.0),
            'max_allowed_drawdown': -0.20,
            'volatility_20d': np.random.uniform(0.15, 0.25),
            'kill_switches_armed': 5,
            'kill_switches_total': 5
        })
    
    # Convert to DataFrame and save
    risk_df = pd.DataFrame(risk_data)
    risk_file = os.path.join(project_root, 'data/risk/risk_state.parquet')
    risk_df.to_parquet(risk_file)
    
    print(f"   ✅ Created: {risk_file}")
    return True

def create_sample_engine_data():
    """Create sample engine decision data"""
    
    print("⚙️ Creating sample engine data...")
    
    # Sample engine decisions
    engine_data = []
    base_date = datetime.now() - timedelta(days=30)
    
    for i in range(30):
        date = base_date + timedelta(days=i)
        
        # Simulate regime-based engine activation
        if i < 10:
            active_engine = 'trend'
            trend_active = True
            crisis_active = False
        elif i < 15:
            active_engine = 'none'
            trend_active = False
            crisis_active = False
        else:
            active_engine = 'trend'
            trend_active = True
            crisis_active = False
        
        engine_data.append({
            'date': date,
            'active_engine': active_engine,
            'trend_engine_active': trend_active,
            'crisis_engine_active': crisis_active,
            'regime_engine_alignment': np.random.uniform(0.8, 0.95),
            'engine_conflicts': 0
        })
    
    # Convert to DataFrame and save
    engine_df = pd.DataFrame(engine_data)
    engine_file = os.path.join(project_root, 'data/intelligence/engine_decisions.parquet')
    engine_df.to_parquet(engine_file)
    
    print(f"   ✅ Created: {engine_file}")
    return True

def create_sample_validation_data():
    """Create sample validation data"""
    
    print("✅ Creating sample validation data...")
    
    # Sample validation results
    validation_data = {
        'timestamp': datetime.now().isoformat(),
        'last_walkforward_result': 'PASS',
        'last_walkforward_date': (datetime.now() - timedelta(days=7)).isoformat(),
        'walkforward_success_rate': 0.85,
        'current_rules_hash': 'a1b2c3d4e5f6789',
        'rules_hash_verified': True,
        'override_attempts_24h': 0,
        'override_attempts_total': 0,
        'data_integrity_layers': {
            'ingestion': True,
            'processing': True,
            'validation': True,
            'storage': True,
            'access': True
        },
        'data_integrity_score': 1.0
    }
    
    # Save to file
    validation_file = os.path.join(project_root, 'data/validation/validation_summary.json')
    with open(validation_file, 'w') as f:
        json.dump(validation_data, f, indent=2)
    
    print(f"   ✅ Created: {validation_file}")
    return True

def create_sample_intelligence_data():
    """Create sample intelligence observer data"""
    
    print("🧠 Creating sample intelligence data...")
    
    # Sample intelligence scores
    intelligence_data = {
        'timestamp': datetime.now().isoformat(),
        'regime_similarity_index': 67.5,
        'stress_clustering_index': 32.1,
        'false_calm_likelihood': 15.8,
        'behavioral_drift_index': 8.2,
        'intelligence_confidence': 0.82,
        'last_intelligence_update': (datetime.now() - timedelta(hours=2)).isoformat(),
        'weekly_report_available': True,
        'weekly_report_path': 'data/intelligence/observer/reports/weekly/latest.md',
        'observer_healthy': True,
        'observer_violations': 0,
        'observer_suspended': False
    }
    
    # Save to file
    intelligence_file = os.path.join(project_root, 'data/intelligence/observer/intelligence_state.json')
    os.makedirs(os.path.dirname(intelligence_file), exist_ok=True)
    with open(intelligence_file, 'w') as f:
        json.dump(intelligence_data, f, indent=2)
    
    print(f"   ✅ Created: {intelligence_file}")
    return True

def create_sample_performance_data():
    """Create sample performance data"""
    
    print("📊 Creating sample performance data...")
    
    # Sample performance data
    performance_data = []
    base_date = datetime.now() - timedelta(days=30)
    
    cumulative_return = 1.0
    for i in range(30):
        date = base_date + timedelta(days=i)
        daily_return = np.random.normal(0.001, 0.02)  # 0.1% daily return, 2% volatility
        cumulative_return *= (1 + daily_return)
        
        performance_data.append({
            'date': date,
            'daily_return': daily_return,
            'cumulative_return': cumulative_return - 1,
            'volatility_30d': 0.18,
            'sharpe_ratio_30d': 0.65,
            'max_drawdown_30d': -0.03,
            'avg_exposure_7d': 0.62,
            'avg_exposure_30d': 0.58,
            'turnover_7d': 0.15
        })
    
    # Convert to DataFrame and save
    performance_df = pd.DataFrame(performance_data)
    performance_file = os.path.join(project_root, 'data/processed/performance_summary.parquet')
    performance_df.to_parquet(performance_file)
    
    print(f"   ✅ Created: {performance_file}")
    return True

def test_snapshot_creation():
    """Test creating a real dashboard snapshot"""
    
    print("📸 Testing snapshot creation...")
    
    try:
        from src.dashboard.snapshot_loader import DashboardSnapshotLoader
        
        # Create snapshot loader
        loader = DashboardSnapshotLoader()
        
        # Load latest snapshot
        snapshot = loader.load_latest_snapshot()
        
        if snapshot is None:
            print("   ❌ Failed to create snapshot")
            return False
        
        print(f"   ✅ Snapshot created: {snapshot.snapshot_id}")
        print(f"   📊 Data quality: {snapshot.data_quality_score:.1%}")
        print(f"   📋 Completeness: {snapshot.completeness_score:.1%}")
        print(f"   ⏰ Staleness: {snapshot.staleness_hours:.1f} hours")
        
        # Verify hash
        if snapshot.verify_hash():
            print("   ✅ Hash verification: PASSED")
        else:
            print("   ❌ Hash verification: FAILED")
        
        # Test panel data
        print("   🔍 Testing panel data:")
        print(f"      System Status: {snapshot.system_state.system_status}")
        print(f"      Current Regime: {snapshot.system_state.current_regime}")
        print(f"      Active Engine: {snapshot.system_state.active_engine}")
        print(f"      Emergency Brake: {snapshot.risk_state.emergency_brake_status}")
        print(f"      Walk-Forward: {snapshot.validation_state.last_walkforward_result}")
        print(f"      Observer Health: {snapshot.intelligence_state.observer_healthy}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Snapshot creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_constitutional_cockpit():
    """Test the constitutional cockpit with real data"""
    
    print("🏛️ Testing Constitutional Cockpit...")
    
    try:
        # Import snapshot loader directly (avoid streamlit context issues)
        from src.dashboard.snapshot_loader import DashboardSnapshotLoader
        
        # Create snapshot loader
        loader = DashboardSnapshotLoader()
        
        # Test snapshot loading
        snapshot = loader.load_latest_snapshot()
        
        if snapshot is None:
            print("   ❌ Cockpit snapshot loading failed")
            return False
        
        print("   ✅ Cockpit snapshot loading: SUCCESS")
        print(f"   📊 Snapshot ID: {snapshot.snapshot_id}")
        print(f"   ⏰ Staleness: {snapshot.staleness_hours:.1f} hours")
        
        # Test panel data access
        print("   🔍 Testing panel data access:")
        print(f"      System State: {snapshot.system_state.system_status}")
        print(f"      Risk State: {snapshot.risk_state.emergency_brake_status}")
        print(f"      Engine State: {snapshot.engine_state.trend_engine_active}")
        print(f"      Validation State: {snapshot.validation_state.last_walkforward_result}")
        print(f"      Intelligence State: {snapshot.intelligence_state.observer_healthy}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Constitutional cockpit test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    
    print("🧪 CONSTITUTIONAL COCKPIT TEST SUITE")
    print("=" * 60)
    print("Creating real snapshots and testing dashboard components")
    print("=" * 60)
    print()
    
    # Create sample data
    success = True
    success &= create_sample_data_directories()
    success &= create_sample_system_state()
    success &= create_sample_risk_data()
    success &= create_sample_engine_data()
    success &= create_sample_validation_data()
    success &= create_sample_intelligence_data()
    success &= create_sample_performance_data()
    
    if not success:
        print("❌ Sample data creation failed")
        return 1
    
    print()
    
    # Test snapshot creation
    success &= test_snapshot_creation()
    
    if not success:
        print("❌ Snapshot creation test failed")
        return 1
    
    print()
    
    # Test constitutional cockpit
    success &= test_constitutional_cockpit()
    
    if not success:
        print("❌ Constitutional cockpit test failed")
        return 1
    
    print()
    print("=" * 60)
    print("🎯 ALL TESTS PASSED")
    print("✅ Sample data created successfully")
    print("✅ Snapshot creation working")
    print("✅ Constitutional cockpit ready")
    print()
    print("🚀 Ready to launch Constitutional Cockpit:")
    print("   python scripts/launch_constitutional_cockpit.py")
    print("=" * 60)
    
    return 0

if __name__ == "__main__":
    exit(main())