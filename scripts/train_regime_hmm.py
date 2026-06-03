#!/usr/bin/env python3
"""
Offline trainer for Northstar V4 regime HMM.

Policy:
- Runtime must never retrain.
- Retraining cadence is monthly (>=30 days).
- If gates fail, keep current model and log "retrain skipped".
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.regime_probability_engine import DEFAULT_STATES, FrozenRegimeHMM, train_hmm_em
from src.options.config_loader import get_config


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


@dataclass
class TrainingOutcome:
    status: str
    reason: str
    model_path: str
    timestamp: str
    diagnostics: Dict[str, Any]


def _load_existing_model(model_path: Path) -> Optional[FrozenRegimeHMM]:
    if not model_path.exists():
        return None
    try:
        with model_path.open("rb") as f:
            payload = pickle.load(f)
        return FrozenRegimeHMM.from_payload(payload)
    except Exception:
        return None


def _days_since_iso(ts: str) -> Optional[int]:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return max(0, int((_utc_now() - dt).days))
    except Exception:
        return None


def _build_feature_frame() -> Tuple[pd.DataFrame, List[str], str]:
    explicit = PROJECT_ROOT / "data/processed/regime_hmm_training_features.parquet"
    if explicit.exists():
        df = pd.read_parquet(explicit)
        num = df.select_dtypes(include=[np.number]).copy()
        cols = [c for c in num.columns if str(c).strip()]
        return num, cols, str(explicit)

    market_state = PROJECT_ROOT / "data/processed/market_state.parquet"
    if not market_state.exists():
        return pd.DataFrame(), [], "none"
    df = pd.read_parquet(market_state)
    if df.empty:
        return pd.DataFrame(), [], str(market_state)

    candidates = [
        "iv_percentile",
        "iv_rank",
        "volatility_20d",
        "volatility_5d",
        "vol_of_vol",
        "skew",
        "correlation_index",
        "risk_on_probability",
        "stress_score",
        "pulse_intensity",
    ]
    out = pd.DataFrame(index=df.index)
    for col in candidates:
        if col in df.columns:
            out[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            out[col] = np.nan

    # Construct coarse derivatives when available.
    out["realized_vol_accel"] = (
        pd.to_numeric(out["volatility_5d"], errors="coerce")
        - pd.to_numeric(out["volatility_20d"], errors="coerce")
    )
    out = out.dropna(how="all")
    return out, list(out.columns), str(market_state)


def _quality_gates(
    features: pd.DataFrame,
    min_samples: int,
    max_nan_ratio: float = 0.20,
) -> Tuple[bool, str]:
    if features.empty:
        return False, "empty_feature_frame"
    if len(features) < min_samples:
        return False, f"insufficient_samples:{len(features)}<{min_samples}"

    nan_ratio = float(features.isna().mean().max())
    if nan_ratio > max_nan_ratio:
        return False, f"feature_nan_ratio_too_high:{nan_ratio:.3f}>{max_nan_ratio:.3f}"

    filled = features.interpolate(limit_direction="both").fillna(method="ffill").fillna(method="bfill")
    if not np.isfinite(filled.to_numpy(dtype=float)).all():
        return False, "non_finite_features_after_fill"

    std = filled.std(axis=0, numeric_only=True)
    weak = int((std <= 1e-10).sum())
    if weak >= max(1, int(len(std) * 0.6)):
        return False, "feature_space_low_variance"

    return True, "ok"


def _append_training_log(payload: Dict[str, Any]) -> None:
    log_path = PROJECT_ROOT / "data/models/regime_hmm_training_log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []
    if log_path.exists():
        try:
            old = json.loads(log_path.read_text())
            if isinstance(old, list):
                rows = old
        except Exception:
            rows = []
    rows.append(payload)
    rows = rows[-200:]
    log_path.write_text(json.dumps(rows, indent=2))


def run_training(force: bool = False) -> TrainingOutcome:
    alpha_cfg = _load_alpha_os_config()
    model_path = PROJECT_ROOT / alpha_cfg.hmm_model_path
    model_path.parent.mkdir(parents=True, exist_ok=True)

    min_interval_days = max(30, int(alpha_cfg.hmm_retrain_interval_days))
    existing = _load_existing_model(model_path)
    if existing is not None and not force:
        age_days = _days_since_iso(existing.trained_at)
        if age_days is not None and age_days < min_interval_days:
            outcome = TrainingOutcome(
                status="skipped",
                reason=f"retrain skipped: cadence gate ({age_days}d<{min_interval_days}d)",
                model_path=str(model_path),
                timestamp=_iso(_utc_now()),
                diagnostics={"age_days": age_days, "min_interval_days": min_interval_days},
            )
            _append_training_log(asdict(outcome))
            return outcome

    feature_frame, feature_names, source = _build_feature_frame()
    gates_ok, gate_reason = _quality_gates(feature_frame, min_samples=int(alpha_cfg.hmm_min_samples))
    if not gates_ok:
        outcome = TrainingOutcome(
            status="skipped",
            reason=f"retrain skipped: {gate_reason}",
            model_path=str(model_path),
            timestamp=_iso(_utc_now()),
            diagnostics={"feature_source": source, "rows": int(len(feature_frame))},
        )
        _append_training_log(asdict(outcome))
        return outcome

    train_df = feature_frame.interpolate(limit_direction="both").fillna(method="ffill").fillna(method="bfill")
    x = train_df.to_numpy(dtype=float)

    model, diagnostics = train_hmm_em(
        features=x,
        states=DEFAULT_STATES,
        smoothing=float(alpha_cfg.hmm_transition_smoothing),
        feature_names=feature_names,
    )
    payload = model.to_payload()
    with model_path.open("wb") as f:
        pickle.dump(payload, f)

    outcome = TrainingOutcome(
        status="trained",
        reason="model updated",
        model_path=str(model_path),
        timestamp=_iso(_utc_now()),
        diagnostics={
            **diagnostics,
            "feature_source": source,
            "feature_names": feature_names,
            "transition_matrix": np.asarray(model.transition_matrix, dtype=float).round(6).tolist(),
        },
    )
    _append_training_log(asdict(outcome))
    return outcome


def _load_alpha_os_config() -> Any:
    """
    Load AlphaOS config without requiring live broker env vars.
    """
    try:
        cfg = get_config()
        return cfg.alpha_os
    except Exception:
        cfg_path = PROJECT_ROOT / "config/options_trading.yaml"
        payload = {}
        if cfg_path.exists():
            try:
                payload = yaml.safe_load(cfg_path.read_text()) or {}
            except Exception:
                payload = {}
        alpha = payload.get("alpha_os", {}) if isinstance(payload, dict) else {}
        defaults = {
            "hmm_model_path": "data/models/regime_hmm_latest.pkl",
            "hmm_retrain_interval_days": 30,
            "hmm_min_samples": 260,
            "hmm_transition_smoothing": 0.02,
        }
        merged = {**defaults, **(alpha if isinstance(alpha, dict) else {})}
        return SimpleNamespace(**merged)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train frozen regime HMM model (monthly cadence).")
    parser.add_argument("--force", action="store_true", help="Bypass cadence gate (still respects quality gates).")
    args = parser.parse_args()

    result = run_training(force=bool(args.force))
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
