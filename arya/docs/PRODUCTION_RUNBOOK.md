# Arya Production Runbook

This runbook is the practical path from the local Arya scaffold to the full
production-grade system described in the plan.

## 1. Collect Raw Corpus

Use conservative daily slices for exchange/regulator sites. Avoid aggressive
parallel scraping.

```bash
python3 -m arya.cli collect nse data/arya/raw --from-date 2026-04-01 --to-date 2026-04-29
python3 -m arya.cli collect rbi data/arya/raw --limit 100
python3 -m arya.cli collect sebi data/arya/raw --limit 100
python3 -m arya.cli collect news data/arya/raw --per-feed-limit 100
python3 -m arya.cli collect wikipedia data/arya/raw
```

Every collector writes:

- source text under `data/arya/raw/<source>/`
- raw payloads under `data/arya/raw/_raw/<source>/`
- append-only provenance under `data/arya/raw/manifest.jsonl`

## 2. Export Northstar Text

Northstar state, reports, manifests, and research artifacts are high-value
domain data. Export them into the same raw corpus root:

```python
from pathlib import Path
from arya.data import NorthstarCorpusExporter

NorthstarCorpusExporter(
    Path("/path/to/northstar_v3"),
    Path("data/arya/raw"),
).export_all()
```

## 3. Clean and Split

```bash
python3 -m arya.cli clean-corpus data/arya/raw data/arya/clean --min-words 50
python3 -m arya.cli split-corpus data/arya/clean data/arya/splits --val-fraction 0.01
```

Run the corpus gate:

```bash
python3 -m arya.cli gate corpus data/arya/clean
```

Do not proceed to tokeniser training until the corpus gate is green or you have
explicitly accepted a smaller experimental run.

## 4. Train Tokeniser

```bash
python3 -m arya.cli train-tokeniser data/arya/splits/train data/arya/tokeniser --vocab-size 32768
python3 -m arya.cli gate tokeniser data/arya/tokeniser/arya-tokeniser.json
```

## 5. Tokenise Corpus

```bash
python3 -m arya.cli tokenise data/arya/splits/train data/arya/tokeniser/arya-tokeniser.json data/arya/train.bin
python3 -m arya.cli tokenise data/arya/splits/val data/arya/tokeniser/arya-tokeniser.json data/arya/val.bin
```

## 6. Pretrain on GPU

Use Kaggle/Colab for 1B/3B training. The local Mac should only run tiny smoke
configs. Checkpoint every few hundred steps and persist checkpoints before the
session ends.

Promotion gate:

```bash
python3 -m arya.cli gate pretraining-log /kaggle/working/checkpoints/log.jsonl
```

## 7. SFT and DPO

Build high-quality labelled examples using `arya.sft.build_sft_data`, train with
`arya.sft.train_sft`, then build preference pairs with `arya.dpo.build_dpo_data`
and train with `arya.dpo.train_dpo`.

Promotion gates:

- SFT held-out task accuracy > 75%
- JSON schema success = 100%
- DPO reward margin > 0.15

## 8. Integration and Safety

Set runtime paths:

```bash
export ARYA_CHECKPOINT_PATH=/path/to/arya-instruct.pt
export ARYA_TOKENISER_PATH=/path/to/arya-tokeniser.json
```

Then use `arya.northstar_bridge.get_arya_runtime()` anywhere an LLM client with
`.complete(system, user, ...)` is expected.

Before live trading integration, benchmark reports must satisfy:

- finance QA accuracy > 70%
- NIL action accuracy > 80%
- ticker validity > 95%
- plausible number rate > 90%
- critical safety failures = 0
