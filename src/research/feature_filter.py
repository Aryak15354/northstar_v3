"""Config-driven feature selection and dead-feature filtering for Kaggle experiments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd
import yaml

from src.research.config_loader import resolve_config_root


NON_FEATURE_COLUMNS = {
    "date",
    "ticker",
    "target_weekly_return",
    "forward_return_5d",
    "forward_return_1w",
    "close",
    "volume",
    "market_cap",
    "market_cap_rank",
    "week_source_date",
    "week_of_year",
    "calendar_year",
}


@dataclass
class FeatureFilterResult:
    candidate_features: list[str]
    selected_features: list[str]
    removed_features: list[str]
    protected_features: list[str]
    forced_features: list[str]
    dropped_redundant_features: list[str]
    coverage_audit: pd.DataFrame


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise TypeError(f"feature_set_must_be_mapping:{path}")
    return payload


def select_numeric_feature_columns(panel: pd.DataFrame) -> list[str]:
    numeric = set(panel.select_dtypes(include=[np.number]).columns)
    return [
        column
        for column in panel.columns
        if column in numeric and column not in NON_FEATURE_COLUMNS and not str(column).endswith("__realized")
    ]


def resolve_feature_candidates(
    features_df: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    nb00_selected_features: Sequence[str] | None = None,
    config_root: str | Path | None = None,
) -> list[str]:
    features_cfg = dict(cfg.get("features") or {})
    source = str(features_cfg.get("source", "") or "").strip().lower()
    if source == "nb00_tier12" and nb00_selected_features:
        return [str(feature) for feature in nb00_selected_features if str(feature) in features_df.columns]

    explicit = [str(feature) for feature in features_cfg.get("selected_features") or [] if str(feature) in features_df.columns]
    if explicit:
        return explicit

    custom_set = str(features_cfg.get("custom_set", "") or "").strip()
    if custom_set:
        root = resolve_config_root(config_root)
        payload = _read_yaml((root / custom_set).resolve())
        explicit = [str(feature) for feature in payload.get("features") or [] if str(feature) in features_df.columns]
        if explicit:
            return explicit

    return select_numeric_feature_columns(features_df)


def build_feature_coverage_audit(
    features_df: pd.DataFrame,
    feature_cols: Sequence[str],
    *,
    null_threshold: float,
    min_unique: int,
    min_cross_sectional_std: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    work = features_df.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce").dt.normalize()
    for feature in feature_cols:
        if feature not in work.columns:
            rows.append(
                {
                    "feature": feature,
                    "present": False,
                    "null_rate": 1.0,
                    "n_unique": 0,
                    "median_cs_std": float("nan"),
                    "likely_dead": True,
                    "dead_reason": "missing_from_export",
                }
            )
            continue

        series = pd.to_numeric(work[feature], errors="coerce")
        cs_std = work.assign(_audit_value=series).groupby("date", sort=False)["_audit_value"].std()
        null_rate = float(series.isna().mean())
        n_unique = int(series.nunique(dropna=True))
        finite_cs_std = cs_std[np.isfinite(cs_std.to_numpy(dtype=float))]
        median_cs_std = float(finite_cs_std.median(skipna=True)) if len(finite_cs_std) else float("nan")

        reasons: list[str] = []
        if null_rate > float(null_threshold):
            reasons.append("high_null_rate")
        if n_unique <= int(min_unique):
            reasons.append("low_unique_values")
        if not np.isfinite(median_cs_std) or median_cs_std < float(min_cross_sectional_std):
            reasons.append("low_cross_sectional_dispersion")

        rows.append(
            {
                "feature": feature,
                "present": True,
                "null_rate": null_rate,
                "n_unique": n_unique,
                "median_cs_std": median_cs_std,
                "likely_dead": bool(reasons),
                "dead_reason": "|".join(reasons),
            }
        )

    return pd.DataFrame(rows).sort_values(
        ["likely_dead", "null_rate", "median_cs_std", "feature"],
        ascending=[False, False, True, True],
        na_position="last",
    ).reset_index(drop=True)


def apply_dead_filter(
    features_df: pd.DataFrame,
    candidate_features: Sequence[str],
    cfg: dict[str, Any],
    *,
    feature_health: pd.DataFrame | None = None,
) -> FeatureFilterResult:
    features_cfg = dict(cfg.get("features") or {})
    dead_cfg = dict(features_cfg.get("dead_filter") or {})

    coverage_audit = build_feature_coverage_audit(
        features_df,
        candidate_features,
        null_threshold=float(dead_cfg.get("null_threshold", 0.80) or 0.80),
        min_unique=int(dead_cfg.get("min_unique", 1) or 1),
        min_cross_sectional_std=float(dead_cfg.get("min_cross_sectional_std", 1e-8) or 1e-8),
    )
    if not bool(dead_cfg.get("enabled", True)):
        return FeatureFilterResult(
            candidate_features=list(candidate_features),
            selected_features=list(candidate_features),
            removed_features=[],
            protected_features=[],
            forced_features=[],
            dropped_redundant_features=[],
            coverage_audit=coverage_audit,
        )

    audit_lookup = coverage_audit.set_index("feature").to_dict(orient="index") if not coverage_audit.empty else {}
    feature_health = feature_health if feature_health is not None else pd.DataFrame()
    health_lookup = feature_health.set_index("feature").to_dict(orient="index") if not feature_health.empty else {}
    min_abs_ic = float(dead_cfg.get("min_abs_ic", 0.002) or 0.002)
    min_abs_tstat = float(dead_cfg.get("min_abs_tstat", 1.5) or 1.5)
    force_include = [str(feature) for feature in features_cfg.get("force_include") or [] if str(feature) in features_df.columns]

    kept: list[str] = []
    removed: list[str] = []
    protected: list[str] = []
    for feature in candidate_features:
        audit_row = audit_lookup.get(str(feature), {})
        likely_dead = bool(audit_row.get("likely_dead", False))
        if not likely_dead or str(feature) in force_include:
            kept.append(str(feature))
            continue

        health_row = health_lookup.get(str(feature), {})
        mean_ic = abs(float(health_row.get("mean_ic", 0.0) or 0.0))
        ic_tstat = abs(float(health_row.get("ic_tstat", 0.0) or 0.0))
        tier = str(health_row.get("tier", "") or "")
        has_support = mean_ic >= min_abs_ic or ic_tstat >= min_abs_tstat or tier in {"TIER_1", "TIER_2"}
        if has_support:
            kept.append(str(feature))
            protected.append(str(feature))
        else:
            removed.append(str(feature))

    dedup_cfg = dict(features_cfg.get("redundancy_dedup") or {})
    dropped_redundant: list[str] = []
    if bool(dedup_cfg.get("enabled", False)):
        exceptions = {str(feature) for feature in dedup_cfg.get("exceptions") or []}
        selected_set = set(kept)
        deduped: list[str] = []
        for feature in kept:
            drop = False
            if feature not in exceptions:
                for rule in dedup_cfg.get("drop_variants") or []:
                    suffix = str(rule.get("suffix", "") or "")
                    if suffix and feature.endswith(suffix) and bool(rule.get("keep_canonical", False)):
                        canonical = feature[: -len(suffix)]
                        if canonical in selected_set:
                            drop = True
                            break
            if drop:
                dropped_redundant.append(feature)
                continue
            deduped.append(feature)
        kept = deduped

    final_selected = list(dict.fromkeys([*kept, *force_include]))
    return FeatureFilterResult(
        candidate_features=list(dict.fromkeys(str(feature) for feature in candidate_features)),
        selected_features=final_selected,
        removed_features=list(dict.fromkeys(removed)),
        protected_features=list(dict.fromkeys(protected)),
        forced_features=list(dict.fromkeys(force_include)),
        dropped_redundant_features=list(dict.fromkeys(dropped_redundant)),
        coverage_audit=coverage_audit,
    )


__all__ = [
    "FeatureFilterResult",
    "apply_dead_filter",
    "build_feature_coverage_audit",
    "resolve_feature_candidates",
    "select_numeric_feature_columns",
]
