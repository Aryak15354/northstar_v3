from __future__ import annotations

import json

from src.dashboard.v3_data_hub import V3DataHub


def test_v3_data_hub_parses_legacy_artifacts_with_alpha_os_extension(tmp_path) -> None:
    processed = tmp_path / "data/processed"
    processed.mkdir(parents=True, exist_ok=True)

    capital_payload = {
        "strategy_allocations": {"core": 0.5, "hedge": 0.5},
        "timestamp": "2026-02-17T00:00:00+00:00",
        "alpha_os": {
            "mode": "shadow",
            "effective_strategy_weights": {"core": 0.4, "hedge": 0.6},
        },
    }
    regime_payload = {
        "regime": "transition",
        "timestamp": "2026-02-17T00:00:00+00:00",
        "alpha_os": {
            "probabilities": {"LOW_VOL": 0.25, "HIGH_VOL": 0.25, "CRISIS": 0.25, "TRANSITION": 0.25},
            "confidence": 0.0,
        },
    }
    (processed / "capital_allocations.json").write_text(json.dumps(capital_payload))
    (processed / "regime_intelligence_feed.json").write_text(json.dumps(regime_payload))

    hub = V3DataHub(project_root=tmp_path)
    cap = hub.capital_allocations()
    regime = hub.regime_intelligence_feed()
    assert cap is not None
    assert regime is not None
    assert "strategy_allocations" in cap
    assert "regime" in regime
    assert "alpha_os" in cap
    assert "alpha_os" in regime
