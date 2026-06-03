"""
StrategyRegistry — The authoritative catalog of all strategies in Northstar V3.

A strategy in Alpha OS is any named alpha-generating signal or model that:
  - Produces per-ticker alpha scores (long/short signals)
  - Has a documented feature set and regime-conditional performance history
  - Has been through validation before being promoted to ACTIVE status
  - Has a current lifecycle status

The registry is the canonical record. The Bayesian tribunal stores beliefs about
strategy performance. The orchestrator decides runtime weights. All three consult
the registry for the authoritative list of strategies.

Strategy lifecycle statuses:
  - RESEARCH:    Discovered by research engine, not yet validated
  - CANDIDATE:   Passed validation criteria, awaiting promotion review
  - ACTIVE:      Running in live system, receiving capital allocation
  - PROBATION:   Active but underperforming — reduced allocation, monitored
  - RETIRED:     Removed from live system, archived in registry
  - REDUNDANT:   Identified as a duplicate of another ACTIVE strategy
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, List
from enum import Enum
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


class StrategyStatus(str, Enum):
    RESEARCH   = "RESEARCH"
    CANDIDATE  = "CANDIDATE"
    ACTIVE     = "ACTIVE"
    PROBATION  = "PROBATION"
    RETIRED    = "RETIRED"
    REDUNDANT  = "REDUNDANT"


class StrategyFamily(str, Enum):
    MOMENTUM        = "MOMENTUM"       # Price momentum, factor momentum
    MEAN_REVERSION  = "MEAN_REVERSION" # Statistical mean reversion
    VALUE           = "VALUE"          # Fundamental value
    QUALITY         = "QUALITY"        # Quality/profitability factors
    MACRO           = "MACRO"          # Macro-driven signals
    SENTIMENT       = "SENTIMENT"      # Sentiment-based signals
    ALTERNATIVE     = "ALTERNATIVE"    # Alt data signals
    COMPOSITE       = "COMPOSITE"      # Multi-factor composites


@dataclass
class StrategyPerformanceRecord:
    """A point-in-time snapshot of strategy performance."""
    as_of_date: datetime
    ic_mean: float               # Information coefficient mean
    ic_std: float                # IC standard deviation
    icir: float                  # IC information ratio (mean/std)
    ic_hit_rate: float           # Fraction of periods with IC > 0
    regime_conditional_ics: Dict[str, float]  # {regime_name: ic_value} mapping
    turnover_pct: float          # Strategy turnover %
    max_drawdown: float          # Maximum drawdown in validation period
    live_days: int               # Days running in live system
    live_ic: Optional[float] = None  # IC in live system (None if < 30 days live)


@dataclass
class StrategyRecord:
    """Complete record for one strategy in the registry."""
    strategy_id: str             # Unique identifier, e.g. "momentum_v3_20240815"
    strategy_name: str           # Human-readable name
    family: StrategyFamily
    status: StrategyStatus
    
    # Provenance
    discovered_date: datetime
    promoted_date: Optional[datetime] = None
    retired_date: Optional[datetime] = None
    model_registry_path: Optional[str] = None  # Path in data/model_registry/
    model_artifact_path: Optional[str] = None  # Direct path to the trained model artifact
    
    # Validation evidence (populated at promotion time)
    validation_ic_mean: float = 0.0
    validation_icir: float = 0.0
    validation_hit_rate: float = 0.0
    validation_regime_ics: Dict[str, float] = field(default_factory=dict)
    validation_experiment_ids: List[str] = field(default_factory=list)
    
    # Current live performance (populated after 30+ days in production)
    current_live_ic: Optional[float] = None
    days_on_probation: int = 0
    probation_reason: Optional[str] = None
    
    # Redundancy tracking
    redundant_with: Optional[str] = None  # strategy_id of the dominant strategy
    
    # Current operational parameters
    max_capital_weight: float = 0.20  # Max fraction of strategy capital this can receive
    regime_activations: Dict[str, bool] = field(default_factory=dict)  # {regime: active_flag}
    
    # History
    performance_history: List[StrategyPerformanceRecord] = field(default_factory=list)
    status_change_log: List[Dict] = field(default_factory=list)


class RegistryError(Exception):
    """Base exception for registry errors"""
    pass


class DuplicateStrategyError(RegistryError):
    """Raised when attempting to register a duplicate strategy"""
    pass


class StrategyNotFoundError(RegistryError):
    """Raised when strategy is not found in registry"""
    pass


class RegistryCorruptionError(RegistryError):
    """Raised when registry file is corrupted"""
    pass


class StrategyRegistry:
    """The single source of truth for what strategies exist in the system."""
    
    def __init__(self, registry_path: str | dict = "data/model_registry/"):
        self.config = registry_path if isinstance(registry_path, dict) else {}
        if isinstance(registry_path, dict):
            resolved_registry_path = (
                self.config.get("alpha_os_registry_path")
                or self.config.get("model_registry_path")
                or "data/model_registry/"
            )
        else:
            resolved_registry_path = registry_path

        self.registry_path = Path(str(resolved_registry_path))
        self.registry_file = self.registry_path / "strategy_registry.json"
        self.production_file = self.registry_path / "production.json"
        self.strategies: Dict[str, StrategyRecord] = {}
        
        # Ensure directory exists
        self.registry_path.mkdir(parents=True, exist_ok=True)
        
        # Load existing registry
        self.load()

    @staticmethod
    def _ic_rank(record: StrategyRecord) -> float:
        value = record.current_live_ic
        if value is None:
            return float("-inf")
        try:
            return float(value)
        except Exception:
            return float("-inf")

    def _resolve_model_pointer(self, record: StrategyRecord) -> Optional[str]:
        candidates = [record.model_artifact_path, record.model_registry_path]
        for candidate in candidates:
            if not candidate:
                continue
            path = Path(str(candidate))
            if path.suffix.lower() == ".json" and path.exists():
                try:
                    payload = json.loads(path.read_text())
                except Exception:
                    logger.warning("Could not parse model registry pointer: %s", path)
                    return str(path)
                for key in ("model_path", "artifact_path", "path"):
                    resolved = payload.get(key)
                    if resolved:
                        return str(resolved)
            return str(path)
        return None

    def _write_production_file(self, strategy_id: str, model_artifact_path: str) -> None:
        payload = {
            "active_strategy": strategy_id,
            "model_path": model_artifact_path,
            "promoted_at": datetime.utcnow().isoformat(),
        }
        self.production_file.parent.mkdir(parents=True, exist_ok=True)
        self.production_file.write_text(json.dumps(payload, indent=2))
        logger.info("Updated production.json: %s -> %s", strategy_id, model_artifact_path)

    def get_active_model_path(self) -> Optional[str]:
        """
        Return the model artifact path for the current ACTIVE strategy.
        Returns None if no ACTIVE strategy or no model path is registered.
        """
        active = [record for record in self.strategies.values() if record.status == StrategyStatus.ACTIVE]
        if not active:
            logger.warning("No ACTIVE strategies in Alpha OS registry")
            return None

        if len(active) > 1:
            active = sorted(active, key=self._ic_rank, reverse=True)
            logger.warning(
                "Multiple ACTIVE strategies: %s. Using highest IC.",
                [record.strategy_id for record in active],
            )

        strategy = active[0]
        model_path = self._resolve_model_pointer(strategy)
        if not model_path:
            logger.warning(
                "ACTIVE strategy %s has no model artifact path registered",
                strategy.strategy_id,
            )
        return model_path

    def promote_to_active(self, strategy_id: str, model_artifact_path: str) -> None:
        """Promote one strategy to ACTIVE and keep production.json in sync."""
        record = self.get(strategy_id)

        for other_id, other in self.strategies.items():
            if other_id == strategy_id:
                continue
            if other.status == StrategyStatus.ACTIVE:
                other.status = StrategyStatus.PROBATION
                other.probation_reason = f"Superseded by ACTIVE strategy {strategy_id}"
                other.status_change_log.append(
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "from_status": StrategyStatus.ACTIVE.value,
                        "to_status": StrategyStatus.PROBATION.value,
                        "reason": f"Superseded by ACTIVE strategy {strategy_id}",
                    }
                )

        old_status = record.status
        record.status = StrategyStatus.ACTIVE
        record.model_artifact_path = model_artifact_path
        record.model_registry_path = model_artifact_path
        if record.promoted_date is None:
            record.promoted_date = datetime.utcnow()
        record.status_change_log.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "from_status": old_status.value,
                "to_status": StrategyStatus.ACTIVE.value,
                "reason": f"Promoted with model artifact {model_artifact_path}",
            }
        )

        self.save()
        self._write_production_file(strategy_id, model_artifact_path)
    
    def register(self, record: StrategyRecord) -> None:
        """
        Adds a strategy to the registry.
        Raises DuplicateStrategyError if strategy_id already exists.
        """
        if record.strategy_id in self.strategies:
            raise DuplicateStrategyError(
                f"Strategy {record.strategy_id} already exists in registry"
            )
        
        self.strategies[record.strategy_id] = record
        self.save()
        
        logger.info(f"Registered strategy: {record.strategy_id} ({record.status.value})")
    
    def get(self, strategy_id: str) -> StrategyRecord:
        """
        Returns the record for a strategy.
        Raises StrategyNotFoundError if absent.
        """
        if strategy_id not in self.strategies:
            raise StrategyNotFoundError(
                f"Strategy {strategy_id} not found in registry"
            )
        return self.strategies[strategy_id]
    
    def get_by_status(self, status: StrategyStatus) -> List[StrategyRecord]:
        """Returns all strategies with the given status."""
        return [
            record for record in self.strategies.values()
            if record.status == status
        ]
    
    def update_status(self, strategy_id: str, new_status: StrategyStatus, reason: str) -> None:
        """
        Updates a strategy's status and appends to its status_change_log.
        Saves to disk immediately (atomic write).
        """
        record = self.get(strategy_id)
        old_status = record.status
        
        record.status = new_status
        record.status_change_log.append({
            'timestamp': datetime.utcnow().isoformat(),
            'from_status': old_status.value,
            'to_status': new_status.value,
            'reason': reason
        })
        
        # Update status-specific timestamps
        if new_status == StrategyStatus.ACTIVE and record.promoted_date is None:
            record.promoted_date = datetime.utcnow()
        elif new_status == StrategyStatus.RETIRED and record.retired_date is None:
            record.retired_date = datetime.utcnow()
        
        self.save()
        
        logger.info(
            f"Updated strategy {strategy_id}: {old_status.value} → {new_status.value} "
            f"(reason: {reason})"
        )
    
    def update_live_performance(
        self, 
        strategy_id: str, 
        performance: StrategyPerformanceRecord
    ) -> None:
        """
        Appends a new performance record to the strategy's history.
        Updates current_live_ic. Saves to disk.
        """
        record = self.get(strategy_id)
        
        record.performance_history.append(performance)
        record.current_live_ic = performance.live_ic
        
        self.save()
        
        logger.debug(
            f"Updated performance for {strategy_id}: "
            f"IC={performance.ic_mean:.4f}, ICIR={performance.icir:.2f}"
        )
    
    def get_active_strategies(self) -> List[StrategyRecord]:
        """Returns all ACTIVE and PROBATION strategies (running in live system)."""
        return [
            record for record in self.strategies.values()
            if record.status in [StrategyStatus.ACTIVE, StrategyStatus.PROBATION]
        ]
    
    def save(self) -> None:
        """
        Writes the entire registry to disk.
        Uses atomic write (temp file + rename) to avoid corruption.
        """
        try:
            # Convert to serializable format
            registry_data = {
                'version': '1.0',
                'last_updated': datetime.utcnow().isoformat(),
                'total_strategies': len(self.strategies),
                'strategies': {
                    strategy_id: self._serialize_record(record)
                    for strategy_id, record in self.strategies.items()
                }
            }
            
            # Atomic write: write to temp file then rename
            temp_file = self.registry_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(registry_data, f, indent=2, default=str)
            
            temp_file.replace(self.registry_file)
            
            logger.debug(f"Registry saved: {len(self.strategies)} strategies")
            
        except Exception as e:
            logger.error(f"Failed to save registry: {e}")
            raise RegistryError(f"Failed to save registry: {e}")
    
    def load(self) -> None:
        """
        Reads from disk. Validates schema and raises RegistryCorruptionError
        if the file is malformed.
        """
        if not self.registry_file.exists():
            logger.info("No existing registry found, starting fresh")
            return
        
        try:
            with open(self.registry_file, 'r') as f:
                registry_data = json.load(f)
            
            # Validate schema
            if not isinstance(registry_data, dict):
                raise RegistryCorruptionError("Registry file is not a valid JSON object")
            
            if 'strategies' not in registry_data:
                raise RegistryCorruptionError("Registry missing 'strategies' key")
            
            # Load strategies
            self.strategies = {}
            for strategy_id, strategy_data in registry_data['strategies'].items():
                record = self._deserialize_record(strategy_data)
                self.strategies[strategy_id] = record
            
            logger.info(f"Loaded registry: {len(self.strategies)} strategies")
            
        except json.JSONDecodeError as e:
            raise RegistryCorruptionError(f"Registry file is corrupted: {e}")
        except Exception as e:
            logger.error(f"Failed to load registry: {e}")
            raise RegistryError(f"Failed to load registry: {e}")
    
    def get_registry_summary(self) -> Dict:
        """
        Returns a dict summarizing the current state of all strategies,
        suitable for dashboard display.
        """
        by_status = {}
        by_family = {}
        active_icirs = []
        weakest_active = None
        weakest_ic = float('inf')
        
        for record in self.strategies.values():
            # Count by status
            status_key = record.status.value
            by_status[status_key] = by_status.get(status_key, 0) + 1
            
            # Count by family
            family_key = record.family.value
            by_family[family_key] = by_family.get(family_key, 0) + 1
            
            # Track active strategy performance
            if record.status == StrategyStatus.ACTIVE:
                if record.validation_icir > 0:
                    active_icirs.append(record.validation_icir)
                
                if record.current_live_ic is not None and record.current_live_ic < weakest_ic:
                    weakest_ic = record.current_live_ic
                    weakest_active = record.strategy_id
        
        return {
            'total_strategies': len(self.strategies),
            'by_status': by_status,
            'by_family': by_family,
            'active_count': by_status.get('ACTIVE', 0),
            'probation_count': by_status.get('PROBATION', 0),
            'candidate_count': by_status.get('CANDIDATE', 0),
            'avg_active_icir': sum(active_icirs) / len(active_icirs) if active_icirs else 0.0,
            'weakest_active_strategy': weakest_active,
            'weakest_active_ic': weakest_ic if weakest_active else None
        }
    
    def _serialize_record(self, record: StrategyRecord) -> Dict:
        """Convert StrategyRecord to JSON-serializable dict."""
        data = asdict(record)
        # Convert enums to strings
        data['family'] = record.family.value
        data['status'] = record.status.value
        return data
    
    def _deserialize_record(self, data: Dict) -> StrategyRecord:
        """Convert dict to StrategyRecord."""
        # Convert string enums back to enum types
        data['family'] = StrategyFamily(data['family'])
        data['status'] = StrategyStatus(data['status'])
        
        # Convert datetime strings back to datetime objects
        for date_field in ['discovered_date', 'promoted_date', 'retired_date']:
            if data.get(date_field):
                data[date_field] = datetime.fromisoformat(data[date_field])
        
        # Convert performance history
        if 'performance_history' in data:
            data['performance_history'] = [
                StrategyPerformanceRecord(
                    as_of_date=datetime.fromisoformat(p['as_of_date']),
                    ic_mean=p['ic_mean'],
                    ic_std=p['ic_std'],
                    icir=p['icir'],
                    ic_hit_rate=p['ic_hit_rate'],
                    regime_conditional_ics=p['regime_conditional_ics'],
                    turnover_pct=p['turnover_pct'],
                    max_drawdown=p['max_drawdown'],
                    live_days=p['live_days'],
                    live_ic=p.get('live_ic')
                )
                for p in data['performance_history']
            ]
        
        return StrategyRecord(**data)
