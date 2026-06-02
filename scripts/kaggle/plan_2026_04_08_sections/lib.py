#!/usr/bin/env python3
"""Shared helpers for section-level compendium runners."""

from __future__ import annotations

import argparse
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_05.catalog import get_experiment_spec, load_experiment_catalog, load_plan_info
from scripts.kaggle.plan_2026_04_05.common import (
    PlanDataset,
    json_ready,
    load_major_events,
    load_plan_dataset,
    make_experiment_paths,
    write_json,
    write_narrative,
)
from scripts.kaggle.plan_2026_04_05.model_redemption import run_redemption_experiment
from scripts.kaggle.plan_2026_04_05.regime_campaign import run_regime_experiment
from scripts.kaggle.plan_2026_04_05.signal_expansion import run_signal_experiment
from scripts.kaggle.plan_2026_04_05.signal_verification import run_verification_experiment
from scripts.kaggle.week_2026_03_29.common import resolve_export_dir as resolve_weekly_export_dir
from scripts.kaggle.plan_2026_04_08.lib import (
    DEFAULT_CANONICAL_FACTOR_ALIASES,
    DEFAULT_EXP18_FIXED_EVENTS,
    DOC_ANCHOR_FACTOR_ALIASES,
    RUNNERS as SEPARATE_RUNNERS,
    _factor_alias_contract,
    resolve_capital_goods_tickers,
    resolve_financial_services_universes,
    resolve_it_tickers,
)


PLAN_INFO = load_plan_info()
EXPERIMENT_CATALOG = load_experiment_catalog()
DEFAULT_VERSION = "apr08_sections_v1"
SECTION_FAMILY_RUNNERS: dict[str, Callable[..., dict[str, Any]]] = {
    "redemption": run_redemption_experiment,
    "regime": run_regime_experiment,
    "signal": run_signal_experiment,
    "verification": run_verification_experiment,
}


def _default_export_candidates() -> list[Path]:
    roots: list[Path] = []
    for candidate_root in [Path.cwd(), *Path.cwd().parents, PROJECT_ROOT]:
        try:
            resolved = candidate_root.resolve()
        except Exception:
            resolved = candidate_root
        if resolved not in roots:
            roots.append(resolved)

    candidates: list[Path] = []
    for root in roots:
        candidates.extend(
            [
                root / "tmp" / "kaggle_uploads" / "northstar_v3_feature_export_augmented_20260408",
                root / "tmp" / "kaggle_uploads" / "northstar_v3_feature_export_robust_20260405",
                root / "tmp" / "northstar_v3_chunk_build_2019_merge_verify",
            ]
        )
    candidates.extend(
        [
            Path("/kaggle/input/northstar-v3-feature-export"),
            Path("/kaggle/input/northstar-v3-feature-export-1"),
            Path("/kaggle/input/northstar-v3-feature-export-2"),
        ]
    )

    deduped: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)
    return deduped


def _default_output_root() -> Path:
    kaggle_root = Path("/kaggle/working")
    if kaggle_root.exists() and os.access(kaggle_root, os.W_OK):
        return kaggle_root / "runs" / "compendium_section_scripts_v1"

    cwd = Path.cwd()
    candidate_roots: list[Path] = []
    for root in [cwd, *cwd.parents]:
        try:
            resolved = root.resolve()
        except Exception:
            resolved = root
        if resolved not in candidate_roots:
            candidate_roots.append(resolved)
    for root in candidate_roots:
        tmp_dir = root / "tmp"
        if tmp_dir.exists() and os.access(tmp_dir, os.W_OK):
            return tmp_dir / "compendium_section_scripts_v1"
        if os.access(root, os.W_OK):
            return root / "runs" / "compendium_section_scripts_v1"
    return PROJECT_ROOT / "runs" / "compendium_section_scripts_v1"
COMPENDIUM_REFERENCE = {
    "expected_universe_tickers": 493,
    "expected_feature_matrix_columns": 458,
    "expected_walk_forward_windows": 20,
    "expected_sector_counts": {
        "Financial Services": 95,
        "Information Technology": 48,
        "Capital Goods": 64,
    },
}
SECTION_EXPERIMENTS = {
    "ratio": ["EXP-09", "EXP-10", "EXP-11", "EXP-12"],
    "sector": ["EXP-13", "EXP-14", "EXP-15", "EXP-16"],
    "regime": ["EXP-17", "EXP-18", "EXP-19"],
    "redemption": ["EXP-20", "EXP-21", "EXP-22", "EXP-23"],
    "signal": ["EXP-24", "EXP-25"],
    "verification": ["EXP-26", "EXP-27"],
}


def build_section_parser(section_title: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=f"Run {section_title}")
    parser.add_argument("--export-dir", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=_default_output_root())
    parser.add_argument("--profile", choices=["smoke", "full"], default="full")
    parser.add_argument("--max-splits", type=int, default=None)
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--audit-only", action="store_true")
    return parser


def resolve_export_dir(path: Path | None) -> Path:
    if path is not None:
        return resolve_weekly_export_dir(path).export_dir
    for candidate in _default_export_candidates():
        if candidate.exists():
            return candidate.resolve()
    try:
        return resolve_weekly_export_dir(None).export_dir
    except Exception:
        pass
    kaggle_input = Path("/kaggle/input")
    if kaggle_input.exists():
        for feature_path in sorted(kaggle_input.rglob("northstar_features.parquet")):
            return feature_path.parent.resolve()
    raise FileNotFoundError("unable_to_resolve_feature_export_dir")


def _latest_metadata(dataset: PlanDataset) -> pd.DataFrame:
    frame = dataset.metadata.copy()
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame.sort_values(["ticker", "date"], kind="mergesort").drop_duplicates("ticker", keep="last")
    return frame


def _feature_presence(columns: set[str], names: list[str]) -> dict[str, Any]:
    present = [name for name in names if name in columns]
    missing = [name for name in names if name not in columns]
    return {
        "requested": list(names),
        "present": present,
        "missing": missing,
        "coverage_fraction": float(len(present) / len(names)) if names else 1.0,
    }


def _event_coverage(dataset: PlanDataset) -> dict[str, Any]:
    events = load_major_events()
    dataset_min = pd.to_datetime(dataset.features["date"], errors="coerce").min()
    dataset_event_ids = set(dataset.regimes.get("major_event_id", pd.Series(dtype="string")).dropna().astype(str))
    covered: list[str] = []
    unavailable: list[dict[str, Any]] = []
    for row in events.to_dict(orient="records"):
        event_id = str(row["event_id"])
        if event_id in dataset_event_ids:
            covered.append(event_id)
            continue
        reason = "predates_export" if pd.Timestamp(row["end_date"]).normalize() < pd.Timestamp(dataset_min).normalize() else "no_weekly_rows_in_export"
        unavailable.append({"event_id": event_id, "reason": reason})
    fixed_event_status: list[dict[str, Any]] = []
    for event_id in DEFAULT_EXP18_FIXED_EVENTS:
        match = next((row for row in events.to_dict(orient="records") if str(row["event_id"]) == event_id), None)
        if match is None:
            fixed_event_status.append({"event_id": event_id, "status": "missing_from_reference"})
            continue
        if event_id in dataset_event_ids:
            fixed_event_status.append({"event_id": event_id, "status": "covered"})
            continue
        if pd.Timestamp(match["end_date"]).normalize() < pd.Timestamp(dataset_min).normalize():
            fixed_event_status.append({"event_id": event_id, "status": "predates_export"})
        else:
            fixed_event_status.append({"event_id": event_id, "status": "covered_event_but_insufficient_rows"})
    return {
        "covered_event_ids": covered,
        "covered_count": len(covered),
        "reference_event_count": int(events["event_id"].nunique()),
        "unavailable_events": unavailable,
        "fixed_exp18_event_status": fixed_event_status,
    }


def build_dataset_audit(dataset: PlanDataset) -> dict[str, Any]:
    feature_columns = set(map(str, dataset.features.columns))
    metadata_columns = set(map(str, dataset.metadata.columns))
    latest_meta = _latest_metadata(dataset)
    broad_sector_counts = (
        latest_meta.get("broad_sector", pd.Series(dtype="string"))
        .astype("string")
        .fillna("NA")
        .value_counts()
        .to_dict()
    )
    catalog_contract = _factor_alias_contract(list(dataset.features.columns), DEFAULT_CANONICAL_FACTOR_ALIASES)
    doc_contract = _factor_alias_contract(list(dataset.features.columns), DOC_ANCHOR_FACTOR_ALIASES)
    exp26_spec = get_experiment_spec("EXP-26")
    exp26_aliases = {
        str(key): [str(value) for value in list(values or [])]
        for key, values in dict(exp26_spec.params.get("factor_aliases") or DOC_ANCHOR_FACTOR_ALIASES).items()
    }
    exp26_contract = _factor_alias_contract(list(dataset.features.columns), exp26_aliases)
    exp27_spec = get_experiment_spec("EXP-27")
    exp27_candidates = [str(value) for value in list(exp27_spec.params.get("feature_candidates") or [])]
    exp27_aliases = {
        str(key): [str(value) for value in list(values or [])]
        for key, values in dict(exp27_spec.params.get("factor_aliases") or DOC_ANCHOR_FACTOR_ALIASES).items()
    }
    exp27_contract = _factor_alias_contract(
        list(dataset.features.columns),
        {candidate: list(exp27_aliases.get(candidate) or []) for candidate in exp27_candidates},
    )
    fs_universes = resolve_financial_services_universes(dataset)
    sector_counts_actual = {
        "Financial Services": len(fs_universes["full_fs"]),
        "Information Technology": len(resolve_it_tickers(dataset)),
        "Capital Goods": len(resolve_capital_goods_tickers(dataset)),
    }
    feature_counts = {
        "total_columns": int(dataset.features.shape[1]),
        "model_feature_columns": int(len(feature_columns - {"date", "ticker", "target_weekly_return"})),
        "metadata_columns": int(dataset.metadata.shape[1]),
    }
    redemption_macro_count = sum(
        1
        for column in feature_columns
        if str(column).lower().startswith(
            (
                "macro_",
                "rbi_",
                "yield_curve",
                "cpi_",
                "gst_",
                "power_",
                "inrusd_",
                "crude_",
                "gold_",
                "copper_",
                "steel_",
                "coal_",
                "dxy_",
                "fii_",
                "vix_",
                "us_10y_",
                "commodity_",
            )
        )
    )
    feature_date_min = pd.to_datetime(dataset.features["date"], errors="coerce").min()
    audit = {
        "export_dir": str(dataset.export_dir),
        "core_contract": {
            "features_rows": int(dataset.features.shape[0]),
            "feature_columns": feature_counts["total_columns"],
            "metadata_rows": int(dataset.metadata.shape[0]),
            "metadata_columns": feature_counts["metadata_columns"],
            "weekly_dates": int(pd.to_datetime(dataset.features["date"], errors="coerce").nunique()),
            "tickers": int(dataset.features["ticker"].nunique()),
            "walk_forward_windows": int(len(dataset.splits)),
            "date_min": str(pd.to_datetime(dataset.features["date"], errors="coerce").min().date()),
            "date_max": str(pd.to_datetime(dataset.features["date"], errors="coerce").max().date()),
            "target_last_column": bool(dataset.features.columns[-1] == "target_weekly_return"),
        },
        "legacy_readiness": {
            "exp01_08_execution_mode": "historical_replay_on_current_export",
            "date_min": str(feature_date_min.date()),
            "has_pre_2010_history": bool(feature_date_min < pd.Timestamp("2010-01-01")),
            "has_pre_2017_history": bool(feature_date_min < pd.Timestamp("2017-01-01")),
            "has_pre_2019_history": bool(feature_date_min < pd.Timestamp("2019-01-01")),
            "note": "EXP-01..08 are replayed approximately because the current Kaggle export starts in 2019 and does not reproduce the original 2005-era historical span.",
        },
        "compendium_reference": COMPENDIUM_REFERENCE,
        "shape_deltas": {
            "ticker_delta_vs_compendium": int(dataset.features["ticker"].nunique()) - COMPENDIUM_REFERENCE["expected_universe_tickers"],
            "feature_column_delta_vs_compendium": feature_counts["model_feature_columns"] - COMPENDIUM_REFERENCE["expected_feature_matrix_columns"],
        },
        "sector_counts_actual": sector_counts_actual,
        "sector_reference_comparison": {
            sector: {
                "expected": expected,
                "actual": sector_counts_actual.get(sector, 0),
                "delta": int(sector_counts_actual.get(sector, 0)) - int(expected),
            }
            for sector, expected in COMPENDIUM_REFERENCE["expected_sector_counts"].items()
        },
        "broad_sector_counts": broad_sector_counts,
        "sector_feature_readiness": {
            "exp13_fs_features": _feature_presence(
                feature_columns,
                [
                    "nim_4q_trend",
                    "npa_net_4q",
                    "provision_coverage",
                    "credit_deposit_ratio",
                    "rbi_rate_chg",
                    "loan_growth_yoy",
                    "casa_ratio",
                    "gnpa_yoy",
                ],
            ),
            "exp14_it_features": _feature_presence(
                feature_columns,
                [
                    "inrusd_4w_return",
                    "inrusd_vol_4w",
                    "deal_TCV_qoq",
                    "attrition_rate",
                    "headcount_growth",
                    "us_tech_index_4w",
                ],
            ),
            "exp15_cg_features": _feature_presence(
                feature_columns,
                [
                    "order_backlog_growth",
                    "govt_capex_qoq",
                    "steel_4w_return",
                    "copper_4w_return",
                    "infra_spending_index",
                    "power_sector_capex",
                ],
            ),
        },
        "factor_readiness": {
            "catalog_contract": catalog_contract,
            "compendium_doc_contract": doc_contract,
        },
        "event_readiness": _event_coverage(dataset),
        "regime_readiness": {
            "exp19_router_inputs": _feature_presence(
                feature_columns | metadata_columns,
                ["vix_india_4w", "inrusd_4w_return", "nifty_close", "nifty_sma_200", "plan_regime_id"],
            ),
        },
        "redemption_readiness": {
            "exp20_large_cap_proxy_inputs": _feature_presence(metadata_columns | feature_columns, ["close", "volume"]),
            "exp20_note": "Current export is weekly and does not contain the compendium's daily 60-day return sequences.",
            "exp21_macro_feature_count": redemption_macro_count,
            "exp21_note": "Current export contains stock-attached weekly macro features, not the compendium's standalone 2010-2025 macro panel with future covariates.",
            "exp22_rotation_core": _feature_presence(
                feature_columns,
                ["mom_20d_sector_rel_cs_z", "res_mom_20d_cs_z", "price_to_sma20_cs_z", "vol_z20_cs_z"],
            ),
            "exp23_channel_candidates": _feature_presence(
                feature_columns,
                [
                    "mom_20d_sector_rel_cs_z",
                    "res_mom_20d_cs_z",
                    "price_to_sma20_cs_z",
                    "vol_z20_cs_z",
                    "inrusd_4w_return",
                    "crude_4w_return",
                    "gold_4w_return",
                    "copper_4w_return",
                    "steel_4w_return",
                    "coal_4w_return",
                    "dxy_4w_return",
                    "vix_india_4w",
                    "rbi_rate_chg",
                    "us_10y_4w",
                    "commodity_basket",
                ],
            ),
        },
        "signal_readiness": {
            "exp24_cross_asset_signals": _feature_presence(feature_columns, list(PLAN_INFO.cross_asset_signals)),
            "exp25_ccms_inputs": _feature_presence(metadata_columns | feature_columns, ["conglomerate_group", "ret_20d", "market_cap"]),
        },
        "verification_readiness": {
            "exp26_anchor_factors": exp26_contract,
            "exp26_ind_as_history_available": bool(feature_date_min < pd.Timestamp("2017-01-01")),
            "exp27_primary_factor_candidates": exp27_contract,
            "exp27_earnings_quality_family": _feature_presence(
                feature_columns,
                ["accruals_ratio", "accruals_ratio_cs_z", "accruals_ratio_cs_rank", "earnings_quality_ratio", "earnings_quality_ratio_cs_z", "earnings_quality_ratio_cs_rank"],
            ),
            "exp27_retail_ownership_inputs": _feature_presence(metadata_columns | feature_columns, ["retail_ownership_pct"]),
        },
    }
    return audit


def _load_separate_config(exp_id: str) -> dict[str, Any]:
    exp_num = int(exp_id.split("-", 1)[1])
    module = importlib.import_module(f"scripts.kaggle.plan_2026_04_08.run_exp{exp_num:02d}")
    return dict(getattr(module, "SCRIPT_CONFIG"))


def _dependency_closure(exp_id: str, seen: set[str] | None = None) -> list[str]:
    seen = seen or set()
    ordered: list[str] = []
    spec = EXPERIMENT_CATALOG.get(exp_id)
    if spec is None:
        return ordered
    for dep_id in list(spec.dependencies):
        ordered.extend(_dependency_closure(dep_id, seen))
        if dep_id not in seen:
            seen.add(dep_id)
            ordered.append(dep_id)
    return ordered


def resolve_execution_order(exp_ids: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for exp_id in exp_ids:
        for dep_id in _dependency_closure(exp_id, seen):
            if dep_id not in ordered:
                ordered.append(dep_id)
        if exp_id not in seen:
            seen.add(exp_id)
            ordered.append(exp_id)
    return ordered


def _load_existing_summary(output_root: Path, exp_id: str, version: str) -> dict[str, Any] | None:
    path = make_experiment_paths(output_root, exp_id, version).summary_path
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def dispatch_experiment(
    *,
    exp_id: str,
    dataset: PlanDataset,
    export_dir: Path,
    output_root: Path,
    profile: str,
    max_splits: int | None,
    version: str,
    fresh: bool,
) -> dict[str, Any]:
    cached = _load_existing_summary(output_root, exp_id, version)
    if cached is not None and not fresh:
        return {"status": "reused_existing", "payload": cached}

    if exp_id in SEPARATE_RUNNERS:
        args = argparse.Namespace(
            export_dir=export_dir,
            output_root=output_root,
            profile=profile,
            max_splits=max_splits,
            version=version,
            fresh=fresh,
            describe=False,
            audit_dataset=False,
            skip_dependencies=True,
        )
        payload = SEPARATE_RUNNERS[exp_id](args, _load_separate_config(exp_id))
        return {"status": "ran", "payload": payload}

    spec = get_experiment_spec(exp_id)
    runner = SECTION_FAMILY_RUNNERS[spec.family]
    payload = runner(
        spec,
        dataset=dataset,
        output_root=output_root,
        profile=profile,
        max_splits=max_splits,
        version=version,
    )
    return {"status": "ran", "payload": payload}


def execute_standard_section(
    *,
    section_slug: str,
    section_title: str,
    requested_exp_ids: list[str],
    args: argparse.Namespace,
    extra_notes: list[str] | None = None,
) -> dict[str, Any]:
    export_dir = resolve_export_dir(args.export_dir)
    dataset = load_plan_dataset(export_dir)
    section_root = args.output_root.expanduser().resolve() / f"{section_slug}_{args.version}"
    section_root.mkdir(parents=True, exist_ok=True)
    audit = build_dataset_audit(dataset)
    write_json(section_root / "dataset_audit.json", audit)

    execution_order = resolve_execution_order(requested_exp_ids)
    if args.audit_only:
        payload = {
            "section": section_slug,
            "title": section_title,
            "requested_experiments": requested_exp_ids,
            "execution_order": execution_order,
            "dataset_audit": audit,
        }
        print(json.dumps(json_ready(payload), indent=2))
        return payload

    results: dict[str, Any] = {}
    for exp_id in execution_order:
        print(f"[section:{section_slug}] running {exp_id}", flush=True)
        results[exp_id] = dispatch_experiment(
            exp_id=exp_id,
            dataset=dataset,
            export_dir=export_dir,
            output_root=section_root,
            profile=args.profile,
            max_splits=args.max_splits,
            version=args.version,
            fresh=args.fresh,
        )

    summary = {
        "section": section_slug,
        "title": section_title,
        "requested_experiments": requested_exp_ids,
        "executed_experiments": execution_order,
        "export_dir": str(export_dir),
        "dataset_audit_path": str(section_root / "dataset_audit.json"),
        "results": results,
    }
    write_json(section_root / "section_summary.json", summary)
    write_narrative(
        section_root / "section_narrative.md",
        exp_id=section_slug.upper(),
        title=section_title,
        hypothesis="Execute the full section cleanly against the current feature export while surfacing all material dataset-plan gaps.",
        metrics={
            "requested_experiments": requested_exp_ids,
            "executed_experiments": execution_order,
            "tickers": audit["core_contract"]["tickers"],
            "weekly_dates": audit["core_contract"]["weekly_dates"],
        },
        extra_notes=list(extra_notes or [])
        + [
            "Each section script runs the dependency closure inside its own output folder so Kaggle execution stays self-contained.",
            "dataset_audit.json is written before any model run so plan-vs-export mismatches are explicit.",
        ],
    )
    print(json.dumps(json_ready(summary), indent=2))
    return summary


def run_python_script(script_path: Path, *script_args: str) -> None:
    cmd = [sys.executable, str(script_path), *[str(value) for value in script_args]]
    subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=True)
