"""
Signal Engineering System - Demo Script

Demonstrates the core functionality of the signal engineering framework:
1. Loading configuration from YAML
2. Applying PIT safety buffers to financial data
3. Running leakage tests on features
4. Managing PIT audit log

This is a standalone demo that can be run independently of the main system.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# Import signal engineering components
from src.signal_engineering import (
    SignalEngineeringConfig,
    PITTimestampManager,
    PITAuditLog,
    LeakageTest,
    create_pit_audit_entry
)


def generate_sample_data(n_stocks=50, n_days=500):
    """Generate sample financial data for demonstration
    
    Creates synthetic data with:
    - Stock identifiers
    - Dates
    - Feature values (momentum, value, quality)
    - Forward returns
    """
    print("\n" + "="*60)
    print("GENERATING SAMPLE DATA")
    print("="*60)
    
    stocks = [f"STOCK_{i:03d}" for i in range(n_stocks)]
    dates = pd.date_range(end=datetime.now(), periods=n_days, freq='D')
    
    # Create panel data
    data = []
    for stock in stocks:
        for date in dates:
            data.append({
                'date': date,
                'stock': stock,
                'momentum_3m': np.random.randn(),
                'value_score': np.random.randn(),
                'quality_score': np.random.randn(),
                'forward_return': np.random.randn() * 0.02  # 2% daily vol
            })
    
    df = pd.DataFrame(data)
    
    print(f"Generated {len(df):,} observations")
    print(f"  Stocks: {n_stocks}")
    print(f"  Days: {n_days}")
    print(f"  Date range: {df['date'].min().date()} to {df['date'].max().date()}")
    
    return df


def demo_configuration():
    """Demo 1: Load and validate configuration"""
    print("\n" + "="*60)
    print("DEMO 1: CONFIGURATION MANAGEMENT")
    print("="*60)
    
    # Load configuration from YAML
    config_path = Path("config/signal_engineering_baseline.yaml")
    
    if config_path.exists():
        print(f"\nLoading configuration from: {config_path}")
        config = SignalEngineeringConfig.from_yaml(config_path)
    else:
        print("\nUsing default configuration")
        config = SignalEngineeringConfig()
    
    # Display key configuration
    print(f"\nPhase: {config.phase}")
    print(f"Universe Size: {config.universe_size} stocks")
    print(f"Feature Budget: {config.feature_budget.budget} features (N/5 rule)")
    print(f"\nXGBoost Hyperparameters:")
    print(f"  max_depth: {config.xgboost.max_depth}")
    print(f"  min_child_weight: {config.xgboost.min_child_weight}")
    print(f"  learning_rate: {config.xgboost.learning_rate}")
    print(f"\nPhase 0 Gate: IC >= {config.gates.phase_0}")
    print(f"Target (Phase 7): IC >= {config.gates.phase_7}")
    
    # Validate configuration
    try:
        config.validate()
        print("\n✅ Configuration validated successfully")
    except AssertionError as e:
        print(f"\n❌ Configuration validation failed: {e}")
    
    return config


def demo_pit_audit(config):
    """Demo 2: PIT timestamp management and safety buffers"""
    print("\n" + "="*60)
    print("DEMO 2: PIT AUDIT FRAMEWORK")
    print("="*60)
    
    # Create PIT timestamp manager
    pit_manager = PITTimestampManager(config.pit_buffers)
    
    # Generate sample quarterly financial data
    print("\nGenerating sample quarterly financial data...")
    financial_data = pd.DataFrame({
        'date': pd.date_range(end=datetime.now() - timedelta(days=10), periods=20, freq='Q'),
        'stock': ['STOCK_001'] * 20,
        'eps': np.random.randn(20),
        'revenue': np.random.uniform(100, 200, 20)
    })
    
    print(f"Original date range: {financial_data['date'].min().date()} to {financial_data['date'].max().date()}")
    
    # Apply safety buffer for quarterly financials
    print(f"\nApplying {config.pit_buffers.quarterly_financials}-day safety buffer...")
    buffered_data = pit_manager.apply_safety_buffer(
        financial_data,
        data_type='quarterly_financials',
        timestamp_col='date'
    )
    
    print(f"Buffered date range: {buffered_data['date'].min().date()} to {buffered_data['date'].max().date()}")
    
    # Validate timestamps
    is_valid = pit_manager.validate_timestamps(buffered_data, 'date')
    print(f"\n{'✅' if is_valid else '❌'} All timestamps are in the past: {is_valid}")
    
    # Show buffer application for different data types
    print("\nSafety buffers by data type:")
    for data_type in ['quarterly_financials', 'annual_financials', 'earnings_announcements', 
                      'bulk_deals', 'price_data', 'analyst_estimates', 'shareholding']:
        buffer = config.pit_buffers.get_buffer(data_type)
        print(f"  {data_type}: {buffer} days")
    
    return pit_manager


def demo_leakage_test(config):
    """Demo 3: Automated leakage detection"""
    print("\n" + "="*60)
    print("DEMO 3: LEAKAGE TEST FRAMEWORK")
    print("="*60)
    
    # Generate sample data
    data = generate_sample_data(n_stocks=30, n_days=300)
    
    # Create leakage tester
    tester = LeakageTest(
        shift_days=config.leakage_shift_days,
        ic_ratio_threshold=config.leakage_ic_ratio_threshold
    )
    
    print(f"\nLeakage Test Configuration:")
    print(f"  Shift days: {tester.shift_days}")
    print(f"  IC ratio threshold: {tester.ic_ratio_threshold}")
    
    # Test features
    feature_names = ['momentum_3m', 'value_score', 'quality_score']
    
    print(f"\nTesting {len(feature_names)} features for leakage...")
    results = tester.test_multiple_features(
        feature_names=feature_names,
        features=data,
        returns=data,
        return_col='forward_return'
    )
    
    # Print detailed report
    tester.print_report(results)
    
    return results


def demo_audit_log(config, leakage_results):
    """Demo 4: PIT audit log management"""
    print("\n" + "="*60)
    print("DEMO 4: PIT AUDIT LOG")
    print("="*60)
    
    # Create audit log
    log_path = Path("data/demo_pit_audit_log.json")
    audit_log = PITAuditLog(log_path)
    
    print(f"\nAudit log path: {log_path}")
    
    # Add entries for each tested feature
    print("\nAdding audit entries for tested features...")
    for feature_name, result in leakage_results.items():
        entry = create_pit_audit_entry(
            feature_name=feature_name,
            data_source="Demo Data",
            data_type="price_data",
            leakage_ic_ratio=result.ic_ratio,
            safety_buffers=config.pit_buffers
        )
        audit_log.add_entry(entry)
        print(f"  Added: {feature_name} (IC ratio: {result.ic_ratio:.4f})")
    
    # Generate report
    report = audit_log.generate_report()
    
    print("\n" + "-"*60)
    print("AUDIT LOG SUMMARY")
    print("-"*60)
    print(f"Total features: {report['total_features']}")
    print(f"Validated features: {report['validated_features']}")
    print(f"Failed features: {report['failed_features']}")
    print(f"Validation rate: {report['validation_rate']:.1%}")
    
    # Show validated features
    validated = audit_log.get_validated_features()
    if validated:
        print(f"\n✅ Validated features ({len(validated)}):")
        for name in validated:
            print(f"  - {name}")
    
    # Show failed features
    failed = audit_log.get_failed_features()
    if failed:
        print(f"\n❌ Failed features ({len(failed)}):")
        for name in failed:
            print(f"  - {name}")
    
    return audit_log


def demo_feature_budget(config):
    """Demo 5: Feature budget enforcement"""
    print("\n" + "="*60)
    print("DEMO 5: FEATURE BUDGET ENFORCEMENT")
    print("="*60)
    
    budget = config.feature_budget
    
    print(f"\nUniverse size: {budget.universe_size} stocks")
    print(f"Feature budget: {budget.budget} features (N/5 rule)")
    
    # Simulate adding features
    print("\nSimulating feature additions:")
    for n_features in [10, 20, 30, 35]:
        utilization = budget.utilization(n_features)
        exceeded = budget.is_exceeded(n_features)
        
        status = "❌ EXCEEDED" if exceeded else "✅ OK"
        print(f"  {n_features} features: {utilization:.1f}% utilization {status}")
    
    # Show budget for different universe sizes
    print("\nFeature budgets for different universe sizes:")
    for size in [150, 200, 250, 300]:
        from src.signal_engineering import FeatureBudgetConfig
        temp_budget = FeatureBudgetConfig(size)
        print(f"  {size} stocks → {temp_budget.budget} features")


def main():
    """Run all demos"""
    print("\n" + "="*60)
    print("SIGNAL ENGINEERING SYSTEM - DEMO")
    print("="*60)
    print("\nThis demo showcases the core functionality of the")
    print("signal engineering framework for quantitative equity research.")
    
    # Demo 1: Configuration
    config = demo_configuration()
    
    # Demo 2: PIT Audit
    pit_manager = demo_pit_audit(config)
    
    # Demo 3: Leakage Testing
    leakage_results = demo_leakage_test(config)
    
    # Demo 4: Audit Log
    audit_log = demo_audit_log(config, leakage_results)
    
    # Demo 5: Feature Budget
    demo_feature_budget(config)
    
    print("\n" + "="*60)
    print("DEMO COMPLETE")
    print("="*60)
    print("\nNext steps:")
    print("1. Review the generated audit log at: data/demo_pit_audit_log.json")
    print("2. Modify config/signal_engineering_baseline.yaml to customize settings")
    print("3. Integrate with your data pipeline for production use")
    print("4. Implement Task 1 subtasks (accruals fix, regime PIT bug fix)")
    print("\nFor production use, connect this module to your existing")
    print("research system's data sources and model training pipeline.")


if __name__ == "__main__":
    main()
