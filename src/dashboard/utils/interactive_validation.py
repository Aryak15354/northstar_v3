#!/usr/bin/env python3
"""
Interactive validation helper.
Persists user-triggered stress/walk-forward requests without synthetic results.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import json


class InteractiveValidationSystem:
    def __init__(self):
        self.results_dir = Path("data/dashboard/validation")
        self.results_dir.mkdir(parents=True, exist_ok=True)

        self.stress_tests_file = self.results_dir / "stress_test_results.json"
        self.walkforward_file = self.results_dir / "walkforward_results.json"
        self._initialize_sample_data()

    def _initialize_sample_data(self) -> None:
        if not self.stress_tests_file.exists():
            self.stress_tests_file.write_text(json.dumps({"tests": []}, indent=2))
        if not self.walkforward_file.exists():
            self.walkforward_file.write_text(json.dumps({"tests": []}, indent=2))

    def _load_json(self, path: Path) -> Dict[str, Any]:
        try:
            return json.loads(path.read_text())
        except Exception:
            return {"tests": []}

    def _save_json(self, path: Path, payload: Dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, indent=2, default=str))

    def run_stress_test(self, name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._load_json(self.stress_tests_file)
        tests = payload.get("tests") or []
        record = {
            "id": f"stress_{int(datetime.now().timestamp())}",
            "name": name,
            "parameters": parameters,
            "status": "queued",
            "created_at": datetime.now().isoformat(),
            "source": "interactive_validation",
        }
        tests.append(record)
        payload["tests"] = tests
        self._save_json(self.stress_tests_file, payload)
        return record

    def run_walkforward_validation(self, name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._load_json(self.walkforward_file)
        tests = payload.get("tests") or []
        record = {
            "id": f"wf_{int(datetime.now().timestamp())}",
            "name": name,
            "parameters": parameters,
            "status": "queued",
            "created_at": datetime.now().isoformat(),
            "source": "interactive_validation",
        }
        tests.append(record)
        payload["tests"] = tests
        self._save_json(self.walkforward_file, payload)
        return record

    def load_stress_tests(self) -> Dict[str, Any]:
        return self._load_json(self.stress_tests_file)

    def load_walkforward_tests(self) -> Dict[str, Any]:
        return self._load_json(self.walkforward_file)

    def compare_results(self, test_ids: List[str], test_type: str = "stress") -> Dict[str, Any]:
        data = self.load_stress_tests() if test_type == "stress" else self.load_walkforward_tests()
        tests = data.get("tests") or []
        selected = [t for t in tests if str(t.get("id")) in set(test_ids)]
        return {
            "test_type": test_type,
            "selected_count": len(selected),
            "tests": selected,
        }
