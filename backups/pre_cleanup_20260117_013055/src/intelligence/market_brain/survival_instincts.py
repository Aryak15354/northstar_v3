#!/usr/bin/env python3
"""
🛡️ SURVIVAL INSTINCTS ENGINE - NORTHSTAR V3 MARKET BRAIN
The Self-Preservation System: Monitoring System Health & Stress

This monitors Northstar's own health and triggers protective actions when:
- Market conditions become unprecedented (regime surprise)
- Model beliefs are drifting from reality (belief drift)
- System stress indicators spike (volatility, drawdown)
- Causal relationships break down (structural breaks)

Integration with V3:
- Extends existing risk management with AI self-monitoring
- Feeds into Portfolio Governor for stress-based position sizing
- Triggers emergency protocols when system confidence drops

Output: system_stress.json + survival_metrics.parquet
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from sklearn.metrics.pairwise import cosine_similarity
import warnings
warnings.filterwarnings('ignore')

class SurvivalInstinctEngine:
    """
    Survival Instinct Engine - System Self-Monitoring
    
    Monitors system health across multiple dimensions:
    - Regime surprise (unprecedented market conditions)
    - Belief drift (model predictions vs reality)
    - System stress (volatility, drawdown, correlation breakdown)
    - Causal stability (relationship consistency)
    """
    
    def __init__(self):
        self.name = "Survival Instinct Engine"
        self.version = "1.0"
        
        # Data paths
        self.paths = {
            'pulse_state': 'data/processed/pulse_state.json',
            'pulse_history': 'data/processed/pulse_history.parquet',
            'regime_fingerprints': 'data/processed/regime_fingerprints.parquet',
            'market_causality': 'data/processed/market_causality.parquet',
            'portfolio_weights': 'data/processed/portfolio_weights.parquet',
            'strategy_performance': 'data/processed/strategy_performance',
            'system_stress': 'data/processed/system_stress.json',
            'survival_metrics': 'data/processed/survival_metrics.parquet',
            'emergency_log': 'data/processed/emergency_log.parquet'
        }
        
        # Survival thresholds
        self.thresholds = {
            'regime_surprise': {
                'low': 0.3,      # Below 30% similarity = surprise
                'high': 0.1      # Below 10% similarity = extreme surprise
            },
            'belief_drift': {
                'low': 0.15,     # 15% prediction error = drift
                'high': 0.30     # 30% prediction error = severe drift
            },
            'system_stress': {
                'low': 0.6,      # Stress index above 0.6 = stress
                'high': 0.8      # Stress index above 0.8 = severe stress
            },
            'causal_breakdown': {
                'low': 0.5,      # 50% of relationships unstable = breakdown
                'high': 0.7      # 70% of relationships unstable = severe breakdown
            },
            'portfolio_drawdown': {
                'low': 0.05,     # 5% drawdown = caution
                'high': 0.15     # 15% drawdown = emergency
            }
        }
        
        # Survival actions
        self.survival_actions = {
            'normal': {
                'exposure_multiplier': 1.0,
                'position_limit': 0.08,
                'sector_limit': 0.30,
                'description': 'Normal operations'
            },
            'caution': {
                'exposure_multiplier': 0.8,
                'position_limit': 0.06,
                'sector_limit': 0.25,
                'description': 'Reduced exposure due to elevated stress'
            },
            'stress': {
                'exposure_multiplier': 0.6,
                'position_limit': 0.04,
                'sector_limit': 0.20,
                'description': 'Significant exposure reduction due to high stress'
            },
            'emergency': {
                'exposure_multiplier': 0.3,
                'position_limit': 0.02,
                'sector_limit': 0.15,
                'description': 'Emergency protocols activated'
            },
            'shutdown': {
                'exposure_multiplier': 0.1,
                'position_limit': 0.01,
                'sector_limit': 0.05,
                'description': 'System shutdown - minimal exposure only'
            }
        }
    
    def assess_regime_surprise(self):
        """Assess how unprecedented current market conditions are"""
        
        print("🔍 Assessing regime surprise...")
        
        try:
            # Load pulse state for regime info
            if os.path.exists(self.paths['pulse_state']):
                with open(self.paths['pulse_state'], 'r') as f:
                    pulse_state = json.load(f)
                
                regime_info = pulse_state.get('regime_info', {})
                current_regime = regime_info.get('current_regime', {})
                
                if current_regime:
                    similarity = current_regime.get('similarity', 0.0)
                    regime_name = current_regime.get('regime_name', 'Unknown')
                    
                    # Assess surprise level
                    if similarity < self.thresholds['regime_surprise']['high']:
                        surprise_level = 'extreme'
                    elif similarity < self.thresholds['regime_surprise']['low']:
                        surprise_level = 'high'
                    else:
                        surprise_level = 'normal'
                    
                    print(f"   📊 Regime similarity: {similarity:.3f} ({surprise_level})")
                    
                    return {
                        'similarity': similarity,
                        'regime_name': regime_name,
                        'surprise_level': surprise_level,
                        'unprecedented': similarity < self.thresholds['regime_surprise']['low']
                    }
            
            print("   ℹ️ Regime information will be available as historical patterns develop")
            return {
                'similarity': 0.5,
                'regime_name': 'Unknown',
                'surprise_level': 'unknown',
                'unprecedented': False
            }
            
        except Exception as e:
            print(f"   ❌ Error assessing regime surprise: {e}")
            return {
                'similarity': 0.5,
                'regime_name': 'Error',
                'surprise_level': 'unknown',
                'unprecedented': False
            }
    
    def assess_belief_drift(self):
        """Assess how much model beliefs are drifting from reality"""
        
        print("🎯 Assessing belief drift...")
        
        try:
            # Load strategy performance data
            strategy_files = []
            if os.path.exists(self.paths['strategy_performance']):
                strategy_files = [f for f in os.listdir(self.paths['strategy_performance']) 
                                if f.endswith('.parquet')]
            
            if not strategy_files:
                print("   ⚠️ No strategy performance data available")
                return {
                    'drift_score': 0.1,
                    'drift_level': 'unknown',
                    'strategies_analyzed': 0
                }
            
            drift_scores = []
            
            for strategy_file in strategy_files[:5]:  # Analyze top 5 strategies
                try:
                    strategy_path = os.path.join(self.paths['strategy_performance'], strategy_file)
                    strategy_perf = pd.read_parquet(strategy_path)
                    
                    if len(strategy_perf) < 10:  # Need minimum data
                        continue
                    
                    # Calculate prediction error (simplified)
                    recent_perf = strategy_perf.tail(20)
                    
                    if 'expected_return' in recent_perf.columns and 'actual_return' in recent_perf.columns:
                        prediction_errors = abs(recent_perf['expected_return'] - recent_perf['actual_return'])
                        avg_error = prediction_errors.mean()
                        drift_scores.append(avg_error)
                    
                except Exception as e:
                    continue
            
            if drift_scores:
                overall_drift = np.mean(drift_scores)
                
                # Assess drift level
                if overall_drift > self.thresholds['belief_drift']['high']:
                    drift_level = 'severe'
                elif overall_drift > self.thresholds['belief_drift']['low']:
                    drift_level = 'moderate'
                else:
                    drift_level = 'normal'
                
                print(f"   📊 Belief drift: {overall_drift:.3f} ({drift_level})")
                
                return {
                    'drift_score': overall_drift,
                    'drift_level': drift_level,
                    'strategies_analyzed': len(drift_scores)
                }
            else:
                print("   ℹ️ Belief drift analysis will be available as regime patterns develop")
                return {
                    'drift_score': 0.1,
                    'drift_level': 'unknown',
                    'strategies_analyzed': 0
                }
                
        except Exception as e:
            print(f"   ❌ Error assessing belief drift: {e}")
            return {
                'drift_score': 0.1,
                'drift_level': 'error',
                'strategies_analyzed': 0
            }
    
    def assess_system_stress(self):
        """Assess overall system stress from multiple indicators"""
        
        print("⚡ Assessing system stress...")
        
        stress_indicators = {}
        
        try:
            # 1. Pulse intensity stress
            if os.path.exists(self.paths['pulse_state']):
                with open(self.paths['pulse_state'], 'r') as f:
                    pulse_state = json.load(f)
                
                pulse_intensity = pulse_state.get('pulse_intensity', 0.0)
                stress_indicators['pulse_intensity'] = min(pulse_intensity / 2.0, 1.0)  # Normalize to 0-1
            
            # 2. Market volatility stress
            if os.path.exists(self.paths['pulse_history']):
                pulse_history = pd.read_parquet(self.paths['pulse_history'])
                
                if len(pulse_history) >= 10:
                    recent_intensity = pulse_history['pulse_intensity'].tail(10)
                    volatility_stress = recent_intensity.std() / recent_intensity.mean() if recent_intensity.mean() > 0 else 0
                    stress_indicators['volatility'] = min(volatility_stress, 1.0)
            
            # 3. Portfolio drawdown stress
            if os.path.exists(self.paths['portfolio_weights']):
                portfolio_df = pd.read_parquet(self.paths['portfolio_weights'])
                
                if 'portfolio_return' in portfolio_df.columns and len(portfolio_df) >= 20:
                    returns = portfolio_df['portfolio_return'].tail(20)
                    cumulative = (1 + returns).cumprod()
                    running_max = cumulative.expanding().max()
                    drawdown = (cumulative - running_max) / running_max
                    max_drawdown = abs(drawdown.min())
                    
                    stress_indicators['drawdown'] = min(max_drawdown / 0.2, 1.0)  # Normalize by 20% max
            
            # 4. Risk level stress (from pulse state)
            if os.path.exists(self.paths['pulse_state']):
                with open(self.paths['pulse_state'], 'r') as f:
                    pulse_state = json.load(f)
                
                risk_level = pulse_state.get('risk_level', 'low')
                risk_stress = {'low': 0.2, 'medium': 0.6, 'high': 1.0}.get(risk_level, 0.5)
                stress_indicators['risk_level'] = risk_stress
            
            # Calculate composite stress score
            if stress_indicators:
                composite_stress = np.mean(list(stress_indicators.values()))
                
                # Assess stress level
                if composite_stress > self.thresholds['system_stress']['high']:
                    stress_level = 'severe'
                elif composite_stress > self.thresholds['system_stress']['low']:
                    stress_level = 'elevated'
                else:
                    stress_level = 'normal'
                
                print(f"   📊 System stress: {composite_stress:.3f} ({stress_level})")
                
                return {
                    'composite_stress': composite_stress,
                    'stress_level': stress_level,
                    'indicators': stress_indicators
                }
            else:
                print("   ⚠️ No stress indicators available")
                return {
                    'composite_stress': 0.3,
                    'stress_level': 'unknown',
                    'indicators': {}
                }
                
        except Exception as e:
            print(f"   ❌ Error assessing system stress: {e}")
            return {
                'composite_stress': 0.5,
                'stress_level': 'error',
                'indicators': {}
            }
    
    def assess_causal_stability(self):
        """Assess stability of causal relationships"""
        
        print("🔗 Assessing causal stability...")
        
        try:
            if not os.path.exists(self.paths['market_causality']):
                print("   ℹ️ Causality analysis will be available when more data is collected")
                return {
                    'stability_score': 0.7,
                    'stability_level': 'unknown',
                    'relationships_analyzed': 0
                }
            
            causality_df = pd.read_parquet(self.paths['market_causality'])
            
            if causality_df.empty:
                print("   ⚠️ Empty causality data")
                return {
                    'stability_score': 0.7,
                    'stability_level': 'unknown',
                    'relationships_analyzed': 0
                }
            
            # Analyze relationship strength distribution
            strengths = causality_df['strength'].values
            
            # Check for stability indicators
            stability_indicators = []
            
            # 1. Strength consistency
            strength_std = np.std(strengths)
            strength_mean = np.mean(strengths)
            cv = strength_std / strength_mean if strength_mean > 0 else 1.0
            stability_indicators.append(1.0 - min(cv, 1.0))  # Lower CV = more stable
            
            # 2. Number of strong relationships
            strong_relationships = (strengths > 0.7).sum()
            total_relationships = len(strengths)
            strong_ratio = strong_relationships / total_relationships if total_relationships > 0 else 0
            stability_indicators.append(strong_ratio)
            
            # 3. P-value distribution (lower p-values = more stable)
            if 'p_value' in causality_df.columns:
                p_values = causality_df['p_value'].values
                significant_ratio = (p_values < 0.01).sum() / len(p_values) if len(p_values) > 0 else 0
                stability_indicators.append(significant_ratio)
            
            # Calculate composite stability
            stability_score = np.mean(stability_indicators) if stability_indicators else 0.7
            
            # Assess stability level
            if stability_score < (1.0 - self.thresholds['causal_breakdown']['high']):
                stability_level = 'breakdown'
            elif stability_score < (1.0 - self.thresholds['causal_breakdown']['low']):
                stability_level = 'unstable'
            else:
                stability_level = 'stable'
            
            print(f"   📊 Causal stability: {stability_score:.3f} ({stability_level})")
            
            return {
                'stability_score': stability_score,
                'stability_level': stability_level,
                'relationships_analyzed': len(causality_df)
            }
            
        except Exception as e:
            print(f"   ❌ Error assessing causal stability: {e}")
            return {
                'stability_score': 0.5,
                'stability_level': 'error',
                'relationships_analyzed': 0
            }
    
    def determine_survival_mode(self, regime_surprise, belief_drift, system_stress, causal_stability):
        """Determine appropriate survival mode based on all assessments"""
        
        print("🛡️ Determining survival mode...")
        
        # Count severe conditions
        severe_conditions = 0
        moderate_conditions = 0
        
        # Regime surprise
        if regime_surprise['surprise_level'] == 'extreme':
            severe_conditions += 1
        elif regime_surprise['surprise_level'] == 'high':
            moderate_conditions += 1
        
        # Belief drift
        if belief_drift['drift_level'] == 'severe':
            severe_conditions += 1
        elif belief_drift['drift_level'] == 'moderate':
            moderate_conditions += 1
        
        # System stress
        if system_stress['stress_level'] == 'severe':
            severe_conditions += 1
        elif system_stress['stress_level'] == 'elevated':
            moderate_conditions += 1
        
        # Causal stability
        if causal_stability['stability_level'] == 'breakdown':
            severe_conditions += 1
        elif causal_stability['stability_level'] == 'unstable':
            moderate_conditions += 1
        
        # Determine survival mode
        if severe_conditions >= 3:
            survival_mode = 'shutdown'
        elif severe_conditions >= 2:
            survival_mode = 'emergency'
        elif severe_conditions >= 1 or moderate_conditions >= 3:
            survival_mode = 'stress'
        elif moderate_conditions >= 1:
            survival_mode = 'caution'
        else:
            survival_mode = 'normal'
        
        print(f"   🎯 Survival mode: {survival_mode.upper()}")
        print(f"   📊 Conditions: {severe_conditions} severe, {moderate_conditions} moderate")
        
        return survival_mode
    
    def generate_survival_recommendations(self, survival_mode, assessments):
        """Generate specific survival recommendations"""
        
        recommendations = []
        
        # Get survival action parameters
        action_params = self.survival_actions[survival_mode]
        
        # Base recommendations
        recommendations.append(f"Set exposure multiplier to {action_params['exposure_multiplier']}")
        recommendations.append(f"Limit single positions to {action_params['position_limit']:.1%}")
        recommendations.append(f"Limit sector exposure to {action_params['sector_limit']:.1%}")
        
        # Specific recommendations based on conditions
        regime_surprise = assessments['regime_surprise']
        if regime_surprise['unprecedented']:
            recommendations.append("Reduce exposure to unprecedented market conditions")
            recommendations.append("Increase cash buffer for unknown regime")
        
        belief_drift = assessments['belief_drift']
        if belief_drift['drift_level'] in ['moderate', 'severe']:
            recommendations.append("Reduce reliance on model predictions")
            recommendations.append("Increase manual oversight of positions")
        
        system_stress = assessments['system_stress']
        if system_stress['stress_level'] in ['elevated', 'severe']:
            recommendations.append("Implement additional risk controls")
            recommendations.append("Monitor portfolio more frequently")
        
        causal_stability = assessments['causal_stability']
        if causal_stability['stability_level'] in ['unstable', 'breakdown']:
            recommendations.append("Reduce reliance on causal relationships")
            recommendations.append("Revert to simpler allocation methods")
        
        return recommendations
    
    def assess_survival_instincts(self):
        """Perform complete survival instinct assessment"""
        
        print("🛡️ ASSESSING SURVIVAL INSTINCTS")
        print("=" * 60)
        
        # Perform all assessments
        regime_surprise = self.assess_regime_surprise()
        belief_drift = self.assess_belief_drift()
        system_stress = self.assess_system_stress()
        causal_stability = self.assess_causal_stability()
        
        # Determine survival mode
        survival_mode = self.determine_survival_mode(
            regime_surprise, belief_drift, system_stress, causal_stability
        )
        
        # Generate recommendations
        assessments = {
            'regime_surprise': regime_surprise,
            'belief_drift': belief_drift,
            'system_stress': system_stress,
            'causal_stability': causal_stability
        }
        
        recommendations = self.generate_survival_recommendations(survival_mode, assessments)
        
        # Create survival state
        survival_state = {
            'timestamp': datetime.now().isoformat(),
            'survival_mode': survival_mode,
            'action_parameters': self.survival_actions[survival_mode],
            'assessments': assessments,
            'recommendations': recommendations,
            'emergency_triggered': survival_mode in ['emergency', 'shutdown']
        }
        
        # Save survival state
        self.save_survival_state(survival_state)
        
        # Log emergency if needed
        if survival_state['emergency_triggered']:
            self.log_emergency_event(survival_state)
        
        print(f"\n✅ Survival assessment complete!")
        print(f"   Mode: {survival_mode.upper()}")
        print(f"   Emergency: {'YES' if survival_state['emergency_triggered'] else 'NO'}")
        print(f"   Recommendations: {len(recommendations)}")
        
        return survival_state
    
    def save_survival_state(self, survival_state):
        """Save current survival state"""
        
        # Create output directory
        os.makedirs(os.path.dirname(self.paths['system_stress']), exist_ok=True)
        
        # Save survival state JSON
        with open(self.paths['system_stress'], 'w') as f:
            json.dump(survival_state, f, indent=2)
        print(f"💾 Saved survival state: {self.paths['system_stress']}")
        
        # Create survival metrics for time series
        survival_metrics = pd.DataFrame([{
            'date': pd.Timestamp.now(),
            'survival_mode': survival_state['survival_mode'],
            'exposure_multiplier': survival_state['action_parameters']['exposure_multiplier'],
            'regime_similarity': survival_state['assessments']['regime_surprise']['similarity'],
            'belief_drift': survival_state['assessments']['belief_drift']['drift_score'],
            'system_stress': survival_state['assessments']['system_stress']['composite_stress'],
            'causal_stability': survival_state['assessments']['causal_stability']['stability_score'],
            'emergency_triggered': survival_state['emergency_triggered']
        }])
        
        # Append to survival history
        if os.path.exists(self.paths['survival_metrics']):
            existing_metrics = pd.read_parquet(self.paths['survival_metrics'])
            survival_history = pd.concat([existing_metrics, survival_metrics], ignore_index=True)
        else:
            survival_history = survival_metrics
        
        # Keep only recent history (last 1000 records)
        survival_history = survival_history.tail(1000)
        
        survival_history.to_parquet(self.paths['survival_metrics'])
        print(f"💾 Updated survival metrics: {len(survival_history)} records")
    
    def log_emergency_event(self, survival_state):
        """Log emergency event for analysis"""
        
        emergency_event = pd.DataFrame([{
            'timestamp': pd.Timestamp.now(),
            'survival_mode': survival_state['survival_mode'],
            'trigger_conditions': json.dumps(survival_state['assessments']),
            'recommendations': json.dumps(survival_state['recommendations']),
            'exposure_reduction': 1.0 - survival_state['action_parameters']['exposure_multiplier']
        }])
        
        # Append to emergency log
        if os.path.exists(self.paths['emergency_log']):
            existing_log = pd.read_parquet(self.paths['emergency_log'])
            emergency_log = pd.concat([existing_log, emergency_event], ignore_index=True)
        else:
            emergency_log = emergency_event
        
        emergency_log.to_parquet(self.paths['emergency_log'])
        print(f"🚨 Logged emergency event: {survival_state['survival_mode']}")
    
    def load_survival_state(self):
        """Load current survival state"""
        
        try:
            if os.path.exists(self.paths['system_stress']):
                with open(self.paths['system_stress'], 'r') as f:
                    survival_state = json.load(f)
                print(f"📊 Loaded survival state: {survival_state['survival_mode']}")
                return survival_state
        except Exception as e:
            print(f"⚠️ Could not load survival state: {e}")
        
        return {}
    
    def get_survival_parameters(self):
        """Get current survival parameters for portfolio governor"""
        
        survival_state = self.load_survival_state()
        
        if survival_state and 'action_parameters' in survival_state:
            return survival_state['action_parameters']
        else:
            # Return default parameters if no survival state
            return self.survival_actions['normal']
    
    def is_emergency_mode(self):
        """Check if system is in emergency mode"""
        
        survival_state = self.load_survival_state()
        
        if survival_state:
            return survival_state.get('emergency_triggered', False)
        
        return False

def main():
    """Assess survival instincts"""
    
    engine = SurvivalInstinctEngine()
    survival_state = engine.assess_survival_instincts()
    
    if survival_state:
        print(f"\n🎯 Survival instincts assessment complete!")
        print(f"   System is in {survival_state['survival_mode'].upper()} mode")
        
        if survival_state['emergency_triggered']:
            print("   🚨 EMERGENCY PROTOCOLS ACTIVATED")
        
        return True
    else:
        print("❌ Failed to assess survival instincts")
        return False

if __name__ == "__main__":
    main()