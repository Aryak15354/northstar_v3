"""
Runtime state tamper guard.

Provides a checksum sidecar for options_runtime_state.json so accidental/manual
edits outside controlled writers are detectable by governance/recovery checks.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def runtime_signature_path(runtime_path: Path) -> Path:
    return runtime_path.with_suffix(f"{runtime_path.suffix}.sha256")


def compute_file_sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def write_runtime_signature(runtime_path: Path) -> bool:
    try:
        if not runtime_path.exists():
            return False
        payload = {
            "timestamp": datetime.now().isoformat(),
            "file": str(runtime_path),
            "sha256": compute_file_sha256(runtime_path),
        }
        sig_path = runtime_signature_path(runtime_path)
        sig_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = sig_path.with_suffix(f"{sig_path.suffix}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        tmp_path.replace(sig_path)
        try:
            dir_fd = os.open(str(sig_path.parent), os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except Exception:
            pass
        return True
    except Exception:
        return False


def verify_runtime_signature(runtime_path: Path) -> Dict[str, Any]:
    sig_path = runtime_signature_path(runtime_path)
    report: Dict[str, Any] = {
        "status": "unknown",
        "runtime_exists": bool(runtime_path.exists()),
        "signature_exists": bool(sig_path.exists()),
        "expected_sha256": None,
        "actual_sha256": None,
        "valid": False,
    }

    if not runtime_path.exists():
        report["status"] = "runtime_missing"
        return report

    if not sig_path.exists():
        report["status"] = "signature_missing"
        return report

    try:
        # Runtime JSON and signature sidecar are written as two sequential atomic writes.
        # During that narrow window, runtime may be newer than signature momentarily.
        max_attempts = 4
        retry_sleep_seconds = 0.15
        for attempt in range(1, max_attempts + 1):
            payload = json.loads(sig_path.read_text())
            expected = str(payload.get("sha256") or "").strip().lower()
            actual = compute_file_sha256(runtime_path).lower()
            report["expected_sha256"] = expected
            report["actual_sha256"] = actual
            report["attempts"] = attempt

            if expected and expected == actual:
                report["status"] = "valid"
                report["valid"] = True
                return report

            try:
                runtime_mtime = float(runtime_path.stat().st_mtime)
                sig_mtime = float(sig_path.stat().st_mtime)
                report["runtime_mtime"] = runtime_mtime
                report["signature_mtime"] = sig_mtime
                # Retry only for likely transient write ordering race.
                if runtime_mtime > sig_mtime and (runtime_mtime - sig_mtime) <= 3.0 and attempt < max_attempts:
                    time.sleep(retry_sleep_seconds)
                    continue
            except Exception:
                pass

            report["status"] = "mismatch"
            report["valid"] = False
            return report

        report["status"] = "mismatch"
        report["valid"] = False
        return report
    except Exception as exc:
        report["status"] = "signature_error"
        report["error"] = str(exc)
        return report
