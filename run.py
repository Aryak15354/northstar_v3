#!/usr/bin/env python3
"""Northstar V3 canonical runtime entrypoint.

Contracted modes:
- dashboard
- update
- health
- status
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


PROJECT_ROOT = Path(__file__).resolve().parent
DASHBOARD_FILE = PROJECT_ROOT / "src/dashboard/northstar_v3_ultimate_integrated_dashboard.py"
RUN_COMPLETE = PROJECT_ROOT / "scripts/run_complete_v3_system.py"
FREEZE_STATE_FILE = PROJECT_ROOT / "data/processed/model_freeze_state.json"
MASTER_LEDGER_FILE = PROJECT_ROOT / "data/pnl/master_ledger.parquet"
WORKSPACE_GUIDE_FILE = PROJECT_ROOT / "docs/operations/WORKSPACE_GUIDE.md"
TEST_COUNT_BASELINE_FILE = PROJECT_ROOT / "data/processed/test_count_baseline.json"
CI_BOOTSTRAP_MANIFEST_FILE = PROJECT_ROOT / "data/options/live/runtime_gate_ci_bootstrap.json"
MARKET_DATA_CANDIDATES = [
    PROJECT_ROOT / "data/processed/market_state.parquet",
    PROJECT_ROOT / "data/options/live/market_data_latest.json",
    PROJECT_ROOT / "data/processed/prices.parquet",
]
HEALTH_HARD_BLOCKERS = {"broker_connectivity", "market_data_freshness", "ledger_integrity"}
HEALTH_SOFT_WARNINGS = {"code_freeze", "doc_staleness", "test_count_drift"}


def _env_flag(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _strict_mode() -> bool:
    return _env_flag("NORTHSTAR_STRICT_MODE", default=False)


def _ci_gate_mode() -> bool:
    return _env_flag("NORTHSTAR_CI_GATE", default=False)


def _load_freeze_state() -> Dict[str, object]:
    if not FREEZE_STATE_FILE.exists():
        return {"freeze_active": False, "triggers": []}
    try:
        payload = json.loads(FREEZE_STATE_FILE.read_text(encoding="utf-8"))
        return {
            "freeze_active": bool(payload.get("freeze_active", False)),
            "triggers": payload.get("triggers", []) or [],
        }
    except Exception:
        if _strict_mode():
            raise
        return {"freeze_active": False, "triggers": []}


def _load_json_file(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _load_ci_bootstrap_manifest() -> Dict[str, object]:
    return _load_json_file(CI_BOOTSTRAP_MANIFEST_FILE)


def _ensure_archive_isolation() -> Tuple[bool, str]:
    archive_hits = [p for p in sys.path if "archive" in str(p).replace("\\", "/").lower()]
    if archive_hits:
        return False, f"archive path detected in sys.path: {archive_hits[:3]}"

    loaded_archive_modules = []
    for _, module in list(sys.modules.items()):
        module_file = getattr(module, "__file__", None)
        if not module_file:
            continue
        if "/archive/" in str(module_file).replace("\\", "/").lower():
            loaded_archive_modules.append(str(module_file))
    if loaded_archive_modules:
        return False, f"archived module imported: {loaded_archive_modules[:3]}"

    return True, ""


def _print_banner(args: argparse.Namespace, freeze_state: Dict[str, object]) -> None:
    print("NORTHSTAR V3 ENTRYPOINT")
    print("=" * 48)
    print(f"Mode: {args.mode}")
    if args.mode == "dashboard":
        print(f"Dashboard: {args.dashboard}")
    print(f"Strict mode: {'ON' if _strict_mode() else 'OFF'}")
    print(f"CI gate mode: {'ON' if _ci_gate_mode() else 'OFF'}")
    print(f"Started (UTC): {datetime.now(timezone.utc).isoformat()}")
    print(
        f"Trading freeze: {'ACTIVE' if freeze_state.get('freeze_active') else 'INACTIVE'}"
    )
    if freeze_state.get("freeze_active"):
        triggers = freeze_state.get("triggers") or []
        if triggers:
            print(f"Freeze triggers: {', '.join(str(x) for x in triggers)}")
    print()


def _run_subprocess(cmd: list[str], *, verbose: bool = False, cwd: Path | None = None) -> bool:
    if verbose:
        print("Command:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(cwd or PROJECT_ROOT))
    return result.returncode == 0


def _health_check_result(
    check: str,
    status: str,
    severity: str,
    message: str,
    **details: Any,
) -> Dict[str, Any]:
    return {
        "check": check,
        "status": status,
        "severity": severity,
        "message": message,
        "details": details,
    }


def _check_broker_connectivity() -> Dict[str, Any]:
    token = os.getenv("UPSTOX_ACCESS_TOKEN", "").strip()
    if not token:
        env_file = PROJECT_ROOT / ".env.options"
        if env_file.exists():
            try:
                for raw_line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    if key.strip() == "UPSTOX_ACCESS_TOKEN" and value.strip():
                        token = value.strip()
                        break
            except Exception:
                token = ""
    if not token:
        if _ci_gate_mode():
            manifest = _load_ci_bootstrap_manifest()
            if manifest:
                return _health_check_result(
                    "broker_connectivity",
                    "pass",
                    "critical",
                    "CI gate mode skips live broker secret validation when bootstrap fixtures are present.",
                    bootstrap_manifest=str(CI_BOOTSTRAP_MANIFEST_FILE),
                )
        return _health_check_result(
            "broker_connectivity",
            "fail",
            "critical",
            "Broker connectivity unavailable: Upstox access token missing.",
        )
    return _health_check_result(
        "broker_connectivity",
        "pass",
        "critical",
        "Broker token resolved for live connectivity checks.",
    )


def _check_market_data_freshness() -> Dict[str, Any]:
    existing = [path for path in MARKET_DATA_CANDIDATES if path.exists()]
    if not existing:
        return _health_check_result(
            "market_data_freshness",
            "fail",
            "critical",
            "No canonical market data artifacts found.",
            checked_paths=[str(path) for path in MARKET_DATA_CANDIDATES],
        )

    freshest_path = max(existing, key=lambda path: path.stat().st_mtime)
    age_hours = max((datetime.now(timezone.utc).timestamp() - freshest_path.stat().st_mtime) / 3600.0, 0.0)
    if age_hours > 4.0:
        return _health_check_result(
            "market_data_freshness",
            "fail",
            "critical",
            f"Market data is {age_hours:.1f} hours old.",
            freshest_artifact=str(freshest_path),
            age_hours=round(age_hours, 3),
        )
    return _health_check_result(
        "market_data_freshness",
        "pass",
        "critical",
        "Canonical market data artifacts are fresh enough for live decisions.",
        freshest_artifact=str(freshest_path),
        age_hours=round(age_hours, 3),
    )


def _check_ledger_integrity() -> Dict[str, Any]:
    if not MASTER_LEDGER_FILE.exists():
        return _health_check_result(
            "ledger_integrity",
            "fail",
            "critical",
            f"Master ledger missing: {MASTER_LEDGER_FILE}",
        )
    try:
        import pandas as pd

        ledger = pd.read_parquet(MASTER_LEDGER_FILE)
    except Exception as exc:
        return _health_check_result(
            "ledger_integrity",
            "fail",
            "critical",
            f"Master ledger unreadable: {exc}",
        )

    if ledger.empty or "entry_type" not in ledger.columns:
        return _health_check_result(
            "ledger_integrity",
            "fail",
            "critical",
            "Master ledger missing entry_type rows.",
        )

    seed_rows = ledger["entry_type"].astype(str).isin(["CASH_IN", "CASH_DEPOSIT"])
    if not bool(seed_rows.any()):
        return _health_check_result(
            "ledger_integrity",
            "fail",
            "critical",
            "Master ledger is missing initial capital seed entries.",
        )

    return _health_check_result(
        "ledger_integrity",
        "pass",
        "critical",
        "Master ledger is present and contains capital seed entries.",
        seed_entry_count=int(seed_rows.sum()),
    )


def _check_code_freeze_status() -> Dict[str, Any]:
    baseline = PROJECT_ROOT / "data/options/live/gate_code_freeze_baseline.json"
    if not baseline.exists():
        return _health_check_result(
            "code_freeze",
            "warn",
            "warning",
            "Code freeze baseline missing.",
            baseline_path=str(baseline),
        )
    return _health_check_result(
        "code_freeze",
        "pass",
        "warning",
        "Code freeze baseline present.",
        baseline_path=str(baseline),
    )


def _check_doc_staleness() -> Dict[str, Any]:
    if not WORKSPACE_GUIDE_FILE.exists():
        return _health_check_result(
            "doc_staleness",
            "warn",
            "warning",
            "Workspace guide missing.",
            path=str(WORKSPACE_GUIDE_FILE),
        )
    age_days = max(
        (datetime.now(timezone.utc).timestamp() - WORKSPACE_GUIDE_FILE.stat().st_mtime) / 86400.0,
        0.0,
    )
    if age_days > 90.0:
        return _health_check_result(
            "doc_staleness",
            "warn",
            "warning",
            f"Workspace guide is {age_days:.0f} days old.",
            path=str(WORKSPACE_GUIDE_FILE),
            age_days=round(age_days, 1),
        )
    return _health_check_result(
        "doc_staleness",
        "pass",
        "warning",
        "Workspace guide is reasonably current.",
        path=str(WORKSPACE_GUIDE_FILE),
        age_days=round(age_days, 1),
    )


def _check_test_count_drift() -> Dict[str, Any]:
    if not TEST_COUNT_BASELINE_FILE.exists():
        return _health_check_result(
            "test_count_drift",
            "warn",
            "warning",
            "Test count baseline missing.",
            baseline_path=str(TEST_COUNT_BASELINE_FILE),
        )
    try:
        payload = json.loads(TEST_COUNT_BASELINE_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        return _health_check_result(
            "test_count_drift",
            "warn",
            "warning",
            f"Test count baseline unreadable: {exc}",
            baseline_path=str(TEST_COUNT_BASELINE_FILE),
        )
    baseline_count = int(payload.get("collected_tests", 0) or 0)
    if baseline_count <= 0:
        return _health_check_result(
            "test_count_drift",
            "warn",
            "warning",
            "Test count baseline invalid.",
            baseline_path=str(TEST_COUNT_BASELINE_FILE),
        )
    return _health_check_result(
        "test_count_drift",
        "pass",
        "warning",
        "Test count baseline available.",
        baseline_path=str(TEST_COUNT_BASELINE_FILE),
        baseline_count=baseline_count,
    )


def _collect_health_checks(verbose: bool = False) -> List[Dict[str, Any]]:
    if verbose:
        print("Collecting health checks...")
    return [
        _check_broker_connectivity(),
        _check_market_data_freshness(),
        _check_ledger_integrity(),
        _check_code_freeze_status(),
        _check_doc_staleness(),
        _check_test_count_drift(),
    ]


def _summarize_health_checks(checks: List[Dict[str, Any]]) -> Dict[str, Any]:
    hard_failures = [
        item["check"]
        for item in checks
        if item.get("check") in HEALTH_HARD_BLOCKERS and item.get("status") == "fail"
    ]
    soft_warnings = [
        item["check"]
        for item in checks
        if item.get("check") in HEALTH_SOFT_WARNINGS and item.get("status") in {"warn", "fail"}
    ]
    overall_status = "fail" if hard_failures else ("warn" if soft_warnings else "pass")
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall_status,
        "hard_blockers": sorted(HEALTH_HARD_BLOCKERS),
        "soft_warnings": sorted(HEALTH_SOFT_WARNINGS),
        "checks": checks,
        "hard_failures": hard_failures,
        "warning_checks": soft_warnings,
        "exit_code": 1 if hard_failures else 0,
    }


def run_dashboard_mode(dashboard_type: str, verbose: bool = False) -> bool:
    _ = dashboard_type  # current contract maps to single canonical dashboard implementation

    if not DASHBOARD_FILE.exists():
        print(f"ERROR: Missing dashboard file: {DASHBOARD_FILE}")
        return False

    if _ci_gate_mode():
        # CI checks integrity without starting long-lived UI server.
        return _run_subprocess(
            [sys.executable, "-m", "py_compile", str(DASHBOARD_FILE)],
            verbose=verbose,
        )

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(DASHBOARD_FILE),
        "--server.address",
        "127.0.0.1",
        "--server.port",
        str(8517),
        "--server.headless",
        "true" if _strict_mode() else "false",
    ]
    return _run_subprocess(cmd, verbose=verbose)


def run_update_mode(quick: bool = False, verbose: bool = False) -> bool:
    if not RUN_COMPLETE.exists():
        print(f"ERROR: Missing update runner: {RUN_COMPLETE}")
        return False

    freeze_state = _load_freeze_state()
    cmd = [sys.executable, str(RUN_COMPLETE)]
    if quick:
        cmd.append("--quick")
    if freeze_state.get("freeze_active") and verbose:
        print("Trading freeze is active; canonical update mode will refresh state only.")

    return _run_subprocess(cmd, verbose=verbose)


def run_health_mode(verbose: bool = False) -> bool:
    required = [
        PROJECT_ROOT / "run.py",
        RUN_COMPLETE,
        DASHBOARD_FILE,
        PROJECT_ROOT / "src/risk/risk_policy.py",
        PROJECT_ROOT / "src/risk/risk_controller.py",
        PROJECT_ROOT / "src/execution/execution_gateway.py",
    ]

    missing = [str(p) for p in required if not p.exists()]
    if missing:
        print("ERROR: Missing required files:")
        for path in missing:
            print(f"  - {path}")
        return False

    # Parse critical modules.
    for path in required:
        ok = _run_subprocess([sys.executable, "-m", "py_compile", str(path)], verbose=verbose)
        if not ok:
            print(f"ERROR: py_compile failed for {path}")
            return False

    report = _summarize_health_checks(_collect_health_checks(verbose=verbose))
    print(json.dumps(report, indent=2))
    return report["exit_code"] == 0


def run_status_mode(verbose: bool = False) -> bool:
    freeze_state = _load_freeze_state()
    print("Runtime status")
    print("=" * 24)
    print(f"strict_mode: {_strict_mode()}")
    print(f"ci_gate_mode: {_ci_gate_mode()}")
    print(f"freeze_active: {freeze_state.get('freeze_active')}")
    print(f"freeze_triggers: {freeze_state.get('triggers', [])}")
    print(f"dashboard_file: {DASHBOARD_FILE} ({'ok' if DASHBOARD_FILE.exists() else 'missing'})")
    if verbose:
        print(f"python: {sys.executable}")
        print(f"cwd: {PROJECT_ROOT}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Northstar V3 canonical entrypoint")
    parser.add_argument(
        "--mode",
        choices=["dashboard", "update", "health", "status"],
        default="dashboard",
        help="Operation mode",
    )
    parser.add_argument(
        "--dashboard",
        choices=["brain", "unified"],
        default="brain",
        help="Dashboard profile",
    )
    parser.add_argument("--quick", action="store_true", help="Quick update mode")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    try:
        archive_ok, archive_reason = _ensure_archive_isolation()
        if not archive_ok:
            print(f"ERROR: archive import isolation violated: {archive_reason}")
            return 1

        freeze_state = _load_freeze_state()
        _print_banner(args, freeze_state)

        if args.mode == "dashboard":
            success = run_dashboard_mode(args.dashboard, args.verbose)
        elif args.mode == "update":
            success = run_update_mode(args.quick, args.verbose)
        elif args.mode == "health":
            success = run_health_mode(args.verbose)
        elif args.mode == "status":
            success = run_status_mode(args.verbose)
        else:
            print(f"ERROR: Unsupported mode {args.mode}")
            success = False

        return 0 if success else 1
    except KeyboardInterrupt:
        print("Interrupted by user")
        return 1
    except Exception as exc:
        print(f"Fatal error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
