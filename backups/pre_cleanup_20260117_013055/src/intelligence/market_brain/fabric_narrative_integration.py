#!/usr/bin/env python3
"""
🧬 FABRIC NARRATIVE INTEGRATION - NORTHSTAR V3 MARKET BRAIN
The Causal Storyteller: Integrating Weekly Causal Fabric with Narrative Generation

This integrates Weekly Causal Fabric insights into narrative generation:
- Causal explanations for market movements
- Anticipatory narratives from emerging relationships
- Regime transition stories from structural shifts
- Relationship evolution narratives

Integration with V3:
- Enhances existing Narrative Engine with causal context
- Provides "why" explanations for market behavior
- Adds anticipatory elements to market stories
- Creates relationship-based market narratives
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

class FabricNarrativeIntegration:
    """
    Fabric Narrative Integration - Causal Storytelling Engine
    
    Transforms causal relationship data into compelling market narratives:
    - Explains current market behavior through causal relationships
    - Generates anticipatory narratives from emerging patterns
    - Creates regime transition stories
    - Provides relationship evolution context
    """
    
    def __init__(self):
        self.name = "Fabric Narrative Integration"
        self.version = "1.0"
        
        # Initialize fabric reader
        self.fabric_reader = WeeklyFabricReader()
        
        # Narrative configuration
        self.config = {
            'max_relationships_per_narrative': 5,
            'min_confidence_for_narrative': 0.6,
            'min_novelty_for_anticipatory': 0.7,
            'narrative_time_horizon': 8,  # weeks
            'relationship_significance_threshold': 0.15
        }
        
        # Narrative templates
        self.narrative_templates = {
            'causal_explanation': {
                'macro_to_sector': [
                    "{macro_factor} has been {direction} {sector} sector performance over the past {timeframe}",
                    "The {sector} sector is experiencing {direction} pressure from {macro_factor} dynamics",
                    "{macro_factor} changes are {direction} influencing {sector} sector returns"
                ],
                'fx_to_sector': [
                    "Currency movements in {fx_factor} are {direction} {sector} sector competitiveness",
                    "The {sector} sector is {direction} benefiting from {fx_factor} trends",
                    "{fx_factor} dynamics are creating {direction} momentum in {sector}"
                ],
                'flows_to_sector': [
                    "Capital flows are {direction} driving {sector} sector performance",
                    "{flow_factor} is creating {direction} pressure in the {sector} sector",
                    "The {sector} sector is experiencing {direction} flow dynamics from {flow_factor}"
                ]
            },
            'anticipatory_narrative': {
                'emerging_relationship': [
                    "A new relationship is emerging between {source} and {target}, suggesting {implication}",
                    "Market structure is evolving as {source} begins to influence {target} performance",
                    "Early signals indicate {source} may become a key driver of {target} in the coming {horizon}"
                ],
                'strengthening_relationship': [
                    "The relationship between {source} and {target} is strengthening, indicating {implication}",
                    "{source} influence on {target} is intensifying, suggesting {implication}",
                    "Market sensitivity to {source} via {target} is increasing"
                ],
                'regime_transition': [
                    "Multiple structural relationships are shifting, suggesting a potential regime transition",
                    "The market's causal fabric is evolving, indicating possible regime change ahead",
                    "Emerging relationship patterns suggest the market may be entering a new regime"
                ]
            },
            'relationship_evolution': {
                'rising_influence': [
                    "{source} influence on {target} has been steadily increasing",
                    "The {source}-{target} relationship is gaining strength",
                    "{target} is becoming more sensitive to {source} dynamics"
                ],
                'declining_influence': [
                    "{source} influence on {target} has been weakening",
                    "The {source}-{target} relationship is losing strength",
                    "{target} is becoming less sensitive to {source} changes"
                ],
                'volatile_relationship': [
                    "The {source}-{target} relationship has been unstable",
                    "{target} sensitivity to {source} has been fluctuating",
                    "The {source}-{target} dynamic is showing inconsistent patterns"
                ]
            }
        }
        
        # Relationship interpretation mappings
        self.relationship_interpretations = {
            'positive_macro_sector': "supportive macro conditions",
            'negative_macro_sector': "challenging macro headwinds",
            'positive_fx_sector': "favorable currency dynamics",
            'negative_fx_sector': "adverse currency pressures",
            'positive_flows_sector': "strong capital inflows",
            'negative_flows_sector': "capital outflow pressures",
            'emerging_structural': "structural market evolution",
            'regime_transition': "potential regime change"
        }
    
    def generate_market_narrative(self) -> Dict[str, str]:
        """Generate comprehensive market narrative incorporating causal insights"""
        
        try:
            print("📖 Generating causal market narrative...")
            
            # Get fabric insights
            pressure = self.fabric_reader.get_current_market_pressure()
            trends = self.fabric_reader.get_relationship_trends()
            signals = self.fabric_reader.get_anticipatory_signals()
            emerging = self.fabric_reader.get_emerging_relationships()
            
            # Generate narrative components
            narrative_components = {
                'current_dynamics': self.generate_current_dynamics_narrative(pressure, trends),
                'causal_explanations': self.generate_causal_explanations(trends),
                'anticipatory_insights': self.generate_anticipatory_narrative(signals, emerging),
                'relationship_evolution': self.generate_relationship_evolution_narrative(trends),
                'regime_assessment': self.generate_regime_assessment_narrative(signals, pressure),
                'market_outlook': self.generate_market_outlook_narrative(signals, trends)
            }
            
            # Combine into comprehensive narrative
            comprehensive_narrative = self.combine_narrative_components(narrative_components)
            
            return {
                'comprehensive_narrative': comprehensive_narrative,
                'narrative_components': narrative_components,
                'generation_timestamp': datetime.now().isoformat(),
                'confidence_level': self.assess_narrative_confidence(pressure, trends, signals)
            }
            
        except Exception as e:
            print(f"❌ Error generating market narrative: {e}")
            return {'comprehensive_narrative': "Market narrative generation unavailable", 'narrative_components': {}}
    
    def generate_current_dynamics_narrative(self, pressure: Dict, trends: Dict) -> str:
        """Generate narrative about current market dynamics"""
        
        try:
            narrative_parts = []
            
            # Analyze dominant forces
            dominant_forces = pressure.get('dominant_forces', [])
            regime_pressure = pressure.get('regime_pressure', 'neutral')
            
            if dominant_forces:
                top_force = dominant_forces[0]
                force_type = top_force['type']
                force_direction = top_force['direction']
                force_strength = top_force['strength']
                
                if force_strength > 0.3:
                    strength_desc = "strong"
                elif force_strength > 0.15:
                    strength_desc = "moderate"
                else:
                    strength_desc = "weak"
                
                direction_desc = "supportive" if force_direction == 'positive' else "challenging"
                
                narrative_parts.append(
                    f"Market dynamics are currently dominated by {strength_desc} {direction_desc} "
                    f"{force_type} forces"
                )
            
            # Regime pressure context
            if regime_pressure == 'expansionary':
                narrative_parts.append("Overall market pressure remains expansionary")
            elif regime_pressure == 'contractionary':
                narrative_parts.append("Market pressure has turned contractionary")
            else:
                narrative_parts.append("Market pressure is currently neutral")
            
            # Trend context
            rising_count = len(trends.get('rising_relationships', []))
            weakening_count = len(trends.get('weakening_relationships', []))
            new_count = len(trends.get('new_relationships', []))
            
            if rising_count > weakening_count:
                narrative_parts.append(f"Market relationships are strengthening ({rising_count} rising vs {weakening_count} weakening)")
            elif weakening_count > rising_count:
                narrative_parts.append(f"Market relationships are weakening ({weakening_count} weakening vs {rising_count} rising)")
            else:
                narrative_parts.append("Market relationship strength is balanced")
            
            if new_count > 0:
                narrative_parts.append(f"{new_count} new relationships have emerged, indicating structural evolution")
            
            return ". ".join(narrative_parts) + "."
            
        except Exception as e:
            print(f"⚠️ Error generating current dynamics narrative: {e}")
            return "Current market dynamics analysis unavailable."
    
    def generate_causal_explanations(self, trends: Dict) -> List[str]:
        """Generate causal explanations for recent market behavior"""
        
        try:
            explanations = []
            
            # Process rising relationships
            for rel in trends.get('rising_relationships', [])[:3]:  # Top 3
                explanation = self.create_relationship_explanation(rel, 'strengthening')
                if explanation:
                    explanations.append(explanation)
            
            # Process weakening relationships
            for rel in trends.get('weakening_relationships', [])[:2]:  # Top 2
                explanation = self.create_relationship_explanation(rel, 'weakening')
                if explanation:
                    explanations.append(explanation)
            
            # Process new relationships
            for rel in trends.get('new_relationships', [])[:2]:  # Top 2
                explanation = self.create_new_relationship_explanation(rel)
                if explanation:
                    explanations.append(explanation)
            
            return explanations
            
        except Exception as e:
            print(f"⚠️ Error generating causal explanations: {e}")
            return []
    
    def create_relationship_explanation(self, relationship: Dict, change_type: str) -> str:
        """Create explanation for a specific relationship change"""
        
        try:
            src_name = relationship.get('src_name', 'unknown')
            dst_name = relationship.get('dst_name', 'unknown')
            confidence_change = relationship.get('confidence_change', 0)
            
            # Determine relationship type
            src_type = self.categorize_variable_for_narrative(src_name)
            dst_type = self.categorize_variable_for_narrative(dst_name)
            
            # Select appropriate template
            template_key = f"{src_type}_to_{dst_type}"
            
            if template_key in self.narrative_templates['causal_explanation']:
                templates = self.narrative_templates['causal_explanation'][template_key]
                template = np.random.choice(templates)
                
                # Determine direction description
                if change_type == 'strengthening':
                    direction = "increasingly" if confidence_change > 0.2 else "moderately"
                else:
                    direction = "decreasingly" if abs(confidence_change) > 0.2 else "somewhat less"
                
                # Format template
                explanation = template.format(
                    macro_factor=src_name,
                    fx_factor=src_name,
                    flow_factor=src_name,
                    sector=dst_name,
                    direction=direction,
                    timeframe="recent weeks"
                )
                
                return explanation
            
            # Generic explanation
            change_desc = "strengthening" if change_type == 'strengthening' else "weakening"
            return f"The relationship between {src_name} and {dst_name} is {change_desc}"
            
        except Exception as e:
            print(f"⚠️ Error creating relationship explanation: {e}")
            return ""
    
    def create_new_relationship_explanation(self, relationship: Dict) -> str:
        """Create explanation for a newly discovered relationship"""
        
        try:
            src_name = relationship.get('src_name', 'unknown')
            dst_name = relationship.get('dst_name', 'unknown')
            novelty = relationship.get('novelty', 0)
            confidence = relationship.get('confidence', 0)
            
            if novelty > 0.8 and confidence > 0.6:
                significance = "significant"
            elif novelty > 0.6:
                significance = "notable"
            else:
                significance = "emerging"
            
            return f"A {significance} new relationship has developed between {src_name} and {dst_name}, " \
                   f"suggesting evolving market structure"
            
        except Exception as e:
            print(f"⚠️ Error creating new relationship explanation: {e}")
            return ""
    
    def generate_anticipatory_narrative(self, signals: Dict, emerging: List[Dict]) -> str:
        """Generate anticipatory narrative from signals and emerging relationships"""
        
        try:
            narrative_parts = []
            
            # Regime transition probability
            transition_prob = signals.get('regime_transition_probability', 0)
            
            if transition_prob > 0.7:
                narrative_parts.append("Multiple indicators suggest a high probability of regime transition in the coming weeks")
            elif transition_prob > 0.4:
                narrative_parts.append("Some indicators point to potential regime evolution ahead")
            
            # High-confidence anticipatory signals
            signal_list = signals.get('signals', [])
            high_confidence_signals = [s for s in signal_list if s['confidence'] > 0.7]
            
            if high_confidence_signals:
                top_signal = high_confidence_signals[0]
                horizon = top_signal['horizon_weeks']
                relationship = top_signal['relationship']
                
                if horizon <= 4:
                    timeframe = "near-term"
                elif horizon <= 12:
                    timeframe = "medium-term"
                else:
                    timeframe = "longer-term"
                
                narrative_parts.append(
                    f"The {relationship} relationship is signaling {timeframe} structural changes"
                )
            
            # Emerging relationships with high novelty
            high_novelty_emerging = [e for e in emerging if e.get('novelty', 0) > 0.7]
            
            if high_novelty_emerging:
                count = len(high_novelty_emerging)
                if count == 1:
                    narrative_parts.append("One significant new relationship pattern has emerged")
                else:
                    narrative_parts.append(f"{count} significant new relationship patterns have emerged")
            
            # Key relationships to watch
            key_relationships = signals.get('key_relationships_to_watch', [])
            if key_relationships:
                top_relationship = key_relationships[0]
                narrative_parts.append(
                    f"The {top_relationship['relationship']} dynamic warrants close monitoring"
                )
            
            if narrative_parts:
                return ". ".join(narrative_parts) + "."
            else:
                return "Market structure appears stable with no significant anticipatory signals."
                
        except Exception as e:
            print(f"⚠️ Error generating anticipatory narrative: {e}")
            return "Anticipatory analysis unavailable."
    
    def generate_relationship_evolution_narrative(self, trends: Dict) -> str:
        """Generate narrative about how relationships have evolved"""
        
        try:
            narrative_parts = []
            
            # Analyze relationship evolution patterns
            rising_relationships = trends.get('rising_relationships', [])
            weakening_relationships = trends.get('weakening_relationships', [])
            
            # Identify patterns
            if len(rising_relationships) > len(weakening_relationships) * 1.5:
                narrative_parts.append("Market relationships are generally strengthening, indicating increasing interconnectedness")
            elif len(weakening_relationships) > len(rising_relationships) * 1.5:
                narrative_parts.append("Market relationships are generally weakening, suggesting structural fragmentation")
            else:
                narrative_parts.append("Market relationship evolution is balanced between strengthening and weakening dynamics")
            
            # Highlight most significant changes
            all_changes = rising_relationships + weakening_relationships
            if all_changes:
                # Sort by magnitude of change
                significant_changes = sorted(
                    all_changes, 
                    key=lambda x: abs(x.get('confidence_change', 0)), 
                    reverse=True
                )[:2]
                
                for change in significant_changes:
                    src_name = change.get('src_name', 'unknown')
                    dst_name = change.get('dst_name', 'unknown')
                    confidence_change = change.get('confidence_change', 0)
                    
                    if confidence_change > 0:
                        narrative_parts.append(f"The {src_name}-{dst_name} relationship has notably strengthened")
                    else:
                        narrative_parts.append(f"The {src_name}-{dst_name} relationship has notably weakened")
            
            return ". ".join(narrative_parts) + "." if narrative_parts else "Relationship evolution patterns are stable."
            
        except Exception as e:
            print(f"⚠️ Error generating relationship evolution narrative: {e}")
            return "Relationship evolution analysis unavailable."
    
    def generate_regime_assessment_narrative(self, signals: Dict, pressure: Dict) -> str:
        """Generate narrative about current regime and potential transitions"""
        
        try:
            narrative_parts = []
            
            # Current regime pressure
            regime_pressure = pressure.get('regime_pressure', 'neutral')
            total_pressure = pressure.get('total_pressure', 0)
            
            if regime_pressure == 'expansionary':
                if total_pressure > 0.4:
                    narrative_parts.append("The market is in a strong expansionary regime")
                else:
                    narrative_parts.append("The market shows moderate expansionary characteristics")
            elif regime_pressure == 'contractionary':
                if total_pressure < -0.4:
                    narrative_parts.append("The market is in a strong contractionary regime")
                else:
                    narrative_parts.append("The market shows moderate contractionary characteristics")
            else:
                narrative_parts.append("The market is in a neutral regime with balanced forces")
            
            # Transition probability assessment
            transition_prob = signals.get('regime_transition_probability', 0)
            
            if transition_prob > 0.6:
                narrative_parts.append("High probability of regime transition based on structural relationship changes")
            elif transition_prob > 0.3:
                narrative_parts.append("Moderate probability of regime evolution in the coming period")
            else:
                narrative_parts.append("Current regime appears stable with low transition probability")
            
            # Dominant forces context
            dominant_forces = pressure.get('dominant_forces', [])
            if dominant_forces:
                top_force = dominant_forces[0]
                force_type = top_force['type']
                narrative_parts.append(f"Regime dynamics are primarily driven by {force_type} forces")
            
            return ". ".join(narrative_parts) + "."
            
        except Exception as e:
            print(f"⚠️ Error generating regime assessment narrative: {e}")
            return "Regime assessment unavailable."
    
    def generate_market_outlook_narrative(self, signals: Dict, trends: Dict) -> str:
        """Generate forward-looking market outlook narrative"""
        
        try:
            narrative_parts = []
            
            # Anticipatory signals outlook
            signal_list = signals.get('signals', [])
            
            if signal_list:
                # Analyze signal horizons
                near_term_signals = [s for s in signal_list if s['horizon_weeks'] <= 4]
                medium_term_signals = [s for s in signal_list if 4 < s['horizon_weeks'] <= 12]
                
                if near_term_signals:
                    positive_signals = [s for s in near_term_signals if s['direction'] == 'positive']
                    negative_signals = [s for s in near_term_signals if s['direction'] == 'negative']
                    
                    if len(positive_signals) > len(negative_signals):
                        narrative_parts.append("Near-term outlook appears constructive based on emerging relationship patterns")
                    elif len(negative_signals) > len(positive_signals):
                        narrative_parts.append("Near-term outlook shows some caution based on relationship dynamics")
                    else:
                        narrative_parts.append("Near-term outlook is mixed with balanced relationship signals")
                
                if medium_term_signals:
                    narrative_parts.append(f"Medium-term structural changes are indicated by {len(medium_term_signals)} relationship signals")
            
            # Trend momentum
            rising_count = len(trends.get('rising_relationships', []))
            new_count = len(trends.get('new_relationships', []))
            
            if rising_count > 3 or new_count > 2:
                narrative_parts.append("Relationship momentum suggests continued market evolution")
            
            # Key factors to watch
            key_relationships = signals.get('key_relationships_to_watch', [])
            if key_relationships:
                narrative_parts.append(
                    f"Key relationships to monitor include {key_relationships[0]['relationship']} "
                    f"for {key_relationships[0]['horizon_weeks']}-week outlook"
                )
            
            if not narrative_parts:
                narrative_parts.append("Market outlook remains stable with no significant structural signals")
            
            return ". ".join(narrative_parts) + "."
            
        except Exception as e:
            print(f"⚠️ Error generating market outlook narrative: {e}")
            return "Market outlook analysis unavailable."
    
    def categorize_variable_for_narrative(self, variable_name: str) -> str:
        """Categorize variable for narrative template selection"""
        
        try:
            var_lower = variable_name.lower()
            
            if any(term in var_lower for term in ['repo', 'rate', 'cpi', 'wpi', 'inflation', 'growth']):
                return 'macro'
            elif any(term in var_lower for term in ['usdinr', 'fx', 'currency', 'exchange']):
                return 'fx'
            elif any(term in var_lower for term in ['fii', 'dii', 'flow', 'capital']):
                return 'flows'
            elif any(term in var_lower for term in ['sector', 'industry']):
                return 'sector'
            else:
                return 'other'
                
        except:
            return 'other'
    
    def combine_narrative_components(self, components: Dict[str, str]) -> str:
        """Combine narrative components into comprehensive story"""
        
        try:
            narrative_sections = []
            
            # Current dynamics
            if components.get('current_dynamics'):
                narrative_sections.append(f"**Current Market Dynamics**\n{components['current_dynamics']}")
            
            # Causal explanations
            causal_explanations = components.get('causal_explanations', [])
            if causal_explanations:
                explanations_text = "\n".join([f"• {exp}" for exp in causal_explanations[:3]])
                narrative_sections.append(f"**Causal Factors**\n{explanations_text}")
            
            # Anticipatory insights
            if components.get('anticipatory_insights'):
                narrative_sections.append(f"**Forward-Looking Insights**\n{components['anticipatory_insights']}")
            
            # Relationship evolution
            if components.get('relationship_evolution'):
                narrative_sections.append(f"**Market Structure Evolution**\n{components['relationship_evolution']}")
            
            # Regime assessment
            if components.get('regime_assessment'):
                narrative_sections.append(f"**Regime Assessment**\n{components['regime_assessment']}")
            
            # Market outlook
            if components.get('market_outlook'):
                narrative_sections.append(f"**Market Outlook**\n{components['market_outlook']}")
            
            return "\n\n".join(narrative_sections)
            
        except Exception as e:
            print(f"⚠️ Error combining narrative components: {e}")
            return "Comprehensive market narrative unavailable."
    
    def assess_narrative_confidence(self, pressure: Dict, trends: Dict, signals: Dict) -> float:
        """Assess confidence level in the generated narrative"""
        
        try:
            confidence_factors = []
            
            # Pressure confidence
            pressure_vectors = pressure.get('pressure_vectors', {})
            if pressure_vectors:
                pressure_confidences = [pv['confidence'] for pv in pressure_vectors.values()]
                avg_pressure_confidence = np.mean(pressure_confidences)
                confidence_factors.append(avg_pressure_confidence)
            
            # Trend confidence
            all_relationships = (
                trends.get('rising_relationships', []) +
                trends.get('weakening_relationships', []) +
                trends.get('new_relationships', [])
            )
            
            if all_relationships:
                trend_confidences = [
                    rel.get('confidence', rel.get('recent_confidence', 0.5))
                    for rel in all_relationships
                ]
                avg_trend_confidence = np.mean(trend_confidences)
                confidence_factors.append(avg_trend_confidence)
            
            # Signal confidence
            signal_list = signals.get('signals', [])
            if signal_list:
                signal_confidences = [s['confidence'] for s in signal_list]
                avg_signal_confidence = np.mean(signal_confidences)
                confidence_factors.append(avg_signal_confidence)
            
            if confidence_factors:
                overall_confidence = np.mean(confidence_factors)
                return float(overall_confidence)
            else:
                return 0.5  # Default moderate confidence
                
        except Exception as e:
            print(f"⚠️ Error assessing narrative confidence: {e}")
            return 0.5
    
    def get_relationship_story(self, src_name: str, dst_name: str, weeks_back: int = 12) -> Dict:
        """Get the story of a specific relationship over time"""
        
        try:
            # Get relationship evolution
            evolution = self.fabric_reader.store.get_relationship_evolution(
                src_name, dst_name, horizon=4, weeks_back=weeks_back
            )
            
            if evolution.empty:
                return {'story': f"No significant relationship found between {src_name} and {dst_name}", 'confidence': 0.0}
            
            # Analyze evolution pattern
            evolution_sorted = evolution.sort_values('date')
            
            # Calculate trend
            if len(evolution_sorted) >= 2:
                recent_confidence = evolution_sorted['confidence'].iloc[-1]
                older_confidence = evolution_sorted['confidence'].iloc[0]
                trend = recent_confidence - older_confidence
                
                # Generate story
                if trend > 0.2:
                    story = f"The relationship between {src_name} and {dst_name} has strengthened significantly over the past {weeks_back} weeks"
                elif trend > 0.05:
                    story = f"The relationship between {src_name} and {dst_name} has gradually strengthened"
                elif trend < -0.2:
                    story = f"The relationship between {src_name} and {dst_name} has weakened significantly"
                elif trend < -0.05:
                    story = f"The relationship between {src_name} and {dst_name} has gradually weakened"
                else:
                    story = f"The relationship between {src_name} and {dst_name} has remained relatively stable"
                
                # Add context
                avg_confidence = evolution_sorted['confidence'].mean()
                if avg_confidence > 0.7:
                    story += " with high confidence"
                elif avg_confidence > 0.5:
                    story += " with moderate confidence"
                else:
                    story += " with low confidence"
                
                return {
                    'story': story,
                    'confidence': float(avg_confidence),
                    'trend': float(trend),
                    'data_points': len(evolution_sorted)
                }
            else:
                return {
                    'story': f"Limited data available for {src_name}-{dst_name} relationship",
                    'confidence': 0.3,
                    'trend': 0.0,
                    'data_points': len(evolution_sorted)
                }
                
        except Exception as e:
            print(f"⚠️ Error getting relationship story: {e}")
            return {'story': "Relationship story unavailable", 'confidence': 0.0}

def main():
    """Test the fabric narrative integration"""
    
    integration = FabricNarrativeIntegration()
    
    print("📖 Testing Fabric Narrative Integration...")
    
    # Generate market narrative
    narrative_result = integration.generate_market_narrative()
    
    print("✅ Market Narrative Generated:")
    print(narrative_result['comprehensive_narrative'])
    print(f"\nConfidence Level: {narrative_result['confidence_level']:.2f}")
    
    # Test relationship story
    print("\n📊 Testing Relationship Story...")
    story = integration.get_relationship_story('repo_rate', 'banking_sector')
    print(f"Story: {story['story']}")
    print(f"Confidence: {story['confidence']:.2f}")
    
    print("\n✅ Fabric Narrative Integration test completed")
    return True

if __name__ == "__main__":
    main()