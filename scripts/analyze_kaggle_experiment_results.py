#!/usr/bin/env python3
"""Build compact CSV/HTML diagnostics from pulled Northstar Kaggle results."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _candidate_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for path in sorted(root.rglob("*_summary.json")):
        data = _load_json(path)
        if not isinstance(data, dict):
            continue
        if "summary" in data and "best_candidate" not in data:
            payload = data
        else:
            payload = data.get("best_candidate") or data
        if not isinstance(payload, dict):
            continue
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
        params = payload.get("params") or payload.get("config") or {}
        label = payload.get("label") or path.stem.removesuffix("_summary")
        rows.append(
            {
                "label": label,
                "mean_test_ic": summary.get("mean_test_ic"),
                "ic_ir": summary.get("ic_ir"),
                "mean_train_test_ratio": summary.get("mean_train_test_ratio"),
                "mean_hit_rate": summary.get("mean_hit_rate"),
                "windows_completed": summary.get("windows_completed"),
                "verdict": summary.get("verdict") or payload.get("verdict"),
                "params": json.dumps(params, sort_keys=True),
                "source": str(path),
            }
        )
        seen.add(path)
    for path in sorted(root.rglob("catboost_final.json")):
        if path in seen:
            continue
        data = _load_json(path)
        if not isinstance(data, dict):
            continue
        summary = data.get("summary") or {}
        rows.append(
            {
                "label": path.parent.name.removesuffix("_run"),
                "mean_test_ic": summary.get("mean_test_ic"),
                "ic_ir": summary.get("ic_ir"),
                "mean_train_test_ratio": summary.get("mean_train_test_ratio"),
                "mean_hit_rate": summary.get("mean_hit_rate"),
                "windows_completed": summary.get("windows_completed"),
                "verdict": summary.get("verdict"),
                "params": json.dumps(data.get("config") or {}, sort_keys=True),
                "source": str(path),
            }
        )
    return rows


def _float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _gate(row: dict[str, Any]) -> str:
    ic = _float(row.get("mean_test_ic"))
    ratio = _float(row.get("mean_train_test_ratio"))
    if ic is None or ratio is None:
        return "UNKNOWN"
    if ic >= 0.020 and ratio < 2.5:
        return "VERDICT_A"
    if ic >= 0.020:
        return "VERDICT_B"
    return "VERDICT_C"


def _rank(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(row: dict[str, Any]) -> tuple[int, float, float]:
        ic = _float(row.get("mean_test_ic")) or -999.0
        ratio = _float(row.get("mean_train_test_ratio")) or 999.0
        return (1 if ic >= 0.020 else 0, -ratio, ic)

    ranked = sorted(rows, key=key, reverse=True)
    for idx, row in enumerate(ranked, 1):
        row["rank"] = idx
        row["gate"] = _gate(row)
    return ranked


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "rank",
        "label",
        "mean_test_ic",
        "ic_ir",
        "mean_train_test_ratio",
        "mean_hit_rate",
        "windows_completed",
        "gate",
        "verdict",
        "params",
        "source",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _bar(value: Any, *, scale: float, reverse: bool = False) -> str:
    number = _float(value)
    if number is None:
        return ""
    width = max(2, min(100, int(abs(number) * scale)))
    color = "#2f855a" if (number >= 0 and not reverse) or (number < 2.5 and reverse) else "#c53030"
    return f'<span class="bar" style="width:{width}px;background:{color}"></span>'


def _write_html(path: Path, rows: list[dict[str, Any]]) -> None:
    best = rows[0] if rows else {}
    cells = []
    for row in rows:
        cells.append(
            "<tr>"
            f"<td>{row.get('rank','')}</td>"
            f"<td>{html.escape(str(row.get('label','')))}</td>"
            f"<td>{_float(row.get('mean_test_ic')) or 0:.4f} {_bar(row.get('mean_test_ic'), scale=1000)}</td>"
            f"<td>{_float(row.get('ic_ir')) or 0:.2f}</td>"
            f"<td>{_float(row.get('mean_train_test_ratio')) or 0:.2f}x {_bar(row.get('mean_train_test_ratio'), scale=4, reverse=True)}</td>"
            f"<td>{_float(row.get('mean_hit_rate')) or 0:.3f}</td>"
            f"<td>{html.escape(str(row.get('windows_completed','')))}</td>"
            f"<td>{html.escape(str(row.get('gate','')))}</td>"
            f"<td><code>{html.escape(str(row.get('params','')))}</code></td>"
            "</tr>"
        )
    page = f"""<!doctype html>
<meta charset="utf-8">
<title>Northstar Kaggle Experiment Analysis</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 28px; color: #182026; }}
h1 {{ font-size: 24px; margin: 0 0 8px; }}
.summary {{ display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 12px; margin: 18px 0; }}
.metric {{ border: 1px solid #d8dee4; border-radius: 6px; padding: 10px 12px; }}
.metric b {{ display:block; font-size: 12px; color:#57606a; font-weight:600; }}
.metric span {{ font-size: 20px; font-weight: 700; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ border-bottom: 1px solid #d8dee4; padding: 8px; text-align: left; vertical-align: top; }}
th {{ background: #f6f8fa; position: sticky; top: 0; }}
code {{ white-space: pre-wrap; font-size: 11px; }}
.bar {{ display: inline-block; height: 8px; border-radius: 3px; margin-left: 6px; vertical-align: middle; }}
</style>
<h1>Northstar Kaggle Experiment Analysis</h1>
<div class="summary">
  <div class="metric"><b>Best candidate</b><span>{html.escape(str(best.get('label', 'n/a')))}</span></div>
  <div class="metric"><b>Best IC</b><span>{_float(best.get('mean_test_ic')) or 0:.4f}</span></div>
  <div class="metric"><b>Best ratio</b><span>{_float(best.get('mean_train_test_ratio')) or 0:.2f}x</span></div>
  <div class="metric"><b>Gate</b><span>{html.escape(str(best.get('gate', 'n/a')))}</span></div>
</div>
<table>
<thead><tr><th>Rank</th><th>Candidate</th><th>IC</th><th>IC IR</th><th>Ratio</th><th>Hit</th><th>Windows</th><th>Gate</th><th>Params</th></tr></thead>
<tbody>
{''.join(cells)}
</tbody>
</table>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("results_root", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path("tmp/kaggle_results/analysis"))
    args = parser.parse_args()

    rows = _rank(_candidate_rows(args.results_root.expanduser().resolve()))
    if not rows:
        raise SystemExit(f"No candidate result JSON files found under {args.results_root}")
    _write_csv(args.out_dir / "candidate_rankings.csv", rows)
    _write_html(args.out_dir / "candidate_rankings.html", rows)
    best = rows[0]
    print(f"Best candidate: {best['label']} IC={_float(best.get('mean_test_ic')):.4f} ratio={_float(best.get('mean_train_test_ratio')):.2f}x gate={best['gate']}")
    print(f"Wrote {args.out_dir / 'candidate_rankings.csv'}")
    print(f"Wrote {args.out_dir / 'candidate_rankings.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
