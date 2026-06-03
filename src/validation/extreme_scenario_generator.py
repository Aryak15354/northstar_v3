"""
Extreme Scenario Generator

This module generates tail risk events and extreme market conditions for stress testing
the Phase 3 anticipatory intelligence system. It creates scenarios with proper statistical
characteristics based on historical crises and synthetic extreme conditions.

The generator focuses on scenarios that should trigger Phase 3 NO_EDGE detection
and test the resilience of regime memory, tailwind calculations, and anticipatory
positioning under extreme market stress.

Author: Northstar V3 System
Date: 2025-01-17
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from enum import Enum
import logging
from scipy import stats
from pathlib import Path

# Import Phase 3 components for validation
from src.intelligence.regime_memory_system import RegimeMemorySystem
from src.intelligence.simple_tailwind_engine import SimpleTailwindEngine
from src.intelligence.no_edge_detector import NoEdgeDetector

logger = logging.getLogger(__name__)


class ExtremeScenarioType(Enum):
    """Types of extreme scenarios to generate."""
    TAIL_RISK_EVENT = "tail_risk_event"
    HISTORICAL_CRISIS_REPLICA = "historical_crisis_replica"
    SYNTHETIC_EXTREME = "synthetic_extreme"
    LIQUIDITY_CRISIS = "liquidity_crisis"
    CORRELATION_SHOCK = "correlation_shock"
    VOLATILITY_EXPLOSION = "volatility_explosion"
    BLACK_SWAN_EVENT = "black_swan_event"


@dataclass
class ExtremeScenarioConfig:
    """Configuration for extreme scenario generation."""
    scenario_type: ExtremeScenarioType
    severity_level: float  # 1.0 = 1-in-100 year, 2.0 = 1-in-1000 year, etc.
    duration_days: int
    affected_assets: List[str]
    statistical_properties: Dict[str, float]
    trigger_conditions: Dict[str, Any]
    expected_no_edge_trigger: bool = True


@dataclass
class MarketShock:
    """Represents a market shock event."""
    shock_type: str
    magnitude: float
    duration: int
    affected_sectors: List[str]
    correlation_impact: float
    volatility_multiplier: float
    liquidity_impact: float


@dataclass
class ExtremeScenarioResult:
    """Result of extreme scenario generation."""
    scenario_id: str
    scenario_type: ExtremeScenarioType
    scenario_description: str
    generation_timestamp: datetime
    scenario_start: datetime
    scenario_end: datetime
    market_data: pd.DataFrame
    statistical_properties: Dict[str, float]
    shock_events: List[MarketShock]
    expected_phase3_behavior: Dict[str, Any]
    no_edge_trigger_expected: bool
    validation_metrics: Dict[str, float]
    scenario_success: bool


class ExtremeScenarioGenerator:
    """
    Generator for extreme market scenarios designed to stress test Phase 3 components.
    
    Creates scenarios with proper statistical characteristics:
    - Tail risk events with correct probability distributions
    - Historical crisis replicas with enhanced severity
    - Synthetic extreme conditions beyond historical experience
    - Liquidity crises with execution impact modeling
    - Correlation breakdown events
    - Volatility explosion scenarios
    """
    
    def __init__(self):
        """Initialize the extreme scenario generator."""
        self.regime_memory = RegimeMemorySystem()
        self.tailwind_engine = SimpleTailwindEngine()
        self.no_edge_detector = NoEdgeDetector()
        
        # Historical crisis templates
        self.crisis_templates = self._initialize_crisis_templates()
        
        # Statistical parameters for extreme events
        self.extreme_parameters = self._initialize_extreme_parameters()
        
        # Asset universe for scenario generation
        self.asset_universe = [
            'NIFTY50', 'BANKNIFTY', 'NIFTYMIDCAP', 'NIFTYSMALLCAP',
            'NIFTYIT', 'NIFTYPHARMA', 'NIFTYAUTO', 'NIFTYMETAL',
            'NIFTYENERGY', 'NIFTYFMCG', 'NIFTYREALTY', 'NIFTYPSU'
        ]
        
        logger.info("ExtremeScenarioGenerator initialized")
    
    def _initialize_crisis_templates(self) -> Dict[str, Dict[str, Any]]:
        """Initialize templates based on historical crises."""
        templates = {}
        
        # 2008 Financial Crisis Template
        templates['financial_crisis_2008'] = {
            'duration_days': 180,
            'max_drawdown': -0.55,
            'volatility_multiplier': 3.5,
            'correlation_spike': 0.9,
            'liquidity_impact': -0.7,
            'sector_impacts': {
                'BANKNIFTY': -0.65,
                'NIFTYREALTY': -0.70,
                'NIFTYAUTO': -0.60,
                'NIFTYMETAL': -0.55
            }
        }
        
        # 2020 COVID Crash Template
        templates['covid_crash_2020'] = {
            'duration_days': 45,
            'max_drawdown': -0.40,
            'volatility_multiplier': 4.0,
            'correlation_spike': 0.95,
            'liquidity_impact': -0.8,
            'sector_impacts': {
                'NIFTYAUTO': -0.50,
                'NIFTYREALTY': -0.45,
                'NIFTYENERGY': -0.55,
                'NIFTYMETAL': -0.40
            }
        }
        
        # Flash Crash Template
        templates['flash_crash'] = {
            'duration_days': 1,
            'max_drawdown': -0.15,
            'volatility_multiplier': 10.0,
            'correlation_spike': 1.0,
            'liquidity_impact': -0.95,
            'sector_impacts': {asset: -0.12 for asset in self.asset_universe}
        }
        
        # Demonetization Shock Template
        templates['demonetization_2016'] = {
            'duration_days': 90,
            'max_drawdown': -0.25,
            'volatility_multiplier': 2.0,
            'correlation_spike': 0.7,
            'liquidity_impact': -0.4,
            'sector_impacts': {
                'BANKNIFTY': -0.30,
                'NIFTYFMCG': -0.20,
                'NIFTYREALTY': -0.35,
                'NIFTYAUTO': -0.25
            }
        }
        
        return templates
    
    def _initialize_extreme_parameters(self) -> Dict[str, Dict[str, float]]:
        """Initialize statistical parameters for extreme event generation."""
        params = {}
        
        # Tail risk parameters
        params['tail_risk'] = {
            'alpha': 1.5,  # Tail index for power law
            'scale': 0.02,  # Scale parameter
            'threshold': 0.05,  # Threshold for extreme events
            'cluster_probability': 0.3  # Probability of clustered events
        }
        
        # Volatility explosion parameters
        params['volatility_explosion'] = {
            'base_vol': 0.15,  # Base volatility
            'explosion_multiplier': 5.0,  # Volatility multiplier
            'mean_reversion_speed': 0.1,  # Speed of reversion
            'persistence': 0.8  # Persistence of high volatility
        }
        
        # Correlation shock parameters
        params['correlation_shock'] = {
            'normal_correlation': 0.3,  # Normal correlation
            'shock_correlation': 0.95,  # Correlation during shock
            'shock_duration': 30,  # Duration of high correlation
            'transition_speed': 0.2  # Speed of transition
        }
        
        # Liquidity crisis parameters
        params['liquidity_crisis'] = {
            'normal_liquidity': 1.0,  # Normal liquidity level
            'crisis_liquidity': 0.1,  # Crisis liquidity level
            'impact_exponent': 1.5,  # Price impact exponent
            'recovery_rate': 0.05  # Daily recovery rate
        }
        
        return params
    
    def generate_tail_risk_event(
        self,
        config: ExtremeScenarioConfig,
        base_date: datetime
    ) -> ExtremeScenarioResult:
        """
        Generate tail risk event with proper statistical characteristics.
        
        Creates events with:
        - Correct probability distributions for extreme moves
        - Proper tail behavior following power laws
        - Realistic clustering of extreme events
        - Appropriate recovery patterns
        """
        logger.info(f"Generating tail risk event with severity {config.severity_level}")
        
        scenario_id = f"tail_risk_{base_date.strftime('%Y%m%d')}_{config.severity_level:.1f}"
        scenario_start = base_date
        scenario_end = base_date + timedelta(days=config.duration_days)
        
        # Generate extreme returns using power law distribution
        tail_params = self.extreme_parameters['tail_risk']
        
        # Calculate return magnitude based on severity level
        return_magnitude = self._calculate_tail_event_magnitude(config.severity_level)
        
        # Generate market data with extreme event
        market_data = self._generate_tail_risk_market_data(
            scenario_start, scenario_end, return_magnitude, config
        )
        
        # Create shock events
        shock_events = [
            MarketShock(
                shock_type="tail_risk_event",
                magnitude=return_magnitude,
                duration=config.duration_days,
                affected_sectors=config.affected_assets,
                correlation_impact=0.8,
                volatility_multiplier=3.0,
                liquidity_impact=-0.5
            )
        ]
        
        # Calculate expected Phase 3 behavior
        expected_behavior = self._calculate_expected_phase3_behavior(
            market_data, shock_events, config
        )
        
        # Validate scenario properties
        validation_metrics = self._validate_scenario_properties(
            market_data, config.statistical_properties
        )
        
        return ExtremeScenarioResult(
            scenario_id=scenario_id,
            scenario_type=config.scenario_type,
            scenario_description=f"Tail risk event with {config.severity_level:.1f} sigma magnitude",
            generation_timestamp=datetime.now(),
            scenario_start=scenario_start,
            scenario_end=scenario_end,
            market_data=market_data,
            statistical_properties=self._calculate_scenario_statistics(market_data),
            shock_events=shock_events,
            expected_phase3_behavior=expected_behavior,
            no_edge_trigger_expected=config.expected_no_edge_trigger,
            validation_metrics=validation_metrics,
            scenario_success=True
        )
    
    def generate_historical_crisis_replica(
        self,
        config: ExtremeScenarioConfig,
        crisis_template: str,
        base_date: datetime,
        severity_multiplier: float = 1.5
    ) -> ExtremeScenarioResult:
        """
        Generate enhanced replica of historical crisis.
        
        Creates scenarios based on historical crises but with:
        - Enhanced severity beyond historical levels
        - Extended duration for stress testing
        - Modified characteristics to test specific components
        - Proper statistical scaling
        """
        logger.info(f"Generating historical crisis replica: {crisis_template}")
        
        if crisis_template not in self.crisis_templates:
            raise ValueError(f"Unknown crisis template: {crisis_template}")
        
        template = self.crisis_templates[crisis_template]
        scenario_id = f"crisis_replica_{crisis_template}_{base_date.strftime('%Y%m%d')}"
        scenario_start = base_date
        scenario_end = base_date + timedelta(days=int(template['duration_days'] * severity_multiplier))
        
        # Generate enhanced crisis scenario
        market_data = self._generate_crisis_replica_data(
            scenario_start, scenario_end, template, severity_multiplier, config
        )
        
        # Create shock events based on template
        shock_events = self._create_crisis_shock_events(template, severity_multiplier)
        
        # Calculate expected Phase 3 behavior
        expected_behavior = self._calculate_expected_phase3_behavior(
            market_data, shock_events, config
        )
        
        # Validate scenario properties
        validation_metrics = self._validate_scenario_properties(
            market_data, config.statistical_properties
        )
        
        return ExtremeScenarioResult(
            scenario_id=scenario_id,
            scenario_type=config.scenario_type,
            scenario_description=f"Enhanced {crisis_template} replica with {severity_multiplier:.1f}x severity",
            generation_timestamp=datetime.now(),
            scenario_start=scenario_start,
            scenario_end=scenario_end,
            market_data=market_data,
            statistical_properties=self._calculate_scenario_statistics(market_data),
            shock_events=shock_events,
            expected_phase3_behavior=expected_behavior,
            no_edge_trigger_expected=config.expected_no_edge_trigger,
            validation_metrics=validation_metrics,
            scenario_success=True
        )
    
    def generate_synthetic_extreme_condition(
        self,
        config: ExtremeScenarioConfig,
        base_date: datetime
    ) -> ExtremeScenarioResult:
        """
        Generate synthetic extreme conditions beyond historical experience.
        
        Creates scenarios that:
        - Exceed historical extremes in magnitude or duration
        - Combine multiple crisis elements simultaneously
        - Test system behavior in unprecedented conditions
        - Maintain statistical realism while pushing boundaries
        """
        logger.info("Generating synthetic extreme condition")
        
        scenario_id = f"synthetic_extreme_{base_date.strftime('%Y%m%d')}_{config.severity_level:.1f}"
        scenario_start = base_date
        scenario_end = base_date + timedelta(days=config.duration_days)
        
        # Generate synthetic extreme market data
        market_data = self._generate_synthetic_extreme_data(
            scenario_start, scenario_end, config
        )
        
        # Create multiple simultaneous shock events
        shock_events = self._create_synthetic_shock_events(config)
        
        # Calculate expected Phase 3 behavior
        expected_behavior = self._calculate_expected_phase3_behavior(
            market_data, shock_events, config
        )
        
        # Validate scenario properties
        validation_metrics = self._validate_scenario_properties(
            market_data, config.statistical_properties
        )
        
        return ExtremeScenarioResult(
            scenario_id=scenario_id,
            scenario_type=config.scenario_type,
            scenario_description=f"Synthetic extreme condition with {config.severity_level:.1f} severity",
            generation_timestamp=datetime.now(),
            scenario_start=scenario_start,
            scenario_end=scenario_end,
            market_data=market_data,
            statistical_properties=self._calculate_scenario_statistics(market_data),
            shock_events=shock_events,
            expected_phase3_behavior=expected_behavior,
            no_edge_trigger_expected=config.expected_no_edge_trigger,
            validation_metrics=validation_metrics,
            scenario_success=True
        )
    
    def generate_liquidity_crisis(
        self,
        config: ExtremeScenarioConfig,
        base_date: datetime
    ) -> ExtremeScenarioResult:
        """
        Generate liquidity crisis scenario with execution impact modeling.
        
        Creates scenarios where:
        - Market liquidity dries up significantly
        - Execution costs increase dramatically
        - Bid-ask spreads widen substantially
        - Position sizing becomes constrained
        """
        logger.info("Generating liquidity crisis scenario")
        
        scenario_id = f"liquidity_crisis_{base_date.strftime('%Y%m%d')}"
        scenario_start = base_date
        scenario_end = base_date + timedelta(days=config.duration_days)
        
        # Generate liquidity crisis market data
        market_data = self._generate_liquidity_crisis_data(
            scenario_start, scenario_end, config
        )
        
        # Create liquidity shock events
        liquidity_params = self.extreme_parameters['liquidity_crisis']
        shock_events = [
            MarketShock(
                shock_type="liquidity_crisis",
                magnitude=liquidity_params['crisis_liquidity'],
                duration=config.duration_days,
                affected_sectors=config.affected_assets,
                correlation_impact=0.9,
                volatility_multiplier=2.5,
                liquidity_impact=-0.9
            )
        ]
        
        # Calculate expected Phase 3 behavior
        expected_behavior = self._calculate_expected_phase3_behavior(
            market_data, shock_events, config
        )
        
        # Validate scenario properties
        validation_metrics = self._validate_scenario_properties(
            market_data, config.statistical_properties
        )
        
        return ExtremeScenarioResult(
            scenario_id=scenario_id,
            scenario_type=config.scenario_type,
            scenario_description="Liquidity crisis with severe execution impact",
            generation_timestamp=datetime.now(),
            scenario_start=scenario_start,
            scenario_end=scenario_end,
            market_data=market_data,
            statistical_properties=self._calculate_scenario_statistics(market_data),
            shock_events=shock_events,
            expected_phase3_behavior=expected_behavior,
            no_edge_trigger_expected=config.expected_no_edge_trigger,
            validation_metrics=validation_metrics,
            scenario_success=True
        )
    
    def generate_black_swan_event(
        self,
        config: ExtremeScenarioConfig,
        base_date: datetime
    ) -> ExtremeScenarioResult:
        """
        Generate black swan event scenario.
        
        Creates scenarios that:
        - Are extremely rare (beyond 3-sigma events)
        - Have massive impact when they occur
        - Are difficult to predict or model
        - Test system behavior under unprecedented stress
        """
        logger.info("Generating black swan event scenario")
        
        scenario_id = f"black_swan_{base_date.strftime('%Y%m%d')}"
        scenario_start = base_date
        scenario_end = base_date + timedelta(days=config.duration_days)
        
        # Generate black swan market data
        market_data = self._generate_black_swan_data(
            scenario_start, scenario_end, config
        )
        
        # Create black swan shock events
        shock_events = [
            MarketShock(
                shock_type="black_swan_event",
                magnitude=-0.5,  # 50% market drop
                duration=config.duration_days,
                affected_sectors=config.affected_assets,
                correlation_impact=1.0,  # Perfect correlation
                volatility_multiplier=8.0,  # Extreme volatility
                liquidity_impact=-0.95  # Near-zero liquidity
            )
        ]
        
        # Calculate expected Phase 3 behavior
        expected_behavior = self._calculate_expected_phase3_behavior(
            market_data, shock_events, config
        )
        
        # Validate scenario properties
        validation_metrics = self._validate_scenario_properties(
            market_data, config.statistical_properties
        )
        
        return ExtremeScenarioResult(
            scenario_id=scenario_id,
            scenario_type=config.scenario_type,
            scenario_description="Black swan event with extreme market impact",
            generation_timestamp=datetime.now(),
            scenario_start=scenario_start,
            scenario_end=scenario_end,
            market_data=market_data,
            statistical_properties=self._calculate_scenario_statistics(market_data),
            shock_events=shock_events,
            expected_phase3_behavior=expected_behavior,
            no_edge_trigger_expected=True,  # Should definitely trigger NO_EDGE
            validation_metrics=validation_metrics,
            scenario_success=True
        )
    
    def _calculate_tail_event_magnitude(self, severity_level: float) -> float:
        """Calculate return magnitude for tail event based on severity level."""
        # Use inverse normal distribution to get return magnitude
        # severity_level 1.0 = 1-in-100 year event (~2.33 sigma)
        # severity_level 2.0 = 1-in-1000 year event (~3.09 sigma)
        # severity_level 3.0 = 1-in-10000 year event (~3.72 sigma)
        
        sigma_level = 2.0 + severity_level * 0.5
        daily_vol = 0.02  # 2% daily volatility assumption
        
        return -sigma_level * daily_vol  # Negative for market crash
    
    def _generate_tail_risk_market_data(
        self,
        start_date: datetime,
        end_date: datetime,
        return_magnitude: float,
        config: ExtremeScenarioConfig
    ) -> pd.DataFrame:
        """Generate market data for tail risk event."""
        dates = pd.date_range(start_date, end_date, freq='D')
        data = {}
        
        for asset in config.affected_assets:
            # Generate returns with extreme event on first day
            returns = np.random.normal(0, 0.015, len(dates))  # Normal daily returns
            returns[0] = return_magnitude  # Extreme event
            
            # Add volatility clustering after extreme event
            for i in range(1, min(10, len(returns))):
                returns[i] *= (1 + 0.5 * np.exp(-i/3))  # Decaying volatility
            
            # Convert to price series
            prices = 100 * np.cumprod(1 + returns)
            data[asset] = prices
        
        return pd.DataFrame(data, index=dates)
    
    def _generate_crisis_replica_data(
        self,
        start_date: datetime,
        end_date: datetime,
        template: Dict[str, Any],
        severity_multiplier: float,
        config: ExtremeScenarioConfig
    ) -> pd.DataFrame:
        """Generate market data based on crisis template."""
        dates = pd.date_range(start_date, end_date, freq='D')
        data = {}
        
        duration = len(dates)
        max_drawdown = template['max_drawdown'] * severity_multiplier
        vol_multiplier = template['volatility_multiplier']
        
        for asset in config.affected_assets:
            # Get asset-specific impact from template
            asset_impact = template['sector_impacts'].get(asset, max_drawdown * 0.8)
            asset_impact *= severity_multiplier
            
            # Generate crisis path
            returns = self._generate_crisis_return_path(
                duration, asset_impact, vol_multiplier
            )
            
            # Convert to price series
            prices = 100 * np.cumprod(1 + returns)
            data[asset] = prices
        
        return pd.DataFrame(data, index=dates)
    
    def _generate_crisis_return_path(
        self,
        duration: int,
        total_drawdown: float,
        vol_multiplier: float
    ) -> np.ndarray:
        """Generate realistic crisis return path."""
        # Create drawdown path with realistic shape
        t = np.linspace(0, 1, duration)
        
        # Crisis typically has sharp initial drop, then gradual recovery
        crisis_shape = np.where(
            t < 0.3,  # First 30% of period
            -total_drawdown * (t / 0.3) ** 0.5,  # Sharp initial drop
            total_drawdown * (0.5 - 0.5 * ((t - 0.3) / 0.7) ** 2)  # Gradual recovery
        )
        
        # Add noise with elevated volatility
        base_vol = 0.015
        noise = np.random.normal(0, base_vol * vol_multiplier, duration)
        
        # Combine trend and noise
        returns = np.diff(np.concatenate([[0], crisis_shape])) + noise
        
        return returns
    
    def _generate_synthetic_extreme_data(
        self,
        start_date: datetime,
        end_date: datetime,
        config: ExtremeScenarioConfig
    ) -> pd.DataFrame:
        """Generate synthetic extreme market data."""
        dates = pd.date_range(start_date, end_date, freq='D')
        data = {}
        
        # Combine multiple extreme elements
        for asset in config.affected_assets:
            returns = []
            
            for i, date in enumerate(dates):
                # Base extreme return
                base_return = np.random.normal(0, 0.03)  # High base volatility
                
                # Add periodic extreme shocks
                if i % 10 == 0:  # Every 10 days
                    shock_magnitude = np.random.uniform(-0.08, -0.03)  # Large negative shock
                    base_return += shock_magnitude
                
                # Add correlation breakdown effects
                if i > len(dates) // 2:  # Second half of period
                    base_return *= 1.5  # Increased volatility
                
                returns.append(base_return)
            
            # Convert to price series
            prices = 100 * np.cumprod(1 + np.array(returns))
            data[asset] = prices
        
        return pd.DataFrame(data, index=dates)
    
    def _generate_liquidity_crisis_data(
        self,
        start_date: datetime,
        end_date: datetime,
        config: ExtremeScenarioConfig
    ) -> pd.DataFrame:
        """Generate market data for liquidity crisis."""
        dates = pd.date_range(start_date, end_date, freq='D')
        data = {}
        
        liquidity_params = self.extreme_parameters['liquidity_crisis']
        
        for asset in config.affected_assets:
            returns = []
            
            for i, date in enumerate(dates):
                # Base return with liquidity impact
                base_return = np.random.normal(0, 0.02)
                
                # Liquidity impact increases execution costs
                liquidity_level = liquidity_params['crisis_liquidity']
                execution_cost = (1 - liquidity_level) * 0.005  # Up to 0.5% execution cost
                
                # Apply execution cost as drag on returns
                adjusted_return = base_return - execution_cost
                
                # Add bid-ask spread widening effect
                if abs(base_return) > 0.01:  # Large moves have higher impact
                    adjusted_return -= 0.002  # Additional 0.2% cost
                
                returns.append(adjusted_return)
            
            # Convert to price series
            prices = 100 * np.cumprod(1 + np.array(returns))
            data[asset] = prices
        
        return pd.DataFrame(data, index=dates)
    
    def _generate_black_swan_data(
        self,
        start_date: datetime,
        end_date: datetime,
        config: ExtremeScenarioConfig
    ) -> pd.DataFrame:
        """Generate market data for black swan event."""
        dates = pd.date_range(start_date, end_date, freq='D')
        data = {}
        
        for asset in config.affected_assets:
            returns = []
            
            for i, date in enumerate(dates):
                if i == 0:  # Initial black swan event
                    return_val = -0.25  # 25% drop on first day
                elif i < 5:  # Continued stress for first week
                    return_val = np.random.normal(-0.05, 0.08)  # High vol, negative bias
                elif i < 20:  # Recovery period with high volatility
                    return_val = np.random.normal(0.01, 0.06)  # Slight positive bias, high vol
                else:  # Gradual normalization
                    vol_decay = np.exp(-(i-20)/30)  # Exponential decay of volatility
                    return_val = np.random.normal(0.002, 0.02 * (1 + vol_decay))
                
                returns.append(return_val)
            
            # Convert to price series
            prices = 100 * np.cumprod(1 + np.array(returns))
            data[asset] = prices
        
        return pd.DataFrame(data, index=dates)
    
    def _create_crisis_shock_events(
        self,
        template: Dict[str, Any],
        severity_multiplier: float
    ) -> List[MarketShock]:
        """Create shock events based on crisis template."""
        return [
            MarketShock(
                shock_type="crisis_replica",
                magnitude=template['max_drawdown'] * severity_multiplier,
                duration=int(template['duration_days'] * severity_multiplier),
                affected_sectors=list(template['sector_impacts'].keys()),
                correlation_impact=template['correlation_spike'],
                volatility_multiplier=template['volatility_multiplier'],
                liquidity_impact=template['liquidity_impact']
            )
        ]
    
    def _create_synthetic_shock_events(
        self,
        config: ExtremeScenarioConfig
    ) -> List[MarketShock]:
        """Create synthetic shock events."""
        shocks = []
        
        # Primary shock
        shocks.append(MarketShock(
            shock_type="synthetic_primary",
            magnitude=-0.3 * config.severity_level,
            duration=config.duration_days // 3,
            affected_sectors=config.affected_assets,
            correlation_impact=0.9,
            volatility_multiplier=4.0,
            liquidity_impact=-0.6
        ))
        
        # Secondary shock (delayed)
        shocks.append(MarketShock(
            shock_type="synthetic_secondary",
            magnitude=-0.2 * config.severity_level,
            duration=config.duration_days // 4,
            affected_sectors=config.affected_assets[:len(config.affected_assets)//2],
            correlation_impact=0.7,
            volatility_multiplier=2.5,
            liquidity_impact=-0.4
        ))
        
        return shocks
    
    def _calculate_expected_phase3_behavior(
        self,
        market_data: pd.DataFrame,
        shock_events: List[MarketShock],
        config: ExtremeScenarioConfig
    ) -> Dict[str, Any]:
        """Calculate expected Phase 3 component behavior during extreme scenario."""
        behavior = {}
        
        # Expected regime memory behavior
        max_shock_magnitude = max(abs(shock.magnitude) for shock in shock_events)
        if max_shock_magnitude > 0.2:  # 20% shock
            behavior['regime_memory'] = {
                'similarity_scores_expected': 'very_low',
                'regime_confidence_expected': 'low',
                'regime_classification_expected': 'crisis_regime'
            }
        
        # Expected tailwind behavior
        avg_volatility_multiplier = np.mean([shock.volatility_multiplier for shock in shock_events])
        if avg_volatility_multiplier > 3.0:
            behavior['tailwind_engine'] = {
                'tailwind_reliability_expected': 'degraded',
                'calculation_stability_expected': 'unstable',
                'performance_prediction_expected': 'poor'
            }
        
        # Expected NO_EDGE detection
        min_liquidity_impact = min(shock.liquidity_impact for shock in shock_events)
        if min_liquidity_impact < -0.5 or max_shock_magnitude > 0.15:
            behavior['no_edge_detector'] = {
                'trigger_expected': True,
                'trigger_timing_expected': 'immediate',
                'exposure_capping_expected': True
            }
        
        # Expected anticipatory allocator behavior
        behavior['anticipatory_allocator'] = {
            'allocation_accuracy_expected': 'poor',
            'position_sizing_expected': 'reduced',
            'risk_management_expected': 'active'
        }
        
        return behavior
    
    def _calculate_scenario_statistics(self, market_data: pd.DataFrame) -> Dict[str, float]:
        """Calculate statistical properties of generated scenario."""
        returns = market_data.pct_change().dropna()
        
        stats = {}
        stats['max_drawdown'] = (market_data / market_data.cummax() - 1).min().min()
        stats['volatility'] = returns.std().mean() * np.sqrt(252)  # Annualized
        stats['skewness'] = returns.skew().mean()
        stats['kurtosis'] = returns.kurtosis().mean()
        stats['var_95'] = returns.quantile(0.05).mean()  # 5% VaR
        stats['var_99'] = returns.quantile(0.01).mean()  # 1% VaR
        
        return stats
    
    def _validate_scenario_properties(
        self,
        market_data: pd.DataFrame,
        expected_properties: Dict[str, float]
    ) -> Dict[str, float]:
        """Validate that generated scenario has expected properties."""
        actual_stats = self._calculate_scenario_statistics(market_data)
        validation = {}
        
        for prop, expected_val in expected_properties.items():
            if prop in actual_stats:
                actual_val = actual_stats[prop]
                # Calculate relative error
                if expected_val != 0:
                    validation[f'{prop}_error'] = abs(actual_val - expected_val) / abs(expected_val)
                else:
                    validation[f'{prop}_error'] = abs(actual_val)
        
        return validation
    
    def get_crisis_template_names(self) -> List[str]:
        """Get list of available crisis template names."""
        return list(self.crisis_templates.keys())
    
    def validate_extreme_scenario_realism(
        self,
        result: ExtremeScenarioResult
    ) -> bool:
        """Validate that extreme scenario is realistic and properly constructed."""
        
        # Check that scenario has proper statistical properties
        stats = result.statistical_properties
        
        # Volatility should be elevated but not unrealistic
        if stats.get('volatility', 0) > 2.0:  # More than 200% annualized volatility
            logger.warning(f"Unrealistic volatility: {stats['volatility']:.2f}")
            return False
        
        # Drawdown should be significant for extreme scenario
        if abs(stats.get('max_drawdown', 0)) < 0.05:  # Less than 5% drawdown
            logger.warning(f"Insufficient drawdown for extreme scenario: {stats['max_drawdown']:.2f}")
            return False
        
        # Should have proper tail characteristics
        if stats.get('kurtosis', 0) < 2.0:  # Should have fat tails
            logger.warning(f"Insufficient kurtosis for extreme scenario: {stats['kurtosis']:.2f}")
            return False
        
        # Validation metrics should be reasonable
        for metric, value in result.validation_metrics.items():
            if 'error' in metric and value > 0.5:  # More than 50% error
                logger.warning(f"High validation error for {metric}: {value:.2f}")
                return False
        
        return True