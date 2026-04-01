#!/usr/bin/env python3
"""NB-02: failed-model autopsy and stratum experiments for the weekly sprint."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SHARED_DIR = PROJECT_ROOT / "notebooks" / "kaggle_sprint" / "shared"
os.environ.setdefault("MPLCONFIGDIR", str((PROJECT_ROOT / "tmp" / ".mplconfig").resolve()))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from track_a_runner import TrackARunConfig, TrackARunner  # noqa: E402
from track_b_runner import TrackBRunConfig, TrackBRunner  # noqa: E402

from scripts.kaggle.week_2026_03_29.common import (  # noqa: E402
    derive_size_rank,
    json_ready,
    load_export_artifacts,
    make_run_dir,
    read_json,
    resolve_export_dir,
    subset_feature_export,
    write_json,
)


PRIOR_TFT_BASELINE_IC = -0.001
PRIOR_PATCHTST_BASELINE_IC = -0.013


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NB-02 failed-model autopsy.")
    parser.add_argument("--export-dir", type=Path, required=True)
    parser.add_argument("--nb00-report", type=Path, default=None)
    parser.add_argument("--nb01-dir", type=Path, default=None)
    parser.add_argument("--patchtst-result-path", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--profile", choices=["smoke", "full"], default="full")
    parser.add_argument("--max-splits", type=int, default=None)
    return parser.parse_args()


class AutopsyTrackARunner(TrackARunner):
    def __init__(self, config: TrackARunConfig | None = None, sequence_overrides: dict[str, dict[str, Any]] | None = None):
        self.sequence_overrides = sequence_overrides or {}
        super().__init__(config=config)

    @staticmethod
    def _empty_model_summary(model_name: str) -> dict[str, Any]:
        return {
            "model": model_name,
            "mean_test_ic": float("nan"),
            "ic_ir": float("nan"),
            "mean_train_test_ratio": float("nan"),
            "mean_hit_rate": float("nan"),
            "windows_completed": 0,
            "verdict": "SKIPPED_BASELINE",
            "decision": "REJECT",
        }

    def _seed_tree_placeholders(self) -> None:
        for prefix, model_name in [("xgb", "XGBoost"), ("lightgbm", "LightGBM"), ("catboost", "CatBoost")]:
            self.state.setdefault(f"{prefix}_results", {"windows": [], "summary": self._empty_model_summary(model_name)})
            self.state.setdefault(f"{prefix}_summary", self._empty_model_summary(model_name))
            self.state.setdefault(f"{prefix}_stability", {"mean_pairwise_correlation": float("nan")})

    def _sequence_configs(self):  # type: ignore[override]
        lstm, gru, tcn, transformer = super()._sequence_configs()
        mapping = {
            "lstm": lstm,
            "gru": gru,
            "tcn": tcn,
            "transformer": transformer,
        }
        for model_name, overrides in self.sequence_overrides.items():
            if model_name in mapping:
                mapping[model_name].update(dict(overrides))
        return mapping["lstm"], mapping["gru"], mapping["tcn"], mapping["transformer"]

    def run(self) -> dict[str, Any]:  # type: ignore[override]
        self._load_data()
        self._bootstrap_day1_if_needed()
        self._run_day(1, "Factor IC Analysis", self._run_day1)
        self._run_day(2, "XGBoost + CatBoost Walk-Forward", self._run_day2)
        self._seed_tree_placeholders()
        self._run_day(3, "Sequence Model Walk-Forward", self._run_day3)
        self._run_day(4, "Regime + Sector Analysis", self._run_day4)
        self._run_day(5, "India-Specific Factor Tests", self._run_day5)
        self._run_day(6, "Ensemble + Deployment Analysis", self._run_day6)
        self._run_day(7, "Final Verdict", self._run_day7)
        self._save_run_state(status="completed")
        return self.state


class AutopsyTrackBRunner(TrackBRunner):
    def __init__(self, config: TrackBRunConfig | None = None, frontier_overrides: dict[str, dict[str, Any]] | None = None):
        self.frontier_overrides = frontier_overrides or {}
        super().__init__(config=config)

    def _frontier_configs(self):  # type: ignore[override]
        tft_config, itransformer_config = super()._frontier_configs()
        mapping = {
            "tft": tft_config,
            "itransformer": itransformer_config,
        }
        for model_name, overrides in self.frontier_overrides.items():
            if model_name in mapping:
                mapping[model_name].update(dict(overrides))
        return mapping["tft"], mapping["itransformer"]


def _tier12_selected_features(export_dir: Path, nb00_report: Path | None) -> list[str]:
    report_path = nb00_report or (export_dir / "feature_health_report.json")
    if not report_path.exists():
        return []
    payload = read_json(report_path)
    tier_lists = dict(payload.get("tier_lists") or {})
    return list(dict.fromkeys([*(tier_lists.get("TIER_1") or []), *(tier_lists.get("TIER_2") or [])]))


def _safe_mean(values: list[float]) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    return float(np.mean(arr)) if arr.size else float("nan")


def _durbin_watson(values: list[float]) -> float:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size < 2:
        return float("nan")
    numer = np.square(np.diff(arr)).sum()
    denom = np.square(arr).sum()
    return float(numer / denom) if denom > 0 else float("nan")


def _load_model_payload(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _valid_windows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [window for window in list(payload.get("windows") or []) if "error" not in window]


def _summary_from_state(state: dict[str, Any], model_name: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    results = dict((state.get("all_model_results") or {}).get(model_name) or {})
    summary = dict((state.get("all_summaries") or {}).get(model_name) or {})
    stability = dict((state.get("all_stabilities") or {}).get(model_name) or {})
    return results, summary, stability


def _prepare_subsets(
    export_dir: Path,
    output_dir: Path,
    metadata_df: pd.DataFrame,
    selected_features: list[str],
    features_df: pd.DataFrame,
) -> dict[str, Path]:
    size_rank = derive_size_rank(metadata_df)
    size_frame = metadata_df[["ticker"]].copy()
    size_frame["market_cap_rank"] = size_rank
    median_rank = (
        size_frame.groupby("ticker", as_index=True)["market_cap_rank"]
        .median()
        .sort_values()
        .dropna()
    )
    large_cap = median_rank[median_rank >= 0.60].index.astype(str).tolist()
    mid_cap = median_rank[(median_rank >= 0.20) & (median_rank < 0.60)].index.astype(str).tolist()
    top97 = median_rank.sort_values(ascending=False).head(97).index.astype(str).tolist()

    rate_feature = None
    for candidate in ["rbi_repo_rate_change_13w", "rbi_repo_rate_level", "rbi_repo_rate_ts_z"]:
        if candidate in features_df.columns:
            rate_feature = candidate
            break
    if rate_feature is not None:
        rate_dates = (
            features_df.groupby("date", as_index=False)[rate_feature]
            .mean(numeric_only=True)
            .rename(columns={rate_feature: "rate_signal"})
        )
        stable_dates = rate_dates.loc[pd.to_numeric(rate_dates["rate_signal"], errors="coerce").abs() <= 0.05, "date"]
        if stable_dates.empty:
            stable_start = "2022-07-01"
            stable_end = "2024-06-30"
        else:
            stable_start = str(pd.Timestamp(stable_dates.min()).date())
            stable_end = str(pd.Timestamp(stable_dates.max()).date())
    else:
        stable_start = "2022-07-01"
        stable_end = "2024-06-30"

    subsets = {
        "large_cap_export": output_dir / "large_cap_export",
        "mid_cap_export": output_dir / "mid_cap_export",
        "rate_stable_export": output_dir / "rate_stable_export",
        "reduced97_export": output_dir / "reduced97_export",
    }
    subset_feature_export(
        source_dir=export_dir,
        output_dir=subsets["large_cap_export"],
        selected_features=selected_features or None,
        ticker_mask=large_cap,
    )
    subset_feature_export(
        source_dir=export_dir,
        output_dir=subsets["mid_cap_export"],
        selected_features=selected_features or None,
        ticker_mask=mid_cap,
    )
    subset_feature_export(
        source_dir=export_dir,
        output_dir=subsets["rate_stable_export"],
        selected_features=selected_features or None,
        date_min=stable_start,
        date_max=stable_end,
    )
    subset_feature_export(
        source_dir=export_dir,
        output_dir=subsets["reduced97_export"],
        selected_features=selected_features or None,
        ticker_mask=top97,
    )
    return subsets


def _run_track_a_sequence(
    data_dir: Path,
    output_dir: Path,
    *,
    profile: str,
    max_splits: int | None,
    model_filter: list[str],
    sequence_overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    config = TrackARunConfig(
        data_dir=data_dir,
        output_dir=output_dir,
        skip_days={1, 2, 4, 5, 6, 7},
        continue_on_error=True,
        resume_from_checkpoint=True,
        run_profile=profile,
        max_splits=max_splits,
        model_filter=model_filter,
        feature_mode="full",
        normalize_raw_financials=True,
        require_group_ranking=True,
    )
    return AutopsyTrackARunner(config=config, sequence_overrides=sequence_overrides).run()


def _run_track_b_frontier(
    data_dir: Path,
    output_dir: Path,
    *,
    profile: str,
    max_splits: int | None,
    feature_mode: str = "full",
    reduced_feature_count: int = 60,
    frontier_overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    config = TrackBRunConfig(
        data_dir=data_dir,
        output_dir=output_dir,
        skip_days={1, 3, 4, 5, 6, 7},
        continue_on_error=True,
        resume_from_checkpoint=True,
        run_profile=profile,
        max_splits=max_splits,
        feature_mode=feature_mode,
        reduced_feature_count=reduced_feature_count,
        normalize_raw_financials=True,
        require_group_ranking=True,
    )
    return AutopsyTrackBRunner(config=config, frontier_overrides=frontier_overrides).run()


def _window_rate_activity(features_df: pd.DataFrame, splits: list[dict[str, Any]]) -> pd.DataFrame:
    if "rbi_repo_rate_change_13w" not in features_df.columns:
        return pd.DataFrame(columns=["window_id", "rate_activity", "bucket"])
    date_activity = (
        features_df.groupby("date", as_index=False)["rbi_repo_rate_change_13w"]
        .mean(numeric_only=True)
        .rename(columns={"rbi_repo_rate_change_13w": "rate_signal"})
    )
    date_activity["rate_activity"] = pd.to_numeric(date_activity["rate_signal"], errors="coerce").abs()
    rows: list[dict[str, Any]] = []
    for split in splits:
        start = pd.Timestamp(split["test_start"]).normalize()
        end = pd.Timestamp(split["test_end"]).normalize()
        value = float(date_activity.loc[date_activity["date"].between(start, end), "rate_activity"].mean())
        bucket = "high_rbi" if np.isfinite(value) and value >= 0.20 else "low_rbi"
        rows.append({"window_id": int(split["window_id"]), "rate_activity": value, "bucket": bucket})
    return pd.DataFrame(rows)


def _baseline_window_diagnostics(export_dir: Path, nb01_dir: Path | None) -> dict[str, Any]:
    if nb01_dir is None:
        return {}
    baseline_root = nb01_dir / "track_a_tree_baseline"
    if not baseline_root.exists():
        return {}

    payloads: dict[str, dict[str, Any]] = {}
    for filename, label in [
        ("xgboost_final.json", "XGBoost"),
        ("lightgbm_final.json", "LightGBM"),
        ("catboost_final.json", "CatBoost"),
    ]:
        path = baseline_root / filename
        if path.exists():
            payloads[label] = _load_model_payload(path)
    if not payloads:
        return {}

    features_df, _, _, _ = load_export_artifacts(export_dir)
    feature_cols = [col for col in features_df.columns if col not in {"date", "ticker", "target_weekly_return"}]
    model_rows: list[dict[str, Any]] = []
    ic_vectors: dict[str, list[float]] = {}
    worst_windows: dict[str, list[dict[str, Any]]] = {}

    for model_name, payload in payloads.items():
        windows = _valid_windows(payload)
        ic_values = [float(window.get("test_ic", float("nan"))) for window in windows if np.isfinite(window.get("test_ic", np.nan))]
        ic_vectors[model_name] = ic_values
        ranked = sorted(windows, key=lambda row: float(row.get("test_ic", float("inf"))))
        culprits: list[dict[str, Any]] = []
        for window in ranked[:5]:
            start = pd.Timestamp(window["test_start"]).normalize()
            end = pd.Timestamp(window["test_end"]).normalize()
            subset = features_df.loc[features_df["date"].between(start, end)].copy()
            culprit = None
            culprit_ic = float("nan")
            for feature in feature_cols[: min(len(feature_cols), 120)]:
                values: list[float] = []
                for _, group in subset.groupby("date", sort=True):
                    local = group[[feature, "target_weekly_return"]].replace([np.inf, -np.inf], np.nan).dropna()
                    if len(local) < 8:
                        continue
                    corr = local[feature].corr(local["target_weekly_return"], method="spearman")
                    if pd.notna(corr):
                        values.append(float(corr))
                mean_ic = _safe_mean(values)
                if culprit is None or (np.isfinite(mean_ic) and mean_ic < culprit_ic):
                    culprit = feature
                    culprit_ic = mean_ic
            culprits.append(
                {
                    "window_id": int(window["window_id"]),
                    "test_ic": float(window.get("test_ic", float("nan"))),
                    "dominant_negative_feature_proxy": culprit,
                    "dominant_negative_feature_ic": culprit_ic,
                }
            )
        worst_windows[model_name] = culprits
        model_rows.append(
            {
                "model": model_name,
                "durbin_watson": _durbin_watson(ic_values),
                "mean_test_ic": _safe_mean(ic_values),
                "windows_completed": len(ic_values),
            }
        )

    corr_rows: list[dict[str, Any]] = []
    model_names = sorted(ic_vectors)
    for left_name in model_names:
        for right_name in model_names:
            left = np.asarray(ic_vectors.get(left_name, []), dtype=float)
            right = np.asarray(ic_vectors.get(right_name, []), dtype=float)
            if left.size == 0 or right.size == 0:
                corr = float("nan")
            else:
                n = min(len(left), len(right))
                corr = float(pd.Series(left[:n]).corr(pd.Series(right[:n]), method="spearman"))
            corr_rows.append({"left_model": left_name, "right_model": right_name, "window_ic_corr": corr})
    return {
        "model_diagnostics": model_rows,
        "window_ic_correlation": corr_rows,
        "worst_window_feature_proxy": worst_windows,
    }


def main() -> int:
    args = parse_args()
    export_artifacts = resolve_export_dir(args.export_dir)
    output_dir = args.output_dir.expanduser().resolve() if args.output_dir else make_run_dir(None, "nb02_failed_model_autopsy")
    output_dir.mkdir(parents=True, exist_ok=True)

    features_df, splits, _, metadata_df = load_export_artifacts(export_artifacts.export_dir)
    selected_features = _tier12_selected_features(export_artifacts.export_dir, args.nb00_report)
    subsets = _prepare_subsets(export_artifacts.export_dir, output_dir, metadata_df, selected_features, features_df)

    large_cap_state = _run_track_a_sequence(
        subsets["large_cap_export"],
        output_dir / "models" / "lstm_large_cap",
        profile=args.profile,
        max_splits=args.max_splits,
        model_filter=["lstm"],
    )
    full_sequence_state = _run_track_a_sequence(
        export_artifacts.export_dir,
        output_dir / "models" / "sequence_full",
        profile=args.profile,
        max_splits=args.max_splits,
        model_filter=["tcn", "transformer"],
        sequence_overrides={"transformer": {"d_model": 64, "nhead": 8, "num_encoder_layers": 3, "dim_feedforward": 128}},
    )
    rate_stable_state = _run_track_b_frontier(
        subsets["rate_stable_export"],
        output_dir / "models" / "frontier_rate_stable",
        profile=args.profile,
        max_splits=args.max_splits,
    )
    reduced97_state = _run_track_b_frontier(
        subsets["reduced97_export"],
        output_dir / "models" / "frontier_reduced97",
        profile=args.profile,
        max_splits=args.max_splits,
        feature_mode="reduced",
        reduced_feature_count=60,
        frontier_overrides={"itransformer": {"d_model": 32, "n_heads": 4, "n_layers": 2, "d_ff": 128}},
    )

    lstm_results, lstm_summary, lstm_stability = _summary_from_state(large_cap_state, "LSTM")
    tcn_results, tcn_summary, tcn_stability = _summary_from_state(full_sequence_state, "TCN")
    transformer_results, transformer_summary, transformer_stability = _summary_from_state(full_sequence_state, "Transformer")
    _, tft_summary, tft_stability = _summary_from_state(rate_stable_state, "TFT")
    _, itransformer_summary, itransformer_stability = _summary_from_state(reduced97_state, "iTransformer")

    rate_table = _window_rate_activity(features_df, splits)
    tcn_window_frame = pd.DataFrame(_valid_windows(tcn_results)) if tcn_results else pd.DataFrame()
    tcn_bucket_summary: dict[str, Any] = {}
    if not tcn_window_frame.empty and not rate_table.empty:
        tcn_window_frame = tcn_window_frame.merge(rate_table, on="window_id", how="left", sort=False)
        bucket_stats = (
            tcn_window_frame.groupby("bucket", as_index=False)["test_ic"]
            .agg(["mean", "count"])
            .reset_index()
            .rename(columns={"mean": "mean_test_ic", "count": "n_windows"})
        )
        tcn_bucket_summary = {
            row["bucket"]: {
                "mean_test_ic": float(row["mean_test_ic"]),
                "n_windows": int(row["n_windows"]),
            }
            for _, row in bucket_stats.iterrows()
        }
        tcn_window_frame.to_csv(output_dir / "tcn_window_rate_activity.csv", index=False)

    patchtst_section: dict[str, Any]
    if args.patchtst_result_path is not None and args.patchtst_result_path.exists():
        patch_payload = _load_model_payload(args.patchtst_result_path)
        patchtst_section = {
            "status": "provided_artifact",
            "prepared_export_dir": str(subsets["mid_cap_export"]),
            "summary": dict(patch_payload.get("summary") or {}),
            "note": "PatchTST remains external to the shared Track B runner; this script consumes the supplied artifact safely.",
        }
    else:
        patchtst_section = {
            "status": "external_artifact_required",
            "prepared_export_dir": str(subsets["mid_cap_export"]),
            "prior_full_universe_ic": PRIOR_PATCHTST_BASELINE_IC,
            "note": "A mid-cap export has been prepared for the dedicated PatchTST notebook path. No native PatchTST trainer exists in the shared weekly runner, so this notebook records the handoff explicitly instead of fabricating a result.",
        }

    diagnostics = _baseline_window_diagnostics(export_artifacts.export_dir, args.nb01_dir)

    model_rows = [
        {
            "model": "LSTM",
            "stratum": "large_cap_top40pct",
            "mean_ic": float(lstm_summary.get("mean_test_ic", float("nan"))),
            "ic_ir": float(lstm_summary.get("ic_ir", float("nan"))),
            "ratio": float(lstm_summary.get("mean_train_test_ratio", float("nan"))),
            "hit_rate": float(lstm_summary.get("mean_hit_rate", float("nan"))),
            "windows_completed": int(lstm_summary.get("windows_completed", 0) or 0),
            "hypothesis_confirmed": bool(float(lstm_summary.get("mean_test_ic", float("nan")) or float("nan")) > 0.020),
        },
        {
            "model": "TCN",
            "stratum": "full_universe_rate_activity_split",
            "mean_ic": float(tcn_summary.get("mean_test_ic", float("nan"))),
            "ic_ir": float(tcn_summary.get("ic_ir", float("nan"))),
            "ratio": float(tcn_summary.get("mean_train_test_ratio", float("nan"))),
            "hit_rate": float(tcn_summary.get("mean_hit_rate", float("nan"))),
            "windows_completed": int(tcn_summary.get("windows_completed", 0) or 0),
            "hypothesis_confirmed": bool(
                float(tcn_bucket_summary.get("high_rbi", {}).get("mean_test_ic", float("nan")) or float("nan"))
                > float(tcn_bucket_summary.get("low_rbi", {}).get("mean_test_ic", float("-inf")) or float("-inf"))
            ),
        },
        {
            "model": "TFT",
            "stratum": "rate_stable",
            "mean_ic": float(tft_summary.get("mean_test_ic", float("nan"))),
            "ic_ir": float(tft_summary.get("ic_ir", float("nan"))),
            "ratio": float(tft_summary.get("mean_train_test_ratio", float("nan"))),
            "hit_rate": float(tft_summary.get("mean_hit_rate", float("nan"))),
            "windows_completed": int(tft_summary.get("windows_completed", 0) or 0),
            "prior_full_universe_ic": PRIOR_TFT_BASELINE_IC,
            "hypothesis_confirmed": bool(float(tft_summary.get("mean_test_ic", float("nan")) or float("nan")) > PRIOR_TFT_BASELINE_IC + 0.010),
        },
        {
            "model": "iTransformer",
            "stratum": "top97_reduced60",
            "mean_ic": float(itransformer_summary.get("mean_test_ic", float("nan"))),
            "ic_ir": float(itransformer_summary.get("ic_ir", float("nan"))),
            "ratio": float(itransformer_summary.get("mean_train_test_ratio", float("nan"))),
            "hit_rate": float(itransformer_summary.get("mean_hit_rate", float("nan"))),
            "windows_completed": int(itransformer_summary.get("windows_completed", 0) or 0),
            "hypothesis_confirmed": bool(float(itransformer_summary.get("mean_test_ic", float("nan")) or float("nan")) > 0.015),
        },
        {
            "model": "Transformer",
            "stratum": "full_universe_dmodel64",
            "mean_ic": float(transformer_summary.get("mean_test_ic", float("nan"))),
            "ic_ir": float(transformer_summary.get("ic_ir", float("nan"))),
            "ratio": float(transformer_summary.get("mean_train_test_ratio", float("nan"))),
            "hit_rate": float(transformer_summary.get("mean_hit_rate", float("nan"))),
            "windows_completed": int(transformer_summary.get("windows_completed", 0) or 0),
            "hypothesis_confirmed": bool(float(transformer_summary.get("mean_test_ic", float("nan")) or float("nan")) > 0.010),
        },
    ]

    summary_table = pd.DataFrame(model_rows)
    summary_table.to_csv(output_dir / "autopsy_model_summary.csv", index=False)
    summary_table.to_parquet(output_dir / "autopsy_model_summary.parquet", index=False)

    payload = {
        "generated_at": pd.Timestamp.utcnow().tz_localize(None).isoformat(),
        "export_dir": str(export_artifacts.export_dir),
        "prepared_exports": {key: str(value) for key, value in subsets.items()},
        "models": model_rows,
        "model_details": {
            "LSTM": {"summary": lstm_summary, "stability": lstm_stability},
            "TCN": {"summary": tcn_summary, "stability": tcn_stability, "rate_bucket_summary": tcn_bucket_summary},
            "TFT": {"summary": tft_summary, "stability": tft_stability},
            "iTransformer": {"summary": itransformer_summary, "stability": itransformer_stability},
            "Transformer": {"summary": transformer_summary, "stability": transformer_stability},
            "PatchTST": patchtst_section,
        },
        "baseline_window_diagnostics": diagnostics,
    }
    write_json(output_dir / "autopsy_results.json", payload)
    print(json.dumps(json_ready({"models": model_rows, "prepared_exports": payload["prepared_exports"]}), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
