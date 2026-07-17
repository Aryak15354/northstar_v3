#!/usr/bin/env python3
"""
🧠 ANTICIPATORY INTELLIGENCE INTEGRATION - NORTHSTAR V3
Integration Layer: Connecting Anticipatory Intelligence with Existing V3 System

This provides a clean integration layer between the new anticipatory intelligence
system and the existing Northstar V3 components, ensuring seamless operation
and backward compatibility.

Key Integration Points:
- Enhanced Intelligence Stack with regime awareness
- Anticipatory Capital Allocator integration
- Regime-aware Portfolio Governor
- Forward-looking Risk Management

Usage:
    try:
    from src.intelligence.anticipatory_intelligence_integration import AnticipatoryIntelligenceIntegration
except ImportError:
    from AnticipatoryIntelligenceIntegration import AnticipatoryIntelligenceIntegration
    
    integration = AnticipatoryIntelligenceIntegration()
    intelligence_result = integration.get_enhanced_intelligence()
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Import safe JSON utilities
try:
    from src.utils.json_utils import safe_load_json, safe_save_json
    from src.utils.parquet_utils import safe_load_parquet
except ImportError:
    # Fallback safe loading functions
    def safe_load_json(file_path, default=None):
        if not os.path.exists(file_path):
            print(f"Warning: JSON file not found: {file_path}")
            return default if default is not None else {}
        try:
            with open(file_path, 'r') as f:
                content = f.read().strip()
            if not content:
                print(f"Warning: Empty JSON file: {file_path}")
                return default if default is not None else {}
            return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"Warning: Invalid JSON in {file_path}: {e}")
            return default if default is not None else {}
        except Exception as e:
            print(f"Warning: Error loading JSON {file_path}: {e}")
            return default if default is not None else {}
    
    def safe_load_parquet(file_path, default=None):
        if not os.path.exists(file_path):
            print(f"Warning: Parquet file not found: {file_path}")
            return default if default is not None else pd.DataFrame()
        try:
            if os.path.getsize(file_path) == 0:
                print(f"Warning: Empty parquet file: {file_path}")
                return default if default is not None else pd.DataFrame()
            df = pd.read_parquet(file_path)
            if df.empty:
                print(f"Warning: Parquet file contains no data: {file_path}")
                return default if default is not None else pd.DataFrame()
            return df
        except Exception as e:
            print(f"Warning: Could not load parquet {file_path}: {e}")
            return default if default is not None else pd.DataFrame()
    
    def safe_save_json(data, file_path):
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            return True
        except:
            return False
    def safe_save_json(data, file_path):
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            return True
        except:
            return False

class AnticipatoryIntelligenceIntegration:
    """
    Anticipatory Intelligence Integration Layer
    
    Provides seamless integration between anticipatory intelligence
    and existing Northstar V3 components.
    """
    
    def __init__(self):
        self.name = "Anticipatory Intelligence Integration"
        self.version = "1.0"
        
        # Integration paths
        self.paths = {
            'anticipatory_signals': 'data/processed/anticipatory_signals.json',
            'anticipatory_allocations': 'data/intelligence/anticipatory_allocations.json',
            'enhanced_brain_state': 'data/processed/enhanced_market_brain_state.json',
            'regime_intelligence_feed': 'data/processed/regime_intelligence_feed.json',
            'integration_status': 'data/processed/anticipatory_integration_status.json'
        }
    
    def is_anticipatory_intelligence_available(self):
        """Check if anticipatory intelligence is available and operational"""
        
        try:
            # Check for key anticipatory intelligence files
            required_files = [
                self.paths['anticipatory_signals'],
                self.paths['enhanced_brain_state']
            ]
            
            files_available = sum(1 for file_path in required_files if os.path.exists(file_path))
            
            if files_available >= len(required_files) * 0.75:
                # Check if brain state indicates operational status
                if os.path.exists(self.paths['enhanced_brain_state']):
                    brain_state = safe_load_json(self.paths['enhanced_brain_state'], {})
                    
                    system_readiness = brain_state.get('system_readiness', {})
                    return system_readiness.get('anticipatory_intelligence', False)
            
            return False
            
        except Exception as e:
            print(f"Error checking anticipatory intelligence availability: {e}")
            return False
    
    def get_current_regime_intelligence(self):
        """Get current regime intelligence"""
        
        try:
            if os.path.exists(self.paths['anticipatory_signals']):
                signals = safe_load_json(self.paths['anticipatory_signals'], {})
                
                current_regime = signals.get('current_regime', {})
                
                return {
                    'available': True,
                    'regime_name': current_regime.get('name', 'Unknown'),
                    'regime_stability': current_regime.get('stability', 0.5),
                    'regime_duration': current_regime.get('duration_in_regime', 0),
                    'confidence': signals.get('confidence_metrics', {}).get('regime_identification', 0.5)
                }
            
            return {'available': False}
            
        except Exception as e:
            print(f"Error getting regime intelligence: {e}")
            return {'available': False, 'error': str(e)}
    
    def get_regime_transition_predictions(self):
        """Get regime transition predictions"""
        
        try:
            if os.path.exists(self.paths['anticipatory_signals']):
                signals = safe_load_json(self.paths['anticipatory_signals'], {})
                
                transitions = signals.get('regime_transitions', {})
                next_regime_probs = transitions.get('next_regime_probabilities', {})
                
                if next_regime_probs:
                    # Get most likely transition
                    most_likely = max(next_regime_probs.items(), key=lambda x: x[1])
                    
                    return {
                        'available': True,
                        'predictions': next_regime_probs,
                        'most_likely_next': {
                            'regime': most_likely[0],
                            'probability': most_likely[1]
                        },
                        'confidence': signals.get('confidence_metrics', {}).get('transition_prediction', 0.5)
                    }
            
            return {'available': False}
            
        except Exception as e:
            print(f"Error getting transition predictions: {e}")
            return {'available': False, 'error': str(e)}
    
    def get_forward_expectations(self):
        """Get forward-looking market expectations"""
        
        try:
            if os.path.exists(self.paths['anticipatory_signals']):
                signals = safe_load_json(self.paths['anticipatory_signals'], {})
                
                forward_expectations = signals.get('forward_expectations', {})
                
                if forward_expectations:
                    return {
                        'available': True,
                        'expectations': forward_expectations,
                        'periods': list(forward_expectations.keys()),
                        'confidence': signals.get('confidence_metrics', {}).get('forward_expectations', 0.5)
                    }
            
            return {'available': False}
            
        except Exception as e:
            print(f"Error getting forward expectations: {e}")
            return {'available': False, 'error': str(e)}
    
    def get_anticipatory_capital_allocation(self):
        """Get anticipatory capital allocation"""
        
        try:
            if os.path.exists(self.paths['anticipatory_allocations']):
                # Try JSON first (our new format)
                if self.paths['anticipatory_allocations'].endswith('.json'):
                    allocations_data = safe_load_json(self.paths['anticipatory_allocations'], {})
                    if allocations_data:
                        return {
                            'available': True,
                            'allocations': allocations_data.get('allocations', {}),
                            'total_exposure': allocations_data.get('total_exposure', 0.9),
                            'confidence': allocations_data.get('confidence', 0.75),
                            'regime': allocations_data.get('regime', 'unknown'),
                            'timestamp': allocations_data.get('timestamp')
                        }
                
                # Fallback to parquet if it exists
                try:
                    allocations_df = safe_load_parquet(self.paths['anticipatory_allocations'])
                    
                    if not allocations_df.empty:
                        # Separate cash and strategy allocations
                        cash_allocation = allocations_df[allocations_df['strategy_name'] == 'CASH']
                        strategy_allocations = allocations_df[allocations_df['strategy_name'] != 'CASH']
                        
                        cash_weight = cash_allocation['allocation_weight'].iloc[0] if not cash_allocation.empty else 0.0
                        
                        # Convert strategy allocations to dictionary
                        strategy_weights = {}
                        for _, allocation in strategy_allocations.iterrows():
                            strategy_weights[allocation['strategy_name']] = {
                                'weight': allocation['allocation_weight'],
                                'category': allocation.get('strategy_category', 'unknown'),
                                'regime_fitness': allocation.get('regime_fitness', 1.0),
                                'allocation_reason': allocation.get('allocation_reason', '')
                            }
                    
                        return {
                            'available': True,
                            'cash_allocation': cash_weight,
                            'strategy_allocations': strategy_weights,
                            'total_strategies': len(strategy_allocations),
                            'regime_context': allocations_df['regime_name'].iloc[0] if 'regime_name' in allocations_df.columns else 'Unknown',
                            'timestamp': allocations_df['timestamp'].iloc[0].isoformat() if 'timestamp' in allocations_df.columns else None
                        }
                except Exception as parquet_error:
                    print(f"Warning: Could not load parquet allocations: {parquet_error}")
            
            return {'available': False}
            
        except Exception as e:
            print(f"Error getting anticipatory allocation: {e}")
            return {'available': False, 'error': str(e)}
    
    def get_strategy_recommendations(self):
        """Get regime-based strategy recommendations"""
        
        try:
            if os.path.exists(self.paths['anticipatory_signals']):
                signals = safe_load_json(self.paths['anticipatory_signals'], {})
                
                strategy_recommendations = signals.get('strategy_recommendations', {})
                anticipatory_actions = signals.get('anticipatory_actions', {})
                strategy_evolution_signals = anticipatory_actions.get('strategy_evolution_signals', {})
                
                return {
                    'available': True,
                    'current_regime_recommendations': strategy_recommendations.get('current_regime', {}),
                    'anticipatory_recommendations': strategy_recommendations.get('anticipatory', {}),
                    'birth_strategies': strategy_evolution_signals.get('birth_strategies', []),
                    'death_strategies': strategy_evolution_signals.get('death_strategies', []),
                    'modify_strategies': strategy_evolution_signals.get('modify_strategies', {})
                }
            
            return {'available': False}
            
        except Exception as e:
            print(f"Error getting strategy recommendations: {e}")
            return {'available': False, 'error': str(e)}
    
    def get_risk_assessment(self):
        """Get regime-aware risk assessment"""
        
        try:
            if os.path.exists(self.paths['anticipatory_signals']):
                signals = safe_load_json(self.paths['anticipatory_signals'], {})
                
                risk_assessment = signals.get('risk_assessment', {})
                anticipatory_actions = signals.get('anticipatory_actions', {})
                risk_management_actions = anticipatory_actions.get('risk_management_actions', {})
                
                return {
                    'available': True,
                    'regime_risk_level': risk_assessment.get('regime_risk_level', 'medium'),
                    'transition_risk': risk_assessment.get('transition_risk', 0.0),
                    'stability_risk': risk_assessment.get('stability_risk', 0.0),
                    'recommended_actions': risk_management_actions,
                    'execution_priority': signals.get('execution_priorities', {}).get('risk_management', 'normal')
                }
            
            return {'available': False}
            
        except Exception as e:
            print(f"Error getting risk assessment: {e}")
            return {'available': False, 'error': str(e)}
    
    def get_enhanced_intelligence(self):
        """Get complete enhanced intelligence summary with robust error handling"""
        try:
            return self._get_enhanced_intelligence_safe()
        except Exception as e:
            print(f"Warning: Enhanced intelligence unavailable: {e}")
            return {
                'available': False,
                'error': str(e),
                'fallback_mode': True,
                'regime_intelligence': {},
                'transition_predictions': {},
                'forward_expectations': {},
                'strategy_recommendations': {},
                'risk_assessment': {}
            }
    
    def _get_enhanced_intelligence_safe(self):
        """Get complete enhanced intelligence summary"""
        
        # Check availability
        if not self.is_anticipatory_intelligence_available():
            return {
                'available': False,
                'message': 'Anticipatory intelligence not available - using baseline intelligence'
            }
        
        # Gather all intelligence components
        intelligence = {
            'available': True,
            'timestamp': datetime.now().isoformat(),
            'version': self.version,
            'intelligence_type': 'anticipatory_enhanced'
        }
        
        # Current regime intelligence (with error handling)
        try:
            intelligence['regime_intelligence'] = self.get_current_regime_intelligence()
        except Exception as e:
            print(f"Error getting regime intelligence: {e}")
            intelligence['regime_intelligence'] = {}
        
        # Transition predictions (with error handling)
        try:
            intelligence['transition_predictions'] = self.get_regime_transition_predictions()
        except Exception as e:
            print(f"Error getting transition predictions: {e}")
            intelligence['transition_predictions'] = {}
        
        # Forward expectations (with error handling)
        try:
            intelligence['forward_expectations'] = self.get_forward_expectations()
        except Exception as e:
            print(f"Error getting forward expectations: {e}")
            intelligence['forward_expectations'] = {}
        
        # Capital allocation (with error handling)
        try:
            intelligence['capital_allocation'] = self.get_anticipatory_capital_allocation()
        except Exception as e:
            print(f"Error getting capital allocation: {e}")
            intelligence['capital_allocation'] = {}
        
        # Strategy recommendations (with error handling)
        try:
            intelligence['strategy_recommendations'] = self.get_strategy_recommendations()
        except Exception as e:
            print(f"Error getting strategy recommendations: {e}")
            intelligence['strategy_recommendations'] = {}
        
        # Risk assessment (with error handling)
        try:
            intelligence['risk_assessment'] = self.get_risk_assessment()
        except Exception as e:
            print(f"Error getting risk assessment: {e}")
            intelligence['risk_assessment'] = {}
        
        # Calculate overall intelligence confidence
        confidence_scores = []
        
        for component in ['regime_intelligence', 'transition_predictions', 'forward_expectations']:
            component_data = intelligence.get(component, {})
            if component_data.get('available'):
                confidence_scores.append(component_data.get('confidence', 0.5))
        
        intelligence['overall_confidence'] = np.mean(confidence_scores) if confidence_scores else 0.0
        
        # Generate intelligence narrative
        intelligence['narrative'] = self.generate_intelligence_narrative(intelligence)
        
        return intelligence
    
    def generate_intelligence_narrative(self, intelligence):
        """Generate human-readable intelligence narrative"""
        
        narrative_parts = []
        
        # Regime context
        regime_intel = intelligence.get('regime_intelligence', {})
        if regime_intel.get('available'):
            regime_name = regime_intel.get('regime_name', 'Unknown')
            regime_stability = regime_intel.get('regime_stability', 0.5)
            
            narrative_parts.append(f"Current market regime: {regime_name}")
            
            if regime_stability > 0.7:
                narrative_parts.append(f"with high stability ({regime_stability:.1%})")
            elif regime_stability > 0.4:
                narrative_parts.append(f"with moderate stability ({regime_stability:.1%})")
            else:
                narrative_parts.append(f"with low stability ({regime_stability:.1%}), indicating potential transition")
        
        # Transition predictions
        transition_intel = intelligence.get('transition_predictions', {})
        if transition_intel.get('available'):
            most_likely = transition_intel.get('most_likely_next', {})
            if most_likely:
                regime = most_likely.get('regime', 'Unknown')
                probability = most_likely.get('probability', 0.0)
                
                if probability > 0.3:
                    narrative_parts.append(f"Most likely next regime: {regime} ({probability:.1%} probability)")
        
        # Risk assessment
        risk_intel = intelligence.get('risk_assessment', {})
        if risk_intel.get('available'):
            risk_level = risk_intel.get('regime_risk_level', 'medium')
            narrative_parts.append(f"Risk level: {risk_level}")
        
        # Capital allocation context
        allocation_intel = intelligence.get('capital_allocation', {})
        if allocation_intel.get('available'):
            cash_allocation = allocation_intel.get('cash_allocation', 0.0)
            total_strategies = allocation_intel.get('total_strategies', 0)
            
            narrative_parts.append(f"Capital allocated across {total_strategies} strategies with {cash_allocation:.1%} cash buffer")
        
        # Combine narrative
        if narrative_parts:
            return ". ".join(narrative_parts) + "."
        else:
            return "Anticipatory intelligence operational with baseline configuration."
    
    def enhance_existing_intelligence(self, base_intelligence):
        """Enhance existing intelligence with anticipatory components"""
        
        if not self.is_anticipatory_intelligence_available():
            return base_intelligence
        
        enhanced_intelligence = base_intelligence.copy() if base_intelligence else {}
        
        # Add anticipatory intelligence
        anticipatory_intel = self.get_enhanced_intelligence()
        
        if anticipatory_intel.get('available'):
            enhanced_intelligence['anticipatory_intelligence'] = anticipatory_intel
            enhanced_intelligence['intelligence_type'] = 'enhanced_with_anticipatory'
            enhanced_intelligence['enhancement_timestamp'] = datetime.now().isoformat()
            
            # Enhance existing components with regime awareness
            if 'beliefs' in enhanced_intelligence:
                enhanced_intelligence['beliefs']['regime_context'] = anticipatory_intel.get('regime_intelligence', {})
            
            if 'actions' in enhanced_intelligence:
                enhanced_intelligence['actions']['anticipatory_actions'] = {
                    'capital_allocation': anticipatory_intel.get('capital_allocation', {}),
                    'strategy_recommendations': anticipatory_intel.get('strategy_recommendations', {}),
                    'risk_management': anticipatory_intel.get('risk_assessment', {})
                }
        
        return enhanced_intelligence
    
    def get_integration_status(self):
        """Get integration status"""
        
        status = {
            'timestamp': datetime.now().isoformat(),
            'version': self.version,
            'anticipatory_intelligence_available': self.is_anticipatory_intelligence_available(),
            'components_status': {}
        }
        
        # Check individual components
        components = [
            'regime_intelligence',
            'transition_predictions', 
            'forward_expectations',
            'capital_allocation',
            'strategy_recommendations',
            'risk_assessment'
        ]
        
        for component in components:
            method_name = f"get_{component}"
            if hasattr(self, method_name):
                try:
                    result = getattr(self, method_name)()
                    status['components_status'][component] = result.get('available', False)
                except:
                    status['components_status'][component] = False
        
        # Overall integration health
        available_components = sum(status['components_status'].values())
        total_components = len(status['components_status'])
        
        status['integration_health'] = {
            'available_components': available_components,
            'total_components': total_components,
            'health_score': available_components / total_components if total_components > 0 else 0.0,
            'status': 'excellent' if available_components >= total_components * 0.9 else
                     'good' if available_components >= total_components * 0.75 else
                     'partial' if available_components >= total_components * 0.5 else
                     'poor'
        }
        
        return status

def main():
    """Test anticipatory intelligence integration"""
    
    print("🧠 TESTING ANTICIPATORY INTELLIGENCE INTEGRATION")
    print("=" * 60)
    
    integration = AnticipatoryIntelligenceIntegration()
    
    # Check availability
    available = integration.is_anticipatory_intelligence_available()
    print(f"Anticipatory Intelligence Available: {'✅' if available else '❌'}")
    
    if available:
        # Get enhanced intelligence
        intelligence = integration.get_enhanced_intelligence()
        
        if intelligence.get('available'):
            print(f"\n📊 Enhanced Intelligence Summary:")
            print(f"   Overall Confidence: {intelligence.get('overall_confidence', 0):.1%}")
            print(f"   Narrative: {intelligence.get('narrative', 'No narrative available')}")
            
            # Show component status
            components = ['regime_intelligence', 'transition_predictions', 'capital_allocation']
            for component in components:
                component_data = intelligence.get(component, {})
                status = "✅" if component_data.get('available') else "❌"
                print(f"   {component.replace('_', ' ').title()}: {status}")
        
        # Get integration status
        status = integration.get_integration_status()
        health = status.get('integration_health', {})
        
        print(f"\n🔗 Integration Status:")
        print(f"   Health Score: {health.get('health_score', 0):.1%}")
        print(f"   Status: {health.get('status', 'unknown').upper()}")
        print(f"   Available Components: {health.get('available_components', 0)}/{health.get('total_components', 0)}")
    
    else:
        print("\n⚠️ Anticipatory intelligence not available")
        print("   Run scripts/build_anticipatory_intelligence.py to enable")
    
    return available

if __name__ == "__main__":
    main()
