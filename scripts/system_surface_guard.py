#!/usr/bin/env python3
"""Audit the canonical runtime surface and prune safe backup clutter."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config" / "system_surface.yaml"
REPORT_PATH = PROJECT_ROOT / "audit" / "system_surface_guard_latest.json"
TIMESTAMP_SUFFIX_RE = re.compile(r"^(?P<prefix>.+?)_(?P<stamp>\d{8}(?:_\d{6})?)$")


def _load_config() -> dict[str, Any]:
    payload = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid system surface config: {CONFIG_PATH}")
    return payload


def _rel(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))


def _iter_canonical_paths(node: Any) -> list[Path]:
    paths: list[Path] = []
    if isinstance(node, dict):
        for value in node.values():
            paths.extend(_iter_canonical_paths(value))
    elif isinstance(node, list):
        for value in node:
            paths.extend(_iter_canonical_paths(value))
    elif isinstance(node, str):
        paths.append(PROJECT_ROOT / node)
    return paths


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _scan_rule(path: Path, rule: dict[str, Any]) -> list[dict[str, Any]]:
    allow = set(rule.get("allow_in") or [])
    rel_path = _rel(path)
    if rel_path in allow:
        return []

    text = path.read_text(encoding="utf-8", errors="replace")
    hits: list[dict[str, Any]] = []
    kind = str(rule.get("kind", "literal")).strip().lower()
    pattern = str(rule.get("pattern", ""))

    if kind == "regex":
        compiled = re.compile(pattern)
        matches = compiled.finditer(text)
        for match in matches:
            hits.append(
                {
                    "rule": rule.get("name", "unnamed"),
                    "file": rel_path,
                    "line": _line_number(text, match.start()),
                    "match": match.group(0),
                }
            )
    else:
        if pattern not in text:
            return []
        for idx, line in enumerate(text.splitlines(), start=1):
            if pattern in line:
                hits.append(
                    {
                        "rule": rule.get("name", "unnamed"),
                        "file": rel_path,
                        "line": idx,
                        "match": pattern,
                    }
                )
    return hits


def _parse_timestamped_file(path: Path) -> tuple[str, datetime] | None:
    match = TIMESTAMP_SUFFIX_RE.match(path.stem)
    if not match:
        return None
    raw = match.group("stamp")
    fmt = "%Y%m%d_%H%M%S" if "_" in raw else "%Y%m%d"
    try:
        parsed = datetime.strptime(raw, fmt)
    except ValueError:
        return None
    prefix = f"{match.group('prefix')}{path.suffix}"
    return prefix, parsed


def _retention_report(config: dict[str, Any], *, apply_retention: bool) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for entry in config.get("retention") or []:
        rel_root = str(entry.get("path", "")).strip()
        root = PROJECT_ROOT / rel_root
        patterns = list(entry.get("patterns") or ["*"])
        keep_latest = int(entry.get("keep_latest_per_prefix", 0) or 0)
        files: set[Path] = set()
        for pattern in patterns:
            files.update(path for path in root.glob(pattern) if path.is_file())

        grouped: dict[str, list[tuple[datetime, Path]]] = defaultdict(list)
        for path in files:
            parsed = _parse_timestamped_file(path)
            if not parsed:
                continue
            prefix, stamp = parsed
            grouped[prefix].append((stamp, path))

        candidates: list[str] = []
        removed: list[str] = []
        for prefix, items in sorted(grouped.items()):
            items.sort(key=lambda item: item[0], reverse=True)
            for _, stale_path in items[keep_latest:]:
                rel_path = _rel(stale_path)
                candidates.append(rel_path)
                if apply_retention:
                    stale_path.unlink(missing_ok=True)
                    removed.append(rel_path)

        reports.append(
            {
                "path": rel_root,
                "keep_latest_per_prefix": keep_latest,
                "candidate_count": len(candidates),
                "removed_count": len(removed),
                "candidates": candidates[:200],
                "removed": removed[:200],
            }
        )
    return reports


def build_report(*, apply_retention: bool) -> dict[str, Any]:
    config = _load_config()
    canonical_paths = _iter_canonical_paths(config.get("canonical") or {})
    canonical_missing = [_rel(path) for path in canonical_paths if not path.exists()]

    operational_files = []
    for rel_path in config.get("operational_surfaces") or []:
        path = PROJECT_ROOT / rel_path
        if path.exists():
            operational_files.append(path)

    deprecated_hits: list[dict[str, Any]] = []
    for path in operational_files:
        for rule in config.get("deprecated_patterns") or []:
            deprecated_hits.extend(_scan_rule(path, rule))

    retention = _retention_report(config, apply_retention=apply_retention)
    total_retention_candidates = sum(int(item.get("candidate_count", 0) or 0) for item in retention)

    status = "FAIL" if canonical_missing or deprecated_hits else ("WARN" if total_retention_candidates else "PASS")
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "canonical_missing": canonical_missing,
        "operational_files_checked": [_rel(path) for path in operational_files],
        "deprecated_reference_count": len(deprecated_hits),
        "deprecated_references": deprecated_hits[:500],
        "retention": retention,
        "apply_retention": apply_retention,
    }


def _write_report(report: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")


def _print_human(report: dict[str, Any]) -> None:
    print("System Surface Guard")
    print("=" * 48)
    print(f"Status: {report['status']}")
    print(f"Canonical missing: {len(report['canonical_missing'])}")
    print(f"Deprecated references: {report['deprecated_reference_count']}")
    for item in report["retention"]:
        print(
            f"Retention {item['path']}: candidates={item['candidate_count']} removed={item['removed_count']}"
        )
    if report["canonical_missing"]:
        print("\nMissing canonical paths:")
        for path in report["canonical_missing"]:
            print(f"  - {path}")
    if report["deprecated_references"]:
        print("\nDeprecated operational references:")
        for hit in report["deprecated_references"][:25]:
            print(f"  - {hit['file']}:{hit['line']} [{hit['rule']}] {hit['match']}")
        remaining = max(len(report["deprecated_references"]) - 25, 0)
        if remaining:
            print(f"  ... {remaining} more")
    print(f"\nReport: {REPORT_PATH}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit and prune the canonical runtime surface.")
    parser.add_argument(
        "--apply-retention",
        action="store_true",
        help="Delete safe stale files from configured backup directories.",
    )
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    args = parser.parse_args()

    report = build_report(apply_retention=bool(args.apply_retention))
    _write_report(report)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_human(report)
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
