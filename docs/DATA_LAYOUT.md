# Data Layout

Canonical storage now lives under:

- `data/raw/exchanges/{nse,bse}/...` for exchange-specific raw datasets
- `data/raw/shared/...` for exchange-agnostic raw datasets
- `data/raw/vendors/...` for vendor datasets such as Screener
- `data/runtime/automation/...`, `data/runtime/quarantine/...`, and `data/runtime/runs/...` for operational state, automation logs, and transient runtime scaffolding
- `data/testing/...` for test-only scratch outputs
- `data/archive/...` for legacy backups, demo artifacts, and historical side datasets that should not bloat the active top-level tree
- `data/results/research/cycles/YYYY/MM/...` for research cycle outputs
- `data/results/research/snapshots/YYYY/MM/...` for research dataset snapshots
- `data/results/research/state/...` for singleton research state and bridge artifacts
- `data/results/research/trackers/...` for append-only trackers and meta-memory stores
- `data/results/research/reports/nightly/...` for nightly research reports
- `data/results/analysis/...` for analysis outputs, including clustering artifacts

Running `python3 scripts/normalize_repo_layout.py` migrates legacy folders into these canonical roots and collapses old top-level clutter into `data/runtime`, `data/testing`, `data/results`, and `data/archive`.
