#!/usr/bin/env python3
"""Background research worker for Northstar daemon."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _default_cpu_cap() -> int:
    cores = max(1, int(os.cpu_count() or 2))
    # Keep a conservative default for long-running laptop workloads.
    return max(1, min(2, cores // 2))


def _host_memory_gb() -> float:
    try:
        import psutil  # type: ignore

        return float(psutil.virtual_memory().total / (1024 ** 3))
    except Exception:
        return 0.0


# Keep worker resource usage predictable on a single laptop daemon host.
os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(_default_cpu_cap()))
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("TORCH_NUM_THREADS", "1")
os.environ.setdefault("TORCH_NUM_INTEROP_THREADS", "1")

# Auto-enable low-resource profile on smaller hosts unless explicitly overridden.
_MEM_GB = _host_memory_gb()
if _MEM_GB and _MEM_GB <= 10.5:
    os.environ.setdefault("NORTHSTAR_LOW_RESOURCE_PROFILE", "1")
    # Keep laptop UX responsive by default; can be set to 0 to re-enable MPS.
    os.environ.setdefault("NORTHSTAR_DISABLE_MPS", "1")

from src.research.research_engine import ResearchEngine

LOGGER = logging.getLogger("northstar.research_worker")


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            payload = json.loads(path.read_text())
            if isinstance(payload, dict):
                return payload
    except Exception:
        pass
    return {}


def _write_heartbeat(path: Path, *, status: str = "alive", phase: str = "idle") -> None:
    payload = {
        "timestamp": datetime.now().isoformat(),
        "pid": int(os.getpid()) if hasattr(os, "getpid") else None,
        "status": str(status),
        "phase": str(phase),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def _bar(current: int, total: int, width: int = 24) -> str:
    total = max(1, int(total))
    current = max(0, min(int(current), total))
    frac = float(current) / float(total)
    filled = int(round(width * frac))
    return f"[{'#' * filled}{'.' * (width - filled)}] {int(frac * 100):3d}%"


def _summarize_cycle(result: Dict[str, Any], started_at: datetime) -> None:
    duration = (datetime.now() - started_at).total_seconds()
    outputs = result.get("outputs_generated", []) if isinstance(result, dict) else []
    actionable = result.get("actionable_outputs", []) if isinstance(result, dict) else []
    errors = result.get("errors", []) if isinstance(result, dict) else []
    modules = result.get("modules_run", []) if isinstance(result, dict) else []
    skipped = bool(result.get("skipped", False)) if isinstance(result, dict) else False

    promotion = None
    awareness = None
    for out in outputs:
        if not isinstance(out, dict):
            continue
        otype = str(out.get("type", "")).strip().lower()
        if otype == "model_promotion":
            promotion = out.get("data", {})
        elif otype == "research_self_awareness":
            awareness = out.get("data", {})

    best_model = None
    candidate_score = None
    if isinstance(promotion, dict):
        best_model = promotion.get("best_model")
        score = promotion.get("score", {})
        if isinstance(score, dict):
            candidate_score = score.get("candidate_score")

    LOGGER.info(
        "Cycle Summary %s duration=%.1fs skipped=%s modules=%s outputs=%d actionable=%d errors=%d",
        _bar(1 if not skipped else 0, 1),
        duration,
        skipped,
        modules,
        len(outputs),
        len(actionable),
        len(errors),
    )
    if skipped and isinstance(result, dict):
        LOGGER.info("Cycle Skip Reason: %s", str(result.get("skip_reason", "unspecified")))
    if best_model is not None:
        LOGGER.info(
            "Cycle Decision: best_model=%s candidate_score=%s",
            str(best_model),
            f"{float(candidate_score):.4f}" if candidate_score is not None else "n/a",
        )
    if isinstance(awareness, dict):
        LOGGER.info(
            "Research Awareness: accepted_rate=%s adaptive_mutation_rate=%s",
            str(awareness.get("acceptance_rate", "n/a")),
            str(awareness.get("adaptive_mutation_rate", "n/a")),
        )
    if errors:
        LOGGER.warning("Cycle Errors: %s", errors)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Northstar research worker")
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config/research_policy.yaml")
    parser.add_argument("--interval-seconds", type=int, default=1800)
    parser.add_argument("--once", action="store_true")
    parser.add_argument(
        "--manual-run",
        action="store_true",
        help="Mark the cycle as operator-triggered so research can run even when scheduled burn-in gating is active.",
    )
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    LOGGER.info(
        "Research worker CPU caps: LOKY_MAX_CPU_COUNT=%s OMP=%s OPENBLAS=%s MKL=%s",
        os.getenv("LOKY_MAX_CPU_COUNT", "n/a"),
        os.getenv("OMP_NUM_THREADS", "n/a"),
        os.getenv("OPENBLAS_NUM_THREADS", "n/a"),
        os.getenv("MKL_NUM_THREADS", "n/a"),
    )
    LOGGER.info(
        "Research worker profile: low_resource=%s disable_mps=%s host_mem_gb=%.2f",
        os.getenv("NORTHSTAR_LOW_RESOURCE_PROFILE", "0"),
        os.getenv("NORTHSTAR_DISABLE_MPS", "0"),
        _MEM_GB,
    )

    engine = ResearchEngine(config_path=args.config)
    runtime_path = PROJECT_ROOT / "data/options/live/options_runtime_state.json"
    market_data_path = PROJECT_ROOT / "data/options/live/market_data_latest.json"
    hb_path = PROJECT_ROOT / "data/results/research/state/research_worker_heartbeat.json"
    cycle = 0

    while True:
        cycle += 1
        cycle_started = datetime.now()
        LOGGER.info(
            "Research Cycle Start %s cycle=%d config=%s",
            _bar(0, 1),
            cycle,
            str(args.config),
        )
        _write_heartbeat(hb_path, status="alive", phase="cycle_start")
        market_data = _load_json(market_data_path)
        system_state = _load_json(runtime_path)
        if args.manual_run:
            system_state = dict(system_state)
            system_state["manual_run"] = True
            system_state["trigger_source"] = "cli"
        try:
            result = engine.run_research_cycle(market_data=market_data, system_state=system_state)
        except Exception as exc:
            LOGGER.error("Research cycle crashed: %s", exc, exc_info=True)
            result = {"modules_run": [], "errors": [str(exc)], "skipped": False}
        _summarize_cycle(result=result, started_at=cycle_started)
        _write_heartbeat(hb_path, status="alive", phase="cycle_complete")

        if args.once:
            return 0
        time.sleep(max(30, int(args.interval_seconds)))


if __name__ == "__main__":
    raise SystemExit(main())
