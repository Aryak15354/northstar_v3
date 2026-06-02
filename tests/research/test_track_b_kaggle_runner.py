from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SHARED_DIR = ROOT / "notebooks" / "kaggle_sprint" / "shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))

from track_b_runner import TrackBRunConfig, run_track_b_notebook  # noqa: E402
from tests.research.test_track_a_kaggle_runner import _build_synthetic_export  # noqa: E402


def test_track_b_runner_smoke_profile_finishes_and_exports_artifacts(tmp_path):
    data_dir = _build_synthetic_export(tmp_path / "export")
    output_dir = tmp_path / "results"
    config = TrackBRunConfig(
        data_dir=data_dir,
        output_dir=output_dir,
        skip_days={1},
        continue_on_error=True,
        resume_from_checkpoint=True,
        run_profile="smoke",
        max_splits=3,
    )

    state = run_track_b_notebook(config)
    combined = json.loads((output_dir / "track_b_frontier_full_results.json").read_text(encoding="utf-8"))

    assert state["run_summary"]["day_status"]["day7"]["status"] == "completed"
    assert combined["run_state"]["day_status"]["day2"]["status"] == "completed"
    assert "day7_verdict" in combined
    assert "all_model_summaries" in combined
    assert "all_model_stabilities" in combined
    assert (output_dir / "track_b_promotion_memo.md").exists()

    expected_model_artifacts = [
        "patchtst_final.json",
        "tft_final.json",
        "itransformer_final.json",
    ]
    for filename in expected_model_artifacts:
        payload = json.loads((output_dir / filename).read_text(encoding="utf-8"))
        assert "summary" in payload
        assert "stability" in payload
        assert "windows" in payload
