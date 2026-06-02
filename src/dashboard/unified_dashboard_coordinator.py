#!/usr/bin/env python3
"""
🖥️ UNIFIED DASHBOARD COORDINATOR - NORTHSTAR V3
Master Dashboard System with Unified Interface

This coordinator launches one of the dashboard entry points and logs
interface activity. It does not compute data; it only launches.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict


class UnifiedDashboardCoordinator:
    """Orchestrates dashboard launch and logging."""

    def __init__(self) -> None:
        self.name = "Unified Dashboard Coordinator"
        self.version = "1.0"

        self.paths: Dict[str, str] = {
            "dashboard_snapshot": "data/processed/cache/dashboard_snapshot.parquet",
            "unified_state": "data/state/unified_state.json",
            "dashboard_config": "data/dashboard/unified_config.json",
            "interface_log": "data/dashboard/interface_coordination_log.json",
        }

        os.makedirs("data/dashboard", exist_ok=True)
        os.makedirs("data/processed/cache", exist_ok=True)

        self.dashboard_types = {
            "unified": {
                "name": "Unified Terminal",
                "description": "War Room + Portfolio + Intelligence",
                "file": "scripts/northstar_unified_terminal.py",
            },
            "professional": {
                "name": "Professional Trading Desk",
                "description": "Bloomberg-style professional interface",
                "file": "scripts/northstar_professional.py",
            },
            "trading-desk": {
                "name": "Trading Desk",
                "description": "Institutional trading desk interface",
                "file": "scripts/northstar_trading_desk.py",
            },
            "intelligence": {
                "name": "Intelligence Organism",
                "description": "AI brain visualization and analysis",
                "file": "scripts/northstar_intelligence_organism.py",
            },
            "react": {
                "name": "Production Dashboard",
                "description": "Canonical Streamlit production dashboard",
                "file": "src/dashboard/app.py",
            },
        }

        self.interface_log = []

    def log_interface_action(self, interface: str, action: str, status: str, message: str = "", duration: float = 0.0) -> None:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "interface": interface,
            "action": action,
            "status": status,
            "message": message,
            "duration_seconds": duration,
        }
        self.interface_log.append(entry)

        status_icon = "✅" if status == "success" else "❌" if status == "failed" else "⚠️"
        print(f"   {status_icon} {interface}: {message}")

        try:
            with open(self.paths["interface_log"], "w") as f:
                json.dump(self.interface_log, f, indent=2)
        except Exception:
            pass

    def launch_unified_interface(self, dashboard_type: str = "unified") -> bool:
        info = self.dashboard_types.get(dashboard_type)
        if not info:
            self.log_interface_action(dashboard_type, "launch", "failed", "Unknown dashboard type")
            return False

        dashboard_file = info["file"]
        if not Path(dashboard_file).exists():
            self.log_interface_action(dashboard_type, "launch", "failed", f"Missing {dashboard_file}")
            return False

        try:
            subprocess.run([sys.executable, dashboard_file], check=False)
            self.log_interface_action(dashboard_type, "launch", "success", info["name"])
            return True
        except Exception as e:
            self.log_interface_action(dashboard_type, "launch", "failed", str(e))
            return False
