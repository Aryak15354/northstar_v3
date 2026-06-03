from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY_PATH = PROJECT_ROOT / "config" / "strategy_surface_policy.json"


def _default_policy() -> dict[str, Any]:
    return {
        "version": 1,
        "overlay": {
            "default_parent": "northstar",
            "max_abs_score_impact": 0.12,
            "signal_cap": 1.0,
        },
        "strategies": {},
    }


@lru_cache(maxsize=1)
def load_strategy_surface_policy(path: str | Path | None = None) -> dict[str, Any]:
    policy_path = Path(path) if path is not None else DEFAULT_POLICY_PATH
    if not policy_path.exists():
        return _default_policy()
    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except Exception:
        return _default_policy()
    if not isinstance(payload, dict):
        return _default_policy()
    payload.setdefault("overlay", {})
    payload.setdefault("strategies", {})
    return payload


def clear_strategy_surface_policy_cache() -> None:
    load_strategy_surface_policy.cache_clear()


def _entries() -> dict[str, dict[str, Any]]:
    payload = load_strategy_surface_policy()
    raw = payload.get("strategies", {})
    return raw if isinstance(raw, dict) else {}


def strategy_surface_entry(strategy_name: str) -> dict[str, Any]:
    return dict(_entries().get(str(strategy_name or ""), {}) or {})


def is_policy_managed_strategy(strategy_name: str) -> bool:
    return str(strategy_name or "") in _entries()


def strategy_surface_mode(strategy_name: str) -> str:
    entry = strategy_surface_entry(strategy_name)
    mode = str(entry.get("mode", "standalone") or "standalone").strip().lower()
    return mode if mode in {"standalone", "feature_only", "archived"} else "standalone"


def is_standalone_strategy(strategy_name: str) -> bool:
    return strategy_surface_mode(strategy_name) == "standalone"


def is_feature_only_strategy(strategy_name: str) -> bool:
    return strategy_surface_mode(strategy_name) == "feature_only"


def is_archived_strategy(strategy_name: str) -> bool:
    return strategy_surface_mode(strategy_name) == "archived"


def standalone_strategy_names(candidates: Iterable[str] | None = None) -> set[str]:
    names = {name for name, entry in _entries().items() if str(entry.get("mode", "")).lower() == "standalone"}
    if candidates is None:
        return names
    return {str(x) for x in candidates if is_standalone_strategy(str(x))}


def strategy_role(strategy_name: str) -> str:
    entry = strategy_surface_entry(strategy_name)
    return str(entry.get("role", "standalone") or "standalone").strip().lower()


def strategy_family_override(strategy_name: str) -> str | None:
    entry = strategy_surface_entry(strategy_name)
    family = str(entry.get("family", "") or "").strip().lower()
    return family or None


def strategy_overlay_parent(strategy_name: str) -> str:
    entry = strategy_surface_entry(strategy_name)
    parent = str(entry.get("parent", "") or "").strip()
    if parent:
        return parent
    overlay_cfg = load_strategy_surface_policy().get("overlay", {})
    default_parent = str((overlay_cfg or {}).get("default_parent", "northstar") or "northstar").strip()
    return default_parent or "northstar"


def strategy_overlay_weight(strategy_name: str) -> float:
    entry = strategy_surface_entry(strategy_name)
    try:
        weight = float(entry.get("overlay_weight", 1.0))
    except Exception:
        weight = 1.0
    return max(0.0, weight)


def strategy_max_allocation(strategy_name: str, default: float | None = None) -> float | None:
    entry = strategy_surface_entry(strategy_name)
    if "max_allocation" not in entry:
        return default
    try:
        value = float(entry["max_allocation"])
    except Exception:
        return default
    return max(0.0, min(1.0, value))


def publishable_strategy_names(candidates: Iterable[str]) -> list[str]:
    out: list[str] = []
    for strategy_name in candidates:
        strategy = str(strategy_name or "")
        if not strategy:
            continue
        if is_archived_strategy(strategy) or is_feature_only_strategy(strategy):
            continue
        out.append(strategy)
    return sorted(set(out))


def managed_nonstandalone_strategy_names() -> set[str]:
    return {
        name for name in _entries()
        if strategy_surface_mode(name) in {"feature_only", "archived"}
    }


def overlay_config() -> dict[str, Any]:
    raw = load_strategy_surface_policy().get("overlay", {})
    return raw if isinstance(raw, dict) else {}

