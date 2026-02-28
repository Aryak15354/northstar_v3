#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET_FILES = [
    ROOT / "src/risk/risk_policy.py",
    ROOT / "src/risk/risk_controller.py",
    ROOT / "src/execution/execution_gateway.py",
]


def _annotate_parents(tree: ast.AST) -> None:
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            setattr(child, "_parent", parent)


def _inside_function(node: ast.AST) -> bool:
    current = getattr(node, "_parent", None)
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return True
        current = getattr(current, "_parent", None)
    return False


def main() -> int:
    violations = []

    for path in TARGET_FILES:
        rel = str(path.relative_to(ROOT))
        if not path.exists():
            violations.append({"file": rel, "error": "missing"})
            continue
        src = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(src, filename=str(path))
        except Exception as exc:
            violations.append({"file": rel, "error": f"parse_error:{exc}"})
            continue

        _annotate_parents(tree)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)) and _inside_function(node):
                violations.append(
                    {
                        "file": rel,
                        "line": getattr(node, "lineno", 0),
                        "error": "lazy_import_in_function",
                    }
                )

    print(json.dumps({"check": "no_lazy_imports_risk_path", "violations": violations[:200], "count": len(violations)}, indent=2))
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
