#!/usr/bin/env python3
"""
Market Hours Manager - Production Grade
Handles NSE market hours and trading calendar
"""
from datetime import datetime, time
import pytz
from typing import Tuple

# NSE timezone
IST = pytz.timezone('Asia/Kolkata')

# NSE trading hours
MARKET_OPEN = time(9, 15)   # 9:15 AM IST
MARKET_CLOSE = time(15, 30)  # 3:30 PM IST

# NSE holidays (major ones - should be updated annually)
NSE_HOLIDAYS_2025 = [
    "2025-01-26",  # Republic Day
    "2025-03-14",  # Holi
    "2025-04-14",  # Ram Navami
    "2025-04-18",  # Good Friday
    "2025-05-01",  # Maharashtra Day
    "2025-08-15",  # Independence Day
    "2025-10-02",  # Gandhi Jayanti
    "2025-11-01",  # Diwali Laxmi Puja
    "2025-11-03",  # Diwali Balipratipada
    "2025-12-25",  # Christmas
]

def get_ist_time() -> datetime:
    """Get current time in IST"""
    return datetime.now(IST)

def is_market_day(date: datetime = None) -> bool:
    """Check if given date is a market day (weekday, not holiday)"""
    if date is None:
        date = get_ist_time()
    
    # Check if weekday (Monday=0, Sunday=6)
    if date.weekday() >= 5:  # Saturday or Sunday
        return False
    
    # Check if holiday
    date_str = date.strftime("%Y-%m-%d")
    if date_str in NSE_HOLIDAYS_2025:
        return False
    
    return True

def is_market_hours(dt: datetime = None) -> bool:
    """Check if given time is within market hours"""
    if dt is None:
        dt = get_ist_time()
    
    # Must be a market day
    if not is_market_day(dt):
        return False
    
    # Check time
    current_time = dt.time()
    return MARKET_OPEN <= current_time <= MARKET_CLOSE

def get_market_status() -> Tuple[str, str]:
    """
    Get current market status
    Returns: (status, description)
    """
    now = get_ist_time()
    
    if not is_market_day(now):
        if now.weekday() >= 5:
            return "CLOSED", "Weekend"
        else:
            return "CLOSED", "Holiday"
    
    current_time = now.time()
    
    if current_time < MARKET_OPEN:
        return "PRE_MARKET", f"Opens at {MARKET_OPEN.strftime('%H:%M')} IST"
    elif current_time > MARKET_CLOSE:
        return "POST_MARKET", f"Closed at {MARKET_CLOSE.strftime('%H:%M')} IST"
    else:
        return "OPEN", "Market is open"

def time_to_market_open() -> int:
    """Get minutes until market opens (0 if market is open)"""
    now = get_ist_time()
    
    if is_market_hours(now):
        return 0
    
    # Find next market open
    next_open = now.replace(hour=MARKET_OPEN.hour, minute=MARKET_OPEN.minute, second=0, microsecond=0)
    
    # If today's market is already closed, move to next market day
    if now.time() > MARKET_CLOSE or not is_market_day(now):
        next_open = next_open.replace(day=now.day + 1)
        
        # Keep moving forward until we find a market day
        while not is_market_day(next_open):
            next_open = next_open.replace(day=next_open.day + 1)
    
    delta = next_open - now
    return int(delta.total_seconds() / 60)

def should_fetch_live_data() -> bool:
    """Determine if we should attempt to fetch live data from NSE"""
    status, _ = get_market_status()
    
    # Only fetch during market hours or slightly before/after
    if status == "OPEN":
        return True
    
    # Allow fetching 15 minutes before market open (pre-market data)
    if status == "PRE_MARKET":
        minutes_to_open = time_to_market_open()
        return minutes_to_open <= 15
    
    # Allow fetching 30 minutes after market close (post-market data)
    if status == "POST_MARKET":
        now = get_ist_time()
        market_close_today = now.replace(hour=MARKET_CLOSE.hour, minute=MARKET_CLOSE.minute, second=0, microsecond=0)
        minutes_since_close = (now - market_close_today).total_seconds() / 60
        return minutes_since_close <= 30
    
    return False

def get_market_info() -> dict:
    """Get comprehensive market information"""
    now = get_ist_time()
    status, description = get_market_status()
    
    return {
        "current_time_ist": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "status": status,
        "description": description,
        "is_market_day": is_market_day(now),
        "is_market_hours": is_market_hours(now),
        "should_fetch_live": should_fetch_live_data(),
        "minutes_to_open": time_to_market_open(),
        "market_open": MARKET_OPEN.strftime("%H:%M"),
        "market_close": MARKET_CLOSE.strftime("%H:%M"),
        "weekday": now.strftime("%A")
    }

if __name__ == "__main__":
    print("🕐 NSE Market Hours Status")
    print("=" * 40)
    
    info = get_market_info()
    
    for key, value in info.items():
        print(f"{key.replace('_', ' ').title()}: {value}")
    
    print("\n" + "=" * 40)
    
    if info["should_fetch_live"]:
        print("✅ LIVE DATA FETCH: Recommended")
        print("💡 NSE API should return live options data")
    else:
        print("❌ LIVE DATA FETCH: Not recommended")
        print("💡 Use stored data or wait for market hours")
        
        if info["status"] == "PRE_MARKET":
            print(f"⏰ Market opens in {info['minutes_to_open']} minutes")
        elif info["status"] == "POST_MARKET":
            print("📊 Market closed - use end-of-day data")
        else:
            print("🏖️ Market closed - weekend/holiday")