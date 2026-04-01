"""Confidence calibration diagnostics for NLP sentiment scores."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


class CalibrationTester:
    """Measures whether high-confidence headlines are directionally more accurate."""

    def run(
        self,
        headline_scores: pd.DataFrame,
        realized_returns: pd.DataFrame,
        *,
        ticker_col: str = "ticker",
        date_col: str = "date",
        confidence_col: str = "sentiment_confidence",
        polarity_col: str = "polarity",
        output_path: str = "data/nlp/evaluation/ic_reports/calibration_report.json",
    ) -> dict[str, Any]:
        if headline_scores.empty or realized_returns.empty:
            return {"status": "no_data"}
        scores = headline_scores.copy()
        returns = realized_returns.copy()
        scores[date_col] = pd.to_datetime(scores[date_col], errors="coerce").dt.normalize()
        returns[date_col] = pd.to_datetime(returns[date_col], errors="coerce").dt.normalize()
        merged = scores.merge(returns[[ticker_col, date_col, "forward_return"]], on=[ticker_col, date_col], how="inner")
        if merged.empty:
            return {"status": "no_overlap"}
        merged["predicted_positive"] = pd.to_numeric(merged[polarity_col], errors="coerce").fillna(0.0) > 0
        merged["realized_positive"] = pd.to_numeric(merged["forward_return"], errors="coerce").fillna(0.0) > 0
        merged["correct"] = (merged["predicted_positive"] == merged["realized_positive"]).astype(float)
        merged["confidence_bin"] = pd.cut(
            pd.to_numeric(merged[confidence_col], errors="coerce").fillna(0.0),
            bins=np.linspace(0.0, 1.0, 6),
            include_lowest=True,
        )
        by_bin = merged.groupby("confidence_bin", observed=False)["correct"].agg(["mean", "count"]).reset_index()
        result = {
            "overall_accuracy": float(merged["correct"].mean()),
            "by_bin": by_bin.to_dict("records"),
            "n_observations": int(len(merged)),
        }
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        return result
