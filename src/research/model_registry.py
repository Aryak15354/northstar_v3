"""Model registry with candidate/production/archive workflow and freeze gating."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class ModelRegistry:
    """File-backed local model registry."""

    def __init__(self, base_dir: Path | str = "data/model_registry") -> None:
        self.base_dir = Path(base_dir)
        self.candidates_dir = self.base_dir / "candidates"
        self.archived_dir = self.base_dir / "archived"
        self.registry_path = self.base_dir / "registry.json"
        self.production_path = self.base_dir / "production.json"
        self.promotion_log_path = self.base_dir / "promotion_log.json"
        self._ensure_layout()

    def _ensure_layout(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.candidates_dir.mkdir(parents=True, exist_ok=True)
        self.archived_dir.mkdir(parents=True, exist_ok=True)
        if not self.registry_path.exists():
            self._write_json(self.registry_path, {"models": []})
        if not self.production_path.exists():
            self._write_json(self.production_path, {})
        if not self.promotion_log_path.exists():
            self._write_json(self.promotion_log_path, [])

    def register_candidate(self, model_id: str, payload: Dict[str, Any]) -> Path:
        record = dict(payload)
        record.setdefault("model_id", model_id)
        record.setdefault("created_at", datetime.utcnow().isoformat())
        record["status"] = "candidate"
        target = self.candidates_dir / f"{model_id}.json"
        self._write_json(target, record)

        registry = self._read_json(self.registry_path, {"models": []})
        models = list(registry.get("models", []))
        models = [m for m in models if m.get("model_id") != model_id]
        models.append(
            {
                "model_id": model_id,
                "type": record.get("type", "generic"),
                "version": record.get("version"),
                "status": "candidate",
                "path": str(target.relative_to(self.base_dir)),
            }
        )
        registry["models"] = models
        self._write_json(self.registry_path, registry)
        return target

    def promote_candidate(
        self,
        model_id: str,
        *,
        freeze_active: bool,
        override: bool = False,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        if freeze_active and not override:
            return {
                "ok": False,
                "blocked": True,
                "reason": "freeze_active",
                "message": "Promotion blocked during freeze window. Use override with explicit reason.",
            }
        if freeze_active and override and not str(reason or "").strip():
            return {
                "ok": False,
                "blocked": True,
                "reason": "missing_override_reason",
                "message": "Override promotion during freeze requires a non-empty reason.",
            }

        candidate_path = self.candidates_dir / f"{model_id}.json"
        if not candidate_path.exists():
            return {"ok": False, "blocked": False, "reason": "candidate_not_found"}

        candidate = self._read_json(candidate_path, {})
        candidate["status"] = "production"
        candidate["promoted_at"] = datetime.utcnow().isoformat()

        prod = self._read_json(self.production_path, {})
        model_type = str(candidate.get("type", "generic"))
        previous_model_id = prod.get(model_type)
        if isinstance(previous_model_id, str) and previous_model_id and previous_model_id != model_id:
            self._archive_model(previous_model_id)
        prod[model_type] = model_id
        self._write_json(self.production_path, prod)

        registry = self._read_json(self.registry_path, {"models": []})
        for item in registry.get("models", []):
            if item.get("model_id") == model_id:
                item["status"] = "production"
        self._write_json(self.registry_path, registry)

        self._write_json(candidate_path, candidate)

        logs = self._read_json(self.promotion_log_path, [])
        logs.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "model_id": model_id,
                "freeze_active": bool(freeze_active),
                "override": bool(override),
                "reason": str(reason or "manual_promotion"),
            }
        )
        self._write_json(self.promotion_log_path, logs)
        return {"ok": True, "blocked": False, "model_id": model_id}

    def list_candidates(self) -> List[Dict[str, Any]]:
        registry = self._read_json(self.registry_path, {"models": []})
        return [m for m in registry.get("models", []) if m.get("status") == "candidate"]

    def _archive_model(self, model_id: str) -> None:
        candidate_path = self.candidates_dir / f"{model_id}.json"
        if not candidate_path.exists():
            return
        payload = self._read_json(candidate_path, {})
        payload["status"] = "archived"
        payload["archived_at"] = datetime.utcnow().isoformat()
        archived_path = self.archived_dir / f"{model_id}.json"
        self._write_json(archived_path, payload)
        try:
            candidate_path.unlink()
        except Exception:
            pass

        registry = self._read_json(self.registry_path, {"models": []})
        for item in registry.get("models", []):
            if item.get("model_id") == model_id:
                item["status"] = "archived"
                item["path"] = str(archived_path.relative_to(self.base_dir))
        self._write_json(self.registry_path, registry)

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        try:
            return json.loads(path.read_text())
        except Exception:
            return default

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(f"{path.suffix}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        tmp_path.replace(path)
