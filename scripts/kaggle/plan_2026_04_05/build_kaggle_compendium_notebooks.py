#!/usr/bin/env python3
"""Generate self-contained Kaggle notebooks for the compendium experiments."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import nbformat as nbf
import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOWNLOADS_DIR = Path.home() / "Downloads"
NOTEBOOK_DIR = PROJECT_ROOT / "notebooks" / "kaggle_sprint"
RUNTIME_PATH = Path(__file__).with_name("selfcontained_runtime.py")
CATALOG_PATH = PROJECT_ROOT / "configs" / "plan_2026_04_05" / "catalog_v1.yaml"
EVENTS_PATH = PROJECT_ROOT / "data" / "canonical" / "reference" / "regimes" / "nse_regime_events_major.parquet"


def _md(text: str):
    return nbf.v4.new_markdown_cell(dedent(text).strip() + "\n")


def _code(text: str):
    return nbf.v4.new_code_cell(dedent(text).strip() + "\n")


def _write_notebook(path: Path, cells: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    nb = nbf.v4.new_notebook(cells=cells)
    nb.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    nb.metadata["language_info"] = {
        "name": "python",
        "version": "3.12",
    }
    path.write_text(nbf.writes(nb), encoding="utf-8")


def _json_literal(value) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True)


def _load_plan_payload() -> dict:
    payload = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise TypeError(f"invalid_catalog_payload:{CATALOG_PATH}")
    plan = dict(payload.get("plan") or {})
    if plan:
        if str(plan.get("source_doc") or "").strip():
            plan["source_doc"] = Path(str(plan["source_doc"])).name
        if str(plan.get("master_notebook") or "").strip():
            plan["master_notebook"] = Path(str(plan["master_notebook"])).name
        payload["plan"] = plan
    return payload


def _load_events_payload() -> list[dict]:
    events = pd.read_parquet(EVENTS_PATH).copy()
    for column in events.columns:
        if pd.api.types.is_datetime64_any_dtype(events[column]):
            events[column] = events[column].dt.strftime("%Y-%m-%d")
    return events.to_dict(orient="records")


def _runtime_source() -> str:
    return RUNTIME_PATH.read_text(encoding="utf-8").strip() + "\n"


def _ratio_cells(plan_payload: dict, events_payload: list[dict], runtime_source: str) -> list:
    return [
        _md(
            """
            # NORTHSTAR V3 - Ratio Campaign

            This notebook runs **EXP-09 through EXP-12** directly on Kaggle with no repo-code dataset.

            Attach only:
            - `northstar-v3-feature-export`

            Expected files inside the dataset:
            - `northstar_features.parquet`
            - `northstar_metadata.parquet`
            - `northstar_regime_labels.parquet`
            - `northstar_walk_forward_splits.json`

            Outputs are written to `/kaggle/working/compendium_plan_v1/exp_xx_v1/`.
            """
        ),
        _md("## Config"),
        _code(
            """
            from pathlib import Path

            EXP_ID = "EXP-09"  # EXP-09 | EXP-10 | EXP-11 | EXP-12
            VERSION = "v1"
            OUTPUT_ROOT = Path("/kaggle/working/compendium_plan_v1")

            EXPORT_DIR_OVERRIDE = None
            EXPORT_DATASET_CANDIDATES = [
                "/kaggle/input/northstar-v3-feature-export",
                "/kaggle/input/northstar-v3-feature-export-1",
                "/kaggle/input/northstar-v3-feature-export-2",
            ]

            MAX_SPLITS = None  # set an integer for a quick smoke test
            MANUAL_UPSTREAM_PARAMS = {}
            SHOW_TOP_ROWS = 12

            print(f"Notebook configured for {EXP_ID}")
            """
        ),
        _md("## Embedded Plan Payload"),
        _code(
            f"""
            PLAN_PAYLOAD = {_json_literal(plan_payload)}
            MAJOR_EVENTS_PAYLOAD = {_json_literal(events_payload)}
            """
        ),
        _md("## Runtime"),
        _code(runtime_source),
        _md("## Load And Validate The Export"),
        _code(
            """
            spec = get_experiment_spec(EXP_ID)
            export_dir = resolve_export_dir(EXPORT_DATASET_CANDIDATES, EXPORT_DIR_OVERRIDE)
            dataset = load_plan_dataset(export_dir)
            contract = validate_dataset_contract(dataset)
            display_dataset_report(EXP_ID, dataset, contract)
            """
        ),
        _md("## Run The Selected Ratio Experiment"),
        _code(
            """
            result = run_ratio_experiment(
                EXP_ID,
                dataset=dataset,
                output_root=OUTPUT_ROOT,
                version=VERSION,
                max_splits=MAX_SPLITS,
                manual_upstream_params=MANUAL_UPSTREAM_PARAMS,
            )
            display_experiment_result(result, show_top_rows=SHOW_TOP_ROWS)
            result
            """
        ),
        _md("## Output Files"),
        _code(
            """
            exp_root = OUTPUT_ROOT / f"{EXP_ID.lower().replace('-', '_')}_{VERSION}"
            files = sorted(str(path.relative_to(exp_root)) for path in exp_root.rglob("*") if path.is_file())
            pd.DataFrame({"output_files": files})
            """
        ),
    ]


def _sector_regime_cells(plan_payload: dict, events_payload: list[dict], runtime_source: str) -> list:
    return [
        _md(
            """
            # NORTHSTAR V3 - Sector And Regime Campaigns

            This notebook runs **EXP-13 through EXP-19** directly on Kaggle with no repo-code dataset.

            Attach only:
            - `northstar-v3-feature-export`

            Best practice:
            - run the ratio notebook first so EXP-13 to EXP-18 can inherit the best CatBoost settings
            - then run this notebook for sector and regime campaigns

            EXP-19 now follows the compendium literally: separate `CatBoost` specialists are routed by regime.
            """
        ),
        _md("## Config"),
        _code(
            """
            from pathlib import Path

            EXP_ID = "EXP-13"  # EXP-13 ... EXP-19
            VERSION = "v1"
            OUTPUT_ROOT = Path("/kaggle/working/compendium_plan_v1")

            EXPORT_DIR_OVERRIDE = None
            EXPORT_DATASET_CANDIDATES = [
                "/kaggle/input/northstar-v3-feature-export",
                "/kaggle/input/northstar-v3-feature-export-1",
                "/kaggle/input/northstar-v3-feature-export-2",
            ]

            MAX_SPLITS = None  # set an integer for a quick smoke test
            BEST_RATIO_PARAMS_OVERRIDE = {}
            SHOW_TOP_ROWS = 12

            SEQUENCE_BACKEND = "torch"  # switch to "sklearn" if torch is unavailable in the Kaggle session
            SEQUENCE_LENGTH = 8
            SEQUENCE_EPOCHS = 4
            SEQUENCE_BATCH_SIZE = 1024
            SEQUENCE_MAX_TRAIN_SAMPLES = 60000

            print(f"Notebook configured for {EXP_ID}")
            """
        ),
        _md("## Embedded Plan Payload"),
        _code(
            f"""
            PLAN_PAYLOAD = {_json_literal(plan_payload)}
            MAJOR_EVENTS_PAYLOAD = {_json_literal(events_payload)}
            """
        ),
        _md("## Runtime"),
        _code(runtime_source),
        _md("## Load And Validate The Export"),
        _code(
            """
            spec = get_experiment_spec(EXP_ID)
            export_dir = resolve_export_dir(EXPORT_DATASET_CANDIDATES, EXPORT_DIR_OVERRIDE)
            dataset = load_plan_dataset(export_dir)
            contract = validate_dataset_contract(dataset)
            display_dataset_report(EXP_ID, dataset, contract)
            """
        ),
        _md("## Run The Selected Sector Or Regime Experiment"),
        _code(
            """
            result = run_sector_or_regime_experiment(
                EXP_ID,
                dataset=dataset,
                output_root=OUTPUT_ROOT,
                version=VERSION,
                max_splits=MAX_SPLITS,
                best_ratio_params_override=BEST_RATIO_PARAMS_OVERRIDE,
            )
            display_experiment_result(result, show_top_rows=SHOW_TOP_ROWS)
            result
            """
        ),
        _md("## Output Files"),
        _code(
            """
            exp_root = OUTPUT_ROOT / f"{EXP_ID.lower().replace('-', '_')}_{VERSION}"
            files = sorted(str(path.relative_to(exp_root)) for path in exp_root.rglob("*") if path.is_file())
            pd.DataFrame({"output_files": files})
            """
        ),
    ]


def main() -> None:
    plan_payload = _load_plan_payload()
    events_payload = _load_events_payload()
    runtime_source = _runtime_source()

    ratio_repo = NOTEBOOK_DIR / "northstar_exp09_12_ratio_campaign.ipynb"
    ratio_downloads = DOWNLOADS_DIR / "northstar_exp09_12_ratio_campaign (1).ipynb"
    sector_repo = NOTEBOOK_DIR / "northstar_exp13_19_sector_regime.ipynb"
    sector_downloads = DOWNLOADS_DIR / "northstar_exp13_19_sector_regime.ipynb"

    _write_notebook(ratio_repo, _ratio_cells(plan_payload, events_payload, runtime_source))
    _write_notebook(ratio_downloads, _ratio_cells(plan_payload, events_payload, runtime_source))
    _write_notebook(sector_repo, _sector_regime_cells(plan_payload, events_payload, runtime_source))
    _write_notebook(sector_downloads, _sector_regime_cells(plan_payload, events_payload, runtime_source))

    print(
        json.dumps(
            {
                "ratio_repo": str(ratio_repo),
                "ratio_downloads": str(ratio_downloads),
                "sector_repo": str(sector_repo),
                "sector_downloads": str(sector_downloads),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
