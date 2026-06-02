#!/usr/bin/env python3
"""
State Initialization Script

Initializes the volatility state engine with default or loaded state.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
from pathlib import Path
from src.volatility.state_engine import VolatilityStateEngine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def initialize_state(config_path=None, state_path=None):
    """Initialize state engine"""
    print("Initializing Volatility State Engine...")
    
    engine = VolatilityStateEngine()
    
    if state_path and Path(state_path).exists():
        print(f"Loading state from: {state_path}")
        try:
            engine.load_state(state_path)
            print("✅ State loaded successfully")
        except Exception as e:
            print(f"❌ Failed to load state: {e}")
            print("Creating fresh state...")
    else:
        print("Creating fresh state...")
    
    # Get current state
    state = engine.get_state()
    
    print("\nState Summary:")
    print(f"  Timestamp: {state.timestamp}")
    print(f"  Regime: {state.regime}")
    print(f"  Positions: {len(state.positions)}")
    print(f"  IV Surfaces: {len(state.iv_surfaces)}")
    
    # Save initial state
    snapshot_path = "snapshots/initial_state.json"
    os.makedirs("snapshots", exist_ok=True)
    engine.save_state(snapshot_path)
    print(f"\n✅ Initial state saved to: {snapshot_path}")
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Initialize volatility state')
    parser.add_argument('--config', help='Configuration file path')
    parser.add_argument('--state', help='Existing state file to load')
    args = parser.parse_args()
    
    success = initialize_state(args.config, args.state)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
