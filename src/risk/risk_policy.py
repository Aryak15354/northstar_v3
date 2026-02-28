from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from typing import Any, Dict


RISK_POLICY_IMMUTABLE_AFTER_INIT = True


@dataclass(frozen=True, slots=True)
class RiskPolicy:
    portfolio_risk_cap_pct: float
    max_position_risk_pct: float
    max_drawdown_pct: float
    weekly_trade_cap: int
    aggressive_mode: bool
    event_calendar_max_age_days: int
    epsilon: float
    version_tag: str
    config_hash: str
    git_commit_hash: str
    strict_mode: bool

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "RiskPolicy":
        strict_mode = _env_flag("NORTHSTAR_STRICT_MODE", default=False)
        risk_cfg = dict(config or {})

        policy = cls(
            portfolio_risk_cap_pct=_decimal_pct(
                "portfolio_risk_cap_pct", risk_cfg.get("portfolio_risk_cap_pct", 0.04)
            ),
            max_position_risk_pct=_decimal_pct(
                "max_position_risk_pct", risk_cfg.get("max_position_risk_pct", 0.02)
            ),
            max_drawdown_pct=_decimal_pct(
                "max_drawdown_pct", risk_cfg.get("max_drawdown_pct", 0.10)
            ),
            weekly_trade_cap=int(risk_cfg.get("weekly_trade_cap", 20)),
            aggressive_mode=bool(risk_cfg.get("aggressive", False)),
            event_calendar_max_age_days=int(risk_cfg.get("event_calendar_max_age_days", 14)),
            epsilon=float(risk_cfg.get("epsilon", 1e-9)),
            version_tag=str(risk_cfg.get("version_tag", os.getenv("NORTHSTAR_VERSION", "v4"))),
            config_hash=_config_hash(risk_cfg),
            git_commit_hash=str(
                risk_cfg.get("git_commit_hash")
                or os.getenv("GIT_COMMIT_HASH")
                or os.getenv("GITHUB_SHA")
                or "unknown"
            ),
            strict_mode=strict_mode,
        )

        if policy.weekly_trade_cap <= 0:
            raise ValueError("weekly_trade_cap must be positive")
        if policy.event_calendar_max_age_days <= 0:
            raise ValueError("event_calendar_max_age_days must be positive")
        if policy.epsilon <= 0.0:
            raise ValueError("epsilon must be > 0")

        return policy

    @property
    def policy_hash(self) -> str:
        payload = {
            "portfolio_risk_cap_pct": self.portfolio_risk_cap_pct,
            "max_position_risk_pct": self.max_position_risk_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "weekly_trade_cap": self.weekly_trade_cap,
            "aggressive_mode": self.aggressive_mode,
            "event_calendar_max_age_days": self.event_calendar_max_age_days,
            "epsilon": self.epsilon,
            "version_tag": self.version_tag,
            "config_hash": self.config_hash,
            "git_commit_hash": self.git_commit_hash,
            "strict_mode": self.strict_mode,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def as_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["policy_hash"] = self.policy_hash
        data["immutable_after_init"] = RISK_POLICY_IMMUTABLE_AFTER_INIT
        return data

    def portfolio_risk_cap(self, current_equity: float) -> float:
        return max(0.0, float(current_equity) * self.portfolio_risk_cap_pct)


class MutableRiskPolicyError(RuntimeError):
    pass


class RiskPolicyHandle:
    """Simple wrapper used where mutating APIs may still exist.

    The wrapped policy stays immutable. Strict mode raises on attempted mutation;
    non-strict mode ignores mutation attempts and keeps the original policy.
    """

    def __init__(self, policy: RiskPolicy):
        self._policy = policy

    @property
    def policy(self) -> RiskPolicy:
        return self._policy

    def replace(self, _: Dict[str, Any]) -> None:
        if RISK_POLICY_IMMUTABLE_AFTER_INIT:
            if self._policy.strict_mode:
                raise MutableRiskPolicyError(
                    "RiskPolicy is immutable after initialization in strict mode"
                )
            return


def _env_flag(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _decimal_pct(name: str, value: Any) -> float:
    try:
        pct = float(value)
    except Exception as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not (0.0 < pct < 1.0):
        raise ValueError(
            f"{name} must be decimal pct in (0,1). Example: 0.02 for 2%; got {pct}"
        )
    return pct


def _config_hash(config: Dict[str, Any]) -> str:
    payload = json.dumps(config, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
