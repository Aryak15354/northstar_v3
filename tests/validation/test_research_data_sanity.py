"""Sanity checks for research dataset/metric stability guards."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.research.dataset_manager import DatasetManager, _sanitize_target_series
from src.research.diagnostics import compute_feature_ic_diagnostics
from src.research.feature_factory import FeatureFactory
from src.research.research_controller import ResearchController
from src.research.research_types import ResearchDataset
from src.research.walk_forward_validator import compute_window_metrics


def test_sanitize_target_series_handles_nonfinite_and_caps_outliers() -> None:
    raw = pd.Series([0.02, np.inf, -np.inf, np.nan, 4.5, -7.0, 0.01], dtype=float)
    out = _sanitize_target_series(raw, clip_abs=1.0, winsor_quantile=0.95)

    assert np.isfinite(out.to_numpy(dtype=float)).all()
    assert float(out.max()) <= 1.0
    assert float(out.min()) >= -1.0


def test_feature_factory_drops_non_positive_close_before_target_construction() -> None:
    prices = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"]),
            "ticker": ["ABC", "ABC", "ABC"],
            "Close": [100.0, 0.0, 120.0],
        }
    )

    panel = FeatureFactory(target_horizon_days=1).build_features(prices=prices)

    assert not panel.empty
    assert (panel["close"] > 0.0).all()
    assert np.isfinite(panel["forward_return_5d"].to_numpy(dtype=float)).all()


def test_compute_window_metrics_limits_drawdown_under_extreme_observations() -> None:
    # Last sample is an extreme positive realization while model is strongly short.
    y_true = np.array([0.01] * 80 + [2500.0], dtype=float)
    y_pred = np.array([0.02] * 80 + [-80.0], dtype=float)

    metrics = compute_window_metrics(y_true=y_true, y_pred=y_pred)

    assert np.isfinite(metrics["max_drawdown"])
    assert 0.0 <= float(metrics["max_drawdown"]) <= 1.0
    assert np.isfinite(metrics["sharpe"])


def test_feature_factory_handles_object_array_columns_without_replace_crash() -> None:
    prices = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"]),
            "ticker": ["ABC", "ABC", "ABC", "ABC"],
            "Close": [100.0, 101.0, 102.0, 103.0],
        }
    )
    macro = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-01", "2025-01-04"]),
            "macro_noise_vector": [np.array([1.0, 2.0]), np.array([3.0, 4.0])],
        }
    )

    panel = FeatureFactory(target_horizon_days=1).build_features(prices=prices, macro=macro)

    assert not panel.empty
    assert "macro_noise_vector" in panel.columns
    assert panel["macro_noise_vector"].notna().any()


def test_feature_factory_adds_structural_alpha_columns() -> None:
    dates = pd.to_datetime(
        [
            "2025-01-01",
            "2025-01-02",
            "2025-01-03",
            "2025-01-04",
            "2025-01-05",
            "2025-01-06",
        ]
    )
    prices = pd.DataFrame(
        {
            "Date": np.tile(dates, 2),
            "ticker": ["AAA"] * len(dates) + ["BBB"] * len(dates),
            "Close": [100, 102, 101, 103, 104, 106, 80, 81, 82, 83, 84, 85],
            "Volume": [1000, 1005, 1010, 1008, 1015, 1020, 900, 910, 920, 915, 918, 925],
        }
    )
    fundamentals = pd.DataFrame(
        {
            "date": np.tile(dates, 2),
            "ticker": ["AAA"] * len(dates) + ["BBB"] * len(dates),
            "Sector": ["Tech"] * len(dates) + ["Banks"] * len(dates),
            "net_income": [10.0] * (2 * len(dates)),
            "revenue": [100.0] * (2 * len(dates)),
            "total_debt": [20.0] * (2 * len(dates)),
            "equity": [80.0] * (2 * len(dates)),
            "operating_cash_flow": [12.0] * (2 * len(dates)),
            "free_cash_flow": [9.0] * (2 * len(dates)),
        }
    )

    panel = FeatureFactory(target_horizon_days=1).build_features(prices=prices, fundamentals=fundamentals)

    assert "sector_name" in panel.columns
    assert "ret_1d_sector_rel" in panel.columns
    assert "ret_1d_sector_resid" in panel.columns
    assert "mom20_x_liquidity" in panel.columns
    assert "res_mom_5d" in panel.columns
    assert "ret_1d_cs_z" in panel.columns
    assert "ret_1d_cs_rank" in panel.columns


def test_dataset_manager_target_mode_rank_with_sector_residualization() -> None:
    dm = DatasetManager(config={"target_mode": "rank", "target_sector_residualize": True})
    panel = pd.DataFrame(
        {
            "date": pd.to_datetime(
                [
                    "2025-01-01",
                    "2025-01-01",
                    "2025-01-01",
                    "2025-01-02",
                    "2025-01-02",
                    "2025-01-02",
                ]
            ),
            "sector_name": ["Tech", "Tech", "Banks", "Tech", "Tech", "Banks"],
            "forward_return_5d": [0.03, 0.01, -0.02, 0.04, 0.01, -0.01],
        }
    )

    y, meta = dm._derive_target_series(panel, target_col="forward_return_5d")

    assert str(meta.get("target_mode")) == "rank"
    assert bool(meta.get("target_sector_residualize")) is True
    assert np.isfinite(y.to_numpy(dtype=float)).all()
    assert float(y.max()) <= 0.5
    assert float(y.min()) >= -0.5


def test_ic_diagnostics_selects_predictive_feature_and_drops_noise() -> None:
    rng = np.random.default_rng(42)
    dates = pd.date_range("2025-01-01", periods=30, freq="D")
    tickers = [f"T{i:02d}" for i in range(12)]
    rows = []
    for dt in dates:
        base = rng.normal(0.0, 0.02, size=len(tickers))
        good = base + rng.normal(0.0, 0.005, size=len(tickers))
        bad = rng.normal(0.0, 0.02, size=len(tickers))
        close = 100.0 + rng.normal(0.0, 1.0, size=len(tickers))
        for i, tk in enumerate(tickers):
            rows.append(
                {
                    "date": dt,
                    "ticker": tk,
                    "close": float(close[i]),
                    "regime": "normal",
                    "forward_return_5d": float(base[i]),
                    "f_good": float(good[i]),
                    "f_bad": float(bad[i]),
                }
            )
    frame = pd.DataFrame(rows)

    report = compute_feature_ic_diagnostics(
        frame,
        feature_cols=["f_good", "f_bad"],
        target_col="forward_return_5d",
        min_obs_per_day=8,
        min_abs_ic=0.01,
        min_sign_consistency=0.55,
        min_keep_features=1,
        max_keep_features=2,
        horizons=[5, 10, 20],
        max_regimes_to_report=2,
        min_regime_days=10,
    )

    assert str(report.get("status")) == "ok"
    selected = set(report.get("selected_features", []))
    assert "f_good" in selected
    assert int(report.get("n_features_selected", 0)) >= 1
    decay = dict(report.get("ic_decay_selected_features", {}) or {})
    assert set(["5", "10", "20"]).issubset(set(decay.keys()))
    decay_summary = dict(report.get("decay_summary_selected_features", {}) or {})
    assert float(decay_summary.get("peak_horizon", 0.0)) in {5.0, 10.0, 20.0}
    regime_decay = dict(report.get("regime_ic_decay_selected_features", {}) or {})
    assert "normal" in regime_decay
    assert set(["5", "10", "20"]).issubset(set(regime_decay["normal"].keys()))


def test_compute_window_metrics_uses_cross_sectional_daily_portfolio_path() -> None:
    rng = np.random.default_rng(7)
    n_days = 24
    n_assets = 18
    dates = np.repeat(pd.date_range("2025-03-01", periods=n_days, freq="D").to_numpy(), n_assets)
    latent = rng.normal(0.0, 0.02, size=n_days * n_assets)
    y_true = latent + rng.normal(0.0, 0.01, size=n_days * n_assets)
    y_pred = latent + rng.normal(0.0, 0.005, size=n_days * n_assets)
    vol = np.abs(rng.normal(0.2, 0.05, size=n_days * n_assets))

    metrics = compute_window_metrics(
        y_true=y_true,
        y_pred=y_pred,
        dates=dates,
        vol=vol,
        min_assets_per_day=10,
    )

    assert np.isfinite(metrics["max_drawdown"])
    assert 0.0 <= float(metrics["max_drawdown"]) <= 1.0
    assert float(metrics.get("portfolio_days", 0.0)) > 0.0


def test_compute_window_metrics_supports_weekly_rebalance_with_tickers() -> None:
    rng = np.random.default_rng(19)
    n_days = 35
    n_assets = 14
    dates = np.repeat(pd.date_range("2025-04-01", periods=n_days, freq="D").to_numpy(), n_assets)
    tickers = np.tile(np.asarray([f"W{i:02d}" for i in range(n_assets)], dtype=object), n_days)
    latent = rng.normal(0.0, 0.02, size=n_days * n_assets)
    y_true = latent + rng.normal(0.0, 0.01, size=n_days * n_assets)
    y_pred = latent + rng.normal(0.0, 0.006, size=n_days * n_assets)
    vol = np.abs(rng.normal(0.2, 0.05, size=n_days * n_assets))

    metrics = compute_window_metrics(
        y_true=y_true,
        y_pred=y_pred,
        dates=dates,
        tickers=tickers,
        vol=vol,
        min_assets_per_day=10,
        rebalance_frequency_days=5,
    )

    assert np.isfinite(metrics["max_drawdown"])
    assert 0.0 <= float(metrics["max_drawdown"]) <= 1.0
    assert float(metrics.get("portfolio_days", 0.0)) > 0.0


def test_research_controller_ic_gate_prunes_features_when_enabled(tmp_path) -> None:
    rng = np.random.default_rng(11)
    dates = pd.date_range("2025-04-01", periods=28, freq="D")
    tickers = [f"S{i:02d}" for i in range(10)]
    rows = []
    for dt in dates:
        latent = rng.normal(0.0, 0.02, size=len(tickers))
        for i, tk in enumerate(tickers):
            rows.append(
                {
                    "date": dt,
                    "ticker": tk,
                    "close": 100.0 + float(i),
                    "regime": "normal",
                    "forward_return_5d": float(latent[i]),
                    "f_good": float(latent[i] + rng.normal(0.0, 0.004)),
                    "f_bad": float(rng.normal(0.0, 0.02)),
                }
            )
    frame = pd.DataFrame(rows)
    X = frame[["f_good", "f_bad"]].to_numpy(dtype=float)
    dataset = ResearchDataset(
        X=X,
        y=frame["forward_return_5d"].to_numpy(dtype=float),
        feature_names=["f_good", "f_bad"],
        metadata={"target_col": "forward_return_5d"},
        index=pd.DatetimeIndex(frame["date"]),
        tickers=frame["ticker"].to_numpy(),
        frame=frame,
    )

    controller = ResearchController(
        config={
            "ic_diagnostics": {
                "enabled": True,
                "prune_features": True,
                "output_dir": str(tmp_path / "ic_reports"),
                "min_obs_per_day": 8,
                "min_abs_ic": 0.01,
                "min_sign_consistency": 0.55,
                "min_keep_features": 1,
                "max_keep_features": 1,
                "max_regimes_to_report": 2,
                "min_regime_days": 8,
            }
        },
        project_root=tmp_path,
    )

    pruned, payload = controller._run_ic_diagnostics_gate(dataset)

    assert payload is not None
    assert bool(payload.get("prune_applied")) is True
    assert len(pruned.feature_names) == 1
    assert "f_good" in pruned.feature_names
    assert isinstance(payload.get("decay_summary_selected_features"), dict)
    assert isinstance(payload.get("regime_decay_summary_selected_features"), dict)


def test_structural_promotion_gate_enforces_decay_thresholds(tmp_path) -> None:
    controller = ResearchController(
        config={
            "structural_promotion_gate": {
                "enabled": True,
                "min_peak_horizon": 80,
                "min_half_life_horizon": 80,
                "min_monotonicity_score": 0.80,
                "min_peak_ic": 0.05,
            }
        },
        project_root=tmp_path,
    )

    ok_payload = {
        "decay_summary_selected_features": {
            "peak_horizon": 100.0,
            "half_life_horizon": 100.0,
            "monotonicity_score": 0.92,
            "peak_ic": 0.07,
        }
    }
    fail_payload = {
        "decay_summary_selected_features": {
            "peak_horizon": 40.0,
            "half_life_horizon": 20.0,
            "monotonicity_score": 0.55,
            "peak_ic": 0.02,
        }
    }

    ok = controller._evaluate_structural_promotion_gate(ok_payload)
    bad = controller._evaluate_structural_promotion_gate(fail_payload)

    assert bool(ok.get("passed")) is True
    assert str(ok.get("reason")) == "pass"
    assert bool(bad.get("passed")) is False
    assert str(bad.get("reason")) == "threshold_violation"
    assert len(list(bad.get("failed_rules", []))) >= 1


def test_dataset_manager_market_residualization_reduces_market_correlation() -> None:
    rng = np.random.default_rng(123)
    dates = pd.date_range("2024-01-01", periods=160, freq="D")
    tickers = [f"M{i:02d}" for i in range(12)]
    sector_map = {tk: ("Banks" if i < 6 else "Tech") for i, tk in enumerate(tickers)}

    market = pd.Series(rng.normal(0.0, 0.015, size=len(dates)), index=dates)
    sector_bank = pd.Series(rng.normal(0.0, 0.012, size=len(dates)), index=dates)
    sector_tech = pd.Series(rng.normal(0.0, 0.012, size=len(dates)), index=dates)

    rows = []
    for dt in dates:
        for tk in tickers:
            sec = sector_map[tk]
            sec_ret = float(sector_bank.loc[dt] if sec == "Banks" else sector_tech.loc[dt])
            base = 1.4 * float(market.loc[dt]) + 0.9 * sec_ret
            y = base + float(rng.normal(0.0, 0.006))
            rows.append(
                {
                    "date": dt,
                    "ticker": tk,
                    "sector_name": sec,
                    "forward_return_5d": y,
                }
            )
    panel = pd.DataFrame(rows)
    market_rep = panel["date"].map(market).to_numpy(dtype=float)

    dm_raw = DatasetManager(config={"target_mode": "raw"})
    y_raw, _ = dm_raw._derive_target_series(panel, target_col="forward_return_5d")

    dm_res = DatasetManager(
        config={
            "target_mode": "raw",
            "target_sector_residualize": True,
            "target_market_residualize": True,
            "target_residual_window_days": 80,
            "target_residual_min_obs": 40,
        }
    )
    y_res, meta = dm_res._derive_target_series(panel, target_col="forward_return_5d")

    corr_raw = float(pd.Series(y_raw).corr(pd.Series(market_rep)))
    corr_res = float(pd.Series(y_res).corr(pd.Series(market_rep)))

    assert bool(meta.get("target_market_residualize")) is True
    assert np.isfinite(corr_raw)
    assert np.isfinite(corr_res)
    assert abs(corr_res) < abs(corr_raw)
