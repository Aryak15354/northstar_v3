from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.intelligence import build_dashboard_snapshot as snapshot_builder
from src.intelligence.market_brain.m1_safe_regime_memory import M1SafeRegimeMemoryEngine
from src.intelligence.market_brain.real_data_integrator import RealDataIntegrator


def test_build_dashboard_snapshot_marks_flat_pnl_unavailable() -> None:
    pnl_df = pd.DataFrame(
        {
            "Equity": [1.0, 1.0, 1.0, 1.0],
            "Return": [0.0, 0.0, 0.0, 0.0],
        }
    )

    performance = snapshot_builder._build_performance_snapshot(pnl_df)

    assert performance["available"] is False
    assert performance["reason"] == "no_real_pnl_data"
    assert performance["equity"] is None
    assert performance["message"]


def test_m1_safe_regime_memory_returns_none_when_tensor_missing(tmp_path: Path) -> None:
    engine = M1SafeRegimeMemoryEngine()
    engine.paths["market_tensor"] = str(tmp_path / "missing_market_tensor.parquet")

    assert engine.load_market_tensor() is None


def test_real_data_integrator_raises_not_implemented_for_fundamentals() -> None:
    integrator = RealDataIntegrator()

    try:
        integrator.extract_real_fundamentals_data()
    except NotImplementedError as exc:
        assert "not yet implemented" in str(exc).lower()
    else:  # pragma: no cover - defensive
        raise AssertionError("extract_real_fundamentals_data() should raise NotImplementedError")
