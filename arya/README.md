# Arya

Arya is the standalone Northstar finance LLM system. It is kept outside `src/`
on purpose: the model, tokeniser, data pipeline, training code, inference
runtime, and benchmark suite should remain plug-and-play for future systems.

The local repository contains the lightweight control plane and smoke-tested
implementation. Full 1B/3B training is expected to run on Kaggle/Colab GPU
sessions using the same interfaces.

## Design Rules

- Keep imports from Northstar optional and one-way. Arya can read/export
  Northstar artifacts, but core Arya modules must not depend on trading runtime
  internals.
- Keep laptop tests tiny. Local tests use `AryaConfig.tiny()` and fixture
  corpora so an 8GB M1 Mac can run them.
- Keep large training gates explicit. Corpus size, perplexity, SFT accuracy,
  DPO margin, latency, and red-team gates are documented as release criteria,
  not laptop smoke tests.
- Keep runtime integration behind `.complete(system, user, ...)`, matching the
  interface expected by Northstar LLM callers.

## Package Map

- `arya.data`: scrapers, cleaners, corpus analysis, Northstar export.
- `arya.tokeniser`: custom BPE training and special token definitions.
- `arya.model`: decoder-only transformer with RMSNorm, SwiGLU, RoPE, and GQA.
- `arya.training`: token binary conversion, memmap dataset, pretraining loop.
- `arya.sft`: instruction-tuning data format and dataset.
- `arya.dpo`: direct preference optimisation loss.
- `arya.inference`: checkpoint loading, optional quantisation, runtime wrapper.
- `arya.eval`: finance QA, hallucination checks, and red-team cases.
- `arya.northstar_bridge`: cached runtime constructor for drop-in integration.

## Local Smoke Tests

Run Arya's local phase tests with:

```bash
python3 -m pytest tests/arya -q
```

These tests do not train a large model. They verify that every phase boundary
works using tiny fixtures.

## Production Pipeline

The operator CLI is available as:

```bash
python3 -m arya.cli --help
```

Production source defaults live in `arya/config/production_sources.yaml`. The
full collection, cleaning, tokeniser, training, and gate workflow is documented
in `arya/docs/PRODUCTION_RUNBOOK.md`.

## Real Release Gates

The real gates from the build plan remain the standard for promoting Arya:

- Phase 1: cleaned corpus >= 500M estimated tokens with balanced sources.
- Phase 2: 32,768-token BPE tokeniser, finance fertility <= 2, coverage >= 98%.
- Phase 3: 1B/3B architecture passes forward/backward and smoke loss descent.
- Phase 4: finance validation perplexity plateaus below 25.
- Phase 5: held-out task accuracy above 75% with valid JSON outputs.
- Phase 6: DPO reward margin above 0.15.
- Phase 7: T4 p95 latency below 4 seconds and no generation failures.
- Phase 8: Northstar integration suite passes with Arya backend.
- Phase 9: finance QA above 70%, ticker validity above 95%, zero P0 failures.
