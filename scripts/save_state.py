#!/usr/bin/env python3
"""
Save State Script

Saves current volatility state to snapshot.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
from pathlib import Path
from datetime import datetime
from src.volatility.state_engine import VolatilityStateEngine


def save_state(output_path):
    """Save current state"""
    print(f"Saving state to: {output_path}")
    
    # Create output directory
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Initialize engine and save state
    engine = VolatilityStateEngine()
    engine.save_state(output_path)
    
    print(f"✅ State saved successfully")
    print(f"File: {output_path}")
    print(f"Size: {Path(output_path).stat().st_size / 1024:.1f} KB")
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Save volatility state')
    parser.add_argument('output', help='Output file path')
    args = parser.parse_args()
    
    success = save_state(args.output)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
