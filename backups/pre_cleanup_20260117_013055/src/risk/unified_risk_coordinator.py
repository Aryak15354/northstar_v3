#!/usr/bin/env python3
"""
🛡️ UNIFIED RISK COORDINATOR - NORTHSTAR V3 PHASE 4
Master Risk Management System with Absolute Authority

This is the unified coordinator that orchestrates all risk management
components with absolute authority over portfolio decisions.

Coordinates:
- Emergency Brake (system-level absolute authority)
- Portfolio Risk Controller (dynamic exposure scaling)
- Risk management integration with portfolio construction
- Unified risk state management

Key Principle: ABSOLUTE RISK AUTHORITY
- Risk systems have final say over all portfolio decisions
- No system can override emergency risk signals
- Risk caps are enforced at all levels

Usage:
from src.cohesion.dependency_container import get_dependency_container

    from src.risk.unified_risk_coordinator import UnifiedRiskCoordinator
    
    coordinator = UnifiedRiskCoordinator()
    success = coordinator.apply_unified_risk_management()
"""

import pandas as pd
import numpy as np
import os
import sys
import json
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

# Add project root to path for imports
if project_root not in sys.path:
    class UnifiedRiskCoordinator:
        pass
    """
    Unified Risk Coordinator - Master Risk Management System
    
    Orchestrates all risk management components with absolute authority
    over portfolio decisions and system operations.
    """
    
    def __init__(self):
        self.name = "Unified Risk Coordinator"
        self.version = "1.0"
        
        # File paths
        self.paths = {
            'portfolio_weights': 'data/processed/portfolio_weights.parquet',
            'unified_portfolio': 'data/processed/unified_portfolio.parquet',
            'emergency_signal': 'data/risk/emergency_signal.parquet',
            'risk_state': 'data/risk/unified_risk_state.json',
            'risk_log': 'data/risk/risk_coordination_log.json',
            'market_state': 'data/processed/market_state.parquet'
        }
        
        # Ensure directories exist
        os.makedirs('data/risk', exist_ok=True)
        
        # Initialize components (lazy loading)
        self._emergency_brake = None
        self._portfolio_risk_controller = None
        
        # Risk coordination tracking
        self.risk_log = []
        
        # Risk authority levels
        self.authority_levels = {
            'EMERGENCY': 1,      # Absolute authority - overrides everything
            'SYSTEM': 2,         # System-level authority
            'PORTFOLIO': 3,      # Portfolio-level authority
            'POSITION': 4        # Position-level authority
        }
    
    def log_risk_action(self, component, authority_level, status, message="", duration=0):
        """Log risk management actions with authority levels"""
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'component': component,
            'authority_level': authority_level,
            'status': status,
            'message': message,
            'duration_seconds': duration
        }
        
        self.risk_log.append(entry)
        
        # Print status with authority indicator
        authority_icon = "🚨" if authority_level == 'EMERGENCY' else "🛡️" if authority_level == 'SYSTEM' else "⚖️"
        status_icon = "✅" if status == 'success' else "❌" if status == 'failed' else "⚠️"
        print(f"   {authority_icon} {status_icon} {component}: {message}")
    
    @property
    def emergency_brake(self):
        """Lazy load Emergency Brake Engine"""
        if self._emergency_brake is None:
            # Dependency injection - import EmergencyBrakeEngine from src.risk.emergency_brake
# print(f"⚠️ Emergency Brake not available: {e}")
                self._emergency_brake = None
        return self._emergency_brake
    
    @property
    def portfolio_risk_controller(self):
        """Lazy load Portfolio Risk Controller"""
        if self._portfolio_risk_controller is None:
            # Dependency injection - import PortfolioRiskController from src.risk.portfolio_risk_controller
# print(f"⚠️ Portfolio Risk Controller not available: {e}")
                self._portfolio_risk_controller = None
        return self._portfolio_risk_controller
    
    def run_emergency_brake_check(self):
        """Step 1: Emergency Brake Check - ABSOLUTE AUTHORITY"""
        
        print("🚨 STEP 1: EMERGENCY BRAKE CHECK - ABSOLUTE AUTHORITY")
        print("-" * 55)
        
        start_time = datetime.now()
        
        try:
            if self.emergency_brake:
                # Run emergency brake system
                emergency_state = self.emergency_brake.run()
                
                duration = (datetime.now() - start_time).total_seconds()
                
                if emergency_state:
                    emergency_active = emergency_state.get('emergency_active', False)
                    emergency_cap = emergency_state.get('emergency_cap', 100.0)
                    risk_level = emergency_state.get('risk_level', 0.0)
                    
                    if emergency_active:
                        self.log_risk_action('emergency_brake', 'EMERGENCY', 'active', 
                                           f"EMERGENCY ACTIVE - {emergency_cap:.1f}% exposure cap enforced", 
                                           duration)
                        
                        # ABSOLUTE AUTHORITY: Emergency brake overrides everything
                        return {
                            'emergency_active': True,
                            'emergency_cap': emergency_cap,
                            'risk_level': risk_level,
                            'authority_level': 'EMERGENCY',
                            'override_all': True
                        }
                    else:
                        self.log_risk_action('emergency_brake', 'SYSTEM', 'success', 
                                           f"Emergency brake inactive - normal operations", 
                                           duration)
                        
                        return {
                            'emergency_active': False,
                            'emergency_cap': 100.0,
                            'risk_level': risk_level,
                            'authority_level': 'SYSTEM',
                            'override_all': False
                        }
                else:
                    self.log_risk_action('emergency_brake', 'SYSTEM', 'failed', 
                                       "Emergency brake check failed", duration)
                    
                    # Default to safe state
                    return {
                        'emergency_active': True,
                        'emergency_cap': 50.0,  # Conservative default
                        'risk_level': 1.0,
                        'authority_level': 'EMERGENCY',
                        'override_all': True
                    }
            else:
                self.log_risk_action('emergency_brake', 'SYSTEM', 'failed', 
                                   "Emergency Brake not available", 0)
                
                # Default to safe state when emergency brake unavailable
                return {
                    'emergency_active': True,
                    'emergency_cap': 60.0,  # Conservative when no emergency brake
                    'risk_level': 0.5,
                    'authority_level': 'SYSTEM',
                    'override_all': True
                }
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_risk_action('emergency_brake', 'SYSTEM', 'failed', str(e), duration)
            
            # Default to safe state on error
            return {
                'emergency_active': True,
                'emergency_cap': 50.0,
                'risk_level': 1.0,
                'authority_level': 'EMERGENCY',
                'override_all': True
            }
    
    def run_portfolio_risk_control(self, emergency_state):
        """Step 2: Portfolio Risk Control - Dynamic Exposure Scaling"""
        
        print("\n⚖️ STEP 2: PORTFOLIO RISK CONTROL")
        print("-" * 35)
        
        start_time = datetime.now()
        
        try:
            # Check if emergency brake has absolute authority
            if emergency_state.get('override_all', False):
                self.log_risk_action('portfolio_risk_controller', 'EMERGENCY', 'overridden', 
                                   f"Emergency brake has absolute authority - {emergency_state['emergency_cap']:.1f}% cap", 0)
                
                return {
                    'risk_adjusted_exposure': emergency_state['emergency_cap'] / 100.0,
                    'authority_level': 'EMERGENCY',
                    'overridden_by_emergency': True,
                    'original_emergency_cap': emergency_state['emergency_cap']
                }
            
            # Run portfolio risk controller if no emergency override
            if self.portfolio_risk_controller:
                success = self.portfolio_risk_controller.apply_risk_controls()
                
                duration = (datetime.now() - start_time).total_seconds()
                
                if success:
                    # Load risk control results
                    risk_controls_file = 'data/risk/portfolio_risk_controls.json'
                    if os.path.exists(risk_controls_file):
                        with open(risk_controls_file, 'r') as f:
                            risk_data = json.load(f)
                        
                        target_exposure = risk_data.get('target_exposure', 0.8)
                        
                        # Apply emergency cap if still active (but not overriding)
                        if emergency_state.get('emergency_active', False):
                            emergency_cap = emergency_state['emergency_cap'] / 100.0
                            final_exposure = min(target_exposure, emergency_cap)
                            
                            self.log_risk_action('portfolio_risk_controller', 'PORTFOLIO', 'success', 
                                               f"Risk controls applied: {target_exposure:.1%} → {final_exposure:.1%} (emergency cap)", 
                                               duration)
                        else:
                            final_exposure = target_exposure
                            
                            self.log_risk_action('portfolio_risk_controller', 'PORTFOLIO', 'success', 
                                               f"Risk controls applied: {final_exposure:.1%} exposure", 
                                               duration)
                        
                        return {
                            'risk_adjusted_exposure': final_exposure,
                            'authority_level': 'PORTFOLIO',
                            'overridden_by_emergency': False,
                            'original_target': target_exposure,
                            'emergency_cap_applied': emergency_state.get('emergency_active', False)
                        }
                    else:
                        self.log_risk_action('portfolio_risk_controller', 'PORTFOLIO', 'failed', 
                                           "Risk control results not found", duration)
                else:
                    self.log_risk_action('portfolio_risk_controller', 'PORTFOLIO', 'failed', 
                                       "Portfolio risk control failed", duration)
            else:
                self.log_risk_action('portfolio_risk_controller', 'PORTFOLIO', 'failed', 
                                   "Portfolio Risk Controller not available", 0)
            
            # Fallback to emergency cap or conservative default
            fallback_exposure = emergency_state.get('emergency_cap', 60.0) / 100.0
            
            self.log_risk_action('portfolio_risk_controller', 'SYSTEM', 'fallback', 
                               f"Using fallback exposure: {fallback_exposure:.1%}", 0)
            
            return {
                'risk_adjusted_exposure': fallback_exposure,
                'authority_level': 'SYSTEM',
                'overridden_by_emergency': False,
                'fallback_used': True
            }
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_risk_action('portfolio_risk_controller', 'PORTFOLIO', 'failed', str(e), duration)
            
            # Fallback to emergency cap
            fallback_exposure = emergency_state.get('emergency_cap', 50.0) / 100.0
            return {
                'risk_adjusted_exposure': fallback_exposure,
                'authority_level': 'EMERGENCY',
                'overridden_by_emergency': True,
                'error_fallback': True
            }
    
    def apply_risk_authority_to_portfolio(self, emergency_state, risk_control_state):
        """Step 3: Apply Risk Authority to Portfolio - ENFORCE CAPS"""
        
        print("\n🎯 STEP 3: APPLY RISK AUTHORITY TO PORTFOLIO")
        print("-" * 45)
        
        start_time = datetime.now()
        
        try:
            # Determine which portfolio file to use
            portfolio_file = self.paths['unified_portfolio'] if os.path.exists(self.paths['unified_portfolio']) else self.paths['portfolio_weights']
            
            if not os.path.exists(portfolio_file):
                self.log_risk_action('portfolio_enforcement', 'SYSTEM', 'failed', 
                                   "No portfolio file found to enforce risk caps", 0)
                return False
            
            # Load portfolio
            portfolio_df = pd.read_parquet(portfolio_file)
            
            if portfolio_df.empty:
                self.log_risk_action('portfolio_enforcement', 'SYSTEM', 'success', 
                                   "Empty portfolio - no risk enforcement needed", 0)
                return True
            
            # Get final exposure target from risk authority
            target_exposure = risk_control_state.get('risk_adjusted_exposure', 0.6)
            authority_level = risk_control_state.get('authority_level', 'SYSTEM')
            
            # Calculate current exposure
            current_exposure = portfolio_df['final_weight'].abs().sum()
            
            if current_exposure > 0:
                # Apply risk authority scaling
                scaling_factor = target_exposure / current_exposure
                
                # Scale portfolio weights
                portfolio_df['final_weight'] = portfolio_df['final_weight'] * scaling_factor
                
                # Add risk authority metadata
                portfolio_df['risk_authority_applied'] = True
                portfolio_df['risk_authority_level'] = authority_level
                portfolio_df['risk_scaling_factor'] = scaling_factor
                portfolio_df['risk_target_exposure'] = target_exposure
                portfolio_df['risk_timestamp'] = datetime.now().isoformat()
                
                # Save risk-adjusted portfolio
                portfolio_df.to_parquet(portfolio_file, index=False)
                
                duration = (datetime.now() - start_time).total_seconds()
                
                self.log_risk_action('portfolio_enforcement', authority_level, 'success', 
                                   f"Risk authority enforced: {current_exposure:.1%} → {target_exposure:.1%} ({authority_level})", 
                                   duration)
                
                return True
            else:
                self.log_risk_action('portfolio_enforcement', 'SYSTEM', 'success', 
                                   "Zero exposure portfolio - no scaling needed", 0)
                return True
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_risk_action('portfolio_enforcement', 'SYSTEM', 'failed', str(e), duration)
            return False
    
    def save_unified_risk_state(self, emergency_state, risk_control_state):
        """Step 4: Save Unified Risk State"""
        
        print("\n💾 STEP 4: SAVE UNIFIED RISK STATE")
        print("-" * 35)
        
        start_time = datetime.now()
        
        try:
            # Create unified risk state
            unified_risk_state = {
                'timestamp': datetime.now().isoformat(),
                'coordinator_version': self.version,
                'emergency_state': emergency_state,
                'risk_control_state': risk_control_state,
                'risk_authority': {
                    'active_authority': emergency_state.get('authority_level', 'SYSTEM'),
                    'emergency_override': emergency_state.get('override_all', False),
                    'final_exposure_cap': risk_control_state.get('risk_adjusted_exposure', 0.6),
                    'risk_level': emergency_state.get('risk_level', 0.0)
                },
                'risk_coordination_log': self.risk_log
            }
            
            # Save unified risk state
            with open(self.paths['risk_state'], 'w') as f:
                json.dump(unified_risk_state, f, indent=2, default=str)
            
            # Save risk coordination log
            risk_log_summary = {
                'timestamp': datetime.now().isoformat(),
                'coordinator_version': self.version,
                'risk_log': self.risk_log,
                'emergency_actions': sum(1 for entry in self.risk_log if entry['authority_level'] == 'EMERGENCY'),
                'system_actions': sum(1 for entry in self.risk_log if entry['authority_level'] == 'SYSTEM'),
                'portfolio_actions': sum(1 for entry in self.risk_log if entry['authority_level'] == 'PORTFOLIO'),
                'success_rate': sum(1 for entry in self.risk_log if entry['status'] == 'success') / len(self.risk_log) if self.risk_log else 0,
                'total_duration': sum(entry['duration_seconds'] for entry in self.risk_log)
            }
            
            with open(self.paths['risk_log'], 'w') as f:
                json.dump(risk_log_summary, f, indent=2, default=str)
            
            duration = (datetime.now() - start_time).total_seconds()
            self.log_risk_action('risk_state_save', 'SYSTEM', 'success', 
                               "Unified risk state saved", duration)
            
            return True
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_risk_action('risk_state_save', 'SYSTEM', 'failed', str(e), duration)
            return False
    
    def apply_unified_risk_management(self):
        """Main unified risk management process with absolute authority"""
        
        print("🛡️ UNIFIED RISK COORDINATOR - ABSOLUTE AUTHORITY")
        print("=" * 60)
        
        total_start_time = datetime.now()
        
        # Step 1: Emergency Brake Check (ABSOLUTE AUTHORITY)
        emergency_state = self.run_emergency_brake_check()
        
        # Step 2: Portfolio Risk Control (unless overridden by emergency)
        risk_control_state = self.run_portfolio_risk_control(emergency_state)
        
        # Step 3: Apply Risk Authority to Portfolio (ENFORCE CAPS)
        enforcement_success = self.apply_risk_authority_to_portfolio(emergency_state, risk_control_state)
        
        # Step 4: Save Unified Risk State
        save_success = self.save_unified_risk_state(emergency_state, risk_control_state)
        
        # Calculate results
        total_duration = (datetime.now() - total_start_time).total_seconds()
        successful_steps = sum(1 for entry in self.risk_log if entry['status'] == 'success')
        total_steps = len(self.risk_log)
        
        # Print summary
        print(f"\n🛡️ UNIFIED RISK MANAGEMENT COMPLETE")
        print("=" * 60)
        print(f"Duration: {total_duration:.1f} seconds")
        print(f"Success: {successful_steps}/{total_steps} steps")
        
        # Show risk authority status
        authority_level = emergency_state.get('authority_level', 'SYSTEM')
        final_exposure = risk_control_state.get('risk_adjusted_exposure', 0.6)
        emergency_active = emergency_state.get('emergency_active', False)
        
        print(f"Risk Authority: {authority_level}")
        print(f"Final Exposure Cap: {final_exposure:.1%}")
        print(f"Emergency Status: {'🚨 ACTIVE' if emergency_active else '✅ INACTIVE'}")
        
        return successful_steps >= 2  # At least emergency check and one other step must succeed

def main():
    """Main execution function"""
    
    coordinator = UnifiedRiskCoordinator()
    success = coordinator.apply_unified_risk_management()
    
    return success

if __name__ == "__main__":
    main()