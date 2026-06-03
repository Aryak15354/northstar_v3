#!/usr/bin/env python3
"""
🧬 PROCESS ALL BETA DRIFT YEARS - COMPLETE 2000-2025 COVERAGE
Process all years from 2000-2025 for beta drift analysis

This script ensures we have complete coverage of all years in the range,
not just the sparse years that were previously processed.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import glob
from datetime import datetime
import json
from src.intelligence.market_brain.beta_drift_fabric import BetaDriftFabric

def get_all_target_years():
    """Get all years from 2000-2025 that we want to process"""
    return list(range(2000, 2026))  # 2000 to 2025 inclusive

def get_processed_years():
    """Get years that have already been processed"""
    processed_years = []
    
    if os.path.exists('data/beta_drift_insights'):
        processed_years = [
            int(d) for d in os.listdir('data/beta_drift_insights')
            if d.isdigit() and os.path.isdir(os.path.join('data/beta_drift_insights', d))
        ]
    
    return sorted(processed_years)

def check_data_availability():
    """Check what years actually have data available"""
    
    print("🔍 CHECKING DATA AVAILABILITY FOR ALL YEARS 2000-2025")
    print("=" * 60)
    
    # Load market tensor to check date coverage
    fabric = BetaDriftFabric()
    tensor = fabric.load_market_tensor()
    
    if tensor.empty:
        print("❌ No market tensor available")
        return []
    
    # Get all years in tensor
    tensor_years = sorted(tensor.index.year.unique())
    print(f"📊 Market tensor years: {min(tensor_years)}-{max(tensor_years)} ({len(tensor_years)} years)")
    
    # Check stock data availability by sampling files
    stock_files = glob.glob(os.path.join('data/raw/prices_daily_extended/', '*.csv'))
    if not stock_files:
        stock_files = glob.glob(os.path.join('data/raw/prices_daily/', '*.csv'))
    
    stock_years = set()
    if stock_files:
        print(f"📈 Found {len(stock_files)} stock files")
        
        # Sample multiple files to get comprehensive year coverage
        sample_files = stock_files[:10]  # Check first 10 files
        
        for file_path in sample_files:
            try:
                # Read just the date column to check range
                df = pd.read_csv(file_path, usecols=['Date'], parse_dates=['Date'])
                if not df.empty:
                    file_years = df['Date'].dt.year.unique()
                    stock_years.update(file_years)
            except Exception as e:
                continue
        
        if stock_years:
            print(f"📅 Stock data years: {min(stock_years)}-{max(stock_years)} ({len(stock_years)} years)")
        else:
            print("⚠️ Could not determine stock data year range")
    
    # Find years that have both tensor and stock data
    target_years = get_all_target_years()
    available_years = []
    
    for year in target_years:
        has_tensor = year in tensor_years
        has_stocks = year in stock_years if stock_years else has_tensor
        
        if has_tensor and has_stocks:
            # Check if tensor has sufficient data for this year
            year_data = tensor[tensor.index.year == year]
            if len(year_data) >= fabric.config['min_observations']:
                available_years.append(year)
        
        status = "✅" if year in available_years else "❌"
        tensor_status = "📊" if has_tensor else "❌"
        stock_status = "📈" if has_stocks else "❌"
        
        print(f"   {status} {year}: Tensor {tensor_status} | Stocks {stock_status}")
    
    print(f"\n📋 SUMMARY:")
    print(f"   🎯 Target years (2000-2025): {len(target_years)}")
    print(f"   ✅ Available years: {len(available_years)} ({min(available_years) if available_years else 'None'}-{max(available_years) if available_years else 'None'})")
    print(f"   ❌ Missing years: {len(target_years) - len(available_years)}")
    
    if len(available_years) < len(target_years):
        missing_years = [y for y in target_years if y not in available_years]
        print(f"   📋 Missing: {missing_years}")
    
    return available_years

def process_all_missing_years():
    """Process all missing years from 2000-2025"""
    
    print("\n🧬 PROCESSING ALL MISSING YEARS 2000-2025")
    print("=" * 60)
    
    # Get current status
    target_years = get_all_target_years()
    processed_years = get_processed_years()
    available_years = check_data_availability()
    
    if not available_years:
        print("❌ No years available for processing")
        return False
    
    # Find years that need processing
    missing_years = [year for year in available_years if year not in processed_years]
    
    if not missing_years:
        print("🎉 All available years have already been processed!")
        print(f"   ✅ Processed: {processed_years}")
        return True
    
    print(f"\n📊 PROCESSING STATUS:")
    print(f"   🎯 Target years: {len(target_years)} (2000-2025)")
    print(f"   ✅ Available: {len(available_years)} years")
    print(f"   ✅ Already processed: {len(processed_years)} years")
    print(f"   ⏳ Need processing: {len(missing_years)} years")
    print(f"   📋 Missing years: {missing_years}")
    
    # Estimate total time
    estimated_minutes = len(missing_years) * 3.5  # ~3.5 minutes per year
    estimated_hours = estimated_minutes / 60
    
    print(f"\n⏱️  ESTIMATED TIME:")
    print(f"   Per year: ~3-5 minutes")
    print(f"   Total remaining: ~{estimated_minutes:.0f} minutes ({estimated_hours:.1f} hours)")
    
    # Process each missing year
    fabric = BetaDriftFabric()
    successful_years = []
    failed_years = []
    
    for i, year in enumerate(missing_years):
        progress = (i + 1) / len(missing_years) * 100
        
        print(f"\n🎯 PROCESSING YEAR {year} ({i+1}/{len(missing_years)} - {progress:.1f}%)")
        print("-" * 50)
        
        try:
            success = fabric.build_year_beta_fabric(year)
            
            if success:
                successful_years.append(year)
                print(f"✅ Year {year} completed successfully")
            else:
                failed_years.append(year)
                print(f"❌ Year {year} failed")
                
        except Exception as e:
            failed_years.append(year)
            print(f"❌ Year {year} failed with error: {e}")
    
    # Final summary
    print(f"\n🎉 BATCH PROCESSING COMPLETED!")
    print("=" * 60)
    print(f"📊 RESULTS:")
    print(f"   ✅ Successful: {len(successful_years)} years")
    print(f"   ❌ Failed: {len(failed_years)} years")
    
    if successful_years:
        print(f"   🎯 Successfully processed: {successful_years}")
    
    if failed_years:
        print(f"   ⚠️ Failed years: {failed_years}")
    
    # Check final status
    final_processed = get_processed_years()
    final_coverage = len(final_processed) / len(target_years) * 100
    
    print(f"\n📈 FINAL COVERAGE:")
    print(f"   🎯 Target years (2000-2025): {len(target_years)}")
    print(f"   ✅ Total processed: {len(final_processed)} ({final_coverage:.1f}%)")
    print(f"   📋 Processed years: {final_processed}")
    
    if len(final_processed) == len(available_years):
        print(f"   🎉 COMPLETE! All available years processed")
        return True
    else:
        remaining = len(available_years) - len(final_processed)
        print(f"   ⏳ Still need: {remaining} more years")
        return len(successful_years) > 0

def main():
    """Main execution function"""
    
    print("🧬 COMPLETE BETA DRIFT PROCESSING 2000-2025")
    print("Processing ALL years in the target range")
    print("=" * 70)
    
    # Check current status
    target_years = get_all_target_years()
    processed_years = get_processed_years()
    
    print(f"🎯 TARGET: Process all years from 2000-2025 ({len(target_years)} years)")
    print(f"✅ CURRENT: {len(processed_years)} years already processed")
    
    if processed_years:
        print(f"   📋 Already done: {processed_years}")
    
    remaining_count = len(target_years) - len(processed_years)
    print(f"⏳ REMAINING: {remaining_count} years to process")
    
    if remaining_count == 0:
        print("🎉 All target years already processed!")
        return True
    
    # Process all missing years
    success = process_all_missing_years()
    
    if success:
        print(f"\n✅ BETA DRIFT PROCESSING COMPLETED!")
        print(f"   🧬 Market nervous system now covers maximum available range")
        print(f"   🎯 Ready for anticipatory intelligence integration")
    else:
        print(f"\n⚠️ Some years failed to process")
        print(f"   🔄 Run again to retry failed years")
    
    return success

if __name__ == "__main__":
    success = main()
    
    if success:
        print("\n🎉 SUCCESS: Beta drift processing completed!")
        exit(0)
    else:
        print("\n⚠️ PARTIAL: Some processing completed, but not all years")
        exit(1)