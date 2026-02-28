#!/usr/bin/env python3
"""
Property tests for AntiOverrideSystem.
"""

from __future__ import annotations

import tempfile

from hypothesis import given, settings, strategies as st

from src.intelligence.anti_override_system import AntiOverrideSystem, SystemChange


def _change(
    change_type: str,
    *,
    stress_level: float = 0.0,
    emergency: bool = False,
) -> SystemChange:
    return SystemChange(
        actor="operator",
        module="portfolio_engine",
        change_type=change_type,
        payload={"key": "value"},
        justification="test",
        stress_level=stress_level,
        emergency=emergency,
    )


@settings(max_examples=25, deadline=5000)
@given(stress=st.floats(min_value=0.0, max_value=1.0))
def test_core_overrides_are_blocked(stress: float) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        system = AntiOverrideSystem(log_dir=tmpdir)
        result = system.intercept_modification(
            _change("position_size_override", stress_level=stress)
        )
        assert result.allowed is False
        assert result.escalation_required is True
        assert result.cooling_off_minutes >= system.base_cooling_minutes


def test_maintenance_changes_can_be_allowed(tmp_path) -> None:
    system = AntiOverrideSystem(log_dir=tmp_path)
    result = system.intercept_modification(
        _change("logging_config", stress_level=0.1)
    )
    assert result.allowed is True
    assert result.reason in {
        "authorized_maintenance_change",
        "authorized_but_escalated_for_stress_review",
    }


def test_high_stress_escalates_even_allowed_change(tmp_path) -> None:
    system = AntiOverrideSystem(log_dir=tmp_path)
    low = system.intercept_modification(_change("logging_config", stress_level=0.1))
    high = system.intercept_modification(_change("logging_config", stress_level=0.95))
    assert high.cooling_off_minutes >= low.cooling_off_minutes
    assert high.escalation_required is True


def test_attempts_are_persisted(tmp_path) -> None:
    system = AntiOverrideSystem(log_dir=tmp_path)
    system.intercept_modification(_change("position_size_override", stress_level=0.8))
    parquet_path = tmp_path / "override_attempts.parquet"
    jsonl_path = tmp_path / "override_attempts.jsonl"
    assert parquet_path.exists()
    assert jsonl_path.exists()
