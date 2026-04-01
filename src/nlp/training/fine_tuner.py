"""Fine-tuning harness for India-specific FinBERT sentiment."""

from __future__ import annotations

import logging
import inspect
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class FinBERTFineTuner:
    """Wraps transformer fine-tuning so it can be triggered from ops or research."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._config = config or {}
        self._training_cfg = self._config.get("nlp", {}).get("training", {})

    def fine_tune(
        self,
        dataset_path: str = "data/nlp/training/labeled_sentiment/auto_labeled_dataset.parquet",
        output_dir: str = "data/nlp/models/finbert_india",
    ) -> dict[str, Any]:
        dataset = pd.read_parquet(dataset_path)
        min_examples = int(self._training_cfg.get("min_labeled_examples", 500))
        if len(dataset) < min_examples:
            return {"status": "skipped", "reason": f"need >= {min_examples} examples", "n_examples": int(len(dataset))}
        try:
            from datasets import Dataset
            from transformers import (
                AutoModelForSequenceClassification,
                AutoTokenizer,
                Trainer,
                TrainingArguments,
            )
        except ImportError as exc:
            raise RuntimeError("Install transformers and datasets to fine-tune FinBERT") from exc

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        label_map = {"positive": 0, "negative": 1, "neutral": 2}
        dataset = dataset[dataset["label"].isin(label_map)].copy()
        if len(dataset) < 2:
            return {"status": "skipped", "reason": "need >= 2 labeled examples", "n_examples": int(len(dataset))}
        dataset["label_id"] = dataset["label"].map(label_map)
        train_df, val_df = self._train_validation_split(dataset)

        base_model_path = self._resolve_base_model_path()
        tokenizer = AutoTokenizer.from_pretrained(base_model_path)
        max_length = int(self._training_cfg.get("tokenizer_max_length", 256))

        def tokenize(batch: dict[str, Any]) -> dict[str, Any]:
            tokens = tokenizer(batch["text"], truncation=True, padding="max_length", max_length=max_length)
            tokens["labels"] = batch["label_id"]
            return tokens

        train_source = Dataset.from_pandas(train_df[["text", "label_id"]], preserve_index=False)
        val_source = Dataset.from_pandas(val_df[["text", "label_id"]], preserve_index=False)
        train_ds = train_source.map(tokenize, batched=True, remove_columns=train_source.column_names)
        val_ds = val_source.map(tokenize, batched=True, remove_columns=val_source.column_names)

        model = AutoModelForSequenceClassification.from_pretrained(base_model_path, num_labels=3)
        frozen_backbone = self._freeze_backbone_if_configured(model)
        training_args_params = inspect.signature(TrainingArguments.__init__).parameters
        evaluation_strategy_param = None
        if "evaluation_strategy" in training_args_params:
            evaluation_strategy_param = "evaluation_strategy"
        elif "eval_strategy" in training_args_params:
            evaluation_strategy_param = "eval_strategy"
        args_kwargs = {
            "output_dir": str(output_path),
            "learning_rate": float(self._training_cfg.get("learning_rate", 2e-5)),
            "num_train_epochs": float(self._training_cfg.get("epochs", 3)),
            "weight_decay": float(self._training_cfg.get("weight_decay", 0.01)),
            "per_device_train_batch_size": int(self._training_cfg.get("per_device_train_batch_size", 4)),
            "per_device_eval_batch_size": int(self._training_cfg.get("per_device_eval_batch_size", 4)),
            "gradient_accumulation_steps": int(self._training_cfg.get("gradient_accumulation_steps", 2)),
            "save_strategy": "epoch",
            "save_total_limit": int(self._training_cfg.get("save_total_limit", 1)),
            "logging_steps": int(self._training_cfg.get("logging_steps", 25)),
            "load_best_model_at_end": evaluation_strategy_param is not None,
            "remove_unused_columns": False,
            "dataloader_num_workers": int(self._training_cfg.get("dataloader_num_workers", 0)),
            "report_to": [],
            "fp16": False,
            "bf16": False,
            "seed": int(self._training_cfg.get("random_seed", 42)),
        }
        if evaluation_strategy_param is not None:
            args_kwargs[evaluation_strategy_param] = "epoch"
            if "metric_for_best_model" in training_args_params:
                args_kwargs["metric_for_best_model"] = str(self._training_cfg.get("metric_for_best_model", "eval_macro_f1"))
            if "greater_is_better" in training_args_params:
                args_kwargs["greater_is_better"] = bool(self._training_cfg.get("greater_is_better", True))
        else:
            logger.warning("TrainingArguments has no evaluation strategy parameter; disabling eval scheduling")
        if "warmup_ratio" in training_args_params:
            args_kwargs["warmup_ratio"] = float(self._training_cfg.get("warmup_ratio", 0.10))
        if "lr_scheduler_type" in training_args_params:
            args_kwargs["lr_scheduler_type"] = str(self._training_cfg.get("lr_scheduler_type", "linear"))
        if "max_grad_norm" in training_args_params:
            args_kwargs["max_grad_norm"] = float(self._training_cfg.get("max_grad_norm", 1.0))
        if bool(self._training_cfg.get("use_cpu", False)):
            if "use_cpu" in training_args_params:
                args_kwargs["use_cpu"] = True
            elif "no_cuda" in training_args_params:
                args_kwargs["no_cuda"] = True
        args = TrainingArguments(**args_kwargs)
        trainer = Trainer(
            model=model,
            args=args,
            train_dataset=train_ds,
            eval_dataset=val_ds,
            compute_metrics=self._compute_metrics,
        )
        trainer.train()
        trainer.save_model(str(output_path))
        tokenizer.save_pretrained(str(output_path))
        return {
            "status": "ok",
            "output_dir": str(output_path),
            "n_examples": int(len(dataset)),
            "base_model_path": base_model_path,
            "frozen_backbone": frozen_backbone,
            "train_examples": int(len(train_df)),
            "validation_examples": int(len(val_df)),
        }

    def _resolve_base_model_path(self) -> str:
        sentiment_cfg = self._config.get("nlp", {}).get("models", {}).get("sentiment", {})
        continue_from_india = bool(self._training_cfg.get("continue_from_india_model", False))
        india_path = Path(sentiment_cfg.get("india_finetuned_path", "data/nlp/models/finbert_india"))
        base_path = Path(sentiment_cfg.get("local_path", "data/nlp/models/finbert_base"))
        hf_model_id = str(sentiment_cfg.get("hf_model_id", "ProsusAI/finbert"))
        if continue_from_india and (india_path / "config.json").exists():
            return str(india_path)
        if (base_path / "config.json").exists():
            return str(base_path)
        if (india_path / "config.json").exists():
            return str(india_path)
        return hf_model_id

    def _train_validation_split(self, dataset: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        validation_fraction = float(self._training_cfg.get("validation_split", 0.15))
        seed = int(self._training_cfg.get("random_seed", 42))
        test_size = min(max(validation_fraction, 1 / max(len(dataset), 2)), 0.5)
        try:
            from sklearn.model_selection import train_test_split

            stratify = dataset["label"] if dataset["label"].nunique() > 1 else None
            train_df, val_df = train_test_split(
                dataset,
                test_size=test_size,
                random_state=seed,
                stratify=stratify,
            )
            return train_df.reset_index(drop=True), val_df.reset_index(drop=True)
        except Exception:
            val_size = min(max(1, int(len(dataset) * validation_fraction)), len(dataset) - 1)
            train_df = dataset.iloc[:-val_size].copy()
            val_df = dataset.iloc[-val_size:].copy()
            return train_df.reset_index(drop=True), val_df.reset_index(drop=True)

    def _freeze_backbone_if_configured(self, model: Any) -> bool:
        if not bool(self._training_cfg.get("freeze_base_model", False)):
            return False
        for param in model.parameters():
            param.requires_grad = False
        trainable_markers = tuple(self._training_cfg.get("trainable_head_patterns", ["classifier", "score", "pre_classifier"]))
        unfreeze_last_n_layers = int(self._training_cfg.get("unfreeze_last_n_layers", 0))
        for name, param in model.named_parameters():
            if any(marker in name for marker in trainable_markers):
                param.requires_grad = True
                continue
            if unfreeze_last_n_layers > 0 and self._is_in_last_encoder_layers(name, unfreeze_last_n_layers):
                param.requires_grad = True
        return True

    @staticmethod
    def _is_in_last_encoder_layers(name: str, unfreeze_last_n_layers: int) -> bool:
        if unfreeze_last_n_layers <= 0:
            return False
        marker = "encoder.layer."
        if marker not in name:
            return False
        try:
            suffix = name.split(marker, 1)[1]
            layer_idx = int(suffix.split(".", 1)[0])
        except Exception:
            return False
        return layer_idx >= 12 - unfreeze_last_n_layers

    @staticmethod
    def _compute_metrics(eval_pred: Any) -> dict[str, float]:
        if hasattr(eval_pred, "predictions") and hasattr(eval_pred, "label_ids"):
            logits = eval_pred.predictions
            labels = eval_pred.label_ids
        else:
            logits, labels = eval_pred
        predictions = np.argmax(logits, axis=-1)
        accuracy = float((predictions == labels).mean()) if len(labels) else 0.0
        try:
            from sklearn.metrics import f1_score

            macro_f1 = float(f1_score(labels, predictions, average="macro"))
        except Exception:
            macro_f1 = 0.0
        return {"accuracy": accuracy, "macro_f1": macro_f1}
