#!/usr/bin/env python3
"""Generate a detailed research report from regime IC experiment JSON files."""

from __future__ import annotations

import argparse
import csv
import glob
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
        if math.isfinite(x):
            return x
        return default
    except Exception:
        return default


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(round(float(v)))
    except Exception:
        return default


def _safe_fmt(v: Any, nd: int = 4) -> str:
    if isinstance(v, (int, float)):
        if not math.isfinite(float(v)):
            return "nan"
        return f"{float(v):.{nd}f}"
    return str(v)


def _load(path: Path) -> Dict[str, Any]:
    return dict(json.loads(path.read_text()))


def _summary_row(path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    agg = dict(payload.get("aggregate_metrics", {}) or {})
    rows = list(payload.get("regime_rows", []) or [])
    rows_sorted = sorted(rows, key=lambda r: _to_float(r.get("ic"), default=-1e9), reverse=True)
    best = rows_sorted[0] if rows_sorted else {}
    worst = rows_sorted[-1] if rows_sorted else {}
    ic_mean = _to_float(agg.get("ic_mean"))
    ic_std = max(1e-12, _to_float(agg.get("ic_std")))
    ic_ir = ic_mean / ic_std
    windows = _to_int(agg.get("windows"))
    avg_n_obs = _to_float(agg.get("avg_n_obs"))
    total_n_obs = _to_int(agg.get("total_n_obs"))
    avg_sharpe = _to_float(agg.get("avg_sharpe"))
    stability = _to_float(agg.get("stability_score"))
    avg_turnover = _to_float(agg.get("avg_turnover"))
    monotonic = _to_float(agg.get("monotonic_pass_rate"))
    best_ic = _to_float(best.get("ic"))
    best_n_obs = _to_int(best.get("n_obs"))

    quality_flags: List[str] = []
    if windows < 4:
        quality_flags.append("LOW_WINDOWS")
    if best_n_obs < 2000:
        quality_flags.append("LOW_REGIME_OBS")
    if ic_mean < 0.02:
        quality_flags.append("LOW_GLOBAL_IC")
    if abs(avg_sharpe) > 3.0 and windows < 6:
        quality_flags.append("SHARPE_UNSTABLE")
    if not quality_flags:
        quality_flags.append("OK")

    return {
        "file": path.name,
        "path": str(path),
        "model": str(payload.get("model", "")),
        "windows": windows,
        "avg_n_obs": avg_n_obs,
        "total_n_obs": total_n_obs,
        "global_ic": ic_mean,
        "global_ic_std": ic_std,
        "global_ic_ir": ic_ir,
        "global_sharpe": avg_sharpe,
        "global_stability_score": stability,
        "avg_turnover": avg_turnover,
        "monotonic_pass_rate": monotonic,
        "best_regime": str(best.get("regime", "")),
        "best_regime_ic": best_ic,
        "best_regime_n_obs": best_n_obs,
        "worst_regime": str(worst.get("regime", "")),
        "worst_regime_ic": _to_float(worst.get("ic")),
        "quality_flags": "|".join(quality_flags),
        "regime_rows": rows,
    }


def _write_csv(path: Path, rows: List[Dict[str, Any]], columns: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k) for k in columns})


def _build_markdown(rows: List[Dict[str, Any]], source_glob: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out: List[str] = []
    out.append("# Regime IC Experiment Report")
    out.append("")
    out.append(f"- Generated: `{now}`")
    out.append(f"- Source glob: `{source_glob}`")
    out.append(f"- Experiments: `{len(rows)}`")
    out.append("")

    if not rows:
        out.append("No experiment files found.")
        return "\n".join(out)

    ranked_ic = sorted(rows, key=lambda r: r.get("global_ic", -1e9), reverse=True)
    ranked_stability = sorted(rows, key=lambda r: r.get("global_stability_score", -1e9), reverse=True)

    out.append("## Top By Global IC")
    out.append("")
    out.append("| file | global_ic | ic_ir | windows | global_sharpe | best_regime | best_regime_ic | flags |")
    out.append("|---|---:|---:|---:|---:|---|---:|---|")
    for r in ranked_ic[:5]:
        out.append(
            f"| {r['file']} | {_safe_fmt(r['global_ic'])} | {_safe_fmt(r['global_ic_ir'])} | "
            f"{r['windows']} | {_safe_fmt(r['global_sharpe'])} | {r['best_regime']} | "
            f"{_safe_fmt(r['best_regime_ic'])} | {r['quality_flags']} |"
        )
    out.append("")

    out.append("## Top By Stability")
    out.append("")
    out.append("| file | stability_score | global_ic | windows | avg_turnover | flags |")
    out.append("|---|---:|---:|---:|---:|---|")
    for r in ranked_stability[:5]:
        out.append(
            f"| {r['file']} | {_safe_fmt(r['global_stability_score'])} | {_safe_fmt(r['global_ic'])} | "
            f"{r['windows']} | {_safe_fmt(r['avg_turnover'])} | {r['quality_flags']} |"
        )
    out.append("")

    out.append("## Full Summary")
    out.append("")
    out.append("| file | global_ic | ic_std | ic_ir | sharpe | windows | avg_n_obs | best_regime | best_regime_ic | best_regime_n_obs | flags |")
    out.append("|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---|")
    for r in ranked_ic:
        out.append(
            f"| {r['file']} | {_safe_fmt(r['global_ic'])} | {_safe_fmt(r['global_ic_std'])} | {_safe_fmt(r['global_ic_ir'])} | "
            f"{_safe_fmt(r['global_sharpe'])} | {r['windows']} | {_safe_fmt(r['avg_n_obs'], 1)} | "
            f"{r['best_regime']} | {_safe_fmt(r['best_regime_ic'])} | {r['best_regime_n_obs']} | {r['quality_flags']} |"
        )
    out.append("")

    out.append("## Regime Breakdown")
    out.append("")
    for r in ranked_ic:
        out.append(f"### {r['file']}")
        out.append("")
        out.append("| regime | ic | n_obs | windows | avg_sharpe | avg_max_dd |")
        out.append("|---|---:|---:|---:|---:|---:|")
        rr = sorted(r.get("regime_rows", []), key=lambda x: _to_float(x.get("ic"), -1e9), reverse=True)
        for x in rr:
            out.append(
                f"| {x.get('regime','')} | {_safe_fmt(_to_float(x.get('ic')))} | {_to_int(x.get('n_obs'))} | "
                f"{_to_int(x.get('windows'))} | {_safe_fmt(_to_float(x.get('avg_sharpe')))} | {_safe_fmt(_to_float(x.get('avg_max_drawdown')))} |"
            )
        out.append("")

    out.append("## Recommended Next Candidates")
    out.append("")
    top_promote = [
        r for r in ranked_ic
        if r.get("windows", 0) >= 4
        and r.get("global_ic", 0.0) >= 0.03
        and r.get("best_regime_n_obs", 0) >= 2000
    ][:3]
    if top_promote:
        for i, r in enumerate(top_promote, 1):
            out.append(
                f"{i}. `{r['file']}` -> global_ic={_safe_fmt(r['global_ic'])}, "
                f"best_regime={r['best_regime']} ({_safe_fmt(r['best_regime_ic'])}, n={r['best_regime_n_obs']})"
            )
    else:
        out.append("No candidate met conservative promotion thresholds.")
    out.append("")

    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate detailed report from regime IC run JSON files")
    ap.add_argument("--glob", default="data/research/regime_ic_runs/*.json")
    ap.add_argument("--output-md", default="data/research/reports/regime_ic_experiment_report_latest.md")
    ap.add_argument("--output-csv", default="data/research/reports/regime_ic_experiment_summary_latest.csv")
    ap.add_argument("--output-regime-csv", default="data/research/reports/regime_ic_experiment_regime_rows_latest.csv")
    args = ap.parse_args()

    paths = [Path(p) for p in sorted(glob.glob(args.glob))]
    rows: List[Dict[str, Any]] = []
    for p in paths:
        try:
            rows.append(_summary_row(p, _load(p)))
        except Exception:
            continue

    summary_cols = [
        "file",
        "model",
        "windows",
        "avg_n_obs",
        "total_n_obs",
        "global_ic",
        "global_ic_std",
        "global_ic_ir",
        "global_sharpe",
        "global_stability_score",
        "avg_turnover",
        "monotonic_pass_rate",
        "best_regime",
        "best_regime_ic",
        "best_regime_n_obs",
        "worst_regime",
        "worst_regime_ic",
        "quality_flags",
        "path",
    ]
    _write_csv(Path(args.output_csv), rows, summary_cols)

    regime_rows: List[Dict[str, Any]] = []
    for r in rows:
        for rr in r.get("regime_rows", []):
            regime_rows.append(
                {
                    "file": r.get("file"),
                    "model": r.get("model"),
                    "global_ic": r.get("global_ic"),
                    "global_sharpe": r.get("global_sharpe"),
                    "regime": rr.get("regime"),
                    "regime_ic": rr.get("ic"),
                    "regime_n_obs": rr.get("n_obs"),
                    "regime_windows": rr.get("windows"),
                    "regime_avg_sharpe": rr.get("avg_sharpe"),
                    "regime_avg_max_drawdown": rr.get("avg_max_drawdown"),
                }
            )
    _write_csv(
        Path(args.output_regime_csv),
        regime_rows,
        [
            "file",
            "model",
            "global_ic",
            "global_sharpe",
            "regime",
            "regime_ic",
            "regime_n_obs",
            "regime_windows",
            "regime_avg_sharpe",
            "regime_avg_max_drawdown",
        ],
    )

    md = _build_markdown(rows, source_glob=str(args.glob))
    out_md = Path(args.output_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(md)
    print(f"[report] markdown: {out_md}")
    print(f"[report] summary csv: {Path(args.output_csv)}")
    print(f"[report] regime csv: {Path(args.output_regime_csv)}")
    print(f"[report] experiments loaded: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

