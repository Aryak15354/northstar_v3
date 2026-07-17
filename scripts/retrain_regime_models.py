#!/usr/bin/env python3
"""Retrain all regime models with regularization and verify train ICs."""

from __future__ import annotations

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))

from src.research.regime_conditional_trainer import RegimeConditionalTrainer
from src.research.dataset_manager import DatasetManager
from src.research.feature_pit_rules import default_feature_pit_lags, default_pit_day_config


def main() -> int:
    print("=== Retraining Regime Models with Regularization ===")
    print("")
    
    # Build dataset. The canonical macro panel is MONTHLY (GST/power series),
    # so ~7 years of real history is ~87 rows — the default 200-row floor was
    # calibrated for daily artifacts and made retraining impossible even with
    # perfectly healthy data. 60 monthly rows (5 years) is the honest minimum.
    print("Building research dataset...")
    dm = DatasetManager(config={
        "artifact_min_rows": {"macro": 60},
        # canonical PIT discipline shared with the Kaggle export (see
        # src/research/feature_pit_rules.py) — without it, the strict PIT
        # guard rejects every feature and retraining is impossible.
        "feature_pit_lags": default_feature_pit_lags(),
        **default_pit_day_config(),
        # match the Kaggle export's strictness profile exactly: the trainer's
        # own regularization handles dimensionality/collinearity; the default
        # 28-feature budget + correlation rejection were calibrated for
        # hand-picked factor sets and make full-panel training impossible.
        "feature_budget": 500,
        "feature_budget_enforce": False,
        "feature_correlation_enforce": False,
        "feature_correlation_skip": True,
    })
    ds = dm.build_research_dataset()
    
    if ds.frame.empty:
        print("ERROR: Dataset is empty!")
        return 1
    
    target_col = str(ds.metadata.get("target_col", "forward_return_5d"))
    print(f"Dataset built: {len(ds.frame)} rows, {len(ds.feature_names)} features")
    print(f"Target column: {target_col}")
    print("")
    
    # Train all regime models
    print("Training regime models...")
    trainer = RegimeConditionalTrainer()
    trainer.train_all_regimes(
        panel_df=ds.frame,
        feature_cols=ds.feature_names,
        target_col=target_col,
        regime_col="regime"
    )
    
    # Load and print registry
    print("")
    print("=== Regime Model Registry ===")
    registry_path = Path("models/regime_models/regime_model_registry.json")
    
    if not registry_path.exists():
        print("ERROR: Registry not found!")
        return 1
    
    with registry_path.open("r") as f:
        registry = json.load(f)
    
    models = registry.get("models", {})
    
    print("")
    print(f"Total regimes trained: {len(models)}")
    print("")
    
    all_ics = []
    for regime_name, model_info in sorted(models.items()):
        train_ic = float(model_info.get("train_ic", 0.0))
        n_obs = int(model_info.get("n_obs", 0))
        backend = str(model_info.get("backend", "unknown"))
        
        all_ics.append(train_ic)
        
        status = "✓" if 0.3 <= train_ic <= 0.5 else "⚠" if train_ic > 0.5 else "✗"
        print(f"{status} {regime_name}")
        print(f"    Train IC: {train_ic:.4f} | Obs: {n_obs:,} | Backend: {backend}")
        
        # Print top 5 features
        fi = model_info.get("feature_importance", {})
        if fi:
            top_features = sorted(fi.items(), key=lambda x: x[1], reverse=True)[:5]
            feat_str = ", ".join([f"{f}" for f, _ in top_features])
            print(f"    Top features: {feat_str}")
        print("")
    
    # Summary
    print("=== Summary ===")
    avg_ic = sum(all_ics) / len(all_ics) if all_ics else 0.0
    min_ic = min(all_ics) if all_ics else 0.0
    max_ic = max(all_ics) if all_ics else 0.0
    
    print(f"Average Train IC: {avg_ic:.4f}")
    print(f"Min Train IC: {min_ic:.4f}")
    print(f"Max Train IC: {max_ic:.4f}")
    print("")
    
    # Verify ICs are in target range
    in_range = sum(1 for ic in all_ics if 0.3 <= ic <= 0.5)
    overfit = sum(1 for ic in all_ics if ic > 0.5)
    underfit = sum(1 for ic in all_ics if ic < 0.3)
    
    print(f"Models in target range (0.3-0.5): {in_range}/{len(all_ics)}")
    print(f"Models overfitting (>0.5): {overfit}/{len(all_ics)}")
    print(f"Models underfitting (<0.3): {underfit}/{len(all_ics)}")
    print("")
    
    if avg_ic > 0.5:
        print("⚠ WARNING: Average IC still too high. Consider stronger regularization.")
    elif avg_ic < 0.3:
        print("⚠ WARNING: Average IC too low. Consider relaxing regularization.")
    else:
        print("✓ Regularization successful! Train ICs in target range.")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
