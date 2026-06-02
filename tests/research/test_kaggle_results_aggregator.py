from __future__ import annotations

import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK_PATH = ROOT / "notebooks" / "kaggle_v4_validation" / "nb_04_results_aggregator.ipynb"


def _model_payload(model: str, *, ic: float, ratio: float, hit: float, stability: float) -> dict:
    return {
        "model": model,
        "summary": {
            "mean_test_ic": ic,
            "mean_test_ic_all_windows": ic,
            "mean_test_ic_active_windows": ic,
            "ic_ir": ic * 10.0,
            "mean_train_test_ratio": ratio,
            "mean_hit_rate": hit,
            "mean_quintile_spread": ic * 2.0,
            "collapse_rate": 0.0,
            "n_inverted_windows": 0,
            "collapse_warning": "",
            "passed_viability_filter": ratio < 2.5 and hit > 0.51,
            "verdict": "QUALIFIED" if ratio < 2.5 and hit > 0.51 else "NOT_QUALIFIED",
        },
        "stability": {
            "mean_pairwise_correlation": stability,
            "band": "stable",
            "top_stable_features": ["piotroski_signal", "amihud_signal"],
            "top_unstable_features": [],
            "mean_importance_by_feature": {
                "piotroski_signal": 0.8,
                "amihud_signal": 0.6,
            },
            "top_features_by_mean_importance": [
                "piotroski_signal",
                "amihud_signal",
            ],
        },
        "windows": [
            {"window_id": 1, "regime": "bull", "test_ic": ic},
            {"window_id": 2, "regime": "bear", "test_ic": ic * 0.8},
        ],
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _execute_notebook(cwd: Path) -> dict:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    namespace: dict = {"__name__": "__main__"}
    old_cwd = Path.cwd()
    os.chdir(cwd)
    try:
        for cell in notebook["cells"]:
            if cell.get("cell_type") != "code":
                continue
            exec("".join(cell.get("source", [])), namespace)
    finally:
        os.chdir(old_cwd)
    return namespace


def test_results_aggregator_handles_mixed_track_outputs(tmp_path):
    kaggle_results = tmp_path / "kaggle_results"
    track_a_results = tmp_path / "track_a_results"
    track_b_results = tmp_path / "track_b_results"

    _write_json(
        track_b_results / "patchtst_final.json",
        _model_payload("patchtst", ic=0.031, ratio=1.8, hit=0.55, stability=0.82),
    )
    _write_json(
        kaggle_results / "catboost_final.json",
        _model_payload("catboost", ic=0.026, ratio=2.2, hit=0.53, stability=0.78),
    )

    _write_json(
        track_b_results / "track_b_frontier_full_results.json",
        {
            "all_model_summaries": {
                "PatchTST": _model_payload("patchtst", ic=0.031, ratio=1.8, hit=0.55, stability=0.82)["summary"],
                "TFT": _model_payload("tft", ic=0.024, ratio=2.1, hit=0.52, stability=0.76)["summary"],
                "iTransformer": _model_payload("itransformer", ic=0.022, ratio=2.4, hit=0.515, stability=0.74)["summary"],
            },
            "all_model_stabilities": {
                "PatchTST": _model_payload("patchtst", ic=0.031, ratio=1.8, hit=0.55, stability=0.82)["stability"],
                "TFT": _model_payload("tft", ic=0.024, ratio=2.1, hit=0.52, stability=0.76)["stability"],
                "iTransformer": _model_payload("itransformer", ic=0.022, ratio=2.4, hit=0.515, stability=0.74)["stability"],
            },
        },
    )
    _write_json(
        track_a_results / "track_a_classical_full_results.json",
        {
            "all_model_summaries": {
                "XGBoost": _model_payload("xgboost", ic=0.019, ratio=2.3, hit=0.518, stability=0.70)["summary"],
                "CatBoost": _model_payload("catboost", ic=0.026, ratio=2.2, hit=0.53, stability=0.78)["summary"],
                "LSTM": _model_payload("lstm", ic=0.017, ratio=2.6, hit=0.505, stability=0.68)["summary"],
                "TCN": _model_payload("tcn", ic=0.018, ratio=2.4, hit=0.514, stability=0.69)["summary"],
                "Transformer": _model_payload("transformer", ic=0.016, ratio=2.45, hit=0.512, stability=0.67)["summary"],
            },
            "all_model_stabilities": {
                "XGBoost": _model_payload("xgboost", ic=0.019, ratio=2.3, hit=0.518, stability=0.70)["stability"],
                "CatBoost": _model_payload("catboost", ic=0.026, ratio=2.2, hit=0.53, stability=0.78)["stability"],
                "LSTM": _model_payload("lstm", ic=0.017, ratio=2.6, hit=0.505, stability=0.68)["stability"],
                "TCN": _model_payload("tcn", ic=0.018, ratio=2.4, hit=0.514, stability=0.69)["stability"],
                "Transformer": _model_payload("transformer", ic=0.016, ratio=2.45, hit=0.512, stability=0.67)["stability"],
            },
        },
    )

    _execute_notebook(tmp_path)

    verdict_path = kaggle_results / "v4_validation_verdict.json"
    comparison_path = kaggle_results / "v4_validation_comparison.csv"
    sources_path = kaggle_results / "v4_validation_loaded_sources.json"

    assert verdict_path.exists()
    assert comparison_path.exists()
    assert sources_path.exists()

    verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    sources = json.loads(sources_path.read_text(encoding="utf-8"))

    assert verdict["loaded_models"] == [
        "patchtst",
        "tft",
        "itransformer",
        "xgboost",
        "catboost",
        "lstm",
        "tcn",
        "transformer",
    ]
    assert sources["patchtst"].endswith("track_b_results/patchtst_final.json")
    assert sources["tft"] == "track_b_combined"
    assert sources["itransformer"] == "track_b_combined"
    assert sources["catboost"].endswith("kaggle_results/catboost_final.json")
    assert sources["xgboost"] == "track_a_combined"


def test_results_aggregator_writes_verdict_when_no_artifacts_exist(tmp_path):
    _execute_notebook(tmp_path)

    verdict_path = tmp_path / "kaggle_results" / "v4_validation_verdict.json"
    sources_path = tmp_path / "kaggle_results" / "v4_validation_loaded_sources.json"

    assert verdict_path.exists()
    assert sources_path.exists()

    verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    sources = json.loads(sources_path.read_text(encoding="utf-8"))

    assert verdict["recommendation"] == "missing_upstream_artifacts"
    assert verdict["missing_upstream_artifacts"] is True
    assert verdict["loaded_models"] == []
    assert verdict["attached_inputs"] == []
    assert verdict["discovered_artifact_paths"] == []
    assert sources == {}
