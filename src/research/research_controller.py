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
from .alpha_factory import (
    apply_family_feature_weights,
    build_family_factor_table,
    build_feature_family_map,
    compute_live_monitoring_metrics,
    optimize_family_blend,
    simulate_signal_stacking,
)
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
from .mutation_engine import MutationEngine
from .portfolio_governor_bridge import PortfolioGovernorBridge
from .research_memory import ResearchMemory
from .reinforcement_regime_agent import RegimeSwitchAgent
from .regime_split import split_by_regime
from .splits import rolling_time_splits
from .structural_monte_carlo import StructuralMonteCarlo
from .training_pipeline import TrainingPipeline
from .walk_forward_validator import build_cross_sectional_portfolio_returns


logger = logging.getLogger(__name__)
_TRADE_ID_TS_RE = re.compile(r"^POS_(\d{8})_(\d{6})_")


class ResearchController:
    """Full historical research loop (offline only)."""

    def __init__(self, config: Dict[str, Any] | None = None, project_root: Path | None = None):
        self.config = copy.deepcopy(config or {})
        self.project_root = Path(project_root) if project_root else Path(".")
        self.low_resource_mode = self._is_low_resource_mode()
        if self.low_resource_mode:
            self._apply_low_resource_overrides()

        dataset_cfg = dict(self.config.get("dataset", {}))
        self.dataset_manager = DatasetManager(project_root=self.project_root, config=dataset_cfg)

        training_cfg = dict(self.config.get("training", {}))
        self.pipeline = TrainingPipeline(
            train_periods=int(training_cfg.get("train_periods", 756)),
            valid_periods=int(training_cfg.get("valid_periods", 126)),
            test_periods=int(training_cfg.get("test_periods", 126)),
            step_periods=int(training_cfg.get("step_periods", 63)),
            max_windows=int(training_cfg.get("max_windows", 10)),
            start_window=int(training_cfg.get("start_window", 0)),
            portfolio_cfg=dict(self.config.get("portfolio_construction", {})),
            **self._holdout_training_kwargs(),
        )

        self.scorer = CandidateScorer()
        self.tracker = ExperimentTracker(path=str(self.config.get("experiment_path", "data/research/experiments.ndjson")))
        self.memory = ResearchMemory(path=str(self.config.get("memory_path", "data/research/research_memory.json")))
        self.mutator = MutationEngine(random_state=int(self.config.get("random_state", 42)))
        self.capital_sim = CapitalSimulator(initial_capital=float(self.config.get("simulation_initial_capital", 1_000_000.0)))
        self.allocator_bridge = CapitalAllocatorBridge()
        self.governor_bridge = PortfolioGovernorBridge()

        self.rl_agent = RegimeSwitchAgent(n_regimes=3, n_actions=max(1, len(self._model_specs())), random_state=int(self.config.get("random_state", 42)))
        self.optimizer = BayesianOptimizer(
            n_calls=int(self.config.get("hyperopt_calls", 12)),
            random_state=int(self.config.get("random_state", 42)),
            strict_gp_only=bool(self.config.get("strict_bayesian_only", True)),
        )

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

        # Keep deep models opt-in on low-resource hosts unless explicitly forced.
        if not bool(self.config.get("force_deep_models_in_low_resource", False)):
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

    def _model_specs(self) -> List[Tuple[str, Dict[str, Any]]]:
        base = [
            ("lightgbm", {"n_estimators": 240, "learning_rate": 0.03}),
            ("xgboost", {"n_estimators": 300, "learning_rate": 0.03, "max_depth": 6}),
            ("catboost", {"iterations": 220, "depth": 6, "learning_rate": 0.03}),
            ("random_forest", {"n_estimators": 350, "max_depth": 12}),
            ("lstm", {"lookback": 20, "epochs": 10, "hidden_dim": 64, "lr": 1e-3}),
            ("tcn", {"lookback": 20, "epochs": 8, "channels": 32, "lr": 1e-3}),
            (
                "transformer",
                {
                    "lookback": 30,
                    "epochs": 12,
                    "d_model": 64,
                    "nhead": 4,
                    "num_layers": 2,
                    "dim_feedforward": 128,
                    "dropout": 0.1,
                    "batch_size": 128,
                    "patience": 4,
                    "lr": 1e-3,
                },
            ),
        ]

        if not bool(self.config.get("enable_deep_models", False)):
            base = [(n, p) for n, p in base if n not in {"lstm", "tcn", "transformer"}]

        enabled = self.config.get("enabled_models")
        if isinstance(enabled, list) and enabled:
            enabled_set = {str(x).strip().lower() for x in enabled}
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
        n = name.lower()
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

        target_col = str(dataset.metadata.get("target_col", "forward_return_5d"))
        raw_h = cfg.get("horizons", [5, 10, 20])
        if isinstance(raw_h, (list, tuple)):
            horizons = [int(h) for h in raw_h if str(h).strip()]
        else:
            horizons = [5, 10, 20]
        report = compute_feature_ic_diagnostics(
            dataset.frame,
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

        out_dir = Path(str(cfg.get("output_dir", "data/research/ic_diagnostics")))
        if not out_dir.is_absolute():
            out_dir = self.project_root / out_dir
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = out_dir / f"ic_report_{ts}.json"
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
            "top_features": list(report.get("top_features", [])),
            "decay_summary_selected_features": dict(
                report.get("decay_summary_selected_features", {}) or {}
            ),
            "regime_decay_summary_selected_features": dict(
                report.get("regime_decay_summary_selected_features", {}) or {}
            ),
        }

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
                train_periods=int(cfg.get("oos_train_periods", self.pipeline.train_periods)),
                valid_periods=int(cfg.get("oos_valid_periods", self.pipeline.valid_periods)),
                test_periods=int(cfg.get("oos_test_periods", self.pipeline.test_periods)),
                step_periods=int(cfg.get("oos_step_periods", self.pipeline.step_periods)),
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

        out_dir = Path(str(cfg.get("output_dir", "data/research/alpha_factory")))
        if not out_dir.is_absolute():
            out_dir = self.project_root / out_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = out_dir / f"alpha_factory_report_{ts}.json"
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

    def run(self, system_state: Dict[str, Any], freeze_active: bool) -> Dict[str, Any]:
        started = datetime.now()
        now_ist = self._now_ist()
        weekend_run = self._is_weekend(now_ist)
        stage_total = 12 if weekend_run else 11
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
            model_specs = self._apply_model_budget(self._model_specs(), weekend_run=weekend_run)
            self._log_stage(
                stage_idx,
                stage_total,
                "Model Training + Walk-Forward",
                details=f"models={len(model_specs)}",
            )
            spec_map = {name: params for name, params in model_specs}
            model_results: Dict[str, Dict[str, Any]] = {}
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
                    next((p for n, p in self._model_specs() if n == best_name), {}),
                )
                model.fit(dataset.X, dataset.y)
                pred = np.asarray(model.predict(dataset.X), dtype=float)
                strategy_returns_row = np.tanh(pred) * np.asarray(dataset.y, dtype=float)
                port_cfg = dict(self.config.get("portfolio_construction", {}))
                strategy_returns_daily = build_cross_sectional_portfolio_returns(
                    y_true=np.asarray(dataset.y, dtype=float),
                    y_pred=pred,
                    dates=dataset.frame["date"].to_numpy() if "date" in dataset.frame.columns else np.arange(len(pred)),
                    tickers=dataset.frame["ticker"].to_numpy(dtype=str) if "ticker" in dataset.frame.columns else None,
                    vol=dataset.frame["vol_20d"].to_numpy(dtype=float) if "vol_20d" in dataset.frame.columns else None,
                    long_short_quantile=float(port_cfg.get("long_short_quantile", 0.20)),
                    min_assets_per_day=int(port_cfg.get("min_assets_per_day", 8)),
                    max_weight_per_asset=float(port_cfg.get("max_weight_per_asset", 0.10)),
                    use_vol_scaling=bool(port_cfg.get("use_vol_scaling", True)),
                    rebalance_frequency_days=int(port_cfg.get("rebalance_frequency_days", 1)),
                )
                sim_input = strategy_returns_daily if len(strategy_returns_daily) else strategy_returns_row
                cap_metrics = self.capital_sim.simulate(sim_input)
                cap_metrics["portfolio_days"] = int(len(strategy_returns_daily))
                cap_metrics["row_level_obs"] = int(len(strategy_returns_row))
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

            # Optional Bayesian hyperopt for best model.
            hyper = self._maybe_hyperopt(best_name, dataset=dataset, freeze_active=freeze_active)
            if hyper is not None:
                outputs.append(
                    {
                        "type": "parameter_search",
                        "actionable": not bool(hyper.get("non_actionable", False)),
                        "generated_at": datetime.now().isoformat(),
                        "data": {
                            "target_model": best_name,
                            "optimization": hyper,
                            "requires_manual_approval": True,
                            "freeze_active": bool(freeze_active),
                        },
                    }
                )

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
