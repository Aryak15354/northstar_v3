#!/usr/bin/env python3
"""
Signal Quality Gate - Renaissance-Grade Signal Filtering

This is the layer that transforms weak signals into institutional-grade alpha.
Every signal must pass through these gates before capital allocation.

The goal: Collapse signal count from ~1000 → ~50, but increase alpha per signal by 10x.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

@dataclass
class SignalQualityMetrics:
    """Metrics for signal quality assessment"""
    ic_21d: float
    ic_63d: float  
    ic_126d: float
    median_ic: float
    persistence: float
    regime_coherence: Dict[str, float]
    alpha_confidence: float
    signal_strength: float
    noise_ratio: float
    qualified: bool
    rejection_reason: Optional[str] = None

@dataclass
class QualifiedSignal:
    """A signal that has passed all quality gates"""
    signal_id: str
    raw_signal: np.ndarray
    qualified_signal: np.ndarray
    quality_metrics: SignalQualityMetrics
    effective_weight: float
    regime_lock: Optional[str] = None
    last_updated: datetime = None

class SignalQualityGate:
    """
    Renaissance-grade signal filtering system.
    
    This is the gate between noise and alpha.
    Only signals that pass all quality checks get capital allocation.
    """
    
    def __init__(self):
        self.name = "Signal Quality Gate"
        self.version = "1.0"
        
        # Quality thresholds (institutional grade)
        self.thresholds = {
            'min_median_ic': 0.03,           # Minimum information coefficient
            'min_persistence': 0.2,          # Minimum signal autocorrelation
            'min_regime_coherence': 0.0,     # Minimum PnL in regime
            'min_alpha_confidence': 0.6,     # Minimum Bayesian confidence
            'max_noise_ratio': 2.0,          # Maximum noise-to-signal ratio
            'min_signal_strength': 0.01      # Minimum daily alpha
        }
        
        # Signal tracking
        self.qualified_signals: Dict[str, QualifiedSignal] = {}
        self.rejected_signals: Dict[str, str] = {}
        self.signal_history: Dict[str, List[float]] = {}
        
        print(f"🚪 {self.name} initialized")
        print(f"   Quality thresholds: {self.thresholds}")
    
    def evaluate_signal_quality(self, 
                              signal_id: str,
                              signal_values: np.ndarray,
                              returns: np.ndarray,
                              regime_labels: List[str],
                              bayesian_confidence: float) -> SignalQualityMetrics:
        """
        Evaluate signal quality using Renaissance-grade filters.
        
        This is the core quality assessment that determines if a signal
        deserves capital allocation.
        """
        
        # A) Rolling IC Filter
        ic_metrics = self._calculate_rolling_ic(signal_values, returns)
        
        # B) Persistence Filter  
        persistence = self._calculate_persistence(signal_values)
        
        # C) Regime Coherence
        regime_coherence = self._calculate_regime_coherence(
            signal_values, returns, regime_labels
        )
        
        # D) Signal Strength & Noise Analysis
        signal_strength, noise_ratio = self._analyze_signal_noise(signal_values, returns)
        
        # E) Overall Quality Assessment
        qualified, rejection_reason = self._assess_overall_quality(
            ic_metrics, persistence, regime_coherence, 
            bayesian_confidence, signal_strength, noise_ratio
        )
        
        return SignalQualityMetrics(
            ic_21d=ic_metrics['ic_21d'],
            ic_63d=ic_metrics['ic_63d'],
            ic_126d=ic_metrics['ic_126d'],
            median_ic=ic_metrics['median_ic'],
            persistence=persistence,
            regime_coherence=regime_coherence,
            alpha_confidence=bayesian_confidence,
            signal_strength=signal_strength,
            noise_ratio=noise_ratio,
            qualified=qualified,
            rejection_reason=rejection_reason
        )
    
    def _calculate_rolling_ic(self, signal_values: np.ndarray, returns: np.ndarray) -> Dict[str, float]:
        """Calculate rolling Information Coefficient (IC) metrics"""
        
        if len(signal_values) < 126:
            return {
                'ic_21d': 0.0,
                'ic_63d': 0.0, 
                'ic_126d': 0.0,
                'median_ic': 0.0
            }
        
        # Calculate rolling ICs
        ic_21d_values = []
        ic_63d_values = []
        ic_126d_values = []
        
        for i in range(126, len(signal_values)):
            # 21-day IC
            if i >= 21:
                ic_21 = np.corrcoef(
                    signal_values[i-21:i], 
                    returns[i-21:i]
                )[0, 1]
                if not np.isnan(ic_21):
                    ic_21d_values.append(ic_21)
            
            # 63-day IC
            if i >= 63:
                ic_63 = np.corrcoef(
                    signal_values[i-63:i], 
                    returns[i-63:i]
                )[0, 1]
                if not np.isnan(ic_63):
                    ic_63d_values.append(ic_63)
            
            # 126-day IC
            ic_126 = np.corrcoef(
                signal_values[i-126:i], 
                returns[i-126:i]
            )[0, 1]
            if not np.isnan(ic_126):
                ic_126d_values.append(ic_126)
        
        return {
            'ic_21d': np.mean(ic_21d_values) if ic_21d_values else 0.0,
            'ic_63d': np.mean(ic_63d_values) if ic_63d_values else 0.0,
            'ic_126d': np.mean(ic_126d_values) if ic_126d_values else 0.0,
            'median_ic': np.median(ic_21d_values + ic_63d_values + ic_126d_values) if (ic_21d_values or ic_63d_values or ic_126d_values) else 0.0
        }
    
    def _calculate_persistence(self, signal_values: np.ndarray) -> float:
        """Calculate signal persistence (autocorrelation)"""
        
        if len(signal_values) < 42:  # Need at least 42 days for 21-day lag
            return 0.0
        
        # Calculate 21-day autocorrelation
        try:
            signal_t = signal_values[21:]
            signal_t_minus_21 = signal_values[:-21]
            
            correlation = np.corrcoef(signal_t, signal_t_minus_21)[0, 1]
            
            return abs(correlation) if not np.isnan(correlation) else 0.0
            
        except Exception:
            return 0.0
    
    def _calculate_regime_coherence(self, 
                                  signal_values: np.ndarray, 
                                  returns: np.ndarray,
                                  regime_labels: List[str]) -> Dict[str, float]:
        """Calculate regime-specific signal coherence"""
        
        if len(signal_values) != len(returns) or len(returns) != len(regime_labels):
            return {}
        
        regime_coherence = {}
        
        # Group by regime
        regimes = set(regime_labels)
        
        for regime in regimes:
            regime_indices = [i for i, r in enumerate(regime_labels) if r == regime]
            
            if len(regime_indices) < 10:  # Need minimum observations
                regime_coherence[regime] = 0.0
                continue
            
            regime_signals = signal_values[regime_indices]
            regime_returns = returns[regime_indices]
            
            # Calculate regime-specific metrics
            try:
                # IC in this regime
                ic = np.corrcoef(regime_signals, regime_returns)[0, 1]
                if np.isnan(ic):
                    ic = 0.0
                
                # PnL in this regime (simplified)
                regime_pnl = np.sum(regime_signals * regime_returns)
                
                # Coherence score (both IC and PnL should be positive)
                coherence = ic if (ic > 0 and regime_pnl > 0) else 0.0
                
                regime_coherence[regime] = coherence
                
            except Exception:
                regime_coherence[regime] = 0.0
        
        return regime_coherence
    
    def _analyze_signal_noise(self, signal_values: np.ndarray, returns: np.ndarray) -> Tuple[float, float]:
        """Analyze signal strength vs noise"""
        
        if len(signal_values) < 21:
            return 0.0, float('inf')
        
        try:
            # Signal strength (correlation with returns)
            signal_strength = abs(np.corrcoef(signal_values, returns)[0, 1])
            if np.isnan(signal_strength):
                signal_strength = 0.0
            
            # Noise analysis (signal volatility vs predictive power)
            signal_vol = np.std(signal_values)
            predictive_power = signal_strength * np.std(returns)
            
            noise_ratio = signal_vol / predictive_power if predictive_power > 0 else float('inf')
            
            return signal_strength, noise_ratio
            
        except Exception:
            return 0.0, float('inf')
    
    def _assess_overall_quality(self, 
                              ic_metrics: Dict[str, float],
                              persistence: float,
                              regime_coherence: Dict[str, float],
                              bayesian_confidence: float,
                              signal_strength: float,
                              noise_ratio: float) -> Tuple[bool, Optional[str]]:
        """Assess overall signal quality and determine if it qualifies"""
        
        # Check each quality gate
        
        # Gate 1: IC Filter
        if ic_metrics['median_ic'] < self.thresholds['min_median_ic']:
            return False, f"Low IC: {ic_metrics['median_ic']:.3f} < {self.thresholds['min_median_ic']}"
        
        # Gate 2: Persistence Filter
        if persistence < self.thresholds['min_persistence']:
            return False, f"Low persistence: {persistence:.3f} < {self.thresholds['min_persistence']}"
        
        # Gate 3: Regime Coherence (at least one regime must be coherent)
        if regime_coherence:
            max_coherence = max(regime_coherence.values())
            if max_coherence < self.thresholds['min_regime_coherence']:
                return False, f"No regime coherence: max {max_coherence:.3f} < {self.thresholds['min_regime_coherence']}"
        
        # Gate 4: Bayesian Confidence
        if bayesian_confidence < self.thresholds['min_alpha_confidence']:
            return False, f"Low confidence: {bayesian_confidence:.3f} < {self.thresholds['min_alpha_confidence']}"
        
        # Gate 5: Signal Strength
        if signal_strength < self.thresholds['min_signal_strength']:
            return False, f"Weak signal: {signal_strength:.3f} < {self.thresholds['min_signal_strength']}"
        
        # Gate 6: Noise Ratio
        if noise_ratio > self.thresholds['max_noise_ratio']:
            return False, f"High noise: {noise_ratio:.3f} > {self.thresholds['max_noise_ratio']}"
        
        # All gates passed
        return True, None
    
    def process_signal(self, 
                      signal_id: str,
                      raw_signal: np.ndarray,
                      returns: np.ndarray,
                      regime_labels: List[str],
                      bayesian_confidence: float) -> Optional[QualifiedSignal]:
        """
        Process a signal through all quality gates.
        
        Returns QualifiedSignal if it passes, None if rejected.
        """
        
        print(f"🔍 Processing signal: {signal_id}")
        
        # Evaluate quality
        quality_metrics = self.evaluate_signal_quality(
            signal_id, raw_signal, returns, regime_labels, bayesian_confidence
        )
        
        if not quality_metrics.qualified:
            print(f"   ❌ REJECTED: {quality_metrics.rejection_reason}")
            self.rejected_signals[signal_id] = quality_metrics.rejection_reason
            return None
        
        # Apply signal conditioning
        qualified_signal = self._condition_signal(raw_signal, quality_metrics)
        
        # Calculate effective weight
        effective_weight = self._calculate_effective_weight(quality_metrics)
        
        # Determine regime lock (if signal only works in specific regimes)
        regime_lock = self._determine_regime_lock(quality_metrics.regime_coherence)
        
        # Create qualified signal
        qualified = QualifiedSignal(
            signal_id=signal_id,
            raw_signal=raw_signal,
            qualified_signal=qualified_signal,
            quality_metrics=quality_metrics,
            effective_weight=effective_weight,
            regime_lock=regime_lock,
            last_updated=datetime.now()
        )
        
        self.qualified_signals[signal_id] = qualified
        
        print(f"   ✅ QUALIFIED: IC={quality_metrics.median_ic:.3f}, "
              f"Persistence={quality_metrics.persistence:.3f}, "
              f"Weight={effective_weight:.3f}")
        
        return qualified
    
    def _condition_signal(self, raw_signal: np.ndarray, quality_metrics: SignalQualityMetrics) -> np.ndarray:
        """Apply signal conditioning (smoothing, noise reduction)"""
        
        # Apply exponential smoothing to reduce noise
        alpha = 0.1  # Smoothing factor
        conditioned = np.zeros_like(raw_signal)
        conditioned[0] = raw_signal[0]
        
        for i in range(1, len(raw_signal)):
            conditioned[i] = alpha * raw_signal[i] + (1 - alpha) * conditioned[i-1]
        
        return conditioned
    
    def _calculate_effective_weight(self, quality_metrics: SignalQualityMetrics) -> float:
        """Calculate effective weight based on quality metrics"""
        
        # Base weight from Bayesian confidence
        base_weight = quality_metrics.alpha_confidence
        
        # Adjust for signal strength
        strength_multiplier = min(quality_metrics.signal_strength / self.thresholds['min_signal_strength'], 3.0)
        
        # Adjust for persistence
        persistence_multiplier = min(quality_metrics.persistence / self.thresholds['min_persistence'], 2.0)
        
        # Adjust for IC quality
        ic_multiplier = min(quality_metrics.median_ic / self.thresholds['min_median_ic'], 2.0)
        
        # Combined effective weight
        effective_weight = base_weight * strength_multiplier * persistence_multiplier * ic_multiplier
        
        # Cap at reasonable maximum
        return min(effective_weight, 1.0)
    
    def _determine_regime_lock(self, regime_coherence: Dict[str, float]) -> Optional[str]:
        """Determine if signal should be locked to specific regime"""
        
        if not regime_coherence:
            return None
        
        # Find best regime
        best_regime = max(regime_coherence.items(), key=lambda x: x[1])
        
        # If signal only works well in one regime, lock it
        if best_regime[1] > 0.1 and len([r for r in regime_coherence.values() if r > 0.05]) == 1:
            return best_regime[0]
        
        return None
    
    def get_qualified_signals(self, current_regime: str = None) -> Dict[str, QualifiedSignal]:
        """Get all qualified signals, optionally filtered by regime"""
        
        if current_regime is None:
            return self.qualified_signals
        
        # Filter by regime lock
        regime_signals = {}
        for signal_id, signal in self.qualified_signals.items():
            if signal.regime_lock is None or signal.regime_lock == current_regime:
                regime_signals[signal_id] = signal
        
        return regime_signals
    
    def get_quality_report(self) -> Dict:
        """Generate quality gate performance report"""
        
        total_signals = len(self.qualified_signals) + len(self.rejected_signals)
        qualified_count = len(self.qualified_signals)
        rejection_rate = len(self.rejected_signals) / total_signals if total_signals > 0 else 0
        
        # Rejection reasons
        rejection_reasons = {}
        for reason in self.rejected_signals.values():
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
        
        # Quality distribution
        if self.qualified_signals:
            ic_values = [s.quality_metrics.median_ic for s in self.qualified_signals.values()]
            persistence_values = [s.quality_metrics.persistence for s in self.qualified_signals.values()]
            confidence_values = [s.quality_metrics.alpha_confidence for s in self.qualified_signals.values()]
            
            quality_stats = {
                'median_ic': np.median(ic_values),
                'median_persistence': np.median(persistence_values),
                'median_confidence': np.median(confidence_values),
                'avg_effective_weight': np.mean([s.effective_weight for s in self.qualified_signals.values()])
            }
        else:
            quality_stats = {}
        
        return {
            'total_signals_processed': total_signals,
            'qualified_signals': qualified_count,
            'rejection_rate': rejection_rate,
            'rejection_reasons': rejection_reasons,
            'quality_statistics': quality_stats,
            'thresholds': self.thresholds
        }

def main():
    """Test the Signal Quality Gate"""
    
    print("🧪 TESTING SIGNAL QUALITY GATE")
    print("=" * 60)
    
    # Initialize gate
    gate = SignalQualityGate()
    
    # Generate test signals
    np.random.seed(42)
    n_days = 500
    
    # Market returns
    returns = np.random.normal(0.001, 0.02, n_days)
    
    # Regime labels
    regimes = ['normal'] * 200 + ['crisis'] * 100 + ['recovery'] * 200
    
    # Test signals of different quality
    test_signals = {
        'strong_signal': returns * 0.5 + np.random.normal(0, 0.01, n_days),  # Strong signal
        'weak_signal': np.random.normal(0, 0.02, n_days),                    # Pure noise
        'persistent_signal': np.cumsum(np.random.normal(0, 0.001, n_days)),  # Persistent trend
        'regime_signal': np.where(np.array(regimes) == 'crisis', 0.05, 0.0) + np.random.normal(0, 0.01, n_days)  # Regime-specific
    }
    
    # Process each signal
    for signal_name, signal_values in test_signals.items():
        print(f"\n🔍 Testing: {signal_name}")
        
        qualified = gate.process_signal(
            signal_id=signal_name,
            raw_signal=signal_values,
            returns=returns,
            regime_labels=regimes,
            bayesian_confidence=0.7
        )
        
        if qualified:
            print(f"   ✅ Signal qualified with weight: {qualified.effective_weight:.3f}")
        else:
            print(f"   ❌ Signal rejected")
    
    # Generate report
    print(f"\n📊 QUALITY GATE REPORT")
    print("=" * 40)
    
    report = gate.get_quality_report()
    print(f"Total signals processed: {report['total_signals_processed']}")
    print(f"Qualified signals: {report['qualified_signals']}")
    print(f"Rejection rate: {report['rejection_rate']:.1%}")
    
    if report['rejection_reasons']:
        print(f"\nRejection reasons:")
        for reason, count in report['rejection_reasons'].items():
            print(f"   {reason}: {count}")
    
    if report['quality_statistics']:
        print(f"\nQuality statistics:")
        for metric, value in report['quality_statistics'].items():
            print(f"   {metric}: {value:.3f}")

if __name__ == "__main__":
    main()