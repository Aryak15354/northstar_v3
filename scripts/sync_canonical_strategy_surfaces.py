#!/usr/bin/env python3
"""Rebuild canonical strategy operating surfaces from fresh beliefs and allocations."""

from __future__ import annotations

import json
import math
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_os.strategy_registry import (
    StrategyFamily,
    StrategyRecord,
    StrategyRegistry,
    StrategyStatus,
)
from src.intelligence.strategy_surface_policy import (
    is_archived_strategy,
    is_feature_only_strategy,
    publishable_strategy_names,
    strategy_family_override,
    strategy_role,
    strategy_surface_mode,
)


BELIEFS_PATH = PROJECT_ROOT / "data" / "processed" / "strategy_beliefs.parquet"
ALLOCATIONS_PATH = PROJECT_ROOT / "data" / "processed" / "capital_allocations.json"
MARKET_STATE_PATH = PROJECT_ROOT / "data" / "processed" / "market_state.parquet"
TAILWINDS_PATH = PROJECT_ROOT / "data" / "intelligence" / "strategy_tailwinds.parquet"
INTELLIGENCE_STATE_PATH = PROJECT_ROOT / "data" / "intelligence" / "intelligence_state.json"
UNIFIED_INTELLIGENCE_STATE_PATH = PROJECT_ROOT / "data" / "processed" / "unified_intelligence_state.json"
UNIFIED_BELIEFS_PATH = PROJECT_ROOT / "data" / "processed" / "unified_beliefs.json"
BELIEF_EVOLUTION_PATH = PROJECT_ROOT / "data" / "processed" / "belief_evolution.json"
CATALOG_PATH = PROJECT_ROOT / "data" / "intelligence" / "canonical_strategy_catalog.json"
STATUS_PATH = PROJECT_ROOT / "data" / "intelligence" / "canonical_strategy_sync_status.json"


REGIME_BOOSTS: dict[str, dict[str, float]] = {
    "crisis": {
        "low_vol": 1.5,
        "quality_tilt": 1.3,
        "value_tilt": 1.2,
        "mom_6m": 0.7,
        "mom_12m": 0.7,
        "dual_momentum": 0.8,
    },
    "boom": {
        "mom_6m": 1.4,
        "mom_12m": 1.3,
        "dual_momentum": 1.2,
        "low_vol": 0.8,
        "quality_tilt": 0.9,
    },
    "expansion": {
        "mom_6m": 1.2,
        "quality_tilt": 1.1,
        "northstar": 1.1,
        "value_tilt": 0.9,
    },
    "late-expansion": {
        "quality_tilt": 1.2,
        "low_vol": 1.1,
        "northstar": 1.0,
        "mom_6m": 0.9,
        "value_tilt": 1.1,
    },
    "slowdown": {
        "value_tilt": 1.3,
        "quality_tilt": 1.2,
        "low_vol": 1.1,
        "mom_6m": 0.8,
        "mom_12m": 0.8,
    },
    "tightening": {
        "low_vol": 1.4,
        "value_tilt": 1.3,
        "quality_tilt": 1.2,
        "mom_6m": 0.7,
        "dual_momentum": 0.8,
    },
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except Exception:
        return float(default)
    if not math.isfinite(parsed):
        return float(default)
    return float(parsed)


def _clip(value: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, value)))


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _family_key(strategy: str) -> str:
    override = strategy_family_override(strategy)
    if override:
        return override
    s = str(strategy or "").strip().lower()
    if any(token in s for token in ["sentiment", "news"]):
        return "sentiment"
    if any(token in s for token in ["alternative", "ownership", "shareholding", "pledge", "bulk", "announcement"]):
        return "alternative"
    if any(token in s for token in ["regime", "macro"]):
        return "macro"
    if any(token in s for token in ["quality"]):
        return "quality"
    if any(token in s for token in ["value"]):
        return "value"
    if any(token in s for token in ["mom", "momentum", "northstar", "sector_tilt", "dual_"]):
        return "momentum"
    if any(token in s for token in ["low_vol", "risk_parity", "sector_neutral", "defensive"]):
        return "defensive"
    return "composite"


def _family_enum(strategy: str) -> StrategyFamily:
    key = _family_key(strategy)
    mapping = {
        "momentum": StrategyFamily.MOMENTUM,
        "quality": StrategyFamily.QUALITY,
        "value": StrategyFamily.VALUE,
        "macro": StrategyFamily.MACRO,
        "sentiment": StrategyFamily.SENTIMENT,
        "alternative": StrategyFamily.ALTERNATIVE,
        "defensive": StrategyFamily.COMPOSITE,
        "composite": StrategyFamily.COMPOSITE,
    }
    return mapping.get(key, StrategyFamily.COMPOSITE)


def _default_family_regime_modifier(family: str, regime: str) -> float:
    regime_key = str(regime or "").strip().lower()
    family_key = str(family or "").strip().lower()
    if family_key == "momentum":
        return {
            "boom": 1.15,
            "expansion": 1.10,
            "late-expansion": 1.00,
            "slowdown": 0.92,
            "tightening": 0.88,
            "crisis": 0.82,
        }.get(regime_key, 1.0)
    if family_key == "quality":
        return {
            "crisis": 1.14,
            "slowdown": 1.10,
            "tightening": 1.08,
            "late-expansion": 1.04,
            "expansion": 1.00,
            "boom": 0.97,
        }.get(regime_key, 1.0)
    if family_key == "value":
        return {
            "tightening": 1.10,
            "slowdown": 1.12,
            "late-expansion": 1.04,
            "crisis": 1.02,
            "expansion": 0.98,
            "boom": 0.95,
        }.get(regime_key, 1.0)
    if family_key == "macro":
        return {
            "crisis": 1.08,
            "tightening": 1.05,
            "slowdown": 1.03,
            "late-expansion": 1.02,
        }.get(regime_key, 1.0)
    if family_key == "defensive":
        return {
            "crisis": 1.12,
            "tightening": 1.08,
            "slowdown": 1.06,
            "boom": 0.95,
        }.get(regime_key, 1.0)
    return 1.0


def _status_from_row(strategy: str, row: pd.Series, allocations: dict[str, float], health: dict[str, float]) -> StrategyStatus:
    allocation = _safe_float(allocations.get(strategy), 0.0)
    belief_status = str(row.get("status", "") or "").strip().upper()
    skill = _safe_float(row.get("skill_prob"), 0.5)
    confidence = _safe_float(row.get("confidence"), 0.5)
    health_score = _safe_float(health.get(strategy), 0.0)

    if allocation > 1e-9:
        return StrategyStatus.ACTIVE
    if belief_status == "ACTIVE" and (skill >= 0.50 or confidence >= 0.70 or health_score > 0.0):
        return StrategyStatus.PROBATION
    if belief_status in {"FADING", "SUSPENDED"}:
        return StrategyStatus.CANDIDATE
    return StrategyStatus.CANDIDATE


def _load_beliefs() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not BELIEFS_PATH.exists():
        raise FileNotFoundError(f"Missing beliefs file: {BELIEFS_PATH}")
    beliefs = pd.read_parquet(BELIEFS_PATH)
    if beliefs.empty or "strategy" not in beliefs.columns:
        raise RuntimeError("strategy_beliefs.parquet is empty or missing strategy column")
    beliefs = beliefs.copy()
    if "date" in beliefs.columns:
        beliefs["date"] = pd.to_datetime(beliefs["date"], errors="coerce")
    elif "timestamp" in beliefs.columns:
        beliefs["date"] = pd.to_datetime(beliefs["timestamp"], errors="coerce")
    else:
        beliefs["date"] = pd.Timestamp.utcnow()
    beliefs["date"] = beliefs["date"].fillna(pd.Timestamp.utcnow())
    beliefs["strategy"] = beliefs["strategy"].astype(str)
    latest = beliefs.sort_values("date").groupby("strategy", as_index=False).tail(1).reset_index(drop=True)
    return beliefs, latest


def _load_allocations() -> dict[str, Any]:
    if not ALLOCATIONS_PATH.exists():
        return {}
    try:
        payload = json.loads(ALLOCATIONS_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _load_market_state() -> tuple[pd.DataFrame, str]:
    if not MARKET_STATE_PATH.exists():
        return pd.DataFrame(), "neutral"
    try:
        market = pd.read_parquet(MARKET_STATE_PATH)
    except Exception:
        return pd.DataFrame(), "neutral"
    if market.empty:
        return market, "neutral"
    market = market.copy()
    if "date" in market.columns:
        market["date"] = pd.to_datetime(market["date"], errors="coerce")
        market = market.sort_values("date", kind="mergesort")
    latest_regime = str(market.iloc[-1].get("regime", "neutral") or "neutral")
    return market, latest_regime


def _strategy_row_lookup(latest_beliefs: pd.DataFrame, strategy_names: list[str]) -> pd.DataFrame:
    indexed = latest_beliefs.set_index("strategy")
    rows: list[dict[str, Any]] = []
    for strategy in strategy_names:
        if strategy in indexed.index:
            row = indexed.loc[strategy].to_dict()
            row["strategy"] = strategy
        else:
            row = {
                "strategy": strategy,
                "belief_strength": 0.5,
                "skill_prob": 0.5,
                "confidence": 0.5,
                "effective_skill": 0.5,
                "regime_fit": 1.0,
                "sharpe": 0.0,
                "mean_return": 0.0,
                "volatility": 0.0,
                "total_observations": 0,
                "status": "CANDIDATE",
                "date": pd.Timestamp.utcnow(),
            }
        rows.append(row)
    return pd.DataFrame(rows)


def _build_catalog(
    latest_rows: pd.DataFrame,
    beliefs_full: pd.DataFrame,
    allocations_payload: dict[str, Any],
    latest_regime: str,
) -> list[dict[str, Any]]:
    allocations = allocations_payload.get("allocations", {}) if isinstance(allocations_payload.get("allocations"), dict) else {}
    health = allocations_payload.get("strategy_health", {}) if isinstance(allocations_payload.get("strategy_health"), dict) else {}
    history_counts = beliefs_full.groupby("strategy").size().to_dict()
    catalog: list[dict[str, Any]] = []

    for _, row in latest_rows.sort_values("strategy").iterrows():
        strategy = str(row.get("strategy", "") or "")
        if not strategy:
            continue
        family_key = _family_key(strategy)
        family_enum = _family_enum(strategy)
        allocation = _safe_float(allocations.get(strategy), 0.0)
        skill = _safe_float(row.get("skill_prob"), _safe_float(row.get("belief_strength"), 0.5))
        confidence = _safe_float(row.get("confidence"), 0.5)
        regime_fit = _safe_float(row.get("regime_fit"), 1.0)
        health_score = _safe_float(health.get(strategy), 0.0)
        effective_skill = _safe_float(row.get("effective_skill"), skill)
        obs = int(_safe_float(row.get("total_observations"), history_counts.get(strategy, 0)))
        status_enum = _status_from_row(strategy, row, allocations, health)
        discovered = pd.to_datetime(row.get("date"), errors="coerce")
        discovered = pd.Timestamp(discovered) if pd.notna(discovered) else pd.Timestamp.utcnow()

        catalog.append(
            {
                "strategy_id": strategy,
                "strategy_name": strategy.replace("_", " ").title(),
                "family_key": family_key,
                "family": family_enum.value,
                "policy_mode": strategy_surface_mode(strategy),
                "policy_role": strategy_role(strategy),
                "status": status_enum.value,
                "allocation": allocation,
                "health_score": health_score,
                "belief_strength": _safe_float(row.get("belief_strength"), skill),
                "skill_prob": skill,
                "confidence": confidence,
                "effective_skill": effective_skill,
                "regime_fit": regime_fit,
                "sharpe": _safe_float(row.get("sharpe"), 0.0),
                "mean_return": _safe_float(row.get("mean_return"), 0.0),
                "volatility": abs(_safe_float(row.get("volatility"), 0.0)),
                "total_observations": obs,
                "latest_regime": latest_regime,
                "discovered_date": discovered.isoformat(),
            }
        )
    return catalog


def _sync_registry(catalog: list[dict[str, Any]], regimes: list[str]) -> dict[str, Any]:
    registry = StrategyRegistry()
    existing_records = dict(registry.strategies)
    registry.strategies = {}
    now = _utc_now()
    catalog_ids = {str(item["strategy_id"]) for item in catalog}

    for strategy_id, record in existing_records.items():
        sid = str(strategy_id)
        if sid in catalog_ids:
            continue
        if is_feature_only_strategy(sid) or is_archived_strategy(sid):
            if record.status != StrategyStatus.RETIRED:
                record.status = StrategyStatus.RETIRED
                record.retired_date = record.retired_date or now
                reason = (
                    "Folded into the cohesive core strategy layer"
                    if is_feature_only_strategy(sid)
                    else "Archived construction shell removed from live strategy surface"
                )
                record.status_change_log.append(
                    {
                        "timestamp": now.isoformat(),
                        "from_status": "SYNCED",
                        "to_status": StrategyStatus.RETIRED.value,
                        "reason": reason,
                    }
                )
            registry.strategies[sid] = record
            continue
        registry.strategies[sid] = record

    for item in catalog:
        status = StrategyStatus(str(item["status"]))
        family = StrategyFamily(str(item["family"]))
        strategy_id = str(item["strategy_id"])
        previous = existing_records.get(strategy_id)
        regime_activations = {
            regime: bool((_default_family_regime_modifier(str(item["family_key"]), regime) >= 0.95))
            for regime in regimes
        }
        status_log = list(previous.status_change_log) if previous is not None else []
        status_log.append(
            {
                "timestamp": now.isoformat(),
                "from_status": "SYNCED",
                "to_status": status.value,
                "reason": "Canonical strategy surface sync from beliefs and capital allocations",
            }
        )
        record = StrategyRecord(
            strategy_id=strategy_id,
            strategy_name=str(item["strategy_name"]),
            family=family,
            status=status,
            discovered_date=(
                previous.discovered_date
                if previous is not None
                else datetime.fromisoformat(str(item["discovered_date"]))
            ),
            promoted_date=(
                previous.promoted_date
                if previous is not None and previous.promoted_date is not None
                else now if status == StrategyStatus.ACTIVE else None
            ),
            retired_date=previous.retired_date if previous is not None else None,
            model_registry_path=previous.model_registry_path if previous is not None else None,
            validation_ic_mean=_safe_float(item.get("mean_return"), 0.0),
            validation_icir=_safe_float(item.get("belief_strength"), 0.0),
            validation_hit_rate=_safe_float(item.get("skill_prob"), 0.0),
            validation_regime_ics={str(item.get("latest_regime", "neutral")): _safe_float(item.get("regime_fit"), 1.0) - 1.0},
            current_live_ic=_safe_float(item.get("health_score"), 0.0),
            probation_reason="allocator_not_currently_weighted" if status == StrategyStatus.PROBATION else None,
            max_capital_weight=max(0.05, _clip(_safe_float(item.get("allocation"), 0.0) * 1.75, 0.05, 0.50)),
            regime_activations=regime_activations,
            performance_history=list(previous.performance_history) if previous is not None else [],
            status_change_log=status_log,
        )
        registry.strategies[strategy_id] = record

    registry.save()
    return registry.get_registry_summary()


def _sync_tailwinds(catalog: list[dict[str, Any]], regimes: list[str], latest_regime: str, market_state: pd.DataFrame) -> dict[str, Any]:
    regime_counts = {}
    if not market_state.empty and "regime" in market_state.columns:
        regime_counts = market_state["regime"].fillna("unknown").astype(str).value_counts().to_dict()
    now = _utc_now()
    rows: list[dict[str, Any]] = []

    for item in catalog:
        strategy = str(item["strategy_id"])
        family_key = str(item["family_key"])
        skill = _safe_float(item.get("skill_prob"), 0.5)
        confidence = _safe_float(item.get("confidence"), 0.5)
        regime_fit = _safe_float(item.get("regime_fit"), 1.0)
        base = 1.0 + 0.40 * (skill - 0.5) + 0.10 * (confidence - 0.5)

        for regime in regimes:
            direct = REGIME_BOOSTS.get(regime, {}).get(strategy)
            modifier = _safe_float(direct, _default_family_regime_modifier(family_key, regime))
            if regime == latest_regime:
                modifier *= max(0.85, regime_fit)
            else:
                modifier *= 1.0 + 0.35 * (regime_fit - 1.0)

            tailwind_score = _clip(base * modifier, 0.70, 1.50)
            rows.append(
                {
                    "strategy_id": strategy,
                    "strategy_family": family_key,
                    "regime": regime,
                    "tailwind_score": tailwind_score,
                    "n_observations": int(regime_counts.get(regime, 0) or max(1, int(item.get("total_observations", 1)))),
                    "as_of_date": now,
                }
            )

    df = pd.DataFrame(rows).sort_values(["strategy_family", "strategy_id", "regime"])
    TAILWINDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(TAILWINDS_PATH, index=False)
    return {
        "rows": int(len(df)),
        "strategies": int(df["strategy_id"].nunique()) if not df.empty else 0,
        "regimes": int(df["regime"].nunique()) if not df.empty else 0,
        "path": str(TAILWINDS_PATH),
    }


def _sync_intelligence_views(
    catalog: list[dict[str, Any]],
    allocations_payload: dict[str, Any],
    latest_regime: str,
) -> dict[str, Any]:
    now = _utc_now().isoformat()
    active = [item for item in catalog if item["status"] == StrategyStatus.ACTIVE.value]
    probation = [item for item in catalog if item["status"] == StrategyStatus.PROBATION.value]
    top_allocated = sorted(catalog, key=lambda item: float(item.get("allocation", 0.0)), reverse=True)[:10]

    strategy_conviction = 0.0
    if catalog:
        strategy_conviction = sum(
            _clip(_safe_float(item.get("skill_prob"), 0.5) * _safe_float(item.get("confidence"), 0.5), 0.0, 1.0)
            for item in catalog
        ) / len(catalog)
    market_conviction = _clip(_safe_float((allocations_payload.get("total_exposure") or 0.0), 0.0) * 1.5, 0.0, 1.0)
    narrative_conviction = _clip(0.45 + 0.20 * max(0.0, min(len(active), 12)) / 12.0, 0.0, 1.0)
    unified_conviction = _clip((strategy_conviction + market_conviction + narrative_conviction) / 3.0, 0.0, 1.0)

    confidence_metrics = {
        "overall_confidence": _clip(
            sum(_safe_float(item.get("confidence"), 0.5) for item in catalog) / max(len(catalog), 1),
            0.0,
            1.0,
        ),
        "strategy_confidence": _clip(strategy_conviction, 0.0, 1.0),
        "market_confidence": market_conviction,
        "narrative_confidence": narrative_conviction,
    }
    top_strategy_payload = [
        {
            "strategy": item["strategy_id"],
            "allocation": _safe_float(item.get("allocation"), 0.0),
            "status": item["status"],
            "family": item["family"],
            "belief_strength": _safe_float(item.get("belief_strength"), 0.0),
        }
        for item in top_allocated
    ]

    intelligence_state = {
        "timestamp": now,
        "source": "canonical_strategy_surface_sync",
        "total_strategies": len(catalog),
        "processed_strategies": len(catalog),
        "successful": len(catalog),
        "failed": 0,
        "active_strategies": len(active),
        "probation_strategies": len(probation),
        "current_regime": latest_regime,
        "capital_allocations": allocations_payload.get("allocations", {}),
        "beliefs": {
            "market_beliefs": {"conviction": market_conviction},
            "valuation_beliefs": {"conviction": strategy_conviction},
            "narrative_beliefs": {"conviction": narrative_conviction},
            "conviction_levels": {
                "strategy": strategy_conviction,
                "overall": unified_conviction,
            },
            "top_strategies": top_strategy_payload,
        },
        "results": top_strategy_payload,
    }
    _write_json_atomic(INTELLIGENCE_STATE_PATH, intelligence_state)

    unified_beliefs = {
        "timestamp": now,
        "version": "canonical_sync_v1",
        "synthesis_method": "beliefs_plus_allocator",
        "source_weights": {
            "strategy_beliefs": 0.50,
            "capital_allocations": 0.30,
            "regime_fit": 0.20,
        },
        "market_beliefs": {"conviction": market_conviction, "regime": latest_regime},
        "valuation_beliefs": {"conviction": strategy_conviction},
        "strategy_beliefs": top_strategy_payload,
        "unified_stance": "risk_on" if market_conviction >= 0.55 else "balanced",
        "unified_conviction": unified_conviction,
        "unified_actions": {
            "primary_action": "allocate_to_live_alpha",
            "target_regime": latest_regime,
        },
        "confidence_metrics": confidence_metrics,
        "risk_assessment": {
            "allocated_strategy_count": len([item for item in catalog if _safe_float(item.get("allocation"), 0.0) > 0.0]),
            "probation_strategy_count": len(probation),
        },
        "contradiction_analysis": {
            "status": "low",
            "conviction_confidence_gap": abs(unified_conviction - confidence_metrics["overall_confidence"]),
        },
        "belief_evolution": {
            "latest_regime": latest_regime,
            "top_allocated_strategies": top_strategy_payload[:5],
        },
    }
    _write_json_atomic(UNIFIED_BELIEFS_PATH, unified_beliefs)

    belief_evolution = {
        "history": [
            {
                "timestamp": now,
                "unified_conviction": unified_conviction,
                "overall_confidence": confidence_metrics["overall_confidence"],
                "active_strategy_count": len(active),
                "probation_strategy_count": len(probation),
                "current_regime": latest_regime,
            }
        ]
    }
    _write_json_atomic(BELIEF_EVOLUTION_PATH, belief_evolution)

    unified_intelligence_state = {
        "timestamp": now,
        "version": "canonical_sync_v1",
        "intelligence_state": {
            "current_regime": latest_regime,
            "strategy_count": len(catalog),
            "active_strategy_count": len(active),
            "allocated_strategy_count": len([item for item in catalog if _safe_float(item.get("allocation"), 0.0) > 0.0]),
            "top_strategies": top_strategy_payload,
            "unified_conviction": unified_conviction,
        },
        "regime_history": [],
        "execution_log": [
            {
                "timestamp": now,
                "source": "sync_canonical_strategy_surfaces",
                "status": "ok",
            }
        ],
        "intelligence_status": {
            "status": "ok",
            "source": "sync_canonical_strategy_surfaces",
            "strategy_count": len(catalog),
            "current_regime": latest_regime,
        },
    }
    _write_json_atomic(UNIFIED_INTELLIGENCE_STATE_PATH, unified_intelligence_state)

    return {
        "active_strategies": len(active),
        "probation_strategies": len(probation),
        "unified_conviction": unified_conviction,
        "overall_confidence": confidence_metrics["overall_confidence"],
    }


def main() -> int:
    beliefs_full, latest_beliefs = _load_beliefs()
    allocations_payload = _load_allocations()
    market_state, latest_regime = _load_market_state()

    allocations = allocations_payload.get("allocations", {}) if isinstance(allocations_payload.get("allocations"), dict) else {}
    health = allocations_payload.get("strategy_health", {}) if isinstance(allocations_payload.get("strategy_health"), dict) else {}
    strategy_names = publishable_strategy_names(
        set(latest_beliefs["strategy"].astype(str)) | set(allocations) | set(health)
    )
    latest_rows = _strategy_row_lookup(latest_beliefs, strategy_names)

    if market_state.empty or "regime" not in market_state.columns:
        regimes = sorted(REGIME_BOOSTS.keys())
    else:
        regimes = sorted({str(v) for v in market_state["regime"].dropna().astype(str)} | set(REGIME_BOOSTS.keys()))

    catalog = _build_catalog(latest_rows, beliefs_full, allocations_payload, latest_regime)
    _write_json_atomic(
        CATALOG_PATH,
        {
            "timestamp": _utc_now().isoformat(),
            "source": "sync_canonical_strategy_surfaces",
            "latest_regime": latest_regime,
            "strategies": catalog,
        },
    )
    registry_summary = _sync_registry(catalog, regimes)
    tailwind_summary = _sync_tailwinds(catalog, regimes, latest_regime, market_state)
    intelligence_summary = _sync_intelligence_views(catalog, allocations_payload, latest_regime)

    status = {
        "timestamp": _utc_now().isoformat(),
        "status": "ok",
        "latest_regime": latest_regime,
        "catalog_path": str(CATALOG_PATH),
        "registry_summary": registry_summary,
        "tailwinds": tailwind_summary,
        "intelligence": intelligence_summary,
    }
    _write_json_atomic(STATUS_PATH, status)
    print(json.dumps(status, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
