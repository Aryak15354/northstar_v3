#!/usr/bin/env python3
"""
⏰ SNAPSHOT SCHEDULER
Automated builder that runs every 5 minutes to keep the terminal synchronized

This is the heartbeat of the unified terminal - it ensures all dashboards
show the same data by building a fresh snapshot every 5 minutes.
"""

import schedule
import time
import sys
import os
from datetime import datetime
import subprocess
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/logs/snapshot_scheduler.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Add src to path
, '..'))

def build_snapshot():
    """Build the unified snapshot"""
    try:
        logger.info("🧠 Starting snapshot build...")
        
        # Import and run the snapshot builder
        from intelligence.build_dashboard_snapshot import build_unified_snapshot
        
        snapshot = build_unified_snapshot()
        
        if snapshot:
            logger.info(f"✅ Snapshot built successfully - Health: {snapshot.get('health', {}).get('grade', 'Unknown')}")
            return True
        else:
            logger.error("❌ Snapshot build returned None")
            return False
            
    except Exception as e:
        logger.error(f"❌ Snapshot build failed: {e}")
        return False

def check_system_health():
    """Check if the system is healthy enough to build snapshots"""
    try:
        # Check if critical directories exist
        critical_dirs = [
            'data/processed',
            'data/portfolio',
            'data/intelligence'
        ]
        
        for dir_path in critical_dirs:
            if not os.path.exists(dir_path):
                logger.warning(f"⚠️ Critical directory missing: {dir_path}")
                os.makedirs(dir_path, exist_ok=True)
        
        # Check if we have recent data
        market_state_path = 'data/processed/market_state.parquet'
        if os.path.exists(market_state_path):
            age_hours = (time.time() - os.path.getmtime(market_state_path)) / 3600
            if age_hours > 48:
                logger.warning(f"⚠️ Market state data is {age_hours:.1f} hours old")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Health check failed: {e}")
        return False

def scheduled_snapshot_build():
    """Scheduled snapshot build with health checks"""
    logger.info("⏰ Scheduled snapshot build triggered")
    
    # Check system health first
    if not check_system_health():
        logger.error("❌ System health check failed - skipping snapshot build")
        return
    
    # Build snapshot
    success = build_snapshot()
    
    if success:
        logger.info("✅ Scheduled snapshot build completed successfully")
    else:
        logger.error("❌ Scheduled snapshot build failed")

def run_scheduler():
    """Run the snapshot scheduler"""
    logger.info("🚀 STARTING SNAPSHOT SCHEDULER")
    logger.info("Building snapshots every 5 minutes...")
    
    # Build initial snapshot
    logger.info("🧠 Building initial snapshot...")
    build_snapshot()
    
    # Schedule regular builds every 5 minutes
    schedule.every(5).minutes.do(scheduled_snapshot_build)
    
    # Also schedule health checks every hour
    schedule.every().hour.do(check_system_health)
    
    logger.info("⏰ Scheduler started - Press Ctrl+C to stop")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)  # Check every 30 seconds
            
    except KeyboardInterrupt:
        logger.info("🛑 Scheduler stopped by user")
    except Exception as e:
        logger.error(f"❌ Scheduler error: {e}")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Snapshot Scheduler')
    parser.add_argument('--build-once', action='store_true', help='Build snapshot once and exit')
    parser.add_argument('--check-health', action='store_true', help='Check system health and exit')
    
    args = parser.parse_args()
    
    # Ensure log directory exists
    os.makedirs('data/logs', exist_ok=True)
    
    if args.build_once:
        logger.info("🧠 Building snapshot once...")
        success = build_snapshot()
        sys.exit(0 if success else 1)
    
    elif args.check_health:
        logger.info("🏥 Checking system health...")
        healthy = check_system_health()
        sys.exit(0 if healthy else 1)
    
    else:
        # Run continuous scheduler
        run_scheduler()

if __name__ == "__main__":
    main()