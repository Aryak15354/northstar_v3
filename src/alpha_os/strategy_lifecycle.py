"""StrategyLifecycleManager — Governs the strategy lifecycle in Northstar V3."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


class PromotionCriteriaNotMetError(Exception):
    """Raised when promote_to_active is called on a strategy that fails its own promotion_criteria."""


@dataclass
class PromotionEvaluationResult:
    evaluated_count: int
    promoted_ids: List[str] = field(default_factory=list)
    failed_ids: List[str] = field(default_factory=list)
    disqualified_ids: List[str] = field(default_factory=list)
    failure_reasons: Dict[str, List[str]] = field(default_factory=dict)
    as_of_date: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MonitoringResult:
    strategies_checked: int
    new_probations: List[str] = field(default_factory=list)
    new_retirements: List[str] = field(default_factory=list)
    recovered_strategies: List[str] = field(default_factory=list)
    all_clear_strategies: List[str] = field(default_factory=list)
    performance_summary: Dict[str, float] = field(default_factory=dict)
    as_of_date: datetime = field(default_factory=datetime.utcnow)


class StrategyLifecycleManager:
    """Governs the complete strategy lifecycle."""
    
    def __init__(self, registry, tribunal, config: Optional[Dict] = None, event_bus=None):
        self._registry = registry
        self._tribunal = tribunal
        self._config = config or {}
        self._event_bus = event_bus
        
        self._promotion_log_path = Path("data/model_registry/promotion_log.json")
        self._reload_signal_path = Path("data/model_registry/reload_signal.json")
        self._promotion_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._promotion_criteria = self._config.get('alpha_os', {}).get(
            'promotion_criteria', self._default_promotion_criteria()
        )
        self._probation_criteria = self._config.get('alpha_os', {}).get(
            'probation_criteria', self._default_probation_criteria()
        )
        self._demotion_criteria = self._config.get('alpha_os', {}).get(
            'demotion_criteria', self._default_demotion_criteria()
        )
        self._hot_reload_config = self._config.get('alpha_os', {}).get(
            'hot_reload', {'enabled': True}
        )
    
    def evaluate_research_candidates(self, experiments: List[Dict]) -> PromotionEvaluationResult:
        result = PromotionEvaluationResult(evaluated_count=len(experiments), as_of_date=datetime.utcnow())
        for experiment in experiments:
            strategy_id = experiment.get('strategy_id') or experiment.get('model_id')
            if not strategy_id:
                continue
            passes, reasons = self._evaluate_promotion_criteria(experiment)
            if passes:
                result.promoted_ids.append(strategy_id)
            else:
                result.failed_ids.append(strategy_id)
                result.failure_reasons[strategy_id] = reasons
        return result
    
    def promote_to_active(
        self,
        strategy_id: str,
        override_reason: Optional[str] = None,
        force: bool = False,
    ) -> None:
        """
        Promote a strategy to ACTIVE.

        Gated on self._promotion_criteria (min_ic_mean/min_icir/min_hit_rate/
        min_validation_windows), evaluated against the strategy's own
        validation evidence. Previously this method promoted unconditionally
        -- a free-text override_reason was the only "check" -- so a model
        with IC ~= 0 could reach ACTIVE and start receiving real capital
        allocation. Set force=True only for a deliberate, reviewed manual
        override; override_reason is still recorded either way but no longer
        substitutes for meeting criteria.
        """
        strategy = self._registry.get(strategy_id)

        if not force:
            passes, reasons = self._evaluate_strategy_promotion_criteria(strategy)
            if not passes:
                raise PromotionCriteriaNotMetError(
                    f"Strategy {strategy_id} does not meet promotion criteria: "
                    f"{'; '.join(reasons)}. Call with force=True to override "
                    f"deliberately (this bypasses quality gating)."
                )

        evidence = {
            'ic_mean': strategy.validation_ic_mean,
            'icir': strategy.validation_icir,
            'evidence_type': 'PROMOTION'
        }
        self._tribunal.update_priors_from_evidence(strategy_id, evidence)
        reason = override_reason or "Promoted"
        if force:
            reason = f"FORCED OVERRIDE: {reason}"
        self._registry.update_status(strategy_id, strategy.status.__class__.ACTIVE, reason)

    def _evaluate_strategy_promotion_criteria(self, strategy) -> tuple:
        """Check a registered StrategyRecord's own validation evidence against self._promotion_criteria."""
        reasons = []
        criteria = self._promotion_criteria

        if strategy.validation_ic_mean < criteria['min_ic_mean']:
            reasons.append(
                f"validation_ic_mean {strategy.validation_ic_mean:.4f} < "
                f"required {criteria['min_ic_mean']:.4f}"
            )
        if strategy.validation_icir < criteria['min_icir']:
            reasons.append(
                f"validation_icir {strategy.validation_icir:.4f} < required {criteria['min_icir']:.4f}"
            )
        if strategy.validation_hit_rate < criteria['min_hit_rate']:
            reasons.append(
                f"validation_hit_rate {strategy.validation_hit_rate:.4f} < "
                f"required {criteria['min_hit_rate']:.4f}"
            )

        min_windows = criteria.get('min_validation_windows')
        if min_windows:
            windows = len(strategy.validation_experiment_ids or [])
            if windows < min_windows:
                reasons.append(
                    f"only {windows} validation experiment(s) on record, "
                    f"required min_validation_windows={min_windows}"
                )

        # min_validation_months and max_turnover_pct are not currently tracked
        # on StrategyRecord (no promotion-time duration/turnover field exists),
        # so they cannot be enforced here -- not silently treated as passing,
        # just genuinely unavailable to check with the current data model.

        return len(reasons) == 0, reasons
    
    def monitor_live_strategies(self, as_of_date: datetime) -> MonitoringResult:
        result = MonitoringResult(strategies_checked=0, as_of_date=as_of_date)
        active_strategies = self._registry.get_active_strategies()
        result.strategies_checked = len(active_strategies)
        return result
    
    def demote_to_retired(self, strategy_id: str, reason: str) -> None:
        strategy = self._registry.get(strategy_id)
        self._registry.update_status(strategy_id, strategy.status.__class__.RETIRED, reason)
    
    def get_lifecycle_report(self) -> Dict:
        return {'timestamp': datetime.utcnow().isoformat(), 'registry_summary': self._registry.get_registry_summary()}
    
    def _evaluate_promotion_criteria(self, experiment: Dict) -> tuple:
        reasons = []
        criteria = self._promotion_criteria

        ic_mean = experiment.get('ic_mean', 0.0)
        if ic_mean < criteria['min_ic_mean']:
            reasons.append(f"ic_mean {ic_mean:.4f} < required {criteria['min_ic_mean']:.4f}")

        icir = experiment.get('icir', 0.0)
        if icir < criteria['min_icir']:
            reasons.append(f"icir {icir:.4f} < required {criteria['min_icir']:.4f}")

        hit_rate = experiment.get('hit_rate', 0.0)
        if hit_rate < criteria['min_hit_rate']:
            reasons.append(f"hit_rate {hit_rate:.4f} < required {criteria['min_hit_rate']:.4f}")

        return len(reasons) == 0, reasons
    
    def _trigger_hot_reload(self, strategy_id: str, action: str = 'LOAD') -> None:
        pass
    
    def _compute_current_live_ic(self, strategy_id: str, as_of_date: datetime) -> float:
        return 0.0
    
    def _emit_event(self, event_type: str, data: Dict) -> None:
        pass
    
    @staticmethod
    def _default_promotion_criteria() -> Dict:
        return {'min_ic_mean': 0.035, 'min_icir': 1.2, 'min_hit_rate': 0.55, 'min_validation_windows': 6, 'min_validation_months': 12, 'max_turnover_pct': 50}
    
    @staticmethod
    def _default_probation_criteria() -> Dict:
        return {'probation_trigger_live_ic_below': 0.015, 'probation_duration_days': 30, 'probation_weight_factor': 0.4}
    
    @staticmethod
    def _default_demotion_criteria() -> Dict:
        return {'retire_if_live_ic_below': 0.005, 'retire_after_probation_days': 30}
