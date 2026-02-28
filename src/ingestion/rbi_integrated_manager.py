#!/usr/bin/env python3
"""
RBI Integrated Data Manager - Simplified Version
Orchestrates RBI data download and processing using modular components
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import json

from src.ingestion.rbi_scraper import RBIScraper

# Directory structure
RAW_DIR = "data/macro/raw"
METADATA_DIR = "data/macro/metadata"
LOG_DIR = "data/macro/logs"

# Create directories
for dir_path in [RAW_DIR, METADATA_DIR, LOG_DIR]:
    os.makedirs(dir_path, exist_ok=True)

class RBIDataManager:
    """Simplified RBI data management system"""
    
    def __init__(self):
        self.metadata_file = os.path.join(METADATA_DIR, "rbi_data_metadata.json")
        self.last_run_file = os.path.join(LOG_DIR, "last_successful_run.txt")
        
    def check_data_freshness(self):
        """Check if we need to update RBI data"""
        
        if not os.path.exists(self.metadata_file):
            print("📊 No existing RBI data found - full download required")
            return True
        
        # Check last update time
        try:
            with open(self.metadata_file, 'r') as f:
                metadata = json.load(f)
            
            # Check if any file was updated in last 7 days
            cutoff = datetime.now() - timedelta(days=7)
            
            for filename, meta in metadata.items():
                last_updated = datetime.fromisoformat(meta.get('last_updated', '2020-01-01'))
                if last_updated > cutoff:
                    print(f"📊 Recent data found - last update: {last_updated.strftime('%Y-%m-%d %H:%M')}")
                    return False
            
            print("📊 Data is stale (>7 days) - update required")
            return True
            
        except Exception as e:
            print(f"📊 Error checking data freshness: {e} - forcing update")
            return True
    
    def run_scraper(self):
        """Run the RBI scraper using the RBIScraper class"""
        print("🔧 Running RBI scraper...")
        
        try:
            scraper = RBIScraper(download_dir=RAW_DIR)
            success = scraper.download_all_datasets()
            
            if success:
                print("✅ RBI scraper completed successfully")
                return True
            else:
                print("❌ RBI scraper failed")
                return False
        except Exception as e:
            print(f"❌ RBI scraper error: {e}")
            return False
    
    def run_processor(self):
        """Run the RBI processor"""
        print("⚙️  Running RBI processor...")
        
        try:
            result = subprocess.run([
                sys.executable, "src/ingestion/rbi_processor.py"
            ], capture_output=True, text=True, timeout=600)  # 10 minute timeout
            
            if result.returncode == 0:
                print("✅ RBI processor completed successfully")
                return True
            else:
                print(f"❌ RBI processor failed with code {result.returncode}")
                print(f"STDERR: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ RBI processor timed out (>10 minutes)")
            return False
        except Exception as e:
            print(f"❌ RBI processor error: {e}")
            return False
    
    def record_successful_run(self):
        """Record successful run timestamp"""
        with open(self.last_run_file, 'w') as f:
            f.write(datetime.now().isoformat())
    
    def run_full_update(self):
        """Run complete RBI data update process"""
        print("🚀 RBI INTEGRATED DATA MANAGER")
        print("=" * 60)
        print("Starting simplified data update process...")
        
        start_time = datetime.now()
        
        try:
            # Step 1: Check if update is needed
            needs_update = self.check_data_freshness()
            
            if not needs_update:
                print("📊 Using existing RBI data (fresh within 7 days)")
                return True
            
            # Step 2: Run scraper to download XLSX files
            print("\n📥 STEP 1: Downloading RBI data...")
            if not self.run_scraper():
                print("❌ Scraper failed, checking for existing XLSX files...")
                xlsx_files = [f for f in os.listdir(RAW_DIR) if f.endswith(('.xlsx', '.xls'))]
                if not xlsx_files:
                    print("❌ No XLSX files available for processing")
                    return False
                print(f"📁 Found {len(xlsx_files)} existing XLSX files to process")
            
            # Step 3: Run processor to convert XLSX to CSV
            print("\n📊 STEP 2: Processing XLSX files...")
            if not self.run_processor():
                print("❌ Processor failed")
                return False
            
            # Step 4: Record successful run
            self.record_successful_run()
            
            # Final summary
            duration = datetime.now() - start_time
            csv_count = len([f for f in os.listdir(RAW_DIR) if f.endswith('.csv')])
            
            print(f"\n✅ RBI DATA UPDATE COMPLETE")
            print(f"   Duration: {duration}")
            print(f"   Total CSV files: {csv_count}")
            
            # Show key output files
            key_files = [
                ("RBI Raw Data", f"{RAW_DIR}/*.csv"),
                ("Metadata", self.metadata_file)
            ]
            
            print(f"\n📁 Key Output Files:")
            for name, file_pattern in key_files:
                if '*' in file_pattern:
                    # Handle wildcard patterns
                    matching_files = list(Path('.').glob(file_pattern))
                    if matching_files:
                        print(f"   ✅ {name}: {len(matching_files)} files")
                    else:
                        print(f"   ❌ {name}: No files found")
                else:
                    if os.path.exists(file_pattern):
                        size = os.path.getsize(file_pattern) / 1024
                        print(f"   ✅ {name}: {file_pattern} ({size:.1f} KB)")
                    else:
                        print(f"   ❌ {name}: {file_pattern} (missing)")
            
            return True
            
        except Exception as e:
            print(f"❌ Update failed: {e}")
            return False

def main():
    """Main function with simplified interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RBI Integrated Data Manager")
    parser.add_argument("--scrape-only", action="store_true", help="Run scraper only")
    parser.add_argument("--process-only", action="store_true", help="Run processor only")
    
    args = parser.parse_args()
    
    manager = RBIDataManager()
    
    if args.scrape_only:
        print("🔄 Scrape-only mode")
        success = manager.run_scraper()
    elif args.process_only:
        print("🔄 Process-only mode")
        success = manager.run_processor()
    else:
        # Default: run full update
        success = manager.run_full_update()
    
    if success:
        print("\n🎯 READY FOR MACRO PIPELINE")
        print("   Next step: python run_macro_pipeline.py")
    else:
        print("\n❌ Update failed - check logs for details")

if __name__ == "__main__":
    main()
    
    def generate_summary_report(self):
        """Generate summary report of the session"""
        report_file = os.path.join(LOG_DIR, f"rbi_update_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        
        with open(report_file, 'w') as f:
            f.write("RBI DATA UPDATE SUMMARY\n")
            f.write("=" * 50 + "\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"Session Changes: {len(self.session_log)}\n\n")
            
            # Group changes by type
            change_types = {}
            for change in self.session_log:
                change_type = change['type']
                if change_type not in change_types:
                    change_types[change_type] = []
                change_types[change_type].append(change)
            
            for change_type, changes in change_types.items():
                f.write(f"{change_type.upper().replace('_', ' ')}: {len(changes)}\n")
                for change in changes:
                    f.write(f"  - {change['details']}\n")
                f.write("\n")
            
            # Current file status
            f.write("CURRENT FILES:\n")
            f.write("-" * 20 + "\n")
            csv_files = [f for f in os.listdir(self.download_dir) if f.endswith('.csv')]
            for csv_file in sorted(csv_files):
                if csv_file in self.metadata:
                    meta = self.metadata[csv_file]
                    f.write(f"{csv_file}: {meta['rows']} rows, {meta['size']} bytes\n")
        
        print(f"📊 Summary report: {report_file}")
        return report_file
    
    def run_full_update(self):
        """Run complete RBI data update process with seamless integration"""
        print("🚀 RBI INTEGRATED DATA MANAGER")
        print("=" * 60)
        print("Starting seamless data update process...")
        
        start_time = datetime.now()
        
        try:
            # Step 1: Download fresh XLSX files
            print("\n📥 STEP 1: Downloading RBI data...")
            downloaded_files = self.download_rbi_data()
            
            if not downloaded_files:
                print("❌ No files downloaded, checking existing files...")
                # Check if we have existing XLSX files to process
                existing_xlsx = [f for f in os.listdir(self.download_dir) if f.endswith(('.xlsx', '.xls'))]
                if existing_xlsx:
                    print(f"📁 Found {len(existing_xlsx)} existing XLSX files to process")
                    downloaded_files = existing_xlsx
                else:
                    print("❌ No XLSX files available, exiting")
                    return False
            
            # Step 2: Process each XLSX file
            print(f"\n📊 STEP 2: Converting {len(downloaded_files)} XLSX files...")
            all_csv_files = []
            
            for xlsx_file in downloaded_files:
                xlsx_path = os.path.join(self.download_dir, xlsx_file)
                
                if not os.path.exists(xlsx_path):
                    print(f"   ⚠️  File not found: {xlsx_file}")
                    continue
                
                # Check for changes
                has_changes = self.detect_changes(xlsx_path)
                
                if has_changes:
                    print(f"   🔍 Processing {xlsx_file} (changes detected)")
                    csv_files = self.convert_xlsx_to_csv(xlsx_path)
                    all_csv_files.extend(csv_files)
                else:
                    print(f"   ✅ Skipping {xlsx_file} (no changes)")
            
            if not all_csv_files:
                print("⚠️  No CSV files generated, but updating metadata anyway...")
            
            # Step 3: Merge/update CSV data with retrospective change detection
            print(f"\n🔄 STEP 3: Merging {len(all_csv_files)} CSV files...")
            for csv_file in all_csv_files:
                csv_path = os.path.join(self.download_dir, csv_file)
                if os.path.exists(csv_path):
                    self.merge_or_replace_csv(csv_path)
            
            # Step 4: Update metadata for all CSV files (including unchanged ones)
            print("\n📋 STEP 4: Updating metadata...")
            self.update_metadata()
            
            # Step 5: Cleanup temporary files
            print("\n🧹 STEP 5: Cleaning up...")
            self.cleanup_old_files()
            
            # Step 6: Generate comprehensive report
            print("\n📊 STEP 6: Generating report...")
            report_file = self.generate_summary_report()
            
            # Final summary
            duration = datetime.now() - start_time
            csv_count = len([f for f in os.listdir(self.download_dir) if f.endswith('.csv')])
            
            print(f"\n✅ RBI DATA UPDATE COMPLETE")
            print(f"   Duration: {duration}")
            print(f"   Total CSV files: {csv_count}")
            print(f"   Session changes: {len(self.session_log)}")
            print(f"   Report: {os.path.basename(report_file)}")
            
            # Check for retrospective changes
            retro_changes = [log for log in self.session_log if log['type'] == 'retrospective_changes']
            if retro_changes:
                print(f"   🔍 Retrospective changes detected in {len(retro_changes)} files")
            
            return True
            
        except Exception as e:
            print(f"❌ Update failed: {e}")
            self.log_change('update_failed', {'error': str(e)})
            return False

def main():
    """Main function with options for different workflows"""
    import sys
    
    manager = RBIDataManager()
    
    # Check command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'download-only':
            print("🔄 Download-only mode")
            files = manager.download_rbi_data()
            print(f"Downloaded: {files}")
            
        elif command == 'convert-only':
            print("🔄 Convert-only mode (processing existing XLSX files)")
            xlsx_files = [f for f in os.listdir(manager.download_dir) if f.endswith(('.xlsx', '.xls'))]
            for xlsx_file in xlsx_files:
                xlsx_path = os.path.join(manager.download_dir, xlsx_file)
                csv_files = manager.convert_xlsx_to_csv(xlsx_path)
                print(f"Converted {xlsx_file} → {len(csv_files)} CSV files")
                
        elif command == 'merge-only':
            print("🔄 Merge-only mode (processing existing CSV files)")
            csv_files = [f for f in os.listdir(manager.download_dir) if f.endswith('.csv')]
            for csv_file in csv_files:
                csv_path = os.path.join(manager.download_dir, csv_file)
                manager.merge_or_replace_csv(csv_path)
            manager.update_metadata()
            
        else:
            print(f"❌ Unknown command: {command}")
            print("Available commands: download-only, convert-only, merge-only")
            return
    else:
        # Default: run full seamless update
        success = manager.run_full_update()
        
        if success:
            print("\n🎯 READY FOR MACRO PIPELINE")
            print("   Next step: python run_macro_pipeline.py")
        else:
            print("\n❌ Update failed - check logs for details")

if __name__ == "__main__":
    main()