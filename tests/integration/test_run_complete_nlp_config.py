from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml


def _load_run_complete_module():
    module_path = Path("scripts/run_complete_v3_system.py")
    spec = importlib.util.spec_from_file_location("run_complete_module_nlp", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_load_system_config_merges_nlp_config(tmp_path, monkeypatch):
    module = _load_run_complete_module()
    monkeypatch.setattr(module, "PROJECT_ROOT", tmp_path)
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)

    (tmp_path / "config" / "sentiment_config.yaml").write_text(
        yaml.safe_dump({"sentiment_regime": {"lookback_days": 99}}),
        encoding="utf-8",
    )
    (tmp_path / "config" / "nlp_config.yaml").write_text(
        yaml.safe_dump({"nlp": {"enabled": True, "pipeline": {"availability_lag_hours": 2}}}),
        encoding="utf-8",
    )

    config = module.load_system_config()

    assert config["nlp"]["enabled"] is True
    assert config["nlp"]["pipeline"]["availability_lag_hours"] == 2
    assert config["sentiment_regime"]["lookback_days"] == 99
