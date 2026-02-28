#!/usr/bin/env python3
"""
🏛️ RBI DAILY UPDATER - NORTHSTAR V3 INTEGRATED PIPELINE
Complete RBI data pipeline: Scraper → Processor → Cleaner → Integration

This is the unified daily updater that:
1. Downloads latest RBI data using the working scraper
2. Processes XLSX to CSV with retrospective change detection
3. Cleans and standardizes the data
4. Integrates with Northstar V3 data pipeline
5. Updates all downstream systems

Run this daily to keep RBI data current.
"""

import os
import sys
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
import json

class RBIDailyUpdater:
    """Unified RBI data pipeline for daily updates"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.log_dir = "data/macro/logs"
        self.metadata_dir = "data/macro/metadata"
        
        # Create directories
        for dir_path in [self.log_dir, self.metadata_dir]:
            os.makedirs(dir_path, exist_ok=True)
        
        self.log_file = os.path.join(self.log_dir, f"rbi_daily_update_{self.start_time.strftime('%Y%m%d_%H%M%S')}.log")
        self.session_log = []
        
        print("🏛️ RBI DAILY UPDATER - NORTHSTAR V3")
        print("=" * 60)
        print(f"Session started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    def log_step(self, step, message, success=True):
        """Log a step in the pipeline"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        status = "✅" if success else "❌"
        log_entry = f"[{timestamp}] {status} {step}: {message}"
        
        print(log_entry)
        self.session_log.append({
            'timestamp': timestamp,
            'step': step,
            'message': message,
            'success': success
        })
    
    def check_data_freshness(self):
        """Check if RBI data needs updating"""
        self.log_step("FRESHNESS", "Checking data freshness...")
        
        metadata_file = os.path.join(self.metadata_dir, "rbi_data_metadata.json")
        
        if not os.path.exists(metadata_file):
            self.log_step("FRESHNESS", "No existing metadata - full update required")
            return True
        
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            # Check if any file was updated in last 24 hours
            cutoff = datetime.now() - timedelta(hours=24)
            
            for filename, meta in metadata.items():
                if 'last_updated' in meta:
                    last_updated = datetime.fromisoformat(meta['last_updated'])
                    if last_updated > cutoff:
                        self.log_step("FRESHNESS", f"Recent data found - last update: {last_updated.strftime('%Y-%m-%d %H:%M')}")
                        return False
            
            self.log_step("FRESHNESS", "Data is stale (>24 hours) - update required")
            return True
            
        except Exception as e:
            self.log_step("FRESHNESS", f"Error checking freshness: {e} - forcing update", False)
            return True
    
    def run_scraper(self):
        """Run RBI scraper to download latest data"""
        self.log_step("SCRAPER", "Starting RBI data download...")
        
        try:
            result = subprocess.run([
                sys.executable, "src/ingestion/rbi_scraper.py"
            ], capture_output=True, text=True, timeout=300)  # 5 minute timeout
            
            if result.returncode == 0:
                self.log_step("SCRAPER", "RBI scraper completed successfully")
                return True
            else:
                self.log_step("SCRAPER", f"RBI scraper failed with code {result.returncode}", False)
                print(f"STDERR: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.log_step("SCRAPER", "RBI scraper timed out (>5 minutes)", False)
            return False
        except Exception as e:
            self.log_step("SCRAPER", f"RBI scraper error: {e}", False)
            return False
    
    def run_processor(self):
        """Run RBI processor to convert XLSX to CSV"""
        self.log_step("PROCESSOR", "Starting RBI data processing...")
        
        try:
            result = subprocess.run([
                sys.executable, "src/ingestion/rbi_processor.py"
            ], capture_output=True, text=True, timeout=600)  # 10 minute timeout
            
            if result.returncode == 0:
                self.log_step("PROCESSOR", "RBI processor completed successfully")
                return True
            else:
                self.log_step("PROCESSOR", f"RBI processor failed with code {result.returncode}", False)
                print(f"STDERR: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.log_step("PROCESSOR", "RBI processor timed out (>10 minutes)", False)
            return False
        except Exception as e:
            self.log_step("PROCESSOR", f"RBI processor error: {e}", False)
            return False
    
    def run_cleaner(self):
        """Run macro cleaner to standardize data"""
        self.log_step("CLEANER", "Starting macro data cleaning...")
        
        try:
            result = subprocess.run([
                sys.executable, "src/preprocessing/macro_cleaner.py"
            ], capture_output=True, text=True, timeout=300)  # 5 minute timeout
            
            if result.returncode == 0:
                self.log_step("CLEANER", "Macro cleaner completed successfully")
                return True
            else:
                self.log_step("CLEANER", f"Macro cleaner failed with code {result.returncode}", False)
                print(f"STDERR: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.log_step("CLEANER", "Macro cleaner timed out (>5 minutes)", False)
            return False
        except Exception as e:
            self.log_step("CLEANER", f"Macro cleaner error: {e}", False)
            return False
    
    def integrate_with_pipeline(self):
        """Integrate with Northstar V3 data pipeline"""
        self.log_step("INTEGRATION", "Integrating with Northstar V3 pipeline...")
        
        try:
            # Check if integrated data pipeline exists
            pipeline_script = "src/ingestion/integrated_data_pipeline.py"
            if os.path.exists(pipeline_script):
                result = subprocess.run([
                    sys.executable, pipeline_script
                ], capture_output=True, text=True, timeout=600)  # 10 minute timeout
                
                if result.returncode == 0:
                    self.log_step("INTEGRATION", "Pipeline integration completed successfully")
                    return True
                else:
                    self.log_step("INTEGRATION", f"Pipeline integration failed with code {result.returncode}", False)
                    return False
            else:
                self.log_step("INTEGRATION", "Integrated pipeline not found - skipping")
                return True
                
        except subprocess.TimeoutExpired:
            self.log_step("INTEGRATION", "Pipeline integration timed out (>10 minutes)", False)
            return False
        except Exception as e:
            self.log_step("INTEGRATION", f"Pipeline integration error: {e}", False)
            return False
    
    def generate_summary_report(self):
        """Generate summary report of the update session"""
        duration = datetime.now() - self.start_time
        
        # Count successes and failures
        successes = sum(1 for log in self.session_log if log['success'])
        failures = sum(1 for log in self.session_log if not log['success'])
        
        # Check for retrospective changes
        changes_dir = "data/macro/changes"
        recent_changes = []
        if os.path.exists(changes_dir):
            try:
                all_changes_file = os.path.join(changes_dir, "all_retrospective_changes.json")
                if os.path.exists(all_changes_file):
                    with open(all_changes_file, 'r') as f:
                        all_changes = json.load(f)
                    
                    # Find changes from this session
                    session_start_str = self.start_time.isoformat()
                    for change in all_changes:
                        if change['timestamp'] >= session_start_str:
                            recent_changes.append(change)
            except Exception as e:
                print(f"   ⚠️ Error checking retrospective changes: {e}")
        
        # Generate report
        report = {
            'session_start': self.start_time.isoformat(),
            'session_end': datetime.now().isoformat(),
            'duration': str(duration),
            'steps_successful': successes,
            'steps_failed': failures,
            'retrospective_changes': len(recent_changes),
            'session_log': self.session_log,
            'recent_changes': recent_changes
        }
        
        # Save report
        try:
            with open(self.log_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)
        except Exception as e:
            print(f"   ⚠️ Error saving report: {e}")
        
        return report
    
    def run_daily_update(self, force_update=False):
        """Run the complete daily RBI update pipeline"""
        
        try:
            # Step 1: Check if update is needed
            if not force_update:
                needs_update = self.check_data_freshness()
                if not needs_update:
                    self.log_step("PIPELINE", "Data is fresh - no update needed")
                    return True
            else:
                self.log_step("PIPELINE", "Forced update requested")
            
            # Step 2: Download latest RBI data
            if not self.run_scraper():
                self.log_step("PIPELINE", "Scraper failed - checking for existing data", False)
                # Continue anyway - might have existing data to process
            
            # Step 3: Process XLSX to CSV
            if not self.run_processor():
                self.log_step("PIPELINE", "Processor failed - aborting pipeline", False)
                return False
            
            # Step 4: Clean and standardize data
            if not self.run_cleaner():
                self.log_step("PIPELINE", "Cleaner failed - continuing with raw data", False)
                # Continue anyway - raw CSV data might still be usable
            
            # Step 5: Integrate with Northstar V3 pipeline
            if not self.integrate_with_pipeline():
                self.log_step("PIPELINE", "Integration failed - data updated but not integrated", False)
                # This is not critical - data is still updated
            
            # Step 6: Generate summary
            report = self.generate_summary_report()
            
            # Final status
            duration = datetime.now() - self.start_time
            successes = sum(1 for log in self.session_log if log['success'])
            failures = sum(1 for log in self.session_log if not log['success'])
            
            print(f"\n📊 RBI DAILY UPDATE COMPLETE")
            print("=" * 50)
            print(f"   Duration: {duration}")
            print(f"   Steps successful: {successes}")
            print(f"   Steps failed: {failures}")
            print(f"   Retrospective changes: {report['retrospective_changes']}")
            print(f"   Session log: {os.path.basename(self.log_file)}")
            
            # Show retrospective changes summary
            if report['retrospective_changes'] > 0:
                print(f"\n🔍 RETROSPECTIVE CHANGES DETECTED:")
                for change in report['recent_changes'][:3]:  # Show first 3
                    analysis = change['analysis']
                    print(f"   - {change['filename']}: {analysis['changes']} changes")
                if len(report['recent_changes']) > 3:
                    print(f"   ... and {len(report['recent_changes']) - 3} more files")
            
            # Check final data status
            csv_files = []
            raw_dir = "data/macro/raw"
            if os.path.exists(raw_dir):
                csv_files = [f for f in os.listdir(raw_dir) if f.endswith('.csv')]
            
            print(f"\n📁 FINAL DATA STATUS:")
            print(f"   CSV files available: {len(csv_files)}")
            
            success = successes > failures and len(csv_files) > 0
            
            if success:
                print(f"\n✅ RBI DAILY UPDATE SUCCESSFUL")
                print(f"   Northstar V3 macro data is current")
            else:
                print(f"\n⚠️ RBI DAILY UPDATE COMPLETED WITH ISSUES")
                print(f"   Check logs for details: {os.path.basename(self.log_file)}")
            
            return success
            
        except Exception as e:
            self.log_step("PIPELINE", f"Unexpected error: {e}", False)
            print(f"\n❌ RBI DAILY UPDATE FAILED")
            print(f"   Error: {e}")
            return False

def main():
    """Main function with command line options"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RBI Daily Updater - Northstar V3 Integrated Pipeline")
    parser.add_argument("--force", action="store_true", help="Force update even if data is fresh")
    parser.add_argument("--scraper-only", action="store_true", help="Run scraper only")
    parser.add_argument("--processor-only", action="store_true", help="Run processor only")
    parser.add_argument("--cleaner-only", action="store_true", help="Run cleaner only")
    
    args = parser.parse_args()
    
    updater = RBIDailyUpdater()
    
    try:
        if args.scraper_only:
            print("🔄 Scraper-only mode")
            success = updater.run_scraper()
        elif args.processor_only:
            print("🔄 Processor-only mode")
            success = updater.run_processor()
        elif args.cleaner_only:
            print("🔄 Cleaner-only mode")
            success = updater.run_cleaner()
        else:
            # Default: run full pipeline
            success = updater.run_daily_update(force_update=args.force)
        
        if success:
            print("\n🎯 READY FOR NORTHSTAR V3")
            print("   RBI macro data pipeline complete")
        else:
            print("\n❌ Update failed - check logs for details")
            
    except KeyboardInterrupt:
        print("\n⚠️ Update interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()