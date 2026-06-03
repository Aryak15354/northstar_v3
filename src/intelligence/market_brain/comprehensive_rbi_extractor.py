#!/usr/bin/env python3
"""
🏛️ COMPREHENSIVE RBI DATA EXTRACTOR - NORTHSTAR V3 MARKET BRAIN
Complete extraction of all available RBI economic variables

This module extracts ALL 112+ variables from RBI CSV files using the unified
RBI Data Handler for consistent data architecture.

Integration with Market Brain:
- Provides comprehensive macro-economic foundation
- Feeds into Market Tensor as monetary/credit forces
- Enhances regime detection and causality analysis
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Import the unified RBI data handler
import sys
import os
# Add the project root to Python path
from src.utils.rbi_data_handler import rbi_handler

class ComprehensiveRBIExtractor:
    """
    Comprehensive RBI Data Extractor
    
    Uses the unified RBI Data Handler for consistent data processing.
    Extracts all available economic variables from RBI CSV files.
    """
    
    def __init__(self):
        self.name = "Comprehensive RBI Extractor"
        self.version = "2.0"  # Updated to use RBI Data Handler
        
        # RBI file paths
        self.rbi_files = {
            'daily_other': 'data/macro/raw/rbi_daily_other.csv',
            'weekly_core': 'data/macro/raw/rbi_weekly_core.csv',
            'weekly_other': 'data/macro/raw/rbi_weekly_other.csv',
            'fortnightly_core': 'data/macro/raw/rbi_fortnightly_core.csv',
            'monthly_core': 'data/macro/raw/rbi_monthly_core.csv',
            'monthly_other': 'data/macro/raw/rbi_monthly_other.csv',
            'quarterly_core': 'data/macro/raw/rbi_quarterly_core.csv',
            'quarterly_other': 'data/macro/raw/rbi_quarterly_other.csv'
        }
        
        # Output paths
        self.output_paths = {
            'comprehensive_rbi': 'data/macro/comprehensive_rbi_data.parquet',
            'rbi_metadata': 'data/macro/rbi_variables_metadata.json',
            'yields_enhanced': 'data/macro/yields_enhanced.csv',
            'macro_indicators': 'data/macro/macro_indicators.parquet'
        }
        
        # Variable categories for organization
        self.categories = {
            'interest_rates_yields': [],
            'market_indices': [],
            'monetary_policy': [],
            'foreign_exchange': [],
            'banking_financial': [],
            'trade_external': [],
            'investment_flows': [],
            'economic_indicators': []
        }
    
    def categorize_variables(self, all_variables):
        """Categorize all extracted variables by type"""
        
        print("   🏷️ Categorizing variables...")
        
        categories = {
            'interest_rates_yields': [],
            'market_indices': [],
            'monetary_policy': [],
            'foreign_exchange': [],
            'banking_financial': [],
            'trade_external': [],
            'investment_flows': [],
            'economic_indicators': []
        }
        
        for var in all_variables:
            var_lower = var.lower()
            
            if any(term in var_lower for term in ['rate', 'yield', 'repo', 'msf', 'bank rate', 'treasury', 'bill']):
                categories['interest_rates_yields'].append(var)
            elif any(term in var_lower for term in ['index', 'cpi', 'wpi', 'iip', 'production']):
                categories['market_indices'].append(var)
            elif any(term in var_lower for term in ['policy', 'crr', 'slr', 'reserve', 'facility']):
                categories['monetary_policy'].append(var)
            elif any(term in var_lower for term in ['exchange', 'forex', 'currency', 'dollar', 'rupee', 'fcnr']):
                categories['foreign_exchange'].append(var)
            elif any(term in var_lower for term in ['credit', 'loan', 'deposit', 'banking', 'commercial', 'certificate']):
                categories['banking_financial'].append(var)
            elif any(term in var_lower for term in ['trade', 'export', 'import', 'balance', 'external']):
                categories['trade_external'].append(var)
            elif any(term in var_lower for term in ['fdi', 'fii', 'investment', 'flow', 'portfolio', 'inflow']):
                categories['investment_flows'].append(var)
            else:
                categories['economic_indicators'].append(var)
        
        # Display categorization results
        for category, variables in categories.items():
            if variables:
                print(f"      📊 {category.replace('_', ' ').title()}: {len(variables)} variables")
        
        return categories
    
    def extract_all_rbi_data(self):
        """Extract all available RBI data from all CSV files using unified handler"""
        
        print("🏛️ COMPREHENSIVE RBI DATA EXTRACTION")
        print("=" * 60)
        
        all_dataframes = {}
        extraction_summary = {}
        
        # Process each RBI file using the unified handler
        for file_key, file_path in self.rbi_files.items():
            print(f"   🔄 Processing {file_key}...")
            
            if os.path.exists(file_path):
                df = rbi_handler.load_rbi_file(file_path, file_key)
                if not df.empty:
                    all_dataframes[file_key] = df
                    summary = rbi_handler.get_rbi_data_summary(df)
                    extraction_summary[file_key] = summary
                    print(f"      ✅ Extracted {summary['shape'][1]} variables, {summary['shape'][0]} periods")
                    print(f"      📅 Date range: {summary['date_range'][0]} to {summary['date_range'][1]}")
                else:
                    extraction_summary[file_key] = {'status': 'no_data'}
            else:
                print(f"   ❌ File not found: {file_key}")
                extraction_summary[file_key] = {'status': 'missing'}
        
        if not all_dataframes:
            print("❌ No RBI data could be extracted")
            return pd.DataFrame(), {}
        
        # Align all data using the unified handler
        print(f"\n🔗 Aligning data from {len(all_dataframes)} files...")
        comprehensive_rbi = rbi_handler.align_rbi_dataframes(all_dataframes, target_frequency='W')
        
        if comprehensive_rbi.empty:
            print("❌ No data could be aligned")
            return pd.DataFrame(), {}
        
        print(f"   ✅ Combined dataset: {comprehensive_rbi.shape}")
        print(f"   📅 Date range: {comprehensive_rbi.index[0].date()} to {comprehensive_rbi.index[-1].date()}")
        
        # Categorize variables
        categories = self.categorize_variables(list(comprehensive_rbi.columns))
        
        return comprehensive_rbi, {
            'extraction_summary': extraction_summary,
            'categories': categories,
            'total_variables': len(comprehensive_rbi.columns),
            'total_periods': len(comprehensive_rbi),
            'date_range': [str(comprehensive_rbi.index[0].date()), str(comprehensive_rbi.index[-1].date())]
        }
    
    def create_enhanced_yield_curve(self, comprehensive_data):
        """Create enhanced yield curve data from comprehensive RBI data"""
        
        print("\n💰 CREATING ENHANCED YIELD CURVE")
        print("-" * 40)
        
        # Extract yield-related variables
        yield_columns = []
        for col in comprehensive_data.columns:
            col_lower = col.lower()
            if any(term in col_lower for term in ['yield', 'rate', 'repo', 'treasury', 'bill']):
                yield_columns.append(col)
        
        if yield_columns:
            yield_data = comprehensive_data[yield_columns].copy()
            
            # Clean column names for yield curve and handle duplicates
            clean_names = {}
            used_names = set()
            
            for col in yield_columns:
                if '91-day' in col.lower() or '3m' in col.lower():
                    clean_name = '3M'
                elif '182-day' in col.lower() or '6m' in col.lower():
                    clean_name = '6M'
                elif '364-day' in col.lower() or '1y' in col.lower():
                    clean_name = '1Y'
                elif '10-year' in col.lower() or '10y' in col.lower():
                    clean_name = '10Y'
                elif 'repo' in col.lower() and 'policy' in col.lower():
                    clean_name = 'Policy_Rate'
                elif 'repo' in col.lower() and 'reverse' not in col.lower():
                    clean_name = 'Repo_Rate'
                elif 'reverse repo' in col.lower():
                    clean_name = 'Reverse_Repo'
                elif 'bank rate' in col.lower():
                    clean_name = 'Bank_Rate'
                elif 'msf' in col.lower():
                    clean_name = 'MSF_Rate'
                else:
                    # Keep original name but clean it
                    clean_name = col.replace('weekly_core_', '').replace('daily_other_', '').replace('monthly_core_', '')
                    clean_name = clean_name.replace(' ', '_').replace('(', '').replace(')', '').replace('%', 'pct')
                
                # Handle duplicates by adding suffix
                original_clean_name = clean_name
                counter = 1
                while clean_name in used_names:
                    clean_name = f"{original_clean_name}_{counter}"
                    counter += 1
                
                clean_names[col] = clean_name
                used_names.add(clean_name)
            
            yield_data = yield_data.rename(columns=clean_names)
            
            # Save enhanced yield data with proper date column
            os.makedirs(os.path.dirname(self.output_paths['yields_enhanced']), exist_ok=True)
            yield_data_csv = yield_data.reset_index()
            yield_data_csv = yield_data_csv.rename(columns={yield_data_csv.columns[0]: 'Date'})  # Ensure first column is 'Date'
            yield_data_csv.to_csv(self.output_paths['yields_enhanced'], index=False)
            
            print(f"   ✅ Enhanced yield curve: {yield_data.shape}")
            print(f"   📊 Yield series: {list(yield_data.columns)}")
            print(f"   📊 No duplicate column names: {len(set(yield_data.columns)) == len(yield_data.columns)}")
            
            return yield_data
        else:
            print("   ⚠️ No yield data found")
            return pd.DataFrame()
    
    def save_comprehensive_data(self, comprehensive_data, metadata):
        """Save comprehensive RBI data and metadata"""
        
        print("\n💾 SAVING COMPREHENSIVE RBI DATA")
        print("-" * 40)
        
        try:
            # Ensure output directories exist
            for path in self.output_paths.values():
                os.makedirs(os.path.dirname(path), exist_ok=True)
            
            # Save main comprehensive dataset
            comprehensive_data.to_parquet(self.output_paths['comprehensive_rbi'])
            print(f"   ✅ Comprehensive data: {self.output_paths['comprehensive_rbi']}")
            
            # Save metadata
            metadata['created_at'] = datetime.now().isoformat()
            metadata['extractor_version'] = self.version
            
            with open(self.output_paths['rbi_metadata'], 'w') as f:
                json.dump(metadata, f, indent=2)
            print(f"   ✅ Metadata: {self.output_paths['rbi_metadata']}")
            
            # Create macro indicators subset (most important variables)
            important_vars = []
            for col in comprehensive_data.columns:
                col_lower = col.lower()
                if any(term in col_lower for term in [
                    'policy', 'repo', 'yield', 'cpi', 'wpi', 'iip', 'credit', 
                    'deposit', 'reserve', 'exchange', 'export', 'import', 'fdi'
                ]):
                    important_vars.append(col)
            
            if important_vars:
                macro_indicators = comprehensive_data[important_vars].copy()
                macro_indicators.to_parquet(self.output_paths['macro_indicators'])
                print(f"   ✅ Macro indicators: {self.output_paths['macro_indicators']} ({len(important_vars)} key variables)")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Error saving data: {e}")
            return False
    
    def run_comprehensive_extraction(self):
        """Run complete RBI data extraction process"""
        
        print("🏛️ COMPREHENSIVE RBI DATA EXTRACTION SYSTEM")
        print("=" * 70)
        
        # Extract all RBI data
        comprehensive_data, metadata = self.extract_all_rbi_data()
        
        if comprehensive_data.empty:
            print("❌ No RBI data could be extracted")
            return False
        
        # Create enhanced yield curve
        yield_data = self.create_enhanced_yield_curve(comprehensive_data)
        
        # Save all data
        save_success = self.save_comprehensive_data(comprehensive_data, metadata)
        
        # Summary
        print(f"\n🎯 EXTRACTION SUMMARY")
        print("=" * 40)
        print(f"Total Variables: {metadata['total_variables']}")
        print(f"Total Periods: {metadata['total_periods']}")
        print(f"Date Range: {metadata['date_range'][0]} to {metadata['date_range'][1]}")
        
        print(f"\n📊 Variable Categories:")
        for category, variables in metadata['categories'].items():
            if variables:
                print(f"   {category.replace('_', ' ').title()}: {len(variables)}")
        
        print(f"\n💾 Output Files:")
        print(f"   📈 Comprehensive RBI Data: {comprehensive_data.shape}")
        print(f"   💰 Enhanced Yield Curve: {yield_data.shape if not yield_data.empty else 'N/A'}")
        print(f"   📊 Macro Indicators: Available")
        
        if save_success:
            print(f"\n🎉 Comprehensive RBI extraction completed successfully!")
            print(f"   All {metadata['total_variables']} variables extracted and categorized")
            return True
        else:
            print(f"\n⚠️ Extraction completed with some issues")
            return False

def main():
    """Run comprehensive RBI data extraction"""
    
    extractor = ComprehensiveRBIExtractor()
    success = extractor.run_comprehensive_extraction()
    
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)