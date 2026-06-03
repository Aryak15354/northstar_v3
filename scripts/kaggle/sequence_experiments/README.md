# Northstar V3 Sequence Experiments

This folder reopens EXP-20 through EXP-23 using the validated multi-format
sequence export instead of the old six-feature proxy experiments.

Experiments:

- `EXP-20`: LSTM temporal ranker
- `EXP-21`: GRU temporal ranker
- `EXP-22`: compact Transformer encoder ranker
- `EXP-23`: hybrid LSTM plus static weekly feature MLP

Expected dataset input:

```text
northstar-v3-sequence-export/
  sample_index.parquet
  static_features.parquet
  sequence_walk_forward_splits.json
  sequence_feature_registry.json
  sequence_shards/seq_shard_*.npz
```

Example:

```bash
python scripts/kaggle/sequence_experiments/run_sequence_experiment.py EXP-20 \
  --sequence-dir /kaggle/input/datasets/aryakghoshal/northstar-v3-sequence-export \
  --output-dir /kaggle/working/northstar_sequence_results
```

