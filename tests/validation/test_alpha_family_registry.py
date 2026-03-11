from __future__ import annotations

import pytest

from src.research.alpha_lab import AlphaFamilyRegistry


def test_phase1_alpha_family_registry_loads_and_validates():
    registry = AlphaFamilyRegistry.from_yaml("config/alpha_family_registry.yaml")
    registry.require_valid()

    expected = {
        "momentum_cross_sectional",
        "mean_reversion_short_term",
        "liquidity_shock",
        "volatility_mispricing",
        "dispersion_rotation",
        "flow_pressure_imbalance",
        "earnings_drift",
        "factor_compression_expansion",
    }
    keys = set(registry.keys())
    assert expected.issubset(keys)

    momentum = registry.get("momentum_cross_sectional")
    assert momentum is not None
    assert "underreact" in momentum.hypothesis.lower()
    assert len(momentum.activation_variables) >= 2
    assert len(momentum.parameter_axes.get("lookback_days", [])) >= 4


def test_phase1_registry_validation_catches_missing_structural_fields():
    registry = AlphaFamilyRegistry.from_dict(
        {
            "version": 1,
            "families": {
                "broken_family": {
                    "label": "Broken Family",
                    "core_signal_form": "Rank(return_20d)",
                    "parameter_axes": {"lookback_days": [20]},
                }
            },
        }
    )
    errors = registry.validate()
    assert any("missing hypothesis" in e for e in errors)
    assert any("missing structural_rationale" in e for e in errors)
    assert any("missing activation_variables" in e for e in errors)
    with pytest.raises(ValueError):
        registry.require_valid()
