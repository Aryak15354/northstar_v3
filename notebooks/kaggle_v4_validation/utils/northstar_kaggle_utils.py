"""Shared utilities for Northstar Kaggle validation notebooks."""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.preprocessing import StandardScaler

REQUIRED_EXPORT_FILES = (
    "northstar_features.parquet",
    "northstar_walk_forward_splits.json",
    "northstar_regime_labels.parquet",
)


def _make_serializable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_serializable(v) for v in obj]
    if isinstance(obj, tuple):
        return [_make_serializable(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        value = float(obj)
        return None if np.isnan(value) or np.isinf(value) else value
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, float):
        return None if np.isnan(obj) or np.isinf(obj) else obj
    return obj


def _safe_rank_corr(left: np.ndarray, right: np.ndarray) -> float:
    x = np.asarray(left, dtype=float)
    y = np.asarray(right, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    if int(mask.sum()) < 2:
        return float("nan")
    corr, _ = spearmanr(x[mask], y[mask])
    return float(corr) if np.isfinite(corr) else float("nan")


def _looks_like_northstar_data_dir(path: Path) -> bool:
    return path.is_dir() and all((path / filename).exists() for filename in REQUIRED_EXPORT_FILES)


def _discover_kaggle_data_dir() -> Path | None:
    kaggle_input = Path("/kaggle/input")
    if not kaggle_input.exists():
        return None

    exact_match = kaggle_input / "northstar-v4-validation-data"
    if _looks_like_northstar_data_dir(exact_match):
        return exact_match

    for candidate in sorted(kaggle_input.iterdir()):
        if _looks_like_northstar_data_dir(candidate):
            return candidate

    for feature_path in sorted(kaggle_input.rglob("northstar_features.parquet")):
        candidate = feature_path.parent
        if _looks_like_northstar_data_dir(candidate):
            return candidate

    return None


class NorthstarPaths:
    """Resolves data paths for both Kaggle and local environments."""

    def __init__(self, data_dir: str | Path | None = None):
        if data_dir:
            resolved_dir = Path(data_dir)
        elif (discovered := _discover_kaggle_data_dir()) is not None:
            resolved_dir = discovered
        else:
            raise ValueError("Cannot find data directory. Pass data_dir= explicitly.")

        if not resolved_dir.exists():
            raise ValueError(f"Data directory does not exist: {resolved_dir}")

        self.data_dir = resolved_dir
        self.output_dir = Path("/kaggle/working/results") if Path("/kaggle").exists() else Path("./kaggle_results")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        missing = [str(path.name) for path in [self.features, self.splits, self.regime_labels] if not path.exists()]
        if missing:
            raise ValueError(
                f"Data directory is missing required files: {', '.join(missing)} in {self.data_dir}"
            )

    @property
    def features(self) -> Path:
        return self.data_dir / "northstar_features.parquet"

    @property
    def splits(self) -> Path:
        return self.data_dir / "northstar_walk_forward_splits.json"

    @property
    def regime_labels(self) -> Path:
        return self.data_dir / "northstar_regime_labels.parquet"


class NorthstarDataLoader:
    def __init__(self, paths: NorthstarPaths):
        self.paths = paths
        self.last_window_context: dict[str, Any] = {}

    def load_all(self) -> tuple[pd.DataFrame, list[dict], pd.DataFrame]:
        features_df = pd.read_parquet(self.paths.features)
        features_df["date"] = pd.to_datetime(features_df["date"], errors="coerce")
        features_df["ticker"] = features_df["ticker"].astype("string")

        with self.paths.splits.open("r", encoding="utf-8") as handle:
            splits = json.load(handle)

        regime_df = pd.read_parquet(self.paths.regime_labels)
        regime_df["date"] = pd.to_datetime(regime_df["date"], errors="coerce")

        print(
            "Loaded data:\n"
            f"  features: {features_df.shape}\n"
            f"  splits:   {len(splits)} windows\n"
            f"  regimes:  {regime_df.shape}"
        )
        return features_df, splits, regime_df

    def get_feature_names(self, features_df: pd.DataFrame) -> list[str]:
        exclude = {"date", "ticker", "target_weekly_return", "forward_return_5d"}
        numeric_columns = set(features_df.select_dtypes(include=[np.number]).columns)
        return [
            column
            for column in features_df.columns
            if column in numeric_columns and column not in exclude and not column.endswith("__realized")
        ]

    def get_window_data(
        self,
        features_df: pd.DataFrame,
        split: dict,
        include_dates: bool = False,
    ) -> tuple[Any, ...]:
        feature_names = self.get_feature_names(features_df)
        train_start = pd.Timestamp(split["train_start"])
        train_end = pd.Timestamp(split["train_end"])
        test_start = pd.Timestamp(split["test_start"])
        test_end = pd.Timestamp(split["test_end"])

        train_df = features_df.loc[features_df["date"].between(train_start, train_end)].copy()
        test_df = features_df.loc[features_df["date"].between(test_start, test_end)].copy()
        train_df = train_df.dropna(subset=["target_weekly_return"]).sort_values(["date", "ticker"], kind="mergesort")
        test_df = test_df.dropna(subset=["target_weekly_return"]).sort_values(["date", "ticker"], kind="mergesort")

        if train_df.empty or test_df.empty:
            raise ValueError(
                f"window {split.get('window_id', 'unknown')} has empty train/test slice "
                f"(train={len(train_df)}, test={len(test_df)})"
            )

        train_features = train_df[feature_names].replace([np.inf, -np.inf], np.nan)
        test_features = test_df[feature_names].replace([np.inf, -np.inf], np.nan)

        medians = train_features.median(axis=0, numeric_only=True).fillna(0.0)
        train_features = train_features.fillna(medians)
        test_features = test_features.fillna(medians)

        scaler = StandardScaler()
        x_train = scaler.fit_transform(train_features.to_numpy(dtype=np.float32)).astype(np.float32)
        x_test = scaler.transform(test_features.to_numpy(dtype=np.float32)).astype(np.float32)
        y_train = train_df["target_weekly_return"].to_numpy(dtype=np.float32)
        y_test = test_df["target_weekly_return"].to_numpy(dtype=np.float32)

        self.last_window_context = {
            "train_dates": train_df["date"].to_numpy(),
            "test_dates": test_df["date"].to_numpy(),
            "train_tickers": train_df["ticker"].astype(str).to_numpy(),
            "test_tickers": test_df["ticker"].astype(str).to_numpy(),
        }

        print(
            f"Window {split.get('window_id', 'n/a')}: "
            f"train rows={len(train_df)} "
            f"test rows={len(test_df)} "
            f"feature count={len(feature_names)} "
            f"target coverage={test_df['target_weekly_return'].notna().mean() * 100.0:.2f}%"
        )

        if include_dates:
            return (
                x_train,
                y_train,
                x_test,
                y_test,
                train_df["date"].to_numpy(),
                test_df["date"].to_numpy(),
                feature_names,
            )

        return x_train, y_train, x_test, y_test, feature_names


class WalkForwardEngine:
    def __init__(self, model_name: str, config: dict, output_dir: Path | None):
        self.model_name = model_name
        self.config = dict(config)
        self.output_dir = Path(output_dir) if output_dir is not None else (Path("/kaggle/working/results") if Path("/kaggle").exists() else Path("./kaggle_results"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_path = self.output_dir / f"{model_name}_checkpoint.json"

    def run(
        self,
        model_factory: Callable,
        features_df: pd.DataFrame,
        splits: list[dict],
        data_loader: NorthstarDataLoader,
        regime_df: pd.DataFrame | None = None,
    ) -> dict:
        results: dict[str, Any] = {
            "model_name": self.model_name,
            "model": self.model_name,
            "config": dict(self.config),
            "feature_names": data_loader.get_feature_names(features_df),
            "feature_importances": {},
            "windows": [],
            "windows_total": len(splits),
            "run_started_at": datetime.now(timezone.utc).isoformat(),
        }

        for index, split in enumerate(splits, start=1):
            window_id = int(split.get("window_id", index))
            try:
                split_for_run = dict(split)
                if regime_df is not None:
                    test_start = pd.Timestamp(split.get("test_start"))
                    test_end = pd.Timestamp(split.get("test_end"))
                    mask = regime_df["date"].between(test_start, test_end)
                    if mask.any():
                        regime_counts = regime_df.loc[mask, "regime"].astype(str).value_counts()
                        split_for_run["regime"] = str(regime_counts.index[0]) if not regime_counts.empty else split.get("regime", "unknown")
                        if "vol_regime" in regime_df.columns:
                            vol_mode = regime_df.loc[mask, "vol_regime"].mode(dropna=True)
                            split_for_run["vol_regime"] = str(vol_mode.iloc[0]) if not vol_mode.empty else "unknown"
                        else:
                            split_for_run["vol_regime"] = "unknown"
                    else:
                        split_for_run["regime"] = "unknown"
                        split_for_run["vol_regime"] = "unknown"

                x_train, y_train, x_test, y_test, _ = data_loader.get_window_data(features_df, split_for_run)
                run_config = dict(self.config)
                run_config["window_id"] = window_id
                run_config["split"] = split_for_run
                run_config["feature_names"] = results["feature_names"]
                run_config["window_context"] = dict(getattr(data_loader, "last_window_context", {}))
                run_config["regime_df"] = regime_df
                train_preds, test_preds, importance = model_factory(x_train, y_train, x_test, run_config)
                metrics = self._compute_metrics(y_train, train_preds, y_test, test_preds, split_for_run)
                metrics.update(
                    {
                        "window_id": window_id,
                        "train_start": split.get("train_start"),
                        "train_end": split.get("train_end"),
                        "test_start": split.get("test_start"),
                        "test_end": split.get("test_end"),
                        "regime": metrics.get("regime", split.get("regime", "unknown")),
                        "vol_regime": metrics.get("vol_regime", "unknown"),
                        "n_train": int(len(y_train)),
                        "n_test": int(len(y_test)),
                    }
                )
                results["windows"].append(metrics)

                if importance is not None:
                    results["feature_importances"][str(window_id)] = np.asarray(importance, dtype=float)

                print(
                    f"{window_id:02d} | "
                    f"train_ic={metrics['train_ic']:.4f} | "
                    f"test_ic={metrics['test_ic']:.4f} | "
                    f"ratio={metrics['train_test_ratio']:.2f} | "
                    f"hit_rate={metrics['hit_rate']:.4f}"
                )
            except Exception as exc:  # noqa: BLE001
                error_payload = {
                    "window_id": window_id,
                    "train_start": split.get("train_start"),
                    "train_end": split.get("train_end"),
                    "test_start": split.get("test_start"),
                    "test_end": split.get("test_end"),
                    "regime": split.get("regime", "unknown"),
                    "error": str(exc),
                }
                results["windows"].append(error_payload)
                print(f"WARNING window {window_id}: {exc}")

            checkpoint = {
                "model_name": self.model_name,
                "windows_completed": len([w for w in results["windows"] if "error" not in w]),
                "windows_total": len(splits),
                "windows": results["windows"],
            }
            self.checkpoint_path.write_text(
                json.dumps(_make_serializable(checkpoint), indent=2),
                encoding="utf-8",
            )

        results["run_completed_at"] = datetime.now(timezone.utc).isoformat()
        return results

    def _compute_metrics(
        self,
        y_train: np.ndarray,
        y_pred_train: np.ndarray,
        y_test: np.ndarray,
        y_pred_test: np.ndarray,
        split: dict,
    ) -> dict:
        def safe_spearman(a, b):
            mask = np.isfinite(a) & np.isfinite(b)
            if mask.sum() < 3:
                return 0.0
            corr, _ = spearmanr(a[mask], b[mask])
            return float(corr) if np.isfinite(corr) else 0.0

        y_train = np.asarray(y_train, dtype=float)
        y_pred_train = np.asarray(y_pred_train, dtype=float)
        y_test = np.asarray(y_test, dtype=float)
        y_pred_test = np.asarray(y_pred_test, dtype=float)

        train_ic = safe_spearman(y_train, y_pred_train)
        test_ic = safe_spearman(y_test, y_pred_test)
        ratio = abs(train_ic) / max(abs(test_ic), 1e-6)
        hit_rate = float(np.mean(np.sign(y_pred_test) == np.sign(y_test)))

        n = len(y_test)
        q_size = max(1, n // 5)
        sorted_idx = np.argsort(y_pred_test)
        bottom_ret = float(np.mean(y_test[sorted_idx[:q_size]]))
        top_ret = float(np.mean(y_test[sorted_idx[-q_size:]]))
        quintile_spread = top_ret - bottom_ret

        return {
            "window_id": split.get("window_id", 0),
            "test_start": split.get("test_start", ""),
            "train_ic": round(train_ic, 6),
            "test_ic": round(test_ic, 6),
            "train_test_ratio": round(ratio, 4),
            "hit_rate": round(hit_rate, 4),
            "ic_positive": bool(test_ic > 0.0),
            "training_collapsed": bool(abs(train_ic) < 0.001),
            "signal_inverted": bool((train_ic > 0.01) and (test_ic < -0.01)),
            "top_quintile_return": round(top_ret, 6),
            "bottom_quintile_return": round(bottom_ret, 6),
            "quintile_spread": round(quintile_spread, 6),
            "regime": split.get("regime", "unknown"),
        }

    def _compute_window_metrics(
        self,
        y_train: np.ndarray,
        y_pred_train: np.ndarray,
        y_test: np.ndarray,
        y_pred_test: np.ndarray,
        split: dict,
    ) -> dict:
        return self._compute_metrics(y_train, y_pred_train, y_test, y_pred_test, split)


class SummaryComputer:
    GATE_RATIO = 2.5
    GATE_IC = 0.015
    GATE_HIT = 0.51

    def compute(self, results: dict) -> dict:
        windows = results.get("windows", [])
        valid = [window for window in windows if "error" not in window]
        collapsed = [window for window in valid if window.get("training_collapsed", False)]
        inverted = [window for window in valid if window.get("signal_inverted", False)]
        active = [window for window in valid if not window.get("training_collapsed", False)]
        windows_total = int(results.get("windows_total", len(windows)))
        windows_completed = len(valid)
        windows_failed = len(windows) - windows_completed

        if windows_completed < 3:
            return {
                "mean_test_ic": float("nan"),
                "mean_test_ic_all_windows": float("nan"),
                "mean_test_ic_active_windows": None,
                "std_test_ic": float("nan"),
                "ic_ir": float("nan"),
                "mean_train_test_ratio": float("nan"),
                "mean_hit_rate": float("nan"),
                "mean_quintile_spread": float("nan"),
                "n_collapsed_windows": len(collapsed),
                "n_inverted_windows": len(inverted),
                "collapse_rate": 0.0,
                "ic_used_for_gate": "insufficient_data",
                "windows_completed": windows_completed,
                "windows_total": windows_total,
                "windows_failed": windows_failed,
                "passed_viability_filter": False,
                "verdict": "INSUFFICIENT_DATA",
                "regime_breakdown": {},
            }

        frame = pd.DataFrame(valid)
        active_frame = pd.DataFrame(active) if active else pd.DataFrame(columns=frame.columns)
        test_ic = pd.to_numeric(frame["test_ic"], errors="coerce")
        mean_test_ic_all = float(test_ic.mean())
        mean_test_ic_active = (
            float(pd.to_numeric(active_frame["test_ic"], errors="coerce").mean())
            if not active_frame.empty
            else None
        )
        std_test_ic = float(test_ic.std(ddof=1)) if len(frame) > 1 else 0.0
        ic_ir = float(mean_test_ic_all / std_test_ic) if abs(std_test_ic) > 1e-12 else 0.0
        mean_ratio = float(pd.to_numeric(frame["train_test_ratio"], errors="coerce").mean())
        mean_hit = float(pd.to_numeric(frame["hit_rate"], errors="coerce").mean())
        mean_spread = float(pd.to_numeric(frame.get("quintile_spread"), errors="coerce").mean())
        collapse_rate = len(collapsed) / len(valid) if valid else 0.0
        use_active = collapse_rate > 0.2 and mean_test_ic_active is not None
        ic_for_gate = mean_test_ic_active if use_active else mean_test_ic_all

        passed = bool(
            mean_ratio < self.GATE_RATIO
            and ic_for_gate > self.GATE_IC
            and mean_hit > self.GATE_HIT
            and len(inverted) <= 3
        )
        verdict = "QUALIFIED" if passed else "NOT_QUALIFIED"

        regime_breakdown: dict[str, Any] = {}
        if "regime" in frame.columns:
            grouped = frame.groupby("regime", dropna=False)
            for regime, group in grouped:
                regime_breakdown[str(regime if pd.notna(regime) else "unknown")] = {
                    "windows": int(len(group)),
                    "mean_test_ic": float(pd.to_numeric(group["test_ic"], errors="coerce").mean()),
                    "mean_hit_rate": float(pd.to_numeric(group["hit_rate"], errors="coerce").mean()),
                }

        return {
            "mean_test_ic": mean_test_ic_all,
            "mean_test_ic_all_windows": mean_test_ic_all,
            "mean_test_ic_active_windows": mean_test_ic_active,
            "std_test_ic": std_test_ic,
            "ic_ir": ic_ir,
            "mean_train_test_ratio": mean_ratio,
            "mean_hit_rate": mean_hit,
            "mean_quintile_spread": mean_spread,
            "n_collapsed_windows": len(collapsed),
            "n_inverted_windows": len(inverted),
            "collapse_rate": collapse_rate,
            "ic_used_for_gate": "active_windows" if use_active else "all_windows",
            "windows_completed": windows_completed,
            "windows_total": windows_total,
            "windows_failed": windows_failed,
            "passed_viability_filter": passed,
            "verdict": verdict,
            "regime_breakdown": regime_breakdown,
        }

    def compare_to_baseline(self, summary: dict) -> dict:
        baseline_ic = 0.0277
        baseline_ratio = 6.9908
        baseline_hit = 0.5126

        mean_ic = float(
            summary.get("mean_test_ic_active_windows")
            if summary.get("mean_test_ic_active_windows") is not None
            else summary.get("mean_test_ic", np.nan)
        )
        mean_ratio = float(summary.get("mean_train_test_ratio", np.nan))
        mean_hit = float(summary.get("mean_hit_rate", np.nan))

        ic_improvement_pct = ((mean_ic - baseline_ic) / abs(baseline_ic)) * 100.0 if np.isfinite(mean_ic) else float("nan")
        ratio_improvement_pct = ((baseline_ratio - mean_ratio) / abs(baseline_ratio)) * 100.0 if np.isfinite(mean_ratio) else float("nan")
        qualifies_vs_baseline = bool(
            summary.get("passed_viability_filter", False)
            and np.isfinite(mean_ic)
            and np.isfinite(mean_ratio)
            and mean_ic >= baseline_ic
            and mean_ratio < baseline_ratio
            and np.isfinite(mean_hit)
            and mean_hit >= baseline_hit
        )

        return {
            "ic_improvement_pct": ic_improvement_pct,
            "ratio_improvement_pct": ratio_improvement_pct,
            "qualifies_vs_baseline": qualifies_vs_baseline,
        }


class FeatureStabilityAnalyzer:
    def _importance_frame(self, feature_importances: dict, feature_names: list[str]) -> pd.DataFrame:
        vectors: list[np.ndarray] = []
        columns: list[str] = []
        for window_id, importance in (feature_importances or {}).items():
            arr = np.asarray(importance, dtype=float).reshape(-1)
            if arr.size != len(feature_names):
                continue
            vectors.append(np.abs(arr))
            columns.append(str(window_id))
        if not vectors:
            return pd.DataFrame(index=feature_names)
        matrix = np.column_stack(vectors)
        return pd.DataFrame(matrix, index=feature_names, columns=columns)

    def analyze(self, feature_importances: dict, feature_names: list[str]) -> dict:
        imp_df = self._importance_frame(feature_importances, feature_names)
        clean_importances = [imp_df[column].to_numpy(dtype=float) for column in imp_df.columns]

        if not clean_importances:
            return {
                "windows_used": 0,
                "mean_pairwise_correlation": float("nan"),
                "pairwise_correlations": [],
                "per_feature_cv": {},
                "top_unstable_features": {},
                "top_stable_features": {},
                "mean_importance_by_feature": {},
                "top_features_by_mean_importance": [],
                "band": "unknown",
                "action": "No valid feature-importance vectors were available for stability analysis.",
            }

        pairwise_correlations: list[float] = []
        for left_idx in range(len(clean_importances)):
            for right_idx in range(left_idx + 1, len(clean_importances)):
                corr = _safe_rank_corr(clean_importances[left_idx], clean_importances[right_idx])
                if np.isfinite(corr):
                    pairwise_correlations.append(float(corr))

        mean_pairwise_correlation = (
            float(np.mean(pairwise_correlations))
            if pairwise_correlations
            else float("nan")
        )

        stacked = np.vstack(clean_importances)
        mean_importance = np.nanmean(stacked, axis=0)
        std_importance = np.nanstd(stacked, axis=0)
        cv = std_importance / np.where(np.abs(mean_importance) > 1e-12, np.abs(mean_importance), 1e-12)

        by_cv = sorted(zip(feature_names, cv), key=lambda item: (-item[1], item[0]))
        by_cv_stable = sorted(zip(feature_names, cv), key=lambda item: (item[1], item[0]))
        by_importance = sorted(zip(feature_names, mean_importance), key=lambda item: (-item[1], item[0]))

        if np.isfinite(mean_pairwise_correlation) and mean_pairwise_correlation >= 0.70:
            band = "stable"
            action = "Feature importance is stable across windows. This model is behaving consistently."
        elif np.isfinite(mean_pairwise_correlation) and mean_pairwise_correlation >= 0.40:
            band = "cautious"
            action = "Feature importance is moderately stable. Review unstable features before trusting promotion."
        elif np.isfinite(mean_pairwise_correlation):
            band = "unstable"
            action = "Feature importance is unstable across windows. Treat generalization claims cautiously."
        else:
            band = "unknown"
            action = "Need at least two valid windows with importance vectors to assess stability confidently."

        return {
            "windows_used": len(clean_importances),
            "mean_pairwise_correlation": mean_pairwise_correlation,
            "pairwise_correlations": pairwise_correlations,
            "per_feature_cv": OrderedDict((name, float(score)) for name, score in sorted(zip(feature_names, cv), key=lambda item: item[0])),
            "top_unstable_features": OrderedDict((name, float(score)) for name, score in by_cv[:15]),
            "top_stable_features": OrderedDict((name, float(score)) for name, score in by_cv_stable[:15]),
            "mean_importance_by_feature": OrderedDict((name, float(score)) for name, score in by_importance),
            "top_features_by_mean_importance": [name for name, _ in by_importance],
            "band": band,
            "action": action,
        }

    def get_anchor_features(
        self,
        feature_importances: dict,
        feature_names: list[str],
        cv_threshold: float = 0.5,
    ) -> list[str]:
        """
        Returns features with CV below threshold - these are stable signal anchors.
        """
        imp_df = self._importance_frame(feature_importances, feature_names).fillna(0.0)
        if imp_df.empty:
            return []
        mean_importance = imp_df.mean(axis=1).abs()
        cv = imp_df.std(axis=1) / (mean_importance + 1e-9)
        anchors = cv[cv < cv_threshold].sort_values()
        return anchors.index.tolist()


class ResultsSaver:
    def save(self, model_name: str, results: dict, summary: dict, stability: dict, output_dir: Path):
        baseline_comparison = SummaryComputer().compare_to_baseline(summary)
        payload = {
            "model": model_name,
            "summary": summary,
            "stability": stability,
            "windows": results.get("windows", []),
            "baseline_comparison": baseline_comparison,
            "config": results.get("config", {}),
            "run_timestamp": datetime.now(timezone.utc).isoformat(),
            "feature_count": int(len(results.get("feature_names", []))),
        }

        output_path = Path(output_dir) / f"{model_name}_final.json"
        serializable_payload = _make_serializable(payload)
        output_path.write_text(json.dumps(serializable_payload, indent=2), encoding="utf-8")
        size_mb = output_path.stat().st_size / (1024.0 * 1024.0)
        print(f"saved to {output_path} ({size_mb:.2f} MB)")

    def print_model_verdict(self, model_name: str, summary: dict, stability: dict):
        print(
            f"{model_name}: verdict={summary.get('verdict', 'UNKNOWN')} "
            f"ic={float(summary.get('mean_test_ic', np.nan)):.4f} "
            f"ratio={float(summary.get('mean_train_test_ratio', np.nan)):.2f}x "
            f"hit={float(summary.get('mean_hit_rate', np.nan)):.4f} "
            f"stability={stability.get('band', 'unknown')}"
        )
