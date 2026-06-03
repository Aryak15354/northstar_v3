#!/usr/bin/env python3
"""Audit the repository issues called out in the V3 screenshot review."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "src/pnl/ledger.py",
    "src/pnl/nav_calculator.py",
    "src/core/state_authority.py",
    "src/alternative_data/alternative_pipeline_runner.py",
    "src/signal_engineering/pit_audit.py",
    "src/dashboard/app.py",
    "src/dashboard/data_contract.py",
    "src/intelligence/news_brain/news_brain.py",
    "src/intelligence/shock_engine/shock_response_engine.py",
    "src/portfolio/governor.py",
    "src/portfolio/portfolio_governor.py",
    "scripts/run_complete_v3_system.py",
    "pytest.ini",
    "requirements.txt",
    ".gitignore",
    "config/options_trading.yaml",
]

FORBIDDEN_ROOT_FILES = [
    "nohup.out",
    "engine.pid",
]

FORBIDDEN_PATTERNS = [
    ".env.options.bak_*",
    "*.pyc",
    "__pycache__",
]


def git_tracked_files() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def check_required_files(errors: list[str]) -> None:
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).exists():
            errors.append(f"missing required file: {relative}")


def check_options_calendar(errors: list[str]) -> None:
    path = ROOT / "config/options_trading.yaml"
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        errors.append(f"could not load {path.relative_to(ROOT)}: {exc}")
        return

    meetings = payload.get("calendar", {}).get("rbi_mpc_meetings", [])
    decisions = {str(item.get("decision")) for item in meetings if isinstance(item, dict)}
    expected = {
        "2026-04-08",
        "2026-06-05",
        "2026-08-05",
        "2026-10-07",
        "2026-12-04",
        "2027-02-05",
    }
    if not expected.issubset(decisions):
        errors.append("options calendar does not contain the FY27 RBI MPC decision dates")

    text = path.read_text(encoding="utf-8")
    if "V4" in text or "v4" in text:
        errors.append("options config still contains V4 naming")


def check_hygiene(errors: list[str]) -> None:
    for relative in FORBIDDEN_ROOT_FILES:
        if (ROOT / relative).exists():
            errors.append(f"runtime artifact exists at repo root: {relative}")

    for pattern in FORBIDDEN_PATTERNS:
        matches = [
            path
            for path in ROOT.glob(pattern)
            if ".git" not in path.parts and ".venv" not in path.parts and "venv" not in path.parts
        ]
        if matches:
            errors.append(f"forbidden root pattern present: {pattern}")

    tracked = git_tracked_files()
    forbidden_tracked = [
        path
        for path in tracked
        if path.startswith(("backups/", "_cold_archive/", "archive/", "logs/", "data/", "tmp/"))
        or path.endswith((".pyc", ".pid", ".log"))
        or ".env.options.bak_" in path
        or path == "nohup.out"
    ]
    if forbidden_tracked:
        preview = ", ".join(forbidden_tracked[:10])
        errors.append(f"forbidden files tracked by git: {preview}")


def check_strategy_deprecation(errors: list[str]) -> None:
    for relative in [
        "src/options/enhanced_strategy_generator.py",
        "src/options/enhanced_strategy_generator_v2.py",
    ]:
        text = (ROOT / relative).read_text(encoding="utf-8")
        if "DeprecatedWarning" in text:
            errors.append(f"{relative} uses misspelled DeprecatedWarning")
        if "DeprecationWarning" not in text or "enhanced_strategy_generator_v3" not in text:
            errors.append(f"{relative} is not explicitly deprecated toward v3")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-tracked", action="store_true", help="Fail if required files are not tracked by git.")
    args = parser.parse_args()

    errors: list[str] = []
    check_required_files(errors)
    check_options_calendar(errors)
    check_hygiene(errors)
    check_strategy_deprecation(errors)

    if args.require_tracked:
        tracked = git_tracked_files()
        for relative in REQUIRED_FILES:
            if relative not in tracked:
                errors.append(f"required file is not tracked by git: {relative}")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1

    print("V3 screenshot issue audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
