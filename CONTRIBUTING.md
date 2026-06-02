# Contributing

Thanks for taking a look at Northstar V3. This is an operational quant workspace, so contributions should optimize for reproducibility, safety, and clear review.

## Before You Start

- Read [README.md](README.md) and [ROOT_FOLDER_README.md](ROOT_FOLDER_README.md).
- Run `python scripts/ci/check_no_secrets.py` before opening a PR.
- Do not commit `.env`, `.env.*`, `.env.options`, private keys, logs, generated data, broker exports, or account-level reports.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Validation

Use focused checks for small changes:

```bash
python -m py_compile path/to/changed_file.py
python -m pytest -q path/to/test_file.py
```

Use public-readiness checks before submitting:

```bash
python scripts/ci/check_no_secrets.py
python -m pytest -q tests/options/test_dashboard_state_contract.py src/core/tests/test_state_authority.py
```

## Pull Request Expectations

- Explain the user-facing or operator-facing behavior change.
- List the commands you ran.
- Mention data, credential, or migration implications.
- Keep generated artifacts out unless the PR is specifically about public docs or figures.

## Coding Guidelines

- Prefer existing modules and patterns over new abstractions.
- Keep live trading, risk, execution, and credential-loading paths conservative.
- Avoid hidden synthetic fallback data in production paths.
- Keep archived docs archival; update canonical docs when changing current behavior.
