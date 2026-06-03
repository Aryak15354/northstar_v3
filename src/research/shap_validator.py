"""SHAP/permutation importance utilities for feature validation."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import numpy as np


def compute_feature_importance(
    model,
    X: np.ndarray,
    feature_names: list[str],
    *,
    y: Optional[np.ndarray] = None,
    max_samples: int = 2000,
    output_dir: Optional[str] = None,
) -> Dict[str, object]:
    """
    Compute mean absolute SHAP values (preferred) or permutation importance.

    Returns:
      {
        "method": "shap" | "permutation",
        "importances": {feature: float},
        "plot_path": str | None
      }
    """
    X_arr = np.asarray(X, dtype=float)
    if X_arr.ndim != 2 or X_arr.shape[1] == 0:
        return {"method": "none", "importances": {}, "plot_path": None}

    n = min(int(max_samples), int(X_arr.shape[0]))
    if n <= 0:
        return {"method": "none", "importances": {}, "plot_path": None}
    sample = X_arr[:n]

    try:
        import shap  # type: ignore

        explainer = shap.Explainer(model, sample)
        shap_vals = explainer(sample)
        vals = np.asarray(shap_vals.values, dtype=float)
        if vals.ndim == 3:  # multi-output
            vals = np.mean(np.abs(vals), axis=0)
        importance = np.mean(np.abs(vals), axis=0)
        out = {feature_names[i]: float(importance[i]) for i in range(min(len(feature_names), len(importance)))}

        plot_path = None
        if output_dir:
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            plot_path = str(Path(output_dir) / "shap_summary.png")
            try:
                shap.summary_plot(shap_vals, sample, feature_names=feature_names, show=False)
                import matplotlib.pyplot as plt  # type: ignore

                plt.tight_layout()
                plt.savefig(plot_path, dpi=120)
                plt.close()
            except Exception:
                plot_path = None

        return {"method": "shap", "importances": out, "plot_path": plot_path}
    except Exception:
        pass

    try:
        from sklearn.inspection import permutation_importance

        if y is None:
            return {"method": "none", "importances": {}, "plot_path": None}
        y_arr = np.asarray(y, dtype=float).reshape(-1)
        if len(y_arr) < n:
            return {"method": "none", "importances": {}, "plot_path": None}
        res = permutation_importance(model, sample, y_arr[:n], n_repeats=5, random_state=42)
        imp = np.asarray(res.importances_mean, dtype=float)
        out = {feature_names[i]: float(imp[i]) for i in range(min(len(feature_names), len(imp)))}
        return {"method": "permutation", "importances": out, "plot_path": None}
    except Exception:
        return {"method": "none", "importances": {}, "plot_path": None}
