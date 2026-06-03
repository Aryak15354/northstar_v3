#!/usr/bin/env python3
"""Generate a human-friendly catalog for the scripts tree."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
OUTPUT_PATH = PROJECT_ROOT / "docs" / "operations" / "SCRIPT_CATALOG.md"
EXCLUDED_TOOLING = {"catalog_scripts.py", "ns.py"}

CANONICAL_ENTRYPOINTS = [
    ("scripts/run_complete_v3_system.py", "Complete daily Gap 1-7 runner"),
    ("scripts/northstar_v3_unified.py", "Unified launcher"),
    ("scripts/preopen_checks.py", "Pre-market readiness checks"),
    ("scripts/run_morning_pipeline.py", "Morning pipeline"),
    ("scripts/eod_rebalance_with_pnl.py", "EOD processing with unified P&L"),
    ("scripts/promote_research_model.py", "Governed model promotion"),
    ("scripts/launch_dashboard.sh", "Dashboard launcher"),
    ("scripts/verify_gap1_fixes.py", "Gap 1 validator"),
    ("scripts/validate_gap2_complete.py", "Gap 2 validator"),
    ("scripts/validate_gap3_robust_complete.py", "Gap 3 validator"),
    ("scripts/test_gap4_robust.py", "Gap 4 validator"),
    ("scripts/validate_gap5_complete.py", "Gap 5 validator"),
    ("scripts/validate_gap6_complete.py", "Gap 6 validator"),
    ("scripts/validate_gap7_complete.py", "Gap 7 validator"),
]

PREFIX_BUCKETS = [
    ("run_", "Execution runners"),
    ("launch_", "Launchers"),
    ("validate_", "Validators"),
    ("verify_", "Verification scripts"),
    ("test_", "Tests"),
    ("build_", "Builders"),
    ("generate_", "Generators"),
    ("create_", "Creators"),
    ("fetch_", "Fetchers"),
    ("download_", "Downloaders"),
    ("scrape_", "Scrapers"),
    ("backfill_", "Backfills"),
    ("monitor_", "Monitors"),
    ("check_", "Checks"),
    ("audit_", "Audits"),
    ("debug_", "Debugging"),
    ("demo_", "Demos"),
    ("fix_", "Fix-up scripts"),
    ("implement_", "Implementation scripts"),
    ("complete_", "Completion scripts"),
    ("integrate_", "Integration scripts"),
]


def classify_root_script(name: str) -> str:
    for prefix, label in PREFIX_BUCKETS:
        if name.startswith(prefix):
            return label
    return "Other root scripts"


def build_catalog() -> str:
    root_py = sorted(
        p for p in SCRIPTS_DIR.glob("*.py")
        if p.name not in EXCLUDED_TOOLING
    )
    root_sh = sorted(SCRIPTS_DIR.glob("*.sh"))
    grouped_root = defaultdict(list)
    for path in root_py:
        grouped_root[classify_root_script(path.name)].append(path.name)

    subdir_counts = Counter()
    for path in SCRIPTS_DIR.rglob("*.py"):
        if len(path.relative_to(SCRIPTS_DIR).parts) == 1 and path.name in EXCLUDED_TOOLING:
            continue
        rel = path.relative_to(SCRIPTS_DIR)
        bucket = rel.parts[0] if len(rel.parts) > 1 else "(root)"
        subdir_counts[bucket] += 1

    lines = []
    lines.append("# Script Catalog\n")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append("\n")
    lines.append("This catalog exists so you do not have to scan the raw `scripts/` tree.\n")
    lines.append("\n")
    lines.append("## Canonical Entry Points\n")
    lines.append("\n")
    for rel_path, purpose in CANONICAL_ENTRYPOINTS:
        lines.append(f"- `{rel_path}`: {purpose}\n")

    lines.append("\n")
    lines.append("## Shape Of The Tree\n")
    lines.append("\n")
    lines.append(f"- Root Python scripts: {len(root_py)}\n")
    lines.append(f"- Root shell scripts: {len(root_sh)}\n")
    lines.append(f"- Total Python scripts under `scripts/`: {sum(subdir_counts.values())}\n")
    lines.append("\n")
    lines.append("### Python scripts by bucket\n")
    lines.append("\n")
    for bucket, count in subdir_counts.most_common():
        lines.append(f"- `{bucket}`: {count}\n")

    lines.append("\n")
    lines.append("## Root Script Breakdown\n")
    lines.append("\n")
    for bucket in sorted(grouped_root):
        names = grouped_root[bucket]
        preview = ", ".join(names[:10])
        remainder = len(names) - min(len(names), 10)
        suffix = f", +{remainder} more" if remainder > 0 else ""
        lines.append(f"- **{bucket}**: {len(names)}\n")
        lines.append(f"  Example: `{preview}{suffix}`\n")

    lines.append("\n")
    lines.append("## Working Rule\n")
    lines.append("\n")
    lines.append("- Prefer the canonical entrypoints above.\n")
    lines.append("- Use subdirectories for one-off debugging, cleanup, and analysis scripts.\n")
    lines.append("- Avoid adding new temporary scripts to the root `scripts/` directory.\n")
    return "".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the scripts catalog")
    parser.add_argument("--write", action="store_true", help="Write the catalog to docs/operations/SCRIPT_CATALOG.md")
    args = parser.parse_args()

    catalog = build_catalog()
    if args.write:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(catalog, encoding="utf-8")
        print(f"Wrote {OUTPUT_PATH}")
    else:
        print(catalog)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
