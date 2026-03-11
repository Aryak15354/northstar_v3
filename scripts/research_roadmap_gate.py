#!/usr/bin/env python3
"""Roadmap preflight and phase gate evaluation utilities."""

from __future__ import annotations

import argparse
import glob
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import yaml


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _safe_load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        out = json.loads(path.read_text())
        return dict(out or {})
    except Exception:
        return {}


def _safe_load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        out = yaml.safe_load(path.read_text())
        return dict(out or {})
    except Exception:
        return {}


def _runtime_cfg_shape_and_payload(cfg: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
    if isinstance(cfg.get("historical_research"), dict):
        return "historical_research", dict(cfg.get("historical_research", {}) or {})
    if isinstance(cfg.get("dataset"), dict) or isinstance(cfg.get("training"), dict):
        return "top_level", dict(cfg or {})
    return "invalid", {}


def _is_low_resource_forced_enabled(raw: Any) -> bool:
    token = str(raw or "").strip().lower()
    if not token:
        return False
    return token in {"1", "true", "yes", "on", "enabled", "auto"}


def _result_paths(output_dir: Path, pattern: str = "*.json") -> List[Path]:
    paths = [Path(p) for p in glob.glob(str(output_dir / pattern))]
    blocked_names = {"preflight.json", "phase_gate.json", "phase3_gate.json"}
    return sorted([p for p in paths if p.name not in blocked_names])


def _metrics_from_result(path: Path) -> Dict[str, Any]:
    payload = _safe_load_json(path)
    agg = dict(payload.get("aggregate_metrics", {}) or {})
    return {
        "path": str(path),
        "windows": float(agg.get("windows", 0.0) or 0.0),
        "ic_mean": float(agg.get("ic_mean", 0.0) or 0.0),
        "total_n_obs": float(agg.get("total_n_obs", 0.0) or 0.0),
        "dataset_tickers": int(payload.get("dataset_tickers", 0) or 0),
        "pit_enabled": bool(((payload.get("data_integrity", {}) or {}).get("pit_fundamentals_enabled", False))),
        "pit_no_future_leak": bool(((payload.get("data_integrity", {}) or {}).get("pit_no_future_leak", False))),
    }


def run_preflight(*, repo_root: Path, base_config: Path, output_dir: Path, phase: str) -> int:
    cfg = _safe_load_yaml(base_config)
    cfg_shape, runtime_cfg = _runtime_cfg_shape_and_payload(cfg)
    dataset_cfg = dict(runtime_cfg.get("dataset", {}) or {})

    lr_tokens = [
        cfg.get("low_resource_mode"),
        runtime_cfg.get("low_resource_mode"),
        cfg.get("dataset", {}).get("low_resource_mode") if isinstance(cfg.get("dataset"), dict) else None,
        dataset_cfg.get("low_resource_mode"),
    ]
    low_resource_hidden = any(_is_low_resource_forced_enabled(x) for x in lr_tokens)

    checks = [
        {"name": "base_config_exists", "pass": bool(base_config.exists()), "detail": str(base_config)},
        {"name": "config_shape_valid", "pass": bool(cfg_shape != "invalid"), "detail": cfg_shape},
        {"name": "prices_exists", "pass": bool((repo_root / "data/processed/prices.parquet").exists())},
        {"name": "fundamentals_exists", "pass": bool((repo_root / "data/processed/fundamentals.parquet").exists())},
        {"name": "runner_exists", "pass": bool((repo_root / "scripts/run_regime_ic_split.py").exists())},
        {"name": "low_resource_profile_not_forced", "pass": bool(not low_resource_hidden), "detail": [str(x) for x in lr_tokens if x is not None]},
        {"name": "dataset_max_tickers_positive", "pass": int(dataset_cfg.get("max_tickers", 1) or 1) > 0},
        {"name": "dataset_max_rows_positive", "pass": int(dataset_cfg.get("max_rows", 1) or 1) > 0},
    ]
    fail = [c for c in checks if not bool(c.get("pass", False))]
    status = "PASS" if not fail else "FAIL"
    payload = {
        "generated_at": _utc_now(),
        "phase": str(phase),
        "status": status,
        "checks": checks,
        "config_shape": cfg_shape,
    }
    _write_json(output_dir / "preflight.json", payload)
    _write_json(
        output_dir / "phase_gate.json",
        {
            "generated_at": _utc_now(),
            "phase": str(phase),
            "status": status,
            "reason": "preflight_pass" if status == "PASS" else "preflight_failed",
            "checks": checks,
        },
    )
    return 0 if status == "PASS" else 2


def run_phase_basic(*, output_dir: Path, phase: str, results_glob: str) -> int:
    preflight = _safe_load_json(output_dir / "preflight.json")
    preflight_ok = str(preflight.get("status", "FAIL")).upper() == "PASS"
    results = [_metrics_from_result(p) for p in _result_paths(output_dir, pattern=results_glob)]
    windows_positive = [m for m in results if float(m.get("windows", 0.0)) > 0.0]
    status = "PASS" if (preflight_ok and windows_positive) else "FAIL"
    payload = {
        "generated_at": _utc_now(),
        "phase": str(phase),
        "status": status,
        "reason": "metrics_valid" if status == "PASS" else "insufficient_windows_or_preflight_failed",
        "result_count": int(len(results)),
        "window_positive_count": int(len(windows_positive)),
        "results": results,
    }
    _write_json(output_dir / "phase_gate.json", payload)
    return 0 if status == "PASS" else 2


def run_phase3_gate(*, output_dir: Path) -> int:
    preflight = _safe_load_json(output_dir / "preflight.json")
    preflight_ok = str(preflight.get("status", "FAIL")).upper() == "PASS"

    universe_sizes = [100, 150]
    universe_rows = []
    universe_exists = []
    for size in universe_sizes:
        p = output_dir / f"ex02_universe_{size}.json"
        universe_exists.append(bool(p.exists()))
        universe_rows.append({"size": size, **_metrics_from_result(p)})
    universe_files_present = bool(all(universe_exists))

    obs = [float(x.get("total_n_obs", 0.0)) for x in universe_rows]
    tk = [int(x.get("dataset_tickers", 0)) for x in universe_rows]
    non_identical = len(set(obs)) > 1 or len(set(tk)) > 1
    monotonic_n_obs = bool(all(obs[i] <= obs[i + 1] for i in range(len(obs) - 1)))
    monotonic_tickers = bool(all(tk[i] <= tk[i + 1] for i in range(len(tk) - 1)))

    pit_enabled = bool(universe_files_present and all(bool(x.get("pit_enabled", False)) for x in universe_rows))
    pit_no_leak = bool(universe_files_present and all(bool(x.get("pit_no_future_leak", False)) for x in universe_rows))

    oos_path = output_dir / "ex08_hard_oos_2020_2024.json"
    if not oos_path.exists():
        oos_path = output_dir / "ex09_hard_oos_2020_2024.json"
    oos_exists = bool(oos_path.exists())
    oos = _metrics_from_result(oos_path)
    oos_windows_ok = float(oos.get("windows", 0.0)) > 0.0
    oos_ic = float(oos.get("ic_mean", 0.0))
    oos_ic_non_degenerate = bool(np.isfinite(oos_ic) and abs(oos_ic) > 1e-8)

    checks = [
        {"name": "preflight_pass", "pass": preflight_ok},
        {"name": "universe_files_present", "pass": universe_files_present},
        {"name": "universe_non_identical", "pass": non_identical, "obs": obs, "dataset_tickers": tk},
        {"name": "universe_monotonic_n_obs", "pass": monotonic_n_obs, "obs": obs},
        {"name": "universe_monotonic_tickers", "pass": monotonic_tickers, "dataset_tickers": tk},
        {"name": "pit_enabled", "pass": pit_enabled},
        {"name": "pit_no_future_leak", "pass": pit_no_leak},
        {"name": "hard_oos_result_exists", "pass": oos_exists, "path": str(oos_path)},
        {"name": "oos_windows_valid", "pass": oos_windows_ok, "oos_windows": oos.get("windows", 0.0)},
        {"name": "oos_ic_non_degenerate", "pass": oos_ic_non_degenerate, "oos_ic_mean": oos_ic},
    ]
    status = "PASS" if all(bool(c.get("pass", False)) for c in checks) else "FAIL"
    payload = {
        "generated_at": _utc_now(),
        "phase": "phase3",
        "status": status,
        "checks": checks,
        "universe_metrics": universe_rows,
        "oos_metrics": oos,
    }
    # phase3_gate.json is written only by phase-3 evaluation.
    _write_json(output_dir / "phase3_gate.json", payload)
    _write_json(output_dir / "phase_gate.json", payload)
    return 0 if status == "PASS" else 2


def run_phase4_gate(*, output_dir: Path, phase3_gate_path: Path, results_glob: str) -> int:
    preflight = _safe_load_json(output_dir / "preflight.json")
    preflight_ok = str(preflight.get("status", "FAIL")).upper() == "PASS"
    phase3 = _safe_load_json(phase3_gate_path)
    phase3_ok = str(phase3.get("status", "FAIL")).upper() == "PASS"
    if not phase3_ok:
        payload = {
            "generated_at": _utc_now(),
            "phase": "phase4",
            "status": "BLOCKED",
            "reason": "blocked_by_phase3_gate",
            "phase3_gate_path": str(phase3_gate_path),
            "phase3_status": str(phase3.get("status", "missing")),
        }
        _write_json(output_dir / "phase_gate.json", payload)
        return 3

    results = [_metrics_from_result(p) for p in _result_paths(output_dir, pattern=results_glob)]
    windows_positive = [m for m in results if float(m.get("windows", 0.0)) > 0.0]
    status = "PASS" if (preflight_ok and windows_positive) else "FAIL"
    payload = {
        "generated_at": _utc_now(),
        "phase": "phase4",
        "status": status,
        "reason": "metrics_valid" if status == "PASS" else "insufficient_windows_or_preflight_failed",
        "phase3_gate_path": str(phase3_gate_path),
        "phase3_status": str(phase3.get("status", "missing")),
        "result_count": int(len(results)),
        "window_positive_count": int(len(windows_positive)),
    }
    _write_json(output_dir / "phase_gate.json", payload)
    return 0 if status == "PASS" else 2


def main() -> int:
    ap = argparse.ArgumentParser(description="Roadmap gate evaluator")
    ap.add_argument("--mode", required=True, choices=["preflight", "phase-basic", "phase3", "phase4"])
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--phase", default="phase")
    ap.add_argument("--base-config", default="config/research_policy.yaml")
    ap.add_argument("--results-glob", default="*.json")
    ap.add_argument("--phase3-gate-path", default="")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    output_dir = Path(args.output_dir).resolve()
    base_config = Path(args.base_config).resolve()

    if args.mode == "preflight":
        return run_preflight(repo_root=repo_root, base_config=base_config, output_dir=output_dir, phase=str(args.phase))
    if args.mode == "phase-basic":
        return run_phase_basic(output_dir=output_dir, phase=str(args.phase), results_glob=str(args.results_glob))
    if args.mode == "phase3":
        return run_phase3_gate(output_dir=output_dir)
    if args.mode == "phase4":
        p3 = Path(args.phase3_gate_path).resolve() if args.phase3_gate_path else (output_dir.parent / "phase3" / "phase3_gate.json")
        return run_phase4_gate(output_dir=output_dir, phase3_gate_path=p3, results_glob=str(args.results_glob))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
