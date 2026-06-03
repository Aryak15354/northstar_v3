#!/usr/bin/env python3
"""Legacy replay runner for EXP-01 through EXP-08 on the current weekly export."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.kaggle.plan_2026_04_08_sections.lib import (
    build_dataset_audit,
    build_section_parser,
    load_plan_dataset,
    resolve_export_dir,
    run_python_script,
    write_json,
    write_narrative,
)


SCRIPT_CONFIG = {
    "section_slug": "section_legacy_01_08",
    "title": "Sections 1-2 - Prior Results, Infrastructure, and Legacy Replay (EXP-01..08)",
    "legacy_mapping": {
        "EXP-01": "NB-01 full tree baselines",
        "EXP-02": "NB-01 tiered/reduced export comparison",
        "EXP-03": "NB-07 ensemble diagnostics",
        "EXP-04": "NB-02 LSTM/GRU stratum replay",
        "EXP-05": "NB-07 TRA/deployment diagnostics",
        "EXP-06": "NB-02 frontier/iTransformer replay",
        "EXP-07": "NB-00/NB-01 factor-tier and selected-feature replay",
        "EXP-08": "NB-07 unified final decision bundle",
    },
}


def main() -> int:
    parser = build_section_parser(SCRIPT_CONFIG["title"])
    args = parser.parse_args()
    if args.describe:
        print(json.dumps(SCRIPT_CONFIG, indent=2))
        return 0

    export_dir = resolve_export_dir(args.export_dir)
    dataset = load_plan_dataset(export_dir)
    section_root = args.output_root.expanduser().resolve() / f"{SCRIPT_CONFIG['section_slug']}_{args.version}"
    section_root.mkdir(parents=True, exist_ok=True)
    audit = build_dataset_audit(dataset)
    write_json(section_root / "dataset_audit.json", audit)

    if args.audit_only:
        payload = {
            "section": SCRIPT_CONFIG["section_slug"],
            "title": SCRIPT_CONFIG["title"],
            "legacy_mapping": SCRIPT_CONFIG["legacy_mapping"],
            "dataset_audit": audit,
        }
        print(json.dumps(payload, indent=2))
        return 0

    nb00_dir = section_root / "01_nb00"
    nb01_dir = section_root / "02_nb01"
    nb02_dir = section_root / "03_nb02"
    nb07_dir = section_root / "07_nb07"
    nb00_report = nb00_dir / "feature_health_report.json"
    nb01_args = [
        "--export-dir",
        export_dir,
        "--nb00-report",
        nb00_report,
        "--output-dir",
        nb01_dir,
        "--profile",
        args.profile,
    ]
    nb02_args = [
        "--export-dir",
        export_dir,
        "--nb00-report",
        nb00_report,
        "--nb01-dir",
        nb01_dir,
        "--output-dir",
        nb02_dir,
        "--profile",
        args.profile,
    ]
    if args.max_splits is not None:
        nb01_args.extend(["--max-splits", str(args.max_splits)])
        nb02_args.extend(["--max-splits", str(args.max_splits)])

    run_python_script(
        PROJECT_ROOT / "scripts" / "kaggle" / "week_2026_03_29" / "nb00_feature_health.py",
        "--export-dir",
        export_dir,
        "--output-dir",
        nb00_dir,
    )
    run_python_script(
        PROJECT_ROOT / "scripts" / "kaggle" / "week_2026_03_29" / "nb01_fixed_baselines.py",
        *nb01_args,
    )
    run_python_script(
        PROJECT_ROOT / "scripts" / "kaggle" / "week_2026_03_29" / "nb02_failed_model_autopsy.py",
        *nb02_args,
    )
    run_python_script(
        PROJECT_ROOT / "scripts" / "kaggle" / "week_2026_03_29" / "nb07_ensemble_tra_deployment.py",
        "--export-dir",
        export_dir,
        "--nb01-dir",
        nb01_dir,
        "--nb02-dir",
        nb02_dir,
        "--output-dir",
        nb07_dir,
    )

    summary = {
        "section": SCRIPT_CONFIG["section_slug"],
        "title": SCRIPT_CONFIG["title"],
        "export_dir": str(export_dir),
        "dataset_audit_path": str(section_root / "dataset_audit.json"),
        "legacy_mapping": SCRIPT_CONFIG["legacy_mapping"],
        "artifact_dirs": {
            "nb00": str(nb00_dir),
            "nb01": str(nb01_dir),
            "nb02": str(nb02_dir),
            "nb07": str(nb07_dir),
        },
    }
    write_json(section_root / "section_summary.json", summary)
    write_narrative(
        section_root / "section_narrative.md",
        exp_id="LEGACY",
        title=SCRIPT_CONFIG["title"],
        hypothesis="Replay the pre-compendium baselines on the current weekly export as faithfully as the 2019+ dataset allows.",
        metrics={
            "artifact_dirs": summary["artifact_dirs"],
            "tickers": audit["core_contract"]["tickers"],
            "weekly_dates": audit["core_contract"]["weekly_dates"],
        },
        extra_notes=[
            "This legacy replay is explicitly approximate because the current export starts in 2019 and is weekly, while several early experiments were designed around earlier history and different training strata.",
        "The mapping from EXP-01..08 to NB-00/NB-01/NB-02/NB-07 is written into section_summary.json so nothing is implicit.",
        "This script stands in for the compendium's Sections 1 and 2, where the earlier experiments and the Kaggle-local execution architecture are carried forward into the current 2019+ export era.",
    ],
)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
