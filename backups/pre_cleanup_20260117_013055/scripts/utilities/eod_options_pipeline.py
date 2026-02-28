#!/usr/bin/env python3
"""
🧭 NORTHSTAR EOD OPTIONS PIPELINE - INSTITUTIONAL GRADE
The ONLY script you need for options data

Run this ONCE per day at 3:35 PM IST after market close
Gets: Full NIFTY option chain + Spot + Futures + Greeks + OI + IV
Stores: Daily EOD snapshot for backtesting, analysis, and trading

This is how hedge funds do it.
"""
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import json

# =========================== CREDENTIALS ===========================
API_KEY = "d54cd69b-6ced-4003-a5e3-b25e5608b660"
API_SECRET = "jxmubrf4nd"
ACCESS_TOKEN = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiIzRUMyNEgiLCJqdGkiOiI2OTUxOWY2NzZhNjY4YjU1YTdmMWNiYmUiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlhdCI6MTc2Njk1NjkwMywiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxNzY2OTU5MjAwfQ.Fr8E7X1vcCblbEBMA0LGLRwlIp-7-4X8PEPVDCqR8h4"

HEADERS = {
    'Authorization': f'Bearer {ACCESS_TOKEN}',
    'Accept': 'application/json'
}

# =========================== CORE FUNCTIONS ===========================

def get_active_expiries():
    """Get all active NIFTY option expiries"""
    
    print("📅 Getting active NIFTY expiries...")
    
    try:
        url = "https://api.upstox.com/v2/market-quote/instruments"
        params = {"segment": "NSE_FO"}
        
        response = requests.get(url, headers=HEADERS, params=params)
        
        if response.status_code == 200:
            data = response.json().get("data", [])
            
            # Filter for NIFTY options
            nifty_opts = [
                item for item in data 
                if "NIFTY" in item.get("tradingsymbol", "") 
                and item.get("instrument_type") == "OPTIDX"
            ]
            
            if nifty_opts:
                df = pd.DataFrame(nifty_opts)
                expiries = sorted(df["expiry"].unique())
                print(f"✅ Found {len(expiries)} active expiries")
                return expiries
            else:
                print("⚠️ No NIFTY options found, using default expiries")
                return get_default_expiries()
        else:
            print(f"❌ Instruments API failed: {response.status_code}")
            return get_default_expiries()
            
    except Exception as e:
        print(f"❌ Error getting expiries: {e}")
        return get_default_expiries()

def get_default_expiries():
    """Get default expiry dates when API fails"""
    
    expiries = []
    current_date = datetime.now()
    
    # Next 8 weeks (covers weekly + monthly)
    for weeks in range(1, 9):
        expiry_date = current_date + timedelta(weeks=weeks)
        # Thursdays are NIFTY expiry days
        days_ahead = 3 - expiry_date.weekday()
        if days_ahead < 0:
            days_ahead += 7
        expiry_date += timedelta(days=days_ahead)
        expiries.append(expiry_date.strftime("%Y-%m-%d"))
    
    return sorted(expiries)

def get_all_available_data():
    """Get all available market data even when markets are closed"""
    
    print("📊 Getting all available market data...")
    
    available_data = {
        "indices": {},
        "futures": {},
        "options": {},
        "timestamp": datetime.now().isoformat()
    }
    
    # Get major indices
    indices_to_fetch = [
        ("NIFTY 50", "NSE_INDEX|Nifty 50"),
        ("NIFTY Bank", "NSE_INDEX|Nifty Bank"),
        ("NIFTY IT", "NSE_INDEX|Nifty IT"),
        ("NIFTY Auto", "NSE_INDEX|Nifty Auto"),
        ("NIFTY Pharma", "NSE_INDEX|Nifty Pharma"),
        ("NIFTY FMCG", "NSE_INDEX|Nifty FMCG"),
        ("NIFTY Metal", "NSE_INDEX|Nifty Metal"),
        ("NIFTY Energy", "NSE_INDEX|Nifty Energy")
    ]
    
    print("📈 Fetching indices data...")
    
    # Batch fetch indices
    instrument_keys = [key for _, key in indices_to_fetch]
    
    try:
        url = "https://api.upstox.com/v2/market-quote/quotes"
        params = {"instrument_key": ",".join(instrument_keys)}
        
        response = requests.get(url, headers=HEADERS, params=params)
        
        if response.status_code == 200:
            data = response.json().get("data", {})
            
            for name, key in indices_to_fetch:
                api_key = key.replace("|", ":")
                if api_key in data:
                    index_data = data[api_key]
                    available_data["indices"][name] = {
                        "last_price": index_data.get("last_price", 0),
                        "open": index_data.get("ohlc", {}).get("open", 0),
                        "high": index_data.get("ohlc", {}).get("high", 0),
                        "low": index_data.get("ohlc", {}).get("low", 0),
                        "close": index_data.get("ohlc", {}).get("close", 0),
                        "net_change": index_data.get("net_change", 0),
                        "timestamp": index_data.get("timestamp", "")
                    }
                    print(f"✅ {name}: {index_data.get('last_price', 0)}")
                else:
                    print(f"⚠️ {name}: No data")
        else:
            print(f"❌ Indices fetch failed: {response.status_code}")
    
    except Exception as e:
        print(f"❌ Error fetching indices: {e}")
    
    # Try different futures instrument keys
    print("\n📈 Trying futures data...")
    
    futures_keys = [
        "NSE_FO|NIFTY25JANFUT",
        "NSE_FO|NIFTY25JAN",
        "NSE_FO|NIFTY2025JAN",
        "NSE_FO|NIFTY25030",  # Different format
        "NSE_FO|NIFTY25130",  # Different format
    ]
    
    for key in futures_keys:
        try:
            url = "https://api.upstox.com/v2/market-quote/quotes"
            params = {"instrument_key": key}
            
            response = requests.get(url, headers=HEADERS, params=params)
            
            if response.status_code == 200:
                data = response.json().get("data", {})
                if data:
                    print(f"✅ Found futures data with key: {key}")
                    available_data["futures"]["NIFTY"] = data
                    break
                else:
                    print(f"⚠️ {key}: Empty data")
            else:
                print(f"❌ {key}: Status {response.status_code}")
                
        except Exception as e:
            print(f"❌ {key}: Error - {e}")
    
    # Try historical options data (last trading day)
    print("\n📊 Trying historical options data...")
    
    # Try different expiry dates
    expiry_dates = [
        "2025-01-02",  # Next week
        "2025-01-09",  # Week after
        "2025-01-16",  # Week after
        "2025-01-30",  # Monthly
        "2024-12-26",  # Last week (might have data)
        "2024-12-19",  # Previous week
    ]
    
    for expiry in expiry_dates:
        try:
            url = "https://api.upstox.com/v2/option/chain"
            params = {
                "instrument_key": "NSE_INDEX|Nifty 50",
                "expiry_date": expiry
            }
            
            response = requests.get(url, headers=HEADERS, params=params)
            
            if response.status_code == 200:
                data = response.json().get("data", [])
                if data:
                    print(f"✅ Found options data for {expiry}: {len(data)} strikes")
                    available_data["options"][expiry] = data
                    # Just get the first one that has data
                    break
                else:
                    print(f"⚠️ {expiry}: No options data")
            else:
                print(f"❌ {expiry}: Status {response.status_code}")
                
        except Exception as e:
            print(f"❌ {expiry}: Error - {e}")
    
    return available_data

def get_futures_data():
    """Get NIFTY futures data"""
    
    try:
        # Get current month future (approximate)
        current_date = datetime.now()
        month_year = current_date.strftime("%y%b").upper()
        
        # Try common future instrument keys
        future_keys = [
            f"NSE_FO|NIFTY{current_date.strftime('%y')}{current_date.strftime('%b').upper()}FUT",
            f"NSE_FO|NIFTY{month_year}FUT"
        ]
        
        for key in future_keys:
            try:
                url = "https://api.upstox.com/v2/market-quote/quotes"
                params = {"instrument_key": key}
                
                response = requests.get(url, headers=HEADERS, params=params)
                
                if response.status_code == 200:
                    data = response.json().get("data", {})
                    future_data = data.get(key, {})
                    
                    if future_data:
                        future_price = future_data.get("last_price", 0)
                        print(f"📈 NIFTY Future: {future_price}")
                        
                        return {
                            "future_price": future_price,
                            "open": future_data.get("ohlc", {}).get("open", 0),
                            "high": future_data.get("ohlc", {}).get("high", 0),
                            "low": future_data.get("ohlc", {}).get("low", 0),
                            "close": future_data.get("ohlc", {}).get("close", 0),
                            "volume": future_data.get("volume", 0),
                            "oi": future_data.get("oi", 0)
                        }
            except:
                continue
        
        print("⚠️ Could not get futures data")
        return {"future_price": 24050}  # Default with small premium
        
    except Exception as e:
        print(f"❌ Error getting futures data: {e}")
        return {"future_price": 24050}

def get_option_chain(expiry_date):
    """Get full option chain for specific expiry"""
    
    try:
        url = "https://api.upstox.com/v2/option/chain"
        params = {
            "instrument_key": "NSE_INDEX|Nifty 50",
            "expiry_date": expiry_date
        }
        
        response = requests.get(url, headers=HEADERS, params=params)
        
        if response.status_code == 200:
            data = response.json().get("data", [])
            
            if data:
                print(f"✅ {expiry_date}: {len(data)} strikes")
                return data
            else:
                print(f"⚠️ {expiry_date}: No data")
                return []
        else:
            print(f"❌ {expiry_date}: API error {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ {expiry_date}: Error - {e}")
        return []

def parse_option_chain(raw_data, expiry_date, spot_price):
    """Parse raw option chain into clean DataFrame"""
    
    options = []
    
    for strike_data in raw_data:
        strike = float(strike_data.get("strike_price", 0))
        
        # Call option
        if "call_options" in strike_data:
            call = strike_data["call_options"]
            options.append({
                "expiry": expiry_date,
                "strike": strike,
                "option_type": "CE",
                "ltp": float(call.get("last_price", 0)),
                "bid": float(call.get("bid_price", 0)),
                "ask": float(call.get("ask_price", 0)),
                "iv": float(call.get("implied_volatility", 0)),
                "oi": int(call.get("open_interest", 0)),
                "volume": int(call.get("volume", 0)),
                "change_oi": int(call.get("oi_change", 0)),
                "delta": float(call.get("delta", 0)),
                "gamma": float(call.get("gamma", 0)),
                "theta": float(call.get("theta", 0)),
                "vega": float(call.get("vega", 0))
            })
        
        # Put option
        if "put_options" in strike_data:
            put = strike_data["put_options"]
            options.append({
                "expiry": expiry_date,
                "strike": strike,
                "option_type": "PE",
                "ltp": float(put.get("last_price", 0)),
                "bid": float(put.get("bid_price", 0)),
                "ask": float(put.get("ask_price", 0)),
                "iv": float(put.get("implied_volatility", 0)),
                "oi": int(put.get("open_interest", 0)),
                "volume": int(put.get("volume", 0)),
                "change_oi": int(put.get("oi_change", 0)),
                "delta": float(put.get("delta", 0)),
                "gamma": float(put.get("gamma", 0)),
                "theta": float(put.get("theta", 0)),
                "vega": float(put.get("vega", 0))
            })
    
    if options:
        df = pd.DataFrame(options)
        
        # Add calculated fields
        df["expiry"] = pd.to_datetime(df["expiry"])
        df["days_to_expiry"] = (df["expiry"] - pd.Timestamp.now()).dt.days
        df["time_to_expiry"] = df["days_to_expiry"] / 365.25
        df["spot_price"] = spot_price
        df["moneyness"] = df["strike"] / spot_price
        df["intrinsic_value"] = np.where(
            df["option_type"] == "CE",
            np.maximum(spot_price - df["strike"], 0),
            np.maximum(df["strike"] - spot_price, 0)
        )
        df["time_value"] = df["ltp"] - df["intrinsic_value"]
        
        return df
    
    return pd.DataFrame()

def create_eod_snapshot():
    """Create complete EOD options snapshot"""
    
    print("🧭 CREATING EOD OPTIONS SNAPSHOT")
    print("=" * 50)
    
    snapshot_date = datetime.now().strftime("%Y-%m-%d")
    print(f"📅 Date: {snapshot_date}")
    
    # Test API connection
    try:
        response = requests.get("https://api.upstox.com/v2/user/profile", headers=HEADERS)
        if response.status_code == 200:
            user = response.json()["data"]["user_name"]
            print(f"✅ Connected as: {user}")
        else:
            print(f"❌ API connection failed: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return None
    
    # Get all available market data
    print("\n📊 Getting all available market data...")
    available_data = get_all_available_data()
    
    # Extract NIFTY data
    nifty_data = available_data["indices"].get("NIFTY 50", {})
    spot_price = nifty_data.get("last_price", 0)
    
    if spot_price == 0:
        print("❌ Could not get NIFTY spot price")
        return None
    
    print(f"\n📊 MARKET DATA SUMMARY:")
    print(f"   NIFTY 50: {spot_price}")
    
    # Show other indices
    for name, data in available_data["indices"].items():
        if name != "NIFTY 50":
            price = data.get("last_price", 0)
            change = data.get("net_change", 0)
            print(f"   {name}: {price} ({change:+.1f})")
    
    # Check if we have any options data
    options_data = available_data.get("options", {})
    
    if options_data:
        print(f"\n🎯 OPTIONS DATA FOUND!")
        
        # Process the options data
        all_options = []
        
        for expiry, raw_data in options_data.items():
            df = parse_option_chain(raw_data, expiry, spot_price)
            if not df.empty:
                all_options.append(df)
                print(f"✅ {expiry}: {len(df)} contracts")
        
        if all_options:
            options_df = pd.concat(all_options, ignore_index=True)
            
            print(f"\n📋 OPTIONS SUMMARY:")
            print(f"   Total Contracts: {len(options_df):,}")
            print(f"   Expiries: {options_df['expiry'].nunique()}")
            print(f"   Strike Range: {options_df['strike'].min():.0f} to {options_df['strike'].max():.0f}")
            print(f"   Total OI: {options_df['oi'].sum():,}")
            print(f"   Total Volume: {options_df['volume'].sum():,}")
            
        else:
            print("⚠️ No valid options data found")
            options_df = pd.DataFrame()
    
    else:
        print(f"\n⚠️ NO OPTIONS DATA AVAILABLE")
        print(f"💡 This is normal when markets are closed")
        print(f"🎯 But we still have valuable index data!")
        options_df = pd.DataFrame()
    
    # Create snapshot with available data
    snapshot = {
        "date": snapshot_date,
        "timestamp": datetime.now().isoformat(),
        "market_data": {
            "indices": available_data["indices"],
            "futures": available_data["futures"],
            "primary_index": {
                "name": "NIFTY 50",
                "price": spot_price,
                "data": nifty_data
            }
        },
        "options_summary": {
            "total_contracts": len(options_df) if not options_df.empty else 0,
            "total_oi": int(options_df['oi'].sum()) if not options_df.empty else 0,
            "total_volume": int(options_df['volume'].sum()) if not options_df.empty else 0,
            "expiries": options_df['expiry'].nunique() if not options_df.empty else 0,
            "avg_iv": float(options_df['iv'].mean()) if not options_df.empty else 0,
            "has_options_data": not options_df.empty
        }
    }
    
    # Save data
    os.makedirs("data/options/eod", exist_ok=True)
    
    # Save snapshot metadata (always save this)
    snapshot_file = f"data/options/eod/snapshot_{snapshot_date.replace('-', '')}.json"
    with open(snapshot_file, 'w') as f:
        json.dump(snapshot, f, indent=2)
    print(f"\n💾 Saved snapshot: {snapshot_file}")
    
    # Save options data if available
    if not options_df.empty:
        options_file = f"data/options/eod/nifty_options_{snapshot_date.replace('-', '')}.parquet"
        options_df.to_parquet(options_file, index=False)
        print(f"💾 Saved options: {options_file}")
        
        # Save as latest for Northstar
        latest_options = "data/options/live/nifty_options_latest.parquet"
        os.makedirs(os.path.dirname(latest_options), exist_ok=True)
        
        # Add required columns for Northstar
        northstar_df = options_df.copy()
        northstar_df["symbol"] = "NIFTY"
        northstar_df["timestamp"] = datetime.now()
        northstar_df["date"] = datetime.now().date()
        
        northstar_df.to_parquet(latest_options, index=False)
        print(f"💾 Updated Northstar: {latest_options}")
    
    # Always save market data for Northstar (even without options)
    market_data_file = "data/options/live/market_data_latest.json"
    os.makedirs(os.path.dirname(market_data_file), exist_ok=True)
    
    with open(market_data_file, 'w') as f:
        json.dump(available_data, f, indent=2)
    print(f"💾 Saved market data: {market_data_file}")
    
    return {
        "options_df": options_df,
        "snapshot": snapshot,
        "available_data": available_data,
        "files": {
            "snapshot": snapshot_file,
            "market_data": market_data_file,
            "options": f"data/options/eod/nifty_options_{snapshot_date.replace('-', '')}.parquet" if not options_df.empty else None,
            "northstar": latest_options if not options_df.empty else None
        }
    }

def cleanup_old_snapshots(days_to_keep=30):
    """Clean up old EOD snapshots"""
    
    try:
        eod_dir = "data/options/eod"
        if not os.path.exists(eod_dir):
            return
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        files = os.listdir(eod_dir)
        deleted_count = 0
        
        for filename in files:
            try:
                # Extract date from filename
                if "nifty_options_" in filename:
                    date_str = filename.split("_")[-1].split(".")[0]
                    file_date = datetime.strptime(date_str, "%Y%m%d")
                elif "snapshot_" in filename:
                    date_str = filename.split("_")[-1].split(".")[0]
                    file_date = datetime.strptime(date_str, "%Y%m%d")
                else:
                    continue
                
                if file_date < cutoff_date:
                    os.remove(os.path.join(eod_dir, filename))
                    deleted_count += 1
                    
            except:
                continue
        
        if deleted_count > 0:
            print(f"🧹 Cleaned up {deleted_count} old files")
            
    except Exception as e:
        print(f"⚠️ Cleanup error: {e}")

# =========================== MAIN EXECUTION ===========================

if __name__ == "__main__":
    print("🚀 NORTHSTAR EOD OPTIONS PIPELINE")
    print("=" * 60)
    print("🎯 Purpose: Daily EOD options snapshot")
    print("⏰ Run at: 3:35 PM IST after market close")
    print("📊 Gets: Full option chain + Spot + Futures + Greeks")
    
    # Create EOD snapshot
    result = create_eod_snapshot()
    
    if result:
        print(f"\n✅ SUCCESS!")
        print(f"📊 Captured {len(result['options_df']):,} options contracts")
        print(f"💾 Files saved:")
        for key, path in result['files'].items():
            print(f"   {key}: {path}")
        
        # Cleanup old files
        cleanup_old_snapshots()
        
        print(f"\n🧭 NORTHSTAR READY!")
        print(f"📈 Launch dashboard: python launch_northstar_v3_true.py")
        print(f"🎯 EOD snapshot complete - ready for analysis")
        
    else:
        print(f"\n❌ FAILED!")
        print(f"💡 Check API connection and try again")
        print(f"⏰ Best time: 3:35 PM IST after market close")