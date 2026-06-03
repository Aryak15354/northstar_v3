"""Formula lineage and unit integrity diagnostics for certification."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


_STRUCTURAL_META_COLUMNS = {
    "horizon",
    "obs_used",
    "n_obs",
    "window",
    "lookback",
    "rank",
    "index",
    "iteration",
}

_EXPECTED_GLOBAL_SNAPSHOT_COLUMNS = {
    "macro_transmission_expected": {"horizon"},
    "macro_transmission_sv_summary": {"obs_used"},
    "macro_transmission_jax_betas": {"obs_used"},
    "valuation": {
        "regime_modifier",
        "macro_compression",
        "regime_low_vol_prob",
        "regime_normal_prob",
        "regime_crisis_prob",
        "core_variance",
        "fcfe_confidence",
        "macro_percentile",
        "macro_adjustment_factor",
    },
}

_PERCENT_TOKENS = ("%", "percent", "basis point", "bps")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return float(default)
    if not np.isfinite(out):
        return float(default)
    return float(out)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _is_fx_series_name(name: str) -> bool:
    lname = str(name).strip().lower()
    if any(tok in lname for tok in ("usd/inr", "inr/usd", "exchange rate", "per usd", "vis-à-vis", " fx ")):
        return True
    has_usd = "usd" in lname or "dollar" in lname
    has_inr = "inr" in lname or "rupee" in lname
    has_rate_context = any(tok in lname for tok in ("rate", "fx", "exchange"))
    return bool(has_usd and has_inr and has_rate_context)


def _first_date_column(columns: Sequence[str]) -> Optional[str]:
    for c in ("date", "Date", "timestamp", "as_of"):
        if c in columns:
            return c
    return None


def _read_parquet(path: Path, columns: Optional[Sequence[str]] = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        if columns:
            return pd.read_parquet(path, columns=[c for c in columns if c])
        return pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()


def _series_cv(values: pd.Series) -> Tuple[float, int, int]:
    s = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(s) == 0:
        return 0.0, 0, 0
    mean = float(s.mean())
    std = float(s.std(ddof=0))
    cv = float(std / abs(mean)) if abs(mean) > 1e-12 else float("inf")
    return cv, int(len(s)), int(s.nunique())


def _temporal_or_snapshot_series(df: pd.DataFrame, col: str) -> Tuple[pd.Series, str, int]:
    """Return series to audit + axis kind + unique-date count."""
    c = str(col)
    if c not in df.columns:
        return pd.Series(dtype=float), "missing", 0
    dcol = _first_date_column(list(df.columns))
    if dcol is None:
        return pd.to_numeric(df[c], errors="coerce"), "cross_sectional", 0

    d = pd.to_datetime(df[dcol], errors="coerce")
    v = pd.to_numeric(df[c], errors="coerce")
    work = pd.DataFrame({"date": d, "v": v}).dropna()
    if work.empty:
        return pd.Series(dtype=float), "missing", 0
    n_dates = int(work["date"].dt.normalize().nunique())
    if n_dates >= 5:
        ts = (
            work.assign(date=work["date"].dt.normalize())
            .groupby("date", as_index=True)["v"]
            .mean()
            .sort_index()
        )
        return ts, "temporal_mean", n_dates
    return work["v"], "snapshot_cross_sectional", n_dates


def _analyze_source(
    source_name: str,
    path: Path,
    *,
    min_cv: float,
    min_obs: int,
    columns: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "source": source_name,
        "path": str(path),
        "exists": bool(path.exists()),
        "series": [],
        "flatline_series": [],
        "structural_constants": [],
        "warnings": [],
    }
    if not path.exists():
        out["warnings"].append("missing_source")
        out["passed"] = True
        return out

    df = _read_parquet(path, columns=columns)
    if df.empty:
        out["warnings"].append("empty_source")
        out["passed"] = True
        return out

    numeric_cols = list(df.select_dtypes(include=[np.number]).columns)
    for col in numeric_cols:
        c = str(col)
        axis_series, axis_kind, n_dates = _temporal_or_snapshot_series(df, c)
        cv, n_obs, n_unique = _series_cv(axis_series)
        if n_obs < int(min_obs):
            classification = "insufficient_observations"
        elif c.strip().lower() in _STRUCTURAL_META_COLUMNS:
            classification = "structural_constant"
        elif (
            axis_kind == "snapshot_cross_sectional"
            and c in _EXPECTED_GLOBAL_SNAPSHOT_COLUMNS.get(source_name, set())
        ):
            classification = "structural_constant"
        elif cv < float(min_cv):
            classification = "flatline_flag"
        else:
            classification = "ok"

        row = {
            "series": f"{source_name}.{c}",
            "column": c,
            "axis": axis_kind,
            "n_dates": int(n_dates),
            "n_obs": int(n_obs),
            "n_unique": int(n_unique),
            "cv": float(cv if np.isfinite(cv) else 999.0),
            "classification": classification,
        }
        out["series"].append(row)
        if classification == "flatline_flag":
            out["flatline_series"].append(row)
        elif classification == "structural_constant":
            out["structural_constants"].append(row)

    out["passed"] = len(out["flatline_series"]) == 0
    return out


def _policy_threshold_snapshot(cert_cfg: Mapping[str, Any]) -> Dict[str, Any]:
    keys = [
        "max_pairwise_corr",
        "max_holdings_overlap",
        "turnover_zero_streak_limit",
        "min_exposure_variance",
        "max_family_weight_hard",
        "max_family_weight_soft",
        "corr_drift_hard",
        "min_family_entropy",
        "allocation_l1_step_max",
        "regime_effectiveness_min_delta_sharpe",
        "regime_effectiveness_min_delta_return_ann",
        "regime_effectiveness_min_delta_dd",
        "min_trials_weekday",
        "min_trials_weekend",
        "min_objective_variance",
        "max_rolling_param_stability",
        "bootstrap_sharpe_p05_min",
        "block_bootstrap_dd_p95_max",
        "ruin_x1_max",
        "ruin_x2_max",
        "ruin_x3_max",
    ]
    out: Dict[str, Any] = {}
    for k in keys:
        if k in cert_cfg:
            out[k] = cert_cfg.get(k)
    return out


def build_formula_lineage_report(
    *,
    project_root: Path,
    dataset_metadata: Mapping[str, Any],
    cert_cfg: Mapping[str, Any],
) -> Dict[str, Any]:
    min_cv = float(cert_cfg.get("lineage_min_cv", 1e-5))
    min_obs = int(cert_cfg.get("lineage_min_obs", 5))
    max_unexplained = int(cert_cfg.get("lineage_max_unexplained_flatlines", 12))

    sources = [
        ("market_state", project_root / "data/processed/market_state.parquet", None),
        ("intelligent_state", project_root / "data/processed/intelligent_market_state.parquet", None),
        (
            "macro_transmission_expected",
            project_root / "data/processed/macro_transmission/macro_expected_change.parquet",
            ["macro_variable", "expected_change", "horizon", "as_of"],
        ),
        (
            "macro_transmission_sv_summary",
            project_root / "data/processed/macro_transmission/stochastic_volatility_summary.parquet",
            ["ticker", "sigma_current", "sigma_mean", "sigma_std", "obs_used"],
        ),
        (
            "macro_transmission_jax_betas",
            project_root / "data/processed/macro_transmission/jax_kalman_betas.parquet",
            ["ticker", "macro_variable", "beta_jax", "obs_used"],
        ),
        (
            "valuation",
            project_root / "data/processed/valuation.parquet",
            [
                "date",
                "growth_score",
                "institutional_value_score",
                "regime_modifier",
                "macro_compression",
                "regime_low_vol_prob",
                "regime_normal_prob",
                "regime_crisis_prob",
                "core_variance",
                "fcfe_confidence",
                "macro_percentile",
                "macro_adjustment_factor",
            ],
        ),
        (
            "strategy_beliefs",
            project_root / "data/processed/strategy_beliefs.parquet",
            ["date", "strategy", "belief_strength", "skill_prob", "confidence", "effective_skill"],
        ),
    ]

    diagnostics = [
        _analyze_source(name, path, min_cv=min_cv, min_obs=min_obs, columns=cols)
        for name, path, cols in sources
    ]
    flatline = [s for d in diagnostics for s in d.get("flatline_series", [])]
    structural = [s for d in diagnostics for s in d.get("structural_constants", [])]
    scanned = int(sum(len(d.get("series", [])) for d in diagnostics))
    passed = bool(len(flatline) <= max_unexplained)

    raw_layers = [
        {
            "layer": "prices_fundamentals_macro_sentiment",
            "source": "/src/research/dataset_manager.py",
            "hash_fields": [
                "universe_hash",
                "price_hash",
                "feature_hash",
                "label_hash",
            ],
            "hash_present": {
                "universe_hash": bool(dataset_metadata.get("universe_hash")),
                "price_hash": bool(dataset_metadata.get("price_hash")),
                "feature_hash": bool(dataset_metadata.get("feature_hash")),
                "label_hash": bool(dataset_metadata.get("label_hash")),
            },
        },
        {
            "layer": "macro_raw_feeds",
            "source": "/src/macro_impact_engine/macro_engine_data_loader.py",
            "inputs": [
                "data/macro/comprehensive_rbi_data.parquet",
                "data/processed/prices.parquet",
                "data/processed/returns_daily.parquet",
            ],
        },
    ]

    normalized_layers = [
        {
            "layer": "target_sanitize_clip_winsor",
            "source": "/src/research/dataset_manager.py",
            "formula": "y_sanitized = clip(winsorize(y_raw, q), +/-clip_abs)",
            "config": {
                "target_clip_abs": _safe_float(dataset_metadata.get("target_clip_abs", 1.0), 1.0),
                "target_winsor_quantile": _safe_float(dataset_metadata.get("target_winsor_quantile", 0.995), 0.995),
            },
        },
        {
            "layer": "feature_cross_sectional_normalization",
            "source": "/src/research/dataset_manager.py",
            "formula": "X_cs = zscore_or_rank(X by date)",
            "config": {
                "feature_cross_sectional_zscore": bool(dataset_metadata.get("feature_cross_sectional_zscore", False)),
                "feature_zscore_clip_abs": _safe_float(dataset_metadata.get("feature_zscore_clip_abs", 8.0), 8.0),
            },
        },
        {
            "layer": "macro_percent_and_bps_normalization",
            "source": "/src/macro_impact_engine/macro_engine_data_loader.py",
            "formula": "percent_to_decimal and bps_to_decimal on explicit percent-like fields",
        },
        {
            "layer": "macro_stationarity_standardization",
            "source": "/src/macro_impact_engine/preprocessing.py",
            "formula": "stationary_series -> winsorize -> zscore",
        },
        {
            "layer": "valuation_percentile_ranks",
            "source": "/src/processing/valuation_engine.py",
            "formula": "feature_pct = pct_rank_by_industry(feature)",
        },
    ]

    derived_layers = [
        {
            "layer": "market_allowed_exposure",
            "source": "/src/state/market_state.py",
            "formula": "allowed_exposure = clip(base_regime * momentum_adj * health_adj * vol_adj * opp_adj, 5, 95)",
            "outputs": ["allowed_exposure", "risk_on_probability"],
        },
        {
            "layer": "sentiment_headwind_multiplier",
            "source": "/src/state/market_state.py",
            "formula": "headwind = tanh(weighted(event_shock, polarity, uncertainty, conflict, counts)); exposure_multiplier = clip(1 - 0.85*headwind)",
            "outputs": ["sentiment_risk_multiplier", "sentiment_exposure_multiplier"],
        },
        {
            "layer": "strategy_belief_posterior",
            "source": "/src/intelligence/strategy_beliefs.py",
            "formula": "skill_prob = alpha/(alpha+beta); alpha,beta updated by wins/losses with decay",
            "outputs": ["belief_strength", "skill_prob", "effective_skill", "status"],
        },
        {
            "layer": "valuation_growth_score",
            "source": "/src/processing/valuation_engine.py",
            "formula": "growth_score = 0.42*revenue_growth_pct + 0.28*(1-peg_pct) + 0.20*earnings_stability_pct + 0.10*owner_earnings_yield_pct",
            "outputs": ["growth_score"],
        },
        {
            "layer": "strategy_survival_curve",
            "source": "/src/dashboard/northstar_v3_ultimate_integrated_dashboard.py",
            "formula": "survival(h) = (1 - clip(base_hazard * multiplier(belief), 0.01, 0.95))^(h/30)",
            "outputs": ["survival_probability"],
        },
    ]

    policy_layers = [
        {
            "layer": "certification_hard_fail_thresholds",
            "source": "/config/research_policy.yaml",
            "thresholds": _policy_threshold_snapshot(cert_cfg),
        },
        {
            "layer": "freeze_and_burn_in_policy",
            "source": "/src/research/research_engine.py",
            "formula": "resume iff consecutive_pass_cycles>=target and regime_coverage>=target",
        },
    ]

    return {
        "raw_data_layers": raw_layers,
        "normalized_layers": normalized_layers,
        "derived_layers": derived_layers,
        "policy_layers": policy_layers,
        "anomaly_normalization": {
            "series_scanned": int(scanned),
            "flatline_series_count": int(len(flatline)),
            "structural_constant_count": int(len(structural)),
            "max_unexplained_flatlines": int(max_unexplained),
            "flatline_series_preview": flatline[:30],
            "structural_constants_preview": structural[:30],
            "source_diagnostics": diagnostics,
        },
        "passed": bool(passed),
    }


def build_belief_layer_diagnostics(project_root: Path, cert_cfg: Mapping[str, Any]) -> Dict[str, Any]:
    min_days = int(cert_cfg.get("belief_min_history_days_for_strict_eval", 20))
    path = project_root / "data/processed/strategy_beliefs.parquet"
    df = _read_parquet(path)
    if df.empty or "strategy" not in df.columns:
        return {
            "history_days": 0,
            "updates_observed": 0,
            "belief_dispersion": 0.0,
            "confidence_dispersion": 0.0,
            "ready_for_strict_evaluation": False,
            "passed": True,
            "warnings": ["belief_history_missing"],
        }

    dcol = _first_date_column(list(df.columns))
    if dcol is None:
        return {
            "history_days": 0,
            "updates_observed": 0,
            "belief_dispersion": 0.0,
            "confidence_dispersion": 0.0,
            "ready_for_strict_evaluation": False,
            "passed": True,
            "warnings": ["belief_time_axis_missing"],
        }

    work = df.copy()
    work[dcol] = pd.to_datetime(work[dcol], errors="coerce")
    work = work.dropna(subset=[dcol])
    if work.empty:
        return {
            "history_days": 0,
            "updates_observed": 0,
            "belief_dispersion": 0.0,
            "confidence_dispersion": 0.0,
            "ready_for_strict_evaluation": False,
            "passed": True,
            "warnings": ["belief_history_empty_after_date_parse"],
        }

    latest = work.sort_values(dcol).groupby("strategy", as_index=False).tail(1)
    belief = pd.to_numeric(latest.get("belief_strength"), errors="coerce").dropna()
    conf = pd.to_numeric(latest.get("confidence"), errors="coerce").dropna()
    history_days = int((work[dcol].max() - work[dcol].min()).days) + 1
    updates = int(work[dcol].dt.normalize().nunique())
    ready = bool(history_days >= min_days and updates >= max(3, min_days // 5))
    return {
        "history_days": int(max(0, history_days)),
        "updates_observed": int(max(0, updates)),
        "belief_dispersion": float(belief.std(ddof=0) if len(belief) > 1 else 0.0),
        "confidence_dispersion": float(conf.std(ddof=0) if len(conf) > 1 else 0.0),
        "ready_for_strict_evaluation": bool(ready),
        "passed": True,
        "warnings": [],
    }


def build_macro_unit_integrity(
    *,
    project_root: Path,
    cert_cfg: Mapping[str, Any],
) -> Dict[str, Any]:
    meta_path = project_root / "data/processed/macro_transmission/run_metadata.json"
    expected_path = project_root / "data/processed/macro_transmission/macro_expected_change.parquet"

    require_meta = bool(cert_cfg.get("require_macro_unit_metadata", False))
    pct_limit = float(cert_cfg.get("macro_percent_abs_expected_change_max", 1.0))
    fx_limit = float(cert_cfg.get("macro_fx_abs_expected_change_max", 0.25))

    suspicious: List[Dict[str, Any]] = []
    warnings: List[str] = []
    structural_constant_fields: List[Dict[str, Any]] = []

    unit_family_counts: Dict[str, Any] = {}
    conversion_sample: Dict[str, Any] = {}
    conversion_full: Dict[str, Any] = {}
    percent_conversions = 0
    metadata_available = False

    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text())
            uh = meta.get("unit_handling", {}) if isinstance(meta, Mapping) else {}
            if isinstance(uh, Mapping):
                metadata_available = True
                unit_family_counts = dict(uh.get("unit_family_counts", {})) if isinstance(uh.get("unit_family_counts"), Mapping) else {}
                conversion_sample = dict(uh.get("conversion_log_sample", {})) if isinstance(uh.get("conversion_log_sample"), Mapping) else {}
                percent_conversions = int(_safe_int(uh.get("percent_conversions", 0), 0))
                conversion_path = uh.get("conversion_log_path")
                if conversion_path:
                    p = Path(str(conversion_path))
                    if not p.is_absolute():
                        p = project_root / p
                    if p.exists():
                        try:
                            full = json.loads(p.read_text())
                            if isinstance(full, Mapping):
                                conversion_full = dict(full)
                        except Exception:
                            warnings.append("macro_unit_conversion_log_unreadable")
                conversion_probe = conversion_full if conversion_full else conversion_sample
                for var_name, action in conversion_probe.items():
                    name = str(var_name).lower()
                    action_s = str(action).strip().lower()
                    explicit_percent = any(tok in name for tok in _PERCENT_TOKENS)
                    fx_named = _is_fx_series_name(name)
                    if fx_named and (not explicit_percent) and action_s == "percent_to_decimal":
                        suspicious.append(
                            {
                                "rule": "currency_series_percent_conversion",
                                "macro_variable": str(var_name),
                                "observed": str(action_s),
                                "expected": "keep_level_or_fx_return",
                            }
                        )
        except Exception:
            warnings.append("macro_run_metadata_unreadable")
    else:
        warnings.append("macro_run_metadata_missing")

    variables_checked = 0
    if expected_path.exists():
        exp = _read_parquet(expected_path, columns=["macro_variable", "expected_change", "horizon", "as_of"])
        if not exp.empty and "macro_variable" in exp.columns:
            exp["macro_variable"] = exp["macro_variable"].astype(str)
            exp["expected_change"] = pd.to_numeric(exp.get("expected_change"), errors="coerce")
            exp = exp.dropna(subset=["expected_change"])
            variables_checked = int(len(exp))
            for _, row in exp.iterrows():
                var_name = str(row.get("macro_variable", ""))
                val = abs(_safe_float(row.get("expected_change", 0.0), 0.0))
                lname = var_name.lower()
                explicit_percent = any(tok in lname for tok in _PERCENT_TOKENS)
                fx_named = _is_fx_series_name(lname)
                if explicit_percent and val > pct_limit:
                    suspicious.append(
                        {
                            "rule": "percent_expected_change_out_of_bounds",
                            "macro_variable": var_name,
                            "observed_abs_expected_change": float(val),
                            "threshold": float(pct_limit),
                        }
                    )
                if fx_named and val > fx_limit:
                    suspicious.append(
                        {
                            "rule": "fx_expected_change_out_of_bounds",
                            "macro_variable": var_name,
                            "observed_abs_expected_change": float(val),
                            "threshold": float(fx_limit),
                        }
                    )
            if "horizon" in exp.columns:
                uniq_h = int(pd.to_numeric(exp["horizon"], errors="coerce").dropna().nunique())
                if uniq_h <= 1:
                    structural_constant_fields.append(
                        {"series": "macro_expected_change.horizon", "reason": "configured_horizon_constant"}
                    )
    else:
        warnings.append("macro_expected_change_missing")

    # Structural constants: obs_used is expected to be constant when a single history window is used.
    for source_name, pth, col in [
        ("macro_transmission_sv_summary", project_root / "data/processed/macro_transmission/stochastic_volatility_summary.parquet", "obs_used"),
        ("macro_transmission_jax_betas", project_root / "data/processed/macro_transmission/jax_kalman_betas.parquet", "obs_used"),
    ]:
        df = _read_parquet(pth, columns=[col]) if pth.exists() else pd.DataFrame()
        if df.empty or col not in df.columns:
            continue
        nuniq = int(pd.to_numeric(df[col], errors="coerce").dropna().nunique())
        if nuniq <= 1:
            structural_constant_fields.append(
                {"series": f"{source_name}.{col}", "reason": "shared_history_window"}
            )

    passed = bool(len(suspicious) == 0 and ((not require_meta) or metadata_available))
    return {
        "metadata_available": bool(metadata_available),
        "variables_checked": int(variables_checked),
        "unit_family_counts": unit_family_counts,
        "percent_conversions": int(percent_conversions),
        "conversion_log_sample": conversion_sample,
        "conversion_log_full_size": int(len(conversion_full)),
        "structural_constant_fields": structural_constant_fields,
        "suspicious_unit_usage": suspicious,
        "warnings": warnings,
        "passed": bool(passed),
    }


def build_gate_overfitting_shadow_audit(
    *,
    critical_failure_details: Sequence[Mapping[str, Any]],
    cert_cfg: Mapping[str, Any],
) -> Dict[str, Any]:
    enabled = bool(cert_cfg.get("shadow_relaxed_audit_enabled", True))
    factor = float(cert_cfg.get("shadow_relaxed_threshold_factor", 1.20))
    factor = float(max(1.01, min(2.50, factor)))
    if not enabled:
        return {
            "enabled": False,
            "relaxed_threshold_factor": factor,
            "currently_failed_rules": 0,
            "would_pass_under_relaxed": [],
            "would_still_fail": [],
            "threshold_pressure_ratio": 0.0,
            "passed": True,
        }

    would_pass: List[str] = []
    still_fail: List[str] = []
    for row in critical_failure_details:
        rule_id = str((row or {}).get("rule_id", ""))
        comp = str((row or {}).get("comparator", "")).strip()
        obs = (row or {}).get("observed")
        thr = (row or {}).get("threshold")
        if rule_id == "" or comp == "":
            continue
        if not isinstance(obs, (int, float)) or not isinstance(thr, (int, float)):
            still_fail.append(rule_id)
            continue
        obs_f = float(obs)
        thr_f = float(thr)
        relaxed_pass = False
        if comp in {"<=", "<"}:
            relaxed_thr = thr_f * factor
            relaxed_pass = obs_f <= relaxed_thr if comp == "<=" else obs_f < relaxed_thr
        elif comp in {">=", ">"}:
            relaxed_thr = thr_f / factor
            relaxed_pass = obs_f >= relaxed_thr if comp == ">=" else obs_f > relaxed_thr
        elif comp == "==":
            relaxed_pass = obs_f == thr_f
        if relaxed_pass:
            would_pass.append(rule_id)
        else:
            still_fail.append(rule_id)

    total = len(set(would_pass + still_fail))
    pressure = float(len(set(would_pass)) / max(1, total))
    return {
        "enabled": True,
        "relaxed_threshold_factor": float(factor),
        "currently_failed_rules": int(total),
        "would_pass_under_relaxed": sorted(set(would_pass)),
        "would_still_fail": sorted(set(still_fail)),
        "threshold_pressure_ratio": float(pressure),
        "passed": True,
    }
