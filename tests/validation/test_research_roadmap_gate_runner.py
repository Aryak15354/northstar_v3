"""Roadmap runner gate tests (temp fixture paths only)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def _run_phase4(repo_root: Path, *, out_root: Path, phase3_gate_path: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["ROADMAP_OUT_ROOT"] = str(out_root)
    env["ROADMAP_PHASE3_GATE_PATH"] = str(phase3_gate_path)
    env["ROADMAP_SKIP_PREFLIGHT"] = "1"
    env["ROADMAP_SKIP_EXPERIMENTS"] = "1"
    return subprocess.run(
        [
            "bash",
            str(repo_root / "scripts/run_research_roadmap_phase4.sh"),
            str(repo_root / "config/research_policy.yaml"),
        ],
        cwd=str(repo_root),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_phase4_runner_exits_blocked_when_phase3_gate_not_pass(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    out_root = tmp_path / "roadmap"
    phase3_dir = out_root / "phase3"
    phase3_dir.mkdir(parents=True, exist_ok=True)
    phase3_gate = phase3_dir / "phase3_gate.json"
    phase3_gate.write_text(json.dumps({"status": "FAIL", "phase": "phase3"}))

    proc = _run_phase4(repo_root, out_root=out_root, phase3_gate_path=phase3_gate)

    assert proc.returncode == 3
    gate_path = out_root / "phase4" / "phase_gate.json"
    payload = json.loads(gate_path.read_text())
    assert str(payload.get("status")) == "BLOCKED"
    assert str(payload.get("reason")) == "blocked_by_phase3_gate"


def test_phase4_runner_executes_only_when_phase3_gate_pass(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    out_root = tmp_path / "roadmap"
    phase3_dir = out_root / "phase3"
    phase3_dir.mkdir(parents=True, exist_ok=True)
    phase3_gate = phase3_dir / "phase3_gate.json"
    phase3_gate.write_text(json.dumps({"status": "PASS", "phase": "phase3"}))

    phase4_dir = out_root / "phase4"
    phase4_dir.mkdir(parents=True, exist_ok=True)
    # Temp test fixture only; real runs write preflight from phase runner.
    (phase4_dir / "preflight.json").write_text(json.dumps({"status": "PASS", "phase": "phase4"}))
    (phase4_dir / "ex41_signal_combo_quality_momentum.json").write_text(
        json.dumps(
            {
                "aggregate_metrics": {"windows": 2, "ic_mean": 0.03, "total_n_obs": 4000},
                "dataset_tickers": 150,
                "data_integrity": {"pit_fundamentals_enabled": True, "pit_no_future_leak": True},
            }
        )
    )

    proc = _run_phase4(repo_root, out_root=out_root, phase3_gate_path=phase3_gate)

    assert proc.returncode == 0
    gate_path = out_root / "phase4" / "phase_gate.json"
    payload = json.loads(gate_path.read_text())
    assert str(payload.get("status")) == "PASS"
    assert str(payload.get("reason")) == "metrics_valid"
