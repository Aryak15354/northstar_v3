"""Structured JSON logger for Northstar V3 Kaggle experiments."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src.research.run_registry import RunRegistry, json_ready


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(json_ready(payload), indent=2), encoding="utf-8")
    tmp_path.replace(path)


class ExperimentLogger:
    """Persist structured experiment logs alongside summary artifacts."""

    def __init__(
        self,
        run_id: str,
        cfg: dict[str, Any],
        output_root: str | Path | None = None,
        registry: RunRegistry | None = None,
    ):
        self.run_id = str(run_id).strip()
        self.cfg = cfg
        self.registry = registry or RunRegistry(self.run_id, cfg=cfg, output_root=output_root)
        self.run_dir = self.registry.initialize(cfg)
        self.full_log_path = self.run_dir / "full_log.json"
        self.summary_path = self.run_dir / "summary.json"
        self.window_events_path = self.run_dir / "window_events.jsonl"
        self.start_time = time.time()
        logging_cfg = dict(cfg.get("logging") or {})
        self._flush_every_windows = max(1, int(logging_cfg.get("flush_every_windows", 1) or 1))
        self._save_window_details = bool(logging_cfg.get("save_window_details", True))
        self._pending_window_events = 0
        self._log: dict[str, Any] = {
            "run_id": self.run_id,
            "started_at": _utc_now_iso(),
            "config": json_ready(cfg),
            "days": {},
            "models": {},
            "regime_breakdown": {},
            "deployment": {},
            "artifacts": {},
            "verdict": None,
            "duration_minutes": None,
        }
        self._save()
        self.registry.register_artifact("run", "config_snapshot", self.run_dir / "config_snapshot.yaml")
        self.registry.register_artifact("run", "environment_manifest", self.run_dir / "environment_manifest.json")
        self.registry.register_artifact("run", "dataset_manifest", self.run_dir / "dataset_manifest.json")
        self.registry.register_artifact("run", "window_events", self.window_events_path)

    def snapshot_config(self, path_name: str = "merged_config.yaml") -> Path:
        path = self.run_dir / path_name
        path.write_text(yaml.safe_dump(self.cfg, sort_keys=False), encoding="utf-8")
        self.registry.register_artifact("run", path_name, path)
        return path

    def log_day(self, day_key: str, payload: dict[str, Any]) -> None:
        self._log["days"][str(day_key)] = json_ready(payload)
        self._save()

    def log_day1(
        self,
        ic_results: list[dict[str, Any]],
        decay_alerts: list[dict[str, Any]],
        gap9_factors: list[dict[str, Any]],
        feature_count: int,
    ) -> None:
        self.log_day(
            "day1",
            {
                "feature_count": int(feature_count),
                "top_20_by_abs_ic": sorted(ic_results, key=lambda row: abs(float(row.get("mean_ic", 0.0) or 0.0)), reverse=True)[:20],
                "decay_alerts": decay_alerts,
                "gap9_factors": gap9_factors,
            },
        )

    def log_window(
        self,
        window_num: int,
        model: str,
        train_ic: float,
        test_ic: float,
        ratio: float,
        hit_rate: float,
        regime: str | None = None,
    ) -> None:
        day2_windows = self._log["days"].setdefault("day2_windows", {})
        model_rows = day2_windows.setdefault(str(model), [])
        payload = {
            "window": int(window_num),
            "train_ic": round(float(train_ic), 6),
            "test_ic": round(float(test_ic), 6),
            "ratio": round(float(ratio), 4),
            "hit_rate": round(float(hit_rate), 4),
            "regime": regime,
        }
        model_rows.append(payload)
        with self.window_events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(json_ready({"model": str(model), **payload})) + "\n")
        self._pending_window_events += 1
        if self._save_window_details and self._pending_window_events >= self._flush_every_windows:
            self._save()
            self._pending_window_events = 0

    def log_model_summary(
        self,
        model: str,
        mean_ic: float,
        ic_ir: float,
        ratio: float,
        hit_rate: float,
        verdict: str,
        windows_completed: int = 20,
    ) -> None:
        self._log["models"][str(model)] = {
            "mean_ic": round(float(mean_ic), 6),
            "ic_ir": round(float(ic_ir), 4),
            "train_test_ratio": round(float(ratio), 4),
            "hit_rate": round(float(hit_rate), 4),
            "verdict": str(verdict),
            "windows_completed": int(windows_completed),
        }
        self._save()

    def log_regime_breakdown(
        self,
        model: str,
        regime_ic: dict[str, Any],
        excl_r7_r8_ic: float,
        excl_r7_r8_ir: float,
        excl_windows: int,
    ) -> None:
        self._log["regime_breakdown"][str(model)] = {
            "by_regime": json_ready(regime_ic),
            "excl_r7_r8": {
                "mean_ic": round(float(excl_r7_r8_ic), 6),
                "ic_ir": round(float(excl_r7_r8_ir), 4),
                "n_windows": int(excl_windows),
            },
        }
        self._save()

    def log_deployment(
        self,
        window_exposures: list[dict[str, Any]],
        mean_exposure: float,
        windows_above_20pct: int,
        windows_in_hold: int,
    ) -> None:
        self._log["deployment"] = {
            "window_detail": json_ready(window_exposures),
            "mean_exposure": round(float(mean_exposure), 4),
            "windows_above_20pct": int(windows_above_20pct),
            "windows_in_hold_5pct": int(windows_in_hold),
        }
        self._save()

    def log_artifact(self, name: str, path: str | Path, *, stage: str = "run", metadata: dict[str, Any] | None = None) -> None:
        self._log.setdefault("artifacts", {})[str(name)] = {
            "path": str(Path(path).expanduser().resolve()),
            "stage": stage,
            "metadata": json_ready(metadata or {}),
        }
        self.registry.register_artifact(stage, name, path, metadata=metadata)
        self._save()

    def finalize(self, verdict: str, best_model: str, notes: str = "") -> dict[str, Any]:
        if self._pending_window_events:
            self._save()
            self._pending_window_events = 0
        self._log["verdict"] = str(verdict)
        self._log["best_model"] = str(best_model)
        self._log["notes"] = str(notes)
        self._log["duration_minutes"] = round((time.time() - self.start_time) / 60.0, 1)
        self._log["finished_at"] = _utc_now_iso()
        self._save()
        summary = {
            "run_id": self.run_id,
            "verdict": verdict,
            "best_model": best_model,
            "catboost": self._log["models"].get("catboost", {}),
            "xgboost": self._log["models"].get("xgboost", {}),
            "lightgbm": self._log["models"].get("lightgbm", {}),
            "mean_exposure": self._log.get("deployment", {}).get("mean_exposure"),
            "windows_above_20pct": self._log.get("deployment", {}).get("windows_above_20pct"),
            "windows_in_hold_5pct": self._log.get("deployment", {}).get("windows_in_hold_5pct"),
            "excl_r7_r8_ir": self._log.get("regime_breakdown", {}).get(best_model, {}).get("excl_r7_r8", {}).get("ic_ir"),
            "duration_minutes": self._log["duration_minutes"],
            "reference_bundle": self.cfg.get("_reference_bundle", {}),
            "regime_config_version": self.cfg.get("_regime_validation", {}).get("version"),
            "summary_generated_at": _utc_now_iso(),
        }
        _atomic_write_json(self.summary_path, summary)
        self.registry.register_artifact("run", "summary", self.summary_path)
        return summary

    def _save(self) -> None:
        _atomic_write_json(self.full_log_path, self._log)


__all__ = ["ExperimentLogger"]
