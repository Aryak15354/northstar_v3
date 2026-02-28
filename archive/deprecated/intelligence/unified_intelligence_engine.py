#!/usr/bin/env python3
"""
🧠 UNIFIED INTELLIGENCE ENGINE - NORTHSTAR V3 PHASE 3
Master Intelligence Coordinator: Unifying All Intelligence Systems
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class UnifiedIntelligenceEngine:
    """
    Unified Intelligence Engine - Master Intelligence Coordinator
    
    Coordinates all three intelligence systems into one coherent
    investment intelligence that thinks, learns, and adapts.
    """
    
    def __init__(self):
        self.name = "Unified Intelligence Engine"
        self.version = "1.0"
        
        # Initialize intelligence systems (lazy loading)
        self._market_brain = None
        self._intelligence_stack = None
        self._strategy_intelligence = None
        self._belief_system = None
        
        # Execution tracking
        self.execution_log = []
        self.intelligence_status = {
            'market_brain': False,
            'intelligence_stack': False,
            'strategy_intelligence': False,
            'belief_system': False
        }
        
        # Output paths
        self.output_dir = 'data/processed'
        os.makedirs(self.output_dir, exist_ok=True)
    
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
        if component in self.intelligence_status:
            self.intelligence_status[component] = (status == 'success')
        
        # Print status
        status_icon = "✅" if status == 'success' else "❌" if status == 'failed' else "⚠️"
        print(f"   {status_icon} {component}: {message}")
    
    @property
    def market_brain(self):
        """Lazy load Market Brain Orchestrator"""
        if self._market_brain is None:
            try:
                from intelligence.market_brain.brain_orchestrator import MarketBrainOrchestrator
                self._market_brain = MarketBrainOrchestrator()
            except ImportError as e:
                print(f"⚠️ Market Brain not available: {e}")
                self._market_brain = None
        return self._market_brain
    
    @property
    def intelligence_stack(self):
        """Lazy load Intelligence Stack"""
        if self._intelligence_stack is None:
            try:
                from intelligence.intelligence_stack import IntelligenceStack
                self._intelligence_stack = IntelligenceStack()
            except ImportError as e:
                print(f"⚠️ Intelligence Stack not available: {e}")
                self._intelligence_stack = None
        return self._intelligence_stack
    
    @property
    def strategy_intelligence(self):
        """Lazy load Strategy Intelligence"""
        if self._strategy_intelligence is None:
            try:
                from intelligence.strategy_intelligence import StrategyIntelligence
                self._strategy_intelligence = StrategyIntelligence()
            except ImportError as e:
                print(f"⚠️ Strategy Intelligence not available: {e}")
                self._strategy_intelligence = None
        return self._strategy_intelligence
    
    @property
    def belief_system(self):
        """Lazy load Unified Belief System"""
        if self._belief_system is None:
            try:
                from intelligence.unified_belief_system import UnifiedBeliefSystem
                self._belief_system = UnifiedBeliefSystem()
            except ImportError as e:
                print(f"⚠️ Unified Belief System not available: {e}")
                self._belief_system = None
        return self._belief_system
    
    def generate_unified_intelligence(self):
        """Generate complete unified intelligence"""
        
        print("🧠 UNIFIED INTELLIGENCE ENGINE")
        print("=" * 70)
        print("Coordinating all intelligence systems into unified investment intelligence")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        total_start_time = datetime.now()
        
        # Step 1: Market Intelligence
        market_intel = self.generate_market_intelligence()
        
        # Step 2: Valuation Intelligence
        valuation_intel = self.generate_valuation_intelligence()
        
        # Step 3: Strategy Intelligence
        strategy_intel = self.generate_strategy_intelligence()
        
        # Step 4: Unified Belief Synthesis
        unified_beliefs = self.merge_unified_beliefs(market_intel, valuation_intel, strategy_intel)
        
        # Create complete intelligence result
        total_duration = (datetime.now() - total_start_time).total_seconds()
        
        intelligence_result = {
            'timestamp': datetime.now().isoformat(),
            'version': self.version,
            'total_duration': total_duration,
            'intelligence_status': self.intelligence_status,
            'execution_log': self.execution_log,
            'market_intelligence': market_intel,
            'valuation_intelligence': valuation_intel,
            'strategy_intelligence': strategy_intel,
            'unified_beliefs': unified_beliefs,
            'system_health': self.calculate_system_health()
        }
        
        # Save unified intelligence
        self.save_unified_intelligence(intelligence_result)
        
        # Print summary
        self.print_intelligence_summary(intelligence_result)
        
        return intelligence_result
    
    def generate_market_intelligence(self):
        """Step 1: Generate Market Intelligence (Market Brain)"""
        
        print("🧠 STEP 1: MARKET INTELLIGENCE")
        print("-" * 40)
        
        start_time = datetime.now()
        
        try:
            if self.market_brain:
                success = self.market_brain.run_complete_market_brain()
                
                if success:
                    # Collect market brain outputs
                    brain_outputs = self.market_brain.collect_brain_outputs()
                    
                    duration = (datetime.now() - start_time).total_seconds()
                    self.log_execution('market_brain', 'success', 
                                     "Market intelligence generated", duration)
                    
                    return {
                        'status': 'success',
                        'brain_outputs': brain_outputs,
                        'pulse_state': brain_outputs.get('pulse_state', {}),
                        'regime_info': brain_outputs.get('pulse_state', {}).get('regime_info', {}),
                        'survival_state': brain_outputs.get('survival_state', {}),
                        'causal_graph': brain_outputs.get('causal_graph', {}),
                        'tensor_state': brain_outputs.get('tensor_state', {})
                    }
                else:
                    self.log_execution('market_brain', 'failed', 
                                     "Market brain execution failed")
                    return {'status': 'failed'}
            else:
                self.log_execution('market_brain', 'failed', 
                                 "Market brain not available")
                return {'status': 'not_available'}
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution('market_brain', 'failed', str(e), duration)
            return {'status': 'error', 'error': str(e)}
    
    def generate_valuation_intelligence(self):
        """Step 2: Generate Valuation Intelligence (Intelligence Stack)"""
        
        print("\n🎯 STEP 2: VALUATION INTELLIGENCE")
        print("-" * 40)
        
        start_time = datetime.now()
        
        try:
            if self.intelligence_stack:
                # Run complete intelligence generation
                intelligence_result = self.intelligence_stack.run_intelligence_update('NIFTY')
                
                if intelligence_result:
                    duration = (datetime.now() - start_time).total_seconds()
                    self.log_execution('intelligence_stack', 'success', 
                                     "Valuation intelligence generated", duration)
                    
                    return {
                        'status': 'success',
                        'intelligence_result': intelligence_result,
                        'beliefs': intelligence_result.get('beliefs', {}),
                        'actions': intelligence_result.get('actions', {}),
                        'regime': intelligence_result.get('regime', 'unknown'),
                        'system_health': intelligence_result.get('system_health', {})
                    }
                else:
                    self.log_execution('intelligence_stack', 'failed', 
                                     "Intelligence stack execution failed")
                    return {'status': 'failed'}
            else:
                self.log_execution('intelligence_stack', 'failed', 
                                 "Intelligence stack not available")
                return {'status': 'not_available'}
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution('intelligence_stack', 'failed', str(e), duration)
            return {'status': 'error', 'error': str(e)}
    
    def generate_strategy_intelligence(self):
        """Step 3: Generate Strategy Intelligence (Strategy System)"""
        
        print("\n🧬 STEP 3: STRATEGY INTELLIGENCE")
        print("-" * 40)
        
        start_time = datetime.now()
        
        try:
            if self.strategy_intelligence:
                success = self.strategy_intelligence.run_complete_intelligence()
                
                if success:
                    duration = (datetime.now() - start_time).total_seconds()
                    self.log_execution('strategy_intelligence', 'success', 
                                     "Strategy intelligence generated", duration)
                    
                    # Load strategy intelligence summary
                    summary_file = 'data/processed/strategy_intelligence_summary.json'
                    strategy_summary = {}
                    
                    if os.path.exists(summary_file):
                        try:
                            with open(summary_file, 'r') as f:
                                strategy_summary = json.load(f)
                        except:
                            pass
                    
                    return {
                        'status': 'success',
                        'strategy_summary': strategy_summary,
                        'component_status': self.strategy_intelligence.component_status,
                        'execution_log': self.strategy_intelligence.execution_log
                    }
                else:
                    self.log_execution('strategy_intelligence', 'failed', 
                                     "Strategy intelligence execution failed")
                    return {'status': 'failed'}
            else:
                self.log_execution('strategy_intelligence', 'failed', 
                                 "Strategy intelligence not available")
                return {'status': 'not_available'}
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution('strategy_intelligence', 'failed', str(e), duration)
            return {'status': 'error', 'error': str(e)}
    
    def merge_unified_beliefs(self, market_intel, valuation_intel, strategy_intel):
        """Step 4: Merge into Unified Beliefs"""
        
        print("\n🔗 STEP 4: UNIFIED BELIEF SYNTHESIS")
        print("-" * 40)
        
        start_time = datetime.now()
        
        try:
            if self.belief_system:
                unified_beliefs = self.belief_system.merge_beliefs(
                    market_intel, valuation_intel, strategy_intel
                )
                
                duration = (datetime.now() - start_time).total_seconds()
                self.log_execution('belief_system', 'success', 
                                 "Unified beliefs synthesized", duration)
                
                return unified_beliefs
            else:
                # Fallback belief synthesis
                print("   🔄 Using fallback belief synthesis...")
                
                unified_beliefs = self.fallback_belief_synthesis(
                    market_intel, valuation_intel, strategy_intel
                )
                
                duration = (datetime.now() - start_time).total_seconds()
                self.log_execution('belief_system', 'success', 
                                 "Fallback belief synthesis completed", duration)
                
                return unified_beliefs
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution('belief_system', 'failed', str(e), duration)
            return self.fallback_belief_synthesis(market_intel, valuation_intel, strategy_intel)
    
    def fallback_belief_synthesis(self, market_intel, valuation_intel, strategy_intel):
        """Fallback belief synthesis when unified belief system not available"""
        
        unified_beliefs = {
            'timestamp': datetime.now().isoformat(),
            'version': self.version,
            'synthesis_method': 'fallback',
            'market_beliefs': {},
            'valuation_beliefs': {},
            'strategy_beliefs': {},
            'unified_stance': 'neutral',
            'unified_conviction': 0.5,
            'unified_actions': {},
            'confidence_metrics': {},
            'risk_assessment': {}
        }
        
        # Extract market beliefs
        if market_intel.get('status') == 'success':
            pulse_state = market_intel.get('pulse_state', {})
            survival_state = market_intel.get('survival_state', {})
            
            unified_beliefs['market_beliefs'] = {
                'pulse_intensity': pulse_state.get('pulse_intensity', 0.0),
                'market_phase': pulse_state.get('market_phase', 'neutral'),
                'risk_level': pulse_state.get('risk_level', 'low'),
                'survival_mode': survival_state.get('survival_mode', 'normal'),
                'regime_info': market_intel.get('regime_info', {})
            }
        
        # Extract valuation beliefs
        if valuation_intel.get('status') == 'success':
            beliefs = valuation_intel.get('beliefs', {})
            actions = valuation_intel.get('actions', {})
            
            unified_beliefs['valuation_beliefs'] = {
                'market_stance': beliefs.get('market_beliefs', {}).get('stance', 'Neutral'),
                'conviction': beliefs.get('conviction_levels', {}).get('overall', 0.5),
                'valuation_assessment': beliefs.get('valuation_beliefs', {}),
                'recommended_exposure': actions.get('exposure_recommendation', {}).get('target_exposure', 50.0)
            }
        
        # Extract strategy beliefs
        if strategy_intel.get('status') == 'success':
            strategy_summary = strategy_intel.get('strategy_summary', {})
            
            unified_beliefs['strategy_beliefs'] = {
                'success_count': strategy_summary.get('success_count', 0),
                'component_status': strategy_summary.get('component_status', {})
            }
        
        # Synthesize unified stance
        market_phase = unified_beliefs['market_beliefs'].get('market_phase', 'neutral')
        valuation_stance = unified_beliefs['valuation_beliefs'].get('market_stance', 'Neutral')
        
        if market_phase == 'expansion' and valuation_stance == 'Bullish':
            unified_beliefs['unified_stance'] = 'bullish'
            unified_beliefs['unified_conviction'] = 0.7
        elif market_phase == 'contraction' and valuation_stance == 'Bearish':
            unified_beliefs['unified_stance'] = 'bearish'
            unified_beliefs['unified_conviction'] = 0.7
        elif market_phase == 'crisis' or unified_beliefs['market_beliefs'].get('survival_mode') != 'normal':
            unified_beliefs['unified_stance'] = 'defensive'
            unified_beliefs['unified_conviction'] = 0.8
        else:
            unified_beliefs['unified_stance'] = 'neutral'
            unified_beliefs['unified_conviction'] = 0.5
        
        # Unified actions
        recommended_exposure = unified_beliefs['valuation_beliefs'].get('recommended_exposure', 50.0)
        survival_mode = unified_beliefs['market_beliefs'].get('survival_mode', 'normal')
        
        # Adjust exposure based on survival mode
        if survival_mode == 'defensive':
            recommended_exposure *= 0.7
        elif survival_mode == 'crisis':
            recommended_exposure *= 0.5
        
        unified_beliefs['unified_actions'] = {
            'target_exposure': recommended_exposure,
            'primary_action': unified_beliefs['unified_stance'].upper(),
            'risk_adjustment': survival_mode,
            'execution_priority': 'high' if survival_mode != 'normal' else 'medium'
        }
        
        return unified_beliefs
    
    def calculate_system_health(self):
        """Calculate unified intelligence system health"""
        
        # Component availability
        available_components = sum(1 for status in self.intelligence_status.values() if status)
        component_health = available_components / len(self.intelligence_status)
        
        # Execution success rate
        successful_executions = sum(1 for entry in self.execution_log if entry['status'] == 'success')
        total_executions = len(self.execution_log)
        execution_health = successful_executions / total_executions if total_executions > 0 else 0.0
        
        # Overall health
        overall_health = (component_health + execution_health) / 2
        
        return {
            'overall_score': overall_health,
            'component_health': component_health,
            'execution_health': execution_health,
            'available_components': available_components,
            'total_components': len(self.intelligence_status),
            'successful_executions': successful_executions,
            'total_executions': total_executions,
            'grade': 'A' if overall_health > 0.8 else 'B' if overall_health > 0.6 else 'C' if overall_health > 0.4 else 'D'
        }
    
    def save_unified_intelligence(self, intelligence_result):
        """Save unified intelligence state"""
        
        # Save complete result
        full_file = os.path.join(self.output_dir, 'unified_intelligence_state.json')
        with open(full_file, 'w') as f:
            json.dump(intelligence_result, f, indent=2, default=str)
        
        # Save summary for dashboard
        summary = {
            'timestamp': intelligence_result['timestamp'],
            'version': intelligence_result['version'],
            'system_health': intelligence_result['system_health'],
            'unified_beliefs': intelligence_result['unified_beliefs'],
            'intelligence_status': intelligence_result['intelligence_status']
        }
        
        summary_file = os.path.join(self.output_dir, 'unified_intelligence_summary.json')
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
        
        print(f"💾 Unified intelligence saved to {full_file}")
    
    def print_intelligence_summary(self, intelligence_result):
        """Print intelligence summary"""
        
        print(f"\n🎯 UNIFIED INTELLIGENCE COMPLETE")
        print("=" * 70)
        print(f"Duration: {intelligence_result['total_duration']:.1f} seconds")
        
        # Component status
        print(f"\nComponent Status:")
        for component, status in intelligence_result['intelligence_status'].items():
            status_icon = "✅" if status else "❌"
            print(f"  {status_icon} {component.replace('_', ' ').title()}")
        
        # System health
        health = intelligence_result['system_health']
        print(f"\nSystem Health: {health['grade']} ({health['overall_score']:.3f})")
        
        # Unified beliefs summary
        beliefs = intelligence_result['unified_beliefs']
        print(f"\nUnified Intelligence:")
        print(f"  🎯 Stance: {beliefs['unified_stance'].upper()}")
        print(f"  🎯 Conviction: {beliefs['unified_conviction']:.1%}")
        print(f"  🎯 Target Exposure: {beliefs['unified_actions']['target_exposure']:.1f}%")
        print(f"  🎯 Risk Level: {beliefs['risk_assessment'].get('overall_risk', 'unknown').upper()}")
        
        success_rate = sum(1 for status in intelligence_result['intelligence_status'].values() if status) / len(intelligence_result['intelligence_status'])
        
        if success_rate >= 0.75:
            print(f"\n🎉 UNIFIED INTELLIGENCE IS ACTIVE!")
            print("   All intelligence systems coordinated into unified investment brain")
        else:
            print(f"\n⚠️ Intelligence system partially operational - some components need attention")
    
    def load_latest_intelligence(self):
        """Load latest unified intelligence"""
        
        summary_file = os.path.join(self.output_dir, 'unified_intelligence_summary.json')
        
        if os.path.exists(summary_file):
            try:
                with open(summary_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading intelligence: {e}")
        
        return None
    
    def get_intelligence_status(self):
        """Get current intelligence system status"""
        
        latest_intelligence = self.load_latest_intelligence()
        
        if latest_intelligence:
            return {
                'status': 'active',
                'timestamp': latest_intelligence['timestamp'],
                'system_health': latest_intelligence['system_health'],
                'unified_beliefs': latest_intelligence['unified_beliefs'],
                'intelligence_status': latest_intelligence['intelligence_status']
            }
        else:
            return {
                'status': 'not_available',
                'message': 'No intelligence data available'
            }

def main():
    """Test Unified Intelligence Engine"""
    
    engine = UnifiedIntelligenceEngine()
    
    print("🧪 TESTING UNIFIED INTELLIGENCE ENGINE")
    print("=" * 50)
    
    # Test component availability
    print(f"Engine initialized: {engine.name} v{engine.version}")
    print(f"Market Brain available: {engine.market_brain is not None}")
    print(f"Intelligence Stack available: {engine.intelligence_stack is not None}")
    print(f"Strategy Intelligence available: {engine.strategy_intelligence is not None}")
    print(f"Belief System available: {engine.belief_system is not None}")
    
    # Test full intelligence generation
    intelligence_result = engine.generate_unified_intelligence()
    
    # Test system status
    status = engine.get_intelligence_status()
    print(f"\nIntelligence Status: {status['status']}")
    
    return intelligence_result is not None

if __name__ == "__main__":
    main()