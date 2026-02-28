#!/usr/bin/env python3
"""
Test Institutional Variance Reduction

This tests whether the institutional-grade components (Signal Quality Gate,
Position Inertia System, and Regime-Locked Capital Allocator) successfully
reduce the 56x seed variance to ~3x as promised.

This is the proof that NorthStar has been transformed from an "unfiltered
conditional alpha factory" into a disciplined institutional system.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime
import subprocess
import warnings
warnings.filterwarnings('ignore')

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class InstitutionalVarianceTest:
    """
    Test the variance reduction achieved by institutional components.
    
    This runs multiple seeds with the new institutional system and compares
    variance to the original 56x variance from the unfiltered system.
    """
    
    def __init__(self):
        self.name = "Institutional Variance Reduction Test"
        self.version = "1.0"
        
        print(f"🧪 {self.name}")
        print("=" * 80)
        print("Testing whether institutional discipline reduces 56x variance to ~3x")
        print()
    
    def run_seed_test(self, seeds: list, timeout_minutes: int = 5) -> dict:
        """Run walk-forward validation with multiple seeds"""
        
        print(f"🎲 RUNNING SEED VARIANCE TEST")
        print("=" * 50)
        print(f"Seeds to test: {seeds}")
        print(f"Timeout per seed: {timeout_minutes} minutes")
        print()
        
        results = {}
        
        for i, seed in enumerate(seeds):
            print(f"🔄 Running seed {seed} ({i+1}/{len(seeds)})...")
            
            # Set environment variable for seed
            env = os.environ.copy()
            env['NORTHSTAR_SEED'] = str(seed)
            
            try:
                # Run the walk-forward validation
                result = subprocess.run(
                    ['python', 'scripts/run_honest_walk_forward_clean.py'],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=timeout_minutes * 60
                )
                
                if result.returncode == 0:
                    # Parse the final NAV from output
                    output_lines = result.stdout.split('\n')
                    final_nav = None
                    
                    for line in output_lines:
                        if 'Final NAV:' in line:
                            # Extract NAV value
                            nav_str = line.split('Final NAV:')[1].strip()
                            nav_str = nav_str.replace('$', '').replace(',', '')
                            try:
                                final_nav = float(nav_str)
                                break
                            except:
                                continue
                    
                    if final_nav:
                        total_return = (final_nav / 100_000_000 - 1) * 100
                        results[seed] = {
                            'final_nav': final_nav,
                            'total_return': total_return,
                            'success': True
                        }
                        print(f"   ✅ Seed {seed}: NAV ${final_nav:,.0f} ({total_return:+.1f}%)")
                    else:
                        print(f"   ❌ Seed {seed}: Could not parse NAV from output")
                        results[seed] = {'success': False, 'error': 'Could not parse NAV'}
                else:
                    print(f"   ❌ Seed {seed}: Process failed with return code {result.returncode}")
                    results[seed] = {'success': False, 'error': f'Return code {result.returncode}'}
                    
            except subprocess.TimeoutExpired:
                print(f"   ⏰ Seed {seed}: Timeout after {timeout_minutes} minutes")
                results[seed] = {'success': False, 'error': 'Timeout'}
            except Exception as e:
                print(f"   ❌ Seed {seed}: Error - {e}")
                results[seed] = {'success': False, 'error': str(e)}
        
        return results
    
    def analyze_variance(self, results: dict) -> dict:
        """Analyze variance in results"""
        
        print(f"\n📊 VARIANCE ANALYSIS")
        print("=" * 40)
        
        # Extract successful results
        successful_results = []
        for seed, result in results.items():
            if result.get('success', False):
                successful_results.append(result['total_return'])
        
        if len(successful_results) < 2:
            print("❌ Insufficient successful results for variance analysis")
            return {}
        
        # Calculate statistics
        returns = np.array(successful_results)
        
        min_return = np.min(returns)
        max_return = np.max(returns)
        mean_return = np.mean(returns)
        median_return = np.median(returns)
        std_return = np.std(returns)
        
        # Calculate variance ratio (max/min)
        if min_return > 0:
            variance_ratio = max_return / min_return
        elif min_return < 0 and max_return > 0:
            # Handle case where min is negative
            variance_ratio = (max_return - min_return) / abs(min_return)
        else:
            variance_ratio = float('inf')
        
        # Print results
        print(f"Successful runs: {len(successful_results)}")
        print(f"Returns range: {min_return:+.1f}% to {max_return:+.1f}%")
        print(f"Mean return: {mean_return:+.1f}%")
        print(f"Median return: {median_return:+.1f}%")
        print(f"Standard deviation: {std_return:.1f}%")
        print(f"Variance ratio: {variance_ratio:.1f}x")
        
        # Verdict
        print(f"\n🎯 VARIANCE REDUCTION VERDICT")
        print("=" * 40)
        
        if variance_ratio <= 3.0:
            print("✅ SUCCESS: Variance reduced to institutional levels (≤3x)")
            print("   The institutional components have successfully disciplined NorthStar")
        elif variance_ratio <= 10.0:
            print("🔧 PARTIAL SUCCESS: Variance reduced but still high (≤10x)")
            print("   Further tuning of institutional parameters needed")
        else:
            print("❌ FAILURE: Variance still too high (>10x)")
            print("   Institutional components need significant improvement")
        
        # Compare to original 56x variance
        improvement_factor = 56.0 / variance_ratio if variance_ratio > 0 else float('inf')
        print(f"\n📈 IMPROVEMENT vs ORIGINAL:")
        print(f"   Original variance: 56x")
        print(f"   Current variance: {variance_ratio:.1f}x")
        print(f"   Improvement factor: {improvement_factor:.1f}x better")
        
        return {
            'successful_runs': len(successful_results),
            'returns': successful_results,
            'min_return': float(min_return),
            'max_return': float(max_return),
            'mean_return': float(mean_return),
            'median_return': float(median_return),
            'std_return': float(std_return),
            'variance_ratio': float(variance_ratio),
            'improvement_factor': float(improvement_factor),
            'institutional_grade': bool(variance_ratio <= 3.0)
        }
    
    def generate_report(self, results: dict, analysis: dict) -> dict:
        """Generate comprehensive test report"""
        
        report = {
            'test_name': self.name,
            'test_timestamp': datetime.now().isoformat(),
            'test_results': results,
            'variance_analysis': analysis,
            'institutional_components': {
                'signal_quality_gate': 'Blocks weak signals (IC < 0.03)',
                'position_inertia_system': 'Reduces turnover via hysteresis',
                'regime_locked_capital_allocator': 'Regime-specific capital limits'
            },
            'verdict': {
                'institutional_grade': analysis.get('institutional_grade', False),
                'variance_ratio': analysis.get('variance_ratio', float('inf')),
                'improvement_factor': analysis.get('improvement_factor', 0),
                'recommendation': self._get_recommendation(analysis)
            }
        }
        
        # Save report
        report_file = f"institutional_variance_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n💾 Report saved: {report_file}")
        
        return report
    
    def _get_recommendation(self, analysis: dict) -> str:
        """Get recommendation based on analysis"""
        
        variance_ratio = analysis.get('variance_ratio', float('inf'))
        
        if variance_ratio <= 3.0:
            return "DEPLOY: System shows institutional-grade discipline. Ready for capital allocation."
        elif variance_ratio <= 10.0:
            return "TUNE: Tighten signal quality thresholds and regime capital limits."
        else:
            return "REBUILD: Institutional components insufficient. Fundamental redesign needed."

def main():
    """Run the institutional variance reduction test"""
    
    # Initialize test
    test = InstitutionalVarianceTest()
    
    # Test with 5 different seeds (reduced from original for speed)
    test_seeds = [123, 456, 789, 101112, 131415]
    
    print(f"⚠️  IMPORTANT: This test validates the institutional transformation")
    print(f"   Original NorthStar: 56x seed variance (unfiltered alpha factory)")
    print(f"   Target: ≤3x seed variance (institutional discipline)")
    print()
    
    # Run seed tests
    results = test.run_seed_test(test_seeds, timeout_minutes=3)
    
    # Analyze variance
    analysis = test.analyze_variance(results)
    
    # Generate report
    if analysis:
        report = test.generate_report(results, analysis)
        
        print(f"\n🏆 INSTITUTIONAL TRANSFORMATION TEST COMPLETE")
        print("=" * 60)
        
        if report['verdict']['institutional_grade']:
            print("✅ NorthStar has been successfully transformed into an institutional system")
            print("   • Signal Quality Gate: Blocking weak signals")
            print("   • Position Inertia: Reducing turnover")
            print("   • Regime Allocator: Disciplined capital deployment")
        else:
            print("⚠️  NorthStar transformation incomplete")
            print(f"   Recommendation: {report['verdict']['recommendation']}")
    
    else:
        print(f"\n❌ TEST FAILED: Insufficient data for analysis")

if __name__ == "__main__":
    main()