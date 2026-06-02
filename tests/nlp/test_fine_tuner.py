from __future__ import annotations

import types
from pathlib import Path

import pandas as pd

from src.nlp.training.fine_tuner import FinBERTFineTuner


class _FakeDataset:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.column_names = list(rows[0].keys()) if rows else []

    @classmethod
    def from_pandas(cls, df: pd.DataFrame, preserve_index: bool = False) -> "_FakeDataset":
        del preserve_index
        return cls(df.to_dict(orient="records"))

    def map(self, fn, batched: bool = False, remove_columns: list[str] | None = None) -> "_FakeDataset":
        del remove_columns
        if not batched:
            raise AssertionError("fine_tuner should use batched tokenization")
        batch = {column: [row[column] for row in self.rows] for column in self.column_names}
        mapped = fn(batch)
        length = len(next(iter(mapped.values()))) if mapped else 0
        rows = [{key: value[idx] for key, value in mapped.items()} for idx in range(length)]
        return _FakeDataset(rows)


class _FakeTokenizer:
    def __call__(self, texts, truncation: bool, padding: str, max_length: int) -> dict[str, list[list[int]]]:
        del truncation, padding, max_length
        if isinstance(texts, str):
            texts = [texts]
        return {
            "input_ids": [[1, 2, 3] for _ in texts],
            "attention_mask": [[1, 1, 1] for _ in texts],
        }

    def save_pretrained(self, output_dir: str) -> None:
        Path(output_dir, "tokenizer_config.json").write_text("{}", encoding="utf-8")


class _FakeModel:
    def __init__(self) -> None:
        self._params = [
            ("bert.encoder.layer.0.weight", _FakeParam()),
            ("bert.encoder.layer.11.weight", _FakeParam()),
            ("classifier.weight", _FakeParam()),
            ("classifier.bias", _FakeParam()),
        ]

    def parameters(self):
        for _, param in self._params:
            yield param

    def named_parameters(self):
        for name, param in self._params:
            yield name, param


class _FakeParam:
    def __init__(self) -> None:
        self.requires_grad = True


class _FakeAutoTokenizer:
    @staticmethod
    def from_pretrained(path: str) -> _FakeTokenizer:
        del path
        return _FakeTokenizer()


class _FakeAutoModel:
    @staticmethod
    def from_pretrained(path: str, num_labels: int) -> _FakeModel:
        del path, num_labels
        return _FakeModel()


class _FakeTrainingArguments:
    def __init__(
        self,
        output_dir: str,
        learning_rate: float,
        num_train_epochs: float,
        weight_decay: float,
        per_device_train_batch_size: int,
        per_device_eval_batch_size: int,
        gradient_accumulation_steps: int,
        save_strategy: str,
        save_total_limit: int,
        logging_steps: int,
        load_best_model_at_end: bool,
        remove_unused_columns: bool,
        dataloader_num_workers: int,
        report_to: list[object],
        fp16: bool,
        bf16: bool,
        eval_strategy: str | None = None,
        use_cpu: bool = False,
        warmup_ratio: float = 0.1,
        lr_scheduler_type: str = "linear",
        max_grad_norm: float = 1.0,
        seed: int = 42,
        metric_for_best_model: str | None = None,
        greater_is_better: bool = True,
    ) -> None:
        del learning_rate, num_train_epochs, weight_decay, per_device_train_batch_size
        del per_device_eval_batch_size, gradient_accumulation_steps, save_strategy
        del save_total_limit, logging_steps, remove_unused_columns, dataloader_num_workers
        del report_to, fp16, bf16, warmup_ratio, lr_scheduler_type, max_grad_norm, seed
        self.output_dir = output_dir
        self.eval_strategy = eval_strategy
        self.use_cpu = use_cpu
        self.load_best_model_at_end = load_best_model_at_end
        self.metric_for_best_model = metric_for_best_model
        self.greater_is_better = greater_is_better


class _FakeTrainer:
    def __init__(
        self,
        model,
        args: _FakeTrainingArguments,
        train_dataset: _FakeDataset,
        eval_dataset: _FakeDataset,
        compute_metrics,
    ) -> None:
        del eval_dataset
        assert args.eval_strategy == "epoch"
        assert args.use_cpu is True
        assert args.load_best_model_at_end is True
        assert args.metric_for_best_model == "eval_macro_f1"
        assert args.greater_is_better is True
        assert train_dataset.rows
        for row in train_dataset.rows:
            assert "labels" in row
            assert "label_id" not in row
        metrics = compute_metrics(([[0.9, 0.05, 0.05], [0.05, 0.9, 0.05]], [0, 1]))
        assert metrics["accuracy"] == 1.0
        assert metrics["macro_f1"] == 1.0
        frozen_encoder_param = next(param for name, param in model.named_parameters() if "encoder.layer.0" in name)
        last_encoder_param = next(param for name, param in model.named_parameters() if "encoder.layer.11" in name)
        classifier_param = next(param for name, param in model.named_parameters() if "classifier.weight" in name)
        assert frozen_encoder_param.requires_grad is False
        assert last_encoder_param.requires_grad is True
        assert classifier_param.requires_grad is True
        self._output_dir = args.output_dir

    def train(self) -> None:
        return None

    def save_model(self, output_dir: str) -> None:
        Path(output_dir, "config.json").write_text("{}", encoding="utf-8")


def _install_fake_modules(monkeypatch) -> None:
    datasets_module = types.ModuleType("datasets")
    datasets_module.Dataset = _FakeDataset

    transformers_module = types.ModuleType("transformers")
    transformers_module.AutoTokenizer = _FakeAutoTokenizer
    transformers_module.AutoModelForSequenceClassification = _FakeAutoModel
    transformers_module.Trainer = _FakeTrainer
    transformers_module.TrainingArguments = _FakeTrainingArguments

    monkeypatch.setitem(__import__("sys").modules, "datasets", datasets_module)
    monkeypatch.setitem(__import__("sys").modules, "transformers", transformers_module)


def test_fine_tune_skips_when_not_enough_examples(tmp_path):
    dataset_path = tmp_path / "tiny.parquet"
    pd.DataFrame({"text": ["only one"], "label": ["positive"]}).to_parquet(dataset_path, index=False)

    result = FinBERTFineTuner({"nlp": {"training": {"min_labeled_examples": 5}}}).fine_tune(dataset_path=str(dataset_path))

    assert result["status"] == "skipped"
    assert "need >=" in result["reason"]


def test_fine_tune_uses_labels_and_eval_strategy_compatible_args(tmp_path, monkeypatch):
    _install_fake_modules(monkeypatch)

    base_model_dir = tmp_path / "finbert_base"
    india_model_dir = tmp_path / "finbert_india"
    base_model_dir.mkdir(parents=True, exist_ok=True)
    india_model_dir.mkdir(parents=True, exist_ok=True)
    (base_model_dir / "config.json").write_text("{}", encoding="utf-8")
    (india_model_dir / "config.json").write_text("{}", encoding="utf-8")

    dataset_path = tmp_path / "train.parquet"
    pd.DataFrame(
        {
            "text": [
                "Infosys beats estimates",
                "Promoter arrested for fraud",
                "RBI keeps rates unchanged",
                "ONGC reports higher PAT",
            ],
            "label": ["positive", "negative", "neutral", "positive"],
        }
    ).to_parquet(dataset_path, index=False)

    config = {
        "nlp": {
            "models": {
                "sentiment": {
                    "local_path": str(base_model_dir),
                    "india_finetuned_path": str(india_model_dir),
                    "use_india_model_if_available": False,
                }
            },
            "training": {
                "min_labeled_examples": 2,
                "validation_split": 0.25,
                "use_cpu": True,
                "freeze_base_model": True,
                "continue_from_india_model": False,
                "unfreeze_last_n_layers": 1,
            },
        }
    }

    result = FinBERTFineTuner(config).fine_tune(
        dataset_path=str(dataset_path),
        output_dir=str(tmp_path / "finbert_india_test"),
    )

    assert result["status"] == "ok"
    assert result["base_model_path"] == str(base_model_dir)
    assert result["frozen_backbone"] is True
    assert Path(result["output_dir"], "config.json").exists()
    assert Path(result["output_dir"], "tokenizer_config.json").exists()
