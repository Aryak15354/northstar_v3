#!/usr/bin/env python3
"""
Seed Variance Test

This tests if different random seeds produce the massive variance you described.
If they do, it means the strategy is fundamentally unstable under perturbation.
"""

import sys
import os
import json
import subprocess
from pathlib import Path

def run_with_different_seeds():
    """Run walk-forward with different seeds to test variance"""
    
    print("🎲 SEED VARIANCE TEST")
    print("=" * 60)
    print("Testing if different seeds produce the massive variance described")
    print()
    
    seeds = [123, 456, 789, 101112, 131415]
    results = []
    
    for i, seed in enumerate(seeds):
        print(f"\n🔍 Run {i+1}: Testing with seed {seed}")
        
        # Clear any existing results
        if os.path.exists("sealed_results.json"):
            os.remove("sealed_results.json")
        
        # Set environment variable for seed
        os.environ['NORTHSTAR_SEED'] = str(seed)
        
        # Run the walk-forward script
        cmd = [sys.executable, "scripts/run_honest_walk_forward_clean.py"]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                print(f"❌ Run {i+1} failed")
                continue
                
            # Load results
            if not os.path.exists("sealed_results.json"):
                print(f"❌ Run {i+1}: No results generated")
                continue
                
            with open("sealed_results.json", "r") as f:
                run_results = json.load(f)
                
            # Extract metrics
            if 'results' in run_results:
                perf = run_results['results']
            else:
                perf = run_results
                
            final_nav = perf.get('final_nav', 0)
            total_return = perf.get('total_return', 0)
            
            results.append({
                'seed': seed,
                'final_nav': final_nav,
                'total_return': total_return
            })
            
            print(f"   Final NAV: ${final_nav:,.0f}")
            print(f"   Total Return: {total_return:.1f}%")
            
        except Exception as e:
            print(f"❌ Run {i+1}: Exception: {e}")
            continue
    
    # Analyze variance
    print(f"\n📊 VARIANCE ANALYSIS")
    print("=" * 60)
    
    if len(results) < 2:
        print("❌ Not enough successful runs to analyze variance")
        return
    
    navs = [r['final_nav'] for r in results]
    returns = [r['total_return'] for r in results]
    
    min_nav = min(navs)
    max_nav = max(navs)
    mean_nav = sum(navs) / len(navs)
    
    min_return = min(returns)
    max_return = max(returns)
    mean_return = sum(returns) / len(returns)
    
    print(f"Final NAV Range:")
    print(f"   Min: ${min_nav:,.0f}")
    print(f"   Max: ${max_nav:,.0f}")
    print(f"   Mean: ${mean_nav:,.0f}")
    print(f"   Ratio (Max/Min): {max_nav/min_nav:.1f}x")
    
    print(f"\nTotal Return Range:")
    print(f"   Min: {min_return:.1f}%")
    print(f"   Max: {max_return:.1f}%")
    print(f"   Mean: {mean_return:.1f}%")
    print(f"   Spread: {max_return - min_return:.1f}%")
    
    # Calculate coefficient of variation
    import numpy as np
    nav_std = np.std(navs)
    nav_cv = nav_std / mean_nav
    
    return_std = np.std(returns)
    return_cv = return_std / abs(mean_return) if mean_return != 0 else float('inf')
    
    print(f"\nVariability Metrics:")
    print(f"   NAV Coefficient of Variation: {nav_cv:.3f}")
    print(f"   Return Coefficient of Variation: {return_cv:.3f}")
    
    # Verdict
    print(f"\n🎯 VARIANCE VERDICT:")
    
    if max_nav / min_nav > 100:  # 100x difference
        print("💥 EXTREME VARIANCE DETECTED")
        print("The strategy shows massive instability under different seeds.")
        print("This suggests fundamental issues with the alpha generation.")
    elif nav_cv > 1.0:  # CV > 100%
        print("⚠️  HIGH VARIANCE DETECTED")
        print("The strategy shows significant instability.")
        print("This may indicate weak signal-to-noise ratio.")
    elif nav_cv > 0.3:  # CV > 30%
        print("📊 MODERATE VARIANCE")
        print("Some variance is expected, but this may be on the high side.")
    else:
        print("✅ ACCEPTABLE VARIANCE")
        print("The strategy shows reasonable stability across seeds.")
    
    return results

if __name__ == "__main__":
    results = run_with_different_seeds()