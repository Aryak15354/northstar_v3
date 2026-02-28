#!/usr/bin/env python3
import os
import json
from portfolio_governor import main as run_portfolio_governor

CFG_PATH = 'data/portfolio/governor_config.json'

def load_config():
    try:
        if os.path.exists(CFG_PATH):
            with open(CFG_PATH, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

if __name__ == "__main__":
    cfg = load_config()
    run_portfolio_governor()
