#!/usr/bin/env python3
"""
Build a canonical formula-lineage + unit-integrity + belief diagnostics artifact.

This runner is intentionally side-effect-light: it computes diagnostics from
existing artifacts and writes a single cohesive report consumed by runtime
integrity checks and dashboards.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text())
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str))
    tmp.replace(path)


def _load_research_policy(project_root: Path, policy_path: str) -> Dict[str, Any]:
    cfg_path = project_root / policy_path
    if not cfg_path.exists():
        return {}
    try:
        with cfg_path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


def _latest_research_cycle(project_root: Path) -> Tuple[Optional[Path], Dict[str, Any]]:
    cycles = sorted((project_root / "data/results/research/cycles").rglob("research_cycle_*.json"))
    if not cycles:
        return None, {}
    latest = cycles[-1]
    return latest, _read_json(latest)


def _extract_dataset_metadata(cycle_blob: Mapping[str, Any]) -> Dict[str, Any]:
    outputs = cycle_blob.get("outputs_generated")
    if not isinstance(outputs, Sequence):
        return {}
    best: Dict[str, Any] = {}
    for row in outputs:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("type", "")).strip().lower() != "research_dataset":
            continue
        data = row.get("data")
        if isinstance(data, Mapping) and len(data) > len(best):
            best = dict(data)
    return best


def _extract_integrity_payload(cycle_blob: Mapping[str, Any], project_root: Path) -> Dict[str, Any]:
    outputs = cycle_blob.get("outputs_generated")
    if isinstance(outputs, Sequence):
        for row in reversed(outputs):
            if not isinstance(row, Mapping):
                continue
            if str(row.get("type", "")).strip().lower() != "integrity_summary":
                continue
            data = row.get("data")
            if isinstance(data, Mapping):
                return dict(data)

    # Fallback to latest structured output if available.
    structured = _read_json(project_root / "data/results/research/state/integrity_summary.json")
    entries = structured.get("data") if isinstance(structured, Mapping) else None
    if isinstance(entries, Sequence):
        for row in reversed(entries):
            if not isinstance(row, Mapping):
                continue
            payload = row.get("data")
            if isinstance(payload, Mapping):
                return dict(payload)
    return {}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build formula lineage + unit integrity artifact")
    parser.add_argument(
        "--policy-path",
        type=str,
        default="config/research_policy.yaml",
        help="Research policy path relative to project root",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/results/research/reports/formula_lineage_and_unit_integrity_latest.json",
        help="Canonical latest output path relative to project root",
    )
    parser.add_argument(
        "--timestamped",
        action="store_true",
        help="Write timestamped copies alongside latest output",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    eval_start = time.perf_counter()

    # Local import keeps this runner independent of research-controller state.
    from src.research.formula_lineage import (
        build_belief_layer_diagnostics,
        build_formula_lineage_report,
        build_gate_overfitting_shadow_audit,
        build_macro_unit_integrity,
    )

    policy = _load_research_policy(PROJECT_ROOT, args.policy_path)
    hr_cfg = dict(policy.get("historical_research", {})) if isinstance(policy, Mapping) else {}
    cert_cfg = dict(hr_cfg.get("certification", {})) if isinstance(hr_cfg, Mapping) else {}

    cycle_path, cycle_blob = _latest_research_cycle(PROJECT_ROOT)
    dataset_metadata = _extract_dataset_metadata(cycle_blob)
    integrity_payload = _extract_integrity_payload(cycle_blob, PROJECT_ROOT)
    integrity_summary = (
        dict(integrity_payload.get("integrity_summary", {}))
        if isinstance(integrity_payload.get("integrity_summary"), Mapping)
        else {}
    )
    critical_failure_details: List[Mapping[str, Any]] = []
    raw_details = integrity_summary.get("critical_failure_details")
    if isinstance(raw_details, Sequence):
        critical_failure_details = [d for d in raw_details if isinstance(d, Mapping)]

    formula_lineage = build_formula_lineage_report(
        project_root=PROJECT_ROOT,
        dataset_metadata=dataset_metadata,
        cert_cfg=cert_cfg,
    )
    macro_unit = build_macro_unit_integrity(project_root=PROJECT_ROOT, cert_cfg=cert_cfg)
    belief_diag = build_belief_layer_diagnostics(PROJECT_ROOT, cert_cfg)
    overfit_shadow = build_gate_overfitting_shadow_audit(
        critical_failure_details=critical_failure_details,
        cert_cfg=cert_cfg,
    )

    elapsed = float(time.perf_counter() - eval_start)
    pass_vector = {
        "formula_lineage": bool(formula_lineage.get("passed", True)),
        "macro_unit_integrity": bool(macro_unit.get("passed", True)),
        "belief_layer_diagnostics": bool(belief_diag.get("passed", True)),
        "gate_overfitting_audit": bool(overfit_shadow.get("passed", True)),
    }
    overall_passed = bool(all(pass_vector.values()))

    out_payload: Dict[str, Any] = {
        "generated_at": _utc_now_iso(),
        "report_version": "formula_lineage_unit_integrity_v1.0",
        "source_context": {
            "project_root": str(PROJECT_ROOT),
            "policy_path": str((PROJECT_ROOT / args.policy_path).resolve()),
            "latest_research_cycle": str(cycle_path) if cycle_path else None,
            "dataset_metadata_fields": sorted(dataset_metadata.keys()),
            "integrity_payload_available": bool(integrity_payload),
        },
        "integrity_summary": {
            "certification_mode": str(integrity_summary.get("mode", "unknown")),
            "hard_fail_triggered": bool(integrity_summary.get("hard_fail_triggered", False)),
            "critical_failures": list(integrity_summary.get("critical_failures", []) or []),
            "certification_passed": bool(integrity_summary.get("certification_passed", False)),
        },
        "formula_lineage": formula_lineage,
        "macro_unit_integrity": macro_unit,
        "belief_layer_diagnostics": belief_diag,
        "gate_overfitting_audit": overfit_shadow,
        "report_runtime_sec": elapsed,
        "passed": overall_passed,
        "pass_vector": pass_vector,
    }

    out_latest = PROJECT_ROOT / args.output
    _write_json(out_latest, out_payload)

    if args.timestamped:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_ts = out_latest.with_name(f"formula_lineage_and_unit_integrity_{ts}.json")
        _write_json(out_ts, out_payload)

    print("Formula Lineage + Unit Integrity Summary")
    print("=" * 52)
    print(f"Passed: {overall_passed}")
    print(f"Runtime sec: {elapsed:.3f}")
    print(f"Output: {out_latest.relative_to(PROJECT_ROOT)}")
    print(f"Pass vector: {json.dumps(pass_vector, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
