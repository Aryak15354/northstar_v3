#!/usr/bin/env python3
"""
🧬 FABRIC CAPITAL INTEGRATION - NORTHSTAR V3 MARKET BRAIN
The Anticipatory Allocator: Integrating Weekly Causal Fabric with Capital Allocation

This integrates Weekly Causal Fabric insights into the existing Capital Allocator:
- Strategy fitness multipliers based on causal pressure
- Anticipatory positioning from emerging relationships
- Risk adjustments from regime transition signals
- Sector rotation timing from relationship trends

Integration with V3:
- Enhances existing Capital Allocator with anticipatory intelligence
- Maintains backward compatibility with current allocation logic
- Adds causal relationship awareness to portfolio decisions
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import warnings
warnings.filterwarnings('ignore')

# Import V3 components
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.intelligence.market_brain.weekly_fabric_reader import WeeklyFabricReader

class FabricCapitalIntegration:
    """
    Fabric Capital Integration - Anticipatory Allocation Engine
    
    Integrates Weekly Causal Fabric insights into capital allocation:
    - Causal pressure-based strategy weighting
    - Anticipatory positioning from emerging relationships
    - Risk management from regime transition signals
    - Sector rotation timing from relationship evolution
    """
    
    def __init__(self):
        self.name = "Fabric Capital Integration"
        self.version = "1.0"
        
        # Initialize fabric reader
        self.fabric_reader = WeeklyFabricReader()
        
        # Integration configuration
        self.config = {
            'pressure_sensitivity': 0.3,      # How much pressure affects allocation
            'anticipatory_weight': 0.2,       # Weight for anticipatory signals
            'risk_adjustment_threshold': 0.6,  # Threshold for risk adjustments
            'sector_rotation_sensitivity': 0.25, # Sensitivity to sector signals
            'confidence_threshold': 0.6,       # Minimum confidence for decisions
            'max_allocation_shift': 0.15,      # Maximum allocation change per period
            'regime_transition_hedge': 0.1     # Cash buffer for regime transitions
        }
        
        # Strategy sensitivity matrix (how strategies respond to different pressures)
        self.strategy_sensitivity = {
            'momentum_strategies': {
                'macro': 0.4,      # Momentum benefits from macro tailwinds
                'flows': 0.6,      # Very sensitive to flow dynamics
                'fx': 0.3,         # Moderate FX sensitivity
                'credit': 0.2,     # Low credit sensitivity
                'liquidity': 0.5   # High liquidity sensitivity
            },
            'value_strategies': {
                'macro': 0.3,      # Value less sensitive to macro
                'flows': -0.2,     # Contrarian to flows
                'fx': 0.1,         # Low FX sensitivity
                'credit': 0.4,     # Sensitive to credit conditions
                'liquidity': 0.2   # Moderate liquidity sensitivity
            },
            'sector_rotation': {
                'macro': 0.5,      # High macro sensitivity
                'flows': 0.4,      # Sensitive to sector flows
                'fx': 0.4,         # FX affects sector competitiveness
                'credit': 0.3,     # Credit affects sector access
                'liquidity': 0.3   # Liquidity affects rotation speed
            },
            'defensive_strategies': {
                'macro': -0.3,     # Defensive when macro weakens
                'flows': -0.1,     # Less sensitive to flows
                'fx': 0.1,         # Low FX sensitivity
                'credit': 0.2,     # Moderate credit sensitivity
                'liquidity': 0.1   # Low liquidity sensitivity
            },
            'growth_strategies': {
                'macro': 0.6,      # High macro sensitivity
                'flows': 0.4,      # Sensitive to growth flows
                'fx': 0.2,         # Moderate FX sensitivity
                'credit': 0.3,     # Credit affects growth funding
                'liquidity': 0.4   # Liquidity affects growth valuations
            }
        }
        
        # Sector sensitivity to different factors
        self.sector_sensitivity = {
            'IT': {'fx': 0.7, 'flows': 0.5, 'macro': 0.4},
            'Banking': {'credit': 0.8, 'macro': 0.6, 'liquidity': 0.5},
            'FMCG': {'macro': 0.4, 'flows': 0.3, 'fx': -0.2},
            'Auto': {'macro': 0.6, 'credit': 0.4, 'fx': 0.3},
            'Pharma': {'fx': 0.5, 'flows': 0.4, 'macro': 0.3},
            'Energy': {'macro': 0.5, 'fx': 0.4, 'flows': 0.3}
        }
    
    def get_enhanced_allocation_weights(self, base_weights: Dict[str, float]) -> Dict[str, float]:
        """Get enhanced allocation weights incorporating causal fabric insights"""
        
        try:
            print("🧬 Enhancing allocation with causal fabric insights...")
            
            # Get fabric insights
            pressure = self.fabric_reader.get_current_market_pressure()
            trends = self.fabric_reader.get_relationship_trends()
            signals = self.fabric_reader.get_anticipatory_signals()
            
            # Calculate strategy fitness multipliers
            fitness_multipliers = self.calculate_strategy_fitness_multipliers(pressure, trends)
            
            # Calculate anticipatory adjustments
            anticipatory_adjustments = self.calculate_anticipatory_adjustments(signals)
            
            # Calculate risk adjustments
            risk_adjustments = self.calculate_risk_adjustments(pressure, signals)
            
            # Apply adjustments to base weights
            enhanced_weights = self.apply_fabric_adjustments(
                base_weights, 
                fitness_multipliers, 
                anticipatory_adjustments, 
                risk_adjustments
            )
            
            # Log the enhancements
            self.log_allocation_enhancements(
                base_weights, enhanced_weights, 
                fitness_multipliers, anticipatory_adjustments, risk_adjustments
            )
            
            return enhanced_weights
            
        except Exception as e:
            print(f"⚠️ Error enhancing allocation weights: {e}")
            return base_weights  # Return original weights if enhancement fails
    
    def calculate_strategy_fitness_multipliers(self, pressure: Dict, trends: Dict) -> Dict[str, float]:
        """Calculate strategy fitness multipliers based on current pressure"""
        
        try:
            fitness_multipliers = {}
            
            # Get pressure vectors
            pressure_vectors = pressure.get('pressure_vectors', {})
            
            if not pressure_vectors:
                return {strategy: 1.0 for strategy in self.strategy_sensitivity.keys()}
            
            # Calculate fitness for each strategy
            for strategy, sensitivities in self.strategy_sensitivity.items():
                total_fitness = 0.0
                total_weight = 0.0
                
                for pressure_type, sensitivity in sensitivities.items():
                    if pressure_type in pressure_vectors:
                        pressure_data = pressure_vectors[pressure_type]
                        pressure_value = pressure_data['pressure']
                        confidence = pressure_data['confidence']
                        
                        # Calculate fitness contribution
                        fitness_contribution = sensitivity * pressure_value * confidence
                        weight = confidence
                        
                        total_fitness += fitness_contribution * weight
                        total_weight += weight
                
                # Calculate average fitness
                if total_weight > 0:
                    avg_fitness = total_fitness / total_weight
                    # Convert to multiplier (1.0 = neutral, >1.0 = favorable, <1.0 = unfavorable)
                    multiplier = 1.0 + (avg_fitness * self.config['pressure_sensitivity'])
                    # Clamp to reasonable range
                    multiplier = max(0.5, min(1.5, multiplier))
                else:
                    multiplier = 1.0
                
                fitness_multipliers[strategy] = multiplier
            
            return fitness_multipliers
            
        except Exception as e:
            print(f"⚠️ Error calculating strategy fitness: {e}")
            return {strategy: 1.0 for strategy in self.strategy_sensitivity.keys()}
    
    def calculate_anticipatory_adjustments(self, signals: Dict) -> Dict[str, float]:
        """Calculate anticipatory adjustments based on emerging signals"""
        
        try:
            anticipatory_adjustments = {}
            
            signal_list = signals.get('signals', [])
            
            if not signal_list:
                return {}
            
            # Process high-confidence anticipatory signals
            for signal in signal_list:
                if signal['confidence'] >= self.config['confidence_threshold']:
                    signal_strength = signal['signal_strength']
                    horizon_weeks = signal['horizon_weeks']
                    
                    # Determine strategy implications
                    strategy_implications = self.interpret_signal_for_strategies(signal)
                    
                    # Apply time decay (closer signals have more impact)
                    time_decay = max(0.1, 1.0 - (horizon_weeks / 52.0))  # Decay over a year
                    
                    for strategy, impact in strategy_implications.items():
                        adjustment = impact * signal_strength * time_decay * self.config['anticipatory_weight']
                        
                        if strategy in anticipatory_adjustments:
                            anticipatory_adjustments[strategy] += adjustment
                        else:
                            anticipatory_adjustments[strategy] = adjustment
            
            # Normalize adjustments
            for strategy in anticipatory_adjustments:
                anticipatory_adjustments[strategy] = max(-0.1, min(0.1, anticipatory_adjustments[strategy]))
            
            return anticipatory_adjustments
            
        except Exception as e:
            print(f"⚠️ Error calculating anticipatory adjustments: {e}")
            return {}
    
    def interpret_signal_for_strategies(self, signal: Dict) -> Dict[str, float]:
        """Interpret anticipatory signal implications for different strategies"""
        
        try:
            implications = {}
            
            signal_type = signal.get('signal_type', '')
            direction = signal.get('direction', 'positive')
            relationship = signal.get('relationship', '')
            
            # Parse relationship
            if '→' in relationship:
                source, target = relationship.split('→')
                source = source.strip()
                target = target.strip()
            else:
                return implications
            
            # Determine strategy implications based on signal characteristics
            if 'macro' in signal_type:
                if direction == 'positive':
                    implications['growth_strategies'] = 0.1
                    implications['momentum_strategies'] = 0.05
                    implications['defensive_strategies'] = -0.05
                else:
                    implications['growth_strategies'] = -0.1
                    implications['momentum_strategies'] = -0.05
                    implications['defensive_strategies'] = 0.1
            
            elif 'fx' in signal_type:
                if direction == 'positive':
                    implications['sector_rotation'] = 0.08  # FX changes drive sector rotation
                    implications['momentum_strategies'] = 0.05
                else:
                    implications['defensive_strategies'] = 0.05
            
            elif 'flows' in signal_type:
                if direction == 'positive':
                    implications['momentum_strategies'] = 0.1
                    implications['growth_strategies'] = 0.05
                else:
                    implications['value_strategies'] = 0.08  # Contrarian opportunity
                    implications['defensive_strategies'] = 0.05
            
            elif 'structural_shift' in signal_type:
                # Structural shifts favor adaptive strategies
                implications['sector_rotation'] = 0.1
                implications['momentum_strategies'] = 0.05
                implications['defensive_strategies'] = 0.03  # Some defensive positioning
            
            return implications
            
        except Exception as e:
            print(f"⚠️ Error interpreting signal: {e}")
            return {}
    
    def calculate_risk_adjustments(self, pressure: Dict, signals: Dict) -> Dict[str, float]:
        """Calculate risk adjustments based on regime transition probability and pressure"""
        
        try:
            risk_adjustments = {
                'cash_buffer_adjustment': 0.0,
                'volatility_adjustment': 0.0,
                'concentration_adjustment': 0.0
            }
            
            # Check regime transition probability
            transition_prob = signals.get('regime_transition_probability', 0.0)
            
            if transition_prob >= self.config['risk_adjustment_threshold']:
                # Increase cash buffer for regime transitions
                cash_adjustment = min(self.config['regime_transition_hedge'], transition_prob * 0.15)
                risk_adjustments['cash_buffer_adjustment'] = cash_adjustment
                
                # Reduce concentration during uncertain periods
                risk_adjustments['concentration_adjustment'] = -0.05
            
            # Check pressure volatility
            pressure_vectors = pressure.get('pressure_vectors', {})
            if pressure_vectors:
                # Calculate pressure volatility (simplified)
                pressure_values = [pv['pressure'] for pv in pressure_vectors.values()]
                pressure_std = np.std(pressure_values) if len(pressure_values) > 1 else 0
                
                if pressure_std > 0.3:  # High pressure volatility
                    risk_adjustments['volatility_adjustment'] = 0.05  # Increase volatility buffer
            
            return risk_adjustments
            
        except Exception as e:
            print(f"⚠️ Error calculating risk adjustments: {e}")
            return {'cash_buffer_adjustment': 0.0, 'volatility_adjustment': 0.0, 'concentration_adjustment': 0.0}
    
    def apply_fabric_adjustments(self, base_weights: Dict[str, float], 
                                fitness_multipliers: Dict[str, float],
                                anticipatory_adjustments: Dict[str, float],
                                risk_adjustments: Dict[str, float]) -> Dict[str, float]:
        """Apply all fabric-based adjustments to base weights"""
        
        try:
            enhanced_weights = base_weights.copy()
            
            # Apply fitness multipliers
            for strategy, base_weight in base_weights.items():
                if strategy in fitness_multipliers:
                    enhanced_weights[strategy] = base_weight * fitness_multipliers[strategy]
            
            # Apply anticipatory adjustments
            for strategy, adjustment in anticipatory_adjustments.items():
                if strategy in enhanced_weights:
                    enhanced_weights[strategy] += adjustment
                else:
                    enhanced_weights[strategy] = adjustment
            
            # Apply risk adjustments (cash buffer)
            cash_adjustment = risk_adjustments.get('cash_buffer_adjustment', 0.0)
            if cash_adjustment > 0:
                # Reduce all strategy weights proportionally to create cash buffer
                total_weight = sum(enhanced_weights.values())
                if total_weight > 0:
                    reduction_factor = (1.0 - cash_adjustment)
                    for strategy in enhanced_weights:
                        enhanced_weights[strategy] *= reduction_factor
                    
                    # Add cash position
                    enhanced_weights['cash_buffer'] = cash_adjustment
            
            # Ensure weights are non-negative and sum to 1.0
            enhanced_weights = self.normalize_weights(enhanced_weights)
            
            # Apply maximum shift constraint
            enhanced_weights = self.apply_shift_constraints(base_weights, enhanced_weights)
            
            return enhanced_weights
            
        except Exception as e:
            print(f"⚠️ Error applying fabric adjustments: {e}")
            return base_weights
    
    def normalize_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Normalize weights to sum to 1.0 and ensure non-negative"""
        
        try:
            # Ensure non-negative
            normalized_weights = {k: max(0.0, v) for k, v in weights.items()}
            
            # Normalize to sum to 1.0
            total_weight = sum(normalized_weights.values())
            
            if total_weight > 0:
                normalized_weights = {k: v / total_weight for k, v in normalized_weights.items()}
            else:
                # If all weights are zero, distribute equally
                n_strategies = len(normalized_weights)
                normalized_weights = {k: 1.0 / n_strategies for k in normalized_weights.keys()}
            
            return normalized_weights
            
        except Exception as e:
            print(f"⚠️ Error normalizing weights: {e}")
            return weights
    
    def apply_shift_constraints(self, base_weights: Dict[str, float], 
                               enhanced_weights: Dict[str, float]) -> Dict[str, float]:
        """Apply maximum shift constraints to prevent excessive changes"""
        
        try:
            constrained_weights = {}
            max_shift = self.config['max_allocation_shift']
            
            for strategy, enhanced_weight in enhanced_weights.items():
                base_weight = base_weights.get(strategy, 0.0)
                
                # Calculate shift
                shift = enhanced_weight - base_weight
                
                # Apply constraint
                if abs(shift) > max_shift:
                    constrained_shift = max_shift if shift > 0 else -max_shift
                    constrained_weights[strategy] = base_weight + constrained_shift
                else:
                    constrained_weights[strategy] = enhanced_weight
            
            # Re-normalize after constraints
            constrained_weights = self.normalize_weights(constrained_weights)
            
            return constrained_weights
            
        except Exception as e:
            print(f"⚠️ Error applying shift constraints: {e}")
            return enhanced_weights
    
    def get_sector_allocation_insights(self) -> Dict:
        """Get sector-specific allocation insights from fabric"""
        
        try:
            # Get fabric insights
            trends = self.fabric_reader.get_relationship_trends()
            pressure = self.fabric_reader.get_current_market_pressure()
            
            sector_insights = {}
            
            # Analyze sector rotation signals
            rotation_signals = []
            
            for rel in trends.get('rising_relationships', []):
                if 'sector' in rel.get('dst_type', '').lower():
                    sector_name = rel['dst_name']
                    driver = rel['src_name']
                    strength = rel.get('confidence_change', 0)
                    
                    rotation_signals.append({
                        'sector': sector_name,
                        'signal': 'strengthening',
                        'driver': driver,
                        'strength': strength,
                        'recommendation': 'overweight' if strength > 0.2 else 'neutral'
                    })
            
            for rel in trends.get('weakening_relationships', []):
                if 'sector' in rel.get('dst_type', '').lower():
                    sector_name = rel['dst_name']
                    driver = rel['src_name']
                    strength = abs(rel.get('confidence_change', 0))
                    
                    rotation_signals.append({
                        'sector': sector_name,
                        'signal': 'weakening',
                        'driver': driver,
                        'strength': strength,
                        'recommendation': 'underweight' if strength > 0.2 else 'neutral'
                    })
            
            # Calculate sector pressure scores
            pressure_vectors = pressure.get('pressure_vectors', {})
            sector_pressure_scores = {}
            
            for sector, sensitivities in self.sector_sensitivity.items():
                sector_score = 0.0
                total_weight = 0.0
                
                for factor, sensitivity in sensitivities.items():
                    if factor in pressure_vectors:
                        pressure_data = pressure_vectors[factor]
                        pressure_value = pressure_data['pressure']
                        confidence = pressure_data['confidence']
                        
                        contribution = sensitivity * pressure_value * confidence
                        sector_score += contribution
                        total_weight += confidence
                
                if total_weight > 0:
                    sector_pressure_scores[sector] = sector_score / total_weight
                else:
                    sector_pressure_scores[sector] = 0.0
            
            sector_insights = {
                'rotation_signals': rotation_signals,
                'pressure_scores': sector_pressure_scores,
                'recommendations': self.generate_sector_recommendations(
                    rotation_signals, sector_pressure_scores
                )
            }
            
            return sector_insights
            
        except Exception as e:
            print(f"⚠️ Error getting sector allocation insights: {e}")
            return {}
    
    def generate_sector_recommendations(self, rotation_signals: List[Dict], 
                                      pressure_scores: Dict[str, float]) -> List[Dict]:
        """Generate sector allocation recommendations"""
        
        try:
            recommendations = []
            
            # Combine rotation signals and pressure scores
            all_sectors = set()
            all_sectors.update(signal['sector'] for signal in rotation_signals)
            all_sectors.update(pressure_scores.keys())
            
            for sector in all_sectors:
                # Get rotation signal
                sector_rotation_signals = [s for s in rotation_signals if s['sector'] == sector]
                rotation_strength = 0.0
                rotation_direction = 'neutral'
                
                if sector_rotation_signals:
                    # Take the strongest signal
                    strongest_signal = max(sector_rotation_signals, key=lambda x: x['strength'])
                    rotation_strength = strongest_signal['strength']
                    rotation_direction = strongest_signal['signal']
                
                # Get pressure score
                pressure_score = pressure_scores.get(sector, 0.0)
                
                # Combine signals
                combined_score = pressure_score
                if rotation_direction == 'strengthening':
                    combined_score += rotation_strength * 0.5
                elif rotation_direction == 'weakening':
                    combined_score -= rotation_strength * 0.5
                
                # Generate recommendation
                if combined_score > 0.15:
                    recommendation = 'overweight'
                elif combined_score < -0.15:
                    recommendation = 'underweight'
                else:
                    recommendation = 'neutral'
                
                recommendations.append({
                    'sector': sector,
                    'recommendation': recommendation,
                    'combined_score': combined_score,
                    'pressure_score': pressure_score,
                    'rotation_strength': rotation_strength,
                    'rotation_direction': rotation_direction,
                    'confidence': min(1.0, abs(combined_score) * 2)  # Simple confidence measure
                })
            
            # Sort by combined score
            recommendations = sorted(recommendations, key=lambda x: x['combined_score'], reverse=True)
            
            return recommendations
            
        except Exception as e:
            print(f"⚠️ Error generating sector recommendations: {e}")
            return []
    
    def log_allocation_enhancements(self, base_weights: Dict[str, float], 
                                   enhanced_weights: Dict[str, float],
                                   fitness_multipliers: Dict[str, float],
                                   anticipatory_adjustments: Dict[str, float],
                                   risk_adjustments: Dict[str, float]):
        """Log allocation enhancements for transparency"""
        
        try:
            print("   🧬 Fabric Enhancement Summary:")
            
            # Show weight changes
            for strategy in base_weights:
                base_weight = base_weights[strategy]
                enhanced_weight = enhanced_weights.get(strategy, 0.0)
                change = enhanced_weight - base_weight
                
                if abs(change) > 0.01:  # Only show significant changes
                    change_pct = (change / base_weight * 100) if base_weight > 0 else 0
                    print(f"      {strategy}: {base_weight:.3f} → {enhanced_weight:.3f} ({change_pct:+.1f}%)")
            
            # Show fitness multipliers
            significant_multipliers = {k: v for k, v in fitness_multipliers.items() if abs(v - 1.0) > 0.05}
            if significant_multipliers:
                print(f"      Fitness multipliers: {significant_multipliers}")
            
            # Show anticipatory adjustments
            if anticipatory_adjustments:
                print(f"      Anticipatory adjustments: {anticipatory_adjustments}")
            
            # Show risk adjustments
            significant_risk_adj = {k: v for k, v in risk_adjustments.items() if abs(v) > 0.01}
            if significant_risk_adj:
                print(f"      Risk adjustments: {significant_risk_adj}")
            
        except Exception as e:
            print(f"⚠️ Error logging enhancements: {e}")

def main():
    """Test the fabric capital integration"""
    
    integration = FabricCapitalIntegration()
    
    # Test with sample base weights
    base_weights = {
        'momentum_strategies': 0.3,
        'value_strategies': 0.2,
        'sector_rotation': 0.25,
        'defensive_strategies': 0.15,
        'growth_strategies': 0.1
    }
    
    print("🧬 Testing Fabric Capital Integration...")
    print(f"   Base weights: {base_weights}")
    
    # Get enhanced weights
    enhanced_weights = integration.get_enhanced_allocation_weights(base_weights)
    print(f"   Enhanced weights: {enhanced_weights}")
    
    # Get sector insights
    sector_insights = integration.get_sector_allocation_insights()
    print(f"   Sector recommendations: {len(sector_insights.get('recommendations', []))}")
    
    print("✅ Fabric Capital Integration test completed")
    return True

if __name__ == "__main__":
    main()