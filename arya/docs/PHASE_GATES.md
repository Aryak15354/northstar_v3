# Arya Phase Gates

This file separates local smoke gates from real training gates. The smoke gates
are safe to run on an 8GB M1 MacBook Air. The training gates are the criteria
for promoting a checkpoint.

## Phase 0: Environment

Local gate: instantiate a tiny causal transformer block, run forward and
backward on CPU or GPU, and verify finite gradients.

Training gate: Kaggle notebook has PyTorch, tokenizers, datasets, accelerate,
bitsandbytes, and persistent checkpoint storage.

## Phase 1: Corpus

Local gate: cleaner, deduplication, corpus stats, and Northstar export work on
fixtures.

Training gate: at least 500M estimated tokens, average document length >= 100
words, includes regulatory and Northstar documents, and no source contributes
more than 60% of documents.

## Phase 2: Tokeniser

Local gate: a tiny BPE tokeniser preserves special tokens and round-trips
financial text.

Training gate: 32,768 vocabulary size, all special tokens at stable IDs,
finance term fertility <= 2, held-out coverage >= 98%.

## Phase 3: Model

Local gate: `AryaConfig.tiny()` has correct shapes, finite loss, generation,
and loss decreases on a tiny batch.

Training gate: 1B or 3B config fits target parameter range and trains stably
with gradient checkpointing/mixed precision.

## Phase 4: Pretraining

Local gate: token memmap dataset, learning-rate schedule, checkpoint retention,
and evaluation loop work on tiny arrays.

Training gate: validation perplexity below 25 or an explicitly approved retry
plan if the curve plateaus above that level.

## Phase 5: SFT

Local gate: SFT examples mask prompt tokens and train only assistant tokens.

Training gate: >= 75% held-out task accuracy, 100% JSON parse success for
schema-bound tasks, and no catastrophic forgetting on finance QA.

## Phase 6: DPO

Local gate: DPO loss is finite and gradients flow only through the policy.

Training gate: reward margin above 0.15 on held-out preference pairs and lower
overconfidence on ambiguous events.

## Phase 7: Inference

Local gate: `.complete()` returns an `LLMResponse`, cache works, and a tiny
checkpoint can be loaded.

Training gate: T4 p95 latency under 4 seconds, no NaN logits, no empty outputs
across a 100-query stress test.

## Phase 8: Northstar Bridge

Local gate: `get_arya_runtime()` builds a cached runtime from env-configured
checkpoint and tokeniser paths.

Training gate: Northstar's LLM-facing integration tests pass with Arya as the
backend and safety validators active.

## Phase 9: Evaluation and Red Team

Local gate: benchmark helpers score finance QA, ticker validity, and red-team
response validators.

Training gate: finance QA > 70%, valid ticker rate > 95%, plausible number
rate > 90%, confidence calibration delta > 0.15, and zero critical safety
failures.

