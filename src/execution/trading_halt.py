"""Central trading-halt gate.

A single source of truth for "is trading halted right now?", backed by the
`TRADING_HALTED` flag file at the project root. That flag is written by:
  - scripts/emergency_halt.py (manual operator halt), and
  - scripts/eod_rebalance_with_pnl.py on a CRITICAL reconciliation failure,
and cleared by scripts/resume_trading.py.

Historically the flag existed but nothing actually checked it before placing
trades, so a halt was advisory-only. Every real order-submission chokepoint
now consults `is_trading_halted()` / `assert_not_halted()` so the flag has
teeth. Closing/exiting existing positions is always allowed even while halted
(a halt should stop new risk, not trap capital) -- callers pass
`close_only=True` for exit orders.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# Project root = two levels up from this file (src/execution/trading_halt.py).
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
HALT_FLAG_PATH = _PROJECT_ROOT / "TRADING_HALTED"


class TradingHaltedError(RuntimeError):
    """Raised by assert_not_halted() when a non-close order is attempted during a halt."""


def _flag_path() -> Path:
    # Env override lets tests point at a scratch flag without touching the repo root.
    override = os.environ.get("NORTHSTAR_TRADING_HALT_FLAG")
    return Path(override) if override else HALT_FLAG_PATH


def is_trading_halted() -> bool:
    """True if the TRADING_HALTED flag file exists."""
    return _flag_path().exists()


def halt_reason() -> Optional[str]:
    """Return the contents of the halt flag (reason/timestamp), or None if not halted."""
    path = _flag_path()
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8").strip()
    except Exception:
        return "TRADING_HALTED flag present (reason unreadable)"


def assert_not_halted(*, close_only: bool = False, context: str = "") -> None:
    """
    Raise TradingHaltedError if trading is halted and this is not a close-only
    (position-exiting) order. Call at every real order-submission chokepoint.
    """
    if close_only:
        return
    if is_trading_halted():
        reason = halt_reason() or "unknown"
        where = f" [{context}]" if context else ""
        raise TradingHaltedError(
            f"Trading is halted{where}; new (non-close) orders are blocked. "
            f"Reason: {reason}. Clear via scripts/resume_trading.py once resolved."
        )
