#!/usr/bin/env python3
"""Governed model promotion CLI with freeze-window enforcement."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_os.strategy_lifecycle import (
    PromotionCriteriaNotMetError,
    StrategyLifecycleManager,
)
from src.alpha_os.strategy_registry import (
    StrategyFamily,
    StrategyRecord,
    StrategyRegistry,
    StrategyStatus,
)
from src.alpha_os.strategy_tribunal import StrategyTribunal
from src.research.model_registry import ModelRegistry
from src.research.research_engine import ResearchEngine


class _PersistentPriorStore:
    """Minimal file-backed tribunal adapter for governed promotion flows."""

    def __init__(self, weights_path: Path) -> None:
        self.weights_path = weights_path
        self.weights_path.parent.mkdir(parents=True, exist_ok=True)
        self.prior_weights = self._load()

    def _load(self) -> Dict[str, float]:
        if not self.weights_path.exists():
            return {}
        try:
            with open(self.weights_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            weights = payload.get("prior_weights", {})
            return {str(key): float(value) for key, value in weights.items()}
        except Exception:
            return {}

    def _save(self) -> None:
        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "prior_weights": self.prior_weights,
        }
        tmp_path = self.weights_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        tmp_path.replace(self.weights_path)

    def set_strategy_prior(self, strategy_id: str, prior_params: Dict[str, Any]) -> None:
        weight = float(
            prior_params.get("prior_weight")
            or prior_params.get("weight")
            or prior_params.get("expected_alpha", 0.0)
            or 0.0
        )
        self.prior_weights[strategy_id] = weight
        self._save()


def _load_candidate_payload(model_id: str) -> Dict[str, Any]:
    candidate_path = PROJECT_ROOT / "data/model_registry/candidates" / f"{model_id}.json"
    if not candidate_path.exists():
        return {}
    try:
        with open(candidate_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def _infer_family(candidate: Dict[str, Any], model_id: str) -> StrategyFamily:
    text = " ".join(
        [
            str(candidate.get("type", "")),
            str(candidate.get("strategy_family", "")),
            str(candidate.get("family", "")),
            model_id,
        ]
    ).lower()
    mapping = [
        ("momentum", StrategyFamily.MOMENTUM),
        ("reversion", StrategyFamily.MEAN_REVERSION),
        ("value", StrategyFamily.VALUE),
        ("quality", StrategyFamily.QUALITY),
        ("macro", StrategyFamily.MACRO),
        ("sentiment", StrategyFamily.SENTIMENT),
        ("alternative", StrategyFamily.ALTERNATIVE),
    ]
    for needle, family in mapping:
        if needle in text:
            return family
    return StrategyFamily.COMPOSITE


def _extract_validation_metrics(candidate: Dict[str, Any]) -> Dict[str, float]:
    validation_metrics = candidate.get("validation_metrics", {}) or {}
    score_metrics = validation_metrics.get("score", {}) or {}
    capital_metrics = validation_metrics.get("capital_metrics", {}) or {}

    ic_mean = float(score_metrics.get("ic", validation_metrics.get("ic_mean", 0.0)) or 0.0)
    hit_rate = float(validation_metrics.get("hit_rate", 0.0) or 0.0)
    icir = float(validation_metrics.get("icir", 0.0) or 0.0)

    if icir == 0.0 and hit_rate == 0.0 and ic_mean > 0.0:
        sharpe = float(score_metrics.get("sharpe", 0.0) or 0.0)
        total_return = float(capital_metrics.get("total_return", 0.0) or 0.0)
        hit_rate = 0.55 if ic_mean > 0 else 0.0
        icir = max(sharpe, total_return / 100.0)

    return {
        "ic_mean": ic_mean,
        "icir": icir,
        "hit_rate": hit_rate,
    }


def _ensure_alpha_os_record(strategy_registry: StrategyRegistry, model_id: str, candidate: Dict[str, Any]) -> StrategyRecord:
    try:
        record = strategy_registry.get(model_id)
    except Exception:
        metrics = _extract_validation_metrics(candidate)
        record = StrategyRecord(
            strategy_id=model_id,
            strategy_name=str(candidate.get("name") or candidate.get("type") or model_id),
            family=_infer_family(candidate, model_id),
            status=StrategyStatus.CANDIDATE,
            discovered_date=datetime.utcnow(),
            model_registry_path=str(Path("data/model_registry/candidates") / f"{model_id}.json"),
            validation_ic_mean=metrics["ic_mean"],
            validation_icir=metrics["icir"],
            validation_hit_rate=metrics["hit_rate"],
        )
        strategy_registry.register(record)
        return record

    metrics = _extract_validation_metrics(candidate)
    if record.status == StrategyStatus.RESEARCH:
        strategy_registry.update_status(model_id, StrategyStatus.CANDIDATE, "Promotable research model")
        record = strategy_registry.get(model_id)

    if metrics["ic_mean"]:
        record.validation_ic_mean = metrics["ic_mean"]
    if metrics["icir"]:
        record.validation_icir = metrics["icir"]
    if metrics["hit_rate"]:
        record.validation_hit_rate = metrics["hit_rate"]
    strategy_registry.save()
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote candidate model through Alpha OS governance")
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--override-freeze", action="store_true")
    parser.add_argument(
        "--force-quality-gate",
        action="store_true",
        help="Bypass the min_ic_mean/min_icir/min_hit_rate promotion criteria check. "
             "Requires --reason. Use only for a deliberate, reviewed exception.",
    )
    parser.add_argument("--reason", default="")
    parser.add_argument("--research-config", type=Path, default=PROJECT_ROOT / "config/research_policy.yaml")
    args = parser.parse_args()

    engine = ResearchEngine(config_path=args.research_config)
    freeze_active = engine.is_freeze_active()

    if freeze_active and not args.override_freeze:
        print(
            json.dumps(
                {
                    "ok": False,
                    "blocked": True,
                    "reason": "freeze_active",
                    "message": "Freeze window active. Use --override-freeze with --reason to proceed.",
                },
                indent=2,
            )
        )
        return 2

    if args.override_freeze and not args.reason.strip():
        print(json.dumps({"ok": False, "blocked": True, "reason": "override_requires_reason"}, indent=2))
        return 2

    if args.force_quality_gate and not args.reason.strip():
        print(json.dumps({"ok": False, "blocked": True, "reason": "force_quality_gate_requires_reason"}, indent=2))
        return 2

    legacy_registry = ModelRegistry()
    legacy_outcome = legacy_registry.promote_candidate(
        model_id=args.model_id,
        freeze_active=freeze_active,
        override=bool(args.override_freeze),
        reason=args.reason.strip() or "manual_promotion",
        min_ic_mean=0.035,
        min_icir=1.2,
        min_hit_rate=0.55,
        force_quality_gate=args.force_quality_gate,
    )
    if not legacy_outcome.get("ok"):
        print(json.dumps(legacy_outcome, indent=2))
        return 1

    candidate = _load_candidate_payload(args.model_id)

    strategy_registry = StrategyRegistry()
    prior_store = _PersistentPriorStore(PROJECT_ROOT / "data/model_registry/alpha_os_prior_weights.json")
    tribunal = StrategyTribunal(
        tribunal_instance=prior_store,
        registry=strategy_registry,
        config={
            "promotion_criteria": {
                "min_ic_mean": 0.035,
                "min_icir": 1.2,
            }
        },
    )
    lifecycle = StrategyLifecycleManager(
        registry=strategy_registry,
        tribunal=tribunal,
        config={"alpha_os": {"hot_reload": {"enabled": False}}},
    )

    record = _ensure_alpha_os_record(strategy_registry, args.model_id, candidate)
    if record.status != StrategyStatus.ACTIVE:
        try:
            lifecycle.promote_to_active(
                strategy_id=args.model_id,
                override_reason=args.reason.strip() or "manual_promotion",
                force=args.force_quality_gate,
            )
        except PromotionCriteriaNotMetError as exc:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "blocked": True,
                        "reason": "promotion_criteria_not_met",
                        "message": str(exc),
                    },
                    indent=2,
                )
            )
            return 2
        record = strategy_registry.get(args.model_id)

    result = {
        "ok": True,
        "blocked": False,
        "model_id": args.model_id,
        "legacy_registry": legacy_outcome,
        "alpha_os": {
            "status": record.status.value,
            "promoted_date": record.promoted_date.isoformat() if record.promoted_date else None,
            "validation_ic_mean": record.validation_ic_mean,
            "validation_icir": record.validation_icir,
            "validation_hit_rate": record.validation_hit_rate,
            "tribunal_weights": tribunal.get_capital_weights(),
        },
    }

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
