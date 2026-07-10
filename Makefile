.PHONY: help doctor surface catalog data-contracts ci-guards gates invariants test ci test-collect test-fast status dashboard preopen morning eod

help:
	@python3 scripts/ns.py surface

doctor:
	@python3 scripts/ns.py doctor

surface:
	@python3 scripts/ns.py surface

catalog:
	@python3 scripts/ns.py catalog --refresh

data-contracts:
	@python3 scripts/ci/check_canonical_artifact_contracts.py

ci-guards:
	@python3 scripts/ci/check_active_import_prefixes.py
	@python3 scripts/ci/check_active_duplicate_truth_sources.py
	@python3 scripts/ci/check_active_synthetic_leakage.py
	@python3 scripts/ci/check_archive_import_isolation.py
	@python3 scripts/ci/check_no_tracked_deadweight.py
	@python3 scripts/ci/check_canonical_artifact_contracts.py
	@python3 scripts/ci/check_system_status_green.py

# gates: the full set of static (no-runtime-state) CI gates. Every gate here
# runs clean on a fresh checkout with no live data/DB, so it is safe to run
# in automated CI. Any non-zero exit fails the target (and the CI job).
gates:
	@set -e; \
	for g in \
	  check_active_python_parse \
	  check_active_import_prefixes \
	  check_active_duplicate_truth_sources \
	  check_active_synthetic_leakage \
	  check_archive_import_isolation \
	  check_execution_bypass \
	  check_no_tracked_deadweight \
	  check_no_local_paths \
	  check_no_secrets \
	  check_no_direct_runtime_mutation_imports \
	  check_no_lazy_imports_risk_path \
	  check_reachability_regression \
	  check_risk_drift_literals \
	  check_risk_clock_injection \
	  check_risk_float_boundaries \
	  check_policy_immutability \
	  check_canonical_artifact_contracts \
	  check_price_continuity \
	; do \
	  echo "== gate: $$g =="; \
	  python3 scripts/ci/$$g.py >/dev/null || { echo "GATE FAILED: $$g"; exit 1; }; \
	done; \
	echo "All static CI gates passed."

# invariants: truth checks over LIVE artifacts (data-dependent, unlike `gates`).
# Fails when a live artifact violates a pipeline-truth invariant: unit mixing,
# degenerate per-stock output, a dead feed, a silently-failing scheduler source,
# or a book that is not the book we intend to hold. Run nightly / post-refresh.
# On a bare checkout with no data every invariant SKIPs, so this stays green.
invariants:
	@python3 scripts/ci/check_live_artifact_invariants.py

test:
	@python3 -m pytest tests src -q

# ci: the single entry point automated CI runs -- static gates then the test
# suite. Mirrors .github/workflows/ci.yml so `make ci` locally == CI.
ci: gates test

test-collect:
	@python3 -m pytest --collect-only -q

test-fast:
	@python3 -m pytest src/nlp/tests src/options/strategy_library/tests src/pnl/tests src/core/tests -q

status:
	@python3 scripts/system_status_report.py

preopen:
	@python3 scripts/preopen_checks.py

morning:
	@python3 scripts/run_morning_pipeline.py

eod:
	@python3 scripts/eod_rebalance_with_pnl.py

dashboard:
	@bash scripts/launch_dashboard.sh
