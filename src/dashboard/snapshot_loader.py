#!/usr/bin/env python3
"""
Dashboard Snapshot Loader - Immutable Data Access for Constitutional Cockpit

This module provides read-only access to immutable system snapshots for the
constitutional cockpit. All data is frozen and timestamped to prevent any
possibility of decision influence.

CRITICAL DESIGN PRINCIPLES:
1. All snapshots are immutable (frozen dataclasses)
2. All data is lagged by minimum 1 hour
3. No current positions or live P&L access
4. Hash verification for data integrity
5. Complete audit trail of access
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union
import os
import json
import hashlib
import time
import warnings
warnings.filterwarnings('ignore')

@dataclass(frozen=True)
class SystemStateView:
    """Immutable system state view for dashboard"""
    timestamp: datetime
    
    # System Health
    system_status: str  # healthy, degraded, critical, emergency
    organs_healthy: int
    organs_total: int
    
    # Current Regime (lagged)
    current_regime: str  # SUPPORTIVE, HOSTILE, PANIC
    regime_confidence: float
    regime_duration_days: int
    last_regime_change: Optional[datetime]
    
    # Active Engine (lagged)
    active_engine: str  # trend, crisis, none
    engine_confidence: float
    
    # Exposure State (lagged)
    exposure_state: str  # RISK_OFF, NEUTRAL, RISK_ON
    allowed_exposure: float
    
    # Conviction Contract Status
    conviction_locked: bool
    conviction_violations: int
    available: bool = True
    unavailable_reason: Optional[str] = None
    
    def __post_init__(self):
        """Validate system state view"""
        assert self.system_status in ['healthy', 'degraded', 'critical', 'emergency']
        assert self.current_regime in ['SUPPORTIVE', 'HOSTILE', 'PANIC', 'UNKNOWN']
        assert self.active_engine in ['trend', 'crisis', 'none']
        assert self.exposure_state in ['RISK_OFF', 'NEUTRAL', 'RISK_ON']
        assert 0.0 <= self.regime_confidence <= 1.0
        assert 0.0 <= self.engine_confidence <= 1.0
        assert 0.0 <= self.allowed_exposure <= 1.0

@dataclass(frozen=True)
class RiskStateView:
    """Immutable risk state view for dashboard"""
    timestamp: datetime
    
    # Emergency Brake Status
    emergency_brake_status: str  # ARMED, DISARMED
    emergency_active: bool
    
    # Drawdown vs Covenant
    current_drawdown: float
    max_allowed_drawdown: float
    drawdown_covenant_ratio: float
    
    # Kill Switch Status
    kill_switches_armed: int
    kill_switches_total: int
    last_kill_switch_activation: Optional[datetime]
    
    # Volatility Stress Level
    volatility_stress: str  # low, medium, high, extreme
    volatility_20d: float
    
    # Last Risk Intervention
    last_intervention: Optional[datetime]
    intervention_type: Optional[str]
    available: bool = True
    unavailable_reason: Optional[str] = None
    
    def __post_init__(self):
        """Validate risk state view"""
        assert self.emergency_brake_status in ['ARMED', 'DISARMED']
        assert self.volatility_stress in ['low', 'medium', 'high', 'extreme']
        assert self.current_drawdown <= 0.0  # Drawdown is negative
        assert self.max_allowed_drawdown <= 0.0
        assert 0.0 <= self.drawdown_covenant_ratio <= 2.0

@dataclass(frozen=True)
class EngineStateView:
    """Immutable engine state view for dashboard"""
    timestamp: datetime
    
    # Trend Engine Behavior
    trend_engine_active: bool
    trend_engine_days_active: int
    trend_holding_duration_avg: float
    trend_recent_exits: List[str]  # structural reasons only
    
    # Crisis Engine Behavior
    crisis_engine_active: bool
    crisis_engine_days_active: int
    crisis_convexity_score: float
    crisis_bleed_vs_payout: float  # historical ratio
    
    # Engine Coordination
    engine_conflicts: int  # should always be 0
    regime_engine_alignment: float  # how well engines match regime
    available: bool = True
    unavailable_reason: Optional[str] = None
    
    def __post_init__(self):
        """Validate engine state view"""
        assert not (self.trend_engine_active and self.crisis_engine_active)  # Never both active
        assert 0.0 <= self.crisis_convexity_score <= 1.0
        assert 0.0 <= self.regime_engine_alignment <= 1.0
        assert self.engine_conflicts == 0  # Must be zero

@dataclass(frozen=True)
class ValidationStateView:
    """Immutable validation state view for dashboard"""
    timestamp: datetime
    
    # Walk-Forward Validation
    last_walkforward_result: str  # PASS, FAIL, PENDING
    last_walkforward_date: Optional[datetime]
    walkforward_success_rate: float
    
    # Rules Hash (system integrity)
    current_rules_hash: str
    rules_hash_verified: bool
    
    # Override Attempts (should be 0)
    override_attempts_24h: int
    override_attempts_total: int
    
    # Data Integrity (5-layer checklist)
    data_integrity_layers: Dict[str, bool]  # 5 layers: ingestion, processing, validation, storage, access
    data_integrity_score: float
    available: bool = True
    unavailable_reason: Optional[str] = None
    
    def __post_init__(self):
        """Validate validation state view"""
        assert self.last_walkforward_result in ['PASS', 'FAIL', 'PENDING']
        assert 0.0 <= self.walkforward_success_rate <= 1.0
        assert self.override_attempts_24h == 0  # Should be zero
        assert len(self.data_integrity_layers) == 5
        assert 0.0 <= self.data_integrity_score <= 1.0

@dataclass(frozen=True)
class IntelligenceStateView:
    """Immutable intelligence state view for dashboard"""
    timestamp: datetime
    
    # Intelligence Scores (quiet, non-actionable)
    regime_similarity_index: float  # 0-100
    stress_clustering_index: float  # 0-100
    false_calm_likelihood: float   # 0-100
    behavioral_drift_index: float  # 0-100
    
    # Intelligence Metadata
    intelligence_confidence: float
    last_intelligence_update: Optional[datetime]
    
    # Weekly Report Status
    weekly_report_available: bool
    weekly_report_path: Optional[str]
    
    # Observer Status
    observer_healthy: bool
    observer_violations: int
    observer_suspended: bool
    available: bool = True
    unavailable_reason: Optional[str] = None
    
    def __post_init__(self):
        """Validate intelligence state view"""
        assert 0.0 <= self.regime_similarity_index <= 100.0
        assert 0.0 <= self.stress_clustering_index <= 100.0
        assert 0.0 <= self.false_calm_likelihood <= 100.0
        assert 0.0 <= self.behavioral_drift_index <= 100.0
        assert 0.0 <= self.intelligence_confidence <= 1.0

@dataclass(frozen=True)
class DashboardSnapshot:
    """
    Complete immutable dashboard snapshot
    
    This is the ONLY data the constitutional cockpit is allowed to see.
    All data is historical/lagged - no live positions or real-time P&L.
    """
    snapshot_id: str
    creation_time: datetime
    data_cutoff_time: datetime  # All data is before this time
    
    # 5 Panel Views (immutable)
    system_state: SystemStateView
    risk_state: RiskStateView
    engine_state: EngineStateView
    validation_state: ValidationStateView
    intelligence_state: IntelligenceStateView
    
    # Metadata
    data_quality_score: float
    completeness_score: float
    staleness_hours: float
    snapshot_hash: str
    
    def __post_init__(self):
        """Validate dashboard snapshot integrity"""
        # Ensure all timestamps are consistent
        assert self.creation_time >= self.data_cutoff_time
        assert self.system_state.timestamp <= self.data_cutoff_time
        assert self.risk_state.timestamp <= self.data_cutoff_time
        assert self.engine_state.timestamp <= self.data_cutoff_time
        assert self.validation_state.timestamp <= self.data_cutoff_time
        assert self.intelligence_state.timestamp <= self.data_cutoff_time
        
        # Ensure data quality
        assert 0.0 <= self.data_quality_score <= 1.0
        assert 0.0 <= self.completeness_score <= 1.0
        assert self.staleness_hours >= 0.5  # Minimum 30 minutes for testing
    
    def verify_hash(self) -> bool:
        """Verify snapshot hash integrity"""
        computed_hash = self._compute_hash()
        return computed_hash == self.snapshot_hash
    
    def _compute_hash(self) -> str:
        """Compute snapshot hash for integrity verification"""
        snapshot_data = {
            'snapshot_id': self.snapshot_id,
            'creation_time': self.creation_time.isoformat(),
            'data_cutoff_time': self.data_cutoff_time.isoformat(),
            'system_state': self.system_state.__dict__,
            'risk_state': self.risk_state.__dict__,
            'engine_state': self.engine_state.__dict__,
            'validation_state': self.validation_state.__dict__,
            'intelligence_state': self.intelligence_state.__dict__
        }
        
        snapshot_json = json.dumps(snapshot_data, sort_keys=True, default=str)
        return hashlib.sha256(snapshot_json.encode()).hexdigest()

class DashboardSnapshotLoader:
    """
    Dashboard Snapshot Loader - Provides immutable snapshots for constitutional cockpit
    
    This class loads and validates immutable system snapshots for dashboard display.
    All data is lagged and aggregated to prevent any possibility of decision influence.
    """
    
    def __init__(self):
        self.name = "Dashboard Snapshot Loader"
        self.version = "1.0.0"
        
        # Data paths (read-only)
        self.data_paths = {
            'system_state': 'data/state/unified_state.json',
            'risk_state': 'data/risk/risk_state.parquet',
            'engine_decisions': 'data/intelligence/engine_decisions.parquet',
            'validation_results': 'data/validation/validation_summary.json',
            'intelligence_observer': 'data/intelligence/observer/snapshots/',
            'performance_history': 'data/processed/performance_summary.parquet'
        }
        
        # Snapshot cache
        self.snapshot_cache = {}
        self.cache_ttl_minutes = 5  # Cache snapshots for 5 minutes
        self._load_requests = 0
        self._cache_hits = 0
        self._load_durations_seconds: List[float] = []
        
        # Access audit
        self.access_log = []
        
        print(f"📸 {self.name} v{self.version} - Immutable Snapshot Loading")

    @staticmethod
    def _project_root() -> str:
        return os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            parsed = float(value)
        except Exception:
            return float(default)
        return float(parsed) if np.isfinite(parsed) else float(default)

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return int(default)

    @staticmethod
    def _safe_bool(value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "y"}:
                return True
            if lowered in {"false", "0", "no", "n"}:
                return False
        if value is None:
            return bool(default)
        return bool(value)

    @staticmethod
    def _safe_datetime(value: Any) -> Optional[datetime]:
        if value in (None, "", "None", "NaT"):
            return None
        try:
            dt = pd.to_datetime(value, errors="coerce")
        except Exception:
            return None
        if pd.isna(dt):
            return None
        if getattr(dt, "tzinfo", None) is not None:
            try:
                dt = dt.tz_localize(None)
            except TypeError:
                dt = dt.tz_convert(None)
        return dt.to_pydatetime()

    @staticmethod
    def _normalize_system_status(value: Any) -> str:
        raw = str(value or "").strip().lower()
        if raw in {"healthy", "good", "ok", "green"}:
            return "healthy"
        if raw in {"critical", "red", "failed"}:
            return "critical"
        if raw in {"emergency", "halted"}:
            return "emergency"
        if raw in {"degraded", "warning", "warn", "amber", "partial"}:
            return "degraded"
        return "degraded"

    @staticmethod
    def _normalize_dashboard_regime(value: Any) -> str:
        raw = str(value or "").strip().lower()
        if not raw:
            return "UNKNOWN"
        if any(token in raw for token in ("panic", "crisis", "crash")):
            return "PANIC"
        if any(token in raw for token in ("hostile", "bear", "stress", "tight", "slowdown", "transition", "high_vol")):
            return "HOSTILE"
        if any(token in raw for token in ("supportive", "bull", "boom", "expansion", "low_vol", "normal")):
            return "SUPPORTIVE"
        return "UNKNOWN"

    @staticmethod
    def _normalize_exposure_state(value: Any, allowed_exposure: float) -> str:
        raw = str(value or "").strip().upper()
        if raw in {"RISK_OFF", "NEUTRAL", "RISK_ON"}:
            return raw
        if allowed_exposure >= 0.55:
            return "RISK_ON"
        if allowed_exposure >= 0.15:
            return "NEUTRAL"
        return "RISK_OFF"
    
    def load_latest_snapshot(self) -> Optional[DashboardSnapshot]:
        """
        Load latest immutable dashboard snapshot
        
        Returns:
            DashboardSnapshot or None if data insufficient
        """
        
        start_perf = time.perf_counter()
        self._load_requests += 1
        try:
            # Check cache first
            cache_key = "latest_snapshot"
            if self._is_cache_valid(cache_key):
                self._cache_hits += 1
                return self.snapshot_cache[cache_key]['snapshot']
            
            # Build new snapshot
            cutoff_time = datetime.now() - timedelta(hours=1.0)  # Minimum 1 hour lag
            
            # Load component views
            system_view = self._load_system_state_view(cutoff_time)
            risk_view = self._load_risk_state_view(cutoff_time)
            engine_view = self._load_engine_state_view(cutoff_time)
            validation_view = self._load_validation_state_view(cutoff_time)
            intelligence_view = self._load_intelligence_state_view(cutoff_time)
            
            # Calculate metadata
            quality_score = self._calculate_data_quality(
                system_view, risk_view, engine_view, validation_view, intelligence_view
            )
            
            completeness_score = self._calculate_completeness(
                system_view, risk_view, engine_view, validation_view, intelligence_view
            )
            
            staleness_hours = max(1.0, (datetime.now() - cutoff_time).total_seconds() / 3600)  # Minimum 1 hour for production
            
            # Create immutable snapshot
            snapshot = DashboardSnapshot(
                snapshot_id=self._generate_snapshot_id(),
                creation_time=datetime.now(),
                data_cutoff_time=cutoff_time,
                system_state=system_view,
                risk_state=risk_view,
                engine_state=engine_view,
                validation_state=validation_view,
                intelligence_state=intelligence_view,
                data_quality_score=quality_score,
                completeness_score=completeness_score,
                staleness_hours=staleness_hours,
                snapshot_hash=""  # Will be computed in __post_init__
            )
            
            # Compute and set hash
            snapshot_hash = snapshot._compute_hash()
            # Create new snapshot with hash (frozen dataclass workaround)
            snapshot = DashboardSnapshot(
                snapshot_id=snapshot.snapshot_id,
                creation_time=snapshot.creation_time,
                data_cutoff_time=snapshot.data_cutoff_time,
                system_state=snapshot.system_state,
                risk_state=snapshot.risk_state,
                engine_state=snapshot.engine_state,
                validation_state=snapshot.validation_state,
                intelligence_state=snapshot.intelligence_state,
                data_quality_score=snapshot.data_quality_score,
                completeness_score=snapshot.completeness_score,
                staleness_hours=snapshot.staleness_hours,
                snapshot_hash=snapshot_hash
            )
            
            # Cache snapshot
            self.snapshot_cache[cache_key] = {
                'snapshot': snapshot,
                'timestamp': datetime.now()
            }
            
            # Log access
            self._log_access(snapshot.snapshot_id, "load_latest_snapshot")
            
            return snapshot
            
        except Exception as e:
            print(f"❌ Failed to load dashboard snapshot: {e}")
            return None
        finally:
            self._load_durations_seconds.append(float(time.perf_counter() - start_perf))
            if len(self._load_durations_seconds) > 200:
                self._load_durations_seconds = self._load_durations_seconds[-200:]
    
    def _load_system_state_view(self, cutoff_time: datetime) -> SystemStateView:
        """Load system state view from unified state"""
        
        try:
            # Load unified state
            state_file = os.path.join(self._project_root(), 'data/state/unified_state.json')
            
            if os.path.exists(state_file):
                with open(state_file, 'r') as f:
                    state_data = json.load(f)
                
                # Extract system state
                organs = state_data.get('organs', {}) if isinstance(state_data.get('organs'), dict) else {}
                health = state_data.get('health', {}) if isinstance(state_data.get('health'), dict) else {}
                market_state = (
                    state_data.get('market', {})
                    if isinstance(state_data.get('market'), dict)
                    else state_data.get('market_state', {})
                )
                governor = state_data.get('governor_state', {}) if isinstance(state_data.get('governor_state'), dict) else {}
                conviction = state_data.get('conviction_contract', {})
                if not any(bool(section) for section in (organs, health, market_state, governor, conviction)):
                    raise ValueError("system_state_missing_core_sections")

                organs_healthy = sum(1 for organ in organs.values() if isinstance(organ, dict) and organ.get('status') == 'healthy')
                organs_total = len(organs)
                if organs_total == 0:
                    organs_healthy = self._safe_int(health.get('components_healthy'), 0)
                    organs_total = self._safe_int(health.get('total_components'), 0)

                system_status = self._normalize_system_status(
                    state_data.get('system_status') or health.get('health_status')
                )
                allowed_exposure = self._safe_float(
                    market_state.get('allowed_exposure', governor.get('equity_fraction', 0.0)),
                    0.0,
                )
                view_timestamp = (
                    self._safe_datetime(market_state.get('last_updated'))
                    or self._safe_datetime(health.get('last_updated'))
                    or self._safe_datetime(state_data.get('timestamp'))
                    or cutoff_time - timedelta(minutes=30)
                )
                
                return SystemStateView(
                    timestamp=view_timestamp,
                    available=True,
                    system_status=system_status,
                    organs_healthy=organs_healthy,
                    organs_total=organs_total,
                    current_regime=self._normalize_dashboard_regime(
                        market_state.get('regime') or governor.get('current_regime')
                    ),
                    regime_confidence=self._safe_float(
                        market_state.get('regime_confidence', governor.get('confidence', 0.0)),
                        0.0,
                    ),
                    regime_duration_days=self._safe_int(market_state.get('regime_duration_days'), 0),
                    last_regime_change=self._safe_datetime(market_state.get('last_regime_change')),
                    active_engine=str(market_state.get('active_engine', 'none') or 'none').lower()
                    if str(market_state.get('active_engine', 'none') or 'none').lower() in {'trend', 'crisis', 'none'}
                    else 'none',
                    engine_confidence=self._safe_float(market_state.get('engine_confidence'), 0.0),
                    exposure_state=self._normalize_exposure_state(
                        market_state.get('exposure_state'),
                        allowed_exposure,
                    ),
                    allowed_exposure=allowed_exposure,
                    conviction_locked=self._safe_bool(conviction.get('locked'), False),
                    conviction_violations=self._safe_int(conviction.get('violations'), 0),
                )
            
        except Exception as e:
            print(f"⚠️ Error loading system state: {e}")

        return SystemStateView(
            timestamp=cutoff_time - timedelta(minutes=30),
            available=False,
            unavailable_reason="system_state_missing_or_unreadable",
            system_status="critical",
            organs_healthy=0,
            organs_total=0,
            current_regime="UNKNOWN",
            regime_confidence=0.0,
            regime_duration_days=0,
            last_regime_change=None,
            active_engine="none",
            engine_confidence=0.0,
            exposure_state="RISK_OFF",
            allowed_exposure=0.0,
            conviction_locked=False,
            conviction_violations=0,
        )
    
    def _load_risk_state_view(self, cutoff_time: datetime) -> RiskStateView:
        """Load risk state view from risk data"""
        
        try:
            # Load risk state data
            risk_file = os.path.join(self._project_root(), 'data/risk/risk_state.parquet')
            
            if os.path.exists(risk_file):
                risk_df = pd.read_parquet(risk_file)
                if "date" not in risk_df.columns or risk_df.empty:
                    raise ValueError("risk_state_missing_date_or_empty")
                risk_df = risk_df.copy()
                risk_df["date"] = pd.to_datetime(risk_df["date"], errors="coerce")
                risk_df = risk_df.dropna(subset=["date"]).sort_values("date")
                risk_df = risk_df[risk_df["date"] <= cutoff_time]
                if risk_df.empty:
                    raise ValueError("risk_state_no_rows_before_cutoff")
                
                # Get latest risk data before cutoff
                risk_data = risk_df.iloc[-1]
                
                if risk_data is not None:
                    current_drawdown = self._safe_float(risk_data.get('current_drawdown'), 0.0)
                    max_allowed_drawdown = self._safe_float(risk_data.get('max_allowed_drawdown'), -0.20)
                    drawdown_ratio = abs(current_drawdown / max_allowed_drawdown) if max_allowed_drawdown != 0 else 0.0
                    
                    # Determine volatility stress level
                    vol_20d = self._safe_float(risk_data.get('volatility_20d'), 0.0)
                    if vol_20d > 0.30:
                        vol_stress = "extreme"
                    elif vol_20d > 0.25:
                        vol_stress = "high"
                    elif vol_20d > 0.20:
                        vol_stress = "medium"
                    else:
                        vol_stress = "low"
                    
                    return RiskStateView(
                        timestamp=self._safe_datetime(risk_data.get('date')) or cutoff_time - timedelta(minutes=30),
                        available=True,
                        emergency_brake_status=str(risk_data.get('emergency_brake_status', 'ARMED') or 'ARMED').upper()
                        if str(risk_data.get('emergency_brake_status', 'ARMED') or 'ARMED').upper() in {'ARMED', 'DISARMED'}
                        else ('ARMED' if self._safe_bool(risk_data.get('emergency_active'), False) else 'DISARMED'),
                        emergency_active=self._safe_bool(risk_data.get('emergency_active'), False),
                        current_drawdown=current_drawdown,
                        max_allowed_drawdown=max_allowed_drawdown,
                        drawdown_covenant_ratio=drawdown_ratio,
                        kill_switches_armed=self._safe_int(risk_data.get('kill_switches_armed'), 0),
                        kill_switches_total=self._safe_int(risk_data.get('kill_switches_total'), 0),
                        last_kill_switch_activation=self._safe_datetime(risk_data.get('last_kill_switch_activation')),
                        volatility_stress=vol_stress,
                        volatility_20d=vol_20d,
                        last_intervention=self._safe_datetime(risk_data.get('last_intervention')),
                        intervention_type=risk_data.get('intervention_type'),
                    )
            
        except Exception as e:
            print(f"⚠️ Error loading risk state: {e}")

        return RiskStateView(
            timestamp=cutoff_time - timedelta(minutes=30),
            available=False,
            unavailable_reason="risk_state_missing_or_unreadable",
            emergency_brake_status="ARMED",
            emergency_active=False,
            current_drawdown=0.0,
            max_allowed_drawdown=-0.20,
            drawdown_covenant_ratio=0.0,
            kill_switches_armed=0,
            kill_switches_total=0,
            last_kill_switch_activation=None,
            volatility_stress="extreme",
            volatility_20d=0.0,
            last_intervention=None,
            intervention_type="state_unavailable",
        )
    
    def _load_engine_state_view(self, cutoff_time: datetime) -> EngineStateView:
        """Load engine state view from engine data"""
        
        try:
            # Load engine decisions data
            engine_file = os.path.join(self._project_root(), 'data/intelligence/engine_decisions.parquet')
            
            if os.path.exists(engine_file):
                engine_df = pd.read_parquet(engine_file)
                if "date" not in engine_df.columns or engine_df.empty:
                    raise ValueError("engine_state_missing_date_or_empty")
                engine_df = engine_df.copy()
                engine_df["date"] = pd.to_datetime(engine_df["date"], errors="coerce")
                engine_df = engine_df.dropna(subset=["date"]).sort_values("date")
                engine_df = engine_df[engine_df["date"] <= cutoff_time]
                if engine_df.empty:
                    raise ValueError("engine_state_no_rows_before_cutoff")
                
                # Get latest engine data before cutoff
                engine_data = engine_df.iloc[-1]
                
                if engine_data is not None:
                    # Calculate days active
                    trend_days = int((engine_df['trend_engine_active'] == True).sum()) if 'trend_engine_active' in engine_df.columns else 0
                    crisis_days = int((engine_df['crisis_engine_active'] == True).sum()) if 'crisis_engine_active' in engine_df.columns else 0
                    recent_exits = engine_data.get('trend_recent_exits', [])
                    if isinstance(recent_exits, str):
                        recent_exits = [token.strip() for token in recent_exits.split(",") if token.strip()]
                    elif not isinstance(recent_exits, list):
                        recent_exits = []
                    
                    return EngineStateView(
                        timestamp=self._safe_datetime(engine_data.get('date')) or cutoff_time - timedelta(minutes=30),
                        available=True,
                        trend_engine_active=self._safe_bool(engine_data.get('trend_engine_active'), False),
                        trend_engine_days_active=trend_days,
                        trend_holding_duration_avg=self._safe_float(engine_data.get('trend_holding_duration_avg'), 0.0),
                        trend_recent_exits=recent_exits,
                        crisis_engine_active=self._safe_bool(engine_data.get('crisis_engine_active'), False),
                        crisis_engine_days_active=crisis_days,
                        crisis_convexity_score=self._safe_float(engine_data.get('crisis_convexity_score'), 0.0),
                        crisis_bleed_vs_payout=self._safe_float(engine_data.get('crisis_bleed_vs_payout'), 0.0),
                        engine_conflicts=self._safe_int(engine_data.get('engine_conflicts'), 0),
                        regime_engine_alignment=self._safe_float(engine_data.get('regime_engine_alignment'), 0.0),
                    )
            
        except Exception as e:
            print(f"⚠️ Error loading engine state: {e}")

        return EngineStateView(
            timestamp=cutoff_time - timedelta(minutes=30),
            available=False,
            unavailable_reason="engine_state_missing_or_unreadable",
            trend_engine_active=False,
            trend_engine_days_active=0,
            trend_holding_duration_avg=0.0,
            trend_recent_exits=[],
            crisis_engine_active=False,
            crisis_engine_days_active=0,
            crisis_convexity_score=0.0,
            crisis_bleed_vs_payout=0.0,
            engine_conflicts=0,
            regime_engine_alignment=0.0,
        )
    
    def _load_validation_state_view(self, cutoff_time: datetime) -> ValidationStateView:
        """Load validation state view from validation data"""
        
        try:
            # Load validation summary
            validation_file = os.path.join(self._project_root(), 'data/validation/validation_summary.json')
            
            if os.path.exists(validation_file):
                with open(validation_file, 'r') as f:
                    validation_data = json.load(f)
                
                # Parse dates
                last_walkforward_date = self._safe_datetime(validation_data.get('last_walkforward_date'))
                layers = validation_data.get('data_integrity_layers')
                if not isinstance(layers, dict):
                    layers = {
                        'ingestion': False,
                        'processing': False,
                        'validation': False,
                        'storage': False,
                        'access': False,
                    }
                status = str(validation_data.get('last_walkforward_result', 'PENDING') or 'PENDING').upper()
                if status not in {'PASS', 'FAIL', 'PENDING'}:
                    status = 'PENDING'
                
                return ValidationStateView(
                    timestamp=last_walkforward_date or cutoff_time - timedelta(minutes=30),
                    available=True,
                    last_walkforward_result=status,
                    last_walkforward_date=last_walkforward_date,
                    walkforward_success_rate=self._safe_float(validation_data.get('walkforward_success_rate'), 0.0),
                    current_rules_hash=str(validation_data.get('current_rules_hash', 'unavailable') or 'unavailable'),
                    rules_hash_verified=self._safe_bool(validation_data.get('rules_hash_verified'), False),
                    override_attempts_24h=self._safe_int(validation_data.get('override_attempts_24h'), 0),
                    override_attempts_total=self._safe_int(validation_data.get('override_attempts_total'), 0),
                    data_integrity_layers=layers,
                    data_integrity_score=self._safe_float(validation_data.get('data_integrity_score'), 0.0),
                )
            
        except Exception as e:
            print(f"⚠️ Error loading validation state: {e}")

        return ValidationStateView(
            timestamp=cutoff_time - timedelta(minutes=30),
            available=False,
            unavailable_reason="validation_state_missing_or_unreadable",
            last_walkforward_result="PENDING",
            last_walkforward_date=None,
            walkforward_success_rate=0.0,
            current_rules_hash="unavailable",
            rules_hash_verified=False,
            override_attempts_24h=0,
            override_attempts_total=0,
            data_integrity_layers={
                'ingestion': False,
                'processing': False,
                'validation': False,
                'storage': False,
                'access': False
            },
            data_integrity_score=0.0,
        )
    
    def _load_intelligence_state_view(self, cutoff_time: datetime) -> IntelligenceStateView:
        """Load intelligence state view from observer data"""
        
        try:
            # Load intelligence state
            intelligence_file = os.path.join(self._project_root(), 'data/intelligence/observer/intelligence_state.json')
            
            if os.path.exists(intelligence_file):
                with open(intelligence_file, 'r') as f:
                    intelligence_data = json.load(f)
                
                # Parse dates
                last_update = self._safe_datetime(intelligence_data.get('last_intelligence_update'))
                
                return IntelligenceStateView(
                    timestamp=last_update or cutoff_time - timedelta(minutes=30),
                    available=True,
                    regime_similarity_index=self._safe_float(intelligence_data.get('regime_similarity_index'), 0.0),
                    stress_clustering_index=self._safe_float(intelligence_data.get('stress_clustering_index'), 0.0),
                    false_calm_likelihood=self._safe_float(intelligence_data.get('false_calm_likelihood'), 0.0),
                    behavioral_drift_index=self._safe_float(intelligence_data.get('behavioral_drift_index'), 0.0),
                    intelligence_confidence=self._safe_float(intelligence_data.get('intelligence_confidence'), 0.0),
                    last_intelligence_update=last_update,
                    weekly_report_available=self._safe_bool(intelligence_data.get('weekly_report_available'), False),
                    weekly_report_path=intelligence_data.get('weekly_report_path'),
                    observer_healthy=self._safe_bool(intelligence_data.get('observer_healthy'), False),
                    observer_violations=self._safe_int(intelligence_data.get('observer_violations'), 0),
                    observer_suspended=self._safe_bool(intelligence_data.get('observer_suspended'), True),
                )
            
        except Exception as e:
            print(f"⚠️ Error loading intelligence state: {e}")

        return IntelligenceStateView(
            timestamp=cutoff_time - timedelta(minutes=30),
            available=False,
            unavailable_reason="intelligence_state_missing_or_unreadable",
            regime_similarity_index=0.0,
            stress_clustering_index=0.0,
            false_calm_likelihood=0.0,
            behavioral_drift_index=0.0,
            intelligence_confidence=0.0,
            last_intelligence_update=None,
            weekly_report_available=False,
            weekly_report_path=None,
            observer_healthy=False,
            observer_violations=0,
            observer_suspended=True,
        )
    
    def _calculate_data_quality(self, *views) -> float:
        """Calculate overall data quality score"""
        available = [1.0 if getattr(view, "available", True) else 0.0 for view in views]
        return float(sum(available) / len(available)) if available else 0.0
    
    def _calculate_completeness(self, *views) -> float:
        """Calculate data completeness score"""
        completeness = []
        for view in views:
            if not getattr(view, "available", True):
                completeness.append(0.0)
                continue
            view_dict = dict(view.__dict__)
            view_dict.pop("available", None)
            view_dict.pop("unavailable_reason", None)
            populated = sum(1 for value in view_dict.values() if value not in (None, "", [], {}))
            completeness.append(populated / max(len(view_dict), 1))
        return float(sum(completeness) / len(completeness)) if completeness else 0.0
    
    def _generate_snapshot_id(self) -> str:
        """Generate unique snapshot ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"snapshot_{timestamp}"
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached snapshot is still valid"""
        if cache_key not in self.snapshot_cache:
            return False
        
        cache_age = datetime.now() - self.snapshot_cache[cache_key]['timestamp']
        return cache_age.total_seconds() < (self.cache_ttl_minutes * 60)
    
    def _log_access(self, snapshot_id: str, operation: str):
        """Log snapshot access for audit trail"""
        self.access_log.append({
            'timestamp': datetime.now(),
            'snapshot_id': snapshot_id,
            'operation': operation,
            'caller': 'constitutional_cockpit'
        })
        
        # Keep only last 100 access records
        if len(self.access_log) > 100:
            self.access_log = self.access_log[-100:]
    
    def get_access_summary(self) -> Dict[str, Any]:
        """Get summary of snapshot access patterns"""
        cache_hit_rate = (
            float(self._cache_hits / self._load_requests)
            if self._load_requests > 0
            else None
        )
        average_load_time = (
            float(sum(self._load_durations_seconds) / len(self._load_durations_seconds))
            if self._load_durations_seconds
            else None
        )
        return {
            'total_accesses': len(self.access_log),
            'last_access': self.access_log[-1] if self.access_log else None,
            'cache_hit_rate': cache_hit_rate,
            'average_load_time': average_load_time,
        }
