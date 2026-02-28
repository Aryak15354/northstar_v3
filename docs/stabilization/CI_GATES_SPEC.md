# Northstar V4 CI Gates Specification

## Scope
This document defines mandatory blocking gates for stabilization and post-cutover governance.

## Global CI Environment
- `NORTHSTAR_STRICT_MODE=1`
- `NORTHSTAR_CI_GATE=1`
- `RISK_RANDOM_SEED=42`
- `PYTHONHASHSEED=42`
- `TZ=UTC`
- `LC_ALL=C.UTF-8`
- `LANG=C.UTF-8`

## Gate 1: Static Integrity
- Parse active Python files (non-archived production tree).
- Block zero-byte modules.
- Block lazy imports in risk/execution path.
- Block direct wall-clock calls in risk/execution path.
- Enforce risk policy immutability contract.
- Enforce execution anti-bypass contract.
- Enforce dashboard chart-registry contracts (required live chart IDs wired, all Plotly charts explicitly keyed).

## Gate 2: Risk Safety
- Enforce epsilon-based boundary checks in risk/execution path.
- Verify deterministic replay (same decision under fixed seed and fixed clock).
- Run options risk-targeted tests (`tests/options`).

## Gate 3: Runtime Integrity
- Run strict three-command runtime gate:
  1. `python run.py --mode health --verbose`
  2. `python run.py --mode update --quick --verbose`
  3. `python run.py --mode dashboard --dashboard brain --verbose`
- Block on non-zero exit.
- Block on strict log patterns (`fallback`, `ignored`, `failed but continuing`, `continue on error`, `skipping`, `skipped`, `defaulting`, `recovered`, `retrying`).

## Gate 4: Drift Detection
- Re-run policy immutability and anti-bypass checks.
- Treat any violation as merge-blocking.

## Gate 5: Risk Drift Detector
- Scan `.py/.yaml/.yml/.json/.toml` for hardcoded risk literals and derived risk-cap formulas.
- Allowlist only canonical policy/config definitions.

## Gate 6: Reachability Regression
- Recompute reachable graph from canonical entrypoints.
- Compare with `audit/reachability_baseline.json`.
- Block on newly introduced unreachable production files.

## Additional Blocking Guard: Archive Isolation
- Ensure archive paths are not importable at runtime.
- Block any static imports from archive namespace.

## CI Summary Job
- Collect all gate outcomes.
- Fail if any gate is `failure`, `cancelled`, or `skipped`.
- Publish machine-readable gate artifact.

## Merge Policy
- All gates are required status checks.
- No temporary bypass, no soft warning mode in CI.
