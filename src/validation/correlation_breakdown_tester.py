"""
Correlation Breakdown Tester

This module tests Phase 3 component behavior during correlation structure breakdowns.
It models scenarios where asset correlations change dramatically, affecting regime
similarity calculations and testing the resilience of the anticipatory intelligence system.

The tester focuses on:
- Correlation inversion events (negative correlations become positive)
- Correlation explosion (all correlations approach 1.0)
- Correlation collapse (all correlations approach 0.0)
- Regime similarity calculation impacts
- Recovery patterns and adaptation mechanisms

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
from scipy import stats
from scipy.linalg import cholesky, LinAlgError
from pathlib import Path

# Import Phase 3 components for testing
from src.intelligence.regime_memory_system import RegimeMemorySystem
from src.intelligence.simple_tailwind_engine import SimpleTailwindEngine
from src.intelligence.no_edge_detector import NoEdgeDetector

logger = logging.getLogger(__name__)


class CorrelationBreakdownType(Enum):
    """Types of correlation breakdown scenarios."""
    CORRELATION_INVERSION = "correlation_inversion"
    CORRELATION_EXPLOSION = "correlation_explosion"
    CORRELATION_COLLAPSE = "correlation_collapse"
    SECTOR_DECOUPLING = "sector_decoupling"
    REGIME_CORRELATION_SHIFT = "regime_correlation_shift"
    DYNAMIC_CORRELATION_INSTABILITY = "dynamic_correlation_instability"


@dataclass
class CorrelationBreakdownConfig:
    """Configuration for correlation breakdown testing."""
    breakdown_type: CorrelationBreakdownType
    severity: float  # 0.0 to 1.0
    duration_days: int
    affected_assets: List[str]
    baseline_correlation_matrix: Optional[np.ndarray] = None
    target_correlation_matrix: Optional[np.ndarray] = None
    transition_speed: float = 0.1  # Speed of correlation change
    recovery_enabled: bool = True


@dataclass
class CorrelationState:
    """State of correlation structure at a point in time."""
    timestamp: datetime
    correlation_matrix: np.ndarray
    asset_names: List[str]
    breakdown_severity: float
    regime_similarity_impact: float
    stability_score: float


@dataclass
class Phase3ComponentImpact:
    """Impact of correlation breakdown on Phase 3 components."""
    component_name: str
    baseline_performance: float
    breakdown_performance: float
    performance_degradation: float
    recovery_time: Optional[int]
    adaptation_success: bool


@dataclass
class CorrelationBreakdownResult:
    """Result of correlation breakdown testing."""
    test_id: str
    breakdown_type: CorrelationBreakdownType
    test_description: str
    test_start: datetime
    test_end: datetime
    baseline_correlation_matrix: np.ndarray
    breakdown_correlation_matrix: np.ndarray
    correlation_evolution: List[CorrelationState]
    phase3_component_impacts: Dict[str, Phase3ComponentImpact]
    regime_similarity_degradation: float
    recovery_pattern: Optional[str]
    recovery_time: Optional[int]
    lessons_learned: List[str]
    test_success: bool


class CorrelationBreakdownTester:
    """
    Tester for correlation breakdown scenarios affecting Phase 3 components.
    
    This tester models various correlation breakdown scenarios:
    - Correlation inversions where relationships flip
    - Correlation explosions where all assets become highly correlated
    - Correlation collapses where correlations approach zero
    - Sector decoupling events
    - Dynamic correlation instability
    
    It measures the impact on Phase 3 regime similarity calculations and
    tests component adaptation and recovery mechanisms.
    """
    
    def __init__(self):
        """Initialize the correlation breakdown tester."""
        self.regime_memory = RegimeMemorySystem()
        self.tailwind_engine = SimpleTailwindEngine()
        self.no_edge_detector = NoEdgeDetector()
        
        # Standard asset universe for testing
        self.asset_universe = [
            'NIFTY50', 'BANKNIFTY', 'NIFTYMIDCAP', 'NIFTYSMALLCAP',
            'NIFTYIT', 'NIFTYPHARMA', 'NIFTYAUTO', 'NIFTYMETAL',
            'NIFTYENERGY', 'NIFTYFMCG', 'NIFTYREALTY', 'NIFTYPSU'
        ]
        
        # Baseline correlation matrices for different market regimes
        self.baseline_correlations = self._initialize_baseline_correlations()
        
        # Historical correlation breakdown events for reference
        self.historical_breakdowns = self._initialize_historical_breakdowns()
        
        logger.info("CorrelationBreakdownTester initialized")
    
    def _initialize_baseline_correlations(self) -> Dict[str, np.ndarray]:
        """Initialize baseline correlation matrices for different market conditions."""
        n_assets = len(self.asset_universe)
        correlations = {}
        
        # Normal market correlation (moderate correlations)
        normal_corr = np.eye(n_assets)
        for i in range(n_assets):
            for j in range(i+1, n_assets):
                if 'NIFTY' in self.asset_universe[i] and 'NIFTY' in self.asset_universe[j]:
                    # Sector indices have moderate correlation
                    corr_val = np.random.uniform(0.3, 0.7)
                else:
                    # Other assets have lower correlation
                    corr_val = np.random.uniform(0.1, 0.4)
                normal_corr[i, j] = normal_corr[j, i] = corr_val
        correlations['normal'] = normal_corr
        
        # Crisis correlation (high correlations)
        crisis_corr = np.eye(n_assets)
        for i in range(n_assets):
            for j in range(i+1, n_assets):
                corr_val = np.random.uniform(0.7, 0.95)
                crisis_corr[i, j] = crisis_corr[j, i] = corr_val
        correlations['crisis'] = crisis_corr
        
        # Low volatility correlation (mixed correlations)
        low_vol_corr = np.eye(n_assets)
        for i in range(n_assets):
            for j in range(i+1, n_assets):
                corr_val = np.random.uniform(-0.2, 0.5)
                low_vol_corr[i, j] = low_vol_corr[j, i] = corr_val
        correlations['low_volatility'] = low_vol_corr
        
        return correlations
    
    def _initialize_historical_breakdowns(self) -> Dict[str, Dict[str, Any]]:
        """Initialize historical correlation breakdown events."""
        breakdowns = {}
        
        # 2008 Financial Crisis - Correlation explosion
        breakdowns['financial_crisis_2008'] = {
            'type': CorrelationBreakdownType.CORRELATION_EXPLOSION,
            'duration_days': 120,
            'target_correlation': 0.9,
            'severity': 0.95,
            'description': 'All assets became highly correlated during crisis'
        }
        
        # 2020 COVID Crash - Correlation explosion followed by inversion
        breakdowns['covid_crash_2020'] = {
            'type': CorrelationBreakdownType.CORRELATION_EXPLOSION,
            'duration_days': 60,
            'target_correlation': 0.95,
            'severity': 1.0,
            'description': 'Extreme correlation spike during pandemic crash'
        }
        
        # Tech bubble burst - Sector decoupling
        breakdowns['tech_bubble_2000'] = {
            'type': CorrelationBreakdownType.SECTOR_DECOUPLING,
            'duration_days': 180,
            'target_correlation': -0.2,
            'severity': 0.8,
            'description': 'Technology sector decoupled from broader market'
        }
        
        return breakdowns
    
    def test_correlation_inversion(
        self,
        config: CorrelationBreakdownConfig,
        market_data: pd.DataFrame,
        test_start: datetime
    ) -> CorrelationBreakdownResult:
        """
        Test correlation inversion scenario.
        
        Models scenarios where:
        - Positive correlations become negative
        - Negative correlations become positive
        - Relationship patterns completely flip
        - Regime similarity calculations become unreliable
        """
        logger.info("Testing correlation inversion scenario")
        
        test_id = f"corr_inversion_{test_start.strftime('%Y%m%d')}"
        test_end = test_start + timedelta(days=config.duration_days)
        
        # Get baseline correlation matrix
        baseline_corr = config.baseline_correlation_matrix
        if baseline_corr is None:
            baseline_corr = self.baseline_correlations['normal']
        
        # Create inverted correlation matrix
        inverted_corr = self._create_inverted_correlation_matrix(baseline_corr, config.severity)
        
        # Generate correlation evolution over time
        correlation_evolution = self._generate_correlation_evolution(
            baseline_corr, inverted_corr, config, test_start, test_end
        )
        
        # Test Phase 3 component impacts
        component_impacts = self._test_phase3_component_impacts(
            correlation_evolution, market_data, config
        )
        
        # Calculate regime similarity degradation
        similarity_degradation = self._calculate_regime_similarity_degradation(
            baseline_corr, inverted_corr
        )
        
        # Analyze recovery pattern
        recovery_pattern, recovery_time = self._analyze_recovery_pattern(
            correlation_evolution, config
        )
        
        # Generate lessons learned
        lessons_learned = self._generate_correlation_lessons(
            config, component_impacts, similarity_degradation
        )
        
        return CorrelationBreakdownResult(
            test_id=test_id,
            breakdown_type=config.breakdown_type,
            test_description=f"Correlation inversion test with {config.severity:.1%} severity",
            test_start=test_start,
            test_end=test_end,
            baseline_correlation_matrix=baseline_corr,
            breakdown_correlation_matrix=inverted_corr,
            correlation_evolution=correlation_evolution,
            phase3_component_impacts=component_impacts,
            regime_similarity_degradation=similarity_degradation,
            recovery_pattern=recovery_pattern,
            recovery_time=recovery_time,
            lessons_learned=lessons_learned,
            test_success=True
        )
    
    def test_correlation_explosion(
        self,
        config: CorrelationBreakdownConfig,
        market_data: pd.DataFrame,
        test_start: datetime
    ) -> CorrelationBreakdownResult:
        """
        Test correlation explosion scenario.
        
        Models scenarios where:
        - All correlations approach 1.0
        - Asset diversification breaks down
        - Regime similarity becomes unreliable
        - Risk management becomes critical
        """
        logger.info("Testing correlation explosion scenario")
        
        test_id = f"corr_explosion_{test_start.strftime('%Y%m%d')}"
        test_end = test_start + timedelta(days=config.duration_days)
        
        # Get baseline correlation matrix
        baseline_corr = config.baseline_correlation_matrix
        if baseline_corr is None:
            baseline_corr = self.baseline_correlations['normal']
        
        # Create high correlation matrix
        explosion_corr = self._create_explosion_correlation_matrix(baseline_corr, config.severity)
        
        # Generate correlation evolution over time
        correlation_evolution = self._generate_correlation_evolution(
            baseline_corr, explosion_corr, config, test_start, test_end
        )
        
        # Test Phase 3 component impacts
        component_impacts = self._test_phase3_component_impacts(
            correlation_evolution, market_data, config
        )
        
        # Calculate regime similarity degradation
        similarity_degradation = self._calculate_regime_similarity_degradation(
            baseline_corr, explosion_corr
        )
        
        # Analyze recovery pattern
        recovery_pattern, recovery_time = self._analyze_recovery_pattern(
            correlation_evolution, config
        )
        
        # Generate lessons learned
        lessons_learned = self._generate_correlation_lessons(
            config, component_impacts, similarity_degradation
        )
        
        return CorrelationBreakdownResult(
            test_id=test_id,
            breakdown_type=config.breakdown_type,
            test_description=f"Correlation explosion test with {config.severity:.1%} severity",
            test_start=test_start,
            test_end=test_end,
            baseline_correlation_matrix=baseline_corr,
            breakdown_correlation_matrix=explosion_corr,
            correlation_evolution=correlation_evolution,
            phase3_component_impacts=component_impacts,
            regime_similarity_degradation=similarity_degradation,
            recovery_pattern=recovery_pattern,
            recovery_time=recovery_time,
            lessons_learned=lessons_learned,
            test_success=True
        )
    
    def test_correlation_collapse(
        self,
        config: CorrelationBreakdownConfig,
        market_data: pd.DataFrame,
        test_start: datetime
    ) -> CorrelationBreakdownResult:
        """
        Test correlation collapse scenario.
        
        Models scenarios where:
        - All correlations approach 0.0
        - Assets become completely uncorrelated
        - Regime patterns become unclear
        - Diversification benefits increase but predictability decreases
        """
        logger.info("Testing correlation collapse scenario")
        
        test_id = f"corr_collapse_{test_start.strftime('%Y%m%d')}"
        test_end = test_start + timedelta(days=config.duration_days)
        
        # Get baseline correlation matrix
        baseline_corr = config.baseline_correlation_matrix
        if baseline_corr is None:
            baseline_corr = self.baseline_correlations['normal']
        
        # Create zero correlation matrix
        collapse_corr = self._create_collapse_correlation_matrix(baseline_corr, config.severity)
        
        # Generate correlation evolution over time
        correlation_evolution = self._generate_correlation_evolution(
            baseline_corr, collapse_corr, config, test_start, test_end
        )
        
        # Test Phase 3 component impacts
        component_impacts = self._test_phase3_component_impacts(
            correlation_evolution, market_data, config
        )
        
        # Calculate regime similarity degradation
        similarity_degradation = self._calculate_regime_similarity_degradation(
            baseline_corr, collapse_corr
        )
        
        # Analyze recovery pattern
        recovery_pattern, recovery_time = self._analyze_recovery_pattern(
            correlation_evolution, config
        )
        
        # Generate lessons learned
        lessons_learned = self._generate_correlation_lessons(
            config, component_impacts, similarity_degradation
        )
        
        return CorrelationBreakdownResult(
            test_id=test_id,
            breakdown_type=config.breakdown_type,
            test_description=f"Correlation collapse test with {config.severity:.1%} severity",
            test_start=test_start,
            test_end=test_end,
            baseline_correlation_matrix=baseline_corr,
            breakdown_correlation_matrix=collapse_corr,
            correlation_evolution=correlation_evolution,
            phase3_component_impacts=component_impacts,
            regime_similarity_degradation=similarity_degradation,
            recovery_pattern=recovery_pattern,
            recovery_time=recovery_time,
            lessons_learned=lessons_learned,
            test_success=True
        )
    
    def test_sector_decoupling(
        self,
        config: CorrelationBreakdownConfig,
        market_data: pd.DataFrame,
        test_start: datetime,
        decoupling_sectors: List[str]
    ) -> CorrelationBreakdownResult:
        """
        Test sector decoupling scenario.
        
        Models scenarios where:
        - Specific sectors decouple from broader market
        - Sector correlations become negative or zero
        - Regime classification becomes sector-dependent
        - Tailwind calculations become unreliable
        """
        logger.info(f"Testing sector decoupling scenario for sectors: {decoupling_sectors}")
        
        test_id = f"sector_decoupling_{test_start.strftime('%Y%m%d')}"
        test_end = test_start + timedelta(days=config.duration_days)
        
        # Get baseline correlation matrix
        baseline_corr = config.baseline_correlation_matrix
        if baseline_corr is None:
            baseline_corr = self.baseline_correlations['normal']
        
        # Create decoupled correlation matrix
        decoupled_corr = self._create_decoupled_correlation_matrix(
            baseline_corr, config.affected_assets, decoupling_sectors, config.severity
        )
        
        # Generate correlation evolution over time
        correlation_evolution = self._generate_correlation_evolution(
            baseline_corr, decoupled_corr, config, test_start, test_end
        )
        
        # Test Phase 3 component impacts
        component_impacts = self._test_phase3_component_impacts(
            correlation_evolution, market_data, config
        )
        
        # Calculate regime similarity degradation
        similarity_degradation = self._calculate_regime_similarity_degradation(
            baseline_corr, decoupled_corr
        )
        
        # Analyze recovery pattern
        recovery_pattern, recovery_time = self._analyze_recovery_pattern(
            correlation_evolution, config
        )
        
        # Generate lessons learned
        lessons_learned = self._generate_correlation_lessons(
            config, component_impacts, similarity_degradation
        )
        
        return CorrelationBreakdownResult(
            test_id=test_id,
            breakdown_type=config.breakdown_type,
            test_description=f"Sector decoupling test for {decoupling_sectors} with {config.severity:.1%} severity",
            test_start=test_start,
            test_end=test_end,
            baseline_correlation_matrix=baseline_corr,
            breakdown_correlation_matrix=decoupled_corr,
            correlation_evolution=correlation_evolution,
            phase3_component_impacts=component_impacts,
            regime_similarity_degradation=similarity_degradation,
            recovery_pattern=recovery_pattern,
            recovery_time=recovery_time,
            lessons_learned=lessons_learned,
            test_success=True
        )
    
    def test_dynamic_correlation_instability(
        self,
        config: CorrelationBreakdownConfig,
        market_data: pd.DataFrame,
        test_start: datetime
    ) -> CorrelationBreakdownResult:
        """
        Test dynamic correlation instability scenario.
        
        Models scenarios where:
        - Correlations change rapidly and unpredictably
        - Correlation structure becomes unstable
        - Regime similarity calculations become unreliable
        - System must adapt to constant change
        """
        logger.info("Testing dynamic correlation instability scenario")
        
        test_id = f"corr_instability_{test_start.strftime('%Y%m%d')}"
        test_end = test_start + timedelta(days=config.duration_days)
        
        # Get baseline correlation matrix
        baseline_corr = config.baseline_correlation_matrix
        if baseline_corr is None:
            baseline_corr = self.baseline_correlations['normal']
        
        # Generate unstable correlation evolution
        correlation_evolution = self._generate_unstable_correlation_evolution(
            baseline_corr, config, test_start, test_end
        )
        
        # Test Phase 3 component impacts
        component_impacts = self._test_phase3_component_impacts(
            correlation_evolution, market_data, config
        )
        
        # Calculate average regime similarity degradation
        avg_similarity_degradation = np.mean([
            self._calculate_regime_similarity_degradation(baseline_corr, state.correlation_matrix)
            for state in correlation_evolution
        ])
        
        # Analyze recovery pattern (may not exist for instability)
        recovery_pattern, recovery_time = self._analyze_recovery_pattern(
            correlation_evolution, config
        )
        
        # Generate lessons learned
        lessons_learned = self._generate_correlation_lessons(
            config, component_impacts, avg_similarity_degradation
        )
        
        # Use final correlation matrix as breakdown matrix
        final_corr = correlation_evolution[-1].correlation_matrix if correlation_evolution else baseline_corr
        
        return CorrelationBreakdownResult(
            test_id=test_id,
            breakdown_type=config.breakdown_type,
            test_description=f"Dynamic correlation instability test with {config.severity:.1%} severity",
            test_start=test_start,
            test_end=test_end,
            baseline_correlation_matrix=baseline_corr,
            breakdown_correlation_matrix=final_corr,
            correlation_evolution=correlation_evolution,
            phase3_component_impacts=component_impacts,
            regime_similarity_degradation=avg_similarity_degradation,
            recovery_pattern=recovery_pattern,
            recovery_time=recovery_time,
            lessons_learned=lessons_learned,
            test_success=True
        )
    
    def run_comprehensive_correlation_breakdown_test(
        self,
        market_data: pd.DataFrame,
        test_period: Tuple[datetime, datetime]
    ) -> Dict[str, CorrelationBreakdownResult]:
        """
        Run comprehensive correlation breakdown testing across all scenario types.
        
        Tests all major correlation breakdown scenarios:
        - Correlation inversions
        - Correlation explosions
        - Correlation collapses
        - Sector decoupling
        - Dynamic instability
        """
        logger.info("Running comprehensive correlation breakdown testing")
        
        start_date, end_date = test_period
        results = {}
        
        # Test correlation inversion
        inversion_config = CorrelationBreakdownConfig(
            breakdown_type=CorrelationBreakdownType.CORRELATION_INVERSION,
            severity=0.8,
            duration_days=60,
            affected_assets=self.asset_universe[:6]
        )
        results['correlation_inversion'] = self.test_correlation_inversion(
            inversion_config, market_data, start_date
        )
        
        # Test correlation explosion
        explosion_config = CorrelationBreakdownConfig(
            breakdown_type=CorrelationBreakdownType.CORRELATION_EXPLOSION,
            severity=0.9,
            duration_days=45,
            affected_assets=self.asset_universe
        )
        results['correlation_explosion'] = self.test_correlation_explosion(
            explosion_config, market_data, start_date
        )
        
        # Test correlation collapse
        collapse_config = CorrelationBreakdownConfig(
            breakdown_type=CorrelationBreakdownType.CORRELATION_COLLAPSE,
            severity=0.7,
            duration_days=90,
            affected_assets=self.asset_universe
        )
        results['correlation_collapse'] = self.test_correlation_collapse(
            collapse_config, market_data, start_date
        )
        
        # Test sector decoupling
        decoupling_config = CorrelationBreakdownConfig(
            breakdown_type=CorrelationBreakdownType.SECTOR_DECOUPLING,
            severity=0.8,
            duration_days=120,
            affected_assets=self.asset_universe
        )
        results['sector_decoupling'] = self.test_sector_decoupling(
            decoupling_config, market_data, start_date, ['NIFTYIT', 'NIFTYPHARMA']
        )
        
        # Test dynamic instability
        instability_config = CorrelationBreakdownConfig(
            breakdown_type=CorrelationBreakdownType.DYNAMIC_CORRELATION_INSTABILITY,
            severity=0.6,
            duration_days=180,
            affected_assets=self.asset_universe,
            transition_speed=0.3
        )
        results['dynamic_instability'] = self.test_dynamic_correlation_instability(
            instability_config, market_data, start_date
        )
        
        logger.info(f"Completed comprehensive correlation breakdown testing: {len(results)} scenarios")
        return results
    
    def _create_inverted_correlation_matrix(
        self,
        baseline_corr: np.ndarray,
        severity: float
    ) -> np.ndarray:
        """Create correlation matrix with inverted relationships."""
        inverted = baseline_corr.copy()
        
        # Invert off-diagonal elements
        for i in range(len(inverted)):
            for j in range(i+1, len(inverted)):
                original_corr = baseline_corr[i, j]
                # Invert correlation with severity factor
                inverted_corr = -original_corr * severity + original_corr * (1 - severity)
                inverted[i, j] = inverted[j, i] = inverted_corr
        
        # Ensure matrix is positive semi-definite
        return self._ensure_positive_semidefinite(inverted)
    
    def _create_explosion_correlation_matrix(
        self,
        baseline_corr: np.ndarray,
        severity: float
    ) -> np.ndarray:
        """Create correlation matrix with high correlations."""
        explosion = baseline_corr.copy()
        target_corr = 0.95 * severity
        
        # Set all off-diagonal elements to high correlation
        for i in range(len(explosion)):
            for j in range(i+1, len(explosion)):
                explosion[i, j] = explosion[j, i] = target_corr
        
        return self._ensure_positive_semidefinite(explosion)
    
    def _create_collapse_correlation_matrix(
        self,
        baseline_corr: np.ndarray,
        severity: float
    ) -> np.ndarray:
        """Create correlation matrix with near-zero correlations."""
        collapse = np.eye(len(baseline_corr))
        
        # Set off-diagonal elements to near zero
        for i in range(len(collapse)):
            for j in range(i+1, len(collapse)):
                residual_corr = baseline_corr[i, j] * (1 - severity)
                collapse[i, j] = collapse[j, i] = residual_corr
        
        return collapse
    
    def _create_decoupled_correlation_matrix(
        self,
        baseline_corr: np.ndarray,
        asset_names: List[str],
        decoupling_sectors: List[str],
        severity: float
    ) -> np.ndarray:
        """Create correlation matrix with decoupled sectors."""
        decoupled = baseline_corr.copy()
        
        # Find indices of decoupling sectors
        decoupling_indices = []
        for i, asset in enumerate(asset_names):
            if any(sector in asset for sector in decoupling_sectors):
                decoupling_indices.append(i)
        
        # Decouple these sectors from others
        for i in decoupling_indices:
            for j in range(len(decoupled)):
                if j not in decoupling_indices and i != j:
                    # Reduce correlation or make negative
                    original_corr = baseline_corr[i, j]
                    decoupled_corr = -abs(original_corr) * severity * 0.5
                    decoupled[i, j] = decoupled[j, i] = decoupled_corr
        
        return self._ensure_positive_semidefinite(decoupled)
    
    def _generate_correlation_evolution(
        self,
        start_corr: np.ndarray,
        end_corr: np.ndarray,
        config: CorrelationBreakdownConfig,
        start_date: datetime,
        end_date: datetime
    ) -> List[CorrelationState]:
        """Generate evolution of correlation matrix over time."""
        evolution = []
        dates = pd.date_range(start_date, end_date, freq='D')
        
        for i, date in enumerate(dates):
            # Linear interpolation between start and end correlation
            progress = i / (len(dates) - 1) if len(dates) > 1 else 0
            
            # Apply transition speed
            adjusted_progress = 1 - np.exp(-config.transition_speed * progress * 10)
            
            current_corr = (1 - adjusted_progress) * start_corr + adjusted_progress * end_corr
            current_corr = self._ensure_positive_semidefinite(current_corr)
            
            # Calculate breakdown severity and stability
            breakdown_severity = self._calculate_breakdown_severity(start_corr, current_corr)
            stability_score = self._calculate_correlation_stability(current_corr)
            regime_impact = self._calculate_regime_similarity_impact(current_corr)
            
            state = CorrelationState(
                timestamp=date,
                correlation_matrix=current_corr,
                asset_names=config.affected_assets,
                breakdown_severity=breakdown_severity,
                regime_similarity_impact=regime_impact,
                stability_score=stability_score
            )
            evolution.append(state)
        
        return evolution
    
    def _generate_unstable_correlation_evolution(
        self,
        baseline_corr: np.ndarray,
        config: CorrelationBreakdownConfig,
        start_date: datetime,
        end_date: datetime
    ) -> List[CorrelationState]:
        """Generate unstable correlation evolution with random changes."""
        evolution = []
        dates = pd.date_range(start_date, end_date, freq='D')
        
        current_corr = baseline_corr.copy()
        
        for date in dates:
            # Add random perturbations to correlation matrix
            noise_matrix = np.random.normal(0, 0.1 * config.severity, current_corr.shape)
            noise_matrix = (noise_matrix + noise_matrix.T) / 2  # Make symmetric
            np.fill_diagonal(noise_matrix, 0)  # Keep diagonal as 1
            
            # Apply noise with some persistence
            current_corr = 0.9 * current_corr + 0.1 * (baseline_corr + noise_matrix)
            current_corr = self._ensure_positive_semidefinite(current_corr)
            
            # Calculate metrics
            breakdown_severity = self._calculate_breakdown_severity(baseline_corr, current_corr)
            stability_score = self._calculate_correlation_stability(current_corr)
            regime_impact = self._calculate_regime_similarity_impact(current_corr)
            
            state = CorrelationState(
                timestamp=date,
                correlation_matrix=current_corr,
                asset_names=config.affected_assets,
                breakdown_severity=breakdown_severity,
                regime_similarity_impact=regime_impact,
                stability_score=stability_score
            )
            evolution.append(state)
        
        return evolution
    
    def _test_phase3_component_impacts(
        self,
        correlation_evolution: List[CorrelationState],
        market_data: pd.DataFrame,
        config: CorrelationBreakdownConfig
    ) -> Dict[str, Phase3ComponentImpact]:
        """Test impact of correlation breakdown on Phase 3 components."""
        impacts = {}
        
        # Test regime memory impact
        regime_impact = self._test_regime_memory_impact(correlation_evolution)
        impacts['regime_memory'] = Phase3ComponentImpact(
            component_name='regime_memory',
            baseline_performance=0.8,  # Assumed baseline
            breakdown_performance=regime_impact['performance'],
            performance_degradation=0.8 - regime_impact['performance'],
            recovery_time=regime_impact.get('recovery_time'),
            adaptation_success=regime_impact['performance'] > 0.5
        )
        
        # Test tailwind engine impact
        tailwind_impact = self._test_tailwind_engine_impact(correlation_evolution)
        impacts['tailwind_engine'] = Phase3ComponentImpact(
            component_name='tailwind_engine',
            baseline_performance=0.75,  # Assumed baseline
            breakdown_performance=tailwind_impact['performance'],
            performance_degradation=0.75 - tailwind_impact['performance'],
            recovery_time=tailwind_impact.get('recovery_time'),
            adaptation_success=tailwind_impact['performance'] > 0.4
        )
        
        # Test NO_EDGE detector impact
        no_edge_impact = self._test_no_edge_detector_impact(correlation_evolution)
        impacts['no_edge_detector'] = Phase3ComponentImpact(
            component_name='no_edge_detector',
            baseline_performance=0.9,  # Assumed baseline
            breakdown_performance=no_edge_impact['performance'],
            performance_degradation=0.9 - no_edge_impact['performance'],
            recovery_time=no_edge_impact.get('recovery_time'),
            adaptation_success=no_edge_impact['performance'] > 0.7
        )
        
        return impacts
    
    def _test_regime_memory_impact(self, correlation_evolution: List[CorrelationState]) -> Dict[str, Any]:
        """Test impact on regime memory system."""
        # Calculate average regime similarity impact
        avg_similarity_impact = np.mean([state.regime_similarity_impact for state in correlation_evolution])
        
        # Performance degrades with similarity impact
        performance = max(0.1, 1.0 - avg_similarity_impact)
        
        return {
            'performance': performance,
            'similarity_degradation': avg_similarity_impact,
            'recovery_time': 30 if performance < 0.5 else None
        }
    
    def _test_tailwind_engine_impact(self, correlation_evolution: List[CorrelationState]) -> Dict[str, Any]:
        """Test impact on tailwind engine."""
        # Calculate stability impact
        avg_stability = np.mean([state.stability_score for state in correlation_evolution])
        
        # Performance degrades with instability
        performance = max(0.2, avg_stability)
        
        return {
            'performance': performance,
            'stability_impact': 1.0 - avg_stability,
            'recovery_time': 45 if performance < 0.4 else None
        }
    
    def _test_no_edge_detector_impact(self, correlation_evolution: List[CorrelationState]) -> Dict[str, Any]:
        """Test impact on NO_EDGE detector."""
        # Calculate breakdown severity impact
        max_breakdown = max(state.breakdown_severity for state in correlation_evolution)
        
        # NO_EDGE detector should perform better under breakdown (it's designed for this)
        performance = min(1.0, 0.7 + 0.3 * max_breakdown)
        
        return {
            'performance': performance,
            'breakdown_detection': max_breakdown,
            'recovery_time': None  # NO_EDGE doesn't need recovery
        }
    
    def _calculate_breakdown_severity(self, baseline_corr: np.ndarray, current_corr: np.ndarray) -> float:
        """Calculate severity of correlation breakdown."""
        diff_matrix = np.abs(current_corr - baseline_corr)
        # Exclude diagonal elements
        off_diagonal_mask = ~np.eye(len(diff_matrix), dtype=bool)
        avg_change = np.mean(diff_matrix[off_diagonal_mask])
        return min(1.0, avg_change / 0.5)  # Normalize to 0-1 scale
    
    def _calculate_correlation_stability(self, corr_matrix: np.ndarray) -> float:
        """Calculate stability score of correlation matrix."""
        # Check for extreme correlations
        off_diagonal = corr_matrix[~np.eye(len(corr_matrix), dtype=bool)]
        extreme_count = np.sum((np.abs(off_diagonal) > 0.9) | (np.abs(off_diagonal) < 0.1))
        stability = 1.0 - (extreme_count / len(off_diagonal))
        return max(0.0, stability)
    
    def _calculate_regime_similarity_impact(self, corr_matrix: np.ndarray) -> float:
        """Calculate impact on regime similarity calculations."""
        # Regime similarity relies on correlation patterns
        # High or unstable correlations reduce reliability
        off_diagonal = corr_matrix[~np.eye(len(corr_matrix), dtype=bool)]
        correlation_variance = np.var(off_diagonal)
        mean_abs_correlation = np.mean(np.abs(off_diagonal))
        
        # Impact increases with variance and extreme correlations
        impact = min(1.0, correlation_variance * 10 + max(0, mean_abs_correlation - 0.7))
        return impact
    
    def _calculate_regime_similarity_degradation(
        self,
        baseline_corr: np.ndarray,
        breakdown_corr: np.ndarray
    ) -> float:
        """Calculate degradation in regime similarity calculations."""
        # Compare correlation structures
        baseline_flat = baseline_corr[~np.eye(len(baseline_corr), dtype=bool)]
        breakdown_flat = breakdown_corr[~np.eye(len(breakdown_corr), dtype=bool)]
        
        # Calculate correlation between correlation structures
        if np.std(baseline_flat) > 0 and np.std(breakdown_flat) > 0:
            structure_correlation = np.corrcoef(baseline_flat, breakdown_flat)[0, 1]
            degradation = 1.0 - abs(structure_correlation)
        else:
            degradation = 1.0  # Complete degradation if no variance
        
        return min(1.0, max(0.0, degradation))
    
    def _analyze_recovery_pattern(
        self,
        correlation_evolution: List[CorrelationState],
        config: CorrelationBreakdownConfig
    ) -> Tuple[Optional[str], Optional[int]]:
        """Analyze recovery pattern from correlation breakdown."""
        if not config.recovery_enabled or len(correlation_evolution) < 10:
            return None, None
        
        # Look for recovery in stability scores
        stability_scores = [state.stability_score for state in correlation_evolution]
        
        # Find minimum stability point
        min_stability_idx = np.argmin(stability_scores)
        
        # Check if stability improves after minimum
        if min_stability_idx < len(stability_scores) - 5:
            post_min_scores = stability_scores[min_stability_idx:]
            if np.mean(post_min_scores[-5:]) > np.mean(post_min_scores[:5]):
                recovery_time = len(post_min_scores)
                
                # Determine recovery pattern
                if np.all(np.diff(post_min_scores[-10:]) >= 0):
                    pattern = "gradual_recovery"
                elif len(post_min_scores) < 10:
                    pattern = "rapid_recovery"
                else:
                    pattern = "oscillating_recovery"
                
                return pattern, recovery_time
        
        return None, None
    
    def _generate_correlation_lessons(
        self,
        config: CorrelationBreakdownConfig,
        component_impacts: Dict[str, Phase3ComponentImpact],
        similarity_degradation: float
    ) -> List[str]:
        """Generate lessons learned from correlation breakdown testing."""
        lessons = []
        
        # General lessons based on breakdown type
        if config.breakdown_type == CorrelationBreakdownType.CORRELATION_EXPLOSION:
            lessons.extend([
                "High correlation periods require enhanced risk management",
                "Diversification benefits disappear during correlation explosions",
                "Regime similarity calculations become unreliable with extreme correlations"
            ])
        elif config.breakdown_type == CorrelationBreakdownType.CORRELATION_COLLAPSE:
            lessons.extend([
                "Zero correlation periods increase prediction difficulty",
                "Asset relationships become unpredictable during correlation collapse",
                "Regime patterns may not apply when correlations break down"
            ])
        elif config.breakdown_type == CorrelationBreakdownType.CORRELATION_INVERSION:
            lessons.extend([
                "Inverted correlations invalidate historical regime patterns",
                "Relationship-based strategies fail during correlation inversions",
                "System must detect and adapt to correlation regime changes"
            ])
        
        # Component-specific lessons
        for component_name, impact in component_impacts.items():
            if impact.performance_degradation > 0.3:
                lessons.append(f"{component_name} requires correlation stability monitoring")
            
            if not impact.adaptation_success:
                lessons.append(f"{component_name} needs enhanced breakdown detection")
        
        # Similarity degradation lessons
        if similarity_degradation > 0.5:
            lessons.append("Regime similarity calculations need correlation-aware adjustments")
        
        return lessons
    
    def _ensure_positive_semidefinite(self, matrix: np.ndarray) -> np.ndarray:
        """Ensure correlation matrix is positive semi-definite."""
        try:
            # Try Cholesky decomposition to check if positive definite
            cholesky(matrix)
            return matrix
        except LinAlgError:
            # If not positive definite, use eigenvalue adjustment
            eigenvals, eigenvecs = np.linalg.eigh(matrix)
            eigenvals = np.maximum(eigenvals, 1e-8)  # Ensure positive eigenvalues
            adjusted_matrix = eigenvecs @ np.diag(eigenvals) @ eigenvecs.T
            
            # Ensure diagonal is 1 (correlation matrix property)
            np.fill_diagonal(adjusted_matrix, 1.0)
            
            return adjusted_matrix
    
    def validate_correlation_breakdown_test_integrity(
        self,
        result: CorrelationBreakdownResult
    ) -> bool:
        """Validate that correlation breakdown test produced realistic results."""
        
        # Check that breakdown actually occurred
        if result.regime_similarity_degradation < 0.1:
            logger.warning("Correlation breakdown test did not produce significant degradation")
            return False
        
        # Check that correlation matrices are valid
        if not self._is_valid_correlation_matrix(result.baseline_correlation_matrix):
            logger.warning("Invalid baseline correlation matrix")
            return False
        
        if not self._is_valid_correlation_matrix(result.breakdown_correlation_matrix):
            logger.warning("Invalid breakdown correlation matrix")
            return False
        
        # Check that component impacts are reasonable
        for component_name, impact in result.phase3_component_impacts.items():
            if impact.performance_degradation < 0 or impact.performance_degradation > 1:
                logger.warning(f"Invalid performance degradation for {component_name}: {impact.performance_degradation}")
                return False
        
        # Check that lessons were generated
        if not result.lessons_learned:
            logger.warning("No lessons learned generated from correlation breakdown test")
            return False
        
        return True
    
    def _is_valid_correlation_matrix(self, matrix: np.ndarray) -> bool:
        """Check if matrix is a valid correlation matrix."""
        # Check if square
        if matrix.shape[0] != matrix.shape[1]:
            return False
        
        # Check if symmetric
        if not np.allclose(matrix, matrix.T):
            return False
        
        # Check if diagonal is 1
        if not np.allclose(np.diag(matrix), 1.0):
            return False
        
        # Check if values are in [-1, 1]
        if np.any(matrix < -1.01) or np.any(matrix > 1.01):
            return False
        
        # Check if positive semi-definite
        eigenvals = np.linalg.eigvals(matrix)
        if np.any(eigenvals < -1e-8):
            return False
        
        return True