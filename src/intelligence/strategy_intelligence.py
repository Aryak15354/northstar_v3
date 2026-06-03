#!/usr/bin/env python3
"""
🧬 STRATEGY INTELLIGENCE - NORTHSTAR V3
Complete Strategy Intelligence System

Coordinates strategy beliefs, regret, and tailwinds into unified intelligence.
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

class StrategyIntelligence:
    """Strategy Intelligence Coordinator"""
    
    def __init__(self):
        self.name = "Strategy Intelligence"
        self.version = "1.0"
        self.component_status = {}
        self.execution_log = []
        
        # Initialize components
        self._tailwind_engine = None
        self._beliefs_engine = None
        self._regret_engine = None
    
    @property
    def tailwind_engine(self):
        if self._tailwind_engine is None:
            try:
                from intelligence.simple_tailwind_engine import SimpleTailwindEngine
                self._tailwind_engine = SimpleTailwindEngine()
            except ImportError:
                self._tailwind_engine = None
        return self._tailwind_engine
    
    @property
    def beliefs_engine(self):
        if self._beliefs_engine is None:
            try:
                from intelligence.strategy_beliefs import StrategyBeliefs
                self._beliefs_engine = StrategyBeliefs()
            except ImportError:
                self._beliefs_engine = None
        return self._beliefs_engine
    
    @property
    def regret_engine(self):
        if self._regret_engine is None:
            try:
                from intelligence.strategy_regret import StrategyRegret
                self._regret_engine = StrategyRegret()
            except ImportError:
                self._regret_engine = None
        return self._regret_engine
    
    def run_complete_intelligence(self):
        """Run complete strategy intelligence"""
        
        print("🧬 Running complete strategy intelligence...")
        
        success_count = 0
        
        # Run tailwinds
        if self.tailwind_engine:
            try:
                tailwinds = self.tailwind_engine.get_all_tailwinds()
                self.component_status['tailwinds'] = True
                success_count += 1
                print(f"   ✅ Tailwinds: {len(tailwinds) if tailwinds else 0} strategies")
            except Exception as e:
                print(f"   ❌ Tailwinds failed: {e}")
                self.component_status['tailwinds'] = False
        
        # Run beliefs
        if self.beliefs_engine:
            try:
                beliefs = self.beliefs_engine.get_all_beliefs()
                self.component_status['beliefs'] = True
                success_count += 1
                print(f"   ✅ Beliefs: {len(beliefs) if beliefs else 0} strategies")
            except Exception as e:
                print(f"   ❌ Beliefs failed: {e}")
                self.component_status['beliefs'] = False
        
        # Run regret
        if self.regret_engine:
            try:
                regret = self.regret_engine.get_all_regret()
                self.component_status['regret'] = True
                success_count += 1
                print(f"   ✅ Regret: {len(regret) if regret else 0} strategies")
            except Exception as e:
                print(f"   ❌ Regret failed: {e}")
                self.component_status['regret'] = False
        
        # Save summary
        summary = {
            'timestamp': datetime.now().isoformat(),
            'success_count': success_count,
            'component_status': self.component_status
        }
        
        os.makedirs('data/processed', exist_ok=True)
        with open('data/processed/strategy_intelligence_summary.json', 'w') as f:
            json.dump(summary, f, indent=2)
        
        return success_count > 0

def main():
    intelligence = StrategyIntelligence()
    return intelligence.run_complete_intelligence()

if __name__ == "__main__":
    main()
