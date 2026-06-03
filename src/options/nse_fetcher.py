#!/usr/bin/env python3
"""
NSE Options Chain Fetcher - Institutional Grade
Fetches NIFTY options data from NSE API with proper error handling
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import json
from typing import Optional, Dict, List
from nse_session import get_nse_session

# NSE API endpoints
NIFTY_CHAIN_URL = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
BANKNIFTY_CHAIN_URL = "https://www.nseindia.com/api/option-chain-indices?symbol=BANKNIFTY"

def fetch_nifty_chain(symbol: str = "NIFTY", max_retries: int = 3) -> Optional[pd.DataFrame]:
    """
    Fetch NIFTY options chain from NSE API
    
    Args:
        symbol: NIFTY or BANKNIFTY
        max_retries: Maximum number of retry attempts
        
    Returns:
        DataFrame with options data or None if failed
    """
    
    url = NIFTY_CHAIN_URL if symbol == "NIFTY" else BANKNIFTY_CHAIN_URL
    
    for attempt in range(max_retries):
        try:
            print(f"📡 Fetching {symbol} options chain (attempt {attempt + 1}/{max_retries})...")
            
            # Get authenticated session
            session = get_nse_session()
            
            # Fetch data
            response = session.get(url, timeout=15)
            
            if response.status_code != 200:
                print(f"❌ HTTP {response.status_code}: {response.text[:200]}")
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    return None
            
            # Parse JSON response
            data = response.json()
            
            if "records" not in data or "data" not in data["records"]:
                print("❌ Invalid response structure")
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))
                    continue
                else:
                    return None
            
            # Extract metadata
            records = data["records"]
            underlying_value = records.get("underlyingValue", 0)
            timestamp = records.get("timestamp", "")
            
            print(f"📊 {symbol} @ {underlying_value} | Timestamp: {timestamp}")
            
            # Process options data
            options_data = records["data"]
            rows = []
            current_time = pd.Timestamp.now()
            
            for row in options_data:
                strike = row["strikePrice"]
                expiry = row["expiryDate"]
                
                # Process Call options
                if "CE" in row and row["CE"]:
                    ce = row["CE"]
                    rows.append({
                        "timestamp": current_time,
                        "date": current_time.normalize(),
                        "symbol": symbol,
                        "underlying_price": underlying_value,
                        "expiry": pd.to_datetime(expiry, format="%d-%b-%Y"),
                        "strike": float(strike),
                        "option_type": "C",
                        "ltp": float(ce.get("lastPrice", 0)),
                        "bid": float(ce.get("bidprice", 0)),
                        "ask": float(ce.get("askPrice", 0)),
                        "iv": float(ce.get("impliedVolatility", 0)),
                        "oi": int(ce.get("openInterest", 0)),
                        "volume": int(ce.get("totalTradedVolume", 0)),
                        "change_oi": int(ce.get("changeinOpenInterest", 0)),
                        "pct_change_oi": float(ce.get("pchangeinOpenInterest", 0)),
                        "delta": float(ce.get("delta", 0)),
                        "gamma": float(ce.get("gamma", 0)),
                        "theta": float(ce.get("theta", 0)),
                        "vega": float(ce.get("vega", 0))
                    })
                
                # Process Put options
                if "PE" in row and row["PE"]:
                    pe = row["PE"]
                    rows.append({
                        "timestamp": current_time,
                        "date": current_time.normalize(),
                        "symbol": symbol,
                        "underlying_price": underlying_value,
                        "expiry": pd.to_datetime(expiry, format="%d-%b-%Y"),
                        "strike": float(strike),
                        "option_type": "P",
                        "ltp": float(pe.get("lastPrice", 0)),
                        "bid": float(pe.get("bidprice", 0)),
                        "ask": float(pe.get("askPrice", 0)),
                        "iv": float(pe.get("impliedVolatility", 0)),
                        "oi": int(pe.get("openInterest", 0)),
                        "volume": int(pe.get("totalTradedVolume", 0)),
                        "change_oi": int(pe.get("changeinOpenInterest", 0)),
                        "pct_change_oi": float(pe.get("pchangeinOpenInterest", 0)),
                        "delta": float(pe.get("delta", 0)),
                        "gamma": float(pe.get("gamma", 0)),
                        "theta": float(pe.get("theta", 0)),
                        "vega": float(pe.get("vega", 0))
                    })
            
            if not rows:
                print("❌ No options data found")
                return None
            
            df = pd.DataFrame(rows)
            
            # Data quality checks
            df = df[df['ltp'] > 0]  # Remove zero prices
            df = df[df['iv'] > 0]   # Remove zero IV
            df = df[df['strike'] > 0]  # Remove invalid strikes
            
            # Calculate additional metrics
            df['days_to_expiry'] = (df['expiry'] - df['date']).dt.days
            df['moneyness'] = df['strike'] / df['underlying_price']
            df['time_to_expiry'] = df['days_to_expiry'] / 365.25
            
            # Filter out very short-term and very long-term options
            df = df[(df['days_to_expiry'] >= 1) & (df['days_to_expiry'] <= 365)]
            
            print(f"✅ Successfully fetched {len(df)} {symbol} options")
            print(f"   Expiries: {df['expiry'].nunique()}")
            print(f"   Strikes: {df['strike'].nunique()}")
            print(f"   Avg IV: {df['iv'].mean():.1f}%")
            
            return df
            
        except Exception as e:
            print(f"❌ Error fetching {symbol} chain (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5 * (attempt + 1))
            else:
                print(f"❌ Failed to fetch {symbol} chain after {max_retries} attempts")
                return None
    
    return None

def fetch_multiple_symbols(symbols: List[str] = ["NIFTY", "BANKNIFTY"]) -> Dict[str, pd.DataFrame]:
    """
    Fetch options chains for multiple symbols
    
    Args:
        symbols: List of symbols to fetch
        
    Returns:
        Dictionary mapping symbol to DataFrame
    """
    results = {}
    
    for symbol in symbols:
        df = fetch_nifty_chain(symbol)
        if df is not None:
            results[symbol] = df
        
        # Small delay between symbols to be respectful
        time.sleep(2)
    
    return results

def get_options_summary(df: pd.DataFrame) -> Dict:
    """Get summary statistics for options data"""
    if df.empty:
        return {}
    
    return {
        "total_options": len(df),
        "calls": len(df[df['option_type'] == 'C']),
        "puts": len(df[df['option_type'] == 'P']),
        "expiries": df['expiry'].nunique(),
        "strikes": df['strike'].nunique(),
        "avg_iv": df['iv'].mean(),
        "total_oi": df['oi'].sum(),
        "total_volume": df['volume'].sum(),
        "underlying_price": df['underlying_price'].iloc[0] if len(df) > 0 else 0,
        "timestamp": df['timestamp'].iloc[0] if len(df) > 0 else None
    }

if __name__ == "__main__":
    # Test the fetcher
    print("🧪 Testing NSE Options Fetcher...")
    
    df = fetch_nifty_chain("NIFTY")
    
    if df is not None:
        print("\n📊 Options Data Summary:")
        summary = get_options_summary(df)
        for key, value in summary.items():
            print(f"   {key}: {value}")
        
        print("\n📋 Sample Data:")
        print(df.head())
        
        print("\n✅ NSE Options Fetcher test successful!")
    else:
        print("\n❌ NSE Options Fetcher test failed!")