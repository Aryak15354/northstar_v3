#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = ROOT / "audit/dashboard_chart_inventory_full.json"
OUT_JSON = ROOT / "audit/dashboard_emission_compression_plan_2026-02-28.json"
OUT_MD = ROOT / "docs/stabilization/V4_DASHBOARD_EMISSION_COMPRESSION_ROADMAP.md"


WAVES = [
    {"wave": "Wave 1", "target": 150, "goal": "Live parallel compression"},
    {"wave": "Wave 2", "target": 120, "goal": "Family surface conversion"},
    {"wave": "Wave 3", "target": 100, "goal": "Research collapsing + lazy loading"},
    {"wave": "Wave 4", "target": 90, "goal": "Semantic consolidation"},
]


def _action_for_function(name: str) -> str:
    if name == "render_advanced_intelligence":
        return "Convert to family tabs + small-multiples + overlays; keep deep views behind expanders."
    if name == "render_alpha_os_control_tower":
        return "Merge overlapping risk diagnostics into one survival engine card set."
    if name in {"render_v3_analytics", "render_advanced_analytics"}:
        return "Consolidate benchmark/performance/risk stats into a compact KPI+toggle card."
    if name == "render_risk_survival_layer":
        return "Unify drawdown/crisis/entropy into a single multi-layer risk card."
    if name in {"render_macro_news_pressure_index", "render_sector_sentiment_vs_flows"}:
        return "Merge into one market/news pressure surface with toggle dimensions."
    return "Fold into section-level card family and remove duplicate derivative views."


def main() -> int:
    if not INVENTORY_PATH.exists():
        raise RuntimeError(f"missing inventory: {INVENTORY_PATH}")

    payload = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    summary = payload.get("summary", {})
    charts = payload.get("charts")
    if charts is None:
        charts = payload.get("entries", [])
    if not isinstance(charts, list):
        raise RuntimeError("inventory malformed: charts/entries not list")

    total = int(summary.get("total_charts", len(charts)))
    by_function = Counter(str(c.get("function", "<unknown>")) for c in charts)
    top_functions = [
        {
            "function": fn,
            "charts": count,
            "recommended_action": _action_for_function(fn),
        }
        for fn, count in by_function.most_common(20)
    ]

    wave_rows = []
    if total <= 90:
        wave_rows.append(
            {
                "wave": "Completed",
                "from": total,
                "to": total,
                "estimated_reduction": 0,
                "goal": "Emission target achieved (<=90)",
            }
        )
    else:
        current = total
        for w in WAVES:
            target = int(w["target"])
            reduction = max(0, current - target)
            wave_rows.append(
                {
                    "wave": w["wave"],
                    "from": current,
                    "to": target,
                    "estimated_reduction": reduction,
                    "goal": w["goal"],
                }
            )
            current = target

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline_total": total,
        "target_total": 90,
        "waves": wave_rows,
        "top_emitters": top_functions,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(output, indent=2), encoding="utf-8")

    lines = [
        "# V4 Dashboard Emission Compression Roadmap",
        "",
        f"- Baseline emissions: {total}",
        "- Target emissions: 90",
        "",
        "## Wave Plan",
        "| Wave | From | To | Estimated Reduction | Goal |",
        "|---|---:|---:|---:|---|",
    ]
    for row in wave_rows:
        lines.append(
            f"| {row['wave']} | {row['from']} | {row['to']} | {row['estimated_reduction']} | {row['goal']} |"
        )

    lines.extend(
        [
            "",
            "## Top Emission Sources (Current)",
            "| Function | Emissions | Compression Action |",
            "|---|---:|---|",
        ]
    )
    for item in top_functions:
        lines.append(
            f"| {item['function']} | {item['charts']} | {item['recommended_action']} |"
        )

    lines.extend(
        [
            "",
            "## Safety Migration Rule",
            "1. Replace chart with new surface container.",
            "2. Verify contract and freshness behavior.",
            "3. Run strict runtime gate.",
            "4. Remove old chart emission.",
            "5. Recompute inventory and repeat.",
        ]
    )

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"json": str(OUT_JSON), "markdown": str(OUT_MD)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
