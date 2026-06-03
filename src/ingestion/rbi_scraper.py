#!/usr/bin/env python3
"""
RBI Data Scraper - Simplified and Robust
Handles only the web scraping part of RBI data collection
"""
import os
import time
import pandas as pd
import shutil
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

class RBIScraper:
    """Simplified RBI data scraper"""
    
    def __init__(self, download_dir="data/macro/raw"):
        self.download_dir = os.path.abspath(download_dir)
        os.makedirs(self.download_dir, exist_ok=True)
        self.archive_dir = os.path.abspath("data/macro/archive")
        os.makedirs(self.archive_dir, exist_ok=True)

    def _archive_existing_file(self, dst_path):
        """Archive existing destination file before replacing it."""
        if not os.path.exists(dst_path):
            return None
        filename = os.path.basename(dst_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_path = os.path.join(self.archive_dir, f"{filename}_{timestamp}")
        shutil.move(dst_path, archive_path)
        return archive_path

    def _copy_into_download_dir(self, src_path, filename, allow_replace=True):
        """
        Copy source file into RBI raw directory.
        If destination exists and replacement is enabled, archive old version first.
        """
        dst_path = os.path.join(self.download_dir, filename)
        if os.path.exists(dst_path):
            if not allow_replace:
                return False, "exists_skip"
            archived_to = self._archive_existing_file(dst_path)
            if archived_to:
                print(f"     📦 Archived previous version: {os.path.basename(archived_to)}")
        shutil.copy2(src_path, dst_path)
        return True, dst_path
        
    def setup_browser(self):
        """Configure Chrome browser for downloading"""
        print("🔧 Setting up browser...")
        
        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Download preferences - FORCE downloads to Mac Downloads folder
        mac_downloads = os.path.expanduser("~/Downloads")
        prefs = {
            "download.default_directory": mac_downloads,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        try:
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=chrome_options
            )
            
            # Force download directory using CDP
            driver.execute_cdp_cmd('Page.setDownloadBehavior', {
                'behavior': 'allow',
                'downloadPath': mac_downloads
            })
            
            print(f"   ✅ Browser configured - downloads go to: {mac_downloads}")
            return driver
        except Exception as e:
            print(f"❌ Failed to setup browser: {e}")
            raise
    
    def wait_for_downloads(self, timeout=60):
        """Wait for downloads to complete in Mac Downloads folder"""
        mac_downloads = os.path.expanduser("~/Downloads")
        start_time = time.time()
        
        print(f"     ⏳ Waiting for download in {mac_downloads}...")
        
        # Get initial file count
        try:
            initial_files = set(os.listdir(mac_downloads))
        except:
            initial_files = set()
        
        # Check immediately for existing RBI files first
        try:
            all_files = os.listdir(mac_downloads)
            existing_rbi = []
            for f in all_files:
                if f.endswith(('.xlsx', '.xls')):
                    filename_lower = f.lower()
                    if any(keyword in filename_lower for keyword in [
                        'macro', 'indicator', '50', 'rbi', 'economic'
                    ]):
                        # Check if file is very recent (within last 2 minutes)
                        file_path = os.path.join(mac_downloads, f)
                        if os.path.exists(file_path):
                            file_time = os.path.getmtime(file_path)
                            current_time = time.time()
                            if current_time - file_time < 120:  # 2 minutes
                                existing_rbi.append(f)
                                print(f"     🔍 Found recent RBI file: {f}")
            
            if existing_rbi:
                print(f"     ✅ Using existing recent files: {existing_rbi}")
                
                # Move files to project directory
                moved_files = []
                for rbi_file in existing_rbi:
                    src = os.path.join(mac_downloads, rbi_file)
                    try:
                        if os.path.exists(src):
                            copied, _ = self._copy_into_download_dir(src, rbi_file, allow_replace=True)
                            if copied:
                                moved_files.append(rbi_file)
                                print(f"     📦 Copied to project: {rbi_file}")
                        else:
                            print(f"     ⚠️ File not found: {rbi_file}")
                    except Exception as e:
                        print(f"     ⚠️ Copy error for {rbi_file}: {e}")
                
                if moved_files:
                    return True
        except Exception as e:
            print(f"     ⚠️ Error checking existing files: {e}")
        
        # If no existing files, wait for new downloads
        while time.time() - start_time < timeout:
            try:
                current_files = set(os.listdir(mac_downloads))
                
                # Check for .crdownload files (still downloading)
                downloading_files = [f for f in current_files if f.endswith(".crdownload")]
                
                # Check for new RBI files
                new_files = current_files - initial_files
                rbi_files = []
                
                for f in new_files:
                    if f.endswith(('.xlsx', '.xls')):
                        filename_lower = f.lower()
                        if any(keyword in filename_lower for keyword in [
                            'macro', 'indicator', '50', 'rbi', 'economic', 
                            'monetary', 'financial', 'banking', 'credit'
                        ]):
                            rbi_files.append(f)
                            print(f"     🔍 New RBI file detected: {f}")
                
                if not downloading_files and rbi_files:
                    print(f"     ✅ Download complete: {rbi_files}")
                    
                    # Move files to project directory
                    moved_files = []
                    for rbi_file in rbi_files:
                        src = os.path.join(mac_downloads, rbi_file)
                        try:
                            if os.path.exists(src):
                                copied, _ = self._copy_into_download_dir(src, rbi_file, allow_replace=True)
                                if copied:
                                    moved_files.append(rbi_file)
                                    print(f"     📦 Copied to project: {rbi_file}")
                            else:
                                print(f"     ⚠️ File not found: {rbi_file}")
                        except Exception as e:
                            print(f"     ⚠️ Copy error for {rbi_file}: {e}")
                    
                    if moved_files:
                        return True
                    else:
                        print(f"     ❌ No files were successfully copied")
                
                if downloading_files:
                    print(f"     ⏳ Still downloading: {len(downloading_files)} file(s)")
                elif not rbi_files:
                    print(f"     🔍 No new RBI files detected yet...")
                
                time.sleep(3)
                
            except Exception as e:
                print(f"     ⚠️ Error checking downloads: {e}")
                time.sleep(2)
        
        print(f"     ⚠️ Download timeout after {timeout} seconds")
        return False
    
    def move_existing_rbi_files(self):
        """Move any existing RBI files from Downloads to project directory"""
        print("📦 Checking for existing RBI files in Downloads...")
        
        mac_downloads = os.path.expanduser("~/Downloads")
        moved_files = []
        
        try:
            all_files = os.listdir(mac_downloads)
            rbi_files = []
            
            for f in all_files:
                if f.endswith(('.xlsx', '.xls')):
                    filename_lower = f.lower()
                    if any(keyword in filename_lower for keyword in [
                        'macro', 'indicator', '50', 'rbi', 'economic',
                        'monetary', 'financial', 'banking', 'credit'
                    ]):
                        rbi_files.append(f)
            
            print(f"   🔍 Found {len(rbi_files)} potential RBI files")
            
            for rbi_file in rbi_files:
                src = os.path.join(mac_downloads, rbi_file)
                
                try:
                    if os.path.exists(src):
                        copied, _ = self._copy_into_download_dir(src, rbi_file, allow_replace=True)
                        if copied:
                            moved_files.append(rbi_file)
                            print(f"   ✅ Copied to project: {rbi_file}")
                        
                        # Optionally remove from Downloads after successful copy
                        # os.remove(src)
                        
                except Exception as e:
                    print(f"   ❌ Error moving {rbi_file}: {e}")
            
            if moved_files:
                print(f"   📦 Successfully moved {len(moved_files)} files")
                return True
            else:
                print(f"   ℹ️ No new RBI files to move")
                return False
                
        except Exception as e:
            print(f"   ❌ Error accessing Downloads folder: {e}")
            return False

    def download_dataset(self, dataset_name, max_retries=3):
        """Download a specific RBI dataset"""
        
        print(f"📥 Downloading: {dataset_name}")
        
        driver = None
        for attempt in range(max_retries):
            try:
                driver = self.setup_browser()
                
                # Navigate to RBI DBIE
                print("🌐 Opening RBI DBIE portal...")
                driver.get("https://data.rbi.org.in/DBIE/#/dbie/home")
                time.sleep(10)
                
                # Find and click the dataset link
                try:
                    # Try multiple strategies to find the link
                    link_element = None
                    
                    # Strategy 1: Exact link text
                    try:
                        link_element = WebDriverWait(driver, 15).until(
                            EC.element_to_be_clickable((By.LINK_TEXT, dataset_name))
                        )
                    except TimeoutException:
                        # Strategy 2: Partial link text
                        try:
                            link_element = driver.find_element(By.PARTIAL_LINK_TEXT, dataset_name)
                        except NoSuchElementException:
                            # Strategy 3: XPath with contains
                            link_element = driver.find_element(By.XPATH, f"//a[contains(text(), '{dataset_name}')]")
                    
                    if not link_element:
                        raise Exception(f"Could not find link for {dataset_name}")
                    
                    # Click the link - THIS IS THE DOWNLOAD LINK
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", link_element)
                    time.sleep(2)
                    driver.execute_script("arguments[0].click();", link_element)
                    
                    # The click itself triggers the download - no need to look for download buttons
                    print(f"   📥 Clicked dataset link - download should start automatically")
                    
                    # Give download time to start
                    time.sleep(5)
                    
                    # Wait for download to complete - FIXED LOGIC
                    if self.wait_for_downloads():
                        print(f"   ✅ Successfully downloaded {dataset_name}")
                        return True
                    else:
                        print(f"   ⚠️ Download detection failed for {dataset_name}")
                        # But the download might have actually worked, so check Downloads folder
                        mac_downloads = os.path.expanduser("~/Downloads")
                        try:
                            recent_files = []
                            for f in os.listdir(mac_downloads):
                                if f.endswith(('.xlsx', '.xls')):
                                    if any(keyword in f.lower() for keyword in ['macro', 'indicator', '50', 'rbi']):
                                        file_path = os.path.join(mac_downloads, f)
                                        file_time = os.path.getmtime(file_path)
                                        if time.time() - file_time < 60:  # Within last minute
                                            recent_files.append(f)
                            
                            if recent_files:
                                print(f"   ✅ Found recent downloads: {recent_files}")
                                # Move them manually
                                for rbi_file in recent_files:
                                    src = os.path.join(mac_downloads, rbi_file)
                                    try:
                                        copied, _ = self._copy_into_download_dir(src, rbi_file, allow_replace=True)
                                        if copied:
                                            print(f"   📦 Copied to project: {rbi_file}")
                                    except Exception as e:
                                        print(f"   ⚠️ Copy error: {e}")
                                return True
                        except Exception as e:
                            print(f"   ⚠️ Error checking recent files: {e}")
                        
                        return False
                
                except Exception as e:
                    print(f"   ❌ Error downloading {dataset_name}: {e}")
                    if attempt < max_retries - 1:
                        print(f"   🔄 Retrying... (attempt {attempt + 2}/{max_retries})")
                        time.sleep(5)
                    continue
                
            except Exception as e:
                print(f"   ❌ Browser error: {e}")
                if attempt < max_retries - 1:
                    print(f"   🔄 Retrying... (attempt {attempt + 2}/{max_retries})")
                    time.sleep(5)
                continue
            finally:
                if driver:
                    driver.quit()
        
        print(f"   ❌ Failed to download {dataset_name} after {max_retries} attempts")
        return False
    
    def download_all_datasets(self):
        """Download all required RBI datasets"""
        
        datasets = [
            "50 Macroeconomic Indicators",
            "Other Macroeconomic Indicators"
        ]
        
        print("🏦 Starting RBI data download...")
        
        # First, try to move any existing files
        existing_moved = self.move_existing_rbi_files()
        
        success_count = 0
        for dataset in datasets:
            if self.download_dataset(dataset):
                success_count += 1
            else:
                # Even if download "failed", check if files actually exist
                print(f"   🔍 Checking if {dataset} was actually downloaded...")
                mac_downloads = os.path.expanduser("~/Downloads")
                try:
                    recent_files = []
                    for f in os.listdir(mac_downloads):
                        if f.endswith(('.xlsx', '.xls')):
                            if any(keyword in f.lower() for keyword in ['macro', 'indicator', '50', 'rbi']):
                                file_path = os.path.join(mac_downloads, f)
                                file_time = os.path.getmtime(file_path)
                                if time.time() - file_time < 300:  # Within last 5 minutes
                                    recent_files.append(f)
                    
                    if recent_files:
                        print(f"   ✅ Found recent files, moving to project: {recent_files}")
                        for rbi_file in recent_files:
                            src = os.path.join(mac_downloads, rbi_file)
                            try:
                                copied, _ = self._copy_into_download_dir(src, rbi_file, allow_replace=True)
                                if copied:
                                    print(f"   📦 Copied: {rbi_file}")
                            except Exception as e:
                                print(f"   ⚠️ Copy error: {e}")
                        success_count += 1
                except Exception as e:
                    print(f"   ⚠️ Error checking files: {e}")
        
        # If downloads failed but we moved existing files, consider it a success
        if success_count == 0 and existing_moved:
            print("✅ Using existing RBI files from Downloads")
            success_count = 1
        
        print(f"\n📊 Download Summary:")
        print(f"   Successful: {success_count}/{len(datasets)} datasets")
        
        # List downloaded files
        xlsx_files = [f for f in os.listdir(self.download_dir) if f.endswith(('.xlsx', '.xls'))]
        print(f"   Available files: {len(xlsx_files)}")
        for file in xlsx_files:
            print(f"     - {file}")
        
        success = success_count > 0 or len(xlsx_files) > 0
        return success

def main():
    """Main function"""
    scraper = RBIScraper()
    success = scraper.download_all_datasets()
    
    if success:
        print("\n✅ RBI data download completed")
        print("   Next step: python src/ingestion/rbi_processor.py")
    else:
        print("\n❌ RBI data download failed")

if __name__ == "__main__":
    scraper = RBIScraper()
    ok = bool(scraper.download_all_datasets())
    raise SystemExit(0 if ok else 1)
