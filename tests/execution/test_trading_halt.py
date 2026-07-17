"""Regression tests for the central trading-halt gate (src/execution/trading_halt.py)."""

import importlib

import pytest


@pytest.fixture()
def halt_module(tmp_path, monkeypatch):
    """trading_halt module pointed at a scratch flag file via env override."""
    flag = tmp_path / "TRADING_HALTED"
    monkeypatch.setenv("NORTHSTAR_TRADING_HALT_FLAG", str(flag))
    import src.execution.trading_halt as th
    importlib.reload(th)
    return th, flag


def test_not_halted_when_flag_absent(halt_module):
    th, flag = halt_module
    assert not flag.exists()
    assert th.is_trading_halted() is False
    assert th.halt_reason() is None
    # Should not raise for either open or close orders.
    th.assert_not_halted(close_only=False, context="test")
    th.assert_not_halted(close_only=True, context="test")


def test_open_order_blocked_during_halt(halt_module):
    th, flag = halt_module
    flag.write_text("Trading halted at 2026-07-05\nReason: unit test\n")
    assert th.is_trading_halted() is True
    assert "unit test" in th.halt_reason()
    with pytest.raises(th.TradingHaltedError):
        th.assert_not_halted(close_only=False, context="test-open")


def test_close_order_allowed_during_halt(halt_module):
    th, flag = halt_module
    flag.write_text("halted\n")
    # Exiting positions must remain possible while halted.
    th.assert_not_halted(close_only=True, context="test-close")


def test_reason_survives_unreadable_flag(halt_module, monkeypatch):
    th, flag = halt_module
    flag.write_text("halted\n")
    assert th.is_trading_halted() is True
    # halt_reason must never raise even if the file can't be read.
    monkeypatch.setattr(
        th.Path, "read_text", lambda self, *a, **k: (_ for _ in ()).throw(OSError("boom"))
    )
    assert th.halt_reason() is not None
