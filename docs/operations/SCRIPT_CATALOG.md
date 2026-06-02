# Script Catalog
Generated: 2026-03-20 05:01:00

This catalog exists so you do not have to scan the raw `scripts/` tree.

## Canonical Entry Points

- `scripts/run_complete_v3_system.py`: Complete daily Gap 1-7 runner
- `scripts/northstar_v3_unified.py`: Unified launcher
- `scripts/preopen_checks.py`: Pre-market readiness checks
- `scripts/run_morning_pipeline.py`: Morning pipeline
- `scripts/eod_rebalance_with_pnl.py`: EOD processing with unified P&L
- `scripts/promote_research_model.py`: Governed model promotion
- `scripts/launch_dashboard.sh`: Dashboard launcher
- `scripts/verify_gap1_fixes.py`: Gap 1 validator
- `scripts/validate_gap2_complete.py`: Gap 2 validator
- `scripts/validate_gap3_robust_complete.py`: Gap 3 validator
- `scripts/test_gap4_robust.py`: Gap 4 validator
- `scripts/validate_gap5_complete.py`: Gap 5 validator
- `scripts/validate_gap6_complete.py`: Gap 6 validator
- `scripts/validate_gap7_complete.py`: Gap 7 validator

## Shape Of The Tree

- Root Python scripts: 415
- Root shell scripts: 32
- Total Python scripts under `scripts/`: 486

## Note On Script Count

The script surface is large and includes both active operational entrypoints and
historical repair, validation, and migration utilities.

Treat the Makefile targets and the canonical entrypoint docs as the operational
surface. Scripts prefixed with `fix_`, `demo_`, `complete_`, `validate_gap`,
and `test_gap` are usually historical gap-filling or validation helpers, not
day-to-day operator entrypoints.

### Python scripts by bucket

- `(root)`: 415
- `runners`: 19
- `ci`: 14
- `cleanup`: 11
- `launchers`: 8
- `analysis`: 4
- `debug`: 4
- `tests`: 3
- `utilities`: 3
- `utils`: 1

## Root Script Breakdown

- **Audits**: 3
  Example: `audit_gaps_1_to_5.py, audit_real_data.py, audit_underlying_attribution.py`
- **Backfills**: 4
  Example: `backfill_60days_nse.py, backfill_historical_sentiment.py, backfill_sentiment_noninteractive.py, backfill_upstox_weekly_history.py`
- **Builders**: 17
  Example: `build_anticipatory_intelligence.py, build_beta_drift_fabric.py, build_bse_nse_mapping.py, build_cohesive_alpha_feed.py, build_crisis_replay_dataset.py, build_et500_reference_data.py, build_gap3_alternative_data_layer.py, build_groww_option_universe.py, build_groww_option_universe_multi_horizon.py, build_horizon_ensemble_metrics.py, +7 more`
- **Checks**: 4
  Example: `check_actual_expiries.py, check_live_status.py, check_v3_system_status.py, check_venue_status.py`
- **Completion scripts**: 6
  Example: `complete_all_remaining_gaps.py, complete_gap8_dashboard.py, complete_system_integrity_repair.py, complete_temporal_protection_implementation.py, complete_tensorflow_m1_fix.py, complete_v3_system_and_dashboard_enhancement.py`
- **Creators**: 7
  Example: `create_clean_dated_dataset.py, create_comprehensive_sample_data.py, create_dashboard_data_from_backtests.py, create_dated_news_dataset.py, create_interactive_dashboard_complete.py, create_nse_bulk_deals.py, create_sample_dashboard_data.py`
- **Debugging**: 4
  Example: `debug_crisis_activation.py, debug_ingestion.py, debug_nse_page.py, debug_upstox_api.py`
- **Demos**: 15
  Example: `demo_command_bridge.py, demo_comprehensive_operation.py, demo_constitutional_cockpit.py, demo_cross_timeline_consistency_checker.py, demo_data_format_standardization.py, demo_enhanced_institutional_reports.py, demo_enhanced_narratives.py, demo_enhanced_stress_tests.py, demo_historical_period_validator.py, demo_institutional_safeguards.py, +5 more`
- **Downloaders**: 4
  Example: `download_harixn_indian_news.py, download_indian_financial_news.py, download_pranali_indian_news.py, download_upstox_instruments.py`
- **Execution runners**: 39
  Example: `run_5min_sentiment_updates.py, run_alpha_attribution.py, run_alpha_diagnostics.py, run_alpha_validation.py, run_baseline_validation.py, run_capacity_walk_forward.py, run_chaos_dry_run.py, run_complete_northstar_system.py, run_complete_v3_system.py, run_comprehensive_system_validation.py, +29 more`
- **Fetchers**: 5
  Example: `fetch_60day_news.py, fetch_india_vix.py, fetch_live_options_for_dashboard.py, fetch_portfolio_options_for_hedging.py, fetch_real_dates_from_urls.py`
- **Fix-up scripts**: 8
  Example: `fix_credit_ratings_tickers.py, fix_gap1_critical_issues.py, fix_gap2_complete.py, fix_gap4_robust.py, fix_gap6_integration.py, fix_gap7_integration.py, fix_ledger_null_dates.py, fix_sector_mapping_for_real_data.py`
- **Generators**: 11
  Example: `generate_12month_performance_report.py, generate_6month_comprehensive_trading_report.py, generate_dashboard_production_data.py, generate_eod_reports.py, generate_institutional_report_complete.py, generate_institutional_walkforward_report.py, generate_periodic_reports.py, generate_portfolio.py, generate_regime_ic_experiment_report.py, generate_system_integrity_diagnostic_report.py, +1 more`
- **Implementation scripts**: 7
  Example: `implement_dashboard_charts.py, implement_gap3_complete.py, implement_gap3_robust_connections.py, implement_gap5_robust.py, implement_layer4_regime_specialists.py, implement_layer5_bayesian_tribunal.py, implement_point_in_time_protection.py`
- **Integration scripts**: 6
  Example: `integrate_alpha_generation_v3.py, integrate_health_calculator.py, integrate_historical_data.py, integrate_official_nse_delisting_data.py, integrate_production_grade_with_live_system.py, integrate_regime_data.py`
- **Launchers**: 6
  Example: `launch_command_bridge.py, launch_comprehensive_shadow_trading.py, launch_integrated_live_system.py, launch_live_operation.py, launch_northstar_v3_ultimate_integrated_dashboard_fixed.py, launch_shadow_trading.py`
- **Monitors**: 3
  Example: `monitor_automation.py, monitor_gap5_reconciliation.py, monitor_options.py`
- **Other root scripts**: 141
  Example: `activate_full_northstar_v3_system.py, activate_system.py, add_credit_spreads.py, analyze_historical_volatility.py, automation_dashboard.py, backup_northstar_data.py, batch_syntax_fix.py, black_swan_snapshot.py, bootstrap_alpha_os_registry.py, clean_legacy_news.py, +131 more`
- **Scrapers**: 18
  Example: `scrape_bse_announcements.py, scrape_bse_bulk_deals.py, scrape_bse_earnings_dates.py, scrape_bse_promoter_pledge.py, scrape_cea_power.py, scrape_cea_power_data.py, scrape_credit_ratings.py, scrape_gst_ewaybill.py, scrape_nse_bulk_deals.py, scrape_nse_bulk_deals_direct.py, +8 more`
- **Tests**: 61
  Example: `test_alternative_data_update.py, test_alternative_feature_block.py, test_alternative_pipeline_runner.py, test_and_fix_all_charts.py, test_anticipatory_integration.py, test_brain_window_integration.py, test_capital_grade_system_laws.py, test_complete_living_system_integration.py, test_constitutional_cockpit.py, test_core_system_integration.py, +51 more`
- **Validators**: 18
  Example: `validate_alternative_data_availability.py, validate_complete_system.py, validate_config.py, validate_gap2_complete.py, validate_gap3_robust_complete.py, validate_gap4_complete.py, validate_gap5_complete.py, validate_gap5_robust.py, validate_gap6_complete.py, validate_gap7_complete.py, +8 more`
- **Verification scripts**: 5
  Example: `verify_complete_system_operation.py, verify_gap1_fixes.py, verify_live_system.py, verify_system_core_functionality.py, verify_system_operations.py`

## Working Rule

- Prefer the canonical entrypoints above.
- Use subdirectories for one-off debugging, cleanup, and analysis scripts.
- Avoid adding new temporary scripts to the root `scripts/` directory.
