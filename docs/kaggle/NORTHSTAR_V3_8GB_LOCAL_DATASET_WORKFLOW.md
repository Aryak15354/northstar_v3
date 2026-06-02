# Northstar V3 8 GB Local Dataset Workflow

This workflow updates the Kaggle architecture in the compendium for an 8 GB M1 Air.

The original plan is still the right one in spirit:

1. build the dataset locally
2. never hold the full matrix in memory
3. upload an intermediate dataset layer to Kaggle
4. let Kaggle do the final merge and experiments

The change is operational, not conceptual: the monolithic feature export dataset is replaced by a chunk dataset that can be built safely on a smaller laptop.

## Updated architecture

Use six layers instead of trying to make the laptop produce one final giant Parquet in a single pass.

1. `northstar-v3-raw-bundle`
   contains the canonical local data bundle and support artifacts
2. local chunk build root
   written by `scripts/kaggle/build_local_feature_chunks.py`
3. `northstar-v3-feature-chunks`
   Kaggle dataset created from the local chunk build root
4. `northstar-v3-code`
   existing code bundle dataset
5. Kaggle working export
   created by `scripts/kaggle/merge_chunked_feature_dataset.py`
   writes `northstar_features.parquet`, `northstar_metadata.parquet`, `northstar_regime_labels.parquet`, and `northstar_walk_forward_splits.json`
6. Kaggle run outputs
   `runs/{run_id}/...` from the existing weekly suite

This preserves the current weekly notebook contract. The experiments still read the same final files. The only change is how those files are produced.

## Hard safety rules

These rules are mandatory for the final frozen dataset.

1. Use `--threads 2` and `--duckdb-threads 1`.
2. Keep `--max-tickers 0` and `--max-rows 0` so no hidden downsampling occurs.
3. Build date chunks one at a time.
4. Keep warmup and forward buffers enabled so rolling features and targets remain correct at chunk boundaries.
5. Run strict signal validation before the full build.
6. Do not use proxies in the final frozen dataset.

`--allow-proxies true` is acceptable only for plumbing smoke tests. It is not acceptable for the final research dataset if the goal is full plan fidelity.

## Current strict blockers

The local inventory is not yet complete for the exact plan signal block. The strict audit is expected to block until the missing exact series are staged locally.

Expected blockers from the current repository state:

1. direct DXY history
2. direct steel or HRC history
3. direct coal history
4. direct US 10Y history
5. exact India VIX if the feature stack does not already surface it

That is intentional. The builder is designed to fail fast instead of silently freezing a partial dataset.

## Local commands

Create a dedicated output root first:

```bash
mkdir -p /Users/aryakghoshal/Downloads/northstar/northstar_v3/tmp/northstar_v3_chunk_build
```

Run the strict contract audit first. This should pass before the final build is allowed.

```bash
python3 scripts/kaggle/build_local_feature_chunks.py \
  --data-dir /Users/aryakghoshal/Downloads/northstar/northstar_v3 \
  --output-dir /Users/aryakghoshal/Downloads/northstar/northstar_v3/tmp/northstar_v3_chunk_build \
  --threads 2 \
  --duckdb-threads 1 \
  --duckdb-memory-limit-mb 640 \
  --chunk-months 4 \
  --warmup-days 420 \
  --forward-buffer-days 10 \
  --allow-proxies false \
  --strict-plan-signals true \
  --max-tickers 0 \
  --max-rows 0 \
  --validate-only
```

Only after the audit is clean, run the full local chunk build:

```bash
python3 scripts/kaggle/build_local_feature_chunks.py \
  --data-dir /Users/aryakghoshal/Downloads/northstar/northstar_v3 \
  --output-dir /Users/aryakghoshal/Downloads/northstar/northstar_v3/tmp/northstar_v3_chunk_build \
  --threads 2 \
  --duckdb-threads 1 \
  --duckdb-memory-limit-mb 640 \
  --chunk-months 4 \
  --warmup-days 420 \
  --forward-buffer-days 10 \
  --allow-proxies false \
  --strict-plan-signals true \
  --max-tickers 0 \
  --max-rows 0
```

For plumbing only, if you want to verify the pipeline before the missing exact series are staged, use:

```bash
python3 scripts/kaggle/build_local_feature_chunks.py \
  --data-dir /Users/aryakghoshal/Downloads/northstar/northstar_v3 \
  --output-dir /Users/aryakghoshal/Downloads/northstar/northstar_v3/tmp/northstar_v3_chunk_build_smoke \
  --threads 2 \
  --duckdb-threads 1 \
  --duckdb-memory-limit-mb 640 \
  --chunk-months 4 \
  --warmup-days 420 \
  --forward-buffer-days 10 \
  --allow-proxies true \
  --strict-plan-signals false \
  --max-tickers 50 \
  --max-rows 50000
```

Do not treat that smoke output as the final research dataset.

## Preparing the Kaggle datasets

Prepare the chunk dataset upload folder without duplicating storage where possible:

```bash
bash scripts/kaggle/prepare_feature_chunk_dataset_upload.sh \
  /Users/aryakghoshal/Downloads/northstar/northstar_v3/tmp/northstar_v3_chunk_build \
  <your-kaggle-username>/northstar-v3-feature-chunks \
  /Users/aryakghoshal/Downloads/northstar/northstar_v3/tmp/kaggle_uploads/feature_chunks \
  "Northstar V3 Feature Chunks"
```

Prepare the code bundle dataset with the existing helper:

```bash
bash scripts/kaggle/prepare_code_dataset_upload.sh \
  <your-kaggle-username>/northstar-v3-code
```

## Kaggle-side merge

Attach these datasets to the notebook:

1. raw bundle dataset
2. feature chunk dataset
3. code dataset

Then merge the chunks inside Kaggle working storage:

```bash
python3 /kaggle/input/northstar-v3-code/scripts/kaggle/merge_chunked_feature_dataset.py \
  --chunk-root /kaggle/input/northstar-v3-feature-chunks \
  --output-dir /kaggle/working/northstar_v3_export
```

After that, the weekly suite can use `/kaggle/working/northstar_v3_export` as the feature export root because it contains:

1. `northstar_features.parquet`
2. `northstar_metadata.parquet`
3. `northstar_regime_labels.parquet`
4. `northstar_walk_forward_splits.json`
5. `weekly_export_manifest.json`

## Why this is safer on 8 GB

1. local memory scales with one date chunk, not the whole history
2. the build keeps the existing feature logic, so we avoid reimplementing the research stack
3. strict validation stops the build if required plan signals are missing
4. the final Kaggle merge is deterministic and writes the exact files the experiments expect
5. the chunk upload keeps dataset versioning aligned with the layered Kaggle plan
