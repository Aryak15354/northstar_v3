#!/usr/bin/env python3
"""
🧠 ANTICIPATORY CAPITAL ALLOCATOR - NORTHSTAR V3 MARKET BRAIN
Capital Moves Before Prices Do

This is the enhanced capital allocator that integrates:
- Strategy beliefs (historical performance)
- Strategy regret (recent performance)
- Strategy tailwinds (anticipatory signals from beta drift)

The formula becomes:
Score = Sharpe × Belief × (1 + Tailwind) × Regret_Adjustment

This is how hedge funds get paid: they position before the market moves.
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Safe utilities
try:
    from src.utils.parquet_utils import safe_load_parquet
    from src.utils.json_utils import safe_load_json
except ImportError:
    def safe_load_parquet(file_path, default=None):
        try:
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                return pd.read_parquet(file_path)
        except:
            pass
        return default if default is not None else pd.DataFrame()
    
    def safe_load_json(file_path, default=None):
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    return json.load(f)
        except:
            pass
        return default if default is not None else {}

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Import existing V3 components
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.intelligence.strategy_beliefs import StrategyBeliefs
from src.intelligence.strategy_regret import StrategyRegret
from src.intelligence.strategy_tailwinds import StrategyTailwinds

class AnticipatoryCapitalAllocator:
    """
    Anticipatory Capital Allocator - The Forward-Looking Brain
    
    Integrates three intelligence layers:
    1. Beliefs: What has worked historically
    2. Regret: What is working recently  
    3. Tailwinds: What will work next (anticipatory)
    
    This creates anticipatory positioning before price moves.
    """
    
    def __init__(self):
        self.name = "Anticipatory Capital Allocator"
        self.version = "1.0"
        
        # Initialize components
        self.beliefs = StrategyBeliefs()
        self.regret = StrategyRegret()
        self.tailwinds = StrategyTailwinds()
        
        # Data paths
        self.paths = {
            'allocations_output': 'data/intelligence/anticipatory_allocations.json',
            'allocation_history': 'data/intelligence/allocation_history.parquet',
            'performance_tracking': 'data/intelligence/allocation_performance.json'
        }
        
        # Allocation parameters
        self.config = {
            'max_strategies': 6,           # Maximum strategies to allocate to
            'min_allocation': 0.05,       # Minimum allocation per strategy (5%)
            'max_allocation': 0.40,       # Maximum allocation per strategy (40%)
            'cash_buffer': 0.10,          # Minimum cash buffer (10%)
            'tailwind_weight': 0.30,      # Weight of tailwind component
            'belief_weight': 0.40,        # Weight of belief component
            'regret_weight': 0.30,        # Weight of regret component
            'rebalance_threshold': 0.05   # Minimum change to trigger rebalance
        }
        
        # Strategy universe
        self.strategy_universe = [
            'dual_momentum',
            'sector_tilt_momentum', 
            'momentum_12m',
            'value_tilt',
            'low_vol',
            'quality_growth'
        ]
    
    def load_strategy_components(self):
        """Load all strategy intelligence components with mock data"""
        
        try:
            print("📊 Loading strategy intelligence components...")
            
            # Mock beliefs data (historical performance)
            beliefs_data = {
                'dual_momentum': {'sharpe_ratio': 1.2},
                'sector_tilt_momentum': {'sharpe_ratio': 0.8},
                'momentum_12m': {'sharpe_ratio': 1.0},
                'value_tilt': {'sharpe_ratio': 0.6},
                'low_vol': {'sharpe_ratio': 0.9},
                'quality_growth': {'sharpe_ratio': 0.7}
            }
            
            # Mock regret data (recent performance)
            regret_data = {
                'dual_momentum': {'regret_adjustment': 1.1},
                'sector_tilt_momentum': {'regret_adjustment': 0.9},
                'momentum_12m': {'regret_adjustment': 1.0},
                'value_tilt': {'regret_adjustment': 1.2},
                'low_vol': {'regret_adjustment': 1.1},
                'quality_growth': {'regret_adjustment': 0.8}
            }
            
            # Load real tailwinds (anticipatory signals)
            tailwinds_data = self.tailwinds.get_current_tailwinds()
            
            print(f"   ✅ Beliefs: {len(beliefs_data)} strategies (mock)")
            print(f"   ✅ Regret: {len(regret_data)} strategies (mock)")
            print(f"   ✅ Tailwinds: {len(tailwinds_data)} strategies (real)")
            
            return beliefs_data, regret_data, tailwinds_data
            
        except Exception as e:
            print(f"❌ Error loading strategy components: {e}")
            return {}, {}, {}
    
    def compute_anticipatory_scores(self, beliefs_data, regret_data, tailwinds_data):
        """Compute anticipatory allocation scores"""
        
        try:
            print("🧠 Computing anticipatory allocation scores...")
            
            strategy_scores = {}
            
            for strategy in self.strategy_universe:
                # Get components (with defaults)
                belief = beliefs_data.get(strategy, {}).get('sharpe_ratio', 0.0)
                regret_adj = regret_data.get(strategy, {}).get('regret_adjustment', 1.0)
                tailwind = tailwinds_data.get(strategy, {}).get('total_tailwind', 0.0)
                
                # Normalize components
                belief_norm = max(0.1, belief + 1.0)  # Ensure positive, shift by 1
                regret_norm = max(0.5, regret_adj)    # Ensure reasonable bounds
                tailwind_norm = 1.0 + (tailwind * self.config['tailwind_weight'])  # Scale tailwind
                
                # Compute anticipatory score
                # Score = Belief × Regret × (1 + Tailwind)
                anticipatory_score = belief_norm * regret_norm * tailwind_norm
                
                strategy_scores[strategy] = {
                    'belief_component': float(belief_norm),
                    'regret_component': float(regret_norm),
                    'tailwind_component': float(tailwind_norm),
                    'raw_tailwind': float(tailwind),
                    'anticipatory_score': float(anticipatory_score),
                    'rank': 0  # Will be filled later
                }
            
            # Rank strategies by anticipatory score
            sorted_strategies = sorted(strategy_scores.items(), key=lambda x: x[1]['anticipatory_score'], reverse=True)
            for rank, (strategy, data) in enumerate(sorted_strategies):
                strategy_scores[strategy]['rank'] = rank + 1
            
            print(f"   ✅ Computed scores for {len(strategy_scores)} strategies")
            
            # Show top strategies
            print(f"   🏆 Top 3 strategies by anticipatory score:")
            for i, (strategy, data) in enumerate(sorted_strategies[:3]):
                print(f"      {i+1}. {strategy}: {data['anticipatory_score']:.3f} (tailwind: {data['raw_tailwind']:+.3f})")
            
            return strategy_scores
            
        except Exception as e:
            print(f"❌ Error computing anticipatory scores: {e}")
            return {}
    
    def compute_allocations(self, strategy_scores):
        """Compute optimal allocations from anticipatory scores"""
        
        try:
            print("💰 Computing optimal allocations...")
            
            if not strategy_scores:
                return {}
            
            # Filter to top strategies
            sorted_strategies = sorted(strategy_scores.items(), key=lambda x: x[1]['anticipatory_score'], reverse=True)
            top_strategies = sorted_strategies[:self.config['max_strategies']]
            
            # Compute raw weights (proportional to scores)
            total_score = sum(data['anticipatory_score'] for _, data in top_strategies)
            
            if total_score <= 0:
                print("⚠️ All strategies have non-positive scores")
                return {}
            
            # Calculate allocations
            allocations = {}
            total_allocated = 0.0
            
            for strategy, data in top_strategies:
                raw_weight = data['anticipatory_score'] / total_score
                
                # Apply allocation constraints
                allocation = max(self.config['min_allocation'], 
                               min(self.config['max_allocation'], raw_weight))
                
                allocations[strategy] = {
                    'allocation': float(allocation),
                    'anticipatory_score': data['anticipatory_score'],
                    'belief_component': data['belief_component'],
                    'regret_component': data['regret_component'],
                    'tailwind_component': data['tailwind_component'],
                    'raw_tailwind': data['raw_tailwind'],
                    'rank': data['rank']
                }
                
                total_allocated += allocation
            
            # Normalize to ensure we don't exceed 1.0 - cash_buffer
            max_total = 1.0 - self.config['cash_buffer']
            if total_allocated > max_total:
                scale_factor = max_total / total_allocated
                for strategy in allocations:
                    allocations[strategy]['allocation'] *= scale_factor
                total_allocated = max_total
            
            # Add cash allocation
            cash_allocation = 1.0 - total_allocated
            allocations['cash'] = {
                'allocation': float(cash_allocation),
                'anticipatory_score': 0.0,
                'belief_component': 1.0,
                'regret_component': 1.0,
                'tailwind_component': 1.0,
                'raw_tailwind': 0.0,
                'rank': len(allocations) + 1
            }
            
            print(f"   ✅ Computed allocations for {len(allocations)} positions")
            print(f"   💰 Total allocated: {total_allocated:.1%}")
            print(f"   💵 Cash buffer: {cash_allocation:.1%}")
            
            # Show allocations
            print(f"   📊 Allocation breakdown:")
            for strategy, data in sorted(allocations.items(), key=lambda x: x[1]['allocation'], reverse=True):
                if strategy != 'cash':
                    tailwind_str = f" (tailwind: {data['raw_tailwind']:+.3f})" if data['raw_tailwind'] != 0 else ""
                    print(f"      {strategy}: {data['allocation']:.1%}{tailwind_str}")
                else:
                    print(f"      {strategy}: {data['allocation']:.1%}")
            
            return allocations
            
        except Exception as e:
            print(f"❌ Error computing allocations: {e}")
            return {}
    
    def save_allocations(self, allocations, strategy_scores):
        """Save allocation results"""
        
        try:
            # Create output directory
            os.makedirs(os.path.dirname(self.paths['allocations_output']), exist_ok=True)
            
            # Prepare allocation data
            allocation_data = {
                'created_at': datetime.now().isoformat(),
                'version': self.version,
                'allocations': allocations,
                'strategy_scores': strategy_scores,
                'config': self.config,
                'summary': {
                    'total_strategies': len([k for k in allocations.keys() if k != 'cash']),
                    'cash_allocation': allocations.get('cash', {}).get('allocation', 0.0),
                    'largest_allocation': max(data['allocation'] for data in allocations.values()),
                    'strategies_with_tailwinds': len([k for k, v in allocations.items() if v.get('raw_tailwind', 0) > 0]),
                    'total_positive_tailwinds': sum(max(0, v.get('raw_tailwind', 0)) for v in allocations.values()),
                    'anticipatory_signal_strength': sum(abs(v.get('raw_tailwind', 0)) for v in allocations.values())
                }
            }
            
            # Save current allocations
            with open(self.paths['allocations_output'], 'w') as f:
                json.dump(allocation_data, f, indent=2)
            
            print(f"   💾 Saved allocations: {self.paths['allocations_output']}")
            
            # Update allocation history
            self.update_allocation_history(allocations)
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving allocations: {e}")
            return False
    
    def update_allocation_history(self, allocations):
        """Update allocation history for tracking"""
        
        try:
            # Create history record
            history_record = {
                'date': datetime.now(),
                **{f'{strategy}_allocation': data['allocation'] for strategy, data in allocations.items()},
                **{f'{strategy}_tailwind': data.get('raw_tailwind', 0.0) for strategy, data in allocations.items() if strategy != 'cash'}
            }
            
            # Load existing history
            if os.path.exists(self.paths['allocation_history']):
                history_df = safe_load_parquet(self.paths['allocation_history'])
                history_df = pd.concat([history_df, pd.DataFrame([history_record])], ignore_index=True)
            else:
                history_df = pd.DataFrame([history_record])
            
            # Save updated history
            history_df.to_parquet(self.paths['allocation_history'], index=False)
            
            print(f"   📈 Updated allocation history: {len(history_df)} records")
            
        except Exception as e:
            print(f"⚠️ Error updating allocation history: {e}")
    
    def build_anticipatory_allocations(self):
        """Build complete anticipatory capital allocations"""
        
        start_time = datetime.now()
        
        print("🧠 BUILDING ANTICIPATORY CAPITAL ALLOCATIONS")
        print("=" * 60)
        print("Capital moves before prices do")
        print("Integrating: Beliefs + Regret + Tailwinds")
        print()
        
        # Load strategy components
        beliefs_data, regret_data, tailwinds_data = self.load_strategy_components()
        
        if not any([beliefs_data, regret_data, tailwinds_data]):
            print("❌ No strategy intelligence data available")
            return False
        
        # Compute anticipatory scores
        strategy_scores = self.compute_anticipatory_scores(beliefs_data, regret_data, tailwinds_data)
        
        if not strategy_scores:
            print("❌ Could not compute strategy scores")
            return False
        
        # Compute allocations
        allocations = self.compute_allocations(strategy_scores)
        
        if not allocations:
            print("❌ Could not compute allocations")
            return False
        
        # Save results
        if not self.save_allocations(allocations, strategy_scores):
            print("❌ Failed to save allocations")
            return False
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        print("=" * 60)
        print("✅ ANTICIPATORY CAPITAL ALLOCATIONS COMPLETED!")
        print(f"   📊 Processed {len(strategy_scores)} strategies")
        print(f"   💰 Generated {len(allocations)} allocations")
        print(f"   🌊 Strategies with tailwinds: {len([k for k, v in allocations.items() if v.get('raw_tailwind', 0) > 0])}")
        print(f"   ⏱️  Processing time: {processing_time:.1f} seconds")
        print()
        print("🎯 ANTICIPATORY POSITIONING READY:")
        print("   Capital is now positioned based on sensitivity shifts")
        print("   Strategies with positive tailwinds get increased allocation")
        print("   This happens BEFORE price moves, not after")
        
        return True
    
    def get_current_allocations(self):
        """Get current anticipatory allocations"""
        
        try:
            if os.path.exists(self.paths['allocations_output']):
                with open(self.paths['allocations_output'], 'r') as f:
                    data = json.load(f)
                return data.get('allocations', {})
            else:
                return {}
        except Exception as e:
            print(f"⚠️ Error loading current allocations: {e}")
            return {}

def main():
    """Build anticipatory capital allocations"""
    
    allocator = AnticipatoryCapitalAllocator()
    
    print("🧠 ANTICIPATORY CAPITAL ALLOCATOR")
    print("Capital moves before prices do")
    print("=" * 50)
    
    success = allocator.build_anticipatory_allocations()
    
    if success:
        print("\n🎯 Anticipatory capital allocations ready!")
        print("   Next: Portfolio execution uses these allocations")
        print("   This is how hedge funds get paid")
        return True
    else:
        print("❌ Failed to build anticipatory allocations")
        return False

if __name__ == "__main__":
    main()
