# Public Demo

This path is designed for reviewers who do not have private broker credentials, local market-data dumps, or operator cron jobs.

## What To Show

1. The project overview in [README.md](../README.md).
2. The command surface with `make help`.
3. The public figures in [docs/figures/](figures/):
   - `northstar_vs_nifty_12m.png`
   - `drawdown_comparison.png`
   - `rolling_alpha.png`
   - `risk/sector_risk_heatmap.png`
   - `risk/exposure_timeline.png`
4. The architecture overview in [docs/system/NORTHSTAR_V3_SYSTEM_AND_RESEARCH_OVERVIEW_2026-03-22.md](system/NORTHSTAR_V3_SYSTEM_AND_RESEARCH_OVERVIEW_2026-03-22.md).
5. The Kaggle research flow in [docs/research/KAGGLE_EXPERIMENT_ARCHITECTURE.md](research/KAGGLE_EXPERIMENT_ARCHITECTURE.md).

## Credential-Free Smoke Checks

```bash
python scripts/ci/check_no_secrets.py
python -m py_compile run.py scripts/ci/check_no_secrets.py scripts/fetch_live_options_for_dashboard.py scripts/fetch_portfolio_options_for_hedging.py
python -m pytest -q tests/options/test_dashboard_state_contract.py src/core/tests/test_state_authority.py
```

## Live Demo Notes

Live broker and dashboard flows may require local files that are intentionally ignored:

- `.env.options`
- `data/`
- `logs/`
- `reports/`
- `snapshots/`

Use `.env.options.template` as the credential template. Never use real credentials in screenshots, docs, issues, pull requests, or demo recordings.
