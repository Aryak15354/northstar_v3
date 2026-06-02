# Kaggle Experiment Configs

This directory holds the config-first Kaggle experiment architecture for Northstar V3.

Hierarchy:

- `experiment_base.yaml`: default settings shared by all Kaggle experiments
- `experiments/`: per-run overrides such as `run_007.yaml` and `run_008.yaml`
- `regime_config.yaml`: externally auditable regime boundaries and exposure caps
- `feature_sets/`: named feature selections and force-include sets
- `model_configs/`: reusable model parameter blocks

The intended workflow is:

1. Copy or edit an experiment file in `experiments/`
2. Change only YAML between routine Kaggle runs
3. Keep Python changes for architecture or logic changes, not routine tuning

Use `src/research/config_loader.py` to materialize the merged config for a run.
