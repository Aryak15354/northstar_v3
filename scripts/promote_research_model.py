#!/usr/bin/env python3
"""Manual model promotion CLI with freeze-window enforcement."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.research.model_registry import ModelRegistry
from src.research.research_engine import ResearchEngine


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote candidate model manually")
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--override-freeze", action="store_true")
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

    registry = ModelRegistry()
    outcome = registry.promote_candidate(
        model_id=args.model_id,
        freeze_active=freeze_active,
        override=bool(args.override_freeze),
        reason=args.reason.strip() or "manual_promotion",
    )

    print(json.dumps(outcome, indent=2))
    return 0 if outcome.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
