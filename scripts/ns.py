#!/usr/bin/env python3
"""Small navigation CLI for the Northstar repo surface."""

from __future__ import annotations

import argparse
from collections import Counter
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
EXCLUDED_ROOT_TOOLING = {"catalog_scripts.py", "ns.py"}

CANONICAL_COMMANDS = [
    ("Complete daily run", "python3 scripts/run_complete_v3_system.py"),
    ("Unified launcher", "python3 scripts/northstar_v3_unified.py"),
    ("Preopen checks", "python3 scripts/preopen_checks.py"),
    ("Morning pipeline", "python3 scripts/run_morning_pipeline.py"),
    ("Dashboard", "bash scripts/launch_dashboard.sh"),
    ("EOD with unified P&L", "python3 scripts/eod_rebalance_with_pnl.py"),
    ("Governed promotion", "python3 scripts/promote_research_model.py --help"),
]

GAP_VALIDATORS = [
    ("Gap 1", "python3 scripts/verify_gap1_fixes.py"),
    ("Gap 2", "python3 scripts/validate_gap2_complete.py"),
    ("Gap 3", "python3 scripts/validate_gap3_robust_complete.py"),
    ("Gap 4", "python3 scripts/test_gap4_robust.py"),
    ("Gap 5", "python3 scripts/validate_gap5_complete.py"),
    ("Gap 6", "python3 scripts/validate_gap6_complete.py"),
    ("Gap 7", "python3 scripts/validate_gap7_complete.py"),
]

SECONDARY_ROOTS = [
    "reports/",
    "snapshots/",
    "archive/",
    "_cold_archive/",
    "data/results/analysis/",
    "truth_mode_runs/",
]


def print_surface() -> None:
    print("Northstar repo surface")
    print("")
    print("Use these first:")
    print("- Task runner: make help")
    print(f"- Workspace guide: {PROJECT_ROOT / 'docs/operations/WORKSPACE_GUIDE.md'}")
    print(f"- Script catalog: {PROJECT_ROOT / 'docs/operations/SCRIPT_CATALOG.md'}")
    print("")
    print("Canonical commands:")
    for label, command in CANONICAL_COMMANDS:
        print(f"- {label}: {command}")
    print("")
    print("Gap validators:")
    for label, command in GAP_VALIDATORS:
        print(f"- {label}: {command}")


def run_command(command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def iter_script_paths() -> list[Path]:
    paths = []
    for path in sorted(SCRIPTS_DIR.rglob("*")):
        if path.is_dir():
            continue
        if "__pycache__" in path.parts:
            continue
        if path.suffix not in {".py", ".sh"}:
            continue
        paths.append(path)
    return paths


def print_gaps() -> None:
    for label, command in GAP_VALIDATORS:
        print(f"{label}: {command}")


def find_scripts(query: str) -> int:
    needle = query.lower()
    matches = []
    for path in iter_script_paths():
        rel_path = path.relative_to(PROJECT_ROOT).as_posix()
        if needle in rel_path.lower():
            matches.append(rel_path)

    if not matches:
        print(f"No script matches for {query!r}.")
        return 1

    print(f"Script matches for {query!r}:")
    for rel_path in matches[:50]:
        print(f"- {rel_path}")
    if len(matches) > 50:
        print(f"- +{len(matches) - 50} more")
    return 0


def count_tracked(pathspec: str) -> int:
    try:
        output = run_command(["git", "ls-files", pathspec])
    except (FileNotFoundError, subprocess.CalledProcessError):
        return 0
    return len([line for line in output.splitlines() if line])


def get_git_status_counts() -> Counter[str]:
    try:
        output = run_command(["git", "status", "--porcelain"])
    except (FileNotFoundError, subprocess.CalledProcessError):
        return Counter()

    counts: Counter[str] = Counter()
    for line in output.splitlines():
        if len(line) < 4:
            continue
        raw_path = line[3:]
        if " -> " in raw_path:
            raw_path = raw_path.split(" -> ", 1)[1]
        path = Path(raw_path)
        bucket = path.parts[0] if path.parts else raw_path
        counts[bucket] += 1
    return counts


def print_doctor() -> None:
    root_python = len([path for path in SCRIPTS_DIR.glob("*.py") if path.name not in EXCLUDED_ROOT_TOOLING])
    total_python = len(
        [
            path
            for path in SCRIPTS_DIR.rglob("*.py")
            if "__pycache__" not in path.parts
            and not (path.parent == SCRIPTS_DIR and path.name in EXCLUDED_ROOT_TOOLING)
        ]
    )
    tracked_hypothesis = count_tracked(".hypothesis")
    tracked_snapshots = count_tracked("snapshots")
    tracked_reports = count_tracked("reports")
    status_counts = get_git_status_counts()

    print("Northstar repo doctor")
    print("")
    print("Repo shape:")
    print(f"- Root Python scripts: {root_python}")
    print(f"- Total Python scripts under scripts/: {total_python}")
    print(f"- Tracked .hypothesis files: {tracked_hypothesis}")
    print(f"- Tracked snapshots: {tracked_snapshots}")
    print(f"- Tracked reports: {tracked_reports}")
    print("")
    print("Recommended working set:")
    print("- Product code: src/, config/, tests/")
    print("- Operator surface: make help, python3 scripts/ns.py")
    print("- Guidance: docs/operations/WORKSPACE_GUIDE.md")
    print(f"- Usually secondary roots: {', '.join(SECONDARY_ROOTS)}")
    print("")
    print("Top git-noise buckets:")
    if not status_counts:
        print("- No git status data available")
        return
    for bucket, count in status_counts.most_common(10):
        print(f"- {bucket}: {count}")
    print("")
    print("Use `make doctor`, `make help`, and `make find q=<term>` instead of scanning the raw tree.")


def run_catalog(refresh: bool) -> int:
    catalog_script = PROJECT_ROOT / "scripts" / "catalog_scripts.py"
    command = [sys.executable, str(catalog_script)]
    if refresh:
        command.append("--write")
    return subprocess.call(command, cwd=PROJECT_ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description="Northstar repo navigator")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("surface", help="Show the curated repo surface")

    catalog_parser = subparsers.add_parser("catalog", help="Show or refresh the script catalog")
    catalog_parser.add_argument("--refresh", action="store_true", help="Regenerate docs/operations/SCRIPT_CATALOG.md")

    subparsers.add_parser("gaps", help="Show the gap validator commands")
    find_parser = subparsers.add_parser("find", help="Find scripts by name")
    find_parser.add_argument("query", help="Substring to search for in script paths")
    subparsers.add_parser("doctor", help="Show a repo hygiene summary")

    args = parser.parse_args()

    if args.command in [None, "surface"]:
        print_surface()
        return 0

    if args.command == "catalog":
        return run_catalog(refresh=args.refresh)

    if args.command == "gaps":
        print_gaps()
        return 0

    if args.command == "find":
        return find_scripts(args.query)

    if args.command == "doctor":
        print_doctor()
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
