"""
Integration Script: Health Calculator into System

Integrates the new HealthCalculator from Task 3 into the existing health monitoring system.
Replaces cosmetic health scores with meaningful calculations based on data freshness,
market consistency, and portfolio stability.

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cohesion.health_calculator import HealthCalculator
from src.cohesion.state_file_manager import StateFileManager
from src.core.health_monitor import HealthMonitor, HealthLevel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntegratedHealthMonitor(HealthMonitor):
    """
    Enhanced Health Monitor with integrated HealthCalculator
    
    Extends the existing HealthMonitor to use the new HealthCalculator
    for meaningful system health metrics instead of cosmetic scores.
    """
    
    def __init__(self, alert_threshold_minutes: int = 5, state_dir: str = "data/state"):
        """
        Initialize integrated health monitor
        
        Args:
            alert_threshold_minutes: Alert threshold in minutes
            state_dir: Directory containing state files
        """
        super().__init__(alert_threshold_minutes)
        
        # Initialize new health calculator
        self.state_manager = StateFileManager(state_dir)
        self.health_calculator = HealthCalculator(self.state_manager, state_dir)
        
        logger.info("✅ Integrated Health Monitor initialized with HealthCalculator")
    
    def get_system_health_report(self):
        """
        Generate comprehensive system health report using new HealthCalculator
        
        Overrides parent method to use meaningful health calculations.
        """
        # Get base report from parent
        base_report = super().get_system_health_report()
        
        try:
            # Calculate meaningful system health using new calculator
            health_metrics = self.health_calculator.calculate_system_health()
            
            # Update overall health score with meaningful calculation
            base_report.overall_health_score = health_metrics.overall_health
            
            # Update health level based on new score
            if health_metrics.overall_health >= 0.9:
                base_report.health_level = HealthLevel.EXCELLENT
            elif health_metrics.overall_health >= 0.7:
                base_report.health_level = HealthLevel.GOOD
            elif health_metrics.overall_health >= 0.5:
                base_report.health_level = HealthLevel.FAIR
            elif health_metrics.overall_health >= 0.3:
                base_report.health_level = HealthLevel.POOR
            else:
                base_report.health_level = HealthLevel.CRITICAL
            
            # Add component breakdown to performance summary
            base_report.performance_summary['health_components'] = {
                'data_freshness': health_metrics.data_freshness,
                'market_consistency': health_metrics.market_consistency,
                'portfolio_stability': health_metrics.portfolio_stability,
                'component_details': health_metrics.components
            }
            
            # Add health-based recommendations
            health_recommendations = self._generate_health_recommendations(health_metrics)
            base_report.recommendations.extend(health_recommendations)
            
            # Alert if health drops below 50%
            if health_metrics.overall_health < 0.5:
                from src.core.health_monitor import HealthAlert, AlertSeverity
                from datetime import datetime
                
                alert = HealthAlert(
                    timestamp=datetime.now(),
                    severity=AlertSeverity.CRITICAL,
                    organ_name="system",
                    alert_type="low_system_health",
                    message=f"System health dropped below 50%: {health_metrics.overall_health:.1%}",
                    metrics={
                        'overall_health': health_metrics.overall_health,
                        'data_freshness': health_metrics.data_freshness,
                        'market_consistency': health_metrics.market_consistency,
                        'portfolio_stability': health_metrics.portfolio_stability
                    }
                )
                base_report.system_alerts.append(alert)
                self._emit_alert(alert)
            
            logger.info(
                f"System Health: {health_metrics.overall_health:.1%} "
                f"(Freshness: {health_metrics.data_freshness:.1%}, "
                f"Consistency: {health_metrics.market_consistency:.1%}, "
                f"Stability: {health_metrics.portfolio_stability:.1%})"
            )
            
        except Exception as e:
            logger.error(f"Error calculating meaningful health metrics: {e}")
            # Fall back to base report if calculation fails
        
        return base_report
    
    def _generate_health_recommendations(self, health_metrics) -> list:
        """
        Generate recommendations based on health component scores
        
        Args:
            health_metrics: HealthMetrics from HealthCalculator
        
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # Data freshness recommendations
        if health_metrics.data_freshness < 0.5:
            recommendations.append(
                f"⚠️ Data freshness is low ({health_metrics.data_freshness:.1%}). "
                f"Market state age: {health_metrics.components.get('market_state_age_minutes', 0):.0f} minutes. "
                "Consider updating market data."
            )
        
        # Market consistency recommendations
        if health_metrics.market_consistency < 0.5:
            allowed = health_metrics.components.get('allowed_exposure', 0)
            actual = health_metrics.components.get('actual_exposure', 0)
            recommendations.append(
                f"⚠️ Market consistency is low ({health_metrics.market_consistency:.1%}). "
                f"Exposure mismatch: allowed={allowed:.1%}, actual={actual:.1%}. "
                "Portfolio Governor may not be respecting Market Brain limits."
            )
        
        # Portfolio stability recommendations
        if health_metrics.portfolio_stability < 0.5:
            turnover = health_metrics.components.get('recent_turnover', 0)
            recommendations.append(
                f"⚠️ Portfolio stability is low ({health_metrics.portfolio_stability:.1%}). "
                f"Recent turnover: {turnover:.1%}. "
                "High portfolio churn detected."
            )
        
        # Overall health recommendations
        if health_metrics.overall_health < 0.5:
            recommendations.append(
                "🚨 CRITICAL: System health below 50%. Immediate attention required."
            )
        elif health_metrics.overall_health < 0.7:
            recommendations.append(
                "⚠️ System health below optimal. Monitor closely."
            )
        
        return recommendations
    
    def display_health_dashboard(self):
        """Display comprehensive health dashboard"""
        report = self.get_system_health_report()
        
        print("\n" + "="*80)
        print("SYSTEM HEALTH DASHBOARD")
        print("="*80)
        
        # Overall health
        print(f"\n{'OVERALL HEALTH':-^80}")
        print(f"Health Score: {report.overall_health_score:.1%}")
        print(f"Health Level: {report.health_level.value.upper()}")
        
        # Component breakdown
        if 'health_components' in report.performance_summary:
            components = report.performance_summary['health_components']
            print(f"\n{'HEALTH COMPONENTS':-^80}")
            print(f"Data Freshness:      {components['data_freshness']:.1%} (40% weight)")
            print(f"Market Consistency:  {components['market_consistency']:.1%} (30% weight)")
            print(f"Portfolio Stability: {components['portfolio_stability']:.1%} (30% weight)")
            
            # Component details
            details = components['component_details']
            print(f"\n{'COMPONENT DETAILS':-^80}")
            print(f"Market State Age: {details.get('market_state_age_minutes', 0):.0f} minutes")
            print(f"Portfolio Age: {details.get('portfolio_age_minutes', 0):.0f} minutes")
            print(f"Allowed Exposure: {details.get('allowed_exposure', 0):.1%}")
            print(f"Actual Exposure: {details.get('actual_exposure', 0):.1%}")
            print(f"Recent Turnover: {details.get('recent_turnover', 0):.1%}")
        
        # Organ health
        print(f"\n{'ORGAN HEALTH':-^80}")
        print(f"Total Organs: {report.performance_summary['total_organs']}")
        print(f"Healthy: {report.performance_summary['healthy_organs']}")
        print(f"Degraded: {report.performance_summary['degraded_organs']}")
        print(f"Failed: {report.performance_summary['failed_organs']}")
        
        # Alerts
        if report.system_alerts:
            print(f"\n{'ACTIVE ALERTS':-^80}")
            for alert in report.system_alerts[-5:]:  # Show last 5
                print(f"[{alert.severity.value.upper()}] {alert.message}")
        
        # Recommendations
        if report.recommendations:
            print(f"\n{'RECOMMENDATIONS':-^80}")
            for i, rec in enumerate(report.recommendations[:5], 1):  # Show top 5
                print(f"{i}. {rec}")
        
        # Critical issues
        if report.critical_issues:
            print(f"\n{'CRITICAL ISSUES':-^80}")
            for issue in report.critical_issues:
                print(f"🚨 {issue}")
        
        print("\n" + "="*80 + "\n")


def main():
    """Test integrated health monitor"""
    logger.info("Testing Integrated Health Monitor...")
    
    try:
        # Create integrated health monitor
        monitor = IntegratedHealthMonitor()
        
        # Display health dashboard
        monitor.display_health_dashboard()
        
        logger.info("✅ Integration successful!")
        
    except Exception as e:
        logger.error(f"❌ Integration failed: {e}")
        raise


if __name__ == "__main__":
    main()
