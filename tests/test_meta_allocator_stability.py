from __future__ import annotations

from src.intelligence.meta_allocator import MetaAllocator


def test_meta_allocator_caps_per_cycle_weight_shifts_and_enforces_floor() -> None:
    meta = MetaAllocator()
    previous = {"short_vol": 0.40, "long_vol": 0.10}
    max_shift = meta.config.max_weight_shift_per_cycle

    for idx in range(12):
        proposed = {"short_vol": 0.90 if idx % 2 == 0 else 0.05, "long_vol": 0.05 if idx % 2 == 0 else 0.90}
        metrics = {
            "short_vol": {"regret": 0.8 if idx % 2 else 0.1, "confidence": 0.4 if idx % 2 else 0.8, "credibility": 0.5},
            "long_vol": {"regret": 0.1 if idx % 2 else 0.8, "confidence": 0.8 if idx % 2 else 0.4, "credibility": 0.5},
        }
        adjusted, _ = meta.apply(
            proposed_weights=proposed,
            strategy_metrics=metrics,
            allowed_gross_cap=1.0,
            previous_weights=previous,
        )

        for strategy in adjusted:
            delta = abs(adjusted[strategy] - previous.get(strategy, 0.0))
            assert delta <= max_shift + 1e-9

        gross = sum(abs(v) for v in adjusted.values())
        assert gross >= meta.config.min_gross_exposure_floor - 1e-8
        previous = adjusted
