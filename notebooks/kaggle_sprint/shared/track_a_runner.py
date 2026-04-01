"""Robust Track A Kaggle runner with resume, day skipping, and soft-fail behavior."""

from __future__ import annotations

import gc
import importlib
import os
import random
import re
import subprocess
import sys
import time
import traceback
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from sprint_utils import (
    DEFAULT_PROTECTED_FEATURES,
    DEFAULT_RAW_FINANCIAL_FEATURES,
    DEFAULT_REDUCED_EXCLUDE_REGEX,
    EnsembleBuilder,
    FactorICAnalyzer,
    PromotionVerdict,
    RegimeConditionalIC,
    ResultsSaver,
    SectorICAnalyzer,
    SprintDataLoader,
    SprintWalkForward,
    expand_feature_importance,
    select_feature_subset,
    top_ic_feature_names,
)


def _ensure_module(module_name: str, pip_spec: str | None = None):
    try:
        return importlib.import_module(module_name)
    except Exception:
        spec = pip_spec or module_name
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", spec],
                check=False,
                capture_output=True,
                text=True,
            )
        except Exception:
            return None
        try:
            return importlib.import_module(module_name)
        except Exception:
            return None


torch = _ensure_module("torch")
xgb = _ensure_module("xgboost", "xgboost>=2.0")
catboost = _ensure_module("catboost")
lightgbm = _ensure_module("lightgbm")
nn = getattr(torch, "nn", None)
CatBoostRegressor = getattr(catboost, "CatBoostRegressor", None)
CatBoostRanker = getattr(catboost, "CatBoostRanker", None)
Pool = getattr(catboost, "Pool", None)
LGBMRanker = getattr(lightgbm, "LGBMRanker", None)

warnings.filterwarnings("ignore")


def _parse_day_set(raw: str | None, default: set[int] | None = None) -> set[int]:
    if raw is None:
        return set(default or set())
    values: set[int] = set()
    for token in raw.split(","):
        cleaned = token.strip()
        if not cleaned:
            continue
        try:
            values.add(int(cleaned))
        except ValueError:
            continue
    return values if values else set(default or set())


def _parse_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _parse_csv_list(raw: str | None) -> list[str]:
    if raw is None:
        return []
    values = []
    for token in raw.split(","):
        cleaned = token.strip()
        if cleaned:
            values.append(cleaned)
    return values


def _normalize_model_token(name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "", str(name).strip().lower())
    aliases = {
        "xgb": "xgboost",
        "lgb": "lightgbm",
        "lgbm": "lightgbm",
        "cb": "catboost",
    }
    return aliases.get(cleaned, cleaned)


def _safe_float(value: Any, default: float = float("-inf")) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return numeric if np.isfinite(numeric) else default


@dataclass
class TrackARunConfig:
    data_dir: Path | None = None
    output_dir: Path | None = None
    track_name: str = "track_a_classical"
    device: str = "cuda" if torch is not None and torch.cuda.is_available() else "cpu"
    skip_days: set[int] = field(default_factory=lambda: {1})
    force_rerun_days: set[int] = field(default_factory=set)
    continue_on_error: bool = True
    resume_from_checkpoint: bool = True
    run_profile: str = "full"
    max_splits: int | None = None
    model_filter: list[str] = field(default_factory=list)
    feature_mode: str = "full"
    reduced_feature_count: int = 60
    reduced_feature_min_abs_ic: float = 0.005
    feature_exclude_regex: str | None = DEFAULT_REDUCED_EXCLUDE_REGEX
    normalize_raw_financials: bool = False
    require_group_ranking: bool = True

    @classmethod
    def from_env(cls) -> "TrackARunConfig":
        output_dir = (
            Path("/kaggle/working/track_a_results")
            if Path("/kaggle").exists()
            else Path("./track_a_results")
        )
        data_dir_env = os.environ.get("TRACK_A_DATA_DIR")
        max_splits_env = os.environ.get("TRACK_A_MAX_SPLITS")
        reduced_count_env = os.environ.get("TRACK_A_REDUCED_FEATURE_COUNT")
        reduced_min_ic_env = os.environ.get("TRACK_A_REDUCED_FEATURE_MIN_ABS_IC")
        feature_exclude_regex = os.environ.get("TRACK_A_FEATURE_EXCLUDE_REGEX", DEFAULT_REDUCED_EXCLUDE_REGEX)
        return cls(
            data_dir=Path(data_dir_env) if data_dir_env else None,
            output_dir=Path(os.environ.get("TRACK_A_OUTPUT_DIR", str(output_dir))),
            skip_days=_parse_day_set(os.environ.get("TRACK_A_SKIP_DAYS"), default={1}),
            force_rerun_days=_parse_day_set(os.environ.get("TRACK_A_FORCE_RERUN_DAYS"), default=set()),
            continue_on_error=_parse_bool(os.environ.get("TRACK_A_CONTINUE_ON_ERROR"), True),
            resume_from_checkpoint=_parse_bool(os.environ.get("TRACK_A_RESUME_CHECKPOINTS"), True),
            run_profile=os.environ.get("TRACK_A_RUN_PROFILE", "full").strip().lower() or "full",
            max_splits=int(max_splits_env) if max_splits_env and max_splits_env.strip() else None,
            model_filter=_parse_csv_list(os.environ.get("TRACK_A_MODEL_FILTER")),
            feature_mode=os.environ.get("TRACK_A_FEATURE_MODE", "full").strip().lower() or "full",
            reduced_feature_count=int(reduced_count_env) if reduced_count_env and reduced_count_env.strip() else 60,
            reduced_feature_min_abs_ic=(
                float(reduced_min_ic_env) if reduced_min_ic_env and reduced_min_ic_env.strip() else 0.005
            ),
            feature_exclude_regex=feature_exclude_regex or None,
            normalize_raw_financials=_parse_bool(os.environ.get("TRACK_A_NORMALIZE_RAW_FINANCIALS"), False),
            require_group_ranking=_parse_bool(os.environ.get("TRACK_A_REQUIRE_GROUP_RANKING"), True),
        )


class TrackARunner:
    def __init__(self, config: TrackARunConfig | None = None):
        self.config = config or TrackARunConfig.from_env()
        self.output_dir = Path(self.config.output_dir or "./track_a_results")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.track_name = self.config.track_name
        self.saver = ResultsSaver()
        self.loader = SprintDataLoader()
        self.engine = SprintWalkForward()
        self.cached_results = self.saver.load_combined(self.output_dir, self.track_name)
        self.state: dict[str, Any] = {}
        self.day_status: dict[str, Any] = {}
        self.sprint_start = time.time()

    def _selected_models(self) -> set[str]:
        return {_normalize_model_token(name) for name in self.config.model_filter if name.strip()}

    def _is_model_enabled(self, model_name: str) -> bool:
        selected = self._selected_models()
        return not selected or _normalize_model_token(model_name) in selected

    def _reduced_feature_names(self) -> list[str]:
        cached = self.state.get("reduced_feature_names")
        if isinstance(cached, list) and cached:
            return cached
        ic_table = self._ensure_ic_table_available("reduced feature selection")
        reduced = top_ic_feature_names(
            ic_table,
            self.state["feature_names"],
            limit=self.config.reduced_feature_count,
            min_abs_ic=self.config.reduced_feature_min_abs_ic,
            exclude_regex=self.config.feature_exclude_regex,
        )
        self.state["reduced_feature_names"] = reduced
        return reduced

    def _feature_prep_config(self) -> dict[str, Any]:
        reduced_names = self._reduced_feature_names() if self.config.feature_mode == "reduced" else []
        return {
            "feature_mode": self.config.feature_mode,
            "reduced_feature_names": reduced_names,
            "protected_features": list(DEFAULT_PROTECTED_FEATURES),
            "exclude_regex": self.config.feature_exclude_regex if self.config.feature_mode == "reduced" else None,
            "normalize_raw_financials": self.config.normalize_raw_financials,
            "raw_financial_features": list(DEFAULT_RAW_FINANCIAL_FEATURES),
            "financial_denominator_feature": "total_assets",
        }

    @staticmethod
    def _prepare_model_features(
        X_train: np.ndarray,
        X_test: np.ndarray,
        feature_names: list[str],
        config: dict[str, Any],
    ) -> tuple[np.ndarray, np.ndarray, list[int], list[str]]:
        return select_feature_subset(
            X_train,
            X_test,
            feature_names,
            feature_mode=str(config.get("feature_mode", "full")),
            reduced_feature_names=list(config.get("reduced_feature_names", [])),
            protected_features=list(config.get("protected_features", list(DEFAULT_PROTECTED_FEATURES))),
            exclude_regex=config.get("exclude_regex"),
        )

    @staticmethod
    def _split_ranking_train_val(
        X_train: np.ndarray,
        y_train: np.ndarray,
        group_sizes: list[int],
        val_fraction: float = 0.10,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, list[int], list[int]]:
        groups = [int(size) for size in group_sizes if int(size) > 0]
        if len(groups) < 3:
            return X_train, X_train[:0], y_train, y_train[:0], groups, []
        n_val_groups = max(1, int(round(len(groups) * float(val_fraction))))
        n_val_groups = min(n_val_groups, len(groups) - 1)
        train_groups = groups[:-n_val_groups]
        val_groups = groups[-n_val_groups:]
        cut = int(sum(train_groups))
        return (
            X_train[:cut],
            X_train[cut:],
            y_train[:cut],
            y_train[cut:],
            train_groups,
            val_groups,
        )

    @staticmethod
    def _require_group_sizes(context: dict[str, Any], y_train: np.ndarray, *, require: bool) -> list[int]:
        groups = [int(size) for size in (context.get("train_group_sizes") or []) if int(size) > 0]
        if groups and int(sum(groups)) == int(len(y_train)):
            return groups
        if require:
            raise ValueError("Per-date train_group_sizes are missing or inconsistent for the ranking model.")
        return [int(len(y_train))]

    @staticmethod
    def _to_group_relevance_labels(
        y_values: np.ndarray,
        group_sizes: list[int],
        *,
        max_relevance: int = 30,
    ) -> np.ndarray:
        """
        Convert continuous signed returns into non-negative integer relevance labels
        per date-group so ranking libraries can optimize NDCG-style objectives.

        LightGBM rankers expect integer labels in ``[0, n_labels - 1]``. Keeping the
        largest emitted label at 30 avoids the ``Label 31 is not less than the number
        of label mappings`` failure that shows up on larger cross-sections.
        """

        y_arr = np.asarray(y_values, dtype=float).reshape(-1)
        labels = np.zeros(len(y_arr), dtype=np.int32)
        cursor = 0
        for group_size in group_sizes:
            size = int(group_size)
            if size <= 0:
                continue
            window = y_arr[cursor : cursor + size]
            if size == 1:
                labels[cursor] = 0
                cursor += size
                continue

            order = np.argsort(np.argsort(window, kind="mergesort"), kind="mergesort")
            if size - 1 <= max_relevance:
                labels[cursor : cursor + size] = np.minimum(order, max_relevance).astype(np.int32)
            else:
                scaled = np.floor(order.astype(float) * float(max_relevance) / float(size - 1))
                labels[cursor : cursor + size] = np.clip(scaled, 0, max_relevance).astype(np.int32)
            cursor += size

        if cursor != len(y_arr):
            raise ValueError(f"Constructed relevance labels for {cursor} rows, expected {len(y_arr)}")
        if len(labels) and int(labels.max()) > max_relevance:
            raise ValueError(
                f"Constructed relevance labels with max {int(labels.max())}, expected <= {max_relevance}"
            )
        return labels

    def run(self) -> dict[str, Any]:
        self._load_data()
        self._bootstrap_day1_if_needed()
        self._run_day(1, "Factor IC Analysis", self._run_day1)
        self._run_day(2, "XGBoost + CatBoost Walk-Forward", self._run_day2)
        self._run_day(3, "Sequence Model Walk-Forward", self._run_day3)
        self._run_day(4, "Regime + Sector Analysis", self._run_day4)
        self._run_day(5, "India-Specific Factor Tests", self._run_day5)
        self._run_day(6, "Ensemble + Deployment Analysis", self._run_day6)
        self._run_day(7, "Final Verdict", self._run_day7)
        self._save_run_state(status="completed")
        return self.state

    def _ensure_ic_table_available(self, reason: str) -> pd.DataFrame:
        existing = self.state.get("ic_table")
        if isinstance(existing, pd.DataFrame) and not existing.empty:
            return existing

        cached_ic = self.saver.load_day(self.output_dir, self.track_name, "day1_ic_table")
        if isinstance(cached_ic, list) and cached_ic:
            self.state["ic_table"] = pd.DataFrame(cached_ic)
            print(f"Loaded cached day-1 IC table for {reason} with {len(self.state['ic_table'])} rows.", flush=True)
            return self.state["ic_table"]

        print(f"Computing IC table for {reason}...", flush=True)
        ic_table = self.state["analyzer"].compute_ic_table(
            self.state["features_df"],
            self.state["feature_names"],
            progress_label=f"IC bootstrap ({reason})",
        )
        self.state["ic_table"] = ic_table
        self.saver.save_all(
            self.output_dir,
            self.track_name,
            {"day1_ic_table": ic_table.to_dict(orient="records")},
        )
        return ic_table

    def _load_data(self) -> None:
        features_df, splits, regime_df = self.loader.load(self.config.data_dir)
        if self.config.max_splits is not None:
            splits = list(splits[: self.config.max_splits])
            print(f"Limiting run to first {len(splits)} walk-forward windows for profile control.")
        feature_names = self.loader.get_feature_names(features_df)
        self.state.update(
            {
                "features_df": features_df,
                "splits": splits,
                "regime_df": regime_df,
                "feature_names": feature_names,
                "analyzer": FactorICAnalyzer(),
            }
        )
        print("Track A - Classical Models")
        print(f"Device: {self.config.device}")
        print(f"Output: {self.output_dir}")
        if self.config.data_dir is not None:
            print(f"Requested data dir: {self.config.data_dir}")
        print(f"Run profile: {self.config.run_profile}")
        print(f"Skip days: {sorted(self.config.skip_days)}")
        print(f"Feature mode: {self.config.feature_mode}")
        print(f"Normalize raw financials: {self.config.normalize_raw_financials}")
        if self.config.model_filter:
            print(f"Model filter: {self.config.model_filter}")

    def _save_run_state(self, status: str = "running") -> None:
        payload = {
            "run_state": {
                "track_name": self.track_name,
                "status": status,
                "device": self.config.device,
                "run_profile": self.config.run_profile,
                "skip_days": sorted(self.config.skip_days),
                "force_rerun_days": sorted(self.config.force_rerun_days),
                "model_filter": list(self.config.model_filter),
                "feature_mode": self.config.feature_mode,
                "reduced_feature_count": self.config.reduced_feature_count,
                "normalize_raw_financials": self.config.normalize_raw_financials,
                "day_status": self.day_status,
                "elapsed_minutes": round((time.time() - self.sprint_start) / 60.0, 3),
            }
        }
        self.saver.save_all(self.output_dir, self.track_name, payload)

    def _normalize_frontier_summary(self, summary: dict[str, Any]) -> dict[str, Any]:
        """Adds frontier-style summary keys so Track A outputs compare cleanly in the aggregator."""

        normalized = dict(summary)
        mean_test_ic = normalized.get("mean_test_ic")
        normalized.setdefault("mean_test_ic_all_windows", mean_test_ic)
        normalized.setdefault("mean_test_ic_active_windows", mean_test_ic)
        normalized.setdefault("collapse_rate", 0.0)
        normalized.setdefault("n_inverted_windows", 0)
        normalized.setdefault("collapse_warning", "")
        return normalized

    def _export_model_payload(
        self,
        model_name: str,
        results: dict[str, Any],
        summary: dict[str, Any],
        stability: dict[str, Any],
        baseline_comparison: dict[str, Any] | None = None,
    ) -> Path:
        """Writes a frontier-compatible per-model artifact for downstream aggregation."""

        output_path = self.saver.save_model_result(
            self.output_dir,
            model_name,
            results,
            self._normalize_frontier_summary(summary),
            stability,
            baseline_comparison=baseline_comparison,
        )
        print(f"Saved {model_name} artifact to {output_path}", flush=True)
        return output_path

    def _record_day_status(
        self,
        day: int,
        label: str,
        status: str,
        started_at: float,
        error: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "label": label,
            "status": status,
            "elapsed_minutes": round((time.time() - started_at) / 60.0, 3),
        }
        if error:
            payload["error"] = error
        if extra:
            payload.update(extra)
        self.day_status[f"day{day}"] = payload
        self._save_run_state(status="running")

    def _run_day(self, day: int, label: str, fn) -> None:
        started_at = time.time()
        if day in self.config.skip_days:
            print(f"Skipping day {day} by configuration.")
            self._record_day_status(day, label, "skipped", started_at)
            return

        self.saver.print_progress_banner(day, label, (time.time() - self.sprint_start) / 60.0)
        try:
            fn()
            self._record_day_status(day, label, "completed", started_at)
        except Exception as exc:  # noqa: BLE001
            error_text = f"{type(exc).__name__}: {exc}"
            error_payload = {
                f"day{day}_error": {
                    "label": label,
                    "error": error_text,
                    "traceback": traceback.format_exc(limit=12),
                }
            }
            self.saver.save_all(self.output_dir, self.track_name, error_payload)
            self._record_day_status(day, label, "failed", started_at, error=error_text)
            print(f"WARNING day {day} failed: {error_text}")
            if not self.config.continue_on_error:
                raise

    def _bootstrap_day1_if_needed(self) -> None:
        if 1 not in self.config.skip_days:
            return
        self.state.setdefault("analyzer", FactorICAnalyzer())
        cached_ic = self.saver.load_day(self.output_dir, self.track_name, "day1_ic_table")
        if isinstance(cached_ic, list) and cached_ic:
            self.state["ic_table"] = pd.DataFrame(cached_ic)
            print(f"Loaded cached day-1 IC table with {len(self.state['ic_table'])} rows.", flush=True)
            return
        self.state["ic_table"] = None
        print(
            "Day 1 is skipped; deferring the full IC-table build until it is actually needed later in the run.",
            flush=True,
        )

    def _tree_configs(self) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        xgb_estimators = 300
        lgbm_estimators = 500
        catboost_iterations = 400
        if self.config.run_profile == "smoke":
            xgb_estimators = 16
            lgbm_estimators = 20
            catboost_iterations = 24

        feature_prep = self._feature_prep_config()
        xgb_config = {
            **feature_prep,
            "model_type": "xgboost",
            "n_estimators": xgb_estimators,
            "max_depth": 4,
            "min_child_weight": 20,
            "learning_rate": 0.03,
            "subsample": 0.7,
            "colsample_bytree": 0.6,
            "reg_alpha": 0.1,
            "reg_lambda": 2.0,
            "objective": "rank:pairwise",
            "eval_metric": "ndcg@10",
            "early_stopping_rounds": 30,
            "random_state": 42,
            "n_jobs": -1,
            "device": self.config.device if self.config.device == "cuda" else "cpu",
            "output_dir": str(self.output_dir),
            "resume_from_checkpoint": self.config.resume_from_checkpoint,
            "require_group_ranking": self.config.require_group_ranking,
        }
        lightgbm_config = {
            **feature_prep,
            "model_type": "lightgbm",
            "objective": "lambdarank",
            "metric": "ndcg",
            "n_estimators": lgbm_estimators,
            "num_leaves": 63,
            "max_depth": 6,
            "min_child_samples": 20,
            "learning_rate": 0.02,
            "subsample": 0.7,
            "colsample_bytree": 0.6,
            "reg_alpha": 0.1,
            "reg_lambda": 2.0,
            "verbosity": -1,
            "random_state": 42,
            "n_jobs": -1,
            "early_stopping_rounds": 30,
            "output_dir": str(self.output_dir),
            "resume_from_checkpoint": self.config.resume_from_checkpoint,
            "require_group_ranking": self.config.require_group_ranking,
        }
        catboost_config = {
            **feature_prep,
            "model_type": "catboost",
            "iterations": catboost_iterations,
            "depth": 5,
            "learning_rate": 0.02,
            "l2_leaf_reg": 5.0,
            "min_data_in_leaf": 15,
            "loss_function": "YetiRank",
            "eval_metric": "NDCG",
            "boosting_type": "Ordered",
            "verbose": 0,
            "random_seed": 42,
            "task_type": "GPU" if self.config.device == "cuda" else "CPU",
            "od_wait": 30,
            "output_dir": str(self.output_dir),
            "resume_from_checkpoint": self.config.resume_from_checkpoint,
            "require_group_ranking": self.config.require_group_ranking,
        }
        return xgb_config, lightgbm_config, catboost_config

    def _sequence_configs(self) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
        max_epochs = 30
        patience = 7
        n_seeds = 3
        seed_list = [42, 123, 456]
        if self.config.run_profile == "smoke":
            max_epochs = 2
            patience = 1
            n_seeds = 1
            seed_list = [42]

        feature_prep = self._feature_prep_config()
        common = {
            **feature_prep,
            "output_dir": str(self.output_dir),
            "device": self.config.device,
            "resume_from_checkpoint": self.config.resume_from_checkpoint,
        }
        lstm_config = {
            **common,
            "model_type": "lstm",
            "lookback_weeks": 12,
            "hidden_size": 32,
            "num_layers": 2,
            "dropout": 0.2,
            "batch_size": 128,
            "learning_rate": 0.001,
            "weight_decay": 1e-4,
            "head_weight_decay": 0.01,
            "max_epochs": max_epochs,
            "patience": patience,
            "n_seeds": n_seeds,
            "seeds": seed_list,
        }
        gru_config = {
            **lstm_config,
            "model_type": "gru",
        }
        tcn_config = {
            **common,
            "model_type": "tcn",
            "lookback_weeks": 26,
            "num_channels": [32, 32, 64],
            "kernel_size": 3,
            "dilations": [1, 2, 4, 8],
            "dropout": 0.2,
            "learning_rate": 0.001,
            "weight_decay": 1e-4,
            "batch_size": 128,
            "max_epochs": max_epochs,
            "patience": patience,
            "n_seeds": n_seeds,
            "seeds": seed_list,
        }
        transformer_config = {
            **common,
            "model_type": "transformer",
            "lookback_weeks": 12,
            "d_model": 32,
            "nhead": 4,
            "num_encoder_layers": 2,
            "dim_feedforward": 64,
            "dropout": 0.3,
            "batch_size": 64,
            "learning_rate": 0.0003,
            "weight_decay": 1e-4,
            "max_epochs": max_epochs,
            "patience": patience,
            "n_seeds": n_seeds,
            "seeds": seed_list,
        }
        return lstm_config, gru_config, tcn_config, transformer_config

    def _empty_model_result(self, model_name: str, error_text: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        results = {
            "model_name": model_name,
            "model": model_name,
            "windows_total": len(self.state["splits"]),
            "feature_names": list(self.state["feature_names"]),
            "feature_importances": {},
            "windows": [{"window_id": 0, "error": error_text}],
        }
        summary = self.engine.summarize(results)
        stability = self.engine.feature_stability(results, self.state["feature_names"])
        return results, summary, stability

    def _run_model(self, model_name: str, model_factory, config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        try:
            results = self.engine.run(
                model_name,
                model_factory,
                self.state["features_df"],
                self.state["splits"],
                self.state["regime_df"],
                self.state["feature_names"],
                config,
            )
            summary = self.engine.summarize(results)
            stability = self.engine.feature_stability(results, self.state["feature_names"])
            return results, summary, stability
        except Exception as exc:  # noqa: BLE001
            error_text = f"{type(exc).__name__}: {exc}"
            print(f"WARNING {model_name} failed before completing a run: {error_text}")
            return self._empty_model_result(model_name, error_text)

    def _rank_models(self) -> list[str]:
        all_summaries = self.state.get("all_summaries", {})
        return sorted(
            list(all_summaries.keys()),
            key=lambda model_name: (
                int(all_summaries[model_name].get("windows_completed", 0) > 0),
                _safe_float(all_summaries[model_name].get("ic_ir")),
                _safe_float(all_summaries[model_name].get("mean_test_ic")),
                -_safe_float(all_summaries[model_name].get("mean_train_test_ratio"), default=float("inf")),
                _safe_float(all_summaries[model_name].get("mean_hit_rate")),
            ),
            reverse=True,
        )

    def _run_day1(self) -> None:
        analyzer = self.state["analyzer"]
        feature_names = self.state["feature_names"]
        features_df = self.state["features_df"]

        ic_table = analyzer.compute_ic_table(
            features_df,
            feature_names,
            progress_label="Day 1 IC analysis",
        )
        top20 = analyzer.top_factors(ic_table, n=20)
        print("\nTop 20 factors by absolute mean IC:")
        print(top20[["feature", "mean_ic", "ic_tstat", "hit_rate", "ic_ir"]].to_string(index=False))

        decay_df = analyzer.decay_check(features_df, feature_names, split_date="2023-01-01")
        decay_alerts = decay_df.loc[decay_df["decay_alert"] == True]
        print(f"\nDecay alerts ({len(decay_alerts)} factors):")
        if len(decay_alerts):
            print(decay_alerts[["feature", "ic_first_half", "ic_second_half", "decay_ratio"]].to_string(index=False))
        else:
            print("  None")

        gap9_features = [
            feature
            for feature in feature_names
            if any(token in feature for token in ["piotroski", "bab", "amihud", "max_ret_20d", "earnings_quality"])
        ]
        gap9_ic = ic_table.loc[ic_table["feature"].isin(gap9_features)].sort_values("mean_ic", ascending=False)
        print(f"\nGap 9 factors in IC table ({len(gap9_features)}):")
        if len(gap9_ic):
            print(gap9_ic[["feature", "mean_ic", "ic_tstat", "hit_rate"]].to_string(index=False))
        else:
            print("  None found in current export.")

        self.state["ic_table"] = ic_table
        self.saver.save_all(
            self.output_dir,
            self.track_name,
            {
                "day1_ic_table": ic_table.to_dict(orient="records"),
                "day1_decay": decay_df.to_dict(orient="records"),
                "day1_gap9": gap9_ic.to_dict(orient="records"),
            },
        )
        print("\nDay 1 complete.")

    def _run_day2(self) -> None:
        xgb_config, lightgbm_config, catboost_config = self._tree_configs()

        def xgb_factory(X_train, y_train, X_test, feature_names, config):
            X_train_sel, X_test_sel, selected_indices, _ = self._prepare_model_features(
                X_train,
                X_test,
                feature_names,
                config,
            )
            ctx = config.get("window_context", {})
            train_groups = self._require_group_sizes(
                ctx,
                y_train,
                require=bool(config.get("require_group_ranking", True)),
            )
            X_fit, X_val, y_fit, y_val, fit_groups, val_groups = self._split_ranking_train_val(
                X_train_sel,
                y_train,
                train_groups,
            )
            y_fit_rank = self._to_group_relevance_labels(y_fit, fit_groups)
            y_val_rank = self._to_group_relevance_labels(y_val, val_groups) if len(y_val) else y_val
            model = xgb.XGBRanker(
                n_estimators=config["n_estimators"],
                max_depth=config["max_depth"],
                min_child_weight=config["min_child_weight"],
                learning_rate=config["learning_rate"],
                subsample=config["subsample"],
                colsample_bytree=config["colsample_bytree"],
                reg_alpha=config["reg_alpha"],
                reg_lambda=config["reg_lambda"],
                objective=config["objective"],
                eval_metric=config["eval_metric"],
                early_stopping_rounds=config["early_stopping_rounds"],
                random_state=config["random_state"],
                n_jobs=config["n_jobs"],
                device=config.get("device", "cpu"),
                verbosity=0,
            )
            fit_kwargs: dict[str, Any] = {"group": fit_groups, "verbose": False}
            if len(y_val):
                fit_kwargs["eval_set"] = [(X_val, y_val_rank)]
                fit_kwargs["eval_group"] = [val_groups]
            model.fit(X_fit, y_fit_rank, **fit_kwargs)
            train_preds = model.predict(X_train_sel)
            test_preds = model.predict(X_test_sel)
            importance = expand_feature_importance(
                model.feature_importances_,
                selected_indices,
                len(feature_names),
            )
            return train_preds, test_preds, importance

        def lightgbm_factory(X_train, y_train, X_test, feature_names, config):
            X_train_sel, X_test_sel, selected_indices, _ = self._prepare_model_features(
                X_train,
                X_test,
                feature_names,
                config,
            )
            ctx = config.get("window_context", {})
            train_groups = self._require_group_sizes(
                ctx,
                y_train,
                require=bool(config.get("require_group_ranking", True)),
            )
            X_fit, X_val, y_fit, y_val, fit_groups, val_groups = self._split_ranking_train_val(
                X_train_sel,
                y_train,
                train_groups,
            )
            y_fit_rank = self._to_group_relevance_labels(y_fit, fit_groups)
            y_val_rank = self._to_group_relevance_labels(y_val, val_groups) if len(y_val) else y_val
            model = LGBMRanker(
                objective=config["objective"],
                metric=config["metric"],
                n_estimators=config["n_estimators"],
                num_leaves=config["num_leaves"],
                max_depth=config["max_depth"],
                min_child_samples=config["min_child_samples"],
                learning_rate=config["learning_rate"],
                subsample=config["subsample"],
                colsample_bytree=config["colsample_bytree"],
                reg_alpha=config["reg_alpha"],
                reg_lambda=config["reg_lambda"],
                random_state=config["random_state"],
                n_jobs=config["n_jobs"],
                verbosity=config["verbosity"],
            )
            fit_kwargs: dict[str, Any] = {"group": fit_groups}
            if len(y_val):
                fit_kwargs["eval_set"] = [(X_val, y_val_rank)]
                fit_kwargs["eval_group"] = [val_groups]
                if lightgbm is not None and hasattr(lightgbm, "early_stopping"):
                    fit_kwargs["callbacks"] = [
                        lightgbm.early_stopping(config["early_stopping_rounds"], verbose=False),
                    ]
            model.fit(X_fit, y_fit_rank, **fit_kwargs)
            train_preds = model.predict(X_train_sel)
            test_preds = model.predict(X_test_sel)
            booster = getattr(model, "booster_", None)
            if booster is not None:
                raw_importance = booster.feature_importance(importance_type="gain")
            else:
                raw_importance = getattr(model, "feature_importances_", np.zeros(len(selected_indices), dtype=float))
            importance = expand_feature_importance(raw_importance, selected_indices, len(feature_names))
            return train_preds, test_preds, importance

        def catboost_factory(X_train, y_train, X_test, feature_names, config):
            X_train_sel, X_test_sel, selected_indices, _ = self._prepare_model_features(
                X_train,
                X_test,
                feature_names,
                config,
            )
            ctx = config.get("window_context", {})
            train_groups = self._require_group_sizes(
                ctx,
                y_train,
                require=bool(config.get("require_group_ranking", True)),
            )
            X_fit, X_val, y_fit, y_val, fit_groups, val_groups = self._split_ranking_train_val(
                X_train_sel,
                y_train,
                train_groups,
            )
            y_fit_rank = self._to_group_relevance_labels(y_fit, fit_groups)
            y_val_rank = self._to_group_relevance_labels(y_val, val_groups) if len(y_val) else y_val
            fit_group_id = np.repeat(np.arange(len(fit_groups)), fit_groups)
            model = CatBoostRanker(
                iterations=config["iterations"],
                depth=config["depth"],
                learning_rate=config["learning_rate"],
                l2_leaf_reg=config["l2_leaf_reg"],
                min_data_in_leaf=config["min_data_in_leaf"],
                loss_function=config["loss_function"],
                eval_metric=config["eval_metric"],
                boosting_type=config["boosting_type"],
                verbose=config["verbose"],
                random_seed=config["random_seed"],
                task_type=config["task_type"],
                od_type="Iter",
                od_wait=config["od_wait"],
            )
            train_pool = Pool(X_fit, y_fit_rank, group_id=fit_group_id)
            fit_kwargs: dict[str, Any] = {}
            if len(y_val):
                eval_group_id = np.repeat(np.arange(len(val_groups)), val_groups)
                fit_kwargs["eval_set"] = Pool(X_val, y_val_rank, group_id=eval_group_id)
                fit_kwargs["use_best_model"] = True
            model.fit(train_pool, **fit_kwargs)

            full_group_id = np.repeat(np.arange(len(train_groups)), train_groups)
            full_train_pool = Pool(X_train_sel, y_train, group_id=full_group_id)
            train_preds = model.predict(X_train_sel)
            test_preds = model.predict(X_test_sel)
            try:
                raw_importance = model.get_feature_importance(full_train_pool, type="LossFunctionChange")
            except Exception:
                raw_importance = model.get_feature_importance(type="PredictionValuesChange")
            importance = expand_feature_importance(raw_importance, selected_indices, len(feature_names))
            return train_preds, test_preds, importance

        def run_or_skip(model_name: str, factory, config: dict[str, Any], unavailable_reason: str | None = None):
            if not self._is_model_enabled(model_name):
                return self._empty_model_result(model_name, "filtered by TRACK_A_MODEL_FILTER")
            if unavailable_reason is not None:
                return self._empty_model_result(model_name, unavailable_reason)
            return self._run_model(model_name, factory, config)

        xgb_results, xgb_summary, xgb_stability = run_or_skip(
            "XGBoost",
            xgb_factory,
            xgb_config,
            unavailable_reason="xgboost import unavailable" if xgb is None else None,
        )
        lightgbm_results, lightgbm_summary, lightgbm_stability = run_or_skip(
            "LightGBM",
            lightgbm_factory,
            lightgbm_config,
            unavailable_reason="lightgbm import unavailable" if LGBMRanker is None else None,
        )
        catboost_results, catboost_summary, catboost_stability = run_or_skip(
            "CatBoost",
            catboost_factory,
            catboost_config,
            unavailable_reason="catboost import unavailable" if (catboost is None or CatBoostRanker is None or Pool is None) else None,
        )

        xgb_baseline = self.engine.compare_to_catboost_baseline(xgb_summary)
        lightgbm_baseline = self.engine.compare_to_catboost_baseline(lightgbm_summary)
        catboost_baseline = self.engine.compare_to_catboost_baseline(catboost_summary)

        for model_name, summary in [
            ("XGBoost", xgb_summary),
            ("LightGBM", lightgbm_summary),
            ("CatBoost", catboost_summary),
        ]:
            print(f"\n=== {model_name} Results ===")
            print(f"Mean test IC:   {summary['mean_test_ic']:.4f}")
            print(f"IC IR:          {summary['ic_ir']:.4f}")
            print(f"Train/test:     {summary['mean_train_test_ratio']:.2f}x")
            print(f"Hit rate:       {summary['mean_hit_rate']:.4f}")
            print(f"Verdict:        {summary['verdict']}")

        self.state.update(
            {
                "xgb_results": xgb_results,
                "xgb_summary": xgb_summary,
                "xgb_stability": xgb_stability,
                "xgb_baseline": xgb_baseline,
                "lightgbm_results": lightgbm_results,
                "lightgbm_summary": lightgbm_summary,
                "lightgbm_stability": lightgbm_stability,
                "lightgbm_baseline": lightgbm_baseline,
                "catboost_results": catboost_results,
                "catboost_summary": catboost_summary,
                "catboost_stability": catboost_stability,
            }
        )
        self._export_model_payload(
            "xgboost",
            xgb_results,
            xgb_summary,
            xgb_stability,
            baseline_comparison=xgb_baseline,
        )
        self._export_model_payload(
            "lightgbm",
            lightgbm_results,
            lightgbm_summary,
            lightgbm_stability,
            baseline_comparison=lightgbm_baseline,
        )
        self._export_model_payload(
            "catboost",
            catboost_results,
            catboost_summary,
            catboost_stability,
            baseline_comparison=catboost_baseline,
        )
        self.saver.save_all(
            self.output_dir,
            self.track_name,
            {
                "day2_xgb": {
                    "summary": xgb_summary,
                    "stability": xgb_stability,
                    "baseline": xgb_baseline,
                },
                "day2_lightgbm": {
                    "summary": lightgbm_summary,
                    "stability": lightgbm_stability,
                    "baseline": lightgbm_baseline,
                },
                "day2_catboost": {
                    "summary": catboost_summary,
                    "stability": catboost_stability,
                    "baseline": catboost_baseline,
                },
            },
        )
        print("\nDay 2 tree models complete.")

    def _run_day3(self) -> None:
        if torch is None or nn is None:
            raise RuntimeError("PyTorch is unavailable, so sequence-model experiments cannot run.")

        def set_seed(seed):
            random.seed(seed)
            np.random.seed(seed)
            torch.manual_seed(seed)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed)

        def make_ranking_loss(margin=0.005):
            def ranking_loss(scores, targets):
                n = len(scores)
                if n < 2:
                    return nn.functional.mse_loss(scores, targets)
                s_i = scores.unsqueeze(1).expand(n, n)
                s_j = scores.unsqueeze(0).expand(n, n)
                t_i = targets.unsqueeze(1).expand(n, n)
                t_j = targets.unsqueeze(0).expand(n, n)
                should_be_higher = (t_i > t_j).float()
                pair_loss = torch.relu(margin - (s_i - s_j)) * should_be_higher
                n_pairs = should_be_higher.sum().clamp(min=1)
                return pair_loss.sum() / n_pairs

            return ranking_loss

        def reshape_feature_sequence(X, lookback_weeks):
            n_samples, n_features = X.shape
            step_dim = int(np.ceil(n_features / lookback_weeks))
            padded_dim = lookback_weeks * step_dim
            pad_width = padded_dim - n_features
            if pad_width > 0:
                X = np.pad(X, ((0, 0), (0, pad_width)), mode="constant")
            return X.reshape(n_samples, lookback_weeks, step_dim).astype(np.float32), n_features

        def extract_importance(model, x_tensor, n_features):
            model.train()
            x_grad = x_tensor.clone().requires_grad_(True)
            out = model(x_grad)
            out.sum().backward()
            flat = x_grad.grad.abs().mean(dim=0).reshape(-1)
            return flat[:n_features].detach().cpu().numpy()

        class LSTMRanker(nn.Module):
            def __init__(self, input_size, hidden_size=64, num_layers=2, dropout=0.3):
                super().__init__()
                self.lstm = nn.LSTM(
                    input_size=input_size,
                    hidden_size=hidden_size,
                    num_layers=num_layers,
                    dropout=dropout if num_layers > 1 else 0.0,
                    batch_first=True,
                )
                self.head = nn.Sequential(
                    nn.LayerNorm(hidden_size),
                    nn.Dropout(dropout),
                    nn.Linear(hidden_size, hidden_size // 2),
                    nn.GELU(),
                    nn.Linear(hidden_size // 2, 1),
                )

            def forward(self, x):
                _, (h_n, _) = self.lstm(x)
                return self.head(h_n[-1]).squeeze(-1)

        class GRURanker(nn.Module):
            def __init__(self, input_size, hidden_size=32, num_layers=2, dropout=0.2):
                super().__init__()
                self.gru = nn.GRU(
                    input_size=input_size,
                    hidden_size=hidden_size,
                    num_layers=num_layers,
                    dropout=dropout if num_layers > 1 else 0.0,
                    batch_first=True,
                )
                self.head = nn.Sequential(
                    nn.LayerNorm(hidden_size),
                    nn.Dropout(dropout),
                    nn.Linear(hidden_size, hidden_size // 2),
                    nn.GELU(),
                    nn.Linear(hidden_size // 2, 1),
                )

            def forward(self, x):
                _, h_n = self.gru(x)
                return self.head(h_n[-1]).squeeze(-1)

        class Chomp1d(nn.Module):
            def __init__(self, chomp_size):
                super().__init__()
                self.chomp_size = chomp_size

            def forward(self, x):
                return x[:, :, :-self.chomp_size] if self.chomp_size > 0 else x

        class TemporalBlock(nn.Module):
            def __init__(self, in_channels, out_channels, kernel_size, dilation, dropout):
                super().__init__()
                padding = (kernel_size - 1) * dilation
                self.net = nn.Sequential(
                    nn.Conv1d(in_channels, out_channels, kernel_size, padding=padding, dilation=dilation),
                    Chomp1d(padding),
                    nn.GELU(),
                    nn.Dropout(dropout),
                    nn.Conv1d(out_channels, out_channels, kernel_size, padding=padding, dilation=dilation),
                    Chomp1d(padding),
                    nn.GELU(),
                    nn.Dropout(dropout),
                )
                self.downsample = (
                    nn.Conv1d(in_channels, out_channels, 1)
                    if in_channels != out_channels
                    else nn.Identity()
                )

            def forward(self, x):
                return self.net(x) + self.downsample(x)

        class TCNRanker(nn.Module):
            def __init__(self, input_size, num_channels, kernel_size=3, dilations=(1, 2, 4, 8), dropout=0.2):
                super().__init__()
                channels = [input_size] + list(num_channels) + [num_channels[-1]]
                blocks = []
                for idx, dilation in enumerate(dilations):
                    blocks.append(TemporalBlock(channels[idx], channels[idx + 1], kernel_size, dilation, dropout))
                self.network = nn.Sequential(*blocks)
                self.head = nn.Sequential(
                    nn.LayerNorm(channels[-1]),
                    nn.Dropout(dropout),
                    nn.Linear(channels[-1], 1),
                )

            def forward(self, x):
                y = self.network(x.transpose(1, 2))
                pooled = y.mean(dim=-1)
                return self.head(pooled).squeeze(-1)

        class PositionalEncoding(nn.Module):
            def __init__(self, d_model, max_len=64):
                super().__init__()
                pe = torch.zeros(max_len, d_model)
                position = torch.arange(0, max_len, dtype=torch.float32).unsqueeze(1)
                div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-np.log(10000.0) / d_model))
                pe[:, 0::2] = torch.sin(position * div_term)
                pe[:, 1::2] = torch.cos(position * div_term)
                self.register_buffer("pe", pe.unsqueeze(0), persistent=False)

            def forward(self, x):
                return x + self.pe[:, : x.size(1)]

        class TransformerRanker(nn.Module):
            def __init__(self, input_size, d_model=32, nhead=4, num_encoder_layers=2, dim_feedforward=64, dropout=0.3):
                super().__init__()
                self.input_proj = nn.Linear(input_size, d_model)
                self.pos = PositionalEncoding(d_model)
                encoder_layer = nn.TransformerEncoderLayer(
                    d_model=d_model,
                    nhead=nhead,
                    dim_feedforward=dim_feedforward,
                    dropout=dropout,
                    activation="gelu",
                    batch_first=True,
                    norm_first=True,
                )
                self.encoder = nn.TransformerEncoder(
                    encoder_layer,
                    num_layers=num_encoder_layers,
                    enable_nested_tensor=False,
                )
                self.head = nn.Sequential(
                    nn.LayerNorm(d_model),
                    nn.Dropout(dropout),
                    nn.Linear(d_model, 1),
                )

            def forward(self, x):
                h = self.input_proj(x)
                h = self.pos(h)
                h = self.encoder(h)
                pooled = h.mean(dim=1)
                return self.head(pooled).squeeze(-1)

        def train_sequence_model(model_cls, X_train, y_train, config, model_kwargs):
            device = config["device"]
            X_seq, n_features = reshape_feature_sequence(X_train, config["lookback_weeks"])
            split_idx = max(int(len(X_seq) * 0.9), 1)
            X_fit = torch.tensor(X_seq[:split_idx], dtype=torch.float32, device=device)
            y_fit = torch.tensor(y_train[:split_idx], dtype=torch.float32, device=device)
            X_val = (
                torch.tensor(X_seq[split_idx:], dtype=torch.float32, device=device)
                if split_idx < len(X_seq)
                else X_fit[:0]
            )
            y_val = (
                torch.tensor(y_train[split_idx:], dtype=torch.float32, device=device)
                if split_idx < len(X_seq)
                else y_fit[:0]
            )
            model = model_cls(input_size=X_seq.shape[2], **model_kwargs).to(device)
            head_params = list(model.head.parameters()) if hasattr(model, "head") else []
            head_param_ids = {id(param) for param in head_params}
            base_params = [param for param in model.parameters() if id(param) not in head_param_ids]
            optim_groups = []
            if base_params:
                optim_groups.append(
                    {
                        "params": base_params,
                        "weight_decay": config["weight_decay"],
                    }
                )
            if head_params:
                optim_groups.append(
                    {
                        "params": head_params,
                        "weight_decay": config.get("head_weight_decay", config["weight_decay"]),
                    }
                )
            optimizer = torch.optim.AdamW(optim_groups or model.parameters(), lr=config["learning_rate"])
            loss_fn = make_ranking_loss()
            best_loss = float("inf")
            best_state = None
            patience_counter = 0
            batch_size = min(config["batch_size"], len(X_fit))
            for _ in range(config["max_epochs"]):
                perm = torch.randperm(len(X_fit), device=device)
                model.train()
                for start in range(0, len(X_fit), batch_size):
                    idx = perm[start : start + batch_size]
                    xb = X_fit[idx]
                    yb = y_fit[idx]
                    optimizer.zero_grad(set_to_none=True)
                    preds = model(xb)
                    loss = loss_fn(preds, yb)
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    optimizer.step()
                model.eval()
                with torch.no_grad():
                    eval_x = X_val if len(X_val) else X_fit
                    eval_y = y_val if len(y_val) else y_fit
                    eval_loss = float(loss_fn(model(eval_x), eval_y).item())
                if eval_loss < best_loss - 1e-4:
                    best_loss = eval_loss
                    best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
                    patience_counter = 0
                else:
                    patience_counter += 1
                    if patience_counter >= config["patience"]:
                        break
            if best_state is not None:
                model.load_state_dict(best_state)
            return model, X_seq, n_features

        def seeded_sequence_factory(model_cls, X_train, y_train, X_test, feature_names, config, model_kwargs):
            X_train_sel, X_test_sel, selected_indices, _ = self._prepare_model_features(
                X_train,
                X_test,
                feature_names,
                config,
            )
            all_train = []
            all_test = []
            all_importance = []
            X_test_seq, n_features = reshape_feature_sequence(X_test_sel, config["lookback_weeks"])
            X_test_tensor = torch.tensor(X_test_seq, dtype=torch.float32, device=config["device"])
            seeds = config.get("seeds", [42])[: config.get("n_seeds", 1)]
            for seed in seeds:
                set_seed(seed)
                model, X_train_seq, _ = train_sequence_model(model_cls, X_train_sel, y_train, config, model_kwargs)
                model.eval()
                X_train_tensor = torch.tensor(X_train_seq, dtype=torch.float32, device=config["device"])
                with torch.no_grad():
                    train_preds = model(X_train_tensor).cpu().numpy()
                    test_preds = model(X_test_tensor).cpu().numpy()
                raw_importance = extract_importance(model, X_test_tensor[: min(len(X_test_tensor), 1024)], n_features)
                importance = expand_feature_importance(raw_importance, selected_indices, len(feature_names))
                all_train.append(train_preds)
                all_test.append(test_preds)
                all_importance.append(importance)
                del model, X_train_tensor
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                gc.collect()
            return (
                np.mean(np.vstack(all_train), axis=0),
                np.mean(np.vstack(all_test), axis=0),
                np.mean(np.vstack(all_importance), axis=0),
            )

        lstm_config, gru_config, tcn_config, transformer_config = self._sequence_configs()

        def lstm_factory(X_train, y_train, X_test, feature_names, config):
            return seeded_sequence_factory(
                LSTMRanker,
                X_train,
                y_train,
                X_test,
                feature_names,
                config,
                {
                    "hidden_size": config["hidden_size"],
                    "num_layers": config["num_layers"],
                    "dropout": config["dropout"],
                },
            )

        def gru_factory(X_train, y_train, X_test, feature_names, config):
            return seeded_sequence_factory(
                GRURanker,
                X_train,
                y_train,
                X_test,
                feature_names,
                config,
                {
                    "hidden_size": config["hidden_size"],
                    "num_layers": config["num_layers"],
                    "dropout": config["dropout"],
                },
            )

        def tcn_factory(X_train, y_train, X_test, feature_names, config):
            return seeded_sequence_factory(
                TCNRanker,
                X_train,
                y_train,
                X_test,
                feature_names,
                config,
                {
                    "num_channels": config["num_channels"],
                    "kernel_size": config["kernel_size"],
                    "dilations": config["dilations"],
                    "dropout": config["dropout"],
                },
            )

        def transformer_factory(X_train, y_train, X_test, feature_names, config):
            return seeded_sequence_factory(
                TransformerRanker,
                X_train,
                y_train,
                X_test,
                feature_names,
                config,
                {
                    "d_model": config["d_model"],
                    "nhead": config["nhead"],
                    "num_encoder_layers": config["num_encoder_layers"],
                    "dim_feedforward": config["dim_feedforward"],
                    "dropout": config["dropout"],
                },
            )

        def run_or_skip(model_name: str, factory, config: dict[str, Any]):
            if not self._is_model_enabled(model_name):
                return self._empty_model_result(model_name, "filtered by TRACK_A_MODEL_FILTER")
            return self._run_model(model_name, factory, config)

        lstm_results, lstm_summary, lstm_stability = run_or_skip("LSTM", lstm_factory, lstm_config)
        gru_results, gru_summary, gru_stability = run_or_skip("GRU", gru_factory, gru_config)
        tcn_results, tcn_summary, tcn_stability = run_or_skip("TCN", tcn_factory, tcn_config)
        transformer_results, transformer_summary, transformer_stability = run_or_skip(
            "Transformer",
            transformer_factory,
            transformer_config,
        )

        lstm_autocorrs = []
        valid_lstm_windows = [window for window in lstm_results["windows"] if "error" not in window]
        for left, right in zip(valid_lstm_windows[:-1], valid_lstm_windows[1:]):
            left_preds = np.asarray(left["test_preds"], dtype=float)
            right_preds = np.asarray(right["test_preds"], dtype=float)
            size = min(len(left_preds), len(right_preds))
            if size < 20:
                continue
            corr = np.corrcoef(left_preds[:size], right_preds[:size])[0, 1]
            if np.isfinite(corr):
                lstm_autocorrs.append({"pair": f"{left['window_id']}->{right['window_id']}", "corr": float(corr)})

        print("\nLSTM prediction autocorrelation diagnostics:")
        if lstm_autocorrs:
            for item in lstm_autocorrs[:10]:
                flag = " FLAG" if item["corr"] > 0.95 else ""
                print(f"  {item['pair']}: {item['corr']:.4f}{flag}")
        else:
            print("  No valid consecutive-window pairs for autocorrelation check.")

        comparison_rows = [
            {
                "Model": "XGBoost",
                "Mean IC": self.state["xgb_summary"]["mean_test_ic"],
                "IC IR": self.state["xgb_summary"]["ic_ir"],
                "Ratio": self.state["xgb_summary"]["mean_train_test_ratio"],
                "Hit Rate": self.state["xgb_summary"]["mean_hit_rate"],
                "Stability": self.state["xgb_stability"]["mean_pairwise_correlation"],
                "Verdict": self.state["xgb_summary"]["verdict"],
            },
            {
                "Model": "LightGBM",
                "Mean IC": self.state["lightgbm_summary"]["mean_test_ic"],
                "IC IR": self.state["lightgbm_summary"]["ic_ir"],
                "Ratio": self.state["lightgbm_summary"]["mean_train_test_ratio"],
                "Hit Rate": self.state["lightgbm_summary"]["mean_hit_rate"],
                "Stability": self.state["lightgbm_stability"]["mean_pairwise_correlation"],
                "Verdict": self.state["lightgbm_summary"]["verdict"],
            },
            {
                "Model": "CatBoost",
                "Mean IC": self.state["catboost_summary"]["mean_test_ic"],
                "IC IR": self.state["catboost_summary"]["ic_ir"],
                "Ratio": self.state["catboost_summary"]["mean_train_test_ratio"],
                "Hit Rate": self.state["catboost_summary"]["mean_hit_rate"],
                "Stability": self.state["catboost_stability"]["mean_pairwise_correlation"],
                "Verdict": self.state["catboost_summary"]["verdict"],
            },
            {
                "Model": "LSTM",
                "Mean IC": lstm_summary["mean_test_ic"],
                "IC IR": lstm_summary["ic_ir"],
                "Ratio": lstm_summary["mean_train_test_ratio"],
                "Hit Rate": lstm_summary["mean_hit_rate"],
                "Stability": lstm_stability["mean_pairwise_correlation"],
                "Verdict": lstm_summary["verdict"],
            },
            {
                "Model": "GRU",
                "Mean IC": gru_summary["mean_test_ic"],
                "IC IR": gru_summary["ic_ir"],
                "Ratio": gru_summary["mean_train_test_ratio"],
                "Hit Rate": gru_summary["mean_hit_rate"],
                "Stability": gru_stability["mean_pairwise_correlation"],
                "Verdict": gru_summary["verdict"],
            },
            {
                "Model": "TCN",
                "Mean IC": tcn_summary["mean_test_ic"],
                "IC IR": tcn_summary["ic_ir"],
                "Ratio": tcn_summary["mean_train_test_ratio"],
                "Hit Rate": tcn_summary["mean_hit_rate"],
                "Stability": tcn_stability["mean_pairwise_correlation"],
                "Verdict": tcn_summary["verdict"],
            },
            {
                "Model": "Transformer",
                "Mean IC": transformer_summary["mean_test_ic"],
                "IC IR": transformer_summary["ic_ir"],
                "Ratio": transformer_summary["mean_train_test_ratio"],
                "Hit Rate": transformer_summary["mean_hit_rate"],
                "Stability": transformer_stability["mean_pairwise_correlation"],
                "Verdict": transformer_summary["verdict"],
            },
        ]
        comparison_df = pd.DataFrame(comparison_rows)
        print("\nModel comparison:")
        print(comparison_df.to_string(index=False))

        self.state.update(
            {
                "lstm_results": lstm_results,
                "lstm_summary": lstm_summary,
                "lstm_stability": lstm_stability,
                "gru_results": gru_results,
                "gru_summary": gru_summary,
                "gru_stability": gru_stability,
                "tcn_results": tcn_results,
                "tcn_summary": tcn_summary,
                "tcn_stability": tcn_stability,
                "transformer_results": transformer_results,
                "transformer_summary": transformer_summary,
                "transformer_stability": transformer_stability,
                "all_model_results": {
                    "XGBoost": self.state["xgb_results"],
                    "LightGBM": self.state["lightgbm_results"],
                    "CatBoost": self.state["catboost_results"],
                    "LSTM": lstm_results,
                    "GRU": gru_results,
                    "TCN": tcn_results,
                    "Transformer": transformer_results,
                },
                "all_summaries": {
                    "XGBoost": self.state["xgb_summary"],
                    "LightGBM": self.state["lightgbm_summary"],
                    "CatBoost": self.state["catboost_summary"],
                    "LSTM": lstm_summary,
                    "GRU": gru_summary,
                    "TCN": tcn_summary,
                    "Transformer": transformer_summary,
                },
                "all_stabilities": {
                    "XGBoost": self.state["xgb_stability"],
                    "LightGBM": self.state["lightgbm_stability"],
                    "CatBoost": self.state["catboost_stability"],
                    "LSTM": lstm_stability,
                    "GRU": gru_stability,
                    "TCN": tcn_stability,
                    "Transformer": transformer_stability,
                },
            }
        )
        self._export_model_payload("lstm", lstm_results, lstm_summary, lstm_stability)
        self._export_model_payload("gru", gru_results, gru_summary, gru_stability)
        self._export_model_payload("tcn", tcn_results, tcn_summary, tcn_stability)
        self._export_model_payload(
            "transformer",
            transformer_results,
            transformer_summary,
            transformer_stability,
        )
        self.saver.save_all(
            self.output_dir,
            self.track_name,
            {
                "day3_classical_models": {
                    "comparison": comparison_df.to_dict(orient="records"),
                    "lstm_autocorrs": lstm_autocorrs,
                }
            },
        )
        print("\nDay 3 sequence models complete.")

    def _run_day4(self) -> None:
        if "all_summaries" not in self.state:
            raise RuntimeError("Day 4 requires model summaries from days 2-3.")

        regime_analyzer = RegimeConditionalIC()
        sector_analyzer = SectorICAnalyzer()
        ranked_models = self._rank_models()
        top2 = ranked_models[:2]
        self.state["ranked_models"] = ranked_models
        self.state["top2"] = top2
        print(f"Top 2 models for regime/sector analysis: {top2}")

        selected = {model_name: self.state["all_model_results"][model_name] for model_name in top2}
        regime_table = regime_analyzer.model_regime_breakdown(selected)
        print("\nRegime-conditional IC:")
        print(regime_table.round(4).to_string() if not regime_table.empty else "No regime table available.")

        for model_name in top2:
            print(f"\nSector IC - {model_name}:")
            sector_df = sector_analyzer.compute(self.state["features_df"], self.state["feature_names"])
            if sector_df.empty:
                print("  Sector column not available in this export, skipping.")
            else:
                print(sector_df.head(10).to_string(index=False))

        regime_ic = regime_analyzer.compute(
            self.state["features_df"],
            self.state["feature_names"],
            self.state["regime_df"],
        )
        for regime_name, ic_series in regime_ic.items():
            top5 = ic_series.abs().nlargest(5)
            print(f"\nTop 5 features in {regime_name}: {top5.index.tolist()}")

        self.saver.save_all(
            self.output_dir,
            self.track_name,
            {
                "day4_regime_sector": {
                    "top2_models": top2,
                    "regime_table": regime_table.reset_index().to_dict(orient="records") if not regime_table.empty else [],
                    "regime_top_features": {
                        name: list(series.abs().nlargest(5).index)
                        for name, series in regime_ic.items()
                    },
                }
            },
        )

    def _run_day5(self) -> None:
        analyzer = self.state["analyzer"]
        feature_names = self.state["feature_names"]
        features_df = self.state["features_df"]

        pledge_cols = [column for column in feature_names if "pledge" in column.lower()]
        bulk_cols = [column for column in feature_names if "bulk" in column.lower()]
        print(f"Pledge features: {pledge_cols}")
        print(f"Bulk features: {bulk_cols}")
        india_results: dict[str, Any] = {}

        if pledge_cols and bulk_cols:
            test_df = features_df.copy()
            pledge_col = pledge_cols[0]
            bulk_col = bulk_cols[0]
            test_df["pledge_bulk_interaction"] = (-test_df[pledge_col]) * test_df[bulk_col]
            interaction_ic = analyzer.compute_ic_table(test_df, [pledge_col, bulk_col, "pledge_bulk_interaction"])
            india_results["pledge_bulk_interaction"] = interaction_ic.to_dict(orient="records")
            print("\nPledge x Bulk interaction vs components:")
            print(interaction_ic[["feature", "mean_ic", "ic_tstat"]].to_string(index=False))
        else:
            print("Pledge or bulk features not available - skipping 5A")

        eq_cols = [column for column in feature_names if "earnings_quality" in column.lower()]
        print(f"\nEarnings quality features: {eq_cols}")
        if eq_cols:
            eq_ic = analyzer.compute_ic_table(features_df, eq_cols)
            test_df2 = features_df.copy()
            negated_cols = []
            for column in eq_cols:
                neg_name = f"{column}_negated"
                test_df2[neg_name] = -test_df2[column]
                negated_cols.append(neg_name)
            eq_both = analyzer.compute_ic_table(test_df2, eq_cols + negated_cols)
            india_results["earnings_quality"] = eq_both.to_dict(orient="records")
            print("\nEarnings quality - both signs:")
            print(eq_both[["feature", "mean_ic", "ic_tstat"]].to_string(index=False))
            winning_sign = "POSITIVE" if eq_ic["mean_ic"].iloc[0] > 0 else "NEGATIVE"
            print(f"\nIndia earnings quality sign: {winning_sign}")

        fii_cols = [column for column in feature_names if "fii" in column.lower()]
        print(f"\nFII features: {fii_cols}")
        if len(fii_cols) >= 2:
            test_df3 = features_df.copy()
            test_df3["fii_interaction"] = test_df3[fii_cols[0]] * test_df3[fii_cols[1]]
            fii_ic = analyzer.compute_ic_table(test_df3, fii_cols[:2] + ["fii_interaction"])
            india_results["fii_interaction"] = fii_ic.to_dict(orient="records")
            print("\nFII interaction vs components:")
            print(fii_ic[["feature", "mean_ic", "ic_tstat"]].to_string(index=False))

        sue_cols = [
            column
            for column in feature_names
            if "sue" in column.lower() or "eps" in column.lower() or "surprise" in column.lower()
        ]
        print(f"\nEarnings surprise features: {sue_cols}")
        if sue_cols:
            sue_ic = analyzer.compute_ic_table(features_df, sue_cols)
            india_results["earnings_revision_proxy"] = sue_ic.to_dict(orient="records")
            print(sue_ic[["feature", "mean_ic", "ic_tstat"]].to_string(index=False))

        power_cols = [column for column in feature_names if "power" in column.lower()]
        print(f"\nPower features: {power_cols}")
        if power_cols:
            power_ic = analyzer.compute_ic_table(features_df, power_cols)
            india_results["power_lag_proxy"] = power_ic.to_dict(orient="records")
            print(power_ic[["feature", "mean_ic", "ic_tstat"]].to_string(index=False))

        self.saver.save_all(self.output_dir, self.track_name, {"day5_india_specific": india_results})
        print("\nDay 5 complete.")

    def _run_day6(self) -> None:
        if "ranked_models" not in self.state:
            self.state["ranked_models"] = self._rank_models()
        top2 = self.state.get("top2") or self.state["ranked_models"][:2]
        ensemble_builder = EnsembleBuilder()
        ensemble_results_list = []

        if len(top2) >= 2:
            for split in self.state["splits"]:
                X_train, y_train, X_test, y_test = self.loader.get_window_arrays(
                    self.state["features_df"],
                    split,
                    self.state["feature_names"],
                )
                model_preds = {}
                ic_history = {}
                for model_name in top2:
                    model_windows = self.state["all_model_results"][model_name]["windows"]
                    valid_prior = [
                        window
                        for window in model_windows
                        if "error" not in window and window["window_id"] < split["window_id"]
                    ]
                    ic_history[model_name] = [window["test_ic"] for window in valid_prior[-10:]]
                    this_window = next(
                        (window for window in model_windows if window.get("window_id") == split["window_id"]),
                        None,
                    )
                    if this_window and "test_preds" in this_window:
                        preds = np.asarray(this_window["test_preds"], dtype=float)
                        if len(preds) == len(y_test):
                            model_preds[model_name] = preds
                if len(model_preds) >= 2:
                    ensemble_pred = ensemble_builder.build(model_preds, ic_history)
                    gain = ensemble_builder.evaluate_gain(ensemble_pred, model_preds, y_test)
                    gain["window_id"] = split["window_id"]
                    ensemble_results_list.append(gain)
        else:
            print("Not enough valid models for ensemble analysis; continuing with deployment-only simulation.")

        mean_gain = None
        passes_parity = None
        if ensemble_results_list:
            mean_ensemble_ic = float(np.mean([row["ensemble_ic"] for row in ensemble_results_list]))
            mean_best_ic = float(np.mean([row["best_individual_ic"] for row in ensemble_results_list]))
            mean_gain = float(np.mean([row["ic_gain"] for row in ensemble_results_list]))
            passes_parity = bool(mean_gain > -0.003)
            print(f"\nEnsemble IC:        {mean_ensemble_ic:.4f}")
            print(f"Best individual IC: {mean_best_ic:.4f}")
            print(f"IC gain:            {mean_gain:+.4f}")
            print(f"Passes parity:      {passes_parity}")

        print("\n--- Deployment Sizing Simulation ---")
        ranked_models = self.state.get("ranked_models") or self._rank_models()
        best_model = ranked_models[0] if ranked_models else None
        deployment_simulation = []
        if best_model is not None:
            for window in self.state["all_model_results"][best_model]["windows"]:
                if "error" in window:
                    continue
                test_ic = window.get("test_ic", 0)
                if test_ic > 0.015:
                    simulated_exposure = 0.40
                elif test_ic > 0.005:
                    simulated_exposure = 0.20
                else:
                    simulated_exposure = 0.05
                deployment_simulation.append(
                    {
                        "window_id": window["window_id"],
                        "test_ic": test_ic,
                        "simulated_exposure": simulated_exposure,
                    }
                )

        sim_df = pd.DataFrame(deployment_simulation)
        if not sim_df.empty:
            print(f"Mean simulated exposure: {sim_df['simulated_exposure'].mean():.1%}")
            print(f"Windows above 20% exposure: {(sim_df['simulated_exposure'] >= 0.20).sum()}/{len(sim_df)}")
            print(f"Windows in HOLD (5%): {(sim_df['simulated_exposure'] <= 0.05).sum()}/{len(sim_df)}")

        self.state["mean_gain"] = mean_gain
        self.state["passes_parity"] = passes_parity
        self.saver.save_all(
            self.output_dir,
            self.track_name,
            {
                "day6_ensemble": ensemble_results_list,
                "day6_deployment_simulation": sim_df.to_dict(orient="records") if not sim_df.empty else [],
            },
        )

    def _run_day7(self) -> None:
        verdict_engine = PromotionVerdict()
        ranked_models = self.state.get("ranked_models") or self._rank_models()
        best_model = ranked_models[0] if ranked_models else None
        best_summary = self.state.get("all_summaries", {}).get(best_model, {})
        best_stability = self.state.get("all_stabilities", {}).get(best_model, {})
        best_regime = (
            self.engine.regime_breakdown(self.state["all_model_results"][best_model])
            if best_model and "all_model_results" in self.state
            else {}
        )
        ensemble_gain_result = {
            "ic_gain": self.state.get("mean_gain"),
            "passes_min_parity": self.state.get("passes_parity"),
        }
        verdict = verdict_engine.compute(
            self._ensure_ic_table_available("final verdict"),
            best_summary,
            best_stability,
            best_regime,
            ensemble_gain_result,
            self.track_name,
        )

        print("\n" + "=" * 60)
        print(f"TRACK A FINAL VERDICT: {verdict['verdict']} - {verdict['verdict_label']}")
        print("=" * 60)
        if best_model is not None:
            print(f"\nBest model: {best_model}")
        print(f"Recommendation: {verdict['recommendation']}")
        print("\nOpen questions:")
        for question in verdict["open_questions"]:
            print(f"  - {question}")

        memo = verdict_engine.format_memo(verdict, self.track_name)
        print("\n--- PROMOTION MEMO ---")
        print(memo)

        memo_path = self.output_dir / "track_a_promotion_memo.md"
        memo_path.write_text(memo, encoding="utf-8")
        total_time = (time.time() - self.sprint_start) / 60.0
        self.state["run_summary"] = {
            "best_model": best_model,
            "verdict": verdict["verdict"],
            "verdict_label": verdict["verdict_label"],
            "memo_path": str(memo_path),
            "total_runtime_minutes": total_time,
            "day_status": self.day_status,
        }
        self.saver.save_all(
            self.output_dir,
            self.track_name,
            {
                "day7_verdict": verdict,
                "day7_memo_path": str(memo_path),
                "all_model_summaries": self.state.get("all_summaries", {}),
                "all_model_stabilities": self.state.get("all_stabilities", {}),
                "total_runtime_minutes": total_time,
            },
        )
        print(f"\n\nTrack A complete. Total runtime: {total_time:.1f} minutes")
        print(f"All results saved to {self.output_dir}")


def run_track_a_notebook(config: TrackARunConfig | None = None) -> dict[str, Any]:
    """Convenience entrypoint used by the Kaggle notebook."""

    runner = TrackARunner(config=config)
    return runner.run()
