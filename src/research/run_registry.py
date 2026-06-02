"""Run registry and artifact bookkeeping for Kaggle experiments."""

from __future__ import annotations

import json
import os
import platform
import socket
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_ready(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): json_ready(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_ready(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    try:
        import numpy as np
        import pandas as pd

        if isinstance(obj, np.ndarray):
            return [json_ready(value) for value in obj.tolist()]
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            value = float(obj)
            return None if not np.isfinite(value) else value
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        if isinstance(obj, pd.Series):
            return {str(k): json_ready(v) for k, v in obj.to_dict().items()}
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict(orient="records")
    except Exception:
        pass
    if isinstance(obj, float):
        return None if obj != obj or obj in {float("inf"), float("-inf")} else obj
    return obj


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _atomic_write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(payload, encoding="utf-8")
    tmp_path.replace(path)


@dataclass
class StageStatus:
    stage: str
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    returncode: int | None = None
    error: str | None = None


class RunRegistry:
    """Create run directories, manifests, and stage status files."""

    def __init__(self, run_id: str, cfg: dict[str, Any] | None = None, output_root: str | Path | None = None):
        self.run_id = str(run_id).strip()
        if not self.run_id:
            raise ValueError("run_id is required")
        self.cfg = cfg or {}
        self.output_root = Path(output_root or self.default_output_root(self.cfg)).expanduser().resolve()
        self.run_dir = self.output_root / self.run_id
        self.manifest_path = self.run_dir / "run_manifest.json"
        self.stage_status_path = self.run_dir / "stage_status.json"
        self.dataset_manifest_path = self.run_dir / "dataset_manifest.json"
        self.environment_manifest_path = self.run_dir / "environment_manifest.json"

    @staticmethod
    def default_output_root(cfg: dict[str, Any] | None = None) -> Path:
        config = cfg or {}
        logging_cfg = dict(config.get("logging") or {})
        if Path("/kaggle").exists():
            return Path(logging_cfg.get("output_dir", "/kaggle/working/runs"))
        return PROJECT_ROOT / str(logging_cfg.get("local_output_dir", "runs"))

    def ensure_run_dir(self) -> Path:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        return self.run_dir

    def stage_output_dir(self, stage_name: str) -> Path:
        stage_dir = self.ensure_run_dir() / stage_name
        stage_dir.mkdir(parents=True, exist_ok=True)
        return stage_dir

    def write_config_snapshot(self, cfg: dict[str, Any]) -> Path:
        path = self.ensure_run_dir() / "config_snapshot.yaml"
        path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
        return path

    def write_environment_manifest(self) -> Path:
        payload = {
            "generated_at": utc_now_iso(),
            "cwd": str(Path.cwd()),
            "platform": platform.platform(),
            "python_version": sys.version,
            "hostname": socket.gethostname(),
            "pid": os.getpid(),
            "is_kaggle": Path("/kaggle").exists(),
        }
        _atomic_write_text(self.environment_manifest_path, json.dumps(json_ready(payload), indent=2))
        return self.environment_manifest_path

    def write_dataset_manifest(self, payload: dict[str, Any] | None = None) -> Path:
        manifest = dict(payload or {})
        _atomic_write_text(self.dataset_manifest_path, json.dumps(json_ready(manifest), indent=2))
        return self.dataset_manifest_path

    def write_run_manifest(self, payload: dict[str, Any] | None = None) -> Path:
        existing = _read_json(self.manifest_path, {})
        merged = dict(existing)
        merged.update(json_ready(payload or {}))
        merged.setdefault("run_id", self.run_id)
        merged.setdefault("created_at", utc_now_iso())
        _atomic_write_text(self.manifest_path, json.dumps(merged, indent=2))
        return self.manifest_path

    def initialize(self, cfg: dict[str, Any]) -> Path:
        self.ensure_run_dir()
        self.write_config_snapshot(cfg)
        self.write_environment_manifest()
        self.write_dataset_manifest(
            {
                "datasets": json_ready(cfg.get("datasets", {})),
                "data": json_ready(cfg.get("data", {})),
                "reference_bundle": json_ready(cfg.get("_reference_bundle", {})),
            }
        )
        self.write_run_manifest(
            {
                "run_id": self.run_id,
                "experiment": json_ready(cfg.get("experiment", {})),
                "config_paths": json_ready(cfg.get("_config_paths", {})),
                "regime_config_version": str(cfg.get("_regime_validation", {}).get("version", "") or ""),
                "reference_bundle": json_ready(cfg.get("_reference_bundle", {})),
            }
        )
        if not self.stage_status_path.exists():
            _atomic_write_text(
                self.stage_status_path,
                json.dumps({"run_id": self.run_id, "stages": {}, "artifacts": {}}, indent=2),
            )
        reference_manifest_raw = str((cfg.get("_reference_bundle") or {}).get("manifest_path", "") or "").strip()
        reference_manifest = Path(reference_manifest_raw).expanduser() if reference_manifest_raw else None
        if reference_manifest is not None and reference_manifest.exists():
            self.register_artifact("run", "reference_manifest", reference_manifest)
        return self.run_dir

    def _load_stage_status(self) -> dict[str, Any]:
        return _read_json(self.stage_status_path, {"run_id": self.run_id, "stages": {}, "artifacts": {}})

    def _write_stage_status(self, payload: dict[str, Any]) -> None:
        _atomic_write_text(self.stage_status_path, json.dumps(json_ready(payload), indent=2))

    def mark_stage_started(self, stage_name: str, *, command: list[str] | None = None, metadata: dict[str, Any] | None = None) -> None:
        payload = self._load_stage_status()
        payload.setdefault("stages", {})
        payload["stages"][stage_name] = {
            "status": "running",
            "started_at": utc_now_iso(),
            "finished_at": None,
            "command": command or [],
            "metadata": json_ready(metadata or {}),
        }
        self._write_stage_status(payload)

    def mark_stage_completed(self, stage_name: str, *, metadata: dict[str, Any] | None = None) -> None:
        payload = self._load_stage_status()
        stage = dict(payload.setdefault("stages", {}).get(stage_name) or {})
        stage.update(
            {
                "status": "completed",
                "finished_at": utc_now_iso(),
                "metadata": json_ready({**dict(stage.get("metadata") or {}), **dict(metadata or {})}),
            }
        )
        payload["stages"][stage_name] = stage
        self._write_stage_status(payload)

    def mark_stage_failed(
        self,
        stage_name: str,
        *,
        error: str,
        returncode: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = self._load_stage_status()
        stage = dict(payload.setdefault("stages", {}).get(stage_name) or {})
        stage.update(
            {
                "status": "failed",
                "finished_at": utc_now_iso(),
                "returncode": returncode,
                "error": error,
                "metadata": json_ready({**dict(stage.get("metadata") or {}), **dict(metadata or {})}),
            }
        )
        payload["stages"][stage_name] = stage
        self._write_stage_status(payload)

    def register_artifact(self, stage_name: str, artifact_name: str, path: str | Path, metadata: dict[str, Any] | None = None) -> None:
        payload = self._load_stage_status()
        payload.setdefault("artifacts", {})
        payload["artifacts"].setdefault(stage_name, {})
        payload["artifacts"][stage_name][artifact_name] = {
            "path": str(Path(path).expanduser().resolve()),
            "metadata": json_ready(metadata or {}),
        }
        self._write_stage_status(payload)


__all__ = ["RunRegistry", "utc_now_iso", "json_ready"]
