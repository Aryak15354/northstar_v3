# Northstar V3

Northstar V3 is an operational quantitative research and trading workspace for Indian equities and options. It combines research pipelines, market and sentiment ingestion, portfolio/risk governance, options runtime tooling, dashboard artifacts, and reproducibility checks around one canonical Python workspace.

This repository is public for review, learning, and collaboration, but it is still an operator-grade workspace rather than a packaged trading product. Live broker access, private data, generated reports, and local credentials are intentionally excluded.

## What It Does

- Runs a daily market workflow for readiness checks, market-state refresh, runtime sync, and end-of-day processing.
- Maintains research and validation paths for factors, regimes, valuation, sentiment, and Kaggle-style experiment runs.
- Provides options tooling around Upstox/Groww integrations, with credentials loaded from local environment files only.
- Produces dashboard-ready artifacts for monitoring system state, risk posture, and strategy diagnostics.
- Includes CI gates for static integrity, runtime smoke checks, risk-policy guardrails, archive isolation, and secret scanning.

## Repository Map

- `src/`: core runtime, research, risk, portfolio, dashboard, ingestion, and options modules
- `scripts/`: operational entrypoints, CI checks, data refreshers, validators, and research runners
- `config/`: runtime, market, policy, strategy, dashboard, and research configuration
- `tests/`: unit, integration, and regression coverage
- `docs/operations/`: operator runbooks and workspace guidance
- `docs/research/`: Kaggle and experiment architecture notes
- `docs/figures/`: public screenshots and result figures suitable for demos
- `data_dictionary/`: schema notes for macro, equity, and sector data

Generated data, logs, snapshots, reports, virtual environments, and private credentials are ignored by default.

## Quick Start

Use Python 3.11 where possible.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Run the lightweight checks:

```bash
python scripts/ci/check_no_secrets.py
python -m py_compile run.py scripts/ci/check_no_secrets.py scripts/fetch_live_options_for_dashboard.py scripts/fetch_portfolio_options_for_hedging.py
python -m pytest -q tests/options/test_dashboard_state_contract.py src/core/tests/test_state_authority.py
```

Explore the command surface:

```bash
make help
make surface
python run.py --mode health --verbose
```

## Credentials

Do not commit credentials. Copy the template only on your local machine:

```bash
cp .env.options.template .env.options
```

Then set values such as `UPSTOX_API_KEY`, `UPSTOX_API_SECRET`, `UPSTOX_ACCESS_TOKEN`, and optional Groww variables. If any credential has ever appeared in this repo or its public history, rotate it at the provider before using the repository again.

## Demo Path

For a public walkthrough without broker credentials or private market data:

1. Read [docs/PUBLIC_DEMO.md](docs/PUBLIC_DEMO.md).
2. Open the figures in [docs/figures/](docs/figures/) for example outputs.
3. Run the smoke checks above to show the repository is installable and guarded.
4. Review [docs/system/NORTHSTAR_V3_SYSTEM_AND_RESEARCH_OVERVIEW_2026-03-22.md](docs/system/NORTHSTAR_V3_SYSTEM_AND_RESEARCH_OVERVIEW_2026-03-22.md) for the broader architecture narrative.

## Architecture

Northstar is organized around a few practical surfaces:

- **Operation layer:** `run.py`, trading-day orchestration scripts, pre-open checks, EOD refreshers, and runtime state sync.
- **Research layer:** feature factories, regime assignment, experiment configs, Kaggle runners, and validation reports.
- **Risk and portfolio layer:** policy checks, governor state, capital controls, execution guards, and deterministic replay checks.
- **Data layer:** market, macro, alternative data, sentiment, and canonical reference inputs.
- **Dashboard layer:** Streamlit-facing models, chart registry, tabs, and generated dashboard state artifacts.

The detailed operator view lives in [ROOT_FOLDER_README.md](ROOT_FOLDER_README.md), and the deeper documentation index starts at [docs/README.md](docs/README.md).

## Contributing

Start with [CONTRIBUTING.md](CONTRIBUTING.md). In short:

- Keep changes scoped and testable.
- Avoid committing generated artifacts, private data, or credential files.
- Add or update tests for behavioral changes.
- Prefer canonical entrypoints under `run.py` and `scripts/` over older root-level launchers.

## Security

See [SECURITY.md](SECURITY.md). Please do not open public issues for secrets, account details, broker credentials, or exploitable vulnerabilities.

## License

This project is source-available, not open source. See [LICENSE](LICENSE) for the current proprietary evaluation terms.
