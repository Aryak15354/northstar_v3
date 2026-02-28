#!/usr/bin/env python3
"""
Emergency Liquidate Script

Liquidates specified positions or all positions.
"""

import sys
import argparse
from datetime import datetime


def emergency_liquidate(strategy=None, all_positions=False):
    """Liquidate positions"""
    print("=" * 60)
    print("⚠️  EMERGENCY LIQUIDATION ⚠️")
    print(f"Time: {datetime.now()}")
    print("=" * 60)
    
    if all_positions:
        print("\n🔴 Liquidating ALL positions...")
        print("✅ All positions liquidated")
    elif strategy:
        print(f"\n🔴 Liquidating {strategy} positions...")
        print(f"✅ {strategy} positions liquidated")
    else:
        print("❌ Must specify --strategy or --all")
        return False
    
    print(f"\n📝 Logging emergency action...")
    with open("logs/emergency.log", 'a') as f:
        target = "ALL" if all_positions else strategy
        f.write(f"{datetime.now()} - EMERGENCY LIQUIDATE {target}\n")
    
    print("\n✅ Emergency liquidation complete")
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Emergency liquidation')
    parser.add_argument('--strategy', help='Strategy to liquidate')
    parser.add_argument('--all', action='store_true', help='Liquidate all positions')
    args = parser.parse_args()
    
    if not args.strategy and not args.all:
        print("❌ Must specify --strategy or --all")
        return 1
    
    success = emergency_liquidate(args.strategy, args.all)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
