"""Shared utilities for the 2026-03-29 Kaggle weekly research sprint."""

from __future__ import annotations

import contextlib
import json
import math
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd
import yaml
from scipy.stats import spearmanr


PROJECT_ROOT = Path(__file__).resolve().parents[3]
WEEK_ID = "2026_03_29"
WEEK_SLUG = "week_2026_03_29"
RAW_BUNDLE_MANIFEST = "northstar_weekly_raw_manifest.json"
FEATURE_EXPORT_FILES = (
    "northstar_features.parquet",
    "northstar_walk_forward_splits.json",
    "northstar_regime_labels.parquet",
    "northstar_metadata.parquet",
)
FULL_SEEDS = [42, 123, 456, 789, 1337]
SMOKE_SEEDS = [42, 123]
PLAN_REGIME_LABELS = {
    "R1": "Low-Vol Bull",
    "R2": "High-Vol Bull",
    "R3": "Low-Vol Bear",
    "R4": "High-Vol Bear",
    "R5": "Recovery",
    "R6": "Sideways",
    "R7": "Rate-Event",
    "R8": "Election/Binary",
    "R9": "External Shock",
}
PLAN_BULL_REGIMES = {"R1", "R2", "R5"}
PLAN_CRASH_REGIMES = {"R4", "R9"}
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
MODEL_EXCLUDED_UNIT_KINDS = {"absolute_scale", "inr_per_share", "count", "text_blob"}
RAW_ABSOLUTE_FEATURE_NAMES = {
    "revenue",
    "sales",
    "gross_profit",
    "ebitda",
    "operating_income",
    "operating_profit",
    "net_income",
    "net_profit",
    "equity",
    "total_assets",
    "total_debt",
    "gross_ppe",
    "working_capital",
    "cash_and_equivalents",
    "operating_cash_flow",
    "free_cash_flow",
    "cost_of_revenue",
    "interest_expense",
    "inventory",
    "receivables",
    "payables",
    "capex",
    "depreciation",
    "other_income",
    "profit_before_tax",
    "expenses",
    "shares_outstanding",
}
PERCENTAGE_FEATURE_NAMES = {
    "agreement_score",
    "posterior_confidence",
    "val_margin_of_safety",
    "market_cap_rank",
}
RATIO_FEATURE_HINTS = ("_ratio", "_yield", "_coverage", "_spread", "_modifier", "_score")
COUNT_FEATURE_HINTS = ("n_shareholders", "_count", "count_")
SCREENER_PERCENT_HINTS = (
    "roce",
    "roe",
    "opm",
    "tax_pct",
    "gross_npa",
    "net_npa",
    "dividend_payout",
    "margin_pct",
    "growth_",
    "promoter_change",
    "fii_change",
    "dii_change",
    "public_pct_change",
    "govt_pct_change",
)
SCREENER_RATIO_HINTS = (
    "_to_",
    "cash_conversion",
    "free_float",
    "institutional_pct",
    "ownership",
)
SCREENER_DAYS_HINTS = (
    "days",
    "cycle",
)


@dataclass
class ExportArtifacts:
    export_dir: Path
    features_path: Path
    splits_path: Path
    regimes_path: Path
    metadata_path: Path


def _safe_spearman(left: Sequence[float], right: Sequence[float]) -> float:
    left_arr = np.asarray(left, dtype=float)
    right_arr = np.asarray(right, dtype=float)
    mask = np.isfinite(left_arr) & np.isfinite(right_arr)
    if int(mask.sum()) < 5:
        return float("nan")
    clean_left = left_arr[mask]
    clean_right = right_arr[mask]
    if np.unique(clean_left).size < 2 or np.unique(clean_right).size < 2:
        return float("nan")
    corr, _ = spearmanr(clean_left, clean_right)
    return float(corr) if np.isfinite(corr) else float("nan")


def safe_spearman(left: Sequence[float], right: Sequence[float]) -> float:
    return _safe_spearman(left, right)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return re.sub(r"\s+", " ", str(value)).strip()


def _normalize_ticker(value: Any) -> str:
    text = _clean_text(value).upper()
    if not text:
        return ""
    if text.endswith(".NS"):
        return text
    if "." in text:
        text = text.split(".", 1)[0]
    return f"{text}.NS"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_ready(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): json_ready(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_ready(v) for v in obj]
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    if isinstance(obj, pd.Series):
        return {str(k): json_ready(v) for k, v in obj.to_dict().items()}
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        value = float(obj)
        return None if not np.isfinite(value) else value
    if isinstance(obj, float):
        return None if not np.isfinite(obj) else obj
    return obj


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_ready(payload), indent=2), encoding="utf-8")


def is_kaggle() -> bool:
    return Path("/kaggle").exists()


def default_results_root() -> Path:
    if is_kaggle():
        return Path("/kaggle/working") / "northstar_v3_weekly_sprint"
    return PROJECT_ROOT / "tmp" / "kaggle_weekly_sprint"


def timestamp_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def make_run_dir(base: Path | None, label: str) -> Path:
    root = (base or default_results_root()).expanduser().resolve()
    run_dir = root / WEEK_SLUG / f"{timestamp_slug()}_{label}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def resolve_raw_bundle_dir(data_dir: str | Path | None = None) -> Path:
    if data_dir is not None:
        candidate = Path(data_dir).expanduser().resolve()
        if not candidate.exists():
            raise FileNotFoundError(f"raw_bundle_missing:{candidate}")
        return candidate

    search_roots = [
        Path.cwd(),
        PROJECT_ROOT,
        default_results_root(),
        Path("/kaggle/input"),
    ]
    for root in search_roots:
        if not root.exists():
            continue
        if (root / RAW_BUNDLE_MANIFEST).exists():
            return root.resolve()
        for manifest in sorted(root.rglob(RAW_BUNDLE_MANIFEST)):
            return manifest.parent.resolve()
        if (root / "data" / "canonical").exists() and (root / "universe" / "nifty500.csv").exists():
            return root.resolve()
    raise FileNotFoundError("could_not_resolve_weekly_raw_bundle")


def resolve_export_dir(export_dir: str | Path | None = None) -> ExportArtifacts:
    if export_dir is not None:
        base = Path(export_dir).expanduser().resolve()
        if not base.exists():
            raise FileNotFoundError(f"feature_export_missing:{base}")
        missing = [name for name in FEATURE_EXPORT_FILES if not (base / name).exists()]
        if missing:
            raise FileNotFoundError(f"feature_export_missing_files:{missing} in {base}")
        return ExportArtifacts(
            export_dir=base,
            features_path=base / "northstar_features.parquet",
            splits_path=base / "northstar_walk_forward_splits.json",
            regimes_path=base / "northstar_regime_labels.parquet",
            metadata_path=base / "northstar_metadata.parquet",
        )

    search_roots = [Path.cwd(), default_results_root(), PROJECT_ROOT / "tmp"]
    for root in search_roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("northstar_features.parquet"), reverse=True):
            candidate = path.parent
            missing = [name for name in FEATURE_EXPORT_FILES if not (candidate / name).exists()]
            if missing:
                continue
            return ExportArtifacts(
                export_dir=candidate,
                features_path=candidate / "northstar_features.parquet",
                splits_path=candidate / "northstar_walk_forward_splits.json",
                regimes_path=candidate / "northstar_regime_labels.parquet",
                metadata_path=candidate / "northstar_metadata.parquet",
            )
    raise FileNotFoundError("could_not_resolve_weekly_feature_export")


def load_export_manifest(export_dir: str | Path) -> dict[str, Any]:
    export_path = Path(export_dir).expanduser().resolve()
    manifest_path = export_path / "weekly_export_manifest.json"
    if not manifest_path.exists():
        return {}
    return read_json(manifest_path)


def resolve_raw_bundle_from_export(export_dir: str | Path, explicit_data_dir: str | Path | None = None) -> Path:
    if explicit_data_dir is not None:
        return resolve_raw_bundle_dir(explicit_data_dir)
    manifest = load_export_manifest(export_dir)
    raw_bundle = str(manifest.get("raw_bundle_dir", "") or "").strip()
    if raw_bundle:
        candidate = Path(raw_bundle).expanduser().resolve()
        if candidate.exists():
            return candidate
    return resolve_raw_bundle_dir(None)


def _remove_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    shutil.rmtree(path)


def symlink_or_copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _remove_path(dest)
    try:
        if src.is_dir():
            os.symlink(src, dest, target_is_directory=True)
        else:
            os.symlink(src, dest)
    except OSError:
        if src.is_dir():
            shutil.copytree(src, dest)
        else:
            shutil.copy2(src, dest)


def prepare_runtime_project(raw_bundle_dir: Path, runtime_root: Path) -> Path:
    runtime_root = runtime_root.expanduser().resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)
    for rel in ["data", "universe", "config"]:
        src = raw_bundle_dir / rel
        if src.exists():
            symlink_or_copy(src, runtime_root / rel)
    (runtime_root / "reports").mkdir(parents=True, exist_ok=True)
    return runtime_root


@contextlib.contextmanager
def working_directory(path: Path):
    prior = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prior)


def build_runtime_policy_dict(
    *,
    start_date: str | None,
    end_date: str | None,
    lookback_days: int,
    max_tickers: int,
    max_rows: int,
    low_resource_mode: str,
    profile: str,
) -> dict[str, Any]:
    valuation_enabled = str(profile).strip().lower() != "smoke"
    gap9_enabled = True
    return {
        "historical_research": {
            "regime_labels_path": "data/processed/regime_labels.parquet",
            "dataset": {
                "prices_path": "data/canonical/prices/equity_prices_daily.parquet",
                "fundamentals_path": "data/canonical/fundamentals/fundamentals_annual_panel.parquet",
                "macro_features_path": "data/canonical/macro/macro_regime_features.parquet",
                "valuation_posterior_path": "data/processed/valuation_posterior.parquet",
                "screener_fundamentals_path": "data/canonical/fundamentals/fundamentals_annual_panel.csv",
                "screener_quarterly_path": "data/canonical/fundamentals/fundamentals_quarterly_panel.csv",
                "screener_shareholding_path": "data/canonical/fundamentals/shareholding_quarterly.csv",
                "announcement_dates_path": "data/processed/alternative/earnings_dates_all.csv",
                "alternative_data_path": "data/canonical/alternative",
                "sentiment_feature_mode": "reduced",
                "enable_macro_features": True,
                "use_macro_features": True,
                "use_screener_features": True,
                "use_alternative_features": True,
                "use_sentiment_features": False,
                "use_gap9_academic_factors": gap9_enabled,
                "lookback_days": int(max(180, lookback_days)),
                "max_tickers": int(max(0, max_tickers)),
                "max_rows": int(max(0, max_rows)),
                "low_resource_mode": str(low_resource_mode),
                "strict_real_data_only": True,
                "strict_required_artifacts": ["prices", "fundamentals", "macro", "valuation_posterior"],
                "target_horizon_days": 5,
                "valuation": {
                    "features_enabled": valuation_enabled,
                    "feature_columns": "zscore_only",
                    "allow_prior_cache_fallback": True,
                    "max_cache_fallback_age_days": 7,
                },
                "feature_groups": {
                    "gap9_academic_factors": {
                        "enabled": gap9_enabled,
                    }
                },
                "start_date": start_date,
                "end_date": end_date,
                "screener_data_path": "data/raw/vendors/screener/financials",
                "screener_metadata_path": "data/raw/vendors/screener/metadata",
            },
        }
    }


def write_runtime_policy(
    runtime_root: Path,
    *,
    start_date: str | None,
    end_date: str | None,
    lookback_days: int,
    max_tickers: int,
    max_rows: int,
    low_resource_mode: str,
    profile: str,
) -> Path:
    payload = build_runtime_policy_dict(
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
        max_tickers=max_tickers,
        max_rows=max_rows,
        low_resource_mode=low_resource_mode,
        profile=profile,
    )
    config_dir = runtime_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "research_policy.yaml"
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return path


def select_feature_columns(panel: pd.DataFrame) -> list[str]:
    feature_cols: list[str] = []
    for column in panel.columns:
        name = str(column)
        if name in NON_FEATURE_COLUMNS:
            continue
        if name.startswith("forward_return_") or name.startswith("target_") or name.endswith("__realized"):
            continue
        if name.endswith("_raw") or "_raw_" in name or name.startswith(("screener_raw_", "native_")):
            continue
        if name.endswith("_date") or name.endswith("_datetime"):
            continue
        if pd.api.types.is_datetime64_any_dtype(panel[column]) or pd.api.types.is_timedelta64_dtype(panel[column]):
            continue
        if pd.api.types.is_numeric_dtype(panel[column]):
            if infer_feature_unit_kind(name) in MODEL_EXCLUDED_UNIT_KINDS:
                continue
            feature_cols.append(name)
    return sorted(dict.fromkeys(feature_cols))


def cast_feature_frame(panel: pd.DataFrame, feature_cols: Sequence[str]) -> pd.DataFrame:
    keep = ["date", "ticker"] + list(feature_cols) + ["target_weekly_return"]
    out = panel[keep].copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out["ticker"] = out["ticker"].astype("string")
    numeric_cols = [col for col in keep if col not in {"date", "ticker"}]
    for column in numeric_cols:
        out[column] = pd.to_numeric(out[column], errors="coerce").astype("float32")
    return out.sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)


def cast_metadata_frame(panel: pd.DataFrame) -> pd.DataFrame:
    keep = [
        col
        for col in [
            "date",
            "ticker",
            "close",
            "volume",
            "market_cap",
            "market_cap_rank",
            "sector",
            "industry",
            "broad_sector",
            "subsector",
            "hq_city",
            "conglomerate_group",
            "international_brand_mnc_subsidiary",
            "commodity_sensitivities",
            "sector_macro_sensitivities",
            "key_interconnections_peers",
            "business_cycle_bucket",
            "plan_regime_id",
            "plan_regime_label",
            "major_event_id",
            "subtle_period_id",
            "fii_pct",
            "promoter_pct",
            "dii_pct",
            "public_pct",
            "macro_linkage_score",
            "international_revenue_proxy",
            "oil_sensitivity_score",
            "steel_sensitivity_score",
            "copper_sensitivity_score",
            "gold_sensitivity_score",
            "fx_sensitivity_score",
            "rate_sensitivity_score",
        ]
        if col in panel.columns
    ]
    out = panel[keep].copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out["ticker"] = out["ticker"].astype("string")
    for column in [c for c in out.columns if c not in {"date", "ticker"}]:
        if pd.api.types.is_numeric_dtype(out[column]):
            out[column] = pd.to_numeric(out[column], errors="coerce").astype("float32")
    return out.sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)


def derive_size_rank(frame: pd.DataFrame) -> pd.Series:
    if frame is None or frame.empty:
        return pd.Series(dtype=float)
    if "market_cap_rank" in frame.columns:
        return pd.to_numeric(frame["market_cap_rank"], errors="coerce").astype(float)

    basis_col = next((col for col in ["market_cap", "close"] if col in frame.columns), None)
    if basis_col is None:
        return pd.Series(np.nan, index=frame.index, dtype=float)

    basis = pd.to_numeric(frame[basis_col], errors="coerce")
    if "date" not in frame.columns:
        return basis.rank(method="average", pct=True).astype(float)

    dates = pd.to_datetime(frame["date"], errors="coerce")
    return basis.groupby(dates, sort=False).rank(method="average", pct=True).astype(float)


def resample_daily_panel_to_weekly(panel: pd.DataFrame) -> pd.DataFrame:
    work = panel.copy()
    work["date"] = pd.to_datetime(work["date"], errors="coerce").dt.normalize()
    work = work.dropna(subset=["date", "ticker"]).sort_values(["ticker", "date"], kind="mergesort")
    work["week_end"] = work["date"].dt.to_period("W-FRI").dt.end_time.dt.normalize()
    weekly = work.groupby(["ticker", "week_end"], sort=True, as_index=False).tail(1).copy()
    weekly = weekly.rename(columns={"date": "week_source_date"})
    weekly["date"] = pd.to_datetime(weekly["week_end"], errors="coerce").dt.normalize()
    weekly = weekly.drop(columns=["week_end"], errors="ignore")
    weekly["calendar_year"] = weekly["date"].dt.year
    weekly["week_of_year"] = weekly["date"].dt.isocalendar().week.astype(int)
    if "close" in weekly.columns:
        weekly["forward_return_1w"] = (
            pd.to_numeric(weekly["close"], errors="coerce")
            .groupby(weekly["ticker"], sort=False)
            .shift(-1)
            / pd.to_numeric(weekly["close"], errors="coerce")
        ) - 1.0
        weekly["forward_return_5d"] = pd.to_numeric(weekly["forward_return_1w"], errors="coerce")
        weekly["target_weekly_return"] = pd.to_numeric(weekly["forward_return_1w"], errors="coerce")
    elif "target_weekly_return" not in weekly.columns:
        weekly["target_weekly_return"] = np.nan
        weekly["forward_return_5d"] = np.nan
    return weekly.sort_values(["date", "ticker"], kind="mergesort").reset_index(drop=True)


def build_market_cap_fields(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    if {"close", "shares_outstanding"}.issubset(set(out.columns)):
        market_cap = (
            pd.to_numeric(out["close"], errors="coerce")
            * pd.to_numeric(out["shares_outstanding"], errors="coerce")
        )
        out["market_cap"] = market_cap.astype(float)
    if "market_cap" in out.columns:
        out["market_cap_rank"] = (
            pd.to_numeric(out["market_cap"], errors="coerce")
            .groupby(out["date"], sort=False)
            .rank(method="average", pct=True)
            .astype(float)
        )
    return out


def _text_token_score(text: str, positive_tokens: Sequence[str], negative_tokens: Sequence[str] | None = None) -> float:
    raw = _clean_text(text).lower()
    if not raw:
        return 0.0
    pos = float(sum(1 for token in positive_tokens if token in raw))
    neg = float(sum(1 for token in (negative_tokens or []) if token in raw))
    if pos <= 0 and neg <= 0:
        return 0.0
    total = max(pos + neg, 1.0)
    return float((pos - neg) / total)


def _count_list_like_items(text: str) -> int:
    raw = _clean_text(text)
    if not raw:
        return 0
    parts = [token.strip() for token in re.split(r"[;,]| and ", raw) if token.strip()]
    return len(parts)


def _business_cycle_bucket(text: str, broad_sector: str) -> str:
    raw = f"{_clean_text(text).lower()} {_clean_text(broad_sector).lower()}"
    cyclical_tokens = ["capex", "commodity", "industrial", "energy", "auto", "infra", "real estate", "power"]
    defensive_tokens = ["pharma", "healthcare", "fmcg", "consumer staples", "utilities", "telecom"]
    cyclical_hits = sum(1 for token in cyclical_tokens if token in raw)
    defensive_hits = sum(1 for token in defensive_tokens if token in raw)
    if cyclical_hits > defensive_hits:
        return "cyclical"
    if defensive_hits > cyclical_hits:
        return "defensive"
    return "mixed"


def attach_universe_annotations(panel: pd.DataFrame, raw_bundle_dir: Path) -> pd.DataFrame:
    universe_path = raw_bundle_dir / "data" / "canonical" / "reference" / "universe" / "nifty500_universe_enriched.parquet"
    if not universe_path.exists():
        return panel
    universe = pd.read_parquet(universe_path)
    universe["ticker"] = universe.get("ticker", universe.get("symbol", "")).map(_normalize_ticker)
    universe = universe.dropna(subset=["ticker"]).drop_duplicates(subset=["ticker"], keep="last")
    out = panel.merge(universe, on="ticker", how="left", sort=False)

    commodity_text = out.get("commodity_sensitivities", pd.Series("", index=out.index)).astype("string")
    macro_text = out.get("sector_macro_sensitivities", pd.Series("", index=out.index)).astype("string")
    peers_text = out.get("key_interconnections_peers", pd.Series("", index=out.index)).astype("string")
    broad_sector = out.get("broad_sector", pd.Series("", index=out.index)).astype("string")
    mnc_flag = out.get("international_brand_mnc_subsidiary", pd.Series("", index=out.index)).astype("string")
    conglomerate = out.get("conglomerate_group", pd.Series("", index=out.index)).astype("string")

    out["international_revenue_proxy"] = [
        max(
            _text_token_score(f"{c} {m}", ["usd", "export", "international", "global", "overseas", "mnc"], []),
            1.0 if "yes" in _clean_text(m).lower() else 0.0,
        )
        for c, m in zip(commodity_text, mnc_flag, strict=False)
    ]
    out["oil_sensitivity_score"] = [
        _text_token_score(
            f"{c} {m} {b}",
            ["crude", "oil", "brent", "fuel", "energy"],
            ["benefit from lower oil", "benefit from soft crude"],
        )
        for c, m, b in zip(commodity_text, macro_text, broad_sector, strict=False)
    ]
    out["steel_sensitivity_score"] = [
        _text_token_score(f"{c} {m} {b}", ["steel", "hrc", "iron ore", "metals"], [])
        for c, m, b in zip(commodity_text, macro_text, broad_sector, strict=False)
    ]
    out["copper_sensitivity_score"] = [
        _text_token_score(f"{c} {m} {b}", ["copper", "electrical", "wiring", "ev"], [])
        for c, m, b in zip(commodity_text, macro_text, broad_sector, strict=False)
    ]
    out["gold_sensitivity_score"] = [
        _text_token_score(f"{c} {m} {b}", ["gold", "jewellery", "consumption spending"], [])
        for c, m, b in zip(commodity_text, macro_text, broad_sector, strict=False)
    ]
    out["fx_sensitivity_score"] = [
        _text_token_score(f"{c} {m}", ["fx", "currency", "usd", "eur", "inr", "export", "import"], [])
        for c, m in zip(commodity_text, macro_text, strict=False)
    ]
    out["rate_sensitivity_score"] = [
        _text_token_score(f"{m} {b}", ["rate", "yield", "rbi", "repo", "credit", "nbfc", "bank"], [])
        for m, b in zip(macro_text, broad_sector, strict=False)
    ]
    out["business_cycle_bucket"] = [
        _business_cycle_bucket(f"{m} {c}", b)
        for m, c, b in zip(macro_text, commodity_text, broad_sector, strict=False)
    ]

    commodity_complexity = commodity_text.map(lambda value: min(_count_list_like_items(str(value)), 6) / 6.0).astype(float)
    macro_complexity = macro_text.map(lambda value: min(_count_list_like_items(str(value)), 6) / 6.0).astype(float)
    peer_complexity = peers_text.map(lambda value: min(_count_list_like_items(str(value)), 6) / 6.0).astype(float)
    conglomerate_flag = conglomerate.map(lambda value: 1.0 if _clean_text(value) else 0.0).astype(float)
    mnc_numeric = mnc_flag.map(lambda value: 1.0 if "yes" in _clean_text(value).lower() else 0.0).astype(float)
    out["macro_linkage_score"] = (
        0.20 * commodity_complexity
        + 0.25 * macro_complexity
        + 0.15 * peer_complexity
        + 0.20 * conglomerate_flag
        + 0.20 * mnc_numeric
    ).clip(lower=0.0, upper=1.0)
    return out


def generate_anchored_weekly_splits(
    weekly_dates: Sequence[pd.Timestamp],
    *,
    anchor_start: str = "2019-01-01",
    train_weeks: int = 104,
    test_weeks: int = 13,
    step_weeks: int = 13,
    target_windows: int = 20,
) -> list[dict[str, Any]]:
    dates = (
        pd.Series(pd.to_datetime(list(weekly_dates), errors="coerce"))
        .dropna()
        .drop_duplicates()
        .sort_values()
        .tolist()
    )
    if len(dates) < train_weeks + test_weeks:
        raise ValueError(f"insufficient_weekly_dates:{len(dates)}<{train_weeks + test_weeks}")
    anchor = pd.Timestamp(anchor_start).normalize()
    dates = [pd.Timestamp(value).normalize() for value in dates if pd.Timestamp(value).normalize() >= anchor]
    if len(dates) < train_weeks + test_weeks:
        raise ValueError(f"insufficient_anchor_aligned_dates:{len(dates)}<{train_weeks + test_weeks}")

    windows: list[dict[str, Any]] = []
    for test_start_idx in range(train_weeks, len(dates) - test_weeks + 1, step_weeks):
        test_end_idx = test_start_idx + test_weeks - 1
        windows.append(
            {
                "window_id": len(windows) + 1,
                "train_start": str(dates[0].date()),
                "train_end": str(dates[test_start_idx - 1].date()),
                "test_start": str(dates[test_start_idx].date()),
                "test_end": str(dates[test_end_idx].date()),
            }
        )
    if target_windows > 0 and len(windows) > target_windows:
        windows = windows[-target_windows:]
        for idx, window in enumerate(windows, start=1):
            window["window_id"] = idx
    return windows


def build_screener_metric_unit_registry(raw_bundle_dir: Path) -> pd.DataFrame:
    base = raw_bundle_dir / "data" / "raw" / "vendors" / "screener"
    if not base.exists():
        return pd.DataFrame(columns=["metric", "unit_kind", "canonical_column", "source_files"])
    metrics: dict[str, set[str]] = {}
    for path in sorted(base.rglob("*.csv")):
        try:
            sample = pd.read_csv(path, usecols=["metric"])
        except Exception:
            continue
        for metric in sample["metric"].dropna().astype(str):
            metrics.setdefault(metric, set()).add(str(path.relative_to(raw_bundle_dir)))

    rows: list[dict[str, Any]] = []
    for metric, sources in sorted(metrics.items()):
        clean = _clean_text(metric)
        lower = clean.lower()
        if "%" in clean or lower.endswith(" pct") or lower in {"opm", "roe", "roce", "dividend payout"}:
            unit_kind = "percentage_points"
        elif "days" in lower or "cycle" in lower:
            unit_kind = "days"
        elif "eps" in lower:
            unit_kind = "inr_per_share"
        elif lower == "raw pdf":
            unit_kind = "text_blob"
        else:
            unit_kind = "inr_crore"
        canonical = re.sub(r"[^a-z0-9]+", "_", lower.replace("%", " pct ")).strip("_")
        rows.append(
            {
                "metric": clean,
                "unit_kind": unit_kind,
                "canonical_column": canonical,
                "source_files": sorted(sources),
            }
        )
    return pd.DataFrame(rows)


def infer_feature_unit_kind(feature_name: str) -> str:
    name = str(feature_name)
    lower = name.lower()
    if lower.endswith("_cs_rank") or lower.endswith("_rank"):
        return "rank_0_1"
    if lower.endswith("_cs_z") or lower.endswith("_ts_z") or lower.endswith("_zscore"):
        return "standardized_score"
    if lower.startswith("screener_") and any(token in lower for token in SCREENER_DAYS_HINTS):
        return "days"
    if lower.startswith("screener_") and "eps" in lower:
        return "inr_per_share"
    if lower.startswith("screener_") and any(token in lower for token in SCREENER_PERCENT_HINTS):
        return "percentage_points"
    if lower.startswith("screener_") and any(token in lower for token in SCREENER_RATIO_HINTS):
        return "ratio"
    if lower.endswith("_pct") or lower in {item.lower() for item in PERCENTAGE_FEATURE_NAMES}:
        return "percentage_points"
    if lower.endswith("_days") or "days" in lower:
        return "days"
    if lower.endswith("_score") or lower.endswith("_confidence"):
        return "bounded_score"
    if any(token in lower for token in RATIO_FEATURE_HINTS) or "_to_" in lower:
        return "ratio"
    if any(token in lower for token in COUNT_FEATURE_HINTS):
        return "count"
    if lower.startswith("val_") and lower.endswith("_pct"):
        return "percentage_points"
    if lower in RAW_ABSOLUTE_FEATURE_NAMES or lower.startswith(("screener_", "native_")):
        return "absolute_scale"
    return "numeric"


def build_feature_unit_registry(features_df: pd.DataFrame) -> list[dict[str, Any]]:
    feature_cols = select_feature_columns(features_df)
    rows: list[dict[str, Any]] = []
    for feature in feature_cols:
        series = pd.to_numeric(features_df[feature], errors="coerce")
        rows.append(
            {
                "feature": feature,
                "unit_kind": infer_feature_unit_kind(feature),
                "model_safe": infer_feature_unit_kind(feature) not in MODEL_EXCLUDED_UNIT_KINDS,
                "coverage": float(series.notna().mean()),
                "min": None if series.dropna().empty else float(series.min()),
                "max": None if series.dropna().empty else float(series.max()),
            }
        )
    return rows


def load_export_artifacts(export_dir: str | Path | None = None) -> tuple[pd.DataFrame, list[dict[str, Any]], pd.DataFrame, pd.DataFrame]:
    artifacts = resolve_export_dir(export_dir)
    features = pd.read_parquet(artifacts.features_path)
    features["date"] = pd.to_datetime(features["date"], errors="coerce").dt.normalize()
    features["ticker"] = features["ticker"].astype("string")
    splits = read_json(artifacts.splits_path)
    regimes = pd.read_parquet(artifacts.regimes_path)
    regimes["date"] = pd.to_datetime(regimes["date"], errors="coerce").dt.normalize()
    metadata = pd.read_parquet(artifacts.metadata_path)
    metadata["date"] = pd.to_datetime(metadata["date"], errors="coerce").dt.normalize()
    metadata["ticker"] = metadata["ticker"].astype("string")
    return features, splits, regimes, metadata


def subset_feature_export(
    *,
    source_dir: str | Path,
    output_dir: str | Path,
    selected_features: Sequence[str] | None = None,
    ticker_mask: Sequence[str] | None = None,
    date_min: str | None = None,
    date_max: str | None = None,
) -> ExportArtifacts:
    artifacts = resolve_export_dir(source_dir)
    features, splits, regimes, metadata = load_export_artifacts(artifacts.export_dir)

    tickers = {_normalize_ticker(value) for value in (ticker_mask or []) if _normalize_ticker(value)}
    if tickers:
        features = features[features["ticker"].astype(str).isin(tickers)].copy()
        metadata = metadata[metadata["ticker"].astype(str).isin(tickers)].copy()

    start = pd.Timestamp(date_min).normalize() if date_min else None
    end = pd.Timestamp(date_max).normalize() if date_max else None
    if start is not None:
        features = features[features["date"] >= start].copy()
        metadata = metadata[metadata["date"] >= start].copy()
        regimes = regimes[regimes["date"] >= start].copy()
    if end is not None:
        features = features[features["date"] <= end].copy()
        metadata = metadata[metadata["date"] <= end].copy()
        regimes = regimes[regimes["date"] <= end].copy()

    base_cols = ["date", "ticker", "target_weekly_return"]
    if selected_features:
        selected = [feature for feature in selected_features if feature in features.columns]
        features = features[base_cols[:2] + selected + [base_cols[-1]]].copy()

    output_root = Path(output_dir).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    features.to_parquet(output_root / "northstar_features.parquet", index=False)
    metadata.to_parquet(output_root / "northstar_metadata.parquet", index=False)
    regimes.to_parquet(output_root / "northstar_regime_labels.parquet", index=False)
    write_json(output_root / "northstar_walk_forward_splits.json", splits)

    return ExportArtifacts(
        export_dir=output_root,
        features_path=output_root / "northstar_features.parquet",
        splits_path=output_root / "northstar_walk_forward_splits.json",
        regimes_path=output_root / "northstar_regime_labels.parquet",
        metadata_path=output_root / "northstar_metadata.parquet",
    )


def compute_window_feature_ic(
    features_df: pd.DataFrame,
    splits: Sequence[dict[str, Any]],
    feature_cols: Sequence[str],
    *,
    target_col: str = "target_weekly_return",
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for split in splits:
        test_start = pd.Timestamp(split["test_start"]).normalize()
        test_end = pd.Timestamp(split["test_end"]).normalize()
        subset = features_df.loc[features_df["date"].between(test_start, test_end)].copy()
        if subset.empty:
            continue
        for feature in feature_cols:
            date_ics: list[float] = []
            for _, group in subset.groupby("date", sort=True):
                local = group[[feature, target_col]].replace([np.inf, -np.inf], np.nan).dropna()
                if len(local) < 8:
                    continue
                corr = _safe_spearman(local[feature].to_numpy(dtype=float), local[target_col].to_numpy(dtype=float))
                if np.isfinite(corr):
                    date_ics.append(float(corr))
            rows.append(
                {
                    "window_id": int(split["window_id"]),
                    "feature": feature,
                    "mean_ic": float(np.mean(date_ics)) if date_ics else float("nan"),
                    "ic_std": float(np.std(date_ics, ddof=1)) if len(date_ics) > 1 else float("nan"),
                    "n_dates": int(len(date_ics)),
                }
            )
    return pd.DataFrame(rows)


def mean_ic_summary(values: Sequence[float]) -> dict[str, float]:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return {
            "mean_ic": float("nan"),
            "ic_tstat": float("nan"),
            "ic_ir": float("nan"),
            "hit_rate": float("nan"),
            "n_obs": 0.0,
        }
    mean_ic = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if arr.size > 1 else float("nan")
    stderr = std / math.sqrt(arr.size) if np.isfinite(std) and std > 0 else float("nan")
    tstat = mean_ic / stderr if np.isfinite(stderr) and stderr > 0 else float("nan")
    ic_ir = mean_ic / std if np.isfinite(std) and std > 0 else float("nan")
    return {
        "mean_ic": mean_ic,
        "ic_tstat": tstat,
        "ic_ir": ic_ir,
        "hit_rate": float(np.mean(arr > 0)),
        "n_obs": float(arr.size),
    }


def build_plan_regime_labels(weekly_panel: pd.DataFrame, raw_bundle_dir: Path) -> pd.DataFrame:
    panel = weekly_panel.copy()
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce").dt.normalize()
    market = (
        panel.groupby("date", as_index=False)
        .agg(
            market_median_return=("target_weekly_return", "median"),
            market_mean_return=("target_weekly_return", "mean"),
            market_dispersion=("target_weekly_return", "std"),
        )
        .sort_values("date", kind="mergesort")
        .reset_index(drop=True)
    )
    if "close" in panel.columns:
        market_close = (
            panel.groupby("date", as_index=False)
            .agg(market_close=("close", "median"))
            .sort_values("date", kind="mergesort")
        )
        market = market.merge(market_close, on="date", how="left", sort=False)
        market["market_return_4w"] = pd.to_numeric(market["market_close"], errors="coerce").pct_change(4)
    else:
        market["market_return_4w"] = pd.to_numeric(market["market_mean_return"], errors="coerce").rolling(4).mean()
    market["market_vol_13w"] = pd.to_numeric(market["market_mean_return"], errors="coerce").rolling(13).std()

    vol_threshold = float(market["market_vol_13w"].median(skipna=True) or 0.04)
    calm_threshold = float(market["market_vol_13w"].quantile(0.35) or 0.02)

    def _fallback_bucket(row: pd.Series) -> tuple[str, str]:
        ret = float(pd.to_numeric(row.get("market_return_4w"), errors="coerce") or 0.0)
        vol = float(pd.to_numeric(row.get("market_vol_13w"), errors="coerce") or 0.0)
        if abs(ret) < 0.01:
            return "R6", PLAN_REGIME_LABELS["R6"]
        if ret > 0 and vol <= calm_threshold:
            return "R1", PLAN_REGIME_LABELS["R1"]
        if ret > 0 and vol > calm_threshold:
            return "R2", PLAN_REGIME_LABELS["R2"]
        if ret < 0 and vol <= vol_threshold:
            return "R3", PLAN_REGIME_LABELS["R3"]
        return "R4", PLAN_REGIME_LABELS["R4"]

    buckets = market.apply(_fallback_bucket, axis=1)
    market["plan_regime_id"] = buckets.map(lambda item: item[0])
    market["plan_regime_label"] = buckets.map(lambda item: item[1])
    market["source_layer"] = "fallback_market_profile"
    market["major_event_id"] = pd.NA
    market["subtle_period_id"] = pd.NA

    major_path = raw_bundle_dir / "data" / "canonical" / "reference" / "regimes" / "nse_regime_events_major.parquet"
    subtle_path = raw_bundle_dir / "data" / "canonical" / "reference" / "regimes" / "nse_regime_periods_subtle.parquet"

    def _bucket_from_text(text: str, severity: float | None = None) -> str | None:
        lower = _clean_text(text).lower()
        sev = float(severity) if severity is not None and pd.notna(severity) else float("nan")
        if any(token in lower for token in ["election", "binary", "policy shock", "demonetization"]):
            return "R8"
        if any(token in lower for token in ["rate", "rbi", "mpc"]):
            return "R7"
        if any(token in lower for token in ["currency crisis", "external shock", "trade war", "geopolitical", "external pressure"]):
            return "R9"
        if any(token in lower for token in ["recovery", "v-shaped", "policy recovery"]):
            return "R5"
        if any(token in lower for token in ["severe bear", "systemic crash", "crash", "credit crisis"]):
            return "R4"
        if any(token in lower for token in ["bear", "correction", "stagflation"]):
            return "R4" if np.isfinite(sev) and sev >= 8 else "R3"
        if any(token in lower for token in ["bull", "euphoria", "stimulus bull", "strong bull"]):
            return "R2" if np.isfinite(sev) and sev >= 8 else "R1"
        return None

    if subtle_path.exists():
        subtle = pd.read_parquet(subtle_path)
        subtle["start_date"] = pd.to_datetime(subtle["start_date"], errors="coerce").dt.normalize()
        subtle["end_date"] = pd.to_datetime(subtle["end_date"], errors="coerce").dt.normalize()
        for _, row in subtle.iterrows():
            bucket = _bucket_from_text(f"{row.get('subtle_type', '')} {row.get('period_name', '')}")
            if bucket is None:
                continue
            mask = market["date"].between(row["start_date"], row["end_date"])
            market.loc[mask, "plan_regime_id"] = bucket
            market.loc[mask, "plan_regime_label"] = PLAN_REGIME_LABELS[bucket]
            market.loc[mask, "source_layer"] = "subtle_period_overlay"
            market.loc[mask, "subtle_period_id"] = row.get("period_id")

    if major_path.exists():
        major = pd.read_parquet(major_path)
        major["start_date"] = pd.to_datetime(major["start_date"], errors="coerce").dt.normalize()
        major["end_date"] = pd.to_datetime(major["end_date"], errors="coerce").dt.normalize()
        for _, row in major.iterrows():
            bucket = _bucket_from_text(
                f"{row.get('regime_type', '')} {row.get('event_name', '')}",
                row.get("severity_score_1_10"),
            )
            if bucket is None:
                continue
            mask = market["date"].between(row["start_date"], row["end_date"])
            market.loc[mask, "plan_regime_id"] = bucket
            market.loc[mask, "plan_regime_label"] = PLAN_REGIME_LABELS[bucket]
            market.loc[mask, "source_layer"] = "major_event_overlay"
            market.loc[mask, "major_event_id"] = row.get("event_id")

    market["regime"] = market["plan_regime_id"] + "|" + market["plan_regime_label"]
    return market[
        [
            "date",
            "plan_regime_id",
            "plan_regime_label",
            "regime",
            "source_layer",
            "major_event_id",
            "subtle_period_id",
            "market_mean_return",
            "market_dispersion",
            "market_return_4w",
            "market_vol_13w",
        ]
    ].copy()


def merge_regimes_into_panel(panel: pd.DataFrame, regimes: pd.DataFrame) -> pd.DataFrame:
    out = panel.merge(
        regimes[
            ["date", "plan_regime_id", "plan_regime_label", "major_event_id", "subtle_period_id"]
        ],
        on="date",
        how="left",
        sort=False,
    )
    return out
