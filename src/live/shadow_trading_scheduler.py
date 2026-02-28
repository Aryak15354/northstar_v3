"""
Shadow Trading Scheduler

Manages automated scheduling of shadow trading operations.
"""

import logging
try:
    import schedule  # type: ignore
except Exception:
    schedule = None
import time
from datetime import datetime, timezone
from typing import Optional

class ShadowTradingScheduler:
    """Automated shadow trading scheduler"""
    
    def __init__(self, trader, data_directory: str):
        self.trader = trader
        self.data_directory = data_directory
        self.logger = logging.getLogger(__name__)
        
        # Market holidays (simplified)
        self.market_holidays_2026 = [
            '2026-01-26',  # Republic Day
            '2026-03-14',  # Holi
            '2026-08-15',  # Independence Day
            '2026-10-02',  # Gandhi Jayanti
        ]
    
    def is_market_day(self, date: datetime) -> bool:
        """Check if given date is a market day"""
        if date.weekday() >= 5:  # Weekend
            return False
        
        date_str = date.strftime("%Y-%m-%d")
        return date_str not in self.market_holidays_2026
    
    def run_scheduled_trading(self) -> None:
        """Run scheduled trading if market is open"""
        today = datetime.now(timezone.utc)
        
        if self.is_market_day(today):
            self.logger.info(f"Running scheduled shadow trading for {today.date()}")
            result = self.trader.execute_daily_trading(today)
            self.logger.info(f"Scheduled trading result: {result.get('status', 'unknown')}")
        else:
            self.logger.info(f"Market closed on {today.date()} - skipping trading")
    
    def start_scheduler(self) -> None:
        """Start the automated scheduler"""
        if schedule is None:
            raise RuntimeError(
                "The 'schedule' package is not installed. "
                "Install it to use automated mode."
            )

        # Schedule trading at 4:00 PM on weekdays
        schedule.every().monday.at("16:00").do(self.run_scheduled_trading)
        schedule.every().tuesday.at("16:00").do(self.run_scheduled_trading)
        schedule.every().wednesday.at("16:00").do(self.run_scheduled_trading)
        schedule.every().thursday.at("16:00").do(self.run_scheduled_trading)
        schedule.every().friday.at("16:00").do(self.run_scheduled_trading)
        
        self.logger.info("Shadow trading scheduler started")
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            self.logger.info("Scheduler stopped by user")
