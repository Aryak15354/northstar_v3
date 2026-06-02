#!/usr/bin/env python3
"""
Test script for AlternativePipelineRunner.

Tests:
1. Pipeline runner initialization
2. Source freshness checking
3. Alternative state computation
4. Full pipeline execution
5. Idempotency (already fresh)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
import yaml
from src.alternative_data.alternative_pipeline_runner import AlternativePipelineRunner

def load_config():
    """Load configuration"""
    config_path = Path('config/ingestion_config.yaml')
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
    else:
        config = {}
    
    # Add alternative data config if not present
    if 'alternative_data' not in config:
        config['alternative_data'] = {
            'freshness_thresholds': {
                'bulk_deals_max_age_days': 2,
                'power_data_max_age_days': 3,
                'credit_ratings_max_age_days': 7,
                'gst_data_max_age_months': 1.5,
                'promoter_pledges_max_age_days': 100
            }
        }
    
    return config


def test_pipeline_runner_init():
    """Test 1: Pipeline runner initialization"""
    print("\n" + "="*80)
    print("TEST 1: Pipeline Runner Initialization")
    print("="*80)
    
    try:
        config = load_config()
        runner = AlternativePipelineRunner(config)
        
        print(f"✓ Pipeline runner initialized")
        print(f"  Registry: {runner.registry}")
        print(f"  Feature block: {runner.feature_block}")
        print(f"  Freshness thresholds: {runner.freshness_thresholds}")
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_source_freshness():
    """Test 2: Source freshness checking"""
    print("\n" + "="*80)
    print("TEST 2: Source Freshness Checking")
    print("="*80)
    
    try:
        config = load_config()
        runner = AlternativePipelineRunner(config)
        # Use date close to latest data (2026-01-31)
        # GST: 2025-12-31 (1 month old - FRESH)
        # Bulk/Credit: 2026-03-06 available (future - FRESH)
        as_of_date = datetime(2026, 1, 31)
        
        sources = ['gst', 'power', 'credit', 'bulk', 'pledge']
        
        for source in sources:
            is_fresh = runner.is_source_fresh(source, as_of_date)
            status = "✓ FRESH" if is_fresh else "✗ STALE"
            print(f"  {source:15s}: {status}")
        
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_compute_alternative_state():
    """Test 3: Alternative state computation"""
    print("\n" + "="*80)
    print("TEST 3: Alternative State Computation")
    print("="*80)
    
    try:
        config = load_config()
        runner = AlternativePipelineRunner(config)
        as_of_date = datetime(2026, 1, 31)
        
        state = runner.compute_alternative_state(as_of_date)
        
        print(f"✓ Alternative state computed")
        print(f"\n  GST Signal:")
        print(f"    Regime: {state.gst.regime.name}")
        print(f"    YoY Growth: {state.gst.yoy_growth_pct:.4f}%")
        print(f"    Trend Direction: {state.gst.trend_direction}")
        print(f"    Fresh: {state.gst.is_fresh}")
        
        print(f"\n  Power Signal:")
        print(f"    Regime: {state.power.regime.name}")
        print(f"    YoY Growth: {state.power.yoy_growth_pct:.4f}%")
        print(f"    Industrial Proxy: {state.power.industrial_proxy_score:.2f}")
        print(f"    Fresh: {state.power.is_fresh}")
        
        print(f"\n  Credit Signal:")
        print(f"    Upgrade Ratio: {state.credit.market_upgrade_ratio:.4f}")
        print(f"    Net Momentum: {state.credit.net_credit_momentum:.4f}")
        print(f"    Stress Flag: {state.credit.high_yield_stress_flag}")
        print(f"    Fresh: {state.credit.is_fresh}")
        
        print(f"\n  Smart Money:")
        print(f"    Signal: {state.smart_money.market_signal.name}")
        print(f"    Net Flow: {state.smart_money.net_institutional_flow_score:.4f}")
        print(f"    Accumulation Breadth: {state.smart_money.accumulation_breadth:.4f}")
        print(f"    Fresh: {state.smart_money.is_fresh}")
        
        print(f"\n  Promoter Risk:")
        print(f"    Market Avg Pledge: {state.promoter_risk.market_avg_pledge_pct:.2f}%")
        print(f"    Systemic Risk: {state.promoter_risk.systemic_pledge_risk}")
        print(f"    Fresh: {state.promoter_risk.is_fresh}")
        
        print(f"\n  Economic Activity Regime: {state.economic_activity_regime.name}")
        print(f"  Any Source Fresh: {state.any_source_fresh}")
        print(f"  All Sources Fresh: {state.all_sources_fresh}")
        
        return True
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_pipeline():
    """Test 4: Full pipeline execution"""
    print("\n" + "="*80)
    print("TEST 4: Full Pipeline Execution")
    print("="*80)
    
    try:
        config = load_config()
        runner = AlternativePipelineRunner(config)
        as_of_date = datetime(2026, 1, 31)
        
        result = runner.run(as_of_date, force=True)
        
        print(f"✓ Pipeline executed")
        print(f"  Status: {result.status}")
        print(f"  Duration: {result.run_duration_seconds:.2f}s")
        print(f"  Sources processed:")
        for source, success in result.sources_processed.items():
            status = "✓" if success else "✗"
            print(f"    {status} {source}")
        
        if result.errors:
            print(f"  Errors:")
            for error in result.errors:
                print(f"    - {error}")
        
        return result.status in ['SUCCESS', 'ALREADY_FRESH']
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_idempotency():
    """Test 5: Idempotency (already fresh)"""
    print("\n" + "="*80)
    print("TEST 5: Idempotency Check")
    print("="*80)
    
    try:
        config = load_config()
        runner = AlternativePipelineRunner(config)
        as_of_date = datetime(2026, 1, 31)
        
        # Run once with force
        result1 = runner.run(as_of_date, force=True)
        print(f"  First run: {result1.status} ({result1.run_duration_seconds:.2f}s)")
        
        # Run again without force (should be already fresh)
        result2 = runner.run(as_of_date, force=False)
        print(f"  Second run: {result2.status} ({result2.run_duration_seconds:.2f}s)")
        
        if result2.status == 'ALREADY_FRESH':
            print(f"✓ Idempotency verified - second run skipped processing")
            return True
        else:
            print(f"✗ Idempotency failed - second run processed data")
            return False
            
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("ALTERNATIVE PIPELINE RUNNER TEST SUITE")
    print("="*80)
    
    tests = [
        ("Initialization", test_pipeline_runner_init),
        ("Source Freshness", test_source_freshness),
        ("State Computation", test_compute_alternative_state),
        ("Full Pipeline", test_full_pipeline),
        ("Idempotency", test_idempotency),
    ]
    
    results = []
    for name, test_func in tests:
        passed = test_func()
        results.append((name, passed))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
    
    passed_count = sum(1 for _, p in results if p)
    total_count = len(results)
    print(f"\nPassed: {passed_count}/{total_count}")
    
    return passed_count == total_count


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
