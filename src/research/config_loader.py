"""Config loader for Northstar V3 Kaggle experiments."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from src.research.reference_data import resolve_reference_root, summarize_reference_bundle


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = PROJECT_ROOT / "configs"


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"config_not_found:{path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise TypeError(f"config_must_be_mapping:{path}")
    return payload


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override into base. Override wins on conflict."""

    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def resolve_config_root(config_root: str | Path | None = None) -> Path:
    return Path(config_root or CONFIG_ROOT).expanduser().resolve()


def resolve_experiment_path(run_id: str, config_root: str | Path | None = None) -> Path:
    root = resolve_config_root(config_root)
    run_token = str(run_id).strip()
    if not run_token:
        raise ValueError("run_id is required")
    direct = Path(run_token).expanduser()
    if direct.suffix in {".yaml", ".yml"} and direct.exists():
        return direct.resolve()
    return (root / "experiments" / f"{run_token}.yaml").resolve()


def _resolve_regime_config_path(cfg: dict[str, Any], root: Path) -> Path:
    requested = str(cfg.get("regime_config_version", "") or "").strip()
    candidates: list[Path] = []
    if requested:
        candidates.extend(
            [
                root / f"regime_config_{requested}.yaml",
                root / f"regime_config_{requested}.yml",
                root / "regimes" / f"{requested}.yaml",
                root / "regimes" / f"{requested}.yml",
            ]
        )
    candidates.extend(
        [
            root / "regime_config.yaml",
            root / "regime_config.yml",
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"regime_config_not_found:{requested or 'default'} under {root}")


def _hydrate_model_configs(cfg: dict[str, Any], root: Path) -> None:
    models = cfg.setdefault("models", {})
    refs = dict(models.get("config_refs") or {})
    for model_name, rel_path in refs.items():
        path = (root / str(rel_path)).resolve()
        payload = _read_yaml(path)
        params = payload.get("params", payload)
        if not isinstance(params, dict):
            raise TypeError(f"model_config_params_must_be_mapping:{path}")
        existing = models.get(model_name, {})
        if existing is None:
            existing = {}
        if not isinstance(existing, dict):
            raise TypeError(f"models.{model_name} must be a mapping")
        models[model_name] = _deep_merge(params, existing)


def _hydrate_feature_sets(cfg: dict[str, Any], root: Path) -> None:
    features_cfg = cfg.setdefault("features", {})
    mode = str(features_cfg.get("mode", "full") or "full").strip().lower()
    set_paths = dict(features_cfg.get("set_paths") or {})
    selected_path: Path | None = None

    if mode == "custom" and features_cfg.get("custom_set"):
        selected_path = (root / str(features_cfg["custom_set"])).resolve()
    elif mode in set_paths:
        selected_path = (root / str(set_paths[mode])).resolve()

    if selected_path is not None and selected_path.exists():
        payload = _read_yaml(selected_path)
        features_cfg["_resolved_set_path"] = str(selected_path)
        if "features" in payload and "selected_features" not in features_cfg:
            features_cfg["selected_features"] = list(payload.get("features") or [])
        if "force_include" in payload:
            merged_force_include = list(
                dict.fromkeys([*(features_cfg.get("force_include") or []), *(payload.get("force_include") or [])])
            )
            features_cfg["force_include"] = merged_force_include


def _validate_regime_config(cfg: dict[str, Any]) -> None:
    regime = cfg.get("regime", {})
    validation = regime.get("validation", {})
    cfg["_regime_validation"] = {
        "max_r7_r8_windows": int(validation.get("max_r7_r8_windows", 6) or 6),
        "warn_threshold": int(validation.get("warn_if_r7_r8_exceeds", 4) or 4),
        "version": str(regime.get("version", "") or ""),
    }


def _hydrate_reference_bundle(cfg: dict[str, Any]) -> None:
    reference_cfg = cfg.setdefault("reference", {})
    reference_root = resolve_reference_root(cfg=cfg, required=False)
    bundle = summarize_reference_bundle(reference_root)
    if reference_root is not None:
        reference_cfg.setdefault("canonical_root", str(reference_root))
    if bundle.get("manifest_path"):
        reference_cfg.setdefault("research_inputs_manifest", str(bundle["manifest_path"]))
    cfg["_reference_bundle"] = bundle


def load_experiment_config(run_id: str, config_root: str | Path | None = None) -> dict[str, Any]:
    """
    Load merged config for a given run id.

    Merge order:
    1. experiment_base.yaml
    2. experiments/{run_id}.yaml
    3. model config references
    4. regime config attachment
    """

    root = resolve_config_root(config_root)
    base_path = root / "experiment_base.yaml"
    run_path = resolve_experiment_path(run_id, root)

    cfg = _read_yaml(base_path)
    run_override = _read_yaml(run_path)
    cfg = _deep_merge(cfg, run_override)
    cfg["_config_paths"] = {
        "config_root": str(root),
        "base": str(base_path),
        "experiment": str(run_path),
    }

    _hydrate_model_configs(cfg, root)
    _hydrate_feature_sets(cfg, root)
    _hydrate_reference_bundle(cfg)

    regime_path = _resolve_regime_config_path(cfg, root)
    cfg["regime"] = _read_yaml(regime_path)
    cfg["_config_paths"]["regime"] = str(regime_path)
    if cfg.get("_reference_bundle", {}).get("reference_root"):
        cfg["_config_paths"]["reference_root"] = str(cfg["_reference_bundle"]["reference_root"])
    _validate_regime_config(cfg)
    return cfg


__all__ = [
    "CONFIG_ROOT",
    "PROJECT_ROOT",
    "load_experiment_config",
    "resolve_config_root",
    "resolve_experiment_path",
]
