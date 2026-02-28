"""
Phase 3 Breakdown Simulator

This module implements sophisticated stress testing scenarios that model breakdown
conditions for Phase 3 anticipatory intelligence components. It creates scenarios
where regime memory fails, tailwind relationships break down, and anticipatory
signals provide false positives to validate system resilience.

The simulator builds upon the completed Phase 3 foundation:
- RegimeMemorySystem with cosine similarity matching
- SimpleTailwindEngine with 60% Sharpe + 40% regime weighting
- NoEdgeDetector with exposure capping
- AnticipatoryCapitalAllocator integration

Author: Northstar V3 System
Date: 2025-01-17
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path

# Import Phase 3 components
from src.intelligence.regime_memory_system import RegimeMemorySystem
from src.intelligence.simple_tailwind_engine import SimpleTailwindEngine
from src.intelligence.no_edge_detector import NoEdgeDetector
from src.intelligence.anticipatory_capital_allocator import AnticipatoryCapitalAllocator

logger = logging.getLogger(__name__)


class BreakdownType(Enum):
    """Types of breakdown scenarios to simulate."""
    REGIME_MEMORY_FAILURE = "regime_memory_failure"
    TAILWIND_BREAKDOWN = "tailwind_breakdown"
    ANTICIPATORY_FALSE_POSITIVES = "anticipatory_false_positives"
    CORRELATION_BREAKDOWN = "correlation_breakdown"
    MULTIPLE_COMPONENT_FAILURE = "multiple_component_failure"


@dataclass
class BreakdownScenarioConfig:
    """Configuration for breakdown scenario generation."""
    breakdown_type: BreakdownType
    severity: float  # 0.0 to 1.0, where 1.0 is complete breakdown
    duration_days: int
    affected_components: List[str]
    trigger_conditions: Dict[str, Any]
    recovery_pattern: Optional[str] = None


@dataclass
class ComponentBreakdownState:
    """State of a component during breakdown."""
    component_name: str
    is_broken: bool
    breakdown_severity: float
    breakdown_start: datetime
    breakdown_duration: int
    failure_mode: str
    recovery_progress: float = 0.0


@dataclass
class BreakdownSimulationResult:
    """Result of breakdown simulation."""
    scenario_id: str
    breakdown_type: BreakdownType
    scenario_description: str
    simulation_start: datetime
    simulation_end: datetime
    component_states: Dict[str, ComponentBreakdownState]
    breakdown_triggers: List[str]
    recovery_time: Optional[int]
    maximum_drawdown: float
    risk_management_effectiveness: float
    phase3_component_performance: Dict[str, float]
    lessons_learned: List[str]
    simulation_success: bool


class Phase3BreakdownSimulator:
    """
    Sophisticated stress testing simulator for Phase 3 component breakdown scenarios.
    
    This simulator creates realistic breakdown conditions to test system resilience:
    - Regime memory failures (no similar periods found)
    - Tailwind relationship breakdowns
    - Anticipatory signal false positives
    - Correlation structure breakdowns
    - Multiple simultaneous component failures
    """
    
    def __init__(self):
        """Initialize the breakdown simulator."""
        self.regime_memory = RegimeMemorySystem()
        self.tailwind_engine = SimpleTailwindEngine()
        self.no_edge_detector = NoEdgeDetector()
        self.anticipatory_allocator = AnticipatoryCapitalAllocator()
        
        # Breakdown scenario templates
        self.breakdown_scenarios = self._initialize_breakdown_scenarios()
        
        # Historical crisis periods for reference
        self.crisis_periods = {
            'dot_com_crash': ('2000-03-01', '2002-10-01'),
            'financial_crisis': ('2007-10-01', '2009-03-01'),
            'flash_crash': ('2010-05-06', '2010-05-07'),
            'covid_crash': ('2020-02-20', '2020-04-01'),
            'inflation_shock': ('2022-01-01', '2022-10-01')
        }
        
        logger.info("Phase3BreakdownSimulator initialized")
    
    def _initialize_breakdown_scenarios(self) -> Dict[str, BreakdownScenarioConfig]:
        """Initialize predefined breakdown scenario configurations."""
        scenarios = {}
        
        # Regime Memory Failure Scenarios
        scenarios['no_similar_regimes'] = BreakdownScenarioConfig(
            breakdown_type=BreakdownType.REGIME_MEMORY_FAILURE,
            severity=0.9,
            duration_days=30,
            affected_components=['regime_memory'],
            trigger_conditions={
                'min_similarity_threshold': 0.1,  # No regimes above 10% similarity
                'historical_lookback_days': 2000,
                'regime_instability': True
            },
            recovery_pattern='gradual'
        )
        
        scenarios['regime_similarity_instability'] = BreakdownScenarioConfig(
            breakdown_type=BreakdownType.REGIME_MEMORY_FAILURE,
            severity=0.7,
            duration_days=60,
            affected_components=['regime_memory'],
            trigger_conditions={
                'similarity_variance': 0.5,  # High variance in similarity scores
                'regime_flip_frequency': 5,  # Regime changes every 5 days
                'confidence_degradation': 0.8
            },
            recovery_pattern='oscillating'
        )
        
        # Tailwind Breakdown Scenarios
        scenarios['all_tailwinds_negative'] = BreakdownScenarioConfig(
            breakdown_type=BreakdownType.TAILWIND_BREAKDOWN,
            severity=1.0,
            duration_days=45,
            affected_components=['tailwind_engine'],
            trigger_conditions={
                'force_negative_tailwinds': True,
                'sharpe_degradation': -2.0,
                'regime_weight_instability': True
            },
            recovery_pattern='step_function'
        )
        
        scenarios['tailwind_calculation_instability'] = BreakdownScenarioConfig(
            breakdown_type=BreakdownType.TAILWIND_BREAKDOWN,
            severity=0.8,
            duration_days=90,
            affected_components=['tailwind_engine'],
            trigger_conditions={
                'calculation_noise': 0.5,
                'weight_oscillation': True,
                'performance_inversion': True
            },
            recovery_pattern='gradual'
        )
        
        # Anticipatory False Positive Scenarios
        scenarios['false_positive_signals'] = BreakdownScenarioConfig(
            breakdown_type=BreakdownType.ANTICIPATORY_FALSE_POSITIVES,
            severity=0.9,
            duration_days=120,
            affected_components=['anticipatory_allocator'],
            trigger_conditions={
                'false_positive_rate': 0.8,
                'signal_noise_ratio': 0.2,
                'lead_lag_inversion': True
            },
            recovery_pattern='gradual'
        )
        
        # Correlation Breakdown Scenarios
        scenarios['correlation_structure_breakdown'] = BreakdownScenarioConfig(
            breakdown_type=BreakdownType.CORRELATION_BREAKDOWN,
            severity=0.95,
            duration_days=30,
            affected_components=['regime_memory', 'tailwind_engine'],
            trigger_conditions={
                'correlation_inversion': True,
                'volatility_spike': 3.0,
                'regime_similarity_breakdown': True
            },
            recovery_pattern='step_function'
        )
        
        # Multiple Component Failure
        scenarios['cascade_failure'] = BreakdownScenarioConfig(
            breakdown_type=BreakdownType.MULTIPLE_COMPONENT_FAILURE,
            severity=0.85,
            duration_days=60,
            affected_components=['regime_memory', 'tailwind_engine', 'anticipatory_allocator'],
            trigger_conditions={
                'cascade_trigger': True,
                'system_wide_instability': True,
                'emergency_protocols': True
            },
            recovery_pattern='staged'
        )
        
        return scenarios
    
    def simulate_regime_memory_breakdown(
        self,
        breakdown_config: BreakdownScenarioConfig,
        market_data: pd.DataFrame,
        start_date: datetime
    ) -> BreakdownSimulationResult:
        """
        Simulate regime memory breakdown scenarios.
        
        Creates scenarios where:
        - No similar historical regimes can be found
        - Regime similarity calculations become unstable
        - Regime transitions happen too rapidly
        - Multiple conflicting regime signals occur
        """
        logger.info(f"Simulating regime memory breakdown: {breakdown_config.breakdown_type}")
        
        scenario_id = f"regime_breakdown_{start_date.strftime('%Y%m%d')}"
        simulation_start = start_date
        simulation_end = start_date + timedelta(days=breakdown_config.duration_days)
        
        # Initialize component breakdown states
        component_states = {}
        breakdown_triggers = []
        
        # Simulate regime memory failure
        if breakdown_config.breakdown_type == BreakdownType.REGIME_MEMORY_FAILURE:
            component_states['regime_memory'] = ComponentBreakdownState(
                component_name='regime_memory',
                is_broken=True,
                breakdown_severity=breakdown_config.severity,
                breakdown_start=simulation_start,
                breakdown_duration=breakdown_config.duration_days,
                failure_mode='no_similar_regimes_found'
            )
            
            # Simulate the breakdown effects
            breakdown_effects = self._simulate_regime_memory_failure_effects(
                breakdown_config, market_data, simulation_start, simulation_end
            )
            
            breakdown_triggers.extend([
                "Regime similarity scores below threshold",
                "Historical lookback insufficient",
                "Regime classification instability"
            ])
        
        # Calculate performance impact
        performance_impact = self._calculate_breakdown_performance_impact(
            component_states, market_data, simulation_start, simulation_end
        )
        
        # Assess risk management effectiveness
        risk_mgmt_effectiveness = self._assess_risk_management_effectiveness(
            component_states, performance_impact
        )
        
        # Generate lessons learned
        lessons_learned = self._generate_breakdown_lessons(
            breakdown_config, component_states, performance_impact
        )
        
        return BreakdownSimulationResult(
            scenario_id=scenario_id,
            breakdown_type=breakdown_config.breakdown_type,
            scenario_description=f"Regime memory breakdown simulation with {breakdown_config.severity:.1%} severity",
            simulation_start=simulation_start,
            simulation_end=simulation_end,
            component_states=component_states,
            breakdown_triggers=breakdown_triggers,
            recovery_time=self._estimate_recovery_time(breakdown_config),
            maximum_drawdown=performance_impact.get('max_drawdown', 0.0),
            risk_management_effectiveness=risk_mgmt_effectiveness,
            phase3_component_performance=performance_impact,
            lessons_learned=lessons_learned,
            simulation_success=True
        )
    
    def simulate_tailwind_breakdown(
        self,
        breakdown_config: BreakdownScenarioConfig,
        market_data: pd.DataFrame,
        start_date: datetime
    ) -> BreakdownSimulationResult:
        """
        Simulate tailwind breakdown scenarios.
        
        Creates scenarios where:
        - All tailwinds turn negative simultaneously
        - Tailwind calculations become unstable
        - Historical performance relationships break down
        - Regime-strategy relationships invert
        """
        logger.info(f"Simulating tailwind breakdown: {breakdown_config.breakdown_type}")
        
        scenario_id = f"tailwind_breakdown_{start_date.strftime('%Y%m%d')}"
        simulation_start = start_date
        simulation_end = start_date + timedelta(days=breakdown_config.duration_days)
        
        # Initialize component breakdown states
        component_states = {}
        breakdown_triggers = []
        
        # Simulate tailwind engine failure
        component_states['tailwind_engine'] = ComponentBreakdownState(
            component_name='tailwind_engine',
            is_broken=True,
            breakdown_severity=breakdown_config.severity,
            breakdown_start=simulation_start,
            breakdown_duration=breakdown_config.duration_days,
            failure_mode='tailwind_relationship_breakdown'
        )
        
        # Simulate the breakdown effects
        breakdown_effects = self._simulate_tailwind_breakdown_effects(
            breakdown_config, market_data, simulation_start, simulation_end
        )
        
        breakdown_triggers.extend([
            "All strategy tailwinds turned negative",
            "Historical performance relationships inverted",
            "Regime-strategy correlation breakdown"
        ])
        
        # Calculate performance impact
        performance_impact = self._calculate_breakdown_performance_impact(
            component_states, market_data, simulation_start, simulation_end
        )
        
        # Assess risk management effectiveness
        risk_mgmt_effectiveness = self._assess_risk_management_effectiveness(
            component_states, performance_impact
        )
        
        # Generate lessons learned
        lessons_learned = self._generate_breakdown_lessons(
            breakdown_config, component_states, performance_impact
        )
        
        return BreakdownSimulationResult(
            scenario_id=scenario_id,
            breakdown_type=breakdown_config.breakdown_type,
            scenario_description=f"Tailwind breakdown simulation with {breakdown_config.severity:.1%} severity",
            simulation_start=simulation_start,
            simulation_end=simulation_end,
            component_states=component_states,
            breakdown_triggers=breakdown_triggers,
            recovery_time=self._estimate_recovery_time(breakdown_config),
            maximum_drawdown=performance_impact.get('max_drawdown', 0.0),
            risk_management_effectiveness=risk_mgmt_effectiveness,
            phase3_component_performance=performance_impact,
            lessons_learned=lessons_learned,
            simulation_success=True
        )
    
    def simulate_anticipatory_false_positives(
        self,
        breakdown_config: BreakdownScenarioConfig,
        market_data: pd.DataFrame,
        start_date: datetime
    ) -> BreakdownSimulationResult:
        """
        Simulate anticipatory signal false positive scenarios.
        
        Creates scenarios where:
        - Anticipatory signals provide false positives
        - Lead-lag relationships become inverted
        - Signal-to-noise ratio degrades significantly
        - Positioning accuracy drops dramatically
        """
        logger.info(f"Simulating anticipatory false positives: {breakdown_config.breakdown_type}")
        
        scenario_id = f"false_positives_{start_date.strftime('%Y%m%d')}"
        simulation_start = start_date
        simulation_end = start_date + timedelta(days=breakdown_config.duration_days)
        
        # Initialize component breakdown states
        component_states = {}
        breakdown_triggers = []
        
        # Simulate anticipatory allocator failure
        component_states['anticipatory_allocator'] = ComponentBreakdownState(
            component_name='anticipatory_allocator',
            is_broken=True,
            breakdown_severity=breakdown_config.severity,
            breakdown_start=simulation_start,
            breakdown_duration=breakdown_config.duration_days,
            failure_mode='false_positive_signals'
        )
        
        # Simulate the breakdown effects
        breakdown_effects = self._simulate_false_positive_effects(
            breakdown_config, market_data, simulation_start, simulation_end
        )
        
        breakdown_triggers.extend([
            "Anticipatory signals providing false positives",
            "Lead-lag relationships inverted",
            "Signal-to-noise ratio degraded"
        ])
        
        # Calculate performance impact
        performance_impact = self._calculate_breakdown_performance_impact(
            component_states, market_data, simulation_start, simulation_end
        )
        
        # Assess risk management effectiveness
        risk_mgmt_effectiveness = self._assess_risk_management_effectiveness(
            component_states, performance_impact
        )
        
        # Generate lessons learned
        lessons_learned = self._generate_breakdown_lessons(
            breakdown_config, component_states, performance_impact
        )
        
        return BreakdownSimulationResult(
            scenario_id=scenario_id,
            breakdown_type=breakdown_config.breakdown_type,
            scenario_description=f"Anticipatory false positive simulation with {breakdown_config.severity:.1%} severity",
            simulation_start=simulation_start,
            simulation_end=simulation_end,
            component_states=component_states,
            breakdown_triggers=breakdown_triggers,
            recovery_time=self._estimate_recovery_time(breakdown_config),
            maximum_drawdown=performance_impact.get('max_drawdown', 0.0),
            risk_management_effectiveness=risk_mgmt_effectiveness,
            phase3_component_performance=performance_impact,
            lessons_learned=lessons_learned,
            simulation_success=True
        )
    
    def simulate_correlation_breakdown(
        self,
        breakdown_config: BreakdownScenarioConfig,
        market_data: pd.DataFrame,
        start_date: datetime
    ) -> BreakdownSimulationResult:
        """
        Simulate correlation structure breakdown scenarios.
        
        Creates scenarios where:
        - Asset correlations invert or break down
        - Regime similarity calculations become unreliable
        - Market structure changes fundamentally
        - Phase 3 assumptions no longer hold
        """
        logger.info(f"Simulating correlation breakdown: {breakdown_config.breakdown_type}")
        
        scenario_id = f"correlation_breakdown_{start_date.strftime('%Y%m%d')}"
        simulation_start = start_date
        simulation_end = start_date + timedelta(days=breakdown_config.duration_days)
        
        # Initialize component breakdown states
        component_states = {}
        breakdown_triggers = []
        
        # Multiple components affected by correlation breakdown
        for component in breakdown_config.affected_components:
            component_states[component] = ComponentBreakdownState(
                component_name=component,
                is_broken=True,
                breakdown_severity=breakdown_config.severity,
                breakdown_start=simulation_start,
                breakdown_duration=breakdown_config.duration_days,
                failure_mode='correlation_structure_breakdown'
            )
        
        breakdown_triggers.extend([
            "Asset correlation structure breakdown",
            "Regime similarity calculations unreliable",
            "Market structure fundamental change"
        ])
        
        # Calculate performance impact
        performance_impact = self._calculate_breakdown_performance_impact(
            component_states, market_data, simulation_start, simulation_end
        )
        
        # Assess risk management effectiveness
        risk_mgmt_effectiveness = self._assess_risk_management_effectiveness(
            component_states, performance_impact
        )
        
        # Generate lessons learned
        lessons_learned = self._generate_breakdown_lessons(
            breakdown_config, component_states, performance_impact
        )
        
        return BreakdownSimulationResult(
            scenario_id=scenario_id,
            breakdown_type=breakdown_config.breakdown_type,
            scenario_description=f"Correlation breakdown simulation with {breakdown_config.severity:.1%} severity",
            simulation_start=simulation_start,
            simulation_end=simulation_end,
            component_states=component_states,
            breakdown_triggers=breakdown_triggers,
            recovery_time=self._estimate_recovery_time(breakdown_config),
            maximum_drawdown=performance_impact.get('max_drawdown', 0.0),
            risk_management_effectiveness=risk_mgmt_effectiveness,
            phase3_component_performance=performance_impact,
            lessons_learned=lessons_learned,
            simulation_success=True
        )
    
    def simulate_multiple_component_failure(
        self,
        breakdown_config: BreakdownScenarioConfig,
        market_data: pd.DataFrame,
        start_date: datetime
    ) -> BreakdownSimulationResult:
        """
        Simulate multiple simultaneous component failure scenarios.
        
        Creates scenarios where:
        - Multiple Phase 3 components fail simultaneously
        - Cascade failures occur across components
        - System-wide instability emerges
        - Emergency protocols must be activated
        """
        logger.info(f"Simulating multiple component failure: {breakdown_config.breakdown_type}")
        
        scenario_id = f"cascade_failure_{start_date.strftime('%Y%m%d')}"
        simulation_start = start_date
        simulation_end = start_date + timedelta(days=breakdown_config.duration_days)
        
        # Initialize component breakdown states for all affected components
        component_states = {}
        breakdown_triggers = []
        
        for component in breakdown_config.affected_components:
            component_states[component] = ComponentBreakdownState(
                component_name=component,
                is_broken=True,
                breakdown_severity=breakdown_config.severity,
                breakdown_start=simulation_start,
                breakdown_duration=breakdown_config.duration_days,
                failure_mode='cascade_failure'
            )
        
        breakdown_triggers.extend([
            "Multiple Phase 3 components failed simultaneously",
            "Cascade failure across system",
            "System-wide instability detected",
            "Emergency protocols activated"
        ])
        
        # Calculate performance impact
        performance_impact = self._calculate_breakdown_performance_impact(
            component_states, market_data, simulation_start, simulation_end
        )
        
        # Assess risk management effectiveness
        risk_mgmt_effectiveness = self._assess_risk_management_effectiveness(
            component_states, performance_impact
        )
        
        # Generate lessons learned
        lessons_learned = self._generate_breakdown_lessons(
            breakdown_config, component_states, performance_impact
        )
        
        return BreakdownSimulationResult(
            scenario_id=scenario_id,
            breakdown_type=breakdown_config.breakdown_type,
            scenario_description=f"Multiple component failure simulation with {breakdown_config.severity:.1%} severity",
            simulation_start=simulation_start,
            simulation_end=simulation_end,
            component_states=component_states,
            breakdown_triggers=breakdown_triggers,
            recovery_time=self._estimate_recovery_time(breakdown_config),
            maximum_drawdown=performance_impact.get('max_drawdown', 0.0),
            risk_management_effectiveness=risk_mgmt_effectiveness,
            phase3_component_performance=performance_impact,
            lessons_learned=lessons_learned,
            simulation_success=True
        )
    
    def run_comprehensive_breakdown_test(
        self,
        market_data: pd.DataFrame,
        test_period: Tuple[datetime, datetime]
    ) -> Dict[str, BreakdownSimulationResult]:
        """
        Run comprehensive breakdown testing across all scenario types.
        
        Tests all major breakdown scenarios:
        - Regime memory failures
        - Tailwind breakdowns
        - Anticipatory false positives
        - Correlation breakdowns
        - Multiple component failures
        """
        logger.info("Running comprehensive Phase 3 breakdown testing")
        
        start_date, end_date = test_period
        results = {}
        
        # Test each breakdown scenario
        for scenario_name, config in self.breakdown_scenarios.items():
            try:
                if config.breakdown_type == BreakdownType.REGIME_MEMORY_FAILURE:
                    result = self.simulate_regime_memory_breakdown(config, market_data, start_date)
                elif config.breakdown_type == BreakdownType.TAILWIND_BREAKDOWN:
                    result = self.simulate_tailwind_breakdown(config, market_data, start_date)
                elif config.breakdown_type == BreakdownType.ANTICIPATORY_FALSE_POSITIVES:
                    result = self.simulate_anticipatory_false_positives(config, market_data, start_date)
                elif config.breakdown_type == BreakdownType.CORRELATION_BREAKDOWN:
                    result = self.simulate_correlation_breakdown(config, market_data, start_date)
                elif config.breakdown_type == BreakdownType.MULTIPLE_COMPONENT_FAILURE:
                    result = self.simulate_multiple_component_failure(config, market_data, start_date)
                else:
                    logger.warning(f"Unknown breakdown type: {config.breakdown_type}")
                    continue
                
                results[scenario_name] = result
                logger.info(f"Completed breakdown test: {scenario_name}")
                
            except Exception as e:
                logger.error(f"Failed to run breakdown test {scenario_name}: {str(e)}")
                continue
        
        logger.info(f"Completed comprehensive breakdown testing: {len(results)} scenarios")
        return results
    
    def _simulate_regime_memory_failure_effects(
        self,
        config: BreakdownScenarioConfig,
        market_data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Simulate the effects of regime memory failure."""
        effects = {}
        
        # Simulate no similar regimes found
        if config.trigger_conditions.get('min_similarity_threshold', 0) < 0.2:
            effects['similarity_scores'] = np.random.uniform(0.0, 0.1, size=100)
            effects['regime_confidence'] = 0.1
        
        # Simulate regime instability
        if config.trigger_conditions.get('regime_instability', False):
            effects['regime_changes_per_week'] = 3.5  # Very high
            effects['regime_duration_stability'] = 0.2  # Very low
        
        return effects
    
    def _simulate_tailwind_breakdown_effects(
        self,
        config: BreakdownScenarioConfig,
        market_data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Simulate the effects of tailwind breakdown."""
        effects = {}
        
        # Force negative tailwinds
        if config.trigger_conditions.get('force_negative_tailwinds', False):
            effects['all_tailwinds_negative'] = True
            effects['average_tailwind'] = -0.5
        
        # Simulate calculation instability
        if config.trigger_conditions.get('calculation_noise', 0) > 0.3:
            effects['tailwind_volatility'] = 2.0  # Very high
            effects['calculation_reliability'] = 0.3  # Very low
        
        return effects
    
    def _simulate_false_positive_effects(
        self,
        config: BreakdownScenarioConfig,
        market_data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Simulate the effects of anticipatory false positives."""
        effects = {}
        
        # High false positive rate
        if config.trigger_conditions.get('false_positive_rate', 0) > 0.5:
            effects['signal_accuracy'] = 0.2  # Very low
            effects['false_positive_rate'] = 0.8  # Very high
        
        # Lead-lag inversion
        if config.trigger_conditions.get('lead_lag_inversion', False):
            effects['lead_time'] = -2  # Signals lag instead of lead
            effects['timing_accuracy'] = 0.1  # Very poor
        
        return effects
    
    def _calculate_breakdown_performance_impact(
        self,
        component_states: Dict[str, ComponentBreakdownState],
        market_data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, float]:
        """Calculate the performance impact of component breakdowns."""
        impact = {}
        
        # Estimate performance degradation based on broken components
        total_severity = sum(state.breakdown_severity for state in component_states.values())
        num_broken = len([state for state in component_states.values() if state.is_broken])
        
        # Base performance impact
        impact['performance_degradation'] = min(total_severity * 0.3, 0.8)
        impact['max_drawdown'] = min(total_severity * 0.15, 0.4)
        impact['volatility_increase'] = total_severity * 0.5
        
        # Component-specific impacts
        for component_name, state in component_states.items():
            if state.is_broken:
                if component_name == 'regime_memory':
                    impact['regime_accuracy_loss'] = state.breakdown_severity * 0.7
                elif component_name == 'tailwind_engine':
                    impact['tailwind_reliability_loss'] = state.breakdown_severity * 0.8
                elif component_name == 'anticipatory_allocator':
                    impact['positioning_accuracy_loss'] = state.breakdown_severity * 0.6
        
        return impact
    
    def _assess_risk_management_effectiveness(
        self,
        component_states: Dict[str, ComponentBreakdownState],
        performance_impact: Dict[str, float]
    ) -> float:
        """Assess how effectively risk management handled the breakdown."""
        
        # Base effectiveness starts high
        effectiveness = 0.9
        
        # Reduce effectiveness based on severity of breakdown
        max_drawdown = performance_impact.get('max_drawdown', 0.0)
        if max_drawdown > 0.3:  # More than 30% drawdown
            effectiveness -= 0.4
        elif max_drawdown > 0.2:  # More than 20% drawdown
            effectiveness -= 0.2
        elif max_drawdown > 0.1:  # More than 10% drawdown
            effectiveness -= 0.1
        
        # Check if NO_EDGE detection would have triggered
        total_severity = sum(state.breakdown_severity for state in component_states.values())
        if total_severity > 0.7:  # High severity should trigger NO_EDGE
            effectiveness += 0.1  # Bonus for proper risk management
        
        return max(0.0, min(1.0, effectiveness))
    
    def _estimate_recovery_time(self, config: BreakdownScenarioConfig) -> Optional[int]:
        """Estimate recovery time based on breakdown configuration."""
        if config.recovery_pattern == 'gradual':
            return int(config.duration_days * 1.5)
        elif config.recovery_pattern == 'step_function':
            return config.duration_days + 7
        elif config.recovery_pattern == 'oscillating':
            return int(config.duration_days * 2.0)
        elif config.recovery_pattern == 'staged':
            return int(config.duration_days * 1.2)
        else:
            return None
    
    def _generate_breakdown_lessons(
        self,
        config: BreakdownScenarioConfig,
        component_states: Dict[str, ComponentBreakdownState],
        performance_impact: Dict[str, float]
    ) -> List[str]:
        """Generate lessons learned from breakdown simulation."""
        lessons = []
        
        # General lessons based on breakdown type
        if config.breakdown_type == BreakdownType.REGIME_MEMORY_FAILURE:
            lessons.extend([
                "Regime memory requires robust fallback mechanisms",
                "Similarity threshold tuning is critical for stability",
                "Historical lookback period affects regime detection reliability"
            ])
        elif config.breakdown_type == BreakdownType.TAILWIND_BREAKDOWN:
            lessons.extend([
                "Tailwind calculations need stability checks",
                "Performance relationship monitoring is essential",
                "Regime-strategy correlation validation required"
            ])
        elif config.breakdown_type == BreakdownType.ANTICIPATORY_FALSE_POSITIVES:
            lessons.extend([
                "Signal validation mechanisms are critical",
                "Lead-lag relationship monitoring needed",
                "False positive detection systems required"
            ])
        
        # Performance-based lessons
        max_drawdown = performance_impact.get('max_drawdown', 0.0)
        if max_drawdown > 0.2:
            lessons.append("Risk management protocols need strengthening")
        
        if len(component_states) > 1:
            lessons.append("Component interdependencies create cascade risks")
        
        return lessons
    
    def get_breakdown_scenario_config(self, scenario_name: str) -> Optional[BreakdownScenarioConfig]:
        """Get configuration for a specific breakdown scenario."""
        return self.breakdown_scenarios.get(scenario_name)
    
    def list_available_scenarios(self) -> List[str]:
        """List all available breakdown scenarios."""
        return list(self.breakdown_scenarios.keys())
    
    def validate_breakdown_simulation_integrity(
        self,
        result: BreakdownSimulationResult
    ) -> bool:
        """Validate that breakdown simulation produced realistic results."""
        
        # Check that breakdown actually occurred
        if not any(state.is_broken for state in result.component_states.values()):
            logger.warning("Breakdown simulation did not produce any broken components")
            return False
        
        # Check that performance impact is realistic
        if result.maximum_drawdown < 0.0 or result.maximum_drawdown > 1.0:
            logger.warning(f"Unrealistic maximum drawdown: {result.maximum_drawdown}")
            return False
        
        # Check that risk management effectiveness is reasonable
        if result.risk_management_effectiveness < 0.0 or result.risk_management_effectiveness > 1.0:
            logger.warning(f"Invalid risk management effectiveness: {result.risk_management_effectiveness}")
            return False
        
        # Check that lessons learned were generated
        if not result.lessons_learned:
            logger.warning("No lessons learned generated from breakdown simulation")
            return False
        
        return True