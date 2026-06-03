"""Training harness for India-focused NER fine-tuning."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


class IndiaNERTrainer:
    """Prepares and fine-tunes a token-classification model for Indian finance."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}

    def train(
        self,
        annotations_path: str = "data/nlp/training/ner_annotations/annotations.parquet",
        output_dir: str = "data/nlp/models/india_ner",
    ) -> dict[str, Any]:
        if not Path(annotations_path).exists():
            return {"status": "skipped", "reason": "annotations_missing"}
        annotations = pd.read_parquet(annotations_path)
        if annotations.empty:
            return {"status": "skipped", "reason": "annotations_empty"}
        if {"tokens", "ner_tags"} - set(annotations.columns):
            return {"status": "skipped", "reason": "invalid_schema"}
        try:
            from datasets import Dataset
            from transformers import (
                AutoModelForTokenClassification,
                AutoTokenizer,
                DataCollatorForTokenClassification,
                Trainer,
                TrainingArguments,
            )
        except ImportError as exc:
            raise RuntimeError("Install transformers and datasets to train the NER model") from exc

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        tokenizer = AutoTokenizer.from_pretrained("dslim/bert-base-NER")
        model = AutoModelForTokenClassification.from_pretrained("dslim/bert-base-NER")
        dataset = Dataset.from_pandas(annotations[["tokens", "ner_tags"]])

        def tokenize_and_align(batch: dict[str, Any]) -> dict[str, Any]:
            tokenized = tokenizer(batch["tokens"], is_split_into_words=True, truncation=True, padding="max_length")
            tokenized["labels"] = batch["ner_tags"]
            return tokenized

        tokenized = dataset.map(tokenize_and_align, batched=False)
        trainer = Trainer(
            model=model,
            args=TrainingArguments(
                output_dir=str(output_path),
                learning_rate=2e-5,
                num_train_epochs=3,
                per_device_train_batch_size=8,
                save_strategy="epoch",
                remove_unused_columns=False,
            ),
            train_dataset=tokenized,
            data_collator=DataCollatorForTokenClassification(tokenizer),
        )
        trainer.train()
        trainer.save_model(str(output_path))
        tokenizer.save_pretrained(str(output_path))
        return {"status": "ok", "output_dir": str(output_path), "n_examples": int(len(annotations))}
