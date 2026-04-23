#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE_DEFAULT = ROOT / "audit/reachability_baseline.json"
ENTRYPOINTS = [
    ROOT / "run.py",
    ROOT / "run_complete_v3_system.py",
    ROOT / "scripts/northstar_v3_unified.py",
]
ALWAYS_ACTIVE = [
    ROOT / "src/risk/risk_policy.py",
    ROOT / "src/risk/risk_controller.py",
    ROOT / "src/execution/execution_gateway.py",
    ROOT / "src/dashboard/chart_registry.py",
    ROOT / "src/dashboard/view_model_loader.py",
    ROOT / "scripts/ci/bootstrap_runtime_gate_state.py",
    ROOT / "scripts/ci/check_dashboard_chart_registry.py",
    ROOT / "scripts/ci/check_no_direct_runtime_mutation_imports.py",
    ROOT / "scripts/ci/strict_data_ingestion_check.py",
    ROOT / "scripts/ci/strict_options_runtime_check.py",
    ROOT / "scripts/ci/strict_system_update_check.py",
    ROOT / "scripts/run_integrated_options_paper_engine.py",
    ROOT / "scripts/run_alpha_diagnostics.py",
    ROOT / "scripts/runners/build_dashboard_view_model.py",
    ROOT / "scripts/runners/generate_dashboard_emission_roadmap.py",
]


def _py_files_under(path: Path):
    for p in path.rglob("*.py"):
        rel = str(p.relative_to(ROOT))
        if rel.startswith(("tests/", "archive/", "venv/", "data/", "logs/", "snapshots/", "github_repo/")):
            continue
        yield p


def _production_files() -> set[str]:
    files = {"run.py", "run_complete_v3_system.py"}
    for root in [ROOT / "src", ROOT / "scripts"]:
        if root.exists():
            files.update(str(p.relative_to(ROOT)) for p in _py_files_under(root))
    return files


def _resolve_module(module: str) -> str | None:
    parts = module.split(".")
    if not parts:
        return None
    if parts[0] not in {"src", "scripts"}:
        return None
    candidate = ROOT.joinpath(*parts).with_suffix(".py")
    if candidate.exists():
        return str(candidate.relative_to(ROOT))
    candidate = ROOT.joinpath(*parts, "__init__.py")
    if candidate.exists():
        return str(candidate.relative_to(ROOT))
    return None


def _imports_from_file(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text, filename=str(path))
    except Exception:
        return set()

    deps: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                resolved = _resolve_module(alias.name)
                if resolved:
                    deps.add(resolved)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            module = node.module or ""
            resolved = _resolve_module(module)
            if resolved:
                deps.add(resolved)
    return deps


def _reachable_files() -> set[str]:
    seeds = [p for p in ENTRYPOINTS if p.exists()]
    seen: set[str] = set()
    queue = [str(p.relative_to(ROOT)) for p in seeds]
    queue.extend(str(p.relative_to(ROOT)) for p in ALWAYS_ACTIVE if p.exists())

    while queue:
        rel = queue.pop(0)
        if rel in seen:
            continue
        seen.add(rel)
        path = ROOT / rel
        if not path.exists() or path.suffix != ".py":
            continue
        for dep in sorted(_imports_from_file(path)):
            if dep not in seen:
                queue.append(dep)
    return seen


def _write_baseline(path: Path, production: set[str], reachable: set[str]) -> None:
    unreachable = sorted(production - reachable)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "entrypoints": [str(p.relative_to(ROOT)) for p in ENTRYPOINTS if p.exists()],
        "production_files": sorted(production),
        "reachable_files": sorted(reachable),
        "unreachable_allowlist": unreachable,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Reachability regression guard")
    parser.add_argument("--baseline", default=str(BASELINE_DEFAULT))
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args()

    baseline_path = Path(args.baseline)
    production = _production_files()
    reachable = _reachable_files()

    if args.update_baseline:
        _write_baseline(baseline_path, production, reachable)
        print(json.dumps({"check": "reachability_regression", "updated": str(baseline_path)}, indent=2))
        return 0

    if not baseline_path.exists():
        print(json.dumps({"check": "reachability_regression", "error": "baseline_missing", "baseline": str(baseline_path)}, indent=2))
        return 1

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    allow_unreachable = set(baseline.get("unreachable_allowlist", []))

    current_unreachable = production - reachable
    new_unreachable = sorted(current_unreachable - allow_unreachable)

    report = {
        "check": "reachability_regression",
        "production_count": len(production),
        "reachable_count": len(reachable),
        "current_unreachable_count": len(current_unreachable),
        "new_unreachable": new_unreachable[:300],
        "new_unreachable_count": len(new_unreachable),
        "baseline": str(baseline_path),
    }
    print(json.dumps(report, indent=2))

    return 1 if new_unreachable else 0


if __name__ == "__main__":
    raise SystemExit(main())
