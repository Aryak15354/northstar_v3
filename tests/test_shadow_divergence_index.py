from __future__ import annotations

from src.validation.shadow_divergence_index import ShadowDivergenceIndex


def test_shadow_divergence_index_computes_reasonable_score() -> None:
    sdi_engine = ShadowDivergenceIndex()
    payload = sdi_engine.update(
        alpha_weights={"short_vol": 0.8, "long_vol": 0.2},
        legacy_weights={"short_vol": 0.2, "long_vol": 0.8},
        alpha_convexity=0.18,
        legacy_convexity=0.05,
        alpha_expected_return=0.02,
        legacy_expected_return=0.005,
        regime_label="CRISIS",
    )
    assert 0.0 <= float(payload["sdi"]) <= 1.0
    assert payload["band"] in {
        "aligned",
        "moderate_divergence",
        "structural_divergence",
        "migration_instability",
    }
    assert payload["components"]["weight_divergence_l1"] >= 0.0
