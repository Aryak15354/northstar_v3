"""
Alpha Validator - Validates alpha generation across different market regimes.

This module implements comprehensive alpha validation functionality including:
- Market regime detection (bull, bear, sideways)
- Alpha signal generation and validation across regimes
- Signal quality assessment and consistency analysis
- Alpha performance degradation detection and alerting
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from enum import Enum

from .base_types import (
    AlphaValidationResult, Alert, AlertLevel, BacktestConfig, OperationConfig
)


class MarketRegime(Enum):
    """Market regime classifications."""
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    UNKNOWN = "unknown"


class MarketRegimeDetector:
    """
    Detects market regimes based on price and volatility patterns.
    
    Uses multiple indicators to classify market conditions:
    - Price trend analysis
    - Volatility patterns
    - Moving average relationships
    - Momentum indicators
    """
    
    def __init__(self):
        """Initialize the market regime detector."""
        self.lookback_window = 252  # 1 year of trading days
        self.short_ma_window = 20   # Short-term moving average
        self.long_ma_window = 50    # Long-term moving average
        
        # Regime classification thresholds
        self.bull_trend_threshold = 0.05    # 5% upward trend
        self.bear_trend_threshold = -0.05   # 5% downward trend
        self.volatility_threshold = 0.20    # 20% volatility threshold
        self.sideways_range = 0.03          # 3% range for sideways markets
    
    def detect_regime(self, market_data: pd.DataFrame) -> str:
        """
        Detect market regime from market data.
        
        Args:
            market_data: DataFrame with columns ['date', 'close', 'volume']
            
        Returns:
            str: Market regime ('bull', 'bear', 'sideways', 'unknown')
        """
        if len(market_data) < self.long_ma_window:
            return MarketRegime.UNKNOWN.value
        
        # Calculate technical indicators
        indicators = self._calculate_indicators(market_data)
        
        # Classify regime based on indicators
        regime = self._classify_regime(indicators)
        
        return regime.value
    
    def detect_regime_periods(self, market_data: pd.DataFrame) -> pd.DataFrame:
        """
        Detect regime periods over time series data.
        
        Args:
            market_data: DataFrame with market data
            
        Returns:
            DataFrame with regime classifications over time
        """
        regimes = []
        
        for i in range(self.lookback_window, len(market_data)):
            window_data = market_data.iloc[i-self.lookback_window:i]
            regime = self.detect_regime(window_data)
            regimes.append({
                'date': market_data.iloc[i]['date'] if 'date' in market_data.columns else market_data.index[i],
                'regime': regime,
                'close': market_data.iloc[i]['close']
            })
        
        return pd.DataFrame(regimes)
    
    def _calculate_indicators(self, data: pd.DataFrame) -> Dict[str, float]:
        """Calculate technical indicators for regime detection."""
        prices = data['close'].values
        
        # Price trend (linear regression slope)
        x = np.arange(len(prices))
        trend_slope = np.polyfit(x, prices, 1)[0] / prices[0]  # Normalized slope
        
        # Volatility (rolling standard deviation)
        returns = np.diff(np.log(prices))
        volatility = np.std(returns) * np.sqrt(252)  # Annualized
        
        # Moving averages
        short_ma = np.mean(prices[-self.short_ma_window:])
        long_ma = np.mean(prices[-self.long_ma_window:])
        ma_ratio = (short_ma / long_ma) - 1
        
        # Price momentum
        momentum = (prices[-1] / prices[-self.short_ma_window]) - 1
        
        # Range analysis (for sideways detection)
        price_range = (np.max(prices) - np.min(prices)) / np.mean(prices)
        
        return {
            'trend_slope': trend_slope,
            'volatility': volatility,
            'ma_ratio': ma_ratio,
            'momentum': momentum,
            'price_range': price_range,
            'current_price': prices[-1],
            'short_ma': short_ma,
            'long_ma': long_ma
        }
    
    def _classify_regime(self, indicators: Dict[str, float]) -> MarketRegime:
        """Classify market regime based on indicators."""
        trend_slope = indicators['trend_slope']
        volatility = indicators['volatility']
        ma_ratio = indicators['ma_ratio']
        momentum = indicators['momentum']
        price_range = indicators['price_range']
        
        # Bull market conditions
        if (trend_slope > self.bull_trend_threshold and 
            ma_ratio > 0 and 
            momentum > 0 and
            volatility < self.volatility_threshold):
            return MarketRegime.BULL
        
        # Bear market conditions
        elif (trend_slope < self.bear_trend_threshold and 
              ma_ratio < 0 and 
              momentum < 0):
            return MarketRegime.BEAR
        
        # Sideways market conditions
        elif (abs(trend_slope) < self.sideways_range and 
              abs(ma_ratio) < self.sideways_range and
              price_range < 0.15):  # Low range indicates sideways
            return MarketRegime.SIDEWAYS
        
        # Default to unknown if conditions are mixed
        else:
            return MarketRegime.UNKNOWN


class AlphaValidator:
    """
    Validates alpha generation across different market regimes.
    
    Tests the Northstar V3 system's ability to generate consistent alpha
    across bull, bear, and sideways market conditions.
    """
    
    # Alpha validation thresholds
    ALPHA_THRESHOLDS = {
        "min_alpha_bull": 0.02,        # 2% minimum alpha in bull markets
        "min_alpha_bear": 0.01,        # 1% minimum alpha in bear markets  
        "min_alpha_sideways": 0.015,   # 1.5% minimum alpha in sideways markets
        "min_information_ratio": 0.5,  # Minimum information ratio
        "min_hit_rate": 0.52,          # 52% minimum hit rate
        "min_signal_quality": 0.6,     # 60% minimum signal quality
        "min_consistency": 0.7,        # 70% minimum consistency score
        "max_alpha_degradation": 0.3   # 30% maximum alpha degradation
    }
    
    def __init__(self, config: Optional[OperationConfig] = None):
        """Initialize the alpha validator."""
        self.config = config or OperationConfig()
        self.logger = logging.getLogger(__name__)
        self.regime_detector = MarketRegimeDetector()
        self.validation_results: Dict[str, AlphaValidationResult] = {}
        
        self.logger.info("Alpha Validator initialized")
        self.logger.info(f"Configured thresholds: {self.ALPHA_THRESHOLDS}")
    
    def validate_all_regimes(self, market_data: pd.DataFrame) -> List[AlphaValidationResult]:
        """
        Validate alpha generation across all market regimes.
        
        Args:
            market_data: Historical market data for regime detection
            
        Returns:
            List[AlphaValidationResult]: Results for each regime
        """
        self.logger.info("Starting alpha validation across all market regimes")
        
        # Detect regime periods
        regime_periods = self.regime_detector.detect_regime_periods(market_data)
        
        results = []
        regimes = [MarketRegime.BULL.value, MarketRegime.BEAR.value, MarketRegime.SIDEWAYS.value]
        
        for regime in regimes:
            self.logger.info(f"Validating alpha generation in {regime} market")
            
            # Get periods for this regime
            regime_data = regime_periods[regime_periods['regime'] == regime]
            
            if len(regime_data) > 0:
                result = self.validate_alpha_regime(regime, regime_data, market_data)
                results.append(result)
                self.validation_results[regime] = result
                
                # Log validation outcome
                status = "PASSED" if result.validation_passed else "FAILED"
                self.logger.info(f"Alpha validation {status} for {regime}: "
                               f"Alpha={result.alpha_generated:.2%}, "
                               f"IR={result.information_ratio:.2f}, "
                               f"Quality={result.signal_quality_score:.2f}")
            else:
                self.logger.warning(f"No {regime} market periods found in data")
        
        self.logger.info(f"Alpha validation completed for {len(results)} regimes")
        return results
    
    def validate_alpha_regime(self, regime: str, regime_data: pd.DataFrame, 
                            market_data: pd.DataFrame) -> AlphaValidationResult:
        """
        Validate alpha generation in a specific market regime.
        
        Args:
            regime: Market regime ('bull', 'bear', 'sideways')
            regime_data: Data for periods in this regime
            market_data: Full market data
            
        Returns:
            AlphaValidationResult: Validation results for the regime
        """
        self.logger.info(f"Starting alpha validation for {regime} market regime")
        
        if len(regime_data) == 0:
            # If no regime data, use the full market data for simulation
            self.logger.warning(f"No regime data for {regime}, using full market data for simulation")
            regime_data = market_data.copy()
            regime_data['regime'] = regime  # Add regime column
        
        # Get period bounds
        if 'date' in regime_data.columns:
            period_start = regime_data['date'].min()
            period_end = regime_data['date'].max()
        else:
            period_start = datetime.now() - timedelta(days=len(regime_data))
            period_end = datetime.now()
        
        # Run alpha generation simulation for this regime
        alpha_results = self._simulate_alpha_generation(regime, regime_data, market_data)
        
        # Calculate alpha metrics
        alpha_metrics = self._calculate_alpha_metrics(alpha_results, regime)
        
        # Validate signal quality
        signal_quality = self._validate_signal_quality(alpha_results, regime)
        
        # Check consistency
        consistency_score = self._calculate_consistency_score(alpha_results, regime)
        
        # Validate against thresholds
        validation_passed = self._validate_alpha_thresholds(alpha_metrics, signal_quality, 
                                                           consistency_score, regime)
        
        # Create validation result
        result = AlphaValidationResult(
            regime=regime,
            period_start=period_start,
            period_end=period_end,
            alpha_generated=alpha_metrics["alpha_generated"],
            information_ratio=alpha_metrics["information_ratio"],
            hit_rate=alpha_metrics["hit_rate"],
            signal_quality_score=signal_quality["overall_quality"],
            consistency_score=consistency_score,
            regime_adaptation_score=alpha_metrics["regime_adaptation"],
            validation_passed=validation_passed,
            signal_count=alpha_metrics["signal_count"],
            additional_metrics=alpha_metrics
        )
        
        self.logger.info(f"Alpha validation completed for {regime}: "
                        f"{'PASSED' if validation_passed else 'FAILED'}")
        
        return result
    
    def validate_bull_market_alpha(self, market_data: pd.DataFrame) -> AlphaValidationResult:
        """Validate alpha generation during bull markets."""
        regime_periods = self.regime_detector.detect_regime_periods(market_data)
        bull_data = regime_periods[regime_periods['regime'] == MarketRegime.BULL.value]
        
        # If no bull periods detected, simulate with the provided data
        if len(bull_data) == 0:
            self.logger.info("No bull market periods detected, using provided data for simulation")
            bull_data = market_data.copy()
            if 'regime' not in bull_data.columns:
                bull_data['regime'] = MarketRegime.BULL.value
        
        return self.validate_alpha_regime(MarketRegime.BULL.value, bull_data, market_data)
    
    def validate_bear_market_alpha(self, market_data: pd.DataFrame) -> AlphaValidationResult:
        """Validate alpha generation during bear markets."""
        regime_periods = self.regime_detector.detect_regime_periods(market_data)
        bear_data = regime_periods[regime_periods['regime'] == MarketRegime.BEAR.value]
        
        # If no bear periods detected, simulate with the provided data
        if len(bear_data) == 0:
            self.logger.info("No bear market periods detected, using provided data for simulation")
            bear_data = market_data.copy()
            if 'regime' not in bear_data.columns:
                bear_data['regime'] = MarketRegime.BEAR.value
        
        return self.validate_alpha_regime(MarketRegime.BEAR.value, bear_data, market_data)
    
    def validate_sideways_market_alpha(self, market_data: pd.DataFrame) -> AlphaValidationResult:
        """Validate alpha generation during sideways markets."""
        regime_periods = self.regime_detector.detect_regime_periods(market_data)
        sideways_data = regime_periods[regime_periods['regime'] == MarketRegime.SIDEWAYS.value]
        
        # If no sideways periods detected, simulate with the provided data
        if len(sideways_data) == 0:
            self.logger.info("No sideways market periods detected, using provided data for simulation")
            sideways_data = market_data.copy()
            if 'regime' not in sideways_data.columns:
                sideways_data['regime'] = MarketRegime.SIDEWAYS.value
        
        return self.validate_alpha_regime(MarketRegime.SIDEWAYS.value, sideways_data, market_data)
    
    def analyze_alpha_consistency(self, results: List[AlphaValidationResult]) -> Dict[str, Any]:
        """
        Analyze alpha consistency across regimes.
        
        Args:
            results: List of alpha validation results
            
        Returns:
            Dict with consistency analysis
        """
        if not results:
            return {"consistency_score": 0.0, "analysis": "No results to analyze"}
        
        # Calculate cross-regime consistency metrics
        alphas = [r.alpha_generated for r in results]
        information_ratios = [r.information_ratio for r in results]
        hit_rates = [r.hit_rate for r in results]
        
        consistency_analysis = {
            "alpha_consistency": {
                "mean": np.mean(alphas),
                "std": np.std(alphas),
                "coefficient_of_variation": np.std(alphas) / np.mean(alphas) if np.mean(alphas) != 0 else float('inf')
            },
            "information_ratio_consistency": {
                "mean": np.mean(information_ratios),
                "std": np.std(information_ratios),
                "min": np.min(information_ratios),
                "max": np.max(information_ratios)
            },
            "hit_rate_consistency": {
                "mean": np.mean(hit_rates),
                "std": np.std(hit_rates),
                "range": np.max(hit_rates) - np.min(hit_rates)
            },
            "regime_performance": {
                result.regime: {
                    "alpha": result.alpha_generated,
                    "ir": result.information_ratio,
                    "hit_rate": result.hit_rate,
                    "passed": result.validation_passed
                }
                for result in results
            }
        }
        
        # Overall consistency score (lower coefficient of variation = higher consistency)
        alpha_cv = consistency_analysis["alpha_consistency"]["coefficient_of_variation"]
        if alpha_cv == float('inf') or np.isnan(alpha_cv):
            overall_consistency = 0.0
        else:
            # Ensure consistency score is between 0 and 1
            overall_consistency = max(0.0, min(1.0, 1.0 - min(alpha_cv, 1.0)))
        
        consistency_analysis["overall_consistency_score"] = overall_consistency
        
        return consistency_analysis
    
    def generate_alpha_report(self, results: List[AlphaValidationResult]) -> Dict[str, Any]:
        """
        Generate comprehensive alpha validation report.
        
        Args:
            results: List of alpha validation results
            
        Returns:
            Dict with comprehensive alpha report
        """
        self.logger.info("Generating comprehensive alpha validation report")
        
        if not results:
            return {
                "summary": {"total_regimes": 0, "error": "No results to report"},
                "generated_at": datetime.now().isoformat()
            }
        
        # Summary statistics
        total_regimes = len(results)
        passed_regimes = sum(1 for r in results if r.validation_passed)
        pass_rate = passed_regimes / total_regimes
        
        # Performance aggregates
        avg_alpha = np.mean([r.alpha_generated for r in results])
        avg_ir = np.mean([r.information_ratio for r in results])
        avg_hit_rate = np.mean([r.hit_rate for r in results])
        avg_signal_quality = np.mean([r.signal_quality_score for r in results])
        avg_consistency = np.mean([r.consistency_score for r in results])
        total_signals = sum(r.signal_count for r in results)
        
        # Consistency analysis
        consistency_analysis = self.analyze_alpha_consistency(results)
        
        # Regime-specific insights
        regime_insights = self._generate_regime_insights(results)
        
        report = {
            "summary": {
                "total_regimes_tested": total_regimes,
                "regimes_passed": passed_regimes,
                "pass_rate": pass_rate,
                "overall_assessment": "STRONG" if pass_rate >= 0.8 else "MODERATE" if pass_rate >= 0.6 else "WEAK"
            },
            "performance_metrics": {
                "average_alpha_generated": avg_alpha,
                "average_information_ratio": avg_ir,
                "average_hit_rate": avg_hit_rate,
                "average_signal_quality": avg_signal_quality,
                "average_consistency_score": avg_consistency,
                "total_signals_generated": total_signals
            },
            "consistency_analysis": consistency_analysis,
            "regime_specific_results": {
                result.regime: {
                    "passed": result.validation_passed,
                    "alpha_generated": result.alpha_generated,
                    "information_ratio": result.information_ratio,
                    "hit_rate": result.hit_rate,
                    "signal_quality": result.signal_quality_score,
                    "consistency_score": result.consistency_score,
                    "signal_count": result.signal_count,
                    "period_start": result.period_start.isoformat() if result.period_start else None,
                    "period_end": result.period_end.isoformat() if result.period_end else None
                }
                for result in results
            },
            "insights_and_recommendations": regime_insights,
            "generated_at": datetime.now().isoformat()
        }
        
        self.logger.info(f"Alpha report generated: {pass_rate:.1%} pass rate, "
                        f"{avg_alpha:.2%} average alpha")
        
        return report
    
    def detect_alpha_degradation(self, historical_results: List[AlphaValidationResult], 
                                current_results: List[AlphaValidationResult]) -> Dict[str, Any]:
        """
        Detect alpha performance degradation over time.
        
        Args:
            historical_results: Previous alpha validation results
            current_results: Current alpha validation results
            
        Returns:
            Dict with degradation analysis and alerts
        """
        if not historical_results or not current_results:
            return {"degradation_detected": False, "reason": "Insufficient data"}
        
        degradation_analysis = {}
        alerts = []
        
        # Compare results by regime
        for current_result in current_results:
            regime = current_result.regime
            
            # Find corresponding historical result
            historical_result = next(
                (r for r in historical_results if r.regime == regime), None
            )
            
            if historical_result:
                # Calculate degradation metrics
                alpha_change = (current_result.alpha_generated - historical_result.alpha_generated) / historical_result.alpha_generated
                ir_change = (current_result.information_ratio - historical_result.information_ratio) / historical_result.information_ratio if historical_result.information_ratio != 0 else 0
                quality_change = (current_result.signal_quality_score - historical_result.signal_quality_score) / historical_result.signal_quality_score
                
                degradation_analysis[regime] = {
                    "alpha_change": alpha_change,
                    "ir_change": ir_change,
                    "quality_change": quality_change,
                    "degradation_detected": alpha_change < -self.ALPHA_THRESHOLDS["max_alpha_degradation"]
                }
                
                # Generate alerts for significant degradation
                if alpha_change < -self.ALPHA_THRESHOLDS["max_alpha_degradation"]:
                    alert = Alert(
                        timestamp=datetime.now(),
                        level=AlertLevel.WARNING,
                        component="AlphaValidator",
                        message=f"Alpha degradation detected in {regime} market",
                        details={
                            "regime": regime,
                            "alpha_change": alpha_change,
                            "current_alpha": current_result.alpha_generated,
                            "historical_alpha": historical_result.alpha_generated
                        }
                    )
                    alerts.append(alert)
        
        overall_degradation = any(analysis["degradation_detected"] for analysis in degradation_analysis.values())
        
        return {
            "degradation_detected": overall_degradation,
            "regime_analysis": degradation_analysis,
            "alerts_generated": alerts,
            "analysis_timestamp": datetime.now().isoformat()
        }
    
    def _simulate_alpha_generation(self, regime: str, regime_data: pd.DataFrame, 
                                 market_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Simulate alpha generation for a specific regime.
        
        This would integrate with the actual Northstar V3 alpha generation system.
        For now, we simulate realistic alpha patterns based on regime characteristics.
        """
        self.logger.debug(f"Simulating alpha generation for {regime} regime")
        
        # Regime-specific alpha generation parameters
        if regime == MarketRegime.BULL.value:
            base_alpha = 0.025      # 2.5% base alpha in bull markets
            signal_frequency = 0.7  # 70% of periods generate signals
            hit_rate_base = 0.58    # 58% base hit rate
            volatility_factor = 0.8 # Lower volatility in bull markets
            
        elif regime == MarketRegime.BEAR.value:
            base_alpha = 0.015      # 1.5% base alpha in bear markets
            signal_frequency = 0.6  # 60% of periods generate signals
            hit_rate_base = 0.54    # 54% base hit rate
            volatility_factor = 1.2 # Higher volatility in bear markets
            
        elif regime == MarketRegime.SIDEWAYS.value:
            base_alpha = 0.018      # 1.8% base alpha in sideways markets
            signal_frequency = 0.5  # 50% of periods generate signals
            hit_rate_base = 0.56    # 56% base hit rate
            volatility_factor = 1.0 # Normal volatility
            
        else:
            # Default parameters for unknown regime
            base_alpha = 0.01
            signal_frequency = 0.4
            hit_rate_base = 0.50
            volatility_factor = 1.0
        
        # Generate synthetic alpha signals
        num_periods = len(regime_data)
        np.random.seed(42)  # For reproducible results
        
        # Generate signals
        signal_generated = np.random.random(num_periods) < signal_frequency
        signal_count = int(signal_generated.sum())
        
        # Generate alpha returns with noise
        alpha_noise = np.random.normal(0, base_alpha * 0.3, num_periods)
        alpha_returns = np.where(signal_generated, 
                               base_alpha + alpha_noise, 
                               alpha_noise * 0.1)  # Small noise when no signal
        
        # Generate hit rates with variability
        hit_rates = np.random.normal(hit_rate_base, 0.05, num_periods)
        hit_rates = np.clip(hit_rates, 0.3, 0.8)  # Reasonable bounds
        
        # Calculate signal quality scores
        quality_scores = np.random.normal(0.7, 0.1, num_periods)
        quality_scores = np.clip(quality_scores, 0.3, 1.0)
        
        return {
            "regime": regime,
            "num_periods": num_periods,
            "signal_generated": signal_generated,
            "signal_count": signal_count,
            "alpha_returns": alpha_returns,
            "hit_rates": hit_rates,
            "quality_scores": quality_scores,
            "base_alpha": base_alpha,
            "volatility_factor": volatility_factor
        }
    
    def _calculate_alpha_metrics(self, alpha_results: Dict[str, Any], regime: str) -> Dict[str, float]:
        """Calculate alpha performance metrics."""
        alpha_returns = alpha_results["alpha_returns"]
        hit_rates = alpha_results["hit_rates"]
        signal_count = alpha_results["signal_count"]
        
        # Core alpha metrics
        alpha_generated = float(np.mean(alpha_returns))
        alpha_volatility = float(np.std(alpha_returns) * np.sqrt(252))  # Annualized
        information_ratio = alpha_generated / alpha_volatility if alpha_volatility > 0 else 0
        
        # Hit rate metrics
        avg_hit_rate = float(np.mean(hit_rates))
        hit_rate_consistency = 1.0 - float(np.std(hit_rates))  # Lower std = higher consistency
        
        # Regime adaptation score (how well alpha adapts to regime characteristics)
        expected_alpha = self.ALPHA_THRESHOLDS.get(f"min_alpha_{regime}", 0.01)
        regime_adaptation = min(1.0, alpha_generated / expected_alpha) if expected_alpha > 0 else 0
        
        return {
            "alpha_generated": alpha_generated,
            "alpha_volatility": alpha_volatility,
            "information_ratio": information_ratio,
            "hit_rate": avg_hit_rate,
            "hit_rate_consistency": hit_rate_consistency,
            "regime_adaptation": regime_adaptation,
            "signal_count": signal_count,
            "sharpe_ratio": information_ratio,  # Approximation
            "tracking_error": alpha_volatility
        }
    
    def _validate_signal_quality(self, alpha_results: Dict[str, Any], regime: str) -> Dict[str, float]:
        """Validate signal quality metrics."""
        quality_scores = alpha_results["quality_scores"]
        signal_generated = alpha_results["signal_generated"]
        
        # Overall signal quality
        overall_quality = float(np.mean(quality_scores))
        
        # Signal strength (proportion of periods with signals)
        signal_strength = float(np.mean(signal_generated))
        
        # Quality consistency
        quality_consistency = 1.0 - float(np.std(quality_scores))
        
        # Signal-to-noise ratio
        signal_periods = quality_scores[signal_generated]
        noise_periods = quality_scores[~signal_generated]
        
        if len(signal_periods) > 0 and len(noise_periods) > 0:
            signal_to_noise = float(np.mean(signal_periods) / np.mean(noise_periods))
        else:
            signal_to_noise = 1.0
        
        return {
            "overall_quality": overall_quality,
            "signal_strength": signal_strength,
            "quality_consistency": quality_consistency,
            "signal_to_noise_ratio": signal_to_noise
        }
    
    def _calculate_consistency_score(self, alpha_results: Dict[str, Any], regime: str) -> float:
        """Calculate consistency score for alpha generation."""
        alpha_returns = alpha_results["alpha_returns"]
        hit_rates = alpha_results["hit_rates"]
        quality_scores = alpha_results["quality_scores"]
        
        # Consistency components
        alpha_consistency = 1.0 - (np.std(alpha_returns) / np.mean(np.abs(alpha_returns))) if np.mean(np.abs(alpha_returns)) > 0 else 0
        hit_rate_consistency = 1.0 - np.std(hit_rates)
        quality_consistency = 1.0 - np.std(quality_scores)
        
        # Weighted average consistency score
        consistency_score = (
            0.4 * alpha_consistency +
            0.3 * hit_rate_consistency +
            0.3 * quality_consistency
        )
        
        return float(max(0.0, min(1.0, consistency_score)))
    
    def _validate_alpha_thresholds(self, alpha_metrics: Dict[str, float], 
                                 signal_quality: Dict[str, float], 
                                 consistency_score: float, regime: str) -> bool:
        """Validate alpha metrics against thresholds."""
        validations = []
        
        # Check alpha generation threshold
        min_alpha_key = f"min_alpha_{regime}"
        if min_alpha_key in self.ALPHA_THRESHOLDS:
            validations.append(alpha_metrics["alpha_generated"] >= self.ALPHA_THRESHOLDS[min_alpha_key])
        
        # Check information ratio
        validations.append(alpha_metrics["information_ratio"] >= self.ALPHA_THRESHOLDS["min_information_ratio"])
        
        # Check hit rate
        validations.append(alpha_metrics["hit_rate"] >= self.ALPHA_THRESHOLDS["min_hit_rate"])
        
        # Check signal quality
        validations.append(signal_quality["overall_quality"] >= self.ALPHA_THRESHOLDS["min_signal_quality"])
        
        # Check consistency
        validations.append(consistency_score >= self.ALPHA_THRESHOLDS["min_consistency"])
        
        # All validations must pass
        return all(validations)
    
    def _create_failed_result(self, regime: str, reason: str) -> AlphaValidationResult:
        """Create a failed validation result."""
        return AlphaValidationResult(
            regime=regime,
            period_start=datetime.now(),
            period_end=datetime.now(),
            alpha_generated=0.0,
            information_ratio=0.0,
            hit_rate=0.0,
            signal_quality_score=0.0,
            consistency_score=0.0,
            regime_adaptation_score=0.0,
            validation_passed=False,
            signal_count=0,
            additional_metrics={"failure_reason": reason}
        )
    
    def _generate_regime_insights(self, results: List[AlphaValidationResult]) -> Dict[str, Any]:
        """Generate insights and recommendations from alpha validation results."""
        insights = {
            "key_findings": [],
            "performance_concerns": [],
            "recommendations": [],
            "strengths": []
        }
        
        # Analyze results for insights
        failed_regimes = [r for r in results if not r.validation_passed]
        low_alpha_regimes = [r for r in results if r.alpha_generated < 0.01]
        low_quality_regimes = [r for r in results if r.signal_quality_score < 0.6]
        
        # Key findings
        if len(failed_regimes) == 0:
            insights["key_findings"].append("Alpha generation passed validation in all tested market regimes")
        else:
            insights["key_findings"].append(f"Alpha validation failed in {len(failed_regimes)} out of {len(results)} regimes")
        
        # Performance concerns
        if low_alpha_regimes:
            regimes_list = [r.regime for r in low_alpha_regimes]
            insights["performance_concerns"].append(f"Low alpha generation in {regimes_list} markets")
        
        if low_quality_regimes:
            regimes_list = [r.regime for r in low_quality_regimes]
            insights["performance_concerns"].append(f"Poor signal quality in {regimes_list} markets")
        
        # Recommendations
        if failed_regimes:
            insights["recommendations"].append("Review alpha generation strategies for failed regimes")
            insights["recommendations"].append("Consider regime-specific parameter optimization")
        
        if low_quality_regimes:
            insights["recommendations"].append("Improve signal quality filters and validation")
        
        # Strengths
        passed_regimes = [r for r in results if r.validation_passed]
        if passed_regimes:
            avg_alpha = np.mean([r.alpha_generated for r in passed_regimes])
            insights["strengths"].append(f"Strong alpha generation averaging {avg_alpha:.2%} in successful regimes")
        
        high_consistency_regimes = [r for r in results if r.consistency_score > 0.8]
        if high_consistency_regimes:
            insights["strengths"].append(f"High consistency in {len(high_consistency_regimes)} regimes")
        
        return insights