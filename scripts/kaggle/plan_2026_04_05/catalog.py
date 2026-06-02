"""Catalog loader for the compendium-aligned experiment plan."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = PROJECT_ROOT / "configs" / "plan_2026_04_05" / "catalog_v1.yaml"


@dataclass(frozen=True)
class PlanInfo:
    plan_id: str
    version: str
    source_doc: str
    master_notebook: str
    dataset_contract: dict[str, Any] = field(default_factory=dict)
    anchor_factors: tuple[str, ...] = ()
    cross_asset_signals: tuple[str, ...] = ()
    sector_conditional_features: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExperimentSpec:
    exp_id: str
    title: str
    family: str
    priority: int
    dependencies: tuple[str, ...]
    hypothesis: str
    outputs: tuple[str, ...]
    params: dict[str, Any] = field(default_factory=dict)


def _load_yaml() -> dict[str, Any]:
    payload = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise TypeError(f"invalid_catalog_payload:{CATALOG_PATH}")
    return payload


def load_plan_info() -> PlanInfo:
    payload = _load_yaml()
    plan = dict(payload.get("plan") or {})
    return PlanInfo(
        plan_id=str(plan.get("plan_id") or ""),
        version=str(plan.get("version") or "v1"),
        source_doc=str(plan.get("source_doc") or ""),
        master_notebook=str(plan.get("master_notebook") or ""),
        dataset_contract=dict(plan.get("dataset_contract") or {}),
        anchor_factors=tuple(str(value) for value in list(plan.get("anchor_factors") or [])),
        cross_asset_signals=tuple(str(value) for value in list(plan.get("cross_asset_signals") or [])),
        sector_conditional_features=tuple(str(value) for value in list(plan.get("sector_conditional_features") or [])),
    )


def load_experiment_catalog() -> dict[str, ExperimentSpec]:
    payload = _load_yaml()
    experiments = dict(payload.get("experiments") or {})
    catalog: dict[str, ExperimentSpec] = {}
    for exp_id, raw in experiments.items():
        data = dict(raw or {})
        catalog[str(exp_id)] = ExperimentSpec(
            exp_id=str(exp_id),
            title=str(data.get("title") or ""),
            family=str(data.get("family") or ""),
            priority=int(data.get("priority") or 0),
            dependencies=tuple(str(value) for value in list(data.get("dependencies") or [])),
            hypothesis=str(data.get("hypothesis") or ""),
            outputs=tuple(str(value) for value in list(data.get("outputs") or [])),
            params=dict(data.get("params") or {}),
        )
    return dict(sorted(catalog.items(), key=lambda item: (item[1].priority, item[0])))


def get_experiment_spec(exp_id: str) -> ExperimentSpec:
    catalog = load_experiment_catalog()
    if exp_id not in catalog:
        raise KeyError(f"unknown_experiment:{exp_id}")
    return catalog[exp_id]


def ordered_experiment_ids() -> list[str]:
    return list(load_experiment_catalog().keys())
