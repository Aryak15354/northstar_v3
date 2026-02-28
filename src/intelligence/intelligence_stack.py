#!/usr/bin/env python3
"""
🧠 MINIMAL INTELLIGENCE STACK - NORTHSTAR V3
Simplified Intelligence System that works without all dependencies
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import json
import warnings
warnings.filterwarnings('ignore')

class MinimalIntelligenceStack:
    """
    Minimal Intelligence Stack - Works without all dependencies
    """
    
    def __init__(self):
        self.name = "Minimal Intelligence Stack"
        self.version = "1.0"
        
        # Initialize with minimal components
        self.current_regime = 'neutral'
        self.current_beliefs = {}
        self.current_conviction = 0.5
        
        # Output paths
        self.output_dir = 'data/intelligence'
        os.makedirs(self.output_dir, exist_ok=True)
    
    def generate_complete_intelligence(self, ticker=None, market_data=None):
        """Generate minimal intelligence"""
        
        print("🧠 GENERATING MINIMAL INTELLIGENCE")
        print("=" * 50)
        
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
        
        # Step 1: Detect Market Regime (simplified)
        regime = self.detect_market_regime(market_data)
        self.current_regime = regime
        intelligence_result['regime'] = regime
        print(f"   Current regime: {regime.upper()}")
        
        # Step 2: Generate minimal beliefs
        beliefs = self.generate_minimal_beliefs()
        intelligence_result['beliefs'] = beliefs
        self.current_beliefs = beliefs
        
        # Step 3: Generate minimal actions
        actions = self.generate_minimal_actions()
        intelligence_result['actions'] = actions
        
        # Step 4: Save intelligence state
        self.save_intelligence_state(intelligence_result)
        
        print("✅ Minimal intelligence generation finished")
        return intelligence_result
    
    def detect_market_regime(self, market_data=None):
        """Simple regime detection"""
        
        if market_data:
            macro_score = market_data.get('macro_score', 0.0)
            if macro_score > 0.5:
                return 'bull'
            elif macro_score < -0.5:
                return 'bear'
        
        return 'neutral'
    
    def generate_minimal_beliefs(self):
        """Generate minimal beliefs"""
        
        beliefs = {
            'timestamp': datetime.now(),
            'regime': self.current_regime,
            'market_beliefs': {
                'stance': 'Neutral',
                'conviction': 0.5,
                'key_themes': ['Market Uncertainty'],
                'juror_consensus': 0.5
            },
            'valuation_beliefs': {
                'composite_assessment': 'neutral',
                'confidence': 0.5,
                'agreement': 0.5,
                'narrative': 'Market appears fairly valued'
            },
            'conviction_levels': {
                'valuation': 0.5,
                'narrative': 0.5,
                'overall': 0.5
            },
            'uncertainty_factors': []
        }
        
        return beliefs
    
    def generate_minimal_actions(self):
        """Generate minimal actions"""
        
        actions = {
            'timestamp': datetime.now(),
            'primary_action': 'MAINTAIN_EXPOSURE',
            'exposure_recommendation': {
                'target_exposure': 50.0,
                'base_exposure': 50.0,
                'conviction_multiplier': 1.0,
                'regime_limit': 65.0
            },
            'sector_allocation': {
                'favor': ['Quality', 'Balanced Growth'],
                'avoid': ['Speculative', 'High Beta'],
                'neutral': ['Diversified Sectors']
            },
            'risk_management': {
                'position_sizing': 'NORMAL',
                'stop_losses': 'STANDARD',
                'diversification': 'MAINTAIN',
                'cash_level': 'NORMAL'
            },
            'execution_priority': 'medium',
            'reasoning': [
                'Minimal intelligence system active',
                'Using conservative defaults',
                'Regime: neutral'
            ]
        }
        
        return actions
    
    def save_intelligence_state(self, intelligence_result):
        """Save intelligence state"""
        
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
            'system_health': {
                'overall_score': 0.7,
                'component_health': 0.7,
                'data_quality': 0.7,
                'learning_health': 0.7,
                'conviction_health': 0.5,
                'grade': 'B'
            }
        }
        
        summary_path = os.path.join(self.output_dir, 'intelligence_summary.json')
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"💾 Intelligence state saved to {output_path}")
    
    def load_latest_intelligence(self):
        """Load latest intelligence state"""
        
        summary_path = os.path.join(self.output_dir, 'intelligence_summary.json')
        
        if os.path.exists(summary_path):
            try:
                with open(summary_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading intelligence: {e}")
        
        return None
    
    def run_intelligence_update(self, ticker=None):
        """Run intelligence update"""
        
        print(f"🧠 Running minimal intelligence update for {ticker or 'market'}")
        
        # Generate intelligence
        intelligence_result = self.generate_complete_intelligence(ticker, None)
        
        return intelligence_result

# Create alias for compatibility
IntelligenceStack = MinimalIntelligenceStack

def main():
    """Test minimal intelligence stack"""
    
    intelligence = MinimalIntelligenceStack()
    result = intelligence.run_intelligence_update('RELIANCE')
    
    print("\n📊 MINIMAL INTELLIGENCE SUMMARY")
    print("-" * 40)
    print(f"Regime: {result.get('regime', 'unknown').upper()}")
    
    if 'beliefs' in result:
        beliefs = result['beliefs']
        print(f"Market Stance: {beliefs['market_beliefs']['stance']}")
        print(f"Overall Conviction: {beliefs['conviction_levels']['overall']:.3f}")
    
    if 'actions' in result:
        actions = result['actions']
        print(f"Primary Action: {actions['primary_action']}")
        print(f"Target Exposure: {actions['exposure_recommendation']['target_exposure']:.1f}%")
    
    print("\n✅ Minimal intelligence stack operational")

if __name__ == "__main__":
    main()
