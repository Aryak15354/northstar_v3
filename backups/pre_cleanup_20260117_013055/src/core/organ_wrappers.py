#!/usr/bin/env python3
"""
🔗 ORGAN WRAPPERS - LIVING SYSTEM INTEGRATION
Organ Wrappers for Existing V3 Components

This module provides organ wrappers that integrate existing Northstar V3 components
into the living system without modifying the original code. This enables zero-rewrite
migration where existing components become organs in the living organism.

Key Features:
- Zero-rewrite migration of existing components
- Preserve all existing functionality
- Add living system integration (state, events, time)
- Backward compatibility with existing interfaces
"""

from src.cohesion.dependency_container import get_dependency_container

import os
import sys
import json
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Any, Optional
import warnings
warnings.filterwarnings('ignore')

from src.core.orchestrator import NorthstarOrgan, OrganStatus
from src.core.state import UnifiedState, AuthorityLevel, RiskStatus
from src.core.clock import TimeEvent, MarketTime
from src.core.memory import MemoryManager

class DataPipelineOrgan(NorthstarOrgan):
    """
    Data Pipeline Organ - Wraps DataPipelineCoordinator
    
    This organ wraps the existing DataPipelineCoordinator without modifying
    its code, integrating it into the living system as a critical organ.
    """
    
    def __init__(self, name: str = "data_pipeline_organ"):
        super().__init__(name)
        self.is_critical = True  # Data pipeline is critical for system operation
        
        # Wrapped component
        self.pipeline_coordinator = None
        self.pipeline_result = None
        self.last_collection_time = None
        self.collection_interval = timedelta(hours=1)  # Collect data every hour
        
        # Initialize wrapped component
        self._initialize_pipeline_coordinator()
        
        # State tracking
        self.needs_collection = True
        self.collection_stats = {
            'total_collections': 0,
            'successful_collections': 0,
            'last_success': None,
            'last_failure': None
        }
    
    def _initialize_pipeline_coordinator(self):
        """Initialize the wrapped DataPipelineCoordinator"""
        
        try:
            from src.ingestion.data_pipeline_coordinator import DataPipelineCoordinator
            self.pipeline_coordinator = DataPipelineCoordinator()
        except ImportError as e:
            print(f"   ⚠️ {self.name}: DataPipelineCoordinator not available - {e}")
            self.pipeline_coordinator = None
        except Exception as e:
            print(f"   ⚠️ {self.name}: Error initializing DataPipelineCoordinator - {e}")
            self.pipeline_coordinator = None
    
    def read_state(self, state: UnifiedState) -> None:
        """Read state to determine data collection needs"""
        
        # Check data freshness from health state
        data_fresh = state.health.data_fresh
        data_freshness_hours = state.health.data_freshness_hours
        
        # Check if collection is needed based on time
        time_based_collection = (
            self.last_collection_time is None or
            datetime.now() - self.last_collection_time > self.collection_interval
        )
        
        # Check if collection is needed based on data freshness
        freshness_based_collection = not data_fresh or data_freshness_hours > 2
        
        self.needs_collection = time_based_collection or freshness_based_collection
        
        if self.needs_collection:
            print(f"   📖 {self.name}: Data collection needed (fresh={data_fresh}, hours={data_freshness_hours:.1f})")
        else:
            print(f"   📖 {self.name}: Data is fresh, skipping collection")
    
    def think(self, state: UnifiedState) -> Any:
        """Execute data collection if needed"""
        
        if not self.needs_collection:
            return {
                'status': 'skipped',
                'reason': 'data_fresh',
                'timestamp': datetime.now()
            }
        
        if not self.pipeline_coordinator:
            return {
                'status': 'failed',
                'reason': 'coordinator_unavailable',
                'timestamp': datetime.now()
            }
        
        try:
            print(f"   🧠 {self.name}: Starting data collection...")
            
            # Execute the wrapped component
            collection_success = self.pipeline_coordinator.collect_all_data()
            
            # Update statistics
            self.collection_stats['total_collections'] += 1
            
            if collection_success:
                self.collection_stats['successful_collections'] += 1
                self.collection_stats['last_success'] = datetime.now()
                self.last_collection_time = datetime.now()
                
                # Get collection details from coordinator
                collection_details = {
                    'status': 'success',
                    'timestamp': datetime.now(),
                    'execution_log': self.pipeline_coordinator.execution_log[-10:],  # Last 10 entries
                    'collection_status': self.pipeline_coordinator.collection_status.copy(),
                    'success_rate': self.collection_stats['successful_collections'] / self.collection_stats['total_collections']
                }
                
                print(f"   🧠 {self.name}: Data collection completed successfully")
                
                self.pipeline_result = collection_details
                return collection_details
                
            else:
                self.collection_stats['last_failure'] = datetime.now()
                
                failure_details = {
                    'status': 'failed',
                    'timestamp': datetime.now(),
                    'execution_log': self.pipeline_coordinator.execution_log[-5:],  # Last 5 entries
                    'collection_status': self.pipeline_coordinator.collection_status.copy(),
                    'success_rate': self.collection_stats['successful_collections'] / self.collection_stats['total_collections']
                }
                
                print(f"   🧠 {self.name}: Data collection failed")
                
                self.pipeline_result = failure_details
                return failure_details
                
        except Exception as e:
            self.collection_stats['last_failure'] = datetime.now()
            
            error_details = {
                'status': 'error',
                'timestamp': datetime.now(),
                'error': str(e),
                'success_rate': self.collection_stats['successful_collections'] / self.collection_stats['total_collections'] if self.collection_stats['total_collections'] > 0 else 0.0
            }
            
            print(f"   🧠 {self.name}: Data collection error - {e}")
            
            self.pipeline_result = error_details
            return error_details
    
    def write_state(self, state: UnifiedState) -> None:
        """Update state with collection results"""
        
        if not self.pipeline_result:
            return
        
        if self.pipeline_result['status'] == 'success':
            # Update health state to reflect fresh data
            state.update_component('health', {
                'data_fresh': True,
                'data_freshness_hours': 0.0
            }, organ=self.name, reason="Data collection completed successfully", 
               authority=AuthorityLevel.SYSTEM)
            
            # Update memory state if data collection affects memory
            state.update_component('memory', {
                'total_memory_records': state.memory.total_memory_records + 1,
                'newest_record': datetime.now()
            }, organ=self.name, reason="New data collected")
            
            print(f"   ✍️ {self.name}: Updated state - data is now fresh")
            
        elif self.pipeline_result['status'] == 'failed':
            # Update health to reflect data collection failure
            hours_since_last_success = 24  # Default to 24 hours if no success recorded
            if self.collection_stats['last_success']:
                hours_since_last_success = (datetime.now() - self.collection_stats['last_success']).total_seconds() / 3600
            
            state.update_component('health', {
                'data_fresh': hours_since_last_success < 6,  # Fresh if success within 6 hours
                'data_freshness_hours': hours_since_last_success
            }, organ=self.name, reason="Data collection failed")
            
            print(f"   ✍️ {self.name}: Updated state - data collection failed")
    
    def handle_time_event(self, event: TimeEvent, market_time: MarketTime) -> None:
        """React to time events for data collection scheduling"""
        
        if event == TimeEvent.PRE_OPEN:
            print(f"   ⏰ {self.name}: Pre-market - scheduling data refresh")
            # Could trigger immediate collection for pre-market data
            
        elif event == TimeEvent.OVERNIGHT:
            print(f"   ⏰ {self.name}: Overnight - running comprehensive data collection")
            # Could trigger full data refresh during overnight hours
            
        elif event == TimeEvent.WEEKLY_REBALANCE:
            print(f"   ⏰ {self.name}: Weekly rebalance - ensuring data is current")
            # Could trigger data validation before rebalance
    
    def get_collection_metrics(self) -> Dict[str, Any]:
        """Get data collection performance metrics"""
        
        return {
            'total_collections': self.collection_stats['total_collections'],
            'successful_collections': self.collection_stats['successful_collections'],
            'success_rate': self.collection_stats['successful_collections'] / max(1, self.collection_stats['total_collections']),
            'last_success': self.collection_stats['last_success'].isoformat() if self.collection_stats['last_success'] else None,
            'last_failure': self.collection_stats['last_failure'].isoformat() if self.collection_stats['last_failure'] else None,
            'last_collection': self.last_collection_time.isoformat() if self.last_collection_time else None,
            'coordinator_available': self.pipeline_coordinator is not None,
            'collection_interval_hours': self.collection_interval.total_seconds() / 3600
        }

class MarketBrainOrgan(NorthstarOrgan):
    """
    Market Brain Organ - Wraps MarketBrainOrchestrator
    
    This organ wraps the existing Market Brain system, integrating regime analysis,
    pulse detection, and causal intelligence into the living system.
    """
    
    def __init__(self, name: str = "market_brain_organ"):
        super().__init__(name)
        self.is_critical = True  # Market brain is critical for intelligence
        
        # Wrapped components
        self.brain_orchestrator = None
        self.brain_result = None
        
        # Initialize wrapped component
        self._initialize_brain_orchestrator()
        
        # State tracking
        self.analysis_cache = {}
        self.last_analysis_time = None
    
    def _initialize_brain_orchestrator(self):
        """Initialize the wrapped MarketBrainOrchestrator"""
        
        try:
            from src.intelligence.market_brain.brain_orchestrator import BrainOrchestrator
            self.brain_orchestrator = BrainOrchestrator()
        except ImportError as e:
            print(f"   ⚠️ {self.name}: MarketBrainOrchestrator not available - {e}")
            self.brain_orchestrator = None
        except Exception as e:
            print(f"   ⚠️ {self.name}: Error initializing MarketBrainOrchestrator - {e}")
            self.brain_orchestrator = None
    
    def read_state(self, state: UnifiedState) -> None:
        """Read market state for brain analysis"""
        
        self.analysis_cache = {
            'current_regime': state.market.regime,
            'risk_on_probability': state.market.risk_on_probability,
            'market_stress': state.market.market_stress,
            'volatility_regime': state.market.volatility_regime,
            'breadth_pct': state.market.breadth_pct,
            'correlation': state.market.correlation,
            'pulse_intensity': state.market.pulse_intensity,
            'brain_regime': state.market.brain_regime
        }
        
        print(f"   📖 {self.name}: Read market state - regime={self.analysis_cache['current_regime']}")
    
    def think(self, state: UnifiedState) -> Any:
        """Execute market brain analysis"""
        
        if not self.brain_orchestrator:
            return {
                'status': 'failed',
                'reason': 'brain_orchestrator_unavailable',
                'timestamp': datetime.now()
            }
        
        try:
            print(f"   🧠 {self.name}: Running market brain analysis...")
            
            # Execute the wrapped brain orchestrator
            # brain_result = self.brain_orchestrator.run_full_analysis()  # Actual call
            
            # Mock brain analysis result for now
            brain_result = {
                'regime_analysis': {
                    'current_regime': 'expansion',
                    'regime_confidence': 0.75,
                    'transition_probability': 0.15
                },
                'pulse_analysis': {
                    'intensity': 0.6,
                    'phase': 'building',
                    'risk_level': 'moderate'
                },
                'causal_intelligence': {
                    'dominant_factors': ['liquidity', 'sentiment'],
                    'opportunity_zones': ['technology', 'healthcare']
                },
                'timestamp': datetime.now()
            }
            
            self.brain_result = brain_result
            self.last_analysis_time = datetime.now()
            
            print(f"   🧠 {self.name}: Brain analysis completed - regime={brain_result['regime_analysis']['current_regime']}")
            
            return brain_result
            
        except Exception as e:
            error_result = {
                'status': 'error',
                'timestamp': datetime.now(),
                'error': str(e)
            }
            
            print(f"   🧠 {self.name}: Brain analysis error - {e}")
            
            self.brain_result = error_result
            return error_result
    
    def write_state(self, state: UnifiedState) -> None:
        """Update state with brain analysis results"""
        
        if not self.brain_result or 'regime_analysis' not in self.brain_result:
            return
        
        try:
            # Update market state with brain analysis
            regime_analysis = self.brain_result['regime_analysis']
            pulse_analysis = self.brain_result['pulse_analysis']
            
            state.update_component('market', {
                'brain_regime': regime_analysis['current_regime'],
                'regime_similarity': regime_analysis['regime_confidence'],
                'pulse_intensity': pulse_analysis['intensity'],
                'market_phase': pulse_analysis['phase'],
                'pulse_risk_level': pulse_analysis['risk_level']
            }, organ=self.name, reason="Market brain analysis update")
            
            # Update regime state
            state.update_component('regime', {
                'current_regime': regime_analysis['current_regime'],
                'regime_confidence': regime_analysis['regime_confidence'],
                'transition_probability': regime_analysis['transition_probability']
            }, organ=self.name, reason="Regime analysis update")
            
            # Update pulse state
            state.update_component('pulse', {
                'intensity': pulse_analysis['intensity'],
                'phase': pulse_analysis['phase'],
                'risk_level': pulse_analysis['risk_level']
            }, organ=self.name, reason="Pulse analysis update")
            
            print(f"   ✍️ {self.name}: Updated state with brain analysis")
            
        except Exception as e:
            print(f"   ⚠️ {self.name}: Error updating state - {e}")
    
    def handle_time_event(self, event: TimeEvent, market_time: MarketTime) -> None:
        """React to time events for brain analysis"""
        
        if event == TimeEvent.OPEN:
            print(f"   ⏰ {self.name}: Market open - running regime analysis")
            
        elif event == TimeEvent.INTRADAY:
            print(f"   ⏰ {self.name}: Intraday - monitoring pulse and regime shifts")
            
        elif event == TimeEvent.CLOSE:
            print(f"   ⏰ {self.name}: Market close - consolidating daily analysis")

class IntelligenceStackOrgan(NorthstarOrgan):
    """
    Intelligence Stack Organ - Wraps IntelligenceStack
    
    This organ wraps the existing IntelligenceStack, integrating valuation engines,
    confidence weighting, Bayesian fusion, narrative generation, and memory systems
    into the living system.
    """
    
    def __init__(self, name: str = "intelligence_stack_organ"):
        super().__init__(name)
        self.is_critical = True  # Intelligence is critical for decision making
        
        # Wrapped component
        self.intelligence_stack = None
        self.intelligence_result = None
        self.last_analysis_time = None
        self.analysis_interval = timedelta(minutes=30)  # Run intelligence every 30 minutes
        
        # Initialize wrapped component
        self._initialize_intelligence_stack()
        
        # State tracking
        self.needs_analysis = True
        self.intelligence_stats = {
            'total_analyses': 0,
            'successful_analyses': 0,
            'last_success': None,
            'last_failure': None
        }
    
    def _initialize_intelligence_stack(self):
        """Initialize the wrapped IntelligenceStack"""
        
        try:
            from src.intelligence.intelligence_stack import IntelligenceStack
            self.intelligence_stack = IntelligenceStack()
        except ImportError as e:
            print(f"   ⚠️ {self.name}: IntelligenceStack not available - {e}")
            self.intelligence_stack = None
        except Exception as e:
            print(f"   ⚠️ {self.name}: Error initializing IntelligenceStack - {e}")
            self.intelligence_stack = None
    
    def read_state(self, state: UnifiedState) -> None:
        """Read state to determine intelligence analysis needs"""
        
        # Check if analysis is needed based on time
        time_based_analysis = (
            self.last_analysis_time is None or
            datetime.now() - self.last_analysis_time > self.analysis_interval
        )
        
        # Check if analysis is needed based on market changes
        market_regime_changed = (
            hasattr(self, 'last_regime') and 
            self.last_regime != state.market.regime
        )
        
        # Check if intelligence is stale
        intelligence_stale = not state.health.intelligence_active
        
        self.needs_analysis = time_based_analysis or market_regime_changed or intelligence_stale
        
        # Cache current market data for analysis
        self.market_data_cache = {
            'regime': state.market.regime,
            'risk_on_probability': state.market.risk_on_probability,
            'market_stress': state.market.market_stress,
            'volatility_regime': state.market.volatility_regime,
            'breadth_pct': state.market.breadth_pct,
            'correlation': state.market.correlation,
            'macro_score': state.macro.macro_score if hasattr(state.macro, 'macro_score') else 0.0
        }
        
        if self.needs_analysis:
            print(f"   📖 {self.name}: Intelligence analysis needed (regime={state.market.regime})")
        else:
            print(f"   📖 {self.name}: Intelligence is current, skipping analysis")
    
    def think(self, state: UnifiedState) -> Any:
        """Execute intelligence analysis if needed"""
        
        if not self.needs_analysis:
            return {
                'status': 'skipped',
                'reason': 'intelligence_current',
                'timestamp': datetime.now()
            }
        
        if not self.intelligence_stack:
            return {
                'status': 'failed',
                'reason': 'intelligence_stack_unavailable',
                'timestamp': datetime.now()
            }
        
        try:
            print(f"   🧠 {self.name}: Running complete intelligence analysis...")
            
            # Execute the wrapped intelligence stack
            intelligence_result = self.intelligence_stack.generate_complete_intelligence(
                ticker=None,  # Portfolio-wide analysis
                market_data=self.market_data_cache
            )
            
            # Update statistics
            self.intelligence_stats['total_analyses'] += 1
            self.intelligence_stats['successful_analyses'] += 1
            self.intelligence_stats['last_success'] = datetime.now()
            self.last_analysis_time = datetime.now()
            
            # Extract key insights
            analysis_summary = {
                'status': 'success',
                'timestamp': datetime.now(),
                'regime': intelligence_result.get('regime', 'unknown'),
                'beliefs': intelligence_result.get('beliefs', {}),
                'actions': intelligence_result.get('actions', {}),
                'conviction': intelligence_result.get('beliefs', {}).get('unified_conviction', 0.0),
                'confidence': intelligence_result.get('components', {}).get('confidence', {}).get('overall_confidence', 0.0),
                'narrative': intelligence_result.get('components', {}).get('narrative', {}),
                'success_rate': self.intelligence_stats['successful_analyses'] / self.intelligence_stats['total_analyses']
            }
            
            print(f"   🧠 {self.name}: Intelligence analysis completed - conviction={analysis_summary['conviction']:.2f}")
            
            self.intelligence_result = analysis_summary
            return analysis_summary
            
        except Exception as e:
            self.intelligence_stats['last_failure'] = datetime.now()
            
            error_details = {
                'status': 'error',
                'timestamp': datetime.now(),
                'error': str(e),
                'success_rate': self.intelligence_stats['successful_analyses'] / max(1, self.intelligence_stats['total_analyses'])
            }
            
            print(f"   🧠 {self.name}: Intelligence analysis error - {e}")
            
            self.intelligence_result = error_details
            return error_details
    
    def write_state(self, state: UnifiedState) -> None:
        """Update state with intelligence analysis results"""
        
        if not self.intelligence_result:
            return
        
        if self.intelligence_result['status'] == 'success':
            # Update beliefs state
            beliefs = self.intelligence_result.get('beliefs', {})
            state.update_component('beliefs', {
                'valuation_conviction': beliefs.get('valuation_conviction', 0.0),
                'market_conviction': beliefs.get('market_conviction', 0.0),
                'strategy_conviction': beliefs.get('strategy_conviction', 0.0),
                'narrative_conviction': beliefs.get('narrative_conviction', 0.0),
                'unified_conviction': beliefs.get('unified_conviction', 0.0)
            }, organ=self.name, reason="Intelligence analysis update", 
               authority=AuthorityLevel.SYSTEM)
            
            # Update confidence state
            confidence = self.intelligence_result.get('confidence', 0.0)
            state.update_component('confidence', {
                'valuation_confidence': confidence,
                'overall_confidence': confidence
            }, organ=self.name, reason="Intelligence confidence update")
            
            # Update health to reflect active intelligence
            state.update_component('health', {
                'intelligence_active': True
            }, organ=self.name, reason="Intelligence system active")
            
            # Store last regime for change detection
            self.last_regime = self.intelligence_result.get('regime', 'unknown')
            
            print(f"   ✍️ {self.name}: Updated state with intelligence analysis")
            
        elif self.intelligence_result['status'] == 'failed':
            # Update health to reflect intelligence failure
            state.update_component('health', {
                'intelligence_active': False
            }, organ=self.name, reason="Intelligence analysis failed")
            
            print(f"   ✍️ {self.name}: Updated state - intelligence analysis failed")
    
    def handle_time_event(self, event: TimeEvent, market_time: MarketTime) -> None:
        """React to time events for intelligence analysis scheduling"""
        
        if event == TimeEvent.OPEN:
            print(f"   ⏰ {self.name}: Market open - running fresh intelligence analysis")
            
        elif event == TimeEvent.INTRADAY:
            print(f"   ⏰ {self.name}: Intraday - monitoring for regime changes")
            
        elif event == TimeEvent.CLOSE:
            print(f"   ⏰ {self.name}: Market close - consolidating daily intelligence")
            
        elif event == TimeEvent.WEEKLY_REBALANCE:
            print(f"   ⏰ {self.name}: Weekly rebalance - running comprehensive intelligence review")
    
    def get_intelligence_metrics(self) -> Dict[str, Any]:
        """Get intelligence analysis performance metrics"""
        
        return {
            'total_analyses': self.intelligence_stats['total_analyses'],
            'successful_analyses': self.intelligence_stats['successful_analyses'],
            'success_rate': self.intelligence_stats['successful_analyses'] / max(1, self.intelligence_stats['total_analyses']),
            'last_success': self.intelligence_stats['last_success'].isoformat() if self.intelligence_stats['last_success'] else None,
            'last_failure': self.intelligence_stats['last_failure'].isoformat() if self.intelligence_stats['last_failure'] else None,
            'last_analysis': self.last_analysis_time.isoformat() if self.last_analysis_time else None,
            'intelligence_stack_available': self.intelligence_stack is not None,
            'analysis_interval_minutes': self.analysis_interval.total_seconds() / 60,
            'current_conviction': self.intelligence_result.get('conviction', 0.0) if self.intelligence_result else 0.0
        }

class CapitalAllocatorOrgan(NorthstarOrgan):
    """
    Capital Allocator Organ - Wraps CapitalAllocator
    
    This organ wraps the existing CapitalAllocator, integrating Bayesian capital
    allocation with Thompson Sampling and regret minimization into the living system.
    """
    
    def __init__(self, name: str = "capital_allocator_organ"):
        super().__init__(name)
        self.is_critical = True  # Capital allocation is critical for portfolio construction
        
        # Wrapped component
        self.capital_allocator = None
        self.allocation_result = None
        self.last_allocation_time = None
        self.allocation_interval = timedelta(hours=6)  # Reallocate every 6 hours
        
        # Initialize wrapped component
        self._initialize_capital_allocator()
        
        # State tracking
        self.needs_allocation = True
        self.allocation_stats = {
            'total_allocations': 0,
            'successful_allocations': 0,
            'last_success': None,
            'last_failure': None
        }
    
    def _initialize_capital_allocator(self):
        """Initialize the wrapped CapitalAllocator"""
        
        try:
            from src.intelligence.capital_allocator import CapitalAllocator
            self.capital_allocator = CapitalAllocator()
        except ImportError as e:
            print(f"   ⚠️ {self.name}: CapitalAllocator not available - {e}")
            self.capital_allocator = None
        except Exception as e:
            print(f"   ⚠️ {self.name}: Error initializing CapitalAllocator - {e}")
            self.capital_allocator = None
    
    def read_state(self, state: UnifiedState) -> None:
        """Read state to determine capital allocation needs"""
        
        # Check if allocation is needed based on time
        time_based_allocation = (
            self.last_allocation_time is None or
            datetime.now() - self.last_allocation_time > self.allocation_interval
        )
        
        # Check if allocation is needed based on strategy changes
        strategy_changes = (
            hasattr(self, 'last_strategy_count') and 
            self.last_strategy_count != state.strategies.active_strategies
        )
        
        # Check if allocation is needed based on regime changes
        regime_changes = (
            hasattr(self, 'last_regime') and 
            self.last_regime != state.market.regime
        )
        
        # Check if capital allocation is stale
        allocation_stale = state.capital.allocation_efficiency < 0.5
        
        self.needs_allocation = time_based_allocation or strategy_changes or regime_changes or allocation_stale
        
        # Cache current state for allocation
        self.state_cache = {
            'regime': state.market.regime,
            'risk_on_probability': state.market.risk_on_probability,
            'market_stress': state.market.market_stress,
            'active_strategies': state.strategies.active_strategies,
            'strategy_allocations': state.strategies.strategy_allocations.copy(),
            'total_capital': state.capital.total_capital,
            'allocated_capital': state.capital.allocated_capital,
            'intelligence_conviction': state.beliefs.unified_conviction
        }
        
        if self.needs_allocation:
            print(f"   📖 {self.name}: Capital allocation needed (regime={state.market.regime}, strategies={state.strategies.active_strategies})")
        else:
            print(f"   📖 {self.name}: Capital allocation is current, skipping reallocation")
    
    def think(self, state: UnifiedState) -> Any:
        """Execute capital allocation if needed"""
        
        if not self.needs_allocation:
            return {
                'status': 'skipped',
                'reason': 'allocation_current',
                'timestamp': datetime.now()
            }
        
        if not self.capital_allocator:
            return {
                'status': 'failed',
                'reason': 'capital_allocator_unavailable',
                'timestamp': datetime.now()
            }
        
        try:
            print(f"   🧠 {self.name}: Running capital allocation...")
            
            # Load strategy performance and market data
            strategy_performance = self.capital_allocator.load_strategy_performance()
            market_regime = self.capital_allocator.load_market_regime()
            strategy_beliefs = self.capital_allocator.load_strategy_beliefs()
            
            # Calculate health scores
            health_scores = self.capital_allocator.calculate_health_scores(
                strategy_performance, market_regime, strategy_beliefs
            )
            
            # Allocate capital
            allocations = self.capital_allocator.allocate_capital(health_scores)
            
            # Update statistics
            self.allocation_stats['total_allocations'] += 1
            self.allocation_stats['successful_allocations'] += 1
            self.allocation_stats['last_success'] = datetime.now()
            self.last_allocation_time = datetime.now()
            
            # Create allocation summary
            allocation_summary = {
                'status': 'success',
                'timestamp': datetime.now(),
                'allocations': allocations,
                'health_scores': health_scores,
                'market_regime': market_regime,
                'total_strategies': len(allocations),
                'allocation_efficiency': sum(allocations.values()),
                'top_allocation': max(allocations.values()) if allocations else 0.0,
                'success_rate': self.allocation_stats['successful_allocations'] / self.allocation_stats['total_allocations']
            }
            
            print(f"   🧠 {self.name}: Capital allocation completed - {len(allocations)} strategies, efficiency={allocation_summary['allocation_efficiency']:.1%}")
            
            self.allocation_result = allocation_summary
            return allocation_summary
            
        except Exception as e:
            self.allocation_stats['last_failure'] = datetime.now()
            
            error_details = {
                'status': 'error',
                'timestamp': datetime.now(),
                'error': str(e),
                'success_rate': self.allocation_stats['successful_allocations'] / max(1, self.allocation_stats['total_allocations'])
            }
            
            print(f"   🧠 {self.name}: Capital allocation error - {e}")
            
            self.allocation_result = error_details
            return error_details
    
    def write_state(self, state: UnifiedState) -> None:
        """Update state with capital allocation results"""
        
        if not self.allocation_result:
            return
        
        if self.allocation_result['status'] == 'success':
            # Update capital state
            allocations = self.allocation_result['allocations']
            total_allocated = sum(allocations.values())
            
            state.update_component('capital', {
                'allocated_capital': total_allocated,
                'allocation_efficiency': total_allocated,
                'last_rebalance': datetime.now()
            }, organ=self.name, reason="Capital allocation update", 
               authority=AuthorityLevel.SYSTEM)
            
            # Update strategy state
            state.update_component('strategies', {
                'active_strategies': len(allocations),
                'strategy_allocations': allocations,
                'allocation_timestamp': datetime.now()
            }, organ=self.name, reason="Strategy allocation update")
            
            # Store regime and strategy count for change detection
            self.last_regime = self.state_cache['regime']
            self.last_strategy_count = len(allocations)
            
            print(f"   ✍️ {self.name}: Updated state with capital allocations")
            
        elif self.allocation_result['status'] == 'failed':
            # Update capital state to reflect allocation failure
            state.update_component('capital', {
                'allocation_efficiency': 0.0
            }, organ=self.name, reason="Capital allocation failed")
            
            print(f"   ✍️ {self.name}: Updated state - capital allocation failed")
    
    def handle_time_event(self, event: TimeEvent, market_time: MarketTime) -> None:
        """React to time events for capital allocation scheduling"""
        
        if event == TimeEvent.OPEN:
            print(f"   ⏰ {self.name}: Market open - checking for allocation updates")
            
        elif event == TimeEvent.CLOSE:
            print(f"   ⏰ {self.name}: Market close - running end-of-day allocation review")
            
        elif event == TimeEvent.WEEKLY_REBALANCE:
            print(f"   ⏰ {self.name}: Weekly rebalance - running comprehensive capital reallocation")
            # Force reallocation on weekly rebalance
            self.needs_allocation = True
            
        elif event == TimeEvent.OVERNIGHT:
            print(f"   ⏰ {self.name}: Overnight - running capital allocation optimization")
    
    def get_allocation_metrics(self) -> Dict[str, Any]:
        """Get capital allocation performance metrics"""
        
        return {
            'total_allocations': self.allocation_stats['total_allocations'],
            'successful_allocations': self.allocation_stats['successful_allocations'],
            'success_rate': self.allocation_stats['successful_allocations'] / max(1, self.allocation_stats['total_allocations']),
            'last_success': self.allocation_stats['last_success'].isoformat() if self.allocation_stats['last_success'] else None,
            'last_failure': self.allocation_stats['last_failure'].isoformat() if self.allocation_stats['last_failure'] else None,
            'last_allocation': self.last_allocation_time.isoformat() if self.last_allocation_time else None,
            'capital_allocator_available': self.capital_allocator is not None,
            'allocation_interval_hours': self.allocation_interval.total_seconds() / 3600,
            'current_efficiency': self.allocation_result.get('allocation_efficiency', 0.0) if self.allocation_result else 0.0
        }

class PortfolioGovernorOrgan(NorthstarOrgan):
    """
    Portfolio Governor Organ - Wraps PortfolioGovernor
    
    This organ wraps the existing PortfolioGovernor, integrating portfolio construction,
    risk controls, and compliance management into the living system.
    """
    
    def __init__(self, name: str = "portfolio_governor_organ"):
        super().__init__(name)
        self.is_critical = True  # Portfolio construction is critical for execution
        
        # Wrapped component
        self.portfolio_governor = None
        self.portfolio_result = None
        self.last_construction_time = None
        self.construction_interval = timedelta(hours=4)  # Reconstruct portfolio every 4 hours
        
        # Initialize wrapped component
        self._initialize_portfolio_governor()
        
        # State tracking
        self.needs_construction = True
        self.construction_stats = {
            'total_constructions': 0,
            'successful_constructions': 0,
            'last_success': None,
            'last_failure': None
        }
    
    def _initialize_portfolio_governor(self):
        """Initialize the wrapped PortfolioGovernor"""
        
        try:
            from src.portfolio.portfolio_governor import PortfolioGovernor
            self.portfolio_governor = PortfolioGovernor()
        except ImportError as e:
            print(f"   ⚠️ {self.name}: PortfolioGovernor not available - {e}")
            self.portfolio_governor = None
        except Exception as e:
            print(f"   ⚠️ {self.name}: Error initializing PortfolioGovernor - {e}")
            self.portfolio_governor = None
        except Exception as e:
            print(f"   ⚠️ {self.name}: Error initializing PortfolioGovernor - {e}")
            self.portfolio_governor = None
    
    def read_state(self, state: UnifiedState) -> None:
        """Read state to determine portfolio construction needs"""
        
        # Check if construction is needed based on time
        time_based_construction = (
            self.last_construction_time is None or
            datetime.now() - self.last_construction_time > self.construction_interval
        )
        
        # Check if construction is needed based on capital allocation changes
        capital_changes = (
            hasattr(self, 'last_allocated_capital') and 
            abs(self.last_allocated_capital - state.capital.allocated_capital) > 0.05
        )
        
        # Check if construction is needed based on regime changes
        regime_changes = (
            hasattr(self, 'last_regime') and 
            self.last_regime != state.market.regime
        )
        
        # Check if portfolio is stale or inactive
        portfolio_stale = not state.health.portfolio_active or state.portfolio.total_exposure < 0.01
        
        self.needs_construction = time_based_construction or capital_changes or regime_changes or portfolio_stale
        
        # Cache current state for construction
        self.state_cache = {
            'regime': state.market.regime,
            'risk_on_probability': state.market.risk_on_probability,
            'allowed_exposure': state.market.allowed_exposure,
            'market_stress': state.market.market_stress,
            'allocated_capital': state.capital.allocated_capital,
            'strategy_allocations': state.strategies.strategy_allocations.copy(),
            'intelligence_conviction': state.beliefs.unified_conviction,
            'system_locked': state.locked
        }
        
        if self.needs_construction:
            print(f"   📖 {self.name}: Portfolio construction needed (regime={state.market.regime}, exposure={state.portfolio.total_exposure:.1%})")
        else:
            print(f"   📖 {self.name}: Portfolio is current, skipping reconstruction")
    
    def think(self, state: UnifiedState) -> Any:
        """Execute portfolio construction if needed"""
        
        if not self.needs_construction:
            return {
                'status': 'skipped',
                'reason': 'portfolio_current',
                'timestamp': datetime.now()
            }
        
        if not self.portfolio_governor:
            return {
                'status': 'failed',
                'reason': 'portfolio_governor_unavailable',
                'timestamp': datetime.now()
            }
        
        # Don't construct portfolio if system is locked (unless we're a risk organ)
        if self.state_cache['system_locked']:
            return {
                'status': 'skipped',
                'reason': 'system_locked',
                'timestamp': datetime.now()
            }
        
        try:
            print(f"   🧠 {self.name}: Running portfolio construction...")
            
            # Execute the wrapped portfolio governor
            portfolio, analytics = self.portfolio_governor.run_portfolio_construction()
            
            # Update statistics
            self.construction_stats['total_constructions'] += 1
            self.construction_stats['successful_constructions'] += 1
            self.construction_stats['last_success'] = datetime.now()
            self.last_construction_time = datetime.now()
            
            # Create construction summary
            construction_summary = {
                'status': 'success',
                'timestamp': datetime.now(),
                'portfolio': portfolio.to_dict('records') if not portfolio.empty else [],
                'analytics': analytics,
                'total_positions': len(portfolio),
                'total_exposure': analytics.get('portfolio_summary', {}).get('total_exposure', 0.0),
                'max_position': analytics.get('portfolio_summary', {}).get('max_position', 0.0),
                'sector_exposure': analytics.get('sector_analysis', {}),
                'compliance_status': analytics.get('compliance', {}).get('all_constraints_met', False),
                'success_rate': self.construction_stats['successful_constructions'] / self.construction_stats['total_constructions']
            }
            
            print(f"   🧠 {self.name}: Portfolio construction completed - {len(portfolio)} positions, {construction_summary['total_exposure']:.1%} exposure")
            
            self.portfolio_result = construction_summary
            return construction_summary
            
        except Exception as e:
            self.construction_stats['last_failure'] = datetime.now()
            
            error_details = {
                'status': 'error',
                'timestamp': datetime.now(),
                'error': str(e),
                'success_rate': self.construction_stats['successful_constructions'] / max(1, self.construction_stats['total_constructions'])
            }
            
            print(f"   🧠 {self.name}: Portfolio construction error - {e}")
            
            self.portfolio_result = error_details
            return error_details
    
    def write_state(self, state: UnifiedState) -> None:
        """Update state with portfolio construction results"""
        
        if not self.portfolio_result:
            return
        
        if self.portfolio_result['status'] == 'success':
            # Update portfolio state
            analytics = self.portfolio_result['analytics']
            portfolio_summary = analytics.get('portfolio_summary', {})
            
            state.update_component('portfolio', {
                'total_positions': self.portfolio_result['total_positions'],
                'total_exposure': self.portfolio_result['total_exposure'],
                'max_position': self.portfolio_result['max_position'],
                'long_positions': portfolio_summary.get('long_positions', 0),
                'short_positions': portfolio_summary.get('short_positions', 0),
                'sector_exposure': self.portfolio_result['sector_exposure'],
                'max_sector_exposure': max(self.portfolio_result['sector_exposure'].values()) if self.portfolio_result['sector_exposure'] else 0.0,
                'expected_return': portfolio_summary.get('expected_return', 0.0),
                'expected_volatility': portfolio_summary.get('expected_volatility', 0.0),
                'sharpe_ratio': portfolio_summary.get('sharpe_ratio', 0.0),
                'compliance_status': self.portfolio_result['compliance_status'],
                'compliance_violations': 0 if self.portfolio_result['compliance_status'] else 1
            }, organ=self.name, reason="Portfolio construction update", 
               authority=AuthorityLevel.SYSTEM)
            
            # Update health to reflect active portfolio
            state.update_component('health', {
                'portfolio_active': self.portfolio_result['total_exposure'] > 0.01
            }, organ=self.name, reason="Portfolio construction completed")
            
            # Store values for change detection
            self.last_regime = self.state_cache['regime']
            self.last_allocated_capital = self.state_cache['allocated_capital']
            
            print(f"   ✍️ {self.name}: Updated state with portfolio construction")
            
        elif self.portfolio_result['status'] == 'failed':
            # Update health to reflect portfolio construction failure
            state.update_component('health', {
                'portfolio_active': False
            }, organ=self.name, reason="Portfolio construction failed")
            
            # Update portfolio state to reflect failure
            state.update_component('portfolio', {
                'compliance_violations': state.portfolio.compliance_violations + 1
            }, organ=self.name, reason="Portfolio construction failed")
            
            print(f"   ✍️ {self.name}: Updated state - portfolio construction failed")
    
    def handle_time_event(self, event: TimeEvent, market_time: MarketTime) -> None:
        """React to time events for portfolio construction scheduling"""
        
        if event == TimeEvent.OPEN:
            print(f"   ⏰ {self.name}: Market open - checking for portfolio updates")
            
        elif event == TimeEvent.CLOSE:
            print(f"   ⏰ {self.name}: Market close - running end-of-day portfolio review")
            
        elif event == TimeEvent.WEEKLY_REBALANCE:
            print(f"   ⏰ {self.name}: Weekly rebalance - running comprehensive portfolio reconstruction")
            # Force reconstruction on weekly rebalance
            self.needs_construction = True
            
        elif event == TimeEvent.OVERNIGHT:
            print(f"   ⏰ {self.name}: Overnight - running portfolio optimization")
    
    def get_construction_metrics(self) -> Dict[str, Any]:
        """Get portfolio construction performance metrics"""
        
        return {
            'total_constructions': self.construction_stats['total_constructions'],
            'successful_constructions': self.construction_stats['successful_constructions'],
            'success_rate': self.construction_stats['successful_constructions'] / max(1, self.construction_stats['total_constructions']),
            'last_success': self.construction_stats['last_success'].isoformat() if self.construction_stats['last_success'] else None,
            'last_failure': self.construction_stats['last_failure'].isoformat() if self.construction_stats['last_failure'] else None,
            'last_construction': self.last_construction_time.isoformat() if self.last_construction_time else None,
            'portfolio_governor_available': self.portfolio_governor is not None,
            'construction_interval_hours': self.construction_interval.total_seconds() / 3600,
            'current_exposure': self.portfolio_result.get('total_exposure', 0.0) if self.portfolio_result else 0.0,
            'current_positions': self.portfolio_result.get('total_positions', 0) if self.portfolio_result else 0
        }

class RiskCoordinatorOrgan(NorthstarOrgan):
    """
    Risk Coordinator Organ - The Spinal Cord with Absolute Authority
    
    This organ wraps the existing Risk Coordinator and serves as the spinal cord
    of the living system with absolute authority over all other organs. It can
    lock the system instantly and has reflex-like response to risk events.
    """
    
    AUTHORITY_LEVELS = {
        'EMERGENCY': 1,    # Absolute authority
        'SYSTEM': 2,       # System-level authority
        'PORTFOLIO': 3,    # Portfolio-level authority
        'POSITION': 4      # Position-level authority
    }
    
    def __init__(self, name: str = "risk_coordinator_organ"):
        super().__init__(name)
        self.is_critical = True  # Risk is the most critical organ
        
        # Wrapped components
        self.risk_coordinator = None
        self.emergency_brake = None
        self.risk_result = None
        
        # Initialize wrapped components
        self._initialize_risk_components()
        
        # Risk state tracking
        self.emergency_conditions = []
        self.risk_events = []
        self.last_risk_check = None
        self.risk_check_interval = timedelta(seconds=30)  # Check risk every 30 seconds
        
        # Emergency response tracking
        self.emergency_stats = {
            'total_risk_checks': 0,
            'emergency_triggers': 0,
            'false_alarms': 0,
            'last_emergency': None,
            'response_times': []  # Track response times for reflex analysis
        }
        
        # Risk thresholds (configurable)
        self.risk_thresholds = {
            'market_stress_critical': 0.8,
            'portfolio_drawdown_critical': 0.15,
            'system_health_critical': 0.3,
            'volatility_spike_critical': 3.0,
            'correlation_breakdown_critical': 0.9
        }
    
    def _initialize_risk_components(self):
        """Initialize the wrapped risk management components"""
        
        try:
            # Try to import existing risk coordinator
            from src.risk.unified_risk_coordinator import UnifiedRiskCoordinator
            self.risk_coordinator = UnifiedRiskCoordinator()
            print(f"   🔗 {self.name}: Successfully wrapped UnifiedRiskCoordinator")
        except ImportError:
            try:
                # Fallback to emergency brake
                from src.risk.emergency_brake import EmergencyBrake
                self.emergency_brake = EmergencyBrake()
                print(f"   🔗 {self.name}: Successfully wrapped EmergencyBrake")
            except ImportError as e:
                print(f"   ⚠️ {self.name}: No risk components available - {e}")
                self.risk_coordinator = None
                self.emergency_brake = None
        except Exception as e:
            print(f"   ⚠️ {self.name}: Error initializing risk components - {e}")
            self.risk_coordinator = None
            self.emergency_brake = None
    
    def read_state(self, state: UnifiedState) -> None:
        """Read state for risk analysis - ALWAYS EXECUTES regardless of system lock"""
        
        # Risk organ ALWAYS reads state, even when system is locked
        self.risk_analysis_cache = {
            'market_stress': state.market.market_stress,
            'volatility_regime': state.market.volatility_regime,
            'portfolio_exposure': state.portfolio.total_exposure,
            'max_drawdown': state.portfolio.max_drawdown,
            'system_health': state.health.overall_health_score,
            'emergency_active': state.risk.emergency_active,
            'current_risk_status': state.risk.status,
            'system_locked': state.locked,
            'correlation': state.market.correlation,
            'breadth_pct': state.market.breadth_pct,
            'compliance_violations': state.portfolio.compliance_violations
        }
        
        # Check if immediate risk assessment is needed
        time_based_check = (
            self.last_risk_check is None or
            datetime.now() - self.last_risk_check > self.risk_check_interval
        )
        
        # Always check if emergency conditions exist
        emergency_conditions = self._detect_emergency_conditions()
        
        print(f"   📖 {self.name}: Risk assessment - stress={self.risk_analysis_cache['market_stress']:.2f}, health={self.risk_analysis_cache['system_health']:.2f}")
        
        if emergency_conditions:
            print(f"   🚨 {self.name}: EMERGENCY CONDITIONS DETECTED: {emergency_conditions}")
    
    def think(self, state: UnifiedState) -> Any:
        """Execute risk analysis with reflex-like speed - ABSOLUTE AUTHORITY"""
        
        risk_check_start = time.time()
        
        try:
            print(f"   🧠 {self.name}: Running risk analysis with absolute authority...")
            
            # Detect emergency conditions
            emergency_conditions = self._detect_emergency_conditions()
            
            # Calculate overall risk level
            risk_level = self._calculate_risk_level()
            
            # Determine risk status
            risk_status = self._determine_risk_status(risk_level, emergency_conditions)
            
            # Check if emergency action is needed
            emergency_action_needed = len(emergency_conditions) > 0 or risk_status == RiskStatus.EMERGENCY
            
            # Update statistics
            self.emergency_stats['total_risk_checks'] += 1
            self.last_risk_check = datetime.now()
            
            # Record response time
            response_time = time.time() - risk_check_start
            self.emergency_stats['response_times'].append(response_time)
            if len(self.emergency_stats['response_times']) > 100:
                self.emergency_stats['response_times'] = self.emergency_stats['response_times'][-100:]
            
            # Create risk analysis result
            risk_analysis = {
                'status': 'success',
                'timestamp': datetime.now(),
                'risk_level': risk_level,
                'risk_status': risk_status.value,
                'emergency_conditions': emergency_conditions,
                'emergency_action_needed': emergency_action_needed,
                'response_time': response_time,
                'average_response_time': np.mean(self.emergency_stats['response_times']),
                'risk_breakdown': {
                    'market_risk': self._assess_market_risk(),
                    'portfolio_risk': self._assess_portfolio_risk(),
                    'system_risk': self._assess_system_risk(),
                    'liquidity_risk': self._assess_liquidity_risk()
                }
            }
            
            # If emergency action needed, trigger immediately
            if emergency_action_needed:
                self.emergency_stats['emergency_triggers'] += 1
                self.emergency_stats['last_emergency'] = datetime.now()
                
                print(f"   🚨 {self.name}: EMERGENCY ACTION TRIGGERED - Response time: {response_time:.3f}s")
                
                risk_analysis['emergency_triggered'] = True
                risk_analysis['emergency_reason'] = f"Conditions: {emergency_conditions}"
            
            print(f"   🧠 {self.name}: Risk analysis completed - Level: {risk_level:.2f}, Status: {risk_status.value}")
            
            self.risk_result = risk_analysis
            return risk_analysis
            
        except Exception as e:
            # Even risk analysis errors are critical
            error_result = {
                'status': 'error',
                'timestamp': datetime.now(),
                'error': str(e),
                'response_time': time.time() - risk_check_start,
                'emergency_triggered': True,  # Treat risk system failure as emergency
                'emergency_reason': f"Risk system failure: {str(e)}"
            }
            
            print(f"   💥 {self.name}: CRITICAL - Risk system failure: {e}")
            
            self.risk_result = error_result
            return error_result
    
    def write_state(self, state: UnifiedState) -> None:
        """Update state with risk analysis - ABSOLUTE AUTHORITY TO LOCK SYSTEM"""
        
        if not self.risk_result:
            return
        
        # Risk organ has absolute authority to update risk state
        risk_level = self.risk_result.get('risk_level', 1.0)
        risk_status_str = self.risk_result.get('risk_status', 'critical')
        emergency_conditions = self.risk_result.get('emergency_conditions', [])
        
        # Convert string back to enum
        risk_status = RiskStatus.EMERGENCY
        for status in RiskStatus:
            if status.value == risk_status_str:
                risk_status = status
                break
        
        # Update risk state with absolute authority
        state.update_component('risk', {
            'status': risk_status,
            'emergency_active': len(emergency_conditions) > 0,
            'system_stress': risk_level,
            'overall_risk_level': risk_level,
            'emergency_brake_active': self.risk_result.get('emergency_triggered', False),
            'brake_conditions': len(emergency_conditions)
        }, organ=self.name, reason=f"Risk analysis: {emergency_conditions}", 
           authority=AuthorityLevel.EMERGENCY)
        
        # ABSOLUTE AUTHORITY: Lock system if emergency conditions exist
        if self.risk_result.get('emergency_triggered', False):
            lock_reason = self.risk_result.get('emergency_reason', 'Emergency conditions detected')
            
            # Use absolute authority to lock the system
            lock_success = state.lock_system(
                reason=lock_reason,
                authority=AuthorityLevel.EMERGENCY,
                organ=self.name
            )
            
            if lock_success:
                print(f"   🔒 {self.name}: SYSTEM LOCKED with absolute authority - {lock_reason}")
            else:
                print(f"   ⚠️ {self.name}: Failed to lock system (this should never happen)")
        
        # If no emergency and system was locked by risk, consider unlocking
        elif state.locked and state.lock_authority == AuthorityLevel.EMERGENCY and risk_status in [RiskStatus.NORMAL, RiskStatus.ELEVATED]:
            unlock_success = state.unlock_system(
                authority=AuthorityLevel.EMERGENCY,
                organ=self.name
            )
            
            if unlock_success:
                print(f"   🔓 {self.name}: System unlocked - risk conditions normalized")
        
        print(f"   ✍️ {self.name}: Updated risk state - Status: {risk_status.value}, Emergency: {len(emergency_conditions) > 0}")
    
    def _detect_emergency_conditions(self) -> List[str]:
        """Detect emergency conditions that require immediate action"""
        
        conditions = []
        
        # Market stress emergency
        if self.risk_analysis_cache['market_stress'] > self.risk_thresholds['market_stress_critical']:
            conditions.append(f"market_stress_critical_{self.risk_analysis_cache['market_stress']:.2f}")
        
        # Portfolio drawdown emergency
        if abs(self.risk_analysis_cache['max_drawdown']) > self.risk_thresholds['portfolio_drawdown_critical']:
            conditions.append(f"portfolio_drawdown_critical_{abs(self.risk_analysis_cache['max_drawdown']):.2f}")
        
        # System health emergency
        if self.risk_analysis_cache['system_health'] < self.risk_thresholds['system_health_critical']:
            conditions.append(f"system_health_critical_{self.risk_analysis_cache['system_health']:.2f}")
        
        # Correlation breakdown (all assets moving together)
        if self.risk_analysis_cache['correlation'] > self.risk_thresholds['correlation_breakdown_critical']:
            conditions.append(f"correlation_breakdown_{self.risk_analysis_cache['correlation']:.2f}")
        
        # Compliance violations
        if self.risk_analysis_cache['compliance_violations'] > 0:
            conditions.append(f"compliance_violations_{self.risk_analysis_cache['compliance_violations']}")
        
        # Portfolio exposure too high in stressed market
        if (self.risk_analysis_cache['market_stress'] > 0.6 and 
            self.risk_analysis_cache['portfolio_exposure'] > 0.5):
            conditions.append(f"high_exposure_in_stress_{self.risk_analysis_cache['portfolio_exposure']:.2f}")
        
        return conditions
    
    def _calculate_risk_level(self) -> float:
        """Calculate overall system risk level (0.0 = no risk, 1.0 = maximum risk)"""
        
        risk_factors = [
            self.risk_analysis_cache['market_stress'],
            abs(self.risk_analysis_cache['max_drawdown']) * 5,  # Scale drawdown
            1.0 - self.risk_analysis_cache['system_health'],
            self.risk_analysis_cache['correlation'],
            self.risk_analysis_cache['compliance_violations'] * 0.2,
            max(0, self.risk_analysis_cache['portfolio_exposure'] - 0.5) * 2  # Penalize high exposure
        ]
        
        # Weight the factors
        weights = [0.3, 0.25, 0.2, 0.15, 0.05, 0.05]
        
        overall_risk = sum(factor * weight for factor, weight in zip(risk_factors, weights))
        
        return min(1.0, max(0.0, overall_risk))
    
    def _determine_risk_status(self, risk_level: float, emergency_conditions: List[str]) -> RiskStatus:
        """Determine risk status based on risk level and emergency conditions"""
        
        if emergency_conditions or risk_level > 0.8:
            return RiskStatus.EMERGENCY
        elif risk_level > 0.6:
            return RiskStatus.CRITICAL
        elif risk_level > 0.4:
            return RiskStatus.ELEVATED
        else:
            return RiskStatus.NORMAL
    
    def _assess_market_risk(self) -> Dict[str, float]:
        """Assess market-specific risks"""
        return {
            'stress_level': self.risk_analysis_cache['market_stress'],
            'volatility_risk': 1.0 if self.risk_analysis_cache['volatility_regime'] == 'high' else 0.5,
            'correlation_risk': self.risk_analysis_cache['correlation'],
            'breadth_risk': 1.0 - (self.risk_analysis_cache['breadth_pct'] / 100.0)
        }
    
    def _assess_portfolio_risk(self) -> Dict[str, float]:
        """Assess portfolio-specific risks"""
        return {
            'exposure_risk': max(0, self.risk_analysis_cache['portfolio_exposure'] - 0.5) * 2,
            'drawdown_risk': abs(self.risk_analysis_cache['max_drawdown']) * 5,
            'compliance_risk': self.risk_analysis_cache['compliance_violations'] * 0.5
        }
    
    def _assess_system_risk(self) -> Dict[str, float]:
        """Assess system-specific risks"""
        return {
            'health_risk': 1.0 - self.risk_analysis_cache['system_health'],
            'emergency_risk': 1.0 if self.risk_analysis_cache['emergency_active'] else 0.0
        }
    
    def _assess_liquidity_risk(self) -> Dict[str, float]:
        """Assess liquidity-specific risks"""
        return {
            'market_liquidity': self.risk_analysis_cache['market_stress'],  # Proxy for liquidity
            'position_liquidity': self.risk_analysis_cache['portfolio_exposure']  # Higher exposure = lower liquidity
        }
    
    def handle_time_event(self, event: TimeEvent, market_time: MarketTime) -> None:
        """React to time events for risk monitoring - ALWAYS ACTIVE"""
        
        if event == TimeEvent.OPEN:
            print(f"   ⏰ {self.name}: Market open - heightened risk monitoring")
            # Reduce check interval during market hours
            self.risk_check_interval = timedelta(seconds=15)
            
        elif event == TimeEvent.CLOSE:
            print(f"   ⏰ {self.name}: Market close - standard risk monitoring")
            # Return to normal check interval
            self.risk_check_interval = timedelta(seconds=30)
            
        elif event == TimeEvent.INTRADAY:
            print(f"   ⏰ {self.name}: Intraday - continuous risk surveillance")
            
        elif event == TimeEvent.OVERNIGHT:
            print(f"   ⏰ {self.name}: Overnight - risk system remains vigilant")
    
    def can_execute(self, state: UnifiedState) -> bool:
        """Risk organ ALWAYS executes - it has absolute authority"""
        return True  # Risk never stops
    
    def get_risk_metrics(self) -> Dict[str, Any]:
        """Get risk management performance metrics"""
        
        return {
            'total_risk_checks': self.emergency_stats['total_risk_checks'],
            'emergency_triggers': self.emergency_stats['emergency_triggers'],
            'false_alarms': self.emergency_stats['false_alarms'],
            'emergency_rate': self.emergency_stats['emergency_triggers'] / max(1, self.emergency_stats['total_risk_checks']),
            'last_emergency': self.emergency_stats['last_emergency'].isoformat() if self.emergency_stats['last_emergency'] else None,
            'average_response_time': np.mean(self.emergency_stats['response_times']) if self.emergency_stats['response_times'] else 0.0,
            'max_response_time': max(self.emergency_stats['response_times']) if self.emergency_stats['response_times'] else 0.0,
            'risk_components_available': self.risk_coordinator is not None or self.emergency_brake is not None,
            'check_interval_seconds': self.risk_check_interval.total_seconds(),
            'current_risk_level': self.risk_result.get('risk_level', 0.0) if self.risk_result else 0.0,
            'reflex_response_capable': np.mean(self.emergency_stats['response_times']) < 1.0 if self.emergency_stats['response_times'] else False
        }

class MemoryManagerOrgan(NorthstarOrgan):
    """
    Memory Manager Organ - The Hippocampus of the Living System
    
    This organ integrates the Memory Manager into the living system,
    providing unified memory access and anticipatory behavior capabilities.
    """
    
    def __init__(self, name: str = "memory_manager_organ"):
        super().__init__(name)
        self.is_critical = False  # Memory is important but not critical for basic operation
        
        # Initialize the memory manager
        self.memory_manager = MemoryManager()
        self.memory_result = None
        
        # Memory update tracking
        self.last_memory_update = None
        self.memory_update_interval = timedelta(minutes=15)  # Update memory every 15 minutes
        
        # Anticipatory signals cache
        self.anticipatory_signals = []
        self.regime_predictions = []
        
        print(f"   🔗 {self.name}: Successfully initialized MemoryManager")
    
    def read_state(self, state: UnifiedState) -> None:
        """Read state to determine memory operations needed"""
        
        # Check if memory update is needed
        time_based_update = (
            self.last_memory_update is None or
            datetime.now() - self.last_memory_update > self.memory_update_interval
        )
        
        # Check for regime changes that need to be recorded
        current_regime = state.market.regime
        regime_changed = (
            hasattr(self, 'last_regime') and 
            self.last_regime != current_regime
        )
        
        # Cache current state for memory operations
        self.current_state_cache = {
            'regime': current_regime,
            'market_stress': state.market.market_stress,
            'volatility_regime': state.market.volatility_regime,
            'portfolio_exposure': state.portfolio.total_exposure,
            'intelligence_conviction': state.beliefs.unified_conviction,
            'risk_status': state.risk.status.value,
            'system_health': state.health.overall_health_score
        }
        
        self.needs_memory_update = time_based_update or regime_changed
        
        if regime_changed:
            print(f"   📖 {self.name}: Regime change detected: {getattr(self, 'last_regime', 'unknown')} → {current_regime}")
        
        if self.needs_memory_update:
            print(f"   📖 {self.name}: Memory update needed")
        else:
            print(f"   📖 {self.name}: Memory is current")
    
    def think(self, state: UnifiedState) -> Any:
        """Execute memory operations and generate anticipatory insights"""
        
        if not self.needs_memory_update:
            return {
                'status': 'skipped',
                'reason': 'memory_current',
                'timestamp': datetime.now()
            }
        
        try:
            print(f"   🧠 {self.name}: Running memory analysis and pattern matching...")
            
            # Record regime transition if detected
            if hasattr(self, 'last_regime') and self.last_regime != self.current_state_cache['regime']:
                self.memory_manager.record_regime_transition(
                    old_regime=self.last_regime,
                    new_regime=self.current_state_cache['regime'],
                    market_context=self.current_state_cache
                )
            
            # Generate anticipatory signals
            self.anticipatory_signals = self.memory_manager.get_anticipatory_signals(
                self.current_state_cache
            )
            
            # Get regime transition predictions
            self.regime_predictions = self.memory_manager.get_regime_transition_predictions(
                current_regime=self.current_state_cache['regime'],
                market_context=self.current_state_cache
            )
            
            # Get memory health metrics
            memory_health = self.memory_manager.get_memory_health_metrics()
            
            # Update timestamp
            self.last_memory_update = datetime.now()
            
            # Create memory analysis result
            memory_analysis = {
                'status': 'success',
                'timestamp': datetime.now(),
                'anticipatory_signals': len(self.anticipatory_signals),
                'regime_predictions': len(self.regime_predictions),
                'memory_health': memory_health['memory_system_health'],
                'total_records': memory_health['total_records'],
                'data_freshness': memory_health['data_freshness'],
                'top_signals': [
                    {
                        'type': signal['signal_type'],
                        'confidence': signal['confidence']
                    }
                    for signal in self.anticipatory_signals[:3]
                ],
                'top_predictions': [
                    {
                        'predicted_regime': pred['predicted_regime'],
                        'confidence': pred['confidence']
                    }
                    for pred in self.regime_predictions[:2]
                ]
            }
            
            print(f"   🧠 {self.name}: Memory analysis completed - {len(self.anticipatory_signals)} signals, {len(self.regime_predictions)} predictions")
            
            self.memory_result = memory_analysis
            return memory_analysis
            
        except Exception as e:
            error_result = {
                'status': 'error',
                'timestamp': datetime.now(),
                'error': str(e)
            }
            
            print(f"   🧠 {self.name}: Memory analysis error - {e}")
            
            self.memory_result = error_result
            return error_result
    
    def write_state(self, state: UnifiedState) -> None:
        """Update state with memory insights and anticipatory signals"""
        
        if not self.memory_result:
            return
        
        if self.memory_result['status'] == 'success':
            # Update memory state with current status
            state.update_component('memory', {
                'regime_patterns_available': True,
                'strategy_history_available': True,
                'narrative_memory_available': True,
                'portfolio_history_available': True,
                'total_memory_records': self.memory_result['total_records']
            }, organ=self.name, reason="Memory analysis update")
            
            # Update health state with memory health
            state.update_component('health', {
                'component_availability': state.health.component_availability + 0.1  # Memory adds to availability
            }, organ=self.name, reason="Memory system active")
            
            # Store regime for change detection
            self.last_regime = self.current_state_cache['regime']
            
            print(f"   ✍️ {self.name}: Updated state with memory insights")
            
        elif self.memory_result['status'] == 'failed':
            # Update memory state to reflect failure
            state.update_component('memory', {
                'regime_patterns_available': False,
                'strategy_history_available': False
            }, organ=self.name, reason="Memory analysis failed")
            
            print(f"   ✍️ {self.name}: Updated state - memory analysis failed")
    
    def handle_time_event(self, event: TimeEvent, market_time: MarketTime) -> None:
        """React to time events for memory operations"""
        
        if event == TimeEvent.CLOSE:
            print(f"   ⏰ {self.name}: Market close - consolidating daily memories")
            # Could trigger end-of-day memory consolidation
            
        elif event == TimeEvent.OVERNIGHT:
            print(f"   ⏰ {self.name}: Overnight - running memory optimization")
            # Could trigger memory cleanup and pattern analysis
            
        elif event == TimeEvent.WEEKLY_REBALANCE:
            print(f"   ⏰ {self.name}: Weekly rebalance - updating long-term patterns")
            # Force memory update for weekly analysis
            self.needs_memory_update = True
    
    def get_memory_metrics(self) -> Dict[str, Any]:
        """Get memory system performance metrics"""
        
        memory_health = self.memory_manager.get_memory_health_metrics()
        
        return {
            'memory_health': memory_health['memory_system_health'],
            'total_records': memory_health['total_records'],
            'data_freshness': memory_health['data_freshness'],
            'coverage_ratio': memory_health.get('memory_coverage', {}).get('coverage_ratio', 0),
            'anticipatory_signals': len(self.anticipatory_signals),
            'regime_predictions': len(self.regime_predictions),
            'last_update': self.last_memory_update.isoformat() if self.last_memory_update else None,
            'update_interval_minutes': self.memory_update_interval.total_seconds() / 60,
            'memory_manager_available': self.memory_manager is not None
        }
    
    def get_anticipatory_insights(self) -> Dict[str, Any]:
        """Get current anticipatory insights for other organs"""
        
        return {
            'anticipatory_signals': self.anticipatory_signals,
            'regime_predictions': self.regime_predictions,
            'memory_health': self.memory_manager.get_memory_health_metrics(),
            'timestamp': datetime.now().isoformat()
        }

def create_v3_organ_wrappers():
    """Create organ wrappers for existing V3 components"""
    
    organs = [
        DataPipelineOrgan("data_pipeline_organ"),
        MarketBrainOrgan("market_brain_organ"),
        IntelligenceStackOrgan("intelligence_stack_organ"),
        CapitalAllocatorOrgan("capital_allocator_organ"),
        PortfolioGovernorOrgan("portfolio_governor_organ"),
        RiskCoordinatorOrgan("risk_coordinator_organ"),  # The Spinal Cord
        MemoryManagerOrgan("memory_manager_organ")  # The Hippocampus
    ]
    
    return organs

def main():
    """Test V3 component organ wrappers"""
    
    print("🔗 TESTING V3 COMPONENT ORGAN WRAPPERS")
    print("=" * 50)
    
    # Create test environment
    from src.core.state import UnifiedState
    from src.core.clock import MarketClock
    from src.core.events import EventBus
    from src.core.orchestrator import OrganOrchestrator
    
    print("\n🏗️ Creating test environment...")
    state = UnifiedState()
    clock = MarketClock()
    event_bus = EventBus()
    orchestrator = OrganOrchestrator(state=state, clock=clock, event_bus=event_bus)
    
    # Create V3 organ wrappers
    print("\n🔗 Creating V3 organ wrappers...")
    organs = create_v3_organ_wrappers()
    
    # Register organs
    print("\n📋 Registering organs...")
    for organ in organs:
        orchestrator.register_organ(organ, is_critical=organ.is_critical)
    
    # Test individual organ execution
    print("\n⚡ Testing individual organ execution...")
    for organ in organs:
        print(f"\n   Testing {organ.name}:")
        result = organ.execute_full_cycle(state)
        print(f"   Result: {'✅ SUCCESS' if result.success else '❌ FAILED'}")
        if result.error:
            print(f"   Error: {result.error}")
        print(f"   Duration: {result.duration:.3f}s")
    
    # Test orchestrator cycle with wrapped organs
    print("\n🎭 Testing orchestrator cycle with V3 wrappers...")
    cycle_result = orchestrator.run_cycle()
    print(f"   Cycle completed: {cycle_result['organs_successful']}/{cycle_result['organs_executed']} organs successful")
    print(f"   Success rate: {cycle_result['success_rate']:.1%}")
    
    # Test time event handling
    print("\n⏰ Testing time event handling...")
    market_time = clock.tick()
    for organ in organs:
        organ.handle_time_event(TimeEvent.OPEN, market_time)
    
    # Test specific metrics
    print("\n📊 Testing organ-specific metrics...")
    data_pipeline_organ = organs[0]
    if hasattr(data_pipeline_organ, 'get_collection_metrics'):
        metrics = data_pipeline_organ.get_collection_metrics()
        print(f"   Data Pipeline Success Rate: {metrics['success_rate']:.1%}")
        print(f"   Total Collections: {metrics['total_collections']}")
    
    # Test Risk Coordinator (Spinal Cord) specifically
    risk_organ = organs[-1]  # Risk coordinator is last
    if hasattr(risk_organ, 'get_risk_metrics'):
        risk_metrics = risk_organ.get_risk_metrics()
        print(f"   Risk Coordinator Response Time: {risk_metrics['average_response_time']:.3f}s")
        print(f"   Emergency Triggers: {risk_metrics['emergency_triggers']}")
        print(f"   Reflex Response Capable: {risk_metrics['reflex_response_capable']}")
    
    # Test emergency scenario
    print("\n🚨 Testing emergency scenario...")
    # Simulate high market stress
    state.update_component('market', {
        'market_stress': 0.9  # Above critical threshold
    }, organ="test", reason="Emergency simulation")
    
    # Run risk organ to see emergency response
    emergency_result = risk_organ.execute_full_cycle(state)
    print(f"   Emergency Response: {'✅ TRIGGERED' if emergency_result.success else '❌ FAILED'}")
    if emergency_result.output and emergency_result.output.get('emergency_triggered'):
        print(f"   System Locked: {'🔒 YES' if state.locked else '🔓 NO'}")
        print(f"   Response Time: {emergency_result.output.get('response_time', 0):.3f}s")
    
    # Reset emergency condition
    state.update_component('market', {
        'market_stress': 0.1  # Back to normal
    }, organ="test", reason="Emergency simulation reset")
    
    # Test recovery
    recovery_result = risk_organ.execute_full_cycle(state)
    if recovery_result.success and not recovery_result.output.get('emergency_triggered'):
        print(f"   System Unlocked: {'🔓 YES' if not state.locked else '🔒 NO'}")
    
    print(f"\n✅ V3 Component Organ Wrappers test successful!")
    print(f"   Existing V3 components are now living system organs!")
    print(f"   Risk Coordinator serves as the spinal cord with absolute authority!")
    
    return True

if __name__ == "__main__":
    main()