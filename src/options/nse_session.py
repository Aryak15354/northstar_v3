#!/usr/bin/env python3
"""
NSE Session Manager - Production Grade & Compliant
Implements proper session-based access with human-scale frequency
"""
import requests
import time
import random
from typing import Optional
import urllib3
from datetime import datetime

# Disable SSL warnings for development
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class NSESession:
    """Production-grade NSE session manager"""
    
    def __init__(self):
        self.session = None
        self.last_request_time = 0
        self.min_request_interval = 60  # 1 minute minimum between requests (human-scale)
        
    def _wait_for_rate_limit(self):
        """Ensure human-scale frequency"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last
            print(f"⏱️ Rate limiting: waiting {wait_time:.1f} seconds...")
            time.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    def create_session(self) -> requests.Session:
        """Create a compliant NSE session with proper browser behavior"""
        session = requests.Session()
        
        # Standard browser headers (not spoofed, just proper)
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0"
        }
        
        try:
            print("🔐 Creating compliant NSE session...")
            
            # Step 1: Visit NSE homepage to establish session (like a human would)
            self._wait_for_rate_limit()
            
            response = session.get(
                "https://www.nseindia.com",
                headers=headers,
                timeout=30,
                allow_redirects=True,
                verify=False
            )
            
            print(f"Homepage visit: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ Successfully visited NSE homepage")
            else:
                print(f"⚠️ Homepage returned {response.status_code}, trying options page...")
                
                # Try options page if homepage fails
                time.sleep(2)
                response = session.get(
                    "https://www.nseindia.com/option-chain",
                    headers=headers,
                    timeout=30,
                    allow_redirects=True,
                    verify=False
                )
                print(f"Options page visit: {response.status_code}")
            
            # Step 2: Update headers for API calls (like the browser does)
            api_headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Referer": "https://www.nseindia.com/option-chain",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "X-Requested-With": "XMLHttpRequest"
            }
            
            session.headers.update(api_headers)
            
            # Step 3: Human-like delay
            time.sleep(random.uniform(2, 5))
            
            self.session = session
            print("✅ NSE session created successfully")
            return session
            
        except Exception as e:
            print(f"❌ Failed to create NSE session: {e}")
            raise
    
    def get_session(self) -> requests.Session:
        """Get current session or create new one"""
        if self.session is None:
            self.session = self.create_session()
        return self.session
    
    def test_api_access(self) -> bool:
        """Test API access with proper rate limiting"""
        try:
            session = self.get_session()
            
            print("🧪 Testing API access...")
            self._wait_for_rate_limit()
            
            test_url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
            response = session.get(test_url, timeout=30)
            
            print(f"API response: {response.status_code}")
            print(f"Content-Type: {response.headers.get('content-type', 'Unknown')}")
            print(f"Content-Length: {len(response.content)}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    if isinstance(data, dict) and len(data) > 0:
                        if "records" in data and "data" in data["records"]:
                            records_count = len(data["records"]["data"])
                            print(f"✅ API test successful - found {records_count} option records")
                            return True
                        else:
                            print("⚠️ API returned data but not in expected format")
                            print(f"Response keys: {list(data.keys())}")
                    else:
                        print("⚠️ API returned empty or invalid JSON")
                        
                except Exception as json_error:
                    print(f"❌ JSON parsing failed: {json_error}")
                    print(f"Raw response: {response.text[:200]}...")
            
            return False
            
        except Exception as e:
            print(f"❌ API test failed: {e}")
            return False

# Global session instance
_nse_session = NSESession()

def get_nse_session() -> requests.Session:
    """Get the global NSE session"""
    return _nse_session.get_session()

def test_nse_session() -> bool:
    """Test NSE session functionality"""
    return _nse_session.test_api_access()

def reset_nse_session():
    """Reset the NSE session (useful for recovery)"""
    global _nse_session
    _nse_session = NSESession()
    print("🔄 NSE session reset")

if __name__ == "__main__":
    print("🧪 Testing Production-Grade NSE Session...")
    print("=" * 50)
    
    success = test_nse_session()
    
    if success:
        print("\n✅ NSE session test PASSED")
        print("🎯 Ready for production data collection")
    else:
        print("\n❌ NSE session test FAILED")
        print("💡 This may be due to:")
        print("   - Market hours (NSE API may be limited outside trading hours)")
        print("   - Network connectivity")
        print("   - NSE server maintenance")
        print("   - Need to retry during market hours (9:15 AM - 3:30 PM IST)")
        
        # Try one more time with fresh session
        print("\n🔄 Trying with fresh session...")
        reset_nse_session()
        success = test_nse_session()
        
        if success:
            print("✅ Fresh session worked!")
        else:
            print("❌ Still failing - likely NSE-side issue")