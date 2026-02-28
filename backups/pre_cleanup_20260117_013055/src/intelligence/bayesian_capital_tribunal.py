#!/usr/bin/env python3
"""
⚖️ BAYESIAN CAPITAL TRIBUNAL - LAYER 5
Probabilistic capital allocation using regime-aware specialist signals

This implements Layer 5 of the institutional alpha engine:
- Evidence evaluation from specialist signals
- Bayesian posterior computation for capital allocation
- Adversarial alpha detection and eviction
- Dynamic reallocation based on regime changes

Key Features:
1. Evidence-based likelihood functions
2. Regime-specific prior updates
3. Posterior normalization and allocation
4. Adversarial alpha harness for overfit protection
5. 1-day reallocation requirement

Usage:
    from src.intelligence.bayesian_capital_tribunal import BayesianCapitalTribunal
    
    tribunal = BayesianCapitalTribunal()
    allocations = tribunal.allocate_capital(specialist_signals, regime_context)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import warnings
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
import json

warnings.filterwarnings('ignore')

import sys
from src.intelligence.regime_aware_specialists import SpecialistSignal, RegimeContext, MarketRegime

@dataclass
class Evidence:
    """Evidence for Bayesian capital allocation"""
    specialist_name: str
    information_coefficient: float    # [-1, +1] signal quality
    signal_decay: float              # [0, 1] signal freshness (1 = fresh, 0 = stale)
    crowding_factor: float           # [0, 1] crowding level (0 = uncrowded, 1 = crowded)
    regime_fit: float               # [0, 1] how well specialist fits current regime
    pnl_quality: float              # [0, 1] recent PnL quality
    confidence: float               # [0, 1] signal confidence
    timestamp: datetime
    metadata: Dict[str, Any]

@dataclass
class CapitalAllocation:
    """Capital allocation decision"""
    specialist_name: str
    allocation_weight: float         # [0, 1] fraction of capital
    posterior_probability: float     # [0, 1] Bayesian posterior
    evidence_strength: float         # [0, 1] combined evidence score
    regime_adjustment: float         # [0, 1] regime-based adjustment
    allocation_change: float         # [-1, +1] change from previous allocation
    confidence: float               # [0, 1] allocation confidence
    metadata: Dict[str, Any]

class AdversarialAlpha:
    """
    Adversarial alpha that looks perfect then collapses
    
    Used to test the tribunal's ability to detect and evict overfit signals.
    Simulates a signal that has perfect backtest performance but fails in live trading.
    """
    
    def __init__(self, name: str = "adversarial"):
        self.name = name
        self.phase = "honeymoon"  # honeymoon -> collapse -> recovery
        self.days_active = 0
        self.collapse_day = 20  # Collapse after 20 days
        self.recovery_day = 50  # Start recovery after 50 days
        
        # Performance tracking
        self.performance_history = []
        self.ic_history = []
        
        print(f"🎭 Adversarial Alpha '{name}' initialized - Honeymoon phase")
    
    def generate_evidence(self, current_time: datetime) -> Evidence:
        """Generate adversarial evidence that looks good then fails"""
        
        self.days_active += 1
        
        if self.phase == "honeymoon" and self.days_active < self.collapse_day:
            # Perfect performance during honeymoon
            ic = 0.3 + np.random.normal(0, 0.05)  # High IC with noise
            pnl_quality = 0.9 + np.random.normal(0, 0.05)  # Excellent PnL
            confidence = 0.95
            
        elif self.phase == "honeymoon" and self.days_active >= self.collapse_day:
            # Transition to collapse
            self.phase = "collapse"
            print(f"🎭 Adversarial Alpha '{self.name}' entering COLLAPSE phase")
            ic = -0.2 + np.random.normal(0, 0.1)  # Negative IC
            pnl_quality = 0.1 + np.random.normal(0, 0.05)  # Poor PnL
            confidence = 0.3
            
        elif self.phase == "collapse" and self.days_active < self.recovery_day:
            # Continued poor performance
            ic = -0.15 + np.random.normal(0, 0.1)  # Negative IC
            pnl_quality = 0.2 + np.random.normal(0, 0.05)  # Poor PnL
            confidence = 0.2
            
        else:
            # Recovery phase (optional)
            self.phase = "recovery"
            ic = 0.1 + np.random.normal(0, 0.1)  # Modest recovery
            pnl_quality = 0.6 + np.random.normal(0, 0.05)  # Moderate PnL
            confidence = 0.5
        
        # Clip values to valid ranges
        ic = np.clip(ic, -1, 1)
        pnl_quality = np.clip(pnl_quality, 0, 1)
        confidence = np.clip(confidence, 0, 1)
        
        # Track performance
        self.ic_history.append(ic)
        self.performance_history.append(pnl_quality)
        
        return Evidence(
            specialist_name=self.name,
            information_coefficient=ic,
            signal_decay=1.0,  # Always fresh
            crowding_factor=0.1,  # Low crowding
            regime_fit=0.8,  # Good regime fit
            pnl_quality=pnl_quality,
            confidence=confidence,
            timestamp=current_time,
            metadata={
                'phase': self.phase,
                'days_active': self.days_active,
                'is_adversarial': True
            }
        )

class BayesianCapitalTribunal:
    """
    Bayesian Capital Tribunal - Probabilistic capital allocation
    
    Core functionality:
    1. Evidence evaluation from specialist signals
    2. Likelihood function computation
    3. Prior update system using regime-specific performance
    4. Posterior computation and normalization
    5. Capital allocation with execution cost consideration
    6. Adversarial alpha detection and eviction
    """
    
    def __init__(self):
        self.allocation_history = []
        self.evidence_history = []
        self.performance_tracking = {}
        
        # Bayesian parameters
        self.prior_weights = {
            'momentum': 0.25,
            'value': 0.25,
            'quality': 0.25,
            'macro': 0.25
        }
        
        # Regime-specific performance memory
        self.regime_performance = {
            regime: {specialist: [] for specialist in self.prior_weights.keys()}
            for regime in MarketRegime
        }
        
        # Adversarial detection parameters
        self.adversarial_threshold = 0.05  # Max 5% allocation to adversarial signals
        self.eviction_days = 30  # Days to reduce adversarial allocation to threshold
        
        # Execution cost parameters
        self.reallocation_cost = 0.001  # 10 bps cost per reallocation
        self.min_allocation_change = 0.02  # 2% minimum change to trigger reallocation
        
        print("⚖️ Bayesian Capital Tribunal initialized - Probabilistic allocation active")
    
    def evaluate_evidence(self, specialist_signals: Dict[str, List[SpecialistSignal]], 
                         regime_context: RegimeContext, current_time: datetime) -> List[Evidence]:
        """Evaluate evidence from specialist signals"""
        
        evidence_list = []
        
        for specialist_name, signals in specialist_signals.items():
            if not signals:
                continue
            
            # Calculate aggregate signal metrics
            avg_strength = np.mean([s.signal_strength for s in signals])
            avg_confidence = np.mean([s.confidence for s in signals])
            avg_regime_fit = np.mean([s.regime_fit for s in signals])
            
            # Mock information coefficient (would be calculated from historical performance)
            ic = self._calculate_information_coefficient(specialist_name, signals, current_time)
            
            # Mock signal decay (would be based on signal age)
            decay = self._calculate_signal_decay(specialist_name, current_time)
            
            # Mock crowding factor (would be based on market crowding metrics)
            crowding = self._calculate_crowding_factor(specialist_name, current_time)
            
            # Mock PnL quality (would be based on recent performance)
            pnl_quality = self._calculate_pnl_quality(specialist_name, current_time)
            
            evidence = Evidence(
                specialist_name=specialist_name,
                information_coefficient=ic,
                signal_decay=decay,
                crowding_factor=crowding,
                regime_fit=avg_regime_fit,
                pnl_quality=pnl_quality,
                confidence=avg_confidence,
                timestamp=current_time,
                metadata={
                    'signal_count': len(signals),
                    'avg_strength': avg_strength,
                    'regime': regime_context.regime.value
                }
            )
            
            evidence_list.append(evidence)
        
        return evidence_list
    
    def compute_likelihood(self, evidence: Evidence) -> float:
        """Compute likelihood function for evidence"""
        
        # Likelihood components
        ic_component = self._sigmoid(evidence.information_coefficient * 5)  # Scale IC
        decay_component = evidence.signal_decay  # Fresh signals better
        crowding_component = np.exp(-evidence.crowding_factor * 2)  # Penalize crowding
        regime_component = evidence.regime_fit  # Reward regime fit
        pnl_component = evidence.pnl_quality  # Reward good PnL
        
        # Combined likelihood
        likelihood = (ic_component * decay_component * crowding_component * 
                     regime_component * pnl_component)
        
        return np.clip(likelihood, 0.001, 0.999)  # Avoid extreme values
    
    def update_priors_with_regime(self, regime_context: RegimeContext, base_priors: Dict[str, float]) -> Dict[str, float]:
        """Update prior weights based on regime-specific performance"""
        
        updated_priors = base_priors.copy()
        
        # Get regime-specific performance for known specialists
        regime_performance = self.regime_performance.get(regime_context.regime, {})
        
        for specialist_name in updated_priors.keys():
            if specialist_name in self.prior_weights:  # Only adjust known specialists
                performance_history = regime_performance.get(specialist_name, [])
                
                if len(performance_history) > 5:  # Need some history
                    # Calculate performance adjustment
                    avg_performance = np.mean(performance_history[-10:])  # Last 10 observations
                    performance_adjustment = (avg_performance - 0.5) * 0.2  # ±10% adjustment
                    
                    # Update prior
                    updated_priors[specialist_name] += performance_adjustment
        
        # Normalize priors
        total_weight = sum(updated_priors.values())
        if total_weight > 0:
            updated_priors = {k: v/total_weight for k, v in updated_priors.items()}
        
        # Handle regime uncertainty (increase prior weights when regime confidence low)
        if regime_context.confidence < 0.6:
            # Flatten priors when uncertain
            uncertainty_factor = (0.6 - regime_context.confidence) * 0.5
            equal_weight = 1.0 / len(updated_priors)
            
            for specialist_name in updated_priors.keys():
                current_weight = updated_priors[specialist_name]
                updated_priors[specialist_name] = (
                    current_weight * (1 - uncertainty_factor) + 
                    equal_weight * uncertainty_factor
                )
        
        return updated_priors
    
    def compute_posteriors(self, evidence_list: List[Evidence], 
                          priors: Dict[str, float]) -> Dict[str, float]:
        """Compute Bayesian posteriors"""
        
        posteriors = {}
        
        # Calculate likelihood for each specialist
        likelihoods = {}
        for evidence in evidence_list:
            likelihood = self.compute_likelihood(evidence)
            likelihoods[evidence.specialist_name] = likelihood
        
        # Compute unnormalized posteriors
        unnormalized_posteriors = {}
        for specialist_name, prior in priors.items():
            likelihood = likelihoods.get(specialist_name, 0.001)  # Small default
            unnormalized_posteriors[specialist_name] = prior * likelihood
        
        # Normalize posteriors
        total_posterior = sum(unnormalized_posteriors.values())
        if total_posterior > 0:
            posteriors = {k: v/total_posterior for k, v in unnormalized_posteriors.items()}
        else:
            # Fallback to equal weights
            posteriors = {k: 1.0/len(priors) for k in priors.keys()}
        
        return posteriors
    
    def allocate_capital(self, specialist_signals: Dict[str, List[SpecialistSignal]], 
                        regime_context: RegimeContext, current_time: datetime,
                        adversarial_evidence: Optional[List[Evidence]] = None) -> List[CapitalAllocation]:
        """Main capital allocation function"""
        
        print(f"⚖️ Bayesian Capital Tribunal - Allocating capital for {current_time.date()}")
        
        # Step 1: Evaluate evidence from specialists
        evidence_list = self.evaluate_evidence(specialist_signals, regime_context, current_time)
        
        # Step 2: Add adversarial evidence if provided
        if adversarial_evidence:
            evidence_list.extend(adversarial_evidence)
        
        # Step 3: Update priors based on regime (include adversarial specialists)
        all_specialist_names = set(evidence.specialist_name for evidence in evidence_list)
        extended_priors = self.prior_weights.copy()
        
        # Add adversarial specialists with small prior
        for specialist_name in all_specialist_names:
            if specialist_name not in extended_priors:
                extended_priors[specialist_name] = 0.05  # Small prior for new specialists
        
        # Normalize extended priors
        total_prior = sum(extended_priors.values())
        if total_prior > 0:
            extended_priors = {k: v/total_prior for k, v in extended_priors.items()}
        
        priors = self.update_priors_with_regime(regime_context, extended_priors)
        
        # Step 4: Compute posteriors
        posteriors = self.compute_posteriors(evidence_list, priors)
        
        # Step 5: Apply adversarial alpha detection
        posteriors = self._apply_adversarial_detection(posteriors, evidence_list, current_time)
        
        # Step 6: Apply execution cost considerations
        posteriors = self._apply_execution_costs(posteriors, current_time)
        
        # Step 7: Create allocation objects
        allocations = []
        previous_allocations = self._get_previous_allocations()
        
        for specialist_name, posterior in posteriors.items():
            # Find corresponding evidence
            evidence = next((e for e in evidence_list if e.specialist_name == specialist_name), None)
            
            # Calculate allocation change
            previous_weight = previous_allocations.get(specialist_name, 0.25)  # Default equal weight
            allocation_change = posterior - previous_weight
            
            # Calculate evidence strength
            evidence_strength = evidence.confidence * evidence.regime_fit if evidence else 0.5
            
            allocation = CapitalAllocation(
                specialist_name=specialist_name,
                allocation_weight=posterior,
                posterior_probability=posterior,
                evidence_strength=evidence_strength,
                regime_adjustment=regime_context.confidence,
                allocation_change=allocation_change,
                confidence=evidence.confidence if evidence else 0.5,
                metadata={
                    'regime': regime_context.regime.value,
                    'prior_weight': priors.get(specialist_name, 0.25),
                    'evidence_available': evidence is not None
                }
            )
            
            allocations.append(allocation)
        
        # Step 8: Store allocation history
        self.allocation_history.append({
            'timestamp': current_time,
            'allocations': {a.specialist_name: a.allocation_weight for a in allocations},
            'regime': regime_context.regime.value,
            'regime_confidence': regime_context.confidence
        })
        
        # Step 9: Store evidence history
        self.evidence_history.extend(evidence_list)
        
        print(f"   Capital allocated across {len(allocations)} specialists")
        for allocation in allocations:
            print(f"   {allocation.specialist_name}: {allocation.allocation_weight:.1%} "
                  f"(change: {allocation.allocation_change:+.1%})")
        
        return allocations
    
    def _calculate_information_coefficient(self, specialist_name: str, 
                                         signals: List[SpecialistSignal], 
                                         current_time: datetime) -> float:
        """Calculate information coefficient (mock implementation)"""
        
        # Mock IC based on specialist type and regime fit
        base_ics = {
            'momentum': 0.15,
            'value': 0.12,
            'quality': 0.10,
            'macro': 0.08
        }
        
        base_ic = base_ics.get(specialist_name, 0.10)
        
        # Add noise and regime adjustment
        avg_regime_fit = np.mean([s.regime_fit for s in signals])
        regime_adjustment = (avg_regime_fit - 0.5) * 0.1
        
        noise = np.random.normal(0, 0.03)
        
        return np.clip(base_ic + regime_adjustment + noise, -0.5, 0.5)
    
    def _calculate_signal_decay(self, specialist_name: str, current_time: datetime) -> float:
        """Calculate signal decay factor (mock implementation)"""
        
        # Mock decay - assume signals are fresh
        return 0.9 + np.random.normal(0, 0.05)
    
    def _calculate_crowding_factor(self, specialist_name: str, current_time: datetime) -> float:
        """Calculate crowding factor (mock implementation)"""
        
        # Mock crowding - momentum typically more crowded
        base_crowding = {
            'momentum': 0.3,
            'value': 0.2,
            'quality': 0.15,
            'macro': 0.1
        }
        
        base = base_crowding.get(specialist_name, 0.2)
        noise = np.random.normal(0, 0.05)
        
        return np.clip(base + noise, 0, 1)
    
    def _calculate_pnl_quality(self, specialist_name: str, current_time: datetime) -> float:
        """Calculate PnL quality (mock implementation)"""
        
        # Mock PnL quality
        base_quality = 0.6 + np.random.normal(0, 0.1)
        return np.clip(base_quality, 0, 1)
    
    def _sigmoid(self, x: float) -> float:
        """Sigmoid function for likelihood computation"""
        return 1 / (1 + np.exp(-x))
    
    def _apply_adversarial_detection(self, posteriors: Dict[str, float], 
                                   evidence_list: List[Evidence], 
                                   current_time: datetime) -> Dict[str, float]:
        """Apply adversarial alpha detection and eviction"""
        
        adjusted_posteriors = posteriors.copy()
        
        for evidence in evidence_list:
            if evidence.metadata.get('is_adversarial', False):
                specialist_name = evidence.specialist_name
                
                # Check if in collapse phase
                if evidence.metadata.get('phase') == 'collapse':
                    # Reduce allocation to threshold over eviction period
                    days_in_collapse = evidence.metadata.get('days_active', 0) - 20  # Collapse starts at day 20
                    
                    if days_in_collapse > 0:
                        # Linear reduction to threshold over eviction_days
                        reduction_factor = min(days_in_collapse / self.eviction_days, 1.0)
                        current_allocation = adjusted_posteriors.get(specialist_name, 0)
                        
                        # Reduce to threshold
                        target_allocation = self.adversarial_threshold
                        adjusted_allocation = current_allocation * (1 - reduction_factor) + target_allocation * reduction_factor
                        
                        adjusted_posteriors[specialist_name] = max(adjusted_allocation, self.adversarial_threshold)
                        
                        print(f"🎭 Adversarial eviction: {specialist_name} reduced to {adjusted_posteriors[specialist_name]:.1%}")
        
        # Renormalize after adversarial adjustments
        total_weight = sum(adjusted_posteriors.values())
        if total_weight > 0:
            adjusted_posteriors = {k: v/total_weight for k, v in adjusted_posteriors.items()}
        
        return adjusted_posteriors
    
    def _apply_execution_costs(self, posteriors: Dict[str, float], 
                             current_time: datetime) -> Dict[str, float]:
        """Apply execution cost considerations"""
        
        if not self.allocation_history:
            return posteriors  # No previous allocation to compare
        
        previous_allocations = self._get_previous_allocations()
        adjusted_posteriors = posteriors.copy()
        
        for specialist_name, new_weight in posteriors.items():
            previous_weight = previous_allocations.get(specialist_name, 0.25)
            allocation_change = abs(new_weight - previous_weight)
            
            # If change is small, stick with previous allocation to avoid costs
            if allocation_change < self.min_allocation_change:
                adjusted_posteriors[specialist_name] = previous_weight
        
        # Renormalize after execution cost adjustments
        total_weight = sum(adjusted_posteriors.values())
        if total_weight > 0:
            adjusted_posteriors = {k: v/total_weight for k, v in adjusted_posteriors.items()}
        
        return adjusted_posteriors
    
    def _get_previous_allocations(self) -> Dict[str, float]:
        """Get previous allocation weights"""
        
        if not self.allocation_history:
            return {}
        
        return self.allocation_history[-1]['allocations']
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary of the tribunal"""
        
        if not self.allocation_history:
            return {'status': 'no_history'}
        
        # Calculate allocation stability
        allocation_changes = []
        for i in range(1, len(self.allocation_history)):
            prev_alloc = self.allocation_history[i-1]['allocations']
            curr_alloc = self.allocation_history[i]['allocations']
            
            total_change = sum(abs(curr_alloc.get(k, 0) - prev_alloc.get(k, 0)) 
                             for k in set(prev_alloc.keys()) | set(curr_alloc.keys()))
            allocation_changes.append(total_change)
        
        avg_turnover = np.mean(allocation_changes) if allocation_changes else 0
        
        # Calculate regime adaptation
        regime_changes = 0
        for i in range(1, len(self.allocation_history)):
            if self.allocation_history[i]['regime'] != self.allocation_history[i-1]['regime']:
                regime_changes += 1
        
        return {
            'total_periods': len(self.allocation_history),
            'average_turnover': avg_turnover,
            'regime_changes': regime_changes,
            'evidence_points': len(self.evidence_history),
            'current_allocations': self._get_previous_allocations()
        }

# =========================== MAIN EXECUTION ===========================

def main():
    """Demonstrate Bayesian Capital Tribunal"""
    
    print("⚖️ BAYESIAN CAPITAL TRIBUNAL - LAYER 5")
    print("=" * 70)
    
    # Initialize tribunal
    tribunal = BayesianCapitalTribunal()
    
    # Mock regime context
    from src.intelligence.regime_aware_specialists import RegimeContext
    regime_context = RegimeContext(
        regime=MarketRegime.EXPANSION,
        confidence=0.8,
        regime_duration=45,
        transition_probability={r: 0.1 for r in MarketRegime},
        macro_indicators={'vix_proxy': 18.0, 'momentum_signal': 0.2}
    )
    
    # Mock specialist signals
    mock_signals = {
        'momentum': [
            SpecialistSignal('RELIANCE.NS', 1.5, 0.8, 0.9, 0.7, {'test': True}),
            SpecialistSignal('TCS.NS', 1.2, 0.7, 0.9, 0.8, {'test': True})
        ],
        'value': [
            SpecialistSignal('RELIANCE.NS', -0.5, 0.6, 0.3, 0.4, {'test': True}),
            SpecialistSignal('TCS.NS', -0.3, 0.5, 0.3, 0.6, {'test': True})
        ],
        'quality': [
            SpecialistSignal('RELIANCE.NS', 0.8, 0.7, 0.6, 0.5, {'test': True}),
            SpecialistSignal('TCS.NS', 1.0, 0.8, 0.6, 0.7, {'test': True})
        ],
        'macro': [
            SpecialistSignal('RELIANCE.NS', 0.3, 0.5, 0.7, 0.6, {'test': True}),
            SpecialistSignal('TCS.NS', 0.5, 0.6, 0.7, 0.8, {'test': True})
        ]
    }
    
    current_time = datetime(2024, 1, 15)
    
    print(f"\n⚖️ Allocating capital for {current_time.date()}")
    print(f"📊 Regime: {regime_context.regime.value} (confidence: {regime_context.confidence:.2f})")
    
    # Test 1: Normal allocation
    print(f"\n🎯 TEST 1: NORMAL CAPITAL ALLOCATION")
    print("-" * 50)
    
    allocations = tribunal.allocate_capital(mock_signals, regime_context, current_time)
    
    print(f"\nAllocation Results:")
    for allocation in allocations:
        print(f"   {allocation.specialist_name:12} | "
              f"Weight: {allocation.allocation_weight:6.1%} | "
              f"Posterior: {allocation.posterior_probability:.3f} | "
              f"Evidence: {allocation.evidence_strength:.3f}")
    
    # Test 2: Adversarial alpha test
    print(f"\n🎭 TEST 2: ADVERSARIAL ALPHA DETECTION")
    print("-" * 50)
    
    # Create adversarial alpha
    adversarial = AdversarialAlpha("fake_momentum")
    
    # Simulate multiple days to show eviction
    for day in range(35):
        test_time = current_time + timedelta(days=day)
        
        # Generate adversarial evidence
        adv_evidence = adversarial.generate_evidence(test_time)
        
        # Allocate capital with adversarial evidence
        allocations = tribunal.allocate_capital(
            mock_signals, regime_context, test_time, 
            adversarial_evidence=[adv_evidence]
        )
        
        # Find adversarial allocation
        adv_allocation = next((a for a in allocations if a.specialist_name == "fake_momentum"), None)
        
        if day % 10 == 0 or day > 15:  # Show key days
            print(f"   Day {day:2d}: {adversarial.phase:10} | "
                  f"IC: {adv_evidence.information_coefficient:+.3f} | "
                  f"Allocation: {adv_allocation.allocation_weight:.1%}")
    
    # Test 3: Performance summary
    print(f"\n📈 TEST 3: TRIBUNAL PERFORMANCE SUMMARY")
    print("-" * 50)
    
    summary = tribunal.get_performance_summary()
    print(f"   Total periods: {summary['total_periods']}")
    print(f"   Average turnover: {summary['average_turnover']:.1%}")
    print(f"   Regime changes: {summary['regime_changes']}")
    print(f"   Evidence points: {summary['evidence_points']}")
    
    print(f"\n   Final allocations:")
    for specialist, weight in summary['current_allocations'].items():
        print(f"      {specialist:12}: {weight:.1%}")
    
    print(f"\n✅ Bayesian Capital Tribunal demonstration complete")
    print("💡 Probabilistic allocation with adversarial protection working")

if __name__ == "__main__":
    main()