from __future__ import annotations

import json

from src.intelligence.shock_engine import shock_knowledge_base as shock_kb
from src.nlp.training.shock_impact_learner import ShockImpactLearner


def test_shock_impact_learner_overrides_static_profile_after_enough_events(tmp_path, monkeypatch):
    weights_path = tmp_path / "shock_impact_weights.json"
    learner = ShockImpactLearner({"nlp": {"shock_impact_learner": {"output_path": str(weights_path), "min_events_to_update": 5}}})

    static_profile = shock_kb.get_shock_profile("rate_hike_rbi")
    static_score = static_profile["sector_impacts"]["Information Technology"]["score"]

    for _ in range(6):
        learner.update_from_price_reaction(
            "rate_hike_rbi",
            "2026-03-20",
            {"Information Technology": 5.0, "Financial Services": -3.0},
        )

    monkeypatch.setattr(shock_kb, "_LEARNED_WEIGHTS_PATH", weights_path)
    monkeypatch.setattr(shock_kb, "_LEARNED_WEIGHTS_CACHE", None)
    monkeypatch.setattr(shock_kb, "_LEARNED_WEIGHTS_MTIME", None)
    monkeypatch.setattr(shock_kb, "_MIN_LEARNED_EVENTS", 5)

    learned_profile = shock_kb.get_shock_profile("rate_hike_rbi")
    learned_score = learned_profile["sector_impacts"]["Information Technology"]["score"]

    assert weights_path.exists()
    assert learned_score != static_score
    assert "learned overlay" in learned_profile["sector_impacts"]["Information Technology"]["rationale"]
    payload = json.loads(weights_path.read_text())
    assert payload["rate_hike_rbi"]["event_count"] >= 6
