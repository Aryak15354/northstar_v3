# Contributing

This repository prioritizes reproducible research and production-safe execution.

## Naming Conventions

- Python files: `snake_case.py`
- Python packages/directories: `snake_case/`
- Config files: `kebab-case.yaml`, `kebab-case.json`
- Tests: `test_*.py`
- Completion reports: `YYYY-MM-DD_<topic>.md`

## Directory Conventions

- `src/`: runtime modules
- `scripts/`: operational scripts and utilities
- `tests/`: unit/integration/property tests
- `docs/`: operator and architecture documentation

## Quality Gates

- Add or update tests for behavioral changes.
- Keep interfaces backward compatible for existing runners.
- Do not silently introduce synthetic fallback data in production paths.

