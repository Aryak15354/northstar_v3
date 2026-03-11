#!/usr/bin/env python3
"""
⚔️ BAYESIAN CONTRADICTION HANDLER - INSTITUTIONAL GRADE SIGNAL FUSION
Handle contradictions like a Bayesian - Northstar V3 Intelligence

Instead of flipping when signals contradict:
- Valuation says cheap
- Momentum says downtrend  
- Macro says tightening

Compute: P(undervalued | macro, trend, fundamentals)

Dynamic regime-aware weighting:
- Bull markets: Trend matters more than cheap
- Bear markets: Cheap matters more than trend
- Neutral: Balanced weighting

This is how real hedge funds handle contradictory signals.

Usage:
    try:
    from intelligence.bayesian_engine import BayesianSignalFusion
except ImportError:
    from BayesianSignalFusion import BayesianSignalFusion
    
    fusion = BayesianSignalFusion()
    result = fusion.fuse_contradictory_signals({
        'valuation': -1.5,  # Cheap
        'momentum': 0.8,    # Uptrend
        'macro': -0.5       # Tightening
    })
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# Temporal protection
try:
    from src.intelligence.temporal_guard import TemporalGuard
except ImportError:
    from src.cohesion.temporal_guard import TemporalGuard

# =========================== BAYESIAN SIGNAL FUSION ENGINE ===========================

class BayesianSignalFusion:
    """
    Bayesian Signal Fusion Engine
    
    Handles contradictory signals using Bayesian probability theory.
    Instead of simple weighted averages, computes conditional probabilities.
    
    Key Innovation: Regime-aware dynamic weighting
    - Bull markets: Momentum > Valuation
    - Bear markets: Valuation > Momentum  
    - Neutral: Balanced approach
    """
    
    def __init__(self):
        self.name = "Bayesian Signal Fusion"
        self.guard = TemporalGuard()  # Temporal protection
        
        # Prior probabilities for different market outcomes
        self.priors = {
            'undervalued': 0.3,    # 30% of stocks are undervalued
            'overvalued': 0.3,     # 30% of stocks are overvalued
            'fairly_valued': 0.4   # 40% are fairly valued
        }
        
        # Signal reliability in different regimes
        self.signal_reliability = {
            'bull': {
                'valuation': 0.6,   # Valuation less reliable in bull markets
                'momentum': 0.8,    # Momentum very reliable
                'macro': 0.7,       # Macro moderately reliable
                'quality': 0.6,     # Quality less important
                'flows': 0.9        # Flows very important
            },
            'bear': {
                'valuation': 0.9,   # Valuation very reliable in bear markets
                'momentum': 0.5,    # Momentum less reliable (can reverse quickly)
                'macro': 0.8,       # Macro very important
                'quality': 0.9,     # Quality crucial
                'flows': 0.7        # Flows important but can be wrong
            },
            'neutral': {
                'valuation': 0.75,  # Balanced approach
                'momentum': 0.7,
                'macro': 0.75,
                'quality': 0.75,
                'flows': 0.7
            }
        }
        
        # Regime detection thresholds
        self.regime_thresholds = {
            'bull': {'macro_score': 0.5, 'breadth': 60, 'momentum': 0.3},
            'bear': {'macro_score': -0.5, 'breadth': 40, 'momentum': -0.3},
            'neutral': 'default'
        }
    
    def detect_market_regime(self, market_state=None):
        """
        Detect current market regime for dynamic weighting
        
        Args:
            market_state: Dict with macro_score, breadth_pct, momentum
        
        Returns:
            str: 'bull', 'bear', or 'neutral'
        """
        
        if market_state is None:
            # Try to load from market state
            try:
                # Use temporal guard for market state
                regime_data = self.guard.get_regime_data(datetime.now())
                market_state = {
                    'macro_score': regime_data.get('macro_score', 0.0),
                    'breadth_pct': regime_data.get('breadth_pct', 50.0),
                    'macro_momentum': regime_data.get('momentum', 0.0)
                }
            except:
                return 'neutral'  # Default if can't load
        
        macro_score = market_state.get('macro_score', 0.0)
        breadth_pct = market_state.get('breadth_pct', 50.0)
        momentum = market_state.get('macro_momentum', 0.0)
        
        # Bull market conditions
        bull_conditions = [
            macro_score > self.regime_thresholds['bull']['macro_score'],
            breadth_pct > self.regime_thresholds['bull']['breadth'],
            momentum > self.regime_thresholds['bull']['momentum']
        ]
        
        # Bear market conditions  
        bear_conditions = [
            macro_score < self.regime_thresholds['bear']['macro_score'],
            breadth_pct < self.regime_thresholds['bear']['breadth'],
            momentum < self.regime_thresholds['bear']['momentum']
        ]
        
        # Regime classification
        if sum(bull_conditions) >= 2:
            return 'bull'
        elif sum(bear_conditions) >= 2:
            return 'bear'
        else:
            return 'neutral'
    
    def calculate_signal_likelihood(self, signal_value, signal_type, regime):
        """
        Calculate likelihood of signal given market regime
        
        P(signal | regime, outcome)
        
        Args:
            signal_value: Normalized signal value (-2 to +2)
            signal_type: 'valuation', 'momentum', 'macro', etc.
            regime: 'bull', 'bear', 'neutral'
        
        Returns:
            dict: Likelihoods for each outcome
        """
        
        # Get signal reliability for this regime
        reliability = self.signal_reliability[regime].get(signal_type, 0.7)
        
        # Signal strength (how far from neutral)
        signal_strength = abs(signal_value)
        
        # Adjust reliability by signal strength
        effective_reliability = reliability * min(1.0, signal_strength / 1.0)
        
        # Calculate likelihoods
        if signal_value > 0.5:  # Positive signal (expensive/uptrend/tightening)
            likelihoods = {
                'undervalued': 1 - effective_reliability,  # Unlikely if signal says expensive
                'fairly_valued': 0.5,                      # Neutral
                'overvalued': effective_reliability        # Likely if signal says expensive
            }
        elif signal_value < -0.5:  # Negative signal (cheap/downtrend/easing)
            likelihoods = {
                'undervalued': effective_reliability,      # Likely if signal says cheap
                'fairly_valued': 0.5,                      # Neutral
                'overvalued': 1 - effective_reliability    # Unlikely if signal says cheap
            }
        else:  # Neutral signal
            likelihoods = {
                'undervalued': 0.4,
                'fairly_valued': 0.6,
                'overvalued': 0.4
            }
        
        # Normalize to sum to 1
        total = sum(likelihoods.values())
        if total > 0:
            likelihoods = {k: v/total for k, v in likelihoods.items()}
        
        return likelihoods
    
    def bayesian_update(self, priors, likelihoods_list):
        """
        Perform Bayesian update with multiple signals
        
        P(outcome | signals) ∝ P(outcome) × ∏P(signal_i | outcome)
        
        Args:
            priors: Prior probabilities for each outcome
            likelihoods_list: List of likelihood dicts from each signal
        
        Returns:
            dict: Posterior probabilities
        """
        
        outcomes = list(priors.keys())
        posteriors = {}
        
        for outcome in outcomes:
            # Start with prior
            posterior = priors[outcome]
            
            # Multiply by each signal's likelihood
            for likelihoods in likelihoods_list:
                posterior *= likelihoods.get(outcome, 0.5)
            
            posteriors[outcome] = posterior
        
        # Normalize
        total = sum(posteriors.values())
        if total > 0:
            posteriors = {k: v/total for k, v in posteriors.items()}
        else:
            posteriors = priors.copy()  # Fallback to priors
        
        return posteriors
    
    def calculate_conviction(self, posteriors):
        """
        Calculate conviction based on posterior distribution
        
        High conviction = one outcome has high probability
        Low conviction = probabilities are spread out
        
        Args:
            posteriors: Posterior probability distribution
        
        Returns:
            float: Conviction score (0-1)
        """
        
        # Maximum probability
        max_prob = max(posteriors.values())
        
        # Entropy-based conviction (lower entropy = higher conviction)
        entropy = -sum(p * np.log(p + 1e-10) for p in posteriors.values())
        max_entropy = np.log(len(posteriors))  # Maximum possible entropy
        
        # Conviction from entropy (1 - normalized_entropy)
        entropy_conviction = 1 - (entropy / max_entropy)
        
        # Conviction from max probability
        prob_conviction = (max_prob - 1/len(posteriors)) / (1 - 1/len(posteriors))
        
        # Combined conviction
        conviction = 0.6 * prob_conviction + 0.4 * entropy_conviction
        
        return max(0, min(1, conviction))
    
    def fuse_contradictory_signals(self, signals, current_time=None, market_state=None, regime=None):
        """
        Main function: Fuse contradictory signals using Bayesian approach
        
        Args:
            signals: Dict of signal_name -> signal_value
            market_state: Current market state (optional)
            regime: Market regime override (optional)
        
        Returns:
            dict: Bayesian fusion result
        """
        
        # Detect regime if not provided
        if regime is None:
            regime = self.detect_market_regime(market_state)
        
        print(f"🧠 Bayesian fusion in {regime.upper()} regime")
        
        # Calculate likelihoods for each signal
        likelihoods_list = []
        signal_analysis = {}
        
        for signal_name, signal_value in signals.items():
            # Normalize signal value to [-2, +2] range if needed
            if abs(signal_value) > 10:  # Assume it's a percentage or large number
                normalized_value = np.clip(signal_value / 50, -2, 2)
            else:
                normalized_value = np.clip(signal_value, -2, 2)
            
            # Calculate likelihood
            likelihoods = self.calculate_signal_likelihood(
                normalized_value, signal_name, regime
            )
            
            likelihoods_list.append(likelihoods)
            
            # Store analysis
            signal_analysis[signal_name] = {
                'raw_value': signal_value,
                'normalized_value': normalized_value,
                'likelihoods': likelihoods,
                'reliability': self.signal_reliability[regime].get(signal_name, 0.7),
                'regime_weight': self.signal_reliability[regime].get(signal_name, 0.7)
            }
        
        # Perform Bayesian update
        posteriors = self.bayesian_update(self.priors, likelihoods_list)
        
        # Calculate conviction
        conviction = self.calculate_conviction(posteriors)
        
        # Determine final assessment
        max_outcome = max(posteriors.keys(), key=lambda k: posteriors[k])
        max_probability = posteriors[max_outcome]
        
        # Convert to investment signal
        if max_outcome == 'undervalued':
            investment_signal = posteriors['undervalued'] - posteriors['overvalued']
        elif max_outcome == 'overvalued':
            investment_signal = posteriors['overvalued'] - posteriors['undervalued']
        else:  # fairly_valued
            investment_signal = 0.0
        
        # Adjust signal by conviction
        final_signal = investment_signal * conviction
        
        # Generate narrative
        narrative = self.generate_bayesian_narrative(
            signals, signal_analysis, posteriors, conviction, regime
        )
        
        return {
            'final_signal': final_signal,
            'conviction': conviction,
            'regime': regime,
            'posteriors': posteriors,
            'most_likely_outcome': max_outcome,
            'outcome_probability': max_probability,
            'signal_analysis': signal_analysis,
            'narrative': narrative,
            'contradictions_resolved': len([s for s in signals.values() if abs(s) > 0.5]) > 1
        }
    
    def generate_bayesian_narrative(self, signals, signal_analysis, posteriors, conviction, regime):
        """Generate human-readable narrative of Bayesian analysis"""
        
        # Most likely outcome
        max_outcome = max(posteriors.keys(), key=lambda k: posteriors[k])
        max_prob = posteriors[max_outcome]
        
        # Signal agreement analysis
        positive_signals = [name for name, value in signals.items() if value > 0.5]
        negative_signals = [name for name, value in signals.items() if value < -0.5]
        
        # Start narrative
        narrative = f"Bayesian analysis in {regime} market: "
        
        # Outcome assessment
        if max_outcome == 'undervalued':
            narrative += f"Stock likely UNDERVALUED ({max_prob:.1%} probability). "
        elif max_outcome == 'overvalued':
            narrative += f"Stock likely OVERVALUED ({max_prob:.1%} probability). "
        else:
            narrative += f"Stock appears FAIRLY VALUED ({max_prob:.1%} probability). "
        
        # Conviction assessment
        if conviction > 0.8:
            narrative += "HIGH CONVICTION - signals align well. "
        elif conviction > 0.6:
            narrative += "MODERATE CONVICTION - some signal disagreement. "
        else:
            narrative += "LOW CONVICTION - significant contradictions. "
        
        # Signal breakdown
        if positive_signals and negative_signals:
            narrative += f"Contradictions: {', '.join(positive_signals)} vs {', '.join(negative_signals)}. "
        
        # Regime implications
        if regime == 'bull':
            narrative += "Bull market: momentum signals weighted higher. "
        elif regime == 'bear':
            narrative += "Bear market: valuation signals weighted higher. "
        else:
            narrative += "Neutral market: balanced signal weighting. "
        
        return narrative
    
    def analyze_signal_contradictions(self, signals):
        """
        Analyze contradictions between signals
        
        Returns detailed breakdown of where signals disagree
        """
        
        contradictions = []
        signal_items = list(signals.items())
        
        for i, (name1, value1) in enumerate(signal_items):
            for name2, value2 in signal_items[i+1:]:
                # Check if signals contradict (opposite signs with significant magnitude)
                if (value1 > 0.5 and value2 < -0.5) or (value1 < -0.5 and value2 > 0.5):
                    contradiction_strength = abs(value1) + abs(value2)
                    contradictions.append({
                        'signal1': name1,
                        'value1': value1,
                        'signal2': name2,
                        'value2': value2,
                        'strength': contradiction_strength,
                        'description': f"{name1} ({value1:+.2f}) contradicts {name2} ({value2:+.2f})"
                    })
        
        # Sort by contradiction strength
        contradictions.sort(key=lambda x: x['strength'], reverse=True)
        
        return contradictions

# =========================== REGIME-AWARE WEIGHT CALCULATOR ===========================

class RegimeAwareWeightCalculator:
    """
    Calculate dynamic weights based on market regime
    
    This implements the core insight:
    - Bull markets: Trend matters more than cheap
    - Bear markets: Cheap matters more than trend
    """
    
    def __init__(self):
        self.regime_weights = {
            'bull': {
                'valuation': 0.20,    # 20% weight on valuation
                'momentum': 0.50,     # 50% weight on momentum
                'macro': 0.15,        # 15% weight on macro
                'quality': 0.10,      # 10% weight on quality
                'flows': 0.05         # 5% weight on flows
            },
            'bear': {
                'valuation': 0.50,    # 50% weight on valuation
                'momentum': 0.15,     # 15% weight on momentum
                'macro': 0.20,        # 20% weight on macro
                'quality': 0.10,      # 10% weight on quality
                'flows': 0.05         # 5% weight on flows
            },
            'neutral': {
                'valuation': 0.35,    # 35% weight on valuation
                'momentum': 0.35,     # 35% weight on momentum
                'macro': 0.20,        # 20% weight on macro
                'quality': 0.05,      # 5% weight on quality
                'flows': 0.05         # 5% weight on flows
            }
        }
    
    def get_regime_weights(self, regime, custom_weights=None):
        """Get weights for specific regime"""
        
        base_weights = self.regime_weights.get(regime, self.regime_weights['neutral'])
        
        if custom_weights:
            # Merge custom weights
            weights = base_weights.copy()
            weights.update(custom_weights)
            
            # Renormalize to sum to 1
            total = sum(weights.values())
            if total > 0:
                weights = {k: v/total for k, v in weights.items()}
        else:
            weights = base_weights
        
        return weights
    
    def calculate_weighted_score(self, signals, regime, custom_weights=None):
        """
        Calculate regime-aware weighted score
        
        This is the simple implementation of dynamic weighting
        """
        
        weights = self.get_regime_weights(regime, custom_weights)
        
        weighted_score = 0.0
        total_weight = 0.0
        
        for signal_name, signal_value in signals.items():
            weight = weights.get(signal_name, 0.0)
            weighted_score += weight * signal_value
            total_weight += weight
        
        # Normalize if we don't have all expected signals
        if total_weight > 0 and total_weight != 1.0:
            weighted_score = weighted_score / total_weight
        
        return {
            'weighted_score': weighted_score,
            'regime': regime,
            'weights_used': weights,
            'total_weight': total_weight,
            'signals_processed': len(signals)
        }

# =========================== CONTRADICTION RESOLVER ===========================

class ContradictionResolver:
    """
    Resolve specific types of contradictions using domain knowledge
    """
    
    def __init__(self):
        self.fusion_engine = BayesianSignalFusion()
        self.weight_calculator = RegimeAwareWeightCalculator()
    
    def resolve_valuation_momentum_contradiction(self, valuation_signal, momentum_signal, regime):
        """
        Resolve valuation vs momentum contradiction
        
        Classic case: Stock is cheap but trending down (or expensive but trending up)
        """
        
        signals = {
            'valuation': valuation_signal,
            'momentum': momentum_signal
        }
        
        # Use Bayesian fusion
        bayesian_result = self.fusion_engine.fuse_contradictory_signals(signals, regime=regime)
        
        # Also calculate simple regime-weighted average for comparison
        weighted_result = self.weight_calculator.calculate_weighted_score(signals, regime)
        
        # Determine resolution strategy
        if regime == 'bull':
            # In bull markets, momentum usually wins
            resolution = "Favor momentum over valuation in bull market"
            primary_signal = momentum_signal
            confidence_adjustment = 0.8
        elif regime == 'bear':
            # In bear markets, valuation usually wins
            resolution = "Favor valuation over momentum in bear market"
            primary_signal = valuation_signal
            confidence_adjustment = 0.8
        else:
            # In neutral markets, use Bayesian result
            resolution = "Balanced approach - use Bayesian fusion"
            primary_signal = bayesian_result['final_signal']
            confidence_adjustment = bayesian_result['conviction']
        
        return {
            'resolved_signal': primary_signal * confidence_adjustment,
            'resolution_method': resolution,
            'regime': regime,
            'bayesian_result': bayesian_result,
            'weighted_result': weighted_result,
            'confidence': confidence_adjustment,
            'contradiction_type': 'valuation_momentum'
        }
    
    def resolve_macro_micro_contradiction(self, macro_signal, micro_signals, regime):
        """
        Resolve macro vs micro contradictions
        
        Example: Macro says tightening but stock fundamentals look good
        """
        
        # Combine micro signals
        avg_micro = np.mean(list(micro_signals.values()))
        
        signals = {
            'macro': macro_signal,
            'micro_average': avg_micro
        }
        
        # Macro typically dominates in extreme regimes
        if abs(macro_signal) > 1.5:  # Strong macro signal
            resolution = "Strong macro signal dominates micro factors"
            resolved_signal = macro_signal * 0.8 + avg_micro * 0.2
            confidence = 0.8
        else:
            # Use Bayesian fusion for moderate macro signals
            bayesian_result = self.fusion_engine.fuse_contradictory_signals(signals, regime=regime)
            resolution = "Moderate macro - use Bayesian fusion with micro"
            resolved_signal = bayesian_result['final_signal']
            confidence = bayesian_result['conviction']
        
        return {
            'resolved_signal': resolved_signal,
            'resolution_method': resolution,
            'regime': regime,
            'macro_dominance': abs(macro_signal) > 1.5,
            'confidence': confidence,
            'contradiction_type': 'macro_micro'
        }

# =========================== MAIN EXECUTION ===========================

def main():
    """Demonstrate Bayesian contradiction handling"""
    
    print("⚔️ BAYESIAN CONTRADICTION HANDLER - INSTITUTIONAL GRADE SIGNAL FUSION")
    print("=" * 80)
    
    # Initialize engines
    fusion = BayesianSignalFusion()
    resolver = ContradictionResolver()
    
    # Example 1: Classic contradiction
    print("\n📊 Example 1: Classic Valuation vs Momentum Contradiction")
    print("-" * 60)
    
    contradictory_signals = {
        'valuation': -1.5,  # Stock looks cheap
        'momentum': 0.8,    # But trending up
        'macro': -0.5       # Macro is tightening
    }
    
    result = fusion.fuse_contradictory_signals(contradictory_signals)
    
    print(f"Signals: Valuation={contradictory_signals['valuation']:.1f}, "
          f"Momentum={contradictory_signals['momentum']:.1f}, "
          f"Macro={contradictory_signals['macro']:.1f}")
    print(f"Regime: {result['regime'].upper()}")
    print(f"Final Signal: {result['final_signal']:.3f}")
    print(f"Conviction: {result['conviction']:.3f}")
    print(f"Most Likely: {result['most_likely_outcome']} ({result['outcome_probability']:.1%})")
    print(f"Narrative: {result['narrative']}")
    
    # Example 2: Regime-aware weighting
    print("\n🎯 Example 2: Regime-Aware Dynamic Weighting")
    print("-" * 60)
    
    weight_calc = RegimeAwareWeightCalculator()
    
    test_signals = {
        'valuation': -1.0,  # Cheap
        'momentum': 1.0     # Uptrend
    }
    
    for regime in ['bull', 'bear', 'neutral']:
        weighted = weight_calc.calculate_weighted_score(test_signals, regime)
        print(f"{regime.upper()} market: Score={weighted['weighted_score']:.3f}, "
              f"Weights={weighted['weights_used']}")
    
    # Example 3: Contradiction resolution
    print("\n⚔️ Example 3: Specific Contradiction Resolution")
    print("-" * 60)
    
    resolution = resolver.resolve_valuation_momentum_contradiction(
        valuation_signal=-1.2,  # Cheap
        momentum_signal=0.9,    # Strong uptrend
        regime='bear'           # Bear market
    )
    
    print(f"Valuation: {-1.2:.1f} (cheap)")
    print(f"Momentum: {0.9:.1f} (uptrend)")
    print(f"Regime: BEAR")
    print(f"Resolution: {resolution['resolution_method']}")
    print(f"Resolved Signal: {resolution['resolved_signal']:.3f}")
    print(f"Confidence: {resolution['confidence']:.3f}")
    
    print("\n✅ Bayesian contradiction handler operational")
    print("💡 Key insight: Bull markets favor momentum, Bear markets favor valuation")

if __name__ == "__main__":
    main()
