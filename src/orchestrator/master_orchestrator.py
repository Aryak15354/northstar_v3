#!/usr/bin/env python3
"""Compatibility orchestrator for the current Northstar V3 runtime surface.

The old implementation tried to dynamically import several historical package
roots and then fell back to root-level scripts that no longer exist. This class
keeps the public MasterOrchestrator interface, but routes work through the
current, explicit V3 entrypoints under ``scripts/`` and ``src/``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class OrchestratorCommandResult:
    name: str
    status: str
    command: list[str]
    started_at: str
    finished_at: str
    duration_seconds: float
    returncode: int | None
    stdout_tail: str
    stderr_tail: str


class MasterOrchestrator:
    """Single compatibility facade for Northstar V3 operator workflows."""

    def __init__(self, verbose: bool = False) -> None:
        self.name = "Northstar V3 Master Orchestrator"
        self.version = "2.0"
        self.verbose = bool(verbose)
        self.execution_log: list[dict[str, Any]] = []
        self.subsystem_status: dict[str, bool] = {
            "data_pipeline": False,
            "system_orchestrator": False,
            "market_brain": False,
            "intelligence_coordinator": False,
            "portfolio_coordinator": False,
            "risk_coordinator": False,
            "state_manager": False,
            "dashboard": False,
        }
        self.log_dir = PROJECT_ROOT / "data" / "operations" / "master_orchestrator"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log_execution(self, subsystem: str, status: str, message: str = "", duration: float = 0.0) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "subsystem": subsystem,
            "status": status,
            "message": message,
            "duration_seconds": float(duration),
        }
        self.execution_log.append(entry)
        if subsystem in self.subsystem_status:
            self.subsystem_status[subsystem] = status == "success"
        if self.verbose:
            print(f"[{status.upper()}] {subsystem}: {message}")

    def _script_path(self, relative_path: str) -> Path:
        path = PROJECT_ROOT / relative_path
        if not path.exists():
            raise FileNotFoundError(f"Missing orchestrator target: {relative_path}")
        return path

    @staticmethod
    def _tail(text: str, max_lines: int = 20) -> str:
        lines = (text or "").splitlines()
        return "\n".join(lines[-max_lines:])

    def _run_command(
        self,
        *,
        name: str,
        subsystem: str,
        command: list[str],
        timeout_seconds: int | None = None,
    ) -> bool:
        started = datetime.now()
        if self.verbose:
            print(f"[RUN] {name}: {' '.join(command)}")
        try:
            completed = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            status = "success" if completed.returncode == 0 else "failed"
            stdout_tail = self._tail(completed.stdout)
            stderr_tail = self._tail(completed.stderr)
            returncode: int | None = completed.returncode
        except Exception as exc:
            status = "failed"
            stdout_tail = ""
            stderr_tail = f"{type(exc).__name__}: {exc}"
            returncode = None

        finished = datetime.now()
        result = OrchestratorCommandResult(
            name=name,
            status=status,
            command=command,
            started_at=started.isoformat(),
            finished_at=finished.isoformat(),
            duration_seconds=(finished - started).total_seconds(),
            returncode=returncode,
            stdout_tail=stdout_tail,
            stderr_tail=stderr_tail,
        )
        self.execution_log.append(asdict(result))
        if subsystem in self.subsystem_status:
            self.subsystem_status[subsystem] = status == "success"

        log_path = self.log_dir / f"{started.strftime('%Y%m%d_%H%M%S')}_{name.lower().replace(' ', '_')}.json"
        log_path.write_text(json.dumps(asdict(result), indent=2), encoding="utf-8")

        if self.verbose or status != "success":
            print(f"[{status.upper()}] {name} ({result.duration_seconds:.1f}s)")
            if stdout_tail:
                print(stdout_tail)
            if stderr_tail:
                print(stderr_tail)
        return status == "success"

    def _complete_runner_command(self, *, quick: bool, data_only: bool = False, proof_level: str = "standard") -> list[str]:
        self._script_path("scripts/run_complete_v3_system.py")
        command = [sys.executable, "scripts/run_complete_v3_system.py", "--proof-level", proof_level]
        if quick:
            command.append("--quick")
        if data_only:
            command.append("--data-only")
        return command

    def run_system_update(self, quick: bool = False) -> bool:
        """Run the current canonical V3 daily runner."""
        success = self._run_command(
            name="Complete V3 System",
            subsystem="system_orchestrator",
            command=self._complete_runner_command(quick=quick, proof_level="standard"),
            timeout_seconds=None,
        )
        if success:
            for subsystem in (
                "data_pipeline",
                "market_brain",
                "intelligence_coordinator",
                "portfolio_coordinator",
                "risk_coordinator",
                "state_manager",
            ):
                self.subsystem_status[subsystem] = True
        self.save_execution_log()
        return success

    def run_data_collection(self) -> bool:
        return self._run_command(
            name="Data Only Refresh",
            subsystem="data_pipeline",
            command=self._complete_runner_command(quick=True, data_only=True, proof_level="none"),
            timeout_seconds=None,
        )

    def run_data_processing(self) -> bool:
        self._script_path("scripts/run_morning_pipeline.py")
        return self._run_command(
            name="Morning Pipeline",
            subsystem="data_pipeline",
            command=[sys.executable, "scripts/run_morning_pipeline.py", "--date", "today"],
            timeout_seconds=3600,
        )

    def run_intelligence_generation(self) -> bool:
        return self._run_command(
            name="Intelligence Refresh",
            subsystem="intelligence_coordinator",
            command=self._complete_runner_command(quick=True, proof_level="none"),
            timeout_seconds=None,
        )

    def run_quick_intelligence_update(self) -> bool:
        return self.run_intelligence_generation()

    def run_portfolio_construction(self) -> bool:
        self._script_path("src/portfolio/portfolio_governor.py")
        return self._run_command(
            name="Portfolio Construction",
            subsystem="portfolio_coordinator",
            command=[sys.executable, "src/portfolio/portfolio_governor.py"],
            timeout_seconds=3600,
        )

    def run_risk_management(self) -> bool:
        """Run the current non-trading risk readiness gate."""
        self._script_path("scripts/preopen_checks.py")
        return self._run_command(
            name="Preopen Risk Checks",
            subsystem="risk_coordinator",
            command=[sys.executable, "scripts/preopen_checks.py"],
            timeout_seconds=1800,
        )

    def run_state_management(self) -> bool:
        try:
            from src.state.unified_state_manager import UnifiedStateManager

            manager = UnifiedStateManager()
            manager.update_all_state()
            self.log_execution("state_manager", "success", "Unified state manager updated all state")
            self.save_execution_log()
            return True
        except Exception as exc:
            self.log_execution("state_manager", "failed", f"{type(exc).__name__}: {exc}")
            self.save_execution_log()
            return False

    def run_dashboard(self, dashboard_type: str = "unified") -> bool:
        """Launch the canonical dashboard.

        Historical dashboard type names are accepted for compatibility, but all
        route to the canonical Streamlit app through scripts/launch_dashboard.sh.
        """
        _ = dashboard_type
        self._script_path("scripts/launch_dashboard.sh")
        return self._run_command(
            name="Dashboard",
            subsystem="dashboard",
            command=["bash", "scripts/launch_dashboard.sh"],
            timeout_seconds=None,
        )

    def run_live_trading(self) -> bool:
        """Live trading is intentionally gated behind pre-open checks."""
        return self.run_risk_management()

    def run_backtest(self, strategy: str | None = None) -> bool:
        command = [sys.executable, "src/backtesting/backtest_engine.py"]
        if strategy:
            command.extend(["--strategy", strategy])
        self._script_path("src/backtesting/backtest_engine.py")
        return self._run_command(
            name="Strategy Backtest",
            subsystem="system_orchestrator",
            command=command,
            timeout_seconds=10800,
        )

    def save_execution_log(self) -> None:
        summary = {
            "timestamp": datetime.now().isoformat(),
            "orchestrator_version": self.version,
            "subsystem_status": self.subsystem_status,
            "execution_log": self.execution_log,
            "success_rate": (
                sum(1 for status in self.subsystem_status.values() if status) / len(self.subsystem_status)
                if self.subsystem_status
                else 0.0
            ),
        }
        path = PROJECT_ROOT / "data" / "processed" / "master_orchestrator_log.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    def get_system_status(self) -> dict[str, Any]:
        targets = {
            "complete_runner": "scripts/run_complete_v3_system.py",
            "preopen_checks": "scripts/preopen_checks.py",
            "morning_pipeline": "scripts/run_morning_pipeline.py",
            "dashboard": "scripts/launch_dashboard.sh",
            "portfolio_governor": "src/portfolio/portfolio_governor.py",
            "state_manager": "src/state/unified_state_manager.py",
        }
        available = {name: (PROJECT_ROOT / rel_path).exists() for name, rel_path in targets.items()}
        return {
            "timestamp": datetime.now().isoformat(),
            "version": self.version,
            "subsystem_status": self.subsystem_status,
            "available_subsystems": available,
            "canonical_runner": str(PROJECT_ROOT / "scripts" / "run_complete_v3_system.py"),
        }


def main() -> int:
    orchestrator = MasterOrchestrator(verbose=True)
    status = orchestrator.get_system_status()
    print(json.dumps(status, indent=2))
    return 0 if all(status["available_subsystems"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
