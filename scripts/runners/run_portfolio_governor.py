#!/usr/bin/env python3
"""
🎯 Portfolio Governor Runner
Wrapper script for running the portfolio construction
"""

import sys
import os
from pathlib import Path

# Ensure project root is on sys.path when running from scripts/runners
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def main():
    """Run portfolio construction"""
    
    try:
        from src.portfolio.portfolio_governor import PortfolioGovernor
        
        print("🎯 Running portfolio construction...")
        governor = PortfolioGovernor()
        portfolio, analytics = governor.run_portfolio_construction()
        
        if not portfolio.empty:
            n_positions = len(portfolio)
            total_exposure = analytics.get('portfolio_summary', {}).get('total_exposure', 0)
            
            print("✅ Portfolio construction completed")
            print(f"   Positions: {n_positions}")
            print(f"   Total Exposure: {total_exposure:.1%}")
            
            return True
        else:
            print("❌ Portfolio construction failed: Empty portfolio")
            return False
        
    except Exception as e:
        print(f"❌ Portfolio construction failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
