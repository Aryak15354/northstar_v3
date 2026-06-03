#!/usr/bin/env python3
"""
🏛️ RBI DATA UPDATE LAUNCHER
Simple launcher for daily RBI data updates

Usage:
  python scripts/launchers/update_rbi_data.py          # Normal daily update
  python scripts/launchers/update_rbi_data.py --force  # Force update
"""

import os
import sys

# Change to project directory
os.chdir(project_root)

# Import and run the daily updater
from src.ingestion.rbi_daily_updater import main

if __name__ == "__main__":
    main()