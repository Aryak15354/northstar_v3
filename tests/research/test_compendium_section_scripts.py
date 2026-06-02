from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.kaggle.plan_2026_04_05.catalog import get_experiment_spec
from scripts.kaggle.plan_2026_04_05.common import load_plan_dataset
from scripts.kaggle.plan_2026_04_05.signal_verification import run_verification_experiment
from scripts.kaggle.plan_2026_04_08_sections.lib import build_dataset_audit, resolve_execution_order
from tests.research.test_separate_compendium_scripts import _build_dirty_sector_export
from tests.research.test_track_a_kaggle_runner import _build_synthetic_export


def test_section_execution_order_pulls_ratio_prerequisites() -> None:
    order = resolve_execution_order(["EXP-13", "EXP-14", "EXP-15", "EXP-16"])

    assert order == ["EXP-09", "EXP-10", "EXP-11", "EXP-12", "EXP-13", "EXP-14", "EXP-15", "EXP-16"]


def test_dataset_audit_marks_missing_earnings_quality_family(tmp_path: Path) -> None:
    export_dir = _build_dirty_sector_export(tmp_path / "audit_export")
    dataset = load_plan_dataset(export_dir)

    audit = build_dataset_audit(dataset)

    assert audit["verification_readiness"]["exp27_earnings_quality_family"]["missing"] == [
        "accruals_ratio",
        "accruals_ratio_cs_z",
        "accruals_ratio_cs_rank",
        "earnings_quality_ratio",
        "earnings_quality_ratio_cs_rank",
    ]
    assert audit["sector_counts_actual"]["Financial Services"] == 4


def test_exp27_returns_dataset_gap_when_earnings_quality_family_missing(tmp_path: Path) -> None:
    export_dir = _build_synthetic_export(tmp_path / "verification_export")
    dataset = load_plan_dataset(export_dir)
    spec = get_experiment_spec("EXP-27")

    payload = run_verification_experiment(
        spec,
        dataset=dataset,
        output_root=tmp_path / "outputs",
        profile="smoke",
        max_splits=1,
        version="test",
    )

    assert payload["status"] == "dataset_gap"
    assert payload["proxy_feature"] is None


def test_section_script_runs_as_plain_python_file() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "kaggle" / "plan_2026_04_08_sections" / "run_section_ratio_09_12.py"

    result = subprocess.run(
        [sys.executable, str(script), "--describe"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Section 3 - Ratio Reduction Campaign" in result.stdout


def test_late_experiment_script_runs_as_plain_python_file() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "kaggle" / "plan_2026_04_08" / "run_exp27.py"

    result = subprocess.run(
        [sys.executable, str(script), "--describe"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "India Earnings Quality Sign Deep Validation" in result.stdout
