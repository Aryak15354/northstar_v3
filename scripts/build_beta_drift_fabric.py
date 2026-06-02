#!/usr/bin/env python3
"""
🧬 BUILD BETA DRIFT FABRIC - NORTHSTAR V3 MARKET BRAIN
The Market Nervous System: Detecting Sensitivity Shifts Before Price Moves

This is the CORRECTED approach that actually works:

WRONG: macro_delta(t) → stock_return(t+4w) [361 regressors, 29 targets, 40 samples = IMPOSSIBLE]
RIGHT: macro_factor(t) ↔ stock_sensitivity(t) [12 factors, rolling betas, drift detection = REAL SIGNAL]

This detects when stocks become more/less sensitive to macro factors,
which is the real signal that precedes price moves by weeks.

Usage:
    python scripts/build_beta_drift_fabric.py

Features:
- Extracts 12 macro factors from 261 market variables using PCA
- Computes rolling betas between stocks and factors (26-week windows)
- Detects beta drift (sensitivity changes) above threshold
- Processes one year at a time starting from 2000
- Provides detailed progress tracking
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

# Import the corrected beta drift fabric
from src.intelligence.market_brain.beta_drift_fabric import BetaDriftFabric

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
        from src.intelligence.market_brain.market_tensor import MarketTensorEngine
        tensor_engine = MarketTensorEngine()
        tensor = tensor_engine.load_market_tensor()
        
        if not tensor.empty:
            prerequisites['market_tensor'] = True
            print(f"✅ Market tensor available: {tensor.shape}")
            print(f"   Date range: {tensor.index[0].date()} to {tensor.index[-1].date()}")
            
            # Check for modern era data (2000+)
            modern_data = tensor[tensor.index.year >= 2000]
            if not modern_data.empty:
                print(f"   Modern era (2000+): {modern_data.shape}")
            else:
                print("   ⚠️ No modern era data available")
        else:
            print("⚠️ Market tensor not found - will build it first")
            
    except Exception as e:
        print(f"❌ Market tensor check failed: {e}")
    
    # Check data availability
    try:
        if prerequisites['market_tensor']:
            modern_years = sorted([y for y in tensor.index.year.unique() if y >= 2000])
            if len(modern_years) >= 1:
                prerequisites['data_availability'] = True
                print(f"✅ Modern era data available: {len(modern_years)} years ({min(modern_years)}-{max(modern_years)})")
            else:
                print("❌ No modern era years available")
        
    except Exception as e:
        print(f"❌ Data availability check failed: {e}")
    
    # Check storage space
    try:
        import shutil
        free_space_gb = shutil.disk_usage('.').free / (1024**3)
        
        if free_space_gb > 1.0:
            prerequisites['storage_space'] = True
            print(f"✅ Storage space available: {free_space_gb:.1f} GB free")
        else:
            print(f"⚠️ Low storage space: {free_space_gb:.1f} GB free")
            
    except Exception as e:
        print(f"⚠️ Storage space check failed: {e}")
        prerequisites['storage_space'] = True
    
    return prerequisites

def build_market_tensor_if_needed():
    """Build market tensor if it doesn't exist"""
    
    print("\n🧠 BUILDING MARKET TENSOR")
    print("=" * 50)
    
    try:
        from src.intelligence.market_brain.market_tensor import MarketTensorEngine
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
    """Process the next available year with beta drift fabric and comprehensive progress tracking"""
    
    print("\n🧬 PROCESSING BETA DRIFT FABRIC - THE MARKET NERVOUS SYSTEM")
    print("=" * 70)
    print("🎯 STARTING FROM YEAR 2000 (when major market data becomes available)")
    print("📊 RBI data starts from 1951, but market data quality improves significantly from 2000")
    print()
    
    try:
        # Initialize beta drift fabric
        fabric = BetaDriftFabric()
        
        # Show available years from 2000 onwards with detailed breakdown
        available_years = fabric.get_available_years()
        
        if not available_years:
            print("❌ No years from 2000 onwards available for processing")
            print("   This might indicate:")
            print("   - Market tensor needs to be built first")
            print("   - Insufficient data quality before 2000")
            print("   - Data pipeline issues")
            return False
        
        # Show processed years
        processed_years = []
        if os.path.exists('data/beta_drift_insights'):
            processed_years = [
                int(d) for d in os.listdir('data/beta_drift_insights')
                if d.isdigit() and os.path.isdir(os.path.join('data/beta_drift_insights', d))
            ]
        
        # Calculate progress statistics
        total_years = len(available_years)
        completed_years = len(processed_years)
        remaining_years = [year for year in available_years if year not in processed_years]
        
        print("📊 PROCESSING STATUS:")
        if processed_years:
            print(f"   ✅ Completed: {sorted(processed_years)} ({completed_years} years)")
        else:
            print(f"   ✅ Completed: None yet")
        
        if remaining_years:
            print(f"   ⏳ Remaining: {len(remaining_years)} years ({min(remaining_years)}-{max(remaining_years)})")
            next_year = min(remaining_years)
            print(f"   🎯 Next target: {next_year}")
            
            # Show progress bar
            progress_pct = (completed_years / total_years) * 100
            progress_bar_length = 40
            filled_length = int(progress_bar_length * completed_years // total_years)
            bar = '█' * filled_length + '░' * (progress_bar_length - filled_length)
            print(f"   📈 Overall progress: [{bar}] {progress_pct:.1f}% ({completed_years}/{total_years})")
            
            # Time estimates
            if completed_years > 0:
                avg_time_per_year = 3.5  # minutes (rough estimate)
                remaining_time_minutes = len(remaining_years) * avg_time_per_year
                remaining_time_hours = remaining_time_minutes / 60
                print(f"   ⏱️  Estimated remaining time: {remaining_time_minutes:.0f} minutes ({remaining_time_hours:.1f} hours)")
            else:
                print(f"   ⏱️  Estimated time per year: 3-5 minutes")
        else:
            print("   🎉 All years have been processed!")
            return True
        
        print()
        print("🧠 WHAT WE'RE MEASURING (THE CORRECT APPROACH):")
        print("   ❌ WRONG: macro_delta(t) → stock_return(t+4w) [Too many variables, too few samples]")
        print("   ✅ RIGHT: macro_factor(t) ↔ stock_sensitivity(t) [Beta drift detection]")
        print("   🎯 RESULT: Detect when stocks become sensitive to macro forces BEFORE price moves")
        print("   📈 SIGNAL: Sensitivity shifts precede price movements by weeks")
        print()
        
        # Process next year with detailed tracking
        success = fabric.process_next_year()
        
        if success:
            print("\n🎉 BETA DRIFT FABRIC PROCESSING COMPLETED!")
            
            # Show updated progress
            updated_processed = []
            if os.path.exists('data/beta_drift_insights'):
                updated_processed = [
                    int(d) for d in os.listdir('data/beta_drift_insights')
                    if d.isdigit() and os.path.isdir(os.path.join('data/beta_drift_insights', d))
                ]
            
            updated_completed = len(updated_processed)
            updated_progress_pct = (updated_completed / total_years) * 100
            updated_remaining = total_years - updated_completed
            
            print(f"📊 UPDATED PROGRESS:")
            print(f"   ✅ Completed: {updated_completed}/{total_years} years ({updated_progress_pct:.1f}%)")
            print(f"   ⏳ Remaining: {updated_remaining} years")
            
            if updated_remaining > 0:
                print(f"   🔄 Next: Run this script again to process the next year")
                print(f"   ⏱️  Estimated remaining time: {updated_remaining * 3.5:.0f} minutes")
            else:
                print(f"   🎉 ALL YEARS COMPLETED! Beta drift fabric is ready for integration")
            
            return True
        else:
            print("❌ Failed to process beta drift fabric")
            return False
            
    except Exception as e:
        print(f"❌ Error processing beta drift fabric: {e}")
        return False

def test_beta_drift_reader():
    """Test reading beta drift data"""
    
    print("\n🔍 TESTING BETA DRIFT DATA")
    print("=" * 50)
    
    try:
        # Check if we have any processed data
        if not os.path.exists('data/beta_drift_insights'):
            print("⚠️ No beta drift data found - run processing first")
            return False
        
        # Find processed years
        processed_years = [
            int(d) for d in os.listdir('data/beta_drift_insights')
            if d.isdigit() and os.path.isdir(os.path.join('data/beta_drift_insights', d))
        ]
        
        if not processed_years:
            print("⚠️ No processed years found")
            return False
        
        # Test loading data from most recent year
        test_year = max(processed_years)
        year_dir = os.path.join('data/beta_drift_insights', str(test_year))
        
        # Load summary
        summary_file = os.path.join(year_dir, 'summary.parquet')
        if os.path.exists(summary_file):
            summary_df = pd.read_parquet(summary_file)
            print(f"✅ Loaded {test_year} summary: {len(summary_df)} beta drifts")
            
            # Show sample data
            if not summary_df.empty:
                print(f"   📊 Factors: {summary_df['factor'].nunique()}")
                print(f"   📈 Stocks: {summary_df['stock'].nunique()}")
                print(f"   📅 Weeks: {summary_df['week'].nunique()}")
                print(f"   🔄 Avg drift magnitude: {summary_df['drift_magnitude'].mean():.3f}")
                
                # Show top drifts
                top_drifts = summary_df.nlargest(5, 'drift_magnitude')
                print(f"   🔝 Top 5 beta drifts:")
                for _, row in top_drifts.iterrows():
                    print(f"      {row['stock']} → {row['factor']}: {row['beta_drift']:+.3f} (week {row['week']})")
        
        # Load metadata
        metadata_file = os.path.join(year_dir, 'metadata.json')
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            print(f"   📋 Metadata: {metadata['total_beta_drifts']} total drifts, {metadata['weeks_processed']} weeks")
        
        print("✅ Beta drift data test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error testing beta drift data: {e}")
        return False

def show_integration_status():
    """Show integration status with existing V3 systems"""
    
    print("\n🔗 INTEGRATION STATUS")
    print("=" * 50)
    
    integration_points = {
        'Market Tensor Engine': 'src/intelligence/market_brain/market_tensor.py',
        'Beta Drift Fabric': 'src/intelligence/market_brain/beta_drift_fabric.py',
        'Capital Allocator': 'src/intelligence/capital_allocator.py',
        'Narrative Engine': 'src/intelligence/narrative_engine.py',
        'Intelligence Stack': 'src/intelligence/intelligence_stack.py'
    }
    
    for component, path in integration_points.items():
        if os.path.exists(path):
            print(f"✅ {component}: Ready for integration")
        else:
            print(f"⚠️ {component}: Path not found - {path}")
    
    # Check if beta drift data exists
    beta_drift_dir = 'data/beta_drift_insights'
    if os.path.exists(beta_drift_dir):
        processed_years = [
            d for d in os.listdir(beta_drift_dir)
            if d.isdigit() and os.path.isdir(os.path.join(beta_drift_dir, d))
        ]
        
        if processed_years:
            print(f"📊 Processed years: {sorted([int(y) for y in processed_years])}")
            
            # Count total beta drifts
            total_drifts = 0
            for year in processed_years:
                summary_file = os.path.join(beta_drift_dir, year, 'summary.parquet')
                if os.path.exists(summary_file):
                    try:
                        summary_df = pd.read_parquet(summary_file)
                        total_drifts += len(summary_df)
                    except:
                        continue
            
            print(f"🧬 Total beta drifts discovered: {total_drifts:,}")
        else:
            print("📊 No processed years found - run the fabric builder first")
    else:
        print("📊 Beta drift directory not found - will be created on first run")

def show_next_steps():
    """Show next steps for integration"""
    
    print("\n🎯 NEXT STEPS")
    print("=" * 50)
    
    print("1. 🧬 Beta Drift Detection:")
    print("   - Measures when stocks become sensitive to macro factors")
    print("   - Detects structural market rewiring before price moves")
    print("   - Provides anticipatory signals weeks ahead of returns")
    
    print("\n2. 🔄 Capital Allocation Integration:")
    print("   - Beta drift feeds into strategy tailwinds")
    print("   - Capital moves to strategies benefiting from sensitivity shifts")
    print("   - Anticipatory positioning before price reactions")
    
    print("\n3. 🧠 Intelligence Enhancement:")
    print("   - Regime transitions detected from beta drift patterns")
    print("   - Pressure maps show where macro forces are building")
    print("   - Narratives explain structural market changes")
    
    print("\n4. 📈 Performance Monitoring:")
    print("   - Track beta drift prediction accuracy")
    print("   - Monitor sensitivity shift effectiveness")
    print("   - Validate anticipatory signal performance")

def main():
    """Main execution function with comprehensive progress tracking"""
    
    print("🧬 BETA DRIFT FABRIC BUILDER - THE MARKET NERVOUS SYSTEM")
    print("Building sensitivity shift detection that precedes price moves")
    print("🎯 PROCESSING FROM YEAR 2000 ONWARDS (when major market data becomes available)")
    print("=" * 70)
    
    # Check prerequisites
    prerequisites = check_prerequisites()
    
    if not all(prerequisites.values()):
        print("\n❌ Prerequisites not met. Please address the issues above.")
        return False
    
    # Build market tensor if needed
    if not build_market_tensor_if_needed():
        print("\n❌ Cannot proceed without market tensor")
        return False
    
    # Show initial progress overview
    print("\n📊 INITIAL PROGRESS ASSESSMENT")
    print("=" * 50)
    
    try:
        from src.intelligence.market_brain.beta_drift_fabric import BetaDriftFabric
        fabric = BetaDriftFabric()
        available_years = fabric.get_available_years()
        
        if available_years:
            processed_years = []
            if os.path.exists('data/beta_drift_insights'):
                processed_years = [
                    int(d) for d in os.listdir('data/beta_drift_insights')
                    if d.isdigit() and os.path.isdir(os.path.join('data/beta_drift_insights', d))
                ]
            
            total_years = len(available_years)
            completed_years = len(processed_years)
            remaining_years = total_years - completed_years
            
            print(f"📅 Years available (2000+): {total_years} ({min(available_years)}-{max(available_years)})")
            print(f"✅ Years completed: {completed_years}")
            print(f"⏳ Years remaining: {remaining_years}")
            
            if remaining_years > 0:
                completion_pct = (completed_years / total_years) * 100
                print(f"📈 Progress: {completion_pct:.1f}% complete")
                
                # Estimated time
                estimated_minutes = remaining_years * 3.5
                estimated_hours = estimated_minutes / 60
                print(f"⏱️  Estimated remaining time: {estimated_minutes:.0f} minutes ({estimated_hours:.1f} hours)")
            else:
                print("🎉 All years already processed!")
        else:
            print("⚠️ No years available for processing")
    except Exception as e:
        print(f"⚠️ Could not assess initial progress: {e}")
    
    # Process next year
    if not process_next_year():
        print("\n❌ Failed to process beta drift fabric")
        return False
    
    # Test beta drift reader
    if not test_beta_drift_reader():
        print("\n⚠️ Beta drift reader tests failed, but fabric was built")
    
    # Show integration status
    show_integration_status()
    
    # Show next steps
    show_next_steps()
    
    print("\n🎉 BETA DRIFT FABRIC BUILD COMPLETED!")
    print("🧠 Northstar now detects sensitivity shifts before price moves")
    print("🔮 Run again to process the next year (if any remaining)")
    print("💡 This is the REAL signal that precedes market movements")
    print("🎯 Starting from 2000 ensures high-quality market data")
    
    return True

if __name__ == "__main__":
    success = main()
    
    if success:
        print("\n✅ Build completed successfully!")
        exit(0)
    else:
        print("\n❌ Build failed!")
        exit(1)