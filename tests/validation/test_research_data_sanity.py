"""Sanity checks for research dataset/metric stability guards."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pandas.testing as pdt

from scripts.run_regime_ic_split import _apply_sector_filter
from src.research.dataset_manager import DatasetManager, _sanitize_target_series
from src.research.diagnostics import compute_feature_ic_diagnostics
from src.research.feature_factory import FeatureFactory
from src.research.research_controller import ResearchController
from src.research.splits import rolling_time_splits
from src.research.training_pipeline import TrainingPipeline
from src.research.research_types import ResearchDataset
from src.research.walk_forward_validator import (
    _period_to_daily_returns,
    build_cross_sectional_portfolio_returns,
    compute_window_metrics,
)


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


def test_period_to_daily_returns_preserves_multi_day_compounding() -> None:
    period = np.array([0.12, -0.08, 0.0], dtype=float)
    daily = _period_to_daily_returns(period, period_days=5)

    recon = np.power(1.0 + daily, 5) - 1.0
    assert np.allclose(recon, period, atol=1e-6)


def test_compute_window_metrics_uses_realized_returns_for_directional_hit_rate() -> None:
    y_true = np.array([0.5, 0.5, 0.5, 0.5], dtype=float)  # transformed target (all positive)
    y_pred = np.array([1.0, -1.0, 1.0, -1.0], dtype=float)
    realized = np.array([0.08, -0.05, 0.04, -0.03], dtype=float)

    metrics = compute_window_metrics(
        y_true=y_true,
        y_pred=y_pred,
        realized_returns=realized,
        target_horizon_days=5,
    )

    assert float(metrics["hit_rate"]) > 0.99


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


def test_build_cross_sectional_portfolio_returns_applies_regime_exposure_scaling() -> None:
    rng = np.random.default_rng(23)
    n_days = 20
    n_assets = 12
    day_idx = np.repeat(np.arange(n_days), n_assets)
    dates = np.repeat(pd.date_range("2025-05-01", periods=n_days, freq="D").to_numpy(), n_assets)
    regimes = np.where(day_idx < 10, "low_vol|downtrend", "low_vol|uptrend").astype(object)
    latent = rng.normal(0.0, 0.02, size=n_days * n_assets)
    y_true = latent + rng.normal(0.0, 0.01, size=n_days * n_assets)
    y_pred = latent + rng.normal(0.0, 0.005, size=n_days * n_assets)
    vol = np.abs(rng.normal(0.2, 0.05, size=n_days * n_assets))

    base = build_cross_sectional_portfolio_returns(
        y_true=y_true,
        y_pred=y_pred,
        dates=dates,
        regimes=regimes,
        vol=vol,
        min_assets_per_day=8,
        rebalance_frequency_days=1,
        turnover_cap=1.0,
        high_vol_exposure_scale=1.0,
        return_diagnostics=True,
    )
    scaled = build_cross_sectional_portfolio_returns(
        y_true=y_true,
        y_pred=y_pred,
        dates=dates,
        regimes=regimes,
        vol=vol,
        min_assets_per_day=8,
        rebalance_frequency_days=1,
        turnover_cap=1.0,
        high_vol_exposure_scale=1.0,
        regime_exposure_scales={"low_vol|downtrend": 0.05, "default": 1.0},
        return_diagnostics=True,
    )
    assert isinstance(base, dict)
    assert isinstance(scaled, dict)
    base_rets = np.asarray(base.get("returns", np.asarray([], dtype=float)), dtype=float)
    base_dates = pd.to_datetime(pd.Series(base.get("return_dates", [])), errors="coerce")
    scaled_rets = np.asarray(scaled.get("returns", np.asarray([], dtype=float)), dtype=float)
    scaled_dates = pd.to_datetime(pd.Series(scaled.get("return_dates", [])), errors="coerce")

    assert len(base_rets) > 0
    assert len(base_rets) == len(scaled_rets)
    assert len(base_dates) == len(scaled_dates)

    regime_by_date = {
        pd.Timestamp(dates[i]).normalize(): str(regimes[i]) for i in range(0, len(dates), n_assets)
    }
    base_day_regime = base_dates.dt.normalize().map(regime_by_date).astype(str).to_numpy()
    scaled_day_regime = scaled_dates.dt.normalize().map(regime_by_date).astype(str).to_numpy()
    low_mask_base = base_day_regime == "low_vol|downtrend"
    low_mask_scaled = scaled_day_regime == "low_vol|downtrend"
    high_mask_base = base_day_regime == "low_vol|uptrend"
    high_mask_scaled = scaled_day_regime == "low_vol|uptrend"

    assert int(low_mask_base.sum()) > 0
    assert int(low_mask_scaled.sum()) == int(low_mask_base.sum())
    assert int(high_mask_base.sum()) > 0
    assert int(high_mask_scaled.sum()) == int(high_mask_base.sum())

    low_abs_base = float(np.mean(np.abs(base_rets[low_mask_base])))
    low_abs_scaled = float(np.mean(np.abs(scaled_rets[low_mask_scaled])))
    high_abs_base = float(np.mean(np.abs(base_rets[high_mask_base])))
    high_abs_scaled = float(np.mean(np.abs(scaled_rets[high_mask_scaled])))

    assert low_abs_scaled < (0.25 * low_abs_base)
    assert np.isclose(high_abs_scaled, high_abs_base, atol=1e-10)


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


def test_dataset_manager_excludes_forward_target_columns_from_features(tmp_path) -> None:
    dates = pd.date_range("2025-01-01", periods=40, freq="D")
    prices = pd.DataFrame(
        {
            "Date": np.tile(dates, 2),
            "ticker": ["AAA"] * len(dates) + ["BBB"] * len(dates),
            "Close": np.concatenate(
                [
                    np.linspace(100.0, 120.0, len(dates)),
                    np.linspace(80.0, 95.0, len(dates)),
                ]
            ),
            "Volume": 1000.0,
        }
    )

    dm = DatasetManager(
        project_root=tmp_path,
        config={
            "strict_real_data_only": False,
            "target_col": "forward_return_5d",
            "target_horizon_days": 5,
            "lookback_days": 3650,
            "max_rows": 200000,
        },
    )
    dm.load_prices = lambda: prices.copy()  # type: ignore[assignment]
    dm.load_fundamentals = lambda: pd.DataFrame()  # type: ignore[assignment]
    dm.load_macro = lambda: pd.DataFrame()  # type: ignore[assignment]
    dm.load_valuation_posterior = lambda: pd.DataFrame()  # type: ignore[assignment]
    dm.load_sentiment_company = lambda: pd.DataFrame()  # type: ignore[assignment]
    dm.load_sentiment_market = lambda: pd.DataFrame()  # type: ignore[assignment]

    ds = dm.build_research_dataset()
    fset = set(str(x) for x in ds.feature_names)

    assert "forward_return_5d__realized" not in fset
    assert not any(str(x).startswith("forward_return_") for x in fset)
    assert ds.metadata.get("target_col") == "forward_return_5d"


def test_training_pipeline_label_embargo_drops_pre_test_rows() -> None:
    dates = pd.date_range("2025-01-01", periods=12, freq="D")
    frame = pd.DataFrame({"date": np.repeat(dates, 2), "ticker": ["A", "B"] * len(dates)})

    train_dates = set(dates[:8])  # 1..8
    test_dates = set(dates[8:])   # 9..12
    row_dates = pd.to_datetime(frame["date"], errors="coerce").to_numpy()
    train_mask = np.array([d in train_dates for d in row_dates], dtype=bool)
    test_mask = np.array([d in test_dates for d in row_dates], dtype=bool)

    pipe = TrainingPipeline()
    filtered, dropped = pipe._apply_label_embargo(
        frame=frame,
        train_mask=train_mask,
        test_mask=test_mask,
        date_col="date",
        embargo_periods=3,
    )

    kept_dates = set(pd.to_datetime(frame.loc[filtered, "date"]).dt.normalize().tolist())
    assert dropped > 0
    # With a 3-day embargo and test starting on day 9, days 6-8 should be removed.
    assert pd.Timestamp("2025-01-06") not in kept_dates
    assert pd.Timestamp("2025-01-07") not in kept_dates
    assert pd.Timestamp("2025-01-08") not in kept_dates


def test_feature_factory_pit_merge_has_no_future_leakage() -> None:
    dates = pd.date_range("2025-01-01", periods=8, freq="D")
    prices = pd.DataFrame(
        {
            "Date": np.tile(dates, 2),
            "ticker": ["AAA"] * len(dates) + ["BBB"] * len(dates),
            "Close": np.concatenate(
                [
                    np.linspace(100.0, 108.0, len(dates)),
                    np.linspace(70.0, 76.0, len(dates)),
                ]
            ),
        }
    )
    fundamentals = pd.DataFrame(
        {
            "ticker": ["AAA", "BBB"],
            "date": pd.to_datetime(["2025-01-01", "2025-01-01"]),
            "announcement_date": pd.to_datetime(["2025-01-03", "2025-01-04"]),
            "revenue": [100.0, 90.0],
            "net_income": [12.0, 8.0],
            "equity": [60.0, 55.0],
            "total_debt": [20.0, 25.0],
            "operating_cash_flow": [15.0, 12.0],
            "free_cash_flow": [11.0, 9.0],
        }
    )

    panel = FeatureFactory(target_horizon_days=1).build_features(prices=prices, fundamentals=fundamentals)
    df = panel.dropna(subset=["availability_date", "trade_date"]).copy()
    assert not df.empty
    assert (df["availability_date"] <= df["trade_date"]).all(), "PIT leak detected — future fundamentals present"


def test_feature_factory_pit_merge_is_deterministic_for_shuffled_multiticker_input() -> None:
    dates = pd.date_range("2025-01-01", periods=16, freq="D")
    prices = pd.DataFrame(
        {
            "Date": np.tile(dates, 2),
            "ticker": ["AAA"] * len(dates) + ["BBB"] * len(dates),
            "Close": np.concatenate(
                [
                    np.linspace(100.0, 120.0, len(dates)),
                    np.linspace(80.0, 95.0, len(dates)),
                ]
            ),
        }
    )
    fundamentals = pd.DataFrame(
        {
            "ticker": ["AAA", "AAA", "BBB", "BBB"],
            "date": pd.to_datetime(["2024-12-31", "2025-01-08", "2024-12-31", "2025-01-09"]),
            "announcement_date": pd.to_datetime(["2025-01-03", "2025-01-10", "2025-01-04", "2025-01-11"]),
            "revenue": [100.0, 105.0, 90.0, 93.0],
            "net_income": [10.0, 11.0, 8.0, 8.5],
            "equity": [60.0, 61.0, 55.0, 55.5],
            "total_debt": [20.0, 19.0, 25.0, 24.0],
            "operating_cash_flow": [13.0, 13.5, 11.0, 11.5],
            "free_cash_flow": [9.0, 9.2, 7.0, 7.4],
        }
    )

    factory = FeatureFactory(target_horizon_days=1)
    baseline = factory.build_features(prices=prices, fundamentals=fundamentals)

    prices_shuffled = prices.sample(frac=1.0, random_state=7).reset_index(drop=True)
    fundamentals_shuffled = fundamentals.sample(frac=1.0, random_state=11).reset_index(drop=True)
    shuffled = factory.build_features(prices=prices_shuffled, fundamentals=fundamentals_shuffled)

    cols = ["trade_date", "ticker", "availability_date", "revenue", "net_income", "forward_return_5d"]
    left = baseline[cols].sort_values(["trade_date", "ticker"]).reset_index(drop=True)
    right = shuffled[cols].sort_values(["trade_date", "ticker"]).reset_index(drop=True)
    pdt.assert_frame_equal(left, right)


def test_dataset_manager_universe_cap_divergence_between_100_and_500() -> None:
    n_tickers = 600
    n_days = 28
    dates = pd.date_range("2025-01-01", periods=n_days, freq="D")
    tickers = [f"T{i:03d}.NS" for i in range(n_tickers)]
    rows = []
    for i, tk in enumerate(tickers):
        base = 90.0 + (i % 25)
        for j, dt in enumerate(dates):
            rows.append(
                {
                    "Date": dt,
                    "ticker": tk,
                    "Close": base + 0.2 * j,
                    "Volume": 1000.0 + float(i),
                }
            )
    prices = pd.DataFrame(rows)

    def _build(max_tickers: int):
        dm = DatasetManager(
            config={
                "strict_real_data_only": False,
                "target_horizon_days": 1,
                "max_tickers": int(max_tickers),
                "max_rows": 500000,
                "lookback_days": 3650,
                "enable_macro_features": False,
                "low_resource_mode": "disabled",
            }
        )
        dm.load_prices = lambda: prices.copy()  # type: ignore[assignment]
        dm.load_fundamentals = lambda: pd.DataFrame()  # type: ignore[assignment]
        dm.load_macro = lambda: pd.DataFrame()  # type: ignore[assignment]
        dm.load_valuation_posterior = lambda: pd.DataFrame()  # type: ignore[assignment]
        dm.load_sentiment_company = lambda: pd.DataFrame()  # type: ignore[assignment]
        dm.load_sentiment_market = lambda: pd.DataFrame()  # type: ignore[assignment]
        return dm.build_research_dataset()

    ds_100 = _build(100)
    ds_500 = _build(500)

    assert int(ds_100.metadata.get("effective_max_tickers", 0)) == 100
    assert int(ds_500.metadata.get("effective_max_tickers", 0)) == 500
    assert int(ds_100.metadata.get("n_tickers", 0)) <= 100
    assert int(ds_500.metadata.get("n_tickers", 0)) <= 500
    assert int(ds_500.metadata.get("n_tickers", 0)) > int(ds_100.metadata.get("n_tickers", 0))
    assert int(ds_500.metadata.get("n_rows", 0)) > int(ds_100.metadata.get("n_rows", 0))


def test_sector_filter_keeps_it_aliases_non_empty_after_canonicalization() -> None:
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(
                [
                    "2025-01-01",
                    "2025-01-01",
                    "2025-01-01",
                    "2025-01-01",
                ]
            ),
            "ticker": ["AAA", "BBB", "CCC", "DDD"],
            "sector_name": ["IT", "Technology", "Information Technology", "Banks"],
            "f1": [1.0, 2.0, 3.0, 4.0],
            "forward_return_5d": [0.01, 0.02, 0.03, -0.01],
        }
    )
    dataset = ResearchDataset(
        X=frame[["f1"]].to_numpy(dtype=float),
        y=frame["forward_return_5d"].to_numpy(dtype=float),
        feature_names=["f1"],
        metadata={"target_col": "forward_return_5d"},
        index=pd.DatetimeIndex(frame["date"]),
        tickers=frame["ticker"].to_numpy(),
        frame=frame.copy(),
    )

    _apply_sector_filter(dataset, ["it"])

    assert int(len(dataset.frame)) > 0
    assert int(dataset.metadata.get("n_rows", 0)) > 0
    assert set(dataset.frame["ticker"].tolist()) == {"AAA", "BBB", "CCC"}


def test_dataset_manager_roadmap_macro_disable_emits_no_macro_features() -> None:
    dates = pd.date_range("2025-01-01", periods=24, freq="D")
    prices = pd.DataFrame(
        {
            "Date": np.tile(dates, 2),
            "ticker": ["AAA"] * len(dates) + ["BBB"] * len(dates),
            "Close": np.concatenate(
                [
                    np.linspace(100.0, 110.0, len(dates)),
                    np.linspace(70.0, 82.0, len(dates)),
                ]
            ),
        }
    )

    dm = DatasetManager(
        config={
            "strict_real_data_only": False,
            "target_horizon_days": 1,
            "enable_macro_features": False,
            "max_tickers": 50,
            "max_rows": 200000,
            "lookback_days": 3650,
        }
    )
    dm.load_prices = lambda: prices.copy()  # type: ignore[assignment]
    dm.load_fundamentals = lambda: pd.DataFrame()  # type: ignore[assignment]
    dm.load_macro = lambda: (_ for _ in ()).throw(AssertionError("load_macro should not be called"))  # type: ignore[assignment]
    dm.load_valuation_posterior = lambda: pd.DataFrame()  # type: ignore[assignment]
    dm.load_sentiment_company = lambda: pd.DataFrame()  # type: ignore[assignment]
    dm.load_sentiment_market = lambda: pd.DataFrame()  # type: ignore[assignment]

    ds = dm.build_research_dataset()
    assert bool(ds.metadata.get("macro_features_enabled")) is False
    assert not any(str(c).startswith("macro_") for c in ds.feature_names)


def test_rolling_time_splits_uses_min_tickers_per_date_not_full_intersection() -> None:
    dates = pd.date_range("2025-01-01", periods=10, freq="D")
    rows = []
    for dt in dates:
        rows.append({"date": dt, "ticker": "AAA"})
        rows.append({"date": dt, "ticker": "BBB"})
    for dt in dates[-3:]:
        rows.append({"date": dt, "ticker": "CCC"})
    frame = pd.DataFrame(rows)

    sparse_ok = list(
        rolling_time_splits(
            frame,
            date_col="date",
            train_periods=4,
            valid_periods=2,
            test_periods=2,
            step_periods=1,
            min_tickers_per_date=2,
        )
    )
    full_only = list(
        rolling_time_splits(
            frame,
            date_col="date",
            train_periods=4,
            valid_periods=2,
            test_periods=2,
            step_periods=1,
            min_tickers_per_date=3,
        )
    )

    assert len(sparse_ok) > 0
    assert len(full_only) == 0


def test_feature_factory_cross_sectional_ops_handle_unbalanced_panel_dates() -> None:
    d1 = pd.date_range("2025-01-01", periods=8, freq="D")
    d2 = pd.date_range("2025-01-05", periods=4, freq="D")
    prices = pd.DataFrame(
        {
            "Date": list(d1) + list(d2),
            "ticker": ["AAA"] * len(d1) + ["BBB"] * len(d2),
            "Close": list(np.linspace(100.0, 107.0, len(d1))) + list(np.linspace(80.0, 84.0, len(d2))),
            "Volume": [1000.0] * (len(d1) + len(d2)),
        }
    )

    panel = FeatureFactory(target_horizon_days=1).build_features(prices=prices)
    unique_dates = int(panel["date"].nunique())

    assert not panel.empty
    assert unique_dates > 3  # full-intersection path would collapse near overlap-only dates
    assert "ret_1d_cs_z" in panel.columns
    assert np.isfinite(pd.to_numeric(panel["ret_1d_cs_z"], errors="coerce").fillna(0.0).to_numpy(dtype=float)).all()


def test_et500_mapping_file_exists_and_has_unique_matched_tickers() -> None:
    mapping_path = Path("data/reference/et500_name_to_ticker.csv")
    assert mapping_path.exists(), f"missing mapping file: {mapping_path}"

    mapping = pd.read_csv(mapping_path)
    assert {"company_name", "nse_ticker"}.issubset(set(mapping.columns))
    matched = mapping[mapping["nse_ticker"].astype(str).ne("UNMATCHED")].copy()
    assert len(matched) > 0
    assert not bool(matched["nse_ticker"].duplicated().any())


def test_et500_pit_membership_year_range_and_counts_align_with_mapping() -> None:
    et_source_path = Path("universe/Economic times Top 500 companies since 2009 - 2009-2021.csv")
    mapping_path = Path("data/reference/et500_name_to_ticker.csv")
    membership_path = Path("data/reference/et500_pit_membership.csv")
    assert et_source_path.exists()
    assert mapping_path.exists()
    assert membership_path.exists()

    source = pd.read_csv(et_source_path)
    source["company_name"] = source["COMPANY NAME"].astype(str).str.strip()
    mapping = pd.read_csv(mapping_path)
    membership = pd.read_csv(membership_path)

    merged = source.merge(mapping, on="company_name", how="left")
    merged["nse_ticker"] = merged["nse_ticker"].fillna("UNMATCHED")
    expected_counts = (
        merged.loc[merged["nse_ticker"].ne("UNMATCHED")]
        .groupby("Year", sort=True)["nse_ticker"]
        .count()
        .astype(int)
    )
    actual_counts = membership.groupby("year", sort=True)["nse_ticker"].count().astype(int)

    expected_years = list(range(2009, 2022))
    assert sorted(actual_counts.index.tolist()) == expected_years
    assert actual_counts.to_dict() == expected_counts.reindex(expected_years, fill_value=0).to_dict()
    assert bool((actual_counts > 0).all())
    assert bool((actual_counts <= 500).all())


def test_feature_factory_et500_rank_change_non_null_for_mapped_tickers() -> None:
    membership_path = Path("data/reference/et500_pit_membership.csv")
    assert membership_path.exists()
    membership = pd.read_csv(membership_path)
    tickers = membership.loc[membership["year"] == 2021, "nse_ticker"].dropna().astype(str).head(3).tolist()
    assert len(tickers) >= 2

    dates = pd.date_range("2022-01-10", periods=16, freq="D")
    rows = []
    for i, tk in enumerate(tickers):
        for j, dt in enumerate(dates):
            rows.append(
                {
                    "Date": dt,
                    "ticker": tk,
                    "Close": 100.0 + float(i) + 0.5 * float(j),
                    "Volume": 1000.0 + float(i),
                }
            )
    prices = pd.DataFrame(rows)
    panel = FeatureFactory(target_horizon_days=1, use_et500_features=True).build_features(
        prices=prices,
        et500_membership=membership,
    )

    assert "et500_rank_change" in panel.columns
    for tk in tickers:
        vals = pd.to_numeric(panel.loc[panel["ticker"] == tk, "et500_rank_change"], errors="coerce")
        assert bool(vals.notna().any())


def test_dataset_manager_et500_universe_filter_reduces_ticker_count(tmp_path) -> None:
    ref_dir = tmp_path / "data/reference"
    ref_dir.mkdir(parents=True, exist_ok=True)
    membership = pd.DataFrame(
        {
            "year": [2010, 2011],
            "nse_ticker": ["AAA.NS", "BBB.NS"],
            "rank": [10, 20],
            "prev_rank": [15, 30],
            "revenue_cr": [1000.0, 900.0],
            "revenue_change_pct": [5.0, 4.0],
            "pat_cr": [100.0, 90.0],
            "pat_change_pct": [2.0, 1.0],
            "market_cap_cr": [5000.0, 4000.0],
        }
    )
    membership_path = ref_dir / "et500_pit_membership.csv"
    membership.to_csv(membership_path, index=False)

    dates = pd.date_range("2011-01-01", periods=90, freq="D")
    rows = []
    for tk in ["AAA.NS", "BBB.NS", "CCC.NS"]:
        for i, dt in enumerate(dates):
            rows.append({"Date": dt, "ticker": tk, "Close": 100.0 + 0.1 * i, "Volume": 1000.0})
    prices = pd.DataFrame(rows)

    common_cfg = {
        "strict_real_data_only": False,
        "target_horizon_days": 1,
        "lookback_days": 3650,
        "max_tickers": 20,
        "max_rows": 200000,
        "et500_membership_path": str(membership_path.relative_to(tmp_path)),
    }
    dm_unfiltered = DatasetManager(project_root=tmp_path, config=dict(common_cfg))
    dm_unfiltered.load_prices = lambda: prices.copy()  # type: ignore[assignment]
    dm_unfiltered.load_fundamentals = lambda: pd.DataFrame()  # type: ignore[assignment]
    dm_unfiltered.load_macro = lambda: pd.DataFrame()  # type: ignore[assignment]
    dm_unfiltered.load_valuation_posterior = lambda: pd.DataFrame()  # type: ignore[assignment]
    dm_unfiltered.load_sentiment_company = lambda: pd.DataFrame()  # type: ignore[assignment]
    dm_unfiltered.load_sentiment_market = lambda: pd.DataFrame()  # type: ignore[assignment]
    ds_unfiltered = dm_unfiltered.build_research_dataset()

    cfg_filtered = dict(common_cfg)
    cfg_filtered["use_et500_universe_filter"] = True
    dm_filtered = DatasetManager(project_root=tmp_path, config=cfg_filtered)
    dm_filtered.load_prices = lambda: prices.copy()  # type: ignore[assignment]
    dm_filtered.load_fundamentals = lambda: pd.DataFrame()  # type: ignore[assignment]
    dm_filtered.load_macro = lambda: pd.DataFrame()  # type: ignore[assignment]
    dm_filtered.load_valuation_posterior = lambda: pd.DataFrame()  # type: ignore[assignment]
    dm_filtered.load_sentiment_company = lambda: pd.DataFrame()  # type: ignore[assignment]
    dm_filtered.load_sentiment_market = lambda: pd.DataFrame()  # type: ignore[assignment]
    ds_filtered = dm_filtered.build_research_dataset()

    assert int(ds_filtered.metadata.get("n_tickers", 0)) < int(ds_unfiltered.metadata.get("n_tickers", 0))


def test_dataset_manager_et500_universe_filter_is_pit_safe(tmp_path) -> None:
    ref_dir = tmp_path / "data/reference"
    ref_dir.mkdir(parents=True, exist_ok=True)
    membership = pd.DataFrame(
        {
            "year": [2012, 2015],
            "nse_ticker": ["OLD.NS", "FUTR.NS"],
            "rank": [10, 5],
            "prev_rank": [12, 8],
            "revenue_cr": [1000.0, 1200.0],
            "revenue_change_pct": [1.0, 2.0],
            "pat_cr": [100.0, 130.0],
            "pat_change_pct": [1.0, 2.0],
            "market_cap_cr": [5000.0, 6000.0],
        }
    )
    membership_path = ref_dir / "et500_pit_membership.csv"
    membership.to_csv(membership_path, index=False)

    dates = pd.date_range("2013-01-01", periods=80, freq="D")
    rows = []
    for tk in ["OLD.NS", "FUTR.NS"]:
        for i, dt in enumerate(dates):
            rows.append({"Date": dt, "ticker": tk, "Close": 100.0 + 0.2 * i, "Volume": 900.0})
    prices = pd.DataFrame(rows)

    dm = DatasetManager(
        project_root=tmp_path,
        config={
            "strict_real_data_only": False,
            "target_horizon_days": 1,
            "lookback_days": 3650,
            "max_tickers": 10,
            "max_rows": 200000,
            "use_et500_universe_filter": True,
            "et500_membership_path": str(membership_path.relative_to(tmp_path)),
        },
    )
    dm.load_prices = lambda: prices.copy()  # type: ignore[assignment]
    dm.load_fundamentals = lambda: pd.DataFrame()  # type: ignore[assignment]
    dm.load_macro = lambda: pd.DataFrame()  # type: ignore[assignment]
    dm.load_valuation_posterior = lambda: pd.DataFrame()  # type: ignore[assignment]
    dm.load_sentiment_company = lambda: pd.DataFrame()  # type: ignore[assignment]
    dm.load_sentiment_market = lambda: pd.DataFrame()  # type: ignore[assignment]
    ds = dm.build_research_dataset()

    frame = ds.frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    pre_2015 = frame.loc[frame["date"].dt.year <= 2014]
    assert "OLD.NS" in set(pre_2015["ticker"].astype(str))
    assert "FUTR.NS" not in set(pre_2015["ticker"].astype(str))


def test_merged_screener_annual_file_has_active_and_delisted_rows() -> None:
    path = Path("data/processed/screener_fundamentals_annual.csv")
    assert path.exists()
    df = pd.read_csv(path)
    assert "is_delisted" in df.columns
    vals = set(df["is_delisted"].astype(str).str.lower().tolist())
    assert "true" in vals
    assert "false" in vals


def test_merged_screener_annual_has_no_duplicate_ticker_fiscal_year_pairs() -> None:
    path = Path("data/processed/screener_fundamentals_annual.csv")
    assert path.exists()
    df = pd.read_csv(path)
    dupes = df.duplicated(subset=["ticker", "fiscal_year"], keep=False)
    assert not bool(dupes.any())


def test_merged_screener_shareholding_has_active_and_delisted_rows() -> None:
    path = Path("data/processed/screener_shareholding.csv")
    assert path.exists()
    df = pd.read_csv(path)
    assert "is_delisted" in df.columns
    vals = set(df["is_delisted"].astype(str).str.lower().tolist())
    assert "true" in vals
    assert "false" in vals


def _build_screener_feature_test_panel(tmp_path: Path, *, use_screener_features: bool) -> pd.DataFrame:
    annual = pd.DataFrame(
        {
            "ticker": [
                "AAA.NS",
                "AAA.NS",
                "AAA.NS",
                "BBB.NS",
                "BBB.NS",
                "BBB.NS",
            ],
            "fiscal_year": [2021, 2022, 2023, 2021, 2022, 2023],
            "availability_date": pd.to_datetime(
                ["2022-03-01", "2023-03-01", "2024-03-01", "2022-03-01", "2023-03-01", "2024-03-01"]
            ),
            "sales": [100.0, 120.0, 140.0, 80.0, 88.0, 100.0],
            "operating_profit": [20.0, 27.0, 35.0, 12.0, 14.0, 16.0],
            "net_profit": [10.0, 12.0, 14.0, 6.0, 7.0, 8.0],
            "roce_pct": [15.0, 17.0, 19.0, 11.0, 12.0, 13.0],
            "debtor_days": [50.0, 48.0, 46.0, 60.0, 58.0, 56.0],
            "cash_conversion_cycle": [70.0, 68.0, 66.0, 90.0, 88.0, 86.0],
            "cash_from_operating_activity": [200.0, 180.0, -200.0, 24.0, 21.0, 20.0],
        }
    )
    share = pd.DataFrame(
        {
            "ticker": ["AAA.NS"] * 6 + ["BBB.NS"] * 6,
            "quarter": [
                "Q1-2023",
                "Q2-2023",
                "Q3-2023",
                "Q4-2023",
                "Q1-2024",
                "Q2-2024",
                "Q1-2023",
                "Q2-2023",
                "Q3-2023",
                "Q4-2023",
                "Q1-2024",
                "Q2-2024",
            ],
            "availability_date": pd.to_datetime(
                [
                    "2023-05-15",
                    "2023-08-14",
                    "2023-11-14",
                    "2024-02-14",
                    "2024-05-15",
                    "2024-08-14",
                    "2023-05-15",
                    "2023-08-14",
                    "2023-11-14",
                    "2024-02-14",
                    "2024-05-15",
                    "2024-08-14",
                ]
            ),
            "promoter_pct": [55.0, 55.3, 55.7, 56.0, 56.4, 56.9, 40.0, 39.8, 39.7, 39.6, 39.4, 39.3],
            "fii_pct": [18.0, 18.2, 18.4, 18.7, 19.0, 19.3, 20.0, 19.8, 19.7, 19.5, 19.3, 19.0],
            "dii_pct": [10.0, 10.1, 10.2, 10.4, 10.5, 10.6, 12.0, 12.1, 12.2, 12.2, 12.3, 12.4],
        }
    )

    annual_path = tmp_path / "screener_fundamentals_annual.csv"
    share_path = tmp_path / "screener_shareholding.csv"
    annual.to_csv(annual_path, index=False)
    share.to_csv(share_path, index=False)

    dates = pd.date_range("2023-01-01", "2024-12-31", freq="D")
    prices = pd.DataFrame(
        {
            "Date": np.tile(dates, 2),
            "ticker": ["AAA.NS"] * len(dates) + ["BBB.NS"] * len(dates),
            "Close": np.linspace(100.0, 160.0, len(dates)).tolist() + np.linspace(50.0, 90.0, len(dates)).tolist(),
            "Volume": [1000.0] * len(dates) + [1200.0] * len(dates),
        }
    )

    factory = FeatureFactory(
        target_horizon_days=1,
        use_screener_features=use_screener_features,
        screener_fundamentals_path=str(annual_path),
        screener_shareholding_path=str(share_path),
    )
    panel = factory.build_features(prices=prices, fundamentals=pd.DataFrame())
    return panel


def test_screener_cfo_to_pat_is_clipped_within_bounds(tmp_path) -> None:
    panel = _build_screener_feature_test_panel(tmp_path, use_screener_features=True)
    vals = pd.to_numeric(panel["screener_cfo_to_pat"], errors="coerce").dropna()
    assert not vals.empty
    assert float(vals.min()) >= -5.0
    assert float(vals.max()) <= 5.0


def test_screener_promoter_change_features_are_differenced(tmp_path) -> None:
    panel = _build_screener_feature_test_panel(tmp_path, use_screener_features=True)
    one_q = pd.to_numeric(panel["screener_promoter_change_1q"], errors="coerce")
    prom = pd.to_numeric(panel["screener_promoter_pct"], errors="coerce")
    valid = pd.concat([prom, one_q], axis=1).dropna()
    assert not valid.empty
    assert not np.allclose(valid.iloc[:, 0].to_numpy(), valid.iloc[:, 1].to_numpy())

    four_q = pd.to_numeric(panel["screener_promoter_change_4q"], errors="coerce")
    assert int(four_q.isna().sum()) > int(one_q.isna().sum())


def test_feature_factory_emits_screener_columns_when_enabled(tmp_path) -> None:
    panel = _build_screener_feature_test_panel(tmp_path, use_screener_features=True)
    assert "screener_opm_pct_cs_z" in panel.columns


def test_feature_factory_omits_screener_columns_when_disabled(tmp_path) -> None:
    panel = _build_screener_feature_test_panel(tmp_path, use_screener_features=False)
    screener_cols = [c for c in panel.columns if str(c).startswith("screener_")]
    assert not screener_cols


def test_screener_pit_merge_has_no_future_leakage(tmp_path) -> None:
    panel = _build_screener_feature_test_panel(tmp_path, use_screener_features=True)
    date_col = pd.to_datetime(panel["date"], errors="coerce")

    annual_av = pd.to_datetime(panel.get("screener_availability_date", pd.NaT), errors="coerce")
    annual_feat = pd.to_numeric(panel.get("screener_opm_pct", np.nan), errors="coerce")
    annual_mask = annual_feat.notna() & annual_av.notna() & date_col.notna()
    assert bool((annual_av[annual_mask] <= date_col[annual_mask]).all())

    share_av = pd.to_datetime(panel.get("screener_shareholding_availability_date", pd.NaT), errors="coerce")
    share_feat = pd.to_numeric(panel.get("screener_promoter_pct", np.nan), errors="coerce")
    share_mask = share_feat.notna() & share_av.notna() & date_col.notna()
    assert bool((share_av[share_mask] <= date_col[share_mask]).all())
