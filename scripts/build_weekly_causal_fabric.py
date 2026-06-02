#!/usr/bin/env python3
"""
🧬 BUILD WEEKLY CAUSAL FABRIC - NORTHSTAR V3 INTEGRATION
The Temporal Causality Builder: One Year at a Time

This script builds the Weekly Causal Fabric system that learns:
"What relationships quietly formed this week, that changed the next 6–12 months?"

This is the layer that turns Northstar from "very good" into unfair.

Usage:
    python scripts/build_weekly_causal_fabric.py

Features:
- Processes one year at a time for M1 safety
- Discovers weekly macro → sector → stock relationships
- Integrates with existing V3 Market Brain
- Feeds anticipatory signals into Capital Allocator
- Enhances Narrative Engine with causal stories
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

# Import V3 components
from src.intelligence.market_brain.weekly_fabric_builder import WeeklyFabricBuilder
from src.intelligence.market_brain.weekly_fabric_reader import WeeklyFabricReader
from src.intelligence.market_brain.market_tensor import MarketTensorEngine

def _year_has_relationship_artifacts(base_dir: str, year: int) -> bool:
    """Treat years with zero-relationship metadata as re-processable."""
    year_dir = os.path.join(base_dir, str(year))
    if not os.path.isdir(year_dir):
        return False
    has_week_files = any(
        name.startswith("week_") and name.endswith(".parquet")
        for name in os.listdir(year_dir)
    )
    if has_week_files:
        return True

    metadata_path = os.path.join(year_dir, "metadata.json")
    if not os.path.exists(metadata_path):
        return False

    try:
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
        return int(metadata.get("total_relationships", 0) or 0) > 0
    except Exception:
        return False

def _get_processed_years(base_dir: str, min_year: int = 2000) -> list[int]:
    """Return processed years while ignoring empty scaffold directories."""
    if not os.path.exists(base_dir):
        return []
    years = []
    for d in os.listdir(base_dir):
        if not d.isdigit():
            continue
        year = int(d)
        if year < min_year:
            continue
        if _year_has_relationship_artifacts(base_dir, year):
            years.append(year)
    return sorted(years)

def check_prerequisites():
    """Check if all prerequisites are available"""
    
    print("🔍 CHECKING PREREQUISITES")
    print("=" * 50)
    
    prerequisites = {
        'market_tensor': False,
        'data_availability': False,
        'storage_space': False
    }
    
    # Check market tensor
    try:
        tensor_engine = MarketTensorEngine()
        tensor = tensor_engine.load_market_tensor()
        
        if not tensor.empty:
            prerequisites['market_tensor'] = True
            print(f"✅ Market tensor available: {tensor.shape}")
            print(f"   Date range: {tensor.index[0].date()} to {tensor.index[-1].date()}")
        else:
            print("⚠️ Market tensor not found - will build it first")
            
    except Exception as e:
        print(f"❌ Market tensor check failed: {e}")
    
    # Check data availability
    try:
        if prerequisites['market_tensor']:
            available_years = sorted(tensor.index.year.unique())
            if len(available_years) >= 1:
                prerequisites['data_availability'] = True
                print(f"✅ Data available for years: {available_years}")
            else:
                print("❌ Insufficient data years available")
        
    except Exception as e:
        print(f"❌ Data availability check failed: {e}")
    
    # Check storage space (simple check)
    try:
        import shutil
        free_space_gb = shutil.disk_usage('.').free / (1024**3)
        
        if free_space_gb > 1.0:  # Need at least 1GB free
            prerequisites['storage_space'] = True
            print(f"✅ Storage space available: {free_space_gb:.1f} GB free")
        else:
            print(f"⚠️ Low storage space: {free_space_gb:.1f} GB free")
            
    except Exception as e:
        print(f"⚠️ Storage space check failed: {e}")
        prerequisites['storage_space'] = True  # Assume OK if can't check
    
    return prerequisites

def build_market_tensor_if_needed():
    """Build market tensor if it doesn't exist"""
    
    print("\n🧠 BUILDING MARKET TENSOR")
    print("=" * 50)
    
    try:
        tensor_engine = MarketTensorEngine()
        tensor = tensor_engine.load_market_tensor()
        
        if tensor.empty:
            print("📊 Building market tensor from scratch...")
            tensor = tensor_engine.build_market_tensor()
            
            if tensor.empty:
                print("❌ Failed to build market tensor")
                return False
            else:
                print(f"✅ Market tensor built successfully: {tensor.shape}")
                return True
        else:
            print(f"✅ Market tensor already exists: {tensor.shape}")
            return True
            
    except Exception as e:
        print(f"❌ Error building market tensor: {e}")
        return False

def process_next_year():
    """Process the next available year starting from 2000"""
    
    print("\n🧬 PROCESSING WEEKLY CAUSAL FABRIC - MODERN ERA (2000+)")
    print("=" * 60)
    
    try:
        # Initialize fabric builder
        builder = WeeklyFabricBuilder()
        
        # Show available years from 2000 onwards
        all_available_years = builder.get_available_years()
        modern_years = [year for year in all_available_years if year >= 2000]
        
        print(f"📅 Total available years (all): {len(all_available_years)} ({min(all_available_years)}-{max(all_available_years)})")
        print(f"📅 Modern era years (2000+): {len(modern_years)} ({min(modern_years) if modern_years else 'None'}-{max(modern_years) if modern_years else 'None'})")
        
        if not modern_years:
            print("❌ No modern era years (2000+) available for processing")
            return False
        
        # Show processed years
        processed_years = _get_processed_years('data/weekly_insights', min_year=2000)
        
        if processed_years:
            print(f"✅ Already processed: {sorted(processed_years)}")
        
        remaining_years = [year for year in modern_years if year not in processed_years]
        if remaining_years:
            print(f"⏳ Remaining to process: {len(remaining_years)} years ({min(remaining_years)}-{max(remaining_years)})")
            next_year = min(remaining_years)
            print(f"🎯 Next year to process: {next_year}")
        else:
            print("🎉 All modern era years have been processed!")
            return True
        
        # Process next year
        success = builder.process_next_year()
        
        if success:
            print("✅ Weekly causal fabric processing completed!")
            
            # Show final progress
            updated_processed = _get_processed_years('data/weekly_insights', min_year=2000)
            
            completed_pct = len(updated_processed) / len(modern_years) * 100
            print(f"   📊 Overall progress: {len(updated_processed)}/{len(modern_years)} years ({completed_pct:.1f}%)")
            return True
        else:
            print("❌ Failed to process weekly causal fabric")
            return False
            
    except Exception as e:
        print(f"❌ Error processing weekly causal fabric: {e}")
        return False

def test_fabric_reader():
    """Test the fabric reader functionality"""
    
    print("\n🔍 TESTING FABRIC READER")
    print("=" * 50)
    
    try:
        reader = WeeklyFabricReader()
        
        # Test basic functionality
        print("📊 Testing market pressure analysis...")
        pressure = reader.get_current_market_pressure()
        print(f"   Found {len(pressure['pressure_vectors'])} pressure vectors")
        print(f"   Regime pressure: {pressure['regime_pressure']}")
        
        print("📈 Testing emerging relationships...")
        emerging = reader.get_emerging_relationships()
        print(f"   Found {len(emerging)} emerging relationships")

        print("🕒 Testing data freshness diagnostics...")
        freshness = reader.get_data_freshness()
        print(f"   Latest relationship date: {freshness.get('relationship_latest_date')}")
        print(f"   Latest tensor date: {freshness.get('tensor_latest_date')}")
        print(f"   Tensor→relationship lag (days): {freshness.get('lag_days')}")

        print("📉 Testing relationship trends...")
        trends = reader.get_relationship_trends()
        rising_count = len(trends['rising_relationships'])
        weakening_count = len(trends['weakening_relationships'])
        new_count = len(trends['new_relationships'])
        print(f"   Rising: {rising_count}, Weakening: {weakening_count}, New: {new_count}")
        
        print("🔮 Testing anticipatory signals...")
        signals = reader.get_anticipatory_signals()
        signal_count = len(signals['signals'])
        transition_prob = signals['regime_transition_probability']
        print(f"   Found {signal_count} anticipatory signals")
        print(f"   Regime transition probability: {transition_prob:.2f}")
        
        print("💰 Testing capital allocation insights...")
        insights = reader.get_capital_allocation_insights()
        fitness_count = len(insights.get('strategy_fitness_multipliers', {}))
        rotation_count = len(insights.get('sector_rotation_signals', []))
        print(f"   Strategy fitness multipliers: {fitness_count}")
        print(f"   Sector rotation signals: {rotation_count}")
        
        print("✅ Fabric reader tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing fabric reader: {e}")
        return False

def show_integration_status():
    """Show integration status with existing V3 systems"""
    
    print("\n🔗 INTEGRATION STATUS")
    print("=" * 50)
    
    integration_points = {
        'Market Tensor Engine': 'src/intelligence/market_brain/market_tensor.py',
        'Capital Allocator': 'src/intelligence/capital_allocator.py',
        'Narrative Engine': 'src/intelligence/narrative_engine.py',
        'Intelligence Stack': 'src/intelligence/intelligence_stack.py',
        'Market Brain': 'src/intelligence/market_brain/'
    }
    
    for component, path in integration_points.items():
        if os.path.exists(path):
            print(f"✅ {component}: Ready for integration")
        else:
            print(f"⚠️ {component}: Path not found - {path}")
    
    # Check if weekly insights directory exists
    weekly_insights_dir = 'data/weekly_insights'
    if os.path.exists(weekly_insights_dir):
        # Count processed years
        processed_years = [str(y) for y in _get_processed_years(weekly_insights_dir, min_year=0)]
        
        if processed_years:
            print(f"📊 Processed years: {sorted(processed_years)}")
            
            # Count total relationships
            total_relationships = 0
            for year in processed_years:
                year_dir = os.path.join(weekly_insights_dir, year)
                week_files = [f for f in os.listdir(year_dir) if f.startswith('week_') and f.endswith('.parquet')]
                
                for week_file in week_files:
                    try:
                        week_path = os.path.join(year_dir, week_file)
                        week_data = pd.read_parquet(week_path)
                        total_relationships += len(week_data)
                    except:
                        continue
            
            print(f"🧬 Total relationships discovered: {total_relationships:,}")
        else:
            print("📊 No processed years found - run the fabric builder first")
    else:
        print("📊 Weekly insights directory not found - will be created on first run")

def show_next_steps():
    """Show next steps for integration"""
    
    print("\n🎯 NEXT STEPS")
    print("=" * 50)
    
    print("1. 📊 Data Integration:")
    print("   - Weekly Causal Fabric feeds into Capital Allocator")
    print("   - Relationship trends enhance Narrative Engine")
    print("   - Anticipatory signals upgrade Intelligence Stack")
    
    print("\n2. 🔄 Workflow Integration:")
    print("   - Run this script daily/weekly to process new years")
    print("   - Use WeeklyFabricReader in existing systems")
    print("   - Monitor relationship evolution for regime changes")
    
    print("\n3. 🧠 Intelligence Enhancement:")
    print("   - Capital allocation becomes anticipatory")
    print("   - Narratives include causal explanations")
    print("   - Risk management gets early warning signals")
    
    print("\n4. 📈 Performance Monitoring:")
    print("   - Track relationship prediction accuracy")
    print("   - Monitor regime transition detection")
    print("   - Measure anticipatory signal effectiveness")

def main():
    """Main execution function"""
    
    print("🧬 WEEKLY CAUSAL FABRIC BUILDER")
    print("Building the layer that makes Northstar unfairly powerful")
    print("=" * 60)
    
    # Check prerequisites
    prerequisites = check_prerequisites()
    
    if not all(prerequisites.values()):
        print("\n❌ Prerequisites not met. Please address the issues above.")
        return False
    
    # Build market tensor if needed
    if not build_market_tensor_if_needed():
        print("\n❌ Cannot proceed without market tensor")
        return False
    
    # Process next year
    if not process_next_year():
        print("\n❌ Failed to process weekly causal fabric")
        return False
    
    # Test fabric reader
    if not test_fabric_reader():
        print("\n⚠️ Fabric reader tests failed, but fabric was built")
    
    # Show integration status
    show_integration_status()
    
    # Show next steps
    show_next_steps()
    
    print("\n🎉 WEEKLY CAUSAL FABRIC BUILD COMPLETED!")
    print("🧠 Northstar now has temporal causality learning")
    print("🔮 Run again to process the next year")
    print("💡 Use WeeklyFabricReader to access relationship insights")
    
    return True

if __name__ == "__main__":
    success = main()
    
    if success:
        print("\n✅ Build completed successfully!")
        exit(0)
    else:
        print("\n❌ Build failed!")
        exit(1)
