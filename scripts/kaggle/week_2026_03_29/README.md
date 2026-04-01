# Northstar V3 Weekly Kaggle Sprint

This folder contains the Kaggle-side weekly sprint stack for the `2026-03-29` plan.

Execution order:

1. `build_weekly_feature_export.py`
2. `nb00_feature_health.py`
3. `nb01_fixed_baselines.py`
4. `nb02_failed_model_autopsy.py`
5. `nb03_regime_dictionary.py`
6. `nb04_company_attribution.py`
7. `nb05_cross_asset_tests.py`
8. `nb06_india_hypothesis_battery.py`
9. `nb07_ensemble_tra_deployment.py`
10. `run_weekly_suite.py`

Design choices:

- The weekly raw bundle is treated as the data root.
- A temporary runtime project is created so the research stack can run against Kaggle inputs without silently falling back to hidden local files.
- Screener metrics receive an explicit unit registry so percentages, crores, days, and per-share values are not mixed.
- Model exports and helper metadata are separated:
  - `northstar_features.parquet` is model-facing.
  - `northstar_metadata.parquet` stores sector/market-cap/regime annotations for diagnostics.
