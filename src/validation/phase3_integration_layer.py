#!/usr/bin/env python3
"""
🔗 PHASE 3 INTEGRATION LAYER - NORTHSTAR V3 PHASE 4
Seamless integration layer for Phase 3 components

This creates a unified integration layer that:
1. Provides seamless integration with existing Phase 3 components
2. Gets regime state from RegimeMemorySystem
3. Gets tailwinds from SimpleTailwindEngine
4. Checks NO_EDGE state from NoEdgeDetector
5. Gets allocations from AnticipatoryCapitalAllocator
6. Maintains clean separation of concerns and error handling

The integration layer acts as a facade that simplifies access to
Phase 3 components while providing robust error handling and
consistent data formats for Phase 4 enhancements.

Integration Benefits:
- Single point of access for all Phase 3 intelligence
- Consistent error handling and fallback behavior
- Clean abstraction for Phase 4 components
- Maintains backward compatibility with V3 architecture
- Provides unified data formats and validation

Output: Unified Phase 3 intelligence state for Phase 4 consumption
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
import warnings
warnings.filterwarnings('ignore')

class Phase3IntegrationLayer:
    """
    Phase 3 Integration Layer
    
    Provides unified access to Phase 3 components:
    - RegimeMemorySystem for regime detection and similarity
    - SimpleTailwindEngine for strategy tailwind calculations
    - NoEdgeDetector for risk state management
    - CapitalAllocator for enhanced allocation decisions
    
    Features:
    - Robust error handling with graceful degradation
    - Consistent data formats across components
    - Caching for performance optimization
    - Validation of component integration
    """
    
    def __init__(self):
        self.name = "Phase 3 Integration Layer"
        self.version = "4.0"
        
        # Data paths for Phase 3 components
        self.paths = {
            # Regime Memory System
            'regime_memory': 'data/intelligence/regime_memory.parquet',
            'regime_metadata': 'data/intelligence/regime_metadata.json',
            
            # Simple Tailwind Engine
            'strategy_tailwinds': 'data/intelligence/strategy_tailwinds.parquet',
            'tailwind_metadata': 'data/intelligence/tailwind_metadata.json',
            
            # NO_EDGE Detector
            'no_edge_state': 'data/intelligence/no_edge_state.parquet',
            'no_edge_log': 'data/intelligence/no_edge_transitions.json',
            
            # Capital Allocator
            'capital_allocations': 'data/processed/capital_allocations.json',
            'allocation_history': 'data/processed/allocation_history.parquet',
            
            # Supporting data
            'market_state': 'data/processed/market_state.parquet',
            'strategy_beliefs': 'data/processed/strategy_beliefs.parquet',
            'strategy_regret': 'data/processed/strategy_regret.parquet'
        }
        
        # Configuration
        self.config = {
            'cache_ttl_seconds': 300,          # 5 minute cache TTL
            'min_confidence_threshold': 0.1,   # Minimum confidence for valid state
            'max_regime_age_days': 7,          # Maximum age for regime data
            'max_tailwind_age_days': 1,        # Maximum age for tailwind data
            'max_no_edge_age_days': 1,         # Maximum age for NO_EDGE data
            'max_allocation_age_hours': 6,     # Maximum age for allocation data
            'fallback_exposure_cap': 0.5,      # Fallback exposure cap when NO_EDGE unavailable
            'fallback_regime': 'Late-Expansion' # Fallback regime when detection fails
        }
        
        # Component interfaces (lazy loaded)
        self._regime_memory = None
        self._tailwind_engine = None
        self._no_edge_detector = None
        self._capital_allocator = None
        
        # Cache for performance
        self._cache = {}
        self._cache_timestamps = {}
        
        # Integration status
        self.integration_status = {
            'regime_memory': False,
            'tailwind_engine': False,
            'no_edge_detector': False,
            'capital_allocator': False,
            'last_check': None
        }
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid"""
        if key not in self._cache_timestamps:
            return False
        
        age = datetime.now() - self._cache_timestamps[key]
        return age.total_seconds() < self.config['cache_ttl_seconds']
    
    def _set_cache(self, key: str, value: Any) -> None:
        """Set cached value with timestamp"""
        self._cache[key] = value
        self._cache_timestamps[key] = datetime.now()
    
    def _get_cache(self, key: str) -> Optional[Any]:
        """Get cached value if valid"""
        if self._is_cache_valid(key):
            return self._cache.get(key)
        return None
    
    def _initialize_component_interfaces(self) -> Dict[str, bool]:
        """Initialize Phase 3 component interfaces with error handling"""
        
        print("🔗 Initializing Phase 3 component interfaces...")
        
        status = {
            'regime_memory': False,
            'tailwind_engine': False,
            'no_edge_detector': False,
            'capital_allocator': False
        }
        
        try:
            # Import Phase 3 components
            import sys
            sys.path.append(os.path.dirname(os.path.dirname(__file__)))
            
            # Initialize RegimeMemorySystem
            try:
                from intelligence.regime_memory_system import RegimeMemorySystem
                self._regime_memory = RegimeMemorySystem()
                status['regime_memory'] = True
                print("   ✅ RegimeMemorySystem initialized")
            except Exception as e:
                print(f"   ⚠️ RegimeMemorySystem failed: {e}")
            
            # Initialize SimpleTailwindEngine
            try:
                from intelligence.simple_tailwind_engine import SimpleTailwindEngine
                self._tailwind_engine = SimpleTailwindEngine()
                status['tailwind_engine'] = True
                print("   ✅ SimpleTailwindEngine initialized")
            except Exception as e:
                print(f"   ⚠️ SimpleTailwindEngine failed: {e}")
            
            # Initialize NoEdgeDetector
            try:
                from intelligence.no_edge_detector import NoEdgeDetector
                self._no_edge_detector = NoEdgeDetector()
                status['no_edge_detector'] = True
                print("   ✅ NoEdgeDetector initialized")
            except Exception as e:
                print(f"   ⚠️ NoEdgeDetector failed: {e}")
            
            # Initialize CapitalAllocator
            try:
                from intelligence.capital_allocator import CapitalAllocator
                self._capital_allocator = CapitalAllocator()
                status['capital_allocator'] = True
                print("   ✅ CapitalAllocator initialized")
            except Exception as e:
                print(f"   ⚠️ CapitalAllocator failed: {e}")
            
        except Exception as e:
            print(f"   ❌ Component initialization failed: {e}")
        
        self.integration_status.update(status)
        self.integration_status['last_check'] = datetime.now()
        
        initialized_count = sum(status.values())
        print(f"   📊 Initialized {initialized_count}/4 Phase 3 components")
        
        return status
    
    def get_regime_state(self, use_cache: bool = True) -> Dict[str, Any]:
        """Get current regime state from RegimeMemorySystem"""
        
        cache_key = 'regime_state'
        if use_cache:
            cached = self._get_cache(cache_key)
            if cached is not None:
                return cached
        
        print("🧠 Getting regime state from RegimeMemorySystem...")
        
        regime_state = {
            'available': False,
            'regime': self.config['fallback_regime'],
            'confidence': 0.1,
            'similarity': 0.0,
            'expected_return': 0.0,
            'expected_sharpe': 0.0,
            'match_date': None,
            'age_days': 999,
            'source': 'fallback'
        }
        
        try:
            # Check if regime memory data exists and is recent
            if os.path.exists(self.paths['regime_memory']):
                regime_df = pd.read_parquet(self.paths['regime_memory'])
                
                if not regime_df.empty:
                    latest_regime = regime_df.iloc[-1]
                    data_age = (datetime.now().date() - latest_regime.name.date()).days
                    
                    if data_age <= self.config['max_regime_age_days']:
                        regime_state.update({
                            'available': True,
                            'regime': latest_regime['Regime'],
                            'confidence': 0.8,  # High confidence for recent data
                            'expected_return': float(latest_regime.get('regime_avg_return', 0)),
                            'expected_sharpe': float(latest_regime.get('regime_sharpe', 0)),
                            'match_date': latest_regime.name.strftime('%Y-%m-%d'),
                            'age_days': data_age,
                            'source': 'regime_memory'
                        })
                        
                        print(f"   ✅ Regime: {regime_state['regime']} (age: {data_age} days)")
                    else:
                        print(f"   ⚠️ Regime data too old: {data_age} days")
                else:
                    print("   ⚠️ Empty regime memory")
            else:
                print("   ⚠️ Regime memory file not found")
            
            # Try to get current regime match if component is available
            if self._regime_memory and regime_state['available']:
                try:
                    # Use a simple market state for matching
                    current_market_state = {
                        'MacroScore': 0.0,
                        'Contrib_G': 0.0,
                        'Contrib_I': 0.0
                    }
                    
                    regime_match = self._regime_memory.get_current_regime_match(current_market_state)
                    if regime_match:
                        regime_state.update({
                            'similarity': regime_match.get('similarity', 0),
                            'confidence': 0.9 if regime_match.get('confidence') == 'high' else 0.7
                        })
                        print(f"   📊 Regime similarity: {regime_state['similarity']:.3f}")
                
                except Exception as e:
                    print(f"   ⚠️ Regime matching failed: {e}")
        
        except Exception as e:
            print(f"   ⚠️ Error getting regime state: {e}")
        
        if use_cache:
            self._set_cache(cache_key, regime_state)
        
        return regime_state
    
    def get_strategy_tailwinds(self, use_cache: bool = True) -> Dict[str, Any]:
        """Get strategy tailwinds from SimpleTailwindEngine"""
        
        cache_key = 'strategy_tailwinds'
        if use_cache:
            cached = self._get_cache(cache_key)
            if cached is not None:
                return cached
        
        print("🌬️ Getting strategy tailwinds from SimpleTailwindEngine...")
        
        tailwind_state = {
            'available': False,
            'tailwinds': {},
            'regime': self.config['fallback_regime'],
            'n_strategies': 0,
            'age_days': 999,
            'top_strategy': None,
            'top_score': 0.0,
            'source': 'fallback'
        }
        
        try:
            # Check if tailwind data exists and is recent
            if os.path.exists(self.paths['strategy_tailwinds']):
                tailwind_df = pd.read_parquet(self.paths['strategy_tailwinds'])
                
                if not tailwind_df.empty:
                    # Check data age
                    if hasattr(tailwind_df.index, 'date'):
                        latest_date = tailwind_df.index[-1]
                        if hasattr(latest_date, 'date'):
                            data_age = (datetime.now().date() - latest_date.date()).days
                        else:
                            data_age = 0  # Assume recent if no date info
                    else:
                        data_age = 0  # Assume recent if no date index
                    
                    if data_age <= self.config['max_tailwind_age_days']:
                        # Process tailwind data
                        tailwinds = {}
                        for _, row in tailwind_df.iterrows():
                            strategy = row['strategy']
                            tailwinds[strategy] = {
                                'combined_score': float(row['combined_score']),
                                'sharpe': float(row['sharpe']),
                                'regime_tailwind': float(row['regime_tailwind']),
                                'regime': row['regime']
                            }
                        
                        # Find top strategy
                        if tailwinds:
                            top_strategy = max(tailwinds.items(), key=lambda x: x[1]['combined_score'])
                            
                            tailwind_state.update({
                                'available': True,
                                'tailwinds': tailwinds,
                                'regime': tailwind_df.iloc[0]['regime'],
                                'n_strategies': len(tailwinds),
                                'age_days': data_age,
                                'top_strategy': top_strategy[0],
                                'top_score': top_strategy[1]['combined_score'],
                                'source': 'tailwind_engine'
                            })
                            
                            print(f"   ✅ Tailwinds for {len(tailwinds)} strategies (age: {data_age} days)")
                            print(f"   🏆 Top strategy: {top_strategy[0]} ({top_strategy[1]['combined_score']:.2f})")
                    else:
                        print(f"   ⚠️ Tailwind data too old: {data_age} days")
                else:
                    print("   ⚠️ Empty tailwind data")
            else:
                print("   ⚠️ Tailwind data file not found")
            
            # Try to get fresh tailwinds if component is available
            if self._tailwind_engine and not tailwind_state['available']:
                try:
                    fresh_tailwinds = self._tailwind_engine.get_all_tailwinds()
                    if fresh_tailwinds:
                        tailwind_state.update({
                            'available': True,
                            'tailwinds': fresh_tailwinds,
                            'n_strategies': len(fresh_tailwinds),
                            'age_days': 0,
                            'source': 'fresh_computation'
                        })
                        print(f"   ✅ Fresh tailwinds computed for {len(fresh_tailwinds)} strategies")
                
                except Exception as e:
                    print(f"   ⚠️ Fresh tailwind computation failed: {e}")
        
        except Exception as e:
            print(f"   ⚠️ Error getting strategy tailwinds: {e}")
        
        if use_cache:
            self._set_cache(cache_key, tailwind_state)
        
        return tailwind_state
    
    def get_no_edge_state(self, use_cache: bool = True) -> Dict[str, Any]:
        """Get NO_EDGE state from NoEdgeDetector"""
        
        cache_key = 'no_edge_state'
        if use_cache:
            cached = self._get_cache(cache_key)
            if cached is not None:
                return cached
        
        print("🚨 Getting NO_EDGE state from NoEdgeDetector...")
        
        no_edge_state = {
            'available': False,
            'state': 'UNKNOWN',
            'exposure_cap': self.config['fallback_exposure_cap'],
            'reasons': [],
            'confidence': 0.1,
            'age_days': 999,
            'transitions_today': 0,
            'source': 'fallback'
        }
        
        try:
            # Check if NO_EDGE state data exists and is recent
            if os.path.exists(self.paths['no_edge_state']):
                no_edge_df = pd.read_parquet(self.paths['no_edge_state'])
                
                if not no_edge_df.empty:
                    latest_state = no_edge_df.iloc[-1]
                    
                    # Check data age
                    if 'date' in latest_state:
                        state_date = pd.to_datetime(latest_state['date']).date()
                        data_age = (datetime.now().date() - state_date).days
                    else:
                        data_age = 0  # Assume recent if no date
                    
                    if data_age <= self.config['max_no_edge_age_days']:
                        reasons = latest_state['reasons'].split('; ') if latest_state['reasons'] else []
                        
                        no_edge_state.update({
                            'available': True,
                            'state': latest_state['state'],
                            'exposure_cap': float(latest_state['exposure_cap']),
                            'reasons': reasons,
                            'confidence': 0.9 if latest_state['state'] == 'NORMAL' else 0.7,
                            'age_days': data_age,
                            'source': 'no_edge_detector'
                        })
                        
                        print(f"   ✅ NO_EDGE state: {latest_state['state']} (cap: {latest_state['exposure_cap']:.0%})")
                        if reasons:
                            print(f"   📋 Reasons: {len(reasons)}")
                    else:
                        print(f"   ⚠️ NO_EDGE data too old: {data_age} days")
                else:
                    print("   ⚠️ Empty NO_EDGE data")
            else:
                print("   ⚠️ NO_EDGE data file not found")
            
            # Try to get fresh NO_EDGE state if component is available
            if self._no_edge_detector and not no_edge_state['available']:
                try:
                    fresh_state = self._no_edge_detector.get_current_state()
                    if fresh_state:
                        no_edge_state.update({
                            'available': True,
                            'state': fresh_state['state'],
                            'exposure_cap': fresh_state['exposure_cap'],
                            'reasons': fresh_state['reasons'],
                            'confidence': 0.9,
                            'age_days': 0,
                            'source': 'fresh_detection'
                        })
                        print(f"   ✅ Fresh NO_EDGE state: {fresh_state['state']}")
                
                except Exception as e:
                    print(f"   ⚠️ Fresh NO_EDGE detection failed: {e}")
            
            # Count transitions today
            if os.path.exists(self.paths['no_edge_log']):
                try:
                    with open(self.paths['no_edge_log'], 'r') as f:
                        transitions = json.load(f)
                    
                    today = datetime.now().date()
                    transitions_today = sum(1 for t in transitions 
                                          if pd.to_datetime(t['timestamp']).date() == today)
                    no_edge_state['transitions_today'] = transitions_today
                    
                    if transitions_today > 0:
                        print(f"   📊 Transitions today: {transitions_today}")
                
                except Exception as e:
                    print(f"   ⚠️ Error counting transitions: {e}")
        
        except Exception as e:
            print(f"   ⚠️ Error getting NO_EDGE state: {e}")
        
        if use_cache:
            self._set_cache(cache_key, no_edge_state)
        
        return no_edge_state
    
    def get_capital_allocations(self, use_cache: bool = True) -> Dict[str, Any]:
        """Get capital allocations from CapitalAllocator"""
        
        cache_key = 'capital_allocations'
        if use_cache:
            cached = self._get_cache(cache_key)
            if cached is not None:
                return cached
        
        print("💰 Getting capital allocations from CapitalAllocator...")
        
        allocation_state = {
            'available': False,
            'allocations': {},
            'total_exposure': 0.0,
            'n_strategies': 0,
            'age_hours': 999,
            'regime': self.config['fallback_regime'],
            'top_allocation': None,
            'top_weight': 0.0,
            'source': 'fallback'
        }
        
        try:
            # Check if allocation data exists and is recent
            if os.path.exists(self.paths['capital_allocations']):
                with open(self.paths['capital_allocations'], 'r') as f:
                    allocation_data = json.load(f)
                
                # Check data age
                if 'timestamp' in allocation_data:
                    allocation_time = pd.to_datetime(allocation_data['timestamp'])
                    data_age_hours = (datetime.now() - allocation_time).total_seconds() / 3600
                else:
                    data_age_hours = 0  # Assume recent if no timestamp
                
                if data_age_hours <= self.config['max_allocation_age_hours']:
                    allocations = allocation_data.get('allocations', {})
                    
                    if allocations:
                        total_exposure = sum(allocations.values())
                        
                        # Find top allocation
                        top_allocation = max(allocations.items(), key=lambda x: x[1])
                        
                        allocation_state.update({
                            'available': True,
                            'allocations': allocations,
                            'total_exposure': total_exposure,
                            'n_strategies': len(allocations),
                            'age_hours': data_age_hours,
                            'regime': allocation_data.get('regime', {}).get('macro_regime', 'Unknown'),
                            'top_allocation': top_allocation[0],
                            'top_weight': top_allocation[1],
                            'source': 'capital_allocator'
                        })
                        
                        print(f"   ✅ Allocations for {len(allocations)} strategies (age: {data_age_hours:.1f}h)")
                        print(f"   📊 Total exposure: {total_exposure:.1%}")
                        print(f"   🏆 Top allocation: {top_allocation[0]} ({top_allocation[1]:.1%})")
                else:
                    print(f"   ⚠️ Allocation data too old: {data_age_hours:.1f} hours")
            else:
                print("   ⚠️ Allocation data file not found")
            
            # Try to get fresh allocations if component is available
            if self._capital_allocator and not allocation_state['available']:
                try:
                    fresh_allocations = self._capital_allocator.run_allocation()
                    if fresh_allocations:
                        total_exposure = sum(fresh_allocations.values())
                        
                        allocation_state.update({
                            'available': True,
                            'allocations': fresh_allocations,
                            'total_exposure': total_exposure,
                            'n_strategies': len(fresh_allocations),
                            'age_hours': 0,
                            'source': 'fresh_allocation'
                        })
                        print(f"   ✅ Fresh allocations computed for {len(fresh_allocations)} strategies")
                
                except Exception as e:
                    print(f"   ⚠️ Fresh allocation computation failed: {e}")
        
        except Exception as e:
            print(f"   ⚠️ Error getting capital allocations: {e}")
        
        if use_cache:
            self._set_cache(cache_key, allocation_state)
        
        return allocation_state
    
    def get_unified_intelligence_state(self, use_cache: bool = True) -> Dict[str, Any]:
        """Get unified intelligence state from all Phase 3 components"""
        
        cache_key = 'unified_intelligence_state'
        if use_cache:
            cached = self._get_cache(cache_key)
            if cached is not None:
                return cached
        
        print("🎯 GATHERING UNIFIED PHASE 3 INTELLIGENCE STATE")
        print("=" * 60)
        
        # Initialize components if needed
        if not any(self.integration_status.values()):
            self._initialize_component_interfaces()
        
        # Get state from each component
        regime_state = self.get_regime_state(use_cache=False)
        tailwind_state = self.get_strategy_tailwinds(use_cache=False)
        no_edge_state = self.get_no_edge_state(use_cache=False)
        allocation_state = self.get_capital_allocations(use_cache=False)
        
        # Calculate overall confidence
        component_confidences = [
            regime_state['confidence'] if regime_state['available'] else 0.1,
            0.8 if tailwind_state['available'] else 0.2,
            no_edge_state['confidence'] if no_edge_state['available'] else 0.3,
            0.9 if allocation_state['available'] else 0.1
        ]
        
        overall_confidence = sum(component_confidences) / len(component_confidences)
        
        # Create unified state
        unified_state = {
            'timestamp': datetime.now().isoformat(),
            'confidence': overall_confidence,
            'components_available': {
                'regime_memory': regime_state['available'],
                'tailwind_engine': tailwind_state['available'],
                'no_edge_detector': no_edge_state['available'],
                'capital_allocator': allocation_state['available']
            },
            'regime': regime_state,
            'tailwinds': tailwind_state,
            'no_edge': no_edge_state,
            'allocations': allocation_state,
            'integration_quality': {
                'data_freshness': self._calculate_data_freshness(regime_state, tailwind_state, 
                                                               no_edge_state, allocation_state),
                'component_consistency': self._check_component_consistency(regime_state, tailwind_state, 
                                                                         no_edge_state, allocation_state),
                'overall_health': self._assess_overall_health(regime_state, tailwind_state, 
                                                            no_edge_state, allocation_state)
            }
        }
        
        # Print summary
        print(f"\n📊 UNIFIED INTELLIGENCE STATE SUMMARY")
        print(f"   Overall Confidence: {overall_confidence:.1%}")
        print(f"   Components Available: {sum(unified_state['components_available'].values())}/4")
        print(f"   Data Freshness: {unified_state['integration_quality']['data_freshness']:.1%}")
        print(f"   Component Consistency: {unified_state['integration_quality']['component_consistency']:.1%}")
        print(f"   Overall Health: {unified_state['integration_quality']['overall_health']:.1%}")
        
        if use_cache:
            self._set_cache(cache_key, unified_state)
        
        return unified_state
    
    def _calculate_data_freshness(self, regime_state: Dict, tailwind_state: Dict, 
                                 no_edge_state: Dict, allocation_state: Dict) -> float:
        """Calculate overall data freshness score"""
        
        freshness_scores = []
        
        # Regime freshness (7 day max)
        if regime_state['available']:
            regime_freshness = max(0, 1 - (regime_state['age_days'] / 7))
            freshness_scores.append(regime_freshness)
        
        # Tailwind freshness (1 day max)
        if tailwind_state['available']:
            tailwind_freshness = max(0, 1 - (tailwind_state['age_days'] / 1))
            freshness_scores.append(tailwind_freshness)
        
        # NO_EDGE freshness (1 day max)
        if no_edge_state['available']:
            no_edge_freshness = max(0, 1 - (no_edge_state['age_days'] / 1))
            freshness_scores.append(no_edge_freshness)
        
        # Allocation freshness (6 hour max)
        if allocation_state['available']:
            allocation_freshness = max(0, 1 - (allocation_state['age_hours'] / 6))
            freshness_scores.append(allocation_freshness)
        
        return sum(freshness_scores) / len(freshness_scores) if freshness_scores else 0.0
    
    def _check_component_consistency(self, regime_state: Dict, tailwind_state: Dict, 
                                   no_edge_state: Dict, allocation_state: Dict) -> float:
        """Check consistency between components"""
        
        consistency_score = 1.0
        
        # Check regime consistency between components
        regimes = []
        if regime_state['available']:
            regimes.append(regime_state['regime'])
        if tailwind_state['available']:
            regimes.append(tailwind_state['regime'])
        if allocation_state['available'] and allocation_state['regime'] != 'Unknown':
            regimes.append(allocation_state['regime'])
        
        if len(regimes) > 1:
            # Check if all regimes match
            unique_regimes = set(regimes)
            if len(unique_regimes) > 1:
                consistency_score *= 0.8  # Penalty for regime mismatch
        
        # Check exposure consistency
        if no_edge_state['available'] and allocation_state['available']:
            exposure_cap = no_edge_state['exposure_cap']
            total_exposure = allocation_state['total_exposure']
            
            if total_exposure > exposure_cap + 0.05:  # 5% tolerance
                consistency_score *= 0.7  # Penalty for exposure cap violation
        
        return consistency_score
    
    def _assess_overall_health(self, regime_state: Dict, tailwind_state: Dict, 
                             no_edge_state: Dict, allocation_state: Dict) -> float:
        """Assess overall health of Phase 3 integration"""
        
        health_factors = []
        
        # Component availability
        available_components = sum([
            regime_state['available'],
            tailwind_state['available'],
            no_edge_state['available'],
            allocation_state['available']
        ])
        availability_score = available_components / 4
        health_factors.append(availability_score)
        
        # Data quality
        if regime_state['available']:
            regime_quality = regime_state['confidence']
            health_factors.append(regime_quality)
        
        if tailwind_state['available']:
            tailwind_quality = min(1.0, tailwind_state['n_strategies'] / 5)  # Expect at least 5 strategies
            health_factors.append(tailwind_quality)
        
        if no_edge_state['available']:
            no_edge_quality = no_edge_state['confidence']
            health_factors.append(no_edge_quality)
        
        if allocation_state['available']:
            allocation_quality = min(1.0, allocation_state['total_exposure'] / 0.5)  # Expect reasonable exposure
            health_factors.append(allocation_quality)
        
        return sum(health_factors) / len(health_factors) if health_factors else 0.0
    
    def validate_integration(self) -> Dict[str, Any]:
        """Validate Phase 3 integration health and provide diagnostics"""
        
        print("🔍 VALIDATING PHASE 3 INTEGRATION")
        print("=" * 50)
        
        # Get unified state
        unified_state = self.get_unified_intelligence_state(use_cache=False)
        
        validation_result = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'UNKNOWN',
            'confidence': unified_state['confidence'],
            'component_status': {},
            'integration_issues': [],
            'recommendations': [],
            'health_score': unified_state['integration_quality']['overall_health']
        }
        
        # Validate each component
        components = ['regime_memory', 'tailwind_engine', 'no_edge_detector', 'capital_allocator']
        
        for component in components:
            is_available = unified_state['components_available'][component]
            
            if is_available:
                validation_result['component_status'][component] = 'HEALTHY'
            else:
                validation_result['component_status'][component] = 'UNAVAILABLE'
                validation_result['integration_issues'].append(f"{component} is not available")
        
        # Check integration quality
        integration_quality = unified_state['integration_quality']
        
        if integration_quality['data_freshness'] < 0.5:
            validation_result['integration_issues'].append("Data freshness is low")
            validation_result['recommendations'].append("Update Phase 3 component data")
        
        if integration_quality['component_consistency'] < 0.8:
            validation_result['integration_issues'].append("Component consistency is low")
            validation_result['recommendations'].append("Check for regime/exposure mismatches")
        
        # Determine overall status
        if validation_result['health_score'] >= 0.8:
            validation_result['overall_status'] = 'HEALTHY'
        elif validation_result['health_score'] >= 0.5:
            validation_result['overall_status'] = 'DEGRADED'
        else:
            validation_result['overall_status'] = 'UNHEALTHY'
        
        # Print validation summary
        print(f"   Overall Status: {validation_result['overall_status']}")
        print(f"   Health Score: {validation_result['health_score']:.1%}")
        print(f"   Confidence: {validation_result['confidence']:.1%}")
        
        if validation_result['integration_issues']:
            print(f"   Issues: {len(validation_result['integration_issues'])}")
            for issue in validation_result['integration_issues'][:3]:
                print(f"     - {issue}")
        
        if validation_result['recommendations']:
            print(f"   Recommendations: {len(validation_result['recommendations'])}")
            for rec in validation_result['recommendations'][:3]:
                print(f"     - {rec}")
        
        return validation_result

def main():
    """Test Phase 3 Integration Layer"""
    
    integration_layer = Phase3IntegrationLayer()
    
    # Test unified intelligence state
    unified_state = integration_layer.get_unified_intelligence_state()
    
    print(f"\n🎯 Phase 3 Integration Layer Test Complete!")
    print(f"   Overall Confidence: {unified_state['confidence']:.1%}")
    print(f"   Components Available: {sum(unified_state['components_available'].values())}/4")
    
    # Validate integration
    validation = integration_layer.validate_integration()
    print(f"   Integration Status: {validation['overall_status']}")
    print(f"   Health Score: {validation['health_score']:.1%}")
    
    return unified_state

if __name__ == "__main__":
    main()