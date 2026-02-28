"""
Find valid option expiry dates from Upstox API

This script helps identify which expiry dates have actual option data.
"""

import sys
import json
import requests
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.options.config_loader import get_config

def find_expiries():
    """Find valid expiry dates"""
    print("="*60)
    print("FINDING VALID OPTION EXPIRIES")
    print("="*60)
    
    config = get_config()
    
    session = requests.Session()
    session.headers.update({
        'Accept': 'application/json',
        'Authorization': f'Bearer {config.upstox.access_token}'
    })
    
    # Try different expiry dates (next 8 weeks)
    today = date.today()
    
    print(f"\nToday: {today}")
    print(f"Checking next 8 weeks for option data...\n")
    
    for weeks_ahead in range(8):
        test_date = today + timedelta(weeks=weeks_ahead)
        
        # Try Thursday (weekly expiry)
        days_to_thursday = (3 - test_date.weekday()) % 7
        thursday = test_date + timedelta(days=days_to_thursday)
        
        url = config.upstox.endpoints['option_chain']
        params = {
            'instrument_key': 'NSE_INDEX|Nifty 50',
            'expiry_date': thursday.strftime("%Y-%m-%d")
        }
        
        try:
            response = session.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                option_count = len(data.get('data', []))
                
                if option_count > 0:
                    print(f"✓ {thursday} ({thursday.strftime('%A')}): {option_count} options")
                    
                    # Show sample data
                    if weeks_ahead == 0:
                        print(f"\n  Sample data structure:")
                        sample = data['data'][0] if data['data'] else {}
                        print(f"  Keys: {list(sample.keys())}")
                else:
                    print(f"  {thursday} ({thursday.strftime('%A')}): No options")
        except Exception as e:
            print(f"  {thursday}: Error - {e}")
    
    # Also try last Thursday of month (monthly expiry)
    print(f"\n\nChecking monthly expiries (last Thursday)...")
    
    for months_ahead in range(3):
        # Get last Thursday of month
        if months_ahead == 0:
            year, month = today.year, today.month
        else:
            month = today.month + months_ahead
            year = today.year + (month - 1) // 12
            month = ((month - 1) % 12) + 1
        
        # Find last day of month
        if month == 12:
            last_day = date(year, month, 31)
        else:
            last_day = date(year, month + 1, 1) - timedelta(days=1)
        
        # Find last Thursday
        days_back = (last_day.weekday() - 3) % 7
        last_thursday = last_day - timedelta(days=days_back)
        
        url = config.upstox.endpoints['option_chain']
        params = {
            'instrument_key': 'NSE_INDEX|Nifty 50',
            'expiry_date': last_thursday.strftime("%Y-%m-%d")
        }
        
        try:
            response = session.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                option_count = len(data.get('data', []))
                
                if option_count > 0:
                    print(f"✓ {last_thursday} (Monthly): {option_count} options")
                else:
                    print(f"  {last_thursday} (Monthly): No options")
        except Exception as e:
            print(f"  {last_thursday}: Error - {e}")
    
    print("\n" + "="*60)
    print("RECOMMENDATION")
    print("="*60)
    print("\nIf no expiries show options:")
    print("1. Market might be closed (check NSE trading hours)")
    print("2. Try during market hours (9:15 AM - 3:30 PM IST)")
    print("3. Options data might not be available on weekends")
    print("4. Check Upstox API documentation for correct format")

if __name__ == "__main__":
    find_expiries()
