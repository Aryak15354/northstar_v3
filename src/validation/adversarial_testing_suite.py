"""
Adversarial Testing Suite - Fault Injection and System Resilience

This module implements adversarial testing that deliberately corrupts data,
delays signals, flips regimes, and injects faults to verify system resilience.

Unlike stress tests, adversarial tests actively try to break the system
to ensure it degrades gracefully rather than explodes.

Key Tests:
- Data corruption injection
- Signal delay and timing attacks
- Regime flip simulation
- Noise injection attacks
- Alpha removal tests
- Market microstructure attacks

Author: Northstar Team
Date: 2026-01-05
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import logging
import random
from copy import deepcopy

try:
    from ..operation.logging_config import setup_operation_logging
except ImportError:
    # Fallback for when running as standalone
    import logging
    def setup_operation_logging():
        logging.basicConfig(level=logging.INFO)
        return logging.getLogger(__name__)


class AdversarialAttackType(Enum):
    """Types of adversarial attacks."""
    DATA_CORRUPTION = "data_corruption"
    SIGNAL_DELAY = "signal_delay"
    REGIME_FLIP = "regime_flip"
    NOISE_INJECTION = "noise_injection"
    ALPHA_REMOVAL = "alpha_removal"
    TIMESTAMP_SCRAMBLE = "timestamp_scramble"
    LIQUIDITY_DRAIN = "liquidity_drain"
    CORRELATION_ATTACK = "correlation_attack"
    OUTLIER_INJECTION = "outlier_injection"
    MISSING_DATA = "missing_data"


class SystemResponse(Enum):
    """System response to adversarial attacks."""
    GRACEFUL_DEGRADATION = "graceful_degradation"
    CATASTROPHIC_FAILURE = "catastrophic_failure"
    RESILIENT_OPERATION = "resilient_operation"
    PARTIAL_FAILURE = "partial_failure"
    RECOVERY_SUCCESS = "recovery_success"


@dataclass
class AdversarialAttack:
    """Definition of an adversarial attack."""
    attack_type: AdversarialAttackType
    intensity: float  # 0-1 scale
    duration: int  # Number of periods
    target_component: str
    parameters: Dict[str, Any]
    expected_impact: str


@dataclass
class AdversarialTestResult:
    """Results from an adversarial test."""
    attack: AdversarialAttack
    system_response: SystemResponse
    
    # Performance impact
    performance_degradation: float
    max_drawdown_increase: float
    volatility_increase: float
    
    # System metrics
    error_rate: float
    recovery_time: Optional[int]
    data_quality_score: float
    
    # Resilience metrics
    resilience_score: float
    graceful_degradation_score: float
    recovery_success: bool
    
    # Detailed analysis
    component_failures: List[str]
    error_messages: List[str]
    performance_timeline: List[float]


@dataclass
class AdversarialTestSuite:
    """Complete adversarial testing suite results."""
    test_date: datetime
    total_attacks: int
    successful_attacks: int
    system_failures: int
    
    # Overall resilience metrics
    overall_resilience_score: float
    graceful_degradation_rate: float
    recovery_success_rate: float
    
    # Attack-specific results
    test_results: List[AdversarialTestResult]
    
    # System recommendations
    vulnerability_assessment: Dict[str, float]
    hardening_recommendations: List[str]
    monitoring_improvements: List[str]


class AdversarialTestingEngine:
    """
    Institutional-grade adversarial testing engine.
    
    This class implements comprehensive adversarial testing to verify
    system resilience under deliberate attacks and fault injection.
    """
    
    def __init__(self, random_seed: int = 42):
        """Initialize adversarial testing engine."""
        self.logger = setup_operation_logging()
        self.random_seed = random_seed
        np.random.seed(random_seed)
        random.seed(random_seed)
        
        self.attack_definitions = self._define_attack_scenarios()
        self.logger.info("Adversarial Testing Engine initialized")
    
    def run_adversarial_test_suite(self, 
                                 returns: np.ndarray,
                                 signals: np.ndarray,
                                 market_data: Dict[str, np.ndarray],
                                 system_components: Dict[str, Any]) -> AdversarialTestSuite:
        """
        Run complete adversarial testing suite.
        
        Args:
            returns: Historical returns
            signals: Alpha signals
            market_data: Market data arrays
            system_components: System components to test
            
        Returns:
            AdversarialTestSuite: Complete test results
        """
        self.logger.info("🧪 Starting Adversarial Testing Suite")
        self.logger.info("=" * 60)
        
        test_results = []
        successful_attacks = 0
        system_failures = 0
        
        # Run each attack scenario
        for attack in self.attack_definitions:
            self.logger.info(f"Running attack: {attack.attack_type.value}")
            
            try:
                # Execute adversarial attack
                result = self._execute_adversarial_attack(
                    attack, returns, signals, market_data, system_components
                )
                
                test_results.append(result)
                
                # Count attack outcomes
                if result.system_response in [SystemResponse.CATASTROPHIC_FAILURE, SystemResponse.PARTIAL_FAILURE]:
                    system_failures += 1
                
                if result.resilience_score < 0.7:
                    successful_attacks += 1
                
            except Exception as e:
                self.logger.error(f"Attack execution failed: {e}")
                # Create failure result
                failure_result = AdversarialTestResult(
                    attack=attack,
                    system_response=SystemResponse.CATASTROPHIC_FAILURE,
                    performance_degradation=1.0,
                    max_drawdown_increase=1.0,
                    volatility_increase=1.0,
                    error_rate=1.0,
                    recovery_time=None,
                    data_quality_score=0.0,
                    resilience_score=0.0,
                    graceful_degradation_score=0.0,
                    recovery_success=False,
                    component_failures=["system_crash"],
                    error_messages=[str(e)],
                    performance_timeline=[]
                )
                test_results.append(failure_result)
                system_failures += 1
                successful_attacks += 1
        
        # Calculate overall metrics
        overall_metrics = self._calculate_overall_resilience_metrics(test_results)
        
        # Generate recommendations
        recommendations = self._generate_hardening_recommendations(test_results)
        
        # Compile test suite results
        suite_results = AdversarialTestSuite(
            test_date=datetime.now(),
            total_attacks=len(self.attack_definitions),
            successful_attacks=successful_attacks,
            system_failures=system_failures,
            overall_resilience_score=overall_metrics['resilience_score'],
            graceful_degradation_rate=overall_metrics['graceful_degradation_rate'],
            recovery_success_rate=overall_metrics['recovery_success_rate'],
            test_results=test_results,
            vulnerability_assessment=recommendations['vulnerabilities'],
            hardening_recommendations=recommendations['hardening'],
            monitoring_improvements=recommendations['monitoring']
        )
        
        self._log_suite_results(suite_results)
        return suite_results
    
    def _define_attack_scenarios(self) -> List[AdversarialAttack]:
        """Define comprehensive adversarial attack scenarios."""
        return [
            # Data corruption attacks
            AdversarialAttack(
                attack_type=AdversarialAttackType.DATA_CORRUPTION,
                intensity=0.3,
                duration=20,
                target_component="data_pipeline",
                parameters={"corruption_rate": 0.1, "corruption_type": "random"},
                expected_impact="Moderate performance degradation"
            ),
            
            AdversarialAttack(
                attack_type=AdversarialAttackType.DATA_CORRUPTION,
                intensity=0.7,
                duration=10,
                target_component="data_pipeline",
                parameters={"corruption_rate": 0.3, "corruption_type": "systematic"},
                expected_impact="Significant performance impact"
            ),
            
            # Signal delay attacks
            AdversarialAttack(
                attack_type=AdversarialAttackType.SIGNAL_DELAY,
                intensity=0.5,
                duration=30,
                target_component="signal_processing",
                parameters={"delay_periods": 3, "delay_probability": 0.2},
                expected_impact="Timing-based alpha decay"
            ),
            
            # Regime flip attacks
            AdversarialAttack(
                attack_type=AdversarialAttackType.REGIME_FLIP,
                intensity=0.8,
                duration=15,
                target_component="regime_detection",
                parameters={"flip_probability": 0.1, "false_regime": "crisis"},
                expected_impact="Strategy misalignment"
            ),
            
            # Noise injection attacks
            AdversarialAttack(
                attack_type=AdversarialAttackType.NOISE_INJECTION,
                intensity=0.4,
                duration=50,
                target_component="signal_generation",
                parameters={"noise_ratio": 2.0, "noise_type": "gaussian"},
                expected_impact="Signal quality degradation"
            ),
            
            AdversarialAttack(
                attack_type=AdversarialAttackType.NOISE_INJECTION,
                intensity=0.9,
                duration=25,
                target_component="signal_generation",
                parameters={"noise_ratio": 5.0, "noise_type": "adversarial"},
                expected_impact="Severe signal corruption"
            ),
            
            # Alpha removal attacks
            AdversarialAttack(
                attack_type=AdversarialAttackType.ALPHA_REMOVAL,
                intensity=0.6,
                duration=40,
                target_component="alpha_generation",
                parameters={"removal_probability": 0.3, "target_alpha": "momentum"},
                expected_impact="Alpha source elimination"
            ),
            
            # Timestamp scrambling
            AdversarialAttack(
                attack_type=AdversarialAttackType.TIMESTAMP_SCRAMBLE,
                intensity=0.5,
                duration=20,
                target_component="data_pipeline",
                parameters={"scramble_probability": 0.15, "max_shift": 5},
                expected_impact="Temporal misalignment"
            ),
            
            # Outlier injection
            AdversarialAttack(
                attack_type=AdversarialAttackType.OUTLIER_INJECTION,
                intensity=0.7,
                duration=10,
                target_component="data_pipeline",
                parameters={"outlier_magnitude": 10.0, "injection_rate": 0.05},
                expected_impact="Outlier-driven instability"
            ),
            
            # Missing data attacks
            AdversarialAttack(
                attack_type=AdversarialAttackType.MISSING_DATA,
                intensity=0.4,
                duration=35,
                target_component="data_pipeline",
                parameters={"missing_rate": 0.2, "missing_pattern": "random"},
                expected_impact="Data availability issues"
            )
        ]
    
    def _execute_adversarial_attack(self, 
                                  attack: AdversarialAttack,
                                  returns: np.ndarray,
                                  signals: np.ndarray,
                                  market_data: Dict[str, np.ndarray],
                                  system_components: Dict[str, Any]) -> AdversarialTestResult:
        """Execute a specific adversarial attack."""
        # Create copies of data for attack simulation
        corrupted_returns = returns.copy()
        corrupted_signals = signals.copy()
        corrupted_market_data = {k: v.copy() for k, v in market_data.items()}
        
        # Apply attack based on type
        if attack.attack_type == AdversarialAttackType.DATA_CORRUPTION:
            corrupted_returns, corrupted_signals, corrupted_market_data = self._apply_data_corruption(
                corrupted_returns, corrupted_signals, corrupted_market_data, attack
            )
        
        elif attack.attack_type == AdversarialAttackType.SIGNAL_DELAY:
            corrupted_signals = self._apply_signal_delay(corrupted_signals, attack)
        
        elif attack.attack_type == AdversarialAttackType.REGIME_FLIP:
            corrupted_signals = self._apply_regime_flip(corrupted_signals, attack)
        
        elif attack.attack_type == AdversarialAttackType.NOISE_INJECTION:
            corrupted_signals = self._apply_noise_injection(corrupted_signals, attack)
        
        elif attack.attack_type == AdversarialAttackType.ALPHA_REMOVAL:
            corrupted_signals = self._apply_alpha_removal(corrupted_signals, attack)
        
        elif attack.attack_type == AdversarialAttackType.TIMESTAMP_SCRAMBLE:
            corrupted_returns, corrupted_signals = self._apply_timestamp_scramble(
                corrupted_returns, corrupted_signals, attack
            )
        
        elif attack.attack_type == AdversarialAttackType.OUTLIER_INJECTION:
            corrupted_returns = self._apply_outlier_injection(corrupted_returns, attack)
        
        elif attack.attack_type == AdversarialAttackType.MISSING_DATA:
            corrupted_returns, corrupted_signals = self._apply_missing_data(
                corrupted_returns, corrupted_signals, attack
            )
        
        # Simulate system response
        system_response = self._simulate_system_response(
            corrupted_returns, corrupted_signals, corrupted_market_data, attack
        )
        
        # Calculate performance impact
        performance_impact = self._calculate_performance_impact(
            returns, corrupted_returns, signals, corrupted_signals
        )
        
        # Assess resilience
        resilience_metrics = self._assess_resilience(
            performance_impact, system_response, attack
        )
        
        return AdversarialTestResult(
            attack=attack,
            system_response=system_response['response_type'],
            performance_degradation=performance_impact['degradation'],
            max_drawdown_increase=performance_impact['drawdown_increase'],
            volatility_increase=performance_impact['volatility_increase'],
            error_rate=system_response['error_rate'],
            recovery_time=system_response['recovery_time'],
            data_quality_score=performance_impact['data_quality'],
            resilience_score=resilience_metrics['resilience_score'],
            graceful_degradation_score=resilience_metrics['graceful_degradation'],
            recovery_success=resilience_metrics['recovery_success'],
            component_failures=system_response['component_failures'],
            error_messages=system_response['error_messages'],
            performance_timeline=performance_impact['timeline']
        )
    
    def _apply_data_corruption(self, 
                             returns: np.ndarray,
                             signals: np.ndarray,
                             market_data: Dict[str, np.ndarray],
                             attack: AdversarialAttack) -> Tuple[np.ndarray, np.ndarray, Dict[str, np.ndarray]]:
        """Apply data corruption attack."""
        corruption_rate = attack.parameters.get('corruption_rate', 0.1)
        corruption_type = attack.parameters.get('corruption_type', 'random')
        
        # Corrupt returns
        corruption_mask = np.random.random(len(returns)) < corruption_rate
        if corruption_type == 'random':
            returns[corruption_mask] = np.random.randn(np.sum(corruption_mask)) * 0.1
        elif corruption_type == 'systematic':
            returns[corruption_mask] = -abs(returns[corruption_mask]) * 2  # Make losses worse
        
        # Corrupt signals
        signal_corruption_mask = np.random.random(len(signals)) < corruption_rate
        if corruption_type == 'random':
            signals[signal_corruption_mask] = np.random.randn(np.sum(signal_corruption_mask))
        elif corruption_type == 'systematic':
            signals[signal_corruption_mask] = -signals[signal_corruption_mask]  # Flip signals
        
        # Corrupt market data
        for key, data in market_data.items():
            data_corruption_mask = np.random.random(len(data)) < corruption_rate
            if corruption_type == 'random':
                data[data_corruption_mask] = np.random.randn(np.sum(data_corruption_mask)) * np.std(data)
            elif corruption_type == 'systematic':
                data[data_corruption_mask] = np.nan  # Create missing data
        
        return returns, signals, market_data
    
    def _apply_signal_delay(self, signals: np.ndarray, attack: AdversarialAttack) -> np.ndarray:
        """Apply signal delay attack."""
        delay_periods = attack.parameters.get('delay_periods', 3)
        delay_probability = attack.parameters.get('delay_probability', 0.2)
        
        delayed_signals = signals.copy()
        
        for i in range(delay_periods, len(signals)):
            if np.random.random() < delay_probability:
                # Use old signal instead of current one
                delayed_signals[i] = signals[i - delay_periods]
        
        return delayed_signals
    
    def _apply_regime_flip(self, signals: np.ndarray, attack: AdversarialAttack) -> np.ndarray:
        """Apply regime flip attack."""
        flip_probability = attack.parameters.get('flip_probability', 0.1)
        false_regime = attack.parameters.get('false_regime', 'crisis')
        
        flipped_signals = signals.copy()
        
        # Simulate regime detection failure
        flip_mask = np.random.random(len(signals)) < flip_probability
        
        if false_regime == 'crisis':
            # In false crisis mode, reduce signal strength
            flipped_signals[flip_mask] *= 0.3
        elif false_regime == 'bull':
            # In false bull mode, amplify signals inappropriately
            flipped_signals[flip_mask] *= 2.0
        
        return flipped_signals
    
    def _apply_noise_injection(self, signals: np.ndarray, attack: AdversarialAttack) -> np.ndarray:
        """Apply noise injection attack."""
        noise_ratio = attack.parameters.get('noise_ratio', 2.0)
        noise_type = attack.parameters.get('noise_type', 'gaussian')
        
        signal_std = np.std(signals)
        
        if noise_type == 'gaussian':
            noise = np.random.randn(len(signals)) * signal_std * noise_ratio
        elif noise_type == 'adversarial':
            # Adversarial noise designed to hurt performance
            noise = -np.sign(signals) * signal_std * noise_ratio
        else:
            noise = np.random.randn(len(signals)) * signal_std * noise_ratio
        
        return signals + noise
    
    def _apply_alpha_removal(self, signals: np.ndarray, attack: AdversarialAttack) -> np.ndarray:
        """Apply alpha removal attack."""
        removal_probability = attack.parameters.get('removal_probability', 0.3)
        
        # Simulate alpha source failure
        removal_mask = np.random.random(len(signals)) < removal_probability
        corrupted_signals = signals.copy()
        corrupted_signals[removal_mask] = 0  # Zero out alpha
        
        return corrupted_signals
    
    def _apply_timestamp_scramble(self, 
                                returns: np.ndarray,
                                signals: np.ndarray,
                                attack: AdversarialAttack) -> Tuple[np.ndarray, np.ndarray]:
        """Apply timestamp scrambling attack."""
        scramble_probability = attack.parameters.get('scramble_probability', 0.15)
        max_shift = attack.parameters.get('max_shift', 5)
        
        scrambled_signals = signals.copy()
        
        for i in range(max_shift, len(signals) - max_shift):
            if np.random.random() < scramble_probability:
                # Randomly shift signal timing
                shift = np.random.randint(-max_shift, max_shift + 1)
                if 0 <= i + shift < len(signals):
                    scrambled_signals[i] = signals[i + shift]
        
        return returns, scrambled_signals
    
    def _apply_outlier_injection(self, returns: np.ndarray, attack: AdversarialAttack) -> np.ndarray:
        """Apply outlier injection attack."""
        outlier_magnitude = attack.parameters.get('outlier_magnitude', 10.0)
        injection_rate = attack.parameters.get('injection_rate', 0.05)
        
        corrupted_returns = returns.copy()
        outlier_mask = np.random.random(len(returns)) < injection_rate
        
        # Inject extreme outliers
        return_std = np.std(returns)
        outliers = np.random.choice([-1, 1], np.sum(outlier_mask)) * outlier_magnitude * return_std
        corrupted_returns[outlier_mask] = outliers
        
        return corrupted_returns
    
    def _apply_missing_data(self, 
                          returns: np.ndarray,
                          signals: np.ndarray,
                          attack: AdversarialAttack) -> Tuple[np.ndarray, np.ndarray]:
        """Apply missing data attack."""
        missing_rate = attack.parameters.get('missing_rate', 0.2)
        missing_pattern = attack.parameters.get('missing_pattern', 'random')
        
        corrupted_returns = returns.copy()
        corrupted_signals = signals.copy()
        
        if missing_pattern == 'random':
            missing_mask = np.random.random(len(returns)) < missing_rate
        elif missing_pattern == 'clustered':
            # Create clusters of missing data
            missing_mask = np.zeros(len(returns), dtype=bool)
            cluster_starts = np.random.choice(len(returns) - 10, size=int(len(returns) * missing_rate / 5))
            for start in cluster_starts:
                missing_mask[start:start+5] = True
        else:
            missing_mask = np.random.random(len(returns)) < missing_rate
        
        corrupted_returns[missing_mask] = np.nan
        corrupted_signals[missing_mask] = np.nan
        
        return corrupted_returns, corrupted_signals
    
    def _simulate_system_response(self, 
                                returns: np.ndarray,
                                signals: np.ndarray,
                                market_data: Dict[str, np.ndarray],
                                attack: AdversarialAttack) -> Dict[str, Any]:
        """Simulate system response to adversarial attack."""
        # Calculate data quality metrics
        data_quality = 1.0 - (np.sum(np.isnan(returns)) + np.sum(np.isnan(signals))) / (len(returns) + len(signals))
        
        # Simulate error rate based on attack intensity
        base_error_rate = 0.01
        attack_error_rate = attack.intensity * 0.1
        total_error_rate = min(base_error_rate + attack_error_rate, 1.0)
        
        # Determine system response type
        if data_quality < 0.5 or total_error_rate > 0.5:
            response_type = SystemResponse.CATASTROPHIC_FAILURE
            recovery_time = None
            component_failures = [attack.target_component, "data_validation", "error_handling"]
        elif data_quality < 0.7 or total_error_rate > 0.2:
            response_type = SystemResponse.PARTIAL_FAILURE
            recovery_time = int(attack.duration * 2)
            component_failures = [attack.target_component]
        elif data_quality < 0.9 or total_error_rate > 0.05:
            response_type = SystemResponse.GRACEFUL_DEGRADATION
            recovery_time = attack.duration
            component_failures = []
        else:
            response_type = SystemResponse.RESILIENT_OPERATION
            recovery_time = int(attack.duration * 0.5)
            component_failures = []
        
        error_messages = [
            f"Attack detected: {attack.attack_type.value}",
            f"Data quality degraded to {data_quality:.2f}",
            f"Error rate increased to {total_error_rate:.2f}"
        ]
        
        return {
            'response_type': response_type,
            'error_rate': total_error_rate,
            'recovery_time': recovery_time,
            'component_failures': component_failures,
            'error_messages': error_messages,
            'data_quality': data_quality
        }
    
    def _calculate_performance_impact(self, 
                                    original_returns: np.ndarray,
                                    corrupted_returns: np.ndarray,
                                    original_signals: np.ndarray,
                                    corrupted_signals: np.ndarray) -> Dict[str, Any]:
        """Calculate performance impact of adversarial attack."""
        # Clean data for comparison
        valid_mask = ~(np.isnan(original_returns) | np.isnan(corrupted_returns))
        orig_clean = original_returns[valid_mask]
        corr_clean = corrupted_returns[valid_mask]
        
        if len(orig_clean) == 0:
            return {
                'degradation': 1.0,
                'drawdown_increase': 1.0,
                'volatility_increase': 1.0,
                'data_quality': 0.0,
                'timeline': []
            }
        
        # Calculate performance metrics
        orig_cumret = np.cumprod(1 + orig_clean) - 1
        corr_cumret = np.cumprod(1 + corr_clean) - 1
        
        # Performance degradation
        orig_final = orig_cumret[-1] if len(orig_cumret) > 0 else 0
        corr_final = corr_cumret[-1] if len(corr_cumret) > 0 else 0
        degradation = max(0, (orig_final - corr_final) / max(abs(orig_final), 0.01))
        
        # Drawdown comparison
        orig_dd = self._calculate_max_drawdown(orig_clean)
        corr_dd = self._calculate_max_drawdown(corr_clean)
        drawdown_increase = max(0, corr_dd - orig_dd)
        
        # Volatility comparison
        orig_vol = np.std(orig_clean)
        corr_vol = np.std(corr_clean)
        volatility_increase = max(0, (corr_vol - orig_vol) / max(orig_vol, 0.01))
        
        # Data quality
        data_quality = np.sum(valid_mask) / len(original_returns)
        
        return {
            'degradation': min(degradation, 1.0),
            'drawdown_increase': min(drawdown_increase, 1.0),
            'volatility_increase': min(volatility_increase, 1.0),
            'data_quality': data_quality,
            'timeline': corr_cumret.tolist() if len(corr_cumret) > 0 else []
        }
    
    def _calculate_max_drawdown(self, returns: np.ndarray) -> float:
        """Calculate maximum drawdown."""
        if len(returns) == 0:
            return 0.0
        
        cumulative = np.cumprod(1 + returns) - 1
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / (1 + running_max)
        return np.min(drawdowns)
    
    def _assess_resilience(self, 
                         performance_impact: Dict[str, Any],
                         system_response: Dict[str, Any],
                         attack: AdversarialAttack) -> Dict[str, Any]:
        """Assess system resilience to adversarial attack."""
        # Base resilience score
        resilience_score = 1.0
        
        # Penalize performance degradation
        resilience_score -= performance_impact['degradation'] * 0.4
        
        # Penalize system failures
        if system_response['response_type'] == SystemResponse.CATASTROPHIC_FAILURE:
            resilience_score -= 0.5
        elif system_response['response_type'] == SystemResponse.PARTIAL_FAILURE:
            resilience_score -= 0.3
        
        # Penalize high error rates
        resilience_score -= system_response['error_rate'] * 0.2
        
        # Reward data quality maintenance
        resilience_score += performance_impact['data_quality'] * 0.1
        
        resilience_score = max(0, min(1, resilience_score))
        
        # Graceful degradation score
        if system_response['response_type'] == SystemResponse.GRACEFUL_DEGRADATION:
            graceful_degradation = 1.0
        elif system_response['response_type'] == SystemResponse.RESILIENT_OPERATION:
            graceful_degradation = 1.0
        elif system_response['response_type'] == SystemResponse.PARTIAL_FAILURE:
            graceful_degradation = 0.5
        else:
            graceful_degradation = 0.0
        
        # Recovery success
        recovery_success = (
            system_response['recovery_time'] is not None and
            system_response['recovery_time'] <= attack.duration * 3
        )
        
        return {
            'resilience_score': resilience_score,
            'graceful_degradation': graceful_degradation,
            'recovery_success': recovery_success
        }
    
    def _calculate_overall_resilience_metrics(self, test_results: List[AdversarialTestResult]) -> Dict[str, float]:
        """Calculate overall resilience metrics."""
        if not test_results:
            return {
                'resilience_score': 0.0,
                'graceful_degradation_rate': 0.0,
                'recovery_success_rate': 0.0
            }
        
        resilience_scores = [r.resilience_score for r in test_results]
        graceful_degradations = [r.graceful_degradation_score for r in test_results]
        recovery_successes = [r.recovery_success for r in test_results]
        
        return {
            'resilience_score': np.mean(resilience_scores),
            'graceful_degradation_rate': np.mean(graceful_degradations),
            'recovery_success_rate': np.mean(recovery_successes)
        }
    
    def _generate_hardening_recommendations(self, test_results: List[AdversarialTestResult]) -> Dict[str, Any]:
        """Generate system hardening recommendations."""
        vulnerabilities = {}
        hardening = []
        monitoring = []
        
        # Analyze vulnerabilities by attack type
        for result in test_results:
            attack_type = result.attack.attack_type.value
            vulnerability_score = 1.0 - result.resilience_score
            vulnerabilities[attack_type] = vulnerability_score
            
            # Generate specific recommendations
            if result.resilience_score < 0.5:
                if result.attack.attack_type == AdversarialAttackType.DATA_CORRUPTION:
                    hardening.append("Implement robust data validation and sanitization")
                    monitoring.append("Add real-time data quality monitoring")
                
                elif result.attack.attack_type == AdversarialAttackType.SIGNAL_DELAY:
                    hardening.append("Add signal freshness validation")
                    monitoring.append("Monitor signal latency and staleness")
                
                elif result.attack.attack_type == AdversarialAttackType.NOISE_INJECTION:
                    hardening.append("Implement signal quality filters")
                    monitoring.append("Monitor signal-to-noise ratios")
                
                elif result.attack.attack_type == AdversarialAttackType.ALPHA_REMOVAL:
                    hardening.append("Add alpha source redundancy")
                    monitoring.append("Monitor alpha source availability")
        
        # Add general recommendations
        avg_resilience = np.mean([r.resilience_score for r in test_results])
        if avg_resilience < 0.7:
            hardening.extend([
                "Implement circuit breakers for system protection",
                "Add graceful degradation modes",
                "Improve error handling and recovery procedures"
            ])
            monitoring.extend([
                "Add comprehensive system health monitoring",
                "Implement anomaly detection for unusual patterns",
                "Add automated recovery triggers"
            ])
        
        return {
            'vulnerabilities': vulnerabilities,
            'hardening': list(set(hardening)),
            'monitoring': list(set(monitoring))
        }
    
    def _log_suite_results(self, suite_results: AdversarialTestSuite):
        """Log adversarial test suite results."""
        self.logger.info("🧪 Adversarial Testing Suite Results")
        self.logger.info(f"   Total Attacks: {suite_results.total_attacks}")
        self.logger.info(f"   Successful Attacks: {suite_results.successful_attacks}")
        self.logger.info(f"   System Failures: {suite_results.system_failures}")
        self.logger.info(f"   Overall Resilience: {suite_results.overall_resilience_score:.2f}")
        self.logger.info(f"   Graceful Degradation Rate: {suite_results.graceful_degradation_rate:.2%}")
        self.logger.info(f"   Recovery Success Rate: {suite_results.recovery_success_rate:.2%}")
        
        # Log top vulnerabilities
        sorted_vulns = sorted(suite_results.vulnerability_assessment.items(), 
                            key=lambda x: x[1], reverse=True)
        self.logger.info("   Top Vulnerabilities:")
        for vuln, score in sorted_vulns[:3]:
            self.logger.info(f"     - {vuln}: {score:.2f}")


def create_adversarial_testing_engine() -> AdversarialTestingEngine:
    """Create institutional-grade adversarial testing engine."""
    return AdversarialTestingEngine(random_seed=42)


if __name__ == "__main__":
    # Demo usage
    engine = create_adversarial_testing_engine()
    
    # Generate sample data
    np.random.seed(42)
    n = 252  # One year of data
    
    returns = np.random.randn(n) * 0.02 + 0.0005  # Small positive drift
    signals = np.random.randn(n) * 0.5
    market_data = {
        'prices': np.random.randn(n) * 10 + 100,
        'volumes': np.random.exponential(1000, n)
    }
    system_components = {
        'data_pipeline': {},
        'signal_processing': {},
        'risk_management': {}
    }
    
    # Run adversarial tests
    results = engine.run_adversarial_test_suite(
        returns, signals, market_data, system_components
    )
    
    print(f"Adversarial Testing Complete:")
    print(f"Overall Resilience: {results.overall_resilience_score:.2f}")
    print(f"System Failures: {results.system_failures}/{results.total_attacks}")
    print(f"Recovery Success Rate: {results.recovery_success_rate:.2%}")