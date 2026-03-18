#!/usr/bin/env python3
"""Northstar V4 canonical runtime entrypoint.

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
from typing import Dict, Tuple


PROJECT_ROOT = Path(__file__).resolve().parent
DASHBOARD_FILE = PROJECT_ROOT / "src/dashboard/northstar_v3_ultimate_integrated_dashboard.py"
RUN_COMPLETE = PROJECT_ROOT / "run_complete_v3_system.py"
CI_UPDATE_SMOKE = PROJECT_ROOT / "scripts/ci/run_update_gate_smoke.py"
FREEZE_STATE_FILE = PROJECT_ROOT / "data/processed/model_freeze_state.json"


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
    print("NORTHSTAR V4 ENTRYPOINT")
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
    if _ci_gate_mode():
        if not CI_UPDATE_SMOKE.exists():
            print(f"ERROR: Missing CI update smoke runner: {CI_UPDATE_SMOKE}")
            return False
        return _run_subprocess([sys.executable, str(CI_UPDATE_SMOKE)], verbose=verbose)

    if not RUN_COMPLETE.exists():
        print(f"ERROR: Missing update runner: {RUN_COMPLETE}")
        return False

    freeze_state = _load_freeze_state()
    cmd = [sys.executable, str(RUN_COMPLETE), "--no-dashboard"]
    if quick:
        cmd.append("--quick")
    if freeze_state.get("freeze_active"):
        # Defense in depth: update path should not open new risk while frozen.
        cmd.append("--skip-options-cycle")

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

    triage_cmd = [sys.executable, "scripts/gate_triage.py"]

    proc = subprocess.run(triage_cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    print(proc.stdout.strip())
    if proc.returncode != 0 and not proc.stdout.strip():
        print("ERROR: gate triage execution failed")
        if proc.stderr:
            print(proc.stderr.strip())
        return False

    try:
        triage_report = json.loads(proc.stdout or "{}")
    except Exception:
        print("ERROR: gate triage emitted non-JSON output")
        if proc.stderr:
            print(proc.stderr.strip())
        return False

    checks = {item.get("check"): item.get("status") for item in triage_report.get("checks", [])}
    critical_checks = {"runtime_schema", "wal", "lock_acquisition", "mode_transitions"}
    failed_critical = sorted(name for name in critical_checks if checks.get(name) == "fail")
    if failed_critical:
        print(f"ERROR: health critical checks failed: {failed_critical}")
        return False

    if _strict_mode():
        strict_fail = sorted(name for name in ["process_exits"] if checks.get(name) == "fail")
        if strict_fail:
            print(f"ERROR: strict health checks failed: {strict_fail}")
            return False

    return True


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
    parser = argparse.ArgumentParser(description="Northstar V4 canonical entrypoint")
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
