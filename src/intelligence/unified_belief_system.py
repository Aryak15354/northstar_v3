#!/usr/bin/env python3
"""
🔗 UNIFIED BELIEF SYSTEM - NORTHSTAR V3 PHASE 3
Single Belief Framework: Merging All Intelligence Sources

This creates a unified belief system that merges:
1. Market Intelligence (Market Brain) - Pulse, regime, survival instincts
2. Valuation Intelligence (Intelligence Stack) - 4 engines, confidence, Bayesian fusion
3. Strategy Intelligence (Strategy System) - Beliefs, regret, capital allocation

The unified belief system resolves contradictions, weights sources by confidence,
and produces coherent investment beliefs that drive portfolio construction.

Usage:
    try:
    from intelligence.unified_belief_system import UnifiedBeliefSystem
except ImportError:
    from UnifiedBeliefSystem import UnifiedBeliefSystem
    
    belief_system = UnifiedBeliefSystem()
    unified_beliefs = belief_system.merge_beliefs(market_intel, valuation_intel, strategy_intel)
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class UnifiedBeliefSystem:
    """
    Unified Belief System - Single Source of Investment Truth
    
    Merges all intelligence sources into coherent beliefs that resolve
    contradictions and provide clear investment direction.
    """
    
    def __init__(self):
        self.name = "Unified Belief System"
        self.version = "1.0"
        
        # Belief weighting parameters
        self.source_weights = {
            'market_brain': 0.4,      # Market intelligence weight
            'intelligence_stack': 0.4, # Valuation intelligence weight
            'strategy_intelligence': 0.2 # Strategy intelligence weight
        }
        
        # Confidence thresholds
        self.confidence_thresholds = {
            'high': 0.7,
            'medium': 0.5,
            'low': 0.3
        }
        
        # Output directory
        self.output_dir = 'data/processed'
        os.makedirs(self.output_dir, exist_ok=True)
    
    def merge_beliefs(self, market_intel, valuation_intel, strategy_intel):
        """
        Merge all intelligence sources into unified beliefs
        
        This is the core function that creates coherent investment beliefs
        from multiple intelligence sources.
        """
        
        print("🔗 MERGING INTELLIGENCE INTO UNIFIED BELIEFS")
        print("-" * 50)
        
        # Initialize unified beliefs structure
        unified_beliefs = {
            'timestamp': datetime.now().isoformat(),
            'version': self.version,
            'synthesis_method': 'unified_belief_system',
            'source_weights': self.source_weights,
            'market_beliefs': {},
            'valuation_beliefs': {},
            'strategy_beliefs': {},
            'unified_stance': 'neutral',
            'unified_conviction': 0.5,
            'unified_actions': {},
            'confidence_metrics': {},
            'risk_assessment': {},
            'contradiction_analysis': {},
            'belief_evolution': {}
        }
        
        # Step 1: Extract and normalize beliefs from each source
        print("   1️⃣ Extracting beliefs from intelligence sources...")
        
        market_beliefs = self.extract_market_beliefs(market_intel)
        valuation_beliefs = self.extract_valuation_beliefs(valuation_intel)
        strategy_beliefs = self.extract_strategy_beliefs(strategy_intel)
        
        unified_beliefs['market_beliefs'] = market_beliefs
        unified_beliefs['valuation_beliefs'] = valuation_beliefs
        unified_beliefs['strategy_beliefs'] = strategy_beliefs
        
        # Step 2: Analyze contradictions between sources
        print("   2️⃣ Analyzing contradictions between sources...")
        
        contradictions = self.analyze_contradictions(market_beliefs, valuation_beliefs, strategy_beliefs)
        unified_beliefs['contradiction_analysis'] = contradictions
        
        # Step 3: Calculate confidence-weighted synthesis
        print("   3️⃣ Synthesizing confidence-weighted beliefs...")
        
        synthesis_result = self.synthesize_weighted_beliefs(
            market_beliefs, valuation_beliefs, strategy_beliefs, contradictions
        )
        
        unified_beliefs.update(synthesis_result)
        
        # Step 4: Generate unified actions
        print("   4️⃣ Generating unified investment actions...")
        
        unified_actions = self.generate_unified_actions(unified_beliefs)
        unified_beliefs['unified_actions'] = unified_actions
        
        # Step 5: Assess overall risk
        print("   5️⃣ Assessing unified risk profile...")
        
        risk_assessment = self.assess_unified_risk(unified_beliefs)
        unified_beliefs['risk_assessment'] = risk_assessment
        
        # Step 6: Track belief evolution
        print("   6️⃣ Tracking belief evolution...")
        
        belief_evolution = self.track_belief_evolution(unified_beliefs)
        unified_beliefs['belief_evolution'] = belief_evolution
        
        # Save unified beliefs
        self.save_unified_beliefs(unified_beliefs)
        
        print("   ✅ Unified beliefs synthesis complete")
        
        return unified_beliefs
    
    def extract_market_beliefs(self, market_intel):
        """Extract and normalize market intelligence beliefs"""
        
        market_beliefs = {
            'available': False,
            'pulse_intensity': 0.0,
            'market_phase': 'neutral',
            'risk_level': 'low',
            'survival_mode': 'normal',
            'regime_info': {},
            'confidence': 0.0,
            'stance': 'neutral'
        }
        
        if market_intel and market_intel.get('status') == 'success':
            market_beliefs['available'] = True
            
            # Extract pulse state
            pulse_state = market_intel.get('pulse_state', {})
            market_beliefs['pulse_intensity'] = pulse_state.get('pulse_intensity', 0.0)
            market_beliefs['market_phase'] = pulse_state.get('market_phase', 'neutral')
            market_beliefs['risk_level'] = pulse_state.get('risk_level', 'low')
            
            # Extract survival state
            survival_state = market_intel.get('survival_state', {})
            market_beliefs['survival_mode'] = survival_state.get('survival_mode', 'normal')
            
            # Extract regime info
            market_beliefs['regime_info'] = market_intel.get('regime_info', {})
            
            # Calculate market confidence based on pulse intensity and survival mode
            pulse_confidence = min(market_beliefs['pulse_intensity'] * 2, 1.0)  # Scale to 0-1
            survival_confidence = 1.0 if market_beliefs['survival_mode'] == 'normal' else 0.5
            market_beliefs['confidence'] = (pulse_confidence + survival_confidence) / 2
            
            # Determine market stance
            if market_beliefs['market_phase'] == 'expansion':
                market_beliefs['stance'] = 'bullish'
            elif market_beliefs['market_phase'] == 'contraction':
                market_beliefs['stance'] = 'bearish'
            elif market_beliefs['survival_mode'] != 'normal':
                market_beliefs['stance'] = 'defensive'
            else:
                market_beliefs['stance'] = 'neutral'
        
        return market_beliefs
    
    def extract_valuation_beliefs(self, valuation_intel):
        """Extract and normalize valuation intelligence beliefs"""
        
        valuation_beliefs = {
            'available': False,
            'market_stance': 'Neutral',
            'conviction': 0.5,
            'valuation_assessment': {},
            'recommended_exposure': 50.0,
            'confidence': 0.5,
            'stance': 'neutral'
        }
        
        if valuation_intel and valuation_intel.get('status') == 'success':
            valuation_beliefs['available'] = True
            
            # Extract beliefs
            beliefs = valuation_intel.get('beliefs', {})
            market_beliefs_data = beliefs.get('market_beliefs', {})
            conviction_levels = beliefs.get('conviction_levels', {})
            
            valuation_beliefs['market_stance'] = market_beliefs_data.get('stance', 'Neutral')
            valuation_beliefs['conviction'] = conviction_levels.get('overall', 0.5)
            valuation_beliefs['valuation_assessment'] = beliefs.get('valuation_beliefs', {})
            
            # Extract actions
            actions = valuation_intel.get('actions', {})
            exposure_rec = actions.get('exposure_recommendation', {})
            valuation_beliefs['recommended_exposure'] = exposure_rec.get('target_exposure', 50.0)
            
            # Set confidence as conviction
            valuation_beliefs['confidence'] = valuation_beliefs['conviction']
            
            # Normalize stance
            stance_mapping = {
                'Bullish': 'bullish',
                'Bearish': 'bearish',
                'Neutral': 'neutral'
            }
            valuation_beliefs['stance'] = stance_mapping.get(valuation_beliefs['market_stance'], 'neutral')
        
        return valuation_beliefs
    
    def extract_strategy_beliefs(self, strategy_intel):
        """Extract and normalize strategy intelligence beliefs"""
        
        strategy_beliefs = {
            'available': False,
            'total_strategies': 0,
            'avg_skill_prob': 0.5,
            'avg_confidence': 0.5,
            'top_strategies': [],
            'confidence': 0.5,
            'stance': 'neutral'
        }
        
        if strategy_intel and strategy_intel.get('status') == 'success':
            strategy_beliefs['available'] = True
            
            # Extract strategy summary
            strategy_summary = strategy_intel.get('strategy_summary', {})
            strategy_insights = strategy_summary.get('strategy_insights', {})
            
            strategy_beliefs['total_strategies'] = strategy_insights.get('total_strategies', 0)
            strategy_beliefs['avg_skill_prob'] = strategy_insights.get('avg_skill_prob', 0.5)
            strategy_beliefs['avg_confidence'] = strategy_insights.get('avg_confidence', 0.5)
            strategy_beliefs['top_strategies'] = strategy_insights.get('top_strategies', [])
            
            # Set confidence as average of skill and confidence
            strategy_beliefs['confidence'] = (strategy_beliefs['avg_skill_prob'] + strategy_beliefs['avg_confidence']) / 2
            
            # Determine stance based on strategy performance
            if strategy_beliefs['avg_skill_prob'] > 0.6:
                strategy_beliefs['stance'] = 'bullish'  # High skill = bullish on strategies
            elif strategy_beliefs['avg_skill_prob'] < 0.4:
                strategy_beliefs['stance'] = 'bearish'  # Low skill = bearish on strategies
            else:
                strategy_beliefs['stance'] = 'neutral'
        
        return strategy_beliefs
    
    def analyze_contradictions(self, market_beliefs, valuation_beliefs, strategy_beliefs):
        """Analyze contradictions between intelligence sources"""
        
        contradictions = {
            'stance_conflicts': [],
            'confidence_divergence': 0.0,
            'major_contradictions': [],
            'resolution_needed': False
        }
        
        # Collect stances
        stances = []
        if market_beliefs['available']:
            stances.append(('market', market_beliefs['stance']))
        if valuation_beliefs['available']:
            stances.append(('valuation', valuation_beliefs['stance']))
        if strategy_beliefs['available']:
            stances.append(('strategy', strategy_beliefs['stance']))
        
        # Check for stance conflicts
        unique_stances = set([stance for _, stance in stances])
        if len(unique_stances) > 1:
            contradictions['stance_conflicts'] = stances
            contradictions['resolution_needed'] = True
        
        # Check confidence divergence
        confidences = []
        if market_beliefs['available']:
            confidences.append(market_beliefs['confidence'])
        if valuation_beliefs['available']:
            confidences.append(valuation_beliefs['confidence'])
        if strategy_beliefs['available']:
            confidences.append(strategy_beliefs['confidence'])
        
        if len(confidences) > 1:
            contradictions['confidence_divergence'] = np.std(confidences)
            if contradictions['confidence_divergence'] > 0.3:
                contradictions['major_contradictions'].append('High confidence divergence')
                contradictions['resolution_needed'] = True
        
        # Specific contradiction checks
        if (market_beliefs['available'] and valuation_beliefs['available'] and 
            market_beliefs['stance'] != valuation_beliefs['stance']):
            contradictions['major_contradictions'].append('Market vs Valuation stance conflict')
        
        if (market_beliefs['available'] and market_beliefs['survival_mode'] != 'normal' and
            valuation_beliefs['available'] and valuation_beliefs['stance'] == 'bullish'):
            contradictions['major_contradictions'].append('Survival mode vs Bullish valuation conflict')
        
        return contradictions
    
    def synthesize_weighted_beliefs(self, market_beliefs, valuation_beliefs, strategy_beliefs, contradictions):
        """Synthesize beliefs using confidence weighting and contradiction resolution"""
        
        # Calculate dynamic weights based on availability and confidence
        weights = {}
        total_weight = 0.0
        
        if market_beliefs['available']:
            weights['market'] = self.source_weights['market_brain'] * market_beliefs['confidence']
            total_weight += weights['market']
        
        if valuation_beliefs['available']:
            weights['valuation'] = self.source_weights['intelligence_stack'] * valuation_beliefs['confidence']
            total_weight += weights['valuation']
        
        if strategy_beliefs['available']:
            weights['strategy'] = self.source_weights['strategy_intelligence'] * strategy_beliefs['confidence']
            total_weight += weights['strategy']
        
        # Normalize weights
        if total_weight > 0:
            for key in weights:
                weights[key] /= total_weight
        
        # Synthesize unified stance
        stance_scores = {'bullish': 0.0, 'bearish': 0.0, 'neutral': 0.0, 'defensive': 0.0}
        
        if market_beliefs['available']:
            stance_scores[market_beliefs['stance']] += weights.get('market', 0.0)
        
        if valuation_beliefs['available']:
            stance_scores[valuation_beliefs['stance']] += weights.get('valuation', 0.0)
        
        if strategy_beliefs['available']:
            stance_scores[strategy_beliefs['stance']] += weights.get('strategy', 0.0)
        
        # Determine unified stance
        unified_stance = max(stance_scores, key=stance_scores.get)
        
        # Calculate unified conviction
        weighted_convictions = []
        if market_beliefs['available']:
            weighted_convictions.append(market_beliefs['confidence'] * weights.get('market', 0.0))
        if valuation_beliefs['available']:
            weighted_convictions.append(valuation_beliefs['conviction'] * weights.get('valuation', 0.0))
        if strategy_beliefs['available']:
            weighted_convictions.append(strategy_beliefs['confidence'] * weights.get('strategy', 0.0))
        
        unified_conviction = sum(weighted_convictions) if weighted_convictions else 0.5
        
        # Adjust for contradictions
        if contradictions['resolution_needed']:
            # Reduce conviction when there are major contradictions
            contradiction_penalty = len(contradictions['major_contradictions']) * 0.1
            unified_conviction = max(0.1, unified_conviction - contradiction_penalty)
        
        # Calculate confidence metrics
        confidence_metrics = {
            'source_weights': weights,
            'stance_scores': stance_scores,
            'weighted_conviction': unified_conviction,
            'contradiction_penalty': len(contradictions['major_contradictions']) * 0.1 if contradictions['resolution_needed'] else 0.0,
            'overall_confidence': unified_conviction
        }
        
        return {
            'unified_stance': unified_stance,
            'unified_conviction': unified_conviction,
            'confidence_metrics': confidence_metrics
        }
    
    def generate_unified_actions(self, unified_beliefs):
        """Generate unified investment actions"""
        
        # Base exposure from valuation beliefs
        base_exposure = unified_beliefs['valuation_beliefs'].get('recommended_exposure', 50.0)
        
        # Adjust based on unified stance and conviction
        stance = unified_beliefs['unified_stance']
        conviction = unified_beliefs['unified_conviction']
        
        # Stance adjustments
        if stance == 'bullish':
            exposure_multiplier = 1.0 + (conviction * 0.5)  # Up to 50% increase
        elif stance == 'bearish':
            exposure_multiplier = 1.0 - (conviction * 0.6)  # Up to 60% decrease
        elif stance == 'defensive':
            exposure_multiplier = 0.5  # Fixed 50% reduction for defensive
        else:  # neutral
            exposure_multiplier = 1.0
        
        target_exposure = base_exposure * exposure_multiplier
        
        # Apply survival mode constraints
        survival_mode = unified_beliefs['market_beliefs'].get('survival_mode', 'normal')
        if survival_mode == 'defensive':
            target_exposure = min(target_exposure, 40.0)
        elif survival_mode == 'crisis':
            target_exposure = min(target_exposure, 20.0)
        
        # Ensure reasonable bounds
        target_exposure = max(5.0, min(95.0, target_exposure))
        
        # Determine execution priority
        if survival_mode != 'normal':
            execution_priority = 'high'
        elif conviction > 0.7:
            execution_priority = 'high'
        elif conviction < 0.3:
            execution_priority = 'low'
        else:
            execution_priority = 'medium'
        
        return {
            'target_exposure': target_exposure,
            'base_exposure': base_exposure,
            'exposure_multiplier': exposure_multiplier,
            'primary_action': stance.upper(),
            'execution_priority': execution_priority,
            'risk_adjustment': survival_mode,
            'conviction_level': 'high' if conviction > 0.7 else 'medium' if conviction > 0.4 else 'low'
        }
    
    def assess_unified_risk(self, unified_beliefs):
        """Assess unified risk profile"""
        
        risk_factors = []
        risk_score = 0.0
        
        # Market risk factors
        market_beliefs = unified_beliefs['market_beliefs']
        if market_beliefs.get('available'):
            risk_level = market_beliefs.get('risk_level', 'low')
            survival_mode = market_beliefs.get('survival_mode', 'normal')
            pulse_intensity = market_beliefs.get('pulse_intensity', 0.0)
            
            if risk_level == 'high':
                risk_factors.append('High market risk level')
                risk_score += 0.3
            
            if survival_mode != 'normal':
                risk_factors.append(f'Survival mode: {survival_mode}')
                risk_score += 0.4 if survival_mode == 'crisis' else 0.2
            
            if pulse_intensity > 0.8:
                risk_factors.append('High market pulse intensity')
                risk_score += 0.2
        
        # Contradiction risk
        contradictions = unified_beliefs.get('contradiction_analysis', {})
        if contradictions.get('resolution_needed'):
            risk_factors.append('Intelligence source contradictions')
            risk_score += len(contradictions.get('major_contradictions', [])) * 0.1
        
        # Confidence risk
        conviction = unified_beliefs.get('unified_conviction', 0.5)
        if conviction < 0.3:
            risk_factors.append('Low conviction environment')
            risk_score += 0.2
        
        # Overall risk assessment
        if risk_score > 0.6:
            overall_risk = 'high'
        elif risk_score > 0.3:
            overall_risk = 'medium'
        else:
            overall_risk = 'low'
        
        return {
            'overall_risk': overall_risk,
            'risk_score': risk_score,
            'risk_factors': risk_factors,
            'market_risk_level': market_beliefs.get('risk_level', 'low'),
            'pulse_intensity': market_beliefs.get('pulse_intensity', 0.0),
            'survival_mode': market_beliefs.get('survival_mode', 'normal'),
            'contradiction_risk': contradictions.get('resolution_needed', False)
        }
    
    def track_belief_evolution(self, unified_beliefs):
        """Track how beliefs evolve over time"""
        
        # Load previous beliefs if available
        evolution_file = os.path.join(self.output_dir, 'belief_evolution.json')
        previous_beliefs = None
        
        if os.path.exists(evolution_file):
            try:
                with open(evolution_file, 'r') as f:
                    evolution_data = json.load(f)
                    if evolution_data.get('history'):
                        previous_beliefs = evolution_data['history'][-1]
            except:
                pass
        
        evolution = {
            'stance_changed': False,
            'conviction_change': 0.0,
            'exposure_change': 0.0,
            'risk_change': 'stable',
            'evolution_summary': 'Initial belief state'
        }
        
        if previous_beliefs:
            # Compare stances
            prev_stance = previous_beliefs.get('unified_stance', 'neutral')
            curr_stance = unified_beliefs['unified_stance']
            evolution['stance_changed'] = prev_stance != curr_stance
            
            # Compare conviction
            prev_conviction = previous_beliefs.get('unified_conviction', 0.5)
            curr_conviction = unified_beliefs['unified_conviction']
            evolution['conviction_change'] = curr_conviction - prev_conviction
            
            # Compare exposure
            prev_exposure = previous_beliefs.get('unified_actions', {}).get('target_exposure', 50.0)
            curr_exposure = unified_beliefs['unified_actions']['target_exposure']
            evolution['exposure_change'] = curr_exposure - prev_exposure
            
            # Compare risk
            prev_risk = previous_beliefs.get('risk_assessment', {}).get('overall_risk', 'low')
            curr_risk = unified_beliefs['risk_assessment']['overall_risk']
            
            if prev_risk != curr_risk:
                if curr_risk == 'high' and prev_risk != 'high':
                    evolution['risk_change'] = 'increased'
                elif curr_risk == 'low' and prev_risk != 'low':
                    evolution['risk_change'] = 'decreased'
                else:
                    evolution['risk_change'] = 'changed'
            
            # Generate evolution summary
            changes = []
            if evolution['stance_changed']:
                changes.append(f"Stance: {prev_stance} → {curr_stance}")
            if abs(evolution['conviction_change']) > 0.1:
                direction = "increased" if evolution['conviction_change'] > 0 else "decreased"
                changes.append(f"Conviction {direction} by {abs(evolution['conviction_change']):.1%}")
            if abs(evolution['exposure_change']) > 5.0:
                direction = "increased" if evolution['exposure_change'] > 0 else "decreased"
                changes.append(f"Exposure {direction} by {abs(evolution['exposure_change']):.1f}%")
            
            evolution['evolution_summary'] = "; ".join(changes) if changes else "Beliefs stable"
        
        return evolution
    
    def save_unified_beliefs(self, unified_beliefs):
        """Save unified beliefs and track evolution"""
        
        # Save current beliefs
        beliefs_file = os.path.join(self.output_dir, 'unified_beliefs.json')
        with open(beliefs_file, 'w') as f:
            json.dump(unified_beliefs, f, indent=2, default=str)
        
        # Update evolution history
        evolution_file = os.path.join(self.output_dir, 'belief_evolution.json')
        
        evolution_data = {'history': []}
        if os.path.exists(evolution_file):
            try:
                with open(evolution_file, 'r') as f:
                    evolution_data = json.load(f)
            except:
                pass
        
        # Add current beliefs to history
        evolution_data['history'].append({
            'timestamp': unified_beliefs['timestamp'],
            'unified_stance': unified_beliefs['unified_stance'],
            'unified_conviction': unified_beliefs['unified_conviction'],
            'unified_actions': unified_beliefs['unified_actions'],
            'risk_assessment': unified_beliefs['risk_assessment']
        })
        
        # Keep only recent history (last 100 entries)
        evolution_data['history'] = evolution_data['history'][-100:]
        
        with open(evolution_file, 'w') as f:
            json.dump(evolution_data, f, indent=2, default=str)

def main():
    """Test Unified Belief System"""
    
    belief_system = UnifiedBeliefSystem()
    
    print("🧪 TESTING UNIFIED BELIEF SYSTEM")
    print("=" * 40)
    
    # Mock intelligence data for testing
    mock_market_intel = {
        'status': 'success',
        'pulse_state': {
            'pulse_intensity': 0.6,
            'market_phase': 'expansion',
            'risk_level': 'medium'
        },
        'survival_state': {
            'survival_mode': 'normal'
        },
        'regime_info': {}
    }
    
    mock_valuation_intel = {
        'status': 'success',
        'beliefs': {
            'market_beliefs': {'stance': 'Bullish'},
            'conviction_levels': {'overall': 0.7}
        },
        'actions': {
            'exposure_recommendation': {'target_exposure': 65.0}
        }
    }
    
    mock_strategy_intel = {
        'status': 'success',
        'strategy_summary': {
            'strategy_insights': {
                'total_strategies': 5,
                'avg_skill_prob': 0.6,
                'avg_confidence': 0.65
            }
        }
    }
    
    # Test belief synthesis
    unified_beliefs = belief_system.merge_beliefs(
        mock_market_intel, mock_valuation_intel, mock_strategy_intel
    )
    
    print(f"\nUnified Stance: {unified_beliefs['unified_stance']}")
    print(f"Unified Conviction: {unified_beliefs['unified_conviction']:.1%}")
    print(f"Target Exposure: {unified_beliefs['unified_actions']['target_exposure']:.1f}%")
    
    return unified_beliefs is not None

if __name__ == "__main__":
    main()