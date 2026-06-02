from __future__ import annotations

import numpy as np
import pandas as pd

import src.scoring.northstar_model as northstar_model


class _NegativePCA:
    def __init__(self, n_components: int = 1) -> None:
        self.n_components = n_components
        self.explained_variance_ratio_ = np.array([0.55])

    def fit_transform(self, X):
        del X
        return np.array([[-4.0], [-3.0], [-2.0], [-1.0]])


def test_pca_quality_score_flips_negative_orientation(monkeypatch) -> None:
    monkeypatch.setattr(northstar_model, "PCA", _NegativePCA)

    quality_df = pd.DataFrame(
        {
            "roe": [1.0, 2.0, 3.0, 4.0],
            "roa": [1.0, 2.0, 3.0, 4.0],
            "fcf_margin": [1.0, 2.0, 3.0, 4.0],
        }
    )

    score = northstar_model._compute_pca_quality_score(quality_df, reference_col="roe")

    assert score.iloc[-1] > score.iloc[0]


def test_partial_sector_neutralization_preserves_cross_sector_signal() -> None:
    scores = pd.Series([90.0, 80.0, 30.0, 20.0], index=["A1", "A2", "B1", "B2"])
    sectors = pd.Series(["Capital Goods", "Capital Goods", "Realty", "Realty"], index=scores.index)

    blended = northstar_model.apply_partial_sector_neutralization(scores, sectors, sector_weight=0.60)

    assert blended["A1"] > blended["B1"]
    assert blended["A1"] != blended["B1"]
