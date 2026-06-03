#!/usr/bin/env python3
"""Write brand-new flat Kaggle notebooks for the compendium experiments."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import nbformat as nbf


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOWNLOADS_DIR = Path.home() / "Downloads"
NOTEBOOK_DIR = PROJECT_ROOT / "notebooks" / "kaggle_sprint"


def _md(text: str):
    return nbf.v4.new_markdown_cell(dedent(text).strip() + "\n")


def _code(text: str):
    return nbf.v4.new_code_cell(dedent(text).strip() + "\n")


def _write_notebook(path: Path, cells: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    nb = nbf.v4.new_notebook(cells=cells)
    nb.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    nb.metadata["language_info"] = {
        "name": "python",
        "version": "3.12",
    }
    path.write_text(nbf.writes(nb), encoding="utf-8")


RATIO_NOTEBOOK = [
    _md(
        """
        # NORTHSTAR V3 Ratio Campaign Fresh Build

        This is a brand-new notebook for **EXP-09 to EXP-12** only.

        It is built around the current merged export and the compendium's current problem statement:
        - CatBoost is the active leader
        - the core remaining gate is the **train/test ratio**
        - feature reduction alone is not the answer
        - the right work is regularization, early stopping, and training-window structure

        Attach only:
        - `northstar-v3-feature-export`
        """
    ),
    _md("## Config"),
    _code(
        """
        from pathlib import Path

        SELECTED_EXP = "EXP-09"  # EXP-09 | EXP-10 | EXP-11 | EXP-12
        RUN_FULL_CHAIN = True
        MAX_SPLITS = None
        VERSION_TAG = "fresh_20260406"
        OUTPUT_ROOT = Path("/kaggle/working/northstar_ratio_campaign_fresh")

        EXPORT_DIR_OVERRIDE = None
        EXPORT_CANDIDATES = [
            "/kaggle/input/northstar-v3-feature-export",
            "/kaggle/input/northstar-v3-feature-export-1",
            "/kaggle/input/northstar-v3-feature-export-2",
        ]

        MANUAL_BASE_PARAMS = {}

        EXPERIMENT_GRID = {
            "EXP-09": {
                "title": "CatBoost Depth Ablation + Early Stopping",
                "depth_grid": [3, 4, 5],
                "early_stopping_rounds": [20, 30, 50],
                "base_params": {"depth": 4, "l2_leaf_reg": 15.0, "min_data_in_leaf": 40},
            },
            "EXP-10": {
                "title": "L2 Regularization Sweep",
                "l2_leaf_reg_grid": [3, 5, 8, 10, 15, 20],
            },
            "EXP-11": {
                "title": "Ordered vs Plain Boosting Type",
                "boosting_types": ["Ordered", "Plain"],
            },
            "EXP-12": {
                "title": "Training Window Length Extension",
                "train_window_years": [2, 3, 4],
                "test_window_weeks": 26,
                "step_weeks": 26,
            },
        }

        print(f"Notebook configured for {SELECTED_EXP}")
        """
    ),
    _md("## Imports, Data Loading, And Contract Checks"),
    _code(
        """
        import json
        import math
        import time
        import warnings
        from datetime import datetime

        import numpy as np
        import pandas as pd
        from IPython.display import Markdown, display

        warnings.filterwarnings("ignore")

        try:
            from catboost import CatBoostRegressor
        except Exception:
            CatBoostRegressor = None

        try:
            from scipy.stats import spearmanr
        except Exception:
            spearmanr = None

        try:
            from sklearn.ensemble import HistGradientBoostingRegressor
        except Exception:
            HistGradientBoostingRegressor = None

        DEFAULT_PARAMS = {
            "depth": 4,
            "l2_leaf_reg": 15.0,
            "min_data_in_leaf": 40,
            "od_wait": 30,
            "boosting_type": "Ordered",
            "iterations": 400,
            "learning_rate": 0.05,
        }

        EXTRA_METADATA_NUMERIC = [
            "close",
            "volume",
            "international_revenue_proxy",
            "macro_linkage_score",
            "oil_sensitivity_score",
            "steel_sensitivity_score",
            "copper_sensitivity_score",
            "gold_sensitivity_score",
            "fx_sensitivity_score",
            "rate_sensitivity_score",
        ]

        LOG_PREFIX = "[ratio-fresh]"


        def log(message):
            stamp = datetime.now().strftime("%H:%M:%S")
            print(f"{LOG_PREFIX} {stamp} | {message}", flush=True)


        def log_kv(title, **kwargs):
            parts = ", ".join(f"{key}={value}" for key, value in kwargs.items())
            log(f"{title}: {parts}" if parts else title)


        def log_frame(name, frame):
            if frame is None:
                log(f"{name}: frame=None")
                return
            details = {
                "rows": len(frame),
                "cols": frame.shape[1],
            }
            if "date" in frame.columns and len(frame):
                details["date_min"] = str(pd.to_datetime(frame["date"], errors="coerce").min())
                details["date_max"] = str(pd.to_datetime(frame["date"], errors="coerce").max())
            if "ticker" in frame.columns:
                details["tickers"] = int(frame["ticker"].nunique())
            log_kv(name, **details)


        def resolve_output_root(preferred):
            preferred = Path(preferred)
            candidates = [
                preferred,
                Path("/kaggle/working") / preferred.name,
                Path.cwd() / preferred.name,
                Path("/tmp") / preferred.name,
            ]
            seen = set()
            for candidate in candidates:
                candidate = candidate.expanduser()
                key = str(candidate)
                if key in seen:
                    continue
                seen.add(key)
                try:
                    candidate.mkdir(parents=True, exist_ok=True)
                    log(f"Resolved output root at: {candidate}")
                    return candidate
                except Exception as exc:
                    log(f"Output root candidate failed: {candidate} ({exc})")
            raise RuntimeError(f"Unable to create output root from preferred path: {preferred}")


        def resolve_output_root(preferred):
            preferred = Path(preferred)
            candidates = [
                preferred,
                Path("/kaggle/working") / preferred.name,
                Path.cwd() / preferred.name,
                Path("/tmp") / preferred.name,
            ]
            seen = set()
            for candidate in candidates:
                candidate = candidate.expanduser()
                key = str(candidate)
                if key in seen:
                    continue
                seen.add(key)
                try:
                    candidate.mkdir(parents=True, exist_ok=True)
                    log(f"Resolved output root at: {candidate}")
                    return candidate
                except Exception as exc:
                    log(f"Output root candidate failed: {candidate} ({exc})")
            raise RuntimeError(f"Unable to create output root from preferred path: {preferred}")


        def dedupe(items):
            seen = set()
            out = []
            for item in items:
                if item in seen:
                    continue
                seen.add(item)
                out.append(item)
            return out


        def json_ready(value):
            if isinstance(value, dict):
                return {str(k): json_ready(v) for k, v in value.items()}
            if isinstance(value, (list, tuple)):
                return [json_ready(v) for v in value]
            if isinstance(value, Path):
                return str(value)
            if isinstance(value, pd.Timestamp):
                return value.isoformat()
            if isinstance(value, np.generic):
                return value.item()
            if isinstance(value, float) and not np.isfinite(value):
                return None
            return value


        def write_json(path, payload):
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(json_ready(payload), indent=2), encoding="utf-8")
            log(f"Wrote JSON: {path}")
            return path


        def write_text(path, text):
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(text).strip() + "\\n", encoding="utf-8")
            log(f"Wrote text: {path}")
            return path


        def write_table(path, frame):
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix.lower() == ".parquet":
                frame.to_parquet(path, index=False)
            else:
                frame.to_csv(path, index=False)
            log_kv("Wrote table", path=path, rows=len(frame), cols=frame.shape[1])
            return path


        def resolve_export_dir():
            required = [
                "northstar_features.parquet",
                "northstar_metadata.parquet",
                "northstar_regime_labels.parquet",
                "northstar_walk_forward_splits.json",
            ]

            def _candidate_dirs(root):
                if not root.exists() or not root.is_dir():
                    return []
                results = []
                if all((root / name).exists() for name in required):
                    results.append(root)
                try:
                    for match in root.rglob(required[0]):
                        parent = match.parent
                        if all((parent / name).exists() for name in required):
                            results.append(parent)
                except Exception:
                    pass
                deduped = []
                seen = set()
                for item in sorted(results, key=lambda p: (len(p.parts), str(p))):
                    key = str(item)
                    if key in seen:
                        continue
                    seen.add(key)
                    deduped.append(item)
                return deduped

            probes = []
            if EXPORT_DIR_OVERRIDE:
                probes.append(Path(EXPORT_DIR_OVERRIDE).expanduser())
            probes.extend(Path(item) for item in EXPORT_CANDIDATES)
            kaggle_root = Path("/kaggle/input")
            if kaggle_root.exists():
                probes.append(kaggle_root)
                probes.extend(sorted(path for path in kaggle_root.iterdir() if path.is_dir()))

            checked = []
            log("Resolving export dataset directory")
            for probe in probes:
                log(f"Checking probe: {probe}")
                if not probe.exists():
                    checked.append(str(probe))
                    log(f"Probe missing: {probe}")
                    continue
                for candidate in _candidate_dirs(probe):
                    log(f"Resolved export dataset at: {candidate}")
                    return candidate
                checked.append(str(probe))
                log(f"No complete export bundle found under: {probe}")

            raise FileNotFoundError(
                "Unable to resolve the export dataset recursively. Checked:\\n- "
                + "\\n- ".join(checked[:40])
            )


        def load_bundle(export_dir):
            root = Path(export_dir).expanduser().resolve()
            log(f"Loading export bundle from {root}")
            started = time.time()
            log("Reading northstar_features.parquet")
            features = pd.read_parquet(root / "northstar_features.parquet")
            log_frame("features", features)
            log("Reading northstar_metadata.parquet")
            metadata = pd.read_parquet(root / "northstar_metadata.parquet")
            log_frame("metadata", metadata)
            log("Reading northstar_regime_labels.parquet")
            regimes = pd.read_parquet(root / "northstar_regime_labels.parquet")
            log_frame("regimes", regimes)
            log("Reading northstar_walk_forward_splits.json")
            splits = json.loads((root / "northstar_walk_forward_splits.json").read_text(encoding="utf-8"))
            log_kv("Loaded splits", count=len(splits))

            for frame in [features, metadata, regimes]:
                frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()

            log("Merging features with metadata")
            merged = features.merge(metadata, on=["date", "ticker"], how="left", sort=False, suffixes=("", "_meta"))
            regime_cols = [c for c in ["date", "plan_regime_id", "plan_regime_label", "regime", "major_event_id"] if c in regimes.columns]
            if regime_cols:
                log_kv("Merging regime columns", columns=regime_cols)
                merged = merged.merge(regimes[regime_cols].drop_duplicates("date"), on="date", how="left", sort=False)
            for col in ["plan_regime_id", "plan_regime_label", "regime", "major_event_id"]:
                if col not in merged.columns:
                    left = f"{col}_x"
                    right = f"{col}_y"
                    if left in merged.columns or right in merged.columns:
                        merged[col] = merged.get(left)
                        if right in merged.columns:
                            merged[col] = merged[col].where(pd.Series(merged[col]).notna(), merged[right])
            merged["plan_regime_label"] = merged["plan_regime_label"].fillna("Unknown").astype(str)
            merged["sector"] = merged["sector"].fillna("Unknown").astype(str)
            log_frame("merged", merged)
            log_kv("Bundle load complete", seconds=round(time.time() - started, 2))
            return {
                "root": root,
                "features": features,
                "metadata": metadata,
                "regimes": regimes,
                "splits": list(splits),
                "merged": merged,
            }


        def validate_bundle(bundle):
            features = bundle["features"]
            log("Validating export contract")
            required = ["date", "ticker", "target_weekly_return"]
            missing = [c for c in required if c not in features.columns]
            if missing:
                raise RuntimeError(f"Missing required columns: {missing}")
            required_flags = ["pledge_pct_available", "rating_numeric_available", "days_since_earnings_available", "sector_dummy__NA_"]
            missing_flags = [c for c in required_flags if c not in features.columns]
            if missing_flags:
                raise RuntimeError(f"Missing robust export flag columns: {missing_flags}")
            dead = [c for c in features.columns if c.startswith("earnings_quality_ratio")]
            if dead:
                raise RuntimeError(f"Dead earnings quality columns came back: {dead}")
            audit_path = bundle["root"] / "plan_signal_audit.json"
            audit = json.loads(audit_path.read_text()) if audit_path.exists() else {}
            overview = pd.DataFrame(
                [
                    {
                        "features_rows": len(features),
                        "feature_columns": features.shape[1],
                        "tickers": features["ticker"].nunique(),
                        "weekly_dates": features["date"].nunique(),
                        "date_min": str(features["date"].min().date()),
                        "date_max": str(features["date"].max().date()),
                        "walk_forward_windows": len(bundle["splits"]),
                    }
                ]
            )
            checks = pd.DataFrame(
                [
                    {
                        "target_last_column": features.columns[-1] == "target_weekly_return",
                        "blocking_signals": ", ".join(list(audit.get("blocking_signals") or [])),
                        "warning_signals": ", ".join(list(audit.get("warning_signals") or [])),
                    }
                ]
            )
            display(overview)
            display(checks)
            log_kv(
                "Validation passed",
                features_rows=len(features),
                feature_columns=features.shape[1],
                tickers=int(features["ticker"].nunique()),
                weekly_dates=int(features["date"].nunique()),
                windows=len(bundle["splits"]),
                blocking_signals="|".join(list(audit.get("blocking_signals") or [])) or "none",
                warning_signals="|".join(list(audit.get("warning_signals") or [])) or "none",
            )
            return audit


        export_dir = resolve_export_dir()
        bundle = load_bundle(export_dir)
        audit = validate_bundle(bundle)
        OUTPUT_ROOT = resolve_output_root(OUTPUT_ROOT)
        log_kv("Notebook bootstrap complete", export_dir=export_dir, selected_exp=SELECTED_EXP)
        """
    ),
    _md("## Modeling Helpers"),
    _code(
        """
        def build_feature_columns(bundle):
            feature_cols = [
                c for c in bundle["features"].columns
                if c not in {"date", "ticker", "target_weekly_return"}
                and pd.api.types.is_numeric_dtype(bundle["features"][c])
            ]
            metadata_cols = [c for c in EXTRA_METADATA_NUMERIC if c in bundle["metadata"].columns]
            output = dedupe(feature_cols + metadata_cols)
            log_kv(
                "Built feature column list",
                core_feature_columns=len(feature_cols),
                metadata_numeric_columns=len(metadata_cols),
                total_feature_columns=len(output),
            )
            return output


        def build_model_frame(bundle, feature_cols):
            cols = ["date", "ticker", "target_weekly_return", "plan_regime_label", "sector"] + [c for c in feature_cols if c in bundle["merged"].columns]
            frame = bundle["merged"][cols].copy()
            for col in feature_cols:
                if col in frame.columns:
                    frame[col] = pd.to_numeric(frame[col], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
            frame["target_weekly_return"] = pd.to_numeric(frame["target_weekly_return"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
            frame["plan_regime_label"] = frame["plan_regime_label"].fillna("Unknown").astype(str)
            frame["sector"] = frame["sector"].fillna("Unknown").astype(str)
            frame = frame.sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)
            log_frame("model_frame", frame)
            return frame


        def safe_spearman(x, y):
            if len(x) < 2 or len(y) < 2:
                return float("nan")
            if spearmanr is not None:
                try:
                    corr = spearmanr(x, y, nan_policy="omit").correlation
                    return float(corr) if corr is not None and np.isfinite(corr) else float("nan")
                except Exception:
                    pass
            corr = pd.Series(x).corr(pd.Series(y), method="spearman")
            return float(corr) if corr is not None and np.isfinite(corr) else float("nan")


        def compute_ic_series(frame, score_col="prediction", target_col="target_weekly_return", min_obs=8):
            rows = []
            for date_value, group in frame.groupby("date", sort=True):
                local = group[[score_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
                if len(local) < min_obs:
                    continue
                if local[score_col].nunique() < 2 or local[target_col].nunique() < 2:
                    continue
                corr = safe_spearman(local[score_col].to_numpy(dtype=float), local[target_col].to_numpy(dtype=float))
                if np.isfinite(corr):
                    rows.append({"date": pd.Timestamp(date_value).normalize(), "ic": float(corr)})
            if not rows:
                return pd.Series(dtype="float64")
            return pd.Series([row["ic"] for row in rows], index=pd.Index([row["date"] for row in rows], name="date"), dtype="float64").sort_index()


        def summarize_ic(series):
            clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
            if clean.empty:
                return {"n_dates": 0, "mean_ic": float("nan"), "ic_ir": float("nan"), "hit_rate": float("nan")}
            mean_ic = float(clean.mean())
            std = float(clean.std(ddof=1)) if len(clean) > 1 else float("nan")
            ic_ir = mean_ic / std if np.isfinite(std) and std > 0 else float("nan")
            hit_rate = float((clean >= 0).mean()) if mean_ic >= 0 else float((clean <= 0).mean())
            return {"n_dates": int(len(clean)), "mean_ic": mean_ic, "ic_ir": ic_ir, "hit_rate": hit_rate}


        def build_model(params):
            config = dict(DEFAULT_PARAMS)
            config.update(dict(params or {}))
            if CatBoostRegressor is not None:
                return CatBoostRegressor(
                    loss_function="RMSE",
                    eval_metric="RMSE",
                    random_seed=42,
                    verbose=False,
                    allow_writing_files=False,
                    depth=int(config["depth"]),
                    l2_leaf_reg=float(config["l2_leaf_reg"]),
                    min_data_in_leaf=int(config["min_data_in_leaf"]),
                    od_type="Iter",
                    od_wait=int(config["od_wait"]),
                    boosting_type=str(config["boosting_type"]),
                    learning_rate=float(config["learning_rate"]),
                    iterations=int(config["iterations"]),
                )
            if HistGradientBoostingRegressor is None:
                raise RuntimeError("No boosting backend is available.")
            return HistGradientBoostingRegressor(
                learning_rate=float(config["learning_rate"]),
                max_depth=int(config["depth"]),
                max_iter=int(config["iterations"]),
                random_state=42,
            )


        def split_train_valid(train_frame):
            dates = sorted(pd.to_datetime(train_frame["date"]).dropna().unique().tolist())
            if len(dates) < 12:
                return train_frame, None
            holdout = max(4, int(round(len(dates) * 0.15)))
            holdout = min(holdout, len(dates) - 4)
            if holdout <= 0:
                return train_frame, None
            cutoff = pd.Timestamp(dates[-holdout]).normalize()
            fit_frame = train_frame[train_frame["date"] < cutoff].copy()
            valid_frame = train_frame[train_frame["date"] >= cutoff].copy()
            if fit_frame.empty or valid_frame.empty:
                return train_frame, None
            return fit_frame, valid_frame


        def coerce_split_dates(split):
            return {
                "train_start": pd.Timestamp(split["train_start"]).normalize(),
                "train_end": pd.Timestamp(split["train_end"]).normalize(),
                "test_start": pd.Timestamp(split["test_start"]).normalize(),
                "test_end": pd.Timestamp(split["test_end"]).normalize(),
            }


        def run_walkforward(frame, splits, feature_cols, params, max_splits=None, output_dir=None):
            selected = list(splits[:max_splits] if max_splits else splits)
            log_kv(
                "Starting walk-forward run",
                selected_windows=len(selected),
                feature_count=len(feature_cols),
                output_dir=output_dir or "none",
                params=json_ready(params),
            )
            windows = []
            for split in selected:
                split_dates = coerce_split_dates(split)
                window_id = split.get("window_id", len(windows) + 1)
                log_kv(
                    "Window start",
                    window_id=window_id,
                    train_start=split_dates["train_start"].date(),
                    train_end=split_dates["train_end"].date(),
                    test_start=split_dates["test_start"].date(),
                    test_end=split_dates["test_end"].date(),
                )
                train_frame = frame[frame["date"].between(split_dates["train_start"], split_dates["train_end"])].copy()
                test_frame = frame[frame["date"].between(split_dates["test_start"], split_dates["test_end"])].copy()
                if len(train_frame) < 1000 or len(test_frame) < 200:
                    log_kv("Window skipped", window_id=window_id, reason="insufficient_rows", train_rows=len(train_frame), test_rows=len(test_frame))
                    windows.append({**dict(split), "error": "insufficient_rows"})
                    continue
                fit_frame, valid_frame = split_train_valid(train_frame)
                log_kv(
                    "Prepared train/valid split",
                    window_id=window_id,
                    train_rows=len(train_frame),
                    fit_rows=len(fit_frame),
                    valid_rows=len(valid_frame) if valid_frame is not None else 0,
                    test_rows=len(test_frame),
                )
                model = build_model(params)
                x_fit = fit_frame[feature_cols].to_numpy(dtype=np.float32)
                y_fit = fit_frame["target_weekly_return"].to_numpy(dtype=np.float32)
                x_train = train_frame[feature_cols].to_numpy(dtype=np.float32)
                x_test = test_frame[feature_cols].to_numpy(dtype=np.float32)
                log_kv("Model fit start", window_id=window_id, backend=type(model).__name__, x_fit_shape=x_fit.shape, x_test_shape=x_test.shape)
                if valid_frame is not None and CatBoostRegressor is not None and isinstance(model, CatBoostRegressor):
                    model.fit(
                        x_fit,
                        y_fit,
                        eval_set=(
                            valid_frame[feature_cols].to_numpy(dtype=np.float32),
                            valid_frame["target_weekly_return"].to_numpy(dtype=np.float32),
                        ),
                        use_best_model=True,
                    )
                else:
                    model.fit(x_fit, y_fit)
                log_kv("Model fit complete", window_id=window_id, backend=type(model).__name__)
                train_scored = train_frame[["date", "ticker", "target_weekly_return", "plan_regime_label"]].copy()
                test_scored = test_frame[["date", "ticker", "target_weekly_return", "plan_regime_label"]].copy()
                train_scored["prediction"] = model.predict(x_train)
                test_scored["prediction"] = model.predict(x_test)
                train_ic = summarize_ic(compute_ic_series(train_scored))
                test_ic = summarize_ic(compute_ic_series(test_scored))
                train_mean = float(train_ic["mean_ic"])
                test_mean = float(test_ic["mean_ic"])
                ratio = abs(train_mean) / max(abs(test_mean), 1e-6) if np.isfinite(train_mean) else float("nan")
                regime = test_scored["plan_regime_label"].mode(dropna=True).iloc[0] if not test_scored.empty else "Unknown"
                log_kv(
                    "Window complete",
                    window_id=window_id,
                    train_ic=round(train_mean, 6) if np.isfinite(train_mean) else "nan",
                    test_ic=round(test_mean, 6) if np.isfinite(test_mean) else "nan",
                    ratio=round(ratio, 6) if np.isfinite(ratio) else "nan",
                    hit_rate=round(float(test_ic["hit_rate"]), 6) if np.isfinite(float(test_ic["hit_rate"])) else "nan",
                    regime=regime,
                )
                windows.append(
                    {
                        **dict(split),
                        "train_rows": int(len(train_frame)),
                        "test_rows": int(len(test_frame)),
                        "train_ic": train_mean,
                        "test_ic": test_mean,
                        "train_test_ratio": ratio,
                        "hit_rate": float(test_ic["hit_rate"]),
                        "regime": str(regime),
                    }
                )
            clean = [row for row in windows if "error" not in row]
            summary = {
                "windows_completed": int(len(clean)),
                "mean_train_ic": float(pd.DataFrame(clean)["train_ic"].mean()) if clean else float("nan"),
                "mean_test_ic": float(pd.DataFrame(clean)["test_ic"].mean()) if clean else float("nan"),
                "ic_ir": float(pd.DataFrame(clean)["test_ic"].mean() / pd.DataFrame(clean)["test_ic"].std(ddof=1))
                if len(clean) > 1 and pd.DataFrame(clean)["test_ic"].std(ddof=1) > 0
                else float("nan"),
                "mean_train_test_ratio": float(pd.DataFrame(clean)["train_test_ratio"].mean()) if clean else float("nan"),
                "mean_hit_rate": float(pd.DataFrame(clean)["hit_rate"].mean()) if clean else float("nan"),
            }
            state = {"feature_columns": list(feature_cols), "feature_count": len(feature_cols), "params": dict(params), "windows": windows, "summary": summary}
            if output_dir:
                output_dir = Path(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
                write_table(output_dir / "window_metrics.csv", pd.DataFrame(windows))
                write_json(output_dir / "summary.json", state)
            log_kv(
                "Walk-forward run complete",
                completed_windows=summary["windows_completed"],
                mean_test_ic=summary["mean_test_ic"],
                mean_train_test_ratio=summary["mean_train_test_ratio"],
                mean_hit_rate=summary["mean_hit_rate"],
            )
            return state


        def best_candidate(rows):
            clean = [dict(row) for row in rows if np.isfinite(float(row.get("mean_test_ic", np.nan)))]
            if not clean:
                return None
            clean.sort(
                key=lambda row: (
                    float(row.get("mean_test_ic", float("-inf"))),
                    float(row.get("ic_ir", float("-inf"))),
                    -float(row.get("mean_train_test_ratio", float("inf"))),
                ),
                reverse=True,
            )
            return clean[0]


        def experiment_root(exp_id):
            root = OUTPUT_ROOT / f"{exp_id.lower().replace('-', '_')}_{VERSION_TAG}"
            root.mkdir(parents=True, exist_ok=True)
            return root


        def load_previous_summary(exp_id):
            path = experiment_root(exp_id) / "summary.json"
            if not path.exists():
                return None
            return json.loads(path.read_text(encoding="utf-8"))


        def resolve_base_params():
            params = dict(DEFAULT_PARAMS)
            for exp_id in ["EXP-12", "EXP-11", "EXP-10", "EXP-09"]:
                payload = load_previous_summary(exp_id) or {}
                best = dict((payload or {}).get("best_candidate") or {})
                values = dict(best.get("params") or {})
                if values:
                    params.update(values)
                    break
            params.update(dict(MANUAL_BASE_PARAMS or {}))
            return params


        def generate_anchored_weekly_splits(weekly_dates, train_weeks, test_weeks=26, step_weeks=26, anchor_start="2019-01-01"):
            dates = pd.Series(pd.to_datetime(list(weekly_dates), errors="coerce")).dropna().drop_duplicates().sort_values().tolist()
            dates = [pd.Timestamp(item).normalize() for item in dates if pd.Timestamp(item).normalize() >= pd.Timestamp(anchor_start).normalize()]
            if len(dates) < train_weeks + test_weeks:
                raise ValueError(f"insufficient_dates:{len(dates)}")
            windows = []
            for test_start_idx in range(train_weeks, len(dates) - test_weeks + 1, step_weeks):
                test_end_idx = test_start_idx + test_weeks - 1
                windows.append(
                    {
                        "window_id": len(windows) + 1,
                        "train_start": str(dates[0].date()),
                        "train_end": str(dates[test_start_idx - 1].date()),
                        "test_start": str(dates[test_start_idx].date()),
                        "test_end": str(dates[test_end_idx].date()),
                    }
                )
            return windows


        feature_columns = build_feature_columns(bundle)
        model_frame = build_model_frame(bundle, feature_columns)
        log_kv("Modeling helpers ready", feature_count=len(feature_columns), rows=len(model_frame))
        """
    ),
    _md("## Ratio Experiment Runner"),
    _code(
        """
        def run_ratio_experiment(exp_id):
            spec = dict(EXPERIMENT_GRID[exp_id])
            root = experiment_root(exp_id)
            artifacts = root / "artifacts"
            artifacts.mkdir(parents=True, exist_ok=True)
            candidates = []
            log_kv("Experiment start", exp_id=exp_id, experiment_title=spec["title"], root=root)

            def _run_candidate(label, params, splits):
                log_kv("Candidate start", exp_id=exp_id, label=label, split_count=len(splits), params=json_ready(params))
                state = run_walkforward(
                    model_frame,
                    splits,
                    feature_columns,
                    params=params,
                    max_splits=MAX_SPLITS,
                    output_dir=artifacts / label,
                )
                summary = dict(state["summary"])
                row = {
                    "label": label,
                    "params": dict(params),
                    "mean_test_ic": summary.get("mean_test_ic"),
                    "ic_ir": summary.get("ic_ir"),
                    "mean_train_test_ratio": summary.get("mean_train_test_ratio"),
                    "mean_hit_rate": summary.get("mean_hit_rate"),
                    "windows_completed": summary.get("windows_completed"),
                    "output_dir": str(artifacts / label),
                }
                log_kv(
                    "Candidate complete",
                    exp_id=exp_id,
                    label=label,
                    mean_test_ic=row["mean_test_ic"],
                    ic_ir=row["ic_ir"],
                    mean_train_test_ratio=row["mean_train_test_ratio"],
                    windows_completed=row["windows_completed"],
                )
                return row

            if exp_id == "EXP-09":
                base = dict(DEFAULT_PARAMS)
                base.update(dict(spec.get("base_params") or {}))
                for depth in list(spec.get("depth_grid") or []):
                    for od_wait in list(spec.get("early_stopping_rounds") or []):
                        params = {**base, "depth": int(depth), "od_wait": int(od_wait)}
                        candidates.append(_run_candidate(f"depth_{depth}_odwait_{od_wait}", params, bundle["splits"]))

            elif exp_id == "EXP-10":
                base = resolve_base_params()
                for value in list(spec.get("l2_leaf_reg_grid") or []):
                    params = {**base, "l2_leaf_reg": float(value)}
                    candidates.append(_run_candidate(f"l2_{str(value).replace('.', '_')}", params, bundle["splits"]))

            elif exp_id == "EXP-11":
                base = resolve_base_params()
                for value in list(spec.get("boosting_types") or []):
                    params = {**base, "boosting_type": str(value)}
                    candidates.append(_run_candidate(f"boosting_{str(value).lower()}", params, bundle["splits"]))

            elif exp_id == "EXP-12":
                base = resolve_base_params()
                weekly_dates = pd.to_datetime(bundle["features"]["date"], errors="coerce").dropna().sort_values().unique().tolist()
                for years in list(spec.get("train_window_years") or []):
                    splits = generate_anchored_weekly_splits(
                        weekly_dates,
                        train_weeks=int(years) * 52,
                        test_weeks=int(spec.get("test_window_weeks") or 26),
                        step_weeks=int(spec.get("step_weeks") or 26),
                    )
                    row = _run_candidate(f"window_{years}yr", base, splits)
                    row["params"] = {**row["params"], "train_window_years": int(years)}
                    row["split_count"] = len(splits)
                    candidates.append(row)

            table = pd.DataFrame(candidates)
            best = best_candidate(candidates)
            payload = {
                "exp_id": exp_id,
                "title": spec["title"],
                "feature_count": len(feature_columns),
                "candidate_count": len(candidates),
                "best_candidate": best,
                "candidates": candidates,
            }
            write_table(root / "candidate_table.csv", table)
            write_json(root / "summary.json", payload)
            notes = [
                "This fresh notebook is ratio-first and directly addresses the compendium's remaining gate.",
                "It uses the current merged export and does not import any external project code.",
            ]
            lines = [f"# {exp_id} - {spec['title']}", "", "Notes:"] + [f"- {note}" for note in notes]
            if best:
                lines.extend(["", "Best candidate:", f"- mean_test_ic: {best.get('mean_test_ic')}", f"- mean_train_test_ratio: {best.get('mean_train_test_ratio')}", f"- params: {best.get('params')}"])
            write_text(root / "economic_narrative.md", "\\n".join(lines))
            log_kv(
                "Experiment complete",
                exp_id=exp_id,
                candidate_count=len(candidates),
                best_label=(best or {}).get("label", "none"),
                best_mean_test_ic=(best or {}).get("mean_test_ic", "nan"),
            )
            return payload


        run_order = ["EXP-09", "EXP-10", "EXP-11", "EXP-12"]
        if RUN_FULL_CHAIN:
            selected_order = run_order[: run_order.index(SELECTED_EXP) + 1]
        else:
            selected_order = [SELECTED_EXP]

        results = {}
        for exp_id in selected_order:
            log_kv("Dispatching experiment", exp_id=exp_id, run_full_chain=RUN_FULL_CHAIN)
            payload = run_ratio_experiment(exp_id)
            results[exp_id] = payload
            display(Markdown(f"### {payload['exp_id']} - {payload['title']}"))
            display(pd.DataFrame(payload["candidates"]).sort_values("mean_test_ic", ascending=False, kind="mergesort"))
            if payload["best_candidate"]:
                display(pd.DataFrame([payload["best_candidate"]]))

        log_kv("Notebook run complete", selected_exp=SELECTED_EXP, executed=len(results))
        results[SELECTED_EXP]
        """
    ),
    _md("## Output Files"),
    _code(
        """
        out_root = experiment_root(SELECTED_EXP)
        files = sorted(str(path.relative_to(out_root)) for path in out_root.rglob("*") if path.is_file())
        log_kv("Output inventory", selected_exp=SELECTED_EXP, file_count=len(files), out_root=out_root)
        pd.DataFrame({"output_files": files})
        """
    ),
]


SECTOR_NOTEBOOK = [
    _md(
        """
        # NORTHSTAR V3 Sector + Regime Campaign Fresh Build

        This is a brand-new notebook for **EXP-13 to EXP-19** only.

        It is built around the current merged export and the compendium's next-stage agenda:
        - test sector specialization where structure is tighter
        - map anchor factor blind spots by event
        - quantify collapse on the highest-risk events
        - route across model families by regime

        Attach only:
        - `northstar-v3-feature-export`
        """
    ),
    _md("## Config"),
    _code(
        """
        from pathlib import Path

        SELECTED_EXP = "EXP-13"  # EXP-13 ... EXP-19
        MAX_SPLITS = None
        VERSION_TAG = "fresh_20260406"
        OUTPUT_ROOT = Path("/kaggle/working/northstar_sector_regime_campaign_fresh")

        EXPORT_DIR_OVERRIDE = None
        EXPORT_CANDIDATES = [
            "/kaggle/input/northstar-v3-feature-export",
            "/kaggle/input/northstar-v3-feature-export-1",
            "/kaggle/input/northstar-v3-feature-export-2",
        ]

        BEST_RATIO_PARAMS_OVERRIDE = {}
        SEQUENCE_BACKEND = "sklearn"  # use "torch" on Kaggle if you want actual LSTM/TCN training
        SEQUENCE_LENGTH = 8
        SEQUENCE_EPOCHS = 4
        SEQUENCE_BATCH_SIZE = 512
        SEQUENCE_MAX_TRAIN_SAMPLES = 30000

        EXPERIMENTS = {
            "EXP-13": {"title": "Financial Services Sector Model", "sector_name": "Financial Services"},
            "EXP-14": {"title": "IT Services Sector Model", "sector_name": "Information Technology"},
            "EXP-15": {"title": "Capital Goods Sector Model", "sector_name": "Capital Goods"},
            "EXP-16": {
                "title": "Sector Blend Model with Sector-Conditional Features",
                "sectors": [
                    "Financial Services",
                    "Information Technology",
                    "Capital Goods",
                    "Healthcare",
                    "Oil Gas & Consumable Fuels",
                    "Fast Moving Consumer Goods",
                ],
            },
            "EXP-17": {"title": "Factor IC Heat Map Across All Anchor Factors and Events"},
            "EXP-18": {"title": "Model Collapse Quantification on High-Risk Events", "top_n_high_risk_events": 5, "train_window_weeks": 104},
            "EXP-19": {"title": "Regime-Conditional Model Routing"},
        }

        ANCHOR_FACTORS = [
            "eps_sue_decay",
            "rev_sue_decay",
            "agreement_score_cs_z",
            "piotroski_fscore_cs_z",
            "bulk_net_pressure_21d_cs_z",
        ]

        SECTOR_CONDITIONAL_BASE = [
            "eps_sue_decay",
            "rev_sue_decay",
            "agreement_score_cs_z",
            "mom_20d_sector_rel_cs_z",
            "res_mom_20d_cs_z",
            "price_to_sma20_cs_z",
            "vol_z20_cs_z",
            "oil_sensitivity_score",
            "fx_sensitivity_score",
            "rate_sensitivity_score",
        ]

        EVENT_TABLE = [
            {"event_id": "E012", "event_name": "IL&FS Crisis & NBFC Contagion", "start_date": "2018-09-21", "end_date": "2019-03-31", "severity_score_1_10": 9, "model_collapse_risk": "EXTREME for small/mid-cap models - liquidity premium spikes to historic highs"},
            {"event_id": "E013", "event_name": "Yes Bank Crisis & Resolution", "start_date": "2020-03-05", "end_date": "2020-03-26", "severity_score_1_10": 6, "model_collapse_risk": "MEDIUM - isolated event but COVID conflation makes clean analysis difficult"},
            {"event_id": "E014", "event_name": "COVID-19 Crash - India", "start_date": "2020-02-19", "end_date": "2020-03-23", "severity_score_1_10": 10, "model_collapse_risk": "EXTREME - complete model failure; use as worst-case scenario benchmark"},
            {"event_id": "E015", "event_name": "COVID V-Recovery & Bull Market 2020-2021", "start_date": "2020-03-23", "end_date": "2021-10-18", "severity_score_1_10": 8, "model_collapse_risk": "HIGH at top - same parabolic pattern as 2007; crowding in quality growth"},
            {"event_id": "E016", "event_name": "2022 Global Rate Hike Bear Market", "start_date": "2021-10-18", "end_date": "2022-06-17", "severity_score_1_10": 7, "model_collapse_risk": "HIGH for growth/quality models; value rotation destroys long-only growth strategies"},
            {"event_id": "E017", "event_name": "Adani Group Crisis & Short-Seller Attack", "start_date": "2023-01-24", "end_date": "2023-03-15", "severity_score_1_10": 6, "model_collapse_risk": "HIGH for concentration-risk models; single-stock weight limits matter"},
            {"event_id": "E018", "event_name": "2023-2024 India Bull Market (Pre-Election)", "start_date": "2023-04-01", "end_date": "2024-09-26", "severity_score_1_10": 7, "model_collapse_risk": "MEDIUM - late-cycle concentration in PSU/defence themes"},
            {"event_id": "E019", "event_name": "2024 Election Shock & Recovery", "start_date": "2024-06-04", "end_date": "2024-06-24", "severity_score_1_10": 7, "model_collapse_risk": "HIGH at event date - binary outcome with high gap risk"},
            {"event_id": "E020", "event_name": "FII Selling Wave & INR Stress 2024-2025", "start_date": "2024-09-27", "end_date": "2025-02-28", "severity_score_1_10": 7, "model_collapse_risk": "HIGH for small/mid models - liquidity withdrawn from non-Nifty50 names"},
            {"event_id": "E021", "event_name": "Trump Tariff Global Shock 2025", "start_date": "2025-04-02", "end_date": "2025-04-09", "severity_score_1_10": 8, "model_collapse_risk": "HIGH - tariff pass-through uncertainty breaks IT earnings models"},
            {"event_id": "E022", "event_name": "India-Pakistan Military Escalation (Operation Sindoor)", "start_date": "2025-05-07", "end_date": "2025-05-12", "severity_score_1_10": 5, "model_collapse_risk": "LOW for macro models; HIGH for sector-specific event models"},
        ]

        print(f"Notebook configured for {SELECTED_EXP}")
        """
    ),
    _md("## Imports, Data Loading, And Contract Checks"),
    _code(
        """
        import json
        import time
        import warnings
        from datetime import datetime

        import numpy as np
        import pandas as pd
        from IPython.display import Markdown, display

        warnings.filterwarnings("ignore")

        try:
            from catboost import CatBoostRegressor
        except Exception:
            CatBoostRegressor = None

        try:
            from scipy.stats import spearmanr
        except Exception:
            spearmanr = None

        try:
            from sklearn.ensemble import HistGradientBoostingRegressor
        except Exception:
            HistGradientBoostingRegressor = None

        try:
            from sklearn.neural_network import MLPRegressor
        except Exception:
            MLPRegressor = None

        try:
            import torch
            from torch import nn
            from torch.utils.data import DataLoader, TensorDataset
        except Exception:
            torch = None
            nn = None
            DataLoader = None
            TensorDataset = None

        DEFAULT_PARAMS = {
            "depth": 4,
            "l2_leaf_reg": 15.0,
            "min_data_in_leaf": 40,
            "od_wait": 30,
            "boosting_type": "Ordered",
            "iterations": 400,
            "learning_rate": 0.05,
        }

        EXTRA_METADATA_NUMERIC = [
            "close",
            "volume",
            "international_revenue_proxy",
            "macro_linkage_score",
            "oil_sensitivity_score",
            "steel_sensitivity_score",
            "copper_sensitivity_score",
            "gold_sensitivity_score",
            "fx_sensitivity_score",
            "rate_sensitivity_score",
        ]

        LOG_PREFIX = "[sector-regime-fresh]"


        def log(message):
            stamp = datetime.now().strftime("%H:%M:%S")
            print(f"{LOG_PREFIX} {stamp} | {message}", flush=True)


        def log_kv(title, **kwargs):
            parts = ", ".join(f"{key}={value}" for key, value in kwargs.items())
            log(f"{title}: {parts}" if parts else title)


        def log_frame(name, frame):
            if frame is None:
                log(f"{name}: frame=None")
                return
            details = {
                "rows": len(frame),
                "cols": frame.shape[1],
            }
            if "date" in frame.columns and len(frame):
                details["date_min"] = str(pd.to_datetime(frame["date"], errors="coerce").min())
                details["date_max"] = str(pd.to_datetime(frame["date"], errors="coerce").max())
            if "ticker" in frame.columns:
                details["tickers"] = int(frame["ticker"].nunique())
            log_kv(name, **details)


        def resolve_output_root(preferred):
            preferred = Path(preferred)
            candidates = [
                preferred,
                Path("/kaggle/working") / preferred.name,
                Path.cwd() / preferred.name,
                Path("/tmp") / preferred.name,
            ]
            seen = set()
            for candidate in candidates:
                candidate = candidate.expanduser()
                key = str(candidate)
                if key in seen:
                    continue
                seen.add(key)
                try:
                    candidate.mkdir(parents=True, exist_ok=True)
                    log(f"Resolved output root at: {candidate}")
                    return candidate
                except Exception as exc:
                    log(f"Output root candidate failed: {candidate} ({exc})")
            raise RuntimeError(f"Unable to create output root from preferred path: {preferred}")


        def dedupe(items):
            seen = set()
            out = []
            for item in items:
                if item in seen:
                    continue
                seen.add(item)
                out.append(item)
            return out


        def slugify(value):
            clean = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or "")).strip("_")
            while "__" in clean:
                clean = clean.replace("__", "_")
            return clean or "unknown"


        def json_ready(value):
            if isinstance(value, dict):
                return {str(k): json_ready(v) for k, v in value.items()}
            if isinstance(value, (list, tuple)):
                return [json_ready(v) for v in value]
            if isinstance(value, Path):
                return str(value)
            if isinstance(value, pd.Timestamp):
                return value.isoformat()
            if isinstance(value, np.generic):
                return value.item()
            if isinstance(value, float) and not np.isfinite(value):
                return None
            return value


        def write_json(path, payload):
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(json_ready(payload), indent=2), encoding="utf-8")
            log(f"Wrote JSON: {path}")
            return path


        def write_text(path, text):
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(str(text).strip() + "\\n", encoding="utf-8")
            log(f"Wrote text: {path}")
            return path


        def write_table(path, frame):
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix.lower() == ".parquet":
                frame.to_parquet(path, index=False)
            else:
                frame.to_csv(path, index=False)
            log_kv("Wrote table", path=path, rows=len(frame), cols=frame.shape[1])
            return path


        def resolve_export_dir():
            required = [
                "northstar_features.parquet",
                "northstar_metadata.parquet",
                "northstar_regime_labels.parquet",
                "northstar_walk_forward_splits.json",
            ]

            def _candidate_dirs(root):
                if not root.exists() or not root.is_dir():
                    return []
                results = []
                if all((root / name).exists() for name in required):
                    results.append(root)
                try:
                    for match in root.rglob(required[0]):
                        parent = match.parent
                        if all((parent / name).exists() for name in required):
                            results.append(parent)
                except Exception:
                    pass
                deduped = []
                seen = set()
                for item in sorted(results, key=lambda p: (len(p.parts), str(p))):
                    key = str(item)
                    if key in seen:
                        continue
                    seen.add(key)
                    deduped.append(item)
                return deduped

            probes = []
            if EXPORT_DIR_OVERRIDE:
                probes.append(Path(EXPORT_DIR_OVERRIDE).expanduser())
            probes.extend(Path(item) for item in EXPORT_CANDIDATES)
            kaggle_root = Path("/kaggle/input")
            if kaggle_root.exists():
                probes.append(kaggle_root)
                probes.extend(sorted(path for path in kaggle_root.iterdir() if path.is_dir()))

            checked = []
            log("Resolving export dataset directory")
            for probe in probes:
                log(f"Checking probe: {probe}")
                if not probe.exists():
                    checked.append(str(probe))
                    log(f"Probe missing: {probe}")
                    continue
                for candidate in _candidate_dirs(probe):
                    log(f"Resolved export dataset at: {candidate}")
                    return candidate
                checked.append(str(probe))
                log(f"No complete export bundle found under: {probe}")

            raise FileNotFoundError(
                "Unable to resolve the export dataset recursively. Checked:\\n- "
                + "\\n- ".join(checked[:40])
            )


        def load_bundle(export_dir):
            root = Path(export_dir).expanduser().resolve()
            log(f"Loading export bundle from {root}")
            started = time.time()
            log("Reading northstar_features.parquet")
            features = pd.read_parquet(root / "northstar_features.parquet")
            log_frame("features", features)
            log("Reading northstar_metadata.parquet")
            metadata = pd.read_parquet(root / "northstar_metadata.parquet")
            log_frame("metadata", metadata)
            log("Reading northstar_regime_labels.parquet")
            regimes = pd.read_parquet(root / "northstar_regime_labels.parquet")
            log_frame("regimes", regimes)
            log("Reading northstar_walk_forward_splits.json")
            splits = json.loads((root / "northstar_walk_forward_splits.json").read_text(encoding="utf-8"))
            log_kv("Loaded splits", count=len(splits))

            for frame in [features, metadata, regimes]:
                frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()

            log("Merging features with metadata")
            merged = features.merge(metadata, on=["date", "ticker"], how="left", sort=False, suffixes=("", "_meta"))
            regime_cols = [c for c in ["date", "plan_regime_id", "plan_regime_label", "regime", "major_event_id"] if c in regimes.columns]
            if regime_cols:
                log_kv("Merging regime columns", columns=regime_cols)
                merged = merged.merge(regimes[regime_cols].drop_duplicates("date"), on="date", how="left", sort=False)
            for col in ["plan_regime_id", "plan_regime_label", "regime", "major_event_id"]:
                if col not in merged.columns:
                    left = f"{col}_x"
                    right = f"{col}_y"
                    if left in merged.columns or right in merged.columns:
                        merged[col] = merged.get(left)
                        if right in merged.columns:
                            merged[col] = merged[col].where(pd.Series(merged[col]).notna(), merged[right])
            merged["plan_regime_label"] = merged["plan_regime_label"].fillna("Unknown").astype(str)
            merged["sector"] = merged["sector"].fillna("Unknown").astype(str)
            log_frame("merged", merged)
            log_kv("Bundle load complete", seconds=round(time.time() - started, 2))
            return {
                "root": root,
                "features": features,
                "metadata": metadata,
                "regimes": regimes,
                "splits": list(splits),
                "merged": merged,
            }


        def validate_bundle(bundle):
            features = bundle["features"]
            log("Validating export contract")
            required = ["date", "ticker", "target_weekly_return"]
            missing = [c for c in required if c not in features.columns]
            if missing:
                raise RuntimeError(f"Missing required columns: {missing}")
            required_flags = ["pledge_pct_available", "rating_numeric_available", "days_since_earnings_available", "sector_dummy__NA_"]
            missing_flags = [c for c in required_flags if c not in features.columns]
            if missing_flags:
                raise RuntimeError(f"Missing robust export flag columns: {missing_flags}")
            dead = [c for c in features.columns if c.startswith("earnings_quality_ratio")]
            if dead:
                raise RuntimeError(f"Dead earnings quality columns came back: {dead}")
            overview = pd.DataFrame(
                [
                    {
                        "features_rows": len(features),
                        "feature_columns": features.shape[1],
                        "tickers": features["ticker"].nunique(),
                        "weekly_dates": features["date"].nunique(),
                        "date_min": str(features["date"].min().date()),
                        "date_max": str(features["date"].max().date()),
                        "walk_forward_windows": len(bundle["splits"]),
                    }
                ]
            )
            display(overview)
            log_kv(
                "Validation passed",
                features_rows=len(features),
                feature_columns=features.shape[1],
                tickers=int(features["ticker"].nunique()),
                weekly_dates=int(features["date"].nunique()),
                windows=len(bundle["splits"]),
            )


        export_dir = resolve_export_dir()
        bundle = load_bundle(export_dir)
        validate_bundle(bundle)
        OUTPUT_ROOT = resolve_output_root(OUTPUT_ROOT)
        log_kv("Notebook bootstrap complete", export_dir=export_dir, selected_exp=SELECTED_EXP)
        """
    ),
    _md("## Modeling And Experiment Helpers"),
    _code(
        """
        def build_full_feature_columns(bundle):
            feature_cols = [
                c for c in bundle["features"].columns
                if c not in {"date", "ticker", "target_weekly_return"}
                and pd.api.types.is_numeric_dtype(bundle["features"][c])
            ]
            metadata_cols = [c for c in EXTRA_METADATA_NUMERIC if c in bundle["metadata"].columns]
            output = dedupe(feature_cols + metadata_cols)
            log_kv(
                "Built full feature columns",
                core_feature_columns=len(feature_cols),
                metadata_numeric_columns=len(metadata_cols),
                total_feature_columns=len(output),
            )
            return output


        def build_sequence_feature_columns(bundle):
            candidates = dedupe(
                ANCHOR_FACTORS
                + SECTOR_CONDITIONAL_BASE
                + [
                    "ret_5d_cs_z",
                    "ret_20d_cs_z",
                    "mom_20d_cs_z",
                    "mom_60d_cs_z",
                    "inrusd_4w_return",
                    "crude_4w_return",
                    "gold_4w_return",
                    "copper_4w_return",
                    "steel_4w_return",
                    "coal_4w_return",
                    "dxy_4w_return",
                    "vix_india_4w",
                    "rbi_rate_chg",
                    "us_10y_4w",
                    "commodity_basket",
                    "val_quality_composite_zscore",
                ]
            )
            merged = bundle["merged"]
            output = [c for c in candidates if c in merged.columns and pd.api.types.is_numeric_dtype(merged[c])][:20]
            log_kv("Built sequence feature columns", candidate_pool=len(candidates), selected=len(output))
            return output


        def build_model_frame(bundle, feature_cols):
            cols = ["date", "ticker", "target_weekly_return", "plan_regime_label", "sector"] + [c for c in feature_cols if c in bundle["merged"].columns]
            frame = bundle["merged"][cols].copy()
            for col in feature_cols:
                if col in frame.columns:
                    frame[col] = pd.to_numeric(frame[col], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
            frame["target_weekly_return"] = pd.to_numeric(frame["target_weekly_return"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
            frame["plan_regime_label"] = frame["plan_regime_label"].fillna("Unknown").astype(str)
            frame["sector"] = frame["sector"].fillna("Unknown").astype(str)
            frame = frame.sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)
            log_frame("model_frame", frame)
            return frame


        def safe_spearman(x, y):
            if len(x) < 2 or len(y) < 2:
                return float("nan")
            if spearmanr is not None:
                try:
                    corr = spearmanr(x, y, nan_policy="omit").correlation
                    return float(corr) if corr is not None and np.isfinite(corr) else float("nan")
                except Exception:
                    pass
            corr = pd.Series(x).corr(pd.Series(y), method="spearman")
            return float(corr) if corr is not None and np.isfinite(corr) else float("nan")


        def compute_ic_series(frame, score_col="prediction", target_col="target_weekly_return", min_obs=8):
            rows = []
            for date_value, group in frame.groupby("date", sort=True):
                local = group[[score_col, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
                if len(local) < min_obs:
                    continue
                if local[score_col].nunique() < 2 or local[target_col].nunique() < 2:
                    continue
                corr = safe_spearman(local[score_col].to_numpy(dtype=float), local[target_col].to_numpy(dtype=float))
                if np.isfinite(corr):
                    rows.append({"date": pd.Timestamp(date_value).normalize(), "ic": float(corr)})
            if not rows:
                return pd.Series(dtype="float64")
            return pd.Series([row["ic"] for row in rows], index=pd.Index([row["date"] for row in rows], name="date"), dtype="float64").sort_index()


        def summarize_ic(series):
            clean = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
            if clean.empty:
                return {"n_dates": 0, "mean_ic": float("nan"), "ic_ir": float("nan"), "hit_rate": float("nan")}
            mean_ic = float(clean.mean())
            std = float(clean.std(ddof=1)) if len(clean) > 1 else float("nan")
            ic_ir = mean_ic / std if np.isfinite(std) and std > 0 else float("nan")
            hit_rate = float((clean >= 0).mean()) if mean_ic >= 0 else float((clean <= 0).mean())
            return {"n_dates": int(len(clean)), "mean_ic": mean_ic, "ic_ir": ic_ir, "hit_rate": hit_rate}


        def build_model(params):
            config = dict(DEFAULT_PARAMS)
            config.update(dict(params or {}))
            if CatBoostRegressor is not None:
                return CatBoostRegressor(
                    loss_function="RMSE",
                    eval_metric="RMSE",
                    random_seed=42,
                    verbose=False,
                    allow_writing_files=False,
                    depth=int(config["depth"]),
                    l2_leaf_reg=float(config["l2_leaf_reg"]),
                    min_data_in_leaf=int(config["min_data_in_leaf"]),
                    od_type="Iter",
                    od_wait=int(config["od_wait"]),
                    boosting_type=str(config["boosting_type"]),
                    learning_rate=float(config["learning_rate"]),
                    iterations=int(config["iterations"]),
                )
            if HistGradientBoostingRegressor is None:
                raise RuntimeError("No boosting backend is available.")
            return HistGradientBoostingRegressor(
                learning_rate=float(config["learning_rate"]),
                max_depth=int(config["depth"]),
                max_iter=int(config["iterations"]),
                random_state=42,
            )


        def split_train_valid(train_frame):
            dates = sorted(pd.to_datetime(train_frame["date"]).dropna().unique().tolist())
            if len(dates) < 12:
                return train_frame, None
            holdout = max(4, int(round(len(dates) * 0.15)))
            holdout = min(holdout, len(dates) - 4)
            if holdout <= 0:
                return train_frame, None
            cutoff = pd.Timestamp(dates[-holdout]).normalize()
            fit_frame = train_frame[train_frame["date"] < cutoff].copy()
            valid_frame = train_frame[train_frame["date"] >= cutoff].copy()
            if fit_frame.empty or valid_frame.empty:
                return train_frame, None
            return fit_frame, valid_frame


        def coerce_split_dates(split):
            return {
                "train_start": pd.Timestamp(split["train_start"]).normalize(),
                "train_end": pd.Timestamp(split["train_end"]).normalize(),
                "test_start": pd.Timestamp(split["test_start"]).normalize(),
                "test_end": pd.Timestamp(split["test_end"]).normalize(),
            }


        def run_walkforward(frame, splits, feature_cols, params, max_splits=None, output_dir=None):
            selected = list(splits[:max_splits] if max_splits else splits)
            log_kv(
                "Starting walk-forward run",
                selected_windows=len(selected),
                feature_count=len(feature_cols),
                output_dir=output_dir or "none",
                params=json_ready(params),
            )
            windows = []
            for split in selected:
                split_dates = coerce_split_dates(split)
                window_id = split.get("window_id", len(windows) + 1)
                log_kv(
                    "Window start",
                    window_id=window_id,
                    train_start=split_dates["train_start"].date(),
                    train_end=split_dates["train_end"].date(),
                    test_start=split_dates["test_start"].date(),
                    test_end=split_dates["test_end"].date(),
                )
                train_frame = frame[frame["date"].between(split_dates["train_start"], split_dates["train_end"])].copy()
                test_frame = frame[frame["date"].between(split_dates["test_start"], split_dates["test_end"])].copy()
                if len(train_frame) < 1000 or len(test_frame) < 200:
                    log_kv("Window skipped", window_id=window_id, reason="insufficient_rows", train_rows=len(train_frame), test_rows=len(test_frame))
                    windows.append({**dict(split), "error": "insufficient_rows"})
                    continue
                fit_frame, valid_frame = split_train_valid(train_frame)
                log_kv(
                    "Prepared train/valid split",
                    window_id=window_id,
                    train_rows=len(train_frame),
                    fit_rows=len(fit_frame),
                    valid_rows=len(valid_frame) if valid_frame is not None else 0,
                    test_rows=len(test_frame),
                )
                model = build_model(params)
                x_fit = fit_frame[feature_cols].to_numpy(dtype=np.float32)
                y_fit = fit_frame["target_weekly_return"].to_numpy(dtype=np.float32)
                x_train = train_frame[feature_cols].to_numpy(dtype=np.float32)
                x_test = test_frame[feature_cols].to_numpy(dtype=np.float32)
                log_kv("Model fit start", window_id=window_id, backend=type(model).__name__, x_fit_shape=x_fit.shape, x_test_shape=x_test.shape)
                if valid_frame is not None and CatBoostRegressor is not None and isinstance(model, CatBoostRegressor):
                    model.fit(
                        x_fit,
                        y_fit,
                        eval_set=(
                            valid_frame[feature_cols].to_numpy(dtype=np.float32),
                            valid_frame["target_weekly_return"].to_numpy(dtype=np.float32),
                        ),
                        use_best_model=True,
                    )
                else:
                    model.fit(x_fit, y_fit)
                log_kv("Model fit complete", window_id=window_id, backend=type(model).__name__)
                train_scored = train_frame[["date", "ticker", "target_weekly_return", "plan_regime_label"]].copy()
                test_scored = test_frame[["date", "ticker", "target_weekly_return", "plan_regime_label"]].copy()
                train_scored["prediction"] = model.predict(x_train)
                test_scored["prediction"] = model.predict(x_test)
                train_ic = summarize_ic(compute_ic_series(train_scored))
                test_ic = summarize_ic(compute_ic_series(test_scored))
                train_mean = float(train_ic["mean_ic"])
                test_mean = float(test_ic["mean_ic"])
                ratio = abs(train_mean) / max(abs(test_mean), 1e-6) if np.isfinite(train_mean) else float("nan")
                regime = test_scored["plan_regime_label"].mode(dropna=True).iloc[0] if not test_scored.empty else "Unknown"
                log_kv(
                    "Window complete",
                    window_id=window_id,
                    train_ic=round(train_mean, 6) if np.isfinite(train_mean) else "nan",
                    test_ic=round(test_mean, 6) if np.isfinite(test_mean) else "nan",
                    ratio=round(ratio, 6) if np.isfinite(ratio) else "nan",
                    hit_rate=round(float(test_ic["hit_rate"]), 6) if np.isfinite(float(test_ic["hit_rate"])) else "nan",
                    regime=regime,
                )
                windows.append(
                    {
                        **dict(split),
                        "train_rows": int(len(train_frame)),
                        "test_rows": int(len(test_frame)),
                        "train_ic": train_mean,
                        "test_ic": test_mean,
                        "train_test_ratio": ratio,
                        "hit_rate": float(test_ic["hit_rate"]),
                        "regime": str(regime),
                    }
                )
            clean = [row for row in windows if "error" not in row]
            summary = {
                "windows_completed": int(len(clean)),
                "mean_train_ic": float(pd.DataFrame(clean)["train_ic"].mean()) if clean else float("nan"),
                "mean_test_ic": float(pd.DataFrame(clean)["test_ic"].mean()) if clean else float("nan"),
                "ic_ir": float(pd.DataFrame(clean)["test_ic"].mean() / pd.DataFrame(clean)["test_ic"].std(ddof=1))
                if len(clean) > 1 and pd.DataFrame(clean)["test_ic"].std(ddof=1) > 0
                else float("nan"),
                "mean_train_test_ratio": float(pd.DataFrame(clean)["train_test_ratio"].mean()) if clean else float("nan"),
                "mean_hit_rate": float(pd.DataFrame(clean)["hit_rate"].mean()) if clean else float("nan"),
            }
            state = {"feature_columns": list(feature_cols), "feature_count": len(feature_cols), "params": dict(params), "windows": windows, "summary": summary}
            if output_dir:
                output_dir = Path(output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
                write_table(output_dir / "window_metrics.csv", pd.DataFrame(windows))
                write_json(output_dir / "summary.json", state)
            log_kv(
                "Walk-forward run complete",
                completed_windows=summary["windows_completed"],
                mean_test_ic=summary["mean_test_ic"],
                mean_train_test_ratio=summary["mean_train_test_ratio"],
                mean_hit_rate=summary["mean_hit_rate"],
            )
            return state


        def experiment_root(exp_id):
            root = OUTPUT_ROOT / f"{exp_id.lower().replace('-', '_')}_{VERSION_TAG}"
            root.mkdir(parents=True, exist_ok=True)
            return root


        def load_ratio_summary(exp_id):
            path = OUTPUT_ROOT / f"{exp_id.lower().replace('-', '_')}_{VERSION_TAG}" / "summary.json"
            if not path.exists():
                return None
            return json.loads(path.read_text(encoding="utf-8"))


        def resolve_base_params():
            params = dict(DEFAULT_PARAMS)
            for exp_id in ["EXP-12", "EXP-11", "EXP-10", "EXP-09"]:
                payload = load_ratio_summary(exp_id) or {}
                best = dict((payload or {}).get("best_candidate") or {})
                values = dict(best.get("params") or {})
                if values:
                    params.update(values)
                    break
            params.update(dict(BEST_RATIO_PARAMS_OVERRIDE or {}))
            return params


        def resolve_sector_tickers(bundle, sector_name):
            metadata = bundle["metadata"]
            tickers = (
                metadata.loc[metadata["sector"].astype(str) == str(sector_name), "ticker"]
                .dropna().astype(str).drop_duplicates().sort_values().tolist()
            )
            log_kv("Resolved sector tickers", sector_name=sector_name, ticker_count=len(tickers))
            return tickers


        def augment_sector_conditionals(frame, sectors):
            augmented = frame.copy()
            added = []
            for sector in sectors:
                tag = slugify(sector)
                flag = f"sector_is__{tag}"
                augmented[flag] = (augmented["sector"].astype(str) == str(sector)).astype("float32")
                added.append(flag)
                for feature in SECTOR_CONDITIONAL_BASE:
                    if feature not in augmented.columns:
                        continue
                    name = f"{feature}__x__{tag}"
                    augmented[name] = (pd.to_numeric(augmented[feature], errors="coerce").fillna(0.0) * augmented[flag]).astype("float32")
                    added.append(name)
            log_kv("Built sector-conditional features", sector_count=len(sectors), added_feature_count=len(added))
            return augmented, added


        def build_event_split(bundle, start_date, end_date, train_weeks=104):
            weekly_dates = pd.to_datetime(bundle["features"]["date"], errors="coerce").dropna().drop_duplicates().sort_values().tolist()
            weekly_dates = [pd.Timestamp(item).normalize() for item in weekly_dates]
            start = pd.Timestamp(start_date).normalize()
            end = pd.Timestamp(end_date).normalize()
            test_dates = [item for item in weekly_dates if start <= item <= end]
            if len(test_dates) < 2:
                log_kv("Event split unavailable", start_date=start, end_date=end, reason="insufficient_test_dates")
                return []
            first_idx = weekly_dates.index(test_dates[0])
            train_end_idx = first_idx - 1
            train_start_idx = max(0, train_end_idx - int(train_weeks) + 1)
            if train_end_idx <= train_start_idx:
                log_kv("Event split unavailable", start_date=start, end_date=end, reason="insufficient_train_history")
                return []
            splits = [
                {
                    "window_id": 1,
                    "train_start": str(weekly_dates[train_start_idx].date()),
                    "train_end": str(weekly_dates[train_end_idx].date()),
                    "test_start": str(test_dates[0].date()),
                    "test_end": str(test_dates[-1].date()),
                }
            ]
            log_kv("Built event split", start_date=start.date(), end_date=end.date(), train_weeks=train_weeks, split_count=len(splits))
            return splits


        def select_high_risk_events(top_n):
            events = pd.DataFrame(EVENT_TABLE).copy()
            events["start_date"] = pd.to_datetime(events["start_date"], errors="coerce")
            events["end_date"] = pd.to_datetime(events["end_date"], errors="coerce")
            def risk_score(row):
                label = str(row.get("model_collapse_risk") or "").upper()
                base = 4 if "EXTREME" in label else 3 if "HIGH" in label else 2 if "MEDIUM" in label else 1 if "LOW" in label else 0
                return base + float(row.get("severity_score_1_10") or 0) / 10.0
            events["risk_score"] = events.apply(risk_score, axis=1)
            selected = events.sort_values(["risk_score", "severity_score_1_10"], ascending=[False, False], kind="mergesort").head(int(top_n))
            log_kv("Selected high-risk events", requested=top_n, selected=len(selected))
            return selected


        def build_group_cache(frame, feature_cols):
            cache = {}
            for ticker, group in frame.groupby("ticker", sort=False):
                ordered = group.sort_values("date", kind="mergesort").reset_index(drop=True)
                cache[str(ticker)] = {
                    "dates": pd.to_datetime(ordered["date"]).to_numpy(),
                    "target": ordered["target_weekly_return"].to_numpy(dtype=np.float32),
                    "regime": ordered["plan_regime_label"].astype(str).to_numpy(),
                    "values": ordered[feature_cols].to_numpy(dtype=np.float32),
                }
            log_kv("Built sequence cache", ticker_groups=len(cache), feature_count=len(feature_cols))
            return cache


        def sequence_samples(cache, split):
            split_dates = coerce_split_dates(split)
            train_x, train_y, train_dates = [], [], []
            test_x, test_y, test_dates, test_regimes = [], [], [], []
            for payload in cache.values():
                dates = payload["dates"]
                values = payload["values"]
                target = payload["target"]
                regimes = payload["regime"]
                for idx in range(int(SEQUENCE_LENGTH) - 1, len(dates)):
                    date_value = pd.Timestamp(dates[idx]).normalize()
                    sample = values[idx - int(SEQUENCE_LENGTH) + 1 : idx + 1]
                    if split_dates["train_start"] <= date_value <= split_dates["train_end"]:
                        train_x.append(sample)
                        train_y.append(float(target[idx]))
                        train_dates.append(date_value)
                    elif split_dates["test_start"] <= date_value <= split_dates["test_end"]:
                        test_x.append(sample)
                        test_y.append(float(target[idx]))
                        test_dates.append(date_value)
                        test_regimes.append(str(regimes[idx]))
            if len(train_x) > int(SEQUENCE_MAX_TRAIN_SAMPLES):
                rng = np.random.default_rng(42)
                keep = np.sort(rng.choice(len(train_x), size=int(SEQUENCE_MAX_TRAIN_SAMPLES), replace=False))
                train_x = [train_x[i] for i in keep]
                train_y = [train_y[i] for i in keep]
                train_dates = [train_dates[i] for i in keep]
            payload = {
                "train_x": np.asarray(train_x, dtype=np.float32),
                "train_y": np.asarray(train_y, dtype=np.float32),
                "train_dates": np.asarray(train_dates, dtype="datetime64[ns]"),
                "test_x": np.asarray(test_x, dtype=np.float32),
                "test_y": np.asarray(test_y, dtype=np.float32),
                "test_dates": np.asarray(test_dates, dtype="datetime64[ns]"),
                "test_regimes": np.asarray(test_regimes, dtype=object),
            }
            log_kv(
                "Built sequence samples",
                window_id=split.get("window_id", "na"),
                train_rows=len(payload["train_x"]),
                test_rows=len(payload["test_x"]),
            )
            return payload


        class LSTMRegressor(nn.Module):
            def __init__(self, feature_count, hidden_size=48):
                super().__init__()
                self.lstm = nn.LSTM(input_size=feature_count, hidden_size=hidden_size, batch_first=True)
                self.head = nn.Linear(hidden_size, 1)

            def forward(self, x):
                out, _ = self.lstm(x)
                return self.head(out[:, -1, :]).squeeze(-1)


        class TCNRegressor(nn.Module):
            def __init__(self, feature_count, hidden_size=48):
                super().__init__()
                self.net = nn.Sequential(
                    nn.Conv1d(feature_count, hidden_size, kernel_size=3, padding=1),
                    nn.ReLU(),
                    nn.Conv1d(hidden_size, hidden_size, kernel_size=3, padding=1),
                    nn.ReLU(),
                    nn.AdaptiveAvgPool1d(1),
                )
                self.head = nn.Linear(hidden_size, 1)

            def forward(self, x):
                hidden = self.net(x.transpose(1, 2)).squeeze(-1)
                return self.head(hidden).squeeze(-1)


        def fit_sequence_model(name, train_x, train_y, feature_count):
            backend = str(SEQUENCE_BACKEND).strip().lower()
            log_kv("Sequence fit start", model=name, requested_backend=backend, train_rows=len(train_x), feature_count=feature_count)
            if backend == "torch" and torch is not None and nn is not None and DataLoader is not None and TensorDataset is not None:
                device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                split_idx = min(max(int(len(train_x) * 0.9), 256), len(train_x) - 128)
                fit_x, valid_x = train_x[:split_idx], train_x[split_idx:]
                fit_y, valid_y = train_y[:split_idx], train_y[split_idx:]
                mean = fit_x.mean(axis=(0, 1), keepdims=True)
                std = fit_x.std(axis=(0, 1), keepdims=True)
                std = np.where(std < 1e-6, 1.0, std)
                fit_x = (fit_x - mean) / std
                valid_x = (valid_x - mean) / std
                model = LSTMRegressor(feature_count) if name == "LSTM" else TCNRegressor(feature_count)
                model = model.to(device)
                optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
                loss_fn = nn.MSELoss()
                loader = DataLoader(TensorDataset(torch.from_numpy(fit_x), torch.from_numpy(fit_y)), batch_size=int(SEQUENCE_BATCH_SIZE), shuffle=True)
                valid_inputs = torch.from_numpy(valid_x).to(device)
                valid_targets = torch.from_numpy(valid_y).to(device)
                best_loss = float("inf")
                best_state = None
                patience = 0
                for _ in range(max(1, int(SEQUENCE_EPOCHS))):
                    model.train()
                    for batch_x, batch_y in loader:
                        batch_x = batch_x.to(device)
                        batch_y = batch_y.to(device)
                        optimizer.zero_grad(set_to_none=True)
                        loss = loss_fn(model(batch_x), batch_y)
                        loss.backward()
                        optimizer.step()
                    model.eval()
                    with torch.no_grad():
                        valid_loss = float(loss_fn(model(valid_inputs), valid_targets).item())
                    if valid_loss < best_loss:
                        best_loss = valid_loss
                        best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
                        patience = 0
                    else:
                        patience += 1
                        if patience >= 2:
                            break
                if best_state is not None:
                    model.load_state_dict(best_state)
                log_kv("Sequence fit complete", model=name, backend="torch", best_loss=best_loss, device=device)
                return model, mean.astype(np.float32), std.astype(np.float32), "torch"

            flat = train_x.reshape(len(train_x), -1).astype(np.float32, copy=False)
            mean = flat.mean(axis=0, keepdims=True)
            std = flat.std(axis=0, keepdims=True)
            std = np.where(std < 1e-6, 1.0, std)
            scaled = (flat - mean) / std
            if name == "LSTM" and MLPRegressor is not None:
                model = MLPRegressor(
                    hidden_layer_sizes=(96, 48),
                    activation="relu",
                    learning_rate_init=1e-3,
                    max_iter=max(40, int(SEQUENCE_EPOCHS) * 20),
                    random_state=42,
                    early_stopping=True,
                    validation_fraction=0.1,
                )
            else:
                model = HistGradientBoostingRegressor(
                    learning_rate=0.05,
                    max_depth=4,
                    max_iter=max(120, int(SEQUENCE_EPOCHS) * 40),
                    random_state=42,
                )
            model.fit(scaled, train_y.astype(np.float32, copy=False))
            log_kv("Sequence fit complete", model=name, backend="sklearn", train_rows=len(train_x))
            return model, mean.astype(np.float32), std.astype(np.float32), "sklearn"


        def predict_sequence_model(model, x, mean, std):
            if hasattr(model, "predict") and not hasattr(model, "parameters"):
                flat = x.reshape(len(x), -1).astype(np.float32, copy=False)
                scaled = (flat - mean) / std
                return np.asarray(model.predict(scaled), dtype=np.float32)
            scaled = ((x.astype(np.float32, copy=False) - mean) / std).astype(np.float32, copy=False)
            device = next(model.parameters()).device
            loader = DataLoader(torch.from_numpy(scaled), batch_size=int(SEQUENCE_BATCH_SIZE), shuffle=False)
            preds = []
            model.eval()
            with torch.no_grad():
                for batch in loader:
                    if isinstance(batch, (list, tuple)):
                        batch = batch[0]
                    preds.append(model(batch.to(device)).detach().cpu().numpy())
            return np.concatenate(preds) if preds else np.zeros(len(x), dtype=np.float32)


        def run_sequence_walkforward(frame, feature_cols, model_name):
            cache = build_group_cache(frame, feature_cols)
            selected = list(bundle["splits"][:MAX_SPLITS] if MAX_SPLITS else bundle["splits"])
            windows = []
            backend_used = str(SEQUENCE_BACKEND)
            log_kv("Starting sequence walk-forward run", model=model_name, selected_windows=len(selected), feature_count=len(feature_cols))
            for split in selected:
                window_id = split.get("window_id", len(windows) + 1)
                log_kv("Sequence window start", model=model_name, window_id=window_id)
                samples = sequence_samples(cache, split)
                if len(samples["train_x"]) < 512 or len(samples["test_x"]) < 128:
                    log_kv("Sequence window skipped", model=model_name, window_id=window_id, reason="insufficient_sequence_rows", train_rows=len(samples["train_x"]), test_rows=len(samples["test_x"]))
                    windows.append({**dict(split), "error": "insufficient_sequence_rows"})
                    continue
                model, mean, std, backend_used = fit_sequence_model(model_name, samples["train_x"], samples["train_y"], len(feature_cols))
                train_pred = predict_sequence_model(model, samples["train_x"], mean, std)
                test_pred = predict_sequence_model(model, samples["test_x"], mean, std)
                train_scored = pd.DataFrame({"date": pd.to_datetime(samples["train_dates"]), "target_weekly_return": samples["train_y"], "prediction": train_pred})
                test_scored = pd.DataFrame({"date": pd.to_datetime(samples["test_dates"]), "target_weekly_return": samples["test_y"], "prediction": test_pred, "plan_regime_label": samples["test_regimes"]})
                train_ic = summarize_ic(compute_ic_series(train_scored))
                test_ic = summarize_ic(compute_ic_series(test_scored))
                train_mean = float(train_ic["mean_ic"])
                test_mean = float(test_ic["mean_ic"])
                ratio = abs(train_mean) / max(abs(test_mean), 1e-6) if np.isfinite(train_mean) else float("nan")
                regime = test_scored["plan_regime_label"].mode(dropna=True).iloc[0] if not test_scored.empty else "Unknown"
                log_kv(
                    "Sequence window complete",
                    model=model_name,
                    window_id=window_id,
                    backend=backend_used,
                    train_ic=round(train_mean, 6) if np.isfinite(train_mean) else "nan",
                    test_ic=round(test_mean, 6) if np.isfinite(test_mean) else "nan",
                    ratio=round(ratio, 6) if np.isfinite(ratio) else "nan",
                    regime=regime,
                )
                windows.append(
                    {
                        **dict(split),
                        "train_rows": int(len(samples["train_x"])),
                        "test_rows": int(len(samples["test_x"])),
                        "train_ic": train_mean,
                        "test_ic": test_mean,
                        "train_test_ratio": ratio,
                        "hit_rate": float(test_ic["hit_rate"]),
                        "regime": str(regime),
                    }
                )
            clean = [row for row in windows if "error" not in row]
            summary = {
                "backend": backend_used,
                "windows_completed": int(len(clean)),
                "mean_train_ic": float(pd.DataFrame(clean)["train_ic"].mean()) if clean else float("nan"),
                "mean_test_ic": float(pd.DataFrame(clean)["test_ic"].mean()) if clean else float("nan"),
                "ic_ir": float(pd.DataFrame(clean)["test_ic"].mean() / pd.DataFrame(clean)["test_ic"].std(ddof=1))
                if len(clean) > 1 and pd.DataFrame(clean)["test_ic"].std(ddof=1) > 0
                else float("nan"),
                "mean_train_test_ratio": float(pd.DataFrame(clean)["train_test_ratio"].mean()) if clean else float("nan"),
                "mean_hit_rate": float(pd.DataFrame(clean)["hit_rate"].mean()) if clean else float("nan"),
            }
            log_kv(
                "Sequence walk-forward complete",
                model=model_name,
                backend=backend_used,
                completed_windows=summary["windows_completed"],
                mean_test_ic=summary["mean_test_ic"],
                mean_train_test_ratio=summary["mean_train_test_ratio"],
            )
            return {"model": model_name, "feature_count": len(feature_cols), "feature_columns": feature_cols, "windows": windows, "summary": summary}


        def build_routing_table(model_rows):
            frame = pd.DataFrame(model_rows)
            if frame.empty:
                return pd.DataFrame()
            output = []
            for regime_name, group in frame.groupby("regime", sort=True):
                row = group.sort_values(["mean_test_ic", "mean_ratio"], ascending=[False, True], kind="mergesort").iloc[0]
                output.append(
                    {
                        "regime": regime_name,
                        "selected_model": row["model"],
                        "selected_mean_test_ic": float(row["mean_test_ic"]),
                        "selected_mean_ratio": float(row["mean_ratio"]),
                        "n_windows": int(row["n_windows"]),
                    }
                )
            return pd.DataFrame(output)


        full_feature_columns = build_full_feature_columns(bundle)
        full_frame = build_model_frame(bundle, full_feature_columns)
        sequence_feature_columns = build_sequence_feature_columns(bundle)
        log_kv("Modeling helpers ready", full_feature_count=len(full_feature_columns), sequence_feature_count=len(sequence_feature_columns), rows=len(full_frame))
        """
    ),
    _md("## Sector + Regime Experiment Runner"),
    _code(
        """
        def run_selected_experiment(exp_id):
            spec = dict(EXPERIMENTS[exp_id])
            root = experiment_root(exp_id)
            artifacts = root / "artifacts"
            artifacts.mkdir(parents=True, exist_ok=True)
            base_params = dict(DEFAULT_PARAMS)
            base_params.update(dict(BEST_RATIO_PARAMS_OVERRIDE or {}))
            log_kv("Experiment start", exp_id=exp_id, experiment_title=spec["title"], root=root)

            if exp_id in {"EXP-13", "EXP-14", "EXP-15"}:
                sector_name = spec["sector_name"]
                tickers = resolve_sector_tickers(bundle, sector_name)
                subset = full_frame[full_frame["ticker"].isin(tickers)].copy()
                log_frame(f"{exp_id}_subset", subset)
                state = run_walkforward(subset, bundle["splits"], full_feature_columns, base_params, max_splits=MAX_SPLITS, output_dir=artifacts / "catboost")
                payload = {
                    "exp_id": exp_id,
                    "title": spec["title"],
                    "sector_name": sector_name,
                    "n_tickers": len(tickers),
                    "tickers": tickers,
                    "feature_count": len(full_feature_columns),
                    "catboost_summary": state["summary"],
                }
                write_json(root / "sector_subset_manifest.json", payload)
                write_json(root / "summary.json", payload)
                write_text(root / "economic_narrative.md", f"# {exp_id} - {spec['title']}\\n\\n- sector_name: {sector_name}\\n- n_tickers: {len(tickers)}\\n- mean_test_ic: {state['summary'].get('mean_test_ic')}\\n- mean_train_test_ratio: {state['summary'].get('mean_train_test_ratio')}")
                log_kv("Experiment complete", exp_id=exp_id, sector_name=sector_name, n_tickers=len(tickers), mean_test_ic=state["summary"].get("mean_test_ic"))
                return payload

            if exp_id == "EXP-16":
                augmented, added_features = augment_sector_conditionals(full_frame, spec["sectors"])
                all_feature_columns = dedupe(full_feature_columns + [c for c in added_features if c in augmented.columns])
                log_frame(f"{exp_id}_augmented", augmented)
                state = run_walkforward(augmented, bundle["splits"], all_feature_columns, base_params, max_splits=MAX_SPLITS, output_dir=artifacts / "catboost")
                payload = {
                    "exp_id": exp_id,
                    "title": spec["title"],
                    "feature_count": len(all_feature_columns),
                    "added_feature_count": len(added_features),
                    "added_features": added_features,
                    "catboost_summary": state["summary"],
                }
                write_json(root / "augmented_feature_manifest.json", payload)
                write_json(root / "summary.json", payload)
                write_text(root / "economic_narrative.md", f"# {exp_id} - {spec['title']}\\n\\n- added_feature_count: {len(added_features)}\\n- mean_test_ic: {state['summary'].get('mean_test_ic')}\\n- mean_train_test_ratio: {state['summary'].get('mean_train_test_ratio')}")
                log_kv("Experiment complete", exp_id=exp_id, added_feature_count=len(added_features), mean_test_ic=state["summary"].get("mean_test_ic"))
                return payload

            if exp_id == "EXP-17":
                events = pd.DataFrame(EVENT_TABLE).copy()
                events["start_date"] = pd.to_datetime(events["start_date"], errors="coerce")
                events["end_date"] = pd.to_datetime(events["end_date"], errors="coerce")
                rows = []
                available_factors = [factor for factor in ANCHOR_FACTORS if factor in full_frame.columns]
                log_kv("EXP-17 setup", event_count=len(events), factor_count=len(available_factors))
                for event in events.to_dict(orient="records"):
                    log_kv("EXP-17 event start", event_id=event["event_id"], event_name=event["event_name"])
                    event_frame = full_frame[full_frame["date"].between(pd.Timestamp(event["start_date"]), pd.Timestamp(event["end_date"]))].copy()
                    for factor in available_factors:
                        scored = event_frame[["date", "target_weekly_return", factor]].rename(columns={factor: "prediction"})
                        summary = summarize_ic(compute_ic_series(scored))
                        rows.append(
                            {
                                "event_id": event["event_id"],
                                "event_name": event["event_name"],
                                "factor": factor,
                                "mean_ic": summary["mean_ic"],
                                "ic_ir": summary["ic_ir"],
                                "n_dates": summary["n_dates"],
                                "severity_score_1_10": event["severity_score_1_10"],
                                "model_collapse_risk": event["model_collapse_risk"],
                            }
                        )
                    log_kv("EXP-17 event complete", event_id=event["event_id"], rows_so_far=len(rows))
                table = pd.DataFrame(rows)
                blind_spots = table.sort_values(["mean_ic", "ic_ir"], ascending=[True, True], kind="mergesort").head(10).to_dict(orient="records") if not table.empty else []
                payload = {
                    "exp_id": exp_id,
                    "title": spec["title"],
                    "event_count": int(events["event_id"].nunique()),
                    "factor_count": int(table["factor"].nunique()) if not table.empty else 0,
                    "available_anchor_factors": available_factors,
                    "blind_spots": blind_spots,
                }
                write_table(root / "factor_event_heatmap.csv", table)
                write_table(root / "factor_event_heatmap.parquet", table)
                write_json(root / "summary.json", payload)
                write_text(root / "economic_narrative.md", f"# {exp_id} - {spec['title']}\\n\\n- event_count: {payload['event_count']}\\n- factor_count: {payload['factor_count']}\\n- available_anchor_factors: {available_factors}")
                log_kv("Experiment complete", exp_id=exp_id, heatmap_rows=len(table), blind_spots=len(blind_spots))
                return payload

            if exp_id == "EXP-18":
                events = select_high_risk_events(spec["top_n_high_risk_events"])
                rows = []
                for event in events.to_dict(orient="records"):
                    log_kv("EXP-18 event start", event_id=event["event_id"], event_name=event["event_name"])
                    splits = build_event_split(bundle, event["start_date"], event["end_date"], train_weeks=int(spec["train_window_weeks"]))
                    if not splits:
                        log_kv("EXP-18 event skipped", event_id=event["event_id"], reason="no_split")
                        rows.append({**event, "error": "insufficient_overlap"})
                        continue
                    state = run_walkforward(full_frame, splits, full_feature_columns, base_params, max_splits=1, output_dir=artifacts / str(event["event_id"]).lower())
                    rows.append(
                        {
                            "event_id": event["event_id"],
                            "event_name": event["event_name"],
                            "severity_score_1_10": event["severity_score_1_10"],
                            "model_collapse_risk": event["model_collapse_risk"],
                            "mean_test_ic": state["summary"].get("mean_test_ic"),
                            "ic_ir": state["summary"].get("ic_ir"),
                            "mean_train_test_ratio": state["summary"].get("mean_train_test_ratio"),
                        }
                    )
                    log_kv("EXP-18 event complete", event_id=event["event_id"], mean_test_ic=state["summary"].get("mean_test_ic"))
                table = pd.DataFrame(rows)
                worst_events = table[table["mean_test_ic"].notna()].sort_values(["mean_test_ic", "mean_train_test_ratio"], ascending=[True, False], kind="mergesort").head(3).to_dict(orient="records") if not table.empty and "mean_test_ic" in table.columns else []
                payload = {
                    "exp_id": exp_id,
                    "title": spec["title"],
                    "events_tested": int(len(table)),
                    "worst_events": worst_events,
                }
                write_table(root / "event_collapse_table.csv", table)
                write_json(root / "summary.json", payload)
                write_text(root / "economic_narrative.md", f"# {exp_id} - {spec['title']}\\n\\n- events_tested: {len(table)}\\n- worst_events: {worst_events}")
                log_kv("Experiment complete", exp_id=exp_id, events_tested=len(table), worst_events=len(worst_events))
                return payload

            if exp_id == "EXP-19":
                routing_catboost_features = dedupe(sequence_feature_columns + [c for c in EXTRA_METADATA_NUMERIC if c in full_frame.columns])
                log_kv("EXP-19 routing setup", catboost_feature_count=len(routing_catboost_features), sequence_feature_count=len(sequence_feature_columns), sequence_backend=SEQUENCE_BACKEND)
                catboost_state = run_walkforward(full_frame, bundle["splits"], routing_catboost_features, base_params, max_splits=MAX_SPLITS, output_dir=artifacts / "catboost")
                lstm_state = run_sequence_walkforward(full_frame, sequence_feature_columns, "LSTM")
                tcn_state = run_sequence_walkforward(full_frame, sequence_feature_columns, "TCN")
                model_rows = []
                for model_name, state in [("CatBoost", catboost_state), ("LSTM", lstm_state), ("TCN", tcn_state)]:
                    clean = [row for row in state["windows"] if "error" not in row]
                    if not clean:
                        continue
                    grouped = pd.DataFrame(clean).groupby("regime", as_index=False).agg(mean_test_ic=("test_ic", "mean"), mean_ratio=("train_test_ratio", "mean"), n_windows=("window_id", "count"))
                    grouped["model"] = model_name
                    model_rows.extend(grouped.to_dict(orient="records"))
                routing = build_routing_table(model_rows)
                payload = {
                    "exp_id": exp_id,
                    "title": spec["title"],
                    "routing_catboost_feature_count": len(routing_catboost_features),
                    "sequence_feature_count": len(sequence_feature_columns),
                    "sequence_backend": str(SEQUENCE_BACKEND),
                    "routed_mean_ic": float(routing["selected_mean_test_ic"].mean()) if not routing.empty else float("nan"),
                    "routing_rows": routing.to_dict(orient="records") if not routing.empty else [],
                    "model_summaries": {
                        "CatBoost": catboost_state["summary"],
                        "LSTM": lstm_state["summary"],
                        "TCN": tcn_state["summary"],
                    },
                }
                write_table(root / "routing_table.csv", routing if not routing.empty else pd.DataFrame(model_rows))
                write_json(root / "summary.json", payload)
                write_text(root / "economic_narrative.md", f"# {exp_id} - {spec['title']}\\n\\n- routed_mean_ic: {payload['routed_mean_ic']}\\n- sequence_backend: {SEQUENCE_BACKEND}\\n- sequence_feature_count: {len(sequence_feature_columns)}")
                log_kv("Experiment complete", exp_id=exp_id, routed_mean_ic=payload["routed_mean_ic"], routing_rows=len(payload["routing_rows"]))
                return payload

            raise KeyError(f"Unsupported experiment: {exp_id}")


        result = run_selected_experiment(SELECTED_EXP)
        log_kv("Notebook run complete", selected_exp=SELECTED_EXP)
        display(Markdown(f"### {result['exp_id']} - {result['title']}"))
        for key in ["catboost_summary", "worst_events", "routing_rows"]:
            if key in result:
                value = result[key]
                if isinstance(value, dict):
                    display(pd.DataFrame([value]))
                elif isinstance(value, list):
                    display(pd.DataFrame(value))
        result
        """
    ),
    _md("## Output Files"),
    _code(
        """
        out_root = experiment_root(SELECTED_EXP)
        files = sorted(str(path.relative_to(out_root)) for path in out_root.rglob("*") if path.is_file())
        log_kv("Output inventory", selected_exp=SELECTED_EXP, file_count=len(files), out_root=out_root)
        pd.DataFrame({"output_files": files})
        """
    ),
]


def main() -> None:
    ratio_repo = NOTEBOOK_DIR / "northstar_exp09_12_ratio_campaign_fresh_20260406.ipynb"
    ratio_downloads = DOWNLOADS_DIR / "northstar_exp09_12_ratio_campaign_fresh_20260406.ipynb"
    ratio_repo_r3 = NOTEBOOK_DIR / "northstar_exp09_12_ratio_campaign_fresh_20260406_r3.ipynb"
    ratio_downloads_r3 = DOWNLOADS_DIR / "northstar_exp09_12_ratio_campaign_fresh_20260406_r3.ipynb"
    ratio_repo_r4 = NOTEBOOK_DIR / "northstar_exp09_12_ratio_campaign_fresh_20260406_r4.ipynb"
    ratio_downloads_r4 = DOWNLOADS_DIR / "northstar_exp09_12_ratio_campaign_fresh_20260406_r4.ipynb"
    ratio_repo_r5 = NOTEBOOK_DIR / "northstar_exp09_12_ratio_campaign_fresh_20260406_r5.ipynb"
    ratio_downloads_r5 = DOWNLOADS_DIR / "northstar_exp09_12_ratio_campaign_fresh_20260406_r5.ipynb"
    ratio_repo_r6 = NOTEBOOK_DIR / "northstar_exp09_12_ratio_campaign_fresh_20260406_r6.ipynb"
    ratio_downloads_r6 = DOWNLOADS_DIR / "northstar_exp09_12_ratio_campaign_fresh_20260406_r6.ipynb"
    sector_repo = NOTEBOOK_DIR / "northstar_exp13_19_sector_regime_fresh_20260406.ipynb"
    sector_downloads = DOWNLOADS_DIR / "northstar_exp13_19_sector_regime_fresh_20260406.ipynb"
    sector_repo_r3 = NOTEBOOK_DIR / "northstar_exp13_19_sector_regime_fresh_20260406_r3.ipynb"
    sector_downloads_r3 = DOWNLOADS_DIR / "northstar_exp13_19_sector_regime_fresh_20260406_r3.ipynb"
    sector_repo_r4 = NOTEBOOK_DIR / "northstar_exp13_19_sector_regime_fresh_20260406_r4.ipynb"
    sector_downloads_r4 = DOWNLOADS_DIR / "northstar_exp13_19_sector_regime_fresh_20260406_r4.ipynb"
    sector_repo_r5 = NOTEBOOK_DIR / "northstar_exp13_19_sector_regime_fresh_20260406_r5.ipynb"
    sector_downloads_r5 = DOWNLOADS_DIR / "northstar_exp13_19_sector_regime_fresh_20260406_r5.ipynb"
    sector_repo_r6 = NOTEBOOK_DIR / "northstar_exp13_19_sector_regime_fresh_20260406_r6.ipynb"
    sector_downloads_r6 = DOWNLOADS_DIR / "northstar_exp13_19_sector_regime_fresh_20260406_r6.ipynb"

    _write_notebook(ratio_repo, RATIO_NOTEBOOK)
    _write_notebook(ratio_downloads, RATIO_NOTEBOOK)
    _write_notebook(ratio_repo_r3, RATIO_NOTEBOOK)
    _write_notebook(ratio_downloads_r3, RATIO_NOTEBOOK)
    _write_notebook(ratio_repo_r4, RATIO_NOTEBOOK)
    _write_notebook(ratio_downloads_r4, RATIO_NOTEBOOK)
    _write_notebook(ratio_repo_r5, RATIO_NOTEBOOK)
    _write_notebook(ratio_downloads_r5, RATIO_NOTEBOOK)
    _write_notebook(ratio_repo_r6, RATIO_NOTEBOOK)
    _write_notebook(ratio_downloads_r6, RATIO_NOTEBOOK)
    _write_notebook(sector_repo, SECTOR_NOTEBOOK)
    _write_notebook(sector_downloads, SECTOR_NOTEBOOK)
    _write_notebook(sector_repo_r3, SECTOR_NOTEBOOK)
    _write_notebook(sector_downloads_r3, SECTOR_NOTEBOOK)
    _write_notebook(sector_repo_r4, SECTOR_NOTEBOOK)
    _write_notebook(sector_downloads_r4, SECTOR_NOTEBOOK)
    _write_notebook(sector_repo_r5, SECTOR_NOTEBOOK)
    _write_notebook(sector_downloads_r5, SECTOR_NOTEBOOK)
    _write_notebook(sector_repo_r6, SECTOR_NOTEBOOK)
    _write_notebook(sector_downloads_r6, SECTOR_NOTEBOOK)

    print("Created:")
    print(ratio_repo)
    print(ratio_downloads)
    print(ratio_repo_r3)
    print(ratio_downloads_r3)
    print(ratio_repo_r4)
    print(ratio_downloads_r4)
    print(ratio_repo_r5)
    print(ratio_downloads_r5)
    print(ratio_repo_r6)
    print(ratio_downloads_r6)
    print(sector_repo)
    print(sector_downloads)
    print(sector_repo_r3)
    print(sector_downloads_r3)
    print(sector_repo_r4)
    print(sector_downloads_r4)
    print(sector_repo_r5)
    print(sector_downloads_r5)
    print(sector_repo_r6)
    print(sector_downloads_r6)


if __name__ == "__main__":
    main()
