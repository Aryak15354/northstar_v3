#!/usr/bin/env python3
"""
Macro Impact report generation helpers.

The original implementation drifted out of the live package while the public
package interface and scripts still imported it. This lightweight replacement
restores the active contract used by tests and operational scripts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

import numpy as np
import pandas as pd


class MacroImpactReportGenerator:
    """Generate and persist macro-impact summary artifacts."""

    def __init__(self, output_dir: str | Path = "reports/macro_impact"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_list(values: Any) -> list[Any]:
        if values is None:
            return []
        if isinstance(values, (list, tuple)):
            return list(values)
        if hasattr(values, "tolist"):
            return list(values.tolist())
        return [values]

    def generate_company_fingerprint(
        self,
        ticker: str,
        regression_results: Dict[str, Any],
        top_n: int = 10,
    ) -> Dict[str, Any]:
        """Summarize the most important macro drivers for a company."""
        coefficients = self._safe_list(regression_results.get("coefficients"))
        t_stats = self._safe_list(regression_results.get("t_stats"))
        p_values = self._safe_list(regression_results.get("p_values"))
        fdr_rejected = self._safe_list(regression_results.get("fdr_rejected"))
        column_names = self._safe_list(regression_results.get("column_names"))

        rows: List[Dict[str, Any]] = []
        for idx, column_name in enumerate(column_names):
            if str(column_name).lower() == "intercept":
                continue
            rows.append(
                {
                    "driver": str(column_name),
                    "coefficient": float(coefficients[idx]) if idx < len(coefficients) else 0.0,
                    "t_stat": float(t_stats[idx]) if idx < len(t_stats) else 0.0,
                    "p_value": float(p_values[idx]) if idx < len(p_values) else 1.0,
                    "significant": bool(fdr_rejected[idx]) if idx < len(fdr_rejected) else False,
                }
            )

        top_drivers = sorted(
            rows,
            key=lambda item: (
                not bool(item["significant"]),
                float(item["p_value"]),
                -abs(float(item["coefficient"])),
            ),
        )[: max(1, int(top_n))]

        return {
            "ticker": str(ticker),
            "success": bool(regression_results.get("success", True)),
            "n_obs": int(regression_results.get("n_obs", 0) or 0),
            "r_squared": float(regression_results.get("r_squared", 0.0) or 0.0),
            "adj_r_squared": float(regression_results.get("adj_r_squared", 0.0) or 0.0),
            "top_drivers": top_drivers,
        }

    def generate_sector_report(
        self,
        sector: str,
        sector_betas: pd.DataFrame,
        top_n: int = 10,
    ) -> Dict[str, Any]:
        """Aggregate sector-level macro sensitivity."""
        if sector_betas is None or sector_betas.empty:
            return {"sector": str(sector), "top_macro_sensitivities": []}

        df = sector_betas.copy()
        macro_col = "macro_variable" if "macro_variable" in df.columns else None
        beta_col = "beta" if "beta" in df.columns else None
        if macro_col is None or beta_col is None:
            return {"sector": str(sector), "top_macro_sensitivities": []}

        grouped = (
            df.groupby(macro_col, dropna=False)[beta_col]
            .mean()
            .sort_values(key=lambda s: s.abs(), ascending=False)
            .head(max(1, int(top_n)))
        )
        return {
            "sector": str(sector),
            "top_macro_sensitivities": [
                {"macro_variable": str(idx), "average_beta": float(val)}
                for idx, val in grouped.items()
            ],
        }

    def save_report(self, payload: Dict[str, Any], filename: str) -> Path:
        path = self.output_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, default=str)
        return path

    def save_dataframe(self, df: pd.DataFrame, filename: str) -> Path:
        path = self.output_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix.lower() == ".parquet":
            df.to_parquet(path, index=False)
        else:
            df.to_csv(path, index=False)
        return path
