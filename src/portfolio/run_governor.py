#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path

# This module is launched as a standalone subprocess (see
# src/scheduler/daily_update.py: `python src/portfolio/run_governor.py`), so
# the project root is not guaranteed to be on sys.path. Add it before the
# src.* import below.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.portfolio.portfolio_governor import main as run_portfolio_governor

CFG_PATH = 'data/portfolio/governor_config.json'

def load_config():
    try:
        if os.path.exists(CFG_PATH):
            with open(CFG_PATH, 'r') as f:
                return json.load(f)
    except Exception as exc:
        print(f"⚠ governor config unreadable ({exc}); using defaults")
    return {}

if __name__ == "__main__":
    cfg = load_config()
    run_portfolio_governor()
