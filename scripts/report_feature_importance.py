#!/usr/bin/env python3
"""
Report feature importance for all regime models.

Outputs:
1. Top 10 features by regime (printed to terminal)
2. CSV report: reports/feature_importance_by_regime.csv
3. Global importance table (average across all regimes)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    print("=== Feature Importance by Regime ===")
    print("")
    
    registry_path = Path("models/regime_models/regime_model_registry.json")
    
    if not registry_path.exists():
        print("ERROR: Registry not found! Run retrain_regime_models.py first.")
        return 1
    
    with registry_path.open("r") as f:
        registry = json.load(f)
    
    models = registry.get("models", {})
    
    if not models:
        print("ERROR: No models found in registry!")
        return 1
    
    # Collect all feature importances for global analysis
    all_importances: dict[str, list[float]] = {}
    csv_rows = []
    
    print(f"Total regimes: {len(models)}")
    print("")
    
    for regime_name in sorted(models.keys()):
        model_info = models[regime_name]
        fi = model_info.get("feature_importance", {})
        
        if not fi:
            continue
        
        print(f"=== {regime_name} ===")
        print(f"Train IC: {model_info.get('train_ic', 0.0):.4f} | Obs: {model_info.get('n_obs', 0):,}")
        print("")
        print("Top 10 Features (by gain):")
        print("  Rank  Feature                                    Importance")
        
        sorted_fi = sorted(fi.items(), key=lambda x: x[1], reverse=True)[:10]
        for rank, (feature, importance) in enumerate(sorted_fi, start=1):
            print(f"  {rank:<5} {feature:<40} {importance:.6f}")
            
            # Add to CSV rows
            csv_rows.append({
                "regime": regime_name,
                "rank": rank,
                "feature": feature,
                "importance_gain": importance,
                "importance_weight": 0.0  # Will be computed globally
            })
            
            # Collect for global analysis
            if feature not in all_importances:
                all_importances[feature] = []
            all_importances[feature].append(importance)
        
        print("")
    
    # Compute global importance (average across regimes)
    print("=== Global Feature Importance (Average Across Regimes) ===")
    print("")
    print("Top 20 Features:")
    print("  Rank  Feature                                    Avg Importance  Regimes")
    
    global_importance = []
    for feature, importances in all_importances.items():
        avg_imp = sum(importances) / len(importances)
        num_regimes = len(importances)
        global_importance.append((feature, avg_imp, num_regimes))
    
    global_importance.sort(key=lambda x: x[1], reverse=True)
    
    for rank, (feature, avg_imp, num_regimes) in enumerate(global_importance[:20], start=1):
        print(f"  {rank:<5} {feature:<40} {avg_imp:.6f}        {num_regimes}")
        
        # Update CSV rows with weight
        for row in csv_rows:
            if row["feature"] == feature:
                row["importance_weight"] = avg_imp
    
    # Save CSV report
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    csv_path = reports_dir / "feature_importance_by_regime.csv"
    
    import csv
    with csv_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["regime", "rank", "feature", "importance_gain", "importance_weight"])
        writer.writeheader()
        writer.writerows(csv_rows)
    
    print("")
    print(f"CSV report saved to: {csv_path}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
