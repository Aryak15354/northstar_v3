from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable

import numpy as np
import pandas as pd

from src.valuation.families.common import clamp, f


@dataclass
class AggregatorConfig:
    kappa: float = 2.5
    epsilon: float = 1e-8


class BayesianValuationAggregator:
    """
    Precision/confidence/regime/dispersion adjusted valuation combiner.
    """

    GAP_COLS = {
        "core": ("core_gap", "core_variance", "core_confidence"),
        "fcff": ("fcff_gap", "fcff_variance", "fcff_confidence"),
        "fcfe": ("fcfe_gap", "fcfe_variance", "fcfe_confidence"),
        "ddm": ("ddm_gap", "ddm_variance", "ddm_confidence"),
        "apv": ("apv_gap", "apv_variance", "apv_confidence"),
        "residual": ("residual_gap", "residual_variance", "residual_confidence"),
        "transaction": ("transaction_gap", "transaction_variance", "transaction_confidence"),
        "lbo": ("lbo_gap", "lbo_variance", "lbo_confidence"),
        "credit": ("credit_gap", "credit_variance", "credit_confidence"),
        "real_option": ("real_option_gap", "real_option_variance", "real_option_confidence"),
    }

    # Family sensitivity to [low_vol, normal, crisis].
    REGIME_SENSITIVITY = {
        "core": (1.0, 1.0, 0.9),
        "fcff": (1.2, 1.0, 0.6),
        "fcfe": (1.2, 1.0, 0.6),
        "ddm": (1.1, 1.0, 0.7),
        "apv": (1.0, 1.0, 0.8),
        "residual": (0.95, 1.0, 1.1),
        "transaction": (0.9, 1.0, 1.15),
        "lbo": (0.85, 1.0, 1.2),
        "credit": (0.9, 1.0, 1.8),
        "real_option": (1.15, 1.0, 0.9),
    }

    def __init__(self, config: AggregatorConfig | None = None) -> None:
        self.config = config or AggregatorConfig()

    def _infer_regime_probs(self, families_df: pd.DataFrame) -> Dict[str, float]:
        """
        Infer a coarse regime probability vector from cross-sectional risk features.
        """
        stress = pd.to_numeric(families_df.get("credit_stress_score"), errors="coerce")
        default_p = pd.to_numeric(families_df.get("default_probability"), errors="coerce")
        avg_stress = float(np.nanmean(stress)) if stress is not None and stress.notna().any() else 25.0
        avg_default = float(np.nanmean(default_p)) if default_p is not None and default_p.notna().any() else 0.08
        crisis = clamp(0.08 + 0.0075 * avg_stress + 0.8 * avg_default, 0.03, 0.90)
        low_vol = clamp(0.40 - 0.0045 * avg_stress, 0.05, 0.80)
        normal = clamp(1.0 - crisis - low_vol, 0.05, 0.90)
        total = crisis + low_vol + normal
        return {
            "low_vol": low_vol / total,
            "normal": normal / total,
            "crisis": crisis / total,
        }

    def _regime_modifier(self, family: str, regime_probs: Dict[str, float]) -> float:
        sens = self.REGIME_SENSITIVITY.get(family, (1.0, 1.0, 1.0))
        return (
            regime_probs["low_vol"] * sens[0]
            + regime_probs["normal"] * sens[1]
            + regime_probs["crisis"] * sens[2]
        )

    def _iter_family_terms(self, row: pd.Series, regime_probs: Dict[str, float]) -> Iterable[tuple[str, float, float]]:
        for family, (gap_col, var_col, conf_col) in self.GAP_COLS.items():
            gap = f(row.get(gap_col), np.nan)
            if not np.isfinite(gap):
                continue
            gap = clamp(gap, -2.0, 2.0)
            variance = max(self.config.epsilon, f(row.get(var_col), 1.0))
            conf = clamp(f(row.get(conf_col), 0.2), 0.05, 0.99)
            effective_variance = variance / max(conf, self.config.epsilon)
            precision = 1.0 / max(effective_variance, self.config.epsilon)
            precision *= self._regime_modifier(family, regime_probs)
            yield family, gap, precision

    def combine(self, families_df: pd.DataFrame) -> pd.DataFrame:
        regime_probs = self._infer_regime_probs(families_df)
        rows: list[dict[str, float]] = []
        for _, row in families_df.iterrows():
            family_names: list[str] = []
            gaps: list[float] = []
            precisions: list[float] = []
            for family, gap, precision in self._iter_family_terms(row, regime_probs):
                family_names.append(family)
                gaps.append(gap)
                precisions.append(precision)

            if not gaps:
                rows.append(
                    {
                        "ticker": row.get("ticker"),
                        "date": row.get("date"),
                        "posterior_gap": np.nan,
                        "posterior_value": np.nan,
                        "posterior_variance": 1.0,
                        "model_dispersion": np.nan,
                        "agreement_score": 0.0,
                        "regime_modifier": np.nan,
                        "macro_compression": f(row.get("macro_adjustment_factor"), 1.0),
                        "posterior_confidence": 0.1,
                    }
                )
                continue

            g = np.array(gaps, dtype=float)
            tau = np.array(precisions, dtype=float)
            dispersion = float(np.var(g)) if len(g) > 1 else 0.0
            shrink = 1.0 / (1.0 + self.config.kappa * dispersion)
            weighted_gap = float(np.sum(tau * g) / max(np.sum(tau), self.config.epsilon))
            macro_c = clamp(f(row.get("macro_adjustment_factor"), 1.0), 0.60, 1.40)
            posterior_gap = clamp(shrink * weighted_gap * macro_c, -2.0, 2.0)
            posterior_variance = float(1.0 / max(np.sum(tau), self.config.epsilon))
            agreement = float(1.0 / (1.0 + dispersion))
            mean_conf = float(np.mean([clamp(f(row.get(self.GAP_COLS[name][2]), 0.2), 0.05, 0.99) for name in family_names]))
            posterior_confidence = clamp(agreement * mean_conf, 0.05, 0.99)
            ref_value = f(row.get("reference_value"), np.nan)
            posterior_value = np.nan
            if np.isfinite(ref_value) and ref_value > 0:
                posterior_value = ref_value * (1.0 + posterior_gap)
            avg_regime_mod = float(np.mean([self._regime_modifier(name, regime_probs) for name in family_names]))

            rows.append(
                {
                    "ticker": row.get("ticker"),
                    "date": row.get("date"),
                    "posterior_gap": posterior_gap,
                    "posterior_value": posterior_value,
                    "posterior_variance": posterior_variance,
                    "model_dispersion": dispersion,
                    "agreement_score": agreement,
                    "regime_modifier": avg_regime_mod,
                    "macro_compression": macro_c,
                    "posterior_confidence": posterior_confidence,
                }
            )

        out = pd.DataFrame(rows)
        out["regime_low_vol_prob"] = regime_probs["low_vol"]
        out["regime_normal_prob"] = regime_probs["normal"]
        out["regime_crisis_prob"] = regime_probs["crisis"]
        return out

