"""Master research controller: historical kernel + model ecosystem + governance-safe outputs."""

from __future__ import annotations

import copy
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from .candidate_scorer import CandidateScorer
from .capital_allocator_bridge import CapitalAllocatorBridge
from .capital_simulator import CapitalSimulator
from .certification import CertificationContext, CertificationEvaluator
from .alpha_factory import (
    apply_family_feature_weights,
    build_family_factor_table,
    build_feature_family_map,
    compute_live_monitoring_metrics,
    optimize_family_blend,
    simulate_signal_stacking,
)
from .alpha_lab import AlphaHypothesis, AlphaLabController
from .dataset_manager import DatasetManager
from .diagnostics import compute_feature_ic_diagnostics, write_ic_report
from .ensemble import StackingMetaLearner, WeightedEnsemble
from .experiment_tracker import ExperimentTracker
from .hyperopt import BayesianOptimizer
from .model_adapters import (
    CatBoostModel,
    DynamicFactorModel,
    HMMRegimeModel,
    LSTMModel,
    LightGBMModel,
    RandomForestModel,
    TCNModel,
    TransformerModel,
    XGBoostModel,
)
from .shap_validator import compute_feature_importance
from .mutation_engine import MutationEngine
from .portfolio_governor_bridge import PortfolioGovernorBridge
from .research_memory import ResearchMemory
from .research_types import ResearchDataset
from .reinforcement_regime_agent import RegimeSwitchAgent
from .regime_split import split_by_regime
from .splits import rolling_time_splits
from .structural_monte_carlo import StructuralMonteCarlo
from .training_pipeline import TrainingPipeline
from .walk_forward_validator import build_cross_sectional_portfolio_returns, _period_to_daily_returns


logger = logging.getLogger(__name__)
_TRADE_ID_TS_RE = re.compile(r"^POS_(\d{8})_(\d{6})_")


class ResearchController:
    """Full historical research loop (offline only)."""

    _CANONICAL_BASE_MODELS: Tuple[str, ...] = (
        "lightgbm",
        "xgboost",
        "catboost",
        "random_forest",
        "lstm",
        "tcn",
        "transformer",
    )
    _DEEP_MODELS = {"lstm", "tcn", "transformer"}
    _MODEL_ALIASES = {
        "lightgbm": "lightgbm",
        "lightbgm": "lightgbm",
        "xgboost": "xgboost",
        "catboost": "catboost",
        "random_forest": "random_forest",
        "randomforest": "random_forest",
        "random_forrest": "random_forest",
        "lstm": "lstm",
        "tcn": "tcn",
        "transformer": "transformer",
        "weighted_ensemble_top3": "weighted_ensemble_top3",
        "stacking_meta_top3": "stacking_meta_top3",
    }

    def __init__(self, config: Dict[str, Any] | None = None, project_root: Path | None = None):
        self.config = copy.deepcopy(config or {})
        self.project_root = Path(project_root) if project_root else Path(".")
        self.low_resource_mode = self._is_low_resource_mode()
        if self.low_resource_mode:
            self._apply_low_resource_overrides()
        self._enforce_certification_defaults()

        dataset_cfg = dict(self.config.get("dataset", {}))
        training_cfg = dict(self.config.get("training", {}))
        if "min_tickers_per_date" in training_cfg and "min_tickers_per_date" not in dataset_cfg:
            dataset_cfg["min_tickers_per_date"] = int(training_cfg.get("min_tickers_per_date", 50))
        dataset_cfg.setdefault("training_train_periods", int(training_cfg.get("train_periods", 756)))
        dataset_cfg.setdefault("training_valid_periods", int(training_cfg.get("valid_periods", 126)))
        dataset_cfg.setdefault("training_test_periods", int(training_cfg.get("test_periods", 126)))
        dataset_cfg.setdefault("training_step_periods", int(training_cfg.get("step_periods", 63)))
        dataset_cfg.setdefault("training_min_tickers_per_date", int(training_cfg.get("min_tickers_per_date", 50)))
        dataset_cfg.setdefault("training_max_windows", int(training_cfg.get("max_windows", 12)))
        if "low_resource_mode" in self.config and "low_resource_mode" not in dataset_cfg:
            dataset_cfg["low_resource_mode"] = self.config.get("low_resource_mode")
        if "low_resource_max_memory_gb" in self.config and "low_resource_max_memory_gb" not in dataset_cfg:
            dataset_cfg["low_resource_max_memory_gb"] = self.config.get("low_resource_max_memory_gb")
        self.dataset_manager = DatasetManager(project_root=self.project_root, config=dataset_cfg)

        self.pipeline = TrainingPipeline(
            train_periods=int(training_cfg.get("train_periods", 756)),
            valid_periods=int(training_cfg.get("valid_periods", 126)),
            test_periods=int(training_cfg.get("test_periods", 126)),
            step_periods=int(training_cfg.get("step_periods", 63)),
            min_tickers_per_date=int(training_cfg.get("min_tickers_per_date", 50)),
            max_windows=int(training_cfg.get("max_windows", 10)),
            start_window=int(training_cfg.get("start_window", 0)),
            portfolio_cfg=dict(self.config.get("portfolio_construction", {})),
            **self._holdout_training_kwargs(),
        )

        self.scorer = CandidateScorer()
        self.tracker = ExperimentTracker(path=str(self.config.get("experiment_path", "data/results/research/trackers/experiments.ndjson")))
        self.memory = ResearchMemory(path=str(self.config.get("memory_path", "data/results/research/state/research_memory.json")))
        self.mutator = MutationEngine(random_state=int(self.config.get("random_state", 42)))
        self.capital_sim = CapitalSimulator(
            initial_capital=float(self.config.get("simulation_initial_capital", 1_000_000.0)),
            max_abs_period_return=float(self.config.get("simulation_max_abs_period_return", 0.25)),
            max_abs_weight=float(self.config.get("simulation_max_abs_weight", 0.35)),
        )
        self.allocator_bridge = CapitalAllocatorBridge()
        self.governor_bridge = PortfolioGovernorBridge()

        self.rl_agent = RegimeSwitchAgent(n_regimes=3, n_actions=max(1, len(self._model_specs())), random_state=int(self.config.get("random_state", 42)))
        self.optimizer = BayesianOptimizer(
            n_calls=int(self.config.get("hyperopt_calls", 12)),
            random_state=int(self.config.get("random_state", 42)),
            strict_gp_only=bool(self.config.get("strict_bayesian_only", True)),
        )
        self.certifier = CertificationEvaluator(project_root=self.project_root, config=self.config)

    def _enforce_certification_defaults(self) -> None:
        cert_cfg = dict(self.config.get("certification", {}))
        if not cert_cfg:
            return
        portfolio_cfg = self.config.setdefault("portfolio_construction", {})
        experiment_only = bool(self.config.get("experiment_only_run", False))
        if experiment_only:
            return
        floor = float(cert_cfg.get("transaction_cost_floor_bps", 5.0))
        cur = float(portfolio_cfg.get("transaction_cost_bps_per_side", 0.0) or 0.0)
        if cur <= 0.0 and floor > 0.0:
            portfolio_cfg["transaction_cost_bps_per_side"] = float(floor)

    def _certification_cfg(self) -> Dict[str, Any]:
        return dict(self.config.get("certification", {}))

    def _certification_enabled(self) -> bool:
        return bool(self._certification_cfg().get("enabled", True))

    def _certification_mode(self) -> str:
        mode = str(self._certification_cfg().get("mode", "enforce") or "enforce").strip().lower()
        return mode if mode in {"enforce", "shadow"} else "enforce"

    def _apply_certification_policy(
        self,
        *,
        outputs: List[Dict[str, Any]],
        cert_payload: Dict[str, Any],
        errors: List[str],
        summary: Dict[str, Any],
    ) -> None:
        integrity = cert_payload.get("integrity_summary", {}) if isinstance(cert_payload, dict) else {}
        hard_fail = bool((integrity or {}).get("hard_fail_triggered", False))
        cert_pass = bool((integrity or {}).get("certification_passed", False))
        mode = self._certification_mode()
        enforce = bool(mode == "enforce")

        for out in outputs:
            if not isinstance(out, dict):
                continue
            otype = str(out.get("type", "")).strip().lower()
            if otype == "model_promotion":
                data = out.get("data", {})
                if isinstance(data, dict):
                    data["integrity_summary"] = integrity
                    data["model_risk_tier"] = cert_payload.get("model_risk_tier", {})
                    out["data"] = data
            if hard_fail and enforce and otype in {"parameter_search", "candidate_model", "model_promotion"}:
                out["actionable"] = False
                out["integrity_blocked"] = True
                out["integrity_block_reason"] = "critical_certification_failure"
            elif hard_fail and (not enforce) and otype in {"parameter_search", "candidate_model", "model_promotion"}:
                out["integrity_shadow_violation"] = True

        if hard_fail and enforce:
            errors.append("certification_hard_fail")
        summary["certification_mode"] = mode
        summary["certification_passed"] = bool(cert_pass)

    def _register_certification_snapshot(self, cert_payload: Dict[str, Any]) -> None:
        """Persist certification snapshot into PRS store when available."""
        if not isinstance(cert_payload, dict):
            return
        snapshot = cert_payload.get("certification_snapshot", {})
        if not isinstance(snapshot, dict):
            return
        required = {
            "snapshot_hash",
            "model_hash",
            "param_hash",
            "feature_hash",
            "data_revision_hash",
            "config_hash",
            "created_at",
            "valid_until",
            "drift_guard_version",
        }
        if not required.issubset(snapshot.keys()):
            return
        try:
            from src.runtime.contracts import CertificationSnapshot
            from src.runtime.storage import RuntimeEventStore

            db_path = self.project_root / str(
                self.config.get("runtime_db_path", "data/runtime/portfolio_runtime.db")
            )
            store = RuntimeEventStore(str(db_path))
            cert = CertificationSnapshot(
                snapshot_hash=str(snapshot.get("snapshot_hash", "")),
                model_hash=str(snapshot.get("model_hash", "")),
                param_hash=str(snapshot.get("param_hash", "")),
                feature_hash=str(snapshot.get("feature_hash", "")),
                data_revision_hash=str(snapshot.get("data_revision_hash", "")),
                config_hash=str(snapshot.get("config_hash", "")),
                created_at=datetime.fromisoformat(str(snapshot.get("created_at"))),
                valid_until=datetime.fromisoformat(str(snapshot.get("valid_until"))),
                drift_guard_version=str(snapshot.get("drift_guard_version", "v1") or "v1"),
            )
            store.insert_certification_snapshot(cert)
            store.close()
        except Exception as exc:
            logger.warning("Could not persist certification snapshot to PRS store: %s", exc)

    def _holdout_training_kwargs(self) -> Dict[str, Any]:
        tcfg = dict(self.config.get("training", {}))
        out: Dict[str, Any] = {}
        if tcfg.get("holdout_train_end_date"):
            out["holdout_train_end_date"] = str(tcfg.get("holdout_train_end_date"))
        if tcfg.get("holdout_test_start_date"):
            out["holdout_test_start_date"] = str(tcfg.get("holdout_test_start_date"))
        if tcfg.get("holdout_test_end_date"):
            out["holdout_test_end_date"] = str(tcfg.get("holdout_test_end_date"))
        if tcfg.get("holdout_valid_periods") is not None:
            out["holdout_valid_periods"] = int(tcfg.get("holdout_valid_periods"))
        if tcfg.get("holdout_min_train_periods") is not None:
            out["holdout_min_train_periods"] = int(tcfg.get("holdout_min_train_periods"))
        return out

    def _alpha_lab_enabled(self, *, weekend_run: bool) -> bool:
        cfg = dict(self.config.get("alpha_lab", {}))
        if not bool(cfg.get("enabled", False)):
            return False
        if bool(cfg.get("weekend_only", True)) and (not weekend_run):
            return False
        return True

    @staticmethod
    def _alpha_lab_grid(base_params: Dict[str, Any], *, max_tunable: int = 2) -> Dict[str, List[Any]]:
        out: Dict[str, List[Any]] = {}
        tunable = 0
        for key, value in sorted(dict(base_params or {}).items()):
            if tunable >= max_tunable:
                break
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                lo = max(1, int(round(value * 0.9)))
                hi = max(1, int(round(value * 1.1)))
                vals = sorted({int(lo), int(value), int(hi)})
                if len(vals) > 1:
                    out[str(key)] = vals
                    tunable += 1
            elif isinstance(value, float):
                lo = float(value * 0.9)
                hi = float(value * 1.1)
                vals = sorted({round(lo, 8), round(float(value), 8), round(hi, 8)})
                if len(vals) > 1:
                    out[str(key)] = vals
                    tunable += 1
        return out

    def _run_alpha_lab(
        self,
        *,
        dataset: ResearchDataset,
        model_specs: List[Tuple[str, Dict[str, Any]]],
    ) -> Dict[str, Any]:
        lab_cfg = dict(self.config.get("alpha_lab", {}))
        max_hyp = int(lab_cfg.get("max_hypotheses", 3))
        max_hyp = max(1, max_hyp)
        selected = model_specs[:max_hyp]
        hypotheses: List[AlphaHypothesis] = []

        for name, params in selected:
            base_params = dict(params or {})

            def _factory(p: Dict[str, Any], _name=name, _base=base_params):
                merged = dict(_base)
                merged.update(dict(p or {}))
                return self._build_model(_name, merged)

            hypotheses.append(
                AlphaHypothesis(
                    name=f"{name}_alpha_lab",
                    model_factory=_factory,
                    parameter_grid=self._alpha_lab_grid(base_params, max_tunable=int(lab_cfg.get("max_tunable_params", 2))),
                    tags={"source_model": name},
                )
            )

        lab = AlphaLabController(pipeline=self.pipeline)
        suite = lab.run_hypothesis_suite(dataset=dataset, hypotheses=hypotheses)
        promotions = lab.promote_survivors(suite.get("survivors", []))
        lab.store.close()
        return {
            "enabled": True,
            "evaluated_count": int(suite.get("evaluated_count", 0)),
            "survivor_count": int(suite.get("survivor_count", 0)),
            "promotions": promotions,
            "survivors": suite.get("survivors", []),
        }

    def _host_memory_gb(self) -> float:
        try:
            import psutil  # type: ignore

            return float(psutil.virtual_memory().total / (1024 ** 3))
        except Exception:
            return 0.0

    def _is_low_resource_mode(self) -> bool:
        env = str(os.getenv("NORTHSTAR_LOW_RESOURCE_PROFILE", "")).strip().lower()
        if env in {"1", "true", "yes", "on"}:
            return True
        if env in {"0", "false", "no", "off"}:
            return False

        cfg = str(self.config.get("low_resource_mode", "auto")).strip().lower()
        if cfg in {"1", "true", "yes", "on", "enabled"}:
            return True
        if cfg in {"0", "false", "no", "off", "disabled"}:
            return False

        mem_gb = self._host_memory_gb()
        if mem_gb > 0:
            return mem_gb <= float(self.config.get("low_resource_max_memory_gb", 10.5))
        return False

    def _apply_low_resource_overrides(self) -> None:
        dataset_cfg = self.config.setdefault("dataset", {})
        training_cfg = self.config.setdefault("training", {})
        budget_cfg = self.config.setdefault("autonomous_budget", {})
        exploration_cfg = self.config.setdefault("autonomous_exploration", {})
        weekend_cfg = self.config.setdefault("weekend_only_tasks", {})
        model_params = self.config.setdefault("model_params", {})

        dataset_cfg["max_rows"] = min(int(dataset_cfg.get("max_rows", 200000)), 90000)
        dataset_cfg["max_tickers"] = min(int(dataset_cfg.get("max_tickers", 250)), 140)
        dataset_cfg["lookback_days"] = min(int(dataset_cfg.get("lookback_days", 3650)), 2200)
        dataset_cfg["duckdb_memory_limit_mb"] = min(int(dataset_cfg.get("duckdb_memory_limit_mb", 768)), 768)
        dataset_cfg["duckdb_threads"] = 1
        dataset_cfg["low_resource_mode"] = True

        training_cfg["max_windows"] = min(int(training_cfg.get("max_windows", 8)), 2)

        budget_cfg["max_models_weekday"] = min(int(budget_cfg.get("max_models_weekday", 4)), 2)
        budget_cfg["max_models_weekend"] = min(int(budget_cfg.get("max_models_weekend", 6)), 3)
        budget_cfg["mc_paths_weekday"] = min(int(budget_cfg.get("mc_paths_weekday", self.config.get("mc_paths", 3000))), 1000)
        budget_cfg["mc_horizon_weekday"] = min(int(budget_cfg.get("mc_horizon_weekday", self.config.get("mc_horizon", 20))), 12)
        budget_cfg["mc_paths_weekend"] = min(int(budget_cfg.get("mc_paths_weekend", self.config.get("weekend_mc_paths", 6000))), 1800)
        budget_cfg["mc_horizon_weekend"] = min(int(budget_cfg.get("mc_horizon_weekend", self.config.get("weekend_mc_horizon", 30))), 20)
        budget_cfg["model_priority"] = [
            "lightgbm",
            "xgboost",
            "catboost",
            "random_forest",
            "transformer",
            "lstm",
            "tcn",
        ]

        exploration_cfg["variants_weekday"] = 0
        exploration_cfg["variants_weekend"] = min(int(exploration_cfg.get("variants_weekend", 3)), 1)
        weekend_cfg["extended_scenario_sweep"] = False

        # Keep deep models enabled when user explicitly requested them via config.
        requested_models = {
            self._normalize_model_name(x)
            for x in (self.config.get("enabled_models", []) or [])
            if str(x).strip()
        }
        explicit_deep_request = bool(self.config.get("enable_deep_models", False)) or bool(
            requested_models & self._DEEP_MODELS
        )
        if explicit_deep_request:
            self.config["enable_deep_models"] = True
        elif not bool(self.config.get("force_deep_models_in_low_resource", False)):
            self.config["enable_deep_models"] = False

        # Ensure tree models remain single-threaded even if external configs override defaults.
        lgb_params = model_params.setdefault("lightgbm", {})
        lgb_params["n_jobs"] = 1
        xgb_params = model_params.setdefault("xgboost", {})
        xgb_params["n_jobs"] = 1
        rf_params = model_params.setdefault("random_forest", {})
        rf_params["n_jobs"] = 1
        cb_params = model_params.setdefault("catboost", {})
        cb_params["thread_count"] = 1

        self.config["enable_ensemble"] = bool(self.config.get("enable_ensemble", False))
        self.config["disable_ensemble_in_low_resource"] = bool(
            self.config.get("disable_ensemble_in_low_resource", True)
        )
        self.config["low_resource_mode_effective"] = True

    @staticmethod
    def _progress_bar(current: int, total: int, width: int = 24) -> str:
        total = max(1, int(total))
        current = max(0, min(int(current), total))
        frac = float(current) / float(total)
        filled = int(round(width * frac))
        return f"[{'#' * filled}{'.' * (width - filled)}] {int(frac * 100):3d}%"

    def _log_stage(self, current: int, total: int, label: str, details: str | None = None) -> None:
        bar = self._progress_bar(current, total)
        suffix = f" | {details}" if details else ""
        logger.info("Research Progress %s Stage %d/%d: %s%s", bar, int(current), int(total), label, suffix)

    def _window_progress_callback(self, event: str, index: int, total: int, model: str, metrics: Dict[str, Any] | None = None) -> None:
        if event == "window_start":
            bar = self._progress_bar(index, total, width=16)
            logger.info("Model %s windows %s %d/%d started", model, bar, index, total)
            return
        if event == "window_done":
            bar = self._progress_bar(index, total, width=16)
            sharpe = float((metrics or {}).get("sharpe", 0.0))
            dd = float((metrics or {}).get("max_drawdown", 0.0))
            logger.info("Model %s windows %s %d/%d done sharpe=%.4f dd=%.4f", model, bar, index, total, sharpe, dd)

    @classmethod
    def _normalize_model_name(cls, name: Any) -> str:
        n = str(name or "").strip().lower().replace("-", "_").replace(" ", "_")
        return cls._MODEL_ALIASES.get(n, n)

    def _expected_model_names(self) -> List[str]:
        enabled = self.config.get("enabled_models")
        if isinstance(enabled, list) and enabled:
            out: List[str] = []
            for raw in enabled:
                normalized = self._normalize_model_name(raw)
                if normalized in self._CANONICAL_BASE_MODELS and normalized not in out:
                    out.append(normalized)
            if out:
                return out
        return list(self._CANONICAL_BASE_MODELS)

    def _model_specs(self) -> List[Tuple[str, Dict[str, Any]]]:
        base = [
            ("lightgbm", {"n_estimators": 240, "learning_rate": 0.03}),
            (
                "xgboost",
                {
                    "n_estimators": 200,
                    "learning_rate": 0.05,
                    "max_depth": 4,
                    "min_child_weight": 20.0,
                    "subsample": 0.8,
                    "colsample_bytree": 0.8,
                    "objective": "reg:squarederror",
                },
            ),
            ("catboost", {"iterations": 220, "depth": 6, "learning_rate": 0.03}),
            ("random_forest", {"n_estimators": 350, "max_depth": 12}),
            ("lstm", {"lookback": 60, "epochs": 10, "hidden_dim": 64, "lr": 1e-3}),
            (
                "tcn",
                {
                    "lookback": 60,
                    "epochs": 20,
                    "channels": 64,
                    "dilations": [1, 2, 4, 8],
                    "dropout": 0.2,
                    "lr": 1e-3,
                    "patience": 10,
                },
            ),
            (
                "transformer",
                {
                    "lookback": 60,
                    "epochs": 12,
                    "d_model": 128,
                    "nhead": 4,
                    "num_layers": 2,
                    "dim_feedforward": 256,
                    "dropout": 0.2,
                    "batch_size": 128,
                    "patience": 10,
                    "lr": 1e-4,
                },
            ),
        ]

        if not bool(self.config.get("enable_deep_models", False)):
            base = [(n, p) for n, p in base if n not in self._DEEP_MODELS]

        enabled = self.config.get("enabled_models")
        if isinstance(enabled, list) and enabled:
            enabled_set = {
                self._normalize_model_name(x)
                for x in enabled
                if str(x).strip()
            }
            base = [(name, params) for name, params in base if name in enabled_set]

        # Optional overrides from config.historical_research.model_params
        # Example:
        # model_params:
        #   random_forest: {n_estimators: 120, n_jobs: 1}
        cfg_overrides = self.config.get("model_params", {})
        if isinstance(cfg_overrides, dict):
            patched: List[Tuple[str, Dict[str, Any]]] = []
            for name, params in base:
                merged = dict(params)
                override = cfg_overrides.get(name, {})
                if isinstance(override, dict):
                    merged.update(override)
                patched.append((name, merged))
            return patched
        return base

    def _budget_cfg(self) -> Dict[str, Any]:
        return dict(self.config.get("autonomous_budget", {}))

    def _apply_model_budget(
        self,
        model_specs: List[Tuple[str, Dict[str, Any]]],
        *,
        weekend_run: bool,
    ) -> List[Tuple[str, Dict[str, Any]]]:
        if not model_specs:
            return model_specs
        cfg = self._budget_cfg()
        max_models_weekday = int(cfg.get("max_models_weekday", 4))
        max_models_weekend = int(cfg.get("max_models_weekend", 6))
        cap = max_models_weekend if weekend_run else max_models_weekday
        if cap <= 0 or len(model_specs) <= cap:
            return model_specs

        priority = cfg.get(
            "model_priority",
            ["transformer", "lightgbm", "xgboost", "catboost", "random_forest", "lstm", "tcn"],
        )
        rank = {str(name).lower(): i for i, name in enumerate(priority)}
        ordered = sorted(model_specs, key=lambda x: (rank.get(x[0].lower(), 999), x[0]))
        return ordered[:cap]

    def _mc_budget(self, *, weekend_run: bool) -> Dict[str, int]:
        cfg = self._budget_cfg()
        n_paths = int(
            cfg.get(
                "mc_paths_weekend" if weekend_run else "mc_paths_weekday",
                self.config.get("mc_paths", 3000),
            )
        )
        horizon = int(
            cfg.get(
                "mc_horizon_weekend" if weekend_run else "mc_horizon_weekday",
                self.config.get("mc_horizon", 20),
            )
        )
        return {"paths": max(200, n_paths), "horizon": max(5, horizon)}

    def _relationship_discovery(self, dataset: Any) -> Dict[str, Any]:
        frame = dataset.frame.copy()
        if frame.empty or "forward_return_5d" not in frame.columns:
            return {"status": "skipped", "reason": "missing_target"}

        cfg = dict(self.config.get("relationship_discovery", {}))
        top_k = int(cfg.get("top_k", 25))
        max_features = int(cfg.get("max_features", 50))
        lags = cfg.get("lags", [1, 3, 5, 10])
        try:
            lag_list = [int(x) for x in lags if int(x) > 0]
        except Exception:
            lag_list = [1, 3, 5, 10]
        lag_list = lag_list[:6] if lag_list else [1, 3, 5, 10]

        target = pd.to_numeric(frame["forward_return_5d"], errors="coerce")
        numeric_candidates = [
            c
            for c in frame.columns
            if c not in {"forward_return_5d", "date", "ticker", "regime", "return_data_mode"}
            and pd.api.types.is_numeric_dtype(frame[c])
        ]
        # Bias towards macro/valuation/context variables first.
        ordered = sorted(
            numeric_candidates,
            key=lambda c: (
                0 if c.startswith("macro_") else 1,
                0 if "posterior" in c or "regime" in c else 1,
                c,
            ),
        )
        ordered = ordered[:max_features]

        if not ordered:
            return {"status": "skipped", "reason": "no_numeric_candidates"}

        work = frame[["ticker"] + ordered].copy()
        out_rows: List[Dict[str, Any]] = []
        for col in ordered:
            s = pd.to_numeric(work[col], errors="coerce")
            for lag in lag_list:
                shifted = (
                    pd.DataFrame({"ticker": work["ticker"], "v": s})
                    .groupby("ticker", sort=False)["v"]
                    .shift(lag)
                )
                pair = pd.DataFrame({"x": shifted, "y": target}).dropna()
                if len(pair) < 200:
                    continue
                if float(pair["x"].std()) <= 1e-12 or float(pair["y"].std()) <= 1e-12:
                    continue
                corr = pair["x"].corr(pair["y"], method="spearman")
                if not np.isfinite(corr):
                    continue
                out_rows.append(
                    {
                        "feature": col,
                        "lag_days": int(lag),
                        "spearman_corr": float(corr),
                        "abs_corr": float(abs(corr)),
                        "samples": int(len(pair)),
                    }
                )
        if not out_rows:
            return {"status": "skipped", "reason": "no_valid_relationships"}

        rel = (
            pd.DataFrame(out_rows)
            .sort_values(["abs_corr", "samples"], ascending=[False, False])
            .head(max(5, top_k))
            .reset_index(drop=True)
        )
        structural_shift = bool(
            (rel["abs_corr"] >= float(cfg.get("structural_shift_abs_corr", 0.08))).any()
        )
        return {
            "status": "ok",
            "top_relationships": rel.to_dict(orient="records"),
            "structural_shift_detected": structural_shift,
            "tested_features": int(len(ordered)),
            "tested_lags": lag_list,
        }

    def _run_autonomous_exploration(
        self,
        *,
        dataset: Any,
        best_model_name: str,
        best_model_params: Dict[str, Any],
        weekend_run: bool,
        freeze_active: bool,
    ) -> Dict[str, Any]:
        cfg = dict(self.config.get("autonomous_exploration", {}))
        if not bool(cfg.get("enabled", True)):
            return {"status": "skipped", "reason": "disabled"}
        if not best_model_name:
            return {"status": "skipped", "reason": "no_best_model"}

        n_variants = int(
            cfg.get("variants_weekend" if weekend_run else "variants_weekday", 1)
        )
        if n_variants <= 0:
            return {"status": "skipped", "reason": "no_variants"}

        mutation_rate = float(cfg.get("mutation_rate", self.config.get("mutation_rate", 0.25)))
        eval_windows = int(cfg.get("evaluation_max_windows", 1))
        eval_windows = max(1, min(eval_windows, self.pipeline.max_windows))
        exp_pipeline = TrainingPipeline(
            train_periods=self.pipeline.train_periods,
            valid_periods=self.pipeline.valid_periods,
            test_periods=self.pipeline.test_periods,
            step_periods=self.pipeline.step_periods,
            max_windows=eval_windows,
            start_window=0,
            portfolio_cfg=dict(self.config.get("portfolio_construction", {})),
            **self._holdout_training_kwargs(),
        )

        trials: List[Dict[str, Any]] = []
        for i in range(n_variants):
            mutated = self.mutator.mutate_params(best_model_params, mutation_rate=mutation_rate)
            try:
                model = self._build_model(best_model_name, mutated)
                result = exp_pipeline.run(model=model, dataset=dataset)
                agg = result.get("aggregate_metrics", {})
                score = (
                    float(agg.get("avg_sharpe", 0.0))
                    + 0.7 * float(agg.get("stability_score", 0.0))
                    + 0.3 * float(agg.get("ic_mean", 0.0))
                    - 0.6 * float(agg.get("avg_max_drawdown", 1.0))
                )
                trials.append(
                    {
                        "trial": int(i + 1),
                        "params": mutated,
                        "score": float(score),
                        "aggregate_metrics": agg,
                        "status": result.get("status", "unknown"),
                    }
                )
            except Exception as exc:
                trials.append(
                    {
                        "trial": int(i + 1),
                        "params": mutated,
                        "score": -999.0,
                        "status": f"failed:{exc}",
                    }
                )

        ranked = sorted(trials, key=lambda x: float(x.get("score", -999.0)), reverse=True)
        best_trial = ranked[0] if ranked else {}
        return {
            "status": "ok",
            "freeze_active": bool(freeze_active),
            "non_actionable": bool(freeze_active),
            "variants_tested": int(len(trials)),
            "best_variant": best_trial,
            "trials": ranked[: max(3, min(10, len(ranked)))],
        }

    @staticmethod
    def _build_model(name: str, params: Dict[str, Any]):
        n = ResearchController._normalize_model_name(name)
        if n == "lightgbm":
            return LightGBMModel(params=params)
        if n == "xgboost":
            return XGBoostModel(params=params)
        if n == "catboost":
            return CatBoostModel(params=params)
        if n == "random_forest":
            return RandomForestModel(params=params)
        if n == "lstm":
            return LSTMModel(params=params)
        if n == "tcn":
            return TCNModel(params=params)
        if n == "transformer":
            return TransformerModel(params=params)
        raise ValueError(f"unknown model: {name}")

    @staticmethod
    def _regime_dispersion(regime_metrics: Dict[str, Dict[str, float]]) -> float:
        if not regime_metrics:
            return 0.0
        vals = []
        for _, m in regime_metrics.items():
            vals.append(float(m.get("avg_sharpe", 0.0)))
        if len(vals) <= 1:
            return 0.0
        return float(np.std(np.asarray(vals, dtype=float)))

    def _select_best_model(self, results: Dict[str, Dict[str, Any]]) -> Tuple[str, Dict[str, Any]]:
        if not results:
            return "", {}

        def score(payload: Dict[str, Any]) -> float:
            agg = payload.get("aggregate_metrics", {})
            sharpe = float(agg.get("avg_sharpe", 0.0))
            stability = float(agg.get("stability_score", 0.0))
            ic = float(agg.get("ic_mean", 0.0))
            dd = float(agg.get("avg_max_drawdown", 1.0))
            return sharpe + 0.7 * stability + 0.3 * ic - 0.5 * dd

        ranked = sorted(results.items(), key=lambda x: score(x[1]), reverse=True)
        return ranked[0]

    @staticmethod
    def _aggregate_utility(aggregate_metrics: Dict[str, Any]) -> float:
        agg = aggregate_metrics if isinstance(aggregate_metrics, dict) else {}
        sharpe = float(agg.get("avg_sharpe", 0.0))
        stability = float(agg.get("stability_score", 0.0))
        ic = float(agg.get("ic_mean", 0.0))
        dd = float(agg.get("avg_max_drawdown", 1.0))
        monotonic = float(agg.get("monotonic_pass_rate", 0.0))
        return float(sharpe + 0.7 * stability + 0.35 * ic + 0.2 * monotonic - 0.6 * dd)

    def _parameter_sensitivity_candidates(self, model_name: str, base_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        n = str(model_name or "").strip().lower()
        base = dict(base_params or {})
        if not base:
            return []

        specs: List[Dict[str, Any]] = []
        if n in {"lightgbm", "xgboost", "catboost"}:
            if "learning_rate" in base:
                specs.append({"param": "learning_rate", "mode": "scale", "vals": [0.80, 1.20], "lo": 0.002, "hi": 0.35, "cast": "float"})
            est_key = "n_estimators" if "n_estimators" in base else ("iterations" if "iterations" in base else "")
            if est_key:
                specs.append({"param": est_key, "mode": "scale", "vals": [0.80, 1.20], "lo": 80, "hi": 1200, "cast": "int"})
            depth_key = "max_depth" if "max_depth" in base else ("depth" if "depth" in base else "")
            if depth_key:
                specs.append({"param": depth_key, "mode": "delta", "vals": [-2, 2], "lo": 2, "hi": 16, "cast": "int"})
        elif n == "random_forest":
            if "n_estimators" in base:
                specs.append({"param": "n_estimators", "mode": "scale", "vals": [0.80, 1.20], "lo": 80, "hi": 1500, "cast": "int"})
            if "max_depth" in base:
                specs.append({"param": "max_depth", "mode": "delta", "vals": [-3, 3], "lo": 2, "hi": 20, "cast": "int"})
        else:
            return []

        out: List[Dict[str, Any]] = []
        seen = set()
        for spec in specs:
            p = str(spec.get("param", ""))
            if p not in base:
                continue
            base_val = base.get(p)
            try:
                base_f = float(base_val)
            except Exception:
                continue
            for raw_v in list(spec.get("vals", [])):
                if str(spec.get("mode")) == "scale":
                    candidate_v = base_f * float(raw_v)
                else:
                    candidate_v = base_f + float(raw_v)
                lo = float(spec.get("lo", -np.inf))
                hi = float(spec.get("hi", np.inf))
                candidate_v = float(np.clip(candidate_v, lo, hi))
                if str(spec.get("cast")) == "int":
                    candidate_v = int(round(candidate_v))
                key = (p, str(candidate_v))
                if key in seen:
                    continue
                seen.add(key)
                params_new = dict(base)
                params_new[p] = candidate_v
                out.append(
                    {
                        "changed_parameter": p,
                        "base_value": base_val,
                        "candidate_value": candidate_v,
                        "params": params_new,
                    }
                )
        return out

    def _run_parameter_sensitivity_search(
        self,
        *,
        model_name: str,
        dataset: Any,
        base_params: Dict[str, Any],
        weekend_run: bool,
        freeze_active: bool,
    ) -> Dict[str, Any]:
        if not model_name:
            return {
                "status": "skipped",
                "reason": "no_best_model",
                "target_model": "none",
                "sensitivity_results": [],
                "requires_manual_approval": True,
                "freeze_active": bool(freeze_active),
                "non_actionable": True,
            }

        candidates = self._parameter_sensitivity_candidates(model_name, base_params)
        if not candidates:
            return {
                "status": "skipped",
                "reason": "model_not_supported_for_sensitivity",
                "target_model": model_name,
                "base_params": base_params,
                "sensitivity_results": [],
                "requires_manual_approval": True,
                "freeze_active": bool(freeze_active),
                "non_actionable": True,
            }

        max_trials_key = "parameter_sensitivity_max_trials_weekend" if weekend_run else "parameter_sensitivity_max_trials_weekday"
        max_trials = int(self.config.get(max_trials_key, 8 if weekend_run else 6))
        max_trials = max(2, min(max_trials, len(candidates)))
        max_windows = int(self.config.get("parameter_sensitivity_max_windows", 1))
        max_windows = max(1, min(max_windows, self.pipeline.max_windows))

        eval_pipeline = TrainingPipeline(
            train_periods=self.pipeline.train_periods,
            valid_periods=self.pipeline.valid_periods,
            test_periods=self.pipeline.test_periods,
            step_periods=self.pipeline.step_periods,
            max_windows=max_windows,
            start_window=self.pipeline.start_window,
            portfolio_cfg=dict(self.config.get("portfolio_construction", {})),
            **self._holdout_training_kwargs(),
        )

        try:
            base_model = self._build_model(model_name, base_params)
            base_result = eval_pipeline.run(model=base_model, dataset=dataset)
            base_agg = base_result.get("aggregate_metrics", {})
            base_score = self._aggregate_utility(base_agg)
        except Exception as exc:
            return {
                "status": "failed",
                "reason": f"base_model_eval_failed:{exc}",
                "target_model": model_name,
                "base_params": base_params,
                "sensitivity_results": [],
                "requires_manual_approval": True,
                "freeze_active": bool(freeze_active),
                "non_actionable": True,
            }

        rows: List[Dict[str, Any]] = []
        for idx, candidate in enumerate(candidates[:max_trials], start=1):
            params_new = dict(candidate.get("params", {}))
            changed_param = str(candidate.get("changed_parameter", ""))
            row: Dict[str, Any] = {
                "trial": int(idx),
                "changed_parameter": changed_param,
                "base_value": candidate.get("base_value"),
                "candidate_value": candidate.get("candidate_value"),
            }
            try:
                model = self._build_model(model_name, params_new)
                result = eval_pipeline.run(model=model, dataset=dataset)
                agg = result.get("aggregate_metrics", {})
                score = self._aggregate_utility(agg)
                row.update(
                    {
                        "status": "ok",
                        "utility_score": float(score),
                        "delta_score": float(score - base_score),
                        "aggregate_metrics": agg,
                        "params": params_new,
                    }
                )
            except Exception as exc:
                row.update({"status": "failed", "error": str(exc), "params": params_new})
            rows.append(row)

        valid = [r for r in rows if str(r.get("status")) == "ok"]
        valid_sorted = sorted(valid, key=lambda x: float(x.get("utility_score", -999.0)), reverse=True)
        best_row = valid_sorted[0] if valid_sorted else {}
        recommendations = []
        for r in valid_sorted[:3]:
            delta = float(r.get("delta_score", 0.0))
            if delta <= 0:
                continue
            recommendations.append(
                {
                    "parameter": str(r.get("changed_parameter", "")),
                    "from": r.get("base_value"),
                    "to": r.get("candidate_value"),
                    "expected_delta_score": delta,
                }
            )

        return {
            "status": "completed" if valid_sorted else "failed",
            "mode": "sensitivity_scan",
            "target_model": model_name,
            "base_params": base_params,
            "base_utility_score": float(base_score),
            "max_windows_used": int(max_windows),
            "candidate_count": int(len(rows)),
            "sensitivity_results": rows,
            "top_candidates": valid_sorted[:5],
            "best_candidate": best_row,
            "recommendations": recommendations,
            "requires_manual_approval": True,
            "freeze_active": bool(freeze_active),
            "non_actionable": bool(freeze_active),
        }

    def _maybe_hyperopt(self, model_name: str, dataset, freeze_active: bool) -> Dict[str, Any] | None:
        if not bool(self.config.get("enable_hyperopt", False)):
            return None

        if model_name not in {"lightgbm", "xgboost", "catboost", "random_forest"}:
            return None

        hyperopt_windows = int(self.config.get("hyperopt_max_windows", 1))
        hyperopt_windows = max(1, min(hyperopt_windows, self.pipeline.max_windows))
        opt_pipeline = TrainingPipeline(
            train_periods=self.pipeline.train_periods,
            valid_periods=self.pipeline.valid_periods,
            test_periods=self.pipeline.test_periods,
            step_periods=self.pipeline.step_periods,
            max_windows=hyperopt_windows,
            start_window=self.pipeline.start_window,
            portfolio_cfg=dict(self.config.get("portfolio_construction", {})),
            **self._holdout_training_kwargs(),
        )

        space = {
            "n_estimators": (120, 420, "int"),
            "learning_rate": (0.005, 0.12, "log_float"),
            "max_depth": (3, 12, "int"),
        }

        def objective(p: Dict[str, Any]) -> float:
            model = self._build_model(model_name, p)
            result = opt_pipeline.run(model=model, dataset=dataset)
            agg = result.get("aggregate_metrics", {})
            sharpe = float(agg.get("avg_sharpe", 0.0))
            dd = float(agg.get("avg_max_drawdown", 1.0))
            monotonic = float(agg.get("monotonic_pass_rate", 0.0))
            # Lower is better objective.
            return float(-(0.8 * sharpe + 0.4 * monotonic - 0.6 * dd))
        try:
            result = self.optimizer.optimize(objective=objective, space=space)
        except Exception as exc:
            logger.warning("hyperopt_failed model=%s error=%s", model_name, exc)
            return {
                "status": "failed",
                "error": str(exc),
                "max_windows_used": int(hyperopt_windows),
                "freeze_active": bool(freeze_active),
                "non_actionable": True,
            }

        if isinstance(result, dict):
            result["status"] = str(result.get("status", "ok"))
            result["max_windows_used"] = int(hyperopt_windows)
            result["freeze_active"] = bool(freeze_active)
            result["non_actionable"] = bool(freeze_active)
        return result

    @staticmethod
    def _now_ist() -> datetime:
        return datetime.now(ZoneInfo("Asia/Kolkata"))

    def _is_weekend(self, now_ist: datetime | None = None) -> bool:
        now = now_ist or self._now_ist()
        return bool(now.weekday() >= 5)

    @staticmethod
    def _infer_trade_ts(trade_id: Any) -> pd.Timestamp | None:
        text = str(trade_id or "").strip().upper()
        m = _TRADE_ID_TS_RE.match(text)
        if not m:
            return None
        ts = pd.to_datetime(f"{m.group(1)}{m.group(2)}", format="%Y%m%d%H%M%S", errors="coerce")
        if pd.isna(ts):
            return None
        return ts

    def _build_returns_partition(self) -> Dict[str, Any]:
        cutover_raw = str(self.config.get("live_returns_cutover_date", "2026-01-18"))
        cutover = pd.to_datetime(cutover_raw, errors="coerce")
        report: Dict[str, Any] = {
            "status": "missing",
            "live_returns_cutover_date": cutover_raw,
            "backtest_closed_trades": 0,
            "live_closed_trades": 0,
            "backtest_net_pnl": 0.0,
            "live_net_pnl": 0.0,
            "total_net_pnl": 0.0,
            "rows_missing_timestamp": 0,
            "source": "data/options/trade_ledger.parquet",
        }
        if pd.isna(cutover):
            report["status"] = "invalid_cutover_date"
            return report

        ledger_path = self.project_root / "data/options/trade_ledger.parquet"
        if not ledger_path.exists():
            return report

        try:
            df = pd.read_parquet(ledger_path)
            if not isinstance(df, pd.DataFrame) or df.empty:
                report["status"] = "empty"
                return report
            work = df.copy()
            if "action" in work.columns:
                work = work[work["action"].astype(str).str.lower() == "close"].copy()
            if work.empty:
                report["status"] = "no_closed_trades"
                return report

            ts = pd.to_datetime(work.get("timestamp"), errors="coerce")
            if "trade_id" in work.columns:
                missing_idx = ts[ts.isna()].index
                if len(missing_idx):
                    inferred = work.loc[missing_idx, "trade_id"].apply(self._infer_trade_ts)
                    ts.loc[missing_idx] = pd.to_datetime(inferred, errors="coerce")
            work["timestamp_fixed"] = ts
            work["net_pnl_num"] = pd.to_numeric(work.get("net_pnl"), errors="coerce").fillna(0.0)

            missing_ts = int(work["timestamp_fixed"].isna().sum())
            valid = work.dropna(subset=["timestamp_fixed"]).copy()
            if valid.empty:
                report["status"] = "no_valid_timestamps"
                report["rows_missing_timestamp"] = missing_ts
                return report

            back = valid[valid["timestamp_fixed"] < cutover]
            live = valid[valid["timestamp_fixed"] >= cutover]
            report.update(
                {
                    "status": "ok",
                    "backtest_closed_trades": int(len(back)),
                    "live_closed_trades": int(len(live)),
                    "backtest_net_pnl": float(back["net_pnl_num"].sum()),
                    "live_net_pnl": float(live["net_pnl_num"].sum()),
                    "total_net_pnl": float(valid["net_pnl_num"].sum()),
                    "rows_missing_timestamp": missing_ts,
                }
            )
            return report
        except Exception as exc:
            report["status"] = "error"
            report["error"] = str(exc)
            return report

    def _run_weekend_scenario_sweep(self, mc: StructuralMonteCarlo, panel: pd.DataFrame) -> Dict[str, Any]:
        if panel.empty:
            return {"status": "skipped", "reason": "empty_panel"}

        multipliers = self.config.get("weekend_scenario_multipliers", [0.8, 1.0, 1.2, 1.5])
        try:
            multipliers = [float(x) for x in multipliers]
        except Exception:
            multipliers = [0.8, 1.0, 1.2, 1.5]

        rows = []
        for mult in multipliers:
            try:
                sim = mc.simulate_paths(
                    panel=panel.tail(int(self.config.get("mc_fit_rows", 50000))),
                    n_paths=int(self.config.get("weekend_mc_paths", self.config.get("mc_paths", 3000))),
                    horizon=int(self.config.get("weekend_mc_horizon", self.config.get("mc_horizon", 20))),
                    stress_multiplier=float(mult),
                )
                m = mc.evaluate(sim.get("paths", np.empty((0, 0))))
                rows.append(
                    {
                        "stress_multiplier": float(mult),
                        "survival_probability": float(m.get("survival_probability", 0.0)),
                        "avg_max_drawdown": float(m.get("avg_max_drawdown", 0.0)),
                        "tail_5pct": float(m.get("tail_5pct", 0.0)),
                    }
                )
            except Exception as exc:
                rows.append({"stress_multiplier": float(mult), "error": str(exc)})
        return {"status": "ok", "scenarios": rows}

    def _export_options_research_opportunities(
        self,
        *,
        dataset,
        model: Any,
        model_name: str,
        feature_importance: Dict[str, float],
    ) -> Dict[str, Any]:
        report: Dict[str, Any] = {
            "status": "skipped",
            "path": str(self.project_root / "data/processed/research_opportunity_surface.parquet"),
            "rows_written": 0,
            "model": model_name,
        }
        if dataset.frame.empty or not dataset.feature_names:
            report["reason"] = "dataset_empty"
            return report

        latest = (
            dataset.frame.sort_values("date")
            .groupby("ticker", as_index=False)
            .tail(1)
            .copy()
        )
        if latest.empty:
            report["reason"] = "no_latest_rows"
            return report

        X_latest = latest[dataset.feature_names].replace([np.inf, -np.inf], np.nan)
        X_latest = X_latest.fillna(X_latest.median(numeric_only=True)).fillna(0.0)
        pred = np.asarray(model.predict(X_latest.to_numpy(dtype=float)), dtype=float).reshape(-1)
        signal = np.tanh(pred)

        conf_col = (
            pd.to_numeric(latest.get("posterior_confidence"), errors="coerce")
            if "posterior_confidence" in latest.columns
            else pd.Series(np.nan, index=latest.index, dtype=float)
        )
        sent_score = (
            pd.to_numeric(latest.get("sent_sentiment_score"), errors="coerce")
            if "sent_sentiment_score" in latest.columns
            else pd.Series(np.nan, index=latest.index, dtype=float)
        )
        sent_trend = (
            pd.to_numeric(latest.get("sent_trend_score"), errors="coerce")
            if "sent_trend_score" in latest.columns
            else pd.Series(np.nan, index=latest.index, dtype=float)
        )
        mkt_polarity = (
            pd.to_numeric(latest.get("mkt_sent_polarity"), errors="coerce")
            if "mkt_sent_polarity" in latest.columns
            else pd.Series(np.nan, index=latest.index, dtype=float)
        )
        mkt_conviction = (
            pd.to_numeric(latest.get("mkt_sent_conviction"), errors="coerce")
            if "mkt_sent_conviction" in latest.columns
            else pd.Series(np.nan, index=latest.index, dtype=float)
        )
        fallback_conf = np.clip(np.abs(signal), 0.0, 1.0)
        conf = np.where(conf_col.isna().to_numpy(), fallback_conf, conf_col.to_numpy(dtype=float))
        mispricing = np.clip(np.abs(signal), 0.0, 1.0)
        confirmation = np.clip(0.6 * conf + 0.4 * mispricing, 0.0, 1.0)
        combined = mispricing * confirmation

        def _alt_series(name: str) -> pd.Series:
            if name not in latest.columns:
                return pd.Series(0.0, index=latest.index, dtype=float)
            return pd.to_numeric(latest.get(name), errors="coerce").fillna(0.0)

        alt_component_map = {
            "bulk_flow": 0.20 * np.tanh(_alt_series("bulk_net_pressure_21d")),
            "bulk_institutional": 0.15 * np.tanh(_alt_series("bulk_net_institutional_21d")),
            "order_flow": 0.12 * _alt_series("order_win_flag_30d"),
            "capex": 0.08 * _alt_series("capex_announced_flag"),
            "insider": 0.10 * (_alt_series("insider_buy_flag_30d") - _alt_series("insider_sell_flag_30d")),
            "ratings": 0.16 * np.tanh(_alt_series("rating_change_1y"))
            + 0.10 * (_alt_series("recent_upgrade_flag") - _alt_series("recent_downgrade_flag"))
            - 0.08 * _alt_series("watch_negative_flag"),
            "pledge": -0.18 * _alt_series("pledge_high_flag") - 0.10 * _alt_series("pledge_increasing_flag"),
        }
        alt_component_df = pd.DataFrame(alt_component_map, index=latest.index)
        alt_signal_score = np.tanh(alt_component_df.sum(axis=1))
        alt_component_abs = alt_component_df.abs()
        alt_driver = alt_component_abs.idxmax(axis=1).where(alt_component_abs.max(axis=1) > 0.03, "none")
        alt_event_flag = (alt_component_abs.max(axis=1) >= 0.20).astype(float)
        alt_signal_direction = np.where(alt_signal_score >= 0.0, "bullish", "bearish")

        # Try to resolve top macro drivers from feature importance.
        macro_rank = []
        for k, v in (feature_importance or {}).items():
            try:
                idx = int(str(k).lstrip("f"))
                if 0 <= idx < len(dataset.feature_names):
                    fname = dataset.feature_names[idx]
                else:
                    fname = str(k)
            except Exception:
                fname = str(k)
            if str(fname).startswith("macro_"):
                macro_rank.append((fname, float(v)))
        macro_rank.sort(key=lambda x: abs(float(x[1])), reverse=True)
        top_driver = macro_rank[0][0] if macro_rank else "macro_unknown"
        top_driver_strength = float(macro_rank[0][1]) if macro_rank else 0.0

        out = pd.DataFrame(
            {
                "ticker": latest["ticker"].astype(str).str.replace(".NS", "", regex=False),
                "mispricing": mispricing,
                "confirmation": confirmation,
                "combined_score": combined,
                "signal_strength": signal,
                "signal_direction": np.where(signal >= 0.0, "bullish", "bearish"),
                "opportunity_type": np.where(signal >= 0.0, "Alpha Core", "Momentum Breakouts"),
                "source": "research_engine",
                "model_name": str(model_name),
                "driver_variable": top_driver,
                "driver_strength": top_driver_strength,
                "sentiment_score": sent_score.fillna(0.0).to_numpy(dtype=float),
                "sentiment_trend_score": sent_trend.fillna(0.0).to_numpy(dtype=float),
                "market_sentiment_polarity": mkt_polarity.fillna(0.0).to_numpy(dtype=float),
                "market_sentiment_conviction": mkt_conviction.fillna(0.0).to_numpy(dtype=float),
                "alternative_signal_score": alt_signal_score.to_numpy(dtype=float),
                "alternative_signal_direction": alt_signal_direction,
                "alternative_driver": alt_driver.astype(str).to_numpy(),
                "alternative_event_flag": alt_event_flag.to_numpy(dtype=float),
                "generated_at": datetime.utcnow().isoformat(),
            }
        )
        out = out.sort_values("combined_score", ascending=False)
        max_rows = int(self.config.get("options_opportunity_max_rows", 60))
        out = out.head(max(10, max_rows)).reset_index(drop=True)

        path = self.project_root / "data/processed/research_opportunity_surface.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        out.to_parquet(path, index=False)
        report.update({"status": "ok", "rows_written": int(len(out)), "path": str(path)})
        return report

    def _run_ic_diagnostics_gate(self, dataset: Any) -> Tuple[Any, Dict[str, Any] | None]:
        cfg = dict(self.config.get("ic_diagnostics", {}))
        if not bool(cfg.get("enabled", False)):
            return dataset, None

        scope_mode_req = str(cfg.get("scope_mode", "train_only")).strip().lower()
        if scope_mode_req not in {"train_only", "full_frame"}:
            scope_mode_req = "train_only"
        ic_frame = dataset.frame
        scope_mode_applied = "full_frame"
        if scope_mode_req == "train_only":
            scoped = self._ic_diagnostics_train_scope_frame(dataset.frame)
            if isinstance(scoped, pd.DataFrame) and not scoped.empty:
                ic_frame = scoped
                scope_mode_applied = "train_only"

        target_col = str(dataset.metadata.get("target_col", "forward_return_5d"))
        raw_h = cfg.get("horizons", [5, 10, 20])
        if isinstance(raw_h, (list, tuple)):
            horizons = [int(h) for h in raw_h if str(h).strip()]
        else:
            horizons = [5, 10, 20]
        report = compute_feature_ic_diagnostics(
            ic_frame,
            feature_cols=list(dataset.feature_names),
            target_col=target_col,
            date_col=str(cfg.get("date_col", "date")),
            ticker_col=str(cfg.get("ticker_col", "ticker")),
            regime_col=str(cfg.get("regime_col", "regime")),
            horizons=horizons,
            min_obs_per_day=int(cfg.get("min_obs_per_day", 25)),
            min_abs_ic=float(cfg.get("min_abs_ic", 0.01)),
            min_sign_consistency=float(cfg.get("min_sign_consistency", 0.55)),
            min_t_stat=float(cfg.get("min_t_stat", 0.0)),
            min_keep_features=int(cfg.get("min_keep_features", 15)),
            max_keep_features=int(cfg.get("max_keep_features", 40)),
            max_features_to_analyze=int(cfg.get("max_features_to_analyze", 0)),
            max_regimes_to_report=int(cfg.get("max_regimes_to_report", 4)),
            min_regime_days=int(cfg.get("min_regime_days", 30)),
        )

        out_dir = Path(str(cfg.get("output_dir", "data/results/research/ic_diagnostics")))
        if not out_dir.is_absolute():
            out_dir = self.project_root / out_dir
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = out_dir / ts[:4] / ts[4:6] / f"ic_report_{ts}.json"
        write_ic_report(report, report_path)

        prune = bool(cfg.get("prune_features", False))
        selected = [str(f) for f in report.get("selected_features", [])]
        before = int(len(dataset.feature_names))
        pruned = False

        if prune and selected and before > 0:
            selected_set = set(selected)
            keep_idx = [i for i, f in enumerate(dataset.feature_names) if str(f) in selected_set]
            min_keep = max(1, int(cfg.get("min_keep_features", 15)))
            if len(keep_idx) >= min_keep:
                dataset.X = np.asarray(dataset.X[:, keep_idx], dtype=float)
                dataset.feature_names = [dataset.feature_names[i] for i in keep_idx]
                pruned = True

                # Keep sequence-observed block aligned when names are available.
                obs_names = list(getattr(dataset, "observed_dynamic_feature_names", []) or [])
                obs_block = getattr(dataset, "observed_dynamic_features", None)
                if obs_names and obs_block is not None and len(obs_names) == int(obs_block.shape[1]):
                    obs_keep = [i for i, f in enumerate(obs_names) if str(f) in selected_set]
                    if obs_keep:
                        dataset.observed_dynamic_features = np.asarray(obs_block[:, obs_keep], dtype=np.float32)
                        dataset.observed_dynamic_feature_names = [obs_names[i] for i in obs_keep]

        after = int(len(dataset.feature_names))
        dataset.metadata["ic_diagnostics_enabled"] = True
        dataset.metadata["ic_diagnostics_report"] = str(report_path)
        dataset.metadata["n_features_before_ic_prune"] = before
        dataset.metadata["n_features_after_ic_prune"] = after
        dataset.metadata["ic_pruning_applied"] = bool(pruned)
        dataset.metadata["ic_diagnostics_scope"] = str(scope_mode_applied)
        dataset.metadata["ic_diagnostics_rows_used"] = int(len(ic_frame))
        dataset.metadata["ic_decay_summary_selected_features"] = dict(
            report.get("decay_summary_selected_features", {}) or {}
        )

        return dataset, {
            "status": str(report.get("status", "unknown")),
            "path": str(report_path),
            "prune_requested": bool(prune),
            "prune_applied": bool(pruned),
            "n_features_input": int(report.get("n_features_input", before)),
            "n_features_selected": int(report.get("n_features_selected", len(selected))),
            "n_features_after_prune": int(after),
            "scope_mode_requested": str(scope_mode_req),
            "scope_mode_applied": str(scope_mode_applied),
            "scope_rows_used": int(len(ic_frame)),
            "top_features": list(report.get("top_features", [])),
            "decay_summary_selected_features": dict(
                report.get("decay_summary_selected_features", {}) or {}
            ),
            "regime_decay_summary_selected_features": dict(
                report.get("regime_decay_summary_selected_features", {}) or {}
            ),
        }

    def _ic_diagnostics_train_scope_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Use only pre-test data for IC diagnostics to avoid lookahead feature pruning."""
        if frame is None or frame.empty or "date" not in frame.columns:
            return frame

        work = frame.copy()
        work["date"] = pd.to_datetime(work["date"], errors="coerce")
        work = work.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        if work.empty:
            return frame

        tcfg = dict(self.config.get("training", {}))
        dataset_cfg = dict(self.config.get("dataset", {}))
        cfg_embargo = int(tcfg.get("label_embargo_periods", 0) or 0)
        horizon_days = int(dataset_cfg.get("target_horizon_days", 1) or 1)
        embargo_periods = max(0, cfg_embargo if cfg_embargo > 0 else horizon_days)

        scoped_mask = None
        fixed = self.pipeline._fixed_holdout_split(work, date_col="date")
        if fixed is not None:
            scoped_mask = np.asarray(fixed["train_mask"], dtype=bool) | np.asarray(fixed["valid_mask"], dtype=bool)
            scoped_mask, _ = self.pipeline._apply_label_embargo(
                frame=work,
                train_mask=scoped_mask,
                test_mask=np.asarray(fixed["test_mask"], dtype=bool),
                date_col="date",
                embargo_periods=embargo_periods,
            )
        else:
            splitter = rolling_time_splits(
                work,
                date_col="date",
                ticker_col="ticker",
                train_periods=self.pipeline.train_periods,
                valid_periods=self.pipeline.valid_periods,
                test_periods=self.pipeline.test_periods,
                step_periods=self.pipeline.step_periods,
                min_tickers_per_date=self.pipeline.min_tickers_per_date,
            )
            first_split = None
            for i, split in enumerate(splitter):
                if i >= max(0, int(self.pipeline.start_window)):
                    first_split = split
                    break
            if first_split is not None:
                scoped_mask = np.asarray(first_split["train_mask"], dtype=bool) | np.asarray(first_split["valid_mask"], dtype=bool)
                scoped_mask, _ = self.pipeline._apply_label_embargo(
                    frame=work,
                    train_mask=scoped_mask,
                    test_mask=np.asarray(first_split["test_mask"], dtype=bool),
                    date_col="date",
                    embargo_periods=embargo_periods,
                )

        if scoped_mask is None:
            return work

        scoped = work.loc[np.asarray(scoped_mask, dtype=bool)].copy()
        return scoped if not scoped.empty else work

    def _run_alpha_factory_stage(
        self,
        dataset: Any,
        *,
        ic_diag_payload: Dict[str, Any] | None = None,
    ) -> Dict[str, Any] | None:
        cfg = dict(self.config.get("alpha_factory", {}))
        if not bool(cfg.get("enabled", False)):
            return None

        date_col = str(cfg.get("date_col", "date"))
        ticker_col = str(cfg.get("ticker_col", "ticker"))
        regime_col = str(cfg.get("regime_col", "regime"))
        target_col = str(dataset.metadata.get("target_col", "forward_return_5d"))
        if date_col not in dataset.frame.columns or ticker_col not in dataset.frame.columns:
            return {"status": "skipped_missing_date_or_ticker"}
        if target_col not in dataset.frame.columns:
            return {"status": "skipped_missing_target", "target_col": target_col}

        features = list(getattr(dataset, "feature_names", []) or [])
        if not features:
            return {"status": "skipped_no_features"}

        # ResearchDataset can be pruned; align frame and X deterministically.
        frame_len = int(len(dataset.frame))
        x_len = int(len(getattr(dataset, "X", [])))
        n = int(min(frame_len, x_len))
        if n <= 0:
            return {"status": "skipped_empty_aligned_dataset"}
        max_rows = int(cfg.get("max_rows", 120000))
        start = int(max(0, n - max_rows)) if max_rows > 0 else 0
        base = dataset.frame.iloc[start:n].copy().reset_index(drop=True)
        x_df = pd.DataFrame(np.asarray(dataset.X[start:n], dtype=float), columns=features)
        work = pd.DataFrame(
            {
                date_col: pd.to_datetime(base[date_col], errors="coerce"),
                ticker_col: base[ticker_col].astype(str),
                target_col: pd.to_numeric(base[target_col], errors="coerce"),
            }
        )
        if regime_col in base.columns:
            work[regime_col] = base[regime_col].astype(str)
        work = pd.concat([work, x_df], axis=1).dropna(subset=[date_col, ticker_col, target_col])
        if work.empty:
            return {"status": "skipped_empty_work_frame"}

        manual_map = cfg.get("manual_family_map", {}) or {}
        fmap = build_feature_family_map(
            features,
            manual_map=manual_map if isinstance(manual_map, dict) else {},
        )
        min_obs_per_day = int(cfg.get("min_obs_per_day", 25))
        min_abs_ic = float(cfg.get("min_abs_ic", 0.01))
        min_sign_consistency = float(cfg.get("min_sign_consistency", 0.55))
        min_t_stat = float(cfg.get("min_t_stat", 0.0))
        corr_prune_threshold = float(cfg.get("corr_prune_threshold", 0.85))
        min_features_per_family = int(cfg.get("min_features_per_family", 1))
        max_features_per_family = int(cfg.get("max_features_per_family", 25))
        long_short_quantile = float(cfg.get("long_short_quantile", 0.20))
        min_assets_per_day = int(cfg.get("min_assets_per_day", 12))

        family_payload: Dict[str, Any]
        family_returns = pd.DataFrame()
        family_ic_daily = pd.DataFrame()
        family_turnover: Dict[str, float] = {}
        window_isolated_oos = bool(cfg.get("window_isolated_oos", True))
        oos_meta: Dict[str, Any] = {
            "window_isolated_oos": bool(window_isolated_oos),
            "windows_attempted": 0,
            "windows_used": 0,
        }

        if window_isolated_oos:
            max_windows = int(cfg.get("oos_max_windows", self.pipeline.max_windows))
            start_window = int(cfg.get("oos_start_window", self.pipeline.start_window))
            split_iter = rolling_time_splits(
                work,
                date_col=date_col,
                ticker_col=ticker_col,
                train_periods=int(cfg.get("oos_train_periods", self.pipeline.train_periods)),
                valid_periods=int(cfg.get("oos_valid_periods", self.pipeline.valid_periods)),
                test_periods=int(cfg.get("oos_test_periods", self.pipeline.test_periods)),
                step_periods=int(cfg.get("oos_step_periods", self.pipeline.step_periods)),
                min_tickers_per_date=int(cfg.get("min_tickers_per_date", self.pipeline.min_tickers_per_date)),
            )

            oos_returns_parts: List[pd.DataFrame] = []
            oos_ic_parts: List[pd.DataFrame] = []
            oos_turnover_parts: Dict[str, List[float]] = {}
            last_train_payload: Dict[str, Any] | None = None

            for i, split in enumerate(split_iter):
                if i < max(0, start_window):
                    continue
                if oos_meta["windows_used"] >= max(1, max_windows):
                    break
                oos_meta["windows_attempted"] = int(oos_meta["windows_attempted"]) + 1

                tr = np.asarray(split.get("train_mask", []), dtype=bool)
                va = np.asarray(split.get("valid_mask", []), dtype=bool)
                te = np.asarray(split.get("test_mask", []), dtype=bool)
                if tr.size != len(work) or va.size != len(work) or te.size != len(work):
                    continue
                train_mask = tr | va
                if int(train_mask.sum()) < 50 or int(te.sum()) < 20:
                    continue

                train_df = work.loc[train_mask].copy()
                test_df = work.loc[te].copy()
                train_payload = build_family_factor_table(
                    train_df,
                    feature_cols=features,
                    feature_family_map=fmap,
                    date_col=date_col,
                    ticker_col=ticker_col,
                    target_col=target_col,
                    min_obs_per_day=min_obs_per_day,
                    min_abs_ic=min_abs_ic,
                    min_sign_consistency=min_sign_consistency,
                    min_t_stat=min_t_stat,
                    corr_prune_threshold=corr_prune_threshold,
                    min_features_per_family=min_features_per_family,
                    max_features_per_family=max_features_per_family,
                    long_short_quantile=long_short_quantile,
                    min_assets_per_day=min_assets_per_day,
                )
                if str(train_payload.get("status", "")) != "ok":
                    continue

                test_payload = apply_family_feature_weights(
                    test_df,
                    family_feature_weights=train_payload.get("family_feature_weights", {}) or {},
                    date_col=date_col,
                    ticker_col=ticker_col,
                    target_col=target_col,
                    min_obs_per_day=min_obs_per_day,
                    long_short_quantile=long_short_quantile,
                    min_assets_per_day=min_assets_per_day,
                )
                if str(test_payload.get("status", "")) != "ok":
                    continue

                fr = test_payload.get("family_returns", pd.DataFrame())
                fic = test_payload.get("family_ic_daily", pd.DataFrame())
                if isinstance(fr, pd.DataFrame) and not fr.empty:
                    oos_returns_parts.append(fr.copy())
                if isinstance(fic, pd.DataFrame) and not fic.empty:
                    oos_ic_parts.append(fic.copy())
                for fam, val in dict(test_payload.get("family_turnover", {}) or {}).items():
                    try:
                        fv = float(val)
                    except Exception:
                        continue
                    if np.isfinite(fv):
                        oos_turnover_parts.setdefault(str(fam), []).append(fv)

                last_train_payload = train_payload
                oos_meta["windows_used"] = int(oos_meta["windows_used"]) + 1

            if not oos_returns_parts or last_train_payload is None:
                return {
                    "status": "insufficient_oos_windows",
                    "window_isolated_oos": True,
                    "oos_windows_used": int(oos_meta.get("windows_used", 0)),
                    "oos_windows_attempted": int(oos_meta.get("windows_attempted", 0)),
                }

            family_returns = pd.concat(oos_returns_parts, axis=0).sort_index()
            if not family_returns.empty:
                family_returns = family_returns.groupby(level=0).mean().sort_index().fillna(0.0)
            if oos_ic_parts:
                family_ic_daily = pd.concat(oos_ic_parts, axis=0).sort_index()
                family_ic_daily = family_ic_daily.groupby(level=0).mean().sort_index().fillna(0.0)
            else:
                family_ic_daily = pd.DataFrame()
            family_turnover = {
                str(fam): float(np.mean(vals))
                for fam, vals in oos_turnover_parts.items()
                if vals
            }
            family_payload = {
                "status": "ok",
                "family_stats": dict(last_train_payload.get("family_stats", {}) or {}),
                "family_feature_weights": dict(last_train_payload.get("family_feature_weights", {}) or {}),
                "feature_stats": list(last_train_payload.get("feature_stats", []) or []),
            }
        else:
            family_payload = build_family_factor_table(
                work,
                feature_cols=features,
                feature_family_map=fmap,
                date_col=date_col,
                ticker_col=ticker_col,
                target_col=target_col,
                min_obs_per_day=min_obs_per_day,
                min_abs_ic=min_abs_ic,
                min_sign_consistency=min_sign_consistency,
                min_t_stat=min_t_stat,
                corr_prune_threshold=corr_prune_threshold,
                min_features_per_family=min_features_per_family,
                max_features_per_family=max_features_per_family,
                long_short_quantile=long_short_quantile,
                min_assets_per_day=min_assets_per_day,
            )
            if str(family_payload.get("status", "")) != "ok":
                return {
                    "status": "family_build_failed",
                    "family_status": str(family_payload.get("status", "unknown")),
                }
            family_returns = family_payload.get("family_returns", pd.DataFrame())
            family_ic_daily = family_payload.get("family_ic_daily", pd.DataFrame())
            family_turnover = family_payload.get("family_turnover", {}) or {}

        if family_returns is None or family_returns.empty:
            return {
                "status": "family_build_failed",
                "family_status": "empty_family_returns",
                "window_isolated_oos": bool(window_isolated_oos),
                "oos_windows_used": int(oos_meta.get("windows_used", 0)),
                "oos_windows_attempted": int(oos_meta.get("windows_attempted", 0)),
            }

        # If IC diagnostics already selected a constrained feature subset, include it for auditability.
        ic_selected = []
        if isinstance(ic_diag_payload, dict):
            ic_selected = [str(x) for x in ic_diag_payload.get("top_features", []) if str(x).strip()]
        horizon_match = re.search(r"forward_return_(\d+)d", str(target_col))
        inferred_horizon_days = int(horizon_match.group(1)) if horizon_match else 1
        override_stride = int(cfg.get("non_overlap_stride_override", 0) or 0)
        non_overlap_stride = int(max(1, override_stride if override_stride > 0 else inferred_horizon_days))

        blend = optimize_family_blend(
            family_returns,
            family_turnover=family_turnover if isinstance(family_turnover, dict) else {},
            lookback_periods=int(cfg.get("blend_lookback_periods", 756)),
            shrinkage=float(cfg.get("covariance_shrinkage", 0.60)),
            eigen_floor=float(cfg.get("covariance_eigen_floor", 1e-6)),
            ridge=float(cfg.get("covariance_ridge", 1e-6)),
            transaction_cost_penalty=float(cfg.get("transaction_cost_penalty", 0.0)),
            allocation_turnover_cap=float(cfg.get("allocation_turnover_cap", 0.20)),
            long_only=bool(cfg.get("long_only", False)),
            max_abs_weight=float(cfg.get("max_abs_weight", 0.60)),
            target_gross=float(cfg.get("target_gross", 1.0)),
            target_annual_vol=float(cfg.get("target_annual_vol", 0.15)),
            periods_per_year=int(cfg.get("periods_per_year", 252)),
            min_history=int(cfg.get("min_history", 40)),
            non_overlap_stride=int(non_overlap_stride),
        )
        monitoring = compute_live_monitoring_metrics(
            family_returns,
            family_ic_daily=family_ic_daily if isinstance(family_ic_daily, pd.DataFrame) else None,
            lookback_periods=int(cfg.get("monitor_lookback_periods", 60)),
            corr_lookback_periods=int(cfg.get("corr_lookback_periods", 60)),
            periods_per_year=int(cfg.get("periods_per_year", 252)),
        )
        stacking = simulate_signal_stacking(
            base_ic=float(cfg.get("theoretical_base_ic", 0.02)),
            n_signals=int(cfg.get("theoretical_n_signals", 200)),
            corr_grid=cfg.get("theoretical_corr_grid", [0.05, 0.10, 0.20]),
        )

        family_stats = dict(family_payload.get("family_stats", {}) or {})
        family_weights = dict(family_payload.get("family_feature_weights", {}) or {})
        blend_weights = dict(blend.get("weights", {}) or {})
        n_selected = int(
            sum(
                int((family_stats.get(fam, {}) or {}).get("n_features_selected", 0))
                for fam in family_stats
            )
        )

        out_dir = Path(str(cfg.get("output_dir", "data/results/research/alpha_factory")))
        if not out_dir.is_absolute():
            out_dir = self.project_root / out_dir
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = out_dir / ts[:4] / ts[4:6] / f"alpha_factory_report_{ts}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_blob = {
            "generated_at": datetime.utcnow().isoformat(),
            "status": "ok",
            "n_rows": int(len(work)),
            "n_features_input": int(len(features)),
            "n_features_selected_base": int(n_selected),
            "n_families": int(len(family_stats)),
            "families": sorted(list(family_stats.keys())),
            "family_stats": family_stats,
            "family_feature_weights": family_weights,
            "blend": blend,
            "monitoring": monitoring,
            "theoretical_stacking": stacking,
            "ic_top_features_reference": ic_selected,
            "window_isolated_oos": bool(oos_meta.get("window_isolated_oos", False)),
            "oos_windows_attempted": int(oos_meta.get("windows_attempted", 0)),
            "oos_windows_used": int(oos_meta.get("windows_used", 0)),
            "inferred_horizon_days": int(inferred_horizon_days),
            "non_overlap_stride": int(non_overlap_stride),
        }
        report_path.write_text(json.dumps(report_blob, indent=2, default=str))

        dataset.metadata["alpha_factory_enabled"] = True
        dataset.metadata["alpha_factory_report"] = str(report_path)
        dataset.metadata["alpha_factory_n_families"] = int(len(family_stats))
        dataset.metadata["alpha_factory_blend_weights"] = blend_weights

        return {
            "status": "ok",
            "path": str(report_path),
            "n_features_input": int(len(features)),
            "n_features_selected_base": int(n_selected),
            "n_families": int(len(family_stats)),
            "families": sorted(list(family_stats.keys())),
            "blend_weights": blend_weights,
            "monitoring_alerts": list(monitoring.get("alerts", []) or []),
            "covariance_condition_number": float(
                (blend.get("diagnostics", {}) or {}).get("covariance_condition_number", 0.0)
            ),
            "theoretical_stacking": stacking,
            "window_isolated_oos": bool(oos_meta.get("window_isolated_oos", False)),
            "oos_windows_attempted": int(oos_meta.get("windows_attempted", 0)),
            "oos_windows_used": int(oos_meta.get("windows_used", 0)),
            "inferred_horizon_days": int(inferred_horizon_days),
            "non_overlap_stride": int(non_overlap_stride),
        }

    def _evaluate_structural_promotion_gate(self, ic_diag_payload: Dict[str, Any] | None) -> Dict[str, Any]:
        cfg = dict(self.config.get("structural_promotion_gate", {}))
        enabled = bool(cfg.get("enabled", False))
        thresholds = {
            "min_peak_horizon": float(cfg.get("min_peak_horizon", 80.0)),
            "min_half_life_horizon": float(cfg.get("min_half_life_horizon", 80.0)),
            "min_monotonicity_score": float(cfg.get("min_monotonicity_score", 0.80)),
            "min_peak_ic": float(cfg.get("min_peak_ic", 0.05)),
        }
        gate_payload: Dict[str, Any] = {
            "enabled": bool(enabled),
            "passed": True,
            "reason": "gate_disabled",
            "thresholds": thresholds,
            "metrics": {},
            "failed_rules": [],
        }
        if not enabled:
            return gate_payload

        summary: Dict[str, Any] = {}
        if isinstance(ic_diag_payload, dict):
            raw_summary = ic_diag_payload.get("decay_summary_selected_features", {})
            if isinstance(raw_summary, dict):
                summary = dict(raw_summary)
            if (not summary) and str(ic_diag_payload.get("path", "")).strip():
                try:
                    p = Path(str(ic_diag_payload.get("path"))).expanduser()
                    if p.exists():
                        blob = json.loads(p.read_text())
                        if isinstance(blob, dict):
                            loaded = blob.get("decay_summary_selected_features", {})
                            if isinstance(loaded, dict):
                                summary = dict(loaded)
                except Exception:
                    summary = {}

        if not summary:
            gate_payload["passed"] = False
            gate_payload["reason"] = "missing_ic_decay_summary"
            return gate_payload

        peak_h = float(summary.get("peak_horizon", 0.0) or 0.0)
        half_h = float(summary.get("half_life_horizon", 0.0) or 0.0)
        mono = float(summary.get("monotonicity_score", 0.0) or 0.0)
        peak_ic = float(summary.get("peak_ic", 0.0) or 0.0)
        failed: List[str] = []
        if peak_h < float(thresholds["min_peak_horizon"]):
            failed.append("min_peak_horizon")
        if half_h < float(thresholds["min_half_life_horizon"]):
            failed.append("min_half_life_horizon")
        if mono < float(thresholds["min_monotonicity_score"]):
            failed.append("min_monotonicity_score")
        if peak_ic < float(thresholds["min_peak_ic"]):
            failed.append("min_peak_ic")

        gate_payload["metrics"] = {
            "peak_horizon": peak_h,
            "half_life_horizon": half_h,
            "monotonicity_score": mono,
            "peak_ic": peak_ic,
        }
        gate_payload["failed_rules"] = failed
        gate_payload["passed"] = len(failed) == 0
        gate_payload["reason"] = "pass" if len(failed) == 0 else "threshold_violation"
        return gate_payload

    def _run_shap_validation(self, dataset: ResearchDataset) -> Dict[str, Any] | None:
        cfg = dict(self.config.get("shap_validation", {}))
        if not bool(cfg.get("enabled", False)):
            return None
        xgb_params = {}
        for name, params in self._model_specs():
            if str(name).strip().lower() == "xgboost":
                xgb_params = dict(params)
                break
        model = XGBoostModel(params=xgb_params)
        X = np.asarray(dataset.X, dtype=float)
        if X.ndim != 2 or X.shape[1] == 0:
            return {"status": "skipped", "reason": "empty_features"}

        med = np.nanmedian(X, axis=0)
        med = np.where(np.isfinite(med), med, 0.0)
        X_imp = np.where(np.isnan(X), med, X)
        mu = np.nanmean(X_imp, axis=0)
        sd = np.nanstd(X_imp, axis=0)
        mu = np.where(np.isfinite(mu), mu, 0.0)
        sd = np.where((~np.isfinite(sd)) | (sd <= 1e-8), 1.0, sd)
        X_scaled = (X_imp - mu) / sd
        X_scaled[~np.isfinite(X_scaled)] = 0.0

        model.fit(X_scaled, dataset.y)
        out_dir = str(cfg.get("output_dir", "reports/shap"))
        raw = compute_feature_importance(
            getattr(model, "estimator", model),
            X_scaled,
            list(dataset.feature_names),
            y=dataset.y,
            max_samples=int(cfg.get("max_samples", 2000) or 2000),
            output_dir=out_dir,
        )
        imps = raw.get("importances", {}) if isinstance(raw, dict) else {}
        low = [k for k, v in imps.items() if abs(float(v)) < 0.01]
        return {
            "status": "ok",
            "method": raw.get("method", "none") if isinstance(raw, dict) else "none",
            "plot_path": raw.get("plot_path") if isinstance(raw, dict) else None,
            "low_importance_features": low,
            "output_dir": out_dir,
        }

    def run(self, system_state: Dict[str, Any], freeze_active: bool) -> Dict[str, Any]:
        started = datetime.now()
        now_ist = self._now_ist()
        weekend_run = self._is_weekend(now_ist)
        stage_total = 13 if weekend_run else 12
        stage_idx = 0
        outputs: List[Dict[str, Any]] = []
        errors: List[str] = []
        summary: Dict[str, Any] = {
            "started_at": started.isoformat(),
            "started_at_ist": now_ist.isoformat(),
            "weekend_run": bool(weekend_run),
            "freeze_active": bool(freeze_active),
            "low_resource_mode": bool(self.low_resource_mode),
            "status": "running",
        }
        ic_diag_payload: Dict[str, Any] | None = None

        try:
            stage_idx += 1
            self._log_stage(stage_idx, stage_total, "Build Historical Dataset")
            dataset = self.dataset_manager.build_research_dataset()
            try:
                dataset, ic_diag = self._run_ic_diagnostics_gate(dataset)
                if isinstance(ic_diag, dict):
                    ic_diag_payload = dict(ic_diag)
                    outputs.append(
                        {
                            "type": "ic_diagnostics",
                            "actionable": False,
                            "generated_at": datetime.now().isoformat(),
                            "data": ic_diag,
                        }
                    )
            except Exception as exc:
                msg = f"ic_diagnostics_failed:{exc}"
                errors.append(msg)
                logger.warning(msg)
            outputs.append(
                {
                    "type": "research_dataset",
                    "actionable": False,
                    "generated_at": datetime.now().isoformat(),
                    "data": dataset.metadata,
                }
            )
            outputs.append(
                {
                    "type": "research_dataset",
                    "actionable": False,
                    "generated_at": datetime.now().isoformat(),
                    "data": {
                        "tft_feature_split": {
                            "static_features": int(len(getattr(dataset, "static_feature_names", []))),
                            "known_dynamic_features": int(len(getattr(dataset, "known_dynamic_feature_names", []))),
                            "observed_dynamic_features": int(len(getattr(dataset, "observed_dynamic_feature_names", []))),
                        }
                    },
                }
            )
            shap_payload = self._run_shap_validation(dataset)
            if isinstance(shap_payload, dict):
                outputs.append(
                    {
                        "type": "shap_validation",
                        "actionable": False,
                        "generated_at": datetime.now().isoformat(),
                        "data": shap_payload,
                    }
                )
            outputs.append(
                {
                    "type": "returns_partition",
                    "actionable": False,
                    "generated_at": datetime.now().isoformat(),
                    "data": self._build_returns_partition(),
                }
            )
            try:
                alpha_factory_payload = self._run_alpha_factory_stage(
                    dataset,
                    ic_diag_payload=ic_diag_payload,
                )
                if isinstance(alpha_factory_payload, dict):
                    outputs.append(
                        {
                            "type": "alpha_factory",
                            "actionable": False,
                            "generated_at": datetime.now().isoformat(),
                            "data": alpha_factory_payload,
                        }
                    )
            except Exception as exc:
                msg = f"alpha_factory_failed:{exc}"
                errors.append(msg)
                logger.warning(msg)

            # Dynamic factor + regime probabilities.
            stage_idx += 1
            self._log_stage(stage_idx, stage_total, "Regime/Factor Context")
            dfm = DynamicFactorModel(n_factors=int(self.config.get("n_macro_factors", 3)))
            factors = dfm.fit_transform(dataset.X)
            hmm_cfg = dict(self.config.get("hmm", {}))
            hmm = HMMRegimeModel(
                n_states=int(hmm_cfg.get("n_states", 3)),
                random_state=int(self.config.get("random_state", 42)),
                max_iter=int(hmm_cfg.get("max_iter", 400)),
                tol=float(hmm_cfg.get("tol", 1e-4)),
                n_init=int(hmm_cfg.get("n_init", 8)),
                min_samples_per_state=int(hmm_cfg.get("min_samples_per_state", 40)),
                allow_kmeans_fallback=bool(hmm_cfg.get("allow_kmeans_fallback", False)),
            )
            hmm.fit(factors)
            regime_probs = hmm.predict_proba(factors)
            latest_prob = regime_probs[-1].tolist() if len(regime_probs) else [1 / 3, 1 / 3, 1 / 3]
            outputs.append(
                {
                    "type": "regime_transition_analysis",
                    "actionable": True,
                    "generated_at": datetime.now().isoformat(),
                    "data": {
                        "model": "hmm_regime",
                        "latest_regime_probabilities": {
                            "LOW_VOL": float(latest_prob[0] if len(latest_prob) > 0 else 0.33),
                            "NORMAL": float(latest_prob[1] if len(latest_prob) > 1 else 0.33),
                            "CRISIS": float(latest_prob[2] if len(latest_prob) > 2 else 0.33),
                        },
                        "factor_dim": int(factors.shape[1]) if factors.ndim == 2 else 0,
                    },
                }
            )

            stage_idx += 1
            all_model_specs = self._model_specs()
            model_specs = self._apply_model_budget(all_model_specs, weekend_run=weekend_run)
            self._log_stage(
                stage_idx,
                stage_total,
                "Model Training + Walk-Forward",
                details=f"models={len(model_specs)}",
            )
            spec_map = {name: params for name, params in all_model_specs}
            model_results: Dict[str, Dict[str, Any]] = {}
            expected_models = self._expected_model_names()
            available_names = {name for name, _ in all_model_specs}
            selected_names = {name for name, _ in model_specs}
            skipped_models: List[Dict[str, Any]] = []
            for model_name in expected_models:
                if model_name in selected_names:
                    continue
                skip_reason = "budget_filtered"
                if model_name not in available_names:
                    skip_reason = (
                        "deep_models_disabled_low_resource"
                        if model_name in self._DEEP_MODELS and self.low_resource_mode
                        else "model_not_enabled"
                    )
                outputs.append(
                    {
                        "type": "model_validation",
                        "actionable": False,
                        "generated_at": datetime.now().isoformat(),
                        "data": {
                            "model": model_name,
                            "status": "skipped",
                            "reason": skip_reason,
                            "low_resource_mode": bool(self.low_resource_mode),
                        },
                    }
                )
                skipped_models.append({"model": model_name, "reason": skip_reason})
            total_models = max(1, len(model_specs))
            model_cooldown_seconds = max(
                0.0,
                float(self.config.get("model_cooldown_seconds", 0.0) or 0.0),
            )
            for m_idx, (model_name, params) in enumerate(model_specs, start=1):
                if model_cooldown_seconds > 0.0 and m_idx > 1:
                    logger.info(
                        "Model pacing cooldown: sleeping %.1fs before model=%s",
                        model_cooldown_seconds,
                        model_name,
                    )
                    time.sleep(model_cooldown_seconds)
                try:
                    logger.info(
                        "Model Progress %s %d/%d model=%s",
                        self._progress_bar(m_idx, total_models, width=18),
                        m_idx,
                        total_models,
                        model_name,
                    )
                    model = self._build_model(model_name, params)
                    result = self.pipeline.run(
                        model=model,
                        dataset=dataset,
                        progress_callback=self._window_progress_callback,
                    )
                    model_results[model_name] = result
                    outputs.append(
                        {
                            "type": "model_validation",
                            "actionable": False,
                            "generated_at": datetime.now().isoformat(),
                            "data": {
                                "model": model_name,
                                "aggregate_metrics": result.get("aggregate_metrics", {}),
                                "status": result.get("status", "unknown"),
                            },
                        }
                    )
                except Exception as exc:
                    msg = f"model_run_failed:{model_name}:{exc}"
                    errors.append(msg)
                    logger.warning(msg)
                    outputs.append(
                        {
                            "type": "model_validation",
                            "actionable": False,
                            "generated_at": datetime.now().isoformat(),
                            "data": {
                                "model": model_name,
                                "status": "failed",
                                "reason": str(exc),
                            },
                        }
                    )

            if self._alpha_lab_enabled(weekend_run=weekend_run):
                try:
                    alpha_lab_payload = self._run_alpha_lab(
                        dataset=dataset,
                        model_specs=model_specs,
                    )
                    outputs.append(
                        {
                            "type": "alpha_lab",
                            "actionable": False,
                            "generated_at": datetime.now().isoformat(),
                            "data": alpha_lab_payload,
                        }
                    )
                except Exception as exc:
                    msg = f"alpha_lab_failed:{exc}"
                    errors.append(msg)
                    logger.warning(msg)

            if not model_results:
                raise RuntimeError("all_model_runs_failed")

            best_name, best_payload = self._select_best_model(model_results)
            best_agg = best_payload.get("aggregate_metrics", {}) if best_payload else {}

            # Ensemble pass with top-3 models.
            stage_idx += 1
            self._log_stage(stage_idx, stage_total, "Ensemble + Meta Learner")
            ranked = sorted(
                model_results.items(),
                key=lambda x: float(x[1].get("aggregate_metrics", {}).get("avg_sharpe", 0.0)),
                reverse=True,
            )
            top = ranked[:3]
            min_ensemble_models = int(self.config.get("min_ensemble_models", 2))
            enable_ensemble = bool(self.config.get("enable_ensemble", True))
            if self.low_resource_mode and bool(self.config.get("disable_ensemble_in_low_resource", True)):
                enable_ensemble = False

            if enable_ensemble and len(top) >= max(2, min_ensemble_models):
                base_models = [self._build_model(name, spec_map.get(name, {})) for name, _ in top]
                ens = WeightedEnsemble(base_models)
                ens_result = self.pipeline.run(
                    model=ens,
                    dataset=dataset,
                    progress_callback=self._window_progress_callback,
                )
                model_results["weighted_ensemble_top3"] = ens_result
                outputs.append(
                    {
                        "type": "model_validation",
                        "actionable": False,
                        "generated_at": datetime.now().isoformat(),
                        "data": {
                            "model": "weighted_ensemble_top3",
                            "aggregate_metrics": ens_result.get("aggregate_metrics", {}),
                            "status": ens_result.get("status", "unknown"),
                        },
                    }
                )

                stack = StackingMetaLearner(base_models)
                stack_result = self.pipeline.run(
                    model=stack,
                    dataset=dataset,
                    progress_callback=self._window_progress_callback,
                )
                model_results["stacking_meta_top3"] = stack_result
                outputs.append(
                    {
                        "type": "model_validation",
                        "actionable": False,
                        "generated_at": datetime.now().isoformat(),
                        "data": {
                            "model": "stacking_meta_top3",
                            "aggregate_metrics": stack_result.get("aggregate_metrics", {}),
                            "status": stack_result.get("status", "unknown"),
                            "meta_weights": stack.summary(),
                        },
                    }
                )
            else:
                ensemble_skip_reason = "insufficient_models" if len(top) < max(2, min_ensemble_models) else "ensemble_disabled"
                outputs.append(
                    {
                        "type": "model_validation",
                        "actionable": False,
                        "generated_at": datetime.now().isoformat(),
                        "data": {
                            "model": "ensemble_phase",
                            "status": "skipped",
                            "reason": "ensemble_disabled_or_insufficient_models",
                            "enable_ensemble": bool(enable_ensemble),
                            "models_available": int(len(top)),
                        },
                    }
                )
                for ensemble_model in ("weighted_ensemble_top3", "stacking_meta_top3"):
                    outputs.append(
                        {
                            "type": "model_validation",
                            "actionable": False,
                            "generated_at": datetime.now().isoformat(),
                            "data": {
                                "model": ensemble_model,
                                "status": "skipped",
                                "reason": ensemble_skip_reason,
                                "enable_ensemble": bool(enable_ensemble),
                                "models_available": int(len(top)),
                            },
                        }
                    )

            # Structural Monte Carlo.
            stage_idx += 1
            self._log_stage(stage_idx, stage_total, "Structural Monte Carlo")
            mc = StructuralMonteCarlo(random_state=int(self.config.get("random_state", 42)))
            mc.fit(dataset.frame)
            mc_budget = self._mc_budget(weekend_run=weekend_run)
            sim = mc.simulate_paths(
                panel=dataset.frame.tail(int(self.config.get("mc_fit_rows", 50000))),
                n_paths=int(mc_budget["paths"]),
                horizon=int(mc_budget["horizon"]),
                stress_multiplier=float(self.config.get("mc_stress_multiplier", 1.0)),
            )
            mc_metrics = mc.evaluate(sim.get("paths", np.empty((0, 0))))
            outputs.append(
                {
                    "type": "monte_carlo_report",
                    "actionable": False,
                    "generated_at": datetime.now().isoformat(),
                    "data": {
                        "status": "completed",
                        **mc_metrics,
                        "budget": mc_budget,
                    },
                }
            )

            weekend_cfg = self.config.get("weekend_only_tasks", {})
            if weekend_run and bool(weekend_cfg.get("extended_scenario_sweep", True)):
                stage_idx += 1
                self._log_stage(stage_idx, stage_total, "Weekend Scenario Sweep")
                weekend_sweep = self._run_weekend_scenario_sweep(mc=mc, panel=dataset.frame)
                outputs.append(
                    {
                        "type": "weekend_research_sweep",
                        "actionable": False,
                        "generated_at": datetime.now().isoformat(),
                        "data": weekend_sweep,
                    }
                )

            # Capital simulation from best model predictions.
            stage_idx += 1
            self._log_stage(stage_idx, stage_total, "Capital Simulation + Opportunity Export")
            cap_metrics = {
                "final_capital": 0.0,
                "total_return": 0.0,
                "max_drawdown": 1.0,
                "risk_of_ruin": 1.0,
            }
            strategy_returns_row = np.asarray([], dtype=float)
            if best_name:
                model = self._build_model(
                    best_name,
                    spec_map.get(best_name, {}),
                )
                model.fit(dataset.X, dataset.y)
                pred = np.asarray(model.predict(dataset.X), dtype=float).reshape(-1)
                target_horizon_days = int(dataset.metadata.get("target_horizon_days", 1) or 1)
                target_realized_col = str(dataset.metadata.get("target_realized_col", "") or "").strip()
                realized_period = (
                    np.asarray(dataset.frame[target_realized_col], dtype=float).reshape(-1)
                    if target_realized_col and target_realized_col in dataset.frame.columns
                    else np.asarray(dataset.y, dtype=float).reshape(-1)
                )
                n_obs = int(min(len(pred), len(realized_period), len(dataset.frame)))
                pred = pred[:n_obs]
                realized_period = realized_period[:n_obs]
                realized_daily = _period_to_daily_returns(realized_period, period_days=target_horizon_days)
                strategy_returns_row = np.tanh(pred) * realized_daily
                port_cfg = dict(self.config.get("portfolio_construction", {}))
                strategy_returns_daily = build_cross_sectional_portfolio_returns(
                    y_true=realized_period,
                    y_pred=pred,
                    dates=(
                        dataset.frame["date"].to_numpy()[:n_obs]
                        if "date" in dataset.frame.columns
                        else np.arange(len(pred))
                    ),
                    tickers=(
                        dataset.frame["ticker"].to_numpy(dtype=str)[:n_obs]
                        if "ticker" in dataset.frame.columns
                        else None
                    ),
                    vol=(
                        dataset.frame["vol_20d"].to_numpy(dtype=float)[:n_obs]
                        if "vol_20d" in dataset.frame.columns
                        else None
                    ),
                    long_short_quantile=float(port_cfg.get("long_short_quantile", 0.20)),
                    min_assets_per_day=int(port_cfg.get("min_assets_per_day", 8)),
                    max_weight_per_asset=float(port_cfg.get("max_weight_per_asset", 0.10)),
                    use_vol_scaling=bool(port_cfg.get("use_vol_scaling", True)),
                    rebalance_frequency_days=int(port_cfg.get("rebalance_frequency_days", 1)),
                    target_horizon_days=target_horizon_days,
                )
                sim_input = strategy_returns_daily if len(strategy_returns_daily) else strategy_returns_row
                cap_metrics = self.capital_sim.simulate(sim_input)
                cap_metrics["portfolio_days"] = int(len(strategy_returns_daily))
                cap_metrics["row_level_obs"] = int(len(strategy_returns_row))
                cap_metrics["target_horizon_days"] = int(target_horizon_days)
                cap_metrics["return_source"] = "realized_target_base" if target_realized_col else "model_target"
                # Export research-origin options opportunities for live overlay consumption.
                options_opp = self._export_options_research_opportunities(
                    dataset=dataset,
                    model=model,
                    model_name=best_name,
                    feature_importance=getattr(model, "feature_importance", lambda: {})(),
                )
                outputs.append(
                    {
                        "type": "options_research_opportunities",
                        "actionable": True,
                        "generated_at": datetime.now().isoformat(),
                        "data": options_opp,
                    }
                )
            else:
                outputs.append(
                    {
                        "type": "options_research_opportunities",
                        "actionable": False,
                        "generated_at": datetime.now().isoformat(),
                        "data": {"status": "skipped", "reason": "no_best_model"},
                    }
                )

            outputs.append(
                {
                    "type": "capital_simulation",
                    "actionable": False,
                    "generated_at": datetime.now().isoformat(),
                    "data": cap_metrics,
                }
            )

            rel = self._relationship_discovery(dataset)
            stage_idx += 1
            self._log_stage(stage_idx, stage_total, "Relationship Discovery")
            outputs.append(
                {
                    "type": "relationship_discovery",
                    "actionable": False,
                    "generated_at": datetime.now().isoformat(),
                    "data": rel,
                }
            )

            # Regime-sliced performance profile from current cycle.
            if len(strategy_returns_row) and len(regime_probs):
                regime_labels = np.argmax(np.asarray(regime_probs, dtype=float), axis=1)
                min_len = int(min(len(strategy_returns_row), len(regime_labels), len(dataset.frame)))
                if min_len > 0:
                    df_reg = dataset.frame.tail(min_len).copy()
                    df_reg["regime"] = regime_labels[-min_len:]
                    masks = split_by_regime(df_reg, regime_col="regime")
                    sliced = {}
                    for regime_name, mask in masks.items():
                        m = np.asarray(mask, dtype=bool)
                        vals = strategy_returns_row[-min_len:][m]
                        if len(vals) == 0:
                            continue
                        mu = float(np.mean(vals))
                        sd = float(np.std(vals))
                        sliced[regime_name] = {
                            "samples": int(len(vals)),
                            "mean_return": mu,
                            "volatility": sd,
                            "sharpe_like": float(mu / (sd + 1e-8)),
                        }
                    if sliced:
                        outputs.append(
                            {
                                "type": "regime_sliced_performance",
                                "actionable": False,
                                "generated_at": datetime.now().isoformat(),
                                "data": {
                                    "model": best_name or "none",
                                    "metrics": sliced,
                                },
                            }
                        )

            # Candidate scoring and promotion proposal (still governed by freeze/manual review).
            stage_idx += 1
            self._log_stage(stage_idx, stage_total, "Candidate Scoring + Awareness")
            regime_disp = self._regime_dispersion(best_payload.get("regime_metrics", {}) if best_payload else {})
            score_payload = self.scorer.score(
                walk_forward_metrics=best_agg,
                mc_metrics=mc_metrics,
                regime_metrics={"dispersion": regime_disp},
            )
            threshold = float(self.config.get("candidate_acceptance_threshold", 0.65))
            structural_gate = self._evaluate_structural_promotion_gate(ic_diag_payload)
            actionable = bool(score_payload.get("candidate_score", 0.0) >= threshold) and bool(structural_gate.get("passed", True))
            proposal = {
                "best_model": best_name,
                "acceptance_threshold": threshold,
                "actionable_candidate": actionable,
                "score": score_payload,
                "capital_metrics": cap_metrics,
                "mc_metrics": mc_metrics,
                "promotion_gates": {
                    "score_gate_passed": bool(score_payload.get("candidate_score", 0.0) >= threshold),
                    "structural_gate": structural_gate,
                },
            }
            outputs.append(
                {
                    "type": "model_promotion",
                    "actionable": actionable,
                    "generated_at": datetime.now().isoformat(),
                    "data": proposal,
                }
            )

            awareness = self.memory.update_cycle(
                candidate_score=float(score_payload.get("candidate_score", 0.0)),
                accepted=bool(actionable),
                errors_count=len(errors),
                timestamp=datetime.utcnow().isoformat(),
            )
            outputs.append(
                {
                    "type": "research_self_awareness",
                    "actionable": False,
                    "generated_at": datetime.now().isoformat(),
                    "data": {
                        **awareness,
                        "autonomous_budget": self._budget_cfg(),
                        "models_tested_this_cycle": [m for m, _ in model_specs],
                        "model_selection_summary": {
                            "expected_models": list(expected_models),
                            "selected_models": [m for m, _ in model_specs],
                            "skipped_models": skipped_models,
                            "available_models_after_policy": sorted(list(available_names)),
                            "low_resource_mode": bool(self.low_resource_mode),
                        },
                        "mode_boundary": {
                            "current_mode": str(system_state.get("current_mode", "unknown")),
                            "weekend_run": bool(weekend_run),
                            "freeze_active": bool(freeze_active),
                        },
                    },
                }
            )

            if best_name:
                exp = self._run_autonomous_exploration(
                    dataset=dataset,
                    best_model_name=best_name,
                    best_model_params=spec_map.get(best_name, {}),
                    weekend_run=weekend_run,
                    freeze_active=freeze_active,
                )
                outputs.append(
                    {
                        "type": "autonomous_exploration",
                        "actionable": not bool(exp.get("non_actionable", False)),
                        "generated_at": datetime.now().isoformat(),
                        "data": exp,
                    }
                )

            # If candidate is below threshold, emit mutation proposal for next cycle.
            stage_idx += 1
            self._log_stage(stage_idx, stage_total, "Mutation + Hyperopt Gate")
            if (not actionable) and best_name:
                base_params = spec_map.get(best_name, {})
                adaptive_mutation = float(awareness.get("adaptive_mutation_rate", self.config.get("mutation_rate", 0.25)))
                mutated = self.mutator.mutate_params(base_params, mutation_rate=adaptive_mutation)
                fail_reason = "below_acceptance_threshold"
                if bool(score_payload.get("candidate_score", 0.0) >= threshold) and not bool(structural_gate.get("passed", True)):
                    fail_reason = "failed_structural_promotion_gate"
                outputs.append(
                    {
                        "type": "candidate_model",
                        "actionable": False,
                        "generated_at": datetime.now().isoformat(),
                        "data": {
                            "source_model": best_name,
                            "source_params": base_params,
                            "mutated_params": mutated,
                            "adaptive_mutation_rate": adaptive_mutation,
                            "reason": fail_reason,
                        },
                    }
                )

            # Hyperopt when enabled, otherwise run governed sensitivity scan.
            hyper = self._maybe_hyperopt(best_name, dataset=dataset, freeze_active=freeze_active)
            if hyper is not None:
                param_payload = {
                    "target_model": best_name,
                    "mode": "bayesian_hyperopt",
                    "optimization": hyper,
                    "requires_manual_approval": True,
                    "freeze_active": bool(freeze_active),
                    "non_actionable": bool(hyper.get("non_actionable", False)),
                }
            else:
                param_payload = self._run_parameter_sensitivity_search(
                    model_name=best_name,
                    dataset=dataset,
                    base_params=spec_map.get(best_name, {}),
                    weekend_run=weekend_run,
                    freeze_active=freeze_active,
                )

            if isinstance(param_payload, dict):
                outputs.append(
                    {
                        "type": "parameter_search",
                        "actionable": not bool(param_payload.get("non_actionable", False)),
                        "generated_at": datetime.now().isoformat(),
                        "data": param_payload,
                    }
                )

            stage_idx += 1
            self._log_stage(stage_idx, stage_total, "Certification Integrity Gates")
            if self._certification_enabled():
                try:
                    cert_payload = self.certifier.evaluate(
                        CertificationContext(
                            outputs=list(outputs),
                            model_results=model_results,
                            best_model=str(best_name or ""),
                            best_payload=dict(best_payload or {}),
                            param_payload=dict(param_payload or {}),
                            cap_metrics=dict(cap_metrics or {}),
                            dataset_metadata=dict(dataset.metadata),
                            dataset_frame=dataset.frame.copy(),
                            portfolio_cfg=dict(self.config.get("portfolio_construction", {})),
                            freeze_active=bool(freeze_active),
                            weekend_run=bool(weekend_run),
                            started_at=started,
                            completed_at=datetime.now(),
                            system_state=dict(system_state or {}),
                        )
                    )
                except Exception as exc:
                    msg = f"certification_failed:{exc}"
                    logger.exception(msg)
                    errors.append(msg)
                    cert_payload = {
                        "integrity_summary": {
                            "mode": self._certification_mode(),
                            "enforcement_active": bool(self._certification_mode() == "enforce"),
                            "certification_enabled": True,
                            "hard_fail_triggered": True,
                            "critical_failures": [msg],
                            "critical_rule_failures": [msg],
                            "critical_failure_details": [],
                            "advisory_warnings": [],
                            "certification_passed": False,
                        }
                    }

                self._register_certification_snapshot(cert_payload)
                self._apply_certification_policy(
                    outputs=outputs,
                    cert_payload=cert_payload,
                    errors=errors,
                    summary=summary,
                )
                outputs.append(
                    {
                        "type": "integrity_summary",
                        "actionable": False,
                        "generated_at": datetime.now().isoformat(),
                        "data": cert_payload,
                    }
                )
            else:
                summary["certification_mode"] = "disabled"
                summary["certification_passed"] = True

            # RL policy update (model-selection policy, not direct trading decisions).
            stage_idx += 1
            self._log_stage(stage_idx, stage_total, "RL Policy + Bridges + Tracker")
            regime_idx = int(np.argmax(np.asarray(latest_prob, dtype=float))) if latest_prob else 1
            action_idx = self.rl_agent.select_action(regime_idx)
            reward = float(score_payload.get("raw_score", 0.0))
            self.rl_agent.update(regime=regime_idx, action=action_idx, reward=reward, next_regime=regime_idx)
            outputs.append(
                {
                    "type": "regime_rl_policy",
                    "actionable": False,
                    "generated_at": datetime.now().isoformat(),
                    "data": {
                        "selected_action": int(action_idx),
                        "reward": reward,
                        "policy_snapshot": self.rl_agent.snapshot(),
                    },
                }
            )

            # Bridges + memory + tracker.
            allocator_bridge = self.allocator_bridge.export_health_scores(model_results)
            governor_bridge = self.governor_bridge.export_allocation_intent(
                best_model=best_name or "none",
                confidence=float(score_payload.get("candidate_score", 0.0)),
                notes={
                    "freeze_active": bool(freeze_active),
                    "research_proposal_only": True,
                },
            )
            outputs.append(
                {
                    "type": "integration_bridge",
                    "actionable": False,
                    "generated_at": datetime.now().isoformat(),
                    "data": {
                        "allocator_bridge": allocator_bridge,
                        "governor_bridge": governor_bridge,
                    },
                }
            )

            if best_name and best_agg:
                self.memory.update_model(best_name, {**best_agg, "timestamp": datetime.utcnow().isoformat()})

            self.tracker.log(
                {
                    "module": "research_controller",
                    "freeze_active": bool(freeze_active),
                    "weekend_run": bool(weekend_run),
                    "best_model": best_name,
                    "candidate_score": float(score_payload.get("candidate_score", 0.0)),
                    "awareness": awareness,
                    "outputs_count": len(outputs),
                    "errors": errors,
                }
            )

            summary.update(
                {
                    "status": "completed",
                    "best_model": best_name,
                    "candidate_score": float(score_payload.get("candidate_score", 0.0)),
                    "awareness": awareness,
                    "outputs_count": len(outputs),
                    "models_ran": list(model_results.keys()),
                    "errors_count": len(errors),
                }
            )
            stage_idx += 1
            self._log_stage(
                min(stage_idx, stage_total),
                stage_total,
                "Cycle Complete",
                details=f"best_model={best_name or 'none'} score={float(score_payload.get('candidate_score', 0.0)):.4f}",
            )
        except Exception as exc:
            err = f"research_controller_failed:{exc}"
            errors.append(err)
            logger.exception(err)
            summary.update({"status": "failed", "error": str(exc), "errors_count": len(errors)})

        summary["completed_at"] = datetime.now().isoformat()
        summary["duration_seconds"] = float((datetime.now() - started).total_seconds())
        return {
            "summary": summary,
            "outputs": outputs,
            "errors": errors,
        }
