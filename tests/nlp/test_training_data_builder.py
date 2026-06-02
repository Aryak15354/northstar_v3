from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.nlp.training.training_data_builder import TrainingDataBuilder


class _FakeTeacherScorer:
    def score_batch(self, texts: list[str]):
        mapping = {
            "Infosys beats estimates": ("positive", 0.92, 0.78),
            "Infosys beats estimates!!!": ("positive", 0.90, 0.74),
            "Promoter arrested for fraud": ("negative", 0.93, -0.81),
            "Company says operations unchanged": ("neutral", 0.64, 0.02),
            "Noisy positive return but weak headline": ("neutral", 0.40, 0.01),
        }
        scores = []
        for text in texts:
            label, confidence, polarity = mapping[text]
            scores.append(
                type(
                    "Score",
                    (),
                    {
                        "text": text,
                        "predicted_label": label,
                        "confidence": confidence,
                        "polarity": polarity,
                    },
                )()
            )
        return scores


def test_build_high_quality_dataset_filters_by_teacher_and_deduplicates(tmp_path, monkeypatch):
    news_path = tmp_path / "news.parquet"
    prices_path = tmp_path / "prices.parquet"
    output_dir = tmp_path / "out"

    pd.DataFrame(
        {
            "date": pd.to_datetime(
                [
                    "2026-01-01",
                    "2026-01-01",
                    "2026-01-01",
                    "2026-01-01",
                    "2026-01-01",
                ]
            ),
            "ticker": ["INFY", "INFY", "ABC", "XYZ", "INFY"],
            "headline": [
                "Infosys beats estimates",
                "Infosys beats estimates!!!",
                "Promoter arrested for fraud",
                "Company says operations unchanged",
                "Noisy positive return but weak headline",
            ],
        }
    ).to_parquet(news_path, index=False)

    pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-02"]),
            "ticker": ["INFY", "INFY"],
            "close": [100.0, 105.0],
        }
    ).to_parquet(prices_path, index=False)
    extra = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-01", "2026-01-02"]),
            "ticker": ["ABC", "ABC", "XYZ", "XYZ"],
            "close": [100.0, 94.0, 100.0, 100.2],
        }
    )
    prices = pd.concat([pd.read_parquet(prices_path), extra], ignore_index=True)
    prices.to_parquet(prices_path, index=False)

    builder = TrainingDataBuilder(
        news_path=str(news_path),
        prices_path=str(prices_path),
        output_dir=str(output_dir),
        config={
            "nlp": {
                "training": {
                    "high_quality_positive_threshold": 0.04,
                    "high_quality_negative_threshold": -0.04,
                    "high_quality_neutral_abs_threshold": 0.01,
                    "teacher_min_confidence": 0.75,
                    "teacher_neutral_min_confidence": 0.45,
                    "teacher_neutral_max_abs_polarity": 0.12,
                    "deduplicate_training_text": True,
                    "max_examples_per_ticker_per_class": 5,
                }
            }
        },
    )
    monkeypatch.setattr(builder, "_build_teacher_scorer", lambda: _FakeTeacherScorer())

    curated = builder.build_high_quality_dataset(min_examples_per_class=5, max_total_examples=10)

    assert not curated.empty
    assert set(curated["label"]) == {"positive", "negative", "neutral"}
    assert "Noisy positive return but weak headline" not in set(curated["text"])
    positive_texts = set(curated[curated["label"] == "positive"]["text"])
    assert len(positive_texts) == 1
    assert Path(output_dir / "auto_labeled_dataset_high_quality.parquet").exists()
