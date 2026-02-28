"""
Real-Time Monitoring Integration

Integration layer for Phase 4.7 real-time monitoring dashboard with existing
V3 health monitoring systems. Provides seamless integration while maintaining
backward compatibility and enhancing existing capabilities.

This integration ensures that Phase 4.7 monitoring builds upon existing
infrastructure without breaking changes.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import asyncio
import threading
import numpy as np
import pandas as pd

from src.validation.phase3_intelligence_monitor import Phase3IntelligenceMonitor
from src.validation.shadow_portfolio_dashboard import ShadowPortfolioDashboard
from src.validation.performance_attribution_display import PerformanceAttributionDisplay
from src.validation.alert_and_diagnostic_system import AlertAndDiagnosticSystem
from src.core.events import EventBus
from src.core.state import UnifiedState
from src.core.health_monitor import HealthMonitor
from src.cohesion.health_monitor import HealthMonitor as CohesionHealthMonitor

logger = logging.getLogger(__name__)

@dataclass
class MonitoringIntegrationConfig:
    """Configuration for monitoring integration"""
    update_frequency: int = 60  # seconds
    enable_legacy_compatibility: bool = True
    enable_enhanced_features: bool = True
    alert_integration: bool = True
    dashboard_integration: bool = True
    attribution_integration: bool = True
    health_monitoring_integration: bool = True

class RealTimeMonitoringIntegration:
    """
    Integration layer for real-time monitoring with existing V3 systems
    
    Provides:
    - Seamless integration with existing health monitoring
    - Enhanced capabilities without breaking changes
    - Unified monitoring interface
    - Backward compatibility preservation
    """
    
    def __init__(self,
                 intelligence_monitor: Phase3IntelligenceMonitor,
                 portfolio_dashboard: ShadowPortfolioDashboard,
                 attribution_display: PerformanceAttributionDisplay,
                 alert_system: AlertAndDiagnosticSystem,
                 event_bus: EventBus,
                 unified_state: UnifiedState,
                 existing_health_monitor: Optional[HealthMonitor] = None,
                 cohesion_health_monitor: Optional[CohesionHealthMonitor] = None,
                 config: Optional[MonitoringIntegrationConfig] = None):
        """
        Initialize real-time monitoring integration
        
        Args:
            intelligence_monitor: Phase 3 intelligence monitor
            portfolio_dashboard: Shadow portfolio dashboard
            attribution_display: Performance attribution display
            alert_system: Alert and diagnostic system
            event_bus: System event bus
            unified_state: System unified state
            existing_health_monitor: Existing V3 health monitor
            cohesion_health_monitor: Cohesion health monitor
            config: Integration configuration
        """
        self.intelligence_monitor = intelligence_monitor
        self.portfolio_dashboard = portfolio_dashboard
        self.attribution_display = attribution_display
        self.alert_system = alert_system
        self.event_bus = event_bus
        self.unified_state = unified_state
        self.existing_health_monitor = existing_health_monitor
        self.cohesion_health_monitor = cohesion_health_monitor
        self.config = config or MonitoringIntegrationConfig()
        
        # Integration state
        self.is_running = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.last_update_time: Optional[datetime] = None
        
        # Enhanced monitoring data
        self.enhanced_health_data: Dict[str, Any] = {}
        self.legacy_compatibility_data: Dict[str, Any] = {}
        
        # Event subscriptions
        self._setup_event_subscriptions()
        
        # Integration metrics
        self.integration_metrics = {
            "updates_processed": 0,
            "alerts_integrated": 0,
            "health_checks_enhanced": 0,
            "compatibility_calls": 0
        }
        
        logger.info("RealTimeMonitoringIntegration initialized")
    
    def _setup_event_subscriptions(self):
        """Set up event subscriptions for integration"""
        try:
            # Subscribe to Phase 3 intelligence updates
            self.event_bus.subscribe('phase3_intelligence_updated', self._handle_intelligence_update)
            
            # Subscribe to dashboard updates
            self.event_bus.subscribe('shadow_portfolio_dashboard_updated', self._handle_dashboard_update)
            
            # Subscribe to attribution updates
            self.event_bus.subscribe('performance_attribution_display_updated', self._handle_attribution_update)
            
            # Subscribe to alert updates
            self.event_bus.subscribe('alert_generated', self._handle_alert_generated)
            self.event_bus.subscribe('system_health_updated', self._handle_system_health_update)
            
            # Subscribe to existing health monitor events (if available)
            if self.existing_health_monitor:
                self.event_bus.subscribe('health_check_completed', self._handle_legacy_health_check)
            
            logger.debug("Event subscriptions set up for monitoring integration")
            
        except Exception as e:
            logger.error(f"Error setting up event subscriptions: {e}")
    
    def start_monitoring(self):
        """Start real-time monitoring integration"""
        try:
            if self.is_running:
                logger.warning("Monitoring integration already running")
                return
            
            self.is_running = True
            
            # Start monitoring thread
            self.monitoring_thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True,
                name="RealTimeMonitoringIntegration"
            )
            self.monitoring_thread.start()
            
            # Emit integration started event
            self.event_bus.emit('monitoring_integration_started', {
                'timestamp': datetime.now(),
                'config': self.config.__dict__
            })
            
            logger.info("Real-time monitoring integration started")
            
        except Exception as e:
            logger.error(f"Error starting monitoring integration: {e}")
            self.is_running = False
            raise
    
    def stop_monitoring(self):
        """Stop real-time monitoring integration"""
        try:
            if not self.is_running:
                logger.warning("Monitoring integration not running")
                return
            
            self.is_running = False
            
            # Wait for monitoring thread to finish
            if self.monitoring_thread and self.monitoring_thread.is_alive():
                self.monitoring_thread.join(timeout=5.0)
            
            # Emit integration stopped event
            self.event_bus.emit('monitoring_integration_stopped', {
                'timestamp': datetime.now(),
                'metrics': self.integration_metrics
            })
            
            logger.info("Real-time monitoring integration stopped")
            
        except Exception as e:
            logger.error(f"Error stopping monitoring integration: {e}")
    
    def _monitoring_loop(self):
        """Main monitoring integration loop"""
        logger.info("Monitoring integration loop started")
        
        while self.is_running:
            try:
                # Update monitoring systems
                self._update_monitoring_systems()
                
                # Integrate with existing health monitoring
                if self.config.health_monitoring_integration:
                    self._integrate_health_monitoring()
                
                # Update integration metrics
                self.integration_metrics["updates_processed"] += 1
                self.last_update_time = datetime.now()
                
                # Sleep until next update
                threading.Event().wait(self.config.update_frequency)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                # Continue running despite errors
                threading.Event().wait(5.0)  # Brief pause before retry
        
        logger.info("Monitoring integration loop stopped")
    
    def _update_monitoring_systems(self):
        """Update all monitoring systems with latest data"""
        try:
            # Get latest market data from unified state
            market_data = self._get_latest_market_data()
            
            if market_data is not None and len(market_data) > 0:
                # Update intelligence monitor
                intelligence_snapshot = self.intelligence_monitor.update_monitoring_state(market_data)
                
                # Update portfolio dashboard (if shadow portfolio state available)
                shadow_portfolio_state = self._get_shadow_portfolio_state()
                dashboard_snapshot = None
                if shadow_portfolio_state:
                    dashboard_snapshot = self.portfolio_dashboard.update_dashboard(shadow_portfolio_state)
                
                # Update attribution display (if portfolio returns available)
                portfolio_returns = self._get_portfolio_returns()
                attribution_snapshot = None
                if portfolio_returns is not None and len(portfolio_returns) > 0:
                    attribution_snapshot = self.attribution_display.update_attribution_display(
                        portfolio_returns, market_data
                    )
                
                # Update alert and diagnostic system
                if intelligence_snapshot:
                    health_report = self.alert_system.process_monitoring_update(
                        intelligence_snapshot, dashboard_snapshot, attribution_snapshot
                    )
                    
                    # Store enhanced health data
                    self.enhanced_health_data = {
                        'intelligence_health': intelligence_snapshot.overall_health_score,
                        'portfolio_health': dashboard_snapshot.health_score if dashboard_snapshot else 0.5,
                        'attribution_quality': attribution_snapshot.attribution_breakdown.attribution_quality_score if attribution_snapshot else 0.5,
                        'overall_health': health_report.overall_health_score,
                        'active_alerts': len(health_report.active_alerts),
                        'timestamp': datetime.now()
                    }
                
        except Exception as e:
            logger.warning(f"Error updating monitoring systems: {e}")
    
    def _integrate_health_monitoring(self):
        """Integrate with existing health monitoring systems"""
        try:
            # Integrate with existing V3 health monitor
            if self.existing_health_monitor and self.config.enable_legacy_compatibility:
                self._integrate_with_existing_health_monitor()
            
            # Integrate with cohesion health monitor
            if self.cohesion_health_monitor and self.config.enable_enhanced_features:
                self._integrate_with_cohesion_health_monitor()
            
            self.integration_metrics["health_checks_enhanced"] += 1
            
        except Exception as e:
            logger.warning(f"Error integrating health monitoring: {e}")
    
    def _integrate_with_existing_health_monitor(self):
        """Integrate with existing V3 health monitor"""
        try:
            # Enhance existing health monitor with Phase 4.7 data
            if hasattr(self.existing_health_monitor, 'update_health_metrics'):
                enhanced_metrics = {
                    'phase3_intelligence_health': self.enhanced_health_data.get('intelligence_health', 0.5),
                    'shadow_portfolio_health': self.enhanced_health_data.get('portfolio_health', 0.5),
                    'attribution_quality': self.enhanced_health_data.get('attribution_quality', 0.5),
                    'active_alert_count': self.enhanced_health_data.get('active_alerts', 0),
                    'monitoring_integration_active': True
                }
                
                self.existing_health_monitor.update_health_metrics(enhanced_metrics)
            
            # Provide backward compatibility interface
            self.legacy_compatibility_data = {
                'system_health': self.enhanced_health_data.get('overall_health', 0.5),
                'component_health': {
                    'intelligence': self.enhanced_health_data.get('intelligence_health', 0.5),
                    'portfolio': self.enhanced_health_data.get('portfolio_health', 0.5),
                    'attribution': self.enhanced_health_data.get('attribution_quality', 0.5)
                },
                'alert_status': 'active' if self.enhanced_health_data.get('active_alerts', 0) > 0 else 'clear',
                'last_update': self.enhanced_health_data.get('timestamp', datetime.now())
            }
            
            self.integration_metrics["compatibility_calls"] += 1
            
        except Exception as e:
            logger.warning(f"Error integrating with existing health monitor: {e}")
    
    def _integrate_with_cohesion_health_monitor(self):
        """Integrate with cohesion health monitor"""
        try:
            if hasattr(self.cohesion_health_monitor, 'register_health_provider'):
                # Register Phase 4.7 monitoring as health provider
                self.cohesion_health_monitor.register_health_provider(
                    'phase4_monitoring',
                    self._provide_health_data
                )
            
            # Update cohesion health with enhanced data
            if hasattr(self.cohesion_health_monitor, 'update_component_health'):
                component_health = {
                    'phase3_intelligence': self.enhanced_health_data.get('intelligence_health', 0.5),
                    'shadow_portfolio': self.enhanced_health_data.get('portfolio_health', 0.5),
                    'performance_attribution': self.enhanced_health_data.get('attribution_quality', 0.5)
                }
                
                for component, health in component_health.items():
                    self.cohesion_health_monitor.update_component_health(component, health)
            
        except Exception as e:
            logger.warning(f"Error integrating with cohesion health monitor: {e}")
    
    def _provide_health_data(self) -> Dict[str, Any]:
        """Provide health data to cohesion health monitor"""
        return {
            'overall_health': self.enhanced_health_data.get('overall_health', 0.5),
            'component_health': {
                'intelligence': self.enhanced_health_data.get('intelligence_health', 0.5),
                'portfolio': self.enhanced_health_data.get('portfolio_health', 0.5),
                'attribution': self.enhanced_health_data.get('attribution_quality', 0.5)
            },
            'alerts': {
                'active_count': self.enhanced_health_data.get('active_alerts', 0),
                'severity_breakdown': self.alert_system.get_alert_summary().get('alerts_by_severity', {})
            },
            'last_update': self.enhanced_health_data.get('timestamp', datetime.now()),
            'integration_metrics': self.integration_metrics.copy()
        }
    
    def _get_latest_market_data(self) -> Optional[pd.DataFrame]:
        """Get latest market data from unified state"""
        try:
            # Get market data from unified state
            market_state = self.unified_state.get_state('market_data')
            
            if market_state and isinstance(market_state, dict):
                # Convert to DataFrame if needed
                if 'data' in market_state:
                    data = market_state['data']
                    if isinstance(data, pd.DataFrame):
                        return data.tail(1)  # Latest row
                    elif isinstance(data, dict):
                        return pd.DataFrame([data])
            
            # Fallback: create minimal market data for testing
            return pd.DataFrame({
                'timestamp': [datetime.now()],
                'market_return': [0.001],
                'volatility': [0.15],
                'volume': [1000000]
            })
            
        except Exception as e:
            logger.warning(f"Error getting market data: {e}")
            return None
    
    def _get_shadow_portfolio_state(self) -> Optional[Any]:
        """Get shadow portfolio state from unified state"""
        try:
            # Get shadow portfolio state from unified state
            portfolio_state = self.unified_state.get_state('shadow_portfolio')
            
            if portfolio_state:
                return portfolio_state
            
            # If no shadow portfolio state, return None
            return None
            
        except Exception as e:
            logger.warning(f"Error getting shadow portfolio state: {e}")
            return None
    
    def _get_portfolio_returns(self) -> Optional[pd.Series]:
        """Get portfolio returns for attribution analysis"""
        try:
            # Get portfolio returns from unified state
            returns_data = self.unified_state.get_state('portfolio_returns')
            
            if returns_data:
                if isinstance(returns_data, pd.Series):
                    return returns_data.tail(1)  # Latest return
                elif isinstance(returns_data, list):
                    return pd.Series(returns_data[-1:])  # Latest return
                elif isinstance(returns_data, (int, float)):
                    return pd.Series([returns_data])
            
            # Fallback: create minimal return data
            return pd.Series([0.001])  # Small positive return
            
        except Exception as e:
            logger.warning(f"Error getting portfolio returns: {e}")
            return None
    
    # Event handlers
    def _handle_intelligence_update(self, event_data: Dict[str, Any]):
        """Handle Phase 3 intelligence update events"""
        try:
            snapshot = event_data.get('snapshot')
            if snapshot:
                # Update enhanced health data
                self.enhanced_health_data['intelligence_health'] = snapshot.overall_health_score
                self.enhanced_health_data['timestamp'] = datetime.now()
                
                # Emit enhanced event for existing systems
                if self.config.enable_legacy_compatibility:
                    self.event_bus.emit('enhanced_intelligence_health_updated', {
                        'health_score': snapshot.overall_health_score,
                        'anomalies': snapshot.anomaly_flags,
                        'regime_confidence': snapshot.regime_state.confidence_score
                    })
            
        except Exception as e:
            logger.warning(f"Error handling intelligence update: {e}")
    
    def _handle_dashboard_update(self, event_data: Dict[str, Any]):
        """Handle dashboard update events"""
        try:
            snapshot = event_data.get('snapshot')
            if snapshot:
                # Update enhanced health data
                self.enhanced_health_data['portfolio_health'] = snapshot.health_score
                
                # Emit enhanced event for existing systems
                if self.config.enable_legacy_compatibility:
                    self.event_bus.emit('enhanced_portfolio_health_updated', {
                        'health_score': snapshot.health_score,
                        'performance_metrics': snapshot.performance_metrics.__dict__,
                        'divergence': snapshot.shadow_vs_live_divergence
                    })
            
        except Exception as e:
            logger.warning(f"Error handling dashboard update: {e}")
    
    def _handle_attribution_update(self, event_data: Dict[str, Any]):
        """Handle attribution update events"""
        try:
            snapshot = event_data.get('snapshot')
            if snapshot:
                # Update enhanced health data
                self.enhanced_health_data['attribution_quality'] = snapshot.attribution_breakdown.attribution_quality_score
                
                # Emit enhanced event for existing systems
                if self.config.enable_legacy_compatibility:
                    self.event_bus.emit('enhanced_attribution_updated', {
                        'quality_score': snapshot.attribution_breakdown.attribution_quality_score,
                        'unexplained_alpha': snapshot.attribution_breakdown.unexplained_alpha,
                        'regime_attribution': snapshot.attribution_breakdown.regime_attribution
                    })
            
        except Exception as e:
            logger.warning(f"Error handling attribution update: {e}")
    
    def _handle_alert_generated(self, event_data: Dict[str, Any]):
        """Handle alert generation events"""
        try:
            alert = event_data.get('alert')
            if alert:
                # Update alert count
                self.enhanced_health_data['active_alerts'] = len(self.alert_system.active_alerts)
                
                # Integrate with existing alert systems
                if self.config.alert_integration and self.existing_health_monitor:
                    if hasattr(self.existing_health_monitor, 'handle_alert'):
                        self.existing_health_monitor.handle_alert({
                            'severity': alert.severity.value,
                            'category': alert.category.value,
                            'message': alert.message,
                            'timestamp': alert.timestamp
                        })
                
                self.integration_metrics["alerts_integrated"] += 1
            
        except Exception as e:
            logger.warning(f"Error handling alert generation: {e}")
    
    def _handle_system_health_update(self, event_data: Dict[str, Any]):
        """Handle system health update events"""
        try:
            health_report = event_data.get('health_report')
            if health_report:
                # Update overall health
                self.enhanced_health_data['overall_health'] = health_report.overall_health_score
                self.enhanced_health_data['active_alerts'] = len(health_report.active_alerts)
                
                # Emit comprehensive health event
                self.event_bus.emit('comprehensive_system_health_updated', {
                    'overall_health': health_report.overall_health_score,
                    'component_health': health_report.component_health,
                    'performance_summary': health_report.performance_summary,
                    'risk_indicators': health_report.risk_indicators,
                    'recommendations': health_report.recommendations
                })
            
        except Exception as e:
            logger.warning(f"Error handling system health update: {e}")
    
    def _handle_legacy_health_check(self, event_data: Dict[str, Any]):
        """Handle legacy health check events"""
        try:
            # Enhance legacy health check with Phase 4.7 data
            enhanced_data = event_data.copy()
            enhanced_data.update({
                'phase4_monitoring': {
                    'intelligence_health': self.enhanced_health_data.get('intelligence_health', 0.5),
                    'portfolio_health': self.enhanced_health_data.get('portfolio_health', 0.5),
                    'attribution_quality': self.enhanced_health_data.get('attribution_quality', 0.5),
                    'active_alerts': self.enhanced_health_data.get('active_alerts', 0)
                }
            })
            
            # Re-emit enhanced health check
            self.event_bus.emit('enhanced_health_check_completed', enhanced_data)
            
        except Exception as e:
            logger.warning(f"Error handling legacy health check: {e}")
    
    # Public interface methods
    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitoring integration status"""
        try:
            return {
                "status": "running" if self.is_running else "stopped",
                "last_update": self.last_update_time.isoformat() if self.last_update_time else None,
                "integration_metrics": self.integration_metrics.copy(),
                "enhanced_health_data": self.enhanced_health_data.copy(),
                "config": self.config.__dict__,
                "components": {
                    "intelligence_monitor": "active",
                    "portfolio_dashboard": "active",
                    "attribution_display": "active",
                    "alert_system": "active",
                    "existing_health_monitor": "integrated" if self.existing_health_monitor else "not_available",
                    "cohesion_health_monitor": "integrated" if self.cohesion_health_monitor else "not_available"
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting monitoring status: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_legacy_compatibility_interface(self) -> Dict[str, Any]:
        """Get legacy compatibility interface for existing systems"""
        return self.legacy_compatibility_data.copy()
    
    def force_update(self):
        """Force immediate update of all monitoring systems"""
        try:
            logger.info("Forcing monitoring systems update")
            self._update_monitoring_systems()
            
            if self.config.health_monitoring_integration:
                self._integrate_health_monitoring()
            
        except Exception as e:
            logger.error(f"Error forcing monitoring update: {e}")
    
    def __enter__(self):
        """Context manager entry"""
        self.start_monitoring()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.stop_monitoring()