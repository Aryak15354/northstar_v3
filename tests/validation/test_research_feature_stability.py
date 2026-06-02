from __future__ import annotations

from src.research.feature_stability import compute_feature_stability_report, map_feature_importance_names


def test_map_feature_importance_names_maps_adapter_keys_back_to_feature_names() -> None:
    mapped = map_feature_importance_names(
        {"f0": 1.5, "f2": 0.75, "raw_feature": 0.25},
        feature_names=["momentum_20d", "rsi_14", "credit_stress_flag"],
    )

    assert mapped == {
        "momentum_20d": 1.5,
        "credit_stress_flag": 0.75,
        "raw_feature": 0.25,
    }


def test_compute_feature_stability_report_flags_stable_windows() -> None:
    windows = [
        {
            "test_start": "2025-01-01",
            "test_end": "2025-01-31",
            "feature_importance": {"mom_20d": 5.0, "rsi_14": 3.0, "credit_flag": 1.0},
        },
        {
            "test_start": "2025-02-01",
            "test_end": "2025-02-28",
            "feature_importance": {"mom_20d": 4.8, "rsi_14": 2.8, "credit_flag": 1.2},
        },
        {
            "test_start": "2025-03-01",
            "test_end": "2025-03-31",
            "feature_importance": {"mom_20d": 5.1, "rsi_14": 3.1, "credit_flag": 1.1},
        },
    ]

    report = compute_feature_stability_report(windows, top_k=3)

    assert report["status"] == "ok"
    assert report["stability_band"] == "stable"
    assert report["mean_pairwise_rank_correlation"] > 0.99
    assert report["windows_with_feature_importance"] == 3


def test_compute_feature_stability_report_flags_unstable_windows() -> None:
    windows = [
        {
            "test_start": "2025-01-01",
            "test_end": "2025-01-31",
            "feature_importance": {"mom_20d": 9.0, "rsi_14": 3.0, "credit_flag": 1.0},
        },
        {
            "test_start": "2025-02-01",
            "test_end": "2025-02-28",
            "feature_importance": {"mom_20d": 1.0, "rsi_14": 9.0, "credit_flag": 3.0},
        },
        {
            "test_start": "2025-03-01",
            "test_end": "2025-03-31",
            "feature_importance": {"mom_20d": 3.0, "rsi_14": 1.0, "credit_flag": 9.0},
        },
    ]

    report = compute_feature_stability_report(windows, top_k=2)

    assert report["status"] == "ok"
    assert report["stability_band"] == "unstable"
    assert report["mean_pairwise_rank_correlation"] < 0.40
    assert report["most_unstable_features"]
