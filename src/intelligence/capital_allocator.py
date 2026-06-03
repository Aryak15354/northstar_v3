#!/usr/bin/env python3
"""
🧠 CAPITAL ALLOCATOR - BAYESIAN MODEL ALLOCATION ENGINE
Institutional-Grade Capital Allocation with Regret Minimization

This is the brain that decides which strategies get money today.
Uses Thompson Sampling and Bayesian updating to allocate capital
across competing strategies based on their skill and regime fit.

This is how Bridgewater, Citadel, and Two Sigma actually operate:
They don't pick stocks. They allocate capital to models.

Usage:
    try:
    from intelligence.capital_allocator import CapitalAllocator
except ImportError:
    from CapitalAllocator import CapitalAllocator
    
    allocator = CapitalAllocator()
    allocations = allocator.allocate_capital()
"""

import pandas as pd
import numpy as np
import os
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from scipy.stats import beta
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src.intelligence.strategy_surface_policy import (
        is_archived_strategy,
        is_feature_only_strategy,
        is_standalone_strategy,
        overlay_config,
        strategy_family_override,
        strategy_max_allocation,
        strategy_overlay_parent,
        strategy_overlay_weight,
        strategy_role,
        strategy_surface_mode,
    )
except Exception:
    from intelligence.strategy_surface_policy import (  # type: ignore
        is_archived_strategy,
        is_feature_only_strategy,
        is_standalone_strategy,
        overlay_config,
        strategy_family_override,
        strategy_max_allocation,
        strategy_overlay_parent,
        strategy_overlay_weight,
        strategy_role,
        strategy_surface_mode,
    )

class CapitalAllocator:
    """
    Bayesian Capital Allocation Engine with Regret Minimization
    
    This system decides how to split capital across strategies using:
    1. Bayesian skill estimation (Thompson Sampling)
    2. Regime awareness
    3. Regret tracking
    4. Risk management overlays
    """
    
    def __init__(self):
        self.name = "Northstar Capital Allocator"
        self.version = "3.0"
        
        # File paths
        self.paths = {
            'strategy_performance': 'data/processed/strategy_performance',
            'backtests': 'data/processed/backtests',
            'market_state': 'data/processed/market_state.parquet',
            'strategy_beliefs': 'data/processed/strategy_beliefs.parquet',
            'strategy_regret': 'data/processed/strategy_regret.parquet',
            'capital_allocations': 'data/processed/capital_allocations.json',
            'allocation_history': 'data/processed/allocation_history.parquet',
            'edge_half_life': 'data/processed/edge_half_life.json',
            'model_freeze_state': 'data/processed/model_freeze_state.json',
            'parameter_version': 'data/processed/parameter_version.json',
            'feature_overlays': 'data/processed/strategy_feature_overlays.json',
            'unified_state': 'data/state/unified_state.json',
        }
        
        # Allocation parameters
        self.params = {
            'min_allocation': 0.05,    # 5% minimum per strategy
            'max_allocation': 0.50,    # 50% maximum per strategy
            'temperature': 0.75,       # Softmax temperature (lower = more concentrated)
            'confidence_threshold': 0.4,  # Minimum skill probability
            'regret_penalty': 0.3,     # Regret penalty weight
            'lookback_days': 90,       # Days to consider for allocation
            'min_trades': 10,          # Minimum trades for skill estimation
            'kill_switch_dd': 0.20,    # 20% drawdown kills strategy
            'kill_switch_regret': 0.70,  # Top 70% regret kills strategy
            'edge_decay_alpha': 2.0,
            # High-conviction gates (pre-allocation filtering)
            'min_alive_score': 0.05,
            'min_alive_skill_prob': 0.52,
            'min_alive_confidence': 0.20,
            'min_alive_tailwind': 0.85,
            'max_live_strategies': 8,
            'fabric_multiplier_strength': 0.35,
            # Allocator hardening parameters
            'risk_lookback_days': 60,
            'covariance_shrinkage': 0.35,
            'covariance_eigen_floor': 1e-6,
            'optimizer_risk_aversion': 3.5,
            'allocation_turnover_cap': 0.20,  # one-way allocation turnover cap
            'transaction_cost_bps': 10.0,
            'freeze_max_exposure': 0.15,
        }
        self.last_optimizer_diagnostics = {}
        self._latest_feature_overlays = {}
        
        # Regime boosts
        self.regime_boosts = {
            'crisis': {
                'low_vol': 1.5, 'quality_tilt': 1.3, 'value_tilt': 1.2,
                'mom_6m': 0.7, 'mom_12m': 0.7, 'dual_momentum': 0.8
            },
            'boom': {
                'mom_6m': 1.4, 'mom_12m': 1.3, 'dual_momentum': 1.2,
                'low_vol': 0.8, 'quality_tilt': 0.9
            },
            'expansion': {
                'mom_6m': 1.2, 'quality_tilt': 1.1, 'northstar': 1.1,
                'value_tilt': 0.9
            },
            'late-expansion': {
                'quality_tilt': 1.2, 'low_vol': 1.1, 'northstar': 1.0,
                'mom_6m': 0.9, 'value_tilt': 1.1
            },
            'slowdown': {
                'value_tilt': 1.3, 'quality_tilt': 1.2, 'low_vol': 1.1,
                'mom_6m': 0.8, 'mom_12m': 0.8
            },
            'tightening': {
                'low_vol': 1.4, 'value_tilt': 1.3, 'quality_tilt': 1.2,
                'mom_6m': 0.7, 'dual_momentum': 0.8
            }
        }
        self.family_regime_boosts = {
            'crisis': {'sentiment': 0.90, 'alternative': 0.92, 'ownership': 0.95},
            'boom': {'sentiment': 1.10, 'alternative': 1.12, 'ownership': 1.05},
            'expansion': {'sentiment': 1.12, 'alternative': 1.08, 'ownership': 1.08},
            'late-expansion': {'sentiment': 1.02, 'alternative': 1.10, 'ownership': 1.12},
            'slowdown': {'sentiment': 0.96, 'alternative': 1.05, 'ownership': 1.08},
            'tightening': {'sentiment': 0.94, 'alternative': 1.00, 'ownership': 1.06},
        }

    def load_weekly_fabric_insights(self):
        """Load weekly causal-fabric insights for allocation-time conditioning."""
        try:
            try:
                from src.intelligence.market_brain.weekly_fabric_reader import WeeklyFabricReader
            except Exception:
                from intelligence.market_brain.weekly_fabric_reader import WeeklyFabricReader
            reader = WeeklyFabricReader()
            insights = reader.get_capital_allocation_insights() or {}
            multipliers = insights.get('strategy_fitness_multipliers', {}) or {}
            print(f"🧬 Weekly fabric insights loaded: {len(multipliers)} multipliers")
            return insights
        except Exception as e:
            print(f"   ⚠️ Weekly fabric insights unavailable: {e}")
            return {}

    @staticmethod
    def _strategy_fabric_tags(strategy_name: str):
        s = str(strategy_name or "").lower()
        tags = set()
        if any(k in s for k in ['mom', 'momentum', 'growth', 'trend', 'northstar']):
            tags.add('growth_strategies')
            tags.add('cyclicals')
        if any(k in s for k in ['quality', 'low_vol', 'defensive']):
            tags.add('defensive_strategies')
            tags.add('quality_defensives')
        if any(k in s for k in ['value', 'contrarian']):
            tags.add('quality_defensives')
            tags.add('credit_sensitive')
        if any(k in s for k in ['export']):
            tags.add('export_focused')
        if any(k in s for k in ['import']):
            tags.add('import_dependent')
        return tags

    def apply_weekly_fabric_conditioning(self, health_scores, fabric_insights):
        """
        Condition health scores with weekly causal-fabric multipliers.
        This wires anticipatory relationships into the allocator directly.
        """
        if not health_scores:
            return health_scores

        multipliers = (fabric_insights or {}).get('strategy_fitness_multipliers', {}) or {}
        if not multipliers:
            return health_scores

        strength = float(self.params.get('fabric_multiplier_strength', 0.35))
        for strategy, metrics in health_scores.items():
            tags = self._strategy_fabric_tags(strategy)
            if not tags:
                metrics['fabric_multiplier'] = 1.0
                continue

            vals = [float(multipliers.get(tag, 1.0) or 1.0) for tag in tags]
            if not vals:
                metrics['fabric_multiplier'] = 1.0
                continue

            raw_mult = float(np.mean(vals))
            effective_mult = float(np.clip(1.0 + strength * (raw_mult - 1.0), 0.80, 1.20))
            metrics['health_score'] = float(metrics.get('health_score', 0.0)) * effective_mult
            metrics['fabric_multiplier'] = effective_mult

        return health_scores

    @staticmethod
    def _iter_open_option_positions(payload):
        if isinstance(payload, dict):
            positions = payload.get('open_positions', {})
            if isinstance(positions, dict):
                return [dict(pos or {}) for pos in positions.values()]
            if isinstance(positions, list):
                return [dict(pos or {}) for pos in positions]
        return []

    def _get_options_notional_deployed(self) -> float:
        """Read current options notional to prevent double-counting capital."""
        path = PROJECT_ROOT / "data/options/live/options_runtime_state.json"
        if not path.exists():
            return 0.0
        try:
            payload = json.loads(path.read_text())
            total = 0.0
            for position in self._iter_open_option_positions(payload):
                for key in ("notional", "max_loss", "current_value", "entry_credit_debit"):
                    value = pd.to_numeric(position.get(key), errors='coerce')
                    if pd.notna(value):
                        total += float(abs(value))
                        break
            return float(total)
        except Exception as e:
            print(f"   ⚠️ Could not read options notional: {e}")
            return 0.0

    @staticmethod
    def _tailwind_multiplier(raw_score):
        """Map legacy or alpha-OS tailwind scales into a neutral-around-1 multiplier."""
        try:
            score = float(raw_score)
        except Exception:
            return 1.0
        if not np.isfinite(score):
            return 1.0
        if -0.50 <= score <= 0.50:
            score = 1.0 + score
        return float(np.clip(score, 0.70, 1.50))

    @staticmethod
    def _safe_float(value, default=0.0):
        try:
            parsed = float(value)
        except Exception:
            return float(default)
        if not np.isfinite(parsed):
            return float(default)
        return float(parsed)

    @staticmethod
    def _tailwind_family_for_strategy(strategy_name: str) -> str:
        override = strategy_family_override(strategy_name)
        if override:
            return override
        s = str(strategy_name or "").strip().lower()
        if any(token in s for token in ["ownership", "shareholding", "promoter"]):
            return "ownership"
        if any(token in s for token in ["sentiment", "news"]):
            return "sentiment"
        if any(token in s for token in ["alternative", "ownership", "shareholding", "pledge", "bulk", "announcement"]):
            return "alternative"
        if any(token in s for token in ["mom", "momentum", "northstar", "sector_tilt", "dual_"]):
            return "momentum"
        if any(token in s for token in ["quality"]):
            return "quality"
        if any(token in s for token in ["value"]):
            return "value"
        if any(token in s for token in ["low_vol", "risk_parity", "sector_neutral", "defensive"]):
            return "defensive"
        return "composite"

    def _feature_overlay_signal(self, metrics):
        sharpe = self._safe_float(metrics.get('sharpe', 0.0), 0.0)
        ann_return = self._safe_float(metrics.get('ann_return', 0.0), 0.0)
        total_return = self._safe_float(metrics.get('total_return', 0.0), 0.0)
        signal = (
            0.55 * np.tanh(sharpe / 3.0) +
            0.30 * np.tanh(ann_return / 0.20) +
            0.15 * np.tanh(total_return / 0.20)
        )
        cap = self._safe_float(overlay_config().get('signal_cap', 1.0), 1.0)
        cap = max(0.1, cap)
        return float(np.clip(signal, -cap, cap))

    def _build_feature_overlays(self, feature_metrics):
        cfg = overlay_config()
        max_impact = self._safe_float(cfg.get('max_abs_score_impact', 0.12), 0.12)
        by_parent = {}

        for strategy, metrics in feature_metrics.items():
            parent = strategy_overlay_parent(strategy)
            weight = strategy_overlay_weight(strategy)
            signal = self._feature_overlay_signal(metrics)
            by_parent.setdefault(parent, []).append({
                'strategy': strategy,
                'weight': weight,
                'signal': signal,
                'family': self._tailwind_family_for_strategy(strategy),
                'sharpe': self._safe_float(metrics.get('sharpe', 0.0), 0.0),
                'ann_return': self._safe_float(metrics.get('ann_return', 0.0), 0.0),
                'total_return': self._safe_float(metrics.get('total_return', 0.0), 0.0),
                'observations': int(self._safe_float(metrics.get('n_observations', 0), 0)),
            })

        payload = {}
        for parent, rows in by_parent.items():
            total_weight = sum(max(0.0, self._safe_float(row.get('weight', 0.0), 0.0)) for row in rows)
            if total_weight <= 0:
                continue
            raw_signal = sum(
                self._safe_float(row.get('weight', 0.0), 0.0) * self._safe_float(row.get('signal', 0.0), 0.0)
                for row in rows
            ) / total_weight
            overlay_score = float(np.clip(raw_signal * max_impact, -max_impact, max_impact))
            positive_share = sum(
                self._safe_float(row.get('weight', 0.0), 0.0)
                for row in rows
                if self._safe_float(row.get('signal', 0.0), 0.0) > 0.0
            ) / total_weight
            payload[parent] = {
                'parent_strategy': parent,
                'component_count': len(rows),
                'raw_signal': float(raw_signal),
                'overlay_score': overlay_score,
                'positive_share': float(np.clip(positive_share, 0.0, 1.0)),
                'components': rows,
            }
        return payload

    def _load_saved_feature_overlays(self):
        path = self.paths.get('feature_overlays')
        if not path or not os.path.exists(path):
            return {}
        try:
            with open(path, 'r') as f:
                payload = json.load(f)
            overlays = payload.get('overlays', payload)
            return overlays if isinstance(overlays, dict) else {}
        except Exception:
            return {}

    def _apply_policy_caps(self, allocations, exposure_cap):
        if not allocations:
            return allocations

        adjusted = {str(k): float(v) for k, v in allocations.items()}
        headroom = 0.0
        capped = set()

        for strategy, weight in list(adjusted.items()):
            max_share = strategy_max_allocation(strategy)
            if max_share is None:
                continue
            cap_value = float(exposure_cap) * float(max_share)
            if weight > cap_value:
                headroom += weight - cap_value
                adjusted[strategy] = cap_value
                capped.add(strategy)

        if headroom <= 1e-12:
            return adjusted

        recipients = {
            strategy: weight for strategy, weight in adjusted.items()
            if strategy not in capped and weight > 0.0
        }
        if not recipients:
            return adjusted

        recipient_total = sum(recipients.values())
        if recipient_total <= 1e-12:
            return adjusted

        for strategy, weight in recipients.items():
            max_share = strategy_max_allocation(strategy, default=1.0)
            cap_value = float(exposure_cap) * float(max_share if max_share is not None else 1.0)
            increment = headroom * (weight / recipient_total)
            adjusted[strategy] = min(cap_value, adjusted[strategy] + increment)

        total = sum(adjusted.values())
        if total > exposure_cap and total > 1e-12:
            scale = exposure_cap / total
            adjusted = {k: float(v * scale) for k, v in adjusted.items()}

        return adjusted

    def _regime_boost_for_strategy(self, strategy_name: str, current_regime: str) -> float:
        regime_key = str(current_regime or "").strip().lower()
        exact = self.regime_boosts.get(regime_key, {}).get(strategy_name)
        if exact is not None:
            return float(exact)
        family = self._tailwind_family_for_strategy(strategy_name)
        return float(self.family_regime_boosts.get(regime_key, {}).get(family, 1.0))

    def _normalize_tailwind_frame(self, tailwind_df: pd.DataFrame) -> dict[str, dict]:
        """Normalize heterogeneous tailwind schemas into allocator-ready records."""
        if tailwind_df is None or tailwind_df.empty:
            return {}

        df = tailwind_df.copy()
        normalized: dict[str, dict] = {}

        def _safe_float(value, default=0.0):
            parsed = pd.to_numeric(value, errors="coerce")
            return float(default if pd.isna(parsed) else parsed)

        if {"strategy", "combined_score"}.issubset(df.columns):
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                latest = df.sort_values("date").groupby("strategy", dropna=False).tail(1)
            else:
                latest = df.groupby("strategy", dropna=False).tail(1)
            for _, row in latest.iterrows():
                strategy = str(row.get("strategy", "") or "").strip()
                if not strategy:
                    continue
                combined_score = self._tailwind_multiplier(row.get("combined_score", 1.0))
                regime_tailwind = self._tailwind_multiplier(row.get("regime_tailwind", combined_score))
                normalized[strategy] = {
                    "combined_score": combined_score,
                    "sharpe": _safe_float(row.get("sharpe", 0.0), 0.0),
                    "regime_tailwind": regime_tailwind,
                    "regime": row.get("regime"),
                }
            if normalized:
                return normalized

        if {"strategy_id", "tailwind_score"}.issubset(df.columns):
            as_of_col = next((c for c in ["as_of_date", "timestamp", "date"] if c in df.columns), None)
            if as_of_col:
                df[as_of_col] = pd.to_datetime(df[as_of_col], errors="coerce")
                latest = df.sort_values(as_of_col).groupby("strategy_id", dropna=False).tail(1)
            else:
                latest = df.groupby("strategy_id", dropna=False).tail(1)
            for _, row in latest.iterrows():
                strategy = str(row.get("strategy_id", "") or "").strip()
                if not strategy:
                    continue
                combined_score = self._tailwind_multiplier(row.get("tailwind_score", 1.0))
                record = {
                    "combined_score": combined_score,
                    "sharpe": _safe_float(row.get("tailwind_score", 0.0), 0.0),
                    "regime_tailwind": combined_score,
                    "regime": row.get("regime"),
                }
                normalized[strategy] = record
                family = str(row.get("strategy_family", "") or "").strip().lower()
                if family:
                    normalized.setdefault(f"__family__:{family}", record)
                if family == "composite" or strategy.startswith("strategy_recommendations_"):
                    normalized.setdefault("__default__", record)
            if normalized:
                return normalized

        if {"strategy_family", "tailwind_score"}.issubset(df.columns):
            as_of_col = next((c for c in ["as_of_date", "timestamp", "date"] if c in df.columns), None)
            if as_of_col:
                df[as_of_col] = pd.to_datetime(df[as_of_col], errors="coerce")
                latest = df.sort_values(as_of_col).groupby("strategy_family", dropna=False).tail(1)
            else:
                latest = df.groupby("strategy_family", dropna=False).tail(1)

            default_record = None
            for _, row in latest.iterrows():
                family = str(row.get("strategy_family", "") or "").strip().lower() or "composite"
                multiplier = self._tailwind_multiplier(row.get("tailwind_score", 0.0))
                record = {
                    "combined_score": multiplier,
                    "sharpe": _safe_float(row.get("sharpe", 0.0), 0.0),
                    "regime_tailwind": multiplier,
                    "regime": row.get("regime"),
                }
                normalized[f"__family__:{family}"] = record
                if family == "composite" or default_record is None:
                    default_record = record

            if default_record is not None:
                normalized["__default__"] = default_record

        return normalized

    def _resolve_tailwind_for_strategy(self, strategy_name: str, tailwinds: dict[str, dict] | None) -> dict:
        if not isinstance(tailwinds, dict) or not tailwinds:
            return {}
        if strategy_name in tailwinds:
            return tailwinds[strategy_name]
        family_key = f"__family__:{self._tailwind_family_for_strategy(strategy_name)}"
        if family_key in tailwinds:
            return tailwinds[family_key]
        return tailwinds.get("__default__", {})

    def load_model_freeze_state(self):
        """Load automatic freeze-state controls from institutional hardening layer."""
        path = self.paths.get('model_freeze_state')
        if not path or not os.path.exists(path):
            return {'freeze_active': False, 'actions': {}}
        try:
            with open(path, 'r') as f:
                payload = json.load(f)
            if not isinstance(payload, dict):
                return {'freeze_active': False, 'actions': {}}
            payload.setdefault('freeze_active', False)
            payload.setdefault('actions', {})
            return payload
        except Exception as e:
            print(f"   ⚠️ Could not load model freeze state: {e}")
            return {'freeze_active': False, 'actions': {}}

    def _load_previous_allocations(self):
        """Load previous strategy allocations for turnover control."""
        try:
            if os.path.exists(self.paths['capital_allocations']):
                with open(self.paths['capital_allocations'], 'r') as f:
                    payload = json.load(f)
                allocs = payload.get('allocations', {})
                if isinstance(allocs, dict):
                    out = {}
                    for k, v in allocs.items():
                        x = float(v)
                        if np.isfinite(x):
                            out[str(k)] = max(0.0, x)
                    return out
        except Exception:
            pass
        return {}

    def _build_strategy_return_matrix(self, strategy_data, strategies):
        """
        Build aligned strategy return matrix for covariance estimation.
        Returns shape: [lookback, n_strategies].
        """
        series = {}
        min_len = None
        lookback = max(20, int(self.params.get('risk_lookback_days', 60)))

        for strategy in strategies:
            raw = strategy_data.get(strategy, {}).get('recent_returns', []) or []
            if len(raw) < 20:
                continue
            s = pd.to_numeric(pd.Series(raw), errors='coerce').dropna()
            if len(s) < 20:
                continue
            arr = s.values.astype(float)
            if np.all(~np.isfinite(arr)):
                continue
            arr = arr[np.isfinite(arr)]
            if len(arr) < 20:
                continue
            series[strategy] = arr
            min_len = len(arr) if min_len is None else min(min_len, len(arr))

        if not series or min_len is None or min_len < 20:
            return pd.DataFrame()

        n = min(min_len, lookback)
        aligned = {k: v[-n:] for k, v in series.items()}
        mat = pd.DataFrame(aligned)
        mat = mat.replace([np.inf, -np.inf], np.nan).dropna(axis=0, how='any')
        if mat.shape[0] < 20:
            return pd.DataFrame()
        return mat

    def _estimate_shrunk_covariance(self, returns_df):
        """Estimate a numerically stable covariance matrix with diagonal shrinkage."""
        if returns_df.empty:
            return np.array([[]], dtype=float), np.array([], dtype=float), np.inf

        cov = returns_df.cov().values.astype(float)
        cov = np.nan_to_num(cov, nan=0.0, posinf=0.0, neginf=0.0)
        diag = np.diag(np.diag(cov))
        shrink = float(np.clip(self.params.get('covariance_shrinkage', 0.35), 0.0, 1.0))
        shrunk = (1.0 - shrink) * cov + shrink * diag

        # Eigenvalue clipping protects inversion from near-singularity.
        floor = float(max(1e-10, self.params.get('covariance_eigen_floor', 1e-6)))
        try:
            eigvals, eigvecs = np.linalg.eigh(shrunk)
            eigvals = np.clip(eigvals, floor, None)
            shrunk = eigvecs @ np.diag(eigvals) @ eigvecs.T
            shrunk = 0.5 * (shrunk + shrunk.T)
            cond = float(np.linalg.cond(shrunk))
        except Exception:
            n = shrunk.shape[0]
            shrunk = np.eye(n) * floor
            eigvals = np.full(n, floor, dtype=float)
            cond = np.inf
        return shrunk, eigvals, cond

    def _risk_normalized_optimizer(
        self,
        alive_strategies,
        health_scores,
        strategy_data,
        exposure_cap,
        previous_allocations,
        freeze_state,
    ):
        """
        Allocate via risk-normalized mean-variance proxy:
        w ~ inv(Sigma) * (mu / sigma), long-only with turnover cap.
        """
        if not alive_strategies:
            return {}

        strat_list = list(alive_strategies.keys())
        ret_mat = self._build_strategy_return_matrix(strategy_data, strat_list)

        if ret_mat.empty or ret_mat.shape[1] < 1:
            return {}

        used = [c for c in ret_mat.columns if c in alive_strategies]
        ret_mat = ret_mat[used]
        if ret_mat.empty:
            return {}

        cov, eigvals, cond = self._estimate_shrunk_covariance(ret_mat)
        vols = np.sqrt(np.clip(np.diag(cov), 1e-12, None))

        mu_raw = []
        avg_turnover = []
        for s in used:
            h = health_scores.get(s, {})
            base_alpha = float(
                h.get('health_score', 0.0) *
                h.get('skill_prob', 0.5) *
                max(0.5, h.get('tailwind_score', 1.0))
            )
            tc_penalty = float(self.params.get('transaction_cost_bps', 10.0)) / 10000.0
            strat_turnover = float(strategy_data.get(s, {}).get('avg_turnover', 0.0) or 0.0)
            mu_raw.append(base_alpha - tc_penalty * strat_turnover)
            avg_turnover.append(strat_turnover)
        mu_raw = np.asarray(mu_raw, dtype=float)
        mu_raw = np.nan_to_num(mu_raw, nan=0.0, posinf=0.0, neginf=0.0)
        mu_rn = mu_raw / np.clip(vols, 1e-8, None)
        mu_rn = np.nan_to_num(mu_rn, nan=0.0, posinf=0.0, neginf=0.0)

        freeze_actions = (freeze_state or {}).get('actions', {}) if isinstance(freeze_state, dict) else {}
        risk_mult = float(freeze_actions.get('risk_aversion_multiplier', 1.0) or 1.0)
        risk_aversion = float(max(1e-6, self.params.get('optimizer_risk_aversion', 3.5) * risk_mult))

        try:
            # Mean-variance first-order condition (unconstrained), then long-only projection.
            precision = np.linalg.pinv(cov + np.eye(cov.shape[0]) * (1.0 / risk_aversion))
            raw = precision @ mu_rn
        except Exception:
            raw = mu_rn.copy()

        raw = np.clip(raw, 0.0, None)
        if raw.sum() <= 1e-12:
            raw = np.clip(mu_rn, 0.0, None)
        if raw.sum() <= 1e-12:
            raw = np.ones_like(raw)

        w = raw / np.clip(raw.sum(), 1e-12, None)

        # Hard max allocation per strategy.
        w = np.minimum(w, float(self.params.get('max_allocation', 0.50)))
        if w.sum() <= 1e-12:
            w = np.ones_like(w) / len(w)
        else:
            w = w / w.sum()

        target = {s: float(w[i] * exposure_cap) for i, s in enumerate(used)}

        # Turnover governance: limit one-way reallocation each cycle.
        all_keys = sorted(set(target.keys()) | set(previous_allocations.keys()))
        prev_vec = np.array([float(previous_allocations.get(k, 0.0)) for k in all_keys], dtype=float)
        new_vec = np.array([float(target.get(k, 0.0)) for k in all_keys], dtype=float)
        turnover = 0.5 * float(np.abs(new_vec - prev_vec).sum())
        turnover_cap = float(max(0.01, self.params.get('allocation_turnover_cap', 0.20)))
        if turnover > turnover_cap and turnover > 1e-12:
            blend = turnover_cap / turnover
            adj_vec = prev_vec + blend * (new_vec - prev_vec)
            new_vec = np.clip(adj_vec, 0.0, None)
            ssum = float(new_vec.sum())
            if ssum > 1e-12:
                new_vec = new_vec / ssum * exposure_cap
            target = {k: float(v) for k, v in zip(all_keys, new_vec) if v > 1e-8}

        self.last_optimizer_diagnostics = {
            'method': 'risk_normalized_mean_variance',
            'n_strategies': int(len(used)),
            'lookback_rows': int(ret_mat.shape[0]),
            'covariance_condition_number': float(cond),
            'covariance_shrinkage': float(self.params.get('covariance_shrinkage', 0.35)),
            'covariance_min_eigenvalue': float(np.min(eigvals)) if len(eigvals) else None,
            'risk_aversion': risk_aversion,
            'estimated_turnover': turnover,
            'turnover_cap': turnover_cap,
            'avg_strategy_turnover': float(np.mean(avg_turnover)) if avg_turnover else 0.0,
        }
        return target

    def _compute_strategy_metrics(self, frame, *, include_returns=False):
        """Compute stable strategy metrics from a backtest frame."""
        if frame is None or len(frame) <= 1:
            return {}
        if "daily_return" not in frame.columns or "equity" not in frame.columns:
            return {}

        work = frame.copy()
        returns = pd.to_numeric(work["daily_return"], errors="coerce")
        equity = pd.to_numeric(work["equity"], errors="coerce")
        valid = returns.notna() & equity.notna()
        work = work.loc[valid].copy()
        returns = returns.loc[valid]
        equity = equity.loc[valid]
        if len(work) <= 1:
            return {}

        total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
        ann_return = float((equity.iloc[-1] / equity.iloc[0]) ** (252 / len(work)) - 1.0)
        volatility = float(returns.std() * np.sqrt(252))
        sharpe = float(ann_return / volatility) if volatility > 0 else 0.0
        out = {
            "total_return": total_return,
            "ann_return": ann_return,
            "volatility": volatility,
            "sharpe": sharpe,
            "max_drawdown": float(pd.to_numeric(work.get("drawdown"), errors="coerce").min()),
            "win_rate": float((returns > 0).mean()),
            "avg_exposure": float(pd.to_numeric(work.get("exposure"), errors="coerce").mean()),
            "avg_turnover": float(pd.to_numeric(work.get("turnover"), errors="coerce").mean()),
            "n_observations": int(len(work)),
            "last_equity": float(equity.iloc[-1]),
        }
        if include_returns:
            out["recent_returns"] = returns.tolist()
        return out
    
    def load_strategy_performance(self):
        """Load recent strategy performance data"""
        
        print("📊 Loading strategy performance data...")
        
        strategy_data = {}
        feature_metrics = {}
        
        # Load backtest results
        if os.path.exists(self.paths['backtests']):
            for file in os.listdir(self.paths['backtests']):
                if file.endswith('.parquet'):
                    strategy_name = file.replace('.parquet', '')
                    if is_archived_strategy(strategy_name):
                        continue
                    try:
                        df = pd.read_parquet(os.path.join(self.paths['backtests'], file))
                        if not df.empty:
                            recent_df = df.tail(self.params['lookback_days'])
                            recent_metrics = self._compute_strategy_metrics(recent_df, include_returns=True)
                            if recent_metrics:
                                full_metrics = self._compute_strategy_metrics(df, include_returns=False)
                                payload = dict(recent_metrics)
                                for key, value in full_metrics.items():
                                    payload[f'full_{key}'] = value
                                payload['n_full_observations'] = int(len(df))
                                if is_feature_only_strategy(strategy_name):
                                    feature_metrics[strategy_name] = payload
                                else:
                                    strategy_data[strategy_name] = payload
                    except Exception as e:
                        print(f"   ⚠️ Error loading {strategy_name}: {e}")

        self._latest_feature_overlays = self._build_feature_overlays(feature_metrics)
        print(f"   ✅ Loaded performance for {len(strategy_data)} standalone strategies")
        if feature_metrics:
            print(f"   🔗 Folded {len(feature_metrics)} legacy sleeves into capped core overlays")
        return strategy_data
    
    def load_market_regime(self):
        """Load current market regime"""
        
        try:
            if os.path.exists(self.paths['market_state']):
                market_df = pd.read_parquet(self.paths['market_state'])
                if not market_df.empty:
                    latest = market_df.iloc[-1]
                    regime = latest.get('macro_regime', 'neutral')
                    vol_regime = latest.get('vol_regime', 'mid')
                    liquidity_regime = latest.get('liquidity_regime', 'neutral')
                    risk_on_prob = latest.get('risk_on_probability', 0.5)
                    
                    print(f"   📊 Current regime: {regime} (risk-on: {risk_on_prob:.1%})")
                    
                    return {
                        'macro_regime': regime,
                        'vol_regime': vol_regime,
                        'liquidity_regime': liquidity_regime,
                        'risk_on_prob': risk_on_prob
                    }
        except Exception as e:
            print(f"   ⚠️ Could not load market regime: {e}")
        
        return {
            'macro_regime': 'neutral',
            'vol_regime': 'mid',
            'liquidity_regime': 'neutral',
            'risk_on_prob': 0.5
        }
    
    def load_strategy_beliefs(self):
        """Load strategy beliefs from the beliefs engine"""
        
        print("🧠 Loading strategy beliefs...")
        
        beliefs = {}
        beliefs_file = 'data/processed/strategy_beliefs.parquet'
        
        if os.path.exists(beliefs_file):
            try:
                beliefs_df = pd.read_parquet(beliefs_file)
                if beliefs_df.empty:
                    return beliefs

                # Backward compatibility: legacy beliefs files used `timestamp`
                # and sometimes only [strategy, belief_strength].
                if 'date' not in beliefs_df.columns:
                    if 'timestamp' in beliefs_df.columns:
                        beliefs_df['date'] = pd.to_datetime(beliefs_df['timestamp'], errors='coerce')
                    else:
                        beliefs_df['date'] = pd.Timestamp.utcnow()
                beliefs_df['date'] = pd.to_datetime(beliefs_df['date'], errors='coerce').fillna(pd.Timestamp.utcnow())

                if 'strategy' not in beliefs_df.columns:
                    return beliefs

                if 'skill_prob' not in beliefs_df.columns and 'belief_strength' in beliefs_df.columns:
                    beliefs_df['skill_prob'] = pd.to_numeric(beliefs_df['belief_strength'], errors='coerce')

                # Ensure canonical numeric fields exist
                beliefs_df['skill_prob'] = pd.to_numeric(
                    beliefs_df.get('skill_prob', 0.5), errors='coerce'
                ).fillna(0.5).clip(0.01, 0.99)
                beliefs_df['confidence'] = pd.to_numeric(
                    beliefs_df.get('confidence', 0.5), errors='coerce'
                ).fillna(0.5).clip(0.01, 1.0)
                beliefs_df['effective_skill'] = pd.to_numeric(
                    beliefs_df.get('effective_skill', beliefs_df['skill_prob']), errors='coerce'
                ).fillna(beliefs_df['skill_prob'])
                beliefs_df['regime_fit'] = pd.to_numeric(
                    beliefs_df.get('regime_fit', 1.0), errors='coerce'
                ).fillna(1.0)
                beliefs_df['sharpe'] = pd.to_numeric(
                    beliefs_df.get('sharpe', 0.0), errors='coerce'
                ).fillna(0.0)
                beliefs_df['alpha'] = pd.to_numeric(
                    beliefs_df.get('alpha', beliefs_df['skill_prob'] * 20.0), errors='coerce'
                ).fillna(beliefs_df['skill_prob'] * 20.0)
                beliefs_df['beta'] = pd.to_numeric(
                    beliefs_df.get('beta', (1.0 - beliefs_df['skill_prob']) * 20.0), errors='coerce'
                ).fillna((1.0 - beliefs_df['skill_prob']) * 20.0)
                beliefs_df['status'] = beliefs_df.get('status', np.where(beliefs_df['skill_prob'] >= 0.45, 'ACTIVE', 'FADING'))
                beliefs_df['status'] = beliefs_df['status'].fillna('ACTIVE')

                # Get latest beliefs for each strategy
                latest_beliefs = beliefs_df.sort_values('date').groupby('strategy').tail(1)
                latest_beliefs = latest_beliefs[
                    ~latest_beliefs['strategy'].astype(str).map(
                        lambda s: is_feature_only_strategy(s) or is_archived_strategy(s)
                    )
                ].copy()
                
                for _, row in latest_beliefs.iterrows():
                    beliefs[row['strategy']] = {
                        'skill_prob': float(row['skill_prob']),
                        'confidence': float(row['confidence']),
                        'effective_skill': float(row['effective_skill']),
                        'regime_fit': float(row['regime_fit']),
                        'status': str(row['status']),
                        'sharpe': float(row['sharpe']),
                        'alpha': float(row['alpha']),
                        'beta': float(row['beta'])
                    }
                
                print(f"   ✅ Loaded beliefs for {len(beliefs)} strategies")
                
            except Exception as e:
                print(f"   ⚠️ Error loading beliefs: {e}")
        
        return beliefs

    def load_edge_half_life(self):
        """Load edge half-life health scores if available."""
        try:
            if os.path.exists(self.paths['edge_half_life']):
                with open(self.paths['edge_half_life'], 'r') as f:
                    payload = json.load(f)
                strategies = payload.get('strategies', {})
                return {k: v.get('edge_health', 1.0) for k, v in strategies.items()}
        except Exception as e:
            print(f"   ⚠️ Could not load edge half-life: {e}")
        return {}
    
    def load_strategy_tailwinds(self):
        """Load strategy tailwinds from the tailwind engine"""
        
        print("🌬️ Loading strategy tailwinds...")
        
        tailwinds = {}
        
        try:
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(__file__)))
            
            from intelligence.simple_tailwind_engine import SimpleTailwindEngine
            
            tailwind_engine = SimpleTailwindEngine()
            all_tailwinds = tailwind_engine.get_all_tailwinds()
            
            if all_tailwinds:
                tailwinds = all_tailwinds
                print(f"   ✅ Loaded tailwinds for {len(tailwinds)} strategies")
                
                # Show top tailwinds
                sorted_tailwinds = sorted(tailwinds.items(), 
                                        key=lambda x: x[1]['combined_score'], reverse=True)
                print(f"   🌬️ Top 3 tailwinds:")
                for strategy, data in sorted_tailwinds[:3]:
                    print(f"      {strategy}: {data['combined_score']:.3f}")
            else:
                print("   ⚠️ No tailwind data available")
                
        except Exception as e:
            print(f"   ⚠️ Error loading tailwinds: {e}")

        if not tailwinds:
            try:
                tailwind_file = 'data/intelligence/strategy_tailwinds.parquet'
                if os.path.exists(tailwind_file):
                    tailwind_df = pd.read_parquet(tailwind_file)
                    tailwinds = self._normalize_tailwind_frame(tailwind_df)
                    if tailwinds:
                        print(f"   ✅ Loaded compatible tailwinds from file for {len(tailwinds)} keys")
            except Exception as e2:
                print(f"   ⚠️ Fallback loading also failed: {e2}")
        
        return tailwinds
    def load_strategy_regret(self):
        """Load strategy regret from the regret engine"""
        
        print("😈 Loading strategy regret...")
        
        regret = {}
        regret_file = 'data/processed/strategy_regret.parquet'
        
        if os.path.exists(regret_file):
            try:
                regret_df = pd.read_parquet(regret_file)
                if regret_df.empty or 'strategy' not in regret_df.columns:
                    return regret

                # Legacy compatibility:
                # Some runs only store [strategy, cumulative_regret].
                if 'cum_regret' not in regret_df.columns and 'cumulative_regret' in regret_df.columns:
                    regret_df = regret_df.rename(columns={'cumulative_regret': 'cum_regret'})

                if 'date' in regret_df.columns:
                    latest_regret = regret_df.sort_values('date').groupby('strategy').tail(1)
                else:
                    latest_regret = regret_df.groupby('strategy').tail(1)

                # Derive missing normalized fields when absent.
                if 'cum_regret' not in latest_regret.columns:
                    latest_regret['cum_regret'] = 0.0
                latest_regret['cum_regret'] = pd.to_numeric(latest_regret['cum_regret'], errors='coerce').fillna(0.0)

                rmin = float(latest_regret['cum_regret'].min())
                rmax = float(latest_regret['cum_regret'].max())
                if rmax > rmin:
                    inferred_norm = (latest_regret['cum_regret'] - rmin) / (rmax - rmin)
                else:
                    inferred_norm = pd.Series(0.5, index=latest_regret.index)

                if 'normalized_regret' not in latest_regret.columns:
                    latest_regret['normalized_regret'] = inferred_norm
                else:
                    latest_regret['normalized_regret'] = pd.to_numeric(
                        latest_regret['normalized_regret'], errors='coerce'
                    ).fillna(inferred_norm)

                if 'penalty_score' not in latest_regret.columns:
                    latest_regret['penalty_score'] = latest_regret['normalized_regret']
                else:
                    latest_regret['penalty_score'] = pd.to_numeric(
                        latest_regret['penalty_score'], errors='coerce'
                    ).fillna(latest_regret['normalized_regret'])
                if 'regret_30d' not in latest_regret.columns:
                    latest_regret['regret_30d'] = latest_regret['cum_regret']
                if 'regret_90d' not in latest_regret.columns:
                    latest_regret['regret_90d'] = latest_regret['cum_regret']
                if 'drawdown' not in latest_regret.columns:
                    latest_regret['drawdown'] = 0.0
                
                for _, row in latest_regret.iterrows():
                    regret[row['strategy']] = {
                        'cum_regret': float(row['cum_regret']),
                        'regret_30d': float(row['regret_30d']),
                        'regret_90d': float(row['regret_90d']),
                        'normalized_regret': float(row['normalized_regret']),
                        'penalty_score': float(row['penalty_score']),
                        'drawdown': float(row['drawdown'])
                    }
                
                print(f"   ✅ Loaded regret for {len(regret)} strategies")
                
            except Exception as e:
                print(f"   ⚠️ Error loading regret: {e}")
        
        return regret
    
    def load_no_edge_state(self):
        """Load NO_EDGE state from detector"""
        
        print("🚨 Loading NO_EDGE state...")
        
        try:
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(__file__)))
            
            from intelligence.no_edge_detector import NoEdgeDetector
            
            detector = NoEdgeDetector()
            current_state = detector.detect_no_edge_state()
            if not isinstance(current_state, dict) or not current_state:
                current_state = detector.get_current_state()
            
            print(f"   📊 Current state: {current_state['state']}")
            print(f"   📊 Exposure cap: {current_state['exposure_cap']:.0%}")
            if current_state['reasons']:
                print(f"   📊 Reasons: {len(current_state['reasons'])}")
            
            return current_state
            
        except Exception as e:
            print(f"   ⚠️ Error loading NO_EDGE state: {e}")
            
            # Fallback: try to load directly from file
            try:
                no_edge_file = 'data/intelligence/no_edge_state.parquet'
                if os.path.exists(no_edge_file):
                    state_df = pd.read_parquet(no_edge_file)
                    
                    if not state_df.empty:
                        latest = state_df.iloc[-1]
                        # Canonical schema
                        if 'exposure_cap' in state_df.columns:
                            reasons_raw = latest.get('reasons', '')
                            reasons = reasons_raw.split('; ') if isinstance(reasons_raw, str) and reasons_raw else []
                            return {
                                'state': latest.get('state', 'NORMAL'),
                                'exposure_cap': float(latest.get('exposure_cap', 0.8)),
                                'reasons': reasons,
                                'date': latest.get('date')
                            }

                        # Legacy schema compatibility
                        state_val = str(latest.get('state', 'NORMAL')).upper()
                        if state_val not in {'NORMAL', 'NO_EDGE'}:
                            edge_strength = float(pd.to_numeric(latest.get('edge_strength', np.nan), errors='coerce'))
                            confidence = float(pd.to_numeric(latest.get('confidence', np.nan), errors='coerce'))
                            state_val = 'NO_EDGE' if (
                                (not np.isnan(edge_strength) and edge_strength < 0.45) or
                                (not np.isnan(confidence) and confidence < 0.55)
                            ) else 'NORMAL'
                        return {
                            'state': state_val,
                            'exposure_cap': 0.2 if state_val == 'NO_EDGE' else 0.8,
                            'reasons': [],
                            'date': latest['date']
                        }
                
            except Exception as e2:
                print(f"   ⚠️ Fallback loading also failed: {e2}")
            
            # Ultimate fallback
            return {
                'state': 'NORMAL',
                'exposure_cap': 0.8,
                'reasons': [],
                'date': datetime.now().date()
            }

    def load_governor_state(self):
        """Load canonical governor budget so allocator respects the unified equity envelope."""
        print("🏛️ Loading governor state...")

        try:
            state_path = PROJECT_ROOT / self.paths['unified_state']
            if not state_path.exists():
                print("   ⚠️ Unified state snapshot missing")
                return {}

            payload = json.loads(state_path.read_text(encoding='utf-8'))
            governor_state = payload.get('governor_state', {}) if isinstance(payload, dict) else {}
            if not isinstance(governor_state, dict):
                return {}

            equity_fraction = pd.to_numeric(governor_state.get('equity_fraction'), errors='coerce')
            regime = str(governor_state.get('capital_structure_regime', '') or '')
            total_capital = pd.to_numeric(governor_state.get('total_capital_inr'), errors='coerce')
            if pd.isna(equity_fraction) or float(equity_fraction) <= 0 or regime.upper() == 'UNKNOWN':
                print("   ⚠️ Governor state unavailable or still defaulted")
                return {}

            options_fraction = pd.to_numeric(governor_state.get('options_fraction'), errors='coerce')
            cash_fraction = pd.to_numeric(governor_state.get('cash_fraction'), errors='coerce')
            options_notional_deployed = self._get_options_notional_deployed()
            available_equity_fraction = float(np.clip(float(equity_fraction), 0.0, 1.0))
            total_capital_value = float(0.0 if pd.isna(total_capital) else total_capital)
            if total_capital_value > 0.0 and options_notional_deployed > 0.0:
                available_equity_fraction = max(
                    0.0,
                    available_equity_fraction - (options_notional_deployed / total_capital_value),
                )
            result = {
                'capital_structure_regime': regime,
                'equity_fraction': float(np.clip(float(equity_fraction), 0.0, 1.0)),
                'available_equity_fraction': float(available_equity_fraction),
                'options_fraction': float(np.clip(0.0 if pd.isna(options_fraction) else float(options_fraction), 0.0, 1.0)),
                'cash_fraction': float(np.clip(0.0 if pd.isna(cash_fraction) else float(cash_fraction), 0.0, 1.0)),
                'total_capital_inr': total_capital_value,
                'options_notional_deployed': float(options_notional_deployed),
                'primary_rationale': str(governor_state.get('primary_rationale', '') or ''),
                'last_morning_decision': governor_state.get('last_morning_decision'),
            }
            print(
                f"   ✅ Governor budget loaded: {result['capital_structure_regime']} "
                f"(equity={result['equity_fraction']:.1%}, available={result['available_equity_fraction']:.1%})"
            )
            return result
        except Exception as e:
            print(f"   ⚠️ Error loading governor state: {e}")
            return {}

    def calculate_regret(self, strategy_data):
        """Calculate and update regret for each strategy"""
        
        print("😈 Calculating strategy regret...")
        
        # Load existing regret or initialize
        if os.path.exists(self.paths['strategy_regret']):
            regret_df = pd.read_parquet(self.paths['strategy_regret'])
            regret = regret_df.set_index('strategy')['cumulative_regret'].to_dict()
        else:
            regret = {}
        
        # Find best performer each day
        all_returns = {}
        max_length = 0
        
        for strategy, data in strategy_data.items():
            returns = data.get('recent_returns', [])
            if returns:
                all_returns[strategy] = returns
                max_length = max(max_length, len(returns))
        
        if not all_returns:
            return regret
        
        # Calculate daily regret
        for i in range(max_length):
            daily_returns = {}
            for strategy, returns in all_returns.items():
                if i < len(returns):
                    daily_returns[strategy] = returns[i]
            
            if daily_returns:
                best_return = max(daily_returns.values())
                
                for strategy, return_val in daily_returns.items():
                    if strategy not in regret:
                        regret[strategy] = 0.0
                    regret[strategy] += max(0, best_return - return_val)
        
        # Save regret
        regret_df = pd.DataFrame(list(regret.items()), columns=['strategy', 'cumulative_regret'])
        regret_df.to_parquet(self.paths['strategy_regret'], index=False)
        
        print(f"   ✅ Updated regret for {len(regret)} strategies")
        return regret
    
    def calculate_health_scores(self, strategy_data, beliefs, regret, regime, tailwinds):
        """Calculate comprehensive health scores using beliefs, regret, and tailwinds"""
        
        print("⚖️ Calculating strategy health scores with beliefs, regret, and tailwinds...")
        
        health_scores = {}
        
        for strategy, data in strategy_data.items():
            # Get beliefs data
            belief_data = beliefs.get(strategy, {})
            regret_data = regret.get(strategy, {})
            tailwind_data = self._resolve_tailwind_for_strategy(strategy, tailwinds)
            feature_overlay = (self._latest_feature_overlays or {}).get(strategy, {})
            if not feature_overlay:
                feature_overlay = self._load_saved_feature_overlays().get(strategy, {})
            
            # Skip if strategy is not ACTIVE or FADING
            if belief_data.get('status') not in ['ACTIVE', 'FADING']:
                # But don't completely kill strategies with good Sharpe ratios or tailwinds
                sharpe = data.get('sharpe', 0)
                tailwind_score = tailwind_data.get('combined_score', 0)
                
                if sharpe > 1.0 or tailwind_score > 1.5:  # Give high-performing strategies a chance
                    print(f"   🔄 Rescuing high-performing strategy: {strategy} (Sharpe: {sharpe:.2f}, Tailwind: {tailwind_score:.2f})")
                    # Override status for allocation - continue processing this strategy
                    belief_data = dict(belief_data)
                    belief_data['status'] = 'FADING'
                    # Don't skip - let it continue to health calculation
                else:
                    health_scores[strategy] = {
                        'health_score': -999,  # Kill non-active strategies
                        'effective_skill': 0,
                        'regret_penalty': 1.0,
                        'tailwind_score': tailwind_score,
                        'status': belief_data.get('status', 'UNKNOWN'),
                        'alive': False
                    }
                    continue
            
            # Core belief metrics
            effective_skill = belief_data.get('effective_skill', 0.1)
            skill_prob = belief_data.get('skill_prob', 0.5)
            confidence = belief_data.get('confidence', 0.1)
            regime_fit = belief_data.get('regime_fit', 1.0)
            
            # Regret penalties
            normalized_regret = regret_data.get('normalized_regret', 0.5)
            penalty_score = regret_data.get('penalty_score', 0.5)
            drawdown = abs(regret_data.get('drawdown', 0))
            
            # Tailwind enhancement
            tailwind_score = tailwind_data.get('combined_score', 1.0)
            regime_tailwind = tailwind_data.get('regime_tailwind', 1.0)
            
            # Performance metrics
            sharpe = data.get('sharpe', 0)
            ann_return = data.get('ann_return', 0)
            full_sharpe = data.get('full_sharpe', sharpe)
            full_ann_return = data.get('full_ann_return', ann_return)
            family = self._tailwind_family_for_strategy(strategy)
            
            # Calculate final score using beliefs + regret + tailwinds
            base_score = (
                effective_skill -
                0.3 * normalized_regret -
                0.2 * drawdown
            )
            
            # Apply tailwind boost (30% weight on tailwinds)
            tailwind_boost = 0.3 * (tailwind_score - 1.0)  # Neutral tailwind = 1.0
            final_score = base_score + tailwind_boost
            feature_overlay_score = self._safe_float(feature_overlay.get('overlay_score', 0.0), 0.0)
            final_score += feature_overlay_score
            
            # Apply legacy regime boost (for backward compatibility)
            current_regime = regime.get('macro_regime', 'neutral')
            legacy_regime_boost = self._regime_boost_for_strategy(strategy, current_regime)
            final_score *= legacy_regime_boost
            
            # Determine if strategy is alive (enhanced criteria with tailwinds)
            is_alive = (
                (
                    final_score >= self.params['min_alive_score'] and
                    skill_prob >= self.params['min_alive_skill_prob'] and
                    confidence >= self.params['min_alive_confidence'] and
                    tailwind_score >= self.params['min_alive_tailwind']
                ) or
                (
                    sharpe > 1.25 and tailwind_score >= 0.95
                ) or
                (
                    ann_return > 0.03 and
                    sharpe >= 0.35 and
                    skill_prob >= 0.50 and
                    confidence >= 0.60 and
                    tailwind_score >= 0.95
                ) or
                (
                    final_score >= 0.0 and
                    skill_prob >= 0.50 and
                    confidence >= 0.90 and
                    tailwind_score >= 0.95 and
                    family in {"quality", "value", "defensive"}
                ) or
                (
                    family in {"quality", "value", "defensive", "ownership", "alternative", "sentiment"} and
                    full_ann_return >= 0.05 and
                    full_sharpe >= 0.60 and
                    confidence >= 0.90 and
                    tailwind_score >= 0.95
                )
            )

            health_scores[strategy] = {
                'family': family,
                'health_score': final_score,
                'base_score': base_score,
                'tailwind_boost': tailwind_boost,
                'feature_overlay_score': feature_overlay_score,
                'feature_overlay_components': int(self._safe_float(feature_overlay.get('component_count', 0), 0)),
                'feature_overlay_positive_share': self._safe_float(feature_overlay.get('positive_share', 0.0), 0.0),
                'effective_skill': effective_skill,
                'skill_prob': skill_prob,
                'confidence': confidence,
                'regime_fit': regime_fit,
                'normalized_regret': normalized_regret,
                'penalty_score': penalty_score,
                'regime_boost': legacy_regime_boost,
                'tailwind_score': tailwind_score,
                'regime_tailwind': regime_tailwind,
                'sharpe': sharpe,
                'ann_return': ann_return,
                'full_sharpe': full_sharpe,
                'full_ann_return': full_ann_return,
                'drawdown': drawdown,
                'status': belief_data.get('status', 'ACTIVE'),
                'alive': is_alive
            }
        
        print(f"   ✅ Calculated health scores for {len(health_scores)} strategies")
        
        # Show enhanced filtering
        active_count = sum(1 for h in health_scores.values() if h['status'] == 'ACTIVE')
        alive_count = sum(1 for h in health_scores.values() if h['alive'])
        tailwind_boosted = sum(1 for h in health_scores.values() if h.get('tailwind_boost', 0) > 0)
        
        print(f"   📊 Active strategies: {active_count}")
        print(f"   📊 Alive strategies: {alive_count}")
        print(f"   🌬️ Tailwind boosted: {tailwind_boosted}")
        
        return health_scores
    
    def allocate_capital(self, health_scores, no_edge_state, edge_health=None, strategy_data=None, freeze_state=None, governor_state=None):
        """Allocate capital using risk-normalized optimization with turnover governance."""
        
        print("🎯 Allocating capital across strategies...")
        edge_health = edge_health or {}
        strategy_data = strategy_data or {}
        freeze_state = freeze_state or {'freeze_active': False, 'actions': {}}
        governor_state = governor_state or {}
        
        # Apply NO_EDGE exposure capping
        exposure_cap = float(no_edge_state.get('exposure_cap', 0.8))
        governor_equity_cap = pd.to_numeric(
            (governor_state or {}).get('available_equity_fraction', (governor_state or {}).get('equity_fraction')),
            errors='coerce',
        )
        if pd.notna(governor_equity_cap):
            governor_equity_cap = float(np.clip(float(governor_equity_cap), 0.0, 1.0))
            if governor_equity_cap > 0.0:
                if governor_equity_cap < exposure_cap:
                    print(f"   🏛️ Governor equity cap: {exposure_cap:.0%} -> {governor_equity_cap:.0%}")
                exposure_cap = min(exposure_cap, governor_equity_cap)
        if freeze_state.get('freeze_active'):
            freeze_cap = float((freeze_state.get('actions') or {}).get(
                'target_max_exposure',
                self.params.get('freeze_max_exposure', 0.15),
            ))
            exposure_cap = min(exposure_cap, freeze_cap)
            no_edge_state = dict(no_edge_state)
            no_edge_state['exposure_cap'] = exposure_cap

        is_no_edge = no_edge_state.get('state') == 'NO_EDGE'
        
        if is_no_edge:
            print(f"   🚨 NO_EDGE state detected - capping exposure at {exposure_cap:.0%}")
            print(f"   🚨 Reasons: {', '.join(no_edge_state.get('reasons', []))}")
        if freeze_state.get('freeze_active'):
            print(f"   🧊 Freeze mode active - exposure clamped to {exposure_cap:.0%}")
        
        # Filter alive strategies
        alive_strategies = {k: v for k, v in health_scores.items() if v['alive']}

        # Keep only the strongest conviction set to reduce dilution.
        max_live = max(1, int(self.params.get('max_live_strategies', 8)))
        if len(alive_strategies) > max_live:
            ranked = sorted(
                alive_strategies.items(),
                key=lambda kv: (
                    kv[1].get('health_score', 0.0) *
                    kv[1].get('skill_prob', 0.5) *
                    max(0.5, kv[1].get('tailwind_score', 1.0)) *
                    max(0.25, edge_health.get(kv[0], 1.0))
                ),
                reverse=True,
            )
            diversified_ranked = []
            selected_names = set()
            for family in ["momentum", "quality", "value", "defensive", "sentiment", "alternative", "ownership", "composite"]:
                family_candidates = [item for item in ranked if self._tailwind_family_for_strategy(item[0]) == family]
                if family_candidates:
                    diversified_ranked.append(family_candidates[0])
                    selected_names.add(family_candidates[0][0])
                if len(diversified_ranked) >= max_live:
                    break
            for item in ranked:
                if item[0] in selected_names:
                    continue
                diversified_ranked.append(item)
                selected_names.add(item[0])
                if len(diversified_ranked) >= max_live:
                    break
            alive_strategies = dict(diversified_ranked[:max_live])
            print(f"   🎯 High-conviction concentration: keeping top {len(alive_strategies)} strategies")
        
        if not alive_strategies:
            print("   ⚠️ No strategies alive! Using fallback allocation...")
            
            # Fallback: allocate to strategies with best raw performance
            fallback_strategies = {}
            for strategy, data in health_scores.items():
                if data.get('sharpe', 0) > 0.5:  # Positive Sharpe strategies
                    fallback_strategies[strategy] = data
            
            if fallback_strategies:
                print(f"   🔄 Using {len(fallback_strategies)} fallback strategies")
                alive_strategies = fallback_strategies
            else:
                # Ultimate fallback: equal weight top 3 by Sharpe
                sorted_by_sharpe = sorted(health_scores.items(), 
                                        key=lambda x: x[1].get('sharpe', -999), reverse=True)
                top_3 = dict(sorted_by_sharpe[:3])
                
                # Apply NO_EDGE capping to fallback allocation
                equal_weight = exposure_cap / len(top_3)
                allocations = {k: equal_weight for k in top_3.keys()}
                
                print(f"   🆘 Emergency allocation: equal weight to top 3 strategies (capped at {exposure_cap:.0%})")
                return allocations

        previous_allocations = self._load_previous_allocations()
        allocations = self._risk_normalized_optimizer(
            alive_strategies=alive_strategies,
            health_scores=health_scores,
            strategy_data=strategy_data,
            exposure_cap=exposure_cap,
            previous_allocations=previous_allocations,
            freeze_state=freeze_state,
        )

        # Fallback path if optimizer lacks enough return history.
        if not allocations:
            print("   ⚠️ Optimizer fallback: insufficient return matrix, using softmax conviction allocation")
            scored = {}
            for strategy, data in alive_strategies.items():
                score = float(max(0.0, data.get('health_score', 0.0)) * data.get('skill_prob', 0.5))
                if score > 0:
                    scored[strategy] = score
            if not scored:
                scored = {k: 1.0 for k in alive_strategies.keys()}
            vals = np.array(list(scored.values()), dtype=float)
            exp_vals = np.exp(vals / max(1e-6, float(self.params.get('temperature', 0.75))))
            raw = exp_vals / np.clip(exp_vals.sum(), 1e-12, None)
            allocations = {
                s: float(raw[i] * exposure_cap)
                for i, s in enumerate(scored.keys())
            }
            self.last_optimizer_diagnostics = {
                'method': 'softmax_fallback',
                'n_strategies': len(allocations),
            }

        # Apply edge half-life decay (capital decay)
        if allocations:
            alpha = self.params.get('edge_decay_alpha', 2.0)
            allocations = {
                k: v * (edge_health.get(k, 1.0) ** alpha) for k, v in allocations.items()
            }
            total_alloc = sum(allocations.values())
            if total_alloc > 0:
                scale_factor = min(1.0, exposure_cap / total_alloc)
                allocations = {k: v * scale_factor for k, v in allocations.items()}

            diversification_candidates = [
                strategy
                for strategy, metrics in alive_strategies.items()
                if self._tailwind_family_for_strategy(strategy) in {"quality", "value", "defensive", "ownership"}
                and (
                    float(metrics.get("health_score", 0.0) or 0.0) >= 0.0
                    or float(metrics.get("full_sharpe", 0.0) or 0.0) >= 0.60
                    or float(metrics.get("full_ann_return", 0.0) or 0.0) >= 0.05
                )
            ]
            if diversification_candidates:
                total_alloc = sum(allocations.values())
                headroom = max(0.0, exposure_cap - total_alloc)
                floor_target = min(0.015, headroom / max(1, len(diversification_candidates)))
                if floor_target > 0.0:
                    for strategy in diversification_candidates:
                        allocations[strategy] = max(float(allocations.get(strategy, 0.0) or 0.0), floor_target)

                    total_alloc = sum(allocations.values())
                    if total_alloc > exposure_cap:
                        excess = total_alloc - exposure_cap
                        reducible = {
                            strategy: float(weight)
                            for strategy, weight in allocations.items()
                            if strategy not in diversification_candidates and float(weight) > 0.0
                        }
                        reducible_total = sum(reducible.values())
                        if reducible_total > 0.0:
                            reduction_scale = min(1.0, excess / reducible_total)
                            for strategy, weight in reducible.items():
                                allocations[strategy] = max(0.0, weight * (1.0 - reduction_scale))

        allocations = self._apply_policy_caps(allocations, exposure_cap)

        final_exposure = sum(allocations.values())
        print(f"   ✅ Allocated capital across {len(allocations)} strategies")
        print(f"   📊 Total exposure: {final_exposure:.1%} (cap: {exposure_cap:.0%})")
        if self.last_optimizer_diagnostics:
            method = self.last_optimizer_diagnostics.get('method', 'unknown')
            print(f"   🧮 Allocator method: {method}")
        
        return allocations
    
    def save_allocations(self, allocations, regime, health_scores, no_edge_state, freeze_state=None, governor_state=None):
        """Save capital allocations and history with NO_EDGE state"""
        
        timestamp = datetime.now()
        freeze_state = freeze_state or {'freeze_active': False, 'actions': {}}
        parameter_version = {}
        try:
            p = self.paths.get('parameter_version')
            if p and os.path.exists(p):
                with open(p, 'r') as f:
                    parameter_version = json.load(f)
        except Exception:
            parameter_version = {}
        
        # Current allocation
        allocation_data = {
            'timestamp': timestamp.isoformat(),
            'date': timestamp.date().isoformat(),
            'regime': regime,
            'no_edge_state': no_edge_state,
            'governor_state': governor_state or {},
            'freeze_state': freeze_state,
            'allocations': allocations,
            'strategy_health': {k: v['health_score'] for k, v in health_scores.items()},
            'strategy_diagnostics': {
                k: {
                    'family': self._tailwind_family_for_strategy(k),
                    'policy_mode': strategy_surface_mode(k),
                    'policy_role': strategy_role(k),
                    'alive': bool(v.get('alive', False)),
                    'status': str(v.get('status', 'UNKNOWN')),
                    'health_score': float(v.get('health_score', 0.0) or 0.0),
                    'skill_prob': float(v.get('skill_prob', 0.0) or 0.0),
                    'confidence': float(v.get('confidence', 0.0) or 0.0),
                    'tailwind_score': float(v.get('tailwind_score', 0.0) or 0.0),
                    'regime_boost': float(v.get('regime_boost', 1.0) or 1.0),
                    'sharpe': float(v.get('sharpe', 0.0) or 0.0),
                    'ann_return': float(v.get('ann_return', 0.0) or 0.0),
                    'full_sharpe': float(v.get('full_sharpe', 0.0) or 0.0),
                    'full_ann_return': float(v.get('full_ann_return', 0.0) or 0.0),
                    'drawdown': float(v.get('drawdown', 0.0) or 0.0),
                    'feature_overlay_score': float(v.get('feature_overlay_score', 0.0) or 0.0),
                    'feature_overlay_components': int(v.get('feature_overlay_components', 0) or 0),
                }
                for k, v in health_scores.items()
            },
            'feature_overlays': self._latest_feature_overlays,
            'strategy_fabric_multipliers': {k: float(v.get('fabric_multiplier', 1.0)) for k, v in health_scores.items()},
            'edge_health': self.load_edge_half_life(),
            'optimizer_diagnostics': self.last_optimizer_diagnostics,
            'parameter_version': {
                'version_id': parameter_version.get('version_id', 'unknown'),
                'git_commit': parameter_version.get('git_commit', 'unknown'),
            },
            'total_strategies': len(allocations),
            'alive_strategies': sum(1 for v in health_scores.values() if v['alive']),
            'total_exposure': sum(allocations.values()),
            'exposure_cap': no_edge_state.get('exposure_cap', 0.8)
        }
        governor_equity = pd.to_numeric((governor_state or {}).get('equity_fraction'), errors='coerce')
        allocation_data['effective_exposure_cap'] = min(
            float(no_edge_state.get('exposure_cap', 0.8) or 0.8),
            float(
                pd.to_numeric(
                    (governor_state or {}).get('available_equity_fraction', governor_equity),
                    errors='coerce',
                )
            ) if pd.notna(
                pd.to_numeric(
                    (governor_state or {}).get('available_equity_fraction', governor_equity),
                    errors='coerce',
                )
            ) else 1.0,
        )
        allocation_data['enforce_total_exposure_as_cap'] = False
        
        # Save current allocations
        with open(self.paths['capital_allocations'], 'w') as f:
            json.dump(allocation_data, f, indent=2, default=str)
        
        # Update allocation history
        history_row = {
            'date': timestamp.date(),
            'regime': regime.get('macro_regime', 'neutral'),
            'no_edge_state': no_edge_state.get('state', 'NORMAL'),
            'freeze_active': bool(freeze_state.get('freeze_active', False)),
            'exposure_cap': no_edge_state.get('exposure_cap', 0.8),
            'total_exposure': sum(allocations.values()),
            **allocations
        }
        
        if os.path.exists(self.paths['allocation_history']):
            history_df = pd.read_parquet(self.paths['allocation_history'])
            history_df = pd.concat([history_df, pd.DataFrame([history_row])], ignore_index=True)
        else:
            history_df = pd.DataFrame([history_row])
        
        history_df.to_parquet(self.paths['allocation_history'], index=False)
        
        print(f"   ✅ Saved allocations: {self.paths['capital_allocations']}")
        print(f"   📊 NO_EDGE state: {no_edge_state.get('state', 'NORMAL')}")
        print(f"   📊 Exposure cap: {no_edge_state.get('exposure_cap', 0.8):.0%}")
    
    def run_allocation(self):
        """Main allocation process with beliefs and regret integration"""
        
        print("🧠 CAPITAL ALLOCATOR - BAYESIAN MODEL ALLOCATION")
        print("=" * 60)
        
        # Load data
        strategy_data = self.load_strategy_performance()
        regime = self.load_market_regime()
        
        if not strategy_data:
            print("❌ No strategy performance data available")
            return {}
        
        # Load beliefs, regret, tailwinds, NO_EDGE state, and edge decay (FULLY ENHANCED!)
        beliefs = self.load_strategy_beliefs()
        regret = self.load_strategy_regret()
        tailwinds = self.load_strategy_tailwinds()
        fabric_insights = self.load_weekly_fabric_insights()
        no_edge_state = self.load_no_edge_state()
        governor_state = self.load_governor_state()
        edge_health = self.load_edge_half_life()
        freeze_state = self.load_model_freeze_state()

        if freeze_state.get('freeze_active'):
            freeze_cap = float((freeze_state.get('actions') or {}).get(
                'target_max_exposure',
                self.params.get('freeze_max_exposure', 0.15),
            ))
            original_cap = float(no_edge_state.get('exposure_cap', 0.8))
            no_edge_state = dict(no_edge_state)
            no_edge_state['exposure_cap'] = min(original_cap, freeze_cap)
            reasons = list(no_edge_state.get('reasons', []))
            reasons.append("model_freeze_active")
            no_edge_state['reasons'] = reasons
            print(
                f"   🧊 Freeze governance active: exposure cap "
                f"{original_cap:.0%} -> {no_edge_state['exposure_cap']:.0%}"
            )
        
        # Calculate health scores using beliefs, regret, and tailwinds
        health_scores = self.calculate_health_scores(strategy_data, beliefs, regret, regime, tailwinds)
        health_scores = self.apply_weekly_fabric_conditioning(health_scores, fabric_insights)
        
        # Allocate capital with NO_EDGE exposure capping
        allocations = self.allocate_capital(
            health_scores,
            no_edge_state,
            edge_health,
            strategy_data=strategy_data,
            freeze_state=freeze_state,
            governor_state=governor_state,
        )
        
        # Save results
        if allocations:
            self.save_allocations(
                allocations,
                regime,
                health_scores,
                no_edge_state,
                freeze_state=freeze_state,
                governor_state=governor_state,
            )
            
            # Print fully enhanced summary
            print(f"\n📊 FULLY ENHANCED CAPITAL ALLOCATION SUMMARY (WITH NO_EDGE)")
            print(f"   Regime: {regime.get('macro_regime', 'neutral')}")
            print(f"   NO_EDGE State: {no_edge_state.get('state', 'NORMAL')}")
            print(f"   Freeze State: {'ACTIVE' if freeze_state.get('freeze_active') else 'inactive'}")
            print(f"   Exposure Cap: {no_edge_state.get('exposure_cap', 0.8):.0%}")
            print(f"   Total Exposure: {sum(allocations.values()):.1%}")
            print(f"   Active Strategies: {len(allocations)}")
            print(f"\n   Top Allocations (with beliefs + tailwinds + NO_EDGE):")
            
            sorted_allocs = sorted(allocations.items(), key=lambda x: x[1], reverse=True)
            for strategy, allocation in sorted_allocs[:5]:
                health = health_scores.get(strategy, {})
                skill = health.get('skill_prob', 0)
                regret = health.get('normalized_regret', 0)
                tailwind = health.get('tailwind_score', 0)
                status = health.get('status', 'UNKNOWN')
                
                print(f"     {strategy}: {allocation:.1%} "
                      f"(skill: {skill:.1%}, regret: {regret:.1%}, tailwind: {tailwind:.2f}, {status})")
            
            if no_edge_state.get('reasons'):
                print(f"\n   🚨 NO_EDGE Reasons:")
                for i, reason in enumerate(no_edge_state['reasons'], 1):
                    print(f"     {i}. {reason}")
        
        return allocations

def main():
    """Main execution function"""
    
    allocator = CapitalAllocator()
    allocations = allocator.run_allocation()
    
    return allocations

if __name__ == "__main__":
    main()
