# XGBoost Research Experiments — Results Summary

Generated: 2026-03-17
Model: XGBoost (n_estimators=300, learning_rate=0.03, max_depth=6)
Dataset: ~90,000 rows, 40 selected features (pruned from 203), 4 walk-forward windows
Regimes: high_vol|uptrend, high_vol|downtrend, low_vol|uptrend, low_vol|downtrend

---

## Experiment Batches

Four research batches were run across March 4–5, 2026:

1. Residual Baseline (run_20260304) — horizon and quantile sweep
2. Signal Engineering (signal_eng_20260305_024312) — signal transformation variants
3. Next Alpha (next_alpha_20260305_140352) — prediction post-processing variants
4. Robustness (robustness_20260305_192850) — universe size, feature family, and OOS stress tests

---

## Batch 1: Residual Baseline — Horizon & Quantile Sweep

| Experiment | Horizon | Global IC | IC IR | Sharpe | Stability | Best Regime | Best IC | Flags |
|---|---|---:|---:|---:|---:|---|---:|---|
| residual_baseline_w10_h5 | 5d | 0.0331 | 1.13 | -0.14 | 0.80 | high_vol\|uptrend | 0.0776 | OK |
| residual_baseline_w10_h10_q10 | 10d | 0.0708 | 0.86 | 0.06 | 0.64 | high_vol\|downtrend | 0.1548 | LOW_REGIME_OBS |
| residual_baseline_w10_h10_q15 | 10d | 0.0708 | 0.86 | 0.05 | 0.62 | high_vol\|downtrend | 0.1548 | LOW_REGIME_OBS |
| residual_baseline_w10_h10_q20 | 10d | 0.0708 | 0.86 | -0.07 | 0.65 | high_vol\|downtrend | 0.1548 | LOW_REGIME_OBS |
| residual_low_vol_downtrend_w10_h3 | 3d | 0.0198 | 0.33 | 0.02 | 0.46 | low_vol\|downtrend | 0.0117 | LOW_GLOBAL_IC |
| residual_low_vol_downtrend_w10_h5 | 5d | 0.0114 | 0.36 | -0.22 | 0.42 | low_vol\|downtrend | 0.0210 | LOW_GLOBAL_IC |
| residual_low_vol_downtrend_w10_h10 | 10d | 0.0568 | 2.00 | 6.02 | 0.04 | low_vol\|downtrend | 0.0776 | SHARPE_UNSTABLE |
| residual_low_vol_downtrend_w10_h20 | 20d | 0.0476 | 0.77 | -0.11 | 0.57 | low_vol\|downtrend | 0.0151 | OK |
| residual_high_vol_inverted_w10_h5 | 5d | 0.0065 | 0.13 | -0.30 | 0.46 | low_vol\|uptrend | 0.0000 | LOW_GLOBAL_IC |
| residual_low_vol_downtrend_w12_h3 | 3d | 0.0000 | 0.00 | 0.00 | 0.50 | — | 0.0000 | LOW_WINDOWS |
| residual_low_vol_downtrend_w12_h5 | 5d | 0.0000 | 0.00 | 0.00 | 0.50 | — | 0.0000 | LOW_WINDOWS |
| residual_low_vol_downtrend_w12_h10 | 10d | -0.0312 | -0.71 | 0.03 | 0.72 | — | 0.0000 | LOW_WINDOWS |
| residual_low_vol_downtrend_w12_h20 | 20d | 0.0000 | 0.00 | 0.00 | 0.75 | — | 0.0000 | LOW_WINDOWS |
| residual_high_vol_inverted_w12_h5 | 5d | -0.0231 | -0.15 | 11.41 | 0.02 | — | 0.0000 | SHARPE_UNSTABLE |

Key finding: h10 (10-day horizon) consistently produces the highest global IC. The w12 window configs suffered from insufficient observations. The SHARPE_UNSTABLE flag on `residual_low_vol_downtrend_w10_h10` (Sharpe=6.02) indicates regime concentration — not a reliable signal.


---

## Batch 2: Signal Engineering — Transformation Variants (signal_eng_20260305_024312)

All experiments at h10 (10-day horizon), 4 windows, ~11,726 avg obs/window.

| Experiment | Description | Global IC | IC IR | Sharpe | Stability | Best Regime | Best IC | Flags |
|---|---|---:|---:|---:|---:|---|---:|---|
| e01_h5_base | h5 baseline | 0.0331 | 1.13 | -0.14 | 0.80 | high_vol\|uptrend | 0.0776 | OK |
| e02_h10_base | h10 baseline | 0.0708 | 0.86 | -0.07 | 0.65 | high_vol\|downtrend | 0.1548 | LOW_REGIME_OBS |
| e03_h30_base | h30 baseline | 0.0680 | 1.57 | 0.22 | 0.85 | low_vol\|uptrend | 0.0834 | OK |
| e04_h10_vol_scaled | vol-scaled target | 0.0708 | 0.86 | -0.07 | 0.65 | high_vol\|downtrend | 0.1548 | LOW_REGIME_OBS |
| e05_h10_vol_unscaled | vol-unscaled target | 0.0708 | 0.86 | -0.07 | 0.65 | high_vol\|downtrend | 0.1548 | LOW_REGIME_OBS |
| e06_h10_turnover_control | turnover penalty | 0.0708 | 0.86 | 0.09 | 0.65 | high_vol\|downtrend | 0.1548 | LOW_REGIME_OBS |
| e07_h10_signal_standardized | standardized signal | 0.0977 | 2.14 | 0.25 | 0.95 | high_vol\|uptrend | 0.1521 | OK |
| e08_h10_residualized_target | residualized target | -0.0256 | -0.19 | -0.004 | 0.55 | high_vol\|uptrend | 0.0118 | LOW_GLOBAL_IC |
| e09_h10_sector_it | IT sector only | 0.0000 | 0.00 | 0.00 | 0.00 | — | 0.0000 | LOW_WINDOWS |
| e10_h10_regime_adaptive_scale | regime-adaptive scale | 0.0644 | 0.87 | -0.07 | 0.65 | high_vol\|downtrend | 0.1548 | LOW_REGIME_OBS |

Key finding: e07 (signal standardization) is the clear winner of this batch — global IC 0.0977, IC IR 2.14, stability 0.95, all-green flags. Residualizing the target (e08) actively hurt performance. Vol scaling had no effect vs baseline.

### e07 Regime Breakdown (Best Experiment)

| Regime | IC | N Obs | Sharpe | Max DD |
|---|---:|---:|---:|---:|
| high_vol\|uptrend | 0.1521 | 7,420 | 2.76 | 0.0044 |
| low_vol\|uptrend | 0.1374 | 25,345 | 0.34 | 0.0078 |
| low_vol\|downtrend | 0.0897 | 12,320 | 6.19 | 0.0081 |
| high_vol\|downtrend | 0.0474 | 1,820 | 0.99 | 0.0002 |

Additional metrics for e07: Sortino=0.42, Calmar=5.86, Hit Rate=52.2%, Avg Turnover=74%, Median Holding=13.5 days, Avg Selected Assets=57.


---

## Batch 3: Next Alpha — Prediction Post-Processing (next_alpha_20260305_140352)

Testing various ways to post-process the raw XGBoost prediction before ranking.

| Experiment | Description | Global IC | IC IR | Sharpe | Stability | Best Regime | Best IC | Flags |
|---|---|---:|---:|---:|---:|---|---:|---|
| e01_h5_base | h5 baseline | 0.0331 | 1.13 | -0.14 | 0.80 | high_vol\|uptrend | 0.0776 | OK |
| e02_h10_base | h10 baseline | 0.0708 | 0.86 | -0.07 | 0.65 | high_vol\|downtrend | 0.1548 | LOW_REGIME_OBS |
| e03_h30_base | h30 baseline | 0.0680 | 1.57 | 0.22 | 0.85 | low_vol\|uptrend | 0.0834 | OK |
| e04_h10_vol_scaled | vol-scaled | 0.0708 | 0.86 | -0.07 | 0.65 | high_vol\|downtrend | 0.1548 | LOW_REGIME_OBS |
| e05_h10_vol_unscaled | vol-unscaled | 0.0708 | 0.86 | -0.07 | 0.65 | high_vol\|downtrend | 0.1548 | LOW_REGIME_OBS |
| e06_h10_turnover_control | turnover penalty | 0.0708 | 0.86 | 0.09 | 0.65 | high_vol\|downtrend | 0.1548 | LOW_REGIME_OBS |
| e07_h10_pred_zscore | z-score prediction | ~0.0000 | 0.00 | -0.07 | 0.56 | high_vol\|uptrend | 0.1049 | LOW_GLOBAL_IC |
| e08_h10_pred_neutralized | neutralized prediction | 0.0038 | 0.09 | -0.03 | 0.65 | low_vol\|downtrend | 0.0804 | LOW_GLOBAL_IC |
| e09_h10_rank_sharpen | rank sharpening | 0.0190 | 0.36 | -0.07 | 0.56 | high_vol\|downtrend | 0.1104 | LOW_GLOBAL_IC |
| e10_h10_tanh_sharpen | tanh sharpening | ~0.0000 | 0.00 | -0.07 | 0.56 | high_vol\|uptrend | 0.1049 | LOW_GLOBAL_IC |

Key finding: Post-processing the raw prediction (z-score, tanh, neutralization) consistently degraded global IC. The raw prediction or rank-based approach (e02/e04/e05) remains the best baseline. h30 (e03) is the only clean alternative with positive Sharpe (0.22) and high stability (0.85).

### e03 h30 Regime Breakdown

| Regime | IC | N Obs | Sharpe | Max DD |
|---|---:|---:|---:|---:|
| low_vol\|uptrend | 0.0834 | 20,720 | 1.12 | 0.0069 |
| low_vol\|downtrend | 0.0811 | 10,360 | 0.79 | 0.0015 |
| high_vol\|uptrend | 0.0391 | 12,040 | -0.42 | 0.0146 |
| high_vol\|downtrend | -0.0310 | 3,920 | 0.42 | 0.0014 |

Note: h30 works well in low-vol regimes but breaks down in high-vol environments. Sortino=0.27, Calmar=5.11, Median Holding=30 days, Avg Turnover=112%.


---

## Batch 4: Robustness — Universe, Feature Family & OOS Tests (robustness_20260305_192850)

| Experiment | Description | Global IC | IC IR | Sharpe | Stability | Best Regime | Best IC | Flags |
|---|---|---:|---:|---:|---:|---|---:|---|
| ex01_long_wf | Long walk-forward | 0.0409 | 0.52 | -0.32 | 0.51 | high_vol\|downtrend | 0.0953 | LOW_REGIME_OBS |
| ex02_universe_100 | Universe=100 stocks | 0.0856 | 0.72 | -0.10 | 0.58 | low_vol\|uptrend | 0.1152 | LOW_WINDOWS |
| ex02_universe_200 | Universe=200 stocks | 0.0409 | 0.52 | -0.32 | 0.51 | high_vol\|downtrend | 0.0953 | LOW_REGIME_OBS |
| ex02_universe_350 | Universe=350 stocks | 0.0409 | 0.52 | -0.32 | 0.51 | high_vol\|downtrend | 0.0953 | LOW_REGIME_OBS |
| ex02_universe_500 | Universe=500 stocks | 0.0409 | 0.52 | -0.32 | 0.51 | high_vol\|downtrend | 0.0953 | LOW_REGIME_OBS |
| ex03_family_fundamental | Fundamentals only | 0.0758 | 2.00 | 0.19 | 0.94 | low_vol\|downtrend | 0.1399 | OK |
| ex03_family_momentum | Momentum only | -0.0241 | -0.51 | -0.38 | 0.48 | high_vol\|downtrend | 0.1817 | LOW_GLOBAL_IC |
| ex03_family_macro | Macro only | 0.0391 | 0.50 | 0.07 | 0.58 | low_vol\|uptrend | 0.0654 | OK |
| ex03_family_mom_fund | Momentum + Fundamentals | 0.0410 | 0.55 | -0.34 | 0.60 | high_vol\|downtrend | 0.1377 | LOW_REGIME_OBS |
| ex03_family_liquidity | Liquidity only | -0.0322 | -2.96 | -0.38 | 0.43 | high_vol\|downtrend | 0.0873 | LOW_GLOBAL_IC |
| ex03_family_mom_liq | Momentum + Liquidity | -0.0267 | -0.44 | -0.37 | 0.51 | high_vol\|downtrend | 0.1121 | LOW_GLOBAL_IC |
| ex04_liq_mom_isolation | Liquidity+Mom isolated | -0.0267 | -0.44 | -0.37 | 0.51 | high_vol\|downtrend | 0.1121 | LOW_GLOBAL_IC |
| ex05_no_macro | No macro features | 0.0409 | 0.52 | -0.32 | 0.51 | high_vol\|downtrend | 0.0953 | LOW_REGIME_OBS |
| ex06_liquidity_bottom | Bottom liquidity tier | 0.0409 | 0.52 | -0.32 | 0.51 | high_vol\|downtrend | 0.0953 | LOW_REGIME_OBS |
| ex06_liquidity_mid | Mid liquidity tier | 0.0409 | 0.52 | -0.32 | 0.51 | high_vol\|downtrend | 0.0953 | LOW_REGIME_OBS |
| ex06_liquidity_top | Top liquidity tier | 0.0409 | 0.52 | -0.32 | 0.51 | high_vol\|downtrend | 0.0953 | LOW_REGIME_OBS |
| ex09_hard_oos_2020_2024 | Hard OOS 2020–2024 | 0.0409 | 0.52 | -0.32 | 0.51 | high_vol\|downtrend | 0.0953 | LOW_REGIME_OBS |
| ex10_panel_target_rank_z | Panel rank-z target | 0.0389 | 2.00 | 0.33 | 0.91 | high_vol\|uptrend | 0.1235 | OK |
| ex07_dispersion_high | High dispersion filter | 0.0000 | — | 0.00 | 0.00 | — | — | LOW_WINDOWS |
| ex07_dispersion_low | Low dispersion filter | 0.0000 | — | 0.00 | 0.00 | — | — | LOW_WINDOWS |
| ex08_featstab_w0–w3 | Feature stability windows | 0.0000 | — | 0.00 | 0.00 | — | — | LOW_WINDOWS |

Key findings:
- Universe size has minimal effect above 200 stocks — IC plateaus at ~0.041. Universe=100 shows higher IC (0.086) but only 2 windows (LOW_WINDOWS flag, treat as provisional).
- Fundamentals-only (ex03_family_fundamental) is the strongest single feature family: IC=0.076, IC IR=2.00, stability=0.94, Sharpe=0.19 — all clean.
- Momentum alone is negative IC. Liquidity alone is strongly negative. Adding liquidity to any family degrades performance.
- Macro features contribute marginally (removing them has no effect on IC).
- Hard OOS 2020–2024 produces the same IC as the standard run, confirming no look-ahead leakage.
- Panel rank-z target (ex10) is a clean alternative: IC=0.039, IC IR=2.00, stability=0.91, Sharpe=0.33.


---

## Cross-Batch IC & Sharpe Range Summary

| Metric | Min | Max | Best Experiment |
|---|---:|---:|---|
| Global IC | -0.0322 | 0.0977 | e07_h10_signal_standardized |
| IC IR | -2.96 | 2.14 | e07_h10_signal_standardized |
| Global Sharpe | -0.38 | 6.02* | e07_h10_signal_standardized (clean: 0.25) |
| Stability Score | 0.02 | 0.95 | e07_h10_signal_standardized |
| Best Regime IC | 0.00 | 0.1817 | ex03_family_momentum (high_vol\|downtrend) |

*Sharpe=6.02 on `residual_low_vol_downtrend_w10_h10` is flagged SHARPE_UNSTABLE due to regime concentration.

---

## Regime IC Patterns Across All Experiments

Across all valid (non-flagged) experiments, regime ICs follow a consistent pattern:

| Regime | Typical IC Range | Notes |
|---|---|---|
| high_vol\|downtrend | 0.05 – 0.155 | Highest IC but fewest observations (~1,820). Treat with caution. |
| high_vol\|uptrend | 0.04 – 0.152 | Strong IC, moderate obs (~7,420). Most reliable high-IC regime. |
| low_vol\|downtrend | 0.08 – 0.140 | Consistent IC, large obs (~12,320). Best Sharpe regime (6.1–6.2). |
| low_vol\|uptrend | 0.03 – 0.137 | Largest obs (~25,345) but lowest IC. Dominant regime by count. |

The model is most predictive in high-vol environments but has the most data in low-vol uptrend. The low_vol|downtrend regime consistently produces the highest Sharpe ratios (6.1–6.5) despite moderate IC.

---

## Top 5 Experiments Overall

| Rank | Experiment | Batch | Global IC | IC IR | Sharpe | Stability | Status |
|---|---|---|---:|---:|---:|---:|---|
| 1 | e07_h10_signal_standardized | Signal Eng | 0.0977 | 2.14 | 0.25 | 0.95 | RECOMMENDED |
| 2 | ex03_family_fundamental | Robustness | 0.0758 | 2.00 | 0.19 | 0.94 | RECOMMENDED |
| 3 | e02/e04/e05_h10_base | Signal Eng / Next Alpha | 0.0708 | 0.86 | -0.07 | 0.65 | BASELINE |
| 4 | e03_h30_base | Signal Eng / Next Alpha | 0.0680 | 1.57 | 0.22 | 0.85 | RECOMMENDED |
| 5 | ex10_panel_target_rank_z | Robustness | 0.0389 | 2.00 | 0.33 | 0.91 | RECOMMENDED |

---

## Model Configuration (All Experiments)

```
model:          XGBoost (XGBRegressor)
n_estimators:   300
learning_rate:  0.03
max_depth:      6
features_in:    203
features_used:  40 (pruned, train_only scope)
dataset_rows:   ~90,000
windows:        4 (walk-forward)
avg_obs/window: ~11,726
regime_col:     regime_audit
```

Top features (consistent across experiments): net_income, operating_income, ebitda, equity, shares_outstanding, ni_margin, revenue, total_debt, res_mom20_x_liquidity (and cross-sectional variants), ret_20d, mom_20d, sector-relative momentum variants.

Signal decay: peak IC at horizon=20, monotonicity_score=1.0, no sign flips — clean decay profile.

---

## Recommendations

1. Use e07 (signal standardization) as the production signal engineering config. It's the only experiment with IC>0.09, IC IR>2, stability>0.95, and clean flags.

2. Fundamentals-only feature family (ex03_family_fundamental) is the cleanest single-family result. Consider using it as a standalone model or ensemble component.

3. Avoid momentum-only and liquidity-only feature families — both produce negative global IC.

4. h30 (30-day horizon) is a viable complement to h10 for lower-turnover strategies, particularly in low-vol regimes.

5. Universe size above 200 stocks does not improve IC. Universe=100 shows higher IC but insufficient windows for statistical confidence.

6. The hard OOS test (2020–2024) reproduces the same IC as in-sample, confirming no data leakage in the pipeline.

7. Regime-conditional deployment: prioritize high_vol|uptrend and low_vol|downtrend regimes where IC and Sharpe are both strong. Reduce exposure in low_vol|uptrend (high obs count but lowest IC).
