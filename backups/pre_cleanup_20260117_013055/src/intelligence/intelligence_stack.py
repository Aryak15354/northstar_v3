#!/usr/bin/env python3
"""
🧠 INTELLIGENCE STACK - INSTITUTIONAL GRADE INTEGRATION
Complete Intelligence System for Northstar V3

This integrates all intelligence components into one coherent system:
1. 4 Independent Valuation Engines
2. Confidence Weighting System  
3. Bayesian Contradiction Handler
4. 5 Jurors Narrative Engine
5. Memory & Learning System

This is the complete institutional-grade intelligence that transforms
Northstar from "a cool dashboard" to "a real investment brain."

Usage:
from src.cohesion.dependency_container import get_dependency_container
    from src.intelligence.intelligence_stack import IntelligenceStack
    
    intelligence = IntelligenceStack()
    result = intelligence.generate_complete_intelligence()
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import json
import warnings
warnings.filterwarnings('ignore')

# Import all intelligence components
try:
    from src.intelligence.valuation_engines import ValuationEngineStack
    from src.intelligence.confidence_engine import ConfidenceWeightedSignalProcessor
    from src.intelligence.bayesian_engine import BayesianSignalFusion, ContradictionResolver
    from src.intelligence.narrative_engine import NarrativeEngine
    from src.intelligence.memory_engine import MemoryEngine, LearningCoordinator
except ImportError:
    # Try relative imports if absolute imports fail
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from valuation_engines import ValuationEngineStack
    from confidence_engine import ConfidenceWeightedSignalProcessor
    from bayesian_engine import BayesianSignalFusion, ContradictionResolver
    from narrative_engine import NarrativeEngine
    from memory_engine import MemoryEngine, LearningCoordinator

# =========================== INTELLIGENCE STACK CORE ===========================

class IntelligenceStack:
    """
    Complete Institutional-Grade Intelligence System
    
    This is the master orchestrator that combines all intelligence components
    into one coherent system that thinks, learns, and adapts like a hedge fund.
    """
    
    def __init__(self):
        self.name = "Northstar Intelligence Stack"
        self.version = "3.0"
        
        # Initialize all intelligence components
        self.valuation_engines = ValuationEngineStack()
        self.confidence_processor = ConfidenceWeightedSignalProcessor()
        self.bayesian_fusion = BayesianSignalFusion()
        self.contradiction_resolver = ContradictionResolver()
        self.narrative_engine = NarrativeEngine()
        self.memory_engine = MemoryEngine()
        self.learning_coordinator = LearningCoordinator()
        
        # Intelligence state
        self.current_regime = None
        self.current_beliefs = {}
        self.current_conviction = 0.0
        self.adaptive_weights = {}
        
        # Output paths
        self.output_dir = 'data/intelligence'
        os.makedirs(self.output_dir, exist_ok=True)
    
    def generate_complete_intelligence(self, ticker=None, market_data=None):
        """
        Generate complete institutional-grade intelligence
        
        This is the main function that orchestrates all intelligence components
        """
        
        print("🧠 GENERATING COMPLETE INSTITUTIONAL-GRADE INTELLIGENCE")
        print("=" * 70)
        
        intelligence_result = {
            'timestamp': datetime.now(),
            'ticker': ticker,
            'system_version': self.version,
            'components': {},
            'synthesis': {},
            'beliefs': {},
            'actions': {},
            'learning': {}
        }
        
        # Step 1: Detect Market Regime
        print("1️⃣ Detecting market regime...")
        regime = self.detect_market_regime(market_data)
        self.current_regime = regime
        intelligence_result['regime'] = regime
        print(f"   Current regime: {regime.upper()}")
        
        # Step 2: Generate 4-Engine Valuation Analysis
        if ticker:
            print("2️⃣ Running 4-engine valuation analysis...")
            valuation_result = self.valuation_engines.compute_all_valuations(ticker)
            intelligence_result['components']['valuation'] = valuation_result
            print(f"   Composite valuation z-score: {valuation_result['synthesis']['composite_z_score']:.3f}")
        
        # Step 3: Apply Confidence Weighting
        print("3️⃣ Applying confidence weighting...")
        confidence_results = self.apply_confidence_weighting(intelligence_result)
        intelligence_result['components']['confidence'] = confidence_results
        
        # Step 4: Generate Market Narrative (5 Jurors)
        print("4️⃣ Generating market narrative from 5 jurors...")
        narrative_result = self.narrative_engine.generate_market_narrative(market_data)
        intelligence_result['components']['narrative'] = narrative_result
        print(f"   Market stance: {narrative_result['market_stance']} "
              f"(conviction: {narrative_result['conviction']:.3f})")
        
        # Step 5: Resolve Contradictions with Bayesian Fusion
        print("5️⃣ Resolving contradictions with Bayesian fusion...")
        contradiction_result = self.resolve_contradictions(intelligence_result)
        intelligence_result['components']['bayesian'] = contradiction_result
        
        # Step 6: Apply Memory & Learning
        print("6️⃣ Applying memory & learning...")
        learning_result = self.apply_learning(intelligence_result)
        intelligence_result['learning'] = learning_result
        
        # Step 7: Synthesize Final Beliefs
        print("7️⃣ Synthesizing final beliefs...")
        beliefs = self.synthesize_beliefs(intelligence_result)
        intelligence_result['beliefs'] = beliefs
        self.current_beliefs = beliefs
        
        # Step 8: Generate Actions
        print("8️⃣ Generating actionable recommendations...")
        actions = self.generate_actions(intelligence_result)
        intelligence_result['actions'] = actions
        
        # Step 9: Save Intelligence State
        self.save_intelligence_state(intelligence_result)
        
        print("✅ Complete intelligence generation finished")
        return intelligence_result
    
    def detect_market_regime(self, market_data=None):
        """Detect current market regime using multiple signals"""
        
        # Use Bayesian engine's regime detection
        regime = self.bayesian_fusion.detect_market_regime(market_data)
        
        # Enhance with additional logic if needed
        if market_data:
            macro_score = market_data.get('macro_score', 0.0)
            breadth_pct = market_data.get('breadth_pct', 50.0)
            
            # Override logic for extreme conditions
            if macro_score < -1.5 and breadth_pct < 30:
                regime = 'bear'
            elif macro_score > 1.5 and breadth_pct > 70:
                regime = 'bull'
        
        return regime
    
    def apply_confidence_weighting(self, intelligence_result):
        """Apply confidence weighting to all signals"""
        
        confidence_results = {
            'processed_signals': {},
            'overall_confidence': 0.0,
            'reliability_assessment': {}
        }
        
        # Process valuation signals if available
        if 'valuation' in intelligence_result.get('components', {}):
            valuation_data = intelligence_result['components']['valuation']
            
            for engine_name, engine_result in valuation_data['engines'].items():
                signal_data = {
                    'engine_type': engine_name,
                    'z_score': engine_result.get('z_score', 0.0),
                    'confidence': engine_result.get('confidence', 0.5),
                    'data': engine_result,
                    'timestamp': datetime.now()
                }
                
                processed_signal = self.confidence_processor.process_valuation_signal(signal_data)
                confidence_results['processed_signals'][engine_name] = processed_signal
        
        # Calculate overall confidence
        if confidence_results['processed_signals']:
            confidences = [s['confidence'] for s in confidence_results['processed_signals'].values()]
            confidence_results['overall_confidence'] = np.mean(confidences)
        
        return confidence_results
    
    def resolve_contradictions(self, intelligence_result):
        """Resolve contradictions using Bayesian fusion"""
        
        # Extract signals for contradiction analysis
        signals = {}
        
        # Valuation signals
        if 'valuation' in intelligence_result.get('components', {}):
            valuation_synthesis = intelligence_result['components']['valuation']['synthesis']
            signals['valuation'] = valuation_synthesis['composite_z_score']
        
        # Narrative signals
        if 'narrative' in intelligence_result.get('components', {}):
            narrative_data = intelligence_result['components']['narrative']
            # Convert narrative votes to signal
            total_votes = narrative_data['total_votes']
            num_jurors = len(narrative_data['juror_votes'])
            signals['narrative'] = total_votes / num_jurors if num_jurors > 0 else 0
        
        # Market state signals (if available)
        try:
            # Try to load market state using the parent class method
            from src.cohesion.unified_state_manager import UnifiedStateManager
            basic_engine = UnifiedStateManager()
            market_state = basic_engine.compute_market_state()
            signals['macro'] = market_state.get('macro_score', 0.0)
            signals['momentum'] = market_state.get('macro_momentum', 0.0)
        except Exception as e:
            print(f"   Could not load market state: {e}")
            pass
        
        # Resolve contradictions if we have multiple signals
        if len(signals) > 1:
            fusion_result = self.bayesian_fusion.fuse_contradictory_signals(
                signals, regime=self.current_regime
            )
            
            # Analyze specific contradictions
            contradictions = self.bayesian_fusion.analyze_signal_contradictions(signals)
            
            return {
                'signals_analyzed': signals,
                'fusion_result': fusion_result,
                'contradictions': contradictions,
                'resolution_method': 'bayesian_fusion'
            }
        else:
            return {
                'signals_analyzed': signals,
                'resolution_method': 'insufficient_signals'
            }
    
    def apply_learning(self, intelligence_result):
        """Apply memory and learning to intelligence"""
        
        # Get adaptive weights based on historical performance
        adaptive_weights = self.memory_engine.get_adaptive_weights(self.current_regime)
        self.adaptive_weights = adaptive_weights
        
        # Get learning summary
        learning_summary = self.memory_engine.get_learning_summary()
        
        # Calculate conditional probabilities for current scenario
        conditional_probs = self.memory_engine.calculate_conditional_probabilities(self.current_regime)
        
        return {
            'adaptive_weights': adaptive_weights,
            'learning_summary': learning_summary,
            'conditional_probabilities': conditional_probs,
            'regime': self.current_regime
        }
    
    def synthesize_beliefs(self, intelligence_result):
        """
        Synthesize all intelligence into coherent beliefs
        
        This is where all the intelligence comes together into actionable beliefs
        """
        
        beliefs = {
            'timestamp': datetime.now(),
            'regime': self.current_regime,
            'market_beliefs': {},
            'valuation_beliefs': {},
            'conviction_levels': {},
            'uncertainty_factors': []
        }
        
        # Market beliefs from narrative
        if 'narrative' in intelligence_result.get('components', {}):
            narrative = intelligence_result['components']['narrative']
            beliefs['market_beliefs'] = {
                'stance': narrative['market_stance'],
                'conviction': narrative['conviction'],
                'key_themes': narrative['key_themes'],
                'juror_consensus': narrative['agreement_analysis']['consensus_strength']
            }
        
        # Valuation beliefs
        if 'valuation' in intelligence_result.get('components', {}):
            valuation = intelligence_result['components']['valuation']['synthesis']
            beliefs['valuation_beliefs'] = {
                'composite_assessment': valuation.get('status', 'unknown'),
                'confidence': valuation.get('composite_confidence', 0.5),
                'agreement': valuation.get('agreement', 0.5),
                'narrative': valuation.get('narrative', 'No valuation narrative available')
            }
        
        # Conviction levels by component
        beliefs['conviction_levels'] = {
            'valuation': beliefs.get('valuation_beliefs', {}).get('confidence', 0.5),
            'narrative': beliefs.get('market_beliefs', {}).get('conviction', 0.5),
            'overall': 0.0
        }
        
        # Calculate overall conviction
        convictions = [c for c in beliefs['conviction_levels'].values() if c > 0]
        if convictions:
            beliefs['conviction_levels']['overall'] = np.mean(convictions)
        
        # Identify uncertainty factors
        if beliefs['conviction_levels']['overall'] < 0.6:
            beliefs['uncertainty_factors'].append("Low overall conviction")
        
        if 'bayesian' in intelligence_result.get('components', {}):
            contradictions = intelligence_result['components']['bayesian'].get('contradictions', [])
            if contradictions:
                beliefs['uncertainty_factors'].append(f"{len(contradictions)} signal contradictions")
        
        return beliefs
    
    def generate_actions(self, intelligence_result):
        """
        Generate specific actionable recommendations
        
        This translates beliefs into portfolio actions
        """
        
        actions = {
            'timestamp': datetime.now(),
            'primary_action': None,
            'exposure_recommendation': None,
            'sector_allocation': {},
            'risk_management': {},
            'execution_priority': 'medium',
            'reasoning': []
        }
        
        # Get beliefs
        beliefs = intelligence_result.get('beliefs', {})
        
        # Primary action from market stance
        market_stance = beliefs.get('market_beliefs', {}).get('stance', 'Neutral')
        overall_conviction = beliefs.get('conviction_levels', {}).get('overall', 0.5)
        
        if market_stance == 'Bullish' and overall_conviction > 0.6:
            actions['primary_action'] = 'INCREASE_EXPOSURE'
            base_exposure = 60
        elif market_stance == 'Bearish' and overall_conviction > 0.6:
            actions['primary_action'] = 'DECREASE_EXPOSURE'
            base_exposure = 30
        else:
            actions['primary_action'] = 'MAINTAIN_EXPOSURE'
            base_exposure = 45
        
        # Adjust exposure by conviction
        conviction_multiplier = 0.7 + (overall_conviction * 0.6)  # 0.7 to 1.3 range
        recommended_exposure = base_exposure * conviction_multiplier
        
        # Apply regime constraints
        regime_limits = {'bull': 80, 'bear': 50, 'neutral': 65}
        max_exposure = regime_limits.get(self.current_regime, 65)
        recommended_exposure = min(recommended_exposure, max_exposure)
        
        actions['exposure_recommendation'] = {
            'target_exposure': recommended_exposure,
            'base_exposure': base_exposure,
            'conviction_multiplier': conviction_multiplier,
            'regime_limit': max_exposure
        }
        
        # Sector allocation from narrative
        if 'narrative' in intelligence_result.get('components', {}):
            narrative = intelligence_result['components']['narrative']
            
            # Extract sector preferences from juror details
            sector_preferences = {}
            for juror_name, details in narrative['juror_details'].items():
                if juror_name == 'flows':  # Flows juror has sector insights
                    # This would be enhanced with actual sector flow data
                    pass
            
            # Default sector allocation based on regime
            if self.current_regime == 'bull':
                actions['sector_allocation'] = {
                    'favor': ['Technology', 'Growth', 'Momentum'],
                    'avoid': ['Utilities', 'Defensives'],
                    'neutral': ['Financials', 'Industrials']
                }
            elif self.current_regime == 'bear':
                actions['sector_allocation'] = {
                    'favor': ['Utilities', 'Consumer Staples', 'Quality'],
                    'avoid': ['Technology', 'Speculative Growth'],
                    'neutral': ['Healthcare', 'Telecom']
                }
            else:
                actions['sector_allocation'] = {
                    'favor': ['Quality', 'Balanced Growth'],
                    'avoid': ['Speculative', 'High Beta'],
                    'neutral': ['Diversified Sectors']
                }
        
        # Risk management
        uncertainty_count = len(beliefs.get('uncertainty_factors', []))
        
        if uncertainty_count > 2:
            actions['risk_management'] = {
                'position_sizing': 'REDUCE',
                'stop_losses': 'TIGHTEN',
                'diversification': 'INCREASE',
                'cash_level': 'RAISE'
            }
            actions['execution_priority'] = 'high'
        elif uncertainty_count > 0:
            actions['risk_management'] = {
                'position_sizing': 'NORMAL',
                'stop_losses': 'STANDARD',
                'diversification': 'MAINTAIN',
                'cash_level': 'NORMAL'
            }
        else:
            actions['risk_management'] = {
                'position_sizing': 'NORMAL_TO_LARGE',
                'stop_losses': 'STANDARD',
                'diversification': 'FOCUSED',
                'cash_level': 'LOW'
            }
        
        # Reasoning
        actions['reasoning'] = [
            f"Market stance: {market_stance} with {overall_conviction:.1%} conviction",
            f"Regime: {self.current_regime} limits exposure to {max_exposure}%",
            f"Uncertainty factors: {uncertainty_count}"
        ]
        
        if beliefs.get('valuation_beliefs'):
            val_assessment = beliefs['valuation_beliefs'].get('composite_assessment', 'unknown')
            actions['reasoning'].append(f"Valuation: Market appears {val_assessment}")
        
        return actions
    
    def save_intelligence_state(self, intelligence_result):
        """Save complete intelligence state for historical analysis"""
        
        # Save full result
        output_path = os.path.join(self.output_dir, 'intelligence_state.json')
        
        # Convert datetime objects to strings for JSON serialization
        def convert_datetime(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, (np.integer, np.int64)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float64)):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert_datetime(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_datetime(item) for item in obj]
            else:
                return obj
        
        serializable_result = convert_datetime(intelligence_result)
        
        with open(output_path, 'w') as f:
            json.dump(serializable_result, f, indent=2)
        
        # Save summary for dashboard
        summary = {
            'timestamp': intelligence_result['timestamp'].isoformat(),
            'regime': intelligence_result.get('regime'),
            'beliefs': convert_datetime(intelligence_result.get('beliefs', {})),
            'actions': convert_datetime(intelligence_result.get('actions', {})),
            'system_health': convert_datetime(self.calculate_system_health(intelligence_result))
        }
        
        summary_path = os.path.join(self.output_dir, 'intelligence_summary.json')
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"💾 Intelligence state saved to {output_path}")
    
    def calculate_system_health(self, intelligence_result):
        """Calculate overall system health score"""
        
        health_factors = []
        
        # Component availability
        components = intelligence_result.get('components', {})
        component_health = len(components) / 4  # Expect 4 main components
        health_factors.append(component_health)
        
        # Data quality
        overall_confidence = components.get('confidence', {}).get('overall_confidence', 0.5)
        health_factors.append(overall_confidence)
        
        # Learning status
        learning = intelligence_result.get('learning', {})
        learning_summary = learning.get('learning_summary', {})
        learning_health = 1.0 if learning_summary.get('learning_status') == 'active' else 0.6
        health_factors.append(learning_health)
        
        # Belief conviction
        beliefs = intelligence_result.get('beliefs', {})
        conviction = beliefs.get('conviction_levels', {}).get('overall', 0.5)
        health_factors.append(conviction)
        
        # Overall health
        overall_health = np.mean(health_factors)
        
        return {
            'overall_score': overall_health,
            'component_health': component_health,
            'data_quality': overall_confidence,
            'learning_health': learning_health,
            'conviction_health': conviction,
            'grade': 'A' if overall_health > 0.8 else 'B' if overall_health > 0.6 else 'C' if overall_health > 0.4 else 'D'
        }
    
    def load_latest_intelligence(self):
        """Load latest intelligence state"""
        
        summary_path = os.path.join(self.output_dir, 'intelligence_summary.json')
        
        if os.path.exists(summary_path):
            try:
                with open(summary_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading intelligence state: {e}")
        
        return None
    
    def run_intelligence_update(self, ticker=None):
        """
        Run complete intelligence update
        
        This is the main function to call for regular intelligence updates
        """
        
        print(f"🧠 Running intelligence update for {ticker or 'market'}")
        
        # Load market data
        try:
            from src.state.market_state import load_latest_market_state
            market_data = load_latest_market_state()
        except:
            market_data = None
        
        # Generate complete intelligence
        intelligence_result = self.generate_complete_intelligence(ticker, market_data)
        
        # Run learning routines
        self.learning_coordinator.run_daily_learning()
        
        return intelligence_result

# =========================== INTELLIGENCE DASHBOARD INTEGRATION ===========================

class IntelligenceDashboard:
    """
    Dashboard integration for intelligence system
    
    Provides clean interface for Northstar dashboard to access intelligence
    """
    
    def __init__(self):
        self.intelligence_stack = IntelligenceStack()
    
    def get_intelligence_summary(self):
        """Get intelligence summary for dashboard display"""
        
        latest_intelligence = self.intelligence_stack.load_latest_intelligence()
        
        if not latest_intelligence:
            return {
                'status': 'no_data',
                'message': 'No intelligence data available'
            }
        
        return {
            'status': 'active',
            'timestamp': latest_intelligence['timestamp'],
            'regime': latest_intelligence['regime'],
            'market_stance': latest_intelligence['beliefs']['market_beliefs']['stance'],
            'conviction': latest_intelligence['beliefs']['conviction_levels']['overall'],
            'primary_action': latest_intelligence['actions']['primary_action'],
            'target_exposure': latest_intelligence['actions']['exposure_recommendation']['target_exposure'],
            'system_health': latest_intelligence['system_health'],
            'key_insights': self.extract_key_insights(latest_intelligence)
        }
    
    def extract_key_insights(self, intelligence_data):
        """Extract key insights for dashboard display"""
        
        insights = []
        
        # Regime insight
        regime = intelligence_data.get('regime', 'unknown')
        insights.append(f"Market regime: {regime.title()}")
        
        # Conviction insight
        conviction = intelligence_data['beliefs']['conviction_levels']['overall']
        if conviction > 0.7:
            insights.append("High conviction environment")
        elif conviction < 0.4:
            insights.append("Low conviction - high uncertainty")
        
        # Valuation insight
        if 'valuation_beliefs' in intelligence_data['beliefs']:
            val_assessment = intelligence_data['beliefs']['valuation_beliefs']['composite_assessment']
            insights.append(f"Market appears {val_assessment}")
        
        # Learning insight
        learning_status = intelligence_data.get('learning', {}).get('learning_summary', {}).get('learning_status')
        if learning_status == 'active':
            insights.append("AI learning system active")
        
        return insights[:4]  # Top 4 insights

# =========================== MAIN EXECUTION ===========================

def main():
    """Demonstrate complete intelligence stack"""
    
    print("🧠 INTELLIGENCE STACK - INSTITUTIONAL GRADE INTEGRATION")
    print("=" * 70)
    
    # Initialize intelligence stack
    intelligence = IntelligenceStack()
    
    # Run complete intelligence generation
    result = intelligence.run_intelligence_update('RELIANCE')
    
    print("\n📊 INTELLIGENCE SUMMARY")
    print("-" * 40)
    print(f"Regime: {result.get('regime', 'unknown').upper()}")
    
    if 'beliefs' in result:
        beliefs = result['beliefs']
        print(f"Market Stance: {beliefs['market_beliefs']['stance']}")
        print(f"Overall Conviction: {beliefs['conviction_levels']['overall']:.3f}")
        
        if beliefs['uncertainty_factors']:
            print(f"Uncertainty Factors: {len(beliefs['uncertainty_factors'])}")
    
    if 'actions' in result:
        actions = result['actions']
        print(f"Primary Action: {actions['primary_action']}")
        print(f"Target Exposure: {actions['exposure_recommendation']['target_exposure']:.1f}%")
    
    # System health
    if 'system_health' in result:
        health = result['system_health']
        print(f"System Health: {health['grade']} ({health['overall_score']:.3f})")
    
    print("\n🎯 KEY INSIGHTS")
    print("-" * 40)
    
    dashboard = IntelligenceDashboard()
    summary = dashboard.get_intelligence_summary()
    
    if summary['status'] == 'active':
        for insight in summary['key_insights']:
            print(f"• {insight}")
    
    print("\n✅ Complete intelligence stack operational")
    print("🧠 Northstar has evolved from dashboard to institutional-grade investment brain")
    print("💡 This is how BlackRock, Bridgewater, AQR actually think about markets")

if __name__ == "__main__":
    main()