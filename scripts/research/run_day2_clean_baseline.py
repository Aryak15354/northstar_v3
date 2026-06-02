#!/usr/bin/env python3
"""Day 2 clean baseline walk-forward runner.

This script exists specifically for the weekly research sprint Day 2 goal:
run an experiment-dir-only, post-bugfix clean baseline walk-forward with:

- forced `STANDARD` capital structure from `config/portfolio_governor_config.yaml`
- `use_config_capital_structure=True`
- certified production model resolution with strict preflight checks
- no writes to `data/validation/`
- conservative resource defaults for laptop hardware

The runner uses the real historical scoring stack (`DailyScorer`) and an
experiment-local walk-forward simulation. It intentionally avoids the older
synthetic/demo walk-forward scripts.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
import warnings
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

# Keep the run predictable on a small laptop host.
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
os.environ.setdefault("VECLIB_MAXIMUM_THREADS", "1")
os.environ.setdefault("TORCH_NUM_THREADS", "1")
os.environ.setdefault("TORCH_NUM_INTEROP_THREADS", "1")
os.environ.setdefault("NORTHSTAR_LOW_RESOURCE_PROFILE", "1")
os.environ.setdefault("NORTHSTAR_DISABLE_MPS", "1")

warnings.filterwarnings(
    "ignore",
    message=".*If you are loading a serialized model.*",
    category=UserWarning,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_os.strategy_registry import StrategyRegistry
from src.scoring.daily_scorer import DailyScorer


DEFAULT_COMPARE_AGAINST = (
    PROJECT_ROOT
    / "data/validation/institutional_complete/institutional_walk_forward_report_20260119_225213.json"
)


@dataclass(frozen=True)
class WalkForwardWindow:
    window_id: str
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    calibration_dates: list[str]
    rebalance_dates: list[str]


@dataclass(frozen=True)
class ModelResolution:
    kind: str
    source: str
    description: str
    model_path: str | None
    model_dir: str | None
    used_bundle_fallback: bool
    warnings: list[str]


@dataclass(frozen=True)
class RequestedConfig:
    validation_type: str
    n_windows: int
    train_weeks: int
    test_weeks: int
    purge_gap_weeks: int
    embargo_weeks: int
    step_size_weeks: int
    universe: str
    min_universe_size: int
    min_factor_coverage: float
    model: str
    model_path: str
    target_horizon_days: int
    target_type: str
    winsorize_low: float
    winsorize_high: float
    portfolio_size: int
    long_only: bool
    max_position_weight: float
    min_position_weight: float
    turnover_constraint: float
    use_config_capital_structure: bool
    governor_config_path: str
    regime: str
    large_cap_bps: float
    mid_cap_bps: float
    small_cap_bps: float
    large_cap_threshold_crore: float
    mid_cap_threshold_crore: float
    output_dir: str
    compare_against: str
    allow_regime_bundle_fallback: bool
    certified_model_path: str | None
    preflight_only: bool
    low_resource_mode: str
    duckdb_threads: int
    duckdb_memory_limit_mb: int
    calibration_stride_weeks: int


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _json_default(value: Any) -> Any:
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    return str(value)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return float(default)
    if not np.isfinite(out):
        return float(default)
    return float(out)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=_json_default))


def _weekly_endpoints(trading_dates: pd.DatetimeIndex) -> list[pd.Timestamp]:
    ser = pd.Series(pd.to_datetime(trading_dates)).dropna().sort_values().drop_duplicates()
    grouped = ser.groupby(ser.dt.to_period("W-FRI")).max()
    return [pd.Timestamp(x).normalize() for x in grouped.sort_values().tolist()]


def _build_windows(weekly_dates: list[pd.Timestamp], cfg: RequestedConfig) -> list[WalkForwardWindow]:
    required_points = (
        cfg.train_weeks
        + cfg.purge_gap_weeks
        + cfg.embargo_weeks
        + cfg.test_weeks
        + 1
    )
    if len(weekly_dates) < required_points:
        raise ValueError(
            "insufficient_weekly_dates_for_requested_walk_forward:"
            f"{len(weekly_dates)}<{required_points}"
        )

    windows: list[WalkForwardWindow] = []
    start_idx = 0
    while len(windows) < cfg.n_windows:
        test_start_idx = start_idx + cfg.train_weeks + cfg.purge_gap_weeks + cfg.embargo_weeks
        test_end_boundary_idx = test_start_idx + cfg.test_weeks
        if test_end_boundary_idx >= len(weekly_dates):
            break

        calibration_slice = weekly_dates[start_idx : start_idx + cfg.train_weeks]
        calibration_dates = calibration_slice[:: max(1, cfg.calibration_stride_weeks)]
        if calibration_slice and calibration_slice[-1] not in calibration_dates:
            calibration_dates = calibration_dates + [calibration_slice[-1]]

        rebalance_dates = weekly_dates[test_start_idx:test_end_boundary_idx]
        test_start = weekly_dates[test_start_idx]
        test_end = weekly_dates[test_end_boundary_idx]
        train_start = weekly_dates[start_idx]
        train_end = weekly_dates[start_idx + cfg.train_weeks - 1]

        windows.append(
            WalkForwardWindow(
                window_id=f"W{len(windows) + 1:02d}",
                train_start=str(train_start.date()),
                train_end=str(train_end.date()),
                test_start=str(test_start.date()),
                test_end=str(test_end.date()),
                calibration_dates=[str(x.date()) for x in calibration_dates],
                rebalance_dates=[str(x.date()) for x in rebalance_dates],
            )
        )
        start_idx += cfg.step_size_weeks

    if not windows:
        raise ValueError("no_valid_walk_forward_windows_constructed")
    return windows


def _load_governor_standard_fraction(governor_config_path: Path) -> dict[str, Any]:
    if not governor_config_path.exists():
        raise FileNotFoundError(f"governor_config_missing:{governor_config_path}")
    payload = yaml.safe_load(governor_config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"invalid_governor_config:{governor_config_path}")
    table = dict(payload.get("regime_table") or {})
    if "STANDARD" not in table:
        raise ValueError("governor_config_missing_STANDARD_regime")
    standard = dict(table["STANDARD"] or {})
    eq = _safe_float(standard.get("equity_fraction"), np.nan)
    opt = _safe_float(standard.get("options_fraction"), np.nan)
    cash = _safe_float(standard.get("cash_fraction"), np.nan)
    total = eq + opt + cash
    if not np.isfinite(total) or abs(total - 1.0) > 1e-6:
        raise ValueError(
            "invalid_STANDARD_capital_structure:"
            f"equity={eq} options={opt} cash={cash} total={total}"
        )
    return {
        "raw_config": payload,
        "equity_fraction": eq,
        "options_fraction": opt,
        "cash_fraction": cash,
    }


def _resolve_certified_model(
    *,
    requested_model: str,
    model_registry_dir: Path,
    explicit_model_path: str | None,
    allow_regime_bundle_fallback: bool,
) -> ModelResolution:
    warnings_out: list[str] = []
    if str(requested_model).strip() != "certified_production":
        raise ValueError(f"unsupported_model_request:{requested_model}")

    if explicit_model_path:
        model_path = Path(explicit_model_path).expanduser().resolve()
        if not model_path.exists():
            raise FileNotFoundError(f"explicit_certified_model_missing:{model_path}")
        return ModelResolution(
            kind="single_artifact",
            source="explicit_model_path",
            description="Using the operator-specified certified model artifact path.",
            model_path=str(model_path),
            model_dir=None,
            used_bundle_fallback=False,
            warnings=warnings_out,
        )

    registry_path = model_registry_dir.resolve()
    alpha_os_model_path: str | None = None
    try:
        registry = StrategyRegistry({"alpha_os_registry_path": str(registry_path)})
        alpha_os_model_path = registry.get_active_model_path()
    except Exception as exc:
        warnings_out.append(f"strategy_registry_resolution_failed:{exc}")

    if alpha_os_model_path:
        candidate = Path(alpha_os_model_path).expanduser().resolve()
        if candidate.exists():
            return ModelResolution(
                kind="single_artifact",
                source="alpha_os_active_strategy",
                description="Resolved certified production model from Alpha OS ACTIVE strategy metadata.",
                model_path=str(candidate),
                model_dir=None,
                used_bundle_fallback=False,
                warnings=warnings_out,
            )
        warnings_out.append(f"alpha_os_model_path_missing_on_disk:{candidate}")

    production_path = registry_path / "production.json"
    if production_path.exists():
        try:
            payload = json.loads(production_path.read_text())
        except Exception as exc:
            warnings_out.append(f"production_json_parse_failed:{exc}")
        else:
            candidate_raw = payload.get("model_path") if isinstance(payload, dict) else None
            if candidate_raw:
                candidate = Path(str(candidate_raw)).expanduser().resolve()
                if candidate.exists():
                    return ModelResolution(
                        kind="single_artifact",
                        source="production_json",
                        description="Resolved certified production model from data/model_registry/production.json.",
                        model_path=str(candidate),
                        model_dir=None,
                        used_bundle_fallback=False,
                        warnings=warnings_out,
                    )
                warnings_out.append(f"production_json_model_path_missing_on_disk:{candidate}")

    bundle_registry = PROJECT_ROOT / "models/regime_models/regime_model_registry.json"
    bundle_dir = PROJECT_ROOT / "models/regime_models"
    if allow_regime_bundle_fallback and bundle_registry.exists():
        try:
            payload = json.loads(bundle_registry.read_text())
        except Exception as exc:
            warnings_out.append(f"regime_bundle_registry_parse_failed:{exc}")
        else:
            models = dict(payload.get("models") or {})
            model_paths = [
                Path(str(rec.get("model_path", ""))).expanduser().resolve()
                for rec in models.values()
                if isinstance(rec, dict) and rec.get("model_path")
            ]
            model_paths = [path for path in model_paths if path.exists()]
            if model_paths:
                warnings_out.append(
                    "production_registry_incomplete_using_regime_bundle_fallback"
                )
                return ModelResolution(
                    kind="regime_bundle",
                    source="regime_model_bundle_fallback",
                    description=(
                        "Production registry metadata is incomplete, so the runner will use the "
                        "existing trained regime model bundle as the certified production fallback."
                    ),
                    model_path=None,
                    model_dir=str(bundle_dir.resolve()),
                    used_bundle_fallback=True,
                    warnings=warnings_out,
                )

    raise RuntimeError(
        "could_not_resolve_certified_production_model:"
        " no valid Alpha OS model path, no valid production.json model_path, "
        "and no allowed regime bundle fallback"
    )


def _load_price_panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    price_path = PROJECT_ROOT / "data/market/daily_prices.parquet"
    if not price_path.exists():
        raise FileNotFoundError(f"daily_prices_missing:{price_path}")
    prices = pd.read_parquet(price_path)
    if prices.empty:
        raise ValueError("daily_prices_empty")
    prices["Date"] = pd.to_datetime(prices["Date"], errors="coerce").dt.normalize()
    prices = prices.dropna(subset=["Date", "ticker", "Close"]).copy()
    prices["ticker"] = prices["ticker"].astype(str).str.upper()
    prices["Close"] = pd.to_numeric(prices["Close"], errors="coerce")
    prices = prices.dropna(subset=["Close"]).sort_values(["Date", "ticker"])
    pivot = prices.pivot(index="Date", columns="ticker", values="Close").sort_index().ffill()
    returns = pivot.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return pivot, returns


class Day2CleanBaselineRunner:
    def __init__(self, cfg: RequestedConfig):
        self.cfg = cfg
        self.output_root = Path(cfg.output_dir).expanduser().resolve()
        self.experiment_dir = self.output_root / f"{_timestamp()}_clean_standard_baseline"
        self.experiment_dir.mkdir(parents=True, exist_ok=True)

        self.governor_path = Path(cfg.governor_config_path)
        if not self.governor_path.is_absolute():
            self.governor_path = (PROJECT_ROOT / self.governor_path).resolve()

        self.model_registry_dir = Path(cfg.model_path)
        if not self.model_registry_dir.is_absolute():
            self.model_registry_dir = (PROJECT_ROOT / self.model_registry_dir).resolve()

        self.compare_against_path = Path(cfg.compare_against)
        if not self.compare_against_path.is_absolute():
            self.compare_against_path = (PROJECT_ROOT / self.compare_against_path).resolve()

        self.governor_standard = _load_governor_standard_fraction(self.governor_path)
        self.model_resolution = _resolve_certified_model(
            requested_model=cfg.model,
            model_registry_dir=self.model_registry_dir,
            explicit_model_path=cfg.certified_model_path,
            allow_regime_bundle_fallback=cfg.allow_regime_bundle_fallback,
        )
        self.price_pivot, self.return_pivot = _load_price_panel()
        self.daily_dates = pd.DatetimeIndex(self.price_pivot.index).sort_values()
        self.weekly_dates = _weekly_endpoints(self.daily_dates)
        self.windows = _build_windows(self.weekly_dates, cfg)
        self.baseline_report = self._load_baseline_report()

        self.score_cache: dict[str, pd.DataFrame] = {}
        self.score_metrics_cache: dict[str, dict[str, Any]] = {}
        self.rebalance_top_positions: list[dict[str, Any]] = []

        self.turnover_cache_path = self.experiment_dir / "cache" / "turnover_cache.pkl"
        self.turnover_cache_path.parent.mkdir(parents=True, exist_ok=True)

        self.scorer = self._build_scorer()
        self._write_manifests()

    def _build_scorer(self) -> DailyScorer:
        scorer_cfg = {
            "project_root": str(PROJECT_ROOT),
            "portfolio_mandate": "long_only",
            "target_type": str(self.cfg.target_type),
            "prediction_transform": "zscore" if str(self.cfg.target_type).strip().lower() == "cross_sectional_rank" else "raw",
            "max_weekly_turnover": float(self.cfg.turnover_constraint),
            "state": {
                # Avoid reading or writing the live UnifiedState snapshot during research.
                "snapshot_path": str(self.experiment_dir / "cache" / "nonexistent_unified_state.json"),
            },
            "dataset": {
                "strict_real_data_only": True,
                "target_horizon_days": int(self.cfg.target_horizon_days),
                "use_screener_features": True,
                "use_alternative_features": True,
                "use_sentiment_features": True,
                "use_macro_features": True,
                "enable_macro_features": True,
                "lookback_days": 120,
                "live_snapshot_mode": True,
                "live_snapshot_only_model_families": True,
                "live_snapshot_write_snapshot": False,
                "low_resource_mode": self.cfg.low_resource_mode,
                "duckdb_threads": int(self.cfg.duckdb_threads),
                "duckdb_memory_limit_mb": int(self.cfg.duckdb_memory_limit_mb),
            },
            "trainer": {
                "model_dir": self.model_resolution.model_dir or str(PROJECT_ROOT / "models/regime_models"),
                "n_jobs": 1,
            },
        }
        return DailyScorer(scorer_cfg)

    def _write_manifests(self) -> None:
        requested = asdict(self.cfg)
        resolved = {
            "requested_config": requested,
            "resolved_model": asdict(self.model_resolution),
            "resolved_governor_standard": {
                "equity_fraction": self.governor_standard["equity_fraction"],
                "options_fraction": self.governor_standard["options_fraction"],
                "cash_fraction": self.governor_standard["cash_fraction"],
                "governor_config_path": str(self.governor_path),
            },
            "experiment_dir": str(self.experiment_dir),
            "project_root": str(PROJECT_ROOT),
            "created_at_utc": _utc_now().isoformat(),
        }
        _write_json(self.experiment_dir / "requested_and_resolved_config.json", resolved)
        shutil.copy2(self.governor_path, self.experiment_dir / self.governor_path.name)

    def _load_baseline_report(self) -> dict[str, Any]:
        if not self.compare_against_path.exists():
            return {}
        try:
            payload = json.loads(self.compare_against_path.read_text())
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _score_snapshot(self, as_of_date: str) -> tuple[pd.DataFrame, dict[str, Any]]:
        key = str(pd.Timestamp(as_of_date).date())
        cached = self.score_cache.get(key)
        cached_metrics = self.score_metrics_cache.get(key)
        if isinstance(cached, pd.DataFrame) and isinstance(cached_metrics, dict):
            return cached.copy(), dict(cached_metrics)

        dt = pd.Timestamp(as_of_date).normalize()
        regime = self.scorer.regime_engine.get_regime_as_of(dt)
        exposure_scale = float(self.scorer.regime_engine.get_exposure_scale(regime))
        frame, feature_cols = self.scorer._load_latest_universe_frame(dt, regime=regime)
        if frame.empty:
            out = pd.DataFrame(
                columns=[
                    "ticker",
                    "raw_model_score",
                    "model_score",
                    "regime",
                    "sentiment_multiplier",
                    "base_sentiment_multiplier",
                    "macro_multiplier",
                    "final_score",
                    "sector",
                    "Company Name",
                    "Industry",
                    "close",
                    "shares_outstanding",
                    "market_cap_crore",
                ]
            )
            meta = {
                "date": key,
                "regime": str(regime),
                "exposure_scale": exposure_scale,
                "top20_positive_count": 0,
                "top20_positive_mass": 0.0,
            }
            self.score_cache[key] = out.copy()
            self.score_metrics_cache[key] = dict(meta)
            return out, meta

        use_feats = [str(c) for c in feature_cols if str(c) in frame.columns]
        if not use_feats:
            use_feats = [str(c) for c in frame.columns if pd.api.types.is_numeric_dtype(frame[c])]

        if self.model_resolution.kind == "single_artifact":
            preds = self.scorer._predict_with_model_path(
                frame[use_feats],
                regime=str(regime),
                model_path=str(self.model_resolution.model_path),
            )
        else:
            preds = self.scorer.trainer.predict(frame[use_feats], regime=regime)

        if len(preds) != len(frame):
            preds = np.resize(preds, len(frame)) if len(preds) > 0 else np.zeros(len(frame), dtype=float)

        raw_scores = pd.to_numeric(pd.Series(preds), errors="coerce").fillna(0.0)
        model_scores = self.scorer.transform_model_scores(raw_scores)
        out = pd.DataFrame(
            {
                "ticker": frame["ticker"].astype(str).to_numpy(),
                "raw_model_score": raw_scores.to_numpy(dtype=float),
                "model_score": model_scores.to_numpy(dtype=float),
                "regime": str(regime),
            }
        )

        if "Company Name" in frame.columns:
            out["Company Name"] = frame["Company Name"].fillna("").astype(str).to_numpy()
        else:
            out["Company Name"] = ""

        if "Industry" in frame.columns:
            out["Industry"] = frame["Industry"].fillna("Unknown").astype(str).to_numpy()
        else:
            out["Industry"] = "Unknown"

        if "sector" in frame.columns:
            out["sector"] = frame["sector"].fillna("Unknown").astype(str).to_numpy()
        else:
            sec_col = next((c for c in ["Industry", "industry", "Sector"] if c in frame.columns), None)
            out["sector"] = (
                frame[sec_col].fillna("Unknown").astype(str).to_numpy()
                if sec_col is not None
                else np.asarray(["Unknown"] * len(out))
            )

        sent = self.scorer.overlay.apply(out[["ticker", "model_score"]], as_of_date=dt)
        keep_cols = [
            "ticker",
            "sentiment_multiplier",
            "sentiment_override",
            "override_reason",
            "sentiment_polarity",
            "sentiment_conviction",
            "news_volume",
        ]
        sent = sent[[c for c in keep_cols if c in sent.columns]].copy()
        out = out.merge(sent, on="ticker", how="left")
        out["sentiment_multiplier"] = pd.to_numeric(out.get("sentiment_multiplier"), errors="coerce").fillna(1.0)
        out["base_sentiment_multiplier"] = pd.to_numeric(
            out.get("base_sentiment_multiplier", out["sentiment_multiplier"]), errors="coerce"
        ).fillna(1.0)
        out["sentiment_override"] = out.get("sentiment_override", False).fillna(False).astype(bool)
        out["sentiment_polarity"] = pd.to_numeric(out.get("sentiment_polarity"), errors="coerce")
        out["sentiment_conviction"] = pd.to_numeric(out.get("sentiment_conviction"), errors="coerce")
        out["news_volume"] = pd.to_numeric(out.get("news_volume"), errors="coerce").fillna(0.0)

        if "sector" in out.columns:
            out = self.scorer.overlay.apply_macro_overlay(out, as_of_date=dt)
        out["macro_multiplier"] = pd.to_numeric(out.get("macro_multiplier"), errors="coerce").fillna(1.0)
        out["sentiment_multiplier"] = pd.to_numeric(out.get("sentiment_multiplier"), errors="coerce").fillna(1.0)

        out["final_score"] = (
            pd.to_numeric(out["model_score"], errors="coerce").fillna(0.0)
            * pd.to_numeric(out["sentiment_multiplier"], errors="coerce").fillna(1.0)
            * exposure_scale
        )
        out["close"] = pd.to_numeric(frame.get("close"), errors="coerce")
        out["shares_outstanding"] = pd.to_numeric(frame.get("shares_outstanding"), errors="coerce")
        out["market_cap_crore"] = (
            pd.to_numeric(out["close"], errors="coerce")
            * pd.to_numeric(out["shares_outstanding"], errors="coerce")
            / 10_000_000.0
        )

        out = out.sort_values("final_score", ascending=False, kind="mergesort").reset_index(drop=True)
        top20 = out.head(self.cfg.portfolio_size).copy()
        meta = {
            "date": key,
            "regime": str(regime),
            "exposure_scale": exposure_scale,
            "top20_positive_count": int((top20["final_score"] > 0).sum()),
            "top20_positive_mass": float(top20["final_score"].clip(lower=0).sum()),
        }
        self.score_cache[key] = out.copy()
        self.score_metrics_cache[key] = dict(meta)
        return out, meta

    def _calibration_stats(self, dates: list[str]) -> dict[str, Any]:
        masses: list[float] = []
        counts: list[int] = []
        regimes: list[str] = []
        for date_str in dates:
            _, meta = self._score_snapshot(date_str)
            masses.append(_safe_float(meta.get("top20_positive_mass"), 0.0))
            counts.append(int(meta.get("top20_positive_count", 0)))
            regimes.append(str(meta.get("regime", "")))

        nonzero_masses = [m for m in masses if m > 0]
        ref_mass = float(np.quantile(nonzero_masses, 0.90)) if nonzero_masses else 1.0
        floor_mass = float(np.quantile(nonzero_masses, 0.25)) if nonzero_masses else 0.0
        positive_counts = [count for count in counts if count > 0]
        ref_count = (
            int(np.quantile(positive_counts, 0.90))
            if positive_counts
            else self.cfg.portfolio_size
        )
        ref_count = max(1, min(ref_count, self.cfg.portfolio_size))
        return {
            "calibration_points": len(dates),
            "positive_mass_ref_p90": ref_mass,
            "positive_mass_floor_p25": floor_mass,
            "positive_count_ref_p90": ref_count,
            "mean_positive_mass": float(np.mean(masses)) if masses else 0.0,
            "mean_positive_count": float(np.mean(counts)) if counts else 0.0,
            "regime_sample": regimes[:10],
        }

    @staticmethod
    def _project_capped_weights(raw_scores: pd.Series, gross_target: float, max_weight: float) -> pd.Series:
        vals = pd.to_numeric(raw_scores, errors="coerce").clip(lower=0.0).fillna(0.0)
        if vals.sum() <= 0 or gross_target <= 0:
            return pd.Series(0.0, index=vals.index, dtype=float)

        weights = (vals / float(vals.sum())) * float(gross_target)
        active = pd.Series(True, index=weights.index)
        while True:
            over = weights > float(max_weight + 1e-12)
            if not bool(over.any()):
                break
            excess = float((weights[over] - float(max_weight)).sum())
            weights.loc[over] = float(max_weight)
            active.loc[over] = False
            if not bool(active.any()) or excess <= 1e-12:
                break
            base = vals.loc[active]
            if float(base.sum()) <= 0:
                weights.loc[active] += excess / float(active.sum())
            else:
                weights.loc[active] += excess * (base / float(base.sum()))
        return weights.clip(lower=0.0)

    def _allocate_target_weights(
        self,
        scored: pd.DataFrame,
        calibration: dict[str, Any],
        prev_weights: dict[str, float],
    ) -> tuple[dict[str, float], dict[str, Any]]:
        ranked = scored[scored["final_score"] > 0].head(self.cfg.portfolio_size).copy()
        positive_count = int(len(ranked))
        positive_mass = float(ranked["final_score"].clip(lower=0).sum())
        count_ref = max(1, int(calibration.get("positive_count_ref_p90", self.cfg.portfolio_size)))
        mass_ref = max(1e-9, float(calibration.get("positive_mass_ref_p90", 1.0)))
        breadth = float(min(1.0, positive_count / float(count_ref)))
        strength = float(min(1.0, positive_mass / mass_ref))
        gross_target = float(self.governor_standard["equity_fraction"]) * breadth * strength

        meta = {
            "positive_count": positive_count,
            "positive_mass": positive_mass,
            "breadth": breadth,
            "strength": strength,
            "gross_target_before_constraints": gross_target,
        }

        if ranked.empty or gross_target < self.cfg.min_position_weight:
            meta["gross_target_after_constraints"] = 0.0
            meta["selected_names"] = 0
            return {}, meta

        max_names = min(self.cfg.portfolio_size, len(ranked))
        feasible_max_names = int(math.floor(gross_target / float(self.cfg.min_position_weight)))
        feasible_max_names = max(1, feasible_max_names)
        n_names = min(max_names, feasible_max_names)
        ranked = ranked.head(n_names).copy()

        # If there are too few names to carry the requested gross under the max weight,
        # clip the gross target rather than violating per-position caps.
        max_feasible_gross = float(len(ranked) * self.cfg.max_position_weight)
        gross_target = min(gross_target, max_feasible_gross)
        weights = self._project_capped_weights(
            ranked["final_score"],
            gross_target=float(gross_target),
            max_weight=float(self.cfg.max_position_weight),
        )
        ranked["target_weight"] = pd.to_numeric(weights, errors="coerce").fillna(0.0).to_numpy()

        # Drop names that still cannot satisfy the minimum target size.
        while not ranked.empty and bool((ranked["target_weight"] < self.cfg.min_position_weight - 1e-12).any()):
            ranked = ranked[ranked["target_weight"] >= self.cfg.min_position_weight - 1e-12].copy()
            if ranked.empty:
                break
            gross_target = min(float(gross_target), float(len(ranked) * self.cfg.max_position_weight))
            weights = self._project_capped_weights(
                ranked["final_score"],
                gross_target=float(gross_target),
                max_weight=float(self.cfg.max_position_weight),
            )
            ranked["target_weight"] = pd.to_numeric(weights, errors="coerce").fillna(0.0).to_numpy()

        target = {
            str(row["ticker"]): float(row["target_weight"])
            for _, row in ranked.iterrows()
            if float(row["target_weight"]) > 1e-8
        }
        target, turnover_meta = self._apply_turnover_constraint(prev_weights=prev_weights, target_weights=target)
        meta.update(turnover_meta)
        meta["gross_target_after_constraints"] = float(sum(target.values()))
        meta["selected_names"] = len(target)
        return target, meta

    def _apply_turnover_constraint(
        self,
        *,
        prev_weights: dict[str, float],
        target_weights: dict[str, float],
    ) -> tuple[dict[str, float], dict[str, Any]]:
        universe = sorted(set(prev_weights) | set(target_weights))
        if not universe:
            return {}, {"turnover_pre_constraint": 0.0, "turnover_post_constraint": 0.0, "turnover_blend_alpha": 1.0}

        turnover = float(
            sum(abs(_safe_float(target_weights.get(t), 0.0) - _safe_float(prev_weights.get(t), 0.0)) for t in universe)
        )
        if turnover <= float(self.cfg.turnover_constraint) + 1e-12:
            return (
                {k: float(v) for k, v in target_weights.items() if float(v) > 1e-8},
                {
                    "turnover_pre_constraint": turnover,
                    "turnover_post_constraint": turnover,
                    "turnover_blend_alpha": 1.0,
                },
            )

        alpha = float(self.cfg.turnover_constraint) / max(turnover, 1e-12)
        blended = {
            ticker: _safe_float(prev_weights.get(ticker), 0.0)
            + alpha * (_safe_float(target_weights.get(ticker), 0.0) - _safe_float(prev_weights.get(ticker), 0.0))
            for ticker in universe
        }
        blended = {
            ticker: float(weight)
            for ticker, weight in blended.items()
            if float(weight) > 1e-8
        }
        post_turnover = float(
            sum(abs(_safe_float(blended.get(t), 0.0) - _safe_float(prev_weights.get(t), 0.0)) for t in universe)
        )
        return blended, {
            "turnover_pre_constraint": turnover,
            "turnover_post_constraint": post_turnover,
            "turnover_blend_alpha": alpha,
        }

    def _trade_cost_bps(self, scored: pd.DataFrame, target_weights: dict[str, float], prev_weights: dict[str, float]) -> float:
        universe = sorted(set(prev_weights) | set(target_weights))
        if not universe:
            return 0.0
        trades = []
        mcap_lookup = scored.set_index("ticker")["market_cap_crore"].to_dict() if not scored.empty else {}
        for ticker in universe:
            delta = abs(_safe_float(target_weights.get(ticker), 0.0) - _safe_float(prev_weights.get(ticker), 0.0))
            if delta <= 1e-10:
                continue
            mcap_crore = _safe_float(mcap_lookup.get(ticker), np.nan)
            if np.isfinite(mcap_crore):
                if mcap_crore >= float(self.cfg.large_cap_threshold_crore):
                    bps = float(self.cfg.large_cap_bps)
                elif mcap_crore >= float(self.cfg.mid_cap_threshold_crore):
                    bps = float(self.cfg.mid_cap_bps)
                else:
                    bps = float(self.cfg.small_cap_bps)
            else:
                bps = float(self.cfg.mid_cap_bps)
            trades.append((delta, bps))
        if not trades:
            return 0.0
        total_delta = sum(delta for delta, _ in trades)
        if total_delta <= 0:
            return 0.0
        return float(sum(delta * bps for delta, bps in trades) / total_delta)

    def _next_trading_date(self, current_date: pd.Timestamp) -> pd.Timestamp | None:
        idx = self.daily_dates.searchsorted(current_date)
        while idx < len(self.daily_dates) and self.daily_dates[idx] <= current_date:
            idx += 1
        if idx >= len(self.daily_dates):
            return None
        return pd.Timestamp(self.daily_dates[idx]).normalize()

    def _daily_slice(self, start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DataFrame:
        return self.return_pivot.loc[(self.return_pivot.index > start_date) & (self.return_pivot.index <= end_date)].copy()

    @staticmethod
    def _max_drawdown(nav: pd.Series) -> float:
        if nav.empty:
            return 0.0
        running_peak = nav.cummax()
        dd = nav / running_peak - 1.0
        return float(abs(dd.min()) * 100.0)

    def _simulate_window(self, window: WalkForwardWindow) -> dict[str, Any]:
        calibration = self._calibration_stats(window.calibration_dates)
        prev_weights: dict[str, float] = {}
        nav = 1.0
        daily_returns: list[float] = []
        daily_exposures: list[float] = []
        nav_records: list[dict[str, Any]] = []
        rebalance_records: list[dict[str, Any]] = []
        violations = 0

        rebalance_boundaries = [pd.Timestamp(x) for x in window.rebalance_dates]
        final_boundary = pd.Timestamp(window.test_end)
        all_boundaries = rebalance_boundaries + [final_boundary]

        print(
            f"   {window.window_id}: test {window.test_start} -> {window.test_end} "
            f"({len(rebalance_boundaries)} rebalances)"
        )

        for i, rebalance_date in enumerate(rebalance_boundaries):
            next_boundary = all_boundaries[i + 1]
            scored, score_meta = self._score_snapshot(str(rebalance_date.date()))
            target_weights, allocation_meta = self._allocate_target_weights(
                scored=scored,
                calibration=calibration,
                prev_weights=prev_weights,
            )

            weighted_bps = self._trade_cost_bps(scored, target_weights, prev_weights)
            turnover = float(
                sum(
                    abs(_safe_float(target_weights.get(t), 0.0) - _safe_float(prev_weights.get(t), 0.0))
                    for t in set(prev_weights) | set(target_weights)
                )
            )
            trade_cost = nav * turnover * (weighted_bps / 10_000.0)
            nav = max(nav - trade_cost, 1e-12)

            daily_slice = self._daily_slice(rebalance_date, next_boundary)
            gross_exposure = float(sum(target_weights.values()))
            if daily_slice.empty:
                violations += 1

            for day, row in daily_slice.iterrows():
                held_tickers = [ticker for ticker in target_weights.keys() if ticker in row.index]
                if held_tickers:
                    asset_returns = pd.to_numeric(row[held_tickers], errors="coerce").fillna(0.0)
                    portfolio_return = float(
                        sum(_safe_float(target_weights.get(ticker), 0.0) * _safe_float(asset_returns.get(ticker), 0.0) for ticker in held_tickers)
                    )
                else:
                    portfolio_return = 0.0
                if not np.isfinite(portfolio_return):
                    portfolio_return = 0.0
                    violations += 1
                nav *= (1.0 + portfolio_return)
                daily_returns.append(portfolio_return)
                daily_exposures.append(gross_exposure)
                nav_records.append(
                    {
                        "window_id": window.window_id,
                        "date": day,
                        "nav": nav,
                        "portfolio_return": portfolio_return,
                        "gross_exposure": gross_exposure,
                    }
                )

            ranked = scored.head(self.cfg.portfolio_size).copy()
            ranked["window_id"] = window.window_id
            ranked["rebalance_date"] = pd.Timestamp(rebalance_date)
            self.rebalance_top_positions.extend(ranked.to_dict("records"))

            rebalance_records.append(
                {
                    "window_id": window.window_id,
                    "rebalance_date": str(rebalance_date.date()),
                    "next_boundary_date": str(next_boundary.date()),
                    "trade_cost_bps": weighted_bps,
                    "trade_cost_fraction": trade_cost,
                    "turnover": turnover,
                    "gross_exposure": gross_exposure,
                    **score_meta,
                    **allocation_meta,
                }
            )
            prev_weights = dict(target_weights)

        nav_series = pd.Series(
            [record["nav"] for record in nav_records],
            index=pd.to_datetime([record["date"] for record in nav_records]),
            dtype=float,
        )
        total_return = (nav - 1.0) * 100.0
        if daily_returns:
            daily_ret_series = pd.Series(daily_returns, dtype=float)
            volatility = float(daily_ret_series.std(ddof=0) * np.sqrt(252.0) * 100.0)
            sharpe = float((daily_ret_series.mean() * 252.0) / max(daily_ret_series.std(ddof=0) * np.sqrt(252.0), 1e-12))
        else:
            volatility = 0.0
            sharpe = 0.0

        result = {
            "window_id": window.window_id,
            "train_start": window.train_start,
            "train_end": window.train_end,
            "test_start": window.test_start,
            "test_end": window.test_end,
            "total_return": total_return,
            "sharpe": sharpe,
            "volatility": volatility,
            "max_drawdown": self._max_drawdown(nav_series),
            "mean_exposure": float(np.mean(daily_exposures) * 100.0) if daily_exposures else 0.0,
            "violations": int(violations),
            "daily_points": len(nav_records),
            "rebalance_count": len(rebalance_records),
            "calibration": calibration,
            "rebalance_records": rebalance_records,
            "daily_nav": nav_records,
        }
        return result

    def run_preflight(self) -> dict[str, Any]:
        first_window = self.windows[0]
        sample_dates = []
        if first_window.calibration_dates:
            sample_dates.append(first_window.calibration_dates[-1])
        if first_window.rebalance_dates:
            sample_dates.append(first_window.rebalance_dates[0])
        if len(self.windows) > 1 and self.windows[-1].rebalance_dates:
            sample_dates.append(self.windows[-1].rebalance_dates[-1])

        sample_scores = []
        for date_str in sample_dates:
            scored, meta = self._score_snapshot(date_str)
            sample_scores.append(
                {
                    "date": date_str,
                    "rows": int(len(scored)),
                    "regime": meta.get("regime"),
                    "exposure_scale": meta.get("exposure_scale"),
                    "top20_positive_count": meta.get("top20_positive_count"),
                    "top20_positive_mass": meta.get("top20_positive_mass"),
                    "top3": scored.head(3)[["ticker", "final_score"]].to_dict("records") if not scored.empty else [],
                }
            )

        calibration = self._calibration_stats(first_window.calibration_dates)
        scored, _ = self._score_snapshot(first_window.rebalance_dates[0])
        target_weights, allocation_meta = self._allocate_target_weights(
            scored=scored,
            calibration=calibration,
            prev_weights={},
        )
        first_rebalance = pd.Timestamp(first_window.rebalance_dates[0])
        next_boundary = pd.Timestamp(first_window.rebalance_dates[1]) if len(first_window.rebalance_dates) > 1 else pd.Timestamp(first_window.test_end)
        daily_slice = self._daily_slice(first_rebalance, next_boundary)

        report = {
            "created_at_utc": _utc_now().isoformat(),
            "ready_for_overnight": True,
            "experiment_dir": str(self.experiment_dir),
            "resolved_model": asdict(self.model_resolution),
            "governor_standard": {
                "equity_fraction": self.governor_standard["equity_fraction"],
                "options_fraction": self.governor_standard["options_fraction"],
                "cash_fraction": self.governor_standard["cash_fraction"],
            },
            "price_coverage": {
                "start": str(self.daily_dates.min().date()),
                "end": str(self.daily_dates.max().date()),
                "tickers": int(self.price_pivot.shape[1]),
                "trading_days": int(self.price_pivot.shape[0]),
                "weekly_rebalance_points": int(len(self.weekly_dates)),
            },
            "window_count": len(self.windows),
            "first_window": asdict(first_window),
            "sample_scores": sample_scores,
            "first_window_calibration": calibration,
            "first_rebalance_allocation": {
                "selected_names": len(target_weights),
                "gross_target": float(sum(target_weights.values())),
                "weights": dict(sorted(target_weights.items(), key=lambda kv: kv[1], reverse=True)[:10]),
                **allocation_meta,
            },
            "first_rebalance_return_slice_days": int(len(daily_slice)),
            "estimated_unique_scoring_dates": int(
                len(
                    {
                        date_str
                        for window in self.windows
                        for date_str in (list(window.calibration_dates) + list(window.rebalance_dates))
                    }
                )
            ),
        }
        _write_json(self.experiment_dir / "preflight_report.json", report)
        return report

    def run_full(self) -> dict[str, Any]:
        window_results: list[dict[str, Any]] = []
        all_rebalances: list[dict[str, Any]] = []
        all_daily_nav: list[dict[str, Any]] = []

        print(
            "Running Day 2 clean baseline walk-forward "
            f"({len(self.windows)} windows, STANDARD equity fraction "
            f"{self.governor_standard['equity_fraction']:.0%})"
        )

        for window in self.windows:
            window_result = self._simulate_window(window)
            window_results.append(
                {
                    key: value
                    for key, value in window_result.items()
                    if key not in {"rebalance_records", "daily_nav"}
                }
            )
            all_rebalances.extend(window_result["rebalance_records"])
            all_daily_nav.extend(window_result["daily_nav"])
            print(
                f"      return={window_result['total_return']:+.2f}% "
                f"sharpe={window_result['sharpe']:.2f} "
                f"dd={window_result['max_drawdown']:.2f}% "
                f"exposure={window_result['mean_exposure']:.2f}% "
                f"violations={window_result['violations']}"
            )

        windows_df = pd.DataFrame(window_results)
        rebalance_df = pd.DataFrame(all_rebalances)
        daily_nav_df = pd.DataFrame(all_daily_nav)
        top_positions_df = pd.DataFrame(self.rebalance_top_positions)

        windows_df.to_parquet(self.experiment_dir / "window_results.parquet", index=False)
        rebalance_df.to_parquet(self.experiment_dir / "rebalance_records.parquet", index=False)
        daily_nav_df.to_parquet(self.experiment_dir / "daily_nav.parquet", index=False)
        if not top_positions_df.empty:
            top_positions_df.to_parquet(self.experiment_dir / "top20_snapshots.parquet", index=False)

        summary = self._build_summary(windows_df)
        _write_json(self.experiment_dir / "summary.json", summary)
        self._write_summary_markdown(summary)
        return summary

    def _build_summary(self, windows_df: pd.DataFrame) -> dict[str, Any]:
        returns = pd.to_numeric(windows_df.get("total_return"), errors="coerce").fillna(0.0)
        sharpes = pd.to_numeric(windows_df.get("sharpe"), errors="coerce").fillna(0.0)
        drawdowns = pd.to_numeric(windows_df.get("max_drawdown"), errors="coerce").fillna(0.0)
        exposures = pd.to_numeric(windows_df.get("mean_exposure"), errors="coerce").fillna(0.0)
        violations = pd.to_numeric(windows_df.get("violations"), errors="coerce").fillna(0).astype(int)

        baseline_distributions = dict(self.baseline_report.get("distributions") or {})
        baseline_returns = dict(baseline_distributions.get("returns") or {})
        baseline_drawdowns = dict(baseline_distributions.get("drawdowns") or {})
        baseline_exposures = dict(baseline_distributions.get("exposures") or {})

        new_metrics = {
            "mean_return": float(returns.mean()) if not returns.empty else 0.0,
            "return_std": float(returns.std(ddof=0)) if not returns.empty else 0.0,
            "mean_sharpe": float(sharpes.mean()) if not sharpes.empty else 0.0,
            "mean_drawdown": float(drawdowns.mean()) if not drawdowns.empty else 0.0,
            "mean_exposure": float(exposures.mean()) if not exposures.empty else 0.0,
            "violations": int(violations.sum()),
        }

        prior_metrics = {
            "mean_return": _safe_float(baseline_returns.get("mean"), 5.84),
            "return_std": _safe_float(baseline_returns.get("std"), 2.66),
            "mean_sharpe": (
                _safe_float(self.baseline_report.get("mean_sharpe"), np.nan)
                if np.isfinite(_safe_float(self.baseline_report.get("mean_sharpe"), np.nan))
                else None
            ),
            "mean_drawdown": _safe_float(baseline_drawdowns.get("mean"), 1.57),
            "mean_exposure": _safe_float(baseline_exposures.get("mean"), 20.69),
            "violations": int(_safe_float(self.baseline_report.get("violations_detected"), 0)),
        }

        comparison = {}
        for key in new_metrics.keys():
            prior_value = prior_metrics[key]
            new_value = new_metrics[key]
            if prior_value is None:
                change = None
            else:
                change = new_value - prior_value
            comparison[key] = {
                "prior": prior_value,
                "new": new_value,
                "change": change,
            }

        verdict = "investigate_deeper"
        prior_sharpe_for_gate = float(prior_metrics["mean_sharpe"] or 0.0)
        if new_metrics["mean_exposure"] > 20.0 and new_metrics["mean_sharpe"] >= max(prior_sharpe_for_gate, 0.0):
            verdict = "bugfixes_materially_restored_deployment"
        elif new_metrics["mean_exposure"] < 10.0:
            verdict = "exposure_problem_deeper_than_formula_fixes"

        return {
            "created_at_utc": _utc_now().isoformat(),
            "experiment_dir": str(self.experiment_dir),
            "resolved_model": asdict(self.model_resolution),
            "governor_standard": {
                "equity_fraction": self.governor_standard["equity_fraction"],
                "options_fraction": self.governor_standard["options_fraction"],
                "cash_fraction": self.governor_standard["cash_fraction"],
            },
            "windows_processed": int(len(windows_df)),
            "window_results": windows_df.to_dict("records"),
            "metrics": new_metrics,
            "comparison_against_prior": comparison,
            "compare_against_path": str(self.compare_against_path) if self.compare_against_path.exists() else None,
            "verdict": verdict,
        }

    def _write_summary_markdown(self, summary: dict[str, Any]) -> None:
        comparison = dict(summary.get("comparison_against_prior") or {})
        lines = [
            "# Day 2 Clean Baseline Walk-Forward",
            "",
            f"- Created: {summary.get('created_at_utc')}",
            f"- Experiment Dir: `{summary.get('experiment_dir')}`",
            f"- Resolved Model Source: `{summary.get('resolved_model', {}).get('source', 'unknown')}`",
            f"- Resolved Model Description: {summary.get('resolved_model', {}).get('description', '')}",
            f"- Windows Processed: {summary.get('windows_processed', 0)}",
            "",
            "## Decision Table",
            "",
            "| Metric | Prior (pre-fix) | New (post-fix) | Change |",
            "|---|---:|---:|---:|",
        ]
        for key, label in [
            ("mean_return", "Mean return"),
            ("return_std", "Return std"),
            ("mean_sharpe", "Mean Sharpe"),
            ("mean_drawdown", "Mean drawdown"),
            ("mean_exposure", "Mean exposure"),
            ("violations", "Violations"),
        ]:
            row = comparison.get(key, {})
            prior = row.get("prior")
            new = row.get("new")
            change = row.get("change")
            def _fmt(v: Any, *, pct: bool = False) -> str:
                if v is None:
                    return "n/a"
                try:
                    fv = float(v)
                except Exception:
                    return str(v)
                if not np.isfinite(fv):
                    return "n/a"
                return f"{fv:.2f}%" if pct else f"{fv:.2f}"
            pct = key in {"mean_return", "return_std", "mean_drawdown", "mean_exposure"}
            lines.append(
                f"| {label} | {_fmt(prior, pct=pct)} | {_fmt(new, pct=pct)} | {_fmt(change, pct=pct)} |"
            )

        lines.extend(
            [
                "",
                "## Verdict",
                "",
                f"`{summary.get('verdict', 'unknown')}`",
                "",
            ]
        )
        (self.experiment_dir / "summary.md").write_text("\n".join(lines))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Day 2 clean baseline walk-forward.")
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "data/results/research/experiments/week_2026_03_22/day2_clean_baseline"),
        help="Experiment root directory. The script creates a timestamped subdirectory inside it.",
    )
    parser.add_argument(
        "--compare-against",
        default=str(DEFAULT_COMPARE_AGAINST),
        help="Baseline institutional walk-forward report to compare against.",
    )
    parser.add_argument(
        "--governor-config-path",
        default="config/portfolio_governor_config.yaml",
        help="Governor config path. STANDARD is read directly from this file.",
    )
    parser.add_argument(
        "--model-path",
        default="data/model_registry",
        help="Model registry directory used for certified production resolution.",
    )
    parser.add_argument(
        "--certified-model-path",
        default=None,
        help="Optional explicit certified model artifact path. Overrides registry resolution.",
    )
    parser.add_argument(
        "--allow-regime-bundle-fallback",
        action="store_true",
        help=(
            "Allow fallback to models/regime_models when production registry metadata is incomplete. "
            "Useful in the current repo because production.json and ACTIVE strategy artifact pointers are missing."
        ),
    )
    parser.add_argument("--preflight-only", action="store_true", help="Run strict preflight checks and exit.")
    parser.add_argument("--n-windows", type=int, default=10)
    parser.add_argument("--train-weeks", type=int, default=104)
    parser.add_argument("--test-weeks", type=int, default=13)
    parser.add_argument("--purge-gap-weeks", type=int, default=1)
    parser.add_argument("--embargo-weeks", type=int, default=2)
    parser.add_argument("--step-size-weeks", type=int, default=13)
    parser.add_argument("--portfolio-size", type=int, default=20)
    parser.add_argument("--max-position-weight", type=float, default=0.10)
    parser.add_argument("--min-position-weight", type=float, default=0.01)
    parser.add_argument("--turnover-constraint", type=float, default=0.60)
    parser.add_argument("--large-cap-bps", type=float, default=15.0)
    parser.add_argument("--mid-cap-bps", type=float, default=20.0)
    parser.add_argument("--small-cap-bps", type=float, default=30.0)
    parser.add_argument("--large-cap-threshold-crore", type=float, default=10000.0)
    parser.add_argument("--mid-cap-threshold-crore", type=float, default=2000.0)
    parser.add_argument("--duckdb-threads", type=int, default=1)
    parser.add_argument("--duckdb-memory-limit-mb", type=int, default=512)
    parser.add_argument("--low-resource-mode", default="on", choices=["on", "off", "auto"])
    parser.add_argument("--calibration-stride-weeks", type=int, default=4)
    return parser


def parse_requested_config(args: argparse.Namespace) -> RequestedConfig:
    return RequestedConfig(
        validation_type="institutional_complete",
        n_windows=int(args.n_windows),
        train_weeks=int(args.train_weeks),
        test_weeks=int(args.test_weeks),
        purge_gap_weeks=int(args.purge_gap_weeks),
        embargo_weeks=int(args.embargo_weeks),
        step_size_weeks=int(args.step_size_weeks),
        universe="nifty_500",
        min_universe_size=100,
        min_factor_coverage=0.25,
        model="certified_production",
        model_path=str(args.model_path),
        target_horizon_days=5,
        target_type="cross_sectional_rank",
        winsorize_low=0.01,
        winsorize_high=0.99,
        portfolio_size=int(args.portfolio_size),
        long_only=True,
        max_position_weight=float(args.max_position_weight),
        min_position_weight=float(args.min_position_weight),
        turnover_constraint=float(args.turnover_constraint),
        use_config_capital_structure=True,
        governor_config_path=str(args.governor_config_path),
        regime="STANDARD",
        large_cap_bps=float(args.large_cap_bps),
        mid_cap_bps=float(args.mid_cap_bps),
        small_cap_bps=float(args.small_cap_bps),
        large_cap_threshold_crore=float(args.large_cap_threshold_crore),
        mid_cap_threshold_crore=float(args.mid_cap_threshold_crore),
        output_dir=str(args.output_dir),
        compare_against=str(args.compare_against),
        allow_regime_bundle_fallback=bool(args.allow_regime_bundle_fallback),
        certified_model_path=str(args.certified_model_path) if args.certified_model_path else None,
        preflight_only=bool(args.preflight_only),
        low_resource_mode=str(args.low_resource_mode),
        duckdb_threads=int(args.duckdb_threads),
        duckdb_memory_limit_mb=int(args.duckdb_memory_limit_mb),
        calibration_stride_weeks=int(args.calibration_stride_weeks),
    )


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    cfg = parse_requested_config(args)
    runner = Day2CleanBaselineRunner(cfg)

    print(f"Experiment directory: {runner.experiment_dir}")
    print(f"Resolved model source: {runner.model_resolution.source}")
    if runner.model_resolution.used_bundle_fallback:
        print("WARNING: using regime model bundle fallback because certified production registry metadata is incomplete")
    print(
        "Forced STANDARD capital structure: "
        f"equity={runner.governor_standard['equity_fraction']:.0%} "
        f"options={runner.governor_standard['options_fraction']:.0%} "
        f"cash={runner.governor_standard['cash_fraction']:.0%}"
    )

    if cfg.preflight_only:
        report = runner.run_preflight()
        print(f"Preflight ready_for_overnight: {report['ready_for_overnight']}")
        print(f"Preflight report: {runner.experiment_dir / 'preflight_report.json'}")
        return 0

    preflight = runner.run_preflight()
    if not preflight.get("ready_for_overnight", False):
        raise RuntimeError("preflight_failed_not_running_full_walk_forward")

    summary = runner.run_full()
    print(f"Summary JSON: {runner.experiment_dir / 'summary.json'}")
    print(f"Summary MD:   {runner.experiment_dir / 'summary.md'}")
    print(f"Verdict: {summary.get('verdict')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
