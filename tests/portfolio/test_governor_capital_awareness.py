from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

import scripts.run_integrated_options_paper_engine as options_engine_module
import src.intelligence.capital_allocator as capital_allocator_module
from src.core.state import UnifiedState
from src.portfolio.governor import PortfolioGovernor
from src.sentiment.sentiment_state import SentimentRegime
from src.alternative_data.alternative_state import EconomicActivityRegime


def _bull_state(nav: float = 10_000_000.0) -> UnifiedState:
    state = UnifiedState()
    state.market.regime = "BULL"
    state.market.volatility_regime = "NORMAL_VOL"
    state.macro.regime = "EXPANSION"
    state.sentiment.market_sentiment_regime = SentimentRegime.OPTIMISM
    state.alternative_data.economic_activity_regime = EconomicActivityRegime.EXPANSION
    state.pnl_state.current_nav_inr = nav
    state.pnl_state.current_drawdown_pct = 0.0
    return state


def _write_options_runtime(path: Path, positions: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"open_positions": positions}), encoding="utf-8")


def test_governor_reduces_equity_budget_when_options_notional_is_deployed(tmp_path: Path) -> None:
    governor = PortfolioGovernor(config={"starting_capital_inr": 10_000_000}, data_dir=str(tmp_path))
    _write_options_runtime(
        tmp_path / "options/live/options_runtime_state.json",
        [
            {"position_id": "P1", "max_loss": 125_000.0},
            {"position_id": "P2", "current_value": 25_000.0},
        ],
    )

    structure = governor.compute_capital_structure(_bull_state())

    assert structure is not None
    expected_budget = (structure.equity_fraction * structure.total_capital_inr) - 150_000.0
    assert structure.equity_budget_inr == expected_budget


def test_governor_full_equity_budget_when_no_options_deployed(tmp_path: Path) -> None:
    governor = PortfolioGovernor(config={"starting_capital_inr": 10_000_000}, data_dir=str(tmp_path))

    structure = governor.compute_capital_structure(_bull_state())

    assert structure is not None
    assert structure.equity_budget_inr == structure.equity_fraction * structure.total_capital_inr


def test_capital_allocator_reduces_available_equity_fraction_when_options_deployed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(capital_allocator_module, "PROJECT_ROOT", tmp_path)

    state_path = tmp_path / "data/state/unified_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "governor_state": {
                    "capital_structure_regime": "STANDARD",
                    "equity_fraction": 0.75,
                    "options_fraction": 0.15,
                    "cash_fraction": 0.10,
                    "total_capital_inr": 10_000_000.0,
                }
            }
        ),
        encoding="utf-8",
    )
    _write_options_runtime(
        tmp_path / "data/options/live/options_runtime_state.json",
        [{"position_id": "P1", "max_loss": 250_000.0}],
    )

    allocator = capital_allocator_module.CapitalAllocator()
    allocator.paths["unified_state"] = str(state_path)

    governor_state = allocator.load_governor_state()

    assert governor_state["equity_fraction"] == 0.75
    assert governor_state["options_notional_deployed"] == 250_000.0
    assert governor_state["available_equity_fraction"] == 0.725


def test_options_engine_uses_real_equity_position_count_for_protected_symbols(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(options_engine_module, "PROJECT_ROOT", tmp_path)

    positions_path = tmp_path / "data/portfolio/current_positions.json"
    positions_path.parent.mkdir(parents=True, exist_ok=True)
    positions_path.write_text(
        json.dumps(
            {
                "positions": {
                    "RELIANCE": {"weight": 0.10, "market_value": 100_000.0},
                    "TCS": {"weight": 0.08, "market_value": 80_000.0},
                    "HDFCBANK": {"weight": 0.07, "market_value": 70_000.0},
                }
            }
        ),
        encoding="utf-8",
    )

    engine = options_engine_module.IntegratedOptionsPaperEngine.__new__(
        options_engine_module.IntegratedOptionsPaperEngine
    )
    engine.portfolio_overlay = {}

    state = engine._hedging_state_for_underlying("NIFTY", "event_shock_hedge")

    assert state["protected_symbols_count"] == 3
    assert state["protected_symbols"] == ["RELIANCE", "TCS", "HDFCBANK"]
