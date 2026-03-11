from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import numpy as np
import pandas as pd

from src.research.alpha_lab import AlphaHypothesis, AlphaLabController, AlphaLabStore, AlphaLabThresholds
from src.research.research_types import ResearchDataset, ResearchWindowResult


@dataclass
class _DummyPipeline:
    def run(self, model: Dict[str, Any], dataset: ResearchDataset) -> Dict[str, Any]:
        score = float(model.get("score", 0.0))
        windows = [
            ResearchWindowResult(
                train_start="2020-01-01",
                train_end="2020-01-05",
                test_start="2020-01-06",
                test_end="2020-01-07",
                n_train=5,
                n_test=2,
                metrics={
                    "train_sharpe": score + 0.1,
                    "sharpe": score,
                    "max_drawdown": 0.10,
                    "turnover": 0.50,
                    "stress_drag": 0.20,
                },
            ),
            ResearchWindowResult(
                train_start="2020-01-08",
                train_end="2020-01-12",
                test_start="2020-01-13",
                test_end="2020-01-14",
                n_train=5,
                n_test=2,
                metrics={
                    "train_sharpe": score + 0.05,
                    "sharpe": score,
                    "max_drawdown": 0.12,
                    "turnover": 0.45,
                    "stress_drag": 0.18,
                },
            ),
        ]
        return {
            "windows": windows,
            "aggregate_metrics": {
                "stability_score": 0.80,
                "avg_sharpe": score,
                "avg_max_drawdown": 0.11,
                "avg_turnover": 0.475,
            },
        }


def _dataset() -> ResearchDataset:
    index = pd.date_range("2020-01-01", periods=10, freq="D")
    frame = pd.DataFrame({"x": np.arange(10), "y": np.arange(10)}, index=index)
    return ResearchDataset(
        X=np.zeros((10, 1)),
        y=np.zeros(10),
        feature_names=["x"],
        metadata={},
        index=index,
        tickers=np.array(["AAA"] * 10),
        frame=frame,
    )


def test_alpha_lab_suite_is_deterministic_and_promotes_survivors(tmp_path):
    store = AlphaLabStore(db_path=str(tmp_path / "alpha_lab.db"))
    controller = AlphaLabController(pipeline=_DummyPipeline(), store=store)
    hypothesis = AlphaHypothesis(
        name="deterministic_hypothesis",
        model_factory=lambda params: dict(params),
        parameter_grid={"score": [0.90, 0.40]},
    )
    dataset = _dataset()
    first = controller.run_hypothesis_suite(dataset=dataset, hypotheses=[hypothesis])
    second = controller.run_hypothesis_suite(dataset=dataset, hypotheses=[hypothesis])
    store.close()

    assert first["evaluated_count"] == 2
    assert first["survivor_count"] == 1
    first_rows = sorted(
        [(r["parameter_hash"], bool(r["promoted"]), str(r["reason"])) for r in first["evaluated"]],
        key=lambda x: x[0],
    )
    second_rows = sorted(
        [(r["parameter_hash"], bool(r["promoted"]), str(r["reason"])) for r in second["evaluated"]],
        key=lambda x: x[0],
    )
    assert first_rows == second_rows


def test_alpha_lab_promotion_hook_and_store_contract(tmp_path):
    store = AlphaLabStore(db_path=str(tmp_path / "alpha_lab.db"))
    controller = AlphaLabController(pipeline=_DummyPipeline(), store=store)
    hypothesis = AlphaHypothesis(
        name="promotion_hook_case",
        model_factory=lambda params: dict(params),
        parameter_grid={"score": [0.95]},
    )
    suite = controller.run_hypothesis_suite(dataset=_dataset(), hypotheses=[hypothesis])
    assert suite["survivor_count"] == 1
    survivor = suite["survivors"][0]

    fetched_rows = store.fetch_fold_rows(survivor["hypothesis_name"], survivor["parameter_hash"])
    assert len(fetched_rows) == 2

    def _hook(payload: Dict[str, Any]):
        score = float(payload.get("aggregate_metrics", {}).get("avg_sharpe", 0.0))
        if score >= 0.90:
            return True, "certified"
        return False, "not_certified"

    promotions = controller.promote_survivors(suite["survivors"], certification_hook=_hook)
    store.close()
    assert promotions["promotion_count"] == 1
    assert promotions["promotions"][0]["promoted"] is True
    assert promotions["promotions"][0]["reason"] == "certified"


def test_alpha_lab_phase2_surface_fields_and_grid_cap(tmp_path):
    store = AlphaLabStore(db_path=str(tmp_path / "alpha_lab.db"))
    thresholds = AlphaLabThresholds(phase2_max_parameter_combinations=4)
    controller = AlphaLabController(pipeline=_DummyPipeline(), store=store, thresholds=thresholds)
    hypothesis = AlphaHypothesis(
        name="phase2_surface_case",
        model_factory=lambda params: dict(params),
        parameter_grid={"score": [0.95, 0.90, 0.85, 0.80, 0.75], "decay": [1, 2]},
    )
    suite = controller.run_hypothesis_suite(dataset=_dataset(), hypotheses=[hypothesis])
    store.close()

    assert suite["evaluated_count"] == 4
    assert suite["survivor_count"] <= suite["evaluated_count"]
    for row in suite["evaluated"]:
        assert "surface_metrics" in row
        assert row["phase2_status"] in {"candidate", "reject"}
        assert isinstance(row["phase2_grid_truncated"], bool)
