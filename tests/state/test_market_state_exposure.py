from __future__ import annotations

import src.state.market_state as market_state_module
from src.state.market_state import MarketStateEngine


def test_supportive_late_expansion_exposure_is_not_overly_compressed():
    engine = MarketStateEngine()

    exposure = engine.compute_allowed_exposure(
        macro_state={"macro_regime": "late-expansion", "macro_momentum": 0.17},
        health_state={"health_score": 0.6426769890765687},
        vol_state={"stress_level": 0.05},
        opp_state={"opportunity_density": 0.07246376811594203},
        risk_on_prob=0.5424888089726975,
    )

    assert 0.40 <= exposure <= 0.70


def test_normal_sentiment_context_does_not_crush_exposure(monkeypatch):
    engine = MarketStateEngine()

    monkeypatch.setattr(
        market_state_module,
        "load_sentiment_context",
        lambda now=None: {
            "available": True,
            "status": "success",
            "summary_age_minutes": 10.0,
            "market_age_minutes": 10.0,
            "polarity": 0.0,
            "uncertainty": 0.0,
            "conviction": 1.0,
            "narrative_conflict": 0.0,
            "sentiment_bias": 0.0,
            "event_shock_score": 0.2,
            "news_signal_score": 0.1,
            "micro_shift_score": 0.0,
            "change_velocity": 0.0,
            "delta_polarity": 0.0,
            "delta_uncertainty": 0.0,
            "delta_conviction": 0.0,
            "negative_trending_company_total": 0,
            "event_company_impact_total": 250,
            "alert_level": "normal",
            "dominant_theme": "neutral",
        },
    )

    adjusted = engine.integrate_sentiment_intelligence(
        {
            "risk_on_probability": 0.5424888089726975,
            "risk_on": 0.5424888089726975,
            "allowed_exposure": 0.52,
            "confidence": 0.8,
        }
    )

    assert adjusted["sentiment_exposure_multiplier"] >= 0.85
    assert adjusted["allowed_exposure"] >= 0.45
