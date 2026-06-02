from src.intelligence.strategy_surface_policy import (
    publishable_strategy_names,
    strategy_max_allocation,
    strategy_overlay_parent,
    strategy_surface_mode,
)
from src.intelligence.capital_allocator import CapitalAllocator


def test_policy_classifies_legacy_sleeves_as_feature_or_archived():
    assert strategy_surface_mode("mom_6m") == "feature_only"
    assert strategy_surface_mode("equal_weight") == "archived"
    assert strategy_surface_mode("northstar") == "standalone"


def test_publishable_surface_keeps_only_live_governed_strategies():
    published = publishable_strategy_names(
        ["mom_6m", "northstar", "equal_weight", "sentiment_trend"]
    )
    assert published == ["northstar", "sentiment_trend"]


def test_policy_caps_and_parenting_follow_single_surface_config():
    assert strategy_overlay_parent("value_tilt") == "northstar"
    assert strategy_max_allocation("northstar") == 0.7
    assert CapitalAllocator._tailwind_family_for_strategy("northstar") == "composite"
