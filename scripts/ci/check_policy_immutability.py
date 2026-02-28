#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.risk.risk_policy import RISK_POLICY_IMMUTABLE_AFTER_INIT, RiskPolicy


def main() -> int:
    cfg = {
        "portfolio_risk_cap_pct": 0.04,
        "max_position_risk_pct": 0.02,
        "max_drawdown_pct": 0.10,
        "weekly_trade_cap": 20,
        "aggressive": False,
        "event_calendar_max_age_days": 14,
        "version_tag": "v4-stabilization",
        "git_commit_hash": "ci-check",
        "epsilon": 1e-9,
    }

    policy = RiskPolicy.from_config(cfg)
    mutation_blocked = False
    mutation_error = ""
    try:
        setattr(policy, "portfolio_risk_cap_pct", 0.5)
    except Exception as exc:
        mutation_blocked = True
        mutation_error = str(exc)

    report = {
        "check": "policy_immutability",
        "immutable_contract_enabled": bool(RISK_POLICY_IMMUTABLE_AFTER_INIT),
        "mutation_blocked": mutation_blocked,
        "mutation_error": mutation_error,
        "policy_hash": policy.policy_hash,
        "config_hash": policy.config_hash,
        "git_commit_hash": policy.git_commit_hash,
        "version_tag": policy.version_tag,
    }
    print(json.dumps(report, indent=2))

    if not RISK_POLICY_IMMUTABLE_AFTER_INIT:
        return 1
    if not mutation_blocked:
        return 1
    if not policy.policy_hash:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
