"""Old-vs-new sentiment comparison report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.nlp.evaluation.nlp_ic_validator import NLPICValidator


class ComparisonReport:
    """Compares backup sentiment IC vs the new NLP-generated sentiment IC."""

    def build(
        self,
        *,
        baseline_path: str,
        candidate_path: str,
        prices_path: str = "data/canonical/prices/equity_prices_daily.parquet",
        output_path: str = "data/nlp/evaluation/ic_reports/comparison_report.json",
    ) -> dict[str, Any]:
        baseline = NLPICValidator(sentiment_path=baseline_path, prices_path=prices_path).run_full_validation()
        candidate = NLPICValidator(sentiment_path=candidate_path, prices_path=prices_path).run_full_validation()
        result = {
            "baseline": baseline,
            "candidate": candidate,
            "improvement": float(candidate.get("mean_ic", 0.0) - baseline.get("mean_ic", 0.0)),
            "candidate_beats_baseline": bool(candidate.get("mean_ic", 0.0) > baseline.get("mean_ic", 0.0)),
        }
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        return result
