#!/usr/bin/env python3
"""
Complete Gap 3 Implementation Script

This script validates the current state and provides next steps for completing Gap 3.
"""

import sys
from pathlib import Path
from datetime import datetime

def check_prerequisites():
    """Check that Gap 1 and Gap 2 are complete."""
    print("🔍 Checking Prerequisites...")
    print("=" * 60)
    
    # Check Gap 1
    gap1_file = Path("GAP1_INGESTION_LAYER_COMPLETE.md")
    if gap1_file.exists():
        print("✓ Gap 1: Ingestion Layer Complete")
    else:
        print("✗ Gap 1: NOT COMPLETE - Required for Gap 3")
        return False
    
    # Check Gap 2
    gap2_file = Path("GAP2_READY_FOR_PRODUCTION.md")
    if gap2_file.exists():
        print("✓ Gap 2: Sentiment System Complete")
    else:
        print("✗ Gap 2: NOT COMPLETE - Required for Gap 3")
        return False
    
    # Check ingestion registry
    registry_file = Path("src/ingestion/ingestion_registry.py")
    if registry_file.exists():
        print("✓ IngestionRegistry exists")
    else:
        print("✗ IngestionRegistry missing")
        return False
    
    # Check alternative loader
    loader_file = Path("src/ingestion/alternative_loader.py")
    if loader_file.exists():
        print("✓ AlternativeDataLoader exists")
    else:
        print("✗ AlternativeDataLoader missing")
        return False
    
    return True

def check_data_availability():
    """Check that alternative data exists."""
    print("\n🗂️  Checking Data Availability...")
    print("=" * 60)
    
    data_sources = {
        'Bulk Deals': 'data/raw/exchanges/bse/alternative/bulk_deals',
        'Promoter Pledges': 'data/raw/exchanges/bse/alternative/promoter_pledge',
        'Credit Ratings': 'data/raw/shared/alternative/credit_ratings',
        'GST Data': 'data/processed/gst_monthly.parquet',
        'Power Data': 'data/processed/macro/cea_power_daily.parquet'
    }
    
    all_present = True
    for name, path in data_sources.items():
        p = Path(path)
        if p.exists():
            if p.is_dir():
                count = len(list(p.glob('*.csv')))
                print(f"✓ {name}: {count} files")
            else:
                print(f"✓ {name}: File exists")
        else:
            print(f"✗ {name}: NOT FOUND at {path}")
            all_present = False
    
    return all_present

def check_implementation_status():
    """Check what has been implemented."""
    print("\n📋 Implementation Status...")
    print("=" * 60)
    
    components = {
        'Alternative State': 'src/alternative_data/alternative_state.py',
        'Feature Block': 'src/alternative_data/alternative_feature_block.py',
        'Macro Bridge': 'src/alternative_data/macro_alternative_bridge.py',
        'Valuation Bridge': 'src/alternative_data/valuation_alternative_bridge.py',
        'Risk Bridge': 'src/alternative_data/risk_alternative_bridge.py',
        'Pipeline Runner': 'src/alternative_data/alternative_pipeline_runner.py'
    }
    
    completed = 0
    for name, path in components.items():
        if Path(path).exists():
            print(f"✓ {name}")
            completed += 1
        else:
            print(f"⬜ {name} - TODO")
    
    print(f"\nProgress: {completed}/{len(components)} components")
    return completed, len(components)

def print_next_steps():
    """Print actionable next steps."""
    print("\n🎯 Next Steps...")
    print("=" * 60)
    
    steps = [
        "1. Complete alternative_feature_block.py implementation",
        "   - Add all _compute_*_features() methods",
        "   - Add compute_company_level_features()",
        "   - Add feature name getters",
        "",
        "2. Create macro_alternative_bridge.py",
        "   - Connect GST and power to Kalman Filter",
        "   - Provide macro forecast inputs",
        "",
        "3. Create valuation_alternative_bridge.py",
        "   - Connect credit ratings to CreditFamilyEngine",
        "   - Connect pledges to EarningsQualityAnalyzer",
        "",
        "4. Create risk_alternative_bridge.py",
        "   - Portfolio risk assessment",
        "   - Pre-trade risk checks",
        "",
        "5. Create alternative_pipeline_runner.py",
        "   - Orchestrate daily collection",
        "   - Compute AlternativeDataState",
        "",
        "6. Integrate with existing systems",
        "   - Modify macro_forecast.py",
        "   - Modify credit_family.py",
        "   - Modify data_pipeline.py",
        "   - Modify risk_controller.py",
        "",
        "7. Create tests",
        "   - Test feature block",
        "   - Test bridges",
        "   - Test integration",
        "",
        "8. Update startup sequence",
        "   - Add to START_LIVE_SYSTEM.sh",
        "   - Add to preopen_checks.py"
    ]
    
    for step in steps:
        print(step)

def main():
    print("\n🚀 Gap 3: Alternative Data Integration")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Run checks
    prereqs_ok = check_prerequisites()
    data_ok = check_data_availability()
    completed, total = check_implementation_status()
    
    print("\n" + "=" * 60)
    print("📊 Summary")
    print("=" * 60)
    print(f"Prerequisites: {'✓ PASS' if prereqs_ok else '✗ FAIL'}")
    print(f"Data Availability: {'✓ PASS' if data_ok else '✗ FAIL'}")
    print(f"Implementation: {completed}/{total} components ({100*completed//total}%)")
    
    if not prereqs_ok:
        print("\n⚠️  Cannot proceed - prerequisites not met")
        return 1
    
    if not data_ok:
        print("\n⚠️  Warning - some data sources missing")
        print("   Run: python scripts/collect_all_alternative_data.py")
    
    print_next_steps()
    
    print("\n✅ Gap 3 validation complete")
    print("   See GAP3_IMPLEMENTATION_PLAN.md for detailed guidance")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
