"""
Diagnostic script to inspect Upstox API responses

This helps debug API integration issues by showing raw responses.
"""

import sys
import json
import requests
from pathlib import Path
from datetime import date, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.options.config_loader import get_config

def diagnose_api():
    """Diagnose Upstox API responses"""
    print("="*60)
    print("UPSTOX API DIAGNOSTIC")
    print("="*60)
    
    # Load config
    config = get_config()
    
    print(f"\nAPI Key: {config.upstox.api_key[:20]}...")
    print(f"Access Token: {config.upstox.access_token[:50]}...")
    
    # Setup session
    session = requests.Session()
    session.headers.update({
        'Accept': 'application/json',
        'Authorization': f'Bearer {config.upstox.access_token}'
    })
    
    # Test 1: Market quote for NIFTY
    print("\n" + "="*60)
    print("TEST 1: Market Quote API")
    print("="*60)
    
    url = config.upstox.endpoints['market_quote']
    params = {'instrument_key': 'NSE_INDEX|Nifty 50'}
    
    print(f"URL: {url}")
    print(f"Params: {params}")
    
    try:
        response = session.get(url, params=params, timeout=30)
        print(f"\nStatus Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\nResponse JSON:")
            print(json.dumps(data, indent=2))
        else:
            print(f"\nError Response:")
            print(response.text)
    except Exception as e:
        print(f"\nException: {e}")
    
    # Test 2: Option chain
    print("\n" + "="*60)
    print("TEST 2: Option Chain API")
    print("="*60)
    
    url = config.upstox.endpoints['option_chain']
    expiry = date.today() + timedelta(days=7)
    params = {
        'instrument_key': 'NSE_INDEX|Nifty 50',
        'expiry_date': expiry.strftime("%Y-%m-%d")
    }
    
    print(f"URL: {url}")
    print(f"Params: {params}")
    
    try:
        response = session.get(url, params=params, timeout=30)
        print(f"\nStatus Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"\nResponse JSON (first 500 chars):")
            print(json.dumps(data, indent=2)[:500])
            
            if 'data' in data:
                print(f"\nData structure:")
                print(f"  - Type: {type(data['data'])}")
                if isinstance(data['data'], list):
                    print(f"  - Length: {len(data['data'])}")
                    if data['data']:
                        print(f"  - First item keys: {list(data['data'][0].keys())}")
                elif isinstance(data['data'], dict):
                    print(f"  - Keys: {list(data['data'].keys())}")
        else:
            print(f"\nError Response:")
            print(response.text)
    except Exception as e:
        print(f"\nException: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 3: Check token validity
    print("\n" + "="*60)
    print("TEST 3: Token Validity")
    print("="*60)
    
    # Try a simple API call to check if token is valid
    url = "https://api.upstox.com/v2/user/profile"
    
    try:
        response = session.get(url, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✓ Token is valid")
            data = response.json()
            print(f"User: {data.get('data', {}).get('user_name', 'Unknown')}")
        elif response.status_code == 401:
            print("✗ Token is expired or invalid")
            print("\nTo generate a new token:")
            print("1. Go to https://api.upstox.com/")
            print("2. Login and navigate to API Console")
            print("3. Generate new access token")
            print("4. Update .env.options file")
        else:
            print(f"Unexpected status: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    diagnose_api()
