#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCAN_ROOTS = [ROOT / "src", ROOT / "scripts", ROOT / "run.py", ROOT / "run_complete_v3_system.py"]


def _py_files() -> list[Path]:
    paths: list[Path] = []
    for item in SCAN_ROOTS:
        if item.is_file() and item.suffix == ".py":
            paths.append(item)
        elif item.is_dir():
            paths.extend(sorted(item.rglob("*.py")))
    return paths


def main() -> int:
    violations = []
    parse_warnings = []

    for p in sys.path:
        if "archive" in str(p).replace("\\", "/").lower():
            violations.append({"scope": "sys_path", "entry": p, "error": "archive_path_visible"})

    for path in _py_files():
        rel = str(path.relative_to(ROOT))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
        except Exception as exc:
            parse_warnings.append({"scope": "ast", "file": rel, "warning": f"parse_error:{exc}"})
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "archive" or alias.name.startswith("archive."):
                        violations.append({"scope": "import", "file": rel, "line": node.lineno, "error": alias.name})
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "archive" or module.startswith("archive."):
                    violations.append({"scope": "import_from", "file": rel, "line": node.lineno, "error": module})
            elif isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Attribute) and fn.attr in {"append", "insert"}:
                    if isinstance(fn.value, ast.Attribute) and fn.value.attr == "path":
                        if isinstance(fn.value.value, ast.Name) and fn.value.value.id == "sys":
                            for arg in node.args:
                                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and "archive" in arg.value.lower():
                                    violations.append({
                                        "scope": "sys_path_mutation",
                                        "file": rel,
                                        "line": node.lineno,
                                        "error": arg.value,
                                    })

    print(
        json.dumps(
            {
                "check": "archive_import_isolation",
                "violations": violations[:200],
                "parse_warnings": parse_warnings[:200],
                "count": len(violations),
            },
            indent=2,
        )
    )
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
