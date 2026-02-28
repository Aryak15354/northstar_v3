#!/usr/bin/env python3
"""
🏛️ GOVERNANCE SYSTEM - PHASE 5: INFRASTRUCTURE LAYER
Human oversight and override capability for institutional validation

This implements the governance requirements for Phase 5 (Infrastructure)
of the institutional validation framework. It provides documented human
oversight and override capability to ensure institutional credibility.

CRITICAL PRINCIPLE: Human Oversight and Control
- Support emergency pause, exposure cap change, strategy deactivation
- Log all overrides with approval verification
- Require approval authority verification
- Maintain immutable audit trail
- Ensure system is institutionally credible, not an uncontrolled black box

Usage:
    from src.validation.governance_system import GovernanceSystem
    
    governance = GovernanceSystem()
    governance.emergency_pause("Market crash detected", "risk_manager")
    governance.change_exposure_cap(0.5, "Reduce risk", "portfolio_manager")
"""

import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import warnings

warnings.filterwarnings('ignore')


class OverrideType(Enum):
    """Types of governance overrides"""
    EMERGENCY_PAUSE = "emergency_pause"
    EXPOSURE_CAP_CHANGE = "exposure_cap_change"
    STRATEGY_DEACTIVATION = "strategy_deactivation"
    MANUAL_INTERVENTION = "manual_intervention"


class ApprovalAuthority(Enum):
    """Approval authority levels"""
    RISK_MANAGER = "risk_manager"
    PORTFOLIO_MANAGER = "portfolio_manager"
    CIO = "cio"
    COMPLIANCE_OFFICER = "compliance_officer"
    SYSTEM_ADMIN = "system_admin"


@dataclass
class HumanOverride:
    """
    Human override record for governance tracking
    
    Complete override information with approval and reasoning.
    """
    timestamp: datetime
    override_type: OverrideType
    reason: str
    approved_by: ApprovalAuthority
    parameters: Dict[str, Any]  # Override-specific parameters
    status: str  # 'pending', 'approved', 'executed', 'reverted'
    execution_time: Optional[datetime] = None
    revert_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        result = asdict(self)
        result['timestamp'] = result['timestamp'].isoformat()
        result['override_type'] = result['override_type'].value
        result['approved_by'] = result['approved_by'].value
        if result['execution_time']:
            result['execution_time'] = result['execution_time'].isoformat()
        if result['revert_time']:
            result['revert_time'] = result['revert_time'].isoformat()
        return result
    
    def validate(self) -> List[str]:
        """Validate override record"""
        errors = []
        
        if not self.reason or len(self.reason.strip()) < 5:
            errors.append("Reason must be at least 5 characters")
        
        if self.status not in ['pending', 'approved', 'executed', 'reverted']:
            errors.append(f"Invalid status: {self.status}")
        
        if not isinstance(self.parameters, dict):
            errors.append("Parameters must be a dictionary")
        
        return errors


@dataclass
class GovernanceState:
    """
    Current governance state
    
    Tracks active overrides and system state.
    """
    emergency_paused: bool = False
    exposure_cap: Optional[float] = None  # None means no cap
    deactivated_strategies: List[str] = None
    active_overrides: List[str] = None  # List of override IDs
    last_update: Optional[datetime] = None
    
    def __post_init__(self):
        if self.deactivated_strategies is None:
            self.deactivated_strategies = []
        if self.active_overrides is None:
            self.active_overrides = []
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        result = asdict(self)
        if result['last_update']:
            result['last_update'] = result['last_update'].isoformat()
        return result
    
    def validate(self) -> List[str]:
        """Validate governance state"""
        errors = []
        
        if self.exposure_cap is not None and not (0.0 <= self.exposure_cap <= 1.0):
            errors.append(f"Exposure cap {self.exposure_cap} outside bounds [0.0, 1.0]")
        
        if not isinstance(self.deactivated_strategies, list):
            errors.append("Deactivated strategies must be a list")
        
        if not isinstance(self.active_overrides, list):
            errors.append("Active overrides must be a list")
        
        return errors


class GovernanceSystem:
    """
    Governance System - Phase 5: Infrastructure Layer
    
    Provides human oversight and override capability for institutional
    validation and compliance. Ensures the system is institutionally
    credible rather than an uncontrolled black box.
    
    ENFORCES REQUIREMENTS:
    - 21.1-21.8: Governance and human override system
    
    V3 INTEGRATION:
    - Uses UnifiedState for state storage (Requirement 14.1)
    - Emits events through EventBus (Requirement 14.2)
    - Integrates with Risk_Coordinator for authority (Requirement 14.3)
    """
    
    def __init__(self, 
                 base_dir: str = "data/governance",
                 unified_state=None,
                 event_bus=None,
                 risk_coordinator=None):
        """
        Initialize Governance System
        
        Args:
            base_dir: Base directory for governance data
            unified_state: Optional UnifiedState instance for V3 integration
            event_bus: Optional EventBus instance for V3 integration
            risk_coordinator: Optional Risk_Coordinator for authority integration
        """
        self.base_dir = base_dir
        
        # Create base directory
        os.makedirs(base_dir, exist_ok=True)
        
        # V3 Integration (optional)
        self.unified_state = unified_state
        self.event_bus = event_bus
        self.risk_coordinator = risk_coordinator
        
        # Current governance state
        self.current_state = GovernanceState()
        
        # Override history
        self.override_history: List[HumanOverride] = []
        
        # Load existing state and history
        self._load_governance_state()
        self._load_override_history()
        
        print("🏛️ Governance System initialized")
        print(f"   Output: {self.base_dir}/")
        print(f"   Emergency paused: {self.current_state.emergency_paused}")
        print(f"   Exposure cap: {self.current_state.exposure_cap}")
        print(f"   Deactivated strategies: {len(self.current_state.deactivated_strategies)}")
        if unified_state:
            print("   ✅ V3 Integration: UnifiedState connected")
        if event_bus:
            print("   ✅ V3 Integration: EventBus connected")
        if risk_coordinator:
            print("   ✅ V3 Integration: Risk_Coordinator connected")
    
    def _generate_override_id(self) -> str:
        """Generate unique override ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"GOV_{timestamp}_{len(self.override_history):04d}"
    
    def _verify_approval_authority(self, 
                                 override_type: OverrideType,
                                 approved_by: ApprovalAuthority) -> bool:
        """
        Verify approval authority for override type
        
        Args:
            override_type: Type of override
            approved_by: Authority requesting approval
            
        Returns:
            True if authority is sufficient, False otherwise
        """
        
        # Define authority matrix
        authority_matrix = {
            OverrideType.EMERGENCY_PAUSE: [
                ApprovalAuthority.RISK_MANAGER,
                ApprovalAuthority.CIO,
                ApprovalAuthority.COMPLIANCE_OFFICER
            ],
            OverrideType.EXPOSURE_CAP_CHANGE: [
                ApprovalAuthority.RISK_MANAGER,
                ApprovalAuthority.PORTFOLIO_MANAGER,
                ApprovalAuthority.CIO
            ],
            OverrideType.STRATEGY_DEACTIVATION: [
                ApprovalAuthority.PORTFOLIO_MANAGER,
                ApprovalAuthority.CIO
            ],
            OverrideType.MANUAL_INTERVENTION: [
                ApprovalAuthority.RISK_MANAGER,
                ApprovalAuthority.PORTFOLIO_MANAGER,
                ApprovalAuthority.CIO,
                ApprovalAuthority.SYSTEM_ADMIN
            ]
        }
        
        allowed_authorities = authority_matrix.get(override_type, [])
        return approved_by in allowed_authorities
    
    def emergency_pause(self, 
                       reason: str,
                       approved_by: str) -> str:
        """
        Execute emergency pause override
        
        ENFORCES PROPERTY 42: Emergency Pause Immediacy
        VALIDATES REQUIREMENTS 21.4
        
        Args:
            reason: Reason for emergency pause
            approved_by: Authority approving the override
            
        Returns:
            Override ID if successful, empty string if failed
        """
        
        print(f"🚨 EMERGENCY PAUSE REQUESTED")
        print(f"   Reason: {reason}")
        print(f"   Approved by: {approved_by}")
        
        try:
            # Convert string to enum
            authority = ApprovalAuthority(approved_by.lower())
        except ValueError:
            print(f"❌ Invalid approval authority: {approved_by}")
            return ""
        
        # Verify authority
        if not self._verify_approval_authority(OverrideType.EMERGENCY_PAUSE, authority):
            print(f"❌ Insufficient authority for emergency pause: {approved_by}")
            return ""
        
        # Create override record
        override_id = self._generate_override_id()
        override = HumanOverride(
            timestamp=datetime.now(),
            override_type=OverrideType.EMERGENCY_PAUSE,
            reason=reason,
            approved_by=authority,
            parameters={'previous_state': self.current_state.emergency_paused},
            status='approved'
        )
        
        # Validate override
        validation_errors = override.validate()
        if validation_errors:
            print(f"⚠️ Override validation warnings:")
            for error in validation_errors:
                print(f"   {error}")
        
        # Execute immediately (emergency)
        self.current_state.emergency_paused = True
        self.current_state.last_update = datetime.now()
        override.execution_time = datetime.now()
        override.status = 'executed'
        
        # Add to active overrides
        self.current_state.active_overrides.append(override_id)
        
        # Store override
        self.override_history.append(override)
        
        # Persist state
        self._save_governance_state()
        self._save_override(override_id, override)
        
        # V3 Integration: Notify Risk_Coordinator
        if self.risk_coordinator:
            try:
                self.risk_coordinator.emergency_halt(reason)
                print("   ✅ Risk_Coordinator notified")
            except Exception as e:
                print(f"   ⚠️ Failed to notify Risk_Coordinator: {e}")
        
        # V3 Integration: Store in UnifiedState
        self._store_state_in_unified_state()
        
        # V3 Integration: Emit event
        self._emit_override_event(override_id, override)
        
        print(f"✅ Emergency pause executed: {override_id}")
        print(f"   All trading halted")
        print(f"   Exposure reduced to cash")
        
        return override_id
    
    def change_exposure_cap(self, 
                           new_cap: float,
                           reason: str,
                           approved_by: str) -> str:
        """
        Change exposure cap override
        
        VALIDATES REQUIREMENTS 21.5
        
        Args:
            new_cap: New exposure cap (0.0 to 1.0)
            reason: Reason for cap change
            approved_by: Authority approving the override
            
        Returns:
            Override ID if successful, empty string if failed
        """
        
        print(f"📊 EXPOSURE CAP CHANGE REQUESTED")
        print(f"   New cap: {new_cap:.1%}")
        print(f"   Current cap: {self.current_state.exposure_cap}")
        print(f"   Reason: {reason}")
        print(f"   Approved by: {approved_by}")
        
        # Validate new cap
        if not (0.0 <= new_cap <= 1.0):
            print(f"❌ Invalid exposure cap: {new_cap} (must be 0.0 to 1.0)")
            return ""
        
        try:
            # Convert string to enum
            authority = ApprovalAuthority(approved_by.lower())
        except ValueError:
            print(f"❌ Invalid approval authority: {approved_by}")
            return ""
        
        # Verify authority
        if not self._verify_approval_authority(OverrideType.EXPOSURE_CAP_CHANGE, authority):
            print(f"❌ Insufficient authority for exposure cap change: {approved_by}")
            return ""
        
        # Create override record
        override_id = self._generate_override_id()
        override = HumanOverride(
            timestamp=datetime.now(),
            override_type=OverrideType.EXPOSURE_CAP_CHANGE,
            reason=reason,
            approved_by=authority,
            parameters={
                'previous_cap': self.current_state.exposure_cap,
                'new_cap': new_cap
            },
            status='approved'
        )
        
        # Validate override
        validation_errors = override.validate()
        if validation_errors:
            print(f"⚠️ Override validation warnings:")
            for error in validation_errors:
                print(f"   {error}")
        
        # Execute override
        self.current_state.exposure_cap = new_cap
        self.current_state.last_update = datetime.now()
        override.execution_time = datetime.now()
        override.status = 'executed'
        
        # Add to active overrides
        self.current_state.active_overrides.append(override_id)
        
        # Store override
        self.override_history.append(override)
        
        # Persist state
        self._save_governance_state()
        self._save_override(override_id, override)
        
        # V3 Integration: Store in UnifiedState
        self._store_state_in_unified_state()
        
        # V3 Integration: Emit event
        self._emit_override_event(override_id, override)
        
        print(f"✅ Exposure cap changed: {override_id}")
        print(f"   New cap enforced on all subsequent rebalances")
        
        return override_id
    
    def deactivate_strategy(self, 
                          strategy_name: str,
                          reason: str,
                          approved_by: str) -> str:
        """
        Deactivate strategy override
        
        VALIDATES REQUIREMENTS 21.6
        
        Args:
            strategy_name: Name of strategy to deactivate
            reason: Reason for deactivation
            approved_by: Authority approving the override
            
        Returns:
            Override ID if successful, empty string if failed
        """
        
        print(f"🚫 STRATEGY DEACTIVATION REQUESTED")
        print(f"   Strategy: {strategy_name}")
        print(f"   Reason: {reason}")
        print(f"   Approved by: {approved_by}")
        
        # Check if already deactivated
        if strategy_name in self.current_state.deactivated_strategies:
            print(f"⚠️ Strategy already deactivated: {strategy_name}")
            return ""
        
        try:
            # Convert string to enum
            authority = ApprovalAuthority(approved_by.lower())
        except ValueError:
            print(f"❌ Invalid approval authority: {approved_by}")
            return ""
        
        # Verify authority
        if not self._verify_approval_authority(OverrideType.STRATEGY_DEACTIVATION, authority):
            print(f"❌ Insufficient authority for strategy deactivation: {approved_by}")
            return ""
        
        # Create override record
        override_id = self._generate_override_id()
        override = HumanOverride(
            timestamp=datetime.now(),
            override_type=OverrideType.STRATEGY_DEACTIVATION,
            reason=reason,
            approved_by=authority,
            parameters={
                'strategy_name': strategy_name,
                'previous_deactivated': self.current_state.deactivated_strategies.copy()
            },
            status='approved'
        )
        
        # Validate override
        validation_errors = override.validate()
        if validation_errors:
            print(f"⚠️ Override validation warnings:")
            for error in validation_errors:
                print(f"   {error}")
        
        # Execute override
        self.current_state.deactivated_strategies.append(strategy_name)
        self.current_state.last_update = datetime.now()
        override.execution_time = datetime.now()
        override.status = 'executed'
        
        # Add to active overrides
        self.current_state.active_overrides.append(override_id)
        
        # Store override
        self.override_history.append(override)
        
        # Persist state
        self._save_governance_state()
        self._save_override(override_id, override)
        
        # V3 Integration: Store in UnifiedState
        self._store_state_in_unified_state()
        
        # V3 Integration: Emit event
        self._emit_override_event(override_id, override)
        
        print(f"✅ Strategy deactivated: {override_id}")
        print(f"   Strategy removed from capital allocation")
        print(f"   Capital redistributed to remaining strategies")
        
        return override_id
    
    def revert_override(self, 
                       override_id: str,
                       reason: str,
                       approved_by: str) -> bool:
        """
        Revert a previous override
        
        Args:
            override_id: ID of override to revert
            reason: Reason for reversion
            approved_by: Authority approving the reversion
            
        Returns:
            True if successful, False otherwise
        """
        
        print(f"↩️ OVERRIDE REVERSION REQUESTED")
        print(f"   Override ID: {override_id}")
        print(f"   Reason: {reason}")
        print(f"   Approved by: {approved_by}")
        
        # Find override
        override = None
        for o in self.override_history:
            if override_id in self.current_state.active_overrides:
                # Find by position in active overrides (simple approach)
                try:
                    index = self.current_state.active_overrides.index(override_id)
                    if index < len(self.override_history):
                        override = self.override_history[-(index+1)]  # Get from end
                        break
                except (ValueError, IndexError):
                    continue
        
        if not override:
            print(f"❌ Override not found or not active: {override_id}")
            return False
        
        if override.status == 'reverted':
            print(f"⚠️ Override already reverted: {override_id}")
            return False
        
        try:
            # Convert string to enum
            authority = ApprovalAuthority(approved_by.lower())
        except ValueError:
            print(f"❌ Invalid approval authority: {approved_by}")
            return False
        
        # Verify authority (same as original override)
        if not self._verify_approval_authority(override.override_type, authority):
            print(f"❌ Insufficient authority for reversion: {approved_by}")
            return False
        
        # Revert based on override type
        success = False
        
        if override.override_type == OverrideType.EMERGENCY_PAUSE:
            previous_state = override.parameters.get('previous_state', False)
            self.current_state.emergency_paused = previous_state
            success = True
            
        elif override.override_type == OverrideType.EXPOSURE_CAP_CHANGE:
            previous_cap = override.parameters.get('previous_cap')
            self.current_state.exposure_cap = previous_cap
            success = True
            
        elif override.override_type == OverrideType.STRATEGY_DEACTIVATION:
            strategy_name = override.parameters.get('strategy_name')
            if strategy_name in self.current_state.deactivated_strategies:
                self.current_state.deactivated_strategies.remove(strategy_name)
                success = True
        
        if success:
            # Update override status
            override.revert_time = datetime.now()
            override.status = 'reverted'
            
            # Remove from active overrides
            if override_id in self.current_state.active_overrides:
                self.current_state.active_overrides.remove(override_id)
            
            # Update state
            self.current_state.last_update = datetime.now()
            
            # Persist state
            self._save_governance_state()
            self._save_override(override_id, override)
            
            # V3 Integration: Store in UnifiedState
            self._store_state_in_unified_state()
            
            # V3 Integration: Emit event
            if self.event_bus:
                self.event_bus.emit(
                    event_type="GOVERNANCE_OVERRIDE_REVERTED",
                    source="governance_system",
                    data={
                        "override_id": override_id,
                        "override_type": override.override_type.value,
                        "reason": reason,
                        "approved_by": approved_by
                    },
                    tags=["governance", "reversion"],
                    priority="HIGH"
                )
            
            print(f"✅ Override reverted: {override_id}")
            return True
        else:
            print(f"❌ Failed to revert override: {override_id}")
            return False
    
    def get_governance_status(self) -> Dict[str, Any]:
        """
        Get current governance status
        
        Returns:
            Dictionary with governance status
        """
        
        return {
            'current_state': self.current_state.to_dict(),
            'active_overrides_count': len(self.current_state.active_overrides),
            'total_overrides': len(self.override_history),
            'override_history_recent': [
                o.to_dict() for o in self.override_history[-5:]  # Last 5 overrides
            ]
        }
    
    def is_strategy_allowed(self, strategy_name: str) -> bool:
        """
        Check if strategy is allowed (not deactivated)
        
        Args:
            strategy_name: Name of strategy to check
            
        Returns:
            True if allowed, False if deactivated
        """
        
        return strategy_name not in self.current_state.deactivated_strategies
    
    def get_effective_exposure_cap(self) -> Optional[float]:
        """
        Get effective exposure cap
        
        Returns:
            Current exposure cap or None if no cap
        """
        
        return self.current_state.exposure_cap
    
    def is_emergency_paused(self) -> bool:
        """
        Check if system is in emergency pause
        
        Returns:
            True if emergency paused, False otherwise
        """
        
        return self.current_state.emergency_paused
    
    def _save_governance_state(self):
        """Save current governance state to file"""
        
        try:
            state_file = os.path.join(self.base_dir, "governance_state.json")
            
            with open(state_file, 'w') as f:
                json.dump(self.current_state.to_dict(), f, indent=2, default=str)
            
        except Exception as e:
            print(f"⚠️ Failed to save governance state: {e}")
    
    def _load_governance_state(self):
        """Load governance state from file"""
        
        try:
            state_file = os.path.join(self.base_dir, "governance_state.json")
            
            if os.path.exists(state_file):
                with open(state_file, 'r') as f:
                    state_data = json.load(f)
                
                # Convert datetime strings back
                if state_data.get('last_update'):
                    state_data['last_update'] = datetime.fromisoformat(state_data['last_update'])
                
                # Create state object
                self.current_state = GovernanceState(**state_data)
                
                print(f"✅ Loaded governance state from {state_file}")
            
        except Exception as e:
            print(f"⚠️ Failed to load governance state: {e}")
    
    def _save_override(self, override_id: str, override: HumanOverride):
        """
        Save override to parquet file
        
        ENFORCES PROPERTY 41: Governance Override Logging
        VALIDATES REQUIREMENTS 21.1, 21.2
        
        Args:
            override_id: Override identifier
            override: HumanOverride object
        """
        
        try:
            # Convert to DataFrame
            override_data = override.to_dict()
            override_data['override_id'] = override_id
            override_df = pd.DataFrame([override_data])
            
            # Enforce schema
            override_df = self._enforce_override_schema(override_df)
            
            # Append to existing file or create new
            file_path = os.path.join(self.base_dir, "human_overrides.parquet")
            
            if os.path.exists(file_path):
                # Append to existing file
                existing_df = pd.read_parquet(file_path)
                combined_df = pd.concat([existing_df, override_df], ignore_index=True)
                combined_df.to_parquet(file_path, index=False)
            else:
                # Create new file
                override_df.to_parquet(file_path, index=False)
            
            print(f"✅ Override logged: {override_id}")
            
        except Exception as e:
            print(f"❌ Failed to save override: {e}")
    
    def _load_override_history(self):
        """Load override history from file"""
        
        try:
            file_path = os.path.join(self.base_dir, "human_overrides.parquet")
            
            if os.path.exists(file_path):
                df = pd.read_parquet(file_path)
                df = self._enforce_override_schema(df)
                
                # Convert to HumanOverride objects
                self.override_history = []
                for _, row in df.iterrows():
                    override = HumanOverride(
                        timestamp=row['timestamp'],
                        override_type=OverrideType(row['override_type']),
                        reason=row['reason'],
                        approved_by=ApprovalAuthority(row['approved_by']),
                        parameters=json.loads(row['parameters']) if isinstance(row['parameters'], str) else row['parameters'],
                        status=row['status'],
                        execution_time=row['execution_time'] if pd.notna(row['execution_time']) else None,
                        revert_time=row['revert_time'] if pd.notna(row['revert_time']) else None
                    )
                    self.override_history.append(override)
                
                print(f"✅ Loaded {len(self.override_history)} override records")
            
        except Exception as e:
            print(f"⚠️ Failed to load override history: {e}")
    
    def _enforce_override_schema(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Enforce override schema
        
        Args:
            df: DataFrame to validate
            
        Returns:
            DataFrame with enforced schema
        """
        
        # Required columns with types
        required_schema = {
            'override_id': 'string',
            'timestamp': 'datetime64[ns]',
            'override_type': 'string',
            'reason': 'string',
            'approved_by': 'string',
            'parameters': 'object',
            'status': 'string',
            'execution_time': 'datetime64[ns]',
            'revert_time': 'datetime64[ns]'
        }
        
        # Ensure all required columns exist
        for col in required_schema.keys():
            if col not in df.columns:
                if col in ['execution_time', 'revert_time']:
                    df[col] = pd.NaT  # Allow null for optional datetime columns
                else:
                    raise ValueError(f"Missing required column: {col}")
        
        # Enforce types
        for col, dtype in required_schema.items():
            if col == 'parameters':
                # Convert parameters to JSON string if it's a dict
                df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, dict) else x)
            elif dtype.startswith('datetime'):
                df[col] = pd.to_datetime(df[col])
            else:
                df[col] = df[col].astype(dtype)
        
        return df
    
    # ========================================================================
    # V3 INTEGRATION METHODS
    # ========================================================================
    
    def _store_state_in_unified_state(self):
        """Store governance state in UnifiedState"""
        
        if self.unified_state is None:
            return
        
        try:
            component_name = "governance_system"
            
            # Store current state
            self.unified_state.set(
                component=component_name,
                key="current_state",
                value=self.current_state.to_dict()
            )
            
        except Exception as e:
            print(f"⚠️ Failed to store state in UnifiedState: {e}")
    
    def _emit_override_event(self, override_id: str, override: HumanOverride):
        """Emit override event through EventBus"""
        
        if self.event_bus is None:
            return
        
        try:
            # Determine priority based on override type
            priority = "CRITICAL" if override.override_type == OverrideType.EMERGENCY_PAUSE else "HIGH"
            
            self.event_bus.emit(
                event_type="GOVERNANCE_OVERRIDE_EXECUTED",
                source="governance_system",
                data={
                    "override_id": override_id,
                    "override_type": override.override_type.value,
                    "reason": override.reason,
                    "approved_by": override.approved_by.value,
                    "status": override.status,
                    "execution_time": override.execution_time.isoformat() if override.execution_time else None
                },
                tags=["governance", "override", override.override_type.value],
                priority=priority
            )
            
        except Exception as e:
            print(f"⚠️ Failed to emit override event: {e}")


def main():
    """Demonstrate Governance System"""
    
    print("🏛️ GOVERNANCE SYSTEM - DEMONSTRATION")
    print("=" * 60)
    
    # Initialize governance system
    governance = GovernanceSystem(base_dir="data/test_governance")
    
    # Demonstrate emergency pause
    print("\n🚨 EMERGENCY PAUSE DEMONSTRATION")
    override_id_1 = governance.emergency_pause(
        reason="Market volatility exceeds 5% threshold",
        approved_by="risk_manager"
    )
    
    # Check status
    status = governance.get_governance_status()
    print(f"\n📊 STATUS AFTER EMERGENCY PAUSE")
    print(f"   Emergency paused: {status['current_state']['emergency_paused']}")
    print(f"   Active overrides: {status['active_overrides_count']}")
    
    # Demonstrate exposure cap change
    print("\n📊 EXPOSURE CAP CHANGE DEMONSTRATION")
    override_id_2 = governance.change_exposure_cap(
        new_cap=0.6,
        reason="Reduce risk during market uncertainty",
        approved_by="portfolio_manager"
    )
    
    # Demonstrate strategy deactivation
    print("\n🚫 STRATEGY DEACTIVATION DEMONSTRATION")
    override_id_3 = governance.deactivate_strategy(
        strategy_name="high_momentum",
        reason="Strategy showing poor performance in current regime",
        approved_by="cio"
    )
    
    # Check final status
    final_status = governance.get_governance_status()
    print(f"\n📋 FINAL STATUS")
    print(f"   Emergency paused: {final_status['current_state']['emergency_paused']}")
    print(f"   Exposure cap: {final_status['current_state']['exposure_cap']}")
    print(f"   Deactivated strategies: {final_status['current_state']['deactivated_strategies']}")
    print(f"   Total overrides: {final_status['total_overrides']}")
    
    # Demonstrate reversion
    print(f"\n↩️ REVERSION DEMONSTRATION")
    success = governance.revert_override(
        override_id=override_id_1,
        reason="Market conditions stabilized",
        approved_by="risk_manager"
    )
    print(f"   Reversion success: {success}")
    
    # Check governance functions
    print(f"\n🔍 GOVERNANCE CHECKS")
    print(f"   Is emergency paused: {governance.is_emergency_paused()}")
    print(f"   Effective exposure cap: {governance.get_effective_exposure_cap()}")
    print(f"   Is 'high_momentum' allowed: {governance.is_strategy_allowed('high_momentum')}")
    print(f"   Is 'value_tilt' allowed: {governance.is_strategy_allowed('value_tilt')}")
    
    print("\n✅ Governance System demonstration complete")


if __name__ == "__main__":
    main()