"""
Unit tests for options config loader.

Feature: options-trading-system
Task: 1.1 Write unit tests for configuration loading
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.options.config_loader import ConfigLoader


def _base_config() -> dict:
    with open("config/options_trading.yaml", "r") as f:
        cfg = yaml.safe_load(f)
    return cfg


def _write_config_for_test(tmp_path: Path, cfg: dict) -> Path:
    # Keep all writes inside tmp_path for hermetic tests.
    cfg = dict(cfg)
    cfg["data_paths"] = {
        "trade_ledger": str(tmp_path / "data/options/trade_ledger.parquet"),
        "regime_history": str(tmp_path / "data/options/regime_history.parquet"),
        "iv_history": str(tmp_path / "data/options/iv_history.parquet"),
        "position_snapshots": str(tmp_path / "data/options/position_snapshots.parquet"),
    }
    cfg["logging"]["file"] = str(tmp_path / "logs/options_trading.log")

    config_path = tmp_path / "options_trading.yaml"
    with open(config_path, "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)
    return config_path


def _write_env(tmp_path: Path, api_key: str = "k", api_secret: str = "s", access_token: str = "t") -> Path:
    env_path = tmp_path / ".env.options"
    env_path.write_text(
        "\n".join(
            [
                f"UPSTOX_API_KEY={api_key}",
                f"UPSTOX_API_SECRET={api_secret}",
                f"UPSTOX_ACCESS_TOKEN={access_token}",
            ]
        )
        + "\n"
    )
    return env_path


def test_config_loader_parses_yaml_and_env_substitution(tmp_path: Path) -> None:
    cfg = _base_config()
    config_path = _write_config_for_test(tmp_path, cfg)
    env_path = _write_env(tmp_path, api_key="api_key_test", api_secret="api_secret_test", access_token="token_test")

    loader = ConfigLoader(config_path=str(config_path), env_path=str(env_path))
    loaded = loader.load()

    assert loaded.upstox.api_key == "api_key_test"
    assert loaded.upstox.api_secret == "api_secret_test"
    assert loaded.upstox.access_token == "token_test"
    assert loaded.capital.base_capital > 0
    assert Path(loaded.data_paths.trade_ledger).parent.exists()


def test_config_loader_raises_on_missing_config_file(tmp_path: Path) -> None:
    env_path = _write_env(tmp_path)
    loader = ConfigLoader(config_path=str(tmp_path / "missing.yaml"), env_path=str(env_path))
    with pytest.raises(FileNotFoundError):
        loader.load()


def test_config_loader_raises_on_missing_required_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = _base_config()
    config_path = _write_config_for_test(tmp_path, cfg)

    # No env file + removed process env keys => placeholder substitution must fail.
    monkeypatch.delenv("UPSTOX_API_KEY", raising=False)
    monkeypatch.delenv("UPSTOX_API_SECRET", raising=False)
    monkeypatch.delenv("UPSTOX_ACCESS_TOKEN", raising=False)

    loader = ConfigLoader(config_path=str(config_path), env_path=str(tmp_path / ".env.missing"))
    with pytest.raises(ValueError, match="Environment variable .* not found"):
        loader.load()


def test_config_loader_raises_on_invalid_thresholds(tmp_path: Path) -> None:
    cfg = _base_config()
    cfg["regime_detection"]["thresholds"]["rising_vol_buy_iv_rank"] = 0.85
    cfg["regime_detection"]["thresholds"]["low_vol_sell_iv_rank"] = 0.70
    cfg["regime_detection"]["thresholds"]["high_vol_sell_iv_rank"] = 0.80
    config_path = _write_config_for_test(tmp_path, cfg)
    env_path = _write_env(tmp_path)

    loader = ConfigLoader(config_path=str(config_path), env_path=str(env_path))
    with pytest.raises(ValueError, match="Invalid IV rank thresholds"):
        loader.load()
