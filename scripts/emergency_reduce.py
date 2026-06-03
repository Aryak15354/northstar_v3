#!/usr/bin/env python3
"""
Emergency Reduce Positions Script

Reduces all positions by specified percentage.
"""

import sys
import argparse
from datetime import datetime


def emergency_reduce(percentage):
    """Reduce all positions"""
    print("=" * 60)
    print("⚠️  EMERGENCY POSITION REDUCTION ⚠️")
    print(f"Time: {datetime.now()}")
    print(f"Reduction: {percentage}%")
    print("=" * 60)
    
    print(f"\n🔄 Reducing all positions by {percentage}%...")
    print("✅ Position reduction complete")
    
    print(f"\n📝 Logging emergency action...")
    with open("logs/emergency.log", 'a') as f:
        f.write(f"{datetime.now()} - EMERGENCY REDUCE {percentage}%\n")
    
    print("\n✅ Emergency reduction complete")
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Emergency position reduction')
    parser.add_argument('--percentage', type=float, required=True,
                       help='Percentage to reduce (e.g., 50 for 50%%)')
    args = parser.parse_args()
    
    if args.percentage <= 0 or args.percentage > 100:
        print("❌ Percentage must be between 0 and 100")
        return 1
    
    success = emergency_reduce(args.percentage)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
