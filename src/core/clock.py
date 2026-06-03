#!/usr/bin/env python3
"""
⏰ MARKET CLOCK - THE TIMEKEEPER
Time as a First-Class Citizen in the Living Investment Organism

This is the Market Clock that drives all system behavior through time events.
Time becomes the heartbeat that coordinates all organs in the living system.

Key Features:
- Market time management with phase detection
- Time-based event emission to all organs via Event Bus
- Market hours awareness and lifecycle management
- Heartbeat coordination for continuous operation
"""

from src.cohesion.dependency_container import get_dependency_container

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
import pytz
import warnings
warnings.filterwarnings('ignore')

# Import Event Bus for time event emission
try:
    from src.core.events import EventBus, Event, EventType, EventPriority
except ImportError:
    EventBus = None
    Event = None
    EventType = None
    EventPriority = None

class TimeEvent(Enum):
    """Time-based events that drive organ behavior"""
    PRE_OPEN = "pre_open"
    OPEN = "open"
    INTRADAY = "intraday"
    CLOSE = "close"
    OVERNIGHT = "overnight"
    WEEKLY_REBALANCE = "weekly_rebalance"
    MONTHLY_REVIEW = "monthly_review"
    HEARTBEAT = "heartbeat"

class MarketPhase(Enum):
    """Market phases throughout the day"""
    CLOSED = "closed"
    PRE_MARKET = "pre_market"
    OPEN = "open"
    INTRADAY = "intraday"
    CLOSE = "close"
    AFTER_HOURS = "after_hours"
    OVERNIGHT = "overnight"

@dataclass
class MarketTime:
    """Market time with phase and event information"""
    timestamp: datetime
    phase: MarketPhase
    market_day: int
    is_trading_day: bool
    next_event: Optional[TimeEvent] = None
    time_to_next_event: Optional[timedelta] = None
    market_open: Optional[datetime] = None
    market_close: Optional[datetime] = None

class MarketClock:
    """
    Market Clock - Time as First-Class Citizen
    
    Manages market time and emits time-based events that drive
    all organ behavior in the living system.
    """
    
    def __init__(self, timezone='US/Eastern', event_bus=None):
        self.timezone = pytz.timezone(timezone)
        self.event_listeners: List[Callable] = []
        self.event_bus = event_bus  # Event Bus for nervous system integration
        
        # Market hours (US Eastern Time)
        self.market_open_time = time(9, 30)  # 9:30 AM
        self.market_close_time = time(16, 0)  # 4:00 PM
        self.pre_market_start = time(4, 0)    # 4:00 AM
        self.after_hours_end = time(20, 0)    # 8:00 PM
        
        # Weekly rebalance (Friday after close)
        self.rebalance_day = 4  # Friday (0=Monday)
        
        # Current state
        self.current_time = None
        self.current_phase = MarketPhase.CLOSED
        self.last_event = None
        self.market_day_counter = 0
        
        # Event history
        self.event_history: List[Dict] = []
        
        # Load market calendar (simplified - could be enhanced with holidays)
        self.trading_days = self._generate_trading_calendar()
    
    def _generate_trading_calendar(self) -> List[datetime]:
        """Generate trading calendar (weekdays only for now)"""
        
        # Generate next 365 trading days (weekdays)
        trading_days = []
        current_date = datetime.now().date()
        
        for i in range(500):  # Look ahead 500 days
            check_date = current_date + timedelta(days=i)
            
            # Skip weekends (Saturday=5, Sunday=6)
            if check_date.weekday() < 5:
                trading_days.append(check_date)
        
        return trading_days
    
    def is_trading_day(self, date: datetime = None) -> bool:
        """Check if given date is a trading day"""
        
        if date is None:
            date = datetime.now()
        
        return date.date() in self.trading_days
    
    def get_market_hours(self, date: datetime = None) -> Dict[str, datetime]:
        """Get market hours for given date"""
        
        if date is None:
            date = datetime.now()
        
        # Convert to market timezone
        market_date = date.astimezone(self.timezone).date()
        
        market_open = self.timezone.localize(
            datetime.combine(market_date, self.market_open_time)
        )
        market_close = self.timezone.localize(
            datetime.combine(market_date, self.market_close_time)
        )
        pre_market = self.timezone.localize(
            datetime.combine(market_date, self.pre_market_start)
        )
        after_hours = self.timezone.localize(
            datetime.combine(market_date, self.after_hours_end)
        )
        
        return {
            'pre_market_start': pre_market,
            'market_open': market_open,
            'market_close': market_close,
            'after_hours_end': after_hours
        }
    
    def determine_market_phase(self, timestamp: datetime = None) -> MarketPhase:
        """Determine current market phase"""
        
        if timestamp is None:
            timestamp = datetime.now()
        
        # Convert to market timezone
        market_time = timestamp.astimezone(self.timezone)
        
        # Check if trading day
        if not self.is_trading_day(market_time):
            return MarketPhase.OVERNIGHT
        
        # Get market hours for this day
        hours = self.get_market_hours(market_time)
        
        # Determine phase
        if market_time < hours['pre_market_start']:
            return MarketPhase.OVERNIGHT
        elif market_time < hours['market_open']:
            return MarketPhase.PRE_MARKET
        elif market_time < hours['market_close']:
            return MarketPhase.INTRADAY
        elif market_time < hours['after_hours_end']:
            return MarketPhase.AFTER_HOURS
        else:
            return MarketPhase.OVERNIGHT
    
    def get_next_event(self, timestamp: datetime = None) -> tuple[TimeEvent, datetime]:
        """Get next time event and when it occurs"""
        
        if timestamp is None:
            timestamp = datetime.now()
        
        market_time = timestamp.astimezone(self.timezone)
        current_phase = self.determine_market_phase(market_time)
        
        # Get today's market hours
        hours = self.get_market_hours(market_time)
        
        # Determine next event based on current phase
        if current_phase == MarketPhase.OVERNIGHT:
            # Next event is pre-market start
            if self.is_trading_day(market_time):
                return TimeEvent.PRE_OPEN, hours['pre_market_start']
            else:
                # Find next trading day
                next_trading_day = self._get_next_trading_day(market_time.date())
                next_hours = self.get_market_hours(
                    datetime.combine(next_trading_day, time())
                )
                return TimeEvent.PRE_OPEN, next_hours['pre_market_start']
        
        elif current_phase == MarketPhase.PRE_MARKET:
            return TimeEvent.OPEN, hours['market_open']
        
        elif current_phase == MarketPhase.INTRADAY:
            # Check if it's Friday for weekly rebalance
            if market_time.weekday() == self.rebalance_day:
                # 30 minutes before close for rebalance
                rebalance_time = hours['market_close'] - timedelta(minutes=30)
                if market_time < rebalance_time:
                    return TimeEvent.WEEKLY_REBALANCE, rebalance_time
            
            return TimeEvent.CLOSE, hours['market_close']
        
        elif current_phase == MarketPhase.AFTER_HOURS:
            return TimeEvent.OVERNIGHT, hours['after_hours_end']
        
        else:
            # Default to next pre-market
            next_trading_day = self._get_next_trading_day(market_time.date())
            next_hours = self.get_market_hours(
                datetime.combine(next_trading_day, time())
            )
            return TimeEvent.PRE_OPEN, next_hours['pre_market_start']
    
    def _get_next_trading_day(self, current_date: datetime.date) -> datetime.date:
        """Get next trading day after current date"""
        
        for trading_day in self.trading_days:
            if trading_day > current_date:
                return trading_day
        
        # Fallback - just add days until we hit a weekday
        next_date = current_date + timedelta(days=1)
        while next_date.weekday() >= 5:  # Skip weekends
            next_date += timedelta(days=1)
        
        return next_date
    
    def tick(self) -> MarketTime:
        """Advance market time and emit events if needed"""
        
        now = datetime.now()
        self.current_time = now
        
        # Determine current phase
        new_phase = self.determine_market_phase(now)
        
        # Check for phase transitions and emit events
        if new_phase != self.current_phase:
            self._emit_phase_transition_event(self.current_phase, new_phase)
            self.current_phase = new_phase
        
        # Get next event
        next_event, next_event_time = self.get_next_event(now)
        time_to_next = next_event_time - now.astimezone(self.timezone)
        
        # Check for special events
        self._check_special_events(now)
        
        # Update market day counter
        if self.is_trading_day(now) and new_phase == MarketPhase.INTRADAY:
            if self.last_event != TimeEvent.OPEN:
                self.market_day_counter += 1
        
        # Create market time object
        market_time = MarketTime(
            timestamp=now,
            phase=new_phase,
            market_day=self.market_day_counter,
            is_trading_day=self.is_trading_day(now),
            next_event=next_event,
            time_to_next_event=time_to_next,
            market_open=self.get_market_hours(now)['market_open'],
            market_close=self.get_market_hours(now)['market_close']
        )
        
        # Emit heartbeat event
        self.emit_time_event(TimeEvent.HEARTBEAT, market_time)
        
        return market_time
    
    def _emit_phase_transition_event(self, old_phase: MarketPhase, new_phase: MarketPhase):
        """Emit event for phase transitions"""
        
        # Map phase transitions to events
        event_mapping = {
            (MarketPhase.OVERNIGHT, MarketPhase.PRE_MARKET): TimeEvent.PRE_OPEN,
            (MarketPhase.PRE_MARKET, MarketPhase.INTRADAY): TimeEvent.OPEN,
            (MarketPhase.INTRADAY, MarketPhase.AFTER_HOURS): TimeEvent.CLOSE,
            (MarketPhase.AFTER_HOURS, MarketPhase.OVERNIGHT): TimeEvent.OVERNIGHT,
        }
        
        event = event_mapping.get((old_phase, new_phase))
        if event:
            self.emit_time_event(event)
            self.last_event = event
    
    def _check_special_events(self, timestamp: datetime):
        """Check for special time-based events"""
        
        market_time = timestamp.astimezone(self.timezone)
        
        # Weekly rebalance (Friday, 30 minutes before close)
        if (market_time.weekday() == self.rebalance_day and 
            self.current_phase == MarketPhase.INTRADAY):
            
            hours = self.get_market_hours(market_time)
            rebalance_time = hours['market_close'] - timedelta(minutes=30)
            
            # Check if we just hit rebalance time (within 1 minute)
            if abs((market_time - rebalance_time).total_seconds()) < 60:
                self.emit_time_event(TimeEvent.WEEKLY_REBALANCE)
        
        # Monthly review (first trading day of month)
        if (market_time.day <= 3 and  # First few days of month
            self.is_trading_day(market_time) and
            self.current_phase == MarketPhase.INTRADAY):
            
            # Check if this is first trading day of month
            month_start = market_time.replace(day=1)
            first_trading_day = None
            
            for day in range(1, 8):  # Check first week
                check_date = month_start.replace(day=day)
                if self.is_trading_day(check_date):
                    first_trading_day = check_date.date()
                    break
            
            if first_trading_day == market_time.date():
                self.emit_time_event(TimeEvent.MONTHLY_REVIEW)
    
    def emit_time_event(self, event: TimeEvent, market_time: MarketTime = None):
        """Emit time-based event to all listeners and Event Bus"""
        
        if market_time is None:
            market_time = MarketTime(
                timestamp=datetime.now(),
                phase=self.current_phase,
                market_day=self.market_day_counter,
                is_trading_day=self.is_trading_day()
            )
        
        # Create event data
        event_data = {
            'timestamp': datetime.now().isoformat(),
            'event': event.value,
            'market_time': market_time,
            'phase': self.current_phase.value,
            'is_trading_day': market_time.is_trading_day
        }
        
        # Add to event history
        self.event_history.append(event_data)
        
        # Keep history manageable
        if len(self.event_history) > 1000:
            self.event_history = self.event_history[-500:]
        
        # Emit to Event Bus if available
        if self.event_bus and Event and EventType:
            try:
                bus_event = Event(
                    event_id="",
                    timestamp=datetime.now(),
                    event_type=EventType.TIME_EVENT,
                    source="market_clock",
                    priority=EventPriority.HIGH if event in [TimeEvent.OPEN, TimeEvent.CLOSE, TimeEvent.WEEKLY_REBALANCE] else EventPriority.NORMAL,
                    data={
                        'time_event': event.value,
                        'market_phase': self.current_phase.value,
                        'is_trading_day': market_time.is_trading_day,
                        'market_day': market_time.market_day,
                        'next_event': market_time.next_event.value if market_time.next_event else None
                    },
                    tags=['time', 'market', event.value]
                )
                self.event_bus.emit_event(bus_event)
            except Exception as e:
                print(f"⚠️ Error emitting time event to Event Bus: {e}")
        
        # Notify all listeners
        for listener in self.event_listeners:
            try:
                listener(event, market_time)
            except Exception as e:
                print(f"⚠️ Error in time event listener: {e}")
    
    def add_event_listener(self, listener: Callable):
        """Add event listener for time events"""
        self.event_listeners.append(listener)
    
    def remove_event_listener(self, listener: Callable):
        """Remove event listener"""
        if listener in self.event_listeners:
            self.event_listeners.remove(listener)
    
    def is_market_alive(self) -> bool:
        """Check if markets are active (trading day and reasonable hours)"""
        
        now = datetime.now()
        
        # Always alive during trading hours
        if self.current_phase in [MarketPhase.PRE_MARKET, MarketPhase.INTRADAY]:
            return True
        
        # Also alive during after hours on trading days
        if (self.current_phase == MarketPhase.AFTER_HOURS and 
            self.is_trading_day(now)):
            return True
        
        # Alive overnight if next day is trading day (for preparation)
        if self.current_phase == MarketPhase.OVERNIGHT:
            next_trading_day = self._get_next_trading_day(now.date())
            # Alive if next trading day is within 24 hours
            time_to_next = datetime.combine(next_trading_day, time()) - now
            return time_to_next.total_seconds() < 24 * 3600
        
        return False
    
    def get_time_until_next_event(self) -> timedelta:
        """Get time until next major event"""
        
        next_event, next_event_time = self.get_next_event()
        return next_event_time - datetime.now().astimezone(self.timezone)
    
    def get_market_status(self) -> Dict[str, Any]:
        """Get comprehensive market status"""
        
        now = datetime.now()
        market_time = self.tick()
        
        return {
            'timestamp': now.isoformat(),
            'market_time': {
                'phase': self.current_phase.value,
                'is_trading_day': market_time.is_trading_day,
                'market_day': market_time.market_day,
                'next_event': market_time.next_event.value if market_time.next_event else None,
                'time_to_next_event': str(market_time.time_to_next_event) if market_time.time_to_next_event else None
            },
            'market_hours': {
                'open': market_time.market_open.isoformat() if market_time.market_open else None,
                'close': market_time.market_close.isoformat() if market_time.market_close else None
            },
            'system_status': {
                'market_alive': self.is_market_alive(),
                'event_listeners': len(self.event_listeners),
                'recent_events': len([e for e in self.event_history if 
                                    (datetime.now() - datetime.fromisoformat(e['timestamp'].replace('Z', '+00:00'))).total_seconds() < 3600])
            }
        }
    
    def save_clock_state(self):
        """Save clock state for persistence"""
        
        clock_state = {
            'timestamp': datetime.now().isoformat(),
            'current_phase': self.current_phase.value,
            'market_day_counter': self.market_day_counter,
            'last_event': self.last_event.value if self.last_event else None,
            'event_history': self.event_history[-100:],  # Keep last 100 events
            'market_status': self.get_market_status()
        }
        
        # Save to file
        clock_file = 'data/state/market_clock_state.json'
        os.makedirs(os.path.dirname(clock_file), exist_ok=True)
        
        with open(clock_file, 'w') as f:
            json.dump(clock_state, f, indent=2, default=str)

def main():
    """Test Market Clock with Event Bus Integration"""
    
    print("⏰ TESTING MARKET CLOCK WITH EVENT BUS INTEGRATION")
    print("=" * 60)
    
    # Create Event Bus
    if EventBus:
        print("\n📡 Creating Event Bus...")
        event_bus = EventBus()
        
        # Event listener for time events
        def time_event_listener(event):
            if hasattr(event, 'data') and 'time_event' in event.data:
                print(f"   🕐 Time Event via Bus: {event.data['time_event']} (Phase: {event.data['market_phase']})")
        
        event_bus.subscribe(EventType.TIME_EVENT, time_event_listener)
        
        # Create market clock with Event Bus
        clock = MarketClock(event_bus=event_bus)
        print("   Market Clock connected to Event Bus")
    else:
        print("\n⚠️ Event Bus not available, using standalone mode")
        clock = MarketClock()
    
    # Test current time
    print("\n📅 Current Market Time:")
    market_time = clock.tick()
    print(f"   Timestamp: {market_time.timestamp}")
    print(f"   Phase: {market_time.phase.value}")
    print(f"   Trading Day: {market_time.is_trading_day}")
    print(f"   Market Day #: {market_time.market_day}")
    print(f"   Next Event: {market_time.next_event.value if market_time.next_event else 'None'}")
    print(f"   Time to Next: {market_time.time_to_next_event}")
    
    # Test market status
    print(f"\n🏛️ Market Status:")
    status = clock.get_market_status()
    print(f"   Market Alive: {status['system_status']['market_alive']}")
    print(f"   Current Phase: {status['market_time']['phase']}")
    print(f"   Next Event: {status['market_time']['next_event']}")
    
    # Test event listener
    def test_listener(event: TimeEvent, market_time: MarketTime):
        print(f"   📡 Direct Event: {event.value} at {market_time.timestamp}")
    
    clock.add_event_listener(test_listener)
    
    # Simulate a few ticks
    print(f"\n⚡ Simulating Clock Ticks with Event Bus:")
    for i in range(3):
        clock.tick()
    
    # Test manual event emission
    print(f"\n🎯 Testing Manual Event Emission:")
    clock.emit_time_event(TimeEvent.INTRADAY)
    
    # Test Event Bus statistics if available
    if EventBus and event_bus:
        print(f"\n📊 Event Bus Statistics:")
        stats = event_bus.get_event_statistics()
        print(f"   Total Events: {stats['total_events']}")
        print(f"   Time Events: {stats['event_types'].get('time_event', 0)}")
    
    # Test save state
    print(f"\n💾 Saving Clock State:")
    clock.save_clock_state()
    print("   Clock state saved successfully")
    
    print(f"\n✅ Market Clock with Event Bus integration test successful!")
    print(f"   Time is now driving the living system through the nervous system!")
    
    return True

if __name__ == "__main__":
    main()