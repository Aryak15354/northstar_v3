#!/usr/bin/env python3
"""NB-07: final ensemble, TRA, and deployment diagnosis for the weekly sprint."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SHARED_DIR = PROJECT_ROOT / "notebooks" / "kaggle_sprint" / "shared"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

def _load_shared_module(module_name: str):
    try:
        return __import__(module_name)
    except ModuleNotFoundError:
        module_path = SHARED_DIR / f"{module_name}.py"
        if not module_path.exists():
            raise FileNotFoundError(f"missing_shared_kaggle_module:{module_path}")
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"unable_to_load_shared_kaggle_module:{module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module


_sprint_utils = _load_shared_module("sprint_utils")
EnsembleBuilder = _sprint_utils.EnsembleBuilder

from scripts.kaggle.week_2026_03_29.common import (  # noqa: E402
    load_export_artifacts,
    make_run_dir,
    read_json,
    resolve_export_dir,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NB-07 ensemble, TRA, and deployment diagnosis.")
    parser.add_argument("--export-dir", type=Path, required=True)
    parser.add_argument("--nb01-dir", type=Path, required=True)
    parser.add_argument("--nb02-dir", type=Path, required=True)
    parser.add_argument("--nb03-dir", type=Path, default=None)
    parser.add_argument("--nb05-dir", type=Path, default=None)
    parser.add_argument("--nb06-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def _load_payload_if_exists(path: Path) -> dict[str, Any]:
    return read_json(path) if path.exists() else {}


def _load_model_payloads(nb01_dir: Path, nb02_dir: Path) -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    for filename in ["xgboost_final.json", "lightgbm_final.json", "catboost_final.json"]:
        path = nb01_dir / "track_a_tree_baseline" / filename
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["_source"] = "NB01"
            payloads[filename.replace("_final.json", "")] = payload
    for relative in [
        ("models/lstm_large_cap/lstm_final.json", "lstm_large_cap"),
        ("models/sequence_full/tcn_final.json", "tcn_full"),
        ("models/sequence_full/transformer_final.json", "transformer64_full"),
        ("models/frontier_rate_stable/tft_final.json", "tft_rate_stable"),
        ("models/frontier_reduced97/itransformer_final.json", "itransformer_reduced97"),
    ]:
        path = nb02_dir / relative[0]
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["_source"] = "NB02"
            payloads[relative[1]] = payload
    return payloads


def _valid_windows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [window for window in list(payload.get("windows") or []) if "error" not in window]


def _full_signature(payload: dict[str, Any]) -> tuple[tuple[int, str, str, int], ...]:
    rows = []
    for window in _valid_windows(payload):
        rows.append(
            (
                int(window.get("window_id", 0)),
                str(window.get("test_start", "")),
                str(window.get("test_end", "")),
                int(len(window.get("y_test", []) or [])),
            )
        )
    return tuple(rows)


def _summary_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("summary") or {})


def _ema_score(history: list[float], alpha: float = 0.2, lookback: int = 4) -> float:
    values = [float(value) for value in history[-lookback:] if np.isfinite(value)]
    if not values:
        return 0.01
    score = values[0]
    for value in values[1:]:
        score = alpha * value + (1.0 - alpha) * score
    return max(float(score), 0.01)


def _window_regime_lookup(regimes_df: pd.DataFrame, splits: list[dict[str, Any]]) -> dict[int, str]:
    lookup: dict[int, str] = {}
    for split in splits:
        start = pd.Timestamp(split["test_start"]).normalize()
        end = pd.Timestamp(split["test_end"]).normalize()
        subset = regimes_df.loc[regimes_df["date"].between(start, end), "plan_regime_id"]
        if subset.empty:
            lookup[int(split["window_id"])] = "unknown"
        else:
            lookup[int(split["window_id"])] = str(subset.mode().iloc[0]) if not subset.mode().empty else str(subset.iloc[0])
    return lookup


def _ensemble_section(model_payloads: dict[str, dict[str, Any]], regimes_df: pd.DataFrame, splits: list[dict[str, Any]]) -> dict[str, Any]:
    signatures: dict[tuple[tuple[int, str, str, int], ...], list[str]] = {}
    for model_name, payload in model_payloads.items():
        summary = _summary_from_payload(payload)
        if float(summary.get("ic_ir", float("-inf")) or float("-inf")) <= 0.30:
            continue
        signature = _full_signature(payload)
        if not signature:
            continue
        signatures.setdefault(signature, []).append(model_name)
    if not signatures:
        return {"status": "insufficient_models"}

    base_signature = max(signatures.items(), key=lambda item: len(item[1]))[0]
    eligible_models = sorted(signatures[base_signature])
    if len(eligible_models) < 2:
        return {"status": "insufficient_models", "eligible_models": eligible_models}

    regime_lookup = _window_regime_lookup(regimes_df, splits)
    builder = EnsembleBuilder()
    rows: list[dict[str, Any]] = []
    ic_history: dict[str, list[float]] = {model_name: [] for model_name in eligible_models}

    payload_windows = {model_name: {int(window["window_id"]): window for window in _valid_windows(model_payloads[model_name])} for model_name in eligible_models}

    for window_id, _, _, _ in base_signature:
        model_predictions: dict[str, np.ndarray] = {}
        y_test = None
        for model_name in eligible_models:
            window = payload_windows[model_name].get(int(window_id))
            if window is None:
                continue
            preds = np.asarray(window.get("test_preds", []), dtype=float)
            target = np.asarray(window.get("y_test", []), dtype=float)
            if preds.size == 0 or target.size == 0 or preds.size != target.size:
                continue
            model_predictions[model_name] = preds
            if y_test is None:
                y_test = target
        if y_test is None or len(model_predictions) < 2:
            continue

        weights = {name: _ema_score(ic_history.get(name, []), alpha=0.2, lookback=4) for name in model_predictions}
        if regime_lookup.get(int(window_id)) in {"R4", "R9"} and "catboost" in model_predictions:
            weights["catboost"] = max(weights.get("catboost", 0.0), 0.70)
        weight_sum = sum(weights.values())
        normalized_weights = {name: value / weight_sum for name, value in weights.items()}
        ensemble_pred = np.average(
            np.vstack([model_predictions[name] for name in normalized_weights]),
            axis=0,
            weights=np.asarray([normalized_weights[name] for name in normalized_weights], dtype=float),
        )
        gain = builder.evaluate_gain(
            ensemble_pred,
            model_predictions,
            y_test,
        )
        gain["window_id"] = int(window_id)
        gain["regime"] = regime_lookup.get(int(window_id), "unknown")
        gain["weights"] = normalized_weights
        rows.append(gain)
        for model_name in eligible_models:
            window = payload_windows[model_name].get(int(window_id))
            if window is not None and np.isfinite(window.get("test_ic", np.nan)):
                ic_history[model_name].append(float(window.get("test_ic", 0.0)))

    if not rows:
        return {"status": "insufficient_windows", "eligible_models": eligible_models}

    table = pd.DataFrame(rows)
    corr_rows: list[dict[str, Any]] = []
    for left_name in eligible_models:
        for right_name in eligible_models:
            left = [float(payload_windows[left_name][window_id]["test_ic"]) for window_id, _, _, _ in base_signature if window_id in payload_windows[left_name]]
            right = [float(payload_windows[right_name][window_id]["test_ic"]) for window_id, _, _, _ in base_signature if window_id in payload_windows[right_name]]
            n = min(len(left), len(right))
            corr = float(pd.Series(left[:n]).corr(pd.Series(right[:n]), method="spearman")) if n >= 2 else float("nan")
            corr_rows.append({"left_model": left_name, "right_model": right_name, "window_ic_corr": corr})
    return {
        "status": "ok",
        "eligible_models": eligible_models,
        "summary": {
            "mean_ensemble_ic": float(table["ensemble_ic"].mean()),
            "mean_best_single_ic": float(table["best_individual_ic"].mean()),
            "mean_ic_gain": float(table["ic_gain"].mean()),
            "ensemble_ic_ir": float(table["ensemble_ic"].mean() / table["ensemble_ic"].std(ddof=1)) if len(table) > 1 and float(table["ensemble_ic"].std(ddof=1)) > 0 else float("nan"),
            "pass_criterion": bool(float(table["ic_gain"].mean()) >= -0.05),
        },
        "window_rows": table.to_dict("records"),
        "correlation_matrix": corr_rows,
    }


def _softmax(values: np.ndarray) -> np.ndarray:
    shifted = values - np.nanmax(values)
    exp = np.exp(shifted)
    denom = np.nansum(exp)
    return exp / denom if denom > 0 else np.ones_like(values) / max(len(values), 1)


def _tra_section(ensemble: dict[str, Any], model_payloads: dict[str, dict[str, Any]], regimes_df: pd.DataFrame, splits: list[dict[str, Any]], features_df: pd.DataFrame) -> dict[str, Any]:
    if ensemble.get("status") != "ok":
        return {"status": "skipped", "reason": "ensemble_not_ready"}
    eligible_models = list(ensemble.get("eligible_models") or [])
    if len(eligible_models) < 2:
        return {"status": "skipped", "reason": "insufficient_models"}

    regime_lookup = _window_regime_lookup(regimes_df, splits)
    payload_windows = {model_name: {int(window["window_id"]): window for window in _valid_windows(model_payloads[model_name])} for model_name in eligible_models}
    common_window_ids = sorted(set.intersection(*(set(windows) for windows in payload_windows.values())))
    if len(common_window_ids) < 8:
        return {"status": "skipped", "reason": "insufficient_common_windows"}

    rate_feature = "rbi_repo_rate_change_13w" if "rbi_repo_rate_change_13w" in features_df.columns else None
    rate_activity_by_window: dict[int, float] = {}
    if rate_feature is not None:
        daily = features_df.groupby("date", as_index=False)[rate_feature].mean(numeric_only=True)
        for split in splits:
            start = pd.Timestamp(split["test_start"]).normalize()
            end = pd.Timestamp(split["test_end"]).normalize()
            rate_activity_by_window[int(split["window_id"])] = float(
                pd.to_numeric(daily.loc[daily["date"].between(start, end), rate_feature], errors="coerce").abs().mean()
            )

    rows: list[dict[str, Any]] = []
    window_ic_map = {
        model_name: {window_id: float(payload_windows[model_name][window_id].get("test_ic", float("nan"))) for window_id in common_window_ids}
        for model_name in eligible_models
    }
    for idx in range(4, len(common_window_ids)):
        window_id = common_window_ids[idx]
        history_ids = common_window_ids[idx - 4 : idx]
        feature_row: dict[str, Any] = {"window_id": int(window_id)}
        for model_name in eligible_models:
            hist = [window_ic_map[model_name].get(hist_id, float("nan")) for hist_id in history_ids]
            feature_row[f"{model_name}_ic_ema"] = _ema_score(hist, alpha=0.2, lookback=4)
        feature_row["regime"] = regime_lookup.get(int(window_id), "unknown")
        feature_row["rbi_active"] = 1.0 if rate_activity_by_window.get(int(window_id), 0.0) >= 0.20 else 0.0
        best_model = max(eligible_models, key=lambda name: window_ic_map[name].get(window_id, float("-inf")))
        feature_row["best_model"] = best_model
        rows.append(feature_row)
    router_df = pd.DataFrame(rows)
    if router_df.empty:
        return {"status": "skipped", "reason": "router_dataset_empty"}

    test_rows = router_df.iloc[10:].copy() if len(router_df) > 10 else router_df.iloc[-min(3, len(router_df)) :].copy()
    eval_rows: list[dict[str, Any]] = []
    for _, row in test_rows.iterrows():
        scores = np.asarray([float(row[f"{model_name}_ic_ema"]) for model_name in eligible_models], dtype=float)
        if row["regime"] in {"R4", "R9"} and "catboost" in eligible_models:
            scores[eligible_models.index("catboost")] = max(scores[eligible_models.index("catboost")], 0.70)
        weights = _softmax(scores)
        window_id = int(row["window_id"])
        first_window = payload_windows[eligible_models[0]][window_id]
        y_test = np.asarray(first_window.get("y_test", []), dtype=float)
        preds = np.average(
            np.vstack([np.asarray(payload_windows[model_name][window_id].get("test_preds", []), dtype=float) for model_name in eligible_models]),
            axis=0,
            weights=weights,
        )
        ic = float(pd.Series(preds).corr(pd.Series(y_test), method="spearman")) if len(preds) == len(y_test) and len(y_test) >= 5 else float("nan")
        eval_rows.append(
            {
                "window_id": window_id,
                "regime": row["regime"],
                "router_weights": {model_name: float(weight) for model_name, weight in zip(eligible_models, weights, strict=False)},
                "test_ic": ic,
                "best_model_realized": row["best_model"],
            }
        )
    eval_df = pd.DataFrame(eval_rows)
    return {
        "status": "ok",
        "eligible_models": eligible_models,
        "router_train_windows": int(min(10, max(len(router_df) - len(test_rows), 0))),
        "router_test_windows": int(len(eval_df)),
        "summary": {
            "mean_test_ic": float(eval_df["test_ic"].mean()) if not eval_df.empty else float("nan"),
            "ic_ir": float(eval_df["test_ic"].mean() / eval_df["test_ic"].std(ddof=1)) if len(eval_df) > 1 and float(eval_df["test_ic"].std(ddof=1)) > 0 else float("nan"),
            "mean_max_weight": float(pd.Series([max(weights.values()) for weights in eval_df["router_weights"]]).mean()) if not eval_df.empty else float("nan"),
        },
        "window_rows": eval_df.to_dict("records") if not eval_df.empty else [],
    }


def _recursive_matches(obj: Any, keywords: list[str]) -> list[tuple[str, Any]]:
    found: list[tuple[str, Any]] = []
    queue = [([], obj)]
    while queue:
        path, current = queue.pop(0)
        if isinstance(current, dict):
            for key, value in current.items():
                new_path = path + [str(key)]
                if any(keyword in str(key).lower() for keyword in keywords):
                    found.append((".".join(new_path), value))
                queue.append((new_path, value))
        elif isinstance(current, list):
            for idx, value in enumerate(current[:50]):
                queue.append((path + [str(idx)], value))
    return found


def _deployment_diagnosis() -> dict[str, Any]:
    state_path = PROJECT_ROOT / "data" / "state" / "unified_state.json"
    runtime_db = PROJECT_ROOT / "data" / "runtime" / "portfolio_runtime.db"
    governor_config_path = PROJECT_ROOT / "config" / "portfolio_governor_config.yaml"

    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    governor_config = yaml.safe_load(governor_config_path.read_text(encoding="utf-8")) if governor_config_path.exists() else {}

    no_edge_matches = _recursive_matches(state, ["no_edge", "edge"])
    recovery_matches = _recursive_matches(state, ["recovery", "counter", "drawdown"])
    convexity_matches = _recursive_matches(state, ["convex", "caution_score"])
    governor_state = dict(state.get("governor_state", {}) or {})
    market_state = dict(state.get("market", {}) or {})
    portfolio_state = dict(state.get("portfolio", {}) or {})

    risk_budget = {"status": "unknown"}
    if runtime_db.exists():
        conn = sqlite3.connect(runtime_db)
        try:
            cursor = conn.cursor()
            tables = {row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "proposal_inbox" in tables:
                rows = cursor.execute("SELECT status FROM proposal_inbox").fetchall()
                statuses = pd.Series([str(row[0] or "UNKNOWN").lower() for row in rows])
                denied = float((statuses.isin(["denied", "rejected"])).mean()) if not statuses.empty else float("nan")
                risk_budget = {"status": "ok" if np.isfinite(denied) and denied <= 0.20 else "fail", "denial_rate": denied}
        finally:
            conn.close()

    forced_regimes = []
    for regime_name, config in dict(governor_config.get("regime_table") or {}).items():
        forced_regimes.append(
            {
                "regime": regime_name,
                "equity_fraction": float(config.get("equity_fraction", float("nan"))),
                "options_fraction": float(config.get("options_fraction", float("nan"))),
                "cash_fraction": float(config.get("cash_fraction", float("nan"))),
            }
        )

    return {
        "no_edge_detector": {
            "status": "fail" if any("true" in str(value).lower() or "no_edge" == str(value).lower() for _, value in no_edge_matches) else "ok",
            "matches": no_edge_matches[:20],
        },
        "recovery_counter": {
            "status": "fail" if any("recovery" in str(value).lower() and "0" not in str(value) for _, value in recovery_matches) else "ok",
            "matches": recovery_matches[:20],
        },
        "governor_capital_structure": {
            "status": "fail" if str(governor_state.get("capital_structure_regime", "")).upper() == "CAPITAL_PRESERVATION" or float(governor_state.get("equity_fraction", 1.0) or 1.0) <= 0.20 else "ok",
            "capital_structure_regime": governor_state.get("capital_structure_regime"),
            "equity_fraction": governor_state.get("equity_fraction"),
            "allowed_exposure": market_state.get("allowed_exposure"),
        },
        "risk_budget_gate": risk_budget,
        "convexity_score_veto": {
            "status": "fail" if any(float(value) > 0.50 for path, value in convexity_matches if path.endswith("caution_score") and str(value).replace(".", "", 1).isdigit()) else "ok",
            "matches": convexity_matches[:20],
        },
        "kelly_allocator": {
            "status": "fail" if float(portfolio_state.get("target_total_exposure", 1.0) or 1.0) < 0.20 else "ok",
            "target_total_exposure": portfolio_state.get("target_total_exposure"),
            "total_exposure": portfolio_state.get("total_exposure"),
        },
        "forced_regime_table": forced_regimes,
    }


def _verdict(baseline_results: dict[str, Any], ensemble: dict[str, Any], tra: dict[str, Any], deployment: dict[str, Any], nb06: dict[str, Any]) -> dict[str, Any]:
    def _metric(value: Any, fallback: float) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return fallback
        return numeric if np.isfinite(numeric) else fallback

    models = list(baseline_results.get("models") or [])
    best_model = max(models, key=lambda row: _metric(row.get("mean_ic"), float("-inf"))) if models else {}
    deployment_failures = [name for name, value in deployment.items() if isinstance(value, dict) and value.get("status") == "fail"]
    india_confirmed = sum(1 for key, value in dict(nb06.get("results") or {}).items() if isinstance(value, dict) and value.get("status") == "confirmed")
    verdict = "C"
    note = "Diagnosis memo only."
    if (
        _metric(best_model.get("mean_ic"), float("-inf")) > 0.030
        and _metric(best_model.get("ratio"), float("inf")) < 1.8
        and not deployment_failures
    ):
        verdict = "A"
        note = "Primary gates pass cleanly; full promotion case is supportable."
    elif (
        _metric(best_model.get("mean_ic"), float("-inf")) > 0.015
        and _metric(best_model.get("ratio"), float("inf")) < 2.5
    ):
        verdict = "B"
        note = "Model quality is viable, but deployment or regime robustness still needs caution."
    return {
        "verdict": verdict,
        "best_model": best_model,
        "ensemble_pass": bool(dict(ensemble.get("summary") or {}).get("pass_criterion", False)),
        "tra_ic_ir": dict(tra.get("summary") or {}).get("ic_ir"),
        "deployment_failures": deployment_failures,
        "confirmed_india_hypotheses": india_confirmed,
        "recommendation": note,
    }


def main() -> int:
    args = parse_args()
    export_artifacts = resolve_export_dir(args.export_dir)
    output_dir = args.output_dir.expanduser().resolve() if args.output_dir else make_run_dir(None, "nb07_ensemble_tra_deployment")
    output_dir.mkdir(parents=True, exist_ok=True)

    features_df, splits, regimes_df, _ = load_export_artifacts(export_artifacts.export_dir)
    model_payloads = _load_model_payloads(args.nb01_dir, args.nb02_dir)
    ensemble = _ensemble_section(model_payloads, regimes_df, splits)
    tra = _tra_section(ensemble, model_payloads, regimes_df, splits, features_df)
    deployment = _deployment_diagnosis()
    baseline_results = _load_payload_if_exists(args.nb01_dir / "baseline_results.json")
    nb03 = _load_payload_if_exists((args.nb03_dir or Path(".")) / "regime_feature_dict.json") if args.nb03_dir is not None else {}
    nb05 = _load_payload_if_exists((args.nb05_dir or Path(".")) / "cross_asset_results.json") if args.nb05_dir is not None else {}
    nb06 = _load_payload_if_exists((args.nb06_dir or Path(".")) / "india_hypothesis_results.json") if args.nb06_dir is not None else {}
    verdict = _verdict(baseline_results, ensemble, tra, deployment, nb06)

    payload = {
        "generated_at": pd.Timestamp.utcnow().tz_localize(None).isoformat(),
        "export_dir": str(export_artifacts.export_dir),
        "ensemble": ensemble,
        "tra": tra,
        "deployment_diagnosis": deployment,
        "context": {
            "baseline_results": baseline_results,
            "regime_dictionary_available": bool(nb03),
            "promoted_cross_asset": list(nb05.get("promoted_signals") or []),
            "india_hypothesis_results": nb06,
        },
        "final_verdict": verdict,
    }
    write_json(output_dir / "final_candidate_report.json", payload)
    print(json.dumps(verdict, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
