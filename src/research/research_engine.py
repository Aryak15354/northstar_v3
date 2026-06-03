"""Research Engine for Northstar: governed offline intelligence orchestrator."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

import yaml

from .research_controller import ResearchController

logger = logging.getLogger(__name__)


class ResearchEngine:
    """Main research engine with freeze governance + candidate discipline."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = Path(config_path) if config_path is not None else Path("config/research_policy.yaml")
        self.config = self._load_config()
        self.research_state_dir = Path("data/results/research/state")
        self.research_cycle_dir = Path("data/results/research/cycles")
        self.research_state_dir.mkdir(parents=True, exist_ok=True)
        self.research_cycle_dir.mkdir(parents=True, exist_ok=True)

        self.modules: Dict[str, Any] = {}
        self._initialize_modules()

        hr_cfg = dict(self.config.get("historical_research", {}))
        self.historical_controller_enabled = bool(hr_cfg.get("enabled", True))
        self.controller = ResearchController(config=hr_cfg)
        runtime_cfg = dict(self.config.get("runtime_policy", {}))
        self.legacy_labs_enabled = bool(runtime_cfg.get("enable_legacy_labs", False))
        cert_cfg = dict(hr_cfg.get("certification", {}))
        mode = str(cert_cfg.get("mode", "enforce") or "enforce").strip().lower()
        self.cert_mode = mode if mode in {"enforce", "shadow"} else "enforce"
        self.pause_scheduled_until_burn_in = bool(runtime_cfg.get("pause_scheduled_until_burn_in", True)) and bool(self.cert_mode == "enforce")
        self.cert_state_path = Path(str(cert_cfg.get("state_path", "data/results/research/state/certification_state.json")))

    def _load_config(self) -> Dict[str, Any]:
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                if not isinstance(config, dict):
                    raise ValueError("research config must be a mapping")
                logger.info("Research policy loaded: %s", self.config_path)
                return config
            logger.warning("Research policy not found: %s, using defaults", self.config_path)
            return self._default_config()
        except Exception as e:
            logger.error("Failed to load research config: %s", e)
            return self._default_config()

    @staticmethod
    def _default_config() -> Dict[str, Any]:
        return {
            "freeze_active": True,
            "freeze_start_ist": "2026-02-17",
            "freeze_days": 60,
            "modules_enabled": {
                "strategy_lab": True,
                "regime_lab": True,
                "covariance_lab": False,
                "monte_carlo_lab": False,
                "parameter_optimizer": False,
            },
            "output_restrictions": {
                "mark_non_actionable_during_freeze": True,
                "require_manual_promotion": True,
                "block_auto_parameter_deployment": True,
            },
            "scheduling": {
                "run_during_market_hours": False,
            },
            "runtime_policy": {
                "enable_legacy_labs": False,
                "pause_scheduled_until_burn_in": True,
            },
            "historical_research": {
                "enabled": True,
                "strict_real_data_only": True,
                "no_synthetic_fallbacks": True,
                "strict_bayesian_only": True,
                "dataset": {
                    "target_col": "forward_return_5d",
                    "lookback_days": 3650,
                    "max_tickers": 250,
                    "max_rows": 200000,
                    "target_horizon_days": 5,
                    "use_et500_features": False,
                    "use_et500_universe_filter": False,
                    "et500_membership_path": "data/reference/et500_pit_membership.csv",
                    "use_screener_features": False,
                    "screener_fundamentals_path": "data/canonical/fundamentals/fundamentals_annual_panel.csv",
                    "screener_shareholding_path": "data/canonical/fundamentals/shareholding_quarterly.csv",
                    "use_alternative_features": False,
                    "alternative_data_path": "data/canonical/alternative/",
                    "use_sentiment_features": False,
                    "use_sentiment_regime": False,
                    "sentiment_path": "data/canonical/sentiment/company_sentiment_daily.parquet",
                    "market_sentiment_path": "data/canonical/sentiment/market_sentiment_daily.parquet",
                    "sentiment_duckdb_path": "data/sentiment.duckdb",
                    "use_macro_features": False,
                    "macro_features_path": "data/canonical/macro/macro_regime_features.parquet",
                    "strict_real_data_only": True,
                    "strict_required_artifacts": [
                        "prices",
                        "fundamentals",
                        "macro",
                        "valuation_posterior",
                    ],
                },
                "training": {
                    "train_periods": 756,
                    "valid_periods": 126,
                    "test_periods": 126,
                    "step_periods": 63,
                    "max_windows": 8,
                    "holdout_train_end_date": None,
                    "holdout_test_start_date": None,
                    "holdout_test_end_date": None,
                    "holdout_valid_periods": None,
                    "holdout_min_train_periods": 252,
                },
                "candidate_acceptance_threshold": 0.65,
                "portfolio_construction": {
                    "long_short_quantile": 0.20,
                    "min_assets_per_day": 8,
                    "max_weight_per_asset": 0.10,
                    "use_vol_scaling": True,
                    "rebalance_frequency_days": 1,
                    "sector_neutralize": False,
                    "max_sector_weight": 1.0,
                    "transaction_cost_bps_per_side": 5.0,
                },
                "structural_promotion_gate": {
                    "enabled": False,
                    "min_peak_horizon": 80,
                    "min_half_life_horizon": 80,
                    "min_monotonicity_score": 0.80,
                    "min_peak_ic": 0.05,
                },
                "alpha_factory": {
                    "enabled": False,
                    "output_dir": "data/results/research/alpha_factory",
                    "max_rows": 120000,
                    "window_isolated_oos": True,
                    "oos_train_periods": 756,
                    "oos_valid_periods": 126,
                    "oos_test_periods": 126,
                    "oos_step_periods": 63,
                    "oos_max_windows": 4,
                    "oos_start_window": 0,
                    "non_overlap_stride_override": 0,
                    "min_obs_per_day": 25,
                    "min_abs_ic": 0.01,
                    "min_sign_consistency": 0.55,
                    "min_t_stat": 0.0,
                    "corr_prune_threshold": 0.85,
                    "min_features_per_family": 1,
                    "max_features_per_family": 20,
                    "long_short_quantile": 0.20,
                    "target_annual_vol": 0.15,
                    "covariance_shrinkage": 0.65,
                    "covariance_eigen_floor": 1e-4,
                    "covariance_ridge": 1e-6,
                    "allocation_turnover_cap": 0.20,
                    "theoretical_base_ic": 0.02,
                    "theoretical_n_signals": 200,
                    "theoretical_corr_grid": [0.05, 0.10, 0.20],
                },
                "enable_deep_models": False,
                "enable_hyperopt": False,
                "mc_paths": 3000,
                "mc_horizon": 20,
                "enabled_models": [
                    "lightgbm",
                    "xgboost",
                    "catboost",
                    "random_forest",
                    "lstm",
                    "tcn",
                    "transformer",
                ],
                "certification": {
                    "enabled": True,
                    "mode": "enforce",
                    "state_path": "data/results/research/state/certification_state.json",
                    "transaction_cost_floor_bps": 5.0,
                    "burn_in_cycles_required": 20,
                    "burn_in_regimes_required": 2,
                    "allow_single_regime_provisional": True,
                    "max_pairwise_corr": 0.99,
                    "max_holdings_overlap": 0.95,
                    "overlap_persistence_threshold": 0.70,
                    "turnover_zero_streak_limit": 3,
                    "turnover_min_rebalances": 10,
                    "min_exposure_variance": 1.0e-4,
                    "max_family_weight_hard": 0.45,
                    "max_family_weight_soft": 0.35,
                    "corr_drift_hard": 0.10,
                    "min_family_entropy": 0.55,
                    "allocation_l1_step_max": 0.35,
                    "allocation_l1_streak_limit": 3,
                    "regime_effectiveness_min_delta_sharpe": 0.15,
                    "regime_effectiveness_min_delta_return_ann": 0.015,
                    "regime_effectiveness_min_delta_dd": 0.01,
                    "min_trials_weekday": 12,
                    "min_trials_weekend": 20,
                    "min_objective_variance": 1e-6,
                    "max_rolling_param_stability": 0.35,
                    "bootstrap_sharpe_p05_min": 0.0,
                    "block_bootstrap_dd_p95_max": 0.35,
                    "ruin_x1_max": 0.02,
                    "ruin_x2_max": 0.07,
                    "ruin_x3_max": 0.15,
                    "sample_coverage_min": 1.0,
                    "regime_coverage_min": 0.67,
                    "bootstrap_conf_width_max": 1.5,
                    "advisory_persistence_limit": 5,
                    "max_certification_runtime_sec": 180,
                    "max_certification_runtime_share": 0.60,
                    "max_cycle_runtime_sec": 2400,
                    "max_peak_rss_mb": 4096,
                    "max_threads": 1,
                    "lineage_min_cv": 1e-5,
                    "lineage_min_obs": 5,
                    "lineage_max_unexplained_flatlines": 12,
                    "require_macro_unit_metadata": False,
                    "macro_percent_abs_expected_change_max": 1.0,
                    "macro_fx_abs_expected_change_max": 0.25,
                    "shadow_relaxed_audit_enabled": True,
                    "shadow_relaxed_threshold_factor": 1.20,
                    "belief_min_history_days_for_strict_eval": 20,
                },
            },
        }

    def _initialize_modules(self) -> None:
        enabled_modules = self.config.get("modules_enabled", {})

        if enabled_modules.get("strategy_lab", False):
            from .strategy_lab import StrategyLab

            self.modules["strategy_lab"] = StrategyLab()

        if enabled_modules.get("regime_lab", False):
            from .regime_lab import RegimeLab

            self.modules["regime_lab"] = RegimeLab()

        if enabled_modules.get("covariance_lab", False):
            from .covariance_lab import CovarianceLab

            self.modules["covariance_lab"] = CovarianceLab()

        if enabled_modules.get("monte_carlo_lab", False):
            from .monte_carlo_lab import MonteCarloLab

            self.modules["monte_carlo_lab"] = MonteCarloLab()

        if enabled_modules.get("parameter_optimizer", False):
            from .parameter_optimizer import ParameterOptimizer

            self.modules["parameter_optimizer"] = ParameterOptimizer()

        logger.info("Research legacy modules initialized: %s", list(self.modules.keys()))

    def is_freeze_active(self) -> bool:
        if not self.config.get("freeze_active", False):
            return False

        try:
            freeze_start = datetime.fromisoformat(str(self.config["freeze_start_ist"])).date()
            freeze_days = int(self.config.get("freeze_days", 60) or 60)
            freeze_end = freeze_start + timedelta(days=freeze_days)
            today = date.today()
            return freeze_start <= today <= freeze_end
        except Exception as e:
            logger.error("Error checking freeze status: %s", e)
            return True

    def run_research_cycle(self, market_data: Dict[str, Any], system_state: Dict[str, Any]) -> Dict[str, Any]:
        cycle_start = datetime.now()
        is_market_hours = self._resolve_market_hours(market_data=market_data, system_state=system_state)
        run_during_market_hours = bool(self.config.get("scheduling", {}).get("run_during_market_hours", False))
        results: Dict[str, Any] = {
            "timestamp": cycle_start.isoformat(),
            "freeze_active": self.is_freeze_active(),
            "mode_boundary": {
                "current_mode": str(system_state.get("current_mode", "unknown")),
                "is_market_hours": bool(is_market_hours),
                "run_during_market_hours": bool(run_during_market_hours),
            },
            "modules_run": [],
            "outputs_generated": [],
            "actionable_outputs": [],
            "non_actionable_outputs": [],
            "errors": [],
        }

        if not self._should_run_research(market_data=market_data, system_state=system_state):
            results["skipped"] = True
            results["skip_reason"] = self._skip_reason(market_data=market_data, system_state=system_state)
            # Persist skipped cycles as first-class artifacts so orchestrators
            # can report them correctly instead of reusing stale prior cycles.
            self._save_cycle_results(results)
            return results

        # 1) Historical research controller (new primary path).
        if self.historical_controller_enabled:
            try:
                c = self.controller.run(system_state=system_state, freeze_active=bool(results["freeze_active"]))
                outputs = c.get("outputs", []) if isinstance(c, dict) else []
                if outputs:
                    module_result = {
                        "module": "historical_research_controller",
                        "outputs": outputs,
                    }
                    module_result = self._apply_freeze_policy(module_result)
                    results["modules_run"].append("historical_research_controller")
                    self._collect_outputs(results, module_result)
                if isinstance(c, dict) and c.get("errors"):
                    for e in c.get("errors", []):
                        results["errors"].append(str(e))
            except Exception as e:
                msg = f"historical_research_controller failed: {e}"
                logger.error(msg, exc_info=True)
                results["errors"].append(msg)

        # 2) Legacy labs: disabled by default for canonical certification runtime.
        if self.legacy_labs_enabled:
            for module_name, module in self.modules.items():
                try:
                    logger.info("Running research module: %s", module_name)
                    module_results = module.run_analysis(market_data, system_state)
                    module_results = self._apply_freeze_policy(module_results)
                    results["modules_run"].append(module_name)
                    self._collect_outputs(results, module_results)
                except Exception as e:
                    error_msg = f"Module {module_name} failed: {e}"
                    logger.error(error_msg)
                    results["errors"].append(error_msg)
        else:
            results["modules_run"].append("legacy_labs_skipped")

        self._save_cycle_results(results)
        self._save_structured_outputs(results)
        self._register_candidates(results)
        self._generate_nightly_report()

        cycle_duration = (datetime.now() - cycle_start).total_seconds()
        logger.info(
            "Research cycle completed in %.1fs: modules=%s actionable=%s errors=%s",
            cycle_duration,
            len(results["modules_run"]),
            len(results["actionable_outputs"]),
            len(results["errors"]),
        )
        return results

    @staticmethod
    def _collect_outputs(results: Dict[str, Any], module_results: Dict[str, Any]) -> None:
        outputs = module_results.get("outputs", []) if isinstance(module_results, dict) else []
        for output in outputs:
            results["outputs_generated"].append(output)
            if output.get("actionable", True):
                results["actionable_outputs"].append(output)
            else:
                results["non_actionable_outputs"].append(output)

    def _resolve_market_hours(self, market_data: Dict[str, Any], system_state: Dict[str, Any]) -> bool:
        # Priority: explicit flags from orchestrators.
        for payload in (market_data, system_state):
            if isinstance(payload, dict):
                if isinstance(payload.get("is_market_hours"), bool):
                    return bool(payload.get("is_market_hours"))
                ms = payload.get("market_status")
                if isinstance(ms, dict):
                    if isinstance(ms.get("is_market_hours"), bool):
                        return bool(ms.get("is_market_hours"))
                    status = str(ms.get("market_status", "")).strip().lower()
                    if status in {"open", "market_hours"}:
                        return True
                    if status in {"closed", "post_market", "pre_market"}:
                        return False
        # Fallback to IST market window.
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        if now.weekday() >= 5:
            return False
        return bool((now.hour > 9 or (now.hour == 9 and now.minute >= 30)) and (now.hour < 15 or (now.hour == 15 and now.minute <= 30)))

    def _should_run_research(self, market_data: Dict[str, Any], system_state: Dict[str, Any]) -> bool:
        current_mode = system_state.get("current_mode", "normal_operation")
        if current_mode in ["survival_core", "recovery_mode"]:
            return False
        if system_state.get("research_throttled", False):
            return False
        if self.pause_scheduled_until_burn_in:
            if (not self._is_manual_run(system_state)) and (not self._burn_in_certification_passed()):
                return False
        if not bool(self.config.get("scheduling", {}).get("run_during_market_hours", False)):
            if self._resolve_market_hours(market_data=market_data, system_state=system_state):
                return False
        return True

    def _skip_reason(self, market_data: Dict[str, Any], system_state: Dict[str, Any]) -> str:
        current_mode = system_state.get("current_mode", "normal_operation")
        if current_mode in ["survival_core", "recovery_mode"]:
            return f"blocked_by_mode:{current_mode}"
        if system_state.get("research_throttled", False):
            return "research_throttled"
        if self.pause_scheduled_until_burn_in:
            if (not self._is_manual_run(system_state)) and (not self._burn_in_certification_passed()):
                return "certification_burn_in_incomplete"
        if not bool(self.config.get("scheduling", {}).get("run_during_market_hours", False)):
            if self._resolve_market_hours(market_data=market_data, system_state=system_state):
                return "market_hours_guard"
        return "research_disabled"

    @staticmethod
    def _is_manual_run(system_state: Dict[str, Any]) -> bool:
        if bool(system_state.get("manual_run", False)):
            return True
        trigger = str(system_state.get("trigger_source", "")).strip().lower()
        return trigger in {"manual", "operator", "cli"}

    def _burn_in_certification_passed(self) -> bool:
        try:
            if not self.cert_state_path.exists():
                return False
            payload = json.loads(self.cert_state_path.read_text())
            burn = payload.get("burn_in", {}) if isinstance(payload, dict) else {}
            return bool((burn or {}).get("certification_passed", False))
        except Exception:
            return False

    def _apply_freeze_policy(self, module_results: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_freeze_active():
            return module_results

        restricted_types = {
            "parameter_search",
            "strategy_optimization",
            "model_promotion",
            "candidate_model",
        }

        for output in module_results.get("outputs", []):
            otype = str(output.get("type", "")).strip().lower()
            if otype in restricted_types:
                output["actionable"] = False
                output["freeze_restriction"] = True
                output["restriction_reason"] = "Research freeze active - output marked non-actionable"
        return module_results

    def _save_cycle_results(self, results: Dict[str, Any]) -> None:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.research_cycle_dir / timestamp[:4] / timestamp[4:6] / f"research_cycle_{timestamp}.json"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, default=str)
            logger.debug("Research cycle results saved: %s", output_file)
        except Exception as e:
            logger.error("Failed to save research cycle results: %s", e)

    def _save_structured_outputs(self, results: Dict[str, Any]) -> None:
        output_map = {
            "strategy_stability.json": [],
            "regime_candidate_scores.json": [],
            "covariance_health.json": [],
            "alpha_factory_report.json": [],
            "monte_carlo_report.json": [],
            "parameter_search_results.json": [],
            "model_training_results.json": [],
            "capital_simulation_report.json": [],
            "research_kernel_status.json": [],
            "returns_partition.json": [],
            "research_awareness.json": [],
            "options_research_opportunities.json": [],
            "weekend_research_sweep.json": [],
            "relationship_discovery.json": [],
            "autonomous_exploration.json": [],
            "integrity_summary.json": [],
        }

        for output in results.get("outputs_generated", []):
            otype = str(output.get("type", "")).strip().lower()

            if otype in {"strategy_performance_analysis", "strategy_recommendations", "model_validation"}:
                output_map["strategy_stability.json"].append(output)
            if otype in {"regime_assessment", "regime_transition_analysis", "regime_strategy_recommendations", "regime_rl_policy", "regime_sliced_performance"}:
                output_map["regime_candidate_scores.json"].append(output)
            if "covariance" in otype:
                output_map["covariance_health.json"].append(output)
            if otype == "alpha_factory":
                output_map["alpha_factory_report.json"].append(output)
            if "monte_carlo" in otype:
                output_map["monte_carlo_report.json"].append(output)
            if otype in {"parameter_search", "parameter_sensitivity"}:
                if otype == "parameter_sensitivity":
                    payload = output.get("data") if isinstance(output.get("data"), dict) else {}
                    if str(payload.get("status", "")).strip().lower() == "skipped_no_real_sensitivity_engine":
                        continue
                output_map["parameter_search_results.json"].append(output)
            if otype in {"model_validation", "model_promotion"}:
                output_map["model_training_results.json"].append(output)
            if otype == "capital_simulation":
                output_map["capital_simulation_report.json"].append(output)
            if otype in {"research_dataset", "integration_bridge"}:
                output_map["research_kernel_status.json"].append(output)
            if otype == "returns_partition":
                output_map["returns_partition.json"].append(output)
            if otype == "research_self_awareness":
                output_map["research_awareness.json"].append(output)
            if otype == "options_research_opportunities":
                output_map["options_research_opportunities.json"].append(output)
            if otype == "weekend_research_sweep":
                output_map["weekend_research_sweep.json"].append(output)
            if otype == "relationship_discovery":
                output_map["relationship_discovery.json"].append(output)
            if otype == "autonomous_exploration":
                output_map["autonomous_exploration.json"].append(output)
            if otype == "integrity_summary":
                output_map["integrity_summary.json"].append(output)

        timestamp = datetime.now().isoformat()
        for file_name, payload in output_map.items():
            if not payload:
                continue
            target = self.research_state_dir / file_name
            with open(target, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "timestamp": timestamp,
                        "freeze_active": bool(results.get("freeze_active", False)),
                        "data": payload,
                    },
                    handle,
                    indent=2,
                    default=str,
                )

    def _register_candidates(self, results: Dict[str, Any]) -> None:
        try:
            from .model_registry import ModelRegistry

            registry = ModelRegistry()
            candidate_types = {"candidate_model", "model_promotion", "parameter_search"}
            for idx, output in enumerate(results.get("actionable_outputs", []), start=1):
                otype = str(output.get("type", "candidate")).strip().lower() or "candidate"
                if otype not in candidate_types:
                    continue
                safe_type = "".join(ch if ch.isalnum() else "_" for ch in otype).strip("_") or "candidate"
                model_id = f"{safe_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{idx}"
                registry.register_candidate(
                    model_id=model_id,
                    payload={
                        "type": otype,
                        "version": datetime.now().strftime("%Y%m%d%H%M%S"),
                        "freeze_active": bool(results.get("freeze_active", False)),
                        "validation_metrics": output.get("data", {}),
                        "promotion_blocked": bool(results.get("freeze_active", False)),
                    },
                )
        except Exception as e:
            logger.warning("Candidate registration skipped: %s", e)

    def _generate_nightly_report(self) -> None:
        try:
            from .report_generator import generate_nightly_report

            report_path = generate_nightly_report(self.research_cycle_dir)
            logger.info("Nightly report generated: %s", report_path)
        except Exception as e:
            logger.warning("Nightly report generation failed: %s", e)

    def get_research_status(self) -> Dict[str, Any]:
        return {
            "timestamp": datetime.now().isoformat(),
            "freeze_active": self.is_freeze_active(),
            "modules_available": list(self.modules.keys()),
            "historical_controller_enabled": bool(self.historical_controller_enabled),
            "config_loaded": self.config_path.exists(),
            "output_directory": str(self.research_cycle_dir),
            "state_directory": str(self.research_state_dir),
            "freeze_config": {
                "freeze_start": self.config.get("freeze_start_ist"),
                "freeze_days": self.config.get("freeze_days"),
                "freeze_end": self._get_freeze_end_date(),
            },
        }

    def _get_freeze_end_date(self) -> Optional[str]:
        try:
            if not self.config.get("freeze_active", False):
                return None
            freeze_start = datetime.fromisoformat(str(self.config["freeze_start_ist"])).date()
            freeze_days = int(self.config.get("freeze_days", 60) or 60)
            return (freeze_start + timedelta(days=freeze_days)).isoformat()
        except Exception:
            return None
