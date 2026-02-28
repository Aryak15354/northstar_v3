from __future__ import annotations

import numpy as np
import pandas as pd

from src.research.alpha_factory import (
    build_family_factor_table,
    build_feature_family_map,
    compute_live_monitoring_metrics,
    estimate_stacked_ic,
    optimize_family_blend,
    simulate_signal_stacking,
)


def _synthetic_cross_sectional_frame() -> tuple[pd.DataFrame, list[str]]:
    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2024-01-01", periods=70)
    tickers = [f"T{i:03d}" for i in range(36)]
    n = len(dates) * len(tickers)

    date_col = np.repeat(dates.values, len(tickers))
    ticker_col = np.tile(np.asarray(tickers, dtype=object), len(dates))

    mom = rng.normal(size=n)
    mom_clone = mom + 0.02 * rng.normal(size=n)  # intentionally correlated for prune test
    quality = rng.normal(size=n)
    value = rng.normal(size=n)
    vol = rng.normal(size=n)
    debt = rng.normal(size=n)
    macro = rng.normal(size=n)
    sent = rng.normal(size=n)
    noise = 0.35 * rng.normal(size=n)

    future_ret = 0.20 * mom + 0.12 * quality + 0.06 * value - 0.15 * vol - 0.08 * debt + noise

    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(date_col),
            "ticker": ticker_col.astype(str),
            "forward_return_5d": future_ret.astype(float),
            "mom_20d_cs_z": mom.astype(float),
            "mom_20d_cs_rank": mom_clone.astype(float),
            "ni_margin": quality.astype(float),
            "posterior_gap": value.astype(float),
            "vol_20d_cs_z": vol.astype(float),
            "debt_to_equity": debt.astype(float),
            "macro_macro_score": macro.astype(float),
            "mkt_sent_polarity": sent.astype(float),
        }
    ).sort_values(["date", "ticker"])

    features = [
        "mom_20d_cs_z",
        "mom_20d_cs_rank",
        "ni_margin",
        "posterior_gap",
        "vol_20d_cs_z",
        "debt_to_equity",
        "macro_macro_score",
        "mkt_sent_polarity",
    ]
    return frame, features


def test_alpha_factory_family_mapping_and_aggregation() -> None:
    frame, features = _synthetic_cross_sectional_frame()
    fmap = build_feature_family_map(features)

    assert fmap["mom_20d_cs_z"] == "momentum"
    assert fmap["ni_margin"] == "quality"
    assert fmap["vol_20d_cs_z"] == "volatility"
    assert fmap["debt_to_equity"] == "leverage"

    payload = build_family_factor_table(
        frame,
        feature_cols=features,
        feature_family_map=fmap,
        min_obs_per_day=12,
        min_abs_ic=0.01,
        min_sign_consistency=0.51,
        corr_prune_threshold=0.85,
        min_features_per_family=1,
        max_features_per_family=5,
        long_short_quantile=0.20,
        min_assets_per_day=10,
    )

    assert payload["status"] == "ok"
    family_returns = payload["family_returns"]
    assert not family_returns.empty
    assert "momentum" in family_returns.columns
    assert "quality" in family_returns.columns
    # Momentum clone should be pruned under tight correlation threshold.
    assert payload["family_stats"]["momentum"]["n_features_selected"] == 1


def test_alpha_factory_covariance_blend_monitoring_and_stacking_math() -> None:
    frame, features = _synthetic_cross_sectional_frame()
    payload = build_family_factor_table(
        frame,
        feature_cols=features,
        min_obs_per_day=12,
        min_abs_ic=0.0,
        min_sign_consistency=0.0,
        corr_prune_threshold=0.90,
        min_features_per_family=1,
        max_features_per_family=4,
        long_short_quantile=0.20,
        min_assets_per_day=10,
    )
    rets = payload["family_returns"]
    ic_daily = payload["family_ic_daily"]

    blend = optimize_family_blend(
        rets,
        family_turnover=payload.get("family_turnover", {}),
        lookback_periods=60,
        shrinkage=0.60,
        target_annual_vol=0.15,
        min_history=30,
    )
    assert blend["status"] == "ok"
    gross = sum(abs(float(v)) for v in blend["weights"].values())
    assert np.isclose(gross, 1.0, atol=1e-6)
    assert float(blend["diagnostics"]["covariance_condition_number"]) >= 0.0

    mon = compute_live_monitoring_metrics(
        rets,
        family_ic_daily=ic_daily,
        lookback_periods=40,
        corr_lookback_periods=40,
    )
    assert mon["status"] == "ok"
    assert "correlation_drift" in mon

    ic_low_corr = estimate_stacked_ic(base_ic=0.02, n_signals=200, avg_pairwise_corr=0.05)
    ic_high_corr = estimate_stacked_ic(base_ic=0.02, n_signals=200, avg_pairwise_corr=0.20)
    assert ic_low_corr > ic_high_corr

    sim = simulate_signal_stacking(base_ic=0.02, n_signals=200, corr_grid=[0.05, 0.10, 0.20])
    assert len(sim["scenarios"]) == 3
    assert sim["scenarios"][0]["combined_ic"] > sim["scenarios"][-1]["combined_ic"]
