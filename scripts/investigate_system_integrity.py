#!/usr/bin/env python3
"""
🔍 SYSTEM INTEGRITY INVESTIGATION - NORTHSTAR V3
Investigating Critical System Issues

This script investigates:
1. Why max drawdown is always zero everywhere
2. Regime transition from Expansion_Liquidity_Driven to Neutral_Consolidation
3. Data calculation integrity across the system
4. Verification of anticipatory intelligence behavior

This ensures the system is working correctly and not just showing fake numbers.
"""

import sys
import os
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def investigate_max_drawdown_issue():
    """Investigate why max drawdown is always zero"""
    
    print("🔍 INVESTIGATING MAX DRAWDOWN ISSUE")
    print("=" * 60)
    
    # Check strategy performance data
    strategy_perf_path = 'data/processed/strategy_performance.parquet'
    if os.path.exists(strategy_perf_path):
        try:
            perf_df = pd.read_parquet(strategy_perf_path)
            print(f"✅ Strategy performance data loaded: {len(perf_df)} strategies")
            
            print(f"\n📊 Max Drawdown Analysis:")
            print(f"   Min drawdown: {perf_df['max_drawdown'].min():.4f}")
            print(f"   Max drawdown: {perf_df['max_drawdown'].max():.4f}")
            print(f"   Mean drawdown: {perf_df['max_drawdown'].mean():.4f}")
            print(f"   Std drawdown: {perf_df['max_drawdown'].std():.4f}")
            
            print(f"\n📋 Sample Strategy Drawdowns:")
            for _, strategy in perf_df.head(5).iterrows():
                print(f"   {strategy['strategy_name']}: {strategy['max_drawdown']:.4f}")
            
            # Check if all drawdowns are the same
            unique_drawdowns = perf_df['max_drawdown'].nunique()
            print(f"\n🔍 Unique drawdown values: {unique_drawdowns}")
            
            if unique_drawdowns <= 3:
                print("❌ ISSUE DETECTED: Very few unique drawdown values")
                print("   This suggests drawdown calculation is not working properly")
                
                # Check source data
                print(f"\n🔍 Checking source strategy performance data...")
                source_path = 'data/processed/strategy_performance/summary.json'
                if os.path.exists(source_path):
                    with open(source_path, 'r') as f:
                        source_data = json.load(f)
                    
                    print(f"📊 Source Data Drawdowns:")
                    for strategy, data in list(source_data.items())[:5]:
                        drawdown = data.get('max_drawdown', 0)
                        print(f"   {strategy}: {drawdown:.4f}")
                    
                    # Check if source has real drawdowns
                    source_drawdowns = [data.get('max_drawdown', 0) for data in source_data.values()]
                    source_unique = len(set(source_drawdowns))
                    print(f"   Source unique drawdowns: {source_unique}")
                    
                    if source_unique > 3:
                        print("✅ Source data has proper drawdowns - conversion issue")
                        return 'conversion_issue'
                    else:
                        print("❌ Source data also has drawdown issues - calculation issue")
                        return 'calculation_issue'
                else:
                    print("❌ Source strategy performance data not found")
                    return 'missing_source'
            else:
                print("✅ Drawdown values appear diverse - may be working correctly")
                return 'working'
                
        except Exception as e:
            print(f"❌ Error loading strategy performance: {e}")
            return 'error'
    else:
        print("❌ Strategy performance data not found")
        return 'missing'

def investigate_regime_transition():
    """Investigate regime transition behavior"""
    
    print("\n🔄 INVESTIGATING REGIME TRANSITION")
    print("=" * 60)
    
    # Load regime fingerprints to see actual regime evolution
    regime_path = 'data/processed/regime_fingerprints_extended.parquet'
    if os.path.exists(regime_path):
        try:
            regime_df = pd.read_parquet(regime_path)
            print(f"✅ Regime fingerprints loaded: {len(regime_df)} periods")
            
            # Check recent regime evolution
            recent_regimes = regime_df.tail(10)
            print(f"\n📊 Recent Regime Evolution (last 10 periods):")
            for i, (date, row) in enumerate(recent_regimes.iterrows()):
                regime_name = row['regime_name']
                regime_cluster = row['regime_cluster']
                print(f"   {date.date()}: {regime_name} (cluster {regime_cluster})")
            
            # Check regime stability over time
            print(f"\n📈 Regime Transition Analysis:")
            regime_changes = []
            prev_regime = None
            
            for date, row in regime_df.tail(20).iterrows():
                current_regime = row['regime_name']
                if prev_regime and current_regime != prev_regime:
                    regime_changes.append({
                        'date': date,
                        'from': prev_regime,
                        'to': current_regime
                    })
                prev_regime = current_regime
            
            print(f"   Recent regime changes: {len(regime_changes)}")
            for change in regime_changes[-5:]:  # Last 5 changes
                print(f"   {change['date'].date()}: {change['from']} → {change['to']}")
            
            # Check current regime determination
            latest_regime = regime_df.iloc[-1]
            print(f"\n🎯 Current Regime Analysis:")
            print(f"   Latest regime: {latest_regime['regime_name']}")
            print(f"   Regime cluster: {latest_regime['regime_cluster']}")
            print(f"   Date: {latest_regime.name.date()}")
            
            # Check regime cluster distribution
            cluster_counts = regime_df['regime_cluster'].value_counts().sort_index()
            print(f"\n📊 Regime Cluster Distribution:")
            for cluster, count in cluster_counts.head(10).items():
                regime_name = regime_df[regime_df['regime_cluster'] == cluster]['regime_name'].iloc[0]
                percentage = count / len(regime_df) * 100
                print(f"   Cluster {cluster} ({regime_name}): {count} periods ({percentage:.1f}%)")
            
            return 'analyzed'
            
        except Exception as e:
            print(f"❌ Error loading regime fingerprints: {e}")
            return 'error'
    else:
        print("❌ Regime fingerprints not found")
        return 'missing'

def investigate_anticipatory_signals():
    """Investigate anticipatory intelligence signals"""
    
    print("\n🔮 INVESTIGATING ANTICIPATORY SIGNALS")
    print("=" * 60)
    
    signals_path = 'data/processed/anticipatory_signals.json'
    if os.path.exists(signals_path):
        try:
            with open(signals_path, 'r') as f:
                signals = json.load(f)
            
            print(f"✅ Anticipatory signals loaded")
            
            # Check current regime
            current_regime = signals.get('current_regime', {})
            print(f"\n🎯 Current Regime Intelligence:")
            print(f"   Name: {current_regime.get('name', 'Unknown')}")
            print(f"   Cluster: {current_regime.get('cluster', 'Unknown')}")
            print(f"   Stability: {current_regime.get('stability', 0):.4f}")
            print(f"   Duration: {current_regime.get('duration_in_regime', 0)} periods")
            
            # Check regime transitions
            transitions = signals.get('regime_transitions', {})
            next_regime_probs = transitions.get('next_regime_probabilities', {})
            print(f"\n🔄 Regime Transition Predictions:")
            print(f"   Predictions available: {len(next_regime_probs)}")
            for regime, prob in next_regime_probs.items():
                print(f"   {regime}: {prob:.3f}")
            
            # Check forward expectations
            forward_expectations = signals.get('forward_expectations', {})
            print(f"\n📈 Forward Expectations:")
            print(f"   Periods with expectations: {len(forward_expectations)}")
            for period, expectation in forward_expectations.items():
                if isinstance(expectation, dict):
                    expected_return = expectation.get('expected_return', 0)
                    confidence = expectation.get('confidence', 0)
                    print(f"   {period}: {expected_return:.4f} return, {confidence:.3f} confidence")
            
            # Check risk assessment
            risk_assessment = signals.get('risk_assessment', {})
            print(f"\n⚠️ Risk Assessment:")
            print(f"   Regime risk level: {risk_assessment.get('regime_risk_level', 'unknown')}")
            print(f"   Transition risk: {risk_assessment.get('transition_risk', 0):.4f}")
            print(f"   Stability risk: {risk_assessment.get('stability_risk', 0):.4f}")
            
            # Check anticipatory actions
            actions = signals.get('anticipatory_actions', {})
            print(f"\n🎯 Anticipatory Actions:")
            for action_type, action_data in actions.items():
                print(f"   {action_type}: {type(action_data).__name__}")
                if isinstance(action_data, dict):
                    for key, value in action_data.items():
                        print(f"     {key}: {value}")
            
            return 'analyzed'
            
        except Exception as e:
            print(f"❌ Error loading anticipatory signals: {e}")
            return 'error'
    else:
        print("❌ Anticipatory signals not found")
        return 'missing'

def investigate_capital_allocation():
    """Investigate capital allocation calculations"""
    
    print("\n🎯 INVESTIGATING CAPITAL ALLOCATION")
    print("=" * 60)
    
    allocation_path = 'data/processed/anticipatory_capital_allocations.parquet'
    if os.path.exists(allocation_path):
        try:
            alloc_df = pd.read_parquet(allocation_path)
            print(f"✅ Capital allocations loaded: {len(alloc_df)} allocations")
            
            # Check allocation distribution
            print(f"\n📊 Allocation Analysis:")
            total_allocation = alloc_df['allocation_weight'].sum()
            print(f"   Total allocation: {total_allocation:.4f}")
            
            cash_allocation = alloc_df[alloc_df['strategy_name'] == 'CASH']['allocation_weight'].iloc[0]
            equity_allocation = alloc_df[alloc_df['strategy_name'] != 'CASH']['allocation_weight'].sum()
            print(f"   Cash allocation: {cash_allocation:.4f}")
            print(f"   Equity allocation: {equity_allocation:.4f}")
            
            # Check top allocations
            print(f"\n🏆 Top Allocations:")
            top_allocations = alloc_df.nlargest(5, 'allocation_weight')
            for _, allocation in top_allocations.iterrows():
                print(f"   {allocation['strategy_name']}: {allocation['allocation_weight']:.4f} "
                      f"(fitness: {allocation.get('regime_fitness', 0):.3f})")
            
            # Check regime fitness distribution
            fitness_values = alloc_df[alloc_df['strategy_name'] != 'CASH']['regime_fitness']
            print(f"\n📈 Regime Fitness Analysis:")
            print(f"   Min fitness: {fitness_values.min():.4f}")
            print(f"   Max fitness: {fitness_values.max():.4f}")
            print(f"   Mean fitness: {fitness_values.mean():.4f}")
            print(f"   Unique fitness values: {fitness_values.nunique()}")
            
            if fitness_values.nunique() <= 3:
                print("❌ ISSUE DETECTED: Very few unique fitness values")
                print("   This suggests regime fitness calculation may not be working properly")
            
            # Check allocation history
            history_path = 'data/processed/allocation_history.parquet'
            if os.path.exists(history_path):
                history_df = pd.read_parquet(history_path)
                print(f"\n📚 Allocation History:")
                print(f"   Total records: {len(history_df)}")
                
                # Check recent changes
                recent_history = history_df.tail(10)
                regime_changes = recent_history['regime_name'].nunique()
                print(f"   Recent regime changes: {regime_changes}")
                
                # Check cash allocation evolution
                cash_evolution = recent_history[recent_history['strategy_name'] == 'CASH']['allocation_weight']
                if len(cash_evolution) > 1:
                    cash_change = cash_evolution.iloc[-1] - cash_evolution.iloc[0]
                    print(f"   Recent cash allocation change: {cash_change:.4f}")
            
            return 'analyzed'
            
        except Exception as e:
            print(f"❌ Error loading capital allocations: {e}")
            return 'error'
    else:
        print("❌ Capital allocations not found")
        return 'missing'

def check_data_pipeline_integrity():
    """Check data pipeline integrity"""
    
    print("\n🔧 CHECKING DATA PIPELINE INTEGRITY")
    print("=" * 60)
    
    # Check key data files
    key_files = {
        'regime_fingerprints': 'data/processed/regime_fingerprints_extended.parquet',
        'anticipatory_signals': 'data/processed/anticipatory_signals.json',
        'strategy_performance': 'data/processed/strategy_performance.parquet',
        'capital_allocations': 'data/processed/anticipatory_capital_allocations.parquet',
        'strategy_beliefs': 'data/processed/strategy_beliefs.parquet',
        'strategy_regret': 'data/processed/strategy_regret.parquet'
    }
    
    file_status = {}
    
    for name, path in key_files.items():
        if os.path.exists(path):
            try:
                if path.endswith('.parquet'):
                    df = pd.read_parquet(path)
                    file_status[name] = {
                        'exists': True,
                        'records': len(df),
                        'columns': len(df.columns),
                        'latest_date': df.index[-1] if hasattr(df.index, 'date') else 'N/A'
                    }
                elif path.endswith('.json'):
                    with open(path, 'r') as f:
                        data = json.load(f)
                    file_status[name] = {
                        'exists': True,
                        'keys': len(data.keys()) if isinstance(data, dict) else 'N/A',
                        'timestamp': data.get('timestamp', 'N/A') if isinstance(data, dict) else 'N/A'
                    }
            except Exception as e:
                file_status[name] = {'exists': True, 'error': str(e)}
        else:
            file_status[name] = {'exists': False}
    
    print(f"📊 Data Pipeline Status:")
    for name, status in file_status.items():
        if status['exists']:
            if 'error' in status:
                print(f"   ❌ {name}: ERROR - {status['error']}")
            else:
                if 'records' in status:
                    print(f"   ✅ {name}: {status['records']} records, {status['columns']} columns")
                else:
                    print(f"   ✅ {name}: {status.get('keys', 'N/A')} keys")
        else:
            print(f"   ❌ {name}: MISSING")
    
    return file_status

def verify_regime_clustering_logic():
    """Verify regime clustering is working correctly"""
    
    print("\n🧠 VERIFYING REGIME CLUSTERING LOGIC")
    print("=" * 60)
    
    # Load regime clusters metadata
    clusters_path = 'data/processed/regime_clusters_extended.json'
    if os.path.exists(clusters_path):
        try:
            with open(clusters_path, 'r') as f:
                clusters_data = json.load(f)
            
            print(f"✅ Regime clusters metadata loaded")
            
            cluster_stats = clusters_data.get('cluster_stats', {})
            print(f"\n📊 Cluster Statistics:")
            print(f"   Total clusters: {len(cluster_stats)}")
            
            for cluster_id, stats in cluster_stats.items():
                name = stats.get('name', f'Cluster_{cluster_id}')
                size = stats.get('size', 0)
                percentage = stats.get('percentage', 0)
                stability = stats.get('stability', 0)
                
                print(f"   {name}: {size} periods ({percentage:.1f}%), stability: {stability:.4f}")
            
            # Check if clustering makes sense
            total_periods = sum(stats.get('size', 0) for stats in cluster_stats.values())
            print(f"\n🔍 Clustering Validation:")
            print(f"   Total periods in clusters: {total_periods}")
            
            # Check for reasonable distribution
            sizes = [stats.get('size', 0) for stats in cluster_stats.values()]
            max_cluster_size = max(sizes)
            min_cluster_size = min(sizes)
            
            print(f"   Largest cluster: {max_cluster_size} periods")
            print(f"   Smallest cluster: {min_cluster_size} periods")
            print(f"   Size ratio: {max_cluster_size / min_cluster_size:.2f}")
            
            if max_cluster_size / min_cluster_size > 50:
                print("⚠️ WARNING: Very uneven cluster distribution")
                print("   This might indicate clustering issues")
            
            return 'analyzed'
            
        except Exception as e:
            print(f"❌ Error loading regime clusters: {e}")
            return 'error'
    else:
        print("❌ Regime clusters metadata not found")
        return 'missing'

def generate_integrity_report():
    """Generate comprehensive integrity report"""
    
    print("\n📋 GENERATING SYSTEM INTEGRITY REPORT")
    print("=" * 60)
    
    # Run all investigations
    drawdown_status = investigate_max_drawdown_issue()
    regime_status = investigate_regime_transition()
    signals_status = investigate_anticipatory_signals()
    allocation_status = investigate_capital_allocation()
    pipeline_status = check_data_pipeline_integrity()
    clustering_status = verify_regime_clustering_logic()
    
    # Create integrity report
    integrity_report = {
        'timestamp': datetime.now().isoformat(),
        'investigation_type': 'system_integrity',
        'version': '1.0',
        
        'issues_identified': {
            'max_drawdown_issue': drawdown_status != 'working',
            'regime_transition_behavior': regime_status == 'analyzed',
            'anticipatory_signals_working': signals_status == 'analyzed',
            'capital_allocation_working': allocation_status == 'analyzed',
            'data_pipeline_integrity': all(status.get('exists', False) for status in pipeline_status.values()),
            'regime_clustering_working': clustering_status == 'analyzed'
        },
        
        'detailed_status': {
            'max_drawdown_investigation': drawdown_status,
            'regime_transition_investigation': regime_status,
            'anticipatory_signals_investigation': signals_status,
            'capital_allocation_investigation': allocation_status,
            'data_pipeline_status': pipeline_status,
            'regime_clustering_investigation': clustering_status
        },
        
        'recommendations': []
    }
    
    # Generate recommendations
    if drawdown_status != 'working':
        integrity_report['recommendations'].append({
            'issue': 'max_drawdown_calculation',
            'priority': 'high',
            'action': 'Fix drawdown calculation in strategy performance pipeline',
            'details': 'Max drawdown values are not being calculated correctly'
        })
    
    if regime_status == 'analyzed':
        integrity_report['recommendations'].append({
            'issue': 'regime_transition_verification',
            'priority': 'medium',
            'action': 'Verify regime transition logic is working as expected',
            'details': 'Regime changed from Expansion_Liquidity_Driven to Neutral_Consolidation'
        })
    
    # Save integrity report
    report_path = 'data/reports/system_integrity_report.json'
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    
    with open(report_path, 'w') as f:
        json.dump(integrity_report, f, indent=2, default=str)
    
    print(f"💾 System integrity report saved: {report_path}")
    
    # Print summary
    issues_count = sum(integrity_report['issues_identified'].values())
    total_checks = len(integrity_report['issues_identified'])
    
    print(f"\n📊 SYSTEM INTEGRITY SUMMARY:")
    print(f"   Issues identified: {issues_count}/{total_checks}")
    print(f"   Recommendations: {len(integrity_report['recommendations'])}")
    
    for rec in integrity_report['recommendations']:
        priority_icon = "🔴" if rec['priority'] == 'high' else "🟡" if rec['priority'] == 'medium' else "🟢"
        print(f"   {priority_icon} {rec['issue']}: {rec['action']}")
    
    return integrity_report

def main():
    """Main investigation function"""
    
    print("🔍 NORTHSTAR V3 - SYSTEM INTEGRITY INVESTIGATION")
    print("=" * 80)
    print("Investigating critical system issues and data integrity")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Generate comprehensive integrity report
    integrity_report = generate_integrity_report()
    
    # Final assessment
    issues_identified = sum(integrity_report['issues_identified'].values())
    
    if issues_identified == 0:
        print(f"\n✅ SYSTEM INTEGRITY: EXCELLENT")
        print("   No critical issues identified")
        print("   All systems operating as expected")
        return True
    elif issues_identified <= 2:
        print(f"\n⚠️ SYSTEM INTEGRITY: GOOD WITH MINOR ISSUES")
        print(f"   {issues_identified} issues identified")
        print("   System is operational but needs attention")
        return True
    else:
        print(f"\n❌ SYSTEM INTEGRITY: NEEDS ATTENTION")
        print(f"   {issues_identified} issues identified")
        print("   Critical issues need to be addressed")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)