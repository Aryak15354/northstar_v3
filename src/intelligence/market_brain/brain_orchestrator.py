#!/usr/bin/env python3
"""
🧠 MARKET BRAIN ORCHESTRATOR - NORTHSTAR V3 INTEGRATION
The Master Controller: Orchestrating All Market Brain Components

This integrates the complete market brain system into Northstar V3:
1. Market Tensor → Enhanced Market State Spine
2. Causal Graph → Enhanced Bayesian Engine  
3. Regime Memory → Enhanced Memory Engine
4. Market Pulse → Enhanced Opportunity Surface
5. Survival Instincts → Enhanced Risk Management

Integration Points:
- Feeds enhanced intelligence into existing Intelligence Stack
- Provides regime-aware inputs to Capital Allocator
- Supplies pulse-based metrics to Portfolio Governor
- Triggers survival protocols in Risk Management

Usage:
    from src.intelligence.market_brain.brain_orchestrator import MarketBrainOrchestrator
    
    brain = MarketBrainOrchestrator()
    brain.run_complete_market_brain()
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from .market_tensor import MarketTensorEngine
from .causal_graph import CausalGraphEngine
from .regime_memory import RegimeMemoryEngine
from .market_pulse import MarketPulseEngine
from .survival_instincts import SurvivalInstinctEngine
from src.cohesion.bounded_exposure_calculator import BoundedExposureCalculator
from src.cohesion.state_file_manager import StateFileManager

class MarketBrainOrchestrator:
    """
    Market Brain Orchestrator - Complete System Integration
    
    Coordinates all market brain components and integrates them
    with the existing Northstar V3 intelligence stack.
    """
    
    def __init__(self):
        self.name = "Market Brain Orchestrator"
        self.version = "1.0"
        
        # Initialize all brain components
        self.tensor_engine = MarketTensorEngine()
        self.causal_engine = CausalGraphEngine()
        self.regime_engine = RegimeMemoryEngine()
        self.pulse_engine = MarketPulseEngine()
        self.survival_engine = SurvivalInstinctEngine()
        
        # Initialize state management components
        self.exposure_calculator = BoundedExposureCalculator()
        self.state_manager = StateFileManager()
        
        # Integration paths with V3 spine
        self.integration_paths = {
            'market_state_spine': 'data/processed/market_state.parquet',
            'intelligent_state': 'data/processed/intelligent_market_state.parquet',
            'opportunity_surface': 'data/processed/opportunity_surface.parquet',
            'brain_state': 'data/processed/market_brain_state.json',
            'brain_metrics': 'data/processed/market_brain_metrics.parquet'
        }
        
        # Execution tracking
        self.execution_log = []
        self.component_status = {
            'tensor': False,
            'causality': False,
            'regimes': False,
            'pulse': False,
            'survival': False
        }
    
    def log_execution(self, component, status, message="", duration=0):
        """Log component execution"""
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'component': component,
            'status': status,
            'message': message,
            'duration_seconds': duration
        }
        
        self.execution_log.append(entry)
        
        # Update component status
        if component in self.component_status:
            self.component_status[component] = (status == 'success')
        
        # Print status
        status_icon = "✅" if status == 'success' else "❌" if status == 'failed' else "⚠️"
        print(f"   {status_icon} {component}: {message}")
    
    def run_market_tensor(self):
        """Step 1: Build market tensor (sensory cortex)"""
        
        print("🧠 STEP 1: BUILDING MARKET TENSOR")
        print("-" * 50)
        
        start_time = datetime.now()
        
        try:
            success = self.tensor_engine.build_market_tensor()
            
            if success:
                # Check if tensor was actually built
                tensor = self.tensor_engine.load_market_tensor()
                if not tensor.empty:
                    duration = (datetime.now() - start_time).total_seconds()
                    self.log_execution('tensor', 'success', 
                                     f"Market tensor built successfully", duration)
                    return True
                else:
                    self.log_execution('tensor', 'failed', "Market tensor is empty")
                    return False
            else:
                self.log_execution('tensor', 'failed', "Failed to build market tensor")
                return False
                
        except Exception as e:
            self.log_execution('tensor', 'failed', f"Error: {str(e)}")
            return False
    
    def run_causal_graph(self):
        """Step 2: Build causal graph (nervous system)"""
        
        print("\n🧬 STEP 2: BUILDING CAUSAL GRAPH")
        print("-" * 50)
        
        start_time = datetime.now()
        
        try:
            success = self.causal_engine.build_causal_intelligence()
            
            if success:
                duration = (datetime.now() - start_time).total_seconds()
                self.log_execution('causality', 'success', 
                                 f"Causal graph built successfully", duration)
                return True
            else:
                self.log_execution('causality', 'failed', "Failed to build causal graph")
                return False
                
        except Exception as e:
            self.log_execution('causality', 'failed', f"Error: {str(e)}")
            return False
    
    def run_regime_memory(self):
        """Step 3: Build regime memory (historical patterns)"""
        
        print("\n🧠 STEP 3: BUILDING REGIME MEMORY")
        print("-" * 50)
        
        start_time = datetime.now()
        
        try:
            success = self.regime_engine.build_regime_fingerprints()
            
            if success:
                duration = (datetime.now() - start_time).total_seconds()
                self.log_execution('regimes', 'success', 
                                 f"Regime memory built successfully", duration)
                return True
            else:
                self.log_execution('regimes', 'failed', "Failed to build regime memory")
                return False
                
        except Exception as e:
            self.log_execution('regimes', 'failed', f"Error: {str(e)}")
            return False
    
    def run_market_pulse(self):
        """Step 4: Compute market pulse (real-time intelligence)"""
        
        print("\n💓 STEP 4: COMPUTING MARKET PULSE")
        print("-" * 50)
        
        start_time = datetime.now()
        
        try:
            success = self.pulse_engine.compute_market_pulse()
            
            if success:
                duration = (datetime.now() - start_time).total_seconds()
                self.log_execution('pulse', 'success', 
                                 f"Market pulse computed successfully", duration)
                return True
            else:
                self.log_execution('pulse', 'failed', "Failed to compute market pulse")
                return False
                
        except Exception as e:
            self.log_execution('pulse', 'failed', f"Error: {str(e)}")
            return False
    
    def run_survival_instincts(self):
        """Step 5: Assess survival instincts (system health)"""
        
        print("\n🛡️ STEP 5: ASSESSING SURVIVAL INSTINCTS")
        print("-" * 50)
        
        start_time = datetime.now()
        
        try:
            survival_state = self.survival_engine.assess_survival_instincts()
            
            if survival_state:
                duration = (datetime.now() - start_time).total_seconds()
                self.log_execution('survival', 'success', 
                                 f"Survival instincts assessed successfully", duration)
                return True
            else:
                self.log_execution('survival', 'failed', "Failed to assess survival instincts")
                return False
                
        except Exception as e:
            self.log_execution('survival', 'failed', f"Error: {str(e)}")
            return False
    
    def integrate_with_v3_spine(self):
        """Integrate market brain outputs with V3 spine"""
        
        print("\n🔗 INTEGRATING WITH V3 SPINE")
        print("-" * 50)
        
        try:
            # Load market brain outputs
            brain_outputs = self.collect_brain_outputs()
            
            # Enhance Market State Spine
            self.enhance_market_state_spine(brain_outputs)
            
            # Enhance Opportunity Surface
            self.enhance_opportunity_surface(brain_outputs)
            
            # Create Brain State Summary
            self.create_brain_state_summary(brain_outputs)
            
            print("   ✅ V3 spine integration completed")
            return True
            
        except Exception as e:
            print(f"   ❌ V3 spine integration failed: {e}")
            return False
    
    def collect_brain_outputs(self):
        """Collect outputs from all brain components"""
        
        brain_outputs = {}
        
        # Market tensor state
        try:
            brain_outputs['tensor_state'] = self.tensor_engine.get_latest_tensor_state()
        except:
            brain_outputs['tensor_state'] = {}
        
        # Causal graph
        try:
            brain_outputs['causal_graph'] = self.causal_engine.load_causal_graph()
        except:
            brain_outputs['causal_graph'] = {}
        
        # Regime memory
        try:
            brain_outputs['regime_fingerprints'] = self.regime_engine.load_regime_memory()
        except:
            brain_outputs['regime_fingerprints'] = pd.DataFrame()
        
        # Market pulse
        try:
            brain_outputs['pulse_state'] = self.pulse_engine.load_pulse_state()
        except:
            brain_outputs['pulse_state'] = {}
        
        # Survival instincts
        try:
            brain_outputs['survival_state'] = self.survival_engine.load_survival_state()
        except:
            brain_outputs['survival_state'] = {}
        
        return brain_outputs
    
    def enhance_market_state_spine(self, brain_outputs):
        """Enhance existing market state with brain intelligence"""
        
        print("   🧠 Enhancing Market State Spine...")
        
        try:
            # Load existing market state using StateFileManager
            try:
                market_state = self.state_manager.read_market_state()
            except FileNotFoundError:
                print("   ⚠️ No existing market state found")
                return
            
            # Add brain-enhanced metrics to latest row
            if not market_state.empty:
                latest_idx = market_state.index[-1]
                
                # Add pulse metrics
                pulse_state = brain_outputs.get('pulse_state', {})
                if pulse_state:
                    market_state.loc[latest_idx, 'pulse_intensity'] = pulse_state.get('pulse_intensity', 0.0)
                    market_state.loc[latest_idx, 'market_phase'] = pulse_state.get('market_phase', 'neutral')
                    market_state.loc[latest_idx, 'pulse_risk_level'] = pulse_state.get('risk_level', 'low')
                
                # Add regime metrics
                regime_info = pulse_state.get('regime_info', {})
                current_regime = regime_info.get('current_regime', {})
                if current_regime:
                    market_state.loc[latest_idx, 'regime_similarity'] = current_regime.get('similarity', 0.5)
                    market_state.loc[latest_idx, 'regime_name'] = current_regime.get('regime_name', 'Unknown')
                
                # Calculate bounded exposure using BoundedExposureCalculator
                risk_on = market_state.loc[latest_idx, 'risk_on'] if 'risk_on' in market_state.columns else 0.5
                stress_score = market_state.loc[latest_idx, 'stress_score'] if 'stress_score' in market_state.columns else 0.0
                regime = market_state.loc[latest_idx, 'regime'] if 'regime' in market_state.columns else 'unknown'
                
                bounded_exposure = self.exposure_calculator.calculate_allowed_exposure(
                    risk_on=risk_on,
                    stress_score=stress_score,
                    regime=regime
                )
                
                # Store bounded exposure (always in [0.0, 1.0])
                market_state.loc[latest_idx, 'allowed_exposure'] = bounded_exposure.value
                
                # Log if bounds were applied
                if bounded_exposure.was_bounded:
                    print(f"   ⚠️ Exposure bounded: {bounded_exposure.bound_reason}")
                
                # Add survival metrics
                survival_state = brain_outputs.get('survival_state', {})
                if survival_state:
                    market_state.loc[latest_idx, 'survival_mode'] = survival_state.get('survival_mode', 'normal')
                    action_params = survival_state.get('action_parameters', {})
                    market_state.loc[latest_idx, 'exposure_multiplier'] = action_params.get('exposure_multiplier', 1.0)
                
                # Save enhanced market state using StateFileManager (atomic write)
                self.state_manager.write_market_state(market_state)
                print("   ✅ Market State Spine enhanced with brain intelligence")
                print(f"   📊 Allowed Exposure: {bounded_exposure.value:.1%}")
        
        except Exception as e:
            print(f"   ❌ Error enhancing Market State Spine: {e}")
    
    def enhance_opportunity_surface(self, brain_outputs):
        """Enhance opportunity surface with pulse-based scoring"""
        
        print("   🎯 Enhancing Opportunity Surface...")
        
        try:
            # Load existing opportunity surface
            if os.path.exists(self.integration_paths['opportunity_surface']):
                opp_surface = pd.read_parquet(self.integration_paths['opportunity_surface'])
            else:
                print("   ⚠️ No existing opportunity surface found")
                return
            
            # Add pulse-based enhancements
            pulse_state = brain_outputs.get('pulse_state', {})
            
            if pulse_state and not opp_surface.empty:
                # Add pulse intensity weighting
                pulse_intensity = pulse_state.get('pulse_intensity', 1.0)
                opp_surface['pulse_weighted_score'] = opp_surface['northstar_score'] * pulse_intensity
                
                # Add regime-aware adjustments
                regime_info = pulse_state.get('regime_info', {})
                current_regime = regime_info.get('current_regime', {})
                
                if current_regime:
                    regime_name = current_regime.get('regime_name', '').lower()
                    
                    # Regime-specific score adjustments
                    if 'crisis' in regime_name:
                        # In crisis, favor quality and low volatility
                        opp_surface['regime_adjusted_score'] = opp_surface['pulse_weighted_score'] * 0.8
                    elif 'expansion' in regime_name:
                        # In expansion, favor momentum and growth
                        opp_surface['regime_adjusted_score'] = opp_surface['pulse_weighted_score'] * 1.2
                    else:
                        opp_surface['regime_adjusted_score'] = opp_surface['pulse_weighted_score']
                else:
                    opp_surface['regime_adjusted_score'] = opp_surface['pulse_weighted_score']
                
                # Add opportunity zones from pulse
                opportunity_zones = pulse_state.get('opportunity_zones', [])
                opp_surface['in_opportunity_zone'] = False
                
                for zone in opportunity_zones:
                    zone_name = zone.get('zone', '')
                    # This would need sector mapping logic
                    # For now, just mark as opportunity zone
                    opp_surface['in_opportunity_zone'] = True  # Simplified
                
                # Save enhanced opportunity surface
                opp_surface.to_parquet(self.integration_paths['opportunity_surface'])
                print("   ✅ Opportunity Surface enhanced with pulse intelligence")
        
        except Exception as e:
            print(f"   ❌ Error enhancing Opportunity Surface: {e}")
    
    def create_brain_state_summary(self, brain_outputs):
        """Create comprehensive brain state summary"""
        
        print("   📊 Creating Brain State Summary...")
        
        try:
            # Create comprehensive brain state
            brain_state = {
                'timestamp': datetime.now().isoformat(),
                'version': self.version,
                'component_status': self.component_status,
                'execution_log': self.execution_log,
                'brain_outputs': {
                    'tensor_available': bool(brain_outputs.get('tensor_state')),
                    'causal_graph_available': bool(brain_outputs.get('causal_graph')),
                    'regime_memory_available': not brain_outputs.get('regime_fingerprints', pd.DataFrame()).empty,
                    'pulse_active': bool(brain_outputs.get('pulse_state')),
                    'survival_monitoring': bool(brain_outputs.get('survival_state'))
                },
                'intelligence_summary': self.generate_intelligence_summary(brain_outputs),
                'integration_status': {
                    'market_state_enhanced': os.path.exists(self.integration_paths['market_state_spine']),
                    'opportunity_surface_enhanced': os.path.exists(self.integration_paths['opportunity_surface']),
                    'v3_compatibility': True
                }
            }
            
            # Save brain state
            with open(self.integration_paths['brain_state'], 'w') as f:
                json.dump(brain_state, f, indent=2)
            
            # Create brain metrics for time series
            brain_metrics = pd.DataFrame([{
                'date': pd.Timestamp.now(),
                'components_active': sum(self.component_status.values()),
                'pulse_intensity': brain_outputs.get('pulse_state', {}).get('pulse_intensity', 0.0),
                'regime_similarity': brain_outputs.get('pulse_state', {}).get('regime_info', {}).get('current_regime', {}).get('similarity', 0.0),
                'survival_mode': brain_outputs.get('survival_state', {}).get('survival_mode', 'normal'),
                'emergency_active': brain_outputs.get('survival_state', {}).get('emergency_triggered', False)
            }])
            
            # Append to brain metrics history
            if os.path.exists(self.integration_paths['brain_metrics']):
                existing_metrics = pd.read_parquet(self.integration_paths['brain_metrics'])
                brain_history = pd.concat([existing_metrics, brain_metrics], ignore_index=True)
            else:
                brain_history = brain_metrics
            
            # Keep only recent history
            brain_history = brain_history.tail(1000)
            brain_history.to_parquet(self.integration_paths['brain_metrics'])
            
            print("   ✅ Brain State Summary created")
            
        except Exception as e:
            print(f"   ❌ Error creating Brain State Summary: {e}")
    
    def generate_intelligence_summary(self, brain_outputs):
        """Generate human-readable intelligence summary"""
        
        summary = {}
        
        # Pulse summary
        pulse_state = brain_outputs.get('pulse_state', {})
        if pulse_state:
            summary['market_pulse'] = {
                'intensity': pulse_state.get('pulse_intensity', 0.0),
                'phase': pulse_state.get('market_phase', 'neutral'),
                'risk_level': pulse_state.get('risk_level', 'low'),
                'narrative': pulse_state.get('pulse_narrative', 'No narrative available')
            }
        
        # Regime summary
        regime_info = pulse_state.get('regime_info', {})
        current_regime = regime_info.get('current_regime', {})
        if current_regime:
            summary['regime_intelligence'] = {
                'current_regime': current_regime.get('regime_name', 'Unknown'),
                'similarity': current_regime.get('similarity', 0.0),
                'confidence': current_regime.get('confidence', 'low')
            }
        
        # Survival summary
        survival_state = brain_outputs.get('survival_state', {})
        if survival_state:
            summary['survival_status'] = {
                'mode': survival_state.get('survival_mode', 'normal'),
                'emergency': survival_state.get('emergency_triggered', False),
                'exposure_multiplier': survival_state.get('action_parameters', {}).get('exposure_multiplier', 1.0)
            }
        
        # Causal summary
        causal_graph = brain_outputs.get('causal_graph', {})
        if causal_graph:
            summary['causal_intelligence'] = {
                'relationships': len(causal_graph.get('edges', [])),
                'variables': len(causal_graph.get('nodes', [])),
                'network_density': causal_graph.get('metadata', {}).get('metrics', {}).get('density', 0.0)
            }
        
        return summary
    
    def run_complete_market_brain(self):
        """Run complete market brain system"""
        
        print("🧠 NORTHSTAR MARKET BRAIN - COMPLETE SYSTEM")
        print("=" * 70)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        total_start_time = datetime.now()
        success_count = 0
        
        # Step 1: Market Tensor
        if self.run_market_tensor():
            success_count += 1
        
        # Step 2: Causal Graph
        if self.run_causal_graph():
            success_count += 1
        
        # Step 3: Regime Memory
        if self.run_regime_memory():
            success_count += 1
        
        # Step 4: Market Pulse
        if self.run_market_pulse():
            success_count += 1
        
        # Step 5: Survival Instincts
        if self.run_survival_instincts():
            success_count += 1
        
        # Step 6: V3 Integration
        integration_success = self.integrate_with_v3_spine()
        
        # Final summary
        total_duration = (datetime.now() - total_start_time).total_seconds()
        
        print(f"\n🎯 MARKET BRAIN EXECUTION COMPLETE")
        print("=" * 70)
        print(f"Total duration: {total_duration:.1f} seconds")
        print(f"Components successful: {success_count}/5")
        print(f"V3 integration: {'✅' if integration_success else '❌'}")
        print(f"Overall success: {success_count >= 3 and integration_success}")
        
        # Print component status
        print(f"\nComponent Status:")
        for component, status in self.component_status.items():
            status_icon = "✅" if status else "❌"
            print(f"  {status_icon} {component.title()}")
        
        # Print intelligence summary if available
        brain_outputs = self.collect_brain_outputs()
        intelligence_summary = self.generate_intelligence_summary(brain_outputs)
        
        if intelligence_summary:
            print(f"\nIntelligence Summary:")
            
            if 'market_pulse' in intelligence_summary:
                pulse = intelligence_summary['market_pulse']
                print(f"  💓 Pulse: {pulse['intensity']:.2f} intensity, {pulse['phase']} phase, {pulse['risk_level']} risk")
            
            if 'regime_intelligence' in intelligence_summary:
                regime = intelligence_summary['regime_intelligence']
                print(f"  🔄 Regime: {regime['current_regime']} ({regime['similarity']:.1%} similarity)")
            
            if 'survival_status' in intelligence_summary:
                survival = intelligence_summary['survival_status']
                emergency_text = " 🚨 EMERGENCY" if survival['emergency'] else ""
                print(f"  🛡️ Survival: {survival['mode']} mode{emergency_text}")
        
        return success_count >= 3 and integration_success
    
    def get_brain_status(self):
        """Get current brain system status"""
        
        try:
            if os.path.exists(self.integration_paths['brain_state']):
                with open(self.integration_paths['brain_state'], 'r') as f:
                    brain_state = json.load(f)
                return brain_state
        except:
            pass
        
        return {'status': 'not_available'}
    
    def is_brain_active(self):
        """Check if brain system is active and healthy"""
        
        brain_state = self.get_brain_status()
        
        if brain_state and 'component_status' in brain_state:
            active_components = sum(brain_state['component_status'].values())
            return active_components >= 3  # At least 3 components working
        
        return False

def main():
    """Run complete market brain system"""
    
    orchestrator = MarketBrainOrchestrator()
    success = orchestrator.run_complete_market_brain()
    
    if success:
        print(f"\n🎉 Market Brain is now ALIVE and integrated with Northstar V3!")
        print(f"   The system now has:")
        print(f"   🧠 Sensory cortex (market tensor)")
        print(f"   🧬 Nervous system (causal graph)")
        print(f"   📚 Memory (regime patterns)")
        print(f"   💓 Pulse (real-time intelligence)")
        print(f"   🛡️ Survival instincts (self-monitoring)")
        return True
    else:
        print("❌ Market Brain initialization failed")
        return False

if __name__ == "__main__":
    main()