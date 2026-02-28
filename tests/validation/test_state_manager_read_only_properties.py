"""
Property tests for read-only unified state behavior and canonical market-state authority.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest
from hypothesis import given, settings, strategies as st, HealthCheck

from src.cohesion.state_file_manager import StateFileManager
from src.state.unified_state_manager import UnifiedStateManager


@st.composite
def market_state_dataframe(draw, min_rows: int = 1, max_rows: int = 20) -> pd.DataFrame:
    n_rows = draw(st.integers(min_value=min_rows, max_value=max_rows))
    base_date = datetime(2024, 1, 1)
    dates = [base_date + timedelta(days=i) for i in range(n_rows)]
    return pd.DataFrame(
        {
            "date": dates,
            "regime": draw(
                st.lists(
                    st.sampled_from(
                        ["early-expansion", "late-expansion", "early-contraction", "late-contraction"]
                    ),
                    min_size=n_rows,
                    max_size=n_rows,
                )
            ),
            "risk_on": draw(
                st.lists(
                    st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
                    min_size=n_rows,
                    max_size=n_rows,
                )
            ),
            "allowed_exposure": draw(
                st.lists(
                    st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
                    min_size=n_rows,
                    max_size=n_rows,
                )
            ),
            "stress_score": draw(
                st.lists(
                    st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
                    min_size=n_rows,
                    max_size=n_rows,
                )
            ),
        }
    )


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(state_df=market_state_dataframe(min_rows=2, max_rows=10))
def test_property_single_market_state_file(tmp_path, monkeypatch, state_df: pd.DataFrame) -> None:
    """
    Property 9: Single Market State File

    Any number of canonical writes should keep exactly one active market_state file
    (plus optional backups under backup directory).
    """
    monkeypatch.setattr(StateFileManager, "MARKET_STATE_PATH", tmp_path / "market_state.parquet")
    monkeypatch.setattr(StateFileManager, "PORTFOLIO_WEIGHTS_PATH", tmp_path / "portfolio_weights.parquet")
    monkeypatch.setattr(StateFileManager, "RISK_STATE_PATH", tmp_path / "risk_state.parquet")
    monkeypatch.setattr(StateFileManager, "EXPOSURE_HISTORY_PATH", tmp_path / "exposure_history.parquet")
    monkeypatch.setattr(StateFileManager, "PORTFOLIO_ANALYTICS_PATH", tmp_path / "portfolio_analytics.json")
    monkeypatch.setattr(StateFileManager, "BACKUP_DIR", tmp_path / "backups")

    manager = StateFileManager()
    manager.write_market_state(state_df)
    manager.write_market_state(state_df.iloc[::-1].sort_values("date").reset_index(drop=True))

    active = list(tmp_path.rglob("market_state.parquet"))
    assert len(active) == 1

    non_backup_dupes = [
        p
        for p in tmp_path.rglob("*market_state*.parquet")
        if p.name != "market_state.parquet" and "backups" not in str(p)
    ]
    assert non_backup_dupes == []


@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    risk_on=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    allowed=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    stress=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
def test_property_state_manager_read_only(monkeypatch, risk_on: float, allowed: float, stress: float) -> None:
    """
    Property 4: State Manager Read-Only

    UnifiedStateManager should read canonical state, but never call canonical write APIs.
    """
    market_df = pd.DataFrame(
        [
            {
                "date": datetime(2026, 1, 1),
                "regime": "early-expansion",
                "risk_on": risk_on,
                "allowed_exposure": allowed,
                "stress_score": stress,
            }
        ]
    )
    portfolio_df = pd.DataFrame(
        [
            {
                "date": datetime(2026, 1, 1),
                "symbol": "TEST",
                "weight": 0.2,
                "exposure": 0.2,
            }
        ]
    )
    risk_df = pd.DataFrame(
        [
            {
                "date": datetime(2026, 1, 1),
                "volatility": 0.2,
                "correlation": 0.3,
                "var": 0.05,
            }
        ]
    )

    monkeypatch.setattr(StateFileManager, "read_market_state", lambda self: market_df)
    monkeypatch.setattr(StateFileManager, "read_portfolio_weights", lambda self: portfolio_df)
    monkeypatch.setattr(StateFileManager, "read_risk_state", lambda self: risk_df)
    monkeypatch.setattr(
        StateFileManager,
        "read_portfolio_analytics",
        lambda self: {
            "portfolio_summary": {
                "expected_return": 0.1,
                "expected_volatility": 0.2,
                "sharpe_ratio": 0.5,
                "max_drawdown": -0.1,
            },
            "compliance_check": {"all_compliant": True, "violations": []},
        },
    )

    # Any canonical write call from UnifiedStateManager should fail this test.
    monkeypatch.setattr(
        StateFileManager,
        "write_market_state",
        lambda self, _: (_ for _ in ()).throw(AssertionError("write_market_state must not be called")),
    )
    monkeypatch.setattr(
        StateFileManager,
        "write_portfolio_weights",
        lambda self, _: (_ for _ in ()).throw(AssertionError("write_portfolio_weights must not be called")),
    )
    monkeypatch.setattr(
        StateFileManager,
        "write_risk_state",
        lambda self, _: (_ for _ in ()).throw(AssertionError("write_risk_state must not be called")),
    )
    monkeypatch.setattr(
        StateFileManager,
        "write_portfolio_analytics",
        lambda self, _: (_ for _ in ()).throw(AssertionError("write_portfolio_analytics must not be called")),
    )
    monkeypatch.setattr(
        StateFileManager,
        "append_exposure_history",
        lambda self, _: (_ for _ in ()).throw(AssertionError("append_exposure_history must not be called")),
    )

    manager = UnifiedStateManager()
    manager.update_market_state()
    manager.update_portfolio_state()
    manager.update_risk_state()
    state = manager.get_unified_state()

    assert "market" in state
    assert "portfolio" in state
    assert "risk" in state
