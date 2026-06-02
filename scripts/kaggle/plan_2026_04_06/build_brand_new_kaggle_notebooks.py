#!/usr/bin/env python3
"""Build brand-new self-contained Kaggle notebooks for EXP-09..19."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import nbformat as nbf
import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOWNLOADS_DIR = Path.home() / "Downloads"
NOTEBOOK_DIR = PROJECT_ROOT / "notebooks" / "kaggle_sprint"
CATALOG_PATH = PROJECT_ROOT / "configs" / "plan_2026_04_05" / "catalog_v1.yaml"
EVENTS_PATH = PROJECT_ROOT / "data" / "canonical" / "reference" / "regimes" / "nse_regime_events_major.parquet"


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


def _load_payloads() -> tuple[dict, dict, dict, list[dict]]:
    payload = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8")) or {}
    plan = dict(payload.get("plan") or {})
    experiments = dict(payload.get("experiments") or {})

    ratio_experiments = {key: experiments[key] for key in ["EXP-09", "EXP-10", "EXP-11", "EXP-12"]}
    sector_regime_experiments = {
        key: experiments[key]
        for key in ["EXP-13", "EXP-14", "EXP-15", "EXP-16", "EXP-17", "EXP-18", "EXP-19"]
    }
    plan_context = {
        "plan_id": str(plan.get("plan_id") or "northstar_compendium"),
        "version": str(plan.get("version") or "v1"),
        "anchor_factors": list(plan.get("anchor_factors") or []),
        "cross_asset_signals": list(plan.get("cross_asset_signals") or []),
        "sector_conditional_features": list(plan.get("sector_conditional_features") or []),
    }

    events = pd.read_parquet(EVENTS_PATH).copy()
    events["start_date"] = pd.to_datetime(events["start_date"], errors="coerce")
    events["end_date"] = pd.to_datetime(events["end_date"], errors="coerce")
    mask = (events["end_date"] >= pd.Timestamp("2019-01-01")) & (events["start_date"] <= pd.Timestamp("2026-03-20"))
    event_cols = ["event_id", "event_name", "start_date", "end_date", "severity_score_1_10", "model_collapse_risk"]
    compact = events.loc[mask, event_cols].copy()
    compact["start_date"] = compact["start_date"].dt.strftime("%Y-%m-%d")
    compact["end_date"] = compact["end_date"].dt.strftime("%Y-%m-%d")
    return plan_context, ratio_experiments, sector_regime_experiments, compact.to_dict(orient="records")


def _json_cell(var_name: str, payload) -> str:
    blob = json.dumps(payload, indent=2, ensure_ascii=True)
    return f"import json\n{var_name} = json.loads(r'''{blob}''')"


RATIO_HELPERS = """
import json
import math
import warnings
from pathlib import Path

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


DEFAULT_CATBOOST_PARAMS = {
    "depth": 4,
    "l2_leaf_reg": 15.0,
    "min_data_in_leaf": 40,
    "od_wait": 30,
    "boosting_type": "Ordered",
    "iterations": 400,
    "learning_rate": 0.05,
}
NUMERIC_METADATA_COLUMNS = [
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
    return path


def write_markdown(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(text).strip() + "\\n", encoding="utf-8")
    return path


def write_table(path, frame):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".parquet":
        frame.to_parquet(path, index=False)
    else:
        frame.to_csv(path, index=False)
    return path


def resolve_export_dir(candidates, export_dir_override=None):
    required = [
        "northstar_features.parquet",
        "northstar_metadata.parquet",
        "northstar_regime_labels.parquet",
        "northstar_walk_forward_splits.json",
    ]
    probes = []
    if export_dir_override:
        probes.append(Path(export_dir_override).expanduser())
    probes.extend(Path(item) for item in candidates)
    root = Path("/kaggle/input")
    if root.exists():
        probes.extend(sorted(path for path in root.iterdir() if path.is_dir()))
    checked = []
    for probe in probes:
        if not probe.exists():
            checked.append(str(probe))
            continue
        if all((probe / name).exists() for name in required):
            return probe
        checked.append(str(probe))
    raise FileNotFoundError("Unable to resolve export dir. Checked:\\n- " + "\\n- ".join(checked[:30]))


def load_bundle(export_dir):
    root = Path(export_dir).expanduser().resolve()
    features = pd.read_parquet(root / "northstar_features.parquet")
    metadata = pd.read_parquet(root / "northstar_metadata.parquet")
    regimes = pd.read_parquet(root / "northstar_regime_labels.parquet")
    splits = json.loads((root / "northstar_walk_forward_splits.json").read_text(encoding="utf-8"))

    for frame in [features, metadata, regimes]:
        if "date" in frame.columns:
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()

    merged = features.merge(metadata, on=["date", "ticker"], how="left", sort=False, suffixes=("", "_meta"))
    regime_cols = [c for c in ["date", "plan_regime_id", "plan_regime_label", "regime", "major_event_id"] if c in regimes.columns]
    if regime_cols:
        merged = merged.merge(regimes[regime_cols].drop_duplicates("date"), on="date", how="left", sort=False)
    for col in ["plan_regime_id", "plan_regime_label", "regime", "major_event_id"]:
        if col not in merged.columns:
            left = f"{col}_x"
            right = f"{col}_y"
            if left in merged.columns or right in merged.columns:
                merged[col] = merged.get(left)
                if right in merged.columns:
                    merged[col] = merged[col].where(pd.Series(merged[col]).notna(), merged[right])
    if "plan_regime_label" in merged.columns:
        merged["plan_regime_label"] = merged["plan_regime_label"].fillna("Unknown").astype(str)
    if "sector" in merged.columns:
        merged["sector"] = merged["sector"].fillna("Unknown").astype(str)
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
    required = ["date", "ticker", "target_weekly_return"]
    missing = [c for c in required if c not in features.columns]
    if missing:
        raise RuntimeError(f"Missing required columns: {missing}")
    flags = ["pledge_pct_available", "rating_numeric_available", "days_since_earnings_available", "sector_dummy__NA_"]
    missing_flags = [c for c in flags if c not in features.columns]
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
                "plan_id": PLAN_CONTEXT["plan_id"],
                "version": PLAN_CONTEXT["version"],
                "features_rows": len(features),
                "feature_columns": features.shape[1],
                "tickers": features["ticker"].nunique(),
                "weekly_dates": features["date"].nunique(),
                "date_min": str(features["date"].min().date()),
                "date_max": str(features["date"].max().date()),
                "windows": len(bundle["splits"]),
            }
        ]
    )
    checks = pd.DataFrame(
        [
            {
                "target_last_column": features.columns[-1] == "target_weekly_return",
                "audit_blocking": ", ".join(list(audit.get("blocking_signals") or [])),
                "audit_warning": ", ".join(list(audit.get("warning_signals") or [])),
            }
        ]
    )
    display(overview)
    display(checks)
    return audit


def build_feature_columns(bundle):
    feature_cols = [
        c for c in bundle["features"].columns
        if c not in {"date", "ticker", "target_weekly_return"} and pd.api.types.is_numeric_dtype(bundle["features"][c])
    ]
    metadata_cols = [c for c in NUMERIC_METADATA_COLUMNS if c in bundle["metadata"].columns]
    return dedupe(feature_cols + metadata_cols)


def build_model_frame(bundle, feature_cols):
    needed = ["date", "ticker", "target_weekly_return", "plan_regime_label", "sector"] + [c for c in feature_cols if c in bundle["merged"].columns]
    frame = bundle["merged"][needed].copy()
    for col in feature_cols:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    frame["target_weekly_return"] = pd.to_numeric(frame["target_weekly_return"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    frame["plan_regime_label"] = frame["plan_regime_label"].fillna("Unknown").astype(str)
    frame["sector"] = frame["sector"].fillna("Unknown").astype(str)
    return frame.sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)


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
    config = dict(DEFAULT_CATBOOST_PARAMS)
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
        raise RuntimeError("No gradient boosting backend is available.")
    return HistGradientBoostingRegressor(
        learning_rate=float(config["learning_rate"]),
        max_depth=int(config["depth"]),
        max_iter=int(config["iterations"]),
        random_state=42,
    )


def split_train_valid(train_frame):
    unique_dates = sorted(pd.to_datetime(train_frame["date"]).dropna().unique().tolist())
    if len(unique_dates) < 12:
        return train_frame, None
    holdout = max(4, int(round(len(unique_dates) * 0.15)))
    holdout = min(holdout, len(unique_dates) - 4)
    if holdout <= 0:
        return train_frame, None
    cutoff = pd.Timestamp(unique_dates[-holdout]).normalize()
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
    windows = []
    for split in selected:
        split_dates = coerce_split_dates(split)
        train_frame = frame[frame["date"].between(split_dates["train_start"], split_dates["train_end"])].copy()
        test_frame = frame[frame["date"].between(split_dates["test_start"], split_dates["test_end"])].copy()
        if len(train_frame) < 1000 or len(test_frame) < 200:
            windows.append({**dict(split), "error": "insufficient_rows"})
            continue
        fit_frame, valid_frame = split_train_valid(train_frame)
        model = build_model(params)
        x_fit = fit_frame[feature_cols].to_numpy(dtype=np.float32)
        y_fit = fit_frame["target_weekly_return"].to_numpy(dtype=np.float32)
        x_train = train_frame[feature_cols].to_numpy(dtype=np.float32)
        y_train = train_frame["target_weekly_return"].to_numpy(dtype=np.float32)
        x_test = test_frame[feature_cols].to_numpy(dtype=np.float32)
        y_test = test_frame["target_weekly_return"].to_numpy(dtype=np.float32)
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
    return state


def best_candidate(candidates):
    clean = [dict(row) for row in candidates if np.isfinite(float(row.get("mean_test_ic", np.nan)))]
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


def experiment_paths(output_root, exp_id, version):
    root = Path(output_root).expanduser().resolve() / f"{exp_id.lower().replace('-', '_')}_{version}"
    artifacts = root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    return {"root": root, "artifacts": artifacts, "summary": root / "summary.json", "narrative": root / "economic_narrative.md"}


def load_existing_summary(output_root, exp_id, version):
    path = Path(output_root).expanduser().resolve() / f"{exp_id.lower().replace('-', '_')}_{version}" / "summary.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_ratio_base_params(output_root, version, override=None):
    params = dict(DEFAULT_CATBOOST_PARAMS)
    for exp_id in ["EXP-12", "EXP-11", "EXP-10", "EXP-09"]:
        payload = load_existing_summary(output_root, exp_id, version) or {}
        candidate = dict((payload or {}).get("best_candidate") or {})
        values = dict(candidate.get("params") or {})
        if values:
            params.update(values)
            break
    if override:
        params.update(dict(override))
    return params


def generate_anchored_weekly_splits(weekly_dates, anchor_start="2019-01-01", train_weeks=104, test_weeks=26, step_weeks=26):
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


def ratio_chain(selected_exp, run_upstream_chain=True):
    ordered = ["EXP-09", "EXP-10", "EXP-11", "EXP-12"]
    if selected_exp not in ordered:
        raise KeyError(f"unknown_ratio_exp:{selected_exp}")
    if not run_upstream_chain:
        return [selected_exp]
    return ordered[: ordered.index(selected_exp) + 1]


def narrative_text(exp_id, title, hypothesis, best_row, notes):
    lines = [f"# {exp_id} - {title}", "", f"Hypothesis: {hypothesis}", ""]
    if best_row:
        lines.extend(
            [
                "Best candidate:",
                f"- mean_test_ic: {best_row.get('mean_test_ic')}",
                f"- ic_ir: {best_row.get('ic_ir')}",
                f"- mean_train_test_ratio: {best_row.get('mean_train_test_ratio')}",
                f"- params: {best_row.get('params')}",
                "",
            ]
        )
    if notes:
        lines.append("Notes:")
        for note in notes:
            lines.append(f"- {note}")
    return "\\n".join(lines)


def run_ratio_experiment(exp_id, bundle, feature_cols, frame, output_root, version, max_splits=None, manual_upstream_params=None):
    spec = dict(RATIO_EXPERIMENTS[exp_id])
    params_spec = dict(spec.get("params") or {})
    paths = experiment_paths(output_root, exp_id, version)
    candidates = []
    notes = []

    def _run_candidate(label, params, splits):
        state = run_walkforward(frame, splits, feature_cols, params=params, max_splits=max_splits, output_dir=paths["artifacts"] / label)
        summary = dict(state["summary"])
        return {
            "label": label,
            "params": dict(params),
            "mean_test_ic": summary.get("mean_test_ic"),
            "ic_ir": summary.get("ic_ir"),
            "mean_train_test_ratio": summary.get("mean_train_test_ratio"),
            "mean_hit_rate": summary.get("mean_hit_rate"),
            "windows_completed": summary.get("windows_completed"),
            "output_dir": str(paths["artifacts"] / label),
        }

    if exp_id == "EXP-09":
        base = dict(DEFAULT_CATBOOST_PARAMS)
        base.update(dict(params_spec.get("base_catboost") or {}))
        for depth in list(params_spec.get("depth_grid") or []):
            for od_wait in list(params_spec.get("early_stopping_rounds") or []):
                candidate_params = {**base, "depth": int(depth), "od_wait": int(od_wait)}
                candidates.append(_run_candidate(f"depth_{depth}_odwait_{od_wait}", candidate_params, bundle["splits"]))
        notes.append("This run sweeps CatBoost depth against early stopping on the current merged export.")

    elif exp_id == "EXP-10":
        base = resolve_ratio_base_params(output_root, version, manual_upstream_params)
        for value in list(params_spec.get("l2_leaf_reg_grid") or []):
            candidate_params = {**base, "l2_leaf_reg": float(value)}
            candidates.append(_run_candidate(f"l2_{str(value).replace('.', '_')}", candidate_params, bundle["splits"]))
        notes.append("This sweep inherits the best available EXP-09 settings when those summaries already exist.")

    elif exp_id == "EXP-11":
        base = resolve_ratio_base_params(output_root, version, manual_upstream_params)
        for value in list(params_spec.get("boosting_types") or []):
            candidate_params = {**base, "boosting_type": str(value)}
            candidates.append(_run_candidate(f"boosting_{str(value).lower()}", candidate_params, bundle["splits"]))
        notes.append("This comparison changes only the CatBoost boosting type.")

    elif exp_id == "EXP-12":
        base = resolve_ratio_base_params(output_root, version, manual_upstream_params)
        weekly_dates = pd.to_datetime(bundle["features"]["date"], errors="coerce").dropna().sort_values().unique().tolist()
        for years in list(params_spec.get("train_window_years") or []):
            splits = generate_anchored_weekly_splits(
                weekly_dates,
                anchor_start="2019-01-01",
                train_weeks=int(years) * 52,
                test_weeks=int(params_spec.get("test_window_weeks") or 26),
                step_weeks=int(params_spec.get("step_weeks") or 26),
            )
            row = _run_candidate(f"window_{years}yr", base, splits)
            row["params"] = {**row["params"], "train_window_years": int(years)}
            row["split_count"] = len(splits)
            candidates.append(row)
        notes.append("EXP-12 rebuilds the windows to compare 2y, 3y, and 4y training spans with a fixed 6-month test horizon.")

    table = pd.DataFrame(candidates)
    best_row = best_candidate(candidates)
    payload = {
        "exp_id": exp_id,
        "title": spec.get("title"),
        "family": spec.get("family"),
        "hypothesis": spec.get("hypothesis"),
        "feature_count": len(feature_cols),
        "candidate_count": len(candidates),
        "best_candidate": best_row,
        "candidates": candidates,
    }
    write_table(paths["root"] / "candidate_table.csv", table)
    write_json(paths["summary"], payload)
    write_markdown(paths["narrative"], narrative_text(exp_id, spec.get("title"), spec.get("hypothesis"), best_row, notes))
    return payload


def display_ratio_result(payload):
    display(Markdown(f"### {payload['exp_id']} - {payload['title']}"))
    display(pd.DataFrame(payload["candidates"]).sort_values("mean_test_ic", ascending=False, kind="mergesort"))
    if payload.get("best_candidate"):
        display(pd.DataFrame([payload["best_candidate"]]))
"""


SECTOR_REGIME_HELPERS = """
import json
import math
import warnings
from pathlib import Path

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


DEFAULT_CATBOOST_PARAMS = {
    "depth": 4,
    "l2_leaf_reg": 15.0,
    "min_data_in_leaf": 40,
    "od_wait": 30,
    "boosting_type": "Ordered",
    "iterations": 400,
    "learning_rate": 0.05,
}
NUMERIC_METADATA_COLUMNS = [
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
    return path


def write_markdown(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(text).strip() + "\\n", encoding="utf-8")
    return path


def write_table(path, frame):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".parquet":
        frame.to_parquet(path, index=False)
    else:
        frame.to_csv(path, index=False)
    return path


def resolve_export_dir(candidates, export_dir_override=None):
    required = [
        "northstar_features.parquet",
        "northstar_metadata.parquet",
        "northstar_regime_labels.parquet",
        "northstar_walk_forward_splits.json",
    ]
    probes = []
    if export_dir_override:
        probes.append(Path(export_dir_override).expanduser())
    probes.extend(Path(item) for item in candidates)
    root = Path("/kaggle/input")
    if root.exists():
        probes.extend(sorted(path for path in root.iterdir() if path.is_dir()))
    checked = []
    for probe in probes:
        if not probe.exists():
            checked.append(str(probe))
            continue
        if all((probe / name).exists() for name in required):
            return probe
        checked.append(str(probe))
    raise FileNotFoundError("Unable to resolve export dir. Checked:\\n- " + "\\n- ".join(checked[:30]))


def load_bundle(export_dir):
    root = Path(export_dir).expanduser().resolve()
    features = pd.read_parquet(root / "northstar_features.parquet")
    metadata = pd.read_parquet(root / "northstar_metadata.parquet")
    regimes = pd.read_parquet(root / "northstar_regime_labels.parquet")
    splits = json.loads((root / "northstar_walk_forward_splits.json").read_text(encoding="utf-8"))

    for frame in [features, metadata, regimes]:
        if "date" in frame.columns:
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()

    merged = features.merge(metadata, on=["date", "ticker"], how="left", sort=False, suffixes=("", "_meta"))
    regime_cols = [c for c in ["date", "plan_regime_id", "plan_regime_label", "regime", "major_event_id"] if c in regimes.columns]
    if regime_cols:
        merged = merged.merge(regimes[regime_cols].drop_duplicates("date"), on="date", how="left", sort=False)
    for col in ["plan_regime_id", "plan_regime_label", "regime", "major_event_id"]:
        if col not in merged.columns:
            left = f"{col}_x"
            right = f"{col}_y"
            if left in merged.columns or right in merged.columns:
                merged[col] = merged.get(left)
                if right in merged.columns:
                    merged[col] = merged[col].where(pd.Series(merged[col]).notna(), merged[right])
    if "plan_regime_label" in merged.columns:
        merged["plan_regime_label"] = merged["plan_regime_label"].fillna("Unknown").astype(str)
    if "sector" in merged.columns:
        merged["sector"] = merged["sector"].fillna("Unknown").astype(str)
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
    required = ["date", "ticker", "target_weekly_return"]
    missing = [c for c in required if c not in features.columns]
    if missing:
        raise RuntimeError(f"Missing required columns: {missing}")
    flags = ["pledge_pct_available", "rating_numeric_available", "days_since_earnings_available", "sector_dummy__NA_"]
    missing_flags = [c for c in flags if c not in features.columns]
    if missing_flags:
        raise RuntimeError(f"Missing robust export flag columns: {missing_flags}")
    dead = [c for c in features.columns if c.startswith("earnings_quality_ratio")]
    if dead:
        raise RuntimeError(f"Dead earnings quality columns came back: {dead}")

    overview = pd.DataFrame(
        [
            {
                "plan_id": PLAN_CONTEXT["plan_id"],
                "version": PLAN_CONTEXT["version"],
                "features_rows": len(features),
                "feature_columns": features.shape[1],
                "tickers": features["ticker"].nunique(),
                "weekly_dates": features["date"].nunique(),
                "date_min": str(features["date"].min().date()),
                "date_max": str(features["date"].max().date()),
                "windows": len(bundle["splits"]),
            }
        ]
    )
    display(overview)


def build_full_feature_columns(bundle):
    feature_cols = [
        c for c in bundle["features"].columns
        if c not in {"date", "ticker", "target_weekly_return"} and pd.api.types.is_numeric_dtype(bundle["features"][c])
    ]
    metadata_cols = [c for c in NUMERIC_METADATA_COLUMNS if c in bundle["metadata"].columns]
    return dedupe(feature_cols + metadata_cols)


def build_sequence_feature_columns(bundle):
    candidates = dedupe(
        list(PLAN_CONTEXT["anchor_factors"])
        + list(PLAN_CONTEXT["cross_asset_signals"])
        + list(PLAN_CONTEXT["sector_conditional_features"])
        + ["ret_5d_cs_z", "ret_20d_cs_z", "mom_20d_cs_z", "mom_60d_cs_z", "val_quality_composite_zscore"]
    )
    merged = bundle["merged"]
    return [
        c for c in candidates
        if c in merged.columns and pd.api.types.is_numeric_dtype(merged[c])
    ][:20]


def build_model_frame(bundle, feature_cols):
    needed = ["date", "ticker", "target_weekly_return", "plan_regime_label", "sector"] + [c for c in feature_cols if c in bundle["merged"].columns]
    frame = bundle["merged"][needed].copy()
    for col in feature_cols:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    frame["target_weekly_return"] = pd.to_numeric(frame["target_weekly_return"], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    frame["plan_regime_label"] = frame["plan_regime_label"].fillna("Unknown").astype(str)
    frame["sector"] = frame["sector"].fillna("Unknown").astype(str)
    return frame.sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)


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
    config = dict(DEFAULT_CATBOOST_PARAMS)
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
        raise RuntimeError("No gradient boosting backend is available.")
    return HistGradientBoostingRegressor(
        learning_rate=float(config["learning_rate"]),
        max_depth=int(config["depth"]),
        max_iter=int(config["iterations"]),
        random_state=42,
    )


def split_train_valid(train_frame):
    unique_dates = sorted(pd.to_datetime(train_frame["date"]).dropna().unique().tolist())
    if len(unique_dates) < 12:
        return train_frame, None
    holdout = max(4, int(round(len(unique_dates) * 0.15)))
    holdout = min(holdout, len(unique_dates) - 4)
    if holdout <= 0:
        return train_frame, None
    cutoff = pd.Timestamp(unique_dates[-holdout]).normalize()
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
    windows = []
    for split in selected:
        split_dates = coerce_split_dates(split)
        train_frame = frame[frame["date"].between(split_dates["train_start"], split_dates["train_end"])].copy()
        test_frame = frame[frame["date"].between(split_dates["test_start"], split_dates["test_end"])].copy()
        if len(train_frame) < 1000 or len(test_frame) < 200:
            windows.append({**dict(split), "error": "insufficient_rows"})
            continue
        fit_frame, valid_frame = split_train_valid(train_frame)
        model = build_model(params)
        x_fit = fit_frame[feature_cols].to_numpy(dtype=np.float32)
        y_fit = fit_frame["target_weekly_return"].to_numpy(dtype=np.float32)
        x_train = train_frame[feature_cols].to_numpy(dtype=np.float32)
        x_test = test_frame[feature_cols].to_numpy(dtype=np.float32)
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
    return state


def experiment_paths(output_root, exp_id, version):
    root = Path(output_root).expanduser().resolve() / f"{exp_id.lower().replace('-', '_')}_{version}"
    artifacts = root / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    return {"root": root, "artifacts": artifacts, "summary": root / "summary.json", "narrative": root / "economic_narrative.md"}


def load_existing_summary(output_root, exp_id, version):
    path = Path(output_root).expanduser().resolve() / f"{exp_id.lower().replace('-', '_')}_{version}" / "summary.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_ratio_base_params(output_root, version, override=None):
    params = dict(DEFAULT_CATBOOST_PARAMS)
    for exp_id in ["EXP-12", "EXP-11", "EXP-10", "EXP-09"]:
        payload = load_existing_summary(output_root, exp_id, version) or {}
        candidate = dict((payload or {}).get("best_candidate") or {})
        values = dict(candidate.get("params") or {})
        if values:
            params.update(values)
            break
    if override:
        params.update(dict(override))
    return params


def resolve_sector_tickers(bundle, sector_name):
    metadata = bundle["metadata"]
    if "sector" not in metadata.columns:
        return []
    return (
        metadata.loc[metadata["sector"].astype(str) == str(sector_name), "ticker"]
        .dropna().astype(str).drop_duplicates().sort_values().tolist()
    )


def augment_sector_conditionals(frame, sectors, base_features):
    augmented = frame.copy()
    added = []
    if "sector" not in augmented.columns:
        return augmented, added
    for sector in sectors:
        tag = slugify(sector)
        indicator = f"sector_is__{tag}"
        augmented[indicator] = (augmented["sector"].astype(str) == str(sector)).astype("float32")
        added.append(indicator)
        for feature in base_features:
            if feature not in augmented.columns:
                continue
            name = f"{feature}__x__{tag}"
            augmented[name] = (pd.to_numeric(augmented[feature], errors="coerce").fillna(0.0) * augmented[indicator]).astype("float32")
            added.append(name)
    return augmented, added


def event_table():
    events = pd.DataFrame(MAJOR_EVENTS)
    events["start_date"] = pd.to_datetime(events["start_date"], errors="coerce")
    events["end_date"] = pd.to_datetime(events["end_date"], errors="coerce")
    return events.sort_values(["start_date", "event_id"], kind="mergesort").reset_index(drop=True)


def select_high_risk_events(events, top_n=5):
    def risk_score(row):
        label = str(row.get("model_collapse_risk") or "").upper()
        base = 4 if "EXTREME" in label else 3 if "HIGH" in label else 2 if "MEDIUM" in label else 1 if "LOW" in label else 0
        return base + float(row.get("severity_score_1_10") or 0) / 10.0
    ranked = events.copy()
    ranked["risk_score"] = ranked.apply(risk_score, axis=1)
    return ranked.sort_values(["risk_score", "severity_score_1_10"], ascending=[False, False], kind="mergesort").head(int(top_n))


def build_event_split(bundle, start_date, end_date, train_weeks=104):
    weekly_dates = pd.to_datetime(bundle["features"]["date"], errors="coerce").dropna().drop_duplicates().sort_values().tolist()
    weekly_dates = [pd.Timestamp(item).normalize() for item in weekly_dates]
    start = pd.Timestamp(start_date).normalize()
    end = pd.Timestamp(end_date).normalize()
    test_dates = [item for item in weekly_dates if start <= item <= end]
    if len(test_dates) < 2:
        return []
    first_idx = weekly_dates.index(test_dates[0])
    train_end_idx = first_idx - 1
    train_start_idx = max(0, train_end_idx - int(train_weeks) + 1)
    if train_end_idx <= train_start_idx:
        return []
    return [
        {
            "window_id": 1,
            "train_start": str(weekly_dates[train_start_idx].date()),
            "train_end": str(weekly_dates[train_end_idx].date()),
            "test_start": str(test_dates[0].date()),
            "test_end": str(test_dates[-1].date()),
        }
    ]


def best_model_by_regime(rows):
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
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


def narrative_text(exp_id, title, hypothesis, metrics, notes):
    lines = [f"# {exp_id} - {title}", "", f"Hypothesis: {hypothesis}", "", "Observed metrics:"]
    for key, value in metrics.items():
        lines.append(f"- {key}: {value}")
    if notes:
        lines.append("")
        lines.append("Notes:")
        for note in notes:
            lines.append(f"- {note}")
    return "\\n".join(lines)


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
    return cache


def sequence_samples(cache, split, seq_len, max_train_samples):
    split_dates = coerce_split_dates(split)
    train_x, train_y, train_dates = [], [], []
    test_x, test_y, test_dates, test_regimes = [], [], [], []
    for payload in cache.values():
        dates = payload["dates"]
        values = payload["values"]
        target = payload["target"]
        regimes = payload["regime"]
        for idx in range(seq_len - 1, len(dates)):
            date_value = pd.Timestamp(dates[idx]).normalize()
            sample = values[idx - seq_len + 1 : idx + 1]
            if split_dates["train_start"] <= date_value <= split_dates["train_end"]:
                train_x.append(sample)
                train_y.append(float(target[idx]))
                train_dates.append(date_value)
            elif split_dates["test_start"] <= date_value <= split_dates["test_end"]:
                test_x.append(sample)
                test_y.append(float(target[idx]))
                test_dates.append(date_value)
                test_regimes.append(str(regimes[idx]))
    if max_train_samples and len(train_x) > max_train_samples:
        rng = np.random.default_rng(42)
        keep = np.sort(rng.choice(len(train_x), size=int(max_train_samples), replace=False))
        train_x = [train_x[i] for i in keep]
        train_y = [train_y[i] for i in keep]
        train_dates = [train_dates[i] for i in keep]
    return {
        "train_x": np.asarray(train_x, dtype=np.float32),
        "train_y": np.asarray(train_y, dtype=np.float32),
        "train_dates": np.asarray(train_dates, dtype="datetime64[ns]"),
        "test_x": np.asarray(test_x, dtype=np.float32),
        "test_y": np.asarray(test_y, dtype=np.float32),
        "test_dates": np.asarray(test_dates, dtype="datetime64[ns]"),
        "test_regimes": np.asarray(test_regimes, dtype=object),
    }


def fit_sequence_sklearn(model_name, train_x, train_y):
    flat = train_x.reshape(len(train_x), -1).astype(np.float32, copy=False)
    mean = flat.mean(axis=0, keepdims=True)
    std = flat.std(axis=0, keepdims=True)
    std = np.where(std < 1e-6, 1.0, std)
    scaled = (flat - mean) / std
    if model_name == "LSTM" and MLPRegressor is not None:
        model = MLPRegressor(
            hidden_layer_sizes=(96, 48),
            activation="relu",
            learning_rate_init=1e-3,
            max_iter=max(30, int(SEQUENCE_EPOCHS) * 20),
            random_state=42,
            early_stopping=True,
            validation_fraction=0.1,
        )
    else:
        model = HistGradientBoostingRegressor(
            learning_rate=0.05,
            max_depth=4,
            max_iter=max(100, int(SEQUENCE_EPOCHS) * 40),
            random_state=42,
        )
    model.fit(scaled, train_y.astype(np.float32, copy=False))
    return model, mean.astype(np.float32), std.astype(np.float32)


def fit_sequence_torch(model_name, train_x, train_y, feature_count):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    order = np.arange(len(train_x))
    split_idx = min(max(int(len(order) * 0.9), 256), len(order) - 128)
    fit_x, valid_x = train_x[:split_idx], train_x[split_idx:]
    fit_y, valid_y = train_y[:split_idx], train_y[split_idx:]
    mean = fit_x.mean(axis=(0, 1), keepdims=True)
    std = fit_x.std(axis=(0, 1), keepdims=True)
    std = np.where(std < 1e-6, 1.0, std)
    fit_x = (fit_x - mean) / std
    valid_x = (valid_x - mean) / std
    model = LSTMRegressor(feature_count) if model_name == "LSTM" else TCNRegressor(feature_count)
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
            loss = float(loss_fn(model(valid_inputs), valid_targets).item())
        if loss < best_loss:
            best_loss = loss
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            patience = 0
        else:
            patience += 1
            if patience >= 2:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    return model, mean.astype(np.float32), std.astype(np.float32)


def predict_sequence(model, x, mean, std):
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


def run_sequence_walkforward(frame, splits, feature_cols, model_name, max_splits=None, output_dir=None):
    backend = str(SEQUENCE_BACKEND).strip().lower()
    if backend not in {"torch", "sklearn"}:
        backend = "sklearn"
    if backend == "torch" and (torch is None or nn is None or DataLoader is None or TensorDataset is None):
        backend = "sklearn"
    cache = build_group_cache(frame, feature_cols)
    selected = list(splits[:max_splits] if max_splits else splits)
    windows = []
    for split in selected:
        bundle = sequence_samples(cache, split, int(SEQUENCE_LENGTH), int(SEQUENCE_MAX_TRAIN_SAMPLES))
        if len(bundle["train_x"]) < 512 or len(bundle["test_x"]) < 128:
            windows.append({**dict(split), "error": "insufficient_sequence_rows"})
            continue
        try:
            if backend == "torch":
                model, mean, std = fit_sequence_torch(model_name, bundle["train_x"], bundle["train_y"], len(feature_cols))
            else:
                model, mean, std = fit_sequence_sklearn(model_name, bundle["train_x"], bundle["train_y"])
        except Exception as exc:
            windows.append({**dict(split), "error": str(exc)})
            continue
        train_pred = predict_sequence(model, bundle["train_x"], mean, std)
        test_pred = predict_sequence(model, bundle["test_x"], mean, std)
        train_scored = pd.DataFrame({"date": pd.to_datetime(bundle["train_dates"]), "target_weekly_return": bundle["train_y"], "prediction": train_pred})
        test_scored = pd.DataFrame({"date": pd.to_datetime(bundle["test_dates"]), "target_weekly_return": bundle["test_y"], "prediction": test_pred, "plan_regime_label": bundle["test_regimes"]})
        train_ic = summarize_ic(compute_ic_series(train_scored))
        test_ic = summarize_ic(compute_ic_series(test_scored))
        train_mean = float(train_ic["mean_ic"])
        test_mean = float(test_ic["mean_ic"])
        ratio = abs(train_mean) / max(abs(test_mean), 1e-6) if np.isfinite(train_mean) else float("nan")
        regime = test_scored["plan_regime_label"].mode(dropna=True).iloc[0] if not test_scored.empty else "Unknown"
        windows.append(
            {
                **dict(split),
                "train_rows": int(len(bundle["train_x"])),
                "test_rows": int(len(bundle["test_x"])),
                "train_ic": train_mean,
                "test_ic": test_mean,
                "train_test_ratio": ratio,
                "hit_rate": float(test_ic["hit_rate"]),
                "regime": str(regime),
            }
        )
    clean = [row for row in windows if "error" not in row]
    summary = {
        "backend": backend,
        "windows_completed": int(len(clean)),
        "mean_train_ic": float(pd.DataFrame(clean)["train_ic"].mean()) if clean else float("nan"),
        "mean_test_ic": float(pd.DataFrame(clean)["test_ic"].mean()) if clean else float("nan"),
        "ic_ir": float(pd.DataFrame(clean)["test_ic"].mean() / pd.DataFrame(clean)["test_ic"].std(ddof=1))
        if len(clean) > 1 and pd.DataFrame(clean)["test_ic"].std(ddof=1) > 0
        else float("nan"),
        "mean_train_test_ratio": float(pd.DataFrame(clean)["train_test_ratio"].mean()) if clean else float("nan"),
        "mean_hit_rate": float(pd.DataFrame(clean)["hit_rate"].mean()) if clean else float("nan"),
    }
    state = {"model": model_name, "feature_columns": list(feature_cols), "feature_count": len(feature_cols), "windows": windows, "summary": summary}
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        write_table(output_dir / "window_metrics.csv", pd.DataFrame(windows))
        write_json(output_dir / "summary.json", state)
    return state


def run_exp13_to_19(exp_id, bundle, output_root, version, max_splits=None, best_ratio_params_override=None):
    spec = dict(SECTOR_REGIME_EXPERIMENTS[exp_id])
    params = dict(DEFAULT_CATBOOST_PARAMS)
    params.update(resolve_ratio_base_params(output_root, version, best_ratio_params_override))
    full_feature_cols = build_full_feature_columns(bundle)
    frame = build_model_frame(bundle, full_feature_cols)
    paths = experiment_paths(output_root, exp_id, version)

    if exp_id in {"EXP-13", "EXP-14", "EXP-15"}:
        sector_name = str((spec.get("params") or {}).get("sector_name") or "")
        tickers = resolve_sector_tickers(bundle, sector_name)
        subset = frame[frame["ticker"].isin(tickers)].copy()
        state = run_walkforward(subset, bundle["splits"], full_feature_cols, params, max_splits=max_splits, output_dir=paths["artifacts"] / "catboost")
        payload = {
            "exp_id": exp_id,
            "title": spec.get("title"),
            "sector_name": sector_name,
            "n_tickers": len(tickers),
            "tickers": tickers,
            "feature_count": len(full_feature_cols),
            "best_params": params,
            "catboost_summary": state["summary"],
        }
        write_json(paths["root"] / "sector_subset_manifest.json", payload)
        write_json(paths["summary"], payload)
        write_markdown(paths["narrative"], narrative_text(exp_id, spec.get("title"), spec.get("hypothesis"), {"sector_name": sector_name, "n_tickers": len(tickers), "mean_test_ic": state["summary"].get("mean_test_ic"), "mean_train_test_ratio": state["summary"].get("mean_train_test_ratio")}, ["This run uses the sector labels stored in northstar_metadata.parquet."]))
        return payload

    if exp_id == "EXP-16":
        sectors = list((spec.get("params") or {}).get("sectors") or [])
        augmented, added_features = augment_sector_conditionals(frame, sectors, PLAN_CONTEXT["sector_conditional_features"])
        all_feature_cols = dedupe(full_feature_cols + [c for c in added_features if c in augmented.columns])
        state = run_walkforward(augmented, bundle["splits"], all_feature_cols, params, max_splits=max_splits, output_dir=paths["artifacts"] / "catboost")
        payload = {
            "exp_id": exp_id,
            "title": spec.get("title"),
            "feature_count": len(all_feature_cols),
            "added_feature_count": len(added_features),
            "added_features": added_features,
            "best_params": params,
            "catboost_summary": state["summary"],
        }
        write_json(paths["root"] / "augmented_feature_manifest.json", payload)
        write_json(paths["summary"], payload)
        write_markdown(paths["narrative"], narrative_text(exp_id, spec.get("title"), spec.get("hypothesis"), {"added_feature_count": len(added_features), "mean_test_ic": state["summary"].get("mean_test_ic"), "mean_train_test_ratio": state["summary"].get("mean_train_test_ratio")}, ["This run adds sector identity flags and sector-conditional interaction features on top of the full numeric feature export."]))
        return payload

    if exp_id == "EXP-17":
        events = event_table()
        available = [factor for factor in PLAN_CONTEXT["anchor_factors"] if factor in frame.columns]
        rows = []
        for event in events.to_dict(orient="records"):
            event_frame = frame[frame["date"].between(pd.Timestamp(event["start_date"]), pd.Timestamp(event["end_date"]))].copy()
            for factor in available:
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
        table = pd.DataFrame(rows)
        blind_spots = table.sort_values(["mean_ic", "ic_ir"], ascending=[True, True], kind="mergesort").head(10).to_dict(orient="records") if not table.empty else []
        payload = {
            "exp_id": exp_id,
            "title": spec.get("title"),
            "event_count": int(events["event_id"].nunique()) if not events.empty else 0,
            "factor_count": int(table["factor"].nunique()) if not table.empty else 0,
            "available_anchor_factors": available,
            "missing_anchor_factors": [factor for factor in PLAN_CONTEXT["anchor_factors"] if factor not in available],
            "blind_spots": blind_spots,
        }
        write_table(paths["root"] / "factor_event_heatmap.csv", table)
        write_table(paths["root"] / "factor_event_heatmap.parquet", table)
        write_json(paths["summary"], payload)
        write_markdown(paths["narrative"], narrative_text(exp_id, spec.get("title"), spec.get("hypothesis"), {"event_count": payload["event_count"], "factor_count": payload["factor_count"], "missing_anchor_factors": ", ".join(payload["missing_anchor_factors"])}, ["The event table is embedded directly in this notebook and only covers periods overlapping the current export."]))
        return payload

    if exp_id == "EXP-18":
        events = select_high_risk_events(event_table(), top_n=int((spec.get("params") or {}).get("top_n_high_risk_events") or 5))
        baseline = load_existing_summary(output_root, "EXP-12", version) or {}
        baseline_ic = float(((baseline.get("best_candidate") or {}).get("mean_test_ic")) or np.nan)
        rows = []
        for event in events.to_dict(orient="records"):
            splits = build_event_split(bundle, event["start_date"], event["end_date"], train_weeks=int((spec.get("params") or {}).get("train_window_weeks") or 104))
            if not splits:
                rows.append({**event, "error": "insufficient_overlap"})
                continue
            state = run_walkforward(frame, splits, full_feature_cols, params, max_splits=1, output_dir=paths["artifacts"] / str(event["event_id"]).lower())
            mean_test_ic = float(state["summary"].get("mean_test_ic"))
            rows.append(
                {
                    "event_id": event["event_id"],
                    "event_name": event["event_name"],
                    "severity_score_1_10": event["severity_score_1_10"],
                    "model_collapse_risk": event["model_collapse_risk"],
                    "mean_test_ic": mean_test_ic,
                    "ic_ir": state["summary"].get("ic_ir"),
                    "mean_train_test_ratio": state["summary"].get("mean_train_test_ratio"),
                    "collapse_vs_baseline": mean_test_ic / baseline_ic if np.isfinite(baseline_ic) and baseline_ic != 0 else float("nan"),
                }
            )
        table = pd.DataFrame(rows)
        worst = table[table["mean_test_ic"].notna()].sort_values(["mean_test_ic", "mean_train_test_ratio"], ascending=[True, False], kind="mergesort").head(3).to_dict(orient="records") if not table.empty and "mean_test_ic" in table.columns else []
        payload = {
            "exp_id": exp_id,
            "title": spec.get("title"),
            "baseline_mean_test_ic": baseline_ic,
            "events_tested": int(len(table)),
            "worst_events": worst,
        }
        write_table(paths["root"] / "event_collapse_table.csv", table)
        write_json(paths["summary"], payload)
        write_markdown(paths["narrative"], narrative_text(exp_id, spec.get("title"), spec.get("hypothesis"), {"events_tested": len(table), "baseline_mean_test_ic": baseline_ic, "worst_event_mean_test_ic": worst[0]["mean_test_ic"] if worst else None}, ["Each event run trains on the preceding history and tests only inside the event window."]))
        return payload

    if exp_id == "EXP-19":
        sequence_cols = build_sequence_feature_columns(bundle)
        routing_catboost_cols = dedupe(sequence_cols + [c for c in NUMERIC_METADATA_COLUMNS if c in frame.columns])
        catboost_state = run_walkforward(frame, bundle["splits"], routing_catboost_cols, params, max_splits=max_splits, output_dir=paths["artifacts"] / "catboost")
        lstm_state = run_sequence_walkforward(frame, bundle["splits"], sequence_cols, "LSTM", max_splits=max_splits, output_dir=paths["artifacts"] / "lstm")
        tcn_state = run_sequence_walkforward(frame, bundle["splits"], sequence_cols, "TCN", max_splits=max_splits, output_dir=paths["artifacts"] / "tcn")
        regime_rows = []
        for name, state in [("CatBoost", catboost_state), ("LSTM", lstm_state), ("TCN", tcn_state)]:
            clean = [row for row in state["windows"] if "error" not in row]
            if not clean:
                continue
            frame_rows = pd.DataFrame(clean)
            grouped = frame_rows.groupby("regime", as_index=False).agg(mean_test_ic=("test_ic", "mean"), mean_ratio=("train_test_ratio", "mean"), n_windows=("window_id", "count"))
            grouped["model"] = name
            regime_rows.extend(grouped.to_dict(orient="records"))
        routing = best_model_by_regime(regime_rows)
        payload = {
            "exp_id": exp_id,
            "title": spec.get("title"),
            "routing_catboost_feature_count": len(routing_catboost_cols),
            "sequence_feature_count": len(sequence_cols),
            "routed_mean_ic": float(routing["selected_mean_test_ic"].mean()) if not routing.empty else float("nan"),
            "routing_rows": routing.to_dict(orient="records") if not routing.empty else [],
            "model_summaries": {
                "CatBoost": catboost_state["summary"],
                "LSTM": lstm_state["summary"],
                "TCN": tcn_state["summary"],
            },
        }
        write_table(paths["root"] / "routing_table.csv", routing if not routing.empty else pd.DataFrame(regime_rows))
        write_json(paths["summary"], payload)
        write_markdown(paths["narrative"], narrative_text(exp_id, spec.get("title"), spec.get("hypothesis"), {"routed_mean_ic": payload["routed_mean_ic"], "sequence_backend": str(SEQUENCE_BACKEND), "sequence_feature_count": len(sequence_cols)}, ["Set SEQUENCE_BACKEND to 'torch' if you want the actual PyTorch LSTM and TCN path on Kaggle; keep 'sklearn' for the most reliable run."]))
        return payload

    raise KeyError(f"unsupported_exp:{exp_id}")


def display_result(payload):
    display(Markdown(f"### {payload['exp_id']} - {payload['title']}"))
    for key in ["catboost_summary", "worst_events", "routing_rows"]:
        if key in payload:
            value = payload[key]
            if isinstance(value, dict):
                display(pd.DataFrame([value]))
            elif isinstance(value, list):
                display(pd.DataFrame(value))
"""


def _ratio_cells(plan_context: dict, ratio_experiments: dict) -> list:
    return [
        _md(
            """
            # NORTHSTAR V3 - Ratio Campaign

            This is a fresh Kaggle notebook for **EXP-09 to EXP-12**.

            Attach only:
            - `northstar-v3-feature-export`

            This notebook is fully self-contained and reads directly from the merged export files.
            """
        ),
        _md("## Config"),
        _code(
            """
            from pathlib import Path

            SELECTED_EXP = "EXP-09"  # EXP-09 | EXP-10 | EXP-11 | EXP-12
            RUN_UPSTREAM_CHAIN = True
            MAX_SPLITS = None  # set to an integer for a smoke test
            VERSION = "v2_clean"
            OUTPUT_ROOT = Path("/kaggle/working/northstar_compendium")

            EXPORT_DIR_OVERRIDE = None
            EXPORT_DATASET_CANDIDATES = [
                "/kaggle/input/northstar-v3-feature-export",
                "/kaggle/input/northstar-v3-feature-export-1",
                "/kaggle/input/northstar-v3-feature-export-2",
            ]

            MANUAL_UPSTREAM_PARAMS = {}
            print(f"Notebook configured for {SELECTED_EXP}")
            """
        ),
        _md("## Embedded Plan"),
        _code(_json_cell("PLAN_CONTEXT", plan_context) + "\n" + _json_cell("RATIO_EXPERIMENTS", ratio_experiments)),
        _md("## Helpers"),
        _code(RATIO_HELPERS),
        _md("## Load Dataset"),
        _code(
            """
            export_dir = resolve_export_dir(EXPORT_DATASET_CANDIDATES, EXPORT_DIR_OVERRIDE)
            bundle = load_bundle(export_dir)
            audit = validate_bundle(bundle)
            feature_columns = build_feature_columns(bundle)
            model_frame = build_model_frame(bundle, feature_columns)
            print({"export_dir": str(export_dir), "feature_count": len(feature_columns)})
            """
        ),
        _md("## Run Ratio Experiments"),
        _code(
            """
            run_order = ratio_chain(SELECTED_EXP, run_upstream_chain=RUN_UPSTREAM_CHAIN)
            results = {}
            for exp_id in run_order:
                result = run_ratio_experiment(
                    exp_id,
                    bundle=bundle,
                    feature_cols=feature_columns,
                    frame=model_frame,
                    output_root=OUTPUT_ROOT,
                    version=VERSION,
                    max_splits=MAX_SPLITS,
                    manual_upstream_params=MANUAL_UPSTREAM_PARAMS,
                )
                results[exp_id] = result
                display_ratio_result(result)
            results[SELECTED_EXP]
            """
        ),
        _md("## Output Files"),
        _code(
            """
            exp_root = OUTPUT_ROOT / f"{SELECTED_EXP.lower().replace('-', '_')}_{VERSION}"
            files = sorted(str(path.relative_to(exp_root)) for path in exp_root.rglob("*") if path.is_file())
            pd.DataFrame({"output_files": files})
            """
        ),
    ]


def _sector_regime_cells(plan_context: dict, sector_regime_experiments: dict, events: list[dict]) -> list:
    return [
        _md(
            """
            # NORTHSTAR V3 - Sector And Regime Campaigns

            This is a fresh Kaggle notebook for **EXP-13 to EXP-19**.

            Attach only:
            - `northstar-v3-feature-export`

            Notes:
            - EXP-13 to EXP-18 use the best ratio params from notebook 1 if those summaries already exist.
            - If not, they fall back to the default CatBoost baseline.
            - EXP-19 defaults to a reliable `sklearn` sequence backend. Switch to `torch` if you want the actual LSTM/TCN path on Kaggle.
            """
        ),
        _md("## Config"),
        _code(
            """
            from pathlib import Path

            SELECTED_EXP = "EXP-13"  # EXP-13 ... EXP-19
            MAX_SPLITS = None  # set to an integer for a smoke test
            VERSION = "v2_clean"
            OUTPUT_ROOT = Path("/kaggle/working/northstar_compendium")

            EXPORT_DIR_OVERRIDE = None
            EXPORT_DATASET_CANDIDATES = [
                "/kaggle/input/northstar-v3-feature-export",
                "/kaggle/input/northstar-v3-feature-export-1",
                "/kaggle/input/northstar-v3-feature-export-2",
            ]

            BEST_RATIO_PARAMS_OVERRIDE = {}
            SEQUENCE_BACKEND = "sklearn"  # "sklearn" for reliability, "torch" for true LSTM/TCN on Kaggle
            SEQUENCE_LENGTH = 8
            SEQUENCE_EPOCHS = 4
            SEQUENCE_BATCH_SIZE = 512
            SEQUENCE_MAX_TRAIN_SAMPLES = 30000
            print(f"Notebook configured for {SELECTED_EXP}")
            """
        ),
        _md("## Embedded Plan"),
        _code(
            _json_cell("PLAN_CONTEXT", plan_context)
            + "\n"
            + _json_cell("SECTOR_REGIME_EXPERIMENTS", sector_regime_experiments)
            + "\n"
            + _json_cell("MAJOR_EVENTS", events)
        ),
        _md("## Helpers"),
        _code(SECTOR_REGIME_HELPERS),
        _md("## Load Dataset"),
        _code(
            """
            export_dir = resolve_export_dir(EXPORT_DATASET_CANDIDATES, EXPORT_DIR_OVERRIDE)
            bundle = load_bundle(export_dir)
            validate_bundle(bundle)
            print({"export_dir": str(export_dir), "features_rows": len(bundle["features"]), "splits": len(bundle["splits"])})
            """
        ),
        _md("## Run Sector Or Regime Experiment"),
        _code(
            """
            result = run_exp13_to_19(
                SELECTED_EXP,
                bundle=bundle,
                output_root=OUTPUT_ROOT,
                version=VERSION,
                max_splits=MAX_SPLITS,
                best_ratio_params_override=BEST_RATIO_PARAMS_OVERRIDE,
            )
            display_result(result)
            result
            """
        ),
        _md("## Output Files"),
        _code(
            """
            exp_root = OUTPUT_ROOT / f"{SELECTED_EXP.lower().replace('-', '_')}_{VERSION}"
            files = sorted(str(path.relative_to(exp_root)) for path in exp_root.rglob("*") if path.is_file())
            pd.DataFrame({"output_files": files})
            """
        ),
    ]


def main() -> None:
    plan_context, ratio_experiments, sector_regime_experiments, events = _load_payloads()

    ratio_repo = NOTEBOOK_DIR / "northstar_exp09_12_ratio_campaign.ipynb"
    ratio_downloads = DOWNLOADS_DIR / "northstar_exp09_12_ratio_campaign (1).ipynb"
    sector_repo = NOTEBOOK_DIR / "northstar_exp13_19_sector_regime.ipynb"
    sector_downloads = DOWNLOADS_DIR / "northstar_exp13_19_sector_regime.ipynb"

    _write_notebook(ratio_repo, _ratio_cells(plan_context, ratio_experiments))
    _write_notebook(ratio_downloads, _ratio_cells(plan_context, ratio_experiments))
    _write_notebook(sector_repo, _sector_regime_cells(plan_context, sector_regime_experiments, events))
    _write_notebook(sector_downloads, _sector_regime_cells(plan_context, sector_regime_experiments, events))

    print(
        json.dumps(
            {
                "ratio_repo": str(ratio_repo),
                "ratio_downloads": str(ratio_downloads),
                "sector_repo": str(sector_repo),
                "sector_downloads": str(sector_downloads),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
