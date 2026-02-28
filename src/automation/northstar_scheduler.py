#!/usr/bin/env python3
"""
Northstar Automated Scheduler
Handles automatic RBI data updates and macro pipeline execution
"""
import os
import sys
import time
import subprocess
from datetime import datetime, timedelta
import logging
from pathlib import Path

try:
    import schedule
except ImportError:
    schedule = None

# Setup logging
LOG_DIR = "data/automation/logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'northstar_scheduler.log')),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class NorthstarScheduler:
    """Automated scheduler for Northstar updates"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.update_script = self.project_root / "run_daily_v3.py"
        # Guaranteed cycle runner (strict export sync + live fallback producer)
        self.sentiment_script = self.project_root / "ns_uso/scripts/run_v3_sentiment_cycle.py"
        self.refresh_script = self.project_root / "scripts/runners/refresh_v3_artifacts.py"
        self.last_run_file = LOG_DIR + "/last_successful_run.txt"
        
    def run_update(self, trigger_type="scheduled"):
        """Run the complete Northstar update"""
        logger.info(f"🚀 Starting Northstar update (trigger: {trigger_type})")
        
        try:
            # Change to project directory
            os.chdir(self.project_root)
            
            # Run the update script
            result = subprocess.run([
                sys.executable, str(self.update_script)
            ], capture_output=True, text=True, timeout=3600)  # 1 hour timeout
            
            if result.returncode == 0:
                logger.info("✅ Northstar update completed successfully")
                
                # Record successful run
                with open(self.last_run_file, 'w') as f:
                    f.write(datetime.now().isoformat())
                
                # Log key outputs
                self.log_system_status()
                
                return True
            else:
                logger.error(f"❌ Northstar update failed with code {result.returncode}")
                logger.error(f"STDOUT: {result.stdout}")
                logger.error(f"STDERR: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("❌ Northstar update timed out (>1 hour)")
            return False
        except Exception as e:
            logger.error(f"❌ Northstar update error: {e}")
            return False
    
    def log_system_status(self):
        """Log current system status"""
        try:
            import pandas as pd
            
            # Check regime
            regime_file = self.project_root / "data/macro/factors/macro_score.parquet"
            if regime_file.exists():
                regime_df = pd.read_parquet(regime_file)
                if len(regime_df) > 0:
                    latest = regime_df.iloc[-1]
                    logger.info(f"📊 Current Regime: {latest.get('Regime', 'Unknown')}")
                    logger.info(f"📊 MacroScore: {latest.get('MacroScore', 0):.3f}")
            
            # Check risk budget
            risk_file = self.project_root / "data/macro/factors/risk_budget.parquet"
            if risk_file.exists():
                risk_df = pd.read_parquet(risk_file)
                if len(risk_df) > 0:
                    latest = risk_df.iloc[-1]
                    exposure = latest.get('Max_Equity_Exposure', 0)
                    logger.info(f"📊 Max Equity Exposure: {exposure:.1%}")
            
            # Check emergency status
            emergency_file = self.project_root / "data/risk/emergency_signal.parquet"
            if emergency_file.exists():
                emergency_df = pd.read_parquet(emergency_file)
                if len(emergency_df) > 0:
                    latest = emergency_df.iloc[-1]
                    emergency = latest.get('Emergency', False)
                    logger.info(f"🚨 Emergency Status: {'ACTIVE' if emergency else 'NORMAL'}")
                    
        except Exception as e:
            logger.warning(f"Could not log system status: {e}")
    
    def check_market_hours(self):
        """Check if markets are open using configurable market hours"""
        from src.cohesion.market_configuration import get_active_market_config
        
        market_config = get_active_market_config()
        if not market_config:
            # Fallback to default behavior if no market config
            print("⚠️ No market configuration found, using default hours")
            now = datetime.now()
            if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
                return False
            market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
            market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
            return market_open <= now <= market_close
        
        now = datetime.now()
        
        # Check if it's a trading day using market configuration
        if not market_config.is_trading_day(now):
            return False
        
        # Check market hours using configuration
        return market_config.trading_hours.is_market_open(now)
    
    def should_run_update(self):
        """Determine if we should run an update"""
        
        # Check if we've run recently
        if os.path.exists(self.last_run_file):
            with open(self.last_run_file, 'r') as f:
                last_run_str = f.read().strip()
            
            try:
                last_run = datetime.fromisoformat(last_run_str)
                hours_since_last = (datetime.now() - last_run).total_seconds() / 3600
                
                # Don't run if we've run in the last 6 hours
                if hours_since_last < 6:
                    logger.info(f"⏰ Skipping update - last run {hours_since_last:.1f} hours ago")
                    return False
            except:
                pass
        
        return True
    
    def weekly_update(self):
        """Weekly comprehensive update"""
        if self.should_run_update():
            logger.info("📅 Running weekly comprehensive update")
            self.run_update("weekly")
        else:
            logger.info("📅 Skipping weekly update - too recent")
    
    def daily_check(self):
        """Daily health check and light update"""
        if not self.check_market_hours():
            logger.info("🕐 Markets closed - skipping daily check")
            return
        
        logger.info("📅 Running daily health check")

        # Weekend-only policy: do not run weekly rebalance on weekdays.
        checks = [
            self.project_root / "data/processed/portfolio_weights.parquet",
            self.project_root / "data/processed/market_state.parquet",
            self.project_root / "data/processed/risk_state.parquet",
        ]
        missing = [str(p) for p in checks if not p.exists()]
        if missing:
            logger.warning("⚠️ Daily health check missing artifacts: %s", missing)
        else:
            logger.info("✅ Daily health check completed (rebalance deferred to weekend run)")
    
    def emergency_check(self):
        """Check for emergency conditions"""
        try:
            emergency_file = self.project_root / "data/risk/emergency_signal.parquet"
            if emergency_file.exists():
                import pandas as pd
                emergency_df = pd.read_parquet(emergency_file)
                
                if len(emergency_df) > 0:
                    latest = emergency_df.iloc[-1]
                    if latest.get('Emergency', False):
                        logger.critical("🚨 EMERGENCY CONDITION DETECTED!")
                        logger.critical("🚨 REDUCE ALL POSITIONS IMMEDIATELY!")
                        
                        # Could add email/SMS alerts here
                        
        except Exception as e:
            logger.error(f"Emergency check failed: {e}")

    def run_sentiment_refresh(self, trigger_type="intraday"):
        """
        Run intraday NS-USO sentiment sync and refresh dashboard artifacts.

        This keeps regime/risk/narrative views aligned with fresh sentiment
        multiple times per day without running the full pipeline.
        """
        logger.info(f"🧠 Starting sentiment refresh (trigger: {trigger_type})")
        try:
            os.chdir(self.project_root)

            sentiment_rc = subprocess.run(
                [sys.executable, str(self.sentiment_script)],
                capture_output=True,
                text=True,
                timeout=900,
            )
            if sentiment_rc.returncode != 0:
                logger.error("❌ Sentiment refresh failed")
                logger.error(f"STDOUT: {sentiment_rc.stdout}")
                logger.error(f"STDERR: {sentiment_rc.stderr}")
                return False

            refresh_rc = subprocess.run(
                [sys.executable, str(self.refresh_script), "--quick"],
                capture_output=True,
                text=True,
                timeout=1800,
            )
            if refresh_rc.returncode != 0:
                # Keep sentiment cadence resilient even if an optional artifact
                # dependency is missing in this environment.
                logger.warning("⚠️ Artifact refresh failed after sentiment sync (continuing with synced sentiment)")
                logger.warning(f"STDOUT: {refresh_rc.stdout}")
                logger.warning(f"STDERR: {refresh_rc.stderr}")
                return True

            logger.info("✅ Intraday sentiment + artifact refresh completed")
            return True
        except subprocess.TimeoutExpired:
            logger.error("❌ Sentiment refresh timed out")
            return False
        except Exception as e:
            logger.error(f"❌ Sentiment refresh error: {e}")
            return False
    
    def start_scheduler(self):
        """Start the automated scheduler"""
        if schedule is None:
            logger.error("❌ 'schedule' package is not installed. Install with: pip install schedule")
            return

        logger.info("🤖 Starting Northstar Automated Scheduler")
        
        # Schedule jobs
        
        # Weekly comprehensive update (Fridays at 6 PM IST - after RBI updates)
        schedule.every().friday.at("18:00").do(self.weekly_update)
        
        # Daily health checks (weekdays at market open)
        schedule.every().monday.at("09:30").do(self.daily_check)
        schedule.every().tuesday.at("09:30").do(self.daily_check)
        schedule.every().wednesday.at("09:30").do(self.daily_check)
        schedule.every().thursday.at("09:30").do(self.daily_check)
        schedule.every().friday.at("09:30").do(self.daily_check)

        # Intraday sentiment refresh (multiple runs per day, more comprehensive cadence)
        for hhmm in ("09:40", "10:45", "12:00", "13:15", "14:30", "15:20"):
            schedule.every().monday.at(hhmm).do(self.run_sentiment_refresh, trigger_type=f"intraday_{hhmm}")
            schedule.every().tuesday.at(hhmm).do(self.run_sentiment_refresh, trigger_type=f"intraday_{hhmm}")
            schedule.every().wednesday.at(hhmm).do(self.run_sentiment_refresh, trigger_type=f"intraday_{hhmm}")
            schedule.every().thursday.at(hhmm).do(self.run_sentiment_refresh, trigger_type=f"intraday_{hhmm}")
            schedule.every().friday.at(hhmm).do(self.run_sentiment_refresh, trigger_type=f"intraday_{hhmm}")
        
        # Emergency checks (every 2 hours during market hours)
        schedule.every(2).hours.do(self.emergency_check)
        
        logger.info("📅 Scheduled jobs:")
        logger.info("   - Weekly update: Fridays 6:00 PM")
        logger.info("   - Daily checks: Weekdays 9:30 AM")
        logger.info("   - Intraday sentiment refresh: 09:40, 10:45, 12:00, 13:15, 14:30, 15:20 (weekdays)")
        logger.info("   - Emergency checks: Every 2 hours")
        
        # Run scheduler
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
                
        except KeyboardInterrupt:
            logger.info("🛑 Scheduler stopped by user")
        except Exception as e:
            logger.error(f"❌ Scheduler error: {e}")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Northstar Automated Scheduler")
    parser.add_argument("--run-now", action="store_true", help="Run update immediately")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    
    args = parser.parse_args()
    
    scheduler = NorthstarScheduler()
    
    if args.run_now:
        logger.info("🚀 Running immediate update")
        scheduler.run_update("manual")
    elif args.daemon:
        if schedule is None:
            logger.error("❌ Cannot run daemon mode: missing dependency 'schedule'")
            logger.error("Install with: pip install schedule")
            return 1
        logger.info("🤖 Starting as daemon")
        scheduler.start_scheduler()
    else:
        print("Northstar Automated Scheduler")
        print("Usage:")
        print("  --run-now    Run update immediately")
        print("  --daemon     Run as automated scheduler")
        print("\nScheduled times:")
        print("  Weekly update: Fridays 6:00 PM IST")
        print("  Daily checks: Weekdays 9:30 AM IST")
        print("  Emergency checks: Every 2 hours")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
