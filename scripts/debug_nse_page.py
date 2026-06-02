#!/usr/bin/env python3
"""
NSE Page Debugger - Inspect actual page structure

This helps identify the correct selectors for NSE bulk deals page.
"""

import time
from pathlib import Path

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

NSE_URL = "https://www.nseindia.com/report-detail/display-bulk-and-block-deals"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "raw" / "exchanges" / "nse" / "alternative" / "bulk_deals" / "debug"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def debug_nse_page():
    """Debug NSE page structure."""
    print("=" * 80)
    print("NSE PAGE DEBUGGER")
    print("=" * 80)
    
    # Create driver
    print("\n1. Creating WebDriver...")
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    
    try:
        # Navigate
        print(f"2. Opening {NSE_URL}...")
        driver.get(NSE_URL)
        driver.maximize_window()
        
        # Wait
        print("   Waiting for page load...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(5)
        print("   ✓ Page loaded")
        
        # Save page source
        print("\n3. Saving page source...")
        html_path = OUTPUT_DIR / "nse_page_source.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"   ✓ Saved to {html_path}")
        
        # Find all buttons
        print("\n4. Finding all buttons...")
        buttons = driver.find_elements(By.TAG_NAME, "button")
        print(f"   Found {len(buttons)} buttons")
        
        for i, btn in enumerate(buttons[:30]):  # First 30
            try:
                text = btn.text.strip()[:50]
                class_name = btn.get_attribute("class") or ""
                btn_id = btn.get_attribute("id") or ""
                print(f"   [{i}] Text: '{text}' | Class: {class_name[:50]} | ID: {btn_id}")
            except Exception:
                continue
        
        # Find all clickable elements with "download" or "csv"
        print("\n5. Finding download/CSV elements...")
        for selector in [
            "//*[contains(text(), 'Download')]",
            "//*[contains(text(), 'CSV')]",
            "//*[contains(text(), 'download')]",
            "//*[contains(@onclick, 'download')]",
            "//button",
            "//a",
        ]:
            try:
                elements = driver.find_elements(By.XPATH, selector)
                if elements:
                    print(f"   Selector '{selector[:40]}...' found {len(elements)} elements")
                    for elem in elements[:5]:
                        try:
                            text = elem.text.strip()[:50]
                            print(f"      - {text}")
                        except Exception:
                            pass
            except Exception:
                continue
        
        # Find all input fields
        print("\n6. Finding input fields...")
        inputs = driver.find_elements(By.TAG_NAME, "input")
        print(f"   Found {len(inputs)} input fields")
        for i, inp in enumerate(inputs[:10]):
            try:
                inp_type = inp.get_attribute("type")
                inp_id = inp.get_attribute("id")
                inp_name = inp.get_attribute("name")
                inp_value = inp.get_attribute("value") or ""
                print(f"   [{i}] Type: {inp_type} | ID: {inp_id} | Name: {inp_name} | Value: {inp_value[:30]}")
            except Exception:
                continue
        
        # Find date-related elements
        print("\n7. Finding date-related elements...")
        for selector in [
            "//*[contains(text(), 'Date')]",
            "//*[contains(@id, 'date')]",
            "//*[contains(@id, 'Date')]",
            "//*[contains(@id, 'from')]",
            "//*[contains(@id, 'to')]",
        ]:
            try:
                elements = driver.find_elements(By.XPATH, selector)
                if elements:
                    print(f"   Selector '{selector[:40]}...' found {len(elements)} elements")
            except Exception:
                continue
        
        # Find table
        print("\n8. Finding tables...")
        tables = driver.find_elements(By.TAG_NAME, "table")
        print(f"   Found {len(tables)} tables")
        for i, table in enumerate(tables[:5]):
            rows = table.find_elements(By.TAG_NAME, "tr")
            print(f"   Table {i}: {len(rows)} rows")
            if rows:
                header_cells = rows[0].find_elements(By.TAG_NAME, "th")
                if header_cells:
                    headers = [cell.text.strip() for cell in header_cells]
                    print(f"      Headers: {headers}")
        
        # Take screenshot
        print("\n9. Taking screenshot...")
        screenshot_path = OUTPUT_DIR / "nse_page_screenshot.png"
        driver.save_screenshot(str(screenshot_path))
        print(f"   ✓ Saved to {screenshot_path}")
        
        print("\n" + "=" * 60)
        print("DEBUG COMPLETE")
        print("=" * 60)
        print(f"\nFiles saved to: {OUTPUT_DIR}")
        print("\nNext steps:")
        print("1. Open nse_page_source.html in browser")
        print("2. Inspect element to find correct selectors")
        print("3. Update scrape_nse_bulk_deals_selenium.py with correct selectors")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        print("\nClosing browser...")
        driver.quit()
        print("✓ Browser closed")


if __name__ == "__main__":
    debug_nse_page()
