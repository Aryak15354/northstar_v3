#!/usr/bin/env python3
"""
🏛️ INSTITUTIONAL ALPHA ENGINE - LAYER 14
Unified orchestrator for institutional-grade alpha generation

This implements Layer 14 of the institutional alpha engine:
- Integration of all components into unified alpha engine
- Main execution loop with proper sequencing
- Configuration management for all parameters
- Error handling and graceful degradation
- Logging and monitoring integration

Key Features:
1. Unified Alpha Engine Orchestrator
2. Component Integration Pipeline
3. Configuration Management System
4. Error Handling and Recovery
5. Performance Monitoring Integration
6. Institutional Reporting Integration

Usage:
    try:
    from intelligence.institutional_alpha_engine import InstitutionalAlphaEngine
except ImportError:
    from InstitutionalAlphaEngine import InstitutionalAlphaEngine
    
    engine = InstitutionalAlphaEngine()
    positions = engine.generate_alpha_positions(market_data)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import warnings
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import json
import logging
from collections import defaultdict

warnings.filterwarnings('ignore')

import sys
# Import all institutional alpha engine components
try:
    from .regime_aware_specialists import (
        RegimeAwareSpecialists, MarketRegime, RegimeContext
    )
except ImportError:
    from regime_aware_specialists import (
        RegimeAwareSpecialists, MarketRegime, RegimeContext
    )

try:
    from .bayesian_capital_tribunal import BayesianCapitalTribunal
except ImportError:
    from bayesian_capital_tribunal import BayesianCapitalTribunal
try:
    from .portfolio_governor import PortfolioGovernor
except ImportError:
    from PortfolioGovernor import PortfolioGovernor
try:
    from .signal_health_monitor import SignalHealthMonitor
except ImportError:
    from SignalHealthMonitor import SignalHealthMonitor
try:
    from .real_time_health_monitor import RealTimeHealthMonitor
except ImportError:
    from RealTimeHealthMonitor import RealTimeHealthMonitor
try:
    from .economic_causality_validator import EconomicCausalityValidator
except ImportError:
    from EconomicCausalityValidator import EconomicCausalityValidator
try:
    from .stress_testing_system import StressTestingSystem
except ImportError:
    from StressTestingSystem import StressTestingSystem
try:
    from ..reporting.institutional_reporting_system import InstitutionalReportingSystem
except ImportError:
    try:
        from src.reporting.institutional_reporting_system import InstitutionalReportingSystem
    except ImportError:
        # Create a mock class if not available
        class InstitutionalReportingSystem:
            def __init__(self, *args, **kwargs):
                pass
            def generate_report(self, *args, **kwargs):
                return {"status": "mock_report"}
try:
    from .temporal_guard import TemporalGuard
except ImportError:
    try:
        from temporal_guard import TemporalGuard
    except ImportError:
        from src.intelligence.temporal_guard import TemporalGuard

@dataclass
class AlphaEngineConfig:
    """Configuration for the institutional alpha engine"""
    # Specialist configuration
    enable_momentum: bool = True
    enable_value: bool = True
    enable_quality: bool = True
    enable_macro: bool = True
    
    # Bayesian tribunal configuration
    min_allocation: float = 0.01
    max_allocation: float = 0.60
    reallocation_threshold: float = 0.05
    
    # Portfolio governor configuration
    max_individual_weight: float = 0.05
    max_sector_weight: float = 0.25
    min_cash_buffer: float = 0.05
    max_turnover_monthly: float = 0.50
    
    # Health monitoring configuration
    alert_percentile_threshold: float = 25.0
    performance_deviation_threshold: float = 2.0
    regime_confidence_threshold: float = 60.0
    volatility_survival_threshold: float = 95.0
    
    # Risk management configuration
    max_portfolio_volatility: float = 0.15
    max_drawdown_limit: float = 0.40
    risk_budget_limit: float = 0.15
    
    # Reporting configuration
    enable_real_time_reporting: bool = True
    enable_institutional_reporting: bool = True
    reporting_frequency: str = "daily"  # daily, weekly, monthly
    
    # System configuration
    enable_temporal_protection: bool = True
    enable_stress_testing: bool = True
    enable_economic_validation: bool = True
    log_level: str = "INFO"

@dataclass
class AlphaEngineState:
    """Current state of the alpha engine"""
    current_regime: MarketRegime
    regime_confidence: float
    specialist_allocations: Dict[str, float]
    portfolio_positions: Dict[str, float]
    health_status: str
    last_update: datetime
    performance_metrics: Dict[str, float]
    active_alerts: List[str]
    survival_protocol_active: bool
    defensive_mode_active: bool

@dataclass
class AlphaGenerationResult:
    """Result of alpha generation process"""
    positions: Dict[str, float]
    allocations: Dict[str, float]
    regime_state: MarketRegime
    health_status: str
    performance_metrics: Dict[str, float]
    execution_time: float
    alerts: List[str]
    metadata: Dict[str, Any]

class InstitutionalAlphaEngine:
    """
    Institutional Alpha Engine
    
    Main orchestrator that integrates all components of the institutional
    alpha engine into a unified system for professional alpha generation.
    """
    
    def __init__(self, config: Optional[AlphaEngineConfig] = None):
        self.config = config or AlphaEngineConfig()
        self.state = None
        
        # Setup logging
        self._setup_logging()
        
        # Initialize components
        self._initialize_components()
        
        # Initialize state
        self._initialize_state()
        
        self.logger.info("🏛️ Institutional Alpha Engine initialized")
    
    def _setup_logging(self):
        """Setup logging configuration"""
        
        log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('logs/institutional_alpha_engine.log', mode='a')
            ]
        )
        
        self.logger = logging.getLogger('InstitutionalAlphaEngine')
    
    def _initialize_components(self):
        """Initialize all alpha engine components"""
        
        self.logger.info("Initializing alpha engine components...")
        
        try:
            # Core components
            self.temporal_guard = TemporalGuard() if self.config.enable_temporal_protection else None
            self.regime_specialists = RegimeAwareSpecialists()
            self.bayesian_tribunal = BayesianCapitalTribunal()
            self.portfolio_governor = PortfolioGovernor()
            
            # Monitoring and validation components
            self.signal_health_monitor = SignalHealthMonitor()
            self.real_time_health_monitor = RealTimeHealthMonitor()
            self.economic_validator = EconomicCausalityValidator() if self.config.enable_economic_validation else None
            self.stress_tester = StressTestingSystem() if self.config.enable_stress_testing else None
            
            # Reporting components
            self.institutional_reporter = InstitutionalReportingSystem() if self.config.enable_institutional_reporting else None
            
            self.logger.info("✅ All components initialized successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Component initialization failed: {e}")
            raise
    
    def _initialize_state(self):
        """Initialize engine state"""
        
        self.state = AlphaEngineState(
            current_regime=MarketRegime.EXPANSION,  # Default regime
            regime_confidence=0.0,
            specialist_allocations={},
            portfolio_positions={},
            health_status="initializing",
            last_update=datetime.now(),
            performance_metrics={},
            active_alerts=[],
            survival_protocol_active=False,
            defensive_mode_active=False
        )
        
        self.logger.info("✅ Engine state initialized")
    
    def generate_alpha_positions(self, market_data: Dict[str, Any], 
                                universe: List[str]) -> AlphaGenerationResult:
        """
        Main alpha generation pipeline
        
        This is the core method that orchestrates the entire institutional
        alpha generation process from market data to final positions.
        """
        
        start_time = datetime.now()
        self.logger.info("🚀 Starting alpha generation pipeline")
        
        try:
            # Step 1: Regime Detection
            regime_result = self._detect_market_regime(market_data)
            
            # Step 2: Generate Specialist Signals
            specialist_signals = self._generate_specialist_signals(market_data, universe, regime_result)
            
            # Step 3: Monitor Signal Health
            health_metrics = self._monitor_signal_health(specialist_signals, market_data)
            
            # Step 4: Bayesian Capital Allocation
            capital_allocations = self._allocate_capital(specialist_signals, health_metrics, regime_result)
            
            # Step 5: Portfolio-Aware Position Sizing
            portfolio_positions = self._size_positions(capital_allocations, specialist_signals, market_data)
            
            # Step 6: Risk Management and Validation
            final_positions = self._apply_risk_management(portfolio_positions, market_data)
            
            # Step 7: Health Monitoring and Alerts
            system_health = self._monitor_system_health(specialist_signals, market_data, capital_allocations)
            
            # Step 8: Update State
            self._update_engine_state(regime_result, capital_allocations, final_positions, system_health)
            
            # Step 9: Generate Reporting Data
            if self.config.enable_institutional_reporting:
                self._update_reporting_data(specialist_signals, market_data, capital_allocations)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            # Create result
            result = AlphaGenerationResult(
                positions=final_positions,
                allocations=capital_allocations,
                regime_state=regime_result['regime'],
                health_status=system_health.overall_health,
                performance_metrics=self._calculate_performance_metrics(final_positions, market_data),
                execution_time=execution_time,
                alerts=[alert.description for alert in system_health.active_alerts],
                metadata={
                    'regime_confidence': regime_result['confidence'],
                    'specialist_count': len(specialist_signals),
                    'universe_size': len(universe),
                    'timestamp': datetime.now().isoformat()
                }
            )
            
            self.logger.info(f"✅ Alpha generation completed in {execution_time:.2f}s")
            self.logger.info(f"   Regime: {regime_result['regime'].value}")
            self.logger.info(f"   Health: {system_health.overall_health}")
            self.logger.info(f"   Positions: {len(final_positions)}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Alpha generation failed: {e}")
            
            # Return safe fallback result
            return self._generate_fallback_result(market_data, universe, str(e))
    
    def _detect_market_regime(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Detect current market regime"""
        
        self.logger.debug("🔍 Detecting market regime")
        
        try:
            # Use regime specialists system for regime detection
            current_time = datetime.now()
            regime_context = self.regime_specialists.regime_detector.detect_regime(current_time)
            
            return {
                'regime': regime_context.regime,
                'confidence': regime_context.confidence,
                'transition_probabilities': regime_context.transition_probability,
                'regime_context': regime_context
            }
            
        except Exception as e:
            self.logger.warning(f"⚠️ Regime detection failed: {e}, using fallback")
            
            # Fallback to neutral regime
            return {
                'regime': MarketRegime.EXPANSION,
                'confidence': 0.5,
                'transition_probabilities': {},
                'regime_context': None
            }
    
    def _generate_specialist_signals(self, market_data: Dict[str, Any], 
                                   universe: List[str], regime_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate signals from all active specialists"""
        
        self.logger.debug("📊 Generating specialist signals")
        
        specialist_signals = {}
        
        try:
            # Generate signals from regime-aware specialists
            current_time = datetime.now()
            signals_result = self.regime_specialists.generate_regime_signals(universe, current_time)
            
            # Extract the actual signals from the nested structure
            signals = signals_result.get('signals', {})
            
            # Filter based on configuration
            if self.config.enable_momentum and 'momentum' in signals:
                specialist_signals['momentum'] = signals['momentum']
            
            if self.config.enable_value and 'value' in signals:
                specialist_signals['value'] = signals['value']
            
            if self.config.enable_quality and 'quality' in signals:
                specialist_signals['quality'] = signals['quality']
            
            if self.config.enable_macro and 'macro' in signals:
                specialist_signals['macro'] = signals['macro']
            
            self.logger.debug(f"✅ Generated signals from {len(specialist_signals)} specialists")
            
            return specialist_signals
            
        except Exception as e:
            self.logger.error(f"❌ Signal generation failed: {e}")
            return {}
    
    def _monitor_signal_health(self, specialist_signals: Dict[str, Any], 
                             market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Monitor health of all specialist signals"""
        
        self.logger.debug("🏥 Monitoring signal health")
        
        try:
            # Use the correct method from SignalHealthMonitor
            current_time = datetime.now()
            health_reports = self.signal_health_monitor.analyze_signal_health(
                specialist_signals, current_time
            )
            
            # Convert health reports to simple dict format
            health_metrics = {}
            for specialist_name, report in health_reports.items():
                health_metrics[specialist_name] = {
                    'overall_health_score': report.overall_health_score,
                    'alert_level': report.alert_level,
                    'ic_count': len(report.ic_metrics),
                    'recommendations_count': len(report.recommendations),
                    'timestamp': report.timestamp.isoformat()
                }
            
            return health_metrics
            
        except Exception as e:
            self.logger.warning(f"⚠️ Health monitoring failed: {e}")
            return {}
    
    def _allocate_capital(self, specialist_signals: Dict[str, Any], 
                         health_metrics: Dict[str, Any], 
                         regime_result: Dict[str, Any]) -> Dict[str, float]:
        """Allocate capital using Bayesian tribunal"""
        
        self.logger.debug("⚖️ Allocating capital via Bayesian tribunal")
        
        try:
            # Convert specialist signals to the format expected by Bayesian tribunal
            # specialist_signals now contains lists of SpecialistSignal objects directly
            tribunal_signals = specialist_signals  # No conversion needed - already in correct format
            current_time = datetime.now()
            
            # Get capital allocations from tribunal
            regime_context = regime_result.get('regime_context')
            if regime_context is None:
                # Create a mock regime context
                regime_context = type('RegimeContext', (), {
                    'regime': regime_result['regime'],
                    'confidence': regime_result['confidence']
                })()
            
            allocations = self.bayesian_tribunal.allocate_capital(
                tribunal_signals, regime_context, current_time
            )
            
            # Convert allocations to simple dict format
            allocation_dict = {}
            for allocation in allocations:
                allocation_dict[allocation.specialist_name] = allocation.allocation_weight
            
            # Apply configuration constraints
            allocation_dict = self._apply_allocation_constraints(allocation_dict)
            
            self.logger.debug(f"✅ Capital allocated across {len(allocation_dict)} specialists")
            
            return allocation_dict
            
        except Exception as e:
            self.logger.error(f"❌ Capital allocation failed: {e}")
            
            # Fallback to equal allocation
            n_specialists = len(specialist_signals)
            if n_specialists > 0:
                equal_weight = 1.0 / n_specialists
                return {name: equal_weight for name in specialist_signals.keys()}
            else:
                return {}
    
    def _apply_allocation_constraints(self, allocations: Dict[str, float]) -> Dict[str, float]:
        """Apply configuration constraints to allocations"""
        
        # Apply min/max constraints
        constrained_allocations = {}
        
        for specialist, allocation in allocations.items():
            constrained_allocation = max(self.config.min_allocation, 
                                       min(self.config.max_allocation, allocation))
            constrained_allocations[specialist] = constrained_allocation
        
        # Renormalize to sum to 1.0
        total_allocation = sum(constrained_allocations.values())
        if total_allocation > 0:
            constrained_allocations = {
                specialist: allocation / total_allocation 
                for specialist, allocation in constrained_allocations.items()
            }
        
        return constrained_allocations
    
    def _size_positions(self, capital_allocations: Dict[str, float], 
                       specialist_signals: Dict[str, Any], 
                       market_data: Dict[str, Any]) -> Dict[str, float]:
        """Size positions using portfolio governor"""
        
        self.logger.debug("📏 Sizing positions via portfolio governor")
        
        try:
            # Convert to format expected by portfolio governor
            current_time = datetime.now()
            
            # Create mock CapitalAllocation objects
            allocation_objects = []
            for specialist_name, allocation in capital_allocations.items():
                mock_allocation = type('CapitalAllocation', (), {
                    'specialist_name': specialist_name,
                    'allocation_weight': allocation,
                    'confidence': 0.8,
                    'timestamp': current_time
                })()
                allocation_objects.append(mock_allocation)
            
            # Convert specialist signals to expected format
            # specialist_signals now contains lists of SpecialistSignal objects directly
            tribunal_signals = {}
            for specialist_name, signal_list in specialist_signals.items():
                tribunal_signals[specialist_name] = signal_list  # signal_list is already a list of SpecialistSignal objects
            
            # Apply portfolio governor
            portfolio_positions = self.portfolio_governor.compute_portfolio_aware_positions(
                allocation_objects, tribunal_signals, market_data, current_time
            )
            
            # Convert to simple dict format
            position_dict = {}
            for position in portfolio_positions:
                position_dict[position.symbol] = position.final_position_size  # Use final_position_size, not weight
            
            self.logger.debug(f"✅ Sized {len(position_dict)} positions")
            
            return position_dict
            
        except Exception as e:
            self.logger.error(f"❌ Position sizing failed: {e}")
            return {}
    
    def _apply_risk_management(self, portfolio_positions: Dict[str, float], 
                             market_data: Dict[str, Any]) -> Dict[str, float]:
        """Apply final risk management and constraints"""
        
        self.logger.debug("🛡️ Applying risk management")
        
        try:
            # Apply portfolio-level constraints
            final_positions = portfolio_positions.copy()
            
            # Ensure cash buffer
            total_weight = sum(abs(weight) for weight in final_positions.values())
            if total_weight > (1.0 - self.config.min_cash_buffer):
                scale_factor = (1.0 - self.config.min_cash_buffer) / total_weight
                final_positions = {stock: weight * scale_factor 
                                 for stock, weight in final_positions.items()}
            
            # Apply individual position limits
            for stock, weight in final_positions.items():
                if abs(weight) > self.config.max_individual_weight:
                    final_positions[stock] = np.sign(weight) * self.config.max_individual_weight
            
            self.logger.debug(f"✅ Risk management applied to {len(final_positions)} positions")
            
            return final_positions
            
        except Exception as e:
            self.logger.error(f"❌ Risk management failed: {e}")
            return portfolio_positions
    
    def _monitor_system_health(self, specialist_signals: Dict[str, Any], 
                             market_data: Dict[str, Any], 
                             capital_allocations: Dict[str, float]):
        """Monitor overall system health"""
        
        self.logger.debug("🏥 Monitoring system health")
        
        try:
            # Prepare data for health monitoring
            specialists_data = {}
            
            for specialist_name, signal_list in specialist_signals.items():
                # signal_list is now a list of SpecialistSignal objects
                if signal_list:
                    avg_regime_fit = np.mean([s.regime_fit for s in signal_list])
                    avg_confidence = np.mean([s.confidence for s in signal_list])
                else:
                    avg_regime_fit = 0.0
                    avg_confidence = 0.0
                
                specialists_data[specialist_name] = {
                    'ic': 0.05,  # Mock IC for now
                    'decay_rate': 0.02,  # Mock decay rate
                    'crowding_index': 0.3,  # Mock crowding
                    'regime_fit': avg_regime_fit,
                    'regime_confidence': market_data.get('regime_confidence', 0.0),
                    'recent_performance': avg_confidence  # Use confidence as performance proxy
                }
            
            # Check for crisis conditions and adjust market data accordingly
            volatility = market_data.get('volatility', 0.15)
            liquidity = market_data.get('liquidity', 0.75)
            
            # Crisis detection: high volatility (>0.3) or low liquidity (<0.3)
            if volatility > 0.3 or liquidity < 0.3:
                # Force crisis-level market data for health monitoring
                crisis_market_data = market_data.copy()
                crisis_market_data['volatility'] = max(volatility, 0.35)  # Ensure high volatility
                crisis_market_data['regime_confidence'] = min(market_data.get('regime_confidence', 50.0), 40.0)  # Low confidence
                
                # Monitor system health with crisis conditions
                system_health = self.real_time_health_monitor.monitor_system_health(
                    specialists_data, crisis_market_data
                )
                
                # Override health status for crisis scenarios
                if system_health.overall_health == "healthy":
                    # Force defensive status during crisis
                    try:
                        from intelligence.real_time_health_monitor import SystemHealthStatus
                    except ImportError:
                        from SystemHealthStatus import SystemHealthStatus
                    system_health = SystemHealthStatus(
                        overall_health="defensive",
                        healthy_specialists=system_health.healthy_specialists,
                        warning_specialists=system_health.warning_specialists,
                        critical_specialists=system_health.critical_specialists,
                        active_alerts=system_health.active_alerts,
                        survival_protocol_active=True,  # Activate survival protocol
                        defensive_mode_active=True,     # Activate defensive mode
                        regime_confidence=crisis_market_data.get('regime_confidence', 40.0),
                        market_volatility_percentile=95.0,  # High volatility percentile
                        timestamp=datetime.now()
                    )
            else:
                # Normal health monitoring
                system_health = self.real_time_health_monitor.monitor_system_health(
                    specialists_data, market_data
                )
            
            return system_health
            
        except Exception as e:
            self.logger.warning(f"⚠️ System health monitoring failed: {e}")
            
            # Return minimal health status
            try:
                from intelligence.real_time_health_monitor import SystemHealthStatus
            except ImportError:
                from SystemHealthStatus import SystemHealthStatus
            return SystemHealthStatus(
                overall_health="unknown",
                healthy_specialists=0,
                warning_specialists=0,
                critical_specialists=0,
                active_alerts=[],
                survival_protocol_active=False,
                defensive_mode_active=False,
                regime_confidence=0.0,
                market_volatility_percentile=50.0,
                timestamp=datetime.now()
            )
    
    def _update_engine_state(self, regime_result: Dict[str, Any], 
                           capital_allocations: Dict[str, float],
                           final_positions: Dict[str, float], 
                           system_health):
        """Update engine state"""
        
        self.state.current_regime = regime_result['regime']
        self.state.regime_confidence = regime_result['confidence']
        self.state.specialist_allocations = capital_allocations
        self.state.portfolio_positions = final_positions
        self.state.health_status = system_health.overall_health
        self.state.last_update = datetime.now()
        self.state.active_alerts = [alert.description for alert in system_health.active_alerts]
        self.state.survival_protocol_active = system_health.survival_protocol_active
        self.state.defensive_mode_active = system_health.defensive_mode_active
    
    def _update_reporting_data(self, specialist_signals: Dict[str, Any], 
                             market_data: Dict[str, Any], 
                             capital_allocations: Dict[str, float]):
        """Update institutional reporting data"""
        
        if not self.institutional_reporter:
            return
        
        try:
            # Prepare reporting data
            specialists_data = {}
            
            for specialist_name, signal_list in specialist_signals.items():
                # signal_list is now a list of SpecialistSignal objects
                if signal_list:
                    avg_regime_fit = np.mean([s.regime_fit for s in signal_list])
                    avg_confidence = np.mean([s.confidence for s in signal_list])
                else:
                    avg_regime_fit = 0.0
                    avg_confidence = 0.0
                
                specialists_data[specialist_name] = {
                    'return': avg_confidence * 0.1,  # Mock return based on confidence
                    'sharpe': avg_confidence * 1.5,  # Mock Sharpe ratio
                    'drawdown': 0.05,  # Mock drawdown
                    'volatility': 0.15,  # Mock volatility
                    'ic': 0.05,  # Mock IC
                    'hit_rate': avg_confidence,  # Use confidence as hit rate proxy
                    'bayesian_data': {
                        'posterior': capital_allocations.get(specialist_name, 0.0),
                        'prior': 0.25,  # Equal prior
                        'likelihood': avg_confidence,  # Use confidence as likelihood proxy
                        'evidence': {
                            'ic_score': 0.05,  # Mock IC
                            'regime_fit': avg_regime_fit,
                            'crowding': 0.3,  # Mock crowding
                            'decay': 0.02  # Mock decay
                        }
                    }
                }
            
            # Record data
            self.institutional_reporter.record_daily_data(
                specialists_data, market_data, capital_allocations
            )
            
        except Exception as e:
            self.logger.warning(f"⚠️ Reporting data update failed: {e}")
    
    def _calculate_performance_metrics(self, positions: Dict[str, float], 
                                     market_data: Dict[str, Any]) -> Dict[str, float]:
        """Calculate performance metrics"""
        
        try:
            if not positions:
                # Handle empty positions case
                return {
                    'total_exposure': 0.0,
                    'long_exposure': 0.0,
                    'short_exposure': 0.0,
                    'net_exposure': 0.0,
                    'position_count': 0,
                    'average_position_size': 0.0
                }
            
            total_exposure = sum(abs(weight) for weight in positions.values())
            long_exposure = sum(max(0, weight) for weight in positions.values())
            short_exposure = sum(min(0, weight) for weight in positions.values())
            
            return {
                'total_exposure': total_exposure,
                'long_exposure': long_exposure,
                'short_exposure': abs(short_exposure),
                'net_exposure': long_exposure + short_exposure,
                'position_count': len(positions),
                'average_position_size': total_exposure / len(positions) if positions else 0.0
            }
            
        except Exception as e:
            self.logger.warning(f"⚠️ Performance metrics calculation failed: {e}")
            return {
                'total_exposure': 0.0,
                'long_exposure': 0.0,
                'short_exposure': 0.0,
                'net_exposure': 0.0,
                'position_count': 0,
                'average_position_size': 0.0
            }
    
    def _generate_fallback_result(self, market_data: Dict[str, Any], 
                                universe: List[str], error_msg: str) -> AlphaGenerationResult:
        """Generate safe fallback result in case of errors"""
        
        self.logger.warning("🚨 Generating fallback result due to error")
        
        return AlphaGenerationResult(
            positions={},  # No positions - safe fallback
            allocations={},
            regime_state=MarketRegime.EXPANSION,
            health_status="error",  # Properly flag error status
            performance_metrics={},
            execution_time=0.0,
            alerts=[f"System error: {error_msg}"],
            metadata={
                'fallback_mode': True,
                'error': error_msg,
                'timestamp': datetime.now().isoformat()
            }
        )
    
    def get_current_state(self) -> AlphaEngineState:
        """Get current engine state"""
        return self.state
    
    def get_configuration(self) -> AlphaEngineConfig:
        """Get current configuration"""
        return self.config
    
    def update_configuration(self, new_config: AlphaEngineConfig):
        """Update engine configuration"""
        self.config = new_config
        self.logger.info("✅ Configuration updated")
    
    def generate_monthly_report(self) -> Dict[str, Any]:
        """Generate monthly institutional report"""
        
        if not self.institutional_reporter:
            self.logger.warning("⚠️ Institutional reporting not enabled")
            return {}
        
        try:
            return self.institutional_reporter.generate_monthly_report()
        except Exception as e:
            self.logger.error(f"❌ Monthly report generation failed: {e}")
            return {}
    
    def run_stress_test(self, test_name: str, test_config: Dict[str, Any]) -> Dict[str, Any]:
        """Run stress test"""
        
        if not self.stress_tester:
            self.logger.warning("⚠️ Stress testing not enabled")
            return {}
        
        try:
            return self.stress_tester.run_stress_test(test_name, test_config)
        except Exception as e:
            self.logger.error(f"❌ Stress test failed: {e}")
            return {}
    
    def validate_economic_causality(self, specialists_data: Optional[Dict[str, Any]] = None, 
                                  market_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Validate economic causality of signals"""
        
        if not self.economic_validator:
            self.logger.warning("⚠️ Economic validation not enabled")
            return {}
        
        try:
            # Use provided data or create mock data for validation
            if specialists_data is None:
                specialists_data = {
                    'momentum': {'ic': 0.05, 'regime_fit': 0.8},
                    'value': {'ic': 0.03, 'regime_fit': 0.7},
                    'quality': {'ic': 0.04, 'regime_fit': 0.9},
                    'macro': {'ic': 0.06, 'regime_fit': 0.8}
                }
            
            if market_data is None:
                market_data = {
                    'regime': 'expansion',
                    'volatility': 0.15,
                    'liquidity': 0.75
                }
            
            return self.economic_validator.validate_all_specialists(specialists_data, market_data)
        except Exception as e:
            self.logger.error(f"❌ Economic validation failed: {e}")
            return {}


def main():
    """Demonstrate Institutional Alpha Engine"""
    
    print("🏛️ INSTITUTIONAL ALPHA ENGINE - LAYER 14")
    print("=" * 70)
    
    # Initialize engine with default configuration
    config = AlphaEngineConfig(
        enable_momentum=True,
        enable_value=True,
        enable_quality=True,
        enable_macro=True,
        enable_institutional_reporting=True,
        log_level="INFO"
    )
    
    engine = InstitutionalAlphaEngine(config)
    
    # Mock market data
    market_data = {
        'regime': 'expansion',
        'regime_confidence': 85.0,
        'volatility': 0.15,
        'liquidity': 0.80,
        'sentiment': 0.65,
        'macro_indicators': {
            'gdp_growth': 0.025,
            'inflation': 0.03,
            'unemployment': 0.04,
            'interest_rates': 0.05
        }
    }
    
    # Mock universe with Indian stocks
    universe = ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'HINDUNILVR.NS', 'ICICIBANK.NS', 'KOTAKBANK.NS', 'BHARTIARTL.NS', 'ITC.NS', 'SBIN.NS']
    
    # Generate alpha positions
    print("\n🚀 Generating alpha positions...")
    result = engine.generate_alpha_positions(market_data, universe)
    
    # Display results
    print(f"\n📊 ALPHA GENERATION RESULTS")
    print("=" * 50)
    print(f"Execution Time: {result.execution_time:.2f}s")
    print(f"Regime: {result.regime_state.value}")
    print(f"Health Status: {result.health_status}")
    print(f"Positions Generated: {len(result.positions)}")
    print(f"Active Alerts: {len(result.alerts)}")
    
    # Show allocations
    if result.allocations:
        print(f"\n💰 SPECIALIST ALLOCATIONS")
        print("-" * 30)
        for specialist, allocation in result.allocations.items():
            print(f"{specialist}: {allocation:.1%}")
    
    # Show top positions
    if result.positions:
        print(f"\n📈 TOP POSITIONS")
        print("-" * 30)
        sorted_positions = sorted(result.positions.items(), 
                                key=lambda x: abs(x[1]), reverse=True)
        for stock, weight in sorted_positions[:5]:
            print(f"{stock}: {weight:.2%}")
    
    # Show performance metrics
    if result.performance_metrics:
        print(f"\n📊 PERFORMANCE METRICS")
        print("-" * 30)
        for metric, value in result.performance_metrics.items():
            if isinstance(value, float):
                print(f"{metric}: {value:.2%}")
            else:
                print(f"{metric}: {value}")
    
    # Show alerts
    if result.alerts:
        print(f"\n⚠️ ACTIVE ALERTS")
        print("-" * 30)
        for alert in result.alerts:
            print(f"• {alert}")
    
    print(f"\n✅ Institutional Alpha Engine demonstration complete")

if __name__ == "__main__":
    main()