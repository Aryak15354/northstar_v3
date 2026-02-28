"""
Northstar V3 Comprehensive Operation System - Analytics Dashboard
"""

import logging
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path

from .base_types import (
    OperationResult, CrisisValidationResult, AlphaValidationResult,
    SystemHealthStatus, PerformanceMetrics, Alert, AlertLevel
)
from .logging_config import setup_operation_logging
from .report_manager import ReportManager


@dataclass
class DashboardConfig:
    """Configuration for analytics dashboard."""
    output_directory: str = "reports/dashboard"
    chart_theme: str = "plotly_white"
    chart_width: int = 1200
    chart_height: int = 600
    enable_interactive: bool = True
    auto_refresh_seconds: int = 30
    max_data_points: int = 1000


@dataclass
class TrendAnalysis:
    """Trend analysis results."""
    trend_direction: str
    trend_strength: float
    trend_duration_days: int
    pattern_detected: str
    confidence_score: float
    support_levels: List[float]
    resistance_levels: List[float]
    next_target: Optional[float]


class AnalyticsDashboard:
    """Comprehensive analytics dashboard for Northstar V3 operations."""
    
    def __init__(self, config: Optional[DashboardConfig] = None):
        """Initialize the analytics dashboard."""
        self.logger = setup_operation_logging()
        self.config = config or DashboardConfig()
        
        # Create output directory
        self.output_path = Path(self.config.output_directory)
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        # Dashboard state
        self.dashboard_data = {}
        self.performance_history = []
        self.alert_history = []
        
        self.logger.info("Analytics Dashboard initialized")
    
    def create_crisis_performance_report(self, crisis_results: List[CrisisValidationResult]) -> str:
        """Create comprehensive crisis performance report."""
        if not crisis_results:
            return ""
        
        # Create summary statistics
        returns = [r.total_return for r in crisis_results]
        summary_stats = {
            "total_crises_tested": len(crisis_results),
            "average_return": np.mean(returns),
            "crisis_survival_rate": sum(1 for r in crisis_results if r.stress_test_passed) / len(crisis_results)
        }
        
        # Generate simple HTML report
        html_content = f"""
        <html><head><title>Crisis Performance Report</title></head>
        <body>
        <h1>Crisis Performance Analysis</h1>
        <p>Total Crises Tested: {summary_stats['total_crises_tested']}</p>
        <p>Average Return: {summary_stats['average_return']:.2%}</p>
        <p>Crisis Survival Rate: {summary_stats['crisis_survival_rate']:.1%}</p>
        </body></html>
        """
        
        report_path = self.output_path / "crisis_performance_report.html"
        with open(report_path, 'w') as f:
            f.write(html_content)
        
        return str(report_path)
    
    def create_alpha_validation_report(self, alpha_results: List[AlphaValidationResult]) -> str:
        """Create comprehensive alpha validation report."""
        if not alpha_results:
            return ""
        
        # Create summary statistics
        alphas = [r.alpha_generated for r in alpha_results]
        summary_stats = {
            "total_regimes_tested": len(alpha_results),
            "average_alpha": np.mean(alphas),
            "validation_success_rate": sum(1 for r in alpha_results if r.validation_passed) / len(alpha_results)
        }
        
        # Generate simple HTML report
        html_content = f"""
        <html><head><title>Alpha Validation Report</title></head>
        <body>
        <h1>Alpha Validation Analysis</h1>
        <p>Total Regimes Tested: {summary_stats['total_regimes_tested']}</p>
        <p>Average Alpha: {summary_stats['average_alpha']:.2%}</p>
        <p>Validation Success Rate: {summary_stats['validation_success_rate']:.1%}</p>
        </body></html>
        """
        
        report_path = self.output_path / "alpha_validation_report.html"
        with open(report_path, 'w') as f:
            f.write(html_content)
        
        return str(report_path)
    
    def create_system_health_dashboard(self, health_status: SystemHealthStatus, 
                                     recent_operations: List[OperationResult]) -> str:
        """Create system health monitoring dashboard."""
        success_count = sum(1 for op in recent_operations if op.status.value == "success") if recent_operations else 0
        total_operations = len(recent_operations) if recent_operations else 1
        success_rate = success_count / total_operations
        
        html_content = f"""
        <html><head><title>System Health Dashboard</title></head>
        <body>
        <h1>System Health Monitoring</h1>
        <p>System Status: {health_status.overall_health.value.upper()}</p>
        <p>Performance Score: {health_status.performance_score:.1%}</p>
        <p>Operation Success Rate: {success_rate:.1%}</p>
        </body></html>
        """
        
        dashboard_path = self.output_path / "system_health_dashboard.html"
        with open(dashboard_path, 'w') as f:
            f.write(html_content)
        
        return str(dashboard_path)
    
    def detect_performance_patterns(self, performance_data: List[Dict[str, Any]]) -> TrendAnalysis:
        """Detect performance patterns and trends."""
        if not performance_data:
            return TrendAnalysis(
                trend_direction="unknown",
                trend_strength=0.0,
                trend_duration_days=0,
                pattern_detected="insufficient_data",
                confidence_score=0.0,
                support_levels=[],
                resistance_levels=[],
                next_target=None
            )
        
        returns = [d.get('return', 0.0) for d in performance_data]
        
        if len(returns) >= 2:
            recent_trend = np.polyfit(range(len(returns)), returns, 1)[0]
            if recent_trend > 0.001:
                trend_direction = "up"
            elif recent_trend < -0.001:
                trend_direction = "down"
            else:
                trend_direction = "sideways"
        else:
            trend_direction = "unknown"
            recent_trend = 0.0
        
        trend_strength = min(abs(recent_trend) * 100, 1.0)
        confidence_score = min(len(returns) / 30.0, 1.0)
        
        return TrendAnalysis(
            trend_direction=trend_direction,
            trend_strength=trend_strength,
            trend_duration_days=len(returns),
            pattern_detected="normal_volatility",
            confidence_score=confidence_score,
            support_levels=[],
            resistance_levels=[],
            next_target=None
        )
    
    def generate_investor_report(self, operation_results: List[OperationResult],
                               crisis_results: List[CrisisValidationResult],
                               alpha_results: List[AlphaValidationResult]) -> str:
        """Generate comprehensive investor report."""
        total_operations = len(operation_results)
        successful_operations = sum(1 for op in operation_results if op.status.value == "success")
        success_rate = successful_operations / total_operations if total_operations > 0 else 0
        
        html_content = f"""
        <html><head><title>Northstar V3 Investor Report</title></head>
        <body>
        <h1>Northstar V3 Trading System - Investor Report</h1>
        <h2>Executive Summary</h2>
        <p>System Success Rate: {success_rate:.1%}</p>
        <p>Total Operations: {total_operations}</p>
        </body></html>
        """
        
        report_path = self.output_path / "investor_report.html"
        with open(report_path, 'w') as f:
            f.write(html_content)
        
        return str(report_path)