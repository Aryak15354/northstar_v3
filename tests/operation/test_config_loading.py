from __future__ import annotations

from pathlib import Path

import yaml

from src.operation.operation_config_manager import OperationConfigManager


REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_CONFIG = REPO_ROOT / "config" / "operation" / "operation_config.yaml"
DEPRECATED_CONFIG = REPO_ROOT / "config" / "operation_config.yaml"


def test_operation_config_manager_loads_canonical_config() -> None:
    manager = OperationConfigManager(config_dir=str(REPO_ROOT / "config" / "operation"))
    config = manager.load_base_config()

    assert config.max_concurrent_operations == 3
    assert config.operation_timeout_hours == 24
    assert config.data_retention_days == 365
    assert config.enable_real_time_monitoring is True
    assert config.performance_thresholds["min_sharpe_ratio"] == 0.5
    assert config.performance_thresholds["max_drawdown"] == 0.15


def test_canonical_operation_config_contains_required_sections() -> None:
    data = yaml.safe_load(CANONICAL_CONFIG.read_text())

    required_sections = [
        "system",
        "performance_thresholds",
        "crisis_periods",
        "validation_scenarios",
        "alerts",
        "reporting",
        "backtesting",
        "walk_forward",
        "logging",
    ]

    for section in required_sections:
        assert section in data

    assert data["system"]["max_concurrent_operations"] == 3
    assert data["alerts"]["email_recipients"] == ["operations@northstar.com", "risk@northstar.com"]
    assert data["reporting"]["output_directory"] == "reports/operation"
    assert data["backtesting"]["default_benchmark"] == "NIFTY50"
    assert data["walk_forward"]["reoptimization_frequency"] == "quarterly"
    assert data["logging"]["enable_alert_logging"] is True
    assert data["performance_thresholds"]["max_drawdown_threshold"] == 0.15


def test_no_active_references_use_root_operation_config_path() -> None:
    allowed = {DEPRECATED_CONFIG.resolve()}
    current_test = Path(__file__).resolve()
    search_roots = ["scripts", "src", "config", "tests"]
    offenders: list[Path] = []

    for root_name in search_roots:
        root = REPO_ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".py", ".yaml", ".yml"}:
                continue
            if path.resolve() in allowed or path.resolve() == current_test:
                continue
            try:
                text = path.read_text()
            except Exception:
                continue
            if "config/operation_config.yaml" in text:
                offenders.append(path)

    assert offenders == []
