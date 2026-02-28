"""
Report Manager for generating comprehensive operation reports.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

from .base_types import (
    OperationResult, CrisisValidationResult, AlphaValidationResult,
    SystemHealthStatus, ReportConfig
)


class ReportManager:
    """
    Manages report generation for all operation system components.
    
    Generates HTML, PDF, and JSON reports for crisis validation,
    alpha testing, system health, and comprehensive operations.
    """
    
    def __init__(self, config: ReportConfig):
        """Initialize the report manager."""
        self.config = config
        self.logger = logging.getLogger("northstar_operation.reports")
        
        # Create output directory
        self.output_path = Path(self.config.output_directory)
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Report Manager initialized - output: {self.output_path}")
    
    def generate_comprehensive_report(
        self,
        operation: OperationResult,
        crisis_results: List[CrisisValidationResult],
        alpha_results: List[AlphaValidationResult],
        health_status: SystemHealthStatus
    ) -> str:
        """
        Generate comprehensive system validation report.
        
        Args:
            operation: Main operation result
            crisis_results: Crisis validation results
            alpha_results: Alpha validation results
            health_status: Current system health
            
        Returns:
            str: Path to generated report
        """
        self.logger.info("Generating comprehensive validation report")
        
        # Create report data structure
        report_data = {
            "report_id": str(uuid.uuid4()),
            "generated_at": datetime.now().isoformat(),
            "report_type": "comprehensive_validation",
            "operation": self._serialize_operation(operation),
            "crisis_validation": {
                "summary": self._summarize_crisis_results(crisis_results),
                "details": [self._serialize_crisis_result(r) for r in crisis_results]
            },
            "alpha_validation": {
                "summary": self._summarize_alpha_results(alpha_results),
                "details": [self._serialize_alpha_result(r) for r in alpha_results]
            },
            "system_health": self._serialize_health_status(health_status),
            "recommendations": self._generate_recommendations(
                operation, crisis_results, alpha_results, health_status
            )
        }
        
        # Generate reports in requested formats
        report_paths = []
        
        if "json" in self.config.report_formats:
            json_path = self._generate_json_report(report_data, "comprehensive")
            report_paths.append(json_path)
        
        if "html" in self.config.report_formats:
            html_path = self._generate_html_report(report_data, "comprehensive")
            report_paths.append(html_path)
        
        if "pdf" in self.config.report_formats:
            pdf_path = self._generate_pdf_report(report_data, "comprehensive")
            report_paths.append(pdf_path)
        
        # Return primary report path (first format)
        primary_path = report_paths[0] if report_paths else None
        self.logger.info(f"Comprehensive report generated: {primary_path}")
        
        return primary_path
    
    def generate_crisis_report(
        self,
        crisis_results: List[CrisisValidationResult],
        operation_id: str = None
    ) -> str:
        """Generate crisis validation report."""
        self.logger.info("Generating crisis validation report")
        
        report_data = {
            "report_id": str(uuid.uuid4()),
            "generated_at": datetime.now().isoformat(),
            "report_type": "crisis_validation",
            "operation_id": operation_id,
            "summary": self._summarize_crisis_results(crisis_results),
            "crisis_periods": [self._serialize_crisis_result(r) for r in crisis_results],
            "aggregate_metrics": self._calculate_crisis_aggregates(crisis_results),
            "risk_analysis": self._analyze_crisis_risks(crisis_results)
        }
        
        # Generate JSON report
        json_path = self._generate_json_report(report_data, "crisis")
        self.logger.info(f"Crisis report generated: {json_path}")
        
        return json_path
    
    def generate_alpha_report(
        self,
        alpha_results: List[AlphaValidationResult],
        operation_id: str = None
    ) -> str:
        """Generate alpha validation report."""
        self.logger.info("Generating alpha validation report")
        
        report_data = {
            "report_id": str(uuid.uuid4()),
            "generated_at": datetime.now().isoformat(),
            "report_type": "alpha_validation",
            "operation_id": operation_id,
            "summary": self._summarize_alpha_results(alpha_results),
            "regime_analysis": [self._serialize_alpha_result(r) for r in alpha_results],
            "aggregate_metrics": self._calculate_alpha_aggregates(alpha_results),
            "signal_analysis": self._analyze_alpha_signals(alpha_results)
        }
        
        # Generate JSON report
        json_path = self._generate_json_report(report_data, "alpha")
        self.logger.info(f"Alpha report generated: {json_path}")
        
        return json_path
    
    def generate_system_report(
        self,
        report_type: str,
        health_status: SystemHealthStatus,
        recent_operations: List[OperationResult],
        active_operations: List[OperationResult]
    ) -> str:
        """Generate system status report."""
        self.logger.info(f"Generating {report_type} system report")
        
        report_data = {
            "report_id": str(uuid.uuid4()),
            "generated_at": datetime.now().isoformat(),
            "report_type": f"system_{report_type}",
            "system_health": self._serialize_health_status(health_status),
            "recent_operations": [self._serialize_operation(op) for op in recent_operations],
            "active_operations": [self._serialize_operation(op) for op in active_operations],
            "system_metrics": self._calculate_system_metrics(recent_operations),
            "operational_insights": self._generate_operational_insights(recent_operations)
        }
        
        # Generate JSON report
        json_path = self._generate_json_report(report_data, "system")
        self.logger.info(f"System report generated: {json_path}")
        
        return json_path
    
    def _generate_json_report(self, report_data: Dict[str, Any], report_type: str) -> str:
        """Generate JSON format report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{report_type}_report_{timestamp}.json"
        file_path = self.output_path / filename
        
        with open(file_path, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        return str(file_path)
    
    def _generate_html_report(self, report_data: Dict[str, Any], report_type: str) -> str:
        """Generate HTML format report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{report_type}_report_{timestamp}.html"
        file_path = self.output_path / filename
        
        # Generate basic HTML report
        html_content = self._create_html_template(report_data, report_type)
        
        with open(file_path, 'w') as f:
            f.write(html_content)
        
        return str(file_path)
    
    def _generate_pdf_report(self, report_data: Dict[str, Any], report_type: str) -> str:
        """Generate PDF format report."""
        # For now, create a placeholder PDF path
        # In a full implementation, this would use a library like reportlab or weasyprint
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{report_type}_report_{timestamp}.pdf"
        file_path = self.output_path / filename
        
        # Create placeholder file
        with open(file_path, 'w') as f:
            f.write(f"PDF Report Placeholder - {report_type}\n")
            f.write(f"Generated: {report_data['generated_at']}\n")
        
        return str(file_path)
    
    def _create_html_template(self, report_data: Dict[str, Any], report_type: str) -> str:
        """Create HTML template for report."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Northstar V3 {report_type.title()} Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .metric {{ display: inline-block; margin: 10px; padding: 10px; background-color: #f9f9f9; border-radius: 3px; }}
                .success {{ color: green; }}
                .warning {{ color: orange; }}
                .error {{ color: red; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Northstar V3 {report_type.title()} Report</h1>
                <p>Generated: {report_data['generated_at']}</p>
                <p>Report ID: {report_data['report_id']}</p>
            </div>
        """
        
        # Add report-specific content
        if report_type == "comprehensive":
            html += self._add_comprehensive_html_content(report_data)
        elif report_type == "crisis":
            html += self._add_crisis_html_content(report_data)
        elif report_type == "alpha":
            html += self._add_alpha_html_content(report_data)
        elif report_type == "system":
            html += self._add_system_html_content(report_data)
        
        html += """
        </body>
        </html>
        """
        
        return html
    
    def _add_comprehensive_html_content(self, report_data: Dict[str, Any]) -> str:
        """Add comprehensive report content to HTML."""
        return f"""
        <div class="section">
            <h2>Operation Summary</h2>
            <div class="metric">Status: {report_data['operation']['status']}</div>
            <div class="metric">Duration: {report_data['operation'].get('duration_seconds', 'N/A')}s</div>
        </div>
        
        <div class="section">
            <h2>Crisis Validation</h2>
            <p>Tested {len(report_data['crisis_validation']['details'])} crisis periods</p>
            <p>Pass Rate: {report_data['crisis_validation']['summary'].get('pass_rate', 0):.1%}</p>
        </div>
        
        <div class="section">
            <h2>Alpha Validation</h2>
            <p>Tested {len(report_data['alpha_validation']['details'])} market regimes</p>
            <p>Pass Rate: {report_data['alpha_validation']['summary'].get('pass_rate', 0):.1%}</p>
        </div>
        
        <div class="section">
            <h2>System Health</h2>
            <p>Overall Health: {report_data['system_health']['overall_health']}</p>
            <p>Performance Score: {report_data['system_health']['performance_score']:.2f}</p>
        </div>
        """
    
    def _add_crisis_html_content(self, report_data: Dict[str, Any]) -> str:
        """Add crisis report content to HTML."""
        return f"""
        <div class="section">
            <h2>Crisis Validation Summary</h2>
            <p>Total Periods Tested: {len(report_data['crisis_periods'])}</p>
            <p>Pass Rate: {report_data['summary'].get('pass_rate', 0):.1%}</p>
        </div>
        """
    
    def _add_alpha_html_content(self, report_data: Dict[str, Any]) -> str:
        """Add alpha report content to HTML."""
        return f"""
        <div class="section">
            <h2>Alpha Validation Summary</h2>
            <p>Regimes Tested: {len(report_data['regime_analysis'])}</p>
            <p>Pass Rate: {report_data['summary'].get('pass_rate', 0):.1%}</p>
        </div>
        """
    
    def _add_system_html_content(self, report_data: Dict[str, Any]) -> str:
        """Add system report content to HTML."""
        return f"""
        <div class="section">
            <h2>System Status</h2>
            <p>Health: {report_data['system_health']['overall_health']}</p>
            <p>Active Operations: {len(report_data['active_operations'])}</p>
            <p>Recent Operations: {len(report_data['recent_operations'])}</p>
        </div>
        """
    
    # Serialization helpers
    
    def _serialize_operation(self, operation: OperationResult) -> Dict[str, Any]:
        """Serialize operation result to dictionary."""
        return {
            "operation_id": operation.operation_id,
            "operation_type": operation.operation_type,
            "start_time": operation.start_time.isoformat(),
            "end_time": operation.end_time.isoformat() if operation.end_time else None,
            "status": operation.status.value,
            "duration_seconds": operation.duration_seconds,
            "performance_metrics": operation.performance_metrics,
            "validation_results": operation.validation_results,
            "alerts_count": len(operation.alerts_generated),
            "report_path": operation.report_path
        }
    
    def _serialize_crisis_result(self, result: CrisisValidationResult) -> Dict[str, Any]:
        """Serialize crisis validation result."""
        return {
            "crisis_period": result.crisis_period,
            "start_date": result.start_date.isoformat(),
            "end_date": result.end_date.isoformat(),
            "total_return": result.total_return,
            "max_drawdown": result.max_drawdown,
            "volatility": result.volatility,
            "sharpe_ratio": result.sharpe_ratio,
            "var_breach_count": result.var_breach_count,
            "recovery_time_days": result.recovery_time_days,
            "stress_test_passed": result.stress_test_passed,
            "risk_breaches": len(result.risk_limit_breaches)
        }
    
    def _serialize_alpha_result(self, result: AlphaValidationResult) -> Dict[str, Any]:
        """Serialize alpha validation result."""
        return {
            "regime": result.regime,
            "period_start": result.period_start.isoformat(),
            "period_end": result.period_end.isoformat(),
            "alpha_generated": result.alpha_generated,
            "information_ratio": result.information_ratio,
            "hit_rate": result.hit_rate,
            "signal_quality_score": result.signal_quality_score,
            "consistency_score": result.consistency_score,
            "regime_adaptation_score": result.regime_adaptation_score,
            "validation_passed": result.validation_passed,
            "signal_count": result.signal_count
        }
    
    def _serialize_health_status(self, status: SystemHealthStatus) -> Dict[str, Any]:
        """Serialize system health status."""
        return {
            "timestamp": status.timestamp.isoformat(),
            "overall_health": status.overall_health.value,
            "component_status": status.component_status,
            "performance_score": status.performance_score,
            "data_quality_score": status.data_quality_score,
            "latency_metrics": status.latency_metrics,
            "error_counts": status.error_counts,
            "alert_level": status.alert_level.value,
            "recommended_actions": status.recommended_actions
        }
    
    # Analysis helpers
    
    def _summarize_crisis_results(self, results: List[CrisisValidationResult]) -> Dict[str, Any]:
        """Summarize crisis validation results."""
        if not results:
            return {}
        
        return {
            "total_periods": len(results),
            "passed_periods": sum(r.stress_test_passed for r in results),
            "pass_rate": sum(r.stress_test_passed for r in results) / len(results),
            "avg_return": sum(r.total_return for r in results) / len(results),
            "avg_drawdown": sum(r.max_drawdown for r in results) / len(results),
            "avg_sharpe": sum(r.sharpe_ratio for r in results) / len(results),
            "total_var_breaches": sum(r.var_breach_count for r in results)
        }
    
    def _summarize_alpha_results(self, results: List[AlphaValidationResult]) -> Dict[str, Any]:
        """Summarize alpha validation results."""
        if not results:
            return {}
        
        return {
            "total_regimes": len(results),
            "passed_regimes": sum(r.validation_passed for r in results),
            "pass_rate": sum(r.validation_passed for r in results) / len(results),
            "avg_alpha": sum(r.alpha_generated for r in results) / len(results),
            "avg_information_ratio": sum(r.information_ratio for r in results) / len(results),
            "avg_hit_rate": sum(r.hit_rate for r in results) / len(results),
            "avg_signal_quality": sum(r.signal_quality_score for r in results) / len(results)
        }
    
    def _calculate_crisis_aggregates(self, results: List[CrisisValidationResult]) -> Dict[str, float]:
        """Calculate aggregate crisis metrics."""
        if not results:
            return {}
        
        return {
            "worst_drawdown": max(r.max_drawdown for r in results),
            "best_return": max(r.total_return for r in results),
            "worst_return": min(r.total_return for r in results),
            "highest_volatility": max(r.volatility for r in results),
            "best_sharpe": max(r.sharpe_ratio for r in results),
            "worst_sharpe": min(r.sharpe_ratio for r in results)
        }
    
    def _calculate_alpha_aggregates(self, results: List[AlphaValidationResult]) -> Dict[str, float]:
        """Calculate aggregate alpha metrics."""
        if not results:
            return {}
        
        return {
            "best_alpha": max(r.alpha_generated for r in results),
            "worst_alpha": min(r.alpha_generated for r in results),
            "best_ir": max(r.information_ratio for r in results),
            "worst_ir": min(r.information_ratio for r in results),
            "best_hit_rate": max(r.hit_rate for r in results),
            "worst_hit_rate": min(r.hit_rate for r in results)
        }
    
    def _analyze_crisis_risks(self, results: List[CrisisValidationResult]) -> Dict[str, Any]:
        """Analyze risk patterns in crisis results."""
        return {
            "high_risk_periods": [r.crisis_period for r in results if r.max_drawdown > 0.15],
            "var_breach_periods": [r.crisis_period for r in results if r.var_breach_count > 3],
            "recovery_analysis": {
                "avg_recovery_days": sum(r.recovery_time_days for r in results) / len(results),
                "longest_recovery": max(r.recovery_time_days for r in results)
            }
        }
    
    def _analyze_alpha_signals(self, results: List[AlphaValidationResult]) -> Dict[str, Any]:
        """Analyze alpha signal patterns."""
        return {
            "strong_regimes": [r.regime for r in results if r.alpha_generated > 0.05],
            "weak_regimes": [r.regime for r in results if r.alpha_generated < 0.01],
            "signal_quality_analysis": {
                "high_quality_regimes": [r.regime for r in results if r.signal_quality_score > 0.8],
                "low_quality_regimes": [r.regime for r in results if r.signal_quality_score < 0.5]
            }
        }
    
    def _calculate_system_metrics(self, operations: List[OperationResult]) -> Dict[str, Any]:
        """Calculate system-level metrics."""
        if not operations:
            return {}
        
        success_count = sum(1 for op in operations if op.status.value == "success")
        
        return {
            "total_operations": len(operations),
            "success_rate": success_count / len(operations),
            "avg_duration": sum(op.duration_seconds or 0 for op in operations) / len(operations),
            "operation_types": list(set(op.operation_type for op in operations))
        }
    
    def _generate_recommendations(
        self,
        operation: OperationResult,
        crisis_results: List[CrisisValidationResult],
        alpha_results: List[AlphaValidationResult],
        health_status: SystemHealthStatus
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        # Crisis-based recommendations
        failed_crisis = [r for r in crisis_results if not r.stress_test_passed]
        if failed_crisis:
            recommendations.append(f"Review risk management for {len(failed_crisis)} failed crisis periods")
        
        # Alpha-based recommendations
        failed_alpha = [r for r in alpha_results if not r.validation_passed]
        if failed_alpha:
            recommendations.append(f"Improve alpha generation for {len(failed_alpha)} market regimes")
        
        # Health-based recommendations
        if health_status.performance_score < 0.8:
            recommendations.append("System performance below optimal - investigate bottlenecks")
        
        if health_status.data_quality_score < 0.9:
            recommendations.append("Data quality issues detected - review data pipelines")
        
        return recommendations
    
    def _generate_operational_insights(self, operations: List[OperationResult]) -> List[str]:
        """Generate operational insights from recent operations."""
        insights = []
        
        if not operations:
            return insights
        
        # Success rate analysis
        success_rate = sum(1 for op in operations if op.status.value == "success") / len(operations)
        if success_rate < 0.9:
            insights.append(f"Operation success rate is {success_rate:.1%} - investigate failures")
        
        # Duration analysis
        durations = [op.duration_seconds for op in operations if op.duration_seconds]
        if durations:
            avg_duration = sum(durations) / len(durations)
            if avg_duration > 3600:  # More than 1 hour
                insights.append(f"Average operation duration is {avg_duration/60:.1f} minutes - consider optimization")
        
        return insights