#!/usr/bin/env python3
"""
RBI Data Processor - Clean and Convert XLSX to CSV
Handles the data processing part of RBI data collection using unified RBI handler
"""
import os
import pandas as pd
import shutil
from datetime import datetime
from pathlib import Path
import hashlib
import json

# Import the unified RBI data handler
import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.utils.rbi_data_handler import rbi_handler

class RBIProcessor:
    """RBI data processor for XLSX to CSV conversion"""
    
    def __init__(self, raw_dir="data/macro/raw", archive_dir="data/macro/archive", metadata_dir="data/macro/metadata"):
        self.raw_dir = raw_dir
        self.archive_dir = archive_dir
        self.metadata_dir = metadata_dir
        
        # Create directories
        for dir_path in [self.raw_dir, self.archive_dir, self.metadata_dir]:
            os.makedirs(dir_path, exist_ok=True)
        
        self.metadata_file = os.path.join(self.metadata_dir, "rbi_data_metadata.json")
        self.metadata = self.load_metadata()
    
    def load_metadata(self):
        """Load existing file metadata"""
        if os.path.exists(self.metadata_file):
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_metadata(self):
        """Save file metadata"""
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2, default=str)
    
    def get_file_hash(self, filepath):
        """Calculate file hash for change detection"""
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def detect_changes(self, filepath):
        """Detect if file has changed since last run"""
        filename = os.path.basename(filepath)
        current_hash = self.get_file_hash(filepath)
        
        if filename in self.metadata:
            old_hash = self.metadata[filename].get('hash')
            return old_hash != current_hash
        return True  # New file
    
    def generate_csv_name(self, df, sheet_name, source_type, index):
        """Generate intelligent CSV names based on content analysis"""
        
        # Clean sheet name
        clean_sheet = sheet_name.lower().replace(' ', '_').replace('-', '_').replace('(', '').replace(')', '')
        
        # Content analysis - look at column names and first few rows
        content_str = ' '.join([str(col) for col in df.columns]).lower()
        if not df.empty:
            content_str += ' ' + ' '.join([str(val) for val in df.iloc[0] if pd.notna(val)]).lower()
        
        # Frequency detection
        frequency = ""
        if any(freq in clean_sheet or freq in content_str for freq in ['daily']):
            frequency = "_daily"
        elif any(freq in clean_sheet or freq in content_str for freq in ['weekly']):
            frequency = "_weekly"
        elif any(freq in clean_sheet or freq in content_str for freq in ['monthly']):
            frequency = "_monthly"
        elif any(freq in clean_sheet or freq in content_str for freq in ['quarterly']):
            frequency = "_quarterly"
        elif any(freq in clean_sheet or freq in content_str for freq in ['annual', 'yearly']):
            frequency = "_annual"
        
        # Content-based categorization
        category_patterns = {
            'fx_reserves': ['foreign', 'exchange', 'reserve', 'forex', 'fx'],
            'policy_rates': ['repo', 'rate', 'policy', 'crr', 'slr', 'mclr'],
            'exchange_rates': ['usd', 'inr', 'eur', 'gbp', 'jpy', 'currency'],
            'inflation': ['cpi', 'wpi', 'inflation', 'price', 'consumer'],
            'gdp_growth': ['gdp', 'gross', 'domestic', 'product', 'growth'],
            'money_supply': ['money', 'supply', 'm1', 'm2', 'm3', 'currency'],
            'banking': ['credit', 'deposit', 'bank', 'lending', 'npa'],
            'equity_indices': ['nifty', 'sensex', 'bse', 'nse', 'index'],
            'government_securities': ['gsec', 'government', 'securities', 'bond'],
            'treasury_bills': ['treasury', 'bill', 'tbill', '91', '182', '364'],
            'trade_balance': ['export', 'import', 'trade', 'balance', 'merchandise'],
            'fiscal_deficit': ['fiscal', 'deficit', 'revenue', 'expenditure'],
            'industrial_production': ['iip', 'industrial', 'production', 'manufacturing']
        }
        
        # Find best matching category
        best_category = None
        max_score = 0
        
        for category, keywords in category_patterns.items():
            score = sum(1 for keyword in keywords if keyword in content_str)
            if score > max_score:
                max_score = score
                best_category = category
        
        # Generate final name
        if best_category and max_score >= 2:
            return f"{source_type}_{best_category}{frequency}"
        elif len(clean_sheet) > 3 and clean_sheet not in ['sheet1', 'sheet2', 'sheet3']:
            return f"{source_type}_{clean_sheet[:25]}{frequency}"
        else:
            return f"{source_type}_sheet_{index + 1}{frequency}"
    
    def clean_dataframe(self, df):
        """Clean dataframe for better data quality"""
        # Remove completely empty rows and columns
        df = df.dropna(how='all').dropna(axis=1, how='all')
        
        # Clean column names
        df.columns = [str(col).strip() for col in df.columns]
        
        # Try to identify and parse date columns
        for col in df.columns:
            if 'date' in col.lower() or 'period' in col.lower() or 'time' in col.lower():
                try:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                except:
                    pass
        
        return df
    
    def convert_xlsx_to_csv(self, xlsx_path):
        """Convert XLSX to multiple CSVs with intelligent naming"""
        print(f"📊 Converting {os.path.basename(xlsx_path)}...")
        
        try:
            # Determine source type from filename
            filename = os.path.basename(xlsx_path).lower()
            if "50" in filename or "macro" in filename:
                source_type = "core_macro"
            else:
                source_type = "market_data"
            
            # Read all sheets
            xls_file = pd.ExcelFile(xlsx_path)
            converted_files = []
            
            print(f"   📋 Found {len(xls_file.sheet_names)} sheets to convert")
            
            for i, sheet_name in enumerate(xls_file.sheet_names):
                try:
                    df = pd.read_excel(xlsx_path, sheet_name=sheet_name)
                    
                    if df.empty:
                        print(f"   ⚠️  Skipping empty sheet: {sheet_name}")
                        continue
                    
                    # Generate intelligent name
                    csv_name = self.generate_csv_name(df, sheet_name, source_type, i)
                    csv_filename = f"{csv_name}.csv"
                    csv_path = os.path.join(self.raw_dir, csv_filename)
                    
                    # Handle duplicates by adding version numbers
                    counter = 1
                    original_csv_path = csv_path
                    while os.path.exists(csv_path):
                        name_part = os.path.splitext(original_csv_path)[0]
                        csv_path = f"{name_part}_v{counter}.csv"
                        csv_filename = os.path.basename(csv_path)
                        counter += 1
                    
                    # Clean and save CSV
                    df_clean = self.clean_dataframe(df)
                    df_clean.to_csv(csv_path, index=False)
                    converted_files.append(csv_filename)
                    
                    print(f"   📋 Sheet '{sheet_name}' → {csv_filename} ({len(df_clean)} rows)")
                    
                except Exception as e:
                    print(f"   ⚠️  Failed to convert sheet '{sheet_name}': {e}")
                    continue
            
            print(f"   ✅ Successfully converted {len(converted_files)} sheets")
            return converted_files
            
        except Exception as e:
            print(f"   ❌ Conversion failed: {e}")
            return []
    
    def detect_retrospective_changes(self, new_csv_path, old_csv_path):
        """
        Detect retrospective changes between new and existing CSV data
        Returns detailed change analysis
        """
        
        if not os.path.exists(old_csv_path):
            return {'type': 'new_file', 'changes': 0, 'details': []}
        
        try:
            # Load both datasets
            new_df = pd.read_csv(new_csv_path)
            old_df = pd.read_csv(old_csv_path)
            
            if new_df.empty or old_df.empty:
                return {'type': 'empty_data', 'changes': 0, 'details': []}
            
            # Find date/period column
            date_col = None
            for col in new_df.columns:
                if any(term in col.lower() for term in ['date', 'period', 'time']):
                    date_col = col
                    break
            
            if not date_col:
                return {'type': 'no_date_column', 'changes': 0, 'details': []}
            
            # Convert date columns to datetime
            try:
                new_df[date_col] = pd.to_datetime(new_df[date_col], errors='coerce')
                old_df[date_col] = pd.to_datetime(old_df[date_col], errors='coerce')
            except:
                return {'type': 'date_conversion_error', 'changes': 0, 'details': []}
            
            # Remove rows with invalid dates
            new_df = new_df.dropna(subset=[date_col])
            old_df = old_df.dropna(subset=[date_col])
            
            if new_df.empty or old_df.empty:
                return {'type': 'no_valid_dates', 'changes': 0, 'details': []}
            
            # Find common columns (excluding date)
            new_cols = set(new_df.columns) - {date_col}
            old_cols = set(old_df.columns) - {date_col}
            common_cols = new_cols.intersection(old_cols)
            
            if not common_cols:
                return {'type': 'no_common_columns', 'changes': len(new_cols), 'details': []}
            
            # Find overlapping periods
            new_periods = set(new_df[date_col])
            old_periods = set(old_df[date_col])
            overlap_periods = new_periods.intersection(old_periods)
            
            if not overlap_periods:
                return {'type': 'no_overlap', 'new_periods': len(new_periods), 'details': []}
            
            # Check for retrospective changes in overlapping periods
            changes_detected = 0
            change_details = []
            
            for period in sorted(overlap_periods):
                new_row = new_df[new_df[date_col] == period]
                old_row = old_df[old_df[date_col] == period]
                
                if len(new_row) == 1 and len(old_row) == 1:
                    for col in common_cols:
                        if col in new_row.columns and col in old_row.columns:
                            try:
                                new_val = new_row[col].iloc[0]
                                old_val = old_row[col].iloc[0]
                                
                                # Compare values (handle NaN)
                                if pd.notna(new_val) and pd.notna(old_val):
                                    if abs(float(new_val) - float(old_val)) > 0.001:  # Threshold for change
                                        changes_detected += 1
                                        change_details.append({
                                            'period': period.strftime('%Y-%m-%d'),
                                            'column': col,
                                            'old_value': float(old_val),
                                            'new_value': float(new_val),
                                            'change': float(new_val) - float(old_val),
                                            'change_pct': ((float(new_val) - float(old_val)) / float(old_val)) * 100 if float(old_val) != 0 else 0
                                        })
                                elif pd.notna(new_val) != pd.notna(old_val):
                                    # One is NaN, other is not
                                    changes_detected += 1
                                    change_details.append({
                                        'period': period.strftime('%Y-%m-%d'),
                                        'column': col,
                                        'old_value': old_val,
                                        'new_value': new_val,
                                        'change': 'na_change',
                                        'change_pct': 0
                                    })
                            except Exception as e:
                                continue
            
            return {
                'type': 'retrospective_analysis',
                'changes': changes_detected,
                'overlap_periods': len(overlap_periods),
                'new_periods': len(new_periods - old_periods),
                'details': change_details[:20]  # Limit to first 20 changes
            }
            
        except Exception as e:
            return {'type': 'analysis_error', 'error': str(e), 'changes': 0, 'details': []}
    
    def save_retrospective_changes(self, filename, change_analysis):
        """Save retrospective changes to a log file"""
        
        if change_analysis['changes'] == 0:
            return
        
        changes_dir = "data/macro/changes"
        os.makedirs(changes_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        changes_file = os.path.join(changes_dir, f"retrospective_changes_{timestamp}.json")
        
        change_log = {
            'timestamp': datetime.now().isoformat(),
            'filename': filename,
            'analysis': change_analysis
        }
        
        try:
            # Load existing changes log if it exists
            all_changes_file = os.path.join(changes_dir, "all_retrospective_changes.json")
            if os.path.exists(all_changes_file):
                with open(all_changes_file, 'r') as f:
                    all_changes = json.load(f)
            else:
                all_changes = []
            
            # Add new change log
            all_changes.append(change_log)
            
            # Keep only last 100 change logs
            all_changes = all_changes[-100:]
            
            # Save individual change file
            with open(changes_file, 'w') as f:
                json.dump(change_log, f, indent=2, default=str)
            
            # Save consolidated changes file
            with open(all_changes_file, 'w') as f:
                json.dump(all_changes, f, indent=2, default=str)
            
            print(f"   📊 Retrospective changes saved: {os.path.basename(changes_file)}")
            
        except Exception as e:
            print(f"   ⚠️ Error saving retrospective changes: {e}")

    def merge_with_existing(self, new_csv_path):
        """Merge new CSV with existing data if available"""
        filename = os.path.basename(new_csv_path)
        
        try:
            new_df = pd.read_csv(new_csv_path)
            
            # Check if file exists in metadata (has been processed before)
            if filename in self.metadata:
                # Create backup
                backup_path = os.path.join(self.archive_dir, f"{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.backup")
                if os.path.exists(new_csv_path):
                    shutil.copy2(new_csv_path, backup_path)
                
                # Detect retrospective changes
                change_analysis = self.detect_retrospective_changes(new_csv_path, backup_path)
                
                if change_analysis['changes'] > 0:
                    print(f"   🔍 Retrospective changes detected: {change_analysis['changes']} changes")
                    self.save_retrospective_changes(filename, change_analysis)
                
                try:
                    old_df = pd.read_csv(backup_path)
                    
                    # Find date columns for merging
                    date_cols = [col for col in new_df.columns 
                               if 'date' in col.lower() or 'period' in col.lower() or 'time' in col.lower()]
                    
                    if date_cols:
                        date_col = date_cols[0]
                        print(f"   🔄 Merging {filename} using date column: {date_col}")
                        
                        # Convert dates
                        new_df[date_col] = pd.to_datetime(new_df[date_col], errors='coerce')
                        old_df[date_col] = pd.to_datetime(old_df[date_col], errors='coerce')
                        
                        # Remove rows with invalid dates
                        new_df = new_df.dropna(subset=[date_col])
                        old_df = old_df.dropna(subset=[date_col])
                        
                        # Merge datasets - new data takes precedence
                        combined_df = pd.concat([old_df, new_df]).drop_duplicates(subset=[date_col], keep='last')
                        combined_df = combined_df.sort_values(date_col).reset_index(drop=True)
                        
                        # Save merged result
                        combined_df.to_csv(new_csv_path, index=False)
                        
                        print(f"   ✅ Merged {filename}: {len(old_df)} + {len(new_df)} → {len(combined_df)} rows")
                    else:
                        print(f"   🔄 Replaced {filename}: No date column for merging")
                        
                except Exception as e:
                    print(f"   ⚠️  Merge failed for {filename}: {e}")
            else:
                print(f"   ✅ New file: {filename} ({len(new_df)} rows)")
                
        except Exception as e:
            print(f"   ❌ Error processing {filename}: {e}")
    
    def update_metadata(self):
        """Update metadata for all CSV files"""
        print("📋 Updating metadata...")
        
        csv_files = [f for f in os.listdir(self.raw_dir) if f.endswith('.csv')]
        
        for csv_file in csv_files:
            csv_path = os.path.join(self.raw_dir, csv_file)
            
            self.metadata[csv_file] = {
                'hash': self.get_file_hash(csv_path),
                'last_updated': datetime.now().isoformat(),
                'size': os.path.getsize(csv_path),
                'rows': len(pd.read_csv(csv_path))
            }
        
        self.save_metadata()
        print(f"   ✅ Updated metadata for {len(csv_files)} files")
    
    def cleanup_xlsx_files(self):
        """Archive XLSX files after processing"""
        print("🧹 Archiving XLSX files...")
        
        xlsx_files = [f for f in os.listdir(self.raw_dir) if f.endswith(('.xlsx', '.xls'))]
        
        for xlsx_file in xlsx_files:
            xlsx_path = os.path.join(self.raw_dir, xlsx_file)
            archive_path = os.path.join(self.archive_dir, f"{xlsx_file}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            shutil.move(xlsx_path, archive_path)
            print(f"   📦 Archived: {xlsx_file}")
    
    def process_all_xlsx(self):
        """Process all XLSX files in the raw directory"""
        print("🔄 Processing RBI XLSX files...")
        
        xlsx_files = [f for f in os.listdir(self.raw_dir) if f.endswith(('.xlsx', '.xls'))]
        
        if not xlsx_files:
            print("   ❌ No XLSX files found to process")
            return False
        
        print(f"   Found {len(xlsx_files)} XLSX files to process")
        
        total_csv_files = []
        
        for xlsx_file in xlsx_files:
            xlsx_path = os.path.join(self.raw_dir, xlsx_file)
            
            # Check if file has changed
            if self.detect_changes(xlsx_path):
                print(f"   🔍 Processing {xlsx_file} (changes detected)")
                csv_files = self.convert_xlsx_to_csv(xlsx_path)
                total_csv_files.extend(csv_files)
            else:
                print(f"   ✅ Skipping {xlsx_file} (no changes)")
        
        # Merge with existing data
        print(f"\n🔄 Merging {len(total_csv_files)} CSV files...")
        for csv_file in total_csv_files:
            csv_path = os.path.join(self.raw_dir, csv_file)
            if os.path.exists(csv_path):
                self.merge_with_existing(csv_path)
        
        # Update metadata
        self.update_metadata()
        
        # Cleanup XLSX files
        self.cleanup_xlsx_files()
        
        print(f"\n✅ RBI data processing complete!")
        print(f"   Processed: {len(xlsx_files)} XLSX files")
        print(f"   Generated: {len(total_csv_files)} CSV files")
        
        return True

def main():
    """Main function"""
    processor = RBIProcessor()
    success = processor.process_all_xlsx()
    
    if success:
        print("\n✅ RBI data processing completed")
        print("   Next step: python src/preprocessing/macro_cleaner.py")
    else:
        print("\n❌ RBI data processing failed")

if __name__ == "__main__":
    main()