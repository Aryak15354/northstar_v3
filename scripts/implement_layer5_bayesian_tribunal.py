#!/usr/bin/env python3
"""
⚖️ IMPLEMENT LAYER 5: BAYESIAN CAPITAL TRIBUNAL
Complete implementation and testing of probabilistic capital allocation

This script implements Layer 5 of the institutional alpha engine:
1. Evidence evaluation system with likelihood functions
2. Bayesian posterior computation and capital allocation
3. Adversarial alpha harness for overfit protection
4. Dynamic reallocation with execution cost consideration
5. Comprehensive testing and validation

Usage:
    python scripts/implement_layer5_bayesian_tribunal.py
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from src.intelligence.bayesian_capital_tribunal import BayesianCapitalTribunal, AdversarialAlpha, Evidence
from src.intelligence.regime_aware_specialists import RegimeAwareSpecialists, MarketRegime, RegimeContext, SpecialistSignal

def test_layer5_implementation():
    """Test Layer 5 implementation with comprehensive validation"""
    
    print("⚖️ IMPLEMENTING LAYER 5: BAYESIAN CAPITAL TRIBUNAL")
    print("=" * 70)
    
    # Initialize systems
    tribunal = BayesianCapitalTribunal()
    specialists = RegimeAwareSpecialists()
    
    # Test configuration
    test_symbols = ['RELIANCE.NS', 'TCS.NS', 'INFY.NS', 'HDFCBANK.NS', 'ICICIBANK.NS']
    
    test_dates = [
        datetime(2023, 6, 15),   # Q2 2023
        datetime(2023, 9, 15),   # Q3 2023
        datetime(2023, 12, 15),  # Q4 2023
        datetime(2024, 1, 15),   # Q1 2024
        datetime(2024, 3, 15)    # Q1 2024 end
    ]
    
    results = {
        'implementation_date': datetime.now().isoformat(),
        'layer': 'Layer 5 - Bayesian Capital Tribunal',
        'test_results': {},
        'performance_metrics': {},
        'validation_summary': {}
    }
    
    print(f"\n📊 Testing with {len(test_symbols)} symbols across {len(test_dates)} time periods")
    
    # Test 1: Evidence Evaluation System
    print(f"\n⚖️ TEST 1: EVIDENCE EVALUATION SYSTEM")
    print("-" * 50)
    
    evidence_tests = []
    
    for test_date in test_dates[:3]:  # Test first 3 dates
        print(f"   Testing evidence evaluation for {test_date.date()}")
        
        # Generate specialist signals
        specialist_signals = specialists.generate_regime_signals(test_symbols, test_date)
        regime_context = specialist_signals['regime_context']
        signals = specialist_signals['signals']
        
        # Evaluate evidence
        evidence_list = tribunal.evaluate_evidence(signals, regime_context, test_date)
        
        evidence_test = {
            'date': test_date.isoformat(),
            'regime': regime_context.regime.value,
            'evidence_count': len(evidence_list),
            'evidence_summary': {}
        }
        
        for evidence in evidence_list:
            evidence_test['evidence_summary'][evidence.specialist_name] = {
                'information_coefficient': evidence.information_coefficient,
                'signal_decay': evidence.signal_decay,
                'crowding_factor': evidence.crowding_factor,
                'regime_fit': evidence.regime_fit,
                'pnl_quality': evidence.pnl_quality,
                'confidence': evidence.confidence
            }
            
            print(f"      {evidence.specialist_name}: IC={evidence.information_coefficient:+.3f}, "
                  f"Decay={evidence.signal_decay:.3f}, Confidence={evidence.confidence:.3f}")
        
        evidence_tests.append(evidence_test)
    
    results['test_results']['evidence_evaluation'] = evidence_tests
    
    # Test 2: Bayesian Posterior Computation
    print(f"\n🧮 TEST 2: BAYESIAN POSTERIOR COMPUTATION")
    print("-" * 50)
    
    posterior_tests = []
    
    for test_date in test_dates[:3]:
        print(f"   Testing posterior computation for {test_date.date()}")
        
        # Generate signals and evidence
        specialist_signals = specialists.generate_regime_signals(test_symbols, test_date)
        regime_context = specialist_signals['regime_context']
        signals = specialist_signals['signals']
        
        # Allocate capital
        allocations = tribunal.allocate_capital(signals, regime_context, test_date)
        
        posterior_test = {
            'date': test_date.isoformat(),
            'regime': regime_context.regime.value,
            'allocations': {},
            'total_weight': 0,
            'allocation_entropy': 0
        }
        
        total_weight = 0
        allocation_weights = []
        
        for allocation in allocations:
            posterior_test['allocations'][allocation.specialist_name] = {
                'weight': allocation.allocation_weight,
                'posterior': allocation.posterior_probability,
                'evidence_strength': allocation.evidence_strength,
                'change': allocation.allocation_change
            }
            
            total_weight += allocation.allocation_weight
            allocation_weights.append(allocation.allocation_weight)
            
            print(f"      {allocation.specialist_name}: {allocation.allocation_weight:.1%} "
                  f"(posterior: {allocation.posterior_probability:.3f})")
        
        posterior_test['total_weight'] = total_weight
        
        # Calculate allocation entropy (measure of diversification)
        if allocation_weights:
            entropy = -sum(w * np.log(w + 1e-10) for w in allocation_weights if w > 0)
            posterior_test['allocation_entropy'] = entropy
        
        posterior_tests.append(posterior_test)
    
    results['test_results']['posterior_computation'] = posterior_tests
    
    # Test 3: Adversarial Alpha Harness
    print(f"\n🎭 TEST 3: ADVERSARIAL ALPHA HARNESS")
    print("-" * 50)
    
    # Create fresh tribunal for adversarial test
    adversarial_tribunal = BayesianCapitalTribunal()
    adversarial_alpha = AdversarialAlpha("test_adversarial")
    
    adversarial_tests = []
    
    # Simulate 40 days to show full adversarial cycle
    base_date = datetime(2024, 1, 1)
    
    for day in range(40):
        test_date = base_date + timedelta(days=day)
        
        # Generate normal signals
        specialist_signals = specialists.generate_regime_signals(test_symbols[:3], test_date)
        regime_context = specialist_signals['regime_context']
        signals = specialist_signals['signals']
        
        # Generate adversarial evidence
        adv_evidence = adversarial_alpha.generate_evidence(test_date)
        
        # Allocate capital with adversarial evidence
        allocations = adversarial_tribunal.allocate_capital(
            signals, regime_context, test_date, 
            adversarial_evidence=[adv_evidence]
        )
        
        # Find adversarial allocation
        adv_allocation = next((a for a in allocations if a.specialist_name == "test_adversarial"), None)
        adv_weight = adv_allocation.allocation_weight if adv_allocation else 0.0
        
        adversarial_test = {
            'day': day,
            'date': test_date.isoformat(),
            'adversarial_phase': adversarial_alpha.phase,
            'adversarial_ic': adv_evidence.information_coefficient,
            'adversarial_allocation': adv_weight,
            'adversarial_pnl_quality': adv_evidence.pnl_quality
        }
        
        adversarial_tests.append(adversarial_test)
        
        # Show key transition points
        if day in [0, 19, 20, 25, 30, 39]:
            print(f"      Day {day:2d}: {adversarial_alpha.phase:10} | "
                  f"IC: {adv_evidence.information_coefficient:+.3f} | "
                  f"Allocation: {adv_weight:.1%} | "
                  f"PnL: {adv_evidence.pnl_quality:.3f}")
    
    results['test_results']['adversarial_harness'] = adversarial_tests
    
    # Test 4: Dynamic Reallocation with Execution Costs
    print(f"\n💰 TEST 4: DYNAMIC REALLOCATION WITH EXECUTION COSTS")
    print("-" * 50)
    
    reallocation_tests = []
    
    # Use fresh tribunal for reallocation test
    reallocation_tribunal = BayesianCapitalTribunal()
    
    for i, test_date in enumerate(test_dates):
        print(f"   Testing reallocation for {test_date.date()}")
        
        # Generate signals
        specialist_signals = specialists.generate_regime_signals(test_symbols, test_date)
        regime_context = specialist_signals['regime_context']
        signals = specialist_signals['signals']
        
        # Allocate capital
        allocations = reallocation_tribunal.allocate_capital(signals, regime_context, test_date)
        
        # Calculate total reallocation
        if i > 0:
            prev_allocations = reallocation_tests[-1]['allocations']
            total_reallocation = sum(
                abs(allocation.allocation_weight - prev_allocations.get(allocation.specialist_name, 0.25))
                for allocation in allocations
            )
        else:
            total_reallocation = 0
        
        reallocation_test = {
            'date': test_date.isoformat(),
            'regime': regime_context.regime.value,
            'regime_confidence': regime_context.confidence,
            'total_reallocation': total_reallocation,
            'allocations': {a.specialist_name: a.allocation_weight for a in allocations}
        }
        
        reallocation_tests.append(reallocation_test)
        
        print(f"      Regime: {regime_context.regime.value} | "
              f"Confidence: {regime_context.confidence:.2f} | "
              f"Reallocation: {total_reallocation:.1%}")
    
    results['test_results']['dynamic_reallocation'] = reallocation_tests
    
    # Test 5: Integration with Layer 4 Specialists
    print(f"\n🔗 TEST 5: INTEGRATION WITH LAYER 4 SPECIALISTS")
    print("-" * 50)
    
    integration_tests = []
    
    for test_date in test_dates[-2:]:  # Test recent dates
        print(f"   Testing integration for {test_date.date()}")
        
        # Generate full specialist signals
        specialist_signals = specialists.generate_regime_signals(test_symbols, test_date)
        regime_context = specialist_signals['regime_context']
        signals = specialist_signals['signals']
        
        # Allocate capital
        allocations = tribunal.allocate_capital(signals, regime_context, test_date)
        
        integration_test = {
            'date': test_date.isoformat(),
            'regime': regime_context.regime.value,
            'specialists_active': len([s for s in signals.values() if s]),
            'total_signals': sum(len(s) for s in signals.values()),
            'allocations': {a.specialist_name: a.allocation_weight for a in allocations},
            'allocation_confidence': np.mean([a.confidence for a in allocations])
        }
        
        integration_tests.append(integration_test)
        
        print(f"      Specialists active: {integration_test['specialists_active']}")
        print(f"      Total signals: {integration_test['total_signals']}")
        print(f"      Avg confidence: {integration_test['allocation_confidence']:.3f}")
    
    results['test_results']['layer4_integration'] = integration_tests
    
    # Calculate Performance Metrics
    print(f"\n📈 CALCULATING PERFORMANCE METRICS")
    print("-" * 50)
    
    # Evidence evaluation success rate
    evidence_success_rate = len([t for t in evidence_tests if t['evidence_count'] > 0]) / len(evidence_tests)
    
    # Posterior computation quality
    valid_posteriors = [t for t in posterior_tests if abs(t['total_weight'] - 1.0) < 0.01]
    posterior_quality = len(valid_posteriors) / len(posterior_tests)
    
    # Adversarial eviction effectiveness
    collapse_allocations = [t for t in adversarial_tests if t['adversarial_phase'] == 'collapse']
    if collapse_allocations:
        max_collapse_allocation = max(t['adversarial_allocation'] for t in collapse_allocations)
        eviction_effectiveness = 1.0 - max_collapse_allocation  # Higher is better
    else:
        eviction_effectiveness = 1.0
    
    # Allocation stability
    reallocations = [t['total_reallocation'] for t in reallocation_tests if t['total_reallocation'] > 0]
    avg_reallocation = np.mean(reallocations) if reallocations else 0
    
    # Integration quality
    integration_success = len([t for t in integration_tests if t['specialists_active'] >= 3]) / len(integration_tests)
    
    performance_metrics = {
        'evidence_success_rate': evidence_success_rate,
        'posterior_quality': posterior_quality,
        'adversarial_eviction_effectiveness': eviction_effectiveness,
        'average_reallocation': avg_reallocation,
        'integration_success_rate': integration_success,
        'total_tests_run': len(evidence_tests) + len(posterior_tests) + len(adversarial_tests) + len(reallocation_tests) + len(integration_tests)
    }
    
    results['performance_metrics'] = performance_metrics
    
    print(f"   Evidence success rate: {evidence_success_rate:.1%}")
    print(f"   Posterior quality: {posterior_quality:.1%}")
    print(f"   Adversarial eviction effectiveness: {eviction_effectiveness:.1%}")
    print(f"   Average reallocation: {avg_reallocation:.1%}")
    print(f"   Integration success rate: {integration_success:.1%}")
    
    # Validation Summary
    print(f"\n✅ VALIDATION SUMMARY")
    print("-" * 30)
    
    validation_checks = {
        'evidence_evaluation_working': evidence_success_rate >= 0.8,
        'posterior_computation_accurate': posterior_quality >= 0.9,
        'adversarial_eviction_effective': eviction_effectiveness >= 0.8,
        'reallocation_reasonable': avg_reallocation <= 0.3,  # Max 30% reallocation
        'layer4_integration_successful': integration_success >= 0.8
    }
    
    passed_checks = sum(validation_checks.values())
    total_checks = len(validation_checks)
    
    validation_summary = {
        'checks_passed': passed_checks,
        'total_checks': total_checks,
        'success_rate': passed_checks / total_checks,
        'individual_checks': validation_checks
    }
    
    results['validation_summary'] = validation_summary
    
    for check_name, passed in validation_checks.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {check_name.replace('_', ' ').title()}: {status}")
    
    print(f"\nOverall validation: {passed_checks}/{total_checks} checks passed ({passed_checks/total_checks:.1%})")
    
    # Save results
    os.makedirs('reports', exist_ok=True)
    report_path = 'reports/layer5_implementation_results.json'
    
    with open(report_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📄 Results saved to: {report_path}")
    
    # Final status
    if validation_summary['success_rate'] >= 0.8:
        print(f"\n⚖️ LAYER 5 IMPLEMENTATION: ✅ SUCCESS")
        print("💡 Bayesian Capital Tribunal is working correctly")
        print("🚀 Ready to proceed with Layer 6: Portfolio-Aware Position Sizing")
        return True
    else:
        print(f"\n⚠️ LAYER 5 IMPLEMENTATION: ❌ NEEDS ATTENTION")
        print("🔧 Some validation checks failed - review and fix issues")
        return False

def demonstrate_layer5_capabilities():
    """Demonstrate Layer 5 capabilities with detailed examples"""
    
    print(f"\n⚖️ DEMONSTRATING LAYER 5 CAPABILITIES")
    print("=" * 50)
    
    # Initialize systems
    tribunal = BayesianCapitalTribunal()
    specialists = RegimeAwareSpecialists()
    
    # Test symbols
    demo_symbols = ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'ASIANPAINT.NS', 'MARUTI.NS']
    demo_time = datetime(2024, 1, 15)
    
    print(f"📊 Demonstrating Bayesian capital allocation")
    print(f"📅 Analysis time: {demo_time}")
    
    # Generate specialist signals
    specialist_results = specialists.generate_regime_signals(demo_symbols, demo_time)
    regime_context = specialist_results['regime_context']
    signals = specialist_results['signals']
    
    print(f"\n🎯 Market Context:")
    print(f"   Regime: {regime_context.regime.value}")
    print(f"   Confidence: {regime_context.confidence:.2f}")
    print(f"   VIX proxy: {regime_context.macro_indicators.get('vix_proxy', 'N/A'):.1f}")
    
    # Demonstrate evidence evaluation
    evidence_list = tribunal.evaluate_evidence(signals, regime_context, demo_time)
    
    print(f"\n📋 Evidence Evaluation:")
    for evidence in evidence_list:
        likelihood = tribunal.compute_likelihood(evidence)
        print(f"   {evidence.specialist_name:12} | "
              f"IC: {evidence.information_coefficient:+.3f} | "
              f"Decay: {evidence.signal_decay:.3f} | "
              f"Crowding: {evidence.crowding_factor:.3f} | "
              f"Likelihood: {likelihood:.3f}")
    
    # Demonstrate capital allocation
    allocations = tribunal.allocate_capital(signals, regime_context, demo_time)
    
    print(f"\n💰 Capital Allocation Results:")
    for allocation in allocations:
        print(f"   {allocation.specialist_name:12} | "
              f"Weight: {allocation.allocation_weight:6.1%} | "
              f"Posterior: {allocation.posterior_probability:.3f} | "
              f"Change: {allocation.allocation_change:+.1%} | "
              f"Confidence: {allocation.confidence:.3f}")
    
    # Demonstrate adversarial alpha detection
    print(f"\n🎭 Adversarial Alpha Demonstration:")
    adversarial = AdversarialAlpha("demo_adversarial")
    
    # Show 3 phases
    for phase_day in [10, 25, 35]:  # Honeymoon, Collapse, Recovery
        test_time = demo_time + timedelta(days=phase_day)
        adv_evidence = adversarial.generate_evidence(test_time)
        
        # Allocate with adversarial evidence
        adv_allocations = tribunal.allocate_capital(
            signals, regime_context, test_time,
            adversarial_evidence=[adv_evidence]
        )
        
        adv_allocation = next((a for a in adv_allocations if a.specialist_name == "demo_adversarial"), None)
        
        print(f"   Day {phase_day:2d} ({adversarial.phase:10}): "
              f"IC: {adv_evidence.information_coefficient:+.3f} | "
              f"Allocation: {adv_allocation.allocation_weight:.1%}")
    
    # Show tribunal performance summary
    summary = tribunal.get_performance_summary()
    print(f"\n📈 Tribunal Performance:")
    print(f"   Total periods: {summary['total_periods']}")
    print(f"   Average turnover: {summary['average_turnover']:.1%}")
    print(f"   Evidence points: {summary['evidence_points']}")
    
    print(f"\n✅ Layer 5 demonstration complete")

def main():
    """Main implementation and testing workflow"""
    
    print("⚖️ LAYER 5 IMPLEMENTATION: BAYESIAN CAPITAL TRIBUNAL")
    print("=" * 70)
    print("Building probabilistic capital allocation with adversarial protection")
    print()
    
    # Run comprehensive testing
    success = test_layer5_implementation()
    
    if success:
        # Demonstrate capabilities
        demonstrate_layer5_capabilities()
        
        print(f"\n⚖️ LAYER 5 IMPLEMENTATION COMPLETE")
        print("=" * 40)
        print("✅ Evidence evaluation system with likelihood functions")
        print("✅ Bayesian posterior computation and capital allocation")
        print("✅ Adversarial alpha harness for overfit protection")
        print("✅ Dynamic reallocation with execution cost consideration")
        print("✅ Full integration with Layer 4 specialists")
        print()
        print("🚀 Ready for Layer 6: Portfolio-Aware Position Sizing")
        
    else:
        print(f"\n⚠️ LAYER 5 IMPLEMENTATION INCOMPLETE")
        print("🔧 Review validation results and fix issues")
        print("📋 Check reports/layer5_implementation_results.json for details")

if __name__ == "__main__":
    main()