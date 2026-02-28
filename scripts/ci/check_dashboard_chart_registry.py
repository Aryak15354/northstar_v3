#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_FILE = ROOT / "src/dashboard/northstar_v3_ultimate_integrated_dashboard.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


REQUIRED_LIVE_CHART_IDS = {
    "market_pressure_surface",
    "portfolio_expression_surface",
    "survival_engine_surface",
    "news_layer_narrative_shock_intensity",
    "system_health_runtime_metrics",
    "system_health_sector_allocation",
}


def _is_st_plotly_chart_call(node: ast.Call) -> bool:
    if not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr != "plotly_chart":
        return False
    return isinstance(node.func.value, ast.Name) and node.func.value.id == "st"


def _literal_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def main() -> int:
    if not DASHBOARD_FILE.exists():
        print(
            json.dumps(
                {
                    "check": "dashboard_chart_registry",
                    "error": f"missing dashboard file: {DASHBOARD_FILE}",
                },
                indent=2,
            )
        )
        return 1

    text = DASHBOARD_FILE.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(DASHBOARD_FILE))
    parent_map = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parent_map[child] = parent

    def _enclosing_function_name(node: ast.AST) -> str | None:
        cur = node
        while cur in parent_map:
            cur = parent_map[cur]
            if isinstance(cur, ast.FunctionDef):
                return cur.name
        return None

    missing_plotly_keys = []
    dynamic_plotly_keys = []
    contract_ids_seen: set[str] = set()
    contract_ids_non_literal = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_st_plotly_chart_call(node):
            key_kw = next((kw for kw in node.keywords if kw.arg == "key"), None)
            if key_kw is None:
                missing_plotly_keys.append(node.lineno)
            else:
                literal = _literal_string(key_kw.value)
                if literal is None:
                    # `_render_chart_with_contract` receives explicit keys at call-sites and
                    # forwards them through its local `key` parameter.
                    if (
                        isinstance(key_kw.value, ast.Name)
                        and key_kw.value.id == "key"
                        and _enclosing_function_name(node) == "_render_chart_with_contract"
                    ):
                        continue
                    dynamic_plotly_keys.append(node.lineno)

        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_render_chart_with_contract"
        ):
            chart_kw = next((kw for kw in node.keywords if kw.arg == "chart_id"), None)
            if chart_kw is None:
                contract_ids_non_literal.append(node.lineno)
                continue
            chart_id = _literal_string(chart_kw.value)
            if chart_id is None:
                contract_ids_non_literal.append(node.lineno)
                continue
            contract_ids_seen.add(chart_id)

    from src.dashboard.chart_registry import CHART_REGISTRY

    unknown_contract_ids = sorted(cid for cid in contract_ids_seen if cid not in CHART_REGISTRY)
    required_missing_in_registry = sorted(cid for cid in REQUIRED_LIVE_CHART_IDS if cid not in CHART_REGISTRY)
    required_not_wired = sorted(cid for cid in REQUIRED_LIVE_CHART_IDS if cid not in contract_ids_seen)

    violations = {
        "missing_plotly_keys": missing_plotly_keys,
        "contract_ids_non_literal": contract_ids_non_literal,
        "unknown_contract_ids": unknown_contract_ids,
        "required_missing_in_registry": required_missing_in_registry,
        "required_not_wired": required_not_wired,
    }

    report = {
        "check": "dashboard_chart_registry",
        "file": str(DASHBOARD_FILE.relative_to(ROOT)),
        "plotly_chart_calls_missing_key": len(missing_plotly_keys),
        "plotly_chart_calls_dynamic_key": len(dynamic_plotly_keys),
        "dynamic_key_lines": dynamic_plotly_keys[:200],
        "contract_chart_ids_seen": sorted(contract_ids_seen),
        "violations": violations,
    }
    print(json.dumps(report, indent=2))

    has_errors = any(bool(v) for v in violations.values())
    return 1 if has_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
