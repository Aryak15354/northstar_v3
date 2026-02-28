"""
V3 Architecture Integration

Complete integration of Phase 4 Shadow Reality enhancements with existing V3
architecture. Ensures all V3 components are used correctly, verifies no breaking
changes to existing functionality, and validates enhanced capabilities build upon
the foundation.

This integration provides seamless enhancement of V3 capabilities while maintaining
full backward compatibility and architectural integrity.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, field
import asyncio
import threading
import numpy as np
import pandas as pd
import json

# V3 Core Components
from src.core.events import EventBus
from src.core.state import UnifiedState
from src.core.orchestrator import Orchestrator
from src.core.memory import Memory
from src.core.clock import Clock

# V3 Intelligence Components
from src.intelligence.intelligence_stack import IntelligenceStack
from src.intelligence.memory_engine import MemoryEngine
from src.intelligence.bayesian_engine import BayesianEngine
from src.intelligence.confidence_engine import ConfidenceEngine

# V3 Portfolio Components
from src.portfolio.portfolio_governor import PortfolioGovernor
from src.portfolio.strategies import Strategies

# V3 Backtesting Components
from src.backtesting.backtest_engine import BacktestEngine

# Phase 4 Shadow Reality Components
from src.validation.phase3_intelligence_monitor import Phase3IntelligenceMonitor
from src.validation.shadow_portfolio_dashboard import ShadowPortfolioDashboard
from src.validation.performance_attribution_display import PerformanceAttributionDisplay
from src.validation.alert_and_diagnostic_system import AlertAndDiagnosticSystem
from src.validation.real_time_monitoring_integration import RealTimeMonitoringIntegration

# Phase 3 Components
from src.intelligence.regime_memory_system import RegimeMemorySystem
from src.intelligence.simple_tailwind_engine import SimpleTailwindEngine
from src.intelligence.no_edge_detector import NoEdgeDetector
from src.intelligence.anticipatory_capital_allocator import AnticipatoryCapitalAllocator

logger = logging.getLogger(__name__)

@dataclass
class V3IntegrationStatus:
    """V3 integration status tracking"""
    component_name: str
    integration_status: str  # 'integrated', 'enhanced', 'compatible', 'error'
    compatibility_verified: bool
    enhancement_applied: bool
    breaking_changes_detected: bool
    integration_notes: List[str]
    performance_impact: float  # -1.0 to 1.0, negative means degradation
    last_validation: datetime

@dataclass
class V3ArchitectureValidation:
    """Complete V3 architecture validation result"""
    timestamp: datetime
    overall_integration_status: str
    component_statuses: List[V3IntegrationStatus]
    compatibility_score: float
    enhancement_score: float
    performance_impact_score: float
    breaking_changes_count: int
    validation_summary: Dict[str, Any]
    recommendations: List[str]

class V3ArchitectureIntegration:
    """
    Complete V3 architecture integration for Phase 4 Shadow Reality
    
    Ensures:
    - All V3 components used correctly
    - No breaking changes to existing functionality
    - Enhanced capabilities build upon foundation
    - Automatic adaptation to Phase 3 component updates
    """
    
    def __init__(self,
                 event_bus: EventBus,
                 unified_state: UnifiedState,
                 orchestrator: Optional[Orchestrator] = None,
                 memory: Optional[Memory] = None,
                 clock: Optional[Clock] = None):
        """
        Initialize V3 architecture integration
        
        Args:
            event_bus: V3 event bus
            unified_state: V3 unified state
            orchestrator: V3 orchestrator (optional)
            memory: V3 memory system (optional)
            clock: V3 clock system (optional)
        """
        self.event_bus = event_bus
        self.unified_state = unified_state
        self.orchestrator = orchestrator
        self.memory = memory
        self.clock = clock
        
        # Integration state
        self.integration_components: Dict[str, Any] = {}
        self.component_statuses: Dict[str, V3IntegrationStatus] = {}
        self.validation_history: List[V3ArchitectureValidation] = []
        
        # V3 component references
        self.v3_components = {
            'event_bus': event_bus,
            'unified_state': unified_state,
            'orchestrator': orchestrator,
            'memory': memory,
            'clock': clock
        }
        
        # Phase 4 component references
        self.phase4_components: Dict[str, Any] = {}
        
        # Integration metrics
        self.integration_metrics = {
            'components_integrated': 0,
            'enhancements_applied': 0,
            'compatibility_checks': 0,
            'breaking_changes_prevented': 0,
            'performance_improvements': 0
        }
        
        # Compatibility tracking
        self.compatibility_tests = {}
        self.enhancement_tests = {}
        
        logger.info("V3ArchitectureIntegration initialized")
    
    def register_phase4_component(self, name: str, component: Any, integration_type: str = 'enhancement'):
        """
        Register a Phase 4 component for V3 integration
        
        Args:
            name: Component name
            component: Component instance
            integration_type: Type of integration ('enhancement', 'extension', 'replacement')
        """
        try:
            self.phase4_components[name] = {
                'component': component,
                'integration_type': integration_type,
                'registered_at': datetime.now()
            }
            
            # Initialize component status
            self.component_statuses[name] = V3IntegrationStatus(
                component_name=name,
                integration_status='registered',
                compatibility_verified=False,
                enhancement_applied=False,
                breaking_changes_detected=False,
                integration_notes=[f"Registered as {integration_type}"],
                performance_impact=0.0,
                last_validation=datetime.now()
            )
            
            logger.info(f"Phase 4 component registered: {name} ({integration_type})")
            
        except Exception as e:
            logger.error(f"Error registering Phase 4 component {name}: {e}")
            raise
    
    def integrate_with_v3_intelligence(self, intelligence_stack: IntelligenceStack) -> bool:
        """Integrate Phase 4 components with V3 intelligence stack"""
        try:
            logger.info("Integrating Phase 4 components with V3 intelligence stack")
            
            # Verify V3 intelligence stack compatibility
            compatibility_result = self._verify_intelligence_compatibility(intelligence_stack)
            
            if not compatibility_result['compatible']:
                logger.error(f"V3 intelligence compatibility check failed: {compatibility_result['issues']}")
                return False
            
            # Enhance intelligence stack with Phase 4 monitoring
            if 'phase3_intelligence_monitor' in self.phase4_components:
                monitor = self.phase4_components['phase3_intelligence_monitor']['component']
                
                # Subscribe to intelligence events
                self.event_bus.subscribe('intelligence_updated', monitor.update_monitoring_state)
                
                # Enhance intelligence stack with monitoring capabilities
                if hasattr(intelligence_stack, 'add_monitor'):
                    intelligence_stack.add_monitor('phase3_monitor', monitor)
                
                self._update_component_status('phase3_intelligence_monitor', 'integrated', True, True)
            
            # Integrate with memory engine
            if hasattr(intelligence_stack, 'memory_engine'):
                memory_engine = intelligence_stack.memory_engine
                self._integrate_with_memory_engine(memory_engine)
            
            # Integrate with bayesian engine
            if hasattr(intelligence_stack, 'bayesian_engine'):
                bayesian_engine = intelligence_stack.bayesian_engine
                self._integrate_with_bayesian_engine(bayesian_engine)
            
            # Integrate with confidence engine
            if hasattr(intelligence_stack, 'confidence_engine'):
                confidence_engine = intelligence_stack.confidence_engine
                self._integrate_with_confidence_engine(confidence_engine)
            
            self.integration_metrics['components_integrated'] += 1
            self.integration_metrics['enhancements_applied'] += 1
            
            logger.info("V3 intelligence integration completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error integrating with V3 intelligence: {e}")
            return False
    
    def integrate_with_v3_portfolio(self, portfolio_governor: PortfolioGovernor) -> bool:
        """Integrate Phase 4 components with V3 portfolio system"""
        try:
            logger.info("Integrating Phase 4 components with V3 portfolio system")
            
            # Verify portfolio compatibility
            compatibility_result = self._verify_portfolio_compatibility(portfolio_governor)
            
            if not compatibility_result['compatible']:
                logger.error(f"V3 portfolio compatibility check failed: {compatibility_result['issues']}")
                return False
            
            # Integrate shadow portfolio dashboard
            if 'shadow_portfolio_dashboard' in self.phase4_components:
                dashboard = self.phase4_components['shadow_portfolio_dashboard']['component']
                
                # Subscribe to portfolio events
                self.event_bus.subscribe('portfolio_updated', dashboard.update_dashboard)
                
                # Enhance portfolio governor with shadow monitoring
                if hasattr(portfolio_governor, 'add_monitor'):
                    portfolio_governor.add_monitor('shadow_dashboard', dashboard)
                
                self._update_component_status('shadow_portfolio_dashboard', 'integrated', True, True)
            
            # Integrate performance attribution
            if 'performance_attribution_display' in self.phase4_components:
                attribution = self.phase4_components['performance_attribution_display']['component']
                
                # Subscribe to performance events
                self.event_bus.subscribe('performance_updated', attribution.update_attribution_display)
                
                self._update_component_status('performance_attribution_display', 'integrated', True, True)
            
            self.integration_metrics['components_integrated'] += 1
            self.integration_metrics['enhancements_applied'] += 1
            
            logger.info("V3 portfolio integration completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error integrating with V3 portfolio: {e}")
            return False
    
    def integrate_with_v3_backtesting(self, backtest_engine: BacktestEngine) -> bool:
        """Integrate Phase 4 components with V3 backtesting system"""
        try:
            logger.info("Integrating Phase 4 components with V3 backtesting system")
            
            # Verify backtesting compatibility
            compatibility_result = self._verify_backtesting_compatibility(backtest_engine)
            
            if not compatibility_result['compatible']:
                logger.error(f"V3 backtesting compatibility check failed: {compatibility_result['issues']}")
                return False
            
            # Enhance backtest engine with Phase 4 capabilities
            if 'enhanced_backtesting_engine' in self.phase4_components:
                enhanced_engine = self.phase4_components['enhanced_backtesting_engine']['component']
                
                # Integrate enhanced backtesting
                if hasattr(backtest_engine, 'add_enhancement'):
                    backtest_engine.add_enhancement('phase4_enhancement', enhanced_engine)
                
                self._update_component_status('enhanced_backtesting_engine', 'integrated', True, True)
            
            # Integrate multi-timeline validation
            if 'multi_timeline_validation' in self.phase4_components:
                validation = self.phase4_components['multi_timeline_validation']['component']
                
                # Add multi-timeline capabilities
                if hasattr(backtest_engine, 'add_validator'):
                    backtest_engine.add_validator('multi_timeline', validation)
                
                self._update_component_status('multi_timeline_validation', 'integrated', True, True)
            
            self.integration_metrics['components_integrated'] += 1
            self.integration_metrics['enhancements_applied'] += 1
            
            logger.info("V3 backtesting integration completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error integrating with V3 backtesting: {e}")
            return False
    
    def validate_v3_architecture_integrity(self) -> V3ArchitectureValidation:
        """Validate complete V3 architecture integrity after Phase 4 integration"""
        try:
            logger.info("Validating V3 architecture integrity")
            
            timestamp = datetime.now()
            
            # Run comprehensive compatibility tests
            compatibility_results = self._run_compatibility_tests()
            
            # Run enhancement validation tests
            enhancement_results = self._run_enhancement_tests()
            
            # Check for breaking changes
            breaking_changes = self._detect_breaking_changes()
            
            # Calculate scores
            compatibility_score = self._calculate_compatibility_score(compatibility_results)
            enhancement_score = self._calculate_enhancement_score(enhancement_results)
            performance_impact_score = self._calculate_performance_impact()
            
            # Determine overall status
            overall_status = self._determine_overall_status(
                compatibility_score, enhancement_score, len(breaking_changes)
            )
            
            # Generate validation summary
            validation_summary = {
                'total_components': len(self.phase4_components),
                'integrated_components': len([s for s in self.component_statuses.values() if s.integration_status == 'integrated']),
                'compatibility_tests_passed': sum(1 for r in compatibility_results.values() if r['passed']),
                'enhancement_tests_passed': sum(1 for r in enhancement_results.values() if r['passed']),
                'performance_improvements': self.integration_metrics['performance_improvements'],
                'breaking_changes_prevented': self.integration_metrics['breaking_changes_prevented']
            }
            
            # Generate recommendations
            recommendations = self._generate_integration_recommendations(
                compatibility_results, enhancement_results, breaking_changes
            )
            
            # Create validation result
            validation = V3ArchitectureValidation(
                timestamp=timestamp,
                overall_integration_status=overall_status,
                component_statuses=list(self.component_statuses.values()),
                compatibility_score=compatibility_score,
                enhancement_score=enhancement_score,
                performance_impact_score=performance_impact_score,
                breaking_changes_count=len(breaking_changes),
                validation_summary=validation_summary,
                recommendations=recommendations
            )
            
            # Store validation
            self.validation_history.append(validation)
            
            # Emit validation event
            self.event_bus.emit('v3_architecture_validation_completed', {
                'validation': validation,
                'overall_status': overall_status,
                'compatibility_score': compatibility_score
            })
            
            logger.info(f"V3 architecture validation completed - Status: {overall_status}, "
                       f"Compatibility: {compatibility_score:.3f}, Enhancement: {enhancement_score:.3f}")
            
            return validation
            
        except Exception as e:
            logger.error(f"Error validating V3 architecture integrity: {e}")
            raise
    
    def _verify_intelligence_compatibility(self, intelligence_stack: IntelligenceStack) -> Dict[str, Any]:
        """Verify compatibility with V3 intelligence stack"""
        try:
            issues = []
            compatible = True
            
            # Check required methods
            required_methods = ['process', 'get_state', 'update']
            for method in required_methods:
                if not hasattr(intelligence_stack, method):
                    issues.append(f"Missing required method: {method}")
                    compatible = False
            
            # Check event bus integration
            if not hasattr(intelligence_stack, 'event_bus'):
                issues.append("Intelligence stack missing event bus integration")
                compatible = False
            
            # Check state management
            if not hasattr(intelligence_stack, 'state'):
                issues.append("Intelligence stack missing state management")
                compatible = False
            
            return {
                'compatible': compatible,
                'issues': issues,
                'tested_at': datetime.now()
            }
            
        except Exception as e:
            logger.warning(f"Error verifying intelligence compatibility: {e}")
            return {'compatible': False, 'issues': [str(e)], 'tested_at': datetime.now()}
    
    def _verify_portfolio_compatibility(self, portfolio_governor: PortfolioGovernor) -> Dict[str, Any]:
        """Verify compatibility with V3 portfolio system"""
        try:
            issues = []
            compatible = True
            
            # Check required methods
            required_methods = ['get_positions', 'update_positions', 'calculate_performance']
            for method in required_methods:
                if not hasattr(portfolio_governor, method):
                    issues.append(f"Missing required method: {method}")
                    compatible = False
            
            # Check portfolio state
            if not hasattr(portfolio_governor, 'positions'):
                issues.append("Portfolio governor missing positions state")
                compatible = False
            
            return {
                'compatible': compatible,
                'issues': issues,
                'tested_at': datetime.now()
            }
            
        except Exception as e:
            logger.warning(f"Error verifying portfolio compatibility: {e}")
            return {'compatible': False, 'issues': [str(e)], 'tested_at': datetime.now()}
    
    def _verify_backtesting_compatibility(self, backtest_engine: BacktestEngine) -> Dict[str, Any]:
        """Verify compatibility with V3 backtesting system"""
        try:
            issues = []
            compatible = True
            
            # Check required methods
            required_methods = ['run_backtest', 'get_results', 'add_strategy']
            for method in required_methods:
                if not hasattr(backtest_engine, method):
                    issues.append(f"Missing required method: {method}")
                    compatible = False
            
            # Check data handling
            if not hasattr(backtest_engine, 'data_handler'):
                issues.append("Backtest engine missing data handler")
                compatible = False
            
            return {
                'compatible': compatible,
                'issues': issues,
                'tested_at': datetime.now()
            }
            
        except Exception as e:
            logger.warning(f"Error verifying backtesting compatibility: {e}")
            return {'compatible': False, 'issues': [str(e)], 'tested_at': datetime.now()}
    
    def _integrate_with_memory_engine(self, memory_engine: MemoryEngine):
        """Integrate Phase 4 components with V3 memory engine"""
        try:
            # Enhance memory engine with Phase 3 regime memory
            if 'regime_memory_system' in self.phase4_components:
                regime_memory = self.phase4_components['regime_memory_system']['component']
                
                # Add regime memory as a memory provider
                if hasattr(memory_engine, 'add_memory_provider'):
                    memory_engine.add_memory_provider('regime_memory', regime_memory)
                
                self._update_component_status('regime_memory_system', 'integrated', True, True)
            
        except Exception as e:
            logger.warning(f"Error integrating with memory engine: {e}")
    
    def _integrate_with_bayesian_engine(self, bayesian_engine: BayesianEngine):
        """Integrate Phase 4 components with V3 Bayesian engine"""
        try:
            # Enhance Bayesian engine with Phase 4 attribution
            if 'performance_attribution_display' in self.phase4_components:
                attribution = self.phase4_components['performance_attribution_display']['component']
                
                # Add attribution as a Bayesian factor
                if hasattr(bayesian_engine, 'add_factor'):
                    bayesian_engine.add_factor('performance_attribution', attribution)
            
        except Exception as e:
            logger.warning(f"Error integrating with Bayesian engine: {e}")
    
    def _integrate_with_confidence_engine(self, confidence_engine: ConfidenceEngine):
        """Integrate Phase 4 components with V3 confidence engine"""
        try:
            # Enhance confidence engine with Phase 4 monitoring
            if 'phase3_intelligence_monitor' in self.phase4_components:
                monitor = self.phase4_components['phase3_intelligence_monitor']['component']
                
                # Add monitor as confidence provider
                if hasattr(confidence_engine, 'add_confidence_provider'):
                    confidence_engine.add_confidence_provider('phase3_monitor', monitor)
            
        except Exception as e:
            logger.warning(f"Error integrating with confidence engine: {e}")
    
    def _update_component_status(self, name: str, status: str, compatibility: bool, enhancement: bool):
        """Update component integration status"""
        if name in self.component_statuses:
            self.component_statuses[name].integration_status = status
            self.component_statuses[name].compatibility_verified = compatibility
            self.component_statuses[name].enhancement_applied = enhancement
            self.component_statuses[name].last_validation = datetime.now()
    
    def _run_compatibility_tests(self) -> Dict[str, Dict[str, Any]]:
        """Run comprehensive compatibility tests"""
        results = {}
        
        try:
            # Test event bus compatibility
            results['event_bus'] = self._test_event_bus_compatibility()
            
            # Test unified state compatibility
            results['unified_state'] = self._test_unified_state_compatibility()
            
            # Test component interface compatibility
            results['component_interfaces'] = self._test_component_interface_compatibility()
            
            self.integration_metrics['compatibility_checks'] += len(results)
            
        except Exception as e:
            logger.warning(f"Error running compatibility tests: {e}")
        
        return results
    
    def _run_enhancement_tests(self) -> Dict[str, Dict[str, Any]]:
        """Run enhancement validation tests"""
        results = {}
        
        try:
            # Test monitoring enhancements
            results['monitoring'] = self._test_monitoring_enhancements()
            
            # Test attribution enhancements
            results['attribution'] = self._test_attribution_enhancements()
            
            # Test dashboard enhancements
            results['dashboard'] = self._test_dashboard_enhancements()
            
        except Exception as e:
            logger.warning(f"Error running enhancement tests: {e}")
        
        return results
    
    def _detect_breaking_changes(self) -> List[Dict[str, Any]]:
        """Detect potential breaking changes"""
        breaking_changes = []
        
        try:
            # Check for method signature changes
            for component_name, component_info in self.phase4_components.items():
                component = component_info['component']
                
                # Check if component overrides V3 methods
                if hasattr(component, '__dict__'):
                    for attr_name in dir(component):
                        if attr_name.startswith('_'):
                            continue
                        
                        # Check if this might conflict with V3 methods
                        if self._is_potential_v3_conflict(attr_name):
                            breaking_changes.append({
                                'component': component_name,
                                'type': 'method_conflict',
                                'method': attr_name,
                                'severity': 'medium'
                            })
            
        except Exception as e:
            logger.warning(f"Error detecting breaking changes: {e}")
        
        return breaking_changes
    
    def _test_event_bus_compatibility(self) -> Dict[str, Any]:
        """Test event bus compatibility"""
        try:
            # Test basic event bus operations
            test_event = 'test_compatibility_event'
            test_data = {'test': True, 'timestamp': datetime.now()}
            
            # Test emit
            self.event_bus.emit(test_event, test_data)
            
            # Test subscribe (simplified)
            def test_handler(data):
                pass
            
            self.event_bus.subscribe('test_event', test_handler)
            
            return {'passed': True, 'notes': ['Event bus compatibility verified']}
            
        except Exception as e:
            return {'passed': False, 'notes': [f'Event bus compatibility failed: {e}']}
    
    def _test_unified_state_compatibility(self) -> Dict[str, Any]:
        """Test unified state compatibility"""
        try:
            # Test basic state operations
            test_key = 'test_compatibility_state'
            test_value = {'test': True, 'timestamp': datetime.now()}
            
            # Test set state
            self.unified_state.set_state(test_key, test_value)
            
            # Test get state
            retrieved_value = self.unified_state.get_state(test_key)
            
            if retrieved_value == test_value:
                return {'passed': True, 'notes': ['Unified state compatibility verified']}
            else:
                return {'passed': False, 'notes': ['State retrieval mismatch']}
            
        except Exception as e:
            return {'passed': False, 'notes': [f'Unified state compatibility failed: {e}']}
    
    def _test_component_interface_compatibility(self) -> Dict[str, Any]:
        """Test component interface compatibility"""
        try:
            notes = []
            all_passed = True
            
            for component_name, component_info in self.phase4_components.items():
                component = component_info['component']
                
                # Check if component has required interfaces
                if hasattr(component, 'update') or hasattr(component, 'process'):
                    notes.append(f'{component_name}: Interface compatible')
                else:
                    notes.append(f'{component_name}: Missing standard interface')
                    all_passed = False
            
            return {'passed': all_passed, 'notes': notes}
            
        except Exception as e:
            return {'passed': False, 'notes': [f'Interface compatibility test failed: {e}']}
    
    def _test_monitoring_enhancements(self) -> Dict[str, Any]:
        """Test monitoring enhancements"""
        try:
            if 'phase3_intelligence_monitor' in self.phase4_components:
                monitor = self.phase4_components['phase3_intelligence_monitor']['component']
                
                # Test monitoring functionality
                if hasattr(monitor, 'get_monitoring_summary'):
                    summary = monitor.get_monitoring_summary()
                    if summary and 'status' in summary:
                        return {'passed': True, 'notes': ['Monitoring enhancement verified']}
            
            return {'passed': False, 'notes': ['Monitoring enhancement not available']}
            
        except Exception as e:
            return {'passed': False, 'notes': [f'Monitoring enhancement test failed: {e}']}
    
    def _test_attribution_enhancements(self) -> Dict[str, Any]:
        """Test attribution enhancements"""
        try:
            if 'performance_attribution_display' in self.phase4_components:
                attribution = self.phase4_components['performance_attribution_display']['component']
                
                # Test attribution functionality
                if hasattr(attribution, 'get_attribution_summary'):
                    summary = attribution.get_attribution_summary()
                    if summary and 'status' in summary:
                        return {'passed': True, 'notes': ['Attribution enhancement verified']}
            
            return {'passed': False, 'notes': ['Attribution enhancement not available']}
            
        except Exception as e:
            return {'passed': False, 'notes': [f'Attribution enhancement test failed: {e}']}
    
    def _test_dashboard_enhancements(self) -> Dict[str, Any]:
        """Test dashboard enhancements"""
        try:
            if 'shadow_portfolio_dashboard' in self.phase4_components:
                dashboard = self.phase4_components['shadow_portfolio_dashboard']['component']
                
                # Test dashboard functionality
                if hasattr(dashboard, 'get_dashboard_summary'):
                    summary = dashboard.get_dashboard_summary()
                    if summary and 'status' in summary:
                        return {'passed': True, 'notes': ['Dashboard enhancement verified']}
            
            return {'passed': False, 'notes': ['Dashboard enhancement not available']}
            
        except Exception as e:
            return {'passed': False, 'notes': [f'Dashboard enhancement test failed: {e}']}
    
    def _is_potential_v3_conflict(self, method_name: str) -> bool:
        """Check if method name might conflict with V3 methods"""
        v3_method_patterns = [
            'process', 'update', 'get_state', 'set_state', 'emit', 'subscribe',
            'run', 'execute', 'calculate', 'analyze'
        ]
        
        return any(pattern in method_name.lower() for pattern in v3_method_patterns)
    
    def _calculate_compatibility_score(self, compatibility_results: Dict[str, Dict[str, Any]]) -> float:
        """Calculate overall compatibility score"""
        if not compatibility_results:
            return 0.0
        
        passed_tests = sum(1 for result in compatibility_results.values() if result.get('passed', False))
        total_tests = len(compatibility_results)
        
        return passed_tests / total_tests if total_tests > 0 else 0.0
    
    def _calculate_enhancement_score(self, enhancement_results: Dict[str, Dict[str, Any]]) -> float:
        """Calculate overall enhancement score"""
        if not enhancement_results:
            return 0.0
        
        passed_tests = sum(1 for result in enhancement_results.values() if result.get('passed', False))
        total_tests = len(enhancement_results)
        
        return passed_tests / total_tests if total_tests > 0 else 0.0
    
    def _calculate_performance_impact(self) -> float:
        """Calculate overall performance impact score"""
        if not self.component_statuses:
            return 0.0
        
        impacts = [status.performance_impact for status in self.component_statuses.values()]
        return np.mean(impacts) if impacts else 0.0
    
    def _determine_overall_status(self, compatibility_score: float, enhancement_score: float, breaking_changes_count: int) -> str:
        """Determine overall integration status"""
        if breaking_changes_count > 0:
            return 'critical_issues'
        elif compatibility_score < 0.7:
            return 'compatibility_issues'
        elif enhancement_score < 0.5:
            return 'limited_enhancements'
        elif compatibility_score >= 0.9 and enhancement_score >= 0.8:
            return 'fully_integrated'
        else:
            return 'partially_integrated'
    
    def _generate_integration_recommendations(self, 
                                           compatibility_results: Dict[str, Dict[str, Any]],
                                           enhancement_results: Dict[str, Dict[str, Any]],
                                           breaking_changes: List[Dict[str, Any]]) -> List[str]:
        """Generate integration recommendations"""
        recommendations = []
        
        # Breaking changes recommendations
        if breaking_changes:
            recommendations.append(f"Address {len(breaking_changes)} potential breaking changes")
            for change in breaking_changes[:3]:  # Top 3
                recommendations.append(f"Resolve {change['type']} in {change['component']}")
        
        # Compatibility recommendations
        failed_compatibility = [name for name, result in compatibility_results.items() if not result.get('passed', False)]
        if failed_compatibility:
            recommendations.append(f"Fix compatibility issues in: {', '.join(failed_compatibility)}")
        
        # Enhancement recommendations
        failed_enhancements = [name for name, result in enhancement_results.items() if not result.get('passed', False)]
        if failed_enhancements:
            recommendations.append(f"Improve enhancements in: {', '.join(failed_enhancements)}")
        
        # General recommendations
        if not recommendations:
            recommendations.append("V3 integration is successful - monitor for performance optimizations")
        
        return recommendations[:5]  # Limit to top 5 recommendations
    
    def get_integration_summary(self) -> Dict[str, Any]:
        """Get comprehensive integration summary"""
        try:
            latest_validation = self.validation_history[-1] if self.validation_history else None
            
            return {
                'status': 'active',
                'total_components': len(self.phase4_components),
                'integrated_components': len([s for s in self.component_statuses.values() if s.integration_status == 'integrated']),
                'latest_validation': {
                    'timestamp': latest_validation.timestamp.isoformat() if latest_validation else None,
                    'overall_status': latest_validation.overall_integration_status if latest_validation else 'not_validated',
                    'compatibility_score': latest_validation.compatibility_score if latest_validation else 0.0,
                    'enhancement_score': latest_validation.enhancement_score if latest_validation else 0.0,
                    'breaking_changes': latest_validation.breaking_changes_count if latest_validation else 0
                },
                'integration_metrics': self.integration_metrics.copy(),
                'component_statuses': {
                    name: {
                        'status': status.integration_status,
                        'compatible': status.compatibility_verified,
                        'enhanced': status.enhancement_applied,
                        'last_validation': status.last_validation.isoformat()
                    }
                    for name, status in self.component_statuses.items()
                },
                'v3_components': {
                    name: 'available' if component else 'not_available'
                    for name, component in self.v3_components.items()
                }
            }
            
        except Exception as e:
            logger.error(f"Error generating integration summary: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def force_integration_validation(self) -> V3ArchitectureValidation:
        """Force immediate integration validation"""
        logger.info("Forcing V3 architecture integration validation")
        return self.validate_v3_architecture_integrity()