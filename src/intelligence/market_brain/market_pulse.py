#!/usr/bin/env python3
"""
💓 MARKET PULSE ENGINE - NORTHSTAR V3 MARKET BRAIN
The Heartbeat: Real-time Market Force Detection

This combines tensor, causality, and regime memory to detect:
- Which forces are currently dominating
- How they're propagating through the system
- What this implies for the next 2-8 weeks
- Where opportunities and risks are forming

Integration with V3:
- Replaces opportunity surface classification with pulse-based scoring
- Feeds into Portfolio Governor for position sizing
- Enhances Market State Spine with real-time pulse metrics

Output: pulse_state.json + pulse_metrics.parquet
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

class MarketPulseEngine:
    """
    Market Pulse Engine - Real-time Force Detection
    
    Combines all market brain components to detect:
    - Dominant market forces
    - Causal propagation patterns
    - Regime similarity and transitions
    - Force flow predictions
    """
    
    def __init__(self):
        self.name = "Market Pulse Engine"
        self.version = "1.0"
        
        # Data paths
        self.paths = {
            'market_tensor': 'data/processed/market_tensor.parquet',
            'market_causality': 'data/processed/market_causality.parquet',
            'regime_fingerprints': 'data/processed/regime_fingerprints.parquet',
            'market_graph': 'data/processed/market_graph.json',
            'pulse_state': 'data/processed/pulse_state.json',
            'pulse_metrics': 'data/processed/pulse_metrics.parquet',
            'pulse_history': 'data/processed/pulse_history.parquet'
        }
        
        # Pulse configuration
        self.config = {
            'lookback_periods': 12,     # Periods to analyze for pulse
            'force_threshold': 0.5,     # Minimum force strength to consider
            'similarity_threshold': 0.7, # Minimum regime similarity
            'propagation_depth': 3,     # Causal propagation depth
            'top_forces': 10,           # Top forces to track
            'pulse_update_freq': 'daily' # Pulse update frequency
        }
        
        # Force categories for interpretation
        self.force_categories = {
            'monetary': ['rbi', 'repo', 'liquidity', 'money'],
            'credit': ['yield', 'spread', 'bond', 'credit'],
            'flows': ['fii', 'dii', 'flow', 'foreign'],
            'structure': ['breadth', 'participation', 'volatility', 'correlation'],
            'sectors': ['bank', 'it', 'pharma', 'auto', 'fmcg', 'metal', 'energy'],
            'corporate': ['corp_factor', 'earnings', 'margin']
        }
        
        # Pulse interpretations
        self.pulse_meanings = {
            'monetary_tightening': 'Central bank reducing liquidity',
            'monetary_easing': 'Central bank increasing liquidity',
            'credit_stress': 'Rising borrowing costs and spreads',
            'credit_easing': 'Falling borrowing costs',
            'flow_exodus': 'Foreign capital leaving markets',
            'flow_influx': 'Foreign capital entering markets',
            'structure_deterioration': 'Market breadth weakening',
            'structure_improvement': 'Market breadth strengthening',
            'sector_rotation': 'Capital rotating between sectors',
            'corporate_stress': 'Corporate fundamentals weakening'
        }
    
    def load_market_brain_components(self):
        """Load all market brain components"""
        
        print("🧠 Loading market brain components...")
        
        components = {}
        
        # Load market tensor
        try:
            if os.path.exists(self.paths['market_tensor']):
                from .market_tensor import MarketTensorEngine
                tensor = pd.read_parquet(self.paths['market_tensor'])
                components['tensor'] = MarketTensorEngine.canonicalize_tensor_frame(tensor)
                print(f"   ✅ Market tensor: {components['tensor'].shape}")
            else:
                print("   ⚠️ Market tensor not found")
                components['tensor'] = pd.DataFrame()
        except Exception as e:
            print(f"   ❌ Error loading tensor: {e}")
            components['tensor'] = pd.DataFrame()
        
        # Load causality data
        try:
            if os.path.exists(self.paths['market_causality']):
                components['causality'] = pd.read_parquet(self.paths['market_causality'])
                print(f"   ✅ Causality: {len(components['causality'])} relationships")
            else:
                print("   ℹ️ Causality analysis requires longer historical data - will be available in future updates")
                components['causality'] = pd.DataFrame()
        except Exception as e:
            print(f"   ❌ Error loading causality: {e}")
            components['causality'] = pd.DataFrame()
        
        # Load regime fingerprints
        try:
            if os.path.exists(self.paths['regime_fingerprints']):
                components['regimes'] = pd.read_parquet(self.paths['regime_fingerprints'])
                print(f"   ✅ Regimes: {len(components['regimes'])} periods")
            else:
                print("   ℹ️ Regime fingerprints will be built as more market data is collected")
                components['regimes'] = pd.DataFrame()
        except Exception as e:
            print(f"   ❌ Error loading regimes: {e}")
            components['regimes'] = pd.DataFrame()
        
        # Load causal graph
        try:
            if os.path.exists(self.paths['market_graph']):
                with open(self.paths['market_graph'], 'r') as f:
                    components['graph'] = json.load(f)
                print(f"   ✅ Causal graph: {len(components['graph'].get('edges', []))} edges")
            else:
                print("   ℹ️ Causal graph will be built as more data becomes available")
                components['graph'] = {}
        except Exception as e:
            print(f"   ❌ Error loading graph: {e}")
            components['graph'] = {}
        
        return components
    
    def detect_dominant_forces(self, tensor):
        """Detect currently dominant market forces"""
        
        print("⚡ Detecting dominant forces...")
        
        if tensor.empty:
            print("   ⚠️ No tensor data available")
            return {}
        
        if len(tensor) < self.config['lookback_periods']:
            print(f"   ⚠️ Insufficient tensor data: {len(tensor)} < {self.config['lookback_periods']}")
            # Use what we have
            recent_data = tensor
        else:
            # Get recent data
            recent_data = tensor.tail(self.config['lookback_periods'])
        
        # Calculate force strength (change magnitude + persistence)
        force_analysis = {}
        
        for column in tensor.columns:
            try:
                recent_series = pd.to_numeric(recent_data[column], errors='coerce').replace([np.inf, -np.inf], np.nan).dropna()
                if len(recent_series) < 4:
                    continue
                recent_values = recent_series.values.astype(float)
                
                # Skip if all values are the same or NaN
                if len(set(recent_values)) <= 1 or np.isnan(recent_values).all():
                    continue

                # Normalize each variable in-window to avoid raw-magnitude dominance.
                center = np.median(recent_values)
                mad = np.median(np.abs(recent_values - center))
                scale = max(float(mad * 1.4826), float(np.std(recent_values)), 1e-6)
                zvals = (recent_values - center) / scale

                # Calculate dimensionless metrics
                recent_change = abs(zvals[-1] - zvals[0])
                volatility = float(np.std(zvals))
                trend_strength = abs(np.corrcoef(range(len(zvals)), zvals)[0, 1])
                
                # Combine into bounded force strength
                force_strength = float(np.clip(
                    (recent_change * 0.4 + volatility * 0.3 + trend_strength * 0.3),
                    0.0,
                    2.0
                ))
                
                if force_strength >= self.config['force_threshold']:
                    force_analysis[column] = {
                        'strength': float(force_strength),
                        'recent_change': float(recent_change),
                        'volatility': float(volatility),
                        'trend_strength': float(trend_strength),
                        'direction': 'up' if zvals[-1] > zvals[0] else 'down',
                        'current_value': float(zvals[-1]),
                        'current_value_raw': float(recent_values[-1]),
                        'category': self.categorize_force(column)
                    }
            
            except Exception as e:
                continue
        
        # Sort by strength
        sorted_forces = dict(sorted(force_analysis.items(), 
                                  key=lambda x: x[1]['strength'], 
                                  reverse=True))
        
        # Take top forces
        top_forces = dict(list(sorted_forces.items())[:self.config['top_forces']])
        
        print(f"   📊 Detected {len(top_forces)} dominant forces")
        for force, data in list(top_forces.items())[:5]:
            print(f"      {force}: {data['strength']:.3f} ({data['direction']})")
        
        return top_forces
    
    def categorize_force(self, variable_name):
        """Categorize a force variable"""
        
        var_lower = variable_name.lower()
        
        for category, keywords in self.force_categories.items():
            for keyword in keywords:
                if keyword in var_lower:
                    return category
        
        return 'other'
    
    def trace_force_propagation(self, dominant_forces, causality_df, graph_data):
        """Trace how dominant forces propagate through the system"""
        
        print("🌊 Tracing force propagation...")
        
        if causality_df.empty or not graph_data:
            print("   ℹ️ Causality analysis will be available when more historical data is collected")
            return {}
        
        propagation_map = {}
        
        for force_name, force_data in dominant_forces.items():
            
            # Find what this force influences
            influences = causality_df[causality_df['cause'] == force_name].copy()
            
            if influences.empty:
                continue
            
            # Sort by strength and take top influences
            influences = influences.sort_values('strength', ascending=False).head(5)
            
            propagation_chain = []
            
            for _, influence in influences.iterrows():
                effect_var = influence['effect']
                strength = influence['strength']
                lag = influence['lag']
                
                # Predict impact direction
                force_direction = 1 if force_data['direction'] == 'up' else -1
                predicted_impact = force_direction * strength
                
                propagation_chain.append({
                    'target': effect_var,
                    'strength': float(strength),
                    'lag_periods': int(lag),
                    'predicted_impact': float(predicted_impact),
                    'category': self.categorize_force(effect_var)
                })
            
            if propagation_chain:
                propagation_map[force_name] = {
                    'source_strength': force_data['strength'],
                    'source_direction': force_data['direction'],
                    'propagation_chain': propagation_chain
                }
        
        print(f"   🌊 Mapped propagation for {len(propagation_map)} forces")
        
        return propagation_map
    
    def match_current_regime(self, tensor, regime_fingerprints):
        """Match current market state to historical regimes"""
        
        print("🔍 Matching current regime...")
        
        if tensor.empty or regime_fingerprints.empty:
            print("   ℹ️ Regime matching requires more historical patterns - building baseline")
            return {}
        
        try:
            # Get current window
            window_size = 26  # Same as regime memory
            if len(tensor) < window_size:
                print("   ⚠️ Insufficient data for regime window")
                return {}
            
            current_window = tensor.tail(window_size)
            
            # Use regime memory engine for matching
            try:
                from .regime_memory import RegimeMemoryEngine
            except Exception:
                # Fallback when executed directly as a script path.
                from src.intelligence.market_brain.regime_memory import RegimeMemoryEngine
            regime_engine = RegimeMemoryEngine()
            
            current_regime = regime_engine.get_current_regime(current_window)
            
            if current_regime:
                print(f"   🎯 Current regime: {current_regime['regime_name']} "
                      f"(similarity: {current_regime['similarity']:.3f})")
                
                # Get regime characteristics
                regime_chars = regime_engine.get_regime_characteristics(current_regime['regime_cluster'])
                
                # Predict regime evolution
                evolution = regime_engine.predict_regime_evolution(current_regime['regime_cluster'])
                
                return {
                    'current_regime': current_regime,
                    'characteristics': regime_chars,
                    'predicted_evolution': evolution
                }
            else:
                print("   ⚠️ Could not match current regime")
                return {}
        
        except Exception as e:
            print(f"   ❌ Error in regime matching: {e}")
            return {}
    
    def synthesize_market_pulse(self, dominant_forces, propagation_map, regime_info):
        """Synthesize complete market pulse from all components"""
        
        print("💓 Synthesizing market pulse...")
        
        # Categorize forces by type
        force_summary = {}
        for category in self.force_categories.keys():
            force_summary[category] = {
                'active_forces': 0,
                'net_strength': 0.0,
                'dominant_direction': 'neutral'
            }
        
        # Analyze force categories
        for force_name, force_data in dominant_forces.items():
            category = force_data['category']
            
            if category in force_summary:
                force_summary[category]['active_forces'] += 1
                
                direction_multiplier = 1 if force_data['direction'] == 'up' else -1
                force_summary[category]['net_strength'] += force_data['strength'] * direction_multiplier
        
        # Determine dominant directions
        for category, summary in force_summary.items():
            if summary['net_strength'] > 0.5:
                summary['dominant_direction'] = 'up'
            elif summary['net_strength'] < -0.5:
                summary['dominant_direction'] = 'down'
            else:
                summary['dominant_direction'] = 'neutral'
        
        # Generate pulse interpretation
        pulse_signals = []
        
        # Monetary pulse
        if force_summary['monetary']['dominant_direction'] == 'down':
            pulse_signals.append('monetary_tightening')
        elif force_summary['monetary']['dominant_direction'] == 'up':
            pulse_signals.append('monetary_easing')
        
        # Credit pulse
        if force_summary['credit']['dominant_direction'] == 'up':
            pulse_signals.append('credit_stress')
        elif force_summary['credit']['dominant_direction'] == 'down':
            pulse_signals.append('credit_easing')
        
        # Flow pulse
        if force_summary['flows']['dominant_direction'] == 'down':
            pulse_signals.append('flow_exodus')
        elif force_summary['flows']['dominant_direction'] == 'up':
            pulse_signals.append('flow_influx')
        
        # Structure pulse
        if force_summary['structure']['dominant_direction'] == 'down':
            pulse_signals.append('structure_deterioration')
        elif force_summary['structure']['dominant_direction'] == 'up':
            pulse_signals.append('structure_improvement')
        
        # Sector pulse
        if force_summary['sectors']['active_forces'] >= 3:
            pulse_signals.append('sector_rotation')
        
        # Corporate pulse
        if force_summary['corporate']['dominant_direction'] == 'down':
            pulse_signals.append('corporate_stress')
        
        # Generate narrative
        pulse_narrative = self.generate_pulse_narrative(pulse_signals, regime_info)
        
        # Calculate overall pulse strength
        total_force_strength = sum(float(f.get('strength', 0.0)) for f in dominant_forces.values())
        raw_pulse_intensity = (total_force_strength / len(dominant_forces)) if dominant_forces else 0.0
        pulse_intensity = float(np.clip(raw_pulse_intensity / 2.5, 0.0, 1.0))
        
        pulse_state = {
            'timestamp': datetime.now().isoformat(),
            'pulse_intensity': float(pulse_intensity),
            'pulse_intensity_raw': float(raw_pulse_intensity),
            'dominant_forces': dominant_forces,
            'force_summary': force_summary,
            'propagation_map': propagation_map,
            'regime_info': regime_info,
            'pulse_signals': pulse_signals,
            'pulse_narrative': pulse_narrative,
            'market_phase': self.determine_market_phase(force_summary, regime_info),
            'risk_level': self.assess_risk_level(force_summary, pulse_intensity),
            'opportunity_zones': self.identify_opportunity_zones(propagation_map, force_summary)
        }
        
        print(f"   💓 Pulse intensity: {pulse_intensity:.2f}")
        print(f"   🎯 Market phase: {pulse_state['market_phase']}")
        print(f"   📊 Risk level: {pulse_state['risk_level']}")
        
        return pulse_state
    
    def generate_pulse_narrative(self, pulse_signals, regime_info):
        """Generate human-readable pulse narrative"""
        
        narrative_parts = []
        
        # Add regime context
        if regime_info and 'current_regime' in regime_info:
            regime_name = regime_info['current_regime']['regime_name']
            similarity = regime_info['current_regime']['similarity']
            narrative_parts.append(f"Market resembles {regime_name} regime ({similarity:.1%} similarity)")
        
        # Add pulse signals
        for signal in pulse_signals:
            if signal in self.pulse_meanings:
                narrative_parts.append(self.pulse_meanings[signal])
        
        # Combine into narrative
        if narrative_parts:
            narrative = ". ".join(narrative_parts) + "."
        else:
            narrative = "Market forces are in neutral state with no dominant trends."
        
        return narrative
    
    def determine_market_phase(self, force_summary, regime_info):
        """Determine current market phase"""
        
        # Use regime info if available
        if regime_info and 'current_regime' in regime_info:
            regime_name = regime_info['current_regime']['regime_name'].lower()
            
            if 'crisis' in regime_name:
                return 'crisis'
            elif 'recovery' in regime_name:
                return 'recovery'
            elif 'expansion' in regime_name:
                return 'expansion'
            elif 'peak' in regime_name:
                return 'peak'
            elif 'slowdown' in regime_name:
                return 'slowdown'
        
        # Fallback to force analysis
        monetary_dir = force_summary['monetary']['dominant_direction']
        credit_dir = force_summary['credit']['dominant_direction']
        flow_dir = force_summary['flows']['dominant_direction']
        structure_dir = force_summary['structure']['dominant_direction']
        
        # Simple phase detection logic
        if monetary_dir == 'up' and flow_dir == 'up' and structure_dir == 'up':
            return 'expansion'
        elif monetary_dir == 'down' and credit_dir == 'up' and structure_dir == 'down':
            return 'crisis'
        elif structure_dir == 'up' and flow_dir == 'up':
            return 'recovery'
        elif monetary_dir == 'down' and structure_dir == 'down':
            return 'slowdown'
        else:
            return 'neutral'
    
    def assess_risk_level(self, force_summary, pulse_intensity):
        """Assess current risk level"""
        
        risk_factors = 0
        
        # Check for stress signals
        if force_summary['monetary']['dominant_direction'] == 'down':
            risk_factors += 1
        
        if force_summary['credit']['dominant_direction'] == 'up':
            risk_factors += 1
        
        if force_summary['flows']['dominant_direction'] == 'down':
            risk_factors += 1
        
        if force_summary['structure']['dominant_direction'] == 'down':
            risk_factors += 1
        
        if force_summary['corporate']['dominant_direction'] == 'down':
            risk_factors += 1
        
        # High pulse intensity can indicate instability
        if pulse_intensity > 0.7:
            risk_factors += 1
        
        # Classify risk level
        if risk_factors >= 4:
            return 'high'
        elif risk_factors >= 2:
            return 'medium'
        else:
            return 'low'
    
    def identify_opportunity_zones(self, propagation_map, force_summary):
        """Identify potential opportunity zones"""
        
        opportunities = []
        
        # Look for positive force propagation
        for force_name, prop_data in propagation_map.items():
            for effect in prop_data['propagation_chain']:
                if effect['predicted_impact'] > 0.5:
                    opportunities.append({
                        'zone': effect['category'],
                        'source_force': force_name,
                        'strength': effect['strength'],
                        'lag': effect['lag_periods'],
                        'type': 'momentum'
                    })
        
        # Look for contrarian opportunities (oversold categories)
        for category, summary in force_summary.items():
            if summary['net_strength'] < -1.0 and summary['active_forces'] >= 2:
                opportunities.append({
                    'zone': category,
                    'source_force': 'contrarian',
                    'strength': abs(summary['net_strength']),
                    'lag': 1,
                    'type': 'contrarian'
                })
        
        # Sort by strength
        opportunities.sort(key=lambda x: x['strength'], reverse=True)
        
        return opportunities[:5]  # Top 5 opportunities
    
    def compute_market_pulse(self):
        """Compute complete market pulse"""
        
        print("💓 COMPUTING MARKET PULSE")
        print("=" * 60)
        
        # Load all components
        components = self.load_market_brain_components()
        
        # Check if we have minimum required data
        if components['tensor'].empty:
            print("❌ Cannot compute pulse without market tensor")
            return False
        
        # Step 1: Detect dominant forces
        dominant_forces = self.detect_dominant_forces(components['tensor'])
        
        # Step 2: Trace force propagation
        propagation_map = self.trace_force_propagation(
            dominant_forces, 
            components['causality'], 
            components['graph']
        )
        
        # Step 3: Match current regime
        regime_info = self.match_current_regime(
            components['tensor'], 
            components['regimes']
        )
        
        # Step 4: Synthesize pulse
        pulse_state = self.synthesize_market_pulse(
            dominant_forces, 
            propagation_map, 
            regime_info
        )
        
        # Step 5: Save pulse state
        self.save_pulse_state(pulse_state)
        
        print("\n✅ Market pulse computed successfully!")
        print(f"   Pulse intensity: {pulse_state['pulse_intensity']:.2f}")
        print(f"   Market phase: {pulse_state['market_phase']}")
        print(f"   Risk level: {pulse_state['risk_level']}")
        print(f"   Active forces: {len(pulse_state['dominant_forces'])}")
        
        return True
    
    def save_pulse_state(self, pulse_state):
        """Save current pulse state"""
        
        # Create output directory
        os.makedirs(os.path.dirname(self.paths['pulse_state']), exist_ok=True)
        
        # Save pulse state JSON
        with open(self.paths['pulse_state'], 'w') as f:
            json.dump(pulse_state, f, indent=2)
        print(f"💾 Saved pulse state: {self.paths['pulse_state']}")
        
        # Create pulse metrics DataFrame for time series
        pulse_metrics = pd.DataFrame([{
            'date': pd.Timestamp.now(),
            'pulse_intensity': pulse_state['pulse_intensity'],
            'market_phase': pulse_state['market_phase'],
            'risk_level': pulse_state['risk_level'],
            'n_dominant_forces': len(pulse_state['dominant_forces']),
            'n_pulse_signals': len(pulse_state['pulse_signals']),
            'regime_similarity': pulse_state['regime_info'].get('current_regime', {}).get('similarity', 0.0)
        }])
        
        # Append to pulse history
        if os.path.exists(self.paths['pulse_history']):
            existing_history = pd.read_parquet(self.paths['pulse_history'])
            pulse_history = pd.concat([existing_history, pulse_metrics], ignore_index=True)
        else:
            pulse_history = pulse_metrics
        
        # Keep only recent history (last 1000 records)
        pulse_history = pulse_history.tail(1000)
        
        pulse_history.to_parquet(self.paths['pulse_history'])
        print(f"💾 Updated pulse history: {len(pulse_history)} records")
    
    def load_pulse_state(self):
        """Load current pulse state"""
        
        try:
            if os.path.exists(self.paths['pulse_state']):
                with open(self.paths['pulse_state'], 'r') as f:
                    pulse_state = json.load(f)
                print(f"📊 Loaded pulse state from {pulse_state['timestamp']}")
                return pulse_state
        except Exception as e:
            print(f"⚠️ Could not load pulse state: {e}")
        
        return {}
    
    def get_pulse_summary(self):
        """Get summary of current market pulse"""
        
        pulse_state = self.load_pulse_state()
        
        if not pulse_state:
            return "Market pulse not available"
        
        summary = f"""
Market Pulse Summary:
- Phase: {pulse_state.get('market_phase', 'unknown').title()}
- Risk Level: {pulse_state.get('risk_level', 'unknown').title()}
- Pulse Intensity: {pulse_state.get('pulse_intensity', 0):.2f}
- Active Forces: {len(pulse_state.get('dominant_forces', {}))}
- Narrative: {pulse_state.get('pulse_narrative', 'No narrative available')}
        """.strip()
        
        return summary

def main():
    """Compute market pulse"""
    
    engine = MarketPulseEngine()
    success = engine.compute_market_pulse()
    
    if success:
        print(f"\n🎯 Market pulse ready for survival instincts!")
        print(f"   Next step: Build survival instinct system")
        return True
    else:
        print("❌ Failed to compute market pulse")
        return False

if __name__ == "__main__":
    main()
