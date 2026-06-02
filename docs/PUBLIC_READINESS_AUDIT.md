# Public Readiness Audit

Date: 2026-05-18

## Fixed In This Pass

- Removed tracked `.env.options` backup files from the repository surface.
- Replaced hardcoded Upstox credentials in archived docs with placeholders.
- Removed hardcoded Upstox JWTs from option-fetch scripts and switched them to environment or `.env.options` loading.
- Added `.gitignore` coverage for `.env.*`, `.env.options.*`, private keys, broker secret files, Kaggle credentials, and common certificate bundles.
- Added `scripts/ci/check_no_secrets.py` and wired it into GitHub Actions.
- Reworked the README for public onboarding: pitch, setup, repo map, credential handling, architecture, demo path, contribution path, and license note.
- Added public-facing `CONTRIBUTING.md`, `SECURITY.md`, issue templates, a PR template, and [PUBLIC_DEMO.md](PUBLIC_DEMO.md).
- Fixed dependency metadata by adding the `aiohttp` range required by `growwapi`.
- Removed several active hardcoded local paths from cron, logging, Kaggle automation, and research utility scripts.

## Validation Run

```bash
python3 scripts/ci/check_no_secrets.py
python3 -m pip check
python3 -m py_compile run.py scripts/ci/check_no_secrets.py scripts/fetch_live_options_for_dashboard.py scripts/fetch_portfolio_options_for_hedging.py
python3 -m pytest -q tests/options/test_dashboard_state_contract.py src/core/tests/test_state_authority.py
python3 run.py --mode health --verbose
```

Results:

- tracked-file secret scan passed
- dependency check passed
- compile checks passed
- focused tests passed: 11 passed, 1 warning
- health command passed

## Remaining Public Risks

- Real Upstox credentials still exist in ignored local files: `.env.options` and `.env.options.bak_20260327_083042`.
- A private key still exists locally at `universe/northstar-key.pem`; it is ignored, but should be treated as sensitive.
- `_cold_archive/` contains historical secret copies locally; it is ignored, but should not be manually uploaded.
- Because real credentials were present in tracked files before this pass, provider-side rotation is required. Removing files now does not clean public git history.
- Some archived docs and generated reports still contain machine-specific paths. Current operational scripts were cleaned where obvious, but historical archives were not fully rewritten.

## Recommended Follow-Up

Run a full history scan and purge if you need the public repo to be clean retroactively:

```bash
gitleaks detect --source . --no-git=false
```

Rotate all exposed broker/API credentials before trusting live operation again.
