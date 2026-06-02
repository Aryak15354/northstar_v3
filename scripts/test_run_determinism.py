#!/usr/bin/env python3
"""
Run Determinism Invariant Test

This is the gate between toy and fund.

Given the same code hash + data + seed, every run must produce identical NAV.
If this test fails, the walk-forward engine is contaminated and all results are meaningless.

The harsh truth: You do not yet have a valid walk-forward engine until this passes.
"""

import sys
import os
import json
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime

def calculate_file_hash(filepath):
    """Calculate SHA-256 hash of a file"""
    hash_sha256 = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except FileNotFoundError:
        return None

def run_walk_forward_with_seed(seed, run_number):
    """Run walk-forward with fixed seed and capture results"""
    print(f"\n🔍 Run {run_number}: Testing determinism with seed {seed}")
    
    # Clear any existing results
    if os.path.exists("sealed_results.json"):
        os.remove("sealed_results.json")
    
    # Set numpy random seed for determinism
    import numpy as np
    np.random.seed(seed)
    
    # Set environment variable for seed (the script should read this)
    os.environ['NORTHSTAR_SEED'] = str(seed)
    
    # Run the walk-forward script
    cmd = [
        sys.executable, 
        "scripts/run_honest_walk_forward_clean.py"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            print(f"❌ Run {run_number} failed:")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            return None
            
        # Load results
        if not os.path.exists("sealed_results.json"):
            print(f"❌ Run {run_number}: No sealed_results.json generated")
            return None
            
        with open("sealed_results.json", "r") as f:
            results = json.load(f)
            
        return results
        
    except subprocess.TimeoutExpired:
        print(f"❌ Run {run_number}: Timeout after 5 minutes")
        return None
    except Exception as e:
        print(f"❌ Run {run_number}: Exception: {e}")
        return None

def compare_results(results1, results2, results3):
    """Compare three runs for bit-wise identical results"""
    
    print("\n🔬 DETERMINISM ANALYSIS")
    print("=" * 60)
    
    # Extract key metrics
    def extract_metrics(results):
        if not results:
            return None
            
        # Handle the sealed results format
        if 'results' in results:
            perf = results['results']
        else:
            perf = results
            
        return {
            'final_nav': perf.get('final_nav', 0),
            'total_return': perf.get('total_return', 0),
            'daily_nav_hash': hashlib.sha256(
                str(perf.get('daily_nav', [])).encode()
            ).hexdigest()[:16],
            'daily_nav_length': len(perf.get('daily_nav', [])),
            'system_hash': perf.get('system_hash', 'unknown')
        }
    
    metrics1 = extract_metrics(results1)
    metrics2 = extract_metrics(results2)
    metrics3 = extract_metrics(results3)
    
    if not all([metrics1, metrics2, metrics3]):
        print("❌ CRITICAL FAILURE: One or more runs failed to complete")
        return False
    
    print(f"Run 1 Final NAV: ${metrics1['final_nav']:,.2f}")
    print(f"Run 2 Final NAV: ${metrics2['final_nav']:,.2f}")
    print(f"Run 3 Final NAV: ${metrics3['final_nav']:,.2f}")
    
    print(f"\nRun 1 Total Return: {metrics1['total_return']:.4f}")
    print(f"Run 2 Total Return: {metrics2['total_return']:.4f}")
    print(f"Run 3 Total Return: {metrics3['total_return']:.4f}")
    
    print(f"\nRun 1 Daily NAV Hash: {metrics1['daily_nav_hash']}")
    print(f"Run 2 Daily NAV Hash: {metrics2['daily_nav_hash']}")
    print(f"Run 3 Daily NAV Hash: {metrics3['daily_nav_hash']}")
    
    print(f"\nRun 1 NAV Length: {metrics1['daily_nav_length']}")
    print(f"Run 2 NAV Length: {metrics2['daily_nav_length']}")
    print(f"Run 3 NAV Length: {metrics3['daily_nav_length']}")
    
    print(f"\nRun 1 System Hash: {metrics1['system_hash'][:16]}...")
    print(f"Run 2 System Hash: {metrics2['system_hash'][:16]}...")
    print(f"Run 3 System Hash: {metrics3['system_hash'][:16]}...")
    
    # Check for exact matches
    nav_match_12 = abs(metrics1['final_nav'] - metrics2['final_nav']) < 0.01
    nav_match_13 = abs(metrics1['final_nav'] - metrics3['final_nav']) < 0.01
    nav_match_23 = abs(metrics2['final_nav'] - metrics3['final_nav']) < 0.01
    
    hash_match_12 = metrics1['daily_nav_hash'] == metrics2['daily_nav_hash']
    hash_match_13 = metrics1['daily_nav_hash'] == metrics3['daily_nav_hash']
    hash_match_23 = metrics2['daily_nav_hash'] == metrics3['daily_nav_hash']
    
    print(f"\n📊 DETERMINISM TEST RESULTS:")
    print(f"NAV Match (1-2): {'✅' if nav_match_12 else '❌'}")
    print(f"NAV Match (1-3): {'✅' if nav_match_13 else '❌'}")
    print(f"NAV Match (2-3): {'✅' if nav_match_23 else '❌'}")
    
    print(f"Hash Match (1-2): {'✅' if hash_match_12 else '❌'}")
    print(f"Hash Match (1-3): {'✅' if hash_match_13 else '❌'}")
    print(f"Hash Match (2-3): {'✅' if hash_match_23 else '❌'}")
    
    all_deterministic = all([
        nav_match_12, nav_match_13, nav_match_23,
        hash_match_12, hash_match_13, hash_match_23
    ])
    
    if all_deterministic:
        print("\n🎯 VERDICT: DETERMINISTIC ✅")
        print("The walk-forward engine passes the determinism test.")
        print("Results are bit-wise reproducible under fixed seed.")
        return True
    else:
        print("\n💥 VERDICT: NON-DETERMINISTIC ❌")
        print("CRITICAL FAILURE: The walk-forward engine is contaminated.")
        print("\nThis means:")
        print("• Hidden state is leaking between runs")
        print("• Random seeds are not being properly controlled")
        print("• The simulation harness has bugs")
        print("• ALL PREVIOUS RESULTS ARE MEANINGLESS")
        
        print("\n🔍 LIKELY CAUSES:")
        print("• Bayesian priors not reset")
        print("• Regime embeddings accumulate")
        print("• Portfolio state not reset")
        print("• RNG not seeded properly")
        print("• Memory engine retaining state")
        print("• Capital tribunal reusing memory")
        
        return False

def main():
    print("🚨 RUN DETERMINISM INVARIANT TEST")
    print("=" * 60)
    print("This is the gate between toy and fund.")
    print("Given same code + data + seed → must produce identical NAV")
    print()
    
    # Check if walk-forward script exists
    if not os.path.exists("scripts/run_honest_walk_forward_clean.py"):
        print("❌ FATAL: scripts/run_honest_walk_forward_clean.py not found")
        return False
    
    # Use fixed seed for all runs
    FIXED_SEED = 123
    
    print(f"Running 3 identical tests with seed {FIXED_SEED}")
    print("If ANY results differ, the engine is contaminated.")
    
    # Run three identical tests
    results1 = run_walk_forward_with_seed(FIXED_SEED, 1)
    results2 = run_walk_forward_with_seed(FIXED_SEED, 2)
    results3 = run_walk_forward_with_seed(FIXED_SEED, 3)
    
    # Compare results
    is_deterministic = compare_results(results1, results2, results3)
    
    print("\n" + "=" * 60)
    if is_deterministic:
        print("🎯 NORTHSTAR STATUS: READY FOR VALIDATION")
        print("The walk-forward engine is clean and deterministic.")
        print("You can now trust the results and proceed with analysis.")
    else:
        print("💥 NORTHSTAR STATUS: CONTAMINATED")
        print("The walk-forward engine has hidden state leaks.")
        print("You must fix determinism before any results are meaningful.")
        print("\nNext steps:")
        print("1. Identify the hidden state leak")
        print("2. Implement proper state reset")
        print("3. Re-run this test until it passes")
        print("4. Only then analyze performance")
    
    return is_deterministic

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)