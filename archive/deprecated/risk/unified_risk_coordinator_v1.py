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
from cohesion.dependency_container import get_dependency_container

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

from src.cohesion.state_file_manager import StateFileManager
from src.risk.liquidity_kill_switch import LiquidityRiskAssessor
# Add project root to path for imports
import pathlib
project_root = str(pathlib.Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    sys.path.insert(0, project_root)

class UnifiedRiskCoordinator:
    """
    Unified Risk Coordinator - Master Risk Management System
    
    Orchestrates all risk management components with absolute authority
    over portfolio decisions and system operations.
    """
    
    def __init__(self):
        self.name = "Unified Risk Coordinator"
        self.version = "1.0"
        self.state_manager = StateFileManager()
        
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
        self._liquidity_assessor = None
        
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
        """Lazy load Kill Switch System (Emergency Brake)"""
        if self._emergency_brake is None:
            try:
                from validation.kill_switch_system import KillSwitchSystem
                self._emergency_brake = KillSwitchSystem()
            except Exception as e:
                print(f"⚠️ Kill Switch System not available: {e}")
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

    @property
    def liquidity_assessor(self):
        """Lazy load Liquidity Risk Assessor"""
        if self._liquidity_assessor is None:
            self._liquidity_assessor = LiquidityRiskAssessor()
        return self._liquidity_assessor
    
    def run_emergency_brake_check(self):
        """Step 1: Emergency Brake Check - ABSOLUTE AUTHORITY"""
        
        print("🚨 STEP 1: EMERGENCY BRAKE CHECK - ABSOLUTE AUTHORITY")
        print("-" * 55)
        
        start_time = datetime.now()
        
        try:
            if self.emergency_brake:
                # Run kill switch system (emergency brake)
                risk_state = self.emergency_brake.evaluate_and_apply()
                
                duration = (datetime.now() - start_time).total_seconds()
                
                if risk_state:
                    emergency_active = risk_state.emergency_active
                    exposure_cap = risk_state.exposure_cap * 100.0  # Convert to percentage
                    risk_level = risk_state.risk_level
                    kill_switch = risk_state.kill_switch_triggered
                    
                    if emergency_active:
                        self.log_risk_action('kill_switch_system', 'EMERGENCY', 'active', 
                                           f"KILL SWITCH ACTIVE - {kill_switch}: {exposure_cap:.1f}% exposure cap", 
                                           duration)
                        
                        # ABSOLUTE AUTHORITY: Kill switches override everything
                        return {
                            'emergency_active': True,
                            'emergency_cap': exposure_cap,
                            'risk_level': risk_level,
                            'authority_level': 'EMERGENCY',
                            'override_all': True,
                            'kill_switch_triggered': kill_switch,
                            'kill_switch_reason': risk_state.kill_switch_reason
                        }
                    else:
                        self.log_risk_action('kill_switch_system', 'SYSTEM', 'success', 
                                           f"All kill switches passed - normal operations", 
                                           duration)
                        
                        return {
                            'emergency_active': False,
                            'emergency_cap': 100.0,
                            'risk_level': risk_level,
                            'authority_level': 'SYSTEM',
                            'override_all': False,
                            'kill_switch_triggered': None,
                            'kill_switch_reason': None
                        }
                else:
                    self.log_risk_action('kill_switch_system', 'SYSTEM', 'failed', 
                                       "Kill switch evaluation failed", duration)
                    
                    # Default to safe state
                    return {
                        'emergency_active': True,
                        'emergency_cap': 50.0,  # Conservative default
                        'risk_level': 1.0,
                        'authority_level': 'EMERGENCY',
                        'override_all': True,
                        'kill_switch_triggered': 'SYSTEM_ERROR',
                        'kill_switch_reason': 'Kill switch evaluation failed - defaulting to safe state'
                    }
            else:
                self.log_risk_action('kill_switch_system', 'SYSTEM', 'failed', 
                                   "Kill Switch System not available", 0)
                
                # Default to safe state when kill switches unavailable
                return {
                    'emergency_active': True,
                    'emergency_cap': 60.0,  # Conservative when no kill switches
                    'risk_level': 0.5,
                    'authority_level': 'SYSTEM',
                    'override_all': True,
                    'kill_switch_triggered': 'SYSTEM_UNAVAILABLE',
                    'kill_switch_reason': 'Kill Switch System not available - defaulting to conservative exposure'
                }
                
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.log_risk_action('kill_switch_system', 'SYSTEM', 'failed', str(e), duration)
            
            # Default to safe state on error
            return {
                'emergency_active': True,
                'emergency_cap': 50.0,
                'risk_level': 1.0,
                'authority_level': 'EMERGENCY',
                'override_all': True,
                'kill_switch_triggered': 'SYSTEM_ERROR',
                'kill_switch_reason': f'Kill switch error: {str(e)}'
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
                
                # Save risk-adjusted portfolio (canonical write)
                try:
                    portfolio_df["date"] = pd.to_datetime(datetime.now().date())
                    portfolio_df["symbol"] = portfolio_df.get("ticker", portfolio_df.get("symbol", "")).astype(str)
                    weight_col = "final_weight" if "final_weight" in portfolio_df.columns else "weight"
                    portfolio_df["weight"] = pd.to_numeric(portfolio_df.get(weight_col, 0.0), errors="coerce").fillna(0.0)
                    portfolio_df["exposure"] = portfolio_df["weight"]
                    self.state_manager.write_portfolio_weights(portfolio_df)
                except Exception as e:
                    print(f"⚠️ Canonical portfolio write failed, falling back: {e}")
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

            # Save canonical parquet risk_state for dashboards
            try:
                risk_row = {
                    "date": pd.to_datetime(datetime.now().date()),
                    "volatility": float(risk_control_state.get("volatility", np.nan)),
                    "correlation": float(risk_control_state.get("correlation", np.nan)),
                    "var": float(risk_control_state.get("var", np.nan)),
                }
                self.state_manager.write_risk_state(pd.DataFrame([risk_row]))
            except Exception as e:
                print(f"⚠️ Failed to write canonical risk_state.parquet: {e}")
            
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

        # Step 3: Liquidity Kill Switch assessment (real-data-only)
        liquidity_state = {}
        try:
            df_liq = self.liquidity_assessor.run()
            if df_liq is not None and not df_liq.empty:
                high_risk = df_liq[df_liq["status"].isin(["DANGEROUS", "FROZEN"])]
                high_weight = float(high_risk["weight"].sum()) if not high_risk.empty else 0.0
                liquidity_cap = max(0.2, 1.0 - high_weight)
                risk_control_state["liquidity_cap"] = liquidity_cap
                risk_control_state["liquidity_high_risk_weight"] = high_weight
                risk_control_state["risk_adjusted_exposure"] = min(
                    risk_control_state.get("risk_adjusted_exposure", 0.6), liquidity_cap
                )
                liquidity_state = {
                    "high_risk_weight": high_weight,
                    "liquidity_cap": liquidity_cap,
                    "positions": int(len(df_liq)),
                    "frozen": int((df_liq["status"] == "FROZEN").sum()),
                    "dangerous": int((df_liq["status"] == "DANGEROUS").sum()),
                }
        except Exception as e:
            print(f"⚠️ Liquidity risk assessment failed: {e}")
        
        # Step 4: Apply Risk Authority to Portfolio (ENFORCE CAPS)
        enforcement_success = self.apply_risk_authority_to_portfolio(emergency_state, risk_control_state)
        
        # Step 5: Save Unified Risk State
        if liquidity_state:
            risk_control_state["liquidity_state"] = liquidity_state
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
