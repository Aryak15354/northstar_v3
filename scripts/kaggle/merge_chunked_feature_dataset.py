#!/usr/bin/env python3
"""Merge a chunked local Northstar dataset into the standard Kaggle export files.

This script is intended to run on Kaggle after attaching the chunk dataset built
by ``scripts/kaggle/build_local_feature_chunks.py``. It reconstructs the usual
export contract without loading the full feature matrix into memory at once.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.week_2026_03_29.common import (  # noqa: E402
    FAMILY_AUDIT_SPECS,
    NON_FEATURE_COLUMNS,
    apply_export_quality_repairs,
    build_feature_unit_registry,
    build_plan_regime_labels,
    repair_runtime_factor_families,
    select_feature_columns,
)


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except TypeError:
            return str(value)
    return str(value)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_root_artifact(chunk_root: Path, name: str) -> Path:
    path = chunk_root / name
    if not path.exists():
        raise FileNotFoundError(f"missing_chunk_dataset_artifact:{path}")
    return path


def _resolve_chunk_file(chunk_root: Path, row: dict[str, Any], kind: str, subdir: str) -> Path:
    slug = str(row.get("slug") or "").strip()
    if slug:
        candidate = chunk_root / subdir / f"{slug}.parquet"
        if candidate.exists():
            return candidate

    raw_path = (((row.get("files") or {}).get(kind)) or "")
    if raw_path:
        candidate = Path(raw_path)
        if candidate.exists():
            return candidate
        if not candidate.is_absolute() and (chunk_root / candidate).exists():
            return chunk_root / candidate
        if candidate.name and (chunk_root / subdir / candidate.name).exists():
            return chunk_root / subdir / candidate.name

    raise FileNotFoundError(f"missing_{kind}_chunk_for_row:{row}")


def _promote_field(current: pa.Field | None, new_field: pa.Field) -> pa.Field:
    if current is None:
        return new_field
    if current.type.equals(new_field.type):
        return current
    if pa.types.is_null(current.type):
        return new_field
    if pa.types.is_null(new_field.type):
        return current
    if pa.types.is_timestamp(current.type) and pa.types.is_timestamp(new_field.type):
        return pa.field(current.name, pa.timestamp("ns"))
    if pa.types.is_date(current.type) and pa.types.is_date(new_field.type):
        return pa.field(current.name, pa.date32())
    if (
        pa.types.is_integer(current.type)
        or pa.types.is_floating(current.type)
        or pa.types.is_integer(new_field.type)
        or pa.types.is_floating(new_field.type)
    ):
        return pa.field(current.name, pa.float64())
    if (
        pa.types.is_string(current.type)
        or pa.types.is_large_string(current.type)
        or pa.types.is_string(new_field.type)
        or pa.types.is_large_string(new_field.type)
    ):
        return pa.field(current.name, pa.string())
    return current


def _derive_schema(files: list[Path], preferred_order: list[str]) -> pa.Schema:
    fields_by_name: dict[str, pa.Field] = {}
    for file_path in files:
        schema = pq.ParquetFile(file_path).schema_arrow
        for field in schema:
            fields_by_name[field.name] = _promote_field(fields_by_name.get(field.name), field)

    ordered_names: list[str] = []
    for name in preferred_order:
        if name not in ordered_names:
            ordered_names.append(name)
    for field_name in fields_by_name:
        if field_name not in ordered_names:
            ordered_names.append(field_name)

    return pa.schema(
        [fields_by_name.get(name, pa.field(name, pa.null())) for name in ordered_names]
    )


def _align_table(table: pa.Table, schema: pa.Schema) -> pa.Table:
    arrays = []
    for field in schema:
        if field.name in table.column_names:
            column = table[field.name]
            if not column.type.equals(field.type):
                if pa.types.is_null(column.type):
                    column = pa.nulls(table.num_rows, type=field.type)
                elif not pa.types.is_null(field.type):
                    column = pc.cast(column, target_type=field.type, safe=False)
            arrays.append(column)
        else:
            arrays.append(pa.nulls(table.num_rows, type=field.type))
    return pa.Table.from_arrays(arrays, schema=schema)


def _scalar_stat(value: Any) -> Any:
    return None if value is None else value.as_py()


def _merge_stream(
    *,
    files: list[Path],
    preferred_order: list[str],
    output_path: Path,
    track_tickers: bool = False,
    track_target_non_null: bool = False,
) -> dict[str, Any]:
    schema = _derive_schema(files, preferred_order)
    writer: pq.ParquetWriter | None = None
    row_count = 0
    date_min = None
    date_max = None
    ticker_values: set[str] = set()
    target_non_null = 0

    try:
        for file_path in files:
            table = pq.read_table(file_path)
            table = _align_table(table, schema)
            if writer is None:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                writer = pq.ParquetWriter(output_path, schema)
            writer.write_table(table)

            row_count += int(table.num_rows)
            if "date" in table.column_names and table.num_rows:
                chunk_min = _scalar_stat(pc.min(table["date"]))
                chunk_max = _scalar_stat(pc.max(table["date"]))
                if date_min is None or (chunk_min is not None and chunk_min < date_min):
                    date_min = chunk_min
                if date_max is None or (chunk_max is not None and chunk_max > date_max):
                    date_max = chunk_max
            if track_tickers and "ticker" in table.column_names:
                for value in table["ticker"].to_pylist():
                    if value is not None:
                        ticker_values.add(str(value))
            if track_target_non_null and "target_weekly_return" in table.column_names:
                target_non_null += int(pc.count(table["target_weekly_return"], mode="only_valid").as_py() or 0)
    finally:
        if writer is not None:
            writer.close()

    return {
        "rows": int(row_count),
        "columns": [field.name for field in schema],
        "date_min": date_min,
        "date_max": date_max,
        "ticker_count": int(len(ticker_values)) if track_tickers else None,
        "target_non_null_count": int(target_non_null) if track_target_non_null else None,
    }


def _feature_family_audit(features_path: Path, *, enforce: bool = True) -> dict[str, Any]:
    parquet = pq.ParquetFile(features_path)
    names = parquet.schema_arrow.names
    total_rows = int(parquet.metadata.num_rows)
    audit: dict[str, Any] = {}
    for family, spec in FAMILY_AUDIT_SPECS.items():
        prefixes = tuple(spec["prefixes"])
        core_prefixes = tuple(spec["core_prefixes"])
        cols = [name for name in names if str(name).startswith(prefixes)]
        core_cols = [name for name in cols if str(name).startswith(core_prefixes)]
        valid_counts = {name: 0 for name in cols}
        if cols:
            for batch in parquet.iter_batches(columns=cols, batch_size=65536):
                table = pa.Table.from_batches([batch])
                for name in cols:
                    valid_counts[name] += int(pc.count(table[name], mode="only_valid").as_py() or 0)
        coverage = {
            name: (float(count / total_rows) if total_rows > 0 else 0.0)
            for name, count in valid_counts.items()
        }
        top = dict(sorted(coverage.items(), key=lambda item: item[1], reverse=True)[:12])
        top_core = {
            name: cov
            for name, cov in sorted(
                ((name, coverage.get(name, 0.0)) for name in core_cols),
                key=lambda item: item[1],
                reverse=True,
            )[:12]
        }
        max_cov = max(coverage.values()) if coverage else 0.0
        core_max_cov = max((coverage.get(name, 0.0) for name in core_cols), default=0.0)
        sorted_cov = sorted(coverage.values())
        median_cov = sorted_cov[len(sorted_cov) // 2] if sorted_cov else 0.0
        sorted_core_cov = sorted(coverage.get(name, 0.0) for name in core_cols)
        core_median_cov = sorted_core_cov[len(sorted_core_cov) // 2] if sorted_core_cov else 0.0
        passing = len(cols) >= int(spec["min_columns"]) and core_median_cov >= float(spec["min_core_median_coverage"])
        audit[family] = {
            "columns": int(len(cols)),
            "core_columns": int(len(core_cols)),
            "min_columns": int(spec["min_columns"]),
            "max_coverage": float(max_cov),
            "core_max_coverage": float(core_max_cov),
            "core_median_coverage": float(core_median_cov),
            "median_coverage": float(median_cov),
            "min_core_median_coverage": float(spec["min_core_median_coverage"]),
            "source_scope": str(spec.get("source_scope", "full_history_expected")),
            "top_columns": top,
            "top_core_columns": top_core,
            "status": "PASS" if passing else "FAIL",
        }
    failures = {k: v for k, v in audit.items() if v.get("status") != "PASS"}
    if failures:
        # E.7: match the direct path's semantics — a smoke/limited run warns
        # rather than hard-failing, so an intentionally-partial build can complete.
        message = "required_feature_families_missing_or_dead:" + json.dumps(failures, sort_keys=True)
        if enforce:
            raise RuntimeError(message)
        print(f"[merge] family audit warning: {message}", flush=True)
    return audit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge chunked Northstar feature exports into the standard Kaggle files.")
    parser.add_argument("--chunk-root", type=Path, required=True, help="Root of the chunk dataset.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Writable directory for the merged export.")
    parser.add_argument(
        "--no-enforce-family-audit",
        action="store_true",
        help="Warn instead of hard-failing when a feature family fails the coverage audit (for smoke/partial runs).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    chunk_root = args.chunk_root.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = _resolve_root_artifact(chunk_root, "local_chunked_dataset_manifest.json")
    manifest = _read_json(manifest_path)
    chunk_rows = sorted(
        [row for row in list(manifest.get("chunks") or []) if row.get("slug")],
        key=lambda row: int(row.get("chunk_id", 0)),
    )
    if not chunk_rows:
        raise RuntimeError(f"no_chunks_recorded_in_manifest:{manifest_path}")

    feature_files = [
        _resolve_chunk_file(chunk_root, row, "features", "features_chunks")
        for row in chunk_rows
    ]
    metadata_files = [
        _resolve_chunk_file(chunk_root, row, "metadata", "metadata_chunks")
        for row in chunk_rows
    ]
    regime_files = [
        _resolve_chunk_file(chunk_root, row, "regimes", "regime_chunks")
        for row in chunk_rows
    ]

    features_path = output_dir / "northstar_features.parquet"
    metadata_path = output_dir / "northstar_metadata.parquet"
    regimes_path = output_dir / "northstar_regime_labels.parquet"
    splits_path = output_dir / "northstar_walk_forward_splits.json"
    unit_registry_path = output_dir / "feature_unit_registry.json"
    signal_audit_path = output_dir / "plan_signal_audit.json"

    features_stats = _merge_stream(
        files=feature_files,
        preferred_order=[str(name) for name in list(manifest.get("feature_columns") or [])],
        output_path=features_path,
        track_tickers=True,
        track_target_non_null=True,
    )
    # NOTE (E.6): the streamed concat is memory-bounded, but the quality repairs,
    # runtime-factor repairs, global regime recompute, and full-history coverage
    # filter below need the whole merged frame in pandas at once. This runs a
    # single time after streaming (not per-chunk), so it is a bounded, deliberate
    # exception to the streaming design rather than a per-chunk regression.
    features_df = pd.read_parquet(features_path)

    # A.3: the chunk builder never ran the quality/revision family repairs (and
    # pre-deleted the columns they need). Apply them here so the chunked path
    # ships the same anchor factors (earnings_quality_ratio, eps_revision_accel,
    # combined_revision_score) as the direct path.
    features_df, runtime_factor_repairs = repair_runtime_factor_families(features_df)

    # E.4: pass the plan-signal audit so dropped dead columns keep a diagnostic
    # trail (status/notes) instead of vanishing silently.
    signal_audit_for_repair: dict[str, Any] | None = None
    plan_audit_src = chunk_root / "plan_signal_audit.json"
    if plan_audit_src.exists():
        try:
            signal_audit_for_repair = _read_json(plan_audit_src)
        except Exception:
            signal_audit_for_repair = None
    features_df, export_quality_audit = apply_export_quality_repairs(
        features_df, signal_audit=signal_audit_for_repair
    )

    # N2: regime labels were built per-chunk with per-chunk thresholds, making
    # the labels inconsistent across the merged history. Recompute them ONCE over
    # the full merged panel so the shipped labels are globally consistent. The
    # labels go ONLY to northstar_regime_labels.parquet — regime_code is not a
    # model feature (already excluded from features via NON_FEATURE_COLUMNS), so
    # we do NOT merge it back into features_df here.
    regime_raw_bundle = Path(str(manifest.get("raw_bundle_dir") or chunk_root))
    try:
        global_regimes = build_plan_regime_labels(features_df, regime_raw_bundle)
    except Exception as exc:  # noqa: BLE001
        print(f"[merge] global regime recompute failed ({exc}); falling back to chunk regimes", flush=True)
        global_regimes = pd.DataFrame()
    # Defensive: strip any regime_code/plan_regime_code that leaked into features
    # from an older chunk build, so they never ship as model inputs.
    leaked_regime_cols = [c for c in ("regime_code", "plan_regime_code") if c in features_df.columns]
    if leaked_regime_cols:
        features_df = features_df.drop(columns=leaked_regime_cols, errors="ignore")

    # A.5: re-run the coverage/unit filter over the FULL merged history and drop
    # any FEATURE that fails on the full frame even if it survived one chunk.
    # Protect the export-contract columns that are legitimately present but are
    # not model features (NON_FEATURE_COLUMNS: date/ticker/target/close/volume/…),
    # plus availability flags and any *_id / *_label metadata.
    keep_features = set(select_feature_columns(features_df))
    protected = set(NON_FEATURE_COLUMNS) | {"date", "ticker", "target_weekly_return"}
    dropped_low_coverage = [
        c for c in features_df.columns
        if c not in protected
        and c not in keep_features
        and not str(c).endswith(("_id", "_label", "_available"))
    ]
    if dropped_low_coverage:
        features_df = features_df.drop(columns=dropped_low_coverage, errors="ignore")
    export_quality_audit["full_history_coverage_dropped"] = sorted(dropped_low_coverage)

    # E.3 (final-export budget): the declared 500-feature budget applies HERE —
    # after RBI capping, dedup, and the coverage filter — not to the pre-repair
    # daily panel. Count base names the same way DatasetManager does (collapse
    # _cs_z/_cs_rank variants and sector dummies).
    export_feature_budget = 500
    def _budget_base_name(name: str) -> str:
        base = str(name)
        for suf in ("_cs_z", "_cs_rank", "_ts_z", "_zscore"):
            if base.endswith(suf):
                base = base[: -len(suf)]
        return "sector_dummy" if base.startswith("sector_dummy_") else base
    export_base_names = sorted({
        _budget_base_name(c) for c in features_df.columns
        if c not in {"date", "ticker", "target_weekly_return"}
    })
    export_quality_audit["export_feature_budget"] = {
        "budget": export_feature_budget,
        "base_feature_count": len(export_base_names),
        "status": "PASS" if len(export_base_names) <= export_feature_budget else "FAIL",
    }
    if len(export_base_names) > export_feature_budget:
        raise RuntimeError(
            f"export_feature_budget_exceeded:{len(export_base_names)}>{export_feature_budget}"
        )

    features_df.to_parquet(features_path, index=False)
    features_stats = {
        **features_stats,
        "rows": int(len(features_df)),
        "columns": list(features_df.columns),
        "ticker_count": int(features_df["ticker"].nunique()) if "ticker" in features_df.columns else 0,
        "date_min": pd.to_datetime(features_df["date"], errors="coerce").min() if "date" in features_df.columns else None,
        "date_max": pd.to_datetime(features_df["date"], errors="coerce").max() if "date" in features_df.columns else None,
        "target_non_null_count": int(features_df["target_weekly_return"].notna().sum()) if "target_weekly_return" in features_df.columns else 0,
    }
    metadata_stats = _merge_stream(
        files=metadata_files,
        preferred_order=[str(name) for name in list(manifest.get("metadata_columns") or [])],
        output_path=metadata_path,
    )
    if not global_regimes.empty:
        global_regimes.to_parquet(regimes_path, index=False)
        regimes_stats = {
            "rows": int(len(global_regimes)),
            "columns": list(global_regimes.columns),
            "date_min": pd.to_datetime(global_regimes["date"], errors="coerce").min() if "date" in global_regimes.columns else None,
            "date_max": pd.to_datetime(global_regimes["date"], errors="coerce").max() if "date" in global_regimes.columns else None,
            "ticker_count": None,
            "target_non_null_count": None,
        }
    else:
        regimes_stats = _merge_stream(
            files=regime_files,
            preferred_order=[str(name) for name in list(manifest.get("regime_columns") or [])],
            output_path=regimes_path,
        )
    export_quality_audit["runtime_factor_repairs"] = runtime_factor_repairs
    family_audit = _feature_family_audit(features_path, enforce=not args.no_enforce_family_audit)
    _write_json(output_dir / "dataset_family_audit.json", family_audit)
    _write_json(output_dir / "export_quality_audit.json", export_quality_audit)
    _write_json(unit_registry_path, build_feature_unit_registry(features_df))

    for artifact_name, destination in [
        ("northstar_walk_forward_splits.json", splits_path),
        ("plan_signal_audit.json", signal_audit_path),
    ]:
        source = _resolve_root_artifact(chunk_root, artifact_name)
        destination.write_bytes(source.read_bytes())

    splits = _read_json(splits_path)
    source_audit = _read_json(signal_audit_path)
    weekly_manifest = {
        "generated_at": _now_utc_iso(),
        "builder": "merge_chunked_feature_dataset.py",
        "source_chunk_manifest": str(manifest_path),
        "feature_count": int(max(0, len(features_stats["columns"]) - 3)),
        "features_rows": int(features_stats["rows"]),
        "metadata_rows": int(metadata_stats["rows"]),
        "ticker_count": int(features_stats.get("ticker_count") or 0),
        "date_min": _json_default(features_stats.get("date_min")),
        "date_max": _json_default(features_stats.get("date_max")),
        "target_non_null_pct": (
            float((features_stats.get("target_non_null_count") or 0) / features_stats["rows"])
            if int(features_stats["rows"]) > 0
            else 0.0
        ),
        "n_windows": int(len(splits)),
        "chunk_policy": manifest.get("chunk_policy") or {},
        "engine_limits": manifest.get("engine_limits") or {},
        "plan_signal_audit": source_audit,
        "dataset_family_audit": family_audit,
        "export_quality_audit": export_quality_audit,
        "files": {
            "features": str(features_path),
            "metadata": str(metadata_path),
            "splits": str(splits_path),
            "regimes": str(regimes_path),
        },
    }
    _write_json(output_dir / "weekly_export_manifest.json", weekly_manifest)
    _write_json(
        output_dir / "merged_chunk_export_manifest.json",
        {
            "generated_at": _now_utc_iso(),
            "chunk_root": str(chunk_root),
            "output_dir": str(output_dir),
            "source_chunk_manifest": str(manifest_path),
            "streams": {
                "features": features_stats,
                "metadata": metadata_stats,
                "regimes": regimes_stats,
            },
            "export_quality_audit": export_quality_audit,
            "files": weekly_manifest["files"],
        },
    )

    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "features_rows": int(features_stats["rows"]),
                "metadata_rows": int(metadata_stats["rows"]),
                "regime_rows": int(regimes_stats["rows"]),
                "feature_count": int(max(0, len(features_stats["columns"]) - 3)),
                "ticker_count": int(features_stats.get("ticker_count") or 0),
                "date_min": _json_default(features_stats.get("date_min")),
                "date_max": _json_default(features_stats.get("date_max")),
                "n_windows": int(len(splits)),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
