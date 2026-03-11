from __future__ import annotations

from src.research.research_controller import ResearchController


def test_low_resource_keeps_explicitly_enabled_deep_models() -> None:
    controller = ResearchController(
        config={
            "low_resource_mode": True,
            "enable_deep_models": False,
            "enabled_models": ["lightgbm", "lstm", "tcn", "transformer"],
        }
    )

    specs = [name for name, _ in controller._model_specs()]
    assert controller.low_resource_mode is True
    assert controller.config.get("enable_deep_models") is True
    assert {"lstm", "tcn", "transformer"}.issubset(set(specs))


def test_low_resource_disables_deep_models_when_not_requested() -> None:
    controller = ResearchController(
        config={
            "low_resource_mode": True,
            "enable_deep_models": False,
            "enabled_models": ["lightgbm", "xgboost", "catboost", "random_forest"],
        }
    )

    specs = [name for name, _ in controller._model_specs()]
    assert controller.low_resource_mode is True
    assert controller.config.get("enable_deep_models") is False
    assert {"lstm", "tcn", "transformer"}.isdisjoint(set(specs))


def test_model_name_aliases_are_normalized() -> None:
    assert ResearchController._normalize_model_name("lightbgm") == "lightgbm"
    assert ResearchController._normalize_model_name("random forrest") == "random_forest"
