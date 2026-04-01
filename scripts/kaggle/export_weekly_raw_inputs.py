#!/usr/bin/env python3
"""Stage the weekly raw-input bundle for Kaggle notebooks."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SAFE_NAME_RE = re.compile(r"[A-Za-z0-9._-]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export weekly raw inputs for Kaggle.")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--dataset-name", type=str, default="northstar-v3-weekly-raw-inputs")
    parser.add_argument("--dataset-title", type=str, default="Northstar V3 Weekly Raw Inputs")
    parser.add_argument("--kaggle-username", type=str, default=os.environ.get("KAGGLE_USERNAME", ""))
    return parser.parse_args()


def kaggle_safe_relative_path(rel_path: Path) -> Path:
    parts: list[str] = []
    for part in rel_path.parts:
        safe_chars: list[str] = []
        for ch in str(part):
            if _SAFE_NAME_RE.fullmatch(ch):
                safe_chars.append(ch)
            else:
                safe_chars.append(f"_x{ord(ch):02x}_")
        parts.append("".join(safe_chars))
    return Path(*parts)


def _link_or_copy_file(src: Path, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    try:
        os.link(src, dest)
    except OSError:
        shutil.copy2(src, dest)
    return int(dest.stat().st_size)


def _copy_path(src: Path, dest_root: Path) -> dict[str, Any]:
    files = 0
    bytes_written = 0
    renamed: list[dict[str, str]] = []
    rel_base = src.relative_to(PROJECT_ROOT)
    if src.is_file():
        staged_rel = kaggle_safe_relative_path(rel_base)
        bytes_written += _link_or_copy_file(src, dest_root / staged_rel)
        files += 1
        if staged_rel != rel_base:
            renamed.append({"source_relative_path": str(rel_base), "staged_relative_path": str(staged_rel)})
        return {"files": files, "bytes": bytes_written, "renamed": renamed}
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(PROJECT_ROOT)
        staged_rel = kaggle_safe_relative_path(rel)
        bytes_written += _link_or_copy_file(path, dest_root / staged_rel)
        files += 1
        if staged_rel != rel:
            renamed.append({"source_relative_path": str(rel), "staged_relative_path": str(staged_rel)})
    return {"files": files, "bytes": bytes_written, "renamed": renamed}


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    selected_paths = [
        PROJECT_ROOT / "data/canonical",
        PROJECT_ROOT / "data/raw/forex",
        PROJECT_ROOT / "data/raw/commodities",
        PROJECT_ROOT / "data/raw/vendors/screener",
        PROJECT_ROOT / "data/raw/shared/research_inputs/week_2026_03_29",
        PROJECT_ROOT / "data/raw/shared/market_data/cross_asset_manifest.json",
        PROJECT_ROOT / "data/processed/alternative/earnings_dates_all.csv",
        PROJECT_ROOT / "data/processed/intelligent_market_state.parquet",
        PROJECT_ROOT / "data/processed/market_state.parquet",
        PROJECT_ROOT / "data/processed/regime_labels.parquet",
        PROJECT_ROOT / "data/processed/sector_mapping.csv",
        PROJECT_ROOT / "data/processed/valuation.parquet",
        PROJECT_ROOT / "data/processed/valuation_posterior.parquet",
        PROJECT_ROOT / "data/processed/valuation_scores.parquet",
        PROJECT_ROOT / "data/results/research/state/weekly_data_stack_verification.json",
        PROJECT_ROOT / "config",
        PROJECT_ROOT / "universe/nifty500.csv",
    ]

    copied: list[dict[str, Any]] = []
    total_files = 0
    total_bytes = 0
    renamed_files: list[dict[str, str]] = []
    for src in selected_paths:
        if not src.exists():
            continue
        stats = _copy_path(src, output_dir)
        copied.append({"source": str(src), **stats})
        total_files += int(stats["files"])
        total_bytes += int(stats["bytes"])
        renamed_files.extend(list(stats.get("renamed") or []))

    manifest = {
        "generated_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "project_root": str(PROJECT_ROOT),
        "total_files": total_files,
        "total_bytes": total_bytes,
        "copied": copied,
        "renamed_files": renamed_files,
    }
    (output_dir / "northstar_weekly_raw_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (output_dir / "kaggle_filename_manifest.json").write_text(json.dumps(renamed_files, indent=2), encoding="utf-8")

    readme = output_dir / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# Northstar V3 Weekly Raw Inputs",
                "",
                "This bundle is designed for Kaggle-side feature generation.",
                "",
                "Included:",
                "- `data/canonical/` low-level canonical panels",
                "- `data/raw/forex/` and `data/raw/commodities/` refreshed cross-asset histories",
                "- `data/raw/vendors/screener/` raw Screener vendor tables for unit-safe Kaggle-side rebuilds",
                "- `data/processed/valuation*.parquet` cached valuation/posterior inputs for Kaggle feature generation",
                "- `data/processed/alternative/earnings_dates_all.csv` earnings calendar for SUE/revision timing",
                "- `data/processed/{regime_labels,market_state,intelligent_market_state,sector_mapping}` support artifacts",
                "- `data/raw/shared/research_inputs/week_2026_03_29/` stored source docs and extracted text",
                "- raw Yahoo/Screener filenames are Kaggle-sanitized when needed; see `kaggle_filename_manifest.json` for original-to-staged name mappings",
                "- `config/` runtime policy/config helpers used by the Kaggle weekly suite",
                "- `universe/nifty500.csv` legacy-compatible enriched universe",
                "- verification and manifest JSON files",
            ]
        ),
        encoding="utf-8",
    )

    if args.kaggle_username.strip():
        metadata = {
            "title": args.dataset_title,
            "id": f"{args.kaggle_username.strip()}/{args.dataset_name.strip()}",
            "licenses": [{"name": "other"}],
            "isPrivate": True,
        }
        (output_dir / "dataset-metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(json.dumps({"output_dir": str(output_dir), "total_files": total_files, "total_bytes": total_bytes}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
