"""Signal-factory primitives: family mapping, aggregation, and blending."""

from .family_registry import build_feature_family_map, infer_family
from .family_aggregator import apply_family_feature_weights, build_family_factor_table
from .alpha_combiner import (
    compute_live_monitoring_metrics,
    estimate_stacked_ic,
    optimize_family_blend,
    simulate_signal_stacking,
)

__all__ = [
    "infer_family",
    "build_feature_family_map",
    "build_family_factor_table",
    "apply_family_feature_weights",
    "optimize_family_blend",
    "estimate_stacked_ic",
    "simulate_signal_stacking",
    "compute_live_monitoring_metrics",
]
