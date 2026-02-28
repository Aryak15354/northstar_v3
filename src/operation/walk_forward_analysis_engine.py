"""
Walk-Forward Analysis Engine - Comprehensive walk-forward validation system.

This module provides rolling window analysis, out-of-sample validation, strategy
degradation detection, and strategy evolution recommendations for robust
strategy validation over time.
"""

import logging
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import json
from dataclasses import dataclass, field

from .base_types import (
    OperationResult, OperationStatus, OperationConfig,
    Alert, AlertLevel, HealthStatus, SystemHealthStatus,
    WalkForwardConfig, WalkForwardResult, StrategyEvolutionResult
)
from .logging_config import setup_operation_logging
from .report_manager import ReportManager


@dataclass
class WalkForwardWindow:
    """Definition of a walk-forward analysis window."""
    window_id: str
    training_start: datetime
    training_end: datetime
    testing_start: datetime
    testing_end: datetime
    training_observations: int
    testing_observations: int
    optimization_parameters: Dict[str, Any] = field(default_factory=dict)
    performance_metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class StrategyDegradation:
    """Strategy degradation analysis result."""
    strategy_name: str
    degradation_detected: bool
    degradation_severity: str  # "low", "medium", "high", "critical"
    degradation_start_date: Optional[datetime] = None
    performance_decline_pct: float = 0.0
    statistical_significance: float = 0.0
    recommended_actions: List[str] = field(default_factory=list)
    degradation_metrics: Dict[str, float] = field(default_factory=dict)


class WalkForwardAnalysisEngine:
    """
    Comprehensive walk-forward analysis engine for strategy validation.
    
    Provides rolling window analysis, out-of-sample validation, strategy
    degradation detection, and strategy evolution recommendations.
    """
    
    def __init__(self, config: Optional[WalkForwardConfig] = None):
        """Initialize the walk-forward analysis engine."""
        self.config = config or WalkForwardConfig()
        self.logger = setup_operation_logging()
        
        from .base_types import ReportConfig
        report_config = getattr(self.config, 'reporting_config', None) or ReportConfig()
        self.report_manager = ReportManager(report_config)
        
        # Analysis state
        self.analysis_history: List[WalkForwardResult] = []
        self.strategy_evolution_history: List[StrategyEvolutionResult] = []
        self.degradation_alerts: List[Alert] = []
        
        # Window management
        self.analysis_windows: List[WalkForwardWindow] = []
        self.current_window_index = 0
        
        # Strategy tracking
        self.strategy_performance_history: Dict[str, List[Dict[str, Any]]] = {}
        self.strategy_parameters_history: Dict[str, List[Dict[str, Any]]] = {}
        
        # Degradation detection
        self.degradation_detectors = {
            "performance_decline": self._detect_performance_decline,
            "sharpe_degradation": self._detect_sharpe_degradation,
            "drawdown_increase": self._detect_drawdown_increase,
            "volatility_increase": self._detect_volatility_increase,
            "consistency_decline": self._detect_consistency_decline
        }
        
        # Evolution analyzers
        self.evolution_analyzers = {
            "parameter_drift": self._analyze_parameter_drift,
            "performance_trends": self._analyze_performance_trends,
            "regime_adaptation": self._analyze_regime_adaptation,
            "risk_profile_changes": self._analyze_risk_profile_changes
        }
        
        self.logger.info("Walk-Forward Analysis Engine initialized")
        self.logger.info(f"Configuration: {self.config.training_window} month training, "
                        f"{self.config.testing_window} month testing, "
                        f"{self.config.step_size} month steps")
    
    def run_comprehensive_walk_forward_analysis(self, 
                                               start_date: datetime,
                                               end_date: datetime,
                                               strategies: List[str]) -> List[WalkForwardResult]:
        """
        Run comprehensive walk-forward analysis across multiple strategies.
        
        Args:
            start_date: Analysis start date
            end_date: Analysis end date
            strategies: List of strategy names to analyze
            
        Returns:
            List[WalkForwardResult]: Results for each walk-forward window
        """
        analysis_start = datetime.now()
        self.logger.info(f"Starting comprehensive walk-forward analysis from {start_date} to {end_date}")
        self.logger.info(f"Analyzing {len(strategies)} strategies: {strategies}")
        
        try:
            # Generate analysis windows
            windows = self._generate_analysis_windows(start_date, end_date)
            self.analysis_windows = windows
            
            self.logger.info(f"Generated {len(windows)} analysis windows")
            
            results = []
            
            for i, window in enumerate(windows):
                self.current_window_index = i
                self.logger.info(f"Processing window {i+1}/{len(windows)}: {window.window_id}")
                
                # Run walk-forward analysis for this window
                window_result = self._run_window_analysis(window, strategies)
                results.append(window_result)
                
                # Update strategy performance history
                self._update_strategy_history(window_result)
                
                # Check for strategy degradation
                degradation_results = []
                for strategy in strategies:
                    degradation_result = self.detect_strategy_degradation(strategy)
                    degradation_results.append(degradation_result)
                window_result.degradation_analysis = degradation_results
                
                # Generate evolution insights if we have enough history
                if i >= 2:  # Need at least 3 windows for evolution analysis
                    evolution_results = self._analyze_strategy_evolution(strategies, results[-3:])
                    window_result.evolution_insights = evolution_results
            
            # Store results
            self.analysis_history.extend(results)
            
            # Generate comprehensive report
            report_path = self._generate_walk_forward_report(results)
            
            self.logger.info(f"Walk-forward analysis completed. Report: {report_path}")
            return results
            
        except Exception as e:
            self.logger.error(f"Walk-forward analysis failed: {str(e)}")
            
            # Generate critical alert
            alert = Alert(
                timestamp=datetime.now(),
                level=AlertLevel.CRITICAL,
                component="WalkForwardAnalysisEngine",
                message=f"Walk-forward analysis failed: {str(e)}",
                details={"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "error": str(e)}
            )
            self.degradation_alerts.append(alert)
            
            raise
    
    def detect_strategy_degradation(self, strategy_name: str, 
                                  lookback_windows: int = 5) -> StrategyDegradation:
        """
        Detect strategy degradation using multiple detection methods.
        
        Args:
            strategy_name: Name of strategy to analyze
            lookback_windows: Number of recent windows to analyze
            
        Returns:
            StrategyDegradation: Degradation analysis result
        """
        self.logger.info(f"Detecting degradation for strategy: {strategy_name}")
        
        if strategy_name not in self.strategy_performance_history:
            return StrategyDegradation(
                strategy_name=strategy_name,
                degradation_detected=False,
                degradation_severity="unknown",
                recommended_actions=["Insufficient data for degradation analysis"]
            )
        
        # Get recent performance history
        performance_history = self.strategy_performance_history[strategy_name]
        
        if len(performance_history) < lookback_windows:
            recent_history = performance_history
        else:
            # Use all history for comparison, not just recent windows
            recent_history = performance_history
        
        if len(recent_history) < 3:
            return StrategyDegradation(
                strategy_name=strategy_name,
                degradation_detected=False,
                degradation_severity="insufficient_data",
                recommended_actions=["Need more historical data for degradation analysis"]
            )
        
        # Run all degradation detectors
        degradation_signals = {}
        for detector_name, detector_func in self.degradation_detectors.items():
            try:
                signal = detector_func(recent_history)
                degradation_signals[detector_name] = signal
            except Exception as e:
                self.logger.warning(f"Degradation detector {detector_name} failed: {str(e)}")
                degradation_signals[detector_name] = {"detected": False, "confidence": 0.0}
        
        # Aggregate degradation signals
        degradation_result = self._aggregate_degradation_signals(strategy_name, degradation_signals, recent_history)
        
        # Generate alert if degradation detected
        if degradation_result.degradation_detected:
            alert = Alert(
                timestamp=datetime.now(),
                level=AlertLevel.WARNING if degradation_result.degradation_severity in ["low", "medium"] else AlertLevel.CRITICAL,
                component="WalkForwardAnalysisEngine",
                message=f"Strategy degradation detected: {strategy_name} ({degradation_result.degradation_severity})",
                details={
                    "strategy": strategy_name,
                    "severity": degradation_result.degradation_severity,
                    "decline_pct": degradation_result.performance_decline_pct,
                    "significance": degradation_result.statistical_significance
                }
            )
            self.degradation_alerts.append(alert)
        
        return degradation_result
    
    def generate_strategy_evolution_insights(self, strategy_name: str,
                                           lookback_windows: int = 10) -> StrategyEvolutionResult:
        """
        Generate strategy evolution insights and recommendations.
        
        Args:
            strategy_name: Name of strategy to analyze
            lookback_windows: Number of recent windows to analyze
            
        Returns:
            StrategyEvolutionResult: Evolution analysis and recommendations
        """
        self.logger.info(f"Generating evolution insights for strategy: {strategy_name}")
        
        if strategy_name not in self.strategy_performance_history:
            return StrategyEvolutionResult(
                strategy_name=strategy_name,
                analysis_period_start=datetime.now(),
                analysis_period_end=datetime.now(),
                evolution_detected=False,
                recommendations=["Insufficient data for evolution analysis"]
            )
        
        # Get recent history
        performance_history = self.strategy_performance_history[strategy_name]
        parameter_history = self.strategy_parameters_history.get(strategy_name, [])
        
        recent_performance = performance_history[-lookback_windows:] if len(performance_history) >= lookback_windows else performance_history
        recent_parameters = parameter_history[-lookback_windows:] if len(parameter_history) >= lookback_windows else parameter_history
        
        if len(recent_performance) < 5:
            return StrategyEvolutionResult(
                strategy_name=strategy_name,
                analysis_period_start=datetime.now(),
                analysis_period_end=datetime.now(),
                evolution_detected=False,
                recommendations=["Need more historical data for evolution analysis"]
            )
        
        # Run evolution analyzers
        evolution_insights = {}
        for analyzer_name, analyzer_func in self.evolution_analyzers.items():
            try:
                insights = analyzer_func(recent_performance, recent_parameters)
                evolution_insights[analyzer_name] = insights
            except Exception as e:
                self.logger.warning(f"Evolution analyzer {analyzer_name} failed: {str(e)}")
                evolution_insights[analyzer_name] = {"detected": False, "insights": []}
        
        # Generate comprehensive evolution result
        evolution_result = self._compile_evolution_result(strategy_name, evolution_insights, recent_performance)
        
        # Store evolution result
        self.strategy_evolution_history.append(evolution_result)
        
        return evolution_result
    
    def get_walk_forward_metrics(self) -> Dict[str, Any]:
        """Get comprehensive walk-forward analysis metrics."""
        current_time = datetime.now()
        
        # Calculate analysis statistics
        total_analyses = len(self.analysis_history)
        total_windows = len(self.analysis_history)  # Each analysis result represents one window
        
        # Calculate strategy statistics
        strategy_stats = {}
        for result in self.analysis_history:
            for strategy_result in result.strategy_results:
                strategy = strategy_result["strategy_name"]
                if strategy not in strategy_stats:
                    strategy_stats[strategy] = {"windows": 0, "avg_performance": 0.0, "degradation_count": 0}
                
                strategy_stats[strategy]["windows"] += 1
                strategy_stats[strategy]["avg_performance"] += strategy_result.get("out_of_sample_return", 0.0)
                
                if strategy_result.get("degradation_detected", False):
                    strategy_stats[strategy]["degradation_count"] += 1
        
        # Calculate average performance
        for strategy, stats in strategy_stats.items():
            if stats["windows"] > 0:
                stats["avg_performance"] /= stats["windows"]
                stats["degradation_rate"] = stats["degradation_count"] / stats["windows"]
        
        # Calculate degradation statistics
        degradation_stats = {
            "total_degradations": len([alert for alert in self.degradation_alerts if "degradation" in alert.message.lower()]),
            "critical_degradations": len([alert for alert in self.degradation_alerts if alert.level == AlertLevel.CRITICAL]),
            "strategies_with_degradation": len([s for s, stats in strategy_stats.items() if stats.get("degradation_count", 0) > 0])
        }
        
        return {
            "analysis_statistics": {
                "total_analyses": total_analyses,
                "total_windows": total_windows,
                "avg_windows_per_analysis": total_windows / total_analyses if total_analyses > 0 else 0.0,
                "analysis_success_rate": 1.0  # Mock - would calculate from actual results
            },
            "strategy_statistics": strategy_stats,
            "degradation_statistics": degradation_stats,
            "evolution_statistics": {
                "total_evolution_analyses": len(self.strategy_evolution_history),
                "strategies_with_evolution": len(set(result.strategy_name for result in self.strategy_evolution_history))
            },
            "window_configuration": {
                "training_window_months": self.config.training_window,
                "testing_window_months": self.config.testing_window,
                "step_size_months": self.config.step_size,
                "minimum_observations": self.config.minimum_observations
            },
            "alerts_generated": len(self.degradation_alerts),
            "metrics_timestamp": current_time.isoformat()
        }
    
    # Private helper methods
    
    def _generate_analysis_windows(self, start_date: datetime, end_date: datetime) -> List[WalkForwardWindow]:
        """Generate walk-forward analysis windows."""
        windows = []
        current_date = start_date
        window_id = 1
        
        while current_date < end_date:
            # Calculate training period
            training_start = current_date
            training_end = training_start + timedelta(days=self.config.training_window * 30)
            
            # Calculate testing period
            testing_start = training_end
            testing_end = testing_start + timedelta(days=self.config.testing_window * 30)
            
            # Check if we have enough data for this window
            if testing_end > end_date:
                break
            
            # Create window
            window = WalkForwardWindow(
                window_id=f"WF_{window_id:03d}",
                training_start=training_start,
                training_end=training_end,
                testing_start=testing_start,
                testing_end=testing_end,
                training_observations=self.config.training_window * 22,  # Approximate trading days
                testing_observations=self.config.testing_window * 22
            )
            
            windows.append(window)
            
            # Move to next window
            current_date += timedelta(days=self.config.step_size * 30)
            window_id += 1
        
        return windows
    
    def _run_window_analysis(self, window: WalkForwardWindow, strategies: List[str]) -> WalkForwardResult:
        """Run walk-forward analysis for a single window."""
        window_start = datetime.now()
        
        # Mock strategy analysis for each strategy
        strategy_results = []
        
        for strategy in strategies:
            # Mock training phase
            training_result = self._run_training_phase(window, strategy)
            
            # Mock testing phase
            testing_result = self._run_testing_phase(window, strategy, training_result)
            
            # Combine results
            strategy_result = {
                "strategy_name": strategy,
                "window_id": window.window_id,
                "training_performance": training_result,
                "testing_performance": testing_result,
                "out_of_sample_return": testing_result.get("total_return", 0.0),
                "out_of_sample_sharpe": testing_result.get("sharpe_ratio", 0.0),
                "parameter_stability": self._calculate_parameter_stability(strategy, training_result),
                "degradation_detected": False  # Will be updated later
            }
            
            strategy_results.append(strategy_result)
        
        # Create walk-forward result
        result = WalkForwardResult(
            analysis_id=f"WF_Analysis_{int(time.time())}",
            window_id=window.window_id,
            training_start=window.training_start,
            training_end=window.training_end,
            testing_start=window.testing_start,
            testing_end=window.testing_end,
            strategies_analyzed=strategies,
            strategy_results=strategy_results,
            analysis_duration_seconds=(datetime.now() - window_start).total_seconds()
        )
        
        return result
    
    def _run_training_phase(self, window: WalkForwardWindow, strategy: str) -> Dict[str, Any]:
        """Run training phase for a strategy in a window."""
        # Mock training phase - would integrate with actual strategy optimization
        
        # Simulate parameter optimization
        optimized_parameters = {
            "lookback_period": np.random.randint(10, 50),
            "signal_threshold": np.random.uniform(0.1, 0.5),
            "position_size": np.random.uniform(0.02, 0.08),
            "stop_loss": np.random.uniform(0.05, 0.15)
        }
        
        # Simulate training performance
        training_performance = {
            "total_return": np.random.uniform(0.05, 0.25),
            "volatility": np.random.uniform(0.10, 0.30),
            "sharpe_ratio": np.random.uniform(0.5, 2.0),
            "max_drawdown": np.random.uniform(0.05, 0.20),
            "win_rate": np.random.uniform(0.45, 0.65),
            "optimized_parameters": optimized_parameters,
            "training_observations": window.training_observations
        }
        
        return training_performance
    
    def _run_testing_phase(self, window: WalkForwardWindow, strategy: str, training_result: Dict[str, Any]) -> Dict[str, Any]:
        """Run testing phase for a strategy in a window."""
        # Mock testing phase - would use optimized parameters from training
        
        # Simulate some degradation from training to testing
        degradation_factor = np.random.uniform(0.7, 1.1)  # Can be better or worse
        
        testing_performance = {
            "total_return": training_result["total_return"] * degradation_factor,
            "volatility": training_result["volatility"] * np.random.uniform(0.9, 1.2),
            "sharpe_ratio": training_result["sharpe_ratio"] * degradation_factor * np.random.uniform(0.8, 1.1),
            "max_drawdown": training_result["max_drawdown"] * np.random.uniform(0.8, 1.3),
            "win_rate": training_result["win_rate"] * np.random.uniform(0.85, 1.05),
            "testing_observations": window.testing_observations,
            "parameters_used": training_result["optimized_parameters"]
        }
        
        return testing_performance
    
    def _calculate_parameter_stability(self, strategy: str, training_result: Dict[str, Any]) -> float:
        """Calculate parameter stability score."""
        # Mock parameter stability calculation
        if strategy not in self.strategy_parameters_history:
            return 1.0  # First time, assume stable
        
        # Compare with previous parameters
        previous_params = self.strategy_parameters_history[strategy][-1] if self.strategy_parameters_history[strategy] else {}
        current_params = training_result.get("optimized_parameters", {})
        
        if not previous_params:
            return 1.0
        
        # Calculate parameter changes
        stability_scores = []
        for param, value in current_params.items():
            if param in previous_params:
                prev_value = previous_params[param]
                if prev_value != 0:
                    change_pct = abs(value - prev_value) / abs(prev_value)
                    stability_score = max(0.0, 1.0 - change_pct)
                    stability_scores.append(stability_score)
        
        return np.mean(stability_scores) if stability_scores else 1.0
    
    def _update_strategy_history(self, result: WalkForwardResult):
        """Update strategy performance and parameter history."""
        for strategy_result in result.strategy_results:
            strategy = strategy_result["strategy_name"]
            
            # Update performance history
            if strategy not in self.strategy_performance_history:
                self.strategy_performance_history[strategy] = []
            
            performance_entry = {
                "window_id": result.window_id,
                "timestamp": result.testing_end,
                "out_of_sample_return": strategy_result["out_of_sample_return"],
                "out_of_sample_sharpe": strategy_result["out_of_sample_sharpe"],
                "testing_performance": strategy_result["testing_performance"]
            }
            self.strategy_performance_history[strategy].append(performance_entry)
            
            # Update parameter history
            if strategy not in self.strategy_parameters_history:
                self.strategy_parameters_history[strategy] = []
            
            if "training_performance" in strategy_result and "optimized_parameters" in strategy_result["training_performance"]:
                parameter_entry = {
                    "window_id": result.window_id,
                    "timestamp": result.training_end,
                    "parameters": strategy_result["training_performance"]["optimized_parameters"]
                }
                self.strategy_parameters_history[strategy].append(parameter_entry)
    
    # Degradation detection methods
    
    def _detect_performance_decline(self, performance_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect overall performance decline."""
        returns = [entry["out_of_sample_return"] for entry in performance_history]
        
        if len(returns) < 3:
            return {"detected": False, "confidence": 0.0}
        
        # Simple trend analysis
        recent_avg = np.mean(returns[-3:])
        earlier_avg = np.mean(returns[:-3]) if len(returns) > 3 else np.mean(returns)
        
        decline_pct = (earlier_avg - recent_avg) / abs(earlier_avg) if earlier_avg != 0 else 0.0
        
        detected = decline_pct > 0.2  # 20% decline threshold
        confidence = min(1.0, decline_pct * 2) if detected else 0.0
        
        return {
            "detected": detected,
            "confidence": confidence,
            "decline_pct": decline_pct,
            "recent_avg": recent_avg,
            "earlier_avg": earlier_avg
        }
    
    def _detect_sharpe_degradation(self, performance_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect Sharpe ratio degradation."""
        sharpe_ratios = [entry["out_of_sample_sharpe"] for entry in performance_history]
        
        if len(sharpe_ratios) < 3:
            return {"detected": False, "confidence": 0.0}
        
        recent_sharpe = np.mean(sharpe_ratios[-3:])
        earlier_sharpe = np.mean(sharpe_ratios[:-3]) if len(sharpe_ratios) > 3 else np.mean(sharpe_ratios)
        
        degradation = (earlier_sharpe - recent_sharpe) / abs(earlier_sharpe) if earlier_sharpe != 0 else 0.0
        
        detected = degradation > 0.3  # 30% Sharpe degradation threshold
        confidence = min(1.0, degradation * 1.5) if detected else 0.0
        
        return {
            "detected": detected,
            "confidence": confidence,
            "degradation_pct": degradation,
            "recent_sharpe": recent_sharpe,
            "earlier_sharpe": earlier_sharpe
        }
    
    def _detect_drawdown_increase(self, performance_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect increasing drawdowns."""
        drawdowns = [entry["testing_performance"]["max_drawdown"] for entry in performance_history if "testing_performance" in entry]
        
        if len(drawdowns) < 3:
            return {"detected": False, "confidence": 0.0}
        
        recent_drawdown = np.mean(drawdowns[-3:])
        earlier_drawdown = np.mean(drawdowns[:-3]) if len(drawdowns) > 3 else np.mean(drawdowns)
        
        increase_pct = (recent_drawdown - earlier_drawdown) / abs(earlier_drawdown) if earlier_drawdown != 0 else 0.0
        
        detected = increase_pct > 0.5  # 50% drawdown increase threshold
        confidence = min(1.0, increase_pct) if detected else 0.0
        
        return {
            "detected": detected,
            "confidence": confidence,
            "increase_pct": increase_pct,
            "recent_drawdown": recent_drawdown,
            "earlier_drawdown": earlier_drawdown
        }
    
    def _detect_volatility_increase(self, performance_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect increasing volatility."""
        volatilities = [entry["testing_performance"]["volatility"] for entry in performance_history if "testing_performance" in entry]
        
        if len(volatilities) < 3:
            return {"detected": False, "confidence": 0.0}
        
        recent_vol = np.mean(volatilities[-3:])
        earlier_vol = np.mean(volatilities[:-3]) if len(volatilities) > 3 else np.mean(volatilities)
        
        increase_pct = (recent_vol - earlier_vol) / abs(earlier_vol) if earlier_vol != 0 else 0.0
        
        detected = increase_pct > 0.4  # 40% volatility increase threshold
        confidence = min(1.0, increase_pct * 1.25) if detected else 0.0
        
        return {
            "detected": detected,
            "confidence": confidence,
            "increase_pct": increase_pct,
            "recent_volatility": recent_vol,
            "earlier_volatility": earlier_vol
        }
    
    def _detect_consistency_decline(self, performance_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect declining consistency."""
        returns = [entry["out_of_sample_return"] for entry in performance_history]
        
        if len(returns) < 5:
            return {"detected": False, "confidence": 0.0}
        
        # Calculate consistency as inverse of return volatility
        recent_consistency = 1.0 / (np.std(returns[-3:]) + 1e-6)
        earlier_consistency = 1.0 / (np.std(returns[:-3]) + 1e-6) if len(returns) > 3 else recent_consistency
        
        decline_pct = (earlier_consistency - recent_consistency) / abs(earlier_consistency) if earlier_consistency != 0 else 0.0
        
        detected = decline_pct > 0.3  # 30% consistency decline threshold
        confidence = min(1.0, decline_pct * 1.5) if detected else 0.0
        
        return {
            "detected": detected,
            "confidence": confidence,
            "decline_pct": decline_pct,
            "recent_consistency": recent_consistency,
            "earlier_consistency": earlier_consistency
        }
    
    def _aggregate_degradation_signals(self, strategy_name: str, 
                                     degradation_signals: Dict[str, Dict[str, Any]],
                                     performance_history: List[Dict[str, Any]]) -> StrategyDegradation:
        """Aggregate degradation signals into final result."""
        # Count detected degradations
        detected_signals = [signal for signal in degradation_signals.values() if signal.get("detected", False)]
        
        if not detected_signals:
            return StrategyDegradation(
                strategy_name=strategy_name,
                degradation_detected=False,
                degradation_severity="none"
            )
        
        # Calculate overall confidence
        overall_confidence = np.mean([signal.get("confidence", 0.0) for signal in detected_signals])
        
        # Determine severity
        if overall_confidence >= 0.8:
            severity = "critical"
        elif overall_confidence >= 0.6:
            severity = "high"
        elif overall_confidence >= 0.4:
            severity = "medium"
        else:
            severity = "low"
        
        # Calculate performance decline
        performance_signal = degradation_signals.get("performance_decline", {})
        performance_decline_pct = performance_signal.get("decline_pct", 0.0) * 100
        
        # Generate recommendations
        recommendations = self._generate_degradation_recommendations(degradation_signals, severity)
        
        # Estimate degradation start date
        degradation_start = performance_history[-len(detected_signals)]["timestamp"] if len(detected_signals) <= len(performance_history) else performance_history[0]["timestamp"]
        
        return StrategyDegradation(
            strategy_name=strategy_name,
            degradation_detected=True,
            degradation_severity=severity,
            degradation_start_date=degradation_start,
            performance_decline_pct=performance_decline_pct,
            statistical_significance=overall_confidence,
            recommended_actions=recommendations,
            degradation_metrics={
                "detected_signals": len(detected_signals),
                "overall_confidence": overall_confidence,
                "signal_details": degradation_signals
            }
        )
    
    def _generate_degradation_recommendations(self, degradation_signals: Dict[str, Dict[str, Any]], 
                                            severity: str) -> List[str]:
        """Generate recommendations based on degradation signals."""
        recommendations = []
        
        # General recommendations based on severity
        if severity == "critical":
            recommendations.append("URGENT: Consider suspending strategy immediately")
            recommendations.append("Conduct comprehensive strategy review")
        elif severity == "high":
            recommendations.append("Reduce position sizes by 50%")
            recommendations.append("Implement enhanced monitoring")
        elif severity == "medium":
            recommendations.append("Increase monitoring frequency")
            recommendations.append("Consider parameter reoptimization")
        else:
            recommendations.append("Monitor closely for further degradation")
        
        # Specific recommendations based on signals
        if degradation_signals.get("performance_decline", {}).get("detected", False):
            recommendations.append("Analyze market regime changes affecting performance")
        
        if degradation_signals.get("sharpe_degradation", {}).get("detected", False):
            recommendations.append("Review risk management parameters")
        
        if degradation_signals.get("drawdown_increase", {}).get("detected", False):
            recommendations.append("Implement stricter stop-loss controls")
        
        if degradation_signals.get("volatility_increase", {}).get("detected", False):
            recommendations.append("Reduce position sizing to manage volatility")
        
        if degradation_signals.get("consistency_decline", {}).get("detected", False):
            recommendations.append("Investigate signal quality degradation")
        
        return recommendations
    
    # Evolution analysis methods
    
    def _analyze_strategy_evolution(self, strategies: List[str], 
                                  recent_results: List[WalkForwardResult]) -> Dict[str, Any]:
        """Analyze strategy evolution across recent windows."""
        evolution_insights = {}
        
        for strategy in strategies:
            # Extract strategy data across windows
            strategy_data = []
            for result in recent_results:
                strategy_result = next((sr for sr in result.strategy_results if sr["strategy_name"] == strategy), None)
                if strategy_result:
                    strategy_data.append(strategy_result)
            
            if len(strategy_data) >= 2:
                insights = self._analyze_single_strategy_evolution(strategy, strategy_data)
                evolution_insights[strategy] = insights
        
        return evolution_insights
    
    def _analyze_single_strategy_evolution(self, strategy: str, strategy_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze evolution for a single strategy."""
        # Analyze parameter drift
        parameter_drift = self._analyze_parameter_drift_for_strategy(strategy_data)
        
        # Analyze performance trends
        performance_trends = self._analyze_performance_trends_for_strategy(strategy_data)
        
        # Analyze risk profile changes
        risk_changes = self._analyze_risk_changes_for_strategy(strategy_data)
        
        return {
            "parameter_drift": parameter_drift,
            "performance_trends": performance_trends,
            "risk_profile_changes": risk_changes,
            "evolution_detected": any([parameter_drift.get("significant_drift", False),
                                     performance_trends.get("significant_trend", False),
                                     risk_changes.get("significant_changes", False)])
        }
    
    def _analyze_parameter_drift(self, performance_history: List[Dict[str, Any]], 
                               parameter_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze parameter drift over time."""
        if len(parameter_history) < 3:
            return {"detected": False, "insights": ["Insufficient parameter history"]}
        
        # Mock parameter drift analysis
        drift_detected = np.random.random() > 0.7  # 30% chance of drift
        
        return {
            "detected": drift_detected,
            "insights": ["Parameter drift detected in lookback_period", "Signal threshold showing instability"] if drift_detected else ["Parameters stable"],
            "drift_magnitude": np.random.uniform(0.1, 0.5) if drift_detected else 0.0
        }
    
    def _analyze_performance_trends(self, performance_history: List[Dict[str, Any]], 
                                  parameter_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze performance trends over time."""
        if len(performance_history) < 3:
            return {"detected": False, "insights": ["Insufficient performance history"]}
        
        returns = [entry["out_of_sample_return"] for entry in performance_history]
        
        # Simple trend analysis
        trend_slope = np.polyfit(range(len(returns)), returns, 1)[0]
        trend_detected = abs(trend_slope) > 0.01  # 1% trend threshold
        
        trend_direction = "improving" if trend_slope > 0 else "declining"
        
        return {
            "detected": trend_detected,
            "insights": [f"Performance trend {trend_direction}", f"Trend slope: {trend_slope:.4f}"] if trend_detected else ["No significant trend"],
            "trend_slope": trend_slope,
            "trend_direction": trend_direction
        }
    
    def _analyze_regime_adaptation(self, performance_history: List[Dict[str, Any]], 
                                 parameter_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze regime adaptation capabilities."""
        # Mock regime adaptation analysis
        adaptation_detected = np.random.random() > 0.6  # 40% chance
        
        return {
            "detected": adaptation_detected,
            "insights": ["Strategy adapting well to regime changes", "Parameter adjustments align with market conditions"] if adaptation_detected else ["Limited regime adaptation observed"],
            "adaptation_score": np.random.uniform(0.6, 0.9) if adaptation_detected else np.random.uniform(0.3, 0.6)
        }
    
    def _analyze_risk_profile_changes(self, performance_history: List[Dict[str, Any]], 
                                    parameter_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze risk profile changes over time."""
        if len(performance_history) < 3:
            return {"detected": False, "insights": ["Insufficient data for risk analysis"]}
        
        # Extract volatility data
        volatilities = [entry["testing_performance"]["volatility"] for entry in performance_history if "testing_performance" in entry]
        
        if len(volatilities) < 3:
            return {"detected": False, "insights": ["Insufficient volatility data"]}
        
        # Analyze volatility trend
        vol_trend = np.polyfit(range(len(volatilities)), volatilities, 1)[0]
        significant_change = abs(vol_trend) > 0.02  # 2% volatility trend threshold
        
        change_direction = "increasing" if vol_trend > 0 else "decreasing"
        
        return {
            "detected": significant_change,
            "insights": [f"Risk profile {change_direction}", f"Volatility trend: {vol_trend:.4f}"] if significant_change else ["Stable risk profile"],
            "volatility_trend": vol_trend,
            "risk_direction": change_direction
        }
    
    def _analyze_parameter_drift_for_strategy(self, strategy_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze parameter drift for a single strategy."""
        # Extract parameters from training results
        parameters_over_time = []
        for data in strategy_data:
            if "training_performance" in data and "optimized_parameters" in data["training_performance"]:
                parameters_over_time.append(data["training_performance"]["optimized_parameters"])
        
        if len(parameters_over_time) < 2:
            return {"significant_drift": False, "drift_details": "Insufficient parameter data"}
        
        # Calculate parameter stability
        drift_scores = []
        for param in parameters_over_time[0].keys():
            values = [params.get(param, 0) for params in parameters_over_time]
            if len(set(values)) > 1:  # Parameter has changed
                coefficient_of_variation = np.std(values) / (np.mean(values) + 1e-6)
                drift_scores.append(coefficient_of_variation)
        
        avg_drift = np.mean(drift_scores) if drift_scores else 0.0
        significant_drift = avg_drift > 0.2  # 20% coefficient of variation threshold
        
        return {
            "significant_drift": significant_drift,
            "drift_score": avg_drift,
            "drift_details": f"Average parameter drift: {avg_drift:.3f}"
        }
    
    def _analyze_performance_trends_for_strategy(self, strategy_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze performance trends for a single strategy."""
        returns = [data["out_of_sample_return"] for data in strategy_data]
        
        if len(returns) < 2:
            return {"significant_trend": False, "trend_details": "Insufficient return data"}
        
        # Calculate trend
        trend_slope = np.polyfit(range(len(returns)), returns, 1)[0]
        significant_trend = abs(trend_slope) > 0.02  # 2% trend threshold
        
        trend_direction = "improving" if trend_slope > 0 else "declining"
        
        return {
            "significant_trend": significant_trend,
            "trend_slope": trend_slope,
            "trend_direction": trend_direction,
            "trend_details": f"Performance trend: {trend_direction} ({trend_slope:.4f})"
        }
    
    def _analyze_risk_changes_for_strategy(self, strategy_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze risk profile changes for a single strategy."""
        volatilities = []
        drawdowns = []
        
        for data in strategy_data:
            if "testing_performance" in data:
                volatilities.append(data["testing_performance"].get("volatility", 0.0))
                drawdowns.append(data["testing_performance"].get("max_drawdown", 0.0))
        
        if len(volatilities) < 2:
            return {"significant_changes": False, "risk_details": "Insufficient risk data"}
        
        # Analyze volatility changes
        vol_change = (volatilities[-1] - volatilities[0]) / (volatilities[0] + 1e-6)
        dd_change = (drawdowns[-1] - drawdowns[0]) / (drawdowns[0] + 1e-6) if drawdowns else 0.0
        
        significant_changes = abs(vol_change) > 0.3 or abs(dd_change) > 0.3  # 30% change threshold
        
        return {
            "significant_changes": significant_changes,
            "volatility_change": vol_change,
            "drawdown_change": dd_change,
            "risk_details": f"Volatility change: {vol_change:.1%}, Drawdown change: {dd_change:.1%}"
        }
    
    def _compile_evolution_result(self, strategy_name: str, 
                                evolution_insights: Dict[str, Dict[str, Any]],
                                performance_history: List[Dict[str, Any]]) -> StrategyEvolutionResult:
        """Compile evolution insights into final result."""
        # Determine if evolution detected
        evolution_detected = any(insights.get("detected", False) for insights in evolution_insights.values())
        
        # Generate recommendations
        recommendations = []
        if evolution_insights.get("parameter_drift", {}).get("detected", False):
            recommendations.append("Monitor parameter stability - consider regularization")
        
        if evolution_insights.get("performance_trends", {}).get("detected", False):
            trend_direction = evolution_insights["performance_trends"].get("trend_direction", "unknown")
            if trend_direction == "declining":
                recommendations.append("Address declining performance trend")
            else:
                recommendations.append("Capitalize on improving performance trend")
        
        if evolution_insights.get("regime_adaptation", {}).get("detected", False):
            recommendations.append("Enhance regime adaptation capabilities")
        
        if evolution_insights.get("risk_profile_changes", {}).get("detected", False):
            recommendations.append("Review risk management parameters")
        
        if not recommendations:
            recommendations.append("Strategy evolution within normal parameters")
        
        return StrategyEvolutionResult(
            strategy_name=strategy_name,
            analysis_period_start=performance_history[0]["timestamp"] if performance_history else datetime.now(),
            analysis_period_end=performance_history[-1]["timestamp"] if performance_history else datetime.now(),
            evolution_detected=evolution_detected,
            evolution_insights=evolution_insights,
            recommendations=recommendations,
            confidence_score=np.mean([insights.get("confidence", 0.5) for insights in evolution_insights.values()]) if evolution_insights else 0.5
        )
    
    def _generate_walk_forward_report(self, results: List[WalkForwardResult]) -> str:
        """Generate comprehensive walk-forward analysis report."""
        report_data = {
            "report_date": datetime.now().date().isoformat(),
            "analysis_summary": {
                "total_windows": len(results),
                "strategies_analyzed": len(set(strategy for result in results for strategy in result.strategies_analyzed)),
                "analysis_period_start": results[0].training_start.isoformat() if results else None,
                "analysis_period_end": results[-1].testing_end.isoformat() if results else None,
                "total_analysis_duration": sum(result.analysis_duration_seconds for result in results)
            },
            "window_results": [
                {
                    "window_id": result.window_id,
                    "training_period": f"{result.training_start.date()} to {result.training_end.date()}",
                    "testing_period": f"{result.testing_start.date()} to {result.testing_end.date()}",
                    "strategies_count": len(result.strategy_results),
                    "avg_out_of_sample_return": np.mean([sr["out_of_sample_return"] for sr in result.strategy_results]),
                    "degradation_detected": any(sr.get("degradation_detected", False) for sr in result.strategy_results)
                }
                for result in results
            ],
            "degradation_analysis": {
                "total_degradations": len(self.degradation_alerts),
                "critical_degradations": len([alert for alert in self.degradation_alerts if alert.level == AlertLevel.CRITICAL]),
                "strategies_with_degradation": len(set(alert.details.get("strategy") for alert in self.degradation_alerts if "strategy" in alert.details))
            },
            "evolution_analysis": {
                "total_evolution_analyses": len(self.strategy_evolution_history),
                "strategies_with_evolution": len(set(result.strategy_name for result in self.strategy_evolution_history if result.evolution_detected))
            },
            "recommendations": self._generate_walk_forward_recommendations(results)
        }
        
        # Save report
        report_path = f"reports/walk_forward_analysis_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        self.logger.info(f"Walk-forward analysis report generated: {report_path}")
        return report_path
    
    def _generate_walk_forward_recommendations(self, results: List[WalkForwardResult]) -> List[str]:
        """Generate recommendations based on walk-forward analysis results."""
        recommendations = []
        
        if not results:
            return ["No analysis results available for recommendations"]
        
        # Analyze overall performance
        all_returns = [sr["out_of_sample_return"] for result in results for sr in result.strategy_results]
        avg_return = np.mean(all_returns)
        
        if avg_return < 0.05:  # Less than 5% average return
            recommendations.append("Overall strategy performance below expectations - consider strategy review")
        
        # Analyze degradation patterns
        degradation_count = len(self.degradation_alerts)
        if degradation_count > len(results) * 0.3:  # More than 30% of windows have degradations
            recommendations.append("High degradation rate detected - implement enhanced monitoring")
        
        # Analyze parameter stability
        stability_scores = []
        for result in results:
            for sr in result.strategy_results:
                if "parameter_stability" in sr:
                    stability_scores.append(sr["parameter_stability"])
        
        if stability_scores and np.mean(stability_scores) < 0.7:  # Low stability
            recommendations.append("Parameter instability detected - consider regularization techniques")
        
        # Window-specific recommendations
        if len(results) < 5:
            recommendations.append("Increase analysis window count for more robust validation")
        
        if not recommendations:
            recommendations.append("Walk-forward analysis shows satisfactory strategy performance")
        
        return recommendations